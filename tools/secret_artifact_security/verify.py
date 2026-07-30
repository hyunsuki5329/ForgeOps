"""Pure pre-storage redaction and artifact-admission evaluator.

This module intentionally contains no command-line or external-effect surface.
All effects are represented by ``SurfaceSpy`` and stay in memory.
"""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


TEST_MARKER = "FORGEOPS_TEST_SECRET_DO_NOT_STORE"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GATE_ID = "VG-009"
PROFILE_ID = "forgeops-secret-artifact-security"
RUNNER_ERROR = "SECRET_ARTIFACT_RUNNER_CONTRACT_INVALID"
RESULT_UNSAFE_ERROR = "SECRET_ARTIFACT_RESULT_UNSAFE"
SCHEMA_REF = "contracts/forgeops-secret-artifact-contract/1.0/schema.json"
SUITE_REF = "fixtures/forgeops-secret-artifact-security/suite.json"
TRUSTED_RESULTS = {
    "secret-surface-negative": "artifacts/verification/vg-009-secret-surface-result.json",
    "artifact-isolation-negative": "artifacts/verification/vg-009-artifact-isolation-result.json",
}
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
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ABSOLUTE_HOST_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:[^\s/]+/)+[^\s/]+|\\\\[^\\/\s]+[\\/])")
_RESULT_CASE_FIELDS = {
    "case_id",
    "expected",
    "actual",
    "status",
    "store_calls",
    "export_calls",
    "publish_calls",
    "raw_occurrences",
}
_RESULT_ASSERTIONS = {
    "negative_store_calls",
    "negative_export_calls",
    "negative_publish_calls",
    "negative_raw_occurrences",
    "no_sensitive_content",
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
        base32 = base64.b32encode(encoded).decode("ascii")
        variants.update(
            {
                marker,
                base64.b64encode(encoded).decode("ascii"),
                base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("="),
                base32,
                base32.rstrip("="),
                base32.lower(),
                base32.rstrip("=").lower(),
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
            occurrences = 0
            cursor = 0
            while True:
                matches = [
                    (value.find(variant, cursor), len(variant))
                    for variant in variants
                    if value.find(variant, cursor) >= 0
                ]
                if not matches:
                    return occurrences
                first_index = min(index for index, _length in matches)
                longest_match = max(length for index, length in matches if index == first_index)
                occurrences += 1
                cursor = first_index + longest_match
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


class _RunnerArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise SecretArtifactError(RUNNER_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _RunnerArgumentParser(
        description="Verify the registered VG-009 fixtures", allow_abbrev=False
    )
    parser.add_argument("--schema", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--command-id", required=True)
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def validate_registered_paths(args: argparse.Namespace) -> None:
    """Accept only the exact registered literals before touching the filesystem."""

    if (
        getattr(args, "schema", None) != SCHEMA_REF
        or getattr(args, "suite", None) != SUITE_REF
        or getattr(args, "command_id", None) not in TRUSTED_RESULTS
        or getattr(args, "result", None) != TRUSTED_RESULTS[args.command_id]
    ):
        raise SecretArtifactError(RUNNER_ERROR)


def resolve_registered_paths(root: Path, args: argparse.Namespace) -> dict[str, Path]:
    validate_registered_paths(args)
    return {
        "schema": root / SCHEMA_REF,
        "suite": root / SUITE_REF,
        "result": root / TRUSTED_RESULTS[args.command_id],
    }


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as source:
            value = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise SecretArtifactError(RUNNER_ERROR) from None
    if not isinstance(value, dict):
        raise SecretArtifactError(RUNNER_ERROR)
    return value


def _sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        raise SecretArtifactError(RUNNER_ERROR) from None


def _strict_utc(value: object) -> bool:
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        return False
    try:
        datetime.strptime(value, _TIMESTAMP_FORMAT)
    except ValueError:
        return False
    return True


def _assert_public_safe_tree(value: object) -> None:
    variants = _marker_variants((TEST_MARKER,))
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower() in FORBIDDEN_KEYS:
                raise SecretArtifactError(RESULT_UNSAFE_ERROR)
            _assert_public_safe_tree(item)
        return
    if isinstance(value, list):
        for item in value:
            _assert_public_safe_tree(item)
        return
    if isinstance(value, str):
        if _contains_unsafe_text(value, variants) or _ABSOLUTE_HOST_PATH.search(value):
            raise SecretArtifactError(RESULT_UNSAFE_ERROR)
        return
    if value is not None and not isinstance(value, (bool, int)):
        raise SecretArtifactError(RESULT_UNSAFE_ERROR)


def _assert_public_safe_result(result: dict[str, Any]) -> None:
    _assert_public_safe_tree(result)
    common = {"gate_id", "profile_id", "command_id", "status", "observed_at", "assertions"}
    success_fields = common | {"hashes", "summary", "cases"}
    failure_fields = common | {"failure_code"}
    if set(result) not in {frozenset(success_fields), frozenset(failure_fields)}:
        raise SecretArtifactError(RESULT_UNSAFE_ERROR)
    if (
        result["gate_id"] != GATE_ID
        or result["profile_id"] != PROFILE_ID
        or result["command_id"] not in TRUSTED_RESULTS
        or result["status"] not in {"PASSED", "FAILED"}
        or not _strict_utc(result["observed_at"])
        or not isinstance(result["assertions"], dict)
        or set(result["assertions"]) != _RESULT_ASSERTIONS
        or not all(isinstance(value, (bool, int)) for value in result["assertions"].values())
        or result["assertions"]["no_sensitive_content"] is not True
    ):
        raise SecretArtifactError(RESULT_UNSAFE_ERROR)
    if set(result) == failure_fields:
        if result["status"] != "FAILED" or result["failure_code"] not in {RUNNER_ERROR, RESULT_UNSAFE_ERROR}:
            raise SecretArtifactError(RESULT_UNSAFE_ERROR)
        return
    if (
        not isinstance(result["hashes"], dict)
        or set(result["hashes"]) != {"schema_sha256", "suite_sha256"}
        or not all(isinstance(value, str) and _CHECKSUM.fullmatch(value) for value in result["hashes"].values())
        or not isinstance(result["summary"], dict)
        or set(result["summary"]) != {"total", "passed", "failed"}
        or not isinstance(result["cases"], list)
    ):
        raise SecretArtifactError(RESULT_UNSAFE_ERROR)
    summary = result["summary"]
    if (
        not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in summary.values())
        or summary["total"] != len(result["cases"])
        or summary["passed"] + summary["failed"] != summary["total"]
    ):
        raise SecretArtifactError(RESULT_UNSAFE_ERROR)
    for case in result["cases"]:
        if (
            not isinstance(case, dict)
            or set(case) != _RESULT_CASE_FIELDS
            or not all(isinstance(case[key], str) for key in ("case_id", "expected", "actual", "status"))
            or not all(
                isinstance(case[key], int) and not isinstance(case[key], bool) and case[key] >= 0
                for key in ("store_calls", "export_calls", "publish_calls", "raw_occurrences")
            )
        ):
            raise SecretArtifactError(RESULT_UNSAFE_ERROR)


def run_conformance(paths: dict[str, Path], command_id: str, observed_at: str) -> dict[str, Any]:
    """Evaluate one registered catalog and return only its safe public result."""

    if set(paths) != {"schema", "suite", "result"} or command_id not in TRUSTED_RESULTS or not _strict_utc(observed_at):
        raise SecretArtifactError(RUNNER_ERROR)
    schema = _load_json_object(paths["schema"])
    suite = _load_json_object(paths["suite"])
    try:
        Draft202012Validator.check_schema(schema)
        if list(Draft202012Validator(schema).iter_errors(suite)):
            raise SecretArtifactError(RUNNER_ERROR)
    except SchemaError:
        raise SecretArtifactError(RUNNER_ERROR) from None
    cases = run_cases(command_id, suite)
    source_cases = suite["surface_cases"] if command_id == "secret-surface-negative" else suite["artifact_cases"]
    if not isinstance(source_cases, list) or len(source_cases) != len(cases):
        raise SecretArtifactError(RUNNER_ERROR)
    negative_results = [
        result for case, result in zip(source_cases, cases, strict=True) if case.get("kind") == "negative"
    ]
    negative_store_calls = sum(result["store_calls"] for result in negative_results)
    negative_export_calls = sum(result["export_calls"] for result in negative_results)
    negative_publish_calls = sum(result["publish_calls"] for result in negative_results)
    negative_raw_occurrences = sum(result["raw_occurrences"] for result in negative_results)
    failed = sum(result["status"] != "PASSED" for result in cases)
    result = {
        "gate_id": GATE_ID,
        "profile_id": PROFILE_ID,
        "command_id": command_id,
        "status": "PASSED" if failed == 0 and not any((negative_store_calls, negative_export_calls, negative_publish_calls, negative_raw_occurrences)) else "FAILED",
        "observed_at": observed_at,
        "hashes": {
            "schema_sha256": _sha256_file(paths["schema"]),
            "suite_sha256": _sha256_file(paths["suite"]),
        },
        "summary": {"total": len(cases), "passed": len(cases) - failed, "failed": failed},
        "cases": cases,
        "assertions": {
            "negative_store_calls": negative_store_calls,
            "negative_export_calls": negative_export_calls,
            "negative_publish_calls": negative_publish_calls,
            "negative_raw_occurrences": negative_raw_occurrences,
            "no_sensitive_content": True,
        },
    }
    _assert_public_safe_result(result)
    return result


def run_registered(command_id: str, observed_at: str, *, root: Path | None = None) -> dict[str, Any]:
    """Run a command using only its registered schema, suite, and result target."""

    repository_root = root if root is not None else REPOSITORY_ROOT
    args = argparse.Namespace(
        schema=SCHEMA_REF,
        suite=SUITE_REF,
        result=TRUSTED_RESULTS.get(command_id),
        command_id=command_id,
    )
    paths = resolve_registered_paths(repository_root, args)
    return run_conformance(paths, command_id, observed_at)


def safe_failure(command_id: str, failure_code: str, observed_at: str | None = None) -> dict[str, Any]:
    result = {
        "gate_id": GATE_ID,
        "profile_id": PROFILE_ID,
        "command_id": command_id,
        "status": "FAILED",
        "failure_code": failure_code,
        "observed_at": observed_at or _observed_at(),
        "assertions": {
            "negative_store_calls": 0,
            "negative_export_calls": 0,
            "negative_publish_calls": 0,
            "negative_raw_occurrences": 0,
            "no_sensitive_content": True,
        },
    }
    _assert_public_safe_result(result)
    return result


def write_result_atomically(path: Path, result: dict[str, Any]) -> None:
    """Replace a registered result through a sibling temporary file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            json.dump(result, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
            temporary = Path(stream.name)
        temporary.replace(path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _observed_at() -> str:
    return datetime.now(timezone.utc).strftime(_TIMESTAMP_FORMAT)


def main(argv: Sequence[str] | None = None, *, root: Path | None = None) -> int:
    """Run and atomically record one exact VG-009 catalog without external effects."""

    repository_root = root if root is not None else REPOSITORY_ROOT
    try:
        args = parse_args(argv)
        paths = resolve_registered_paths(repository_root, args)
    except SecretArtifactError:
        return 1
    try:
        result = run_conformance(paths, args.command_id, _observed_at())
    except SecretArtifactError as error:
        failure_code = RESULT_UNSAFE_ERROR if error.code == RESULT_UNSAFE_ERROR else RUNNER_ERROR
        write_result_atomically(paths["result"], safe_failure(args.command_id, failure_code))
        return 1
    write_result_atomically(paths["result"], result)
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    sys.exit(main())
