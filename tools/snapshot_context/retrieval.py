from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path, PurePosixPath
import re
from typing import Mapping, Sequence

from jsonschema import Draft202012Validator

from .model import SnapshotError, sha256_bytes
from .snapshot import _read_stable_regular_file, verify_snapshot


MAX_QUERY_TOKENS = 32
MAX_TOP_K = 20
MAX_TEXT_BYTES = 256 * 1024
MAX_EXCERPT_CHARACTERS = 1024
REASON_ORDER = ("PATH_EXACT", "PATH_SUBSTRING", "CONTENT_MATCH")
REASON_SCORE = {"PATH_EXACT": 1000, "PATH_SUBSTRING": 100, "CONTENT_MATCH": 1}


def tokenize_query(query: str) -> Sequence[str]:
    if not isinstance(query, str):
        raise SnapshotError("CONTEXT_QUERY_INVALID")
    tokens: list[str] = []
    seen: set[str] = set()
    for raw in re.findall(r"[^\W_]+", query.casefold(), flags=re.UNICODE):
        if raw not in seen:
            seen.add(raw)
            tokens.append(raw)
    if not 1 <= len(tokens) <= MAX_QUERY_TOKENS:
        raise SnapshotError("CONTEXT_QUERY_INVALID")
    return tokens


def _excerpt(text: str, tokens: Sequence[str]) -> str:
    lowered = text.casefold()
    positions = [lowered.find(token) for token in tokens]
    positions = [position for position in positions if position >= 0]
    center = min(positions) if positions else 0
    start = max(0, center - MAX_EXCERPT_CHARACTERS // 2)
    end = min(len(text), start + MAX_EXCERPT_CHARACTERS)
    if end - start < MAX_EXCERPT_CHARACTERS:
        start = max(0, end - MAX_EXCERPT_CHARACTERS)
    return text[start:end]


def _context_schema() -> Mapping[str, object]:
    path = (
        Path(__file__).resolve().parents[2]
        / "contracts"
        / "forgeops-context-pack"
        / "1.0"
        / "schema.json"
    )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotError("CONTEXT_PROVENANCE_INVALID") from exc


def build_context_pack(
    snapshot_root: Path,
    manifest: Mapping[str, object],
    query: str,
    *,
    top_k: int = 10,
) -> dict[str, object]:
    if type(top_k) is not int or not 1 <= top_k <= MAX_TOP_K:
        raise SnapshotError("CONTEXT_QUERY_INVALID")
    tokens = tokenize_query(query)
    snapshot_root = Path(snapshot_root)
    try:
        verify_snapshot(snapshot_root, manifest)
    except SnapshotError as exc:
        raise SnapshotError("CONTEXT_PROVENANCE_INVALID") from exc
    snapshot_root = Path(os.path.abspath(snapshot_root))
    raw_entries = manifest.get("entries")
    if not isinstance(raw_entries, list):
        raise SnapshotError("CONTEXT_PROVENANCE_INVALID")

    candidates: list[dict[str, object]] = []
    excluded_binary = 0
    excluded_oversized = 0
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, Mapping):
            raise SnapshotError("CONTEXT_PROVENANCE_INVALID")
        path_text = raw_entry.get("path")
        expected_hash = raw_entry.get("sha256")
        expected_size = raw_entry.get("size")
        if not isinstance(path_text, str) or not isinstance(expected_hash, str):
            raise SnapshotError("CONTEXT_PROVENANCE_INVALID")
        if type(expected_size) is not int:
            raise SnapshotError("CONTEXT_PROVENANCE_INVALID")
        relative = Path(*PurePosixPath(path_text).parts)
        try:
            content, _ = _read_stable_regular_file(snapshot_root, relative)
        except SnapshotError as exc:
            raise SnapshotError("CONTEXT_PROVENANCE_INVALID") from exc
        if len(content) != expected_size or sha256_bytes(content) != expected_hash:
            raise SnapshotError("CONTEXT_PROVENANCE_INVALID")
        if len(content) > MAX_TEXT_BYTES:
            excluded_oversized += 1
            continue
        if b"\x00" in content:
            excluded_binary += 1
            continue
        try:
            text = content.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            excluded_binary += 1
            continue

        folded_path = path_text.casefold()
        path = PurePosixPath(path_text)
        exact_values = {folded_path, path.name.casefold(), path.stem.casefold()}
        folded_text = text.casefold()
        exact = any(token in exact_values for token in tokens)
        substring = any(token in folded_path for token in tokens)
        content_match = any(token in folded_text for token in tokens)
        matched = {
            "PATH_EXACT": exact,
            "PATH_SUBSTRING": substring,
            "CONTENT_MATCH": content_match,
        }
        reasons = [reason for reason in REASON_ORDER if matched[reason]]
        if not reasons:
            continue
        media_type = mimetypes.guess_type(path_text)[0] or "text/plain"
        candidates.append(
            {
                "path": path_text,
                "sha256": expected_hash,
                "size": expected_size,
                "media_type": media_type,
                "selection_reason": reasons,
                "score": sum(REASON_SCORE[reason] for reason in reasons),
                "excerpt": _excerpt(text, tokens),
                "trust": "UNTRUSTED_SOURCE",
            }
        )

    candidates.sort(key=lambda item: (-int(item["score"]), str(item["path"])))
    selected = candidates[:top_k]
    pack: dict[str, object] = {
        "context_pack_version": "1.0",
        "snapshot_id": manifest.get("snapshot_id"),
        "query_tokens": list(tokens),
        "items": selected,
        "summary": {
            "selected": len(selected),
            "excluded_binary": excluded_binary,
            "excluded_oversized": excluded_oversized,
        },
        "control_claims_accepted": False,
    }
    if list(Draft202012Validator(_context_schema()).iter_errors(pack)):
        raise SnapshotError("CONTEXT_PROVENANCE_INVALID")
    return pack
