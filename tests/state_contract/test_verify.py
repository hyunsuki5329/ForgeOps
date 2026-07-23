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


ROOT = Path(__file__).resolve().parents[2]
VERIFY_PATH = ROOT / "tools/state_contract/verify.py"
SUITE_PATH = ROOT / "fixtures/forgeops-state-contract/state-suite.json"
SCHEMA_PATH = ROOT / "contracts/forgeops-state-contract/1.0/schema.json"

SPEC = importlib.util.spec_from_file_location("state_contract_verify", VERIFY_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load state contract verifier")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def load_suite() -> dict:
    return json.loads(SUITE_PATH.read_text(encoding="utf-8"))


def case(case_id: str) -> dict:
    return next(item for item in load_suite()["cases"] if item["id"] == case_id)


def snapshot(*, revision: int, next_seq: int) -> dict:
    value = copy.deepcopy(case("POSITIVE_ACTIVE_IN_PROGRESS")["snapshot"])
    value.update(revision=revision, next_seq=next_seq)
    return value


def proposal(*, base_revision: int, expected_seq: int) -> dict:
    value = copy.deepcopy(case("POSITIVE_ACTIVE_IN_PROGRESS")["proposal"])
    value.update(base_revision=base_revision, expected_seq=expected_seq)
    return value


class StateContractTests(unittest.TestCase):
    def test_suite_rejects_changed_catalog_entry(self) -> None:
        suite = load_suite()
        suite["cases"][0]["id"] = "POSITIVE_RENAMED"

        with self.assertRaisesRegex(ValueError, "exact case catalog"):
            VERIFY.validate_suite(suite)

    def test_cancelled_mapping_is_rejected(self) -> None:
        result = VERIFY.run_case(case("NEGATIVE_CANCELLED_COERCION"))

        self.assertEqual("STATE_CANCELLED_COERCION_FORBIDDEN", result["actual"])

    def test_main_must_match_current_revision_and_next_sequence(self) -> None:
        with self.assertRaisesRegex(VERIFY.StateError, "STATE_REVISION_STALE"):
            VERIFY.validate_transition(
                snapshot(revision=3, next_seq=9),
                proposal(base_revision=2, expected_seq=9),
            )
        with self.assertRaisesRegex(VERIFY.StateError, "STATE_SEQUENCE_OUT_OF_ORDER"):
            VERIFY.validate_transition(
                snapshot(revision=3, next_seq=9),
                proposal(base_revision=3, expected_seq=8),
            )

    def test_created_pending_is_a_mapping_observation_not_a_transition(self) -> None:
        initial = case("POSITIVE_CREATED_PENDING")

        with self.assertRaisesRegex(VERIFY.StateError, "STATE_TRANSITION_INVALID"):
            VERIFY.validate_transition(initial["snapshot"], initial["proposal"])

        self.assertEqual("PASSED", VERIFY.validate_mapping(initial["proposal"]))

    def test_all_catalog_cases_match_their_stable_verdict(self) -> None:
        for item in load_suite()["cases"]:
            result = VERIFY.run_case(item)

            self.assertEqual("PASSED", result["status"], item["id"])

    def test_runner_contract_failure_replaces_stale_pass_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            temp_verify = temporary_root / "tools/state_contract/verify.py"
            temp_schema = temporary_root / "contracts/forgeops-state-contract/1.0/schema.json"
            temp_suite = temporary_root / "fixtures/forgeops-state-contract/state-suite.json"
            temp_result = (
                temporary_root
                / "artifacts/verification/vg-003-state-transition-result.json"
            )
            for target in (temp_verify, temp_schema, temp_suite, temp_result):
                target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(VERIFY_PATH, temp_verify)
            shutil.copy2(SCHEMA_PATH, temp_schema)
            changed = load_suite()
            changed["cases"][0]["id"] = "POSITIVE_RENAMED"
            temp_suite.write_text(json.dumps(changed), encoding="utf-8")
            temp_result.write_text('{"status":"PASSED","stale":true}\n', encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/state_contract/verify.py",
                    "--schema",
                    "contracts/forgeops-state-contract/1.0/schema.json",
                    "--suite",
                    "fixtures/forgeops-state-contract/state-suite.json",
                    "--result",
                    "artifacts/verification/vg-003-state-transition-result.json",
                    "--command-id",
                    "state-transition-fixture",
                ],
                cwd=temporary_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(2, completed.returncode)
            failed_result = json.loads(temp_result.read_text(encoding="utf-8"))
            self.assertEqual("FAILED", failed_result["status"])
            self.assertEqual("RUNNER_CONTRACT_INVALID", failed_result["runner_error"])
            self.assertNotIn("stale", failed_result)

    def test_runner_rejects_an_unregistered_result_path_without_overwriting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            temp_verify = temporary_root / "tools/state_contract/verify.py"
            temp_schema = temporary_root / "contracts/forgeops-state-contract/1.0/schema.json"
            temp_suite = temporary_root / "fixtures/forgeops-state-contract/state-suite.json"
            protected_target = temporary_root / "docs/control.json"
            for target in (temp_verify, temp_schema, temp_suite, protected_target):
                target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(VERIFY_PATH, temp_verify)
            shutil.copy2(SCHEMA_PATH, temp_schema)
            shutil.copy2(SUITE_PATH, temp_suite)
            protected_target.write_text('{"user_owned":true}\n', encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "tools/state_contract/verify.py",
                    "--schema",
                    "contracts/forgeops-state-contract/1.0/schema.json",
                    "--suite",
                    "fixtures/forgeops-state-contract/state-suite.json",
                    "--result",
                    "docs/control.json",
                    "--command-id",
                    "state-transition-fixture",
                ],
                cwd=temporary_root,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(2, completed.returncode)
            self.assertEqual('{"user_owned":true}\n', protected_target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
