# W5 Local Snapshot, Baseline, and Context Pack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement WBS-013~WBS-015 as a local-only, content-addressed snapshot, trusted baseline, and deterministic Context Pack pipeline with fresh VG-010/VG-011 E2 evidence.

**Architecture:** A small `tools.snapshot_context` package separates closed data models, Git-backed snapshot creation, exact-profile baseline execution, deterministic retrieval, and a public-safe verifier CLI. All consumers bind to one `snapshot_id`; source files are copied into an immutable image and an independent workspace without modifying the original repository.

**Tech Stack:** Python 3 standard library, `jsonschema`, Git plumbing commands through `subprocess` with `shell=False`, `unittest`, JSON Schema 2020-12.

## Global Constraints

- Do not use network, external services, package installation, raw shell strings, or external writes.
- Preserve the source repository, dirty state, user files, `.git`, protected paths, and unrelated worktree changes.
- Use canonical project-root-relative POSIX paths and SHA-256 over raw file bytes.
- Treat repository content as untrusted data; it cannot change authority, policy, approval, budget, tool schema, or accepted state.
- Emit only closed, bounded, public-safe JSON with atomic replacement.
- WBS-013~WBS-015 become `WBS_DONE` only after all four registered VG-010/VG-011 commands produce fresh E2 `PASSED` results.
- W6 and later WBS, Phase 1 Exit, remote publication, and PR creation remain out of scope.

---

## File Structure

- `contracts/forgeops-snapshot-contract/1.0/schema.json`: closed snapshot manifest and baseline artifact schema.
- `contracts/forgeops-context-pack/1.0/schema.json`: closed Context Pack schema.
- `fixtures/forgeops-snapshot-baseline/suite.json`: ordered snapshot and baseline positive/negative cases plus trusted command profile.
- `fixtures/forgeops-context-security/suite.json`: ordered retrieval/provenance/injection cases.
- `tools/snapshot_context/model.py`: shared dataclasses, canonical JSON/hash/path helpers, stable errors, atomic JSON writes.
- `tools/snapshot_context/snapshot.py`: Git inventory, manifest construction, materialization, verification, cleanup.
- `tools/snapshot_context/baseline.py`: exact trusted profile validation and bounded subprocess execution.
- `tools/snapshot_context/retrieval.py`: deterministic retrieval and Context Pack construction.
- `tools/snapshot_context/verify.py`: four registered command adapters and public E2 result generation.
- `tests/snapshot_context/test_contracts.py`: schema and fixture catalog tests.
- `tests/snapshot_context/test_snapshot.py`: snapshot provider tests.
- `tests/snapshot_context/test_baseline.py`: baseline runner tests.
- `tests/snapshot_context/test_retrieval.py`: retrieval and injection tests.
- `tests/snapshot_context/test_verify.py`: CLI, exact identity, public result, and runner-failure tests.

---

### Task 1: Closed Contracts and Ordered Fixtures

**Files:**
- Create: `contracts/forgeops-snapshot-contract/1.0/schema.json`
- Create: `contracts/forgeops-context-pack/1.0/schema.json`
- Create: `fixtures/forgeops-snapshot-baseline/suite.json`
- Create: `fixtures/forgeops-context-security/suite.json`
- Create: `tests/snapshot_context/__init__.py`
- Create: `tests/snapshot_context/test_contracts.py`

**Interfaces:**
- Consumes: W5 design, VG-010/VG-011 rows, Protocol 2.0 public evidence conventions.
- Produces: snapshot schema ID `contracts/forgeops-snapshot-contract/1.0/schema.json`, context schema ID `contracts/forgeops-context-pack/1.0/schema.json`, exact fixture catalogs used by Tasks 2~5.

- [ ] **Step 1: Write schema identity and closed-field tests**

```python
class SnapshotContextContractTests(unittest.TestCase):
    def test_schemas_are_draft_2020_12_and_closed(self):
        for path, schema_id in (
            (SNAPSHOT_SCHEMA, "contracts/forgeops-snapshot-contract/1.0/schema.json"),
            (CONTEXT_SCHEMA, "contracts/forgeops-context-pack/1.0/schema.json"),
        ):
            schema = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(schema_id, schema["$id"])
            self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
            self.assertFalse(schema["additionalProperties"])
            Draft202012Validator.check_schema(schema)

    def test_fixture_case_catalogs_are_exact_and_unique(self):
        snapshot = load_json(SNAPSHOT_SUITE)
        context = load_json(CONTEXT_SUITE)
        self.assertEqual(SNAPSHOT_CASES, tuple(case["id"] for case in snapshot["cases"]))
        self.assertEqual(CONTEXT_CASES, tuple(case["id"] for case in context["cases"]))
```

