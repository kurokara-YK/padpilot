# PS5 コントローラー (DualSense) でデスクトップを操作する

DualSense をマウス・キーボード代わりに使うための構成手順書。

- 対象環境: Ubuntu 24.04.4 LTS / GNOME / **X11**
- コントローラー: DualSense Wireless Controller (Bluetooth 接続)
- アプリ: AntiMicroX **3.6.0** (AppImage 版)
- 最終更新: 2026-08-07

> **X11 必須。** AntiMicroX は X11 の XTest API でマウス・キー入力を生成するため、
> Wayland セッションでは動作しない。ログイン画面で「Ubuntu on Xorg」を選ぶこと。
> 現在のセッションは `echo $XDG_SESSION_TYPE` で確認できる (`x11` であること)。

---

## 1. 構成の全体像

```
ドックのアイコン
   └─ ~/.local/share/applications/antimicrox-ps5.desktop   ← メニュー定義
         └─ ~/bin/antimicrox-ps5                           ← 状態判定するラッパー
               └─ ~/bin/antimicrox360                      ← AntiMicroX 本体 (AppImage)
                     └─ ~/p2.amgp                          ← プロファイル (割り当て定義)
```

`.desktop` は `Exec` を実行するだけで状態を持てない。「起動していなければ起動、
していれば GUI を出す」という出し分けが必要なので、間にラッパーを噛ませている。

---

## 2. ファイル一覧とパス

### 2.1 原本 (このリポジトリ)

```
~/colcon_ws/src/
├── PS5コントローラー_README.md          ← このファイル
├── antimicrox-ps5                       ← 起動ラッパー (bash)
├── antimicrox-ps5.desktop               ← ランチャー定義
└── ps5_desktop.gamecontroller_2_2.amgp  ← プロファイル原本
```

### 2.2 配置先

| 原本 | 配置先 | 権限 | 役割 |
|---|---|---|---|
| `antimicrox-ps5` | `~/bin/antimicrox-ps5` | **755 (要実行権限)** | 状態判定・起動・終了 |
| `antimicrox-ps5.desktop` | `~/.local/share/applications/antimicrox-ps5.desktop` | 644 | ドックのメニュー |
| `ps5_desktop.gamecontroller_2_2.amgp` | `~/p2.amgp` | 644 | アプリが実際に読むプロファイル |
| (GitHub から取得) | `~/bin/antimicrox360` | **755 (要実行権限)** | AntiMicroX 本体 |

### 2.3 自動生成されるファイル

| パス | 内容 | 削除してよいか |
|---|---|---|
| `~/.antimicrox-ps5.log` | ラッパーとアプリのログ | ✅ 消しても再生成される |
| `/tmp/antimicroxSignalListener` | 多重起動判定用ソケット | ⚠️ 6.1 参照 |
| `~/.config/antimicrox/` | アプリの設定 (GUI の状態など) | ✅ |
| `/tmp/.mount_antimiXXXX/` | AppImage の展開先 | 終了時に自動削除 |

> `~/bin` は Ubuntu の `.profile` が自動で PATH に追加する。反映にはログインし直しが必要。

---

## 3. バージョンについて

### 3.1 結論

**3.6.0 を使う。3.6.1 (最新) は使えない。**

### 3.2 全バージョンの実測結果

2026-08-07 に、この環境で全バージョンにプロファイルを読ませて計測した結果。

| バージョン | リリース | プロファイル読込 | 判定 |
|---|---|---|---|
| 3.1.4 (`antimicro` パッケージ) | 2021-01-11 | 動く | ❌ 別問題あり (3.4 参照) |
| 3.3.2 | 2022-11-21 | 動く | ✅ |
| 3.3.3 | 2023-01-30 | 動く | ✅ |
| 3.3.4 | 2023-06-03 | 動く | ✅ |
| 3.4.0 | 2024-03-10 | 動く | ✅ |
| 3.4.1 | 2024-08-10 | 動く | ✅ |
| 3.5.0 | 2024-10-31 | 動く | ✅ |
| 3.5.1 | 2025-01-27 | 動く | ✅ |
| **3.6.0** | **2026-05-06** | **動く** | ✅ **採用** |
| 3.6.1 | 2026-05-24 | **不可** | ❌ |

