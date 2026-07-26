# W4-5 Phase 0 Exit Gate and Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggregate all 18 required Phase 0 command results into one fail-closed `READY|NOT_READY` decision and an evidence-backed public-safe Exit report.

**Architecture:** A closed phase-exit registry pins every gate/profile/command/artifact/input/floor tuple. A pure aggregator validates exact identity, current input hashes, strict freshness, status, floor, public safety, and complete coverage before building an atomic JSON decision; a renderer creates Markdown only from the closed result.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `argparse`/`datetime`/`hashlib`/`json`/`tempfile`/`unittest`, JSON Schema, Markdown

## Global Constraints

- Phase 0 requires every registered result for VG-001 through VG-009 and VG-023; 18 exact command records must be covered once each with no unknown or duplicate command.
- Required floors are E3 for VG-008 and VG-009 commands and E2 for every other Phase 0 command.
- Before aggregation, every required command must be run fresh against final inputs. Artifact `observed_at` must be strict UTC and 0 through 300 seconds old relative to trusted aggregator `validation_at`.
- `FAILED`, `NOT_RUN`, missing artifact, runtime unavailable, stale/future time, input-hash mismatch, lower floor, malformed/unsafe result, command/profile mismatch, incomplete coverage, or duplicate entry yields `NOT_READY`.
- `READY` is allowed only with 18/18 exact fresh PASSED command results and zero blockers. Qualitative review cannot override a deterministic blocker.
- The aggregator never executes validation commands, Docker, network, Git, or external effects; it only reads registered result and input files after separately authorized commands finish.
- The report contains only gate/profile/command/status/floor/time/artifact refs, counts, blockers, and residual risks. It must not copy raw cases, logs, payloads, environment, absolute paths, credentials, tokens, or secrets.
- WBS/RTM status changes occur after inspecting the final result. If result is `NOT_READY`, WBS-012 remains incomplete and Phase 0 Exit is not declared.
- Do not Git add/commit/push/PR, deploy, publish, or perform external effects.

---

## File Structure

- Create `contracts/forgeops-phase-exit-contract/1.0/schema.json`: closed registry and decision schemas.
- Create `fixtures/forgeops-phase-exit/phase-0-suite.json`: exact 18-command registry and expected Phase 0 coverage.
- Create `tools/phase_exit/__init__.py` and `tools/phase_exit/verify.py`.
- Create `tests/phase_exit/__init__.py` and `tests/phase_exit/test_verify.py`.
- Modify `AGENTS.md`: register `phase0-exit-gate` and `forgeops-phase0-exit` profile.
- Generate `artifacts/verification/phase-0-exit-result.json`.
- Generate `artifacts/reviews/phase-0-exit-report.md`.
- Modify `docs/project/wbs.md`, `docs/project/requirements-traceability-matrix.md`, and `docs/quality/verification-and-evaluation-plan.md` according to the observed result only.

### Task 1: Define the exact Phase 0 registry and closed result schema

**Files:**

- Create: `contracts/forgeops-phase-exit-contract/1.0/schema.json`
- Create: `fixtures/forgeops-phase-exit/phase-0-suite.json`
- Create: `tests/phase_exit/__init__.py`
- Create: `tests/phase_exit/test_verify.py`

**Interfaces:**

- Registry root: `suite_id`, `suite_version`, `phase_id`, `freshness_seconds`, `registrations`.
- Registration: `gate_id`, `profile_id`, `command_id`, `artifact_ref`, `required_tier`, `input_refs`, `hash_fields`.
- Decision root: `schema_version`, `phase_id`, `status`, `observed_at`, `registry_sha256`, `summary`, `gate_results`, `blockers`, `assertions`.
- Gate result: `gate_id`, `profile_id`, `command_id`, `artifact_ref`, `required_tier`, `status`, `observed_at`, `input_hashes_valid`, `public_safe`.

- [ ] **Step 1: Write failing schema-closure and exact-coverage tests**

```python
class PhaseExitSchemaTests(unittest.TestCase):
    def test_all_objects_are_closed(self):
        schema = load_schema()
        objects = [node for node in walk(schema) if node.get("type") == "object"]
        self.assertTrue(objects)
        self.assertTrue(all(node.get("additionalProperties") is False for node in objects))

class RegistryTests(unittest.TestCase):
    def test_phase_zero_registry_has_exact_18_commands(self):
        suite = load_suite()
        observed = [(r["gate_id"], r["command_id"]) for r in suite["registrations"]]
        self.assertEqual(list(verify.EXPECTED_COMMANDS), observed)
        self.assertEqual(18, len(observed))
        self.assertEqual(18, len(set(observed)))
```

