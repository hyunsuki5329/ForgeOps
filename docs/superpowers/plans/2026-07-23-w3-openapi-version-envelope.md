# W3-1 OpenAPI Version and Envelope Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define and executable-test the OpenAPI 3.1 version, operation surface, request identity, and common success/error envelopes for ForgeOps API v1.

**Architecture:** Store the OpenAPI document as JSON-compatible YAML so the existing Python runtime can parse it with `json` without adding a YAML dependency. Keep reusable parsing, exact-field, UTC, hashing, and stable-error primitives in `common.py`; keep OpenAPI-specific structural and case validation in `openapi_contract.py`.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `json`/`hashlib`/`unittest`, OpenAPI 3.1.0, JSON-compatible YAML

## Global Constraints

- Implement only the five approved operations under `/v1`; do not create an API server, listener, database, authentication mechanism, SSE, or WebSocket transport.
- Fix `openapi` to `3.1.0`, `info.version` to `1.0.0`, and request/response `api_version` to the literal `1.0`.
- Require `X-Request-ID` on every operation; mutation body `request_id` and response `request_id` must ordinal-exactly equal the header.
- Keep every object closed with `additionalProperties: false`; also use `unevaluatedProperties: false` on composed object schemas.
- Emit only the first stable error according to the approved validation order, and never include raw requests, headers, validator internals, credentials, or private payloads in results.
- The stable API categories are exactly `API_VERSION_UNSUPPORTED`, `API_SCHEMA_INVALID`, `API_IDENTITY_MISMATCH`, `API_CONTROL_FIELD_FORBIDDEN`, `API_REFERENCE_INVALID`, and `API_RESOURCE_NOT_FOUND`.
- Do not change WBS/RTM status, invoke network/external effects, or run Git add/commit/push/PR without separate authorization.

---

## File Structure

- Create `tools/interface_contract/__init__.py`: marks the verifier helpers as one importable package.
- Create `tools/interface_contract/common.py`: closed error type, JSON-compatible YAML loader, exact-field assertion, strict UTC check, SHA-256 helper.
- Create `tools/interface_contract/openapi_contract.py`: OpenAPI subset validator and W3-1 version/envelope case evaluator.
- Create `contracts/forgeops-api/1.0/openapi.yaml`: approved v1 paths and common schemas.
- Create `fixtures/forgeops-api/version-envelope-suite.json`: exact ordered W3-1 positive/negative case catalog.
- Create `tests/interface_contract/__init__.py`: enables module-based unittest execution.
- Create `tests/interface_contract/test_openapi_version.py`: structural, version, envelope, identity, and result-safety tests.

### Task 1: Lock the OpenAPI document and common validation primitives

**Files:**

- Create: `tools/interface_contract/__init__.py`
- Create: `tools/interface_contract/common.py`
- Create: `tools/interface_contract/openapi_contract.py`
- Create: `contracts/forgeops-api/1.0/openapi.yaml`
- Create: `tests/interface_contract/__init__.py`
- Create: `tests/interface_contract/test_openapi_version.py`

**Interfaces:**

- `ContractError(code: str)` exposes the stable category as `code` and exception text.
- `load_json(path: Path) -> dict` parses UTF-8 JSON or JSON-compatible YAML and rejects non-object roots.
- `assert_exact_fields(value: dict, required: set[str], optional: set[str], code: str) -> None` rejects missing and unknown fields without normalization.
- `validate_openapi_document(document: dict) -> None` validates the approved OpenAPI subset and all local `$ref` targets.
- `evaluate_version_envelope(case: dict, document: dict) -> str` returns `PASSED` or raises `ContractError`.

- [ ] **Step 1: Write failing document-structure tests**

```python
class OpenApiDocumentTests(unittest.TestCase):
    def test_document_has_exact_version_and_operations(self):
        document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")
        validate_openapi_document(document)
        self.assertEqual("3.1.0", document["openapi"])
        self.assertEqual("1.0.0", document["info"]["version"])
        actual = {(method.upper(), path, operation["operationId"])
                  for path, item in document["paths"].items()
                  for method, operation in item.items()}
        self.assertEqual({
            ("POST", "/v1/tasks", "createTask"),
            ("GET", "/v1/tasks/{task_id}", "getTask"),
            ("GET", "/v1/runs/{run_id}", "getRun"),
            ("GET", "/v1/runs/{run_id}/events", "listRunEvents"),
            ("GET", "/v1/runs/{run_id}/manifest", "getRunManifest"),
        }, actual)

    def test_every_operation_requires_request_id_header(self):
        document = load_json(ROOT / "contracts/forgeops-api/1.0/openapi.yaml")
        for path_item in document["paths"].values():
            for operation in path_item.values():
                refs = [item.get("$ref") for item in operation["parameters"]]
                self.assertIn("#/components/parameters/RequestIdHeader", refs)
```

- [ ] **Step 2: Run the tests and observe the intended RED state**

Run: `python -m unittest tests.interface_contract.test_openapi_version -v`
Expected: FAIL because `contracts/forgeops-api/1.0/openapi.yaml` and the validator modules do not exist.

- [ ] **Step 3: Add exact common primitives**

