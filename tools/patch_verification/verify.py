"""Registered E2 verifier for ForgeOps W7 bounded patch verification."""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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

from tools.patch_verification.anti_tamper import build_guard_manifest, verify_guard_manifest
from tools.patch_verification.model import EffectAudit, PatchVerificationError, atomic_write_json
from tools.patch_verification.patch import apply_bounded_patch, materialize_fixture
from tools.patch_verification.profiles import (
    TRUSTED_PROFILE,
    TRUSTED_PROFILE_DIGEST,
    compare_baseline_and_changed,
    run_trusted_profile,
)


SCHEMA_REF = "contracts/forgeops-patch-verification/1.0/schema.json"
SUITE_REF = "fixtures/forgeops-patch-verification/suite.json"
PROFILE_SOURCE_REF = "tools/patch_verification/profiles.py"
PROFILE_ID = "forgeops-patch-verification"
TRUSTED_COMMANDS = {
    "task-checks": "artifacts/verification/vg-013-task-checks-result.json",
    "regression-checks": "artifacts/verification/vg-013-regression-checks-result.json",
    "verification-anti-tamper": "artifacts/verification/vg-013-verification-anti-tamper-result.json",
}

CASE_EXPECTATIONS = {
    "POSITIVE_BOUNDED_PATCH": "PASSED",
    "NEGATIVE_ABSOLUTE_RESOURCE": "PATCH_RESOURCE_INVALID",
    "NEGATIVE_TRAVERSAL_RESOURCE": "PATCH_RESOURCE_INVALID",
    "NEGATIVE_UNKNOWN_RESOURCE": "PATCH_RESOURCE_UNAUTHORIZED",
    "NEGATIVE_BEFORE_HASH_MISMATCH": "PATCH_BASE_MISMATCH",
    "NEGATIVE_SOURCE_AS_WORKSPACE": "PATCH_CONTAINMENT_VIOLATION",
    "NEGATIVE_WORKSPACE_SYMLINK_ESCAPE": "PATCH_CONTAINMENT_VIOLATION",
    "NEGATIVE_DIFF_LIMIT": "PATCH_DIFF_LIMIT_EXCEEDED",
    "NEGATIVE_RAW_PATCH_INPUT": "PATCH_INPUT_INVALID",
    "POSITIVE_TRUSTED_CHECKS": "PASSED",
    "NEGATIVE_TASK_CHECK_FAILURE": "TASK_CHECK_FAILED",
    "NEGATIVE_NEW_REGRESSION": "NEW_REGRESSION",
    "NEGATIVE_BASELINE_UNHEALTHY": "BASELINE_UNHEALTHY",
    "NEGATIVE_LINT_FAILURE": "LINT_FAILED",
    "NEGATIVE_TYPECHECK_FAILURE": "TYPECHECK_FAILED",
    "NEGATIVE_UNKNOWN_PROFILE": "PROFILE_IDENTITY_INVALID",
    "NEGATIVE_PROFILE_DIGEST_MISMATCH": "PROFILE_DIGEST_INVALID",
    "NEGATIVE_STALE_EVIDENCE": "EVIDENCE_FRESHNESS_INVALID",
    "POSITIVE_GUARDS_UNCHANGED": "PASSED",
    "NEGATIVE_TEST_DELETE": "TEST_DELETED",
    "NEGATIVE_SKIP_INJECTION": "TEST_SKIP_INJECTED",
    "NEGATIVE_XFAIL_INJECTION": "TEST_XFAIL_INJECTED",
    "NEGATIVE_ASSERTION_WEAKEN": "ASSERTION_WEAKENED",
    "NEGATIVE_COVERAGE_EXCLUSION": "COVERAGE_POLICY_CHANGED",
    "NEGATIVE_PROFILE_CHANGE": "VERIFICATION_PROFILE_CHANGED",
    "NEGATIVE_TEST_SYMLINK": "TEST_PATH_INVALID",
    "NEGATIVE_TEST_RENAME": "TEST_PATH_INVALID",
}


class VerificationError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class CaseAudit:
    unauthorized_workspace_effects: int = 0
    outside_workspace_write_attempts: int = 0
    remote_write_attempts: int = 0


