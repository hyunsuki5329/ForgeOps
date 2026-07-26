"""Pure evaluator for ForgeOps evidence and extension provenance records."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Sequence

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GATE_ID = "VG-023"
PROFILE_ID = "forgeops-evidence-contract"
RUNNER_ERROR = "EVIDENCE_RUNNER_CONTRACT_INVALID"
RESULT_UNSAFE_ERROR = "EVIDENCE_RESULT_UNSAFE"
SCHEMA_REF = "contracts/forgeops-evidence-contract/1.0/schema.json"
SUITE_REF = "fixtures/forgeops-evidence-contract/suite.json"
TRUSTED_RESULTS = {
    "evidence-positive-negative": "artifacts/verification/vg-023-evidence-contract-result.json",
    "extension-provenance": "artifacts/verification/vg-023-extension-provenance-result.json",
}


_EVIDENCE_FIELDS = {
    "id",
    "tier",
    "type",
    "source_ref",
    "observation",
    "evidence_refs",
    "observed_revision",
    "observed_at",
}
_PROVENANCE_FIELDS = {
    "provenance_id",
    "producer_kind",
    "task_id",
    "run_id",
    "source_ref",
    "source_sha256",
    "finding_refs",
}
_EVIDENCE_TYPES = {"file", "diff", "command", "test", "render", "runtime", "approval"}
_EVIDENCE_TIERS = {"E0", "E1", "E2", "E3"}
_PRODUCER_KINDS = {"plugin", "static_analyzer"}
_REVISION_TYPES = {"file", "diff"}
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_UTC_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_RESULT_KEYS = {
    "packet",
    "record",
    "finding",
    "exception",
    "traceback",
    "source_ref",
    "observation",
}
_SENSITIVE_RESULT_VALUE = re.compile(
    r"(?i)(?:\bbearer\s+|\bbasic\s+|(?:client_secret|access_token|api_key|token|secret|password|credential|signature)\s*[:=]|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{8,})"
)
_ABSOLUTE_HOST_PATH = re.compile(
    r"(?:[A-Za-z]:[\\/]|/(?:[^\s/]+/)+[^\s/]+|\\\\[^\\/\s]+[\\/])"
)
_TRUSTED_SOURCE_HASHES = {
    "plugins/example/finding.json": "637ba4f365de653abe58805066f69b5fc08aac8fc0f825fdff01fa040b9818cb",
    "tools/static/finding.sarif": "37e999c8d1d4d78882ddf935624477e30def1e26045822bfca7f71ca00acdf9f",
}


class EvidenceError(Exception):
    """A stable, public evaluator rejection category."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class EffectSpy:
    """Counts the evaluator's only in-memory effect boundaries."""

    def __init__(self) -> None:
        self.accept_calls = 0
        self.append_calls = 0

    def accept(self) -> None:
        self.accept_calls += 1

    def append(self) -> None:
        self.append_calls += 1


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and value != ""


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_closed_evidence_schema(record: object) -> dict:
    if not isinstance(record, dict):
        raise EvidenceError("EVIDENCE_SCHEMA_INVALID")
    required = {"id", "tier", "type", "source_ref", "observation", "evidence_refs"}
    if set(record) - _EVIDENCE_FIELDS or not required <= set(record):
        raise EvidenceError("EVIDENCE_SCHEMA_INVALID")
    if not all(_is_non_empty_string(record[field]) for field in ("id", "tier", "type", "source_ref", "observation")):
        raise EvidenceError("EVIDENCE_SCHEMA_INVALID")
    if not isinstance(record["evidence_refs"], list):
        raise EvidenceError("EVIDENCE_SCHEMA_INVALID")
    return record


def _validate_type_and_tier(record: dict) -> None:
    if record["type"] not in _EVIDENCE_TYPES:
        raise EvidenceError("EVIDENCE_TYPE_INVALID")
    if record["tier"] not in _EVIDENCE_TIERS:
        raise EvidenceError("EVIDENCE_TIER_INVALID")


def _validate_ids_and_refs(record: dict, catalog_ids: object) -> None:
    if not isinstance(catalog_ids, list) or not all(_is_non_empty_string(value) for value in catalog_ids):
        raise EvidenceError("EVIDENCE_REFERENCE_INVALID")
    if len(catalog_ids) != len(set(catalog_ids)) or record["id"] not in catalog_ids:
        raise EvidenceError("EVIDENCE_REFERENCE_INVALID")
    references = record["evidence_refs"]
    if (
        not all(_is_non_empty_string(value) for value in references)
        or len(references) != len(set(references))
        or any(value not in catalog_ids for value in references)
    ):
        raise EvidenceError("EVIDENCE_REFERENCE_INVALID")


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or _UTC_TIMESTAMP.fullmatch(value) is None:
        raise ValueError
    return datetime.strptime(value, _TIMESTAMP_FORMAT)


