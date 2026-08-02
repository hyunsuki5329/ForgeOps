"""Read-only Part candidate proposal for the local W6 vertical flow."""

from __future__ import annotations

from collections.abc import Mapping

from tools.local_vertical.common import (
    VerticalFlowError,
    canonical_resource_ref,
    require_id,
    validate_authority,
)


_TASK_FIELDS = frozenset(
    {"protocol_version", "packet_type", "task_id", "correlation_id", "base_revision", "actor", "status", "payload"}
)
_TASK_PAYLOAD_FIELDS = frozenset(
    {"request", "project_profile", "capabilities", "authority", "control", "budgets"}
)
_CONTEXT_FIELDS = frozenset(
    {"context_pack_version", "snapshot_id", "query_tokens", "items", "summary", "control_claims_accepted"}
)
_CONTEXT_ITEM_FIELDS = frozenset(
    {"path", "sha256", "size", "media_type", "selection_reason", "score", "excerpt", "trust"}
)
_MANIFEST_FIELDS = frozenset(
    {"snapshot_version", "snapshot_id", "source", "dirty", "entries", "deleted_paths", "manifest_sha256"}
)
_MANIFEST_ENTRY_FIELDS = frozenset({"path", "size", "sha256", "mode", "source_states"})
_HEX = frozenset("0123456789abcdef")


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _is_sha256(value: object) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in _HEX for char in value)


def _require_exact_fields(value: object, fields: frozenset[str], *, code: str) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise VerticalFlowError(code)
    return value


def validate_task_envelope(task_packet: object, *, required_mode: str) -> dict[str, object]:
    """Require a closed Main-owned TaskPacket before Part interprets it."""
    task = _require_exact_fields(task_packet, _TASK_FIELDS, code="PART_ENVELOPE_INVALID")
    if (
        task["protocol_version"] != "2.0"
        or task["packet_type"] != "task"
        or task["actor"] != "main"
        or task["status"] != "IN_PROGRESS"
        or not _is_nonnegative_int(task["base_revision"])
    ):
        raise VerticalFlowError("PART_ENVELOPE_INVALID")
    try:
        require_id(task["task_id"], code="PART_ENVELOPE_INVALID")
        require_id(task["correlation_id"], code="PART_ENVELOPE_INVALID")
    except VerticalFlowError as exc:
        raise VerticalFlowError("PART_ENVELOPE_INVALID") from exc
    payload = _require_exact_fields(task["payload"], _TASK_PAYLOAD_FIELDS, code="PART_ENVELOPE_INVALID")
    control = payload["control"]
    if not isinstance(control, dict) or control.get("route") != "PART_THEN_WORK":
        raise VerticalFlowError("PART_ROUTE_INVALID")
    if control.get("operation_mode") != required_mode:
        raise VerticalFlowError("PART_OPERATION_MODE_INVALID")
    return task


def _validate_context_item(item: object) -> dict[str, object]:
    value = _require_exact_fields(item, _CONTEXT_ITEM_FIELDS, code="PART_CONTEXT_PROVENANCE_INVALID")
    try:
        canonical_resource_ref(value["path"])
    except VerticalFlowError as exc:
        raise VerticalFlowError("PART_CONTEXT_PROVENANCE_INVALID") from exc
    if (
        not _is_sha256(value["sha256"])
        or not _is_nonnegative_int(value["size"])
        or value["trust"] != "UNTRUSTED_SOURCE"
        or not isinstance(value["selection_reason"], list)
    ):
        raise VerticalFlowError("PART_CONTEXT_PROVENANCE_INVALID")
    return value


def _validate_manifest_entry(entry: object) -> dict[str, object]:
    value = _require_exact_fields(entry, _MANIFEST_ENTRY_FIELDS, code="PART_CONTEXT_PROVENANCE_INVALID")
    try:
        canonical_resource_ref(value["path"])
    except VerticalFlowError as exc:
        raise VerticalFlowError("PART_CONTEXT_PROVENANCE_INVALID") from exc
    if not _is_sha256(value["sha256"]) or not _is_nonnegative_int(value["size"]):
        raise VerticalFlowError("PART_CONTEXT_PROVENANCE_INVALID")
    return value


