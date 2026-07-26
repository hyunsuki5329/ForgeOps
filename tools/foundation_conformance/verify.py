from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import tempfile
from typing import Any
import copy
from datetime import datetime, timezone


class FoundationError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


EXPECTED_SAMPLE_FILES = (
    (
        "samples/forgeops-conformance/.gitattributes",
        "a79691a93b46e49ce460c26ef22afcc03d6eca1e63bf2edbc20e96159510f6c9",
        "PUBLIC_SAMPLE",
    ),
    (
        "samples/forgeops-conformance/README.fixture.md",
        "a30ca1ffd4411a1fdef33eef2118f96d4cd2593698e625faae7d7a38fb752ca5",
        "PUBLIC_SAMPLE",
    ),
    (
        "samples/forgeops-conformance/src/calculator.py",
        "0049214146c09e015865e54237ecc4d15c9e043886cb20d1d9c68659bf744bc9",
        "PUBLIC_SAMPLE",
    ),
    (
        "samples/forgeops-conformance/untrusted/instructions.txt",
        "36a9082bb3399c588207238e35d23d7127cce28a119699f2ac69630bc5a17563",
        "UNTRUSTED_DATA",
    ),
)
EXPECTED_SAMPLE_HASHES = {path: digest for path, digest, _ in EXPECTED_SAMPLE_FILES}
EXPECTED_SAMPLE_CLASSIFICATIONS = {
    path: classification for path, _, classification in EXPECTED_SAMPLE_FILES
}
EXPECTED_SAMPLE_PATHS = tuple(path for path, _, _ in EXPECTED_SAMPLE_FILES)

ENVELOPE_FIELDS = {
    "protocol_version",
    "packet_type",
    "task_id",
    "correlation_id",
    "base_revision",
    "actor",
    "status",
    "payload",
}
ACTOR_BY_PACKET = {
    "task": "main",
    "candidate_proposal": "part",
    "work_result": "work",
    "main_decision": "main",
}
ENVELOPE_STATUSES = {
    "PENDING",
    "IN_PROGRESS",
    "WAITING_FOR_HUMAN",
    "BLOCKED",
    "SUCCEEDED",
    "FAILED",
    "PARTIAL",
}
EFFECT_COUNTERS = (
    "policy_calls",
    "command_calls",
    "network_calls",
    "write_calls",
    "external_calls",
)
PROTOCOL_CASES = (
    ("positive-task-envelope", "PASSED"),
    ("positive-compatible-minor", "PASSED"),
    ("negative-unknown-major", "FOUNDATION_PROTOCOL_MISMATCH"),
    ("negative-actor-packet-mapping", "FOUNDATION_PROTOCOL_MISMATCH"),
    ("negative-envelope-unknown-field", "FOUNDATION_FIXTURE_INVALID"),
    ("negative-stale-revision", "FOUNDATION_PROTOCOL_MISMATCH"),
    ("negative-untrusted-authority-claim", "FOUNDATION_SEMANTICS_CHANGED"),
)
SAMPLE_CASES = (
    ("positive-source-manifest", "PASSED"),
    ("positive-adapter-equivalence", "PASSED"),
    ("negative-source-hash", "FOUNDATION_HASH_MISMATCH"),
    ("negative-source-path", "FOUNDATION_FIXTURE_INVALID"),
    ("negative-adapter-control-grant", "FOUNDATION_SEMANTICS_CHANGED"),
    ("negative-adapter-status-change", "FOUNDATION_SEMANTICS_CHANGED"),
    ("negative-catalog-reorder", "FOUNDATION_FIXTURE_INVALID"),
)

GATE_ID = "VG-001"
PROFILE_ID = "forgeops-foundation-conformance"
TRUSTED_MANIFEST = "fixtures/forgeops-foundation/source-manifest.json"
TRUSTED_SUITE = "fixtures/forgeops-foundation/suite.json"
TRUSTED_RESULTS = {
    "protocol-conformance": "artifacts/verification/vg-001-protocol-conformance-result.json",
    "sample-fixture": "artifacts/verification/vg-001-sample-fixture-result.json",
}
REGISTERED_ARGUMENTS = {"manifest", "suite", "result", "command_id"}


