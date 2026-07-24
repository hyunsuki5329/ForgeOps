# W3-2 Closed API Data and Control Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the endpoint-specific closed OpenAPI schemas and prove that product requests cannot create canonical ForgeOps control grants or external effects.

**Architecture:** Extend the W3-1 OpenAPI module instead of adding a handler layer. Validate endpoint shape and the existing Product Task Contract first-class, then run explicit non-grant and zero-spy assertions before returning public-safe projections and references.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `unittest`, OpenAPI 3.1.0, JSON

## Global Constraints

- Consume W3-1's exact `ContractError`, `load_json`, `validate_openapi_document`, and request-ID rules.
- Treat Product Task Contract `budget` and `approval_policy` as untrusted product constraints; they never create capability, authority, accepted state, approval token, nonce, policy, or runtime budget.
- Reject top-level `authority`, `capabilities`, `runtime_policy`, `accepted_state`, `approval_token`, `nonce`, `credentials`, `tools`, and `commands` as `API_CONTROL_FIELD_FORBIDDEN` before general closed-body validation.
- Preserve the approved priority: version, envelope required/type, forbidden control scan, endpoint body, Product Task Contract, identity/reference.
- Keep all negative dispatcher/process/network/credential/external-store spy counts at zero.
- Do not implement an API handler, queue, persistence, approval UI, runtime authorization, Git commit/push/PR, or WBS/RTM update.

---

## File Structure

- Modify `contracts/forgeops-api/1.0/openapi.yaml`: add exact endpoint request/data/page/manifest schemas and Product Task Contract reference.
- Modify `tools/interface_contract/openapi_contract.py`: add data/control evaluator, product-contract validation, projections, reference checks, and spies.
- Create `fixtures/forgeops-api/data-control-suite.json`: ordered valid/invalid/non-grant catalog.
- Create `tests/interface_contract/test_api_boundary.py`: schema, error-priority, non-grant, identity/reference, and zero-effect tests.

### Task 1: Close every endpoint schema and Product Task Contract boundary

**Files:**

- Modify: `contracts/forgeops-api/1.0/openapi.yaml`
- Modify: `tools/interface_contract/openapi_contract.py`
- Create: `fixtures/forgeops-api/data-control-suite.json`
- Create: `tests/interface_contract/test_api_boundary.py`

**Interfaces:**

- `validate_api_case(case: dict, document: dict, product_schema: dict, spies: EffectSpies) -> str` returns `PASSED` or raises `ContractError`.
- `EffectSpies` has integer fields `dispatcher_calls`, `process_calls`, `network_calls`, `credential_calls`, `store_calls`, all initialized to zero.
- Suite root is exactly `{suite_id, suite_version, cases}` with ID `forgeops-api-data-control`, version `1.0`.

- [ ] **Step 1: Write failing endpoint-schema tests**

```python
def test_create_task_accepts_only_product_contract_envelope(self):
    case = case_by_id("create-task-valid")
    self.assertEqual("PASSED", validate_api_case(case, DOCUMENT, PRODUCT_SCHEMA, EffectSpies()))

def test_forbidden_control_precedes_unknown_field(self):
    case = deepcopy(case_by_id("create-task-valid"))
    case["body"]["authority"] = {}
    case["body"]["ordinary_unknown"] = True
    with self.assertRaisesRegex(ContractError, "API_CONTROL_FIELD_FORBIDDEN"):
        validate_api_case(case, DOCUMENT, PRODUCT_SCHEMA, EffectSpies())

def test_product_contract_unknown_field_is_schema_error(self):
    case = deepcopy(case_by_id("create-task-valid"))
    case["body"]["task_contract"]["unknown"] = True
    with self.assertRaisesRegex(ContractError, "API_SCHEMA_INVALID"):
        validate_api_case(case, DOCUMENT, PRODUCT_SCHEMA, EffectSpies())
```

- [ ] **Step 2: Run the new tests and observe RED**

Run: `python -m unittest tests.interface_contract.test_api_boundary -v`
Expected: FAIL because endpoint components, suite, and `validate_api_case` do not exist.

- [ ] **Step 3: Complete exact OpenAPI components**

Define `CreateTaskRequest` with only `api_version`, `request_id`, `task_contract`; reference `../../product-task-contract/1.0/schema.json` from the API contract. Define `CreateTaskData` with only `task_id`, `artifact_id`, `artifact_version`, `product_state="CREATED"`, `contract_sha256`, and closed `links` containing only `task` and `run`. Define `TaskData` projection (`status`, `revision`, `last_event_seq`) and `RunData` with `task_id`, `run_id`, `correlation_id`, the four approved run modes, `status`, `accepted_revision`, `event_stream_ref`, and `manifest_ref`. Define finite event-page and manifest response references without duplicating W3-3/W3-4 fields.

