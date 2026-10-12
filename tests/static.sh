#!/bin/sh

set -eu

root=$(cd -- "$(dirname -- "$0")/.." && pwd)
unit="$root/systemd/zhixu-controller-ensure-xpad-mode.service"
rule="$root/udev/99-zhixu-controller-xpad-mode.rules"
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT HUP INT TERM

for script in "$root"/scripts/*.sh "$root"/tools/*.sh; do
    sh -n "$script"
done
bash -n "$root/install.sh"
udevadm verify --no-summary "$root"/udev/*.rules
cp "$root/systemd/zhixu-pad@.service" "$temporary/zhixu-pad@event0.service"
systemd-analyze verify "$temporary/zhixu-pad@event0.service"

if grep -Eq '^(After|Wants)=.*systemd-udev-settle' "$unit"; then
    printf 'deprecated udev settle dependency returned\n' >&2
    exit 1
fi
grep -q '^After=systemd-udev-trigger.service$' "$unit"
grep -q 'SYSTEMD_WANTS.*zhixu-controller-ensure-xpad-mode.service' "$rule"

# Verify unit syntax without requiring the machine-local helper installation.
sed 's|/usr/local/sbin/zhixu-controller-ensure-xpad-mode|/usr/bin/true|' \
    "$unit" >"$temporary/zhixu-controller-ensure-xpad-mode.service"
systemd-analyze verify "$temporary/zhixu-controller-ensure-xpad-mode.service"

printf 'PASS build, scripts, udev rules, keepalive unit, and non-blocking boot unit\n'
