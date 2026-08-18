import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.patch_verification.anti_tamper import build_guard_manifest, verify_guard_manifest
from tools.patch_verification.model import PatchVerificationError, tree_hash
from tools.patch_verification.patch import materialize_fixture
from tools.patch_verification.profiles import TRUSTED_PROFILE_DIGEST


ROOT = Path(__file__).resolve().parents[2]
SUITE = json.loads((ROOT / "fixtures/forgeops-patch-verification/suite.json").read_text(encoding="utf-8"))


class AntiTamperTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name) / "workspace"
        materialize_fixture(self.workspace, SUITE["base_fixture"]["files"])
        self.manifest = build_guard_manifest(self.workspace, TRUSTED_PROFILE_DIGEST)

    def verify_error(self, code, *, digest=TRUSTED_PROFILE_DIGEST, manifest=None):
        before = tree_hash(self.workspace)
        with self.assertRaises(PatchVerificationError) as caught:
            verify_guard_manifest(
                self.workspace,
                manifest or self.manifest,
                trusted_profile_digest=digest,
            )
        self.assertEqual(code, caught.exception.code)
        self.assertEqual(before, tree_hash(self.workspace))

    def test_unchanged_guard_manifest_passes_and_is_closed(self):
        result = verify_guard_manifest(
            self.workspace, self.manifest, trusted_profile_digest=TRUSTED_PROFILE_DIGEST
        )
        self.assertEqual({"status": "PASSED", "tamper_count": 0}, result)
        self.assertEqual(
            ["tests/test_calculator.py", ".coveragerc", "verification-profile.json"],
            [item["path"] for item in self.manifest["protected_files"]],
        )
        self.assertEqual(
            {"manifest_version", "trusted_profile_digest", "protected_files", "test_paths"},
            set(self.manifest),
        )

    def test_deleted_and_renamed_tests_have_distinct_errors(self):
        test_path = self.workspace / "tests/test_calculator.py"
        test_path.unlink()
        self.verify_error("TEST_DELETED")
        materialize_fixture(
            self.workspace / "restore", [SUITE["base_fixture"]["files"][1]]
        )

    def test_renamed_or_added_test_path_is_rejected(self):
        test_path = self.workspace / "tests/test_calculator.py"
        test_path.replace(self.workspace / "tests/test_renamed.py")
        self.verify_error("TEST_PATH_INVALID")

    def test_skip_xfail_and_assertion_weakening_are_specific(self):
        original = (self.workspace / "tests/test_calculator.py").read_text(encoding="utf-8")
        mutations = {
            "TEST_SKIP_INJECTED": original.replace(
                "    def test_total_matches_task", "    @unittest.skip('disabled')\n    def test_total_matches_task"
            ),
            "TEST_XFAIL_INJECTED": original.replace(
                "    def test_total_matches_task", "    @unittest.expectedFailure\n    def test_total_matches_task"
            ),
            "ASSERTION_WEAKENED": original.replace(
                "self.assertEqual(5, total(2, 3))", "self.assertTrue(True)"
            ),
        }
        for code, content in mutations.items():
            with self.subTest(code=code):
                (self.workspace / "tests/test_calculator.py").write_text(content, encoding="utf-8", newline="\n")
                self.verify_error(code)
                (self.workspace / "tests/test_calculator.py").write_text(original, encoding="utf-8", newline="\n")

    def test_coverage_and_profile_changes_are_specific(self):
        coverage = self.workspace / ".coveragerc"
        original_coverage = coverage.read_text(encoding="utf-8")
        coverage.write_text(original_coverage + "    src/calculator.py\n", encoding="utf-8")
        self.verify_error("COVERAGE_POLICY_CHANGED")
        coverage.write_text(original_coverage, encoding="utf-8", newline="\n")
        profile = self.workspace / "verification-profile.json"
        profile.write_text('{"profile_id":"other","checks":[]}\n', encoding="utf-8")
        self.verify_error("VERIFICATION_PROFILE_CHANGED")

    def test_trusted_digest_and_malformed_manifest_fail_closed(self):
        self.verify_error("VERIFICATION_PROFILE_CHANGED", digest="0" * 64)
        malformed = copy.deepcopy(self.manifest)
        malformed["unexpected"] = True
        self.verify_error("VERIFICATION_PROFILE_CHANGED", manifest=malformed)
        duplicated = copy.deepcopy(self.manifest)
        duplicated["protected_files"].append(copy.deepcopy(duplicated["protected_files"][0]))
        self.verify_error("VERIFICATION_PROFILE_CHANGED", manifest=duplicated)

    def test_test_symlink_is_rejected_when_supported(self):
        target = self.workspace / "tests/test_calculator.py"
        real = self.workspace / "tests/real.py"
        target.replace(real)
        try:
            target.symlink_to(real)
        except OSError as error:
            self.skipTest(f"symlink creation unavailable: {error}")
        self.verify_error("TEST_PATH_INVALID")


if __name__ == "__main__":
    unittest.main()
