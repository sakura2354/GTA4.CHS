# GTA4.CHS 汉化补丁 · 增强版

适用于 GTA4 三合一版本（1.2.0.43 及以上）的汉化程序，基于
[ckeleshi/GTA4.CHS](https://github.com/ckeleshi/GTA4.CHS) 增强。

原汉化项目：[b9348.pages.dev](https://b9348.pages.dev/)

---

## 本增强版做了什么

| 项目 | 原版 | 增强版 |
|---|---|---|
| 收字 | 仅译文实际用字（约 3050 汉字），**无假名** | 通用规范汉字表一级 **3500** ∪ 现有译文用字 ∪ **平假名 86** ∪ **片假名 90** ∪ ASCII ∪ 标点 = **4245 字** |
| 图集 | 4096×4096（64×62 = 3968 格） | **8192×8192**（128×124 = 15872 格） |
| ASCII 字形 | **豁免**（`<0x100` 交回游戏原版字体） | **不豁免**，所有字符统一走字库图集 |
| 英文宽度 | 沿用游戏原版字宽表 | 图集内按 `advance` 保留比例宽度 |

设计动机与容量核算见 [ENHANCED.md](ENHANCED.md)。

---

## 安装

把 `plugins\GTA4.CHS\` 目录放到游戏根目录，需包含：

```
GTA4.CHS.asi        插件本体（CI 构建产物）
char_table.dat      字表 v2（4245 字 + 宽度）
fonts_chs.wtd       8192² 字体图集（DXT5）
custom_translations.json   （可选，第三方 mod 文本覆盖）
```

`GTA4.CHS.asi` 需要 ASI Loader（如 `dinput8.dll`）加载。

> ⚠️ 图集为 8192×8192。D3D9 规范要求 `MaxTextureWidth ≥ 8192`，绝大多数现代显卡满足；
> 若目标机器只支持 4096，请参见 ENHANCED.md 第 7 节的回退方案。

---

## 从源码构建

### 依赖

- Visual Studio 2022（含 C++ x86 工具链）
- CMake 3.28+
- [vcpkg](https://github.com/microsoft/vcpkg)（清单模式，见 `vcpkg.json`）
- [VC-LTL5](https://github.com/Chuyu-Team/VC-LTL5)（缩小 CRT 体积，可省）
- Python 3.12 + `pillow` / `numpy`（仅生成字体资源时需要）

### 本地构建

```powershell
# 1) 字体资源（仓库根目录执行）
python tools/build_charset.py       # 生成 4245 字表 -> assets/charset.txt
python tools/render_atlas.py        # 渲染 8192² 图集 + 宽度表
python tools/build_char_table.py    # -> assets/char_table.dat (v2)
python tools/build_wtd.py           # BC3 压缩 + RSC5 打包 -> assets/fonts_chs.wtd
python tools/verify_wtd.py          # 校验容器结构

# 2) 编译插件（x86！GTA4 是 32 位进程）
cmake -S . -B build -G "Ninja Multi-Config" ^
  -DCMAKE_TOOLCHAIN_FILE=$env:VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake ^
  -DVCPKG_TARGET_TRIPLET=x86-windows-static
cmake --build build --config Release
```

> `characters.csv`（通用规范汉字表 8105 字，前 3500 行为一级）已随仓库附带。
> `final_charset.txt`（现有译文用字）亦可由 `tools/collect_all_chars.py` 从译文目录重新生成。

### CI

`.github/workflows/build.yml` 分两个 job：

1. **assets** —— 在 Windows runner 上生成 `char_table.dat` 与 `fonts_chs.wtd`，并跑容器校验
2. **build** —— 下载 VC-LTL5、vcpkg 清单安装依赖、用 `vcvars32` 环境编译 x86 插件，
   校验产物 `machine == 0x014C`（确认是 32 位 PE），产出可直接用的 `release/plugins/GTA4.CHS/`

触发方式：push 到 `master` / `eflc112`、PR、或手动 `workflow_dispatch`。

---

## 依赖库

- [VC-LTL5](https://github.com/Chuyu-Team/VC-LTL5)
- [Vcpkg](https://github.com/microsoft/vcpkg)
- [zlib](https://github.com/madler/zlib)
- [utfcpp](https://github.com/nemtrif/utfcpp)
- [fmt](https://github.com/fmtlib/fmt)
- [nlohmann-json](https://github.com/nlohmann/json)
- [spdlog](https://github.com/gabime/spdlog)

---

## 致谢

原程序作者 **Clans (ckeleshi)**，以及无名汉化组与 GTA4 完整版汉化组全体成员。
本增强版仅修改字库容量、收字范围与 ASCII 字形策略，未改动文本内容。
