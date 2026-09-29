import importlib.util
from pathlib import Path
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

    def test_launcher_uses_public_plugin_id(self):
        entry = installer.desktop_entry()
        self.assertIn("Exec=omarchy-shell shell summon io.github.dandiccf.x1-touch {}", entry)
        self.assertNotIn("local.x1-touch", entry)


if __name__ == "__main__":
    unittest.main()
