"""Deterministic public scorecards for the Phase 1 safety decision."""

from __future__ import annotations

from html import escape
import os
from pathlib import Path
import tempfile
from typing import Callable, Mapping

from .model import SafetyError, canonical_json_bytes


Replace = Callable[[str | Path, str | Path], object]


def _decision_rows(decision: Mapping[str, object]) -> list[Mapping[str, object]]:
    gates = decision.get("gates")
    if not isinstance(gates, list) or len(gates) != 19 or not all(isinstance(row, Mapping) for row in gates):
        raise SafetyError("SCORECARD_INPUT_INVALID")
    return gates


def render_scorecard_markdown(decision: Mapping[str, object]) -> str:
    rows = _decision_rows(decision)
    summary = decision["summary"]
    effects = decision["effect_counters"]
    lines = [
        "# ForgeOps Phase 1 Safety Scorecard",
        "",
        f"- Status: `{decision['status']}`",
        f"- Evidence tier: `{decision['evidence_tier']}`",
        f"- Validated at: `{decision['validated_at']}`",
        f"- Source SHA: `{decision['source_identity']['source_sha']}`",
        f"- Coverage: `{summary['passed']}/{summary['total']}`",
        f"- Blockers: `{summary['blockers']}`",
        "",
        "| Gate | Command | Status | Tier | Observed at | Artifact | Blockers |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        blockers = ", ".join(row["blocker_codes"]) or "-"
        lines.append(
            f"| {row['gate_id']} | {row['command_id']} | {row['status']} | "
            f"{row['observed_tier'] or '-'} | {row['observed_at'] or '-'} | "
            f"{row['artifact_ref']} | {blockers} |"
        )
    lines.extend(["", "## Normalized effects", ""])
    for key, value in effects.items():
        lines.append(f"- {key}: `{value}`")
    lines.append("")
    return "\n".join(lines)


def render_scorecard_html(decision: Mapping[str, object]) -> str:
    rows = _decision_rows(decision)
    summary = decision["summary"]
    cells = []
    for row in rows:
        blockers = ", ".join(row["blocker_codes"]) or "-"
        values = (
            row["gate_id"], row["command_id"], row["status"], row["observed_tier"] or "-",
            row["observed_at"] or "-", row["artifact_ref"], blockers,
        )
        cells.append("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in values) + "</tr>")
    effects = "".join(
        f"<li>{escape(str(key))}: <code>{escape(str(value))}</code></li>"
        for key, value in decision["effect_counters"].items()
    )
    return (
        "<!doctype html>\n<html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<title>ForgeOps Phase 1 Safety Scorecard</title></head><body>"
        "<h1>ForgeOps Phase 1 Safety Scorecard</h1>"
        f"<dl><dt>Status</dt><dd><code>{escape(str(decision['status']))}</code></dd>"
        f"<dt>Evidence tier</dt><dd><code>{escape(str(decision['evidence_tier']))}</code></dd>"
        f"<dt>Validated at</dt><dd><code>{escape(str(decision['validated_at']))}</code></dd>"
        f"<dt>Source SHA</dt><dd><code>{escape(str(decision['source_identity']['source_sha']))}</code></dd>"
        f"<dt>Coverage</dt><dd><code>{summary['passed']}/{summary['total']}</code></dd>"
        f"<dt>Blockers</dt><dd><code>{summary['blockers']}</code></dd></dl>"
        "<table><thead><tr><th>Gate</th><th>Command</th><th>Status</th><th>Tier</th>"
        "<th>Observed at</th><th>Artifact</th><th>Blockers</th></tr></thead><tbody>"
        + "".join(cells)
        + "</tbody></table><h2>Normalized effects</h2><ul>"
        + effects
        + "</ul></body></html>\n"
    )


def atomic_publish_scorecard(
    result_path: Path,
    markdown_path: Path,
    html_path: Path,
    decision: Mapping[str, object],
    *,
    replacer: Replace = os.replace,
) -> None:
    """Publish one generation or invalidate the complete output set."""

    payloads = (
        (result_path, canonical_json_bytes(decision)),
        (markdown_path, render_scorecard_markdown(decision).encode("utf-8")),
        (html_path, render_scorecard_html(decision).encode("utf-8")),
    )
    staged: list[tuple[Path, Path]] = []
    try:
        for target, content in payloads:
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(prefix=".phase1-scorecard-", dir=target.parent)
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            staged.append((temporary, target))
        for temporary, target in staged:
            replacer(temporary, target)
    except Exception as error:
        for target, _content in payloads:
            target.unlink(missing_ok=True)
        raise SafetyError("SCORECARD_WRITE_FAILED") from error
    finally:
        for temporary, _target in staged:
            temporary.unlink(missing_ok=True)
