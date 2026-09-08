"""キー送出。OS ごとの違いをここに閉じ込める (AGENTS.md §7.2)。

Linux は XTest、Windows は SendInput。どちらも「今フォーカスがある
ウィンドウ」へキーを送る。IME も通る (§5.5 で実測)。
"""
from __future__ import annotations

from . import paths

_display = None


def _x_display():
    global _display
    if _display is None:
        from Xlib import display
        _display = display.Display()
    return _display


def available() -> bool:
    """この環境でキー送出ができるか。"""
    if paths.IS_WINDOWS:
        return True
    try:
        _x_display()
        return True
    except Exception:
        return False


def send_key(keysym: str) -> bool:
    """キーを 1 つ送る。keysym は X の名前 ("a", "space", "Return" 等)。"""
    if paths.IS_WINDOWS:
        return _send_windows(keysym)
    return _send_x11(keysym)


def _send_x11(keysym: str) -> bool:
    try:
        from Xlib import X, XK
        from Xlib.ext import xtest
        d = _x_display()
        code = d.keysym_to_keycode(XK.string_to_keysym(keysym))
        if not code:
            return False
        xtest.fake_input(d, X.KeyPress, code)
        d.sync()
        xtest.fake_input(d, X.KeyRelease, code)
        d.sync()
        return True
    except Exception:
        return False


# Windows の仮想キーコード。X の keysym 名から引く。
_VK = {"space": 0x20, "Return": 0x0D, "BackSpace": 0x08, "Tab": 0x09,
       "Escape": 0x1B}


def _send_windows(keysym: str) -> bool:
    try:
        import ctypes
        vk = _VK.get(keysym)
        if vk is None and len(keysym) == 1:
            vk = ctypes.windll.user32.VkKeyScanW(ord(keysym)) & 0xFF
        if not vk:
            return False
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        return True
    except Exception:
        return False
