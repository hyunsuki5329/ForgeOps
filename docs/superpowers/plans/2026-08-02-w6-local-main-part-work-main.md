# W6 Local Main→Part→Work→Main Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement WBS-016~WBS-019 as a deterministic local Main→Part→Work→Main vertical flow with fresh VG-012 E2 evidence while preserving W7's VG-013 scope.

**Architecture:** Reuse the W1 Product Contract bridge and W5 snapshot/Context Pack contracts. Implement focused actor modules that exchange only canonical Protocol 2.0 packets; the Main/runtime-owned trusted execution context remains an immutable non-packet value. A registered local verifier runs one positive end-to-end flow plus boundary mutations and emits a closed public-safe result.

**Tech Stack:** Python 3 standard library, `jsonschema` Draft 2020-12, `unittest`, existing ForgeOps contract/verifier patterns, Markdown/YAML project adapters.

## Global Constraints

- Work only in `C:\Users\User\AppData\Local\Temp\forgeops-w6-local-vertical` on `feature/w6-local-vertical`.
- Preserve Protocol 2.0 envelope values and exact ordinal identity matching; never trim, case-fold, glob, prefix-match, or manufacture authority.
- Main alone accepts canonical state transitions, increments accepted revision exactly once per accepted transition, and assigns contiguous seq values to accepted authoritative events.
- Part remains read-only and receives an `EXPLORE` TaskPacket; Work receives an `EXECUTE` TaskPacket only through Main's trusted execution context.
- Missing safety-relevant capability or authority becomes `UNKNOWN` and fails closed.
- W6 Work supports only the deterministic fixture RESOURCE update `fixture/work-item.txt`: UTF-8 bytes `before\n` to `after\n` inside the verifier-owned separated workspace.
- COMMAND, NETWORK, delete, arbitrary patch/diff, trusted task/regression/lint/typecheck profiles, and anti-tamper remain unsupported in W6 and fail before effect; W7 owns the generalized VG-013 path.
- E2 claims are limited to source-tree hash unchanged, runner-observed unauthorized fixture effects 0, and public result secret-pattern occurrences 0. OS protected reads, network calls, and full external writes remain `null`/`not_observed`.
- Do not add dependencies. Do not push, create a PR, access protected data, call external services, deploy, or perform destructive Git operations.
- Every task follows RED→GREEN TDD, runs its focused tests, receives an independent requirements/quality review, and ends with an intentional commit.

---

## File Map

### New files

| Path | Responsibility |
| --- | --- |
| `contracts/forgeops-local-vertical/1.0/schema.json` | Closed Draft 2020-12 schema for the fixture suite and registered public result |
| `fixtures/forgeops-local-vertical/suite.json` | Exact ordered VG-012 positive/negative case catalog and trusted fixture inputs |
| `tools/local_vertical/__init__.py` | Public actor/verifier exports only |
| `tools/local_vertical/common.py` | Stable error, frozen JSON, canonical identity, authority, evidence, hashing, and atomic-write primitives |
| `tools/local_vertical/main_actor.py` | Product bridge normalization, actor-scoped TaskPackets, candidate approval, WorkResult validation, MainDecision |
| `tools/local_vertical/part_actor.py` | W5 provenance-bound read-only discovery and CandidatePacket production |
| `tools/local_vertical/work_actor.py` | Trusted-context preflight, bounded fixture mutation, verification, WorkResult production |
| `tools/local_vertical/verify.py` | Registered VG-012 CLI, fixture mutations, effect audit, result assembly |
| `tests/local_vertical/__init__.py` | Test package marker |
| `tests/local_vertical/test_contracts.py` | Schema, case catalog, adapter registration, WBS re-scope tests |
| `tests/local_vertical/test_main_actor.py` | Main normalization, routing, trusted context, decision/state/evidence tests |
| `tests/local_vertical/test_part_actor.py` | Part read/provenance/identity/ownership tests |
| `tests/local_vertical/test_work_actor.py` | Work preflight, exact fixture effect, evidence and zero-effect rejection tests |
| `tests/local_vertical/test_verify.py` | End-to-end registered CLI, atomic result, hashes, counters, safe-output tests |
| `artifacts/verification/vg-012-local-vertical-result.json` | Fresh registered E2 result generated only after implementation passes |

### Modified files

| Path | Responsibility |
| --- | --- |
| `AGENTS.md` | Register `main-part-work-main` and `forgeops-local-vertical` |
| `docs/project/wbs.md` | Exact WBS-014/WBS-018 re-scope, capacity note, W6 status/evidence |
| `docs/product/prd.md` | Mark PRD-FR-010 implemented only after VG-012 passes |
| `docs/architecture/system-architecture.md` | Record local ARC-004 kernel subset evidence while keeping ARC-004 `PLANNED` |
| `docs/project/requirements-traceability-matrix.md` | Attach fresh VG-012 E2 evidence and update PRD-FR-010 result |
| `docs/quality/verification-and-evaluation-plan.md` | Register actual result status and retain Phase 1 Exit blockers |
| `README.md` | Report W6 local vertical capability without claiming VG-013 or Phase 1 Exit |

---

### Task 1: Contract Baseline, Registered Identity, and WBS Re-scope

**Files:**
- Create: `contracts/forgeops-local-vertical/1.0/schema.json`
- Create: `fixtures/forgeops-local-vertical/suite.json`
- Create: `tests/local_vertical/__init__.py`
- Create: `tests/local_vertical/test_contracts.py`
- Modify: `AGENTS.md`
- Modify: `docs/project/wbs.md`

**Interfaces:**
- Consumes: Product Contract schema ID `forgeops.task-contract`/`1.0`, W5 snapshot and Context Pack schema refs, Protocol 2.0 packet names.
- Produces: ordered `CASE_IDS`, suite schema, exact CLI identity `main-part-work-main`, verification profile `forgeops-local-vertical`, final WBS-014/WBS-018 row meanings used by Tasks 2~5.

- [ ] **Step 1: Add failing contract and planning tests**

