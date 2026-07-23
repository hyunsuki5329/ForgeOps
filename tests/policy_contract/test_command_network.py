from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFY_PATH = ROOT / "tools/policy_contract/verify.py"
SUITE_PATH = ROOT / "fixtures/forgeops-authority-command-network/suite.json"

SPEC = importlib.util.spec_from_file_location("policy_contract_verify_command_network", VERIFY_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load policy contract verifier")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def load_suite() -> dict:
    return json.loads(SUITE_PATH.read_text(encoding="utf-8"))


def trusted_catalog() -> dict:
    return copy.deepcopy(load_suite()["catalog"])


def case(case_id: str) -> dict:
    return next(item for item in load_suite()["cases"] if item["id"] == case_id)


def request(case_id: str) -> dict:
    return copy.deepcopy(case(case_id)["request"])


class CommandNetworkAuthorityTests(unittest.TestCase):
    def test_raw_command_and_private_network_are_denied_before_adapter(self) -> None:
        for case_id, code in (
            ("NEGATIVE_COMMAND_RAW", "COMMAND_RAW_FORBIDDEN"),
            ("NEGATIVE_NETWORK_PRIVATE", "NETWORK_DESTINATION_FORBIDDEN"),
        ):
            with self.subTest(case_id=case_id):
                result, adapter = VERIFY.evaluate_command_network(request(case_id))
                self.assertEqual(code, result)
                self.assertEqual(0, adapter.calls)

    def test_command_requires_all_three_exact_values(self) -> None:
        for case_id in (
            "NEGATIVE_COMMAND_ID_MISMATCH",
            "NEGATIVE_COMMAND_TEXT_MISMATCH",
            "NEGATIVE_COMMAND_CWD_MISMATCH",
        ):
            with self.subTest(case_id=case_id):
                with self.assertRaisesRegex(VERIFY.PolicyError, "COMMAND_IDENTITY_MISMATCH"):
                    VERIFY.validate_command(request(case_id), trusted_catalog())

    def test_command_rejects_noncanonical_cwd_even_when_trusted_record_matches(self) -> None:
        for invalid_cwd in (
            "C:/tests",
            "../tests",
            "tests\\unit",
            "tests/*",
            "./tests",
            "tests/./unit",
        ):
            with self.subTest(cwd=invalid_cwd):
                value = request("POSITIVE_COMMAND_EXACT_TRIPLE")
                value["identity"]["cwd"] = invalid_cwd
                catalog = trusted_catalog()
                catalog["commands"]["policy-tests"]["cwd"] = invalid_cwd
                with self.assertRaisesRegex(VERIFY.PolicyError, "COMMAND_IDENTITY_MISMATCH"):
                    VERIFY.validate_command(value, catalog)

    def test_network_rejects_url_not_host_literal(self) -> None:
        with self.assertRaisesRegex(VERIFY.PolicyError, "NETWORK_IDENTITY_INVALID"):
            VERIFY.validate_network(request("NEGATIVE_NETWORK_SCHEME"), trusted_catalog())

    def test_every_negative_fixture_stops_before_adapter(self) -> None:
        for item in load_suite()["cases"]:
            if item["kind"] != "negative":
                continue
            with self.subTest(case_id=item["id"]):
                result, adapter = VERIFY.evaluate_command_network(copy.deepcopy(item["request"]))
                self.assertEqual(item["expected_error"], result)
                self.assertEqual(0, adapter.calls)

    def test_positive_fixtures_only_reach_in_memory_spy(self) -> None:
        for item in load_suite()["cases"]:
            if item["kind"] != "positive":
                continue
            with self.subTest(case_id=item["id"]):
                result, adapter = VERIFY.evaluate_command_network(copy.deepcopy(item["request"]))
                self.assertEqual("PASSED", result)
                self.assertEqual(1, adapter.calls)
                self.assertEqual(0, adapter.process_calls)
                self.assertEqual(0, adapter.dns_calls)
                self.assertEqual(0, adapter.socket_calls)

    def test_missing_or_invalid_execution_preconditions_stop_before_adapter(self) -> None:
        baseline = request("POSITIVE_COMMAND_EXACT_TRIPLE")
        for field in (
            "operation_mode",
            "capability",
            "approved_candidate",
            "current_revision",
            "all_preflights_passed",
        ):
            baseline.pop(field)
        result, adapter = VERIFY.evaluate_command_network(baseline)
        self.assertEqual("COMMAND_NETWORK_SCHEMA_INVALID", result)
        self.assertEqual(0, adapter.calls)

        for field, value in (
            ("operation_mode", "EXPLORE"),
            ("capability", "UNKNOWN"),
            ("approved_candidate", False),
            ("current_revision", False),
            ("all_preflights_passed", False),
        ):
            with self.subTest(field=field):
                denied = request("POSITIVE_NETWORK_HOST")
                denied.update(
                    operation_mode="EXECUTE",
                    capability="AVAILABLE",
                    approved_candidate=True,
                    current_revision=True,
                    all_preflights_passed=True,
                )
                denied[field] = value
                result, adapter = VERIFY.evaluate_command_network(denied)
                self.assertEqual("AUTHORITY_CAPABILITY_DENIED", result)
                self.assertEqual(0, adapter.calls)

    def test_schema_requires_and_fixture_exercises_all_execution_preconditions(self) -> None:
        required = VERIFY.default_validator().schema["$defs"]["command_network_request"][
            "required"
        ]
        self.assertTrue(
            {
                "operation_mode",
                "capability",
                "approved_candidate",
                "current_revision",
                "all_preflights_passed",
            }.issubset(required)
        )

        expected_cases = {
            "NEGATIVE_COMMAND_CAPABILITY_UNKNOWN": ("capability", "UNKNOWN"),
            "NEGATIVE_NETWORK_CANDIDATE_UNAPPROVED": ("approved_candidate", False),
            "NEGATIVE_COMMAND_EXPLORE_MODE": ("operation_mode", "EXPLORE"),
            "NEGATIVE_NETWORK_STALE_REVISION": ("current_revision", False),
            "NEGATIVE_COMMAND_PREFLIGHT_FAILED": ("all_preflights_passed", False),
        }
        for case_id, (field, expected_value) in expected_cases.items():
            with self.subTest(case_id=case_id):
                item = case(case_id)
                self.assertEqual(expected_value, item["request"][field])
                result, adapter = VERIFY.evaluate_command_network(request(case_id))
                self.assertEqual("AUTHORITY_CAPABILITY_DENIED", result)
                self.assertEqual(0, adapter.calls)

    def test_suite_is_closed_and_schema_valid(self) -> None:
        suite = load_suite()
        VERIFY.validate_command_network_suite(suite)
        self.assertEqual(
            {"suite_id", "suite_version", "schema_ref", "catalog", "cases"},
            set(suite),
        )

    def test_public_result_requires_one_spy_dispatch_for_each_positive_case(self) -> None:
        suite = load_suite()
        cases = [VERIFY.run_command_network_case(item) for item in suite["cases"]]
        result = VERIFY.command_network_public_result(
            ROOT / "contracts/forgeops-authority-policy/1.0/schema.json",
            SUITE_PATH,
            cases,
        )
        self.assertTrue(result["assertions"]["positive_single_adapter_call"])
        self.assertEqual("PASSED", result["status"])


if __name__ == "__main__":
    unittest.main()
