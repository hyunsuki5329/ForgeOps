"""Pure, fail-closed Phase 0 exit-result aggregation.

This module deliberately has no command runner.  It consumes only the closed
Phase 0 registry and already-produced public result artifacts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import parse_qsl, urlsplit


EXPECTED_COMMANDS = (
    ("VG-001", "protocol-conformance"),
    ("VG-001", "sample-fixture"),
    ("VG-002", "bridge-schema-fixture"),
    ("VG-003", "state-transition-fixture"),
    ("VG-003", "event-order-fixture"),
    ("VG-003", "replay-contract-negative"),
    ("VG-004", "interface-contract-fixture"),
    ("VG-005", "resource-authority-negative"),
    ("VG-005", "protected-read-negative"),
    ("VG-006", "command-network-negative"),
    ("VG-007", "approval-negative-fixture"),
    ("VG-008", "image-provenance-negative"),
    ("VG-008", "containment-egress-negative"),
    ("VG-008", "teardown-negative"),
    ("VG-009", "secret-surface-negative"),
    ("VG-009", "artifact-isolation-negative"),
    ("VG-023", "evidence-positive-negative"),
    ("VG-023", "extension-provenance"),
)

_TIERS = {"E0": 0, "E1": 1, "E2": 2, "E3": 3}
_STATUSES = {"PASSED", "FAILED", "NOT_RUN"}
_FORBIDDEN_KEYS = {
    "request", "response", "body", "headers", "payload", "raw", "raw_log",
    "credential", "token", "secret", "private", "exception",
}
_SYNTHETIC_MARKER = re.compile(r"(?:^|[_<\s-])synthetic(?:[_>\s-]|$)", re.IGNORECASE)
_WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")
_CANONICAL_REGISTRY_SHA256 = "ac29486b35cd64840b6ec3f7f9ef171cbccf82c63f1941cd4ecaf9e51386926b"
_QUERY_CREDENTIAL_KEYS = ("credential", "password", "secret", "token", "api_key", "apikey", "access_key")
_REGISTERED_CLI_PATHS = {
    "schema": "contracts/forgeops-phase-exit-contract/1.0/schema.json",
    "suite": "fixtures/forgeops-phase-exit/phase-0-suite.json",
    "result": "artifacts/verification/phase-0-exit-result.json",
    "report": "artifacts/reviews/phase-0-exit-report.md",
}
_REGISTERED_COMMAND_ID = "phase0-exit-gate"
_ROOT = Path(__file__).resolve().parents[2]
_NATIVE_ADAPTER_FIELDS = {
    "protocol-conformance": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
    "sample-fixture": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
    "bridge-schema-fixture": {"cases", "command_id", "evidence_tier", "gate_id", "inputs", "observed_at", "profile_id", "runtime", "status", "summary"},
    "state-transition-fixture": {"cases", "command_id", "observed_at", "schema_sha256", "status", "suite_sha256", "summary"},
    "event-order-fixture": {"cases", "command_id", "observed_at", "schema_sha256", "status", "suite_sha256", "summary"},
    "replay-contract-negative": {"cases", "command_id", "observed_at", "schema_sha256", "status", "suite_sha256", "summary"},
    "interface-contract-fixture": {"assertions", "command_id", "components", "gate_id", "hashes", "observed_at", "profile_id", "status"},
    "resource-authority-negative": {"assertions", "cases", "catalog_match", "command_id", "observed_at", "schema_sha256", "sentinel_raw_value_recorded", "status", "suite_sha256", "summary"},
    "protected-read-negative": {"assertions", "cases", "catalog_match", "command_id", "observed_at", "schema_sha256", "sentinel_raw_value_recorded", "status", "suite_sha256", "summary"},
    "command-network-negative": {"assertions", "cases", "catalog_match", "command_id", "observed_at", "schema_sha256", "status", "suite_sha256", "summary"},
    "approval-negative-fixture": {"assertions", "cases", "catalog_match", "command_id", "observed_at", "schema_sha256", "status", "suite_sha256", "summary"},
    "secret-surface-negative": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
    "artifact-isolation-negative": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
    "evidence-positive-negative": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
    "extension-provenance": {"assertions", "cases", "command_id", "gate_id", "hashes", "observed_at", "profile_id", "status", "summary"},
}


class PhaseExitError(Exception):
    """Closed contract error with a stable machine-readable code."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _is_relative_ref(value: object) -> bool:
    return (
        isinstance(value, str)
        and bool(value)
        and not value.startswith(("/", "\\"))
        and not _WINDOWS_ABSOLUTE.match(value)
        and ".." not in Path(value).parts
        and "*" not in value
        and "?" not in value
    )


