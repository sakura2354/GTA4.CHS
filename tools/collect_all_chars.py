# -*- coding: utf-8 -*-
"""汇总三部分 GXT 译文 + 网页译文，统计最终用字，并生成增强版字表"""
import re
from pathlib import Path
from collections import Counter

BASE = Path(__file__).resolve().parent.parent
GXT_ROOT = [BASE / "x_GTAIV" / "GTAIV-master" / "text",
            BASE / "x_TBoGT" / "TBoGT-master" / "text",
            BASE / "x_TLAD" / "TLAD-master" / "text"]
HTML_ROOT = BASE / "x_html" / "html-main"

PAT = re.compile(r"^(;?)\s*(0[xX][0-9a-fA-F]{8})=(.*)$")

chars = Counter()
stats = {}


def scan(root, label):
    if not root.exists():
        stats[label] = "MISSING"
        return
    n = 0
    for f in root.rglob("*.txt"):
        try:
            txt = f.read_text(encoding="utf-8-sig", errors="strict")
        except Exception:
            txt = f.read_text(encoding="utf-8", errors="ignore")
        for line in txt.splitlines():
            m = PAT.match(line.strip())
            if not m or m.group(1) == ';':
                continue
            s = m.group(3)
            if not s or not s.strip():
                continue
            n += 1
            for ch in s:
                if ord(ch) > 255:
                    chars[ch] += 1
    stats[label] = n


for r in GXT_ROOT:
    scan(r, r.parent.name)
scan(HTML_ROOT, "html")

L = []
L.append("=== 译文条目数 ===")
for k, v in stats.items():
    L.append("  %-14s %s" % (k, v))
L.append("unique non-ASCII = %d" % len(chars))

cjk = {c for c in chars if 0x4E00 <= ord(c) <= 0x9FFF}
kana = {c for c in chars if 0x3040 <= ord(c) <= 0x30FF}
other = {c for c in chars if not (0x4E00 <= ord(c) <= 0x9FFF or 0x3040 <= ord(c) <= 0x30FF)}
L.append("CJK=%d  kana=%d  other=%d" % (len(cjk), len(kana), len(other)))
L.append("other = " + " ".join("U+%04X(%s)" % (ord(c), c) for c in sorted(other, key=ord)))
L.append("假名出现: " + ("".join(sorted(kana, key=ord)) or "(无)"))

OUT = BASE / "final_charset.txt"
OUT.write_text("".join(sorted(chars, key=ord)), encoding="utf-8")
L.append("written " + str(OUT))

(BASE / "charset_report.txt").write_text("\n".join(L), encoding="utf-8")
print("done")