Exact snapshot catalog:

```python
SNAPSHOT_CASES = (
    "POSITIVE_CLEAN_REPEAT",
    "POSITIVE_DIRTY_STAGED_MODIFIED_UNTRACKED",
    "POSITIVE_WORKSPACE_SEPARATION",
    "NEGATIVE_SOURCE_NOT_GIT",
    "NEGATIVE_PATH_TRAVERSAL",
    "NEGATIVE_SYMLINK",
    "NEGATIVE_PROTECTED_PATH",
    "NEGATIVE_CONTENT_CHANGED",
    "NEGATIVE_PROFILE_RAW_SHELL",
    "NEGATIVE_PROFILE_CWD_ESCAPE",
    "NEGATIVE_BASELINE_NONZERO",
    "NEGATIVE_BASELINE_TIMEOUT",
)
```

Exact context catalog:

```python
CONTEXT_CASES = (
    "POSITIVE_PATH_SELECTION",
    "POSITIVE_CONTENT_SELECTION",
    "POSITIVE_REPEATABLE_PACK",
    "NEGATIVE_EMPTY_QUERY",
    "NEGATIVE_TOP_K_RANGE",
    "NEGATIVE_MANIFEST_HASH_MISMATCH",
    "NEGATIVE_BINARY_EXCLUDED",
    "NEGATIVE_OVERSIZED_EXCLUDED",
    "NEGATIVE_REPOSITORY_INSTRUCTION",
    "NEGATIVE_CONTROL_FIELD_INJECTION",
)
```

- [ ] **Step 2: Run the contract tests and observe RED**

Run: `python -m unittest tests.snapshot_context.test_contracts`

Expected: import/file failures because the schemas and suites do not exist.

- [ ] **Step 3: Create the snapshot schema**

Require exact top-level fields:

```json
{
  "snapshot_version": "1.0",
  "snapshot_id": "sha256:<64 lowercase hex>",
  "source": {
    "repository_label": "fixture-repository",
    "head_sha": "<40 lowercase hex or UNBORN>",
    "git_state_sha256": "<64 lowercase hex>"
  },
  "dirty": true,
  "entries": [],
  "deleted_paths": [],
  "manifest_sha256": "<64 lowercase hex>"
}
```

Entry fields are exactly `path`, `size`, `sha256`, `mode`, `source_states`; `source_states` is a unique ordered subset of `tracked`, `staged`, `modified`, `untracked`. Add a `$defs.baseline_artifact` with exact profile, command result, status, count, truncation, and `result_fingerprint` fields. Forbid unknown fields at every object level.

- [ ] **Step 4: Create the Context Pack schema**

Require exact fields `context_pack_version`, `snapshot_id`, `query_tokens`, `items`, `summary`, `control_claims_accepted`. Each item has exactly `path`, `sha256`, `size`, `media_type`, `selection_reason`, `score`, `excerpt`, `trust`. Fix `trust` to `UNTRUSTED_SOURCE` and `control_claims_accepted` to false.

- [ ] **Step 5: Create both ordered suites**

Snapshot suite top-level fields are exactly `suite_id`, `suite_version`, `snapshot_schema_ref`, `context_schema_ref`, `trusted_profile`, `cases`. Context suite uses the same identity fields except `trusted_profile`. Every case has exact `id`, `kind`, `mutation`, and `expected_result` or `expected_error`. Use stable errors from the design and a trusted profile with argv arrays only.

- [ ] **Step 6: Run Task 1 tests**

Run: `python -m unittest tests.snapshot_context.test_contracts`

Expected: all tests pass.

- [ ] **Step 7: Inspect and commit**

Run: `git diff --check`

```powershell
git add -- contracts/forgeops-snapshot-contract/1.0/schema.json contracts/forgeops-context-pack/1.0/schema.json fixtures/forgeops-snapshot-baseline/suite.json fixtures/forgeops-context-security/suite.json tests/snapshot_context/__init__.py tests/snapshot_context/test_contracts.py
git commit -m "feat: define W5 snapshot and context contracts"
```

---

### Task 2: Immutable Snapshot Provider

**Files:**
- Create: `tools/snapshot_context/__init__.py`
- Create: `tools/snapshot_context/model.py`
- Create: `tools/snapshot_context/snapshot.py`
- Create: `tests/snapshot_context/test_snapshot.py`

**Interfaces:**
- Consumes: snapshot schema and fixture catalog from Task 1.
- Produces: `SnapshotError`, `SnapshotEntry`, `SnapshotBundle`, `create_snapshot()`, `verify_snapshot()` for Tasks 3~5.

