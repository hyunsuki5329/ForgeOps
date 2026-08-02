"""Main-owned Product Contract normalization and actor routing."""

from __future__ import annotations

import copy
from collections.abc import Mapping

from jsonschema import Draft202012Validator

from tools.contract_bridge.verify import BridgeError, canonical_sha256, validate_and_map
from tools.local_vertical.common import (
    VerticalFlowError,
    require_id,
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
