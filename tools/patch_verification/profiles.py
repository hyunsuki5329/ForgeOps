from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Callable

from .model import PatchVerificationError, public_sha256, strict_utc


TRUSTED_PROFILE = {
    "profile_id": "forgeops-w7-fixture-checks",
    "checks": [
        {"id": "TASK_TEST", "kind": "task"},
        {"id": "REGRESSION_TEST", "kind": "regression"},
        {"id": "LINT", "kind": "lint"},
        {"id": "TYPECHECK", "kind": "typecheck"},
    ],
}
TRUSTED_PROFILE_DIGEST = public_sha256(TRUSTED_PROFILE)
COMPANION_PROFILE = {
    "profile_id": TRUSTED_PROFILE["profile_id"],
    "checks": [item["id"] for item in TRUSTED_PROFILE["checks"]],
}


def _load_python(root: Path) -> tuple[bytes, bytes, ast.Module | None, ast.Module | None]:
    try:
        source_bytes = (root / "src/calculator.py").read_bytes()
        tests_bytes = (root / "tests/test_calculator.py").read_bytes()
    except OSError:
        return b"", b"", None, None
    try:
        source_tree = ast.parse(source_bytes.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError):
        source_tree = None
    try:
        tests_tree = ast.parse(tests_bytes.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError):
        tests_tree = None
    return source_bytes, tests_bytes, source_tree, tests_tree


def _functions(tree: ast.Module | None) -> dict[str, ast.FunctionDef]:
    if tree is None:
        return {}
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _restricted_probe(function: ast.FunctionDef | None, arguments: tuple[int, ...]) -> int | None:
    if function is None or len(function.body) != 1 or len(function.args.args) != len(arguments):
        return None
    if function.decorator_list or function.args.vararg or function.args.kwarg:
        return None
    statement = function.body[0]
    if not isinstance(statement, ast.Return):
        return None
    names = [argument.arg for argument in function.args.args]
    environment = dict(zip(names, arguments, strict=True))
    value = statement.value
    if isinstance(value, ast.Name) and value.id in environment:
        return environment[value.id]
    if (
        isinstance(value, ast.BinOp)
        and isinstance(value.left, ast.Name)
        and isinstance(value.right, ast.Name)
        and value.left.id in environment
        and value.right.id in environment
        and isinstance(value.op, (ast.Add, ast.Sub))
    ):
        left = environment[value.left.id]
        right = environment[value.right.id]
        return left + right if isinstance(value.op, ast.Add) else left - right
    return None


def _task_check(root: Path) -> tuple[bool, str, object]:
    _, _, source_tree, _ = _load_python(root)
    observed = _restricted_probe(_functions(source_tree).get("total"), (2, 3))
    return observed == 5, "CHECK_PASSED" if observed == 5 else "TASK_EXPECTATION_FAILED", observed


def _regression_check(root: Path) -> tuple[bool, str, object]:
    _, _, source_tree, _ = _load_python(root)
    observed = _restricted_probe(_functions(source_tree).get("identity"), (7,))
    return observed == 7, "CHECK_PASSED" if observed == 7 else "REGRESSION_EXPECTATION_FAILED", observed


def _lint_check(root: Path) -> tuple[bool, str, object]:
    source_bytes, tests_bytes, source_tree, tests_tree = _load_python(root)
    valid = bool(source_bytes and tests_bytes and source_tree is not None and tests_tree is not None)
    for value in (source_bytes, tests_bytes):
        if b"\r" in value or any(line.endswith((b" ", b"\t")) for line in value.splitlines()):
            valid = False
    return valid, "CHECK_PASSED" if valid else "LINT_POLICY_FAILED", valid


def _annotation_name(value: ast.expr | None) -> str | None:
    return value.id if isinstance(value, ast.Name) else None


def _typecheck(root: Path) -> tuple[bool, str, object]:
    _, _, source_tree, _ = _load_python(root)
    functions = _functions(source_tree)
    expected = {"total": ("left", "right"), "identity": ("value",)}
    valid = set(functions) == set(expected)
    for name, arguments in expected.items():
        function = functions.get(name)
        if function is None:
            valid = False
            continue
        actual_names = tuple(argument.arg for argument in function.args.args)
        annotations = tuple(_annotation_name(argument.annotation) for argument in function.args.args)
        if actual_names != arguments or annotations != ("int",) * len(arguments) or _annotation_name(function.returns) != "int":
            valid = False
    return valid, "CHECK_PASSED" if valid else "TYPE_CONTRACT_FAILED", valid


