"""セットアップウィザード (AGENTS.md §6.2.1)。

Windows のインストーラーと同じ流れ。実処理は core が持つ。
ここは画面と進行だけ (§7.1)。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QProgressBar, QPushButton, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWizard, QWizardPage,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gui.widgets import NoScrollComboBox  # noqa: E402
from core import detect, install, paths, profile as profile_mod, runner  # noqa: E402


def _title(text: str) -> QLabel:
    lb = QLabel(text)
    lb.setObjectName("Title")
    lb.setWordWrap(True)
    return lb


def _body(text: str, obj: str = "") -> QLabel:
    lb = QLabel(text)
    lb.setWordWrap(True)
    if obj:
        lb.setObjectName(obj)
    return lb


def _card(*widgets) -> QFrame:
    f = QFrame()
    f.setObjectName("Card")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(16, 14, 16, 14)
    for w in widgets:
        lay.addWidget(w)
    return f


class WelcomePage(QWizardPage):
    """ようこそ。何が起きるかを先に示す。"""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(_title("padpilot セットアップ"))
        lay.addWidget(_body(
            "ゲームパッドで、パソコンのマウスとキーボードの代わりができるようになります。\n"
            "PS5 / PS4 / Xbox のコントローラーに対応しています。"))
        lay.addSpacing(16)

        lay.addWidget(_body("このセットアップですること", "Section"))
        lay.addWidget(_card(_body(
            "1.  必要なソフト（AntiMicroX）を公式サイトから取り込みます\n\n"
            "2.  ボタンの割り当てを設定します\n\n"
            "3.  文字を入力できるようにします\n\n"
            "4.  アプリの一覧に登録します")))
        lay.addSpacing(12)
        lay.addWidget(_body(
            "パスワードの入力は必要ありません。\n"
            "あとから削除すれば、元どおりに戻せます。", "Subtitle"))
        lay.addStretch()


class ConnectPage(QWizardPage):
    """コントローラーの接続確認。

    接続済みでも「確認しました」を必ず見せる。未接続なら繋ぎ方を案内し、
    繋がった瞬間に自動で表示が変わる。
    """

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(_title("コントローラーの確認"))
        lay.addWidget(_body("コントローラーがパソコンとつながっているか調べます。"))
        lay.addSpacing(14)

        self.card = QFrame()
        self.card.setObjectName("Card")
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(18, 16, 18, 16)
        self.status = QLabel()
        self.status.setObjectName("Big")
        self.status.setWordWrap(True)
        self.detail = QLabel()
        self.detail.setWordWrap(True)
        cl.addWidget(self.status)
        cl.addWidget(self.detail)
        lay.addWidget(self.card)
        lay.addSpacing(12)

        self.help = _body("", "Subtitle")
        lay.addWidget(self.help)
        lay.addStretch()

        self.skip = QCheckBox("接続しないで先に進む")
        self.skip.stateChanged.connect(lambda _: self.completeChanged.emit())
        lay.addWidget(self.skip)

        self._found = False
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)

    def initializePage(self) -> None:
        self._refresh()
        # 抜き差しは通知が来ないのでポーリングする (AGENTS.md §7.3)
        self.timer.start(1500)

    def cleanupPage(self) -> None:
        self.timer.stop()

    def _refresh(self) -> None:
        controllers = detect.find_controllers()
        was = self._found
        self._found = bool(controllers)

        if controllers:
            c = controllers[0]
            via = "Bluetooth" if c.transport == "bluetooth" else "USB ケーブル"
            self.card.setObjectName("CardOk")
            self.status.setObjectName("BigOk")
            self.status.setText("✅  接続を確認しました")
            extra = ""
            if c.touchpad_is_pointer:
                extra = "\nタッチパッドを指でなぞるとカーソルが動きます。"
            self.detail.setText(f"{c.name}\n{via} でつながっています。{extra}")
            self.help.setText("")
            self.skip.setVisible(False)
        else:
            self.card.setObjectName("CardWarn")
            self.status.setObjectName("BigWarn")
            self.status.setText("⚠️  つながっていません")
            self.detail.setText("コントローラーが見つかりませんでした。")
            self.help.setText(
                "つなぎ方\n\n"
                "  ● Bluetooth の場合\n"
                "      コントローラーの PS ボタン と Create ボタン（左上の小さいボタン）を\n"
                "      同時に長押しします。ライトが速く点滅したら、\n"
                "      パソコンの「設定 → Bluetooth」から選んでください。\n\n"
                "  ● USB ケーブルの場合\n"
                "      ケーブルでパソコンとつなぐだけです。こちらが確実です。\n\n"
                "つながると、この画面は自動で切り替わります。")
            self.skip.setVisible(True)

        # スタイルを付け直す (objectName を変えたため)
        for w in (self.card, self.status):
            w.style().unpolish(w)
            w.style().polish(w)

        if was != self._found:
            self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._found or self.skip.isChecked()


class OptionsPage(QWizardPage):
    """Windows で言う「ショートカットを作りますか」の画面。"""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(_title("セットアップの内容"))
        lay.addWidget(_body("必要なものを選んでください。"))
        lay.addSpacing(12)

        self.cb_launcher = QCheckBox("アプリの一覧に追加する")
        self.cb_launcher.setChecked(True)
        self.cb_osk = QCheckBox("文字を入力できるようにする（画面キーボード）")
        self.cb_osk.setChecked(True)
        self.cb_autostart = QCheckBox("パソコンを起動したら自動ではじめる")
        self.cb_autostart.setChecked(False)

        for cb, note in (
            (self.cb_launcher, "アプリ一覧から padpilot を開けるようになります"),
            (self.cb_osk, "入力欄をクリックすると、画面にキーボードが出ます"),
            (self.cb_autostart,
             "電源を入れるたびに、自分で起動する手間がなくなります"),
        ):
            lay.addWidget(cb)
            n = _body(f"        {note}", "Subtitle")
            lay.addWidget(n)
            lay.addSpacing(4)

        # 旧構成がある場合だけ出す。無いなら項目自体を隠す
        self.cb_legacy = QCheckBox("以前の設定を削除する")
        legacy = install.find_legacy()
        self.cb_legacy.setChecked(bool(legacy))
        self.cb_legacy.setVisible(bool(legacy))
        lay.addWidget(self.cb_legacy)
        if legacy:
            lay.addWidget(_body(
                f"        以前に手動で入れたものが {len(legacy)} 件残っています。"
                "そのままだと二重に動いてしまいます。", "Subtitle"))

        lay.addSpacing(14)
        lay.addWidget(_body(
            f"保存先: {paths.bin_dir()}", "Subtitle"))
        lay.addStretch()

        self.registerField("launcher", self.cb_launcher)
        self.registerField("osk", self.cb_osk)
        self.registerField("autostart", self.cb_autostart)
        self.registerField("legacy", self.cb_legacy)


class ProfilePage(QWizardPage):
    """ボタンの割り当て。クリックで選び直せる。"""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(_title("ボタンの割り当て"))
        lay.addWidget(_body(
            "右側をクリックすると変更できます。このままでも構いません。"))
        lay.addSpacing(10)

        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["コントローラーの操作", "割り当て"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch)
        lay.addWidget(self.table)

        lay.addWidget(_body(
            "スティックと十字キーは固定です（左＝カーソル移動 / 右＝スクロール）。\n"
            "R2 を押している間は速く、L2 を押している間はゆっくり動きます。",
            "Subtitle"))
        self.combos: dict[int, QComboBox] = {}
        self.initial: dict[int, str] = {}

    def initializePage(self) -> None:
        buttons = profile_mod.editable_buttons()
        labels = profile_mod.choice_labels()
        self.table.setRowCount(len(buttons))
        self.combos.clear()
        # 現在値は一度だけ読む。changes() で読み直すとディスクアクセスが増え、
        # かつ導入後に読むと「変更なし」と誤判定する
        self.initial = {idx: profile_mod.current_label(idx)
                        for idx, _ in buttons}

        for row, (idx, name) in enumerate(buttons):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            cb = NoScrollComboBox()
            cb.addItems(labels)
            cur = self.initial[idx]
            if cur in labels:
                cb.setCurrentText(cur)
            else:
                # 既定に無い組み合わせは選択肢として足す
                cb.insertItem(0, cur)
                cb.setCurrentIndex(0)
            self.table.setCellWidget(row, 1, cb)
            self.combos[idx] = cb

    def changes(self) -> dict[int, str]:
        """既定から変更されたものだけ返す。"""
        return {idx: cb.currentText() for idx, cb in self.combos.items()
                if cb.currentText() != self.initial.get(idx)}


class _Worker(QThread):
    """導入をバックグラウンドで走らせる。GUI を固めないため。"""
    line = Signal(str)
    done = Signal(bool, str)

    def __init__(self, opts: dict, changes: dict):
        super().__init__()
        self.opts = opts
        self.changes = changes

    def run(self) -> None:
        try:
            if self.opts.get("legacy"):
                install._kill_all_antimicrox()
                install.remove_legacy(self.line.emit)
            install.download_antimicrox(self.line.emit)
            install.install_profile(self.line.emit, changes=self.changes)
            if self.opts.get("osk"):
                install.enable_onscreen_keyboard(self.line.emit)
            if self.opts.get("launcher"):
                install.install_launcher(self.line.emit)
            if self.opts.get("autostart"):
                install.enable_autostart(self.line.emit)
            issues = install.verify(allow_edited=bool(self.changes))
            self.done.emit(not issues, "\n".join(issues))
        except Exception as e:
            self.done.emit(False, str(e))


class ProgressPage(QWizardPage):
    """導入の実行。"""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(_title("セットアップしています"))
        lay.addWidget(_body("しばらくお待ちください。"))
        lay.addSpacing(10)
        self.bar = QProgressBar()
        self.bar.setRange(0, 0)      # 不定。段数を偽らない
        self.bar.setTextVisible(False)
        lay.addWidget(self.bar)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log)

        row = QHBoxLayout()
        row.addStretch()
        self.retry = QPushButton("もう一度試す")
        self.retry.setObjectName("Primary")
        self.retry.setVisible(False)
        self.retry.clicked.connect(self.initializePage)
        row.addWidget(self.retry)
        lay.addLayout(row)

        self._done = False
        self._ok = False
        self.worker: _Worker | None = None

    def initializePage(self) -> None:
        self._done = False
        self._ok = False
        self.retry.setVisible(False)
        self.log.clear()
        self.bar.setRange(0, 0)
        opts = {k: bool(self.field(k))
                for k in ("launcher", "osk", "autostart", "legacy")}
        wiz = self.wizard()
        changes = wiz.profile_page.changes() if wiz.profile_page else {}
        if changes:
            self.log.append(f"割り当てを {len(changes)} 件変更します")
        self.worker = _Worker(opts, changes)
        self.worker.line.connect(self.log.append)
        self.worker.done.connect(self._finish)
        self.worker.start()

    def _finish(self, ok: bool, err: str) -> None:
        self._done = True
        self._ok = ok
        self.bar.setRange(0, 1)
        self.bar.setValue(1)
        self.wizard().installed_ok = ok
        if ok:
            self.log.append("\n✅ セットアップが終わりました。")
        else:
            self.log.append(f"\n❌ うまくいきませんでした\n\n{err}")
            # 失敗したまま先へ進ませない。やり直せるようにする。
            self.retry.setVisible(True)
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        # 失敗時は「次へ」を無効にする。進んでも壊れた状態になるだけ。
        return self._done and self._ok


class TestPage(QWizardPage):
    """動作確認。実際に動いてから完了させる。

    導入直後は常駐が始まっておらず「完了を押したら動いた」ことがあった。
    ここで起動し、動いたことを本人に確かめてもらう。
    """

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        lay.addWidget(_title("動作の確認"))
        lay.addWidget(_body("実際に動かして確かめます。"))
        lay.addSpacing(12)

        self.card = QFrame()
        self.card.setObjectName("Card")
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(18, 16, 18, 16)
        self.state = QLabel("準備しています…")
        self.state.setObjectName("Big")
        self.state.setWordWrap(True)
        cl.addWidget(self.state)
        lay.addWidget(self.card)
        lay.addSpacing(14)

        lay.addWidget(_body("試してみてください", "Section"))
        lay.addWidget(_card(_body(
            "左スティックを倒す  →  マウスカーソルが動きます\n\n"
            "○ ボタンを押す      →  クリックになります\n\n"
            "R2 を押しながら動かす →  カーソルが速くなります")))
        lay.addSpacing(12)

        self.ok = QCheckBox("カーソルが動くのを確認しました")
        self.ok.stateChanged.connect(lambda _: self.completeChanged.emit())
        lay.addWidget(self.ok)
        self.note = _body("", "Subtitle")
        lay.addWidget(self.note)
        lay.addStretch()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._refresh)

    def initializePage(self) -> None:
        self.ok.setChecked(False)
        try:
            runner.start(hidden=True)
        except Exception as e:
            self.state.setText(f"起動できませんでした: {e}")
            return
        self._refresh()
        self.timer.start(1500)

    def cleanupPage(self) -> None:
        self.timer.stop()

    def _refresh(self) -> None:
        running = runner.is_running()
        has_pad = bool(detect.find_controllers())
        if running and has_pad:
            self.state.setObjectName("BigOk")
            self.state.setText("✅  動いています")
            self.note.setText(
                "動かない場合は、コントローラーの PS ボタンを一度押してみてください。")
        elif running:
            self.state.setObjectName("BigWarn")
            self.state.setText("⚠️  コントローラーがつながっていません")
            self.note.setText("コントローラーを接続すると自動で使えるようになります。")
        else:
            self.state.setObjectName("BigWarn")
            self.state.setText("⚠️  起動していません")
            self.note.setText("「戻る」でやり直すか、完了後に padpilot を開いてください。")
        self.state.style().unpolish(self.state)
        self.state.style().polish(self.state)

    def isComplete(self) -> bool:
        return self.ok.isChecked()


class DonePage(QWizardPage):
    """完了。"""

    def __init__(self):
        super().__init__()
        lay = QVBoxLayout(self)
        self.head = _title("セットアップ完了")
        lay.addWidget(self.head)
        self.msg = QLabel()
        self.msg.setWordWrap(True)
        lay.addWidget(self.msg)
        lay.addStretch()

    def initializePage(self) -> None:
        if getattr(self.wizard(), "installed_ok", False):
            self.head.setText("使えるようになりました")
            self.msg.setText(
                "コントローラーでパソコンを操作できます。\n\n"
                "  ● 左スティック … カーソル移動\n"
                "  ● 右スティック … スクロール\n"
                "  ● ○ ボタン … クリック\n"
                "  ● R2 / L2 を押しながら … 速く / ゆっくり\n\n"
                "文字を入力したいときは、入力欄をクリックしてください。\n"
                "画面にキーボードが出てきます。\n\n"
                "調子が悪いときは、アプリ一覧から padpilot を開いてください。")
        else:
            self.head.setText("セットアップは完了しませんでした")
            self.msg.setText("前の画面の内容を確認して、もう一度お試しください。")


class InstallerWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.installed_ok = False
        self.setWindowTitle("padpilot セットアップ")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnStartPage, True)
        self.resize(680, 620)

        self.profile_page = ProfilePage()
        for page in (WelcomePage(), ConnectPage(), OptionsPage(),
                     self.profile_page, ProgressPage(), TestPage(), DonePage()):
            self.addPage(page)

        self.setButtonText(QWizard.NextButton, "次へ  ›")
        self.setButtonText(QWizard.BackButton, "‹  戻る")
        self.setButtonText(QWizard.FinishButton, "完了")
        self.setButtonText(QWizard.CancelButton, "中止")
        self.button(QWizard.NextButton).setObjectName("Primary")
        self.button(QWizard.FinishButton).setObjectName("Primary")


def main() -> int:
    app = QApplication(sys.argv)
    qss = Path(__file__).resolve().parent / "style.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    w = InstallerWizard()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
