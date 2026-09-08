#!/bin/bash
# padpilot 導入スクリプト。
#
# 実処理は core/ にある (AGENTS.md §7.1)。これは Linux 利用者向けの薄い入口。
# GUI も同じ core を呼ぶため、両者の挙動が食い違わない。
set -euo pipefail

cd "$(dirname "$0")"

command -v python3 >/dev/null || { echo "python3 が必要です"; exit 1; }

exec python3 -m core install "$@"