Create `tests/local_vertical/test_contracts.py` with exact checks:

```python
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/forgeops-local-vertical/1.0/schema.json"
SUITE = ROOT / "fixtures/forgeops-local-vertical/suite.json"
WBS_COLUMNS = (
    "id", "phase", "week", "status", "person_day", "predecessor",
    "prd_ids", "deliverable", "definition_of_done", "vg_ids", "evidence_types",
)

CASE_IDS = (
    "POSITIVE_MAIN_PART_WORK_MAIN",
    "POSITIVE_GATE_WAITING",
    "NEGATIVE_MAIN_PROTOCOL",
    "NEGATIVE_PART_ENVELOPE_MISMATCH",
    "NEGATIVE_PART_READ_NONE",
    "NEGATIVE_CONTEXT_HASH_MISMATCH",
    "NEGATIVE_PART_STATE_OWNERSHIP",
    "NEGATIVE_PROTECTED_NO_APPROVAL",
    "NEGATIVE_APPROVAL_WITHOUT_AUTHORITY",
    "NEGATIVE_HYBRID_IDENTITY",
    "NEGATIVE_SCOPE_LIST_MISMATCH",
    "NEGATIVE_WORK_ENVELOPE_MISMATCH",
    "NEGATIVE_WORK_MODE_EXPLORE",
    "NEGATIVE_WORK_CAPABILITY_UNKNOWN",
    "NEGATIVE_TRUST_APPROVED_ID_INJECTION",
    "NEGATIVE_TRUST_VALIDATION_AT_INJECTION",
    "NEGATIVE_PROJECT_EXECUTE_SCOPE",
    "NEGATIVE_WILDCARD_COMPANION",
    "NEGATIVE_RESOURCE_TRAVERSAL",
    "NEGATIVE_UNSUPPORTED_COMMAND",
    "NEGATIVE_WORK_STALE_REVISION",
    "NEGATIVE_WORK_STATE_OWNERSHIP",
    "NEGATIVE_EVIDENCE_DANGLING",
    "NEGATIVE_EVIDENCE_STALE",
    "NEGATIVE_EVIDENCE_FUTURE",
    "NEGATIVE_EVIDENCE_LOW_TIER",
    "NEGATIVE_CANDIDATE_COVERAGE",
    "NEGATIVE_CRITERION_COVERAGE",
    "NEGATIVE_SUMMARY_MISMATCH",
    "NEGATIVE_MAIN_ACTOR_OWNERSHIP",
)

def parse_wbs_rows() -> dict[str, dict[str, str]]:
    records = {}
    for line in (ROOT / "docs/project/wbs.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("| WBS-"):
            continue
        values = tuple(value.strip() for value in line.strip("|").split("|"))
        if len(values) == len(WBS_COLUMNS):
            record = dict(zip(WBS_COLUMNS, values, strict=True))
            records[record["id"]] = record
    return records

def comma_ids(raw: str) -> tuple[str, ...]:
    return tuple(value.strip() for value in raw.split(",") if value.strip())

class LocalVerticalContractTests(unittest.TestCase):
    def test_schema_and_suite_are_closed_and_exact(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertFalse(schema["additionalProperties"])
        Draft202012Validator.check_schema(schema)
        self.assertEqual([], list(Draft202012Validator(schema).iter_errors(suite)))
        self.assertEqual(CASE_IDS, tuple(case["id"] for case in suite["cases"]))
        self.assertEqual(len(CASE_IDS), len(set(CASE_IDS)))

    def test_wbs_rows_reassign_exact_contract_ownership_to_w6_and_w7(self):
        rows = parse_wbs_rows()
        self.assertEqual("WBS_DONE", rows["WBS-014"]["status"])
        self.assertEqual(("PRD-FR-008", "PRD-NFR-001"), comma_ids(rows["WBS-014"]["prd_ids"]))
        self.assertEqual(("VG-010",), comma_ids(rows["WBS-014"]["vg_ids"]))
        self.assertEqual(
            ("PRD-FR-010", "PRD-NFR-002", "PRD-NFR-003"),
            comma_ids(rows["WBS-018"]["prd_ids"]),
        )
        self.assertEqual(
            ("VG-005", "VG-006", "VG-012"),
            comma_ids(rows["WBS-018"]["vg_ids"]),
        )
        self.assertEqual(("VG-013",), comma_ids(rows["WBS-021"]["vg_ids"]))
        self.assertEqual(("VG-013",), comma_ids(rows["WBS-022"]["vg_ids"]))

```

- [ ] **Step 2: Run the focused tests and observe RED**

Run:

```powershell
python -m unittest tests.local_vertical.test_contracts -v
```

Expected: FAIL because the schema, suite, and structurally re-scoped WBS rows do not exist yet.

- [ ] **Step 3: Create the closed suite/result schema and exact fixture catalog**

Create a Draft 2020-12 schema with these exact top-level suite fields:

```json
{
  "suite_id": "forgeops-local-vertical-v1",
  "suite_version": "1.0",
  "schema_ref": "contracts/forgeops-local-vertical/1.0/schema.json",
  "product_schema_ref": "contracts/product-task-contract/1.0/schema.json",
  "snapshot_schema_ref": "contracts/forgeops-snapshot-contract/1.0/schema.json",
  "context_schema_ref": "contracts/forgeops-context-pack/1.0/schema.json",
  "base_fixture": {},
  "cases": []
}
```

The schema must close the suite, base fixture, every case, trusted bridge context, accepted state, snapshot manifest, Context Pack, and expected outcome. A case has exactly `id`, `kind`, `mutation`, and one of `expected_result` or `expected_error`. The public result definition must close these fields: `result_version`, `gate_id`, `profile_id`, `command_id`, `status`, `evidence_tier`, `observed_at`, `input_hashes`, `summary`, `effect_counters`, and `cases`.

Create the suite with `CASE_IDS` in the exact order above. Use one public-safe base fixture:

```json
{
  "accepted_state": {"task_id":"TASK-W6-FIXTURE","correlation_id":"CORR-W6-FIXTURE","revision":1,"status":"IN_PROGRESS","next_seq":7},
  "fixture_resource": {"path":"fixture/work-item.txt","before":"before\n","after":"after\n"},
  "validation_at":"2026-08-02T00:05:00Z",
  "candidate_evidence_floor":"E2",
  "human_review_result":null
}
```

The Product Contract objective must say that `fixture/work-item.txt` changes from `before` to `after`; its one criterion ID is `AC-W6-1`. The trusted authority must use `read_scope=PROJECT`, empty `read_resources`, `write_scope=NAMED_RESOURCES`, exact `write_resources=["fixture/work-item.txt"]`, `execute_scope=NONE`, empty `execute_commands`, `network_scope=NONE`, and empty `network_hosts`.

- [ ] **Step 4: Register the exact command and profile**

Add this validation record to `AGENTS.md`:

```yaml
- id: main-part-work-main
  command: python tools/local_vertical/verify.py --schema contracts/forgeops-local-vertical/1.0/schema.json --product-schema contracts/product-task-contract/1.0/schema.json --snapshot-schema contracts/forgeops-snapshot-contract/1.0/schema.json --context-schema contracts/forgeops-context-pack/1.0/schema.json --suite fixtures/forgeops-local-vertical/suite.json --result artifacts/verification/vg-012-local-vertical-result.json --command-id main-part-work-main
  cwd: "."
  evidence_tier: E2
  required: true
```

Add profile `forgeops-local-vertical` containing only `main-part-work-main`.

Do not add a source-text assertion for `AGENTS.md`. Task 5 consumes this registration by running the exact command and verifying its result identity, exit code, and output artifact.

- [ ] **Step 5: Apply the exact WBS re-scope and capacity note**

Change WBS-014 to `WBS_DONE`, PRD IDs `PRD-FR-008, PRD-NFR-001`, and VG IDs `VG-010`. Its DoD must say snapshot-bound exact baseline profile, repeatable health artifact, baseline/runner-failure distinction, and explicitly not claim changed-task regression.

Change WBS-018 to PRD IDs `PRD-FR-010, PRD-NFR-002, PRD-NFR-003`, deliverable `bounded Work preflight, fixture execution and WorkResult`, and VG IDs `VG-005, VG-006, VG-012`.

Add an acceptance note recording: cycle removal reason, W5/W6/W7 impact, unchanged W5 and W6 4.0 person-day plans, and retained W7 WBS-021/022 2.5 person-day scope.

- [ ] **Step 6: Run focused and existing WBS evidence tests**

Run:

```powershell
python -m unittest tests.local_vertical.test_contracts -v
python -m unittest tests.snapshot_context.test_contracts tests.snapshot_context.test_verify -v
```

Expected: PASS with no new skip and no W5 regression.

- [ ] **Step 7: Independently review Task 1 and commit**

Reviewer checks exact case order, closed schema, registered command/path equality, WBS row semantics, W7 VG-013 retention, and capacity note.

```powershell
git add AGENTS.md docs/project/wbs.md contracts/forgeops-local-vertical/1.0/schema.json fixtures/forgeops-local-vertical/suite.json tests/local_vertical/__init__.py tests/local_vertical/test_contracts.py
git commit -m "feat: define W6 local vertical contract"
```

---

### Task 2: Main Product Normalization and Actor Routing

**Files:**
- Create: `tools/local_vertical/__init__.py`
- Create: `tools/local_vertical/common.py`
- Create: `tools/local_vertical/main_actor.py`
- Create: `tests/local_vertical/test_main_actor.py`

**Interfaces:**
- Consumes: `contract_bridge.verify.validate_and_map`, trusted bridge context, Product Contract schema, accepted revision, correlation ID.
- Produces: `normalize_product_task(contract, bridge_context, product_schema, correlation_id) -> dict[str, object]`, `build_part_task(task_packet) -> dict[str, object]`, `VerticalFlowError.code`, canonical/frozen JSON and authority helpers used by Tasks 3~5.

- [ ] **Step 1: Write failing Main normalization and routing tests**

Add tests that assert canonical envelope and fail-closed defaults:

```python
class MainNormalizationTests(unittest.TestCase):
    def test_change_normalizes_to_part_explore_task(self):
        packet = main_actor.normalize_product_task(
            self.contract,
            self.bridge_context,
            self.product_schema,
            correlation_id="CORR-W6-FIXTURE",
        )
        self.assertEqual("2.0", packet["protocol_version"])
        self.assertEqual("task", packet["packet_type"])
        self.assertEqual("main", packet["actor"])
        self.assertEqual(1, packet["base_revision"])
        self.assertEqual("PART_THEN_WORK", packet["payload"]["control"]["route"])
        self.assertEqual("EXPLORE", packet["payload"]["control"]["operation_mode"])
        self.assertEqual([], packet["payload"]["request"]["assumptions"])

    def test_missing_safety_capability_becomes_unknown(self):
        del self.bridge_context["canonical_control"]["capabilities"]["network"]
        packet = main_actor.normalize_product_task(
            self.contract, self.bridge_context, self.product_schema,
            correlation_id="CORR-W6-FIXTURE",
        )
        self.assertEqual("UNKNOWN", packet["payload"]["capabilities"]["network"])

    def test_unknown_protocol_and_scope_list_mismatch_fail_closed(self):
        self.contract["schema_version"] = "9.0"
        with self.assertRaisesRegex(common.VerticalFlowError, "MAIN_CONTRACT_VERSION_UNSUPPORTED"):
            main_actor.normalize_product_task(
                self.contract, self.bridge_context, self.product_schema,
                correlation_id="CORR-W6-FIXTURE",
            )
```

Also test duplicate/wildcard/traversal companion values, PROJECT with a non-empty list, PROJECT execute/network, malformed correlation ID, and input mutation after return not changing the TaskPacket.

- [ ] **Step 2: Run Main tests and observe RED**

```powershell
python -m unittest tests.local_vertical.test_main_actor.MainNormalizationTests -v
```

