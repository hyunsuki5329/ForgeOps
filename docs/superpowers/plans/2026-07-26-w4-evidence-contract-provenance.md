# W4-1 Evidence Contract and Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement VG-023 as a closed, deterministic E2 evidence and extension-provenance contract that can safely unblock WBS-008.

**Architecture:** A Draft 2020-12 schema closes evidence and extension-provenance records. A pure Python evaluator enforces type/tier/reference/freshness precedence and zero-effect rejection, while one exact-path CLI exposes the two registered command IDs and writes separate public-safe results atomically.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `argparse`/`datetime`/`hashlib`/`json`/`tempfile`/`unittest`, JSON Schema, Markdown

## Global Constraints

- Evidence type is exactly `file|diff|command|test|render|runtime|approval`; tier is exactly `E0|E1|E2|E3`.
- `file`/`diff` require integer `observed_revision==base_revision` and forbid `observed_at`; every other type requires strict UTC `observed_at`, forbids `observed_revision`, and must be 0 through 300 seconds old relative to trusted `validation_at`.
- IDs and references are original non-empty strings, case-sensitive, ordinal-unique, and exact; dangling, duplicate, trim, case folding, prefix, and suffix matching are forbidden.
- Plugin/static finding provenance is metadata only and cannot create authority, approval, freshness, evidence tier, or acceptance.
- Every negative case must leave `accept_calls=0` and `append_calls=0`; results must not contain raw packet, finding payload, absolute paths, exception text, credentials, tokens, or secrets.
- Accept only registered root-relative schema/suite/result literals and exact command IDs `evidence-positive-negative` and `extension-provenance`.
- Do not Git add/commit/push/PR, publish, access a network, or perform external effects.

---

## File Structure

- Create `contracts/forgeops-evidence-contract/1.0/schema.json`: closed evidence and extension-provenance definitions.
- Create `fixtures/forgeops-evidence-contract/suite.json`: exact ordered positive/negative catalogs and trusted validation context.
- Create `tools/evidence_contract/__init__.py`: package marker.
- Create `tools/evidence_contract/verify.py`: evaluator, CLI, public result builder, and atomic writer.
- Create `tests/evidence_contract/__init__.py`: test package marker.
- Create `tests/evidence_contract/test_verify.py`: schema, precedence, reference, freshness, provenance, path, and safety tests.
- Modify `AGENTS.md`: register the two required E2 commands and `forgeops-evidence-contract` profile.
- Generate `artifacts/verification/vg-023-evidence-contract-result.json` and `artifacts/verification/vg-023-extension-provenance-result.json`.
- Modify `docs/project/wbs.md`, `docs/project/requirements-traceability-matrix.md`, and `docs/quality/verification-and-evaluation-plan.md` only after both registered runs pass with fresh evidence.

### Task 1: Create the closed schema and exact fixture catalogs

**Files:**

- Create: `contracts/forgeops-evidence-contract/1.0/schema.json`
- Create: `fixtures/forgeops-evidence-contract/suite.json`
- Create: `tests/evidence_contract/__init__.py`
- Create: `tests/evidence_contract/test_verify.py`

**Interfaces:**

- Schema definitions: `$defs.EvidenceRecord`, `$defs.ExtensionProvenanceRecord`.
- Suite root fields: `suite_id`, `suite_version`, `validation_at`, `base_revision`, `evidence_cases`, `provenance_cases`.
- Evidence case fields: `id`, `kind`, `record`, `catalog_ids`, `expected`, `expected_accept_calls`, `expected_append_calls`.
- Provenance case fields: `id`, `kind`, `record`, `expected_context`, `expected`, `expected_accept_calls`, `expected_append_calls`.

- [ ] **Step 1: Write schema-closure tests before creating the schema**

