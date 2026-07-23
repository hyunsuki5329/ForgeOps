#!/usr/bin/env python3
"""Verify the ForgeOps replay-contract fixture suite without external effects."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_REF = "contracts/forgeops-replay-contract/1.0/schema.json"
SUITE_REF = "fixtures/forgeops-replay-contract/suite.json"
COMMAND_ID = "replay-contract-negative"
EXPECTED_RESULT_REF = "artifacts/verification/vg-003-replay-contract-result.json"
EXPECTED_SUITE_ID = "forgeops-replay-contract-v1"
EXPECTED_SUITE_VERSION = "1.0"
MODES = {"AUDIT_REPLAY", "REEXECUTE", "COUNTERFACTUAL"}
EXPECTED_CASE_CATALOG = (
    ("POSITIVE_AUDIT_READ_ONLY", "positive", "PASSED"),
    ("POSITIVE_COUNTERFACTUAL_EFFECT_FREE", "positive", "PASSED"),
    ("POSITIVE_REEXECUTE_EFFECT_FREE", "positive", "PASSED"),
    ("POSITIVE_REEXECUTE_EXTERNAL_EFFECT", "positive", "PASSED"),
    ("NEGATIVE_INVALID_MODE", "negative", "REPLAY_MODE_INVALID"),
    ("NEGATIVE_LINEAGE_MISSING", "negative", "REPLAY_LINEAGE_MISSING"),
    ("NEGATIVE_RUN_REUSED", "negative", "REPLAY_IDENTITY_REUSED"),
    ("NEGATIVE_CORRELATION_REUSED", "negative", "REPLAY_IDENTITY_REUSED"),
    ("NEGATIVE_SEQUENCE_REUSED", "negative", "REPLAY_IDENTITY_REUSED"),
    ("NEGATIVE_COUNTERFACTUAL_TASK_REUSED", "negative", "REPLAY_IDENTITY_REUSED"),
    ("NEGATIVE_COPY_AUTHORITY", "negative", "REPLAY_CONTROL_COPY_FORBIDDEN"),
    ("NEGATIVE_COPY_APPROVAL_TOKEN", "negative", "REPLAY_CONTROL_COPY_FORBIDDEN"),
    ("NEGATIVE_COPY_NONCE", "negative", "REPLAY_CONTROL_COPY_FORBIDDEN"),
    ("NEGATIVE_COPY_CREDENTIAL", "negative", "REPLAY_CONTROL_COPY_FORBIDDEN"),
    ("NEGATIVE_COPY_PUBLISHER_TOKEN", "negative", "REPLAY_CONTROL_COPY_FORBIDDEN"),
    ("NEGATIVE_COPY_PREVIOUS_DISPATCH_RESULT", "negative", "REPLAY_CONTROL_COPY_FORBIDDEN"),
    ("NEGATIVE_AUDIT_EXTERNAL_EFFECT", "negative", "REPLAY_EXTERNAL_EFFECT_FORBIDDEN"),
    ("NEGATIVE_COUNTERFACTUAL_EXTERNAL_EFFECT", "negative", "REPLAY_EXTERNAL_EFFECT_FORBIDDEN"),
    ("NEGATIVE_REEXECUTE_PRECONDITIONS_INCOMPLETE", "negative", "REPLAY_REAPPROVAL_REQUIRED"),
    ("NEGATIVE_UNKNOWN_OUTCOME_RETRY", "negative", "REPLAY_RECONCILIATION_REQUIRED"),
)


class ReplayError(Exception):
    """A stable, public-safe replay-contract rejection."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SpyDispatcher:
    """Fixture-only dispatcher that records no payload or external outcome."""

    def __init__(self) -> None:
        self.calls = 0

    def dispatch(self) -> None:
        self.calls += 1


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def default_validator() -> Draft202012Validator:
    schema = load_json(ROOT / SCHEMA_REF)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def validate_schema(request: dict[str, Any]) -> None:
    validator = default_validator()
    request_validator = validator.evolve(schema=validator.schema["$defs"]["request"])
    if next(request_validator.iter_errors(request), None) is not None:
        raise ReplayError("REPLAY_SCHEMA_INVALID")


def validate_suite(suite: dict[str, Any]) -> None:
    if set(suite) != {"suite_id", "suite_version", "schema_ref", "cases"}:
        raise ValueError("suite top-level fields do not match the closed manifest")
    if suite["suite_id"] != EXPECTED_SUITE_ID or suite["suite_version"] != EXPECTED_SUITE_VERSION:
        raise ValueError("unsupported suite identity or version")
    if suite["schema_ref"] != SCHEMA_REF:
        raise ValueError("suite schema_ref does not match the trusted schema")
    if next(default_validator().iter_errors(suite), None) is not None:
        raise ValueError("suite does not satisfy the closed schema")

    catalog = []
    for item in suite["cases"]:
        expected = item.get("expected_result", item.get("expected_error"))
        catalog.append((item["id"], item["kind"], expected))
    if tuple(catalog) != EXPECTED_CASE_CATALOG:
        raise ValueError("suite cases do not match the exact case catalog")


