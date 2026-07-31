"""Tests for the fixed, recording-runner E3 probe helper."""

from __future__ import annotations

import json
import io
import inspect
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/forgeops-sandbox-contract/1.0/schema.json"
SUITE = ROOT / "fixtures/forgeops-sandbox-security/suite.json"
IMAGE = "ghcr.io/example/forgeops-e3@sha256:" + "c" * 64


class RootlessSetupTests(unittest.TestCase):
    def test_subid_mapping_requires_exact_user_and_positive_numeric_range(self):
        script = (ROOT / "tools/sandbox_security/setup_rootless.sh").read_text(encoding="utf-8")
        self.assertIn("has_subid_mapping()", script)
        self.assertIn("$1 == user", script)
        self.assertIn("$2 ~ /^[0-9]+$/", script)
        self.assertIn("$3 ~ /^[0-9]+$/", script)
        self.assertIn("$2 > 0 && $3 > 0", script)
        self.assertIn('has_subid_mapping /etc/subuid || fail "E3_ROOTLESS_SUBUID_MISSING" 24', script)
        self.assertIn('has_subid_mapping /etc/subgid || fail "E3_ROOTLESS_SUBGID_MISSING" 25', script)
        self.assertNotIn('grep -qF "${runner_user}:"', script)

    def test_setup_names_each_prerequisite_and_runtime_failure_with_a_stable_code(self):
        script = (ROOT / "tools/sandbox_security/setup_rootless.sh").read_text(encoding="utf-8")
        expected = {
            "E3_ROOTLESS_MUST_BE_UNPRIVILEGED": 20,
            "E3_ROOTLESS_SETUP_TOOL_MISSING": 21,
            "E3_ROOTLESS_NEWUIDMAP_MISSING": 22,
            "E3_ROOTLESS_NEWGIDMAP_MISSING": 23,
            "E3_ROOTLESS_SUBUID_MISSING": 24,
            "E3_ROOTLESS_SUBGID_MISSING": 25,
            "E3_ROOTLESS_CGROUP_V2_REQUIRED": 26,
            "E3_ROOTLESS_CONTROLLER_MISSING": 27,
            "E3_ROOTLESS_RUNTIME_DIR_INVALID": 28,
            "E3_ROOTLESS_USER_BUS_MISSING": 29,
            "E3_ROOTLESS_INSTALL_FAILED": 30,
            "E3_ROOTLESS_SERVICE_FAILED": 31,
            "E3_ROOTLESS_SOCKET_MISSING": 32,
            "E3_ROOTLESS_SECURITY_OPTION_MISSING": 33,
            "E3_ROOTLESS_CGROUP_DRIVER_INVALID": 34,
        }
        for reason, code in expected.items():
            with self.subTest(reason=reason):
                self.assertIn(f'fail "{reason}" {code}', script)

    def test_controller_check_is_order_independent_and_rejects_each_missing_controller(self):
        script = (ROOT / "tools/sandbox_security/setup_rootless.sh").read_text(encoding="utf-8")
        self.assertIn("for controller in memory pids cpu", script)
        self.assertIn('" $controller "', script)

        def admitted(value: str) -> bool:
            available = set(value.split())
            return all(name in available for name in ("memory", "pids", "cpu"))

        self.assertTrue(admitted("cpuset cpu io memory hugetlb pids rdma misc dmem"))
        for missing in ("memory", "pids", "cpu"):
            with self.subTest(missing=missing):
                self.assertFalse(admitted(" ".join(name for name in ("memory", "pids", "cpu") if name != missing)))


