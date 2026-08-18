import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from tools.lifecycle_trace import verify


ROOT = Path(__file__).resolve().parents[2]


class RegisteredVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        for relative in (verify.SCHEMA_REF, verify.SUITE_REF, *verify.PROFILE_SOURCE_REFS):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def args(self, command_id="budget-cancel-negative"):
        return argparse.Namespace(schema=verify.SCHEMA_REF, suite=verify.SUITE_REF,
                                  result=verify.TRUSTED_COMMANDS[command_id], command_id=command_id)

    def test_exact_registry_and_all_four_results(self):
        self.assertEqual({
            "budget-cancel-negative": "artifacts/verification/vg-014-budget-cancel-result.json",
            "no-progress-stop": "artifacts/verification/vg-014-no-progress-result.json",
            "trace-manifest-completeness": "artifacts/verification/vg-015-trace-manifest-result.json",
            "external-write-negative": "artifacts/verification/vg-015-external-write-result.json",
        }, verify.TRUSTED_COMMANDS)
        totals = {"budget-cancel-negative": 16, "no-progress-stop": 10,
                  "trace-manifest-completeness": 12, "external-write-negative": 10}
        schema = json.loads((self.repo / verify.SCHEMA_REF).read_text(encoding="utf-8"))
        public_schema = {"$ref": "#/$defs/publicResult", "$defs": schema["$defs"]}
        for command_id, total in totals.items():
            with self.subTest(command_id=command_id):
                self.assertEqual(0, verify.run(self.args(command_id), repository_root=self.repo))
                result = json.loads((self.repo / verify.TRUSTED_COMMANDS[command_id]).read_text(encoding="utf-8"))
                self.assertEqual([], list(Draft202012Validator(public_schema).iter_errors(result)))
                self.assertEqual({"total": total, "passed": total, "failed": 0}, result["summary"])
                self.assertEqual("PASSED", result["status"])
                self.assertEqual("E2", result["evidence_tier"])
                self.assertTrue(all(case["expected"] == case["actual"] for case in result["cases"]))
                counters = result["effect_counters"]
                self.assertTrue(counters["source_tree_hash_unchanged"])
                self.assertEqual(0, counters["unauthorized_dispatches"])
                self.assertEqual(0, counters["adapter_cleanup_residues"])
                self.assertEqual(0, counters["external_write_attempts"])
                self.assertEqual(0, counters["result_artifact_raw_secret_occurrences"])
                self.assertIsNone(counters["os_process_tree_residue"])
                self.assertIsNone(counters["os_mount_residue"])
                self.assertIsNone(counters["network_calls"])

    def test_trace_command_writes_static_atomic_viewer(self):
        self.assertEqual(0, verify.run(self.args("trace-manifest-completeness"), repository_root=self.repo))
        viewer = self.repo / verify.VIEWER_REF
        text = viewer.read_text(encoding="utf-8")
        self.assertIn("ForgeOps W8 Trace", text)
        self.assertNotIn("<script", text.lower())
        self.assertEqual([], list(viewer.parent.glob(f".{viewer.name}.*.tmp")))

    def test_input_hashes_are_raw_bytes_and_result_atomic(self):
        self.assertEqual(0, verify.run(self.args(), repository_root=self.repo))
        path = self.repo / verify.TRUSTED_COMMANDS["budget-cancel-negative"]
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual({
            "schema": hashlib.sha256((self.repo / verify.SCHEMA_REF).read_bytes()).hexdigest(),
            "suite": hashlib.sha256((self.repo / verify.SUITE_REF).read_bytes()).hexdigest(),
            "profile_source": verify._profile_source_hash(self.repo),
        }, result["input_hashes"])
        self.assertEqual([], list(path.parent.glob(f".{path.name}.*.tmp")))

    def test_wrong_identity_and_malformed_suite_preserve_sentinel(self):
        result = self.repo / verify.TRUSTED_COMMANDS["budget-cancel-negative"]
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text("sentinel", encoding="utf-8")
        wrong = self.args()
        wrong.result = "artifacts/verification/other.json"
        with self.assertRaises(verify.VerificationError):
            verify.run(wrong, repository_root=self.repo)
        self.assertEqual("sentinel", result.read_text(encoding="utf-8"))
        (self.repo / verify.SUITE_REF).write_text("{}", encoding="utf-8")
        with self.assertRaises(verify.VerificationError):
            verify.run(self.args(), repository_root=self.repo)
        self.assertEqual("sentinel", result.read_text(encoding="utf-8"))

    def test_mismatch_or_unsafe_counter_cannot_false_pass(self):
        original_case = verify._evaluate_case
        def mismatch(case, fixture):
            record, audit, manifest = original_case(case, fixture)
            if case["id"] == "POSITIVE_BUDGETED_SUCCESS":
                record = {**record, "actual": "FORCED_MISMATCH"}
            return record, audit, manifest
        with mock.patch.object(verify, "_evaluate_case", side_effect=mismatch):
            self.assertEqual(1, verify.run(self.args(), repository_root=self.repo))
        original_counters = verify._effect_counters
        mutations = ({"source_tree_hash_unchanged": False}, {"unauthorized_dispatches": 1},
                     {"adapter_cleanup_residues": 1}, {"external_write_attempts": 1},
                     {"result_artifact_raw_secret_occurrences": 1})
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                def altered(*args, **kwargs):
                    value = original_counters(*args, **kwargs)
                    value.update(mutation)
                    return value
                with mock.patch.object(verify, "_effect_counters", side_effect=altered):
                    self.assertEqual(1, verify.run(self.args(), repository_root=self.repo))
                result = json.loads((self.repo / verify.TRUSTED_COMMANDS["budget-cancel-negative"]).read_text(encoding="utf-8"))
                self.assertEqual("FAILED", result["status"])

    def test_unexpected_error_returns_two_without_replacing_result(self):
        result = self.repo / verify.TRUSTED_COMMANDS["budget-cancel-negative"]
        result.parent.mkdir(parents=True, exist_ok=True)
        result.write_text("sentinel", encoding="utf-8")
        argv = ["--schema", verify.SCHEMA_REF, "--suite", verify.SUITE_REF,
                "--result", verify.TRUSTED_COMMANDS["budget-cancel-negative"],
                "--command-id", "budget-cancel-negative"]
        with mock.patch.object(verify, "_evaluate_case", side_effect=RuntimeError("boom")):
            self.assertEqual(2, verify.main(argv, repository_root=self.repo))
        self.assertEqual("sentinel", result.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
