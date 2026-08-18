# W7 Patch Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement WBS-020~WBS-022 as a deterministic ephemeral patch/diff, trusted-check, baseline-differential and anti-tamper flow with fresh VG-013 E2 evidence.

**Architecture:** Reuse W5 snapshot concepts and W6 registered-verifier patterns, but keep W7 in a focused `tools/patch_verification` package. Structured patch intent changes one exact workspace resource, registered Python callables evaluate task/regression/lint/type contracts, and a manifest-bound guard rejects verification weakening before result acceptance.

**Tech Stack:** Python 3 standard library, `jsonschema` Draft 2020-12, `unittest`, existing ForgeOps atomic-result and documentation patterns.

**Spec:** `docs/superpowers/specs/2026-08-19-w7-patch-verification-design.md`

## Global Constraints

- Work only in `C:\Users\User\AppData\Local\Temp\forgeops-w7-patch-verification` on `feature/w7-patch-verification`.
- Base is W6 commit `bc4bc5742c58c0899f829a431337cf6b40c35718`.
- Do not add third-party dependencies or download tools.
- Do not accept raw shell, raw unified diff or workspace-owned profile data as authority.
- Source, workspace and result paths are canonical project-relative or verifier-owned temporary paths; reject absolute, traversal, wildcard, symlink and reparse escape.
- W7 may claim only VG-013 E2 local observations. Keep VG-015, W8, Phase 1 safety gate and Phase 1 Exit `NOT_RUN`/planned.
- Every implementation step follows RED → minimal GREEN → regression → commit.
- Preserve user changes. Before every mutation round, inspect `git status --short`.

## File Structure

### New files

| Path | Responsibility |
| --- | --- |
| `contracts/forgeops-patch-verification/1.0/schema.json` | Closed suite and public result contract |
| `fixtures/forgeops-patch-verification/suite.json` | Exact 27-case catalog and public-safe base fixture |
| `tools/patch_verification/__init__.py` | Public W7 exports |
| `tools/patch_verification/model.py` | Errors, hashes, paths, timestamps, atomic JSON and audit model |
| `tools/patch_verification/patch.py` | Exact workspace mutation and bounded diff |
| `tools/patch_verification/profiles.py` | Trusted four-check registry and baseline differential |
| `tools/patch_verification/anti_tamper.py` | Protected verification manifest and semantic tamper categories |
| `tools/patch_verification/verify.py` | Registered three-command VG-013 CLI |
| `tests/patch_verification/__init__.py` | Test package marker |
| `tests/patch_verification/test_contracts.py` | Schema, catalog, registration and WBS scope tests |
| `tests/patch_verification/test_patch.py` | Patch/diff containment tests |
| `tests/patch_verification/test_profiles.py` | Trusted check and differential tests |
| `tests/patch_verification/test_anti_tamper.py` | Guard and zero-effect tests |
| `tests/patch_verification/test_verify.py` | Registered CLI, result, audit and atomicity tests |
| `artifacts/verification/vg-013-task-checks-result.json` | Fresh task-checks E2 result |
| `artifacts/verification/vg-013-regression-checks-result.json` | Fresh regression-checks E2 result |
| `artifacts/verification/vg-013-verification-anti-tamper-result.json` | Fresh anti-tamper E2 result |

### Modified files

| Path | Responsibility |
| --- | --- |
| `AGENTS.md` | Register three exact commands and profile |
| `docs/project/wbs.md` | WBS-020 VG-013 scope and W7 completion |
| `docs/product/prd.md` | PRD-FR-011/012 maturity after evidence |
| `docs/architecture/system-architecture.md` | Record local patch/trusted-check subset |
| `docs/project/requirements-traceability-matrix.md` | Attach three fresh VG-013 results |
| `docs/quality/verification-and-evaluation-plan.md` | Record VG-013 actual result and retained blockers |
| `README.md` | Describe W7 capability and non-claims |

---

### Task 1: Closed Contract, Exact Catalog, Registration, and WBS Re-scope

**Files:**
- Create: `contracts/forgeops-patch-verification/1.0/schema.json`
- Create: `fixtures/forgeops-patch-verification/suite.json`
- Create: `tests/patch_verification/__init__.py`
- Create: `tests/patch_verification/test_contracts.py`
- Modify: `AGENTS.md`
- Modify: `docs/project/wbs.md`

