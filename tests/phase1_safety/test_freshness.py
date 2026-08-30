import copy
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from jsonschema import Draft202012Validator

from tools.phase1_safety import verify
from tools.phase1_safety.audit import reduce_required_evidence, reduce_security_negative, validate_e3_receipt
from tools.phase1_safety.model import SourceIdentity
from tools.phase1_safety.registry import load_registry


ROOT = Path(__file__).resolve().parents[2]
SUITE = json.loads((ROOT / "fixtures/forgeops-phase1-safety/suite.json").read_text(encoding="utf-8"))
REGISTRATIONS = load_registry(SUITE)
REQUIRED_COMMANDS = tuple(SUITE["subsets"]["required_evidence"])
NOW = datetime(2026, 8, 29, 0, 0, 0, tzinfo=timezone.utc)
NOW_TEXT = "2026-08-29T00:00:00Z"
IDENTITY = SourceIdentity(
    repository="example/forgeops",
    repository_id="123",
    default_branch="main",
    workflow_ref="refs/heads/main",
    source_sha="a" * 40,
    workflow_sha="a" * 40,
    run_id="1001",
    run_attempt=1,
)


def _set_dotted(value: dict, dotted: str, replacement: object) -> None:
    current = value
    parts = dotted.split(".")
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = replacement


def _fixture_root(directory: str) -> tuple[Path, dict[str, dict]]:
    root = Path(directory)
    artifacts: dict[str, dict] = {}
    for registration in REGISTRATIONS:
        if registration.command_id not in REQUIRED_COMMANDS:
            continue
        value = json.loads((ROOT / registration.artifact_ref).read_text(encoding="utf-8"))
        value[registration.observed_at_field] = NOW_TEXT
        for field in registration.hash_fields:
            _set_dotted(value, field, "b" * 64)
        target = root / registration.artifact_ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(value), encoding="utf-8")
        artifacts[registration.command_id] = value
    return root, artifacts


def _run(root: Path, *, receipt_valid: bool = True, source_valid: bool = True) -> dict:
    return reduce_required_evidence(
        root,
        registrations=REGISTRATIONS,
        validated_at=NOW,
        source_identity=IDENTITY,
        binding_resolver=lambda _root, _binding: "b" * 64,
        source_checker=lambda _root, _identity: source_valid,
        receipt_validator=lambda _root, _identity, _when: receipt_valid,
    )


