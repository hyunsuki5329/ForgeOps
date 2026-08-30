#!/usr/bin/env bash
set -euo pipefail

fail() {
  printf '%s\n' "$1" >&2
  exit "$2"
}

rootless_diagnostics() {
  SYSTEMD_COLORS=0 systemctl --user status docker.service --no-pager >&2 || true
  SYSTEMD_COLORS=0 journalctl --user --unit docker.service --no-pager --lines 50 --output short-iso >&2 || true
}

has_subid_mapping() {
  awk -F: -v user="$runner_user" '
    $1 == user &&
    $2 ~ /^[0-9]+$/ &&
    $3 ~ /^[0-9]+$/ &&
    $2 > 0 && $3 > 0 { found = 1 }
    END { exit found ? 0 : 1 }
  ' "$1"
}

runner_uid="$(id -u)"
[ "$runner_uid" -ne 0 ] || fail "E3_ROOTLESS_MUST_BE_UNPRIVILEGED" 20
command -v dockerd-rootless-setuptool.sh >/dev/null || fail "E3_ROOTLESS_SETUP_TOOL_MISSING" 21
command -v newuidmap >/dev/null || fail "E3_ROOTLESS_NEWUIDMAP_MISSING" 22
command -v newgidmap >/dev/null || fail "E3_ROOTLESS_NEWGIDMAP_MISSING" 23
runner_user="$(id -un)"
has_subid_mapping /etc/subuid || fail "E3_ROOTLESS_SUBUID_MISSING" 24
has_subid_mapping /etc/subgid || fail "E3_ROOTLESS_SUBGID_MISSING" 25
[ "$(stat -fc %T /sys/fs/cgroup)" = "cgroup2fs" ] || fail "E3_ROOTLESS_CGROUP_V2_REQUIRED" 26
controllers="$(cat /sys/fs/cgroup/cgroup.controllers)" || fail "E3_ROOTLESS_CGROUP_V2_REQUIRED" 26
for controller in memory pids cpu; do
  case " $controllers " in
    *" $controller "*) ;;
    *) fail "E3_ROOTLESS_CONTROLLER_MISSING" 27 ;;
  esac
done
expected_runtime_dir="/run/user/$runner_uid"
[ "${XDG_RUNTIME_DIR:-}" = "$expected_runtime_dir" ] || fail "E3_ROOTLESS_RUNTIME_DIR_INVALID" 28
[ -d "$XDG_RUNTIME_DIR" ] || fail "E3_ROOTLESS_RUNTIME_DIR_INVALID" 28
[ "$(stat -c %u "$XDG_RUNTIME_DIR")" = "$runner_uid" ] || fail "E3_ROOTLESS_RUNTIME_DIR_INVALID" 28
[ -S "$XDG_RUNTIME_DIR/bus" ] || fail "E3_ROOTLESS_USER_BUS_MISSING" 29

if ! dockerd-rootless-setuptool.sh install --force; then
  rootless_diagnostics
  fail "E3_ROOTLESS_INSTALL_FAILED" 30
fi
if ! systemctl --user start docker.service; then
  rootless_diagnostics
  fail "E3_ROOTLESS_SERVICE_FAILED" 31
fi
docker context use rootless >/dev/null || fail "E3_ROOTLESS_SERVICE_FAILED" 31
export DOCKER_HOST="unix://$XDG_RUNTIME_DIR/docker.sock"
for _attempt in {1..20}; do
  [ -S "$XDG_RUNTIME_DIR/docker.sock" ] && break
  sleep 0.25
done
[ -S "$XDG_RUNTIME_DIR/docker.sock" ] || fail "E3_ROOTLESS_SOCKET_MISSING" 32
context_host="$(docker context inspect rootless --format '{{.Endpoints.docker.Host}}')" || fail "E3_ROOTLESS_SOCKET_MISSING" 32
[ "$context_host" = "$DOCKER_HOST" ] || fail "E3_ROOTLESS_SOCKET_MISSING" 32
security_options="$(docker info --format '{{json .SecurityOptions}}')" || fail "E3_ROOTLESS_SERVICE_FAILED" 31
cgroup="$(docker info --format '{{.CgroupVersion}} {{.CgroupDriver}}')" || fail "E3_ROOTLESS_SERVICE_FAILED" 31
case "$security_options" in
  *rootless*) ;;
  *) fail "E3_ROOTLESS_SECURITY_OPTION_MISSING" 33 ;;
esac
[ "$cgroup" = "2 systemd" ] || fail "E3_ROOTLESS_CGROUP_DRIVER_INVALID" 34
