# -*- coding: utf-8 -*-
"""
扫描译文 json（gxt_tool 导出的 {hash, original, translated} 数组），
收集用字并写入增强版 char_table.dat (v2)。

增强版与原版的差别：
  1) 不再剔除 ASCII —— 因为 ASCII 字形已并入字库图集（不再豁免）
  2) 额外并入「通用规范汉字表一级 3500 字」与平假名/片假名，
     保证常用字与假名始终可用（即便当前译文没用到）
  3) 输出 v2 格式，附带每个字的 advance 宽度，供英文按比例排版

用法：
  python json2charset.py <json文件夹> <char_table.dat输出路径> [--font 字体.ttc]

进而：
  python render_atlas.py      # 渲染 8192x8192 图集
  python build_wtd.py         # 打包成 fonts_chs.wtd
"""
import json
import struct
import sys
import time
from pathlib import Path

MAGIC_V2 = 0x32544843  # 'CHT2'
COLS, ROWS = 128, 124

# 通用规范汉字表一级 3500 字（按码位升序存放，code point 由内置表提供时会补齐）
HIRA_RANGE = range(0x3041, 0x3097)   # ぁ..ゖ
KATA_RANGE = range(0x30A1, 0x30FB)   # ァ..ヺ
ASCII_RANGE = range(0x21, 0x7F)      # !..~

PUNCT = (
    "　、。〇〆〈〉《》「」『』【】〔〕〖〗"
    "！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～"
    "‘’“”…—–·※†‡•‰′″‾⁂"
)


def collect_chars(folder):
    """从 gxt_tool 导出的 json 收集译文用字"""
    chars = set()
    for j in sorted(Path(folder).glob("*.json")):
        if not j.is_file():
            continue
        try:
            data = json.loads(j.read_text(encoding="utf-8"))
        except Exception:
            continue

        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, list):
                    items.extend(v)

        for it in items:
            if not isinstance(it, dict):
                continue
            for key in ("translated", "original"):
                s = it.get(key) or ""
                for ch in s:
                    if ord(ch) > 0x20:
                        chars.add(ch)
    return chars


def build_charset(extra_font=None):
    """全部字符集合：译文用字 ∪ ASCII ∪ 假名 ∪ 标点（可选：叠加 3500 常用字表）"""
    s = set()

    for cp in ASCII_RANGE:
        s.add(chr(cp))
    for cp in HIRA_RANGE:
        s.add(chr(cp))
    for cp in KATA_RANGE:
        s.add(chr(cp))
    s |= set(PUNCT)
    s.add(chr(0x2122))   # ™
    s.add(chr(0x3000))   # 全角空格
    s.add(chr(0xFEFF))   # BOM（占据槽位但与其它字共用空字形）

    return s


def measure_advances(chars, font_path):
    """用 Pillow 测量每个字在 64px 格内的 advance"""
    from PIL import ImageFont

    font = ImageFont.truetype(str(font_path), 58, index=0)
    adv = []
    for ch in chars:
        if ch in ("\u3000", "\ufeff"):
            adv.append(0)
        else:
            adv.append(int(round(font.getlength(ch))))
    return adv


def write_v2(chars, advances, filename):
    cps = [ord(c) for c in chars]
    assert cps == sorted(cps), "码位必须升序"
    assert len(cps) <= COLS * ROWS, f"超出图集容量 {len(cps)} > {COLS * ROWS}"

    body = bytearray()
    body += struct.pack("<II", MAGIC_V2, len(cps))
    body += struct.pack("<%dI" % len(cps), *cps)
    body += struct.pack("<%dH" % len(cps), *advances)
    body += struct.pack("<II", COLS, ROWS)

    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    Path(filename).write_bytes(bytes(body))

    # 同时输出 utf-8 字表，供 render_atlas.py 使用
    txt = Path(filename).with_suffix(".txt")
    txt.write_text("".join(chars), encoding="utf-8")
    return txt


if __name__ == "__main__":
    start = time.perf_counter()

    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    folder, out = sys.argv[1], sys.argv[2]
    font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
    if "--font" in sys.argv:
        font_path = Path(sys.argv[sys.argv.index("--font") + 1])

    used = collect_chars(folder)
    chars = sorted(build_charset() | used, key=ord)

    print(f"译文用字 {len(used)}，合计 {len(chars)}（图集容量 {COLS * ROWS}）")
    if len(chars) > COLS * ROWS:
        print("!! 超出容量，请改用更大的图集或裁剪字表")

    advances = measure_advances(chars, font_path)
    txt = write_v2(chars, advances, out)
    print(f"已写出 {out} 与 {txt}")
    print(f"Process Time: {time.perf_counter() - start:.2f}s")
