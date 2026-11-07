# -*- coding: utf-8 -*-
"""
构建增强版字表 char_table.dat。

集合 = 通用规范汉字表一级(3500) ∪ 现有三部分译文用字 ∪ 平假名 ∪ 片假名
       ∪ ASCII 可打印 ∪ 中文标点 ∪ 常用符号

图集：8192x8192，128 列 × 124 行 = 15872 格（每格 64x66）。

char_table.dat v2 格式（向后兼容 v1 的 count+codepoints 前段）：
    uint32  magic   = 0x32544843 ('CHT2')
    uint32  count
    uint32  codepoints[count]   (码位升序，即图集槽位顺序)
    uint16  advances[count]     (原版 64 宽格子内的 advance 像素，0..64)
    uint32  cols                (每行字符数)
    uint32  rows                (总行数)
"""
import struct
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
CSV = BASE / "characters.csv"            # 通用规范汉字表 8105 字，前 3500 为一级
USED = BASE / "final_charset.txt"        # 现有全部译文用字（可由 collect_all_chars.py 生成）
TRANSLATIONS = BASE / "translations"     # 译文目录（CI 中由 workflow 检出/下载）
ASSETS = BASE / "assets"
LIST_OUT = ASSETS / "charset.txt"

COLS, ROWS = 128, 124
CAP = COLS * ROWS

# ---------------------------------------------------------------- 字表来源

def level1_3500():
    lines = CSV.read_text(encoding="utf-8-sig").splitlines()
    chars = []
    for line in lines[1:]:           # 跳过表头
        if not line.strip():
            continue
        ch = line.split(",")[0].strip()
        if len(ch) == 1 and 0x4E00 <= ord(ch) <= 0x9FFF:
            chars.append(ch)
        if len(chars) >= 3500:
            break
    assert len(chars) == 3500, len(chars)
    return chars


def used_chars():
    """优先读取预生成的 final_charset.txt；否则直接扫描 translations/ 下的译文"""
    if USED.exists():
        return [c for c in USED.read_text(encoding="utf-8") if ord(c) > 0x20]

    assert TRANSLATIONS.exists(), (
        "缺少译文来源：请先运行 collect_all_chars.py，或把译文放到 %s" % TRANSLATIONS
    )

    import re
    pat = re.compile(r"^(;?)\s*(0[xX][0-9a-fA-F]{8})=(.*)$")
    chars = set()
    for f in TRANSLATIONS.rglob("*.txt"):
        try:
            txt = f.read_text(encoding="utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue
        for line in txt.splitlines():
            m = pat.match(line.strip())
            if not m or m.group(1) == ";":
                continue
            for ch in m.group(3):
                if ord(ch) > 0x20:
                    chars.add(ch)
    assert chars, "译文扫描结果为空，请检查 translations/ 目录"
    return sorted(chars, key=ord)


HIRA = [chr(c) for c in range(0x3041, 0x3097)]          # ぁ..ゖ  86
KATA = [chr(c) for c in range(0x30A1, 0x30FB)]          # ァ..ヺ  90
ASCII_ = [chr(c) for c in range(0x21, 0x7F)]            # !..~    94

PUNCT = list("　、。〇〆〈〉《》「」『』【】〔〕〖〗"
             "！＂＃＄％＆＇（）＊＋，－．／：；＜＝＞？＠［＼］＾＿｀｛｜｝～"
             "‘’“”…—–·※†‡•‰′″‾⁂")

# 供字模渲染时需要单独处理的字符（空格无字形）
EXTRA = [chr(0x3000), chr(0x2122)]

sets = {}
sets["level1_3500"] = set(level1_3500())
sets["used"] = set(used_chars())
sets["hiragana"] = set(HIRA)
sets["katakana"] = set(KATA)
sets["ascii"] = set(ASCII_)
sets["punct"] = set(PUNCT) | set(EXTRA)

final = set()
for s in sets.values():
    final |= s

# 码位升序 = 图集槽位顺序
chars = sorted(final, key=ord)

print("=== 字表构成 ===")
for k, v in sets.items():
    print("  %-16s %5d" % (k, len(v)))
print("  union unique     %5d" % len(chars))
print("  atlas capacity   %5d  (cols=%d rows=%d)" % (CAP, COLS, ROWS))
assert len(chars) <= CAP, "超容量：%d > %d" % (len(chars), CAP)

# 需求核对：现有译文用字必须全部在内
missing = sets["used"] - final
assert not missing, "现译文用字缺失: %s" % "".join(sorted(missing, key=ord))
print("  现译文用字 100%% 覆盖")

LIST_OUT.parent.mkdir(parents=True, exist_ok=True)
LIST_OUT.write_text("".join(chars), encoding="utf-8")
print("written", LIST_OUT)
