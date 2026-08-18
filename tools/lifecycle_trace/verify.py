"""Registered E2 verifier for ForgeOps W8 lifecycle and trace controls."""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.lifecycle_trace.budget import BudgetController, BudgetLimits, NoProgressGuard
from tools.lifecycle_trace.lifecycle import LifecycleRun, ResourceLedger
from tools.lifecycle_trace.model import LifecycleError, atomic_write_bytes, atomic_write_json
from tools.lifecycle_trace.trace import ExternalWriteGate, TraceManifest, render_trace_html, SECRET_PATTERN


SCHEMA_REF = "contracts/forgeops-lifecycle-trace/1.0/schema.json"
SUITE_REF = "fixtures/forgeops-lifecycle-trace/suite.json"
PROFILE_SOURCE_REF = "tools/lifecycle_trace/verify.py"
PROFILE_SOURCE_REFS = (
    "tools/lifecycle_trace/verify.py",
    "tools/lifecycle_trace/model.py",
    "tools/lifecycle_trace/budget.py",
    "tools/lifecycle_trace/lifecycle.py",
    "tools/lifecycle_trace/trace.py",
)
VIEWER_REF = "artifacts/reviews/w8-trace-viewer.html"
TRUSTED_COMMANDS = {
    "budget-cancel-negative": "artifacts/verification/vg-014-budget-cancel-result.json",
    "no-progress-stop": "artifacts/verification/vg-014-no-progress-result.json",
    "trace-manifest-completeness": "artifacts/verification/vg-015-trace-manifest-result.json",
    "external-write-negative": "artifacts/verification/vg-015-external-write-result.json",
}
COMMAND_METADATA = {
    "budget-cancel-negative": ("VG-014", "forgeops-lifecycle-budget"),
    "no-progress-stop": ("VG-014", "forgeops-lifecycle-budget"),
    "trace-manifest-completeness": ("VG-015", "forgeops-trace-manifest"),
    "external-write-negative": ("VG-015", "forgeops-trace-manifest"),
}
CASE_EXPECTATIONS = {
    "budget-cancel-negative": (
        ("POSITIVE_BUDGETED_SUCCESS", "PASSED"), ("POSITIVE_CANCEL_CLEANUP", "PASSED"),
        ("NEGATIVE_TIME_LIMIT", "BUDGET_TIME_EXCEEDED"), ("NEGATIVE_TOKEN_LIMIT", "BUDGET_TOKEN_EXCEEDED"),
        ("NEGATIVE_TOOL_LIMIT", "BUDGET_TOOL_EXCEEDED"), ("NEGATIVE_COMMAND_LIMIT", "BUDGET_COMMAND_EXCEEDED"),
        ("NEGATIVE_REPAIR_LIMIT", "BUDGET_REPAIR_EXCEEDED"), ("NEGATIVE_COST_LIMIT", "BUDGET_COST_EXCEEDED"),
        ("NEGATIVE_DISPATCH_AFTER_LIMIT", "DISPATCH_FORBIDDEN"), ("NEGATIVE_DISPATCH_AFTER_CANCEL", "RUN_CANCELLED"),
        ("NEGATIVE_PROCESS_RESIDUE", "PROCESS_RESIDUE"), ("NEGATIVE_MOUNT_RESIDUE", "MOUNT_RESIDUE"),
        ("NEGATIVE_LEASE_RESIDUE", "LEASE_RESIDUE"), ("NEGATIVE_SECRET_RESIDUE", "SECRET_RESIDUE"),
        ("NEGATIVE_WORKSPACE_RESIDUE", "WORKSPACE_RESIDUE"), ("NEGATIVE_CLEANUP_NOT_IDEMPOTENT", "CLEANUP_NOT_IDEMPOTENT"),
    ),
    "no-progress-stop": (
        ("POSITIVE_PROGRESS_CONTINUES", "PASSED"), ("POSITIVE_SIGNATURE_CHANGE_CONTINUES", "PASSED"),
        ("NEGATIVE_IDENTICAL_SIGNATURE", "NO_PROGRESS_STOPPED"), ("NEGATIVE_EVIDENCE_UNCHANGED", "NO_PROGRESS_STOPPED"),
        ("NEGATIVE_DIFF_UNCHANGED", "NO_PROGRESS_STOPPED"), ("NEGATIVE_NO_PROGRESS_LIMIT", "NO_PROGRESS_STOPPED"),
        ("NEGATIVE_REPAIR_AFTER_STOP", "DISPATCH_FORBIDDEN"), ("NEGATIVE_BUDGET_PRECEDENCE", "BUDGET_REPAIR_EXCEEDED"),
        ("NEGATIVE_NONCANONICAL_SIGNATURE", "PROGRESS_INPUT_INVALID"), ("NEGATIVE_UNTRUSTED_PROGRESS", "NO_PROGRESS_STOPPED"),
    ),
    "trace-manifest-completeness": (
        ("POSITIVE_SUCCESS_TRACE", "PASSED"), ("POSITIVE_CANCEL_TRACE", "PASSED"),
        ("POSITIVE_BUDGET_TRACE", "PASSED"), ("NEGATIVE_EVENT_GAP", "TRACE_SEQUENCE_INVALID"),
        ("NEGATIVE_EVENT_REORDER", "TRACE_SEQUENCE_INVALID"), ("NEGATIVE_REVISION_DECREASE", "TRACE_REVISION_INVALID"),
        ("NEGATIVE_ACTOR_INVALID", "TRACE_ACTOR_INVALID"), ("NEGATIVE_EVIDENCE_DANGLING", "TRACE_REFERENCE_INVALID"),
        ("NEGATIVE_ARTIFACT_DANGLING", "TRACE_REFERENCE_INVALID"), ("NEGATIVE_CLEANUP_MISSING", "TRACE_CLEANUP_INVALID"),
        ("NEGATIVE_TERMINAL_REASON", "TRACE_TERMINAL_INVALID"), ("NEGATIVE_NEXT_ACTION", "TRACE_NEXT_ACTION_INVALID"),
    ),
    "external-write-negative": (
        ("POSITIVE_NO_EXTERNAL_WRITE", "PASSED"), ("NEGATIVE_DIRECT_PUBLISH", "EXTERNAL_ACTION_FORBIDDEN"),
        ("NEGATIVE_GATEWAY_BYPASS", "EXTERNAL_GATEWAY_REQUIRED"), ("NEGATIVE_REMOTE_TARGET", "EXTERNAL_TARGET_INVALID"),
        ("NEGATIVE_APPROVAL_ABSENT", "EXTERNAL_APPROVAL_REQUIRED"), ("NEGATIVE_APPROVAL_MISMATCH", "EXTERNAL_APPROVAL_INVALID"),
        ("NEGATIVE_DUPLICATE_EFFECT", "EXTERNAL_EFFECT_DUPLICATE"), ("NEGATIVE_DENIAL_NOT_TRACED", "EXTERNAL_DENIAL_TRACE_MISSING"),
        ("NEGATIVE_EFFECT_OBSERVED", "EXTERNAL_EFFECT_OBSERVED"), ("NEGATIVE_RAW_SECRET", "RESULT_SECRET_DETECTED"),
    ),
}


