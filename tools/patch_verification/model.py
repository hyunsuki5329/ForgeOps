from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import tempfile
from typing import Any


class PatchVerificationError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class EffectAudit:
    workspace_writes: int = 0
    outside_workspace_write_attempts: int = 0
    remote_write_attempts: int = 0


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _is_reparse_or_symlink(path: Path) -> bool:
    try:
        info = path.lstat()
    except OSError as error:
        raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION") from error
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def canonical_resource_ref(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise PatchVerificationError("PATCH_RESOURCE_INVALID")
    if value.startswith("/") or (len(value) >= 2 and value[1] == ":"):
        raise PatchVerificationError("PATCH_RESOURCE_INVALID")
    if any(character in value for character in ("*", "?", "[", "]")):
        raise PatchVerificationError("PATCH_RESOURCE_INVALID")
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or any(part in ("", ".", "..") for part in parsed.parts):
        raise PatchVerificationError("PATCH_RESOURCE_INVALID")
    normalized = parsed.as_posix()
    if normalized != value:
        raise PatchVerificationError("PATCH_RESOURCE_INVALID")
    return normalized


def strict_utc(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PatchVerificationError("EVIDENCE_FRESHNESS_INVALID")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise PatchVerificationError("EVIDENCE_FRESHNESS_INVALID") from error
    if parsed.tzinfo != timezone.utc:
        raise PatchVerificationError("EVIDENCE_FRESHNESS_INVALID")
    return parsed


def tree_hash(root: Path) -> str:
    try:
        resolved = root.resolve(strict=True)
    except OSError as error:
        raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION") from error
    if not resolved.is_dir() or _is_reparse_or_symlink(root):
        raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION")
    entries: list[tuple[str, bytes]] = []
    for path in root.rglob("*"):
        if _is_reparse_or_symlink(path):
            raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PatchVerificationError("PATCH_CONTAINMENT_VIOLATION")
        relative = path.relative_to(root).as_posix()
        entries.append((relative, path.read_bytes()))
    digest = hashlib.sha256()
    for relative, content in sorted(entries):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def public_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256_bytes(encoded)

