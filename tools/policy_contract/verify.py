#!/usr/bin/env python3
"""Verify closed ForgeOps authority-policy fixture branches."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_REF = "contracts/forgeops-authority-policy/1.0/schema.json"
RESOURCE_SUITE_REF = "fixtures/forgeops-authority-resource/suite.json"
COMMAND_NETWORK_SUITE_REF = "fixtures/forgeops-authority-command-network/suite.json"
APPROVAL_SUITE_REF = "fixtures/forgeops-approval-policy/suite.json"
EXPECTED_SUITE_ID = "forgeops-authority-resource-v1"
EXPECTED_COMMAND_NETWORK_SUITE_ID = "forgeops-authority-command-network-v1"
EXPECTED_APPROVAL_SUITE_ID = "forgeops-approval-policy-v1"
EXPECTED_SUITE_VERSION = "1.0"
RESOURCE_COMMAND_IDS = {"resource-authority-negative", "protected-read-negative"}
COMMAND_NETWORK_COMMAND_ID = "command-network-negative"
APPROVAL_COMMAND_ID = "approval-negative-fixture"
EXPECTED_RESULT_REFS = {
    "resource-authority-negative": "artifacts/verification/vg-005-resource-authority-result.json",
    "protected-read-negative": "artifacts/verification/vg-005-protected-read-result.json",
    "command-network-negative": "artifacts/verification/vg-006-command-network-result.json",
    "approval-negative-fixture": "artifacts/verification/vg-007-approval-policy-result.json",
}
PROTECTED_CLASSIFICATIONS = {"PROTECTED", "CREDENTIAL", "PRIVATE_DATA"}
MUTATING_OPERATIONS = {"create", "update", "delete"}
ACTION_OPERATIONS = {
    "READ_RESOURCE": "read",
    "CREATE_RESOURCE": "create",
    "UPDATE_RESOURCE": "update",
    "DELETE_RESOURCE": "delete",
}
_UNSAFE_LITERAL = re.compile(r"[\\:*?\[\]{}()^$+|]|[^\x21-\x7e]")
_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")
_SENTINEL = bytes.fromhex("464f5247454f50535f50524f5445435445445f53454e54494e454c")

EXPECTED_CASE_CATALOG = (
    ("POSITIVE_PROJECT_READ", "positive", "PASSED"),
    ("POSITIVE_NAMED_UPDATE", "positive", "PASSED"),
    ("POSITIVE_NAMED_READ", "positive", "PASSED"),
    ("NEGATIVE_ABSOLUTE_PATH", "negative", "RESOURCE_PATH_INVALID"),
    ("NEGATIVE_PARENT_TRAVERSAL", "negative", "RESOURCE_PATH_INVALID"),
    ("NEGATIVE_WILDCARD_PATH", "negative", "RESOURCE_PATH_INVALID"),
    ("NEGATIVE_REGEX_PATH", "negative", "RESOURCE_PATH_INVALID"),
    ("NEGATIVE_PROJECT_WITH_LIST", "negative", "RESOURCE_SCOPE_INVALID"),
    ("NEGATIVE_NAMED_EMPTY", "negative", "RESOURCE_SCOPE_INVALID"),
    ("NEGATIVE_NAMED_DUPLICATE", "negative", "RESOURCE_SCOPE_INVALID"),
    ("NEGATIVE_NAMED_WILDCARD_ENTRY", "negative", "RESOURCE_SCOPE_INVALID"),
    ("NEGATIVE_NAMED_PREFIX", "negative", "RESOURCE_EXACT_MATCH_REQUIRED"),
    ("NEGATIVE_NAMED_CASE", "negative", "RESOURCE_EXACT_MATCH_REQUIRED"),
    ("NEGATIVE_NAMED_SUFFIX", "negative", "RESOURCE_EXACT_MATCH_REQUIRED"),
    ("NEGATIVE_NONE_SCOPE", "negative", "RESOURCE_SCOPE_INVALID"),
    ("NEGATIVE_UNKNOWN_SCOPE", "negative", "RESOURCE_SCOPE_INVALID"),
    ("NEGATIVE_CAPABILITY_UNKNOWN", "negative", "RESOURCE_CAPABILITY_DENIED"),
    ("NEGATIVE_CAPABILITY_UNAVAILABLE", "negative", "RESOURCE_CAPABILITY_DENIED"),
    ("NEGATIVE_CANDIDATE_UNAPPROVED", "negative", "RESOURCE_CAPABILITY_DENIED"),
    ("NEGATIVE_STALE_REVISION", "negative", "RESOURCE_CAPABILITY_DENIED"),
    ("NEGATIVE_EXPLORE_MUTATION", "negative", "RESOURCE_CAPABILITY_DENIED"),
    ("NEGATIVE_PROJECT_ROOT_ESCAPE", "negative", "RESOURCE_CONTAINMENT_FAILED"),
    ("NEGATIVE_SYMLINK_ESCAPE", "negative", "RESOURCE_CONTAINMENT_FAILED"),
    ("NEGATIVE_PROTECTED_READ_UNAPPROVED", "negative", "PROTECTED_TARGET_APPROVAL_REQUIRED"),
    ("NEGATIVE_CREDENTIAL_READ_UNAPPROVED", "negative", "PROTECTED_TARGET_APPROVAL_REQUIRED"),
    ("NEGATIVE_PRIVATE_DATA_READ_UNAPPROVED", "negative", "PROTECTED_TARGET_APPROVAL_REQUIRED"),
    ("NEGATIVE_USER_CHANGE_CONFLICT", "negative", "USER_CHANGE_CONFLICT"),
)
PROTECTED_CASE_IDS = {
    "NEGATIVE_PROTECTED_READ_UNAPPROVED",
    "NEGATIVE_CREDENTIAL_READ_UNAPPROVED",
    "NEGATIVE_PRIVATE_DATA_READ_UNAPPROVED",
}
COMMAND_NETWORK_EXPECTED_CASE_CATALOG = (
    ("POSITIVE_COMMAND_EXACT_TRIPLE", "positive", "PASSED"),
    ("POSITIVE_NETWORK_HOST", "positive", "PASSED"),
    ("POSITIVE_NETWORK_HOST_PORT", "positive", "PASSED"),
    ("NEGATIVE_COMMAND_CAPABILITY_UNKNOWN", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_NETWORK_CANDIDATE_UNAPPROVED", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_COMMAND_ID_MISMATCH", "negative", "COMMAND_IDENTITY_MISMATCH"),
    ("NEGATIVE_COMMAND_TEXT_MISMATCH", "negative", "COMMAND_IDENTITY_MISMATCH"),
    ("NEGATIVE_COMMAND_CWD_MISMATCH", "negative", "COMMAND_IDENTITY_MISMATCH"),
    ("NEGATIVE_COMMAND_RAW", "negative", "COMMAND_RAW_FORBIDDEN"),
    ("NEGATIVE_COMMAND_PROJECT_SCOPE", "negative", "COMMAND_SCOPE_INVALID"),
    ("NEGATIVE_COMMAND_NONE_SCOPE", "negative", "COMMAND_SCOPE_INVALID"),
    ("NEGATIVE_COMMAND_UNKNOWN_SCOPE", "negative", "COMMAND_SCOPE_INVALID"),
    ("NEGATIVE_COMMAND_NAMED_EMPTY", "negative", "COMMAND_SCOPE_INVALID"),
    ("NEGATIVE_COMMAND_NAMED_DUPLICATE", "negative", "COMMAND_SCOPE_INVALID"),
    ("NEGATIVE_COMMAND_NAMED_WILDCARD", "negative", "COMMAND_SCOPE_INVALID"),
    ("NEGATIVE_NETWORK_SCHEME", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_PATH", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_QUERY", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_FRAGMENT", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_USERINFO", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_WHITESPACE", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_UPPERCASE", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_WILDCARD", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_LABEL", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_EDGE_HYPHEN", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_MULTIPLE_COLONS", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_PORT_ZERO", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_PORT_HIGH", "negative", "NETWORK_IDENTITY_INVALID"),
    ("NEGATIVE_NETWORK_EXACT_MISMATCH", "negative", "NETWORK_EXACT_MATCH_REQUIRED"),
    ("NEGATIVE_NETWORK_PROJECT_SCOPE", "negative", "NETWORK_SCOPE_INVALID"),
    ("NEGATIVE_NETWORK_NAMED_EMPTY", "negative", "NETWORK_SCOPE_INVALID"),
    ("NEGATIVE_NETWORK_NAMED_DUPLICATE", "negative", "NETWORK_SCOPE_INVALID"),
    ("NEGATIVE_NETWORK_INVALID_ALLOWLIST_EXTRA", "negative", "NETWORK_SCOPE_INVALID"),
    (
        "NEGATIVE_NETWORK_REDIRECT_INHERITANCE",
        "negative",
        "NETWORK_REDIRECT_INHERITANCE_FORBIDDEN",
    ),
    ("NEGATIVE_NETWORK_PRIVATE", "negative", "NETWORK_DESTINATION_FORBIDDEN"),
    ("NEGATIVE_NETWORK_LOOPBACK", "negative", "NETWORK_DESTINATION_FORBIDDEN"),
    ("NEGATIVE_NETWORK_LINK_LOCAL", "negative", "NETWORK_DESTINATION_FORBIDDEN"),
    ("NEGATIVE_NETWORK_METADATA", "negative", "NETWORK_DESTINATION_FORBIDDEN"),
    (
        "NEGATIVE_NETWORK_CLASSIFICATION_MISMATCH",
        "negative",
        "NETWORK_DESTINATION_FORBIDDEN",
    ),
    ("NEGATIVE_COMMAND_EXPLORE_MODE", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_NETWORK_STALE_REVISION", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_COMMAND_PREFLIGHT_FAILED", "negative", "AUTHORITY_CAPABILITY_DENIED"),
)

APPROVAL_EXPECTED_CASE_CATALOG = (
    ("POSITIVE_DESTRUCTIVE_EXTERNAL", "positive", "PASSED"),
    ("POSITIVE_LOCAL_NON_DESTRUCTIVE", "positive", "PASSED"),
    ("NEGATIVE_DESTRUCTIVE_DENIED", "negative", "EFFECT_GATE_DENIED"),
    ("NEGATIVE_DESTRUCTIVE_UNKNOWN", "negative", "EFFECT_GATE_DENIED"),
    ("NEGATIVE_EXTERNAL_AUTHORITY_DENIED", "negative", "EFFECT_GATE_DENIED"),
    ("NEGATIVE_EXTERNAL_AUTHORITY_UNKNOWN", "negative", "EFFECT_GATE_DENIED"),
    ("NEGATIVE_EXTERNAL_RUNTIME_UNAVAILABLE", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_EXTERNAL_RUNTIME_UNKNOWN", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_AUTHORITY_DENIED", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_AUTHORITY_UNKNOWN", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_CAPABILITY_UNKNOWN", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_CANDIDATE_UNAPPROVED", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_STALE_REVISION", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_EXPLORE_MODE", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_PREFLIGHT_FAILED", "negative", "AUTHORITY_CAPABILITY_DENIED"),
    ("NEGATIVE_APPROVAL_MISSING", "negative", "APPROVAL_MISSING"),
    ("NEGATIVE_APPROVAL_REJECTED", "negative", "APPROVAL_REJECTED"),
    ("NEGATIVE_NOT_BEFORE", "negative", "APPROVAL_EXPIRED"),
    ("NEGATIVE_EXPIRED", "negative", "APPROVAL_EXPIRED"),
    ("NEGATIVE_WRONG_ISSUER", "negative", "APPROVAL_AUDIENCE_INVALID"),
    ("NEGATIVE_WRONG_AUDIENCE", "negative", "APPROVAL_AUDIENCE_INVALID"),
    ("NEGATIVE_WRONG_TENANT", "negative", "APPROVAL_TENANT_INVALID"),
    ("NEGATIVE_WRONG_APPROVER", "negative", "APPROVAL_SIGNATURE_INVALID"),
    ("NEGATIVE_WRONG_KEY", "negative", "APPROVAL_SIGNATURE_INVALID"),
    ("NEGATIVE_SIGNATURE_REF", "negative", "APPROVAL_SIGNATURE_INVALID"),
    ("NEGATIVE_SIGNATURE_UNVERIFIED", "negative", "APPROVAL_SIGNATURE_INVALID"),
    ("NEGATIVE_BIND_CANDIDATE", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_ACTION_IDENTITY", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_TARGET", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_REVISION", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_CONTRACT", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_PLAN", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_POLICY", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_DIFF", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_PAYLOAD", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_POLICY_VERSION", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_NOT_BEFORE", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_EXPIRES_AT", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_BIND_NONCE", "negative", "APPROVAL_BINDING_MISMATCH"),
    ("NEGATIVE_NONCE_REUSE", "negative", "APPROVAL_NONCE_REUSED"),
    ("NEGATIVE_REPLAYED_APPROVAL", "negative", "APPROVAL_NONCE_REUSED"),
    ("NEGATIVE_NONCE_CONSUME_FAILED", "negative", "APPROVAL_NONCE_CONSUME_FAILED"),
    ("POSITIVE_ATOMIC_SINGLE_CONSUME", "positive", "PASSED"),
)


class PolicyError(Exception):
    """A stable, public-safe policy rejection."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ProbeSet:
    """In-memory first-byte probes; no filesystem target is ever opened."""

    def __init__(self) -> None:
        self.reader_calls = 0
        self._reader_values: list[bytes] = []
        self._model_context: list[bytes] = []
        self._logs: list[bytes] = []
        self._evidence: list[bytes] = []

    def guarded_read(self, classification: str) -> bytes:
        self.reader_calls += 1
        value = _SENTINEL if classification in PROTECTED_CLASSIFICATIONS else b"public-fixture-content"
        self._reader_values.append(value)
        return value

    def publish(self, value: bytes) -> None:
        self._model_context.append(value)
        self._logs.append(value)
        self._evidence.append(value)

    def sentinel_occurrences(self) -> int:
        surfaces = self._reader_values + self._model_context + self._logs + self._evidence
        return sum(value.count(_SENTINEL) for value in surfaces)

    def public_counts(self) -> dict[str, int]:
        return {
            "reader_calls": self.reader_calls,
            "model_context_writes": len(self._model_context),
            "log_writes": len(self._logs),
            "evidence_writes": len(self._evidence),
            "sentinel_occurrences": self.sentinel_occurrences(),
        }