Expected: FAIL because `common.py` and `main_actor.py` do not exist.

- [ ] **Step 3: Implement immutable JSON and exact authority primitives**

In `common.py`, implement these signatures:

```python
class VerticalFlowError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

def freeze_json(value: object) -> object:
    if isinstance(value, dict):
        return MappingProxyType({key: freeze_json(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(freeze_json(child) for child in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise VerticalFlowError("JSON_VALUE_INVALID")

def thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(child) for child in value]
    return value

def canonical_resource_ref(raw: object) -> str:
    if not isinstance(raw, str) or not raw or "\\" in raw or "*" in raw:
        raise VerticalFlowError("RESOURCE_IDENTITY_NONCANONICAL")
    path = PurePosixPath(raw)
    if path.is_absolute() or ".." in path.parts or any(part in ("", ".") for part in path.parts):
        raise VerticalFlowError("RESOURCE_IDENTITY_NONCANONICAL")
    return raw
```

Implement `validate_authority(authority)` with separate RESOURCE PROJECT/NAMED branches and exact closed companion arrays. `execute_scope` accepts only NONE/NAMED_COMMANDS/UNKNOWN; `network_scope` accepts only NONE/NAMED_HOSTS/UNKNOWN. NONE/UNKNOWN require empty lists. Reject non-list, empty named list, duplicate, wildcard, traversal, case-normalization attempts, and inconsistent scope/list pairs with stable `AUTHORITY_*` codes.

- [ ] **Step 4: Implement Product bridge normalization and actor-scoped TaskPacket**

In `main_actor.py`, call the existing W1 bridge on deep copies, then build the Protocol envelope:

```python
def normalize_product_task(contract, bridge_context, product_schema, *, correlation_id):
    validator = Draft202012Validator(copy.deepcopy(product_schema))
    try:
        mapped = validate_and_map(
            copy.deepcopy(contract), copy.deepcopy(bridge_context), validator,
            canonical_sha256(contract),
        )
    except BridgeError as exc:
        raise VerticalFlowError(f"MAIN_{exc.code}") from exc
    capabilities = normalize_capabilities(mapped["capabilities"])
    authority = validate_authority(mapped["authority"])
    payload = {
        "request": normalize_request(mapped["request"]),
        "project_profile": normalize_project_profile(mapped["project_profile"]),
        "capabilities": capabilities,
        "authority": authority,
        "control": normalize_control(mapped["control"], route="PART_THEN_WORK", operation_mode="EXPLORE"),
        "budgets": normalize_budgets(mapped["budgets"]),
    }
    return {
        "protocol_version": "2.0", "packet_type": "task",
        "task_id": mapped["task_id"], "correlation_id": require_id(correlation_id),
        "base_revision": mapped["accepted_state"]["revision"],
        "actor": "main", "status": "IN_PROGRESS", "payload": payload,
    }
```

`normalize_request` adds only `assumptions=[]`; `normalize_project_profile` supplies only missing canonical fields (`instruction_files=[]`, `validation_commands=[]`, `extensions={}`) without changing existing values. `normalize_capabilities` supplies `UNKNOWN` for missing enum keys. `build_part_task` returns a deep copy that preserves base revision and forces only `route=PART_THEN_WORK`, `operation_mode=EXPLORE`.

- [ ] **Step 5: Run Main and W1 bridge tests GREEN**

```powershell
python -m unittest tests.local_vertical.test_main_actor.MainNormalizationTests -v
python -m unittest tests.contract_bridge.test_verify -v
```

Expected: PASS; W1 bridge semantics remain unchanged.

- [ ] **Step 6: Independently review Task 2 and commit**

Reviewer checks lossless request mapping, UNKNOWN fail-close behavior, no adapter-granted authority, exact route/mode, original inputs unchanged, and no accepted-state mutation.

```powershell
git add tools/local_vertical/__init__.py tools/local_vertical/common.py tools/local_vertical/main_actor.py tests/local_vertical/test_main_actor.py
git commit -m "feat: add W6 Main normalization and routing"
```

---

### Task 3: Part Provenance-Bound Read-Only Candidate Proposal

**Files:**
- Create: `tools/local_vertical/part_actor.py`
- Create: `tests/local_vertical/test_part_actor.py`
- Modify: `tools/local_vertical/__init__.py`

**Interfaces:**
- Consumes: `build_part_task` output, W5 snapshot manifest, W5 Context Pack.
- Produces: `propose_candidates(task_packet, snapshot_manifest, context_pack) -> dict[str, object]` returning a canonical CandidatePacket with one RESOURCE candidate or a stable blocked/contract outcome.

- [ ] **Step 1: Write failing Part boundary tests**

```python
class PartActorTests(unittest.TestCase):
    def test_proposes_one_exact_read_only_candidate(self):
        before = canonical_json_bytes(self.context_pack)
        packet = part_actor.propose_candidates(
            self.task_packet, self.snapshot_manifest, self.context_pack
        )
        self.assertEqual("candidate_proposal", packet["packet_type"])
        self.assertEqual("part", packet["actor"])
        self.assertEqual("CANDIDATES_PROPOSED", packet["payload"]["outcome_code"])
        candidate = packet["payload"]["candidates"][0]
        self.assertEqual("UPDATE_RESOURCE", candidate["action_type"])
        self.assertEqual(
            {"identity_kind":"RESOURCE", "resource_ref":"fixture/work-item.txt"},
            candidate["action_identity"],
        )
        self.assertEqual(before, canonical_json_bytes(self.context_pack))
        self.assertNotIn("accepted_state", packet["payload"])
        self.assertNotIn("revision", packet["payload"])
        self.assertNotIn("seq", packet["payload"])

    def test_context_snapshot_or_item_hash_mismatch_is_contract_error(self):
        self.context_pack["snapshot_id"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(common.VerticalFlowError, "PART_CONTEXT_PROVENANCE_INVALID"):
            part_actor.propose_candidates(
                self.task_packet, self.snapshot_manifest, self.context_pack
            )

    def test_none_read_scope_returns_zero_effect_blocked_proposal(self):
        self.task_packet["payload"]["authority"]["read_scope"] = "NONE"
        packet = part_actor.propose_candidates(
            self.task_packet, self.snapshot_manifest, self.context_pack
        )
        self.assertEqual("BLOCKED_PROPOSAL", packet["payload"]["outcome_code"])
        self.assertEqual([], packet["payload"]["candidates"])
        self.assertEqual("WAITING_FOR_HUMAN", packet["payload"]["proposed_transition"])
```

