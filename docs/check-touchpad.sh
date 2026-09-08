#!/bin/bash
# タッチパッドが OS から独立したデバイスとして見えているかを確認する。
# AGENTS.md §3.2 A の検証。コントローラーを接続してから実行すること。
#
# 判定したいこと:
#   hid-playstation は DualSense を gamepad / touchpad / motion の3ノードに分ける。
#   touchpad ノードが libinput から見えていれば、AntiMicroX を介さず
#   既に普通のタッチパッドとして動く = 実装不要 (§3.2 A)。
#   見えていなければ補助デーモンが要る (§3.2 B)。

echo "=== 1. コントローラーの接続 ==="
if grep -qiE 'Name=.*(dualsense|wireless controller)' /proc/bus/input/devices; then
    grep -iE 'Name=.*(dualsense|wireless controller)' /proc/bus/input/devices
else
    echo "  × 見つからない。PS ボタンで接続してから再実行すること"
    exit 1
fi

echo
echo "=== 2. hid-playstation ドライバ ==="
lsmod | grep -i playstation || echo "  × 未ロード。カーネル 5.12 未満か、汎用HIDで認識されている"

echo
echo "=== 3. DualSense が公開する全ノード (ここが核心) ==="
# Handlers 行に event/js が出る。Name と対にして見る。
awk '
  /^I:/ { name="" }
  /^N: Name=/ { name=$0; sub(/^N: Name="/,"",name); sub(/"$/,"",name) }
  /^H: Handlers=/ {
    handlers=$0; sub(/^H: Handlers=/,"",handlers)
    lname=tolower(name)
    if (index(lname,"dualsense") || index(lname,"wireless controller"))
      printf "  %-45s -> %s\n", name, handlers
  }
' /proc/bus/input/devices

echo
echo "  期待する形 (3ノードに分かれていれば A が使える):"
echo "    DualSense Wireless Controller            -> js0 event*   ← gamepad"
echo "    DualSense Wireless Controller Touchpad   -> mouse* event* ← ★これ"
echo "    DualSense Wireless Controller Motion...  -> event*       ← ジャイロ"

echo
echo "=== 4. libinput から見えているか ==="
if command -v libinput >/dev/null 2>&1; then
    # 要 root のことが多い。失敗しても致命ではない
    (libinput list-devices 2>/dev/null || sudo -n libinput list-devices 2>/dev/null) \
      | grep -iA2 -E 'dualsense|wireless controller' \
      || echo "  取得できず (要 sudo)。3 の結果で判断してよい"
else
    echo "  libinput コマンドなし: sudo apt install libinput-tools"
fi

echo
echo "=== 判定 ==="
if grep -qiE 'Name=.*(dualsense|wireless controller).*[Tt]ouchpad' /proc/bus/input/devices; then
    echo "  ✅ touchpad ノードが存在する"
    echo "     → AGENTS.md §3.2 A が成立。実装不要の可能性が高い"
    echo "     → 次: 実際に指でなぞってカーソルが動くか試す"
    echo "     → 動く場合、左スティックとの二重操作が起きないか確認 (§3.2 A の注意)"
else
    echo "  ❌ touchpad ノードが無い"
    echo "     → §3.2 B (evdev+uinput の補助デーモン) が必要"
fi