### 3.3 なぜ 3.6.1 だけだめなのか

プロファイルを読むとき、XML パーサへのポインタ (`QXmlStreamReader*`) を別スレッドへ
渡して `InputDeviceXml::readConfig` を呼ぶ。Qt ではスレッドを跨ぐシグナルの引数は
`qRegisterMetaType` での事前登録が必要だが、それが抜けているためシグナルが配送されない。

```
[INFO]  Change joystick "DualSense Wireless Controller" profile to: "/home/kurokara/p2.amgp"
[WARN]  QObject::connect: Cannot queue arguments of type 'QXmlStreamReader*'
        (Make sure 'QXmlStreamReader*' is registered using qRegisterMetaType().)
[DEBUG] Redirecting readConfig call to antoher Thread, waiting on mutex here.
[WARN]  Could not open mutex_read_config          ← 1秒待って諦める
```

結果、**プロファイル名は表示されるのに全項目が「割り当てなし」になる**。
ファイルが読めていないのではなく、読み込み処理が起動しないまま完了扱いされる。

これは 3.6.1 で入ったリグレッション。upstream に issue はまだ無い (2026-08-07 時点)。

### 3.4 3.1.4 を使ってはいけない理由

Ubuntu 標準の `antimicro` パッケージ (中身は 3.1.4) はスレッド処理が壊れている。

```
QObject::startTimer: Timers cannot be started from another thread
QObject: Cannot create children for a parent that is in a different thread
```

