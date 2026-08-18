from __future__ import annotations

from copy import deepcopy
import html
import json
import re

from .model import CANONICAL_NAME, CANONICAL_REF, LifecycleError


ACTORS = ("MAIN", "PART", "WORK", "SYSTEM")
NEXT_ACTIONS = {
    "SUCCESS": ("CLOSE",),
    "USER_CANCELLED": ("STOP",),
    "BUDGET_STOPPED": ("WAIT_FOR_HUMAN",),
    "NO_PROGRESS_STOPPED": ("WAIT_FOR_HUMAN",),
}
RESOURCE_KINDS = ("processes", "mounts", "leases", "transient_secrets", "workspaces")
SECRET_PATTERN = re.compile(r"(?i)(?:gh[pousr]_[A-Za-z0-9]{20,}|(?:token|password|secret)\s*[:=]\s*\S+)")


class TraceManifest:
    def __init__(self, identities: dict[str, str], *, evidence_catalog: tuple[str, ...],
                 artifact_catalog: tuple[str, ...]):
        self.identities = dict(identities)
        self.evidence_catalog = tuple(evidence_catalog)
        self.artifact_catalog = tuple(artifact_catalog)
        self.events: list[dict[str, object]] = []
        self.terminal: dict[str, object] | None = None
        self.cleanup: dict[str, object] | None = None

    def append(self, actor: str, event_type: str, revision: int, *,
               evidence_refs: tuple[str, ...] = (), artifact_refs: tuple[str, ...] = ()) -> None:
        if (actor not in ACTORS or not isinstance(event_type, str)
                or not CANONICAL_NAME.fullmatch(event_type)
                or not isinstance(revision, int) or isinstance(revision, bool) or revision < 0):
            raise LifecycleError("TRACE_ACTOR_INVALID" if actor not in ACTORS else "TRACE_REVISION_INVALID")
        self.events.append({"seq": len(self.events) + 1, "revision": revision,
                            "actor": actor, "event_type": event_type,
                            "evidence_refs": list(evidence_refs),
                            "artifact_refs": list(artifact_refs)})

    def finalize(self, reason: str, next_actions: tuple[str, ...],
                 cleanup: dict[str, object]) -> None:
        self.terminal = {"reason": reason, "next_actions": list(next_actions)}
        self.cleanup = deepcopy(cleanup)

    def to_dict(self) -> dict[str, object]:
        return {"manifest_version": "1.0", "identities": deepcopy(self.identities),
                "evidence_catalog": list(self.evidence_catalog),
                "artifact_catalog": list(self.artifact_catalog),
                "events": deepcopy(self.events), "terminal": deepcopy(self.terminal),
                "cleanup": deepcopy(self.cleanup)}

    def validate(self) -> dict[str, object]:
        if [event.get("seq") for event in self.events] != list(range(1, len(self.events) + 1)):
            raise LifecycleError("TRACE_SEQUENCE_INVALID")
        previous = -1
        for event in self.events:
            revision = event.get("revision")
            if (not isinstance(revision, int) or isinstance(revision, bool)
                    or revision < previous):
                raise LifecycleError("TRACE_REVISION_INVALID")
            previous = revision
            if event.get("actor") not in ACTORS:
                raise LifecycleError("TRACE_ACTOR_INVALID")
            evidence = event.get("evidence_refs")
            artifacts = event.get("artifact_refs")
            if (not isinstance(evidence, list) or not set(evidence).issubset(self.evidence_catalog)
                    or not isinstance(artifacts, list) or not set(artifacts).issubset(self.artifact_catalog)):
                raise LifecycleError("TRACE_REFERENCE_INVALID")
        if not isinstance(self.cleanup, dict) or not isinstance(self.cleanup.get("remaining"), dict):
            raise LifecycleError("TRACE_CLEANUP_INVALID")
        remaining = self.cleanup["remaining"]
        if set(remaining) != set(RESOURCE_KINDS) or any(remaining[kind] != 0 for kind in RESOURCE_KINDS):
            raise LifecycleError("TRACE_CLEANUP_INVALID")
        if (not isinstance(self.terminal, dict) or not isinstance(self.terminal.get("reason"), str)
                or not self.terminal["reason"]):
            raise LifecycleError("TRACE_TERMINAL_INVALID")
        reason = self.terminal["reason"]
        actions = self.terminal.get("next_actions")
        expected = NEXT_ACTIONS.get(reason)
        if expected is None or actions != list(expected):
            raise LifecycleError("TRACE_NEXT_ACTION_INVALID")
        return self.to_dict()


def render_trace_html(manifest: dict[str, object]) -> str:
    rows = []
    for event in manifest.get("events", []):
        cells = (event.get("seq"), event.get("revision"), event.get("actor"),
                 event.get("event_type"), ", ".join(event.get("evidence_refs", [])),
                 ", ".join(event.get("artifact_refs", [])))
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>")
    terminal = manifest.get("terminal") or {}
    return ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<title>ForgeOps W8 Trace</title><style>body{font:14px system-ui;margin:2rem}"
            "table{border-collapse:collapse}th,td{border:1px solid #bbb;padding:.4rem}</style>"
            "</head><body><h1>ForgeOps W8 Trace</h1>"
            f"<p>Terminal: {html.escape(str(terminal.get('reason', 'UNSET')))}</p>"
            "<table><thead><tr><th>Seq</th><th>Revision</th><th>Actor</th><th>Event</th>"
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
