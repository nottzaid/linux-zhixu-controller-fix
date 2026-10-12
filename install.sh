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
    # Running proxies stop when the pad is re-enumerated below; stopping one
    # now would let the pad drop off USB mid-cycle.
    rm -f /etc/udev/rules.d/70-zhixu-pad.rules /etc/systemd/system/zhixu-pad@.service \
        /usr/local/libexec/zhixu-pad-proxy
else
    # The old fix patched xpad to unswap the stick; the proxy would swap it back.
    if [[ -e /sys/module/xpad/parameters/zhixu_suppress_rt ||
        $(modinfo -F parm xpad 2>/dev/null) == *zhixu_* ]] ||
        grep -qis zhixu /usr/src/xpad*/xpad.c; then
        say "the patched xpad from the old fix is installed or still loaded; remove it and reboot first (see README)" >&2
        exit 1
    fi
    /usr/bin/python3 -I -c 'import evdev' 2>/dev/null ||
        { say "needs python-evdev" >&2; exit 1; }
    install -Dm755 "$HERE/scripts/zhixu-pad-proxy" /usr/local/libexec/zhixu-pad-proxy
    install -Dm644 "$HERE/udev/70-zhixu-pad.rules" /etc/udev/rules.d/70-zhixu-pad.rules
    install -Dm644 "$HERE/systemd/zhixu-pad@.service" /etc/systemd/system/zhixu-pad@.service
fi
systemctl daemon-reload
udevadm control --reload
udevadm trigger --action=change --subsystem-match=misc --sysname-match=uinput

# Re-enumerate a connected pad so it gets fresh nodes (with or without the
# seat ACL) and a proxy running the script just installed, or none. A pad
# that drops off USB meanwhile comes back fresh on its own.
for pad in /sys/bus/usb/devices/*; do
    [[ -f $pad/authorized && "$(cat "$pad/idVendor" "$pad/idProduct" "$pad/manufacturer" 2>/dev/null)" == $'045e\n028e\nZhiXu' ]] || continue
    echo 0 2>/dev/null >"$pad/authorized" || continue
    echo 1 2>/dev/null >"$pad/authorized" ||
        [[ $(cat "$pad/authorized" 2>/dev/null) != 0 ]] ||
        say "could not re-enable the pad; replug it" >&2
done
if ((uninstall)); then
    systemctl stop 'zhixu-pad@*.service'
    say removed
else
    say installed
fi
