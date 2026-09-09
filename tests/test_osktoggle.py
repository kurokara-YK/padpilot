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


class ButtonMapTests(unittest.TestCase):
    """ボタン番号は SDL GameController 順（AGENTS.md §6.2.12）。

    jstest の生の並びと混同して書き換える事故を防ぐ。
    """

    EXPECT = {1: "×", 2: "○", 3: "□", 4: "△",
              5: "SHARE", 6: "PS", 7: "OPTIONS",
              8: "L3", 9: "R3", 10: "L1", 11: "R1"}

    def test_index_matches_sdl_gamecontroller_order(self):
        from core.profile import BUTTON_NAMES
        for idx, word in self.EXPECT.items():
            self.assertIn(word, BUTTON_NAMES[idx],
                          f"index {idx} は {word} のはず")

    def test_all_11_buttons_are_editable(self):
        """すべてのボタンを割り当てられること。"""
        from core.profile import editable_buttons
        self.assertEqual([i for i, _ in editable_buttons()], list(range(1, 12)))

    def test_l2_r2_are_not_buttons(self):
        """L2/R2 はトリガー。ボタン表には入れない。"""
        from core.profile import BUTTON_NAMES
        names = " ".join(BUTTON_NAMES.values())
        self.assertNotIn("L2", names)
        self.assertNotIn("R2", names)

    def test_fixed_rows_cover_sticks_and_triggers(self):
        """変更できない操作も一覧に出す。"""
        from core.profile import FIXED_ROWS
        labels = " ".join(a for a, _ in FIXED_ROWS)
        for w in ("左スティック", "右スティック", "十字キー", "L2", "R2",
                  "タッチパッド"):
            self.assertIn(w, labels)

    def test_button_names_tell_where_they_are(self):
        from core.profile import BUTTON_NAMES
        self.assertIn("左", BUTTON_NAMES[5])
        self.assertIn("右", BUTTON_NAMES[7])


class DefaultProfileTests(unittest.TestCase):
    """既定プロファイルは利用者の原本と一致すること（AGENTS.md §6.2.12）。"""

    ORIGINAL_MD5 = "bd328e091e60e87c1b50580e53882c72"

    def test_shipped_profile_matches_user_original(self):
        import hashlib
        from core import paths
        data = paths.source_profile().read_bytes()
        self.assertEqual(hashlib.md5(data).hexdigest(), self.ORIGINAL_MD5,
                         "profiles/desktop.amgp が原本と違う。勝手に変えない。")

    def test_assignments_match_the_table(self):
        from core import profile
        want = {1: "Enter", 2: "左クリック", 3: "Ctrl + C", 4: "Ctrl + V",
                5: "Esc", 6: "PrintScreen", 7: "Alt + Tab", 8: "Shift",
                9: "右クリック", 10: "Backspace", 11: "Delete"}
        got = profile.bindings_for_set(1)
        for idx, expected in want.items():
            self.assertEqual(got.get(idx), expected, f"index {idx}")

    def test_speeds_match(self):
        from core import profile
        self.assertEqual(profile.get_speeds(1), (60, 15))
        self.assertEqual(profile.get_speeds(2), (175, 40))
        self.assertEqual(profile.get_speeds(3), (20, 5))
