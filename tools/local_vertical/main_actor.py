"""Main-owned Product Contract normalization and actor routing."""

from __future__ import annotations

import copy
import hmac
import weakref
from collections.abc import Mapping

from jsonschema import Draft202012Validator

from tools.contract_bridge.verify import BridgeError, canonical_sha256, validate_and_map
from tools.local_vertical.common import (
    TrustedExecutionContext,
    VerticalFlowError,
    canonical_resource_ref,
    freeze_json,
    require_id,
    require_strict_utc,
    thaw_json,
    validate_authority,
)


_CAPABILITY_KEYS = (
    "filesystem_read",
    "filesystem_write",
    "command_execute",
    "delegation",
    "network",
    "external_side_effects",
)
_CAPABILITY_VALUES = {
    "filesystem_read": frozenset({"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}),
    "filesystem_write": frozenset({"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}),
    "command_execute": frozenset({"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}),
    "delegation": frozenset({"NONE", "SEQUENTIAL", "PARALLEL", "UNKNOWN"}),
    "network": frozenset({"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}),
    "external_side_effects": frozenset({"AVAILABLE", "UNAVAILABLE", "UNKNOWN"}),
}
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
_CANDIDATE_PACKET_FIELDS = frozenset(
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
_CANDIDATE_PAYLOAD_FIELDS = frozenset(
    {
        "outcome_code",
        "task_breakdown",
        "evidence",
        "candidates",
        "unknowns",
        "assertion_suggestions",
        "event_suggestions",
        "proposed_transition",
    }
)
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
_PART_EVIDENCE_FIELDS = frozenset(
    {"id", "tier", "type", "source", "observation", "observed_revision"}
)
_EVIDENCE_TIERS = frozenset({"E0", "E1", "E2", "E3"})
_TRUSTED_CONTEXT_FIELDS = (
    "task_packet",
    "candidate_packet",
    "current_revision",
    "approved_candidate_ids",
    "approved_candidates",
    "authority",
    "candidate_evidence_floor",
    "acceptance_criteria",
    "validation_at",
    "human_review_result",
)
_ISSUED_CONTEXT_DIGESTS: weakref.WeakKeyDictionary[TrustedExecutionContext, str] = (
    weakref.WeakKeyDictionary()
)


def _copy_mapping(value: object, *, code: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise VerticalFlowError(code)
    return copy.deepcopy(dict(value))


def normalize_request(request: object) -> dict[str, object]:
    normalized = _copy_mapping(request, code="MAIN_REQUEST_INVALID")
    normalized.setdefault("assumptions", [])
    return normalized


def normalize_project_profile(project_profile: object) -> dict[str, object]:
    normalized = _copy_mapping(project_profile, code="MAIN_PROJECT_PROFILE_INVALID")
    normalized.setdefault("instruction_files", [])
    normalized.setdefault("validation_commands", [])
    normalized.setdefault("extensions", {})
    return normalized


def normalize_capabilities(capabilities: object) -> dict[str, object]:
    if not isinstance(capabilities, Mapping):
        return {key: "UNKNOWN" for key in _CAPABILITY_KEYS}
    return {
        key: capabilities[key]
        if capabilities.get(key) in _CAPABILITY_VALUES[key]
        else "UNKNOWN"
        for key in _CAPABILITY_KEYS
    }


def normalize_control(
    control: object, *, route: str, operation_mode: str
) -> dict[str, object]:
    normalized = _copy_mapping(control, code="MAIN_CONTROL_INVALID")
    normalized["route"] = route
    normalized["operation_mode"] = operation_mode
    return normalized


def normalize_budgets(budgets: object) -> dict[str, object]:
    return _copy_mapping(budgets, code="MAIN_BUDGETS_INVALID")


def normalize_product_task(
    contract: object,
    bridge_context: object,
    product_schema: object,
    *,
    correlation_id: object,
) -> dict[str, object]:
    """Map a Product Contract through W1 into a canonical Main TaskPacket."""
    if not isinstance(contract, dict) or not isinstance(bridge_context, dict):
        raise VerticalFlowError("MAIN_BRIDGE_INPUT_INVALID")
    if not isinstance(product_schema, dict):
        raise VerticalFlowError("MAIN_PRODUCT_SCHEMA_INVALID")
    validator = Draft202012Validator(copy.deepcopy(product_schema))
    try:
        mapped = validate_and_map(
            copy.deepcopy(contract),
            copy.deepcopy(bridge_context),
            validator,
            canonical_sha256(contract),
        )
    except BridgeError as exc:
        raise VerticalFlowError(f"MAIN_{exc.code}") from exc

    payload = {
        "request": normalize_request(mapped["request"]),
        "project_profile": normalize_project_profile(mapped["project_profile"]),
        "capabilities": normalize_capabilities(mapped["capabilities"]),
        "authority": validate_authority(mapped["authority"]),
        "control": normalize_control(
            mapped["control"], route="PART_THEN_WORK", operation_mode="EXPLORE"
        ),
        "budgets": normalize_budgets(mapped["budgets"]),
    }
    accepted_state = _copy_mapping(mapped["accepted_state"], code="MAIN_ACCEPTED_STATE_INVALID")
    revision = accepted_state.get("revision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        raise VerticalFlowError("MAIN_ACCEPTED_REVISION_INVALID")
    return {
        "protocol_version": "2.0",
        "packet_type": "task",
        "task_id": require_id(mapped["task_id"], code="MAIN_TASK_ID_INVALID"),
        "correlation_id": require_id(correlation_id, code="CORRELATION_ID_INVALID"),
        "base_revision": revision,
        "actor": "main",
        "status": "IN_PROGRESS",
        "payload": payload,
    }


def build_part_task(task_packet: object) -> dict[str, object]:
    """Return an isolated Main TaskPacket restricted to Part exploration."""
    if not isinstance(task_packet, Mapping):
        raise VerticalFlowError("MAIN_TASK_PACKET_INVALID")
    task = copy.deepcopy(dict(task_packet))
    try:
        control = task["payload"]["control"]
    except (KeyError, TypeError) as exc:
        raise VerticalFlowError("MAIN_TASK_PACKET_INVALID") from exc
    if not isinstance(control, dict):
        raise VerticalFlowError("MAIN_TASK_PACKET_INVALID")
    control["route"] = "PART_THEN_WORK"
    control["operation_mode"] = "EXPLORE"
    return task


def _trusted_context_digest(context: TrustedExecutionContext) -> str:
    try:
        values = {
            name: thaw_json(getattr(context, name)) for name in _TRUSTED_CONTEXT_FIELDS
        }
        return canonical_sha256(values)
    except (AttributeError, BridgeError, VerticalFlowError, TypeError, ValueError) as exc:
        raise VerticalFlowError("WORK_CONTEXT_PROVENANCE_INVALID") from exc


def validate_main_issued_context(context: object) -> None:
    """Fail closed unless this exact immutable object was issued unchanged by Main."""
    if not isinstance(context, TrustedExecutionContext):
        raise VerticalFlowError("WORK_CONTEXT_PROVENANCE_INVALID")
    issued_digest = _ISSUED_CONTEXT_DIGESTS.get(context)
    if issued_digest is None:
        raise VerticalFlowError("WORK_CONTEXT_PROVENANCE_INVALID")
    observed_digest = _trusted_context_digest(context)
    if not hmac.compare_digest(issued_digest, observed_digest):
        raise VerticalFlowError("WORK_CONTEXT_PROVENANCE_INVALID")


def _require_work_approval_task(task_packet: object) -> dict[str, object]:
    if not isinstance(task_packet, Mapping):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    task = copy.deepcopy(dict(task_packet))
    if set(task) != _TASK_FIELDS:
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    if (
        task["protocol_version"] != "2.0"
        or task["packet_type"] != "task"
        or task["actor"] != "main"
        or task["status"] != "IN_PROGRESS"
        or isinstance(task["base_revision"], bool)
        or not isinstance(task["base_revision"], int)
        or task["base_revision"] < 0
    ):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    try:
        require_id(task["task_id"], code="WORK_ENVELOPE_INVALID")
        require_id(task["correlation_id"], code="WORK_ENVELOPE_INVALID")
    except VerticalFlowError as exc:
        raise VerticalFlowError("WORK_ENVELOPE_INVALID") from exc
    payload = task["payload"]
    if not isinstance(payload, dict) or set(payload) != _TASK_PAYLOAD_FIELDS:
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    control = payload["control"]
    if (
        not isinstance(control, dict)
        or control.get("route") != "PART_THEN_WORK"
        or control.get("operation_mode") != "EXPLORE"
    ):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    return task


def _contains_owned_candidate_state(value: object) -> bool:
    if isinstance(value, dict):
        if any(field in value for field in ("accepted_state", "revision", "events", "seq")):
            return True
        return any(_contains_owned_candidate_state(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_owned_candidate_state(child) for child in value)
    return False


def _validate_part_evidence(payload: Mapping[str, object], current_revision: int) -> set[str]:
    evidence = payload.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise VerticalFlowError("WORK_CANDIDATE_EVIDENCE_INVALID")
    evidence_ids: list[str] = []
    for record in evidence:
        if not isinstance(record, dict) or set(record) != _PART_EVIDENCE_FIELDS:
            raise VerticalFlowError("WORK_CANDIDATE_EVIDENCE_INVALID")
        try:
            evidence_ids.append(
                require_id(record["id"], code="WORK_CANDIDATE_EVIDENCE_INVALID")
            )
        except VerticalFlowError as exc:
            raise VerticalFlowError("WORK_CANDIDATE_EVIDENCE_INVALID") from exc
        if (
            record["id"] != "EVID-PART-CONTEXT"
            or record["tier"] != "E1"
            or record["type"] != "file"
            or record["source"] != "fixture/work-item.txt"
            or record["observation"]
            != "exact W5 Context Pack item matched the snapshot manifest"
        ):
            raise VerticalFlowError("WORK_CANDIDATE_PACKET_INVALID")
        if record["observed_revision"] != current_revision or isinstance(
            record["observed_revision"], bool
        ):
            raise VerticalFlowError("WORK_CANDIDATE_EVIDENCE_INVALID")
    if len(evidence_ids) != len(set(evidence_ids)):
        raise VerticalFlowError("WORK_CANDIDATE_EVIDENCE_INVALID")
    return set(evidence_ids)


def _validate_part_packet_metadata(
    payload: Mapping[str, object], criterion_ids: list[str]
) -> None:
    if (
        payload.get("task_breakdown")
        != [
            {
                "unit_id": "UNIT-W6-UPDATE",
                "objective": "replace fixture marker before with after",
                "acceptance_criteria_ids": criterion_ids,
                "dependencies": [],
            }
        ]
        or payload.get("unknowns") != []
        or payload.get("assertion_suggestions") != []
        or payload.get("event_suggestions")
        != [
            {
                "actor": "part",
                "phase": "DISCOVER",
                "code": "PART_CANDIDATE_PROPOSED",
            }
        ]
        or payload.get("proposed_transition") != "IN_PROGRESS"
    ):
        raise VerticalFlowError("WORK_CANDIDATE_PACKET_INVALID")


def _validate_approved_candidate(
    candidate: object,
    *,
    evidence_ids: set[str],
    criterion_ids: list[str],
    authority: Mapping[str, object],
    protected_resources: object,
) -> dict[str, object]:
    if not isinstance(candidate, dict) or set(candidate) != _CANDIDATE_FIELDS:
        raise VerticalFlowError("WORK_ACTION_IDENTITY_INVALID")
    try:
        require_id(candidate["candidate_id"], code="WORK_APPROVED_ID_INVALID")
    except VerticalFlowError as exc:
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID") from exc
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
    if resource_ref != "fixture/work-item.txt":
        raise VerticalFlowError("WORK_ACTION_IDENTITY_INVALID")
    refs = candidate["evidence_refs"]
    if (
        not isinstance(refs, list)
        or not refs
        or any(not isinstance(ref, str) or not ref for ref in refs)
        or len(refs) != len(set(refs))
        or any(ref not in evidence_ids for ref in refs)
    ):
        raise VerticalFlowError("WORK_CANDIDATE_EVIDENCE_INVALID")
    if candidate["acceptance_criteria_ids"] != criterion_ids:
        raise VerticalFlowError("WORK_CANDIDATE_CRITERIA_INVALID")
    if (
        candidate["expected_effect"] != "replace fixture marker before with after"
        or candidate["preconditions"]
        != ["sha256:c0cde77fa8fef97d3b55e18e9a5f8f08c4f19b67b6dd8a19a0163aa1f8a5a7ab"]
        or candidate["proposed_verification"]
        != ["fixture content equals UTF-8 after newline"]
    ):
        raise VerticalFlowError("WORK_ACTION_IDENTITY_INVALID")
    if authority["write_scope"] == "PROJECT":
        pass
    elif (
        authority["write_scope"] != "NAMED_RESOURCES"
        or resource_ref not in authority["write_resources"]
    ):
        raise VerticalFlowError("WORK_WRITE_AUTHORITY_DENIED")
    if not isinstance(protected_resources, list) or any(
        not isinstance(item, str) for item in protected_resources
    ):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    if resource_ref in protected_resources:
        raise VerticalFlowError("WORK_PROTECTED_RESOURCE_DENIED")
    if ".git/**" in protected_resources and (
        resource_ref == ".git" or resource_ref.startswith(".git/")
    ):
        raise VerticalFlowError("WORK_PROTECTED_RESOURCE_DENIED")
    return candidate


def approve_candidates(
    task_packet: object,
    candidate_packet: object,
    *,
    approved_candidate_ids: object,
    validation_at: object,
    human_review_result: object | None,
) -> TrustedExecutionContext:
    """Bind Main-approved Part output into an immutable Work-only context."""
    task = _require_work_approval_task(task_packet)
    require_strict_utc(validation_at, code="MAIN_VALIDATION_AT_INVALID")
    authority = validate_authority(task["payload"]["authority"])
    evidence_floor = task["payload"]["control"].get("evidence_floor")
    if evidence_floor not in _EVIDENCE_TIERS:
        raise VerticalFlowError("WORK_EVIDENCE_FLOOR_INVALID")
    request = task["payload"]["request"]
    raw_criteria = request.get("acceptance_criteria") if isinstance(request, dict) else None
    if not isinstance(raw_criteria, list) or not raw_criteria:
        raise VerticalFlowError("WORK_CANDIDATE_CRITERIA_INVALID")
    criterion_ids: list[str] = []
    for criterion in raw_criteria:
        if not isinstance(criterion, dict) or set(criterion) != {"id", "statement"}:
            raise VerticalFlowError("WORK_CANDIDATE_CRITERIA_INVALID")
        try:
            criterion_ids.append(
                require_id(criterion["id"], code="WORK_CANDIDATE_CRITERIA_INVALID")
            )
        except VerticalFlowError as exc:
            raise VerticalFlowError("WORK_CANDIDATE_CRITERIA_INVALID") from exc
    if len(criterion_ids) != len(set(criterion_ids)):
        raise VerticalFlowError("WORK_CANDIDATE_CRITERIA_INVALID")

    if not isinstance(candidate_packet, Mapping):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    packet = copy.deepcopy(dict(candidate_packet))
    if set(packet) != _CANDIDATE_PACKET_FIELDS:
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    if (
        packet["protocol_version"] != "2.0"
        or packet["packet_type"] != "candidate_proposal"
        or packet["actor"] != "part"
        or packet["status"] != "IN_PROGRESS"
        or packet["task_id"] != task["task_id"]
        or packet["correlation_id"] != task["correlation_id"]
        or packet["base_revision"] != task["base_revision"]
        or isinstance(packet["base_revision"], bool)
    ):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    payload = packet["payload"]
    if not isinstance(payload, dict):
        raise VerticalFlowError("WORK_ENVELOPE_INVALID")
    if "approved_candidate_ids" in payload:
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID")
    if "validationAt" in payload or "validation_at" in payload:
        raise VerticalFlowError("WORK_VALIDATION_AT_UNTRUSTED")
    if _contains_owned_candidate_state(payload):
        raise VerticalFlowError("WORK_STATE_OWNERSHIP_FORBIDDEN")
    if set(payload) != _CANDIDATE_PAYLOAD_FIELDS:
        raise VerticalFlowError("WORK_CANDIDATE_PACKET_INVALID")
    if payload["outcome_code"] != "CANDIDATES_PROPOSED":
        raise VerticalFlowError("WORK_CANDIDATE_PACKET_INVALID")
    _validate_part_packet_metadata(payload, criterion_ids)
    evidence_ids = _validate_part_evidence(payload, task["base_revision"])
    candidates = payload["candidates"]
    if not isinstance(candidates, list) or not candidates:
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID")
    validated_candidates = [
        _validate_approved_candidate(
            candidate,
            evidence_ids=evidence_ids,
            criterion_ids=criterion_ids,
            authority=authority,
            protected_resources=task["payload"]["project_profile"].get(
                "protected_resources"
            )
            if isinstance(task["payload"]["project_profile"], dict)
            else None,
        )
        for candidate in candidates
    ]
    candidate_ids = [candidate["candidate_id"] for candidate in validated_candidates]
    if len(candidate_ids) != len(set(candidate_ids)):
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID")
    if (
        not isinstance(approved_candidate_ids, list)
        or any(not isinstance(candidate_id, str) for candidate_id in approved_candidate_ids)
        or len(approved_candidate_ids) != len(set(approved_candidate_ids))
        or approved_candidate_ids != candidate_ids
    ):
        raise VerticalFlowError("WORK_APPROVED_ID_INVALID")

    work_task = copy.deepcopy(task)
    work_task["payload"]["control"]["route"] = "WORK_ONLY"
    work_task["payload"]["control"]["operation_mode"] = "EXECUTE"
    acceptance_criteria = [
        {"criterion_id": criterion_id, "evidence_floor": evidence_floor}
        for criterion_id in criterion_ids
    ]
    issued_values = {
        "task_packet": work_task,
        "candidate_packet": packet,
        "current_revision": task["base_revision"],
        "approved_candidate_ids": approved_candidate_ids,
        "approved_candidates": validated_candidates,
        "authority": authority,
        "candidate_evidence_floor": evidence_floor,
        "acceptance_criteria": acceptance_criteria,
        "validation_at": validation_at,
        "human_review_result": human_review_result,
    }
    context = object.__new__(TrustedExecutionContext)
    for name in _TRUSTED_CONTEXT_FIELDS:
        object.__setattr__(context, name, freeze_json(issued_values[name]))
    _ISSUED_CONTEXT_DIGESTS[context] = _trusted_context_digest(context)
    return context


_WORK_RESULT_FIELDS = _TASK_FIELDS
_WORK_PAYLOAD_FIELDS = frozenset(
    {
        "approved_candidate_ids",
        "candidate_results",
        "changed_resources",
        "acceptance_results",
        "evidence",
        "validation_summary",
        "residual_risks",
        "compensation_options",
        "assertion_suggestions",
        "event_suggestions",
        "proposed_transition",
    }
)
_CANDIDATE_RESULT_FIELDS = frozenset(
    {
        "candidate_id",
        "action_type",
        "action_identity",
        "decision",
        "reason",
        "evidence_refs",
    }
)
_ACCEPTANCE_RESULT_FIELDS = frozenset(
    {"criterion_id", "status", "evidence_refs", "notes"}
)
_EVIDENCE_BASE_FIELDS = frozenset(
    {"id", "tier", "type", "source", "observation"}
)
_ACCEPTED_STATE_FIELDS = frozenset(
    {"task_id", "correlation_id", "revision", "status", "next_seq"}
)
_EVENT_FIELDS = frozenset({"actor", "phase", "code"})
_TIME_EVIDENCE_TYPES = frozenset({"command", "test", "render", "runtime", "approval"})
_REVISION_EVIDENCE_TYPES = frozenset({"file", "diff"})
_TIER_RANK = {"E0": 0, "E1": 1, "E2": 2, "E3": 3}


def _accepted_state_copy(
    accepted_state: object, *, task_id: object, correlation_id: object
) -> dict[str, object]:
    if not isinstance(accepted_state, Mapping):
        raise VerticalFlowError("MAIN_ACCEPTED_STATE_INVALID")
    state = copy.deepcopy(dict(accepted_state))
    if (
        set(state) != _ACCEPTED_STATE_FIELDS
        or state.get("task_id") != task_id
        or state.get("correlation_id") != correlation_id
        or state.get("status") != "IN_PROGRESS"
        or isinstance(state.get("revision"), bool)
        or not isinstance(state.get("revision"), int)
        or state["revision"] < 0
        or isinstance(state.get("next_seq"), bool)
        or not isinstance(state.get("next_seq"), int)
        or state["next_seq"] < 1
    ):
        raise VerticalFlowError("MAIN_ACCEPTED_STATE_INVALID")
    return state


def _contains_authoritative_output(value: object) -> bool:
    if isinstance(value, dict):
        if any(name in value for name in ("accepted_state", "revision", "events", "seq")):
            return True
        return any(_contains_authoritative_output(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_authoritative_output(child) for child in value)
    return False


def _require_raw_array(payload: Mapping[str, object], name: str, code: str) -> list[object]:
    value = payload.get(name)
    if not isinstance(value, list):
        raise VerticalFlowError(code)
    return value


def _require_unique_refs(refs: object, *, known: set[str] | None = None) -> list[str]:
    if (
        not isinstance(refs, list)
        or not refs
        or any(not isinstance(ref, str) or not ref for ref in refs)
        or len(refs) != len(set(refs))
        or (known is not None and any(ref not in known for ref in refs))
    ):
        raise VerticalFlowError("MAIN_EVIDENCE_REFERENCE_INVALID")
    return refs


def _normalize_event(suggestion: object) -> dict[str, object]:
    if (
        not isinstance(suggestion, dict)
        or set(suggestion) != _EVENT_FIELDS
        or suggestion.get("actor") not in {"part", "work"}
        or not all(isinstance(suggestion.get(name), str) and suggestion[name] for name in _EVENT_FIELDS)
    ):
        raise VerticalFlowError("MAIN_EVENT_SUGGESTION_INVALID")
    return copy.deepcopy(suggestion)


def _main_decision(
    source_packet: Mapping[str, object],
    state: Mapping[str, object],
    *,
    decision: str,
    status: str,
    event_suggestions: list[object],
    acceptance_results: list[object],
    unresolved_risks: list[object],
) -> dict[str, object]:
    events: list[dict[str, object]] = []
    for offset, suggestion in enumerate(event_suggestions):
        event = _normalize_event(suggestion)
        event["seq"] = state["next_seq"] + offset
        events.append(event)
    accepted_payload_ref = "sha256:" + canonical_sha256(source_packet)
    accepted = {
        "task_id": state["task_id"],
        "correlation_id": state["correlation_id"],
        "revision": state["revision"] + 1,
        "status": status,
        "next_seq": state["next_seq"] + len(events),
        "checkpoint_ref": None,
        "accepted_payload_ref": accepted_payload_ref,
        "acceptance_results": copy.deepcopy(acceptance_results),
        "unresolved_risks": copy.deepcopy(unresolved_risks),
    }
    return {
        "protocol_version": "2.0",
        "packet_type": "main_decision",
        "task_id": state["task_id"],
        "correlation_id": state["correlation_id"],
        "base_revision": state["revision"],
        "actor": "main",
        "status": status,
        "payload": {
            "decision": decision,
            "accepted_state": accepted,
            "assertions": {"status": "PASSED", "violations": []},
            "events": events,
            "user_response": "local vertical transition accepted",
        },
    }


def validate_and_decide(
    work_result: object,
    context: object,
    accepted_state: object,
) -> dict[str, object]:
    """Accept one complete, fresh WorkResult and assign authoritative state once."""
    validate_main_issued_context(context)
    if not isinstance(context, TrustedExecutionContext):
        raise VerticalFlowError("WORK_CONTEXT_PROVENANCE_INVALID")
    task = thaw_json(context.task_packet)
    candidate_packet = thaw_json(context.candidate_packet)
    if not isinstance(work_result, Mapping):
        raise VerticalFlowError("MAIN_WORK_ENVELOPE_INVALID")
    result = copy.deepcopy(dict(work_result))
    if set(result) != _WORK_RESULT_FIELDS:
        raise VerticalFlowError("MAIN_WORK_ENVELOPE_INVALID")
    if (
        result.get("protocol_version") != "2.0"
        or result.get("packet_type") != "work_result"
        or result.get("actor") != "work"
    ):
        raise VerticalFlowError("MAIN_WORK_ENVELOPE_INVALID")
    if (
        result.get("task_id") != task["task_id"]
        or result.get("correlation_id") != task["correlation_id"]
    ):
        raise VerticalFlowError("MAIN_WORK_IDENTITY_INVALID")
    state = _accepted_state_copy(
        accepted_state,
        task_id=result["task_id"],
        correlation_id=result["correlation_id"],
    )
    if (
        isinstance(result.get("base_revision"), bool)
        or result.get("base_revision") != state["revision"]
        or result.get("base_revision") != context.current_revision
    ):
        raise VerticalFlowError("MAIN_WORK_REVISION_STALE")
    if result.get("status") != "SUCCEEDED":
        raise VerticalFlowError("MAIN_WORK_STATUS_INVALID")
    payload = result.get("payload")
    if not isinstance(payload, dict):
        raise VerticalFlowError("MAIN_WORK_PAYLOAD_INVALID")
    forbidden_ownership = {"accepted_state", "revision", "events", "seq"}
    if set(payload) - (_WORK_PAYLOAD_FIELDS | forbidden_ownership):
        raise VerticalFlowError("MAIN_WORK_PAYLOAD_INVALID")
    if not _WORK_PAYLOAD_FIELDS.issubset(payload):
        raise VerticalFlowError("MAIN_WORK_PAYLOAD_INVALID")
    if payload.get("proposed_transition") != "SUCCEEDED":
        raise VerticalFlowError("MAIN_WORK_TRANSITION_INVALID")

    approved_ids = _require_raw_array(payload, "approved_candidate_ids", "MAIN_CANDIDATE_COVERAGE_INVALID")
    candidate_results = _require_raw_array(payload, "candidate_results", "MAIN_CANDIDATE_COVERAGE_INVALID")
    changed_resources = _require_raw_array(payload, "changed_resources", "MAIN_WORK_PAYLOAD_INVALID")
    acceptance_results = _require_raw_array(payload, "acceptance_results", "MAIN_CRITERION_COVERAGE_INVALID")
    evidence = _require_raw_array(payload, "evidence", "MAIN_EVIDENCE_CATALOG_INVALID")
    residual_risks = _require_raw_array(payload, "residual_risks", "MAIN_WORK_PAYLOAD_INVALID")
    _require_raw_array(payload, "compensation_options", "MAIN_WORK_PAYLOAD_INVALID")
    assertions = _require_raw_array(payload, "assertion_suggestions", "MAIN_WORK_PAYLOAD_INVALID")
    work_events = _require_raw_array(payload, "event_suggestions", "MAIN_EVENT_SUGGESTION_INVALID")

    expected_ids = list(context.approved_candidate_ids)
    if approved_ids != expected_ids or len(approved_ids) != len(set(approved_ids)):
        raise VerticalFlowError("MAIN_CANDIDATE_COVERAGE_INVALID")
    if len(candidate_results) != len(expected_ids):
        raise VerticalFlowError("MAIN_CANDIDATE_COVERAGE_INVALID")
    candidate_refs: list[list[str]] = []
    for expected_id, record in zip(expected_ids, candidate_results):
        if (
            not isinstance(record, dict)
            or set(record) != _CANDIDATE_RESULT_FIELDS
            or record.get("candidate_id") != expected_id
            or record.get("decision") != "ACCEPTED"
        ):
            raise VerticalFlowError("MAIN_CANDIDATE_COVERAGE_INVALID")
        candidate_refs.append(_require_unique_refs(record.get("evidence_refs")))

    expected_criteria = [item["criterion_id"] for item in thaw_json(context.acceptance_criteria)]
    if len(acceptance_results) != len(expected_criteria):
        raise VerticalFlowError("MAIN_CRITERION_COVERAGE_INVALID")
    criterion_refs: list[list[str]] = []
    for expected_id, record in zip(expected_criteria, acceptance_results):
        if (
            not isinstance(record, dict)
            or set(record) != _ACCEPTANCE_RESULT_FIELDS
            or record.get("criterion_id") != expected_id
            or record.get("status") != "PASSED"
        ):
            raise VerticalFlowError("MAIN_CRITERION_COVERAGE_INVALID")
        criterion_refs.append(_require_unique_refs(record.get("evidence_refs")))

    evidence_ids: list[str] = []
    validation_time = require_strict_utc(
        context.validation_at, code="MAIN_EVIDENCE_FRESHNESS_INVALID"
    )
    for record in evidence:
        if not isinstance(record, dict):
            raise VerticalFlowError("MAIN_EVIDENCE_CATALOG_INVALID")
        evidence_type = record.get("type")
        expected_fields = set(_EVIDENCE_BASE_FIELDS)
        if evidence_type in _TIME_EVIDENCE_TYPES:
            expected_fields.add("observed_at")
            if evidence_type == "command":
                expected_fields.add("exit_code")
        elif evidence_type in _REVISION_EVIDENCE_TYPES:
            expected_fields.add("observed_revision")
        else:
            raise VerticalFlowError("MAIN_EVIDENCE_FRESHNESS_INVALID")
        # W6 Work currently carries exit_code on test evidence; tolerate it as a
        # legacy local adapter field while all freshness semantics remain closed.
        if evidence_type == "test" and "exit_code" in record:
            expected_fields.add("exit_code")
        if set(record) != expected_fields:
            raise VerticalFlowError("MAIN_EVIDENCE_FRESHNESS_INVALID")
        try:
            evidence_ids.append(require_id(record["id"], code="MAIN_EVIDENCE_CATALOG_INVALID"))
        except VerticalFlowError as exc:
            raise VerticalFlowError("MAIN_EVIDENCE_CATALOG_INVALID") from exc
        tier = record.get("tier")
        if not isinstance(tier, str) or _TIER_RANK.get(tier, -1) < _TIER_RANK[context.candidate_evidence_floor]:
            raise VerticalFlowError("MAIN_EVIDENCE_TIER_INVALID")
        if evidence_type in _TIME_EVIDENCE_TYPES:
            observed = require_strict_utc(
                record.get("observed_at"), code="MAIN_EVIDENCE_FRESHNESS_INVALID"
            )
            age = (observed - validation_time).total_seconds()
            if not 0 <= age <= 300:
                raise VerticalFlowError("MAIN_EVIDENCE_FRESHNESS_INVALID")
        else:
            observed_revision = record.get("observed_revision")
            if isinstance(observed_revision, bool) or observed_revision != context.current_revision:
                raise VerticalFlowError("MAIN_EVIDENCE_FRESHNESS_INVALID")
    if not evidence_ids or len(evidence_ids) != len(set(evidence_ids)):
        raise VerticalFlowError("MAIN_EVIDENCE_CATALOG_INVALID")
    known_evidence = set(evidence_ids)
    for refs in candidate_refs + criterion_refs:
        _require_unique_refs(refs, known=known_evidence)

    summary = payload.get("validation_summary")
    if (
        not isinstance(summary, dict)
        or set(summary) != {"passed", "failed", "not_run"}
        or summary != {"passed": len(acceptance_results), "failed": 0, "not_run": 0}
    ):
        raise VerticalFlowError("MAIN_SUMMARY_INVALID")
    if changed_resources != [
        {
            "resource_ref": "fixture/work-item.txt",
            "operation": "update",
            "scope": "verifier-owned fixture workspace",
        }
    ] or residual_risks != [] or assertions != [] or len(work_events) != 1:
        raise VerticalFlowError("MAIN_WORK_SUCCESS_INVALID")
    if _contains_authoritative_output(payload):
        raise VerticalFlowError("WORK_STATE_OWNERSHIP_FORBIDDEN")

    part_events = candidate_packet.get("payload", {}).get("event_suggestions")
    if not isinstance(part_events, list) or len(part_events) != 1:
        raise VerticalFlowError("MAIN_EVENT_SUGGESTION_INVALID")
    return _main_decision(
        result,
        state,
        decision="ACCEPT",
        status="SUCCEEDED",
        event_suggestions=part_events + work_events,
        acceptance_results=acceptance_results,
        unresolved_risks=residual_risks,
    )


def decide_candidate_gate(
    candidate_packet: object, accepted_state: object
) -> dict[str, object]:
    """Accept only the canonical Part blocked proposal as a human gate."""
    if not isinstance(candidate_packet, Mapping):
        raise VerticalFlowError("MAIN_GATE_PACKET_INVALID")
    packet = copy.deepcopy(dict(candidate_packet))
    if set(packet) != _CANDIDATE_PACKET_FIELDS or (
        packet.get("protocol_version") != "2.0"
        or packet.get("packet_type") != "candidate_proposal"
        or packet.get("actor") != "part"
        or packet.get("status") != "BLOCKED"
    ):
        raise VerticalFlowError("MAIN_GATE_PACKET_INVALID")
    state = _accepted_state_copy(
        accepted_state,
        task_id=packet.get("task_id"),
        correlation_id=packet.get("correlation_id"),
    )
    if packet.get("base_revision") != state["revision"]:
        raise VerticalFlowError("MAIN_WORK_REVISION_STALE")
    payload = packet.get("payload")
    expected_fields = {
        "outcome_code", "task_breakdown", "evidence", "candidates",
        "missing_authority", "recommended_next_action", "assertion_suggestions",
        "event_suggestions", "proposed_transition",
    }
    if not isinstance(payload, dict):
        raise VerticalFlowError("MAIN_GATE_PACKET_INVALID")
    forbidden_ownership = {"accepted_state", "revision", "events", "seq"}
    if (
        set(payload) - (expected_fields | forbidden_ownership)
        or not expected_fields.issubset(payload)
        or payload.get("outcome_code") != "BLOCKED_PROPOSAL"
        or payload.get("task_breakdown") != []
        or payload.get("evidence") != []
        or payload.get("candidates") != []
        or not isinstance(payload.get("missing_authority"), str)
        or not payload["missing_authority"]
        or payload.get("recommended_next_action") != "ASK_USER"
        or payload.get("assertion_suggestions") != []
        or payload.get("proposed_transition") != "WAITING_FOR_HUMAN"
        or not isinstance(payload.get("event_suggestions"), list)
        or len(payload["event_suggestions"]) != 1
    ):
        raise VerticalFlowError("MAIN_GATE_PACKET_INVALID")
    if _contains_authoritative_output(payload):
        raise VerticalFlowError("MAIN_ACTOR_OWNERSHIP_FORBIDDEN")
    return _main_decision(
        packet,
        state,
        decision="GATE",
        status="WAITING_FOR_HUMAN",
        event_suggestions=payload["event_suggestions"],
        acceptance_results=[],
        unresolved_risks=[payload["missing_authority"]],
    )
