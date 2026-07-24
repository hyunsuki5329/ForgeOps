# W3-5 VG-004 Interface Conformance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggregate W3 OpenAPI, API boundary, event, and manifest contracts into one registered, deterministic, public-safe E2 VG-004 verification command.

**Architecture:** A thin CLI imports the four focused validators, admits only registered literal input/result paths, runs exact ordered catalogs, then performs cross-contract identity/reference/status checks. It atomically replaces the single registered result artifact on both success and runner-contract failure without calling real effect surfaces.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `argparse`/`json`/`tempfile`/`unittest`, Markdown

## Global Constraints

- Accept only the seven approved contract/suite paths and result path `artifacts/verification/vg-004-interface-contract-result.json` as exact root-relative literals.
- Run validation in the approved ten-stage order and retain component stable categories; use only `INTERFACE_RUNNER_CONTRACT_INVALID`, `INTERFACE_CROSS_REFERENCE_INVALID`, and `INTERFACE_RESULT_UNSAFE` for integration-owned failures.
- Never call HTTP, DNS, sockets, child processes, credential providers, external stores, or artifact content reads; every negative effect spy count must be zero.
- Result data is limited to gate/profile/command/status, hashes, strict UTC observation time, component counts, public case verdicts, and zero-effect/no-sensitive assertions.
- Update WBS-006 through WBS-008 and mapped RTM results only after the registered command and all unit tests produce fresh passing evidence.
- Do not Git add/commit/push/PR or perform publication/external effects without separate authorization.

---

## File Structure

- Create `tools/interface_contract/verify.py`: exact CLI/path guard, component orchestration, cross-contract checks, safe result builder, atomic writer.
- Create `tests/interface_contract/test_verify.py`: CLI path denial, catalog tamper, cross-reference, safety, failure replacement, and integrated-pass tests.
- Modify `AGENTS.md`: register one required E2 command and one verification profile.
- Generate `artifacts/verification/vg-004-interface-contract-result.json`: registered public-safe evidence.
- Modify `docs/project/requirements-traceability-matrix.md`: update only VG-004-backed W3 owner rows after fresh pass.
- Modify `docs/project/wbs.md`: close only WBS-006, WBS-007, WBS-008 after fresh pass and evidence inspection.

### Task 1: Build the exact-path integrated runner and failure-safe result

**Files:**

- Create: `tools/interface_contract/verify.py`
- Create: `tests/interface_contract/test_verify.py`

**Interfaces:**

- CLI flags: `--openapi`, `--event-schema`, `--manifest-schema`, `--api-version-suite`, `--api-boundary-suite`, `--event-suite`, `--manifest-suite`, `--result`, `--command-id`.
- `validate_registered_paths(args: argparse.Namespace) -> None` admits only exact trusted literals.
- `run_conformance(paths: dict[str, Path], observed_at: str) -> dict` returns a closed result object.
- `write_result_atomically(path: Path, result: dict) -> None` uses a sibling temporary file and `Path.replace`.

- [ ] **Step 1: Write failing exact-path and failure-replacement tests**

```python
def test_arbitrary_result_path_is_denied(self):
    args = registered_args(result="artifacts/verification/other.json")
    with self.assertRaisesRegex(ContractError, "INTERFACE_RUNNER_CONTRACT_INVALID"):
        validate_registered_paths(args)

def test_corrupt_suite_replaces_registered_result_with_safe_failure(self):
    with temporary_registered_copy("api-version-suite", b"not-json") as paths:
        exit_code = run_cli_for_test(paths)
        result = json.loads(paths["result"].read_text(encoding="utf-8"))
    self.assertEqual(1, exit_code)
    self.assertEqual("FAILED", result["status"])
    self.assertEqual("INTERFACE_RUNNER_CONTRACT_INVALID", result["failure_code"])
    self.assertNotIn("exception", result)
```

- [ ] **Step 2: Run runner tests and observe RED**

Run: `python -m unittest tests.interface_contract.test_verify -v`
Expected: FAIL because the integrated runner does not exist.

- [ ] **Step 3: Implement exact path and catalog guards**