def _fixture_packet(
    protocol_version: str,
    task_id: str,
    correlation_id: str,
    base_revision: int,
    actor: str = "main",
    status: str = "PENDING",
    **extra_fields: Any,
) -> dict[str, Any]:
    return {
        "protocol_version": protocol_version,
        "packet_type": "task",
        "task_id": task_id,
        "correlation_id": correlation_id,
        "base_revision": base_revision,
        "actor": actor,
        "status": status,
        "payload": {"operation_mode": "EXPLORE"},
        **extra_fields,
    }


FIXTURE_PROTOCOL_PACKETS = {
    "positive-task-envelope": _fixture_packet("2.0", "TASK-FOUNDATION-001", "CORR-FOUNDATION-001", 4),
    "positive-compatible-minor": _fixture_packet("2.1", "TASK-FOUNDATION-002", "CORR-FOUNDATION-002", 4),
    "negative-unknown-major": _fixture_packet("3.0", "TASK-FOUNDATION-003", "CORR-FOUNDATION-003", 4),
    "negative-actor-packet-mapping": _fixture_packet("2.0", "TASK-FOUNDATION-004", "CORR-FOUNDATION-004", 4, actor="part"),
    "negative-envelope-unknown-field": _fixture_packet("2.0", "TASK-FOUNDATION-005", "CORR-FOUNDATION-005", 4, extra=True),
    "negative-stale-revision": _fixture_packet("2.0", "TASK-FOUNDATION-006", "CORR-FOUNDATION-006", 3),
    "negative-untrusted-authority-claim": _fixture_packet("2.0", "TASK-FOUNDATION-007", "CORR-FOUNDATION-007", 4),
}
FIXTURE_ADAPTER_PACKETS = {
    "positive-adapter-equivalence": {
        "expected": _fixture_packet("2.0", "TASK-FOUNDATION-008", "CORR-FOUNDATION-008", 4),
        "codex": _fixture_packet("2.0", "TASK-FOUNDATION-008", "CORR-FOUNDATION-008", 4),
        "copilot": _fixture_packet("2.0", "TASK-FOUNDATION-008", "CORR-FOUNDATION-008", 4),
    },
    "negative-adapter-control-grant": {
        "expected": _fixture_packet("2.0", "TASK-FOUNDATION-009", "CORR-FOUNDATION-009", 4),
        "codex": _fixture_packet("2.0", "TASK-FOUNDATION-009", "CORR-FOUNDATION-009", 4),
        "copilot": _fixture_packet("2.0", "TASK-FOUNDATION-009", "CORR-FOUNDATION-009", 4),
    },
    "negative-adapter-status-change": {
        "expected": _fixture_packet("2.0", "TASK-FOUNDATION-010", "CORR-FOUNDATION-010", 4),
        "codex": _fixture_packet("2.0", "TASK-FOUNDATION-010", "CORR-FOUNDATION-010", 4),
        "copilot": _fixture_packet("2.0", "TASK-FOUNDATION-010", "CORR-FOUNDATION-010", 4, status="SUCCEEDED"),
    },
}


class EffectSpy:
    """Records forbidden observable effects; evaluators must leave it unchanged."""

    def __init__(self) -> None:
        self.policy_calls = 0
        self.command_calls = 0
        self.network_calls = 0
        self.write_calls = 0
        self.external_calls = 0

    def as_dict(self) -> dict[str, int]:
        return {counter: getattr(self, counter) for counter in EFFECT_COUNTERS}


def _validate_effect_expectation(value: Any) -> dict[str, int]:
    assert_exact_fields(value, set(EFFECT_COUNTERS))
    if any(
        isinstance(value[counter], bool)
        or not isinstance(value[counter], int)
        or value[counter] < 0
        for counter in EFFECT_COUNTERS
    ):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    return value


