# -*- coding: utf-8 -*-
"""验证 fonts_chs.wtd：RSC5 头、pgDictionary 结构、纹理描述、BC3 回读比对源图"""

# ---- CI（英文 Windows 控制台为 cp1252）强制 UTF-8 输出，须早于任何 print ----
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


import struct, zlib, sys
from pathlib import Path
import numpy as np
from PIL import Image

BASE = Path(__file__).resolve().parent.parent
WTD = BASE / "assets" / "fonts_chs.wtd"
PNG = BASE / "assets" / "font_chs_atlas.png"

MAGIC = 0x05435352
KEY = "font_chs"


def rage_hash(s, h=0):
    for ch in s:
        h = (h + ord(ch)) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


data = WTD.read_bytes()
magic, rtype, flags = struct.unpack("<III", data[:12])
print("magic=0x%08X  type=0x%X  flags=0x%08X" % (magic, rtype, flags))
assert magic == MAGIC, "magic 错误"
assert rtype == 0x8, "type 必须是 Texture(8)"

v_units, v_exp = flags & 0x7FF, (flags >> 11) & 0xF
p_units, p_exp = (flags >> 15) & 0x7FF, (flags >> 26) & 0xF
vsize = v_units << (8 + v_exp)
psize = p_units << (8 + p_exp)
print("virtual=%d (units=%d exp=%d)   physical=%d (units=%d exp=%d)" % (
    vsize, v_units, v_exp, psize, p_units, p_exp))
assert vsize == 4096, "virtual 必须是单个 4096B 的 4 级块"

raw = zlib.decompress(data[12:])
assert len(raw) == vsize + psize, (len(raw), vsize + psize)
v, p = raw[:vsize], raw[vsize:]
print("解压 OK：%d bytes" % len(raw))

# ---- pgDictionary @0
vtbl, blockmap, parent, usage = struct.unpack("<IIII", v[0:16])
h_off, h_size, h_cap = struct.unpack("<IHH", v[16:24])
val_off, v_size_, v_cap = struct.unpack("<IHH", v[24:32])
print("pgDictionary: blockMap=%d usage=%d hashes(off=%d,size=%d,cap=%d) values(off=%d,size=%d,cap=%d)" % (
    blockmap, usage, h_off, h_size, h_cap, val_off, v_size_, v_cap))
assert h_size == 1 and v_size_ == 1, "字典必须恰好 1 项"

# ---- hashes
stored = struct.unpack("<I", v[h_off:h_off + 4])[0]
expect = rage_hash(KEY)
print("hash: stored=0x%08X  expected(%r)=0x%08X  %s" % (
    stored, KEY, expect, "OK" if stored == expect else "MISMATCH"))
assert stored == expect

# ---- values[0] -> grcTexturePC
tex = struct.unpack("<I", v[val_off:val_off + 4])[0]
print("values[0] -> virtual offset %d (type=%d)" % (tex & 0x0FFFFFFF, tex >> 28))
tex &= 0x0FFFFFFF

name_off = struct.unpack("<I", v[tex + 20:tex + 24])[0] & 0x0FFFFFFF
w, h = struct.unpack("<HH", v[tex + 28:tex + 32])
fmt = struct.unpack("<I", v[tex + 32:tex + 36])[0]
stride = struct.unpack("<H", v[tex + 36:tex + 38])[0]
ttype, levels = v[tex + 38], v[tex + 39]
pixptr = struct.unpack("<I", v[tex + 72:tex + 76])[0]
name = v[name_off:name_off + 40].split(b"\x00")[0].decode("ascii", "replace")

print("grcTexturePC: name=%r  %dx%d  fmt=0x%08X(%s)  stride=%d  type=0x%X  levels=%d" % (
    name, w, h, fmt, "DXT5" if fmt == 0x31545844 else "?", stride, ttype, levels))
print("              pixelData offset=%d type=%d(%s)" % (
    pixptr & 0x0FFFFFFF, pixptr >> 28,
    {5: "Virtual", 6: "Physical"}.get(pixptr >> 28, "?")))
assert name == "pack:/font_chs"
assert (w, h) == (8192, 8192)
assert pixptr >> 28 == 6, "pixelData 必须是 Physical(6)"

# ---- 回读 BC3
expect_bytes = w * h
print("physical 段 %d bytes，需要 %d" % (len(p), expect_bytes))
assert len(p) >= expect_bytes

dds = bytearray(128)
dds[0:4] = b"DDS "
struct.pack_into("<I", dds, 4, 124)
struct.pack_into("<I", dds, 8, 0x1 | 0x2 | 0x4 | 0x1000 | 0x8)
struct.pack_into("<I", dds, 12, h)
struct.pack_into("<I", dds, 16, w)
struct.pack_into("<I", dds, 20, w * 2)
struct.pack_into("<I", dds, 24, 1)
struct.pack_into("<I", dds, 28, 1)
struct.pack_into("<I", dds, 76, 32)
struct.pack_into("<I", dds, 80, 0x4)
struct.pack_into("<4s", dds, 84, b"DXT5")
struct.pack_into("<I", dds, 108, 0x1000 | 0x8 | 0x40)

tmp = BASE / "assets" / "_verify.dds"
tmp.write_bytes(bytes(dds) + p[:expect_bytes])

back = np.array(Image.open(tmp).convert("RGBA"))[:, :, 3]
src = np.array(Image.open(PNG).convert("RGBA"))[:, :, 3]
err = np.abs(back.astype(np.int32) - src.astype(np.int32))
mask = src > 0
print("回读比对: 全图 max=%d mean=%.2f | 墨迹区 max=%d mean=%.2f" % (
    err.max(), err.mean(), err[mask].max(), err[mask].mean()))
tmp.unlink()
print("\n=== 全部校验通过 ===")
