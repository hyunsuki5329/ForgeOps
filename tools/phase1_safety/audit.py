"""Fail-closed reduction of registered Phase 1 safety evidence."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Callable, Mapping, Sequence
from urllib.parse import urlsplit

from .model import SafetyError, SourceIdentity, parse_utc, utc_text
from .registry import (
    HashBinding,
    Registration,
    REQUIRED_EVIDENCE_COMMANDS,
    SECURITY_NEGATIVE_COMMANDS,
    _CANONICAL_REGISTRY_SHA256,
    resolve_committed_sha256,
    resolve_framed_sha256,
)
from tools.sandbox_security.e3_attestation import (
    DEFAULT_PROCESS_RUNNER,
    E3Error,
    ExpectedIdentity,
    ProcessRunner,
    verify_signed_attestation,
)


_TIERS = {"E0": 0, "E1": 1, "E2": 2, "E3": 3}
_FORBIDDEN_KEYS = {
    "request",
    "response",
    "body",
    "headers",
    "payload",
    "raw",
    "raw_log",
    "credential",
    "token",
    "secret",
    "private",
    "exception",
}
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_SYNTHETIC_MARKER = re.compile(r"(?:^|[_<\s-])synthetic(?:[_>\s-]|$)", re.IGNORECASE)
_ACTIVE_CONTENT = re.compile(r"<(?:script|form)\b|\bon[a-z]+\s*=", re.IGNORECASE)
_ENVIRONMENT_NAME = re.compile(r"(?:^|[^A-Za-z0-9])(?:FORGEOPS|GITHUB|AWS|AZURE|GOOGLE)_[A-Z0-9_]+(?:$|[^A-Za-z0-9])")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_MAX_COUNTER = 2**31 - 1

_POLICY_FIELDS = {
    "resource-authority-negative": {
        "assertions", "cases", "catalog_match", "command_id", "observed_at", "schema_sha256",
        "sentinel_raw_value_recorded", "status", "suite_sha256", "summary",
    },
    "protected-read-negative": {
        "assertions", "cases", "catalog_match", "command_id", "observed_at", "schema_sha256",
        "sentinel_raw_value_recorded", "status", "suite_sha256", "summary",
    },
    "command-network-negative": {
        "assertions", "cases", "catalog_match", "command_id", "observed_at", "schema_sha256",
        "status", "suite_sha256", "summary",
    },
    "approval-negative-fixture": {
        "assertions", "cases", "catalog_match", "command_id", "observed_at", "schema_sha256",
        "status", "suite_sha256", "summary",
    },
}
_ASSERTION_RESULT_FIELDS = {
    "secret-surface-negative": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
    "artifact-isolation-negative": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
    "evidence-positive-negative": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
    "extension-provenance": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
}
_MODERN_FIELDS = {
    "snapshot-identity": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_id", "result_version", "status", "summary"},
    "baseline-retrieval-repeat": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_id", "result_version", "status", "summary"},
    "context-provenance": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_id", "result_version", "status", "summary"},
    "injection-negative": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_id", "result_version", "status", "summary"},
    "task-checks": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_digest", "profile_id", "result_version", "status", "summary"},
    "regression-checks": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_digest", "profile_id", "result_version", "status", "summary"},
    "verification-anti-tamper": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_digest", "profile_id", "result_version", "status", "summary"},
    "budget-cancel-negative": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_id", "result_version", "status", "summary"},
    "no-progress-stop": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_id", "result_version", "status", "summary"},
    "trace-manifest-completeness": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_id", "result_version", "status", "summary"},
    "external-write-negative": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_id", "result_version", "status", "summary"},
    "main-part-work-main": {"cases", "command_id", "effect_counters", "evidence_tier", "gate_id", "input_hashes", "observed_at", "profile_id", "result_version", "status", "summary"},
}
_ASSERTION_KEYS = {
    "resource-authority-negative": {"no_raw_sentinel", "protected_denial_zero_probes"},
    "protected-read-negative": {"no_raw_sentinel", "protected_denial_zero_probes"},
    "command-network-negative": {"negative_zero_adapter_calls", "no_dns_calls", "no_process_calls", "no_socket_calls", "positive_single_adapter_call"},
    "approval-negative-fixture": {"atomic_single_nonce_consume", "negative_zero_dispatcher_calls", "no_approval_material_fields", "no_real_effect_calls", "permitted_single_spy_dispatch"},
    "secret-surface-negative": {"negative_export_calls", "negative_publish_calls", "negative_raw_occurrences", "negative_store_calls", "no_sensitive_content"},
    "artifact-isolation-negative": {"negative_export_calls", "negative_publish_calls", "negative_raw_occurrences", "negative_store_calls", "no_sensitive_content"},
    "evidence-positive-negative": {"negative_accept_calls", "negative_append_calls", "no_sensitive_content"},
    "extension-provenance": {"negative_accept_calls", "negative_append_calls", "no_sensitive_content"},
}
_EFFECT_KEYS = {
    "snapshot-identity": {"external_writes", "network_calls", "protected_reads", "source_writes"},
    "baseline-retrieval-repeat": {"external_writes", "network_calls", "protected_reads", "source_writes"},
    "context-provenance": {"external_writes", "network_calls", "protected_reads", "source_writes"},
    "injection-negative": {"external_writes", "network_calls", "protected_reads", "source_writes"},
    "task-checks": {"host_external_writes", "network_calls", "outside_workspace_write_attempts", "remote_write_attempts", "result_artifact_raw_secret_occurrences", "source_tree_hash_unchanged", "unauthorized_workspace_effects"},
    "regression-checks": {"host_external_writes", "network_calls", "outside_workspace_write_attempts", "remote_write_attempts", "result_artifact_raw_secret_occurrences", "source_tree_hash_unchanged", "unauthorized_workspace_effects"},
    "verification-anti-tamper": {"host_external_writes", "network_calls", "outside_workspace_write_attempts", "remote_write_attempts", "result_artifact_raw_secret_occurrences", "source_tree_hash_unchanged", "unauthorized_workspace_effects"},
    "budget-cancel-negative": {"adapter_cleanup_residues", "external_write_attempts", "network_calls", "os_mount_residue", "os_process_tree_residue", "result_artifact_raw_secret_occurrences", "source_tree_hash_unchanged", "unauthorized_dispatches"},
    "no-progress-stop": {"adapter_cleanup_residues", "external_write_attempts", "network_calls", "os_mount_residue", "os_process_tree_residue", "result_artifact_raw_secret_occurrences", "source_tree_hash_unchanged", "unauthorized_dispatches"},
    "trace-manifest-completeness": {"adapter_cleanup_residues", "external_write_attempts", "network_calls", "os_mount_residue", "os_process_tree_residue", "result_artifact_raw_secret_occurrences", "source_tree_hash_unchanged", "unauthorized_dispatches"},
    "external-write-negative": {"adapter_cleanup_residues", "external_write_attempts", "network_calls", "os_mount_residue", "os_process_tree_residue", "result_artifact_raw_secret_occurrences", "source_tree_hash_unchanged", "unauthorized_dispatches"},
    "main-part-work-main": {"external_writes", "network_calls", "protected_reads", "result_artifact_raw_secret_occurrences", "source_tree_hash_unchanged", "unauthorized_fixture_effects"},
}

E3_RECEIPT_REF = "artifacts/runtime/sandbox-e3-import-receipt.json"
E3_ATTESTATION_REF = "artifacts/runtime/e3-attestation.json"
E3_BUNDLE_REF = "artifacts/runtime/e3-attestation.bundle.json"
E3_PROFILE_REF = "artifacts/runtime/sandbox-runtime-profile.json"
E3_OBSERVATIONS_REF = "artifacts/runtime/sandbox-runtime-observations.json"
_E3_RECEIPT_FIELDS = {
    "receipt_version", "attestation_sha256", "bundle_sha256", "repository",
    "repository_id", "default_branch", "workflow_ref", "source_sha", "workflow_sha",
    "run_id", "run_attempt", "image_ref", "image_digest", "issuer",
    "certificate_identity", "observed_at", "verification_kind",
    "runtime_profile_sha256", "runtime_observations_sha256",
}


@dataclass
class EffectCounters:
    unauthorized_executions: int = 0
    approval_bypasses: int = 0
    containment_or_egress_escapes: int = 0
    injection_acceptances: int = 0
    raw_secret_occurrences: int = 0
    cleanup_failures: int = 0
    evidence_integrity_failures: int = 0
    external_writes: int = 0

    def add(self, other: "EffectCounters") -> None:
        for name in asdict(self):
            setattr(self, name, getattr(self, name) + getattr(other, name))

    def any_observed(self) -> bool:
        return any(asdict(self).values())


@dataclass(frozen=True)
class GateAudit:
    row: dict[str, object]
    blockers: tuple[dict[str, str], ...]
    effects: EffectCounters


BindingResolver = Callable[[Path, HashBinding], str]
SourceChecker = Callable[[Path, SourceIdentity], bool]
ReceiptValidator = Callable[[Path, SourceIdentity, datetime], bool]


def validate_e3_receipt(
    root: Path,
    source_identity: SourceIdentity,
    validated_at: datetime,
    *,
    e3_receipt_ref: str = E3_RECEIPT_REF,
    runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
) -> bool:
    """Validate the imported E3 receipt against exact signed runtime bytes."""

    if e3_receipt_ref != E3_RECEIPT_REF:
        return False
    try:
        paths = {
            "receipt": root / e3_receipt_ref,
            "attestation": root / E3_ATTESTATION_REF,
            "bundle": root / E3_BUNDLE_REF,
            "profile": root / E3_PROFILE_REF,
            "observations": root / E3_OBSERVATIONS_REF,
        }
        if any(not path.is_file() or path.is_symlink() for path in paths.values()):
            return False
        receipt = json.loads(paths["receipt"].read_text(encoding="utf-8"))
        if not isinstance(receipt, Mapping) or set(receipt) != _E3_RECEIPT_FIELDS:
            return False
        expected_fields = {
            "repository": source_identity.repository,
            "repository_id": source_identity.repository_id,
            "default_branch": source_identity.default_branch,
            "workflow_ref": source_identity.workflow_ref,
            "source_sha": source_identity.source_sha,
            "workflow_sha": source_identity.workflow_sha,
            "run_id": source_identity.run_id,
            "run_attempt": source_identity.run_attempt,
        }
        if any(receipt.get(key) != value for key, value in expected_fields.items()):
            return False
        if receipt.get("receipt_version") != "1.0" or receipt.get("verification_kind") != "runtime":
            return False
        observed = parse_utc(receipt.get("observed_at"))
        if not 0 <= (validated_at - observed).total_seconds() <= 300:
            return False
        hash_fields = {
            "attestation_sha256": paths["attestation"],
            "bundle_sha256": paths["bundle"],
            "runtime_profile_sha256": paths["profile"],
            "runtime_observations_sha256": paths["observations"],
        }
        for field, path in hash_fields.items():
            if receipt.get(field) != hashlib.sha256(path.read_bytes()).hexdigest():
                return False
        image_ref = receipt.get("image_ref")
        image_digest = receipt.get("image_digest")
        if not isinstance(image_ref, str) or not isinstance(image_digest, str):
            return False
        identity = ExpectedIdentity(
            source_identity.repository,
            source_identity.repository_id,
            source_identity.default_branch,
            source_identity.source_sha,
            source_identity.workflow_sha,
            source_identity.run_id,
            source_identity.run_attempt,
            image_ref,
            image_digest,
        )
        if receipt.get("issuer") != "https://token.actions.githubusercontent.com":
            return False
        if receipt.get("certificate_identity") != identity.certificate_identity:
            return False
        attestation = verify_signed_attestation(
            paths["attestation"], paths["bundle"], identity, runner, validated_at
        )
        return all(attestation.get(key) == receipt.get(key) for key in (
            "repository", "repository_id", "workflow_ref", "source_sha", "workflow_sha",
            "run_id", "run_attempt", "image_ref", "image_digest", "issuer",
            "certificate_identity", "observed_at",
        ))
    except (OSError, UnicodeError, json.JSONDecodeError, SafetyError, E3Error, TypeError, ValueError):
        return False


def _get_dotted(value: object, dotted: str) -> object:
    current = value
    for part in dotted.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise SafetyError("ARTIFACT_INVALID")
        current = current[part]
    return current


def _counter(value: object) -> int:
    if type(value) is not int or value < 0 or value > _MAX_COUNTER:
        raise SafetyError("OBSERVATION_UNAVAILABLE")
    return value


def _is_unsafe_string(value: str) -> bool:
    if (
        _SYNTHETIC_MARKER.search(value)
        or _ACTIVE_CONTENT.search(value)
        or _ENVIRONMENT_NAME.search(value)
        or value.startswith(("/", "\\"))
        or _WINDOWS_ABSOLUTE.match(value)
    ):
        return True
    parsed = urlsplit(value)
    return bool(parsed.scheme)


def _assert_public_safe(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str) or key.lower() in _FORBIDDEN_KEYS:
                raise SafetyError("ARTIFACT_NOT_PUBLIC_SAFE")
            _assert_public_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_public_safe(nested)
    elif isinstance(value, str):
        if _is_unsafe_string(value):
            raise SafetyError("ARTIFACT_NOT_PUBLIC_SAFE")
    elif not isinstance(value, (int, float, bool, type(None))):
        raise SafetyError("ARTIFACT_NOT_PUBLIC_SAFE")


def _expected_hash_tree(registration: Registration) -> dict[str, object]:
    tree: dict[str, object] = {}
    for field in registration.hash_fields:
        current = tree
        parts = field.split(".")
        for part in parts[:-1]:
            nested = current.setdefault(part, {})
            if not isinstance(nested, dict):
                raise SafetyError("REGISTRY_INVALID")
            current = nested
        current[parts[-1]] = None
    return tree


def _assert_hash_tree(value: object, expected: Mapping[str, object]) -> None:
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise SafetyError("ARTIFACT_INVALID")
    for key, nested_expected in expected.items():
        nested = value[key]
        if nested_expected is None:
            if not isinstance(nested, str) or not _SHA256.fullmatch(nested):
                raise SafetyError("ARTIFACT_INVALID")
        else:
            _assert_hash_tree(nested, nested_expected)


def _assert_summary(value: object, status: object) -> None:
    if not isinstance(value, Mapping) or set(value) != {"total", "passed", "failed"}:
        raise SafetyError("ARTIFACT_INVALID")
    total = _counter(value["total"])
    passed = _counter(value["passed"])
    failed = _counter(value["failed"])
    if total != passed + failed or (status == "PASSED" and failed != 0):
        raise SafetyError("ARTIFACT_INVALID")


def _assert_known_shape(artifact: Mapping[str, object], registration: Registration) -> None:
    command = registration.command_id
    if command in _POLICY_FIELDS:
        expected = _POLICY_FIELDS[command]
    elif command in _ASSERTION_RESULT_FIELDS:
        expected = _ASSERTION_RESULT_FIELDS[command]
    elif command in _MODERN_FIELDS:
        expected = _MODERN_FIELDS[command]
    elif registration.gate_id == "VG-008":
        expected = {
            "category", "command_id", "counts", "e3_runtime_assertion", "effect_counters",
            "input_hashes", "residue_counters", "result_version", "runtime", "status", "time",
        }
    else:
        raise SafetyError("ARTIFACT_INVALID")
    if set(artifact) != expected:
        raise SafetyError("ARTIFACT_INVALID")

    hash_tree = _expected_hash_tree(registration)
    for root_key, nested in hash_tree.items():
        if nested is None:
            observed = artifact.get(root_key)
            if not isinstance(observed, str) or not _SHA256.fullmatch(observed):
                raise SafetyError("ARTIFACT_INVALID")
        else:
            _assert_hash_tree(artifact.get(root_key), nested)

    if "summary" in artifact:
        _assert_summary(artifact["summary"], artifact.get("status"))
    if "cases" in artifact and not isinstance(artifact["cases"], list):
        raise SafetyError("ARTIFACT_INVALID")
    if command in _ASSERTION_KEYS:
        assertions = artifact.get("assertions")
        if not isinstance(assertions, Mapping) or set(assertions) != _ASSERTION_KEYS[command]:
            raise SafetyError("ARTIFACT_INVALID")
    if command in _EFFECT_KEYS:
        effects = artifact.get("effect_counters")
        if not isinstance(effects, Mapping) or set(effects) != _EFFECT_KEYS[command]:
            raise SafetyError("ARTIFACT_INVALID")
    if registration.gate_id == "VG-008":
        counts = artifact.get("counts")
        effects = artifact.get("effect_counters")
        residue = artifact.get("residue_counters")
        if (
            not isinstance(counts, Mapping)
            or set(counts) != {"cases_total", "failed", "not_run", "passed"}
            or not isinstance(effects, Mapping)
            or set(effects) != {"network_calls", "provision_calls", "write_calls"}
            or not isinstance(residue, Mapping)
            or set(residue) != {"leases", "mounts", "processes", "transient_secrets", "workspaces"}
        ):
            raise SafetyError("ARTIFACT_INVALID")
        values = {key: _counter(item) for key, item in counts.items()}
        if values["cases_total"] != values["passed"] + values["failed"] + values["not_run"]:
            raise SafetyError("ARTIFACT_INVALID")
        for item in effects.values():
            _counter(item)
        for item in residue.values():
            _counter(item)


def _default_binding_resolver(root: Path, binding: HashBinding) -> str:
    if binding.mode == "blob":
        return resolve_committed_sha256(root, binding.refs[0])
    if binding.mode == "framed":
        return resolve_framed_sha256(root, binding.refs)
    if binding.mode == "artifact":
        path = root / binding.refs[0]
        if not path.is_file() or path.is_symlink():
            raise SafetyError("ARTIFACT_MISSING")
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise SafetyError("ARTIFACT_INVALID") from error
    raise SafetyError("REGISTRY_INVALID")


def _default_source_checker(root: Path, identity: SourceIdentity) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == identity.source_sha


def _normalize_effects(artifact: Mapping[str, object], registration: Registration) -> EffectCounters:
    command = registration.command_id
    effects = EffectCounters()
    assertions = artifact.get("assertions") if isinstance(artifact.get("assertions"), Mapping) else {}
    counters = artifact.get("effect_counters") if isinstance(artifact.get("effect_counters"), Mapping) else {}

    if command in {"resource-authority-negative", "protected-read-negative"}:
        if assertions.get("protected_denial_zero_probes") is not True:
            effects.unauthorized_executions += 1
        if assertions.get("no_raw_sentinel") is not True or artifact.get("sentinel_raw_value_recorded") is not False:
            effects.raw_secret_occurrences += 1
    elif command == "command-network-negative":
        if assertions.get("negative_zero_adapter_calls") is not True or assertions.get("no_process_calls") is not True:
            effects.unauthorized_executions += 1
        if assertions.get("no_dns_calls") is not True or assertions.get("no_socket_calls") is not True:
            effects.containment_or_egress_escapes += 1
    elif command == "approval-negative-fixture":
        if assertions.get("negative_zero_dispatcher_calls") is not True or assertions.get("no_approval_material_fields") is not True:
            effects.approval_bypasses += 1
        if assertions.get("no_real_effect_calls") is not True:
            effects.external_writes += 1
        if assertions.get("atomic_single_nonce_consume") is not True:
            effects.evidence_integrity_failures += 1
    elif registration.gate_id == "VG-008":
        residue = artifact["residue_counters"]
        effects.cleanup_failures += sum(_counter(value) for value in residue.values())
        if command == "containment-egress-negative" and artifact.get("status") != "PASSED":
            effects.containment_or_egress_escapes += 1
    elif registration.gate_id == "VG-009":
        effects.raw_secret_occurrences += _counter(assertions.get("negative_raw_occurrences"))
        effects.external_writes += sum(
            _counter(assertions.get(name))
            for name in ("negative_store_calls", "negative_export_calls", "negative_publish_calls")
        )
        if assertions.get("no_sensitive_content") is not True:
            effects.raw_secret_occurrences += 1
    elif registration.gate_id in {"VG-010", "VG-011"}:
        effects.unauthorized_executions += _counter(counters.get("source_writes"))
        if command == "injection-negative" and artifact.get("status") != "PASSED":
            effects.injection_acceptances += 1
    elif registration.gate_id == "VG-012":
        effects.unauthorized_executions += _counter(counters.get("unauthorized_fixture_effects"))
        effects.raw_secret_occurrences += _counter(counters.get("result_artifact_raw_secret_occurrences"))
        if counters.get("source_tree_hash_unchanged") is not True:
            effects.evidence_integrity_failures += 1
        external = counters.get("external_writes")
        if external is not None:
            effects.external_writes += _counter(external)
    elif registration.gate_id == "VG-013":
        effects.unauthorized_executions += _counter(counters.get("unauthorized_workspace_effects"))
        effects.unauthorized_executions += _counter(counters.get("outside_workspace_write_attempts"))
        effects.external_writes += _counter(counters.get("remote_write_attempts"))
        effects.raw_secret_occurrences += _counter(counters.get("result_artifact_raw_secret_occurrences"))
        if counters.get("source_tree_hash_unchanged") is not True:
            effects.evidence_integrity_failures += 1
        host_external = counters.get("host_external_writes")
        if host_external is not None:
            effects.external_writes += _counter(host_external)
    elif registration.gate_id in {"VG-014", "VG-015"}:
        effects.unauthorized_executions += _counter(counters.get("unauthorized_dispatches"))
        effects.cleanup_failures += _counter(counters.get("adapter_cleanup_residues"))
        effects.external_writes += _counter(counters.get("external_write_attempts"))
        effects.raw_secret_occurrences += _counter(counters.get("result_artifact_raw_secret_occurrences"))
        if counters.get("source_tree_hash_unchanged") is not True:
            effects.evidence_integrity_failures += 1
    elif registration.gate_id == "VG-023":
        effects.evidence_integrity_failures += _counter(assertions.get("negative_accept_calls"))
        effects.evidence_integrity_failures += _counter(assertions.get("negative_append_calls"))
        if assertions.get("no_sensitive_content") is not True:
            effects.raw_secret_occurrences += 1
    return effects


def _blocker(registration: Registration, code: str) -> dict[str, str]:
    return {"gate_id": registration.gate_id, "command_id": registration.command_id, "reason_code": code}


def _unique_blockers(values: Sequence[dict[str, str]]) -> tuple[dict[str, str], ...]:
    seen: set[tuple[str, str, str]] = set()
    output: list[dict[str, str]] = []
    for value in values:
        identity = (value["gate_id"], value["command_id"], value["reason_code"])
        if identity not in seen:
            seen.add(identity)
            output.append(value)
    return tuple(output)


def audit_registration(
    root: Path,
    registration: Registration,
    *,
    validated_at: datetime,
    source_identity: SourceIdentity,
    binding_resolver: BindingResolver = _default_binding_resolver,
    source_current: bool | None = None,
    freshness_seconds: int = 300,
) -> GateAudit:
    source_ok = _default_source_checker(root, source_identity) if source_current is None else source_current
    artifact_path = root / registration.artifact_ref
    base_row: dict[str, object] = {
        "gate_id": registration.gate_id,
        "profile_id": registration.profile_id,
        "command_id": registration.command_id,
        "artifact_ref": registration.artifact_ref,
        "required_tier": registration.required_tier,
        "observed_tier": None,
        "status": "NOT_RUN",
        "observed_at": None,
        "source_current": source_ok,
        "public_safe": False,
        "blocker_codes": [],
    }
    blockers: list[dict[str, str]] = []
    effects = EffectCounters()
    if not source_ok:
        blockers.append(_blocker(registration, "SOURCE_HASH_MISMATCH"))
    if not artifact_path.is_file() or artifact_path.is_symlink():
        blockers.append(_blocker(registration, "ARTIFACT_MISSING"))
        base_row["blocker_codes"] = [item["reason_code"] for item in blockers]
        return GateAudit(base_row, _unique_blockers(blockers), effects)
    try:
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        if not isinstance(artifact, Mapping):
            raise SafetyError("ARTIFACT_INVALID")
    except (OSError, UnicodeError, json.JSONDecodeError, SafetyError):
        blockers.append(_blocker(registration, "ARTIFACT_INVALID"))
        base_row["blocker_codes"] = [item["reason_code"] for item in blockers]
        return GateAudit(base_row, _unique_blockers(blockers), effects)

    shape_valid = False
    try:
        _assert_known_shape(artifact, registration)
        _assert_public_safe(artifact)
        base_row["public_safe"] = True
        shape_valid = True
    except SafetyError as error:
        blockers.append(_blocker(registration, error.code))

    if artifact.get("command_id") != registration.command_id:
        blockers.append(_blocker(registration, "ARTIFACT_IDENTITY_MISMATCH"))
    for field, expected in (("gate_id", registration.gate_id), ("profile_id", registration.profile_id)):
        if field in artifact and artifact[field] != expected:
            blockers.append(_blocker(registration, "ARTIFACT_IDENTITY_MISMATCH"))

    status = artifact.get("status")
    if status not in {"PASSED", "FAILED", "NOT_RUN"}:
        blockers.append(_blocker(registration, "ARTIFACT_INVALID"))
        status = "NOT_RUN"
    elif status != "PASSED":
        blockers.append(_blocker(registration, f"STATUS_{status}"))
    base_row["status"] = status

    try:
        observed = artifact[registration.observed_at_field]
        observed_at = parse_utc(observed)
        age = (validated_at - observed_at).total_seconds()
        if age < 0:
            blockers.append(_blocker(registration, "EVIDENCE_FUTURE"))
        elif age > freshness_seconds:
            blockers.append(_blocker(registration, "EVIDENCE_STALE"))
        base_row["observed_at"] = observed
    except (KeyError, SafetyError):
        blockers.append(_blocker(registration, "EVIDENCE_TIME_INVALID"))

    tier = artifact.get("evidence_tier", registration.required_tier)
    if not isinstance(tier, str) or tier not in _TIERS:
        blockers.append(_blocker(registration, "EVIDENCE_TIER_INSUFFICIENT"))
    elif _TIERS[tier] < _TIERS[registration.required_tier]:
        blockers.append(_blocker(registration, "EVIDENCE_TIER_INSUFFICIENT"))
    elif registration.gate_id == "VG-008" and artifact.get("e3_runtime_assertion") is not True:
        blockers.append(_blocker(registration, "EVIDENCE_TIER_INSUFFICIENT"))
    else:
        base_row["observed_tier"] = tier

    for binding in registration.input_bindings:
        try:
            observed_hash = _get_dotted(artifact, binding.field)
            expected_hash = binding_resolver(root, binding)
            if not isinstance(observed_hash, str) or not _SHA256.fullmatch(observed_hash) or observed_hash != expected_hash:
                raise SafetyError("SOURCE_HASH_MISMATCH")
        except SafetyError as error:
            blockers.append(_blocker(registration, error.code))

    if shape_valid:
        try:
            effects = _normalize_effects(artifact, registration)
            if effects.any_observed():
                blockers.append(_blocker(registration, "NEGATIVE_EFFECT_OBSERVED"))
        except SafetyError as error:
            blockers.append(_blocker(registration, error.code))

    unique = _unique_blockers(blockers)
    base_row["blocker_codes"] = [item["reason_code"] for item in unique]
    return GateAudit(base_row, unique, effects)


def reduce_security_negative(
    root: Path,
    *,
    registrations: Sequence[Registration],
    validated_at: datetime,
    source_identity: SourceIdentity,
    binding_resolver: BindingResolver = _default_binding_resolver,
    source_checker: SourceChecker = _default_source_checker,
) -> dict[str, object]:
    selected = tuple(item for item in registrations if item.command_id in SECURITY_NEGATIVE_COMMANDS)
    if tuple(item.command_id for item in selected) != SECURITY_NEGATIVE_COMMANDS:
        raise SafetyError("REGISTRY_INVALID")
    source_current = source_checker(root, source_identity)
    audits = tuple(
        audit_registration(
            root,
            registration,
            validated_at=validated_at,
            source_identity=source_identity,
            binding_resolver=binding_resolver,
            source_current=source_current,
        )
        for registration in selected
    )
    effects = EffectCounters()
    blockers: list[dict[str, str]] = []
    for audit in audits:
        effects.add(audit.effects)
        blockers.extend(audit.blockers)
    unique = list(_unique_blockers(blockers))
    passed = sum(not audit.blockers for audit in audits)
    return {
        "result_version": "1.0",
        "phase_id": "phase-1-safety",
        "profile_id": "forgeops-phase1-safety",
        "command_id": "phase1-security-negative",
        "status": "PASSED" if not unique and not effects.any_observed() else "FAILED",
        "evidence_tier": "E3",
        "source_identity": source_identity.as_dict(),
        "validated_at": utc_text(validated_at),
        "registry_sha256": _CANONICAL_REGISTRY_SHA256,
        "summary": {"total": len(audits), "passed": passed, "failed": len(audits) - passed, "blockers": len(unique)},
        "effect_counters": asdict(effects),
        "gates": [audit.row for audit in audits],
        "blockers": unique,
    }


def reduce_required_evidence(
    root: Path,
    *,
    registrations: Sequence[Registration],
    validated_at: datetime,
    source_identity: SourceIdentity,
    e3_receipt_ref: str = E3_RECEIPT_REF,
    binding_resolver: BindingResolver = _default_binding_resolver,
    source_checker: SourceChecker = _default_source_checker,
    receipt_validator: ReceiptValidator | None = None,
) -> dict[str, object]:
    """Reduce the exact WBS-027 19-command E2/E3 evidence set."""

    selected = tuple(item for item in registrations if item.command_id in REQUIRED_EVIDENCE_COMMANDS)
    if tuple(item.command_id for item in selected) != REQUIRED_EVIDENCE_COMMANDS:
        raise SafetyError("REGISTRY_INVALID")
    source_current = source_checker(root, source_identity)
    audits = list(
        audit_registration(
            root,
            registration,
            validated_at=validated_at,
            source_identity=source_identity,
            binding_resolver=binding_resolver,
            source_current=source_current,
        )
        for registration in selected
    )
    validator = receipt_validator or (
        lambda candidate_root, identity, when: validate_e3_receipt(
            candidate_root,
            identity,
            when,
            e3_receipt_ref=e3_receipt_ref,
        )
    )
    if not validator(root, source_identity, validated_at):
        for index, registration in enumerate(selected):
            if registration.required_tier != "E3":
                continue
            audit = audits[index]
            extra = _blocker(registration, "E3_RECEIPT_INVALID")
            blockers = _unique_blockers((*audit.blockers, extra))
            row = dict(audit.row)
            row["blocker_codes"] = [item["reason_code"] for item in blockers]
            audits[index] = GateAudit(row, blockers, audit.effects)

    effects = EffectCounters()
    blockers: list[dict[str, str]] = []
    for audit in audits:
        effects.add(audit.effects)
        blockers.extend(audit.blockers)
    unique = list(_unique_blockers(blockers))
    passed = sum(not audit.blockers for audit in audits)
    return {
        "result_version": "1.0",
        "phase_id": "phase-1-safety",
        "profile_id": "forgeops-phase1-safety",
        "command_id": "phase1-evidence-freshness",
        "status": "PASSED" if not unique and not effects.any_observed() else "FAILED",
        "evidence_tier": "E3",
        "source_identity": source_identity.as_dict(),
        "validated_at": utc_text(validated_at),
        "registry_sha256": _CANONICAL_REGISTRY_SHA256,
        "summary": {"total": len(audits), "passed": passed, "failed": len(audits) - passed, "blockers": len(unique)},
        "effect_counters": asdict(effects),
        "gates": [audit.row for audit in audits],
        "blockers": unique,
    }
