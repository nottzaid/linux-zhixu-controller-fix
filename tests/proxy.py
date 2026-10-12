#!/usr/bin/python3
"""End-to-end test of zhixu-pad-proxy without the pad.

A fake pad (the real one's capabilities and IDs, through uinput) replays the
events the real pad sends; SDL3 reads the proxy's output the way a game does.
Needs python-evdev, SDL3, and write access to /dev/uinput (the input group,
once install.sh has run). Run from a desktop session so the proxy's output
gets the seat ACL.

Usage: tests/proxy.py [PROXY]   (default: scripts/zhixu-pad-proxy)
"""

import ctypes
import fcntl
import glob
import os
import select
import subprocess
import sys
import threading
import time

import evdev
from evdev import AbsInfo, ff
from evdev import ecodes as e

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROXY = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "scripts", "zhixu-pad-proxy")

STICK = AbsInfo(0, -32768, 32767, 16, 128, 0)
TRIGGER = AbsInfo(0, 0, 255, 0, 0, 0)
HAT = AbsInfo(0, -1, 1, 0, 0, 0)
CAPS = {   # as xpad reports the ZhiXu pad
    e.EV_KEY: [e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST, e.BTN_TL, e.BTN_TR,
               e.BTN_SELECT, e.BTN_START, e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR],
    e.EV_ABS: [(e.ABS_X, STICK), (e.ABS_Y, STICK), (e.ABS_Z, TRIGGER), (e.ABS_RX, STICK),
               (e.ABS_RY, STICK), (e.ABS_RZ, TRIGGER), (e.ABS_HAT0X, HAT), (e.ABS_HAT0Y, HAT)],
    e.EV_FF: [e.FF_RUMBLE, e.FF_PERIODIC, e.FF_SQUARE, e.FF_TRIANGLE, e.FF_SINE, e.FF_GAIN],
}
fake = evdev.UInput(CAPS, name="Microsoft X-Box 360 pad", vendor=0x045E, product=0x028E,
                    version=0x0110, bustype=e.BUS_USB, phys="zhixu-fake", max_effects=16)


# Answer rumble requests that reach the fake pad, as xpad would, and log them.
def _ioc(direction, nr, size):
    return direction << 30 | size << 16 | ord("U") << 8 | nr


BEGIN_UPLOAD = _ioc(3, 200, ctypes.sizeof(ff.UInputUpload))
END_UPLOAD = _ioc(1, 201, ctypes.sizeof(ff.UInputUpload))
BEGIN_ERASE = _ioc(3, 202, ctypes.sizeof(ff.UInputErase))
END_ERASE = _ioc(1, 203, ctypes.sizeof(ff.UInputErase))
ff_log, stop = [], threading.Event()


def serve_feedback():
    while not stop.is_set():
        if not select.select([fake.fd], [], [], 0.1)[0]:
            continue
        try:
            events = list(fake.read())
        except BlockingIOError:
            continue
        for event in events:
            if event.type == e.EV_UINPUT and event.code == e.UI_FF_UPLOAD:
                request = ff.UInputUpload()
                request.request_id = event.value
                fcntl.ioctl(fake.fd, BEGIN_UPLOAD, request)
                ff_log.append(("upload", request.effect.u.ff_rumble_effect.strong_magnitude))
                request.retval = 0
                fcntl.ioctl(fake.fd, END_UPLOAD, request)
            elif event.type == e.EV_UINPUT and event.code == e.UI_FF_ERASE:
                request = ff.UInputErase()
                request.request_id = event.value
                fcntl.ioctl(fake.fd, BEGIN_ERASE, request)
                request.retval = 0
                fcntl.ioctl(fake.fd, END_ERASE, request)
            elif event.type == e.EV_FF:
                ff_log.append(("play", event.code, event.value))


threading.Thread(target=serve_feedback, daemon=True).start()


def proxy_nodes():
    found = set()
    for node in glob.glob("/sys/class/input/event*"):
        try:
            if open(node + "/device/phys").read().strip() == "zhixu-pad-proxy":
                found.add("/dev/input/" + os.path.basename(node))
        except OSError:
            pass
    return found


