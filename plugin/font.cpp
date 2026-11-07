#include "font.h"
#include "gta_string.h"
#include "plugin.h"

static const float fChsWidth = 32.0f;
static const float fChsWidthFix = -1.0f;
static const float fSpriteWidth = 64.0f;
static const float fSpriteHeight = 66.0f;

// 图集分辨率：v2 = 8192（128 列 x 124 行），v1 = 4096（64 列）。
// 运行时从 char_table.dat 的 cols/rows 反推，避免硬编码导致 v1 资产 UV 全错。
static float TextureResolution()
{
    // 每格 64x66；以宽度推算分辨率（cols * 64）
    uint cols = plugin.char_table.GetColumns();
    if (cols == 0)
    {
        return 4096.0f;
    }
    return static_cast<float>(cols) * fSpriteWidth;
}

// 兼容旧命名：只用于需要常数的地方（此处已无）
// static const float fTextureResolution = 8192.0f;

void* CNFont;

void* __fastcall CFont::LoadTextureCB(void* pDictionary, int, uint hash)
{
    auto result = plugin.game.Dictionary_grcTexturePC_GetElementByKey(pDictionary, hash);

    CNFont = plugin.game.Dictionary_grcTexturePC_GetElementByKey(pDictionary,
        plugin.game.Hash_HashStringFromSeediCase("font_chs"));

    return result;
}

const GTAChar* CFont::SkipWord_Prolog(std::uintptr_t address)
{
    auto ptr = reinterpret_cast<const GTAChar*>(address & 0x7FFFFFFF);

    if ((address & 0x80000000) == 0)
    {
        ptr = SkipWord(ptr);
    }

    SkipSpecialPunctuationMarks(ptr);

    return ptr;
}

bool CFont::IsSpecialPunctuationMark(GTAChar chr)
{
#if 0
    return false;
#else
    // 不能出现在行首的标点（行首禁则）。
    // 增强版补齐了括号、破折号、书名号等，避免中文标点悬挂在行首。
    return
        chr == L'、' || chr == L'。' ||
        chr == L'》' ||
        chr == L'」' ||
        chr == L'）' ||
        chr == L'』' ||
        chr == L'】' ||
        chr == L'〕' ||
        chr == L'〗' ||
        chr == L'！' || chr == L'，' ||
        chr == L'：' || chr == L'；' || chr == L'？' || chr == L'～' ||
        chr == L'…' || chr == L'—' ||
        chr == L'“' || chr == L'”' || chr == L'‘' || chr == L'’' ||
        chr == '.' || chr == ',' || chr == '!' || chr == '?' ||
        chr == ':' || chr == ';' || chr == ')' || chr == ']' || chr == '}' ||
        chr == '-' || chr == '%';
#endif
}

void CFont::SkipSpecialPunctuationMarks(const GTAChar*& str)
{
    while (IsSpecialPunctuationMark(*str))
    {
        ++str;
    }
}

void CFont::AddSpecialPunctuationMarksWidth(const GTAChar*& str, float* width)
{
    while (IsSpecialPunctuationMark(*str))
    {
        *width += GetCharacterSizeNormalDispatch(*str - 0x20);
        ++str;
    }
}

const GTAChar* CFont::SkipWord(const GTAChar* str)
{
    if (str == nullptr)
    {
        return str;
    }

    auto begin = str;
    auto current = str;

    while (true)
    {
        GTAChar chr = *current;

        if (chr == ' ' || chr == '~' || chr == 0)
        {
            break;
        }

        // 增强版：断词边界只看字符类别，与字形来源无关。
        // 拉丁/数字字符（0x20..0xFF）连续拼成一个词；
        // 全角/CJK 字符每个自成一词 —— 这样英文单词不会在字母间被拆行，
        // 中文也不会因为没有空格而溢出。
        if (!IsLatinWordChar(chr))
        {
            if (current == begin)
            {
                ++current;
            }

            break;
        }
        else
        {
            ++current;
        }
    }

    SkipSpecialPunctuationMarks(current);

    return current;
}

const GTAChar* CFont::SkipSpaces(const GTAChar* text)
{
    if (text == nullptr)
        return text;

    while (*text == ' ')
    {
        ++text;
    }

    return text;
}

float CFont::GetMaxWordWidth(const GTAChar* text)
{
    if (text == nullptr)
        return 0.0f;

    float max_word_width = 0.0f;

    while (*text != 0)
    {
        float word_width = GetStringWidthRemake(text, false);

        if (word_width > max_word_width)
            max_word_width = word_width;

        text = SkipSpaces(SkipWord(text));
    }

    return max_word_width;
}

