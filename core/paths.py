"""OS ごとの配置先を一元管理する (AGENTS.md §7.2)。

GUI や他モジュールに `if platform.system() == "Windows"` を書かないための集約点。
"""
from __future__ import annotations

import os
import platform
from pathlib import Path

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"

APP_NAME = "padpilot"

# 使用する AntiMicroX のバージョン。3.6.1 はプロファイルを読めない
# (docs/original-notes.md §3.3 の実測)。固定する。
ANTIMICROX_VERSION = "3.6.0"
APPIMAGE_URL = (
    "https://github.com/AntiMicroX/antimicrox/releases/download/"
    f"{ANTIMICROX_VERSION}/AntiMicroX-x86_64.AppImage"
)


def home() -> Path:
    return Path.home()


def config_dir() -> Path:
    """設定ファイルの置き場所。"""
    if IS_WINDOWS:
        base = Path(os.environ.get("APPDATA", home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", home() / ".config"))
    return base / APP_NAME


def data_dir() -> Path:
    """本体やプロファイルの配置先。"""
    if IS_WINDOWS:
        base = Path(os.environ.get("LOCALAPPDATA", home() / "AppData" / "Local"))
        return base / APP_NAME
    return Path(os.environ.get("XDG_DATA_HOME", home() / ".local" / "share")) / APP_NAME


def bin_dir() -> Path:
    return data_dir() if IS_WINDOWS else home() / ".local" / "bin"


def antimicrox_path() -> Path:
    """AntiMicroX 本体の配置先。"""
    return bin_dir() / ("antimicrox.exe" if IS_WINDOWS else "antimicrox")


def profile_path() -> Path:
    """アプリが実際に読むプロファイル。

    原本 (repo の profiles/) とは別物。両者の取り違えが
    プロファイル欠落事故の原因になった (AGENTS.md §5.1)。
    """
    return data_dir() / "desktop.amgp"


def repo_root() -> Path:
    """このリポジトリのルート。"""
    return Path(__file__).resolve().parent.parent


def source_profile() -> Path:
    """プロファイルの原本。"""
    return repo_root() / "profiles" / "desktop.amgp"


def config_file() -> Path:
    return config_dir() / "config.json"


def log_file() -> Path:
    return data_dir() / "padpilot.log"


def socket_path() -> Path:
    """AntiMicroX の多重起動判定ソケット。

    異常終了で残ると以後起動できなくなる (docs/original-notes.md §8.1)。
    """
    return Path("/tmp/antimicroxSignalListener")


def desktop_entry() -> Path:
    return home() / ".local" / "share" / "applications" / f"{APP_NAME}.desktop"