```python
class EvidenceSchemaTests(unittest.TestCase):
    def test_schema_closes_every_object(self):
        schema = load_json(ROOT / "contracts/forgeops-evidence-contract/1.0/schema.json")
        objects = [node for node in walk(schema) if node.get("type") == "object"]
        self.assertTrue(objects)
        self.assertTrue(all(node.get("additionalProperties") is False for node in objects))

    def test_evidence_enums_are_exact(self):
        schema = load_schema()
        record = schema["$defs"]["EvidenceRecord"]
        self.assertEqual(
            ["file", "diff", "command", "test", "render", "runtime", "approval"],
            record["properties"]["type"]["enum"],
        )
        self.assertEqual(["E0", "E1", "E2", "E3"], record["properties"]["tier"]["enum"])
```

- [ ] **Step 2: Run the focused schema tests and observe RED**

Run: `python -m unittest tests.evidence_contract.test_verify.EvidenceSchemaTests -v`

Expected: FAIL because the schema and fixture suite do not exist.

- [ ] **Step 3: Create the closed evidence and provenance schema**

Use this evidence shape exactly:

```json
{
  "id": "EVID-001",
  "tier": "E2",
  "type": "test",
  "source_ref": "tests/evidence_contract/test_verify.py",
  "observation": "registered fixture passed",
  "evidence_refs": [],
  "observed_at": "2026-07-26T00:00:00Z"
}
```

`EvidenceRecord` must require `id`, `tier`, `type`, `source_ref`, `observation`, and `evidence_refs`; allow exactly one freshness field selected by `type`. `ExtensionProvenanceRecord` must require exactly `provenance_id`, `producer_kind`, `task_id`, `run_id`, `source_ref`, `source_sha256`, and `finding_refs`, where `producer_kind` is `plugin|static_analyzer`, SHA-256 is `^[0-9a-f]{64}$`, and finding refs are unique non-empty strings.

- [ ] **Step 4: Create the exact ordered fixture catalogs**

Set evidence case IDs in this order:

```python
EVIDENCE_CASES = (
    ("positive-file-revision", "PASSED"),
    ("positive-command-time", "PASSED"),
    ("negative-type-case", "EVIDENCE_TYPE_INVALID"),
    ("negative-tier-case", "EVIDENCE_TIER_INVALID"),
    ("negative-file-with-time", "EVIDENCE_FRESHNESS_INVALID"),
    ("negative-command-with-revision", "EVIDENCE_FRESHNESS_INVALID"),
    ("negative-stale-time", "EVIDENCE_FRESHNESS_INVALID"),
    ("negative-future-time", "EVIDENCE_FRESHNESS_INVALID"),
    ("negative-dangling-ref", "EVIDENCE_REFERENCE_INVALID"),
    ("negative-duplicate-ref", "EVIDENCE_REFERENCE_INVALID"),
)
```

Set provenance case IDs in this order:

```python
PROVENANCE_CASES = (
    ("positive-plugin-provenance", "PASSED"),
    ("positive-static-provenance", "PASSED"),
    ("negative-producer-kind", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-task-mismatch", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-run-mismatch", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-source-hash", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-duplicate-finding-ref", "EVIDENCE_PROVENANCE_INVALID"),
    ("negative-authority-field", "EVIDENCE_SCHEMA_INVALID"),
)
```

Every negative case must declare both expected spy counts as zero.

- [ ] **Step 5: Run schema and catalog tests**

Run: `python -m unittest tests.evidence_contract.test_verify.EvidenceSchemaTests tests.evidence_contract.test_verify.CatalogTests -v`

Expected: PASS; both catalogs have exact IDs/order/expected categories and every object boundary is closed.

### Task 2: Implement evidence and provenance evaluation with zero effects

**Files:**

- Create: `tools/evidence_contract/__init__.py`
- Create: `tools/evidence_contract/verify.py`
- Modify: `tests/evidence_contract/test_verify.py`

**Interfaces:**

