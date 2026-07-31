"""Pure, fail-closed evaluation of ForgeOps sandbox observations.

This module deliberately has no process, Docker, socket, or DNS dependency.
It evaluates only closed observations supplied by a runtime observer.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.sandbox_security import runtime


_RUNTIME_MODULE = runtime
_HAS_E3_CONSTRUCTION = runtime.has_e3_construction
_OBSERVE_E3 = runtime.observe_e3
_HAS_ATTESTED_E3_CONSTRUCTION = runtime.has_attested_e3_construction


_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _ROOT / "contracts/forgeops-sandbox-contract/1.0/schema.json"
_CATALOGS = ("image_cases", "containment_cases", "egress_cases", "quota_cases", "teardown_cases")
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PUBLIC_CASE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TRUSTED_ISSUER = runtime.LOCAL_TEST_ISSUER
EXTERNAL_E3_ISSUER = runtime.EXTERNAL_E3_ISSUER
_FRESHNESS_SECONDS = 300
_PUBLIC_ERROR_CODES = {
    "PASSED",
    "SANDBOX_IMAGE_PROVENANCE_INVALID",
    "SANDBOX_CONTAINMENT_VIOLATION",
    "SANDBOX_EGRESS_VIOLATION",
    "SANDBOX_QUOTA_VIOLATION",
    "SANDBOX_TEARDOWN_INCOMPLETE",
    "SANDBOX_EFFECT_CONTRACT_INVALID",
    "SANDBOX_RUNTIME_UNAVAILABLE",
    "SANDBOX_CASE_INVALID",
    "SANDBOX_OBSERVATION_INVALID",
    "SANDBOX_EVALUATION_INVALID",
}
TRUSTED_RESULTS = {
    "image-provenance-negative": "artifacts/verification/vg-008-image-provenance-result.json",
    "containment-egress-negative": "artifacts/verification/vg-008-containment-egress-result.json",
    "teardown-negative": "artifacts/verification/vg-008-teardown-result.json",
}
_REGISTERED_INPUTS = {
    "schema": "contracts/forgeops-sandbox-contract/1.0/schema.json",
    "suite": "fixtures/forgeops-sandbox-security/suite.json",
    "runtime_profile": "artifacts/runtime/sandbox-runtime-profile.json",
}
ATTESTED_OBSERVATIONS = "artifacts/runtime/sandbox-runtime-observations.json"
ATTESTED_RECEIPT = "artifacts/runtime/sandbox-e3-import-receipt.json"
_COMMAND_CATALOGS = {
    "image-provenance-negative": ("image_cases",),
    "containment-egress-negative": ("containment_cases", "egress_cases", "quota_cases"),
    "teardown-negative": ("teardown_cases",),
}
_FULL_INPUT_HASH_KEYS = frozenset({"schema_sha256", "suite_sha256", "runtime_profile_sha256"})
_MISSING_RUNTIME_PROFILE_HASH_KEYS = frozenset({"schema_sha256", "suite_sha256"})
_PUBLIC_NOT_RUN_CATEGORIES = {"SANDBOX_RUNTIME_UNAVAILABLE"}
_PUBLIC_RESIDUE_COUNTERS = {
    "processes": 0,
    "mounts": 0,
    "leases": 0,
    "transient_secrets": 0,
    "workspaces": 0,
}
_PUBLIC_EFFECT_COUNTERS = {
    "provision_calls": 0,
    "network_calls": 0,
    "write_calls": 0,
}


class SandboxError(Exception):
    """A stable sandbox evaluator rejection category."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _load_schema() -> dict[str, Any]:
    try:
        with _SCHEMA_PATH.open(encoding="utf-8") as source:
            schema = json.load(source)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SandboxError("SANDBOX_SCHEMA_INVALID") from error
    if not isinstance(schema, dict):
        raise SandboxError("SANDBOX_SCHEMA_INVALID")
    return schema


def _as_mapping(value: object) -> dict[str, Any]:
    if is_dataclass(value):
        value = asdict(value)
    if not isinstance(value, dict):
        raise SandboxError("SANDBOX_OBSERVATION_INVALID")
    return value


