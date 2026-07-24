"""In-memory validation for the ForgeOps run-manifest contract."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .common import ContractError, is_strict_utc


MANIFEST_ERROR_CODES = (
    "MANIFEST_SCHEMA_INVALID",
    "MANIFEST_IDENTITY_MISMATCH",
    "MANIFEST_MODE_INVALID",
    "MANIFEST_EVENT_RANGE_INVALID",
    "MANIFEST_ID_DUPLICATE",
    "MANIFEST_REFERENCE_DANGLING",
    "MANIFEST_REFERENCE_CROSS_RUN",
    "MANIFEST_PRODUCER_SEQUENCE_INVALID",
    "MANIFEST_EVIDENCE_FRESHNESS_INVALID",
    "MANIFEST_HASH_INVALID",
    "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
)

TERMINAL_STATUSES = frozenset({"BLOCKED", "SUCCEEDED", "FAILED"})
RUN_MODES = ("PRIMARY", "AUDIT_REPLAY", "COUNTERFACTUAL", "REEXECUTE")
REVISION_EVIDENCE_TYPES = frozenset({"file", "diff"})
TIME_EVIDENCE_TYPES = frozenset(
    {"command", "test", "render", "runtime", "approval"}
)
FORGEOPS_SOURCE_REF = re.compile(
    r"^forgeops:(?P<kind>[a-z][a-z0-9_-]{0,31}):"
    r"[A-Za-z0-9][A-Za-z0-9._-]{0,126}$"
)
FORGEOPS_SOURCE_KINDS = frozenset(
    {
        "approval",
        "artifact",
        "command",
        "diff",
        "event",
        "evidence",
        "file",
        "manifest",
        "render",
        "report",
        "result",
        "run",
        "runtime",
        "stream",
        "task",
        "test",
    }
)
RELATIVE_SOURCE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
SENSITIVE_KEY_PARTS = frozenset(
    {
        "authorization",
        "cookie",
        "credential",
        "password",
        "private_key",
        "raw_content",
        "raw_secret",
        "secret",
        "signed_url",
        "tenant",
        "token",
    }
)
PATH_FIELD_NAMES = frozenset({"absolute_path", "file_path", "filesystem_path", "path"})


class StorageSpy:
    """Test seam proving validation performs no storage effect on rejection."""

    def __init__(self) -> None:
        self.calls = 0

    def store(self, _manifest: dict[str, Any]) -> None:
        self.calls += 1


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Serialize after excluding only the root self-hash field."""
    if not isinstance(manifest, dict):
        raise ContractError("MANIFEST_SCHEMA_INVALID")
    payload = {
        key: value for key, value in manifest.items() if key != "manifest_sha256"
    }
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ContractError("MANIFEST_SCHEMA_INVALID") from exc


def calculate_manifest_sha256(manifest: dict[str, Any]) -> str:
    """Return the lowercase SHA-256 digest of canonical manifest bytes."""
    return hashlib.sha256(canonical_manifest_bytes(manifest)).hexdigest()


def _parse_utc(value: object) -> datetime:
    if not is_strict_utc(value):
        raise ContractError("MANIFEST_SCHEMA_INVALID")
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )


def validate_lifecycle(manifest: dict[str, Any]) -> None:
    """Enforce terminal/finalized/decision consistency without changing state."""
    created_at = _parse_utc(manifest["created_at"])
    finalized_at_value = manifest.get("finalized_at")
    finalized_at = (
        _parse_utc(finalized_at_value) if finalized_at_value is not None else None
    )
    terminal_refs = [
        decision
        for decision in manifest["decision_refs"]
        if decision["decision_kind"] == "TERMINAL"
    ]
    terminal_status = manifest["status"] in TERMINAL_STATUSES

    if terminal_status:
        if finalized_at is None or len(terminal_refs) != 1:
            raise ContractError("MANIFEST_IDENTITY_MISMATCH")
        if finalized_at < created_at:
            raise ContractError("MANIFEST_IDENTITY_MISMATCH")
    elif finalized_at is not None or terminal_refs:
        raise ContractError("MANIFEST_IDENTITY_MISMATCH")


def _is_sensitive_key(key: object) -> bool:
    if not isinstance(key, str):
        return True
    lowered = key.lower()
    if lowered in PATH_FIELD_NAMES:
        return True
    return any(
        lowered == part
        or lowered.startswith(f"{part}_")
        or lowered.endswith(f"_{part}")
        for part in SENSITIVE_KEY_PARTS
    )


