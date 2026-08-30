import copy
import hashlib
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.local_vertical import verify


ROOT = Path(__file__).resolve().parents[2]


def namespace():
    return SimpleNamespace(
        schema="contracts/forgeops-local-vertical/1.0/schema.json",
        product_schema="contracts/product-task-contract/1.0/schema.json",
        snapshot_schema="contracts/forgeops-snapshot-contract/1.0/schema.json",
        context_schema="contracts/forgeops-context-pack/1.0/schema.json",
        suite="fixtures/forgeops-local-vertical/suite.json",
        result="artifacts/verification/vg-012-local-vertical-result.json",
        command_id="main-part-work-main",
    )


class LocalVerticalVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.repository = Path(self.temporary.name)
        for ref in (
            namespace().schema,
            namespace().product_schema,
            namespace().snapshot_schema,
            namespace().context_schema,
            namespace().suite,
        ):
            target = self.repository / ref
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / ref, target)

    def result_path(self):
        return self.repository / namespace().result

    def test_runtime_suite_schema_uses_absolute_local_id_without_mutating_contract(self):
        schema_path = self.repository / namespace().schema
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        normalized = verify._runtime_schema(schema, schema_path, namespace().schema)

        self.assertEqual(namespace().schema, schema["$id"])
        self.assertTrue(normalized["$id"].startswith("file:"))
        self.assertTrue(normalized["$id"].endswith("/contracts/forgeops-local-vertical/1.0/schema.json"))

    def test_registered_run_writes_closed_public_safe_result_atomically(self):
        result_path = self.result_path()
        result_path.parent.mkdir(parents=True)
        result_path.write_text("preserve until replace", encoding="utf-8")

        self.assertEqual(0, verify.run(namespace(), repository_root=self.repository))

        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual("PASSED", result["status"])
        self.assertEqual("E2", result["evidence_tier"])
        self.assertEqual({"total": 30, "passed": 30, "failed": 0}, result["summary"])
        self.assertTrue(result["effect_counters"]["source_tree_hash_unchanged"])
        self.assertEqual(0, result["effect_counters"]["unauthorized_fixture_effects"])
        self.assertEqual(0, result["effect_counters"]["result_artifact_raw_secret_occurrences"])
        self.assertIsNone(result["effect_counters"]["protected_reads"])
        self.assertIsNone(result["effect_counters"]["network_calls"])
        self.assertIsNone(result["effect_counters"]["external_writes"])
        self.assertEqual(30, len(result["cases"]))
        self.assertTrue(all(case["expected"] == case["actual"] for case in result["cases"]))

    def test_input_hashes_are_exact_raw_bytes_and_output_is_public_safe(self):
        verify.run(namespace(), repository_root=self.repository)
        result = json.loads(self.result_path().read_text(encoding="utf-8"))
        for name, ref in (
            ("schema", namespace().schema),
            ("product_schema", namespace().product_schema),
            ("snapshot_schema", namespace().snapshot_schema),
            ("context_schema", namespace().context_schema),
            ("suite", namespace().suite),
        ):
            self.assertEqual(hashlib.sha256((self.repository / ref).read_bytes()).hexdigest(), result["input_hashes"][name])
        rendered = json.dumps(result, ensure_ascii=False).lower()
        self.assertNotIn(str(self.repository).lower(), rendered)
        for forbidden in ("stdout", "stderr", "environment", "credential", "token"):
            self.assertNotIn(f'"{forbidden}"', rendered)

    def test_identity_or_catalog_failure_preserves_prior_result(self):
        result_path = self.result_path()
        result_path.parent.mkdir(parents=True)
        result_path.write_text("preserved", encoding="utf-8")
        args = namespace()
        args.command_id = "other"
        with self.assertRaisesRegex(verify.VerificationError, "VERIFIER_IDENTITY_INVALID"):
            verify.run(args, repository_root=self.repository)
        self.assertEqual("preserved", result_path.read_text(encoding="utf-8"))

        suite_path = self.repository / namespace().suite
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        suite["cases"][0], suite["cases"][1] = suite["cases"][1], suite["cases"][0]
        suite_path.write_text(json.dumps(suite), encoding="utf-8")
        with self.assertRaisesRegex(verify.VerificationError, "VERIFIER_INPUT_INVALID"):
            verify.run(namespace(), repository_root=self.repository)
        self.assertEqual("preserved", result_path.read_text(encoding="utf-8"))

    def test_schema_or_runner_failure_preserves_prior_result(self):
        result_path = self.result_path()
        result_path.parent.mkdir(parents=True)
        result_path.write_text("preserved", encoding="utf-8")
        schema_path = self.repository / namespace().schema
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        schema["$defs"]["public_result"]["properties"]["status"]["enum"] = ["FAILED"]
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        with self.assertRaisesRegex(verify.VerificationError, "VERIFIER_RESULT_INVALID"):
            verify.run(namespace(), repository_root=self.repository)
        self.assertEqual("preserved", result_path.read_text(encoding="utf-8"))

    def test_observed_safety_invariant_failure_cannot_emit_false_pass(self):
        scenarios = (
            ("source changed", patch.object(verify, "_tree_hash", side_effect=("before", "after"))),
            ("fixture effect", patch.object(verify, "_fixture_effect_count", return_value=1)),
            ("secret pattern", patch.object(verify, "_result_secret_occurrences", return_value=1)),
        )
        for name, mocked in scenarios:
            with self.subTest(name=name), mocked:
                self.assertEqual(1, verify.run(namespace(), repository_root=self.repository))
                result = json.loads(self.result_path().read_text(encoding="utf-8"))
                self.assertEqual("FAILED", result["status"])
                self.assertGreater(result["summary"]["failed"], 0)
                self.assertFalse(all(case["expected"] == case["actual"] for case in result["cases"]))

    def test_deleted_fixture_during_expected_negative_is_an_effect_failure(self):
        original = verify._negative_case

        def deleting_negative(mutation, fixture, product_schema, root):
            if mutation == "MAIN_PROTOCOL":
                (root / "workspace/fixture/work-item.txt").unlink()
                raise verify.common.VerticalFlowError("MAIN_CONTRACT_VERSION_UNSUPPORTED")
            return original(mutation, fixture, product_schema, root)

        with patch.object(verify, "_negative_case", side_effect=deleting_negative):
            self.assertEqual(1, verify.run(namespace(), repository_root=self.repository))
        result = json.loads(self.result_path().read_text(encoding="utf-8"))
        self.assertEqual("FAILED", result["status"])
        self.assertGreater(result["effect_counters"]["unauthorized_fixture_effects"], 0)
        self.assertGreater(result["summary"]["failed"], 0)

    def test_negative_case_cannot_hide_a_mutation_to_success_bytes(self):
        original = verify._negative_case

        def mutating_negative(mutation, fixture, product_schema, root):
            if mutation == "MAIN_PROTOCOL":
                (root / "workspace/fixture/work-item.txt").write_bytes(b"after\n")
                raise verify.common.VerticalFlowError("MAIN_CONTRACT_VERSION_UNSUPPORTED")
            return original(mutation, fixture, product_schema, root)

        with patch.object(verify, "_negative_case", side_effect=mutating_negative):
            self.assertEqual(1, verify.run(namespace(), repository_root=self.repository))
        result = json.loads(self.result_path().read_text(encoding="utf-8"))
        self.assertEqual("FAILED", result["status"])
        self.assertGreater(result["effect_counters"]["unauthorized_fixture_effects"], 0)

    def test_fixture_audit_rejects_symlink_without_dereferencing_it(self):
        audit_root = self.repository / "audit"
        source = audit_root / "source/fixture/work-item.txt"
        workspace = audit_root / "workspace/fixture/work-item.txt"
        for path in (source, workspace):
            path.parent.mkdir(parents=True)
            path.write_bytes(b"before\n")
        original_is_symlink = Path.is_symlink
        original_read_bytes = Path.read_bytes
        dereferenced_workspace = False

        def fake_is_symlink(path):
            return path == workspace or original_is_symlink(path)

        def observed_read_bytes(path):
            nonlocal dereferenced_workspace
            if path == workspace:
                dereferenced_workspace = True
            return original_read_bytes(path)

        with patch.object(Path, "is_symlink", new=fake_is_symlink), patch.object(
            Path, "read_bytes", new=observed_read_bytes
        ):
            self.assertEqual(1, verify._fixture_effect_count(audit_root))
        self.assertFalse(dereferenced_workspace)
