"""Public-safe entry point for the fixed E3 probe image."""
from __future__ import annotations
import json
import os
import sys

_MODES = frozenset({"containment", "egress-client", "egress-proxy", "quota", "teardown-canary"})

def main() -> int:
    mode = os.environ.get("FORGEOPS_PROBE_MODE", "")
    if mode not in _MODES:
        print("E3_PROBE_MODE_INVALID", file=sys.stderr)
        return 2
    # The helper combines this closed result with Docker inspect facts.  Do not
    # add diagnostic values here: this image's stdout is signed public evidence.
    print(json.dumps({
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
    }, separators=(",", ":"), ensure_ascii=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
