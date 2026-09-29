#!/usr/bin/python
"""JSON-lines bridge to fprintd. Each invocation owns and releases its claim.

The helper runs as the current user. fprintd/Polkit owns authorization; no
passwords, templates, PAM writes, firmware operations or root helper here.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import signal
import subprocess
import sys
import tempfile
import time

from gi.repository import Gio, GLib

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model import DEFAULTS, FINGERS, ScanState, pam_status, validate_settings

BUS = "net.reactivated.Fprint"
DEVICE = BUS + ".Device"
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "x1-touch/settings.json"


def emit(event):
    print(json.dumps(event, separators=(",", ":")), flush=True)


def load_settings():
    try:
        return validate_settings(json.loads(CONFIG.read_text()))
    except FileNotFoundError:
        return dict(DEFAULTS)


def save_settings(values):
    values = validate_settings(values)
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".settings-", dir=CONFIG.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(values, stream, indent=2)
            stream.write("\n")
        os.replace(name, CONFIG)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return values


def friendly_error(error):
    name = Gio.DBusError.get_remote_error(error) if isinstance(error, GLib.Error) else ""
    hints = {
        "AlreadyInUse": "The reader is busy. Finish any fingerprint login or sudo prompt, then retry.",
        "PermissionDenied": "Authorization was declined. Retry and approve the system authorization dialog.",
        "NoEnrolledPrints": "No fingerprint is enrolled for this finger.",
        "ServiceUnknown": "fprintd is not installed or its D-Bus service is unavailable.",
        "NoSuchDevice": "The reader is unavailable. Reconnect or wake the laptop and refresh.",
        "UnknownMethod": "This fprintd version does not support that operation.",
        "PrintsNotDeleted": "The fingerprint could not be removed. Refresh to check its current state.",
    }
    suffix = (name or "").rsplit(".", 1)[-1]
    return hints.get(suffix, str(error)), name or type(error).__name__


class Client:
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.path = None
        self.claimed = False
        self.active = None

    def call(self, method, signature=None, args=(), path=None, interface=DEVICE, timeout=15000):
        params = GLib.Variant(signature, args) if signature else None
        result = self.bus.call_sync(BUS, path or self.path, interface, method, params, None,
                                    Gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, timeout, None)
        return result.unpack()

    def properties(self, path=None):
        return self.call("GetAll", "(s)", (DEVICE,), path, "org.freedesktop.DBus.Properties")[0]

    def discover(self):
        # fprintd owns hardware support, including USB and SPI readers.
        self.path = None
        paths = self.call("GetDevices", path="/net/reactivated/Fprint/Manager", interface=BUS + ".Manager")[0]
        if not paths:
            raise RuntimeError("No reader is exposed by fprintd. Check that your sensor is enabled and supported by the installed libfprint driver.")
        if len(paths) != 1:
            raise RuntimeError("Multiple fingerprint readers are exposed by fprintd. Connect only one to manage enrollments.")
        props = self.properties(paths[0])
        self.path = paths[0]
        return props

    def fingers(self):
        try:
            return self.call("ListEnrolledFingers", "(s)", ("",))[0]
        except GLib.Error as error:
            if (Gio.DBusError.get_remote_error(error) or "").endswith(".NoEnrolledPrints"):
                return []
            raise

    def claim(self):
        self.call("Claim", "(s)", ("",), timeout=120000)
        self.claimed = True

    def cleanup(self):
        errors = []
        if self.active:
            try:
                self.call(self.active + "Stop", timeout=3000)
            except GLib.Error as error:
                if not (Gio.DBusError.get_remote_error(error) or "").endswith(".NoActionInProgress"):
                    errors.append(friendly_error(error)[0])
            self.active = None
        if self.claimed:
            try:
                self.call("Release", timeout=3000)
            except GLib.Error as error:
                errors.append(friendly_error(error)[0])
            self.claimed = False
        return errors


def snapshot(client):
    # Read-only: never claim the reader just to paint a status panel.
    result = {"type": "snapshot", "user": pwd.getpwuid(os.getuid()).pw_name,
              "present": False, "fingers": [], "settings": load_settings(),
              "auth": {key: pam_status(path) for key, path in {
                  "sudo": "/etc/pam.d/sudo", "polkit": "/etc/pam.d/polkit-1",
                  "lock": "/etc/pam.d/omarchy-lock-fingerprint"}.items()}}
    try:
        props = client.discover()
        result.update(present=True, name=props.get("name", "Fingerprint reader"), scanType=props.get("scan-type", "unknown"),
                      fingers=client.fingers())
    except (GLib.Error, RuntimeError) as error:
        result["error"], result["errorCode"] = friendly_error(error)
    try:
        result["model"] = Path("/sys/class/dmi/id/product_version").read_text().strip()
    except OSError:
        result["model"] = "This computer"
    packages = subprocess.run(["pacman", "-Q", "fprintd", "libfprint-git", "libfprint"],
                              capture_output=True, text=True, timeout=5)
    result["packages"] = list(dict.fromkeys(packages.stdout.strip().splitlines()))
    return result


def run_operation(client, action, finger, timeout, emit_event=emit):
    if finger not in FINGERS:
        raise ValueError("Choose a specific finger")
    props = client.discover()
    scan_type = props.get("scan-type", "unknown")
    enrolled = client.fingers()
    if action == "enroll" and finger in enrolled:
        raise ValueError("This finger is already enrolled. Remove it explicitly before enrolling again.")
    if action in ("verify", "delete") and finger not in enrolled:
        raise ValueError("This finger is not enrolled")
    emit_event({"type": "phase", "message": "Requesting access to the reader…", "code": "authorizing"})
    client.claim()
    subscription = None
    source = None
    loop = GLib.MainLoop()
    finished = False
    success = False
    started = time.monotonic()

    def cancel(signum, frame):
        nonlocal finished
        if not finished:
            finished = True
            emit_event({"type": "result", "success": False, "code": "cancelled", "message": "Scan cancelled"})
        loop.quit()

    old_signals = {s: signal.signal(s, cancel) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        if action == "delete":
            client.call("DeleteEnrolledFinger", "(s)", (finger,), timeout=120000)
            emit_event({"type": "result", "success": True, "code": "deleted", "message": "Fingerprint removed"})
            return True
        stages = client.properties().get("num-enroll-stages", 0)
        state = ScanState(action, stages, scan_type)

        def on_signal(conn, sender, path, iface, name, params):
            nonlocal finished, success
            if finished:
                return
            if name == action.capitalize() + "Status":
                code, done = params.unpack()
                event = state.update(code, done)
                if event:
                    event["elapsedMs"] = round((time.monotonic() - started) * 1000)
                    emit_event(event)
                    if event["done"]:
                        success = event["success"]
                        finished = True
                        loop.quit()
            elif name == "VerifyFingerSelected":
                emit_event({"type": "selected", "finger": params.unpack()[0]})

        subscription = client.bus.signal_subscribe(BUS, DEVICE, None, client.path, None,
                                                   Gio.DBusSignalFlags.NONE, on_signal)
        # Start may trigger a Polkit dialog; the scan timeout begins afterwards.
        client.call(action.capitalize() + "Start", "(s)", (finger,), timeout=120000)
        client.active = action.capitalize()
        if finished:
            return False
        started = time.monotonic()
        emit_event({"type": "phase", "code": "scanning", "stages": max(0, stages),
                    "message": ("Swipe your " if scan_type == "swipe" else "Scan your ") + finger.replace("-finger", " finger").replace("-", " ") + (" across the sensor." if scan_type == "swipe" else " on the sensor.")})

        def expired():
            nonlocal finished
            if not finished:
                finished = True
                emit_event({"type": "result", "success": False, "code": "timeout", "message": "Scan timed out. You can try again."})
                loop.quit()
            return GLib.SOURCE_REMOVE

        source = GLib.timeout_add_seconds(timeout, expired)
        # Wake Python regularly so SIGTERM cancels promptly, even without scans.
        def heartbeat_tick():
            # SIGTERM can arrive after Start but before MainLoop.run(). A quit
            # at that point has no effect; settle it on the first loop tick.
            if finished:
                loop.quit()
            return GLib.SOURCE_CONTINUE

        heartbeat = GLib.timeout_add(100, heartbeat_tick)
        try:
            loop.run()
        finally:
            GLib.source_remove(heartbeat)
        return success
    finally:
        if subscription is not None:
            client.bus.signal_unsubscribe(subscription)
        if source and GLib.MainContext.default().find_source_by_id(source):
            GLib.source_remove(source)
        for sig, handler in old_signals.items():
            signal.signal(sig, handler)
        for message in client.cleanup():
            emit_event({"type": "warning", "message": message})


def main():
    parser = argparse.ArgumentParser(description="X1 Touch fingerprint bridge")
    parser.add_argument("action", choices=("status", "verify", "enroll", "delete", "settings"))
    parser.add_argument("--finger", choices=FINGERS)
    parser.add_argument("--timeout", type=int)
    parser.add_argument("--confirm-finger", choices=FINGERS)
    parser.add_argument("--json")
    args = parser.parse_args()
    client = None
    try:
        if args.action == "settings":
            emit({"type": "settings", "settings": save_settings(json.loads(args.json or "{}"))})
            return 0
        if args.action == "delete" and (not args.finger or args.confirm_finger != args.finger):
            raise ValueError("Deletion requires --confirm-finger matching --finger")
        prefs = load_settings()
        timeout = args.timeout if args.timeout is not None else prefs["enrollTimeout" if args.action == "enroll" else "verifyTimeout"]
        if not 5 <= timeout <= 180:
            raise ValueError("Timeout must be between 5 and 180 seconds")
        client = Client()
        if args.action == "status":
            emit(snapshot(client))
            return 0
        return 0 if run_operation(client, args.action, args.finger, timeout) else 2
    except (GLib.Error, OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        message, code = friendly_error(error)
        emit({"type": "error", "message": message, "code": code, "success": False})
        return 1
    finally:
        if client:
            client.cleanup()


if __name__ == "__main__":
    sys.exit(main())