```python
class SnapshotError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code

@dataclass(frozen=True)
class SnapshotEntry:
    path: str
    size: int
    sha256: str
    mode: str
    source_states: Sequence[str]

@dataclass(frozen=True)
class SnapshotBundle:
    manifest: dict[str, object]
    snapshot_root: Path
    workspace_root: Path
```

Exact callable signatures are `create_snapshot(source_root: Path, destination_root: Path, repository_label: str, *, runner: ProcessRunner = subprocess.run) -> SnapshotBundle` and `verify_snapshot(snapshot_root: Path, manifest: Mapping[str, object]) -> None`.

- [ ] **Step 1: Write failing clean/dirty/repeat tests**

Create temp Git repositories with `git init`, local user configuration, a committed file, then staged, modified, deleted and untracked changes. Assert repeated manifests have the same `snapshot_id`, combined staged+modified states are preserved, deleted paths are recorded, and source status/bytes do not change.

- [ ] **Step 2: Write failing containment tests**

Assert non-Git input, absolute/traversal paths, `.git`, `.env`, credential-like path, symlink/reparse point and content mutation return the exact design error. Confirm failed creation leaves no destination manifest.

- [ ] **Step 3: Run snapshot tests and observe RED**

Run: `python -m unittest tests.snapshot_context.test_snapshot`

Expected: module import failure.

- [ ] **Step 4: Implement canonical helpers in `model.py`**

```python
def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def canonical_relative_path(raw: str) -> PurePosixPath:
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts or "\\" in raw or "//" in raw:
        raise SnapshotError("SNAPSHOT_PATH_INVALID")
    return path
```

Add public-safe atomic JSON writing with `tempfile.mkstemp` and `os.replace`.

- [ ] **Step 5: Implement NUL-delimited Git inventory**

Use exact argv calls with ten-second timeouts. Parse `git ls-files -z --cached --others --exclude-standard` and `git status --porcelain=v2 -z --untracked-files=all`. Preserve simultaneous staged and modified flags in `source_states`; sort paths ordinally.

- [ ] **Step 6: Implement snapshot materialization**

Validate every path and file type before reading. Read each regular file once into a temporary snapshot tree, record before/after stat, hash raw bytes, copy the complete snapshot into a separate workspace, verify every materialized hash, then atomically rename the bundle. On any error remove only the newly created temporary sibling.

- [ ] **Step 7: Run Task 2 tests**

Run: `python -m unittest tests.snapshot_context.test_snapshot`

Expected: all tests pass with source bytes and Git status unchanged.

- [ ] **Step 8: Commit**

```powershell
git add -- tools/snapshot_context/__init__.py tools/snapshot_context/model.py tools/snapshot_context/snapshot.py tests/snapshot_context/test_snapshot.py
git commit -m "feat: add immutable local snapshot provider"
```

---

### Task 3: Trusted Baseline Runner

**Files:**
- Create: `tools/snapshot_context/baseline.py`
- Create: `tests/snapshot_context/test_baseline.py`

**Interfaces:**
- Consumes: verified `SnapshotBundle` and trusted profile from Task 1.
- Produces: `validate_profile()` and `run_baseline()` for Task 5.

Exact callable signatures are `validate_profile(profile: Mapping[str, object]) -> Sequence[dict[str, object]]` and `run_baseline(workspace_root: Path, manifest: Mapping[str, object], profile: Mapping[str, object], *, popen_factory: Callable = subprocess.Popen, clock: Callable[[], datetime] = utc_now) -> dict[str, object]`. `utc_now()` returns `datetime.now(timezone.utc)`.

- [ ] **Step 1: Write failing profile validation tests**

Cover valid ordered commands and rejection of unknown fields, duplicate IDs, scalar/raw shell argv, empty arguments, absolute/traversal cwd, timeout outside 1..300, output cap outside 1024..1048576 and shell metacharacter command identity.

- [ ] **Step 2: Write failing execution tests**

Use short Python child processes to assert exit 0 `PASSED`, exit non-zero `BASELINE_UNHEALTHY`, timeout `BASELINE_TIMEOUT`, missing executable `BASELINE_RUNNER_ERROR`, and output beyond cap sets `output_truncated=true` without raw output in the artifact.

- [ ] **Step 3: Run baseline tests and observe RED**

Run: `python -m unittest tests.snapshot_context.test_baseline`

Expected: module import failure.

- [ ] **Step 4: Implement exact profile validation**

Validate raw JSON types before casting. Keep argv and cwd exact, use ordinal unique IDs, reject `|`, `&&`, `||`, `;`, redirection and wildcard tokens in executable identity, and confirm cwd resolves inside workspace without symlink traversal.

