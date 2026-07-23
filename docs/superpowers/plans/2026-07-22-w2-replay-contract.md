# W2 Replay Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add executable VG-003 replay coverage that preserves lineage, requires new identities, prevents control copying and hard-denies forbidden external effects.

**Architecture:** A closed replay schema and public fixture suite are validated by an isolated Python runner. A spy dispatcher records only an invocation count, allowing the suite to prove all prohibited cases stop before an effect.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `unittest`, JSON, Markdown

## Global Constraints

- Preserve source lineage but never copy authority, approval/token, nonce, credential, publisher token or previous dispatch result.
- Only `AUDIT_REPLAY`, `REEXECUTE`, `COUNTERFACTUAL` are valid modes; AUDIT and COUNTERFACTUAL external effects always deny.
- A Contract-changing COUNTERFACTUAL requires a new task ID; every replay requires a new run ID, correlation ID and event sequence.
- Do not use real network, credentials, publisher, remote reconciliation, Git mutation or WBS state update before fresh evidence.

---

### Task 1: Define replay schema, catalog and failing tests

**Files:**

- Create: `contracts/forgeops-replay-contract/1.0/schema.json`
- Create: `fixtures/forgeops-replay-contract/suite.json`
- Create: `tests/replay_contract/test_verify.py`

**Interfaces:**

- Replay request: `{mode, lineage, new_identity, contract_changed, copied_controls, requested_external_effect, outcome_known, reexecute_preconditions}`.
- `lineage` contains `source_task_id`, `source_run_id`, `source_manifest_id`.

- [ ] **Step 1: Write failing replay guard tests**

```python
def test_audit_replay_cannot_dispatch_external_effect(self):
    result, dispatcher = VERIFY.evaluate(request(mode="AUDIT_REPLAY", requested_external_effect=True))
    self.assertEqual("REPLAY_EXTERNAL_EFFECT_FORBIDDEN", result)
    self.assertEqual(0, dispatcher.calls)

def test_counterfactual_contract_change_requires_new_task(self):
    with self.assertRaisesRegex(VERIFY.ReplayError, "REPLAY_IDENTITY_REUSED"):
        VERIFY.validate(request(mode="COUNTERFACTUAL", contract_changed=True, new_task_id="TASK-1"))
```

- [ ] **Step 2: Run the new tests**

Run: `python -m unittest tests/replay_contract/test_verify.py -v`  
Expected: FAIL because `tools/replay_contract/verify.py` does not exist.

- [ ] **Step 3: Create a closed schema and exact catalog**

Use `additionalProperties: false`. Add positive read-only AUDIT, effect-free COUNTERFACTUAL and effect-free REEXECUTE cases. Add invalid mode, missing lineage, reused run/correlation/sequence, changed-Contract reused task, every prohibited copied control, AUDIT/COUNTERFACTUAL effect, incomplete REEXECUTE precondition and unknown-outcome retry cases.

### Task 2: Implement replay validation and public-safe evidence

**Files:**

- Create: `tools/replay_contract/verify.py`
- Modify: `tests/replay_contract/test_verify.py`

**Interfaces:**

- `validate(request: dict) -> str` raises `ReplayError` for a stable category.
- `evaluate(request: dict) -> tuple[str, SpyDispatcher]` performs only a permitted fixture-local dispatch.
- CLI: `verify.py --schema PATH --suite PATH --result PATH`.

- [ ] **Step 1: Add a failing stable-priority test**

```python
def test_control_copy_precedes_effect_evaluation(self):
    with self.assertRaisesRegex(VERIFY.ReplayError, "REPLAY_CONTROL_COPY_FORBIDDEN"):
        VERIFY.validate(request(mode="AUDIT_REPLAY", copied_controls=["nonce"], requested_external_effect=True))
```

- [ ] **Step 2: Implement ordered validation**

```python
def validate(request):
    validate_schema(request)
    if request["mode"] not in MODES: raise ReplayError("REPLAY_MODE_INVALID")
    if not lineage_complete(request["lineage"]): raise ReplayError("REPLAY_LINEAGE_MISSING")
    if identity_reused(request): raise ReplayError("REPLAY_IDENTITY_REUSED")
    if request["copied_controls"]: raise ReplayError("REPLAY_CONTROL_COPY_FORBIDDEN")
    if request["mode"] in {"AUDIT_REPLAY", "COUNTERFACTUAL"} and request["requested_external_effect"]: raise ReplayError("REPLAY_EXTERNAL_EFFECT_FORBIDDEN")
    if request["mode"] == "REEXECUTE" and not fresh_effect_preconditions(request): raise ReplayError("REPLAY_REAPPROVAL_REQUIRED")
    if not request["outcome_known"] and request["requested_external_effect"]: raise ReplayError("REPLAY_RECONCILIATION_REQUIRED")
    return "PASSED"
```

- [ ] **Step 3: Implement runner failure replacement and safe result fields**

Result cases contain only ID, kind, expected/actual category and verdict. Write `FAILED/RUNNER_CONTRACT_INVALID` atomically on suite corruption and prove it with a temporary-directory regression test.

- [ ] **Step 4: Run replay tests**

Run: `python -m unittest tests/replay_contract/test_verify.py -v`  
Expected: PASS; every forbidden case reports dispatcher count `0`.

### Task 3: Register VG-003 replay evidence and close only WBS-004

**Files:**

- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-003-replay-contract-result.json`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/project/wbs.md`

**Interfaces:**

- Command ID: `replay-contract-negative`; profile: `forgeops-state-contract`; tier: `E2`.
- Consumes the two passed results from the state-transition plan and the fresh replay result.

- [ ] **Step 1: Register and execute the exact replay command**

Add the required E2 command/profile binding, execute it verbatim, and require exit 0 with a strict UTC timestamp and all fixture cases matched.

- [ ] **Step 2: Perform the VG-003 evidence aggregation check**

Verify the three results cover transition, event order and replay, all have `PASSED`, and no result includes copied control values or raw payloads.

- [ ] **Step 3: Synchronize only evidence-backed owner rows**

Update the `PRD-FR-002` RTM row to its actual E2 result/evidence references and change only `WBS-004` to `WBS_DONE`. Preserve WBS-005 and all later rows unchanged. Run `git diff --check` and `git status --short`; do not stage or commit.
