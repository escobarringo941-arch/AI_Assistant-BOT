# -*- coding: utf-8 -*-
"""GGMW9 bot entrypoint.

All bounded systems and commands live in cogs/.  This file only owns the bot
bootstrap, compatibility service bridge, ordered extension loading, and run.
"""

import importlib
import traceback

import discord

import bot_core as core


bot = core.bot
DISCORD_TOKEN = core.DISCORD_TOKEN
OPENROUTER_API_KEY = core.OPENROUTER_API_KEY


SYSTEM_COGS = [
    "cogs.system_verification",
    "cogs.system_support",
    "cogs.system_community",
    "cogs.system_voice",
    "cogs.system_leveling",
    "cogs.system_moderation",
    "cogs.system_general",
    "cogs.system_owner",
    "cogs.system_lifecycle",
]

# Existing game/economy Cogs keep their original, dependency-sensitive order.
GAMES_COGS = [
    "cogs.economy",
    "cogs.city",
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
    "cogs.temp_room_full_control",
]


def _base_bridge():
    return {
        "DATA_DIR": core.DATA_DIR,
        "OWNER_ID": core.OWNER_ID,
        "get_panel_language": core.get_panel_language,
        "set_panel_language": core.set_panel_language,
        "upsert_ephemeral_panel": core.upsert_ephemeral_panel,
        "get_user_level_data": core.get_user_level_data,
        "get_level_perks": core.get_level_perks,
        "save_levels": core.save_levels,
        "log_action": core.log_action,
        "is_exempt": core.is_exempt,
        "call_openrouter_chat": core.call_openrouter_chat,
    }


bot.gg = _base_bridge()


async def _load_extensions(extension_names):
    for extension in extension_names:
        try:
            await bot.load_extension(extension)
            print(f"✅ Cog محمّل: {extension}")
        except Exception as error:
            print(f"❌ فشل تحميل {extension}: {type(error).__name__}: {error}")
            traceback.print_exc()


def _attach_temp_voice_bridge():
    voice = importlib.import_module("cogs.system_voice")
    bot.gg.update({
        "temp_voice_channels": voice.temp_voice_channels,
        "temp_voice_acl": voice.temp_voice_acl,
        "is_temp_voice_channel": voice.is_temp_voice_channel,
        "is_temp_voice_owner": voice.is_temp_voice_owner,
        "get_temp_voice_acl": voice.get_temp_voice_acl,
        "temp_voice_allow_member": voice.temp_voice_allow_member,
        "temp_voice_deny_member": voice.temp_voice_deny_member,
        "temp_voice_block_member": voice.temp_voice_block_member,
        "temp_voice_unblock_member": voice.temp_voice_unblock_member,
        "temp_voice_kick_member": voice.temp_voice_kick_member,
        "temp_voice_set_manual_mute": voice.temp_voice_set_manual_mute,
        "temp_voice_set_voice_mute": voice.temp_voice_set_voice_mute,
        "temp_voice_set_chat_mute": voice.temp_voice_set_chat_mute,
        "is_temp_voice_protected_target": voice.is_temp_voice_protected_target,
        "set_temp_voice_private": voice.set_temp_voice_private,
        "refresh_temp_voice_control_panel": voice.refresh_temp_voice_control_panel,
    })


# Preserve the old design: prefix commands stay disabled because the ordered
# message pipeline intentionally does not call bot.process_commands().
@bot.event
async def on_message(message: discord.Message):
    return None


@bot.event
async def setup_hook():
    await _load_extensions(SYSTEM_COGS)
    _attach_temp_voice_bridge()

    # These three views were registered by the original setup_hook (before
    # on_ready adds the remaining persistent views).
    bot.add_view(core.LevelsInfoView())
    bot.add_view(core.OwnerControlCenterView())
    bot.add_view(core.SupportCenterView())

    await _load_extensions(GAMES_COGS)


if __name__ == "__main__":
    if not DISCORD_TOKEN or not OPENROUTER_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
