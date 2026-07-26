"""Pure pre-storage redaction and artifact-admission evaluator.

This module intentionally contains no command-line or external-effect surface.
All effects are represented by ``SurfaceSpy`` and stay in memory.
"""

from __future__ import annotations

import base64
import hashlib
import math
import re
from typing import Any


TEST_MARKER = "FORGEOPS_TEST_SECRET_DO_NOT_STORE"
SURFACES = ("packet", "event", "prompt", "artifact", "trace", "telemetry", "response")
FORBIDDEN_KEYS = {
    "credential",
    "credentials",
    "token",
    "secret",
    "private",
    "raw",
    "raw_log",
    "raw_event",
    "raw_manifest",
    "headers",
    "signed_url",
}
REDACTED = "[REDACTED]"
MAX_DEPTH = 12
MAX_ITEMS = 1000
MAX_STRING_LENGTH = 4096

_ARTIFACT_FIELDS = {
    "artifact_id",
    "tenant_id",
    "source_ref",
    "checksum_sha256",
    "encryption_state",
    "retention_class",
    "deletion_policy",
    "tamper_ref",
}
_IDENTITY = re.compile(r"^[A-Z][A-Z0-9_-]{2,63}$")
_CHECKSUM = re.compile(r"^[0-9a-f]{64}$")
_TAMPER_REF = re.compile(r"^forgeops:tamper:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SOURCE_REF = re.compile(
    r"^(?!/)(?!.*(?:^|/)\.{1,2}(?:/|$))(?!.*\\)(?!.*[?#@])(?:[A-Za-z0-9._-]+/)*[A-Za-z0-9._-]+$"
)
_OPAQUE_ARTIFACT_REF = re.compile(r"^forgeops:artifact:[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_CREDENTIAL_VALUE = re.compile(
    r"(?i)(?:\bbearer\s+\S{1,512}|\bbasic\s+\S{1,512}|"
    r"\b(?:credential|credentials|token|secret|password|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*\S{1,512}|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----)"
)
_ALLOWED_POLICY_COMBINATIONS = {
    ("ENCRYPTED", "EPHEMERAL", "DELETE_ON_TERMINAL"),
    ("ENCRYPTED", "AUDIT_SHORT", "DELETE_AFTER_RETENTION"),
    ("PUBLIC_SAFE", "PUBLIC", "RETAIN_PUBLIC"),
}


