# W9 Phase 1 Safety Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to execute this plan task by task. Use
> `superpowers:test-driven-development` for every behavior change and
> `superpowers:verification-before-completion` before every completion claim.

**Goal:** Complete WBS-026~WBS-028 with a source-bound security-negative run,
fresh VG-008~VG-015/VG-023 evidence at the required E2/E3 floors, and a
public-safe Phase 1 safety scorecard without declaring Phase 1 Exit.

**Architecture:** A standard-library Python aggregator owns a closed
23-command registry, exact WBS subsets, source/tier/freshness/effect reduction,
and deterministic JSON/Markdown/HTML outputs. The existing isolated Linux
two-job workflow remains the E3 boundary and emits a versioned W9 allowlisted
artifact after the implementation reaches protected `main`.

**Tech stack:** Python 3, `unittest`, `jsonschema`, Git blob identities, GitHub
Actions on Ubuntu 24.04, rootless Docker, Cosign, closed JSON artifacts.

**Base:** `origin/main` at `4c09269`

**Design:**
`docs/superpowers/specs/2026-08-24-w9-phase1-safety-gate-design.md`

**Known baseline:** On Windows with `core.autocrlf=true`, the pre-W9 full suite
runs 516 tests with four subcase failures in
`tests.lifecycle_trace.test_contracts.LifecycleTraceContractTests.test_committed_evidence_is_current_public_safe_and_documented`.
The repository blobs are LF while the W8 source inputs are checked out as CRLF,
so the test compares checkout-transformed hashes with Linux-generated committed
hashes. Task 1 adds an explicit LF checkout rule and repository-blob resolver;
do not misreport these baseline failures as a W9 regression or suppress them.

**Execution authority bundle:** Before implementation starts, request one
batched approval covering local source/test/document edits, task commits, branch
push and implementation PR, protected-main workflow dispatch and its GHCR/artifact
writes, evidence download/import, closure commit, branch push, and closure PR.
The plan itself grants none of those external actions.

---

## Task 1: Closed contract, registry, and immutable source identity

**Files**

- Create `contracts/forgeops-phase1-safety/1.0/schema.json`
- Create `fixtures/forgeops-phase1-safety/suite.json`
- Create `tools/phase1_safety/__init__.py`
- Create `tools/phase1_safety/model.py`
- Create `tools/phase1_safety/registry.py`
- Create `tests/phase1_safety/__init__.py`
- Create `tests/phase1_safety/test_contracts.py`
- Create `tests/phase1_safety/test_registry.py`
- Modify `.gitattributes`
- Modify `tests/lifecycle_trace/test_contracts.py`
- Modify `AGENTS.md`
- Modify `docs/project/wbs.md`

**Public interfaces**

```python
class SafetyError(RuntimeError):
    code: str

@dataclass(frozen=True)
class Registration:
    gate_id: str
    profile_id: str
    command_id: str
    artifact_ref: str
    required_tier: str
    input_refs: tuple[str, ...]
    hash_fields: tuple[str, ...]
    observed_at_field: str

def load_registry(suite: Mapping[str, object]) -> tuple[Registration, ...]: ...
def resolve_committed_sha256(root: Path, ref: str) -> str: ...
def validate_source_identity(identity: Mapping[str, object]) -> SourceIdentity: ...
```

**RED**

- [ ] Add a schema test that requires Draft 2020-12 validity and recursively
      closed contract, suite, reducer-result, gate-result, source-identity,
      effect-counter, gate-row, blocker, and artifact-manifest objects.
- [ ] Assert the exact ordered 23-command union from VG-005~VG-015 and VG-023,
      including gate/profile/command/result path, minimum tier, input refs, and
      timestamp field for every registration.
- [ ] Assert the exact WBS-026 20-command and WBS-027/WBS-028 19-command subsets;
      reject duplicates, omissions, additions, reordering, and wrong membership.
- [ ] Reject absolute, parent-relative, backslash, wildcard, symlink, missing,
      secret-like, and unregistered source or artifact references.
- [ ] Add Git blob tests showing that an LF repository blob and a CRLF working
      copy resolve to the same committed source hash, while a dirty content
      mismatch, missing Git metadata, non-blob object, or unknown ref fails
      closed without exposing file content.
- [ ] Update the W8 committed-evidence test to compare its source inputs to the
      committed blob identity rather than checkout-transformed bytes. Keep
      `tests.lifecycle_trace.test_verify` asserting that newly generated result
      files describe the exact bytes the verifier executed.
