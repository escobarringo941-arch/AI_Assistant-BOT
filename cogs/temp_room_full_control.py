# -*- coding: utf-8 -*-
"""
🎤 نظام الروم المؤقتة - أمر واحد + بانل بأزرار!

جديد فهاد النسخة:
  • 🔒/🔓 خاص/عام: المالك يقدر يدير الروم "خاصة" — حتى واحد ما يدخل حتى تسمحلو
  • ✅ سماح (allow): كتزيد شخص للائحة المسموحين، يقدر يدخل حتى ملي الروم خاصة
  • 🔐 حظر (block): يبقى ممنوع فكل الحالات (حتى ملي الروم عامة) — وكيطرد توا إلا كان داخل
  • 🎛️ بانل بأزرار: زر لكل أمر (مافيش حاجة تكتب Slash Command) — كيتبعث وحدو
    ملي تتخلق الروم، وتقدر تعاود تصاوبو بـ /room panel

⚠️ ملاحظة مهمة (قيد تقني ديال ديسكورد نفسو، ماشي مشكل فالبوت):
  عضو عندو صلاحية "Administrator" (مدير كامل) فالسيرفر كيتجاوز صلاحيات القنوات
  (channel overwrites) بشكل تلقائي من ديسكورد — يعني حتى تحظرو، يقدر يدخل. هادشي
  خاص ب كل بوتات ديسكورد بلا استثناء. أما الـ Moderators اللي ماعندهمش
  Administrator كاملة، حظرهم غادي يخدم عادي.
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from typing import Optional

# ملف الـ Join to Create ديال البوت الرئيسي (ai_bot) — هو المصدر الحقيقي لصاحب الروم
EXTERNAL_TEMP_VOICE_PATH = "/app/data/temp_voice.json"


def default_room():
    return {
        "owner": None,
        "muted": [],
        "blocked": [],
        "allowed": [],
        "private": False,
    }


class TempRoom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = {}
        self.load_data()

    def load_data(self):
        os.makedirs("data", exist_ok=True)
        if os.path.exists("data/temp_room.json"):
            with open("data/temp_room.json", "r", encoding="utf-8") as f:
                self.data = json.load(f)
        # migration: كاع الروومات القديمة خاصهم "allowed" و"private"
        for cid, room in self.data.items():
            room.setdefault("muted", [])
            room.setdefault("blocked", [])
            room.setdefault("allowed", [])
            room.setdefault("private", False)

    def save_data(self):
        with open("data/temp_room.json", "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def is_temp_room(self, channel):
        if not channel or not channel.category:
            return False
        return "🎤" in channel.category.name or "temp" in channel.category.name.lower()

    def get_external_owner_id(self, channel):
        """كيقرا صاحب الروم من ملف الـ Join to Create ديال ai_bot (temp_voice.json)."""
        try:
            if os.path.exists(EXTERNAL_TEMP_VOICE_PATH):
                with open(EXTERNAL_TEMP_VOICE_PATH, "r", encoding="utf-8") as f:
                    external = json.load(f)
                owner_id = external.get(str(channel.id))
                return int(owner_id) if owner_id is not None else None
        except Exception:
            pass
        return None

    def is_owner(self, member, channel):
        cid = str(channel.id)
        if cid in self.data and self.data[cid]["owner"] is not None:
            return self.data[cid]["owner"] == member.id

        # ما كايناش مسجل عندنا؟ نشوفو عند ai_bot (Join to Create) — هو صاحب الحقيقة
        external_owner_id = self.get_external_owner_id(channel)
        if external_owner_id is not None:
            return external_owner_id == member.id

        return member.guild_permissions.manage_channels

    def register_owner(self, channel, owner):
        cid = str(channel.id)
        if cid not in self.data:
            self.data[cid] = default_room()
            self.data[cid]["owner"] = owner.id
            self.save_data()
        elif self.data[cid]["owner"] is None:
            self.data[cid]["owner"] = owner.id
            self.save_data()

    def get_room(self, channel):
        cid = str(channel.id)
        if cid not in self.data:
            self.data[cid] = default_room()
        return self.data[cid]

    # ═══════════════════════════════════════════════════════════════
    # تطبيق الصلاحيات: خاص/عام + المسموحين + المحظورين — دفعة وحدة
    # ═══════════════════════════════════════════════════════════════
    async def apply_permissions(self, channel: discord.VoiceChannel):
        room = self.get_room(channel)
        guild = channel.guild
        everyone = guild.default_role

        # كنبدأو من الصلاحيات الحالية (باش ما نمسحوش صلاحية المالك، Unverified، إلخ)
        overwrites = dict(channel.overwrites)

        # 1) @everyone: خاصة = مخبية + ممنوع الدخول | عامة = ترجع للحالة الافتراضية
        everyone_ow = overwrites.get(everyone, discord.PermissionOverwrite())
        if room["private"]:
            everyone_ow.view_channel = False
            everyone_ow.connect = False
        else:
            everyone_ow.view_channel = None
            everyone_ow.connect = None
        overwrites[everyone] = everyone_ow

        # 2) المسموحين — يقدرو يشوفو ويدخلو حتى ملي الروم خاصة
        for uid in room["allowed"]:
            target = guild.get_member(uid) or discord.Object(id=uid)
            ow = overwrites.get(target, discord.PermissionOverwrite())
            ow.view_channel = True
            ow.connect = True
            overwrites[target] = ow

        # 3) المحظورين — ممنوعين فكل الحالات (حتى لو الروم عامة)
        for uid in room["blocked"]:
            target = guild.get_member(uid) or discord.Object(id=uid)
            ow = overwrites.get(target, discord.PermissionOverwrite())
            ow.view_channel = False
            ow.connect = False
            ow.send_messages = False
            ow.speak = False
            overwrites[target] = ow

        try:
            await channel.edit(overwrites=overwrites, reason="Room Panel — تحديث الصلاحيات")
        except discord.Forbidden:
            pass

    def build_status_embed(self, channel):
        room = self.get_room(channel)
        muted = "\n".join([f"🔇 <@{m}>" for m in room["muted"]]) or "بلا"
        blocked = "\n".join([f"🔐 <@{b}>" for b in room["blocked"]]) or "بلا"
        allowed = "\n".join([f"✅ <@{a}>" for a in room["allowed"]]) or "بلا"

        embed = discord.Embed(
            title=f"🎤 {channel.name}",
            description=(
                f"**الحالة:** {'🔒 خاصة (محدودة للمسموحين فقط)' if room['private'] else '🔓 عامة (مفتوحة للجميع ماعدا المحظورين)'}\n"
                f"**المالك:** <@{room['owner']}>" if room["owner"] else "**الحالة:** —"
            ),
            color=discord.Color.blue()
        )
        embed.add_field(name="✅ مسموحين (فحالة الخصوصية)", value=allowed, inline=False)
        embed.add_field(name="🔐 محظورين (دايماً)", value=blocked, inline=False)
        embed.add_field(name="🔇 مكتومين", value=muted, inline=False)
        embed.set_footer(text="🎛️ استعمل الأزرار تحت باش تدير أي أمر — بلا ما تكتب حتى Slash Command")
        return embed

    # ═══════════════════════════════════════════════════════════════
    # الأوامر الأساسية اللي كانت موجودة (مافيهاش تبديل)
    # ═══════════════════════════════════════════════════════════════

    async def do_mute(self, actor, channel, user):
        if not self.is_owner(actor, channel):
            return "❌ أنت ما مالك الروم!"
        room = self.get_room(channel)
        self.register_owner(channel, actor)
        if user.id in room["muted"]:
            return "⚠️ محكوم بالفعل"
        room["muted"].append(user.id)
        self.save_data()
        member = channel.guild.get_member(user.id)
        if member:
            try:
                await member.edit(mute=True)
            except (discord.Forbidden, discord.HTTPException):
                pass
        return f"🔇 {user.mention} مكتوم!"

    async def do_unmute(self, actor, channel, user):
        if not self.is_owner(actor, channel):
            return "❌ أنت ما مالك الروم!"
        room = self.get_room(channel)
        if user.id not in room["muted"]:
            return "⚠️ ما كان مكتوم"
        room["muted"].remove(user.id)
        self.save_data()
        member = channel.guild.get_member(user.id)
        if member:
            try:
                await member.edit(mute=False)
            except (discord.Forbidden, discord.HTTPException):
                pass
        return f"🔊 الكتم رفع على {user.mention}!"

    async def do_kick(self, actor, channel, user):
        if not self.is_owner(actor, channel):
            return "❌ أنت ما مالك الروم!"
        member = channel.guild.get_member(user.id)
        if member and member in channel.members:
            try:
                await member.move_to(None)
            except (discord.Forbidden, discord.HTTPException):
                pass
            return f"🚫 {user.mention} طيح من الروم!"
        return "⚠️ هاد العضو ماشي فالروم دابا."

    async def do_block(self, actor, channel, user):
        if not self.is_owner(actor, channel):
            return "❌ أنت ما مالك الروم!"
        room = self.get_room(channel)
        self.register_owner(channel, actor)
        if user.id in room["blocked"]:
            return "⚠️ محظور بالفعل"
        room["blocked"].append(user.id)
        if user.id in room["allowed"]:
            room["allowed"].remove(user.id)  # الحظر كيغلب على السماح
        self.save_data()
        await self.apply_permissions(channel)
        member = channel.guild.get_member(user.id)
        if member and member in channel.members:
            try:
                await member.move_to(None)
            except (discord.Forbidden, discord.HTTPException):
                pass
        return f"🔐 {user.mention} محظور! (حتى لو الروم عامة)"

    async def do_unblock(self, actor, channel, user):
        if not self.is_owner(actor, channel):
            return "❌ أنت ما مالك الروم!"
        room = self.get_room(channel)
        if user.id not in room["blocked"]:
            return "⚠️ ما كان محظور"
        room["blocked"].remove(user.id)
        self.save_data()
        await self.apply_permissions(channel)
        return f"✅ الحظر رفع على {user.mention}!"

    async def do_allow(self, actor, channel, user):
        if not self.is_owner(actor, channel):
            return "❌ أنت ما مالك الروم!"
        room = self.get_room(channel)
        self.register_owner(channel, actor)
        if user.id in room["blocked"]:
            return f"❌ {user.mention} محظور — فك الحظر عليه بالأول قبل ما تسمحلو."
        if user.id in room["allowed"]:
            return "⚠️ مسموح ليه بالفعل"
        room["allowed"].append(user.id)
        self.save_data()
        await self.apply_permissions(channel)
        return f"✅ {user.mention} دابا يقدر يدخل، حتى لو الروم خاصة!"

    async def do_disallow(self, actor, channel, user):
        if not self.is_owner(actor, channel):
            return "❌ أنت ما مالك الروم!"
        room = self.get_room(channel)
        if user.id not in room["allowed"]:
            return "⚠️ ما كانش مسموح ليه بالخصوص"
        room["allowed"].remove(user.id)
        self.save_data()
        await self.apply_permissions(channel)
        return f"↩️ حيّدنا {user.mention} من لائحة المسموحين."

    async def do_toggle_private(self, actor, channel):
        if not self.is_owner(actor, channel):
            return "❌ أنت ما مالك الروم!"
        room = self.get_room(channel)
        self.register_owner(channel, actor)
        room["private"] = not room["private"]
        self.save_data()
        await self.apply_permissions(channel)
        if room["private"]:
            return ("🔒 الروم دابا **خاصة**! ماحدش يقدر يشوفها ولا يدخلها إلا اللي زدتيه فلائحة "
                    "المسموحين (✅ سماح)، ولا اللي عندو صلاحية Administrator كاملة فالسيرفر.")
        return "🔓 الروم دابا **عامة**! الكل يقدر يدخلها ماعدا المحظورين."

    # ═══════════════════════════════════════════════════════════════
    # أمر واحد فقط: /room
    # ═══════════════════════════════════════════════════════════════

    room = app_commands.Group(name="room", description="🎤 إدارة الروم")

    @room.command(name="mute", description="🔇 كتم الصوت")
    async def mute(self, ctx: discord.Interaction, user: discord.User):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        msg = await self.do_mute(ctx.user, ch, user)
        await ctx.response.send_message(msg, ephemeral=msg.startswith(("❌", "⚠️")))

    @room.command(name="unmute", description="🔊 فك الكتم")
    async def unmute(self, ctx: discord.Interaction, user: discord.User):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        msg = await self.do_unmute(ctx.user, ch, user)
        await ctx.response.send_message(msg, ephemeral=msg.startswith(("❌", "⚠️")))

    @room.command(name="kick", description="🚫 طيح من الروم")
    async def kick(self, ctx: discord.Interaction, user: discord.User):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        msg = await self.do_kick(ctx.user, ch, user)
        await ctx.response.send_message(msg, ephemeral=msg.startswith(("❌", "⚠️")))

    @room.command(name="block", description="🔐 حظر كامل (يبقى ممنوع حتى فالحالة العامة)")
    async def block(self, ctx: discord.Interaction, user: discord.User):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        msg = await self.do_block(ctx.user, ch, user)
        await ctx.response.send_message(msg, ephemeral=msg.startswith(("❌", "⚠️")))

    @room.command(name="unblock", description="✅ فك الحظر")
    async def unblock(self, ctx: discord.Interaction, user: discord.User):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        msg = await self.do_unblock(ctx.user, ch, user)
        await ctx.response.send_message(msg, ephemeral=msg.startswith(("❌", "⚠️")))

    @room.command(name="allow", description="✅ سماح لعضو بالدخول حتى ملي الروم خاصة")
    async def allow(self, ctx: discord.Interaction, user: discord.User):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        msg = await self.do_allow(ctx.user, ch, user)
        await ctx.response.send_message(msg, ephemeral=msg.startswith(("❌", "⚠️")))

    @room.command(name="disallow", description="↩️ حيّد عضو من لائحة المسموحين")
    async def disallow(self, ctx: discord.Interaction, user: discord.User):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        msg = await self.do_disallow(ctx.user, ch, user)
        await ctx.response.send_message(msg, ephemeral=msg.startswith(("❌", "⚠️")))

    @room.command(name="private", description="🔒 بدّل الروم بين خاصة/عامة")
    async def private(self, ctx: discord.Interaction):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        msg = await self.do_toggle_private(ctx.user, ch)
        await ctx.response.send_message(msg, ephemeral=msg.startswith("❌"))

    @room.command(name="list", description="📋 شوف الحالة الكاملة ديال الروم")
    async def list_cmd(self, ctx: discord.Interaction):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        if not self.is_owner(ctx.user, ch):
            return await ctx.response.send_message("❌ أنت ما مالك الروم!", ephemeral=True)
        await ctx.response.send_message(embed=self.build_status_embed(ch), ephemeral=True)

    @room.command(name="panel", description="🎛️ ابعث بانل بأزرار باش تسهّل التحكم فالروم")
    async def panel(self, ctx: discord.Interaction):
        ch = ctx.user.voice.channel if ctx.user.voice else None
        if not ch or not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ خاصك تكون فروم مؤقتة!", ephemeral=True)
        if not self.is_owner(ctx.user, ch):
            return await ctx.response.send_message("❌ أنت ما مالك الروم!", ephemeral=True)
        await ctx.response.send_message(embed=self.build_status_embed(ch), view=RoomPanelView(self))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel and after.channel != before.channel:
            ch = after.channel
            cid = str(ch.id)

            new_room = cid not in self.data and self.is_temp_room(ch)
            if new_room:
                self.register_owner(ch, member)

            room = self.data.get(cid)
            if room:
                if member.id in room["blocked"]:
                    try:
                        await member.move_to(None)
                    except (discord.Forbidden, discord.HTTPException):
                        pass

                if member.id in room["muted"]:
                    try:
                        await member.edit(mute=True)
                    except (discord.Forbidden, discord.HTTPException):
                        pass

            # ═══ كنبعثو البانل وحدو أول مرة كتتخلق فيها الروم (بلا ما يطلب المالك حتى شي حاجة) ═══
            if new_room:
                try:
                    await ch.send(
                        content=f"🎛️ مرحبا {member.mention}! هادي الروم ديالك، تحكم فيها بالأزرار تحت:",
                        embed=self.build_status_embed(ch),
                        view=RoomPanelView(self)
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass


# ═══════════════════════════════════════════════════════════════
# 🎛️ بانل بأزرار — بلا ما تكتب حتى Slash Command
# ═══════════════════════════════════════════════════════════════

class RoomActionSelect(discord.ui.UserSelect):
    """Select كيبين مربع بحث للأعضاء — كتختار واحد وكيتطبق عليه الأمر توا."""

    LABELS = {
        "mute": "🎯 اختار عضو باش تكتمو...",
        "unmute": "🎯 اختار عضو باش تفك عليه الكتم...",
        "kick": "🎯 اختار عضو باش تطيحو من الروم...",
        "block": "🎯 اختار عضو باش تحظرو (دايماً)...",
        "unblock": "🎯 اختار عضو باش تفك عليه الحظر...",
        "allow": "🎯 اختار عضو باش تسمحلو يدخل (حتى ملي الروم خاصة)...",
        "disallow": "🎯 اختار عضو باش تحيدو من لائحة المسموحين...",
    }

    def __init__(self, cog: "TempRoom", channel, action: str):
        super().__init__(placeholder=self.LABELS[action], min_values=1, max_values=1)
        self.cog = cog
        self.channel = channel
        self.action = action

    async def callback(self, interaction: discord.Interaction):
        target = self.values[0]  # discord.Member ولا discord.User

        if not self.cog.is_owner(interaction.user, self.channel):
            return await interaction.response.send_message("❌ أنت ما مالك الروم!", ephemeral=True)

        handler = {
            "mute": self.cog.do_mute,
            "unmute": self.cog.do_unmute,
            "kick": self.cog.do_kick,
            "block": self.cog.do_block,
            "unblock": self.cog.do_unblock,
            "allow": self.cog.do_allow,
            "disallow": self.cog.do_disallow,
        }[self.action]

        msg = await handler(interaction.user, self.channel, target)
        await interaction.response.edit_message(content=msg, view=None)


class RoomActionPickView(discord.ui.View):
    """View مؤقتة (ephemeral) فيها غير الـ Select ديال اختيار العضو."""

    def __init__(self, cog: "TempRoom", channel, action: str):
        super().__init__(timeout=120)
        self.add_item(RoomActionSelect(cog, channel, action))


class RoomPanelView(discord.ui.View):
    """البانل الرئيسي — persistent (custom_id ثابت)، كيخدم حتى بعد ريستارت البوت.
    كل زر كيتأكد بروحو بلي الضاغط عليه هو مالك الروم ديالو الحالية قبل مايدير والو."""

    def __init__(self, cog: "TempRoom"):
        super().__init__(timeout=None)
        self.cog = cog

    async def _get_owner_channel(self, interaction: discord.Interaction):
        """كيرجع الروم الصوتية اللي فيها الضاغط دابا، وكيتأكد بلي هو المالك ديالها."""
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.voice or not member.voice.channel:
            await interaction.response.send_message("❌ خاصك تكون داخل الروم ديالك باش تستعمل هاد الزر!", ephemeral=True)
            return None
        channel = member.voice.channel
        if not self.cog.is_temp_room(channel):
            await interaction.response.send_message("❌ هاد الشي ماشي روم مؤقتة!", ephemeral=True)
            return None
        if not self.cog.is_owner(member, channel):
            await interaction.response.send_message("❌ أنت ما مالك هاد الروم!", ephemeral=True)
            return None
        return channel

    @discord.ui.button(label="🔒 خاص/عام", style=discord.ButtonStyle.primary, custom_id="room_panel_private", row=0)
    async def toggle_private_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._get_owner_channel(interaction)
        if not channel:
            return
        msg = await self.cog.do_toggle_private(interaction.user, channel)
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="✅ سماح لعضو", style=discord.ButtonStyle.success, custom_id="room_panel_allow", row=0)
    async def allow_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._get_owner_channel(interaction)
        if not channel:
            return
        await interaction.response.send_message(view=RoomActionPickView(self.cog, channel, "allow"), ephemeral=True)

    @discord.ui.button(label="🔐 حظر عضو", style=discord.ButtonStyle.danger, custom_id="room_panel_block", row=0)
    async def block_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._get_owner_channel(interaction)
        if not channel:
            return
        await interaction.response.send_message(view=RoomActionPickView(self.cog, channel, "block"), ephemeral=True)

    @discord.ui.button(label="↩️ فك حظر", style=discord.ButtonStyle.secondary, custom_id="room_panel_unblock", row=0)
    async def unblock_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._get_owner_channel(interaction)
        if not channel:
            return
        await interaction.response.send_message(view=RoomActionPickView(self.cog, channel, "unblock"), ephemeral=True)

    @discord.ui.button(label="🔇 كتم", style=discord.ButtonStyle.secondary, custom_id="room_panel_mute", row=1)
    async def mute_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._get_owner_channel(interaction)
        if not channel:
            return
        await interaction.response.send_message(view=RoomActionPickView(self.cog, channel, "mute"), ephemeral=True)

    @discord.ui.button(label="🔊 فك كتم", style=discord.ButtonStyle.secondary, custom_id="room_panel_unmute", row=1)
    async def unmute_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._get_owner_channel(interaction)
        if not channel:
            return
        await interaction.response.send_message(view=RoomActionPickView(self.cog, channel, "unmute"), ephemeral=True)

    @discord.ui.button(label="🚫 طرد", style=discord.ButtonStyle.secondary, custom_id="room_panel_kick", row=1)
    async def kick_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._get_owner_channel(interaction)
        if not channel:
            return
        await interaction.response.send_message(view=RoomActionPickView(self.cog, channel, "kick"), ephemeral=True)

    @discord.ui.button(label="↩️ حيّد من المسموحين", style=discord.ButtonStyle.secondary, custom_id="room_panel_disallow", row=1)
    async def disallow_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._get_owner_channel(interaction)
        if not channel:
            return
        await interaction.response.send_message(view=RoomActionPickView(self.cog, channel, "disallow"), ephemeral=True)

    @discord.ui.button(label="📋 الحالة الكاملة", style=discord.ButtonStyle.blurple, custom_id="room_panel_status", row=2)
    async def status_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = await self._get_owner_channel(interaction)
        if not channel:
            return
        await interaction.response.send_message(embed=self.cog.build_status_embed(channel), ephemeral=True)


async def setup(bot):
    cog = TempRoom(bot)
    await bot.add_cog(cog)
    bot.add_view(RoomPanelView(cog))  # باش الأزرار يبقاو خدامين حتى بعد ريستارت البوت
    print("✅ نظام الروم: /room + بانل بأزرار (خاص/عام، سماح، حظر، كتم، طرد)")
