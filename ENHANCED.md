# GTA4.CHS 增强版 —— 实现说明

本目录是 [ckeleshi/GTA4.CHS](https://github.com/ckeleshi/GTA4.CHS) 的增强分支，围绕三点改造：

| 目标 | 原版 | 增强版 |
|---|---|---|
| 收字范围 | 仅当前译文用到字（约 3050 个汉字），**无假名** | 通用规范汉字表一级 **3500** ∪ 现有译文用字 ∪ **平假名 86** ∪ **片假名 90** ∪ ASCII ∪ 标点，共 **4245** 字 |
| 图集 | 4096×4096，64×62 = **3968** 格 | 8192×8192，128×124 = **15872** 格 |
| ASCII 字形 | **豁免**：`< 0x100` 直接交回游戏原版字体 | **不豁免**：所有字符统一从字库图集绘制，按 `advance` 保留比例宽度 |

---

## 1. 为什么必须扩到 8192

原版图集格子固定 64×66（`font.cpp` 的 `fSpriteWidth/fSpriteHeight`），容量是硬约束：

```
4096 ÷ 64 = 64 列   4096 ÷ 66 = 62 行   =>  3968 格
```

实测现有三部分译文（GTAIV + TBoGT + TLAD + 网页，共 102,096 条）用字：

- 汉字 **3197**、其他非 ASCII **20**、**假名 0**
- 通用规范汉字表一级 3500 对它只覆盖 **2843 个**，缺 **206** 个（镖/噢/呃/婊/嗯/嗨/屌…），
  这些字若不在字表里，`CCharTable::GetCharPos` 会 fallback 成 `？`，现有译文直接出方块

所以字表必须取并集，而不是替换：

```
3500 ∪ 3197(已完成) ∪ 176 假名 ∪ 94 ASCII ∪ 69 标点  =  4245
```

而 3500+176+94+69 已经 **3798 > 3968 且并集 4245 远超额**，4096 图集放不下，因此图集扩到 8192：

```
8192 ÷ 64 = 128 列   8192 ÷ 66 = 124 行   =>  15872 格
```

> 代价：DXT5 纹理从 16 MB 升到 64 MB 显存。实际只需 34/124 行，压缩后 WTD 仅 3.09 MB。

---

## 2. 关键设计：把「字形来源」和「断词边界」拆开

这是本次改造最容易踩的坑。原版 `IsNativeChar`（`c < 0x100`）**一个判断承担两个职责**：

```cpp
// 原版 font.cpp
bool IsNativeChar(char32_t c) { return c < 0x100; }
```

它同时被用于：

1. **字形来源** —— `PrintCharDispatch` 里 `< 0x100` 就走游戏原版字体
2. **断词边界** —— `SkipWord` / `GetStringWidthRemake` 里非原版字符视为「一个独立词」

如果只是把 `PrintCharDispatch` 的豁免去掉，而 `SkipWord` 仍用同一个函数，后果是：
**中文字符变成「可延续的词」**，整句中文被当成一个超长单词 → 换行错乱、溢出。

反之，若把 `SkipWord` 也改成「所有字符都可延续」，英文单词会在任意字母间被拆行。

因此拆成两个语义独立的函数（`common/common.cpp`）：

```cpp
// 断词边界：拉丁/数字/标点区间，与字形无关
bool IsLatinWordChar(char32_t c) { return c >= 0x20 && c < 0x100; }

// 全角/CJK：占满 32px 格，且每个字符自成断词单元
bool IsWideChar(char32_t c) {
    if (c >= 0x2E80) return true;          // 假名/汉字/全角/兼容汉字
    switch (c) { case 0x2014: case 0x2026: case 0x2122: /* … */ return true; }
    return false;
}
```

`IsNativeChar` 保留（仅作历史语义），但**不再参与任何字形选择**。

---

## 3. 逐处改动

### 3.1 `common/common.h` / `common.cpp`

- 新增 `IsLatinWordChar` / `IsWideChar`，`IsNativeChar` 降级为纯分类函数
- 新增 `g_CharsWidth = 32.0f`（汉字目标宽度常量）

### 3.2 `plugin/char_table.h` / `char_table.cpp`

字表格式升级到 v2（前段兼容 v1）：

```
v2:  magic='CHT2' | count | uint32 codepoints[count] | uint16 advances[count] | cols | rows
v1:  count | uint32 codepoints[count]          （旧资产，仍可加载）
```

- 新增 `GetAdvance()`：返回该字在 64px 格内的自然宽度（ASCII 比例排版靠它）
- 新增 `Contains()` / `GetColumns()` / `GetRows()` / `IsV2()`
- `GetCharPos` 的分列数改为读 `m_Cols`（v1=64，v2=128）

### 3.3 `plugin/font.cpp`

四处 ASCII 豁免全部移除，改为统一的「按字符类别路由宽度、统一走图集绘制」：

| 函数 | 原版行为 | 增强版 |
|---|---|---|
| `GetCharacterSizeNormalDispatch` | `<0x100` 走原版表 | 全角→32px 定宽；拉丁→`advance*0.5`；v1 兜底保留原逻辑 |
| `GetCharacterSizeDrawingDispatch` | 同上 | 同上 |
| `PrintCharDispatch` | `<0x100` 走原版字形 | 仅 token 图标走原版；**其余全部走图集** |
| `PrintCHSChar` | 固定 4096 分母 | 分母由 `cols*64` 动态推算，兼容 4096/8192 |

`SkipWord` / `GetStringWidthRemake` 中的 `!IsNativeChar(chr)` 全部替换为 `!IsLatinWordChar(chr)`：

- 拉丁字符串连续 → 英文单词不会被拆
- 全角/CJK 每字独立 → 中文可正常断行
- 行首禁则标点集补齐了 `（）【】〕〖〗“”‘’—` 与 ASCII 的 `.,!?:;)]}-%`

宽度换算系数：图集格宽 64px，汉字目标 32px，故 `advance * 0.5`。

```
'A' advance=41 -> 20.5px   (汉字 32px 的 0.64 倍)
'i' advance=15 ->  7.5px
'W' advance=59 -> 29.5px
```

### 3.4 `plugin/plugin.cpp`

字表加载后做硬校验：若为空则 `return false`（拒绝启动补丁），并打日志说明，
避免「补丁生效但字表缺失」时满屏 `？`。

---

## 4. 资源生成链

```
译文 json/txt ──collect_all_chars.py──► final_charset.txt
通用规范汉字表(3500) ──build_charset.py─┐
假名/ASCII/标点 ────────────────────────┼─► charset.txt (4245 字，码位升序)
                                        │
字体 (msyh.ttc) ──render_atlas.py──► font_chs_atlas.png (8192²)
                             └─────► atlas_ranges.json (codepoints + advances)
                                        │
                                        ├─► build_char_table.py ─► char_table.dat (v2, 25 KB)
                                        │
                     bc3.py (BC3/DXT5) ─┴─► build_wtd.py ─► fonts_chs.wtd (3.09 MB)
```

### 4.1 执行顺序

```bash
# 0) 依赖：pip install pillow numpy
python tools/collect_all_chars.py      # 统计译文用字 -> final_charset.txt
python tools/build_charset.py          # 生成 charset.txt（需 characters.csv）
python tools/render_atlas.py           # 渲染 8192² 图集 + 宽度表
python tools/build_char_table.py       # 生成 char_table.dat v2
python tools/build_wtd.py              # BC3 压缩 + RSC5 打包 -> fonts_chs.wtd
python tools/verify_wtd.py             # 回读校验容器结构与画质
```

### 4.2 `characters.csv`

来自 [jaywcjlove/table-of-general-standard-chinese-characters](https://github.com/jaywcjlove/table-of-general-standard-chinese-characters)
（通用规范汉字表 8105 字，前 3500 行为一级字表，`build_charset.py` 直接取前 3500）。

---

## 5. WTD 容器格式（手写生成器的要点）

`fonts_chs.wtd` 是 RSC5（`magic=0x05435352`, `type=0x8`）zlib 容器，
解压后 = virtual 段 + physical 段：

```
virtual 4096B（必须报成 1 个 4 级块：units=16, exp=0）
  +0    pgDictionary 32B
  +32   blockMap 528B（全 0，游戏侧重建）
  +560  hashes[1] = HashString("font_chs")
  +576  values[1] -> grcTexturePC
  +592  grcTexturePC 80B
        name = "pack:/font_chs"
        8192×8192, D3DFMT_DXT5, stride=8192, levels=1
        pixelData = pgPtr{offset:0, type:6(Physical)}
physical 64 MB = BC3 像素
```

两个易错点：

1. **`pgPtr` 位域是 `offset:28`（低位）+ `blockType:4`（高位）**，
   所以 physical 指针写作 `6 << 28`，不是 `6`。
   （我第一次写成 `6`，`values[0]` 直接变成 type=0，游戏会读成 virtual 段崩溃）
2. **virtual 段的分页标志**：4096 字节 = 16 个 256B 基础页，
   即 `(flags & 0x7FF) = 16`、`vexp = 0`。写成 `units=1` 只会分配 256 字节。

---

## 6. 验证

```bash
# 字符分类 / 断词逻辑（15 项分类 + 6 项断词，全部通过）
cd tests && g++ -std=c++20 -O2 -o test_logic test_logic.cpp && ./test_logic

# BC3 编码器往返（Pillow 独立解码）
python tools/test_bc3.py

# WTD 容器结构 + 画质回读
python tools/verify_wtd.py
```

实测结果：

- BC3 回读 alpha 误差：全图 `mean=0.47/255`，墨迹区 `max=54`
- 容器解压长度、字典哈希、纹理字段、physical 指针类型全部断言通过

---

## 7. 尚未验证 / 需要真机确认

本环境**没有 GTA4 本体、没有 MSVC 工具链**，以下只能在真机验证：

1. **D3D9 是否支持 8192² 纹理**。D3D9 规范要求 `MaxTextureWidth >= 8192`
   （多数现代显卡支持 8192~16384，老卡可能只有 4096）。若目标机器只支持 4096，
   需回退到「4096 + 裁剪字表」方案（见下）。
2. **实际观感**：ASCII 去掉豁免后由微软雅黑渲染，风格与游戏原版 sans 字体不同；
   英文的视觉宽度靠 `advance` 比例控制，需要在游戏内确认行距/断行。
3. **`GetCharacterSize*` 的 `advance*0.5` 与游戏原版拉丁宽度表的偏差**可能造成
   个别 UI 元素（如菜单项右对齐、滚动字幕）位置微调。

### 若必须留在 4096

把 `build_charset.py` 的集合改为「3500 ∪ 现译文用字」去掉标点与假名（实测 4053，仍超 85），
可行做法是：

- 去掉 ASCII 94 字（反正原版字形本来就够用，只是放弃「统一字形」）
- 或改用半角格（ASCII 用 32×66，汉字 64×66），同尺寸可多放约 30%

---

## 8. 目录说明

```
enhanced/
├── assets/                    生成产物
│   ├── charset.txt            4245 字（码位升序）
│   ├── char_table.dat         v2 字表（含 advance）
│   ├── font_chs_atlas.png     8192² 图集
│   ├── atlas_ranges.json      码位 + 宽度元数据
│   └── fonts_chs.wtd          RSC5 容器（3.09 MB）
├── src/GTA4.CHS/              改造后的插件源码
│   ├── common/                IsLatinWordChar / IsWideChar 拆分
│   ├── plugin/font.cpp        ASCII 豁免移除 + 宽度路由
│   ├── plugin/char_table.*    v1/v2 双格式
│   ├── gxt_tool/json2charset.py  v2 字表生成
│   └── tools/                 资源生成链
└── tests/                     逻辑测试 + 语法检查
```