- [ ] Assert `AGENTS.md` registers exactly one ordered
      `forgeops-phase1-safety` profile with `phase1-security-negative`,
      `phase1-evidence-freshness`, and `phase1-safety-gate`, all required E3.
- [ ] Assert WBS-026~WBS-028 remain non-complete and explicitly describe the
      two-stage merge/E3/import boundary during Stage A.
- [ ] Run the new contract and registry tests and confirm they fail for missing
      files/interfaces before adding production code.

**GREEN**

- [ ] Add the closed schema and suite with the exact 23 entries and named
      `security_negative` (20) and `required_evidence` (19) subsets.
- [ ] Implement strict model loading, canonical JSON, UTC parsing, SHA-256,
      stable public errors, and same-directory atomic replacement.
- [ ] Implement registry validation as exact equality against trusted constants;
      never discover identities from artifacts, globs, or directory contents.
- [ ] Resolve source hashes from committed Git blob bytes with `shell=False`, a
      fixed argv, bounded output, stable errors, and no subprocess output in
      public results. Permit an injected resolver only for deterministic tests.
- [ ] Add LF rules for existing W8 lifecycle inputs and all new W9 contract,
      fixture, package, test, and generated public artifact paths. Normalize the
      isolated working copy, then prove both fresh checkout and CRLF simulation.
- [ ] Register the three fixed command lines and outputs in `AGENTS.md`; add the
      ordered profile below the Phase 1 verification profiles.
- [ ] Use these exact registered CLIs; the verifier rejects any path or command
      substitution:

```text
python tools/phase1_safety/verify.py --schema contracts/forgeops-phase1-safety/1.0/schema.json --suite fixtures/forgeops-phase1-safety/suite.json --result artifacts/verification/phase-1-security-negative-result.json --command-id phase1-security-negative
python tools/phase1_safety/verify.py --schema contracts/forgeops-phase1-safety/1.0/schema.json --suite fixtures/forgeops-phase1-safety/suite.json --result artifacts/verification/phase-1-evidence-freshness-result.json --command-id phase1-evidence-freshness
python tools/phase1_safety/verify.py --schema contracts/forgeops-phase1-safety/1.0/schema.json --suite fixtures/forgeops-phase1-safety/suite.json --result artifacts/verification/phase-1-safety-gate-result.json --report-md artifacts/reviews/phase-1-safety-scorecard.md --report-html artifacts/reviews/phase-1-safety-scorecard.html --command-id phase1-safety-gate
```

- [ ] Run:

```powershell
python -m unittest tests.phase1_safety.test_contracts tests.phase1_safety.test_registry tests.lifecycle_trace.test_contracts -v
python -m unittest tests.lifecycle_trace.test_verify -v
python -m json.tool contracts/forgeops-phase1-safety/1.0/schema.json *> $null
python -m json.tool fixtures/forgeops-phase1-safety/suite.json *> $null
git diff --check
```

- [ ] Inspect only the listed paths, stage them explicitly, and commit:

```text
feat: define W9 phase 1 safety registry
```

---

## Task 2: WBS-026 security-negative reducer

**Files**

- Create `tools/phase1_safety/audit.py`
- Create `tools/phase1_safety/verify.py`
- Create `tests/phase1_safety/test_security_negative.py`
- Modify `tools/phase1_safety/__init__.py`
- Modify `contracts/forgeops-phase1-safety/1.0/schema.json`
- Modify `fixtures/forgeops-phase1-safety/suite.json`

**Public interfaces**

```python
@dataclass(frozen=True)
class EffectCounters:
    unauthorized_executions: int
    approval_bypasses: int
    containment_or_egress_escapes: int
    injection_acceptances: int
    raw_secret_occurrences: int
    cleanup_failures: int
    evidence_integrity_failures: int
    external_writes: int

def audit_registration(
    root: Path,
    registration: Registration,
    *,
    validated_at: datetime,
    source_identity: SourceIdentity,
) -> GateAudit: ...

def reduce_security_negative(
    root: Path,
    *,
    validated_at: datetime,
    source_identity: SourceIdentity,
) -> dict[str, object]: ...
```

**RED**

- [ ] Build one positive fixture for all exact 20 WBS-026 registrations and
      prove the reducer reports 20/20 `PASSED`, blockers 0, and eight zero
      counters without copying source case arrays.
