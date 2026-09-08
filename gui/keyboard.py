"""padpilot の画面キーボード（最小版）。

onboard はカーソルを重ねると SIGSEGV で落ちるため使えない
(AGENTS.md §6.2.9)。自前で持つ。

最重要の性質: **押しても入力欄からフォーカスを奪わない**。
奪うと送ったキーが入力欄に届かない。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QGridLayout, QPushButton, QVBoxLayout, QWidget,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import keysend  # noqa: E402

# (表示, 送る keysym, 横幅)
ROWS = [
    [("1","1",1),("2","2",1),("3","3",1),("4","4",1),("5","5",1),
     ("6","6",1),("7","7",1),("8","8",1),("9","9",1),("0","0",1)],
    [("q","q",1),("w","w",1),("e","e",1),("r","r",1),("t","t",1),
     ("y","y",1),("u","u",1),("i","i",1),("o","o",1),("p","p",1)],
    [("a","a",1),("s","s",1),("d","d",1),("f","f",1),("g","g",1),
     ("h","h",1),("j","j",1),("k","k",1),("l","l",1),("⌫","BackSpace",1)],
    [("z","z",1),("x","x",1),("c","c",1),("v","v",1),("b","b",1),
     ("n","n",1),("m","m",1),("スペース","space",2),("⏎","Return",1)],
]


class OnScreenKeyboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("padpilot キーボード")
        # フォーカスを奪わない。これが無いと文字が入らない。
        self.setWindowFlags(
            Qt.Tool | Qt.WindowStaysOnTopHint
            | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFocusPolicy(Qt.NoFocus)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        grid = QGridLayout()
        grid.setSpacing(5)
        outer.addLayout(grid)

        for r, row in enumerate(ROWS):
            col = 0
            for label, keysym, span in row:
                b = QPushButton(label)
                b.setFocusPolicy(Qt.NoFocus)   # ボタンもフォーカスを取らない
                b.setMinimumSize(58, 52)
                b.setProperty("keysym", keysym)
                b.clicked.connect(
                    lambda _=False, k=keysym: keysend.send_key(k))
                grid.addWidget(b, r, col, 1, span)
                col += span

        close = QPushButton("× 閉じる")
        close.setFocusPolicy(Qt.NoFocus)
        close.setMinimumHeight(34)
        close.clicked.connect(self.close)
        outer.addWidget(close)

    def place_bottom(self) -> None:
        """画面下部の中央に置く。"""
        scr = QApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        self.move(scr.x() + (scr.width() - self.width()) // 2,
                  scr.y() + scr.height() - self.height() - 40)


def main() -> int:
    app = QApplication(sys.argv)
    qss = Path(__file__).resolve().parent / "style.qss"
    if qss.exists():
        app.setStyleSheet(qss.read_text(encoding="utf-8"))
    k = OnScreenKeyboard()
    k.place_bottom()
    k.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