**Interfaces:**
- Consumes: W5 snapshot concepts, W6 registered command conventions, WBS-020~022 and VG-013 definitions.
- Produces: closed suite/result schema, exact `CASE_IDS`, three registered CLI identities and the final W7 ownership boundary used by Tasks 2~5.

- [x] **Step 1: Write failing contract and catalog tests**

Create `tests/patch_verification/test_contracts.py` with constants and these assertions:

```python
ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/forgeops-patch-verification/1.0/schema.json"
SUITE = ROOT / "fixtures/forgeops-patch-verification/suite.json"

COMMAND_CASE_IDS = {
    "task-checks": (
        "POSITIVE_BOUNDED_PATCH",
        "NEGATIVE_ABSOLUTE_RESOURCE",
        "NEGATIVE_TRAVERSAL_RESOURCE",
        "NEGATIVE_UNKNOWN_RESOURCE",
        "NEGATIVE_BEFORE_HASH_MISMATCH",
        "NEGATIVE_SOURCE_AS_WORKSPACE",
        "NEGATIVE_WORKSPACE_SYMLINK_ESCAPE",
        "NEGATIVE_DIFF_LIMIT",
        "NEGATIVE_RAW_PATCH_INPUT",
    ),
    "regression-checks": (
        "POSITIVE_TRUSTED_CHECKS",
        "NEGATIVE_TASK_CHECK_FAILURE",
        "NEGATIVE_NEW_REGRESSION",
        "NEGATIVE_BASELINE_UNHEALTHY",
        "NEGATIVE_LINT_FAILURE",
        "NEGATIVE_TYPECHECK_FAILURE",
        "NEGATIVE_UNKNOWN_PROFILE",
        "NEGATIVE_PROFILE_DIGEST_MISMATCH",
        "NEGATIVE_STALE_EVIDENCE",
    ),
    "verification-anti-tamper": (
        "POSITIVE_GUARDS_UNCHANGED",
        "NEGATIVE_TEST_DELETE",
        "NEGATIVE_SKIP_INJECTION",
        "NEGATIVE_XFAIL_INJECTION",
        "NEGATIVE_ASSERTION_WEAKEN",
        "NEGATIVE_COVERAGE_EXCLUSION",
        "NEGATIVE_PROFILE_CHANGE",
        "NEGATIVE_TEST_SYMLINK",
        "NEGATIVE_TEST_RENAME",
    ),
}
```

Tests must verify Draft 2020-12, recursive `additionalProperties: false`, exact ordered case IDs, unique IDs, exact command partition, exact fixture hashes, public result required fields, nullable unobserved counters, AGENTS command/path equality and WBS-020 VG-013-only ownership with WBS-021/022 still VG-013.

- [x] **Step 2: Run contract tests RED**

Run:

```powershell
python -m unittest tests.patch_verification.test_contracts -v
```

Expected: import/file failures because the contract, suite and registration do not exist.

- [x] **Step 3: Create the exact suite fixture**

Use these exact LF-terminated fixture bytes and hashes:

```text
src/calculator.py before_sha256=d7c0073ac57f6b7f11d524b13b0eb3a0badc43380985b593aa7a59b6b0d1b461
src/calculator.py after_sha256=a735f4673c5cdda031f0e3a32ae62b05c404cbd868f7b491df598d67051c7af1
tests/test_calculator.py sha256=9de315c74fa479ed3f924a2a38bbe5752cec3675d8175310e172a7052409f0ea
.coveragerc sha256=ee199da3fd728b9e24cc6ffe76dc69adf4db903056e1d56801d3163608e35dcd
verification-profile.json sha256=78891da4564a528c252606a97db065c9b784dd1d79c99384f2488f0ff64eb826
```

The suite root must contain exactly:

```json
{
  "suite_id": "forgeops-patch-verification-v1",
  "suite_version": "1.0",
  "schema_ref": "contracts/forgeops-patch-verification/1.0/schema.json",
  "profile_id": "forgeops-w7-fixture-checks",
  "base_fixture": {},
  "cases": []
}
```

Each case contains exactly `id`, `command_id`, `kind`, `mutation` and one of `expected_result` or `expected_error`.

- [x] **Step 4: Create the closed schema**

Define closed `$defs` for `fileFixture`, `patchIntent`, `case`, `baseFixture`, `suite`, `caseResult`, `summary`, `effectCounters`, `inputHashes` and `publicResult`. Use enums for the three commands, 27 mutations, `positive|negative`, `PASSED|FAILED`, `E2`, and stable error categories from the design.

