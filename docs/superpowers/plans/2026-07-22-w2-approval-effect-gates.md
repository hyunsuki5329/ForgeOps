# W2 Approval and Effect Gates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add VG-007 fixture coverage proving approval cannot grant authority and destructive/external effects require independent hard gates, all-input binding and an atomic one-time nonce.

**Architecture:** The shared policy runner adds an approval branch after exact authority preflight. A deterministic fixture verifier and injected nonce ledger test approval semantics without a real key store or external effect; a spy dispatcher proves denied cases stop before dispatch.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `unittest`, JSON, Markdown

## Global Constraints

- Dispatch requires `EXECUTE`, available capability, exact current authority, approved candidate, current revision and all preflights; approval never supplies a missing condition.
- `destructive_actions=ALLOWED` and external-effect runtime/authority gates are separate and non-substitutable.
- Approval binds candidate, action identity, target, tenant, issuer/audience, policy/key version, temporal bounds, nonce and canonical effect hash over revision, Contract, plan, policy, diff and payload.
- Never record approval token, signature raw value, credential or private payload. Do not perform an actual effect, mutate WBS status before fresh evidence, or perform Git operations.

---

### Task 1: Define approval scenarios and write failing gate tests

**Files:**

- Create: `fixtures/forgeops-approval-policy/suite.json`
- Create: `tests/policy_contract/test_approval.py`

**Interfaces:**

- `approval`: `{candidate_id, action_identity, target, tenant, issuer, audience, approver_subject, policy_version, key_id, not_before, expires_at, nonce, signature_ref, effect_hash}`.
- `NonceLedger.consume_once(nonce: str) -> bool`.
- `evaluate_approval(request: dict, ledger: NonceLedger) -> tuple[str, SpyDispatcher]`.

- [ ] **Step 1: Write the failing authority-intersection tests**

```python
def test_approval_cannot_overcome_unknown_authority_or_external_gate(self):
    for request in (approved_request(authority="UNKNOWN"), approved_request(external_runtime="UNAVAILABLE")):
        result, dispatcher = VERIFY.evaluate_approval(request, VERIFY.MemoryNonceLedger())
        self.assertEqual("AUTHORITY_CAPABILITY_DENIED", result)
        self.assertEqual(0, dispatcher.calls)
```

- [ ] **Step 2: Run tests and create the immutable suite**

Run: `python -m unittest tests/policy_contract/test_approval.py -v`  
Expected: FAIL before the approval branch exists. Add valid local non-destructive, hard-gate missing, rejected/expired/not-before/wrong issuer/audience/tenant/signature, every bound-input mutation, nonce reuse/concurrent consume and replayed approval cases.

### Task 2: Implement approval binding, gates and atomic nonce use

**Files:**

- Modify: `tools/policy_contract/verify.py`
- Modify: `tests/policy_contract/test_approval.py`

**Interfaces:**

- `canonical_effect_hash(request: dict) -> str`.
- `validate_approval(request: dict, ledger: NonceLedger) -> str`.
- `MemoryNonceLedger` is test-only and must lock around consume-and-mark.

- [ ] **Step 1: Add failing input-binding and nonce tests**

```python
def test_revision_change_invalidates_approval_and_nonce_is_one_time(self):
    request = approved_request()
    request["base_revision"] += 1
    with self.assertRaisesRegex(VERIFY.PolicyError, "APPROVAL_BINDING_MISMATCH"):
        VERIFY.validate_approval(request, VERIFY.MemoryNonceLedger())
    ledger = VERIFY.MemoryNonceLedger()
    self.assertEqual("PASSED", VERIFY.validate_approval(approved_request(), ledger))
    with self.assertRaisesRegex(VERIFY.PolicyError, "APPROVAL_NONCE_REUSED"):
        VERIFY.validate_approval(approved_request(), ledger)
```

- [ ] **Step 2: Implement ordered hard-gate and approval validation**

```python
def validate_approval(request, ledger):
    require_execute_available_exact_authority_candidate_revision(request)
    require_destructive_and_external_gates(request)
    approval = request.get("approval")
    if approval is None: raise PolicyError("APPROVAL_MISSING")
    validate_issuer_audience_tenant_signature_and_time(approval, request)
    if approval["effect_hash"] != canonical_effect_hash(request): raise PolicyError("APPROVAL_BINDING_MISMATCH")
    if not ledger.consume_once(approval["nonce"]): raise PolicyError("APPROVAL_NONCE_REUSED")
    return "PASSED"
```

- [ ] **Step 3: Test atomicity and zero-dispatch behavior**

Run: `python -m unittest tests/policy_contract/test_resource.py tests/policy_contract/test_command_network.py tests/policy_contract/test_approval.py -v`  
Expected: PASS; concurrent nonce test permits one result only and every negative case has dispatcher count `0`.

### Task 3: Register VG-007 and complete only evidence-backed W2 records

**Files:**

- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-007-approval-policy-result.json`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/project/wbs.md`

**Interfaces:**

- Command ID: `approval-negative-fixture`; profile: `forgeops-approval-policy`; tier: `E2`.
- Inputs: fresh VG-005, VG-006 and VG-007 result artifacts only.

- [ ] **Step 1: Register and run the exact command**

Add the required E2 command/profile record, execute it verbatim from `AGENTS.md`, and require exit 0 with exact expected categories and no raw approval material.

- [ ] **Step 2: Verify all WBS-005 acceptance gates together**

Confirm VG-005 resource/protected-read, VG-006 command/network and VG-007 approval results are fresh `PASSED`, all sink/adapter/dispatcher zero assertions hold for negative cases, and all result artifacts remain public-safe.

- [ ] **Step 3: Synchronize owner rows and final W2 evidence**

Update RTM actual E2 results/evidence for `PRD-FR-006`, `PRD-NFR-002`, `PRD-NFR-005` and `PRD-NFR-012` only where the fixture coverage supports them. Change only `WBS-005` to `WBS_DONE`; preserve W3+ statuses. Run `git diff --check` and `git status --short`; do not stage, commit, push or publish.