Add tests for protocol/packet/actor/task/correlation/base mismatches, operation mode not EXPLORE, control claim promotion, non-list items, duplicate evidence IDs/refs, hybrid identity construction, protected target with missing/forged approval, and approval without exact write authority.

- [ ] **Step 2: Run Part tests and observe RED**

```powershell
python -m unittest tests.local_vertical.test_part_actor -v
```

Expected: FAIL because `part_actor.py` does not exist.

- [ ] **Step 3: Implement envelope, Context Pack provenance, and protected-path checks**

Implement validation in this exact order:

```python
def propose_candidates(task_packet, snapshot_manifest, context_pack):
    validate_task_envelope(task_packet, required_mode="EXPLORE")
    authority = validate_authority(task_packet["payload"]["authority"])
    if authority["read_scope"] in ("NONE", "UNKNOWN"):
        return build_blocked_candidate_packet(task_packet, "PART_READ_AUTHORITY_DENIED")
    validate_snapshot_context(snapshot_manifest, context_pack)
    item = select_exact_item(context_pack, "fixture/work-item.txt")
    if is_protected_resource(item["path"]):
        return build_blocked_candidate_packet(task_packet, "PART_PROTECTED_APPROVAL_REQUIRED")
    require_exact_write_candidate_authority(authority, item["path"])
    return build_candidate_packet(task_packet, item)
```

`validate_snapshot_context` requires matching `snapshot_id`, `control_claims_accepted is False`, one manifest entry with the same path/sha256/size, and exact canonical path. Part reads only the passed immutable values and performs no filesystem writes or commands.

`build_blocked_candidate_packet` returns actor=`part`, packet_type=`candidate_proposal`, status=`BLOCKED`, outcome=`BLOCKED_PROPOSAL`, an empty candidate array, explicit `missing_authority`/`recommended_next_action=ASK_USER`, and proposed transition `WAITING_FOR_HUMAN`. A forged approval field inside Context Pack is a contract error; a valid human approval without exact read/write authority remains blocked.

- [ ] **Step 4: Build the canonical CandidatePacket**

Use candidate ID `CAND-W6-UPDATE`, E1 file evidence ID `EVID-PART-CONTEXT`, observed revision equal to TaskPacket base revision, confidence `1.0`, confidence basis `DIRECT`, operation `update`, expected effect `replace fixture marker before with after`, precondition containing the selected item sha256, verification `fixture content equals UTF-8 after newline`, and acceptance criterion ID `AC-W6-1`.

Return only `assertion_suggestions`, `event_suggestions` without authoritative state. A proposed candidate includes exactly one event suggestion with actor=`part`, phase=`DISCOVER`, code=`PART_CANDIDATE_PROPOSED`; a blocked proposal uses code=`PART_PROPOSAL_BLOCKED`. Event suggestions contain no `seq`.

- [ ] **Step 5: Run Part, W5 context, and authority regressions GREEN**

```powershell
python -m unittest tests.local_vertical.test_part_actor -v
python -m unittest tests.snapshot_context.test_retrieval tests.snapshot_context.test_contracts -v
python -m unittest tests.policy_contract.test_resource -v
```

Expected: PASS with no filesystem mutation.

- [ ] **Step 6: Independently review Task 3 and commit**

Reviewer checks Part read-only behavior, exact W5 provenance, protected target denial, approval-not-authority, CandidatePacket evidence resolution, no accepted state/revision/seq, and no input mutation.

```powershell
git add tools/local_vertical/__init__.py tools/local_vertical/part_actor.py tests/local_vertical/test_part_actor.py
git commit -m "feat: add W6 Part candidate proposal"
```

---

### Task 4: Main Trusted Approval Context and Work Preflight/Execution/Verification

**Files:**
- Modify: `tools/local_vertical/common.py`
- Modify: `tools/local_vertical/main_actor.py`
- Create: `tools/local_vertical/work_actor.py`
- Create: `tests/local_vertical/test_work_actor.py`
- Modify: `tests/local_vertical/test_main_actor.py`
- Modify: `tools/local_vertical/__init__.py`

**Interfaces:**
- Consumes: TaskPacket, CandidatePacket, exact approved candidate IDs, runtime validation time, verifier-owned separated workspace.
- Produces: immutable `TrustedExecutionContext`, `approve_candidates(task_packet, candidate_packet, *, approved_candidate_ids, validation_at, human_review_result) -> TrustedExecutionContext`, `preflight_execute_verify(context, *, workspace_root, source_root, clock) -> dict[str, object]` returning WorkResult.

- [ ] **Step 1: Write failing trusted-context and Work success tests**

```python
class WorkActorTests(unittest.TestCase):
    def test_exact_approved_fixture_update_returns_fresh_e2_work_result(self):
        context = main_actor.approve_candidates(
            self.task_packet, self.candidate_packet,
            approved_candidate_ids=["CAND-W6-UPDATE"],
            validation_at="2026-08-02T00:05:00Z",
            human_review_result=None,
        )
        result = work_actor.preflight_execute_verify(
            context, workspace_root=self.workspace,
            source_root=self.source,
            clock=lambda: "2026-08-02T00:05:00Z",
        )
        self.assertEqual(b"after\n", (self.workspace / "fixture/work-item.txt").read_bytes())
        self.assertEqual(b"before\n", (self.source / "fixture/work-item.txt").read_bytes())
        self.assertEqual("work_result", result["packet_type"])
        self.assertEqual("work", result["actor"])
        self.assertEqual("SUCCEEDED", result["status"])
        self.assertEqual("E2", result["payload"]["evidence"][0]["tier"])

    def test_context_is_immutable_and_packet_injection_cannot_shadow_it(self):
        context = self.approved_context()
        with self.assertRaises(TypeError):
            context.approved_candidate_ids[0] = "CAND-INJECTED"
        self.candidate_packet["payload"]["approved_candidate_ids"] = ["CAND-INJECTED"]
        result = work_actor.preflight_execute_verify(
            context, workspace_root=self.workspace,
            source_root=self.source,
            clock=lambda: "2026-08-02T00:05:00Z",
        )
        self.assertEqual(["CAND-W6-UPDATE"], result["payload"]["approved_candidate_ids"])
```

