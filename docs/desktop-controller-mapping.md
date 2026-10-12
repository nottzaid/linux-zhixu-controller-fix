# Desktop controller mapping without in-game interference

On the tested laptop, one physical controller has two jobs: the proxy
provides the gamepad, while AntiMicroX replaces a broken touchpad. The
desktop mapper must disappear inside games without taking the real controller
with it.

| Layer | Desktop | Guarded game |
| --- | --- | --- |
| `Microsoft X-Box 360 pad` served by the proxy | Present | Present |
| AntiMicroX virtual keyboard and mouse | Present | Stopped |

The guard controls only `controller-mouse.service`. It never touches the
proxy, `xpad`, or USB.

`zhixu-pad@.service` keeps the pad polled, so stopping AntiMicroX no longer
drops it off USB.

## Desktop profile

`antimicrox/desktop.gamecontroller.amgp` maps:

| Input | Desktop action |
| --- | --- |
| Left stick | Cursor, speed 20, Enhanced Precision |
| Right stick or D-pad up/down | Scroll |
| Left trigger / B | Right click |
| Right trigger / A | Left click |
| X | Middle click |
| Back / Start | Escape / Enter |

The tested SDL GUID is `030081b85e0400008e02000010010000`. Run
`antimicrox --list` before installing on another revision; if its GUID differs,
update both the profile and `controller-mouse.service`.

## How games acquire the guard

The guard reconciles three sources:

- **Steam:** watches `app-steam-app*.scope` units through the user systemd
  manager, with cgroup and process checks for startup/recovery.
- **Lutris:** `game-with-controller` creates an inhibitor before executing the
  runner and releases it after exit.
- **Integrated launchers:** call the public token protocol directly.

```text
controller-mouse-game-guard --inhibit PID-owner-N
controller-mouse-game-guard --release PID-owner-N
```

Tokens compose. The mapper returns only after the final Steam scope, Lutris
process, RetroPort emulator tree, or explicit inhibitor disappears. PID-prefixed
stale tokens are removed automatically.

[RetroPort](https://github.com/muradkant/retrobat-portable) uses this protocol
from emulator spawn through normal exit or **TERMINATE**. A failed spawn releases
the same owned token. Live verification showed `sources=wrapper`, no AntiMicroX
process, and continued Wine XInput enumeration during play; exit restored the
exact idle state.

## Requirements

- AntiMicroX 3.6.1 or compatible
- Python 3, `systemd --user`, and cgroup v2
- read access to the controller's `/dev/input/event*`
- optional `dbus-python` and PyGObject for event-driven Steam detection; without
  them the monitor polls every 0.5 seconds

## Install

From the repository root:

```sh
install -Dm644 antimicrox/desktop.gamecontroller.amgp \
  "$HOME/.config/antimicrox/desktop.gamecontroller.amgp"
install -Dm755 scripts/controller-mouse-game-guard \
  "$HOME/.local/bin/controller-mouse-game-guard"
install -Dm755 scripts/controller-mouse-toggle.sh \
  "$HOME/.local/bin/controller-mouse-toggle"
install -Dm755 scripts/game-with-controller.sh \
  "$HOME/.local/bin/game-with-controller"
install -Dm644 systemd/controller-mouse.service \
  "$HOME/.config/systemd/user/controller-mouse.service"
install -Dm644 systemd/controller-mouse-game-guard.service \
  "$HOME/.config/systemd/user/controller-mouse-game-guard.service"

systemctl --user daemon-reload
systemctl --user enable --now controller-mouse.service
systemctl --user enable --now controller-mouse-game-guard.service
```

Steam needs no launch option. For Lutris, merge this into
`~/.config/lutris/system.yml`:

```yaml
system:
  prefix_command: /home/YOUR_USER/.local/bin/game-with-controller
```

Add only `prefix_command` if `system:` already exists. A per-game prefix
overrides the global one, so wrap that game separately. Restart Lutris.

Toggle the mapper manually with `controller-mouse-toggle`. An optional Hyprland
binding is:

```ini
bind = $mainMod CTRL, M, exec, $HOME/.local/bin/controller-mouse-toggle
```

## Runtime state

Transient ownership lives under
`$XDG_RUNTIME_DIR/controller-mouse-game-guard/`. The guard remembers whether the
mapper was active before the first inhibitor; if it was manually disabled,
finishing a game does not enable it.

```sh
controller-mouse-game-guard --status
```

Typical states:

```text
sources=none mapper=active restore=no
sources=steam mapper=inactive restore=yes
sources=wrapper mapper=inactive restore=yes
```

## Verify

Baseline:

```sh
systemctl --user is-active controller-mouse.service
systemctl --user is-active controller-mouse-game-guard.service
controller-mouse-game-guard --status
```

Both services should be active and sources should be `none`.

Exercise Steam detection without launching a game:

```sh
systemd-run --user --scope \
  --unit=app-steam-app999999-isolation-test sleep 10
```

Or exercise the Lutris path:

```sh
"$HOME/.local/bin/game-with-controller" sleep 10
```

While either runs:

```sh
systemctl --user is-active controller-mouse.service || true
grep -E 'antimicrox .* Emulation|Microsoft X-Box 360 pad' \
  /proc/bus/input/devices
```

The mapper should be inactive, its virtual devices absent, and the
controller present. No new USB disconnect should appear merely because the
mapper stopped. After ten seconds the prior mapper state should return.

For an integrated launcher, inspect the same evidence during a real game:

```sh
controller-mouse-game-guard --status
pgrep -x antimicrox || true
```

## Recover or remove

If a stopped guard leaves restoration pending:

```sh
controller-mouse-game-guard --once
systemctl --user start controller-mouse.service
```

Remove the integration:

```sh
systemctl --user disable --now controller-mouse-game-guard.service
systemctl --user disable --now controller-mouse.service
rm -f "$HOME/.config/systemd/user/controller-mouse-game-guard.service" \
  "$HOME/.config/systemd/user/controller-mouse.service" \
  "$HOME/.config/antimicrox/desktop.gamecontroller.amgp" \
  "$HOME/.local/bin/controller-mouse-game-guard" \
  "$HOME/.local/bin/controller-mouse-toggle" \
  "$HOME/.local/bin/game-with-controller"
systemctl --user daemon-reload
```

Remove Lutris's `prefix_command` separately. This procedure does not touch the
proxy.