```python
TRUSTED = {
    "openapi": "contracts/forgeops-api/1.0/openapi.yaml",
    "event_schema": "contracts/forgeops-event/1.0/schema.json",
    "manifest_schema": "contracts/forgeops-run-manifest/1.0/schema.json",
    "api_version_suite": "fixtures/forgeops-api/version-envelope-suite.json",
    "api_boundary_suite": "fixtures/forgeops-api/data-control-suite.json",
    "event_suite": "fixtures/forgeops-event-contract/suite.json",
    "manifest_suite": "fixtures/forgeops-run-manifest/suite.json",
    "result": "artifacts/verification/vg-004-interface-contract-result.json",
}

def validate_registered_paths(args):
    if args.command_id != "interface-contract-fixture":
        raise ContractError("INTERFACE_RUNNER_CONTRACT_INVALID")
    for name, literal in TRUSTED.items():
        if getattr(args, name) != literal:
            raise ContractError("INTERFACE_RUNNER_CONTRACT_INVALID")
```

Validate each suite's exact `suite_id`, `suite_version`, ordered case IDs, uniqueness, and closed case fields before evaluating cases.

- [ ] **Step 4: Implement orchestration and safe atomic result**

Execute: path/catalog → schema/OpenAPI → version/closed → non-grant → identity → sequences → revision/provenance → uniqueness → references/freshness → result safety. Build case records from IDs and categories only; hash the seven trusted files; compute component counts; require every expected/actual category to match and every spy assertion to be zero.

```python
def write_result_atomically(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
```

On any caught contract or parse failure, write a closed FAILED result to the same registered path, omit raw exception text, and return exit 1.

- [ ] **Step 5: Run Task 1 tests**

Run: `python -m unittest tests.interface_contract.test_verify -v`
Expected: PASS for exact path, catalog tamper, atomic replacement, and public-safe failure tests.

### Task 2: Add cross-contract identity, event-to-manifest, and terminal-state checks

**Files:**

- Modify: `tools/interface_contract/verify.py`
- Modify: `tests/interface_contract/test_verify.py`

**Interfaces:**

- `validate_cross_contract(api_case: dict, event_records: list[dict], manifest: dict) -> None`.
- `assert_public_safe_result(result: dict) -> None` rejects forbidden keys/values and absolute host paths.

- [ ] **Step 1: Add failing cross-contract tests**

```python
def test_event_evidence_resolves_once_in_same_manifest(self):
    bundle = valid_integrated_bundle()
    bundle["events"][0]["canonical_event"]["evidence_refs"] = ["EVID-missing"]
    with self.assertRaisesRegex(ContractError, "INTERFACE_CROSS_REFERENCE_INVALID"):
        validate_cross_contract(**bundle)

def test_terminal_status_and_revision_match_final_main_event(self):
    bundle = valid_integrated_bundle()
    bundle["manifest"]["accepted_revision"] += 1
    with self.assertRaisesRegex(ContractError, "INTERFACE_CROSS_REFERENCE_INVALID"):
        validate_cross_contract(**bundle)
```

- [ ] **Step 2: Run cross-contract tests and observe RED**

Run: `python -m unittest tests.interface_contract.test_verify.CrossContractTests -v`
Expected: FAIL until integrated relation checks are implemented.

- [ ] **Step 3: Implement exact same-run resolution**

```python
def validate_cross_contract(api_case, event_records, manifest):
    identities = {(item["task_id"], item["run_id"], item["correlation_id"]) for item in event_records}
    identities.add((manifest["task_id"], manifest["run_id"], manifest["correlation_id"]))
    identities.add((api_case["task_id"], api_case["run_id"], api_case["correlation_id"]))
    if len(identities) != 1:
        raise ContractError("INTERFACE_CROSS_REFERENCE_INVALID")
    evidence_ids = [item["evidence_id"] for item in manifest["evidence"]]
    for event in event_records:
        for ref in event["canonical_event"]["evidence_refs"]:
            if evidence_ids.count(ref) != 1:
                raise ContractError("INTERFACE_CROSS_REFERENCE_INVALID")
    validate_terminal_event_match(event_records[-1], manifest)
```

