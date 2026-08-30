from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import subprocess
import tempfile
from typing import Callable, Mapping

from jsonschema import Draft202012Validator

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
_READ_OBSERVER: ContextVar[Callable[[Path], None] | None] = ContextVar(
    "snapshot_read_observer", default=None
)
_SNAPSHOT_SCHEMA_ID = "contracts/forgeops-snapshot-contract/1.0/schema.json"


def _load_snapshot_schema() -> dict[str, object]:
    schema_path = Path(__file__).resolve().parents[2] / _SNAPSHOT_SCHEMA_ID
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        if not isinstance(schema, dict) or schema.get("$id") != _SNAPSHOT_SCHEMA_ID:
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        schema["$id"] = schema_path.resolve(strict=True).as_uri()
        return schema
    except SnapshotError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SnapshotError("SNAPSHOT_CONTENT_CHANGED") from exc


@contextmanager
def observe_reads(observer: Callable[[Path], None]):
    token = _READ_OBSERVER.set(observer)
    try:
        yield
    finally:
        _READ_OBSERVER.reset(token)


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


def _read_stable_regular_file(
    source_root: Path, relative: Path
) -> tuple[bytes, os.stat_result]:
    before = _ensure_regular_file(source_root, relative)
    file_path = source_root / relative
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(file_path, flags)
        opened = os.fstat(descriptor)
        attributes = getattr(opened, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (
            not _same_file(before, opened)
            or not stat.S_ISREG(opened.st_mode)
            or (reparse and attributes & reparse)
        ):
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        observer = _READ_OBSERVER.get()
        if observer is not None:
            observer(file_path)
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            content = stream.read()
            after = os.fstat(stream.fileno())
        if not _same_file(opened, after) or len(content) != opened.st_size:
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        return content, opened
    except SnapshotError:
        raise
    except OSError as exc:
        raise SnapshotError("SNAPSHOT_CONTENT_CHANGED") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _manifest_digest_body(manifest: Mapping[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in manifest.items()
        if key not in ("snapshot_id", "manifest_sha256")
    }


def _validated_root_path(raw: Path) -> Path:
    absolute = Path(os.path.abspath(raw))
    chain = [absolute]
    chain.extend(parent for parent in absolute.parents if parent != absolute)
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    for node in reversed(chain):
        try:
            info = os.lstat(node)
        except OSError as exc:
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED") from exc
        attributes = getattr(info, "st_file_attributes", 0)
        if (
            stat.S_ISLNK(info.st_mode)
            or not stat.S_ISDIR(info.st_mode)
            or (reparse and attributes & reparse)
        ):
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
    return absolute


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
    try:
        destination_root.relative_to(source_root)
    except ValueError:
        pass
    else:
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
            if modes.get(path_text) == "120000":
                raise SnapshotError("SNAPSHOT_FILE_TYPE_FORBIDDEN")
            content, before = _read_stable_regular_file(source_root, relative)
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
    snapshot_root = _validated_root_path(Path(snapshot_root))
    try:
        schema = _load_snapshot_schema()
        if list(Draft202012Validator(schema).iter_errors(manifest)):
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
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
            content, info = _read_stable_regular_file(snapshot_root, relative)
            if info.st_size != raw_entry.get("size") or sha256_bytes(content) != raw_entry.get("sha256"):
                raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        expected_directories = {"."}
        for path_text in expected_paths:
            parent = PurePosixPath(path_text).parent
            while str(parent) != ".":
                expected_directories.add(str(parent))
                parent = parent.parent
        actual_paths: set[str] = set()
        actual_directories = {"."}
        root_info = os.lstat(snapshot_root)
        root_attributes = getattr(root_info, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if not stat.S_ISDIR(root_info.st_mode) or (reparse and root_attributes & reparse):
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        for current_root, directory_names, file_names in os.walk(
            snapshot_root, topdown=True, followlinks=False
        ):
            current = Path(current_root)
            for name in directory_names:
                node = current / name
                info = os.lstat(node)
                attributes = getattr(info, "st_file_attributes", 0)
                if (
                    stat.S_ISLNK(info.st_mode)
                    or not stat.S_ISDIR(info.st_mode)
                    or (reparse and attributes & reparse)
                ):
                    raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
                actual_directories.add(node.relative_to(snapshot_root).as_posix())
            for name in file_names:
                node = current / name
                info = os.lstat(node)
                attributes = getattr(info, "st_file_attributes", 0)
                if (
                    stat.S_ISLNK(info.st_mode)
                    or not stat.S_ISREG(info.st_mode)
                    or (reparse and attributes & reparse)
                ):
                    raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
                actual_paths.add(node.relative_to(snapshot_root).as_posix())
        if actual_paths != expected_paths:
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
        if actual_directories != expected_directories:
            raise SnapshotError("SNAPSHOT_CONTENT_CHANGED")
    except SnapshotError:
        raise
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SnapshotError("SNAPSHOT_CONTENT_CHANGED") from exc