- [ ] For every adapter shape, test missing/malformed JSON, unknown keys, wrong
      gate/profile/command/artifact identity, invalid summary totals, failed or
      `NOT_RUN` status, insufficient tier, source hash mismatch, stale/future
      timestamp, and duplicate artifact consumption.
- [ ] Test each nonzero normalized counter independently and prove the reducer
      returns `FAILED` with `NEGATIVE_EFFECT_OBSERVED`.
- [ ] Test `null`, absent, string, boolean, negative, and overflow counter values.
      An unobserved required boundary must become `OBSERVATION_UNAVAILABLE`, not
      an assumed zero; a registered E3 owner may satisfy only its declared field.
- [ ] Test a raw-secret marker in keys and values, nested source cases, command
      output, absolute host paths, URLs, environment names, and active content.
      The public reducer result must retain only fixed IDs, totals, flags, and
      stable codes.
- [ ] Test atomic write rollback and prove a failed run removes or replaces no
      previously valid result with a partial document.
- [ ] Run `python -m unittest tests.phase1_safety.test_security_negative -v` and
      confirm missing reducer/verifier failures.

**GREEN**

- [ ] Implement strict adapter functions for the registered VG-005~VG-009,
      VG-011, VG-013~VG-015, and VG-023 result shapes. Reject any unrecognized
      shape before status or counters are trusted.
- [ ] Deep-copy parsed values, validate closed hash layouts, compare all trusted
      identities, verify source-current inputs, and enforce each tier/freshness
      floor before normalization.
- [ ] Normalize only explicitly mapped observations into the eight counters.
      Never infer zero from a missing key, successful process exit, or a summary
      count alone.
- [ ] Implement `phase1-security-negative` CLI identity validation with fixed
      schema, suite, result, command ID, and source-identity inputs. Unknown or
      substituted CLI paths fail before artifact reads.
- [ ] Emit a closed public result at
      `artifacts/verification/phase-1-security-negative-result.json` with no raw
      cases, source payload, logs, exception text, or absolute paths.
- [ ] Run:

```powershell
python -m unittest tests.phase1_safety.test_contracts tests.phase1_safety.test_registry tests.phase1_safety.test_security_negative -v
python -m compileall -q tools/phase1_safety tests/phase1_safety
git diff --check
```

- [ ] Review the normalized field map against all 20 registrations, stage only
      Task 2 paths, and commit:

```text
feat: add W9 security negative reducer
```

---

## Task 3: WBS-027 freshness, attested E3 intake, and two-job workflow

**Files**

- Create `tests/phase1_safety/test_freshness.py`
- Modify `tools/phase1_safety/audit.py`
- Modify `tools/phase1_safety/verify.py`
- Modify `tools/sandbox_security/e3_artifact.py`
- Modify `.github/workflows/vg-008-e3.yml`
- Modify `tests/sandbox_security/test_e3_workflow.py`
- Modify `tests/sandbox_security/test_verify.py`
- Modify `contracts/forgeops-phase1-safety/1.0/schema.json`
- Modify `fixtures/forgeops-phase1-safety/suite.json`

**Public interfaces**

```python
def reduce_required_evidence(
    root: Path,
    *,
    validated_at: datetime,
    source_identity: SourceIdentity,
    e3_receipt_ref: str,
) -> dict[str, object]: ...

PHASE1_PAYLOAD_VERSION = "phase1-safety-1.0"
PHASE1_PAYLOAD_FILES: tuple[str, ...]

def build_phase1_manifest(root: Path, output: Path) -> dict[str, object]: ...
def verify_downloaded_phase1_artifact(
    source: Path,
    expected_identity: ExpectedIdentity,
    *,
    validation_at: datetime,
) -> dict[str, object]: ...

def verify_downloaded_phase1_artifact_from_facts(
    source: Path,
    expected_repository: str,
    expected_repository_id: str,
    expected_default_branch: str,
    expected_run_id: str,
    expected_run_attempt: int,
    expected_source_sha: str,
    *,
    validation_at: datetime,
) -> dict[str, object]: ...
```

The fixed download/import CLI accepts only independently observed GitHub API
facts. Image reference and digest are read from the already snapshotted receipt
inside the verifier and must then pass the signed identity checks; callers do
not inspect unverified artifact content to construct trusted input.

**RED**

- [ ] Test the exact 19-command required-evidence subset: five E3 results from
      VG-008/VG-009 and fourteen E2 results from VG-010~VG-015/VG-023.
