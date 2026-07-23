from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERIFY_PATH = ROOT / "tools/policy_contract/verify.py"
SCHEMA_PATH = ROOT / "contracts/forgeops-authority-policy/1.0/schema.json"
SUITE_PATH = ROOT / "fixtures/forgeops-approval-policy/suite.json"

SPEC = importlib.util.spec_from_file_location("policy_contract_verify_approval", VERIFY_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load policy contract verifier")
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


def load_suite() -> dict:
    return json.loads(SUITE_PATH.read_text(encoding="utf-8"))


def approved_request() -> dict:
    value = copy.deepcopy(load_suite()["base_request"])
    value["approval"]["effect_hash"] = VERIFY.canonical_effect_hash(value)
    return value


class ApprovalEffectGateTests(unittest.TestCase):
    def test_approval_cannot_overcome_unknown_authority_or_external_runtime(self) -> None:
        for field, denied in (
            ("exact_authority", "UNKNOWN"),
            ("external_runtime", "UNAVAILABLE"),
        ):
            with self.subTest(field=field):
                request = approved_request()
                request[field] = denied
                result, dispatcher = VERIFY.evaluate_approval(
                    request, VERIFY.MemoryNonceLedger()
                )
                self.assertEqual("AUTHORITY_CAPABILITY_DENIED", result)
                self.assertEqual(0, dispatcher.calls)

    def test_destructive_and_external_authority_are_separate_hard_gates(self) -> None:
        for field, denied in (
            ("destructive_actions", "DENIED"),
            ("external_side_effects", "DENIED"),
        ):
            with self.subTest(field=field):
                request = approved_request()
                request[field] = denied
                result, dispatcher = VERIFY.evaluate_approval(
                    request, VERIFY.MemoryNonceLedger()
                )
                self.assertEqual("EFFECT_GATE_DENIED", result)
                self.assertEqual(0, dispatcher.calls)

    def test_revision_change_invalidates_approval_and_nonce_is_one_time(self) -> None:
        request = approved_request()
        request["base_revision"] += 1
        with self.assertRaisesRegex(VERIFY.PolicyError, "APPROVAL_BINDING_MISMATCH"):
            VERIFY.validate_approval(request, VERIFY.MemoryNonceLedger())

        ledger = VERIFY.MemoryNonceLedger()
        self.assertEqual("PASSED", VERIFY.validate_approval(approved_request(), ledger))
        with self.assertRaisesRegex(VERIFY.PolicyError, "APPROVAL_NONCE_REUSED"):
            VERIFY.validate_approval(approved_request(), ledger)

    def test_every_bound_effect_input_mutation_is_rejected(self) -> None:
        suite = load_suite()
        binding_cases = [
            item for item in suite["cases"] if item["id"].startswith("NEGATIVE_BIND_")
        ]
        self.assertGreaterEqual(len(binding_cases), 10)
        for item in binding_cases:
            with self.subTest(case_id=item["id"]):
                request = VERIFY.materialize_approval_case(suite, item)
                result, dispatcher = VERIFY.evaluate_approval(
                    request, VERIFY.MemoryNonceLedger()
                )
                self.assertEqual("APPROVAL_BINDING_MISMATCH", result)
                self.assertEqual(0, dispatcher.calls)

    def test_atomic_nonce_consumption_allows_exactly_one_validator(self) -> None:
        ledger = VERIFY.MemoryNonceLedger()
        request = approved_request()

        def validate() -> str:
            try:
                return VERIFY.validate_approval(request, ledger)
            except VERIFY.PolicyError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=16) as executor:
            results = list(executor.map(lambda _: validate(), range(32)))
        self.assertEqual(1, results.count("PASSED"))
        self.assertEqual(31, results.count("APPROVAL_NONCE_REUSED"))

    def test_every_negative_fixture_stops_before_spy_dispatch(self) -> None:
        suite = load_suite()
        for item in suite["cases"]:
            if item["kind"] != "negative":
                continue
            with self.subTest(case_id=item["id"]):
                result = VERIFY.run_approval_case(suite, item)
                self.assertEqual("PASSED", result["status"])
                self.assertEqual(0, result["dispatcher"]["dispatcher_calls"])
                self.assertEqual(0, result["dispatcher"]["external_effect_calls"])

    def test_permitted_positive_reaches_only_in_memory_spy(self) -> None:
        request = approved_request()
        result, dispatcher = VERIFY.evaluate_approval(request, VERIFY.MemoryNonceLedger())
        self.assertEqual("PASSED", result)
        self.assertEqual(1, dispatcher.calls)
        self.assertEqual(0, dispatcher.external_effect_calls)
        self.assertEqual(0, dispatcher.process_calls)
        self.assertEqual(0, dispatcher.network_calls)
        self.assertEqual(0, dispatcher.store_calls)

    def test_suite_is_closed_and_public_result_redacts_approval_material(self) -> None:
        suite = load_suite()
        VERIFY.validate_approval_suite(suite)
        cases = [VERIFY.run_approval_case(suite, item) for item in suite["cases"]]
        result = VERIFY.approval_public_result(SCHEMA_PATH, SUITE_PATH, cases)
        serialized = json.dumps(result, sort_keys=True)
        for forbidden in (
            suite["base_request"]["approval"]["nonce"],
            suite["base_request"]["approval"]["signature_ref"],
            suite["base_request"]["payload"]["content_hash"],
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual("PASSED", result["status"])

    def test_public_result_derives_approval_material_assertion(self) -> None:
        suite = load_suite()
        cases = [VERIFY.run_approval_case(suite, item) for item in suite["cases"]]
        cases[0]["signature_ref"] = suite["base_request"]["approval"]["signature_ref"]

        result = VERIFY.approval_public_result(SCHEMA_PATH, SUITE_PATH, cases)

        self.assertFalse(result["assertions"]["no_approval_material_fields"])
        self.assertEqual("FAILED", result["status"])


if __name__ == "__main__":
    unittest.main()
