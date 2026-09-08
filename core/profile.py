"""プロファイル (.amgp) の読み取りと説明 (AGENTS.md §7.2)。

OS 非依存。XML を読むだけで、編集器は作らない (§7.8)。
"""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from . import paths

# Qt のキーコード → 表示名。プロファイルに現れるものだけ。
QT_KEYS = {
    "0x1000000": "Esc",
    "0x1000003": "Backspace",
    "0x1000004": "Enter",
    "0x1000007": "Delete",
    "0x1000009": "Tab",
    "0x1000020": "Shift",
    "0x1000021": "Ctrl",
    "0x1000023": "Alt",
    "0x1000012": "←",
    "0x1000013": "↑",
    "0x1000014": "→",
    "0x1000015": "↓",
    "0x1000001": "Tab",
    "0x43": "C",
    "0x56": "V",
    "0x41": "A",
    "0x58": "X",
    "0x5a": "Z",
}


def _key_name(code: str) -> str:
    """Qt キーコードを表示名にする。KEYS の逆引き。"""
    code = code.strip().lower()
    for name, c in KEYS.items():
        if c.lower() == code:
            return name
    # 数値として解釈できる ASCII はその文字にする
    try:
        n = int(code, 16) if code.startswith("0x") else int(code)
    except ValueError:
        return code
    if 0x21 <= n <= 0x7E:
        return chr(n).upper()
    return code


def _mouse_name(code: str) -> str:
    for name, c in MOUSE_ACTIONS.items():
        if c == code.strip():
            return name
    return f"マウス{code}"


# DualSense の物理ボタン名。SDL の GameController 抽象での index。
# 機種が変わっても index は同じで、刻印だけが違う (AGENTS.md §1.1)。
BUTTON_NAMES = {
    1: "×ボタン", 2: "○ボタン", 3: "□ボタン", 4: "△ボタン",
    5: "L1", 6: "R1", 7: "SHARE", 8: "OPTIONS",
    9: "PS ボタン", 10: "L3 (左スティック押し込み)",
    11: "R3 (右スティック押し込み)",
    21: "タッチパッド押し込み",
}


def _fmt_slot(slot: ET.Element) -> str:
    """1 つの割り当てを人間が読める形にする。"""
    mode = (slot.findtext("mode") or "").strip()
    code = (slot.findtext("code") or "").strip()
    if mode == "keyboard":
        return _key_name(code)
    if mode == "mousebutton":
        return _mouse_name(code)
    if mode == "execute":
        path = (slot.findtext("path") or "").strip()
        if not path:
            return "起動"
        name = Path(path).name
        # 選択肢の表示名と一致させる。一致しないと GUI のプルダウンで
        # 「候補に無い現在値」として重複表示されてしまう。
        if name in ("onboard", "squeekboard", "florence"):
            return "画面キーボードを出す"
        return f"起動: {name}"
    return mode or code


def describe_bindings(profile: Path | None = None) -> list[tuple[str, str]]:
    """既定の割り当てを (操作, 割り当て) の一覧で返す。

    セットアップ画面で「何がどうなるか」を見せるため。
    Set 1 (通常) のみを対象にする。速度切り替えは別途説明する。
    """
    src = profile or paths.source_profile()
    if not src.exists():
        return []
    try:
        root = ET.parse(src).getroot()
    except ET.ParseError:
        return []

    rows: list[tuple[str, str]] = [
        ("左スティック", "カーソル移動"),
        ("右スティック", "スクロール"),
        ("十字キー", "矢印キー"),
    ]

    first_set = root.find("./sets/set")
    if first_set is None:
        return rows

    for btn in first_set.findall("button"):
        try:
            idx = int(btn.get("index", "0"))
        except ValueError:
            continue
        slots = btn.findall("./slots/slot")
        if not slots:
            continue
        label = BUTTON_NAMES.get(idx, f"ボタン {idx}")
        action = " + ".join(_fmt_slot(s) for s in slots)
        # 届かないボタンは注記する (AGENTS.md §5.2)
        if idx == 21:
            action += "  ※現在は動作しません"
        rows.append((label, action))

    rows.append(("R2 押しっぱなし", "カーソル高速 (175)"))
    rows.append(("L2 押しっぱなし", "カーソル低速 (20)"))
    return rows