- `class EvidenceError(Exception)` exposes `.code` only.
- `class EffectSpy` exposes `accept_calls`, `append_calls`, `accept()`, and `append()`.
- `validate_evidence(record: dict, *, base_revision: int, validation_at: str, catalog_ids: list[str], spy: EffectSpy) -> None`.
- `validate_extension_provenance(record: dict, *, expected_task_id: str, expected_run_id: str, spy: EffectSpy) -> None`.
- `run_cases(command_id: str, suite: dict) -> list[dict]` returns public case records only.

- [ ] **Step 1: Write failing precedence, freshness, reference, and provenance tests**

```python
def test_wrong_mode_freshness_is_rejected_before_accept(self):
    record = valid_command_evidence()
    record["observed_revision"] = 7
    spy = verify.EffectSpy()
    with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_FRESHNESS_INVALID"):
        verify.validate_evidence(
            record,
            base_revision=7,
            validation_at="2026-07-26T00:04:00Z",
            catalog_ids=[record["id"]],
            spy=spy,
        )
    self.assertEqual((0, 0), (spy.accept_calls, spy.append_calls))

def test_provenance_hash_mismatch_never_appends(self):
    record = valid_plugin_provenance()
    record["source_sha256"] = "0" * 64
    spy = verify.EffectSpy()
    with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_PROVENANCE_INVALID"):
        verify.validate_extension_provenance(
            record, expected_task_id="TASK-001", expected_run_id="RUN-001", spy=spy
        )
    self.assertEqual((0, 0), (spy.accept_calls, spy.append_calls))
```

- [ ] **Step 2: Run evaluator tests and observe RED**

Run: `python -m unittest tests.evidence_contract.test_verify.EvidenceEvaluatorTests -v`

Expected: FAIL because `EvidenceError`, `EffectSpy`, and validators are not implemented.

- [ ] **Step 3: Implement stable validation order**

Use this order without normalization:

```python
def validate_evidence(record, *, base_revision, validation_at, catalog_ids, spy):
    validate_closed_schema(record)
    validate_type_and_tier(record)
    validate_ids_and_refs(record, catalog_ids)
    validate_freshness(record, base_revision, validation_at)
    spy.accept()

def validate_extension_provenance(record, *, expected_task_id, expected_run_id, spy):
    validate_closed_provenance_schema(record)
    validate_producer_kind(record)
    validate_context_identity(record, expected_task_id, expected_run_id)
    validate_source_hash_and_findings(record)
    spy.append()
```

Parse timestamps only with `datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")`; compute `age_seconds = (validation_at - observed_at).total_seconds()` and accept only `0 <= age_seconds <= 300`. Never derive `validation_at` from the record.

- [ ] **Step 4: Implement exact fixture execution and public case records**

```python
def public_case(case_id: str, expected: str, actual: str, spy: EffectSpy) -> dict:
    return {
        "case_id": case_id,
        "expected": expected,
        "actual": actual,
        "status": "PASSED" if expected == actual else "FAILED",
        "accept_calls": spy.accept_calls,
        "append_calls": spy.append_calls,
    }
```

Require observed spy counts to equal the exact expected values from the suite. A category match with a non-zero negative effect is `FAILED`.

- [ ] **Step 5: Run the complete evaluator suite**

Run: `python -m unittest tests.evidence_contract.test_verify -v`

Expected: PASS; stable categories match and all negative accept/append counts are zero.

### Task 3: Add the registered CLI, generate VG-023 evidence, and synchronize WBS-008

**Files:**

- Modify: `tools/evidence_contract/verify.py`
- Modify: `tests/evidence_contract/test_verify.py`
- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-023-evidence-contract-result.json`
- Generate: `artifacts/verification/vg-023-extension-provenance-result.json`
- Modify: `docs/project/wbs.md`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/quality/verification-and-evaluation-plan.md`

**Interfaces:**

- Profile ID: `forgeops-evidence-contract`.
- Command IDs: `evidence-positive-negative`, `extension-provenance`.
- CLI flags: `--schema`, `--suite`, `--result`, `--command-id` with `allow_abbrev=False`.
- Result fields: `gate_id`, `profile_id`, `command_id`, `status`, `observed_at`, `hashes`, `summary`, `cases`, `assertions`; optional failure result adds only `failure_code`.

