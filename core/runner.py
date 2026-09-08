"""AntiMicroX の起動・終了・状態取得 (AGENTS.md §7.2)。

legacy-wrapper.sh の移植。判定ロジックは実測で得たものなので、
理由ごと持ち込む (docs/original-notes.md §6)。
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from . import paths


def _pids_by_name(name: str) -> list[int]:
    """プロセス名の完全一致で PID を得る。

    pgrep -f (コマンドライン部分一致) は使わない。検索文字列を引数に含むだけの
    無関係なプロセスまで巻き込み、kill 時に事故る
    (docs/original-notes.md §6.2: 検証スクリプト自身を kill した事故)。
    """
    try:
        r = subprocess.run(["pgrep", "-x", name], capture_output=True,
                           text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    return [int(x) for x in r.stdout.split() if x.isdigit()]


def _cmdline(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\0", b" ").decode(errors="replace")


def antimicrox_pids() -> list[int]:
    """管轄下の AntiMicroX プロセス。

    AppImage は /tmp/.mount_antimiXXXX/ に展開した AppRun.wrapped を実行し直すため、
    プロセス名は antimicrox にならない (docs/original-notes.md §6.1)。

    展開先に "antimi" を含むかだけでは不足。別名で置くと
    /tmp/.mount_<別名>XXXX/ になり取りこぼす。終了させたはずなのに
    コントローラーが効き続ける事故が実際に起きた (§6.3)。
    そのためプロファイルのパスを掴んでいるプロセスも管轄とみなす。
    """
    me = os.getpid()
    profile = str(paths.profile_path())
    app_name = paths.antimicrox_path().name
    found: list[int] = []
    for pid in _pids_by_name("AppRun.wrapped") + _pids_by_name(app_name):
        if pid == me:
            continue
        cmd = _cmdline(pid)
        if not cmd:
            continue
        if "antimi" in cmd or profile in cmd:
            found.append(pid)
    return sorted(set(found))


def is_running() -> bool:
    return bool(antimicrox_pids())


def has_window() -> bool:
    """ウィンドウが実在するか。最小化されていても _NET_CLIENT_LIST には残る。"""
    try:
        r = subprocess.run(["xprop", "-root", "_NET_CLIENT_LIST"],
                           capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return False
    for wid in [w for w in r.stdout.split() if w.startswith("0x")]:
        try:
            w = subprocess.run(["xprop", "-id", wid.rstrip(","), "WM_CLASS"],
                               capture_output=True, text=True, timeout=5)
        except subprocess.SubprocessError:
            continue
        if "antimicrox" in w.stdout.lower():
            return True
    return False


def _clean_socket() -> None:
    """残留ソケットを消す。

    必ず生死を確認してから。生きているうちに消すと多重起動を許す
    (docs/original-notes.md §8.1, §6.6)。
    """
    if not is_running():
        paths.socket_path().unlink(missing_ok=True)


def start(hidden: bool = True) -> bool:
    """起動する。すでに動いていれば何もしない。"""
    if is_running():
        return True
    profile = paths.profile_path()
    if not profile.exists():
        # プロファイルが無いと AntiMicroX は起動直後に終了する
        # (AGENTS.md §5.1)。ここで弾いて理由を明示する。
        raise FileNotFoundError(f"プロファイルがありません: {profile}")
    app = paths.antimicrox_path()
    if not app.exists():
        raise FileNotFoundError(f"AntiMicroX がありません: {app}")

    _clean_socket()
    # --no-tray は必須。GNOME にトレイが無いため、トレイ有効だと [x] が
    # 「トレイへ格納」になり終了できなくなる (docs/original-notes.md §5.4)。
    cmd = [str(app), "--profile", str(profile), "--no-tray"]
    if hidden:
        cmd.append("--hidden")

    paths.log_file().parent.mkdir(parents=True, exist_ok=True)
    with open(paths.log_file(), "a") as log:
        log.write(f"\n=== start {time.strftime('%F %T')}: {' '.join(cmd)}\n")
        log.flush()
        subprocess.Popen(
            cmd, stdout=log, stderr=log,
            start_new_session=True,   # setsid 相当。端末を閉じても残す (§6.7)
        )
    time.sleep(2)
    return is_running()


def stop() -> None:
    """終了させる。"""
    pids = antimicrox_pids()
    for pid in pids:
        try:
            os.kill(pid, 15)
        except OSError:
            pass
    if pids:
        time.sleep(1)
        for pid in antimicrox_pids():
            try:
                os.kill(pid, 9)
            except OSError:
                pass
    paths.socket_path().unlink(missing_ok=True)


def show_gui() -> bool:
    """GUI を表示する。

    既存インスタンスへ --show を転送する方式は 3.3.2 / 3.5.1 / 3.6.0 の
    いずれでも機能しない (docs/original-notes.md §6.4 の実測)。
    ウィンドウが無い場合は起動し直す。
    """
    if is_running():
        if has_window():
            return True     # GNOME 側の復帰に任せる
        stop()
        time.sleep(1)
    return start(hidden=False)
