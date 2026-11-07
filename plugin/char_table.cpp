#include "char_table.h"

void CCharTable::LoadTable(const std::filesystem::path& filename)
{
    m_Chars.clear();
    m_Advances.clear();
    m_Cols = g_CharsPerLine;
    m_Rows = 62;
    m_IsV2 = false;

    BinaryFile file(filename, "rb");

    if (!file)
    {
        spdlog::error("char_table.dat 打开失败: {}", filename.string());
        return;
    }

    uint32 first = 0;
    file.Read(first);

    if (first == magic_v2)
    {
        uint32 count = 0;
        file.Read(count);

        if (count == 0 || count > 65536)
        {
            spdlog::error("char_table.dat v2 条目数非法: {}", count);
            return;
        }

        m_Chars.resize(count);
        file.ReadArray(m_Chars);
        m_Advances.resize(count);
        file.ReadArray(m_Advances);

        uint32 cols = 0, rows = 0;
        file.Read(cols);
        file.Read(rows);

        if (cols == 0 || rows == 0)
        {
            spdlog::error("char_table.dat v2 图集布局非法: {}x{}", cols, rows);
            return;
        }

        m_Cols = cols;
        m_Rows = rows;
        m_IsV2 = true;

        spdlog::info("char_table.dat v2: {} 字，图集 {}x{}（{}列）", count, cols, rows, cols);
    }
    else
    {
        // v1：首字段即为条目数
        uint32 count = first;

        if (count == 0 || count > 65536)
        {
            spdlog::error("char_table.dat v1 条目数非法: {}", count);
            return;
        }

        m_Chars.resize(count);
        file.ReadArray(m_Chars);

        // v1 无宽度表：全部按 32px 格处理（原版汉化即为该行为）。
        // 注意 v1 与 v2 的 advances 语义不同：v1 里非 0 的 advance 会被
        // GetCharacterSize*Dispatch 当作「有自定义宽度」分支，因此这里给 0，
        // 让 v1 完全走原有的 IsWideChar/原版表逻辑，保持向后兼容。
        m_Advances.assign(count, static_cast<uint16>(0));
        m_Cols = g_CharsPerLine;
        m_Rows = 62;

        spdlog::info("char_table.dat v1: {} 字（4096 图集）", count);
    }
}

std::pair<uint, uint> CCharTable::GetCharPos(GTAChar chr) const
{
    auto char_it = std::ranges::lower_bound(m_Chars, chr);

    if (char_it != m_Chars.end() && *char_it == chr)
    {
        auto diff = char_it - m_Chars.begin();

        return {static_cast<uint>(diff / m_Cols), static_cast<uint>(diff % m_Cols)};
    }
    else
    {
        auto fallback = std::ranges::lower_bound(m_Chars, L'？');

        if (fallback != m_Chars.end() && *fallback == L'？')
        {
            auto diff = fallback - m_Chars.begin();
            return {static_cast<uint>(diff / m_Cols), static_cast<uint>(diff % m_Cols)};
        }

        return {0, 0};
    }
}

uint CCharTable::GetAdvance(GTAChar chr) const
{
    auto char_it = std::ranges::lower_bound(m_Chars, chr);

    if (char_it != m_Chars.end() && *char_it == chr && m_Advances.size() == m_Chars.size())
    {
        return m_Advances[static_cast<std::size_t>(char_it - m_Chars.begin())];
    }

    return 0;
}

bool CCharTable::Contains(GTAChar chr) const
{
    auto char_it = std::ranges::lower_bound(m_Chars, chr);
    return char_it != m_Chars.end() && *char_it == chr;
}