def _strict_ref(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise VerificationError("VERIFIER_IDENTITY_INVALID")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise VerificationError("VERIFIER_IDENTITY_INVALID")
    return value


def _validate_identity(args: argparse.Namespace) -> None:
    if args.command_id not in TRUSTED_COMMANDS:
        raise VerificationError("VERIFIER_IDENTITY_INVALID")
    expected = {
        "schema": SCHEMA_REF,
        "suite": SUITE_REF,
        "result": TRUSTED_COMMANDS[args.command_id],
    }
    for name, value in expected.items():
        observed = getattr(args, name, None)
        if observed != value:
            raise VerificationError("VERIFIER_IDENTITY_INVALID")
        _strict_ref(observed)


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise VerificationError("VERIFIER_INPUT_INVALID") from error


def _validate_suite(value: object, schema: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, dict) or list(Draft202012Validator(schema).iter_errors(value)):
        raise VerificationError("VERIFIER_INPUT_INVALID")
    cases = value.get("cases")
    if not isinstance(cases, list) or len(cases) != len(CASE_EXPECTATIONS):
        raise VerificationError("VERIFIER_INPUT_INVALID")
    if tuple(case.get("id") for case in cases if isinstance(case, dict)) != tuple(CASE_EXPECTATIONS):
        raise VerificationError("VERIFIER_INPUT_INVALID")
    for case in cases:
        expected = CASE_EXPECTATIONS[case["id"]]
        expected_key = "expected_result" if case["kind"] == "positive" else "expected_error"
        if case["mutation"] != case["id"] or case.get(expected_key) != expected:
            raise VerificationError("VERIFIER_INPUT_INVALID")
    return value


def _repository_tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if not relative.parts or relative.parts[0] in {".git", "artifacts"} or "__pycache__" in relative.parts:
            continue
        if not path.is_file() or path.is_symlink():
            continue
        content = path.read_bytes()
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
    return digest.hexdigest()


def _write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8", newline="\n")


def _try_symlink_or_alias(target: Path, real: Path) -> bool:
    target.replace(real)
    try:
        target.symlink_to(real)
        return True
    except OSError:
        real.replace(target)
        return False


def _evaluate_patch(case_id: str, fixture: Mapping[str, object]) -> CaseAudit:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        source = base / "source"
        workspace = base / "workspace"
        materialize_fixture(source, fixture["files"])
        materialize_fixture(workspace, fixture["files"])
        intent = copy.deepcopy(fixture["patch_intent"])
        selected_source = source
        selected_workspace = workspace
        if case_id == "NEGATIVE_ABSOLUTE_RESOURCE":
            intent["resource_ref"] = "C:/outside.py"
        elif case_id == "NEGATIVE_TRAVERSAL_RESOURCE":
            intent["resource_ref"] = "../outside.py"
        elif case_id == "NEGATIVE_UNKNOWN_RESOURCE":
            intent["resource_ref"] = "src/other.py"
        elif case_id == "NEGATIVE_BEFORE_HASH_MISMATCH":
            intent["before_sha256"] = "0" * 64
        elif case_id == "NEGATIVE_SOURCE_AS_WORKSPACE":
            selected_workspace = source
        elif case_id == "NEGATIVE_WORKSPACE_SYMLINK_ESCAPE":
            target = workspace / "src/calculator.py"
            real = workspace / "src/real_calculator.py"
            if not _try_symlink_or_alias(target, real):
                selected_workspace = source
        elif case_id == "NEGATIVE_DIFF_LIMIT":
            intent["max_diff_bytes"] = 1
        elif case_id == "NEGATIVE_RAW_PATCH_INPUT":
            intent["raw_patch"] = "--- a/raw"
        audit = EffectAudit()
        apply_bounded_patch(selected_source, selected_workspace, intent, audit=audit)
        return CaseAudit(
            outside_workspace_write_attempts=audit.outside_workspace_write_attempts,
            remote_write_attempts=audit.remote_write_attempts,
        )


def _profile_args(observed_at: str, phase: str) -> dict[str, object]:
    return {
        "profile_id": TRUSTED_PROFILE["profile_id"],
        "profile_digest": TRUSTED_PROFILE_DIGEST,
        "observed_at": observed_at,
        "validation_at": observed_at,
        "phase": phase,
    }


def _evaluate_regression(case_id: str, fixture: Mapping[str, object], observed_at: str) -> CaseAudit:
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        source = base / "source"
        changed = base / "changed"
        materialize_fixture(source, fixture["files"])
        materialize_fixture(changed, fixture["files"])
        if case_id == "NEGATIVE_BASELINE_UNHEALTHY":
            path = source / "src/calculator.py"
            _write_text(path, path.read_text(encoding="utf-8").replace("return value", "return value + 1"))
            baseline = run_trusted_profile(source, **_profile_args(observed_at, "baseline"))
            compare_baseline_and_changed(baseline, baseline)
            return CaseAudit()
        baseline = run_trusted_profile(source, **_profile_args(observed_at, "baseline"))
        patch_audit = EffectAudit()
        apply_bounded_patch(source, changed, fixture["patch_intent"], audit=patch_audit)
        if case_id == "NEGATIVE_TASK_CHECK_FAILURE":
            path = changed / "src/calculator.py"
            _write_text(path, path.read_text(encoding="utf-8").replace("return left + right", "return left - right"))
        elif case_id == "NEGATIVE_NEW_REGRESSION":
            path = changed / "src/calculator.py"
            _write_text(path, path.read_text(encoding="utf-8").replace("return value", "return value + 1"))
        elif case_id == "NEGATIVE_LINT_FAILURE":
            path = changed / "src/calculator.py"
            _write_text(path, path.read_text(encoding="utf-8").replace("return value\n", "return value  \n"))
        elif case_id == "NEGATIVE_TYPECHECK_FAILURE":
            path = changed / "src/calculator.py"
            _write_text(path, path.read_text(encoding="utf-8").replace("left: int", "left"))
        arguments = _profile_args(observed_at, "changed")
        if case_id == "NEGATIVE_UNKNOWN_PROFILE":
            arguments["profile_id"] = "unknown"
        elif case_id == "NEGATIVE_PROFILE_DIGEST_MISMATCH":
            arguments["profile_digest"] = "0" * 64
        elif case_id == "NEGATIVE_STALE_EVIDENCE":
            anchor = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            arguments["observed_at"] = (anchor + timedelta(seconds=301)).isoformat().replace("+00:00", "Z")
        changed_result = run_trusted_profile(changed, **arguments)
        compare_baseline_and_changed(baseline, changed_result)
        return CaseAudit(
            outside_workspace_write_attempts=patch_audit.outside_workspace_write_attempts,
            remote_write_attempts=patch_audit.remote_write_attempts,
        )


def _evaluate_guard(case_id: str, fixture: Mapping[str, object]) -> CaseAudit:
    with tempfile.TemporaryDirectory() as temporary:
        workspace = Path(temporary) / "workspace"
        materialize_fixture(workspace, fixture["files"])
        manifest = build_guard_manifest(workspace, TRUSTED_PROFILE_DIGEST)
        test_path = workspace / "tests/test_calculator.py"
        if case_id == "NEGATIVE_TEST_DELETE":
            test_path.unlink()
        elif case_id == "NEGATIVE_SKIP_INJECTION":
            text = test_path.read_text(encoding="utf-8").replace("    def test_total_matches_task", "    @unittest.skip('disabled')\n    def test_total_matches_task")
            _write_text(test_path, text)
        elif case_id == "NEGATIVE_XFAIL_INJECTION":
            text = test_path.read_text(encoding="utf-8").replace("    def test_total_matches_task", "    @unittest.expectedFailure\n    def test_total_matches_task")
            _write_text(test_path, text)
        elif case_id == "NEGATIVE_ASSERTION_WEAKEN":
            text = test_path.read_text(encoding="utf-8").replace("self.assertEqual(5, total(2, 3))", "self.assertTrue(True)")
            _write_text(test_path, text)
        elif case_id == "NEGATIVE_COVERAGE_EXCLUSION":
            coverage = workspace / ".coveragerc"
            _write_text(coverage, coverage.read_text(encoding="utf-8") + "    src/calculator.py\n")
        elif case_id == "NEGATIVE_PROFILE_CHANGE":
            _write_text(workspace / "verification-profile.json", '{"profile_id":"other","checks":[]}\n')
        elif case_id == "NEGATIVE_TEST_SYMLINK":
            real = workspace / "tests/real.py"
            if not _try_symlink_or_alias(test_path, real):
                test_path.replace(workspace / "tests/test_alias.py")
        elif case_id == "NEGATIVE_TEST_RENAME":
            test_path.replace(workspace / "tests/test_renamed.py")
        verify_guard_manifest(workspace, manifest, trusted_profile_digest=TRUSTED_PROFILE_DIGEST)
        return CaseAudit()


def _evaluate_case(
    case: Mapping[str, object], fixture: Mapping[str, object], observed_at: str
) -> tuple[dict[str, str], CaseAudit]:
    expected = case.get("expected_result", case.get("expected_error"))
    actual = "PASSED"
    audit = CaseAudit()
    try:
        if case["command_id"] == "task-checks":
            audit = _evaluate_patch(case["id"], fixture)
        elif case["command_id"] == "regression-checks":
            audit = _evaluate_regression(case["id"], fixture, observed_at)
        else:
            audit = _evaluate_guard(case["id"], fixture)
    except PatchVerificationError as error:
        actual = error.code
    return {
        "id": case["id"],
        "kind": case["kind"],
        "expected": expected,
        "actual": actual,
    }, audit


def _secret_occurrences(value: object) -> int:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    assignment = re.compile(r"(?i)(?:token|secret|password|credential|api[_-]?key|access[_-]?token)\s*[=:]")
    absolute = re.compile(r"(?:[A-Za-z]:[\\/]|/(?:tmp|home|Users)/)")
    return len(assignment.findall(serialized)) + len(absolute.findall(serialized))


def _effect_counters(
    source_unchanged: bool, audits: Sequence[CaseAudit], result_basis: object
) -> dict[str, object]:
    return {
        "source_tree_hash_unchanged": source_unchanged,
        "unauthorized_workspace_effects": sum(item.unauthorized_workspace_effects for item in audits),
        "outside_workspace_write_attempts": sum(item.outside_workspace_write_attempts for item in audits),
        "remote_write_attempts": sum(item.remote_write_attempts for item in audits),
        "result_artifact_raw_secret_occurrences": _secret_occurrences(result_basis),
        "host_external_writes": None,
        "network_calls": None,
    }


def run(args: argparse.Namespace, *, repository_root: Path = REPOSITORY_ROOT) -> int:
    repository_root = Path(repository_root).resolve()
    _validate_identity(args)
    schema_path = repository_root / args.schema
    suite_path = repository_root / args.suite
    profile_path = repository_root / PROFILE_SOURCE_REF
    schema = _load_json(schema_path)
    suite_value = _load_json(suite_path)
    if not isinstance(schema, dict):
        raise VerificationError("VERIFIER_INPUT_INVALID")
    try:
        Draft202012Validator.check_schema(schema)
    except Exception as error:
        raise VerificationError("VERIFIER_INPUT_INVALID") from error
    suite = _validate_suite(suite_value, schema)
    if not profile_path.is_file():
        raise VerificationError("VERIFIER_INPUT_INVALID")
    source_before = _repository_tree_hash(repository_root)
    observed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    selected = [case for case in suite["cases"] if case["command_id"] == args.command_id]
    evaluated = [_evaluate_case(case, suite["base_fixture"], observed_at) for case in selected]
    cases = [item[0] for item in evaluated]
    audits = [item[1] for item in evaluated]
    source_after = _repository_tree_hash(repository_root)
    basis = {"command_id": args.command_id, "cases": cases}
    counters = _effect_counters(source_before == source_after, audits, basis)
    unsafe = (
        not counters["source_tree_hash_unchanged"]
        or counters["unauthorized_workspace_effects"] != 0
        or counters["outside_workspace_write_attempts"] != 0
        or counters["remote_write_attempts"] != 0
        or counters["result_artifact_raw_secret_occurrences"] != 0
    )
    if unsafe and cases:
        cases[0] = {**cases[0], "actual": "VERIFIER_AUDIT_FAILED"}
    failed = sum(item["expected"] != item["actual"] for item in cases)
    result = {
        "result_version": "1.0",
        "gate_id": "VG-013",
        "profile_id": PROFILE_ID,
        "command_id": args.command_id,
        "status": "PASSED" if failed == 0 else "FAILED",
        "evidence_tier": "E2",
        "observed_at": observed_at,
        "input_hashes": {
            "schema": hashlib.sha256(schema_path.read_bytes()).hexdigest(),
            "suite": hashlib.sha256(suite_path.read_bytes()).hexdigest(),
            "profile_source": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        },
        "profile_digest": TRUSTED_PROFILE_DIGEST,
        "summary": {"total": len(cases), "passed": len(cases) - failed, "failed": failed},
        "effect_counters": counters,
        "cases": cases,
    }
    public_schema = {"$ref": "#/$defs/publicResult", "$defs": schema["$defs"]}
    if list(Draft202012Validator(public_schema).iter_errors(result)):
        raise VerificationError("VERIFIER_RESULT_INVALID")
    atomic_write_json(repository_root / args.result, result)
    return 0 if failed == 0 else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--command-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None, *, repository_root: Path = REPOSITORY_ROOT) -> int:
    try:
        return run(_parser().parse_args(argv), repository_root=repository_root)
    except (VerificationError, PatchVerificationError, OSError, RuntimeError, ValueError):
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
