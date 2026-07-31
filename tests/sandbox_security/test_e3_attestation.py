"""Tests for importing a signed, public-safe E3 runtime attestation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SUITE_PATH = ROOT / "fixtures/forgeops-sandbox-security/suite.json"
SCHEMA_PATH = ROOT / "contracts/forgeops-e3-attestation/1.0/schema.json"
FIXTURE_PATH = ROOT / "fixtures/forgeops-e3-attestation/suite.json"
VALIDATION_AT = datetime(2026, 7, 30, tzinfo=timezone.utc)


def canonical_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


class SignedE3AttestationTests(unittest.TestCase):
    """The importer accepts only an exact identity-bound public attestation."""

    def setUp(self) -> None:
        from tools.sandbox_security.e3_attestation import ExpectedIdentity

        self.identity = ExpectedIdentity(
            repository="example/forgeops",
            repository_id="123456",
            default_branch="main",
            source_sha="a" * 40,
            workflow_sha="b" * 40,
            run_id="1001",
            run_attempt=1,
            image_ref="ghcr.io/example/forgeops-e3@sha256:" + "c" * 64,
            image_digest="sha256:" + "c" * 64,
        )

    def _attestation(self) -> dict:
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
        observed_at = "2026-07-30T00:00:00Z"
        cases = [case for catalog in ("image_cases", "containment_cases", "egress_cases", "quota_cases", "teardown_cases") for case in suite[catalog]]
        observations = []
        for case, fixture_observation in zip(cases, fixture["observations"], strict=True):
            observation = {
                "case_id": case["id"], "evidence_kind": "runtime", "observation_mode": fixture_observation["observation_mode"],
                "observed_at": observed_at, "provision_calls": case["expected_provision_calls"], "network_calls": case["expected_network_calls"], "write_calls": case["expected_write_calls"],
                "root_uid": 1000, "rootfs_read_only": True, "cap_drop_all": True, "no_new_privileges": True,
                "forbidden_mounts": 0, "forbidden_devices": 0, "direct_socket_calls": 0, "direct_dns_calls": 0,
                "proxy_calls": 1 if case["case_kind"] == "egress" else 0, "proxy_destination": case["expected_proxy_destination"],
                "connected_addresses": [], "redirects": 0, "quota_exceeded": False,
                "residue": {"processes": 0, "mounts": 0, "leases": 0, "transient_secrets": 0, "workspaces": 0},
            }
            observations.append(observation)
        attestation = {
            "attestation_version": "1.0", "repository": "example/forgeops", "repository_id": "123456", "workflow_ref": "refs/heads/main",
            "workflow_sha": "b" * 40, "source_sha": "a" * 40, "run_id": "1001", "run_attempt": 1,
            "issuer": "https://token.actions.githubusercontent.com", "certificate_identity": self.identity.certificate_identity,
            "image_ref": self.identity.image_ref, "image_digest": self.identity.image_digest, "observed_at": observed_at,
            "capabilities": {"rootless": True, "cgroup_version": "2", "cgroup_driver": "systemd", "memory_controller": True, "pids_controller": True, "cpu_controller": True},
            "input_hashes": {"sandbox_schema_sha256": hashlib.sha256(SCHEMA_PATH.parents[3].joinpath("contracts/forgeops-sandbox-contract/1.0/schema.json").read_bytes()).hexdigest(), "sandbox_suite_sha256": hashlib.sha256(SUITE_PATH.read_bytes()).hexdigest(), "runtime_profile_sha256": "", "helper_sha256": "d" * 64, "probe_sha256": "e" * 64},
            "observations": observations, "terminal_residue": {"processes": 0, "mounts": 0, "leases": 0, "transient_secrets": 0, "workspaces": 0},
        }
        profile = {"runtime": "docker", "available": True, "rootless": True, "image_ref": self.identity.image_ref, "image_digest": self.identity.image_digest, "signature_verified": True, "issuer": attestation["issuer"], "expected_issuer": attestation["issuer"], "provenance_ref": "sha256:" + hashlib.sha256(canonical_bytes((self.identity.image_ref, self.identity.image_digest, attestation["issuer"], self.identity.certificate_identity))).hexdigest(), "observed_at": observed_at}
        attestation["input_hashes"]["runtime_profile_sha256"] = sha256(profile)
        return attestation

    @staticmethod
    def _runner(arguments, *, shell, check, capture_output, text, timeout):
        if not (shell is False and check is False and capture_output is True and text is True and timeout == 30):
            raise AssertionError("cosign must be invoked with its closed process boundary")
        return subprocess.CompletedProcess(arguments, 0, stdout="verified", stderr="")

    def _write_inputs(self, directory: Path, attestation: dict | None = None, bundle: bytes = b"bundle") -> tuple[Path, Path]:
        attestation_path = directory / "e3-attestation.json"
        bundle_path = directory / "e3-attestation.bundle.json"
        attestation_path.write_bytes(canonical_bytes(self._attestation() if attestation is None else attestation))
        bundle_path.write_bytes(bundle)
        return attestation_path, bundle_path

    @staticmethod
    def _refresh_profile_hash(attestation: dict) -> None:
        profile = {
            "runtime": "docker", "available": True, "rootless": attestation["capabilities"]["rootless"],
            "image_ref": attestation["image_ref"], "image_digest": attestation["image_digest"], "signature_verified": True,
            "issuer": attestation["issuer"], "expected_issuer": attestation["issuer"],
            "provenance_ref": "sha256:" + hashlib.sha256(canonical_bytes((attestation["image_ref"], attestation["image_digest"], attestation["issuer"], attestation["certificate_identity"]))).hexdigest(),
            "observed_at": attestation["observed_at"],
        }
        attestation["input_hashes"]["runtime_profile_sha256"] = sha256(profile)

    def test_schema_is_closed_and_fixture_has_all_registered_cases_once(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(False, schema["additionalProperties"])
        for definition in schema["$defs"].values():
            if definition.get("type") == "object":
                self.assertFalse(definition.get("additionalProperties", True))
        observed_ids = [item["case_id"] for item in fixture["observations"]]
        suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
        registered_ids = [case["id"] for catalog in ("image_cases", "containment_cases", "egress_cases", "quota_cases", "teardown_cases") for case in suite[catalog]]
        self.assertEqual(23, len(observed_ids))
        self.assertEqual(registered_ids, observed_ids)
        self.assertEqual(23, len(set(observed_ids)))

    def test_expected_identity_has_the_fixed_certificate_identity(self):
        self.assertEqual(
            "https://github.com/example/forgeops/.github/workflows/vg-008-e3.yml@refs/heads/main",
            self.identity.certificate_identity,
        )

    def test_verifies_and_imports_exact_identity_with_closed_cosign_arguments(self):
        from tools.sandbox_security.e3_attestation import import_signed_attestation, verify_signed_attestation

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            attestation_path, bundle_path = self._write_inputs(root)
            verified = verify_signed_attestation(attestation_path, bundle_path, self.identity, self._runner, VALIDATION_AT)
            outputs = import_signed_attestation(attestation_path, bundle_path, self.identity, root, self._runner, VALIDATION_AT)

            self.assertEqual(self.identity.image_digest, verified["image_digest"])
            self.assertEqual(
                {"profile", "observations", "receipt"},
                set(outputs),
            )
            profile = json.loads(outputs["profile"].read_text(encoding="utf-8"))
            receipt = json.loads(outputs["receipt"].read_text(encoding="utf-8"))
            observations = json.loads(outputs["observations"].read_text(encoding="utf-8"))
            self.assertEqual("test", receipt["verification_kind"])
            self.assertEqual(hashlib.sha256(outputs["profile"].read_bytes()).hexdigest(), receipt["runtime_profile_sha256"])
            self.assertEqual(
                {"processes": 0, "mounts": 0, "leases": 0, "transient_secrets": 0, "workspaces": 0},
                observations["terminal_residue"],
            )
            self.assertEqual(self.identity.image_ref, profile["image_ref"])

    def test_direct_verification_uses_the_complete_fixed_cosign_argv(self):
        from tools.sandbox_security.e3_attestation import verify_signed_attestation

        calls = []

        def runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            return subprocess.CompletedProcess(arguments, 0, stdout="verified", stderr="")

        with tempfile.TemporaryDirectory() as temporary_directory:
            attestation_path, bundle_path = self._write_inputs(Path(temporary_directory))
            verify_signed_attestation(attestation_path, bundle_path, self.identity, runner, VALIDATION_AT)

        self.assertEqual(
            [[
                "cosign", "verify-blob", "--bundle", str(bundle_path), "--certificate-identity",
                self.identity.certificate_identity, "--certificate-oidc-issuer",
                "https://token.actions.githubusercontent.com", str(attestation_path),
            ]],
            [arguments for arguments, _kwargs in calls],
        )
        self.assertEqual(
            [{"shell": False, "check": False, "capture_output": True, "text": True, "timeout": 30}],
            [kwargs for _arguments, kwargs in calls],
        )

    def test_rejects_identity_mismatches_before_or_after_signature_verification(self):
        from tools.sandbox_security.e3_attestation import E3Error, verify_signed_attestation

        mismatches = {
            "issuer": "https://issuer.invalid",
            "repository": "example/other",
            "repository_id": "999",
            "source_sha": "d" * 40,
            "workflow_sha": "e" * 40,
            "run_id": "1002",
            "run_attempt": 2,
            "image_ref": "ghcr.io/example/forgeops-e3@sha256:" + "d" * 64,
            "image_digest": "sha256:" + "d" * 64,
            "certificate_identity": "https://github.com/example/forgeops/.github/workflows/vg-008-e3.yml@refs/heads/other",
        }
        for key, value in mismatches.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary_directory:
                attestation = self._attestation()
                attestation[key] = value
                paths = self._write_inputs(Path(temporary_directory), attestation)
                with self.assertRaisesRegex(E3Error, "E3_IDENTITY_INVALID"):
                    verify_signed_attestation(*paths, self.identity, self._runner, VALIDATION_AT)

    def test_rejects_closed_schema_and_integrity_violations(self):
        from tools.sandbox_security.e3_attestation import E3Error, verify_signed_attestation

        mutations = {
            "malformed_digest": lambda value: value.__setitem__("image_digest", "sha256:" + "C" * 64),
            "uppercase_sha": lambda value: value.__setitem__("source_sha", "A" * 40),
            "duplicate_case": lambda value: value["observations"].__setitem__(1, deepcopy(value["observations"][0])),
            "extra_property": lambda value: value.__setitem__("unexpected", True),
            "secret_like_property": lambda value: value.__setitem__("token", "not-a-secret"),
            "non_zero_residue": lambda value: value["terminal_residue"].__setitem__("mounts", 1),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary_directory:
                attestation = self._attestation()
                mutate(attestation)
                paths = self._write_inputs(Path(temporary_directory), attestation)
                with self.assertRaisesRegex(E3Error, "E3_ATTESTATION_INVALID"):
                    verify_signed_attestation(*paths, self.identity, self._runner, VALIDATION_AT)

    def test_rejects_every_forbidden_raw_key_and_allows_certificate_identity(self):
        from tools.sandbox_security.e3_attestation import E3Error, verify_signed_attestation

        forbidden = ("token", "secret", "credential", "environment", "stdout", "stderr", "log", "certificate_pem", "certificate_chain", "private_path")
        for key in forbidden:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temporary_directory:
                attestation = self._attestation()
                attestation[key] = "public-placeholder"
                with self.assertRaisesRegex(E3Error, "E3_ATTESTATION_INVALID"):
                    verify_signed_attestation(*self._write_inputs(Path(temporary_directory), attestation), self.identity, self._runner, VALIDATION_AT)
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.assertEqual(self.identity.certificate_identity, self._attestation()["certificate_identity"])
            verify_signed_attestation(*self._write_inputs(Path(temporary_directory)), self.identity, self._runner, VALIDATION_AT)

    def test_rejects_non_ghcr_or_wrong_repository_package_identity(self):
        from tools.sandbox_security.e3_attestation import E3Error, verify_signed_attestation

        image_refs = (
            ("registry.example/example/forgeops-e3@sha256:" + "c" * 64, "E3_ATTESTATION_INVALID"),
            ("ghcr.io/example/other-e3@sha256:" + "c" * 64, "E3_IDENTITY_INVALID"),
        )
        for image_ref, error_code in image_refs:
            with self.subTest(image_ref=image_ref), tempfile.TemporaryDirectory() as temporary_directory:
                expected = replace(self.identity, image_ref=image_ref)
                attestation = self._attestation()
                attestation["image_ref"] = image_ref
                self._refresh_profile_hash(attestation)
                with self.assertRaisesRegex(E3Error, error_code):
                    verify_signed_attestation(*self._write_inputs(Path(temporary_directory), attestation), expected, self._runner, VALIDATION_AT)

    def test_rejects_capabilities_that_cannot_support_e3_import(self):
        from tools.sandbox_security.e3_attestation import E3Error, verify_signed_attestation

        incompatible = {
            "rootless": False, "cgroup_version": "1", "cgroup_driver": "cgroupfs",
            "memory_controller": False, "pids_controller": False, "cpu_controller": False,
        }
        for field, value in incompatible.items():
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary_directory:
                attestation = self._attestation()
                attestation["capabilities"][field] = value
                self._refresh_profile_hash(attestation)
                with self.assertRaisesRegex(E3Error, "E3_ATTESTATION_INVALID"):
                    verify_signed_attestation(*self._write_inputs(Path(temporary_directory), attestation), self.identity, self._runner, VALIDATION_AT)

    def test_import_uses_snapshot_bytes_for_verification_and_receipt(self):
        from tools.sandbox_security.e3_attestation import import_signed_attestation

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            attestation_path, bundle_path = self._write_inputs(root)
            verified_bytes = {}

            def runner(arguments, **kwargs):
                verified_bytes["attestation"] = Path(arguments[-1]).read_bytes()
                verified_bytes["bundle"] = Path(arguments[3]).read_bytes()
                self.assertNotEqual(attestation_path, Path(arguments[-1]))
                self.assertNotEqual(bundle_path, Path(arguments[3]))
                attestation_path.write_bytes(b"attacker replacement")
                bundle_path.write_bytes(b"attacker bundle replacement")
                return subprocess.CompletedProcess(arguments, 0, stdout="verified", stderr="")

            outputs = import_signed_attestation(attestation_path, bundle_path, self.identity, root, runner, VALIDATION_AT)
            receipt = json.loads(outputs["receipt"].read_text(encoding="utf-8"))

        self.assertEqual(hashlib.sha256(verified_bytes["attestation"]).hexdigest(), receipt["attestation_sha256"])
        self.assertEqual(hashlib.sha256(verified_bytes["bundle"]).hexdigest(), receipt["bundle_sha256"])

    def test_failed_verification_creates_none_of_the_three_output_files(self):
        from tools.sandbox_security.e3_attestation import E3Error, import_signed_attestation

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            attestation = self._attestation()
            attestation["terminal_residue"]["processes"] = 1
            paths = self._write_inputs(root, attestation)
            with self.assertRaisesRegex(E3Error, "E3_ATTESTATION_INVALID"):
                import_signed_attestation(*paths, self.identity, root, self._runner, VALIDATION_AT)
            self.assertFalse((root / "artifacts/runtime/sandbox-runtime-profile.json").exists())
            self.assertFalse((root / "artifacts/runtime/sandbox-runtime-observations.json").exists())
            self.assertFalse((root / "artifacts/runtime/sandbox-e3-import-receipt.json").exists())

    def test_rejects_stale_and_future_evidence(self):
        from tools.sandbox_security.e3_attestation import E3Error, verify_signed_attestation

        for offset in (-301, 1):
            with self.subTest(offset=offset), tempfile.TemporaryDirectory() as temporary_directory:
                attestation = self._attestation()
                timestamp = VALIDATION_AT + timedelta(seconds=offset)
                attestation["observed_at"] = timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")
                for observation in attestation["observations"]:
                    observation["observed_at"] = attestation["observed_at"]
                paths = self._write_inputs(Path(temporary_directory), attestation)
                with self.assertRaisesRegex(E3Error, "E3_EVIDENCE_STALE"):
                    verify_signed_attestation(*paths, self.identity, self._runner, VALIDATION_AT)

    def test_detects_attestation_or_bundle_tampering_in_receipt_hashes(self):
        from tools.sandbox_security.e3_attestation import import_signed_attestation

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            attestation_path, bundle_path = self._write_inputs(root)
            outputs = import_signed_attestation(attestation_path, bundle_path, self.identity, root, self._runner, VALIDATION_AT)
            receipt = json.loads(outputs["receipt"].read_text(encoding="utf-8"))
            self.assertEqual(hashlib.sha256(attestation_path.read_bytes()).hexdigest(), receipt["attestation_sha256"])
            self.assertEqual(hashlib.sha256(bundle_path.read_bytes()).hexdigest(), receipt["bundle_sha256"])
            attestation_path.write_bytes(b"tampered")
            bundle_path.write_bytes(b"tampered bundle")
            self.assertNotEqual(hashlib.sha256(attestation_path.read_bytes()).hexdigest(), receipt["attestation_sha256"])
            self.assertNotEqual(hashlib.sha256(bundle_path.read_bytes()).hexdigest(), receipt["bundle_sha256"])


if __name__ == "__main__":
    unittest.main()
