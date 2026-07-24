# W3-3 Task 1 Implementation Report

## Scope

Implemented only Task 1, “Define the wrapper schema and Main ownership boundary,” from the approved W3-3 plan. The change is limited to a closed durable event wrapper, one-record validation, the fixture catalog, and focused tests.

No broker, append store, replay/runtime behavior, WBS/RTM update, Git operation, network access, credential access, or external side effect was introduced.

## Changed resources

- `contracts/forgeops-event/1.0/schema.json`
  - Defines the closed `forgeops.event` 1.0 wrapper.
  - Closes the canonical event and provenance objects.
  - Constrains positive sequence values, non-negative accepted revisions, strict UTC shape, identifiers, actor/phase/severity enums, and lowercase SHA-256 provenance hashes.
- `tools/interface_contract/event_contract.py`
  - Adds `validate_event_record(record, schema) -> None`.
  - Applies stable fail-closed order: schema, wrapper/canonical identity, Main ownership, strict UTC semantics, then evidence-reference semantics.
  - Does not assign or rewrite canonical `seq`, accepted revision, or any identity.
- `fixtures/forgeops-event-contract/suite.json`
  - Adds the approved positive catalog: first append, consecutive append, revision increase, Main-normalized part actor, Main-normalized work actor, and Main actor.
  - Adds negative mutations for identity mismatch, non-Main source, missing/bad source hash, duplicate/empty evidence reference, forbidden raw field, and invalid timestamp.
  - Keeps source revisions as validation context rather than serializing them into wrapper records.
- `tests/interface_contract/test_event_wrapper.py`
  - Covers valid MainDecision wrappers, Main ownership, exact wrapper/canonical identity, full positive/negative fixture records, and closure of every object boundary.

## TDD evidence

### RED

Command:

`python -m unittest tests.interface_contract.test_event_wrapper -v`

Observed result: exit code 1, six failures. Every failure was the expected `event validator is not implemented` assertion before production files existed.

### GREEN

Command:

`python -m unittest tests.interface_contract.test_event_wrapper.EventRecordTests -v`

Observed result: exit code 0, six tests passed.

## Regression and structural evidence

- `python -m unittest discover -s tests/interface_contract -p "test_*.py" -v`
  - Exit code 0; 31 tests passed.
- JSON parse check for the event schema and fixture suite
  - Exit code 0; output `JSON_OK`.
- `git diff --check`
  - Exit code 0; no whitespace errors reported.

## Deferred to W3-3 Task 2

Stream sequencing, canonical sequence progression, source-revision matching, state-event revision rules, append-spy behavior, and whole-stream validation remain outside this task and are not claimed here.

## Reviewer finding remediation

### Root causes

- The phase schema copied the broader harness phase list and therefore admitted `PLAN`/`APPROVE` while omitting the wrapper-specific `NORMALIZE` phase.
- `evidence_refs` constrained only the JSON type, so arbitrary strings could cross the durable boundary; only empty and duplicate values were rejected semantically.
- `EVENT_PROVENANCE_INVALID` was declared but no trusted source MainDecision context entered `validate_event_record`, leaving the category unreachable.

### Remediation RED

Command:

`python -m unittest tests.interface_contract.test_event_wrapper.EventRecordTests -v`

Observed result: exit code 1 with four expected failures: exact phase catalog mismatch, `NORMALIZE` rejected as `EVENT_SCHEMA_INVALID`, missing evidence-reference grammar, and missing `source_main_decisions` validation context.

### Minimal fixes

- Made the phase enum exactly `NORMALIZE|DISCOVER|EXECUTE|VERIFY|DECIDE|GATE` and added a valid `NORMALIZE` record test.
- Defined the bounded opaque evidence-reference grammar as `^EVID-[A-Za-z0-9][A-Za-z0-9._:-]{0,122}$`, with a six-character minimum and 128-character maximum. Schema errors confined to evidence-reference items map to `EVENT_REFERENCE_INVALID`; duplicate detection remains case-sensitive and exact.
- Added tests rejecting whitespace, oversized references, raw prompt text, log text, and private-content text.
- Added optional trusted `source_main_decisions` fixture context keyed by `source_ref`. When supplied, its closed metadata (`source_kind`, task identity, correlation identity, and content SHA-256) must exactly match the durable record or validation returns `EVENT_PROVENANCE_INVALID`. No source metadata was added to the wrapper itself.

### Remediation GREEN

- Phase tests: 2/2 passed.
- Evidence grammar and existing negative-catalog tests: 2/2 passed.
- Provenance mismatch test: 1/1 passed.
- Full `EventRecordTests`: 10/10 passed.
