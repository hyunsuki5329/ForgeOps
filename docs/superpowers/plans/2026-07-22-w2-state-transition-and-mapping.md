# W2 State Transition and Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an executable VG-003 state-contract fixture that accepts only explicit product-to-Protocol mappings and Main-owned, ordered canonical transitions.

**Architecture:** A closed JSON Schema and immutable fixture suite feed a Python `jsonschema` validator. The runner returns one stable error per case, writes public-safe E2 evidence atomically, and never creates a MainDecision or durable event.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `unittest`, JSON, Markdown

## Global Constraints

- Preserve existing changes; do not install packages, access network/private data, stage, commit, push, or alter WBS/VG status before fresh verified evidence.
- Canonical transitions and Main-only ownership must exactly follow `.github/agents/main_instruction.prompt.md` section 6.
- `CANCELLED` is product-only and must never coerce to a Protocol terminal state.
- Result artifacts contain only safe IDs, hashes, verdicts, counts and runtime UTC timestamps.
- W3 owns durable event wrapper and `stream_seq`; this plan validates only Main canonical `seq`.

---

### Task 1: Define the closed state-contract schema and suite

**Files:**

- Create: `contracts/forgeops-state-contract/1.0/schema.json`
- Create: `fixtures/forgeops-state-contract/state-suite.json`
- Test: `tests/state_contract/test_verify.py`

**Interfaces:**

- Suite case: `{id, kind, snapshot, proposal, expected_result|expected_error}`.
- `snapshot`: `{task_id, correlation_id, status, revision, next_seq}`.
- `proposal`: `{actor, product_state, canonical_state, base_revision, expected_seq, has_required_evidence}`.

- [ ] **Step 1: Write the schema and catalog regression tests**

```python
def test_suite_rejects_changed_catalog_entry(self):
    suite = load_suite()
    suite["cases"][0]["id"] = "POSITIVE_RENAMED"
    with self.assertRaisesRegex(ValueError, "exact case catalog"):
        VERIFY.validate_suite(suite)

def test_cancelled_mapping_is_rejected(self):
    result = VERIFY.run_case(case("NEGATIVE_CANCELLED_COERCION"))
    self.assertEqual("STATE_CANCELLED_COERCION_FORBIDDEN", result["actual"])
```

- [ ] **Step 2: Run the focused tests and confirm they fail because the runner is absent**

Run: `python -m unittest tests/state_contract/test_verify.py -v`  
Expected: FAIL with module or verifier import error.

- [ ] **Step 3: Create the schema and immutable case catalog**

Use `additionalProperties: false` for every object. Include positive CREATED→PENDING, active→IN_PROGRESS, waiting, PARTIAL, verified success and policy block cases. Include negative stale revision, sequence reuse/skip, non-Main actor, terminal restart, missing success evidence and both `CANCELLED → FAILED` and `CANCELLED → BLOCKED` coercion cases. Pin their ordered `(id, kind, expected)` tuples in the runner.

- [ ] **Step 4: Re-run the catalog tests**

Run: `python -m unittest tests/state_contract/test_verify.py -v`  
Expected: FAIL only because semantic validation is not implemented.

### Task 2: Implement the deterministic state validator and safe runner

**Files:**

- Create: `tools/state_contract/verify.py`
- Modify: `tests/state_contract/test_verify.py`

**Interfaces:**

- `validate_transition(snapshot: dict, proposal: dict) -> str`: returns `PASSED` or raises `StateError(code)`.
- `run_case(case: dict) -> dict`: returns `{id, kind, status, expected, actual}`.
- CLI: `verify.py --schema PATH --suite PATH --result PATH --command-id ID`.

- [ ] **Step 1: Add failing transition-order tests**

```python
def test_main_must_match_current_revision_and_next_sequence(self):
    with self.assertRaisesRegex(VERIFY.StateError, "STATE_REVISION_STALE"):
        VERIFY.validate_transition(snapshot(revision=3, next_seq=9), proposal(base_revision=2, expected_seq=9))
    with self.assertRaisesRegex(VERIFY.StateError, "STATE_SEQUENCE_OUT_OF_ORDER"):
        VERIFY.validate_transition(snapshot(revision=3, next_seq=9), proposal(base_revision=3, expected_seq=8))
```

- [ ] **Step 2: Implement the minimal validator in stable priority order**

```python
def validate_transition(snapshot, proposal):
    if proposal["actor"] != "main": raise StateError("STATE_OWNER_INVALID")
    if proposal["base_revision"] != snapshot["revision"]: raise StateError("STATE_REVISION_STALE")
    if proposal["expected_seq"] != snapshot["next_seq"]: raise StateError("STATE_SEQUENCE_OUT_OF_ORDER")
    if proposal["product_state"] == "CANCELLED": raise StateError("STATE_CANCELLED_COERCION_FORBIDDEN")
    if proposal["canonical_state"] not in ALLOWED[snapshot["status"]]: raise StateError("STATE_TRANSITION_INVALID")
    if not mapping_is_valid(proposal): raise StateError("STATE_MAPPING_INVALID")
    if proposal["canonical_state"] == "SUCCEEDED" and not proposal["has_required_evidence"]: raise StateError("STATE_EVIDENCE_INSUFFICIENT")
    return "PASSED"
```

- [ ] **Step 3: Implement atomic safe-result generation and the CLI**

Use `tempfile.NamedTemporaryFile(delete=False, dir=target.parent)` followed by `os.replace`. On runner-contract failure replace any stale result with `FAILED` and `RUNNER_CONTRACT_INVALID`; do not preserve stale `PASSED` content.

- [ ] **Step 4: Run all state tests**

Run: `python -m unittest tests/state_contract/test_verify.py -v`  
Expected: PASS; every negative case has one exact stable category.

### Task 3: Register commands and capture fresh state evidence

**Files:**

- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-003-state-transition-result.json`
- Generate: `artifacts/verification/vg-003-event-order-result.json`

**Interfaces:**

- Profile ID: `forgeops-state-contract`.
- Command IDs: `state-transition-fixture`, `event-order-fixture`.

- [ ] **Step 1: Add exact command records and profile bindings**

Register two E2 required commands that invoke the same runner with the same schema/suite and distinct `--command-id` and result paths. Add both IDs to `extensions.forgeops.verification_profiles` under `forgeops-state-contract`.

- [ ] **Step 2: Execute both registered commands in fresh processes**

Run each command copied verbatim from `AGENTS.md`.  
Expected: exit 0, `status=PASSED`, all catalog cases matched, strict UTC `observed_at` present.

- [ ] **Step 3: Inspect evidence and leave Git unchanged**

Assert no raw snapshot/proposal/evidence content is emitted, hashes and counts exist, then run `git diff --check` and `git status --short`. Do not update `WBS-004`: replay coverage from the next plan remains required.
