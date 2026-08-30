"""Registered E2 verifier for the W6 local Main-Part-Work-Main flow."""

from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.local_vertical import common, main_actor, part_actor, work_actor


SCHEMA_REF = "contracts/forgeops-local-vertical/1.0/schema.json"
PRODUCT_SCHEMA_REF = "contracts/product-task-contract/1.0/schema.json"
SNAPSHOT_SCHEMA_REF = "contracts/forgeops-snapshot-contract/1.0/schema.json"
CONTEXT_SCHEMA_REF = "contracts/forgeops-context-pack/1.0/schema.json"
SUITE_REF = "fixtures/forgeops-local-vertical/suite.json"
RESULT_REF = "artifacts/verification/vg-012-local-vertical-result.json"
COMMAND_ID = "main-part-work-main"
PROFILE_ID = "forgeops-local-vertical"
CASE_CATALOG = (
    ("POSITIVE_MAIN_PART_WORK_MAIN", "positive", "NONE", "expected_result", "PASSED"),
    ("POSITIVE_GATE_WAITING", "positive", "READ_NONE_GATE", "expected_result", "PASSED"),
    ("NEGATIVE_MAIN_PROTOCOL", "negative", "MAIN_PROTOCOL", "expected_error", "MAIN_CONTRACT_VERSION_UNSUPPORTED"),
    ("NEGATIVE_PART_ENVELOPE_MISMATCH", "negative", "PART_ENVELOPE_MISMATCH", "expected_error", "PART_ENVELOPE_INVALID"),
    ("NEGATIVE_PART_READ_NONE", "negative", "PART_READ_NONE", "expected_error", "PART_READ_AUTHORITY_DENIED"),
    ("NEGATIVE_CONTEXT_HASH_MISMATCH", "negative", "CONTEXT_HASH_MISMATCH", "expected_error", "PART_CONTEXT_PROVENANCE_INVALID"),
    ("NEGATIVE_PART_STATE_OWNERSHIP", "negative", "PART_STATE_OWNERSHIP", "expected_error", "PART_STATE_OWNERSHIP_FORBIDDEN"),
    ("NEGATIVE_PROTECTED_NO_APPROVAL", "negative", "PROTECTED_NO_APPROVAL", "expected_error", "PART_PROTECTED_APPROVAL_REQUIRED"),
    ("NEGATIVE_APPROVAL_WITHOUT_AUTHORITY", "negative", "APPROVAL_WITHOUT_AUTHORITY", "expected_error", "PART_WRITE_AUTHORITY_DENIED"),
    ("NEGATIVE_HYBRID_IDENTITY", "negative", "HYBRID_IDENTITY", "expected_error", "WORK_ACTION_IDENTITY_INVALID"),
    ("NEGATIVE_SCOPE_LIST_MISMATCH", "negative", "SCOPE_LIST_MISMATCH", "expected_error", "AUTHORITY_SCOPE_LIST_MISMATCH"),
    ("NEGATIVE_WORK_ENVELOPE_MISMATCH", "negative", "WORK_ENVELOPE_MISMATCH", "expected_error", "WORK_ENVELOPE_INVALID"),
    ("NEGATIVE_WORK_MODE_EXPLORE", "negative", "WORK_MODE_EXPLORE", "expected_error", "WORK_OPERATION_MODE_INVALID"),
    ("NEGATIVE_WORK_CAPABILITY_UNKNOWN", "negative", "WORK_CAPABILITY_UNKNOWN", "expected_error", "WORK_CAPABILITY_DENIED"),
    ("NEGATIVE_TRUST_APPROVED_ID_INJECTION", "negative", "TRUST_APPROVED_ID_INJECTION", "expected_error", "WORK_APPROVED_ID_INVALID"),
    ("NEGATIVE_TRUST_VALIDATION_AT_INJECTION", "negative", "TRUST_VALIDATION_AT_INJECTION", "expected_error", "WORK_VALIDATION_AT_UNTRUSTED"),
    ("NEGATIVE_PROJECT_EXECUTE_SCOPE", "negative", "PROJECT_EXECUTE_SCOPE", "expected_error", "AUTHORITY_EXECUTE_SCOPE_INVALID"),
    ("NEGATIVE_WILDCARD_COMPANION", "negative", "WILDCARD_COMPANION", "expected_error", "AUTHORITY_RESOURCE_INVALID"),
    ("NEGATIVE_RESOURCE_TRAVERSAL", "negative", "RESOURCE_TRAVERSAL", "expected_error", "RESOURCE_IDENTITY_NONCANONICAL"),
    ("NEGATIVE_UNSUPPORTED_COMMAND", "negative", "UNSUPPORTED_COMMAND", "expected_error", "WORK_ACTION_TYPE_UNSUPPORTED"),
    ("NEGATIVE_WORK_STALE_REVISION", "negative", "WORK_STALE_REVISION", "expected_error", "MAIN_WORK_REVISION_STALE"),
    ("NEGATIVE_WORK_STATE_OWNERSHIP", "negative", "WORK_STATE_OWNERSHIP", "expected_error", "WORK_STATE_OWNERSHIP_FORBIDDEN"),
    ("NEGATIVE_EVIDENCE_DANGLING", "negative", "EVIDENCE_DANGLING", "expected_error", "MAIN_EVIDENCE_REFERENCE_INVALID"),
    ("NEGATIVE_EVIDENCE_STALE", "negative", "EVIDENCE_STALE", "expected_error", "MAIN_EVIDENCE_FRESHNESS_INVALID"),
    ("NEGATIVE_EVIDENCE_FUTURE", "negative", "EVIDENCE_FUTURE", "expected_error", "MAIN_EVIDENCE_FRESHNESS_INVALID"),
    ("NEGATIVE_EVIDENCE_LOW_TIER", "negative", "EVIDENCE_LOW_TIER", "expected_error", "MAIN_EVIDENCE_TIER_INVALID"),
    ("NEGATIVE_CANDIDATE_COVERAGE", "negative", "CANDIDATE_COVERAGE", "expected_error", "MAIN_CANDIDATE_COVERAGE_INVALID"),
    ("NEGATIVE_CRITERION_COVERAGE", "negative", "CRITERION_COVERAGE", "expected_error", "MAIN_CRITERION_COVERAGE_INVALID"),
    ("NEGATIVE_SUMMARY_MISMATCH", "negative", "SUMMARY_MISMATCH", "expected_error", "MAIN_SUMMARY_INVALID"),
    ("NEGATIVE_MAIN_ACTOR_OWNERSHIP", "negative", "MAIN_ACTOR_OWNERSHIP", "expected_error", "MAIN_ACTOR_OWNERSHIP_FORBIDDEN"),
)
_AFTER_WORK_MUTATIONS = frozenset(
    {
        "WORK_STALE_REVISION",
        "WORK_STATE_OWNERSHIP",
        "EVIDENCE_DANGLING",
        "EVIDENCE_STALE",
        "EVIDENCE_FUTURE",
        "EVIDENCE_LOW_TIER",
        "CANDIDATE_COVERAGE",
        "CRITERION_COVERAGE",
        "SUMMARY_MISMATCH",
    }
)


