# -*- coding: utf-8 -*-
"""终验：确认假名/ASCII/3500常用字真的在图集与字表中，且槽位可正确索引"""

# ---- CI（英文 Windows 控制台为 cp1252）强制 UTF-8 输出，须早于任何 print ----
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


import json, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
ASSETS = BASE / "assets"

COLS, ROWS = 128, 124
CW, CH = 64, 66

# ---- 读 char_table.dat v2
data = (ASSETS / "char_table.dat").read_bytes()
magic, count = struct.unpack("<II", data[:8])
assert magic == 0x32544843, magic
off = 8
cps = list(struct.unpack("<%dI" % count, data[off:off + 4 * count]))
off += 4 * count
adv = list(struct.unpack("<%dH" % count, data[off:off + 2 * count]))
off += 2 * count
cols, rows = struct.unpack("<II", data[off:off + 8])

print("char_table.dat v2: count=%d cols=%d rows=%d" % (count, cols, rows))
cmap = dict(zip(cps, range(count)))

# ---- 关键字符是否在表内
hira = [chr(c) for c in range(0x3041, 0x3097)]
kata = [chr(c) for c in range(0x30A1, 0x30FB)]
ascii_ = [chr(c) for c in range(0x21, 0x7F)]

def present(chars):
    return sum(1 for c in chars if ord(c) in cmap)

print("平假名 %d/%d" % (present(hira), len(hira)))
print("片假名 %d/%d" % (present(kata), len(kata)))
print("ASCII  %d/%d" % (present(ascii_), len(ascii_)))

# ---- 图集槽位抽查：确认这些字在图集对应格里确实有墨迹
atlas = np.array(Image.open(ASSETS / "font_chs_atlas.png").convert("RGBA"))[:, :, 3]

def cell_ink(ch):
    idx = cmap.get(ord(ch))
    if idx is None:
        return None, 0
    r, c = divmod(idx, COLS)
    block = atlas[r * CH:(r + 1) * CH, c * CW:(c + 1) * CW]
    return idx, int((block > 0).sum())

print("\n槽位抽查（索引, 墨迹像素数）:")
for ch in ["あ", "ア", "国", "A", "i", "W", "，", "。"]:
    idx, ink = cell_ink(ch)
    ok = "OK" if ink > 0 else "!! 空"
    print("  %-2s U+%04X idx=%-5s ink=%-5d [%s]" % (ch, ord(ch), idx, ink, ok))

# ---- 假名整段墨迹检查
empty_kana = [c for c in hira + kata if cell_ink(c)[1] == 0]
print("\n无墨迹的假名: %d 个" % len(empty_kana),
      ("".join(empty_kana) if empty_kana else "(无，全部有字形)"))

# ---- 空字形应只有空格类
empties = []
for i, cp in enumerate(cps):
    r, c = divmod(i, COLS)
    if (atlas[r * CH:(r + 1) * CH, c * CW:(c + 1) * CW] > 0).sum() == 0:
        empties.append(cp)
print("全表空字形字符 (%d):" % len(empties),
      " ".join("U+%04X" % e for e in empties[:20]))
