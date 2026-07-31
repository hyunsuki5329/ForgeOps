"""Policy and artifact-boundary tests for the two-job VG-008 workflow."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/vg-008-e3.yml"
VALIDATION_AT = datetime(2026, 7, 30, tzinfo=timezone.utc)


class E3WorkflowPolicyTests(unittest.TestCase):
    def test_workflow_is_manual_two_job_and_fail_closed_before_effects(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("on:\n  workflow_dispatch:", text)
        for forbidden in ("\n  pull_request:", "\n  push:", "\n  schedule:", "secrets: inherit"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(["build-sign", "verify-e3"], [line[2:-1] for line in text.splitlines() if line.startswith("  ") and not line.startswith("    ") and line.endswith(":") and line.strip() not in {"workflow_dispatch:", "permissions:", "concurrency:", "jobs:"}])
        self.assertIn("needs: build-sign", text)
        self.assertEqual(2, text.count("runs-on: ubuntu-latest"))
        self.assertEqual(2, text.count("github.ref_protected == true"))
        self.assertEqual(2, text.count("github.ref == format('refs/heads/{0}', github.event.repository.default_branch)"))
        self.assertIn("permissions: {}", text)
        self.assertIn("concurrency:\n  group: vg-008-e3-${{ github.repository_id }}\n  cancel-in-progress: false", text)
        for forbidden in ("actions: write", "contents: write", "pull-requests: write", "deployments: write", "git commit", "git push", "gh pr", " release ", " deploy "):
            self.assertNotIn(forbidden, text.lower())

    def test_jobs_have_exact_permissions_and_all_actions_are_fully_pinned(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("contents: read\n      packages: write\n      id-token: write", text)
        self.assertIn("contents: read\n      packages: read\n      id-token: write", text)
        pins = {
            "actions/checkout": "de0fac2e4500dabe0009e67214ff5f5447ce83dd",
            "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
            "docker/login-action": "b45d80f862d83dbcd57f89517bcf500b2ab88fb2",
            "docker/setup-buildx-action": "4d04d5d9486b7bd6fa91e7baf45bbb4f8b9deedd",
            "docker/build-push-action": "f9f3042f7e2789586610d6e8b85c8f03e5195baf",
            "sigstore/cosign-installer": "6f9f17788090df1f26f669e9d70d6ae9567deba6",
        }
        uses = [line.strip().split("uses: ", 1)[1] for line in text.splitlines() if "uses: " in line]
        self.assertTrue(uses)
        for value in uses:
            name, sha = value.split("@", 1)
            self.assertEqual(40, len(sha))
            self.assertEqual(pins[name], sha)

    def test_workflow_invokes_fixed_clis_and_uploads_only_the_public_allowlist(self):
        from tools.sandbox_security.e3_artifact import E3_ARTIFACT_FILES

        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python tools/sandbox_security/e3_helper.py", text)
        self.assertIn("python tools/sandbox_security/e3_attestation.py import", text)
        self.assertEqual(3, text.count("python tools/sandbox_security/verify.py"))
        self.assertIn("python tools/sandbox_security/e3_artifact.py build", text)
        self.assertIn("name: forgeops-e3-evidence-${{ github.run_id }}-${{ github.run_attempt }}", text)
        self.assertIn("if-no-files-found: error", text)
        self.assertIn("include-hidden-files: false", text)
        self.assertIn("retention-days: 7", text)
        for path in E3_ARTIFACT_FILES:
            self.assertIn(f"          {path}", text)


class E3ArtifactTests(unittest.TestCase):
    def setUp(self):
        from tests.sandbox_security.test_e3_attestation import SignedE3AttestationTests

        factory = SignedE3AttestationTests()
        factory.setUp()
        self.identity = factory.identity
        self.attestation = factory._attestation()
        self.runner = factory._runner

    @staticmethod
    def _write(path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, bytes):
            path.write_bytes(value)
        elif isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")

    def _source(self, root: Path, *, status: str = "READY") -> Path:
        from tools.sandbox_security.e3_artifact import E3_PAYLOAD_FILES

        phase = json.loads((ROOT / "artifacts/verification/phase-0-exit-result.json").read_text(encoding="utf-8"))
        phase["status"] = status
        phase["observed_at"] = "2026-07-30T00:00:00Z"
        phase["summary"] = {"required": 18, "passed": 18 if status == "READY" else 17, "failed": 0, "not_run": 0 if status == "READY" else 1, "blocked": 0 if status == "READY" else 1}
        phase["blockers"] = [] if status == "READY" else [{"gate_id": "VG-008", "command_id": "teardown-negative", "reason_code": "PHASE_EXIT_STATUS_NOT_RUN"}]
        phase["assertions"] = {"exact_coverage": True, "freshness_valid": status == "READY", "input_hashes_valid": True, "public_safe": True, "tiers_sufficient": True}
        for gate in phase["gate_results"]:
            gate["status"] = "PASSED" if status == "READY" else gate["status"]
            gate["observed_at"] = "2026-07-30T00:00:00Z"
        values: dict[str, object] = {
            E3_PAYLOAD_FILES[0]: self.attestation,
            E3_PAYLOAD_FILES[1]: b"bundle",
            E3_PAYLOAD_FILES[2]: {"runtime": "docker", "available": True},
            E3_PAYLOAD_FILES[3]: {"observations_version": "1.0", "observations": []},
            E3_PAYLOAD_FILES[4]: {"receipt_version": "1.0"},
            E3_PAYLOAD_FILES[5]: {"status": "PASSED"},
            E3_PAYLOAD_FILES[6]: {"status": "PASSED"},
            E3_PAYLOAD_FILES[7]: {"status": "PASSED"},
            E3_PAYLOAD_FILES[8]: phase,
            E3_PAYLOAD_FILES[9]: "# Phase 0\n\nREADY\n",
        }
        for path in E3_PAYLOAD_FILES:
            self._write(root / path, values[path])
        return root

    def test_manifest_hashes_exact_payload_and_never_itself(self):
        from tools.sandbox_security.e3_artifact import E3_MANIFEST_FILE, E3_PAYLOAD_FILES, build_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = self._source(Path(directory))
            manifest = build_manifest(root, root / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
            self.assertEqual(list(E3_PAYLOAD_FILES), [item["path"] for item in manifest["files"]])
            self.assertNotIn(E3_MANIFEST_FILE, [item["path"] for item in manifest["files"]])
            for item in manifest["files"]:
                self.assertEqual(hashlib.sha256((root / item["path"]).read_bytes()).hexdigest(), item["sha256"])
            self.assertEqual("READY", manifest["status"])
            self.assertEqual("1001", manifest["run_id"])

    def test_builder_rejects_missing_secret_like_oversized_and_not_ready_inputs(self):
        from tools.sandbox_security.e3_artifact import ArtifactError, E3_MANIFEST_FILE, E3_PAYLOAD_FILES, MAX_FILE_BYTES, build_manifest

        mutations = ("missing", "secret", "oversized", "phase-extra", "not-ready")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = self._source(Path(directory), status="NOT_READY" if mutation == "not-ready" else "READY")
                if mutation == "missing":
                    (root / E3_PAYLOAD_FILES[5]).unlink()
                elif mutation == "secret":
                    self._write(root / E3_PAYLOAD_FILES[5], {"status": "PASSED", "secret": "redacted"})
                elif mutation == "oversized":
                    (root / E3_PAYLOAD_FILES[9]).write_bytes(b"x" * (MAX_FILE_BYTES + 1))
                elif mutation == "phase-extra":
                    phase = json.loads((root / E3_PAYLOAD_FILES[8]).read_text(encoding="utf-8"))
                    phase["unexpected"] = True
                    self._write(root / E3_PAYLOAD_FILES[8], phase)
                with self.assertRaises(ArtifactError):
                    build_manifest(root, root / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
                self.assertFalse((root / E3_MANIFEST_FILE).exists())

    def test_builder_rejects_tag_uppercase_digest_issuer_and_identity_near_misses(self):
        from tools.sandbox_security.e3_artifact import ArtifactError, E3_MANIFEST_FILE, E3_PAYLOAD_FILES, build_manifest

        mutations = {
            "tag": {"image_ref": "ghcr.io/example/forgeops-e3:latest"},
            "uppercase-digest": {"image_digest": "sha256:" + "C" * 64, "image_ref": "ghcr.io/example/forgeops-e3@sha256:" + "C" * 64},
            "issuer": {"issuer": "https://token.actions.githubusercontent.com.example"},
            "identity": {"certificate_identity": "https://github.com/example/forgeops/.github/workflows/vg-008-e3.yml@refs/heads/main-near"},
        }
        for name, changes in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = self._source(Path(directory))
                attestation = json.loads((root / E3_PAYLOAD_FILES[0]).read_text(encoding="utf-8"))
                attestation.update(changes)
                self._write(root / E3_PAYLOAD_FILES[0], attestation)
                with self.assertRaises(ArtifactError):
                    build_manifest(root, root / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
                self.assertFalse((root / E3_MANIFEST_FILE).exists())

    def test_download_verification_rejects_extra_absolute_symlink_stale_and_identity_near_miss(self):
        from tools.sandbox_security.e3_artifact import ArtifactError, E3_MANIFEST_FILE, E3_PAYLOAD_FILES, build_manifest, verify_downloaded_artifact

        mutations = ("extra", "absolute", "symlink", "stale", "identity")
        for mutation in mutations:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as directory:
                root = self._source(Path(directory))
                build_manifest(root, root / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
                if mutation == "extra":
                    self._write(root / "unexpected.json", {})
                elif mutation == "absolute":
                    manifest = json.loads((root / E3_MANIFEST_FILE).read_text(encoding="utf-8"))
                    manifest["files"][0]["path"] = str((root / E3_PAYLOAD_FILES[0]).resolve())
                    self._write(root / E3_MANIFEST_FILE, manifest)
                elif mutation == "symlink":
                    with mock.patch("pathlib.Path.is_symlink", autospec=True, side_effect=lambda value: value.as_posix().endswith(E3_PAYLOAD_FILES[5])):
                        with self.assertRaises(ArtifactError):
                            verify_downloaded_artifact(root, self.identity.repository, self.identity.repository_id, self.identity.default_branch, self.identity.run_id, self.identity.run_attempt, self.identity.source_sha, runner=self.runner, validation_at=VALIDATION_AT)
                    continue
                validation_at = VALIDATION_AT + timedelta(seconds=301) if mutation == "stale" else VALIDATION_AT
                repository = "example/near-miss" if mutation == "identity" else self.identity.repository
                with self.assertRaises(ArtifactError):
                    verify_downloaded_artifact(root, repository, self.identity.repository_id, self.identity.default_branch, self.identity.run_id, self.identity.run_attempt, self.identity.source_sha, runner=self.runner, validation_at=validation_at)

    def test_fresh_verified_artifact_imports_only_known_targets(self):
        from tools.sandbox_security.e3_artifact import E3_ARTIFACT_FILES, E3_MANIFEST_FILE, build_manifest, import_downloaded_artifact

        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            source = self._source(Path(source_directory))
            build_manifest(source, source / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
            target = Path(target_directory)
            imported = import_downloaded_artifact(source, target, self.identity, runner=self.runner, validation_at=VALIDATION_AT)
            self.assertEqual(set(E3_ARTIFACT_FILES), set(imported))
            self.assertEqual(set(E3_ARTIFACT_FILES), {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()})


if __name__ == "__main__":
    unittest.main()