- [ ] **Step 2: Run schema/registry tests and observe RED**

Run: `python -m unittest tests.phase_exit.test_verify.PhaseExitSchemaTests tests.phase_exit.test_verify.RegistryTests -v`

Expected: FAIL because schema, registry, and expected catalog do not exist.

- [ ] **Step 3: Create the closed result schema**

Use exact status enums:

```json
{
  "decision_status": ["READY", "NOT_READY"],
  "gate_status": ["PASSED", "FAILED", "NOT_RUN"],
  "tier": ["E0", "E1", "E2", "E3"]
}
```

`blockers` is an array of unique objects with exactly `gate_id`, `command_id`, and `reason_code`. `summary` has exactly non-negative integers `required`, `passed`, `failed`, `not_run`, and `blocked` whose total classifications cover all 18 registrations.

- [ ] **Step 4: Create the exact registration catalog**

Use this order:

```python
EXPECTED_COMMANDS = (
    ("VG-001", "protocol-conformance"),
    ("VG-001", "sample-fixture"),
    ("VG-002", "bridge-schema-fixture"),
    ("VG-003", "state-transition-fixture"),
    ("VG-003", "event-order-fixture"),
    ("VG-003", "replay-contract-negative"),
    ("VG-004", "interface-contract-fixture"),
    ("VG-005", "resource-authority-negative"),
    ("VG-005", "protected-read-negative"),
    ("VG-006", "command-network-negative"),
    ("VG-007", "approval-negative-fixture"),
    ("VG-008", "image-provenance-negative"),
    ("VG-008", "containment-egress-negative"),
    ("VG-008", "teardown-negative"),
    ("VG-009", "secret-surface-negative"),
    ("VG-009", "artifact-isolation-negative"),
    ("VG-023", "evidence-positive-negative"),
    ("VG-023", "extension-provenance"),
)
```

For every registration, copy the exact profile ID and artifact path from `AGENTS.md`. Set `required_tier="E3"` only for VG-008/VG-009. `input_refs` lists every schema/suite/manifest/runtime-profile input read by that command; `hash_fields` maps each input ref to the public artifact hash field used by that verifier.

- [ ] **Step 5: Run schema/registry tests**

Run: `python -m unittest tests.phase_exit.test_verify.PhaseExitSchemaTests tests.phase_exit.test_verify.RegistryTests -v`

Expected: PASS with 18 unique registrations, exact order, closed objects, and no wildcard/absolute/unregistered refs.

### Task 2: Implement fail-closed result aggregation and report rendering

**Files:**

- Create: `tools/phase_exit/__init__.py`
- Create: `tools/phase_exit/verify.py`
- Modify: `tests/phase_exit/test_verify.py`

**Interfaces:**

- `class PhaseExitError(Exception)` exposes `.code` only.
- `validate_registry(suite: dict) -> None`.
- `inspect_registration(root: Path, registration: dict, validation_at: str) -> tuple[dict, list[dict]]` returns one public gate result and zero or more blockers.
- `aggregate_phase_zero(root: Path, suite: dict, validation_at: str) -> dict`.
- `assert_public_safe(value: object) -> None`.
- `render_report(result: dict) -> str`.
- `write_text_atomically(path: Path, text: str) -> None`.

- [ ] **Step 1: Write failing missing/stale/hash/floor/unsafe tests**

```python
def test_missing_artifact_is_not_ready(self):
    root, suite = temporary_complete_bundle()
    (root / suite["registrations"][0]["artifact_ref"]).unlink()
    result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)
    self.assertEqual("NOT_READY", result["status"])
    self.assertIn("PHASE_EXIT_ARTIFACT_MISSING", blocker_codes(result))

def test_stale_and_future_results_are_not_ready(self):
    for observed_at, code in (
        ("2026-07-25T23:54:59Z", "PHASE_EXIT_EVIDENCE_STALE"),
        ("2026-07-26T00:00:01Z", "PHASE_EXIT_EVIDENCE_FUTURE"),
    ):
        with self.subTest(observed_at=observed_at):
            root, suite = temporary_complete_bundle()
            mutate_artifact(root, suite, 0, observed_at=observed_at)
            result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)
            self.assertEqual("NOT_READY", result["status"])
            self.assertIn(code, blocker_codes(result))

def test_one_not_run_sandbox_result_blocks_ready(self):
    root, suite = temporary_complete_bundle()
    mutate_command_artifact(root, suite, "teardown-negative", status="NOT_RUN")
    result = verify.aggregate_phase_zero(root, suite, VALIDATION_AT)
    self.assertEqual("NOT_READY", result["status"])
```