def _require_case_spy(case: dict) -> None:
    expected = _validate_effect_expectation(case["expected_spy"])
    if expected != {counter: 0 for counter in EFFECT_COUNTERS}:
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")


def _validate_envelope(packet: Any, current_revision: Any = None) -> dict:
    assert_exact_fields(packet, ENVELOPE_FIELDS)
    packet_type = packet["packet_type"]
    if (
        not isinstance(packet_type, str)
        or ACTOR_BY_PACKET.get(packet_type) != packet["actor"]
    ):
        raise FoundationError("FOUNDATION_PROTOCOL_MISMATCH")
    if (
        not isinstance(packet["protocol_version"], str)
        or re.fullmatch(r"2\.[0-9]+", packet["protocol_version"]) is None
    ):
        raise FoundationError("FOUNDATION_PROTOCOL_MISMATCH")
    if any(
        not isinstance(packet[field], str) or not packet[field]
        for field in ("task_id", "correlation_id", "status")
    ) or packet["status"] not in ENVELOPE_STATUSES:
        raise FoundationError("FOUNDATION_PROTOCOL_MISMATCH")
    if (
        isinstance(packet["base_revision"], bool)
        or not isinstance(packet["base_revision"], int)
        or packet["base_revision"] < 0
        or not isinstance(packet["payload"], dict)
    ):
        raise FoundationError("FOUNDATION_PROTOCOL_MISMATCH")
    if ENVELOPE_FIELDS.intersection(packet["payload"]):
        raise FoundationError("FOUNDATION_PROTOCOL_MISMATCH")
    if current_revision is not None:
        if (
            isinstance(current_revision, bool)
            or not isinstance(current_revision, int)
            or current_revision < 0
            or packet["base_revision"] != current_revision
        ):
            raise FoundationError("FOUNDATION_PROTOCOL_MISMATCH")
    return copy.deepcopy(packet)


