#include "plugin.h"
#include "font.h"
#include "game.h"
#include "char_table.h"
#include "gta_string.h"
#include "gta_benchmark.h"
#include "gta_font.h"
#include "gta_game.h"
#include "gta_html.h"
#include "gta_menu.h"
#include "gta_phone.h"
#include "gta_save.h"
#include "gta_whm.h"
#include "gta_mail_reply.h"

CPlugin plugin;

void CPlugin::RegisterPatchSteps(batch_matching &batch_matcher)
{
    gta_benchmark::register_patches(batch_matcher);
    gta_font::register_patches(batch_matcher);
    gta_game::register_patches(batch_matcher);
    gta_html::register_patches(batch_matcher);
    gta_mail_reply::register_patches(batch_matcher);
    gta_menu::register_patches(batch_matcher);
    gta_phone::register_patches(batch_matcher);
    gta_save::register_patches(batch_matcher);
    gta_whm::register_patches(batch_matcher);
}

HANDLE CPlugin::GetGameModule() const
{
    return game_module_path.GetModule();
}

HANDLE CPlugin::GetPluginModule() const
{
    return plugin_module_path.GetModule();
}

std::filesystem::path CPlugin::GetGameRoot() const
{
    return game_module_path.GetModuleDir();
}

std::filesystem::path CPlugin::GetPluginAsset(const std::filesystem::path &rest_path) const
{
    return plugin_module_path.GetModuleDir() / "GTA4.CHS" / rest_path;
}

bool CPlugin::Init(HMODULE module)
{
    game_module_path.SetModule(::GetModuleHandleW(nullptr));
    plugin_module_path.SetModule(module);

    batch_matching batch_matcher;

    RegisterPatchSteps(batch_matcher);

    if (batch_matcher.perform_search())
    {
        batch_matcher.write_log("gta4.chs");
    }

    if (!batch_matcher.is_all_succeed())
    {
        return false;
    }

    batch_matcher.run_callbacks();

    // 字表必须在补丁生效后立即加载：字体 Hook 已经生效，
    // 若字表为空，任何一个非 0x20 字符都会落到 fallback，导致满屏'？'。
    char_table.LoadTable(GetPluginAsset("char_table.dat"));

    if (char_table.GetChars().empty())
    {
        spdlog::critical("char_table.dat 未加载，汉化不可用（请确认 GTA4.CHS\\char_table.dat 存在且为增强版）");
        return false;
    }

    spdlog::info("字库就绪：{} 字，图集 {} 列 x {} 行，格式 v{}",
        char_table.GetChars().size(), char_table.GetColumns(), char_table.GetRows(),
        char_table.IsV2() ? 2 : 1);

    whm_table.LoadTable(GetPluginAsset("whm_table.dat"));
    string_table.LoadTable(GetPluginAsset("custom_translations.json"));

    return true;
}
