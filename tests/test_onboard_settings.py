"""Regression: working auto-show settings must not hide the XInput crash risk."""
import subprocess
import unittest
from unittest.mock import patch

from core import doctor, install


class OnboardSettingsTests(unittest.TestCase):
    def problems(self, source, monitor="'primary'"):
        settings = {
            'input-event-source': source,
            'toolkit-accessibility': 'true',
            'enabled': 'false',
            'hide-on-key-press': 'false',
            'tablet-mode-detection-enabled': 'false',
            'docking-monitor': monitor,
        }
        with (patch.object(doctor, '_gsettings_get', side_effect=lambda s, k: settings.get(k)),
              patch.object(doctor.shutil, 'which', return_value='/test/onboard'),
              patch.object(doctor.paths, 'IS_LINUX', True),
              patch.object(doctor.detect, 'find_controllers', return_value=[object()]),
              patch.object(doctor.detect, 'antimicrox_version', return_value=None),
              patch.object(doctor.detect, 'session_type', return_value='x11'),
              patch.object(doctor, '_pgrep_exact', return_value=False),
              patch('core.runner.is_running', return_value=True)):
            return doctor.check()

    def test_xinput_detected_even_when_autoshow_is_healthy(self):
        problem = next(p for p in self.problems("'XInput'") if p.id == 'onboard_xinput')
        with patch.object(doctor.subprocess, 'run') as run:
            problem.fix()
        self.assertEqual(run.call_args.args[0], [
            'gsettings', 'set', 'org.onboard.keyboard', 'input-event-source', 'GTK'])
        self.assertTrue(run.call_args.kwargs['check'])

    def test_gtk_and_unreadable_setting_are_not_reported_as_xinput(self):
        for source in ("'GTK'", None):
            with self.subTest(source=source):
                self.assertNotIn('onboard_xinput', [p.id for p in self.problems(source)])

    def test_active_monitor_is_not_misdiagnosed_as_disabled_autoshow(self):
        self.assertNotIn('a11y_disabled', [p.id for p in self.problems("'GTK'", "'active'")])
        with patch.object(doctor, '_gsettings_set') as set_value:
            doctor._enable_a11y()
        self.assertNotIn('docking-monitor', [c.args[1] for c in set_value.call_args_list])

    def test_install_failure_on_input_setting_is_not_reported_as_success(self):
        def result(command, **kwargs):
            code = 1 if command[3] == 'input-event-source' else 0
            return subprocess.CompletedProcess(command, code)
        with (patch.object(install.paths, 'IS_LINUX', True),
              patch.object(install.shutil, 'which', return_value='/test/gsettings'),
              patch.object(install.subprocess, 'run', side_effect=result)):
            self.assertFalse(install.enable_onscreen_keyboard())

    def test_install_and_uninstall_cover_the_new_setting(self):
        with (patch.object(install.paths, 'IS_LINUX', True),
              patch.object(install.shutil, 'which', return_value='/test/gsettings'),
              patch.object(install.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run):
            self.assertTrue(install.enable_onscreen_keyboard())
            install._restore_onscreen_keyboard()
        commands = [c.args[0] for c in run.call_args_list]
        self.assertIn(['gsettings', 'set', 'org.onboard.keyboard', 'input-event-source', 'GTK'], commands)
        self.assertIn(['gsettings', 'reset', 'org.onboard.keyboard', 'input-event-source'], commands)


if __name__ == '__main__':
    unittest.main()