Add zero-effect tests for unapproved/unknown/duplicate IDs, stale base revision, task/correlation mismatch, EXPLORE mode, filesystem_write UNKNOWN, NAMED authority miss, PROJECT execute/network, wildcard/traversal, protected path, source-root target, unsupported COMMAND/NETWORK, forged `validationAt`, and candidate state/revision/seq ownership.

- [ ] **Step 2: Run focused Work tests and observe RED**

```powershell
python -m unittest tests.local_vertical.test_work_actor -v
```

Expected: FAIL because trusted context and Work actor are not implemented.

- [ ] **Step 3: Implement the immutable non-packet trusted execution context**

Add to `common.py`:

```python
@dataclass(frozen=True)
class TrustedExecutionContext:
    task_packet: object
    candidate_packet: object
    current_revision: int
    approved_candidate_ids: tuple[str, ...]
    approved_candidates: object
    authority: object
    candidate_evidence_floor: str
    acceptance_criteria: object
    validation_at: str
    human_review_result: object | None
```

Every JSON field is passed through `freeze_json`; callers can inspect only with `thaw_json`. Validate UTC `validation_at` once in Main. This class has no `protocol_version`, `packet_type`, `actor`, or `status` and must never serialize as a fifth packet.

Implement `approve_candidates` to validate CandidatePacket envelope/base revision, exact candidate coverage and evidence refs, ordinal approved IDs, exact action identity/authority, and current accepted revision. It creates a Work-scoped TaskPacket copy with `route=WORK_ONLY`, `operation_mode=EXECUTE` and otherwise preserves canonical fields.

- [ ] **Step 4: Implement Work preflight in stable order**

In `work_actor.py`, perform these checks before opening the target:

```python
def preflight_execute_verify(context, *, workspace_root, source_root, clock):
    task = thaw_json(context.task_packet)
    candidate_packet = thaw_json(context.candidate_packet)
    validate_work_task(task, context.current_revision)
    candidates = validate_approved_coverage(candidate_packet, context)
    candidate = candidates[0]
    validate_action_identity(candidate)
    validate_authority(thaw_json(context.authority))
    target = contained_workspace_target(workspace_root, candidate["action_identity"]["resource_ref"])
    reject_source_target(target, source_root)
    return execute_fixture_update(task, candidate, target, context, clock)
```

`contained_workspace_target` resolves the existing workspace root and target, rejects traversal/symlink/reparse escape, and confirms the target is not under source root. W6 accepts only `UPDATE_RESOURCE`, resource `fixture/work-item.txt`, exact bytes `before\n`, and no command/network candidate.

- [ ] **Step 5: Implement bounded effect and canonical WorkResult**

Write `after\n` through a sibling temporary file followed by `os.replace`. Verify exact bytes immediately. Build one E2 test evidence record with runtime-supplied UTC `observed_at`; reference it from the accepted candidate result and passed `AC-W6-1`. Set `validation_summary={"passed":1,"failed":0,"not_run":0}` and `proposed_transition="SUCCEEDED"`.

The WorkResult must contain no `accepted_state`, `revision`, authoritative `events`, or event `seq`; only `event_suggestions` are allowed. A successful WorkResult contains exactly one suggestion with actor=`work`, phase=`VERIFY`, code=`WORK_VERIFICATION_PASSED`. On any preflight error, target/source bytes remain unchanged.

- [ ] **Step 6: Run Work, Main, authority, and source-containment tests GREEN**

```powershell
python -m unittest tests.local_vertical.test_main_actor tests.local_vertical.test_work_actor -v
python -m unittest tests.policy_contract.test_resource tests.policy_contract.test_command_network -v
python -m unittest tests.snapshot_context.test_snapshot -v
```

Expected: PASS; optional Windows symlink tests may retain their existing skip behavior.

- [ ] **Step 7: Independently review Task 4 and commit**

Reviewer checks context is non-packet and immutable, Work mode/capability/authority/current revision are exact, source containment is enforced before effect, unsupported action types are zero-effect, evidence is fresh E2, and Work owns no accepted state/seq.

```powershell
git add tools/local_vertical/__init__.py tools/local_vertical/common.py tools/local_vertical/main_actor.py tools/local_vertical/work_actor.py tests/local_vertical/test_main_actor.py tests/local_vertical/test_work_actor.py
git commit -m "feat: add W6 trusted Work execution"
```

---

### Task 5: Main Acceptance, Registered VG-012, and Evidence-Grounded Closure

**Files:**
- Modify: `tools/local_vertical/main_actor.py`
- Create: `tools/local_vertical/verify.py`
- Modify: `tools/local_vertical/__init__.py`
- Modify: `tests/local_vertical/test_main_actor.py`
- Create: `tests/local_vertical/test_verify.py`
- Create: `artifacts/verification/vg-012-local-vertical-result.json`
- Modify: `docs/project/wbs.md`
- Modify: `docs/product/prd.md`
- Modify: `docs/architecture/system-architecture.md`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/quality/verification-and-evaluation-plan.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: WorkResult and immutable trusted context from Task 4, current accepted state `{task_id, correlation_id, revision, status, next_seq}`.
- Produces: `validate_and_decide(work_result, context, accepted_state) -> MainDecision`, `decide_candidate_gate(candidate_packet, accepted_state) -> MainDecision`, registered CLI `verify.run(args, repository_root=...) -> int`, fresh VG-012 result, evidence-grounded document status.