```python
class ContractError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)

def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if type(value) is not dict:
        raise ContractError("INTERFACE_RUNNER_CONTRACT_INVALID")
    return value

def assert_exact_fields(value, required, optional, code):
    if type(value) is not dict or set(value) != required | (set(value) & optional):
        raise ContractError(code)
    if not required.issubset(value):
        raise ContractError(code)
```

Add `sha256_file(path: Path) -> str` using chunked binary reads and `is_strict_utc(value: object) -> bool` using `datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")` plus exact round-trip formatting.

- [ ] **Step 4: Write the OpenAPI document and focused subset validator**

The document root is exactly `openapi`, `info`, `paths`, `components`; `components` defines `RequestIdHeader`, `Identifier`, `ApiVersion`, `Error`, `ErrorEnvelope`, and `SuccessEnvelope`. Each operation references the common envelopes in a structurally valid document; W3-2 later adds endpoint-specific data schemas without changing these common components. Every operation has the exact method/path/operationId above, the request-ID parameter, and only JSON responses. `validate_openapi_document` checks those exact roots, versions, paths, operation IDs, parameter reference, component presence, local reference resolution, and recursively enforces closed object schemas.

```python
def validate_openapi_document(document: dict) -> None:
    assert_exact_fields(document, {"openapi", "info", "paths", "components"}, set(), "API_SCHEMA_INVALID")
    if document["openapi"] != "3.1.0" or document["info"].get("version") != "1.0.0":
        raise ContractError("API_VERSION_UNSUPPORTED")
    if operation_catalog(document) != EXPECTED_OPERATIONS:
        raise ContractError("API_SCHEMA_INVALID")
    validate_local_refs(document)
    validate_closed_objects(document["components"]["schemas"])
```

- [ ] **Step 5: Run the document tests**

Run: `python -m unittest tests.interface_contract.test_openapi_version.OpenApiDocumentTests -v`
Expected: PASS with two tests and no network or external process invocation.

- [ ] **Step 6: Review the task diff without committing**

Run: `git diff --check`
Expected: exit 0. Confirm the diff contains only the files listed in this task; leave them unstaged.

### Task 2: Prove version, envelope, identity, and closed-object behavior

**Files:**

- Create: `fixtures/forgeops-api/version-envelope-suite.json`
- Modify: `tools/interface_contract/openapi_contract.py`
- Modify: `tests/interface_contract/test_openapi_version.py`

**Interfaces:**

- Suite root: `{suite_id, suite_version, cases}` with `suite_id="forgeops-api-version-envelope"`, `suite_version="1.0"`.
- Case: `{id, kind, uri_major, request_header, body, response, expected}`; `expected` is `PASSED` or one approved API stable error.
- `run_version_envelope_suite(document: dict, suite: dict) -> list[dict]` returns only `{id, kind, expected, actual, status}` records.

- [ ] **Step 1: Add failing catalog and priority tests**

```python
def test_exact_case_catalog(self):
    suite = load_json(ROOT / "fixtures/forgeops-api/version-envelope-suite.json")
    self.assertEqual(EXPECTED_CASE_IDS, [case["id"] for case in suite["cases"]])

def test_version_error_precedes_closed_body_error(self):
    case = valid_create_case()
    case["uri_major"] = "v2"
    case["body"]["unknown"] = True
    with self.assertRaisesRegex(ContractError, "API_VERSION_UNSUPPORTED"):
        evaluate_version_envelope(case, DOCUMENT)

def test_result_records_are_public_safe(self):
    records = run_version_envelope_suite(DOCUMENT, SUITE)
    self.assertTrue(all(set(item) == {"id", "kind", "expected", "actual", "status"} for item in records))
```

- [ ] **Step 2: Run the suite tests and observe RED**

Run: `python -m unittest tests.interface_contract.test_openapi_version -v`
Expected: FAIL because the suite catalog and evaluator are incomplete.

- [ ] **Step 3: Add the exact ordered fixture catalog**

Include valid envelopes for all five operations, then these negatives in order: unknown URI major, unsupported body version, missing request header, wrong request-ID type, header/body mismatch, response request-ID mismatch, unknown field, missing required field, wrong field type, path/body identity mismatch, and simultaneous `data`/`error`. Each negative carries exactly one expected stable category.

- [ ] **Step 4: Implement the approved validation order**

```python
def evaluate_version_envelope(case: dict, document: dict) -> str:
    validate_openapi_document(document)
    if case["uri_major"] != "v1" or case.get("body", {}).get("api_version", "1.0") != "1.0":
        raise ContractError("API_VERSION_UNSUPPORTED")
    validate_request_id(case)
    scan_forbidden_control_fields(case.get("body", {}))
    validate_endpoint_shape(case)
    validate_identity_matches(case)
    validate_component_refs(case, document)
    return "PASSED"
```

`validate_request_id` requires a non-empty ASCII string and exact header/body/response equality. `validate_endpoint_shape` requires exactly one response branch (`data` xor `error`) and maps unknown/missing/wrong-type fields to `API_SCHEMA_INVALID`.

- [ ] **Step 5: Run all W3-1 tests**

Run: `python -m unittest tests.interface_contract.test_openapi_version -v`
Expected: PASS; every ordered fixture has `actual == expected` and no case record contains raw body/header values.

- [ ] **Step 6: Review the W3-1 deliverable without changing project status**

Run: `git diff --check`
Expected: exit 0. Keep `WBS-006` and RTM evidence unchanged because VG-004 has not run yet.
