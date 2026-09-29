import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("installer", Path(__file__).resolve().parents[1] / "scripts/install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_waits_for_asynchronous_discovery(self):
        with patch.object(installer.subprocess, "check_output", side_effect=["[]", '[{"id":"io.github.dandiccf.x1-touch"}]']) as check, patch.object(installer.time, "sleep") as sleep:
            installer.wait_for_discovery()
        self.assertEqual(check.call_count, 2)
        sleep.assert_called_once_with(.2)

    def test_discovery_has_bounded_timeout(self):
        with patch.object(installer.subprocess, "check_output", return_value="[]"), patch.object(installer.time, "sleep"), self.assertRaises(RuntimeError):
            installer.wait_for_discovery()

    def test_uninstall_requires_deliberate_flag(self):
        with patch.object(installer, "run") as run, self.assertRaises(SystemExit):
            installer.uninstall(False)
        run.assert_not_called()

    def test_launcher_creation_is_exclusive_and_preserves_foreign_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app.desktop"
            self.assertTrue(installer.create_launcher_file(path, b"owned"))
            self.assertTrue(installer.create_launcher_file(path, b"owned"))
            self.assertFalse(installer.create_launcher_file(path, b"different"))
            self.assertEqual(path.read_bytes(), b"owned")

    def test_launcher_never_follows_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "target"
            target.write_bytes(b"foreign")
            link = root / "app.desktop"
            link.symlink_to(target)
            self.assertFalse(installer.create_launcher_file(link, b"owned"))
            self.assertFalse(installer.read_owned(link, b"foreign"))
            self.assertEqual(target.read_bytes(), b"foreign")
            link.unlink()
            link.symlink_to(root / "absent")
            self.assertFalse(installer.create_launcher_file(link, b"owned"))
            self.assertFalse((root / "absent").exists())
            directory = root / "apps"
            directory.symlink_to(root, target_is_directory=True)
            self.assertFalse(installer.create_launcher_file(directory / "new", b"owned"))
            self.assertFalse((root / "new").exists())

    def test_uninstall_only_removes_exact_owned_regular_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            owned, foreign, link = [root / name for name in ("owned", "foreign", "link")]
            owned.write_bytes(b"ours")
            foreign.write_bytes(b"foreign")
            link.symlink_to(foreign)
            with patch.object(installer, "launcher_files", return_value=((owned, b"ours"), (foreign, b"ours"), (link, b"foreign"))):
                installer.remove_launcher_files()
            self.assertFalse(owned.exists())
            self.assertEqual(foreign.read_bytes(), b"foreign")
            self.assertTrue(link.is_symlink())

    def test_uninstall_from_installed_source_reads_ownership_before_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "plugin"
            source.mkdir()
            (source / "manifest.json").write_text('{"id":"io.github.dandiccf.x1-touch"}')
            (source / "icon.svg").write_text("<svg/>")
            with patch.object(installer, "SOURCE", source), patch.object(installer, "DEST", source), patch.object(installer, "ICON", root / "icon.svg"), patch.object(installer, "LAUNCHER", root / "app.desktop"), patch.object(installer, "run"):
                for path, content in installer.launcher_files():
                    path.write_bytes(content)
                installer.uninstall(True)
                self.assertFalse(source.exists())
                self.assertFalse(installer.ICON.exists())
                self.assertFalse(installer.LAUNCHER.exists())

    def test_launcher_uses_public_plugin_id(self):
        entry = installer.desktop_entry()
        self.assertIn("Exec=omarchy-shell shell summon io.github.dandiccf.x1-touch {}", entry)
        self.assertNotIn("local.x1-touch", entry)


if __name__ == "__main__":
    unittest.main()