class SpyAdapter:
    """In-memory dispatch witness; it cannot start a process or touch a network."""

    def __init__(self) -> None:
        self.calls = 0
        self.process_calls = 0
        self.dns_calls = 0
        self.socket_calls = 0

    def dispatch(self, identity_kind: str) -> None:
        if identity_kind not in {"COMMAND", "NETWORK"}:
            raise ValueError("unsupported spy dispatch identity")
        self.calls += 1

    def public_counts(self) -> dict[str, int]:
        return {
            "adapter_calls": self.calls,
            "process_calls": self.process_calls,
            "dns_calls": self.dns_calls,
            "socket_calls": self.socket_calls,
        }


class SpyDispatcher:
    """Records policy dispatch only; it cannot perform a real effect."""

    def __init__(self) -> None:
        self.calls = 0
        self.external_effect_calls = 0
        self.process_calls = 0
        self.network_calls = 0
        self.store_calls = 0

    def dispatch(self) -> None:
        self.calls += 1

    def public_counts(self) -> dict[str, int]:
        return {
            "dispatcher_calls": self.calls,
            "external_effect_calls": self.external_effect_calls,
            "process_calls": self.process_calls,
            "network_calls": self.network_calls,
            "store_calls": self.store_calls,
        }


class MemoryNonceLedger:
    """Fixture-only atomic consume-and-mark ledger."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._consumed: set[str] = set()

    def consume_once(self, nonce: str) -> bool:
        with self._lock:
            if nonce in self._consumed:
                return False
            self._consumed.add(nonce)
            return True


class FailingNonceLedger:
    """Fixture-only witness for a durable-store consume failure."""

    def consume_once(self, nonce: str) -> bool:
        del nonce
        raise RuntimeError("fixture nonce ledger unavailable")


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def default_validator() -> Draft202012Validator:
    schema = load_json(ROOT / SCHEMA_REF)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_schema(request: dict[str, Any]) -> None:
    validator = default_validator()
    request_validator = validator.evolve(schema=validator.schema["$defs"]["resource_request"])
    if next(request_validator.iter_errors(request), None) is not None:
        raise PolicyError("RESOURCE_SCHEMA_INVALID")
    action = request["action"]
    if ACTION_OPERATIONS[action["action_type"]] != action["operation"]:
        raise PolicyError("RESOURCE_SCHEMA_INVALID")


def validate_literal_root_relative(resource_ref: str, error_code: str = "RESOURCE_PATH_INVALID") -> None:
    if (
        not resource_ref
        or resource_ref != resource_ref.strip()
        or resource_ref.startswith("/")
        or resource_ref.endswith("/")
        or "//" in resource_ref
        or _UNSAFE_LITERAL.search(resource_ref)
    ):
        raise PolicyError(error_code)
    path = PurePosixPath(resource_ref)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise PolicyError(error_code)


def validate_scope_and_list(authority: dict[str, Any]) -> None:
    scope = authority["scope"]
    resources = authority["resources"]
    if scope == "PROJECT":
        if resources:
            raise PolicyError("RESOURCE_SCOPE_INVALID")
        return
    if scope == "NAMED_RESOURCES":
        if not resources or len(resources) != len(set(resources)):
            raise PolicyError("RESOURCE_SCOPE_INVALID")
        for resource_ref in resources:
            validate_literal_root_relative(resource_ref, "RESOURCE_SCOPE_INVALID")
        return
    if resources or scope in {"NONE", "UNKNOWN"}:
        raise PolicyError("RESOURCE_SCOPE_INVALID")
    raise PolicyError("RESOURCE_SCOPE_INVALID")


def require_available_capability_and_operation_preconditions(request: dict[str, Any]) -> None:
    if request["capability"] != "AVAILABLE":
        raise PolicyError("RESOURCE_CAPABILITY_DENIED")
    if request["action"]["operation"] == "read" and request["operation_mode"] == "EXPLORE":
        return
    if (
        request["operation_mode"] != "EXECUTE"
        or request["approved_candidate"] is not True
        or request["current_revision"] is not True
    ):
        raise PolicyError("RESOURCE_CAPABILITY_DENIED")


def require_root_containment_or_exact_membership(request: dict[str, Any]) -> None:
    identity = request["identity"]
    if identity["root_contained"] is not True or identity["symlink_contained"] is not True:
        raise PolicyError("RESOURCE_CONTAINMENT_FAILED")
    authority = request["authority"]
    if authority["scope"] == "NAMED_RESOURCES":
        resource_ref = identity["resource_ref"]
        if not any(resource_ref == allowed for allowed in authority["resources"]):
            raise PolicyError("RESOURCE_EXACT_MATCH_REQUIRED")


def require_protected_target_approval_before_read(request: dict[str, Any]) -> None:
    identity = request["identity"]
    if request["action"]["operation"] != "read":
        return
    if identity["classification"] not in PROTECTED_CLASSIFICATIONS:
        return
    approval = request["protected_target_approval"]
    if approval is None or (
        approval["resource_ref"] != identity["resource_ref"]
        or approval["classification"] != identity["classification"]
    ):
        raise PolicyError("PROTECTED_TARGET_APPROVAL_REQUIRED")


def require_user_change_ownership_before_mutation(request: dict[str, Any]) -> None:
    if (
        request["action"]["operation"] in MUTATING_OPERATIONS
        and request["action"]["user_change_owned"] is not True
    ):
        raise PolicyError("USER_CHANGE_CONFLICT")


def validate_resource(request: dict[str, Any]) -> str:
    """Validate RESOURCE preflight in the normative fail-closed order."""
    validate_schema(request)
    validate_literal_root_relative(request["identity"]["resource_ref"])
    validate_scope_and_list(request["authority"])
    require_available_capability_and_operation_preconditions(request)
    require_root_containment_or_exact_membership(request)
    require_protected_target_approval_before_read(request)
    require_user_change_ownership_before_mutation(request)
    return "PASSED"


def evaluate_resource(request: dict[str, Any]) -> tuple[str, ProbeSet]:
    probes = ProbeSet()
    try:
        result = validate_resource(request)
    except PolicyError as exc:
        return exc.code, probes
    if request["action"]["operation"] == "read":
        value = probes.guarded_read(request["identity"]["classification"])
        probes.publish(value)
    return result, probes


def validate_command_network_request_schema(request: dict[str, Any]) -> None:
    validator = default_validator()
    request_validator = validator.evolve(
        schema=validator.schema["$defs"]["command_network_request"]
    )
    if next(request_validator.iter_errors(request), None) is not None:
        raise PolicyError("COMMAND_NETWORK_SCHEMA_INVALID")


def validate_command_cwd(cwd: str) -> None:
    if cwd == ".":
        return
    if not isinstance(cwd, str) or any(part in {"", ".", ".."} for part in cwd.split("/")):
        raise PolicyError("COMMAND_IDENTITY_MISMATCH")
    try:
        validate_literal_root_relative(cwd, "COMMAND_IDENTITY_MISMATCH")
    except (PolicyError, TypeError):
        raise PolicyError("COMMAND_IDENTITY_MISMATCH") from None


def validate_command(request: dict[str, Any], catalog: dict[str, Any]) -> str:
    """Require an exact named validation-command id, command, and cwd triple."""
    validate_command_network_request_schema(request)
    identity = request["identity"]
    if set(identity) == {"identity_kind", "command"}:
        raise PolicyError("COMMAND_RAW_FORBIDDEN")
    if (
        request["action"] != {"action_type": "EXECUTE_COMMAND", "operation": "invoke"}
        or set(identity) != {"identity_kind", "command_id", "command", "cwd"}
        or identity["identity_kind"] != "COMMAND"
        or request["destination_class"] is not None
        or request["redirect_source"] is not None
    ):
        raise PolicyError("COMMAND_NETWORK_SCHEMA_INVALID")
    authority = request["authority"]
    command_ids = authority.get("execute_commands")
    if (
        set(authority) != {"execute_scope", "execute_commands"}
        or authority.get("execute_scope") != "NAMED_COMMANDS"
        or not isinstance(command_ids, list)
        or not command_ids
        or any(not isinstance(item, str) or not item or "*" in item for item in command_ids)
        or len(command_ids) != len(set(command_ids))
    ):
        raise PolicyError("COMMAND_SCOPE_INVALID")
    command_id = identity["command_id"]
    record = catalog.get("commands", {}).get(command_id)
    if (
        command_id not in command_ids
        or not isinstance(record, dict)
        or record.get("id") != command_id
        or record.get("command") != identity["command"]
        or record.get("cwd") != identity["cwd"]
    ):
        raise PolicyError("COMMAND_IDENTITY_MISMATCH")
    validate_command_cwd(identity["cwd"])
    return "PASSED"


def require_canonical_host_port_literal(host_port: str) -> None:
    if (
        not isinstance(host_port, str)
        or not host_port
        or not host_port.isascii()
        or host_port != host_port.strip()
        or host_port.count(":") > 1
    ):
        raise PolicyError("NETWORK_IDENTITY_INVALID")
    if ":" in host_port:
        host, port_text = host_port.rsplit(":", 1)
        if not port_text.isdecimal():
            raise PolicyError("NETWORK_IDENTITY_INVALID")
        port = int(port_text)
        if port < 1 or port > 65535:
            raise PolicyError("NETWORK_IDENTITY_INVALID")
    else:
        host = host_port
    if len(host) < 1 or len(host) > 253:
        raise PolicyError("NETWORK_IDENTITY_INVALID")
    labels = host.split(".")
    if any(_DNS_LABEL.fullmatch(label) is None for label in labels):
        raise PolicyError("NETWORK_IDENTITY_INVALID")


def validate_network(request: dict[str, Any], catalog: dict[str, Any]) -> str:
    """Require an exact canonical named host and a trusted public destination."""
    validate_command_network_request_schema(request)
    identity = request["identity"]
    if (
        request["action"] != {"action_type": "CALL_NETWORK", "operation": "invoke"}
        or set(identity) != {"identity_kind", "network_host"}
        or identity["identity_kind"] != "NETWORK"
    ):
        raise PolicyError("COMMAND_NETWORK_SCHEMA_INVALID")
    host = identity["network_host"]
    require_canonical_host_port_literal(host)
    authority = request["authority"]
    hosts = authority.get("network_hosts")
    if (
        set(authority) != {"network_scope", "network_hosts"}
        or authority.get("network_scope") != "NAMED_HOSTS"
        or not isinstance(hosts, list)
        or not hosts
        or len(hosts) != len(set(hosts))
    ):
        raise PolicyError("NETWORK_SCOPE_INVALID")
    try:
        for allowed in hosts:
            require_canonical_host_port_literal(allowed)
    except PolicyError:
        raise PolicyError("NETWORK_SCOPE_INVALID") from None
    if request["redirect_source"] is not None:
        raise PolicyError("NETWORK_REDIRECT_INHERITANCE_FORBIDDEN")
    if not any(host == allowed for allowed in hosts):
        raise PolicyError("NETWORK_EXACT_MATCH_REQUIRED")
    destination_class = request["destination_class"]
    trusted_class = catalog.get("network_destinations", {}).get(host)
    if destination_class != "PUBLIC" or trusted_class != "PUBLIC":
        raise PolicyError("NETWORK_DESTINATION_FORBIDDEN")
    return "PASSED"


def require_command_network_execute_preconditions(request: dict[str, Any]) -> None:
    if (
        request.get("operation_mode") != "EXECUTE"
        or request.get("capability") != "AVAILABLE"
        or request.get("approved_candidate") is not True
        or request.get("current_revision") is not True
        or request.get("all_preflights_passed") is not True
    ):
        raise PolicyError("AUTHORITY_CAPABILITY_DENIED")


def evaluate_command_network(request: dict[str, Any]) -> tuple[str, SpyAdapter]:
    adapter = SpyAdapter()
    try:
        suite = load_json(ROOT / COMMAND_NETWORK_SUITE_REF)
        catalog = suite["catalog"]
        identity = request.get("identity")
        identity_kind = identity.get("identity_kind") if isinstance(identity, dict) else None
        if identity_kind == "COMMAND":
            result = validate_command(request, catalog)
        elif identity_kind == "NETWORK":
            result = validate_network(request, catalog)
        else:
            raise PolicyError("COMMAND_NETWORK_SCHEMA_INVALID")
        require_command_network_execute_preconditions(request)
    except PolicyError as exc:
        return exc.code, adapter
    adapter.dispatch(identity_kind)
    return result, adapter


def canonical_effect_hash(request: dict[str, Any]) -> str:
    """Bind every trusted effect input without serializing approval material."""
    approval = request.get("approval")
    approval_claim = None
    if isinstance(approval, dict):
        approval_claim = {
            key: approval[key]
            for key in (
                "candidate_id",
                "action_identity",
                "target",
                "tenant",
                "issuer",
                "audience",
                "approver_subject",
                "policy_version",
                "key_id",
                "not_before",
                "expires_at",
                "nonce",
                "signature_ref",
            )
        }
    bound = {
        "base_revision": request["base_revision"],
        "candidate_id": request["candidate_id"],
        "action_identity": request["action_identity"],
        "target": request["target"],
        "tenant": request["tenant"],
        "effect": request["effect"],
        "contract": request["contract"],
        "plan": request["plan"],
        "policy": request["policy"],
        "diff": request["diff"],
        "payload": request["payload"],
        "approval_claim": approval_claim,
    }
    encoded = json.dumps(
        bound, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_approval_request_schema(request: dict[str, Any]) -> None:
    validator = default_validator()
    request_validator = validator.evolve(schema=validator.schema["$defs"]["approval_request"])
    if next(request_validator.iter_errors(request), None) is not None:
        raise PolicyError("APPROVAL_BINDING_MISMATCH")


def require_execute_available_exact_authority_candidate_revision(
    request: dict[str, Any],
) -> None:
    if (
        request["operation_mode"] != "EXECUTE"
        or request["capability"] != "AVAILABLE"
        or request["exact_authority"] != "ALLOWED"
        or request["approved_candidate"] is not True
        or request["current_revision"] is not True
        or request["all_preflights_passed"] is not True
    ):
        raise PolicyError("AUTHORITY_CAPABILITY_DENIED")
    if request["effect"]["external"] is True and request["external_runtime"] != "AVAILABLE":
        raise PolicyError("AUTHORITY_CAPABILITY_DENIED")


def require_destructive_and_external_gates(request: dict[str, Any]) -> None:
    effect = request["effect"]
    if effect["destructive"] is True and request["destructive_actions"] != "ALLOWED":
        raise PolicyError("EFFECT_GATE_DENIED")
    if effect["external"] is True and request["external_side_effects"] != "ALLOWED":
        raise PolicyError("EFFECT_GATE_DENIED")


def _strict_utc(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except (TypeError, ValueError):
        raise PolicyError("APPROVAL_EXPIRED") from None
    return parsed.replace(tzinfo=timezone.utc)


def validate_issuer_audience_tenant_signature_and_time(
    approval: dict[str, Any], request: dict[str, Any]
) -> None:
    if request["approval_decision"] != "APPROVED":
        raise PolicyError("APPROVAL_REJECTED")
    if (
        approval["issuer"] != request["trusted_issuer"]
        or approval["audience"] != request["trusted_audience"]
    ):
        raise PolicyError("APPROVAL_AUDIENCE_INVALID")
    if approval["tenant"] != request["tenant"]:
        raise PolicyError("APPROVAL_TENANT_INVALID")
    if (
        request["signature_verified"] is not True
        or approval["approver_subject"] != request["trusted_approver_subject"]
        or approval["key_id"] != request["trusted_key_id"]
        or approval["signature_ref"] != request["trusted_signature_ref"]
    ):
        raise PolicyError("APPROVAL_SIGNATURE_INVALID")
    now = _strict_utc(request["validation_time"])
    not_before = _strict_utc(approval["not_before"])
    expires_at = _strict_utc(approval["expires_at"])
    if not_before > now or expires_at < now or expires_at < not_before:
        raise PolicyError("APPROVAL_EXPIRED")


def validate_approval(request: dict[str, Any], ledger: Any) -> str:
    """Validate independent hard gates, exact binding, then atomic nonce use."""
    validate_approval_request_schema(request)
    require_execute_available_exact_authority_candidate_revision(request)
    require_destructive_and_external_gates(request)
    approval = request.get("approval")
    if approval is None:
        raise PolicyError("APPROVAL_MISSING")
    validate_issuer_audience_tenant_signature_and_time(approval, request)
    if (
        approval["candidate_id"] != request["candidate_id"]
        or approval["action_identity"] != request["action_identity"]
        or approval["target"] != request["target"]
        or approval["policy_version"] != request["trusted_policy_version"]
        or approval["policy_version"] != request["policy"]["version"]
        or approval["effect_hash"] != canonical_effect_hash(request)
    ):
        raise PolicyError("APPROVAL_BINDING_MISMATCH")
    try:
        consumed = ledger.consume_once(approval["nonce"])
    except Exception:
        raise PolicyError("APPROVAL_NONCE_CONSUME_FAILED") from None
    if consumed is not True:
        raise PolicyError("APPROVAL_NONCE_REUSED")
    return "PASSED"


def evaluate_approval(request: dict[str, Any], ledger: Any) -> tuple[str, SpyDispatcher]:
    dispatcher = SpyDispatcher()
    try:
        result = validate_approval(request, ledger)
    except PolicyError as exc:
        return exc.code, dispatcher
    dispatcher.dispatch()
    return result, dispatcher


def _apply_approval_mutation(request: dict[str, Any], mutation: dict[str, Any]) -> None:
    parts = mutation["path"].split(".")
    target: dict[str, Any] = request
    for part in parts[:-1]:
        value = target.get(part)
        if not isinstance(value, dict):
            raise ValueError("approval mutation path does not name an object")
        target = value
    leaf = parts[-1]
    if mutation.get("remove") is True:
        if leaf not in target:
            raise ValueError("approval mutation remove target does not exist")
        del target[leaf]
    elif "value" in mutation:
        if leaf not in target:
            raise ValueError("approval mutation target does not exist")
        target[leaf] = copy.deepcopy(mutation["value"])
    else:
        raise ValueError("approval mutation has no operation")


def materialize_approval_case(suite: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    request = copy.deepcopy(suite["base_request"])
    request["approval"]["effect_hash"] = canonical_effect_hash(request)
    for mutation in case["mutations"]:
        _apply_approval_mutation(request, mutation)
    if case["kind"] == "positive" and request.get("approval") is not None:
        request["approval"]["effect_hash"] = canonical_effect_hash(request)
    return request


def validate_approval_suite(suite: dict[str, Any]) -> None:
    if set(suite) != {"suite_id", "suite_version", "schema_ref", "base_request", "cases"}:
        raise ValueError("approval suite fields do not match the closed manifest")
    if (
        suite["suite_id"] != EXPECTED_APPROVAL_SUITE_ID
        or suite["suite_version"] != EXPECTED_SUITE_VERSION
        or suite["schema_ref"] != SCHEMA_REF
    ):
        raise ValueError("unsupported approval suite identity or version")
    if next(default_validator().iter_errors(suite), None) is not None:
        raise ValueError("approval suite does not satisfy the closed schema")
    catalog = tuple(
        (item["id"], item["kind"], item.get("expected_result", item.get("expected_error")))
        for item in suite["cases"]
    )
    if catalog != APPROVAL_EXPECTED_CASE_CATALOG:
        raise ValueError("approval cases do not match the exact case catalog")
    base_request = copy.deepcopy(suite["base_request"])
    base_request["approval"]["effect_hash"] = canonical_effect_hash(base_request)
    validate_approval_request_schema(base_request)


def run_approval_case(suite: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    request = materialize_approval_case(suite, case)
    scenario = case["scenario"]
    dispatcher = SpyDispatcher()
    nonce_outcome = "NOT_CONSUMED"
    if scenario == "concurrent":
        ledger = MemoryNonceLedger()

        def validate_once(_: int) -> str:
            try:
                return validate_approval(request, ledger)
            except PolicyError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=16) as executor:
            outcomes = list(executor.map(validate_once, range(32)))
        actual = (
            "PASSED"
            if outcomes.count("PASSED") == 1
            and outcomes.count("APPROVAL_NONCE_REUSED") == 31
            else "APPROVAL_NONCE_CONSUME_FAILED"
        )
        nonce_outcome = "ATOMIC_SINGLE_CONSUME" if actual == "PASSED" else "ATOMICITY_FAILED"
    else:
        if scenario in {"nonce_reuse", "replay"}:
            ledger: Any = MemoryNonceLedger()
            ledger.consume_once(request["approval"]["nonce"])
        elif scenario == "nonce_failure":
            ledger = FailingNonceLedger()
        else:
            ledger = MemoryNonceLedger()
        actual, dispatcher = evaluate_approval(request, ledger)
        if actual == "PASSED":
            nonce_outcome = "CONSUMED"
        elif actual == "APPROVAL_NONCE_REUSED":
            nonce_outcome = "REUSED_REJECTED"
        elif actual == "APPROVAL_NONCE_CONSUME_FAILED":
            nonce_outcome = "CONSUME_FAILED"
    expected = case.get("expected_result", case.get("expected_error", ""))
    return {
        "id": case["id"],
        "kind": case["kind"],
        "scenario": scenario,
        "status": "PASSED" if actual == expected else "FAILED",
        "expected": expected,
        "actual": actual,
        "nonce_outcome": nonce_outcome,
        "dispatcher": dispatcher.public_counts(),
    }


def validate_suite(suite: dict[str, Any]) -> None:
    if set(suite) != {"suite_id", "suite_version", "schema_ref", "cases"}:
        raise ValueError("suite top-level fields do not match the closed manifest")
    if suite["suite_id"] != EXPECTED_SUITE_ID or suite["suite_version"] != EXPECTED_SUITE_VERSION:
        raise ValueError("unsupported suite identity or version")
    if suite["schema_ref"] != SCHEMA_REF:
        raise ValueError("suite schema_ref does not match the trusted schema")
    if next(default_validator().iter_errors(suite), None) is not None:
        raise ValueError("suite does not satisfy the closed schema")
    catalog = []
    for item in suite["cases"]:
        expected = item.get("expected_result", item.get("expected_error"))
        catalog.append((item["id"], item["kind"], expected))
    if tuple(catalog) != EXPECTED_CASE_CATALOG:
        raise ValueError("suite cases do not match the exact case catalog")


def validate_command_network_suite(suite: dict[str, Any]) -> None:
    if set(suite) != {"suite_id", "suite_version", "schema_ref", "catalog", "cases"}:
        raise ValueError("command/network suite fields do not match the closed manifest")
    if (
        suite["suite_id"] != EXPECTED_COMMAND_NETWORK_SUITE_ID
        or suite["suite_version"] != EXPECTED_SUITE_VERSION
        or suite["schema_ref"] != SCHEMA_REF
    ):
        raise ValueError("unsupported command/network suite identity or version")
    if next(default_validator().iter_errors(suite), None) is not None:
        raise ValueError("command/network suite does not satisfy the closed schema")
    expected_catalog = {
        "commands": {
            "policy-tests": {
                "id": "policy-tests",
                "command": "python -m unittest tests/policy_contract/test_resource.py -v",
                "cwd": ".",
            }
        },
        "network_destinations": {
            "api.example.com": "PUBLIC",
            "api.example.com:443": "PUBLIC",
            "10.0.0.1": "PRIVATE",
            "127.0.0.1": "LOOPBACK",
            "169.254.1.1": "LINK_LOCAL",
            "metadata.google.internal": "METADATA",
        },
    }
    if suite["catalog"] != expected_catalog:
        raise ValueError("command/network suite catalog does not match the trusted catalog")
    for command_id, record in suite["catalog"]["commands"].items():
        if record["id"] != command_id:
            raise ValueError("command catalog key and record id must match exactly")
        validate_command_cwd(record["cwd"])
    for host in suite["catalog"]["network_destinations"]:
        require_canonical_host_port_literal(host)
    case_catalog = tuple(
        (item["id"], item["kind"], item.get("expected_result", item.get("expected_error")))
        for item in suite["cases"]
    )
    if case_catalog != COMMAND_NETWORK_EXPECTED_CASE_CATALOG:
        raise ValueError("command/network cases do not match the exact case catalog")


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    actual = "RUNNER_ERROR"
    probes = ProbeSet()
    try:
        validator = default_validator()
        case_validator = validator.evolve(schema=validator.schema["$defs"]["resource_case"])
        if next(case_validator.iter_errors(case), None) is not None:
            raise PolicyError("RESOURCE_SCHEMA_INVALID")
        actual, probes = evaluate_resource(case["request"])
    except PolicyError as exc:
        actual = exc.code
    expected = case.get("expected_result", case.get("expected_error", ""))
    return {
        "id": str(case.get("id", "")),
        "kind": str(case.get("kind", "")),
        "status": "PASSED" if actual == expected else "FAILED",
        "expected": str(expected),
        "actual": actual,
        "probes": probes.public_counts(),
    }


def run_command_network_case(case: dict[str, Any]) -> dict[str, Any]:
    actual = "RUNNER_ERROR"
    adapter = SpyAdapter()
    try:
        validator = default_validator()
        case_validator = validator.evolve(
            schema=validator.schema["$defs"]["command_network_case"]
        )
        if next(case_validator.iter_errors(case), None) is not None:
            raise PolicyError("COMMAND_NETWORK_SCHEMA_INVALID")
        actual, adapter = evaluate_command_network(case["request"])
    except PolicyError as exc:
        actual = exc.code
    expected = case.get("expected_result", case.get("expected_error", ""))
    return {
        "id": str(case.get("id", "")),
        "kind": str(case.get("kind", "")),
        "status": "PASSED" if actual == expected else "FAILED",
        "expected": str(expected),
        "actual": actual,
        "adapter": adapter.public_counts(),
    }


def selected_cases(suite: dict[str, Any], command_id: str) -> list[dict[str, Any]]:
    protected = command_id == "protected-read-negative"
    return [item for item in suite["cases"] if (item["id"] in PROTECTED_CASE_IDS) is protected]


def public_result(
    command_id: str,
    schema_path: Path,
    suite_path: Path,
    cases: list[dict[str, Any]],
    *,
    runner_error: str | None = None,
) -> dict[str, Any]:
    passed = sum(case["status"] == "PASSED" for case in cases)
    protected_cases = [case for case in cases if case["id"] in PROTECTED_CASE_IDS]
    protected_probe_fields = (
        "reader_calls",
        "model_context_writes",
        "log_writes",
        "evidence_writes",
        "sentinel_occurrences",
    )
    protected_denial_zero_probes = all(
        all(case["probes"].get(field) == 0 for field in protected_probe_fields)
        for case in protected_cases
    )
    result: dict[str, Any] = {
        "command_id": command_id,
        "schema_sha256": file_sha256(schema_path) if schema_path.is_file() else None,
        "suite_sha256": file_sha256(suite_path) if suite_path.is_file() else None,
        "observed_at": utc_now(),
        "catalog_match": not runner_error,
        "summary": {"total": len(cases), "passed": passed, "failed": len(cases) - passed},
        "cases": cases,
    }
    if runner_error:
        result["runner_error"] = runner_error
    raw_sentinel = _SENTINEL.decode("ascii") in json.dumps(
        result, ensure_ascii=False, sort_keys=True
    )
    result["assertions"] = {
        "protected_denial_zero_probes": protected_denial_zero_probes,
        "no_raw_sentinel": not raw_sentinel,
    }
    result["sentinel_raw_value_recorded"] = raw_sentinel
    result["status"] = (
        "PASSED"
        if (
            not runner_error
            and passed == len(cases)
            and protected_denial_zero_probes
            and not raw_sentinel
        )
        else "FAILED"
    )
    return result


def command_network_public_result(
    schema_path: Path,
    suite_path: Path,
    cases: list[dict[str, Any]],
    *,
    runner_error: str | None = None,
) -> dict[str, Any]:
    passed = sum(case["status"] == "PASSED" for case in cases)
    negative_zero_adapter_calls = all(
        case["adapter"]["adapter_calls"] == 0
        for case in cases
        if case["kind"] == "negative"
    )
    positive_single_adapter_call = all(
        case["adapter"]["adapter_calls"] == 1
        for case in cases
        if case["kind"] == "positive"
    )
    no_process_calls = all(case["adapter"]["process_calls"] == 0 for case in cases)
    no_dns_calls = all(case["adapter"]["dns_calls"] == 0 for case in cases)
    no_socket_calls = all(case["adapter"]["socket_calls"] == 0 for case in cases)
    result: dict[str, Any] = {
        "command_id": COMMAND_NETWORK_COMMAND_ID,
        "schema_sha256": file_sha256(schema_path) if schema_path.is_file() else None,
        "suite_sha256": file_sha256(suite_path) if suite_path.is_file() else None,
        "observed_at": utc_now(),
        "catalog_match": not runner_error,
        "summary": {"total": len(cases), "passed": passed, "failed": len(cases) - passed},
        "cases": cases,
        "assertions": {
            "negative_zero_adapter_calls": negative_zero_adapter_calls,
            "positive_single_adapter_call": positive_single_adapter_call,
            "no_process_calls": no_process_calls,
            "no_dns_calls": no_dns_calls,
            "no_socket_calls": no_socket_calls,
        },
    }
    if runner_error:
        result["runner_error"] = runner_error
    result["status"] = (
        "PASSED"
        if (
            not runner_error
            and passed == len(cases)
            and negative_zero_adapter_calls
            and positive_single_adapter_call
            and no_process_calls
            and no_dns_calls
            and no_socket_calls
        )
        else "FAILED"
    )
    return result


def approval_public_result(
    schema_path: Path,
    suite_path: Path,
    cases: list[dict[str, Any]],
    *,
    runner_error: str | None = None,
) -> dict[str, Any]:
    forbidden_material_fields = {
        "approval",
        "approval_token",
        "credential",
        "effect_hash",
        "nonce",
        "payload",
        "signature",
        "signature_ref",
    }

    def contains_approval_material(value: Any) -> bool:
        if isinstance(value, dict):
            return any(
                key in forbidden_material_fields or contains_approval_material(item)
                for key, item in value.items()
            )
        if isinstance(value, list):
            return any(contains_approval_material(item) for item in value)
        return False

    passed = sum(case["status"] == "PASSED" for case in cases)
    negative_zero_dispatch = all(
        case["dispatcher"]["dispatcher_calls"] == 0
        for case in cases
        if case["kind"] == "negative"
    )
    permitted_single_dispatch = all(
        case["dispatcher"]["dispatcher_calls"] == 1
        for case in cases
        if case["kind"] == "positive" and case["scenario"] == "evaluate"
    )
    no_real_effects = all(
        all(
            case["dispatcher"][field] == 0
            for field in (
                "external_effect_calls",
                "process_calls",
                "network_calls",
                "store_calls",
            )
        )
        for case in cases
    )
    atomic_single_consume = all(
        case["nonce_outcome"] == "ATOMIC_SINGLE_CONSUME"
        for case in cases
        if case["scenario"] == "concurrent"
    )
    no_approval_material_fields = not contains_approval_material(cases)
    result: dict[str, Any] = {
        "command_id": APPROVAL_COMMAND_ID,
        "schema_sha256": file_sha256(schema_path) if schema_path.is_file() else None,
        "suite_sha256": file_sha256(suite_path) if suite_path.is_file() else None,
        "observed_at": utc_now(),
        "catalog_match": not runner_error,
        "summary": {"total": len(cases), "passed": passed, "failed": len(cases) - passed},
        "cases": cases,
        "assertions": {
            "negative_zero_dispatcher_calls": negative_zero_dispatch,
            "permitted_single_spy_dispatch": permitted_single_dispatch,
            "atomic_single_nonce_consume": atomic_single_consume,
            "no_real_effect_calls": no_real_effects,
            "no_approval_material_fields": no_approval_material_fields,
        },
    }
    if runner_error:
        result["runner_error"] = runner_error
    result["status"] = (
        "PASSED"
        if (
            not runner_error
            and passed == len(cases)
            and negative_zero_dispatch
            and permitted_single_dispatch
            and atomic_single_consume
            and no_real_effects
            and no_approval_material_fields
        )
        else "FAILED"
    )
    return result


def validate_registered_result_ref(result_ref: str, command_id: str) -> str:
    validate_literal_root_relative(result_ref)
    lowered_parts = tuple(part.lower() for part in PurePosixPath(result_ref).parts)
    if (
        ".git" in lowered_parts
        or "protected" in lowered_parts
        or any(
            part == ".env"
            or part.startswith(".env.")
            or "credential" in part
            or "secret" in part
            for part in lowered_parts
        )
    ):
        raise ValueError("result path cannot target a protected resource")
    expected = EXPECTED_RESULT_REFS[command_id]
    if result_ref != expected:
        raise ValueError("result path does not match the registered command output")
    return expected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="branch", required=True)
    resource = subparsers.add_parser("resource", help="verify the RESOURCE authority branch")
    resource.add_argument("--schema", required=True)
    resource.add_argument("--suite", required=True)
    resource.add_argument("--result", required=True)
    resource.add_argument("--command-id", required=True, choices=sorted(RESOURCE_COMMAND_IDS))
    command_network = subparsers.add_parser(
        "command-network", help="verify COMMAND and NETWORK authority branches"
    )
    command_network.add_argument("--schema", required=True)
    command_network.add_argument("--suite", required=True)
    command_network.add_argument("--result", required=True)
    command_network.add_argument(
        "--command-id", required=True, choices=[COMMAND_NETWORK_COMMAND_ID]
    )
    approval = subparsers.add_parser(
        "approval", help="verify destructive/external approval effect gates"
    )
    approval.add_argument("--schema", required=True)
    approval.add_argument("--suite", required=True)
    approval.add_argument("--result", required=True)
    approval.add_argument("--command-id", required=True, choices=[APPROVAL_COMMAND_ID])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schema_path = ROOT / SCHEMA_REF
    suite_ref = {
        "resource": RESOURCE_SUITE_REF,
        "command-network": COMMAND_NETWORK_SUITE_REF,
        "approval": APPROVAL_SUITE_REF,
    }[args.branch]
    suite_path = ROOT / suite_ref
    expected_result_ref = EXPECTED_RESULT_REFS[args.command_id]
    result_path = ROOT / expected_result_ref
    try:
        if args.schema != SCHEMA_REF or args.suite != suite_ref:
            raise ValueError("runner paths must name the trusted branch fixture")
        validate_registered_result_ref(args.result, args.command_id)
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        suite = load_json(suite_path)
        if args.branch == "resource":
            validate_suite(suite)
            cases = [run_case(item) for item in selected_cases(suite, args.command_id)]
            result = public_result(args.command_id, schema_path, suite_path, cases)
        elif args.branch == "command-network":
            validate_command_network_suite(suite)
            cases = [run_command_network_case(item) for item in suite["cases"]]
            result = command_network_public_result(schema_path, suite_path, cases)
        else:
            validate_approval_suite(suite)
            cases = [run_approval_case(suite, item) for item in suite["cases"]]
            result = approval_public_result(schema_path, suite_path, cases)
        atomic_write(result_path, json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 0 if result["status"] == "PASSED" else 1
    except Exception:
        if args.branch == "resource":
            result = public_result(
                args.command_id, schema_path, suite_path, [], runner_error="RUNNER_CONTRACT_INVALID"
            )
        elif args.branch == "command-network":
            result = command_network_public_result(
                schema_path, suite_path, [], runner_error="RUNNER_CONTRACT_INVALID"
            )
        else:
            result = approval_public_result(
                schema_path, suite_path, [], runner_error="RUNNER_CONTRACT_INVALID"
            )
        atomic_write(result_path, json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
