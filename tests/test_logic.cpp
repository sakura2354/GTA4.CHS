// 独立单元测试：验证增强版的字符分类与断词逻辑
// 编译：g++ -std=c++20 -O2 -o test_logic test_logic.cpp
#include <cstdint>
#include <cstdio>
#include <vector>
#include <string>

typedef std::uint16_t GTAChar;

// ---------- 从 common.cpp 复刻 ----------
bool IsLatinWordChar(char32_t c) { return c >= 0x20 && c < 0x100; }

bool IsWideChar(char32_t c)
{
    if (c >= 0x2E80) return true;
    switch (c)
    {
    case 0x2014: case 0x2018: case 0x2019: case 0x201C:
    case 0x201D: case 0x2026: case 0x2122:
        return true;
    default: return false;
    }
}

// ---------- 从 font.cpp 复刻 ----------
static const GTAChar kSpecials[] = {
    0x3001, 0x3002, 0x3009, 0x300D, 0xFF09, 0x300F, 0x3011, 0x3015, 0x3017,
    0xFF01, 0xFF0C, 0xFF1A, 0xFF1B, 0xFF1F, 0xFF5E, 0x2026, 0x2014,
    0x201C, 0x201D, 0x2018, 0x2019,
    '.', ',', '!', '?', ':', ';', ')', ']', '}', '-', '%'
};

bool IsSpecialPunctuationMark(GTAChar chr)
{
    for (auto c : kSpecials) if (c == chr) return true;
    return false;
}

void SkipSpecialPunctuationMarks(const GTAChar*& str)
{
    while (IsSpecialPunctuationMark(*str)) ++str;
}

const GTAChar* SkipWord(const GTAChar* str)
{
    if (!str) return str;
    auto begin = str;
    auto current = str;
    while (true)
    {
        GTAChar chr = *current;
        if (chr == ' ' || chr == '~' || chr == 0) break;
        if (!IsLatinWordChar(chr))
        {
            if (current == begin) ++current;
            break;
        }
        else ++current;
    }
    SkipSpecialPunctuationMarks(current);
    return current;
}

// ---------- 测试工具 ----------
static std::u16string U(const char* utf8)
{
    std::u16string out;
    for (size_t i = 0; utf8[i]; )
    {
        unsigned cp;
        unsigned char c = utf8[i];
        if (c < 0x80) { cp = c; i += 1; }
        else if ((c >> 5) == 0x6) { cp = ((c & 0x1F) << 6) | (utf8[i+1] & 0x3F); i += 2; }
        else if ((c >> 4) == 0xE) { cp = ((c & 0x0F) << 12) | ((utf8[i+1] & 0x3F) << 6) | (utf8[i+2] & 0x3F); i += 3; }
        else { cp = ((c & 0x07) << 18) | ((utf8[i+1] & 0x3F) << 12) | ((utf8[i+2] & 0x3F) << 6) | (utf8[i+3] & 0x3F); i += 4; }
        if (cp > 0x10FFFF) cp = 0xFFFD;
        if (cp <= 0xFFFF) out.push_back((char16_t)cp);
        else { cp -= 0x10000; out.push_back((char16_t)(0xD800 + (cp >> 10))); out.push_back((char16_t)(0xDC00 + (cp & 0x3FF))); }
    }
    return out;
}

static int fails = 0;

static std::vector<std::u16string> split_words(const std::u16string& s)
{
    std::vector<std::u16string> out;
    const GTAChar* p = reinterpret_cast<const GTAChar*>(s.c_str());
    const GTAChar* end = p + s.size();
    while (p < end && *p)
    {
        while (p < end && *p == ' ') ++p;
        if (p >= end || !*p) break;
        const GTAChar* start = p;
        p = SkipWord(p);
        if (p <= start) break;
        out.emplace_back(reinterpret_cast<const char16_t*>(start), (size_t)(p - start));
    }
    return out;
}

static void check(const char* name, const char* utf8, size_t expect)
{
    auto text = U(utf8);
    auto words = split_words(text);
    bool ok = words.size() == expect;
    printf("[%s] %-14s words=%zu (expect %zu)\n", ok ? " OK " : "FAIL", name, words.size(), expect);
    if (!ok) ++fails;
    printf("       ");
    for (auto& w : words)
    {
        printf("[");
        for (auto c : w) printf("%s", (char)c < 0x80 ? (const char*)&c : "*");
        printf("]");
    }
    printf("\n");
}

void check_widths()
{
    printf("\n=== 宽度映射 (advance * 0.5) ===\n");
    struct W { char32_t ch; std::uint16_t adv; } ws[] = {
        {U'A', 41}, {U'i', 15}, {U'W', 59}, {U'国', 58}, {U'，', 58}
    };
    for (auto& w : ws)
    {
        bool wide = IsWideChar(w.ch);
        printf("  U+%04X adv=%2u wide=%d -> %s\n", (unsigned)w.ch, w.adv, wide,
               wide ? "固定 32px 格" : "advance*0.5");
    }
}

int main()
{
    printf("=== 字符分类 ===\n");
    struct C { char32_t ch; bool latin; bool wide; const char* note; } cs[] = {
        {U'A', true, false, "ASCII 字母"},
        {U'z', true, false, "ASCII 小写"},
        {U'5', true, false, "数字"},
        {U' ', true, false, "空格"},
        {U'.', true, false, "英文句点"},
        {0x00E9, true, false, "é (Latin-1)"},
        {0x0100, false, false, "Ā (>0xFF 非宽)"},
        {U'国', false, true, "汉字"},
        {U'あ', false, true, "平假名"},
        {U'ア', false, true, "片假名"},
        {0xFF0C, false, true, "全角逗号"},
        {0x3002, false, true, "全角句号"},
        {0x3000, false, true, "全角空格"},
        {0x2014, false, true, "em dash"},
        {0x2122, false, true, "trademark"},
    };
    for (auto& c : cs)
    {
        bool l = IsLatinWordChar(c.ch), w = IsWideChar(c.ch);
        bool ok = (l == c.latin) && (w == c.wide);
        printf("  [%s] U+%04X latin=%d wide=%d  %s\n", ok ? "OK" : "!!", (unsigned)c.ch, l, w, c.note);
        if (!ok) ++fails;
    }

    printf("\n=== 断词 ===\n");
    check("纯英文", "Hello world", 2);
    check("英文标点", "Hello, world!", 2);
    check("英文缩写", "Don't stop", 2);
    check("纯中文", "开车去", 3);
    // 「你好，世界。」-> [你] [好，] [世] [界。]：标点被并入前一个词（行首禁则），共 4 段
    check("中文标点", "你好，世界。", 4);
    check("数字", "100", 1);
    check("英文+数字", "MP5", 1);

    check_widths();

    printf("\n%s (fails=%d)\n", fails == 0 ? "=== 通过 ===" : "=== 失败 ===", fails);
    return fails == 0 ? 0 : 1;
}
