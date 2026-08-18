from __future__ import annotations

import ast
import configparser
import io
import json
from pathlib import Path
from typing import Mapping

from .model import (
    PatchVerificationError,
    _is_reparse_or_symlink,
    public_sha256,
    sha256_bytes,
)


PROTECTED_PATHS = (
    "tests/test_calculator.py",
    ".coveragerc",
    "verification-profile.json",
)
MANIFEST_FIELDS = {
    "manifest_version",
    "trusted_profile_digest",
    "protected_files",
    "test_paths",
}
PROTECTED_FIELDS = {"path", "sha256", "semantic_fingerprint"}


def _safe_file(root: Path, relative: str, error_code: str) -> Path:
    candidate = root.joinpath(*relative.split("/"))
    cursor = root
    for part in relative.split("/"):
        cursor = cursor / part
        if not cursor.exists() or _is_reparse_or_symlink(cursor):
            raise PatchVerificationError(error_code)
    try:
        candidate.resolve(strict=True).relative_to(root.resolve(strict=True))
    except (OSError, ValueError) as error:
        raise PatchVerificationError(error_code) from error
    if not candidate.is_file():
        raise PatchVerificationError(error_code)
    return candidate


def _decorator_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _decorator_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    return ""


def _test_semantics(content: bytes) -> dict[str, object]:
    try:
        tree = ast.parse(content.decode("utf-8"))
    except (UnicodeDecodeError, SyntaxError) as error:
        raise PatchVerificationError("ASSERTION_WEAKENED") from error
    classes = []
    functions = []
    decorators = []
    assertions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            functions.append(node.name)
            decorators.extend(_decorator_name(item) for item in node.decorator_list)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr.startswith("assert"):
            assertions.append(
                {
                    "name": node.func.attr,
                    "args": [ast.dump(item, annotate_fields=True, include_attributes=False) for item in node.args],
                    "keywords": [
                        [item.arg, ast.dump(item.value, annotate_fields=True, include_attributes=False)]
                        for item in node.keywords
                    ],
                }
            )
    return {
        "classes": sorted(classes),
        "functions": sorted(functions),
        "decorators": sorted(decorators),
        "assertions": assertions,
    }


def _coverage_semantics(content: bytes) -> dict[str, object]:
    try:
        text = content.decode("utf-8")
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_file(io.StringIO(text))
    except (UnicodeDecodeError, configparser.Error) as error:
        raise PatchVerificationError("COVERAGE_POLICY_CHANGED") from error
    return {
        section: {key: value.splitlines() for key, value in sorted(parser.items(section))}
        for section in sorted(parser.sections())
    }


def _profile_semantics(content: bytes) -> object:
    try:
        return json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED") from error


def _semantic(path: str, content: bytes) -> str:
    if path.startswith("tests/"):
        value = _test_semantics(content)
    elif path == ".coveragerc":
        value = _coverage_semantics(content)
    else:
        value = _profile_semantics(content)
    return public_sha256(value)


def build_guard_manifest(workspace_root: Path, trusted_profile_digest: str) -> dict[str, object]:
    if not isinstance(trusted_profile_digest, str) or len(trusted_profile_digest) != 64:
        raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")
    protected = []
    for relative in PROTECTED_PATHS:
        error = "TEST_PATH_INVALID" if relative.startswith("tests/") else "VERIFICATION_PROFILE_CHANGED"
        path = _safe_file(workspace_root, relative, error)
        content = path.read_bytes()
        protected.append(
            {
                "path": relative,
                "sha256": sha256_bytes(content),
                "semantic_fingerprint": _semantic(relative, content),
            }
        )
    return {
        "manifest_version": "1.0",
        "trusted_profile_digest": trusted_profile_digest,
        "protected_files": protected,
        "test_paths": ["tests/test_calculator.py"],
    }


def _validate_manifest(manifest: Mapping[str, object], trusted_digest: str) -> dict[str, dict[str, str]]:
    if not isinstance(manifest, Mapping) or set(manifest) != MANIFEST_FIELDS:
        raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")
    if manifest["manifest_version"] != "1.0" or manifest["trusted_profile_digest"] != trusted_digest:
        raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")
    if manifest["test_paths"] != ["tests/test_calculator.py"] or not isinstance(manifest["protected_files"], list):
        raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")
    records: dict[str, dict[str, str]] = {}
    for item in manifest["protected_files"]:
        if not isinstance(item, dict) or set(item) != PROTECTED_FIELDS:
            raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")
        path = item.get("path")
        if path not in PROTECTED_PATHS or path in records:
            raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")
        if any(not isinstance(item[field], str) or len(item[field]) != 64 for field in ("sha256", "semantic_fingerprint")):
            raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")
        records[path] = item
    if tuple(records) != PROTECTED_PATHS:
        raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")
    return records


def verify_guard_manifest(
    workspace_root: Path,
    manifest: Mapping[str, object],
    *,
    trusted_profile_digest: str,
) -> dict[str, object]:
    records = _validate_manifest(manifest, trusted_profile_digest)
    test_root = workspace_root / "tests"
    actual_tests = sorted(
        path.relative_to(workspace_root).as_posix()
        for path in test_root.glob("test_*.py")
    ) if test_root.is_dir() else []
    expected_test = "tests/test_calculator.py"
    if expected_test not in actual_tests:
        if actual_tests:
            raise PatchVerificationError("TEST_PATH_INVALID")
        raise PatchVerificationError("TEST_DELETED")
    if actual_tests != [expected_test]:
        raise PatchVerificationError("TEST_PATH_INVALID")
    test_path = _safe_file(workspace_root, expected_test, "TEST_PATH_INVALID")
    test_content = test_path.read_bytes()
    semantics = _test_semantics(test_content)
    decorator_names = [value.lower() for value in semantics["decorators"]]
    text_lower = test_content.decode("utf-8", errors="ignore").lower()
    if any("skip" in value for value in decorator_names):
        raise PatchVerificationError("TEST_SKIP_INJECTED")
    if any("expectedfailure" in value or "xfail" in value for value in decorator_names) or "xfail" in text_lower:
        raise PatchVerificationError("TEST_XFAIL_INJECTED")
    if public_sha256(semantics) != records[expected_test]["semantic_fingerprint"]:
        raise PatchVerificationError("ASSERTION_WEAKENED")
    if sha256_bytes(test_content) != records[expected_test]["sha256"]:
        raise PatchVerificationError("TEST_PATH_INVALID")

    coverage = _safe_file(workspace_root, ".coveragerc", "COVERAGE_POLICY_CHANGED").read_bytes()
    if (
        _semantic(".coveragerc", coverage) != records[".coveragerc"]["semantic_fingerprint"]
        or sha256_bytes(coverage) != records[".coveragerc"]["sha256"]
    ):
        raise PatchVerificationError("COVERAGE_POLICY_CHANGED")
    profile = _safe_file(workspace_root, "verification-profile.json", "VERIFICATION_PROFILE_CHANGED").read_bytes()
    if (
        _semantic("verification-profile.json", profile) != records["verification-profile.json"]["semantic_fingerprint"]
        or sha256_bytes(profile) != records["verification-profile.json"]["sha256"]
    ):
        raise PatchVerificationError("VERIFICATION_PROFILE_CHANGED")
    return {"status": "PASSED", "tamper_count": 0}
