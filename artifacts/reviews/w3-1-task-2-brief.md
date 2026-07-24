### Task 2: Prove version, envelope, identity, and closed-object behavior

**Files:**

- Create `fixtures/forgeops-api/version-envelope-suite.json`.
- Modify `tools/interface_contract/openapi_contract.py`.
- Modify `tests/interface_contract/test_openapi_version.py`.

**Binding constraints:**

- Keep the Task 1 five-operation API surface and exact stable API categories.
- Validate in this exact order: document/OpenAPI validity; URI/body version; common envelope required/type; forbidden control scan; endpoint closed object; identity exact match; component reference.
- All identifiers are non-empty ASCII literals compared ordinal-exactly, with no trimming or case folding.
- Mutation request `request_id` exactly matches the `X-Request-ID` header; all responses return the same `request_id`; response has exactly one of `data` or `error`.
- Public result records expose only `id`, `kind`, `expected`, `actual`, `status`; never raw body/header values.
- Do not add endpoint-specific data schemas, a server, external effects, WBS/RTM updates, staging, commits, pushes, or PRs.

**Required interfaces:**

- Suite root is exactly `{suite_id, suite_version, cases}`, ID `forgeops-api-version-envelope`, version `1.0`.
- Each case is exactly `{id, kind, uri_major, request_header, body, response, expected}`. `kind` is one of the five operation IDs. The body carries the endpoint's simple fixture input and any path identity required for cross-checks; it must remain data only.
- `run_version_envelope_suite(document: dict, suite: dict) -> list[dict]` returns only `{id, kind, expected, actual, status}`.
- `evaluate_version_envelope(case: dict, document: dict) -> str` returns `PASSED` or raises `ContractError`.

**Catalog IDs in this exact order:**

1. `valid-create-task`
2. `valid-get-task`
3. `valid-get-run`
4. `valid-list-run-events`
5. `valid-get-run-manifest`
6. `unsupported-uri-major`
7. `unsupported-body-version`
8. `missing-request-header`
9. `invalid-request-id-type`
10. `request-id-header-body-mismatch`
11. `response-request-id-mismatch`
12. `endpoint-unknown-field`
13. `endpoint-missing-required-field`
14. `endpoint-wrong-field-type`
15. `path-body-identity-mismatch`
16. `response-data-error-conflict`

The first five expect `PASSED`. Expected categories for the negatives, in order, are `API_VERSION_UNSUPPORTED`, `API_VERSION_UNSUPPORTED`, `API_SCHEMA_INVALID`, `API_SCHEMA_INVALID`, `API_IDENTITY_MISMATCH`, `API_IDENTITY_MISMATCH`, `API_SCHEMA_INVALID`, `API_SCHEMA_INVALID`, `API_SCHEMA_INVALID`, `API_IDENTITY_MISMATCH`, `API_SCHEMA_INVALID`.

**TDD steps:**

1. First add tests for exact ID ordering, version priority over unknown body field, and public-safe result records. Run `python -m unittest tests.interface_contract.test_openapi_version -v` and record a meaningful RED failure caused by the absent suite/evaluator behavior.
2. Add the closed fixture catalog above. Do not include raw credentials, private text, stack traces, or effect instructions.
3. Implement the ordered evaluator. `api_version` must be exactly `1.0`; URI major must be `v1`. Required/type checks occur before endpoint closure; control scan must preserve `API_CONTROL_FIELD_FORBIDDEN` for an explicit top-level forbidden literal even though W3-2 adds full data/control cases; then apply generic endpoint shape and exact identity checks. A case with version and unknown field must report `API_VERSION_UNSUPPORTED`.
4. `validate_request_id` rejects absent/non-string/empty/non-ASCII IDs and requires header/body/response exact equality. `validate_endpoint_shape` accepts no unknown fields, rejects missing/wrong type according to the fixture schema, and enforces data xor error.
5. Run `python -m unittest tests.interface_contract.test_openapi_version -v` and record GREEN; every catalog case must match its expected category and results must have no raw input fields. Run `git diff --check` and leave all changes unstaged.

**Report:** Write a full report to `artifacts/reviews/w3-1-task-2-report.md` with changed files, RED/GREEN command/output evidence, catalog results, self-review, and concerns. Return status, one-line test summary, concerns, and report path. Do not commit.