def set_speeds(profile: Path | None = None) -> dict[str, int]:
    """各セットのマウス速度を返す。"""
    src = profile or paths.source_profile()
    if not src.exists():
        return {}
    try:
        root = ET.parse(src).getroot()
    except ET.ParseError:
        return {}
    out: dict[str, int] = {}
    labels = {1: "通常", 2: "高速", 3: "低速"}
    for st in root.findall("./sets/set"):
        try:
            i = int(st.get("index", "0"))
        except ValueError:
            continue
        sp = st.find(".//stickbutton/mousespeedx")
        if sp is not None and sp.text:
            out[labels.get(i, str(i))] = int(sp.text)
    return out


# 割り当てできるキーの一覧 (表示名 -> Qt キーコード)。
# AntiMicroX が扱えるものを網羅する。GUI はここから選択肢を作る。
KEYS: dict[str, str] = {}

# 文字キー
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    KEYS[_c] = hex(ord(_c))
for _c in "0123456789":
    KEYS[_c] = hex(ord(_c))

# ファンクションキー (F1-F35)。Qt では 0x1000030 から連番。
for _i in range(1, 36):
    KEYS[f"F{_i}"] = hex(0x1000030 + _i - 1)

# 記号
KEYS.update({
    "スペース": "0x20", "-": "0x2d", "=": "0x3d", "[": "0x5b", "]": "0x5d",
    "\\": "0x5c", ";": "0x3b", "'": "0x27", ",": "0x2c", ".": "0x2e",
    "/": "0x2f", "`": "0x60",
})

# 特殊キー
KEYS.update({
    "Enter": "0x1000004", "Esc": "0x1000000", "Tab": "0x1000001",
    "Backspace": "0x1000003", "Delete": "0x1000007", "Insert": "0x1000006",
    "Home": "0x1000010", "End": "0x1000011",
    "PageUp": "0x1000016", "PageDown": "0x1000017",
    "↑": "0x1000013", "↓": "0x1000015", "←": "0x1000012", "→": "0x1000014",
    "Shift": "0x1000020", "Ctrl": "0x1000021", "Alt": "0x1000023",
    "Meta (Windows)": "0x1000022", "CapsLock": "0x1000024",
    "PrintScreen": "0x1000009", "Pause": "0x1000008", "Menu": "0x1000055",
    "半角/全角": "0x1001262", "変換": "0x1001261", "無変換": "0x1001263",
})

MOUSE_ACTIONS: dict[str, str] = {
    "左クリック": "1", "中クリック": "2", "右クリック": "3",
    "ホイール上": "4", "ホイール下": "5",
    "ホイール左": "6", "ホイール右": "7",
    "戻る (第4ボタン)": "8", "進む (第5ボタン)": "9",
}

# よく使う組み合わせ。任意の組み合わせは GUI から作れる。
PRESETS: list[str] = [
    "Ctrl + C", "Ctrl + V", "Ctrl + X", "Ctrl + Z", "Ctrl + Y",
    "Ctrl + A", "Ctrl + S", "Ctrl + F", "Ctrl + W", "Ctrl + T",
    "Alt + Tab", "Alt + F4", "Ctrl + Shift + T",
    "Ctrl + PageUp", "Ctrl + PageDown",
]

SPECIAL = {
    "画面キーボードを出す": ("execute", "onboard"),
    "割り当てなし": ("none", ""),
}


def _parse_combo(label: str) -> list[str] | None:
    """"Ctrl + C" のような表示名をキーコードの並びにする。

    未知のキー名が混ざっていれば None を返す (組み合わせとして扱わない)。
    """
    if "+" not in label:
        return None
    parts = [p.strip() for p in label.split("+")]
    codes = []
    for p in parts:
        if p not in KEYS:
            return None
        codes.append(KEYS[p])
    return codes


