"""Shared primitives for the ForgeOps interface-contract checks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


class ContractError(Exception):
    """A stable public API contract rejection."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def load_json(path: Path) -> dict[str, Any]:
    """Load UTF-8 JSON-compatible YAML and require an object root."""
    try:
        with path.open("r", encoding="utf-8") as stream:
            value = json.load(stream)
    except (OSError, json.JSONDecodeError) as exc:
        raise ContractError("API_SCHEMA_INVALID") from exc
    if not isinstance(value, dict):
        raise ContractError("API_SCHEMA_INVALID")
    return value


def assert_exact_fields(
    value: dict[str, Any], required: set[str], optional: set[str], code: str
) -> None:
    """Reject missing and unknown fields without changing the supplied object."""
    if not isinstance(value, dict) or not required.issubset(value) or set(value) - required - optional:
        raise ContractError(code)


def sha256_file(path: Path) -> str:
    """Return the SHA-256 digest for a file using bounded binary reads."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def is_strict_utc(value: object) -> bool:
    """Accept only an exact UTC second timestamp in the API wire format."""
    if not isinstance(value, str):
        return False
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ) == value
    except ValueError:
        return False