`effectCounters` requires exactly:

```json
[
  "source_tree_hash_unchanged",
  "unauthorized_workspace_effects",
  "outside_workspace_write_attempts",
  "remote_write_attempts",
  "result_artifact_raw_secret_occurrences",
  "host_external_writes",
  "network_calls"
]
```

The last two accept only `null`; observed counts accept non-negative integers, and `source_tree_hash_unchanged` is boolean.

- [x] **Step 5: Register exact commands and profile**

Add these commands to `AGENTS.md`:

```yaml
- id: task-checks
  command: python tools/patch_verification/verify.py --schema contracts/forgeops-patch-verification/1.0/schema.json --suite fixtures/forgeops-patch-verification/suite.json --result artifacts/verification/vg-013-task-checks-result.json --command-id task-checks
  cwd: "."
  evidence_tier: E2
  required: true
- id: regression-checks
  command: python tools/patch_verification/verify.py --schema contracts/forgeops-patch-verification/1.0/schema.json --suite fixtures/forgeops-patch-verification/suite.json --result artifacts/verification/vg-013-regression-checks-result.json --command-id regression-checks
  cwd: "."
  evidence_tier: E2
  required: true
- id: verification-anti-tamper
  command: python tools/patch_verification/verify.py --schema contracts/forgeops-patch-verification/1.0/schema.json --suite fixtures/forgeops-patch-verification/suite.json --result artifacts/verification/vg-013-verification-anti-tamper-result.json --command-id verification-anti-tamper
  cwd: "."
  evidence_tier: E2
  required: true
```

Add profile `forgeops-patch-verification` with command IDs in exactly that order.

- [x] **Step 6: Re-scope WBS-020 without claiming completion**

Change WBS-020 VG IDs to `VG-013` and its DoD to local source/workspace/diff boundaries. Add an acceptance note that VG-015 remains W8 WBS-025/Phase integration scope. Keep WBS-020~022 `WBS_NOT_STARTED` until Task 5 generates fresh results.

- [x] **Step 7: Run contract tests GREEN and commit**

Run:

```powershell
python -m unittest tests.patch_verification.test_contracts -v
python -m unittest tests.local_vertical.test_contracts -v
python -m json.tool contracts/forgeops-patch-verification/1.0/schema.json > $null
python -m json.tool fixtures/forgeops-patch-verification/suite.json > $null
git diff --check
```

Commit:

```powershell
git add AGENTS.md docs/project/wbs.md contracts/forgeops-patch-verification fixtures/forgeops-patch-verification tests/patch_verification/__init__.py tests/patch_verification/test_contracts.py
git commit -m "feat: define W7 patch verification contract"
```

---

### Task 2: Bounded Ephemeral Patch and Canonical Diff

**Files:**
- Create: `tools/patch_verification/__init__.py`
- Create: `tools/patch_verification/model.py`
- Create: `tools/patch_verification/patch.py`
- Create: `tests/patch_verification/test_patch.py`

**Interfaces:**
- Consumes: Task 1 `base_fixture.patch_intent`, exact file fixtures and allowed resource list.
- Produces: `EffectAudit`, `PatchVerificationError`, `materialize_fixture`, `apply_bounded_patch` and a closed patch artifact consumed by Tasks 3~5.

- [x] **Step 1: Write failing positive patch test**

```python
def test_exact_patch_changes_only_workspace_and_returns_bounded_diff(self):
    source, workspace, intent, audit = self.fixture_bundle()
    before_source = tree_hash(source)
    artifact = apply_bounded_patch(source, workspace, intent, audit=audit)
    self.assertEqual(before_source, tree_hash(source))
    self.assertEqual(b"...return left + right...", normalized_calculator_bytes(workspace))
    self.assertEqual("src/calculator.py", artifact["resource_ref"])
    self.assertEqual(intent["before_sha256"], artifact["before_sha256"])
    self.assertEqual(intent["after_sha256"], artifact["after_sha256"])
    self.assertTrue(artifact["diff"].startswith("--- a/src/calculator.py\n+++ b/src/calculator.py\n"))
    self.assertEqual(1, audit.workspace_writes)
    self.assertEqual(0, audit.outside_workspace_write_attempts)
    self.assertEqual(0, audit.remote_write_attempts)
```

- [x] **Step 2: Write failing containment and limit tests**

