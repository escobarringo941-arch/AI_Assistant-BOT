# -- coding: utf-8 --
"""
🎤 نظام الروم المؤقتة - نسخة محسنة
الجديد فهاد النسخة:
• 🔒 الروم الخاصة = بَانََة لكاع الناس ولكن غير المسموحين يقدرو يدخلو
• 🛡️ حماية ضد تجاوز Admin/Administrator: البوت كيطرد أي واحد ماشي مسموح ليه
  من الروم ديركت، كيعطيه إنذارات، وبعد 3 محاولات كيعاقبو (kick من السيرفر ولا
  يخبي ليه الروم نهائياً)
• ⏰ البانل كيبين وقتاش تصاوبات الروم (منذ X دقايق) كيتحدث أوتوماتيكياً
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
        "intrusions": {},   # {user_id: عدد محاولات الدخول غير المصرح بها}
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
        # migration: كاع الروومات القديمة خاصهم الحقول الجداد
        for cid, room in self.data.items():
            room.setdefault("muted", [])
            room.setdefault("blocked", [])
            room.setdefault("allowed", [])
            room.setdefault("private", False)
            room.setdefault("intrusions", {})

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

    def _strict_owner_id(self, channel):
        """كيرجع ID ديال المالك الحقيقي — بلا ما يحسب Admins (مهم للحماية)."""
        cid = str(channel.id)
        if cid in self.data and self.data[cid].get("owner"):
            return self.data[cid]["owner"]
        return self.get_external_owner_id(channel)

    def is_owner(self, member, channel):
        cid = str(channel.id)
        if cid in self.data and self.data[cid]["owner"] is not None:
            return self.data[cid]["owner"] == member.id
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
    # تطبيق الصلاحيات: خاصة = بَانََة ولكن ممنوع الدخول
    # ═══════════════════════════════════════════════════════════════
    async def apply_permissions(self, channel: discord.VoiceChannel):
        room = self.get_room(channel)
        guild = channel.guild
        everyone = guild.default_role
        overwrites = dict(channel.overwrites)

        # 1) @everyone: خاصة = بَانََة للجميع ولكن ما يقدروش يدخلو
        everyone_ow = overwrites.get(everyone, discord.PermissionOverwrite())
        if room["private"]:
            everyone_ow.view_channel = True    # ✅ بَانََة لكاع الناس
            everyone_ow.connect = False         # ❌ ولكن ما يقدروش يدخلو
        else:
            everyone_ow.view_channel = None
            everyone_ow.connect = None
        overwrites[everyone] = everyone_ow

        # 2) المالك دايماً عندو حق الدخول
        if room["owner"]:
            owner_target = guild.get_member(room["owner"]) or discord.Object(id=room["owner"])
            owner_ow = overwrites.get(owner_target, discord.PermissionOverwrite())
            owner_ow.view_channel = True
            owner_ow.connect = True
            overwrites[owner_target] = owner_ow

        # 3) المسموحين — يقدرو يشوفو ويدخلو حتى ملي الروم خاصة
        for uid in room["allowed"]:
            target = guild.get_member(uid) or discord.Object(id=uid)
            ow = overwrites.get(target, discord.PermissionOverwrite())
            ow.view_channel = True
            ow.connect = True
            overwrites[target] = ow

        # 4) المحظورين — مخبيين وممنوعين فكل الحالات
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

        # ⏰ وقتاش تصاوبات الروم — كيتحدث أوتوماتيكياً من جهة ديسكورد
        created_ts = int(channel.created_at.timestamp())
        total_intrusions = sum(room.get("intrusions", {}).values())

        desc = (
            f"**الحالة:** {'🔒 خاصة (بَانََة للجميع، غير المسموحين يدخلو)' if room['private'] else '🔓 عامة (مفتوحة للجميع ماعدا المحظورين)'}\n"
            f"**المالك:** <@{room['owner']}>" if room["owner"] else "**الحالة:** —"
        )
        if room["private"]:
            desc += "\n🛡️ **الحماية مفعلة:** حتى Admin ما يقدر يدخل — البوت كيطردو أوتوماتيكياً"

        embed = discord.Embed(
            title=f"🎤 {channel.name}",
            description=desc,
            color=discord.Color.blue()
        )
        # ⏰ وقتاش تصاوبات — <t:...:R> كيعطيك "منذ 5 دقايق" وكيتحدث وحده
        embed.add_field(
            name="⏰ تصاوبات",
            value=f"<t:{created_ts}:R> (<t:{created_ts}:f>)",
            inline=False
        )
        embed.add_field(name="✅ مسموحين (فحالة الخصوصية)", value=allowed, inline=False)
        embed.add_field(name="🔐 محظورين (دايماً)", value=blocked, inline=False)
        embed.add_field(name="🔇 مكتومين", value=muted, inline=False)
        if total_intrusions > 0:
            embed.add_field(
                name="🛡️ محاولات دخول مرفوضة",
                value=f"{total_intrusions} محاولة تم صدها",
                inline=False
            )
        embed.set_footer(text="🎛️ استعمل الأزرار تحت باش تدير أي أمر — بلا ما تكتب حتى Slash Command")
        return embed

    # ═══════════════════════════════════════════════════════════════
    # 🛡️ الحماية ضد تجاوز Admin/Administrator
    # ═══════════════════════════════════════════════════════════════
    async def _handle_intrusion(self, member, channel, room):
        """كيتعامل مع أي واحد دخل لروم خاصة بلا ما يكون مسموح ليه
        (حتى لو كان Admin/Administrator)."""
        room.setdefault("intrusions", {})
        key = str(member.id)
        room["intrusions"][key] = room["intrusions"].get(key, 0) + 1
        count = room["intrusions"][key]
        self.save_data()

        # 🚫 طرد فوري من الروم (كيخدم حتى ضد Administrator)
        try:
            await member.move_to(None, reason="روم خاصة — ماشي مسموح ليه")
        except (discord.Forbidden, discord.HTTPException):
            pass

        if count < 3:
            # إنذار عادي
            warn_msg = (
                f"⚠️ **إنذار {count}/3**\n"
                f"الروم **{channel.name}** خاصة ونتا ماشي فلائحة المسموحين.\n"
                f"ما تحاولش تعاود تدخل.\n"
                f"فالمحاولة الثالثة غادي تتعاقب (kick من السيرفر ولا خبي الروم نهائياً)."
            )
            try:
                await member.send(warn_msg)
            except (discord.Forbidden, discord.HTTPException):
                try:
                    await channel.send(f"⚠️ {member.mention} هاد الروم خاصة! (إنذار {count}/3)")
                except Exception:
                    pass
        elif count == 3:
            # العقوبة بعد 3 محاولات
            await self._punish_intruder(member, channel, room, count)
        # count > 3: غير طرد صامت (تمت العقوبة بالفعل)

    async def _punish_intruder(self, member, channel, room, count):
        """العقوبة بعد 3 محاولات: kick من السيرفر، ولا خبي الروم + حظر نهائي."""
        guild = channel.guild
        punished = False

        # الخيار 1: kick من السيرفر
        try:
            await member.kick(reason=f"{count} محاولات دخول غير مصرح بها لروم خاصة {channel.name}")
            punished = True
            try:
                await channel.send(
                    f"🚫 **{member.display_name}** تدار ليه kick من السيرفر بعد {count} محاولات دخول لهاد الروم الخاصة."
                )
            except Exception:
                pass
        except (discord.Forbidden, discord.HTTPException):
            punished = False

        if not punished:
            # الخيار 2: خبي الروم نهائياً + حظر
            try:
                await channel.set_permissions(
                    member, view_channel=False, connect=False,
                    reason=f"{count} محاولات دخول غير مصرح بها"
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

            if member.id not in room["blocked"]:
                room["blocked"].append(member.id)
                if member.id in room["allowed"]:
                    room["allowed"].remove(member.id)
