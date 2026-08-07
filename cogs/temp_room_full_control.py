# -*- coding: utf-8 -*-
"""
🎤 Temp Room commands — نفس source of truth ديال Join-to-Create فـ ai_bot.py.
ماكاين لا DB ثانية لا voice listener ثاني.
"""

import discord
from discord.ext import commands
from discord import app_commands


class TempRoom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _gg(self, key):
        return getattr(self.bot, "gg", {}).get(key)

    def is_temp_room(self, channel) -> bool:
        fn = self._gg("is_temp_voice_channel")
        return bool(fn and fn(channel))

    def is_owner(self, member, channel) -> bool:
        fn = self._gg("is_temp_voice_owner")
        return bool(fn and fn(member, channel))

    async def _owner_room(self, ctx: discord.Interaction):
        if not isinstance(ctx.user, discord.Member) or not ctx.user.voice or not ctx.user.voice.channel:
            await ctx.response.send_message("❌ خاصك تكون داخل الروم المؤقتة ديالك.", ephemeral=True)
            return None
        ch = ctx.user.voice.channel
        if not self.is_temp_room(ch):
            await ctx.response.send_message("❌ هادي ماشي روم مؤقتة ديال Join-to-Create.", ephemeral=True)
            return None
        if not self.is_owner(ctx.user, ch):
            await ctx.response.send_message("❌ غير مول الروم يقدر يتحكم فيها — Admin/Mod ماشي Owner ديالها.", ephemeral=True)
            return None
        return ch

    async def _call_member_action(self, ctx: discord.Interaction, bridge_name: str, user: discord.Member, *args):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        fn = self._gg(bridge_name)
        if not fn:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        ok, msg = await fn(ch, user, *args, actor=ctx.user)
        await ctx.followup.send(msg, ephemeral=True)

    room = app_commands.Group(name="room", description="🎤 تحكم كامل فالروم المؤقتة ديالك")

    @room.command(name="allow", description="✅ سمح لعضو يدخل حتى إلا كانت الروم Private")
    async def allow(self, ctx: discord.Interaction, user: discord.Member):
        await self._call_member_action(ctx, "temp_voice_allow_member", user)

    @room.command(name="block", description="🔐 خبي الروم على عضو ومنعو منها حتى Unblock")
    async def block(self, ctx: discord.Interaction, user: discord.Member):
        await self._call_member_action(ctx, "temp_voice_block_member", user)

    @room.command(name="unblock", description="🔓 فك Block وخلي الروم تبان للعضو من جديد")
    async def unblock(self, ctx: discord.Interaction, user: discord.Member):
        await self._call_member_action(ctx, "temp_voice_unblock_member", user)

    @room.command(name="deny", description="⛔ خلي الروم باينة ولكن منع العضو من الدخول")
    async def deny(self, ctx: discord.Interaction, user: discord.Member):
        await self._call_member_action(ctx, "temp_voice_deny_member", user)

    @room.command(name="kick", description="🚪 خرج عضو من الروم فقط بلا Block")
    async def kick(self, ctx: discord.Interaction, user: discord.Member):
        await self._call_member_action(ctx, "temp_voice_kick_member", user)

    @room.command(name="mute", description="🔇 كتم صوت عضو فهاد الروم")
    async def mute(self, ctx: discord.Interaction, user: discord.Member):
        await self._call_member_action(ctx, "temp_voice_set_voice_mute", user, True)

    @room.command(name="unmute", description="🔊 فك كتم الصوت على عضو")
    async def unmute(self, ctx: discord.Interaction, user: discord.Member):
        await self._call_member_action(ctx, "temp_voice_set_voice_mute", user, False)

    @room.command(name="chatmute", description="💬🔇 منع عضو من الكتابة فـ Chat ديال الروم")
    async def chatmute(self, ctx: discord.Interaction, user: discord.Member):
        await self._call_member_action(ctx, "temp_voice_set_chat_mute", user, True)

    @room.command(name="chatunmute", description="💬🔊 فك كتم الكتابة فـ Chat ديال الروم")
    async def chatunmute(self, ctx: discord.Interaction, user: discord.Member):
        await self._call_member_action(ctx, "temp_voice_set_chat_mute", user, False)

    @room.command(name="private", description="🔒 الروم تبقى باينة ولكن الدخول غير لـ Owner + Allowed")
    async def private(self, ctx: discord.Interaction):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        fn = self._gg("set_temp_voice_private")
        if not fn:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        ok, msg = await fn(ch, True, actor=ctx.user)
        await ctx.followup.send(msg, ephemeral=True)

    @room.command(name="public", description="🔓 رجع الروم Public")
    async def public(self, ctx: discord.Interaction):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        fn = self._gg("set_temp_voice_private")
        if not fn:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        ok, msg = await fn(ch, False, actor=ctx.user)
        await ctx.followup.send(msg, ephemeral=True)

    @room.command(name="list", description="📋 شوف Allow / Deny / Block / Voice Mute / Chat Mute")
    async def list_cmd(self, ctx: discord.Interaction):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        get_acl = self._gg("get_temp_voice_acl")
        if not get_acl:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        rec = get_acl(ch)
        allowed = rec.get("allowed", [])
        denied = rec.get("denied", [])
        blocked = rec.get("blocked", [])
        voice_muted = rec.get("voice_muted", [])
        chat_muted = rec.get("chat_muted", [])

        def lines(items, limit=20):
            vals = [f"<@{uid}>" for uid in items[:limit]]
            if len(items) > limit:
                vals.append(f"... +{len(items) - limit}")
            return "\n".join(vals) or "—"

        embed = discord.Embed(
            title=f"📋 {ch.name}",
            description=f"الحالة: **{'🔒 Private' if rec.get('private') else '🔓 Public'}**",
            color=discord.Color.blurple(),
        )
        embed.add_field(name=f"✅ Allowed ({len(allowed)})", value=lines(allowed), inline=False)
        embed.add_field(name=f"⛔ Denied ({len(denied)})", value=lines(denied), inline=False)
        embed.add_field(name=f"🔐 Blocked ({len(blocked)})", value=lines(blocked), inline=False)
        embed.add_field(name=f"🔇 Voice Muted ({len(voice_muted)})", value=lines(voice_muted), inline=False)
        embed.add_field(name=f"💬 Chat Muted ({len(chat_muted)})", value=lines(chat_muted), inline=False)
        await ctx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(TempRoom(bot))
    print("✅ نظام الروم: Panel + /room Allow/Deny/Block/Kick/VoiceMute/ChatMute")
