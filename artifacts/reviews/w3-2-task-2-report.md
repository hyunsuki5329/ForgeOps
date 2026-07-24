# W3-2 Task 2 Implementation Report

## Scope

Implemented only Task 2, “Prove non-grant behavior, public projections, and zero effects,” from the approved W3-2 plan.

Changed resources:

- `tools/interface_contract/openapi_contract.py`
- `tests/interface_contract/test_api_boundary.py`
- `artifacts/reviews/w3-2-task-2-report.md`

No runtime API server, persistence, WBS/RTM update, staging, commit, push, network call, credential access, or external effect was performed.

## TDD RED evidence

Command:

```text
python -m unittest tests.interface_contract.test_api_boundary.ApiBoundaryCatalogTests.test_product_approval_never_becomes_canonical_approval tests.interface_contract.test_api_boundary.ApiBoundaryCatalogTests.test_run_references_resolve_in_same_task_and_run tests.interface_contract.test_api_boundary.ApiBoundaryCatalogTests.test_public_projection_rejects_external_url_without_effects tests.interface_contract.test_api_boundary.ApiBoundaryCatalogTests.test_suite_runner_returns_closed_records_counts_and_zero_effects -v
```

Observed result: exit code 1, four tests run. The two pre-existing behaviors passed. The new external-URL projection test failed because no `ContractError` was raised, and the suite-runner test errored because `run_api_boundary_suite` did not exist. These were the intended missing Task 2 behaviors.

## Minimal implementation

- Public response traversal now rejects string values containing an external URL form (`://`) as `API_CONTROL_FIELD_FORBIDDEN` before any effect surface is touched.
- Added closed fixture materialization for the approved data/control mutation catalog.
- Added `run_api_boundary_suite(document, product_schema, suite)`, returning exact case records with `id`, `kind`, `expected`, `actual`, `status`, and the five zero-valued `spy_calls` counters, plus integer `passed`/`failed` counts.
- Fixture identifiers and response/reference values are compared as supplied; no trimming or case folding was added.

## TDD GREEN evidence

Focused command: same four-test command used for RED.

Observed result: exit code 0, four tests run, all passed.

Regression command:

```text
python -m unittest tests.interface_contract.test_openapi_version tests.interface_contract.test_api_boundary -v
```

Observed result: exit code 0, 23 tests run, all passed. The full W3-2 catalog retained stable expected categories, and all negative cases retained five zero effect counters.

Review command:

```text
git diff --check
```

Observed result: exit code 0 with no reported whitespace errors.

## Residual risk

The suite materializer intentionally supports only the mutation literals present in the approved W3-2 fixture catalog. Unknown mutations fail closed as `API_SCHEMA_INVALID`. Integrated VG-004 registration and WBS/RTM evidence updates remain outside this task and must wait for the later integrated verification task.

## Important review finding correction

The review found that `run_api_boundary_suite` returned `PASSED` when the expected error code matched even if an effect counter differed, and that malformed or missing negative-case `expected_spy_calls` contracts were not validated.

### Review RED evidence

Command:

```text
python -m unittest tests.interface_contract.test_api_boundary.ApiBoundaryCatalogTests.test_suite_runner_requires_exact_negative_expected_spy_contract tests.interface_contract.test_api_boundary.ApiBoundaryCatalogTests.test_suite_runner_marks_observed_spy_mismatch_failed -v
```

Observed result: exit code 1. Four subtests showed that a missing counter, an extra counter, a boolean counter, and a negative counter were accepted. The observed-effect regression injected `network_calls=1`; the actual error code still matched, so the record incorrectly remained `PASSED`.

### Review fix

- Every negative fixture case must provide `expected_spy_calls` with exactly the five approved keys.
- Each counter must be a non-boolean integer greater than or equal to zero.
- The runner captures the exact observed five-counter record and marks a negative case `FAILED` unless both its error code and its complete spy record match expectations.
- The public result record remains exactly six fields: `id`, `kind`, `expected`, `actual`, `status`, and `spy_calls`.

### Review GREEN evidence

The same two-test command completed with exit code 0 and both tests passed.

Fresh regression command:

```text
python -m unittest tests.interface_contract.test_openapi_version tests.interface_contract.test_api_boundary -v
```

Observed result: exit code 0, 25 tests run, all passed.
