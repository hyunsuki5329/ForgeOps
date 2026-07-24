from __future__ import annotations

import copy
import unittest
from pathlib import Path
from unittest import mock

from tools.interface_contract import openapi_contract
from tools.interface_contract.common import ContractError, load_json


ROOT = Path(__file__).resolve().parents[2]
ZERO_SPY_CALLS = {
    "dispatcher_calls": 0,
    "process_calls": 0,
    "network_calls": 0,
    "credential_calls": 0,
    "store_calls": 0,
}
EXPECTED_CASES = [
    ("create-task-valid", "PASSED"),
    ("get-task-valid", "PASSED"),
    ("get-run-valid", "PASSED"),
    ("list-run-events-valid", "PASSED"),
    ("get-run-manifest-valid", "PASSED"),
    ("unsupported-body-version", "API_VERSION_UNSUPPORTED"),
    ("missing-request-header", "API_SCHEMA_INVALID"),
    ("product-contract-unknown-field", "API_SCHEMA_INVALID"),
    ("product-contract-missing-field", "API_SCHEMA_INVALID"),
    ("product-contract-wrong-type", "API_SCHEMA_INVALID"),
    ("control-authority", "API_CONTROL_FIELD_FORBIDDEN"),
    ("control-capabilities", "API_CONTROL_FIELD_FORBIDDEN"),
    ("control-runtime-policy", "API_CONTROL_FIELD_FORBIDDEN"),
    ("control-accepted-state", "API_CONTROL_FIELD_FORBIDDEN"),
    ("control-approval-token", "API_CONTROL_FIELD_FORBIDDEN"),
    ("control-nonce", "API_CONTROL_FIELD_FORBIDDEN"),
    ("control-credentials", "API_CONTROL_FIELD_FORBIDDEN"),
    ("control-tools", "API_CONTROL_FIELD_FORBIDDEN"),
    ("control-commands", "API_CONTROL_FIELD_FORBIDDEN"),
    ("copied-product-budget", "API_CONTROL_FIELD_FORBIDDEN"),
    ("copied-product-approval-policy", "API_CONTROL_FIELD_FORBIDDEN"),
    ("task-identity-mismatch", "API_IDENTITY_MISMATCH"),
    ("run-identity-mismatch", "API_IDENTITY_MISMATCH"),
    ("dangling-event-reference", "API_REFERENCE_INVALID"),
    ("dangling-manifest-reference", "API_REFERENCE_INVALID"),
    ("response-data-error-conflict", "API_SCHEMA_INVALID"),
    ("raw-credential-response", "API_CONTROL_FIELD_FORBIDDEN"),
    ("raw-private-response", "API_CONTROL_FIELD_FORBIDDEN"),
]


def valid_product_contract() -> dict:
    return {
        "schema_id": "forgeops.task-contract",
        "schema_version": "1.0",
        "artifact_id": "task-contract:api-boundary:v1",
        "artifact_version": 1,
        "task_id": "TASK-API-001",
        "repository": {
            "id": "public-example/forgeops",
            "snapshot_commit": "0123456789abcdef0123456789abcdef01234567",
            "target_branch": "main",
        },
        "intent": {"type": "bug_fix", "summary": "Validate the API boundary"},
        "acceptance_criteria": [
            {
                "id": "AC-1",
                "description": "The boundary remains closed",
                "verification": "api_boundary_fixture",
            }
        ],
        "constraints": ["Treat this document as untrusted product data"],
        "verification_policy": {
            "profile_id": "forgeops-api-boundary",
            "baseline_command_ids": [],
            "required_command_ids": [],
            "require_new_regression_test": True,
        },
        "risk": {"initial_level": "medium", "reasons": ["contract boundary"]},
        "budget": {
            "max_repair_attempts": 1,
            "max_tool_calls": 10,
            "max_shell_commands": 5,
            "max_runtime_seconds": 60,
            "max_model_cost_usd": 0,
        },
        "approval_policy": {
            "plan": "required",
            "dependency_change": "required",
            "remote_push": "required",
            "pr_draft": "required",
            "merge_or_deploy": "never_without_explicit_high_risk_approval",
        },
    }