float CFont::GetStringWidthRemake(const GTAChar* str, bool get_all)
{
    float current_width = 0.0f, max_width = 0.0f;
    bool had_word = false;
    auto render_index = plugin.game.Font_GetRenderIndex();
    auto& using_details = plugin.game.game_addr.pFont_Details[render_index];

    TokenStruct token_data;
    GTAChar token_string[64];

    if (str == nullptr)
    {
        return 0.0f;
    }

    while (true)
    {
        auto chr = *str;

        if (chr == 0)
        {
            break;
        }
        else if (chr == ' ')
        {
            if (!get_all)
                break;
        }
        else if (!IsLatinWordChar(chr))
        {
            // 全角/CJK 字符：每个自成一词
            // 有可能是英语单词+汉字，要断开
            if (had_word && !get_all)
            {
                break;
            }
        }
        else if (chr == '~')
        {
            // token
            if (had_word && !get_all)
                break;

            // 91BEC3
            token_string[0] = 0;

            int token_type = plugin.game.Font_ParseToken(++str, token_string, &token_data);

            if (token_data.f110 == 0)
            {
                // 91C0B4
                if (token_type < 256 || token_type > 300)
                {
                    // 91C116
                    if (gta_string::gtaWcslen(token_string) > 0)
                    {
                        // 91C122
                        plugin.game.Font_AddTokenStringWidth(token_string, &current_width, render_index);
                        had_word = true;
                    }
                }
                else
                {
                    // 91C0C3
                    current_width +=
                        plugin.game.game_addr.pFont_ButtonWidths[token_type - 255] * using_details.fBlipScaleX;
                    had_word = true;
                }
            }
            else
            {
                // 91BF11
                for (int token_index = 0; token_index < 4; ++token_index)
                {
                    switch (token_data.a110[token_index])
                    {
                    case 1: {
                        // 91BF26
                        current_width += plugin.game.game_addr.pFont_ButtonWidths[token_data.f0[token_index] - 255] *
                            using_details.fBlipScaleX;
                        had_word = true;

                        break;
                    }

                    case 2: {
                        // 91BF53
                        plugin.game.Font_AddTokenStringWidth(token_data.f10[token_index], &current_width, render_index);
                        had_word = true;
                        break;
                    }

                    default: {
                        break;
                    }
                    }
                }
            }

            // 91BF9E
            if (token_type >= 1000)
            {
                // 91BFA6
                current_width += *plugin.game.game_addr.pFont_BlipWidth * using_details.fBlipScaleX;
                had_word = true;
            }

            // 91BFD3
            while (*str != '~')
            {
                // 91BFE0
                if (*str == 'n')
                {
                    max_width = std::max(max_width, current_width);
                    current_width = 0.0f;
                }

                ++str;
            }

            // 91C013
            // 跳过后边的'~'
            ++str;

            AddSpecialPunctuationMarksWidth(str, &current_width);

            // 处理token后立即判断分词，配合ProcessString逻辑
            if (!get_all)
            {
                break;
            }

            continue;
        }

        // 累加字符宽度
        current_width += GetCharacterSizeNormalDispatch(chr - 0x20);
        had_word = true;
        ++str;

        auto old_ptr = str;
        AddSpecialPunctuationMarksWidth(str, &current_width);

        // 解决标英交替时的宽度计算错误
        if (str != old_ptr && !get_all)
        {
            break;
        }

        // 全角/CJK 字符自成断词单元：累加后立即判断一次分词
        if (!IsLatinWordChar(chr) && !get_all)
        {
            break;
        }
    }

    return std::max(current_width, max_width);
}

void CFont::ProcessStringRoutine(float x, float y, const GTAChar* str, void* a4)
{
    plugin.game.Font_ProcessString(x, y, plugin.string_table.GetString(str), a4);
}

/**
 * 全角/CJK 字符的宽度（32px 格）。
 */
float CFont::GetCHSCharacterSizeNormal()
{
    auto render_index = plugin.game.Font_GetRenderIndex();
    auto& using_details = plugin.game.game_addr.pFont_Details[render_index];
    auto& using_font_data = plugin.game.game_addr.pFont_Datas[using_details.nFont];

    float extra_width = using_font_data.fWidthOfSpaceBetweenChars[using_details.nExtraWidthIndex];

    return (((fChsWidth + fChsWidthFix + extra_width) / *plugin.game.game_addr.pFont_ResolutionX +
        using_details.fEdgeSize2) *
        using_details.fScaleX);
}

/**
 * 增强版：按字符自然宽度算宽度（ASCII 不再豁免）。
 * chr 是游戏管线的口径（原码 - 0x20），故这里要 +0x20 还原码位。
 *
 * 宽度来源优先级：
 *   1) 全角/CJK -> 固定 32px 格（与原来的 fChsWidth 体系完全一致，避免汉字变窄）
 *   2) 表意/窄字符 -> char_table.dat v2 的 advance 按比例缩放
 *   3) 兜底 -> 游戏原版字宽表
 */