- [ ] Prove that all 19 observations must fall within 0~300 seconds of one
      validation time and bind one exact repository/default-branch/source SHA,
      workflow ref/SHA, run ID, and run attempt.
- [ ] Reject a local/injected E3 runner, `verification_kind=test`, unsigned or
      changed bundle, issuer/certificate near miss, tag or unprotected ref,
      source/workflow SHA mismatch, digest mismatch, replayed run, stale or future
      receipt, receipt/output hash mismatch, and mixed-run evidence.
- [ ] Test a closed W9 artifact manifest with the exact runtime files, exact 23
      registered source results, three W9 outputs, and two scorecards. Reject a
      missing/extra/duplicate/symlink/absolute/secret-like/oversized file and a
      manifest that hashes itself.
- [ ] Preserve the historical Phase 0 manifest/import behavior byte-for-byte;
      W9 payload selection must be explicit and versioned rather than widening
      the existing allowlist.
- [ ] Assert workflow dispatch only, top-level `permissions: {}`, protected
      default-branch checks, `cancel-in-progress: false`, exactly two jobs,
      pinned actions, least job permissions, bounded timeouts, and no third job.
- [ ] Assert verifier-job ordering: signed source checkout, Cosign verification,
      rootless setup, E3 collection/import, exact 23 registered commands,
      WBS-026 reducer, WBS-027 reducer, WBS-028 gate, manifest construction,
      exact staging, then upload.
- [ ] Assert workflow failure prevents successful manifest construction/upload;
      no `continue-on-error`, wildcard upload, raw log upload, pull-request run,
      mutable action tag, or credential persistence is allowed.
- [ ] Run focused tests and confirm the missing freshness and payload behavior.

**GREEN**

- [ ] Implement 19-result freshness reduction and exact E3 receipt/attestation
      validation using the already hardened sandbox consumer. Do not duplicate
      or weaken Cosign identity checks.
- [ ] Add an explicit W9 payload version and exact allowlist to
      `e3_artifact.py`; keep the Phase 0 constants and CLI behavior compatible.
- [ ] Add atomic W9 verify/import paths that validate GitHub API-supplied facts
      before replacing any repository artifact. Stale evidence may be reported
      as historical but may not be imported as current.
- [ ] Extend only the existing verifier job to execute the twelve new VG-010~
      VG-015 commands after the eleven already present W9-union commands. Assert
      the final run contains each union command exactly once.
- [ ] Run the three W9 commands in dependency order, stage the exact versioned
      W9 payload, and upload as
      `forgeops-phase1-evidence-${run_id}-${run_attempt}` for seven days.
- [ ] Keep the producer/verifier split, pinned Ubuntu 24.04, rootless Docker,
      digest-pinned image, Cosign, current concurrency, and least privileges.
- [ ] Run:

```powershell
python -m unittest tests.phase1_safety.test_freshness tests.sandbox_security.test_e3_workflow -v
python -m unittest tests.sandbox_security.test_e3_attestation tests.sandbox_security.test_verify -v
python -m compileall -q tools/phase1_safety tools/sandbox_security tests/phase1_safety tests/sandbox_security
git diff --check
```

- [ ] Inspect the workflow diff for exact permissions, pins, shell safety, step
      order, and allowlist; stage only Task 3 paths and commit:

```text
feat: add W9 attested evidence run
```

---

## Task 4: WBS-028 safety decision and public scorecard

**Files**

- Create `tools/phase1_safety/scorecard.py`
- Create `tests/phase1_safety/test_gate.py`
- Create `tests/phase1_safety/test_scorecard.py`
- Modify `tools/phase1_safety/audit.py`
- Modify `tools/phase1_safety/verify.py`
- Modify `tools/phase1_safety/__init__.py`
- Modify `contracts/forgeops-phase1-safety/1.0/schema.json`
- Modify `fixtures/forgeops-phase1-safety/suite.json`

**Public interfaces**

```python
def decide_phase1_safety(
    root: Path,
    *,
    validated_at: datetime,
    source_identity: SourceIdentity,
) -> dict[str, object]: ...

def render_scorecard_markdown(decision: Mapping[str, object]) -> str: ...
def render_scorecard_html(decision: Mapping[str, object]) -> str: ...
```

**RED**

- [ ] Build a valid 19/19 fixture and assert exact `READY`, E3, blockers 0,
      immutable source, five verified E3 inputs, fourteen E2-or-higher inputs,
      and all normalized counters zero.
