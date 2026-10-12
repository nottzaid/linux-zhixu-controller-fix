#!/bin/sh

set -eu

root=$(cd -- "$(dirname -- "$0")/.." && pwd)
unit="$root/systemd/zhixu-controller-ensure-xpad-mode.service"
rule="$root/udev/99-zhixu-controller-xpad-mode.rules"
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT HUP INT TERM

for script in "$root"/scripts/*.sh; do
    sh -n "$script"
done
bash -n "$root/install.sh"
for script in "$root/scripts/zhixu-pad-proxy" "$root/scripts/controller-mouse-game-guard" "$root/tests/proxy.py"; do
    python3 -c 'import ast, sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])' "$script"
done
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

printf 'PASS scripts, udev rules, proxy unit, and non-blocking boot unit\n'