Add subtests for absolute path, `../`, wildcard, unknown resource, before hash mismatch, source-as-workspace, symlink target, raw patch field, after hash mismatch, oversized diff and source mutation. Assert exact stable error and unchanged source; pre-mutation errors also require unchanged workspace.

- [x] **Step 3: Run patch tests RED**

```powershell
python -m unittest tests.patch_verification.test_patch -v
```

Expected: module import failure.

- [x] **Step 4: Implement model primitives**

`model.py` must define:

```python
class PatchVerificationError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

@dataclass
class EffectAudit:
    workspace_writes: int = 0
    outside_workspace_write_attempts: int = 0
    remote_write_attempts: int = 0

def sha256_bytes(value: bytes) -> str: ...
def tree_hash(root: Path) -> str: ...
def canonical_resource_ref(value: object) -> str: ...
def strict_utc(value: object) -> datetime: ...
def atomic_write_json(path: Path, value: object) -> None: ...
```

Tree hashing must reject symlink/reparse entries and hash ordinal root-relative POSIX paths plus raw bytes.

- [x] **Step 5: Implement fixture materialization and patch preflight**

Create every fixture file under verifier-owned roots with LF-preserved UTF-8 bytes. `apply_bounded_patch` requires exact intent fields:

```python
{
    "resource_ref",
    "before_sha256",
    "after_sha256",
    "replacement_text",
    "max_diff_bytes",
    "max_changed_lines",
}
```

Reject bool for integer limits, limits outside `1..65536` bytes or `1..2000` lines, and any target not an existing regular non-symlink file inside the workspace.

- [x] **Step 6: Implement atomic mutation and canonical diff**

Use a sibling temporary file and `os.replace`, then verify exact bytes. Generate diff with:

```python
difflib.unified_diff(
    before_text.splitlines(keepends=True),
    after_text.splitlines(keepends=True),
    fromfile=f"a/{resource_ref}",
    tofile=f"b/{resource_ref}",
    lineterm="\n",
)
```

Return exactly `resource_ref`, `before_sha256`, `after_sha256`, `diff`, `diff_sha256`, `diff_bytes`, `changed_lines`.

- [x] **Step 7: Run patch tests GREEN and commit**

```powershell
python -m unittest tests.patch_verification.test_patch -v
python -m unittest tests.snapshot_context.test_snapshot -v
python -m py_compile tools/patch_verification/model.py tools/patch_verification/patch.py
git diff --check
```

Commit:

```powershell
git add tools/patch_verification tests/patch_verification/test_patch.py
git commit -m "feat: add bounded W7 patch pipeline"
```

---

### Task 3: Trusted Check Registry and Baseline Differential

**Files:**
- Create: `tools/patch_verification/profiles.py`
- Create: `tests/patch_verification/test_profiles.py`
- Modify: `tools/patch_verification/__init__.py`

**Interfaces:**
- Consumes: Task 2 workspace and patch artifact.
- Produces: `TRUSTED_PROFILE`, `TRUSTED_PROFILE_DIGEST`, `run_trusted_profile`, `compare_baseline_and_changed` and fresh E2 check evidence.

- [x] **Step 1: Write failing exact profile tests**

Assert:

```python
self.assertEqual(
    ("TASK_TEST", "REGRESSION_TEST", "LINT", "TYPECHECK"),
    tuple(item["id"] for item in TRUSTED_PROFILE["checks"]),
)
self.assertEqual(
    canonical_sha256(TRUSTED_PROFILE),
    TRUSTED_PROFILE_DIGEST,
)
```

Mutating `verification-profile.json`, supplying an unknown profile, wrong digest, raw command, duplicate/reordered checks or stale/non-UTC time must fail before any check execution.

- [x] **Step 2: Write failing baseline differential tests**

Test these exact outcomes:

- baseline: `TASK_TEST=FAILED/TASK_EXPECTATION_FAILED`, other three `PASSED`
- patched: all four `PASSED`
- baseline regression/lint/type failure → `BASELINE_UNHEALTHY`
- post-patch task failure → `TASK_CHECK_FAILED`
- baseline-passed check failing after patch → `NEW_REGRESSION`
- all records have E2, strict UTC time, profile ID/digest and stable fingerprints

- [x] **Step 3: Run profile tests RED**

```powershell
python -m unittest tests.patch_verification.test_profiles -v
```

- [x] **Step 4: Implement exact registered checks**