class RequiredEvidenceReducerTests(unittest.TestCase):
    def test_exact_nineteen_results_reduce_to_five_e3_and_fourteen_e2(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = _fixture_root(directory)
            result = _run(root)

        self.assertEqual("PASSED", result["status"])
        self.assertEqual({"total": 19, "passed": 19, "failed": 0, "blockers": 0}, result["summary"])
        self.assertEqual(REQUIRED_COMMANDS, tuple(row["command_id"] for row in result["gates"]))
        self.assertEqual(5, sum(row["required_tier"] == "E3" for row in result["gates"]))
        self.assertEqual(14, sum(row["required_tier"] == "E2" for row in result["gates"]))
        self.assertFalse(any(result["effect_counters"].values()))

    def test_invalid_receipt_blocks_only_the_five_e3_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = _fixture_root(directory)
            result = _run(root, receipt_valid=False)

        self.assertEqual("FAILED", result["status"])
        blocked = [row for row in result["gates"] if "E3_RECEIPT_INVALID" in row["blocker_codes"]]
        self.assertEqual(5, len(blocked))
        self.assertTrue(all(row["required_tier"] == "E3" for row in blocked))

    def test_stale_missing_and_mixed_source_evidence_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root, artifacts = _fixture_root(directory)
            registration = next(item for item in REGISTRATIONS if item.command_id == "snapshot-identity")
            artifacts[registration.command_id]["observed_at"] = "2026-08-28T23:54:59Z"
            (root / registration.artifact_ref).write_text(json.dumps(artifacts[registration.command_id]), encoding="utf-8")
            stale = _run(root)
            (root / registration.artifact_ref).unlink()
            missing = _run(root)
            mixed = _run(root, source_valid=False)

        self.assertIn("EVIDENCE_STALE", {item["reason_code"] for item in stale["blockers"]})
        self.assertIn("ARTIFACT_MISSING", {item["reason_code"] for item in missing["blockers"]})
        self.assertEqual(19, sum("SOURCE_HASH_MISMATCH" in row["blocker_codes"] for row in mixed["gates"]))

    def test_registered_cli_writes_schema_valid_freshness_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root, _ = _fixture_root(directory)
            for relative in (
                "contracts/forgeops-phase1-safety/1.0/schema.json",
                "fixtures/forgeops-phase1-safety/suite.json",
            ):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            argv = [
                "--schema", "contracts/forgeops-phase1-safety/1.0/schema.json",
                "--suite", "fixtures/forgeops-phase1-safety/suite.json",
                "--result", "artifacts/verification/phase-1-evidence-freshness-result.json",
                "--command-id", "phase1-evidence-freshness",
            ]
            exit_code = verify.main(
                argv,
                root=root,
                validated_at=NOW,
                source_identity=IDENTITY,
                binding_resolver=lambda _root, _binding: "b" * 64,
                source_checker=lambda _root, _identity: True,
                receipt_validator=lambda _root, _identity, _when: True,
            )
            result = json.loads((root / "artifacts/verification/phase-1-evidence-freshness-result.json").read_text(encoding="utf-8"))
            schema = json.loads((root / "contracts/forgeops-phase1-safety/1.0/schema.json").read_text(encoding="utf-8"))

        self.assertEqual(0, exit_code)
        result_schema = {"$ref": "#/$defs/reducerResult", "$defs": schema["$defs"]}
        self.assertEqual([], list(Draft202012Validator(result_schema).iter_errors(result)))


class E3ReceiptValidationTests(unittest.TestCase):
    def _signed_root(self, root: Path):
        from tests.sandbox_security.test_e3_attestation import SignedE3AttestationTests, canonical_bytes
        from tools.sandbox_security.e3_attestation import import_signed_attestation

        factory = SignedE3AttestationTests()
        factory.setUp()
        identity = replace(factory.identity, workflow_sha=factory.identity.source_sha)
        attestation = factory._attestation()
        attestation["workflow_sha"] = identity.workflow_sha
        attestation["observed_at"] = NOW_TEXT
        for observation in attestation["observations"]:
            observation["observed_at"] = NOW_TEXT
        factory._refresh_profile_hash(attestation)
        attestation_path = root / "source-attestation.json"
        bundle_path = root / "source-bundle.json"
        attestation_path.write_bytes(canonical_bytes(attestation))
        bundle_path.write_bytes(b"bundle")
        import_signed_attestation(attestation_path, bundle_path, identity, root, factory._runner, NOW)
        runtime_attestation = root / "artifacts/runtime/e3-attestation.json"
        runtime_bundle = root / "artifacts/runtime/e3-attestation.bundle.json"
        runtime_attestation.write_bytes(attestation_path.read_bytes())
        runtime_bundle.write_bytes(bundle_path.read_bytes())
        receipt_path = root / "artifacts/runtime/sandbox-e3-import-receipt.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["verification_kind"] = "runtime"
        receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
        source_identity = SourceIdentity(
            identity.repository, identity.repository_id, identity.default_branch,
            identity.workflow_ref, identity.source_sha, identity.workflow_sha,
            identity.run_id, identity.run_attempt,
        )
        return source_identity, factory._runner

    def test_accepts_exact_runtime_receipt_and_signed_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity, runner = self._signed_root(root)
            self.assertTrue(validate_e3_receipt(root, identity, NOW, runner=runner))

    def test_rejects_test_receipt_hash_change_identity_near_miss_and_stale_time(self):
        mutations = (
            ("verification_kind", "test"),
            ("bundle_sha256", "0" * 64),
            ("repository_id", "999"),
            ("certificate_identity", "https://github.com/example/forgeops/.github/workflows/vg-008-e3.yml@refs/heads/other"),
            ("observed_at", "2026-08-28T23:54:59Z"),
        )
        for field, value in mutations:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                identity, runner = self._signed_root(root)
                receipt_path = root / "artifacts/runtime/sandbox-e3-import-receipt.json"
                receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
                receipt[field] = value
                receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                self.assertFalse(validate_e3_receipt(root, identity, NOW, runner=runner))


class Phase1ArtifactBoundaryTests(unittest.TestCase):
    def _source(self, root: Path):
        from tools.sandbox_security.e3_attestation import ExpectedIdentity

        receipt_fixture = E3ReceiptValidationTests()
        source_identity, runner = receipt_fixture._signed_root(root)
        for registration in REGISTRATIONS:
            value = json.loads((ROOT / registration.artifact_ref).read_text(encoding="utf-8"))
            value[registration.observed_at_field] = NOW_TEXT
            for field in registration.hash_fields:
                _set_dotted(value, field, "b" * 64)
            target = root / registration.artifact_ref
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value), encoding="utf-8")
        shared = {
            "registrations": REGISTRATIONS,
            "validated_at": NOW,
            "source_identity": source_identity,
            "binding_resolver": lambda _root, _binding: "b" * 64,
            "source_checker": lambda _root, _identity: True,
        }
        security = reduce_security_negative(root, **shared)
        freshness = reduce_required_evidence(
            root,
            **shared,
            receipt_validator=lambda _root, _identity, _when: True,
        )
        gate = copy.deepcopy(freshness)
        gate["command_id"] = "phase1-safety-gate"
        gate["status"] = "READY"
        values = {
            "artifacts/verification/phase-1-security-negative-result.json": security,
            "artifacts/verification/phase-1-evidence-freshness-result.json": freshness,
            "artifacts/verification/phase-1-safety-gate-result.json": gate,
        }
        for relative, value in values.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
        for relative, text in (
            ("artifacts/reviews/phase-1-safety-scorecard.md", "# Phase 1 Safety\n\nREADY\n"),
            ("artifacts/reviews/phase-1-safety-scorecard.html", "<!doctype html><meta charset=utf-8><title>Phase 1 Safety</title><p>READY</p>\n"),
        ):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        receipt = json.loads((root / "artifacts/runtime/sandbox-e3-import-receipt.json").read_text(encoding="utf-8"))
        identity = ExpectedIdentity(
            source_identity.repository, source_identity.repository_id, source_identity.default_branch,
            source_identity.source_sha, source_identity.workflow_sha, source_identity.run_id,
            source_identity.run_attempt, receipt["image_ref"], receipt["image_digest"],
        )
        return identity, runner

    def test_versioned_payload_is_exact_registry_plus_runtime_outputs_and_scorecards(self):
        from tools.sandbox_security.e3_artifact import PHASE1_PAYLOAD_FILES, PHASE1_RESULT_FILES

        self.assertEqual(
            tuple(registration.artifact_ref for registration in REGISTRATIONS),
            PHASE1_RESULT_FILES,
        )
        self.assertEqual(33, len(PHASE1_PAYLOAD_FILES))
        self.assertEqual(len(PHASE1_PAYLOAD_FILES), len(set(PHASE1_PAYLOAD_FILES)))

    def test_build_verify_stage_and_import_exact_phase1_artifact(self):
        from tools.sandbox_security.e3_artifact import (
            PHASE1_ARTIFACT_FILES,
            PHASE1_MANIFEST_FILE,
            PHASE1_PAYLOAD_FILES,
            build_phase1_manifest,
            import_downloaded_phase1_artifact_from_facts,
            stage_phase1_upload_artifact,
            verify_downloaded_phase1_artifact_from_facts,
            verify_downloaded_phase1_artifact,
        )

        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as target_directory:
            root = Path(directory)
            identity, runner = self._source(root)
            manifest = build_phase1_manifest(root, root / PHASE1_MANIFEST_FILE, runner=runner, validation_at=NOW)
            self.assertEqual(list(PHASE1_PAYLOAD_FILES), [item["path"] for item in manifest["files"]])
            self.assertNotIn(PHASE1_MANIFEST_FILE, [item["path"] for item in manifest["files"]])
            staging = stage_phase1_upload_artifact(root)
            verified = verify_downloaded_phase1_artifact(staging, identity, runner=runner, validation_at=NOW)
            facts = {
                "expected_repository": identity.repository,
                "expected_repository_id": identity.repository_id,
                "expected_default_branch": identity.default_branch,
                "expected_run_id": identity.run_id,
                "expected_run_attempt": identity.run_attempt,
                "expected_source_sha": identity.source_sha,
            }
            verified_from_facts = verify_downloaded_phase1_artifact_from_facts(
                staging, **facts, runner=runner, validation_at=NOW
            )
            targets = import_downloaded_phase1_artifact_from_facts(
                staging, Path(target_directory), **facts, runner=runner, validation_at=NOW
            )

            self.assertEqual("READY", verified["status"])
            self.assertEqual(verified, verified_from_facts)
            self.assertEqual(set(PHASE1_ARTIFACT_FILES), set(targets))
            for relative in PHASE1_ARTIFACT_FILES:
                self.assertEqual((staging / relative).read_bytes(), targets[relative].read_bytes())

    def test_facts_only_download_rejects_github_identity_near_miss(self):
        from tools.sandbox_security.e3_artifact import (
            ArtifactError,
            PHASE1_MANIFEST_FILE,
            build_phase1_manifest,
            stage_phase1_upload_artifact,
            verify_downloaded_phase1_artifact_from_facts,
        )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            identity, runner = self._source(root)
            build_phase1_manifest(root, root / PHASE1_MANIFEST_FILE, runner=runner, validation_at=NOW)
            staging = stage_phase1_upload_artifact(root)
            with self.assertRaises(ArtifactError):
                verify_downloaded_phase1_artifact_from_facts(
                    staging,
                    expected_repository=identity.repository,
                    expected_repository_id="999",
                    expected_default_branch=identity.default_branch,
                    expected_run_id=identity.run_id,
                    expected_run_attempt=identity.run_attempt,
                    expected_source_sha=identity.source_sha,
                    runner=runner,
                    validation_at=NOW,
                )

    def test_download_rejects_extra_missing_tampered_and_stale_payload(self):
        from tools.sandbox_security.e3_artifact import (
            ArtifactError,
            PHASE1_MANIFEST_FILE,
            PHASE1_STAGING_ROOT,
            build_phase1_manifest,
            stage_phase1_upload_artifact,
            verify_downloaded_phase1_artifact,
        )

        mutations = ("extra", "missing", "tampered", "stale")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                identity, runner = self._source(root)
                build_phase1_manifest(root, root / PHASE1_MANIFEST_FILE, runner=runner, validation_at=NOW)
                staging = stage_phase1_upload_artifact(root)
                if mutation == "extra":
                    (staging / "extra.txt").write_text("extra", encoding="utf-8")
                elif mutation == "missing":
                    (staging / "artifacts/reviews/phase-1-safety-scorecard.md").unlink()
                elif mutation == "tampered":
                    (staging / "artifacts/reviews/phase-1-safety-scorecard.md").write_text("changed", encoding="utf-8")
                validation_at = NOW if mutation != "stale" else datetime(2026, 8, 29, 0, 5, 1, tzinfo=timezone.utc)
                with self.assertRaises(ArtifactError):
                    verify_downloaded_phase1_artifact(staging, identity, runner=runner, validation_at=validation_at)


if __name__ == "__main__":
    unittest.main()
