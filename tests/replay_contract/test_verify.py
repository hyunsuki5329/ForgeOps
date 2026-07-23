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
VERIFY_PATH = ROOT / "tools/replay_contract/verify.py"
SUITE_PATH = ROOT / "fixtures/forgeops-replay-contract/suite.json"
SCHEMA_PATH = ROOT / "contracts/forgeops-replay-contract/1.0/schema.json"

SPEC = importlib.util.spec_from_file_location("replay_contract_verify", VERIFY_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load replay contract verifier")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def load_suite() -> dict:
    return json.loads(SUITE_PATH.read_text(encoding="utf-8"))


def case(case_id: str) -> dict:
    return next(item for item in load_suite()["cases"] if item["id"] == case_id)


def request(**changes: object) -> dict:
    value = copy.deepcopy(case("POSITIVE_AUDIT_READ_ONLY")["request"])
    new_task_id = changes.pop("new_task_id", None)
    value.update(changes)
    if new_task_id is not None:
        value["new_identity"]["task_id"] = new_task_id
    return value


class ReplayContractTests(unittest.TestCase):
    def test_audit_replay_cannot_dispatch_external_effect(self) -> None:
        result, dispatcher = VERIFY.evaluate(
            request(mode="AUDIT_REPLAY", requested_external_effect=True)
        )

        self.assertEqual("REPLAY_EXTERNAL_EFFECT_FORBIDDEN", result)
        self.assertEqual(0, dispatcher.calls)

    def test_counterfactual_contract_change_requires_new_task(self) -> None:
        with self.assertRaisesRegex(VERIFY.ReplayError, "REPLAY_IDENTITY_REUSED"):
            VERIFY.validate(
                request(mode="COUNTERFACTUAL", contract_changed=True, new_task_id="TASK-1")
            )

    def test_control_copy_precedes_effect_evaluation(self) -> None:
        with self.assertRaisesRegex(VERIFY.ReplayError, "REPLAY_CONTROL_COPY_FORBIDDEN"):
            VERIFY.validate(
                request(
                    mode="AUDIT_REPLAY",
                    copied_controls=["nonce"],
                    requested_external_effect=True,
                )
            )

    def test_fully_reapproved_reexecute_dispatches_once_in_fixture(self) -> None:
        permitted = case("POSITIVE_REEXECUTE_EXTERNAL_EFFECT")

        result, dispatcher = VERIFY.evaluate(permitted["request"])

        self.assertEqual("PASSED", result)
        self.assertEqual(1, dispatcher.calls)

    def test_all_catalog_cases_match_their_stable_verdict_and_stop_forbidden_effects(self) -> None:
        for item in load_suite()["cases"]:
            result, dispatcher = VERIFY.evaluate(item["request"])
            expected = item.get("expected_result", item.get("expected_error"))

            self.assertEqual(expected, result, item["id"])
            if item["kind"] == "negative":
                self.assertEqual(0, dispatcher.calls, item["id"])

    def test_runner_contract_failure_replaces_stale_pass_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            temp_verify = temporary_root / "tools/replay_contract/verify.py"
            temp_schema = temporary_root / "contracts/forgeops-replay-contract/1.0/schema.json"
            temp_suite = temporary_root / "fixtures/forgeops-replay-contract/suite.json"
            temp_result = temporary_root / VERIFY.EXPECTED_RESULT_REF
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
                    "tools/replay_contract/verify.py",
                    "--schema",
                    "contracts/forgeops-replay-contract/1.0/schema.json",
                    "--suite",
                    "fixtures/forgeops-replay-contract/suite.json",
                    "--result",
                    VERIFY.EXPECTED_RESULT_REF,
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
            temp_verify = temporary_root / "tools/replay_contract/verify.py"
            temp_schema = temporary_root / "contracts/forgeops-replay-contract/1.0/schema.json"
            temp_suite = temporary_root / "fixtures/forgeops-replay-contract/suite.json"
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
                    "tools/replay_contract/verify.py",
                    "--schema",
                    "contracts/forgeops-replay-contract/1.0/schema.json",
                    "--suite",
                    "fixtures/forgeops-replay-contract/suite.json",
                    "--result",
                    "docs/control.json",
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