Implement AST-based loading without importing workspace modules.

```python
TRUSTED_PROFILE = {
    "profile_id": "forgeops-w7-fixture-checks",
    "checks": [
        {"id": "TASK_TEST", "kind": "task"},
        {"id": "REGRESSION_TEST", "kind": "regression"},
        {"id": "LINT", "kind": "lint"},
        {"id": "TYPECHECK", "kind": "typecheck"},
    ],
}
```

The evaluator may execute only a minimal restricted expression model for the fixture functions: parse the exact `Return(BinOp(Name, Add|Sub, Name))` and `Return(Name)` forms, reject imports/calls/globals, and compute the two integer probes itself.

LINT checks UTF-8, LF, no trailing whitespace and AST parse for both Python files. TYPECHECK requires exact `int` annotations and return annotation for both fixture functions.

- [x] **Step 5: Implement evidence and differential**

Each check result contains exactly:

```python
{
    "check_id": check_id,
    "kind": kind,
    "status": "PASSED" or "FAILED",
    "reason": stable_reason,
    "evidence": {
        "evidence_id": f"EVID-W7-{check_id}-{phase}",
        "type": "test",
        "tier": "E2",
        "observed_at": observed_at,
        "profile_id": TRUSTED_PROFILE["profile_id"],
        "profile_digest": TRUSTED_PROFILE_DIGEST,
        "result_fingerprint": fingerprint,
    },
}
```

Do not include raw source, stdout/stderr or `exit_code` for non-command evidence.

- [x] **Step 6: Run profile tests GREEN and commit**

```powershell
python -m unittest tests.patch_verification.test_profiles -v
python -m unittest tests.snapshot_context.test_baseline -v
python -m unittest tests.evidence_contract.test_verify -v
python -m py_compile tools/patch_verification/profiles.py
git diff --check
```

Commit:

```powershell
git add tools/patch_verification/__init__.py tools/patch_verification/profiles.py tests/patch_verification/test_profiles.py
git commit -m "feat: add W7 trusted check profiles"
```

---

### Task 4: Verification Anti-Tamper Guard

**Files:**
- Create: `tools/patch_verification/anti_tamper.py`
- Create: `tests/patch_verification/test_anti_tamper.py`
- Modify: `tools/patch_verification/__init__.py`

**Interfaces:**
- Consumes: Task 1 protected fixture files and Task 3 trusted profile digest.
- Produces: `build_guard_manifest` and `verify_guard_manifest`, returning a closed guard result used before Task 5 accepts checks.

- [x] **Step 1: Write failing unchanged guard test**

```python
manifest = build_guard_manifest(workspace, TRUSTED_PROFILE_DIGEST)
result = verify_guard_manifest(
    workspace,
    manifest,
    trusted_profile_digest=TRUSTED_PROFILE_DIGEST,
)
self.assertEqual("PASSED", result["status"])
self.assertEqual(0, result["tamper_count"])
self.assertEqual(
    ["tests/test_calculator.py", ".coveragerc", "verification-profile.json"],
    [item["path"] for item in manifest["protected_files"]],
)
```

- [x] **Step 2: Write failing tamper category tests**

Mutate one item per subtest and assert the exact code:

```text
delete/rename test -> TEST_DELETED or TEST_PATH_INVALID
@unittest.skip -> TEST_SKIP_INJECTED
@unittest.expectedFailure or xfail token -> TEST_XFAIL_INJECTED
self.assertEqual(5, ...) -> self.assertTrue(True) -> ASSERTION_WEAKENED
.coveragerc omit/include change -> COVERAGE_POLICY_CHANGED
verification-profile.json change or trusted digest change -> VERIFICATION_PROFILE_CHANGED
test file symlink -> TEST_PATH_INVALID
```

Every negative asserts source unchanged and no new file/write after guard invocation.

- [x] **Step 3: Run guard tests RED**

```powershell
python -m unittest tests.patch_verification.test_anti_tamper -v
```

- [x] **Step 4: Implement closed manifest and semantic fingerprints**

Manifest exact fields:

```python
{
    "manifest_version": "1.0",
    "trusted_profile_digest": digest,
    "protected_files": [
        {"path": path, "sha256": digest, "semantic_fingerprint": semantic},
        ...
    ],
    "test_paths": ["tests/test_calculator.py"],
}
```

