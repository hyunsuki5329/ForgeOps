#!/usr/bin/env python3
"""Verify the ForgeOps product-to-canonical state-contract fixture suite."""

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
SCHEMA_REF = "contracts/forgeops-state-contract/1.0/schema.json"
SUITE_REF = "fixtures/forgeops-state-contract/state-suite.json"
EXPECTED_SUITE_ID = "forgeops-state-contract-v1"
EXPECTED_SUITE_VERSION = "1.0"
COMMAND_IDS = {"state-transition-fixture", "event-order-fixture"}
EXPECTED_RESULT_REFS = {
    "state-transition-fixture": "artifacts/verification/vg-003-state-transition-result.json",
    "event-order-fixture": "artifacts/verification/vg-003-event-order-result.json",
}

ALLOWED_TRANSITIONS = {
    "PENDING": {"IN_PROGRESS"},
    "IN_PROGRESS": {"WAITING_FOR_HUMAN", "BLOCKED", "SUCCEEDED", "FAILED", "PARTIAL"},
    "WAITING_FOR_HUMAN": {"IN_PROGRESS", "BLOCKED"},
    "PARTIAL": {"IN_PROGRESS", "SUCCEEDED", "FAILED", "BLOCKED"},
    "BLOCKED": set(),
    "SUCCEEDED": set(),
    "FAILED": set(),
}
PRODUCT_MAPPINGS = {
    "CREATED": {"PENDING"},
    "TRIAGING": {"IN_PROGRESS"},
    "EVALUATING": {"IN_PROGRESS"},
    "AWAITING_USER": {"WAITING_FOR_HUMAN"},
    "AWAITING_APPROVAL": {"WAITING_FOR_HUMAN"},
    "REVIEW_REQUIRED": {"WAITING_FOR_HUMAN"},
    "PARTIAL_RESULT": {"PARTIAL"},
    "COMPLETED_VERIFIED": {"SUCCEEDED"},
    "POLICY_BLOCKED": {"BLOCKED"},
    "BASELINE_UNHEALTHY": {"BLOCKED"},
    "FAILED": {"FAILED"},
    "REJECTED": {"FAILED"},
    "BUDGET_EXCEEDED": {"FAILED", "BLOCKED"},
}
EXPECTED_CASE_CATALOG = (
    ("POSITIVE_CREATED_PENDING", "mapping", "PASSED"),
    ("POSITIVE_ACTIVE_IN_PROGRESS", "positive", "PASSED"),
    ("POSITIVE_WAITING_FOR_HUMAN", "positive", "PASSED"),
    ("POSITIVE_PARTIAL", "positive", "PASSED"),
    ("POSITIVE_VERIFIED_SUCCESS", "positive", "PASSED"),
    ("POSITIVE_POLICY_BLOCK", "positive", "PASSED"),
    ("NEGATIVE_STALE_REVISION", "negative", "STATE_REVISION_STALE"),
    ("NEGATIVE_SEQUENCE_REUSE", "negative", "STATE_SEQUENCE_OUT_OF_ORDER"),
    ("NEGATIVE_SEQUENCE_SKIP", "negative", "STATE_SEQUENCE_OUT_OF_ORDER"),
    ("NEGATIVE_NON_MAIN_ACTOR", "negative", "STATE_OWNER_INVALID"),
    ("NEGATIVE_TERMINAL_RESTART", "negative", "STATE_TRANSITION_INVALID"),
    ("NEGATIVE_SUCCESS_WITHOUT_EVIDENCE", "negative", "STATE_EVIDENCE_INSUFFICIENT"),
    ("NEGATIVE_MAPPING_INVALID", "negative", "STATE_MAPPING_INVALID"),
    ("NEGATIVE_CANCELLED_COERCION", "negative", "STATE_CANCELLED_COERCION_FORBIDDEN"),
    ("NEGATIVE_CANCELLED_COERCION_BLOCKED", "negative", "STATE_CANCELLED_COERCION_FORBIDDEN"),
)