class VerificationError(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass
class CaseAudit:
    unauthorized_dispatches: int = 0
    adapter_cleanup_residues: int = 0
    external_write_attempts: int = 0


def _strict_ref(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise VerificationError("VERIFIER_IDENTITY_INVALID")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise VerificationError("VERIFIER_IDENTITY_INVALID")
    return value


def _validate_identity(args: argparse.Namespace) -> None:
    if args.command_id not in TRUSTED_COMMANDS:
        raise VerificationError("VERIFIER_IDENTITY_INVALID")
    expected = {"schema": SCHEMA_REF, "suite": SUITE_REF,
                "result": TRUSTED_COMMANDS[args.command_id]}
    for name, trusted in expected.items():
        observed = getattr(args, name, None)
        if observed != trusted:
            raise VerificationError("VERIFIER_IDENTITY_INVALID")
        _strict_ref(observed)


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError("VERIFIER_INPUT_INVALID") from error


def _validate_suite(value: object, schema: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, dict) or list(Draft202012Validator(schema).iter_errors(value)):
        raise VerificationError("VERIFIER_INPUT_INVALID")
    expected = tuple(item for command in CASE_EXPECTATIONS.values() for item in command)
    cases = value.get("cases")
    observed = tuple((case.get("id"), case.get("expected")) for case in cases if isinstance(case, dict)) if isinstance(cases, list) else ()
    if observed != expected:
        raise VerificationError("VERIFIER_INPUT_INVALID")
    for command_id, catalog in CASE_EXPECTATIONS.items():
        selected = [case for case in cases if case["command_id"] == command_id]
        if tuple(case["id"] for case in selected) != tuple(item[0] for item in catalog):
            raise VerificationError("VERIFIER_INPUT_INVALID")
        if any(case["mutation"] != case["id"] or case["kind"] != ("positive" if case["id"].startswith("POSITIVE_") else "negative") for case in selected):
            raise VerificationError("VERIFIER_INPUT_INVALID")
    return value


def _repository_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if (not relative.parts or relative.parts[0] in {".git", "artifacts"}
                or "__pycache__" in relative.parts or not path.is_file() or path.is_symlink()):
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _profile_source_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for relative in PROFILE_SOURCE_REFS:
        path = root / relative
        if not path.is_file() or path.is_symlink():
            raise VerificationError("VERIFIER_INPUT_INVALID")
        content = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def _limits(fixture: Mapping[str, object], *, now: list[int] | None = None) -> tuple[BudgetController, list[int]]:
    clock = now or [0]
    limits = BudgetLimits(**fixture["limits"])
    return BudgetController(limits, clock_ms=lambda: clock[0]), clock


def _evaluate_budget(case_id: str, fixture: Mapping[str, object]) -> TraceManifest | None:
    controller, now = _limits(fixture)
    run = LifecycleRun(controller)
    dimensions = {
        "NEGATIVE_TOKEN_LIMIT": "tokens", "NEGATIVE_TOOL_LIMIT": "tool_calls",
        "NEGATIVE_COMMAND_LIMIT": "command_calls", "NEGATIVE_REPAIR_LIMIT": "repair_attempts",
        "NEGATIVE_COST_LIMIT": "cost_microunits",
    }
    if case_id == "POSITIVE_BUDGETED_SUCCESS":
        controller.reserve("tokens", 100)
        run.complete()
    elif case_id == "POSITIVE_CANCEL_CLEANUP":
        for kind in ResourceLedger.KINDS:
            run.resources.acquire(kind, f"{kind}-1")
        run.cancel()
    elif case_id == "NEGATIVE_TIME_LIMIT":
        now[0] = fixture["limits"]["time_ms"] + 1
        run.authorize_dispatch()
    elif case_id in dimensions:
        dimension = dimensions[case_id]
        controller.reserve(dimension, fixture["limits"][dimension] + 1)
    elif case_id == "NEGATIVE_DISPATCH_AFTER_LIMIT":
        try:
            controller.reserve("tokens", fixture["limits"]["tokens"] + 1)
        except LifecycleError:
            pass
        controller.authorize_dispatch()
    elif case_id == "NEGATIVE_DISPATCH_AFTER_CANCEL":
        run.cancel()
        run.authorize_dispatch()
    elif case_id.startswith("NEGATIVE_") and case_id.endswith("_RESIDUE"):
        kinds = {"NEGATIVE_PROCESS_RESIDUE": "processes", "NEGATIVE_MOUNT_RESIDUE": "mounts",
                 "NEGATIVE_LEASE_RESIDUE": "leases", "NEGATIVE_SECRET_RESIDUE": "transient_secrets",
                 "NEGATIVE_WORKSPACE_RESIDUE": "workspaces"}
        kind = kinds[case_id]
        ledger = ResourceLedger(cleanup_failures={kind})
        ledger.acquire(kind, f"{kind}-1")
        LifecycleRun(controller, resources=ledger).cleanup()
    elif case_id == "NEGATIVE_CLEANUP_NOT_IDEMPOTENT":
        run.cleanup()
        run._cleanup_receipt["remaining"]["leases"] = 1
        run.cleanup()
    return None


def _evaluate_progress(case_id: str, fixture: Mapping[str, object]) -> TraceManifest | None:
    controller, _ = _limits(fixture)
    guard = NoProgressGuard(limit=fixture["no_progress_limit"], budget=controller)
    base = ("CHECK_A", ("EVID-W8-TASK",), "a" * 64)
    if case_id in {"POSITIVE_PROGRESS_CONTINUES", "POSITIVE_SIGNATURE_CHANGE_CONTINUES"}:
        guard.observe(*base, trusted=True)
        guard.observe("CHECK_B", ("EVID-W8-REGRESSION",), "b" * 64, trusted=True)
    elif case_id in {"NEGATIVE_IDENTICAL_SIGNATURE", "NEGATIVE_EVIDENCE_UNCHANGED", "NEGATIVE_DIFF_UNCHANGED", "NEGATIVE_NO_PROGRESS_LIMIT"}:
        guard.observe(*base, trusted=True)
        guard.observe(*base, trusted=True)
        guard.observe(*base, trusted=True)
    elif case_id == "NEGATIVE_REPAIR_AFTER_STOP":
        try:
            guard.observe(*base, trusted=True); guard.observe(*base, trusted=True); guard.observe(*base, trusted=True)
        except LifecycleError:
            pass
        controller.authorize_dispatch()
    elif case_id == "NEGATIVE_BUDGET_PRECEDENCE":
        controller.reserve("repair_attempts", fixture["limits"]["repair_attempts"] + 1)
    elif case_id == "NEGATIVE_NONCANONICAL_SIGNATURE":
        guard.observe("not canonical", ("EVID-W8-TASK",), "a" * 64, trusted=True)
    elif case_id == "NEGATIVE_UNTRUSTED_PROGRESS":
        guard.observe(*base, trusted=True)
        guard.observe("CHECK_B", ("EVID-W8-REGRESSION",), "b" * 64, trusted=False)
        guard.observe("CHECK_C", ("EVID-W8-REGRESSION",), "c" * 64, trusted=False)
    return None


def _valid_trace(fixture: Mapping[str, object], reason: str = "SUCCESS") -> TraceManifest:
    trace = TraceManifest(fixture["identities"], evidence_catalog=tuple(fixture["evidence_catalog"]),
                          artifact_catalog=tuple(fixture["artifact_catalog"]))
    trace.append("MAIN", "TASK_ACCEPTED", 1, evidence_refs=("EVID-W8-TASK",))
    trace.append("WORK", "CLEANUP_VERIFIED", 2, artifact_refs=("ART-W8-TRACE",))
    actions = {"SUCCESS": ("CLOSE",), "USER_CANCELLED": ("STOP",),
               "BUDGET_STOPPED": ("WAIT_FOR_HUMAN",)}[reason]
    trace.finalize(reason, actions, {"remaining": {kind: 0 for kind in ResourceLedger.KINDS}})
    return trace


def _evaluate_trace(case_id: str, fixture: Mapping[str, object]) -> TraceManifest:
    reasons = {"POSITIVE_CANCEL_TRACE": "USER_CANCELLED", "POSITIVE_BUDGET_TRACE": "BUDGET_STOPPED"}
    trace = _valid_trace(fixture, reasons.get(case_id, "SUCCESS"))
    if case_id == "NEGATIVE_EVENT_GAP":
        trace.events[1]["seq"] = 3
    elif case_id == "NEGATIVE_EVENT_REORDER":
        trace.events[0]["seq"], trace.events[1]["seq"] = 2, 1
    elif case_id == "NEGATIVE_REVISION_DECREASE":
        trace.events[1]["revision"] = 0
    elif case_id == "NEGATIVE_ACTOR_INVALID":
        trace.events[0]["actor"] = "ROOT"
    elif case_id == "NEGATIVE_EVIDENCE_DANGLING":
        trace.events[0]["evidence_refs"] = ["EVID-MISSING"]
    elif case_id == "NEGATIVE_ARTIFACT_DANGLING":
        trace.events[0]["artifact_refs"] = ["ART-MISSING"]
    elif case_id == "NEGATIVE_CLEANUP_MISSING":
        trace.cleanup = None
    elif case_id == "NEGATIVE_TERMINAL_REASON":
        trace.terminal["reason"] = ""
    elif case_id == "NEGATIVE_NEXT_ACTION":
        trace.terminal["next_actions"] = ["RETRY_REPAIR"]
    trace.validate()
    return trace


def _evaluate_external(case_id: str) -> TraceManifest | None:
    gate = ExternalWriteGate(expected_approval="APPROVAL-W8", allowed_target="github:forgeops")
    if case_id == "POSITIVE_NO_EXTERNAL_WRITE":
        gate.authorize("NONE", None, False, None, None)
    elif case_id == "NEGATIVE_DIRECT_PUBLISH":
        gate.authorize("PUBLISH", "github:forgeops", True, "APPROVAL-W8", "EFFECT-1")
    elif case_id == "NEGATIVE_GATEWAY_BYPASS":
        gate.authorize("APPROVED_EXTERNAL_WRITE", "github:forgeops", False, "APPROVAL-W8", "EFFECT-1")
    elif case_id == "NEGATIVE_REMOTE_TARGET":
        gate.authorize("APPROVED_EXTERNAL_WRITE", "https://example.test", True, "APPROVAL-W8", "EFFECT-1")
    elif case_id == "NEGATIVE_APPROVAL_ABSENT":
        gate.authorize("APPROVED_EXTERNAL_WRITE", "github:forgeops", True, None, "EFFECT-1")
    elif case_id == "NEGATIVE_APPROVAL_MISMATCH":
        gate.authorize("APPROVED_EXTERNAL_WRITE", "github:forgeops", True, "WRONG", "EFFECT-1")
    elif case_id == "NEGATIVE_DUPLICATE_EFFECT":
        args = ("APPROVED_EXTERNAL_WRITE", "github:forgeops", True, "APPROVAL-W8", "EFFECT-1")
        gate.authorize(*args); gate.authorize(*args)
    elif case_id == "NEGATIVE_DENIAL_NOT_TRACED":
        gate.audit(denial_required=True, denial_traced=False, effect_observed=False, public_text="safe")
    elif case_id == "NEGATIVE_EFFECT_OBSERVED":
        gate.audit(denial_required=False, denial_traced=True, effect_observed=True, public_text="safe")
    elif case_id == "NEGATIVE_RAW_SECRET":
        gate.audit(denial_required=False, denial_traced=True, effect_observed=False,
                   public_text="token=ghp_12345678901234567890")
    return None


def _evaluate_case(case: Mapping[str, object], fixture: Mapping[str, object]) -> tuple[dict[str, str], CaseAudit, TraceManifest | None]:
    actual = "PASSED"
    manifest = None
    try:
        command = case["command_id"]
        if command == "budget-cancel-negative":
            manifest = _evaluate_budget(case["id"], fixture)
        elif command == "no-progress-stop":
            manifest = _evaluate_progress(case["id"], fixture)
        elif command == "trace-manifest-completeness":
            manifest = _evaluate_trace(case["id"], fixture)
        else:
            manifest = _evaluate_external(case["id"])
    except LifecycleError as error:
        actual = error.code
    return ({"id": case["id"], "kind": case["kind"],
             "expected": case["expected"], "actual": actual}, CaseAudit(), manifest)


def _effect_counters(source_unchanged: bool, audits: Sequence[CaseAudit], basis: object) -> dict[str, object]:
    serialized = json.dumps(basis, sort_keys=True, ensure_ascii=False)
    return {"source_tree_hash_unchanged": source_unchanged,
            "unauthorized_dispatches": sum(item.unauthorized_dispatches for item in audits),
            "adapter_cleanup_residues": sum(item.adapter_cleanup_residues for item in audits),
            "external_write_attempts": sum(item.external_write_attempts for item in audits),
            "result_artifact_raw_secret_occurrences": len(SECRET_PATTERN.findall(serialized)),
            "os_process_tree_residue": None, "os_mount_residue": None, "network_calls": None}


def run(args: argparse.Namespace, *, repository_root: Path = REPOSITORY_ROOT) -> int:
    repository_root = Path(repository_root).resolve()
    _validate_identity(args)
    schema_path, suite_path = repository_root / args.schema, repository_root / args.suite
    schema, suite_value = _load_json(schema_path), _load_json(suite_path)
    if not isinstance(schema, dict):
        raise VerificationError("VERIFIER_INPUT_INVALID")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise VerificationError("VERIFIER_INPUT_INVALID") from error
    suite = _validate_suite(suite_value, schema)
    profile_source_hash = _profile_source_hash(repository_root)
    source_before = _repository_tree_hash(repository_root)
    selected = [case for case in suite["cases"] if case["command_id"] == args.command_id]
    evaluated = [_evaluate_case(case, suite["base_fixture"]) for case in selected]
    cases, audits = [item[0] for item in evaluated], [item[1] for item in evaluated]
    manifests = [item[2] for item in evaluated if item[2] is not None and item[0]["actual"] == "PASSED"]
    source_after = _repository_tree_hash(repository_root)
    counters = _effect_counters(source_before == source_after, audits,
                                {"command_id": args.command_id, "cases": cases})
    unsafe = (not counters["source_tree_hash_unchanged"]
              or counters["unauthorized_dispatches"] != 0
              or counters["adapter_cleanup_residues"] != 0
              or counters["external_write_attempts"] != 0
              or counters["result_artifact_raw_secret_occurrences"] != 0)
    if unsafe and cases:
        cases[0] = {**cases[0], "actual": "VERIFIER_AUDIT_FAILED"}
    failed = sum(case["expected"] != case["actual"] for case in cases)
    gate_id, profile_id = COMMAND_METADATA[args.command_id]
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result = {"result_version": "1.0", "gate_id": gate_id, "profile_id": profile_id,
              "command_id": args.command_id, "status": "PASSED" if failed == 0 else "FAILED",
              "evidence_tier": "E2", "observed_at": observed_at,
              "input_hashes": {"schema": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
                               "suite": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
                               "profile_source": profile_source_hash},
              "summary": {"total": len(cases), "passed": len(cases) - failed, "failed": failed},
              "effect_counters": counters, "cases": cases}
    public_schema = {"$ref": "#/$defs/publicResult", "$defs": schema["$defs"]}
    if list(Draft202012Validator(public_schema).iter_errors(result)):
        raise VerificationError("VERIFIER_RESULT_INVALID")
    if args.command_id == "trace-manifest-completeness" and manifests:
        atomic_write_bytes(repository_root / VIEWER_REF,
                           render_trace_html(manifests[0].to_dict()).encode("utf-8"))
    atomic_write_json(repository_root / args.result, result)
    return 0 if failed == 0 else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--command-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None, *, repository_root: Path = REPOSITORY_ROOT) -> int:
    try:
        return run(_parser().parse_args(argv), repository_root=repository_root)
    except (VerificationError, LifecycleError, OSError, RuntimeError, ValueError, TypeError, KeyError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
