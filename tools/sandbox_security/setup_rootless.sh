#!/usr/bin/env bash
set -euo pipefail

if [ "$(id -u)" -eq 0 ]; then exit 1; fi
command -v dockerd-rootless-setuptool.sh >/dev/null
command -v newuidmap >/dev/null
command -v newgidmap >/dev/null
grep -q "^$(id -un):" /etc/subuid
grep -q "^$(id -un):" /etc/subgid
[ "$(stat -fc %T /sys/fs/cgroup)" = "cgroup2fs" ]
controllers="$(cat /sys/fs/cgroup/cgroup.controllers)"
for controller in memory pids cpu; do
  case " $controllers " in *" $controller "*) ;; *) exit 1;; esac
done
dockerd-rootless-setuptool.sh install --force
systemctl --user start docker
docker context use rootless
security_options="$(docker info --format '{{json .SecurityOptions}}')"
cgroup="$(docker info --format '{{.CgroupVersion}} {{.CgroupDriver}}')"
case "$security_options" in *rootless*) ;; *) exit 1;; esac
[ "$cgroup" = "2 systemd" ]
