from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
VERIFY_PATH = ROOT / "tools/contract_bridge/verify.py"
SUITE_PATH = ROOT / "fixtures/product-task-contract-bridge/suite.json"
SCHEMA_PATH = ROOT / "contracts/product-task-contract/1.0/schema.json"

SPEC = importlib.util.spec_from_file_location("contract_bridge_verify", VERIFY_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load contract bridge verifier")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


class SuiteContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))

    def test_rejects_replaced_case_catalog_entry(self) -> None:
        changed = copy.deepcopy(self.suite)
        changed["cases"][0]["id"] = "POSITIVE_REPLACEMENT"

        with self.assertRaisesRegex(ValueError, "exact case catalog"):
            VERIFY.validate_suite(
                changed,
                "contracts/product-task-contract/1.0/schema.json",
                "fixtures/product-task-contract-bridge/suite.json",
            )

    def test_case_internal_error_becomes_safe_failed_result(self) -> None:
        broken_context = copy.deepcopy(self.suite["trusted_context"])
        del broken_context["intent_mapping"]
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

        try:
            result = VERIFY.run_case(
                self.suite["cases"][0],
                self.suite["base_contract"],
                broken_context,
                Draft202012Validator(schema),
            )
        except Exception as exc:  # The desired contract is a safe case result.
            self.fail(f"run_case leaked {type(exc).__name__} instead of returning RUNNER_ERROR")

        self.assertEqual("FAILED", result["status"])
        self.assertEqual("RUNNER_ERROR", result["actual"])

    def test_runner_contract_error_replaces_stale_pass_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp_root = Path(temporary)
            temp_verify = temp_root / "tools/contract_bridge/verify.py"
            temp_schema = temp_root / "contracts/product-task-contract/1.0/schema.json"
            temp_suite = temp_root / "fixtures/product-task-contract-bridge/suite.json"
            temp_result = temp_root / "artifacts/verification/vg-002-contract-bridge-result.json"
            temp_report = temp_root / "artifacts/reviews/w1-contract-bridge-checkpoint.html"
            for target in (temp_verify, temp_schema, temp_suite, temp_result, temp_report):
                target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(VERIFY_PATH, temp_verify)
            shutil.copy2(SCHEMA_PATH, temp_schema)
            changed = copy.deepcopy(self.suite)
            changed["cases"][0]["id"] = "POSITIVE_REPLACEMENT"
            temp_suite.write_text(json.dumps(changed), encoding="utf-8")
            temp_result.write_text('{"status":"PASSED","stale":true}\n', encoding="utf-8")
            temp_report.write_text("STALE PASSED\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/contract_bridge/verify.py",
                    "--schema",
                    "contracts/product-task-contract/1.0/schema.json",
                    "--suite",
                    "fixtures/product-task-contract-bridge/suite.json",
                    "--result",
                    "artifacts/verification/vg-002-contract-bridge-result.json",
                    "--report",
                    "artifacts/reviews/w1-contract-bridge-checkpoint.html",
                ],
                cwd=temp_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(2, completed.returncode)
            failed_result = json.loads(temp_result.read_text(encoding="utf-8"))
            self.assertEqual("FAILED", failed_result["status"])
            self.assertEqual("RUNNER_CONTRACT_INVALID", failed_result["runner_error"])
            self.assertNotIn("stale", failed_result)
            self.assertIn("Status: FAILED", temp_report.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