- [ ] **Step 2: Run aggregation tests and observe RED**

Run: `python -m unittest tests.phase_exit.test_verify.AggregationTests -v`

Expected: FAIL until registry inspection and aggregation exist.

- [ ] **Step 3: Implement strict UTC freshness and input-hash checks**

```python
def inspect_registration(root, registration, validation_at):
    artifact_path = root / registration["artifact_ref"]
    if not artifact_path.is_file():
        return blocked_result(registration, "NOT_RUN"), [blocker(registration, "PHASE_EXIT_ARTIFACT_MISSING")]
    artifact = load_public_json(artifact_path)
    validate_artifact_identity(artifact, registration)
    validate_observed_at(artifact["observed_at"], validation_at, max_age=300)
    hashes_valid = validate_input_hashes(root, artifact, registration)
    assert_public_safe(artifact)
    return public_gate_result(registration, artifact, hashes_valid), collect_blockers(artifact, hashes_valid)
```

Do not use filesystem mtime as evidence freshness. Do not infer an absent hash or tier. A missing artifact field produces a stable blocker.

- [ ] **Step 4: Implement exact coverage and decision invariants**

```python
def aggregate_phase_zero(root, suite, validation_at):
    validate_registry(suite)
    gate_results, blockers = [], []
    for registration in suite["registrations"]:
        gate_result, registration_blockers = inspect_registration(root, registration, validation_at)
        gate_results.append(gate_result)
        blockers.extend(registration_blockers)
    ready = len(gate_results) == 18 and not blockers and all(r["status"] == "PASSED" for r in gate_results)
    return build_decision("READY" if ready else "NOT_READY", gate_results, blockers, validation_at, suite)
```

Require `READY` summary to be exactly `required=18`, `passed=18`, `failed=0`, `not_run=0`, `blocked=0`.

- [ ] **Step 5: Implement public-safety validation**

Reject result objects containing unknown fields for their registered adapter, forbidden keys `request|response|body|headers|payload|raw|raw_log|credential|token|secret|private|exception`, absolute Windows/POSIX paths, URL userinfo/query credentials, or serialized synthetic marker values. The phase result must not embed source artifacts or raw case arrays.

- [ ] **Step 6: Write failing report tests**

```python
def test_not_ready_report_names_blockers_and_never_says_exit_achieved(self):
    result = not_ready_decision("PHASE_EXIT_EVIDENCE_STALE")
    report = verify.render_report(result)
    self.assertIn("NOT_READY", report)
    self.assertIn("PHASE_EXIT_EVIDENCE_STALE", report)
    self.assertNotIn("Phase 0 Exit 달성", report)

def test_ready_report_is_derived_only_from_closed_result(self):
    report = verify.render_report(ready_decision())
    self.assertIn("18/18", report)
    self.assertIn("READY", report)
```

- [ ] **Step 7: Implement report rendering and atomic writes**

Report sections are exactly `판정`, `게이트 요약`, `차단 조건`, `잔여 위험`, `재현 명령`. Render one table row per public gate result. `READY` may say `Phase 0 Exit 조건 충족`; `NOT_READY` must say `Phase 0 Exit 미충족` and preserve every blocker.

- [ ] **Step 8: Run all pure phase-exit tests**

Run: `python -m unittest tests.phase_exit.test_verify -v`

Expected: PASS for missing, failed, not-run, stale, future, hash, identity, tier, unsafe, exact coverage, READY, and report cases.

### Task 3: Register the Exit command, run all gates fresh, and synchronize project status

**Files:**

