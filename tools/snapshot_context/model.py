from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import tempfile
from typing import Mapping, Sequence


class SnapshotError(Exception):
    """Stable, public-safe failure from the local snapshot boundary."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class SnapshotEntry:
    path: str
    size: int
    sha256: str
    mode: str
    source_states: Sequence[str]

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "size": self.size,
            "sha256": self.sha256,
            "mode": self.mode,
            "source_states": list(self.source_states),
        }


@dataclass(frozen=True)
class SnapshotBundle:
    manifest: dict[str, object]
    snapshot_root: Path
    workspace_root: Path


def canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_relative_path(raw: str) -> PurePosixPath:
    if not isinstance(raw, str):
        raise SnapshotError("SNAPSHOT_PATH_INVALID")
    path = PurePosixPath(raw)
    if (
        not raw
        or path.is_absolute()
        or raw.startswith("/")
        or ".." in path.parts
        or "\\" in raw
        or "//" in raw
        or "\x00" in raw
        or any(part in ("", ".") for part in path.parts)
    ):
        raise SnapshotError("SNAPSHOT_PATH_INVALID")
    lowered = tuple(part.casefold() for part in path.parts)
    if ".git" in lowered:
        raise SnapshotError("SNAPSHOT_PATH_INVALID")
    if any(
        part == ".env"
        or part.startswith(".env.")
        or "credential" in part
        or "secret" in part
        for part in lowered
    ):
        raise SnapshotError("SNAPSHOT_PATH_INVALID")
    return path


def atomic_write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
