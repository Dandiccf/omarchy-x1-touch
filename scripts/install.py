#!/usr/bin/python
"""Install the local project as an Omarchy plugin without privileged changes."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import time

ID = "io.github.dandiccf.x1-touch"
SOURCE = Path(__file__).resolve().parents[1]
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
STATE_HOME = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
DEST = CONFIG_HOME / "omarchy/plugins" / ID
LAUNCHER = DATA_HOME / "applications/x1-touch.desktop"
ICON = DATA_HOME / "icons/hicolor/scalable/apps/x1-touch.svg"


def run(*args):
    subprocess.run(args, check=True)


def wait_for_discovery():
    # rescanPlugins queues an asynchronous directory scan in the shell.
    for _ in range(40):
        output = subprocess.check_output(["omarchy", "plugin", "list", "--json"], text=True)
        if any(plugin.get("id") == ID for plugin in json.loads(output)):
            return
        time.sleep(0.2)
    raise RuntimeError("Omarchy did not discover X1 Touch. Try omarchy-shell shell rescanPlugins.")


def desktop_entry():
    return ("[Desktop Entry]\nType=Application\nName=X1 Touch\n"
            "Comment=Manage your fingerprints through fprintd\n"
            "Exec=omarchy-shell shell summon io.github.dandiccf.x1-touch {}\n"
            "Icon=x1-touch\nTerminal=false\nCategories=Settings;HardwareSettings;\n"
            "X-X1-Touch-Owner=io.github.dandiccf.x1-touch\nKeywords=fingerprint;fprintd;biometric;\n")


def launcher_files():
    # Ownership is exact generated content, including a plugin-specific marker.
    return ((ICON, b"<!-- Installed by io.github.dandiccf.x1-touch -->\n" + (SOURCE / "icon.svg").read_bytes()),
            (LAUNCHER, desktop_entry().encode()))


def safe_parents(path):
    return not any(parent.is_symlink() for parent in path.parents)


def read_owned(path, content):
    if not safe_parents(path):
        return False
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return False
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size != len(content):
            return False
        return stream.read() == content


def create_launcher_file(path, content):
    if not safe_parents(path):
        print(f"Preserved path with symlink parent: {path}")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644)
    except FileExistsError:
        if read_owned(path, content):
            return True
        print(f"Preserved existing file (not owned by this installer): {path}")
        return False
    with os.fdopen(fd, "wb") as stream:
        stream.write(content)
    return True


def remove_launcher_files(files=None):
    for path, content in launcher_files() if files is None else files:
        if read_owned(path, content):
            path.unlink()
        elif path.exists() or path.is_symlink():
            print(f"Preserved existing file (not owned by this installer): {path}")


def register_launcher():
    outcomes = [create_launcher_file(path, content) for path, content in launcher_files()]
    if all(outcomes):
        if shutil.which("desktop-file-validate"):
            run("desktop-file-validate", str(LAUNCHER))
        if shutil.which("update-desktop-database"):
            run("update-desktop-database", str(LAUNCHER.parent))


def install():
    if SOURCE == DEST.resolve():
        raise SystemExit("Run this installer from the project checkout, not the installed plugin.")
    run("omarchy", "plugin", "validate", str(SOURCE))
    run("/usr/bin/python", "-c", "from gi.repository import Gio, GLib")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    # Keep staging outside the watched plugin tree. Move only a complete plugin.
    stage_parent = Path(tempfile.mkdtemp(prefix="x1-touch-install-", dir=CONFIG_HOME))
    stage = stage_parent / ID
    backup = None
    try:
        shutil.copytree(SOURCE, stage, ignore=shutil.ignore_patterns(".git", "__pycache__", ".ruff_cache", "test-results"))
        run("omarchy", "plugin", "validate", str(stage))
        if DEST.exists():
            existing = json.loads((DEST / "manifest.json").read_text())
            if existing.get("id") != ID:
                raise SystemExit("Refusing to replace a directory with a different plugin ID.")
            backup = STATE_HOME / "x1-touch/install-backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup.parent.mkdir(parents=True, exist_ok=True)
            DEST.rename(backup)
        try:
            stage.rename(DEST)
        except OSError:
            if backup:
                backup.rename(DEST)
            raise
    finally:
        shutil.rmtree(stage_parent)
    register_launcher()
    run("omarchy-shell", "shell", "rescanPlugins")
    wait_for_discovery()
    run("omarchy", "plugin", "enable", ID)
    print(f"Installed {DEST}\nOpen X1 Touch from your launcher or the fingerprint bar icon.")
    if backup:
        print(f"Previous plugin saved at {backup}")


def uninstall(yes):
    if not yes:
        raise SystemExit("Use uninstall --yes to remove the plugin. Enrollments and preferences are retained.")
    owned_files = launcher_files()
    run("omarchy", "plugin", "disable", ID)
    if DEST.exists():
        if json.loads((DEST / "manifest.json").read_text()).get("id") != ID:
            raise SystemExit("Unexpected plugin ID; no files removed.")
        shutil.rmtree(DEST)
    remove_launcher_files(owned_files)
    run("omarchy-shell", "shell", "rescanPlugins")
    print("Removed X1 Touch. Enrolled fingerprints, authentication and preferences are unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall", "launcher"), default="install", nargs="?")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    if args.action == "install":
        install()
    elif args.action == "launcher":
        register_launcher()
    else:
        uninstall(args.yes)