For tests, semantic fingerprint is canonical JSON of test class/function names, decorators, assertion call names and AST dumps of assertion arguments. For coverage/profile files it is canonical parsed data. Reject extra/missing manifest fields, duplicate paths and non-list arrays.

- [x] **Step 5: Implement stable precedence and zero-effect verification**

Check containment and file type before reading bytes. Detect skip/xfail/assertion weakening before generic hash mismatch so specific categories remain stable. Reject any unexpected `tests/test_*.py` path to catch rename/addition.

- [x] **Step 6: Run guard tests GREEN and commit**

```powershell
python -m unittest tests.patch_verification.test_anti_tamper -v
python -m unittest tests.patch_verification.test_patch tests.patch_verification.test_profiles -v
python -m py_compile tools/patch_verification/anti_tamper.py
git diff --check
```

Commit:

```powershell
git add tools/patch_verification/__init__.py tools/patch_verification/anti_tamper.py tests/patch_verification/test_anti_tamper.py
git commit -m "feat: add W7 verification anti-tamper guard"
```

---

### Task 5: Registered VG-013 Results and Evidence-Grounded W7 Closure

**Files:**
- Create: `tools/patch_verification/verify.py`
- Create: `tests/patch_verification/test_verify.py`
- Modify: `tools/patch_verification/__init__.py`
- Create: `artifacts/verification/vg-013-task-checks-result.json`
- Create: `artifacts/verification/vg-013-regression-checks-result.json`
- Create: `artifacts/verification/vg-013-verification-anti-tamper-result.json`
- Modify: `docs/project/wbs.md`
- Modify: `docs/product/prd.md`
- Modify: `docs/architecture/system-architecture.md`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/quality/verification-and-evaluation-plan.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: Tasks 1~4 schema, suite, patch artifact, differential result and guard result.
- Produces: registered `run(args, repository_root=...) -> int`, three fresh closed VG-013 artifacts and evidence-grounded W7 status.

- [x] **Step 1: Write failing registered CLI tests**

Test exact `TRUSTED_COMMANDS` identity, wrong command/result/schema/suite pair preserving a sentinel, malformed schema/suite preserving result, atomic replacement, exact case partition/order, raw input hashes, public-safe output, runner error exit 2, case failure exit 1 and success exit 0.

The success assertion for each command:

```python
self.assertEqual("VG-013", result["gate_id"])
self.assertEqual("forgeops-patch-verification", result["profile_id"])
self.assertEqual(command_id, result["command_id"])
self.assertEqual("PASSED", result["status"])
self.assertEqual("E2", result["evidence_tier"])
self.assertEqual(9, result["summary"]["total"])
self.assertEqual(9, result["summary"]["passed"])
self.assertEqual(0, result["summary"]["failed"])
```

- [x] **Step 2: Write failing audit false-positive tests**

Monkeypatch each observed invariant independently:

- source hash changed
- expected workspace file deleted/wrong bytes/symlink
- outside workspace attempts = 1
- remote write attempts = 1
- result secret occurrence = 1

Each must write a closed `FAILED` result and return 1. Unobserved `host_external_writes` and `network_calls` must remain `None`, not zero.

- [x] **Step 3: Run verifier tests RED**

```powershell
python -m unittest tests.patch_verification.test_verify -v
```

- [x] **Step 4: Implement exact command evaluation**

```python
TRUSTED_COMMANDS = {
    "task-checks": "artifacts/verification/vg-013-task-checks-result.json",
    "regression-checks": "artifacts/verification/vg-013-regression-checks-result.json",
    "verification-anti-tamper": "artifacts/verification/vg-013-verification-anti-tamper-result.json",
}
```

For each selected case, create a fresh temporary source/workspace bundle, apply only the named mutation, run the relevant Task 2/3/4 path, compare expected/actual, then audit source/workspace/effects. Catch only `PatchVerificationError` as expected product failure; unexpected exceptions are runner errors and must not replace the prior result.

- [x] **Step 5: Assemble and validate public results**

Capture one strict UTC `observed_at` per command. Hash schema and suite raw bytes plus `tools/patch_verification/profiles.py` as `profile_source`. Validate the complete result against `$defs.publicResult` before `atomic_write_json`.

Secret scan patterns include assignment-like `token`, `secret`, `password`, `credential`, `api_key`, `access_token`, absolute workspace paths and raw fixture source outside the bounded diff field.

- [x] **Step 6: Run focused tests and exact VG-013 commands**