def _validate_schema(value: object, definition: str, failure_code: str) -> dict[str, Any]:
    checked = _as_mapping(value)
    try:
        runtime.schema_validator(_load_schema(), definition).validate(checked)
    except (KeyError, ValidationError) as error:
        raise SandboxError(failure_code) from error
    return checked


def _validate_suite_schema(suite: object) -> dict[str, Any]:
    checked = _as_mapping(suite)
    try:
        Draft202012Validator(_load_schema()).validate(checked)
    except ValidationError as error:
        raise SandboxError("SANDBOX_CASE_INVALID") from error
    return checked


def _parse_utc(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError
    return datetime.strptime(value, _TIMESTAMP_FORMAT)


def _is_known(value: object) -> bool:
    return isinstance(value, str) and value not in {"", "unavailable"}


def validate_runtime_profile(profile: dict, validation_at: str, *, expected_issuer: str = TRUSTED_ISSUER) -> None:
    """Deny an unavailable, uncontained, or unprovenanced runtime profile."""

    checked = _validate_schema(profile, "RuntimeProfile", "SANDBOX_RUNTIME_UNAVAILABLE")
    try:
        observed_at = _parse_utc(checked["observed_at"])
        validated_at = _parse_utc(validation_at)
    except (KeyError, TypeError, ValueError):
        raise SandboxError("SANDBOX_RUNTIME_UNAVAILABLE") from None
    age_seconds = (validated_at - observed_at).total_seconds()
    if not 0 <= age_seconds <= _FRESHNESS_SECONDS or not checked["available"]:
        raise SandboxError("SANDBOX_RUNTIME_UNAVAILABLE")
    image_digest = checked["image_digest"]
    if (
        not isinstance(image_digest, str)
        or _DIGEST.fullmatch(image_digest) is None
        or checked["image_ref"].rsplit("@", 1)[-1] != image_digest
        or not checked["signature_verified"]
        or not _is_known(checked["issuer"])
        or checked["issuer"] != expected_issuer
        or not _is_known(checked["provenance_ref"])
    ):
        raise SandboxError("SANDBOX_IMAGE_PROVENANCE_INVALID")
    if not checked["rootless"]:
        raise SandboxError("SANDBOX_CONTAINMENT_VIOLATION")


def is_forbidden_address(value: str) -> bool:
    """Identify non-public destinations without resolving names or opening sockets."""

    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return True
    return not address.is_global


def _validate_effect_counts(case: dict[str, Any], observation: dict[str, Any]) -> None:
    for effect in ("provision_calls", "network_calls", "write_calls"):
        if observation[effect] != case[f"expected_{effect}"]:
            raise SandboxError("SANDBOX_EFFECT_CONTRACT_INVALID")


def evaluate_observation(case: dict, observation: dict, validation_at: str) -> None:
    """Evaluate a closed observation in containment-to-teardown deny order."""

    checked_case = _validate_schema(case, "SandboxCase", "SANDBOX_CASE_INVALID")
    checked_observation = _validate_schema(observation, "RuntimeObservation", "SANDBOX_OBSERVATION_INVALID")
    try:
        observed_at = _parse_utc(checked_observation["observed_at"])
        trusted_validation_at = _parse_utc(validation_at)
    except (KeyError, TypeError, ValueError):
        raise SandboxError("SANDBOX_RUNTIME_UNAVAILABLE") from None
    if not 0 <= (trusted_validation_at - observed_at).total_seconds() <= _FRESHNESS_SECONDS:
        raise SandboxError("SANDBOX_RUNTIME_UNAVAILABLE")
    if checked_observation["case_id"] != checked_case["id"]:
        raise SandboxError("SANDBOX_OBSERVATION_INVALID")
    _validate_effect_counts(checked_case, checked_observation)
    if checked_observation["root_uid"] == 0 or not checked_observation["rootfs_read_only"]:
        raise SandboxError("SANDBOX_CONTAINMENT_VIOLATION")
    if not checked_observation["cap_drop_all"] or not checked_observation["no_new_privileges"]:
        raise SandboxError("SANDBOX_CONTAINMENT_VIOLATION")
    if checked_observation["forbidden_mounts"] or checked_observation["forbidden_devices"]:
        raise SandboxError("SANDBOX_CONTAINMENT_VIOLATION")
    if checked_observation["direct_dns_calls"] or checked_observation["direct_socket_calls"]:
        raise SandboxError("SANDBOX_EGRESS_VIOLATION")
    if checked_observation["redirects"] or any(
        is_forbidden_address(address) for address in checked_observation["connected_addresses"]
    ):
        raise SandboxError("SANDBOX_EGRESS_VIOLATION")
    if checked_case["case_kind"] == "egress" and (
        checked_observation["proxy_calls"] != 1
        or checked_observation["proxy_destination"] != checked_case["expected_proxy_destination"]
    ):
        raise SandboxError("SANDBOX_EGRESS_VIOLATION")
    if checked_case["case_kind"] != "egress" and (
        checked_observation["proxy_calls"] != 0 or checked_observation["proxy_destination"] != ""
    ):
        raise SandboxError("SANDBOX_EGRESS_VIOLATION")
    if checked_observation["quota_exceeded"]:
        raise SandboxError("SANDBOX_QUOTA_VIOLATION")
    if any(checked_observation["residue"].values()):
        raise SandboxError("SANDBOX_TEARDOWN_INCOMPLETE")


def _safe_observation_fields(observation: object) -> tuple[str, int, int, int]:
    checked = _as_mapping(observation)
    return (
        str(checked.get("evidence_kind", "unknown")),
        int(checked.get("provision_calls", 0)) if isinstance(checked.get("provision_calls"), int) else 0,
        int(checked.get("network_calls", 0)) if isinstance(checked.get("network_calls"), int) else 0,
        int(checked.get("write_calls", 0)) if isinstance(checked.get("write_calls"), int) else 0,
    )


def public_case(
    case_id: str,
    expected: str,
    actual: str,
    observation: dict,
    *,
    trusted_runtime_observer: bool = False,
) -> dict[str, Any]:
    """Project an observation into fixed public-safe case metadata only."""

    if not isinstance(case_id, str) or _PUBLIC_CASE_ID.fullmatch(case_id) is None:
        raise SandboxError("SANDBOX_PUBLIC_RESULT_UNSAFE")
    if actual not in _PUBLIC_ERROR_CODES:
        actual = "SANDBOX_EVALUATION_INVALID"
    try:
        evidence_kind, provision_calls, network_calls, write_calls = _safe_observation_fields(observation)
    except SandboxError:
        actual = "SANDBOX_EVALUATION_INVALID"
        evidence_kind, provision_calls, network_calls, write_calls = "unknown", 0, 0, 0
    if actual == "SANDBOX_RUNTIME_UNAVAILABLE" or evidence_kind != "runtime" or not trusted_runtime_observer:
        status = "NOT_RUN"
    elif expected == actual:
        status = "PASSED"
    else:
        status = "FAILED"
    return {
        "case_id": case_id,
        "expected": expected,
        "actual": actual,
        "status": status,
        "runtime_evidence": evidence_kind == "runtime" and trusted_runtime_observer,
        "provision_calls": provision_calls,
        "network_calls": network_calls,
        "write_calls": write_calls,
    }


def _public_error_code(error: SandboxError) -> str:
    return error.code if error.code in _PUBLIC_ERROR_CODES else "SANDBOX_EVALUATION_INVALID"


def run_cases(
    command_id: str,
    suite: dict,
    observer: runtime.RuntimeObserver,
    validation_at: str,
) -> list[dict]:
    """Run the closed catalogs using only injected observations.

    Image profiles are validated before their corresponding observation is
    requested, so a provenance denial never reaches a provision boundary.
    """

    if not isinstance(command_id, str) or not command_id:
        raise SandboxError("SANDBOX_CASE_INVALID")
    checked_suite = _validate_suite_schema(suite)
    try:
        _parse_utc(validation_at)
    except (TypeError, ValueError):
        raise SandboxError("SANDBOX_RUNTIME_UNAVAILABLE") from None
    local_e3 = _HAS_E3_CONSTRUCTION(observer)
    # Imported E3 authority is intentionally not accepted on this public,
    # injectable API.  The isolated consumer owns that trust boundary.
    imported_e3 = False
    trusted_runtime_observer = local_e3 or imported_e3
    imported_profile = observer.runtime_profile() if imported_e3 else None
    results: list[dict] = []
    for catalog in _CATALOGS:
        for case in checked_suite[catalog]:
            observation: object = {
                "evidence_kind": "runtime" if imported_e3 and case["case_kind"] == "image_provenance" else "unknown",
                "provision_calls": 0,
                "network_calls": 0,
                "write_calls": 0,
            }
            try:
                if case["case_kind"] == "image_provenance":
                    profile = case["runtime_profile"]
                    issuer = TRUSTED_ISSUER
                    if imported_e3:
                        profile = dict(imported_profile)
                        if case["id"] == "negative-tag-only":
                            profile["image_ref"] = profile["image_ref"].split("@", 1)[0] + ":latest"
                        elif case["id"] == "negative-signature-unverified":
                            profile["signature_verified"] = False
                        elif case["id"] == "negative-issuer-mismatch":
                            profile["issuer"] = "untrusted-issuer"
                        issuer = EXTERNAL_E3_ISSUER
                    validate_runtime_profile(profile, validation_at, expected_issuer=issuer)
                observation = (
                    _OBSERVE_E3(observer, case)
                    if local_e3
                    else observer.observe(case)
                )
                evaluate_observation(case, observation, validation_at)
            except runtime.RuntimeUnavailable as error:
                actual = error.code if error.code in _PUBLIC_ERROR_CODES else "SANDBOX_RUNTIME_UNAVAILABLE"
            except SandboxError as error:
                actual = _public_error_code(error)
            except Exception:
                actual = "SANDBOX_RUNTIME_UNAVAILABLE"
            else:
                actual = "PASSED"
            results.append(
                public_case(
                    case["id"],
                    case["expected"],
                    actual,
                    observation,
                    trusted_runtime_observer=trusted_runtime_observer,
                )
            )
    return results


def _public_timestamp() -> str:
    """Return a public UTC generation time without observing a sandbox runtime."""

    return datetime.utcnow().replace(microsecond=0).strftime(_TIMESTAMP_FORMAT)


def _input_sha256(path: Path) -> str:
    """Hash an explicitly supplied public input without retaining its contents."""

    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_not_run(command_id: str, category: str, *, input_hashes: Mapping[str, str]) -> dict[str, Any]:
    """Build a closed public result for an unavailable sandbox runtime."""

    if command_id not in TRUSTED_RESULTS or category not in _PUBLIC_NOT_RUN_CATEGORIES:
        raise SandboxError("SANDBOX_PUBLIC_RESULT_UNSAFE")
    if (
        not isinstance(input_hashes, Mapping)
        or set(input_hashes) not in {_FULL_INPUT_HASH_KEYS, _MISSING_RUNTIME_PROFILE_HASH_KEYS}
        or any(
        not isinstance(key, str) or not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        for key, value in input_hashes.items()
        )
    ):
        raise SandboxError("SANDBOX_PUBLIC_RESULT_UNSAFE")
    return {
        "result_version": "1.0",
        "command_id": command_id,
        "runtime": "docker",
        "status": "NOT_RUN",
        "category": category,
        "time": _public_timestamp(),
        "input_hashes": dict(sorted(input_hashes.items())),
        "counts": {"cases_total": 0, "passed": 0, "failed": 0, "not_run": 0},
        "e3_runtime_assertion": False,
        "effect_counters": dict(_PUBLIC_EFFECT_COUNTERS),
        "residue_counters": dict(_PUBLIC_RESIDUE_COUNTERS),
    }


def _admit_registered_cli_literals(
    *,
    schema: str,
    suite: str,
    runtime_profile: str,
    runtime: str,
    command_id: str,
    result: str,
    project_root: Path,
) -> tuple[Path, Path, Path, Path]:
    """Admit only exact registered literals before resolving or reading paths."""

    if (
        type(command_id) is not str
        or command_id not in TRUSTED_RESULTS
        or type(runtime) is not str
        or runtime != "docker"
        or type(schema) is not str
        or schema != _REGISTERED_INPUTS["schema"]
        or type(suite) is not str
        or suite != _REGISTERED_INPUTS["suite"]
        or type(runtime_profile) is not str
        or runtime_profile != _REGISTERED_INPUTS["runtime_profile"]
        or type(result) is not str
        or result != TRUSTED_RESULTS[command_id]
    ):
        raise SandboxError("SANDBOX_PUBLIC_RESULT_UNSAFE")
    root = project_root.resolve(strict=True)
    return (
        root / _REGISTERED_INPUTS["schema"],
        root / _REGISTERED_INPUTS["suite"],
        root / _REGISTERED_INPUTS["runtime_profile"],
        root / TRUSTED_RESULTS[command_id],
    )


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    """Atomically replace an already-authorized public result file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".sandbox-result-", suffix=".json", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as target:
            json.dump(value, target, ensure_ascii=True, indent=2, sort_keys=True)
            target.write("\n")
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _write_admitted_not_run(command_id: str, schema_path: Path, suite_path: Path, runtime_profile_path: Path, output: Path) -> int:
    """Write the only public parent result; this path never evaluates imported E3."""
    try:
        input_hashes = {
            "schema_sha256": _input_sha256(schema_path),
            "suite_sha256": _input_sha256(suite_path),
        }
    except OSError as error:
        raise SandboxError("SANDBOX_PUBLIC_RESULT_UNSAFE") from error
    try:
        input_hashes["runtime_profile_sha256"] = _input_sha256(runtime_profile_path)
    except OSError:
        pass
    _atomic_write_json(output, safe_not_run(command_id, "SANDBOX_RUNTIME_UNAVAILABLE", input_hashes=input_hashes))
    return 2


def run_cli(
    *, schema: str, suite: str, runtime_profile: str, runtime: str, result: str,
    command_id: str, project_root: Path = _ROOT,
) -> int:
    """Public callable: only write a closed capability-gap result, never consume E3."""
    schema_path, suite_path, runtime_profile_path, output = _admit_registered_cli_literals(
        schema=schema, suite=suite, runtime_profile=runtime_profile, runtime=runtime,
        result=result, command_id=command_id, project_root=project_root,
    )
    return _write_admitted_not_run(command_id, schema_path, suite_path, runtime_profile_path, output)


def _install_cli_main():
    """Keep exec capability and consumer path out of the public callable surface."""
    execv = os.execv
    platform_name = os.name
    interpreter = str(Path(sys.executable).resolve(strict=True))
    project_root = _ROOT.resolve(strict=True)
    consumer_path = Path(__file__).with_name("e3_consumer.py").resolve()

    def consumer_argv(command_id: str) -> list[str]:
        return [
            interpreter, "-I", str(consumer_path), "--project-root",
            str(project_root), "--command-id", command_id,
        ]

    def cli_main(argv: list[str] | None = None) -> int:
        """Replace this process with the only authority allowed to consume E3."""
        parser = argparse.ArgumentParser(description="ForgeOps VG-008 sandbox verifier")
        parser.add_argument("--schema", required=True)
        parser.add_argument("--suite", required=True)
        parser.add_argument("--runtime-profile", required=True)
        parser.add_argument("--runtime", required=True, choices=("docker",))
        parser.add_argument("--result", required=True)
        parser.add_argument("--command-id", required=True, choices=tuple(TRUSTED_RESULTS))
        arguments = parser.parse_args(argv)
        try:
            schema_path, suite_path, runtime_profile_path, output = _admit_registered_cli_literals(
                schema=arguments.schema, suite=arguments.suite, runtime_profile=arguments.runtime_profile,
                runtime=arguments.runtime, result=arguments.result, command_id=arguments.command_id,
                project_root=project_root,
            )
            if platform_name == "posix":
                execv(interpreter, consumer_argv(arguments.command_id))
        except SandboxError as error:
            parser.error(error.code)
        except OSError:
            pass
        return _write_admitted_not_run(arguments.command_id, schema_path, suite_path, runtime_profile_path, output)

    return consumer_argv, cli_main


consumer_argv, main = _install_cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