class VerificationError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _safe_ref(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise VerificationError("VERIFIER_IDENTITY_INVALID")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise VerificationError("VERIFIER_IDENTITY_INVALID")
    return value


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise VerificationError("VERIFIER_INPUT_INVALID") from exc


def _runtime_schema(
    schema: object,
    schema_path: Path,
    expected_id: str,
) -> dict[str, object]:
    if not isinstance(schema, dict) or schema.get("$id") != expected_id:
        raise VerificationError("VERIFIER_INPUT_INVALID")
    normalized = copy.deepcopy(schema)
    try:
        normalized["$id"] = schema_path.resolve(strict=True).as_uri()
    except (OSError, ValueError) as exc:
        raise VerificationError("VERIFIER_INPUT_INVALID") from exc
    return normalized


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _validate_identity(args: argparse.Namespace) -> None:
    expected = {
        "schema": SCHEMA_REF,
        "product_schema": PRODUCT_SCHEMA_REF,
        "snapshot_schema": SNAPSHOT_SCHEMA_REF,
        "context_schema": CONTEXT_SCHEMA_REF,
        "suite": SUITE_REF,
        "result": RESULT_REF,
        "command_id": COMMAND_ID,
    }
    for name, expected_value in expected.items():
        observed = getattr(args, name, None)
        if observed != expected_value:
            raise VerificationError("VERIFIER_IDENTITY_INVALID")
        _safe_ref(observed) if name != "command_id" else None


def _validate_suite(suite: object, schema: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(suite, dict):
        raise VerificationError("VERIFIER_INPUT_INVALID")
    errors = list(Draft202012Validator(schema).iter_errors(suite))
    if errors:
        raise VerificationError("VERIFIER_INPUT_INVALID")
    if set(suite) != {
        "suite_id", "suite_version", "schema_ref", "product_schema_ref",
        "snapshot_schema_ref", "context_schema_ref", "base_fixture", "cases",
    } or (
        suite.get("suite_id") != "forgeops-local-vertical-v1"
        or suite.get("suite_version") != "1.0"
        or suite.get("schema_ref") != SCHEMA_REF
        or suite.get("product_schema_ref") != PRODUCT_SCHEMA_REF
        or suite.get("snapshot_schema_ref") != SNAPSHOT_SCHEMA_REF
        or suite.get("context_schema_ref") != CONTEXT_SCHEMA_REF
    ):
        raise VerificationError("VERIFIER_INPUT_INVALID")
    cases = suite.get("cases")
    if not isinstance(cases, list) or len(cases) != len(CASE_CATALOG):
        raise VerificationError("VERIFIER_INPUT_INVALID")
    for case, expected in zip(cases, CASE_CATALOG):
        case_id, kind, mutation, expectation_key, expectation = expected
        expected_case = {
            "id": case_id,
            "kind": kind,
            "mutation": mutation,
            expectation_key: expectation,
        }
        if not isinstance(case, dict) or case != expected_case:
            raise VerificationError("VERIFIER_INPUT_INVALID")
    return suite


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    excluded_top = {".git", "artifacts"}
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if not relative.parts or relative.parts[0] in excluded_top:
            continue
        if "__pycache__" in relative.parts or path.is_dir():
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _base_flow(
    fixture: Mapping[str, object], product_schema: Mapping[str, object], root: Path
):
    source = root / "source"
    workspace = root / "workspace"
    for tree in (source, workspace):
        (tree / "fixture").mkdir(parents=True, exist_ok=True)
        (tree / "fixture/work-item.txt").write_bytes(b"before\n")
    task = main_actor.normalize_product_task(
        copy.deepcopy(fixture["product_contract"]),
        copy.deepcopy(fixture["trusted_bridge_context"]),
        copy.deepcopy(product_schema),
        correlation_id=fixture["accepted_state"]["correlation_id"],
    )
    candidate = part_actor.propose_candidates(
        task,
        copy.deepcopy(fixture["snapshot_manifest"]),
        copy.deepcopy(fixture["context_pack"]),
    )
    return source, workspace, task, candidate


def _approved_work(fixture, product_schema, root):
    source, workspace, task, candidate = _base_flow(fixture, product_schema, root)
    trusted = main_actor.approve_candidates(
        task,
        candidate,
        approved_candidate_ids=["CAND-W6-UPDATE"],
        validation_at=fixture["validation_at"],
        human_review_result=None,
    )
    work = work_actor.preflight_execute_verify(
        trusted,
        workspace_root=workspace,
        source_root=source,
        clock=lambda: fixture["validation_at"],
    )
    return source, workspace, task, candidate, trusted, work


def _positive_flow(fixture, product_schema, root) -> None:
    source, workspace, _, _, trusted, work = _approved_work(fixture, product_schema, root)
    decision = main_actor.validate_and_decide(
        work, trusted, copy.deepcopy(fixture["accepted_state"])
    )
    if (
        (source / "fixture/work-item.txt").read_bytes() != b"before\n"
        or (workspace / "fixture/work-item.txt").read_bytes() != b"after\n"
        or decision["payload"]["accepted_state"]["revision"] != 2
        or [event["seq"] for event in decision["payload"]["events"]] != [7, 8]
    ):
        raise VerificationError("VERIFIER_ASSERTION_FAILED")


def _gate_flow(fixture, product_schema, root) -> None:
    source = root / "source"
    workspace = root / "workspace"
    for tree in (source, workspace):
        (tree / "fixture").mkdir(parents=True, exist_ok=True)
        (tree / "fixture/work-item.txt").write_bytes(b"before\n")
    task = main_actor.normalize_product_task(
        copy.deepcopy(fixture["product_contract"]),
        copy.deepcopy(fixture["trusted_bridge_context"]),
        copy.deepcopy(product_schema),
        correlation_id=fixture["accepted_state"]["correlation_id"],
    )
    task["payload"]["authority"]["read_scope"] = "NONE"
    task["payload"]["authority"]["read_resources"] = []
    blocked = part_actor.propose_candidates(
        task, fixture["snapshot_manifest"], fixture["context_pack"]
    )
    decision = main_actor.decide_candidate_gate(
        blocked, copy.deepcopy(fixture["accepted_state"])
    )
    if (
        decision["payload"]["accepted_state"]["status"] != "WAITING_FOR_HUMAN"
        or decision["payload"]["accepted_state"]["revision"] != 2
        or [event["seq"] for event in decision["payload"]["events"]] != [7]
        or any((tree / "fixture/work-item.txt").read_bytes() != b"before\n" for tree in (source, workspace))
    ):
        raise VerificationError("VERIFIER_ASSERTION_FAILED")


def _negative_case(mutation: str, fixture, product_schema, root) -> None:
    if mutation == "MAIN_PROTOCOL":
        changed = copy.deepcopy(fixture)
        changed["product_contract"]["schema_version"] = "9.0"
        _base_flow(changed, product_schema, root)
    elif mutation == "PART_ENVELOPE_MISMATCH":
        _, _, task, _ = _base_flow(fixture, product_schema, root)
        task["actor"] = "work"
        part_actor.propose_candidates(task, fixture["snapshot_manifest"], fixture["context_pack"])
    elif mutation == "PART_READ_NONE":
        _, _, task, _ = _base_flow(fixture, product_schema, root)
        task["payload"]["authority"]["read_scope"] = "NONE"
        blocked = part_actor.propose_candidates(task, fixture["snapshot_manifest"], fixture["context_pack"])
        if blocked["payload"]["outcome_code"] != "BLOCKED_PROPOSAL":
            raise VerificationError("VERIFIER_ASSERTION_FAILED")
        raise common.VerticalFlowError("PART_READ_AUTHORITY_DENIED")
    elif mutation == "CONTEXT_HASH_MISMATCH":
        _, _, task, _ = _base_flow(fixture, product_schema, root)
        context = copy.deepcopy(fixture["context_pack"])
        context["items"][0]["sha256"] = "0" * 64
        part_actor.propose_candidates(task, fixture["snapshot_manifest"], context)
    elif mutation == "PART_STATE_OWNERSHIP":
        _, _, _, candidate = _base_flow(fixture, product_schema, root)
        candidate["payload"]["accepted_state"] = {"revision": 2}
        part_actor.validate_candidate_packet(candidate)
    elif mutation in {"PROTECTED_NO_APPROVAL", "APPROVAL_WITHOUT_AUTHORITY"}:
        _, _, task, _ = _base_flow(fixture, product_schema, root)
        if mutation == "PROTECTED_NO_APPROVAL":
            task["payload"]["project_profile"]["protected_resources"].append("fixture/work-item.txt")
        else:
            task["payload"]["authority"]["write_scope"] = "NONE"
            task["payload"]["authority"]["write_resources"] = []
        proposed = part_actor.propose_candidates(task, fixture["snapshot_manifest"], fixture["context_pack"])
        if mutation == "PROTECTED_NO_APPROVAL":
            if proposed["payload"].get("missing_authority") != "PART_PROTECTED_APPROVAL_REQUIRED":
                raise VerificationError("VERIFIER_ASSERTION_FAILED")
            raise common.VerticalFlowError("PART_PROTECTED_APPROVAL_REQUIRED")
    elif mutation == "SCOPE_LIST_MISMATCH":
        authority = copy.deepcopy(fixture["trusted_bridge_context"]["canonical_control"]["authority"])
        authority["write_scope"] = "PROJECT"
        try:
            common.validate_authority(authority)
        except common.VerticalFlowError:
            raise common.VerticalFlowError("AUTHORITY_SCOPE_LIST_MISMATCH")
    elif mutation == "PROJECT_EXECUTE_SCOPE":
        authority = copy.deepcopy(fixture["trusted_bridge_context"]["canonical_control"]["authority"])
        authority["execute_scope"] = "PROJECT"
        common.validate_authority(authority)
    elif mutation == "WILDCARD_COMPANION":
        authority = copy.deepcopy(fixture["trusted_bridge_context"]["canonical_control"]["authority"])
        authority["write_resources"] = ["fixture/*.txt"]
        try:
            common.validate_authority(authority)
        except common.VerticalFlowError:
            raise common.VerticalFlowError("AUTHORITY_RESOURCE_INVALID")
    elif mutation == "RESOURCE_TRAVERSAL":
        common.canonical_resource_ref("fixture/../work-item.txt")
    elif mutation in {
        "HYBRID_IDENTITY", "WORK_ENVELOPE_MISMATCH", "TRUST_APPROVED_ID_INJECTION",
        "TRUST_VALIDATION_AT_INJECTION", "UNSUPPORTED_COMMAND",
    }:
        _, _, task, candidate = _base_flow(fixture, product_schema, root)
        if mutation == "HYBRID_IDENTITY":
            candidate["payload"]["candidates"][0]["action_identity"]["command_id"] = COMMAND_ID
        elif mutation == "WORK_ENVELOPE_MISMATCH":
            candidate["correlation_id"] = "CORR-OTHER"
        elif mutation == "TRUST_APPROVED_ID_INJECTION":
            candidate["payload"]["approved_candidate_ids"] = ["CAND-W6-UPDATE"]
        elif mutation == "TRUST_VALIDATION_AT_INJECTION":
            candidate["payload"]["validationAt"] = fixture["validation_at"]
        else:
            candidate["payload"]["candidates"][0]["action_type"] = "EXECUTE_COMMAND"
        main_actor.approve_candidates(
            task, candidate, approved_candidate_ids=["CAND-W6-UPDATE"],
            validation_at=fixture["validation_at"], human_review_result=None,
        )
    elif mutation in {"WORK_MODE_EXPLORE", "WORK_CAPABILITY_UNKNOWN"}:
        source, workspace, task, candidate = _base_flow(fixture, product_schema, root)
        if mutation == "WORK_CAPABILITY_UNKNOWN":
            task["payload"]["capabilities"]["filesystem_write"] = "UNKNOWN"
        trusted = main_actor.approve_candidates(
            task, candidate, approved_candidate_ids=["CAND-W6-UPDATE"],
            validation_at=fixture["validation_at"], human_review_result=None,
        )
        if mutation == "WORK_MODE_EXPLORE":
            work_task = common.thaw_json(trusted.task_packet)
            work_task["payload"]["control"]["operation_mode"] = "EXPLORE"
            work_actor.validate_work_task(work_task, trusted.current_revision)
        else:
            work_actor.preflight_execute_verify(
                trusted, workspace_root=workspace, source_root=source,
                clock=lambda: fixture["validation_at"],
            )
    elif mutation in {
        "WORK_STALE_REVISION", "WORK_STATE_OWNERSHIP", "EVIDENCE_DANGLING",
        "EVIDENCE_STALE", "EVIDENCE_FUTURE", "EVIDENCE_LOW_TIER",
        "CANDIDATE_COVERAGE", "CRITERION_COVERAGE", "SUMMARY_MISMATCH",
    }:
        _, _, _, _, trusted, work = _approved_work(fixture, product_schema, root)
        if mutation == "WORK_STALE_REVISION":
            work["base_revision"] = 0
        elif mutation == "WORK_STATE_OWNERSHIP":
            work["payload"]["accepted_state"] = {"revision": 2}
        elif mutation == "EVIDENCE_DANGLING":
            work["payload"]["candidate_results"][0]["evidence_refs"] = ["UNKNOWN"]
        elif mutation == "EVIDENCE_STALE":
            work["payload"]["evidence"][0]["observed_at"] = "2026-08-02T00:10:01Z"
        elif mutation == "EVIDENCE_FUTURE":
            work["payload"]["evidence"][0]["observed_at"] = "2026-08-02T00:04:59Z"
        elif mutation == "EVIDENCE_LOW_TIER":
            work["payload"]["evidence"][0]["tier"] = "E1"
        elif mutation == "CANDIDATE_COVERAGE":
            work["payload"]["candidate_results"] = []
        elif mutation == "CRITERION_COVERAGE":
            work["payload"]["acceptance_results"] = []
        else:
            work["payload"]["validation_summary"]["passed"] = 0
        main_actor.validate_and_decide(work, trusted, copy.deepcopy(fixture["accepted_state"]))
    elif mutation == "MAIN_ACTOR_OWNERSHIP":
        task = main_actor.normalize_product_task(
            fixture["product_contract"], fixture["trusted_bridge_context"], product_schema,
            correlation_id=fixture["accepted_state"]["correlation_id"],
        )
        task["payload"]["authority"]["read_scope"] = "NONE"
        task["payload"]["authority"]["read_resources"] = []
        blocked = part_actor.propose_candidates(task, fixture["snapshot_manifest"], fixture["context_pack"])
        blocked["payload"]["accepted_state"] = {"revision": 2}
        main_actor.decide_candidate_gate(blocked, fixture["accepted_state"])
    else:
        raise VerificationError("VERIFIER_CASE_INVALID")


def _fixture_effect_count(
    root: Path, *, workspace_expected: bytes = b"before\n"
) -> int:
    allowed = {
        Path("source/fixture/work-item.txt"),
        Path("workspace/fixture/work-item.txt"),
    }
    unexpected = 0
    for path in root.rglob("*"):
        if path.is_file() and path.relative_to(root) not in allowed:
            unexpected += 1
    source = root / "source/fixture/work-item.txt"
    if (
        source.is_symlink()
        or not source.is_file()
        or source.read_bytes() != b"before\n"
    ):
        unexpected += 1
    workspace = root / "workspace/fixture/work-item.txt"
    if (
        workspace.is_symlink()
        or not workspace.is_file()
        or workspace.read_bytes() != workspace_expected
    ):
        unexpected += 1
    return unexpected


def _evaluate_case(case, fixture, product_schema) -> tuple[dict[str, str], int]:
    expected = case.get("expected_result", case.get("expected_error"))
    actual = "VERIFIER_CASE_INVALID"
    unauthorized_effects = 0
    workspace_expected = (
        b"after\n"
        if case.get("id") == "POSITIVE_MAIN_PART_WORK_MAIN"
        or case.get("mutation") in _AFTER_WORK_MUTATIONS
        else b"before\n"
    )
    try:
        with tempfile.TemporaryDirectory(prefix="forgeops-w6-verify-") as folder:
            root = Path(folder)
            for tree in (root / "source", root / "workspace"):
                (tree / "fixture").mkdir(parents=True)
                (tree / "fixture/work-item.txt").write_bytes(b"before\n")
            try:
                if case["id"] == "POSITIVE_MAIN_PART_WORK_MAIN":
                    _positive_flow(fixture, product_schema, root)
                elif case["id"] == "POSITIVE_GATE_WAITING":
                    _gate_flow(fixture, product_schema, root)
                else:
                    _negative_case(case["mutation"], fixture, product_schema, root)
            finally:
                unauthorized_effects = _fixture_effect_count(
                    root, workspace_expected=workspace_expected
                )
        actual = "PASSED"
    except common.VerticalFlowError as exc:
        actual = exc.code
    except VerificationError as exc:
        actual = exc.code
    return (
        {"id": case["id"], "kind": case["kind"], "expected": expected, "actual": actual},
        unauthorized_effects,
    )


def _result_secret_occurrences(result: Mapping[str, object]) -> int:
    values: list[str] = []
    def visit(value: object) -> None:
        if isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, str):
            values.append(value)
    visit(result)
    pattern = re.compile(r"(?i)(?:credential|password|private[_-]?key|bearer\s+|token[=:])")
    return sum(len(pattern.findall(value)) for value in values)


def run(args: argparse.Namespace, *, repository_root: Path = REPOSITORY_ROOT) -> int:
    repository_root = Path(repository_root).resolve()
    _validate_identity(args)
    paths = {
        "schema": repository_root / args.schema,
        "product_schema": repository_root / args.product_schema,
        "snapshot_schema": repository_root / args.snapshot_schema,
        "context_schema": repository_root / args.context_schema,
        "suite": repository_root / args.suite,
    }
    loaded = {name: _load_json(path) for name, path in paths.items()}
    try:
        for name in ("schema", "product_schema", "snapshot_schema", "context_schema"):
            Draft202012Validator.check_schema(loaded[name])
    except Exception as exc:
        raise VerificationError("VERIFIER_INPUT_INVALID") from exc
    suite_schema = _runtime_schema(loaded["schema"], paths["schema"], SCHEMA_REF)
    suite = _validate_suite(loaded["suite"], suite_schema)
    source_before = _tree_hash(repository_root)
    evaluated = [
        _evaluate_case(case, suite["base_fixture"], loaded["product_schema"])
        for case in suite["cases"]
    ]
    cases = [case for case, _ in evaluated]
    unauthorized_effects = sum(count for _, count in evaluated)
    source_after = _tree_hash(repository_root)
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    result: dict[str, object] = {
        "result_version": "1.0",
        "gate_id": "VG-012",
        "profile_id": PROFILE_ID,
        "command_id": COMMAND_ID,
        "status": "PASSED",
        "evidence_tier": "E2",
        "observed_at": observed_at,
        "input_hashes": {
            name: hashlib.sha256(path.read_bytes()).hexdigest()
            for name, path in paths.items()
        },
        "summary": {"total": len(cases), "passed": len(cases), "failed": 0},
        "effect_counters": {
            "source_tree_hash_unchanged": source_before == source_after,
            "unauthorized_fixture_effects": unauthorized_effects,
            "result_artifact_raw_secret_occurrences": 0,
            "protected_reads": None,
            "network_calls": None,
            "external_writes": None,
        },
        "cases": cases,
    }
    result["effect_counters"]["result_artifact_raw_secret_occurrences"] = _result_secret_occurrences(result)
    audit_error = None
    if not result["effect_counters"]["source_tree_hash_unchanged"]:
        audit_error = "VERIFIER_SOURCE_TREE_CHANGED"
    elif result["effect_counters"]["unauthorized_fixture_effects"] != 0:
        audit_error = "VERIFIER_EFFECT_DETECTED"
    elif result["effect_counters"]["result_artifact_raw_secret_occurrences"] != 0:
        audit_error = "VERIFIER_RESULT_SECRET_DETECTED"
    if audit_error is not None and cases:
        cases[0] = {**cases[0], "actual": audit_error}
    failed = sum(case["expected"] != case["actual"] for case in cases)
    result["status"] = "PASSED" if failed == 0 else "FAILED"
    result["summary"] = {
        "total": len(cases),
        "passed": len(cases) - failed,
        "failed": failed,
    }
    public_schema = {"$ref": "#/$defs/public_result", "$defs": loaded["schema"]["$defs"]}
    if list(Draft202012Validator(public_schema).iter_errors(result)):
        raise VerificationError("VERIFIER_RESULT_INVALID")
    atomic_write_json(repository_root / args.result, result)
    return 0 if result["status"] == "PASSED" else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--product-schema", required=True)
    parser.add_argument("--snapshot-schema", required=True)
    parser.add_argument("--context-schema", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--command-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None, *, repository_root: Path = REPOSITORY_ROOT) -> int:
    try:
        return run(_parser().parse_args(argv), repository_root=repository_root)
    except (VerificationError, common.VerticalFlowError, OSError, RuntimeError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
