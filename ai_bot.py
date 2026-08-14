# -*- coding: utf-8 -*-
"""GGMW9 bot entrypoint.

Feature code lives in ordered extensions under ``cogs/``.  The shared runtime keeps
the exact global state and execution order of the former monolithic file.
"""

import traceback

from cogs.bootstrap import bot
from cogs._component_runtime import runtime_namespace, runtime_value
from cogs.panel_registry import upsert_fixed_panel
from cogs._rtl import patch_discord_rtl

# Fix Darija/Arabic RTL rendering globally, before any cog builds an embed
# or sends a message. See cogs/_rtl.py for details.
patch_discord_rtl()


# Dependency-safe order of the split source sections plus focused new systems.
CORE_COGS = [
    "cogs.persistent_state",
    "cogs.xp_runtime",
    "cogs.settings_storage",
    "cogs.ai_conversation",
    "cogs.content_apis",
    "cogs.moderation_core",
    "cogs.access_panels",
    "cogs.support_system",
    "cogs.applications",
    "cogs.suggestions",
    "cogs.birthdays",
    "cogs.relationships",
    "cogs.temp_voice",
    "cogs.temp_music",
    "cogs.voice_runtime",
    "cogs.server_setup",
    "cogs.member_events",
    "cogs.moderation_commands",
    "cogs.xp_admin",
    "cogs.bot_admin_panel",
    "cogs.leveling_commands",
    "cogs.levels_center",
    "cogs.verification_commands",
    "cogs.general_commands",
    "cogs.automation_tasks",
    "cogs.owner_control",
    "cogs.ready_events",
]


# Standalone Cogs keep their dependency-safe order.
GAMES_COGS = [
    "cogs.economy",
    "cogs.city",
    "cogs.city.businesses",
    "cogs.games_panel",
    "cogs.game_counting",
    "cogs.game_tictactoe",
    "cogs.game_hangman",
    "cogs.game_wordle",
    "cogs.game_reaction",
    "cogs.trivia",
    "cogs.game_dice",
    "cogs.game_coinflip",
    "cogs.game_slots",
    "cogs.game_scratch",
    "cogs.game_lottery",
    "cogs.gambling_panel",
    "cogs.moderation",
    "cogs.unverified_visibility",
    "cogs.temp_room_full_control",
    # 🔒 نظام السجن — خاصو يتحمل قبل ما يعيطو عليه باقي الـCogs فالـruntime
    "cogs.prison",
    "cogs.prison_panel",
    # 🛡️ قفل الصلاحيات — آخر واحد باش يشوف كاع الرومز ديال الأنظمة الأخرى
    "cogs.channel_lockdown",
]

# هاد الـCog أمني: إلا فشل ما خاصش البوت يكمل وكأن الحماية خدامة.
REQUIRED_STANDALONE_COGS = {
    "cogs.economy",
    "cogs.city",
    "cogs.city.businesses",
    "cogs.unverified_visibility",
    "cogs.prison",
}