def choice_labels() -> list[str]:
    """GUI のプルダウンに出す選択肢。

    よく使うものを先頭に、その後に全キーを並べる。
    """
    out: list[str] = ["割り当てなし"]
    out += list(MOUSE_ACTIONS.keys())
    out += PRESETS
    out.append("画面キーボードを出す")
    out += [k for k in KEYS if k not in out]
    return out


def current_label(button_index: int, profile: Path | None = None) -> str:
    """あるボタンの現在の割り当てを表示名で返す。"""
    src = profile or paths.source_profile()
    if not src.exists():
        return "割り当てなし"
    try:
        root = ET.parse(src).getroot()
    except ET.ParseError:
        return "割り当てなし"
    st = root.find("./sets/set")
    if st is None:
        return "割り当てなし"
    for btn in st.findall("button"):
        if btn.get("index") != str(button_index):
            continue
        slots = btn.findall("./slots/slot")
        if not slots:
            return "割り当てなし"
        return " + ".join(_fmt_slot(s) for s in slots)
    return "割り当てなし"


def _slot_elements(label: str) -> list[ET.Element]:
    """表示名から <slot> 要素の並びを作る。

    対応する形:
      - マウス操作      (MOUSE_ACTIONS)
      - 単独キー        (KEYS)
      - 組み合わせ      "Ctrl + Shift + T" のように任意個
      - 特殊            画面キーボード / 割り当てなし
    """
    out: list[ET.Element] = []

    if label in SPECIAL:
        mode, code = SPECIAL[label]
        if mode == "none":
            return out
        el = ET.Element("slot")
        path = shutil.which(code) or f"/usr/bin/{code}"
        ET.SubElement(el, "path").text = path
        ET.SubElement(el, "mode").text = "execute"
        return [el]

    if label in MOUSE_ACTIONS:
        el = ET.Element("slot")
        ET.SubElement(el, "code").text = MOUSE_ACTIONS[label]
        ET.SubElement(el, "mode").text = "mousebutton"
        return [el]

    combo = _parse_combo(label)
    if combo:
        for code in combo:
            el = ET.Element("slot")
            ET.SubElement(el, "code").text = code
            ET.SubElement(el, "mode").text = "keyboard"
            out.append(el)
        return out

    if label in KEYS:
        el = ET.Element("slot")
        ET.SubElement(el, "code").text = KEYS[label]
        ET.SubElement(el, "mode").text = "keyboard"
        return [el]

    return out


def apply_bindings(changes: dict[int, str], src: Path, dst: Path) -> None:
    """割り当ての変更を適用して dst へ書き出す。

    changes: {ボタン index: 表示名}
    全セットに同じ変更を反映する。セットごとに違う割り当ては扱わない
    (速度切り替え以外でセットを使い分けていないため)。
    """
    tree = ET.parse(src)
    root = tree.getroot()

    for st in root.findall("./sets/set"):
        for idx, label in changes.items():
            btn = None
            for b in st.findall("button"):
                if b.get("index") == str(idx):
                    btn = b
                    break
            if btn is None:
                btn = ET.SubElement(st, "button")
                btn.set("index", str(idx))
            for old in btn.findall("slots"):
                btn.remove(old)
            slots_el = ET.SubElement(btn, "slots")
            for el in _slot_elements(label):
                slots_el.append(el)

    dst.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="UTF-8", xml_declaration=True)


def editable_buttons() -> list[tuple[int, str]]:
    """GUI で編集させるボタン。

    タッチパッド押し込み (21) は AntiMicroX に届かないので出さない
    (AGENTS.md §5.2)。
    """
    return [(i, BUTTON_NAMES[i]) for i in
            (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11)]


def make_combo(keys: list[str]) -> str | None:
    """キー名の並びから組み合わせの表示名を作る。

    GUI の「組み合わせを作る」で使う。未知のキーが混ざれば None。
    """
    if not keys:
        return None
    for k in keys:
        if k not in KEYS:
            return None
    return " + ".join(keys)


def is_valid_label(label: str) -> bool:
    """その表示名を割り当てとして書けるか。"""
    return bool(
        label in SPECIAL or label in MOUSE_ACTIONS
        or label in KEYS or _parse_combo(label))