def _validate_freshness(record: dict, base_revision: object, validation_at: object) -> None:
    is_revision_evidence = record["type"] in _REVISION_TYPES
    has_revision = "observed_revision" in record
    has_timestamp = "observed_at" in record
    if has_revision != is_revision_evidence or has_timestamp == is_revision_evidence:
        raise EvidenceError("EVIDENCE_FRESHNESS_INVALID")

    if is_revision_evidence:
        if (
            not _is_integer(record["observed_revision"])
            or not _is_integer(base_revision)
            or record["observed_revision"] < 0
            or base_revision < 0
        ):
            raise EvidenceError("EVIDENCE_FRESHNESS_INVALID")
        if record["observed_revision"] != base_revision:
            raise EvidenceError("EVIDENCE_FRESHNESS_INVALID")
        return

    if not _is_integer(base_revision) or base_revision < 0:
        raise EvidenceError("EVIDENCE_FRESHNESS_INVALID")
    try:
        observed_at = _parse_utc(record["observed_at"])
        trusted_validation_at = _parse_utc(validation_at)
    except (TypeError, ValueError):
        raise EvidenceError("EVIDENCE_FRESHNESS_INVALID") from None
    age_seconds = (trusted_validation_at - observed_at).total_seconds()
    if not 0 <= age_seconds <= 300:
        raise EvidenceError("EVIDENCE_FRESHNESS_INVALID")


def validate_evidence(
    record: dict,
    *,
    base_revision: int,
    validation_at: str,
    catalog_ids: list[str],
    spy: EffectSpy,
) -> None:
    """Validate evidence before recording its in-memory acceptance effect."""

    checked_record = _validate_closed_evidence_schema(record)
    _validate_type_and_tier(checked_record)
    _validate_ids_and_refs(checked_record, catalog_ids)
    _validate_freshness(checked_record, base_revision, validation_at)
    spy.accept()


def _validate_closed_provenance_schema(record: object) -> dict:
    if not isinstance(record, dict) or set(record) != _PROVENANCE_FIELDS:
        raise EvidenceError("EVIDENCE_SCHEMA_INVALID")
    if not all(
        _is_non_empty_string(record[field])
        for field in ("provenance_id", "producer_kind", "task_id", "run_id", "source_ref", "source_sha256")
    ):
        raise EvidenceError("EVIDENCE_SCHEMA_INVALID")
    if not isinstance(record["finding_refs"], list):
        raise EvidenceError("EVIDENCE_SCHEMA_INVALID")
    return record


def _validate_producer_kind(record: dict) -> None:
    if record["producer_kind"] not in _PRODUCER_KINDS:
        raise EvidenceError("EVIDENCE_PROVENANCE_INVALID")


def _validate_context_identity(record: dict, expected_task_id: object, expected_run_id: object) -> None:
    if record["task_id"] != expected_task_id or record["run_id"] != expected_run_id:
        raise EvidenceError("EVIDENCE_PROVENANCE_INVALID")


def _validate_source_hash_and_findings(record: dict) -> None:
    finding_refs = record["finding_refs"]
    if (
        _SHA256.fullmatch(record["source_sha256"]) is None
        or _TRUSTED_SOURCE_HASHES.get(record["source_ref"]) != record["source_sha256"]
        or not all(_is_non_empty_string(value) for value in finding_refs)
        or len(finding_refs) != len(set(finding_refs))
    ):
        raise EvidenceError("EVIDENCE_PROVENANCE_INVALID")


def validate_extension_provenance(
    record: dict,
    *,
    expected_task_id: str,
    expected_run_id: str,
    spy: EffectSpy,
) -> None:
    """Validate metadata-only provenance before appending it in memory."""

    checked_record = _validate_closed_provenance_schema(record)
    _validate_producer_kind(checked_record)
    _validate_context_identity(checked_record, expected_task_id, expected_run_id)
    _validate_source_hash_and_findings(checked_record)
    spy.append()


def public_case(case_id: str, expected: str, actual: str, spy: EffectSpy) -> dict:
    """Return a public result that contains no raw packet or exception data."""

    return {
        "case_id": case_id,
        "expected": expected,
        "actual": actual,
        "status": "PASSED" if expected == actual else "FAILED",
        "accept_calls": spy.accept_calls,
        "append_calls": spy.append_calls,
    }


def _evaluate_evidence_case(case: dict, suite: dict) -> tuple[str, EffectSpy]:
    spy = EffectSpy()
    try:
        validate_evidence(
            case["record"],
            base_revision=suite["base_revision"],
            validation_at=suite["validation_at"],
            catalog_ids=case["catalog_ids"],
            spy=spy,
        )
    except EvidenceError as error:
        return error.code, spy
    return "PASSED", spy


