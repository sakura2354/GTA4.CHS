# -*- coding: utf-8 -*-
"""
BC3 (DXT5) 编码器 —— 纯 numpy 向量化实现。

BC3 每 4x4 块 16 字节：8 字节 BC4 alpha + 8 字节 BC1 color。
8192x8192 = 4194304 块 => 64 MB。

BC4 alpha 两种模式（规范 D3D10 BC4_UNORM）：
  8 值模式 (v0 > v1):  pal[0]=v0, pal[1]=v1, pal[i]=((7-i)*v0+(i-1)*v1)/7, i=2..7
  6 值模式 (v0 <= v1): pal[0]=v0, pal[1]=v1, pal[i]=((5-i)*v0+(i-1)*v1)/5, i=2..5,
                        pal[6]=0, pal[7]=255

源图约定：预乘 alpha 的白色字形，RGBA=(a,a,a,a)。
"""

# ---- CI（英文 Windows 控制台为 cp1252）强制 UTF-8 输出，须早于任何 print ----
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


import struct
import numpy as np

DDS_MAGIC = b"DDS "


def _blocks_from_image(rgba):
    """(H,W,4) uint8 -> (nblocks, 16, 4) uint8，块内顺序 row*4+col，块行优先。"""
    h, w, _ = rgba.shape
    assert h % 4 == 0 and w % 4 == 0
    b = rgba.reshape(h // 4, 4, w // 4, 4, 4)
    b = b.transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    return b


def _encode_alpha_blocks(alphas, batch=65536):
    """alphas: (n,16) uint8 -> (n,8) uint8"""
    n = alphas.shape[0]
    out = np.zeros((n, 8), dtype=np.uint8)
    a = alphas.astype(np.float32)

    for s in range(0, n, batch):
        e = min(s + batch, n)
        blk = a[s:e]                                # (m,16)
        amin = blk.min(axis=1)                       # (m,)
        amax = blk.max(axis=1)                       # (m,)

        # --- 8 值模式：(v0=amax, v1=amin)，要求 v0 > v1
        v0 = amax[:, None]
        v1 = amin[:, None]
        i = np.arange(8, dtype=np.float32)[None, :]
        # pal[i] ：i=0 -> v0, i=1 -> v1, i>=2 -> ((7-i)*v0+(i-1)*v1)/7
        w0 = np.where(i == 0, 1.0, np.where(i == 1, 0.0, (7.0 - i) / 7.0))
        w1 = np.where(i == 0, 0.0, np.where(i == 1, 1.0, (i - 1.0) / 7.0))
        pal8 = w0 * v0 + w1 * v1                     # (m,8)

        d8 = np.abs(blk[:, :, None] - pal8[:, None, :])
        i8 = d8.argmin(axis=2).astype(np.uint8)
        e8 = np.take_along_axis(d8, i8[:, :, None].astype(np.intp), axis=2)[:, :, 0].sum(axis=1)

        # --- 6 值模式：(v0=amin, v1=amax)，要求 v0 <= v1
        j = np.arange(8, dtype=np.float32)[None, :]
        w0b = np.where(j == 0, 1.0, np.where(j == 1, 0.0, np.where(j <= 5, (5.0 - j) / 5.0, 0.0)))
        w1b = np.where(j == 0, 0.0, np.where(j == 1, 1.0, np.where(j <= 5, (j - 1.0) / 5.0, 0.0)))
        pal6 = w0b * amin[:, None] + w1b * amax[:, None]
        pal6[:, 6] = 0.0
        pal6[:, 7] = 255.0

        d6 = np.abs(blk[:, :, None] - pal6[:, None, :])
        i6 = d6.argmin(axis=2).astype(np.uint8)
        e6 = np.take_along_axis(d6, i6[:, :, None].astype(np.intp), axis=2)[:, :, 0].sum(axis=1)

        use6 = e6 <= e8
        idx = np.where(use6[:, None], i6, i8)
        endpoint0 = np.where(use6, amin, amax).astype(np.uint8)
        endpoint1 = np.where(use6, amax, amin).astype(np.uint8)

        # 全同块：两模式都退化为常量，索引全 0
        flat = amax == amin
        endpoint0 = np.where(flat, amin, endpoint0).astype(np.uint8)
        endpoint1 = np.where(flat, amin, endpoint1).astype(np.uint8)
        idx = np.where(flat[:, None], np.uint8(0), idx)

        # 打包 idx 为 48 bit（16 x 3 bit，little-endian 位序）
        bits = np.zeros((e - s, 16, 3), dtype=np.uint8)
        for k in range(3):
            bits[:, :, k] = (idx >> k) & 1
        packed = np.packbits(bits.reshape(e - s, 48), axis=1, bitorder="little")

        out[s:e, 0] = endpoint0
        out[s:e, 1] = endpoint1
        out[s:e, 2:] = packed

    return out


def _encode_color_blocks(rgbs, batch=65536):
    """rgbs: (n,16,3) uint8 -> (n,8) uint8"""
    n = rgbs.shape[0]
    out = np.zeros((n, 8), dtype=np.uint8)

    for s in range(0, n, batch):
        e = min(s + batch, n)
        blk = rgbs[s:e].astype(np.int32)             # (m,16,3)
        mn = blk.min(axis=1)                          # (m,3)
        mx = blk.max(axis=1)                          # (m,3)

        def to565(c):
            c = c.astype(np.int32)
            return ((c[:, 0] >> 3) << 11) | ((c[:, 1] >> 2) << 5) | (c[:, 2] >> 3)

        c0 = to565(mn).astype(np.uint16)
        c1 = to565(mx).astype(np.uint16)

        same = (mn == mx).all(axis=1)
        c0s = np.where(same, np.uint16(0), c0)
        c1s = np.where(same, np.uint16(0), c1)
        # 保证 c0 > c1 走 4 色插值模式（BC2/BC3 色块必须 4 色）
        swap = (~same) & (c0s <= c1s)
        c0f = np.where(swap, c1s, c0s)
        c1f = np.where(swap, c0s, c1s)

        def from565(c):
            r = (c >> 11) & 0x1F
            g = (c >> 5) & 0x3F
            b = c & 0x1F
            return np.stack([
                ((r << 3) | (r >> 2)),
                ((g << 2) | (g >> 4)),
                ((b << 3) | (b >> 2)),
            ], axis=1).astype(np.float32)

        p0 = from565(c0f)
        p1 = from565(c1f)
        p2 = (2.0 * p0 + p1) / 3.0
        p3 = (p0 + 2.0 * p1) / 3.0

        pal = np.stack([p0, p1, p2, p3], axis=1)      # (m,4,3)
        d = np.abs(blk[:, :, None, :] - pal[:, None, :, :]).sum(axis=3)
        idx = d.argmin(axis=2).astype(np.uint8)        # (m,16)

        ones = np.ones((e - s,), dtype=np.bool_)
        idx = np.where(same[:, None], np.uint8(0), idx)

        bits = np.zeros((e - s, 16, 2), dtype=np.uint8)
        bits[:, :, 0] = idx & 1
        bits[:, :, 1] = (idx >> 1) & 1
        packed = np.packbits(bits.reshape(e - s, 32), axis=1, bitorder="little")

        out[s:e, 0] = (c0f & 0xFF).astype(np.uint8)
        out[s:e, 1] = ((c0f >> 8) & 0xFF).astype(np.uint8)
        out[s:e, 2] = (c1f & 0xFF).astype(np.uint8)
        out[s:e, 3] = ((c1f >> 8) & 0xFF).astype(np.uint8)
        out[s:e, 4:] = packed

    return out


def compress_atlas(rgba, premultiplied=True):
    """rgba: (H,W,4) uint8 -> BC3 bytes"""
    work = rgba
    if not premultiplied:
        a = rgba[:, :, 3:4].astype(np.float32) / 255.0
        work = np.concatenate([
            (rgba[:, :, :3].astype(np.float32) * a).astype(np.uint8),
            rgba[:, :, 3:4]],
            axis=2)

    blocks = _blocks_from_image(work)                 # (n,16,4)
    alpha = _encode_alpha_blocks(np.ascontiguousarray(blocks[:, :, 3]))
    color = _encode_color_blocks(np.ascontiguousarray(blocks[:, :, :3]))

    merged = np.concatenate([alpha, color], axis=1)   # (n,16)
    return merged.tobytes()


def write_dds(path, rgba):
    h, w, _ = rgba.shape
    data = compress_atlas(rgba, premultiplied=True)

    hdr = bytearray(128)
    hdr[0:4] = DDS_MAGIC
    struct.pack_into("<I", hdr, 4, 124)
    struct.pack_into("<I", hdr, 8, 0x1 | 0x2 | 0x4 | 0x1000 | 0x8)
    struct.pack_into("<I", hdr, 12, h)
    struct.pack_into("<I", hdr, 16, w)
    struct.pack_into("<I", hdr, 20, w * 2)
    struct.pack_into("<I", hdr, 24, 1)
    struct.pack_into("<I", hdr, 28, 1)
    struct.pack_into("<I", hdr, 76, 32)
    struct.pack_into("<I", hdr, 80, 0x4)
    struct.pack_into("<4s", hdr, 84, b"DXT5")
    struct.pack_into("<I", hdr, 108, 0x1000 | 0x8 | 0x40)

    with open(path, "wb") as f:
        f.write(bytes(hdr))
        f.write(data)
    return len(data)
