"""コントローラーとセッションの検出 (AGENTS.md §5.3, §7.2)。

外部コマンドに頼らず /proc/bus/input/devices を読む。権限不要で最も速い。
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from . import paths

DEVICES = Path("/proc/bus/input/devices")

# 対応機種。名前で判定する。js0 等の番号は抜き差しで変わるので使わない。
KNOWN = {
    "DualSense": "ps5",
    "DualShock": "ps4",
    "Wireless Controller": "ps4",   # PS4 は環境によりこの名前になる
    "Xbox": "xbox",
    "Pro Controller": "switch",
}


@dataclass
class Node:
    """1 つの evdev ノード。DualSense は gamepad/touchpad/motion の 3 つを持つ。"""
    name: str
    handlers: list[str] = field(default_factory=list)
    uniq: str = ""
    sysfs: str = ""

    @property
    def is_touchpad(self) -> bool:
        return "touchpad" in self.name.lower()

    @property
    def is_motion(self) -> bool:
        return "motion" in self.name.lower()

    @property
    def is_gamepad(self) -> bool:
        return not self.is_touchpad and not self.is_motion

    @property
    def event_path(self) -> str | None:
        for h in self.handlers:
            if h.startswith("event"):
                return f"/dev/input/{h}"
        return None


@dataclass
class Controller:
    name: str
    kind: str                 # "ps5" / "ps4" / "xbox" / "switch" / "unknown"
    transport: str            # "bluetooth" / "usb"
    mac: str
    nodes: list[Node] = field(default_factory=list)

    @property
    def has_touchpad(self) -> bool:
        """タッチパッドが独立ノードとして公開されているか。

        これが真なら、カーネルが既にマウスとして扱っている (AGENTS.md §3.2 A)。
        """
        return any(n.is_touchpad for n in self.nodes)

    @property
    def touchpad_is_pointer(self) -> bool:
        """タッチパッドが mouse* ハンドラを持つ = ポインタとして動いている。"""
        return any(n.is_touchpad and any(h.startswith("mouse") for h in n.handlers)
                   for n in self.nodes)


def _parse_devices() -> list[Node]:
    """/proc/bus/input/devices を解析する。"""
    if not DEVICES.exists():
        return []
    nodes: list[Node] = []
    cur: Node | None = None
    for line in DEVICES.read_text(errors="replace").splitlines():
        if line.startswith("I:"):
            cur = None
        elif line.startswith("N: Name="):
            cur = Node(name=line.split("=", 1)[1].strip().strip('"'))
            nodes.append(cur)
        elif cur is None:
            continue
        elif line.startswith("U: Uniq="):
            cur.uniq = line.split("=", 1)[1].strip()
        elif line.startswith("S: Sysfs="):
            cur.sysfs = line.split("=", 1)[1].strip()
        elif line.startswith("H: Handlers="):
            cur.handlers = line.split("=", 1)[1].split()
    return nodes


def find_controllers() -> list[Controller]:
    """接続中のコントローラーを返す。

    ノート PC 内蔵タッチパッド (PNP0C50 等) を拾わないよう、
    必ず機種名を含むかで絞る (AGENTS.md §3.2 A の注意)。
    """
    nodes = _parse_devices()
    groups: dict[str, list[Node]] = {}
    for n in nodes:
        for key, kind in KNOWN.items():
            if key.lower() in n.name.lower():
                # 同一デバイスの 3 ノードは MAC でまとまる。
                # MAC が無いノード(touchpad等)は基底名で寄せる。
                base = n.uniq or re.sub(
                    r"\s+(touchpad|motion sensors?)$", "", n.name, flags=re.I)
                groups.setdefault(base, []).append(n)
                break

    out: list[Controller] = []
    for base, group in groups.items():
        gamepad = next((g for g in group if g.is_gamepad), group[0])
        kind = "unknown"
        for key, k in KNOWN.items():
            if key.lower() in gamepad.name.lower():
                kind = k
                break
        transport = "bluetooth" if "bluetooth" in gamepad.sysfs.lower() else "usb"
        out.append(Controller(
            name=gamepad.name, kind=kind, transport=transport,
            mac=gamepad.uniq or base, nodes=group,
        ))
    return out


def session_type() -> str:
    """"x11" / "wayland" / "windows" / "unknown"。"""
    if paths.IS_WINDOWS:
        return "windows"
    t = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if t in ("x11", "wayland"):
        return t
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "unknown"


def bluetooth_paired() -> list[tuple[str, str]]:
    """ペアリング済みデバイス [(MAC, 名前)]。

    「ペアリング済みだが未接続」を区別して案内を出し分けるために使う。
    bluetoothctl が無い環境では空を返す (致命ではない)。
    """
    try:
        r = subprocess.run(["bluetoothctl", "devices", "Paired"],
                           capture_output=True, text=True, timeout=5)
    except (FileNotFoundError, subprocess.SubprocessError):
        return []
    out = []
    for line in r.stdout.splitlines():
        m = re.match(r"Device\s+(\S+)\s+(.*)", line.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def antimicrox_version() -> str | None:
    """配置済み AntiMicroX のバージョン。未配置なら None。"""
    app = paths.antimicrox_path()
    if not app.exists():
        return None
    try:
        r = subprocess.run([str(app), "--version"],
                           capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    m = re.search(r"(\d+\.\d+\.\d+)", r.stdout + r.stderr)
    return m.group(1) if m else None