```powershell
python -m unittest discover -s tests/patch_verification -v
python tools/patch_verification/verify.py --schema contracts/forgeops-patch-verification/1.0/schema.json --suite fixtures/forgeops-patch-verification/suite.json --result artifacts/verification/vg-013-task-checks-result.json --command-id task-checks
python tools/patch_verification/verify.py --schema contracts/forgeops-patch-verification/1.0/schema.json --suite fixtures/forgeops-patch-verification/suite.json --result artifacts/verification/vg-013-regression-checks-result.json --command-id regression-checks
python tools/patch_verification/verify.py --schema contracts/forgeops-patch-verification/1.0/schema.json --suite fixtures/forgeops-patch-verification/suite.json --result artifacts/verification/vg-013-verification-anti-tamper-result.json --command-id verification-anti-tamper
```

Expected: each result 9/9 E2 `PASSED`, failed 0; all observed effect counters safe.

- [x] **Step 7: Run linked verification**

Run exact registered commands for:

```text
VG-010: snapshot-identity, baseline-retrieval-repeat
VG-012: main-part-work-main
VG-023: evidence-positive-negative, extension-provenance
```

Restore/exclude timestamp-only changes to pre-existing artifacts; W7 owns only three VG-013 results.

- [x] **Step 8: Update evidence-owned documentation**

Only after Step 6 succeeds:

- WBS-020~022 → `WBS_DONE`; keep WBS-023 onward unchanged.
- PRD-FR-011/012 → `IMPLEMENTED`.
- RTM PRD-FR-011/012 → `PASSED`, E2, three VG-013 result refs and exact artifact times; state that VG-015 remains `NOT_RUN`.
- architecture records local patch/trusted verification subset without claiming OS sandbox or trace completeness.
- verification plan records all three commands 9/9 and VG-013 actual `PASSED`; Phase 1 remains `NOT_RUN`.
- README describes W7 and explicitly retains VG-014/VG-015/Phase 1 blockers.

- [x] **Step 9: Run full regression and consistency checks**

```powershell
python -m unittest discover -s tests -v
python -m py_compile tools/patch_verification/__init__.py tools/patch_verification/model.py tools/patch_verification/patch.py tools/patch_verification/profiles.py tools/patch_verification/anti_tamper.py tools/patch_verification/verify.py tests/patch_verification/__init__.py tests/patch_verification/test_contracts.py tests/patch_verification/test_patch.py tests/patch_verification/test_profiles.py tests/patch_verification/test_anti_tamper.py tests/patch_verification/test_verify.py
git diff --check
git status --short
```

Use a read-only consistency script to assert:

- three VG-013 results are E2 `PASSED`, each 9/9, failed 0
- all schema/suite/profile input hashes match raw bytes
- WBS-020~022 are DONE; WBS-023 onward are not started
- PRD-FR-011/012 and RTM are PASSED with exact observed times
- VG-015 and Phase 1 Exit remain NOT_RUN
- no result contains raw secret or absolute temporary path

- [x] **Step 10: Review complete W7 diff and commit**

Review merge base `bc4bc57..HEAD` for spec coverage, path containment, profile authority, baseline differential, tamper categories, effect-counter honesty and documentation claims. Resolve all Critical/Important findings before completion.

Commit:

```powershell
git add README.md docs AGENTS.md tools/patch_verification tests/patch_verification contracts/forgeops-patch-verification fixtures/forgeops-patch-verification artifacts/verification/vg-013-*.json
git commit -m "feat: complete W7 patch verification"
```

---

## Plan Self-Review Checklist

- [x] Exactly five independently testable tasks map to WBS-020~022 and VG-013.
- [x] Every new file has one responsibility and named public interfaces.
- [x] All 27 case IDs and three command/result paths are exact.
- [x] Test, regression, lint and typecheck meanings are explicit without external dependencies.
- [x] Source/workspace/remote effect observations and OS-unobserved nulls are separated.
- [x] WBS-020 re-scope preserves W8/VG-015 ownership.
- [x] No raw shell, raw diff authority, placeholder, unnamed test or undefined neighboring interface remains.
- [x] Final verification includes full regression, linked VGs, public-safety and documentation consistency.

## Execution Choice

The user pre-approved the Inline Execution path for this plan: execute Tasks 1~5 sequentially in this session using `superpowers:executing-plans`, with checkpoints after each task and no push/PR/merge.
