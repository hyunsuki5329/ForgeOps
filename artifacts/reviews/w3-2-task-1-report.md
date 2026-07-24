# W3-2 Task 1 Report — Closed API data/control boundary

## Outcome

Implemented the endpoint-specific closed OpenAPI schemas and the Product Task
Contract boundary. The validator reuses the W3-1 document, version, envelope,
request-ID, identifier, and identity checks before applying the new forbidden
control, endpoint, Draft 2020-12 product-contract, non-grant, public-response,
identity, and reference checks. It is an in-memory validator only and makes no
dispatcher, process, network, credential, or store calls.

## Changed files

- `contracts/forgeops-api/1.0/openapi.yaml` — endpoint-specific request,
  success-data, event-page reference, manifest reference, and response schemas.
- `tools/interface_contract/openapi_contract.py` — `EffectSpies`, W3-1
  projection, Product Task Contract validation, non-grant/public-response
  guards, endpoint schema validation, and exact identity/reference checks.
- `fixtures/forgeops-api/data-control-suite.json` — ordered 28-case catalog
  with five complete positive cases and explicit single-mutation negatives.
- `tests/interface_contract/test_api_boundary.py` — required initial TDD tests,
  exact catalog/schema assertions, stable-category evaluation, and zero-effect
  assertions.
- `artifacts/reviews/w3-2-task-1-report.md` — this report.

## TDD evidence

### RED — required boundary interface absent

Command:

```text
python -m unittest tests.interface_contract.test_api_boundary -v
```

Observed result: exit `1`; `Ran 3 tests`; `FAILED (failures=3)`. Each required
test failed with the intended assertion `EffectSpies boundary interface is not
implemented`. The failing behaviors were valid create-task acceptance,
forbidden `authority` priority over an ordinary unknown field, and Product Task
Contract unknown-field rejection.

After adding the full catalog assertions but before implementation, the same
command remained RED because `EffectSpies`, `validate_api_case`, and
`CreateTaskRequest` were absent. No implementation existed during either RED
observation.

### GREEN — focused W3-2 boundary suite

Command:

```text
python -m unittest tests.interface_contract.test_api_boundary -v
```

Observed result: exit `0`; `Ran 7 tests`; `OK`.

### Compatibility GREEN — W3-1 plus W3-2

Command:

```text
python -m unittest tests.interface_contract.test_openapi_version tests.interface_contract.test_api_boundary -v
```

Observed result: exit `0`; `Ran 18 tests`; `OK`. All eleven prior W3-1 tests
and all seven W3-2 Task 1 tests passed together.

### Final workspace check

Command:

```text
git diff --check
```

Observed result: exit `0` with no reported whitespace errors. The five scoped
files, including this report, remain untracked/unstaged with the rest of the
preserved W3 working tree; no Git mutation was performed.

## Fixture catalog result

All 28 catalog entries produced their independently fixed expected category.
The five positives passed:

- `create-task-valid`
- `get-task-valid`
- `get-run-valid`
- `list-run-events-valid`
- `get-run-manifest-valid`

The 23 negatives covered unsupported/missing envelope values; Product Task
Contract unknown, missing, and wrong-type fields; all nine forbidden top-level
control literals; copied product `budget` and `approval_policy`; task and run
identity mismatch; dangling event and manifest references; simultaneous
`data`/`error`; and raw credential/private response fields. Every negative
observed exactly these counters:

```text
dispatcher_calls=0
process_calls=0
network_calls=0
credential_calls=0
store_calls=0
```

## Self-review

- `POST /v1/tasks` is closed over exactly `api_version`, `request_id`, and
  `task_contract`; its Product Task Contract reference is exactly
  `../../product-task-contract/1.0/schema.json`.
- The Product Task Contract's `budget` and `approval_policy` validate as
  ordinary untrusted product fields. Only an attempted derived/canonical copy
  is rejected as `API_CONTROL_FIELD_FORBIDDEN`.
- Version and common-envelope checks still run through the W3-1 evaluator.
  On a supported request, the top-level forbidden scan precedes closed-body
  validation, so a forbidden control field plus an ordinary unknown field
  deterministically returns `API_CONTROL_FIELD_FORBIDDEN`.
- `CreateTaskData`, `TaskData`, and `RunData` contain only the brief's approved
  fields. Run mode is the closed four-value enum. Create links are closed over
  only `task` and `run`.
- Event pages are bounded to 100 opaque event references, while event-stream
  and manifest values resolve through case-local same-task/same-run context.
  No W3-3 event-wrapper or W3-4 manifest fields are duplicated.
- Response traversal rejects raw credential/private/control keys before a
  public projection could be accepted.
- `validate_api_case` never increments or otherwise accesses an effect surface;
  the five counters remain at their initialized zero values on all paths.
- No server, handler, queue, persistence, approval UI, runtime authorization,
  WBS/RTM update, staging, commit, push, PR, or external effect was introduced.

## Concerns

No blocking concerns. Event and manifest responses intentionally expose only
bounded opaque references in this task; W3-3 and W3-4 remain responsible for
the referenced record schemas and their deeper semantics.

## Review-fix addendum — forbidden-control priority with invalid product identity

The reviewer found that a create request containing top-level `authority` and
a Product Task Contract missing `task_id` returned `API_SCHEMA_INVALID`. Root
cause tracing showed that `_legacy_envelope_case` copied `task_contract.task_id`
into the W3-1 compatibility projection before the required top-level forbidden
scan. That made unvalidated product data affect error ordering.

### RED

Command:

```text
python -m unittest tests.interface_contract.test_api_boundary.ApiBoundaryInitialTddTests.test_forbidden_control_precedes_missing_product_task_identity -v
```

Observed result: exit `1`; `Ran 1 test`; `FAILED (failures=1)`. The regression
expected `API_CONTROL_FIELD_FORBIDDEN` but observed `API_SCHEMA_INVALID`.

### Minimal fix

The W3-1 compatibility projection now uses a fixed internal placeholder for
its legacy create-task identity field. It no longer reads any identity from the
unvalidated Product Task Contract. The real contract identity remains subject
to Draft 2020-12 validation and the later exact request/response identity check.

### GREEN

Focused regression command:

```text
python -m unittest tests.interface_contract.test_api_boundary.ApiBoundaryInitialTddTests.test_forbidden_control_precedes_missing_product_task_identity -v
```

Observed result: exit `0`; `Ran 1 test`; `OK`.

Compatibility command:

```text
python -m unittest tests.interface_contract.test_openapi_version tests.interface_contract.test_api_boundary -v
```

Observed result: exit `0`; `Ran 19 tests`; `OK`. The regression also verifies
that all five effect counters remain zero on this mixed-invalid rejection.
