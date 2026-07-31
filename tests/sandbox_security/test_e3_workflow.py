"""Policy and artifact-boundary tests for the two-job VG-008 workflow."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github/workflows/vg-008-e3.yml"
VALIDATION_AT = datetime(2026, 7, 30, tzinfo=timezone.utc)
PHASE0_SUITE = ROOT / "fixtures/forgeops-phase-exit/phase-0-suite.json"
E3_HELPER_INPUTS = {
    "tools/sandbox_security/e3_helper.py",
    "tools/sandbox_security/e3_probe.py",
}


class E3WorkflowPolicyTests(unittest.TestCase):
    def test_exact_phase0_byte_inputs_are_lf_without_a_repository_wide_policy(self):
        suite = json.loads(PHASE0_SUITE.read_text(encoding="utf-8"))
        exact_byte_inputs = tuple(
            sorted(
                E3_HELPER_INPUTS
                | {
                    input_ref
                    for registration in suite["registrations"]
                    for input_ref in registration["input_refs"]
                }
            )
        )
        attributes_path = ROOT / ".gitattributes"
        active_lines = [
            line.strip()
            for line in attributes_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(
            [f"{path} text eol=lf" for path in exact_byte_inputs],
            active_lines,
        )

        completed = subprocess.run(
            ["git", "check-attr", "text", "eol", "--", *exact_byte_inputs],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            [
                f"{path}: {attribute}: {value}"
                for path in exact_byte_inputs
                for attribute, value in (("text", "set"), ("eol", "lf"))
            ],
            completed.stdout.splitlines(),
        )

    def test_primary_key_parser_ignores_subkeys_and_rejects_an_appended_primary(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        install = text.split("- name: Install rootless Docker prerequisites", 1)[1].split(
            "- name: Configure rootless Docker", 1
        )[0]
        match = re.search(
            r'docker_primary_fingerprints="\$\(.*?awk -F: \'(.*?)\'\s*\)"',
            install,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        awk_program = match.group(1)
        self.assertEqual(
            [
                '$1 == "pub" { awaiting_primary_fpr = 1; next }',
                '$1 == "sub" { awaiting_primary_fpr = 0; next }',
                'awaiting_primary_fpr && $1 == "fpr" { print $10; awaiting_primary_fpr = 0 }',
            ],
            [line.strip() for line in awk_program.splitlines() if line.strip()],
        )

        pinned = "9DC858229FC7DD38854AE2D88D81803C0EBFCD88"
        subkey = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        attacker = "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        valid_listing = (
            "pub:-:4096:1:8D81803C0EBFCD88:0:0:::::::\n"
            f"fpr:::::::::{pinned}:\n"
            "uid:-::::0::Docker Release (CE deb):\n"
            "sub:-:4096:1:7EA0A9C3F273FCD8:0:0:::::::\n"
            f"fpr:::::::::{subkey}:\n"
        )
        appended_primary = valid_listing + (
            "pub:-:4096:1:BBBBBBBBBBBBBBBB:0:0:::::::\n"
            f"fpr:::::::::{attacker}:\n"
        )

        def primary_fingerprints(listing: str) -> tuple[int, list[str]]:
            primary_count = 0
            awaiting_primary_fpr = False
            fingerprints: list[str] = []
            for line in listing.splitlines():
                fields = line.split(":")
                if fields[0] == "pub":
                    primary_count += 1
                    awaiting_primary_fpr = True
                elif fields[0] == "sub":
                    awaiting_primary_fpr = False
                elif awaiting_primary_fpr and fields[0] == "fpr":
                    fingerprints.append(fields[9])
                    awaiting_primary_fpr = False
            return primary_count, fingerprints

        self.assertEqual((1, [pinned]), primary_fingerprints(valid_listing))
        self.assertEqual((2, [pinned, attacker]), primary_fingerprints(appended_primary))
        self.assertIn('test "$docker_primary_pub_count" = "1" || prerequisite_fail "E3_ROOTLESS_KEY_FINGERPRINT_MISMATCH" 48', install)
        self.assertIn('test "$docker_primary_fingerprint_count" = "1" || prerequisite_fail "E3_ROOTLESS_KEY_FINGERPRINT_MISMATCH" 48', install)
        self.assertIn('test "$docker_primary_fingerprints" = "9DC858229FC7DD38854AE2D88D81803C0EBFCD88" || prerequisite_fail "E3_ROOTLESS_KEY_FINGERPRINT_MISMATCH" 48', install)

    def test_rootless_prerequisite_bootstraps_only_the_fingerprint_pinned_docker_repository(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        install = text.split("- name: Install rootless Docker prerequisites", 1)[1].split(
            "- name: Configure rootless Docker", 1
        )[0]
        repository_template = (
            "Types: deb\\n"
            "URIs: https://download.docker.com/linux/ubuntu\\n"
            "Suites: %s\\n"
            "Components: stable\\n"
            "Architectures: %s\\n"
            "Signed-By: /etc/apt/keyrings/docker.asc\\n"
        )
        repository_write = f"printf '{repository_template}' \"$VERSION_CODENAME\" \"$architecture\""

        self.assertIn("https://download.docker.com/linux/ubuntu/gpg", install)
        self.assertIn("--proto '=https'", install)
        self.assertIn("--proto-redir '=https'", install)
        self.assertIn("--tlsv1.2", install)
        self.assertIn("--output \"$docker_key_temp\"", install)
        self.assertIn("9DC858229FC7DD38854AE2D88D81803C0EBFCD88", install)
        self.assertIn("gpg --batch --show-keys --with-colons --with-fingerprint", install)
        self.assertIn("sudo install -m 0755 -d /etc/apt/keyrings", install)
        self.assertIn('sudo install -m 0644 "$docker_key_temp" /etc/apt/keyrings/docker.asc', install)
        self.assertIn(repository_write, install)
        self.assertIn('sudo install -m 0644 "$docker_repository_temp" /etc/apt/sources.list.d/docker.sources', install)
        self.assertNotIn("/etc/apt/sources.list.d/docker.list", install)
        self.assertIn('test "${ID:-}" = "ubuntu"', install)
        self.assertIn('test "${VERSION_ID:-}" = "24.04"', install)
        self.assertIn('test "${VERSION_CODENAME:-}" = "noble"', install)
        self.assertIn('test "$architecture" = "amd64"', install)
        self.assertLess(install.index(repository_write), install.index("sudo apt-get update"))
        self.assertLess(install.index("sudo apt-get update"), install.index("apt-cache madison docker-ce-rootless-extras"))
        expected_failures = {
            "E3_ROOTLESS_KEY_DOWNLOAD_FAILED": 47,
            "E3_ROOTLESS_KEY_FINGERPRINT_MISMATCH": 48,
            "E3_ROOTLESS_KEYRING_INSTALL_FAILED": 49,
            "E3_ROOTLESS_REPOSITORY_CONFIG_INVALID": 50,
            "E3_ROOTLESS_REPOSITORY_UPDATE_FAILED": 51,
        }
        for reason, code in expected_failures.items():
            with self.subTest(reason=reason):
                self.assertIn(f'prerequisite_fail "{reason}" {code}', install)
        for forbidden in ("| sh", "| bash", "get.docker.com", "apt-key", "trusted=yes", "add-apt-repository", "--privileged"):
            self.assertNotIn(forbidden, install)

    def test_verify_job_installs_version_matched_rootless_prerequisites_before_configuration(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        install = text.split("- name: Install rootless Docker prerequisites", 1)[1].split(
            "- name: Configure rootless Docker", 1
        )[0]

        self.assertLess(
            text.index("- name: Install rootless Docker prerequisites"),
            text.index("- name: Configure rootless Docker"),
        )
        self.assertIn("sudo apt-get update", install)
        self.assertIn("dpkg-query --show --showformat='${Version}' docker-ce-cli", install)
        self.assertIn("apt-cache policy uidmap", install)
        self.assertIn("apt-cache madison docker-ce-rootless-extras", install)
        self.assertIn(
            "uidmap_version=\"$(apt-cache policy uidmap | awk '/Candidate:/ { print $2; exit }')\" || prerequisite_fail \"E3_ROOTLESS_UIDMAP_VERSION_UNAVAILABLE\" 41",
            install,
        )
        self.assertIn(
            "rootless_version=\"$(apt-cache madison docker-ce-rootless-extras | awk -v expected=\"$docker_version\" '$3 == expected { print $3; exit }')\" || prerequisite_fail \"E3_ROOTLESS_EXTRAS_VERSION_MISMATCH\" 42",
            install,
        )
        self.assertIn('"uidmap=$uidmap_version"', install)
        self.assertIn('"docker-ce-rootless-extras=$docker_version"', install)
        self.assertIn("--no-install-recommends", install)
        self.assertIn('sudo systemctl start "user@$runner_uid.service"', install)
        self.assertIn('test -S "$XDG_RUNTIME_DIR/bus"', install)
        self.assertIn('echo "XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR" >> "$GITHUB_ENV"', install)
        expected_failures = {
            "E3_ROOTLESS_DOCKER_CLI_VERSION_UNAVAILABLE": 40,
            "E3_ROOTLESS_UIDMAP_VERSION_UNAVAILABLE": 41,
            "E3_ROOTLESS_EXTRAS_VERSION_MISMATCH": 42,
            "E3_ROOTLESS_PACKAGE_INSTALL_FAILED": 43,
            "E3_ROOTLESS_USER_SESSION_FAILED": 44,
            "E3_ROOTLESS_RUNTIME_DIR_INVALID": 45,
            "E3_ROOTLESS_USER_BUS_MISSING": 46,
        }
        for reason, code in expected_failures.items():
            with self.subTest(reason=reason):
                self.assertIn(f'prerequisite_fail "{reason}" {code}', install)
        for forbidden in ("curl |", "| sh", "| bash", "get.docker.com", "--privileged"):
            self.assertNotIn(forbidden, install)

    def test_workflow_is_manual_two_job_and_fail_closed_before_effects(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("on:\n  workflow_dispatch:", text)
        for forbidden in ("\n  pull_request:", "\n  push:", "\n  schedule:", "secrets: inherit"):
            self.assertNotIn(forbidden, text)
        self.assertEqual(["build-sign", "verify-e3"], [line[2:-1] for line in text.splitlines() if line.startswith("  ") and not line.startswith("    ") and line.endswith(":") and line.strip() not in {"workflow_dispatch:", "permissions:", "concurrency:", "jobs:"}])
        self.assertIn("needs: build-sign", text)
        self.assertEqual(2, text.count("runs-on: ubuntu-24.04"))
        self.assertNotIn("runs-on: ubuntu-latest", text)
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
        self.assertEqual(2, text.count("cosign-release: 'v3.0.6'"))

    def test_workflow_invokes_fixed_clis_and_uploads_only_the_public_allowlist(self):
        from tools.sandbox_security.e3_artifact import E3_ARTIFACT_FILES, E3_STAGING_ROOT

        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python tools/sandbox_security/e3_helper.py", text)
        self.assertIn("python tools/sandbox_security/e3_attestation.py import", text)
        self.assertEqual(3, text.count("python tools/sandbox_security/verify.py"))
        self.assertIn("python tools/sandbox_security/e3_artifact.py build", text)
        self.assertIn("python tools/sandbox_security/e3_artifact.py stage-upload", text)
        self.assertIn("name: forgeops-e3-evidence-${{ github.run_id }}-${{ github.run_attempt }}", text)
        self.assertIn("if-no-files-found: error", text)
        self.assertIn("include-hidden-files: false", text)
        self.assertIn("retention-days: 7", text)
        upload = text.split("- name: Upload public E3 evidence", 1)[1]
        self.assertIn(f"path: {E3_STAGING_ROOT}", upload)
        self.assertNotIn("path: |", upload)
        for path in E3_ARTIFACT_FILES:
            self.assertNotIn(f"          {path}", upload)
        self.assertIn('test "$WORKFLOW_SHA" = "$SOURCE_SHA"', text)


class E3ArtifactTests(unittest.TestCase):
    def setUp(self):
        from tests.sandbox_security.test_e3_attestation import SignedE3AttestationTests

        factory = SignedE3AttestationTests()
        factory.setUp()
        self.identity = replace(factory.identity, workflow_sha=factory.identity.source_sha)
        self.attestation = factory._attestation()
        self.attestation["workflow_sha"] = self.identity.workflow_sha
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

    def test_builder_requires_the_canonical_phase_schema_id(self):
        from tools.sandbox_security import e3_artifact

        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as schema_directory:
            root = self._source(Path(source_directory))
            schema_root = Path(schema_directory)
            schema_path = schema_root / "contracts/forgeops-phase-exit-contract/1.0/schema.json"
            schema = json.loads((ROOT / "contracts/forgeops-phase-exit-contract/1.0/schema.json").read_text(encoding="utf-8"))
            schema["$id"] = "contracts/forgeops-phase-exit-contract/1.0/near-miss.json"
            self._write(schema_path, schema)

            with mock.patch.object(e3_artifact, "_ROOT", schema_root):
                with self.assertRaises(e3_artifact.ArtifactError):
                    e3_artifact.build_manifest(
                        root,
                        root / e3_artifact.E3_MANIFEST_FILE,
                        runner=self.runner,
                        validation_at=VALIDATION_AT,
                    )

    def test_phase_validator_receives_an_absolute_file_schema_uri(self):
        from tools.sandbox_security import e3_artifact

        observed_ids: list[object] = []
        real_validator = e3_artifact.Draft202012Validator

        def recording_validator(schema, *args, **kwargs):
            observed_ids.append(schema.get("$id"))
            return real_validator(schema, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            root = self._source(Path(directory))
            with mock.patch.object(e3_artifact, "Draft202012Validator", side_effect=recording_validator):
                e3_artifact.build_manifest(
                    root,
                    root / e3_artifact.E3_MANIFEST_FILE,
                    runner=self.runner,
                    validation_at=VALIDATION_AT,
                )

        expected = (ROOT / "contracts/forgeops-phase-exit-contract/1.0/schema.json").resolve().as_uri()
        self.assertEqual([expected], observed_ids)

    def test_builder_maps_phase_schema_resolution_failure_to_artifact_error(self):
        from tools.sandbox_security import e3_artifact

        class LegacyResolverFailure(Exception):
            pass

        with tempfile.TemporaryDirectory() as directory:
            root = self._source(Path(directory))
            with mock.patch.object(
                e3_artifact,
                "Draft202012Validator",
                side_effect=LegacyResolverFailure("#/$defs/decision"),
            ):
                with self.assertRaisesRegex(e3_artifact.ArtifactError, "^E3_ARTIFACT_INVALID$"):
                    e3_artifact.build_manifest(
                        root,
                        root / e3_artifact.E3_MANIFEST_FILE,
                        runner=self.runner,
                        validation_at=VALIDATION_AT,
                    )

    def test_staging_contains_only_the_exact_artifacts_tree(self):
        from tools.sandbox_security.e3_artifact import E3_ARTIFACT_FILES, E3_MANIFEST_FILE, E3_STAGING_ROOT, build_manifest, stage_upload_artifact

        with tempfile.TemporaryDirectory() as directory:
            root = self._source(Path(directory))
            build_manifest(root, root / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
            staging = stage_upload_artifact(root)
            self.assertEqual(root / E3_STAGING_ROOT, staging)
            self.assertEqual(set(E3_ARTIFACT_FILES), {path.relative_to(staging).as_posix() for path in staging.rglob("*") if path.is_file()})
            self.assertFalse(any(path.name.startswith(".") for path in staging.rglob("*")))

    def test_builder_and_staging_reject_parent_component_symlink(self):
        from tools.sandbox_security.e3_artifact import ArtifactError, E3_MANIFEST_FILE, build_manifest, stage_upload_artifact

        with tempfile.TemporaryDirectory() as directory:
            root = self._source(Path(directory))
            artifacts_directory = root / "artifacts"
            original_is_symlink = Path.is_symlink
            with mock.patch("pathlib.Path.is_symlink", autospec=True, side_effect=lambda value: value == artifacts_directory or original_is_symlink(value)):
                with self.assertRaises(ArtifactError):
                    build_manifest(root, root / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)

            build_manifest(root, root / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
            with mock.patch("pathlib.Path.is_symlink", autospec=True, side_effect=lambda value: value == artifacts_directory or original_is_symlink(value)):
                with self.assertRaises(ArtifactError):
                    stage_upload_artifact(root)

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

    def test_download_rejects_parent_symlink_and_externally_unbound_workflow_sha(self):
        from tools.sandbox_security.e3_artifact import ArtifactError, E3_MANIFEST_FILE, E3_PAYLOAD_FILES, build_manifest, verify_downloaded_artifact

        with tempfile.TemporaryDirectory() as directory:
            root = self._source(Path(directory))
            build_manifest(root, root / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
            artifacts_directory = root / "artifacts"
            original_is_symlink = Path.is_symlink
            with mock.patch("pathlib.Path.is_symlink", autospec=True, side_effect=lambda value: value == artifacts_directory or original_is_symlink(value)):
                with self.assertRaises(ArtifactError):
                    verify_downloaded_artifact(root, self.identity.repository, self.identity.repository_id, self.identity.default_branch, self.identity.run_id, self.identity.run_attempt, self.identity.source_sha, runner=self.runner, validation_at=VALIDATION_AT)

        with tempfile.TemporaryDirectory() as directory:
            root = self._source(Path(directory))
            build_manifest(root, root / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
            attestation = json.loads((root / E3_PAYLOAD_FILES[0]).read_text(encoding="utf-8"))
            attestation["workflow_sha"] = "b" * 40
            self._write(root / E3_PAYLOAD_FILES[0], attestation)
            manifest = json.loads((root / E3_MANIFEST_FILE).read_text(encoding="utf-8"))
            manifest["workflow_sha"] = "b" * 40
            manifest["files"][0]["sha256"] = hashlib.sha256((root / E3_PAYLOAD_FILES[0]).read_bytes()).hexdigest()
            manifest["files"][0]["size"] = (root / E3_PAYLOAD_FILES[0]).stat().st_size
            self._write(root / E3_MANIFEST_FILE, manifest)
            with self.assertRaises(ArtifactError):
                verify_downloaded_artifact(root, self.identity.repository, self.identity.repository_id, self.identity.default_branch, self.identity.run_id, self.identity.run_attempt, self.identity.source_sha, runner=self.runner, validation_at=VALIDATION_AT)

    def test_fresh_verified_artifact_imports_only_known_targets(self):
        from tools.sandbox_security.e3_artifact import E3_ARTIFACT_FILES, E3_MANIFEST_FILE, build_manifest, import_downloaded_artifact

        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            source = self._source(Path(source_directory))
            build_manifest(source, source / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
            target = Path(target_directory)
            imported = import_downloaded_artifact(source, target, self.identity, runner=self.runner, validation_at=VALIDATION_AT)
            self.assertEqual(set(E3_ARTIFACT_FILES), set(imported))
            self.assertEqual(set(E3_ARTIFACT_FILES), {path.relative_to(target).as_posix() for path in target.rglob("*") if path.is_file()})

    def test_import_uses_validated_snapshot_when_source_changes_during_verification(self):
        from tools.sandbox_security.e3_artifact import E3_MANIFEST_FILE, E3_PAYLOAD_FILES, build_manifest, import_downloaded_artifact

        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            source = self._source(Path(source_directory))
            build_manifest(source, source / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
            original = (source / E3_PAYLOAD_FILES[5]).read_bytes()

            def mutating_runner(arguments, **kwargs):
                result = self.runner(arguments, **kwargs)
                self._write(source / E3_PAYLOAD_FILES[5], {"status": "ATTACKER_REPLACEMENT"})
                return result

            target = Path(target_directory)
            import_downloaded_artifact(source, target, self.identity, runner=mutating_runner, validation_at=VALIDATION_AT)
            self.assertEqual(original, (target / E3_PAYLOAD_FILES[5]).read_bytes())

    def test_import_invalidates_manifest_and_prestages_before_mid_replace_failure(self):
        from tools.sandbox_security.e3_artifact import ArtifactError, E3_MANIFEST_FILE, E3_PAYLOAD_FILES, build_manifest, import_downloaded_artifact

        with tempfile.TemporaryDirectory() as source_directory, tempfile.TemporaryDirectory() as target_directory:
            source = self._source(Path(source_directory))
            build_manifest(source, source / E3_MANIFEST_FILE, runner=self.runner, validation_at=VALIDATION_AT)
            target = Path(target_directory)
            stale_manifest = target / E3_MANIFEST_FILE
            self._write(stale_manifest, {"status": "READY", "stale": True})
            calls = 0

            def fail_second_replace(source_path, target_path):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("injected replace failure")
                os.replace(source_path, target_path)

            with self.assertRaises(ArtifactError):
                import_downloaded_artifact(source, target, self.identity, runner=self.runner, validation_at=VALIDATION_AT, replacer=fail_second_replace)
            self.assertFalse(stale_manifest.exists())


if __name__ == "__main__":
    unittest.main()
