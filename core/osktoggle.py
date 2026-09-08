"""タッチパッド押し込みで画面キーボードを開閉する。

なぜ AntiMicroX でやらないか
--------------------------
DualSense のタッチパッド押し込みは、AntiMicroX (SDL) からは**見えない**。
カーネルの hid-playstation がコントローラーを 3 つのノードに分け、
押し込みを touchpad ノード側の BTN_LEFT として出すため。
ゲームパッドノードは 13 ボタンしか持たない (AGENTS.md §5.2)。
プロファイルの <button index="21"> が動かなかったのはこのため。

そこで X の XInput2 で、タッチパッドのデバイスから直接ボタン押下を受け取る。
evdev を直接読む方法もあるが、touchpad ノードには logind の ACL が付かず
root 権限か udev ルールが要る (§5.4)。XInput2 なら権限は不要。
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time

from . import paths

# 押し込みを 1 回と数えるための最短間隔 (秒)。
# 押下が連続して届いても 1 回として扱う。
DEBOUNCE = 0.35

# タッチパッドのデバイス名。接続のたびに id が変わるので名前で探す。
TOUCHPAD_HINTS = ("dualsense", "wireless controller")


def _dbus(method: str) -> bool:
    r = subprocess.run(
        ["gdbus", "call", "--session", "--dest", "org.onboard.Onboard",
         "--object-path", "/org/onboard/Onboard/Keyboard",
         "--method", f"org.onboard.Onboard.Keyboard.{method}"],
        capture_output=True, timeout=5)
    return r.returncode == 0


def toggle() -> bool:
    """キーボードの表示/非表示を切り替える。"""
    return _dbus("ToggleVisible")


def show() -> bool:
    return _dbus("Show")


def hide() -> bool:
    return _dbus("Hide")


def onboard_running() -> bool:
    try:
        r = subprocess.run(["pgrep", "-x", "onboard"],
                           capture_output=True, timeout=5)
        return r.returncode == 0
    except (FileNotFoundError, subprocess.SubprocessError):
        return False


def ensure_onboard() -> bool:
    """onboard を常駐させる（画面には出さない）。

    押し込みで開くには onboard 自身が動いている必要がある。
    start-minimized=true にしてあるので、起動しても画面には出ない。
    """
    if onboard_running():
        return True
    if not shutil.which("onboard"):
        return False
    try:
        subprocess.Popen(["onboard"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False
    time.sleep(3)
    hide()          # 念のため隠す
    return onboard_running()


def find_touchpad(d) -> tuple[int, str] | None:
    """タッチパッドの XInput デバイスを探す。

    ノート PC 内蔵のタッチパッドと紛らわしいので、
    必ずコントローラー名を含むかで絞る。
    """
    from Xlib.ext import xinput
    try:
        info = xinput.query_device(d, xinput.AllDevices)
    except Exception:
        return None
    for dev in info.devices:
        name = (dev.name or "").lower()
        if "touchpad" not in name:
            continue
        if any(h in name for h in TOUCHPAD_HINTS):
            return (dev.deviceid, dev.name)
    return None


def pid_file():
    return paths.data_dir() / "osktoggle.pid"


def is_running() -> bool:
    f = pid_file()
    if not f.exists():
        return False
    try:
        os.kill(int(f.read_text().strip()), 0)
        return True
    except (OSError, ValueError):
        return False


def stop() -> None:
    f = pid_file()
    if f.exists():
        try:
            os.kill(int(f.read_text().strip()), 15)
        except (OSError, ValueError):
            pass
        f.unlink(missing_ok=True)


def run(verbose: bool = False) -> int:
    """タッチパッドの押し込みを待ち受け、開閉を切り替える。"""
    if not paths.IS_LINUX:
        return 0
    try:
        from Xlib import display
        from Xlib.ext import xinput
    except ImportError:
        print("python3-xlib が必要です", file=sys.stderr)
        return 1

    try:
        d = display.Display()
    except Exception as e:
        print(f"X に接続できません: {e}", file=sys.stderr)
        return 1

    pf = pid_file()
    pf.parent.mkdir(parents=True, exist_ok=True)
    pf.write_text(str(os.getpid()))

    if not ensure_onboard() and verbose:
        print("onboard を起動できません（未導入？）", flush=True)

    # XInput2 は使用前にバージョンを交渉する。省くとイベントが届かない。
    try:
        xinput.query_version(d)
    except Exception as e:
        print(f"XInput2 を使えません: {e}", file=sys.stderr)
        return 1

    root = d.screen().root
    last = 0.0
    current: tuple[int, str] | None = None

    try:
        while True:
            found = find_touchpad(d)
            if found is None:
                # コントローラー未接続。つながるまで待つ
                if current is not None and verbose:
                    print("タッチパッドが切断されました", flush=True)
                current = None
                time.sleep(2.0)
                continue

            if found != current:
                current = found
                dev_id, dev_name = found
                xinput.select_events(
                    root, [(dev_id, xinput.ButtonPressMask)])
                if verbose:
                    print(f"待ち受け開始: {dev_name} (id={dev_id})", flush=True)

            # イベントを待つ。届かなければデバイスの生死を見直す
            if d.pending_events() == 0:
                time.sleep(0.05)
                continue
            ev = d.next_event()
            # XInput2 は GenericEvent で届く。種別は ev.evtype、
            # デバイスは ev.data 側にある。
            if getattr(ev, "evtype", None) != xinput.ButtonPress:
                continue
            data = getattr(ev, "data", None)
            if data is None or isinstance(data, bytes):
                continue
            # master 経由で届くと deviceid は master になるため
            # sourceid（実際に発生させたデバイス）も見る。
            ids = {getattr(data, "deviceid", None),
                   getattr(data, "sourceid", None)}
            if current[0] not in ids:
                continue

            now = time.time()
            if now - last < DEBOUNCE:
                continue
            last = now
            ok = toggle()
            if verbose:
                print(f"押し込み → キーボードを切り替え "
                      f"({'成功' if ok else '失敗'})", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        pf.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(run(verbose="--verbose" in sys.argv or "-v" in sys.argv))
