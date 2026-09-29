import importlib.util
import json
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import fingerprint as fp
from model import DEFAULTS, FINGERS, ScanState, detect_sensor, pam_status, validate_settings


class FakeBus:
    def signal_subscribe(self, *args):
        self.callback = args[-1]
        return 1

    def signal_unsubscribe(self, subscription):
        self.unsubscribed = True


class FakeClient:
    def __init__(self, events=(), enrolled=("right-index-finger",), fail=None):
        self.bus = FakeBus()
        self.path = "/fake"
        self.claimed = False
        self.active = None
        self.events = events
        self.enrolled = enrolled
        self.calls = []
        self.fail = fail

    def discover(self):
        self.calls.append("discover")

    def fingers(self):
        return self.enrolled

    def claim(self):
        self.calls.append("Claim")
        self.claimed = True

    def properties(self):
        return {"num-enroll-stages": 3}

    def call(self, method, *args, **kwargs):
        self.calls.append(method)
        if self.fail == method:
            raise RuntimeError("Simulated failure")
        if method.endswith("Start"):
            for code, done in self.events:
                def dispatch(c=code, d=done):
                    self.bus.callback(None, None, None, None, method[:-5] + "Status", fp.GLib.Variant("(sb)", (c, d)))
                    return False
                fp.GLib.idle_add(dispatch)

    cleanup = fp.Client.cleanup


class ModelTests(unittest.TestCase):
    def test_exact_hardware_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, vendor, product in [("correct", "27c6", "659c"), ("t480", "06cb", "009a"), ("other", "27c6", "1234")]:
                p = root / name
                p.mkdir()
                (p / "idVendor").write_text(vendor)
                (p / "idProduct").write_text(product)
            self.assertEqual(detect_sensor(root), ["correct"])

    def test_pam_comment_is_not_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "pam"
            p.write_text("# auth sufficient pam_fprintd.so\nauth include system-auth\n")
            self.assertEqual(pam_status(p), "not-configured")
            p.write_text("auth sufficient pam_fprintd.so\n")
            self.assertEqual(pam_status(p), "configured")

    def test_settings_validate_types_bounds_and_keys(self):
        self.assertEqual(validate_settings({}), DEFAULTS)
        for bad in ({"verifyTimeout": True}, {"verifyTimeout": 0}, {"enrollTimeout": 181}, {"animations": 1}, {"defaultHand": "both"}, {"command": "anything"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_settings(bad)

    def test_unknown_stage_count_does_not_fabricate_progress(self):
        state = ScanState("enroll", -1)
        event = state.update("enroll-stage-passed", False)
        self.assertEqual(event["stages"], 0)
        self.assertEqual(event["passed"], 1)

    def test_retries_do_not_advance_progress(self):
        state = ScanState("enroll", 3)
        state.update("enroll-stage-passed", False)
        event = state.update("enroll-remove-and-retry", False)
        self.assertEqual(event["passed"], 1)
        self.assertFalse(event["done"])
        self.assertTrue(state.update("enroll-completed", True)["success"])
        self.assertIsNone(state.update("enroll-stage-passed", False))

    def test_verify_failure_is_terminal(self):
        state = ScanState("verify")
        self.assertIsNone(state.update("enroll-completed", True))
        self.assertTrue(state.update("verify-no-match", True)["done"])

    def test_settings_atomic_and_private(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(fp, "CONFIG", Path(tmp) / "config/settings.json"):
            self.assertEqual(fp.load_settings(), DEFAULTS)
            fp.save_settings({"animations": False})
            self.assertFalse(fp.load_settings()["animations"])
            self.assertEqual(fp.CONFIG.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(fp.CONFIG.parent.glob(".settings-*")), [])


class LifecycleTests(unittest.TestCase):
    def run_fake(self, client, action="verify", finger="right-index-finger"):
        events = []
        result = fp.run_operation(client, action, finger, 5, events.append)
        return result, events

    def test_match_stops_and_releases(self):
        client = FakeClient([("verify-match", True)])
        result, events = self.run_fake(client)
        self.assertTrue(result)
        self.assertEqual(client.calls[-2:], ["VerifyStop", "Release"])
        self.assertTrue(client.bus.unsubscribed)

    def test_enrollment_reports_real_stages(self):
        client = FakeClient([("enroll-stage-passed", False), ("enroll-stage-passed", False), ("enroll-completed", True)], enrolled=())
        result, events = self.run_fake(client, "enroll")
        self.assertTrue(result)
        self.assertEqual([e["passed"] for e in events if e["type"] == "scan"], [1, 2, 2])
        self.assertEqual(client.calls[-2:], ["EnrollStop", "Release"])

    def test_existing_enrollment_is_never_overwritten(self):
        client = FakeClient()
        with self.assertRaisesRegex(ValueError, "already enrolled"):
            self.run_fake(client, "enroll")
        self.assertNotIn("Claim", client.calls)

    def test_start_failure_releases_claim(self):
        client = FakeClient(fail="VerifyStart")
        with self.assertRaisesRegex(RuntimeError, "Simulated"):
            self.run_fake(client)
        self.assertEqual(client.calls[-1], "Release")
        self.assertTrue(client.bus.unsubscribed)

    def test_timeout_releases_reader(self):
        client = FakeClient()
        with patch.object(fp.GLib, "timeout_add_seconds", side_effect=lambda seconds, callback: fp.GLib.timeout_add(5, callback)):
            result, events = self.run_fake(client)
        self.assertFalse(result)
        self.assertIn("timeout", [e.get("code") for e in events])
        self.assertEqual(client.calls[-2:], ["VerifyStop", "Release"])

    def test_cancel_releases_reader(self):
        client = FakeClient()
        def cancel():
            signal.raise_signal(signal.SIGTERM)
            return False
        fp.GLib.timeout_add(5, cancel)
        result, events = self.run_fake(client)
        self.assertFalse(result)
        self.assertIn("cancelled", [e.get("code") for e in events])
        self.assertEqual(client.calls[-2:], ["VerifyStop", "Release"])

    def test_cancel_before_main_loop_starts(self):
        client = FakeClient()
        events = []
        def receive(event):
            events.append(event)
            if event.get("code") == "scanning":
                signal.raise_signal(signal.SIGTERM)
        self.assertFalse(fp.run_operation(client, "verify", "right-index-finger", 5, receive))
        self.assertIn("cancelled", [e.get("code") for e in events])
        self.assertEqual(client.calls[-2:], ["VerifyStop", "Release"])

    def test_delete_is_single_finger_only(self):
        client = FakeClient()
        result, events = self.run_fake(client, "delete")
        self.assertTrue(result)
        self.assertIn("DeleteEnrolledFinger", client.calls)
        self.assertNotIn("DeleteEnrolledFingers", client.calls)
        self.assertEqual(client.calls[-1], "Release")

    def test_cli_delete_needs_matching_confirmation_before_bus(self):
        for confirm in ([], ["--confirm-finger", "left-thumb"]):
            with patch.object(sys, "argv", ["fingerprint.py", "delete", "--finger", "right-index-finger"] + confirm), patch.object(fp, "Client") as client, patch.object(fp, "emit"):
                self.assertEqual(fp.main(), 1)
                client.assert_not_called()

    def test_invalid_finger_cannot_reach_device(self):
        client = FakeClient()
        with self.assertRaises(ValueError):
            self.run_fake(client, finger="any")
        self.assertEqual(client.calls, [])


if __name__ == "__main__":
    unittest.main()