- [ ] Parameterize every command as missing, failed, `NOT_RUN`, stale, future,
      insufficient tier, source-mixed, identity-mismatched, input-hash-invalid,
      malformed, or non-public-safe; each must yield `NOT_READY` with a stable
      blocker tied only to the registered row.
- [ ] Set each required effect counter nonzero and each required observation
      unavailable in turn. Prove one violation blocks the gate and W10 handoff.
- [ ] Tamper with either reducer summary after its source results are created.
      The final gate must re-audit source artifacts and reject summary-only trust.
- [ ] Assert exactly 19 ordered gate rows, deterministic blocker order, stable
      canonical JSON, no duplicate blocker, and identical output across mapping
      insertion order, locale, and timezone changes.
- [ ] Assert Markdown and HTML contain only fixed IDs, status, tier, public
      timestamps, counts, stable codes, and repository-relative artifact refs.
      Reject `<script`, `<form`, event handlers, remote/file URLs, raw fixture
      values, environment data, absolute paths, and secret-like keys.
- [ ] Inject report-write failure between JSON/Markdown/HTML replacements and
      prove no mixed-generation output set remains.
- [ ] Run gate/scorecard tests and confirm missing implementation failures.

**GREEN**

- [ ] Implement one-shot snapshot reads for all registered artifacts and both
      reducer results, then revalidate exact identities, byte hashes, source,
      tier, freshness, public safety, and effects before deciding.
- [ ] Emit `READY` only for 19/19 with zero blockers and counters. All exceptions
      map to `NOT_READY`; never leave an earlier `READY` artifact after failure.
- [ ] Render deterministic Markdown and static HTML from the final JSON decision;
      use escaping and fixed templates with no active or remote content.
- [ ] Atomically publish the JSON/Markdown/HTML generation set to:

```text
artifacts/verification/phase-1-safety-gate-result.json
artifacts/reviews/phase-1-safety-scorecard.md
artifacts/reviews/phase-1-safety-scorecard.html
```

- [ ] Run:

```powershell
python -m unittest tests.phase1_safety.test_gate tests.phase1_safety.test_scorecard -v
python -m unittest discover -s tests/phase1_safety -p "test_*.py" -v
python -m compileall -q tools/phase1_safety tests/phase1_safety
git diff --check
```

- [ ] Inspect a rendered fixture with a text search and browser only if visual
      layout requires it; browser inspection cannot substitute for content and
      active-surface tests. Stage only Task 4 paths and commit:

```text
feat: add W9 phase 1 safety gate
```

---

## Task 5: Two-stage verification, evidence import, and W9 closure

**Files — Stage A implementation closure**

- Modify `docs/project/wbs.md`
- Modify `docs/project/requirements-traceability-matrix.md`
- Modify `docs/quality/verification-and-evaluation-plan.md`
- Modify `docs/architecture/system-architecture.md`
- Modify `docs/security/threat-model.md`
- Modify `README.md` only if its current verification instructions need the W9
  command or completion boundary
- Modify tests under `tests/phase1_safety/` only for documentation assertions

**Files — Stage B evidence closure**

- Regenerate/import `artifacts/runtime/e3-attestation.json`
- Regenerate/import `artifacts/runtime/e3-attestation.bundle.json`
- Regenerate/import `artifacts/runtime/sandbox-runtime-profile.json`
- Regenerate/import `artifacts/runtime/sandbox-runtime-observations.json`
- Regenerate/import `artifacts/runtime/sandbox-e3-import-receipt.json`
- Regenerate/import all exact 23 registered VG result artifacts
- Create/import `artifacts/verification/phase-1-security-negative-result.json`
- Create/import `artifacts/verification/phase-1-evidence-freshness-result.json`
- Create/import `artifacts/verification/phase-1-safety-gate-result.json`
- Create/import `artifacts/reviews/phase-1-safety-scorecard.md`
- Create/import `artifacts/reviews/phase-1-safety-scorecard.html`
- Create/import the versioned W9 public artifact manifest
- Modify the five Stage A traceability/security/architecture documents with the
  immutable run and acceptance facts

**Stage A — RED/GREEN and implementation PR**

- [ ] Add documentation tests asserting W9 remains incomplete until a current
      imported `READY` result binds the exact protected-main merge SHA.