- ホイールの連続スクロール用タイマーが起動できず、**スクロールが1目盛りで止まる**
- トリガーに設定したセット切り替えが、保存・読み込みを経ると動かなくなる
  ([issue #525](https://github.com/AntiMicroX/antimicrox/issues/525)、2022-10-24 に修正済み)

修正が入ったのは 3.3.0。したがって **3.3.0 以上が必須**。

### 3.5 なぜ deb でなく AppImage なのか

3.6.0 には Ubuntu 24.04 用の deb もあるが、AppImage を使う。

| | AppImage | deb |
|---|---|---|
| 導入 | ファイルを置くだけ | `sudo` 必要、システムに広がる |
| 撤退 | ファイルを消すだけ | `apt purge` + 残骸掃除 |
| 複数バージョンの併存 | できる | できない |

バージョンを固定して使う構成なので、入れ替えと撤退が軽い方を選ぶ。

---

## 4. インストール手順 (ゼロから)

### 4.1 旧バージョンの除去

Ubuntu 標準の `antimicro` パッケージが入っている場合は設定ごと削除する。
パッケージ名は `antimicro`、コマンド名は `antimicrox` とズレているので注意。

```bash
sudo apt purge -y antimicro
```

過去に別の方法で入れていた場合の残骸も消す。

```bash
rm -f ~/.local/share/applications/io.github.antimicrox.antimicrox.desktop
rm -rf "$HOME/.config/Unknown Organization"
rm -f ~/antimicrox.log /tmp/antimicroxSignalListener
```

確認 (何も出なければクリーン)。

```bash
dpkg -l | grep -i antimicro
```

### 4.2 AppImage 3.6.0 の取得

```bash
mkdir -p ~/bin
```

```bash
wget https://github.com/AntiMicroX/antimicrox/releases/download/3.6.0/AntiMicroX-x86_64.AppImage -O ~/bin/antimicrox360
```

```bash
chmod +x ~/bin/antimicrox360
```

> **`chmod +x` を忘れると `許可がありません` になる。** `wget` はただのファイルとして
> 保存するため、実行権限は自分で付ける必要がある。

確認。

```bash
~/bin/antimicrox360 --version
```

`antimicrox 3.6.0` と出れば成功。

### 4.3 プロファイルの配置

```bash
cp ~/colcon_ws/src/ps5_desktop.gamecontroller_2_2.amgp ~/p2.amgp
```

### 4.4 起動ラッパーの配置

```bash
cp ~/colcon_ws/src/antimicrox-ps5 ~/bin/ && chmod +x ~/bin/antimicrox-ps5
```

### 4.5 ランチャーの登録

```bash
mkdir -p ~/.local/share/applications
cp ~/colcon_ws/src/antimicrox-ps5.desktop ~/.local/share/applications/
update-desktop-database ~/.local/share/applications
```

アプリ一覧に「AntiMicroX (PS5)」が現れる。アイコンを右クリックして
「お気に入りに追加」でドックへ固定する。

### 4.6 動作確認

```bash
~/bin/antimicrox-ps5 gui
```

GUI が開き、割り当てが埋まっていれば成功。R2 を押しながら左スティックを動かし、
カーソルが速くなればセット切り替えも効いている。

常駐しているかの確認。

```bash
pgrep -af AppRun.wrapped
```

### 4.7 自動起動 (任意・既定では設定しない)

ログイン時に GUI 無しで常駐させたい場合のみ。

```bash
mkdir -p ~/.config/autostart && cp ~/.local/share/applications/antimicrox-ps5.desktop ~/.config/autostart/
```

解除する場合。

```bash
rm -f ~/.config/autostart/antimicrox-ps5.desktop
```

---

## 5. ドックのメニュー構成

アイコンを右クリックすると以下が出る。**このうち3項目だけがこの構成で定義したもの**で、
残りは GNOME が自動で追加する。

```
ウィンドウプレビュー...        ← GNOME が自動追加
新しいウィンドウで開く          ← GNOME が自動追加
─────────────────
GUI を表示して起動             ← antimicrox-ps5.desktop の [Desktop Action ShowGUI]
常駐開始 (GUI なし)            ← antimicrox-ps5.desktop の [Desktop Action StartTray]
完全に終了 (常駐も停止)         ← antimicrox-ps5.desktop の [Desktop Action Quit]
─────────────────
ピン留めを外す                 ← GNOME が自動追加
─────────────────
終了                          ← GNOME が自動追加 (ウィンドウがあるときだけ表示)
```

### 5.1 「終了」が2つある理由

- **下の「終了」** … GNOME 組み込み。ウィンドウに閉じる要求を送るだけ。
  **GUI 無しで常駐しているときはメニューに現れない。**
- **「完全に終了 (常駐も停止)」** … この構成で定義したもの。プロセスを直接終了させ、
  残留ソケットも削除する。常駐中でも使える。応答しなくなった場合は `kill -9` まで行う。

GUI 無しで常駐させているときは後者しか使えないため、両方残している。
名前が同じだと区別できないので、後者は「完全に終了」に改名してある。

### 5.2 「ディスクリートグラフィックスを使用して起動」について

このマシンは GPU を2つ持つ (Intel UHD + NVIDIA RTX A3000)。`switcheroo-control` が
それを検出すると、GNOME は**全アプリ**の右クリックメニューにこの項目を自動で追加する。

**AntiMicroX では使わないこと。** 入力を変換するだけのアプリで GPU 性能は無関係、
NVIDIA 側で起動しても消費電力と発熱が増えるだけ。この項目は消せない (GNOME が一律で付ける)。

### 5.3 クリック時の挙動

| 操作 | 引数 | 動作 |
|---|---|---|
| **左クリック (既定)** | なし | 未起動 → **GUI 無しで常駐開始**<br>常駐中 (ウィンドウ無し) → GUI 付きで起動し直す<br>ウィンドウ有り → 何もしない (GNOME が前面化する) |
| GUI を表示して起動 | `gui` | 未起動 → ウィンドウ付きで起動 / 起動中 → 上と同じ |
| 常駐開始 (GUI なし) | `start` | 未起動のときだけ常駐開始。起動中なら何もしない |
| 完全に終了 | `quit` | プロセスを終了しソケットを削除 |

### 5.4 ウィンドウの閉じ方

| 操作 | 動作 |
|---|---|
| `[-]` 最小化 | ウィンドウが消える。**常駐は継続し、コントローラー操作も効いたまま** |
| `[×]` 閉じる | **アプリが完全に終了する**。コントローラー操作も止まる |

この挙動は**ラッパーが常に `--no-tray` を付けている**ことで成立している。
トレイが有効だと `[×]` は「トレイへ格納」の意味になるが、
**Ubuntu 24.04 の GNOME にはトレイが無い**ため、ウィンドウが消えたのに終了できない
状態になってしまう。`--no-tray` にすることで `[×]` が素直な終了になる。

---

## 6. ラッパーの実装ノート

`~/bin/antimicrox-ps5` の設計上、押さえておくべき点。

### 6.1 プロセス名は `antimicrox` ではない

AppImage は `/tmp/.mount_antimiXXXX/` に展開した本体を実行し直すため、
**`pgrep -x antimicrox` は決してマッチしない。** 実際のプロセスは2つ。

```
AppRun.wrapped   /tmp/.mount_antimiXXXX/AppRun.wrapped --profile /home/kurokara/p2.amgp --no-tray
antimicrox360    /home/kurokara/bin/antimicrox360 --profile /home/kurokara/p2.amgp --no-tray
```

### 6.2 `pgrep -f` を使ってはいけない

`pgrep -f` / `pkill -f` はコマンドライン全体への部分一致なので、
**その文字列を引数に含むだけの無関係なプロセスまで巻き込む。**
実際、検証中に `pkill -f "mount_antimi.*AppRun"` が検証スクリプト自身を kill する事故が起きた。

プロセス名の完全一致 `pgrep -x` で候補を絞り、その上で `/proc/PID/cmdline` を読んで
他の AppImage と区別する。

### 6.3 判定にはプロファイルのパスも使う

展開先の名前は AppImage のファイル名で決まる。別名で置くと
`/tmp/.mount_<別名>XXXX/` となり、`antimi` という文字列が現れない。

| ファイル名 | 展開先 | `antimi` を含むか |
|---|---|---|
| `antimicrox360` | `/tmp/.mount_antimiXXXX/` | ✅ |
| `am3.3.4` (検証用に置いた例) | `/tmp/.mount_am3.3.4XXXX/` | ❌ |

これを取りこぼすと、**終了させたはずなのにコントローラーが効き続ける**。
実際にこの事故が起きた (別バージョンの検証インスタンスが残り、Steam の競合を疑った)。
そのため `~/p2.amgp` を掴んでいるプロセスも管轄とみなして終了させる。

### 6.4 `--show` は機能しない

「2回目の起動時に引数が既存インスタンスへ転送されるので `--show` でウィンドウが出る」
という想定は**成立しない**。3.3.2 / 3.5.1 / 3.6.0 のいずれでも、
ソケット接続までは成功するが `AntiMicroX is already running.` を出して終わる。

そのため以下の方式にしている。

- ウィンドウが実在する (最小化含む) → 何もしない。GNOME がドックのクリックで復帰させる
- ウィンドウが無い (GUI 無しで常駐中) → 一度終了して GUI 付きで起動し直す

後者は 2〜3 秒コントローラー操作が途切れるが、`--show` が使えない以上これが確実。
ウィンドウの存在は `xprop -root _NET_CLIENT_LIST` から `WM_CLASS` を見て判定する
(最小化されたウィンドウもこのリストには残る)。

### 6.5 `StartupWMClass` が必須

`.desktop` に以下が無いと、ドックのランチャーとは別に「実行中アプリ」のアイコンが
並んでしまい、**アイコンが2つに割れる。**

```ini
StartupWMClass=antimicrox
```

実測した値は `WM_CLASS(STRING) = "AppRun.wrapped", "antimicrox"`。

### 6.6 残留ソケットの掃除

`/tmp/antimicroxSignalListener` は多重起動判定に使われる。
**プロセスが居ないことを確認してから消す。** 生きているうちに消すと多重起動を許してしまう
(検証中に6インスタンスが同時に生き残った)。

### 6.7 `setsid` で端末から切り離す

これが無いと、ターミナルから起動した場合にターミナルを閉じると一緒に落ちる。

```bash
setsid "$APP" --profile "$PROFILE" --no-tray "$@" >>"$LOG" 2>&1 &
```

### 6.8 ログを残す

呼び出しのたびに引数・プロセス状態・ソケット状態を `~/.antimicrox-ps5.log` へ記録する。
AntiMicroX 本体の出力も同じファイルへ流すため、起動失敗の原因を後から追える。

---

## 7. プロファイルの内容

3セット構成。L2 / R2 の押し込みで速度を切り替える。

| セット | 入り方 | マウス速度 | スクロール速度 |
|---|---|---|---|
| Set 1 通常 | — | 60 | 15 |
| Set 2 高速 | **R2 長押し** | 175 | 40 |
| Set 3 低速 | **L2 長押し** | 20 | 5 |

### 7.1 ボタン割り当て

| PS5 操作 | 割り当て |
|---|---|
| 左スティック | マウスカーソル移動 |
| 右スティック | スクロール (縦横) |
| ○ | 左クリック |
| × | Enter |
| □ | Ctrl + C |
| △ | Ctrl + V |
| 十字キー | 矢印キー |
| SHARE | Esc |
| OPTIONS | Alt + Tab |
| L1 | Backspace |
| R1 | Delete |
| L3 押し込み | Shift |
| R3 押し込み | 右クリック |
| PS ボタン | Print |
| タッチパッド押し込み | `/usr/bin/onboard` を起動 (画面キーボード) |
| L2 / R2 | 速度切り替え (上表) |

> タッチパッド押し込みで出る画面キーボードは **Onboard** という別アプリ
> (`onboard` パッケージ)。プロファイルの3セットすべてに割り当てられている。

### 7.2 編集時の注意点

プロファイルを手で編集する場合、以下は必須。

**トリガーの `throttle` は必ず `positivehalf`。** DualSense の L2 / R2 は静止位置が
`-32767` のため、`normal` にすると「離した状態＝負方向フル入力」と誤判定され、
セット切り替えが暴走する。

```xml
<trigger index="5">
    <throttle>positivehalf</throttle>
    <triggerbutton index="2">   <!-- 押し込み方向は index 2 のみ -->
```

**右スティックは8方向すべてに割り当てる。** 斜め方向 (`stickbutton` の 2・4・6・8) を
空にすると、少し斜めに倒しただけで無反応ゾーンに入り、スクロールが止まる。
斜めには隣接する2方向のホイールを同時に割り当てる。

**セット切り替えの戻り側は AntiMicroX が自動生成する。** Set 1 に
「While Held で Set 2 へ」と書くと、Set 2 側に「While Held で Set 1 へ」が自動で追加される。
手で消しても保存時に復活するので、消そうとしないこと。

### 7.3 編集内容の反映

**アプリが読むのは `~/p2.amgp` であって原本ではない。**

原本を編集したらコピーする。

```bash
cp ~/colcon_ws/src/ps5_desktop.gamecontroller_2_2.amgp ~/p2.amgp
```

GUI から「保存」した場合の保存先も `~/p2.amgp` になる。原本には反映されないので、
GUI で調整したら原本へ吸い上げる。

```bash
cp ~/p2.amgp ~/colcon_ws/src/ps5_desktop.gamecontroller_2_2.amgp
```

---

## 8. 既知の問題と対処

### 8.1 「AntiMicroX is already running.」と出て起動できない

AntiMicroX は `/tmp/antimicroxSignalListener` への接続可否で多重起動を判定する。
**この判定はソケットの削除処理より先に走る**ため、異常終了でファイルが残ると
以後永久に起動できなくなる。アプリ自身では復帰できない。

```bash
rm -f /tmp/antimicroxSignalListener
```

ラッパーが起動前に自動で掃除するため、通常は意識しなくてよい。
この判定処理はどのバージョンでも同じなので、バージョンを上げても解決しない。

### 8.2 終了させたのにコントローラーが動き続ける

**まず別バージョンのインスタンスが残っていないか確認する。** Steam を疑う前にこちら。

```bash
ps -eo pid,args | grep AppRun.wrapped | grep -v grep
```

出てきたら終了させる。

```bash
~/bin/antimicrox-ps5 quit
```

これで消えない場合 (別名 AppImage を直接起動した場合など) は PID を指定する。

```bash
kill <PID>
```

### 8.3 Steam との競合

Steam には「デスクトップ設定」があり、コントローラー接続時に自動で
「左スティック＝マウス、右スティック＝スクロール」を有効にする。両方が有効だと入力が二重に飛ぶ。

ただし **Steam が起動していなければ競合しない。** まず起動の有無を確認する。

```bash
pgrep -x steam && echo "Steam が動作中 → 競合の可能性あり" || echo "Steam は停止中 → 競合しない"
```

Steam を終了してカーソルが止まるなら Steam が原因。
`Steam → 設定 → コントローラ` からデスクトップ設定を無効にする。

> このマシンでは Steam はインストール済みだが**自動起動しない** (`~/.config/autostart/` に無い)。
> 意図的に起動しない限り問題は起きない。

### 8.4 GNOME にシステムトレイが無い

Ubuntu 24.04 の GNOME には標準でトレイが存在しない。`--tray` を付けても常駐アイコンは
表示されないため、**GUI 無しで起動すると見た目上は何も起きない**。
この構成では `--no-tray` を使うことで、そもそもトレイに依存しない設計にしている (5.4 参照)。

動作しているかは以下で確認する。

```bash
pgrep -af AppRun.wrapped
```

### 8.5 `QCommandLineParser: option not defined: "next"`

AntiMicroX 内部のオプション定義漏れによる警告。実害は無く、無視してよい。

### 8.6 GUI に「Accelerometer」「Gyroscope」が表示される

DualSense のセンサーを AntiMicroX が認識しているだけで、異常ではない。割り当ては不要。

### 8.7 ドックのメニューが更新されない

GNOME Shell は `.desktop` をキャッシュする。`update-desktop-database` を実行しても
反映されない場合は、ピン留めを一度外して再度お気に入りに追加するか、再ログインする。

---

## 9. トラブル時の調査手順

```bash
# 1. 動いているか
pgrep -af AppRun.wrapped

# 2. ラッパーの判定履歴とアプリの出力
tail -50 ~/.antimicrox-ps5.log

# 3. 残留ソケットの有無
ls -l /tmp/antimicroxSignalListener

# 4. バージョン確認
~/bin/antimicrox360 --version

# 5. プロファイル読み込みが壊れていないか (何も出なければ正常)
~/bin/antimicrox360 --profile ~/p2.amgp --log-level debug 2>&1 | grep -iE "mutex|cannot queue|another thread"

# 6. セッションが X11 か (wayland だと動かない)
echo $XDG_SESSION_TYPE

# 7. コントローラーが OS に見えているか
ls /dev/input/js*
grep -i "Name=.*DualSense" /proc/bus/input/devices
```

手順5で `mutex` や `cannot queue` が出た場合はバージョンが 3.6.1 になっている。
`another thread` が出た場合は 3.1.4 に戻っている。いずれも 3.6.0 を入れ直す。

---

## 10. アンインストール

```bash
~/bin/antimicrox-ps5 quit
rm -f ~/bin/antimicrox360 ~/bin/antimicrox-ps5
rm -f ~/.local/share/applications/antimicrox-ps5.desktop
rm -f ~/.config/autostart/antimicrox-ps5.desktop
rm -f ~/p2.amgp ~/.antimicrox-ps5.log /tmp/antimicroxSignalListener
rm -rf ~/.config/antimicrox
update-desktop-database ~/.local/share/applications
```

`sudo` は不要。すべてホームディレクトリ内で完結する。