Also require API `event_stream_ref`/`manifest_ref` to name the same fixture stream/manifest, all producer sequence values inside the manifest range, and terminal status plus accepted revision to match the final Main state event.

- [ ] **Step 4: Add result-safety tests and guard**

Scan result keys recursively for the exact forbidden raw-data names `request`, `response`, `body`, `headers`, `raw_event`, `raw_manifest`, `payload`, `credential`, `token`, `secret`, `private`, and `exception`, and scan string values for credential material and absolute host-path patterns. Permit safe metadata names such as `event_schema_sha256` and `manifest_schema_sha256`; otherwise allow only the closed result fields from the approved design. Raise `INTERFACE_RESULT_UNSAFE` before writing a PASSED result.

- [ ] **Step 5: Run all interface unit tests**

Run: `python -m unittest tests.interface_contract.test_openapi_version tests.interface_contract.test_api_boundary tests.interface_contract.test_event_wrapper tests.interface_contract.test_run_manifest tests.interface_contract.test_verify -v`
Expected: PASS with all fixture cases matched, every negative spy count zero, and no sensitive result field.

### Task 3: Register VG-004, generate fresh evidence, and synchronize W3 owner rows

**Files:**

- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-004-interface-contract-result.json`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/project/wbs.md`

**Interfaces:**

- Command ID: `interface-contract-fixture`; profile ID: `forgeops-interface-contract`; required evidence tier: `E2`.
- Exact command:

```text
python tools/interface_contract/verify.py --openapi contracts/forgeops-api/1.0/openapi.yaml --event-schema contracts/forgeops-event/1.0/schema.json --manifest-schema contracts/forgeops-run-manifest/1.0/schema.json --api-version-suite fixtures/forgeops-api/version-envelope-suite.json --api-boundary-suite fixtures/forgeops-api/data-control-suite.json --event-suite fixtures/forgeops-event-contract/suite.json --manifest-suite fixtures/forgeops-run-manifest/suite.json --result artifacts/verification/vg-004-interface-contract-result.json --command-id interface-contract-fixture
```

- [ ] **Step 1: Register the exact required command and profile**

Add one `validation_commands` record with the command above, `cwd: "."`, `evidence_tier: E2`, and `required: true`. Add `forgeops-interface-contract` under `extensions.forgeops.verification_profiles` with only `interface-contract-fixture` in `command_ids`.

- [ ] **Step 2: Run the exact registered command**

Run the exact command shown in this task from repository root.
Expected: exit 0; result has `gate_id="VG-004"`, `profile_id="forgeops-interface-contract"`, `command_id="interface-contract-fixture"`, `status="PASSED"`, strict UTC `observed_at`, current hashes, all component failures zero, all negative spy calls zero, and no-sensitive assertion true.

- [ ] **Step 3: Re-run all interface tests after registration**

Run: `python -m unittest tests.interface_contract.test_openapi_version tests.interface_contract.test_api_boundary tests.interface_contract.test_event_wrapper tests.interface_contract.test_run_manifest tests.interface_contract.test_verify -v`
Expected: exit 0 and all tests PASS against the registered paths.

- [ ] **Step 4: Inspect evidence before status synchronization**

Run: `python -m json.tool artifacts/verification/vg-004-interface-contract-result.json`
Expected: exit 0 and only public-safe fields. Independently recompute the seven file hashes and require exact equality with the artifact before editing project status.

- [ ] **Step 5: Update only evidence-backed W3 rows**

In `docs/project/requirements-traceability-matrix.md`, update the mapped `PRD-FR-003`, `PRD-FR-004`, and applicable `PRD-NFR-006` VG-004 Result/Evidence references to the registered command/artifact. In `docs/project/wbs.md`, change only `WBS-006`, `WBS-007`, and `WBS-008` to their done state after confirming their dependency and acceptance columns are satisfied. Preserve W4 and unrelated rows verbatim.

- [ ] **Step 6: Run final registered verification and workspace checks**

Run the exact registered command again.
Expected: exit 0 with a newly observed PASSED artifact whose hashes match the final contract/suite files.

Run: `git diff --check`
Expected: exit 0.

Run: `git status --short`
Expected: only W3 implementation/evidence/status files are changed or untracked; no file is staged or committed.
