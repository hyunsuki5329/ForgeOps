"""Closed runtime observations and a process-free deterministic test observer."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import weakref
from typing import Callable, Mapping, Protocol

from jsonschema import Draft202012Validator, FormatChecker


class RuntimeUnavailable(Exception):
    """Raised when a requested runtime observation is unavailable."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class RuntimeProfile:
    runtime: str
    available: bool
    rootless: bool
    image_ref: str
    image_digest: str
    signature_verified: bool
    issuer: str
    expected_issuer: str
    provenance_ref: str
    observed_at: str


@dataclass
class Residue:
    processes: int = 0
    mounts: int = 0
    leases: int = 0
    transient_secrets: int = 0
    workspaces: int = 0


@dataclass
class RuntimeObservation:
    case_id: str
    evidence_kind: str
    observed_at: str
    provision_calls: int
    network_calls: int
    write_calls: int
    root_uid: int
    rootfs_read_only: bool
    cap_drop_all: bool
    no_new_privileges: bool
    forbidden_mounts: int
    forbidden_devices: int
    direct_socket_calls: int
    direct_dns_calls: int
    proxy_calls: int
    proxy_destination: str
    connected_addresses: tuple[str, ...]
    redirects: int
    quota_exceeded: bool
    residue: Residue
    observation_mode: str = "RUNTIME_EXECUTED"


class RuntimeObserver(Protocol):
    def observe(self, case: dict) -> RuntimeObservation:
        """Return the closed observation for one registered case."""


class TrustedRuntimeObserver:
    """Marker base for a separately authorized runtime-backed observer.

    The process-free fake deliberately does not inherit this type. A future
    Docker observer must inherit it before its observations can support E3.
    """


@dataclass(frozen=True)
class LocalVerificationProvenance:
    """Closed output from a configured local image verifier."""

    image_ref: str
    signature_verified: bool
    provenance_verified: bool
    issuer: str
    provenance_ref: str


class LocalImageVerifier:
    """Closed local-verifier value; callbacks and mapping adapters are forbidden."""

    __slots__ = ("_provenance",)

    def __init__(self, provenance: LocalVerificationProvenance):
        self._provenance = provenance

    def verify(self, image_ref: str) -> LocalVerificationProvenance:
        return self._provenance


def schema_validator(schema: Mapping[str, object], definition: str) -> Draft202012Validator:
    """Build the shared Draft 2020-12 validator with format enforcement enabled."""

    return Draft202012Validator(
        {"$ref": f"#/$defs/{definition}", "$defs": schema["$defs"]},
        format_checker=FormatChecker(),
    )


class FakeRuntimeObserver:
    """Return only preloaded observations and never invoke a process."""

    def __init__(self, observations: Mapping[str, RuntimeObservation]):
        self._observations = dict(observations)
        self.process_calls = 0

    def observe(self, case: dict) -> RuntimeObservation:
        case_id = case.get("id")
        if case_id not in self._observations:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        return copy.deepcopy(self._observations[case_id])


ALLOWED_PREFIXES = (
    ("docker", "version", "--format", "{{json .Server}}"),
    ("docker", "image", "inspect"),
    ("docker", "run", "--rm"),
    ("docker", "inspect"),
    ("docker", "rm", "-f"),
)
_DIGEST_IMAGE = re.compile(r"^[^@\s]+@sha256:[0-9a-f]{64}$")
_REGISTERED_PROBE_KINDS = frozenset(
    {"image_provenance", "containment", "egress", "quota", "teardown"}
)
LOCAL_TEST_ISSUER = "forgeops-test-issuer"
EXTERNAL_E3_ISSUER = "https://token.actions.githubusercontent.com"
_TRUSTED_ISSUER = LOCAL_TEST_ISSUER
_VERSION_COMMAND = ["docker", "version", "--format", "{{json .Server}}"]
_MIN_TIMEOUT_SECONDS = 1
_MAX_TIMEOUT_SECONDS = 30
_CONTAINER_ID = re.compile(r"^[0-9a-f]{64}$")
_PROVENANCE_REF = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class _ConstructionSeal:
    observer_type: type
    runner: object
    verifier_type: type
    attestation: LocalVerificationProvenance | None
    image_ref: str
    image_digest: str
    provenance_ref: str
    image_inspect_argv: tuple[str, ...]
    probe_argv: tuple[str, ...]
    observe_method: object
    verified_attestation_method: object
    probe_method: object
    image_inspect_method: object
    run_method: object
    allowed_method: object


_CONSTRUCTION_SEALS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


def _image_inspect_argv(image_ref: str) -> tuple[str, ...]:
    return ("docker", "image", "inspect", image_ref, "--format", "{{json .}}")


def _probe_argv(image_ref: str) -> tuple[str, ...]:
    return (
        "docker", "run", "--rm", "--detach", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--pids-limit=64", "--memory=128m",
        "--cpus=0.5", "--network=none", "--user=1000:1000", "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m", image_ref, "/bin/sh", "-c", "sleep 30",
    )


def _closed_attestation(value: object, image_ref: object) -> LocalVerificationProvenance | None:
    """Validate every provenance field by exact type before content checks."""

    if type(value) is not LocalVerificationProvenance or type(image_ref) is not str:
        return None
    if (
        type(value.image_ref) is not str
        or value.image_ref != image_ref
        or type(value.signature_verified) is not bool
        or value.signature_verified is not True
        or type(value.provenance_verified) is not bool
        or value.provenance_verified is not True
        or type(value.issuer) is not str
        or value.issuer != _TRUSTED_ISSUER
        or type(value.provenance_ref) is not str
        or _PROVENANCE_REF.fullmatch(value.provenance_ref) is None
    ):
        return None
    return value


