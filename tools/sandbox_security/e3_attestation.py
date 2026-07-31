"""Closed import boundary for GitHub Actions E3 runtime attestations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Protocol

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


OIDC_ISSUER = "https://token.actions.githubusercontent.com"
_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _ROOT / "contracts/forgeops-e3-attestation/1.0/schema.json"
_SANDBOX_SCHEMA_PATH = _ROOT / "contracts/forgeops-sandbox-contract/1.0/schema.json"
_SANDBOX_SUITE_PATH = _ROOT / "fixtures/forgeops-sandbox-security/suite.json"
_TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_KEYS = frozenset({"token", "secret", "credential", "environment", "stdout", "stderr", "log", "certificate_pem", "certificate_chain", "private_path"})
_CATALOGS = ("image_cases", "containment_cases", "egress_cases", "quota_cases", "teardown_cases")


class ProcessRunner(Protocol):
    def __call__(self, args: list[str], *, shell: bool, check: bool, capture_output: bool, text: bool, timeout: int) -> subprocess.CompletedProcess[str]: ...


DEFAULT_PROCESS_RUNNER = subprocess.run


class E3Error(Exception):
    """Stable, public-safe E3 importer rejection."""


@dataclass(frozen=True)
class ExpectedIdentity:
    repository: str
    repository_id: str
    default_branch: str
    source_sha: str
    workflow_sha: str
    run_id: str
    run_attempt: int
    image_ref: str
    image_digest: str

    @property
    def workflow_ref(self) -> str:
        return f"refs/heads/{self.default_branch}"

    @property
    def certificate_identity(self) -> str:
        return f"https://github.com/{self.repository}/.github/workflows/vg-008-e3.yml@{self.workflow_ref}"


def _canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _load_json_bytes(path: Path) -> tuple[bytes, dict[str, Any]]:
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise E3Error("E3_ATTESTATION_INVALID") from error
    if not isinstance(value, dict):
        raise E3Error("E3_ATTESTATION_INVALID")
    return raw, value


def _contains_forbidden_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(not isinstance(key, str) or key.lower() in _FORBIDDEN_KEYS or _contains_forbidden_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_forbidden_key(item) for item in value)
    return False


def _load_validator() -> Draft202012Validator:
    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
        return Draft202012Validator(schema, format_checker=FormatChecker())
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as error:
        raise E3Error("E3_ATTESTATION_INVALID") from error


def _registered_case_ids() -> list[str]:
    try:
        suite = json.loads(_SANDBOX_SUITE_PATH.read_text(encoding="utf-8"))
        return [case["id"] for catalog in _CATALOGS for case in suite[catalog]]
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise E3Error("E3_ATTESTATION_INVALID") from error


def _public_profile(attestation: dict[str, Any]) -> dict[str, Any]:
    provenance = (attestation["image_ref"], attestation["image_digest"], attestation["issuer"], attestation["certificate_identity"])
    return {
        "runtime": "docker", "available": True, "rootless": attestation["capabilities"]["rootless"],
        "image_ref": attestation["image_ref"], "image_digest": attestation["image_digest"], "signature_verified": True,
        "issuer": attestation["issuer"], "expected_issuer": OIDC_ISSUER,
        "provenance_ref": "sha256:" + _sha256_bytes(_canonical_bytes(provenance)), "observed_at": attestation["observed_at"],
    }


def _validate_identity(attestation: dict[str, Any], expected: ExpectedIdentity) -> None:
    expected_image_ref = f"ghcr.io/{expected.repository}-e3@{expected.image_digest}"
    if expected.image_ref != expected_image_ref:
        raise E3Error("E3_IDENTITY_INVALID")
    expected_fields = {
        "repository": expected.repository, "repository_id": expected.repository_id, "workflow_ref": expected.workflow_ref,
        "workflow_sha": expected.workflow_sha, "source_sha": expected.source_sha, "run_id": expected.run_id,
        "run_attempt": expected.run_attempt, "image_ref": expected.image_ref, "image_digest": expected.image_digest,
        "certificate_identity": expected.certificate_identity, "issuer": OIDC_ISSUER,
    }
    if any(attestation.get(key) != value for key, value in expected_fields.items()):
        raise E3Error("E3_IDENTITY_INVALID")
    if expected.image_ref.rsplit("@", 1)[-1] != expected.image_digest:
        raise E3Error("E3_IDENTITY_INVALID")


def _validation_time(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise E3Error("E3_EVIDENCE_STALE")
    return value.astimezone(timezone.utc)


def _validate_freshness(attestation: dict[str, Any], validation_at: datetime) -> None:
    try:
        timestamps = [attestation["observed_at"], *(item["observed_at"] for item in attestation["observations"])]
        for value in timestamps:
            observed = datetime.strptime(value, _TIMESTAMP).replace(tzinfo=timezone.utc)
            age = (validation_at - observed).total_seconds()
            if not 0 <= age <= 300:
                raise E3Error("E3_EVIDENCE_STALE")
    except (KeyError, TypeError, ValueError) as error:
        raise E3Error("E3_EVIDENCE_STALE") from error


def _validate_hashes(attestation: dict[str, Any]) -> None:
    hashes = attestation["input_hashes"]
    try:
        if hashes["sandbox_schema_sha256"] != _sha256_bytes(_SANDBOX_SCHEMA_PATH.read_bytes()):
            raise E3Error("E3_HASH_MISMATCH")
        if hashes["sandbox_suite_sha256"] != _sha256_bytes(_SANDBOX_SUITE_PATH.read_bytes()):
            raise E3Error("E3_HASH_MISMATCH")
        if hashes["runtime_profile_sha256"] != _sha256_bytes(_canonical_bytes(_public_profile(attestation))):
            raise E3Error("E3_HASH_MISMATCH")
    except (KeyError, OSError, TypeError) as error:
        raise E3Error("E3_HASH_MISMATCH") from error


def _validate_attestation(attestation: dict[str, Any], expected: ExpectedIdentity, validation_at: datetime) -> None:
    if _contains_forbidden_key(attestation):
        raise E3Error("E3_ATTESTATION_INVALID")
    # The issuer is a caller-bound trust identity, not merely a schema literal.
    if attestation.get("issuer") != OIDC_ISSUER:
        raise E3Error("E3_IDENTITY_INVALID")
    try:
        _load_validator().validate(attestation)
    except ValidationError as error:
        raise E3Error("E3_ATTESTATION_INVALID") from error
    observations = attestation["observations"]
    case_ids = [item["case_id"] for item in observations]
    if case_ids != _registered_case_ids() or len(case_ids) != len(set(case_ids)):
        raise E3Error("E3_ATTESTATION_INVALID")
    _validate_identity(attestation, expected)
    _validate_freshness(attestation, validation_at)
    _validate_hashes(attestation)


def verify_signed_attestation(attestation_path: Path, bundle_path: Path, expected: ExpectedIdentity, runner: ProcessRunner = DEFAULT_PROCESS_RUNNER, validation_at: datetime | None = None) -> dict[str, Any]:
    """Validate the public bytes and verify their exact Cosign identity."""

    raw, attestation = _load_json_bytes(attestation_path)
    try:
        bundle_path.read_bytes()
    except OSError as error:
        raise E3Error("E3_ATTESTATION_INVALID") from error
    _validate_attestation(attestation, expected, _validation_time(validation_at))
    arguments = ["cosign", "verify-blob", "--bundle", str(bundle_path), "--certificate-identity", expected.certificate_identity, "--certificate-oidc-issuer", OIDC_ISSUER, str(attestation_path)]
    try:
        result = runner(arguments, shell=False, check=False, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError) as error:
        raise E3Error("E3_SIGNATURE_INVALID") from error
    if not isinstance(result, subprocess.CompletedProcess) or result.returncode != 0:
        raise E3Error("E3_SIGNATURE_INVALID")
    return attestation


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".e3-import-", suffix=".json", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as target:
            target.write(_canonical_bytes(value))
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def import_signed_attestation(attestation_path: Path, bundle_path: Path, expected: ExpectedIdentity, output_root: Path, runner: ProcessRunner = DEFAULT_PROCESS_RUNNER, validation_at: datetime | None = None) -> dict[str, Path]:
    """Verify and atomically project only the three fixed runtime artifacts."""

    try:
        source_attestation_bytes = attestation_path.read_bytes()
        source_bundle_bytes = bundle_path.read_bytes()
    except OSError as error:
        raise E3Error("E3_ATTESTATION_INVALID") from error
    with tempfile.TemporaryDirectory(prefix=".e3-snapshot-") as snapshot_directory:
        snapshot_root = Path(snapshot_directory)
        snapshot_attestation = snapshot_root / "e3-attestation.json"
        snapshot_bundle = snapshot_root / "e3-attestation.bundle.json"
        snapshot_attestation.write_bytes(source_attestation_bytes)
        snapshot_bundle.write_bytes(source_bundle_bytes)
        attestation = verify_signed_attestation(snapshot_attestation, snapshot_bundle, expected, runner, validation_at)
        outputs = {
            "profile": output_root / "artifacts/runtime/sandbox-runtime-profile.json",
            "observations": output_root / "artifacts/runtime/sandbox-runtime-observations.json",
            "receipt": output_root / "artifacts/runtime/sandbox-e3-import-receipt.json",
        }
        profile = _public_profile(attestation)
        observations = {
            "observations_version": "1.0",
            "observed_at": attestation["observed_at"],
            "observations": attestation["observations"],
            "terminal_residue": attestation["terminal_residue"],
        }
        _atomic_write(outputs["profile"], profile)
        _atomic_write(outputs["observations"], observations)
        receipt = {
            "receipt_version": "1.0", "attestation_sha256": _sha256_bytes(source_attestation_bytes), "bundle_sha256": _sha256_bytes(source_bundle_bytes),
            "repository": expected.repository, "repository_id": expected.repository_id, "default_branch": expected.default_branch, "workflow_ref": expected.workflow_ref,
            "source_sha": expected.source_sha, "workflow_sha": expected.workflow_sha, "run_id": expected.run_id, "run_attempt": expected.run_attempt,
            "image_ref": expected.image_ref, "image_digest": expected.image_digest, "issuer": OIDC_ISSUER,
            "certificate_identity": expected.certificate_identity, "observed_at": attestation["observed_at"],
            "verification_kind": "runtime" if runner is DEFAULT_PROCESS_RUNNER else "test",
            "runtime_profile_sha256": _sha256_bytes(outputs["profile"].read_bytes()), "runtime_observations_sha256": _sha256_bytes(outputs["observations"].read_bytes()),
        }
        _atomic_write(outputs["receipt"], receipt)
    return outputs