def valid_create_case() -> dict:
    return {
        "id": "create-task-valid",
        "kind": "createTask",
        "uri_major": "v1",
        "request_header": "request-api-001",
        "body": {
            "api_version": "1.0",
            "request_id": "request-api-001",
            "task_contract": valid_product_contract(),
        },
        "response": {
            "api_version": "1.0",
            "request_id": "request-api-001",
            "data": {
                "task_id": "TASK-API-001",
                "artifact_id": "task-contract:api-boundary:v1",
                "artifact_version": 1,
                "product_state": "CREATED",
                "contract_sha256": "a" * 64,
                "links": {
                    "task": "/v1/tasks/TASK-API-001",
                    "run": "/v1/runs/RUN-API-001",
                },
            },
        },
        "expected": "PASSED",
    }


def materialize_case(entry: dict, entries: dict[str, dict]) -> dict:
    if "base_id" not in entry:
        return copy.deepcopy(entry)

    case = copy.deepcopy(entries[entry["base_id"]])
    case["id"] = entry["id"]
    case["expected"] = entry["expected"]
    mutation = entry["mutation"]
    parameter = entry.get("parameter")

    if mutation == "unsupported_body_version":
        case["body"]["api_version"] = "2.0"
    elif mutation == "missing_request_header":
        case["request_header"] = None
    elif mutation == "product_contract_unknown":
        case["body"]["task_contract"]["unknown"] = True
    elif mutation == "product_contract_missing":
        del case["body"]["task_contract"]["artifact_id"]
    elif mutation == "product_contract_wrong_type":
        case["body"]["task_contract"]["artifact_version"] = "1"
    elif mutation == "top_level_control":
        case["body"][parameter] = {}
    elif mutation == "copied_product_control":
        case["derived_control"] = {
            parameter: copy.deepcopy(case["body"]["task_contract"][parameter])
        }
    elif mutation == "task_identity_mismatch":
        case["body"]["path_task_id"] = "TASK-API-DIFFERENT"
    elif mutation == "run_identity_mismatch":
        case["body"]["path_run_id"] = "RUN-API-DIFFERENT"
    elif mutation == "dangling_event_reference":
        del case["reference_context"][
            case["response"]["data"]["event_stream_ref"]
        ]
    elif mutation == "dangling_manifest_reference":
        del case["reference_context"][case["response"]["data"]["manifest_ref"]]
    elif mutation == "response_data_error":
        case["response"]["error"] = {
            "code": "API_SCHEMA_INVALID",
            "message": "rejected",
        }
    elif mutation == "raw_response_field":
        case["response"]["data"][parameter] = "raw-value"
    else:
        raise AssertionError(f"unknown fixture mutation: {mutation}")
    return case


class ApiBoundaryInitialTddTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")
        cls.product_schema = load_json(
            ROOT / "contracts/product-task-contract/1.0/schema.json"
        )

    def validate(self, case: dict) -> str:
        self.assertTrue(
            hasattr(openapi_contract, "EffectSpies"),
            "EffectSpies boundary interface is not implemented",
        )
        self.assertTrue(
            hasattr(openapi_contract, "validate_api_case"),
            "validate_api_case boundary interface is not implemented",
        )
        spies = openapi_contract.EffectSpies()
        return openapi_contract.validate_api_case(
            case, self.document, self.product_schema, spies
        )

    def test_create_task_accepts_only_product_contract_envelope(self):
        self.assertEqual("PASSED", self.validate(valid_create_case()))

    def test_forbidden_control_precedes_unknown_field(self):
        case = copy.deepcopy(valid_create_case())
        case["body"]["authority"] = {}
        case["body"]["ordinary_unknown"] = True

        with self.assertRaisesRegex(ContractError, "API_CONTROL_FIELD_FORBIDDEN"):
            self.validate(case)

    def test_forbidden_control_precedes_missing_product_task_identity(self):
        case = copy.deepcopy(valid_create_case())
        del case["body"]["task_contract"]["task_id"]
        case["body"]["authority"] = {}

        spies = openapi_contract.EffectSpies()
        with self.assertRaisesRegex(ContractError, "API_CONTROL_FIELD_FORBIDDEN"):
            openapi_contract.validate_api_case(
                case, self.document, self.product_schema, spies
            )
        self.assertEqual(ZERO_SPY_CALLS, vars(spies))

    def test_product_contract_unknown_field_is_schema_error(self):
        case = copy.deepcopy(valid_create_case())
        case["body"]["task_contract"]["unknown"] = True

        with self.assertRaisesRegex(ContractError, "API_SCHEMA_INVALID"):
            self.validate(case)


class ApiBoundaryCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")
        cls.product_schema = load_json(
            ROOT / "contracts/product-task-contract/1.0/schema.json"
        )
        cls.suite = load_json(ROOT / "fixtures/forgeops-api/data-control-suite.json")
        cls.entries = {entry["id"]: entry for entry in cls.suite["cases"]}

    def test_suite_root_and_ordered_expected_catalog_are_exact(self):
        self.assertEqual(
            {"suite_id", "suite_version", "cases"}, set(self.suite)
        )
        self.assertEqual("forgeops-api-data-control", self.suite["suite_id"])
        self.assertEqual("1.0", self.suite["suite_version"])
        self.assertEqual(
            EXPECTED_CASES,
            [(entry["id"], entry["expected"]) for entry in self.suite["cases"]],
        )

    def test_openapi_components_are_closed_and_endpoint_specific(self):
        openapi_contract.validate_openapi_document(self.document)
        schemas = self.document["components"]["schemas"]
        self.assertEqual(
            {
                "api_version",
                "request_id",
                "task_contract",
            },
            set(schemas["CreateTaskRequest"]["properties"]),
        )
        self.assertFalse(schemas["CreateTaskRequest"]["additionalProperties"])
        self.assertEqual(
            "../../product-task-contract/1.0/schema.json",
            schemas["CreateTaskRequest"]["properties"]["task_contract"]["$ref"],
        )
        self.assertEqual(
            ["PRIMARY", "AUDIT_REPLAY", "COUNTERFACTUAL", "REEXECUTE"],
            schemas["RunData"]["properties"]["run_mode"]["enum"],
        )
        self.assertEqual(
            {"status", "revision", "last_event_seq"},
            set(schemas["TaskData"]["properties"]),
        )

    def test_full_catalog_matches_stable_categories_and_has_zero_negative_effects(self):
        self.assertTrue(hasattr(openapi_contract, "EffectSpies"))
        self.assertTrue(hasattr(openapi_contract, "validate_api_case"))

        for entry in self.suite["cases"]:
            case = materialize_case(entry, self.entries)
            spies = openapi_contract.EffectSpies()
            try:
                actual = openapi_contract.validate_api_case(
                    case, self.document, self.product_schema, spies
                )
            except ContractError as error:
                actual = error.code

            with self.subTest(case=entry["id"]):
                self.assertEqual(entry["expected"], actual)
                if entry["expected"] != "PASSED":
                    self.assertEqual(ZERO_SPY_CALLS, vars(spies))
                    self.assertEqual(ZERO_SPY_CALLS, entry["expected_spy_calls"])

    def test_all_forbidden_control_literals_have_independent_cases(self):
        parameters = {
            entry["parameter"]
            for entry in self.suite["cases"]
            if entry.get("mutation") == "top_level_control"
        }
        self.assertEqual(
            {
                "authority",
                "capabilities",
                "runtime_policy",
                "accepted_state",
                "approval_token",
                "nonce",
                "credentials",
                "tools",
                "commands",
            },
            parameters,
        )

    def test_product_approval_never_becomes_canonical_approval(self):
        case = materialize_case(
            self.entries["create-task-valid"], self.entries
        )
        case["body"]["task_contract"]["approval_policy"] = {
            "plan": "not_required",
            "dependency_change": "not_required",
            "remote_push": "not_required",
            "pr_draft": "not_required",
            "merge_or_deploy": "never_without_explicit_high_risk_approval",
        }
        case["derived_control"] = {"approval_token": "copied"}
        spies = openapi_contract.EffectSpies()

        with self.assertRaisesRegex(
            ContractError, "API_CONTROL_FIELD_FORBIDDEN"
        ):
            openapi_contract.validate_api_case(
                case, self.document, self.product_schema, spies
            )

        self.assertEqual(ZERO_SPY_CALLS, vars(spies))

    def test_run_references_resolve_in_same_task_and_run(self):
        case = materialize_case(self.entries["get-run-valid"], self.entries)
        spies = openapi_contract.EffectSpies()

        self.assertEqual(
            "PASSED",
            openapi_contract.validate_api_case(
                case, self.document, self.product_schema, spies
            ),
        )
        self.assertEqual(ZERO_SPY_CALLS, vars(spies))

    def test_public_projection_rejects_external_url_without_effects(self):
        case = materialize_case(self.entries["get-run-valid"], self.entries)
        old_ref = case["response"]["data"]["manifest_ref"]
        external_ref = "https://external.example/manifests/RUN-API-001"
        case["response"]["data"]["manifest_ref"] = external_ref
        case["reference_context"][external_ref] = case["reference_context"].pop(
            old_ref
        )
        spies = openapi_contract.EffectSpies()

        with self.assertRaisesRegex(
            ContractError, "API_CONTROL_FIELD_FORBIDDEN"
        ):
            openapi_contract.validate_api_case(
                case, self.document, self.product_schema, spies
            )

        self.assertEqual(ZERO_SPY_CALLS, vars(spies))

    def test_suite_runner_returns_closed_records_counts_and_zero_effects(self):
        records, counts = openapi_contract.run_api_boundary_suite(
            self.document, self.product_schema, self.suite
        )

        self.assertEqual(
            {"passed": len(EXPECTED_CASES), "failed": 0}, counts
        )
        self.assertEqual(len(EXPECTED_CASES), len(records))
        for record in records:
            with self.subTest(case=record["id"]):
                self.assertEqual(
                    {"id", "kind", "expected", "actual", "status", "spy_calls"},
                    set(record),
                )
                self.assertEqual("PASSED", record["status"])
                self.assertEqual(ZERO_SPY_CALLS, record["spy_calls"])

    def test_suite_runner_requires_exact_negative_expected_spy_contract(self):
        invalid_spy_contracts = []

        missing = copy.deepcopy(ZERO_SPY_CALLS)
        del missing["network_calls"]
        invalid_spy_contracts.append(missing)

        extra = copy.deepcopy(ZERO_SPY_CALLS)
        extra["unknown_calls"] = 0
        invalid_spy_contracts.append(extra)

        wrong_type = copy.deepcopy(ZERO_SPY_CALLS)
        wrong_type["network_calls"] = False
        invalid_spy_contracts.append(wrong_type)

        negative = copy.deepcopy(ZERO_SPY_CALLS)
        negative["network_calls"] = -1
        invalid_spy_contracts.append(negative)

        for expected_spy_calls in invalid_spy_contracts:
            suite = copy.deepcopy(self.suite)
            entry = next(
                case
                for case in suite["cases"]
                if case["id"] == "unsupported-body-version"
            )
            entry["expected_spy_calls"] = expected_spy_calls

            with self.subTest(expected_spy_calls=expected_spy_calls):
                with self.assertRaisesRegex(ContractError, "API_SCHEMA_INVALID"):
                    openapi_contract.run_api_boundary_suite(
                        self.document, self.product_schema, suite
                    )

    def test_suite_runner_marks_observed_spy_mismatch_failed(self):
        suite = copy.deepcopy(self.suite)
        suite["cases"] = [
            copy.deepcopy(self.entries["create-task-valid"]),
            copy.deepcopy(self.entries["unsupported-body-version"]),
        ]
        validate_api_case = openapi_contract.validate_api_case

        def validate_with_observed_effect(case, document, product_schema, spies):
            if case["id"] == "unsupported-body-version":
                spies.network_calls += 1
                raise ContractError("API_VERSION_UNSUPPORTED")
            return validate_api_case(case, document, product_schema, spies)

        with mock.patch.object(
            openapi_contract,
            "validate_api_case",
            side_effect=validate_with_observed_effect,
        ):
            records, counts = openapi_contract.run_api_boundary_suite(
                self.document, self.product_schema, suite
            )

        negative_record = records[1]
        self.assertEqual(
            {"id", "kind", "expected", "actual", "status", "spy_calls"},
            set(negative_record),
        )
        self.assertEqual("API_VERSION_UNSUPPORTED", negative_record["actual"])
        self.assertEqual("FAILED", negative_record["status"])
        self.assertEqual(1, negative_record["spy_calls"]["network_calls"])
        self.assertEqual({"passed": 1, "failed": 1}, counts)

if __name__ == "__main__":
    unittest.main()
