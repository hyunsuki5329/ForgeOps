"""Fresh-process integration fixture for the sealed E3 consumer boundary."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile


_REAL_RUN = subprocess.run


def _successful_cosign(arguments, **kwargs):
    """Replace only the external Cosign binary before trust modules import."""

    if arguments and arguments[0] == "cosign":
        return subprocess.CompletedProcess(arguments, 0, stdout="verified", stderr="")
    return _REAL_RUN(arguments, **kwargs)


# runtime.py intentionally captures the process runner at import time.  This
# fresh helper process supplies a successful external-verifier stand-in before
# importing that trust boundary; all identity, receipt, hash, reconstruction
# and seal checks remain the production implementations.
subprocess.run = _successful_cosign

from tools.sandbox_security import e3_attestation, e3_consumer, e3_helper, runtime
from tools.sandbox_security.e3_attestation import ExpectedIdentity
from tests.sandbox_security.test_e3_helper import RecordingRunner


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/forgeops-sandbox-contract/1.0/schema.json"
SUITE = ROOT / "fixtures/forgeops-sandbox-security/suite.json"


def main() -> int:
    identity = ExpectedIdentity(
        "example/forgeops", "123456", "main", "a" * 40, "b" * 40, "1001", 1,
        "ghcr.io/example/forgeops-e3@sha256:" + "c" * 64,
        "sha256:" + "c" * 64,
    )
    with tempfile.TemporaryDirectory() as temporary_directory:
        root = Path(temporary_directory)
        runtime_root = root / "artifacts/runtime"
        runtime_root.mkdir(parents=True)
        attestation_path = runtime_root / "e3-attestation.json"
        if e3_helper.collect_e3_attestation(
            identity, SCHEMA, SUITE, attestation_path, runner=RecordingRunner()
        ) != 0:
            return 2
        bundle_path = runtime_root / "e3-attestation.bundle.json"
        bundle_path.write_bytes(b"bundle")
        attestation = json.loads(attestation_path.read_text(encoding="utf-8"))
        validation_at = datetime.strptime(
            attestation["observed_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
        outputs = e3_attestation.import_signed_attestation(
            attestation_path, bundle_path, identity, root,
            validation_at=validation_at,
        )
        schema_target = root / "contracts/forgeops-sandbox-contract/1.0/schema.json"
        suite_target = root / "fixtures/forgeops-sandbox-security/suite.json"
        schema_target.parent.mkdir(parents=True)
        suite_target.parent.mkdir(parents=True)
        schema_target.write_bytes(SCHEMA.read_bytes())
        suite_target.write_bytes(SUITE.read_bytes())
        os.environ.update({
            "GITHUB_REPOSITORY": identity.repository,
            "GITHUB_REPOSITORY_ID": identity.repository_id,
            "GITHUB_REF": f"refs/heads/{identity.default_branch}",
            "GITHUB_SHA": identity.source_sha,
            "GITHUB_WORKFLOW_SHA": identity.workflow_sha,
            "GITHUB_RUN_ID": identity.run_id,
            "GITHUB_RUN_ATTEMPT": str(identity.run_attempt),
        })
        observer = runtime.AttestedRuntimeObserver.from_imported_files(
            outputs["profile"], outputs["observations"], outputs["receipt"],
            attestation["observed_at"],
        )
        if not runtime.has_attested_e3_construction(observer):
            return 3
        suite = json.loads(SUITE.read_text(encoding="utf-8"))
        summary = {}
        for command_id, catalogs in e3_consumer.verify._COMMAND_CATALOGS.items():
            if e3_consumer.consume(root, command_id) != 0:
                return 4
            result = json.loads(
                (root / e3_consumer.verify.TRUSTED_RESULTS[command_id]).read_text(encoding="utf-8")
            )
            summary[command_id] = {
                "counts": result["counts"],
                "effect_counters": result["effect_counters"],
                "expected_total": sum(len(suite[catalog]) for catalog in catalogs),
            }
        observations = json.loads(outputs["observations"].read_text(encoding="utf-8"))["observations"]
        summary["preprovision_zero_effects"] = all(
            not any(item[name] for name in ("provision_calls", "network_calls", "write_calls"))
            for item in observations
            if item["observation_mode"] == "PREPROVISION_DENIED"
        )
        print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