def validate_registry(suite: dict) -> None:
    """Validate the closed, ordered registry before any artifact is read."""
    if not isinstance(suite, dict) or set(suite) != {
        "suite_id", "suite_version", "phase_id", "freshness_seconds", "registrations"
    }:
        raise PhaseExitError("PHASE_EXIT_REGISTRY_INVALID")
    if (
        suite["suite_id"] != "forgeops-phase-0-exit-v1"
        or suite["suite_version"] != "1.0"
        or suite["phase_id"] != "phase-0"
        or suite["freshness_seconds"] != 300
        or not isinstance(suite["registrations"], list)
    ):
        raise PhaseExitError("PHASE_EXIT_REGISTRY_INVALID")
    registrations = suite["registrations"]
    observed = tuple((item.get("gate_id"), item.get("command_id")) for item in registrations if isinstance(item, dict))
    if len(registrations) != 18 or observed != EXPECTED_COMMANDS or len(set(observed)) != 18:
        raise PhaseExitError("PHASE_EXIT_REGISTRY_COVERAGE_INVALID")
    required_fields = {
        "gate_id", "profile_id", "command_id", "artifact_ref", "required_tier", "input_refs", "hash_fields"
    }
    artifact_refs: set[str] = set()
    for item in registrations:
        if not isinstance(item, dict) or set(item) != required_fields:
            raise PhaseExitError("PHASE_EXIT_REGISTRY_INVALID")
        if (
            item["required_tier"] not in _TIERS
            or not _is_relative_ref(item["artifact_ref"])
            or item["artifact_ref"] in artifact_refs
            or not isinstance(item["input_refs"], list)
            or not item["input_refs"]
            or not isinstance(item["hash_fields"], dict)
            or set(item["input_refs"]) != set(item["hash_fields"])
        ):
            raise PhaseExitError("PHASE_EXIT_REGISTRY_INVALID")
        artifact_refs.add(item["artifact_ref"])
        for ref, field in item["hash_fields"].items():
            if not _is_relative_ref(ref) or not isinstance(field, str) or not field:
                raise PhaseExitError("PHASE_EXIT_REGISTRY_INVALID")
    if _registry_sha256(suite) != _CANONICAL_REGISTRY_SHA256:
        raise PhaseExitError("PHASE_EXIT_REGISTRY_CATALOG_MISMATCH")


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value):
        raise PhaseExitError("PHASE_EXIT_EVIDENCE_TIME_INVALID")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise PhaseExitError("PHASE_EXIT_EVIDENCE_TIME_INVALID") from exc


def _blocker(registration: dict, code: str) -> dict:
    return {
        "gate_id": registration["gate_id"],
        "command_id": registration["command_id"],
        "reason_code": code,
    }


def _gate_result(registration: dict, *, status: str, observed_at: str, hashes_valid: bool, public_safe: bool) -> dict:
    return {
        "gate_id": registration["gate_id"],
        "profile_id": registration["profile_id"],
        "command_id": registration["command_id"],
        "artifact_ref": registration["artifact_ref"],
        "required_tier": registration["required_tier"],
        "status": status if status in _STATUSES else "NOT_RUN",
        "observed_at": observed_at,
        "input_hashes_valid": hashes_valid,
        "public_safe": public_safe,
    }