existing = proxy_nodes()   # e.g. the installed proxy serving the real pad
proxy = subprocess.Popen([sys.executable, "-I", PROXY, fake.device.path],
                         stderr=subprocess.PIPE, text=True)
out_node = None
for _ in range(50):
    if new := proxy_nodes() - existing:
        out_node = new.pop()
        break
    time.sleep(0.1)
assert out_node, "the proxy's output device never appeared"
time.sleep(0.5)   # let udev apply the seat ACL

sdl = ctypes.CDLL("libSDL3.so.0")
sdl.SDL_Init.argtypes = [ctypes.c_uint32]
sdl.SDL_Init.restype = ctypes.c_bool
sdl.SDL_GetGamepads.argtypes = [ctypes.POINTER(ctypes.c_int)]
sdl.SDL_GetGamepads.restype = ctypes.POINTER(ctypes.c_uint32)
sdl.SDL_OpenGamepad.argtypes = [ctypes.c_uint32]
sdl.SDL_OpenGamepad.restype = ctypes.c_void_p
for name in ("SDL_GetGamepadPath", "SDL_GetGamepadName"):
    getattr(sdl, name).argtypes = [ctypes.c_void_p]
    getattr(sdl, name).restype = ctypes.c_char_p
sdl.SDL_GetGamepadAxis.argtypes = [ctypes.c_void_p, ctypes.c_int]
sdl.SDL_GetGamepadAxis.restype = ctypes.c_int16
sdl.SDL_GetGamepadButton.argtypes = [ctypes.c_void_p, ctypes.c_int]
sdl.SDL_GetGamepadButton.restype = ctypes.c_bool
sdl.SDL_RumbleGamepad.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint32]
sdl.SDL_RumbleGamepad.restype = ctypes.c_bool
sdl.SDL_GetError.restype = ctypes.c_char_p
assert sdl.SDL_Init(0x2000), sdl.SDL_GetError()   # SDL_INIT_GAMEPAD
pad = None
for _ in range(30):
    sdl.SDL_PumpEvents()
    count = ctypes.c_int()
    ids = sdl.SDL_GetGamepads(ctypes.byref(count))
    for i in range(count.value):
        opened = sdl.SDL_OpenGamepad(ids[i])
        if opened and sdl.SDL_GetGamepadPath(opened) == out_node.encode():
            pad = opened
    if pad:
        break
    time.sleep(0.1)
assert pad, "SDL does not list the proxy's output as a gamepad"
print(f'SDL sees the proxy output {out_node} as "{sdl.SDL_GetGamepadName(pad).decode()}"')

LX, LY, RX, RT = 0, 1, 2, 5                       # SDL_GamepadAxis
SOUTH, UP, DOWN, LEFT, RIGHT = 0, 11, 12, 13, 14   # SDL_GamepadButton
A = e.EV_ABS
HIGH, LOW = (32000, 32767), (-32768, -32000)
failures = 0


def send(*events):
    for etype, code, value in events:
        fake.write(etype, code, value)
    fake.syn()
    time.sleep(0.08)
    sdl.SDL_PumpEvents()
    sdl.SDL_UpdateGamepads()


def seen():
    dpad = "".join(name for button, name in ((UP, "U"), (DOWN, "D"), (LEFT, "L"), (RIGHT, "R"))
                   if sdl.SDL_GetGamepadButton(pad, button))
    return dict(LX=sdl.SDL_GetGamepadAxis(pad, LX), LY=sdl.SDL_GetGamepadAxis(pad, LY),
                RX=sdl.SDL_GetGamepadAxis(pad, RX), RT=sdl.SDL_GetGamepadAxis(pad, RT),
                dpad=dpad or "-", A=int(sdl.SDL_GetGamepadButton(pad, SOUTH)))


def report(label, ok, detail=""):
    global failures
    failures += not ok
    print(f'{"PASS" if ok else "FAIL"} {label:44} {detail}')


