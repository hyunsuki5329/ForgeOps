# W3-1 Task 2 Report — Version, envelope, identity, and closed objects

## Outcome

Implemented the closed version-envelope fixture catalog and ordered evaluator.
The evaluator keeps the five Task 1 operation IDs and existing stable API
categories unchanged. It adds no endpoint-specific OpenAPI data schemas or
external effects.

## Changed files

- `fixtures/forgeops-api/version-envelope-suite.json` — closed 16-case catalog
  with the required root/case fields, IDs, and expected categories.
- `tools/interface_contract/openapi_contract.py` — ordered evaluator, suite
  runner, request-ID validation, endpoint closure, identity checks, and
  component-reference check.
- `tests/interface_contract/test_openapi_version.py` — catalog ordering,
  version-priority, public-safe result, and version type/exactness tests.
- `artifacts/reviews/w3-1-task-2-report.md` — this report.

## TDD evidence

### RED 1 — required Task 2 behavior absent

Command:

```text
python -m unittest tests.interface_contract.test_openapi_version -v
```

Observed result: exit `1`; the test module failed to import because
`run_version_envelope_suite` was absent from `openapi_contract.py`. This was
the intended pre-implementation failure for the new public suite-runner
interface.

### GREEN 1 — catalog/evaluator implementation

Command:

```text
python -m unittest tests.interface_contract.test_openapi_version -v
```

Observed result: exit `0`; `Ran 8 tests`; `OK`. The catalog order, URI-version
priority over an unknown body field, and public-safe records all passed.

### RED/GREEN 2 — response API version exactness and type

RED command:

```text
python -m unittest tests.interface_contract.test_openapi_version -v
```

Observed result: exit `1`; the exact-response-version test initially failed
because no `ContractError` was raised. After adding the exact response version
check, the non-string response version test correctly produced a second RED:
the evaluator returned `API_VERSION_UNSUPPORTED` where the required type error
was `API_SCHEMA_INVALID`.

GREEN command:

```text
python -m unittest tests.interface_contract.test_openapi_version -v
```

Observed result: exit `0`; `Ran 10 tests`; `OK`.

### RED/GREEN 3 — body API version type

RED command:

```text
python -m unittest tests.interface_contract.test_openapi_version -v
```

Observed result: exit `1`; a non-string body version returned
`API_VERSION_UNSUPPORTED` instead of `API_SCHEMA_INVALID`.

GREEN command:

```text
python -m unittest tests.interface_contract.test_openapi_version -v
```

Observed result: exit `0`; `Ran 10 tests`; `OK`.

## Catalog results

The suite runner returned only public records with exactly
`id`, `kind`, `expected`, `actual`, and `status`. All 16 records have
`status=PASSED`:

| Case | Actual |
| --- | --- |
| valid-create-task | PASSED |
| valid-get-task | PASSED |
| valid-get-run | PASSED |
| valid-list-run-events | PASSED |
| valid-get-run-manifest | PASSED |
| unsupported-uri-major | API_VERSION_UNSUPPORTED |
| unsupported-body-version | API_VERSION_UNSUPPORTED |
| missing-request-header | API_SCHEMA_INVALID |
| invalid-request-id-type | API_SCHEMA_INVALID |
| request-id-header-body-mismatch | API_IDENTITY_MISMATCH |
| response-request-id-mismatch | API_IDENTITY_MISMATCH |
| endpoint-unknown-field | API_SCHEMA_INVALID |
| endpoint-missing-required-field | API_SCHEMA_INVALID |
| endpoint-wrong-field-type | API_SCHEMA_INVALID |
| path-body-identity-mismatch | API_IDENTITY_MISMATCH |
| response-data-error-conflict | API_SCHEMA_INVALID |

## Final validation

```text
git diff --check
```

Observed result: exit `0` with no whitespace errors. No staging, commit, push,
PR, WBS/RTM update, server, or external effect was performed.

## Self-review

- Validation order is document/OpenAPI, URI/body version, common envelope,
  control-field scan, endpoint closure, exact identity, then component
  references.
- Version errors precede endpoint unknown-field errors.
- Request IDs and path/body identities are checked as non-empty printable ASCII
  literals with direct string equality; no trimming or case folding occurs.
- Responses require exactly one `data` or `error` branch.
- Public records intentionally omit body and header values.
- The OpenAPI document remains unchanged, preserving Task 1 and reserving
  endpoint-specific schema work for W3-2.

## Concerns

No blocking concerns. The control scan deliberately covers only explicit
top-level forbidden control literals for this task; the broader data/control
boundary catalog remains reserved for W3-2.

## Review-fix addendum

### Scope

- Identifier validation now accepts every non-empty ASCII string, including
  spaces and leading/trailing spaces. Equality remains direct Python string
  equality, with no trimming or case folding.
- The test suite now independently fixes the full ordered ID/category mapping
  for all 16 fixture cases. Fixture and evaluator changes cannot make the
  public-safe runner test pass by drifting together.

### TDD evidence

RED command:

```text
python -m unittest tests.interface_contract.test_openapi_version -v
```

Observed result: exit `1`; the new identifier test supplied space-containing
non-empty ASCII literals and received `API_SCHEMA_INVALID`, proving the former
printable-non-space predicate was too narrow. The independent 16-case
ID/category assertion passed against the current catalog.

Minimal implementation: `_is_ascii_identifier` now requires only a non-empty
Python string and `str.isascii()`; it neither trims nor transforms the value.

GREEN command:

```text
python -m unittest tests.interface_contract.test_openapi_version -v
```

Observed result: exit `0`; `Ran 11 tests`; `OK`. The same test also verifies
that a response ID differing only by omitted spaces produces
`API_IDENTITY_MISMATCH`, preserving ordinal-exact comparison.
