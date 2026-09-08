"""GUI 共通の部品。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox


class NoScrollComboBox(QComboBox):
    """ホイールで値が変わらないコンボボックス。

    表の中に置くと、表をスクロールしたつもりが値を書き換えてしまう。
    クリックして開いたときだけ選べるようにする。
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # フォーカスが無い状態でホイールを受け取らない
        self.setFocusPolicy(Qt.StrongFocus)

    def wheelEvent(self, event):
        # 閉じているときはホイールを親（表）へ流す
        if not self.view().isVisible():
            event.ignore()
            return
        super().wheelEvent(event)
