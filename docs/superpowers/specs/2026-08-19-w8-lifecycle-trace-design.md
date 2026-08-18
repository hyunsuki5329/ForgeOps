# W8 Lifecycle Budget, Cleanup, and Trace Design

**Date:** 2026-08-19
**Status:** Approved for implementation
**Base:** `feature/w7-patch-verification` (`a831ae8`)
**Scope:** WBS-023~WBS-025, VG-014, VG-015

## 1. Goal and evidence boundary

W8 adds a deterministic local lifecycle kernel that enforces bounded execution,
stops dispatch after cancellation or exhaustion, verifies cleanup of resources
owned by its adapter, and produces an interpretable terminal trace. It closes the
local E2 portions of VG-014 and VG-015.

The W8 verifier observes only its own resource adapter. `process`, `mount`,
`lease`, `transient_secret`, and `workspace` are closed adapter resource kinds;
they are not claims about every OS process, mount, credential, or filesystem
write on the host. Existing hash-current VG-008 E3 evidence continues to own the
Linux container, egress, and teardown boundary. W8 results therefore use `null`
for unobserved OS process, OS mount, and network counters.

W8 does not complete WBS-026 onward, the Phase 1 safety gate, Phase 1 Exit,
deployment, publishing, or a remote integration.

## 2. Chosen architecture

Use a Python standard-library deterministic kernel with injected monotonic time
and verifier-owned temporary resources. This is preferred over real host process
and mount orchestration because the latter is privilege- and platform-dependent,
and over schema-only fixtures because they would not execute lifecycle behavior.

New package:

```text
tools/lifecycle_trace/
  model.py       closed errors, hashing, UTC, atomic JSON
  budget.py      reserve-before-dispatch and no-progress enforcement
  lifecycle.py   state machine and idempotent resource cleanup
  trace.py       canonical events, manifest, and public-safe HTML rendering
  verify.py      registered VG-014/VG-015 command runner
```

Contract and fixture:

```text
contracts/forgeops-lifecycle-trace/1.0/schema.json
fixtures/forgeops-lifecycle-trace/suite.json
```

## 3. Five implementation tasks

1. Define the closed lifecycle/trace contract, exact case catalog, registered
   commands, and W8 ownership boundaries.
2. Implement budget accounting and no-progress stopping.
3. Implement cancellation and verified idempotent cleanup.
4. Implement canonical trace/manifest validation and static HTML rendering.
5. Implement registered result generation, execute evidence, and close W8 docs.

Each task uses test-first RED/GREEN development and an independent commit.

## 4. Contract identities

Registered profiles and commands are exact and ordered:

```yaml
forgeops-lifecycle-budget:
  - budget-cancel-negative
  - no-progress-stop
forgeops-trace-manifest:
  - trace-manifest-completeness
  - external-write-negative
```

Registered result paths:

```text
artifacts/verification/vg-014-budget-cancel-result.json
artifacts/verification/vg-014-no-progress-result.json
artifacts/verification/vg-015-trace-manifest-result.json
artifacts/verification/vg-015-external-write-result.json
```

All four commands are required E2 checks. The contract is Draft 2020-12 and
closes every object and array shape used by the suite and public result.

## 5. Budget and no-progress model

`BudgetLimits` and `BudgetUsage` have exactly six non-negative integer fields:

```text
time_ms
tokens
tool_calls
command_calls
repair_attempts
cost_microunits
```

`BudgetController.reserve()` checks projected usage before changing usage. A
request that would exceed a limit raises the dimension-specific stable error and
makes the controller `STOPPED`. Once stopped or cancelled, every later reserve
or dispatch attempt is rejected without changing counters.

Time uses an injected monotonic integer clock. Wall-clock timestamps are used
only for evidence and trace serialization. Boolean values are not accepted as
integers.

`NoProgressGuard.observe()` hashes the exact tuple of failure signature,
ordered evidence references, and diff hash. A changed tuple resets the repeat
count. Reaching the configured repeat limit records `NO_PROGRESS_STOPPED` and
prevents another repair reservation or dispatch. Untrusted claims of progress
cannot change the fingerprint.

