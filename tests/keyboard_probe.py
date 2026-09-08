"""X11 desktop probe. Uses owned test windows and exact widget coordinates.

python3 tests/keyboard_probe.py --backend qt
python3 tests/keyboard_probe.py --backend onboard --event-source GTK
Results/logs go to a fresh /tmp/padpilot-probe-* directory. No persistent
onboard settings are changed (GSettings memory backend). Do not use the
mouse/keyboard during the short run. Only spawned children are terminated.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import signal
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def save(path, data):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False))
    tmp.replace(path)


def worker(args):
    state = Path(args.directory) / (args.worker + '.json')
    if args.worker == 'target' and args.target == 'chrome':
        os.execlp('node', 'node', str(ROOT / 'tests/browser_target.mjs'), args.directory)
    if args.worker == 'target':
        import gi
        gi.require_version('Gtk', '3.0')
        gi.require_version('GdkX11', '3.0')
        from gi.repository import Gtk, GLib, GdkX11  # noqa: F401
        win = Gtk.Window(title='PADPILOT PROBE INPUT')
        entry = Gtk.Entry()
        activations = []
        entry.connect('activate', lambda e: activations.append(e.get_text()))
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outside = Gtk.Button(label='Non-text focus target')
        box.pack_start(entry, True, True, 0)
        box.pack_start(outside, True, True, 0)
        win.add(box)
        win.set_default_size(500, 90)
        win.move(100, 200)
        win.connect('destroy', Gtk.main_quit)
        win.show_all()
        entry.grab_focus()
        win.present()
        resets = 0
        focus_command = ''
        def snapshot():
            nonlocal resets, focus_command
            control = state.parent / 'reset'
            if control.exists() and int(control.read_text()) != resets:
                resets = int(control.read_text())
                entry.reset_im_context()
                entry.set_text('')
            focus_file = state.parent / 'focus'
            if focus_file.exists() and focus_file.read_text() != focus_command:
                focus_command = focus_file.read_text()
                (entry if focus_command == 'entry' else outside).grab_focus()
            save(state, dict(wid=GdkX11.X11Window.get_xid(win.get_window()),
                             text=entry.get_text(), reset=resets,
                             activations=activations, focus=focus_command))
            return True
        GLib.timeout_add(50, snapshot)
        Gtk.main()
    elif args.worker == 'qt':
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication, QPushButton
        from gui.keyboard import OnScreenKeyboard
        from core import keysend
        app = QApplication([])
        app.setStyleSheet((ROOT / 'gui/style.qss').read_text())
        sent = []
        original = keysend.send_key
        def send(k):
            ok = original(k)
            sent.append([k, ok])
            return ok
        keysend.send_key = send
        win = OnScreenKeyboard()
        win.place_bottom()
        win.show()
        def snapshot():
            keys = {}
            for b in win.findChildren(QPushButton):
                k = b.property('keysym')
                if k:
                    pt = b.mapToGlobal(b.rect().center())
                    keys[k] = [pt.x(), pt.y()]
            save(state, dict(wid=int(win.winId()), keys=keys, sent=sent))
        timer = QTimer()
        timer.timeout.connect(snapshot)
        timer.start(50)
        app.exec()
    else:
        # Per-process settings; no dconf writes or changes to installed source.
        os.environ['GSETTINGS_BACKEND'] = 'memory'
        import gi
        gi.require_version('Gtk', '3.0')
        from gi.repository import Gio, GLib
        for schema, key, value in [
            ('org.gnome.desktop.interface', 'toolkit-accessibility', args.auto_show),
            ('org.onboard.keyboard', 'input-event-source', args.event_source),
            ('org.onboard.auto-show', 'enabled', args.auto_show),
            ('org.onboard.auto-show', 'hide-on-key-press', args.hide_on_key_press),
            ('org.onboard.auto-show', 'tablet-mode-detection-enabled', args.tablet_detection),
            ('org.onboard.keyboard', 'touch-input', args.touch_input),
            ('org.onboard.window', 'docking-enabled', args.auto_show),
            ('org.onboard.window', 'docking-monitor', args.monitor),
        ]:
            s = Gio.Settings.new(schema)
            if isinstance(value, bool):
                s.set_boolean(key, value)
            else:
                s.set_string(key, value)
        sys.argv = ['onboard', '--allow-multiple-instances', '-x', '900', '-y', '600', '-s', '900x300']
        from Onboard.OnboardGtk import OnboardGtk
        class ProbeOnboard(OnboardGtk):
            def init(self):
                super().init()
                def snapshot():
                    keys = {}
                    for k in self.keyboard.iter_keys():
                        r = self.keyboard_widget.get_key_screen_rect(k)
                        if r and k.is_visible():
                            keys[k.id] = dict(xy=[int(r.x+r.w/2), int(r.y+r.h/2)],
                                              label=k.label)
                    save(state, dict(wid=self._window.get_window().get_xid(), keys=keys,
                                     visible=bool(self._window.get_mapped()
                                                  and self._window.is_visible()
                                                  and self._window.get_opacity() > .1),
                                     opacity=self._window.get_opacity()))
                    return True
                GLib.timeout_add(100, snapshot)
        ProbeOnboard()


def run(args):
    from Xlib import display, X
    from Xlib.ext import xtest
    from core import keysend
    d = display.Display()
    root = d.screen().root
    old_pointer = root.query_pointer()
    old_focus = d.get_input_focus().focus
    directory = Path(tempfile.mkdtemp(prefix='padpilot-probe-'))
    print('ARTIFACTS', directory, flush=True)
    children, logs = [], []
    results = []
    def launch(kind):
        log = (directory / (kind + '.log')).open('w')
        logs.append(log)
        env = dict(os.environ)
        if kind == 'target' and not args.japanese:
            env['GTK_IM_MODULE'] = 'gtk-im-context-simple'
        command = [sys.executable, str(Path(__file__).resolve()),
                   '--worker', kind, '--directory', str(directory),
                   '--event-source', args.event_source, '--monitor', args.monitor,
                   '--touch-input', args.touch_input, '--target', args.target]
        if args.auto_show:
            command.append('--auto-show')
        if args.hide_on_key_press:
            command.append('--hide-on-key-press')
        if args.tablet_detection:
            command.append('--tablet-detection')
        if args.gdb and kind == 'onboard':
            command = ['gdb', '-q', '-batch', '-ex', 'set debuginfod enabled off',
                       '-ex', 'run', '-ex', 'bt 20', '--args'] + command
        p = subprocess.Popen(command, env=env, stdout=log, stderr=log,
                             start_new_session=True)
        children.append(p)
        return p
    def read(kind):
        return json.loads((directory / (kind + '.json')).read_text())
    def wait_for(fn, timeout=25):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            try:
                value = fn()
                if value:
                    return value
            except (FileNotFoundError, json.JSONDecodeError):
                pass
            time.sleep(.05)
        raise RuntimeError('Timeout waiting for probe state')
    def focused():
        f = d.get_input_focus().focus
        while hasattr(f, 'id'):
            if f.id == target['wid']:
                return True
            if f.id == root.id:
                return False
            f = f.query_tree().parent
        return False
    def check_focus():
        if not focused():
            raise RuntimeError('Input focus left the owned target; aborting input')
    def record(name, **kw):
        row = dict(step=name, focus_ok=focused(), **kw)
        results.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
        save(directory / 'results.json', results)
    try:
        launch('target')
        target = wait_for(lambda: read('target'))
        wait_for(focused)
        if args.japanese:
            check_focus()
            assert keysend.send_key('Henkan')
            time.sleep(.5)
        control_keys = list('aiueo') + ['Return'] if args.japanese else list('asd')
        for k in control_keys:
            check_focus()
            assert keysend.send_key(k)
            time.sleep(.12)
        time.sleep(.4)
        control_text = read('target')['text']
        record('direct_without_QApplication', text=control_text)
        if args.japanese and control_text == 'aiueo':
            check_focus()
            assert keysend.send_key('Zenkaku_Hankaku')
            time.sleep(.4)
            save(directory / 'reset', -1)
            wait_for(lambda: read('target')['reset'] == -1)
            for k in control_keys:
                check_focus()
                assert keysend.send_key(k)
                time.sleep(.15)
            time.sleep(.4)
            control_text = read('target')['text']
            record('direct_after_IME_on', text=control_text)
        if control_text != ('あいうえお' if args.japanese else 'asd'):
            raise RuntimeError('Direct control failed; check IME mode before testing the keyboard')
        save(directory / 'reset', 1)
        wait_for(lambda: read('target')['reset'] == 1)
        p = launch(args.backend)
        keyboard = wait_for(lambda: read(args.backend))
        time.sleep(1)
        if args.auto_show:
            (directory / 'focus').write_text('outside')
            wait_for(lambda: read('target')['focus'] == 'outside')
            wait_for(lambda: not read(args.backend)['visible'])
            record('auto_hidden', alive=p.poll() is None)
            (directory / 'focus').write_text('entry')
            wait_for(lambda: read('target')['focus'] == 'entry')
            wait_for(lambda: read(args.backend)['visible'])
            record('auto_shown', alive=p.poll() is None)
            time.sleep(1)
            check_focus()
            assert keysend.send_key('space')
            time.sleep(2)
            record('after_external_key', visible=read(args.backend)['visible'],
                   alive=p.poll() is None)
            save(directory / 'reset', 2)
            wait_for(lambda: read('target')['reset'] == 2)
        record('shown', alive=p.poll() is None, wid=keyboard['wid'])
        keyboard = read(args.backend)
        for label in args.keys.split(','):
            if args.backend == 'qt':
                xy = keyboard['keys'][label]
            else:
                key_id = {'BackSpace': 'BKSP', 'Return': 'RTRN', 'space': 'SPCE',
                          'Zenkaku_Hankaku': 'TLDE'}.get(label)
                xy = (keyboard['keys'][key_id]['xy'] if key_id else
                      next(v['xy'] for v in keyboard['keys'].values() if v['label'] == label))
            check_focus()
            root.warp_pointer(*xy)
            d.sync()
            time.sleep(.8)
            record('hover_' + label, alive=p.poll() is None, exit_code=p.poll(), xy=xy)
            if p.poll() is not None:
                break
            # Confirm the pointer is over the exact owned window before clicking.
            w = root
            while hasattr(w, 'id') and w.id != keyboard['wid']:
                w = w.query_pointer().child
            if not hasattr(w, 'id') or w.id != keyboard['wid']:
                pointer = root.query_pointer()
                record('pointer_target_mismatch',
                       pointer_xy=[pointer.root_x, pointer.root_y], expected_xy=xy,
                       keyboard_visible=read(args.backend).get('visible'))
                raise RuntimeError('Pointer is not over the owned keyboard')
            check_focus()
            xtest.fake_input(d, X.ButtonPress, 1)
            d.sync()
            time.sleep(.08)
            xtest.fake_input(d, X.ButtonRelease, 1)
            d.sync()
            time.sleep(.4)
            record('click_' + label, alive=p.poll() is None, text=read('target')['text'])
            if p.poll() is not None:
                break
        actual = read('target')['text']
        passed = actual == args.expected and focused() and p.poll() is None
        record('result', text=actual, passed=passed, exit_code=p.poll(),
               activations=read('target')['activations'])
        if args.backend == 'qt':
            record('send_results', sent=read('qt')['sent'])
        if args.auto_show:
            # Query actual monitors; move only, never click other applications.
            monitors = subprocess.run(['xrandr', '--listmonitors'], check=True,
                                      capture_output=True, text=True).stdout
            points = [(int(x)+50, int(y)+50) for x, y in
                      re.findall(r'\d+/\d+x\d+/\d+([+-]\d+)([+-]\d+)', monitors)]
            for xy in points + points[:1]:
                root.warp_pointer(*xy)
                d.sync()
                time.sleep(2)
                visible = read(args.backend)['visible']
                record('monitor_crossing', xy=xy, visible=visible, alive=p.poll() is None)
                passed = passed and visible and p.poll() is None
        record('final', passed=passed)
        return 0 if passed else 1
    except Exception as exc:
        save(directory / 'error.json', dict(error=str(exc),
                                            child_exit_codes=[p.poll() for p in children]))
        raise
    finally:
        for p in reversed(children):
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait()
        for log in logs:
            log.close()
        root.warp_pointer(old_pointer.root_x, old_pointer.root_y)
        try:
            if hasattr(old_focus, 'set_input_focus'):
                old_focus.set_input_focus(X.RevertToParent, X.CurrentTime)
            d.sync()
        finally:
            d.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=['qt', 'onboard'], default='qt')
    parser.add_argument('--event-source', choices=['GTK', 'XInput'], default='XInput')
    parser.add_argument('--worker', choices=['target', 'qt', 'onboard'])
    parser.add_argument('--directory')
    parser.add_argument('--japanese', action='store_true')
    parser.add_argument('--keys', default='a,s,d')
    parser.add_argument('--expected', default='asd')
    parser.add_argument('--gdb', action='store_true')
    parser.add_argument('--auto-show', action='store_true')
    parser.add_argument('--monitor', default='primary')
    parser.add_argument('--touch-input', choices=['multi', 'single', 'none'], default='multi')
    parser.add_argument('--hide-on-key-press', action='store_true')
    parser.add_argument('--tablet-detection', action='store_true')
    parser.add_argument('--target', choices=['gtk', 'chrome'], default='gtk')
    args = parser.parse_args()
    if args.worker:
        worker(args)
    else:
        sys.exit(run(args))
