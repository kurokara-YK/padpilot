"""CLI 入口。GUI と同じ core を呼ぶ (AGENTS.md §7.1)。

    python3 -m core <command>

コマンド:
  status              現在の状態を表示
  doctor              診断（問題があれば終了コード 1）
  fix                 自動修復できる問題を直す
  install [--clean]   導入（--clean で旧構成も片付ける）
  uninstall [--purge] 撤退（--purge で設定も削除）
            [--keep-legacy]  旧構成を残す
  verify              導入が正しいか確認
  start / gui / stop  起動・GUI表示・終了
  osk-listen          タッチパッド押し込みの待ち受けを前面で実行（確認用）
  osk-toggle          画面キーボードを今すぐ開閉する
"""
from __future__ import annotations

import sys

from . import doctor, i18n, install, runner, status


def _print_status() -> None:
    s = status.get_status()
    print(f"導入        : {'済' if s.installed else '未'}"
          + (f" ({s.version})" if s.version else ""))
    if s.controller:
        via = i18n.t("via_bluetooth" if s.transport == "bluetooth" else "via_usb")
        print(f"コントローラー: {s.controller} [{via}]")
        print(f"タッチパッド : {'マウスとして使用可' if s.touchpad_ok else '不可'}")
    else:
        print(f"コントローラー: {i18n.t('disconnected')}")
    print(f"動作        : {i18n.t('running') if s.running else i18n.t('stopped')}")
    print(f"セッション  : {s.session}")


def _print_problems(problems) -> int:
    if not problems:
        print("✅ " + i18n.t("no_problems"))
        return 0
    print(i18n.t("problems_found", n=len(problems)))
    for p in problems:
        mark = "🔴" if p.severity == "error" else "🟡"
        print(f"\n{mark} [{p.id}] {p.message}")
        for line in p.detail.splitlines():
            print(f"    {line}")
        if p.fixable:
            print("    → 自動修復できます (fix コマンド)")
    return 1


def main(argv: list[str] | None = None) -> int:
    args = (argv if argv is not None else sys.argv[1:]) or ["status"]
    cmd = args[0]

    if cmd == "status":
        _print_status()
        return 0
    if cmd == "doctor":
        return _print_problems(doctor.check())
    if cmd == "fix":
        fixed = 0
        for p in doctor.check():
            if p.fixable:
                print(f"修復中: {p.message}")
                try:
                    p.fix()
                    fixed += 1
                except Exception as e:
                    print(f"  失敗: {e}")
        print(f"{fixed} 件を修復しました" if fixed else "修復できる問題はありません")
        return 0
    if cmd == "install":
        try:
            install.install_all(progress=print,
                                clean_legacy="--clean" in args)
        except RuntimeError as e:
            print(e)
            return 1
        return 0
    if cmd == "uninstall":
        install.uninstall(progress=print,
                          purge="--purge" in args,
                          legacy="--keep-legacy" not in args)
        return 0
    if cmd == "verify":
        issues = install.verify()
        if not issues:
            print("✅ 導入は正常です")
            return 0
        for i in issues:
            print(f"⚠ {i}")
        return 1
    if cmd == "start":
        try:
            ok = runner.start(hidden=True)
        except FileNotFoundError as e:
            print(f"起動できません: {e}")
            return 1
        print("開始しました" if ok else "起動に失敗しました")
        return 0 if ok else 1
    if cmd == "gui":
        return 0 if runner.show_gui() else 1
    if cmd == "stop":
        runner.stop()
        print("停止しました")
        return 0
    if cmd == "osk-listen":
        # タッチパッド押し込みの待ち受け。前面で動かす（動作確認用）
        from . import osktoggle
        return osktoggle.run(verbose=True)
    if cmd == "osk-toggle":
        from . import osktoggle
        print("切り替えました" if osktoggle.toggle() else "切り替えできません")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
