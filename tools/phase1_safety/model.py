"""Closed shared primitives for Phase 1 safety verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Mapping


_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_NUMERIC = re.compile(r"^[1-9][0-9]*$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
_BRANCH = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class SafetyError(RuntimeError):
    """Stable public failure without sensitive exception details."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class SourceIdentity:
    repository: str
    repository_id: str
    default_branch: str
    workflow_ref: str
    source_sha: str
    workflow_sha: str
    run_id: str
    run_attempt: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def validate_source_identity(value: Mapping[str, object]) -> SourceIdentity:
    fields = {
        "repository",
        "repository_id",
        "default_branch",
        "workflow_ref",
        "source_sha",
        "workflow_sha",
        "run_id",
        "run_attempt",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise SafetyError("SOURCE_IDENTITY_INVALID")
    repository = value["repository"]
    repository_id = value["repository_id"]
    default_branch = value["default_branch"]
    workflow_ref = value["workflow_ref"]
    source_sha = value["source_sha"]
    workflow_sha = value["workflow_sha"]
    run_id = value["run_id"]
    run_attempt = value["run_attempt"]
    if (
        not isinstance(repository, str)
        or not _REPOSITORY.fullmatch(repository)
        or not isinstance(repository_id, str)
        or not _NUMERIC.fullmatch(repository_id)
        or not isinstance(default_branch, str)
        or not _BRANCH.fullmatch(default_branch)
        or not isinstance(workflow_ref, str)
        or workflow_ref != f"refs/heads/{default_branch}"
        or not isinstance(source_sha, str)
        or not _SHA40.fullmatch(source_sha)
        or not isinstance(workflow_sha, str)
        or workflow_sha != source_sha
        or not isinstance(run_id, str)
        or not _NUMERIC.fullmatch(run_id)
        or type(run_attempt) is not int
        or run_attempt < 1
    ):
        raise SafetyError("SOURCE_IDENTITY_INVALID")
    return SourceIdentity(
        repository=repository,
        repository_id=repository_id,
        default_branch=default_branch,
        workflow_ref=workflow_ref,
        source_sha=source_sha,
        workflow_sha=workflow_sha,
        run_id=run_id,
        run_attempt=run_attempt,
    )


def parse_utc(value: object) -> datetime:
    if not isinstance(value, str) or not _UTC.fullmatch(value):
        raise SafetyError("EVIDENCE_TIME_INVALID")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise SafetyError("EVIDENCE_TIME_INVALID") from error


def utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        raise SafetyError("EVIDENCE_TIME_INVALID")
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical_json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def atomic_write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".phase1-safety-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(canonical_json_bytes(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink(missing_ok=True)
        finally:
            raise
