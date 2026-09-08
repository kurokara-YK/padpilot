"""アンインストールの確認画面。

消す前に何が消えるかを見せる。取り返しがつかない操作なので確認を挟む。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QVBoxLayout,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import install  # noqa: E402


class _Worker(QThread):
    line = Signal(str)
    done = Signal()

    def __init__(self, purge: bool):
        super().__init__()
        self.purge = purge

    def run(self) -> None:
        try:
            install.uninstall(self.line.emit, purge=self.purge)
        except Exception as e:
            self.line.emit(f"エラー: {e}")
        self.done.emit()


class Uninstaller(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("padpilot の削除")
        self.resize(560, 470)
        lay = QVBoxLayout(self)

        title = QLabel("本当にアンインストールしますか？")
        title.setObjectName("Title")
        title.setWordWrap(True)
        lay.addWidget(title)
        sub = QLabel("padpilot をパソコンから取り除きます。\n"
                     "元に戻すには、もう一度セットアップしてください。")
        sub.setWordWrap(True)
        sub.setObjectName("Subtitle")
        lay.addWidget(sub)
        lay.addSpacing(12)

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(18, 14, 18, 14)
        items = QLabel(
            "消えるもの\n\n"
            "  ・ AntiMicroX（コントローラーを読み取るソフト）\n"
            "  ・ ボタンの割り当て設定\n"
            "  ・ アプリ一覧のアイコン\n"
            "  ・ 画面キーボードの設定（元に戻します）\n\n"
            "パソコンの他の設定には影響しません。")
        items.setWordWrap(True)
        cl.addWidget(items)
        lay.addWidget(card)
        lay.addSpacing(10)

        self.purge = QCheckBox("設定もすべて消す")
        self.purge.setChecked(True)
        lay.addWidget(self.purge)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setVisible(False)
        lay.addWidget(self.log)
        lay.addStretch()

        row = QHBoxLayout()
        row.addStretch()
        self.cancel = QPushButton("やめる")
        self.cancel.setMinimumHeight(38)
        self.cancel.clicked.connect(self.reject)
        self.run_btn = QPushButton("アンインストールする")
        self.run_btn.setMinimumHeight(38)
        self.run_btn.setObjectName("Danger")
        self.run_btn.clicked.connect(self._run)
        row.addWidget(self.cancel)
        row.addWidget(self.run_btn)
        lay.addLayout(row)
        self.worker: _Worker | None = None

    def _run(self) -> None:
        self.run_btn.setEnabled(False)
        self.purge.setEnabled(False)
        self.log.setVisible(True)
        self.worker = _Worker(self.purge.isChecked())
        self.worker.line.connect(self.log.append)
        self.worker.done.connect(self._finished)
        self.worker.start()

    def _finished(self) -> None:
        self.log.append("\n✅ 削除しました。")
        self.cancel.setText("閉じる")
        self.run_btn.setVisible(False)


def main() -> int:
    app = QApplication(sys.argv)
    qss = Path(__file__).resolve().parent / "style.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    d = Uninstaller()
    d.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
