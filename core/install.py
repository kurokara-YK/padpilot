"""導入処理 (AGENTS.md §4.1)。

要件: 冪等 / sudo 不要 / バージョン固定 / ダウンロード検証 / パス直書き除去。
GPL の観点から AntiMicroX 本体は同梱せず、公式リリースから取得する
(AGENTS.md §2.1)。
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from . import paths
from .__init__ import __version__

Progress = Callable[[str], None]

# AppImage が壊れていないかの下限。3.6.0 は約 32MB。
MIN_APPIMAGE_BYTES = 10 * 1024 * 1024

# 取得の試行回数。GitHub が一時的に 500 を返すことがあるため。
DOWNLOAD_RETRIES = 4


def _describe_error(e: Exception) -> str:
    """利用者に見せる短い説明。"""
    if isinstance(e, urllib.error.HTTPError):
        if e.code >= 500:
            return f"配布元が応答しません (HTTP {e.code})"
        if e.code == 404:
            return "ファイルが見つかりません (HTTP 404)"
        return f"HTTP {e.code}"
    if isinstance(e, urllib.error.URLError):
        return "インターネットに接続できません"
    return type(e).__name__


def _log(cb: Progress | None, msg: str) -> None:
    if cb:
        cb(msg)


def download_antimicrox(progress: Progress | None = None,
                        force: bool = False) -> Path:
    """AntiMicroX を公式リリースから取得する。

    リポジトリに同梱しないのは GPL の頒布義務を負わないため (AGENTS.md §2.1)。
    """
    dest = paths.antimicrox_path()
    if dest.exists() and not force:
        _log(progress, f"すでにあります: {dest}")
        return dest
    if paths.IS_WINDOWS:
        raise NotImplementedError(
            "Windows は公式インストーラ (.exe) を使ってください")

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".download")
    _log(progress, f"取得中: {paths.APPIMAGE_URL}")

    # GitHub の配信は稀に 500 / 503 を返す。1 回の失敗で
    # セットアップ全体を止めない。少し待って数回やり直す。
    last: Exception | None = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            req = urllib.request.Request(
                paths.APPIMAGE_URL,
                headers={"User-Agent": f"padpilot/{__version__}"})
            with urllib.request.urlopen(req, timeout=180) as r, \
                    open(tmp, "wb") as f:
                shutil.copyfileobj(r, f)
            last = None
            break
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as e:
            last = e
            tmp.unlink(missing_ok=True)
            if attempt < DOWNLOAD_RETRIES:
                wait = attempt * 3
                _log(progress,
                     f"  取得に失敗しました（{_describe_error(e)}）。"
                     f"{wait} 秒後に再試行します… "
                     f"({attempt}/{DOWNLOAD_RETRIES - 1})")
                time.sleep(wait)
    if last is not None:
        raise RuntimeError(
            f"AntiMicroX を取得できませんでした（{_describe_error(last)}）。\n\n"
            "インターネットにつながっているか確かめて、"
            "しばらく待ってからもう一度お試しください。\n"
            "配布元（GitHub）が一時的に応答しないこともあります。") from last

    size = tmp.stat().st_size
    if size < MIN_APPIMAGE_BYTES:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"ダウンロードが不完全です ({size} バイト)。"
            "壊れたファイルに実行権限を与えないため中止しました。")

    tmp.replace(dest)
    # chmod +x を忘れると「許可がありません」になる
    # (docs/original-notes.md §4.2)。
    dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    _log(progress, f"配置しました: {dest} ({size // 1024 // 1024} MB)")
    return dest


def install_profile(progress: Progress | None = None,
                    changes: dict[int, str] | None = None) -> Path:
    """プロファイルを配置する。

    原本と配置先が別なのは AntiMicroX の仕様。取り違えが欠落事故の原因に
    なったので (AGENTS.md §5.1)、ここを唯一の配置経路にする。

    changes があれば割り当てを変更して書き出す。**原本は書き換えない。**
    """
    src, dst = paths.source_profile(), paths.profile_path()
    if not src.exists():
        raise FileNotFoundError(f"プロファイル原本がありません: {src}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if changes:
        from . import profile as profile_mod
        profile_mod.apply_bindings(changes, src, dst)
        _log(progress, f"プロファイルを配置 (割り当て {len(changes)} 件を変更): {dst}")
    else:
        shutil.copy2(src, dst)
        _log(progress, f"プロファイルを配置: {dst}")
    # 意図的な変更かどうかを記録する。これが無いと後の verify が
    # 「原本と違う」と誤って警告する。
    _set_customized(bool(changes))
    return dst


def _marker() -> Path:
    return paths.data_dir() / ".customized"


def _set_customized(flag: bool) -> None:
    m = _marker()
    if flag:
        m.parent.mkdir(parents=True, exist_ok=True)
        m.touch()
    else:
        m.unlink(missing_ok=True)


def is_customized() -> bool:
    """割り当てを変更して導入したか。"""
    return _marker().exists()


def enable_onscreen_keyboard(progress: Progress | None = None) -> bool:
    """画面キーボードの自動表示を有効にする (AGENTS.md §5.2 B)。

    toolkit-accessibility と auto-show の両方が要る。前者が false だと
    onboard は入力欄を検知できず、auto-show だけ true にしても動かない。
    """
    if not paths.IS_LINUX or not shutil.which("gsettings"):
        return False
    ok = True
    for schema, key, val in [
        ("org.gnome.desktop.interface", "toolkit-accessibility", "true"),
        ("org.onboard.auto-show", "enabled", "true"),
        # コントローラーのボタンは AntiMicroX が「キー入力」として送るため、
        # hide-on-key-press が有効だと出た瞬間に隠れてしまう
        # (体感 1 秒で消える)。この構成では必ず無効にする。
        ("org.onboard.auto-show", "hide-on-key-press", "false"),
        # タブレットモード検出は acpid が要る。ノート PC やデスクトップでは
        # 判定できず tablet_mode=None となり、onboard が
        # 「出してよいか分からない」状態になって数秒で引っ込む。
        # 検出を切ると常に表示してよいと判断する。
        ("org.onboard.auto-show", "tablet-mode-detection-enabled", "false"),
        # 複数モニタで 'active' だと、カーソルが別モニタへ移った瞬間に
        # キーボードが消える (実測: 1.5 秒後に消え、戻しても復帰しない)。
        # 表示先を固定して回避する (AGENTS.md §5.2)。
        ("org.onboard.window", "docking-monitor", "primary"),
    ]:
        r = subprocess.run(["gsettings", "set", schema, key, val],
                           capture_output=True, timeout=5)
        if r.returncode != 0:
            ok = False
    _log(progress, "画面キーボードの自動表示を有効にしました"
         if ok else "画面キーボードの設定に失敗しました (onboard 未導入?)")
    return ok


def install_launcher(progress: Progress | None = None) -> Path | None:
    """デスクトップランチャーを登録する。

    テンプレートの @PLACEHOLDER@ を実際のパスへ置換する。
    パスを直書きすると他人の環境で動かない (AGENTS.md §4.2)。
    """
    if not paths.IS_LINUX:
        return None
    tpl = paths.repo_root() / "share" / "padpilot.desktop.in"
    if not tpl.exists():
        return None
    launcher = _launcher_path()
    text = (tpl.read_text(encoding="utf-8")
            .replace("@EXEC@", launcher)
            .replace("@ICON@", "input-gaming"))
    dst = paths.desktop_entry()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(dst.parent)],
                       capture_output=True, timeout=15)
    _log(progress, f"ランチャーを登録: {dst}")
    return dst


def preflight(progress: Progress | None = None) -> list[str]:
    """導入前の前提検査。致命的な問題を文字列で返す (AGENTS.md §4.1)。

    空なら導入してよい。警告は progress へ流すだけで止めない。
    """
    blockers: list[str] = []

    if not paths.source_profile().exists():
        blockers.append(f"プロファイル原本がありません: {paths.source_profile()}")

    if paths.IS_LINUX:
        # 旧 antimicro (3.1.4) が入っているとスクロールが1目盛りで止まる
        # (docs/original-notes.md §3.4)。同居させない。
        try:
            r = subprocess.run(["dpkg", "-l", "antimicro"],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and "\nii " in r.stdout:
                _log(progress, "警告: 旧 antimicro パッケージが入っています。"
                               "sudo apt purge antimicro を推奨します")
        except (FileNotFoundError, subprocess.SubprocessError):
            pass

        if not shutil.which("onboard"):
            _log(progress, "警告: onboard が未導入です。画面キーボードが使えません "
                           "(sudo apt install onboard)")

        legacy = find_legacy()
        if legacy:
            _log(progress, f"警告: 旧構成が {len(legacy)} 件残っています。"
                           "二重起動を避けるため uninstall --legacy を推奨します")

    # 書き込み先が作れるか
    for d in (paths.bin_dir(), paths.data_dir()):
        try:
            d.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            blockers.append(f"ディレクトリを作成できません: {d} ({e})")

    return blockers


def enable_autostart(progress: Progress | None = None) -> Path | None:
    """ログイン時の自動起動を有効にする。

    ランチャーと同じ .desktop を autostart へ置く。既定では有効にしない
    (docs/original-notes.md §4.7)。
    """
    if not paths.IS_LINUX:
        return None
    entry = paths.desktop_entry()
    if not entry.exists():
        install_launcher(progress)
    if not entry.exists():
        return None
    dst = paths.home() / ".config" / "autostart" / f"{paths.APP_NAME}.desktop"
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = entry.read_text(encoding="utf-8")
    # 自動起動では GUI を出さず常駐だけ開始する
    text = text.replace(f"Exec={_launcher_path()}\n",
                        f"Exec={_launcher_path()} start\n", 1)
    dst.write_text(text, encoding="utf-8")
    _log(progress, f"自動起動を有効にしました: {dst}")
    return dst


def disable_autostart(progress: Progress | None = None) -> None:
    dst = paths.home() / ".config" / "autostart" / f"{paths.APP_NAME}.desktop"
    if dst.exists():
        dst.unlink()
        _log(progress, "自動起動を無効にしました")


def _launcher_path() -> str:
    return shutil.which("padpilot") or str(paths.repo_root() / "padpilot.sh")


def install_all(progress: Progress | None = None,
                clean_legacy: bool = False,
                changes: dict[int, str] | None = None) -> None:
    """一括導入。冪等 — 何度実行しても壊れない。

    clean_legacy=True なら旧構成の残骸も片付ける。
    """
    blockers = preflight(progress)
    if blockers:
        raise RuntimeError("導入を中止しました:\n  " + "\n  ".join(blockers))

    if clean_legacy:
        _kill_all_antimicrox()
        remove_legacy(progress)

    download_antimicrox(progress)
    install_profile(progress, changes=changes)
    enable_onscreen_keyboard(progress)
    install_launcher(progress)

    issues = verify(allow_edited=bool(changes))
    if issues:
        _log(progress, "警告: 導入後の確認で問題が見つかりました:")
        for i in issues:
            _log(progress, f"  - {i}")
    else:
        _log(progress, "確認: すべて正しく配置されています")
    _log(progress, "完了しました。")


def find_legacy() -> list[Path]:
    """旧構成 (手動セットアップ時代) の残骸を探す。

    padpilot 以前は ~/bin と ~/p2.amgp に直接置いていた。
    残っていると別インスタンスが起動して二重に入力が飛ぶため、
    「終了させたのにコントローラーが効き続ける」事故になる
    (docs/original-notes.md §8.2)。
    """
    home = paths.home()
    candidates = [
        home / "bin" / "antimicrox360",
        home / "bin" / "antimicrox332",
        home / "bin" / "antimicrox-ps5",
        home / "p2.amgp",
        home / ".antimicrox-ps5.log",
        home / ".local/share/applications/antimicrox-ps5.desktop",
        home / ".config/autostart/antimicrox-ps5.desktop",
        home / ".local/share/applications/io.github.antimicrox.antimicrox.desktop",
    ]
    return [p for p in candidates if p.exists()]


def _kill_all_antimicrox() -> int:
    """名前を問わず AntiMicroX 系プロセスを止める。

    別名で置かれた AppImage は展開先に "antimi" が現れず、
    通常の判定では取りこぼす (docs/original-notes.md §6.3)。
    撤退時は残すと害しかないので、AppRun.wrapped を広く止める。
    """
    killed = 0
    for name in ("AppRun.wrapped", "antimicrox", "antimicrox360",
                 "antimicrox332", "antimicrox-ps5"):
        try:
            r = subprocess.run(["pgrep", "-x", name],
                               capture_output=True, text=True, timeout=5)
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
        for pid in (int(x) for x in r.stdout.split() if x.isdigit()):
            if pid == os.getpid():
                continue
            try:
                os.kill(pid, 15)
                killed += 1
            except OSError:
                pass
    if killed:
        time.sleep(1)
        for name in ("AppRun.wrapped", "antimicrox360"):
            try:
                r = subprocess.run(["pgrep", "-x", name],
                                   capture_output=True, text=True, timeout=5)
            except (FileNotFoundError, subprocess.SubprocessError):
                continue
            for pid in (int(x) for x in r.stdout.split() if x.isdigit()):
                if pid == os.getpid():
                    continue
                try:
                    os.kill(pid, 9)
                except OSError:
                    pass
    return killed


def remove_legacy(progress: Progress | None = None) -> int:
    """旧構成の残骸を削除する。"""
    removed = 0
    for p in find_legacy():
        try:
            p.unlink()
            _log(progress, f"旧構成を削除: {p}")
            removed += 1
        except OSError as e:
            _log(progress, f"削除できません: {p} ({e})")
    return removed


def _restore_onscreen_keyboard(progress: Progress | None = None) -> None:
    """画面キーボードの設定を既定へ戻す。

    toolkit-accessibility はシステム全体の設定で、padpilot 以外も使う。
    勝手に有効化したものは撤退時に戻す。
    """
    if not paths.IS_LINUX or not shutil.which("gsettings"):
        return
    for key in ("enabled", "hide-on-key-press",
                "tablet-mode-detection-enabled"):
        subprocess.run(["gsettings", "reset", "org.onboard.auto-show", key],
                       capture_output=True, timeout=5)
    subprocess.run(["gsettings", "reset",
                    "org.onboard.window", "docking-monitor"],
                   capture_output=True, timeout=5)
    subprocess.run(["gsettings", "reset",
                    "org.gnome.desktop.interface", "toolkit-accessibility"],
                   capture_output=True, timeout=5)
    _log(progress, "画面キーボードの設定を既定へ戻しました")


def uninstall(progress: Progress | None = None,
              purge: bool = False,
              legacy: bool = True) -> None:
    """撤退する。sudo 不要、すべてホーム内で完結する。

    purge=True で設定 (config.json, ~/.config/antimicrox) も消す。
    legacy=True で旧構成 (~/bin, ~/p2.amgp) の残骸も消す。
    """
    stopped = _kill_all_antimicrox()
    if stopped:
        _log(progress, f"プロセスを終了しました ({stopped} 件)")

    for p in [paths.antimicrox_path(), paths.profile_path(),
              paths.desktop_entry(), paths.log_file(), _marker(),
              paths.home() / ".config/autostart" / f"{paths.APP_NAME}.desktop"]:
        if p.exists():
            p.unlink(missing_ok=True)
            _log(progress, f"削除: {p}")

    # 残留ソケットは必ず消す。残ると次回起動できなくなる (§8.1)
    if paths.socket_path().exists():
        paths.socket_path().unlink(missing_ok=True)
        _log(progress, f"削除: {paths.socket_path()}")

    if legacy:
        remove_legacy(progress)

    _restore_onscreen_keyboard(progress)

    if purge:
        for d in [paths.config_dir(), paths.home() / ".config" / "antimicrox"]:
            if d.exists():
                shutil.rmtree(d, ignore_errors=True)
                _log(progress, f"設定を削除: {d}")

    # 空になったディレクトリを片付ける。中身が残っていれば消さない
    for d in [paths.data_dir()]:
        if d.exists() and not any(d.iterdir()):
            d.rmdir()
            _log(progress, f"空ディレクトリを削除: {d}")

    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database",
                        str(paths.desktop_entry().parent)],
                       capture_output=True, timeout=15)

    _log(progress, "撤退しました。")


def verify(allow_edited: bool = False) -> list[str]:
    """導入が正しく完了しているかを確認し、問題を文字列で返す。

    allow_edited=True なら原本との md5 不一致を問題としない
    (割り当てを変更した場合は一致しなくて当然)。
    """
    issues = []
    if not paths.antimicrox_path().exists():
        issues.append(f"AntiMicroX がありません: {paths.antimicrox_path()}")
    elif not os.access(paths.antimicrox_path(), os.X_OK):
        issues.append("AntiMicroX に実行権限がありません")
    if not paths.profile_path().exists():
        issues.append(f"プロファイルがありません: {paths.profile_path()}")
    elif paths.source_profile().exists() and not (allow_edited or is_customized()):
        import hashlib
        def h(p):
            return hashlib.md5(p.read_bytes()).hexdigest()
        if h(paths.profile_path()) != h(paths.source_profile()):
            issues.append("プロファイルが原本と異なります (GUI で編集された可能性)")
    if paths.IS_LINUX and not paths.desktop_entry().exists():
        issues.append("ランチャーが登録されていません")
    return issues