def _load_public_json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PhaseExitError("PHASE_EXIT_ARTIFACT_INVALID") from exc
    if not isinstance(value, dict):
        raise PhaseExitError("PHASE_EXIT_ARTIFACT_INVALID")
    return value


def _get_dotted(value: object, dotted_path: str) -> object:
    current = value
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise PhaseExitError("PHASE_EXIT_INPUT_HASH_MISSING")
        current = current[part]
    return current


def _expected_hash_tree(registration: dict) -> dict:
    tree: dict = {}
    for dotted_path in registration["hash_fields"].values():
        current = tree
        parts = dotted_path.split(".")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = None
    return tree


def _assert_closed_hash_tree(value: object, expected: dict) -> None:
    if not isinstance(value, dict) or set(value) != set(expected):
        raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
    for key, nested_expected in expected.items():
        nested = value[key]
        if nested_expected is None:
            if not isinstance(nested, str) or not re.fullmatch(r"[0-9a-f]{64}", nested):
                raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
        else:
            _assert_closed_hash_tree(nested, nested_expected)


def _assert_hash_layout(artifact: dict, expected: dict) -> None:
    for root_key, nested_expected in expected.items():
        value = artifact.get(root_key)
        if nested_expected is None:
            if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
                raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
        else:
            _assert_closed_hash_tree(value, nested_expected)


def _assert_known_adapter_fields(artifact: dict, registration: dict) -> None:
    if registration["gate_id"] == "VG-008":
        allowed = {
            "category", "command_id", "counts", "e3_runtime_assertion", "effect_counters",
            "input_hashes", "residue_counters", "result_version", "runtime", "status", "time",
        }
        nested_objects = {
            "counts": {"cases_total", "failed", "not_run", "passed"},
            "effect_counters": {"network_calls", "provision_calls", "write_calls"},
            "residue_counters": {"leases", "mounts", "processes", "transient_secrets", "workspaces"},
        }
        if set(artifact) != allowed or artifact.get("command_id") != registration["command_id"]:
            raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
        for field, keys in nested_objects.items():
            if not isinstance(artifact.get(field), dict) or set(artifact[field]) != keys:
                raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
        _assert_closed_hash_tree(artifact.get("input_hashes"), _expected_hash_tree(registration)["input_hashes"])
        return
    allowed = {"gate_id", "profile_id", "command_id", "status", "observed_at", "evidence_tier"}
    hash_tree = _expected_hash_tree(registration)
    allowed.update(hash_tree)
    native_allowed = _NATIVE_ADAPTER_FIELDS.get(registration["command_id"])
    if set(artifact) != allowed and set(artifact) != native_allowed:
        raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
    if set(artifact) == allowed:
        _assert_hash_layout(artifact, hash_tree)


def _is_unsafe_string(value: str) -> bool:
    if _SYNTHETIC_MARKER.search(value):
        return True
    if value.startswith(("/", "\\")) or _WINDOWS_ABSOLUTE.match(value):
        return True
    parsed = urlsplit(value)
    if parsed.scheme and parsed.username:
        return True
    if parsed.scheme and parsed.query:
        return any(
            any(marker in key.lower() for marker in _QUERY_CREDENTIAL_KEYS)
            for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
        )
    return False


