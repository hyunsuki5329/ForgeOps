### Task 1: Close endpoint schemas and Product Task Contract boundary

**Files:** modify `contracts/forgeops-api/1.0/openapi.yaml`, modify `tools/interface_contract/openapi_contract.py`, create `fixtures/forgeops-api/data-control-suite.json`, create `tests/interface_contract/test_api_boundary.py`.

**Binding constraints:**

- Reuse W3-1 `ContractError`, version/envelope validation, request-ID, identifier, and exact error ordering.
- `POST /v1/tasks` body is exactly `api_version`, `request_id`, `task_contract`; `task_contract` references `contracts/product-task-contract/1.0/schema.json`.
- Product `budget`/`approval_policy` are untrusted constraints, never canonical authority/capability/approval/policy/runtime budget/accepted state.
- Reject top-level `authority`, `capabilities`, `runtime_policy`, `accepted_state`, `approval_token`, `nonce`, `credentials`, `tools`, and `commands` as `API_CONTROL_FIELD_FORBIDDEN` before closed-body validation.
- Add closed CreateTaskData (`task_id`, `artifact_id`, `artifact_version`, `product_state="CREATED"`, `contract_sha256`, `links` with only `task`/`run`), TaskData projection (`status`, `revision`, `last_event_seq`), RunData (`task_id`, `run_id`, `correlation_id`, `run_mode`, `status`, `accepted_revision`, `event_stream_ref`, `manifest_ref`), and finite event/manifest response references without duplicating W3-3/W3-4 fields. Run modes are `PRIMARY|AUDIT_REPLAY|COUNTERFACTUAL|REEXECUTE`.
- Maintain zero calls on EffectSpies (`dispatcher_calls`, `process_calls`, `network_calls`, `credential_calls`, `store_calls`) for every negative. No server, persistence, approval UI, runtime authorization, WBS/RTM, Git, or external effects.

**Interfaces:**

- `EffectSpies` has the five integer counters initialized to zero.
- `validate_api_case(case: dict, document: dict, product_schema: dict, spies: EffectSpies) -> str` returns `PASSED` or raises `ContractError`.
- Suite root exactly `{suite_id, suite_version, cases}` with `suite_id="forgeops-api-data-control"`, `suite_version="1.0"`.

**TDD:**

1. First add tests that valid createTask succeeds, forbidden `authority` plus ordinary unknown produces `API_CONTROL_FIELD_FORBIDDEN`, and unknown product-contract field produces `API_SCHEMA_INVALID`. Run `python -m unittest tests.interface_contract.test_api_boundary -v` and record RED.
2. Create closed endpoint schemas and fixture catalog. Include valid create/task/run/event-page/manifest cases; negatives for envelope and PTC unknown/missing/wrong type, every forbidden control literal, copied budget/approval control, task/run identity mismatch, dangling event/manifest reference, data+error, raw credential/private response. Every negative supplies expected stable category and zero spy counts.
3. Implement `validate_api_case`: run W3-1 evaluator, forbidden scan, endpoint schema, Draft202012 PTC validation for createTask, non-grant assertion, identity, and reference checks. Do not invoke any effect.
4. Re-run `python -m unittest tests.interface_contract.test_api_boundary -v` for GREEN, then `git diff --check`; leave changes unstaged.

**Report:** write `artifacts/reviews/w3-2-task-1-report.md` with RED/GREEN evidence, catalog result, changed files, self-review, concerns. Return short status only; no commit.
