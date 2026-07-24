# W3-4 Task 2 Implementation Report

## Scope

Implemented only Task 2, "Resolve catalogs, references, freshness, and sensitive boundaries," from the approved W3-4 plan. The work remains in-memory and does not add storage, runtime behavior, WBS/RTM changes, Git operations, network access, or external effects.

## Changed resources

- `tools/interface_contract/manifest_contract.py`
  - Adds exact artifact, evidence, and decision identity indexing.
  - Rejects duplicate catalog IDs and duplicate decision references.
  - Resolves artifact/evidence references within the same manifest and rejects dangling IDs.
  - Enforces inclusive producer sequence bounds for artifact, evidence, and decision records.
  - Enforces the file/diff revision freshness branch and command/test/render/runtime/approval strict-UTC branch.
  - Accepts only literal project-root-relative source references or closed `forgeops:<kind>:<opaque-id>` URNs.
  - Rejects absolute, drive, UNC, traversal, backslash, wildcard, query, fragment, encoded, URL, signed URL, `.env`, credential/secret/token paths, secret fields, tenant identifiers, and raw-path content.
  - Adds exact case-envelope and same-task/run `resolution_context` validation.
  - Adds a `StorageSpy` seam; validation never invokes it.
- `fixtures/forgeops-run-manifest/suite.json`
  - Adds exact negative case envelopes for duplicate and dangling references, cross-run resolution, producer range, both freshness wrong modes, invalid UTC, raw secret content, absolute/traversal refs, and signed URLs.
  - Adds missing self-hash, missing content hash, and malformed content hash lifecycle/schema cases.
- `tests/interface_contract/test_run_manifest.py`
  - Adds focused semantic resolver, freshness, source grammar, sensitive boundary, same-run context, and zero-storage assertions.
  - Verifies inclusive producer bounds across artifacts, evidence, and decisions.
  - Verifies all positive and negative fixture cases without storage effects.

## TDD evidence

### RED

Command:

`python -m unittest tests.interface_contract.test_run_manifest.ManifestReferenceTests -v`

Observed result: exit code 1; seven focused tests failed because `StorageSpy`, `validate_catalogs_and_references`, `validate_manifest_case`, and `validate_source_ref` did not exist.

### GREEN and refinement

After the minimal resolver implementation, the focused run exposed one expected ordering defect: duplicate terminal decision IDs returned `MANIFEST_IDENTITY_MISMATCH`. Catalog identity resolution was moved immediately after schema validation so the stable duplicate category wins. The next focused run passed all seven initial tests.

The completed fixture and boundary catalog then passed nine focused reference tests and 22 total W3-4 tests.

Final boundary review reproduced a protected-source gap: `.env`, `config/credentials.json`, and `secrets/token.txt` were syntactically canonical and therefore accepted. Four regression subtests first failed consistently; segment-level protected-resource detection was then added, and the focused test passed before the full verification run.

## Fresh verification evidence

- `python -m unittest tests.interface_contract.test_run_manifest -v`
  - Exit code 0; 22 tests passed.
- `python -m unittest discover -s tests/interface_contract -p "test_*.py" -v`
  - Exit code 0; 65 tests passed.
- JSON parsing for `contracts/forgeops-run-manifest/1.0/schema.json` and `fixtures/forgeops-run-manifest/suite.json`
  - Exit code 0; `JSON_OK`.
- `python -m py_compile tools/interface_contract/manifest_contract.py tests/interface_contract/test_run_manifest.py`
  - Exit code 0.
- `git diff --check`
  - Exit code 0.
- `git status --short docs/project/wbs.md docs/project/requirements-traceability-matrix.md`
  - Exit code 0 with no output; planning status and traceability files remain unchanged.

## Deferred scope

VG-004 unified runner/result generation, project validation-command registration, integrated evidence, and WBS/RTM status changes remain W3-5 work and are not claimed here.

## Independent review — 2026-07-24

**Verdict: CHANGES_REQUESTED**

The catalog resolver, reference guards, producer sequence bounds, freshness
union, path/URL rejection, and in-memory storage boundary are otherwise
consistent with W3-4 Task 2. This review was static and read-only; it did not
rerun the broad interface-contract suite.

### Findings

1. **Medium — `MANIFEST_MODE_INVALID` is declared but unreachable.**
   The approved interface declares this as a stable manifest category, but the
   validator has no branch that emits it. `run_mode` is rejected only by the
   generic JSON Schema enum, which becomes `MANIFEST_SCHEMA_INVALID`.

   - Contract declaration: `docs/superpowers/plans/2026-07-23-w3-run-manifest-reference.md:44`
   - Declared-but-unused category: `tools/interface_contract/manifest_contract.py:17-29`
   - Generic schema-only run-mode enforcement:
     `contracts/forgeops-run-manifest/1.0/schema.json:34-37` and
     `tools/interface_contract/manifest_contract.py:303-331`

   Add a semantic run-mode precheck that emits `MANIFEST_MODE_INVALID`, plus a
   rehashed negative fixture and assertion. Keep the schema enum as the closed
   shape guard.

2. **Medium — the ForgeOps URN grammar accepts credential and tenant kinds.**
   `FORGEOPS_SOURCE_REF` accepts every lower-case kind, including values such
   as `forgeops:token:opaque-id`, `forgeops:credential:opaque-id`, and
   `forgeops:tenant:opaque-id`. This bypasses the sensitive-key/path checks,
   despite the approved boundary forbidding credential and tenant identifiers.

   - Broad kind grammar: `tools/interface_contract/manifest_contract.py:36-38`
   - Early accept before sensitive path checks:
     `tools/interface_contract/manifest_contract.py:155-160`
   - Existing protected-key policy and tests only cover field names:
     `tools/interface_contract/manifest_contract.py:123-152` and
     `tests/interface_contract/test_run_manifest.py:435-460`
   - Approved prohibition: `docs/superpowers/specs/2026-07-23-w3-run-manifest-reference-design.md:57-64`

   Replace the free-form URN kind expression with an explicit approved kind
   set, or at minimum reject reserved sensitive kinds before returning from
   `validate_source_ref`. Add negative cases for `token`, `credential`, and
   `tenant` URNs expecting `MANIFEST_SENSITIVE_CONTENT_FORBIDDEN`.