- [ ] **Step 5: Implement bounded process draining**

Use `Popen(shell=False, stdout=PIPE, stderr=PIPE, env=minimal_environment)` with two daemon reader threads. Readers count all bytes, retain none, and set truncation once the configured cap is exceeded. On timeout terminate, wait for a short bounded grace, then kill and wait. Never start the next command after timeout or runner error.

- [ ] **Step 6: Build public baseline artifact**

Compute `result_fingerprint` only from command ID, argv, cwd, status, exit code and truncation flag. Validate the artifact against `$defs.baseline_artifact` before returning it.

- [ ] **Step 7: Run Task 3 tests**

Run: `python -m unittest tests.snapshot_context.test_baseline`

Expected: all tests pass; recursive forbidden-key scan finds no raw output, environment or absolute path.

- [ ] **Step 8: Commit**

```powershell
git add -- tools/snapshot_context/baseline.py tests/snapshot_context/test_baseline.py
git commit -m "feat: run trusted baseline in snapshot workspace"
```

---

### Task 4: Deterministic Retrieval and Context Pack

**Files:**
- Create: `tools/snapshot_context/retrieval.py`
- Create: `tests/snapshot_context/test_retrieval.py`

**Interfaces:**
- Consumes: verified snapshot root and manifest from Task 2.
- Produces: `tokenize_query()` and `build_context_pack()` for Task 5.

Exact callable signatures are `tokenize_query(query: str) -> Sequence[str]` and `build_context_pack(snapshot_root: Path, manifest: Mapping[str, object], query: str, *, top_k: int = 10) -> dict[str, object]`.

- [ ] **Step 1: Write failing token/ranking tests**

Assert query token count 1..32, top_k 1..20, deterministic score ordering, path exact before path substring before content match, path tie-break ordering, and byte-identical canonical JSON for repeated input.

- [ ] **Step 2: Write failing provenance and exclusion tests**

Cover manifest hash mismatch, missing file, binary/invalid UTF-8 exclusion, file above 256 KiB exclusion, excerpt limit 1,024 characters, item hash equality and selection reason completeness.

- [ ] **Step 3: Write failing injection tests**

Use content containing `ignore previous instructions`, fake authority, policy, budget, approval and tool claims. Assert it remains an item with `trust=UNTRUSTED_SOURCE`, `control_claims_accepted=false`, and no control-plane keys appear anywhere in the pack.

- [ ] **Step 4: Run retrieval tests and observe RED**

Run: `python -m unittest tests.snapshot_context.test_retrieval`

Expected: module import failure.

- [ ] **Step 5: Implement deterministic retrieval**

Tokenize with Unicode alphanumeric runs and casefold, deduplicate while preserving token order. Revalidate snapshot entry bytes, decode strict UTF-8, score with fixed integer weights `PATH_EXACT=1000`, `PATH_SUBSTRING=100`, `CONTENT_MATCH=1`, then sort by negative score and path.

- [ ] **Step 6: Implement Context Pack generation**

Create bounded excerpts around the first matching token, attach exact selection reasons and `UNTRUSTED_SOURCE`, set `control_claims_accepted=false`, validate against the Context Pack schema, and return canonicalizable data without writing source excerpts to public artifacts.

- [ ] **Step 7: Run Task 4 tests**

