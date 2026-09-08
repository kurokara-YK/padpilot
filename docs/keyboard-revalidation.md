# 画面キーボードの再検証 — Codex、2026-09-09

## 結論

**この Linux/X11 環境では、自作キーボードを本採用する必要は現時点でない。**
インストール済み onboard の `org.onboard.keyboard input-event-source` を
`XInput` から `GTK` に変更すると、クラッシュを回避して文字入力できた。
自動表示と、日本語の変換・確定まで GTK 入力欄と Chrome のローカルページで確認した。

AGENTS.md §6.2.9 の「設定では直らない」「onboard 不採用」を撤回し、
§6.2.10 に **「Codexで修正」** と変更理由を記した。以前の実測記録は残した。

キー送出の **XTest** と、ポインタ受信の **XInput / GTK** は別の設定・機構。
今回変えたのは後者であり、IME やキーボードレイアウトを作り直してはいない。
GTK モードも内部では X11 を使用するため、「X11を使わなくした」という意味ではない。

## 環境と比較方法

- Linux、GNOME/X11 (`DISPLAY=:1`)、Python 3.12、PySide6 6.11.1。
- onboard 1.4.1 系のシステムインストール、ibus/mozc (`mozc-jp`)。
- 3 画面: eDP-1 1920×1080、DP-1-0 2560×1440、HDMI-1-0 3440×1440。
- `tests/keyboard_probe.py` の制御プロセスは QApplication を生成しない。
  入力先とキーボードは別プロセスにし、キー送出単体の対照実験を先に実行する。
- 入力先は試験専用の GTK Entry、または独立した一時プロファイルの Chrome。
  Chrome は `data:` のローカルページだけを開き、DOM の入力値を記録する。
- 自作版は Qt の実ボタン位置、onboard はシステムの Onboard ライブラリが計算した
  キー位置を取得する。onboard の試験用サブクラスは状態を記録するだけで、
  ポインタ処理・キー送出を置き換えない。インストール済みのファイルも変更しない。
- マウス移動と押下・解放は X11 経由。毎回、入力先のフォーカスと
  ポインタ直下のウィンドウ ID を検査する。想定外なら次の入力を中止する。
- 「プロセスが生存」「表示されている」「文字が入った」は別々に記録する。
  表示の判定は最終版では mapped 状態、onboard 内部の可視状態、透明度を確認する。
- onboard の比較設定は `GSETTINGS_BACKEND=memory` で試験プロセス内に限定する。
  通常利用の設定への修正適用は別途行い、適用前の値を保存した。

## 再検証結果

| 検証項目 | 今回の観測 | 判定・範囲 |
|---|---|---|
| QApplication なしの直接送出 | GTK の専用入力欄に `asd` | 成功 |
| 自作 Qt の表示・ホバー・実クリック | `a` → `as` → `asd`、入力欄のフォーカス維持 | **変更前の自作コードで成功** |
| onboard / XInput | 最初のキー操作付近で SIGSEGV、直接起動の終了値 `-11` | クラッシュ再現 |
| onboard / XInput、gdb | ホバー時に SIGSEGV、osk C 拡張を経由したスタック | イベント受信経路が有力。内部の破損原因までは未確定 |
| onboard / GTK | `a` → `as` → `asd`、生存・フォーカス維持 | 成功 |
| onboard / GTK、編集キー | `asd` → Backspace → 空白 → `a` → Enter、結果 `as a`、Entry の activate も記録 | 成功 |
| onboard / GTK、mozc | 実クリックの `ai` → 空白 → Enter → `aiueo` → Enter で `愛あいうえお` | 変換・確定成功 |
| 自動表示 / GTK / primary | 非テキストボタンへフォーカスすると非表示、入力欄へ戻すと表示。その後文字入力 | 成功 |
| 3画面移動 / GTK / primary | 入力先と別画面のキーボードを操作し、3画面間を移動しても生存・表示維持 | 成功 |
| `docking-monitor=active` / GTK | `asd` 入力後、3画面間を移動しても表示維持 | **以前の消失は再現せず** |
| `tablet-mode-detection-enabled=true` / GTK | 自動表示、`asd` 入力、3画面移動が成立 | **以前の消失は今回の条件では再現せず** |
| `hide-on-key-press=true` / GTK | 外部から space を送った2秒後も表示。後続の試行はポインタの外部移動で中断 | 「必ず即座に消える」は確認できず。継続操作は未判定 |
| Chrome / GTK / mozc / auto-show | 入力欄で自動表示、`愛あいうえお` の変換・確定、画面移動後も表示 | **成功**。テスト用ページの通常の input 要素 |
| 現在のPCの修正後診断 | GTK方式・自動表示などを読み直す | キーボード関連の問題は0件 |

