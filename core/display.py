"""画面（モニタ）の検出と、画面キーボードの表示先の設定。

複数モニタ環境で onboard の docking-monitor が 'active' だと、
カーソルが別モニタへ移った瞬間にキーボードが消える (AGENTS.md §5.2)。
表示先を固定して回避する。
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass

from . import paths


@dataclass
class Monitor:
    name: str          # "HDMI-1-0" など
    width: int
    height: int
    x: int
    y: int
    primary: bool
    index: int         # onboard の monitor0/1/2... に対応

    @property
    def label(self) -> str:
        p = "（メイン）" if self.primary else ""
        return f"{self.name} {self.width}x{self.height}{p}"


def monitors() -> list[Monitor]:
    """接続されているモニタの一覧。"""
    if not paths.IS_LINUX or not shutil.which("xrandr"):
        return []
    try:
        out = subprocess.run(["xrandr"], capture_output=True,
                             text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found: list[Monitor] = []
    for line in out.splitlines():
        if " connected" not in line:
            continue
        m = re.search(r"(\d+)x(\d+)\+(\d+)\+(\d+)", line)
        if not m:
            continue
        found.append(Monitor(
            name=line.split()[0],
            width=int(m.group(1)), height=int(m.group(2)),
            x=int(m.group(3)), y=int(m.group(4)),
            primary=" primary " in line,
            index=len(found),
        ))
    return found


def keyboard_monitor() -> str:
    """現在の画面キーボードの表示先設定。"""
    if not shutil.which("gsettings"):
        return ""
    try:
        r = subprocess.run(
            ["gsettings", "get", "org.onboard.window", "docking-monitor"],
            capture_output=True, text=True, timeout=5)
    except subprocess.SubprocessError:
        return ""
    return r.stdout.strip().strip("'")


def set_keyboard_monitor(value: str) -> bool:
    """画面キーボードの表示先を設定する。

    'active' は使わない。カーソルが別モニタへ移った瞬間に消えるため。
    """
    if not shutil.which("gsettings"):
        return False
    try:
        r = subprocess.run(
            ["gsettings", "set", "org.onboard.window",
             "docking-monitor", value],
            capture_output=True, timeout=5)
    except subprocess.SubprocessError:
        return False
    return r.returncode == 0


def monitor_choices() -> list[tuple[str, str]]:
    """GUI に出す表示先の選択肢 [(設定値, 表示名)]。"""
    out = [("primary", "メインの画面")]
    for m in monitors():
        out.append((f"monitor{m.index}", m.label))
    return out
