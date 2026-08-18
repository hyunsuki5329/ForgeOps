import copy
import json
import os
from pathlib import Path
import tempfile
import unittest

from tools.patch_verification.model import EffectAudit, PatchVerificationError, tree_hash
from tools.patch_verification.patch import apply_bounded_patch, materialize_fixture


ROOT = Path(__file__).resolve().parents[2]
SUITE = json.loads(
    (ROOT / "fixtures/forgeops-patch-verification/suite.json").read_text(encoding="utf-8")
)


class BoundedPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.source = base / "source"
        self.workspace = base / "workspace"
        files = SUITE["base_fixture"]["files"]
        materialize_fixture(self.source, files)
        materialize_fixture(self.workspace, files)
        self.intent = copy.deepcopy(SUITE["base_fixture"]["patch_intent"])
        self.audit = EffectAudit()

    def assert_error(self, code, *, intent=None, source=None, workspace=None):
        source = source or self.source
        workspace = workspace or self.workspace
        source_before = tree_hash(source)
        workspace_before = tree_hash(workspace)
        with self.assertRaises(PatchVerificationError) as caught:
            apply_bounded_patch(source, workspace, intent or self.intent, audit=self.audit)
        self.assertEqual(code, caught.exception.code)
        self.assertEqual(source_before, tree_hash(source))
        self.assertEqual(workspace_before, tree_hash(workspace))
        self.assertEqual(0, self.audit.workspace_writes)

    def test_exact_patch_changes_only_workspace_and_returns_bounded_diff(self):
        before_source = tree_hash(self.source)
        artifact = apply_bounded_patch(
            self.source, self.workspace, self.intent, audit=self.audit
        )
        self.assertEqual(before_source, tree_hash(self.source))
        self.assertIn(
            b"return left + right", (self.workspace / "src/calculator.py").read_bytes()
        )
        self.assertEqual("src/calculator.py", artifact["resource_ref"])
        self.assertEqual(self.intent["before_sha256"], artifact["before_sha256"])
        self.assertEqual(self.intent["after_sha256"], artifact["after_sha256"])
        self.assertTrue(
            artifact["diff"].startswith(
                "--- a/src/calculator.py\n+++ b/src/calculator.py\n"
            )
        )
        self.assertEqual(len(artifact["diff"].encode("utf-8")), artifact["diff_bytes"])
        self.assertEqual(2, artifact["changed_lines"])
        self.assertEqual(1, self.audit.workspace_writes)
        self.assertEqual(0, self.audit.outside_workspace_write_attempts)
        self.assertEqual(0, self.audit.remote_write_attempts)

    def test_invalid_resource_forms_are_rejected_before_mutation(self):
        for resource in ("C:/outside.py", "/outside.py", "../outside.py", "src/*.py", "src\\calculator.py", "./src/calculator.py"):
            with self.subTest(resource=resource):
                intent = copy.deepcopy(self.intent)
                intent["resource_ref"] = resource
                self.assert_error("PATCH_RESOURCE_INVALID", intent=intent)

    def test_unknown_resource_and_bad_baseline_are_rejected(self):
        intent = copy.deepcopy(self.intent)
        intent["resource_ref"] = "src/identity.py"
        self.assert_error("PATCH_RESOURCE_UNAUTHORIZED", intent=intent)
        intent = copy.deepcopy(self.intent)
        intent["before_sha256"] = "0" * 64
        self.assert_error("PATCH_BASE_MISMATCH", intent=intent)

    def test_source_cannot_be_used_as_workspace(self):
        self.assert_error(
            "PATCH_CONTAINMENT_VIOLATION", source=self.source, workspace=self.source
        )

    def test_source_and_workspace_roots_cannot_overlap(self):
        nested_workspace = self.source / "nested-workspace"
        materialize_fixture(nested_workspace, SUITE["base_fixture"]["files"])
        source_before = tree_hash(self.source)
        workspace_before = tree_hash(nested_workspace)
        with self.assertRaises(PatchVerificationError) as caught:
            apply_bounded_patch(
                self.source, nested_workspace, self.intent, audit=self.audit
            )
        self.assertEqual("PATCH_CONTAINMENT_VIOLATION", caught.exception.code)
        self.assertEqual(source_before, tree_hash(self.source))
        self.assertEqual(workspace_before, tree_hash(nested_workspace))
        self.assertEqual(0, self.audit.workspace_writes)

        nested_source = self.workspace / "nested-source"
        materialize_fixture(nested_source, SUITE["base_fixture"]["files"])
        with self.assertRaises(PatchVerificationError) as caught:
            apply_bounded_patch(
                nested_source, self.workspace, self.intent, audit=self.audit
            )
        self.assertEqual("PATCH_CONTAINMENT_VIOLATION", caught.exception.code)
        self.assertEqual(0, self.audit.workspace_writes)

    def test_raw_or_malformed_intent_is_rejected(self):
        mutations = []
        extra = copy.deepcopy(self.intent)
        extra["raw_patch"] = "--- a/x"
        mutations.append(extra)
        missing = copy.deepcopy(self.intent)
        del missing["after_sha256"]
        mutations.append(missing)
        boolean_limit = copy.deepcopy(self.intent)
        boolean_limit["max_diff_bytes"] = True
        mutations.append(boolean_limit)
        bad_hash = copy.deepcopy(self.intent)
        bad_hash["after_sha256"] = "not-a-hash"
        mutations.append(bad_hash)
        for intent in mutations:
            with self.subTest(intent=intent):
                self.assert_error("PATCH_INPUT_INVALID", intent=intent)

    def test_after_hash_and_diff_limits_are_checked_before_mutation(self):
        intent = copy.deepcopy(self.intent)
        intent["after_sha256"] = "0" * 64
        self.assert_error("PATCH_INPUT_INVALID", intent=intent)
        intent = copy.deepcopy(self.intent)
        intent["max_diff_bytes"] = 1
        self.assert_error("PATCH_DIFF_LIMIT_EXCEEDED", intent=intent)
        intent = copy.deepcopy(self.intent)
        intent["max_changed_lines"] = 1
        self.assert_error("PATCH_DIFF_LIMIT_EXCEEDED", intent=intent)

    def test_symlink_target_is_rejected_when_supported(self):
        target = self.workspace / "src/calculator.py"
        saved = self.workspace / "src/real_calculator.py"
        target.replace(saved)
        try:
            target.symlink_to(saved)
        except OSError as error:
            self.skipTest(f"symlink creation unavailable: {error}")
        self.assert_error("PATCH_CONTAINMENT_VIOLATION")

    def test_materialization_rejects_noncanonical_paths(self):
        bad = [dict(SUITE["base_fixture"]["files"][0], path="../outside.py")]
        with self.assertRaises(PatchVerificationError) as caught:
            materialize_fixture(Path(self.temp.name) / "bad", bad)
        self.assertEqual("PATCH_RESOURCE_INVALID", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
