# W3-1 Task 1 implementation report

## Scope and changed files

- `tools/interface_contract/__init__.py` — package marker.
- `tools/interface_contract/common.py` — stable `ContractError`, JSON loading,
  exact-field checking, chunked SHA-256, and strict UTC helpers.
- `tools/interface_contract/openapi_contract.py` — closed local OpenAPI subset
  validator and later-fixture import stub.
- `contracts/forgeops-api/1.0/openapi.yaml` — UTF-8 JSON-compatible OpenAPI
  3.1 document for the five approved operations.
- `tests/interface_contract/__init__.py` — test package marker.
- `tests/interface_contract/test_openapi_version.py` — required document and
  request-ID-header tests.
- `artifacts/reviews/w3-1-task-1-report.md` — this report.

No WBS/RTM, design, plan, Git metadata, or pre-existing user files were
modified. No server, listener, database, authentication, SSE/WebSocket
transport, network call, staging, commit, push, or PR was created.

## TDD evidence

### RED

Command:

```text
python -m unittest tests.interface_contract.test_openapi_version -v
```

Observed output (exit code 1):

```text
test_openapi_version (unittest.loader._FailedTest.test_openapi_version) ... ERROR

ERROR: test_openapi_version (unittest.loader._FailedTest.test_openapi_version)
ImportError: Failed to import test module: test_openapi_version
...
from tools.interface_contract.common import load_json
ModuleNotFoundError: No module named 'tools.interface_contract'

Ran 1 test in 0.000s
FAILED (errors=1)
```

This is the expected missing-module failure, not a test typo.

### GREEN

Command:

```text
python -m unittest tests.interface_contract.test_openapi_version.OpenApiDocumentTests -v
```

Observed output (exit code 0):

```text
test_document_has_exact_version_and_operations (...) ... ok
test_every_operation_requires_request_id_header (...) ... ok

Ran 2 tests in 0.000s
OK
```

### Whitespace and staging check

Command:

```text
git diff --check; git status --short
```

Observed output (exit code 0): `git diff --check` produced no whitespace
diagnostics. `git status --short` showed the created contract, tool, and test
paths as untracked and no staged paths. It also continued to show the
pre-existing untracked W3 brief/design materials, which were preserved.

## Self-review

- The OpenAPI root is exactly `openapi`, `info`, `paths`, and `components`.
- The document and validator lock `openapi` to `3.1.0`, `info.version` to
  `1.0.0`, and envelope `api_version` to literal `1.0`.
- The operation catalog is limited to the five required method/path/operationId
  tuples. Every operation references `RequestIdHeader`, and every response uses
  only `application/json` content.
- Component objects are closed with `additionalProperties: false`; the
  validator rejects object schemas that are not closed and composed schemas
  lacking `unevaluatedProperties: false`. It also resolves every `$ref` locally.
- The `Error` code enum contains exactly the six required stable API categories.
- Helpers use stable `ContractError.code` values and perform no normalization.

## Concerns

- Endpoint-specific request and response data schemas are deliberately not
  defined in this task; the success envelope currently contains only the
  required `api_version` field.
- `evaluate_version_envelope` is an intentional importable `NotImplementedError`
  stub for the later fixture task, as authorized by this task brief.

## Review correction: path parameters and envelope structures

### Changed files

- `contracts/forgeops-api/1.0/openapi.yaml` — added the required inline
  `task_id`/`run_id` path parameters for each templated path, preserving the
  required `X-Request-ID` header parameter on all five operations.
- `tools/interface_contract/openapi_contract.py` — validates exact path
  parameter lists; exact `Error`, `ErrorEnvelope`, and `SuccessEnvelope`
  schemas; the six stable error categories; and `ApiVersion` reference wiring
  in both envelopes.
- `tests/interface_contract/test_openapi_version.py` — added focused negative
  tests for missing template parameters, a missing error category, and invalid
  envelope API-version references.
- `artifacts/reviews/w3-1-task-1-report.md` — appended this correction record.

### RED

Command:

```text
python -m unittest tests.interface_contract.test_openapi_version.OpenApiDocumentTests -v
```

Observed output (exit code 1):

```text
Ran 5 tests in 0.002s

FAILED (failures=4)
```

The four expected failures were all `AssertionError: ContractError not raised`:
one for a missing templated-path parameter, one for a removed stable error
category, and one each for invalid `api_version` wiring in `ErrorEnvelope` and
`SuccessEnvelope`.

### GREEN

Command:

```text
python -m unittest tests.interface_contract.test_openapi_version.OpenApiDocumentTests -v
```

Observed output (exit code 0):

```text
test_document_has_exact_version_and_operations (...) ... ok
test_envelopes_require_api_version_schema_wiring (...) ... ok
test_error_schema_rejects_missing_stable_category (...) ... ok
test_every_operation_requires_request_id_header (...) ... ok
test_path_templates_require_matching_path_parameter (...) ... ok

Ran 5 tests in 0.001s
OK
```

### Correction self-review and concerns

- Each path template now has exactly its matching required `in: path`
  parameter using the `Identifier` schema; `POST /v1/tasks` correctly has no
  path parameter.
- The validator compares the error and both envelope schemas to their complete
  approved structures, including closed-object fields, stable code ordering,
  and references to `ApiVersion` (`const: "1.0"`).
- No runtime feature, WBS/RTM, staging, commit, push, PR, network call, or
  external side effect was added.
- Concern: none for this correction scope. Endpoint-specific data schemas and
  the version-envelope fixture evaluator remain intentionally deferred to
  their designated tasks.
