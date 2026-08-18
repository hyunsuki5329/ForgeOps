import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

from jsonschema import Draft202012Validator

from tools.patch_verification import verify


ROOT = Path(__file__).resolve().parents[2]


class RegisteredVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        for relative in (
            verify.SCHEMA_REF,
            verify.SUITE_REF,
            verify.PROFILE_SOURCE_REF,
        ):
            target = self.repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, target)

    def args(self, command_id="task-checks"):
        return argparse.Namespace(
            schema=verify.SCHEMA_REF,
            suite=verify.SUITE_REF,
            result=verify.TRUSTED_COMMANDS[command_id],
            command_id=command_id,
        )

    def test_exact_command_registry_and_all_three_success_results(self):
        self.assertEqual(
            {
                "task-checks": "artifacts/verification/vg-013-task-checks-result.json",
                "regression-checks": "artifacts/verification/vg-013-regression-checks-result.json",
                "verification-anti-tamper": "artifacts/verification/vg-013-verification-anti-tamper-result.json",
            },
            verify.TRUSTED_COMMANDS,
        )
        schema = json.loads((self.repo / verify.SCHEMA_REF).read_text(encoding="utf-8"))
        public_schema = {"$ref": "#/$defs/publicResult", "$defs": schema["$defs"]}
        for command_id in verify.TRUSTED_COMMANDS:
            with self.subTest(command_id=command_id):
                self.assertEqual(0, verify.run(self.args(command_id), repository_root=self.repo))
                result = json.loads((self.repo / verify.TRUSTED_COMMANDS[command_id]).read_text(encoding="utf-8"))
                self.assertEqual([], list(Draft202012Validator(public_schema).iter_errors(result)))
                self.assertEqual("VG-013", result["gate_id"])
                self.assertEqual("forgeops-patch-verification", result["profile_id"])
                self.assertEqual(command_id, result["command_id"])
                self.assertEqual("PASSED", result["status"])
                self.assertEqual("E2", result["evidence_tier"])
                self.assertEqual({"total": 9, "passed": 9, "failed": 0}, result["summary"])
                self.assertEqual(
                    [case["id"] for case in json.loads((self.repo / verify.SUITE_REF).read_text(encoding="utf-8"))["cases"] if case["command_id"] == command_id],
                    [case["id"] for case in result["cases"]],
                )
                self.assertIsNone(result["effect_counters"]["host_external_writes"])
                self.assertIsNone(result["effect_counters"]["network_calls"])
                serialized = json.dumps(result)
                self.assertNotIn(str(self.repo), serialized)

    def test_input_hashes_are_raw_bytes_and_result_is_atomic(self):
        self.assertEqual(0, verify.run(self.args(), repository_root=self.repo))
        result_path = self.repo / verify.TRUSTED_COMMANDS["task-checks"]
        result = json.loads(result_path.read_text(encoding="utf-8"))
        expected = {
            "schema": hashlib.sha256((self.repo / verify.SCHEMA_REF).read_bytes()).hexdigest(),
            "suite": hashlib.sha256((self.repo / verify.SUITE_REF).read_bytes()).hexdigest(),
            "profile_source": hashlib.sha256((self.repo / verify.PROFILE_SOURCE_REF).read_bytes()).hexdigest(),
        }
        self.assertEqual(expected, result["input_hashes"])
        self.assertEqual([], list(result_path.parent.glob(f".{result_path.name}.*.tmp")))

    def test_wrong_identity_and_malformed_input_preserve_sentinel(self):
        result_path = self.repo / verify.TRUSTED_COMMANDS["task-checks"]
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text("sentinel", encoding="utf-8")
        wrong = self.args()
        wrong.command_id = "unknown"
        with self.assertRaises(verify.VerificationError):
            verify.run(wrong, repository_root=self.repo)
        self.assertEqual("sentinel", result_path.read_text(encoding="utf-8"))
        (self.repo / verify.SUITE_REF).write_text("{}", encoding="utf-8")
        with self.assertRaises(verify.VerificationError):
            verify.run(self.args(), repository_root=self.repo)
        self.assertEqual("sentinel", result_path.read_text(encoding="utf-8"))

    def test_case_mismatch_writes_failed_result_and_returns_one(self):
        original = verify._evaluate_case

        def mismatch(case, fixture, observed_at):
            record, audit = original(case, fixture, observed_at)
            if case["id"] == "POSITIVE_BOUNDED_PATCH":
                record = {**record, "actual": "FORCED_MISMATCH"}
            return record, audit

        with mock.patch.object(verify, "_evaluate_case", side_effect=mismatch):
            self.assertEqual(1, verify.run(self.args(), repository_root=self.repo))
        result = json.loads((self.repo / verify.TRUSTED_COMMANDS["task-checks"]).read_text(encoding="utf-8"))
        self.assertEqual("FAILED", result["status"])
        self.assertEqual(1, result["summary"]["failed"])

    def test_observed_audit_invariants_cannot_false_pass(self):
        mutations = (
            {"source_tree_hash_unchanged": False},
            {"unauthorized_workspace_effects": 1},
            {"outside_workspace_write_attempts": 1},
            {"remote_write_attempts": 1},
            {"result_artifact_raw_secret_occurrences": 1},
        )
        original = verify._effect_counters
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                def altered(*args, **kwargs):
                    value = original(*args, **kwargs)
                    value.update(mutation)
                    return value
                with mock.patch.object(verify, "_effect_counters", side_effect=altered):
                    self.assertEqual(1, verify.run(self.args(), repository_root=self.repo))
                result = json.loads((self.repo / verify.TRUSTED_COMMANDS["task-checks"]).read_text(encoding="utf-8"))
                self.assertEqual("FAILED", result["status"])
                self.assertGreaterEqual(result["summary"]["failed"], 1)

    def test_unexpected_runner_error_returns_two_without_replacing_result(self):
        result_path = self.repo / verify.TRUSTED_COMMANDS["task-checks"]
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text("sentinel", encoding="utf-8")
        argv = [
            "--schema", verify.SCHEMA_REF,
            "--suite", verify.SUITE_REF,
            "--result", verify.TRUSTED_COMMANDS["task-checks"],
            "--command-id", "task-checks",
        ]
        with mock.patch.object(verify, "_evaluate_case", side_effect=RuntimeError("boom")):
            self.assertEqual(2, verify.main(argv, repository_root=self.repo))
        self.assertEqual("sentinel", result_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