def lineage_complete(lineage: dict[str, Any]) -> bool:
    return all(
        isinstance(lineage[name], str) and lineage[name]
        for name in ("source_task_id", "source_run_id", "source_manifest_id", "source_correlation_id")
    )


def identity_reused(request: dict[str, Any]) -> bool:
    lineage = request["lineage"]
    identity = request["new_identity"]
    return (
        identity["run_id"] == lineage["source_run_id"]
        or identity["correlation_id"] == lineage["source_correlation_id"]
        or identity["event_seq"] == lineage["source_event_seq"]
        or (
            request["mode"] == "COUNTERFACTUAL"
            and request["contract_changed"]
            and identity["task_id"] == lineage["source_task_id"]
        )
    )


def fresh_effect_preconditions(request: dict[str, Any]) -> bool:
    return all(request["reexecute_preconditions"].values())


def validate(request: dict[str, Any]) -> str:
    """Validate replay guards in stable, fail-closed priority order."""
    validate_schema(request)
    if request["mode"] not in MODES:
        raise ReplayError("REPLAY_MODE_INVALID")
    if not lineage_complete(request["lineage"]):
        raise ReplayError("REPLAY_LINEAGE_MISSING")
    if identity_reused(request):
        raise ReplayError("REPLAY_IDENTITY_REUSED")
    if request["copied_controls"]:
        raise ReplayError("REPLAY_CONTROL_COPY_FORBIDDEN")
    if request["mode"] in {"AUDIT_REPLAY", "COUNTERFACTUAL"} and request[
        "requested_external_effect"
    ]:
        raise ReplayError("REPLAY_EXTERNAL_EFFECT_FORBIDDEN")
    if request["mode"] == "REEXECUTE" and not fresh_effect_preconditions(request):
        raise ReplayError("REPLAY_REAPPROVAL_REQUIRED")
    if not request["outcome_known"] and request["requested_external_effect"]:
        raise ReplayError("REPLAY_RECONCILIATION_REQUIRED")
    return "PASSED"


def evaluate(request: dict[str, Any]) -> tuple[str, SpyDispatcher]:
    """Validate then perform the sole permitted fixture-local dispatch."""
    dispatcher = SpyDispatcher()
    try:
        result = validate(request)
    except ReplayError as exc:
        return exc.code, dispatcher
    if request["requested_external_effect"]:
        dispatcher.dispatch()
    return result, dispatcher


def run_case(case: dict[str, Any]) -> dict[str, str]:
    """Return only stable case identity, kind, expected/actual, and verdict."""
    actual_error = ""
    try:
        validator = default_validator()
        case_validator = validator.evolve(schema=validator.schema["$defs"]["case"])
        if next(case_validator.iter_errors(case), None) is not None:
            raise ReplayError("REPLAY_SCHEMA_INVALID")
        actual, dispatcher = evaluate(case["request"])
        if dispatcher.calls and case["kind"] == "negative":
            actual = "RUNNER_ERROR"
    except ReplayError as exc:
        actual = exc.code
    except Exception:
        actual = "RUNNER_ERROR"

    expected = case.get("expected_result", case.get("expected_error", ""))
    return {
        "id": str(case.get("id", "")),
        "kind": str(case.get("kind", "")),
        "status": "PASSED" if actual == expected else "FAILED",
        "expected": str(expected),
        "actual": actual,
    }


def public_result(
    schema_path: Path,
    suite_path: Path,
    cases: list[dict[str, str]],
    *,
    runner_error: str | None = None,
) -> dict[str, Any]:
    passed = sum(case["status"] == "PASSED" for case in cases)
    result: dict[str, Any] = {
        "command_id": COMMAND_ID,
        "status": "PASSED" if not runner_error and passed == len(cases) else "FAILED",
        "schema_sha256": file_sha256(schema_path) if schema_path.is_file() else None,
        "suite_sha256": file_sha256(suite_path) if suite_path.is_file() else None,
        "observed_at": utc_now(),
        "summary": {"total": len(cases), "passed": passed, "failed": len(cases) - passed},
        "cases": cases,
    }
    if runner_error:
        result["runner_error"] = runner_error
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schema_path = ROOT / SCHEMA_REF
    suite_path = ROOT / SUITE_REF
    result_path = ROOT / EXPECTED_RESULT_REF
    try:
        if (
            args.schema != SCHEMA_REF
            or args.suite != SUITE_REF
            or args.result != EXPECTED_RESULT_REF
        ):
            raise ValueError("runner paths must name the trusted replay fixture")
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        suite = load_json(suite_path)
        validate_suite(suite)
        cases = [run_case(item) for item in suite["cases"]]
        result = public_result(schema_path, suite_path, cases)
        atomic_write(result_path, json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 0 if result["status"] == "PASSED" else 1
    except Exception:
        result = public_result(
            schema_path, suite_path, [], runner_error="RUNNER_CONTRACT_INVALID"
        )
        atomic_write(result_path, json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
