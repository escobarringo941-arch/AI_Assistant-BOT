# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/prison.py — 🔒 نظام السجن الحقيقي ديال GGMW9    ║
═══════════════════════════════════════════════════════

المبدأ:
  • كاع العقوبات (kick / ban / mute) ولاو **سجن**. حتى واحد ما كيتطرد.
  • السجين كيتحيدو ليه كاع الرولات وكيتخزنو، وكيتعطى رول Prisoner.
  • رول Prisoner مخبّي من **كل** روم فالسيرفر (بحال Unverified) — حتى الرومز
    الجديدة اللي كيتصاوبو من بعد كيتلحقو أوتوماتيكيا.
  • السجين كيشوف غير الزنزانة ديالو + prison-code + warden-office.
  • عداد حي بـ <t:...:R> ديال Discord (كيتحدث بوحدو، بلا استنزاف الـAPI).
  • ملي تسالي المدة → كيترجعو ليه الرولات ديالو بالضبط كيف كانو.
  • التحكم الكامل = **Owner ديال السيرفر بوحدو**. الادمين والمود كتسقط
    القوة ديالهم كاملة داخل كاتيكوري السجن (بحال Temp Rooms).
  • الـ Warden (الشرطة) كيقدر غير على الأحكام الخفيفة، وما يقدرش يطلق سراح.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Iterable, Optional

import discord
from discord.ext import commands, tasks

from cogs.prison_core import (
    CELL_KEYS,
    CHANNEL_NAMES,
    COMPLAINT_MAX_PENDING,
    SOLITARY_DEFAULT_SECONDS,
    SOLITARY_MAX_ROOMS,
    SOLITARY_MAX_SECONDS,
    SOLITARY_PREFIX,
    VISIT_CHANNEL_PREFIX,
    VISIT_DEFAULT_SECONDS,
    VISIT_INVITE_TIMEOUT_SECONDS,
    WANTED_BOARD_CHANNEL_NAME,
    parse_duration,
    solitary_channel_name,
    visit_channel_name,
    PRISON_CATEGORY_NAME,
    PRISONER_ROLE_COLOR,
    PRISONER_ROLE_NAME,
    WARDEN_ALLOWED_CELLS,
    WARDEN_ALLOWED_SEVERITY,
    WARDEN_MAX_SECONDS,
    WARDEN_ROLE_COLOR,
    WARDEN_ROLE_NAME,
    PrisonStore,
    format_duration,
    now_ts,
    remaining_seconds,
)

# ═══════════════════════════════════════════════════════
# ║                    ثوابت داخلية                       ║
# ═══════════════════════════════════════════════════════

REASON_TAG = "GGMW9 Prison System"

# ═══════ التصعيد الأوتوماتيكي للزنازن (Auto-Escalation) ═══════
# إلا سبام السجين ولا كتب حوايج ممنوعة وهو دايما فزنزانتو، البوت كيديه
# مباشرة للزنزانة الأقسح اللي بعدها، بلا تدخل يدوي.
NEXT_CELL = {"holding": "block", "block": "max"}  # "max" هي السقف — ماكاينش أقسح منها
CELL_SPAM_WINDOW_SECONDS = 8      # نافذة الوقت باش نحسبو الرسائل المتتالية
CELL_SPAM_THRESHOLD = 5           # عدد الرسائل فالنافذة باش يتعتبر Spam
CELL_ESCALATION_EXTRA_SECONDS = {
    "holding": 6 * 3600,     # +6 سوايع ملي يتصعّد لـ Cell Block
    "block": 24 * 3600,      # +24 ساعة ملي يتصعّد لـ Maximum Security
    "max": 3 * 24 * 3600,    # مازال فـ Maximum وعاود كرر → +3 أيام بلا تصعيد فما فوق
}
CELL_FORBIDDEN_PATTERNS = (
    "discord.gg/", "discord.com/invite", "discordapp.com/invite",
    "http://", "https://", "www.",
    "@everyone", "@here",
)

# الصلاحيات اللي كتتحيد من السجين فكل روم برا السجن.
HIDE_OVERWRITE = discord.PermissionOverwrite(
    view_channel=False,
    read_messages=False,
    send_messages=False,
    connect=False,
    speak=False,
    add_reactions=False,
)

COLOR_JAIL = discord.Color.dark_red()
COLOR_FREE = discord.Color.green()
COLOR_INFO = discord.Color.blurple()


def _cell_display(key: str) -> str:
    return CHANNEL_NAMES.get(key, key)