## 6. Lifecycle and cleanup model

Lifecycle states are closed:

```text
ACTIVE, CANCELLING, TERMINAL
```

Terminal reasons are closed:

```text
SUCCEEDED, FAILED, CANCELLED, BUDGET_EXHAUSTED, NO_PROGRESS
```

The adapter ledger owns five resource sets:

```text
processes, mounts, leases, transient_secrets, workspaces
```

Allocation is allowed only while active and budget-authorized. `cancel()` first
blocks dispatch, records one cancellation event, then invokes cleanup. Normal
terminal paths invoke the same cleanup. Cleanup is idempotent: repeated calls do
not add events, effects, or errors. A verifier fault injector may retain exactly
one resource kind so each residue category can be tested independently.

A terminal result is accepted only when all five adapter residue counts are
zero. Cleanup errors never convert a run to success.

## 7. Trace, manifest, and viewer

Main-owned canonical events contain exactly:

```text
event_id, task_id, run_id, correlation_id, actor, phase,
code, seq, revision, observed_at, evidence_refs, artifact_refs
```

Sequence starts at one and is contiguous. Revision never decreases. Actors,
phases, and codes use closed enums. Evidence and artifact references must resolve
against catalogs in the same run.

The terminal manifest contains identity, event range, terminal reason, budget
limits and usage, cleanup counts, evidence/artifact catalogs, allowed next
actions, and a hash over the manifest excluding only its own hash field.

The viewer is a static, escaped HTML document produced from a validated manifest
and event stream. It shows terminal reason, actor-ordered timeline, budget usage,
cleanup status, evidence/artifact references, and allowed next actions. It has no
script, remote asset, link target, form, or network behavior.

## 8. External-write boundary

The local kernel exposes only named adapter actions. `PUBLISH`, raw URLs, remote
targets, gateway bypass, missing/mismatched approval, and duplicate external
effect identities are rejected before an effect record is appended. The W8
positive path records zero external effects.

This is a contract/kernel E2 proof, not a claim that the host made no network
calls. `network_calls` remains `null` in public results.

## 9. Exact case catalog

### `budget-cancel-negative` (16)

```text
POSITIVE_BUDGETED_SUCCESS
POSITIVE_CANCEL_CLEANUP
NEGATIVE_TIME_LIMIT
NEGATIVE_TOKEN_LIMIT
NEGATIVE_TOOL_LIMIT
NEGATIVE_COMMAND_LIMIT
NEGATIVE_REPAIR_LIMIT
NEGATIVE_COST_LIMIT
NEGATIVE_DISPATCH_AFTER_LIMIT
NEGATIVE_DISPATCH_AFTER_CANCEL
NEGATIVE_PROCESS_RESIDUE
NEGATIVE_MOUNT_RESIDUE
NEGATIVE_LEASE_RESIDUE
NEGATIVE_SECRET_RESIDUE
NEGATIVE_WORKSPACE_RESIDUE
NEGATIVE_CLEANUP_NOT_IDEMPOTENT
```

### `no-progress-stop` (10)

```text
POSITIVE_PROGRESS_CONTINUES
POSITIVE_SIGNATURE_CHANGE_CONTINUES
NEGATIVE_IDENTICAL_SIGNATURE
NEGATIVE_EVIDENCE_UNCHANGED
NEGATIVE_DIFF_UNCHANGED
NEGATIVE_NO_PROGRESS_LIMIT
NEGATIVE_REPAIR_AFTER_STOP
NEGATIVE_BUDGET_PRECEDENCE
NEGATIVE_NONCANONICAL_SIGNATURE
NEGATIVE_UNTRUSTED_PROGRESS
```

### `trace-manifest-completeness` (12)