- Modify: `tools/phase_exit/verify.py`
- Modify: `tests/phase_exit/test_verify.py`
- Modify: `AGENTS.md`
- Generate: `artifacts/verification/phase-0-exit-result.json`
- Generate: `artifacts/reviews/phase-0-exit-report.md`
- Modify: `docs/project/wbs.md`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/quality/verification-and-evaluation-plan.md`

**Interfaces:**

- Profile ID: `forgeops-phase0-exit`.
- Command ID: `phase0-exit-gate`.
- CLI flags: `--schema`, `--suite`, `--result`, `--report`, `--command-id`; `allow_abbrev=False`.
- Exact command:

```text
python tools/phase_exit/verify.py --schema contracts/forgeops-phase-exit-contract/1.0/schema.json --suite fixtures/forgeops-phase-exit/phase-0-suite.json --result artifacts/verification/phase-0-exit-result.json --report artifacts/reviews/phase-0-exit-report.md --command-id phase0-exit-gate
```

- [ ] **Step 1: Write failing exact-path and failure-write tests**

```python
def test_report_and_result_paths_are_exact(self):
    args = registered_namespace(report="artifacts/reviews/other.md")
    with self.assertRaisesRegex(verify.PhaseExitError, "PHASE_EXIT_RUNNER_CONTRACT_INVALID"):
        verify.validate_registered_paths(args)

def test_cli_writes_not_ready_for_missing_artifact(self):
    exit_code, result = run_cli_with_missing_required_artifact()
    self.assertEqual(1, exit_code)
    self.assertEqual("NOT_READY", result["status"])
