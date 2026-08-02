"""Canonical JSON, identity, and authority primitives for the local vertical flow."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePosixPath
from types import MappingProxyType


class VerticalFlowError(Exception):
    """A stable, public-safe local vertical-flow rejection."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def freeze_json(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze_json(child) for key, child in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(child) for child in value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise VerticalFlowError("JSON_VALUE_INVALID")


def thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {key: thaw_json(child) for key, child in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(child) for child in value]
    return value


def require_strict_utc(raw: object, *, code: str) -> datetime:
    """Require the closed UTC timestamp spelling used by trusted runtime context."""
    if not isinstance(raw, str):
        raise VerticalFlowError(code)
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise VerticalFlowError(code) from exc
    if parsed.strftime("%Y-%m-%dT%H:%M:%SZ") != raw:
        raise VerticalFlowError(code)
    return parsed


@dataclass(frozen=True)
class TrustedExecutionContext:
    """Main/runtime-owned immutable execution input; deliberately not a packet."""

    task_packet: object
    candidate_packet: object
    current_revision: int
    approved_candidate_ids: tuple[str, ...]
    approved_candidates: object
    authority: object
    candidate_evidence_floor: str
    acceptance_criteria: object
    validation_at: str
    human_review_result: object | None

    def __post_init__(self) -> None:
        for name in (
            "task_packet",
            "candidate_packet",
            "approved_candidate_ids",
            "approved_candidates",
            "authority",
            "acceptance_criteria",
            "human_review_result",
        ):
            object.__setattr__(self, name, freeze_json(getattr(self, name)))


def canonical_json_bytes(value: object) -> bytes:
    """Return the stable JSON bytes used for local provenance comparisons."""
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise VerticalFlowError("JSON_VALUE_INVALID") from exc


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def require_id(raw: object, *, code: str = "ID_INVALID") -> str:
    """Require a literal, non-blank protocol identifier without normalization."""
    if (
        not isinstance(raw, str)
        or not raw
        or raw != raw.strip()
        or "\\" in raw
        or "/" in raw
        or "*" in raw
    ):
        raise VerticalFlowError(code)
    return raw


def canonical_resource_ref(raw: object) -> str:
    if (
        not isinstance(raw, str)
        or not raw
        or "\\" in raw
        or any(character in raw for character in "*?[]")
    ):
        raise VerticalFlowError("RESOURCE_IDENTITY_NONCANONICAL")
    path = PurePosixPath(raw)
    if (
        path.is_absolute()
        or ".." in path.parts
        or any(part in ("", ".") for part in path.parts)
        or "//" in raw
    ):
        raise VerticalFlowError("RESOURCE_IDENTITY_NONCANONICAL")
    return raw


def canonical_network_host(raw: object) -> str:
    """Require an exact lower-case ASCII DNS hostname with an optional TCP port."""
    if not isinstance(raw, str) or not raw or raw != raw.strip() or not raw.isascii():
        raise VerticalFlowError("NETWORK_IDENTITY_NONCANONICAL")
    if raw.count(":") > 1:
        raise VerticalFlowError("NETWORK_IDENTITY_NONCANONICAL")

    hostname = raw
    if ":" in raw:
        hostname, port = raw.split(":", 1)
        if (
            not port
            or not port.isdecimal()
            or len(port) > 5
            or not 1 <= int(port) <= 65535
        ):
            raise VerticalFlowError("NETWORK_IDENTITY_NONCANONICAL")
    if not 1 <= len(hostname) <= 253:
        raise VerticalFlowError("NETWORK_IDENTITY_NONCANONICAL")

    for label in hostname.split("."):
        if (
            not 1 <= len(label) <= 63
            or label[0] == "-"
            or label[-1] == "-"
            or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789-" for character in label)
        ):
            raise VerticalFlowError("NETWORK_IDENTITY_NONCANONICAL")
    return raw


_AUTHORITY_FIELDS = frozenset(
    {
        "read_scope",
        "read_resources",
        "write_scope",
        "write_resources",
        "execute_scope",
        "execute_commands",
        "network_scope",
        "network_hosts",
        "destructive_actions",
        "external_side_effects",
    }
)
_RESOURCE_SCOPES = frozenset({"NONE", "PROJECT", "NAMED_RESOURCES", "UNKNOWN"})
_EXECUTE_SCOPES = frozenset({"NONE", "NAMED_COMMANDS", "UNKNOWN"})
_NETWORK_SCOPES = frozenset({"NONE", "NAMED_HOSTS", "UNKNOWN"})
_EFFECT_FLAGS = frozenset({"ALLOWED", "DENIED", "UNKNOWN"})


def _copy_resource_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        raise VerticalFlowError("AUTHORITY_RESOURCE_LIST_INVALID")
    values: list[str] = []
    for item in raw:
        try:
            values.append(canonical_resource_ref(item))
        except VerticalFlowError as exc:
            raise VerticalFlowError("AUTHORITY_RESOURCE_NONCANONICAL") from exc
    if len(values) != len(set(values)):
        raise VerticalFlowError("AUTHORITY_RESOURCE_DUPLICATE")
    return values


