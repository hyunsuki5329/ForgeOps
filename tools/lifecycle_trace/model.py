from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any


CANONICAL_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
CANONICAL_REF = re.compile(r"^(EVID|ART)-[A-Z0-9-]+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class LifecycleError(RuntimeError):
    """Stable, public-safe lifecycle rejection."""

    def __init__(self, code: str):
        if not CANONICAL_NAME.fullmatch(code):
            raise ValueError("error code must be canonical")
        self.code = code
        super().__init__(code)


def canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str

