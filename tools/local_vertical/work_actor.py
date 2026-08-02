"""Bounded Work execution for the local W6 vertical flow."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
import tempfile

from tools.local_vertical.common import (
    TrustedExecutionContext,
    VerticalFlowError,
    canonical_json_bytes,
    canonical_resource_ref,
    require_id,
    require_strict_utc,
    thaw_json,
    validate_authority,
)
from tools.local_vertical.main_actor import validate_main_issued_context


_TASK_FIELDS = frozenset(
    {
        "protocol_version",
        "packet_type",
        "task_id",
        "correlation_id",
        "base_revision",
        "actor",
        "status",
        "payload",
    }
)
_TASK_PAYLOAD_FIELDS = frozenset(
    {"request", "project_profile", "capabilities", "authority", "control", "budgets"}
)
_CANDIDATE_PACKET_FIELDS = _TASK_FIELDS
_CANDIDATE_FIELDS = frozenset(
    {
        "candidate_id",
        "action_type",
        "action_identity",
        "resource_ref",
        "operation",
        "expected_effect",
        "scope",
        "rationale",
        "confidence",
        "confidence_basis",
        "evidence_refs",
        "dependencies",
        "preconditions",
        "proposed_verification",
        "risk_notes",
        "acceptance_criteria_ids",
    }
)
_BEFORE = b"before\n"
_AFTER = b"after\n"
_RESOURCE_REF = "fixture/work-item.txt"
_CANDIDATE_ID = "CAND-W6-UPDATE"
_CRITERION_ID = "AC-W6-1"


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_work_task(task: object, current_revision: object) -> dict[str, object]:
    """Validate the Main-owned Work route without reading a target."""
    if not isinstance(task, dict) or set(task) != _TASK_FIELDS:
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    if (
        task["protocol_version"] != "2.0"
        or task["packet_type"] != "task"
        or task["actor"] != "main"
        or task["status"] != "IN_PROGRESS"
        or not _is_nonnegative_int(task["base_revision"])
    ):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    try:
        require_id(task["task_id"], code="WORK_ENVELOPE_INVALID")
        require_id(task["correlation_id"], code="WORK_ENVELOPE_INVALID")
    except VerticalFlowError as exc:
        raise VerticalFlowError("WORK_ENVELOPE_INVALID") from exc
    if not _is_nonnegative_int(current_revision) or task["base_revision"] != current_revision:
        raise VerticalFlowError("WORK_REVISION_STALE")
    payload = task["payload"]
    if not isinstance(payload, dict) or set(payload) != _TASK_PAYLOAD_FIELDS:
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    control = payload["control"]
    if not isinstance(control, dict) or control.get("route") != "WORK_ONLY":
        raise VerticalFlowError("WORK_ROUTE_INVALID")
    if control.get("operation_mode") != "EXECUTE":
        raise VerticalFlowError("WORK_OPERATION_MODE_INVALID")
    capabilities = payload["capabilities"]
    if (
        not isinstance(capabilities, dict)
        or capabilities.get("filesystem_read") != "AVAILABLE"
        or capabilities.get("filesystem_write") != "AVAILABLE"
    ):
        raise VerticalFlowError("WORK_CAPABILITY_DENIED")
    project_profile = payload["project_profile"]
    if (
        not isinstance(project_profile, dict)
        or project_profile.get("profile_status") != "LOADED"
    ):
        raise VerticalFlowError("WORK_PROFILE_NOT_LOADED")
    budgets = payload["budgets"]
    work_attempts = budgets.get("work_attempts") if isinstance(budgets, dict) else None
    if (
        isinstance(work_attempts, bool)
        or not isinstance(work_attempts, int)
        or work_attempts < 1
    ):
        raise VerticalFlowError("WORK_BUDGET_EXHAUSTED")
    return task


def require_exact_authority(
    task: Mapping[str, object], context: TrustedExecutionContext
) -> None:
    """Require the embedded Work task and trusted snapshot to bind identical authority."""
    try:
        task_authority = task["payload"]["authority"]
        trusted_authority = thaw_json(context.authority)
        matches = canonical_json_bytes(task_authority) == canonical_json_bytes(
            trusted_authority
        )
    except (KeyError, TypeError, VerticalFlowError) as exc:
        raise VerticalFlowError("WORK_AUTHORITY_CONTEXT_MISMATCH") from exc
    if not matches:
        raise VerticalFlowError("WORK_AUTHORITY_CONTEXT_MISMATCH")


def _candidate_id(candidate: object) -> str:
    if not isinstance(candidate, dict):
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID")
    try:
        return require_id(candidate.get("candidate_id"), code="WORK_APPROVED_ID_INVALID")
    except VerticalFlowError as exc:
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID") from exc


def validate_approved_coverage(
    candidate_packet: object, context: TrustedExecutionContext
) -> list[dict[str, object]]:
    """Bind the immutable approved records exactly to their Part packet envelope."""
    if not isinstance(candidate_packet, dict) or set(candidate_packet) != _CANDIDATE_PACKET_FIELDS:
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    task = thaw_json(context.task_packet)
    if (
        candidate_packet["protocol_version"] != "2.0"
        or candidate_packet["packet_type"] != "candidate_proposal"
        or candidate_packet["actor"] != "part"
        or candidate_packet["status"] != "IN_PROGRESS"
        or candidate_packet["task_id"] != task["task_id"]
        or candidate_packet["correlation_id"] != task["correlation_id"]
        or candidate_packet["base_revision"] != context.current_revision
        or isinstance(candidate_packet["base_revision"], bool)
    ):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    payload = candidate_packet["payload"]
    if not isinstance(payload, dict):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    if "approved_candidate_ids" in payload:
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID")
    if "validationAt" in payload or "validation_at" in payload:
        raise VerticalFlowError("WORK_VALIDATION_AT_UNTRUSTED")
    packet_candidates = payload.get("candidates")
    approved_candidates = thaw_json(context.approved_candidates)
    approved_ids = list(context.approved_candidate_ids)
    if (
        not isinstance(packet_candidates, list)
        or not isinstance(approved_candidates, list)
        or not approved_ids
        or any(not isinstance(item, str) or not item for item in approved_ids)
        or len(approved_ids) != len(set(approved_ids))
    ):
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID")
    packet_ids = [_candidate_id(candidate) for candidate in packet_candidates]
    trusted_ids = [_candidate_id(candidate) for candidate in approved_candidates]
    if (
        packet_ids != approved_ids
        or trusted_ids != approved_ids
        or packet_candidates != approved_candidates
    ):
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID")
    return approved_candidates


def validate_action_identity(candidate: object) -> dict[str, object]:
    """Accept only the exact deterministic W6 resource update."""
    if not isinstance(candidate, dict) or set(candidate) != _CANDIDATE_FIELDS:
        raise VerticalFlowError("WORK_ACTION_IDENTITY_INVALID")
    if candidate["action_type"] != "UPDATE_RESOURCE":
        raise VerticalFlowError("WORK_ACTION_TYPE_UNSUPPORTED")
    identity = candidate["action_identity"]
    if (
        not isinstance(identity, dict)
        or set(identity) != {"identity_kind", "resource_ref"}
        or identity.get("identity_kind") != "RESOURCE"
        or candidate["operation"] != "update"
        or candidate["resource_ref"] != identity.get("resource_ref")
        or candidate["scope"] != [identity.get("resource_ref")]
    ):
        raise VerticalFlowError("WORK_ACTION_IDENTITY_INVALID")
    try:
        resource_ref = canonical_resource_ref(identity["resource_ref"])
    except VerticalFlowError as exc:
        raise VerticalFlowError("WORK_ACTION_IDENTITY_INVALID") from exc
    if (
        candidate["candidate_id"] != _CANDIDATE_ID
        or resource_ref != _RESOURCE_REF
        or candidate["expected_effect"] != "replace fixture marker before with after"
        or candidate["preconditions"]
        != ["sha256:c0cde77fa8fef97d3b55e18e9a5f8f08c4f19b67b6dd8a19a0163aa1f8a5a7ab"]
        or candidate["proposed_verification"]
        != ["fixture content equals UTF-8 after newline"]
        or candidate["acceptance_criteria_ids"] != [_CRITERION_ID]
        or candidate["rationale"]
        != "direct Context Pack evidence identifies the fixture item and its snapshot hash"
        or not isinstance(candidate["confidence"], float)
        or candidate["confidence"] != 1.0
        or candidate["confidence_basis"] != "DIRECT"
        or candidate["dependencies"] != []
        or candidate["risk_notes"] != []
    ):
        raise VerticalFlowError("WORK_ACTION_IDENTITY_INVALID")
    return candidate


def _validate_write_authority(authority: Mapping[str, object], resource_ref: str) -> None:
    if authority["write_scope"] == "PROJECT":
        return
    if (
        authority["write_scope"] != "NAMED_RESOURCES"
        or resource_ref not in authority["write_resources"]
    ):
        raise VerticalFlowError("WORK_WRITE_AUTHORITY_DENIED")


def _is_protected(resource_ref: str, protected_resources: object) -> bool:
    if not isinstance(protected_resources, list) or any(
        not isinstance(item, str) for item in protected_resources
    ):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    for protected in protected_resources:
        if protected == resource_ref:
            return True
        if protected == ".git/**" and (
            resource_ref == ".git" or resource_ref.startswith(".git/")
        ):
            return True
        if protected == ".env.*" and resource_ref.startswith(".env."):
            return True
    return False


def contained_workspace_target(workspace_root: object, resource_ref: object) -> Path:
    """Resolve an existing target and reject every lexical or resolved escape."""
    try:
        canonical = canonical_resource_ref(resource_ref)
    except VerticalFlowError as exc:
        raise VerticalFlowError("WORK_ACTION_IDENTITY_INVALID") from exc
    try:
        root = Path(workspace_root).resolve(strict=True)
    except (OSError, TypeError) as exc:
        raise VerticalFlowError("WORK_WORKSPACE_INVALID") from exc
    if not root.is_dir():
        raise VerticalFlowError("WORK_WORKSPACE_INVALID")
    lexical_target = root.joinpath(*PurePosixPath(canonical).parts)
    try:
        target = lexical_target.resolve(strict=True)
    except OSError as exc:
        raise VerticalFlowError("WORK_TARGET_INVALID") from exc
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise VerticalFlowError("WORK_TARGET_ESCAPE") from exc
    if not target.is_file():
        raise VerticalFlowError("WORK_TARGET_INVALID")
    return target


def reject_source_target(target: Path, source_root: object) -> None:
    try:
        source = Path(source_root).resolve(strict=True)
    except (OSError, TypeError) as exc:
        raise VerticalFlowError("WORK_SOURCE_ROOT_INVALID") from exc
    if not source.is_dir():
        raise VerticalFlowError("WORK_SOURCE_ROOT_INVALID")
    try:
        target.relative_to(source)
    except ValueError:
        return
    raise VerticalFlowError("WORK_SOURCE_TARGET_FORBIDDEN")


def _validate_result_context(context: TrustedExecutionContext) -> None:
    criteria = thaw_json(context.acceptance_criteria)
    if (
        context.candidate_evidence_floor != "E2"
        or criteria != [{"criterion_id": _CRITERION_ID, "evidence_floor": "E2"}]
        or context.human_review_result is not None
    ):
        raise VerticalFlowError("WORK_CONTEXT_INVALID")


def _capture_fresh_observed_at(
    context: TrustedExecutionContext, clock: object
) -> str:
    if not callable(clock):
        raise VerticalFlowError("WORK_OBSERVED_AT_INVALID")
    observed_at = clock()
    observed_time = require_strict_utc(
        observed_at, code="WORK_OBSERVED_AT_INVALID"
    )
    validation_time = require_strict_utc(
        context.validation_at, code="WORK_VALIDATION_AT_INVALID"
    )
    age_seconds = (observed_time - validation_time).total_seconds()
    if not 0 <= age_seconds <= 300:
        raise VerticalFlowError("WORK_EVIDENCE_FRESHNESS_INVALID")
    return observed_at


def _atomic_replace(target: Path, content: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def execute_fixture_update(
    task: Mapping[str, object],
    candidate: Mapping[str, object],
    target: Path,
    context: TrustedExecutionContext,
    observed_at: str,
) -> dict[str, object]:
    if target.read_bytes() != _BEFORE:
        raise VerticalFlowError("WORK_PRECONDITION_FAILED")
    _atomic_replace(target, _AFTER)
    if target.read_bytes() != _AFTER:
        raise VerticalFlowError("WORK_VERIFICATION_FAILED")
    evidence_id = "EVID-WORK-FIXTURE-TEST"
    evidence = {
        "id": evidence_id,
        "tier": "E2",
        "type": "test",
        "source": _RESOURCE_REF,
        "observation": "fixture workspace content equals exact UTF-8 after newline",
        "observed_at": observed_at,
    }
    return {
        "protocol_version": "2.0",
        "packet_type": "work_result",
        "task_id": task["task_id"],
        "correlation_id": task["correlation_id"],
        "base_revision": context.current_revision,
        "actor": "work",
        "status": "SUCCEEDED",
        "payload": {
            "approved_candidate_ids": list(context.approved_candidate_ids),
            "candidate_results": [
                {
                    "candidate_id": candidate["candidate_id"],
                    "action_type": candidate["action_type"],
                    "action_identity": dict(candidate["action_identity"]),
                    "decision": "ACCEPTED",
                    "reason": "current evidence and exact authority support the bounded fixture update",
                    "evidence_refs": [evidence_id],
                }
            ],
            "changed_resources": [
                {
                    "resource_ref": _RESOURCE_REF,
                    "operation": "update",
                    "scope": "verifier-owned fixture workspace",
                }
            ],
            "acceptance_results": [
                {
                    "criterion_id": _CRITERION_ID,
                    "status": "PASSED",
                    "evidence_refs": [evidence_id],
                    "notes": "exact fixture bytes were verified after atomic replacement",
                }
            ],
            "evidence": [evidence],
            "validation_summary": {"passed": 1, "failed": 0, "not_run": 0},
            "residual_risks": [],
            "compensation_options": [],
            "assertion_suggestions": [],
            "event_suggestions": [
                {
                    "actor": "work",
                    "phase": "VERIFY",
                    "code": "WORK_VERIFICATION_PASSED",
                }
            ],
            "proposed_transition": "SUCCEEDED",
        },
    }


def preflight_execute_verify(
    context: object, *, workspace_root: object, source_root: object, clock: object
) -> dict[str, object]:
    """Preflight, atomically update, and verify the one approved W6 fixture action."""
    validate_main_issued_context(context)
    task = thaw_json(context.task_packet)
    candidate_packet = thaw_json(context.candidate_packet)
    validate_work_task(task, context.current_revision)
    require_exact_authority(task, context)
    candidates = validate_approved_coverage(candidate_packet, context)
    if len(candidates) != 1:
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID")
    candidate = validate_action_identity(candidates[0])
    authority = validate_authority(thaw_json(context.authority))
    resource_ref = candidate["action_identity"]["resource_ref"]
    _validate_write_authority(authority, resource_ref)
    project_profile = task["payload"]["project_profile"]
    if not isinstance(project_profile, dict) or project_profile.get("root") != ".":
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    if _is_protected(resource_ref, project_profile.get("protected_resources")):
        raise VerticalFlowError("WORK_PROTECTED_RESOURCE_DENIED")
    _validate_result_context(context)
    observed_at = _capture_fresh_observed_at(context, clock)
    target = contained_workspace_target(workspace_root, resource_ref)
    reject_source_target(target, source_root)
    return execute_fixture_update(
        task, candidate, target, context, observed_at
    )
