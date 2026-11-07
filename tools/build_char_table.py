# -*- coding: utf-8 -*-
"""
生成增强版 char_table.dat (v2)。

格式（前 8+4N 字节与 v1 前段兼容，便于旧工具读取）：
    uint32  magic   = 0x32544843   ('CHT2')
    uint32  count
    uint32  codepoints[count]    码位升序 = 图集槽位顺序
    uint16  advances[count]      该字在 64px 宽格子内的自然 advance（0..64）
    uint32  cols                 每行字符数（128）
    uint32  rows                 行数（124）

advances 用于「ASCII 移除豁免」后仍保留比例宽度：拉丁字母按自身宽度排版，
CJK 与全角标点固定 32px。
"""

# ---- CI（英文 Windows 控制台为 cp1252）强制 UTF-8 输出，须早于任何 print ----
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


import json
from pathlib import Path
import struct

BASE = Path(__file__).resolve().parent.parent
ASSETS = BASE / "assets"
META = ASSETS / "atlas_ranges.json"
OUT = ASSETS / "char_table.dat"

MAGIC = 0x32544843


def main():
    meta = json.loads(META.read_text(encoding="utf-8"))
    cps = meta["codepoints"]
    adv = meta["advances"]
    cols, rows = meta["cols"], meta["rows"]
    assert len(cps) == len(adv) == meta["count"]

    # 码位必须严格升序，二分查找依赖此性质
    assert all(cps[i] < cps[i + 1] for i in range(len(cps) - 1)), "码位必须严格升序"
    assert len(cps) <= cols * rows

    buf = bytearray()
    buf += struct.pack("<II", MAGIC, len(cps))
    buf += struct.pack("<%dI" % len(cps), *cps)
    buf += struct.pack("<%dH" % len(cps), *adv)
    buf += struct.pack("<II", cols, rows)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(buf)

    print("count=%d  cols=%d rows=%d" % (len(cps), cols, rows))
    print("文件大小 %d bytes" % len(buf))
    print("written", OUT)

    # 抽样核对宽度
    sample = ["A", "i", "W", "国", "，", "　"]
    cmap = dict(zip(cps, adv))
    for ch in sample:
        cp = ord(ch)
        if cp in cmap:
            print("  %r U+%04X advance=%d" % (ch, cp, cmap[cp]))


if __name__ == "__main__":
    main()