class SecretArtifactError(Exception):
    """Stable public rejection category; no source content is retained."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SurfaceSpy:
    """Counts the only evaluator effect boundaries and retains safe values."""

    def __init__(self) -> None:
        self.store_calls = 0
        self.export_calls = 0
        self.publish_calls = 0
        self.admitted_values: list[object] = []

    def store(self, value: object) -> None:
        self.store_calls += 1
        self.admitted_values.append(value)

    def export(self, value: object) -> None:
        self.export_calls += 1
        self.admitted_values.append(value)

    def publish(self, value: object) -> None:
        self.publish_calls += 1
        self.admitted_values.append(value)


def _marker_variants(markers: tuple[str, ...]) -> set[str]:
    variants: set[str] = set()
    for marker in markers:
        if not isinstance(marker, str) or not marker:
            raise SecretArtifactError("REDACTION_UNSUPPORTED")
        encoded = marker.encode("utf-8")
        variants.update(
            {
                marker,
                base64.b64encode(encoded).decode("ascii"),
                base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("="),
                encoded.hex(),
                encoded.hex().upper(),
                hashlib.sha256(encoded).hexdigest(),
                hashlib.sha256(encoded).hexdigest().upper(),
            }
        )
    return variants


def _contains_unsafe_text(value: str, variants: set[str]) -> bool:
    return any(variant in value for variant in variants) or _CREDENTIAL_VALUE.search(value) is not None


def _redact_value(value: object, variants: set[str], *, depth: int, item_count: list[int]) -> object:
    if depth > MAX_DEPTH:
        raise SecretArtifactError("REDACTION_UNSUPPORTED")
    item_count[0] += 1
    if item_count[0] > MAX_ITEMS:
        raise SecretArtifactError("REDACTION_UNSUPPORTED")

    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError:
            raise SecretArtifactError("REDACTION_UNSUPPORTED") from None
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH:
            raise SecretArtifactError("REDACTION_UNSUPPORTED")
        return REDACTED if _contains_unsafe_text(value, variants) else value
    if value is None or isinstance(value, bool) or (isinstance(value, int) and not isinstance(value, bool)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SecretArtifactError("REDACTION_UNSUPPORTED")
        return value
    if isinstance(value, list):
        return [_redact_value(item, variants, depth=depth + 1, item_count=item_count) for item in value]
    if isinstance(value, dict):
        projected: dict[str, object] = {}
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > MAX_STRING_LENGTH or _contains_unsafe_text(key, variants):
                raise SecretArtifactError("REDACTION_UNSUPPORTED")
            if key.lower() == "unsupported":
                raise SecretArtifactError("REDACTION_UNSUPPORTED")
            if key.lower() in FORBIDDEN_KEYS:
                projected[key] = REDACTED
            else:
                projected[key] = _redact_value(item, variants, depth=depth + 1, item_count=item_count)
        return projected
    raise SecretArtifactError("REDACTION_UNSUPPORTED")


def redact_surface(surface: str, value: object, markers: tuple[str, ...]) -> object:
    """Create a bounded safe projection for one of the seven public surfaces."""

    if surface not in SURFACES:
        raise SecretArtifactError("REDACTION_UNSUPPORTED")
    projected = _redact_value(value, _marker_variants(markers), depth=0, item_count=[0])
    validate_public_projection(projected, markers)
    return projected


def _validate_public_value(value: object, variants: set[str], *, depth: int, item_count: list[int]) -> None:
    if depth > MAX_DEPTH:
        raise SecretArtifactError("REDACTION_UNSUPPORTED")
    item_count[0] += 1
    if item_count[0] > MAX_ITEMS:
        raise SecretArtifactError("REDACTION_UNSUPPORTED")
    if isinstance(value, str):
        if len(value) > MAX_STRING_LENGTH or _contains_unsafe_text(value, variants):
            raise SecretArtifactError("REDACTION_UNSUPPORTED")
        return
    if value is None or isinstance(value, bool) or (isinstance(value, int) and not isinstance(value, bool)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SecretArtifactError("REDACTION_UNSUPPORTED")
        return
    if isinstance(value, list):
        for item in value:
            _validate_public_value(item, variants, depth=depth + 1, item_count=item_count)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or len(key) > MAX_STRING_LENGTH or _contains_unsafe_text(key, variants):
                raise SecretArtifactError("REDACTION_UNSUPPORTED")
            _validate_public_value(item, variants, depth=depth + 1, item_count=item_count)
        return
    raise SecretArtifactError("REDACTION_UNSUPPORTED")


def validate_public_projection(value: object, markers: tuple[str, ...]) -> None:
    """Reject a public value containing raw, encoded, hashed, or credential data."""

    _validate_public_value(value, _marker_variants(markers), depth=0, item_count=[0])


def _validate_artifact_schema(artifact: object) -> dict[str, Any]:
    if not isinstance(artifact, dict) or set(artifact) != _ARTIFACT_FIELDS:
        raise SecretArtifactError("ARTIFACT_POLICY_INVALID")
    if not all(isinstance(artifact[field], str) and artifact[field] for field in _ARTIFACT_FIELDS):
        raise SecretArtifactError("ARTIFACT_POLICY_INVALID")
    return artifact


def _validate_source_ref(source_ref: str) -> None:
    if _SOURCE_REF.fullmatch(source_ref) is None and _OPAQUE_ARTIFACT_REF.fullmatch(source_ref) is None:
        raise SecretArtifactError("ARTIFACT_REFERENCE_INVALID")


def _validate_artifact_policy(artifact: dict[str, Any]) -> None:
    combination = (artifact["encryption_state"], artifact["retention_class"], artifact["deletion_policy"])
    if combination not in _ALLOWED_POLICY_COMBINATIONS:
        raise SecretArtifactError("ARTIFACT_POLICY_INVALID")


def _validate_checksum_and_tamper_ref(artifact: dict[str, Any]) -> None:
    if (
        _IDENTITY.fullmatch(artifact["artifact_id"]) is None
        or _IDENTITY.fullmatch(artifact["tenant_id"]) is None
        or _CHECKSUM.fullmatch(artifact["checksum_sha256"]) is None
        or _TAMPER_REF.fullmatch(artifact["tamper_ref"]) is None
    ):
        raise SecretArtifactError("ARTIFACT_POLICY_INVALID")


def _public_artifact_record(artifact: dict[str, Any]) -> dict[str, str]:
    return {field: artifact[field] for field in sorted(_ARTIFACT_FIELDS)}


def admit_artifact(artifact: dict, expected_tenant_id: str, spy: SurfaceSpy) -> None:
    """Validate an artifact in deny order before the sole store effect."""

    checked = _validate_artifact_schema(artifact)
    if not isinstance(expected_tenant_id, str) or checked["tenant_id"] != expected_tenant_id:
        raise SecretArtifactError("ARTIFACT_TENANT_VIOLATION")
    _validate_source_ref(checked["source_ref"])
    _validate_artifact_policy(checked)
    _validate_checksum_and_tamper_ref(checked)
    public_record = _public_artifact_record(checked)
    validate_public_projection(public_record, (TEST_MARKER,))
    spy.store(public_record)


def _raw_occurrences(values: list[object], markers: tuple[str, ...]) -> int:
    variants = _marker_variants(markers)

    def count(value: object) -> int:
        if isinstance(value, str):
            return sum(value.count(variant) for variant in variants)
        if isinstance(value, list):
            return sum(count(item) for item in value)
        if isinstance(value, dict):
            return sum(count(key) + count(item) for key, item in value.items())
        return 0

    return sum(count(value) for value in values)


def _public_case(case_id: object, expected: object, actual: str, spy: SurfaceSpy) -> dict[str, object]:
    variants = _marker_variants((TEST_MARKER,))
    safe_case_id = (
        case_id
        if isinstance(case_id, str) and case_id and not _contains_unsafe_text(case_id, variants)
        else "invalid-case"
    )
    safe_expected = (
        expected
        if isinstance(expected, str) and not _contains_unsafe_text(expected, variants)
        else "ARTIFACT_POLICY_INVALID"
    )
    raw_occurrences = _raw_occurrences(spy.admitted_values, (TEST_MARKER,))
    return {
        "case_id": safe_case_id,
        "expected": safe_expected,
        "actual": actual,
        "status": "PASSED" if safe_expected == actual and raw_occurrences == 0 else "FAILED",
        "store_calls": spy.store_calls,
        "export_calls": spy.export_calls,
        "publish_calls": spy.publish_calls,
        "raw_occurrences": raw_occurrences,
    }


def _evaluate_surface_case(case: dict[str, Any]) -> tuple[str, SurfaceSpy]:
    spy = SurfaceSpy()
    expected = case.get("expected")
    try:
        if expected == "PASSED":
            projected = redact_surface(case["surface"], case["input"], (TEST_MARKER,))
            spy.store(projected)
            spy.export(projected)
            spy.publish(projected)
        elif expected == "SECRET_SURFACE_LEAK":
            try:
                validate_public_projection(case["input"], (TEST_MARKER,))
            except SecretArtifactError:
                return "SECRET_SURFACE_LEAK", spy
            return "PASSED", spy
        elif expected == "REDACTION_UNSUPPORTED":
            redact_surface(case["surface"], case["input"], (TEST_MARKER,))
        else:
            raise SecretArtifactError("ARTIFACT_POLICY_INVALID")
    except SecretArtifactError as error:
        return error.code, spy
    return "PASSED", spy


def _evaluate_artifact_case(
    case: dict[str, Any], seen_ids: tuple[set[str], set[str]]
) -> tuple[str, SurfaceSpy]:
    spy = SurfaceSpy()
    seen_case_ids, seen_artifact_ids = seen_ids
    case_id = case.get("id")
    if not isinstance(case_id, str) or not case_id or case_id in seen_case_ids:
        return "ARTIFACT_POLICY_INVALID", spy
    seen_case_ids.add(case_id)
    try:
        context = case["expected_context"]
        artifact = case["artifact"]
        if not isinstance(artifact, dict):
            return "ARTIFACT_POLICY_INVALID", spy
        artifact_id = artifact.get("artifact_id")
        if not isinstance(artifact_id, str) or artifact_id in seen_artifact_ids:
            return "ARTIFACT_POLICY_INVALID", spy
        seen_artifact_ids.add(artifact_id)
        admit_artifact(artifact, context["tenant_id"], spy)
    except (KeyError, TypeError):
        return "ARTIFACT_POLICY_INVALID", spy
    except SecretArtifactError as error:
        return error.code, spy
    return "PASSED", spy


def _effects_match(case: dict[str, Any], spy: SurfaceSpy) -> bool:
    effects = case.get("expected_effects")
    return effects == {
        "store_calls": spy.store_calls,
        "export_calls": spy.export_calls,
        "publish_calls": spy.publish_calls,
        "raw_occurrences": _raw_occurrences(spy.admitted_values, (TEST_MARKER,)),
    }


def run_cases(command_id: str, suite: dict) -> list[dict]:
    """Evaluate exactly one closed catalog and emit fixed safe case records."""

    if not isinstance(suite, dict):
        raise SecretArtifactError("ARTIFACT_POLICY_INVALID")
    if command_id == "secret-surface-negative":
        cases = suite.get("surface_cases")
        evaluator = lambda case, _seen: _evaluate_surface_case(case)
        seen_ids: object = (set(), set())
    elif command_id == "artifact-isolation-negative":
        cases = suite.get("artifact_cases")
        evaluator = _evaluate_artifact_case
        seen_ids = (set(), set())
    else:
        raise SecretArtifactError("ARTIFACT_POLICY_INVALID")
    if not isinstance(cases, list):
        raise SecretArtifactError("ARTIFACT_POLICY_INVALID")

    results: list[dict] = []
    for case in cases:
        if not isinstance(case, dict):
            raise SecretArtifactError("ARTIFACT_POLICY_INVALID")
        actual, spy = evaluator(case, seen_ids)
        result = _public_case(case.get("id"), case.get("expected"), actual, spy)
        if not _effects_match(case, spy):
            result["status"] = "FAILED"
        results.append(result)
    return results
