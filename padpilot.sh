#!/bin/bash
# padpilot。引数なしでメイン画面、それ以外は core に渡す。
set -euo pipefail
cd "$(dirname "$0")"

if [ $# -eq 0 ]; then
    if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ] \
       && python3 -c "import PySide6" 2>/dev/null; then
        exec python3 -m gui.main
    fi
    exec python3 -m core status
fi
exec python3 -m core "$@"
