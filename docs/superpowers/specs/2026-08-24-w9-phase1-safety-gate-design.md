# W9 Phase 1 Safety Gate Design

**Date:** 2026-08-24
**Status:** Approved for implementation planning
**Base:** `origin/main` (`4c09269`)
**Scope:** WBS-026~WBS-028; VG-005~VG-015 and VG-023 aggregation

## 1. Goal and completion boundary

W9 turns the already implemented Phase 1 safety checks into one fail-closed,
source-bound decision. It runs the security-negative subset, refreshes every
required Phase 1 criterion at its declared evidence floor, and produces a
public-safe scorecard for the Phase 1 safety gate.

W9 is complete only after both stages below succeed:

1. the implementation PR is merged into the protected default branch; and
2. the existing isolated Linux two-job workflow runs against that exact merge
   commit, its signed evidence is verified and imported by a follow-up evidence
   PR, and the imported gate result is `READY`.

The implementation branch may prove deterministic E2 behavior, schema closure,
workflow shape, and negative paths. It may not claim fresh E3 evidence or mark
WBS-026~WBS-028 complete before the protected-main run is imported.

W9 does not implement WBS-029~WBS-032, VG-024, the Phase 1 Exit decision,
deployment, publication, or product runtime orchestration.

## 2. Chosen architecture

Add a W9-specific Phase 1 safety aggregator and extend the existing
`.github/workflows/vg-008-e3.yml` without adding a third job. The producer job
continues to build and sign the fixed probe image. The independent verifier job
continues to verify that image and collect VG-008/VG-009 E3 observations, then
runs all W9 registered commands, reduces the results, builds the scorecard, and
uploads a closed public artifact.

This is preferred over generalizing the Phase 0 exit verifier because Phase 0
has a different registry, completion meaning, and artifact contract. It is also
preferred over a CI-only script because the registry, reduction rules, and
decision must be unit-testable and reproducible without trusting workflow YAML
as executable policy.

New package:

```text
tools/phase1_safety/
  __init__.py   public identifiers
  model.py      closed errors, canonical JSON, UTC, atomic writes
  registry.py   exact command registry, subsets, and artifact adapters
  audit.py      source/freshness/tier/effect validation and reduction
  scorecard.py  deterministic public Markdown and static HTML
  verify.py     three registered W9 command entry points
```

Contract and fixture:

```text
contracts/forgeops-phase1-safety/1.0/schema.json
fixtures/forgeops-phase1-safety/suite.json
```

## 3. Five implementation tasks

1. Define the closed W9 contract, exact 23-command registry, three W9 command
   identities, immutable-source rules, and cross-platform source resolution.
2. Implement the WBS-026 security-negative reducer over its exact 20-command
   subset and prove all zero-event conditions fail closed.
3. Implement WBS-027 evidence freshness and E3 intake, then extend the existing
   protected-main two-job workflow to produce one signed W9 evidence package.
4. Implement the WBS-028 Phase 1 safety decision and deterministic Markdown/HTML
   scorecard over the exact 19-command required-evidence subset.
5. Execute the two-stage closure: merge implementation, run protected-main E3,
   verify/import evidence, update traceability and WBS status, and merge the
   evidence-only closure PR.

Each implementation task uses test-first RED/GREEN development and an
independent commit. Task 5 has an explicit external-effect checkpoint before
push, PR creation, workflow dispatch, package write, or evidence import.

## 4. Closed command registry

The union registry contains exactly 23 ordered command identities. No command
may be inferred from filesystem discovery, a glob, a profile name, or an
artifact's self-reported identity.

| VG | Required tier | Registered commands |
| --- | --- | --- |
| VG-005 | E2 | `resource-authority-negative`, `protected-read-negative` |
| VG-006 | E2 | `command-network-negative` |
| VG-007 | E2 | `approval-negative-fixture` |
| VG-008 | E3 | `image-provenance-negative`, `containment-egress-negative`, `teardown-negative` |
| VG-009 | E3 | `secret-surface-negative`, `artifact-isolation-negative` |
| VG-010 | E2 | `snapshot-identity`, `baseline-retrieval-repeat` |
| VG-011 | E2 | `context-provenance`, `injection-negative` |
| VG-012 | E2 | `main-part-work-main` |
| VG-013 | E2 | `task-checks`, `regression-checks`, `verification-anti-tamper` |
| VG-014 | E2 | `budget-cancel-negative`, `no-progress-stop` |
| VG-015 | E2 | `trace-manifest-completeness`, `external-write-negative` |
| VG-023 | E2 | `evidence-positive-negative`, `extension-provenance` |

The registry entry for each command fixes:

- gate ID, profile ID, command ID, result artifact reference, and minimum tier;
- trusted input references and the result fields that bind those inputs;
- the timestamp field and maximum freshness age;
- the adapter-specific fields allowed in its public result; and
- which normalized effect counters it contributes.

Unknown, duplicate, missing, reordered, absolute, parent-relative, symlinked, or
unregistered references produce a stable failure before any source artifact is
accepted.

## 5. Exact WBS subsets