- [ ] **Step 1: Write failing Main acceptance/state/evidence tests**

```python
class MainDecisionTests(unittest.TestCase):
    def test_fresh_complete_work_result_is_the_only_success_path(self):
        decision = main_actor.validate_and_decide(
            self.work_result, self.context, self.accepted_state
        )
        self.assertEqual("main_decision", decision["packet_type"])
        self.assertEqual("main", decision["actor"])
        accepted = decision["payload"]["accepted_state"]
        self.assertEqual(2, accepted["revision"])
        self.assertEqual("SUCCEEDED", accepted["status"])
        self.assertEqual([7, 8], [event["seq"] for event in decision["payload"]["events"]])

    def test_stale_or_invalid_result_has_zero_accepted_effect(self):
        self.work_result["base_revision"] = 0
        before = canonical_json_bytes(self.accepted_state)
        with self.assertRaisesRegex(common.VerticalFlowError, "MAIN_WORK_REVISION_STALE"):
            main_actor.validate_and_decide(
                self.work_result, self.context, self.accepted_state
            )
        self.assertEqual(before, canonical_json_bytes(self.accepted_state))

    def test_blocked_part_proposal_can_gate_waiting_for_human(self):
        decision = main_actor.decide_candidate_gate(
            self.blocked_candidate_packet, self.accepted_state
        )
        self.assertEqual("GATE", decision["payload"]["decision"])
        self.assertEqual("WAITING_FOR_HUMAN", decision["payload"]["accepted_state"]["status"])
        self.assertEqual(2, decision["payload"]["accepted_state"]["revision"])
        self.assertEqual([7], [event["seq"] for event in decision["payload"]["events"]])
```

Add tests for actor/task/correlation mismatch, missing/duplicate/unknown candidate and criterion coverage, scalar refs, dangling/duplicate refs, wrong freshness mode, stale/future timestamps, E1 tier, summary mismatch, Work state/revision/seq ownership, Main actor ownership, and canonical GATE→WAITING_FOR_HUMAN acceptance with one revision increment.

- [ ] **Step 2: Run Main decision tests and observe RED**

```powershell
python -m unittest tests.local_vertical.test_main_actor.MainDecisionTests -v
```

Expected: FAIL because `validate_and_decide` does not exist.

- [ ] **Step 3: Implement closed WorkResult validation and MainDecision**

Validate in this stable order: trusted context/envelope identity; closed status/transition; raw top-level arrays; ordinal candidate coverage/decisions/refs; criterion coverage/status/refs; evidence catalog/references; freshness; E2 floors; summary counts; success invariants; forbidden ownership fields.

Use the trusted `validation_at`, never a WorkResult timestamp, as the clock anchor. File/diff evidence accepts only matching integer `observed_revision`; command/test/render/runtime/approval accepts only strict UTC `observed_at` aged 0..300 seconds.

On accepted transition:

```python
new_revision = accepted_state["revision"] + 1
next_seq = accepted_state["next_seq"]
events = []
for offset, suggestion in enumerate(validated_event_suggestions):
    event = normalize_event(suggestion)
    event["seq"] = next_seq + offset
    events.append(event)
```

For Work success, `validated_event_suggestions` is the ordered Part suggestion frozen in the trusted CandidatePacket followed by the Work suggestion, producing seq 7 and 8 and accepted `next_seq=9` in the base fixture. `decide_candidate_gate` accepts only a valid `BLOCKED_PROPOSAL` with `recommended_next_action=ASK_USER`, assigns its one blocked suggestion seq 7, and transitions IN_PROGRESS→WAITING_FOR_HUMAN with revision 2 and `next_seq=8`.

Return MainDecision status/proposed state consistent with the canonical transition. Set `accepted_payload_ref` to `sha256:` plus canonical source packet bytes. Do not change the caller's accepted-state mapping. Malformed/stale/validation-rejected results raise before any authoritative output.

- [ ] **Step 4: Write failing registered verifier tests**

```python
class LocalVerticalVerifierTests(unittest.TestCase):
    def test_registered_run_writes_closed_public_safe_result_atomically(self):
        args = namespace()
        result_path = self.repository / args.result
        result_path.parent.mkdir(parents=True)
        result_path.write_text("preserve until replace", encoding="utf-8")
        self.assertEqual(0, verify.run(args, repository_root=self.repository))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual("PASSED", result["status"])
        self.assertEqual("E2", result["evidence_tier"])
        self.assertEqual(30, result["summary"]["total"])
        self.assertTrue(result["effect_counters"]["source_tree_hash_unchanged"])
        self.assertEqual(0, result["effect_counters"]["unauthorized_fixture_effects"])
        self.assertEqual(0, result["effect_counters"]["result_artifact_raw_secret_occurrences"])
        self.assertIsNone(result["effect_counters"]["protected_reads"])
        self.assertIsNone(result["effect_counters"]["network_calls"])
        self.assertIsNone(result["effect_counters"]["external_writes"])
```

Also test raw input hashes, exact command/result pairing, reordered/open catalog rejection, runner failure preserving the prior result, atomic write, no absolute host path, no raw stdout/stderr/environment/token/credential fields, and every negative case reporting its stable expected category with zero unintended fixture effect.

- [ ] **Step 5: Implement the registered end-to-end verifier**

In `verify.py`, define exact trusted identity constants and reject any argument mismatch before write. Load each input by registered root-relative path, validate schemas and exact ordered catalog, then run cases in separate `TemporaryDirectory` instances.

The main positive evaluator must call, in order:

```python
task = normalize_product_task(contract, bridge_context, product_schema, correlation_id=correlation_id)
candidate = propose_candidates(task, snapshot_manifest, context_pack)
trusted = approve_candidates(task, candidate, approved_candidate_ids=["CAND-W6-UPDATE"], validation_at=validation_at, human_review_result=None)
work = preflight_execute_verify(trusted, workspace_root=workspace, source_root=source, clock=lambda: validation_at)
decision = validate_and_decide(work, trusted, accepted_state)
```