class RecordingRunner:
    """A complete Docker-response double; no process is ever started."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, arguments: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        self.calls.append((arguments, kwargs))
        joined = " ".join(arguments)
        if arguments[:3] == ["docker", "info", "--format"]:
            if "SecurityOptions" in arguments[-1]:
                return subprocess.CompletedProcess(arguments, 0, stdout='["name=rootless"]', stderr="")
            if "CgroupVersion" in arguments[-1]:
                return subprocess.CompletedProcess(arguments, 0, stdout="2 systemd\n", stderr="")
            return subprocess.CompletedProcess(arguments, 0, stdout="memory pids cpu\n", stderr="")
        if arguments[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps({"RepoDigests": [IMAGE]}), stderr="")
        if "FORGEOPS_PROBE_MODE=" in joined:
            if "FORGEOPS_PROBE_MODE=egress-client" in joined:
                base = {
                    "root_uid": 1000, "rootfs_read_only": True, "cap_drop_all": True,
                    "no_new_privileges": True, "forbidden_mounts": 0, "forbidden_devices": 0,
                    "direct_socket_calls": 0, "direct_dns_calls": 0, "proxy_calls": 0,
                    "proxy_destination": "", "connected_addresses": [], "redirects": 0,
                    "quota_exceeded": False,
                }
                scenarios = {
                    "positive-exact-proxy-destination": {**base, "proxy_calls": 1, "proxy_destination": "proxy.sandbox.invalid:443"},
                    "negative-direct-dns": {**base, "direct_dns_calls": 1},
                    "negative-direct-socket": {**base, "direct_socket_calls": 1},
                    "negative-loopback": {**base, "direct_socket_calls": 1},
                    "negative-private-address": {**base, "direct_socket_calls": 1},
                    "negative-metadata-address": {**base, "direct_socket_calls": 1},
                    "negative-redirect": {**base, "redirects": 1},
                }
                return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps({"egress_scenarios": scenarios}), stderr="")
            telemetry = {
                "root_uid": 1000, "rootfs_read_only": True, "cap_drop_all": True,
                "no_new_privileges": True, "forbidden_mounts": 0, "forbidden_devices": 0,
                "direct_socket_calls": 0, "direct_dns_calls": 0, "proxy_calls": 0,
                "proxy_destination": "", "connected_addresses": [], "redirects": 0,
                "quota_exceeded": False,
                "memory_controller": True, "pids_controller": True, "cpu_controller": True,
            }
            if "FORGEOPS_PROBE_MODE=quota" in joined:
                telemetry["write_calls"] = 1
            if "FORGEOPS_PROBE_MODE=teardown-canary" in joined:
                telemetry["write_calls"] = 1
                telemetry["pre_cleanup_residue"] = {"processes": 1, "mounts": 1, "leases": 1, "transient_secrets": 1, "workspaces": 1}
                telemetry["cleanup_confirmed"] = True
            return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps(telemetry), stderr="")
        if arguments[:2] == ["docker", "inspect"]:
            if "canary" in arguments[2]:
                return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps({"Mounts": [{"Type": "volume", "Name": "forgeops-e3-1001-1-volume", "Destination": "/workspace"}]}), stderr="")
            return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps({
                "Config": {"User": "1000:1000"},
                "HostConfig": {"ReadonlyRootfs": True, "CapDrop": ["ALL"],
                               "SecurityOpt": ["no-new-privileges"], "PidsLimit": 64,
                               "Memory": 134217728, "NanoCpus": 500000000,
                               "NetworkMode": "none", "Devices": []},
                "Mounts": [],
            }), stderr="")
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")


class FixedE3HelperTests(unittest.TestCase):
    def test_direct_path_cli_bootstraps_project_package_and_fails_closed_for_incomplete_identity(self):
        environment = os.environ.copy()
        for name in tuple(environment):
            if name.startswith("GITHUB_") or name.startswith("FORGEOPS_E3_") or name == "PYTHONPATH":
                environment.pop(name)
        completed = subprocess.run(
            [sys.executable, "tools/sandbox_security/e3_helper.py"],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(2, completed.returncode)
        self.assertNotIn("ModuleNotFoundError", completed.stderr)

    def test_cli_uses_only_protected_github_identity_and_fixed_repository_paths(self):
        from tools.sandbox_security import e3_helper

        environment = {
            "GITHUB_REPOSITORY": "example/forgeops", "GITHUB_REPOSITORY_ID": "123",
            "GITHUB_EVENT_DEFAULT_BRANCH": "main", "GITHUB_REF": "refs/heads/main",
            "GITHUB_REF_PROTECTED": "true", "GITHUB_SHA": "a" * 40,
            "GITHUB_WORKFLOW_SHA": "b" * 40, "GITHUB_RUN_ID": "1001",
            "GITHUB_RUN_ATTEMPT": "1", "FORGEOPS_E3_IMAGE_REF": IMAGE,
            "FORGEOPS_E3_IMAGE_DIGEST": "sha256:" + "c" * 64,
        }
        with tempfile.TemporaryDirectory() as directory:
            project_root = Path(directory)
            expected_output = project_root / "artifacts/runtime/e3-attestation.json"
            with mock.patch.object(e3_helper, "collect_e3_attestation", return_value=0) as collect:
                self.assertEqual(0, e3_helper.run_cli(environment=environment, project_root=project_root))
            identity, schema, suite, output = collect.call_args.args[:4]
            self.assertEqual("example/forgeops", identity.repository)
            self.assertEqual(IMAGE, identity.image_ref)
            self.assertEqual(project_root / "contracts/forgeops-sandbox-contract/1.0/schema.json", schema)
            self.assertEqual(project_root / "fixtures/forgeops-sandbox-security/suite.json", suite)
            self.assertEqual(expected_output, output)

    def test_cli_rejects_unprotected_or_tag_identity_before_runtime_effects(self):
        from tools.sandbox_security import e3_helper

        base = {
            "GITHUB_REPOSITORY": "example/forgeops", "GITHUB_REPOSITORY_ID": "123",
            "GITHUB_EVENT_DEFAULT_BRANCH": "main", "GITHUB_REF": "refs/heads/main",
            "GITHUB_REF_PROTECTED": "true", "GITHUB_SHA": "a" * 40,
            "GITHUB_WORKFLOW_SHA": "b" * 40, "GITHUB_RUN_ID": "1001",
            "GITHUB_RUN_ATTEMPT": "1", "FORGEOPS_E3_IMAGE_REF": IMAGE,
            "FORGEOPS_E3_IMAGE_DIGEST": "sha256:" + "c" * 64,
        }
        for changes in ({"GITHUB_REF_PROTECTED": "false"}, {"FORGEOPS_E3_IMAGE_REF": "ghcr.io/example/forgeops-e3:latest"}, {"GITHUB_REPOSITORY": object()}):
            with self.subTest(changes=changes), mock.patch.object(e3_helper, "collect_e3_attestation") as collect:
                self.assertEqual(2, e3_helper.run_cli(environment={**base, **changes}))
                collect.assert_not_called()

    def test_collector_removes_stale_output_when_preflight_fails(self):
        from tools.sandbox_security.e3_helper import collect_e3_attestation
        from tools.sandbox_security.e3_attestation import ExpectedIdentity

        identity = ExpectedIdentity("example/forgeops", "123", "main", "a" * 40, "b" * 40, "1001", 1, IMAGE, "sha256:" + "c" * 64)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "e3-attestation.json"
            output.write_text('{"stale":true}', encoding="utf-8")
            self.assertEqual(2, collect_e3_attestation(identity, SCHEMA, SUITE, output, runner=lambda *_a, **_k: (_ for _ in ()).throw(OSError())))
            self.assertFalse(output.exists())

    def test_collector_has_no_resource_token_override(self):
        from tools.sandbox_security.e3_helper import collect_e3_attestation
        self.assertNotIn("resource_token", inspect.signature(collect_e3_attestation).parameters)

    def test_lifecycle_runs_network_proxy_and_client_before_containment(self):
        from tools.sandbox_security.e3_helper import collect_e3_attestation
        from tools.sandbox_security.e3_attestation import ExpectedIdentity

        identity = ExpectedIdentity("example/forgeops", "123", "main", "a" * 40, "b" * 40, "1001", 1, IMAGE, "sha256:" + "c" * 64)
        runner = RecordingRunner()
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(0, collect_e3_attestation(identity, SCHEMA, SUITE, Path(directory) / "out.json", runner=runner))
        calls = [" ".join(arguments) for arguments, _kwargs in runner.calls]
        network = next(index for index, call in enumerate(calls) if " network create --internal " in f" {call} ")
        proxy = next(index for index, call in enumerate(calls) if "FORGEOPS_PROBE_MODE=egress-proxy" in call)
        client = next(index for index, call in enumerate(calls) if "FORGEOPS_PROBE_MODE=egress-client" in call)
        containment = next(index for index, call in enumerate(calls) if "FORGEOPS_PROBE_MODE=containment" in call)
        self.assertLess(network, proxy)
        self.assertLess(proxy, client)
        self.assertLess(client, containment)

    def test_mid_lifecycle_failure_still_cleans_attempted_resources_and_checks_residue(self):
        from tools.sandbox_security.e3_helper import collect_e3_attestation
        from tools.sandbox_security.e3_attestation import ExpectedIdentity

        class FailingRunner(RecordingRunner):
            def __call__(self, arguments, **kwargs):
                result = super().__call__(arguments, **kwargs)
                if "FORGEOPS_PROBE_MODE=containment" in " ".join(arguments):
                    return subprocess.CompletedProcess(arguments, 1, stdout="", stderr="")
                return result

        identity = ExpectedIdentity("example/forgeops", "123", "main", "a" * 40, "b" * 40, "1001", 1, IMAGE, "sha256:" + "c" * 64)
        runner = FailingRunner()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.json"
            self.assertEqual(2, collect_e3_attestation(identity, SCHEMA, SUITE, output, runner=runner))
            self.assertFalse(output.exists())
        calls = [" ".join(arguments) for arguments, _kwargs in runner.calls]
        self.assertTrue(any(" rm -f forgeops-e3-1001-1-containment" in f" {call}" for call in calls))
        self.assertTrue(any(" network ls " in f" {call} " for call in calls))
        self.assertTrue(any(" volume ls " in f" {call} " for call in calls))

    def test_canary_requires_exact_named_volume_mount(self):
        from tools.sandbox_security.e3_helper import collect_e3_attestation
        from tools.sandbox_security.e3_attestation import ExpectedIdentity
        class WrongMountRunner(RecordingRunner):
            def __call__(self, arguments, **kwargs):
                result = super().__call__(arguments, **kwargs)
                if arguments[:2] == ["docker", "inspect"] and "canary" in arguments[2]:
                    return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps({"Mounts": []}), stderr="")
                return result
        identity = ExpectedIdentity("example/forgeops", "123", "main", "a" * 40, "b" * 40, "1001", 1, IMAGE, "sha256:" + "c" * 64)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "out.json"
            self.assertEqual(2, collect_e3_attestation(identity, SCHEMA, SUITE, output, runner=WrongMountRunner()))
            self.assertFalse(output.exists())
    def test_probe_emits_only_the_closed_observation_fields_for_an_allowed_mode(self):
        from tools.sandbox_security import e3_probe

        output = io.StringIO()
        with mock.patch.dict("os.environ", {"FORGEOPS_PROBE_MODE": "containment"}, clear=True), mock.patch.object(e3_probe.os, "getuid", return_value=1000, create=True), mock.patch("sys.stdout", output):
            self.assertEqual(0, e3_probe.main())
        self.assertEqual(
            {"root_uid", "rootfs_read_only", "cap_drop_all", "no_new_privileges", "forbidden_mounts", "forbidden_devices", "direct_socket_calls", "direct_dns_calls", "proxy_calls", "proxy_destination", "connected_addresses", "redirects", "quota_exceeded", "write_calls", "memory_controller", "pids_controller", "cpu_controller"},
            set(json.loads(output.getvalue())),
        )

    def test_fixed_command_graph_is_shell_free_bounded_and_has_no_escape_flags(self):
        from tools.sandbox_security.e3_helper import fixed_command_graph

        commands = fixed_command_graph(image_ref=IMAGE, resource_token="1001-1")
        serialized = "\n".join(" ".join(command) for command in commands)

        self.assertNotIn("--privileged", serialized)
        self.assertNotIn("/var/run/docker.sock", serialized)
        self.assertNotIn("--device", serialized)
        self.assertNotIn("--pid=host", serialized)
        self.assertNotIn("--network=host", serialized)
        self.assertGreaterEqual(len(commands), 12)
        self.assertIn("--network-alias forgeops-e3-proxy", serialized)
        self.assertIn("--mount type=volume,source=forgeops-e3-1001-1-volume,target=/workspace", serialized)
        for command in commands:
            self.assertIsInstance(command, tuple)
            self.assertTrue(all(type(part) is str for part in command))
            self.assertEqual("docker", command[0])
            for value in command:
                if value.startswith("forgeops-e3-") and value != "forgeops-e3-proxy":
                    self.assertTrue(value.startswith("forgeops-e3-1001-1-"))

    def test_rejects_unsafe_inputs_before_the_recording_runner_has_effects(self):
        from tools.sandbox_security.e3_helper import E3HelperError, collect_e3_attestation, fixed_command_graph
        from tools.sandbox_security.e3_attestation import ExpectedIdentity

        for image_ref, token in (("ghcr.io/example/forgeops-e3:latest", "1001-1"), (IMAGE, "../../escape")):
            with self.subTest(image_ref=image_ref, token=token):
                with self.assertRaisesRegex(E3HelperError, "E3_HELPER_INPUT_INVALID"):
                    fixed_command_graph(image_ref=image_ref, resource_token=token)

        identity = ExpectedIdentity("example/forgeops", "123", "main", "a" * 40, "b" * 40, "1001", 1, IMAGE, "sha256:" + "c" * 64)
        runner = RecordingRunner()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TypeError):
                collect_e3_attestation(identity, SCHEMA, SUITE, Path(directory) / "e3-attestation.json", runner=runner, resource_token="bad/token")
        self.assertEqual([], runner.calls)

    def test_rejects_an_unregistered_case_id_before_any_runtime_effect(self):
        from tools.sandbox_security.e3_helper import collect_e3_attestation
        from tools.sandbox_security.e3_attestation import ExpectedIdentity

        identity = ExpectedIdentity("example/forgeops", "123", "main", "a" * 40, "b" * 40, "1001", 1, IMAGE, "sha256:" + "c" * 64)
        runner = RecordingRunner()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            suite = json.loads(SUITE.read_text(encoding="utf-8"))
            suite["image_cases"][0]["id"] = "unregistered-case"
            altered_suite = root / "suite.json"
            altered_suite.write_text(json.dumps(suite), encoding="utf-8")
            result = collect_e3_attestation(identity, SCHEMA, altered_suite, root / "e3-attestation.json", runner=runner)
        self.assertEqual(2, result)
        self.assertEqual([], runner.calls)

    def test_collects_a_closed_public_attestation_with_egress_timeout_budget(self):
        from tools.sandbox_security.e3_helper import collect_e3_attestation
        from tools.sandbox_security.e3_attestation import ExpectedIdentity

        identity = ExpectedIdentity("example/forgeops", "123", "main", "a" * 40, "b" * 40, "1001", 1, IMAGE, "sha256:" + "c" * 64)
        runner = RecordingRunner()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "e3-attestation.json"
            result = collect_e3_attestation(identity, SCHEMA, SUITE, output, runner=runner)
            attestation = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(0, result)
        self.assertEqual(23, len(attestation["observations"]))
        self.assertEqual("runtime", attestation["observations"][0]["evidence_kind"])
        self.assertEqual("PREPROVISION_DENIED", attestation["observations"][1]["observation_mode"])
        self.assertEqual((0, 0, 0), tuple(attestation["observations"][1][key] for key in ("provision_calls", "network_calls", "write_calls")))
        teardown = {item["case_id"]: item["residue"] for item in attestation["observations"] if item["case_id"].startswith("negative-") and "residue" in item}
        self.assertEqual({"processes": 1, "mounts": 0, "leases": 0, "transient_secrets": 0, "workspaces": 0}, teardown["negative-process-residue"])
        self.assertEqual({"processes": 0, "mounts": 1, "leases": 0, "transient_secrets": 0, "workspaces": 0}, teardown["negative-mount-residue"])
        self.assertEqual({"processes": 0, "mounts": 0, "leases": 0, "transient_secrets": 0, "workspaces": 0}, attestation["terminal_residue"])
        self.assertTrue(runner.calls)
        for arguments, kwargs in runner.calls:
            self.assertEqual("docker", arguments[0])
            expected_timeout = 15 if "FORGEOPS_PROBE_MODE=egress-client" in arguments else 10
            self.assertEqual(
                {"shell": False, "check": False, "capture_output": True, "text": True, "timeout": expected_timeout},
                kwargs,
            )


if __name__ == "__main__":
    unittest.main()
