#!/bin/bash
# padpilot セットアップ。ダブルクリックで起動する想定。
#
# GUI が使えれば セットアップウィザードを開く。
# 使えない環境 (SSH 等) では CLI の install へ落とす。
set -euo pipefail
cd "$(dirname "$0")"

command -v python3 >/dev/null || {
    echo "python3 が必要です。sudo apt install python3"; exit 1; }

if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] \
   && python3 -c "import PySide6" 2>/dev/null; then
    exec python3 -m gui.installer
fi

echo "GUI を使えないため、コマンドライン版で導入します。"
echo "(GUI 版を使うには: pip install --user PySide6)"
echo
exec python3 -m core install "$@"
