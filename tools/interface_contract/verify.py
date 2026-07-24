"""Deterministic, exact-path VG-004 interface-contract verification runner."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from tools.interface_contract.common import ContractError, is_strict_utc, sha256_file
from tools.interface_contract.event_contract import (
    AppendSpy,
    validate_event_record,
    validate_event_stream,
)
from tools.interface_contract.manifest_contract import (
    StorageSpy,
    calculate_manifest_sha256,
    validate_manifest_case,
)
from tools.interface_contract.openapi_contract import (
    run_api_boundary_suite,
    run_version_envelope_suite,
    validate_openapi_document,
)


COMMAND_ID = "interface-contract-fixture"
GATE_ID = "VG-004"
PROFILE_ID = "forgeops-interface-contract"
RUNNER_ERROR = "INTERFACE_RUNNER_CONTRACT_INVALID"
CROSS_REFERENCE_ERROR = "INTERFACE_CROSS_REFERENCE_INVALID"
RESULT_UNSAFE_ERROR = "INTERFACE_RESULT_UNSAFE"

TRUSTED = {
    "openapi": "contracts/forgeops-api/1.0/openapi.yaml",
    "event_schema": "contracts/forgeops-event/1.0/schema.json",
    "manifest_schema": "contracts/forgeops-run-manifest/1.0/schema.json",
    "api_version_suite": "fixtures/forgeops-api/version-envelope-suite.json",
    "api_boundary_suite": "fixtures/forgeops-api/data-control-suite.json",
    "event_suite": "fixtures/forgeops-event-contract/suite.json",
    "manifest_suite": "fixtures/forgeops-run-manifest/suite.json",
    "result": "artifacts/verification/vg-004-interface-contract-result.json",
}
SUITE_NAMES = (
    "api_version_suite",
    "api_boundary_suite",
    "event_suite",
    "manifest_suite",
)
PRODUCT_SCHEMA_LITERAL = "contracts/product-task-contract/1.0/schema.json"

API_VERSION_CASES = (
    "valid-create-task",
    "valid-get-task",
    "valid-get-run",
    "valid-list-run-events",
    "valid-get-run-manifest",
    "unsupported-uri-major",
    "unsupported-body-version",
    "missing-request-header",
    "invalid-request-id-type",
    "request-id-header-body-mismatch",
    "response-request-id-mismatch",
    "endpoint-unknown-field",
    "endpoint-missing-required-field",
    "endpoint-wrong-field-type",
    "path-body-identity-mismatch",
    "response-data-error-conflict",
)
API_BOUNDARY_CASES = (
    "create-task-valid",
    "get-task-valid",
    "get-run-valid",
    "list-run-events-valid",
    "get-run-manifest-valid",
    "unsupported-body-version",
    "missing-request-header",
    "product-contract-unknown-field",
    "product-contract-missing-field",
    "product-contract-wrong-type",
    "control-authority",
    "control-capabilities",
    "control-runtime-policy",
    "control-accepted-state",
    "control-approval-token",
    "control-nonce",
    "control-credentials",
    "control-tools",
    "control-commands",
    "copied-product-budget",
    "copied-product-approval-policy",
    "task-identity-mismatch",
    "run-identity-mismatch",
    "dangling-event-reference",
    "dangling-manifest-reference",
    "response-data-error-conflict",
    "raw-credential-response",
    "raw-private-response",
)
EVENT_POSITIVE_CASES = (
    "first-append",
    "consecutive-append",
    "revision-increase",
    "main-normalized-part-actor",
    "main-normalized-work-actor",
    "main-actor",
)
EVENT_NEGATIVE_RECORD_CASES = (
    "wrapper-canonical-task-mismatch",
    "non-main-source",
    "missing-source-hash",
    "bad-source-hash",
    "duplicate-evidence-ref",
    "empty-evidence-ref",
    "forbidden-raw-field",
    "invalid-timestamp",
)
EVENT_NEGATIVE_RECORD_ERRORS = dict(
    zip(
        EVENT_NEGATIVE_RECORD_CASES,
        (
            "EVENT_IDENTITY_MISMATCH",
            "EVENT_OWNER_INVALID",
            "EVENT_SCHEMA_INVALID",
            "EVENT_SCHEMA_INVALID",
            "EVENT_REFERENCE_INVALID",
            "EVENT_REFERENCE_INVALID",
            "EVENT_SCHEMA_INVALID",
            "EVENT_TIMESTAMP_INVALID",
        ),
        strict=True,
    )
)
EVENT_NEGATIVE_STREAM_CASES = (
    "stream-seq-reuse",
    "stream-seq-skip",
    "stream-seq-decrease",
    "cross-run-stream-mix",
    "task-mix",
    "correlation-mix",
    "canonical-seq-reuse",
    "canonical-seq-decrease",
    "stale-revision",
    "revision-decrease",
    "duplicate-state-accepted",
    "work-owned-state-accepted",
)
EVENT_NEGATIVE_STREAM_ERRORS = dict(
    zip(
        EVENT_NEGATIVE_STREAM_CASES,
        (
            "EVENT_STREAM_OUT_OF_ORDER",
            "EVENT_STREAM_OUT_OF_ORDER",
            "EVENT_STREAM_OUT_OF_ORDER",
            "EVENT_STREAM_OUT_OF_ORDER",
            "EVENT_IDENTITY_MISMATCH",
            "EVENT_IDENTITY_MISMATCH",
            "EVENT_CANONICAL_SEQUENCE_INVALID",
            "EVENT_CANONICAL_SEQUENCE_INVALID",
            "EVENT_REVISION_MISMATCH",
            "EVENT_REVISION_MISMATCH",
            "EVENT_REVISION_MISMATCH",
            "EVENT_OWNER_INVALID",
        ),
        strict=True,
    )
)
MANIFEST_POSITIVE_CASES = (
    "primary-terminal",
    "non-terminal-snapshot",
    "audit-replay",
    "counterfactual",
    "revision-evidence",
    "time-evidence",
    "blocked-terminal",
)
MANIFEST_POSITIVE_KINDS = dict(
    zip(
        MANIFEST_POSITIVE_CASES,
        (
            "primary_terminal",
            "non_terminal_snapshot",
            "audit_replay",
            "counterfactual",
            "revision_evidence",
            "time_evidence",
            "blocked_terminal",
        ),
        strict=True,
    )
)
MANIFEST_NEGATIVE_LIFECYCLE_CASES = (
    "event-count-mismatch",
    "terminal-missing-finalized",
    "terminal-missing-decision",
    "non-terminal-has-finalized",
    "non-terminal-has-terminal-decision",
    "finalized-before-created",
    "bad-self-hash",
    "missing-self-hash",
    "missing-content-hash",
    "bad-content-hash",
    "unknown-root-field",
)
MANIFEST_NEGATIVE_LIFECYCLE_ERRORS = dict(
    zip(
        MANIFEST_NEGATIVE_LIFECYCLE_CASES,
        (
            "MANIFEST_EVENT_RANGE_INVALID",
            "MANIFEST_IDENTITY_MISMATCH",
            "MANIFEST_IDENTITY_MISMATCH",
            "MANIFEST_IDENTITY_MISMATCH",
            "MANIFEST_IDENTITY_MISMATCH",
            "MANIFEST_IDENTITY_MISMATCH",
            "MANIFEST_HASH_INVALID",
            "MANIFEST_SCHEMA_INVALID",
            "MANIFEST_SCHEMA_INVALID",
            "MANIFEST_SCHEMA_INVALID",
            "MANIFEST_SCHEMA_INVALID",
        ),
        strict=True,
    )
)
MANIFEST_NEGATIVE_REFERENCE_CASES = (
    "duplicate-evidence-id",
    "dangling-reference",
    "producer-outside-range",
    "file-evidence-with-time",
    "time-evidence-with-revision",
    "invalid-strict-utc",
    "raw-secret-field",
    "absolute-source-ref",
    "traversal-source-ref",
    "signed-url-source-ref",
    "cross-run-reference",
    "invalid-run-mode",
    "sensitive-urn-token",
    "sensitive-urn-credential",
    "sensitive-urn-tenant",
    "sensitive-urn-secret",
)
MANIFEST_NEGATIVE_REFERENCE_KINDS = dict(
    zip(
        MANIFEST_NEGATIVE_REFERENCE_CASES,
        (
            "duplicate_identity",
            "dangling_reference",
            "producer_sequence",
            "freshness_union",
            "freshness_union",
            "freshness_timestamp",
            "sensitive_boundary",
            "source_reference",
            "source_reference",
            "source_reference",
            "reference_resolution",
            "run_mode",
            "source_reference",
            "source_reference",
            "source_reference",
            "source_reference",
        ),
        strict=True,
    )
)
MANIFEST_NEGATIVE_REFERENCE_ERRORS = dict(
    zip(
        MANIFEST_NEGATIVE_REFERENCE_CASES,
        (
            "MANIFEST_ID_DUPLICATE",
            "MANIFEST_REFERENCE_DANGLING",
            "MANIFEST_PRODUCER_SEQUENCE_INVALID",
            "MANIFEST_EVIDENCE_FRESHNESS_INVALID",
            "MANIFEST_EVIDENCE_FRESHNESS_INVALID",
            "MANIFEST_EVIDENCE_FRESHNESS_INVALID",
            "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
            "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
            "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
            "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
            "MANIFEST_REFERENCE_CROSS_RUN",
            "MANIFEST_MODE_INVALID",
            "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
            "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
            "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
            "MANIFEST_SENSITIVE_CONTENT_FORBIDDEN",
        ),
        strict=True,
    )
)


class _RunnerArgumentParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise ContractError(RUNNER_ERROR)


def _raise_runner_error() -> None:
    raise ContractError(RUNNER_ERROR)


def build_parser() -> argparse.ArgumentParser:
    parser = _RunnerArgumentParser(
        description="Verify the registered VG-004 fixtures", allow_abbrev=False
    )
    for name in TRUSTED:
        parser.add_argument(f"--{name.replace('_', '-')}", required=True)
    parser.add_argument("--command-id", required=True)
    return parser


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)


def validate_registered_paths(args: argparse.Namespace) -> None:
    """Admit only the registered root-relative literals and command identity."""
    if getattr(args, "command_id", None) != COMMAND_ID:
        _raise_runner_error()
    for name, literal in TRUSTED.items():
        if getattr(args, name, None) != literal:
            _raise_runner_error()


def resolve_registered_paths(
    root: Path, args: argparse.Namespace
) -> dict[str, Path]:
    validate_registered_paths(args)
    return {name: root / literal for name, literal in TRUSTED.items()}


def _require_exact_object(value: object, fields: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        _raise_runner_error()
    return value


def _require_ordered_cases(
    suite: dict[str, Any], category: str, expected_ids: tuple[str, ...]
) -> list[dict[str, Any]]:
    cases = suite.get(category)
    if not isinstance(cases, list) or [case.get("id") for case in cases if isinstance(case, dict)] != list(expected_ids):
        _raise_runner_error()
    if len(cases) != len(expected_ids) or len(set(expected_ids)) != len(expected_ids):
        _raise_runner_error()
    return cases


def _validate_api_version_catalog(suite: dict[str, Any]) -> None:
    _require_exact_object(suite, {"suite_id", "suite_version", "cases"})
    if suite["suite_id"] != "forgeops-api-version-envelope" or suite["suite_version"] != "1.0":
        _raise_runner_error()
    fields = {"id", "kind", "uri_major", "request_header", "body", "response", "expected"}
    for case in _require_ordered_cases(suite, "cases", API_VERSION_CASES):
        _require_exact_object(case, fields)


def _api_boundary_fields(case_id: str) -> set[str]:
    if case_id in API_BOUNDARY_CASES[:2]:
        return {"id", "kind", "uri_major", "request_header", "body", "response", "expected"}
    if case_id in API_BOUNDARY_CASES[2:5]:
        return {"id", "kind", "uri_major", "request_header", "body", "response", "reference_context", "expected"}
    fields = {"id", "base_id", "mutation", "expected", "expected_spy_calls"}
    if case_id.startswith("control-") or case_id.startswith("copied-product-") or case_id.startswith("raw-"):
        fields.add("parameter")
    return fields


def _validate_api_boundary_catalog(suite: dict[str, Any]) -> None:
    _require_exact_object(suite, {"suite_id", "suite_version", "cases"})
    if suite["suite_id"] != "forgeops-api-data-control" or suite["suite_version"] != "1.0":
        _raise_runner_error()
    for case in _require_ordered_cases(suite, "cases", API_BOUNDARY_CASES):
        _require_exact_object(case, _api_boundary_fields(case["id"]))


def _validate_event_catalog(suite: dict[str, Any]) -> None:
    _require_exact_object(
        suite,
        {"suite_id", "schema_version", "positive", "negative_records", "negative_streams"},
    )
    if suite["suite_id"] != "forgeops-event-contract-1.0" or suite["schema_version"] != "1.0":
        _raise_runner_error()
    positive = _require_ordered_cases(suite, "positive", EVENT_POSITIVE_CASES)
    for case in positive:
        fields = {"id", "source_revisions", "records"}
        if case["id"] == "first-append":
            fields.add("source_main_decisions")
        _require_exact_object(case, fields)
    for case in _require_ordered_cases(
        suite, "negative_records", EVENT_NEGATIVE_RECORD_CASES
    ):
        _require_exact_object(case, {"id", "base_case", "expected_error", "mutation"})
        if case["expected_error"] != EVENT_NEGATIVE_RECORD_ERRORS[case["id"]]:
            _raise_runner_error()
    for case in _require_ordered_cases(
        suite, "negative_streams", EVENT_NEGATIVE_STREAM_CASES
    ):
        fields = {"id", "base_case", "expected_error", "expected_append_calls", "mutations"}
        if case["id"] in {"revision-decrease", "duplicate-state-accepted"}:
            fields.add("source_revision_overrides")
        _require_exact_object(case, fields)
        if (
            case["expected_error"] != EVENT_NEGATIVE_STREAM_ERRORS[case["id"]]
            or case["expected_append_calls"] != 0
        ):
            _raise_runner_error()


def _validate_manifest_catalog(suite: dict[str, Any]) -> None:
    _require_exact_object(
        suite,
        {"suite_id", "schema_version", "positive", "negative_lifecycle", "negative_reference"},
    )
    if suite["suite_id"] != "forgeops-run-manifest-1.0" or suite["schema_version"] != "1.0":
        _raise_runner_error()
    case_fields = {"id", "kind", "manifest", "resolution_context", "expected", "expected_storage_calls"}
    for case in _require_ordered_cases(suite, "positive", MANIFEST_POSITIVE_CASES):
        _require_exact_object(case, case_fields)
        if (
            case["kind"] != MANIFEST_POSITIVE_KINDS[case["id"]]
            or case["expected"] != "PASSED"
            or case["expected_storage_calls"] != 0
        ):
            _raise_runner_error()
    for case in _require_ordered_cases(
        suite, "negative_lifecycle", MANIFEST_NEGATIVE_LIFECYCLE_CASES
    ):
        _require_exact_object(case, {"id", "base_case", "mutations", "rehash", "expected_error"})
        if case["expected_error"] != MANIFEST_NEGATIVE_LIFECYCLE_ERRORS[case["id"]]:
            _raise_runner_error()
    for case in _require_ordered_cases(
        suite, "negative_reference", MANIFEST_NEGATIVE_REFERENCE_CASES
    ):
        _require_exact_object(case, case_fields)
        if (
            case["kind"] != MANIFEST_NEGATIVE_REFERENCE_KINDS[case["id"]]
            or case["expected"] != MANIFEST_NEGATIVE_REFERENCE_ERRORS[case["id"]]
            or case["expected_storage_calls"] != 0
        ):
            _raise_runner_error()


def validate_suite_catalog(name: str, suite: dict[str, Any]) -> None:
    """Validate one exact, ordered, closed suite catalog before evaluation."""
    validators = {
        "api_version_suite": _validate_api_version_catalog,
        "api_boundary_suite": _validate_api_boundary_catalog,
        "event_suite": _validate_event_catalog,
        "manifest_suite": _validate_manifest_catalog,
    }
    validator = validators.get(name)
    if validator is None:
        _raise_runner_error()
    validator(suite)


def _load_object(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError(RUNNER_ERROR) from exc
    if not isinstance(value, dict):
        _raise_runner_error()
    return value


def _apply_mutations(value: dict[str, Any], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    for mutation in mutations:
        if not isinstance(mutation, dict):
            _raise_runner_error()
        target: Any = result
        path = mutation.get("path")
        if not isinstance(path, list) or not path:
            _raise_runner_error()
        try:
            for segment in path[:-1]:
                target = target[segment]
            leaf = path[-1]
            operation = mutation.get("operation", "replace")
            if operation == "remove":
                target.pop(leaf)
            elif operation == "replace" and "value" in mutation:
                target[leaf] = copy.deepcopy(mutation["value"])
            else:
                _raise_runner_error()
        except (KeyError, IndexError, TypeError) as exc:
            raise ContractError(RUNNER_ERROR) from exc
    return result


def _case_record(case_id: str, kind: str, expected: str, actual: str) -> dict[str, str]:
    return {
        "case_id": case_id,
        "kind": kind,
        "expected": expected,
        "actual": actual,
        "status": "PASSED" if expected == actual else "FAILED",
    }


def _project_api_records(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        _case_record(record["id"], record["kind"], record["expected"], record["actual"])
        for record in records
    ]


def _run_event_suite(
    schema: dict[str, Any], suite: dict[str, Any]
) -> tuple[list[dict[str, str]], int]:
    positives = {case["id"]: case for case in suite["positive"]}
    records: list[dict[str, str]] = []
    negative_effect_calls = 0

    for case in suite["positive"]:
        spy = AppendSpy()
        try:
            actual = validate_event_stream(
                copy.deepcopy(case["records"]),
                schema,
                copy.deepcopy(case["source_revisions"]),
                spy,
                copy.deepcopy(case.get("source_main_decisions")),
            )
        except ContractError as error:
            actual = error.code
        if actual == "PASSED" and spy.calls != len(case["records"]):
            actual = RUNNER_ERROR
        records.append(_case_record(case["id"], "stream", "PASSED", actual))

    for case in suite["negative_records"]:
        base = positives[case["base_case"]]["records"][0]
        record = _apply_mutations(base, [case["mutation"]])
        try:
            validate_event_record(record, schema)
            actual = "PASSED"
        except ContractError as error:
            actual = error.code
        records.append(
            _case_record(case["id"], "record", case["expected_error"], actual)
        )

    for case in suite["negative_streams"]:
        base = positives[case["base_case"]]
        materialized = copy.deepcopy(base["records"])
        source_revisions = copy.deepcopy(base["source_revisions"])
        source_revisions.update(case.get("source_revision_overrides", {}))
        for mutation in case["mutations"]:
            index = mutation.get("record_index")
            if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(materialized):
                _raise_runner_error()
            materialized[index] = _apply_mutations(materialized[index], [mutation])
        spy = AppendSpy()
        try:
            validate_event_stream(
                materialized,
                schema,
                source_revisions,
                spy,
                copy.deepcopy(base.get("source_main_decisions")),
            )
            actual = "PASSED"
        except ContractError as error:
            actual = error.code
        expected_calls = case["expected_append_calls"]
        negative_effect_calls += spy.calls
        if spy.calls != expected_calls:
            actual = RUNNER_ERROR
        records.append(
            _case_record(case["id"], "stream", case["expected_error"], actual)
        )
    return records, negative_effect_calls


def _run_manifest_suite(
    schema: dict[str, Any], suite: dict[str, Any]
) -> tuple[list[dict[str, str]], int]:
    positives = {case["id"]: case for case in suite["positive"]}
    records: list[dict[str, str]] = []
    effect_calls = 0

    cases: list[dict[str, Any]] = [copy.deepcopy(case) for case in suite["positive"]]
    for negative in suite["negative_lifecycle"]:
        base = positives[negative["base_case"]]
        manifest = _apply_mutations(base["manifest"], negative["mutations"])
        if negative["rehash"]:
            manifest["manifest_sha256"] = calculate_manifest_sha256(manifest)
        cases.append(
            {
                "id": negative["id"],
                "kind": "lifecycle_or_hash",
                "manifest": manifest,
                "resolution_context": copy.deepcopy(base["resolution_context"]),
                "expected": negative["expected_error"],
                "expected_storage_calls": 0,
            }
        )
    cases.extend(copy.deepcopy(suite["negative_reference"]))

    for case in cases:
        spy = StorageSpy()
        try:
            actual = validate_manifest_case(case, schema, spy)
        except ContractError as error:
            actual = error.code
        effect_calls += spy.calls
        if spy.calls != case["expected_storage_calls"]:
            actual = RUNNER_ERROR
        records.append(
            _case_record(case["id"], case["kind"], case["expected"], actual)
        )
    return records, effect_calls


def _component(records: list[dict[str, str]]) -> dict[str, Any]:
    passed = sum(record["status"] == "PASSED" for record in records)
    return {
        "total": len(records),
        "passed": passed,
        "failed": len(records) - passed,
        "cases": records,
    }


def _strict_schema(schema: dict[str, Any]) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except (SchemaError, TypeError, ValueError) as exc:
        raise ContractError(RUNNER_ERROR) from exc


def _raise_cross_reference_error() -> None:
    raise ContractError(CROSS_REFERENCE_ERROR)


def validate_cross_contract(
    api_case: dict[str, Any],
    event_records: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    """Validate one literal API/event/manifest bundle without resolving externally."""
    api_fields = {
        "task_id",
        "run_id",
        "correlation_id",
        "run_mode",
        "status",
        "accepted_revision",
        "event_stream_ref",
        "manifest_ref",
        "reference_context",
    }
    if (
        not isinstance(api_case, dict)
        or set(api_case) != api_fields
        or not isinstance(event_records, list)
        or not event_records
        or not isinstance(manifest, dict)
    ):
        _raise_cross_reference_error()

    try:
        identity = (
            manifest["task_id"],
            manifest["run_id"],
            manifest["correlation_id"],
        )
        if (
            (api_case["task_id"], api_case["run_id"], api_case["correlation_id"])
            != identity
        ):
            _raise_cross_reference_error()
        for event in event_records:
            if not isinstance(event, dict):
                _raise_cross_reference_error()
            canonical = event["canonical_event"]
            if (
                (event["task_id"], event["run_id"], event["correlation_id"])
                != identity
                or canonical["task_id"] != identity[0]
                or canonical["correlation_id"] != identity[2]
            ):
                _raise_cross_reference_error()

        stream = manifest["event_stream"]
        stream_sequences = [event["stream_seq"] for event in event_records]
        stream_ids = {event["stream_id"] for event in event_records}
        if (
            stream_ids != {stream["stream_id"]}
            or stream_sequences
            != list(range(stream["first_seq"], stream["last_seq"] + 1))
            or stream["count"] != len(event_records)
        ):
            _raise_cross_reference_error()

        expected_event_ref = f"forgeops:event-stream:{stream['stream_id']}"
        expected_manifest_ref = f"forgeops:manifest:{manifest['manifest_id']}"
        if (
            api_case["event_stream_ref"] != expected_event_ref
            or api_case["manifest_ref"] != expected_manifest_ref
        ):
            _raise_cross_reference_error()
        context = api_case["reference_context"]
        expected_context = {
            expected_event_ref: {
                "kind": "event_stream",
                "task_id": identity[0],
                "run_id": identity[1],
            },
            expected_manifest_ref: {
                "kind": "manifest",
                "task_id": identity[0],
                "run_id": identity[1],
            },
        }
        if context != expected_context:
            _raise_cross_reference_error()

        if (
            api_case["run_mode"] != manifest["run_mode"]
            or api_case["status"] != manifest["status"]
            or api_case["accepted_revision"] != manifest["accepted_revision"]
        ):
            _raise_cross_reference_error()

        evidence_ids = [item["evidence_id"] for item in manifest["evidence"]]
        if len(evidence_ids) != len(set(evidence_ids)):
            _raise_cross_reference_error()
        for event in event_records:
            for reference in event["canonical_event"]["evidence_refs"]:
                if evidence_ids.count(reference) != 1:
                    _raise_cross_reference_error()

        first_seq = stream["first_seq"]
        last_seq = stream["last_seq"]
        for record in (
            *manifest["artifacts"],
            *manifest["evidence"],
            *manifest["decision_refs"],
        ):
            producer_seq = record["producer_event_seq"]
            if (
                isinstance(producer_seq, bool)
                or not isinstance(producer_seq, int)
                or not first_seq <= producer_seq <= last_seq
            ):
                _raise_cross_reference_error()

        if manifest["status"] in {"BLOCKED", "SUCCEEDED", "FAILED"}:
            final_event = event_records[-1]
            canonical = final_event["canonical_event"]
            if (
                canonical["actor"] != "main"
                or canonical["code"] != "STATE_ACCEPTED"
                or canonical["action"] != manifest["status"]
                or final_event["accepted_revision"] != manifest["accepted_revision"]
            ):
                _raise_cross_reference_error()
    except (KeyError, IndexError, TypeError, ValueError):
        _raise_cross_reference_error()


FORBIDDEN_RESULT_KEYS = frozenset(
    {
        "request",
        "response",
        "body",
        "headers",
        "raw_event",
        "raw_manifest",
        "payload",
        "credential",
        "token",
        "secret",
        "private",
        "exception",
    }
)
RESULT_HASH_FIELDS = frozenset(
    f"{name}_sha256"
    for name in (
        "openapi",
        "event_schema",
        "manifest_schema",
        *SUITE_NAMES,
    )
)
RESULT_COMPONENT_FIELDS = frozenset(
    {"api_version", "api_boundary", "event", "manifest"}
)
SENSITIVE_RESULT_VALUE = re.compile(
    r"(?i)(?:\bbearer\s+|\bbasic\s+|(?:token|secret|password|credential|signature)=|"
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{8,})"
)
ABSOLUTE_HOST_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|/|\\\\)")


def _assert_safe_result_tree(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or key.lower() in FORBIDDEN_RESULT_KEYS:
                raise ContractError(RESULT_UNSAFE_ERROR)
            _assert_safe_result_tree(item)
    elif isinstance(value, list):
        for item in value:
            _assert_safe_result_tree(item)
    elif isinstance(value, str):
        if SENSITIVE_RESULT_VALUE.search(value) or ABSOLUTE_HOST_PATH.match(value):
            raise ContractError(RESULT_UNSAFE_ERROR)
    elif value is not None and not isinstance(value, (bool, int)):
        raise ContractError(RESULT_UNSAFE_ERROR)


def _is_non_negative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def assert_public_safe_result(result: dict[str, Any]) -> None:
    """Require the approved closed result shape and reject sensitive values."""
    _assert_safe_result_tree(result)
    if not isinstance(result, dict):
        raise ContractError(RESULT_UNSAFE_ERROR)

    common = {
        "gate_id",
        "profile_id",
        "command_id",
        "status",
        "observed_at",
        "assertions",
    }
    success_fields = common | {"hashes", "components"}
    failure_fields = common | {"failure_code"}
    if set(result) not in (success_fields, failure_fields):
        raise ContractError(RESULT_UNSAFE_ERROR)
    if (
        result["gate_id"] != GATE_ID
        or result["profile_id"] != PROFILE_ID
        or result["command_id"] != COMMAND_ID
        or result["status"] not in {"PASSED", "FAILED"}
        or not is_strict_utc(result["observed_at"])
        or result["assertions"]
        != {"negative_effect_calls": 0, "no_sensitive_content": True}
    ):
        raise ContractError(RESULT_UNSAFE_ERROR)

    if set(result) == failure_fields:
        if result["status"] != "FAILED" or result["failure_code"] not in {
            RUNNER_ERROR,
            CROSS_REFERENCE_ERROR,
            RESULT_UNSAFE_ERROR,
        }:
            raise ContractError(RESULT_UNSAFE_ERROR)
        return

    hashes = result["hashes"]
    components = result["components"]
    if (
        not isinstance(hashes, dict)
        or set(hashes) != RESULT_HASH_FIELDS
        or any(
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            for digest in hashes.values()
        )
        or not isinstance(components, dict)
        or set(components) != RESULT_COMPONENT_FIELDS
    ):
        raise ContractError(RESULT_UNSAFE_ERROR)
    for component in components.values():
        if not isinstance(component, dict) or set(component) != {
            "total",
            "passed",
            "failed",
            "cases",
        }:
            raise ContractError(RESULT_UNSAFE_ERROR)
        counts = (component["total"], component["passed"], component["failed"])
        cases = component["cases"]
        if (
            not all(_is_non_negative_int(count) for count in counts)
            or not isinstance(cases, list)
            or component["total"] != len(cases)
            or component["passed"] + component["failed"] != component["total"]
        ):
            raise ContractError(RESULT_UNSAFE_ERROR)
        for case in cases:
            if (
                not isinstance(case, dict)
                or set(case) != {"case_id", "kind", "expected", "actual", "status"}
                or any(
                    not isinstance(case[field], str)
                    for field in ("case_id", "kind", "expected", "actual", "status")
                )
                or case["status"] not in {"PASSED", "FAILED"}
            ):
                raise ContractError(RESULT_UNSAFE_ERROR)


def _integrated_fixture_bundle(loaded: dict[str, dict[str, Any]]) -> dict[str, Any]:
    try:
        api_fixture = next(
            case
            for case in loaded["api_boundary_suite"]["cases"]
            if case["id"] == "get-run-valid"
        )
        event_fixture = next(
            case
            for case in loaded["event_suite"]["positive"]
            if case["id"] == "first-append"
        )
        manifest_fixture = next(
            case
            for case in loaded["manifest_suite"]["positive"]
            if case["id"] == "primary-terminal"
        )
    except (KeyError, StopIteration, TypeError):
        _raise_cross_reference_error()
    api_case = copy.deepcopy(api_fixture["response"]["data"])
    api_case["reference_context"] = copy.deepcopy(api_fixture["reference_context"])
    return {
        "api_case": api_case,
        "event_records": copy.deepcopy(event_fixture["records"]),
        "manifest": copy.deepcopy(manifest_fixture["manifest"]),
    }


def run_conformance(paths: dict[str, Path], observed_at: str) -> dict[str, Any]:
    """Run the four exact catalogs and return a closed public-safe result."""
    if set(paths) != set(TRUSTED) or not is_strict_utc(observed_at):
        _raise_runner_error()

    loaded = {
        name: _load_object(paths[name])
        for name in (
            "openapi",
            "event_schema",
            "manifest_schema",
            *SUITE_NAMES,
        )
    }
    for name in SUITE_NAMES:
        validate_suite_catalog(name, loaded[name])

    try:
        validate_openapi_document(loaded["openapi"])
        _strict_schema(loaded["event_schema"])
        _strict_schema(loaded["manifest_schema"])
    except ContractError as exc:
        raise ContractError(RUNNER_ERROR) from exc

    product_schema = _load_object(
        paths["openapi"].parents[2] / "product-task-contract" / "1.0" / "schema.json"
    )
    version_records = _project_api_records(
        run_version_envelope_suite(loaded["openapi"], loaded["api_version_suite"])
    )
    boundary_raw, _ = run_api_boundary_suite(
        loaded["openapi"], product_schema, loaded["api_boundary_suite"]
    )
    boundary_records = _project_api_records(boundary_raw)
    api_effect_calls = sum(
        sum(record["spy_calls"].values()) for record in boundary_raw
    )
    event_records, event_effect_calls = _run_event_suite(
        loaded["event_schema"], loaded["event_suite"]
    )
    manifest_records, manifest_effect_calls = _run_manifest_suite(
        loaded["manifest_schema"], loaded["manifest_suite"]
    )
    validate_cross_contract(**_integrated_fixture_bundle(loaded))

    components = {
        "api_version": _component(version_records),
        "api_boundary": _component(boundary_records),
        "event": _component(event_records),
        "manifest": _component(manifest_records),
    }
    negative_effect_calls = api_effect_calls + event_effect_calls + manifest_effect_calls
    status = (
        "PASSED"
        if all(component["failed"] == 0 for component in components.values())
        and negative_effect_calls == 0
        else "FAILED"
    )
    result = {
        "gate_id": GATE_ID,
        "profile_id": PROFILE_ID,
        "command_id": COMMAND_ID,
        "status": status,
        "observed_at": observed_at,
        "hashes": {
            f"{name}_sha256": sha256_file(paths[name])
            for name in (
                "openapi",
                "event_schema",
                "manifest_schema",
                *SUITE_NAMES,
            )
        },
        "components": components,
        "assertions": {
            "negative_effect_calls": negative_effect_calls,
            "no_sensitive_content": True,
        },
    }
    assert_public_safe_result(result)
    return result


def _failure_result(
    observed_at: str, failure_code: str = RUNNER_ERROR
) -> dict[str, Any]:
    result = {
        "gate_id": GATE_ID,
        "profile_id": PROFILE_ID,
        "command_id": COMMAND_ID,
        "status": "FAILED",
        "failure_code": failure_code,
        "observed_at": observed_at,
        "assertions": {
            "negative_effect_calls": 0,
            "no_sensitive_content": True,
        },
    }
    assert_public_safe_result(result)
    return result


def write_result_atomically(path: Path, result: dict[str, Any]) -> None:
    """Replace only the registered result using a sibling temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        temporary.write_text(
            json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _observed_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: Sequence[str] | None = None, *, root: Path | None = None) -> int:
    """Run the registered command and always replace its registered safe result."""
    repository_root = root if root is not None else Path(__file__).resolve().parents[2]
    observed_at = _observed_at()
    result_path = repository_root / TRUSTED["result"]
    try:
        args = parse_args(argv)
        paths = resolve_registered_paths(repository_root, args)
        result = run_conformance(paths, observed_at)
        exit_code = 0 if result["status"] == "PASSED" else 1
    except ContractError as error:
        failure_code = (
            error.code
            if error.code
            in {RUNNER_ERROR, CROSS_REFERENCE_ERROR, RESULT_UNSAFE_ERROR}
            else RUNNER_ERROR
        )
        result = _failure_result(observed_at, failure_code)
        exit_code = 1
    except (OSError, UnicodeError, TypeError, ValueError, KeyError, IndexError):
        result = _failure_result(observed_at)
        exit_code = 1
    write_result_atomically(result_path, result)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