The gate-positive evaluator changes read scope to NONE, receives `BLOCKED_PROPOSAL`, calls `decide_candidate_gate`, and asserts WAITING_FOR_HUMAN, revision 2, event seq 7, source/workspace unchanged.

Each negative case deep-copies the same baseline and applies only its named mutation. Compare actual stable error to expected error. Record `source_tree_hash_unchanged`, runner-observed unauthorized fixture effects, and result secret-pattern count. Leave unobserved OS/network/external counters `None`. Use `atomic_write_json` only after the complete result validates against the result definition.

- [ ] **Step 6: Run focused actor and VG-012 tests GREEN**

```powershell
python -m unittest tests.local_vertical.test_main_actor tests.local_vertical.test_part_actor tests.local_vertical.test_work_actor tests.local_vertical.test_verify -v
python tools/local_vertical/verify.py --schema contracts/forgeops-local-vertical/1.0/schema.json --product-schema contracts/product-task-contract/1.0/schema.json --snapshot-schema contracts/forgeops-snapshot-contract/1.0/schema.json --context-schema contracts/forgeops-context-pack/1.0/schema.json --suite fixtures/forgeops-local-vertical/suite.json --result artifacts/verification/vg-012-local-vertical-result.json --command-id main-part-work-main
```

Expected: all unit/integration tests PASS; command exit 0; result `30/30 PASSED`, E2, no failed case.

- [ ] **Step 7: Run all linked VG regressions**

Run the exact registered commands from `AGENTS.md` for:

```text
VG-002: bridge-schema-fixture
VG-003: state-transition-fixture, event-order-fixture, replay-contract-negative
VG-005: resource-authority-negative, protected-read-negative
VG-006: command-network-negative
VG-010: snapshot-identity, baseline-retrieval-repeat
VG-011: context-provenance, injection-negative
VG-023: evidence-positive-negative, extension-provenance
```

Expected: every command exits 0 and retains its registered `PASSED` result. Do not run or claim VG-013.

- [ ] **Step 8: Update evidence-owned project documentation**

Only after fresh VG-012 success:

- Set WBS-016~WBS-019 to `WBS_DONE`; keep WBS-020 onward `WBS_NOT_STARTED`.
- Keep WBS-014 `WBS_DONE` on VG-010 only and add W6 acceptance note with `main-part-work-main` case counts.
- Set PRD-FR-010 to `IMPLEMENTED` and link VG-012.
- In ARC-004, record the local orchestration kernel subset and result path but keep maturity `PLANNED` because PRD-FR-013/runtime work remains.
- In RTM, set PRD-FR-010 result `PASSED`, actual floor E2, result path, and observed_at copied from the generated result.
- In verification plan, set VG-012 actual result to PASSED while retaining VG-013, Phase 1 safety gate, and Phase 1 Exit as `NOT_RUN`.
- In README, describe W6 local vertical capability and explicitly state that OS-level external-write absence, VG-013, and Phase 1 Exit are not proven.

- [ ] **Step 9: Run full regression and documentation consistency checks**

```powershell
python -m unittest discover -s tests -v
git diff --check
git status --short
```

Expected baseline: at least 358 existing tests plus new local-vertical tests pass; only the existing optional Windows symlink tests may skip. Inspect generated result with a read-only script and assert `status=PASSED`, `evidence_tier=E2`, `summary.failed=0`, all input hashes match raw bytes, WBS-016~019 are DONE, PRD-FR-010 is PASSED, ARC-004 remains PLANNED, and no document claims VG-013 or Phase 1 Exit completion.

- [ ] **Step 10: Independently review Task 5 and the complete W6 diff**

First reviewer checks exact spec/plan coverage and WBS/PRD/VG traceability. Second reviewer checks code quality, stable error precedence, packet/state ownership, evidence freshness, effect-counter honesty, registered CLI safety, and W7 scope isolation. Resolve all blocking findings and rerun affected tests.

- [ ] **Step 11: Run verification-before-completion and commit**

Re-run the focused VG-012 command and full unittest command immediately before the completion claim. Record observed counts and skip reasons, then commit:

```powershell
git add AGENTS.md README.md contracts/forgeops-local-vertical fixtures/forgeops-local-vertical tools/local_vertical tests/local_vertical artifacts/verification/vg-012-local-vertical-result.json docs/project/wbs.md docs/product/prd.md docs/architecture/system-architecture.md docs/project/requirements-traceability-matrix.md docs/quality/verification-and-evaluation-plan.md
git commit -m "feat: complete W6 local vertical flow"
```

The final report must state changed resources, exact verification commands and counts, residual unobserved surfaces, W7/VG-013 remaining scope, branch name, and commits. Do not push or open a PR without separate explicit authority.

---

## Plan Self-Review Checklist

- [x] Every section of `2026-08-02-w6-local-main-part-work-main-design.md` maps to Task 1~5.
- [x] No task adds a fifth protocol packet; trusted execution context is Main/runtime-owned and immutable.
- [x] Function names are consistent: `normalize_product_task`, `build_part_task`, `propose_candidates`, `approve_candidates`, `preflight_execute_verify`, `validate_and_decide`, `decide_candidate_gate`.
- [x] Task 4 cannot execute until Main changes operation mode to EXECUTE and freezes exact approved IDs/current revision/authority/floors/criteria/validation time.
- [x] Task 5 assigns revision once per accepted canonical transition and seq once per accepted event; pre-acceptance rejection has zero authoritative effect.
- [x] E2 effect claims remain limited to directly observed surfaces; null values are not converted to zero.
- [x] WBS-014/WBS-018 final rows and capacity note preserve W7 VG-013 responsibility.
- [x] ARC-004 remains PLANNED; PRD-FR-010 alone becomes IMPLEMENTED/PASSED after fresh VG-012.
- [x] No placeholder wording, unbound type, unnamed test, or undefined neighboring interface remains.
