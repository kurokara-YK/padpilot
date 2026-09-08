#!/bin/bash
# padpilot をパソコンから削除する。
# 右クリック →「プログラムとして実行する」で使う。
#
# 「はじめにこれを実行.sh」と同じく、GUI で確認画面を出す。
# 端末が開かない実行方法でも結果が見えるようにするため。
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null; then
    command -v zenity >/dev/null && zenity --error --text="python3 が見つかりません"
    exit 1
fi

# GUI が使えるなら確認画面を出す
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] \
   && python3 -c "import PySide6" 2>/dev/null; then
    exec python3 -m gui.uninstaller
fi

# GUI が無い環境。zenity があれば確認を取る
if command -v zenity >/dev/null 2>&1; then
    zenity --question --title="padpilot の削除" --width=380 \
      --text="padpilot をパソコンから削除します。\n\nよろしいですか？" || exit 0
fi
python3 -m core uninstall --purge
command -v zenity >/dev/null 2>&1 && \
    zenity --info --title="padpilot" --width=320 --text="削除しました。" 2>/dev/null || true
