from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import html
import json
import re

from .model import CANONICAL_NAME, CANONICAL_REF, LifecycleError, canonical_hash


ACTORS = ("MAIN", "PART", "WORK", "SYSTEM")
PHASES = ("CONTROL", "ANALYSIS", "EXECUTION", "TERMINAL")
CODES = ("TASK_ACCEPTED", "CLEANUP_VERIFIED", "BUDGET_STOPPED", "RUN_CANCELLED",
         "RUN_COMPLETED", "EXTERNAL_WRITE_DENIED")
EVENT_KEYS = {"seq", "revision", "actor", "phase", "code", "observed_at",
              "evidence_refs", "artifact_refs"}
NEXT_ACTIONS = {
    "SUCCESS": ("CLOSE",),
    "USER_CANCELLED": ("STOP",),
    "BUDGET_STOPPED": ("WAIT_FOR_HUMAN",),
    "NO_PROGRESS_STOPPED": ("WAIT_FOR_HUMAN",),
}
RESOURCE_KINDS = ("processes", "mounts", "leases", "transient_secrets", "workspaces")
BUDGET_DIMENSIONS = ("time_ms", "tokens", "tool_calls", "command_calls",
                     "repair_attempts", "cost_microunits")
SECRET_PATTERN = re.compile(r"(?i)(?:gh[pousr]_[A-Za-z0-9]{20,}|(?:token|password|secret)\s*[:=]\s*\S+)")


