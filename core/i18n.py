"""日本語/英語 (AGENTS.md §6.6)。

Qt の翻訳機構は使わない。この規模なら辞書で足りる。
文字列は最初から t() を通す。後から剥がすのは高くつく。
"""
from __future__ import annotations

import json
import locale
import os

from . import paths

LANGS = {
    "ja": {
        "app_name": "padpilot",
        "tagline": "ゲームパッドでデスクトップを操作する",
        "connected": "接続済み",
        "disconnected": "未接続",
        "connect_prompt": "コントローラーを接続してください",
        "connect_help": "PS ボタンと Create ボタンを同時に長押ししてください。\n"
                        "USB ケーブルで繋ぐ方法も確実です。",
        "via_bluetooth": "Bluetooth 接続",
        "via_usb": "USB 接続",
        "start": "開始",
        "stop": "停止",
        "running": "動作中",
        "stopped": "停止中",
        "install": "インストール",
        "diagnose": "診断",
        "advanced": "詳細設定",
        "fix": "直す",
        "no_problems": "問題は見つかりませんでした",
        "problems_found": "{n} 件の問題が見つかりました",
        "touchpad_ok": "タッチパッドはマウスとして使えます",
    },
    "en": {
        "app_name": "padpilot",
        "tagline": "Control your desktop with a gamepad",
        "connected": "Connected",
        "disconnected": "Not connected",
        "connect_prompt": "Please connect your controller",
        "connect_help": "Hold the PS button and Create button together.\n"
                        "Connecting by USB cable also works.",
        "via_bluetooth": "Bluetooth",
        "via_usb": "USB",
        "start": "Start",
        "stop": "Stop",
        "running": "Running",
        "stopped": "Stopped",
        "install": "Install",
        "diagnose": "Diagnose",
        "advanced": "Advanced",
        "fix": "Fix",
        "no_problems": "No problems found",
        "problems_found": "{n} problem(s) found",
        "touchpad_ok": "Touchpad works as a mouse",
    },
}

_current = "ja"      # 既定は日本語


def detect_lang() -> str:
    """設定 > 環境変数 の順に決める。ja 以外は英語に落とす。"""
    cfg = paths.config_file()
    if cfg.exists():
        try:
            v = json.loads(cfg.read_text(encoding="utf-8")).get("lang")
            if v in LANGS:
                return v
        except (OSError, ValueError):
            pass
    env = os.environ.get("LANG") or ""
    if not env:
        try:
            env = locale.getdefaultlocale()[0] or ""
        except (ValueError, TypeError):
            env = ""
    return "ja" if env.lower().startswith("ja") else "en"


def set_lang(lang: str) -> None:
    global _current
    if lang in LANGS:
        _current = lang


def get_lang() -> str:
    return _current


def t(key: str, **kw) -> str:
    s = LANGS.get(_current, LANGS["ja"]).get(key) or LANGS["ja"].get(key, key)
    return s.format(**kw) if kw else s


set_lang(detect_lang())
