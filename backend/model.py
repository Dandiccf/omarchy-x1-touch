"""Pure state and validation. No fingerprint templates ever enter this process."""
from pathlib import Path

USB_ID = "27c6:659c"
FINGERS = tuple(f"{hand}-{finger}" for hand in ("left", "right") for finger in
                ("thumb", "index-finger", "middle-finger", "ring-finger", "little-finger"))
DEFAULTS = {"verifyTimeout": 20, "enrollTimeout": 90, "animations": True,
            "showHints": True, "defaultHand": "right"}


def validate_settings(values):
    if not isinstance(values, dict) or set(values) - set(DEFAULTS):
        raise ValueError("Unknown preference")
    result = dict(DEFAULTS)
    result.update(values)
    for key, low, high in (("verifyTimeout", 10, 60), ("enrollTimeout", 30, 180)):
        if type(result[key]) is not int or not low <= result[key] <= high:
            raise ValueError(f"{key} must be between {low} and {high} seconds")
    for key in ("animations", "showHints"):
        if type(result[key]) is not bool:
            raise ValueError(f"{key} must be true or false")
    if result["defaultHand"] not in ("left", "right"):
        raise ValueError("Choose left or right hand")
    return result


def detect_sensor(sysfs=Path("/sys/bus/usb/devices")):
    matches = []
    for entry in sysfs.iterdir():
        try:
            usb_id = f"{(entry / 'idVendor').read_text().strip()}:{(entry / 'idProduct').read_text().strip()}"
            if usb_id == USB_ID:
                matches.append(entry.name)
        except (OSError, UnicodeError):
            continue
    return matches


def pam_status(path):
    """Report a configured module, not a claim that authentication was tested."""
    try:
        lines = [line.split("#", 1)[0].strip() for line in Path(path).read_text().splitlines()]
    except OSError:
        return "not-configured"
    return "configured" if any(line.startswith("auth") and "pam_fprintd.so" in line
                               for line in lines) else "not-configured"


MESSAGES = {
    "verify-match": "Fingerprint matched",
    "verify-no-match": "No match. Lift your finger and try again.",
    "enroll-stage-passed": "Touch recorded. Lift and reposition your finger.",
    "enroll-completed": "Fingerprint enrolled",
    "enroll-duplicate": "This finger is already registered. Choose a different finger.",
    "enroll-data-full": "The sensor is full. Remove an unused enrollment before trying again.",
    "enroll-failed": "Enrollment failed. Try again with a clean, dry finger.",
}


def scan_message(code):
    if code in MESSAGES:
        return MESSAGES[code]
    suffix = code.split("-", 1)[-1]
    return {
        "retry-scan": "Lift your finger, then touch the sensor again.",
        "finger-not-centered": "Center your fingertip on the sensor.",
        "remove-and-retry": "Lift your finger completely, then try again.",
        "too-fast": "Keep your finger still a little longer.",
        "swipe-too-short": "Keep your fingertip on the sensor a little longer.",
        "disconnected": "The fingerprint sensor disconnected.",
        "unknown-error": "The driver reported a scan error. Try again.",
    }.get(suffix, "Sensor update: " + code)


class ScanState:
    def __init__(self, action, stages=0):
        self.action = action
        self.stages = max(0, stages)
        self.passed = 0
        self.done = False

    def update(self, code, done):
        if self.done or not code.startswith(self.action + "-"):
            return None
        if code == "enroll-stage-passed":
            self.passed += 1
        success = code in ("verify-match", "enroll-completed")
        terminal = success or done or code in ("verify-no-match", "enroll-failed", "enroll-duplicate",
                                               "enroll-data-full") or code.endswith(("disconnected", "unknown-error"))
        self.done = terminal
        return {"type": "scan", "code": code, "message": scan_message(code),
                "passed": self.passed, "stages": self.stages, "done": terminal,
                "success": success}
