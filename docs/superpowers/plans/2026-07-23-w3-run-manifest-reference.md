# W3-4 Run Manifest and Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define and executable-test a closed run manifest with deterministic self-hash, event range, artifact/evidence catalogs, freshness union, and exact same-run references.

**Architecture:** JSON Schema owns shape and closed enums; `manifest_contract.py` owns deterministic canonical serialization and semantic catalog resolution. Fixture manifests contain opaque identities and hashes only, and validation completes in memory before any storage spy can run.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `json`/`hashlib`/`unittest`, JSON

## Global Constraints

- `manifest_sha256` hashes canonical sorted-key compact JSON encoded as UTF-8 without BOM after removing only the root `manifest_sha256` field.
- `run_mode` is exactly `PRIMARY|AUDIT_REPLAY|COUNTERFACTUAL|REEXECUTE`; W2 replay meaning is not redefined.
- `file|diff` evidence requires only `observed_revision`; time-based evidence requires only strict UTC `observed_at`.
- Resolve every decision/evidence/artifact reference exactly once within the same manifest/task/run and inside the declared producer sequence range.
- PRIVATE/SECRET records retain only opaque IDs and hashes; raw content, credentials, tenant IDs, signed URLs, absolute paths, traversal, backslashes, wildcards, queries, and fragments are forbidden.
- Do not implement storage, encryption, retention, deletion, tenant enforcement, Git commit/push/PR, or WBS/RTM update.

---

## File Structure

- Create `contracts/forgeops-run-manifest/1.0/schema.json`: closed root, catalog records, freshness union, and enums.
- Create `tools/interface_contract/manifest_contract.py`: canonical hash, lifecycle, catalog, reference, source-ref, and freshness validation.
- Create `fixtures/forgeops-run-manifest/suite.json`: ordered valid/invalid manifest catalog.
- Create `tests/interface_contract/test_run_manifest.py`: schema, hash, range, reference, freshness, and sensitive-content tests.

### Task 1: Define manifest shape, lifecycle, event range, and deterministic hash

**Files:**

- Create: `contracts/forgeops-run-manifest/1.0/schema.json`
- Create: `tools/interface_contract/manifest_contract.py`
- Create: `fixtures/forgeops-run-manifest/suite.json`
- Create: `tests/interface_contract/test_run_manifest.py`

**Interfaces:**

- `canonical_manifest_bytes(manifest: dict) -> bytes` excludes only root `manifest_sha256`.
- `calculate_manifest_sha256(manifest: dict) -> str` returns lowercase SHA-256 hex.
- `validate_manifest(manifest: dict, schema: dict) -> str` validates the self-contained manifest and returns `PASSED` or raises `ContractError`.
- `validate_manifest_case(case: dict, schema: dict, storage_spy: StorageSpy | None = None) -> str` additionally validates case-local resolved source identity without adding fields to the manifest.
- Stable errors are exactly `MANIFEST_SCHEMA_INVALID`, `MANIFEST_IDENTITY_MISMATCH`, `MANIFEST_MODE_INVALID`, `MANIFEST_EVENT_RANGE_INVALID`, `MANIFEST_ID_DUPLICATE`, `MANIFEST_REFERENCE_DANGLING`, `MANIFEST_REFERENCE_CROSS_RUN`, `MANIFEST_PRODUCER_SEQUENCE_INVALID`, `MANIFEST_EVIDENCE_FRESHNESS_INVALID`, `MANIFEST_HASH_INVALID`, and `MANIFEST_SENSITIVE_CONTENT_FORBIDDEN`.

- [ ] **Step 1: Write failing schema and hash tests**

```python
def test_primary_terminal_manifest_is_valid(self):
    self.assertEqual("PASSED", validate_manifest(case_by_id("primary-terminal")["manifest"], SCHEMA))

def test_manifest_hash_excludes_only_itself(self):
    manifest = deepcopy(case_by_id("primary-terminal")["manifest"])
    expected = hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest()
    self.assertEqual(expected, manifest["manifest_sha256"])

def test_event_count_matches_inclusive_range(self):
    manifest = deepcopy(case_by_id("primary-terminal")["manifest"])
    manifest["event_stream"]["count"] += 1
    manifest["manifest_sha256"] = calculate_manifest_sha256(manifest)
    with self.assertRaisesRegex(ContractError, "MANIFEST_EVENT_RANGE_INVALID"):
        validate_manifest(manifest, SCHEMA)
```

- [ ] **Step 2: Run tests and observe RED**

Run: `python -m unittest tests.interface_contract.test_run_manifest -v`
Expected: FAIL because the manifest contract, fixture, and validator do not exist.

- [ ] **Step 3: Write the closed manifest schema**

Require the exact approved root fields; source contract fields `artifact_id`, `artifact_version`, `content_sha256`; event stream fields `stream_id`, `first_seq`, `last_seq`, `count`, `content_sha256`; closed artifact/evidence records; the four run modes; closed status and classification enums; SHA-256 patterns; and a `oneOf` freshness union that forbids the wrong companion field. Each `decision_refs` record is exactly `decision_id`, `decision_kind`, `subject_id`, `artifact_refs`, `evidence_refs`, and `producer_event_seq`; `decision_kind` is `CANDIDATE|CRITERION|TERMINAL`.

- [ ] **Step 4: Implement canonical bytes, range, lifecycle, and hash checks**

