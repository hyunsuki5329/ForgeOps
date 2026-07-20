#!/usr/bin/env python3
"""Verify the Product Task Contract -> TaskPacket bridge fixture suite."""

from __future__ import annotations

import argparse
import copy
import hashlib
import html
import importlib.metadata
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


SUPPORTED_SCHEMA_ID = "forgeops.task-contract"
SUPPORTED_SCHEMA_VERSION = "1.0"
EXPECTED_SUITE_ID = "forgeops-contract-bridge-v1"
EXPECTED_SUITE_VERSION = "1.0"
PROFILE_ID = "forgeops-contract-bridge"
COMMAND_ID = "bridge-schema-fixture"
EXPECTED_CASE_COUNTS = {"positive": 3, "negative": 16}
FORBIDDEN_CONTROL_FIELDS = {
    "authority",
    "capabilities",
    "approval",
    "policy",
    "budgets",
    "accepted_state",
    "tools",
}
APPROVAL_RANK = {
    "not_required": 0,
    "required": 1,
    "never_without_explicit_high_risk_approval": 2,
}
MUTATIONS = {
    "NONE",
    "EMBED_CONTROL_TEXT",
    "STRENGTHEN_VERIFIED_GATE",
    "UNSUPPORTED_VERSION",
    "ADD_FORBIDDEN_FIELD",
    "ADD_UNKNOWN_FIELD",
    "REMOVE_REQUIRED_FIELD",
    "WRONG_TYPE",
    "DUPLICATE_CRITERION",
    "UNMAPPED_INTENT",
    "UNTRUSTED_COMMAND",
    "RELAX_VERIFIED_GATE",
    "PROVENANCE_HASH_MISMATCH",
}
EXPECTED_CASE_CATALOG = (
    ("POSITIVE_LOSSLESS_BASELINE", "positive", "NONE", None, "PASSED"),
    ("POSITIVE_EMBEDDED_CONTROL_TEXT", "positive", "EMBED_CONTROL_TEXT", None, "PASSED"),
    ("POSITIVE_VERIFIED_GATE_STRENGTHENING", "positive", "STRENGTHEN_VERIFIED_GATE", None, "PASSED"),
    ("NEGATIVE_VERSION_UNSUPPORTED", "negative", "UNSUPPORTED_VERSION", None, "CONTRACT_VERSION_UNSUPPORTED"),
    ("NEGATIVE_CONTROL_AUTHORITY", "negative", "ADD_FORBIDDEN_FIELD", "authority", "CONTRACT_CONTROL_FIELD_FORBIDDEN"),
    ("NEGATIVE_CONTROL_CAPABILITIES", "negative", "ADD_FORBIDDEN_FIELD", "capabilities", "CONTRACT_CONTROL_FIELD_FORBIDDEN"),
    ("NEGATIVE_CONTROL_APPROVAL", "negative", "ADD_FORBIDDEN_FIELD", "approval", "CONTRACT_CONTROL_FIELD_FORBIDDEN"),
    ("NEGATIVE_CONTROL_POLICY", "negative", "ADD_FORBIDDEN_FIELD", "policy", "CONTRACT_CONTROL_FIELD_FORBIDDEN"),
    ("NEGATIVE_CONTROL_BUDGETS", "negative", "ADD_FORBIDDEN_FIELD", "budgets", "CONTRACT_CONTROL_FIELD_FORBIDDEN"),
    ("NEGATIVE_CONTROL_ACCEPTED_STATE", "negative", "ADD_FORBIDDEN_FIELD", "accepted_state", "CONTRACT_CONTROL_FIELD_FORBIDDEN"),
    ("NEGATIVE_CONTROL_TOOLS", "negative", "ADD_FORBIDDEN_FIELD", "tools", "CONTRACT_CONTROL_FIELD_FORBIDDEN"),
    ("NEGATIVE_UNKNOWN_FIELD", "negative", "ADD_UNKNOWN_FIELD", None, "CONTRACT_SCHEMA_INVALID"),
    ("NEGATIVE_MISSING_REQUIRED", "negative", "REMOVE_REQUIRED_FIELD", None, "CONTRACT_SCHEMA_INVALID"),
    ("NEGATIVE_WRONG_TYPE", "negative", "WRONG_TYPE", None, "CONTRACT_SCHEMA_INVALID"),
    ("NEGATIVE_DUPLICATE_CRITERION", "negative", "DUPLICATE_CRITERION", None, "CONTRACT_CRITERION_DUPLICATE"),
    ("NEGATIVE_UNMAPPED_INTENT", "negative", "UNMAPPED_INTENT", None, "CONTRACT_INTENT_UNMAPPED"),
    ("NEGATIVE_UNTRUSTED_COMMAND", "negative", "UNTRUSTED_COMMAND", None, "CONTRACT_COMMAND_UNTRUSTED"),
    ("NEGATIVE_VERIFIED_GATE_RELAXATION", "negative", "RELAX_VERIFIED_GATE", None, "CONTRACT_MONOTONICITY_VIOLATION"),
    ("NEGATIVE_PROVENANCE_HASH", "negative", "PROVENANCE_HASH_MISMATCH", None, "CONTRACT_PROVENANCE_INVALID"),
)