def validate_snapshot_context(snapshot_manifest: object, context_pack: object) -> None:
    """Bind untrusted W5 excerpts exactly to the passed snapshot manifest."""
    manifest = _require_exact_fields(snapshot_manifest, _MANIFEST_FIELDS, code="PART_CONTEXT_PROVENANCE_INVALID")
    context = _require_exact_fields(context_pack, _CONTEXT_FIELDS, code="PART_CONTEXT_PROVENANCE_INVALID")
    if (
        manifest["snapshot_version"] != "1.0"
        or context["context_pack_version"] != "1.0"
        or not isinstance(manifest["snapshot_id"], str)
        or manifest["snapshot_id"] != context["snapshot_id"]
        or context["control_claims_accepted"] is not False
        or not isinstance(manifest["entries"], list)
        or not isinstance(context["items"], list)
    ):
        raise VerticalFlowError("PART_CONTEXT_PROVENANCE_INVALID")
    entries = [_validate_manifest_entry(entry) for entry in manifest["entries"]]
    items = [_validate_context_item(item) for item in context["items"]]
    if len({entry["path"] for entry in entries}) != len(entries) or len({item["path"] for item in items}) != len(items):
        raise VerticalFlowError("PART_CONTEXT_PROVENANCE_INVALID")
    for item in items:
        matches = [
            entry
            for entry in entries
            if entry["path"] == item["path"]
            and entry["sha256"] == item["sha256"]
            and entry["size"] == item["size"]
        ]
        if len(matches) != 1:
            raise VerticalFlowError("PART_CONTEXT_PROVENANCE_INVALID")


def select_exact_item(context_pack: object, resource_ref: str) -> dict[str, object]:
    if not isinstance(context_pack, dict) or not isinstance(context_pack.get("items"), list):
        raise VerticalFlowError("PART_CONTEXT_PROVENANCE_INVALID")
    matches = [item for item in context_pack["items"] if isinstance(item, dict) and item.get("path") == resource_ref]
    if len(matches) != 1:
        raise VerticalFlowError("PART_CONTEXT_PROVENANCE_INVALID")
    return matches[0]


def is_protected_resource(resource_ref: str, protected_resources: object) -> bool:
    """Interpret only the declared protected patterns needed by the profile."""
    if not isinstance(protected_resources, list):
        raise VerticalFlowError("PART_ENVELOPE_INVALID")
    for protected in protected_resources:
        if not isinstance(protected, str):
            raise VerticalFlowError("PART_ENVELOPE_INVALID")
        if protected == resource_ref:
            return True
        if protected == ".git/**" and (resource_ref == ".git" or resource_ref.startswith(".git/")):
            return True
        if protected == ".env.*" and resource_ref.startswith(".env."):
            return True
    return False


def require_exact_write_candidate_authority(authority: Mapping[str, object], resource_ref: str) -> None:
    if authority["write_scope"] != "NAMED_RESOURCES" or resource_ref not in authority["write_resources"]:
        raise VerticalFlowError("PART_WRITE_AUTHORITY_DENIED")


def _packet_envelope(task_packet: Mapping[str, object], *, status: str) -> dict[str, object]:
    return {
        "protocol_version": "2.0",
        "packet_type": "candidate_proposal",
        "task_id": task_packet["task_id"],
        "correlation_id": task_packet["correlation_id"],
        "base_revision": task_packet["base_revision"],
        "actor": "part",
        "status": status,
    }


def build_blocked_candidate_packet(task_packet: Mapping[str, object], missing_authority: str) -> dict[str, object]:
    packet = _packet_envelope(task_packet, status="BLOCKED")
    packet["payload"] = {
        "outcome_code": "BLOCKED_PROPOSAL",
        "task_breakdown": [],
        "evidence": [],
        "candidates": [],
        "missing_authority": missing_authority,
        "recommended_next_action": "ASK_USER",
        "assertion_suggestions": [],
        "event_suggestions": [{"actor": "part", "phase": "DISCOVER", "code": "PART_PROPOSAL_BLOCKED"}],
        "proposed_transition": "WAITING_FOR_HUMAN",
    }
    return packet


