### Task 1: Lock the OpenAPI document and common validation primitives

**Files:**

- Create `tools/interface_contract/__init__.py`.
- Create `tools/interface_contract/common.py`.
- Create `tools/interface_contract/openapi_contract.py`.
- Create `contracts/forgeops-api/1.0/openapi.yaml` as UTF-8 JSON-compatible YAML.
- Create `tests/interface_contract/__init__.py`.
- Create `tests/interface_contract/test_openapi_version.py`.

**Binding constraints:**

- Implement only `POST /v1/tasks`, `GET /v1/tasks/{task_id}`, `GET /v1/runs/{run_id}`, `GET /v1/runs/{run_id}/events`, `GET /v1/runs/{run_id}/manifest`; do not create a server, listener, database, authentication, SSE, or WebSocket transport.
- `openapi` is `3.1.0`, `info.version` is `1.0.0`; request/response `api_version` is literal `1.0`.
- Every operation requires `X-Request-ID`; all object schemas use `additionalProperties: false`, and composed object schemas use `unevaluatedProperties: false`.
- Stable API categories are exactly `API_VERSION_UNSUPPORTED`, `API_SCHEMA_INVALID`, `API_IDENTITY_MISMATCH`, `API_CONTROL_FIELD_FORBIDDEN`, `API_REFERENCE_INVALID`, `API_RESOURCE_NOT_FOUND`.
- Do not modify WBS/RTM, invoke external effects, stage, commit, push, or create a PR.

**Required interfaces:**

- `ContractError(code: str)` exposes `code` and uses it as exception text.
- `load_json(path: Path) -> dict` parses UTF-8 JSON-compatible YAML and rejects non-object roots.
- `assert_exact_fields(value: dict, required: set[str], optional: set[str], code: str) -> None` rejects missing/unknown fields without normalization.
- `sha256_file(path: Path) -> str` performs chunked binary SHA-256; `is_strict_utc(value: object) -> bool` requires exact `YYYY-MM-DDTHH:MM:SSZ` round trip.
- `validate_openapi_document(document: dict) -> None` validates the approved local OpenAPI subset and all local `$ref` targets.
- `evaluate_version_envelope(case: dict, document: dict) -> str` will be completed by the later fixture task; it may exist as an importable stub only if current tests do not invoke it.

**TDD steps:**

1. First write the two failing tests below, then run `python -m unittest tests.interface_contract.test_openapi_version -v`. The expected RED failure is missing module/document, not a test typo.

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

2. Implement the smallest code to pass. The document root is exactly `openapi`, `info`, `paths`, `components`; components include `RequestIdHeader`, `Identifier`, `ApiVersion`, `Error`, `ErrorEnvelope`, and `SuccessEnvelope`. Every operation has the exact path/method/operationId above, references the request-ID header, and exposes only JSON responses. Endpoint-specific data schemas are a later task.

3. `validate_openapi_document` must exact-check root fields, OpenAPI and info versions, expected operation catalog, local reference resolution, component presence, and recursively closed component object schemas. Use `API_VERSION_UNSUPPORTED` for wrong versions and `API_SCHEMA_INVALID` for the remaining structure faults.

4. Re-run `python -m unittest tests.interface_contract.test_openapi_version.OpenApiDocumentTests -v`; it must pass with two tests and no network/external process calls. Then run `git diff --check`; leave all files unstaged.

**Report:** Write a full report to `artifacts/reviews/w3-1-task-1-report.md` containing changed files, RED and GREEN command/output evidence, self-review, and concerns. Return only status, one-line test summary, concerns, and report path. Do not commit.
