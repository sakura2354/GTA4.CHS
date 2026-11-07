# -*- coding: utf-8 -*-
"""
渲染 8192x8192 中文字模图集。

布局与原版一致：每格 64x66，共 128 列 × 124 行。
槽位顺序 = char_table.dat 中码位升序。

字形排布参考原 CWTDGen：字号 -58、粗体、GDI+/D2D 居中绘制。
为保证与原版观感一致，采用「底对齐 + 水平居中」，并将墨迹下沿对齐到格子内基准线。

输出：预乘 alpha 的白色字形 (a,a,a,a)，供 BC3 压缩。
"""
import json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

TEX_W = TEX_H = 8192
CW, CH = 64, 66
COLS, ROWS = TEX_W // CW, TEX_H // CH      # 128, 124
FONT_SIZE = 58
BASE_Y = CH - 5          # 墨迹下沿在格子内的 y（预留下伸部空间，与原 PrintCHSChar 的 y_delta=5 一致）

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CHARSET = ASSETS / "charset.txt"
OUT_PNG = ASSETS / "font_chs_atlas.png"
OUT_META = ASSETS / "atlas_ranges.json"


def render(font, chars):
    """chars -> (TEX_H, TEX_W) uint8 预乘 alpha"""
    img = Image.new("L", (TEX_W, TEX_H), 0)
    draw = ImageDraw.Draw(img)

    for i, ch in enumerate(chars):
        row, col = divmod(i, COLS)
        x0 = col * CW
        y0 = row * CH

        if ch == "\u3000":                    # 全角空格：无字形
            continue
        if ch in ("\n", "\r"):
            continue

        # 用 bbox 做精确居中与基线对齐
        bb = font.getbbox(ch)
        if bb is None:
            continue
        l, t, r, b = bb
        gw = r - l
        gh = b - t

        dx = x0 + (CW - gw) // 2 - l
        dy = y0 + BASE_Y - b

        draw.text((dx, dy), ch, font=font, fill=255)

    return np.array(img, dtype=np.uint8)


def main():
    chars = list(CHARSET.read_text(encoding="utf-8"))
    n = len(chars)
    assert n <= COLS * ROWS, (n, COLS * ROWS)
    print("chars=%d  cols=%d rows=%d  used_rows=%d" % (n, COLS, ROWS, (n + COLS - 1) // COLS))

    font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", FONT_SIZE, index=0)

    # 分条渲染以控制内存：每条 = 若干整行
    band_rows = 8
    alpha = np.zeros((TEX_H, TEX_W), dtype=np.uint8)

    for r0 in range(0, ROWS, band_rows):
        r1 = min(r0 + band_rows, ROWS)
        i0 = r0 * COLS
        i1 = min(r1 * COLS, n)
        if i0 >= n:
            break
        sub = chars[i0:i1]
        band = Image.new("L", (TEX_W, (r1 - r0) * CH), 0)
        d = ImageDraw.Draw(band)
        for j, ch in enumerate(sub):
            rr, cc = divmod(j, COLS)
            x0 = cc * CW
            y0 = rr * CH
            if ch == "\u3000":
                continue
            bb = font.getbbox(ch)
            if bb is None:
                continue
            l, t, r, b = bb
            gw, gh = r - l, b - t
            dx = x0 + (CW - gw) // 2 - l
            dy = y0 + BASE_Y - b
            d.text((dx, dy), ch, font=font, fill=255)
        alpha[r0 * CH:r1 * CH, :] = np.array(band, dtype=np.uint8)
        print("  band rows %d..%d done" % (r0, r1))

    # 预乘 alpha 的白色字形
    rgba = np.empty((TEX_H, TEX_W, 4), dtype=np.uint8)
    rgba[:, :, 0] = alpha
    rgba[:, :, 1] = alpha
    rgba[:, :, 2] = alpha
    rgba[:, :, 3] = alpha

    Image.fromarray(rgba, "RGBA").save(OUT_PNG, optimize=False)
    print("saved", OUT_PNG)

    # 记录每个字符的 advance（相对 64 宽格子），供插件排版用
    advances = []
    for ch in chars:
        if ch == "\u3000":
            advances.append(0)
        else:
            advances.append(int(round(font.getlength(ch))))

    OUT_META.write_text(json.dumps({
        "cols": COLS, "rows": ROWS, "cell_w": CW, "cell_h": CH,
        "tex_w": TEX_W, "tex_h": TEX_H, "font_size": FONT_SIZE, "base_y": BASE_Y,
        "count": n,
        "codepoints": [ord(c) for c in chars],
        "advances": advances,
    }, ensure_ascii=False), encoding="utf-8")
    print("saved", OUT_META)


if __name__ == "__main__":
    main()