async def _reply(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


def _is_visit_staff(cog, member: discord.Member) -> bool:
    """Admin / Mod / Warden / Owner — هوما لي عندهم صلاحية يستعملو بانل الزيارات."""
    if cog.is_server_owner(member, member.guild):
        return True
    if cog.is_warden(member):
        return True
    role_ids = {role.id for role in member.roles}
    if cog.admin_role_id and cog.admin_role_id in role_ids:
        return True
    if cog.moderator_role_id and cog.moderator_role_id in role_ids:
        return True
    return False


class PrisonerCardView(discord.ui.View):
    """
    زر واحد فبطاقة السجين: كيعطيه الوقت الباقي **دابا بالثانية**.
    persistent (timeout=None + custom_id) باش يخدم حتى بعد ريستارت البوت.
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="اشكي من سجين",
        emoji="📮",
        style=discord.ButtonStyle.danger,
        custom_id="ggmw9:prison:complain",
        row=0,
    )
    async def complain(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("PrisonSystem")
        if cog is None or interaction.guild is None:
            await interaction.response.send_message("❌ النظام ماشي متاح دابا.", ephemeral=True)
            return
        if not cog.store.is_inmate(interaction.guild.id, interaction.user.id):
            await interaction.response.send_message(
                "❌ غير السجناء لي كيقدرو يشكيو.", ephemeral=True
            )
            return

        left = cog.store.complaint_cooldown_left(interaction.guild.id, interaction.user.id)
        if left > 0:
            await interaction.response.send_message(
                f"⏳ صبر — تقدر تشكي من جديد بعد **{format_duration(left)}**.", ephemeral=True
            )
            return

        others = [
            uid
            for uid in cog.store.inmates(interaction.guild.id)
            if int(uid) != interaction.user.id
            and not cog.store.in_solitary(interaction.guild.id, int(uid))
        ]
        if not others:
            await interaction.response.send_message(
                "🕊️ ماكاين حتى سجين آخر تشكي منو.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            "📮 اختار السجين اللي بغيتي تشكي منو:",
            view=ComplaintTargetView(cog, interaction.guild, others),
            ephemeral=True,
        )

    @discord.ui.button(
        label="شحال بقا ليا؟",
        emoji="⏱️",
        style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:prison:mytime",
        row=0,
    )
    async def my_time(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("PrisonSystem")
        if cog is None or interaction.guild is None:
            await interaction.response.send_message("❌ النظام ماشي متاح دابا.", ephemeral=True)
            return

        record = cog.store.inmate(interaction.guild.id, interaction.user.id)
        if not record:
            await interaction.response.send_message(
                "🕊️ نتا ماشي فالسجن. هاد البطاقة ديال شي حد آخر.", ephemeral=True
            )
            return

        offense = cog.store.offense(interaction.guild.id, record.get("offense", "manual"))
        until = int(record.get("until", 0))
        left = remaining_seconds(record)
        bar, percent = cog._progress_bar(record)

        if until < 0:
            timing = "♾️ **حكم مؤبّد** — ماكاين حتى عداد."
        elif left <= 0:
            timing = "🔓 **سالات المدة!** غادي تخرج فأقل من 20 ثانية."
        else:
            timing = (
                f"⏳ باقي ليك: **{format_duration(left)}**\n"
                f"🕐 بالضبط: **<t:{until}:R>**\n"
                f"📤 الخروج: <t:{until}:F>"
            )

        embed = discord.Embed(
            title="⏱️ الوقت ديالك — مباشر",
            description=f"{timing}\n\n`{bar}` **{percent}%**",
            color=discord.Color.orange(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="📌 المخالفة", value=offense["label"], inline=True)
        embed.add_field(name="🗂️ Case", value=f"#{record.get('case','?')}", inline=True)
        embed.add_field(
            name="📝 السبب",
            value=str(record.get("reason") or offense["label"])[:1000],
            inline=False,
        )
        embed.set_footer(text="محسوب دابا فهاد اللحظة")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ComplaintTargetSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild, user_ids: list):
        options = []
        for uid in user_ids[:25]:
            member = guild.get_member(int(uid))
            record = cog.store.inmate(guild.id, int(uid)) or {}
            offense = cog.store.offense(guild.id, record.get("offense", "manual"))
            options.append(
                discord.SelectOption(
                    label=(member.display_name if member else f"ID {uid}")[:100],
                    value=str(uid),
                    description=offense["label"][:100],
                )
            )
        super().__init__(placeholder="اختار السجين…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ComplaintModal(int(self.values[0])))


class ComplaintTargetView(discord.ui.View):
    def __init__(self, cog, guild: discord.Guild, user_ids: list):
        super().__init__(timeout=180)
        self.add_item(ComplaintTargetSelect(cog, guild, user_ids))


class ComplaintModal(discord.ui.Modal, title="📮 شكاية من سجين"):
    def __init__(self, target_id: int):
        super().__init__()
        self.target_id = target_id
        self.reason = discord.ui.TextInput(
            label="أشنو وقع بالضبط؟",
            placeholder="كن واضح ومحدد — الشكايات الكاذبة كتاخد تنبيه.",
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=10,
            max_length=500,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("PrisonSystem")
        if cog is None:
            await interaction.response.send_message("❌ النظام ماشي متاح.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await cog.submit_complaint(
            interaction.user, self.target_id, str(self.reason.value).strip()
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result['error']}", ephemeral=True)
            return
        route = result["route"]
        await interaction.followup.send(
            f"✅ الشكاية **#{result['complaint']['id']}** توصلات.\n"
            + (
                "👮 غادي يشوفها الـ**Warden**."
                if route == "warden"
                else "👑 هاد السجين من الكبار — غادي يشوفها **الاونر** بوحدو."
            )
            + "\n\n⏳ غادي توصلك النتيجة فـDM.",
            ephemeral=True,
        )


class ComplaintReviewView(discord.ui.View):
    """
    أزرار القرار. persistent: الشكاية كتتلقا عبر message_id،
    والاختصاص كيتفحص فكل ضغطة (Warden للخفاف، Owner للكبار).
    """

    def __init__(self):
        super().__init__(timeout=None)

    async def _resolve(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("PrisonSystem")
        if cog is None or interaction.guild is None:
            return None, None, None
        found = cog.store.complaint_by_message(interaction.guild.id, interaction.message.id)
        if found is None:
            return cog, None, None
        return cog, found[0], found[1]

    @staticmethod
    def _may_handle(interaction: discord.Interaction, cog, complaint: dict) -> bool:
        is_owner = interaction.user.id == interaction.guild.owner_id
        if is_owner:
            return True
        if complaint.get("route") == "warden" and isinstance(interaction.user, discord.Member):
            return cog.is_warden(interaction.user)
        return False

    @discord.ui.button(
        label="قبول → انفرادي",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="ggmw9:prison:complaint:approve",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog, cid, complaint = await self._resolve(interaction)
        if complaint is None:
            await interaction.response.send_message("❌ الشكاية ما بقاتش موجودة.", ephemeral=True)
            return
        if complaint.get("status") != "pending":
            await interaction.response.send_message(
                f"⚠️ الشكاية تحسمات من قبل ({complaint.get('status')}).", ephemeral=True
            )
            return
        if not self._may_handle(interaction, cog, complaint):
            await interaction.response.send_message(
                "❌ هاد الشكاية من اختصاص **الاونر بوحدو** — السجين من الكبار.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(SolitaryDurationModal(cid))

    @discord.ui.button(
        label="رفض",
        emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="ggmw9:prison:complaint:reject",
    )
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog, cid, complaint = await self._resolve(interaction)
        if complaint is None:
            await interaction.response.send_message("❌ الشكاية ما بقاتش موجودة.", ephemeral=True)
            return
        if complaint.get("status") != "pending":
            await interaction.response.send_message("⚠️ تحسمات من قبل.", ephemeral=True)
            return
        if not self._may_handle(interaction, cog, complaint):
            await interaction.response.send_message(
                "❌ هاد الشكاية من اختصاص **الاونر بوحدو**.", ephemeral=True
            )
            return

        await interaction.response.defer()
        cog.store.resolve_complaint(
            interaction.guild.id, cid, status="rejected", handler_id=interaction.user.id
        )
        author = interaction.guild.get_member(int(complaint["author"]))
        if author:
            await cog._dm(
                author,
                discord.Embed(
                    title="❌ الشكاية ديالك ترفضات",
                    description=(
                        f"الشكاية **#{cid}** ما تقبلاتش.\n\n"
                        "⚠️ تنبيه: الشكايات الكاذبة ولا المتكررة بلا سبب "
                        "يقدرو يوصلوك نتا للانفرادي."
                    ),
                    color=discord.Color.red(),
                ),
            )
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.dark_grey()
        embed.title = f"❌ شكاية #{cid} — مرفوضة"
        embed.add_field(
            name="🧾 القرار", value=f"رفضها {interaction.user.mention}", inline=False
        )
        await interaction.message.edit(embed=embed, view=None)


class SolitaryDurationModal(discord.ui.Modal, title="🔗 مدة الحبس الانفرادي"):
    def __init__(self, complaint_id: str):
        super().__init__()
        self.complaint_id = complaint_id
        self.duration = discord.ui.TextInput(
            label=f"المدة (أقصى {SOLITARY_MAX_SECONDS // 3600} ساعة)",
            placeholder="مثال: 2h — خليها خاوية للمدة الافتراضية",
            required=False,
            max_length=16,
        )
        self.note = discord.ui.TextInput(
            label="ملاحظة (اختيارية)",
            placeholder="كتبان فسبب العزل",
            required=False,
            max_length=200,
        )
        self.add_item(self.duration)
        self.add_item(self.note)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("PrisonSystem")
        complaint = cog.store.complaints(interaction.guild.id).get(self.complaint_id)
        if complaint is None or complaint.get("status") != "pending":
            await interaction.response.send_message("⚠️ الشكاية تحسمات.", ephemeral=True)
            return

        seconds = SOLITARY_DEFAULT_SECONDS
        raw = str(self.duration.value or "").strip()
        if raw:
            parsed = parse_duration(raw)
            if parsed is None or parsed < 0:
                await interaction.response.send_message(
                    "❌ المدة ماشي صالحة. مثال: `2h` ولا `45m`.", ephemeral=True
                )
                return
            seconds = parsed
        if seconds > SOLITARY_MAX_SECONDS:
            await interaction.response.send_message(
                f"❌ أقصى مدة عزل هي **{format_duration(SOLITARY_MAX_SECONDS)}**.",
                ephemeral=True,
            )
            return

        target = interaction.guild.get_member(int(complaint["target"]))
        if target is None:
            await interaction.response.send_message("❌ المشكي عليه خرج من السيرفر.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        note = str(self.note.value or "").strip()
        reason = f"شكاية #{self.complaint_id}: {complaint['reason']}" + (
            f" • {note}" if note else ""
        )
        result = await cog.send_to_solitary(
            target,
            seconds=seconds,
            reason=reason,
            actor=interaction.user,
            complaint_id=int(self.complaint_id),
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result['error']}", ephemeral=True)
            return

        cog.store.resolve_complaint(
            interaction.guild.id, self.complaint_id, status="approved", handler_id=interaction.user.id
        )
        author = interaction.guild.get_member(int(complaint["author"]))
        if author:
            await cog._dm(
                author,
                discord.Embed(
                    title="✅ الشكاية ديالك تقبلات",
                    description=(
                        f"الشكاية **#{self.complaint_id}** تقبلات.\n"
                        f"المشكي عليه تنقل للحبس الانفرادي لمدة "
                        f"**{format_duration(seconds)}**."
                    ),
                    color=discord.Color.green(),
                ),
            )

        try:
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.dark_purple()
            embed.title = f"✅ شكاية #{self.complaint_id} — مقبولة"
            embed.add_field(
                name="🧾 القرار",
                value=(
                    f"قبلها {interaction.user.mention}\n"
                    f"🔗 عزل **{format_duration(seconds)}** فـ {result['channel'].mention}"
                ),
                inline=False,
            )
            await interaction.message.edit(embed=embed, view=None)
        except (AttributeError, IndexError, discord.HTTPException):
            pass

        await interaction.followup.send(
            f"✅ {target.mention} تنقل للانفرادي — {result['channel'].mention}", ephemeral=True
        )


# ═══════════════════════════════════════════════════════
# ║          الزيارات — الواجهة (UI) ديال الغرفة           ║
# ═══════════════════════════════════════════════════════

class VisitStaffView(discord.ui.View):
    """أي View كيرث من هادي = Admin/Mod/Warden/Owner بوحدهم."""

    def __init__(self, timeout: float = 180):
        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cog = interaction.client.get_cog("PrisonSystem")
        if cog is None or not isinstance(interaction.user, discord.Member):
            await _reply(interaction, "❌ النظام ماشي متاح دابا.")
            return False
        if not _is_visit_staff(cog, interaction.user):
            await _reply(interaction, "❌ هاد البانل خاصة بالإدارة (Admin / Mod / Warden / Owner).")
            return False
        return True


class VisitVisitorSelect(discord.ui.UserSelect):
    def __init__(self, prisoner_id: int):
        super().__init__(placeholder="اختار الشخص لي بغيتي تدعوه…", min_values=1, max_values=1)
        self.prisoner_id = prisoner_id

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("PrisonSystem")
        if cog is None:
            await _reply(interaction, "❌ النظام ماشي متاح دابا.")
            return
        visitor = self.values[0]
        if visitor.bot:
            await _reply(interaction, "❌ ما يمكنش تدعو بوت.")
            return
        if visitor.id == self.prisoner_id:
            await _reply(interaction, "❌ السجين ما يقدرش يزور راسو.")
            return
        if cog.store.is_inmate(interaction.guild.id, visitor.id):
            await _reply(interaction, "❌ الزائر ماخصوش يكون سجين هو الآخر.")
            return
        if cog.store.active_visit_for_visitor(interaction.guild.id, visitor.id):
            await _reply(interaction, "❌ هاد الشخص عندو زيارة جارية ولا معلّقة أصلاً.")
            return

        result = await cog.request_visit(
            interaction.guild,
            prisoner_id=self.prisoner_id,
            visitor_id=visitor.id,
            actor=interaction.user,
        )
        if not result.get("ok"):
            await _reply(interaction, f"❌ {result.get('error')}")
            return
        note = "" if result.get("dm") else "\n⚠️ الـDM ديالو مسدودة — الدعوة تبعثات فروم الزيارات."
        await _reply(
            interaction,
            f"✅ تبعثات الدعوة لـ {visitor.mention} باش يزور <@{self.prisoner_id}>."
            f"{note}\n⏳ عندو {format_duration(VISIT_INVITE_TIMEOUT_SECONDS)} باش يجاوب.",
        )


class VisitVisitorPickView(VisitStaffView):
    def __init__(self, prisoner_id: int):
        super().__init__(timeout=180)
        self.add_item(VisitVisitorSelect(prisoner_id))


class VisitPrisonerSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild):
        options: list[discord.SelectOption] = []
        for uid, record in cog.store.inmates(guild.id).items():
            uid_int = int(uid)
            if cog.store.in_solitary(guild.id, uid_int):
                continue
            if cog.store.active_visit_for_inmate(guild.id, uid_int):
                continue
            member = guild.get_member(uid_int)
            offense = cog.store.offense(guild.id, record.get("offense", "manual"))
            options.append(
                discord.SelectOption(
                    label=(member.display_name if member else f"ID {uid}")[:100],
                    value=str(uid_int),
                    description=offense["label"][:100],
                )
            )
            if len(options) >= 25:
                break
        super().__init__(
            placeholder="اختار السجين اللي بغا يتزار…" if options else "ماكاين حتى سجين متاح دابا للزيارة",
            options=options or [discord.SelectOption(label="—", value="0")],
            min_values=1,
            max_values=1,
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction):
        prisoner_id = int(self.values[0])
        member = interaction.guild.get_member(prisoner_id)
        if member is None:
            await _reply(interaction, "❌ هاد السجين ماشي فالسيرفر دابا.")
            return
        await interaction.response.send_message(
            f"👥 بغيتي تدعو شكون يزور {member.mention}؟ اختارو تحت:",
            view=VisitVisitorPickView(prisoner_id),
            ephemeral=True,
        )


class VisitPanelPrisonerView(VisitStaffView):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__(timeout=180)
        self.add_item(VisitPrisonerSelect(cog, guild))


# ─── الزيارة الذاتية — مفتوحة لكل الأعضاء (ماشي غير الإدارة) ───

class SelfVisitPrisonerSelect(discord.ui.Select):
    """أي عضو عادي كيختار صاحبو المسجون باش يزورو — بلا ما يحتاج صلاحية إدارة."""

    def __init__(self, cog, guild: discord.Guild, visitor_id: int):
        options: list[discord.SelectOption] = []
        for uid, record in cog.store.inmates(guild.id).items():
            uid_int = int(uid)
            if uid_int == visitor_id:
                continue
            if cog.store.in_solitary(guild.id, uid_int):
                continue
            if cog.store.active_visit_for_inmate(guild.id, uid_int):
                continue
            member = guild.get_member(uid_int)
            offense = cog.store.offense(guild.id, record.get("offense", "manual"))
            options.append(
                discord.SelectOption(
                    label=(member.display_name if member else f"ID {uid}")[:100],
                    value=str(uid_int),
                    description=offense["label"][:100],
                )
            )
            if len(options) >= 25:
                break
        super().__init__(
            placeholder="اختار صاحبك المسجون اللي بغيتي تزور…" if options else "ماكاين حتى سجين متاح دابا للزيارة",
            options=options or [discord.SelectOption(label="—", value="0")],
            min_values=1,
            max_values=1,
            disabled=not options,
        )
        self.visitor_id = visitor_id

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("PrisonSystem")
        if cog is None:
            await _reply(interaction, "❌ النظام ماشي متاح دابا.")
            return
        prisoner_id = int(self.values[0])
        member = interaction.guild.get_member(prisoner_id)
        if member is None:
            await _reply(interaction, "❌ هاد السجين ماشي فالسيرفر دابا.")
            return
        await interaction.response.defer(ephemeral=True)
        result = await cog.request_self_visit(
            interaction.guild,
            prisoner_id=prisoner_id,
            visitor_id=self.visitor_id,
            actor=interaction.user,
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
            return
        note = "" if result.get("dm") else "\n⚠️ الـDM ديالو مسدودة — الدعوة تبعثات فروم الزيارات."
        await interaction.followup.send(
            f"✅ تبعثات الدعوة لـ {member.mention} باش يوافق على الزيارة."
            f"{note}\n⏳ عندو {format_duration(VISIT_INVITE_TIMEOUT_SECONDS)} باش يجاوب.",
            ephemeral=True,
        )


class SelfVisitPrisonerView(discord.ui.View):
    def __init__(self, cog, guild: discord.Guild, visitor_id: int):
        super().__init__(timeout=180)
        self.add_item(SelfVisitPrisonerSelect(cog, guild, visitor_id))


class VisitEndSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild):
        options: list[discord.SelectOption] = []
        for vid, record in cog.store.visits(guild.id).items():
            if record.get("status") != "active":
                continue
            prisoner = guild.get_member(int(record.get("prisoner_id", 0)))
            visitor = guild.get_member(int(record.get("visitor_id", 0)))
            label = f"{(prisoner.display_name if prisoner else '؟')} × {(visitor.display_name if visitor else '؟')}"
            left = format_duration(remaining_seconds(record))
            options.append(
                discord.SelectOption(label=label[:100], value=vid, description=f"باقي {left}"[:100])
            )
            if len(options) >= 25:
                break
        super().__init__(
            placeholder="اختار الزيارة اللي بغيتي تسدها…" if options else "ماكاين حتى زيارة جارية",
            options=options or [discord.SelectOption(label="—", value="0")],
            min_values=1,
            max_values=1,
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("PrisonSystem")
        await interaction.response.defer(ephemeral=True)
        result = await cog.end_visit(
            interaction.guild, self.values[0], reason="سدها الإدارة يدويا", actor=interaction.user
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
        else:
            await interaction.followup.send("✅ تسدات الزيارة ورجع السجين لزنزانتو.", ephemeral=True)


class VisitEndView(VisitStaffView):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__(timeout=180)
        self.add_item(VisitEndSelect(cog, guild))


class VisitInviteView(discord.ui.View):
    """
    دعوة الزيارة — كتبعث DM (ولا روم الزيارات إلا DM مسدودة) للزائر بوحدو.
    """

    def __init__(self, cog, visit_id: str, visitor_id: int, guild_id: int):
        super().__init__(timeout=VISIT_INVITE_TIMEOUT_SECONDS)
        self.cog = cog
        self.visit_id = visit_id
        self.visitor_id = visitor_id
        self.guild_id = guild_id
        self.invite_message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.visitor_id:
            await _reply(interaction, "❌ هاد الدعوة ماشي ليك.")
            return False
        return True

    def _lock(self) -> None:
        for child in self.children:
            child.disabled = True

    async def _sync_message(self, interaction: Optional[discord.Interaction] = None) -> None:
        target = interaction.message if interaction is not None else self.invite_message
        if target is None:
            return
        try:
            await target.edit(view=self)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            pass

    @discord.ui.button(
        label="قبول الزيارة", emoji="✅", style=discord.ButtonStyle.success, custom_id="ggmw9:visit:accept"
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.cog.bot.get_guild(self.guild_id)
        if guild is None:
            await _reply(interaction, "❌ السيرفر ماشي متاح دابا.")
            return
        await interaction.response.defer(ephemeral=True)
        result = await self.cog.accept_visit(guild, self.visit_id, visitor_id=self.visitor_id)
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
        else:
            channel = result["channel"]
            await interaction.followup.send(
                f"✅ قبلتي الزيارة! دخل هنا: {channel.mention}", ephemeral=True
            )
        self._lock()
        await self._sync_message(interaction)
        self.stop()

    @discord.ui.button(
        label="رفض", emoji="❌", style=discord.ButtonStyle.secondary, custom_id="ggmw9:visit:decline"
    )
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.cog.bot.get_guild(self.guild_id)
        if guild is not None:
            await self.cog.decline_visit(guild, self.visit_id, reason="رفض الزائر الدعوة")
        await _reply(interaction, "🚫 رفضتي الزيارة.")
        self._lock()
        await self._sync_message(interaction)
        self.stop()

    async def on_timeout(self) -> None:
        self._lock()
        await self._sync_message()
        guild = self.cog.bot.get_guild(self.guild_id)
        if guild is not None:
            await self.cog.decline_visit(guild, self.visit_id, reason="⏳ ما تجاوبش فالوقت المحدد")


class PrisonerVisitInviteView(discord.ui.View):
    """
    دعوة زيارة مبعوثة **للسجين** (ماشي للزائر) — كتخدم ملي عضو عادي (ماشي إدارة)
    كيطلب يزور صاحبو المسجون: خاص موافقة السجين نفسو قبل ما تحل الروم.
    """

    def __init__(self, cog, visit_id: str, prisoner_id: int, guild_id: int):
        super().__init__(timeout=VISIT_INVITE_TIMEOUT_SECONDS)
        self.cog = cog
        self.visit_id = visit_id
        self.prisoner_id = prisoner_id
        self.guild_id = guild_id
        self.invite_message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.prisoner_id:
            await _reply(interaction, "❌ هاد الدعوة ماشي ليك.")
            return False
        return True

    def _lock(self) -> None:
        for child in self.children:
            child.disabled = True

    async def _sync_message(self, interaction: Optional[discord.Interaction] = None) -> None:
        target = interaction.message if interaction is not None else self.invite_message
        if target is None:
            return
        try:
            await target.edit(view=self)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            pass

    @discord.ui.button(
        label="قبول الزيارة",
        emoji="✅",
        style=discord.ButtonStyle.success,
        custom_id="ggmw9:visit:prisoner_accept",
    )
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.cog.bot.get_guild(self.guild_id)
        if guild is None:
            await _reply(interaction, "❌ السيرفر ماشي متاح دابا.")
            return
        await interaction.response.defer(ephemeral=True)
        result = await self.cog.accept_visit_as_prisoner(
            guild, self.visit_id, prisoner_id=self.prisoner_id
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
        else:
            channel = result["channel"]
            await interaction.followup.send(
                f"✅ قبلتي الزيارة! دخل هنا: {channel.mention}", ephemeral=True
            )
        self._lock()
        await self._sync_message(interaction)
        self.stop()

    @discord.ui.button(
        label="رفض",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:visit:prisoner_decline",
    )
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.cog.bot.get_guild(self.guild_id)
        if guild is not None:
            await self.cog.decline_visit(guild, self.visit_id, reason="رفض السجين الدعوة")
        await _reply(interaction, "🚫 رفضتي الزيارة.")
        self._lock()
        await self._sync_message(interaction)
        self.stop()

    async def on_timeout(self) -> None:
        self._lock()
        await self._sync_message()
        guild = self.cog.bot.get_guild(self.guild_id)
        if guild is not None:
            await self.cog.decline_visit(
                guild, self.visit_id, reason="⏳ السجين ما تجاوبش فالوقت المحدد"
            )


class VisitPanelView(discord.ui.View):
    """
    البانل الثابتة فغرفة الزيارات.
    "طلب زيارة" مفتوحة لكل الأعضاء (أي واحد يقدر يزور صاحبو المسجون مباشرة).
    "الزيارات الجارية" و"سد زيارة" خاصين بالإدارة (Admin / Mod / Warden / Owner) بوحدها.
    persistent (timeout=None) باش تخدم حتى بعد ريستارت البوت.
    """

    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cog = interaction.client.get_cog("PrisonSystem")
        if cog is None or not isinstance(interaction.user, discord.Member):
            await _reply(interaction, "❌ النظام ماشي متاح دابا.")
            return False
        custom_id = (interaction.data or {}).get("custom_id", "")
        if custom_id in ("ggmw9:visit:list", "ggmw9:visit:end") and not _is_visit_staff(
            cog, interaction.user
        ):
            await _reply(interaction, "❌ هاد الزر خاص بالإدارة (Admin / Mod / Warden / Owner).")
            return False
        return True

    @discord.ui.button(
        label="طلب زيارة",
        emoji="🔔",
        style=discord.ButtonStyle.success,
        custom_id="ggmw9:visit:request",
    )
    async def request_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("PrisonSystem")
        if not cog.store.inmates(interaction.guild.id):
            await _reply(interaction, "🕊️ ماكاين حتى سجين دابا.")
            return

        # الإدارة: كتقدر تنظم زيارة بين أي سجين وأي زائر.
        if _is_visit_staff(cog, interaction.user):
            await interaction.response.send_message(
                "🔒 اختار السجين اللي بغيتي تنظم ليه زيارة:",
                view=VisitPanelPrisonerView(cog, interaction.guild),
                ephemeral=True,
            )
            return

        # عضو عادي: كيزور مباشرة صاحبو المسجون (بلا حاجة لصلاحية إدارة).
        if cog.store.is_inmate(interaction.guild.id, interaction.user.id):
            await _reply(interaction, "❌ ما يمكنش للسجين يطلب زيارة — خاصك تستنى الزوار.")
            return
        if cog.store.active_visit_for_visitor(interaction.guild.id, interaction.user.id):
            await _reply(interaction, "❌ عندك زيارة جارية ولا معلّقة أصلاً.")
            return
        await interaction.response.send_message(
            "🔒 اختار صاحبك المسجون اللي بغيتي تزور:",
            view=SelfVisitPrisonerView(cog, interaction.guild, interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(
        label="الزيارات الجارية",
        emoji="📋",
        style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:visit:list",
    )
    async def list_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("PrisonSystem")
        await interaction.response.send_message(
            embed=cog.visits_embed(interaction.guild), ephemeral=True
        )

    @discord.ui.button(
        label="سد زيارة",
        emoji="📴",
        style=discord.ButtonStyle.danger,
        custom_id="ggmw9:visit:end",
    )
    async def end_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("PrisonSystem")
        active = [r for r in cog.store.visits(interaction.guild.id).values() if r.get("status") == "active"]
        if not active:
            await _reply(interaction, "🕊️ ماكاين حتى زيارة جارية دابا.")
            return
        await interaction.response.send_message(
            "📴 اختار الزيارة اللي بغيتي تسدها:",
            view=VisitEndView(cog, interaction.guild),
            ephemeral=True,
        )


class PrisonSystem(commands.Cog):
    """النواة التنفيذية ديال السجن."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = PrisonStore()

        bridge = getattr(bot, "gg", {}) or {}
        self.admin_role_id = int(bridge.get("ADMIN_ROLE_ID") or 0)
        self.moderator_role_id = int(bridge.get("MODERATOR_ROLE_ID") or 0)
        self.mod_logs_channel_id = int(bridge.get("MOD_LOGS_CHANNEL_ID") or 0)
        self.unverified_role_id = int(bridge.get("UNVERIFIED_ROLE_ID") or 0)

        self._guild_locks: dict[int, asyncio.Lock] = {}
        self._member_locks: dict[int, asyncio.Lock] = {}
        # باش on_member_update ما يتصارعش مع العمليات ديالنا
        self._suppress_role_guard: set[int] = set()
        self._ready_done = False
        # تتبّع الرسائل المتتالية ديال كل سجين فزنزانتو — باش نكشفو Spam
        # ونصعّدو العقوبة أوتوماتيكيا. المفتاح: (guild_id, user_id).
        self._cell_spam_tracker: dict[tuple[int, int], list[int]] = {}

    # ═══════════════════════════════════════════════════
    # ║                  0. أدوات مساعدة                  ║
    # ═══════════════════════════════════════════════════

    def _lock(self, guild_id: int) -> asyncio.Lock:
        lock = self._guild_locks.get(guild_id)
        if lock is None:
            lock = asyncio.Lock()
            self._guild_locks[guild_id] = lock
        return lock

    def _member_lock(self, member_id: int) -> asyncio.Lock:
        lock = self._member_locks.get(member_id)
        if lock is None:
            lock = asyncio.Lock()
            self._member_locks[member_id] = lock
        return lock

    @staticmethod
    def is_server_owner(user: Optional[discord.abc.User], guild: Optional[discord.Guild]) -> bool:
        """كنعتمدو على Discord الحي، ماشي على ID مكتوب فالكود."""
        return bool(user and guild and user.id == guild.owner_id)

    def prisoner_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        return guild.get_role(int(self.store.guild(guild.id)["roles"].get("prisoner") or 0))

    def warden_role(self, guild: discord.Guild) -> Optional[discord.Role]:
        return guild.get_role(int(self.store.guild(guild.id)["roles"].get("warden") or 0))

    def prison_category(self, guild: discord.Guild) -> Optional[discord.CategoryChannel]:
        channel = guild.get_channel(int(self.store.guild(guild.id).get("category_id") or 0))
        return channel if isinstance(channel, discord.CategoryChannel) else None

    def prison_channel(self, guild: discord.Guild, key: str):
        return guild.get_channel(int(self.store.guild(guild.id)["channels"].get(key) or 0))

    def cell_voice_channel(self, guild: discord.Guild, key: str):
        return guild.get_channel(int(self.store.voice_channel_id(guild.id, key)))

    def visit_channel(self, guild: discord.Guild):
        return self.prison_channel(guild, "visits")

    def prison_channel_ids(self, guild: discord.Guild) -> set[int]:
        record = self.store.guild(guild.id)
        ids = {int(record.get("category_id") or 0)}
        ids.update(int(cid or 0) for cid in record["channels"].values())
        ids.update(int(cid or 0) for cid in record.get("voice_channels", {}).values())
        ids.update(
            int(s.get("channel_id") or 0) for s in record.get("solitary", {}).values()
        )
        ids.update(
            int(v.get("channel_id") or 0) for v in record.get("visits", {}).values()
        )
        ids.add(int(record.get("wanted_channel_id") or 0))
        ids.discard(0)
        return ids

    def is_prison_area(self, channel: discord.abc.GuildChannel) -> bool:
        """السجن = الكاتيكوري + رومزو الثابتة + رومز الانفرادي."""
        if channel.id in self.prison_channel_ids(channel.guild):
            return True
        record = self.store.guild(channel.guild.id)
        category_id = int(record.get("category_id") or 0)
        parent = getattr(channel, "category_id", None)
        if category_id and parent == category_id:
            return True
        # رومز الانفرادي (حتى إلا تحركو من الكاتيكوري)
        for solitary in record.get("solitary", {}).values():
            if int(solitary.get("channel_id") or 0) == channel.id:
                return True
        # رومز الزيارات المؤقتة (حتى إلا تحركو من الكاتيكوري)
        for visit in record.get("visits", {}).values():
            if int(visit.get("channel_id") or 0) == channel.id:
                return True
        name = str(getattr(channel, "name", ""))
        return name.startswith(SOLITARY_PREFIX) or name.startswith(VISIT_CHANNEL_PREFIX)

    def is_warden(self, member: discord.Member) -> bool:
        role = self.warden_role(member.guild)
        return bool(role and role in member.roles)

    async def _log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        """
        🕵️ Owner stealth: السجل كيمشي **غير** لـ prison-log،
        وهاد الروم مخبيّة على الجميع — حتى الادمين والمود والـWarden.
        **ما كيمشي حتى شي حاجة لـ Mod-Logs.** حتى واحد ما كيشوف أش كيدير الاونر.
        """
        prison_log = self.prison_channel(guild, "log")
        if prison_log is None:
            return
        try:
            await prison_log.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    @staticmethod
    async def _dm(member: discord.Member, embed: discord.Embed) -> bool:
        try:
            await member.send(embed=embed)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False

    # ═══════════════════════════════════════════════════
    # ║          1. بناء البنية (رولات + رومز)            ║
    # ═══════════════════════════════════════════════════

    async def ensure_roles(self, guild: discord.Guild) -> tuple[Optional[discord.Role], Optional[discord.Role]]:
        """كتصاوب/كتلقا رول Prisoner و Warden. الجوج بلا حتى صلاحية عامة."""
        record = self.store.guild(guild.id)
        changed = False

        prisoner = guild.get_role(int(record["roles"].get("prisoner") or 0))
        if prisoner is None:
            prisoner = discord.utils.get(guild.roles, name=PRISONER_ROLE_NAME)
        if prisoner is None:
            try:
                prisoner = await guild.create_role(
                    name=PRISONER_ROLE_NAME,
                    colour=discord.Colour(PRISONER_ROLE_COLOR),
                    permissions=discord.Permissions.none(),
                    hoist=True,
                    mentionable=False,
                    reason=f"{REASON_TAG}: create prisoner role",
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[PRISON] ❌ ما قدرتش نصاوب رول Prisoner: {exc}")
                prisoner = None
        if prisoner and int(record["roles"].get("prisoner") or 0) != prisoner.id:
            record["roles"]["prisoner"] = prisoner.id
            changed = True

        warden = guild.get_role(int(record["roles"].get("warden") or 0))
        if warden is None:
            warden = discord.utils.get(guild.roles, name=WARDEN_ROLE_NAME)
        if warden is None:
            try:
                warden = await guild.create_role(
                    name=WARDEN_ROLE_NAME,
                    colour=discord.Colour(WARDEN_ROLE_COLOR),
                    permissions=discord.Permissions.none(),
                    hoist=False,
                    mentionable=False,
                    reason=f"{REASON_TAG}: create warden role",
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[PRISON] ❌ ما قدرتش نصاوب رول Warden: {exc}")
                warden = None
        if warden and int(record["roles"].get("warden") or 0) != warden.id:
            record["roles"]["warden"] = warden.id
            changed = True

        # رول Prisoner خاصو يكون تحت البوت باش يقدر يعطيه/يحيدو.
        if prisoner and guild.me and guild.me.top_role.position > 1:
            try:
                target = max(1, min(prisoner.position, guild.me.top_role.position - 1))
                if prisoner.position != target and prisoner.position >= guild.me.top_role.position:
                    await prisoner.edit(position=target, reason=f"{REASON_TAG}: keep role manageable")
            except (discord.Forbidden, discord.HTTPException):
                pass

        if changed:
            self.store.save()
        return prisoner, warden

    def _category_overwrites(self, guild: discord.Guild) -> dict:
        """
        الكاتيكوري: مخبيّة على الكل.
        ⚠️ الادمين والمود كيتحرمو صراحة — حتى هوما ما عندهم حتى سلطة فالسجن.
        """
        prisoner = self.prisoner_role(guild)
        warden = self.warden_role(guild)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }

        # البوت خاصو يبقا قادر يخدم
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                send_messages=True,
                manage_messages=True,
                manage_channels=True,
                manage_permissions=True,
                embed_links=True,
                read_message_history=True,
            )

        # الادمين والمود: يشوفو كاع السجن (view-only) ولكن حرفيا ميقدروش يديرو
        # تا شي حاجة فيه — لا يكتبو، لا يدخلو للفويس، لا يديرو تا صلاحية إدارية.
        # الاستثناء الوحيد ديالهم هو غرفة الزيارات (_visit_voice_overwrites).
        # التحكم الفعلي (سجن/فك/تعديل) محسوب بالرول ديال Warden فمنطق البوت،
        # ماشي بالـDiscord permissions.
        for role_id in (self.admin_role_id, self.moderator_role_id):
            role = guild.get_role(role_id) if role_id else None
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=False,
                    add_reactions=False,
                    create_public_threads=False,
                    create_private_threads=False,
                    manage_messages=False,
                    manage_channels=False,
                    manage_permissions=False,
                    manage_threads=False,
                    manage_webhooks=False,
                    connect=False,
                    speak=False,
                    stream=False,
                    mute_members=False,
                    deafen_members=False,
                    move_members=False,
                )

        if warden:
            overwrites[warden] = discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=True,
                manage_messages=False,
                manage_channels=False,
                manage_permissions=False,
            )

        if prisoner:
            # على مستوى الكاتيكوري: لا. الوصول كيتعطى روم بروم.
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False)

        return overwrites

    def _channel_overwrites(self, guild: discord.Guild, key: str) -> dict:
        overwrites = dict(self._category_overwrites(guild))
        prisoner = self.prisoner_role(guild)
        if not prisoner:
            return overwrites

        if key == "code":
            overwrites[prisoner] = discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=False,
                add_reactions=False,
                create_public_threads=False,
                create_private_threads=False,
            )
        elif key == "warden":
            overwrites[prisoner] = discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=True,
                attach_files=False,
                embed_links=False,
                add_reactions=False,
                create_public_threads=False,
                create_private_threads=False,
            )
        elif key == "visits":
            # 🌍 روم الزيارات مفتوحة للعموم: أي عضو (ماشي غير الإدارة) يقدر يشوفها
            # ويستعمل البانل باش يزور صاحبو المسجون. التحكم الفعلي محسوب فمنطق
            # البوت (VisitPanelView) — هنا غير كنسمحو بالمشاهدة، بلا الكتابة الحرة.
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=False,
                add_reactions=False,
                create_public_threads=False,
                create_private_threads=False,
            )
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False)
        elif key == "log":
            # 🕵️ prison-log = Owner بوحدو. حتى Warden/Admin/Mod ما كيشوفوش أش كيدير الاونر.
            # (الادمين والمود عندهم دابا view-only على باقي السجن، ولكن هاد الروم
            #  بالذات محمية بشكل صريح باش يبقى الـstealth log حقيقي.)
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False)
            warden_role = self.warden_role(guild)
            if warden_role:
                overwrites[warden_role] = discord.PermissionOverwrite(
                    view_channel=False,
                    read_messages=False,
                    read_message_history=False,
                    send_messages=False,
                )
            for role_id in (self.admin_role_id, self.moderator_role_id):
                role = guild.get_role(role_id) if role_id else None
                if role:
                    overwrites[role] = discord.PermissionOverwrite(
                        view_channel=False,
                        read_messages=False,
                        read_message_history=False,
                        send_messages=False,
                    )
        else:
            # الزنازن: الوصول كيتعطى **للعضو بذاتو** ماشي للرول،
            # باش السجين يشوف غير الزنزانة ديالو.
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False)
        return overwrites

    def _cell_voice_overwrites(self, guild: discord.Guild, key: str) -> dict:
        """
        صلاحيات فويس شانيل الزنزانة (نفس سمية الروم النصية):
          • الادمين/المود: يشوفو (view_channel) ولكن ميقدروش يدخلو (connect=False).
          • الـWarden: دخول وتكلم كامل — بحال الاونر.
          • السجين: بلا صلاحية على مستوى الرول؛ الوصول الفردي فـ _grant_cell_access.
        """
        overwrites = dict(self._category_overwrites(guild))
        warden = self.warden_role(guild)
        if warden:
            overwrites[warden] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                stream=True,
                use_voice_activation=True,
            )
        prisoner = self.prisoner_role(guild)
        if prisoner:
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False, connect=False)
        return overwrites

    def _visit_voice_overwrites(
        self, guild: discord.Guild, prisoner: discord.Member, visitor: discord.Member
    ) -> dict:
        """
        فويس شانيل الزيارة المؤقتة: الاستثناء الوحيد اللي الادمين/المود يقدرو
        يدخلو ليه (بحال Warden/Owner) — ولكن غير هو، ماشي باقي السجن.
        """
        overwrites = dict(self._category_overwrites(guild))
        for role_id in (self.admin_role_id, self.moderator_role_id):
            role = guild.get_role(role_id) if role_id else None
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, connect=True, speak=True, stream=True,
                )
        warden = self.warden_role(guild)
        if warden:
            overwrites[warden] = discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True, stream=True,
            )
        prisoner_role = self.prisoner_role(guild)
        if prisoner_role:
            overwrites[prisoner_role] = discord.PermissionOverwrite(view_channel=False, connect=False)
        full = discord.PermissionOverwrite(
            view_channel=True, connect=True, speak=True, use_voice_activation=True,
        )
        overwrites[prisoner] = full
        overwrites[visitor] = full
        return overwrites

    async def ensure_infrastructure(self, guild: discord.Guild) -> dict:
        """كتصاوب/كتصلّح الكاتيكوري والرومز. آمنة ضد التكرار."""
        async with self._lock(guild.id):
            result = {"created": [], "repaired": [], "errors": []}
            prisoner, warden = await self.ensure_roles(guild)
            if prisoner is None:
                result["errors"].append("رول Prisoner ما تصاوبش — شوف صلاحيات البوت (Manage Roles).")
                return result

            record = self.store.guild(guild.id)

            # ───── الكاتيكوري ─────
            category = self.prison_category(guild)
            if category is None:
                category = discord.utils.find(
                    lambda c: c.name == PRISON_CATEGORY_NAME, guild.categories
                )
            if category is None:
                try:
                    category = await guild.create_category(
                        PRISON_CATEGORY_NAME,
                        overwrites=self._category_overwrites(guild),
                        reason=f"{REASON_TAG}: create category",
                    )
                    result["created"].append(PRISON_CATEGORY_NAME)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    result["errors"].append(f"الكاتيكوري: {exc}")
                    return result
            else:
                try:
                    await category.edit(
                        overwrites=self._category_overwrites(guild),
                        reason=f"{REASON_TAG}: repair category permissions",
                    )
                    result["repaired"].append(PRISON_CATEGORY_NAME)
                except (discord.Forbidden, discord.HTTPException) as exc:
                    result["errors"].append(f"الكاتيكوري: {exc}")

            record["category_id"] = category.id

            # ───── الرومز ─────
            for key, name in CHANNEL_NAMES.items():
                channel = guild.get_channel(int(record["channels"].get(key) or 0))
                if channel is None:
                    channel = discord.utils.find(
                        lambda c: c.name == name and c.category_id == category.id,
                        guild.text_channels,
                    )
                overwrites = self._channel_overwrites(guild, key)
                if channel is None:
                    try:
                        channel = await guild.create_text_channel(
                            name,
                            category=category,
                            overwrites=overwrites,
                            reason=f"{REASON_TAG}: create channel",
                        )
                        result["created"].append(name)
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        result["errors"].append(f"{name}: {exc}")
                        continue
                else:
                    try:
                        await channel.edit(
                            category=category,
                            overwrites=overwrites,
                            reason=f"{REASON_TAG}: repair channel permissions",
                        )
                        result["repaired"].append(name)
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        result["errors"].append(f"{name}: {exc}")
                record["channels"][key] = channel.id

            self.store.save()

            # ───── فويس شانيلز الزنازن (نفس سمية الروم النصية) ─────
            voice_map = record.setdefault("voice_channels", {})
            for key in CELL_KEYS:
                name = CHANNEL_NAMES[key]
                voice_channel = guild.get_channel(int(voice_map.get(key) or 0))
                if not isinstance(voice_channel, discord.VoiceChannel):
                    voice_channel = discord.utils.find(
                        lambda c: c.name == name and c.category_id == category.id,
                        guild.voice_channels,
                    )
                overwrites = self._cell_voice_overwrites(guild, key)
                if voice_channel is None:
                    try:
                        voice_channel = await guild.create_voice_channel(
                            name,
                            category=category,
                            overwrites=overwrites,
                            reason=f"{REASON_TAG}: create cell voice channel",
                        )
                        result["created"].append(f"{name} (voice)")
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        result["errors"].append(f"{name} (voice): {exc}")
                        continue
                else:
                    try:
                        await voice_channel.edit(
                            category=category,
                            overwrites=overwrites,
                            reason=f"{REASON_TAG}: repair cell voice channel",
                        )
                        result["repaired"].append(f"{name} (voice)")
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        result["errors"].append(f"{name} (voice): {exc}")
                voice_map[key] = voice_channel.id

            self.store.save()

        # رجّع الوصول ديال السجناء الحاليين لزنازنهم + خبّي السجن على الباقي
        await self.hide_everywhere(guild)
        for uid in list(self.store.inmates(guild.id)):
            member = guild.get_member(int(uid))
            if member:
                await self._grant_cell_access(member)
        await self.ensure_wanted_board(guild)
        await self.publish_prison_code(guild)
        await self.publish_visit_panel(guild)
        await self.refresh_wanted_board(guild)
        return result

    # ═══════════════════════════════════════════════════
    # ║        2. إخفاء رول Prisoner من كل السيرفر         ║
    # ═══════════════════════════════════════════════════

    async def _apply_hidden(self, channel: discord.abc.GuildChannel, role: discord.Role) -> bool:
        """كترجع True إلا تبدل شي حاجة."""
        current = channel.overwrites_for(role)
        if current.view_channel is False and current.send_messages is False:
            return False
        try:
            await channel.set_permissions(
                role,
                overwrite=HIDE_OVERWRITE,
                reason=f"{REASON_TAG}: prisoner blackout",
            )
            return True
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
            print(f"[PRISON] ⚠️ ما قدرتش نخبي {channel.name}: {type(exc).__name__}: {exc}")
            return False

    async def hide_everywhere(self, guild: discord.Guild) -> int:
        """كتخبي رول Prisoner من كاع الرومز/الكاتيكوريز برا السجن."""
        role = self.prisoner_role(guild)
        if role is None:
            return 0

        prison_ids = self.prison_channel_ids(guild)
        changed = 0
        for channel in list(guild.channels):
            if channel.id in prison_ids:
                continue
            if getattr(channel, "category_id", None) and channel.category_id in prison_ids:
                continue
            if await self._apply_hidden(channel, role):
                changed += 1
        if changed:
            print(f"[PRISON] 🔒 {guild.name}: {changed} روم تخباو على السجناء.")
        return changed

    async def _grant_cell_access(self, member: discord.Member) -> None:
        """
        كيعطي السجين وصول للزنزانة ديالو بوحدها (overwrite فردي) — نصي + صوتي.
        وإلا كان السجين دابا فشي فويس شانيل، كنرجعوه أوتوماتيكيا لفويس زنزانتو
        (نفس المنطق ملي يتسجن أول مرة، ملي يخرج من الانفرادي، أو ملي تتبدل الزنزانة ديالو).
        """
        record = self.store.inmate(member.guild.id, member.id)
        if not record:
            return
        cell_key = record.get("cell", "holding")
        target_voice: Optional[discord.VoiceChannel] = None

        for key in CELL_KEYS:
            channel = self.prison_channel(member.guild, key)
            if channel is not None:
                try:
                    if key == cell_key:
                        await channel.set_permissions(
                            member,
                            overwrite=discord.PermissionOverwrite(
                                view_channel=True,
                                read_messages=True,
                                read_message_history=True,
                                send_messages=True,
                                attach_files=False,
                                embed_links=False,
                                add_reactions=False,
                            ),
                            reason=f"{REASON_TAG}: assign cell",
                        )
                    elif channel.overwrites_for(member).view_channel is not None:
                        await channel.set_permissions(
                            member, overwrite=None, reason=f"{REASON_TAG}: clear old cell"
                        )
                except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                    pass

            voice_channel = self.cell_voice_channel(member.guild, key)
            if voice_channel is not None:
                try:
                    if key == cell_key:
                        await voice_channel.set_permissions(
                            member,
                            overwrite=discord.PermissionOverwrite(
                                view_channel=True,
                                connect=True,
                                speak=True,
                                use_voice_activation=True,
                                stream=False,
                            ),
                            reason=f"{REASON_TAG}: assign cell voice",
                        )
                        target_voice = voice_channel
                    elif voice_channel.overwrites_for(member).view_channel is not None:
                        await voice_channel.set_permissions(
                            member, overwrite=None, reason=f"{REASON_TAG}: clear old cell voice"
                        )
                except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                    pass

        # 🔊 نقل أوتوماتيكي: إلا كان السجين دابا فشي فويس، نرجعوه لفويس زنزانتو.
        if target_voice is not None:
            try:
                state = member.voice
                if state and state.channel and state.channel.id != target_voice.id:
                    await member.move_to(
                        target_voice, reason=f"{REASON_TAG}: auto-move to assigned cell voice"
                    )
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def _revoke_cell_access(self, guild: discord.Guild, member_or_id) -> None:
        target = member_or_id
        if isinstance(member_or_id, int):
            target = guild.get_member(member_or_id)
        if target is None:
            return
        for key in CELL_KEYS:
            channel = self.prison_channel(guild, key)
            if channel is not None:
                try:
                    if channel.overwrites_for(target).view_channel is not None:
                        await channel.set_permissions(
                            target, overwrite=None, reason=f"{REASON_TAG}: release"
                        )
                except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                    pass

            voice_channel = self.cell_voice_channel(guild, key)
            if voice_channel is not None:
                try:
                    if voice_channel.overwrites_for(target).view_channel is not None:
                        await voice_channel.set_permissions(
                            target, overwrite=None, reason=f"{REASON_TAG}: release voice"
                        )
                except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                    pass
                # طرد ديركت إلا كان مازال داخل فويس زنزانتو
                try:
                    if (
                        isinstance(target, discord.Member)
                        and target.voice
                        and target.voice.channel
                        and target.voice.channel.id == voice_channel.id
                    ):
                        await target.move_to(None, reason=f"{REASON_TAG}: release — disconnect")
                except (discord.Forbidden, discord.HTTPException):
                    pass

    # ═══════════════════════════════════════════════════
    # ║              3. السجن وإطلاق السراح               ║
    # ═══════════════════════════════════════════════════

    def _strippable_roles(self, member: discord.Member) -> list[discord.Role]:
        """الرولات اللي البوت قادر يحيدها فعلاً."""
        me = member.guild.me
        top = me.top_role.position if me else 0
        keep = {member.guild.default_role.id}
        prisoner = self.prisoner_role(member.guild)
        if prisoner:
            keep.add(prisoner.id)
        return [
            role
            for role in member.roles
            if role.id not in keep and not role.managed and role.position < top
        ]

    async def imprison(
        self,
        member: discord.Member,
        *,
        offense_key: str = "manual",
        seconds: Optional[int] = None,
        reason: str = "",
        actor: Optional[discord.abc.User] = None,
        cell: Optional[str] = None,
        announce_channel: Optional[discord.abc.Messageable] = None,
    ) -> dict:
        """
        الدالة الوحيدة اللي كتسجن. كل العقوبات فالبوت كيعيطو عليها.
        كترجع {"ok": bool, "error": str, "record": dict}
        """
        guild = member.guild

        if member.bot:
            return {"ok": False, "error": "ما كنسجنوش البوتات."}
        if member.id == guild.owner_id:
            return {"ok": False, "error": "Owner ديال السيرفر محمي."}

        async with self._member_lock(member.id):
            prisoner, _ = await self.ensure_roles(guild)
            if prisoner is None:
                return {"ok": False, "error": "رول Prisoner ماكاينش. دير Setup من البانل."}
            if self.prison_category(guild) is None:
                return {"ok": False, "error": "السجن ماشي مصاوب. دير Setup من البانل."}

            offense = self.store.offense(guild.id, offense_key)
            duration = int(seconds) if seconds is not None else int(offense["seconds"])
            cell_key = cell or offense.get("cell", "holding")
            if cell_key not in CELL_KEYS:
                cell_key = "holding"

            existing = self.store.inmate(guild.id, member.id)
            if existing:
                # كاين أصلاً فالسجن → كنزيدو المدة بدل ما نعاودو من الصفر.
                return await self.extend_sentence(
                    member, extra_seconds=duration, reason=reason, actor=actor
                )

            saved_roles = self._strippable_roles(member)
            saved_ids = [role.id for role in saved_roles]

            self._suppress_role_guard.add(member.id)
            try:
                try:
                    await member.edit(
                        roles=[prisoner],
                        reason=f"{REASON_TAG}: {offense['label']} — {reason or 'بلا سبب'}",
                    )
                except discord.Forbidden:
                    return {
                        "ok": False,
                        "error": "البوت ماعندوش Manage Roles ولا الرول ديالو تحت رول العضو.",
                    }
                except discord.HTTPException as exc:
                    return {"ok": False, "error": f"Discord رفض: {exc}"}
            finally:
                self._suppress_role_guard.discard(member.id)

            record = self.store.add_inmate(
                guild.id,
                member.id,
                seconds=duration,
                offense_key=offense_key,
                reason=reason or offense["label"],
                cell=cell_key,
                actor_id=int(getattr(actor, "id", 0) or 0),
                roles=saved_ids,
                nick=member.nick,
            )

        await self._grant_cell_access(member)
        await self._post_cell_card(member, record)

        embed = discord.Embed(
            title="⛓️ حكم بالسجن",
            description=f"{member.mention} تحكم عليه بالسجن.",
            color=COLOR_JAIL,
            timestamp=datetime.now(),
        )
        embed.add_field(name="📌 المخالفة", value=offense["label"], inline=True)
        embed.add_field(name="⏱️ المدة", value=format_duration(duration), inline=True)
        embed.add_field(name="🏚️ الزنزانة", value=_cell_display(cell_key), inline=True)
        embed.add_field(name="📝 السبب", value=(reason or offense["label"])[:1000], inline=False)
        embed.add_field(
            name="👮 المنفّذ",
            value=(actor.mention if isinstance(actor, (discord.Member, discord.User)) else "النظام الآلي"),
            inline=True,
        )
        embed.add_field(name="🗂️ Case", value=f"#{record['case']}", inline=True)
        embed.add_field(
            name="🎭 رولات محفوظة",
            value=str(len(saved_ids)) + " رول (غادي ترجع ليه)",
            inline=True,
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"GGMW9 Prison • Case #{record['case']}")
        await self._log(guild, embed)

        dm = discord.Embed(
            title="⛓️ تسجنتي فـ GGMW9",
            description=(
                f"**المخالفة:** {offense['label']}\n"
                f"**السبب:** {reason or offense['label']}\n"
                f"**المدة:** {format_duration(duration)}\n"
                f"**الزنزانة:** {_cell_display(cell_key)}\n\n"
                + (
                    f"🔓 غادي تخرج <t:{record['until']}:R> (<t:{record['until']}:F>)"
                    if record["until"] > 0
                    else "♾️ حكم مؤبّد — غير الاونر لي يقدر يطلق سراحك."
                )
                + "\n\nملي تسالي المدة كيرجعو ليك كاع الرولات ديالك أوتوماتيكيا."
            ),
            color=COLOR_JAIL,
            timestamp=datetime.now(),
        )
        dm.set_footer(text=f"GGMW9 Prison • Case #{record['case']}")
        await self._dm(member, dm)

        if announce_channel is not None:
            try:
                await announce_channel.send(
                    f"⛓️ {member.mention} تحط فالسجن — **{offense['label']}** "
                    f"({format_duration(duration)}) • Case #{record['case']}",
                    delete_after=12,
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        return {"ok": True, "record": record, "offense": offense}

    async def extend_sentence(
        self,
        member: discord.Member,
        *,
        extra_seconds: int,
        reason: str = "",
        actor: Optional[discord.abc.User] = None,
    ) -> dict:
        record = self.store.inmate(member.guild.id, member.id)
        if not record:
            return {"ok": False, "error": "هاد العضو ماشي فالسجن."}
        if int(record.get("until", 0)) < 0:
            return {"ok": True, "record": record, "note": "الحكم مؤبد أصلاً."}

        base = max(int(record["until"]), now_ts())
        record["until"] = base + int(extra_seconds)
        record.setdefault("extended", []).append(
            {"at": now_ts(), "seconds": int(extra_seconds), "by": int(getattr(actor, "id", 0) or 0)}
        )
        self.store.save()
        await self._post_cell_card(member, record)

        embed = discord.Embed(
            title="⏳ تمديد الحكم",
            description=f"{member.mention} تزادت ليه المدة.",
            color=discord.Color.orange(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="➕ الزيادة", value=format_duration(int(extra_seconds)), inline=True)
        embed.add_field(name="🔓 الخروج", value=f"<t:{record['until']}:R>", inline=True)
        embed.add_field(name="📝 السبب", value=(reason or "ما ذكرش سبب")[:1000], inline=False)
        await self._log(member.guild, embed)
        return {"ok": True, "record": record}

    async def reduce_sentence(
        self,
        member: discord.Member,
        *,
        seconds: int,
        actor: Optional[discord.abc.User] = None,
    ) -> dict:
        record = self.store.inmate(member.guild.id, member.id)
        if not record:
            return {"ok": False, "error": "هاد العضو ماشي فالسجن."}
        if int(record.get("until", 0)) < 0:
            return {"ok": False, "error": "الحكم مؤبد — خاصك تطلق سراحو مباشرة."}

        record["until"] = max(now_ts(), int(record["until"]) - int(seconds))
        self.store.save()
        await self._post_cell_card(member, record)

        embed = discord.Embed(
            title="⏬ تخفيض الحكم",
            description=f"{member.mention} تنقصات ليه المدة بـ **{format_duration(int(seconds))}**.",
            color=discord.Color.teal(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="🔓 الخروج", value=f"<t:{record['until']}:R>", inline=True)
        await self._log(member.guild, embed)
        return {"ok": True, "record": record}

    async def transfer_cell(
        self,
        member: discord.Member,
        *,
        new_cell: str,
        extra_seconds: int = 0,
        reason: str = "",
        actor: Optional[discord.abc.User] = None,
    ) -> dict:
        """
        كينقل السجين لزنزانة أخرى (تصعيد تلقائي ولا يدوي) — كيبدل cell، يمدد المدة
        إلا تعطات extra_seconds، وكينقلو تكست + فويس أوتوماتيكيا (عبر _grant_cell_access).
        """
        guild = member.guild
        record = self.store.inmate(guild.id, member.id)
        if not record:
            return {"ok": False, "error": "هاد العضو ماشي فالسجن."}
        if new_cell not in CELL_KEYS:
            return {"ok": False, "error": "زنزانة ماشي صحيحة."}
        if self.store.in_solitary(guild.id, member.id):
            return {"ok": False, "error": "السجين فالحبس الانفرادي دابا — ما يمكنش ننقلوه."}

        old_cell = record.get("cell", "holding")
        if old_cell == new_cell and not extra_seconds:
            return {"ok": True, "record": record, "note": "مازال فنفس الزنزانة."}

        record["cell"] = new_cell
        if extra_seconds and int(record.get("until", 0)) >= 0:
            base = max(int(record["until"]), now_ts())
            record["until"] = base + int(extra_seconds)
            record.setdefault("extended", []).append(
                {
                    "at": now_ts(),
                    "seconds": int(extra_seconds),
                    "by": int(getattr(actor, "id", 0) or 0),
                    "reason": "cell_transfer",
                }
            )
        self.store.save()

        await self._grant_cell_access(member)
        await self._post_cell_card(member, record)

        embed = discord.Embed(
            title="🚨 تصعيد العقوبة — نقل زنزانة",
            description=f"{member.mention} تنقل من **{_cell_display(old_cell)}** لـ **{_cell_display(new_cell)}**.",
            color=discord.Color.dark_orange(),
            timestamp=datetime.now(),
        )
        if extra_seconds:
            embed.add_field(name="➕ الزيادة", value=format_duration(int(extra_seconds)), inline=True)
        embed.add_field(name="📝 السبب", value=(reason or "تصعيد")[:1000], inline=False)
        embed.add_field(
            name="👮 المنفّذ",
            value=(actor.mention if isinstance(actor, (discord.Member, discord.User)) else "النظام الآلي (Auto-Mod)"),
            inline=True,
        )
        await self._log(guild, embed)

        dm = discord.Embed(
            title="🚨 تصعدت العقوبة ديالك!",
            description=(
                f"تنقلتي من **{_cell_display(old_cell)}** لـ **{_cell_display(new_cell)}**.\n"
                f"**السبب:** {reason or 'خرق القوانين'}\n"
                + (f"⏳ تزادت ليك **{format_duration(int(extra_seconds))}**.\n" if extra_seconds else "")
                + "\n⚠️ احترم القوانين ديال الزنزانة الجديدة — عاود كرر يقدر يزيدك عقوبة أكثر."
            ),
            color=discord.Color.dark_orange(),
            timestamp=datetime.now(),
        )
        await self._dm(member, dm)

        return {"ok": True, "record": record, "old_cell": old_cell, "new_cell": new_cell}

    def _detect_cell_violation(self, message: discord.Message) -> Optional[str]:
        """كتفحص رسالة ديال سجين داخل زنزانتو: محتوى ممنوع ولا Spam/Flood."""
        content_lower = (message.content or "").lower()
        for pattern in CELL_FORBIDDEN_PATTERNS:
            if pattern in content_lower:
                return f"محتوى ممنوع (`{pattern}`)"

        key = (message.guild.id, message.author.id)
        now = now_ts()
        bucket = self._cell_spam_tracker.setdefault(key, [])
        bucket.append(now)
        bucket[:] = [t for t in bucket if now - t <= CELL_SPAM_WINDOW_SECONDS]
        if len(bucket) >= CELL_SPAM_THRESHOLD:
            self._cell_spam_tracker[key] = []
            return "Spam / Flood فالزنزانة"
        return None

    async def _escalate_cell(self, member: discord.Member, *, reason: str) -> dict:
        """كتصعّد عقوبة السجين تلقائيا — بلا تدخل يدوي — ملي يخرق القوانين فزنزانتو."""
        guild = member.guild
        record = self.store.inmate(guild.id, member.id)
        if not record:
            return {"ok": False, "error": "هاد العضو ماشي فالسجن."}

        current_cell = record.get("cell", "holding")
        next_cell = NEXT_CELL.get(current_cell)
        extra_seconds = CELL_ESCALATION_EXTRA_SECONDS.get(
            current_cell, CELL_ESCALATION_EXTRA_SECONDS["max"]
        )

        if next_cell is None:
            # مازال فـ Maximum Security (السقف) → زيادة إضافية بلا تصعيد لزنزانة أقسح.
            if int(record.get("until", 0)) >= 0:
                base = max(int(record["until"]), now_ts())
                record["until"] = base + extra_seconds
                record.setdefault("extended", []).append(
                    {"at": now_ts(), "seconds": extra_seconds, "by": 0, "reason": "escalation"}
                )
                self.store.save()
                await self._post_cell_card(member, record)
            embed = discord.Embed(
                title="🚨 مخالفة جديدة فـ Maximum Security",
                description=f"{member.mention} خرق القوانين مرة أخرى وهو دايما فـ **{_cell_display(current_cell)}**.",
                color=discord.Color.dark_red(),
                timestamp=datetime.now(),
            )
            embed.add_field(name="📌 السبب", value=reason, inline=False)
            embed.add_field(name="➕ الزيادة", value=format_duration(extra_seconds), inline=True)
            await self._log(guild, embed)
            return {"ok": True, "record": record, "escalated": False}

        return await self.transfer_cell(
            member,
            new_cell=next_cell,
            extra_seconds=extra_seconds,
            reason=f"تصعيد تلقائي — {reason}",
            actor=None,
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        مراقبة تلقائية: أي سجين كيسبام ولا كيكتب حوايج ممنوعة وهو فزنزانتو
        (نصية) → كيتصعّد مباشرة لزنزانة أقسح، بلا حاجة لتدخل الإدارة.
        """
        if message.author.bot or message.guild is None:
            return
        member = message.author
        if not isinstance(member, discord.Member):
            return

        guild = message.guild
        record = self.store.inmate(guild.id, member.id)
        if not record:
            return
        if self.store.in_solitary(guild.id, member.id):
            return  # الحبس الانفرادي عندو منطق ديالو الخاص

        cell_key = record.get("cell", "holding")
        cell_channel = self.prison_channel(guild, cell_key)
        if cell_channel is None or message.channel.id != cell_channel.id:
            return

        violation = self._detect_cell_violation(message)
        if not violation:
            return

        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            pass

        await self._escalate_cell(member, reason=violation)

    async def release(
        self,
        guild: discord.Guild,
        user_id: int,
        *,
        reason: str = "سالات المدة",
        actor: Optional[discord.abc.User] = None,
        outcome: str = "released",
    ) -> dict:
        """إطلاق سراح + إرجاع الرولات بالضبط كيف كانو."""
        record = self.store.inmate(guild.id, user_id)
        if not record:
            return {"ok": False, "error": "هاد العضو ماشي فالسجن."}

        member = guild.get_member(int(user_id))
        restored: list[str] = []
        missing: list[str] = []

        if member is not None:
            async with self._member_lock(member.id):
                prisoner = self.prisoner_role(guild)
                me = guild.me
                top = me.top_role.position if me else 0

                target_roles = []
                for role_id in record.get("roles", []):
                    role = guild.get_role(int(role_id))
                    if role is None:
                        missing.append(str(role_id))
                    elif role.managed or role.position >= top:
                        missing.append(role.name)
                    else:
                        target_roles.append(role)
                        restored.append(role.name)

                # الرولات اللي البوت ما يقدرش يمسها كيبقاو كيف ما هوما
                keep = [
                    role
                    for role in member.roles
                    if (role.managed or role.position >= top)
                    and role != guild.default_role
                    and (prisoner is None or role.id != prisoner.id)
                ]

                self._suppress_role_guard.add(member.id)
                try:
                    await member.edit(
                        roles=list({r.id: r for r in (target_roles + keep)}.values()),
                        reason=f"{REASON_TAG}: release — {reason}",
                    )
                except (discord.Forbidden, discord.HTTPException) as exc:
                    print(f"[PRISON] ⚠️ إرجاع الرولات فشل لـ {member}: {exc}")
                finally:
                    self._suppress_role_guard.discard(member.id)

            await self._revoke_cell_access(guild, member)
            await self._delete_cell_card(guild, record)
        else:
            await self._delete_cell_card(guild, record)

        self.store.remove_inmate(
            guild.id, user_id, outcome=outcome, actor_id=int(getattr(actor, "id", 0) or 0)
        )

        embed = discord.Embed(
            title="🔓 إطلاق سراح",
            description=(member.mention if member else f"<@{user_id}>") + " خرج من السجن.",
            color=COLOR_FREE,
            timestamp=datetime.now(),
        )
        embed.add_field(name="📝 السبب", value=reason[:1000], inline=False)
        embed.add_field(
            name="👮 المنفّذ",
            value=(actor.mention if isinstance(actor, (discord.Member, discord.User)) else "النظام الآلي"),
            inline=True,
        )
        embed.add_field(name="🗂️ Case", value=f"#{record.get('case', '?')}", inline=True)
        if restored:
            embed.add_field(
                name=f"🎭 رولات ترجعات ({len(restored)})",
                value=", ".join(restored)[:1000],
                inline=False,
            )
        if missing:
            embed.add_field(
                name=f"⚠️ ما ترجعاتش ({len(missing)})",
                value=", ".join(missing)[:1000] + "\n(تمسحات ولا فوق رول البوت)",
                inline=False,
            )
        await self._log(guild, embed)

        if member is not None:
            dm = discord.Embed(
                title="🔓 خرجتي من السجن",
                description=(
                    f"**السبب:** {reason}\n"
                    f"**الرولات:** {len(restored)} رول ترجعو ليك.\n\n"
                    "ردّ البال المرة الجاية 🙏"
                ),
                color=COLOR_FREE,
                timestamp=datetime.now(),
            )
            await self._dm(member, dm)

        return {"ok": True, "restored": restored, "missing": missing}

    # ═══════════════════════════════════════════════════
    # ║             4. البطاقة الحية ديال السجين           ║
    # ═══════════════════════════════════════════════════

    @staticmethod
    def _progress_bar(record: dict, slots: int = 20) -> tuple[str, int]:
        """شريط تقدم ديال العقوبة + النسبة المئوية."""
        until = int(record.get("until", 0))
        since = int(record.get("since", now_ts()))
        if until < 0:
            return "▓" * slots, 100
        total = max(1, until - since)
        done = min(total, max(0, now_ts() - since))
        percent = int(done * 100 / total)
        filled = int(done * slots / total)
        return "▰" * filled + "▱" * (slots - filled), percent

    def _cell_card_embed(self, member: discord.Member, record: dict) -> discord.Embed:
        offense = self.store.offense(member.guild.id, record.get("offense", "manual"))
        until = int(record.get("until", 0))
        since = int(record.get("since", now_ts()))
        left = remaining_seconds(record)
        bar, percent = self._progress_bar(record)
        priors = self.store.record_count(member.guild.id, member.id)

        if until < 0:
            headline = "♾️ **حكم مؤبّد** — غير الاونر لي يقدر يطلق سراحك."
            colour = discord.Color.from_rgb(90, 0, 0)
        elif left <= 0:
            headline = "🔓 **سالات المدة!** غادي تخرج فأي لحظة…"
            colour = COLOR_FREE
        else:
            headline = f"⏳ باقي ليك **<t:{until}:R>**"
            colour = COLOR_JAIL

        embed = discord.Embed(
            title=f"⛓️ ملف السجين — {member.display_name}",
            description=(
                f"{member.mention}\n\n"
                f"{headline}\n"
                f"`{bar}` **{percent}%**"
            ),
            color=colour,
        )
        embed.add_field(name="📌 المخالفة", value=offense["label"], inline=True)
        embed.add_field(
            name="🏚️ الزنزانة",
            value=_cell_display(record.get("cell", "holding")),
            inline=True,
        )
        embed.add_field(name="🗂️ Case", value=f"#{record.get('case', '?')}", inline=True)

        embed.add_field(
            name="📝 السبب ديال دخولك للسجن",
            value=f"```{str(record.get('reason') or offense['label'])[:900]}```",
            inline=False,
        )

        embed.add_field(name="📥 دخلتي", value=f"<t:{since}:f>\n<t:{since}:R>", inline=True)
        embed.add_field(
            name="📤 غادي تخرج",
            value=(f"<t:{until}:f>\n<t:{until}:R>" if until > 0 else "—\nمؤبّد ♾️"),
            inline=True,
        )
        embed.add_field(
            name="⌛ الحكم الكامل",
            value=format_duration(int(record.get("sentence", 0))),
            inline=True,
        )

        if left > 0:
            embed.add_field(
                name="⏱️ الباقي بالتفصيل",
                value=f"**{format_duration(left)}**",
                inline=True,
            )
        embed.add_field(
            name="📚 السوابق",
            value=(f"{priors} مرة قبل هادي" if priors else "أول مرة"),
            inline=True,
        )
        extended = record.get("extended") or []
        if extended:
            embed.add_field(name="➕ تمديدات", value=f"{len(extended)} مرة", inline=True)

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text="العداد حي • كتب فـ warden-office إلا بغيتي تستأنف • آخر تحديث"
        )
        embed.timestamp = datetime.now()
        return embed

    async def _post_cell_card(self, member: discord.Member, record: dict) -> None:
        channel = self.prison_channel(member.guild, record.get("cell", "holding"))
        if channel is None:
            return
        embed = self._cell_card_embed(member, record)
        view = PrisonerCardView()
        message_id = int(record.get("cell_message_id") or 0)
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed, view=view)
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        try:
            message = await channel.send(content=member.mention, embed=embed, view=view)
            record["cell_message_id"] = message.id
            self.store.save()
            try:
                await message.pin(reason=f"{REASON_TAG}: inmate file")
            except (discord.Forbidden, discord.HTTPException):
                pass
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def refresh_cell_cards(self, guild: discord.Guild) -> int:
        """كيحدّث بطاقة كل سجين فالزنزانة ديالو."""
        updated = 0
        for uid, record in list(self.store.inmates(guild.id).items()):
            member = guild.get_member(int(uid))
            if member is None:
                continue
            channel = self.prison_channel(guild, record.get("cell", "holding"))
            message_id = int(record.get("cell_message_id") or 0)
            if channel is None or not message_id:
                await self._post_cell_card(member, record)
                updated += 1
                continue
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(
                    embed=self._cell_card_embed(member, record), view=PrisonerCardView()
                )
                updated += 1
            except discord.NotFound:
                record["cell_message_id"] = 0
                self.store.save()
                await self._post_cell_card(member, record)
                updated += 1
            except (discord.Forbidden, discord.HTTPException):
                continue
            await asyncio.sleep(0.6)  # احترام rate limits
        return updated

    async def _delete_cell_card(self, guild: discord.Guild, record: dict) -> None:
        message_id = int(record.get("cell_message_id") or 0)
        if not message_id:
            return
        channel = self.prison_channel(guild, record.get("cell", "holding"))
        if channel is None:
            return
        try:
            message = await channel.fetch_message(message_id)
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    # ═══════════════════════════════════════════════════
    # ║        5. الشكايات + الحبس الانفرادي              ║
    # ═══════════════════════════════════════════════════

    def complaint_route(self, guild: discord.Guild, target_id: int) -> str:
        """
        🔀 تقسيم الاختصاص:
          • السجين خفيف (severity 1) → الـWarden كيقدر يحسم
          • السجين كبير (severity 2-3) → **الاونر بوحدو**
        """
        record = self.store.inmate(guild.id, target_id)
        if not record:
            return "owner"
        offense = self.store.offense(guild.id, record.get("offense", "manual"))
        if int(offense.get("severity", 1)) <= WARDEN_ALLOWED_SEVERITY:
            return "warden"
        return "owner"

    async def submit_complaint(
        self, author: discord.Member, target_id: int, reason: str
    ) -> dict:
        guild = author.guild

        if not self.store.is_inmate(guild.id, author.id):
            return {"ok": False, "error": "غير السجناء لي كيقدرو يشكيو."}
        if int(target_id) == author.id:
            return {"ok": False, "error": "ما تقدرش تشكي من راسك."}
        if not self.store.is_inmate(guild.id, target_id):
            return {"ok": False, "error": "هاد العضو ماشي فالسجن."}
        if self.store.in_solitary(guild.id, target_id):
            return {"ok": False, "error": "هاد السجين راه أصلاً فالانفرادي."}

        left = self.store.complaint_cooldown_left(guild.id, author.id)
        if left > 0:
            return {
                "ok": False,
                "error": f"صبر شوية — تقدر تشكي من جديد بعد **{format_duration(left)}**.",
            }
        if len(self.store.pending_complaints(guild.id)) >= COMPLAINT_MAX_PENDING:
            return {"ok": False, "error": "كاين بزاف ديال الشكايات المعلقة. صبر حتى يتحسمو."}

        # ما نقبلوش شكايتين على نفس الهدف من نفس الشاكي
        for record in self.store.pending_complaints(guild.id).values():
            if int(record["author"]) == author.id and int(record["target"]) == int(target_id):
                return {"ok": False, "error": "عندك شكاية معلقة على هاد السجين."}

        route = self.complaint_route(guild, target_id)
        complaint = self.store.add_complaint(
            guild.id,
            author_id=author.id,
            target_id=int(target_id),
            reason=reason,
            route=route,
        )
        posted = await self._post_complaint(guild, complaint)
        if not posted:
            return {"ok": False, "error": "ما قدرتش نبعث الشكاية. عيّط للاونر."}
        return {"ok": True, "complaint": complaint, "route": route}

    async def _post_complaint(self, guild: discord.Guild, complaint: dict) -> bool:
        """كتبعث الشكاية للجهة المختصة: Warden desk ولا prison-log ديال الاونر."""
        route = complaint.get("route", "owner")
        channel = self.prison_channel(guild, "complaints" if route == "warden" else "log")
        if channel is None:
            channel = self.prison_channel(guild, "log")
        if channel is None:
            return False

        author = guild.get_member(int(complaint["author"]))
        target = guild.get_member(int(complaint["target"]))
        target_record = self.store.inmate(guild.id, complaint["target"]) or {}
        offense = self.store.offense(guild.id, target_record.get("offense", "manual"))

        author_text = author.mention if author else f"<@{int(complaint['author'])}>"
        target_text = target.mention if target else f"<@{int(complaint['target'])}>"

        embed = discord.Embed(
            title=f"📮 شكاية #{complaint['id']} — تسنّا القرار",
            description=(
                f"**الشاكي:** {author_text}\n"
                f"**المشكي عليه:** {target_text}"
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="📝 السبب", value=f"```{str(complaint['reason'])[:900]}```", inline=False
        )
        embed.add_field(name="⚖️ مخالفة المشكي عليه", value=offense["label"], inline=True)
        embed.add_field(
            name="🏚️ زنزانتو",
            value=_cell_display(target_record.get("cell", "holding")),
            inline=True,
        )
        embed.add_field(
            name="🔀 الاختصاص",
            value=("👮 Warden" if route == "warden" else "👑 **Owner بوحدو**"),
            inline=True,
        )
        embed.add_field(
            name="🔗 القرار",
            value=(
                "**قبول** → المشكي عليه كيمشي لروم انفرادية خاصة بيه.\n"
                "**رفض** → الشكاية كتطيح، والشاكي كياخد تنبيه."
            ),
            inline=False,
        )
        if target:
            embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text=f"GGMW9 Prison • Complaint #{complaint['id']}")

        try:
            message = await channel.send(embed=embed, view=ComplaintReviewView())
        except (discord.Forbidden, discord.HTTPException):
            return False

        complaint["message_id"] = message.id
        complaint["channel_id"] = channel.id
        self.store.save()
        return True

    # ───── الحبس الانفرادي ─────

    def solitary_overwrites(self, guild: discord.Guild, member: discord.Member) -> dict:
        """الروم الانفرادية: السجين المعني + الاونر + البوت بوحدهم."""
        overwrites = dict(self._category_overwrites(guild))
        prisoner = self.prisoner_role(guild)
        if prisoner:
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False)
        overwrites[member] = discord.PermissionOverwrite(
            view_channel=True,
            read_messages=True,
            read_message_history=True,
            send_messages=True,
            attach_files=False,
            embed_links=False,
            add_reactions=False,
        )
        return overwrites

    async def send_to_solitary(
        self,
        member: discord.Member,
        *,
        seconds: int,
        reason: str,
        actor: Optional[discord.abc.User] = None,
        complaint_id: int = 0,
    ) -> dict:
        """كتصاوب روم انفرادية باسم السجين وكتنقلو ليها."""
        guild = member.guild
        record = self.store.inmate(guild.id, member.id)
        if not record:
            return {"ok": False, "error": "هاد العضو ماشي فالسجن."}
        if self.store.in_solitary(guild.id, member.id):
            return {"ok": False, "error": "راه أصلاً فالانفرادي."}

        category = self.prison_category(guild)
        if category is None:
            return {"ok": False, "error": "كاتيكوري السجن ماكايناش."}

        if self.store.solitary_count(guild.id) >= SOLITARY_MAX_ROOMS:
            return {
                "ok": False,
                "error": (
                    f"الانفرادي عامر ({SOLITARY_MAX_ROOMS} روم — الحد ديال Discord). "
                    "صبر حتى يخرج شي واحد."
                ),
            }

        seconds = max(60, min(int(seconds), SOLITARY_MAX_SECONDS))
        name = solitary_channel_name(member.display_name, member.id)

        try:
            channel = await guild.create_text_channel(
                name,
                category=category,
                overwrites=self.solitary_overwrites(guild, member),
                topic=f"Solitary • {member} • {member.id}",
                reason=f"{REASON_TAG}: solitary confinement",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            return {"ok": False, "error": f"ما قدرتش نصاوب الروم: {exc}"}

        # نحيدو ليه الوصول للزنزانة العامة
        await self._revoke_cell_access(guild, member)
        await self._delete_cell_card(guild, record)
        record["cell_message_id"] = 0

        solitary = self.store.add_solitary(
            guild.id,
            member.id,
            channel_id=channel.id,
            seconds=seconds,
            reason=reason,
            by=int(getattr(actor, "id", 0) or 0),
            cell=record.get("cell", "holding"),
            complaint_id=complaint_id,
        )

        # بطاقة السجين كتتعاود فالروم الانفرادية
        await self._post_solitary_card(member, record, solitary, channel)

        embed = discord.Embed(
            title="🔗 حبس انفرادي",
            description=f"{member.mention} تنقل للحبس الانفرادي.",
            color=discord.Color.dark_purple(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="⏱️ مدة العزل", value=format_duration(seconds), inline=True)
        embed.add_field(name="🚪 الروم", value=channel.mention, inline=True)
        if complaint_id:
            embed.add_field(name="📮 شكاية", value=f"#{complaint_id}", inline=True)
        embed.add_field(name="📝 السبب", value=str(reason)[:1000], inline=False)
        embed.add_field(
            name="ℹ️ ملاحظة",
            value="الحكم الأصلي باقي كيمشي عادي — هادا عزل ماشي عقوبة زايدة.",
            inline=False,
        )
        await self._log(guild, embed)

        dm = discord.Embed(
            title="🔗 تنقلتي للحبس الانفرادي",
            description=(
                f"**السبب:** {reason}\n"
                f"**مدة العزل:** {format_duration(seconds)}\n"
                f"**تسالي:** <t:{solitary['until']}:R>\n\n"
                "⚠️ الحكم الأصلي ديالك باقي كيمشي عادي — العزل ما كيزيدش فيه.\n"
                "ملي يسالي العزل كترجع للزنزانة العادية."
            ),
            color=discord.Color.dark_purple(),
        )
        await self._dm(member, dm)
        return {"ok": True, "channel": channel, "record": solitary}

    async def _post_solitary_card(
        self,
        member: discord.Member,
        record: dict,
        solitary: dict,
        channel: discord.TextChannel,
    ) -> None:
        embed = self._cell_card_embed(member, record)
        embed.title = f"🔗 حبس انفرادي — {member.display_name}"
        embed.colour = discord.Color.dark_purple()
        embed.insert_field_at(
            0,
            name="🔗 العزل يسالي",
            value=f"**<t:{int(solitary['until'])}:R>**\n<t:{int(solitary['until'])}:f>",
            inline=False,
        )
        embed.insert_field_at(
            1,
            name="📮 سبب العزل",
            value=f"```{str(solitary.get('reason'))[:900]}```",
            inline=False,
        )
        try:
            message = await channel.send(content=member.mention, embed=embed, view=PrisonerCardView())
            record["cell_message_id"] = message.id
            self.store.save()
            try:
                await message.pin(reason=f"{REASON_TAG}: solitary file")
            except (discord.Forbidden, discord.HTTPException):
                pass
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def release_from_solitary(
        self, guild: discord.Guild, user_id: int, *, reason: str = "سالات مدة العزل"
    ) -> dict:
        solitary = self.store.in_solitary(guild.id, user_id)
        if not solitary:
            return {"ok": False, "error": "ماشي فالانفرادي."}

        channel = guild.get_channel(int(solitary.get("channel_id") or 0))
        if channel is not None:
            try:
                await channel.delete(reason=f"{REASON_TAG}: solitary ended")
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                pass

        self.store.remove_solitary(guild.id, user_id)

        member = guild.get_member(int(user_id))
        record = self.store.inmate(guild.id, user_id)
        if member is not None and record is not None:
            record["cell_message_id"] = 0
            self.store.save()
            await self._grant_cell_access(member)
            await self._post_cell_card(member, record)
            await self._dm(
                member,
                discord.Embed(
                    title="🔓 خرجتي من الانفرادي",
                    description=f"{reason}\nرجعتي للزنزانة العادية ديالك.",
                    color=COLOR_FREE,
                ),
            )

        embed = discord.Embed(
            title="🔓 نهاية الحبس الانفرادي",
            description=(member.mention if member else f"<@{user_id}>") + f" — {reason}",
            color=discord.Color.teal(),
            timestamp=datetime.now(),
        )
        await self._log(guild, embed)
        return {"ok": True}

    # ═══════════════════════════════════════════════════
    # ║                  5ب. الزيارات                     ║
    # ═══════════════════════════════════════════════════

    async def publish_visit_panel(self, guild: discord.Guild) -> None:
        channel = self.visit_channel(guild)
        if channel is None:
            return
        record = self.store.guild(guild.id)
        embed = discord.Embed(
            title="👥 غرفة الزيارات",
            description=(
                "هنا كتنظم الزيارات بين السجناء والمعارف ديالهم.\n\n"
                "🔔 **طلب زيارة** — اختار سجين، من بعد اختار الشخص لي بغيتي تدعوه.\n"
                "📋 **الزيارات الجارية** — شوف شكون كيزور شكون دابا.\n"
                "📴 **سد زيارة** — وقّف زيارة جارية قبل ما تسالي مدتها.\n\n"
                f"⏱️ كل زيارة كتدوم **{format_duration(VISIT_DEFAULT_SECONDS)}** بشكل تلقائي، "
                "ومن بعد كيرجع السجين أوتوماتيكيا لزنزانتو.\n"
                "⚠️ هاد البانل خاصة بالإدارة (Admin / Mod / Warden / Owner) — "
                "روم الزيارة الصوتية كتبقى خاصة بالسجين والزائر المدعو (+ الإدارة للإشراف)."
            ),
            color=discord.Color.blurple(),
        )
        message_id = int(record.get("visits_message_id") or 0)
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed, view=VisitPanelView())
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        try:
            message = await channel.send(embed=embed, view=VisitPanelView())
            record["visits_message_id"] = message.id
            self.store.save()
        except (discord.Forbidden, discord.HTTPException):
            pass

    def visits_embed(self, guild: discord.Guild) -> discord.Embed:
        visits = self.store.visits(guild.id)
        embed = discord.Embed(
            title="👥 الزيارات — الحالة", color=discord.Color.blurple(), timestamp=datetime.now()
        )
        active = [r for r in visits.values() if r.get("status") == "active"]
        pending = [r for r in visits.values() if r.get("status") == "pending"]
        if not active and not pending:
            embed.description = "🕊️ ماكاين حتى زيارة دابا."
            return embed
        if active:
            lines = [
                f"👥 <@{r['prisoner_id']}> × <@{r['visitor_id']}> — تسالي <t:{int(r['until'])}:R>"
                for r in active
            ]
            embed.add_field(name=f"🟢 جارية ({len(active)})", value="\n".join(lines)[:1024], inline=False)
        if pending:
            lines = [f"⏳ <@{r['prisoner_id']}> × <@{r['visitor_id']}>" for r in pending]
            embed.add_field(name=f"🟡 معلّقة ({len(pending)})", value="\n".join(lines)[:1024], inline=False)
        return embed

    async def request_visit(
        self, guild: discord.Guild, *, prisoner_id: int, visitor_id: int, actor
    ) -> dict:
        """كتبعث دعوة زيارة للزائر. كترجع {"ok": bool, "error"?: str, "record"?, "dm"?: bool}."""
        if not self.store.is_inmate(guild.id, prisoner_id):
            return {"ok": False, "error": "هاد السجين خرج من السجن."}
        if self.store.in_solitary(guild.id, prisoner_id):
            return {"ok": False, "error": "السجين فالحبس الانفرادي — ما يقدرش يستقبل زوار دابا."}
        if self.store.active_visit_for_inmate(guild.id, prisoner_id):
            return {"ok": False, "error": "عندو زيارة جارية ولا معلّقة أصلاً."}
        if self.store.active_visit_for_visitor(guild.id, visitor_id):
            return {"ok": False, "error": "هاد الزائر عندو زيارة جارية ولا معلّقة أصلاً."}

        prisoner = guild.get_member(prisoner_id)
        visitor = guild.get_member(visitor_id)
        if prisoner is None or visitor is None:
            return {"ok": False, "error": "شي حد ماشي متاح دابا."}

        record = self.store.add_visit(
            guild.id,
            prisoner_id=prisoner_id,
            visitor_id=visitor_id,
            seconds=VISIT_DEFAULT_SECONDS,
            by=int(getattr(actor, "id", 0) or 0),
        )

        embed = discord.Embed(
            title="👥 دعوة زيارة",
            description=(
                f"شي حد بغاك تزور **{prisoner.display_name}** فالسجن.\n\n"
                f"⏱️ الزيارة غادي تدوم **{format_duration(VISIT_DEFAULT_SECONDS)}** إلا قبلتي.\n"
                "غادي تنعطاو فويس شانيل خاص بيكم بجوج."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"الدعوة كتلغى تلقائيا بعد {format_duration(VISIT_INVITE_TIMEOUT_SECONDS)}")

        view = VisitInviteView(self, record["id"], visitor_id, guild.id)
        sent_dm = False
        try:
            message = await visitor.send(embed=embed, view=view)
            view.invite_message = message
            sent_dm = True
        except (discord.Forbidden, discord.HTTPException):
            pass

        if not sent_dm:
            channel = self.visit_channel(guild)
            if channel is None:
                self.store.remove_visit(guild.id, record["id"])
                return {"ok": False, "error": "الـDM مسدودة وروم الزيارات ماكايناش."}
            try:
                message = await channel.send(content=visitor.mention, embed=embed, view=view)
                view.invite_message = message
            except (discord.Forbidden, discord.HTTPException):
                self.store.remove_visit(guild.id, record["id"])
                return {"ok": False, "error": "ما قدرتش نوصل الدعوة (DM مسدودة + ماقدرتش نكتب فروم الزيارات)."}

        log_embed = discord.Embed(
            title="📮 طلب زيارة جديد",
            description=f"{prisoner.mention} × {visitor.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        log_embed.add_field(
            name="👮 طالب الزيارة",
            value=(actor.mention if isinstance(actor, (discord.Member, discord.User)) else "؟"),
            inline=True,
        )
        await self._log(guild, log_embed)

        return {"ok": True, "record": record, "dm": sent_dm}

    async def accept_visit(self, guild: discord.Guild, visit_id, *, visitor_id: int) -> dict:
        record = self.store.visit(guild.id, visit_id)
        if not record or record.get("status") != "pending":
            return {"ok": False, "error": "هاد الدعوة ماشي صالحة (تلغات ولا تجاوب عليها قبل)."}
        if int(record.get("visitor_id", 0)) != int(visitor_id):
            return {"ok": False, "error": "هاد الدعوة ماشي ليك."}
        return await self._activate_visit(guild, visit_id, record)

    async def accept_visit_as_prisoner(self, guild: discord.Guild, visit_id, *, prisoner_id: int) -> dict:
        """موافقة السجين على دعوة زيارة بعثها ليه زائر عادي (request_self_visit)."""
        record = self.store.visit(guild.id, visit_id)
        if not record or record.get("status") != "pending":
            return {"ok": False, "error": "هاد الدعوة ماشي صالحة (تلغات ولا تجاوب عليها قبل)."}
        if int(record.get("prisoner_id", 0)) != int(prisoner_id):
            return {"ok": False, "error": "هاد الدعوة ماشي ليك."}
        return await self._activate_visit(guild, visit_id, record)

    async def request_self_visit(
        self, guild: discord.Guild, *, prisoner_id: int, visitor_id: int, actor
    ) -> dict:
        """
        طلب زيارة من عضو عادي (ماشي إدارة) باش يزور صاحبو المسجون.
        الدعوة كتبعث **للسجين نفسو** — خاص يوافق هو باش تحل الروم (بحال زيارة حقيقية).
        """
        if not self.store.is_inmate(guild.id, prisoner_id):
            return {"ok": False, "error": "هاد السجين خرج من السجن."}
        if self.store.in_solitary(guild.id, prisoner_id):
            return {"ok": False, "error": "السجين فالحبس الانفرادي — ما يقدرش يستقبل زوار دابا."}
        if self.store.active_visit_for_inmate(guild.id, prisoner_id):
            return {"ok": False, "error": "عندو زيارة جارية ولا معلّقة أصلاً."}
        if self.store.is_inmate(guild.id, visitor_id):
            return {"ok": False, "error": "السجين ما يقدرش يزور سجين آخر."}
        if self.store.active_visit_for_visitor(guild.id, visitor_id):
            return {"ok": False, "error": "عندك زيارة جارية ولا معلّقة أصلاً."}

        prisoner = guild.get_member(prisoner_id)
        visitor = guild.get_member(visitor_id)
        if prisoner is None or visitor is None:
            return {"ok": False, "error": "شي حد ماشي متاح دابا."}

        record = self.store.add_visit(
            guild.id,
            prisoner_id=prisoner_id,
            visitor_id=visitor_id,
            seconds=VISIT_DEFAULT_SECONDS,
            by=int(getattr(actor, "id", 0) or 0),
        )

        embed = discord.Embed(
            title="👥 طلب زيارة",
            description=(
                f"{visitor.mention} بغا يزورك فالسجن.\n\n"
                f"⏱️ الزيارة غادي تدوم **{format_duration(VISIT_DEFAULT_SECONDS)}** إلا وافقتي.\n"
                "غادي تنعطاو فويس شانيل خاص بيكم بجوج بوحدكم."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"الدعوة كتلغى تلقائيا بعد {format_duration(VISIT_INVITE_TIMEOUT_SECONDS)}")

        view = PrisonerVisitInviteView(self, record["id"], prisoner_id, guild.id)
        sent_dm = False
        try:
            message = await prisoner.send(embed=embed, view=view)
            view.invite_message = message
            sent_dm = True
        except (discord.Forbidden, discord.HTTPException):
            pass

        if not sent_dm:
            channel = self.visit_channel(guild)
            if channel is None:
                self.store.remove_visit(guild.id, record["id"])
                return {"ok": False, "error": "الـDM مسدودة وروم الزيارات ماكايناش."}
            try:
                message = await channel.send(content=prisoner.mention, embed=embed, view=view)
                view.invite_message = message
            except (discord.Forbidden, discord.HTTPException):
                self.store.remove_visit(guild.id, record["id"])
                return {"ok": False, "error": "ما قدرتش نوصل الدعوة (DM مسدودة + ماقدرتش نكتب فروم الزيارات)."}

        log_embed = discord.Embed(
            title="📮 طلب زيارة جديد (عضو عادي)",
            description=f"{visitor.mention} → {prisoner.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        log_embed.add_field(name="👤 طالب الزيارة", value=visitor.mention, inline=True)
        await self._log(guild, log_embed)

        return {"ok": True, "record": record, "dm": sent_dm}

    async def _activate_visit(self, guild: discord.Guild, visit_id, record: dict) -> dict:
        """كتصاوب روم الفويس ديال الزيارة وكتبدا العداد. مستعملة من accept_visit و accept_visit_as_prisoner."""
        prisoner_id = int(record["prisoner_id"])
        visitor_id = int(record["visitor_id"])

        if not self.store.is_inmate(guild.id, prisoner_id):
            self.store.remove_visit(guild.id, visit_id)
            return {"ok": False, "error": "السجين خرج من السجن قبل الزيارة."}
        if self.store.in_solitary(guild.id, prisoner_id):
            self.store.remove_visit(guild.id, visit_id)
            return {"ok": False, "error": "السجين تنقل للحبس الانفرادي — ما يقدرش يستقبلك دابا."}

        prisoner = guild.get_member(prisoner_id)
        visitor = guild.get_member(visitor_id)
        category = self.prison_category(guild)
        if prisoner is None or visitor is None or category is None:
            self.store.remove_visit(guild.id, visit_id)
            return {"ok": False, "error": "شي حد (ولا الكاتيكوري) ماشي متاح دابا."}

        seconds = int(record.get("seconds") or VISIT_DEFAULT_SECONDS)
        overwrites = self._visit_voice_overwrites(guild, prisoner, visitor)
        try:
            channel = await guild.create_voice_channel(
                visit_channel_name(prisoner.display_name, prisoner.id),
                category=category,
                overwrites=overwrites,
                reason=f"{REASON_TAG}: visit room ({prisoner} × {visitor})",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            return {"ok": False, "error": f"ما قدرتش نصاوب روم الزيارة: {exc}"}

        self.store.start_visit(guild.id, visit_id, channel_id=channel.id, seconds=seconds)
        record = self.store.visit(guild.id, visit_id)

        # 🔊 نقل أوتوماتيكي: السجين إلا كان دابا فشي فويس
        try:
            if prisoner.voice and prisoner.voice.channel:
                await prisoner.move_to(channel, reason=f"{REASON_TAG}: visit start")
        except (discord.Forbidden, discord.HTTPException):
            pass
        # الزائر: نديرو move إلا كان أصلاً فشي فويس بنفس السيرفر
        try:
            if visitor.voice and visitor.voice.channel:
                await visitor.move_to(channel, reason=f"{REASON_TAG}: visit start")
        except (discord.Forbidden, discord.HTTPException):
            pass

        embed = discord.Embed(
            title="👥 بدات زيارة",
            description=f"{prisoner.mention} × {visitor.mention}",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="⏱️ المدة", value=format_duration(seconds), inline=True)
        embed.add_field(name="🚪 الروم", value=channel.mention, inline=True)
        await self._log(guild, embed)

        try:
            await channel.send(
                f"👋 {visitor.mention} جا يزور {prisoner.mention}.\n"
                f"⏱️ الزيارة غادي تسالي **<t:{int(record['until'])}:R>** — من بعد كترجعو أوتوماتيكيا."
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

        return {"ok": True, "channel": channel, "record": record}

    async def decline_visit(
        self, guild: discord.Guild, visit_id, *, reason: str = "مرفوضة"
    ) -> dict:
        record = self.store.remove_visit(guild.id, visit_id)
        if not record:
            return {"ok": False, "error": "الدعوة ماكايناش."}
        embed = discord.Embed(
            title="🚫 دعوة زيارة تلغات",
            description=f"<@{record['prisoner_id']}> × <@{record['visitor_id']}>\n{reason}",
            color=discord.Color.dark_grey(),
            timestamp=datetime.now(),
        )
        await self._log(guild, embed)
        return {"ok": True}

    async def end_visit(
        self, guild: discord.Guild, visit_id, *, reason: str = "سالات المدة", actor=None
    ) -> dict:
        """كتسد زيارة جارية: كترجع السجين لفويس زنزانتو أوتوماتيكيا وكتطرد الزائر."""
        record = self.store.visit(guild.id, visit_id)
        if not record or record.get("status") != "active":
            return {"ok": False, "error": "هاد الزيارة ماشي جارية."}

        channel = guild.get_channel(int(record.get("channel_id") or 0))
        prisoner = guild.get_member(int(record.get("prisoner_id", 0)))
        visitor = guild.get_member(int(record.get("visitor_id", 0)))

        # 🔊 رجّع السجين لفويس زنزانتو (إلا كان دابا فروم الزيارة)
        if prisoner is not None:
            cell_record = self.store.inmate(guild.id, prisoner.id)
            cell_voice = None
            if cell_record:
                cell_voice = self.cell_voice_channel(guild, cell_record.get("cell", "holding"))
            try:
                if (
                    prisoner.voice
                    and channel is not None
                    and prisoner.voice.channel
                    and prisoner.voice.channel.id == channel.id
                ):
                    if cell_voice is not None:
                        await prisoner.move_to(cell_voice, reason=f"{REASON_TAG}: visit ended")
                    else:
                        await prisoner.move_to(None, reason=f"{REASON_TAG}: visit ended")
            except (discord.Forbidden, discord.HTTPException):
                pass

        # طرد الزائر
        if visitor is not None and channel is not None:
            try:
                if visitor.voice and visitor.voice.channel and visitor.voice.channel.id == channel.id:
                    await visitor.move_to(None, reason=f"{REASON_TAG}: visit ended")
            except (discord.Forbidden, discord.HTTPException):
                pass

        if channel is not None:
            try:
                await channel.delete(reason=f"{REASON_TAG}: visit ended")
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                pass

        self.store.remove_visit(guild.id, visit_id)

        embed = discord.Embed(
            title="🔚 نهاية الزيارة",
            description=f"<@{record['prisoner_id']}> × <@{record['visitor_id']}>\n{reason}",
            color=discord.Color.dark_teal(),
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="👮 المنفّذ",
            value=(
                actor.mention
                if isinstance(actor, (discord.Member, discord.User))
                else "النظام الآلي (سالات المدة)"
            ),
            inline=True,
        )
        await self._log(guild, embed)
        return {"ok": True}

    # ═══════════════════════════════════════════════════
    # ║          6. لوحة القوانين + لوحة السجناء          ║
    # ═══════════════════════════════════════════════════

    def prison_code_embeds(self, guild: discord.Guild) -> list[discord.Embed]:
        catalogue = self.store.offenses(guild.id)
        intro = discord.Embed(
            title="📜 PRISON CODE — قانون السجن",
            description=(
                "هادي لائحة **كاع الحوايج اللي كيدخلوك للسجن** والمدة ديال كل وحدة.\n"
                "ملي تدخل للسجن كيتحيدو ليك **كاع الرولات** ديالك وما تبقا تشوف "
                "حتى روم فالسيرفر غير الزنزانة ديالك.\n"
                "ملي تسالي المدة كيرجعو ليك الرولات ديالك **أوتوماتيكيا** كيف كانو.\n\n"
                "⚠️ **السوابق كتزيد فالمدة.** اللي كيعاود كيتحكم عليه بأقسح."
            ),
            color=COLOR_INFO,
        )
        intro.set_footer(text="GGMW9 Prison • القانون كيتطبق على الجميع بلا استثناء")

        by_cell: dict[str, list[str]] = {"holding": [], "block": [], "max": []}
        for entry in sorted(catalogue.values(), key=lambda e: (e.get("severity", 1), e["seconds"])):
            cell = entry.get("cell", "holding")
            if cell not in by_cell:
                cell = "holding"
            by_cell[cell].append(f"• **{entry['label']}** — `{format_duration(entry['seconds'])}`")

        titles = {
            "holding": "⛓️ HOLDING CELL — عقوبات خفيفة",
            "block": "🔒 CELL BLOCK — عقوبات متوسطة",
            "max": "🚨 MAXIMUM SECURITY — عقوبات قاسحة",
        }
        rules = discord.Embed(title="⚖️ العقوبات حسب الزنزانة", color=discord.Color.dark_theme())
        for key in CELL_KEYS:
            lines = by_cell.get(key) or ["—"]
            rules.add_field(name=titles[key], value="\n".join(lines)[:1024], inline=False)
        rules.set_footer(text="أي حكم كيتسجل بـ Case ID • الاونر بوحدو لي كيقدر يبدل ولا يطلق سراح")
        return [intro, rules]

    async def publish_prison_code(self, guild: discord.Guild) -> None:
        channel = self.prison_channel(guild, "code")
        if channel is None:
            return
        record = self.store.guild(guild.id)
        embeds = self.prison_code_embeds(guild)
        message_id = int(record.get("code_message_id") or 0)
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embeds=embeds)
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        try:
            message = await channel.send(embeds=embeds)
            record["code_message_id"] = message.id
            self.store.save()
        except (discord.Forbidden, discord.HTTPException):
            pass

    def board_embed(self, guild: discord.Guild) -> discord.Embed:
        inmates = self.store.inmates(guild.id)
        embed = discord.Embed(
            title="📋 PRISON BOARD — السجناء الحاليين",
            description=f"العدد الإجمالي: **{len(inmates)}**",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(),
        )
        if not inmates:
            embed.description = "🕊️ السجن خاوي. كلشي حر."
            embed.set_footer(text="كيتحدث كل دقيقة")
            return embed

        rows: dict[str, list[str]] = {key: [] for key in CELL_KEYS}
        ordered = sorted(
            inmates.items(),
            key=lambda item: (int(item[1].get("until", 0)) if int(item[1].get("until", 0)) > 0 else 1 << 62),
        )
        for uid, record in ordered:
            member = guild.get_member(int(uid))
            name = member.mention if member else f"<@{uid}> *(خرج من السيرفر)*"
            until = int(record.get("until", 0))
            timer = f"<t:{until}:R>" if until > 0 else "♾️ مؤبّد"
            cell = record.get("cell", "holding")
            if cell not in rows:
                cell = "holding"
            rows[cell].append(f"`#{record.get('case','?')}` {name} → {timer}")

        titles = {"holding": "⛓️ Holding Cell", "block": "🔒 Cell Block", "max": "🚨 Maximum Security"}
        for key in CELL_KEYS:
            if rows[key]:
                embed.add_field(
                    name=f"{titles[key]} ({len(rows[key])})",
                    value="\n".join(rows[key])[:1024],
                    inline=False,
                )
        embed.set_footer(text="العدادات حية • كيتحدث كل دقيقة")
        return embed

    async def refresh_board(self, guild: discord.Guild) -> None:
        channel = self.prison_channel(guild, "log")
        if channel is None:
            return
        record = self.store.guild(guild.id)
        embed = self.board_embed(guild)
        message_id = int(record.get("board_message_id") or 0)
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed)
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        try:
            message = await channel.send(embed=embed)
            record["board_message_id"] = message.id
            self.store.save()
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ═══════════════════════════════════════════════════
    # ║        7. اللوحة العامة (wanted-board)            ║
    # ═══════════════════════════════════════════════════

    def wanted_board_overwrites(self, guild: discord.Guild) -> dict:
        """عامة للجميع، ولكن read-only. حتى الادمين ما كيكتبش فيها."""
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=False,
                add_reactions=False,
                create_public_threads=False,
                create_private_threads=False,
            )
        }
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, manage_messages=True, embed_links=True
            )
        for role_id in (self.admin_role_id, self.moderator_role_id):
            role = guild.get_role(role_id) if role_id else None
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True, read_messages=True, send_messages=False
                )
        # السجناء ما كيشوفوهاش — هوما عندهم البطاقة ديالهم
        prisoner = self.prisoner_role(guild)
        if prisoner:
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False)
        return overwrites

    async def ensure_wanted_board(self, guild: discord.Guild):
        """كتصاوب/كتلقا الروم العامة — **برا** كاتيكوري السجن."""
        record = self.store.guild(guild.id)
        channel = guild.get_channel(int(record.get("wanted_channel_id") or 0))
        if channel is None:
            channel = discord.utils.find(
                lambda c: c.name == WANTED_BOARD_CHANNEL_NAME, guild.text_channels
            )
        if channel is None:
            try:
                channel = await guild.create_text_channel(
                    WANTED_BOARD_CHANNEL_NAME,
                    overwrites=self.wanted_board_overwrites(guild),
                    topic="لائحة السجناء الحاليين — شكون مسجون، علاش، وشحال باقي ليه.",
                    reason=f"{REASON_TAG}: public wanted board",
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[PRISON] ⚠️ ما قدرتش نصاوب wanted-board: {exc}")
                return None
        else:
            try:
                await channel.edit(
                    overwrites=self.wanted_board_overwrites(guild),
                    reason=f"{REASON_TAG}: repair wanted board",
                )
            except (discord.Forbidden, discord.HTTPException):
                pass

        if int(record.get("wanted_channel_id") or 0) != channel.id:
            record["wanted_channel_id"] = channel.id
            self.store.save()
        return channel

    def wanted_board_embed(self, guild: discord.Guild) -> discord.Embed:
        """
        ⚠️ عمداً: **ما كيبانش شكون حكم**. غير شكون مسجون، علاش، وشحال باقي ليه.
        هكذا الردع كيخدم والتخفي ديال الاونر محفوظ.
        """
        inmates = self.store.inmates(guild.id)
        embed = discord.Embed(
            title="📢 WANTED BOARD — السجناء الحاليين",
            color=discord.Color.dark_red(),
            timestamp=datetime.now(),
        )
        if not inmates:
            embed.description = "🕊️ **السجن خاوي.** كلشي حر — خليها هكا."
            embed.set_footer(text="كيتحدث كل دقيقة • اللائحة الكاملة ديال المخالفات فـ prison-code")
            return embed

        embed.description = (
            f"عدد السجناء: **{len(inmates)}**\n"
            "شوف علاش تسجنو وشحال باقي ليهم. القانون كامل فـ `prison-code`."
        )

        lines: list[str] = []
        ordered = sorted(
            inmates.items(),
            key=lambda item: (
                int(item[1].get("until", 0)) if int(item[1].get("until", 0)) > 0 else 1 << 62
            ),
        )
        for uid, record in ordered[:30]:
            member = guild.get_member(int(uid))
            name = member.mention if member else f"<@{uid}>"
            offense = self.store.offense(guild.id, record.get("offense", "manual"))
            until = int(record.get("until", 0))
            timer = f"<t:{until}:R>" if until > 0 else "♾️ مؤبّد"
            solitary = "🔗 " if self.store.in_solitary(guild.id, int(uid)) else ""
            lines.append(f"{solitary}`#{record.get('case','?')}` {name}\n╰ {offense['label']} — باقي {timer}")

        chunk: list[str] = []
        field_index = 1
        for line in lines:
            if sum(len(x) + 1 for x in chunk) + len(line) > 1000:
                embed.add_field(
                    name="⛓️ السجناء" if field_index == 1 else "\u200b",
                    value="\n".join(chunk),
                    inline=False,
                )
                chunk, field_index = [], field_index + 1
            chunk.append(line)
        if chunk:
            embed.add_field(
                name="⛓️ السجناء" if field_index == 1 else "\u200b",
                value="\n".join(chunk),
                inline=False,
            )

        if len(ordered) > 30:
            embed.add_field(name="…", value=f"و {len(ordered) - 30} آخرين", inline=False)

        embed.set_footer(text="🔗 = حبس انفرادي • العدادات حية • كيتحدث كل دقيقة")
        return embed

    async def refresh_wanted_board(self, guild: discord.Guild) -> None:
        channel = guild.get_channel(int(self.store.guild(guild.id).get("wanted_channel_id") or 0))
        if channel is None:
            return
        record = self.store.guild(guild.id)
        embed = self.wanted_board_embed(guild)
        message_id = int(record.get("wanted_message_id") or 0)
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed)
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        try:
            message = await channel.send(embed=embed)
            record["wanted_message_id"] = message.id
            self.store.save()
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ═══════════════════════════════════════════════════
    # ║                   8. الحلقات                      ║
    # ═══════════════════════════════════════════════════

    @tasks.loop(seconds=20)
    async def release_loop(self):
        for guild in list(self.bot.guilds):
            try:
                # 🔗 الانفرادي الأول — باش السجين يرجع لزنزانتو قبل أي إطلاق
                for user_id, _sol in self.store.expired_solitary(guild.id):
                    await self.release_from_solitary(guild, user_id)

                for user_id, _record in self.store.expired_inmates(guild.id):
                    # إلا كان فالانفرادي وسالا حكمو، كنمسحو الروم الأول
                    if self.store.in_solitary(guild.id, user_id):
                        await self.release_from_solitary(
                            guild, user_id, reason="سالا الحكم الأصلي"
                        )
                    await self.release(
                        guild, user_id, reason="سالات المدة ديال الحكم", outcome="expired"
                    )
            except Exception as exc:  # ما نوقفوش الحلقة على شي غلطة وحدة
                print(f"[PRISON] ❌ release_loop: {type(exc).__name__}: {exc}")

    @release_loop.before_loop
    async def _before_release(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=60)
    async def board_loop(self):
        for guild in list(self.bot.guilds):
            try:
                if self.prison_channel(guild, "log"):
                    await self.refresh_board(guild)
                await self.refresh_wanted_board(guild)
            except Exception as exc:
                print(f"[PRISON] ❌ board_loop: {type(exc).__name__}: {exc}")

    @board_loop.before_loop
    async def _before_board(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=60)
    async def card_loop(self):
        """كيخلي بطاقة كل سجين حية فالزنزانة ديالو."""
        for guild in list(self.bot.guilds):
            try:
                if self.store.inmates(guild.id):
                    await self.refresh_cell_cards(guild)
            except Exception as exc:
                print(f"[PRISON] ❌ card_loop: {type(exc).__name__}: {exc}")

    @card_loop.before_loop
    async def _before_cards(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=20)
    async def visit_loop(self):
        """كتسد الزيارات اللي سالات مدتها وكترجع السجين أوتوماتيكيا لفويس زنزانتو."""
        for guild in list(self.bot.guilds):
            try:
                for visit_id, _record in self.store.expired_visits(guild.id):
                    await self.end_visit(guild, visit_id, reason="سالات مدة الزيارة")
            except Exception as exc:
                print(f"[PRISON] ❌ visit_loop: {type(exc).__name__}: {exc}")

    @visit_loop.before_loop
    async def _before_visits(self):
        await self.bot.wait_until_ready()

    # ═══════════════════════════════════════════════════
    # ║                  7. الأحداث                       ║
    # ═══════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready_done:
            return
        self._ready_done = True
        for guild in self.bot.guilds:
            try:
                if self.prisoner_role(guild) is None:
                    continue  # ما تصاوبش عاد — كيستنا Setup من بانل الاونر
                await self.hide_everywhere(guild)
                await self.publish_prison_code(guild)
                await self.publish_visit_panel(guild)
                await self.refresh_board(guild)
                await self.refresh_wanted_board(guild)
                await self.refresh_cell_cards(guild)
            except Exception as exc:
                print(f"[PRISON] ❌ on_ready {guild.id}: {type(exc).__name__}: {exc}")
        if not self.release_loop.is_running():
            self.release_loop.start()
        if not self.board_loop.is_running():
            self.board_loop.start()
        if not self.card_loop.is_running():
            self.card_loop.start()
        if not self.visit_loop.is_running():
            self.visit_loop.start()

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        """أي روم جديدة كتولي مخبيّة على السجناء ديركت."""
        role = self.prisoner_role(channel.guild)
        if role is None or self.is_prison_area(channel):
            return
        await self._apply_hidden(channel, role)

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ):
        """شي حد بدّل الصلاحيات يدوياً → كنرجعوها."""
        role = self.prisoner_role(after.guild)
        if role is None:
            return
        if self.is_prison_area(after):
            return
        if after.overwrites_for(role).view_channel is False:
            return
        await self._apply_hidden(after, role)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """خرج من السيرفر باش يهرب من السجن؟ كيرجع للزنزانة ديركت."""
        record = self.store.inmate(member.guild.id, member.id)
        if not record:
            return
        prisoner = self.prisoner_role(member.guild)
        if prisoner is None:
            return
        self._suppress_role_guard.add(member.id)
        try:
            await member.edit(roles=[prisoner], reason=f"{REASON_TAG}: rejoin while jailed")
        except (discord.Forbidden, discord.HTTPException):
            try:
                await member.add_roles(prisoner, reason=f"{REASON_TAG}: rejoin while jailed")
            except (discord.Forbidden, discord.HTTPException):
                pass
        finally:
            self._suppress_role_guard.discard(member.id)
        await self._grant_cell_access(member)
        await self._post_cell_card(member, record)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """
        حارس: إلا شي حد عطى رول لسجين (ولا حيّد ليه Prisoner)، كنرجعو الحالة.
        هادشي هو اللي كيخلي السجن **حقيقي** — حتى ادمين ما يقدر يفكّو.

        ⭐ استثناء: إلا الأونر الحقيقي ديال السيرفر (guild.owner_id) هو اللي
        حيّد رول Prisoner يدويا من ديسكورد، البوت ما كيرجعوش — بالعكس كيدير
        إفراج رسمي كامل (يرجع الرولات الأصلية، كيحيد التسجيل، كيسجل فـ log).
        """
        if after.id in self._suppress_role_guard:
            return
        record = self.store.inmate(after.guild.id, after.id)
        if not record:
            return
        prisoner = self.prisoner_role(after.guild)
        if prisoner is None:
            return

        prisoner_removed = prisoner in before.roles and prisoner not in after.roles
        if prisoner_removed:
            try:
                async for entry in after.guild.audit_logs(
                    limit=3, action=discord.AuditLogAction.member_role_update
                ):
                    if entry.target is None or entry.target.id != after.id:
                        continue
                    age = datetime.now(entry.created_at.tzinfo) - entry.created_at
                    if age > timedelta(seconds=15):
                        break
                    if entry.user and entry.user.id == after.guild.owner_id:
                        await self.release(
                            after.guild, after.id,
                            reason="فك يدوي من طرف الاونر (حيّد رول Prisoner مباشرة من ديسكورد)",
                            actor=entry.user,
                        )
                        return
                    break
            except (discord.Forbidden, discord.HTTPException):
                pass

        me = after.guild.me
        top = me.top_role.position if me else 0
        extra = [
            role
            for role in after.roles
            if role != after.guild.default_role
            and role.id != prisoner.id
            and not role.managed
            and role.position < top
        ]
        has_prisoner = prisoner in after.roles

        if not extra and has_prisoner:
            return

        # خزّن أي رول جديد تعطى ليه باش يرجع ليه ملي يخرج
        if extra:
            saved = set(int(r) for r in record.get("roles", []))
            saved.update(role.id for role in extra)
            record["roles"] = sorted(saved)
            self.store.save()

        self._suppress_role_guard.add(after.id)
        try:
            await after.edit(roles=[prisoner], reason=f"{REASON_TAG}: enforce sentence")
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[PRISON] ⚠️ ما قدرتش نفرض الحكم على {after}: {exc}")
        finally:
            self._suppress_role_guard.discard(after.id)

    async def cog_unload(self):
        self.release_loop.cancel()
        self.board_loop.cancel()
        self.card_loop.cancel()
        self.visit_loop.cancel()


# ═══════════════════════════════════════════════════════
# ║        API عام: كيستعملوه باقي الـ Cogs               ║
# ═══════════════════════════════════════════════════════

async def imprison_member(
    bot: commands.Bot,
    member: discord.Member,
    *,
    offense_key: str = "manual",
    seconds: Optional[int] = None,
    reason: str = "",
    actor: Optional[discord.abc.User] = None,
    cell: Optional[str] = None,
    announce_channel: Optional[discord.abc.Messageable] = None,
) -> dict:
    """
    نقطة الدخول الموحدة. أي مكان فالبوت كان كيدير kick/ban/mute
    ولّى كيعيط على هادي.

    مثال:
        from cogs.prison import imprison_member
        await imprison_member(bot, member, offense_key="ban", reason="...")
    """
    cog = bot.get_cog("PrisonSystem")
    if cog is None:
        return {"ok": False, "error": "PrisonSystem ماشي محمّلة."}
    return await cog.imprison(
        member,
        offense_key=offense_key,
        seconds=seconds,
        reason=reason,
        actor=actor,
        cell=cell,
        announce_channel=announce_channel,
    )


def prison_cog(bot: commands.Bot) -> Optional[PrisonSystem]:
    return bot.get_cog("PrisonSystem")


async def setup(bot: commands.Bot):
    bot.add_view(PrisonerCardView())      # persistent: كيخدم حتى بعد ريستارت
    bot.add_view(ComplaintReviewView())   # persistent: أزرار قبول/رفض الشكايات
    bot.add_view(VisitPanelView())        # persistent: بانل غرفة الزيارات
    await bot.add_cog(PrisonSystem(bot))
    print("✅ Prison System: السجن واجد — الرولات، الزنازن الصوتية، الزيارات، العدادات الحية")