def assert_public_safe(value: object) -> None:
    """Reject raw/sensitive surfaces, absolute paths, and synthetic evidence."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or key.lower() in _FORBIDDEN_KEYS:
                raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
            assert_public_safe(nested)
    elif isinstance(value, list):
        # Public result artifacts are summaries; raw case arrays are forbidden.
        raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
    elif isinstance(value, str) and _is_unsafe_string(value):
        raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")


def _assert_artifact_public_safe(value: object) -> None:
    """Validate source envelopes without copying their permitted case arrays outward."""
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str) or key.lower() in _FORBIDDEN_KEYS:
                raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
            _assert_artifact_public_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_artifact_public_safe(nested)
    elif isinstance(value, str) and _is_unsafe_string(value):
        raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")
    elif not isinstance(value, (str, int, float, bool, type(None))):
        raise PhaseExitError("PHASE_EXIT_PUBLIC_UNSAFE")


def _validate_input_hashes(root: Path, artifact: dict, registration: dict) -> bool:
    for input_ref, field in registration["hash_fields"].items():
        input_path = root / input_ref
        if not input_path.is_file():
            raise PhaseExitError("PHASE_EXIT_INPUT_MISSING")
        observed = _get_dotted(artifact, field)
        if not isinstance(observed, str) or not re.fullmatch(r"[0-9a-f]{64}", observed):
            raise PhaseExitError("PHASE_EXIT_INPUT_HASH_MISSING")
        actual = hashlib.sha256(input_path.read_bytes()).hexdigest()
        if observed != actual:
            raise PhaseExitError("PHASE_EXIT_INPUT_HASH_MISMATCH")
    return True


def _unique_blockers(blockers: list[dict]) -> list[dict]:
    unique: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for item in blockers:
        key = (item["gate_id"], item["command_id"], item["reason_code"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def inspect_registration(root: Path, registration: dict, validation_at: str) -> tuple[dict, list[dict]]:
    """Reduce one registered artifact to public fields and deterministic blockers."""
    validated_at = _parse_utc(validation_at)
    artifact_path = root / registration["artifact_ref"]
    if not artifact_path.is_file():
        return (
            _gate_result(registration, status="NOT_RUN", observed_at=validation_at, hashes_valid=False, public_safe=False),
            [_blocker(registration, "PHASE_EXIT_ARTIFACT_MISSING")],
        )
    try:
        artifact = _load_public_json(artifact_path)
    except PhaseExitError as exc:
        return (
            _gate_result(registration, status="NOT_RUN", observed_at=validation_at, hashes_valid=False, public_safe=False),
            [_blocker(registration, exc.code)],
        )

    blockers: list[dict] = []
    status = artifact.get("status") if isinstance(artifact.get("status"), str) else "NOT_RUN"
    time_field = "time" if registration["gate_id"] == "VG-008" else "observed_at"
    observed_at = artifact.get(time_field) if isinstance(artifact.get(time_field), str) else validation_at
    public_safe = True
    hashes_valid = False

    try:
        _assert_known_adapter_fields(artifact, registration)
        _assert_artifact_public_safe(artifact)
    except PhaseExitError as exc:
        public_safe = False
        blockers.append(_blocker(registration, exc.code))

    if artifact.get("command_id") != registration["command_id"]:
        blockers.append(_blocker(registration, "PHASE_EXIT_IDENTITY_MISMATCH"))
    for field in ("gate_id", "profile_id"):
        if field in artifact and artifact[field] != registration[field]:
            blockers.append(_blocker(registration, "PHASE_EXIT_IDENTITY_MISMATCH"))
    if status not in _STATUSES:
        blockers.append(_blocker(registration, "PHASE_EXIT_STATUS_INVALID"))
        status = "NOT_RUN"
    elif status != "PASSED":
        blockers.append(_blocker(registration, f"PHASE_EXIT_STATUS_{status}"))

    try:
        artifact_time = _parse_utc(artifact.get(time_field))
        observed_at = artifact[time_field]
        age = (validated_at - artifact_time).total_seconds()
        if age < 0:
            blockers.append(_blocker(registration, "PHASE_EXIT_EVIDENCE_FUTURE"))
        elif age > 300:
            blockers.append(_blocker(registration, "PHASE_EXIT_EVIDENCE_STALE"))
    except PhaseExitError as exc:
        blockers.append(_blocker(registration, exc.code))
        observed_at = validation_at

    if registration["gate_id"] == "VG-008":
        if status == "PASSED" and artifact.get("e3_runtime_assertion") is not True:
            blockers.append(_blocker(registration, "PHASE_EXIT_EVIDENCE_TIER_INSUFFICIENT"))
    else:
        tier = artifact.get("evidence_tier")
        if tier is None:
            # The closed registration binds the declared verifier to its evidence floor.
            pass
        elif not isinstance(tier, str) or tier not in _TIERS:
            blockers.append(_blocker(registration, "PHASE_EXIT_EVIDENCE_TIER_MISSING"))
        elif _TIERS[tier] < _TIERS[registration["required_tier"]]:
            blockers.append(_blocker(registration, "PHASE_EXIT_EVIDENCE_TIER_INSUFFICIENT"))

    try:
        hashes_valid = _validate_input_hashes(root, artifact, registration)
    except PhaseExitError as exc:
        blockers.append(_blocker(registration, exc.code))

    return (
        _gate_result(
            registration,
            status=status,
            observed_at=observed_at,
            hashes_valid=hashes_valid,
            public_safe=public_safe,
        ),
        _unique_blockers(blockers),
    )


def _registry_sha256(suite: dict) -> str:
    canonical = json.dumps(suite, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def aggregate_phase_zero(root: Path, suite: dict, validation_at: str) -> dict:
    """Build the single Phase 0 decision, failing closed for every deficiency."""
    validate_registry(suite)
    _parse_utc(validation_at)
    root = Path(root)
    gate_results: list[dict] = []
    blockers: list[dict] = []
    for registration in suite["registrations"]:
        gate_result, registration_blockers = inspect_registration(root, registration, validation_at)
        gate_results.append(gate_result)
        blockers.extend(registration_blockers)
    blockers = _unique_blockers(blockers)
    statuses = [item["status"] for item in gate_results]
    summary = {
        "required": 18,
        "passed": statuses.count("PASSED"),
        "failed": statuses.count("FAILED"),
        "not_run": statuses.count("NOT_RUN"),
        "blocked": len({(item["gate_id"], item["command_id"]) for item in blockers}),
    }
    blocker_codes = {item["reason_code"] for item in blockers}
    assertions = {
        "exact_coverage": len(gate_results) == 18,
        "freshness_valid": not any("EVIDENCE_" in code for code in blocker_codes),
        "input_hashes_valid": not any("INPUT_" in code for code in blocker_codes),
        "public_safe": "PHASE_EXIT_PUBLIC_UNSAFE" not in blocker_codes,
        "tiers_sufficient": not any("EVIDENCE_TIER" in code for code in blocker_codes),
    }
    ready = (
        summary == {"required": 18, "passed": 18, "failed": 0, "not_run": 0, "blocked": 0}
        and not blockers
        and all(assertions.values())
    )
    return {
        "schema_version": "1.0",
        "phase_id": "phase-0",
        "status": "READY" if ready else "NOT_READY",
        "observed_at": validation_at,
        "registry_sha256": _registry_sha256(suite),
        "summary": summary,
        "gate_results": gate_results,
        "blockers": blockers,
        "assertions": assertions,
    }


def _validate_public_decision(result: dict) -> None:
    required = {
        "schema_version", "phase_id", "status", "observed_at", "registry_sha256",
        "summary", "gate_results", "blockers", "assertions",
    }
    gate_fields = {
        "gate_id", "profile_id", "command_id", "artifact_ref", "required_tier", "status",
        "observed_at", "input_hashes_valid", "public_safe",
    }
    blocker_fields = {"gate_id", "command_id", "reason_code"}
    summary_fields = {"required", "passed", "failed", "not_run", "blocked"}
    assertion_fields = {"exact_coverage", "freshness_valid", "input_hashes_valid", "public_safe", "tiers_sufficient"}
    if (
        not isinstance(result, dict)
        or set(result) != required
        or result.get("status") not in {"READY", "NOT_READY"}
        or not isinstance(result.get("summary"), dict)
        or set(result["summary"]) != summary_fields
        or not isinstance(result.get("assertions"), dict)
        or set(result["assertions"]) != assertion_fields
        or not isinstance(result.get("gate_results"), list)
        or not isinstance(result.get("blockers"), list)
    ):
        raise PhaseExitError("PHASE_EXIT_DECISION_INVALID")
    _parse_utc(result.get("observed_at"))
    assert_public_safe({key: result[key] for key in ("schema_version", "phase_id", "status", "registry_sha256")})
    assert_public_safe(result["summary"])
    assert_public_safe(result["assertions"])
    for gate in result["gate_results"]:
        if not isinstance(gate, dict) or set(gate) != gate_fields:
            raise PhaseExitError("PHASE_EXIT_DECISION_INVALID")
        _parse_utc(gate.get("observed_at"))
        assert_public_safe(gate)
    for blocker in result["blockers"]:
        if not isinstance(blocker, dict) or set(blocker) != blocker_fields:
            raise PhaseExitError("PHASE_EXIT_DECISION_INVALID")
        assert_public_safe(blocker)


def render_report(result: dict) -> str:
    """Render only the public decision surface; source artifacts never enter Markdown."""
    _validate_public_decision(result)
    summary = result["summary"]
    lines = [
        "# Phase 0 Exit Report",
        "",
        "## Decision",
        "",
        f"Status: **{result['status']}**",
        f"Observed at: {result['observed_at']}",
        f"Coverage: {summary['passed']}/{summary['required']} passed",
        "",
        "## Gate summary",
        "",
        "| Gate | Profile | Command | Status | Tier | Observed at | Artifact |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for gate in result["gate_results"]:
        lines.append(
            "| {gate_id} | {profile_id} | {command_id} | {status} | {required_tier} | {observed_at} | {artifact_ref} |".format(**gate)
        )
    lines.extend(["", "## Blocking conditions", ""])
    if result["blockers"]:
        for blocker in result["blockers"]:
            lines.append(f"- {blocker['gate_id']} / {blocker['command_id']}: {blocker['reason_code']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Residual risks", ""])
    if result["status"] == "READY":
        lines.append("- Phase 0 Exit conditions satisfied.")
    else:
        lines.append("- Phase 0 Exit conditions are not satisfied; resolve every blocker before reassessment.")
    lines.extend(["", "## Reproduction command", "", "- Aggregation is performed by the registered Phase 0 exit command.", ""])
    return "\n".join(lines)


def write_text_atomically(path: Path, text: str) -> None:
    """Write one text artifact without exposing a partial report or decision."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_path, path)
    except BaseException:
        try:
            os.unlink(temporary_path)
        except FileNotFoundError:
            pass
        raise


