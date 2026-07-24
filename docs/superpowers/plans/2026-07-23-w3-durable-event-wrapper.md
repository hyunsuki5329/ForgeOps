# W3-3 Durable Event Wrapper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define and executable-test a closed durable wrapper that preserves Main-owned canonical events, stream ordering, accepted revision, and provenance.

**Architecture:** Use JSON Schema for shape and a focused Python semantic validator for cross-field identity, sequence, owner, revision, time, and reference rules. The validator is storage-free and evaluates complete fixture streams in memory so all invalid records stop before append.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `unittest`, JSON, SHA-256

## Global Constraints

- Main alone assigns canonical event `seq`; the wrapper never assigns or rewrites it.
- `stream_seq` is a separate durable ordering value that starts at 1 and increments exactly by 1 within one `stream_id` and run.
- Version 1.0 provenance requires `source_kind="MAIN_DECISION"`; Part/Work suggestions are accepted only after Main normalization and sequence assignment.
- Do not store raw prompts, request bodies, stdout/stderr, credentials, approval tokens, nonces, private payloads, or source event text.
- Reject invalid streams before any append/store spy call; public results contain only IDs, category, sequence, hash, and verdict.
- Do not implement a broker/store, replay execution, retention, encryption, Git commit/push/PR, or WBS/RTM update.

---

## File Structure

- Create `contracts/forgeops-event/1.0/schema.json`: closed wrapper, canonical event, and provenance schemas.
- Create `tools/interface_contract/event_contract.py`: shape and ordered semantic validation.
- Create `fixtures/forgeops-event-contract/suite.json`: exact positive/negative stream catalog.
- Create `tests/interface_contract/test_event_wrapper.py`: schema, ownership, ordering, revision, provenance, and zero-append tests.

### Task 1: Define the wrapper schema and Main ownership boundary

**Files:**

- Create: `contracts/forgeops-event/1.0/schema.json`
- Create: `tools/interface_contract/event_contract.py`
- Create: `fixtures/forgeops-event-contract/suite.json`
- Create: `tests/interface_contract/test_event_wrapper.py`

**Interfaces:**

- `validate_event_record(record: dict, schema: dict) -> None` validates one record.
- `validate_event_stream(records: list[dict], schema: dict, source_revisions: dict[str, int] | None = None, append_spy: AppendSpy | None = None) -> str` validates a whole stream and returns `PASSED`.
- `AppendSpy.calls: int` remains zero on every rejected fixture.
- Stable errors are exactly `EVENT_SCHEMA_INVALID`, `EVENT_IDENTITY_MISMATCH`, `EVENT_STREAM_OUT_OF_ORDER`, `EVENT_CANONICAL_SEQUENCE_INVALID`, `EVENT_REVISION_MISMATCH`, `EVENT_OWNER_INVALID`, `EVENT_PROVENANCE_INVALID`, `EVENT_REFERENCE_INVALID`, and `EVENT_TIMESTAMP_INVALID`.

- [ ] **Step 1: Write failing schema and ownership tests**

```python
def test_valid_main_decision_wrapper(self):
    validate_event_record(case_by_id("first-append")["records"][0], SCHEMA)

def test_part_suggestion_cannot_be_durable_source(self):
    record = deepcopy(case_by_id("first-append")["records"][0])
    record["provenance"]["source_kind"] = "PART_SUGGESTION"
    with self.assertRaisesRegex(ContractError, "EVENT_OWNER_INVALID"):
        validate_event_record(record, SCHEMA)

def test_wrapper_and_canonical_identity_are_exact(self):
    record = deepcopy(case_by_id("first-append")["records"][0])
    record["canonical_event"]["task_id"] = "TASK-case-variant"
    with self.assertRaisesRegex(ContractError, "EVENT_IDENTITY_MISMATCH"):
        validate_event_record(record, SCHEMA)
```

- [ ] **Step 2: Run tests and observe RED**

Run: `python -m unittest tests.interface_contract.test_event_wrapper -v`
Expected: FAIL because schema, fixture, and event validator do not exist.

- [ ] **Step 3: Write the closed event schema**

Require exactly `schema_id="forgeops.event"`, `schema_version="1.0"`, `event_id`, `task_id`, `run_id`, `correlation_id`, `stream_id`, positive `stream_seq`, strict-UTC-shaped `recorded_at`, non-negative `accepted_revision`, `canonical_event`, and `provenance`. Close `canonical_event` over `seq`, `task_id`, `correlation_id`, `actor`, `phase`, `attempt`, `severity`, `code`, `action`, `evidence_refs`; close provenance over `source_kind`, `source_ref`, 64-lowercase-hex `content_sha256`, and `recorder_id`.

- [ ] **Step 4: Implement one-record semantics**

