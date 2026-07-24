"""Validation for the approved ForgeOps OpenAPI 3.1 document subset."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from tools.interface_contract.common import ContractError, assert_exact_fields


API_VERSION = "1.0"
OPENAPI_VERSION = "3.1.0"
DOCUMENT_VERSION = "1.0.0"
API_ERROR_CODE_ENUM = (
    "API_VERSION_UNSUPPORTED",
    "API_SCHEMA_INVALID",
    "API_IDENTITY_MISMATCH",
    "API_CONTROL_FIELD_FORBIDDEN",
    "API_REFERENCE_INVALID",
    "API_RESOURCE_NOT_FOUND",
)
API_ERROR_CODES = frozenset(API_ERROR_CODE_ENUM)
EXPECTED_OPERATIONS = {
    ("post", "/v1/tasks"): "createTask",
    ("get", "/v1/tasks/{task_id}"): "getTask",
    ("get", "/v1/runs/{run_id}"): "getRun",
    ("get", "/v1/runs/{run_id}/events"): "listRunEvents",
    ("get", "/v1/runs/{run_id}/manifest"): "getRunManifest",
}
PATH_PARAMETER_NAMES = {
    "/v1/tasks": (),
    "/v1/tasks/{task_id}": ("task_id",),
    "/v1/runs/{run_id}": ("run_id",),
    "/v1/runs/{run_id}/events": ("run_id",),
    "/v1/runs/{run_id}/manifest": ("run_id",),
}
VERSION_ENVELOPE_CASE_FIELDS = {
    "id",
    "kind",
    "uri_major",
    "request_header",
    "body",
    "response",
    "expected",
}
VERSION_ENVELOPE_KINDS = frozenset(EXPECTED_OPERATIONS.values())
ENDPOINT_BODY_FIELDS = {
    "createTask": {"api_version", "request_id", "task_id"},
    "getTask": {"api_version", "path_task_id", "task_id"},
    "getRun": {"api_version", "path_run_id", "run_id"},
    "listRunEvents": {"api_version", "path_run_id", "run_id"},
    "getRunManifest": {"api_version", "path_run_id", "run_id"},
}
FORBIDDEN_CONTROL_FIELDS = frozenset(
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
    }
)
PRODUCT_CONTROL_FIELDS = frozenset({"budget", "approval_policy"})
SENSITIVE_RESPONSE_FIELDS = FORBIDDEN_CONTROL_FIELDS | frozenset(
    {"credential", "private", "private_data", "private_payload", "secret", "secrets"}
)
PRODUCT_SCHEMA_REF = "../../product-task-contract/1.0/schema.json"
RESPONSE_COMPONENTS = {
    "createTask": "CreateTaskResponse",
    "getTask": "TaskResponse",
    "getRun": "RunResponse",
    "listRunEvents": "EventPageResponse",
    "getRunManifest": "ManifestResponse",
}
COMPONENT_SCHEMA_NAMES = {
    "Identifier",
    "ApiVersion",
    "Status",
    "Error",
    "ErrorEnvelope",
    "SuccessEnvelope",
    "CreateTaskRequest",
    "CreateTaskData",
    "TaskData",
    "RunData",
    "EventPageData",
    "ManifestData",
    "CreateTaskResponse",
    "TaskResponse",
    "RunResponse",
    "EventPageResponse",
    "ManifestResponse",
}


def _schema_error() -> ContractError:
    return ContractError("API_SCHEMA_INVALID")


def _resolve_local_ref(document: dict[str, Any], reference: object) -> object:
    if not isinstance(reference, str) or not reference.startswith("#/"):
        raise ContractError("API_REFERENCE_INVALID")
    target: object = document
    for part in reference[2:].split("/"):
        if not isinstance(target, dict):
            raise ContractError("API_REFERENCE_INVALID")
        key = part.replace("~1", "/").replace("~0", "~")
        if key not in target:
            raise ContractError("API_REFERENCE_INVALID")
        target = target[key]
    return target


def _validate_schema(schema: object) -> None:
    if not isinstance(schema, dict):
        raise _schema_error()

    if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
        raise _schema_error()

    composition = [key for key in ("allOf", "anyOf", "oneOf") if key in schema]
    if composition and schema.get("unevaluatedProperties") is not False:
        raise _schema_error()

    properties = schema.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise _schema_error()
        for property_schema in properties.values():
            _validate_schema(property_schema)

    if "items" in schema:
        _validate_schema(schema["items"])

    for key in composition:
        choices = schema[key]
        if not isinstance(choices, list) or not choices:
            raise _schema_error()
        for choice in choices:
            _validate_schema(choice)


def _validate_request_id_parameter(parameter: object) -> None:
    if not isinstance(parameter, dict):
        raise _schema_error()
    assert_exact_fields(parameter, {"name", "in", "required", "schema"}, set(), "API_SCHEMA_INVALID")
    if (
        parameter["name"] != "X-Request-ID"
        or parameter["in"] != "header"
        or parameter["required"] is not True
        or not isinstance(parameter["schema"], dict)
    ):
        raise _schema_error()
    _validate_schema(parameter["schema"])


def _path_parameter(name: str) -> dict[str, object]:
    return {
        "name": name,
        "in": "path",
        "required": True,
        "schema": {"$ref": "#/components/schemas/Identifier"},
    }


def _validate_json_content(content: object) -> None:
    if not isinstance(content, dict) or set(content) != {"application/json"}:
        raise _schema_error()
    media = content["application/json"]
    if not isinstance(media, dict):
        raise _schema_error()
    assert_exact_fields(media, {"schema"}, set(), "API_SCHEMA_INVALID")
    _validate_schema(media["schema"])


def _validate_operation(
    operation: object, method: str, path: str
) -> None:
    expected_id = EXPECTED_OPERATIONS[(method, path)]
    required = {"operationId", "parameters", "responses"}
    if method == "post":
        required.add("requestBody")
    assert_exact_fields(operation, required, set(), "API_SCHEMA_INVALID")
    if not isinstance(operation, dict) or operation["operationId"] != expected_id:
        raise _schema_error()

    parameters = operation["parameters"]
    expected_parameters: list[object] = [
        {"$ref": "#/components/parameters/RequestIdHeader"}
    ]
    expected_parameters.extend(_path_parameter(name) for name in PATH_PARAMETER_NAMES[path])
    if not isinstance(parameters, list) or parameters != expected_parameters:
        raise _schema_error()

    if method == "post":
        request_body = operation["requestBody"]
        if not isinstance(request_body, dict):
            raise _schema_error()
        assert_exact_fields(request_body, {"required", "content"}, set(), "API_SCHEMA_INVALID")
        if request_body["required"] is not True:
            raise _schema_error()
        _validate_json_content(request_body["content"])
        request_schema = request_body["content"]["application/json"]["schema"]
        if request_schema != {"$ref": "#/components/schemas/CreateTaskRequest"}:
            raise _schema_error()

    responses = operation["responses"]
    if not isinstance(responses, dict) or not responses:
        raise _schema_error()
    success_status = "201" if method == "post" else "200"
    if set(responses) != {success_status, "400" if method == "post" else "404"}:
        raise _schema_error()
    for status, response in responses.items():
        if not isinstance(response, dict):
            raise _schema_error()
        assert_exact_fields(response, {"description", "content"}, set(), "API_SCHEMA_INVALID")
        if not isinstance(response["description"], str):
            raise _schema_error()
        _validate_json_content(response["content"])
        expected_component = (
            RESPONSE_COMPONENTS[expected_id]
            if status == success_status
            else "ErrorEnvelope"
        )
        response_schema = response["content"]["application/json"]["schema"]
        if response_schema != {"$ref": f"#/components/schemas/{expected_component}"}:
            raise _schema_error()


def _validate_component_schemas(schemas: object) -> None:
    if not isinstance(schemas, dict) or set(schemas) != COMPONENT_SCHEMA_NAMES:
        raise _schema_error()
    for schema in schemas.values():
        _validate_schema(schema)

    if schemas["Identifier"] != {"type": "string", "minLength": 1}:
        raise _schema_error()
    if schemas["ApiVersion"] != {"type": "string", "const": API_VERSION}:
        raise _schema_error()
    if schemas["Status"] != {
        "type": "string",
        "enum": [
            "PENDING",
            "IN_PROGRESS",
            "WAITING_FOR_HUMAN",
            "BLOCKED",
            "SUCCEEDED",
            "FAILED",
            "PARTIAL",
        ],
    }:
        raise _schema_error()
    if schemas["Error"] != {
        "type": "object",
        "additionalProperties": False,
        "required": ["code", "message"],
        "properties": {
            "code": {"type": "string", "enum": list(API_ERROR_CODE_ENUM)},
            "message": {"type": "string"},
        },
    }:
        raise _schema_error()
    if schemas["ErrorEnvelope"] != {
        "type": "object",
        "additionalProperties": False,
        "required": ["api_version", "request_id", "error"],
        "properties": {
            "api_version": {"$ref": "#/components/schemas/ApiVersion"},
            "request_id": {"$ref": "#/components/schemas/Identifier"},
            "error": {"$ref": "#/components/schemas/Error"},
        },
    }:
        raise _schema_error()
    if schemas["SuccessEnvelope"] != {
        "type": "object",
        "additionalProperties": False,
        "required": ["api_version"],
        "properties": {
            "api_version": {"$ref": "#/components/schemas/ApiVersion"},
        },
    }:
        raise _schema_error()
    if schemas["CreateTaskRequest"] != {
        "type": "object",
        "additionalProperties": False,
        "required": ["api_version", "request_id", "task_contract"],
        "properties": {
            "api_version": {"$ref": "#/components/schemas/ApiVersion"},
            "request_id": {"$ref": "#/components/schemas/Identifier"},
            "task_contract": {"$ref": PRODUCT_SCHEMA_REF},
        },
    }:
        raise _schema_error()

    expected_data_fields = {
        "CreateTaskData": {
            "task_id",
            "artifact_id",
            "artifact_version",
            "product_state",
            "contract_sha256",
            "links",
        },
        "TaskData": {"status", "revision", "last_event_seq"},
        "RunData": {
            "task_id",
            "run_id",
            "correlation_id",
            "run_mode",
            "status",
            "accepted_revision",
            "event_stream_ref",
            "manifest_ref",
        },
        "EventPageData": {
            "task_id",
            "run_id",
            "event_stream_ref",
            "event_refs",
            "next_page_ref",
        },
        "ManifestData": {"task_id", "run_id", "manifest_ref"},
    }
    for name, fields in expected_data_fields.items():
        schema = schemas[name]
        if (
            schema.get("type") != "object"
            or schema.get("additionalProperties") is not False
            or set(schema.get("required", [])) != fields
            or set(schema.get("properties", {})) != fields
        ):
            raise _schema_error()

    if schemas["CreateTaskData"]["properties"]["product_state"] != {
        "type": "string",
        "const": "CREATED",
    }:
        raise _schema_error()
    if schemas["CreateTaskData"]["properties"]["links"] != {
        "type": "object",
        "additionalProperties": False,
        "required": ["task", "run"],
        "properties": {
            "task": {"$ref": "#/components/schemas/Identifier"},
            "run": {"$ref": "#/components/schemas/Identifier"},
        },
    }:
        raise _schema_error()
    if schemas["RunData"]["properties"]["run_mode"] != {
        "type": "string",
        "enum": ["PRIMARY", "AUDIT_REPLAY", "COUNTERFACTUAL", "REEXECUTE"],
    }:
        raise _schema_error()

    for component_name in RESPONSE_COMPONENTS.values():
        expected_data_name = {
            "CreateTaskResponse": "CreateTaskData",
            "TaskResponse": "TaskData",
            "RunResponse": "RunData",
            "EventPageResponse": "EventPageData",
            "ManifestResponse": "ManifestData",
        }[component_name]
        if schemas[component_name] != {
            "type": "object",
            "additionalProperties": False,
            "required": ["api_version", "request_id", "data"],
            "properties": {
                "api_version": {"$ref": "#/components/schemas/ApiVersion"},
                "request_id": {"$ref": "#/components/schemas/Identifier"},
                "data": {"$ref": f"#/components/schemas/{expected_data_name}"},
            },
        }:
            raise _schema_error()


def validate_openapi_document(document: dict[str, Any]) -> None:
    """Validate the closed local OpenAPI surface for the first W3 interface task."""
    assert_exact_fields(document, {"openapi", "info", "paths", "components"}, set(), "API_SCHEMA_INVALID")
    if document["openapi"] != OPENAPI_VERSION:
        raise ContractError("API_VERSION_UNSUPPORTED")

    info = document["info"]
    assert_exact_fields(info, {"title", "version"}, set(), "API_SCHEMA_INVALID")
    if info["version"] != DOCUMENT_VERSION:
        raise ContractError("API_VERSION_UNSUPPORTED")
    if not isinstance(info["title"], str) or not info["title"]:
        raise _schema_error()

    paths = document["paths"]
    if not isinstance(paths, dict) or set(paths) != {path for _, path in EXPECTED_OPERATIONS}:
        raise _schema_error()
    actual_operations: set[tuple[str, str]] = set()
    for path, item in paths.items():
        if not isinstance(item, dict):
            raise _schema_error()
        for method, operation in item.items():
            identity = (method, path)
            if identity not in EXPECTED_OPERATIONS or identity in actual_operations:
                raise _schema_error()
            actual_operations.add(identity)
            _validate_operation(operation, method, path)
    if actual_operations != set(EXPECTED_OPERATIONS):
        raise _schema_error()

    components = document["components"]
    assert_exact_fields(components, {"parameters", "schemas"}, set(), "API_SCHEMA_INVALID")
    parameters = components["parameters"]
    if not isinstance(parameters, dict) or set(parameters) != {"RequestIdHeader"}:
        raise _schema_error()
    _validate_request_id_parameter(parameters["RequestIdHeader"])
    _validate_component_schemas(components["schemas"])

    def visit(value: object) -> None:
        if isinstance(value, dict):
            if "$ref" in value:
                if set(value) != {"$ref"}:
                    raise ContractError("API_REFERENCE_INVALID")
                if value["$ref"] != PRODUCT_SCHEMA_REF:
                    _resolve_local_ref(document, value["$ref"])
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(document)


def _is_ascii_identifier(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value.isascii()


def _validate_common_envelope(case: dict[str, Any]) -> None:
    body = case["body"]
    response = case["response"]
    if not isinstance(body, dict) or not isinstance(response, dict):
        raise _schema_error()
    if not isinstance(body.get("api_version"), str):
        raise _schema_error()
    if not {"api_version", "request_id"}.issubset(response):
        raise _schema_error()
    if not isinstance(response["api_version"], str) or not isinstance(response["request_id"], str):
        raise _schema_error()
    if response["api_version"] != API_VERSION:
        raise ContractError("API_VERSION_UNSUPPORTED")


def validate_request_id(case: dict[str, Any]) -> None:
    """Validate request-ID presence, ASCII type, and exact envelope equality."""
    header = case["request_header"]
    body = case["body"]
    response = case["response"]
    identifiers = [header, response.get("request_id")]
    if case["kind"] == "createTask":
        identifiers.append(body.get("request_id"))
    if not all(_is_ascii_identifier(value) for value in identifiers):
        raise _schema_error()
    if response["request_id"] != header:
        raise ContractError("API_IDENTITY_MISMATCH")
    if case["kind"] == "createTask" and body["request_id"] != header:
        raise ContractError("API_IDENTITY_MISMATCH")


def _scan_forbidden_control_fields(body: dict[str, Any]) -> None:
    if any(field in body for field in FORBIDDEN_CONTROL_FIELDS):
        raise ContractError("API_CONTROL_FIELD_FORBIDDEN")


def validate_endpoint_shape(case: dict[str, Any]) -> None:
    """Require the fixture-only simple inputs and a closed success/error envelope."""
    body = case["body"]
    expected_fields = ENDPOINT_BODY_FIELDS[case["kind"]]
    assert_exact_fields(body, expected_fields, set(), "API_SCHEMA_INVALID")
    for field in expected_fields - {"api_version"}:
        if not _is_ascii_identifier(body[field]):
            raise _schema_error()

    response = case["response"]
    has_data = "data" in response
    has_error = "error" in response
    if has_data == has_error:
        raise _schema_error()
    branch = "data" if has_data else "error"
    assert_exact_fields(
        response,
        {"api_version", "request_id", branch},
        set(),
        "API_SCHEMA_INVALID",
    )
    if branch == "data":
        if not isinstance(response["data"], dict):
            raise _schema_error()
        return

    error = response["error"]
    assert_exact_fields(error, {"code", "message"}, set(), "API_SCHEMA_INVALID")
    if error["code"] not in API_ERROR_CODES or not isinstance(error["message"], str):
        raise _schema_error()


def _validate_path_body_identity(case: dict[str, Any]) -> None:
    body = case["body"]
    if case["kind"] == "getTask":
        if body["path_task_id"] != body["task_id"]:
            raise ContractError("API_IDENTITY_MISMATCH")
    elif case["kind"] != "createTask" and body["path_run_id"] != body["run_id"]:
        raise ContractError("API_IDENTITY_MISMATCH")


def _validate_component_reference(case: dict[str, Any], document: dict[str, Any]) -> None:
    for (method, path), operation_id in EXPECTED_OPERATIONS.items():
        if operation_id != case["kind"]:
            continue
        operation = document["paths"][path][method]
        for response in operation["responses"].values():
            schema = response["content"]["application/json"]["schema"]
            if not isinstance(schema, dict) or "$ref" not in schema:
                raise ContractError("API_REFERENCE_INVALID")
            _resolve_local_ref(document, schema["$ref"])
        return
    raise _schema_error()


def evaluate_version_envelope(case: dict[str, Any], document: dict[str, Any]) -> str:
    """Evaluate one version/envelope fixture with the approved stable ordering."""
    validate_openapi_document(document)
    assert_exact_fields(case, VERSION_ENVELOPE_CASE_FIELDS, set(), "API_SCHEMA_INVALID")
    if not _is_ascii_identifier(case["id"]) or case["kind"] not in VERSION_ENVELOPE_KINDS:
        raise _schema_error()
    if not isinstance(case["uri_major"], str):
        raise _schema_error()
    if case["uri_major"] != "v1":
        raise ContractError("API_VERSION_UNSUPPORTED")
    body = case["body"]
    if isinstance(body, dict) and "api_version" in body:
        if not isinstance(body["api_version"], str):
            raise _schema_error()
        if body["api_version"] != API_VERSION:
            raise ContractError("API_VERSION_UNSUPPORTED")

    _validate_common_envelope(case)
    _scan_forbidden_control_fields(body)
    validate_endpoint_shape(case)
    validate_request_id(case)
    _validate_path_body_identity(case)
    _validate_component_reference(case, document)
    return "PASSED"


@dataclass
class EffectSpies:
    """Effect counters that remain untouched by pure boundary validation."""

    dispatcher_calls: int = 0
    process_calls: int = 0
    network_calls: int = 0
    credential_calls: int = 0
    store_calls: int = 0


EFFECT_SPY_FIELDS = (
    "dispatcher_calls",
    "process_calls",
    "network_calls",
    "credential_calls",
    "store_calls",
)


def _effect_spy_calls(spies: EffectSpies) -> dict[str, int]:
    return {field: getattr(spies, field) for field in EFFECT_SPY_FIELDS}


def _validate_expected_spy_calls(entry: dict[str, Any], expected: object) -> None:
    if expected == "PASSED":
        return
    spy_calls = entry.get("expected_spy_calls")
    if not isinstance(spy_calls, dict) or set(spy_calls) != set(EFFECT_SPY_FIELDS):
        raise _schema_error()
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in spy_calls.values()
    ):
        raise _schema_error()


def _legacy_envelope_case(case: dict[str, Any]) -> dict[str, Any]:
    """Project W3-2 inputs through the already-approved W3-1 evaluator."""
    kind = case.get("kind")
    body = case.get("body")
    if isinstance(body, dict) and kind == "createTask":
        body = {
            "api_version": body.get("api_version"),
            "request_id": body.get("request_id"),
            "task_id": "w3-2-unvalidated-product-task",
        }
    elif isinstance(body, dict) and kind in ENDPOINT_BODY_FIELDS:
        body = {field: body.get(field) for field in ENDPOINT_BODY_FIELDS[kind]}

    return {
        "id": case.get("id"),
        "kind": kind,
        "uri_major": case.get("uri_major"),
        "request_header": case.get("request_header"),
        "body": body,
        "response": case.get("response"),
        "expected": case.get("expected"),
    }


def _validate_api_body(case: dict[str, Any]) -> None:
    body = case["body"]
    if case["kind"] == "createTask":
        assert_exact_fields(
            body,
            {"api_version", "request_id", "task_contract"},
            set(),
            "API_SCHEMA_INVALID",
        )
        return

    expected = ENDPOINT_BODY_FIELDS[case["kind"]]
    assert_exact_fields(body, expected, set(), "API_SCHEMA_INVALID")
    for field in expected - {"api_version"}:
        if not _is_ascii_identifier(body[field]):
            raise _schema_error()


def _validate_product_contract(contract: object, product_schema: dict[str, Any]) -> None:
    if not isinstance(product_schema, dict):
        raise _schema_error()
    try:
        Draft202012Validator.check_schema(product_schema)
        errors = list(Draft202012Validator(product_schema).iter_errors(contract))
    except SchemaError as exc:
        raise _schema_error() from exc
    if errors:
        raise _schema_error()


def _validate_component_instance(
    value: object, component_name: str, document: dict[str, Any]
) -> None:
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": f"#/components/schemas/{component_name}",
        "components": copy.deepcopy(document["components"]),
    }
    try:
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(value))
    except SchemaError as exc:
        raise _schema_error() from exc
    if errors:
        raise _schema_error()


def _assert_non_grant(case: dict[str, Any]) -> None:
    if "derived_control" not in case:
        return
    derived = case["derived_control"]
    if not isinstance(derived, dict):
        raise _schema_error()
    control_fields = FORBIDDEN_CONTROL_FIELDS | PRODUCT_CONTROL_FIELDS | frozenset(
        {"approval", "budget", "budgets", "control", "policy", "runtime_budget"}
    )
    if control_fields.intersection(derived):
        raise ContractError("API_CONTROL_FIELD_FORBIDDEN")
    if derived:
        raise _schema_error()


def _assert_public_response(response: object) -> None:
    def visit(value: object) -> None:
        if isinstance(value, dict):
            if SENSITIVE_RESPONSE_FIELDS.intersection(value):
                raise ContractError("API_CONTROL_FIELD_FORBIDDEN")
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)
        elif isinstance(value, str) and "://" in value:
            raise ContractError("API_CONTROL_FIELD_FORBIDDEN")

    visit(response)


def _validate_api_identity(case: dict[str, Any]) -> None:
    response = case["response"]
    if "data" not in response:
        return
    data = response["data"]
    body = case["body"]
    kind = case["kind"]
    if kind == "createTask":
        contract = body["task_contract"]
        if any(
            data[field] != contract[field]
            for field in ("task_id", "artifact_id", "artifact_version")
        ):
            raise ContractError("API_IDENTITY_MISMATCH")
    elif kind in {"getRun", "listRunEvents", "getRunManifest"}:
        if data["run_id"] != body["run_id"]:
            raise ContractError("API_IDENTITY_MISMATCH")


def _validate_resolved_reference(
    reference: object,
    expected_kind: str,
    task_id: str,
    run_id: str,
    context: object,
) -> None:
    if not isinstance(reference, str) or not isinstance(context, dict):
        raise ContractError("API_REFERENCE_INVALID")
    resolved = context.get(reference)
    if not isinstance(resolved, dict):
        raise ContractError("API_REFERENCE_INVALID")
    if set(resolved) != {"kind", "task_id", "run_id"}:
        raise ContractError("API_REFERENCE_INVALID")
    if resolved != {
        "kind": expected_kind,
        "task_id": task_id,
        "run_id": run_id,
    }:
        raise ContractError("API_REFERENCE_INVALID")


def _validate_case_references(case: dict[str, Any]) -> None:
    response = case["response"]
    if "data" not in response or case["kind"] in {"createTask", "getTask"}:
        return
    data = response["data"]
    context = case.get("reference_context")
    task_id = data["task_id"]
    run_id = data["run_id"]
    if case["kind"] in {"getRun", "listRunEvents"}:
        _validate_resolved_reference(
            data["event_stream_ref"], "event_stream", task_id, run_id, context
        )
    if case["kind"] in {"getRun", "getRunManifest"}:
        _validate_resolved_reference(
            data["manifest_ref"], "manifest", task_id, run_id, context
        )


def validate_api_case(
    case: dict[str, Any],
    document: dict[str, Any],
    product_schema: dict[str, Any],
    spies: EffectSpies,
) -> str:
    """Validate one API data/control case without invoking any effect surface."""
    if not isinstance(spies, EffectSpies):
        raise _schema_error()

    evaluate_version_envelope(_legacy_envelope_case(case), document)
    body = case["body"]
    _scan_forbidden_control_fields(body)
    _validate_api_body(case)
    if case["kind"] == "createTask":
        _validate_product_contract(body["task_contract"], product_schema)
    _assert_non_grant(case)
    _assert_public_response(case["response"])

    response_component = (
        RESPONSE_COMPONENTS[case["kind"]]
        if "data" in case["response"]
        else "ErrorEnvelope"
    )
    _validate_component_instance(case["response"], response_component, document)
    _validate_api_identity(case)
    _validate_case_references(case)
    return "PASSED"


def run_version_envelope_suite(
    document: dict[str, Any], suite: dict[str, Any]
) -> list[dict[str, str]]:
    """Run a closed fixture catalog and expose only public-safe result records."""
    assert_exact_fields(suite, {"suite_id", "suite_version", "cases"}, set(), "API_SCHEMA_INVALID")
    if suite["suite_id"] != "forgeops-api-version-envelope" or suite["suite_version"] != API_VERSION:
        raise _schema_error()
    cases = suite["cases"]
    if not isinstance(cases, list):
        raise _schema_error()

    records: list[dict[str, str]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise _schema_error()
        assert_exact_fields(case, VERSION_ENVELOPE_CASE_FIELDS, set(), "API_SCHEMA_INVALID")
        if not _is_ascii_identifier(case["id"]) or case["kind"] not in VERSION_ENVELOPE_KINDS:
            raise _schema_error()
        expected = case["expected"]
        if expected != "PASSED" and expected not in API_ERROR_CODES:
            raise _schema_error()
        try:
            actual = evaluate_version_envelope(case, document)
        except ContractError as error:
            actual = error.code
        records.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "expected": expected,
                "actual": actual,
                "status": "PASSED" if actual == expected else "FAILED",
            }
        )
    return records


def _materialize_api_boundary_case(
    entry: dict[str, Any], entries: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    if "base_id" not in entry:
        return copy.deepcopy(entry)

    base_id = entry.get("base_id")
    if not isinstance(base_id, str) or base_id not in entries:
        raise _schema_error()
    case = copy.deepcopy(entries[base_id])
    case["id"] = entry.get("id")
    case["expected"] = entry.get("expected")
    mutation = entry.get("mutation")
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
    elif mutation == "top_level_control" and parameter in FORBIDDEN_CONTROL_FIELDS:
        case["body"][parameter] = {}
    elif mutation == "copied_product_control" and parameter in PRODUCT_CONTROL_FIELDS:
        case["derived_control"] = {
            parameter: copy.deepcopy(case["body"]["task_contract"][parameter])
        }
    elif mutation == "task_identity_mismatch":
        case["body"]["path_task_id"] = "TASK-API-DIFFERENT"
    elif mutation == "run_identity_mismatch":
        case["body"]["path_run_id"] = "RUN-API-DIFFERENT"
    elif mutation == "dangling_event_reference":
        del case["reference_context"][case["response"]["data"]["event_stream_ref"]]
    elif mutation == "dangling_manifest_reference":
        del case["reference_context"][case["response"]["data"]["manifest_ref"]]
    elif mutation == "response_data_error":
        case["response"]["error"] = {
            "code": "API_SCHEMA_INVALID",
            "message": "rejected",
        }
    elif mutation == "raw_response_field" and isinstance(parameter, str):
        case["response"]["data"][parameter] = "raw-value"
    else:
        raise _schema_error()
    return case


def run_api_boundary_suite(
    document: dict[str, Any],
    product_schema: dict[str, Any],
    suite: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Run the closed W3-2 catalog without invoking an effect surface."""
    assert_exact_fields(
        suite,
        {"suite_id", "suite_version", "cases"},
        set(),
        "API_SCHEMA_INVALID",
    )
    if (
        suite["suite_id"] != "forgeops-api-data-control"
        or suite["suite_version"] != API_VERSION
        or not isinstance(suite["cases"], list)
    ):
        raise _schema_error()

    entries: dict[str, dict[str, Any]] = {}
    for entry in suite["cases"]:
        if not isinstance(entry, dict) or not _is_ascii_identifier(entry.get("id")):
            raise _schema_error()
        if entry["id"] in entries:
            raise _schema_error()
        expected = entry.get("expected")
        if expected != "PASSED" and expected not in API_ERROR_CODES:
            raise _schema_error()
        _validate_expected_spy_calls(entry, expected)
        entries[entry["id"]] = entry

    records: list[dict[str, Any]] = []
    counts = {"passed": 0, "failed": 0}
    for entry in suite["cases"]:
        case = _materialize_api_boundary_case(entry, entries)
        expected = entry.get("expected")
        spies = EffectSpies()
        try:
            actual = validate_api_case(case, document, product_schema, spies)
        except ContractError as error:
            actual = error.code
        spy_calls = _effect_spy_calls(spies)
        expected_spy_calls = entry.get("expected_spy_calls")
        spy_calls_match = expected == "PASSED" or spy_calls == expected_spy_calls
        status = "PASSED" if actual == expected and spy_calls_match else "FAILED"
        counts[status.lower()] += 1
        records.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "expected": expected,
                "actual": actual,
                "status": status,
                "spy_calls": spy_calls,
            }
        )
    return records, counts