float CFont::GetCharacterSizeNormalDispatch(GTAChar chr)
{
    auto code = static_cast<char32_t>(chr) + 0x20;

    // 全角/CJK 优先：保持原版 32px 宽度不变
    if (IsWideChar(code))
    {
        return GetCHSCharacterSizeNormal();
    }

    if (plugin.char_table.IsV2())
    {
        auto advance = plugin.char_table.GetAdvance(static_cast<GTAChar>(code));

        if (advance != 0)
        {
            auto render_index = plugin.game.Font_GetRenderIndex();
            auto& using_details = plugin.game.game_addr.pFont_Details[render_index];
            auto& using_font_data = plugin.game.game_addr.pFont_Datas[using_details.nFont];
            float extra_width = using_font_data.fWidthOfSpaceBetweenChars[using_details.nExtraWidthIndex];

            // 图集格子宽 64px，汉字目标宽 32px，故缩放系数 = 32/64 = 0.5
            return (((static_cast<float>(advance) * 0.5f) + fChsWidthFix + extra_width) /
                *plugin.game.game_addr.pFont_ResolutionX + using_details.fEdgeSize2) *
                using_details.fScaleX;
        }
    }

    // v1 资产没有宽度表：保留原版汉化的「非 ASCII 一律走中文定宽」行为
    if (!plugin.char_table.IsV2() && !IsLatinWordChar(code))
    {
        return GetCHSCharacterSizeNormal();
    }

    return plugin.game.Font_GetCharacterSizeNormal(chr);
}

/**
 * 全角/CJK 字符的绘制宽度。
 */
float CFont::GetCHSCharacterSizeDrawing(bool use_extra_width)
{
    float extra_width = 0.0f;

    auto render_state = plugin.game.game_addr.pFont_RenderState;
    auto& using_font_data = plugin.game.game_addr.pFont_Datas[render_state->nFont];

    if (use_extra_width)
    {
        extra_width = using_font_data.fWidthOfSpaceBetweenChars[render_state->nExtraWidthIndex];
    }

    return ((fChsWidth + fChsWidthFix + extra_width) / *plugin.game.game_addr.pFont_ResolutionX +
        render_state->fEdgeSize) *
        render_state->fScaleX;
}

float CFont::GetCharacterSizeDrawingDispatch(GTAChar chr, bool use_extra_width)
{
    auto code = static_cast<char32_t>(chr) + 0x20;

    // 全角/CJK 优先：保持原版 32px 宽度不变
    if (IsWideChar(code))
    {
        return GetCHSCharacterSizeDrawing(use_extra_width);
    }

    if (plugin.char_table.IsV2())
    {
        auto advance = plugin.char_table.GetAdvance(static_cast<GTAChar>(code));

        if (advance != 0)
        {
            auto render_state = plugin.game.game_addr.pFont_RenderState;
            auto& using_font_data = plugin.game.game_addr.pFont_Datas[render_state->nFont];
            float extra_width = 0.0f;

            if (use_extra_width)
            {
                extra_width = using_font_data.fWidthOfSpaceBetweenChars[render_state->nExtraWidthIndex];
            }

            return (((static_cast<float>(advance) * 0.5f) + fChsWidthFix + extra_width) /
                *plugin.game.game_addr.pFont_ResolutionX + render_state->fEdgeSize) *
                render_state->fScaleX;
        }
    }

    // v1 资产没有宽度表：保留原版汉化的「非 ASCII 一律走中文定宽」行为
    if (!plugin.char_table.IsV2() && !IsLatinWordChar(code))
    {
        return GetCHSCharacterSizeDrawing(use_extra_width);
    }

    return plugin.game.Font_GetCharacterSizeDrawing(chr, use_extra_width);
}

/**
 * 从字库图集绘制一个字符。
 *
 * 增强版要点：
 *   - figure 尺寸由 char_table.dat 的 cols/rows 决定（v2 = 128x124 @8192）
 *   - ASCII 也走这里，但屏幕矩形按其自然宽度收窄，保持英文排版比例
 */