```python
def validate_event_record(record, schema):
    errors = list(Draft202012Validator(schema).iter_errors(record))
    if errors:
        raise ContractError("EVENT_SCHEMA_INVALID")
    event = record["canonical_event"]
    if event["task_id"] != record["task_id"] or event["correlation_id"] != record["correlation_id"]:
        raise ContractError("EVENT_IDENTITY_MISMATCH")
    if record["provenance"]["source_kind"] != "MAIN_DECISION":
        raise ContractError("EVENT_OWNER_INVALID")
    if not is_strict_utc(record["recorded_at"]):
        raise ContractError("EVENT_TIMESTAMP_INVALID")
    if len(event["evidence_refs"]) != len(set(event["evidence_refs"])):
        raise ContractError("EVENT_REFERENCE_INVALID")
```

- [ ] **Step 5: Add the exact fixture catalog and pass record tests**

Positive cases include first append, consecutive append, revision increase, Main-normalized `part` actor, Main-normalized `work` actor, and Main actor. Each fixture case carries a closed `source_revisions` map from `event_id` to the accepted revision observed in its source MainDecision; this is validator context and is not serialized into the wrapper. Negative records cover wrapper/canonical identity mismatch, non-Main source, missing/bad source hash, duplicate/empty evidence ref, forbidden raw field, and invalid timestamp.

Run: `python -m unittest tests.interface_contract.test_event_wrapper.EventRecordTests -v`
Expected: PASS for all single-record cases.

### Task 2: Enforce stream, canonical sequence, revision, and state-event rules

**Files:**

- Modify: `tools/interface_contract/event_contract.py`
- Modify: `fixtures/forgeops-event-contract/suite.json`
- Modify: `tests/interface_contract/test_event_wrapper.py`

**Interfaces:**

- `validate_event_stream(records: list[dict], schema: dict, source_revisions: dict[str, int] | None = None, append_spy: AppendSpy | None = None) -> str`.
- State-accept events are identified only by `canonical_event.code == "STATE_ACCEPTED"`; the exact Main phase enum remains unchanged.

- [ ] **Step 1: Add failing ordered-stream tests**

```python
def test_stream_sequence_starts_at_one_and_has_no_gap(self):
    with self.assertRaisesRegex(ContractError, "EVENT_STREAM_OUT_OF_ORDER"):
        validate_event_stream(case_by_id("stream-seq-skip")["records"], SCHEMA)

def test_canonical_sequence_is_monotonic_but_not_reassigned(self):
    with self.assertRaisesRegex(ContractError, "EVENT_CANONICAL_SEQUENCE_INVALID"):
        validate_event_stream(case_by_id("canonical-seq-reuse")["records"], SCHEMA)

def test_invalid_stream_never_appends(self):
    spy = AppendSpy()
    with self.assertRaises(ContractError):
        case = case_by_id("stale-revision")
        validate_event_stream(case["records"], SCHEMA, case["source_revisions"], spy)
    self.assertEqual(0, spy.calls)
```

- [ ] **Step 2: Run ordered-stream tests and observe RED**

Run: `python -m unittest tests.interface_contract.test_event_wrapper.EventStreamTests -v`
Expected: FAIL until stream semantics are implemented.

- [ ] **Step 3: Implement ordered semantic validation**

```python
def validate_event_stream(records, schema, source_revisions=None, append_spy=None):
    for record in records:
        validate_event_record(record, schema)
    if not records or [item["stream_seq"] for item in records] != list(range(1, len(records) + 1)):
        raise ContractError("EVENT_STREAM_OUT_OF_ORDER")
    if len({(item["run_id"], item["stream_id"]) for item in records}) != 1:
        raise ContractError("EVENT_STREAM_OUT_OF_ORDER")
    canonical = [item["canonical_event"]["seq"] for item in records]
    if canonical != sorted(canonical) or len(canonical) != len(set(canonical)):
        raise ContractError("EVENT_CANONICAL_SEQUENCE_INVALID")
    validate_revisions_and_state_events(records, source_revisions or {})
    return "PASSED"
```

`validate_revisions_and_state_events` rejects a wrapper revision that differs from `source_revisions[event_id]`, decreasing revision, more than one `STATE_ACCEPTED` event for the same revision, and any `STATE_ACCEPTED` event whose canonical actor is not `main`. It validates the whole list before incrementing `append_spy.calls`; negative fixtures therefore remain zero.

- [ ] **Step 4: Complete negative stream fixtures**

Add stream sequence reuse/skip/decrease, cross-run stream mix, canonical sequence reuse/decrease, stale revision, duplicate state-accept event at one revision, and Work-owned authoritative state event. Give each case one expected stable category and `expected_append_calls: 0`.

- [ ] **Step 5: Run all W3-3 tests and inspect the diff**

Run: `python -m unittest tests.interface_contract.test_event_wrapper -v`
Expected: PASS; every negative expected category matches and append calls are zero.

Run: `git diff --check`
Expected: exit 0. Keep `WBS-007` unchanged until integrated evidence exists.
