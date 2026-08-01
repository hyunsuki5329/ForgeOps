from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import threading
from typing import Callable, Mapping, Sequence

from jsonschema import Draft202012Validator

from .model import SnapshotError, canonical_json_bytes, sha256_bytes
from .snapshot import verify_snapshot


PROFILE_FIELDS = {"profile_id", "profile_version", "commands"}
COMMAND_FIELDS = {
    "command_id",
    "argv",
    "cwd",
    "timeout_seconds",
    "max_output_bytes",
}
SHELL_IDENTITY_CHARACTERS = frozenset("|&;<>*?")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _profile_error() -> SnapshotError:
    return SnapshotError("BASELINE_PROFILE_INVALID")


def _valid_text(value: object, *, maximum: int) -> bool:
    return isinstance(value, str) and bool(value) and len(value) <= maximum


def _valid_cwd(value: object) -> bool:
    if not isinstance(value, str) or not value or "\\" in value or "//" in value:
        return False
    if value == ".":
        return True
    path = PurePosixPath(value)
    return not path.is_absolute() and ".." not in path.parts and "." not in path.parts


def validate_profile(profile: Mapping[str, object]) -> Sequence[dict[str, object]]:
    if not isinstance(profile, Mapping) or set(profile) != PROFILE_FIELDS:
        raise _profile_error()
    if not _valid_text(profile.get("profile_id"), maximum=200):
        raise _profile_error()
    if not _valid_text(profile.get("profile_version"), maximum=50):
        raise _profile_error()
    raw_commands = profile.get("commands")
    if not isinstance(raw_commands, list) or not raw_commands:
        raise _profile_error()
    result: list[dict[str, object]] = []
    identifiers: set[str] = set()
    for raw in raw_commands:
        if not isinstance(raw, Mapping) or set(raw) != COMMAND_FIELDS:
            raise _profile_error()
        command_id = raw.get("command_id")
        if not _valid_text(command_id, maximum=200) or command_id in identifiers:
            raise _profile_error()
        identifiers.add(command_id)
        argv = raw.get("argv")
        if (
            not isinstance(argv, list)
            or not argv
            or any(not _valid_text(item, maximum=4096) for item in argv)
        ):
            raise _profile_error()
        executable = argv[0]
        if any(character in executable for character in SHELL_IDENTITY_CHARACTERS):
            raise _profile_error()
        cwd = raw.get("cwd")
        if not _valid_cwd(cwd):
            raise _profile_error()
        timeout = raw.get("timeout_seconds")
        output_cap = raw.get("max_output_bytes")
        if type(timeout) is not int or not 1 <= timeout <= 300:
            raise _profile_error()
        if type(output_cap) is not int or not 1024 <= output_cap <= 1_048_576:
            raise _profile_error()
        result.append(
            {
                "command_id": command_id,
                "argv": list(argv),
                "cwd": cwd,
                "timeout_seconds": timeout,
                "max_output_bytes": output_cap,
            }
        )
    return result


def _minimal_environment() -> dict[str, str]:
    permitted = (
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "TMP",
        "TEMP",
        "LANG",
        "LC_ALL",
    )
    environment = {key: os.environ[key] for key in permitted if key in os.environ}
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def _resolved_cwd(workspace_root: Path, raw: str) -> Path:
    relative = Path() if raw == "." else Path(*PurePosixPath(raw).parts)
    candidate = workspace_root / relative
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(workspace_root)
    except (OSError, ValueError) as exc:
        raise _profile_error() from exc
    current = workspace_root
    for component in relative.parts:
        current = current / component
        if current.is_symlink():
            raise _profile_error()
    if not resolved.is_dir():
        raise _profile_error()
    return resolved


def _fingerprint(result: Mapping[str, object]) -> str:
    public_identity = {
        key: result[key]
        for key in (
            "command_id",
            "argv",
            "cwd",
            "status",
            "exit_code",
            "output_truncated",
        )
    }
    return sha256_bytes(canonical_json_bytes(public_identity))


def _command_result(
    command: Mapping[str, object],
    status: str,
    exit_code: int | None,
    stdout_bytes: int,
    stderr_bytes: int,
    truncated: bool,
) -> dict[str, object]:
    result: dict[str, object] = {
        "command_id": command["command_id"],
        "argv": list(command["argv"]),
        "cwd": command["cwd"],
        "status": status,
        "exit_code": exit_code,
        "stdout_bytes_seen": stdout_bytes,
        "stderr_bytes_seen": stderr_bytes,
        "output_truncated": truncated,
    }
    result["result_fingerprint"] = _fingerprint(result)
    return result