def _evaluate_provenance_case(case: dict) -> tuple[str, EffectSpy]:
    spy = EffectSpy()
    try:
        context = case["expected_context"]
        validate_extension_provenance(
            case["record"],
            expected_task_id=context["task_id"],
            expected_run_id=context["run_id"],
            spy=spy,
        )
    except EvidenceError as error:
        return error.code, spy
    return "PASSED", spy


def run_cases(command_id: str, suite: dict) -> list[dict]:
    """Run exactly one registered fixture catalog without external effects."""

    if command_id == "evidence-positive-negative":
        cases = suite["evidence_cases"]
        evaluator = lambda case: _evaluate_evidence_case(case, suite)
    elif command_id == "extension-provenance":
        cases = suite["provenance_cases"]
        evaluator = _evaluate_provenance_case
    else:
        raise EvidenceError("EVIDENCE_SCHEMA_INVALID")

    results = []
    for case in cases:
        actual, spy = evaluator(case)
        result = public_case(case["id"], case["expected"], actual, spy)
        if (
            spy.accept_calls != case["expected_accept_calls"]
            or spy.append_calls != case["expected_append_calls"]
        ):
            result["status"] = "FAILED"
        results.append(result)
    return results


class _RunnerArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise EvidenceError(RUNNER_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _RunnerArgumentParser(
        description="Verify the registered VG-023 fixtures", allow_abbrev=False
    )
    parser.add_argument("--schema", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--command-id", required=True)
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def validate_registered_paths(args: argparse.Namespace) -> None:
    """Admit only the registered root-relative literals before file access."""

    if (
        getattr(args, "schema", None) != SCHEMA_REF
        or getattr(args, "suite", None) != SUITE_REF
        or getattr(args, "command_id", None) not in TRUSTED_RESULTS
        or getattr(args, "result", None) != TRUSTED_RESULTS[args.command_id]
    ):
        raise EvidenceError(RUNNER_ERROR)


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
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise EvidenceError(RUNNER_ERROR) from error
    if not isinstance(value, dict):
        raise EvidenceError(RUNNER_ERROR)
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strict_utc(value: object) -> bool:
    try:
        return isinstance(value, str) and _parse_utc(value).tzinfo is None
    except (TypeError, ValueError):
        return False


def _assert_public_safe_tree(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower() in _FORBIDDEN_RESULT_KEYS:
                raise EvidenceError(RESULT_UNSAFE_ERROR)
            _assert_public_safe_tree(item)
    elif isinstance(value, list):
        for item in value:
            _assert_public_safe_tree(item)
    elif isinstance(value, str):
        if _SENSITIVE_RESULT_VALUE.search(value) or _ABSOLUTE_HOST_PATH.search(value):
            raise EvidenceError(RESULT_UNSAFE_ERROR)
    elif value is not None and not isinstance(value, (bool, int)):
        raise EvidenceError(RESULT_UNSAFE_ERROR)


def _assert_public_safe_result(result: dict[str, Any]) -> None:
    _assert_public_safe_tree(result)
    common = {
        "gate_id",
        "profile_id",
        "command_id",
        "status",
        "observed_at",
        "assertions",
    }
    success_fields = common | {"hashes", "summary", "cases"}
    failure_fields = common | {"failure_code"}
    if set(result) not in {frozenset(success_fields), frozenset(failure_fields)}:
        raise EvidenceError(RESULT_UNSAFE_ERROR)
    if (
        result["gate_id"] != GATE_ID
        or result["profile_id"] != PROFILE_ID
        or result["command_id"] not in TRUSTED_RESULTS
        or result["status"] not in {"PASSED", "FAILED"}
        or not _strict_utc(result["observed_at"])
        or result["assertions"]
        != {
            "negative_accept_calls": 0,
            "negative_append_calls": 0,
            "no_sensitive_content": True,
        }
    ):
        raise EvidenceError(RESULT_UNSAFE_ERROR)
    if set(result) == failure_fields:
        if result["status"] != "FAILED" or result["failure_code"] not in {
            RUNNER_ERROR,
            RESULT_UNSAFE_ERROR,
        }:
            raise EvidenceError(RESULT_UNSAFE_ERROR)
        return
    if (
        not isinstance(result["hashes"], dict)
        or set(result["hashes"]) != {"schema_sha256", "suite_sha256"}
        or not all(isinstance(value, str) and _SHA256.fullmatch(value) for value in result["hashes"].values())
        or not isinstance(result["summary"], dict)
        or set(result["summary"]) != {"total", "passed", "failed"}
        or not isinstance(result["cases"], list)
    ):
        raise EvidenceError(RESULT_UNSAFE_ERROR)
    summary = result["summary"]
    if (
        not all(_is_integer(summary[key]) and summary[key] >= 0 for key in summary)
        or summary["total"] != len(result["cases"])
        or summary["passed"] + summary["failed"] != summary["total"]
    ):
        raise EvidenceError(RESULT_UNSAFE_ERROR)
    for case in result["cases"]:
        if (
            not isinstance(case, dict)
            or set(case) != {"case_id", "expected", "actual", "status", "accept_calls", "append_calls"}
            or not all(isinstance(case[key], str) for key in ("case_id", "expected", "actual", "status"))
            or not all(_is_integer(case[key]) and case[key] >= 0 for key in ("accept_calls", "append_calls"))
        ):
            raise EvidenceError(RESULT_UNSAFE_ERROR)


def run_conformance(paths: dict[str, Path], command_id: str, observed_at: str) -> dict[str, Any]:
    if set(paths) != {"schema", "suite", "result"} or command_id not in TRUSTED_RESULTS or not _strict_utc(observed_at):
        raise EvidenceError(RUNNER_ERROR)
    schema = _load_json_object(paths["schema"])
    suite = _load_json_object(paths["suite"])
    try:
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(suite))
    except SchemaError as error:
        raise EvidenceError(RUNNER_ERROR) from error
    if errors:
        raise EvidenceError(RUNNER_ERROR)
    cases = run_cases(command_id, suite)
    negative_cases = [
        case for case, result in zip(
            suite["evidence_cases"] if command_id == "evidence-positive-negative" else suite["provenance_cases"],
            cases,
            strict=True,
        )
        if case["kind"] == "negative"
    ]
    negative_results = [
        result for case, result in zip(
            suite["evidence_cases"] if command_id == "evidence-positive-negative" else suite["provenance_cases"],
            cases,
            strict=True,
        )
        if case["kind"] == "negative"
    ]
    negative_accept_calls = sum(result["accept_calls"] for result in negative_results)
    negative_append_calls = sum(result["append_calls"] for result in negative_results)
    failed = sum(result["status"] != "PASSED" for result in cases)
    if len(negative_cases) != len(negative_results):
        raise EvidenceError(RUNNER_ERROR)
    result = {
        "gate_id": GATE_ID,
        "profile_id": PROFILE_ID,
        "command_id": command_id,
        "status": "PASSED" if failed == 0 and negative_accept_calls == 0 and negative_append_calls == 0 else "FAILED",
        "observed_at": observed_at,
        "hashes": {
            "schema_sha256": _sha256_file(paths["schema"]),
            "suite_sha256": _sha256_file(paths["suite"]),
        },
        "summary": {"total": len(cases), "passed": len(cases) - failed, "failed": failed},
        "cases": cases,
        "assertions": {
            "negative_accept_calls": negative_accept_calls,
            "negative_append_calls": negative_append_calls,
            "no_sensitive_content": True,
        },
    }
    _assert_public_safe_result(result)
    return result


def safe_failure(command_id: str, failure_code: str, observed_at: str | None = None) -> dict[str, Any]:
    result = {
        "gate_id": GATE_ID,
        "profile_id": PROFILE_ID,
        "command_id": command_id,
        "status": "FAILED",
        "failure_code": failure_code,
        "observed_at": observed_at or _observed_at(),
        "assertions": {
            "negative_accept_calls": 0,
            "negative_append_calls": 0,
            "no_sensitive_content": True,
        },
    }
    _assert_public_safe_result(result)
    return result


def write_result_atomically(path: Path, result: dict[str, Any]) -> None:
    """Replace a result via a sibling file without exposing partial JSON."""

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
    """Run one exact VG-023 catalog and write only its registered result."""

    repository_root = root if root is not None else REPOSITORY_ROOT
    try:
        args = parse_args(argv)
        validate_registered_paths(args)
        paths = resolve_registered_paths(repository_root, args)
    except (EvidenceError, OSError, UnicodeError, TypeError, ValueError, KeyError, IndexError):
        return 1

    command_id = args.command_id
    observed_at = _observed_at()
    result_path = paths["result"]
    try:
        result = run_conformance(paths, command_id, observed_at)
        exit_code = 0 if result["status"] == "PASSED" else 1
    except EvidenceError as error:
        result = safe_failure(command_id, error.code if error.code in {RUNNER_ERROR, RESULT_UNSAFE_ERROR} else RUNNER_ERROR, observed_at)
        exit_code = 1
    except (OSError, UnicodeError, TypeError, ValueError, KeyError, IndexError):
        result = safe_failure(command_id, RUNNER_ERROR, observed_at)
        exit_code = 1
    write_result_atomically(result_path, result)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
