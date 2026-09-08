"""padpilot のメイン画面。

起動/停止、ボタン割り当ての変更、診断をここで行う。
AntiMicroX 本体の GUI は開かない — 分かりにくいため、必要な操作だけを出す。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QMessageBox, QPushButton, QSpinBox,
    QStackedWidget, QTableWidget, QTableWidgetItem,
    QTextEdit, QVBoxLayout,
    QWidget,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gui.widgets import NoScrollComboBox  # noqa: E402
from core import (detect, display, doctor, install, osktoggle,  # noqa: E402
                  paths, profile as profile_mod, runner)


def _card(*widgets) -> QFrame:
    """枠で囲ったまとまり。"""
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 14, 16, 14)
    for w in widgets:
        lay.addWidget(w)
    return f


def _lbl(text: str, obj: str = "") -> QLabel:
    w = QLabel(text)
    w.setWordWrap(True)
    if obj:
        w.setObjectName(obj)
    return w


class HomeTab(QWidget):
    """状態表示と開始/停止。"""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.addWidget(_lbl("padpilot", "Title"))
        lay.addSpacing(12)

        self.card = QFrame()
        self.card.setObjectName("Card")
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(20, 18, 20, 18)
        self.state = _lbl("", "Big")
        self.detail = _lbl("")
        cl.addWidget(self.state)
        cl.addWidget(self.detail)
        lay.addWidget(self.card)
        lay.addSpacing(16)

        row = QHBoxLayout()
        self.toggle = QPushButton()
        self.toggle.setObjectName("Primary")
        self.toggle.setMinimumHeight(44)
        self.toggle.clicked.connect(self._toggle)
        row.addWidget(self.toggle)
        lay.addLayout(row)
        lay.addSpacing(8)
        lay.addWidget(_lbl(
            "コントローラーでパソコンを操作できるようにします。\n"
            "使い終わったら停止してください。", "Subtitle"))
        lay.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        self.refresh()

    def _toggle(self) -> None:
        if runner.is_running():
            runner.stop()
        else:
            try:
                runner.start(hidden=True)
            except FileNotFoundError as e:
                QMessageBox.warning(self, "開始できません", str(e))
        self.refresh()

    def refresh(self) -> None:
        running = runner.is_running()
        pads = detect.find_controllers()
        if running and pads:
            c = pads[0]
            via = "Bluetooth" if c.transport == "bluetooth" else "USB"
            self.card.setObjectName("CardOk")
            self.state.setObjectName("BigOk")
            self.state.setText("● 動作中")
            self.detail.setText(f"{c.name}（{via}）でつながっています。")
        elif running:
            self.card.setObjectName("CardWarn")
            self.state.setObjectName("BigWarn")
            self.state.setText("● コントローラー未接続")
            self.detail.setText("PS ボタンを押すか、USB でつないでください。")
        else:
            self.card.setObjectName("Card")
            self.state.setObjectName("Big")
            self.state.setText("○ 停止中")
            self.detail.setText("「開始する」を押すと使えるようになります。")
        self.toggle.setText("停止する" if running else "開始する")
        for w in (self.card, self.state):
            w.style().unpolish(w)
            w.style().polish(w)


class ComboDialog(QDialog):
    """任意のキーの組み合わせを作る。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("組み合わせを作る")
        self.resize(430, 330)
        lay = QVBoxLayout(self)
        lay.addWidget(_lbl("同時に押すキーを選んでください", "Big"))
        lay.addWidget(_lbl("上から順に押されます。修飾キー（Ctrl など）を先に。",
                           "Subtitle"))
        lay.addSpacing(8)

        self.rows: list[QComboBox] = []
        self.box = QVBoxLayout()
        lay.addLayout(self.box)
        keys = list(profile_mod.KEYS.keys())
        for i in range(4):
            cb = NoScrollComboBox()
            cb.addItem("（なし）")
            cb.addItems(keys)
            if i == 0:
                cb.setCurrentText("Ctrl")
            cb.currentTextChanged.connect(self._update)
            self.box.addWidget(cb)
            self.rows.append(cb)

        lay.addSpacing(8)
        self.preview = _lbl("", "Big")
        lay.addWidget(self.preview)
        lay.addStretch()

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("やめる")
        cancel.clicked.connect(self.reject)
        self.okb = QPushButton("決定")
        self.okb.setObjectName("Primary")
        self.okb.clicked.connect(self.accept)
        row.addWidget(cancel)
        row.addWidget(self.okb)
        lay.addLayout(row)
        self._update()

    def _update(self) -> None:
        self.okb.setEnabled(bool(self.result_label()))
        self.preview.setText(self.result_label() or "キーを選んでください")

    def result_label(self) -> str:
        keys = [cb.currentText() for cb in self.rows
                if cb.currentText() != "（なし）"]
        return profile_mod.make_combo(keys) or ""