- [ ] **Step 1: Write failing exact-path and atomic-failure tests**

```python
def test_unregistered_result_and_abbreviated_flag_are_denied(self):
    with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_RUNNER_CONTRACT_INVALID"):
        verify.parse_args(["--sch", verify.SCHEMA_REF])
    args = registered_namespace(result="artifacts/verification/other.json")
    with self.assertRaisesRegex(verify.EvidenceError, "EVIDENCE_RUNNER_CONTRACT_INVALID"):
        verify.validate_registered_paths(args)

def test_parse_failure_writes_no_exception_or_absolute_path(self):
    result = verify.safe_failure("evidence-positive-negative", "EVIDENCE_RUNNER_CONTRACT_INVALID")
    encoded = json.dumps(result)
    self.assertNotIn("exception", encoded.lower())
    self.assertNotIn(str(ROOT), encoded)
```

- [ ] **Step 2: Run CLI tests and observe RED**

Run: `python -m unittest tests.evidence_contract.test_verify.RegisteredCliTests -v`

Expected: FAIL until the exact-path CLI and safe atomic writer exist.

- [ ] **Step 3: Implement exact registration and atomic writes**

```python
TRUSTED_RESULTS = {
    "evidence-positive-negative": "artifacts/verification/vg-023-evidence-contract-result.json",
    "extension-provenance": "artifacts/verification/vg-023-extension-provenance-result.json",
}

def write_result_atomically(path: Path, result: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
```

Reject any schema, suite, result, or command literal not equal to the registered mapping before reading an untrusted input.

- [ ] **Step 4: Register the two exact E2 commands in `AGENTS.md`**

Register these commands with `cwd: "."`, `evidence_tier: E2`, and `required: true`:

```text
python tools/evidence_contract/verify.py --schema contracts/forgeops-evidence-contract/1.0/schema.json --suite fixtures/forgeops-evidence-contract/suite.json --result artifacts/verification/vg-023-evidence-contract-result.json --command-id evidence-positive-negative
python tools/evidence_contract/verify.py --schema contracts/forgeops-evidence-contract/1.0/schema.json --suite fixtures/forgeops-evidence-contract/suite.json --result artifacts/verification/vg-023-extension-provenance-result.json --command-id extension-provenance
```

- [ ] **Step 5: Run both registered commands and all evidence tests**

Run the two commands above, then:

Run: `python -m unittest discover -s tests/evidence_contract -p "test_*.py" -v`

Expected: both commands exit 0; both artifacts have `gate_id="VG-023"`, `status="PASSED"`, current schema/suite hashes, strict UTC `observed_at`, zero failed cases, and zero negative effects; all tests pass.

- [ ] **Step 6: Inspect fresh evidence before documentation changes**

Run: `python -m json.tool artifacts/verification/vg-023-evidence-contract-result.json`

Run: `python -m json.tool artifacts/verification/vg-023-extension-provenance-result.json`

Expected: only closed public-safe fields. Independently recompute schema and suite SHA-256 values and require exact equality with both artifacts.

- [ ] **Step 7: Synchronize only evidence-backed WBS/RTM/quality rows**

Change WBS-008 to `WBS_DONE` only if VG-004 remains fresh and both VG-023 commands pass at E2. Add the exact profile/commands to the quality plan and update only mapped RTM rows with actual artifact paths and observed times. Do not change WBS-009 or declare Phase 0 Exit.

- [ ] **Step 8: Run final checks**

Run both registered commands again after final file edits.

Run: `python -m unittest discover -s tests/evidence_contract -p "test_*.py" -v`

Run: `git diff --check`

Run: `git status --short`

Expected: commands and tests pass; no whitespace errors; only W4-1 implementation/evidence/status files are changed; the Git index remains untouched.