def _execute(
    command: Mapping[str, object],
    workspace_root: Path,
    popen_factory: Callable,
) -> dict[str, object]:
    cwd = _resolved_cwd(workspace_root, str(command["cwd"]))
    counts = {"stdout": 0, "stderr": 0}
    lock = threading.Lock()
    truncated = [False]
    cap = int(command["max_output_bytes"])
    try:
        process = popen_factory(
            list(command["argv"]),
            cwd=cwd,
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_minimal_environment(),
        )
    except (OSError, subprocess.SubprocessError):
        return _command_result(command, "BASELINE_RUNNER_ERROR", None, 0, 0, False)

    def drain(name: str, stream) -> None:
        try:
            while True:
                block = stream.read(8192)
                if not block:
                    return
                with lock:
                    counts[name] += len(block)
                    if counts["stdout"] + counts["stderr"] > cap:
                        truncated[0] = True
        finally:
            stream.close()

    readers = [
        threading.Thread(target=drain, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=drain, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()
    status: str
    try:
        exit_code = process.wait(timeout=int(command["timeout_seconds"]))
        status = "PASSED" if exit_code == 0 else "BASELINE_UNHEALTHY"
    except subprocess.TimeoutExpired:
        status = "BASELINE_TIMEOUT"
        exit_code = None
        try:
            process.terminate()
            process.wait(timeout=1)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=1)
            except (OSError, subprocess.SubprocessError):
                pass
    except (OSError, subprocess.SubprocessError):
        status = "BASELINE_RUNNER_ERROR"
        exit_code = None
        try:
            process.kill()
        except OSError:
            pass
    for reader in readers:
        reader.join(timeout=2)
    return _command_result(
        command,
        status,
        exit_code,
        counts["stdout"],
        counts["stderr"],
        truncated[0],
    )


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_artifact(artifact: Mapping[str, object]) -> None:
    schema_path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "forgeops-snapshot-contract"
        / "1.0"
        / "schema.json"
    )
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))["$defs"][
            "baseline_artifact"
        ]
        errors = list(Draft202012Validator(schema).iter_errors(artifact))
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise SnapshotError("BASELINE_RUNNER_ERROR") from exc
    if errors:
        raise SnapshotError("BASELINE_RUNNER_ERROR")


def run_baseline(
    workspace_root: Path,
    manifest: Mapping[str, object],
    profile: Mapping[str, object],
    *,
    popen_factory: Callable = subprocess.Popen,
    clock: Callable[[], datetime] = utc_now,
) -> dict[str, object]:
    workspace_root = Path(workspace_root).resolve()
    verify_snapshot(workspace_root, manifest)
    commands = validate_profile(profile)
    started_at = clock()
    results: list[dict[str, object]] = []
    stop = False
    for command in commands:
        if stop:
            results.append(_command_result(command, "NOT_RUN", None, 0, 0, False))
            continue
        result = _execute(command, workspace_root, popen_factory)
        results.append(result)
        if result["status"] in ("BASELINE_TIMEOUT", "BASELINE_RUNNER_ERROR"):
            stop = True
    statuses = [str(item["status"]) for item in results]
    if "BASELINE_RUNNER_ERROR" in statuses:
        overall = "BASELINE_RUNNER_ERROR"
    elif "BASELINE_TIMEOUT" in statuses:
        overall = "BASELINE_TIMEOUT"
    elif "BASELINE_UNHEALTHY" in statuses:
        overall = "BASELINE_UNHEALTHY"
    else:
        overall = "PASSED"
    artifact: dict[str, object] = {
        "baseline_version": "1.0",
        "snapshot_id": manifest.get("snapshot_id"),
        "profile_id": profile.get("profile_id"),
        "profile_version": profile.get("profile_version"),
        "status": overall,
        "started_at": _timestamp(started_at),
        "completed_at": _timestamp(clock()),
        "commands": results,
        "summary": {
            "total": len(results),
            "passed": statuses.count("PASSED"),
            "failed": sum(
                status not in ("PASSED", "NOT_RUN") for status in statuses
            ),
            "not_run": statuses.count("NOT_RUN"),
        },
    }
    _validate_artifact(artifact)
    return artifact
