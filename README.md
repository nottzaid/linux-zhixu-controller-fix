# ZhiXu controller fix for Linux

For the ZhiXu controller that poses as a wired Xbox 360 pad (USB `045e:028e`,
manufacturer `ZhiXu`), with its back switch on the Windows logo.

## What's wrong with it

- **It keeps disconnecting.** It drops off USB ~350 ms after the host stops
  polling it, and `xpad` polls only while something has it open. With no game
  running it reconnects in a loop, and a game that starts mid-loop gets a pad
  that comes and goes.
- **The stick and D-pad are swapped.** The left stick arrives as the D-pad, and
  the D-pad as the left stick at full tilt.

## The fix

A udev rule starts `zhixu-pad@.service` the moment the pad appears. The service
runs `zhixu-pad-proxy`, which:

- holds the pad open, so it stays connected;
- swaps the stick and D-pad back;
- forwards rumble;
- serves the result as an ordinary Xbox 360 pad, with the real one's name and
  IDs.

udev hides the real pad from your user, so games see only the proxy's copy.
No kernel patch, nothing to rebuild.

## Install

Needs `python-evdev`.

```sh
git clone https://github.com/nottzaid/linux-zhixu-controller-fix.git
cd linux-zhixu-controller-fix
sudo ./install.sh                # --uninstall removes it
```

`systemctl status 'zhixu-pad@*'` should show it running, and games should list
one "Xbox 360 Controller".

## Limits

- The pad has a D-pad mode, where the left stick sends only eight directions
  at full tilt and the D-pad moves the stick. On the Fantech EOS Pro, pressing
  Capture twice switches between that mode and the normal analog one
  ([Fantech's FAQ](https://fantechworld.com/products/eos-pro-wgp15)). The
  proxy undoes the swap in D-pad mode and stops swapping as soon as the stick
  reports a partial tilt.
- D-pad Left is unreliable: in some captures the pad never sent it.
- Other switch positions give other USB identities, which this doesn't handle.

## Coming from the old xpad patch

Earlier versions patched `xpad-dkms-git`. `install.sh` refuses to run while
that driver is installed, because the proxy would swap the stick back. Remove
the old pieces first:

```sh
sudo pacman -Rns xpad-dkms-git
sudo systemctl disable --now zhixu-controller-ensure-xpad-mode.service
sudo rm -f /etc/systemd/system/zhixu-controller-ensure-xpad-mode.service \
  /usr/local/sbin/zhixu-controller-ensure-xpad-mode \
  /etc/udev/rules.d/99-zhixu-controller-xpad-mode.rules
```

Then drop `usbcore.quirks=057e:2009:ik` from the kernel command line and reboot.

## Mouse mode

Optional: the pad drives the desktop through AntiMicroX and steps aside while a
game runs. See [docs/mouse-mode.md](docs/mouse-mode.md).

## Tests

```sh
tests/static.sh    # syntax, udev rule, unit
tests/proxy.py     # the proxy end to end with a fake pad, read through SDL3
```
