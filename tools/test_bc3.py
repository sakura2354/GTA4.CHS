# -*- coding: utf-8 -*-
"""验证 BC3 编码器：编码 -> 用 Pillow(独立解码器) 回读 -> 比较误差"""

# ---- CI（英文 Windows 控制台为 cp1252）强制 UTF-8 输出，须早于任何 print ----
import sys as _sys
try:
    _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


import numpy as np
from PIL import Image
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from bc3 import compress_atlas, write_dds

rng = np.random.default_rng(1234)

def make_test(h=64, w=64):
    img = np.zeros((h, w, 4), dtype=np.uint8)
    # 画一些字形状的内容：白色预乘
    for y in range(h):
        for x in range(w):
            if (x % 16 in range(3, 12)) and (y % 16 in range(2, 14)):
                v = 255 if ((x + y) % 7 != 0) else 120
                img[y, x] = (v, v, v, v)
    # 加一些半透明抗锯齿
    img[:, :, 3] = np.where(img[:, :, 3] > 0, img[:, :, 3], 0)
    return img

def roundtrip(path, rgba):
    write_dds(path, rgba)
    back = np.array(Image.open(path).convert("RGBA"))
    # 预乘图的 RGB 与 A 应一致；Pillow 返回的是解预乘后的值，故只比较 alpha
    return back

img = make_test()
b = roundtrip("t1.dds", img)
orig_a = img[:, :, 3].astype(np.int32)
back_a = b[:, :, 3].astype(np.int32)
err = np.abs(orig_a - back_a)
print("alpha  max_err=%d  mean_err=%.2f  >8 比例=%.2f%%" % (err.max(), err.mean(), 100.0 * (err > 8).mean()))

# 纯色块
solid = np.full((32, 32, 4), 200, dtype=np.uint8)
b2 = roundtrip("t2.dds", solid)
print("solid alpha back =", b2[0, 0, 3], "expect 200")

# 全透明
trans = np.zeros((32, 32, 4), dtype=np.uint8)
b3 = roundtrip("t3.dds", trans)
print("transparent alpha back =", b3[0, 0, 3], "expect 0")

# 渐变
grad = np.zeros((64, 64, 4), dtype=np.uint8)
for y in range(64):
    v = int(y * 255 / 63)
    grad[y, :, :] = (v, v, v, v)
b4 = roundtrip("t4.dds", grad)
ga = grad[:, :, 3].astype(np.int32)
ba = b4[:, :, 3].astype(np.int32)
e4 = np.abs(ga - ba)
print("gradient alpha max_err=%d mean_err=%.2f" % (e4.max(), e4.mean()))

# 尺寸检查
big = np.zeros((1024, 1024, 4), dtype=np.uint8)
import time
t0 = time.time()
nbytes = write_dds("t5.dds", big)
dt = time.time() - t0
print("1024x1024 -> %d bytes, %.2fs, 推算 8192: %.1fs" % (nbytes, dt, dt * 64))
assert nbytes == 1024 * 1024, "BC3 大小应为 w*h"
print("OK")