GTK 側の成功は、単一のクリックだけでなく、独立起動した英数・編集・日本語・
自動表示・ブラウザの複数試行で確認した。無期限の安定性を保証する試験ではない。

### gdb の主要部分

```text
Thread 1 "python3" received signal SIGSEGV, Segmentation fault.
#0 PyObject_Malloc ()
#1 _PyObject_New ()
#2 ... Onboard/osk.cpython-312-x86_64-linux-gnu.so
#3 ... Onboard/osk.cpython-312-x86_64-linux-gnu.so
#4 ... libgdk-3.so.0
#5 ... libgdk-3.so.0
#6 gdk_display_get_event ()
```

gdb 自身は調査完了後に終了値 0 を返したが、これは onboard が正常終了した意味ではない。
SIGSEGV の記録と、onboard を直接起動した試行の `-11` を併記する。

## 検証スクリプトの不備と中断も記録する

過去のテストは `padpilot` の部分一致でウィンドウを選んでいた。
メイン画面とキーボードを区別できない。また、10列のキーボードを11列として
座標計算し、高さも不均等な行を均等割りしていた。Enterでダイアログを閉じないと
結果を取得できないため、入力と確定の失敗も区別できなかった。
これらを直した再検証では、自作版の英字入力は成立した。

今回作った検証スクリプトにも以下の不備があり、修正してから再実行した。
失敗試行をキーボード本体の不具合として数えていない。

1. onboard の import 時に試験用 `--worker` 引数が解釈された。
   onboard 用の引数を import 前に設定して修正。
2. IMEの未確定文字を残したまま入力欄の文字列だけを消し、後で文字が現れた。
   対照実験で確定まで行い、GTKの入力コンテキストもリセットするよう修正。
   英数モードなら半角全角キーで切り替え、`あいうえお` の実入力を確認する。
3. 一時設定側の `toolkit-accessibility` が false で、onboard が確認ダイアログで待った。
   最初は起動遅延を疑って待機時間を8秒から25秒に延ばしたが解消せず、
   ソースの `check_gnome_accessibility()` を確認して一時設定を揃えた。
4. フォーカスを外す指示の完了前に、入力欄へ戻す指示を上書きしていた。
   対象側の完了通知を待つよう修正。自動表示・非表示が成立した。
5. ポインタ待機中に外部から位置が変わる試行があった。
   例: 指定位置 `(1293,2351)` に対し実位置 `(1071,2190)`。
   誤った場所をクリックせず中断し、利用者に操作を止めてもらったブラウザ試行は成功。

## 修正したところ

- `core/install.py`: 導入時の設定に `input-event-source=GTK` を追加。
  アンインストール時は既存の設定撤去方式に合わせ、このキーも既定へ戻す。
- `core/doctor.py`: XInput 設定を個別の問題として検出し、GTKへ修正。
  設定書き込みが失敗した場合は成功扱いしない。
- `docking-monitor=active` を、自動表示が無効である証拠として扱うのをやめた。
  診断の修正処理は利用者の表示先を上書きしない。
- GUIと説明文の「activeなら消える」「タブレット判定が有効なら必ず消える」などの
  断定を修正。導入時の既定は検証済みの `primary`、キー入力時の非表示なし、
  タブレット判定なしを維持する。
- 自作版は実験用として保持。Windows の説明を、実際の未検証の `keybd_event` に訂正。

現在のPCにはGTK方式と自動表示の修正を適用済み。
変更前の値（未設定と明示設定の区別を含む）は
`/tmp/padpilot-keyboard-settings-before-codex.json` に保存した。
元から `primary` だった表示先は維持されている。
通常の `/usr/bin/onboard` も起動し、生存とD-Busサービスの登録を確認した。
利用者がそのまま試せるよう、この通常起動のプロセスは残している。
ログは `/tmp/padpilot-onboard-after-fix.log`。
snap Discord に対するAT-SPIのAppArmor警告は残るため、そのアプリでの動作は未検証とする。

