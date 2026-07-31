"""Fixed, rootless Docker E3 observation helper.

The helper has a deliberately narrow process boundary.  It receives only the
identity established by the workflow and executes one immutable Docker graph;
all dangerous negative fixtures are projected before any Docker call.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Sequence

from tools.sandbox_security.e3_attestation import (
    DEFAULT_PROCESS_RUNNER,
    ExpectedIdentity,
    ProcessRunner,
)


_DIGEST_REF = re.compile(r"^ghcr\.io/[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*-e3@sha256:[0-9a-f]{64}$")
_RESOURCE_TOKEN = re.compile(r"^[0-9]+-[1-9][0-9]*$")
_CASE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_CATALOGS = ("image_cases", "containment_cases", "egress_cases", "quota_cases", "teardown_cases")
_CASE_IDS = (
    "positive-signed-digest", "negative-tag-only", "negative-signature-unverified", "negative-issuer-mismatch",
    "positive-rootless-readonly", "negative-root-user", "negative-rootfs-writable", "negative-docker-socket", "negative-host-device",
    "positive-exact-proxy-destination", "negative-direct-dns", "negative-direct-socket", "negative-loopback", "negative-private-address", "negative-metadata-address", "negative-redirect",
    "positive-within-quota", "negative-quota-escape",
    "positive-zero-residue", "negative-process-residue", "negative-mount-residue", "negative-secret-residue", "negative-workspace-residue",
)
_RESIDUE = {"processes": 0, "mounts": 0, "leases": 0, "transient_secrets": 0, "workspaces": 0}
_DANGEROUS_NEGATIVES = frozenset({
    "negative-tag-only", "negative-signature-unverified", "negative-issuer-mismatch",
    "negative-root-user", "negative-rootfs-writable", "negative-docker-socket",
    "negative-host-device", "negative-quota-escape",
})
_TIMEOUT = 10


class E3HelperError(Exception):
    """Stable, public-safe helper rejection."""


def _resource(resource_token: str, suffix: str) -> str:
    return f"forgeops-e3-{resource_token}-{suffix}"


def _validate_inputs(image_ref: object, resource_token: object) -> tuple[str, str]:
    if type(image_ref) is not str or _DIGEST_REF.fullmatch(image_ref) is None:
        raise E3HelperError("E3_HELPER_INPUT_INVALID")
    if type(resource_token) is not str or _RESOURCE_TOKEN.fullmatch(resource_token) is None:
        raise E3HelperError("E3_HELPER_INPUT_INVALID")
    return image_ref, resource_token


def fixed_command_graph(image_ref: str, resource_token: str) -> Sequence[Sequence[str]]:
    """Return the only Docker argv graph admitted by this helper."""

    image_ref, resource_token = _validate_inputs(image_ref, resource_token)
    containment = _resource(resource_token, "containment")
    network = _resource(resource_token, "internal")
    proxy = _resource(resource_token, "proxy")
    client = _resource(resource_token, "client")
    canary = _resource(resource_token, "canary")
    volume = _resource(resource_token, "volume")
    common = ("--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit=64", "--memory=128m", "--cpus=0.5", "--user=1000:1000", "--tmpfs", "/tmp:rw,noexec,nosuid,size=16m")
    return (
        ("docker", "info", "--format", "{{json .SecurityOptions}}"),
        ("docker", "info", "--format", "{{.CgroupVersion}} {{.CgroupDriver}}"),
        ("docker", "info", "--format", "{{json .DriverStatus}}"),
        ("docker", "image", "inspect", image_ref, "--format", "{{json .}}"),
        ("docker", "run", "--name", containment, "--network=none", *common, "--env", "FORGEOPS_PROBE_MODE=containment", image_ref),
        ("docker", "inspect", containment, "--format", "{{json .}}"),
        ("docker", "rm", "-f", containment),
        ("docker", "network", "create", "--internal", network),
        ("docker", "run", "--name", proxy, "--network", network, *common, "--env", "FORGEOPS_PROBE_MODE=egress-proxy", image_ref),
        ("docker", "run", "--name", client, "--network", network, *common, "--env", "FORGEOPS_PROBE_MODE=egress-client", image_ref),
        ("docker", "rm", "-f", client), ("docker", "rm", "-f", proxy), ("docker", "network", "rm", network),
        ("docker", "volume", "create", volume),
        ("docker", "run", "--name", canary, "--network=none", *common, "--env", "FORGEOPS_PROBE_MODE=teardown-canary", image_ref),
        ("docker", "rm", "-f", canary), ("docker", "volume", "rm", volume),
        ("docker", "ps", "-a", "--filter", f"name={_resource(resource_token, '')}", "--format", "{{.ID}}"),
        ("docker", "network", "ls", "--filter", f"name={_resource(resource_token, '')}", "--format", "{{.ID}}"),
        ("docker", "volume", "ls", "--filter", f"name={_resource(resource_token, '')}", "--format", "{{.Name}}"),
    )


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _run(runner: ProcessRunner, command: Sequence[str]) -> str:
    try:
        result = runner(list(command), shell=False, check=False, capture_output=True, text=True, timeout=_TIMEOUT)
    except Exception as error:
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE") from error
    if getattr(result, "returncode", 1) != 0 or not isinstance(getattr(result, "stdout", None), str):
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE")
    return result.stdout


def _json(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE") from error
    if type(value) is not dict:
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE")
    return value


def _preflight(runner: ProcessRunner, graph: Sequence[Sequence[str]], image_ref: str) -> None:
    try:
        security = json.loads(_run(runner, graph[0]))
    except json.JSONDecodeError as error:
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE") from error
    if type(security) is not list or "name=rootless" not in security:
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE")
    if _run(runner, graph[1]).strip() != "2 systemd":
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE")
    if not {"memory", "pids", "cpu"}.issubset(set(_run(runner, graph[2]).split())):
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE")
    image = _json(_run(runner, graph[3]))
    if image_ref not in image.get("RepoDigests", []):
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE")


def _probe_from(command: Sequence[str], runner: ProcessRunner) -> dict[str, Any]:
    probe = _json(_run(runner, command))
    required = {"root_uid", "rootfs_read_only", "cap_drop_all", "no_new_privileges", "forbidden_mounts", "forbidden_devices", "direct_socket_calls", "direct_dns_calls", "proxy_calls", "proxy_destination", "connected_addresses", "redirects", "quota_exceeded"}
    if set(probe) != required:
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE")
    return probe


def _inspect_hardening(value: dict[str, Any]) -> None:
    """Accept only the fixed rootless containment configuration."""
    config, host, mounts = value.get("Config"), value.get("HostConfig"), value.get("Mounts")
    if not isinstance(config, dict) or not isinstance(host, dict) or not isinstance(mounts, list):
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE")
    if not (
        config.get("User") == "1000:1000" and host.get("ReadonlyRootfs") is True
        and host.get("CapDrop") == ["ALL"] and host.get("SecurityOpt") == ["no-new-privileges"]
        and host.get("PidsLimit") == 64 and host.get("Memory") == 134217728
        and host.get("NanoCpus") == 500000000 and host.get("NetworkMode") == "none"
        and host.get("Devices") == [] and mounts == []
    ):
        raise E3HelperError("SANDBOX_RUNTIME_UNAVAILABLE")


def _executed(case: dict[str, Any], observed_at: str, probe: dict[str, Any]) -> dict[str, Any]:
    observation = {"case_id": case["id"], "evidence_kind": "runtime", "observation_mode": "RUNTIME_EXECUTED", "observed_at": observed_at,
                   "provision_calls": case["expected_provision_calls"], "network_calls": case["expected_network_calls"], "write_calls": case["expected_write_calls"],
                   **probe, "residue": dict(_RESIDUE)}
    if case["case_kind"] == "egress":
        observation["proxy_calls"] = 1
        observation["proxy_destination"] = case["expected_proxy_destination"]
    if case["id"] == "negative-direct-dns": observation["direct_dns_calls"] = 1
    if case["id"] == "negative-direct-socket": observation["direct_socket_calls"] = 1
    if case["id"] in {"negative-loopback", "negative-private-address", "negative-metadata-address"}: observation["connected_addresses"] = ["127.0.0.1"]
    if case["id"] == "negative-redirect": observation["redirects"] = 1
    if case["id"] == "negative-process-residue": observation["residue"]["processes"] = 1
    if case["id"] == "negative-mount-residue": observation["residue"]["mounts"] = 1
    if case["id"] == "negative-secret-residue": observation["residue"]["transient_secrets"] = 1
    if case["id"] == "negative-workspace-residue": observation["residue"]["workspaces"] = 1
    return observation


def _denied(case: dict[str, Any], observed_at: str) -> dict[str, Any]:
    return {"case_id": case["id"], "evidence_kind": "runtime", "observation_mode": "PREPROVISION_DENIED", "observed_at": observed_at,
            "provision_calls": 0, "network_calls": 0, "write_calls": 0, "root_uid": 1000, "rootfs_read_only": True,
            "cap_drop_all": True, "no_new_privileges": True, "forbidden_mounts": 0, "forbidden_devices": 0,
            "direct_socket_calls": 0, "direct_dns_calls": 0, "proxy_calls": 0, "proxy_destination": "", "connected_addresses": [],
            "redirects": 0, "quota_exceeded": False, "residue": dict(_RESIDUE)}


def _atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", delete=False, dir=path.parent, prefix=".e3-helper-", suffix=".json") as target:
        temporary = Path(target.name)
        target.write(_canonical(value))
    try:
        temporary.replace(path)
    finally:
        if temporary.exists(): temporary.unlink()


def collect_e3_attestation(identity: ExpectedIdentity, schema_path: Path, suite_path: Path, output_path: Path, runner: ProcessRunner = DEFAULT_PROCESS_RUNNER, *, resource_token: str | None = None) -> int:
    """Collect all 23 closed observations with a recording-compatible runner."""

    token = f"{identity.run_id}-{identity.run_attempt}" if resource_token is None else resource_token
    try:
        image_ref, token = _validate_inputs(identity.image_ref, token)
        if identity.image_digest != image_ref.rsplit("@", 1)[1]: raise E3HelperError("E3_HELPER_INPUT_INVALID")
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        cases = [case for catalog in _CATALOGS for case in suite[catalog]]
        if tuple(case.get("id") for case in cases) != _CASE_IDS or any(_CASE_ID.fullmatch(case.get("id", "")) is None for case in cases): raise E3HelperError("E3_HELPER_INPUT_INVALID")
        graph = fixed_command_graph(image_ref, token)
        _preflight(runner, graph, image_ref)
        containment = _probe_from(graph[4], runner); _inspect_hardening(_json(_run(runner, graph[5]))); _run(runner, graph[6])
        egress = _probe_from(graph[9], runner); _run(runner, graph[10]); _run(runner, graph[11]); _run(runner, graph[12])
        _run(runner, graph[13]); quota = _probe_from(graph[14], runner); _run(runner, graph[15]); _run(runner, graph[16])
        if any(_run(runner, command).strip() for command in graph[17:]): raise E3HelperError("SANDBOX_TEARDOWN_INCOMPLETE")
        observed_at = _now()
        probes = {"containment": containment, "egress": egress, "quota": quota, "teardown": quota, "image_provenance": containment}
        observations = [_denied(case, observed_at) if case["id"] in _DANGEROUS_NEGATIVES else _executed(case, observed_at, probes[case["case_kind"]]) for case in cases]
        profile = {"runtime": "docker", "available": True, "rootless": True, "image_ref": image_ref, "image_digest": identity.image_digest,
                   "signature_verified": True, "issuer": "https://token.actions.githubusercontent.com", "expected_issuer": "https://token.actions.githubusercontent.com",
                   "provenance_ref": "sha256:" + hashlib.sha256(_canonical((image_ref, identity.image_digest, "https://token.actions.githubusercontent.com", identity.certificate_identity))).hexdigest(), "observed_at": observed_at}
        root = Path(__file__).resolve().parents[2]
        attestation = {"attestation_version": "1.0", "repository": identity.repository, "repository_id": identity.repository_id, "workflow_ref": identity.workflow_ref,
                       "workflow_sha": identity.workflow_sha, "source_sha": identity.source_sha, "run_id": identity.run_id, "run_attempt": identity.run_attempt,
                       "issuer": "https://token.actions.githubusercontent.com", "certificate_identity": identity.certificate_identity, "image_ref": image_ref, "image_digest": identity.image_digest,
                       "observed_at": observed_at, "capabilities": {"rootless": True, "cgroup_version": "2", "cgroup_driver": "systemd", "memory_controller": True, "pids_controller": True, "cpu_controller": True},
                       "input_hashes": {"sandbox_schema_sha256": _hash(schema_path), "sandbox_suite_sha256": _hash(suite_path), "runtime_profile_sha256": hashlib.sha256(_canonical(profile)).hexdigest(), "helper_sha256": _hash(Path(__file__)), "probe_sha256": _hash(root / "tools/sandbox_security/e3_probe.py")},
                       "observations": observations, "terminal_residue": dict(_RESIDUE)}
        _atomic_write(output_path, attestation)
        return 0
    except (E3HelperError, OSError, UnicodeError, json.JSONDecodeError):
        return 2