class TraceManifest:
    def __init__(self, identities: dict[str, str], *, evidence_catalog: tuple[str, ...],
                 artifact_catalog: tuple[str, ...], budget: dict[str, object] | None = None,
                 observed_at: str = "1970-01-01T00:00:00Z"):
        self.identities = dict(identities)
        self.evidence_catalog = tuple(evidence_catalog)
        self.artifact_catalog = tuple(artifact_catalog)
        self.budget = deepcopy(budget) if budget is not None else {
            "state": "ACTIVE",
            "usage": {"time_ms": 0, "tokens": 0, "tool_calls": 0, "command_calls": 0,
                      "repair_attempts": 0, "cost_microunits": 0},
            "limits": {"time_ms": 1000, "tokens": 100, "tool_calls": 4,
                       "command_calls": 3, "repair_attempts": 2, "cost_microunits": 500},
        }
        self.observed_at = observed_at
        self.events: list[dict[str, object]] = []
        self.terminal: dict[str, object] | None = None
        self.cleanup: dict[str, object] | None = None
        self._manifest_hash: str | None = None

    def append(self, actor: str, event_type: str, revision: int, *,
               evidence_refs: tuple[str, ...] = (), artifact_refs: tuple[str, ...] = (),
               phase: str | None = None, observed_at: str | None = None) -> None:
        if self.terminal is not None:
            raise LifecycleError("TRACE_EVENT_INVALID")
        if (actor not in ACTORS or not isinstance(event_type, str)
                or event_type not in CODES
                or not isinstance(revision, int) or isinstance(revision, bool) or revision < 0):
            if actor not in ACTORS:
                raise LifecycleError("TRACE_ACTOR_INVALID")
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
                raise LifecycleError("TRACE_REVISION_INVALID")
            raise LifecycleError("TRACE_EVENT_INVALID")
        selected_phase = phase or {"MAIN": "CONTROL", "PART": "ANALYSIS",
                                   "WORK": "EXECUTION", "SYSTEM": "TERMINAL"}[actor]
        if selected_phase not in PHASES:
            raise LifecycleError("TRACE_EVENT_INVALID")
        self.events.append({"seq": len(self.events) + 1, "revision": revision,
                            "actor": actor, "phase": selected_phase, "code": event_type,
                            "observed_at": observed_at or self.observed_at,
                            "evidence_refs": list(evidence_refs),
                            "artifact_refs": list(artifact_refs)})

    def finalize(self, reason: str, next_actions: tuple[str, ...],
                 cleanup: dict[str, object]) -> None:
        self.terminal = {"reason": reason, "next_actions": list(next_actions)}
        self.cleanup = deepcopy(cleanup)
        self.budget["state"] = {"SUCCESS": "COMPLETED", "USER_CANCELLED": "CANCELLED"}.get(reason, "STOPPED")
        self._manifest_hash = canonical_hash(self._body())

    def _body(self) -> dict[str, object]:
        return {"manifest_version": "1.0", "identities": deepcopy(self.identities),
                "evidence_catalog": list(self.evidence_catalog),
                "artifact_catalog": list(self.artifact_catalog), "budget": deepcopy(self.budget),
                "events": deepcopy(self.events), "terminal": deepcopy(self.terminal),
                "cleanup": deepcopy(self.cleanup)}

    def to_dict(self) -> dict[str, object]:
        return {**self._body(), "manifest_hash": self._manifest_hash}

    def validate(self) -> dict[str, object]:
        identity_patterns = {"task_id": r"TASK-[A-Z0-9-]+", "run_id": r"RUN-[A-Z0-9-]+",
                             "correlation_id": r"CORR-[A-Z0-9-]+"}
        if (set(self.identities) != set(identity_patterns)
                or any(not isinstance(self.identities[key], str)
                       or not re.fullmatch(pattern, self.identities[key])
                       for key, pattern in identity_patterns.items())):
            raise LifecycleError("TRACE_IDENTITY_INVALID")
        if (not self.evidence_catalog or len(set(self.evidence_catalog)) != len(self.evidence_catalog)
                or any(not CANONICAL_REF.fullmatch(ref) or not ref.startswith("EVID-") for ref in self.evidence_catalog)
                or not self.artifact_catalog or len(set(self.artifact_catalog)) != len(self.artifact_catalog)
                or any(not CANONICAL_REF.fullmatch(ref) or not ref.startswith("ART-") for ref in self.artifact_catalog)):
            raise LifecycleError("TRACE_REFERENCE_INVALID")
        if [event.get("seq") for event in self.events] != list(range(1, len(self.events) + 1)):
            raise LifecycleError("TRACE_SEQUENCE_INVALID")
        previous = -1
        for event in self.events:
            if set(event) != EVENT_KEYS or event.get("code") not in CODES or event.get("phase") not in PHASES:
                raise LifecycleError("TRACE_EVENT_INVALID")
            revision = event.get("revision")
            if (not isinstance(revision, int) or isinstance(revision, bool)
                    or revision < previous):
                raise LifecycleError("TRACE_REVISION_INVALID")
            previous = revision
            if event.get("actor") not in ACTORS:
                raise LifecycleError("TRACE_ACTOR_INVALID")
            timestamp = event.get("observed_at")
            if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
                raise LifecycleError("TRACE_TIME_INVALID")
            try:
                parsed = datetime.fromisoformat(timestamp[:-1] + "+00:00")
            except ValueError as error:
                raise LifecycleError("TRACE_TIME_INVALID") from error
            if parsed.tzinfo != timezone.utc:
                raise LifecycleError("TRACE_TIME_INVALID")
            evidence = event.get("evidence_refs")
            artifacts = event.get("artifact_refs")
            if (not isinstance(evidence, list) or not set(evidence).issubset(self.evidence_catalog)
                    or not isinstance(artifacts, list) or not set(artifacts).issubset(self.artifact_catalog)):
                raise LifecycleError("TRACE_REFERENCE_INVALID")
        if (not isinstance(self.cleanup, dict) or set(self.cleanup) not in ({"remaining"}, {"released", "remaining"})
                or not isinstance(self.cleanup.get("remaining"), dict)):
            raise LifecycleError("TRACE_CLEANUP_INVALID")
        remaining = self.cleanup["remaining"]
        if set(remaining) != set(RESOURCE_KINDS) or any(remaining[kind] != 0 for kind in RESOURCE_KINDS):
            raise LifecycleError("TRACE_CLEANUP_INVALID")
        if "released" in self.cleanup:
            released = self.cleanup["released"]
            if (not isinstance(released, dict) or set(released) != set(RESOURCE_KINDS)
                    or any(not isinstance(released[kind], int) or isinstance(released[kind], bool)
                           or released[kind] < 0 for kind in RESOURCE_KINDS)):
                raise LifecycleError("TRACE_CLEANUP_INVALID")
        if (not isinstance(self.terminal, dict) or not isinstance(self.terminal.get("reason"), str)
                or not self.terminal["reason"]):
            raise LifecycleError("TRACE_TERMINAL_INVALID")
        if set(self.terminal) != {"reason", "next_actions"}:
            raise LifecycleError("TRACE_MANIFEST_INVALID")
        reason = self.terminal["reason"]
        actions = self.terminal.get("next_actions")
        expected = NEXT_ACTIONS.get(reason)
        if expected is None or actions != list(expected):
            raise LifecycleError("TRACE_NEXT_ACTION_INVALID")
        if (not isinstance(self.budget, dict) or set(self.budget) != {"state", "usage", "limits"}
                or self.budget["state"] not in {"ACTIVE", "COMPLETED", "CANCELLED", "STOPPED"}
                or not isinstance(self.budget["usage"], dict)
                or set(self.budget["usage"]) != set(BUDGET_DIMENSIONS)
                or any(not isinstance(self.budget["usage"][key], int)
                       or isinstance(self.budget["usage"][key], bool)
                       or self.budget["usage"][key] < 0 for key in BUDGET_DIMENSIONS)
                or not isinstance(self.budget["limits"], dict)
                or set(self.budget["limits"]) != set(BUDGET_DIMENSIONS)
                or any(not isinstance(self.budget["limits"][key], int)
                       or isinstance(self.budget["limits"][key], bool)
                       or self.budget["limits"][key] <= 0 for key in BUDGET_DIMENSIONS)):
            raise LifecycleError("TRACE_MANIFEST_INVALID")
        if self._manifest_hash != canonical_hash(self._body()):
            raise LifecycleError("TRACE_MANIFEST_INVALID")
        return self.to_dict()