def _copy_id_list(raw: object, *, kind: str) -> list[str]:
    if not isinstance(raw, list):
        raise VerticalFlowError(f"AUTHORITY_{kind}_LIST_INVALID")
    values: list[str] = []
    for item in raw:
        try:
            values.append(require_id(item, code=f"AUTHORITY_{kind}_VALUE_INVALID"))
        except VerticalFlowError as exc:
            raise VerticalFlowError(f"AUTHORITY_{kind}_VALUE_INVALID") from exc
    if len(values) != len(set(values)):
        raise VerticalFlowError(f"AUTHORITY_{kind}_DUPLICATE")
    return values


def _copy_network_host_list(raw: object) -> list[str]:
    if not isinstance(raw, list):
        raise VerticalFlowError("AUTHORITY_NETWORK_LIST_INVALID")
    values: list[str] = []
    for item in raw:
        try:
            values.append(canonical_network_host(item))
        except VerticalFlowError as exc:
            raise VerticalFlowError("AUTHORITY_NETWORK_VALUE_INVALID") from exc
    if len(values) != len(set(values)):
        raise VerticalFlowError("AUTHORITY_NETWORK_DUPLICATE")
    return values


def _validate_resource_branch(scope: object, raw_values: object) -> tuple[str, list[str]]:
    if not isinstance(scope, str) or scope not in _RESOURCE_SCOPES:
        raise VerticalFlowError("AUTHORITY_RESOURCE_SCOPE_INVALID")
    values = _copy_resource_list(raw_values)
    if scope == "NAMED_RESOURCES" and not values:
        raise VerticalFlowError("AUTHORITY_RESOURCE_LIST_REQUIRED")
    if scope in {"NONE", "PROJECT", "UNKNOWN"} and values:
        raise VerticalFlowError("AUTHORITY_RESOURCE_LIST_FORBIDDEN")
    return scope, values


def _validate_named_branch(
    scope: object,
    raw_values: object,
    *,
    kind: str,
    named_scope: str,
    valid_scopes: frozenset[str],
) -> tuple[str, list[str]]:
    if not isinstance(scope, str) or scope not in valid_scopes:
        raise VerticalFlowError(f"AUTHORITY_{kind}_SCOPE_INVALID")
    values = _copy_id_list(raw_values, kind=kind)
    if scope == named_scope and not values:
        raise VerticalFlowError(f"AUTHORITY_{kind}_LIST_REQUIRED")
    if scope in {"NONE", "UNKNOWN"} and values:
        raise VerticalFlowError(f"AUTHORITY_{kind}_LIST_FORBIDDEN")
    return scope, values


def _validate_network_branch(scope: object, raw_values: object) -> tuple[str, list[str]]:
    if not isinstance(scope, str) or scope not in _NETWORK_SCOPES:
        raise VerticalFlowError("AUTHORITY_NETWORK_SCOPE_INVALID")
    values = _copy_network_host_list(raw_values)
    if scope == "NAMED_HOSTS" and not values:
        raise VerticalFlowError("AUTHORITY_NETWORK_LIST_REQUIRED")
    if scope in {"NONE", "UNKNOWN"} and values:
        raise VerticalFlowError("AUTHORITY_NETWORK_LIST_FORBIDDEN")
    return scope, values


def validate_authority(authority: object) -> dict[str, object]:
    """Validate exact authority branches without granting or normalizing authority."""
    if not isinstance(authority, dict):
        raise VerticalFlowError("AUTHORITY_OBJECT_INVALID")
    if set(authority) != _AUTHORITY_FIELDS:
        raise VerticalFlowError("AUTHORITY_FIELDS_INVALID")

    read_scope, read_resources = _validate_resource_branch(
        authority["read_scope"], authority["read_resources"]
    )
    write_scope, write_resources = _validate_resource_branch(
        authority["write_scope"], authority["write_resources"]
    )
    execute_scope, execute_commands = _validate_named_branch(
        authority["execute_scope"],
        authority["execute_commands"],
        kind="EXECUTE",
        named_scope="NAMED_COMMANDS",
        valid_scopes=_EXECUTE_SCOPES,
    )
    network_scope, network_hosts = _validate_network_branch(
        authority["network_scope"], authority["network_hosts"]
    )
    for field in ("destructive_actions", "external_side_effects"):
        if not isinstance(authority[field], str) or authority[field] not in _EFFECT_FLAGS:
            raise VerticalFlowError("AUTHORITY_EFFECT_FLAG_INVALID")

    return {
        "read_scope": read_scope,
        "read_resources": read_resources,
        "write_scope": write_scope,
        "write_resources": write_resources,
        "execute_scope": execute_scope,
        "execute_commands": execute_commands,
        "network_scope": network_scope,
        "network_hosts": network_hosts,
        "destructive_actions": authority["destructive_actions"],
        "external_side_effects": authority["external_side_effects"],
    }
