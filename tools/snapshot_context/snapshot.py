from __future__ import annotations

import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
from typing import Callable, Mapping

from .model import (
    SnapshotBundle,
    SnapshotEntry,
    SnapshotError,
    atomic_write_json,
    canonical_json_bytes,
    canonical_relative_path,
    sha256_bytes,
)


ProcessRunner = Callable[..., object]
STATE_ORDER = ("tracked", "staged", "modified", "untracked")


def _run_git(
    runner: ProcessRunner,
    source_root: Path,
    arguments: list[str],
    *,
    required: bool = True,
) -> object:
    try:
        completed = runner(
            ["git", "-C", str(source_root), *arguments],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SnapshotError("SNAPSHOT_SOURCE_INVALID") from exc
    if required and getattr(completed, "returncode", 1) != 0:
        raise SnapshotError("SNAPSHOT_SOURCE_INVALID")
    return completed


def _decode_path(raw: bytes) -> str:
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SnapshotError("SNAPSHOT_PATH_INVALID") from exc


def _parse_status(raw: bytes) -> tuple[dict[str, set[str]], set[str]]:
    states: dict[str, set[str]] = {}
    deleted: set[str] = set()
    records = raw.split(b"\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        if record.startswith(b"? "):
            path = _decode_path(record[2:])
            canonical_relative_path(path)
            states.setdefault(path, set()).add("untracked")
            continue
        if record.startswith(b"1 "):
            fields = record.split(b" ", 8)
            if len(fields) != 9:
                raise SnapshotError("SNAPSHOT_SOURCE_INVALID")
            change = fields[1].decode("ascii", errors="strict")
            path = _decode_path(fields[8])
        elif record.startswith(b"2 "):
            fields = record.split(b" ", 9)
            if len(fields) != 10 or index >= len(records):
                raise SnapshotError("SNAPSHOT_SOURCE_INVALID")
            change = fields[1].decode("ascii", errors="strict")
            path = _decode_path(fields[9])
            index += 1  # original path for rename/copy
        else:
            # Ignore headers and ignored entries, reject malformed tracked records.
            if record.startswith((b"# ", b"! ")):
                continue
            raise SnapshotError("SNAPSHOT_SOURCE_INVALID")
        canonical_relative_path(path)
        current = states.setdefault(path, {"tracked"})
        if change[0] != ".":
            current.add("staged")
        if change[1] != ".":
            current.add("modified")
        if "D" in change:
            deleted.add(path)
    return states, deleted


def _parse_modes(raw: bytes) -> dict[str, str]:
    modes: dict[str, str] = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode = metadata.split(b" ", 1)[0].decode("ascii")
        except (ValueError, UnicodeDecodeError) as exc:
            raise SnapshotError("SNAPSHOT_SOURCE_INVALID") from exc
        path = _decode_path(raw_path)
        canonical_relative_path(path)
        if mode in ("100644", "100755"):
            modes[path] = mode
        elif mode == "120000":
            modes[path] = mode
        else:
            raise SnapshotError("SNAPSHOT_FILE_TYPE_FORBIDDEN")
    return modes


def _ensure_regular_file(source_root: Path, relative: Path) -> os.stat_result:
    current = source_root
    for component in relative.parts:
        current = current / component
        try:
            info = os.lstat(current)
        except OSError as exc:
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED") from exc
        attributes = getattr(info, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if stat.S_ISLNK(info.st_mode) or (reparse and attributes & reparse):
            raise SnapshotError("SNAPSHOT_FILE_TYPE_FORBIDDEN")
    if not stat.S_ISREG(info.st_mode):
        raise SnapshotError("SNAPSHOT_FILE_TYPE_FORBIDDEN")
    return info


def _same_file(before: os.stat_result, after: os.stat_result) -> bool:
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    return all(getattr(before, key, None) == getattr(after, key, None) for key in keys)


def _manifest_digest_body(manifest: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in manifest.items()
        if key not in ("snapshot_id", "manifest_sha256")
    }


def create_snapshot(
    source_root: Path,
    destination_root: Path,
    repository_label: str,
    *,
    runner: ProcessRunner = subprocess.run,
) -> SnapshotBundle:
    source_root = Path(source_root).resolve()
    destination_root = Path(destination_root).resolve()
    if not isinstance(repository_label, str) or not repository_label.strip():
        raise SnapshotError("SNAPSHOT_SOURCE_INVALID")
    if destination_root.exists():
        raise SnapshotError("SNAPSHOT_DESTINATION_INVALID")
    destination_root.parent.mkdir(parents=True, exist_ok=True)

    inside = _run_git(runner, source_root, ["rev-parse", "--is-inside-work-tree"])
    if getattr(inside, "stdout", b"").strip() != b"true":
        raise SnapshotError("SNAPSHOT_SOURCE_INVALID")
    head_result = _run_git(
        runner, source_root, ["rev-parse", "--verify", "HEAD"], required=False
    )
    if getattr(head_result, "returncode", 1) == 0:
        head_sha = getattr(head_result, "stdout", b"").strip().decode("ascii")
        if len(head_sha) != 40 or any(ch not in "0123456789abcdef" for ch in head_sha):
            raise SnapshotError("SNAPSHOT_SOURCE_INVALID")
    else:
        head_sha = "UNBORN"

    inventory_result = _run_git(
        runner,
        source_root,
        ["ls-files", "-z", "--cached", "--others", "--exclude-standard"],
    )
    status_result = _run_git(
        runner,
        source_root,
        ["status", "--porcelain=v2", "-z", "--untracked-files=all"],
    )
    modes_result = _run_git(runner, source_root, ["ls-files", "-s", "-z"])
    inventory = []
    for raw_path in getattr(inventory_result, "stdout", b"").split(b"\0"):
        if not raw_path:
            continue
        path = _decode_path(raw_path)
        canonical_relative_path(path)
        inventory.append(path)
    if len(inventory) != len(set(inventory)):
        raise SnapshotError("SNAPSHOT_SOURCE_INVALID")
    states, deleted = _parse_status(getattr(status_result, "stdout", b""))
    modes = _parse_modes(getattr(modes_result, "stdout", b""))

    temporary = Path(
        tempfile.mkdtemp(prefix=f".{destination_root.name}.", dir=destination_root.parent)
    )
    snapshot_tree = temporary / "snapshot"
    workspace_tree = temporary / "workspace"
    snapshot_tree.mkdir()
    entries: list[SnapshotEntry] = []
    try:
        for path_text in sorted(inventory):
            relative_posix = canonical_relative_path(path_text)
            relative = Path(*relative_posix.parts)
            source_path = source_root / relative
            if path_text in deleted or not source_path.exists():
                deleted.add(path_text)
                continue
            before = _ensure_regular_file(source_root, relative)
            if modes.get(path_text) == "120000":
                raise SnapshotError("SNAPSHOT_FILE_TYPE_FORBIDDEN")
            try:
                content = source_path.read_bytes()
                after = os.lstat(source_path)
            except OSError as exc:
                raise SnapshotError("SNAPSHOT_CONTENT_CHANGED") from exc
            if not _same_file(before, after) or len(content) != before.st_size:
                raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
            target = snapshot_tree / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            mode = modes.get(path_text)
            if mode is None:
                mode = "100755" if before.st_mode & stat.S_IXUSR else "100644"
            source_states = states.get(path_text, {"tracked"})
            ordered_states = tuple(item for item in STATE_ORDER if item in source_states)
            entries.append(
                SnapshotEntry(path_text, len(content), sha256_bytes(content), mode, ordered_states)
            )

        shutil.copytree(snapshot_tree, workspace_tree)
        manifest: dict[str, object] = {
            "snapshot_version": "1.0",
            "source": {
                "repository_label": repository_label,
                "head_sha": head_sha,
                "git_state_sha256": sha256_bytes(getattr(status_result, "stdout", b"")),
            },
            "dirty": bool(getattr(status_result, "stdout", b"")),
            "entries": [entry.as_dict() for entry in entries],
            "deleted_paths": sorted(deleted),
        }
        digest = sha256_bytes(canonical_json_bytes(manifest))
        manifest["snapshot_id"] = f"sha256:{digest}"
        manifest["manifest_sha256"] = digest
        verify_snapshot(snapshot_tree, manifest)
        verify_snapshot(workspace_tree, manifest)
        atomic_write_json(temporary / "manifest.json", manifest)
        os.replace(temporary, destination_root)
        return SnapshotBundle(
            manifest=manifest,
            snapshot_root=destination_root / "snapshot",
            workspace_root=destination_root / "workspace",
        )
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_snapshot(snapshot_root: Path, manifest: Mapping[str, object]) -> None:
    snapshot_root = Path(snapshot_root).resolve()
    try:
        body = _manifest_digest_body(manifest)
        digest = sha256_bytes(canonical_json_bytes(body))
        if manifest.get("snapshot_id") != f"sha256:{digest}":
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        if manifest.get("manifest_sha256") != digest:
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        entries = manifest["entries"]
        if not isinstance(entries, list):
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        expected_paths: set[str] = set()
        for raw_entry in entries:
            if not isinstance(raw_entry, Mapping):
                raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
            path_text = raw_entry.get("path")
            if not isinstance(path_text, str):
                raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
            relative_posix = canonical_relative_path(path_text)
            if path_text in expected_paths:
                raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
            expected_paths.add(path_text)
            relative = Path(*relative_posix.parts)
            file_path = snapshot_root / relative
            info = _ensure_regular_file(snapshot_root, relative)
            content = file_path.read_bytes()
            if info.st_size != raw_entry.get("size") or sha256_bytes(content) != raw_entry.get("sha256"):
                raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        actual_paths = {
            path.relative_to(snapshot_root).as_posix()
            for path in snapshot_root.rglob("*")
            if path.is_file()
        }
        if actual_paths != expected_paths:
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
    except SnapshotError:
        raise
    except (KeyError, OSError, TypeError, ValueError) as exc:
        raise SnapshotError("SNAPSHOT_CONTENT_CHANGED") from exc
