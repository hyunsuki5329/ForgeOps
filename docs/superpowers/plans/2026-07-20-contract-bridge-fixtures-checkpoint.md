# Contract Bridge Fixtures and W1 Checkpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute VG-002 with 19 deterministic bridge fixtures, preserve fresh E2 evidence, and complete the W1 bridge review checkpoint.

**Architecture:** A closed mutation-based JSON suite drives one Python 3.11 validator using Draft 2020-12 `jsonschema`. The registered command writes a public-safe JSON result and standalone HTML render; a Markdown checkpoint and synchronized owner/trace/WBS documents consume only the safe result.

**Tech Stack:** Python 3.11.9, jsonschema 4.26.0, JSON Schema Draft 2020-12, JSON, HTML, Markdown

## Global Constraints

- Preserve all pre-existing user changes and patch dirty owner documents only at exact rows.
- Do not install packages or access network, credentials, private data, external systems, `.git` internals, publication, messaging, deployment, or material cost.
- The exact validation command ID is `bridge-schema-fixture`, profile ID is `forgeops-contract-bridge`, and evidence tier is `E2`.
- The suite contains exactly 3 positive and 16 negative cases with ordinal-unique IDs.
- Generated evidence contains no raw Contract, trusted context, mapped packet, secret, private repository, tenant ID, raw log, or active/remote HTML content.
- Update PASSED/DONE states only after the registered command exits 0 and its result artifact validates.
- Do not change VG-001, WBS-004 or later WBS state, product runtime claims, Phase 0 Exit, or publication authority.
- Do not stage, commit, merge, push, open a PR, or clean existing user changes.

---

### Task 1: Fixture Suite and Validator

**Files:**

- Create: `fixtures/product-task-contract-bridge/suite.json`
- Create: `tools/contract_bridge/verify.py`
- Create: `tests/contract_bridge/test_verify.py`

**Interfaces:**

- CLI: `verify.py --schema PATH --suite PATH --result PATH --report PATH`.
- Core functions: `load_json(Path) -> dict`, `canonical_sha256(object) -> str`, `apply_mutation(contract, context, case) -> tuple`, `validate_and_map(contract, context, expected_hash) -> dict`, `run_case(schema_validator, suite, case) -> dict`, `render_html(result) -> str`, `atomic_write(path, text) -> None`.
- Stable errors: the eight `CONTRACT_*` categories defined by the bridge plus runner contract errors that fail the suite command.

- [x] **Step 1: Verify the runner command fails before implementation**

Run the final command from the design. Expected: non-zero because `tools/contract_bridge/verify.py` does not exist.

- [x] **Step 2: Create the exact 19-case suite**

Create a closed suite with one public base Contract, trusted intent mapping, one exact validation profile and trusted canonical control. Add the three positive IDs and sixteen negative IDs from the approved design. Each negative case has exactly one mutation and exact `expected_error`; positive cases use `expected_result=PASSED`.

- [x] **Step 3: Implement schema validation, mutation, mapping and assertions**

Use `jsonschema.Draft202012Validator.check_schema`. Apply stable priority: version, forbidden control, schema, duplicate criterion, intent, command, monotonicity, provenance. Successful mapping must preserve objective, criteria, constraints, repository, source issue, product budget, approval policy and content hash while keeping trusted capabilities, authority, source of truth, risk rules, Harness budgets, state and tool schema outside Contract control.

- [x] **Step 4: Implement safe evidence and HTML generation**

Record only validator identity/version, hashes, strict UTC observed_at, safe case IDs/kinds/status/error and aggregate counts. Render escaped standalone HTML without script, external stylesheet/image/link or raw fixture values. Write result and report atomically.

- [x] **Step 5: Run the command directly**

Expected: exit 0, `19/19`, positive `3/3`, negative `16/16`, and both generated artifacts exist.

- [x] **Step 6: Harden the runner fail-closed contract**

Pin the exact 19-case catalog, convert unexpected case errors to safe FAILED
results, and replace stale PASSED artifacts with a public-safe FAILED artifact
when suite/runner validation fails. Verify all three behaviors with stdlib
`unittest` regression tests.

### Task 2: Trusted Command Registration and Fresh VG-002 Run

**Files:**

- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-002-contract-bridge-result.json`
- Generate: `artifacts/reviews/w1-contract-bridge-checkpoint.html`

**Interfaces:**

- `project_profile.validation_commands[bridge-schema-fixture]` exact record from the design.
- `project_profile.extensions.forgeops.verification_profiles[forgeops-contract-bridge].command_ids = [bridge-schema-fixture]`.

- [x] **Step 1: Register the exact command and profile**

Replace `validation_commands: []` with the closed command record and add the profile under `extensions.forgeops`. Do not change capability defaults or authority.

- [x] **Step 2: Re-read and exact-compare the registered command**

Assert ID, command, cwd, E2 and required values and the profile command binding.

- [x] **Step 3: Execute the exact registered command in a fresh process**

Expected: exit 0 and result `PASSED` with a runtime-supplied strict UTC timestamp.

- [x] **Step 4: Validate generated artifacts**

Assert 19 case records, hashes, 3/16 counts, zero failed/mismatched cases, no disallowed raw fields, and HTML active/remote content zero.

### Task 3: Public-Safe Bridge Review Checkpoint

**Files:**

- Create: `docs/reviews/w1-contract-bridge-checkpoint.md`
- Modify: `docs/contracts/product-task-contract-to-taskpacket.md`

**Interfaces:**

- Consumes only the generated safe result and render.
- Produces a public-safe file/render review with evidence links, criterion matrix, resolved violations and explicit non-claims.

- [x] **Step 1: Read the fresh result metadata**

Capture observed_at, hashes, case counts, validator versions and status from the JSON artifact; do not infer values.

- [x] **Step 2: Create the review Markdown**

Link schema, bridge, suite, runner, AGENTS command, result JSON and HTML. Include VG-002 criterion-to-evidence mapping, 19/19 summary, stable negative rejection summary, resolved violations=0 remaining, and non-claims for VG-001, product runtime, Phase 0 Exit and publication.

- [x] **Step 3: Update the bridge evidence section**

Replace future Task 4 wording with executed fixture coverage, result/report links and retained non-grant limits.

- [x] **Step 4: Verify Markdown and HTML review surfaces**

Assert all local links resolve, safe fields only, no raw Contract/private values, no remote/active HTML, UTF-8 and final newlines.

### Task 4: Owner, Trace, WBS and Document Map Synchronization

**Files:**

- Modify: `docs/agent-harness/BASELINE_INVENTORY.md`
- Modify: `docs/product/prd.md`
- Modify: `docs/architecture/system-architecture.md`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/project/wbs.md`
- Modify: `docs/README.md`

**Interfaces:**

- Consumes: fresh PASSED result path and observed_at.
- Produces: IMPLEMENTED PRD-FR-001/ARC-002/ARC-010 contract scope, RTM E2 PASSED evidence, WBS-002/003 DONE and checkpoint discovery.

- [x] **Step 1: Patch exact maturity rows and baseline boundary**

Change only Product Contract layer, PRD-FR-001, ARC-002 and ARC-010 from SPECIFIED to IMPLEMENTED and link the fixture evidence without claiming product runtime.

- [x] **Step 2: Patch exact RTM evidence cells**

For PRD-FR-001 set maturity IMPLEMENTED, Result PASSED, Actual tier E2, Evidence ref to `artifacts/verification/vg-002-contract-bridge-result.json`, Observation metadata to the exact generated `observed_at`, trace COVERED, and gap/action to completed fixture plus WBS-003 review.

- [x] **Step 3: Close WBS-002 and WBS-003**

Change only those two rows to WBS_DONE after verifying the result and review artifacts. Preserve WBS-001 DONE and WBS-004 NOT_STARTED.

- [x] **Step 4: Register checkpoint in the document map**

Add the review immediately after the bridge in reading order and identify it as a WBS-003 public-safe internal artifact, not publication authority.

- [x] **Step 5: Run final verification and inspect scoped diff/status**

Re-run the exact trusted command. Validate result freshness, 19/19 cases, all links, synchronized IDs/states, VG-001 unchanged, WBS-004+ unchanged, safe render, whitespace/newline and exact diff rows. Expected final marker: `W1_CONTRACT_BRIDGE_CHECKPOINT_OK`.

- [x] **Step 6: Preserve the branch without Git mutation**

Leave `feature/portable-agent-harness-v2` and the current workspace as-is; report generated evidence and pre-existing user changes separately.
