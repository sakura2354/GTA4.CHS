#pragma once
#include "../common/stdinc.h"
#include "../common/common.h"

/**
 * 增强版字表（v2）。
 *
 * v1（原版汉化）：文件只有 count + uint32 codepoints，图集 4096x4096、64 列。
 * v2（本增强版）：追加 advances（每字自然宽度）与 cols/rows（图集布局），
 *               支持 8192x8192 图集，并让 ASCII 也能按自身宽度排版。
 *
 * 文件格式见 tools/build_char_table.py。
 */
class CCharTable
{
public:
    static constexpr uint32 magic_v2 = 0x32544843u; // 'CHT2'

    void LoadTable(const std::filesystem::path& filename);

    // 返回 (row, column)；未收录则回退到'？'
    std::pair<uint, uint> GetCharPos(GTAChar chr) const;

    // 字符在 64px 宽格子内的自然 advance；未收录返回 0
    uint GetAdvance(GTAChar chr) const;

    bool Contains(GTAChar chr) const;

    uint GetColumns() const { return m_Cols; }
    uint GetRows() const { return m_Rows; }
    bool IsV2() const { return m_IsV2; }

    const std::vector<char32_t>& GetChars() const { return m_Chars; }

private:
    std::vector<char32_t> m_Chars;   // 码位升序
    std::vector<uint16> m_Advances;  // 与 m_Chars 同序

    uint m_Cols = 64;
    uint m_Rows = 62;
    bool m_IsV2 = false;
};
