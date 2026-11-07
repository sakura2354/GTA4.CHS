# -*- coding: utf-8 -*-
"""
生成 fonts_chs.wtd —— RSC5 容器，内含 pgDictionary<grcTexturePC>，键为 "font_chs"。

严格复刻 CWTDGen/RageUtil.hpp 的块布局与序列化顺序：

  virtual 段（4096 字节分页，单块）：
    +0    pgDictionary  32B  (vtable4, blockMap4, parent4, usageCount4,
                              hashes{ptr4,size2,cap2}, values{ptr4,size2,cap2})
    随后由 BlockList 按「除第 0 块外按 size 降序」排布：
      blockMap 528B、hashes 4B*n、values 4B*n、grcTexturePC 80B、name 字符串
  physical 段：
    BC3 像素数据

RSC5 flags（GetVirtualSize/GetPhysicalSize 的逆）：
    size = ((flags & 0x7FF)        ) << (((flags >> 11) & 0xF) + 8)   # virtual
    size = ((flags >> 15) & 0x7FF) << (((flags >> 26) & 0xF) + 8)   # physical
  其中 block4Count 权重为 16 个基础页，故 4096 = 16 个 256B 页 -> (flags&0x7FF)=16, vexp=0
"""
import struct, zlib, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ASSETS = BASE / "assets"
ATLAS_PNG = ASSETS / "font_chs_atlas.png"
OUT_WTD = ASSETS / "fonts_chs.wtd"

TEX_W = 8192
TEX_H = 8192
TEX_NAME = "pack:/font_chs"
TEX_KEY = "font_chs"

RAGE_MAGIC = 0x05435352
TYPE_TEXTURE = 0x8
VIRTUAL_ALLOC = 4096            # 单个 4 级块


def rage_hash(s, h=0):
    """RageUtil::HashString（注意原版初值为 0，不是 FNV）"""
    for ch in s:
        h = (h + ord(ch)) & 0xFFFFFFFF
        h = (h + (h << 10)) & 0xFFFFFFFF
        h ^= h >> 6
    h = (h + (h << 3)) & 0xFFFFFFFF
    h ^= h >> 11
    h = (h + (h << 15)) & 0xFFFFFFFF
    return h


def roundup(n, a):
    return (n + a - 1) & ~(a - 1)


class VirtualAlloc:
    """按 16 字节对齐分配 virtual 偏移"""

    def __init__(self):
        self.cursor = 0

    def alloc(self, size):
        off = roundup(self.cursor, 16)
        self.cursor = off + roundup(size, 16)
        return off


def block_flags(size_bytes):
    """把字节数拆成 (count_units, size_exp)，满足 units * 2^(8+exp) >= size。
    注意 units 是「基础页」计数；物理段的 count 字段放在 bit15，权重 1。"""
    for exp in range(16):
        unit = 1 << (8 + exp)
        units = (size_bytes + unit - 1) // unit
        if units <= 0x7FF:
            return units, exp
    raise RuntimeError("size too big: %d" % size_bytes)


def build_blank_texture(key, w, h, levels=1):
    """构造一个不含像素的逻辑纹理描述（仅用于占位/校验）"""
    raise NotImplementedError