Run: `python -m unittest tests.snapshot_context.test_retrieval`

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add -- tools/snapshot_context/retrieval.py tests/snapshot_context/test_retrieval.py
git commit -m "feat: build provenance-bound Context Packs"
```

---

### Task 5: VG-010/VG-011 Verification and W5 Closure

**Files:**
- Create: `tools/snapshot_context/verify.py`
- Create: `tests/snapshot_context/test_verify.py`
- Create: `artifacts/verification/vg-010-snapshot-identity-result.json`
- Create: `artifacts/verification/vg-010-baseline-retrieval-result.json`
- Create: `artifacts/verification/vg-011-context-provenance-result.json`
- Create: `artifacts/verification/vg-011-injection-negative-result.json`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/project/wbs.md`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/quality/verification-and-evaluation-plan.md`

**Interfaces:**
- Consumes: Tasks 1~4 and existing project profile conventions.
- Produces: four registered E2 results, WBS-013~015 completion evidence, and W6 handoff inputs.

- [ ] **Step 1: Write failing verifier CLI tests**

Cover exact subcommands `snapshot-baseline` and `context`, exact schema/suite/result literals, exact command IDs, four successful results, wrong command/result pair rejection, runner failure exit 2, atomic result replacement, closed public fields and no absolute path/raw output/environment/secret-like key.

- [ ] **Step 2: Run verifier tests and observe RED**

Run: `python -m unittest tests.snapshot_context.test_verify`

Expected: verifier module import failure.

- [ ] **Step 3: Implement fixture adapters**

The verifier creates a temporary Git repository per case, applies only the catalog mutation, calls Tasks 2~4, compares the stable actual result with the case expectation, and deletes the temporary bundle. It never snapshots the developer worktree or writes outside the requested registered result.

Result shape:

```json
{
  "result_version": "1.0",
  "gate_id": "VG-010",
  "profile_id": "forgeops-snapshot-baseline",
  "command_id": "snapshot-identity",
  "status": "PASSED",
  "evidence_tier": "E2",
  "observed_at": "runtime UTC",
  "input_hashes": {
    "snapshot_schema_sha256": "64 lowercase hexadecimal characters",
    "context_schema_sha256": "64 lowercase hexadecimal characters",
    "suite_sha256": "64 lowercase hexadecimal characters"
  },
  "summary": {"total": 0, "passed": 0, "failed": 0},
  "effect_counters": {"source_writes": 0, "protected_reads": 0, "network_calls": 0, "external_writes": 0},
  "cases": []
}
```

- [ ] **Step 4: Register exact validation commands in `AGENTS.md`**

Add four required E2 records and two profiles:

```yaml
- id: snapshot-identity
  command: python tools/snapshot_context/verify.py snapshot-baseline --snapshot-schema contracts/forgeops-snapshot-contract/1.0/schema.json --context-schema contracts/forgeops-context-pack/1.0/schema.json --suite fixtures/forgeops-snapshot-baseline/suite.json --result artifacts/verification/vg-010-snapshot-identity-result.json --command-id snapshot-identity
  cwd: "."
  evidence_tier: E2
  required: true
```

Repeat with command IDs and result paths `baseline-retrieval-repeat`, `context-provenance`, `injection-negative`; the latter two use `context` and `fixtures/forgeops-context-security/suite.json`.

- [ ] **Step 5: Run all four registered commands**

Run each exact `AGENTS.md` command. Expected: exit 0, E2 `PASSED`, zero failed cases, and all four effect counters zero.

- [ ] **Step 6: Update W5 documentation from fresh results**

Set WBS-013~015 to `WBS_DONE`, update PRD-FR-008 and PRD-FR-009 to `IMPLEMENTED`/`PASSED`, retain cross-phase NFR rows as `NOT_RUN` where later WBS/VGs remain, add W5/VG-010/VG-011 status to README and verification plan, and explicitly keep WBS-016 onward and Phase 1 Exit incomplete.

- [ ] **Step 7: Run focused and full verification**

```powershell
python -m unittest discover -s tests/snapshot_context -p "test_*.py"
python -m unittest discover -s tests -p "test_*.py"
git diff --check
```

Expected: all W5 tests pass, all existing tests pass with only the known Windows symlink privilege skip, and no whitespace errors.

- [ ] **Step 8: Cross-document and evidence consistency check**

Verify programmatically that all four results are `PASSED`, input hashes match raw repository bytes, WBS-013~015 are `WBS_DONE`, WBS-016 remains `WBS_NOT_STARTED`, RTM row count remains 37, and no document claims Phase 1 Exit.

- [ ] **Step 9: Final diff review and commit**

```powershell
git add -- AGENTS.md README.md contracts/forgeops-snapshot-contract/1.0/schema.json contracts/forgeops-context-pack/1.0/schema.json fixtures/forgeops-snapshot-baseline/suite.json fixtures/forgeops-context-security/suite.json tools/snapshot_context tests/snapshot_context artifacts/verification/vg-010-snapshot-identity-result.json artifacts/verification/vg-010-baseline-retrieval-result.json artifacts/verification/vg-011-context-provenance-result.json artifacts/verification/vg-011-injection-negative-result.json docs/project/wbs.md docs/project/requirements-traceability-matrix.md docs/quality/verification-and-evaluation-plan.md
git commit -m "feat: complete W5 snapshot baseline and context"
```

---

## Plan Self-Review Record

- Spec coverage: Tasks 1~5 cover every approved W5 design section and WBS-013~015 deliverable.
- Placeholder scan: no deferred implementation, unspecified error handling, or generic “add tests” step remains.
- Interface consistency: Tasks 3 and 4 consume the exact `SnapshotBundle` and manifest produced by Task 2; Task 5 consumes the named functions and registered paths from Tasks 1~4.
- Scope: no W6 orchestration, patch pipeline, external service, network action, publication, or Phase 1 Exit claim is included.
