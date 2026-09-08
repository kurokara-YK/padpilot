"""GUI が表示する状態 (AGENTS.md §7.3)。

controller と running を別々に持つ。これが分かれていないと
「コントローラーは見えているがアプリが落ちている」を表現できず、
プロファイル欠落事故 (§5.1) のような誤解が起きる。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import detect, doctor, paths, runner


@dataclass
class Status:
    installed: bool
    version: str | None
    controller: str | None
    kind: str | None
    transport: str | None       # "bluetooth" / "usb"
    mac: str | None
    touchpad_ok: bool
    running: bool
    has_window: bool
    session: str
    problems: list = field(default_factory=list)

    @property
    def ready(self) -> bool:
        return self.installed and self.controller is not None and self.running


def get_status(with_problems: bool = True) -> Status:
    """現在の状態を取得する。

    1〜2 秒ごとにポーリングして使う。コントローラーの抜き差しや
    プロセスの異常終了は通知が来ないため、見に行くのが唯一確実 (§7.3)。
    """
    controllers = detect.find_controllers()
    c = controllers[0] if controllers else None
    return Status(
        installed=paths.antimicrox_path().exists(),
        version=detect.antimicrox_version(),
        controller=c.name if c else None,
        kind=c.kind if c else None,
        transport=c.transport if c else None,
        mac=c.mac if c else None,
        touchpad_ok=bool(c and c.touchpad_is_pointer),
        running=runner.is_running(),
        has_window=runner.has_window() if runner.is_running() else False,
        session=detect.session_type(),
        problems=doctor.check() if with_problems else [],
    )
