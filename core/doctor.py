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
    # キー入力中も表示を維持する、検証済みの既定設定 (§6.2.10)。
    _gsettings_set("org.onboard.auto-show", "hide-on-key-press", "false")
    # タブレットの判定に依存せず表示する、検証済みの既定設定 (§6.2.10)。
    _gsettings_set("org.onboard.auto-show",
                   "tablet-mode-detection-enabled", "false")
    # 表示先は利用者の選択を保つ。GTK では active でも入力が成立した。


def _use_gtk_input() -> None:
    """onboard の XInput 受信経路のクラッシュを回避する (§6.2.10)。"""
    subprocess.run(["gsettings", "set", "org.onboard.keyboard",
                    "input-event-source", "GTK"],
                   capture_output=True, timeout=5, check=True)


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
            source = _gsettings_get("org.onboard.keyboard", "input-event-source")
            if source == "'XInput'":
                problems.append(Problem(
                    id="onboard_xinput", severity=WARNING,
                    message="画面キーボードが操作時に落ちる可能性のある設定です",
                    detail=("この環境では XInput 方式でのクラッシュを確認しています。\n"
                            "ポインタ入力を GTK 方式に切り替えて回避します。\n"
                            "変更後は画面キーボードを閉じて、もう一度開いてください。"),
                    fix=_use_gtk_input,
                ))
            a11y = _gsettings_get("org.gnome.desktop.interface",
                                  "toolkit-accessibility")
            auto = _gsettings_get("org.onboard.auto-show", "enabled")
            hide = _gsettings_get("org.onboard.auto-show", "hide-on-key-press")
            tablet = _gsettings_get("org.onboard.auto-show",
                                    "tablet-mode-detection-enabled")
            if (a11y == "false" or auto == "false"
                    or hide == "true" or tablet == "true"):
                problems.append(Problem(
                    id="a11y_disabled", severity=WARNING,
                    message="画面キーボードの表示設定を確認してください",
                    detail=("padpilot で検証した表示設定と異なります。\n"
                            "支援技術と入力欄への自動表示を有効にし、"
                            "キー入力時の非表示とタブレット判定を無効にします。\n"
                            "現在の設定で必ず不具合が起こるという意味ではありません。"),
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
