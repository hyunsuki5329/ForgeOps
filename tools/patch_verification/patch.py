from __future__ import annotations

import difflib
import os
from pathlib import Path
import tempfile
from typing import Mapping, Sequence

from .model import (
    EffectAudit,
    PatchVerificationError,
    _is_reparse_or_symlink,
    canonical_resource_ref,
    sha256_bytes,
    tree_hash,
)


INTENT_FIELDS = {
    "resource_ref",
    "before_sha256",
    "after_sha256",
    "replacement_text",
    "max_diff_bytes",
    "max_changed_lines",
}
ALLOWED_RESOURCES = frozenset({"src/calculator.py"})


def _contained_file(root: Path, resource_ref: str) -> Path:
    candidate = root.joinpath(*resource_ref.split("/"))
    cursor = root
    for part in resource_ref.split("/"):
        cursor = cursor / part
        if not cursor.exists() or _is_reparse_or_symlink(cursor):
            raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION")
    try:
        root_resolved = root.resolve(strict=True)
        candidate_resolved = candidate.resolve(strict=True)
        candidate_resolved.relative_to(root_resolved)
    except (OSError, ValueError) as error:
        raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION") from error
    if not candidate_resolved.is_file():
        raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION")
    return candidate


def materialize_fixture(root: Path, files: Sequence[Mapping[str, object]]) -> None:
    root.mkdir(parents=True, exist_ok=False)
    seen: set[str] = set()
    for item in files:
        if set(item) != {"path", "content", "sha256"}:
            raise PatchVerificationError("PATCH_INPUT_INVALID")
        resource_ref = canonical_resource_ref(item["path"])
        if resource_ref in seen or not isinstance(item["content"], str):
            raise PatchVerificationError("PATCH_INPUT_INVALID")
        content = item["content"].encode("utf-8")
        if not isinstance(item["sha256"], str) or sha256_bytes(content) != item["sha256"]:
            raise PatchVerificationError("PATCH_INPUT_INVALID")
        target = root.joinpath(*resource_ref.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        seen.add(resource_ref)


def _validated_intent(intent: Mapping[str, object]) -> tuple[str, bytes, int, int]:
    if not isinstance(intent, Mapping) or set(intent) != INTENT_FIELDS:
        raise PatchVerificationError("PATCH_INPUT_INVALID")
    resource_ref = canonical_resource_ref(intent["resource_ref"])
    if resource_ref not in ALLOWED_RESOURCES:
        raise PatchVerificationError("PATCH_RESOURCE_UNAUTHORIZED")
    for field in ("before_sha256", "after_sha256"):
        value = intent[field]
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise PatchVerificationError("PATCH_INPUT_INVALID")
    replacement = intent["replacement_text"]
    if not isinstance(replacement, str):
        raise PatchVerificationError("PATCH_INPUT_INVALID")
    try:
        after_bytes = replacement.encode("utf-8")
    except UnicodeEncodeError as error:
        raise PatchVerificationError("PATCH_INPUT_INVALID") from error
    if sha256_bytes(after_bytes) != intent["after_sha256"]:
        raise PatchVerificationError("PATCH_INPUT_INVALID")
    byte_limit = intent["max_diff_bytes"]
    line_limit = intent["max_changed_lines"]
    if (
        isinstance(byte_limit, bool) or not isinstance(byte_limit, int) or not 1 <= byte_limit <= 65536
        or isinstance(line_limit, bool) or not isinstance(line_limit, int) or not 1 <= line_limit <= 2000
    ):
        raise PatchVerificationError("PATCH_INPUT_INVALID")
    return resource_ref, after_bytes, byte_limit, line_limit


def apply_bounded_patch(
    source_root: Path,
    workspace_root: Path,
    intent: Mapping[str, object],
    *,
    audit: EffectAudit,
) -> dict[str, object]:
    if not isinstance(audit, EffectAudit):
        raise PatchVerificationError("PATCH_INPUT_INVALID")
    try:
        source_resolved = source_root.resolve(strict=True)
        workspace_resolved = workspace_root.resolve(strict=True)
    except OSError as error:
        raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION") from error
    if (
        source_resolved == workspace_resolved
        or not source_resolved.is_dir()
        or not workspace_resolved.is_dir()
        or _is_reparse_or_symlink(source_root)
        or _is_reparse_or_symlink(workspace_root)
    ):
        raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION")

    source_tree_before = tree_hash(source_root)
    resource_ref, after_bytes, byte_limit, line_limit = _validated_intent(intent)
    source_target = _contained_file(source_root, resource_ref)
    workspace_target = _contained_file(workspace_root, resource_ref)
    source_before = source_target.read_bytes()
    workspace_before = workspace_target.read_bytes()
    if source_before != workspace_before or sha256_bytes(source_before) != intent["before_sha256"]:
        raise PatchVerificationError("PATCH_BASE_MISMATCH")
    try:
        before_text = source_before.decode("utf-8")
        after_text = after_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PatchVerificationError("PATCH_INPUT_INVALID") from error
    diff = "".join(
        difflib.unified_diff(
            before_text.splitlines(keepends=True),
            after_text.splitlines(keepends=True),
            fromfile=f"a/{resource_ref}",
            tofile=f"b/{resource_ref}",
            lineterm="\n",
        )
    )
    diff_bytes = len(diff.encode("utf-8"))
    changed_lines = sum(
        1 for line in diff.splitlines() if (line.startswith("+") or line.startswith("-")) and not line.startswith(("+++", "---"))
    )
    if not diff or diff_bytes > byte_limit or changed_lines > line_limit:
        raise PatchVerificationError("PATCH_DIFF_LIMIT_EXCEEDED")

    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=workspace_target.parent, prefix=f".{workspace_target.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(after_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, workspace_target)
        audit.workspace_writes += 1
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    if workspace_target.read_bytes() != after_bytes:
        raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION")
    if tree_hash(source_root) != source_tree_before:
        audit.outside_workspace_write_attempts += 1
        raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION")
    return {
        "resource_ref": resource_ref,
        "before_sha256": intent["before_sha256"],
        "after_sha256": intent["after_sha256"],
        "diff": diff,
        "diff_sha256": sha256_bytes(diff.encode("utf-8")),
        "diff_bytes": diff_bytes,
        "changed_lines": changed_lines,
    }
