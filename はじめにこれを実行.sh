#!/bin/bash
# padpilot をアプリ一覧に登録する。最初の1回だけ実行すればよい。
#
# GNOME 46 (Ubuntu 24.04) の Nautilus は、任意のフォルダに置かれた
# .desktop ファイルを実行しない。正式な場所に登録されたものだけが
# アプリとして起動できる。そのため、まずここへ登録する。
set -euo pipefail
cd "$(dirname "$0")"
HERE="$(pwd)"
APPS="$HOME/.local/share/applications"
mkdir -p "$APPS"

command -v python3 >/dev/null || {
    echo "python3 が見つかりません。"; read -rp "Enterで閉じます"; exit 1; }

cat > "$APPS/padpilot-setup.desktop" <<INNER
[Desktop Entry]
Type=Application
Version=1.0
Name=padpilot セットアップ
Name[en]=padpilot Setup
Comment=ゲームパッドでパソコンを操作できるようにします
Exec=$HERE/setup.sh
Icon=input-gaming
Terminal=false
Categories=Settings;
INNER

cat > "$APPS/padpilot-uninstall.desktop" <<INNER
[Desktop Entry]
Type=Application
Version=1.0
Name=padpilot の削除
Comment=padpilot をパソコンから取り除きます
Exec=$HERE/アンインストール.sh
Icon=user-trash
Terminal=false
Categories=Settings;
NoDisplay=false
INNER

command -v update-desktop-database >/dev/null && \
    update-desktop-database "$APPS" 2>/dev/null || true

# 右クリック「プログラムとして実行」では端末が出ないため、
# 画面上に結果を出す。無反応に見えるのを防ぐ。
notify() {
    command -v zenity >/dev/null 2>&1 && \
        zenity --info --title="padpilot" --width=380 --text="$1" 2>/dev/null &
}

echo
echo "  登録しました。"
echo
echo "  「アプリケーションを表示する」（画面左下の点が9つ並んだボタン）を開き，"
echo "  「padpilot セットアップ」をクリックしてください。"
echo
echo "  見つからないときは，検索欄に padpilot と入力してください。"
echo

# そのままセットアップを開く。
# 端末から実行した場合も、右クリック実行の場合も同じ動きにする。
if [ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then
    echo "  続けてセットアップを開きます..."
    exec "$HERE/setup.sh"
else
    notify "アプリ一覧に登録しました。\n\n「padpilot セットアップ」を開いてください。"
fi
