# -*- coding: utf-8 -*-
"""Keep the Unverified role hidden from every channel except verification."""

from __future__ import annotations

import asyncio

import discord
from discord.ext import commands


class UnverifiedVisibility(commands.Cog):
    """Apply and continuously repair the server's Unverified visibility policy."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bridge = getattr(bot, "gg", {})
        self.unverified_role_id = int(bridge.get("UNVERIFIED_ROLE_ID") or 0)
        self.visible_channel_ids = frozenset(
            int(channel_id)
            for channel_id in (
                bridge.get("RULES_CHANNEL_ID"),
                bridge.get("VERIFY_CHANNEL_ID"),
            )
            if channel_id
        )
        self._guild_locks: dict[int, asyncio.Lock] = {}

    def _lock_for(self, guild_id: int) -> asyncio.Lock:
        lock = self._guild_locks.get(guild_id)
        if lock is None:
            lock = asyncio.Lock()
            self._guild_locks[guild_id] = lock
        return lock

    def _is_visible_exception(self, channel: discord.abc.GuildChannel) -> bool:
        return channel.id in self.visible_channel_ids

    async def _set_visibility(
        self,
        channel: discord.abc.GuildChannel,
        role: discord.Role,
        *,
        visible: bool,
    ) -> tuple[bool, bool]:
        """Return ``(successful, changed)`` while preserving all other overwrite bits."""
        overwrite = channel.overwrites_for(role)
        if overwrite.view_channel is visible:
            return True, False

        overwrite.view_channel = visible
        try:
            await channel.set_permissions(
                role,
                overwrite=overwrite,
                reason="GGMW9 Unverified channel visibility policy",
            )
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            print(
                "[UNVERIFIED-VISIBILITY] "
                f"تعذر تعديل {channel.guild.name}/{channel.name} ({channel.id}): "
                f"{type(exc).__name__}: {exc}"
            )
            return False, False
        return True, True

    def _verification_channels(
        self,
        guild: discord.Guild,
    ) -> list[discord.abc.GuildChannel]:
        channels = []
        for channel_id in self.visible_channel_ids:
            channel = guild.get_channel(channel_id)
            if channel is not None:
                channels.append(channel)
        return channels

    async def sync_guild(self, guild: discord.Guild) -> None:
        """Repair every current category/channel, with verification protected first."""
        async with self._lock_for(guild.id):
            role = guild.get_role(self.unverified_role_id)
            if role is None:
                print(
                    f"[UNVERIFIED-VISIBILITY] {guild.name}: رول Unverified "
                    f"({self.unverified_role_id}) ما لقاهاش؛ المزامنة توقفات."
                )
                return

            verification_channels = self._verification_channels(guild)
            if not verification_channels:
                print(
                    f"[UNVERIFIED-VISIBILITY] {guild.name}: لا Rules لا Verify تلقاو؛ "
                    "خبّاية باقي السيرفر توقفات باش الأعضاء الجدد ما يتسدوش."
                )
                return

            # Make at least one verification route visible before hiding anything.
            safe_routes = 0
            updated = 0
            failed = 0
            for channel in verification_channels:
                success, changed = await self._set_visibility(channel, role, visible=True)
                safe_routes += int(success)
                updated += int(changed)
                failed += int(not success)

            if not safe_routes:
                print(
                    f"[UNVERIFIED-VISIBILITY] {guild.name}: ما قدرناش نظهرو قناة التفعيل؛ "
                    "خبّاية باقي السيرفر توقفات للحماية."
                )
                return

            protected_ids = {channel.id for channel in verification_channels}
            hidden_channels = [
                channel for channel in guild.channels if channel.id not in protected_ids
            ]
            hidden_channels.sort(
                key=lambda channel: (
                    0 if isinstance(channel, discord.CategoryChannel) else 1,
                    int(getattr(channel, "position", 0)),
                    channel.id,
                )
            )

            for channel in hidden_channels:
                success, changed = await self._set_visibility(channel, role, visible=False)
                updated += int(changed)
                failed += int(not success)

            # Reassert the exceptions after their parent categories were denied.
            for channel in verification_channels:
                success, changed = await self._set_visibility(channel, role, visible=True)
                updated += int(changed)
                failed += int(not success)

            print(
                f"[UNVERIFIED-VISIBILITY] {guild.name}: {updated} تبدلو، "
                f"{failed} فشلو، {len(guild.channels)} channel/category تفحصو."
            )

    async def _repair_channel(self, channel: discord.abc.GuildChannel) -> None:
        guild = channel.guild
        async with self._lock_for(guild.id):
            role = guild.get_role(self.unverified_role_id)
            if role is None:
                return

            if self._is_visible_exception(channel):
                await self._set_visibility(channel, role, visible=True)
                return

            # Never hide a new/updated channel unless at least one configured
            # verification route exists and is explicitly visible first.
            verification_channels = self._verification_channels(guild)
            safe_route = False
            for verification_channel in verification_channels:
                success, _ = await self._set_visibility(
                    verification_channel,
                    role,
                    visible=True,
                )
                safe_route = safe_route or success

            if not safe_route:
                print(
                    f"[UNVERIFIED-VISIBILITY] {guild.name}: ما كايناش قناة تفعيل "
                    f"صالحة؛ {channel.name} ({channel.id}) ما تخباتش للحماية."
                )
                return

            await self._set_visibility(channel, role, visible=False)

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        for guild in self.bot.guilds:
            await self.sync_guild(guild)

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        await self._repair_channel(channel)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self,
        before: discord.abc.GuildChannel,
        after: discord.abc.GuildChannel,
    ) -> None:
        role = after.guild.get_role(self.unverified_role_id)
        if role is None:
            return
        desired = self._is_visible_exception(after)
        if after.overwrites_for(role).view_channel is desired:
            return
        await self._repair_channel(after)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:
        self._guild_locks.pop(guild.id, None)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(UnverifiedVisibility(bot))
    print("✅ Unverified Visibility: كاع القنوات مخبيين حتى التفعيل")
