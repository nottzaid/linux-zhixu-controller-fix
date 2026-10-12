# Mouse mode

On a laptop with no working touchpad, the pad doubles as a mouse through
AntiMicroX. A guard stops AntiMicroX while a game runs, so the game gets no
clicks from it, and starts it again afterwards. The guard only starts and stops
`controller-mouse.service`; it never touches the proxy.

## Profile

`antimicrox/desktop.gamecontroller.amgp`:

| Input | Action |
| --- | --- |
| Left stick | Cursor |
| Right stick, D-pad up/down | Scroll |
| LT, B | Right click |
| RT, A | Left click |
| X | Middle click |
| Back, Start | Escape, Enter |

It is tied to SDL GUID `030081b85e0400008e02000010010000`, which the proxy
keeps. If `antimicrox --list` shows another, change it in the profile and in
`controller-mouse.service`.

## How the guard spots a game

- **Steam:** its `app-steam-app*.scope` units.
- **Lutris:** games run through `game-with-controller` (see Install).
- **Anything else:** `controller-mouse-game-guard --inhibit TOKEN` before the
  game, `--release TOKEN` after. A token that starts with its owner's PID is
  dropped once that process is gone. [RetroPort](https://github.com/nottzaid/retrobat-portable)
  does this.

Mouse mode comes back when the last game ends, unless it was off before.

## Install

Needs AntiMicroX. With `dbus-python` and PyGObject the guard reacts to Steam at
once; without them it checks every 0.5 s.

```sh
install -Dm644 antimicrox/desktop.gamecontroller.amgp ~/.config/antimicrox/desktop.gamecontroller.amgp
install -Dm755 scripts/controller-mouse-game-guard ~/.local/bin/controller-mouse-game-guard
install -Dm755 scripts/controller-mouse-toggle.sh ~/.local/bin/controller-mouse-toggle
install -Dm755 scripts/game-with-controller.sh ~/.local/bin/game-with-controller
install -Dm644 -t ~/.config/systemd/user systemd/controller-mouse.service systemd/controller-mouse-game-guard.service
systemctl --user daemon-reload
systemctl --user enable --now controller-mouse.service controller-mouse-game-guard.service
```

For Lutris, add this to `~/.config/lutris/system.yml` (a per-game prefix
overrides it) and restart Lutris:

```yaml
system:
  prefix_command: /home/YOUR_USER/.local/bin/game-with-controller
```

`controller-mouse-toggle` turns mouse mode on or off, e.g. from Hyprland:

```ini
bind = $mainMod CTRL, M, exec, $HOME/.local/bin/controller-mouse-toggle
```

## Check

`controller-mouse-game-guard --status` prints the state, e.g.
`sources=none mapper=active restore=no`. Fake a game for ten seconds:

```sh
systemd-run --user --scope --unit=app-steam-app999999-test sleep 10   # Steam
~/.local/bin/game-with-controller sleep 10                            # Lutris
```

Meanwhile `--status` shows `mapper=inactive`; afterwards, `active` again. If
the guard died mid-game and left mouse mode off, run
`controller-mouse-game-guard --once`.

## Remove

```sh
systemctl --user disable --now controller-mouse-game-guard.service controller-mouse.service
rm -f ~/.config/systemd/user/controller-mouse.service \
  ~/.config/systemd/user/controller-mouse-game-guard.service \
  ~/.config/antimicrox/desktop.gamecontroller.amgp \
  ~/.local/bin/controller-mouse-game-guard \
  ~/.local/bin/controller-mouse-toggle \
  ~/.local/bin/game-with-controller
systemctl --user daemon-reload
```

Then take `prefix_command` out of Lutris's `system.yml`.
