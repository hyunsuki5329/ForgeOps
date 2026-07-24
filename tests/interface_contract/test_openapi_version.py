from __future__ import annotations

import copy
import unittest
from pathlib import Path

from tools.interface_contract.common import ContractError, load_json
from tools.interface_contract.openapi_contract import (
    evaluate_version_envelope,
    run_version_envelope_suite,
    validate_openapi_document,
)


ROOT = Path(__file__).resolve().parents[2]
VERSION_ENVELOPE_CASE_IDS = [
    "valid-create-task",
    "valid-get-task",
    "valid-get-run",
    "valid-list-run-events",
    "valid-get-run-manifest",
    "unsupported-uri-major",
    "unsupported-body-version",
    "missing-request-header",
    "invalid-request-id-type",
    "request-id-header-body-mismatch",
    "response-request-id-mismatch",
    "endpoint-unknown-field",
    "endpoint-missing-required-field",
    "endpoint-wrong-field-type",
    "path-body-identity-mismatch",
    "response-data-error-conflict",
]
VERSION_ENVELOPE_EXPECTED_CATEGORIES = [
    "PASSED",
    "PASSED",
    "PASSED",
    "PASSED",
    "PASSED",
    "API_VERSION_UNSUPPORTED",
    "API_VERSION_UNSUPPORTED",
    "API_SCHEMA_INVALID",
    "API_SCHEMA_INVALID",
    "API_IDENTITY_MISMATCH",
    "API_IDENTITY_MISMATCH",
    "API_SCHEMA_INVALID",
    "API_SCHEMA_INVALID",
    "API_SCHEMA_INVALID",
    "API_IDENTITY_MISMATCH",
    "API_SCHEMA_INVALID",
]


class OpenApiDocumentTests(unittest.TestCase):
    def test_document_has_exact_version_and_operations(self):
        document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")
        validate_openapi_document(document)
        self.assertEqual("3.1.0", document["openapi"])
        self.assertEqual("1.0.0", document["info"]["version"])
        actual = {
            (method.upper(), path, operation["operationId"])
            for path, item in document["paths"].items()
            for method, operation in item.items()
        }
        self.assertEqual(
            {
                ("POST", "/v1/tasks", "createTask"),
                ("GET", "/v1/tasks/{task_id}", "getTask"),
                ("GET", "/v1/runs/{run_id}", "getRun"),
                ("GET", "/v1/runs/{run_id}/events", "listRunEvents"),
                ("GET", "/v1/runs/{run_id}/manifest", "getRunManifest"),
            },
            actual,
        )

    def test_every_operation_requires_request_id_header(self):
        document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")
        for path_item in document["paths"].values():
            for operation in path_item.values():
                refs = [item.get("$ref") for item in operation["parameters"]]
                self.assertIn("#/components/parameters/RequestIdHeader", refs)

    def test_path_templates_require_matching_path_parameter(self):
        document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")
        changed = copy.deepcopy(document)
        for path, path_item in changed["paths"].items():
            if "{" not in path:
                continue
            operation = path_item["get"]
            operation["parameters"] = [
                parameter
                for parameter in operation["parameters"]
                if parameter.get("in") != "path"
            ]

        with self.assertRaisesRegex(ContractError, "API_SCHEMA_INVALID"):
            validate_openapi_document(changed)

    def test_error_schema_rejects_missing_stable_category(self):
        document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")
        changed = copy.deepcopy(document)
        changed["components"]["schemas"]["Error"]["properties"]["code"]["enum"].pop()

        with self.assertRaisesRegex(ContractError, "API_SCHEMA_INVALID"):
            validate_openapi_document(changed)

    def test_envelopes_require_api_version_schema_wiring(self):
        document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")
        for envelope in ("ErrorEnvelope", "SuccessEnvelope"):
            changed = copy.deepcopy(document)
            changed["components"]["schemas"][envelope]["properties"]["api_version"] = {
                "$ref": "#/components/schemas/Identifier"
            }

            with self.subTest(envelope=envelope):
                with self.assertRaisesRegex(ContractError, "API_SCHEMA_INVALID"):
                    validate_openapi_document(changed)


class VersionEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")

    def test_exact_case_catalog(self):
        suite = load_json(ROOT / "fixtures/forgeops-api/version-envelope-suite.json")
        self.assertEqual("forgeops-api-version-envelope", suite["suite_id"])
        self.assertEqual("1.0", suite["suite_version"])
        self.assertEqual(VERSION_ENVELOPE_CASE_IDS, [case["id"] for case in suite["cases"]])
        self.assertEqual(
            list(zip(VERSION_ENVELOPE_CASE_IDS, VERSION_ENVELOPE_EXPECTED_CATEGORIES)),
            [(case["id"], case["expected"]) for case in suite["cases"]],
        )

    def test_identifiers_accept_all_non_empty_ascii_literals_without_trimming(self):
        case = {
            "id": " case id ",
            "kind": "createTask",
            "uri_major": "v1",
            "request_header": " request id ",
            "body": {
                "api_version": "1.0",
                "request_id": " request id ",
                "task_id": " task id ",
            },
            "response": {
                "api_version": "1.0",
                "request_id": " request id ",
                "data": {},
            },
            "expected": "PASSED",
        }

        self.assertEqual("PASSED", evaluate_version_envelope(case, self.document))

        case["response"]["request_id"] = "request id"
        with self.assertRaisesRegex(ContractError, "API_IDENTITY_MISMATCH"):
            evaluate_version_envelope(case, self.document)

    def test_version_error_precedes_closed_body_error(self):
        case = {
            "id": "priority-case",
            "kind": "createTask",
            "uri_major": "v2",
            "request_header": "request-001",
            "body": {
                "api_version": "1.0",
                "request_id": "request-001",
                "task_id": "task-001",
                "unknown": True,
            },
            "response": {
                "api_version": "1.0",
                "request_id": "request-001",
                "data": {},
            },
            "expected": "API_VERSION_UNSUPPORTED",
        }

        with self.assertRaisesRegex(ContractError, "API_VERSION_UNSUPPORTED"):
            evaluate_version_envelope(case, self.document)

    def test_response_api_version_must_be_exact(self):
        case = {
            "id": "response-version-case",
            "kind": "createTask",
            "uri_major": "v1",
            "request_header": "request-response-version",
            "body": {
                "api_version": "1.0",
                "request_id": "request-response-version",
                "task_id": "task-response-version",
            },
            "response": {
                "api_version": "2.0",
                "request_id": "request-response-version",
                "data": {},
            },
            "expected": "API_VERSION_UNSUPPORTED",
        }

        with self.assertRaisesRegex(ContractError, "API_VERSION_UNSUPPORTED"):
            evaluate_version_envelope(case, self.document)

        case["response"]["api_version"] = 2
        with self.assertRaisesRegex(ContractError, "API_SCHEMA_INVALID"):
            evaluate_version_envelope(case, self.document)

    def test_non_string_body_version_is_schema_invalid(self):
        case = {
            "id": "body-version-type-case",
            "kind": "createTask",
            "uri_major": "v1",
            "request_header": "request-body-version-type",
            "body": {
                "api_version": 1,
                "request_id": "request-body-version-type",
                "task_id": "task-body-version-type",
            },
            "response": {
                "api_version": "1.0",
                "request_id": "request-body-version-type",
                "data": {},
            },
            "expected": "API_SCHEMA_INVALID",
        }

        with self.assertRaisesRegex(ContractError, "API_SCHEMA_INVALID"):
            evaluate_version_envelope(case, self.document)

    def test_result_records_are_public_safe_and_match_expected(self):
        suite = load_json(ROOT / "fixtures/forgeops-api/version-envelope-suite.json")
        records = run_version_envelope_suite(self.document, suite)

        self.assertTrue(
            all(
                set(record) == {"id", "kind", "expected", "actual", "status"}
                for record in records
            )
        )
        self.assertTrue(all(record["actual"] == record["expected"] for record in records))
        self.assertTrue(all(record["status"] == "PASSED" for record in records))


if __name__ == "__main__":
    unittest.main()
