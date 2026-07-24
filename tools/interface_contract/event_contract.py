"""In-memory validation for the ForgeOps durable event wrapper."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from .common import ContractError, is_strict_utc


EVENT_ERROR_CODES = (
    "EVENT_SCHEMA_INVALID",
    "EVENT_IDENTITY_MISMATCH",
    "EVENT_STREAM_OUT_OF_ORDER",
    "EVENT_CANONICAL_SEQUENCE_INVALID",
    "EVENT_REVISION_MISMATCH",
    "EVENT_OWNER_INVALID",
    "EVENT_PROVENANCE_INVALID",
    "EVENT_REFERENCE_INVALID",
    "EVENT_TIMESTAMP_INVALID",
)


class AppendSpy:
    """In-memory append counter used to prove fail-closed stream validation."""

    def __init__(self) -> None:
        self.calls = 0

    def append(self, _record: dict[str, Any]) -> None:
        self.calls += 1


def validate_event_record(
    record: dict[str, Any],
    schema: dict[str, Any],
    source_main_decisions: dict[str, dict[str, Any]] | None = None,
) -> None:
    """Validate one closed wrapper without assigning or rewriting event state."""
    try:
        validator = Draft202012Validator(schema)
        errors = list(validator.iter_errors(record))
    except (SchemaError, TypeError, ValueError) as exc:
        raise ContractError("EVENT_SCHEMA_INVALID") from exc
    if errors:
        reference_paths = [tuple(error.absolute_path) for error in errors]
        if all(
            len(path) >= 2 and path[:2] == ("canonical_event", "evidence_refs")
            for path in reference_paths
        ):
            raise ContractError("EVENT_REFERENCE_INVALID")
        raise ContractError("EVENT_SCHEMA_INVALID")

    canonical_event = record["canonical_event"]
    if (
        canonical_event["task_id"] != record["task_id"]
        or canonical_event["correlation_id"] != record["correlation_id"]
    ):
        raise ContractError("EVENT_IDENTITY_MISMATCH")

    if record["provenance"]["source_kind"] != "MAIN_DECISION":
        raise ContractError("EVENT_OWNER_INVALID")

    if source_main_decisions is not None:
        provenance = record["provenance"]
        source = source_main_decisions.get(provenance["source_ref"])
        required_source_fields = {
            "source_kind",
            "task_id",
            "correlation_id",
            "content_sha256",
        }
        if (
            not isinstance(source, dict)
            or set(source) != required_source_fields
            or source["source_kind"] != "MAIN_DECISION"
            or source["task_id"] != record["task_id"]
            or source["correlation_id"] != record["correlation_id"]
            or source["content_sha256"] != provenance["content_sha256"]
        ):
            raise ContractError("EVENT_PROVENANCE_INVALID")

    if not is_strict_utc(record["recorded_at"]):
        raise ContractError("EVENT_TIMESTAMP_INVALID")

    evidence_refs = canonical_event["evidence_refs"]
    if any(not reference for reference in evidence_refs) or len(evidence_refs) != len(
        set(evidence_refs)
    ):
        raise ContractError("EVENT_REFERENCE_INVALID")


def validate_revisions_and_state_events(
    records: list[dict[str, Any]], source_revisions: dict[str, int] | None
) -> None:
    """Require trusted revision parity and Main-owned state acceptance."""
    event_ids = [record["event_id"] for record in records]
    if not isinstance(source_revisions, dict) or set(source_revisions) != set(event_ids):
        raise ContractError("EVENT_REVISION_MISMATCH")

    accepted_revisions: list[int] = []
    state_accepted_revisions: set[int] = set()
    for record in records:
        source_revision = source_revisions.get(record["event_id"])
        accepted_revision = record["accepted_revision"]
        if (
            not isinstance(source_revision, int)
            or isinstance(source_revision, bool)
            or source_revision != accepted_revision
        ):
            raise ContractError("EVENT_REVISION_MISMATCH")
        accepted_revisions.append(accepted_revision)

        canonical_event = record["canonical_event"]
        if canonical_event["code"] == "STATE_ACCEPTED":
            if canonical_event["actor"] != "main":
                raise ContractError("EVENT_OWNER_INVALID")
            if accepted_revision in state_accepted_revisions:
                raise ContractError("EVENT_REVISION_MISMATCH")
            state_accepted_revisions.add(accepted_revision)

    if any(
        current < previous
        for previous, current in zip(accepted_revisions, accepted_revisions[1:])
    ):
        raise ContractError("EVENT_REVISION_MISMATCH")


def validate_event_stream(
    records: list[dict[str, Any]],
    schema: dict[str, Any],
    source_revisions: dict[str, int] | None = None,
    append_spy: AppendSpy | None = None,
    source_main_decisions: dict[str, dict[str, Any]] | None = None,
) -> str:
    """Validate a complete stream before performing any append observation."""
    for record in records:
        validate_event_record(record, schema, source_main_decisions)

    stream_sequences = [record["stream_seq"] for record in records]
    task_identities = {
        (record["task_id"], record["correlation_id"]) for record in records
    }
    stream_identities = {
        (record["run_id"], record["stream_id"]) for record in records
    }
    if records and len(task_identities) != 1:
        raise ContractError("EVENT_IDENTITY_MISMATCH")
    if (
        not records
        or stream_sequences != list(range(1, len(records) + 1))
        or len(stream_identities) != 1
    ):
        raise ContractError("EVENT_STREAM_OUT_OF_ORDER")

    canonical_sequences = [record["canonical_event"]["seq"] for record in records]
    if any(
        current <= previous
        for previous, current in zip(canonical_sequences, canonical_sequences[1:])
    ):
        raise ContractError("EVENT_CANONICAL_SEQUENCE_INVALID")

    validate_revisions_and_state_events(records, source_revisions)

    if append_spy is not None:
        for record in records:
            append_spy.append(record)
    return "PASSED"


__all__ = [
    "AppendSpy",
    "ContractError",
    "EVENT_ERROR_CODES",
    "validate_event_record",
    "validate_event_stream",
    "validate_revisions_and_state_events",
]