class BindingsTab(QWidget):
    """ボタン割り当て・速度の変更。セットごとに設定できる。"""

    CUSTOM = "＋ 組み合わせを作る…"

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(_lbl("ボタンの割り当て", "Title"))

        # セット選択
        top = QHBoxLayout()
        top.addWidget(_lbl("設定するセット:"))
        self.set_box = NoScrollComboBox()
        self.set_box.currentIndexChanged.connect(self._set_changed)
        top.addWidget(self.set_box)
        top.addStretch()
        lay.addLayout(top)
        self.set_note = _lbl("", "Subtitle")
        lay.addWidget(self.set_note)
        lay.addSpacing(6)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["コントローラーの操作", "割り当て"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        lay.addWidget(self.table)

        # 速度
        sp = QHBoxLayout()
        sp.addWidget(_lbl("カーソルの速さ:"))
        self.mouse_sp = QSpinBox()
        self.mouse_sp.setRange(1, 500)
        sp.addWidget(self.mouse_sp)
        sp.addSpacing(14)
        sp.addWidget(_lbl("スクロールの速さ:"))
        self.wheel_sp = QSpinBox()
        self.wheel_sp.setRange(1, 200)
        sp.addWidget(self.wheel_sp)
        sp.addStretch()
        lay.addLayout(sp)
        lay.addSpacing(8)

        row = QHBoxLayout()
        row.addStretch()
        self.reset = QPushButton("最初の設定に戻す")
        self.reset.clicked.connect(self._reset)
        self.save = QPushButton("保存する")
        self.save.setObjectName("Primary")
        self.save.clicked.connect(self._save)
        row.addWidget(self.reset)
        row.addWidget(self.save)
        lay.addLayout(row)
        self.note = _lbl("", "Subtitle")
        lay.addWidget(self.note)

        self.combos: dict[int, QComboBox] = {}
        self.initial: dict[int, str] = {}
        self._loading = False
        self._load_sets()

    def _target(self) -> Path:
        return (paths.profile_path() if paths.profile_path().exists()
                else paths.source_profile())

    def _load_sets(self) -> None:
        self._loading = True
        self.set_box.clear()
        for i, name in profile_mod.set_names(self._target()):
            self.set_box.addItem(f"{i}. {name}", i)
        self._loading = False
        self.reload()

    def _current_set(self) -> int:
        return self.set_box.currentData() or 1

    def _set_changed(self) -> None:
        if not self._loading:
            self.reload()

    def reload(self) -> None:
        target = self._target()
        si = self._current_set()
        notes = {1: "ふだんの状態です。",
                 2: "R2 を押している間だけ、この設定になります。",
                 3: "L2 を押している間だけ、この設定になります。"}
        self.set_note.setText(notes.get(si, ""))

        cur = profile_mod.bindings_for_set(si, target)
        buttons = profile_mod.editable_buttons()
        labels = profile_mod.choice_labels()
        self.table.setRowCount(len(buttons))
        self.combos.clear()
        self.initial = {i: cur.get(i, "割り当てなし") for i, _ in buttons}

        for r, (idx, name) in enumerate(buttons):
            self.table.setItem(r, 0, QTableWidgetItem(name))
            cb = NoScrollComboBox()
            cb.addItems(labels)
            cb.addItem(self.CUSTOM)
            val = self.initial[idx]
            if val in labels:
                cb.setCurrentText(val)
            else:
                cb.insertItem(0, val)
                cb.setCurrentIndex(0)
            cb.activated.connect(
                lambda _i, c=cb, prev=val: self._maybe_custom(c, prev))
            self.table.setCellWidget(r, 1, cb)
            self.combos[idx] = cb

        m, w = profile_mod.get_speeds(si, target)
        self.mouse_sp.setValue(m or 60)
        self.wheel_sp.setValue(w or 15)
        self.init_speeds = (self.mouse_sp.value(), self.wheel_sp.value())

    def _maybe_custom(self, cb: QComboBox, prev: str) -> None:
        """「組み合わせを作る」が選ばれたらダイアログを出す。"""
        if cb.currentText() != self.CUSTOM:
            return
        dlg = ComboDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.result_label():
            label = dlg.result_label()
            if cb.findText(label) < 0:
                cb.insertItem(0, label)
            cb.setCurrentText(label)
        else:
            cb.setCurrentText(prev)

    def _changes(self) -> dict[int, str]:
        return {i: cb.currentText() for i, cb in self.combos.items()
                if cb.currentText() != self.initial.get(i)
                and cb.currentText() != self.CUSTOM}

    def _save(self) -> None:
        changes = self._changes()
        speeds = (self.mouse_sp.value(), self.wheel_sp.value())
        if not changes and speeds == self.init_speeds:
            self.note.setText("変更はありません。")
            return
        si = self._current_set()
        dst = paths.profile_path()
        try:
            base = self._target()
            if changes:
                profile_mod.apply_set_bindings(si, changes, base, dst)
                base = dst
            if speeds != self.init_speeds:
                profile_mod.set_speeds_for(si, speeds[0], speeds[1], base, dst)
            install._set_customized(True)
        except Exception as e:
            QMessageBox.warning(self, "保存できません", str(e))
            return
        was = runner.is_running()
        if was:
            # プロファイルは起動時に読まれるので、反映には再起動が要る
            runner.stop()
            runner.start(hidden=True)
        self.reload()
        self.note.setText(
            "保存しました。" + ("すぐに反映されます。" if was
                               else "開始すると反映されます。"))

    def _reset(self) -> None:
        if QMessageBox.question(
                self, "確認",
                "すべてのセットを最初の設定に戻しますか？") != QMessageBox.Yes:
            return
        install.install_profile()
        if runner.is_running():
            runner.stop()
            runner.start(hidden=True)
        self._load_sets()
        self.note.setText("最初の設定に戻しました。")


class KeyboardTab(QWidget):
    """画面キーボードの設定。"""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.addWidget(_lbl("画面キーボード", "Title"))
        lay.addWidget(_lbl(
            "入力欄をクリックすると出てくるキーボードの設定です。", "Subtitle"))
        lay.addSpacing(14)

        lay.addWidget(_lbl("どの画面に出すか", "Section"))
        lay.addWidget(_lbl(
            "画面が複数あるときは、よく使う画面を選んでください。", "Subtitle"))
        row = QHBoxLayout()
        self.mon = NoScrollComboBox()
        self.mon.setMinimumWidth(300)
        row.addWidget(self.mon)
        row.addStretch()
        lay.addLayout(row)
        lay.addSpacing(6)

        warn = _lbl(
            "表示先を固定すると、毎回同じ画面でキーボードを操作できます。",
            "Subtitle")
        lay.addWidget(warn)
        lay.addSpacing(16)

        lay.addWidget(_lbl("使いかた", "Section"))
        lay.addWidget(_card(_lbl(
            "出すとき   … コントローラーのタッチパッドを押し込む\n\n"
            "閉じるとき … もう一度タッチパッドを押し込む\n"
            "             または、キーボード右上の × を押す\n\n"
            "※ 入力欄をクリックしただけでは出ません。\n"
            "   ターミナルなどで勝手に出ないようにするためです。")))
        lay.addStretch()

        row2 = QHBoxLayout()
        row2.addStretch()
        self.test = QPushButton("試しに出してみる")
        self.test.clicked.connect(self._test)
        self.save = QPushButton("保存する")
        self.save.setObjectName("Primary")
        self.save.clicked.connect(self._save)
        row2.addWidget(self.test)
        row2.addWidget(self.save)
        lay.addLayout(row2)
        self.note = _lbl("", "Subtitle")
        lay.addWidget(self.note)
        self.reload()

    def reload(self) -> None:
        self.mon.clear()
        cur = display.keyboard_monitor()
        for value, label in display.monitor_choices():
            self.mon.addItem(label, value)
        idx = self.mon.findData(cur)
        if idx >= 0:
            self.mon.setCurrentIndex(idx)
        elif cur == "active":
            self.mon.insertItem(0, "動いている画面",
                                "active")
            self.mon.setCurrentIndex(0)

    def _save(self) -> None:
        value = self.mon.currentData()
        ok = display.set_keyboard_monitor(value)
        self.note.setText("保存しました。" if ok else "保存できませんでした。")
        self.reload()

    def _test(self) -> None:
        import subprocess
        try:
            if not osktoggle.toggle():
                subprocess.Popen(["onboard"], start_new_session=True)
            self.note.setText(
                "切り替えました。タッチパッド押し込みでも開閉できます。")
        except OSError:
            self.note.setText("onboard が見つかりません。")


class _DoctorWorker(QThread):
    finished_ = Signal(list)

    def run(self) -> None:
        self.finished_.emit(doctor.check())


class DoctorTab(QWidget):
    """調子が悪いときの点検。"""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.addWidget(_lbl("調子を確認する", "Title"))
        lay.addWidget(_lbl(
            "うまく動かないときに，原因を調べて直します。", "Subtitle"))
        lay.addSpacing(10)

        self.out = QTextEdit()
        self.out.setReadOnly(True)
        lay.addWidget(self.out)

        row = QHBoxLayout()
        row.addStretch()
        self.check_btn = QPushButton("調べる")
        self.check_btn.setObjectName("Primary")
        self.check_btn.clicked.connect(self.run_check)
        self.fix_btn = QPushButton("見つかった問題を直す")
        self.fix_btn.setEnabled(False)
        self.fix_btn.clicked.connect(self._fix)
        row.addWidget(self.check_btn)
        row.addWidget(self.fix_btn)
        lay.addLayout(row)
        self.problems: list = []
        self.worker: _DoctorWorker | None = None

    def run_check(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return          # 二重起動を防ぐ
        self.out.setPlainText("調べています…")
        self.check_btn.setEnabled(False)
        self.worker = _DoctorWorker()
        self.worker.finished_.connect(self._show)
        self.worker.start()

    def stop_worker(self) -> None:
        """実行中の点検を待って片付ける。

        待たずにウィンドウを壊すと
        "QThread: Destroyed while thread is still running" で落ちる。
        """
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(5000)

    def _show(self, problems: list) -> None:
        self.problems = problems
        self.check_btn.setEnabled(True)
        if not problems:
            self.out.setPlainText("✅ 問題は見つかりませんでした。\n\n"
                                  "正常に動作しています。")
            self.fix_btn.setEnabled(False)
            return
        lines = []
        for p in problems:
            mark = "🔴" if p.severity == "error" else "🟡"
            lines.append(f"{mark} {p.message}")
            for l in p.detail.splitlines():
                lines.append(f"    {l}")
            if p.fixable:
                lines.append("    → この問題は自動で直せます")
            lines.append("")
        self.out.setPlainText("\n".join(lines))
        self.fix_btn.setEnabled(any(p.fixable for p in problems))

    def _fix(self) -> None:
        done = 0
        for p in self.problems:
            if p.fixable:
                try:
                    p.fix()
                    done += 1
                except Exception:
                    pass
        self.out.append(f"\n{done} 件を直しました。もう一度調べます…")
        self.run_check()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("padpilot")
        self.resize(720, 600)

        central = QWidget()
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # 左のサイドバー (Discord 風)
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(190)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(10, 18, 10, 18)
        sl.setSpacing(6)

        self.stack = QStackedWidget()
        self.tabs = {}
        for name, widget in (("ホーム", HomeTab()),
                             ("ボタンの割り当て", BindingsTab()),
                             ("画面キーボード", KeyboardTab()),
                             ("調子を確認する", DoctorTab())):
            btn = QPushButton(name)
            btn.setObjectName("NavItem")
            btn.setCheckable(True)
            btn.setMinimumHeight(38)
            idx = self.stack.count()
            btn.clicked.connect(lambda _, i=idx: self._select(i))
            sl.addWidget(btn)
            self.stack.addWidget(widget)
            self.tabs[idx] = btn
        sl.addStretch()

        quit_btn = QPushButton("終了")
        quit_btn.clicked.connect(self.close)
        sl.addWidget(quit_btn)

        outer.addWidget(side)
        outer.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self._select(0)

    def _select(self, i: int) -> None:
        self.stack.setCurrentIndex(i)
        for idx, btn in self.tabs.items():
            btn.setChecked(idx == i)

    def closeEvent(self, event) -> None:
        # 走っているスレッドを待ってから閉じる
        for i in range(self.stack.count()):
            w = self.stack.widget(i)
            if hasattr(w, "stop_worker"):
                w.stop_worker()
            if hasattr(w, "timer"):
                w.timer.stop()
        super().closeEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    qss = Path(__file__).resolve().parent / "style.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
