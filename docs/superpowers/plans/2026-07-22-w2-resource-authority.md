# W2 RESOURCE Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add VG-005 fixture coverage for exact RESOURCE authority, root containment and protected data first-byte denial.

**Architecture:** The first WBS-005 component creates the shared closed authority-policy envelope and a RESOURCE validator. Instrumented reader/context/log/evidence sinks make denial observable without reading a protected real file.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `unittest`, JSON

## Global Constraints

- `PROJECT` permits only root-contained RESOURCE operations with an empty list; `NAMED_RESOURCES` requires non-empty case-sensitive exact membership.
- Reject absolute/parent paths, wildcard/glob/regex/prefix/suffix inference, duplicate entries, symlink escape and `UNKNOWN` before effect.
- Protected resource, credential and private-data sentinel bytes must be absent from reader, model-context, log and evidence sinks before exact-target approval.
- Do not inspect, read or alter real protected paths; do not change WBS-005 until VG-005, VG-006 and VG-007 are all fresh passed.

---

### Task 1: Create the shared authority envelope and RESOURCE suite

**Files:**

- Create: `contracts/forgeops-authority-policy/1.0/schema.json`
- Create: `fixtures/forgeops-authority-resource/suite.json`
- Create: `tests/policy_contract/test_resource.py`

**Interfaces:**

- Authority envelope: `{action, identity, authority, capability, approved_candidate, current_revision, operation_mode, protected_target_approval}`.
- `identity.resource_ref` is a root-relative literal; `authority` contains a scope and companion list.

- [ ] **Step 1: Write failing first-byte tests**

```python
def test_protected_read_never_invokes_reader_or_sinks(self):
    result, probes = VERIFY.evaluate_resource(protected_request(approval=False))
    self.assertEqual("PROTECTED_TARGET_APPROVAL_REQUIRED", result)
    self.assertEqual(0, probes.reader_calls)
    self.assertEqual(0, probes.sentinel_occurrences())
```

- [ ] **Step 2: Run the test and create the closed schema/suite**

Run: `python -m unittest tests/policy_contract/test_resource.py -v`  
Expected: FAIL before the verifier exists. Create valid PROJECT/NAMED cases and negatives for every prohibited path/list form, capability, stale revision, protected target and user-change conflict.

### Task 2: Implement RESOURCE validation and regression coverage

**Files:**

- Create: `tools/policy_contract/verify.py`
- Modify: `tests/policy_contract/test_resource.py`

**Interfaces:**

- `evaluate_resource(request: dict) -> tuple[str, ProbeSet]`.
- `validate_resource(request: dict) -> str` raises `PolicyError(code)`.

- [ ] **Step 1: Add failing exact-membership tests**

```python
def test_named_scope_does_not_accept_prefix_or_case_variation(self):
    for resource in ("src/app.py.bak", "SRC/app.py"):
        with self.assertRaisesRegex(VERIFY.PolicyError, "RESOURCE_EXACT_MATCH_REQUIRED"):
            VERIFY.validate_resource(named_request(resource))
```

- [ ] **Step 2: Implement preflight in this order**

```python
def validate_resource(request):
    validate_schema(request)
    validate_literal_root_relative(request["identity"]["resource_ref"])
    validate_scope_and_list(request["authority"])
    require_available_capability_and_current_candidate(request)
    require_root_containment_or_exact_membership(request)
    require_protected_target_approval_before_read(request)
    require_user_change_ownership_before_mutation(request)
    return "PASSED"
```

- [ ] **Step 3: Add atomic safe evidence output and run tests**

Run: `python -m unittest tests/policy_contract/test_resource.py -v`  
Expected: PASS; every denied protected case has reader/sink counts of zero.

### Task 3: Register and execute VG-005

**Files:**

- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-005-resource-authority-result.json`
- Generate: `artifacts/verification/vg-005-protected-read-result.json`

- [ ] **Step 1: Register `resource-authority-negative` and `protected-read-negative`**

Add required E2 command records and profile `forgeops-authority-resource`, both using `tools/policy_contract/verify.py resource` with distinct result paths.

- [ ] **Step 2: Execute both commands and inspect results**

Expected: exit 0, exact catalog match, no sentinel raw value, all denied cases have zero reader/sink counts.

- [ ] **Step 3: Leave the workspace reviewable**

Run `git diff --check` and `git status --short`; do not update WBS-005, stage or commit.