def main():
    sys.path.insert(0, str(BASE / "tools"))
    from bc3 import compress_atlas
    from PIL import Image
    import numpy as np

    print("[1/3] 读取图集 -> BC3")
    img = Image.open(ATLAS_PNG).convert("RGBA")
    rgba = np.array(img, dtype=np.uint8)
    assert rgba.shape[:2] == (TEX_H, TEX_W), rgba.shape
    bcn = compress_atlas(rgba, premultiplied=True)
    print("      BC3 %d bytes (%.1f MB)" % (len(bcn), len(bcn) / 1048576))

    print("[2/3] 布局 virtual 段")
    va = VirtualAlloc()
    # --- pgDictionary 32B
    DICT_OFF = va.alloc(32)
    BLOCKMAP_OFF = va.alloc(528)
    HASHES_OFF = va.alloc(4)          # 1 个 uint32
    VALUES_OFF = va.alloc(4)          # 1 个 pgPtr (uint32)
    TEX_OFF = va.alloc(80)            # grcTexturePC
    NAME_OFF = va.alloc(len(TEX_NAME) + 1)

    # 追加字符串块（与 grcTexture::DumpToMemory 一致，按 strlen+1）
    name_bytes = TEX_NAME.encode("ascii") + b"\x00"

    virtual_size = va.cursor
    print("      virtual cursor = %d (<= %d)" % (virtual_size, VIRTUAL_ALLOC))
    assert virtual_size <= VIRTUAL_ALLOC

    # --- flags
    v_units, v_exp = block_flags(VIRTUAL_ALLOC)
    p_units, p_exp = block_flags(len(bcn))
    flags = (v_units & 0x7FF) | ((v_exp & 0xF) << 11) | ((p_units & 0x7FF) << 15) | ((p_exp & 0xF) << 26)
    v_bytes = (flags & 0x7FF) << (((flags >> 11) & 0xF) + 8)
    p_bytes = ((flags >> 15) & 0x7FF) << (((flags >> 26) & 0xF) + 8)
    print("      flags=0x%08X  virtual=%d physical=%d" % (flags, v_bytes, p_bytes))
    assert v_bytes >= virtual_size, (v_bytes, virtual_size)
    assert p_bytes >= len(bcn)

    print("[3/3] 序列化")
    v = bytearray(v_bytes)
    p = bytearray(p_bytes)
    p[0:len(bcn)] = bcn

    # pgDictionary
    struct.pack_into("<I", v, DICT_OFF + 0, 0)                  # vtable
    struct.pack_into("<I", v, DICT_OFF + 4, BLOCKMAP_OFF)       # blockMap (virtual ptr, type=5 高4位)
    struct.pack_into("<I", v, DICT_OFF + 8, 0)                  # parent
    struct.pack_into("<I", v, DICT_OFF + 12, 0)                 # usageCount
    struct.pack_into("<I", v, DICT_OFF + 16, HASHES_OFF)        # hashes.data
    struct.pack_into("<H", v, DICT_OFF + 20, 1)                 # hashes.size
    struct.pack_into("<H", v, DICT_OFF + 22, 1)                 # hashes.capacity
    struct.pack_into("<I", v, DICT_OFF + 24, VALUES_OFF)        # values.data
    struct.pack_into("<H", v, DICT_OFF + 28, 1)                 # values.size
    struct.pack_into("<H", v, DICT_OFF + 30, 1)                 # values.capacity

    # blockMap：保持全 0（原版 RSC 的 blockMap 由游戏重建；CWTDGen 亦未改写其内容）
    # hashes / values
    struct.pack_into("<I", v, HASHES_OFF, rage_hash(TEX_KEY))
    struct.pack_into("<I", v, VALUES_OFF, TEX_OFF)              # virtual ptr

    # grcTexturePC
    struct.pack_into("<I", v, TEX_OFF + 0, 0)                   # vtable
    struct.pack_into("<I", v, TEX_OFF + 4, 0)                   # blockMap
    v[TEX_OFF + 8] = 0                                          # objectType
    v[TEX_OFF + 9] = 0                                          # depth
    struct.pack_into("<H", v, TEX_OFF + 10, 1)                  # usageCount
    struct.pack_into("<I", v, TEX_OFF + 12, 0)                  # pad
    struct.pack_into("<I", v, TEX_OFF + 16, 0)                  # pad2
    struct.pack_into("<I", v, TEX_OFF + 20, NAME_OFF)           # name ptr
    struct.pack_into("<I", v, TEX_OFF + 24, 0)                  # nativeHandle
    struct.pack_into("<H", v, TEX_OFF + 28, TEX_W)              # width
    struct.pack_into("<H", v, TEX_OFF + 30, TEX_H)              # height
    struct.pack_into("<I", v, TEX_OFF + 32, 0x31545844)         # D3DFMT_DXT5
    struct.pack_into("<H", v, TEX_OFF + 36, TEX_W)              # stride
    v[TEX_OFF + 38] = 0x80                                      # textureType
    v[TEX_OFF + 39] = 1                                         # levels
    for i in range(3):
        struct.pack_into("<f", v, TEX_OFF + 40 + i * 4, 1.0)    # unk28
        struct.pack_into("<f", v, TEX_OFF + 52 + i * 4, 0.0)    # unk34
    struct.pack_into("<I", v, TEX_OFF + 64, 0)                  # next
    struct.pack_into("<I", v, TEX_OFF + 68, 0)                  # prev
    # pixelData：offset:28 低位 + blockType:4 高位，Physical(6)
    struct.pack_into("<I", v, TEX_OFF + 72, (6 << 28) | 0)
    v[TEX_OFF + 76:TEX_OFF + 80] = b"\x00" * 4                  # pad

    v[NAME_OFF:NAME_OFF + len(name_bytes)] = name_bytes

    raw = bytes(v) + bytes(p)
    payload = zlib.compress(raw, 9)

    OUT_WTD.parent.mkdir(parents=True, exist_ok=True)
    OUT_WTD.write_bytes(struct.pack("<III", RAGE_MAGIC, TYPE_TEXTURE, flags) + payload)
    print("写出 %s  压缩后 %.2f MB" % (OUT_WTD, len(payload) / 1048576))


if __name__ == "__main__":
    main()
