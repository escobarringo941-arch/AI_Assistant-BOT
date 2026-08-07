# -*- coding: utf-8 -*-
"""
🎤 نظام الروم المؤقتة — أوامر /room مرتبطة مباشرة بالنظام الرئيسي ديال Join-to-Create.
ماكايناش DB ثانية وماكاينش listener ثاني للـ Deny، باش مايبقاش تعارض.
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
            await ctx.response.send_message("❌ غير مول الروم يقدر يدير هاد العملية — Admin/Mod ماشي Owner ديالها.", ephemeral=True)
            return None
        return ch

    room = app_commands.Group(name="room", description="🎤 إدارة الروم المؤقتة ديالك")

    @room.command(name="allow", description="✅ سماح لعضو يدخل الروم حتى إلا كانت Private")
    async def allow(self, ctx: discord.Interaction, user: discord.Member):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        fn = self._gg("temp_voice_allow_member")
        if not fn:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        ok, msg = await fn(ch, user, actor=ctx.user)
        await ctx.followup.send(msg, ephemeral=True)

    @room.command(name="deny", description="⛔ عدم السماح لعضو يدخل الروم")
    async def deny(self, ctx: discord.Interaction, user: discord.Member):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        fn = self._gg("temp_voice_deny_member")
        if not fn:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        ok, msg = await fn(ch, user, actor=ctx.user)
        await ctx.followup.send(msg, ephemeral=True)

    # aliases باش الأوامر القديمة يبقاو خدامين
    @room.command(name="block", description="🔐 نفس /room deny")
    async def block(self, ctx: discord.Interaction, user: discord.Member):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        fn = self._gg("temp_voice_deny_member")
        if not fn:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        ok, msg = await fn(ch, user, actor=ctx.user)
        await ctx.followup.send(msg, ephemeral=True)

    @room.command(name="unblock", description="✅ نفس /room allow")
    async def unblock(self, ctx: discord.Interaction, user: discord.Member):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        fn = self._gg("temp_voice_allow_member")
        if not fn:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        ok, msg = await fn(ch, user, actor=ctx.user)
        await ctx.followup.send(msg, ephemeral=True)

    @room.command(name="mute", description="🔇 كتم عضو داخل الروم")
    async def mute(self, ctx: discord.Interaction, user: discord.Member):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        fn = self._gg("temp_voice_set_manual_mute")
        if not fn:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        ok, msg = await fn(ch, user, True, actor=ctx.user)
        await ctx.followup.send(msg, ephemeral=True)

    @room.command(name="unmute", description="🔊 فك الكتم على عضو داخل الروم")
    async def unmute(self, ctx: discord.Interaction, user: discord.Member):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        fn = self._gg("temp_voice_set_manual_mute")
        if not fn:
            return await ctx.response.send_message("❌ Temp Voice bridge ما تحملش مزيان.", ephemeral=True)
        await ctx.response.defer(ephemeral=True)
        ok, msg = await fn(ch, user, False, actor=ctx.user)
        await ctx.followup.send(msg, ephemeral=True)

    @room.command(name="kick", description="🚫 خرج عضو من الروم فقط")
    async def kick(self, ctx: discord.Interaction, user: discord.Member):
        ch = await self._owner_room(ctx)
        if not ch:
            return
        if user.id == ctx.user.id:
            return await ctx.response.send_message("❌ مايمكنش تخرج راسك بهاد الأمر.", ephemeral=True)
        if not user.voice or not user.voice.channel or user.voice.channel.id != ch.id:
            return await ctx.response.send_message("❌ هاد العضو ماشي داخل الروم دابا.", ephemeral=True)
        try:
            await user.move_to(None, reason=f"Temp room kick by {ctx.user}")
            await ctx.response.send_message(f"🚫 {user.mention} خرج من الروم.", ephemeral=True)
        except (discord.Forbidden, discord.HTTPException) as e:
            await ctx.response.send_message(f"❌ ما قدرتش نخرجو: {e}", ephemeral=True)

    @room.command(name="private", description="🔒 خلي الروم Private ولكن تبقى باينة للجميع")
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

    @room.command(name="list", description="📋 شوف Allow / Deny ديال الروم")
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
        attempts = rec.get("attempts", {})
        muted = rec.get("muted", [])
        embed = discord.Embed(
            title=f"📋 {ch.name}",
            description=f"الحالة: **{'🔒 Private' if rec.get('private') else '🔓 Public'}**",
            color=discord.Color.blurple()
        )
        def _lines(items, formatter, limit=20):
            vals = [formatter(x) for x in items[:limit]]
            if len(items) > limit:
                vals.append(f"... +{len(items) - limit}")
            return "\n".join(vals) or "—"

        embed.add_field(name=f"✅ مسموح ({len(allowed)})", value=_lines(allowed, lambda uid: f"<@{uid}>"), inline=False)
        embed.add_field(
            name=f"⛔ ممنوع ({len(denied)})",
            value=_lines(denied, lambda uid: f"<@{uid}> — محاولات: {attempts.get(str(uid), 0)}"),
            inline=False
        )
        embed.add_field(name=f"🔇 مكتومين ({len(muted)})", value=_lines(muted, lambda uid: f"<@{uid}>"), inline=False)
        await ctx.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(TempRoom(bot))
    print("✅ نظام الروم: /room + Allow/Deny مربوط بـ Join-to-Create")