def _configure_cog_bridge(shared):
    # All public fixed panels use the same lock-aware upsert primitive.  The
    # mechanically split core components resolve globals from ``shared`` at
    # call time, so exposing it here keeps their source independent of the
    # standalone cogs while still serialising ready/loop/owner refreshes.
    shared["upsert_fixed_panel"] = upsert_fixed_panel
    bot.gg = {
        "DATA_DIR": shared["DATA_DIR"],
        "OWNER_ID": shared["OWNER_ID"],
        "ADMIN_ROLE_ID": shared["ADMIN_ROLE_ID"],
        "MODERATOR_ROLE_ID": shared["MODERATOR_ROLE_ID"],
        "MUTED_ROLE_ID": shared["MUTED_ROLE_ID"],
        # ── Prison / lockdown systems need these too ──
        "MEMBER_ROLE_ID": shared["MEMBER_ROLE_ID"],
        "BOYS_ROLE_ID": shared["BOYS_ROLE_ID"],
        "GIRLS_ROLE_ID": shared["GIRLS_ROLE_ID"],
        "MOD_LOGS_CHANNEL_ID": shared["MOD_LOGS_CHANNEL_ID"],
        "OWNER_CONTROL_CHANNEL_ID": shared["OWNER_CONTROL_CHANNEL_ID"],
        "TEMP_VC_CATEGORY_ID": shared["TEMP_VC_CATEGORY_ID"],
        "EXEMPT_ROLE_IDS": shared["EXEMPT_ROLE_IDS"],
        "JOIN_TO_CREATE_CHANNEL_ID": shared["JOIN_TO_CREATE_CHANNEL_ID"],
        "UNVERIFIED_ROLE_ID": shared["UNVERIFIED_ROLE_ID"],
        "RULES_CHANNEL_ID": shared["RULES_CHANNEL_ID"],
        "VERIFY_CHANNEL_ID": shared["VERIFY_CHANNEL_ID"],
        "get_panel_language": shared["get_panel_language"],
        "set_panel_language": shared["set_panel_language"],
        "upsert_ephemeral_panel": shared["upsert_ephemeral_panel"],
        "upsert_fixed_panel": upsert_fixed_panel,
        "get_user_level_data": shared["get_user_level_data"],
        "get_level_perks": shared["get_level_perks"],
        "save_levels": shared["save_levels"],
        "log_action": shared["log_action"],
        "is_exempt": shared["is_exempt"],
        "call_openrouter_chat": shared["call_openrouter_chat"],
        "temp_voice_channels": shared["temp_voice_channels"],
        "temp_voice_acl": shared["temp_voice_acl"],
        "is_temp_voice_channel": shared["is_temp_voice_channel"],
        "is_temp_voice_owner": shared["is_temp_voice_owner"],
        "get_temp_voice_acl": shared["get_temp_voice_acl"],
        "temp_voice_allow_member": shared["temp_voice_allow_member"],
        "temp_voice_deny_member": shared["temp_voice_deny_member"],
        "temp_voice_block_member": shared["temp_voice_block_member"],
        "temp_voice_unblock_member": shared["temp_voice_unblock_member"],
        "temp_voice_kick_member": shared["temp_voice_kick_member"],
        "temp_voice_set_manual_mute": shared["temp_voice_set_manual_mute"],
        "temp_voice_set_voice_mute": shared["temp_voice_set_voice_mute"],
        "temp_voice_set_chat_mute": shared["temp_voice_set_chat_mute"],
        "is_temp_voice_protected_target": shared["is_temp_voice_protected_target"],
        "set_temp_voice_private": shared["set_temp_voice_private"],
        "refresh_temp_voice_control_panel": shared["refresh_temp_voice_control_panel"],
        "enforce_temp_voice_security_overwrites": shared["enforce_temp_voice_security_overwrites"],
    }


@bot.event
async def setup_hook():
    """Load all split systems before slash-command synchronization."""
    for extension in CORE_COGS:
        try:
            await bot.load_extension(extension)
            print(f"✅ Core Cog محمّل: {extension}")
        except Exception as exc:
            print(f"❌ فشل تحميل Core Cog {extension}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            raise

    shared = runtime_namespace()
    _configure_cog_bridge(shared)

    # Persistent public/private control centers (same three as before).
    bot.add_view(shared["LevelsInfoView"]())
    bot.add_view(shared["OwnerControlCenterView"]())
    bot.add_view(shared["SupportCenterView"]())

    for extension in GAMES_COGS:
        try:
            await bot.load_extension(extension)
            print(f"✅ Cog محمّل: {extension}")
        except Exception as exc:
            print(f"❌ فشل تحميل {extension}: {type(exc).__name__}: {exc}")
            traceback.print_exc()
            if extension in REQUIRED_STANDALONE_COGS:
                raise


def __getattr__(name):
    """Compatibility for optional legacy imports that still target ai_bot."""
    return runtime_value(name)


if __name__ == "__main__":
    shared = runtime_namespace()
    if not shared["DISCORD_TOKEN"] or not shared["OPENROUTER_API_KEY"]:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(shared["DISCORD_TOKEN"])
