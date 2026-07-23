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
VERIFY_PATH = ROOT / "tools/policy_contract/verify.py"
SCHEMA_PATH = ROOT / "contracts/forgeops-authority-policy/1.0/schema.json"
SUITE_PATH = ROOT / "fixtures/forgeops-authority-resource/suite.json"

SPEC = importlib.util.spec_from_file_location("policy_contract_verify", VERIFY_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load policy contract verifier")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def load_suite() -> dict:
    return json.loads(SUITE_PATH.read_text(encoding="utf-8"))


def case(case_id: str) -> dict:
    return next(item for item in load_suite()["cases"] if item["id"] == case_id)


def request(case_id: str) -> dict:
    return copy.deepcopy(case(case_id)["request"])


def named_request(resource_ref: str) -> dict:
    value = request("POSITIVE_NAMED_UPDATE")
    value["identity"]["resource_ref"] = resource_ref
    return value


class ResourceAuthorityTests(unittest.TestCase):
    def test_explore_public_read_does_not_require_candidate_or_current_revision(self) -> None:
        value = request("POSITIVE_PROJECT_READ")
        value["operation_mode"] = "EXPLORE"
        value["approved_candidate"] = False
        value["current_revision"] = False

        result, probes = VERIFY.evaluate_resource(value)

        self.assertEqual("PASSED", result)
        self.assertEqual(1, probes.reader_calls)

    def test_mutation_still_requires_execute_approval_and_current_revision(self) -> None:
        mutations = {
            "explore": {"operation_mode": "EXPLORE"},
            "unapproved": {"approved_candidate": False},
            "stale": {"current_revision": False},
        }
        for label, changes in mutations.items():
            with self.subTest(label=label):
                value = request("POSITIVE_NAMED_UPDATE")
                value.update(changes)
                with self.assertRaisesRegex(VERIFY.PolicyError, "RESOURCE_CAPABILITY_DENIED"):
                    VERIFY.validate_resource(value)

    def test_protected_read_never_invokes_reader_or_sinks(self) -> None:
        result, probes = VERIFY.evaluate_resource(request("NEGATIVE_PROTECTED_READ_UNAPPROVED"))

        self.assertEqual("PROTECTED_TARGET_APPROVAL_REQUIRED", result)
        self.assertEqual(
            {
                "reader_calls": 0,
                "model_context_writes": 0,
                "log_writes": 0,
                "evidence_writes": 0,
                "sentinel_occurrences": 0,
            },
            probes.public_counts(),
        )

    def test_protected_read_approval_is_closed_and_exactly_bound(self) -> None:
        approved = request("NEGATIVE_PROTECTED_READ_UNAPPROVED")
        approved["protected_target_approval"] = {
            "resource_ref": approved["identity"]["resource_ref"],
            "classification": approved["identity"]["classification"],
        }
        self.assertEqual("PASSED", VERIFY.validate_resource(approved))

        for field, other_value in (
            ("resource_ref", "protected/other.bin"),
            ("classification", "CREDENTIAL"),
        ):
            with self.subTest(field=field):
                mismatched = copy.deepcopy(approved)
                mismatched["protected_target_approval"][field] = other_value
                with self.assertRaisesRegex(
                    VERIFY.PolicyError, "PROTECTED_TARGET_APPROVAL_REQUIRED"
                ):
                    VERIFY.validate_resource(mismatched)

        extra = copy.deepcopy(approved)
        extra["protected_target_approval"]["unexpected"] = True
        with self.assertRaisesRegex(VERIFY.PolicyError, "RESOURCE_SCHEMA_INVALID"):
            VERIFY.validate_resource(extra)

    def test_named_scope_does_not_accept_prefix_or_case_variation(self) -> None:
        for resource_ref in ("src/app.py.bak", "SRC/app.py"):
            with self.subTest(resource_ref=resource_ref):
                with self.assertRaisesRegex(VERIFY.PolicyError, "RESOURCE_EXACT_MATCH_REQUIRED"):
                    VERIFY.validate_resource(named_request(resource_ref))

    def test_project_scope_requires_root_containment(self) -> None:
        with self.assertRaisesRegex(VERIFY.PolicyError, "RESOURCE_CONTAINMENT_FAILED"):
            VERIFY.validate_resource(request("NEGATIVE_PROJECT_ROOT_ESCAPE"))

    def test_denied_fixture_cases_leave_protected_sentinel_unobserved(self) -> None:
        for item in load_suite()["cases"]:
            if item["kind"] != "negative":
                continue
            with self.subTest(case_id=item["id"]):
                result, probes = VERIFY.evaluate_resource(copy.deepcopy(item["request"]))
                self.assertEqual(item["expected_error"], result)
                self.assertEqual(
                    {
                        "reader_calls": 0,
                        "model_context_writes": 0,
                        "log_writes": 0,
                        "evidence_writes": 0,
                        "sentinel_occurrences": 0,
                    },
                    probes.public_counts(),
                )

    def test_resource_case_schema_closes_the_nested_request(self) -> None:
        changed = case("POSITIVE_PROJECT_READ")
        changed["request"]["unexpected"] = True
        validator = VERIFY.default_validator()
        case_validator = validator.evolve(schema=validator.schema["$defs"]["resource_case"])

        self.assertIsNotNone(next(case_validator.iter_errors(changed), None))

    def test_all_catalog_cases_match_stable_verdicts(self) -> None:
        for item in load_suite()["cases"]:
            result = VERIFY.run_case(copy.deepcopy(item))
            self.assertEqual("PASSED", result["status"], item["id"])

    def test_suite_rejects_changed_catalog_entry(self) -> None:
        suite = load_suite()
        suite["cases"][0]["id"] = "POSITIVE_RENAMED"

        with self.assertRaisesRegex(ValueError, "exact case catalog"):
            VERIFY.validate_suite(suite)

    def test_runner_contract_failure_replaces_stale_pass_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            temp_verify = temporary_root / "tools/policy_contract/verify.py"
            temp_schema = temporary_root / "contracts/forgeops-authority-policy/1.0/schema.json"
            temp_suite = temporary_root / "fixtures/forgeops-authority-resource/suite.json"
            temp_result = temporary_root / "artifacts/verification/vg-005-resource-authority-result.json"
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
                    "tools/policy_contract/verify.py",
                    "resource",
                    "--schema",
                    "contracts/forgeops-authority-policy/1.0/schema.json",
                    "--suite",
                    "fixtures/forgeops-authority-resource/suite.json",
                    "--result",
                    "artifacts/verification/vg-005-resource-authority-result.json",
                    "--command-id",
                    "resource-authority-negative",
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

    def test_runner_never_writes_an_unregistered_or_outside_result_path(self) -> None:
        attempts = (
            "artifacts/verification/vg-005-protected-read-result.json",
            "../outside-{temporary_name}.json",
            "protected/result.json",
        )
        for result_template in attempts:
            with self.subTest(result_ref=result_template), tempfile.TemporaryDirectory() as temporary:
                temporary_root = Path(temporary)
                result_ref = result_template.format(temporary_name=temporary_root.name)
                temp_verify = temporary_root / "tools/policy_contract/verify.py"
                temp_schema = temporary_root / "contracts/forgeops-authority-policy/1.0/schema.json"
                temp_suite = temporary_root / "fixtures/forgeops-authority-resource/suite.json"
                expected_result = (
                    temporary_root
                    / "artifacts/verification/vg-005-resource-authority-result.json"
                )
                for target in (temp_verify, temp_schema, temp_suite):
                    target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(VERIFY_PATH, temp_verify)
                shutil.copy2(SCHEMA_PATH, temp_schema)
                shutil.copy2(SUITE_PATH, temp_suite)

                completed = subprocess.run(
                    [
                        sys.executable,
                        "tools/policy_contract/verify.py",
                        "resource",
                        "--schema",
                        "contracts/forgeops-authority-policy/1.0/schema.json",
                        "--suite",
                        "fixtures/forgeops-authority-resource/suite.json",
                        "--result",
                        result_ref,
                        "--command-id",
                        "resource-authority-negative",
                    ],
                    cwd=temporary_root,
                    capture_output=True,
                    text=True,
                    check=False,
                )

                self.assertEqual(2, completed.returncode)
                self.assertTrue(expected_result.is_file())
                self.assertEqual("FAILED", json.loads(expected_result.read_text())["status"])
                attempted_path = (temporary_root / result_ref).resolve()
                if attempted_path != expected_result.resolve():
                    self.assertFalse(attempted_path.exists())

    def test_protected_success_requires_every_probe_to_be_zero(self) -> None:
        counts = {
            "reader_calls": 0,
            "model_context_writes": 0,
            "log_writes": 1,
            "evidence_writes": 0,
            "sentinel_occurrences": 0,
        }
        protected_case = {
            "id": "NEGATIVE_PROTECTED_READ_UNAPPROVED",
            "kind": "negative",
            "status": "PASSED",
            "expected": "PROTECTED_TARGET_APPROVAL_REQUIRED",
            "actual": "PROTECTED_TARGET_APPROVAL_REQUIRED",
            "probes": counts,
        }

        result = VERIFY.public_result(
            "protected-read-negative", SCHEMA_PATH, SUITE_PATH, [protected_case]
        )

        self.assertEqual("FAILED", result["status"])

    def test_no_raw_sentinel_assertion_is_derived_from_public_output(self) -> None:
        protected_case = {
            "id": "NEGATIVE_PROTECTED_READ_UNAPPROVED",
            "kind": "negative",
            "status": "PASSED",
            "expected": "PROTECTED_TARGET_APPROVAL_REQUIRED",
            "actual": "PROTECTED_TARGET_APPROVAL_REQUIRED",
            "probes": {
                "reader_calls": 0,
                "model_context_writes": 0,
                "log_writes": 0,
                "evidence_writes": 0,
                "sentinel_occurrences": 0,
            },
            "leaked_value": VERIFY._SENTINEL.decode("ascii"),
        }

        result = VERIFY.public_result(
            "protected-read-negative", SCHEMA_PATH, SUITE_PATH, [protected_case]
        )

        self.assertEqual("FAILED", result["status"])
        self.assertTrue(result["sentinel_raw_value_recorded"])


if __name__ == "__main__":
    unittest.main()