- [ ] **Step 4: Implement schema and Product Task Contract validation**

```python
FORBIDDEN_CONTROL_FIELDS = frozenset({
    "authority", "capabilities", "runtime_policy", "accepted_state",
    "approval_token", "nonce", "credentials", "tools", "commands",
})

def validate_api_case(case, document, product_schema, spies):
    evaluate_version_envelope(case, document)
    body = case.get("body", {})
    if FORBIDDEN_CONTROL_FIELDS.intersection(body):
        raise ContractError("API_CONTROL_FIELD_FORBIDDEN")
    validate_endpoint_component(case, document)
    if case["operation_id"] == "createTask":
        errors = list(Draft202012Validator(product_schema).iter_errors(body["task_contract"]))
        if errors:
            raise ContractError("API_SCHEMA_INVALID")
    assert_non_grant(case)
    validate_identity_matches(case)
    validate_case_references(case)
    return "PASSED"
```

`assert_non_grant` rejects any derived-control object that copies product `budget` or `approval_policy` into canonical fields. It inspects data only and never calls an effect surface.

- [ ] **Step 5: Add the ordered schema/control fixture catalog**

Include valid create-task, get-task, get-run, event-page, and manifest-response cases. Include negatives for envelope and contract unknown/missing/wrong-type fields; each forbidden control literal; copied budget/approval control; task/run path-body mismatch; dangling event/manifest refs; simultaneous data/error; raw credential/private response fields. Store expected stable error and expected zero spy counts in every negative.

- [ ] **Step 6: Run Task 1 tests**

Run: `python -m unittest tests.interface_contract.test_api_boundary -v`
Expected: PASS for schema, priority, Product Task Contract, and ordered catalog tests.

### Task 2: Prove non-grant behavior, public projections, and zero effects

**Files:**

- Modify: `tools/interface_contract/openapi_contract.py`
- Modify: `tests/interface_contract/test_api_boundary.py`

**Interfaces:**

- `run_api_boundary_suite(document: dict, product_schema: dict, suite: dict) -> tuple[list[dict], dict[str, int]]`.
- Case record is exactly `{id, kind, expected, actual, status, spy_calls}` where `spy_calls` contains the five named non-negative counters.

- [ ] **Step 1: Add failing non-grant and reference tests**

```python
def test_product_approval_never_becomes_canonical_approval(self):
    case = deepcopy(case_by_id("create-task-valid"))
    case["body"]["task_contract"]["approval_policy"] = "not_required"
    case["derived_control"] = {"approval_token": "copied"}
    spies = EffectSpies()
    with self.assertRaisesRegex(ContractError, "API_CONTROL_FIELD_FORBIDDEN"):
        validate_api_case(case, DOCUMENT, PRODUCT_SCHEMA, spies)
    self.assertEqual((0, 0, 0, 0, 0), spies.as_tuple())

def test_run_references_resolve_in_same_task_and_run(self):
    case = case_by_id("get-run-valid")
    self.assertEqual("PASSED", validate_api_case(case, DOCUMENT, PRODUCT_SCHEMA, EffectSpies()))
```

- [ ] **Step 2: Run the focused tests and observe RED**

Run: `python -m unittest tests.interface_contract.test_api_boundary.ApiBoundaryTests.test_product_approval_never_becomes_canonical_approval tests.interface_contract.test_api_boundary.ApiBoundaryTests.test_run_references_resolve_in_same_task_and_run -v`
Expected: FAIL until derived-control and reference checks are implemented.

- [ ] **Step 3: Implement deterministic non-grant and reference checks**

```python
def assert_non_grant(case):
    derived = case.get("derived_control", {})
    if set(derived).intersection(FORBIDDEN_CONTROL_FIELDS | {"budget", "approval_policy"}):
        raise ContractError("API_CONTROL_FIELD_FORBIDDEN")

def validate_case_references(case):
    for ref in case.get("references", []):
        if ref["task_id"] != case["expected_task_id"] or ref["run_id"] != case["expected_run_id"]:
            raise ContractError("API_REFERENCE_INVALID")
```

Ensure response projections exclude MainDecision bodies, approval material, raw private data, external URLs, and commands. All identifier comparisons use the original strings without trimming or case folding.

- [ ] **Step 4: Run all W3-1 and W3-2 tests together**

Run: `python -m unittest tests.interface_contract.test_openapi_version tests.interface_contract.test_api_boundary -v`
Expected: PASS; all negative cases have five zero spy counters and no result contains a forbidden field value.

- [ ] **Step 5: Review the W3-2 deliverable without committing**

Run: `git diff --check`
Expected: exit 0. Leave WBS/RTM evidence unchanged until the integrated VG-004 command passes.

