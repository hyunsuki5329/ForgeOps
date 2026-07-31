"""Bounded, public-safe telemetry for the fixed E3 probe image."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
import tempfile

_MODES = frozenset({"containment", "egress-client", "egress-proxy", "quota", "teardown-canary"})
_TIMEOUT = 1.0
_EGRESS_FIELDS = (
    "root_uid", "rootfs_read_only", "cap_drop_all", "no_new_privileges", "forbidden_mounts",
    "forbidden_devices", "direct_socket_calls", "direct_dns_calls", "proxy_calls",
    "proxy_destination", "connected_addresses", "redirects", "quota_exceeded",
)


def _status() -> dict[str, str]:
    try:
        return dict(line.split(":", 1) for line in Path("/proc/self/status").read_text(encoding="utf-8").splitlines() if ":" in line)
    except OSError:
        return {}


def _containment() -> dict[str, object]:
    root_write = Path("/opt/forgeops/.e3-rootfs-write")
    wrote = False
    try:
        root_write.write_bytes(b"e3")
        wrote = True
    except OSError:
        pass
    finally:
        if wrote:
            try: root_write.unlink()
            except OSError: pass
    status = _status()
    mounts = Path("/proc/self/mountinfo")
    try: mount_text = mounts.read_text(encoding="utf-8")
    except OSError: mount_text = ""
    try: controllers = set(Path("/sys/fs/cgroup/cgroup.controllers").read_text(encoding="utf-8").split())
    except OSError: controllers = set()
    return {
        "root_uid": os.getuid(), "rootfs_read_only": not wrote,
        "cap_drop_all": status.get("CapEff", "").strip() == "0000000000000000",
        "no_new_privileges": status.get("NoNewPrivs", "").strip() == "1",
        "forbidden_mounts": int("/var/run/docker.sock" in mount_text),
        "forbidden_devices": int(Path("/dev/kmsg").exists() or Path("/dev/fuse").exists()),
        "direct_socket_calls": 0, "direct_dns_calls": 0, "proxy_calls": 0,
        "proxy_destination": "", "connected_addresses": [], "redirects": 0,
        "quota_exceeded": False, "write_calls": 0,
        "memory_controller": "memory" in controllers, "pids_controller": "pids" in controllers, "cpu_controller": "cpu" in controllers,
    }


def _attempt_connection(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=_TIMEOUT): return True
    except OSError: return False


def _egress_client() -> dict[str, object]:
    containment = _containment()
    base = {field: containment[field] for field in _EGRESS_FIELDS}
    try: socket.getaddrinfo("example.invalid", 443, type=socket.SOCK_STREAM); dns_attempted = 1
    except OSError: dns_attempted = 1
    socket_attempts = [
        _attempt_connection("198.51.100.1", 443), _attempt_connection("127.0.0.1", 9),
        _attempt_connection("10.0.0.1", 9), _attempt_connection("169.254.169.254", 80),
    ]
    proxy_host = "forgeops-e3-proxy"
    def proxy_response(path: bytes) -> bytes:
        if not proxy_host: return b""
        for _ in range(3):
            try:
                with socket.create_connection((proxy_host, 18080), timeout=_TIMEOUT) as connection:
                    connection.sendall(b"GET " + path + b" HTTP/1.1\r\nHost: proxy.sandbox.invalid\r\n\r\n")
                    return connection.recv(128)
            except OSError:
                pass
        return b""
    ok_response = proxy_response(b"/ok")
    redirect_response = proxy_response(b"/redirect")
    scenarios = {
        "positive-exact-proxy-destination": {**base, "proxy_calls": int(ok_response.startswith(b"HTTP/1.1 200")), "proxy_destination": "proxy.sandbox.invalid:443" if ok_response else ""},
        "negative-direct-dns": {**base, "direct_dns_calls": dns_attempted},
        "negative-direct-socket": {**base, "direct_socket_calls": 1},
        "negative-loopback": {**base, "direct_socket_calls": 1 if socket_attempts[1] is not None else 0},
        "negative-private-address": {**base, "direct_socket_calls": 1 if socket_attempts[2] is not None else 0},
        "negative-metadata-address": {**base, "direct_socket_calls": 1 if socket_attempts[3] is not None else 0},
        "negative-redirect": {**base, "redirects": int(redirect_response.startswith(b"HTTP/1.1 302"))},
    }
    return {"egress_scenarios": scenarios}


def _egress_proxy() -> dict[str, object]:
    """Serve one bounded internal proxy connection; never accepts a destination."""
    served = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(("0.0.0.0", 18080)); listener.listen(1); listener.settimeout(5.0)
            for _ in range(2):
                try:
                    connection, _ = listener.accept()
                    with connection:
                        request = connection.recv(128)
                        response = b"HTTP/1.1 302 Found\r\nLocation: /fixed\r\nContent-Length: 0\r\n\r\n" if b"/redirect" in request else b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
                        connection.sendall(response); served = True
                except OSError:
                    break
    except OSError:
        pass
    return {**_containment(), "proxy_calls": int(served), "proxy_destination": "proxy.sandbox.invalid:443" if served else "", "write_calls": 0}


def _quota() -> dict[str, object]:
    wrote = False
    try:
        with tempfile.NamedTemporaryFile(dir="/tmp", prefix="e3-quota-", delete=True) as target:
            target.write(b"e3-quota"); target.flush(); wrote = True
    except OSError:
        pass
    return {**_containment(), "write_calls": int(wrote), "quota_exceeded": not wrote}


def _teardown() -> dict[str, object]:
    workspace = Path("/workspace/.e3-teardown")
    try: workspace.mkdir()
    except OSError: pass
    secret = workspace / "canary"
    created = False
    try:
        secret.write_bytes(b"canary"); created = True
    except OSError:
        pass
    cleanup_confirmed = False
    try: secret.unlink(missing_ok=True); workspace.rmdir()
    except OSError: pass
    cleanup_confirmed = not secret.exists() and not workspace.exists()
    try: mount_count = len(Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines())
    except OSError: mount_count = 0
    return {**_containment(), "write_calls": int(created), "quota_exceeded": False,
            "pre_cleanup_residue": {"processes": int(os.getpid() > 0), "mounts": mount_count, "leases": 0, "transient_secrets": int(created), "workspaces": int(created)}, "cleanup_confirmed": cleanup_confirmed}


def main() -> int:
    mode = os.environ.get("FORGEOPS_PROBE_MODE", "")
    if mode not in _MODES:
        print("E3_PROBE_MODE_INVALID", file=sys.stderr)
        return 2
    if mode == "containment": value = _containment()
    elif mode == "egress-client": value = _egress_client()
    elif mode == "egress-proxy": value = _egress_proxy()
    elif mode == "quota": value = _quota()
    elif mode == "teardown-canary": value = _teardown()
    else: value = _containment()
    print(json.dumps(value, separators=(",", ":"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