class BridgeError(Exception):
    """A stable, public-safe bridge rejection."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def project_path(root: Path, raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"path must be project-root-relative: {raw}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {raw}") from exc
    return resolved


def validate_suite(
    suite: dict[str, Any], schema_ref: str, suite_ref: str
) -> None:
    allowed_keys = {
        "suite_id",
        "suite_version",
        "schema_ref",
        "bridge_ref",
        "base_contract",
        "trusted_context",
        "cases",
    }
    if set(suite) != allowed_keys:
        raise ValueError("suite top-level fields do not match the closed manifest")
    if suite["suite_id"] != EXPECTED_SUITE_ID or suite["suite_version"] != EXPECTED_SUITE_VERSION:
        raise ValueError("unsupported suite identity or version")
    if suite["schema_ref"] != schema_ref:
        raise ValueError("suite schema_ref does not match --schema")
    if suite_ref != "fixtures/product-task-contract-bridge/suite.json":
        raise ValueError("--suite must name the trusted bridge suite")
    if not isinstance(suite["base_contract"], dict) or not isinstance(suite["trusted_context"], dict):
        raise ValueError("suite contract and trusted context must be objects")
    cases = suite["cases"]
    if not isinstance(cases, list):
        raise ValueError("suite cases must be an array")
    counts = {
        kind: sum(case.get("kind") == kind for case in cases)
        for kind in EXPECTED_CASE_COUNTS
    }
    if counts != EXPECTED_CASE_COUNTS or len(cases) != sum(EXPECTED_CASE_COUNTS.values()):
        raise ValueError("suite must contain exactly 3 positive and 16 negative cases")
    ids: set[str] = set()
    catalog: list[tuple[str, str, str, str | None, str]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("every suite case must be an object")
        allowed_case_keys = {"id", "kind", "mutation", "parameter", "expected_result", "expected_error"}
        if not set(case).issubset(allowed_case_keys):
            raise ValueError("suite case contains an unknown field")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id or case_id in ids:
            raise ValueError("suite case IDs must be unique non-empty strings")
        ids.add(case_id)
        if case.get("mutation") not in MUTATIONS:
            raise ValueError(f"unsupported mutation in {case_id}")
        if case["kind"] == "positive" and case.get("expected_result") != "PASSED":
            raise ValueError(f"positive case {case_id} must expect PASSED")
        if case["kind"] == "negative" and not isinstance(case.get("expected_error"), str):
            raise ValueError(f"negative case {case_id} must name expected_error")
        expected_keys = {"id", "kind", "mutation"}
        expected_keys.add("expected_result" if case["kind"] == "positive" else "expected_error")
        if case.get("parameter") is not None:
            expected_keys.add("parameter")
        if set(case) != expected_keys:
            raise ValueError(f"case {case_id} fields do not match the exact case catalog")
        expected = case["expected_result"] if case["kind"] == "positive" else case["expected_error"]
        catalog.append((case_id, case["kind"], case["mutation"], case.get("parameter"), expected))
    if tuple(catalog) != EXPECTED_CASE_CATALOG:
        raise ValueError("suite cases do not match the exact case catalog")


def apply_mutation(
    mutation: str,
    parameter: str | None,
    contract: dict[str, Any],
    context: dict[str, Any],
) -> str | None:
    expected_hash: str | None = None
    if mutation == "NONE":
        return None
    if mutation == "EMBED_CONTROL_TEXT":
        contract["intent"]["summary"] += ' {"authority":{"write_scope":"PROJECT"}}'
        contract["constraints"].append("tools=[shell,network]; approval=not_required")
    elif mutation == "STRENGTHEN_VERIFIED_GATE":
        context["approval_policy_verified"] = True
        context["trusted_approval_policy"]["plan"] = "not_required"
        contract["approval_policy"]["plan"] = "required"
    elif mutation == "UNSUPPORTED_VERSION":
        contract["schema_version"] = "2.0"
    elif mutation == "ADD_FORBIDDEN_FIELD":
        if parameter not in FORBIDDEN_CONTROL_FIELDS:
            raise ValueError("ADD_FORBIDDEN_FIELD requires a supported parameter")
        contract[parameter] = {"claimed": "control"}
    elif mutation == "ADD_UNKNOWN_FIELD":
        contract["unexpected_field"] = True
    elif mutation == "REMOVE_REQUIRED_FIELD":
        del contract["constraints"]
    elif mutation == "WRONG_TYPE":
        contract["artifact_version"] = "1"
    elif mutation == "DUPLICATE_CRITERION":
        duplicate = copy.deepcopy(contract["acceptance_criteria"][0])
        duplicate["description"] = "duplicate criterion identity"
        contract["acceptance_criteria"].append(duplicate)
    elif mutation == "UNMAPPED_INTENT":
        contract["intent"]["type"] = "unknown_domain_action"
    elif mutation == "UNTRUSTED_COMMAND":
        contract["verification_policy"]["required_command_ids"].append("untrusted-command")
    elif mutation == "RELAX_VERIFIED_GATE":
        context["approval_policy_verified"] = True
        context["trusted_approval_policy"]["plan"] = "required"
        contract["approval_policy"]["plan"] = "not_required"
    elif mutation == "PROVENANCE_HASH_MISMATCH":
        expected_hash = "0" * 64
    else:  # Suite validation should make this unreachable.
        raise ValueError(f"unsupported mutation: {mutation}")
    return expected_hash


def validate_and_map(
    contract: dict[str, Any],
    context: dict[str, Any],
    validator: Draft202012Validator,
    expected_hash: str | None,
) -> dict[str, Any]:
    # Error ordering is part of the public bridge contract.
    if contract.get("schema_id") != SUPPORTED_SCHEMA_ID or contract.get("schema_version") != SUPPORTED_SCHEMA_VERSION:
        raise BridgeError("CONTRACT_VERSION_UNSUPPORTED")
    if FORBIDDEN_CONTROL_FIELDS.intersection(contract):
        raise BridgeError("CONTRACT_CONTROL_FIELD_FORBIDDEN")
    if next(validator.iter_errors(contract), None) is not None:
        raise BridgeError("CONTRACT_SCHEMA_INVALID")

    criterion_ids = [criterion["id"] for criterion in contract["acceptance_criteria"]]
    if len(criterion_ids) != len(set(criterion_ids)):
        raise BridgeError("CONTRACT_CRITERION_DUPLICATE")

    intent_mapping = context["intent_mapping"]
    intent_type = contract["intent"]["type"]
    if intent_type not in intent_mapping:
        raise BridgeError("CONTRACT_INTENT_UNMAPPED")

    requested_profile = contract["verification_policy"]["profile_id"]
    trusted_profile = context["validation_profile"]
    if requested_profile != trusted_profile["id"]:
        raise BridgeError("CONTRACT_COMMAND_UNTRUSTED")
    trusted_commands = {record["id"]: record for record in trusted_profile["commands"]}
    requested_ids = contract["verification_policy"]["baseline_command_ids"] + contract["verification_policy"]["required_command_ids"]
    if any(command_id not in trusted_commands for command_id in requested_ids):
        raise BridgeError("CONTRACT_COMMAND_UNTRUSTED")
    selected_ids = list(dict.fromkeys(requested_ids))

    trusted_policy = context["trusted_approval_policy"]
    contract_policy = contract["approval_policy"]
    effective_policy = copy.deepcopy(trusted_policy)
    if context["approval_policy_verified"]:
        if any(APPROVAL_RANK[contract_policy[key]] < APPROVAL_RANK[trusted_policy[key]] for key in trusted_policy):
            raise BridgeError("CONTRACT_MONOTONICITY_VIOLATION")
        effective_policy = {
            key: max((trusted_policy[key], contract_policy[key]), key=APPROVAL_RANK.__getitem__)
            for key in trusted_policy
        }

    content_hash = canonical_sha256(contract)
    if expected_hash is not None and content_hash != expected_hash:
        raise BridgeError("CONTRACT_PROVENANCE_INVALID")

    canonical = context["canonical_control"]
    extensions = {
        "task_contract": {
            "schema_id": contract["schema_id"],
            "schema_version": contract["schema_version"],
            "artifact_id": contract["artifact_id"],
            "artifact_version": contract["artifact_version"],
            "repository": copy.deepcopy(contract["repository"]),
            "intent": {"source_issue": contract["intent"].get("source_issue")},
            "criterion_verification": [
                {"id": item["id"], "verification": item["verification"]}
                for item in contract["acceptance_criteria"]
            ],
            "verification_policy": copy.deepcopy(contract["verification_policy"]),
            "risk": copy.deepcopy(contract["risk"]),
            "approval_policy": copy.deepcopy(contract["approval_policy"]),
            "content_hash_ref": f"sha256:{content_hash}",
        },
        "product_budget": copy.deepcopy(contract["budget"]),
    }
    mapped = {
        "task_id": contract["task_id"],
        "request": {
            "kind": intent_mapping[intent_type],
            "objective": contract["intent"]["summary"],
            "acceptance_criteria": [
                {"id": item["id"], "statement": item["description"]}
                for item in contract["acceptance_criteria"]
            ],
            "constraints": copy.deepcopy(contract["constraints"]),
        },
        "project_profile": copy.deepcopy(canonical["project_profile"]),
        "capabilities": copy.deepcopy(canonical["capabilities"]),
        "authority": copy.deepcopy(canonical["authority"]),
        "control": copy.deepcopy(canonical["control"]),
        "budgets": copy.deepcopy(canonical["budgets"]),
        "accepted_state": copy.deepcopy(canonical["accepted_state"]),
        "tool_schema": copy.deepcopy(canonical["tool_schema"]),
        "bridge_decision": {"required_gates": effective_policy},
    }
    mapped["project_profile"]["validation_commands"] = [
        copy.deepcopy(trusted_commands[command_id]) for command_id in selected_ids
    ]
    mapped["project_profile"].setdefault("extensions", {}).setdefault("forgeops", {}).update(extensions)

    expected_criteria = [
        {"id": item["id"], "statement": item["description"]}
        for item in contract["acceptance_criteria"]
    ]
    if mapped["request"]["objective"] != contract["intent"]["summary"]:
        raise AssertionError("objective was not losslessly mapped")
    if mapped["request"]["acceptance_criteria"] != expected_criteria:
        raise AssertionError("criteria were not losslessly mapped")
    if mapped["request"]["constraints"] != contract["constraints"]:
        raise AssertionError("constraints were not losslessly mapped")
    if contract["intent"].get("source_issue") in mapped["project_profile"].get("source_of_truth", []):
        raise AssertionError("source issue was promoted into source_of_truth")
    task_contract = mapped["project_profile"]["extensions"]["forgeops"]["task_contract"]
    if task_contract["repository"] != contract["repository"]:
        raise AssertionError("repository identity was not losslessly preserved")
    if task_contract["intent"]["source_issue"] != contract["intent"].get("source_issue"):
        raise AssertionError("source issue was not preserved as namespaced provenance")
    expected_verification = [
        {"id": item["id"], "verification": item["verification"]}
        for item in contract["acceptance_criteria"]
    ]
    if task_contract["criterion_verification"] != expected_verification:
        raise AssertionError("criterion verification provenance was not preserved")
    if task_contract["risk"] != contract["risk"] or task_contract["approval_policy"] != contract["approval_policy"]:
        raise AssertionError("risk or approval provenance was not preserved")
    if task_contract["content_hash_ref"] != f"sha256:{canonical_sha256(contract)}":
        raise AssertionError("content hash provenance was not preserved")
    for field in ("capabilities", "authority", "control", "budgets", "accepted_state", "tool_schema"):
        if mapped[field] != canonical[field]:
            raise AssertionError(f"canonical {field} was changed by contract data")
    if mapped["project_profile"]["validation_commands"] != [trusted_commands[item] for item in selected_ids]:
        raise AssertionError("validation command was not selected from the trusted profile")
    if mapped["project_profile"]["extensions"]["forgeops"]["product_budget"] == mapped["budgets"]:
        raise AssertionError("product budget was confused with harness attempt budgets")
    return mapped


def run_case(
    case: dict[str, Any],
    base_contract: dict[str, Any],
    trusted_context: dict[str, Any],
    validator: Draft202012Validator,
) -> dict[str, str]:
    contract = copy.deepcopy(base_contract)
    context = copy.deepcopy(trusted_context)
    expected_hash = apply_mutation(case["mutation"], case.get("parameter"), contract, context)
    actual_error = ""
    try:
        validate_and_map(contract, context, validator, expected_hash)
    except BridgeError as exc:
        actual_error = exc.code
    except Exception:
        actual_error = "RUNNER_ERROR"

    if case["kind"] == "positive":
        passed = not actual_error
        expected = "PASSED"
    else:
        expected = case["expected_error"]
        passed = actual_error == expected
    return {
        "id": case["id"],
        "kind": case["kind"],
        "status": "PASSED" if passed else "FAILED",
        "expected": expected,
        "actual": actual_error or "PASSED",
    }


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    ) as stream:
        stream.write(content)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def render_html(result: dict[str, Any]) -> str:
    rows = []
    for case in result["cases"]:
        cells = "".join(f"<td>{html.escape(str(case[key]))}</td>" for key in ("id", "kind", "status", "expected", "actual"))
        rows.append(f"<tr>{cells}</tr>")
    summary = result["summary"]
    runner_error = result.get("runner_error")
    runner_line = f"<p>Runner error: {html.escape(runner_error)}</p>" if runner_error else ""
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="ko">',
            '<head><meta charset="utf-8"><title>W1 Contract Bridge Checkpoint</title></head>',
            "<body>",
            "<h1>W1 Contract Bridge Checkpoint</h1>",
            f"<p>Gate: {html.escape(result['gate_id'])}</p>",
            f"<p>Status: {html.escape(result['status'])}</p>",
            f"<p>Observed at: {html.escape(result['observed_at'])}</p>",
            f"<p>Cases: {summary['passed']}/{summary['total']} passed; positive {summary['positive_passed']}/{summary['positive_total']}; negative {summary['negative_passed']}/{summary['negative_total']}.</p>",
            runner_line,
            "<table>",
            "<thead><tr><th>Case</th><th>Kind</th><th>Status</th><th>Expected</th><th>Actual</th></tr></thead>",
            "<tbody>",
            *rows,
            "</tbody></table>",
            "<p>This report contains public fixture identifiers and stable error categories only.</p>",
            "</body></html>",
            "",
        ]
    )


def runner_failure_result(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "gate_id": "VG-002",
        "profile_id": PROFILE_ID,
        "command_id": COMMAND_ID,
        "status": "FAILED",
        "evidence_tier": "E2",
        "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime": {
            "python": sys.version.split()[0],
            "jsonschema": importlib.metadata.version("jsonschema"),
        },
        "inputs": {
            "schema": args.schema.replace("\\", "/"),
            "suite": args.suite.replace("\\", "/"),
        },
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "positive_total": 0,
            "positive_passed": 0,
            "negative_total": 0,
            "negative_passed": 0,
        },
        "cases": [],
        "runner_error": "RUNNER_CONTRACT_INVALID",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path.cwd().resolve()
    result_path: Path | None = None
    report_path: Path | None = None
    try:
        result_path = project_path(root, args.result)
        report_path = project_path(root, args.report)
        schema_path = project_path(root, args.schema)
        suite_path = project_path(root, args.suite)
        schema = load_json(schema_path)
        suite = load_json(suite_path)
        validate_suite(suite, args.schema.replace("\\", "/"), args.suite.replace("\\", "/"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        cases = [
            run_case(case, suite["base_contract"], suite["trusted_context"], validator)
            for case in suite["cases"]
        ]
    except Exception:
        if result_path is not None and report_path is not None:
            failure = runner_failure_result(args)
            try:
                atomic_write(result_path, json.dumps(failure, ensure_ascii=False, indent=2) + "\n")
                atomic_write(report_path, render_html(failure))
            except OSError:
                pass
        print("VG-002 RUNNER_ERROR", file=sys.stderr)
        return 2

    positive = [case for case in cases if case["kind"] == "positive"]
    negative = [case for case in cases if case["kind"] == "negative"]
    passed = sum(case["status"] == "PASSED" for case in cases)
    result = {
        "gate_id": "VG-002",
        "profile_id": PROFILE_ID,
        "command_id": COMMAND_ID,
        "status": "PASSED" if passed == len(cases) else "FAILED",
        "evidence_tier": "E2",
        "observed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime": {
            "python": sys.version.split()[0],
            "jsonschema": importlib.metadata.version("jsonschema"),
        },
        "inputs": {
            "schema": args.schema.replace("\\", "/"),
            "schema_sha256": file_sha256(schema_path),
            "suite": args.suite.replace("\\", "/"),
            "suite_sha256": file_sha256(suite_path),
        },
        "summary": {
            "total": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "positive_total": len(positive),
            "positive_passed": sum(case["status"] == "PASSED" for case in positive),
            "negative_total": len(negative),
            "negative_passed": sum(case["status"] == "PASSED" for case in negative),
        },
        "cases": cases,
    }
    atomic_write(result_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    atomic_write(report_path, render_html(result))
    summary = result["summary"]
    print(
        f"VG-002 {result['status']} {summary['passed']}/{summary['total']} "
        f"positive={summary['positive_passed']}/{summary['positive_total']} "
        f"negative={summary['negative_passed']}/{summary['negative_total']}"
    )
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