### 5.1 WBS-026 security-negative subset

WBS-026 covers VG-005~VG-009, VG-011, VG-013~VG-015, and VG-023. It therefore
contains exactly 20 commands: the 23-command union minus both VG-010 commands
and the single VG-012 command.

Every registered result must be `PASSED`, meet its required evidence tier, be
fresh and source-current, and normalize to all of the following:

```text
unauthorized_executions == 0
approval_bypasses == 0
containment_or_egress_escapes == 0
injection_acceptances == 0
raw_secret_occurrences == 0
cleanup_failures == 0
evidence_integrity_failures == 0
external_writes == 0
```

An adapter that cannot supply a required observation does not receive a zero by
default. It yields `OBSERVATION_UNAVAILABLE` unless that observation is owned by
a separately registered E3 result in the same source-bound package.

### 5.2 WBS-027 required-evidence subset

WBS-027 covers VG-008~VG-015 and VG-023, exactly 19 commands. It includes five
E3 commands from VG-008/VG-009 and fourteen E2 commands from VG-010~VG-015 and
VG-023. All 19 must be fresh in one workflow run and bound to one source SHA.

The broader 23-command union is retained so WBS-026 can also validate its four
Phase 0 policy commands from VG-005~VG-007. Those four are not silently promoted
into the WBS-027 or WBS-028 completion criterion.

### 5.3 WBS-028 safety-gate subset

WBS-028 uses the same exact 19-command subset as WBS-027. The gate is `READY`
only when the immutable-source, tier, freshness, completeness, public-safety,
and zero-effect assertions all pass. Otherwise it is `NOT_READY`; partial
success is never rounded up.

## 6. Registered W9 commands and outputs

Register one profile with three ordered commands:

```yaml
forgeops-phase1-safety:
  - phase1-security-negative
  - phase1-evidence-freshness
  - phase1-safety-gate
```

Fixed outputs:

```text
artifacts/verification/phase-1-security-negative-result.json
artifacts/verification/phase-1-evidence-freshness-result.json
artifacts/verification/phase-1-safety-gate-result.json
artifacts/reviews/phase-1-safety-scorecard.md
artifacts/reviews/phase-1-safety-scorecard.html
```

`phase1-security-negative` reduces the 20-command WBS-026 subset.
`phase1-evidence-freshness` reduces the 19-command WBS-027 subset.
`phase1-safety-gate` consumes both prior reducer results plus the same 19 source
artifacts and writes the WBS-028 decision and scorecard. It never trusts a
summary without revalidating its registered artifact identities and hashes.

The gate output carries E3 only when the five E3 inputs were verified by the
external attested path and all remaining inputs meet E2. A local fixture or
injected runner can never produce an E3 gate result.

## 7. Immutable source and checkout portability

The authority identity is the exact GitHub repository, protected default branch,
source commit SHA, workflow SHA, workflow ref, run ID, and run attempt carried by
the verified E3 receipt. The authoritative W9 workflow requires workflow SHA to
equal source SHA.

Repository input identities use committed Git blob bytes or an equivalent
explicit LF-canonical UTF-8 resolver. They do not hash checkout-transformed text
bytes as the source of truth. This avoids treating the same commit as different
when Windows `core.autocrlf=true` checks out CRLF while the repository stores LF.
The resolver is closed and injectable in tests; absence of Git metadata or a
blob mismatch fails with `SOURCE_IDENTITY_UNAVAILABLE` or
`SOURCE_HASH_MISMATCH`, never a platform-specific success.

Generated result artifacts remain hashed as their exact raw bytes. Only the
mapping from a registered source reference to its committed content uses the
blob resolver. The protected-main Linux run is the sole authoritative freshness
run, so its working tree and Git blob bytes are expected to agree.

## 8. Freshness and E3 intake

All current W9 evidence is generated in one protected-main workflow run. The
default freshness window is 300 seconds between each result's observation time
and the W9 validation time. A timestamp in the future, an over-age result, a
mixed source SHA, an earlier run artifact, or an artifact without an exact
registered input hash is `EVIDENCE_STALE` or `SOURCE_HASH_MISMATCH`.

The verifier job must validate before aggregation:

- protected default branch and exact source/workflow SHA equality;
- Cosign image identity, digest, issuer, and signed attestation bundle;
- runtime receipt hashes and `verification_kind=runtime`;
- exact repository, repository ID, workflow ref, run ID, and run attempt;
- exact 23 registered result files and the three W9 result files;
- closed public manifest, byte hashes, size limits, no symlink, no extra file,
  and no secret-like path or key; and
- exact upload staging with no credential, raw log, host path, environment dump,
  source payload, or token.

The existing public artifact helper is extended with a W9 payload version rather
than weakened. The Phase 0 allowlist and importer remain valid for historical
artifacts; a W9 artifact declares its own exact versioned allowlist.

## 9. Decision and scorecard

The public gate result is a closed JSON document with these top-level concepts:

```text
result_version
phase_id = "phase-1-safety"
profile_id = "forgeops-phase1-safety"
command_id = "phase1-safety-gate"
status = "READY" | "NOT_READY"
evidence_tier = "E3"
source_identity
validated_at
registry_sha256
summary
effect_counters
gates[19]
blockers[]
```

