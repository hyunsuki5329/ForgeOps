# W3-3 Task 2 Implementation Report

## Scope

Implemented only Task 2, `Enforce stream, canonical sequence, revision, and state-event rules`, from the approved W3-3 plan.

The implementation remains in-memory. It does not add a broker, append store, filesystem artifact reader, replay/runtime behavior, network access, WBS/RTM update, Git operation, credential access, or external side effect.

## Conflict resolution

The plan text described `STATE_ACCEPTED` as a phase, but the approved Main event contract defines the phase catalog exactly as `NORMALIZE|DISCOVER|EXECUTE|VERIFY|DECIDE|GATE`.

The parent orchestrator resolved the conflict as follows:

- preserve the exact Main phase catalog and the existing closed event schema;
- identify state-accept semantics only by `canonical_event.code == "STATE_ACCEPTED"`;
- treat `phase` as lifecycle stage and `code` as canonical event meaning.

No schema change was made.

## Changed resources

- `tools/interface_contract/event_contract.py`
  - Adds `AppendSpy`, `validate_event_stream`, and `validate_revisions_and_state_events`.
  - Requires a non-empty single-run/single-stream record list whose `stream_seq` is exactly `1..N`.
  - Requires canonical `seq` values to be strictly increasing without assigning or rewriting them.
  - Requires the trusted source revision map to cover exactly the stream event IDs, match every `accepted_revision`, and never decrease in stream order.
  - Allows at most one `STATE_ACCEPTED` code per accepted revision and requires its canonical actor to be `main`.
  - Performs all validation before observing append calls, so every rejection leaves `AppendSpy.calls == 0`.
- `fixtures/forgeops-event-contract/suite.json`
  - Adds negative cases for stream sequence reuse, skip, decrease, cross-run mixing, canonical sequence reuse/decrease, stale/decreasing revisions, duplicate state acceptance, and Work-owned state acceptance.
  - Every negative case declares one stable category and `expected_append_calls: 0`.
- `tests/interface_contract/test_event_wrapper.py`
  - Adds focused whole-stream tests for positive append observation, stream ordering, canonical sequence preservation, revision parity/progression, Main-owned state acceptance, stable rejection categories, and zero append on every invalid fixture.

## TDD evidence

### RED

Command:

`python -m unittest tests.interface_contract.test_event_wrapper.EventStreamTests -v`

Observed result before production implementation: exit code 1; seven tests failed at the expected missing `AppendSpy`/whole-stream validator boundary. The fixture JSON parsed successfully before this run.

### GREEN

Command:

`python -m unittest tests.interface_contract.test_event_wrapper.EventStreamTests -v`

Observed result after the minimal implementation: exit code 0; 7/7 tests passed.

## Fresh verification evidence

- `python -m unittest tests.interface_contract.test_event_wrapper -v`
  - Exit code 0; 17/17 W3-3 tests passed.
- `python -m unittest discover -s tests/interface_contract -p "test_*.py" -v`
  - Exit code 0; 42/42 interface-contract tests passed.
- `python -m json.tool fixtures/forgeops-event-contract/suite.json`
  - Exit code 0; fixture JSON is valid.
- `python -m py_compile tools/interface_contract/event_contract.py tests/interface_contract/test_event_wrapper.py`
  - Exit code 0.
- `git diff --check`
  - Exit code 0; no whitespace error reported.
- `rg -n "WBS-007" docs/project/wbs.md`
  - Confirms `WBS-007` remains `WBS_NOT_STARTED` pending integrated W3 evidence.
- Phase/schema inspection
  - Confirms the schema phase catalog was not changed and `STATE_ACCEPTED` is interpreted only from `canonical_event.code`.

## Deferred scope

VG-004 aggregation, durable storage/runtime behavior, WBS/RTM transitions, and any Git or external operation remain outside this task.

## Independent review remediation: stream identity tuple

### Root cause

The initial whole-stream validator checked `(run_id, stream_id)` across records and checked wrapper/canonical task and correlation identity only within each individual record. It did not compare `task_id` or `correlation_id` between records, so a single run stream could mix tasks or correlations while every record remained internally valid.

### Remediation RED

Added `task-mix` and `correlation-mix` negative fixtures. Each keeps wrapper/canonical identity internally consistent, expects `EVENT_IDENTITY_MISMATCH`, and declares `expected_append_calls: 0`.

Command:

`python -m unittest tests.interface_contract.test_event_wrapper.EventStreamTests.test_stream_identity_tuple_is_exact_and_never_appends_on_mismatch -v`

Observed result before the validator fix: exit code 1; both subtests failed because no `ContractError` was raised.

### Minimal fix and GREEN

The validator now requires one exact `(task_id, correlation_id)` pair before applying its existing one exact `(run_id, stream_id)` check. Together these checks require one exact `(task_id, run_id, correlation_id, stream_id)` tuple across the stream. Identity mismatch is detected before append observation.

Command:

`python -m unittest tests.interface_contract.test_event_wrapper.EventStreamTests.test_stream_identity_tuple_is_exact_and_never_appends_on_mismatch -v`

Observed result after the fix: exit code 0; the focused test passed, including `AppendSpy.calls == 0` for both fixtures.

Command:

`python -m unittest tests.interface_contract.test_event_wrapper.EventStreamTests -v`

Observed result after the fix: exit code 0; 8/8 stream tests passed.

### Approved plan correction

Updated only the stale Task 2 interface wording in `docs/superpowers/plans/2026-07-23-w3-durable-event-wrapper.md` to identify state acceptance by `canonical_event.code == "STATE_ACCEPTED"`. The exact Main phase enum remains unchanged.

### Post-remediation verification

- `python -m unittest tests.interface_contract.test_event_wrapper -v`
  - Exit code 0; 18/18 W3-3 tests passed.
- `python -m unittest discover -s tests/interface_contract -p "test_*.py" -v`
  - Exit code 0; 43/43 interface-contract tests passed.
- Fixture JSON parse, Python compile, and `git diff --check`
  - Exit code 0 for each command.