def _validate_sensitive_content(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if _is_sensitive_key(key):
                raise ContractError("MANIFEST_SENSITIVE_CONTENT_FORBIDDEN")
            _validate_sensitive_content(item)
    elif isinstance(value, list):
        for item in value:
            _validate_sensitive_content(item)
    elif isinstance(value, str):
        lowered = value.lower()
        if lowered.startswith(("http://", "https://")) or any(
            marker in lowered
            for marker in ("x-amz-signature=", "x-goog-signature=", "signature=", "sig=")
        ):
            raise ContractError("MANIFEST_SENSITIVE_CONTENT_FORBIDDEN")


def validate_source_ref(source_ref: object) -> None:
    """Accept a literal root-relative path or a closed ForgeOps opaque URN."""
    if not isinstance(source_ref, str) or not source_ref or len(source_ref) > 255:
        raise ContractError("MANIFEST_SENSITIVE_CONTENT_FORBIDDEN")
    forgeops_match = FORGEOPS_SOURCE_REF.fullmatch(source_ref)
    if forgeops_match:
        if forgeops_match.group("kind") in FORGEOPS_SOURCE_KINDS:
            return
        raise ContractError("MANIFEST_SENSITIVE_CONTENT_FORBIDDEN")
    if (
        source_ref.startswith(("/", "\\"))
        or re.match(r"^[A-Za-z]:", source_ref)
        or "\\" in source_ref
        or "//" in source_ref
        or any(character in source_ref for character in "*?#[]{}%")
        or any(character.isspace() for character in source_ref)
    ):
        raise ContractError("MANIFEST_SENSITIVE_CONTENT_FORBIDDEN")
    segments = source_ref.split("/")
    if any(
        segment in {"", ".", ".."}
        or RELATIVE_SOURCE_SEGMENT.fullmatch(segment) is None
        or _is_protected_source_segment(segment)
        for segment in segments
    ):
        raise ContractError("MANIFEST_SENSITIVE_CONTENT_FORBIDDEN")


def _is_protected_source_segment(segment: str) -> bool:
    lowered = segment.lower()
    if lowered == ".env" or lowered.startswith(".env."):
        return True
    words = set(filter(None, re.split(r"[._-]+", lowered)))
    return bool(
        words
        & {
            "credential",
            "credentials",
            "password",
            "secret",
            "secrets",
            "token",
            "tokens",
        }
    ) or lowered in {"id_rsa", "id_ed25519"}


def validate_evidence_freshness(evidence_records: object) -> None:
    """Enforce the closed revision/time freshness union with stable errors."""
    if not isinstance(evidence_records, list):
        return
    for evidence in evidence_records:
        if not isinstance(evidence, dict):
            continue
        evidence_type = evidence.get("type")
        has_revision = "observed_revision" in evidence
        has_time = "observed_at" in evidence
        if evidence_type in REVISION_EVIDENCE_TYPES:
            revision = evidence.get("observed_revision")
            if (
                not has_revision
                or has_time
                or isinstance(revision, bool)
                or not isinstance(revision, int)
                or revision < 0
            ):
                raise ContractError("MANIFEST_EVIDENCE_FRESHNESS_INVALID")
        elif evidence_type in TIME_EVIDENCE_TYPES:
            if not has_time or has_revision or not is_strict_utc(evidence.get("observed_at")):
                raise ContractError("MANIFEST_EVIDENCE_FRESHNESS_INVALID")


def _unique_index(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    values = [item[key] for item in items]
    if len(values) != len(set(values)):
        raise ContractError("MANIFEST_ID_DUPLICATE")
    return {item[key]: item for item in items}


def _validate_producer_range(sequence: int, event_stream: dict[str, Any]) -> None:
    if not event_stream["first_seq"] <= sequence <= event_stream["last_seq"]:
        raise ContractError("MANIFEST_PRODUCER_SEQUENCE_INVALID")


def validate_catalogs_and_references(manifest: dict[str, Any]) -> None:
    """Resolve every manifest-local identity exactly once and in range."""
    artifacts = _unique_index(manifest["artifacts"], "artifact_id")
    evidence = _unique_index(manifest["evidence"], "evidence_id")
    decisions = _unique_index(manifest["decision_refs"], "decision_id")
    event_stream = manifest["event_stream"]

    for record in [*artifacts.values(), *evidence.values(), *decisions.values()]:
        _validate_producer_range(record["producer_event_seq"], event_stream)

    for record in evidence.values():
        validate_source_ref(record["source_ref"])

    for decision in decisions.values():
        artifact_refs = decision["artifact_refs"]
        evidence_refs = decision["evidence_refs"]
        if len(artifact_refs) != len(set(artifact_refs)) or len(evidence_refs) != len(
            set(evidence_refs)
        ):
            raise ContractError("MANIFEST_ID_DUPLICATE")
        if any(reference not in artifacts for reference in artifact_refs):
            raise ContractError("MANIFEST_REFERENCE_DANGLING")
        if any(reference not in evidence for reference in evidence_refs):
            raise ContractError("MANIFEST_REFERENCE_DANGLING")

    validate_evidence_freshness(manifest["evidence"])


def _validate_resolution_context(
    manifest: dict[str, Any], resolution_context: object
) -> None:
    if not isinstance(resolution_context, dict):
        raise ContractError("MANIFEST_REFERENCE_CROSS_RUN")
    catalog_ids = {
        record["artifact_id"] for record in manifest["artifacts"]
    } | {record["evidence_id"] for record in manifest["evidence"]}
    if set(resolution_context) != catalog_ids:
        raise ContractError("MANIFEST_REFERENCE_CROSS_RUN")
    expected_identity = {"task_id": manifest["task_id"], "run_id": manifest["run_id"]}
    for identity in resolution_context.values():
        if identity != expected_identity:
            raise ContractError("MANIFEST_REFERENCE_CROSS_RUN")


def validate_manifest_case(
    case: dict[str, Any],
    schema: dict[str, Any],
    storage_spy: StorageSpy | None = None,
) -> str:
    """Validate a fixture case and its non-persisted same-run resolution context."""
    expected_fields = {
        "id",
        "kind",
        "manifest",
        "resolution_context",
        "expected",
        "expected_storage_calls",
    }
    if not isinstance(case, dict) or set(case) != expected_fields:
        raise ContractError("MANIFEST_SCHEMA_INVALID")
    result = validate_manifest(case["manifest"], schema)
    _validate_resolution_context(case["manifest"], case["resolution_context"])
    if storage_spy is not None and storage_spy.calls != 0:
        raise ContractError("MANIFEST_SENSITIVE_CONTENT_FORBIDDEN")
    return result


def validate_manifest(manifest: dict[str, Any], schema: dict[str, Any]) -> str:
    """Validate one self-contained manifest without performing storage effects."""
    _validate_sensitive_content(manifest)
    if isinstance(manifest, dict):
        if "run_mode" in manifest and manifest["run_mode"] not in RUN_MODES:
            raise ContractError("MANIFEST_MODE_INVALID")
        validate_evidence_freshness(manifest.get("evidence"))
        evidence_records = manifest.get("evidence")
        if isinstance(evidence_records, list):
            for evidence in evidence_records:
                if isinstance(evidence, dict) and "source_ref" in evidence:
                    validate_source_ref(evidence["source_ref"])
    try:
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(manifest))
    except (SchemaError, TypeError, ValueError) as exc:
        raise ContractError("MANIFEST_SCHEMA_INVALID") from exc
    if errors:
        raise ContractError("MANIFEST_SCHEMA_INVALID")

    validate_catalogs_and_references(manifest)
    validate_lifecycle(manifest)

    stream = manifest["event_stream"]
    if stream["count"] != stream["last_seq"] - stream["first_seq"] + 1:
        raise ContractError("MANIFEST_EVENT_RANGE_INVALID")

    if calculate_manifest_sha256(manifest) != manifest["manifest_sha256"]:
        raise ContractError("MANIFEST_HASH_INVALID")
    return "PASSED"


__all__ = [
    "ContractError",
    "MANIFEST_ERROR_CODES",
    "FORGEOPS_SOURCE_KINDS",
    "RUN_MODES",
    "StorageSpy",
    "TERMINAL_STATUSES",
    "calculate_manifest_sha256",
    "canonical_manifest_bytes",
    "validate_lifecycle",
    "validate_manifest",
    "validate_catalogs_and_references",
    "validate_evidence_freshness",
    "validate_manifest_case",
    "validate_source_ref",
]