def build_candidate_packet(task_packet: Mapping[str, object], item: Mapping[str, object]) -> dict[str, object]:
    packet = _packet_envelope(task_packet, status="IN_PROGRESS")
    resource_ref = item["path"]
    evidence = {
        "id": "EVID-PART-CONTEXT",
        "tier": "E1",
        "type": "file",
        "source": resource_ref,
        "observation": "exact W5 Context Pack item matched the snapshot manifest",
        "observed_revision": task_packet["base_revision"],
    }
    packet["payload"] = {
        "outcome_code": "CANDIDATES_PROPOSED",
        "task_breakdown": [{"unit_id": "UNIT-W6-UPDATE", "objective": "replace fixture marker before with after", "acceptance_criteria_ids": ["AC-W6-1"], "dependencies": []}],
        "evidence": [evidence],
        "candidates": [{
            "candidate_id": "CAND-W6-UPDATE",
            "action_type": "UPDATE_RESOURCE",
            "action_identity": {"identity_kind": "RESOURCE", "resource_ref": resource_ref},
            "resource_ref": resource_ref,
            "operation": "update",
            "expected_effect": "replace fixture marker before with after",
            "scope": [resource_ref],
            "rationale": "direct Context Pack evidence identifies the fixture item and its snapshot hash",
            "confidence": 1.0,
            "confidence_basis": "DIRECT",
            "evidence_refs": ["EVID-PART-CONTEXT"],
            "dependencies": [],
            "preconditions": [f"sha256:{item['sha256']}"],
            "proposed_verification": ["fixture content equals UTF-8 after newline"],
            "risk_notes": [],
            "acceptance_criteria_ids": ["AC-W6-1"],
        }],
        "unknowns": [],
        "assertion_suggestions": [],
        "event_suggestions": [{"actor": "part", "phase": "DISCOVER", "code": "PART_CANDIDATE_PROPOSED"}],
        "proposed_transition": "IN_PROGRESS",
    }
    validate_candidate_packet(packet)
    return packet


def validate_candidate_packet(packet: object) -> None:
    """Check the Part-owned output closure before it leaves this actor."""
    if not isinstance(packet, dict) or packet.get("packet_type") != "candidate_proposal" or packet.get("actor") != "part":
        raise VerticalFlowError("PART_PACKET_INVALID")
    payload = packet.get("payload")
    if not isinstance(payload, dict) or "accepted_state" in payload or "revision" in payload or "seq" in payload:
        raise VerticalFlowError("PART_STATE_OWNERSHIP_FORBIDDEN")
    evidence = payload.get("evidence")
    candidates = payload.get("candidates")
    if not isinstance(evidence, list) or not isinstance(candidates, list):
        raise VerticalFlowError("PART_EVIDENCE_INVALID")
    evidence_ids = []
    for record in evidence:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not record["id"]:
            raise VerticalFlowError("PART_EVIDENCE_INVALID")
        evidence_ids.append(record["id"])
    if len(evidence_ids) != len(set(evidence_ids)):
        raise VerticalFlowError("PART_EVIDENCE_INVALID")
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise VerticalFlowError("PART_ACTION_IDENTITY_INVALID")
        identity = candidate.get("action_identity")
        if (
            candidate.get("action_type") != "UPDATE_RESOURCE"
            or candidate.get("operation") != "update"
            or not isinstance(identity, dict)
            or set(identity) != {"identity_kind", "resource_ref"}
            or identity.get("identity_kind") != "RESOURCE"
            or candidate.get("resource_ref") != identity.get("resource_ref")
        ):
            raise VerticalFlowError("PART_ACTION_IDENTITY_INVALID")
        try:
            canonical_resource_ref(identity["resource_ref"])
        except VerticalFlowError as exc:
            raise VerticalFlowError("PART_ACTION_IDENTITY_INVALID") from exc
        refs = candidate.get("evidence_refs")
        if not isinstance(refs, list) or len(refs) != len(set(refs)) or any(ref not in evidence_ids for ref in refs):
            raise VerticalFlowError("PART_EVIDENCE_INVALID")


def propose_candidates(task_packet: object, snapshot_manifest: object, context_pack: object) -> dict[str, object]:
    """Propose the single fixture update without reading or changing the filesystem."""
    task = validate_task_envelope(task_packet, required_mode="EXPLORE")
    authority = validate_authority(task["payload"]["authority"])
    if task["payload"]["capabilities"].get("filesystem_read") != "AVAILABLE":
        return build_blocked_candidate_packet(task, "PART_READ_CAPABILITY_DENIED")
    if authority["read_scope"] in {"NONE", "UNKNOWN"}:
        return build_blocked_candidate_packet(task, "PART_READ_AUTHORITY_DENIED")
    validate_snapshot_context(snapshot_manifest, context_pack)
    item = select_exact_item(context_pack, "fixture/work-item.txt")
    protected_resources = task["payload"]["project_profile"].get("protected_resources")
    if is_protected_resource(item["path"], protected_resources):
        return build_blocked_candidate_packet(task, "PART_PROTECTED_APPROVAL_REQUIRED")
    require_exact_write_candidate_authority(authority, item["path"])
    return build_candidate_packet(task, item)
