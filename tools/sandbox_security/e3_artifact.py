"""Closed public artifact boundary for the externally attested VG-008 run."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sys
import tempfile
from typing import Any, Mapping

from jsonschema import Draft202012Validator

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.sandbox_security.e3_attestation import (
    DEFAULT_PROCESS_RUNNER,
    E3Error,
    ExpectedIdentity,
    ProcessRunner,
    verify_signed_attestation,
)


PHASE0_RESULT_FILES = (
    "artifacts/verification/vg-001-protocol-conformance-result.json",
    "artifacts/verification/vg-001-sample-fixture-result.json",
    "artifacts/verification/vg-002-contract-bridge-result.json",
    "artifacts/verification/vg-003-state-transition-result.json",
    "artifacts/verification/vg-003-event-order-result.json",
    "artifacts/verification/vg-003-replay-contract-result.json",
    "artifacts/verification/vg-004-interface-contract-result.json",
    "artifacts/verification/vg-005-resource-authority-result.json",
    "artifacts/verification/vg-005-protected-read-result.json",
    "artifacts/verification/vg-006-command-network-result.json",
    "artifacts/verification/vg-007-approval-policy-result.json",
    "artifacts/verification/vg-008-image-provenance-result.json",
    "artifacts/verification/vg-008-containment-egress-result.json",
    "artifacts/verification/vg-008-teardown-result.json",
    "artifacts/verification/vg-009-secret-surface-result.json",
    "artifacts/verification/vg-009-artifact-isolation-result.json",
    "artifacts/verification/vg-023-evidence-contract-result.json",
    "artifacts/verification/vg-023-extension-provenance-result.json",
)

E3_PAYLOAD_FILES = (
    "artifacts/runtime/e3-attestation.json",
    "artifacts/runtime/e3-attestation.bundle.json",
    "artifacts/runtime/sandbox-runtime-profile.json",
    "artifacts/runtime/sandbox-runtime-observations.json",
    "artifacts/runtime/sandbox-e3-import-receipt.json",
    *PHASE0_RESULT_FILES,
    "artifacts/verification/phase-0-exit-result.json",
    "artifacts/reviews/phase-0-exit-report.md",
)
E3_MANIFEST_FILE = "artifacts/runtime/e3-artifact-manifest.json"
E3_ARTIFACT_FILES = E3_PAYLOAD_FILES + (E3_MANIFEST_FILE,)
E3_STAGING_ROOT = "e3-upload"
PHASE1_PAYLOAD_VERSION = "phase1-safety-1.0"
PHASE1_RESULT_FILES = (
    "artifacts/verification/vg-005-resource-authority-result.json",
    "artifacts/verification/vg-005-protected-read-result.json",
    "artifacts/verification/vg-006-command-network-result.json",
    "artifacts/verification/vg-007-approval-policy-result.json",
    "artifacts/verification/vg-008-image-provenance-result.json",
    "artifacts/verification/vg-008-containment-egress-result.json",
    "artifacts/verification/vg-008-teardown-result.json",
    "artifacts/verification/vg-009-secret-surface-result.json",
    "artifacts/verification/vg-009-artifact-isolation-result.json",
    "artifacts/verification/vg-010-snapshot-identity-result.json",
    "artifacts/verification/vg-010-baseline-retrieval-result.json",
    "artifacts/verification/vg-011-context-provenance-result.json",
    "artifacts/verification/vg-011-injection-negative-result.json",
    "artifacts/verification/vg-012-local-vertical-result.json",
    "artifacts/verification/vg-013-task-checks-result.json",
    "artifacts/verification/vg-013-regression-checks-result.json",
    "artifacts/verification/vg-013-verification-anti-tamper-result.json",
    "artifacts/verification/vg-014-budget-cancel-result.json",
    "artifacts/verification/vg-014-no-progress-result.json",
    "artifacts/verification/vg-015-trace-manifest-result.json",
    "artifacts/verification/vg-015-external-write-result.json",
    "artifacts/verification/vg-023-evidence-contract-result.json",
    "artifacts/verification/vg-023-extension-provenance-result.json",
)
PHASE1_PAYLOAD_FILES = (
    "artifacts/runtime/e3-attestation.json",
    "artifacts/runtime/e3-attestation.bundle.json",
    "artifacts/runtime/sandbox-runtime-profile.json",
    "artifacts/runtime/sandbox-runtime-observations.json",
    "artifacts/runtime/sandbox-e3-import-receipt.json",
    *PHASE1_RESULT_FILES,
    "artifacts/verification/phase-1-security-negative-result.json",
    "artifacts/verification/phase-1-evidence-freshness-result.json",
    "artifacts/verification/phase-1-safety-gate-result.json",
    "artifacts/reviews/phase-1-safety-scorecard.md",
    "artifacts/reviews/phase-1-safety-scorecard.html",
)
PHASE1_MANIFEST_FILE = "artifacts/runtime/phase1-safety-artifact-manifest.json"
PHASE1_ARTIFACT_FILES = PHASE1_PAYLOAD_FILES + (PHASE1_MANIFEST_FILE,)
PHASE1_STAGING_ROOT = "phase1-upload"
MAX_FILE_BYTES = 1_048_576
MAX_ARTIFACT_BYTES = 4_194_304
_ROOT = Path(__file__).resolve().parents[2]
_TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PHASE_SCHEMA_ID = "contracts/forgeops-phase-exit-contract/1.0/schema.json"
_PHASE1_SCHEMA_ID = "contracts/forgeops-phase1-safety/1.0/schema.json"
_FORBIDDEN_KEYS = frozenset({
    "token", "secret", "credential", "environment", "stdout", "stderr", "log",
    "private_path", "certificate_pem", "certificate_chain", "raw_docker_output",
    "container_log", "host_absolute_path",
})
_MANIFEST_KEYS = frozenset({
    "manifest_version", "status", "created_at", "repository", "repository_id",
    "default_branch", "workflow_ref", "workflow_sha", "source_sha", "run_id",
    "run_attempt", "image_ref", "image_digest", "issuer", "certificate_identity",
    "phase_summary", "files",
})


class ArtifactError(Exception):
    """Stable public-artifact rejection without source-data disclosure."""


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".e3-artifact-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(content)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _remove_output(path: Path) -> None:
    try:
        if path.exists() or path.is_symlink():
            path.unlink()
    except OSError as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    if type(value) is not dict:
        raise ArtifactError("E3_ARTIFACT_INVALID")
    return value


def _has_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(type(key) is not str or key.lower() in _FORBIDDEN_KEYS or _has_forbidden_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_has_forbidden_key(item) for item in value)
    return False


def _safe_relative(path: str) -> bool:
    value = PurePosixPath(path)
    return type(path) is str and path != "" and not value.is_absolute() and ".." not in value.parts and "\\" not in path and ":" not in path


def _root_directory(root: Path) -> Path:
    try:
        if root.is_symlink():
            raise ArtifactError("E3_ARTIFACT_INVALID")
        resolved = root.resolve(strict=True)
    except OSError as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    if not resolved.is_dir():
        raise ArtifactError("E3_ARTIFACT_INVALID")
    return resolved


def _guard_relative_path(root: Path, relative: str, *, require_file: bool = True) -> Path:
    if not _safe_relative(relative):
        raise ArtifactError("E3_ARTIFACT_INVALID")
    current = root
    try:
        for part in PurePosixPath(relative).parts:
            current = current / part
            if current.is_symlink():
                raise ArtifactError("E3_ARTIFACT_INVALID")
        resolved = current.resolve(strict=True)
    except OSError as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    if not resolved.is_relative_to(root) or (require_file and not resolved.is_file()):
        raise ArtifactError("E3_ARTIFACT_INVALID")
    return resolved


def _read_payload(root: Path, relative: str) -> bytes:
    path = _guard_relative_path(root, relative)
    try:
        size = path.stat().st_size
        if not 0 < size <= MAX_FILE_BYTES:
            raise ArtifactError("E3_ARTIFACT_INVALID")
        content = path.read_bytes()
    except OSError as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    if path.suffix == ".json":
        try:
            value = json.loads(content.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            # Cosign bundles are JSON in production, but an opaque test double is
            # still bounded and signature-verified through the attestation path.
            if path.name != "e3-attestation.bundle.json":
                raise ArtifactError("E3_ARTIFACT_INVALID") from None
        else:
            if _has_forbidden_key(value):
                raise ArtifactError("E3_ARTIFACT_INVALID")
    return content


def _ready_phase(root: Path) -> dict[str, Any]:
    phase = _load_json(root / "artifacts/verification/phase-0-exit-result.json")
    try:
        schema_path = _ROOT / _PHASE_SCHEMA_ID
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if type(schema) is not dict or schema.get("$id") != _PHASE_SCHEMA_ID:
            raise ArtifactError("E3_ARTIFACT_INVALID")
        schema["$id"] = schema_path.resolve(strict=True).as_uri()
        Draft202012Validator(schema).validate(phase)
    except ArtifactError:
        raise
    except Exception as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    if not (
        phase.get("status") == "READY"
        and phase.get("phase_id") == "phase-0"
        and phase.get("summary") == {"required": 18, "passed": 18, "failed": 0, "not_run": 0, "blocked": 0}
        and phase.get("blockers") == []
    ):
        raise ArtifactError("E3_ARTIFACT_NOT_READY")
    return phase


def build_manifest(root: Path, output: Path, *, runner: ProcessRunner = DEFAULT_PROCESS_RUNNER, validation_at: datetime | None = None) -> dict[str, Any]:
    """Hash the exact public payload and atomically emit a non-self-hashing manifest."""

    root = _root_directory(root)
    expected_output = root / E3_MANIFEST_FILE
    if output.absolute() != expected_output.absolute():
        raise ArtifactError("E3_ARTIFACT_INVALID")
    _guard_relative_path(root, "artifacts/runtime", require_file=False)
    if expected_output.is_symlink():
        raise ArtifactError("E3_ARTIFACT_INVALID")
    _remove_output(expected_output)
    try:
        for relative in E3_PAYLOAD_FILES:
            _guard_relative_path(root, relative)
        phase = _ready_phase(root)
        attestation = _load_json(root / E3_PAYLOAD_FILES[0])
        workflow_ref = attestation["workflow_ref"]
        if type(workflow_ref) is not str or not workflow_ref.startswith("refs/heads/"):
            raise ArtifactError("E3_ARTIFACT_IDENTITY_INVALID")
        identity = ExpectedIdentity(
            attestation["repository"], attestation["repository_id"], workflow_ref.removeprefix("refs/heads/"),
            attestation["source_sha"], attestation["workflow_sha"], attestation["run_id"],
            attestation["run_attempt"], attestation["image_ref"], attestation["image_digest"],
        )
        try:
            attestation = verify_signed_attestation(
                root / E3_PAYLOAD_FILES[0], root / E3_PAYLOAD_FILES[1], identity,
                runner, _validation_time(validation_at),
            )
        except E3Error as error:
            raise ArtifactError("E3_ARTIFACT_SIGNATURE_INVALID") from error
        if attestation["workflow_sha"] != attestation["source_sha"]:
            raise ArtifactError("E3_ARTIFACT_IDENTITY_INVALID")
        files = []
        total = 0
        for relative in E3_PAYLOAD_FILES:
            content = _read_payload(root, relative)
            total += len(content)
            files.append({"path": relative, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
        if total > MAX_ARTIFACT_BYTES:
            raise ArtifactError("E3_ARTIFACT_INVALID")
        summary = phase["summary"]
        manifest = {
            "manifest_version": "1.0", "status": "READY", "created_at": attestation["observed_at"],
            "repository": attestation["repository"], "repository_id": attestation["repository_id"],
            "default_branch": identity.default_branch,
            "workflow_ref": attestation["workflow_ref"], "workflow_sha": attestation["workflow_sha"],
            "source_sha": attestation["source_sha"], "run_id": attestation["run_id"], "run_attempt": attestation["run_attempt"],
            "image_ref": attestation["image_ref"], "image_digest": attestation["image_digest"],
            "issuer": attestation["issuer"], "certificate_identity": attestation["certificate_identity"],
            "phase_summary": dict(summary), "files": files,
        }
        if set(manifest) != _MANIFEST_KEYS or _has_forbidden_key(manifest):
            raise ArtifactError("E3_ARTIFACT_INVALID")
        _atomic_write(expected_output, _canonical(manifest))
        return manifest
    except (ArtifactError, KeyError, TypeError, ValueError, OSError) as error:
        _remove_output(expected_output)
        if isinstance(error, ArtifactError):
            raise
        raise ArtifactError("E3_ARTIFACT_INVALID") from error


def _validation_time(value: datetime | None) -> datetime:
    result = datetime.now(timezone.utc) if value is None else value
    if result.tzinfo is None:
        raise ArtifactError("E3_ARTIFACT_STALE")
    return result.astimezone(timezone.utc)


def _phase1_schema() -> dict[str, Any]:
    try:
        schema_path = _ROOT / _PHASE1_SCHEMA_ID
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if type(schema) is not dict or schema.get("$id") != "https://forgeops.invalid/contracts/forgeops-phase1-safety/1.0/schema.json":
            raise ArtifactError("E3_ARTIFACT_INVALID")
        return schema
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error


def _validate_phase1_result(value: dict[str, Any], definition: str) -> None:
    schema = _phase1_schema()
    validator_schema = {"$ref": f"#/$defs/{definition}", "$defs": schema["$defs"]}
    try:
        Draft202012Validator(validator_schema).validate(value)
    except Exception as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error


def _ready_phase1(root: Path, validation_at: datetime, runner: ProcessRunner) -> tuple[dict[str, Any], ExpectedIdentity]:
    from tools.phase1_safety.audit import validate_e3_receipt
    from tools.phase1_safety.model import SourceIdentity, validate_source_identity

    security = _load_json(root / "artifacts/verification/phase-1-security-negative-result.json")
    freshness = _load_json(root / "artifacts/verification/phase-1-evidence-freshness-result.json")
    gate = _load_json(root / "artifacts/verification/phase-1-safety-gate-result.json")
    _validate_phase1_result(security, "reducerResult")
    _validate_phase1_result(freshness, "reducerResult")
    _validate_phase1_result(gate, "gateResult")
    if not (
        security.get("command_id") == "phase1-security-negative"
        and freshness.get("command_id") == "phase1-evidence-freshness"
        and security.get("status") == "PASSED"
        and freshness.get("status") == "PASSED"
        and gate.get("status") == "READY"
        and gate.get("summary") == {"total": 19, "passed": 19, "failed": 0, "blockers": 0}
        and gate.get("blockers") == []
        and not any(gate.get("effect_counters", {}).values())
        and security.get("source_identity") == gate.get("source_identity")
        and freshness.get("source_identity") == gate.get("source_identity")
    ):
        raise ArtifactError("E3_ARTIFACT_NOT_READY")
    try:
        source_identity: SourceIdentity = validate_source_identity(gate["source_identity"])
        receipt = _load_json(root / "artifacts/runtime/sandbox-e3-import-receipt.json")
        expected = ExpectedIdentity(
            source_identity.repository,
            source_identity.repository_id,
            source_identity.default_branch,
            source_identity.source_sha,
            source_identity.workflow_sha,
            source_identity.run_id,
            source_identity.run_attempt,
            receipt["image_ref"],
            receipt["image_digest"],
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ArtifactError("E3_ARTIFACT_IDENTITY_INVALID") from error
    if not validate_e3_receipt(root, source_identity, validation_at, runner=runner):
        raise ArtifactError("E3_ARTIFACT_SIGNATURE_INVALID")
    return gate, expected


def build_phase1_manifest(
    root: Path,
    output: Path,
    *,
    runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
    validation_at: datetime | None = None,
) -> dict[str, Any]:
    """Build the explicit versioned W9 payload without widening Phase 0."""

    root = _root_directory(root)
    expected_output = root / PHASE1_MANIFEST_FILE
    if output.absolute() != expected_output.absolute():
        raise ArtifactError("E3_ARTIFACT_INVALID")
    _guard_relative_path(root, "artifacts/runtime", require_file=False)
    if expected_output.is_symlink():
        raise ArtifactError("E3_ARTIFACT_INVALID")
    _remove_output(expected_output)
    try:
        when = _validation_time(validation_at)
        gate, _identity = _ready_phase1(root, when, runner)
        files = []
        total = 0
        for relative in PHASE1_PAYLOAD_FILES:
            content = _read_payload(root, relative)
            total += len(content)
            files.append({"path": relative, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
        if total > MAX_ARTIFACT_BYTES:
            raise ArtifactError("E3_ARTIFACT_INVALID")
        manifest = {
            "payload_version": PHASE1_PAYLOAD_VERSION,
            "status": "READY",
            "created_at": gate["validated_at"],
            "source_identity": gate["source_identity"],
            "files": files,
        }
        _validate_phase1_result(manifest, "artifactManifest")
        if _has_forbidden_key(manifest):
            raise ArtifactError("E3_ARTIFACT_INVALID")
        _atomic_write(expected_output, _canonical(manifest))
        return manifest
    except (ArtifactError, KeyError, TypeError, ValueError, OSError) as error:
        _remove_output(expected_output)
        if isinstance(error, ArtifactError):
            raise
        raise ArtifactError("E3_ARTIFACT_INVALID") from error


def _exact_tree_for(source: Path, artifact_files: tuple[str, ...]) -> None:
    expected = set(artifact_files)
    for relative in artifact_files:
        parts = PurePosixPath(relative).parts
        expected.update(PurePosixPath(*parts[:index]).as_posix() for index in range(1, len(parts)))
    try:
        observed = set()
        for path in source.rglob("*"):
            relative = path.relative_to(source).as_posix()
            if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):
                raise ArtifactError("E3_ARTIFACT_INVALID")
            observed.add(relative)
    except (OSError, ValueError) as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    if observed != expected:
        raise ArtifactError("E3_ARTIFACT_INVALID")


def _exact_tree(source: Path) -> None:
    _exact_tree_for(source, E3_ARTIFACT_FILES)


@contextmanager
def _snapshot_source(source: Path):
    source = _root_directory(source)
    _exact_tree(source)
    with tempfile.TemporaryDirectory(prefix="forgeops-e3-snapshot-") as directory:
        snapshot = Path(directory)
        for relative in E3_ARTIFACT_FILES:
            content = _read_payload(source, relative)
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        _exact_tree(snapshot)
        yield snapshot


@contextmanager
def _snapshot_phase1_source(source: Path):
    source = _root_directory(source)
    _exact_tree_for(source, PHASE1_ARTIFACT_FILES)
    with tempfile.TemporaryDirectory(prefix="forgeops-phase1-snapshot-") as directory:
        snapshot = Path(directory)
        for relative in PHASE1_ARTIFACT_FILES:
            content = _read_payload(source, relative)
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        _exact_tree_for(snapshot, PHASE1_ARTIFACT_FILES)
        yield snapshot


def _verify_phase1_snapshot(
    source: Path,
    expected_identity: ExpectedIdentity,
    *,
    runner: ProcessRunner,
    validation_at: datetime | None,
) -> dict[str, Any]:
    when = _validation_time(validation_at)
    manifest = _load_json(source / PHASE1_MANIFEST_FILE)
    _validate_phase1_result(manifest, "artifactManifest")
    files = manifest.get("files")
    if type(files) is not list or [item.get("path") for item in files if type(item) is dict] != list(PHASE1_PAYLOAD_FILES):
        raise ArtifactError("E3_ARTIFACT_INVALID")
    total = 0
    for item in files:
        if type(item) is not dict or set(item) != {"path", "sha256", "bytes"}:
            raise ArtifactError("E3_ARTIFACT_INVALID")
        content = _read_payload(source, item["path"])
        total += len(content)
        if item["bytes"] != len(content) or not _SHA256.fullmatch(item["sha256"]) or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ArtifactError("E3_ARTIFACT_INVALID")
    if total > MAX_ARTIFACT_BYTES:
        raise ArtifactError("E3_ARTIFACT_INVALID")
    expected_source = {
        "repository": expected_identity.repository,
        "repository_id": expected_identity.repository_id,
        "default_branch": expected_identity.default_branch,
        "workflow_ref": expected_identity.workflow_ref,
        "source_sha": expected_identity.source_sha,
        "workflow_sha": expected_identity.workflow_sha,
        "run_id": expected_identity.run_id,
        "run_attempt": expected_identity.run_attempt,
    }
    if manifest.get("source_identity") != expected_source:
        raise ArtifactError("E3_ARTIFACT_IDENTITY_INVALID")
    try:
        created_at = datetime.strptime(manifest["created_at"], _TIMESTAMP).replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError) as error:
        raise ArtifactError("E3_ARTIFACT_STALE") from error
    if not 0 <= (when - created_at).total_seconds() <= 300:
        raise ArtifactError("E3_ARTIFACT_STALE")
    gate, observed_identity = _ready_phase1(source, when, runner)
    if observed_identity != expected_identity or gate.get("source_identity") != expected_source:
        raise ArtifactError("E3_ARTIFACT_IDENTITY_INVALID")
    return manifest


def verify_downloaded_phase1_artifact(
    source: Path,
    expected_identity: ExpectedIdentity,
    *,
    runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
    validation_at: datetime | None = None,
) -> dict[str, Any]:
    """Verify exact W9 payload bytes, signed identity and GitHub run facts."""

    with _snapshot_phase1_source(source) as snapshot:
        return _verify_phase1_snapshot(snapshot, expected_identity, runner=runner, validation_at=validation_at)


def _phase1_identity_from_github_facts(
    source: Path,
    expected_repository: str,
    expected_repository_id: str,
    expected_default_branch: str,
    expected_run_id: str,
    expected_run_attempt: int,
    expected_source_sha: str,
) -> ExpectedIdentity:
    """Bind caller-supplied GitHub API facts to image identity inside the verifier."""

    from tools.phase1_safety.model import SafetyError, validate_source_identity

    try:
        source_identity = validate_source_identity({
            "repository": expected_repository,
            "repository_id": expected_repository_id,
            "default_branch": expected_default_branch,
            "workflow_ref": f"refs/heads/{expected_default_branch}",
            "source_sha": expected_source_sha,
            "workflow_sha": expected_source_sha,
            "run_id": expected_run_id,
            "run_attempt": expected_run_attempt,
        })
        receipt = _load_json(source / "artifacts/runtime/sandbox-e3-import-receipt.json")
        return ExpectedIdentity(
            source_identity.repository,
            source_identity.repository_id,
            source_identity.default_branch,
            source_identity.source_sha,
            source_identity.workflow_sha,
            source_identity.run_id,
            source_identity.run_attempt,
            receipt["image_ref"],
            receipt["image_digest"],
        )
    except (KeyError, TypeError, ValueError, SafetyError) as error:
        raise ArtifactError("E3_ARTIFACT_IDENTITY_INVALID") from error


def verify_downloaded_phase1_artifact_from_facts(
    source: Path,
    expected_repository: str,
    expected_repository_id: str,
    expected_default_branch: str,
    expected_run_id: str,
    expected_run_attempt: int,
    expected_source_sha: str,
    *,
    runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
    validation_at: datetime | None = None,
) -> dict[str, Any]:
    """Verify W9 evidence from immutable GitHub API facts without pre-reading it."""

    with _snapshot_phase1_source(source) as snapshot:
        identity = _phase1_identity_from_github_facts(
            snapshot,
            expected_repository,
            expected_repository_id,
            expected_default_branch,
            expected_run_id,
            expected_run_attempt,
            expected_source_sha,
        )
        return _verify_phase1_snapshot(snapshot, identity, runner=runner, validation_at=validation_at)


def _verify_snapshot(
    source: Path, expected_repository: str, expected_repository_id: str,
    expected_default_branch: str, expected_run_id: str, expected_run_attempt: int,
    expected_source_sha: str, *, runner: ProcessRunner, validation_at: datetime | None,
) -> dict[str, Any]:
    manifest = _load_json(source / E3_MANIFEST_FILE)
    if set(manifest) != _MANIFEST_KEYS or manifest.get("manifest_version") != "1.0" or manifest.get("status") != "READY":
        raise ArtifactError("E3_ARTIFACT_INVALID")
    files = manifest.get("files")
    if type(files) is not list or len(files) != len(E3_PAYLOAD_FILES):
        raise ArtifactError("E3_ARTIFACT_INVALID")
    if [item.get("path") for item in files if type(item) is dict] != list(E3_PAYLOAD_FILES):
        raise ArtifactError("E3_ARTIFACT_INVALID")
    total = 0
    for item in files:
        if type(item) is not dict or set(item) != {"path", "sha256", "size"} or not _safe_relative(item["path"]):
            raise ArtifactError("E3_ARTIFACT_INVALID")
        content = _read_payload(source, item["path"])
        total += len(content)
        if item["size"] != len(content) or not _SHA256.fullmatch(item["sha256"]) or hashlib.sha256(content).hexdigest() != item["sha256"]:
            raise ArtifactError("E3_ARTIFACT_INVALID")
    if total > MAX_ARTIFACT_BYTES or _has_forbidden_key(manifest):
        raise ArtifactError("E3_ARTIFACT_INVALID")
    expected_values = {
        "repository": expected_repository, "repository_id": expected_repository_id,
        "default_branch": expected_default_branch, "workflow_ref": f"refs/heads/{expected_default_branch}",
        "workflow_sha": expected_source_sha, "source_sha": expected_source_sha,
        "run_id": expected_run_id, "run_attempt": expected_run_attempt,
    }
    if any(manifest.get(key) != value for key, value in expected_values.items()):
        raise ArtifactError("E3_ARTIFACT_IDENTITY_INVALID")
    try:
        created_at = datetime.strptime(manifest["created_at"], _TIMESTAMP).replace(tzinfo=timezone.utc)
    except (KeyError, TypeError, ValueError) as error:
        raise ArtifactError("E3_ARTIFACT_STALE") from error
    validated_at = _validation_time(validation_at)
    if not 0 <= (validated_at - created_at).total_seconds() <= 300:
        raise ArtifactError("E3_ARTIFACT_STALE")
    try:
        identity = ExpectedIdentity(
            expected_repository, expected_repository_id, expected_default_branch, expected_source_sha,
            expected_source_sha, expected_run_id, expected_run_attempt,
            manifest["image_ref"], manifest["image_digest"],
        )
        attestation = verify_signed_attestation(
            source / E3_PAYLOAD_FILES[0], source / E3_PAYLOAD_FILES[1], identity,
            runner, validated_at,
        )
    except (E3Error, KeyError, TypeError) as error:
        raise ArtifactError("E3_ARTIFACT_SIGNATURE_INVALID") from error
    identity_keys = ("repository", "repository_id", "workflow_ref", "workflow_sha", "source_sha", "run_id", "run_attempt", "image_ref", "image_digest", "issuer", "certificate_identity")
    if any(manifest.get(key) != attestation.get(key) for key in identity_keys):
        raise ArtifactError("E3_ARTIFACT_IDENTITY_INVALID")
    if manifest["created_at"] != attestation["observed_at"]:
        raise ArtifactError("E3_ARTIFACT_IDENTITY_INVALID")
    _ready_phase(source)
    return manifest


def verify_downloaded_artifact(
    source: Path, expected_repository: str, expected_repository_id: str,
    expected_default_branch: str, expected_run_id: str, expected_run_attempt: int,
    expected_source_sha: str, *, runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
    validation_at: datetime | None = None,
) -> dict[str, Any]:
    """Verify exact payload hashes, GitHub API identity, freshness and Cosign proof."""

    with _snapshot_source(source) as snapshot:
        return _verify_snapshot(
            snapshot, expected_repository, expected_repository_id, expected_default_branch,
            expected_run_id, expected_run_attempt, expected_source_sha,
            runner=runner, validation_at=validation_at,
        )


def _safe_target(root: Path, relative: str) -> Path:
    if not _safe_relative(relative):
        raise ArtifactError("E3_ARTIFACT_INVALID")
    current = root
    try:
        for part in PurePosixPath(relative).parts[:-1]:
            current = current / part
            if current.is_symlink():
                raise ArtifactError("E3_ARTIFACT_INVALID")
            current.mkdir(exist_ok=True)
            if not current.resolve(strict=True).is_relative_to(root):
                raise ArtifactError("E3_ARTIFACT_INVALID")
        target = current / PurePosixPath(relative).name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ArtifactError("E3_ARTIFACT_INVALID")
    except OSError as error:
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    return target


def stage_upload_artifact(root: Path) -> Path:
    """Create the sole non-hidden upload root from exact allowlisted bytes."""

    root = _root_directory(root)
    staging = root / E3_STAGING_ROOT
    if staging.is_symlink():
        raise ArtifactError("E3_ARTIFACT_INVALID")
    if staging.exists():
        if not staging.is_dir() or not staging.resolve(strict=True).is_relative_to(root):
            raise ArtifactError("E3_ARTIFACT_INVALID")
        shutil.rmtree(staging)
    captured = {relative: _read_payload(root, relative) for relative in E3_ARTIFACT_FILES}
    temporary = Path(tempfile.mkdtemp(prefix="forgeops-e3-upload-", dir=root))
    try:
        for relative, content in captured.items():
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        _exact_tree(temporary)
        os.replace(temporary, staging)
    except (OSError, ArtifactError) as error:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    return staging


def stage_phase1_upload_artifact(root: Path) -> Path:
    """Stage only the explicit versioned W9 public allowlist."""

    root = _root_directory(root)
    staging = root / PHASE1_STAGING_ROOT
    if staging.is_symlink():
        raise ArtifactError("E3_ARTIFACT_INVALID")
    if staging.exists():
        if not staging.is_dir() or not staging.resolve(strict=True).is_relative_to(root):
            raise ArtifactError("E3_ARTIFACT_INVALID")
        shutil.rmtree(staging)
    captured = {relative: _read_payload(root, relative) for relative in PHASE1_ARTIFACT_FILES}
    temporary = Path(tempfile.mkdtemp(prefix="forgeops-phase1-upload-", dir=root))
    try:
        for relative, content in captured.items():
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        _exact_tree_for(temporary, PHASE1_ARTIFACT_FILES)
        os.replace(temporary, staging)
    except (OSError, ArtifactError) as error:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    return staging


def import_downloaded_phase1_artifact(
    source: Path,
    root: Path,
    expected_identity: ExpectedIdentity,
    *,
    runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
    validation_at: datetime | None = None,
    replacer=os.replace,
) -> dict[str, Path]:
    """Verify a W9 snapshot before replacing only versioned allowlist targets."""

    resolved_root = _root_directory(root)
    targets = {relative: _safe_target(resolved_root, relative) for relative in PHASE1_ARTIFACT_FILES}
    manifest_target = targets[PHASE1_MANIFEST_FILE]
    _remove_output(manifest_target)
    staged: dict[str, Path] = {}
    try:
        with _snapshot_phase1_source(source) as snapshot_root:
            _verify_phase1_snapshot(snapshot_root, expected_identity, runner=runner, validation_at=validation_at)
            captured = {relative: _read_payload(snapshot_root, relative) for relative in PHASE1_ARTIFACT_FILES}
            for relative, content in captured.items():
                target = targets[relative]
                descriptor, temporary_name = tempfile.mkstemp(prefix=".phase1-import-", dir=target.parent)
                with os.fdopen(descriptor, "wb") as temporary_file:
                    temporary_file.write(content)
                staged[relative] = Path(temporary_name)
            for relative in PHASE1_PAYLOAD_FILES:
                replacer(staged.pop(relative), targets[relative])
            replacer(staged.pop(PHASE1_MANIFEST_FILE), manifest_target)
    except (OSError, ArtifactError) as error:
        _remove_output(manifest_target)
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    finally:
        for temporary in staged.values():
            if temporary.exists():
                temporary.unlink()
    return targets


def import_downloaded_phase1_artifact_from_facts(
    source: Path,
    root: Path,
    expected_repository: str,
    expected_repository_id: str,
    expected_default_branch: str,
    expected_run_id: str,
    expected_run_attempt: int,
    expected_source_sha: str,
    *,
    runner: ProcessRunner = DEFAULT_PROCESS_RUNNER,
    validation_at: datetime | None = None,
    replacer=os.replace,
) -> dict[str, Path]:
    """Import W9 evidence using only independently observed GitHub API facts."""

    with _snapshot_phase1_source(source) as snapshot:
        identity = _phase1_identity_from_github_facts(
            snapshot,
            expected_repository,
            expected_repository_id,
            expected_default_branch,
            expected_run_id,
            expected_run_attempt,
            expected_source_sha,
        )
        return import_downloaded_phase1_artifact(
            snapshot,
            root,
            identity,
            runner=runner,
            validation_at=validation_at,
            replacer=replacer,
        )


def import_downloaded_artifact(source: Path, root: Path, expected_identity: ExpectedIdentity, *, runner: ProcessRunner = DEFAULT_PROCESS_RUNNER, validation_at: datetime | None = None, replacer=os.replace) -> dict[str, Path]:
    """Verify then atomically replace only fixed repository targets."""

    resolved_root = _root_directory(root)
    targets = {relative: _safe_target(resolved_root, relative) for relative in E3_ARTIFACT_FILES}
    manifest_target = targets[E3_MANIFEST_FILE]
    _remove_output(manifest_target)
    staged: dict[str, Path] = {}
    try:
        with _snapshot_source(source) as snapshot_root:
            _verify_snapshot(
                snapshot_root, expected_identity.repository, expected_identity.repository_id,
                expected_identity.default_branch, expected_identity.run_id,
                expected_identity.run_attempt, expected_identity.source_sha,
                runner=runner, validation_at=validation_at,
            )
            captured = {relative: _read_payload(snapshot_root, relative) for relative in E3_ARTIFACT_FILES}
            for relative, content in captured.items():
                target = targets[relative]
                descriptor, temporary_name = tempfile.mkstemp(prefix=".e3-import-", dir=target.parent)
                with os.fdopen(descriptor, "wb") as temporary_file:
                    temporary_file.write(content)
                staged[relative] = Path(temporary_name)
            for relative in E3_PAYLOAD_FILES:
                replacer(staged.pop(relative), targets[relative])
            replacer(staged.pop(E3_MANIFEST_FILE), manifest_target)
    except (OSError, ArtifactError) as error:
        _remove_output(manifest_target)
        raise ArtifactError("E3_ARTIFACT_INVALID") from error
    finally:
        for temporary in staged.values():
            if temporary.exists():
                temporary.unlink()
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ForgeOps E3 public artifact verifier")
    subparsers = parser.add_subparsers(dest="operation", required=True)
    subparsers.add_parser("build")
    subparsers.add_parser("stage-upload")
    subparsers.add_parser("build-phase1")
    subparsers.add_parser("stage-phase1-upload")
    verify = subparsers.add_parser("verify-download")
    verify.add_argument("--source", required=True)
    verify.add_argument("--expected-repository", required=True)
    verify.add_argument("--expected-repository-id", required=True)
    verify.add_argument("--expected-default-branch", required=True)
    verify.add_argument("--expected-run-id", required=True)
    verify.add_argument("--expected-run-attempt", required=True, type=int)
    verify.add_argument("--expected-source-sha", required=True)
    phase1_verify = subparsers.add_parser("verify-phase1-download")
    phase1_import = subparsers.add_parser("import-phase1-download")
    for phase1_parser in (phase1_verify, phase1_import):
        phase1_parser.add_argument("--source", required=True)
        phase1_parser.add_argument("--expected-repository", required=True)
        phase1_parser.add_argument("--expected-repository-id", required=True)
        phase1_parser.add_argument("--expected-default-branch", required=True)
        phase1_parser.add_argument("--expected-run-id", required=True)
        phase1_parser.add_argument("--expected-run-attempt", required=True, type=int)
        phase1_parser.add_argument("--expected-source-sha", required=True)
    arguments = parser.parse_args(argv)
    try:
        if arguments.operation == "build":
            build_manifest(_ROOT, _ROOT / E3_MANIFEST_FILE)
        elif arguments.operation == "stage-upload":
            stage_upload_artifact(_ROOT)
        elif arguments.operation == "build-phase1":
            build_phase1_manifest(_ROOT, _ROOT / PHASE1_MANIFEST_FILE)
        elif arguments.operation == "stage-phase1-upload":
            stage_phase1_upload_artifact(_ROOT)
        elif arguments.operation == "verify-download":
            verify_downloaded_artifact(
                Path(arguments.source), arguments.expected_repository, arguments.expected_repository_id,
                arguments.expected_default_branch, arguments.expected_run_id,
                arguments.expected_run_attempt, arguments.expected_source_sha,
            )
        elif arguments.operation == "verify-phase1-download":
            verify_downloaded_phase1_artifact_from_facts(
                Path(arguments.source), arguments.expected_repository, arguments.expected_repository_id,
                arguments.expected_default_branch, arguments.expected_run_id,
                arguments.expected_run_attempt, arguments.expected_source_sha,
            )
        else:
            import_downloaded_phase1_artifact_from_facts(
                Path(arguments.source), _ROOT, arguments.expected_repository,
                arguments.expected_repository_id, arguments.expected_default_branch,
                arguments.expected_run_id, arguments.expected_run_attempt,
                arguments.expected_source_sha,
            )
    except ArtifactError:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