class StateError(Exception):
    """A stable, public-safe state-contract rejection."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


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


def mapping_is_valid(proposal: dict[str, Any]) -> bool:
    return proposal["canonical_state"] in PRODUCT_MAPPINGS.get(proposal["product_state"], set())


def validate_mapping(proposal: dict[str, Any]) -> str:
    """Validate a product-to-canonical mapping without accepting a transition."""
    if proposal["product_state"] == "CANCELLED":
        raise StateError("STATE_CANCELLED_COERCION_FORBIDDEN")
    if not mapping_is_valid(proposal):
        raise StateError("STATE_MAPPING_INVALID")
    if proposal["canonical_state"] == "SUCCEEDED" and not proposal["has_required_evidence"]:
        raise StateError("STATE_EVIDENCE_INSUFFICIENT")
    return "PASSED"


def validate_transition(snapshot: dict[str, Any], proposal: dict[str, Any]) -> str:
    """Validate a Main-owned product mapping to the next canonical state."""
    if proposal["actor"] != "main":
        raise StateError("STATE_OWNER_INVALID")
    if proposal["base_revision"] != snapshot["revision"]:
        raise StateError("STATE_REVISION_STALE")
    if proposal["expected_seq"] != snapshot["next_seq"]:
        raise StateError("STATE_SEQUENCE_OUT_OF_ORDER")
    if proposal["canonical_state"] not in ALLOWED_TRANSITIONS[snapshot["status"]]:
        raise StateError("STATE_TRANSITION_INVALID")
    return validate_mapping(proposal)


def run_case(case: dict[str, Any]) -> dict[str, str]:
    """Return only a stable verdict category for one fixture case."""
    actual_error = ""
    try:
        validator = default_validator()
        case_validator = validator.evolve(schema=validator.schema["$defs"]["case"])
        if next(case_validator.iter_errors(case), None) is not None:
            raise StateError("STATE_SCHEMA_INVALID")
        if case["kind"] == "mapping":
            validate_mapping(case["proposal"])
        else:
            validate_transition(case["snapshot"], case["proposal"])
    except StateError as exc:
        actual_error = exc.code
    except Exception:
        actual_error = "RUNNER_ERROR"

    expected = case.get("expected_result", case.get("expected_error", ""))
    actual = actual_error or "PASSED"
    return {
        "id": str(case.get("id", "")),
        "kind": str(case.get("kind", "")),
        "status": "PASSED" if actual == expected else "FAILED",
        "expected": str(expected),
        "actual": actual,
    }


def public_result(
    command_id: str,
    schema_path: Path,
    suite_path: Path,
    cases: list[dict[str, str]],
    *,
    runner_error: str | None = None,
) -> dict[str, Any]:
    passed = sum(case["status"] == "PASSED" for case in cases)
    result: dict[str, Any] = {
        "command_id": command_id,
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
    parser.add_argument("--command-id", required=True, choices=sorted(COMMAND_IDS))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    schema_path = ROOT / SCHEMA_REF
    suite_path = ROOT / SUITE_REF
    expected_result_ref = EXPECTED_RESULT_REFS[args.command_id]
    result_path = ROOT / expected_result_ref
    try:
        if (
            args.schema != SCHEMA_REF
            or args.suite != SUITE_REF
            or args.result != expected_result_ref
        ):
            raise ValueError("runner paths must name the trusted state fixture")
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        suite = load_json(suite_path)
        validate_suite(suite)
        cases = [run_case(item) for item in suite["cases"]]
        result = public_result(args.command_id, schema_path, suite_path, cases)
        atomic_write(result_path, json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 0 if result["status"] == "PASSED" else 1
    except Exception:
        result = public_result(
            args.command_id,
            schema_path,
            suite_path,
            [],
            runner_error="RUNNER_CONTRACT_INVALID",
        )
        atomic_write(result_path, json.dumps(result, indent=2, sort_keys=True) + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