Each gate row exposes only the registered gate/profile/command/artifact IDs,
required and observed tier, status, observation time, source-current flag, and
stable blocker codes. It excludes raw cases, command output, environment data,
credentials, absolute paths, and source content.

The Markdown and HTML scorecards are deterministic projections of the JSON
decision. The HTML is static: no script, form, remote URL, active content, or
filesystem URL. Rendering never changes gate status.

`READY` requires exactly 19/19 required commands `PASSED`, no blocker, one
immutable source identity, all five E3 assertions, all freshness checks, and all
normalized effect counters equal to zero. Any parser, schema, registry, hash,
tier, freshness, receipt, completeness, or rendering precondition failure yields
`NOT_READY` with a stable public code.

## 10. Stable fail-closed errors

The implementation defines and tests at least these public codes:

```text
REGISTRY_INVALID
REGISTRATION_MISSING
REGISTRATION_DUPLICATE
ARTIFACT_MISSING
ARTIFACT_INVALID
ARTIFACT_IDENTITY_MISMATCH
ARTIFACT_NOT_PUBLIC_SAFE
SOURCE_IDENTITY_UNAVAILABLE
SOURCE_HASH_MISMATCH
SOURCE_MIXED
EVIDENCE_TIER_INSUFFICIENT
EVIDENCE_STALE
E3_RECEIPT_INVALID
E3_ATTESTATION_INVALID
OBSERVATION_UNAVAILABLE
NEGATIVE_EFFECT_OBSERVED
SCORECARD_RENDER_FAILED
```

Error text contains only stable identifiers and never includes source values,
subprocess output, file content, tokens, host paths, or unredacted exceptions.

## 11. Two-stage workflow and artifact closure

### Stage A: implementation PR

The implementation branch adds the contract, fixture, package, tests, registered
commands, workflow changes, and provisional documentation. All local results
are explicitly diagnostic. WBS-026~WBS-028 remain `WBS_NOT_STARTED` or a
documented non-terminal state, and no fresh E3 artifact is committed.

After review, the implementation PR is merged to the protected default branch.
That merge commit becomes the only acceptable source SHA for Stage B.

### Stage B: protected-main evidence and closure PR

Dispatch the existing two-job workflow against the protected default branch.
The verifier job reruns all 23 registered commands, creates the three W9 outputs,
builds the exact public manifest, and uploads the run-scoped artifact. The
downloaded artifact is verified against GitHub API facts and its signed receipt
before any repository file is replaced.

The closure branch imports only allowlisted public evidence, updates WBS-026,
WBS-027, and WBS-028 to `WBS_DONE`, and records the immutable run, attempt,
artifact, source SHA, totals, zero-effect assertions, and residual risks in WBS,
RTM, architecture, security, and verification documentation. A separate
evidence-only PR is reviewed and merged.

If the run is stale, unavailable, failed, or targets a different commit, retain
it only as historical evidence and rerun. Do not mark W9 complete.

## 12. Test strategy

The W9 suite covers:

- Draft 2020-12 schema validity and recursively closed objects;
- exact 23-command order and exact 20/19 subset cardinalities;
- registry drift, duplicate/missing/extra command and artifact substitution;
- LF Git blob versus CRLF checkout source resolution;
- missing Git identity, dirty or mixed-source evidence, hash mismatch, and
  source/workflow SHA mismatch;
- every insufficient-tier, stale, future, malformed, missing, failed, and
  `NOT_RUN` result path;
- all eight WBS-026 zero-event counters and unavailable-observation handling;
- signed E3 receipt and attestation identity near misses;
- deterministic JSON/Markdown/HTML output and forbidden-content scans;
- workflow trigger, protected-branch assertion, exactly two jobs, least
  privilege, pinned actions, timeout, exact step order, and upload allowlist;
- importer atomicity, rollback on replacement failure, no symlink/extra file,
  and stale artifact rejection; and
- WBS/RTM closure only after an imported `READY` result from the exact merge SHA.

Focused tests run before the full repository suite. The final external run also
executes all registered commands and the full test suite on Ubuntu 24.04.

## 13. Documentation and traceability

Stage A documents the design and provisional ownership in:

```text
AGENTS.md
docs/project/wbs.md
docs/project/requirements-traceability-matrix.md
docs/quality/verification-and-evaluation-plan.md
docs/architecture/system-architecture.md
docs/security/threat-model.md
```

Stage B changes completion status only with fresh imported evidence. The W9
acceptance note must explicitly say that W9 safety aggregation is complete but
WBS-029~WBS-032, VG-024, the public-safe package, local vertical demonstration,
and Phase 1 Exit remain incomplete.

## 14. Approval and external-effect boundary

This design approval authorizes only creation and local commit of the design and
implementation-plan documents. Implementation, branch publication, PR creation,
workflow dispatch, GHCR package writes, artifact download/import, closure commit,
and closure PR require a later execution authority bundle. At execution start,
those known actions should be presented together for one batched approval.
