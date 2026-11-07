#pragma once
#include "stdinc.h"

// 图集每行字符数（v1 = 64，v2 = 128；实际值由 char_table.dat 提供）
static constexpr uint g_CharsPerLine = 64;

// 汉字/全角字符在 64px 宽格子内的目标宽度
static constexpr float g_CharsWidth = 32.0f;

typedef std::uint16_t GTAChar;

struct CVector2D
{
    float x;
    float y;
};

struct CRect
{
    CVector2D bottom_left;
    CVector2D top_right;
};

struct WhmTextData
{
    std::size_t hash;
    std::uintptr_t offset;
};
VALIDATE_SIZE(WhmTextData, 8);

// ---------------------------------------------------------------------------
// 字符分类
//
// 【重要】原版汉化用 IsNativeChar 一个判断同时承担了两个职责：
//     (a) 字形来源：< 0x100 走游戏原版字体，>= 0x100 走中文字库
//     (b) 断词边界：非原版字符视为「一个独立词」，供 CFont::SkipWord 断行
// 增强版移除 (a)（所有字符统一走字库图集），但必须保留 (b)，
// 否则英文单词会在任意字母处被拆行。故此处拆成两个独立函数。
// ---------------------------------------------------------------------------

// (b) 断词边界：原版能自然处理的拉丁/数字/标点区间（0x20..0xFF）。
// 仅用于判断「一个词延续到哪里」，与字形来源无关。
bool IsLatinWordChar(char32_t c);

// 全角/CJK 字符：字形占满 32px，且每个字符都是独立断词单元
bool IsWideChar(char32_t c);

// 原版字符集判定，保留以兼容旧调用；增强版中它不再决定字形来源
bool IsNativeChar(char32_t c);
bool IsNormalNativeChar(char32_t c);

//读取流时跳过UTF8签名
void SkipUTF8Signature(std::ifstream& stream);