- [ ] Document the exact 23/20/19 cardinalities, E2/E3 split, zero-effect rules,
      two-job boundary, Stage B requirement, and W10/VG-024 exclusions.
- [ ] Run every registered non-E3 verifier in a bounded batch, then all focused
      W9, sandbox-security, lifecycle, patch, vertical, context, and snapshot
      tests. These are diagnostics only; do not commit a locally synthesized E3
      result or mark W9 complete.
- [ ] Run the full suite and review every failure against the recorded baseline:

```powershell
python -m unittest discover -s tests -p "test_*.py"
python -m compileall -q tools tests
git diff --check
git status --short
```

- [ ] Require zero unexplained failure. Specifically confirm the Task 1 source
      identity change removes the four Windows CRLF baseline subcase failures
      while keeping raw-byte verifier tests intact.
- [ ] Review the entire implementation diff, public artifact surface, workflow,
      and threat/traceability mappings. Commit the Stage A documentation:

```text
docs: prepare W9 safety evidence closure
```

- [ ] After the batched external-action approval is active, push the feature
      branch and open an implementation PR to `main`. Record the PR URL, obtain
      review, wait for required checks, and merge without force-push or bypass.
- [ ] Resolve the exact merge SHA from protected `main`; do not use the feature
      tip or a locally predicted merge SHA as Stage B identity.

**Stage B — protected-main E3 and evidence-only PR**

- [ ] Dispatch `VG-008 E3 Verification` on the protected default branch at the
      exact merge SHA. Record repository ID, run ID, run attempt, source SHA,
      workflow SHA/ref, image digest/ref, artifact name/ID, and timestamps.
- [ ] Require both jobs to succeed. Require exactly one W9 artifact named
      `forgeops-phase1-evidence-${run_id}-${run_attempt}` and reject a rerun or
      artifact whose recorded attempt does not match the GitHub API response.
- [ ] Download to a newly created temporary directory and invoke the fixed W9
      verify-download command with GitHub API facts. Do not inspect or copy files
      before manifest, signature, receipt, path, byte-hash, size, freshness, and
      source identity validation succeeds.
- [ ] Create a new evidence-closure branch from the exact merge SHA. Import only
      the versioned allowlist atomically; inspect `git status`, public secret
      scan, artifact totals, and the JSON/Markdown/HTML decision.
- [ ] Require:

```text
union registry: 23/23 PASSED
WBS-026 security-negative subset: 20/20 PASSED
WBS-027 required-evidence subset: 19/19 PASSED
WBS-028 safety gate: READY at E3
blockers: 0
unauthorized executions: 0
cleanup failures: 0
external writes: 0
raw secret occurrences: 0
source SHA: exact implementation merge SHA
workflow SHA: exact implementation merge SHA
```

- [ ] Update WBS-026~WBS-028 to `WBS_DONE` only now. Add one acceptance note
      with immutable run/artifact references and explicitly retain WBS-029~
      WBS-032, VG-024, public-safe package, local vertical demonstration, and
      Phase 1 Exit as incomplete.
- [ ] Update RTM, verification plan, architecture, and threat model with the same
      source-bound facts and residual risks. No document may claim deployment,
      publication, product runtime, or Phase 1 Exit.
- [ ] Run the imported gate command, focused evidence/contract tests, public
      secret scan, full repository suite, compile, JSON parse, and diff checks on
      the evidence branch. Any stale result requires a new workflow run rather
      than a relaxed clock or edited timestamp.
- [ ] Inspect exact staged files and commit:

```text
evidence: close W9 phase 1 safety gate
```

- [ ] Push the evidence branch, open a separate evidence-only PR to `main`,
      obtain independent review, wait for required checks, and merge. Report W9
      complete only after the closure PR is merged and protected `main` contains
      the verified artifacts and `WBS_DONE` records.

## Final completion checklist

- [ ] The implementation and evidence closure are two separate reviewed PRs.
- [ ] The authoritative run is the existing two-job protected-main Linux path.
- [ ] The 23-command registry and 20/19 subsets are exact and closed.
- [ ] All results are fresh, source-current, public-safe, and at their required
      E2/E3 floors.
- [ ] The Phase 1 safety gate is `READY` with all required zero-effect counters.
- [ ] WBS-026~WBS-028 alone are `WBS_DONE`; W10 and VG-024 remain incomplete.
- [ ] No force push, branch-protection bypass, credential exposure, publication,
      deployment, or unapproved external side effect occurred.
