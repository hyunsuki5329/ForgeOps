"""Exact W9 command registry and committed source resolution."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
import subprocess
from typing import Mapping, Sequence

from .model import SafetyError, canonical_json_bytes


EXPECTED_COMMANDS = (
    ("VG-005", "forgeops-authority-resource", "resource-authority-negative", "E2"),
    ("VG-005", "forgeops-authority-resource", "protected-read-negative", "E2"),
    ("VG-006", "forgeops-authority-command-network", "command-network-negative", "E2"),
    ("VG-007", "forgeops-approval-policy", "approval-negative-fixture", "E2"),
    ("VG-008", "forgeops-sandbox-security", "image-provenance-negative", "E3"),
    ("VG-008", "forgeops-sandbox-security", "containment-egress-negative", "E3"),
    ("VG-008", "forgeops-sandbox-security", "teardown-negative", "E3"),
    ("VG-009", "forgeops-secret-artifact-security", "secret-surface-negative", "E3"),
    ("VG-009", "forgeops-secret-artifact-security", "artifact-isolation-negative", "E3"),
    ("VG-010", "forgeops-snapshot-baseline", "snapshot-identity", "E2"),
    ("VG-010", "forgeops-snapshot-baseline", "baseline-retrieval-repeat", "E2"),
    ("VG-011", "forgeops-context-security", "context-provenance", "E2"),
    ("VG-011", "forgeops-context-security", "injection-negative", "E2"),
    ("VG-012", "forgeops-local-vertical", "main-part-work-main", "E2"),
    ("VG-013", "forgeops-patch-verification", "task-checks", "E2"),
    ("VG-013", "forgeops-patch-verification", "regression-checks", "E2"),
    ("VG-013", "forgeops-patch-verification", "verification-anti-tamper", "E2"),
    ("VG-014", "forgeops-lifecycle-budget", "budget-cancel-negative", "E2"),
    ("VG-014", "forgeops-lifecycle-budget", "no-progress-stop", "E2"),
    ("VG-015", "forgeops-trace-manifest", "trace-manifest-completeness", "E2"),
    ("VG-015", "forgeops-trace-manifest", "external-write-negative", "E2"),
    ("VG-023", "forgeops-evidence-contract", "evidence-positive-negative", "E2"),
    ("VG-023", "forgeops-evidence-contract", "extension-provenance", "E2"),
)

SECURITY_NEGATIVE_COMMANDS = tuple(
    command
    for _, _, command, _ in EXPECTED_COMMANDS
    if command not in {"snapshot-identity", "baseline-retrieval-repeat", "main-part-work-main"}
)
REQUIRED_EVIDENCE_COMMANDS = tuple(
    command
    for _, _, command, _ in EXPECTED_COMMANDS
    if command
    not in {
        "resource-authority-negative",
        "protected-read-negative",
        "command-network-negative",
        "approval-negative-fixture",
    }
)

_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_FIELD = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")
_MODES = {"blob", "artifact", "framed"}
_MAX_BLOB_BYTES = 8 * 1024 * 1024
_CANONICAL_REGISTRY_SHA256 = "24e435dfbec2f7daf7c21278bf16f0f2524ba6f00f1d6fb21c6c02294e19a03d"


@dataclass(frozen=True)
class HashBinding:
    field: str
    mode: str
    refs: tuple[str, ...]


@dataclass(frozen=True)
class Registration:
    gate_id: str
    profile_id: str
    command_id: str
    artifact_ref: str
    required_tier: str
    observed_at_field: str
    input_bindings: tuple[HashBinding, ...]

    @property
    def input_refs(self) -> tuple[str, ...]:
        return tuple(ref for binding in self.input_bindings for ref in binding.refs)

    @property
    def hash_fields(self) -> tuple[str, ...]:
        return tuple(binding.field for binding in self.input_bindings)


def _safe_ref(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or value.startswith("/")
        or _WINDOWS_ABSOLUTE.match(value)
        or "*" in value
        or "?" in value
    ):
        raise SafetyError("REGISTRY_INVALID")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise SafetyError("REGISTRY_INVALID")
    return value


def registry_sha256(suite: Mapping[str, object]) -> str:
    return hashlib.sha256(canonical_json_bytes(suite)).hexdigest()


def load_registry(suite: Mapping[str, object]) -> tuple[Registration, ...]:
    if not isinstance(suite, Mapping) or set(suite) != {
        "suite_id",
        "suite_version",
        "phase_id",
        "freshness_seconds",
        "registrations",
        "subsets",
    }:
        raise SafetyError("REGISTRY_INVALID")
    if (
        suite["suite_id"] != "forgeops-phase1-safety-v1"
        or suite["suite_version"] != "1.0"
        or suite["phase_id"] != "phase-1-safety"
        or suite["freshness_seconds"] != 300
        or not isinstance(suite["registrations"], list)
        or not isinstance(suite["subsets"], Mapping)
        or set(suite["subsets"]) != {"security_negative", "required_evidence"}
        or tuple(suite["subsets"]["security_negative"]) != SECURITY_NEGATIVE_COMMANDS
        or tuple(suite["subsets"]["required_evidence"]) != REQUIRED_EVIDENCE_COMMANDS
    ):
        raise SafetyError("REGISTRY_INVALID")

    observed = tuple(
        (item.get("gate_id"), item.get("profile_id"), item.get("command_id"), item.get("required_tier"))
        for item in suite["registrations"]
        if isinstance(item, Mapping)
    )
    if observed != EXPECTED_COMMANDS or len(suite["registrations"]) != len(EXPECTED_COMMANDS):
        raise SafetyError("REGISTRY_INVALID")
    if registry_sha256(suite) != _CANONICAL_REGISTRY_SHA256:
        raise SafetyError("REGISTRY_INVALID")

    registrations: list[Registration] = []
    artifact_refs: set[str] = set()
    for item in suite["registrations"]:
        if not isinstance(item, Mapping) or set(item) != {
            "gate_id",
            "profile_id",
            "command_id",
            "artifact_ref",
            "required_tier",
            "observed_at_field",
            "input_bindings",
        }:
            raise SafetyError("REGISTRY_INVALID")
        artifact_ref = _safe_ref(item["artifact_ref"])
        if artifact_ref in artifact_refs or item["observed_at_field"] != "observed_at":
            raise SafetyError("REGISTRY_INVALID")
        artifact_refs.add(artifact_ref)
        if not isinstance(item["input_bindings"], list) or not item["input_bindings"]:
            raise SafetyError("REGISTRY_INVALID")
        bindings: list[HashBinding] = []
        fields: set[str] = set()
        refs_seen: set[str] = set()
        for binding in item["input_bindings"]:
            if not isinstance(binding, Mapping) or set(binding) != {"field", "mode", "refs"}:
                raise SafetyError("REGISTRY_INVALID")
            field = binding["field"]
            mode = binding["mode"]
            refs = binding["refs"]
            if (
                not isinstance(field, str)
                or not _FIELD.fullmatch(field)
                or field in fields
                or mode not in _MODES
                or not isinstance(refs, list)
                or not refs
                or (mode != "framed" and len(refs) != 1)
            ):
                raise SafetyError("REGISTRY_INVALID")
            safe_refs = tuple(_safe_ref(ref) for ref in refs)
            if refs_seen.intersection(safe_refs):
                raise SafetyError("REGISTRY_INVALID")
            if mode == "artifact" and any(not ref.startswith("artifacts/runtime/") for ref in safe_refs):
                raise SafetyError("REGISTRY_INVALID")
            if mode != "artifact" and any(ref.startswith("artifacts/") for ref in safe_refs):
                raise SafetyError("REGISTRY_INVALID")
            fields.add(field)
            refs_seen.update(safe_refs)
            bindings.append(HashBinding(field=field, mode=mode, refs=safe_refs))
        registrations.append(
            Registration(
                gate_id=item["gate_id"],
                profile_id=item["profile_id"],
                command_id=item["command_id"],
                artifact_ref=artifact_ref,
                required_tier=item["required_tier"],
                observed_at_field=item["observed_at_field"],
                input_bindings=tuple(bindings),
            )
        )
    return tuple(registrations)


def _committed_bytes(root: Path, ref: str) -> bytes:
    safe_ref = _safe_ref(ref)
    path = root / PurePosixPath(safe_ref)
    if not path.is_file() or path.is_symlink():
        raise SafetyError("SOURCE_IDENTITY_UNAVAILABLE")
    try:
        kind = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-t", f"HEAD:{safe_ref}"],
            check=False,
            capture_output=True,
            timeout=5,
        )
        blob = subprocess.run(
            ["git", "-C", str(root), "cat-file", "blob", f"HEAD:{safe_ref}"],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise SafetyError("SOURCE_IDENTITY_UNAVAILABLE") from error
    if kind.returncode != 0 or kind.stdout.strip() != b"blob" or blob.returncode != 0:
        raise SafetyError("SOURCE_IDENTITY_UNAVAILABLE")
    if len(blob.stdout) > _MAX_BLOB_BYTES:
        raise SafetyError("SOURCE_IDENTITY_UNAVAILABLE")
    try:
        working = path.read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    except (OSError, UnicodeError) as error:
        raise SafetyError("SOURCE_IDENTITY_UNAVAILABLE") from error
    if working != blob.stdout:
        raise SafetyError("SOURCE_HASH_MISMATCH")
    return blob.stdout


def resolve_committed_sha256(root: Path, ref: str) -> str:
    return hashlib.sha256(_committed_bytes(root, ref)).hexdigest()


def resolve_framed_sha256(root: Path, refs: Sequence[str]) -> str:
    if not refs:
        raise SafetyError("SOURCE_IDENTITY_UNAVAILABLE")
    digest = hashlib.sha256()
    for ref in refs:
        safe_ref = _safe_ref(ref)
        content = _committed_bytes(root, safe_ref)
        digest.update(safe_ref.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()
