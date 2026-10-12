#!/usr/bin/env bash
# Install the ZhiXu pad fix, or remove it with --uninstall. Run as root.

set -Eeuo pipefail

HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
say() { printf 'zhixu-pad: %s\n' "$*"; }

case "${1:-}" in
    '') uninstall=0 ;;
    --uninstall) uninstall=1 ;;
    *) say "usage: ${0##*/} [--uninstall]" >&2; exit 64 ;;
esac
[[ $EUID -eq 0 ]] || { say "must run as root" >&2; exit 1; }

if ((uninstall)); then
    systemctl stop 'zhixu-pad@*.service'
    rm -f /etc/udev/rules.d/70-zhixu-pad.rules /etc/systemd/system/zhixu-pad@.service
else
    install -Dm644 "$HERE/udev/70-zhixu-pad.rules" /etc/udev/rules.d/70-zhixu-pad.rules
    install -Dm644 "$HERE/systemd/zhixu-pad@.service" /etc/systemd/system/zhixu-pad@.service
fi
systemctl daemon-reload
udevadm control --reload

# Re-enumerate a connected pad so the change applies without replugging it.
for pad in /sys/bus/usb/devices/*; do
    [[ -f $pad/authorized && "$(cat "$pad/idVendor" "$pad/idProduct" "$pad/manufacturer" 2>/dev/null)" == $'045e\n028e\nZhiXu' ]] || continue
    echo 0 >"$pad/authorized"
    echo 1 >"$pad/authorized"
done
say "$( ((uninstall)) && echo removed || echo installed)"