def _contains_control_grant(value: Any) -> bool:
    """Detect fixture attempts to let untrusted data change control semantics."""
    if isinstance(value, str):
        return bool(
            re.search(
                r"(?:ignore\s+policy|grant\s+(?:network\s+)?access|allow\s+network)",
                value,
                flags=re.IGNORECASE,
            )
        )
    if isinstance(value, list):
        return any(_contains_control_grant(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_control_grant(item) for item in value.values())
    return False


def validate_protocol_case(case: dict, spy: EffectSpy) -> dict:
    assert_exact_fields(
        case,
        {"id", "expected", "expected_spy", "packet", "current_revision", "untrusted_data"},
    )
    if not isinstance(case["id"], str) or not isinstance(case["expected"], str):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    if not isinstance(spy, EffectSpy):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    _require_case_spy(case)
    canonical = _validate_envelope(case["packet"], case["current_revision"])
    if _contains_control_grant(case["untrusted_data"]):
        raise FoundationError("FOUNDATION_SEMANTICS_CHANGED")
    return canonical


def normalize_adapter_case(adapter_input: dict) -> dict:
    if not isinstance(adapter_input, dict) or set(adapter_input) - {
        "canonical_packet", "transport", "untrusted_data"
    }:
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    if "canonical_packet" not in adapter_input:
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    canonical = _validate_envelope(adapter_input["canonical_packet"])
    if _contains_control_grant(adapter_input.get("untrusted_data")):
        raise FoundationError("FOUNDATION_SEMANTICS_CHANGED")
    return canonical


def validate_adapter_equivalence(case: dict, spy: EffectSpy) -> dict:
    assert_exact_fields(
        case, {"id", "expected", "expected_spy", "expected_canonical", "adapters"}
    )
    if (
        not isinstance(case["id"], str)
        or not isinstance(case["expected"], str)
        or not isinstance(spy, EffectSpy)
        or not isinstance(case["adapters"], dict)
        or set(case["adapters"]) != {"codex", "copilot"}
    ):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    _require_case_spy(case)
    expected = _validate_envelope(case["expected_canonical"])
    projections = [normalize_adapter_case(case["adapters"][name]) for name in ("codex", "copilot")]
    if any(projection != expected for projection in projections):
        raise FoundationError("FOUNDATION_SEMANTICS_CHANGED")
    return expected


def _validate_catalog(
    cases: Any,
    expected_catalog: tuple[tuple[str, str], ...],
    kind: str,
) -> None:
    if not isinstance(cases, list):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    if tuple((case.get("id"), case.get("expected")) if isinstance(case, dict) else (None, None) for case in cases) != expected_catalog:
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    for case in cases:
        base_fields = {"id", "expected", "expected_spy"}
        if kind == "protocol":
            allowed_fields = base_fields | {"packet", "current_revision", "untrusted_data"}
            if (
                set(case) != allowed_fields
                or case["packet"] != FIXTURE_PROTOCOL_PACKETS[case["id"]]
            ):
                raise FoundationError("FOUNDATION_FIXTURE_INVALID")
        elif "adapters" in case or "expected_canonical" in case:
            allowed_fields = base_fields | {"expected_canonical", "adapters"}
            expected_packets = FIXTURE_ADAPTER_PACKETS.get(case["id"])
            if (
                set(case) != allowed_fields
                or expected_packets is None
                or case["expected_canonical"] != expected_packets["expected"]
                or not isinstance(case["adapters"], dict)
                or set(case["adapters"]) != {"codex", "copilot"}
            ):
                raise FoundationError("FOUNDATION_FIXTURE_INVALID")
            for adapter_name, expected_packet in expected_packets.items():
                if adapter_name == "expected":
                    continue
                adapter = case["adapters"][adapter_name]
                if (
                    not isinstance(adapter, dict)
                    or set(adapter) - {"canonical_packet", "transport", "untrusted_data"}
                    or adapter.get("canonical_packet") != expected_packet
                ):
                    raise FoundationError("FOUNDATION_FIXTURE_INVALID")
        elif set(case) != base_fields:
            raise FoundationError("FOUNDATION_FIXTURE_INVALID")
        _validate_effect_expectation(case["expected_spy"])


def validate_fixture_suite(suite: dict) -> None:
    assert_exact_fields(suite, {"suite_id", "suite_version", "protocol_cases", "sample_cases"})
    if (
        suite["suite_id"] != "forgeops-foundation-conformance-v1"
        or suite["suite_version"] != "1.0"
    ):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    _validate_catalog(suite["protocol_cases"], PROTOCOL_CASES, "protocol")
    _validate_catalog(suite["sample_cases"], SAMPLE_CASES, "sample")


def load_fixture_suite(path: Path) -> dict:
    try:
        with path.open("r", encoding="utf-8", newline="") as source:
            suite = json.load(source)
    except (OSError, json.JSONDecodeError) as error:
        raise FoundationError("FOUNDATION_FIXTURE_INVALID") from error
    validate_fixture_suite(suite)
    return suite


def _evaluate_case(case: dict, spy: EffectSpy, validator: Any) -> dict[str, Any]:
    if (
        not isinstance(case, dict)
        or not isinstance(case.get("id"), str)
        or not isinstance(case.get("expected"), str)
        or "expected_spy" not in case
        or not isinstance(spy, EffectSpy)
    ):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    _validate_effect_expectation(case["expected_spy"])
    try:
        validator(case, spy)
        actual = "PASSED"
    except FoundationError as error:
        actual = error.code
    counters = spy.as_dict()
    status = (
        "PASSED"
        if actual == case["expected"] and counters == case["expected_spy"]
        else "FAILED"
    )
    return {
        "case_id": case["id"],
        "expected": case["expected"],
        "actual": actual,
        "status": status,
        **counters,
    }


def evaluate_protocol_case(case: dict, spy: EffectSpy) -> dict[str, Any]:
    return _evaluate_case(case, spy, validate_protocol_case)


def evaluate_adapter_case(case: dict, spy: EffectSpy) -> dict[str, Any]:
    return _evaluate_case(case, spy, validate_adapter_equivalence)


def load_source_manifest(path: Path) -> dict:
    with path.open("r", encoding="utf-8", newline="") as source:
        return json.load(source)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assert_exact_fields(value: Any, fields: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")


def _validate_literal_path(path: Any) -> str:
    if not isinstance(path, str) or not path:
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    if "\\" in path or os.path.isabs(path) or PureWindowsPath(path).is_absolute():
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    if any(character in path for character in "*?[]"):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    if path not in EXPECTED_SAMPLE_HASHES:
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    return path


def _sample_target_without_reparse_points(root: Path, path: str) -> Path:
    target = root
    for component in path.split("/"):
        target = target / component
        try:
            target_status = target.lstat()
        except OSError as error:
            raise FoundationError("FOUNDATION_FIXTURE_INVALID") from error
        is_reparse_point = bool(
            getattr(target_status, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
        if stat.S_ISLNK(target_status.st_mode) or is_reparse_point:
            raise FoundationError("FOUNDATION_FIXTURE_INVALID")
    return target


def verify_source_manifest(root: Path, manifest: dict) -> None:
    assert_exact_fields(
        manifest, {"manifest_id", "manifest_version", "root_ref", "files"}
    )
    if (
        manifest["manifest_id"] != "forgeops-foundation-sample-v1"
        or manifest["manifest_version"] != "1.0"
        or manifest["root_ref"] != "samples/forgeops-conformance"
        or not isinstance(manifest["files"], list)
    ):
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")

    observed_paths: list[str] = []
    for item in manifest["files"]:
        assert_exact_fields(item, {"path", "sha256", "classification"})
        observed_paths.append(_validate_literal_path(item["path"]))

    if tuple(observed_paths) != EXPECTED_SAMPLE_PATHS:
        raise FoundationError("FOUNDATION_FIXTURE_INVALID")

    for item in manifest["files"]:
        path = item["path"]
        if (
            item["sha256"] != EXPECTED_SAMPLE_HASHES[path]
            or item["classification"] != EXPECTED_SAMPLE_CLASSIFICATIONS[path]
        ):
            raise FoundationError("FOUNDATION_HASH_MISMATCH")
        target = _sample_target_without_reparse_points(root, path)
        if sha256_file(target) != item["sha256"]:
            raise FoundationError("FOUNDATION_HASH_MISMATCH")


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _observed_at() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def validate_registered_paths(args: argparse.Namespace) -> None:
    if not isinstance(args, argparse.Namespace) or set(vars(args)) != REGISTERED_ARGUMENTS:
        raise FoundationError("FOUNDATION_RUNNER_CONTRACT_INVALID")
    if (
        args.command_id not in TRUSTED_RESULTS
        or args.manifest != TRUSTED_MANIFEST
        or args.suite != TRUSTED_SUITE
        or args.result != TRUSTED_RESULTS[args.command_id]
    ):
        raise FoundationError("FOUNDATION_RUNNER_CONTRACT_INVALID")


def _input_hashes(root: Path, manifest: dict) -> dict[str, Any]:
    return {
        "manifest_sha256": sha256_file(root / TRUSTED_MANIFEST),
        "suite_sha256": sha256_file(root / TRUSTED_SUITE),
        "sample_files": {
            item["path"]: sha256_file(root / item["path"])
            for item in manifest["files"]
        },
    }


def _evaluate_sample_manifest_case(
    case: dict,
    spy: EffectSpy,
    root: Path,
    manifest: dict,
    suite: dict,
) -> dict[str, Any]:
    def validate(_: dict, __: EffectSpy) -> None:
        if case["id"] == "positive-source-manifest":
            verify_source_manifest(root, manifest)
        elif case["id"] == "negative-source-hash":
            altered = copy.deepcopy(manifest)
            altered["files"][0]["sha256"] = "0" * 64
            verify_source_manifest(root, altered)
        elif case["id"] == "negative-source-path":
            altered = copy.deepcopy(manifest)
            altered["files"][0]["path"] = "samples/forgeops-conformance/./.gitattributes"
            verify_source_manifest(root, altered)
        elif case["id"] == "negative-catalog-reorder":
            altered = copy.deepcopy(suite)
            altered["sample_cases"][0], altered["sample_cases"][1] = (
                altered["sample_cases"][1],
                altered["sample_cases"][0],
            )
            validate_fixture_suite(altered)
        else:
            validate_adapter_equivalence(case, spy)

    return _evaluate_case(case, spy, validate)


def _evaluate_registered_cases(
    command_id: str,
    root: Path,
    manifest: dict,
    suite: dict,
) -> list[dict[str, Any]]:
    if command_id == "protocol-conformance":
        return [
            evaluate_protocol_case(case, EffectSpy())
            for case in suite["protocol_cases"]
        ]
    if command_id == "sample-fixture":
        return [
            _evaluate_sample_manifest_case(case, EffectSpy(), root, manifest, suite)
            for case in suite["sample_cases"]
        ]
    raise FoundationError("FOUNDATION_RUNNER_CONTRACT_INVALID")


def _failed_result(
    command_id: str,
    observed_at: str,
    hashes: dict[str, Any],
    failure_code: str,
) -> dict[str, Any]:
    return {
        "gate_id": GATE_ID,
        "profile_id": PROFILE_ID,
        "command_id": command_id,
        "status": "FAILED",
        "observed_at": observed_at,
        "hashes": hashes,
        "failure_code": failure_code,
    }


def run_registered(
    command_id: str,
    *,
    observed_at: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    if command_id not in TRUSTED_RESULTS:
        raise FoundationError("FOUNDATION_RUNNER_CONTRACT_INVALID")
    run_root = _repository_root() if root is None else root
    run_observed_at = _observed_at() if observed_at is None else observed_at
    hashes: dict[str, Any] = {}
    try:
        manifest = load_source_manifest(run_root / TRUSTED_MANIFEST)
        suite = load_fixture_suite(run_root / TRUSTED_SUITE)
        verify_source_manifest(run_root, manifest)
        hashes = _input_hashes(run_root, manifest)
        cases = _evaluate_registered_cases(command_id, run_root, manifest, suite)
    except FoundationError as error:
        return _failed_result(command_id, run_observed_at, hashes, error.code)
    except (OSError, json.JSONDecodeError, TypeError, KeyError):
        return _failed_result(
            command_id,
            run_observed_at,
            hashes,
            "FOUNDATION_FIXTURE_INVALID",
        )

    passed = sum(case["status"] == "PASSED" for case in cases)
    failed = len(cases) - passed
    negative_effects_zero = all(
        all(case[counter] == 0 for counter in EFFECT_COUNTERS)
        for case in cases
        if case["expected"] != "PASSED"
    )
    return {
        "gate_id": GATE_ID,
        "profile_id": PROFILE_ID,
        "command_id": command_id,
        "status": "PASSED" if failed == 0 and negative_effects_zero else "FAILED",
        "observed_at": run_observed_at,
        "hashes": hashes,
        "summary": {"total": len(cases), "passed": passed, "failed": failed},
        "cases": cases,
        "assertions": {"negative_effects_zero": negative_effects_zero},
    }


def write_result_atomically(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".vg-001-", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
            json.dump(result, target, indent=2, sort_keys=True)
            target.write("\n")
        os.replace(temporary_name, path)
    except OSError:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--command-id", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        validate_registered_paths(args)
    except FoundationError as error:
        print(error.code, file=sys.stderr)
        return 2
    result = run_registered(args.command_id)
    write_result_atomically(_repository_root() / args.result, result)
    return 0 if result["status"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