def has_e3_construction(observer: object) -> bool:
    """Return E3 eligibility from the private construction seal, never instance state."""

    try:
        seal = _CONSTRUCTION_SEALS.get(observer)
        instance_values = vars(observer)
    except (TypeError, AttributeError):
        return False
    return (
        type(observer) is VerifiedDockerRuntimeObserver
        and type(seal) is _ConstructionSeal
        and seal.observer_type is VerifiedDockerRuntimeObserver
        and seal.runner is subprocess.run
        and seal.verifier_type is LocalImageVerifier
        and seal.attestation is not None
        and type(observer._image_ref) is str
        and observer._image_ref == seal.image_ref
        and seal.image_digest == seal.image_ref.rsplit("@", 1)[1]
        and seal.provenance_ref == seal.attestation.provenance_ref
        and seal.image_inspect_argv == _image_inspect_argv(seal.image_ref)
        and seal.probe_argv == _probe_argv(seal.image_ref)
        and seal.observe_method is VerifiedDockerRuntimeObserver.observe
        and VerifiedDockerRuntimeObserver.observe is seal.observe_method
        and seal.verified_attestation_method is VerifiedDockerRuntimeObserver._verified_attestation
        and seal.probe_method is DockerRuntimeObserver._probe_command
        and seal.image_inspect_method is DockerRuntimeObserver._image_inspect_command
        and seal.run_method is DockerRuntimeObserver._run
        and seal.allowed_method is DockerRuntimeObserver._is_allowed
        and "observe" not in instance_values
        and "_run" not in instance_values
        and "_verified_attestation" not in instance_values
        and "_probe_command" not in instance_values
        and "_image_inspect_command" not in instance_values
        and "_is_allowed" not in instance_values
    )