void CFont::PrintCHSChar(float x, float y, GTAChar chr)
{
    auto [row, column] = plugin.char_table.GetCharPos(chr);
    auto render_state = plugin.game.game_addr.pFont_RenderState;

    // 原版游戏实际截取的图块在 64*80 格子中的坐标是
    //  x 0.0
    //  y 4.4
    //  w 64.0
    //  h 78.4912

    // 通过尝试得出的 relative_char_rect 在 64*78.4912 矩形中的偏移
    float x_delta = 0.0f;
    float y_delta = 5.0f;

    // 先计算字符图片在 64*78.4912 矩形内的位置
    CRect relative_char_rect;
    relative_char_rect.bottom_left.x = x_delta;
    relative_char_rect.top_right.x = relative_char_rect.bottom_left.x + fSpriteWidth;
    relative_char_rect.top_right.y = y_delta;
    relative_char_rect.bottom_left.y = relative_char_rect.top_right.y + fSpriteHeight;

    // 截取纹理的位置（分母按实际图集分辨率算，兼容 v1=4096 / v2=8192）
    float resolution = TextureResolution();
    CRect texture_rect;
    texture_rect.bottom_left.x = static_cast<float>(column) * fSpriteWidth / resolution;
    texture_rect.bottom_left.y = static_cast<float>(row + 1) * fSpriteHeight / resolution;
    texture_rect.top_right.x = static_cast<float>(column + 1) * fSpriteWidth / resolution;
    texture_rect.top_right.y = static_cast<float>(row) * fSpriteHeight / resolution;

    float old_screen_character_width =
        (fChsWidth / *plugin.game.game_addr.pFont_ResolutionX + render_state->fEdgeSize) * render_state->fScaleX;

    float old_screen_character_height = render_state->fScaleY * 0.06558f;

    // 64*78.4912 图块在屏幕上的位置
    CRect old_screen_rect;
    old_screen_rect.bottom_left.x = x;
    old_screen_rect.bottom_left.y = y + old_screen_character_height;
    old_screen_rect.top_right.x = x + old_screen_character_width;
    old_screen_rect.top_right.y = y;

    // ---- 增强版：按字符自然宽度收窄屏幕矩形（仅横向）
    // 全角/CJK 字符铺满 64px 格投影（保持原版观感）；
    // 拉丁字母按 advance/64 收窄，得到接近原版的英文节奏。
    if (!IsWideChar(chr))
    {
        auto advance = plugin.char_table.GetAdvance(chr);
        if (advance != 0 && advance < static_cast<uint>(fSpriteWidth))
        {
            float ratio = static_cast<float>(advance) / fSpriteWidth;
            old_screen_rect.top_right.x = x + old_screen_character_width * ratio;
        }
    }

    auto flt_proj = [](float old_lb, float old_ub, float old_val, float new_lb, float new_ub) {
        auto old_range = old_ub - old_lb;
        auto old_diff = old_val - old_lb;
        auto new_range = new_ub - new_lb;

        return old_diff / old_range * new_range + new_lb;
        };

    // 将 virtual_char_rect 投影到 old_screen_rect 中，得到 real_screen_rect
    CRect real_screen_rect;

    // 计算 y 的第二个参数越小，字的 y 长度越大
    real_screen_rect.top_right.x = flt_proj(0.0f, 64.0f, relative_char_rect.top_right.x, old_screen_rect.bottom_left.x,
        old_screen_rect.top_right.x);

    real_screen_rect.top_right.y = flt_proj(0.0f, 74.4912f, relative_char_rect.top_right.y, old_screen_rect.top_right.y,
        old_screen_rect.bottom_left.y);

    real_screen_rect.bottom_left.x = flt_proj(0.0f, 64.0f, relative_char_rect.bottom_left.x,
        old_screen_rect.bottom_left.x, old_screen_rect.top_right.x);

    real_screen_rect.bottom_left.y = flt_proj(0.0f, 74.4912f, relative_char_rect.bottom_left.y,
        old_screen_rect.top_right.y, old_screen_rect.bottom_left.y);

    switch (render_state->nFont)
    {
    case 0:
    case 1:
    case 3: {
        plugin.game.Graphics_SetRenderState(CNFont);
        break;
    }

    default:
        break;
    }

    plugin.game.Font_Render2DPrimitive(&real_screen_rect, &texture_rect, render_state->field_18, false);
}

/**
 * 增强版：彻底移除 ASCII 字形豁免。
 *
 * 原版逻辑：
 *     if (TokenType != 0 || IsNativeChar(chr + 0x20))  -> 交回游戏原版字体
 * 增强版：除 token 图标（由游戏自绘，不能走字形图集）外，所有字符统一从字库图集绘制。
 */
void CFont::PrintCharDispatch(float x, float y, GTAChar chr, bool buffered)
{
    if (plugin.game.game_addr.pFont_RenderState->TokenType != 0)
    {
        // token 内部（按键图标等）由游戏原版流程绘制
        plugin.game.Font_PrintChar(x, y, chr, buffered);
        return;
    }

    if ((chr + 0x20) == 0x3000)
    {
        // 全角空格：无字形，直接跳过
        return;
    }

    if (y < -0.06558f || y > 1.0f)
    {
        return;
    }

    if (-(GetCHSCharacterSizeDrawing(true) / plugin.game.game_addr.pFont_RenderState->fScaleX) > x || x > 1.0f)
    {
        return;
    }

    PrintCHSChar(x, y, chr + 0x20);
}