### Confirmed coverage

- Artifact, evidence, decision, and per-decision reference duplicates map to
  `MANIFEST_ID_DUPLICATE` through
  `tools/interface_contract/manifest_contract.py:224-260`.
- Dangling artifact/evidence references map to
  `MANIFEST_REFERENCE_DANGLING` at lines 256-259; the fixture catalog covers
  the negative case at `fixtures/forgeops-run-manifest/suite.json:465-470`.
- Case-local artifact/evidence resolution requires the exact manifest
  task/run identity and complete catalog mapping at lines 264-277, with
  cross-run coverage at `tests/interface_contract/test_run_manifest.py:462-488`.
- Producer sequence validation is inclusive at lines 231-244 and is covered
  at `tests/interface_contract/test_run_manifest.py:352-382`.
- The revision/time evidence union rejects wrong-mode fields and invalid UTC
  values before generic schema rejection at lines 199-221, with tests at
  `tests/interface_contract/test_run_manifest.py:384-400`.
- Relative source references reject absolute/drive/UNC/traversal/backslash/
  wildcard/query/fragment forms at lines 155-177; sensitive path segments are
  denied at lines 180-196.
- `validate_manifest_case` has no storage call and rejects before any optional
  spy observation; zero-call checks cover invalid and valid fixtures at
  `tools/interface_contract/manifest_contract.py:280-300` and
  `tests/interface_contract/test_run_manifest.py:490-556`.
- Task 2 does not alter canonical-byte, lifecycle, range-count, or hash
  routines (`tools/interface_contract/manifest_contract.py:68-120` and
  303-331), and it introduces no runtime/network/storage implementation.

## Review remediation — 2026-07-24

Both requested changes were reproduced and corrected with focused RED/GREEN cycles.

### Stable run-mode category

- Added a semantic precheck for every supplied `run_mode` value before JSON Schema validation.
- Unknown strings and invalid JSON types now return `MANIFEST_MODE_INVALID`, including when another schema violation is present.
- Added an exact `invalid-run-mode` negative case whose `manifest_sha256` is the calculated canonical self-hash.
- The regression test verifies string, integer, null, and array values and confirms `StorageSpy.calls == 0`.

Initial focused result: four failures returned `MANIFEST_SCHEMA_INVALID`. After the minimal precheck, all four variants returned `MANIFEST_MODE_INVALID` and the focused test passed.

### Closed ForgeOps URN kinds

- Replaced the free-form early acceptance with an explicit `FORGEOPS_SOURCE_KINDS` allowlist of non-sensitive project-owned kinds.
- `forgeops:token:*`, `forgeops:credential:*`, `forgeops:tenant:*`, and `forgeops:secret:*` now return `MANIFEST_SENSITIVE_CONTENT_FORBIDDEN`.
- Added four exact negative fixture cases and direct grammar assertions while retaining positive `evidence`, `command`, `test`, and `runtime` URNs.
- Every new negative fixture confirms zero storage calls.

Initial focused result: the four sensitive URNs were accepted directly and fixture execution reached `MANIFEST_HASH_INVALID`. After the allowlist guard, direct and fixture tests returned `MANIFEST_SENSITIVE_CONTENT_FORBIDDEN`.

### Fresh post-remediation evidence

- `python -m unittest tests.interface_contract.test_run_manifest -v`
  - Exit code 0; 23 tests passed.
- `python -m unittest discover -s tests/interface_contract -p "test_*.py" -v`
  - Exit code 0; 66 tests passed.
- Manifest schema and fixture JSON parse
  - Exit code 0; `JSON_OK`.
- Python compilation, `git diff --check`, and WBS/RTM status inspection
  - Exit code 0; no compile or whitespace errors and no WBS/RTM changes.

## Independent re-review — 2026-07-24

**Verdict: APPROVED.** The two prior findings are corrected without expanding
Task 2 into a runtime, network, persistence, WBS, or RTM change.

- `RUN_MODES` is closed at
  `tools/interface_contract/manifest_contract.py:31-36`, and the supplied
  `run_mode` semantic precheck at lines 328-339 now emits
  `MANIFEST_MODE_INVALID` before JSON Schema evaluation at lines 340-347.
  The regression covers a bad string, integer, null, and array in the presence
  of an additional schema defect, while asserting zero `StorageSpy` calls at
  `tests/interface_contract/test_run_manifest.py:441-470`.
- ForgeOps URNs now require both the closed grammar (lines 37-40) and the
  explicit non-sensitive kind allowlist (lines 41-60). Unknown or sensitive
  kinds fail with `MANIFEST_SENSITIVE_CONTENT_FORBIDDEN` before any
  root-relative fallback at lines 177-202. Direct tests reject `token`,
  `credential`, `tenant`, and `secret` at
  `tests/interface_contract/test_run_manifest.py:413-439`; the fixture catalog
  supplies matching zero-storage cases at
  `fixtures/forgeops-run-manifest/suite.json:553-582`.
- Canonical serialization, lifecycle, inclusive range, and self-hash logic
  remain unchanged in their prior routines (lines 90-143 and 349-358). No
  storage spy invocation, runtime service, network call, or external effect is
  introduced by the remediation.
