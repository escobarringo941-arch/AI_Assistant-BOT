# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║  cogs/owner_channel_autoclean.py — 🧹 تنظيف قناة الاونر  ║
═══════════════════════════════════════════════════════

الهدف: شانيل Owner Control Center تبقى ديما فيها غير رسالة البانل
الرسمية (Embed + الأزرار)، وصافي. أي رسالة أخرى — لوگات "Lockdown —
تصحيح صلاحيات"، ريبورتات refresh، أي رسالة كيبعثها شي cog آخر لهاد
الشانيل، ولا حتى كتابة يدوية — كتتمسح أوتوماتيكياً:

  • فالحين ملي تبان (on_message)
  • مسح دوري كل SWEEP_MINUTES (safety net — إلا فاتت شي رسالة، ولا
    البوت كان مطفي ملي تبعثت)
  • مسح فالبداية (on_ready) باش يتصافى أي قديم متراكم

كيتعرف على رسالة البانل الرسمية بنفس الطريقة اللي كيستعملها
setup_owner_control_panel (owner_control.py): رسالة ديال البوت
فيها Embed وعنوانو فيه "Owner Control Center".
"""

from __future__ import annotations

import asyncio

import discord
from discord.ext import commands, tasks

import bot_core as core

SWEEP_MINUTES = 5


def _is_panel_message(bot_user_id: int, message: discord.Message) -> bool:
    if message.author.id != bot_user_id:
        return False
    if not message.embeds:
        return False
    title = message.embeds[0].title or ""
    return "Owner Control Center" in title


class OwnerChannelAutoClean(commands.Cog):
    """كيخلي شانيل Owner Control Center غير البانل — كاع الباقي كيتمسح."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_id = int(getattr(core, "OWNER_CONTROL_CHANNEL_ID", 0) or 0)
        self._ready_done = False
        self.sweep_loop.start()

    def cog_unload(self):
        self.sweep_loop.cancel()

    async def _purge_channel(self, channel: discord.abc.GuildChannel) -> int:
        removed = 0
        try:
            async for msg in channel.history(limit=200):
                if _is_panel_message(self.bot.user.id, msg):
                    continue
                try:
                    await msg.delete()
                    removed += 1
                    await asyncio.sleep(0.3)
                except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                    pass
        except (discord.Forbidden, discord.HTTPException):
            pass
        return removed

    # ─────────────────────────────────────────────
    # الأحداث
    # ─────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready_done or not self.channel_id:
            return
        self._ready_done = True
        await asyncio.sleep(16)  # نخليو setup_owner_control_panel يصاوب/يحدث البانل الأول
        for guild in self.bot.guilds:
            channel = guild.get_channel(self.channel_id)
            if channel is None:
                continue
            removed = await self._purge_channel(channel)
            if removed:
                print(f"[OWNER-CLEAN] 🧹 {guild.name}: تمسحو {removed} رسالة زايدة من قناة الاونر.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.channel_id or message.channel.id != self.channel_id:
            return
        if _is_panel_message(self.bot.user.id, message):
            return
        try:
            await message.delete()
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass

    @tasks.loop(minutes=SWEEP_MINUTES)
    async def sweep_loop(self):
        if not self.channel_id:
            return
        for guild in self.bot.guilds:
            channel = guild.get_channel(self.channel_id)
            if channel is not None:
                await self._purge_channel(channel)

    @sweep_loop.before_loop
    async def _before_sweep(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(OwnerChannelAutoClean(bot))
    print("✅ Owner Channel Auto-Clean: قناة الاونر غادي تبقى غير البانل، والباقي كيتمسح")
