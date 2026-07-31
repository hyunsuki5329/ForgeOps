"""Tests for the fixed, recording-runner E3 probe helper."""

from __future__ import annotations

import json
import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "contracts/forgeops-sandbox-contract/1.0/schema.json"
SUITE = ROOT / "fixtures/forgeops-sandbox-security/suite.json"
IMAGE = "ghcr.io/example/forgeops-e3@sha256:" + "c" * 64


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
            return subprocess.CompletedProcess(arguments, 0, stdout=json.dumps({
                "root_uid": 1000, "rootfs_read_only": True, "cap_drop_all": True,
                "no_new_privileges": True, "forbidden_mounts": 0, "forbidden_devices": 0,
                "direct_socket_calls": 0, "direct_dns_calls": 0, "proxy_calls": 0,
                "proxy_destination": "", "connected_addresses": [], "redirects": 0,
                "quota_exceeded": False,
            }), stderr="")
        if arguments[:2] == ["docker", "inspect"]:
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
    def test_probe_emits_only_the_closed_observation_fields_for_an_allowed_mode(self):
        from tools.sandbox_security import e3_probe

        output = io.StringIO()
        with mock.patch.dict("os.environ", {"FORGEOPS_PROBE_MODE": "containment"}, clear=True), mock.patch("sys.stdout", output):
            self.assertEqual(0, e3_probe.main())
        self.assertEqual(
            {"root_uid", "rootfs_read_only", "cap_drop_all", "no_new_privileges", "forbidden_mounts", "forbidden_devices", "direct_socket_calls", "direct_dns_calls", "proxy_calls", "proxy_destination", "connected_addresses", "redirects", "quota_exceeded"},
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
        for command in commands:
            self.assertIsInstance(command, tuple)
            self.assertTrue(all(type(part) is str for part in command))
            self.assertEqual("docker", command[0])
            for value in command:
                if value.startswith("forgeops-e3-"):
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
            result = collect_e3_attestation(identity, SCHEMA, SUITE, Path(directory) / "e3-attestation.json", runner=runner, resource_token="bad/token")
        self.assertEqual(2, result)
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

    def test_collects_a_closed_public_attestation_using_only_the_fixed_graph(self):
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
        self.assertEqual({"processes": 0, "mounts": 0, "leases": 0, "transient_secrets": 0, "workspaces": 0}, attestation["terminal_residue"])
        self.assertTrue(runner.calls)
        for arguments, kwargs in runner.calls:
            self.assertEqual("docker", arguments[0])
            self.assertEqual({"shell": False, "check": False, "capture_output": True, "text": True, "timeout": 10}, kwargs)


if __name__ == "__main__":
    unittest.main()
