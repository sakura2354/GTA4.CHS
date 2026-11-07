#include "common.h"

// 断词边界判定：0x20..0xFF 是游戏原版字体能处理的拉丁/数字/符号区间。
// 注意：这里只回答「这个字符是否参与英文单词的连续拼接」，不回答「用哪套字形」。
bool IsLatinWordChar(char32_t c)
{
    return c >= 0x20 && c < 0x100;
}

// 全角/CJK：占满一个 32px 宽的格子，且自身可作为独立断词单元。
// 判据用 0x2E80 起点（CJK 部首/假名/注音/汉字/全角形式/兼容汉字），
// 覆盖通用规范汉字表、平假名、片假名、中文标点与全角 ASCII。
bool IsWideChar(char32_t c)
{
    if (c >= 0x2E80)
    {
        return true;
    }

    // 中日韩符号与标点之外的少量常用全角/特殊符号
    switch (c)
    {
    case 0x2014: // —
    case 0x2018: // '
    case 0x2019: // '
    case 0x201C: // "
    case 0x201D: // "
    case 0x2026: // …
    case 0x2122: // ™
        return true;

    default:
        return false;
    }
}

// 保留原义：游戏原版字体的可处理区间。增强版中不再用于选择字形。
bool IsNativeChar(char32_t c)
{
    return c < 0x100;
}

bool IsNormalNativeChar(char32_t c)
{
    return IsNativeChar(c) && (c != 0) && (c != ' ') && (c != '~');
}

void SkipUTF8Signature(std::ifstream& stream)
{
    char bom[3];

    if (stream.get(bom[0]) && stream.get(bom[1]) && stream.get(bom[2]))
    {
        if (bom[0] == '\xEF' && bom[1] == '\xBB' && bom[2] == '\xBF')
        {
            return;
        }
    }

    stream.seekg(0);
}
