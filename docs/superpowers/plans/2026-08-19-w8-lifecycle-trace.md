# W8 Lifecycle Budget, Cleanup, and Trace Implementation Plan

> Execute inline in this session with `superpowers:executing-plans`. Use TDD for
> every production behavior and commit after each task. Do not push or open a PR.

**Goal:** Complete WBS-023~WBS-025 with fresh VG-014/VG-015 E2 evidence while
keeping OS-wide and Phase 1 Exit claims explicitly open.

**Architecture:** A standard-library deterministic lifecycle kernel owns budget,
no-progress, cancellation, adapter cleanup, canonical trace/manifest, and a
static viewer. A registered verifier executes the exact 48-case suite.

**Base:** `feature/w7-patch-verification` at `a831ae8`

---

## Task 1: Contract, catalog, and registered identities

**Files**

- Create `contracts/forgeops-lifecycle-trace/1.0/schema.json`
- Create `fixtures/forgeops-lifecycle-trace/suite.json`
- Create `tests/lifecycle_trace/__init__.py`
- Create `tests/lifecycle_trace/test_contracts.py`
- Modify `AGENTS.md`
- Modify `docs/project/wbs.md`

**RED**

1. Test Draft 2020-12 validity and recursively closed suite/public-result shapes.
2. Assert the exact 48 ordered IDs and their four command partitions (16/10/12/10).
3. Assert exact expected result/error for every case and no duplicate IDs.
4. Assert four exact command/result registrations and two ordered profiles.
5. Assert WBS-023~025 remain `WBS_NOT_STARTED` during implementation and document
   the split between existing VG-008 E3 and new VG-014/VG-015 E2.
6. Run `python -m unittest tests.lifecycle_trace.test_contracts -v` and confirm
   missing contract/fixture failures.

**GREEN**

1. Add a closed schema with `$defs.publicResult` and strict `null` fields for
   unobserved OS counters.
2. Add the exact case suite, default limits, validation time, trace identities,
   evidence/artifact catalogs, and resource kinds.
3. Register:

```text
budget-cancel-negative -> artifacts/verification/vg-014-budget-cancel-result.json
no-progress-stop -> artifacts/verification/vg-014-no-progress-result.json
trace-manifest-completeness -> artifacts/verification/vg-015-trace-manifest-result.json
external-write-negative -> artifacts/verification/vg-015-external-write-result.json
```

4. Run the contract test, JSON parsing, and `git diff --check`.
5. Commit `feat: define W8 lifecycle trace contract`.

---

## Task 2: Budget and no-progress enforcement

**Files**

- Create `tools/lifecycle_trace/__init__.py`
- Create `tools/lifecycle_trace/model.py`
- Create `tools/lifecycle_trace/budget.py`
- Create `tests/lifecycle_trace/test_budget.py`

**Public API**

```python
class LifecycleError(Exception):
    code: str

@dataclass(frozen=True)
class BudgetLimits: ...

@dataclass
class BudgetUsage: ...

class BudgetController:
    def reserve(self, dimension: str, amount: int = 1) -> None: ...
    def stop(self, reason: str) -> None: ...
    def snapshot(self) -> dict[str, object]: ...

class NoProgressGuard:
    def observe(self, signature: str, evidence_refs: tuple[str, ...], diff_sha256: str) -> bool: ...
```

**RED**

1. Test exact-limit acceptance and projected-over-limit rejection for all six
   dimensions, including time from an injected monotonic clock.
2. Test rejection before usage mutation, bool/non-integer rejection, unknown
   dimensions, and no reserve after stop/cancel.
3. Test canonical no-progress fingerprints, changed-input reset, repeat-limit
   stop, no repair after stop, and untrusted progress claims having no effect.
4. Run `python -m unittest tests.lifecycle_trace.test_budget -v`; imports fail.

**GREEN**

1. Implement closed dataclasses and dimension-specific stable errors.
2. Make projected admission atomic: validate, calculate, reject, then mutate.
3. Hash canonical JSON for no-progress and stop at the configured repeat count.
4. Run budget tests, related local-vertical budget tests, `py_compile`, and diff check.
5. Commit `feat: add W8 budget and no-progress enforcement`.

---

## Task 3: Cancellation and verified cleanup

**Files**

- Create `tools/lifecycle_trace/lifecycle.py`
- Create `tests/lifecycle_trace/test_lifecycle.py`
- Modify `tools/lifecycle_trace/__init__.py`

**Public API**

```python
RESOURCE_KINDS = ("processes", "mounts", "leases", "transient_secrets", "workspaces")

class ResourceLedger:
    def allocate(self, kind: str, resource_id: str) -> None: ...
    def cleanup(self, *, retain: str | None = None) -> dict[str, int]: ...

class LifecycleRun:
    def dispatch(self, action_id: str, reservations: dict[str, int]) -> None: ...
    def cancel(self, reason: str, *, retain: str | None = None) -> dict[str, int]: ...
    def finish(self, reason: str, *, retain: str | None = None) -> dict[str, int]: ...
```

**RED**