```text
POSITIVE_SUCCESS_TRACE
POSITIVE_CANCEL_TRACE
POSITIVE_BUDGET_TRACE
NEGATIVE_EVENT_GAP
NEGATIVE_EVENT_REORDER
NEGATIVE_REVISION_DECREASE
NEGATIVE_ACTOR_INVALID
NEGATIVE_EVIDENCE_DANGLING
NEGATIVE_ARTIFACT_DANGLING
NEGATIVE_CLEANUP_MISSING
NEGATIVE_TERMINAL_REASON
NEGATIVE_NEXT_ACTION
```

### `external-write-negative` (10)

```text
POSITIVE_NO_EXTERNAL_WRITE
NEGATIVE_DIRECT_PUBLISH
NEGATIVE_GATEWAY_BYPASS
NEGATIVE_REMOTE_TARGET
NEGATIVE_APPROVAL_ABSENT
NEGATIVE_APPROVAL_MISMATCH
NEGATIVE_DUPLICATE_EFFECT
NEGATIVE_DENIAL_NOT_TRACED
NEGATIVE_EFFECT_OBSERVED
NEGATIVE_RAW_SECRET
```

The suite therefore contains exactly 48 ordered cases.

## 10. Stable failure categories

```text
BUDGET_TIME_EXCEEDED
BUDGET_TOKEN_EXCEEDED
BUDGET_TOOL_EXCEEDED
BUDGET_COMMAND_EXCEEDED
BUDGET_REPAIR_EXCEEDED
BUDGET_COST_EXCEEDED
DISPATCH_FORBIDDEN
RUN_CANCELLED
NO_PROGRESS_STOPPED
PROGRESS_INPUT_INVALID
PROCESS_RESIDUE
MOUNT_RESIDUE
LEASE_RESIDUE
SECRET_RESIDUE
WORKSPACE_RESIDUE
CLEANUP_NOT_IDEMPOTENT
TRACE_SEQUENCE_INVALID
TRACE_REVISION_INVALID
TRACE_ACTOR_INVALID
TRACE_REFERENCE_INVALID
TRACE_CLEANUP_INVALID
TRACE_TERMINAL_INVALID
TRACE_NEXT_ACTION_INVALID
EXTERNAL_ACTION_FORBIDDEN
EXTERNAL_GATEWAY_REQUIRED
EXTERNAL_TARGET_INVALID
EXTERNAL_APPROVAL_REQUIRED
EXTERNAL_APPROVAL_INVALID
EXTERNAL_EFFECT_DUPLICATE
EXTERNAL_DENIAL_TRACE_MISSING
EXTERNAL_EFFECT_OBSERVED
RESULT_SECRET_DETECTED
```

Validation precedence is identity and shape, budget/cancel admission, mutation,
cleanup, trace references, external-effect audit, then public-result audit.

## 11. Public result and evidence honesty

Each result contains exact schema/suite/profile-source hashes, command identity,
E2 tier, strict UTC observation time, case records, and these counters:

```text
source_tree_hash_unchanged: boolean
unauthorized_dispatches: integer
adapter_cleanup_residues: integer
external_write_attempts: integer
result_artifact_raw_secret_occurrences: integer
os_process_tree_residue: null
os_mount_residue: null
network_calls: null
```

A result is `PASSED` only when every selected case matches and every observed
counter is safe. Unobserved values remain `null`; they are never rewritten as
zero.

## 12. Completion and documentation

After all four registered commands produce fresh `PASSED` results:

- WBS-023~WBS-025 become `WBS_DONE`.
- PRD-FR-013 becomes `IMPLEMENTED` for the local lifecycle/trace subset.
- RTM links exact artifacts and observation times.
- Architecture records the implemented local subset while retaining PLANNED
  maturity for distributed control plane, full sandbox, and production UI.
- VG-014 and VG-015 become actual E2 `PASSED`; WBS-026 onward and Phase 1 Exit
  remain `NOT_RUN`.
- README documents W8 and the remaining W9/W10 blockers.

No push, PR, merge, deployment, or message publication is part of W8 execution.