def render_trace_html(manifest: dict[str, object]) -> str:
    rows = []
    for event in manifest.get("events", []):
        cells = (event.get("seq"), event.get("revision"), event.get("actor"),
                 event.get("phase"), event.get("code"), event.get("observed_at"),
                 ", ".join(event.get("evidence_refs", [])),
                 ", ".join(event.get("artifact_refs", [])))
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>")
    terminal = manifest.get("terminal") or {}
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<title>ForgeOps W8 Trace</title><style>body{font:14px system-ui;margin:2rem}"
            "table{border-collapse:collapse}th,td{border:1px solid #bbb;padding:.4rem}</style>"
            "</head><body><h1>ForgeOps W8 Trace</h1>"
            f"<p>Terminal: {html.escape(str(terminal.get('reason', 'UNSET')))}</p>"
            f"<p>Next Actions: {html.escape(', '.join(terminal.get('next_actions', [])))}</p>"
            f"<h2>Budget</h2><pre>{html.escape(json.dumps(manifest.get('budget', {}), sort_keys=True))}</pre>"
            f"<h2>Cleanup</h2><pre>{html.escape(json.dumps(manifest.get('cleanup', {}), sort_keys=True))}</pre>"
            "<table><thead><tr><th>Seq</th><th>Revision</th><th>Actor</th><th>Phase</th>"
            "<th>Code</th><th>Observed At</th>"
            "<th>Evidence</th><th>Artifacts</th></tr></thead><tbody>"
            + "".join(rows) + "</tbody></table></body></html>\n")


class ExternalWriteGate:
    def __init__(self, *, expected_approval: str, allowed_target: str):
        self.expected_approval = expected_approval
        self.allowed_target = allowed_target
        self._authorized_effects: set[str] = set()

    def authorize(self, action: str, target: str | None, via_gateway: bool,
                  approval: str | None, effect_id: str | None) -> str:
        if action == "NONE":
            if any((target is not None, via_gateway, approval is not None, effect_id is not None)):
                raise LifecycleError("EXTERNAL_ACTION_FORBIDDEN")
            return "PASSED"
        if action != "APPROVED_EXTERNAL_WRITE":
            raise LifecycleError("EXTERNAL_ACTION_FORBIDDEN")
        if via_gateway is not True:
            raise LifecycleError("EXTERNAL_GATEWAY_REQUIRED")
        if target != self.allowed_target:
            raise LifecycleError("EXTERNAL_TARGET_INVALID")
        if approval is None:
            raise LifecycleError("EXTERNAL_APPROVAL_REQUIRED")
        if approval != self.expected_approval:
            raise LifecycleError("EXTERNAL_APPROVAL_INVALID")
        if not isinstance(effect_id, str) or not re.fullmatch(r"EFFECT-[A-Z0-9-]+", effect_id):
            raise LifecycleError("EXTERNAL_TARGET_INVALID")
        if effect_id in self._authorized_effects:
            raise LifecycleError("EXTERNAL_EFFECT_DUPLICATE")
        self._authorized_effects.add(effect_id)
        return "AUTHORIZED"

    def audit(self, *, denial_required: bool, denial_traced: bool,
              effect_observed: bool, public_text: str) -> None:
        if denial_required and not denial_traced:
            raise LifecycleError("EXTERNAL_DENIAL_TRACE_MISSING")
        if effect_observed:
            raise LifecycleError("EXTERNAL_EFFECT_OBSERVED")
        if not isinstance(public_text, str) or SECRET_PATTERN.search(public_text):
            raise LifecycleError("RESULT_SECRET_DETECTED")