def validate_registered_paths(args: argparse.Namespace) -> None:
    """Admit only the one registered Phase 0 exit command literal surface."""
    for name, expected in _REGISTERED_CLI_PATHS.items():
        if getattr(args, name, None) != expected:
            raise PhaseExitError("PHASE_EXIT_RUNNER_CONTRACT_INVALID")
    if getattr(args, "command_id", None) != _REGISTERED_COMMAND_ID:
        raise PhaseExitError("PHASE_EXIT_RUNNER_CONTRACT_INVALID")


def _failure_decision(validation_at: str, reason_code: str) -> dict:
    """Return a public-safe, schema-shaped closed result for runner failures."""
    gate_results = []
    blockers = []
    for gate_id, command_id in EXPECTED_COMMANDS:
        gate_results.append(
            {
                "gate_id": gate_id,
                "profile_id": "forgeops-phase0-exit",
                "command_id": command_id,
                "artifact_ref": "artifacts/verification/phase-0-exit-unavailable.json",
                "required_tier": "E3" if gate_id in {"VG-008", "VG-009"} else "E2",
                "status": "NOT_RUN",
                "observed_at": validation_at,
                "input_hashes_valid": False,
                "public_safe": True,
            }
        )
        blockers.append({"gate_id": gate_id, "command_id": command_id, "reason_code": reason_code})
    return {
        "schema_version": "1.0",
        "phase_id": "phase-0",
        "status": "NOT_READY",
        "observed_at": validation_at,
        "registry_sha256": "0" * 64,
        "summary": {"required": 18, "passed": 0, "failed": 0, "not_run": 18, "blocked": 18},
        "gate_results": gate_results,
        "blockers": blockers,
        "assertions": {
            "exact_coverage": True,
            "freshness_valid": False,
            "input_hashes_valid": False,
            "public_safe": True,
            "tiers_sufficient": False,
        },
    }


