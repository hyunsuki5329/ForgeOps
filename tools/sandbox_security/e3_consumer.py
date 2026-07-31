"""Private, isolated consumer for imported VG-008 E3 evidence.

Only the public verifier launches this module.  Its two arguments identify a
fixed project root and one registered result; every evidence path is derived
inside this process so an injectable caller cannot provide an observer or
replace evidence after it has been snapshotted.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

_SOURCE_ROOT = Path(__file__).resolve().parents[2]
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

from jsonschema import Draft202012Validator
from tools.sandbox_security import runtime, verify


_FIXED_INPUTS = {
    "schema": "contracts/forgeops-sandbox-contract/1.0/schema.json",
    "suite": "fixtures/forgeops-sandbox-security/suite.json",
    "profile": "artifacts/runtime/sandbox-runtime-profile.json",
    "observations": "artifacts/runtime/sandbox-runtime-observations.json",
    "receipt": "artifacts/runtime/sandbox-e3-import-receipt.json",
    "attestation": "artifacts/runtime/e3-attestation.json",
    "bundle": "artifacts/runtime/e3-attestation.bundle.json",
}


def _timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _snapshot(root: Path, directory: Path) -> dict[str, Path]:
    """Copy each fixed input exactly once before hashing, parsing, or evaluating."""
    snapshots: dict[str, Path] = {}
    for name, relative in _FIXED_INPUTS.items():
        source = root / relative
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        snapshots[name] = target
    return snapshots


def _hashes(snapshots: dict[str, Path]) -> dict[str, str]:
    return {
        "schema_sha256": hashlib.sha256(snapshots["schema"].read_bytes()).hexdigest(),
        "suite_sha256": hashlib.sha256(snapshots["suite"].read_bytes()).hexdigest(),
        "runtime_profile_sha256": hashlib.sha256(snapshots["profile"].read_bytes()).hexdigest(),
    }


def _image_profile(profile: dict[str, Any], case_id: str) -> dict[str, Any]:
    projected = dict(profile)
    if case_id == "negative-tag-only":
        projected["image_ref"] = projected["image_ref"].split("@", 1)[0] + ":latest"
    elif case_id == "negative-signature-unverified":
        projected["signature_verified"] = False
    elif case_id == "negative-issuer-mismatch":
        projected["issuer"] = "untrusted-issuer"
    return projected


def _evaluate_snapshot(snapshots: dict[str, Path], command_id: str, validation_at: str) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Evaluate one private snapshot; no observer enters this function."""
    schema_bytes = snapshots["schema"].read_bytes()
    suite_bytes = snapshots["suite"].read_bytes()
    schema = json.loads(schema_bytes.decode("utf-8"))
    suite = json.loads(suite_bytes.decode("utf-8"))
    Draft202012Validator(schema).validate(suite)
    observer = runtime.AttestedRuntimeObserver.from_imported_files(
        snapshots["profile"], snapshots["observations"], snapshots["receipt"], validation_at,
    )
    if not runtime.has_attested_e3_construction(observer):
        raise runtime.RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
    profile = observer.runtime_profile()
    selected: list[dict[str, Any]] = []
    for catalog in verify._COMMAND_CATALOGS[command_id]:
        for case in suite[catalog]:
            observation: object = {"evidence_kind": "unknown", "provision_calls": 0, "network_calls": 0, "write_calls": 0}
            try:
                if case["case_kind"] == "image_provenance":
                    verify.validate_runtime_profile(_image_profile(profile, case["id"]), validation_at, expected_issuer=verify.EXTERNAL_E3_ISSUER)
                observation = observer.observe(case)
                verify.evaluate_observation(case, observation, validation_at)
            except runtime.RuntimeUnavailable as error:
                actual = error.code if error.code in verify._PUBLIC_ERROR_CODES else "SANDBOX_RUNTIME_UNAVAILABLE"
            except verify.SandboxError as error:
                actual = verify._public_error_code(error)
            except Exception:
                actual = "SANDBOX_RUNTIME_UNAVAILABLE"
            else:
                actual = "PASSED"
            selected.append(verify.public_case(case["id"], case["expected"], actual, observation, trusted_runtime_observer=True))
    if any(item["status"] != "PASSED" for item in selected):
        raise runtime.RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
    return selected, _hashes(snapshots)


def _not_run(command_id: str, hashes: dict[str, str], output: Path) -> int:
    verify._atomic_write_json(output, verify.safe_not_run(command_id, "SANDBOX_RUNTIME_UNAVAILABLE", input_hashes=hashes))
    return 2


def consume(project_root: Path, command_id: str) -> int:
    """Evaluate fixed evidence and atomically write only the registered result."""
    if type(command_id) is not str or command_id not in verify.TRUSTED_RESULTS:
        return 2
    try:
        root = Path(project_root).resolve(strict=True)
        output = root / verify.TRUSTED_RESULTS[command_id]
        output.unlink(missing_ok=True)
    except (OSError, TypeError, ValueError):
        return 2
    hashes: dict[str, str] = {}
    try:
        with tempfile.TemporaryDirectory(prefix=".e3-consumer-") as temporary_directory:
            snapshots = _snapshot(root, Path(temporary_directory))
            hashes = _hashes(snapshots)
            validation_at = _timestamp()
            selected, hashes = _evaluate_snapshot(snapshots, command_id, validation_at)
        effect_counters = {key: sum(item[key] for item in selected) for key in verify._PUBLIC_EFFECT_COUNTERS}
        verify._atomic_write_json(output, {
            "result_version": "1.0", "command_id": command_id, "runtime": "docker",
            "status": "PASSED", "category": "PASSED", "time": validation_at,
            "input_hashes": dict(sorted(hashes.items())),
            "counts": {"cases_total": len(selected), "passed": len(selected), "failed": 0, "not_run": 0},
            "e3_runtime_assertion": True, "effect_counters": effect_counters,
            "residue_counters": dict(verify._PUBLIC_RESIDUE_COUNTERS),
        })
        return 0
    except Exception:
        if not hashes:
            try:
                schema = root / _FIXED_INPUTS["schema"]
                suite = root / _FIXED_INPUTS["suite"]
                hashes = {
                    "schema_sha256": hashlib.sha256(schema.read_bytes()).hexdigest(),
                    "suite_sha256": hashlib.sha256(suite.read_bytes()).hexdigest(),
                }
            except Exception:
                return 2
        return _not_run(command_id, hashes, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ForgeOps isolated E3 evidence consumer")
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--command-id", required=True, choices=tuple(verify.TRUSTED_RESULTS))
    arguments = parser.parse_args(argv)
    return consume(Path(arguments.project_root), arguments.command_id)


if __name__ == "__main__":
    raise SystemExit(main())
