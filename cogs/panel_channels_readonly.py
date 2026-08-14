# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║  cogs/panel_channels_readonly.py — 🔒 شانيلز البانلز فقط  ║
═══════════════════════════════════════════════════════

الهدف: فشانيلز البانلز الرسمية (البنك، القوانين/التفعيل، المتجر، الكازينو،
Trivia، Applications، الاقتراحات، Support Center، Blacklist، Levels/Leaderboard...)
ما يقدروش الأعضاء العاديين (Member/Boys/Girls) يكتبو والو — غير يستعملو
الأزرار/الـ Select/الـ Modal ديال البانل. التفاعل بالأزرار كيخدم حتى بلا
صلاحية "Send Messages"، فـ ماكاين حتى تأثير على البانلز نفسها.

الشانيلز اللي فيهم الكتابة مطلوبة بصح (بحال #counting و #general) ماشي
داخلين هنا — التقييد كيوقع غير على الشانيلز فـ PANEL_ONLY_CHANNEL_IDS تحت.

كيفرض روحو أوتوماتيكياً:
  • on_ready (مرة وحدة كل ما يشعل البوت)
  • أي تعديل يدوي على الـ overwrites ديال شي شانيل من اللائحة (on_guild_channel_update)

باش تزيد/تحيد شانيل من التقييد، زيد/حيد الـ ID من PANEL_ONLY_CHANNEL_IDS تحت.
باش تزيد/تحيد رول، بدل TARGET_ROLE_IDS.
"""

from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

import bot_core as core
import games_config as cfg

REASON_TAG = "GGMW9 Panel Read-Only"

# الصلاحيات اللي كنمنعوها: كتابة عادية + threads (باش ما يقدروش يدوروا على
# التقييد بخلق thread ويهضروا فيه).
_LOCKED_PERMS = (
    "send_messages",
    "send_messages_in_threads",
    "create_public_threads",
    "create_private_threads",
)


def _channel_ids() -> dict[int, str]:
    """لائحة الشانيلز 'بانل فقط' — القراءة والأزرار مسموحين، الكتابة ممنوعة."""
    raw = {
        getattr(core, "RULES_CHANNEL_ID", 0): "📜 القوانين / التفعيل",
        getattr(core, "VERIFY_CHANNEL_ID", 0): "✅ التفعيل",
        getattr(core, "BLACKLIST_CHANNEL_ID", 0): "🚫 الممنوعات (Blacklist)",
        getattr(core, "SUPPORT_CENTER_CHANNEL_ID", 0): "🎫 Support Center",
        getattr(core, "SUGGESTIONS_CHANNEL_ID", 0): "💡 الاقتراحات",
        getattr(core, "APPLICATIONS_PANEL_CHANNEL_ID", 0): "📋 التوظيف (Applications)",
        getattr(core, "LEVELS_INFO_CHANNEL_ID", 0): "🎚️ Levels / Leaderboard",
        getattr(core, "LEADERBOARD_CHANNEL_ID", 0): "🏆 Leaderboard",
        getattr(cfg, "ECONOMY_BANK_CHANNEL_ID", 0): "🏦 البنك",
        getattr(cfg, "SHOP_PANEL_CHANNEL_ID", 0): "🛒 المتجر",
        getattr(cfg, "GAMES_PANEL_CHANNEL_ID", 0): "🎮 Arcade (الألعاب)",
        getattr(cfg, "GAMES_LEADERBOARD_CHANNEL_ID", 0): "🏆 ترتيب الألعاب",
        getattr(cfg, "GAMBLING_CHANNEL_ID", 0): "🎰 الكازينو",
        getattr(cfg, "TRIVIA_CHANNEL_ID", 0): "📚 Trivia",
    }
    return {cid: label for cid, label in raw.items() if cid}


def _target_role_ids() -> set[int]:
    """الرولات العادية اللي كنقفلو عليهم الكتابة: Member + Boys + Girls."""
    ids = {
        int(getattr(core, "MEMBER_ROLE_ID", 0) or 0),
        int(getattr(core, "BOYS_ROLE_ID", 0) or 0),
        int(getattr(core, "GIRLS_ROLE_ID", 0) or 0),
    }
    ids.discard(0)
    return ids


class PanelChannelsReadOnly(commands.Cog):
    """كيمنع الكتابة/الـ threads فشانيلز البانلز الرسمية على Member/Boys/Girls."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ready_done = False
        self._lock = asyncio.Lock()

    # ─────────────────────────────────────────────
    # الفرض على شانيل وحدة
    # ─────────────────────────────────────────────
    async def _enforce_channel(self, channel: discord.abc.GuildChannel) -> bool:
        """كترجع True إلا دارت شي تعديل."""
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            return False

        guild = channel.guild
        changed_any = False
        for role_id in _target_role_ids():
            role = guild.get_role(role_id)
            if role is None:
                continue

            current = channel.overwrites_for(role)
            needs_update = any(getattr(current, perm) is not False for perm in _LOCKED_PERMS)
            if not needs_update:
                continue

            for perm in _LOCKED_PERMS:
                setattr(current, perm, False)

            try:
                await channel.set_permissions(
                    role, overwrite=current, reason=f"{REASON_TAG}: panel-only channel"
                )
                changed_any = True
                await asyncio.sleep(0.3)
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[PANEL-RO] ⚠️ {channel.name} / @{role.name}: {exc}")
        return changed_any

    async def enforce_all(self, guild: discord.Guild) -> int:
        async with self._lock:
            fixed = 0
            for channel_id in _channel_ids():
                channel = guild.get_channel(channel_id)
                if channel is None:
                    continue
                if await self._enforce_channel(channel):
                    fixed += 1
            if fixed:
                print(f"[PANEL-RO] 🔒 {guild.name}: {fixed} شانيل تصلحو (بانل فقط، بلا كتابة).")
            return fixed

    # ─────────────────────────────────────────────
    # الأحداث
    # ─────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready_done:
            return
        self._ready_done = True
        await asyncio.sleep(14)  # نخليو باقي البانلز يتصاوبو الأول
        for guild in self.bot.guilds:
            try:
                await self.enforce_all(guild)
            except Exception as exc:
                print(f"[PANEL-RO] ❌ {guild.id}: {type(exc).__name__}: {exc}")

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ):
        if after.id not in _channel_ids():
            return
        if before.overwrites == after.overwrites:
            return
        try:
            await self._enforce_channel(after)
        except Exception as exc:
            print(f"[PANEL-RO] ❌ channel_update: {type(exc).__name__}: {exc}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        # حالة نادرة: إلا تحيدت شانيل من اللائحة وتعاود خلقها بنفس الـID
        # (عملياً ما كيوقعش لأن الـID كيتبدل)، خليها هنا للأمان.
        if channel.id not in _channel_ids():
            return
        await asyncio.sleep(1.5)
        try:
            await self._enforce_channel(channel)
        except Exception as exc:
            print(f"[PANEL-RO] ❌ channel_create: {type(exc).__name__}: {exc}")


async def setup(bot: commands.Bot):
    await bot.add_cog(PanelChannelsReadOnly(bot))
    print("✅ Panel Channels Read-Only: البانلز محميين — الكتابة ممنوعة على Member/Boys/Girls")