```

- [ ] **Step 2: Implement exact CLI and atomic JSON/Markdown writes**

The CLI captures its own strict UTC `validation_at`, validates registered paths before reading the suite, aggregates once, writes JSON then the report atomically, and returns 0 only for `READY`. Contract/parse failure writes a closed `NOT_READY` result and matching report without exception text.

- [ ] **Step 3: Register the exact command**

Add `phase0-exit-gate` to `validation_commands` with `cwd: "."`, `evidence_tier: E3`, and `required: true`; add profile `forgeops-phase0-exit` with only that command.

- [ ] **Step 4: Obtain one batched approval for the complete fresh run**

The approval request must enumerate all local validation commands below, the three Docker-backed VG-008 commands, and the files they generate. State explicitly that no network, image pull/build/push, Git mutation, publication, deployment, or external messaging is included. If Docker approval/capability is absent, continue only far enough to produce truthful `NOT_RUN`/`NOT_READY` evidence.

- [ ] **Step 5: Run all 18 required commands in exact order**

```text
python tools/foundation_conformance/verify.py --manifest fixtures/forgeops-foundation/source-manifest.json --suite fixtures/forgeops-foundation/suite.json --result artifacts/verification/vg-001-protocol-conformance-result.json --command-id protocol-conformance
python tools/foundation_conformance/verify.py --manifest fixtures/forgeops-foundation/source-manifest.json --suite fixtures/forgeops-foundation/suite.json --result artifacts/verification/vg-001-sample-fixture-result.json --command-id sample-fixture
python tools/contract_bridge/verify.py --schema contracts/product-task-contract/1.0/schema.json --suite fixtures/product-task-contract-bridge/suite.json --result artifacts/verification/vg-002-contract-bridge-result.json --report artifacts/reviews/w1-contract-bridge-checkpoint.html
python tools/state_contract/verify.py --schema contracts/forgeops-state-contract/1.0/schema.json --suite fixtures/forgeops-state-contract/state-suite.json --result artifacts/verification/vg-003-state-transition-result.json --command-id state-transition-fixture
python tools/state_contract/verify.py --schema contracts/forgeops-state-contract/1.0/schema.json --suite fixtures/forgeops-state-contract/state-suite.json --result artifacts/verification/vg-003-event-order-result.json --command-id event-order-fixture
python tools/replay_contract/verify.py --schema contracts/forgeops-replay-contract/1.0/schema.json --suite fixtures/forgeops-replay-contract/suite.json --result artifacts/verification/vg-003-replay-contract-result.json
python tools/interface_contract/verify.py --openapi contracts/forgeops-api/1.0/openapi.yaml --event-schema contracts/forgeops-event/1.0/schema.json --manifest-schema contracts/forgeops-run-manifest/1.0/schema.json --api-version-suite fixtures/forgeops-api/version-envelope-suite.json --api-boundary-suite fixtures/forgeops-api/data-control-suite.json --event-suite fixtures/forgeops-event-contract/suite.json --manifest-suite fixtures/forgeops-run-manifest/suite.json --result artifacts/verification/vg-004-interface-contract-result.json --command-id interface-contract-fixture
python tools/policy_contract/verify.py resource --schema contracts/forgeops-authority-policy/1.0/schema.json --suite fixtures/forgeops-authority-resource/suite.json --result artifacts/verification/vg-005-resource-authority-result.json --command-id resource-authority-negative
python tools/policy_contract/verify.py resource --schema contracts/forgeops-authority-policy/1.0/schema.json --suite fixtures/forgeops-authority-resource/suite.json --result artifacts/verification/vg-005-protected-read-result.json --command-id protected-read-negative
python tools/policy_contract/verify.py command-network --schema contracts/forgeops-authority-policy/1.0/schema.json --suite fixtures/forgeops-authority-command-network/suite.json --result artifacts/verification/vg-006-command-network-result.json --command-id command-network-negative
python tools/policy_contract/verify.py approval --schema contracts/forgeops-authority-policy/1.0/schema.json --suite fixtures/forgeops-approval-policy/suite.json --result artifacts/verification/vg-007-approval-policy-result.json --command-id approval-negative-fixture
python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-image-provenance-result.json --command-id image-provenance-negative
python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-containment-egress-result.json --command-id containment-egress-negative
python tools/sandbox_security/verify.py --schema contracts/forgeops-sandbox-contract/1.0/schema.json --suite fixtures/forgeops-sandbox-security/suite.json --runtime-profile artifacts/runtime/sandbox-runtime-profile.json --runtime docker --result artifacts/verification/vg-008-teardown-result.json --command-id teardown-negative
python tools/secret_artifact_security/verify.py --schema contracts/forgeops-secret-artifact-contract/1.0/schema.json --suite fixtures/forgeops-secret-artifact-security/suite.json --result artifacts/verification/vg-009-secret-surface-result.json --command-id secret-surface-negative
python tools/secret_artifact_security/verify.py --schema contracts/forgeops-secret-artifact-contract/1.0/schema.json --suite fixtures/forgeops-secret-artifact-security/suite.json --result artifacts/verification/vg-009-artifact-isolation-result.json --command-id artifact-isolation-negative
python tools/evidence_contract/verify.py --schema contracts/forgeops-evidence-contract/1.0/schema.json --suite fixtures/forgeops-evidence-contract/suite.json --result artifacts/verification/vg-023-evidence-contract-result.json --command-id evidence-positive-negative
python tools/evidence_contract/verify.py --schema contracts/forgeops-evidence-contract/1.0/schema.json --suite fixtures/forgeops-evidence-contract/suite.json --result artifacts/verification/vg-023-extension-provenance-result.json --command-id extension-provenance
```

Expected: each command truthfully produces PASSED, FAILED, or NOT_RUN. Do not stop recording evidence after the first independent failure, but do not run dependent unsafe runtime work after a hard preflight failure.

- [ ] **Step 6: Run all W1~W4 unit tests**

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: all contract/unit tests pass. This does not override a VG-008 runtime `NOT_RUN` result.

- [ ] **Step 7: Run the registered Phase 0 aggregator**

Run the exact `phase0-exit-gate` command above immediately after the 18 results.

Expected READY path: exit 0, 18/18 passed, zero blockers, all hashes/freshness/public-safe assertions true.

Expected blocked path: exit 1, `NOT_READY`, exact blockers listed, no unsupported Exit claim.

- [ ] **Step 8: Independently inspect the result and report**

Run: `python -m json.tool artifacts/verification/phase-0-exit-result.json`

Verify every registration appears once, counts total 18, artifact refs exist, observed times are within the configured window, and report status/blockers exactly match JSON. Scan both files for forbidden raw/sensitive content and absolute paths.

- [ ] **Step 9: Synchronize WBS, RTM, and quality status**

If `READY`, set WBS-008~WBS-012 according to their individual fresh evidence and record Phase 0 Exit conditions as satisfied. If `NOT_READY`, update only rows whose own gates passed; leave WBS-012 incomplete and record exact blockers/residual risks. Never mark a requirement PASSED solely because the aggregator file exists.

- [ ] **Step 10: Re-run the aggregator and final workspace checks**

Re-run `phase0-exit-gate` after documentation changes only if the registry inputs and result artifacts are unchanged and still fresh; otherwise rerun all affected registered commands first.

Run: `git diff --check`

Run: `git status --short`

Run: `git diff --cached --quiet`

Expected: decision/report remain consistent with evidence, no whitespace errors, no staged changes, and no commit/push/PR/publication/deployment occurred.