def _write_decision_and_report(result_path: Path, report_path: Path, decision: dict) -> None:
    write_text_atomically(result_path, json.dumps(decision, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
    write_text_atomically(report_path, render_report(decision))


def _trusted_output_paths(root: Path, result: object, report: object) -> tuple[Path | None, Path | None]:
    result_path = root / _REGISTERED_CLI_PATHS["result"] if result == _REGISTERED_CLI_PATHS["result"] else None
    report_path = root / _REGISTERED_CLI_PATHS["report"] if report == _REGISTERED_CLI_PATHS["report"] else None
    return result_path, report_path


def _write_closed_failure_to_trusted_targets(
    root: Path,
    validation_at: str,
    reason_code: str,
    result: object,
    report: object,
) -> None:
    """Write only exact registered output literals; invalid paths never become targets."""
    result_path, report_path = _trusted_output_paths(root, result, report)
    decision = _failure_decision(validation_at, reason_code)
    if result_path is not None:
        write_text_atomically(result_path, json.dumps(decision, ensure_ascii=True, indent=2, sort_keys=True) + "\n")
    if report_path is not None:
        write_text_atomically(report_path, render_report(decision))


def _argument_literal(argv: list[str], name: str) -> str | None:
    """Extract an exact long-option value without accepting abbreviations or aliases."""
    for index, value in enumerate(argv):
        if value == name and index + 1 < len(argv):
            return argv[index + 1]
        if value.startswith(name + "="):
            return value[len(name) + 1:]
    return None


class _PhaseExitArgumentParser(argparse.ArgumentParser):
    """Convert parser errors to a closed code without printing parser internals."""

    def error(self, message: str) -> None:
        raise PhaseExitError("PHASE_EXIT_RUNNER_CONTRACT_INVALID")


def run_cli(
    *,
    schema: str,
    suite: str,
    result: str,
    report: str,
    command_id: str,
    project_root: Path | None = None,
    validation_at: str | None = None,
) -> int:
    """Aggregate the registered artifacts once and atomically write public outputs."""
    arguments = argparse.Namespace(
        schema=schema,
        suite=suite,
        result=result,
        report=report,
        command_id=command_id,
    )
    validation_at = validation_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    root = Path(project_root) if project_root is not None else _ROOT
    try:
        validate_registered_paths(arguments)
        schema_value = _load_public_json(root / schema)
        suite_value = _load_public_json(root / suite)
        # The closed registry validator is the schema authority; custom validation pins catalog identity.
        if schema_value.get("$id") != _REGISTERED_CLI_PATHS["schema"]:
            raise PhaseExitError("PHASE_EXIT_SCHEMA_INVALID")
        validate_registry(suite_value)
        decision = aggregate_phase_zero(root, suite_value, validation_at)
    except PhaseExitError as exc:
        _write_closed_failure_to_trusted_targets(root, validation_at, exc.code, result, report)
        return 1
    _write_decision_and_report(root / result, root / report, decision)
    return 0 if decision["status"] == "READY" else 1


def main(argv: list[str] | None = None) -> int:
    """Run only the registered Phase 0 exit aggregation command."""
    raw_arguments = list(argv) if argv is not None else None
    parser = _PhaseExitArgumentParser(description="ForgeOps Phase 0 exit gate", allow_abbrev=False)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--command-id", required=True)
    try:
        arguments = parser.parse_args(raw_arguments)
        return run_cli(
            schema=arguments.schema,
            suite=arguments.suite,
            result=arguments.result,
            report=arguments.report,
            command_id=arguments.command_id,
        )
    except PhaseExitError as exc:
        supplied = raw_arguments if raw_arguments is not None else []
        validation_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_closed_failure_to_trusted_targets(
            _ROOT,
            validation_at,
            exc.code,
            _argument_literal(supplied, "--result"),
            _argument_literal(supplied, "--report"),
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
