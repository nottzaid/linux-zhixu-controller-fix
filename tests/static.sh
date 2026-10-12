#!/bin/sh

set -eu

root=$(cd -- "$(dirname -- "$0")/.." && pwd)
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

printf 'PASS scripts, udev rule, and proxy unit\n'
