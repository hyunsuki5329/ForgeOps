"""Closed-schema and fake-runtime-observer tests."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "contracts/forgeops-sandbox-contract/1.0/schema.json"
SUITE_PATH = ROOT / "fixtures/forgeops-sandbox-security/suite.json"

IMAGE_CASES = (
    ("positive-signed-digest", "PASSED"),
    ("negative-tag-only", "SANDBOX_IMAGE_PROVENANCE_INVALID"),
    ("negative-signature-unverified", "SANDBOX_IMAGE_PROVENANCE_INVALID"),
    ("negative-issuer-mismatch", "SANDBOX_IMAGE_PROVENANCE_INVALID"),
)
CONTAINMENT_CASES = (
    ("positive-rootless-readonly", "PASSED"),
    ("negative-root-user", "SANDBOX_CONTAINMENT_VIOLATION"),
    ("negative-rootfs-writable", "SANDBOX_CONTAINMENT_VIOLATION"),
    ("negative-docker-socket", "SANDBOX_CONTAINMENT_VIOLATION"),
    ("negative-host-device", "SANDBOX_CONTAINMENT_VIOLATION"),
)
EGRESS_CASES = (
    ("positive-exact-proxy-destination", "PASSED"),
    ("negative-direct-dns", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-direct-socket", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-loopback", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-private-address", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-metadata-address", "SANDBOX_EGRESS_VIOLATION"),
    ("negative-redirect", "SANDBOX_EGRESS_VIOLATION"),
)
QUOTA_CASES = (
    ("positive-within-quota", "PASSED"),
    ("negative-quota-escape", "SANDBOX_QUOTA_VIOLATION"),
)
TEARDOWN_CASES = (
    ("positive-zero-residue", "PASSED"),
    ("negative-process-residue", "SANDBOX_TEARDOWN_INCOMPLETE"),
    ("negative-mount-residue", "SANDBOX_TEARDOWN_INCOMPLETE"),
    ("negative-secret-residue", "SANDBOX_TEARDOWN_INCOMPLETE"),
    ("negative-workspace-residue", "SANDBOX_TEARDOWN_INCOMPLETE"),
)

DIGEST_REF = "registry.example/forgeops@sha256:" + "a" * 64


def completed(*, stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


def fail_if_called(*_arguments, **_kwargs):
    raise AssertionError("subprocess runner must not be called")


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def load_schema() -> dict:
    return load_json(SCHEMA_PATH)


def walk(value: object):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class SandboxSchemaTests(unittest.TestCase):
    def test_every_object_is_closed(self):
        schema = load_schema()
        objects = [node for node in walk(schema) if node.get("type") == "object"]
        self.assertTrue(objects)
        self.assertTrue(all(node.get("additionalProperties") is False for node in objects))

    def test_runtime_enums_are_exact(self):
        schema = load_schema()
        profile = schema["$defs"]["RuntimeProfile"]
        observation = schema["$defs"]["RuntimeObservation"]
        sandbox_case = schema["$defs"]["SandboxCase"]

        self.assertEqual(["docker"], profile["properties"]["runtime"]["enum"])
        self.assertEqual(["test", "runtime"], observation["properties"]["evidence_kind"]["enum"])
        self.assertEqual(
            ["image_provenance", "containment", "egress", "quota", "teardown"],
            sandbox_case["properties"]["case_kind"]["enum"],
        )
        self.assertEqual(
            ["PASSED", "FAILED", "NOT_RUN"],
            sandbox_case["properties"]["result_status"]["enum"],
        )

    def test_observation_residue_and_address_fields_are_closed(self):
        schema = load_schema()
        observation = schema["$defs"]["RuntimeObservation"]
        residue = schema["$defs"]["Residue"]

        self.assertEqual(
            {"processes", "mounts", "leases", "transient_secrets", "workspaces"},
            set(residue["required"]),
        )
        self.assertTrue(
            all(field["minimum"] == 0 for field in residue["properties"].values())
        )
        self.assertTrue(observation["properties"]["connected_addresses"]["uniqueItems"])
        address_formats = {
            branch["format"]
            for branch in observation["properties"]["connected_addresses"]["items"]["anyOf"]
        }
        self.assertEqual({"ipv4", "ipv6"}, address_formats)

    def test_observation_validator_rejects_malformed_addresses_and_accepts_ip_addresses(self):
        from tools.sandbox_security import runtime

        observation = {
            "case_id": "address-check",
            "evidence_kind": "test",
            "observed_at": "2026-07-26T00:00:00Z",
            "provision_calls": 0,
            "network_calls": 0,
            "write_calls": 0,
            "root_uid": 1000,
            "rootfs_read_only": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "forbidden_mounts": 0,
            "forbidden_devices": 0,
            "direct_socket_calls": 0,
            "direct_dns_calls": 0,
            "proxy_calls": 0,
            "proxy_destination": "",
            "connected_addresses": ["192.0.2.1", "2001:db8::1"],
            "redirects": 0,
            "quota_exceeded": False,
            "residue": {
                "processes": 0,
                "mounts": 0,
                "leases": 0,
                "transient_secrets": 0,
                "workspaces": 0,
            },
        }
        validator = runtime.schema_validator(load_schema(), "RuntimeObservation")

        validator.validate(observation)
        observation["connected_addresses"] = ["999.0.0.1"]

        with self.assertRaisesRegex(Exception, "999.0.0.1"):
            validator.validate(observation)

        observation["connected_addresses"] = ["2001:db8:::1"]

        with self.assertRaisesRegex(Exception, "2001:db8:::1"):
            validator.validate(observation)


class SandboxCatalogTests(unittest.TestCase):
    def test_case_catalogs_are_exactly_ordered(self):
        suite = load_json(SUITE_PATH)

        self.assertEqual(IMAGE_CASES, tuple((case["id"], case["expected"]) for case in suite["image_cases"]))
        self.assertEqual(
            CONTAINMENT_CASES,
            tuple((case["id"], case["expected"]) for case in suite["containment_cases"]),
        )
        self.assertEqual(EGRESS_CASES, tuple((case["id"], case["expected"]) for case in suite["egress_cases"]))
        self.assertEqual(QUOTA_CASES, tuple((case["id"], case["expected"]) for case in suite["quota_cases"]))
        self.assertEqual(
            TEARDOWN_CASES,
            tuple((case["id"], case["expected"]) for case in suite["teardown_cases"]),
        )

    def test_negative_cases_declare_exact_effect_counts(self):
        suite = load_json(SUITE_PATH)
        cases = (
            *suite["image_cases"],
            *suite["containment_cases"],
            *suite["egress_cases"],
            *suite["quota_cases"],
            *suite["teardown_cases"],
        )

        for case in cases:
            self.assertEqual(
                {"expected_provision_calls", "expected_network_calls", "expected_write_calls"},
                {key for key in case if key.startswith("expected_") and key.endswith("_calls")},
            )
            if case.get("observation_mode") == "PREPROVISION_DENIED":
                self.assertEqual(
                    (0, 0, 0),
                    (
                        case["expected_provision_calls"],
                        case["expected_network_calls"],
                        case["expected_write_calls"],
                    ),
                )


class FakeObserverTests(unittest.TestCase):
    def test_unknown_case_never_falls_back_to_runtime(self):
        from tools.sandbox_security import runtime

        observer = runtime.FakeRuntimeObserver({})

        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_RUNTIME_UNAVAILABLE"):
            observer.observe({"id": "unknown"})

        self.assertEqual(0, observer.process_calls)


class DockerObserverTests(unittest.TestCase):
    """Injected boundary tests; they never invoke a Docker process."""

    @staticmethod
    def capability_runner(calls):
        def runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            if arguments[1:3] == ["version", "--format"]:
                return completed(stdout='{"SecurityOptions": ["name=rootless"]}')
            if arguments[1:3] == ["image", "inspect"]:
                return completed(
                    stdout=json.dumps(
                        {
                            "RepoDigests": [DIGEST_REF],
                            "Config": {
                                "Labels": {
                                    "forgeops.signature.verified": "true",
                                    "forgeops.issuer": "forgeops-test-issuer",
                                    "forgeops.provenance": "provenance:forgeops-test",
                                }
                            },
                        }
                    )
                )
            return completed()

        return runner

    def test_docker_observer_uses_argument_list_and_never_shell(self):
        """Treating an injected runner as an E3-capable runtime must fail."""
        from tools.sandbox_security import runtime

        calls = []
        observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=self.capability_runner(calls))

        profile = observer.inspect_capability()

        self.assertFalse(profile["available"])
        self.assertNotIsInstance(observer, runtime.TrustedRuntimeObserver)
        self.assertFalse(observer.runtime_evidence_trusted)
        self.assertEqual("unavailable", profile["image_ref"])
        self.assertEqual("unavailable", profile["provenance_ref"])
        self.assertIsInstance(calls[0][0], list)
        self.assertFalse(calls[0][1]["shell"])
        self.assertEqual(30, calls[0][1]["timeout"])
        self.assertTrue(calls[0][1]["capture_output"])
        self.assertTrue(calls[0][1]["text"])
        self.assertFalse(calls[0][1]["check"])

    def test_non_digest_image_is_rejected_before_runner(self):
        """A tag-only preflight must return a safe unavailable profile before any runner call."""
        from tools.sandbox_security import runtime

        observer = runtime.DockerRuntimeObserver("docker", "forgeops/sandbox:latest", runner=fail_if_called)

        profile = observer.inspect_capability()

        self.assertFalse(profile["available"])
        self.assertEqual("unavailable", profile["image_ref"])

    def test_observe_uses_fixed_hardening_flags_for_a_registered_probe(self):
        """A test-injected success must not fabricate a runtime observation."""
        from tools.sandbox_security import runtime

        calls = []
        observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=self.capability_runner(calls))

        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_RUNTIME_UNAVAILABLE"):
            observer.observe({"id": "positive-rootless-readonly", "case_kind": "containment"})

        self.assertEqual(
            [["docker", "version", "--format"], ["docker", "image", "inspect"]],
            [arguments[:3] for arguments, _kwargs in calls],
        )
        self.assertFalse(any(arguments[1] == "run" for arguments, _kwargs in calls))

    def test_probe_argv_is_exact_and_near_misses_are_rejected(self):
        """Adding a mount, device, privilege, or alternate command must be denied."""
        from tools.sandbox_security import runtime

        observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=fail_if_called)
        expected = [
            "docker", "run", "--rm", "--detach", "--read-only", "--cap-drop=ALL",
            "--security-opt=no-new-privileges", "--pids-limit=64", "--memory=128m",
            "--cpus=0.5", "--network=none", "--user=1000:1000", "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=16m", DIGEST_REF, "/bin/sh", "-c", "sleep 30",
        ]

        self.assertEqual(expected, observer._probe_command())
        for forbidden in ("--privileged", "--volume=/var/run/docker.sock:/var/run/docker.sock", "--device=/dev/null"):
            with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_RUNTIME_UNAVAILABLE"):
                observer._run([*expected[:-3], forbidden, *expected[-3:]])

    def test_labels_without_an_independent_verifier_fail_closed(self):
        """Trusting self-asserted image labels must not make a profile available."""
        from tools.sandbox_security import runtime

        observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=self.capability_runner([]))

        profile = observer.inspect_capability()

        self.assertFalse(profile["available"])
        self.assertFalse(profile["signature_verified"])
        self.assertEqual("unavailable", profile["issuer"])

    def test_injected_docker_observer_never_projects_e3_runtime_evidence(self):
        """Changing the trust boundary must not turn runner doubles into E3 proof."""
        from tools.sandbox_security import runtime, verify

        results = verify.run_cases(
            "sandbox-security",
            load_json(SUITE_PATH),
            runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=self.capability_runner([])),
            "2026-07-26T00:00:00Z",
        )

        self.assertTrue(results)
        self.assertTrue(all(result["status"] == "NOT_RUN" for result in results))
        self.assertTrue(all(not result["runtime_evidence"] for result in results))

    def test_rootless_false_is_public_safe_not_ready(self):
        """Rootful Docker must not authorize a capability profile."""
        from tools.sandbox_security import runtime

        def rootful_runner(arguments, **_kwargs):
            if arguments[1] == "version":
                return completed(stdout='{"SecurityOptions": []}')
            return completed(stdout=json.dumps({"RepoDigests": [DIGEST_REF]}))

        profile = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=rootful_runner).inspect_capability()

        self.assertFalse(profile["available"])
        self.assertFalse(profile["rootless"])
        self.assertEqual("unavailable", profile["image_ref"])

    def test_malformed_inspect_is_public_safe_not_ready(self):
        """Malformed image inspection must not be treated as absence of risk."""
        from tools.sandbox_security import runtime

        def malformed_runner(arguments, **_kwargs):
            if arguments[1] == "version":
                return completed(stdout='{"SecurityOptions": ["name=rootless"]}')
            return completed(stdout="not-json")

        profile = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=malformed_runner).inspect_capability()

        self.assertFalse(profile["available"])
        self.assertFalse(profile["rootless"])
        self.assertEqual("unavailable", profile["image_ref"])

    def test_cleanup_requires_explicit_remove_and_confirmed_absence(self):
        """Assuming `--rm` succeeded without a post-remove inspection must fail."""
        from tools.sandbox_security import runtime

        container_id = "b" * 64
        calls = []

        def cleanup_runner(arguments, **kwargs):
            calls.append((arguments, kwargs))
            if arguments[1:3] == ["rm", "-f"]:
                return completed(returncode=0)
            return completed(returncode=1, stdout="", stderr="No such object")

        observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=cleanup_runner)
        observer._tracked_container_id = container_id

        self.assertTrue(observer._cleanup_confirmed(container_id))
        self.assertEqual(
            [
                ["docker", "rm", "-f", container_id],
                ["docker", "inspect", container_id, "--format", "{{json .}}"],
            ],
            [arguments for arguments, _kwargs in calls],
        )

    def test_timeout_range_accepts_only_one_through_thirty_seconds(self):
        """Removing the timeout bound would permit an unbounded Docker invocation."""
        from tools.sandbox_security import runtime

        for timeout in (1, 30):
            observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, timeout, runner=lambda *_a, **_k: completed())
            self.assertEqual(0, observer._run(["docker", "version", "--format", "{{json .Server}}"]).returncode)
        for timeout in (0, 31, True, "30"):
            observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, timeout, runner=fail_if_called)
            with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_RUNTIME_UNAVAILABLE"):
                observer._run(["docker", "version", "--format", "{{json .Server}}"])

    def test_closed_local_verifier_is_required_for_the_verified_type(self):
        """Accepting callbacks, mappings, or malformed provenance would forge image trust."""
        from tools.sandbox_security import runtime

        provenance_ref = "sha256:" + "b" * 64

        closed = runtime.LocalImageVerifier(
            runtime.LocalVerificationProvenance(
                image_ref=DIGEST_REF,
                signature_verified=True,
                provenance_verified=True,
                issuer="forgeops-test-issuer",
                provenance_ref=provenance_ref,
            )
        )
        verified = runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, closed)
        self.assertTrue(verified.runtime_evidence_trusted)
        self.assertEqual(provenance_ref, verified._verified_attestation().provenance_ref)

        callback = runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, lambda _image: {})
        self.assertFalse(callback.runtime_evidence_trusted)
        self.assertIsNone(callback._verified_attestation())

        class MalformedVerifier:
            def verify(self, _image_ref):
                return runtime.LocalVerificationProvenance(
                    image_ref=DIGEST_REF,
                    signature_verified=True,
                    provenance_verified=True,
                    issuer="forgeops-test-issuer",
                    provenance_ref="private/path",
                )

        self.assertIsNone(
            runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, MalformedVerifier())._verified_attestation()
        )

    def test_mapping_verifier_and_instance_observe_shadow_cannot_pass_e3(self):
        """Mutable verifier and instance-method replacement must not cross the construction seal."""
        from tools.sandbox_security import runtime, verify

        mapping_verifier = runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, {"signature_verified": True})
        self.assertFalse(runtime.has_e3_construction(mapping_verifier))

        closed = runtime.LocalImageVerifier(
            runtime.LocalVerificationProvenance(
                image_ref=DIGEST_REF,
                signature_verified=True,
                provenance_verified=True,
                issuer="forgeops-test-issuer",
                provenance_ref="sha256:" + "c" * 64,
            )
        )
        observer = runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, closed)
        observer.observe = lambda case: SandboxEvaluatorTests.valid_observation(case["id"])

        self.assertFalse(runtime.has_e3_construction(observer))
        results = verify.run_cases("sandbox-security", load_json(SUITE_PATH), observer, "2026-07-26T00:00:00Z")
        self.assertTrue(all(result["status"] == "NOT_RUN" for result in results))
        self.assertTrue(all(not result["runtime_evidence"] for result in results))

    def test_malformed_provenance_yields_safe_unavailable_profile(self):
        """Invalid verifier fields must not escape preflight as an exception or public value."""
        from tools.sandbox_security import runtime

        verifier = runtime.LocalImageVerifier(
            runtime.LocalVerificationProvenance(
                image_ref=DIGEST_REF,
                signature_verified=True,
                provenance_verified=True,
                issuer="forgeops-test-issuer",
                provenance_ref="not-a-hash",
            )
        )
        observer = runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, verifier)

        def inspect_runner(arguments, **_kwargs):
            if arguments[1] == "version":
                return completed(stdout='{"SecurityOptions": ["name=rootless"]}')
            return completed(stdout=json.dumps({"RepoDigests": [DIGEST_REF]}))

        observer._run = inspect_runner
        profile = observer.inspect_capability()

        self.assertFalse(profile["available"])
        self.assertEqual("unavailable", profile["provenance_ref"])

    def test_final_profile_preserves_only_the_validated_provenance_hash(self):
        """Profile serialization must retain the strict verified hash, not a static or raw verifier value."""
        from tools.sandbox_security import runtime

        provenance_ref = "sha256:" + "e" * 64

        class ProfileObserver(runtime.DockerRuntimeObserver):
            def _verified_attestation(self):
                return runtime.LocalVerificationProvenance(
                    image_ref=DIGEST_REF,
                    signature_verified=True,
                    provenance_verified=True,
                    issuer="forgeops-test-issuer",
                    provenance_ref=provenance_ref,
                )

        def runner(arguments, **_kwargs):
            if arguments[1] == "version":
                return completed(stdout='{"SecurityOptions": ["name=rootless"]}')
            return completed(stdout=json.dumps({"RepoDigests": [DIGEST_REF]}))

        observer = ProfileObserver("docker", DIGEST_REF, runner=runner)
        profile = observer.inspect_capability()

        self.assertTrue(profile["available"])
        self.assertEqual(provenance_ref, profile["provenance_ref"])
        self.assertFalse(runtime.has_e3_construction(observer))

    def test_full_observe_malformed_id_marks_residual_uncertainty_without_e3(self):
        """A malformed detached ID follows the lifecycle denial path without guessing a cleanup target."""
        from tools.sandbox_security import runtime

        class LifecycleObserver(runtime.DockerRuntimeObserver):
            def _verified_attestation(self):
                return runtime.LocalVerificationProvenance(
                    image_ref=DIGEST_REF,
                    signature_verified=True,
                    provenance_verified=True,
                    issuer="forgeops-test-issuer",
                    provenance_ref="sha256:" + "d" * 64,
                )

        def runner(arguments, **_kwargs):
            if arguments[1] == "version":
                return completed(stdout='{"SecurityOptions": ["name=rootless"]}')
            if arguments[1:3] == ["image", "inspect"]:
                return completed(stdout=json.dumps({"RepoDigests": [DIGEST_REF]}))
            return completed(stdout="not-a-container-id")

        observer = LifecycleObserver("docker", DIGEST_REF, runner=runner)
        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_TEARDOWN_INCOMPLETE"):
            observer.observe({"id": "positive-rootless-readonly", "case_kind": "containment"})
        self.assertTrue(observer.residual_uncertainty)
        self.assertFalse(runtime.has_e3_construction(observer))

    def test_e3_seal_rejects_mutated_image_helpers_and_privileged_probe(self):
        """Mutable image or helper state must not alter the sealed E3 probe."""
        from tools.sandbox_security import runtime

        def sealed_observer():
            return runtime.VerifiedDockerRuntimeObserver(
                "docker",
                DIGEST_REF,
                runtime.LocalImageVerifier(
                    runtime.LocalVerificationProvenance(
                        image_ref=DIGEST_REF,
                        signature_verified=True,
                        provenance_verified=True,
                        issuer="forgeops-test-issuer",
                        provenance_ref="sha256:" + "f" * 64,
                    )
                ),
            )

        observer = sealed_observer()
        self.assertTrue(runtime.has_e3_construction(observer))
        observer._image_ref = "registry.example/forgeops@sha256:" + "0" * 64
        self.assertFalse(runtime.has_e3_construction(observer))

        observer = sealed_observer()
        observer._verified_attestation = lambda: None
        self.assertFalse(runtime.has_e3_construction(observer))

        observer = sealed_observer()
        observer._probe_command = lambda: ["docker", "run", "--rm", "--privileged", DIGEST_REF]
        self.assertFalse(runtime.has_e3_construction(observer))

    def test_e3_rejects_builder_and_subprocess_global_mutation_before_construction(self):
        """Rebinding a trusted builder or subprocess global must never mint an E3 observer."""
        from tools.sandbox_security import runtime, verify

        verifier = runtime.LocalImageVerifier(
            runtime.LocalVerificationProvenance(
                image_ref=DIGEST_REF,
                signature_verified=True,
                provenance_verified=True,
                issuer="forgeops-test-issuer",
                provenance_ref="sha256:" + "2" * 64,
            )
        )
        original_builder = runtime._probe_argv
        original_runner = runtime.subprocess.run
        try:
            runtime._probe_argv = lambda image_ref: (
                "docker", "run", "--rm", "--privileged", image_ref,
            )
            runtime.subprocess.run = lambda *_args, **_kwargs: completed()
            observer = runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, verifier)
            self.assertFalse(runtime.has_e3_construction(observer))
            results = verify.run_cases(
                "sandbox-security", load_json(SUITE_PATH), observer, "2026-07-26T00:00:00Z"
            )
        finally:
            runtime._probe_argv = original_builder
            runtime.subprocess.run = original_runner

        self.assertFalse(runtime.has_e3_construction(observer))
        self.assertTrue(all(result["status"] == "NOT_RUN" for result in results))
        self.assertTrue(all(not result["runtime_evidence"] for result in results))

    def test_e3_rejects_mutable_hardening_and_cleanup_helpers_after_construction(self):
        """Replacing any capability or lifecycle helper must invalidate the whole E3 call graph."""
        from tools.sandbox_security import runtime

        verifier = runtime.LocalImageVerifier(
            runtime.LocalVerificationProvenance(
                image_ref=DIGEST_REF,
                signature_verified=True,
                provenance_verified=True,
                issuer="forgeops-test-issuer",
                provenance_ref="sha256:" + "3" * 64,
            )
        )
        observer = runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, verifier)
        original_hardening = vars(runtime.DockerRuntimeObserver)["_inspection_confirms_hardening"]
        original_cleanup = runtime.DockerRuntimeObserver._cleanup_confirmed
        try:
            runtime.DockerRuntimeObserver._inspection_confirms_hardening = staticmethod(lambda _value: True)
            runtime.DockerRuntimeObserver._cleanup_confirmed = lambda _self, _container_id: True
            self.assertFalse(runtime.has_e3_construction(observer))
        finally:
            runtime.DockerRuntimeObserver._inspection_confirms_hardening = original_hardening
            runtime.DockerRuntimeObserver._cleanup_confirmed = original_cleanup

    def test_callback_mapping_and_injected_runner_are_never_e3(self):
        """Only exact closed verifier values plus the import-time runner can enter E3."""
        from tools.sandbox_security import runtime

        for verifier in (lambda _image_ref: {}, {"signature_verified": True}):
            observer = runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, verifier)
            self.assertFalse(runtime.has_e3_construction(observer))

        injected = runtime.DockerRuntimeObserver(
            "docker", DIGEST_REF, runner=lambda *_args, **_kwargs: completed()
        )
        self.assertFalse(runtime.has_e3_construction(injected))

    def test_exact_verified_observer_probe_timeout_is_safe_nonpass_with_uncertainty(self):
        """A TimeoutExpired before a container ID exists must leave explicit teardown uncertainty."""
        from tools.sandbox_security import runtime

        verifier = runtime.LocalImageVerifier(
            runtime.LocalVerificationProvenance(
                image_ref=DIGEST_REF,
                signature_verified=True,
                provenance_verified=True,
                issuer="forgeops-test-issuer",
                provenance_ref="sha256:" + "4" * 64,
            )
        )
        observer = runtime.VerifiedDockerRuntimeObserver("docker", DIGEST_REF, verifier)

        class FakeProcess:
            def __init__(self, stdout="", stderr="", timeout=False):
                self._stdout = stdout
                self._stderr = stderr
                self._timeout = timeout
                self.returncode = 0
                self.args = []

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def communicate(self, input=None, timeout=None):
                if self._timeout:
                    raise subprocess.TimeoutExpired(["docker", "run"], timeout)
                return self._stdout, self._stderr

            def poll(self):
                return self.returncode

            def kill(self):
                return None

            def wait(self):
                return self.returncode

        processes = [
            FakeProcess(stdout='{"SecurityOptions": ["name=rootless"]}'),
            FakeProcess(stdout=json.dumps({"RepoDigests": [DIGEST_REF]})),
            FakeProcess(timeout=True),
        ]
        with mock.patch("subprocess.Popen", side_effect=processes):
            with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_TEARDOWN_INCOMPLETE"):
                runtime.observe_e3(
                    observer, {"id": "positive-rootless-readonly", "case_kind": "containment"}
                )

        self.assertTrue(observer.residual_uncertainty)
        self.assertTrue(runtime.has_e3_construction(observer))

    def test_probe_timeout_marks_residual_uncertainty_before_any_result(self):
        """A bounded run timeout must not be mistaken for a cleaned-up sandbox."""
        from tools.sandbox_security import runtime

        class LifecycleObserver(runtime.DockerRuntimeObserver):
            def _verified_attestation(self):
                return runtime.LocalVerificationProvenance(
                    image_ref=DIGEST_REF,
                    signature_verified=True,
                    provenance_verified=True,
                    issuer="forgeops-test-issuer",
                    provenance_ref="sha256:" + "1" * 64,
                )

        def runner(arguments, **_kwargs):
            if arguments[1] == "version":
                return completed(stdout='{"SecurityOptions": ["name=rootless"]}')
            if arguments[1:3] == ["image", "inspect"]:
                return completed(stdout=json.dumps({"RepoDigests": [DIGEST_REF]}))
            raise subprocess.TimeoutExpired(arguments, 30)

        observer = LifecycleObserver("docker", DIGEST_REF, runner=runner)
        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_TEARDOWN_INCOMPLETE"):
            observer.observe({"id": "positive-rootless-readonly", "case_kind": "containment"})
        self.assertTrue(observer.residual_uncertainty)
        self.assertFalse(runtime.has_e3_construction(observer))

    def test_lifecycle_cleanup_failures_are_not_confirmed(self):
        """A failed remove or a still-inspectable container leaves teardown uncertain."""
        from tools.sandbox_security import runtime

        container_id = "c" * 64
        for remove_result, inspect_result in (
            (completed(returncode=1), completed(returncode=1, stderr="No such object")),
            (completed(), completed(returncode=0, stdout="{}")),
        ):
            calls = []

            def runner(arguments, **_kwargs):
                calls.append(arguments)
                return remove_result if arguments[1] == "rm" else inspect_result

            observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=runner)
            observer._tracked_container_id = container_id
            self.assertFalse(observer._cleanup_confirmed(container_id))
            self.assertEqual(["docker", "rm", "-f", container_id], calls[0])

    def test_detached_container_id_parser_rejects_each_unusable_run_result(self):
        """A failed, blank, short, or non-hex detached ID leaves no safe cleanup target."""
        from tools.sandbox_security import runtime

        for result in (
            completed(returncode=1),
            completed(stdout=""),
            completed(stdout="abc"),
            completed(stdout="G" * 64),
        ):
            self.assertIsNone(runtime.DockerRuntimeObserver._container_id(result))

    def test_inspect_parser_requires_each_hardening_fact(self):
        """Any missing parsed Docker fact must prevent a containment observation."""
        from tools.sandbox_security import runtime

        valid = {
            "Config": {"User": "1000:1000"},
            "HostConfig": {
                "ReadonlyRootfs": True,
                "CapDrop": ["ALL"],
                "SecurityOpt": ["no-new-privileges"],
                "PidsLimit": 64,
                "Memory": 134217728,
                "NanoCpus": 500000000,
                "NetworkMode": "none",
                "Devices": [],
            },
            "Mounts": [],
        }
        self.assertTrue(runtime.DockerRuntimeObserver._inspection_confirms_hardening(valid))
        for field, invalid in (
            ("User", "0"), ("ReadonlyRootfs", False), ("CapDrop", []),
            ("SecurityOpt", []), ("PidsLimit", 0), ("Memory", 0),
            ("NanoCpus", 0), ("NetworkMode", "bridge"), ("Devices", [{}]),
        ):
            candidate = json.loads(json.dumps(valid))
            section = candidate["Config"] if field == "User" else candidate["HostConfig"]
            section[field] = invalid
            self.assertFalse(runtime.DockerRuntimeObserver._inspection_confirms_hardening(candidate))
        self.assertFalse(runtime.DockerRuntimeObserver._inspection_confirms_hardening({"Config": {}, "HostConfig": {}}))

    def test_unknown_probe_kind_is_rejected_before_runner(self):
        """Accepting a caller-defined probe kind would permit arbitrary Docker commands."""
        from tools.sandbox_security import runtime

        observer = runtime.DockerRuntimeObserver("docker", DIGEST_REF, runner=fail_if_called)

        with self.assertRaisesRegex(runtime.RuntimeUnavailable, "SANDBOX_RUNTIME_UNAVAILABLE"):
            observer.observe({"id": "arbitrary", "case_kind": "shell"})

    def test_preloaded_observation_is_returned_as_a_copy(self):
        from tools.sandbox_security import runtime

        expected = runtime.RuntimeObservation(
            case_id="known",
            evidence_kind="test",
            observed_at="2026-07-26T00:00:00Z",
            provision_calls=0,
            network_calls=0,
            write_calls=0,
            root_uid=1000,
            rootfs_read_only=True,
            cap_drop_all=True,
            no_new_privileges=True,
            forbidden_mounts=0,
            forbidden_devices=0,
            direct_socket_calls=0,
            direct_dns_calls=0,
            proxy_calls=0,
            proxy_destination="",
            connected_addresses=(),
            redirects=0,
            quota_exceeded=False,
            residue=runtime.Residue(),
        )
        observer = runtime.FakeRuntimeObserver({"known": expected})

        observed = observer.observe({"id": "known"})
        observed.connected_addresses += ("127.0.0.1",)

        self.assertEqual((), expected.connected_addresses)
        self.assertEqual(0, observer.process_calls)


class SandboxEvaluatorTests(unittest.TestCase):
    """Pure evaluator tests; production regressions caught are named below."""

    @staticmethod
    def valid_profile() -> dict:
        return {
            "runtime": "docker",
            "available": True,
            "rootless": True,
            "image_ref": "registry.example/forgeops@sha256:" + "a" * 64,
            "image_digest": "sha256:" + "a" * 64,
            "signature_verified": True,
            "issuer": "forgeops-test-issuer",
            "expected_issuer": "forgeops-test-issuer",
            "provenance_ref": "provenance:forgeops-test",
            "observed_at": "2026-07-26T00:00:00Z",
        }

    @staticmethod
    def valid_observation(case_id: str) -> dict:
        return {
            "case_id": case_id,
            "evidence_kind": "test",
            "observed_at": "2026-07-26T00:00:00Z",
            "provision_calls": 1,
            "network_calls": 0,
            "write_calls": 0,
            "root_uid": 1000,
            "rootfs_read_only": True,
            "cap_drop_all": True,
            "no_new_privileges": True,
            "forbidden_mounts": 0,
            "forbidden_devices": 0,
            "direct_socket_calls": 0,
            "direct_dns_calls": 0,
            "proxy_calls": 0,
            "proxy_destination": "",
            "connected_addresses": [],
            "redirects": 0,
            "quota_exceeded": False,
            "residue": {
                "processes": 0,
                "mounts": 0,
                "leases": 0,
                "transient_secrets": 0,
                "workspaces": 0,
            },
        }

    def setUp(self):
        from tools.sandbox_security import runtime

        self.observer = runtime.FakeRuntimeObserver({})

    def egress_case(self, case_id: str) -> dict:
        suite = load_json(SUITE_PATH)
        return next(case for case in suite["egress_cases"] if case["id"] == case_id)

    def observing_all_cases(
        self,
        evidence_kind: str = "test",
        unavailable_case: str | None = None,
        trusted: bool = False,
        observed_at: str = "2026-07-26T00:00:00Z",
    ):
        from tools.sandbox_security import runtime

        test = self

        class RecordingObserver(runtime.TrustedRuntimeObserver if trusted else object):
            def __init__(self):
                self.case_ids = []

            def observe(self, case):
                self.case_ids.append(case["id"])
                if case["id"] == unavailable_case:
                    from tools.sandbox_security import runtime

                    raise runtime.RuntimeUnavailable(r"C:\private\secret.txt")
                observation = test.valid_observation(case["id"])
                observation["evidence_kind"] = evidence_kind
                observation["observed_at"] = observed_at
                observation["provision_calls"] = case["expected_provision_calls"]
                observation["network_calls"] = case["expected_network_calls"]
                observation["write_calls"] = case["expected_write_calls"]
                if case["case_kind"] == "egress" and case["id"] == "positive-exact-proxy-destination":
                    observation["proxy_calls"] = 1
                    observation["proxy_destination"] = case["expected_proxy_destination"]
                elif case["id"] == "negative-root-user":
                    observation["root_uid"] = 0
                elif case["id"] == "negative-rootfs-writable":
                    observation["rootfs_read_only"] = False
                elif case["id"] == "negative-docker-socket":
                    observation["forbidden_mounts"] = 1
                elif case["id"] == "negative-host-device":
                    observation["forbidden_devices"] = 1
                elif case["id"] == "negative-direct-dns":
                    observation["direct_dns_calls"] = 1
                elif case["id"] == "negative-direct-socket":
                    observation["direct_socket_calls"] = 1
                elif case["id"] == "negative-loopback":
                    observation["connected_addresses"] = ["127.0.0.1"]
                elif case["id"] == "negative-private-address":
                    observation["connected_addresses"] = ["10.0.0.1"]
                elif case["id"] == "negative-metadata-address":
                    observation["connected_addresses"] = ["169.254.169.254"]
                elif case["id"] == "negative-redirect":
                    observation["redirects"] = 1
                elif case["id"] == "negative-quota-escape":
                    observation["quota_exceeded"] = True
                elif case["id"] == "negative-process-residue":
                    observation["residue"]["processes"] = 1
                elif case["id"] == "negative-mount-residue":
                    observation["residue"]["mounts"] = 1
                elif case["id"] == "negative-secret-residue":
                    observation["residue"]["transient_secrets"] = 1
                elif case["id"] == "negative-workspace-residue":
                    observation["residue"]["workspaces"] = 1
                return observation

        return RecordingObserver()

    def test_unverified_signature_is_rejected_before_any_observation(self):
        """Removing provenance verification must deny before any observer call."""
        from tools.sandbox_security import verify

        profile = self.valid_profile()
        profile["signature_verified"] = False

        with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_IMAGE_PROVENANCE_INVALID"):
            verify.validate_runtime_profile(profile, "2026-07-26T00:01:00Z")

        self.assertEqual(0, self.observer.process_calls)

    def test_private_connected_address_is_an_egress_violation(self):
        """Removing private-address denial must fail this egress fixture."""
        from tools.sandbox_security import verify

        case = self.egress_case("negative-private-address")
        observation = self.valid_observation(case["id"])
        observation["provision_calls"] = case["expected_provision_calls"]
        observation["network_calls"] = case["expected_network_calls"]
        observation["connected_addresses"] = ["10.0.0.1"]

        with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_EGRESS_VIOLATION"):
            verify.evaluate_observation(case, observation, "2026-07-26T00:00:00Z")

    def test_proxy_destination_must_exactly_match_the_egress_case(self):
        """Removing exact proxy matching must accept a redirected destination."""
        from tools.sandbox_security import verify

        case = self.egress_case("positive-exact-proxy-destination")
        observation = self.valid_observation(case["id"])
        observation["network_calls"] = case["expected_network_calls"]
        observation["proxy_calls"] = 1
        observation["proxy_destination"] = "other-proxy.invalid:443"

        with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_EGRESS_VIOLATION"):
            verify.evaluate_observation(case, observation, "2026-07-26T00:00:00Z")

    def test_issuer_must_match_the_pinned_expected_issuer(self):
        """Removing issuer equality must admit a profile from another issuer."""
        from tools.sandbox_security import verify

        profile = self.valid_profile()
        profile["issuer"] = "other-issuer"

        with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_IMAGE_PROVENANCE_INVALID"):
            verify.validate_runtime_profile(profile, "2026-07-26T00:01:00Z")

    def test_profile_cannot_replace_both_issuer_values_to_bypass_the_trusted_pin(self):
        """Replacing both mutable issuer fields must not change evaluator trust."""
        from tools.sandbox_security import verify

        profile = self.valid_profile()
        profile["issuer"] = "attacker-issuer"
        profile["expected_issuer"] = "attacker-issuer"

        with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_IMAGE_PROVENANCE_INVALID"):
            verify.validate_runtime_profile(profile, "2026-07-26T00:01:00Z")

    def test_profile_freshness_rejects_stale_and_future_observations(self):
        """Removing the bounded trusted-time check must admit stale or future profiles."""
        from tools.sandbox_security import verify

        for observed_at in ("2026-07-25T23:54:59Z", "2026-07-26T00:00:01Z"):
            profile = self.valid_profile()
            profile["observed_at"] = observed_at
            with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_RUNTIME_UNAVAILABLE"):
                verify.validate_runtime_profile(profile, "2026-07-26T00:00:00Z")

    def test_effect_count_mismatch_precedes_a_detected_containment_violation(self):
        """Removing effect checks must hide a provision call made before denial."""
        from tools.sandbox_security import verify

        suite = load_json(SUITE_PATH)
        case = next(case for case in suite["containment_cases"] if case["id"] == "negative-root-user")
        observation = self.valid_observation(case["id"])
        observation["root_uid"] = 0
        observation["provision_calls"] = case["expected_provision_calls"] + 1

        with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_EFFECT_CONTRACT_INVALID"):
            verify.evaluate_observation(case, observation, "2026-07-26T00:00:00Z")

    def test_each_observed_effect_dimension_rejects_a_mismatch(self):
        """Removing any individual effect assertion must admit its mismatch."""
        from tools.sandbox_security import verify

        suite = load_json(SUITE_PATH)
        case = next(case for case in suite["containment_cases"] if case["id"] == "positive-rootless-readonly")
        for effect in ("provision_calls", "network_calls", "write_calls"):
            observation = self.valid_observation(case["id"])
            observation["provision_calls"] = case["expected_provision_calls"]
            observation["network_calls"] = case["expected_network_calls"]
            observation["write_calls"] = case["expected_write_calls"]
            observation[effect] += 1
            with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_EFFECT_CONTRACT_INVALID"):
                verify.evaluate_observation(case, observation, "2026-07-26T00:00:00Z")

    def test_fake_observer_with_runtime_label_never_produces_e3_passed(self):
        """Trusting an observation label rather than its observer must fail this test."""
        from tools.sandbox_security import runtime, verify

        suite = load_json(SUITE_PATH)
        observations = {}
        for case in (*suite["image_cases"], *suite["containment_cases"], *suite["egress_cases"], *suite["quota_cases"], *suite["teardown_cases"]):
            observation = self.valid_observation(case["id"])
            observation["evidence_kind"] = "runtime"
            observation["provision_calls"] = case["expected_provision_calls"]
            observation["network_calls"] = case["expected_network_calls"]
            observation["write_calls"] = case["expected_write_calls"]
            if case["id"] == "positive-exact-proxy-destination":
                observation["proxy_calls"] = 1
                observation["proxy_destination"] = case["expected_proxy_destination"]
            observations[case["id"]] = observation

        results = verify.run_cases(
            "sandbox-security",
            suite,
            runtime.FakeRuntimeObserver(observations),
            "2026-07-26T00:00:00Z",
        )

        self.assertTrue(all(result["status"] == "NOT_RUN" for result in results))

    def test_stale_runtime_observation_is_not_run_against_trusted_validation_time(self):
        """Removing observation freshness must turn this stale runtime record into E3."""
        from tools.sandbox_security import verify

        suite = load_json(SUITE_PATH)
        results = verify.run_cases(
            "sandbox-security",
            suite,
            self.observing_all_cases("runtime", trusted=True, observed_at="2026-07-25T23:54:59Z"),
            "2026-07-26T00:00:00Z",
        )
        result = next(result for result in results if result["case_id"] == "positive-rootless-readonly")

        self.assertEqual("NOT_RUN", result["status"])
        self.assertEqual("SANDBOX_RUNTIME_UNAVAILABLE", result["actual"])

    def test_unknown_and_generic_runtime_errors_map_to_the_safe_not_run_category(self):
        """Returning observer error text must leak these untrusted failures."""
        from tools.sandbox_security import runtime, verify

        suite = load_json(SUITE_PATH)

        class UnknownRuntimeObserver:
            def observe(self, _case):
                raise runtime.RuntimeUnavailable(r"unknown C:\private\secret.txt")

        class GenericRuntimeObserver:
            def observe(self, _case):
                raise RuntimeError(r"generic C:\private\secret.txt")

        for observer in (UnknownRuntimeObserver(), GenericRuntimeObserver()):
            results = verify.run_cases("sandbox-security", suite, observer, "2026-07-26T00:00:00Z")
            result = next(result for result in results if result["case_id"] == "positive-rootless-readonly")
            encoded = json.dumps(result)
            self.assertEqual("NOT_RUN", result["status"])
            self.assertEqual("SANDBOX_RUNTIME_UNAVAILABLE", result["actual"])
            self.assertNotIn("private", encoded)
            self.assertNotIn("secret", encoded)

    def test_non_mapping_observer_return_is_closed_without_echoing_raw_content(self):
        """Letting a raw observer value reach public projection must fail this test."""
        from tools.sandbox_security import runtime, verify

        suite = load_json(SUITE_PATH)

        class RawValueObserver(runtime.TrustedRuntimeObserver):
            def observe(self, _case):
                return r"C:\private\secret.txt"

        results = verify.run_cases("sandbox-security", suite, RawValueObserver(), "2026-07-26T00:00:00Z")
        result = next(result for result in results if result["case_id"] == "positive-rootless-readonly")
        encoded = json.dumps(result)

        self.assertEqual("NOT_RUN", result["status"])
        self.assertEqual("SANDBOX_EVALUATION_INVALID", result["actual"])
        self.assertFalse(result["runtime_evidence"])
        self.assertEqual(
            (0, 0, 0),
            (result["provision_calls"], result["network_calls"], result["write_calls"]),
        )
        self.assertNotIn("private", encoded)
        self.assertNotIn("secret", encoded)

    def test_image_profile_cases_are_evaluated_before_observing_negative_cases(self):
        """Removing profile-first dispatch must observe invalid image cases."""
        from tools.sandbox_security import verify

        suite = load_json(SUITE_PATH)
        observer = self.observing_all_cases("runtime", trusted=True)

        results = verify.run_cases("sandbox-security", suite, observer, "2026-07-26T00:00:00Z")

        all_cases = [case for catalog in ("image_cases", "containment_cases", "egress_cases", "quota_cases", "teardown_cases") for case in suite[catalog]]
        self.assertEqual([case["id"] for case in all_cases], [result["case_id"] for result in results])
        self.assertEqual(
            ["positive-signed-digest"],
            [case_id for case_id in observer.case_ids if case_id in {case["id"] for case in suite["image_cases"]}],
        )

    def test_generic_runtime_marker_is_not_e3_evidence(self):
        """A generic marker class must not substitute for the exact verified observer type."""
        from tools.sandbox_security import verify

        suite = load_json(SUITE_PATH)
        fake_results = verify.run_cases("sandbox-security", suite, self.observing_all_cases("test"), "2026-07-26T00:00:00Z")
        runtime_results = verify.run_cases("sandbox-security", suite, self.observing_all_cases("runtime", trusted=True), "2026-07-26T00:00:00Z")

        self.assertTrue(all(result["status"] == "NOT_RUN" for result in fake_results))
        image_negative_ids = {case["id"] for case in suite["image_cases"] if case["kind"] == "negative"}
        self.assertTrue(all(result["status"] == "NOT_RUN" for result in runtime_results))
        self.assertTrue(all(not result["runtime_evidence"] for result in runtime_results))

    def test_runtime_exception_is_not_run_and_never_echoes_untrusted_error_data(self):
        """Removing runtime-error mapping leaks arbitrary observer exception data."""
        from tools.sandbox_security import verify

        suite = load_json(SUITE_PATH)
        results = verify.run_cases(
            "sandbox-security",
            suite,
            self.observing_all_cases("runtime", unavailable_case="positive-rootless-readonly", trusted=True),
            "2026-07-26T00:00:00Z",
        )
        result = next(result for result in results if result["case_id"] == "positive-rootless-readonly")

        self.assertEqual("NOT_RUN", result["status"])
        self.assertEqual("SANDBOX_RUNTIME_UNAVAILABLE", result["actual"])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))

    def test_negative_fixture_categories_match_with_exact_observed_effect_counts(self):
        """Removing effect-count or category checks must fail a negative fixture."""
        from tools.sandbox_security import runtime, verify

        suite = load_json(SUITE_PATH)
        observations = {}
        for catalog in (
            "image_cases",
            "containment_cases",
            "egress_cases",
            "quota_cases",
            "teardown_cases",
        ):
            for case in suite[catalog]:
                observation = self.valid_observation(case["id"])
                observation["provision_calls"] = case["expected_provision_calls"]
                observation["network_calls"] = case["expected_network_calls"]
                observation["write_calls"] = case["expected_write_calls"]
                if case["id"] == "positive-exact-proxy-destination":
                    observation["proxy_calls"] = 1
                    observation["proxy_destination"] = case["expected_proxy_destination"]
                if case["id"] == "negative-root-user":
                    observation["root_uid"] = 0
                elif case["id"] == "negative-rootfs-writable":
                    observation["rootfs_read_only"] = False
                elif case["id"] == "negative-docker-socket":
                    observation["forbidden_mounts"] = 1
                elif case["id"] == "negative-host-device":
                    observation["forbidden_devices"] = 1
                elif case["id"] == "negative-direct-dns":
                    observation["direct_dns_calls"] = 1
                elif case["id"] == "negative-direct-socket":
                    observation["direct_socket_calls"] = 1
                elif case["id"] == "negative-loopback":
                    observation["connected_addresses"] = ["127.0.0.1"]
                elif case["id"] == "negative-private-address":
                    observation["connected_addresses"] = ["10.0.0.1"]
                elif case["id"] == "negative-metadata-address":
                    observation["connected_addresses"] = ["169.254.169.254"]
                elif case["id"] == "negative-redirect":
                    observation["redirects"] = 1
                elif case["id"] == "negative-quota-escape":
                    observation["quota_exceeded"] = True
                elif case["id"] == "negative-process-residue":
                    observation["residue"]["processes"] = 1
                elif case["id"] == "negative-mount-residue":
                    observation["residue"]["mounts"] = 1
                elif case["id"] == "negative-secret-residue":
                    observation["residue"]["transient_secrets"] = 1
                elif case["id"] == "negative-workspace-residue":
                    observation["residue"]["workspaces"] = 1
                observations[case["id"]] = observation

        results = verify.run_cases("sandbox-security", suite, runtime.FakeRuntimeObserver(observations), "2026-07-26T00:00:00Z")

        expected_cases = [
            case
            for catalog in ("image_cases", "containment_cases", "egress_cases", "quota_cases", "teardown_cases")
            for case in suite[catalog]
        ]
        self.assertEqual([(case["id"], case["expected"]) for case in expected_cases], [(result["case_id"], result["actual"]) for result in results])
        self.assertTrue(all(result["status"] == "NOT_RUN" for result in results))
        for case, result in zip(expected_cases, results, strict=True):
            self.assertEqual(
                (case["expected_provision_calls"], case["expected_network_calls"], case["expected_write_calls"]),
                (result["provision_calls"], result["network_calls"], result["write_calls"]),
            )

    def test_test_evidence_is_never_reported_as_e3_runtime_evidence(self):
        """Changing the evidence gate must fail this non-runtime observation."""
        from tools.sandbox_security import verify

        result = verify.public_case(
            "positive-rootless-readonly",
            "PASSED",
            "PASSED",
            self.valid_observation("positive-rootless-readonly"),
        )

        self.assertFalse(result["runtime_evidence"])
        self.assertNotIn("raw_observation", result)

    def test_public_projection_rejects_an_unsafe_case_identifier(self):
        """Removing public identifier validation must leak this host path."""
        from tools.sandbox_security import verify

        with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_PUBLIC_RESULT_UNSAFE"):
            verify.public_case(
                r"case-C:\private\runtime.json",
                "PASSED",
                "PASSED",
                self.valid_observation("positive-rootless-readonly"),
            )


class SandboxCliTests(unittest.TestCase):
    """Public-only VG-008 CLI behavior; these tests never invoke Docker."""

    def test_registered_commands_have_exact_result_paths(self):
        from tools.sandbox_security import verify

        self.assertEqual(
            {
                "image-provenance-negative": "artifacts/verification/vg-008-image-provenance-result.json",
                "containment-egress-negative": "artifacts/verification/vg-008-containment-egress-result.json",
                "teardown-negative": "artifacts/verification/vg-008-teardown-result.json",
            },
            verify.TRUSTED_RESULTS,
        )

    def test_missing_or_unavailable_profile_writes_closed_not_run_result(self):
        from tools.sandbox_security import verify

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            schema = root / "contracts/forgeops-sandbox-contract/1.0/schema.json"
            suite = root / "fixtures/forgeops-sandbox-security/suite.json"
            result = root / "artifacts/verification/vg-008-teardown-result.json"
            schema.parent.mkdir(parents=True)
            suite.parent.mkdir(parents=True)
            schema.write_text(SCHEMA_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            suite.write_text(SUITE_PATH.read_text(encoding="utf-8"), encoding="utf-8")

            exit_code = verify.run_cli(
                schema="contracts/forgeops-sandbox-contract/1.0/schema.json",
                suite="fixtures/forgeops-sandbox-security/suite.json",
                runtime_profile="artifacts/runtime/sandbox-runtime-profile.json",
                runtime="docker",
                result="artifacts/verification/vg-008-teardown-result.json",
                command_id="teardown-negative",
                project_root=root,
            )

            public_result = load_json(result)

        self.assertNotEqual(0, exit_code)
        self.assertEqual("NOT_RUN", public_result["status"])
        self.assertEqual("SANDBOX_RUNTIME_UNAVAILABLE", public_result["category"])
        self.assertFalse(public_result["e3_runtime_assertion"])
        self.assertNotIn("cases", public_result)

    def test_public_not_run_result_excludes_private_input_content(self):
        from tools.sandbox_security import verify

        result = verify.safe_not_run(
            "image-provenance-negative",
            "SANDBOX_RUNTIME_UNAVAILABLE",
            input_hashes={
                "schema_sha256": "a" * 64,
                "suite_sha256": "b" * 64,
                "runtime_profile_sha256": "c" * 64,
            },
        )

        serialized = json.dumps(result, sort_keys=True)
        self.assertEqual("NOT_RUN", result["status"])
        self.assertEqual("SANDBOX_RUNTIME_UNAVAILABLE", result["category"])
        self.assertNotIn(r"C:\\private", serialized)
        self.assertNotIn("token=", serialized)
        self.assertNotIn("raw_observation", serialized)

    def test_cli_rejects_aliases_unregistered_inputs_and_mismatched_result_pairing(self):
        from tools.sandbox_security import verify

        registered = {
            "schema": "contracts/forgeops-sandbox-contract/1.0/schema.json",
            "suite": "fixtures/forgeops-sandbox-security/suite.json",
            "runtime_profile": "artifacts/runtime/sandbox-runtime-profile.json",
            "runtime": "docker",
            "result": "artifacts/verification/vg-008-image-provenance-result.json",
            "command_id": "image-provenance-negative",
        }
        rejected_overrides = (
            {"schema": "contracts/forgeops-sandbox-contract/1.0/../1.0/schema.json"},
            {"suite": "./fixtures/forgeops-sandbox-security/suite.json"},
            {"runtime_profile": "ARTIFACTS/runtime/sandbox-runtime-profile.json"},
            {"result": "artifacts/verification/../verification/vg-008-image-provenance-result.json"},
            {"result": "artifacts/verification/vg-008-teardown-result.json"},
            {"runtime": "Docker"},
        )

        for override in rejected_overrides:
            with self.subTest(override=override), self.assertRaisesRegex(
                verify.SandboxError, "SANDBOX_PUBLIC_RESULT_UNSAFE"
            ):
                verify.run_cli(**(registered | override))

    def test_safe_not_run_rejects_unknown_or_incomplete_hash_key_sets(self):
        from tools.sandbox_security import verify

        full_hashes = {
            "schema_sha256": "a" * 64,
            "suite_sha256": "b" * 64,
            "runtime_profile_sha256": "c" * 64,
        }
        hostile_hashes = full_hashes | {r"C:\\private\\token": "d" * 64}

        with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_PUBLIC_RESULT_UNSAFE"):
            verify.safe_not_run(
                "image-provenance-negative",
                "SANDBOX_RUNTIME_UNAVAILABLE",
                input_hashes=hostile_hashes,
            )
        with self.assertRaisesRegex(verify.SandboxError, "SANDBOX_PUBLIC_RESULT_UNSAFE"):
            verify.safe_not_run(
                "image-provenance-negative",
                "SANDBOX_RUNTIME_UNAVAILABLE",
                input_hashes={"runtime_profile_sha256": "a" * 64},
            )

    def test_direct_script_cli_writes_the_registered_closed_result(self):
        result = ROOT / "artifacts/verification/vg-008-image-provenance-result.json"
        completed_process = subprocess.run(
            [
                "python",
                "tools/sandbox_security/verify.py",
                "--schema",
                "contracts/forgeops-sandbox-contract/1.0/schema.json",
                "--suite",
                "fixtures/forgeops-sandbox-security/suite.json",
                "--runtime-profile",
                "artifacts/runtime/sandbox-runtime-profile.json",
                "--runtime",
                "docker",
                "--result",
                str(result.relative_to(ROOT)),
                "--command-id",
                "image-provenance-negative",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(2, completed_process.returncode, completed_process.stderr)
        self.assertEqual("NOT_RUN", load_json(result)["status"])


if __name__ == "__main__":
    unittest.main()