変更後の回帰テスト5件、`pyflakes core gui tests`、ブラウザ検証用JavaScriptの
構文検査、`git diff --check` はすべて通過した。

## 再実行

X11の実デスクトップに接続できる環境で、リポジトリのルートから実行する。
**実マウスを動かすため、実行中はマウス・ゲームパッドを操作しない。**
出力先は毎回別の `/tmp/padpilot-probe-*`。終了時は自分で起動したプロセス群だけを閉じる。
フォーカスとポインタ位置も終了時に復帰する。
既存のonboardを閉じてから比較を行うこと（複数のOSKの自動表示を競合させない）。
自動表示の検証ではセッション側の支援技術も有効になっている必要がある。

```sh
python3 tests/keyboard_probe.py --backend qt
python3 tests/keyboard_probe.py --backend onboard --event-source XInput
python3 tests/keyboard_probe.py --backend onboard --event-source XInput --gdb
python3 tests/keyboard_probe.py --backend onboard --event-source GTK
python3 tests/keyboard_probe.py --backend onboard --event-source GTK \
  --keys a,s,d,BackSpace,space,a,Return --expected 'as a'
python3 tests/keyboard_probe.py --backend onboard --event-source GTK --japanese \
  --keys a,i,space,Return,a,i,u,e,o,Return --expected '愛あいうえお'
python3 tests/keyboard_probe.py --backend onboard --event-source GTK --auto-show
python3 tests/keyboard_probe.py --backend onboard --event-source GTK --auto-show --monitor active
python3 tests/keyboard_probe.py --backend onboard --event-source GTK --auto-show --tablet-detection
python3 tests/keyboard_probe.py --backend onboard --event-source GTK --target chrome \
  --japanese --auto-show --keys a,i,space,Return,a,i,u,e,o,Return --expected '愛あいうえお'
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m pyflakes core gui tests
```

Chrome試験には `/usr/bin/google-chrome` と WebSocket を標準搭載した Node.js が必要。
CDPは一時プロファイルのローカルポートへ接続する。既存のブラウザプロファイルは使わない。
日本語試験は ibus/mozc が選択されている前提。変換候補の学習によって `愛` 以外になる場合は、
実際の文字を読んで判断する。単に「何か入れば成功」とはしていない。

主要試行の機械可読ログは [keyboard-revalidation-results.json](keyboard-revalidation-results.json)。
一時ディレクトリ名も残し、同じ試行の stderr と照合できるようにした。

## 未検証・保留

- 物理DualSenseのスティック・ボタンからAntiMicroXを経由した一連の操作。
  今回の自動検証はX11のマウス・キーイベントを使った。実機の操作感や誤入力は別途確認する。
- Chromeのアドレスバー候補ポップアップ、Firefox、snap版の入力欄、各種ダイアログ、長時間利用。
  onboard自身の設定説明にも、GTK方式にはポインタグラブに関する制約があると記されている。
  通常のブラウザ入力欄の成功から全アプリの成功とは判断しない。
- `touch-input=single/none` や `force-to-top` の全組合せは今回再実行していない。
  以前の記録は残し、今回のGTK切替との比較に混ぜない。
- GNOME内蔵OSK / xvkbdの実動作比較は今回行っていない。
  onboardで主要要件が成立したため、自作や他のOSKへ切り替える根拠は現時点でない。
- Windows、Wayland、自作版の日本語UI・IME切替・自動表示は未検証。

## 参照した一次情報

- インストール済み `/usr/share/glib-2.0/schemas/org.onboard.gschema.xml`:
  `input-event-source` の説明はGTKを安全側の選択肢としている。
- インストール済み `Onboard/TouchInput.py`: GTK/XInput のイベント受信登録を切り替える実装。
- インストール済み `Onboard/Config.py`: 自動表示時の支援技術の確認処理。
- インストール済み `/usr/bin/onboard`: ライセンス文には改変許可が明記されている。
- [GNOMEの画面キーボードの説明](https://help.gnome.org/gnome-help/keyboard-osk.html):
  内蔵OSKは候補に残す。ただし説明の存在をこのX11環境での実測の代用にはしない。