1. Test active allocation/dispatch and exact budget reservation.
2. Test cancel blocks dispatch before cleanup and produces zero adapter residues.
3. Test normal success/failure/budget/no-progress terminal cleanup.
4. Test each retained resource kind maps to its exact residue error.
5. Test duplicate cleanup/cancel/finish is idempotent and cannot add events.
6. Test invalid IDs, kinds, transitions, and cleanup fault values fail before effects.

**GREEN**

1. Implement the closed state machine and ledger.
2. Record adapter effects only after all admission checks pass.
3. Validate zero residue with deterministic precedence: process, mount, lease,
   secret, workspace.
4. Run lifecycle, budget, and W6 local-vertical tests; compile and diff check.
5. Commit `feat: add W8 cancellation and cleanup lifecycle`.

---

## Task 4: Canonical trace, manifest, and viewer

**Files**

- Create `tools/lifecycle_trace/trace.py`
- Create `tests/lifecycle_trace/test_trace.py`
- Modify `tools/lifecycle_trace/__init__.py`

**Public API**

```python
def append_event(stream: list[dict[str, object]], event: dict[str, object]) -> None: ...
def build_manifest(...)-> dict[str, object]: ...
def validate_trace(events, manifest) -> None: ...
def render_trace_html(events, manifest) -> str: ...
def authorize_external_action(action, approvals, effects) -> None: ...
```

**RED**

1. Test contiguous sequence, monotonic revision, closed actor/phase/code enums,
   exact run identity, and strict UTC timestamps.
2. Test evidence/artifact reference resolution, terminal reason, cleanup zeros,
   budget usage, and allowed next actions.
3. Test manifest self-hash and unknown/missing fields.
4. Test static HTML escaping, deterministic output, required sections, and absence
   of scripts, remote URLs, forms, and absolute paths.
5. Test direct publish, gateway bypass, remote target, approval mismatch, duplicate
   effect, untraced denial, observed effect, and raw secret failures.

**GREEN**

1. Implement exact shapes and validation precedence.
2. Render only validated public-safe fields with `html.escape`.
3. Keep external-effect records empty on every negative case.
4. Run trace/lifecycle tests, interface manifest tests, compile, and diff check.
5. Commit `feat: add W8 lifecycle trace viewer`.

---

## Task 5: Registered verifier, evidence, and W8 closure

**Files**

- Create `tools/lifecycle_trace/verify.py`
- Create `tests/lifecycle_trace/test_verify.py`
- Create four `artifacts/verification/vg-014|015-*.json` results
- Create `artifacts/reviews/w8-trace-viewer.html`
- Modify `README.md`
- Modify `docs/product/prd.md`
- Modify `docs/architecture/system-architecture.md`
- Modify `docs/project/wbs.md`
- Modify `docs/project/requirements-traceability-matrix.md`
- Modify `docs/quality/verification-and-evaluation-plan.md`
- Modify this plan to check completed steps

**RED**

1. Test exact command/result identity, malformed inputs preserving a sentinel,
   runner error exit 2, case mismatch exit 1, success exit 0, and atomic writes.
2. Test exact partition/order and result schema validation.
3. Test raw schema/suite/profile-source hashes and public-safe projection.
4. Independently force each observed counter unsafe; result must be `FAILED`.
5. Ensure OS process/mount/network fields remain `null`.

**GREEN**

1. Implement a fresh temporary fixture per case and catch only `LifecycleError`
   as an expected product result.
2. Execute the four exact registered commands. Expected counts:

```text
budget-cancel-negative: 16/16 PASSED
no-progress-stop: 10/10 PASSED
trace-manifest-completeness: 12/12 PASSED
external-write-negative: 10/10 PASSED
```

3. Generate the HTML viewer from the positive terminal trace and verify it has no
   active/external content.
4. Re-run linked VG-008 input-hash consistency plus VG-012, VG-013, and VG-023
   registered commands. Restore timestamp-only changes outside W8.
5. Only after fresh results pass, mark WBS-023~025 done and update PRD/ARC/RTM,
   verification plan, and README. Keep WBS-026 onward and Phase 1 Exit open.
6. Run full tests, explicit `py_compile`, schema/result/hash consistency, secret
   scan, `git diff --check`, and worktree status.
7. Review the complete W8 diff for Critical/Important issues and fix with a
   failing test first.
8. Commit `feat: complete W8 lifecycle trace` and a documentation-only checklist
   commit if required.

---

## Completion checklist

- [x] All five tasks have independent commits and tests.
- [x] All 48 registered cases pass at E2.
- [x] Observed dispatch, cleanup, external-write, and secret counters are safe.
- [x] OS-wide unobserved counters remain `null`.
- [x] Static viewer is deterministic and contains no active content.
- [x] WBS-023~025 are done; WBS-026 onward remain not started.
- [x] VG-014/VG-015 are passed without claiming Phase 1 Exit.
- [x] Full regression and branch-wide diff checks pass.

Fresh completion evidence: W8 focused tests 44/44; registered VG-014/VG-015
cases 48/48; repository tests 516 passed with 7 documented optional skips.

## Execution decision

The user approved inline execution in this session. No subagent, push, PR, merge,
deployment, or external publication is authorized by this plan.