def check(label, expect, *events):
    send(*events)
    got = seen()
    bad = {key: (got[key], want) for key, want in expect.items()
           if (not want[0] <= got[key] <= want[1] if isinstance(want, tuple) else got[key] != want)}
    report(label, not bad, f"{got}" + (f"  mismatched: {bad}" if bad else ""))


check("idle", dict(LX=0, LY=0, dpad="-", A=0))
check("stick up (arrives as HAT0Y -1)", dict(LY=LOW, LX=0, dpad="-"), (A, e.ABS_HAT0Y, -1))
check("stick up-right (diagonal)", dict(LY=LOW, LX=HIGH, dpad="-"), (A, e.ABS_HAT0X, 1))
check("stick down-left", dict(LY=HIGH, LX=LOW, dpad="-"), (A, e.ABS_HAT0Y, 1), (A, e.ABS_HAT0X, -1))
check("stick released", dict(LY=0, LX=0, dpad="-"), (A, e.ABS_HAT0Y, 0), (A, e.ABS_HAT0X, 0))
check("D-pad Up (arrives as ABS_Y -32768)", dict(dpad="U", LX=0, LY=0), (A, e.ABS_Y, -32768))
check("D-pad Up released (ABS_Y -1)", dict(dpad="-", LY=0), (A, e.ABS_Y, -1))
check("D-pad Right (ABS_X 32767)", dict(dpad="R", LX=0), (A, e.ABS_X, 32767))
check("D-pad Right released (ABS_X 0)", dict(dpad="-"), (A, e.ABS_X, 0))
check("D-pad Down (ABS_Y 32767)", dict(dpad="D", LY=0), (A, e.ABS_Y, 32767))
check("D-pad Down released", dict(dpad="-"), (A, e.ABS_Y, -1))
check("D-pad Left (ABS_X -32768)", dict(dpad="L", LX=0), (A, e.ABS_X, -32768))
check("D-pad Left released", dict(dpad="-"), (A, e.ABS_X, 0))
check("stick and D-pad at once", dict(dpad="U", LX=HIGH, LY=0), (A, e.ABS_HAT0X, 1), (A, e.ABS_Y, -32768))
check("both released", dict(dpad="-", LX=0, LY=0), (A, e.ABS_HAT0X, 0), (A, e.ABS_Y, -1))
check("RT squeezed to 200 of 255", dict(RT=(25000, 26500)), (A, e.ABS_RZ, 200))
check("RT released", dict(RT=0), (A, e.ABS_RZ, 0))
check("A pressed", dict(A=1), (e.EV_KEY, e.BTN_SOUTH, 1))
check("A released", dict(A=0), (e.EV_KEY, e.BTN_SOUTH, 0))
check("right stick partial tilt passes through", dict(RX=12000), (A, e.ABS_RX, 12000))

ok = sdl.SDL_RumbleGamepad(pad, 0xC000, 0x4000, 300)
time.sleep(0.5)
uploads = [entry for entry in ff_log if entry[0] == "upload"]
plays = [entry for entry in ff_log if entry[0] == "play"]
report("rumble reaches the pad, played once", ok and uploads and 1 <= len(plays) <= 3,
       f"SDL ok={ok} uploads={uploads[:2]} plays={len(plays)}")

check("analog stick (ABS_X 15000): pass through", dict(LX=15000), (A, e.ABS_X, 15000))
check("after that, HAT is the D-pad again", dict(dpad="R", LX=15000), (A, e.ABS_HAT0X, 1))

stop.set()
time.sleep(0.3)
fake.close()
try:
    code = proxy.wait(timeout=5)
except subprocess.TimeoutExpired:
    proxy.kill()
    code = "hung"
report("proxy exits cleanly when the pad goes", code == 0, f"exit={code}")
print("proxy log:", proxy.stderr.read().strip().replace("\n", " | "))
print(f"\n{failures} failure(s)")
sys.exit(1 if failures else 0)
