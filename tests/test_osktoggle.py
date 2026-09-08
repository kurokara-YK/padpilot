"""タッチパッド押し込みでの開閉（core/osktoggle.py）の検査。"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import install, osktoggle  # noqa: E402


class ToggleTests(unittest.TestCase):
    def test_autoshow_is_disabled_by_install(self):
        """自動表示は使わない。ターミナルでも出てしまうため。"""
        pairs = [(s, k, v) for s, k, v in _install_settings()]
        self.assertIn(("org.onboard.auto-show", "enabled", "false"), pairs)

    def test_touchpad_is_matched_by_name_not_id(self):
        """id は再接続で変わるので名前で探す。"""
        self.assertTrue(all(h.islower() for h in osktoggle.TOUCHPAD_HINTS))
        self.assertIn("dualsense", osktoggle.TOUCHPAD_HINTS)

    def test_laptop_touchpad_is_not_matched(self):
        """ノート内蔵タッチパッドを誤検出しない。"""
        name = "pnp0c50:00 06cb:cdaa touchpad"
        self.assertFalse(any(h in name for h in osktoggle.TOUCHPAD_HINTS))

    def test_toggle_uses_dbus(self):
        with mock.patch.object(osktoggle, "_dbus", return_value=True) as m:
            self.assertTrue(osktoggle.toggle())
            m.assert_called_once_with("ToggleVisible")

    def test_debounce_is_positive(self):
        self.assertGreater(osktoggle.DEBOUNCE, 0)


def _install_settings():
    """install.enable_onscreen_keyboard が書く設定を取り出す。"""
    captured = []

    def fake_run(cmd, **kw):
        if cmd[:2] == ["gsettings", "set"]:
            captured.append((cmd[2], cmd[3], cmd[4]))
        class R:
            returncode = 0
        return R()

    with mock.patch.object(install.subprocess, "run", side_effect=fake_run), \
         mock.patch.object(install.shutil, "which", return_value="/usr/bin/x"), \
         mock.patch.object(install.paths, "IS_LINUX", True):
        install.enable_onscreen_keyboard()
    return captured


if __name__ == "__main__":
    unittest.main()