# --- セット (プロファイル切り替え) -------------------------------------

def set_names(profile: Path | None = None) -> list[tuple[int, str]]:
    """セットの一覧を返す。

    AntiMicroX は 1 つのプロファイルに複数セットを持てる。
    既定は 3 つで、L2/R2 で速度を切り替えている。
    """
    src = profile or paths.source_profile()
    if not src.exists():
        return []
    try:
        root = ET.parse(src).getroot()
    except ET.ParseError:
        return []
    labels = {1: "通常", 2: "高速", 3: "低速"}
    out = []
    for st in root.findall("./sets/set"):
        try:
            i = int(st.get("index", "0"))
        except ValueError:
            continue
        out.append((i, labels.get(i, f"セット {i}")))
    return out


def bindings_for_set(set_index: int,
                     profile: Path | None = None) -> dict[int, str]:
    """指定セットのボタン割り当てを返す。"""
    src = profile or paths.source_profile()
    if not src.exists():
        return {}
    try:
        root = ET.parse(src).getroot()
    except ET.ParseError:
        return {}
    out: dict[int, str] = {}
    for st in root.findall("./sets/set"):
        if st.get("index") != str(set_index):
            continue
        for btn in st.findall("button"):
            try:
                idx = int(btn.get("index", "0"))
            except ValueError:
                continue
            slots = btn.findall("./slots/slot")
            out[idx] = (" + ".join(_fmt_slot(s) for s in slots)
                        if slots else "割り当てなし")
    return out


def apply_set_bindings(set_index: int, changes: dict[int, str],
                       src: Path, dst: Path) -> None:
    """指定セットだけ割り当てを変更する。"""
    tree = ET.parse(src)
    root = tree.getroot()
    for st in root.findall("./sets/set"):
        if st.get("index") != str(set_index):
            continue
        for idx, label in changes.items():
            btn = None
            for b in st.findall("button"):
                if b.get("index") == str(idx):
                    btn = b
                    break
            if btn is None:
                btn = ET.SubElement(st, "button")
                btn.set("index", str(idx))
            for old in btn.findall("slots"):
                btn.remove(old)
            slots_el = ET.SubElement(btn, "slots")
            for el in _slot_elements(label):
                slots_el.append(el)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="UTF-8", xml_declaration=True)


def get_speeds(set_index: int, profile: Path | None = None) -> tuple[int, int]:
    """(マウス速度, スクロール速度) を返す。"""
    src = profile or paths.source_profile()
    if not src.exists():
        return (0, 0)
    try:
        root = ET.parse(src).getroot()
    except ET.ParseError:
        return (0, 0)
    for st in root.findall("./sets/set"):
        if st.get("index") != str(set_index):
            continue
        m = st.find(".//stick[@index='1']//mousespeedx")
        w = st.find(".//stick[@index='2']//wheelspeedx")
        return (int(m.text) if m is not None and m.text else 0,
                int(w.text) if w is not None and w.text else 0)
    return (0, 0)


def set_speeds_for(set_index: int, mouse: int, wheel: int,
                   src: Path, dst: Path) -> None:
    """セットのマウス速度・スクロール速度を変更する。

    スティックの全方向 (8 方向) に同じ値を書く。一部だけ変えると
    斜め方向だけ速度が違う、といった不自然な挙動になる。
    """
    tree = ET.parse(src)
    root = tree.getroot()
    for st in root.findall("./sets/set"):
        if st.get("index") != str(set_index):
            continue
        for stick in st.findall("stick"):
            is_mouse = stick.get("index") == "1"
            for sb in stick.findall("stickbutton"):
                for tag, val in (("mousespeedx", mouse), ("mousespeedy", mouse),
                                 ("wheelspeedx", wheel), ("wheelspeedy", wheel)):
                    el = sb.find(tag)
                    if el is None:
                        continue
                    if tag.startswith("mouse") and is_mouse:
                        el.text = str(val)
                    elif tag.startswith("wheel") and not is_mouse:
                        el.text = str(val)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tree.write(dst, encoding="UTF-8", xml_declaration=True)
