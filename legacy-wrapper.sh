#!/bin/bash
# AntiMicroX 3.6.0 (AppImage) を PS5 プロファイル付きで起動するラッパー。
#
#   引数なし : 未起動なら GUI 無しで常駐開始 / 起動中なら隠れている GUI を表示
#   gui      : 未起動なら GUI を出して起動 / 起動中なら GUI を表示
#   start    : 常駐開始のみ (起動中なら何もしない)
#   quit     : 終了
#
# --no-tray を常に付ける。GNOME にはトレイが無いため、トレイ有効のままだと
# ウィンドウの [x] がトレイへの格納として扱われ、閉じても終了できなくなる。
# --no-tray なら [x] = 終了、[-] = 最小化 (常駐は継続) となり要件どおりになる。
#
# AntiMicroX は /tmp/antimicroxSignalListener への接続可否で多重起動を判定するが、
# 異常終了でこのソケットが残ると「起動中」と誤判定して二度と起動できなくなる。
# プロセスが居ないのにソケットだけ残っている場合は消してから起動する。
# 逆に生きているうちに消すと多重起動を許してしまうので、必ず生死を見てから消す。

PROFILE="$HOME/p2.amgp"
SOCK="/tmp/antimicroxSignalListener"
LOG="$HOME/.antimicrox-ps5.log"

log() { echo "$(date '+%F %T') [$$] $*" >>"$LOG"; }

for candidate in "$HOME/bin/antimicrox360" "$HOME/bin/antimicrox332"; do
    if [ -x "$candidate" ]; then
        APP="$candidate"
        break
    fi
done

if [ -z "$APP" ]; then
    log "AppImage が見つからない"
    notify-send "AntiMicroX" "AppImage が見つかりません" 2>/dev/null
    exit 1
fi

# AppImage は /tmp/.mount_antimiXXXX/ に展開した AppRun.wrapped を実行し直すため、
# プロセス名は antimicrox にならない。pgrep -x antimicrox は決してマッチしない。
# 実際のプロセス名は AppRun.wrapped (実体) と antimicrox360 (ランチャー) の2つ。
#
# pgrep -f (コマンドライン部分一致) は使わない。検索文字列を含むだけの無関係な
# プロセス (その文字列を引数に持つシェル等) まで巻き込み、kill 時に事故る。
# pgrep -x はプロセス名の完全一致なので誤爆しない。その上で cmdline を見て
# 他の AppImage の AppRun.wrapped と区別する。
# 判定は「展開先パスに antimi を含む」だけでは不足。AppImage を別名で置くと
# 展開先が /tmp/.mount_<別名>XXXX/ になり antimi が現れないため取りこぼす
# (検証用に am3.3.4 等の名前で置いたインスタンスが quit で殺せず、
#  終了したはずなのにコントローラーが効き続ける事故が実際に起きた)。
# プロファイルのパスも判定材料に加える。どの名前で起動していても
# このプロファイルを掴んでいる以上、こちらの管轄とみなして終了させる。
antimicrox_pids() {
    local p cmd pids=""
    for p in $(pgrep -x AppRun.wrapped 2>/dev/null) \
             $(pgrep -x "$(basename "$APP")" 2>/dev/null); do
        [ "$p" = "$$" ] && continue
        cmd=$(tr '\0' ' ' <"/proc/$p/cmdline" 2>/dev/null) || continue
        case "$cmd" in
            *antimi*|*"$PROFILE"*) pids="$pids $p" ;;
        esac
    done
    echo $pids
}

running() {
    [ -n "$(antimicrox_pids)" ]
}

clean_socket() {
    if ! running && [ -e "$SOCK" ]; then
        log "残留ソケットを削除: $SOCK"
        rm -f "$SOCK"
    fi
}

launch() {
    clean_socket
    log "起動: $APP --profile $PROFILE --no-tray $*"
    # setsid で端末から切り離す。ターミナルを閉じても常駐が続くようにするため。
    # 出力はログへ流す。捨てると失敗理由が分からなくなる。
    setsid "$APP" --profile "$PROFILE" --no-tray "$@" >>"$LOG" 2>&1 &
    disown 2>/dev/null
    sleep 2
    log "起動後の状態: running=$(running && echo yes || echo no)"
}

# ウィンドウが実在するか (最小化されていても _NET_CLIENT_LIST には残る)。
has_window() {
    command -v xprop >/dev/null 2>&1 || return 1
    local w
    for w in $(xprop -root _NET_CLIENT_LIST 2>/dev/null | grep -o '0x[0-9a-f]*'); do
        xprop -id "$w" WM_CLASS 2>/dev/null | grep -qi antimicrox && return 0
    done
    return 1
}

# 隠れている GUI を出す。
#
# 本来は既存インスタンスへ --show を転送する想定だったが、3.3.2 / 3.5.1 / 3.6.0 の
# いずれでも機能しないことを実測で確認した (ソケット接続までは成功し
# "AntiMicroX is already running." を出して終わる)。手順書の記述は誤り。
# そのため「ウィンドウが無いときは GUI 付きで起動し直す」方式にする。
#
# 最小化しただけならウィンドウは生きているので再起動は不要。その場合は
# GNOME 側がドックのクリックで復帰させるため、ここでは何もしない。
show() {
    if has_window; then
        log "ウィンドウは存在する (最小化含む)。GNOME 側の復帰に任せる"
        return
    fi
    log "GUI 無しで常駐中のためウィンドウが無い。GUI 付きで起動し直す"
    stop
    sleep 1
    launch
}

stop() {
    local pids
    pids=$(antimicrox_pids)
    if [ -n "$pids" ]; then
        log "終了対象 PID: $pids"
        kill $pids 2>/dev/null
        sleep 1
        pids=$(antimicrox_pids)
        [ -n "$pids" ] && { log "強制終了: $pids"; kill -9 $pids 2>/dev/null; }
    else
        log "終了対象なし"
    fi
    rm -f "$SOCK"
    log "終了処理を実行"
}

log "呼び出し: '${1:-（引数なし）}' running=$(running && echo yes || echo no) socket=$([ -e "$SOCK" ] && echo あり || echo なし)"

case "$1" in
quit)
    stop
    ;;
gui)
    if running; then
        show
    else
        launch
    fi
    ;;
start)
    running || launch --hidden
    ;;
*)
    if running; then
        show
    else
        launch --hidden
    fi
    ;;
esac