class DockerRuntimeObserver:
    """A narrow, injectable Docker boundary that is never an E3 trust anchor."""

    def __init__(
        self,
        executable: str,
        image_ref: str,
        timeout_seconds: int = 30,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ):
        self._executable = executable
        self._image_ref = image_ref
        self._timeout_seconds = timeout_seconds
        self._runner = runner if runner is not None else subprocess.run
        self._injected_runner = runner is not None
        self._tracked_container_id: str | None = None
        self.residual_uncertainty = False

    @property
    def runtime_evidence_trusted(self) -> bool:
        """The injectable base observer is never an E3 trust anchor."""

        return False

    @staticmethod
    def _observed_at() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _unavailable_profile(self) -> dict:
        return {
            "runtime": "docker",
            "available": False,
            "rootless": False,
            "image_ref": "unavailable",
            "image_digest": "unavailable",
            "signature_verified": False,
            "issuer": "unavailable",
            "expected_issuer": _TRUSTED_ISSUER,
            "provenance_ref": "unavailable",
            "observed_at": self._observed_at(),
        }

    def _image_inspect_command(self) -> list[str]:
        return list(_image_inspect_argv(self._image_ref))

    def _probe_command(self) -> list[str]:
        return list(_probe_argv(self._image_ref))

    def _inspect_command(self, container_id: str) -> list[str]:
        return [self._executable, "inspect", container_id, "--format", "{{json .}}"]

    def _remove_command(self, container_id: str) -> list[str]:
        return [self._executable, "rm", "-f", container_id]

    def _is_allowed(self, arguments: list[str]) -> bool:
        if not isinstance(arguments, list) or not all(isinstance(value, str) for value in arguments):
            return False
        if type(self) is VerifiedDockerRuntimeObserver:
            if not has_e3_construction(self):
                return False
            seal = _CONSTRUCTION_SEALS[self]
            if arguments == _VERSION_COMMAND:
                return True
            if tuple(arguments) == seal.image_inspect_argv or tuple(arguments) == seal.probe_argv:
                return True
            if self._tracked_container_id is not None and arguments == [
                "docker", "inspect", self._tracked_container_id, "--format", "{{json .}}"
            ]:
                return True
            return self._tracked_container_id is not None and arguments == ["docker", "rm", "-f", self._tracked_container_id]
        if arguments == _VERSION_COMMAND:
            return True
        if arguments == self._image_inspect_command():
            return True
        if arguments == self._probe_command():
            return True
        if (
            self._tracked_container_id is not None
            and arguments == self._inspect_command(self._tracked_container_id)
        ):
            return True
        if self._tracked_container_id is not None and arguments == self._remove_command(self._tracked_container_id):
            return True
        return False

    def _run(self, arguments: list[str]) -> subprocess.CompletedProcess[str]:
        """Run one exact, bounded allowlisted command without a shell."""

        if (
            isinstance(self._timeout_seconds, bool)
            or not isinstance(self._timeout_seconds, int)
            or not _MIN_TIMEOUT_SECONDS <= self._timeout_seconds <= _MAX_TIMEOUT_SECONDS
            or not self._is_allowed(arguments)
        ):
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        runner = self._runner
        if type(self) is VerifiedDockerRuntimeObserver:
            if not has_e3_construction(self):
                raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
            runner = _CONSTRUCTION_SEALS[self].runner
        try:
            return runner(
                arguments,
                shell=False,
                capture_output=True,
                text=True,
                check=False,
                timeout=self._timeout_seconds,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE") from error

    @staticmethod
    def _json_object(result: object) -> dict | None:
        if not isinstance(result, subprocess.CompletedProcess) or result.returncode != 0 or not isinstance(result.stdout, str):
            return None
        try:
            value = json.loads(result.stdout)
        except (TypeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _is_rootless(server: Mapping[str, object]) -> bool:
        options = server.get("SecurityOptions")
        return isinstance(options, list) and "name=rootless" in options

    def _verified_attestation(self) -> LocalVerificationProvenance | None:
        """The injectable base observer never has independent provenance."""

        return None

    def inspect_capability(self) -> dict:
        """Return a closed, public-safe capability profile without raw output."""

        try:
            if (
                self._executable != "docker"
                or isinstance(self._timeout_seconds, bool)
                or not isinstance(self._timeout_seconds, int)
                or not _MIN_TIMEOUT_SECONDS <= self._timeout_seconds <= _MAX_TIMEOUT_SECONDS
                or type(self._image_ref) is not str
                or _DIGEST_IMAGE.fullmatch(self._image_ref) is None
            ):
                return self._unavailable_profile()
            image_command = self._image_inspect_command()
            if type(self) is VerifiedDockerRuntimeObserver:
                if not has_e3_construction(self):
                    return self._unavailable_profile()
                image_command = list(_CONSTRUCTION_SEALS[self].image_inspect_argv)
            server = self._json_object(self._run(_VERSION_COMMAND))
            image = self._json_object(self._run(image_command))
        except Exception:
            return self._unavailable_profile()
        if server is None or image is None:
            return self._unavailable_profile()

        repo_digests = image.get("RepoDigests")
        image_is_exact = isinstance(repo_digests, list) and self._image_ref in repo_digests
        attestation = self._verified_attestation()
        rootless = self._is_rootless(server)
        available = image_is_exact and rootless and attestation is not None
        digest = self._image_ref.rsplit("@", 1)[1]
        return {
            "runtime": "docker",
            "available": available,
            "rootless": rootless,
            "image_ref": self._image_ref if available else "unavailable",
            "image_digest": digest if available else "unavailable",
            "signature_verified": available,
            "issuer": attestation.issuer if available else "unavailable",
            "expected_issuer": _TRUSTED_ISSUER,
            "provenance_ref": attestation.provenance_ref if available else "unavailable",
            "observed_at": self._observed_at(),
        }

    @staticmethod
    def _container_id(result: object) -> str | None:
        if not isinstance(result, subprocess.CompletedProcess) or result.returncode != 0:
            return None
        value = result.stdout.strip() if isinstance(result.stdout, str) else ""
        return value if _CONTAINER_ID.fullmatch(value) is not None else None

    @staticmethod
    def _inspection_confirms_hardening(inspect: Mapping[str, object]) -> bool:
        """Accept only directly parsed Docker inspect facts; unknown is not safe."""

        config = inspect.get("Config")
        host = inspect.get("HostConfig")
        mounts = inspect.get("Mounts")
        if not isinstance(config, Mapping) or not isinstance(host, Mapping) or not isinstance(mounts, list):
            return False
        security_options = host.get("SecurityOpt")
        cap_drop = host.get("CapDrop")
        devices = host.get("Devices")
        return (
            config.get("User") == "1000:1000"
            and host.get("ReadonlyRootfs") is True
            and isinstance(cap_drop, list)
            and cap_drop == ["ALL"]
            and isinstance(security_options, list)
            and security_options == ["no-new-privileges"]
            and host.get("PidsLimit") == 64
            and host.get("Memory") == 134217728
            and host.get("NanoCpus") == 500000000
            and host.get("NetworkMode") == "none"
            and devices == []
            and mounts == []
        )

    def _cleanup_confirmed(self, container_id: str) -> bool:
        removed = self._run(self._remove_command(container_id))
        if not isinstance(removed, subprocess.CompletedProcess) or removed.returncode != 0:
            return False
        post_remove = self._run(self._inspect_command(container_id))
        return (
            isinstance(post_remove, subprocess.CompletedProcess)
            and post_remove.returncode != 0
            and isinstance(post_remove.stderr, str)
            and "No such object" in post_remove.stderr
        )

    def observe(self, case: dict) -> dict:
        """Attempt a fixed lifecycle but never fill unobserved fields with claims.

        Docker inspect proves a limited configuration subset. It cannot, by
        itself, prove every evaluator field (for example direct DNS/socket
        attempts, quota consumption, or host-wide residual secrets). Therefore
        even a fully parsed lifecycle is reported unavailable until a later
        registered probe supplies the missing closed observations.
        """

        if not isinstance(case, dict) or case.get("case_kind") not in _REGISTERED_PROBE_KINDS:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        if not isinstance(case.get("id"), str) or not case["id"]:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        if not self.inspect_capability()["available"]:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")

        probe_command = self._probe_command()
        if type(self) is VerifiedDockerRuntimeObserver:
            if not has_e3_construction(self):
                raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
            probe_command = list(_CONSTRUCTION_SEALS[self].probe_argv)
        try:
            started = self._run(probe_command)
        except RuntimeUnavailable as error:
            self.residual_uncertainty = True
            raise RuntimeUnavailable("SANDBOX_TEARDOWN_INCOMPLETE") from error
        container_id = self._container_id(started)
        if container_id is None:
            self.residual_uncertainty = True
            raise RuntimeUnavailable("SANDBOX_TEARDOWN_INCOMPLETE")
        self._tracked_container_id = container_id
        try:
            inspected = self._json_object(self._run(self._inspect_command(container_id)))
            if inspected is None or not self._inspection_confirms_hardening(inspected):
                raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        finally:
            try:
                cleaned = self._cleanup_confirmed(container_id)
            except RuntimeUnavailable:
                cleaned = False
            self._tracked_container_id = None
        if not cleaned:
            self.residual_uncertainty = True
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")


class VerifiedDockerRuntimeObserver(DockerRuntimeObserver, TrustedRuntimeObserver):
    """Exact E3 candidate whose implementation is installed from a closed graph below."""


def _install_verified_e3_boundary() -> tuple[Callable[[object], bool], Callable[[object, dict], dict]]:
    """Create the E3 boundary once and retain every trusted value in closures.

    The verified path never resolves a builder, helper, runner, verifier method,
    or lifecycle method through mutable module/class/instance state. Public
    methods are wrappers installed from this graph and eligibility additionally
    rejects any later mutation of the snapshotted module and class surfaces.
    """

    observer_type = VerifiedDockerRuntimeObserver
    base_type = DockerRuntimeObserver
    verifier_type = LocalImageVerifier
    provenance_type = LocalVerificationProvenance
    runtime_unavailable_type = RuntimeUnavailable
    original_run = subprocess.run
    completed_process_type = subprocess.CompletedProcess
    subprocess_error_type = subprocess.SubprocessError
    timeout_error_type = subprocess.TimeoutExpired
    json_loads = json.loads
    utc_now = datetime.now
    utc_zone = timezone.utc
    exact_image_ref = "registry.example/forgeops@sha256:" + "a" * 64
    exact_digest = "sha256:" + "a" * 64
    exact_issuer = "forgeops-test-issuer"
    min_timeout_seconds = 1
    max_timeout_seconds = 30
    exact_version_argv = ("docker", "version", "--format", "{{json .Server}}")
    exact_image_inspect_argv = (
        "docker", "image", "inspect", exact_image_ref, "--format", "{{json .}}",
    )
    exact_probe_argv = (
        "docker", "run", "--rm", "--detach", "--read-only", "--cap-drop=ALL",
        "--security-opt=no-new-privileges", "--pids-limit=64", "--memory=128m",
        "--cpus=0.5", "--network=none", "--user=1000:1000", "--tmpfs",
        "/tmp:rw,noexec,nosuid,size=16m", exact_image_ref, "/bin/sh", "-c", "sleep 30",
    )
    exact_probe_kinds = frozenset(
        {"image_provenance", "containment", "egress", "quota", "teardown"}
    )
    container_id_fullmatch = re.compile(r"^[0-9a-f]{64}$").fullmatch
    provenance_fullmatch = re.compile(r"^sha256:[0-9a-f]{64}$").fullmatch
    verifier_verify = verifier_type.verify
    seals: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
    residual_state: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()

    module_snapshot = {
        "ALLOWED_PREFIXES": ALLOWED_PREFIXES,
        "_DIGEST_IMAGE": _DIGEST_IMAGE,
        "_REGISTERED_PROBE_KINDS": _REGISTERED_PROBE_KINDS,
        "_TRUSTED_ISSUER": _TRUSTED_ISSUER,
        "_VERSION_COMMAND": _VERSION_COMMAND,
        "_CONTAINER_ID": _CONTAINER_ID,
        "_PROVENANCE_REF": _PROVENANCE_REF,
        "_image_inspect_argv": _image_inspect_argv,
        "_probe_argv": _probe_argv,
        "_closed_attestation": _closed_attestation,
        "DockerRuntimeObserver": base_type,
        "VerifiedDockerRuntimeObserver": observer_type,
        "LocalImageVerifier": verifier_type,
        "LocalVerificationProvenance": provenance_type,
        "RuntimeUnavailable": runtime_unavailable_type,
    }

    def module_graph_intact() -> bool:
        try:
            current = globals()
            return (
                subprocess.run is original_run
                and tuple(_VERSION_COMMAND) == exact_version_argv
                and ALLOWED_PREFIXES == (
                    ("docker", "version", "--format", "{{json .Server}}"),
                    ("docker", "image", "inspect"),
                    ("docker", "run", "--rm"),
                    ("docker", "inspect"),
                    ("docker", "rm", "-f"),
                )
                and all(current.get(name) is value for name, value in module_snapshot.items())
            )
        except Exception:
            return False

    def safe_profile() -> dict:
        return {
            "runtime": "docker",
            "available": False,
            "rootless": False,
            "image_ref": "unavailable",
            "image_digest": "unavailable",
            "signature_verified": False,
            "issuer": "unavailable",
            "expected_issuer": exact_issuer,
            "provenance_ref": "unavailable",
            "observed_at": utc_now(utc_zone).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def exact_class_surface(cls: type, snapshot: dict[str, object]) -> bool:
        current = vars(cls)
        return current.keys() == snapshot.keys() and all(
            current[name] is value for name, value in snapshot.items()
        )

    def attestation_fields(value: object, image_ref: object) -> tuple[str, str] | None:
        if type(value) is not provenance_type or image_ref != exact_image_ref:
            return None
        try:
            valid = (
                type(value.image_ref) is str
                and value.image_ref == exact_image_ref
                and type(value.signature_verified) is bool
                and value.signature_verified is True
                and type(value.provenance_verified) is bool
                and value.provenance_verified is True
                and type(value.issuer) is str
                and value.issuer == exact_issuer
                and type(value.provenance_ref) is str
                and provenance_fullmatch(value.provenance_ref) is not None
            )
        except Exception:
            return None
        return (value.issuer, value.provenance_ref) if valid else None

    def trusted_init(
        self: object,
        executable: str,
        image_ref: str,
        verifier: LocalImageVerifier,
        timeout_seconds: int = 30,
    ) -> None:
        self._executable = executable
        self._image_ref = image_ref
        self._timeout_seconds = timeout_seconds
        self._runner = original_run
        self._injected_runner = False
        self._tracked_container_id = None
        residual_state[self] = False
        if (
            not module_graph_intact()
            or type(self) is not observer_type
            or executable != "docker"
            or image_ref != exact_image_ref
            or isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, int)
            or not min_timeout_seconds <= timeout_seconds <= max_timeout_seconds
            or type(verifier) is not verifier_type
        ):
            return
        try:
            provenance = verifier_verify(verifier, exact_image_ref)
        except Exception:
            return
        fields = attestation_fields(provenance, image_ref)
        if fields is None:
            return
        seals[self] = (verifier, provenance, fields[0], fields[1], timeout_seconds)

    def runtime_evidence_trusted(self: object) -> bool:
        return gate(self)

    def residual_uncertainty(self: object) -> bool:
        return residual_state.get(self, True)

    def verified_attestation(self: object) -> LocalVerificationProvenance | None:
        if not gate(self):
            return None
        seal = seals[self]
        return provenance_type(
            image_ref=exact_image_ref,
            signature_verified=True,
            provenance_verified=True,
            issuer=seal[2],
            provenance_ref=seal[3],
        )

    def run_exact(self: object, argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        if not gate(self) or argv not in (exact_version_argv, exact_image_inspect_argv, exact_probe_argv):
            raise runtime_unavailable_type("SANDBOX_RUNTIME_UNAVAILABLE")
        try:
            return original_run(
                list(argv),
                shell=False,
                capture_output=True,
                text=True,
                check=False,
                timeout=seals[self][4],
            )
        except (OSError, subprocess_error_type) as error:
            raise runtime_unavailable_type("SANDBOX_RUNTIME_UNAVAILABLE") from error

    def json_object(result: object) -> dict | None:
        if type(result) is not completed_process_type or result.returncode != 0 or type(result.stdout) is not str:
            return None
        try:
            value = json_loads(result.stdout)
        except Exception:
            return None
        return value if type(value) is dict else None

    def inspect_capability(self: object) -> dict:
        if not gate(self):
            return safe_profile()
        try:
            server = json_object(run_exact(self, exact_version_argv))
            image = json_object(run_exact(self, exact_image_inspect_argv))
        except Exception:
            return safe_profile()
        if server is None or image is None:
            return safe_profile()
        options = server.get("SecurityOptions")
        repo_digests = image.get("RepoDigests")
        rootless = type(options) is list and "name=rootless" in options
        image_is_exact = type(repo_digests) is list and exact_image_ref in repo_digests
        if not rootless or not image_is_exact:
            return safe_profile()
        seal = seals[self]
        return {
            "runtime": "docker",
            "available": True,
            "rootless": True,
            "image_ref": exact_image_ref,
            "image_digest": exact_digest,
            "signature_verified": True,
            "issuer": seal[2],
            "expected_issuer": exact_issuer,
            "provenance_ref": seal[3],
            "observed_at": utc_now(utc_zone).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def hardening_confirmed(value: object) -> bool:
        if type(value) is not dict:
            return False
        config = value.get("Config")
        host = value.get("HostConfig")
        mounts = value.get("Mounts")
        if type(config) is not dict or type(host) is not dict or type(mounts) is not list:
            return False
        return (
            config.get("User") == "1000:1000"
            and host.get("ReadonlyRootfs") is True
            and host.get("CapDrop") == ["ALL"]
            and host.get("SecurityOpt") == ["no-new-privileges"]
            and host.get("PidsLimit") == 64
            and host.get("Memory") == 134217728
            and host.get("NanoCpus") == 500000000
            and host.get("NetworkMode") == "none"
            and host.get("Devices") == []
            and mounts == []
        )

    def lifecycle_run(self: object, argv: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
        if not gate(self):
            raise runtime_unavailable_type("SANDBOX_RUNTIME_UNAVAILABLE")
        try:
            return original_run(
                list(argv), shell=False, capture_output=True, text=True, check=False,
                timeout=seals[self][4],
            )
        except timeout_error_type as error:
            raise error
        except (OSError, subprocess_error_type) as error:
            raise runtime_unavailable_type("SANDBOX_RUNTIME_UNAVAILABLE") from error

    def cleanup(self: object, container_id: str) -> bool:
        remove = lifecycle_run(self, ("docker", "rm", "-f", container_id))
        if type(remove) is not completed_process_type or remove.returncode != 0:
            return False
        post = lifecycle_run(
            self, ("docker", "inspect", container_id, "--format", "{{json .}}")
        )
        return (
            type(post) is completed_process_type
            and post.returncode != 0
            and type(post.stderr) is str
            and "No such object" in post.stderr
        )

    def trusted_observe(self: object, case: dict) -> dict:
        if (
            not gate(self)
            or type(case) is not dict
            or case.get("case_kind") not in exact_probe_kinds
            or type(case.get("id")) is not str
            or not case["id"]
        ):
            raise runtime_unavailable_type("SANDBOX_RUNTIME_UNAVAILABLE")
        if not inspect_capability(self)["available"]:
            raise runtime_unavailable_type("SANDBOX_RUNTIME_UNAVAILABLE")
        try:
            started = lifecycle_run(self, exact_probe_argv)
        except timeout_error_type as error:
            residual_state[self] = True
            raise runtime_unavailable_type("SANDBOX_TEARDOWN_INCOMPLETE") from error
        except runtime_unavailable_type as error:
            residual_state[self] = True
            raise runtime_unavailable_type("SANDBOX_TEARDOWN_INCOMPLETE") from error
        container_id = ""
        if type(started) is completed_process_type and started.returncode == 0 and type(started.stdout) is str:
            candidate = started.stdout.strip()
            if container_id_fullmatch(candidate) is not None:
                container_id = candidate
        if not container_id:
            residual_state[self] = True
            raise runtime_unavailable_type("SANDBOX_TEARDOWN_INCOMPLETE")
        try:
            inspected = json_object(
                lifecycle_run(
                    self, ("docker", "inspect", container_id, "--format", "{{json .}}")
                )
            )
            if not hardening_confirmed(inspected):
                raise runtime_unavailable_type("SANDBOX_RUNTIME_UNAVAILABLE")
        finally:
            try:
                cleaned = cleanup(self, container_id)
            except Exception:
                cleaned = False
        if not cleaned:
            residual_state[self] = True
            raise runtime_unavailable_type("SANDBOX_TEARDOWN_INCOMPLETE")
        raise runtime_unavailable_type("SANDBOX_RUNTIME_UNAVAILABLE")

    observer_type.__init__ = trusted_init
    observer_type.runtime_evidence_trusted = property(runtime_evidence_trusted)
    observer_type.residual_uncertainty = property(residual_uncertainty)
    observer_type._verified_attestation = verified_attestation
    observer_type.inspect_capability = inspect_capability
    observer_type.observe = trusted_observe

    class_snapshots = {
        base_type: dict(vars(base_type)),
        observer_type: dict(vars(observer_type)),
        verifier_type: dict(vars(verifier_type)),
        provenance_type: dict(vars(provenance_type)),
    }

    def gate(observer: object) -> bool:
        if not module_graph_intact() or type(observer) is not observer_type:
            return False
        if not all(exact_class_surface(cls, snapshot) for cls, snapshot in class_snapshots.items()):
            return False
        try:
            seal = seals.get(observer)
            values = vars(observer)
        except Exception:
            return False
        if type(seal) is not tuple or len(seal) != 5:
            return False
        verifier, provenance, issuer, provenance_ref, timeout_seconds = seal
        if set(values) != {
            "_executable", "_image_ref", "_timeout_seconds", "_runner",
            "_injected_runner", "_tracked_container_id",
        }:
            return False
        try:
            current_provenance = verifier_verify(verifier, exact_image_ref)
        except Exception:
            return False
        return (
            values["_executable"] == "docker"
            and values["_image_ref"] == exact_image_ref
            and values["_timeout_seconds"] == timeout_seconds
            and values["_runner"] is original_run
            and values["_injected_runner"] is False
            and values["_tracked_container_id"] is None
            and type(verifier) is verifier_type
            and current_provenance is provenance
            and attestation_fields(provenance, exact_image_ref) == (issuer, provenance_ref)
        )

    return gate, trusted_observe


has_e3_construction, observe_e3 = _install_verified_e3_boundary()


_ATTESTED_SEALS: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_ATTESTED_TIMESTAMP = "%Y-%m-%dT%H:%M:%SZ"
_ATTESTED_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_ATTESTED_HEX = re.compile(r"^[0-9a-f]{64}$")
_ATTESTED_CATALOGS = ("image_cases", "containment_cases", "egress_cases", "quota_cases", "teardown_cases")


def _attested_hash(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _attested_time(value: object) -> datetime:
    if type(value) is not str:
        raise ValueError
    return datetime.strptime(value, _ATTESTED_TIMESTAMP).replace(tzinfo=timezone.utc)


def _attested_case_ids() -> tuple[str, ...]:
    try:
        suite = json.loads(
            (Path(__file__).resolve().parents[2] / "fixtures/forgeops-sandbox-security/suite.json").read_text(encoding="utf-8")
        )
        return tuple(case["id"] for catalog in _ATTESTED_CATALOGS for case in suite[catalog])
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE") from error


class AttestedRuntimeObserver(TrustedRuntimeObserver):
    """Read only fresh, importer-sealed E3 observations from fixed public files."""

    @classmethod
    def from_imported_files(
        cls,
        profile_path: Path,
        observations_path: Path,
        receipt_path: Path,
        validation_at: str,
    ) -> "AttestedRuntimeObserver":
        try:
            profile_bytes = Path(profile_path).read_bytes()
            observations_bytes = Path(observations_path).read_bytes()
            receipt_bytes = Path(receipt_path).read_bytes()
            profile = json.loads(profile_bytes.decode("utf-8"))
            observation_document = json.loads(observations_bytes.decode("utf-8"))
            receipt = json.loads(receipt_bytes.decode("utf-8"))
        except (OSError, TypeError, UnicodeError, json.JSONDecodeError) as error:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE") from error
        if type(cls) is not type or cls is not AttestedRuntimeObserver:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        if not _validate_attested_import(profile, observation_document, receipt, profile_bytes, observations_bytes, validation_at):
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        observer = cls()
        observer._profile = copy.deepcopy(profile)
        observer._observations = {item["case_id"]: copy.deepcopy(item) for item in observation_document["observations"]}
        observer._validation_at = validation_at
        _ATTESTED_SEALS[observer] = (
            _canonical_attested(observer._profile),
            _canonical_attested(observer._observations),
            validation_at,
        )
        return observer

    def observe(self, case: dict) -> dict:
        if not has_attested_e3_construction(self) or type(case) is not dict or type(case.get("id")) is not str:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        try:
            return copy.deepcopy(self._observations[case["id"]])
        except KeyError as error:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE") from error

    def runtime_profile(self) -> dict:
        if not has_attested_e3_construction(self):
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        return copy.deepcopy(self._profile)


def _canonical_attested(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("utf-8")


def _validate_attested_import(
    profile: object,
    observation_document: object,
    receipt: object,
    profile_bytes: bytes,
    observations_bytes: bytes,
    validation_at: str,
) -> bool:
    """Validate every imported public field before any observer exists."""
    try:
        if type(profile) is not dict or type(observation_document) is not dict or type(receipt) is not dict:
            return False
        profile_keys = {
            "runtime", "available", "rootless", "image_ref", "image_digest", "signature_verified",
            "issuer", "expected_issuer", "provenance_ref", "observed_at",
        }
        if set(profile) != profile_keys or set(observation_document) != {"observations_version", "observed_at", "observations", "terminal_residue"}:
            return False
        if receipt.get("verification_kind") != "runtime" or receipt.get("issuer") != EXTERNAL_E3_ISSUER:
            return False
        if receipt.get("runtime_profile_sha256") != _attested_hash(profile_bytes):
            return False
        if receipt.get("runtime_observations_sha256") != _attested_hash(observations_bytes):
            return False
        if not all(type(receipt.get(key)) is str and _ATTESTED_HEX.fullmatch(receipt[key]) for key in ("runtime_profile_sha256", "runtime_observations_sha256")):
            return False
        if (
            profile["runtime"] != "docker" or profile["available"] is not True or profile["rootless"] is not True
            or profile["signature_verified"] is not True or profile["issuer"] != EXTERNAL_E3_ISSUER
            or profile["expected_issuer"] != EXTERNAL_E3_ISSUER or type(profile["image_ref"]) is not str
            or type(profile["image_digest"]) is not str or _ATTESTED_DIGEST.fullmatch(profile["image_digest"]) is None
            or profile["image_ref"].rsplit("@", 1)[-1] != profile["image_digest"]
            or receipt.get("image_ref") != profile["image_ref"] or receipt.get("image_digest") != profile["image_digest"]
        ):
            return False
        expected_ids = _attested_case_ids()
        observations = observation_document["observations"]
        terminal_residue = observation_document["terminal_residue"]
        if (
            type(terminal_residue) is not dict
            or set(terminal_residue) != {"processes", "mounts", "leases", "transient_secrets", "workspaces"}
            or any(type(value) is not int or value != 0 for value in terminal_residue.values())
        ):
            return False
        if type(observations) is not list or len(observations) != 23:
            return False
        if tuple(item.get("case_id") if type(item) is dict else None for item in observations) != expected_ids:
            return False
        if len({item["case_id"] for item in observations}) != 23:
            return False
        trusted_at = _attested_time(validation_at)
        timestamps = (profile["observed_at"], observation_document["observed_at"], receipt.get("observed_at"), *(item.get("observed_at") for item in observations if type(item) is dict))
        for timestamp in timestamps:
            age = (trusted_at - _attested_time(timestamp)).total_seconds()
            if not 0 <= age <= 300:
                return False
        for observation in observations:
            if type(observation) is not dict or observation.get("evidence_kind") != "runtime":
                return False
            if set(observation.get("residue", {})) != {"processes", "mounts", "leases", "transient_secrets", "workspaces"}:
                return False
            if any(type(value) is not int or value < 0 for value in observation["residue"].values()):
                return False
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
    return True


_ATTESTED_CLASS_SNAPSHOT = dict(vars(AttestedRuntimeObserver))


def has_attested_e3_construction(observer: object) -> bool:
    """Verify the immutable imported-E3 construction and mutation-free surface."""
    try:
        seal = _ATTESTED_SEALS.get(observer)
        values = vars(observer)
        return (
            type(observer) is AttestedRuntimeObserver
            and dict(vars(AttestedRuntimeObserver)) == _ATTESTED_CLASS_SNAPSHOT
            and set(values) == {"_profile", "_observations", "_validation_at"}
            and type(seal) is tuple and len(seal) == 3
            and _canonical_attested(values["_profile"]) == seal[0]
            and _canonical_attested(values["_observations"]) == seal[1]
            and values["_validation_at"] == seal[2]
        )
    except (AttributeError, TypeError, ValueError):
        return False


def _install_attested_e3_boundary():
    """Install an imported-E3 boundary whose authority state never escapes closures."""
    from tools.sandbox_security import e3_attestation

    observer_type = type("AttestedRuntimeObserver", (TrustedRuntimeObserver,), {})
    original_run = subprocess.run
    verify_signed = e3_attestation.verify_signed_attestation
    expected_identity_type = e3_attestation.ExpectedIdentity
    public_profile = e3_attestation._public_profile
    canonical = e3_attestation._canonical_bytes
    environment_get = os.environ.get
    utc = timezone.utc
    issuer = "https://token.actions.githubusercontent.com"
    receipt_keys = frozenset({
        "receipt_version", "attestation_sha256", "bundle_sha256", "repository", "repository_id",
        "default_branch", "workflow_ref", "source_sha", "workflow_sha", "run_id", "run_attempt",
        "image_ref", "image_digest", "issuer", "certificate_identity", "observed_at",
        "verification_kind", "runtime_profile_sha256", "runtime_observations_sha256",
    })
    residue_keys = frozenset({"processes", "mounts", "leases", "transient_secrets", "workspaces"})
    required_context = (
        "GITHUB_REPOSITORY", "GITHUB_REPOSITORY_ID", "GITHUB_REF", "GITHUB_SHA",
        "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_WORKFLOW_SHA",
    )
    seals: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
    schema_path = Path(__file__).resolve().parents[2] / "contracts/forgeops-sandbox-contract/1.0/schema.json"
    try:
        sandbox_schema = json.loads(schema_path.read_text(encoding="utf-8"))
        profile_validator = schema_validator(sandbox_schema, "RuntimeProfile")
        observation_validator = schema_validator(sandbox_schema, "RuntimeObservation")
        suite = json.loads((Path(__file__).resolve().parents[2] / "fixtures/forgeops-sandbox-security/suite.json").read_text(encoding="utf-8"))
        case_ids = tuple(case["id"] for catalog in _ATTESTED_CATALOGS for case in suite[catalog])
    except Exception:
        case_ids = ()
        profile_validator = observation_validator = None

    def load_snapshot(path: Path) -> tuple[bytes, dict] | None:
        try:
            raw = Path(path).read_bytes()
            value = json.loads(raw.decode("utf-8"))
            return (raw, value) if type(value) is dict else None
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            return None

    def valid_documents(profile: dict, observations: dict, receipt: dict, profile_bytes: bytes, observations_bytes: bytes, validation_at: str) -> bool:
        try:
            if (
                profile_validator is None
                or set(observations) != {"observations_version", "observed_at", "observations", "terminal_residue"}
                or set(receipt) != receipt_keys
                or receipt["receipt_version"] != "1.0"
            ):
                return False
            profile_validator.validate(profile)
            if receipt["runtime_profile_sha256"] != hashlib.sha256(profile_bytes).hexdigest() or receipt["runtime_observations_sha256"] != hashlib.sha256(observations_bytes).hexdigest():
                return False
            if type(observations["observations"]) is not list or tuple(item.get("case_id") if type(item) is dict else None for item in observations["observations"]) != case_ids:
                return False
            residue = observations["terminal_residue"]
            if type(residue) is not dict or set(residue) != residue_keys or any(type(value) is not int or value != 0 for value in residue.values()):
                return False
            now = datetime.strptime(validation_at, _ATTESTED_TIMESTAMP).replace(tzinfo=utc)
            observed_at = profile["observed_at"]
            if observations["observed_at"] != observed_at or receipt["observed_at"] != observed_at:
                return False
            if any(item.get("observed_at") != observed_at for item in observations["observations"] if type(item) is dict):
                return False
            for value in (observed_at, *(item.get("observed_at") for item in observations["observations"] if type(item) is dict)):
                age = (now - datetime.strptime(value, _ATTESTED_TIMESTAMP).replace(tzinfo=utc)).total_seconds()
                if not 0 <= age <= 300:
                    return False
            for item in observations["observations"]:
                observation_validator.validate(item)
                if item["evidence_kind"] != "runtime" or set(item["residue"]) != residue_keys or any(type(value) is not int or value < 0 for value in item["residue"].values()):
                    return False
            return profile["issuer"] == issuer and profile["expected_issuer"] == issuer and profile["rootless"] is True and profile["signature_verified"] is True
        except Exception:
            return False

    def expected_from_context(receipt: dict):
        values = {key: environment_get(key) for key in required_context}
        if any(type(value) is not str or not value for value in values.values()) or not values["GITHUB_REF"].startswith("refs/heads/"):
            return None
        try:
            run_attempt = int(values["GITHUB_RUN_ATTEMPT"])
        except ValueError:
            return None
        branch = values["GITHUB_REF"].removeprefix("refs/heads/")
        expected = expected_identity_type(values["GITHUB_REPOSITORY"], values["GITHUB_REPOSITORY_ID"], branch, values["GITHUB_SHA"], values["GITHUB_WORKFLOW_SHA"], values["GITHUB_RUN_ID"], run_attempt, receipt.get("image_ref"), receipt.get("image_digest"))
        fields = {
            "repository": expected.repository, "repository_id": expected.repository_id, "default_branch": expected.default_branch,
            "workflow_ref": expected.workflow_ref, "source_sha": expected.source_sha, "workflow_sha": expected.workflow_sha,
            "run_id": expected.run_id, "run_attempt": expected.run_attempt, "image_ref": expected.image_ref,
            "image_digest": expected.image_digest, "issuer": issuer, "certificate_identity": expected.certificate_identity,
        }
        return expected if all(receipt.get(key) == value for key, value in fields.items()) else None

    def __init__(self):
        self._profile = None
        self._observations = None

    @classmethod
    def from_imported_files(cls, profile_path: Path, observations_path: Path, receipt_path: Path, validation_at: str):
        loaded = [load_snapshot(path) for path in (profile_path, observations_path, receipt_path)]
        if any(value is None for value in loaded):
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        (profile_bytes, profile), (observations_bytes, observations), (receipt_bytes, receipt) = loaded
        if cls is not observer_type or not valid_documents(profile, observations, receipt, profile_bytes, observations_bytes, validation_at):
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        instance = cls()
        instance._profile = copy.deepcopy(profile)
        instance._observations = {item["case_id"]: copy.deepcopy(item) for item in observations["observations"]}
        expected = expected_from_context(receipt)
        sibling_root = Path(receipt_path).parent
        attestation_path = sibling_root / "e3-attestation.json"
        bundle_path = sibling_root / "e3-attestation.bundle.json"
        attestation_snapshot = load_snapshot(attestation_path)
        try:
            bundle_bytes = bundle_path.read_bytes()
            if expected is not None and attestation_snapshot is not None and receipt["verification_kind"] == "runtime" and receipt["attestation_sha256"] == hashlib.sha256(attestation_snapshot[0]).hexdigest() and receipt["bundle_sha256"] == hashlib.sha256(bundle_bytes).hexdigest() and e3_attestation.DEFAULT_PROCESS_RUNNER is original_run:
                with tempfile.TemporaryDirectory(prefix=".e3-runtime-") as directory:
                    snapshot_attestation = Path(directory) / "e3-attestation.json"
                    snapshot_bundle = Path(directory) / "e3-attestation.bundle.json"
                    snapshot_attestation.write_bytes(attestation_snapshot[0])
                    snapshot_bundle.write_bytes(bundle_bytes)
                    attestation = verify_signed(snapshot_attestation, snapshot_bundle, expected, original_run, datetime.strptime(validation_at, _ATTESTED_TIMESTAMP).replace(tzinfo=utc))
                reconstructed_profile = public_profile(attestation)
                reconstructed_observations = {"observations_version": "1.0", "observed_at": attestation["observed_at"], "observations": attestation["observations"], "terminal_residue": attestation["terminal_residue"]}
                if canonical(reconstructed_profile) == profile_bytes and canonical(reconstructed_observations) == observations_bytes:
                    seals[instance] = (canonical(instance._profile), canonical(instance._observations))
        except Exception:
            pass
        return instance

    def observe(self, case: dict) -> dict:
        if not gate(self) or type(case) is not dict or type(case.get("id")) is not str:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        try:
            return copy.deepcopy(self._observations[case["id"]])
        except KeyError as error:
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE") from error

    def runtime_profile(self) -> dict:
        if not gate(self):
            raise RuntimeUnavailable("SANDBOX_RUNTIME_UNAVAILABLE")
        return copy.deepcopy(self._profile)

    observer_type.__init__ = __init__
    observer_type.from_imported_files = from_imported_files
    observer_type.observe = observe
    observer_type.runtime_profile = runtime_profile
    class_snapshot = dict(vars(observer_type))

    def gate(instance: object) -> bool:
        try:
            seal = seals.get(instance)
            values = vars(instance)
            return type(instance) is observer_type and dict(vars(observer_type)) == class_snapshot and set(values) == {"_profile", "_observations"} and type(seal) is tuple and seal == (canonical(values["_profile"]), canonical(values["_observations"]))
        except Exception:
            return False

    return observer_type, gate


AttestedRuntimeObserver, has_attested_e3_construction = _install_attested_e3_boundary()
del _ATTESTED_SEALS, _ATTESTED_CLASS_SNAPSHOT
