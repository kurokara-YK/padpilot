"""診断 (AGENTS.md §7.5)。

既知の問題を Problem として列挙し、自動修復できるものは fix() を持たせる。
「動くはず」で書かない。すべて docs/original-notes.md の実測に対応する。
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Callable

from . import detect, paths

ERROR = "error"
WARNING = "warning"


@dataclass
class Problem:
    id: str
    severity: str
    message: str            # 日本語。GUI では t() を通す
    detail: str = ""
    fix: Callable[[], None] | None = None

    @property
    def fixable(self) -> bool:
        return self.fix is not None


def _gsettings_get(schema: str, key: str) -> str | None:
    if not shutil.which("gsettings"):
        return None
    try:
        r = subprocess.run(["gsettings", "get", schema, key],
                           capture_output=True, text=True, timeout=5)
    except subprocess.SubprocessError:
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _gsettings_set(schema: str, key: str, value: str) -> None:
    subprocess.run(["gsettings", "set", schema, key, value],
                   capture_output=True, timeout=5)


def _restore_profile() -> None:
    src, dst = paths.source_profile(), paths.profile_path()
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _remove_socket() -> None:
    paths.socket_path().unlink(missing_ok=True)


def _enable_a11y() -> None:
    # 両方必要。toolkit-accessibility が false だと auto-show は動かない
    # (AGENTS.md §5.2 B の実測)。
    _gsettings_set("org.gnome.desktop.interface", "toolkit-accessibility", "true")
    _gsettings_set("org.onboard.auto-show", "enabled", "true")
    # これが true だとコントローラー操作で即座に隠れる (§5.2)
    _gsettings_set("org.onboard.auto-show", "hide-on-key-press", "false")
    # acpid が無いと tablet_mode=None になり、数秒で引っ込む (§5.2)
    _gsettings_set("org.onboard.auto-show",
                   "tablet-mode-detection-enabled", "false")
    # 複数モニタで 'active' だとカーソル移動で消える (§5.2)
    if _gsettings_get("org.onboard.window", "docking-monitor") == "'active'":
        _gsettings_set("org.onboard.window", "docking-monitor", "primary")


def check() -> list[Problem]:
    """全検査を実行し、見つかった問題を重大な順に返す。"""
    problems: list[Problem] = []

    # --- プロファイル欠落。最優先 (AGENTS.md §5.1 の事故) ---
    if not paths.profile_path().exists():
        problems.append(Problem(
            id="profile_missing", severity=ERROR,
            message="プロファイルが見つかりません",
            detail=(f"{paths.profile_path()} がありません。\n"
                    "AntiMicroX はプロファイルが無いと起動直後に終了するため、"
                    "コントローラーが反応しなくなります。"),
            fix=_restore_profile if paths.source_profile().exists() else None,
        ))

    # --- 本体の有無とバージョン ---
    if not paths.antimicrox_path().exists():
        problems.append(Problem(
            id="not_installed", severity=ERROR,
            message="AntiMicroX が導入されていません",
            detail="install を実行してください。",
        ))
    else:
        ver = detect.antimicrox_version()
        if ver and ver != paths.ANTIMICROX_VERSION:
            problems.append(Problem(
                id="wrong_version", severity=ERROR,
                message=f"AntiMicroX のバージョンが {ver} です",
                detail=(f"{paths.ANTIMICROX_VERSION} を使ってください。\n"
                        "3.6.1 はプロファイルを読み込めません "
                        "(Qt のスレッド跨ぎシグナル未登録による不具合)。\n"
                        "3.1.4 以下はスクロールとセット切替が壊れています。"),
            ))

    # --- コントローラー接続 (AGENTS.md §5.3) ---
    controllers = detect.find_controllers()
    if not controllers:
        paired = detect.bluetooth_paired()
        if paired:
            detail = ("ペアリング済みの機器があります:\n  "
                      + "\n  ".join(f"{m} {n}" for m, n in paired)
                      + "\nPS ボタンを押して接続してください。")
        else:
            detail = ("PS ボタンと Create ボタンを同時に長押しして"
                      "ペアリングモードにしてください。\n"
                      "USB ケーブルで繋ぐ方法も確実です。")
        problems.append(Problem(
            id="no_controller", severity=ERROR,
            message="コントローラーが接続されていません", detail=detail,
        ))

    # --- セッション種別 ---
    st = detect.session_type()
    if st == "wayland":
        problems.append(Problem(
            id="wayland", severity=WARNING,
            message="Wayland セッションです",
            detail=("AntiMicroX は X11 の XTest でマウス操作を生成します。\n"
                    "動作しない場合はログイン画面で「Ubuntu on Xorg」を"
                    "選んでください。"),
        ))

    # --- 残留ソケット (docs/original-notes.md §8.1) ---
    # プロセスが居ないのにソケットだけ残っていると以後起動できなくなる。
    # 生きているうちに消すと多重起動を許すので、必ず生死を見てから。
    from . import runner
    if paths.socket_path().exists() and not runner.is_running():
        problems.append(Problem(
            id="stale_socket", severity=ERROR,
            message="残留ソケットがあります",
            detail=("異常終了の名残です。これがあると"
                    "「AntiMicroX is already running.」と出て起動できません。"),
            fix=_remove_socket,
        ))

    # --- 画面キーボードの自動表示 (AGENTS.md §5.2 B) ---
    if paths.IS_LINUX:
        if not shutil.which("onboard"):
            problems.append(Problem(
                id="onboard_missing", severity=WARNING,
                message="画面キーボード (onboard) が入っていません",
                detail="sudo apt install onboard で導入してください。",
            ))
        else:
            a11y = _gsettings_get("org.gnome.desktop.interface",
                                  "toolkit-accessibility")
            auto = _gsettings_get("org.onboard.auto-show", "enabled")
            hide = _gsettings_get("org.onboard.auto-show", "hide-on-key-press")
            tablet = _gsettings_get("org.onboard.auto-show",
                                    "tablet-mode-detection-enabled")
            dock = _gsettings_get("org.onboard.window", "docking-monitor")
            if (a11y == "false" or auto == "false"
                    or hide == "true" or tablet == "true"
                    or dock == "'active'"):
                problems.append(Problem(
                    id="a11y_disabled", severity=WARNING,
                    message="画面キーボードが自動で出ない設定です",
                    detail=("入力欄をクリックしても画面キーボードが出ない、"
                            "または出てもすぐ消える状態です。\n"
                            "コントローラーの操作はキー入力として送られるため、"
                            "hide-on-key-press が有効だと即座に隠れます。\n"
                            "また、タブレットモード検出が有効だと、"
                            "判定できず数秒で引っ込みます。\n"
                            "画面が複数ある場合、表示先が「動いている画面」"
                            "になっていると、カーソルを別の画面へ動かした"
                            "だけで消えてしまいます。"),
                    fix=_enable_a11y,
                ))

    # --- Steam 競合 (docs/original-notes.md §8.3) ---
    if _pgrep_exact("steam"):
        problems.append(Problem(
            id="steam_conflict", severity=WARNING,
            message="Steam が起動しています",
            detail=("Steam のデスクトップ設定が有効だと入力が二重に飛びます。\n"
                    "Steam → 設定 → コントローラ から無効にしてください。"),
        ))

    order = {ERROR: 0, WARNING: 1}
    return sorted(problems, key=lambda p: order[p.severity])


def _pgrep_exact(name: str) -> bool:
    """プロセス名の完全一致。

    pgrep -f は文字列を引数に含むだけの無関係なプロセスまで拾うので使わない
    (docs/original-notes.md §6.2 の事故)。
    """
    try:
        r = subprocess.run(["pgrep", "-x", name],
                           capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