CHECKS: dict[str, Callable[[Path], tuple[bool, str, object]]] = {
    "TASK_TEST": _task_check,
    "REGRESSION_TEST": _regression_check,
    "LINT": _lint_check,
    "TYPECHECK": _typecheck,
}


def _validate_invocation(
    workspace_root: Path,
    profile_id: str,
    profile_digest: str,
    observed_at: str,
    validation_at: str | None,
) -> None:
    if profile_id != TRUSTED_PROFILE["profile_id"]:
        raise PatchVerificationError("PROFILE_IDENTITY_INVALID")
    if profile_digest != TRUSTED_PROFILE_DIGEST:
        raise PatchVerificationError("PROFILE_DIGEST_INVALID")
    observed = strict_utc(observed_at)
    if validation_at is not None:
        anchor = strict_utc(validation_at)
        if not 0 <= (observed - anchor).total_seconds() <= 300:
            raise PatchVerificationError("EVIDENCE_FRESHNESS_INVALID")
    try:
        companion = json.loads((workspace_root / "verification-profile.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED") from error
    if companion != COMPANION_PROFILE:
        raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")


def run_trusted_profile(
    workspace_root: Path,
    *,
    profile_id: str,
    profile_digest: str,
    observed_at: str,
    validation_at: str | None = None,
    phase: str | None = None,
) -> dict[str, object]:
    _validate_invocation(workspace_root, profile_id, profile_digest, observed_at, validation_at)
    evaluated: list[tuple[dict[str, str], bool, str, object]] = []
    for item in TRUSTED_PROFILE["checks"]:
        passed, reason, detail = CHECKS[item["id"]](workspace_root)
        evaluated.append((item, passed, reason, detail))
    if phase is None:
        phase = "changed" if evaluated[0][1] else "baseline"
    if phase not in {"baseline", "changed"}:
        raise PatchVerificationError("PATCH_INPUT_INVALID")
    records = []
    for item, passed, reason, detail in evaluated:
        fingerprint = public_sha256({"check_id": item["id"], "status": "PASSED" if passed else "FAILED", "reason": reason, "detail": detail})
        records.append(
            {
                "check_id": item["id"],
                "kind": item["kind"],
                "status": "PASSED" if passed else "FAILED",
                "reason": reason,
                "evidence": {
                    "evidence_id": f"EVID-W7-{item['id']}-{phase}",
                    "type": "test",
                    "tier": "E2",
                    "observed_at": observed_at,
                    "profile_id": TRUSTED_PROFILE["profile_id"],
                    "profile_digest": TRUSTED_PROFILE_DIGEST,
                    "result_fingerprint": fingerprint,
                },
            }
        )
    return {"phase": phase, "profile_id": profile_id, "profile_digest": profile_digest, "checks": records}


def compare_baseline_and_changed(baseline: dict[str, object], changed: dict[str, object]) -> str:
    baseline_checks = {item["check_id"]: item for item in baseline.get("checks", [])}
    changed_checks = {item["check_id"]: item for item in changed.get("checks", [])}
    expected_ids = tuple(item["id"] for item in TRUSTED_PROFILE["checks"])
    if tuple(baseline_checks) != expected_ids or tuple(changed_checks) != expected_ids:
        raise PatchVerificationError("PROFILE_IDENTITY_INVALID")
    task_baseline = baseline_checks["TASK_TEST"]
    if task_baseline["status"] != "FAILED" or task_baseline["reason"] != "TASK_EXPECTATION_FAILED":
        raise PatchVerificationError("BASELINE_UNHEALTHY")
    if any(baseline_checks[item]["status"] != "PASSED" for item in expected_ids[1:]):
        raise PatchVerificationError("BASELINE_UNHEALTHY")
    if changed_checks["TASK_TEST"]["status"] != "PASSED":
        raise PatchVerificationError("TASK_CHECK_FAILED")
    if changed_checks["LINT"]["status"] != "PASSED":
        raise PatchVerificationError("LINT_FAILED")
    if changed_checks["TYPECHECK"]["status"] != "PASSED":
        raise PatchVerificationError("TYPECHECK_FAILED")
    if any(changed_checks[item]["status"] != "PASSED" for item in expected_ids[1:]):
        raise PatchVerificationError("NEW_REGRESSION")
    return "PASSED"