```python
def canonical_manifest_bytes(manifest):
    payload = {key: value for key, value in manifest.items() if key != "manifest_sha256"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def calculate_manifest_sha256(manifest):
    return hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest()

def validate_manifest(manifest, schema):
    if list(Draft202012Validator(schema).iter_errors(manifest)):
        raise ContractError("MANIFEST_SCHEMA_INVALID")
    validate_lifecycle(manifest)
    stream = manifest["event_stream"]
    if stream["count"] != stream["last_seq"] - stream["first_seq"] + 1:
        raise ContractError("MANIFEST_EVENT_RANGE_INVALID")
    if calculate_manifest_sha256(manifest) != manifest["manifest_sha256"]:
        raise ContractError("MANIFEST_HASH_INVALID")
    validate_catalogs_and_references(manifest)
    return "PASSED"
```

`validate_lifecycle` identifies terminal decision refs by `decision_kind="TERMINAL"`, forbids `finalized_at` and terminal refs on non-terminal snapshots, and requires them for terminal manifests.

- [ ] **Step 5: Add positive lifecycle fixtures and pass Task 1 tests**

Include primary terminal, non-terminal snapshot, audit replay, counterfactual, revision-evidence, and time-evidence manifests. Calculate each stored `manifest_sha256` with the exact function above.

Run: `python -m unittest tests.interface_contract.test_run_manifest.ManifestShapeTests -v`
Expected: PASS for schema, lifecycle, event range, and deterministic hash cases.

### Task 2: Resolve catalogs, references, freshness, and sensitive boundaries

**Files:**

- Modify: `tools/interface_contract/manifest_contract.py`
- Modify: `fixtures/forgeops-run-manifest/suite.json`
- Modify: `tests/interface_contract/test_run_manifest.py`

**Interfaces:**

- `validate_catalogs_and_references(manifest: dict) -> None` validates ordinal uniqueness and exact resolution.
- A fixture case is exactly `{id, kind, manifest, resolution_context, expected, expected_storage_calls}`; `resolution_context` maps source/reference IDs to `{task_id, run_id}` and is not part of the manifest contract.
- `validate_source_ref(source_ref: object) -> None` accepts only canonical root-relative literals or `forgeops:` opaque URNs.
- `StorageSpy.calls: int` remains zero for every invalid manifest.

- [ ] **Step 1: Write failing resolver and freshness tests**

```python
def test_duplicate_evidence_id_is_rejected(self):
    with self.assertRaisesRegex(ContractError, "MANIFEST_ID_DUPLICATE"):
        validate_manifest(case_by_id("duplicate-evidence-id")["manifest"], SCHEMA)

def test_dangling_decision_reference_is_rejected(self):
    with self.assertRaisesRegex(ContractError, "MANIFEST_REFERENCE_DANGLING"):
        validate_manifest(case_by_id("dangling-reference")["manifest"], SCHEMA)

def test_time_evidence_cannot_have_revision_freshness(self):
    with self.assertRaisesRegex(ContractError, "MANIFEST_EVIDENCE_FRESHNESS_INVALID"):
        validate_manifest(case_by_id("time-evidence-with-revision")["manifest"], SCHEMA)

def test_resolved_source_from_another_run_is_rejected(self):
    case = case_by_id("cross-run-reference")
    with self.assertRaisesRegex(ContractError, "MANIFEST_REFERENCE_CROSS_RUN"):
        validate_manifest_case(case, SCHEMA, StorageSpy())
```

- [ ] **Step 2: Run resolver tests and observe RED**

Run: `python -m unittest tests.interface_contract.test_run_manifest.ManifestReferenceTests -v`
Expected: FAIL until semantic catalog resolution is complete.

- [ ] **Step 3: Implement exact catalog and reference resolution**

```python
def unique_index(items, key):
    values = [item[key] for item in items]
    if len(values) != len(set(values)):
        raise ContractError("MANIFEST_ID_DUPLICATE")
    return {item[key]: item for item in items}

def validate_catalogs_and_references(manifest):
    artifacts = unique_index(manifest["artifacts"], "artifact_id")
    evidence = unique_index(manifest["evidence"], "evidence_id")
    for record in [*artifacts.values(), *evidence.values()]:
        validate_producer_range(record["producer_event_seq"], manifest["event_stream"])
    for decision in manifest["decision_refs"]:
        for ref in decision["artifact_refs"]:
            if ref not in artifacts:
                raise ContractError("MANIFEST_REFERENCE_DANGLING")
        for ref in decision["evidence_refs"]:
            if ref not in evidence:
                raise ContractError("MANIFEST_REFERENCE_DANGLING")
    validate_evidence_freshness(evidence.values())
```

`validate_manifest_case` compares every `resolution_context` entry used by the manifest with the manifest's exact `task_id` and `run_id`, rejecting a mismatch as `MANIFEST_REFERENCE_CROSS_RUN`; it does not copy that context into artifact or evidence records. `validate_producer_range` uses the inclusive event range.

- [ ] **Step 4: Implement source and sensitive-content guards**

Reject absolute/drive/UNC paths, `..`, backslashes, wildcard characters, query, fragment, raw secret fields, credential-like fields, tenant identifiers, and signed URLs. Allow only project-root-relative forward-slash literals or closed `forgeops:<kind>:<opaque-id>` values; never normalize an invalid value into a match.

- [ ] **Step 5: Complete negative fixtures and zero-storage assertion**

Add duplicate/dangling/cross-run references, producer outside range, file evidence with time, time evidence with revision, invalid strict UTC, missing/bad hash, terminal/finalized mismatch, raw secret field, absolute path, traversal, and signed URL. Validate the entire manifest before incrementing any `StorageSpy` call.

- [ ] **Step 6: Run all W3-4 tests and inspect the diff**

Run: `python -m unittest tests.interface_contract.test_run_manifest -v`
Expected: PASS; every negative stable category matches and storage calls are zero.

Run: `git diff --check`
Expected: exit 0. Keep `WBS-008` unchanged until integrated evidence exists.
