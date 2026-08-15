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
    CELL_RANK,
    CELL_KEYS,
    CHANNEL_NAMES,
    COMPLAINT_MAX_TARGETS,
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
    WARDEN_MAX_SECONDS,
    WARDEN_ROLE_COLOR,
    WARDEN_ROLE_NAME,
    PrisonStore,
    cell_for_penalty,
    complaint_route_for_cell,
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
    """غير Warden وOwner عندهم بانل مراقبة الزيارات."""
    return cog.is_server_owner(member, member.guild) or cog.is_warden(member)


async def _open_complaint_flow(interaction: discord.Interaction) -> None:
    """المسار المشترك لزر الشكاية فبطاقة السجين وفبانل الزنزانة."""
    cog = interaction.client.get_cog("PrisonSystem")
    if cog is None or interaction.guild is None:
        await interaction.response.send_message("❌ النظام ماشي متاح دابا.", ephemeral=True)
        return
    if not cog.store.is_inmate(interaction.guild.id, interaction.user.id):
        await interaction.response.send_message(
            "❌ غير السجناء لي كيقدرو يطلبو التدخل.", ephemeral=True
        )
        return
    if cog.store.in_solitary(interaction.guild.id, interaction.user.id):
        await interaction.response.send_message(
            "❌ نتا دابا فالانفرادي وما عندكش زملاء فنفس الزنزانة.", ephemeral=True
        )
        return

    left = cog.store.complaint_cooldown_left(interaction.guild.id, interaction.user.id)
    if left > 0:
        await interaction.response.send_message(
            f"⏳ صبر — تقدر تطلب تدخل جديد بعد **{format_duration(left)}**.",
            ephemeral=True,
        )
        return

    author_record = cog.store.inmate(interaction.guild.id, interaction.user.id) or {}
    author_cell = author_record.get("cell", "holding")
    others = [
        uid
        for uid, record in cog.store.inmates(interaction.guild.id).items()
        if int(uid) != interaction.user.id
        and record.get("cell", "holding") == author_cell
        and not cog.store.in_solitary(interaction.guild.id, int(uid))
    ]
    if not others:
        await interaction.response.send_message(
            "🕊️ ماكاين حتى سجين آخر معاك فنفس الزنزانة.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        "🆘 اختار من **1 حتى 10** ديال السجناء اللي دارو المشكل.\n"
        "البوت غادي يقبل غير اللي معاك دابا فنفس الزنزانة:",
        view=ComplaintTargetView(),
        ephemeral=True,
    )


class PrisonerCardView(discord.ui.View):
    """
    بطاقة السجين: طلب تدخل داخل الزنزانة + الوقت الباقي **دابا بالثانية**.
    persistent (timeout=None + custom_id) باش يخدم حتى بعد ريستارت البوت.
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="طلب تدخل / شكاية",
        emoji="🆘",
        style=discord.ButtonStyle.danger,
        custom_id="ggmw9:prison:complain",
        row=0,
    )
    async def complain(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _open_complaint_flow(interaction)

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


class CellHelpView(discord.ui.View):
    """بانل ثابتة فالروم النصية ديال كل زنزانة."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="طلب تدخل / شكاية",
        emoji="🆘",
        style=discord.ButtonStyle.danger,
        custom_id="ggmw9:prison:cell-help",
    )
    async def request_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await _open_complaint_flow(interaction)


class ComplaintTargetSelect(discord.ui.UserSelect):
    """Searchable select: كيخدم حتى إلا كانو عشرات السجناء فنفس الزنزانة."""

    def __init__(self):
        super().__init__(
            placeholder="اختار المشكي عليهم (من نفس الزنزانة)…",
            min_values=1,
            max_values=COMPLAINT_MAX_TARGETS,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ComplaintModal([int(member.id) for member in self.values])
        )


class ComplaintTargetView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(ComplaintTargetSelect())


class ComplaintModal(discord.ui.Modal, title="🆘 طلب تدخل داخل الزنزانة"):
    def __init__(self, target_ids: list[int]):
        super().__init__()
        self.target_ids = target_ids
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
            interaction.user, self.target_ids, str(self.reason.value).strip()
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result['error']}", ephemeral=True)
            return
        route = result["route"]
        await interaction.followup.send(
            f"✅ الشكاية **#{result['complaint']['id']}** توصلات.\n"
            + (
                "👮 غادي يشوفها الـ**Warden** والـ**Owner**."
                if route == "warden"
                else "👑 هاد الزنزانة من اختصاص **الـOwner بوحدو**."
            )
            + "\n\n⏳ غادي توصلك النتيجة فـDM.",
            ephemeral=True,
        )


class ComplaintReviewView(discord.ui.View):
    """
    أزرار القرار. persistent: الشكاية كتتلقا عبر message_id،
    والاختصاص كيتفحص فكل ضغطة (Warden لـHolding، Owner لكل المستويات).
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
        return isinstance(interaction.user, discord.Member) and cog.can_handle_complaint(
            interaction.user, complaint
        )

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
                "❌ غير الـ**Owner** يقدر يحسم شكايات Cell Block وMaximum Security.",
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
        async with cog.complaint_lock(interaction.guild.id, cid):
            complaint = cog.store.complaints(interaction.guild.id).get(cid)
            if complaint is None or complaint.get("status") != "pending":
                await interaction.followup.send(
                    "⚠️ شي مسؤول حسم الشكاية قبلك.", ephemeral=True
                )
                return
            if not self._may_handle(interaction, cog, complaint):
                await interaction.followup.send(
                    "❌ الاختصاص تبدل؛ هاد القرار خاص الـOwner.", ephemeral=True
                )
                return
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
        if cog is None or interaction.guild is None:
            await interaction.response.send_message("❌ النظام ماشي متاح.", ephemeral=True)
            return
        complaint = cog.store.complaints(interaction.guild.id).get(self.complaint_id)
        if complaint is None or complaint.get("status") != "pending":
            await interaction.response.send_message("⚠️ الشكاية تحسمات.", ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not cog.can_handle_complaint(
            interaction.user, complaint
        ):
            await interaction.response.send_message(
                "❌ ما عندكش الاختصاص باش تحسم هاد الشكاية.", ephemeral=True
            )
            return

        seconds = SOLITARY_DEFAULT_SECONDS
        raw = str(self.duration.value or "").strip()
        if raw:
            parsed = parse_duration(raw)
            if parsed is None or parsed <= 0:
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

        await interaction.response.defer(ephemeral=True, thinking=True)
        async with cog.complaint_lock(interaction.guild.id, self.complaint_id):
            complaint = cog.store.complaints(interaction.guild.id).get(self.complaint_id)
            if complaint is None or complaint.get("status") != "pending":
                await interaction.followup.send("⚠️ شي مسؤول حسم الشكاية قبلك.", ephemeral=True)
                return
            if not cog.can_handle_complaint(interaction.user, complaint):
                await interaction.followup.send(
                    "❌ الاختصاص تبدل؛ هاد القرار خاص الـOwner دابا.", ephemeral=True
                )
                return

            target_ids = cog.store.complaint_target_ids(complaint)
            if not target_ids:
                await interaction.followup.send(
                    "❌ الشكاية ما فيها حتى مشكي عليه صالح.", ephemeral=True
                )
                return
            targets: list[discord.Member] = []
            invalid: list[str] = []
            is_owner = cog.is_server_owner(interaction.user, interaction.guild)
            for target_id in target_ids:
                member = interaction.guild.get_member(target_id)
                record = cog.store.inmate(interaction.guild.id, target_id)
                if member is None or record is None:
                    invalid.append(f"<@{target_id}> (خرج من السيرفر/السجن)")
                    continue
                if cog.store.in_solitary(interaction.guild.id, target_id):
                    invalid.append(f"{member.mention} (راه فالانفرادي)")
                    continue
                if not is_owner and record.get("cell", "holding") != "holding":
                    invalid.append(f"{member.mention} (طلع من Holding)")
                    continue
                targets.append(member)

            if invalid or len(targets) != len(target_ids):
                details = ", ".join(invalid)[:1200] or "اللائحة تبدلات"
                await interaction.followup.send(
                    "❌ ما قدرناش ننفذ القرار حيث تبدلات حالة شي سجين:\n"
                    f"{details}\n\nراجع الشكاية كـOwner إلا تبدل المستوى.",
                    ephemeral=True,
                )
                return

            available = SOLITARY_MAX_ROOMS - cog.store.solitary_count(interaction.guild.id)
            if available < len(targets):
                await interaction.followup.send(
                    f"❌ خاص **{len(targets)}** روم انفرادية وباقي غير **{available}**.",
                    ephemeral=True,
                )
                return

            note = str(self.note.value or "").strip()
            reason = f"شكاية #{self.complaint_id}: {complaint['reason']}" + (
                f" • {note}" if note else ""
            )
            created: list[tuple[discord.Member, dict]] = []
            for target in targets:
                result = await cog.send_to_solitary(
                    target,
                    seconds=seconds,
                    reason=reason,
                    actor=interaction.user,
                    complaint_id=int(self.complaint_id),
                )
                if not result.get("ok"):
                    # All-or-nothing: إلى فشلت روم وحدة كنرجعو اللي تصاوبو قبلها.
                    for created_member, _created_result in created:
                        await cog.release_from_solitary(
                            interaction.guild,
                            created_member.id,
                            reason=f"إلغاء تنفيذ جزئي للشكاية #{self.complaint_id}",
                        )
                    await interaction.followup.send(
                        f"❌ التنفيذ تلغى كامل حيث وقعات مشكلة: {result['error']}",
                        ephemeral=True,
                    )
                    return
                created.append((target, result))

            cog.store.resolve_complaint(
                interaction.guild.id,
                self.complaint_id,
                status="approved",
                handler_id=interaction.user.id,
                result={
                    "targets": [member.id for member, _result in created],
                    "seconds": seconds,
                    "channels": [result["channel"].id for _member, result in created],
                },
            )

        author = interaction.guild.get_member(int(complaint["author"]))
        if author:
            await cog._dm(
                author,
                discord.Embed(
                    title="✅ الشكاية ديالك تقبلات",
                    description=(
                        f"الشكاية **#{self.complaint_id}** تقبلات.\n"
                        f"**{len(created)}** من المشكي عليهم تنقل كل واحد منهم "
                        f"لروم انفرادية مستقلة لمدة "
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
                    f"🔗 عزل **{format_duration(seconds)}**\n"
                    + "\n".join(
                        f"• {member.mention} → {result['channel'].mention}"
                        for member, result in created
                    )[:900]
                ),
                inline=False,
            )
            await interaction.message.edit(embed=embed, view=None)
        except (AttributeError, IndexError, discord.HTTPException):
            pass

        await interaction.followup.send(
            "✅ تنفذ القرار، وكل سجين تحط فروم انفرادية مستقلة:\n"
            + "\n".join(
                f"• {member.mention} → {result['channel'].mention}"
                for member, result in created
            ),
            ephemeral=True,
        )


# ═══════════════════════════════════════════════════════
# ║          الزيارات — الواجهة (UI) ديال الغرفة           ║
# ═══════════════════════════════════════════════════════

class VisitStaffView(discord.ui.View):
    """أي View كيرث من هادي = Warden/Owner بوحدهم."""

    def __init__(self, timeout: Optional[float] = 180):
        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cog = interaction.client.get_cog("PrisonSystem")
        if cog is None or not isinstance(interaction.user, discord.Member):
            await _reply(interaction, "❌ النظام ماشي متاح دابا.")
            return False
        if not _is_visit_staff(cog, interaction.user):
            await _reply(interaction, "❌ هاد البانل خاصة بـ Warden وOwner بوحدهم.")
            return False
        return True


class VisitRequestPrisonerSelect(discord.ui.Select):
    """الزائر كيختار السجين، والدعوة كتمشي للسجين باش هو اللي يقرر."""

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
        result = await cog.request_visit(
            interaction.guild,
            prisoner_id=prisoner_id,
            visitor_id=self.visitor_id,
            actor=interaction.user,
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
            return
        note = "" if result.get("dm") else "\n📨 الـDM ديالو مسدودة — تصاوبات ليه روم دعوة خاصة ومؤقتة."
        await interaction.followup.send(
            f"✅ تبعثات الدعوة لـ {member.mention} باش يوافق على الزيارة."
            f"{note}\n⏳ عندو {format_duration(VISIT_INVITE_TIMEOUT_SECONDS)} باش يجاوب.",
            ephemeral=True,
        )


class VisitRequestPrisonerView(discord.ui.View):
    def __init__(self, cog, guild: discord.Guild, visitor_id: int):
        super().__init__(timeout=180)
        self.add_item(VisitRequestPrisonerSelect(cog, guild, visitor_id))


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
            interaction.guild, self.values[0], reason="سدها Warden/Owner يدويا", actor=interaction.user
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
        else:
            await interaction.followup.send("✅ تسدات الزيارة ورجع السجين لزنزانتو.", ephemeral=True)


class VisitEndView(VisitStaffView):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__(timeout=180)
        self.add_item(VisitEndSelect(cog, guild))


class PrisonerVisitInviteView(discord.ui.View):
    """
    دعوة مبعوثة **للسجين**: هو بوحدو اللي يقدر يقبل أو يرفض قبل ما تحل الروم.
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
        result = await self.cog.accept_visit(guild, self.visit_id, prisoner_id=self.prisoner_id)
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
            if result.get("terminal"):
                self._lock()
                await self._sync_message(interaction)
                await self.cog.decline_visit(
                    guild, self.visit_id, reason=str(result.get("error") or "الدعوة ما بقاتش صالحة")
                )
                self.stop()
            return
        channel = result["channel"]
        await interaction.followup.send(
            f"✅ قبلتي الزيارة! دخل هنا: {channel.mention}", ephemeral=True
        )
        self._lock()
        await self._sync_message(interaction)
        await self.cog.cleanup_visit_invite_channel(guild, self.visit_id)
        self.stop()

    @discord.ui.button(
        label="رفض",
        emoji="❌",
        style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:visit:prisoner_decline",
    )
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = self.cog.bot.get_guild(self.guild_id)
        self._lock()
        await self._sync_message(interaction)
        await _reply(interaction, "🚫 رفضتي الزيارة.")
        if guild is not None:
            await self.cog.decline_visit(guild, self.visit_id, reason="رفض السجين الدعوة")
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
    البانل العامة الثابتة: فيها غير طلب زيارة، وكتخدم حتى بعد restart.
    """

    def __init__(self):
        super().__init__(timeout=None)

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

        if cog.store.is_inmate(interaction.guild.id, interaction.user.id):
            await _reply(interaction, "❌ ما يمكنش للسجين يطلب زيارة — خاصك تستنى الزوار.")
            return
        if cog.store.active_visit_for_visitor(interaction.guild.id, interaction.user.id):
            await _reply(interaction, "❌ عندك زيارة جارية ولا معلّقة أصلاً.")
            return
        await interaction.response.send_message(
            "🔒 اختار صاحبك المسجون اللي بغيتي تزور:",
            view=VisitRequestPrisonerView(cog, interaction.guild, interaction.user.id),
            ephemeral=True,
        )


class VisitManagementPanelView(VisitStaffView):
    """بانل منفصلة ومخفية: Warden وOwner بوحدهم."""

    def __init__(self):
        super().__init__(timeout=None)

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
        self._complaint_locks: dict[tuple[int, str], asyncio.Lock] = {}
        # باش on_member_update ما يتصارعش مع العمليات ديالنا
        self._suppress_role_guard: set[int] = set()
        self._ready_done = False
        # تتبّع الرسائل المتتالية ديال كل سجين فزنزانتو — باش نكشفو Spam
        # ونصعّدو العقوبة أوتوماتيكيا. المفتاح: (guild_id, user_id).
        self._cell_spam_tracker: dict[tuple[int, int], list[int]] = {}
        # آخر روم عامة كتب فيها العضو؛ كتستعمل باش يتقفل عليه فردياً وقت الاعتقال.
        self._last_non_prison_message_channel: dict[tuple[int, int], int] = {}

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

    def complaint_lock(self, guild_id: int, complaint_id: str) -> asyncio.Lock:
        """كيمنع جوج مسؤولين يقبلو نفس الشكاية فنفس اللحظة."""
        key = (int(guild_id), str(complaint_id))
        lock = self._complaint_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._complaint_locks[key] = lock
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

    def visit_admin_channel(self, guild: discord.Guild):
        return self.prison_channel(guild, "visit_admin")

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
        ids.update(
            int(v.get("invite_channel_id") or 0) for v in record.get("visits", {}).values()
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
            if channel.id in {
                int(visit.get("channel_id") or 0),
                int(visit.get("invite_channel_id") or 0),
            }:
                return True
        name = str(getattr(channel, "name", ""))
        return name.startswith(SOLITARY_PREFIX) or name.startswith(VISIT_CHANNEL_PREFIX)

    def is_warden(self, member: discord.Member) -> bool:
        role = self.warden_role(member.guild)
        return bool(role and role in member.roles)

    def can_handle_complaint(self, member: discord.Member, complaint: dict) -> bool:
        """Owner كيتحكم فكلشي؛ Warden غير فشكايات Holding Cell."""
        if self.is_server_owner(member, member.guild):
            return True
        return bool(
            complaint.get("route") == "warden"
            and complaint.get("cell") == "holding"
            and self.is_warden(member)
        )

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
        # حتى روم الزيارة المؤقتة ما كيدخلوش ليها؛ التحكم فيها كيبقى من البانل
        # الخاصة بـWarden/Owner. التحكم الفعلي محسوب بالرول ديال Warden فمنطق البوت،
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
            # 🌍 الروم العامة للزوار فيها غير زر طلب الزيارة.
            # السجناء ما كيشوفوهاش؛ الدعوة كتوصل للسجين فالـDM/الروم الخاصة.
            overwrites[guild.default_role] = discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=False,
                add_reactions=False,
                create_public_threads=False,
                create_private_threads=False,
            )
            overwrites[prisoner] = discord.PermissionOverwrite(
                view_channel=False,
                read_messages=False,
                read_message_history=False,
                send_messages=False,
                add_reactions=False,
                create_public_threads=False,
                create_private_threads=False,
            )
        elif key == "visit_admin":
            # 🔐 بانل المراقبة فشانيل بوحدها: Warden + Owner فقط.
            overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False)
            warden_role = self.warden_role(guild)
            if warden_role:
                overwrites[warden_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=False,
                    add_reactions=False,
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
        elif key == "complaints":
            # مكتب التدخل ديال Holding: Owner + Warden بوحدهم.
            overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False)
            warden_role = self.warden_role(guild)
            if warden_role:
                overwrites[warden_role] = discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=False,
                    add_reactions=False,
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
        elif key in CELL_KEYS:
            # السجين كيشوف غير زنزانتو بالـmember overwrite.
            # Warden عندو سلطة فـHolding فقط؛ Block/Maximum مخبيين عليه صراحة.
            overwrites[prisoner] = discord.PermissionOverwrite(view_channel=False)
            warden_role = self.warden_role(guild)
            if warden_role:
                if key == "holding":
                    overwrites[warden_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        read_messages=True,
                        read_message_history=True,
                        send_messages=True,
                        manage_messages=False,
                    )
                else:
                    overwrites[warden_role] = discord.PermissionOverwrite(
                        view_channel=False,
                        read_messages=False,
                        read_message_history=False,
                        send_messages=False,
                    )
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
          • الـWarden: دخول وتكلم غير فـHolding؛ الباقي Owner بوحدو.
          • السجين: بلا صلاحية على مستوى الرول؛ الوصول الفردي فـ _grant_cell_access.
        """
        overwrites = dict(self._category_overwrites(guild))
        warden = self.warden_role(guild)
        if warden:
            if key == "holding":
                overwrites[warden] = discord.PermissionOverwrite(
                    view_channel=True,
                    read_message_history=True,
                    send_messages=True,
                    connect=True,
                    speak=True,
                    stream=True,
                    use_voice_activation=True,
                )
            else:
                overwrites[warden] = discord.PermissionOverwrite(
                    view_channel=False,
                    read_message_history=False,
                    send_messages=False,
                    connect=False,
                    speak=False,
                    stream=False,
                )
        prisoner = self.prisoner_role(guild)
        if prisoner:
            overwrites[prisoner] = discord.PermissionOverwrite(
                view_channel=False,
                read_message_history=False,
                send_messages=False,
                connect=False,
            )
        return overwrites

    def _visit_voice_overwrites(
        self, guild: discord.Guild, prisoner: discord.Member, visitor: discord.Member
    ) -> dict:
        """
        فويس الزيارة خاص بالسجين والزائر فقط. الصلاحيات ما كتتورّتش من الكاتيكوري
        باش Warden/Admin/Mod ما يقدروش يدخلو ويقطعو عليهم الزيارة.
        """
        blocked = discord.PermissionOverwrite(
            view_channel=False, connect=False, speak=False, stream=False,
        )
        overwrites = {guild.default_role: blocked}
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                move_members=True,
                manage_channels=True,
                manage_permissions=True,
            )
        for role_id in (self.admin_role_id, self.moderator_role_id):
            role = guild.get_role(role_id) if role_id else None
            if role:
                overwrites[role] = blocked
        warden = self.warden_role(guild)
        if warden:
            overwrites[warden] = blocked
        prisoner_role = self.prisoner_role(guild)
        if prisoner_role:
            overwrites[prisoner_role] = discord.PermissionOverwrite(view_channel=False, connect=False)
        full = discord.PermissionOverwrite(
            view_channel=True, connect=True, speak=True, use_voice_activation=True,
        )
        overwrites[prisoner] = full
        overwrites[visitor] = full
        return overwrites

    def _visit_invite_overwrites(
        self, guild: discord.Guild, prisoner: discord.Member
    ) -> dict:
        """Fallback خاص إلا كانت DM ديال السجين مسدودة: البوت والسجين بوحدهم."""
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            prisoner: discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=False,
                add_reactions=False,
            ),
        }
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                read_messages=True,
                read_message_history=True,
                send_messages=True,
                manage_messages=True,
                manage_channels=True,
                manage_permissions=True,
            )
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
        await self.publish_cell_help_panels(guild)
        await self.publish_visit_panel(guild)
        await self.publish_visit_admin_panel(guild)
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

    @staticmethod
    def _penalty_total(record: dict) -> int:
        """كيهاجر السجلات القديمة وكيعطي مجموع العقوبات اللي تحسبات على السجين."""
        record.setdefault("discipline_log", [])
        record.setdefault("cell_history", [])
        if "penalty_seconds_total" in record:
            return int(record.get("penalty_seconds_total", 0) or 0)
        sentence = int(record.get("sentence", 0) or 0)
        if sentence < 0:
            total = -1
        else:
            total = max(0, sentence) + sum(
                max(0, int(item.get("seconds", 0) or 0))
                for item in record.get("extended", [])
            )
        record["penalty_seconds_total"] = total
        return total

    @staticmethod
    def _add_discipline_event(
        record: dict,
        *,
        reason: str,
        seconds: int,
        offense: str,
        actor_id: int,
    ) -> None:
        log = record.setdefault("discipline_log", [])
        log.append(
            {
                "at": now_ts(),
                "offense": offense,
                "reason": (reason or "مخالفة جديدة")[:400],
                "seconds": int(seconds),
                "cell": record.get("cell", "holding"),
                "by": int(actor_id),
            }
        )
        record["discipline_log"] = log[-50:]

    def _required_cell(self, record: dict, minimum_cell: str = "holding") -> str:
        current = record.get("cell", "holding")
        target = cell_for_penalty(self._penalty_total(record), minimum_cell)
        return current if CELL_RANK.get(current, 0) >= CELL_RANK.get(target, 0) else target

    async def _grant_cell_access(self, member: discord.Member, *, move_voice: bool = True) -> None:
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
                    else:
                        await channel.set_permissions(
                            member,
                            overwrite=discord.PermissionOverwrite(
                                view_channel=False,
                                read_messages=False,
                                read_message_history=False,
                                send_messages=False,
                            ),
                            reason=f"{REASON_TAG}: hide other cell",
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
                                read_message_history=True,
                                # يقدر يكتب غير رسائل عادية فـChat المدمج ديال فويس زنزانتو.
                                send_messages=True,
                                send_tts_messages=False,
                                attach_files=False,
                                embed_links=False,
                                add_reactions=False,
                                mention_everyone=False,
                                create_public_threads=False,
                                create_private_threads=False,
                                send_messages_in_threads=False,
                                use_external_emojis=False,
                                use_external_stickers=False,
                                connect=True,
                                speak=True,
                                use_voice_activation=True,
                                stream=False,
                            ),
                            reason=f"{REASON_TAG}: assign cell voice",
                        )
                        target_voice = voice_channel
                    else:
                        await voice_channel.set_permissions(
                            member,
                            overwrite=discord.PermissionOverwrite(
                                view_channel=False,
                                read_message_history=False,
                                send_messages=False,
                                connect=False,
                                speak=False,
                            ),
                            reason=f"{REASON_TAG}: hide other cell voice",
                        )
                except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                    pass

        # Visit Room وVisit Control مخبيين على السجين حتى بmember overwrite مباشر.
        # هاد المنع كيغلب أي Permission فردية قديمة كانت عندو.
        for key in ("visits", "visit_admin"):
            visit_channel = self.prison_channel(member.guild, key)
            if visit_channel is not None:
                try:
                    await visit_channel.set_permissions(
                        member,
                        overwrite=HIDE_OVERWRITE,
                        reason=f"{REASON_TAG}: hide visit channels from inmate",
                    )
                except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                    pass

        # 🔊 نقل أوتوماتيكي: إلا كان السجين دابا فشي فويس، نرجعوه لفويس زنزانتو.
        if move_voice and target_voice is not None:
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

        # حيد المنع الفردي ديال الزيارة؛ الصلاحيات العامة كترجع تتحكم من بعد الإفراج.
        for key in ("visits", "visit_admin"):
            visit_channel = self.prison_channel(guild, key)
            if visit_channel is not None:
                try:
                    await visit_channel.set_permissions(
                        target, overwrite=None, reason=f"{REASON_TAG}: release visit access"
                    )
                except (discord.Forbidden, discord.HTTPException, discord.NotFound):
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

    def _pre_prison_origin_channels(
        self,
        member: discord.Member,
        announce_channel: Optional[discord.abc.Messageable] = None,
    ) -> list:
        """آخر روم كتب فيها + الفويس اللي كان داخل ليه قبل الاعتقال."""
        guild = member.guild
        candidates = []
        tracked_id = self._last_non_prison_message_channel.get((guild.id, member.id), 0)
        tracked = guild.get_channel(int(tracked_id or 0))
        if tracked is not None:
            candidates.append(tracked)
        if member.voice and member.voice.channel:
            candidates.append(member.voice.channel)
        if (
            announce_channel is not None
            and getattr(announce_channel, "guild", None) == guild
            and hasattr(announce_channel, "set_permissions")
        ):
            candidates.append(announce_channel)

        result = []
        seen: set[int] = set()
        for channel in candidates:
            channel_id = int(getattr(channel, "id", 0) or 0)
            if not channel_id or channel_id in seen or self.is_prison_area(channel):
                continue
            if not hasattr(channel, "overwrites_for") or not hasattr(channel, "set_permissions"):
                continue
            seen.add(channel_id)
            result.append(channel)
        return result

    @staticmethod
    def _has_member_overwrite(channel, member: discord.Member) -> bool:
        return any(
            not isinstance(target, discord.Role) and int(getattr(target, "id", 0)) == member.id
            for target in channel.overwrites
        )

    async def _lock_pre_prison_channels(
        self, member: discord.Member, record: dict, channels: Iterable
    ) -> int:
        """كيحفظ Permission الفردية الأصلية وكيطبق منع كامل ما يقدرش Role Allow يغلبو."""
        snapshots = record.setdefault("pre_prison_overwrites", [])
        existing = {int(item.get("channel_id", 0) or 0) for item in snapshots}
        changed = False
        locked = 0
        for channel in channels:
            channel_id = int(getattr(channel, "id", 0) or 0)
            snapshot = None
            if channel_id not in existing:
                previous = channel.overwrites_for(member)
                allow, deny = previous.pair()
                snapshot = {
                    "channel_id": channel_id,
                    "had_overwrite": self._has_member_overwrite(channel, member),
                    "allow": int(allow.value),
                    "deny": int(deny.value),
                }
            try:
                await channel.set_permissions(
                    member,
                    overwrite=HIDE_OVERWRITE,
                    reason=f"{REASON_TAG}: lock pre-prison channel",
                )
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                continue
            locked += 1
            if snapshot is not None:
                snapshots.append(snapshot)
                existing.add(channel_id)
                changed = True
        if changed:
            self.store.save()
        return locked

    async def _enforce_pre_prison_locks(self, member: discord.Member, record: dict) -> None:
        channels = []
        for snapshot in record.get("pre_prison_overwrites", []):
            channel = member.guild.get_channel(int(snapshot.get("channel_id", 0) or 0))
            if channel is not None and not self.is_prison_area(channel):
                channels.append(channel)
        await self._lock_pre_prison_channels(member, record, channels)

    async def _restore_pre_prison_overwrites(
        self, member: discord.Member, record: dict
    ) -> tuple[int, list[int]]:
        """ملي يخرج كيرجع آخر روم لنفس member overwrite اللي كانت قبل السجن."""
        restored = 0
        failed: list[int] = []
        for snapshot in record.get("pre_prison_overwrites", []):
            channel_id = int(snapshot.get("channel_id", 0) or 0)
            channel = member.guild.get_channel(channel_id)
            if channel is None:
                continue
            overwrite = None
            if bool(snapshot.get("had_overwrite")):
                overwrite = discord.PermissionOverwrite.from_pair(
                    discord.Permissions(int(snapshot.get("allow", 0) or 0)),
                    discord.Permissions(int(snapshot.get("deny", 0) or 0)),
                )
            try:
                await channel.set_permissions(
                    member,
                    overwrite=overwrite,
                    reason=f"{REASON_TAG}: restore pre-prison permissions",
                )
                restored += 1
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                failed.append(channel_id)
        return restored, failed

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
            cell_key = cell_for_penalty(duration, cell_key)

            existing = self.store.inmate(guild.id, member.id)
            if existing:
                # كاين أصلاً فالسجن → كنزيدو المدة بدل ما نعاودو من الصفر.
                return await self.extend_sentence(
                    member,
                    extra_seconds=duration,
                    reason=reason or offense["label"],
                    actor=actor,
                    offense_key=offense_key,
                    minimum_cell=cell_key,
                )

            origin_channels = self._pre_prison_origin_channels(member, announce_channel)
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

        await self._lock_pre_prison_channels(member, record, origin_channels)
        self._last_non_prison_message_channel.pop((guild.id, member.id), None)
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
        offense_key: str = "manual",
        minimum_cell: str = "holding",
    ) -> dict:
        record = self.store.inmate(member.guild.id, member.id)
        if not record:
            return {"ok": False, "error": "هاد العضو ماشي فالسجن."}

        added = int(extra_seconds)
        actor_id = int(getattr(actor, "id", 0) or 0)
        event_reason = reason or self.store.offense(member.guild.id, offense_key)["label"]
        old_cell = record.get("cell", "holding")
        previous_total = self._penalty_total(record)

        if added < 0:
            record["until"] = -1
            record["sentence"] = -1
            record["penalty_seconds_total"] = -1
        else:
            if int(record.get("until", 0)) >= 0:
                base = max(int(record["until"]), now_ts())
                record["until"] = base + added
            if int(record.get("sentence", 0)) >= 0:
                record["sentence"] = int(record.get("sentence", 0) or 0) + added
            if previous_total >= 0:
                record["penalty_seconds_total"] = previous_total + added

        record.setdefault("extended", []).append(
            {
                "at": now_ts(),
                "seconds": added,
                "by": actor_id,
                "reason": event_reason[:400],
                "offense": offense_key,
            }
        )
        record["last_offense"] = offense_key
        self._add_discipline_event(
            record,
            reason=event_reason,
            seconds=added,
            offense=offense_key,
            actor_id=actor_id,
        )

        required_cell = self._required_cell(record, minimum_cell)
        should_escalate = CELL_RANK.get(required_cell, 0) > CELL_RANK.get(old_cell, 0)
        in_solitary = bool(self.store.in_solitary(member.guild.id, member.id))
        if should_escalate and in_solitary:
            record["pending_cell"] = required_cell
        self.store.save()

        if should_escalate and not in_solitary:
            transfer = await self.transfer_cell(
                member,
                new_cell=required_cell,
                reason=f"تراكم/زيادة العقوبة — {event_reason}",
                actor=actor,
                notice_seconds=added,
            )
            record = transfer.get("record", record)
        elif not in_solitary:
            await self._post_cell_card(member, record)

        embed = discord.Embed(
            title="⏳ تمديد الحكم",
            description=f"{member.mention} تزادت ليه المدة.",
            color=discord.Color.orange(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="➕ الزيادة", value=format_duration(added), inline=True)
        embed.add_field(
            name="🔓 الخروج",
            value=(f"<t:{record['until']}:R>" if int(record.get("until", 0)) > 0 else "♾️ مؤبّد"),
            inline=True,
        )
        embed.add_field(name="📝 السبب", value=event_reason[:1000], inline=False)
        if should_escalate:
            embed.add_field(
                name="🚨 التصعيد",
                value=f"{_cell_display(old_cell)} → {_cell_display(required_cell)}",
                inline=False,
            )
        await self._log(member.guild, embed)
        return {"ok": True, "record": record, "escalated": should_escalate}

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
        if int(record.get("sentence", 0)) >= 0:
            record["sentence"] = max(0, int(record.get("sentence", 0) or 0) - int(seconds))
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
        notice_seconds: Optional[int] = None,
        move_voice: bool = True,
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

        old_message_id = int(record.get("cell_message_id") or 0)
        if old_cell != new_cell and old_message_id:
            await self._delete_cell_card_at(guild, old_cell, old_message_id)
            record["cell_message_id"] = 0

        record["cell"] = new_cell
        if extra_seconds and int(record.get("until", 0)) >= 0:
            penalty_total = self._penalty_total(record)
            base = max(int(record["until"]), now_ts())
            record["until"] = base + int(extra_seconds)
            if int(record.get("sentence", 0)) >= 0:
                record["sentence"] = int(record.get("sentence", 0) or 0) + int(extra_seconds)
            if penalty_total >= 0:
                record["penalty_seconds_total"] = penalty_total + int(extra_seconds)
            record.setdefault("extended", []).append(
                {
                    "at": now_ts(),
                    "seconds": int(extra_seconds),
                    "by": int(getattr(actor, "id", 0) or 0),
                    "reason": (reason or "تصعيد الزنزانة")[:400],
                    "offense": "cell_escalation",
                }
            )
            self._add_discipline_event(
                record,
                reason=reason or "تصعيد الزنزانة",
                seconds=int(extra_seconds),
                offense="cell_escalation",
                actor_id=int(getattr(actor, "id", 0) or 0),
            )
        record.setdefault("cell_history", []).append(
            {
                "at": now_ts(),
                "from": old_cell,
                "to": new_cell,
                "reason": (reason or "تصعيد")[:400],
                "by": int(getattr(actor, "id", 0) or 0),
            }
        )
        record["cell_history"] = record["cell_history"][-25:]
        record.pop("pending_cell", None)
        self.store.save()
        reported_seconds = int(extra_seconds) if notice_seconds is None else int(notice_seconds)

        await self._grant_cell_access(member, move_voice=move_voice)
        await self._post_cell_card(member, record)
        await self._post_cell_escalation_notice(
            member,
            record,
            old_cell=old_cell,
            new_cell=new_cell,
            reason=reason or "تصعيد العقوبة",
            added_seconds=reported_seconds,
            actor=actor,
        )

        embed = discord.Embed(
            title="🚨 تصعيد العقوبة — نقل زنزانة",
            description=f"{member.mention} تنقل من **{_cell_display(old_cell)}** لـ **{_cell_display(new_cell)}**.",
            color=discord.Color.dark_orange(),
            timestamp=datetime.now(),
        )
        if reported_seconds:
            embed.add_field(name="➕ الزيادة", value=format_duration(reported_seconds), inline=True)
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
                + (f"⏳ تزادت ليك **{format_duration(reported_seconds)}**.\n" if reported_seconds else "")
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
                penalty_total = self._penalty_total(record)
                base = max(int(record["until"]), now_ts())
                record["until"] = base + extra_seconds
                if int(record.get("sentence", 0)) >= 0:
                    record["sentence"] = int(record.get("sentence", 0) or 0) + extra_seconds
                if penalty_total >= 0:
                    record["penalty_seconds_total"] = penalty_total + extra_seconds
                record.setdefault("extended", []).append(
                    {
                        "at": now_ts(),
                        "seconds": extra_seconds,
                        "by": 0,
                        "reason": reason[:400],
                        "offense": "cell_escalation",
                    }
                )
            self._add_discipline_event(
                record,
                reason=reason,
                seconds=extra_seconds,
                offense="cell_escalation",
                actor_id=0,
            )
            self.store.save()
            await self._post_cell_card(member, record)
            await self._post_cell_escalation_notice(
                member,
                record,
                old_cell=current_cell,
                new_cell=current_cell,
                reason=reason,
                added_seconds=extra_seconds,
                actor=None,
            )
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
        (الروم النصية أو Chat المدمج ديال الفويس) → كيتصعّد مباشرة لزنزانة
        أقسح، بلا حاجة لتدخل الإدارة.
        """
        if message.author.bot or message.guild is None:
            return
        member = message.author
        if not isinstance(member, discord.Member):
            return

        guild = message.guild
        if isinstance(message.channel, (discord.TextChannel, discord.VoiceChannel)):
            if not self.is_prison_area(message.channel):
                self._last_non_prison_message_channel[(guild.id, member.id)] = message.channel.id

        record = self.store.inmate(guild.id, member.id)
        if not record:
            return
        if self.store.in_solitary(guild.id, member.id):
            return  # الحبس الانفرادي عندو منطق ديالو الخاص

        cell_key = record.get("cell", "holding")
        cell_channel = self.prison_channel(guild, cell_key)
        cell_voice = self.cell_voice_channel(guild, cell_key)
        allowed_cell_chat_ids = {
            channel.id for channel in (cell_channel, cell_voice) if channel is not None
        }
        if message.channel.id not in allowed_cell_chat_ids:
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
            _restored_channels, failed_channels = await self._restore_pre_prison_overwrites(
                member, record
            )
            if failed_channels:
                print(
                    f"[PRISON] ⚠️ فشل إرجاع صلاحيات {member.id} فالرومز: {failed_channels}"
                )
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
        embed.add_field(
            name="⚖️ مجموع العقوبات المتراكمة",
            value=format_duration(self._penalty_total(record)),
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
        discipline_log = record.get("discipline_log") or []
        if discipline_log:
            latest = discipline_log[-1]
            embed.add_field(
                name="📌 آخر سبب تأديبي",
                value=str(latest.get("reason") or "بلا سبب")[:500],
                inline=False,
            )

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

    async def _post_cell_escalation_notice(
        self,
        member: discord.Member,
        record: dict,
        *,
        old_cell: str,
        new_cell: str,
        reason: str,
        added_seconds: int,
        actor: Optional[discord.abc.User] = None,
    ) -> None:
        """كيعلن فالزنزانة الجديدة علاش السجين وصل لهاد الدرجة."""
        channel = self.prison_channel(member.guild, new_cell)
        if channel is None:
            return

        escalated = CELL_RANK.get(new_cell, 0) > CELL_RANK.get(old_cell, 0)
        title = (
            f"🚨 تصعيد إلى {_cell_display(new_cell)}"
            if escalated
            else f"🔄 تحديث وضع السجين فـ {_cell_display(new_cell)}"
        )
        embed = discord.Embed(
            title=title,
            description=(
                f"{member.mention} وصل لهاد الدرجة بسبب تراكم المخالفات والعقوبات."
                if escalated
                else f"تحدث الوضع التأديبي ديال {member.mention}."
            ),
            color=(discord.Color.dark_red() if new_cell == "max" else discord.Color.dark_orange()),
            timestamp=datetime.now(),
        )
        embed.add_field(name="⬅️ الزنزانة السابقة", value=_cell_display(old_cell), inline=True)
        embed.add_field(name="➡️ الزنزانة الحالية", value=_cell_display(new_cell), inline=True)
        embed.add_field(
            name="⚖️ مجموع العقوبات",
            value=format_duration(self._penalty_total(record)),
            inline=True,
        )
        embed.add_field(name="📌 سبب هاد التصعيد", value=reason[:1000], inline=False)
        if added_seconds:
            embed.add_field(
                name="➕ آخر عقوبة تزادت",
                value=format_duration(int(added_seconds)),
                inline=True,
            )

        history_lines: list[str] = []
        for item in record.get("discipline_log", [])[-5:]:
            offense_key = str(item.get("offense") or "manual")
            offense = self.store.offense(member.guild.id, offense_key)
            offense_label = (
                "سلوك مخالف داخل الزنزانة"
                if offense_key == "cell_escalation"
                else offense["label"]
            )
            seconds = int(item.get("seconds", 0) or 0)
            duration = format_duration(seconds)
            history_lines.append(
                f"• **{offense_label}** — {str(item.get('reason') or 'بلا سبب')[:180]}"
                f" ({duration})"
            )
        if history_lines:
            embed.add_field(
                name="🧾 الأسباب اللي وصلاتو لهاد المستوى",
                value="\n".join(history_lines)[:1024],
                inline=False,
            )
        embed.add_field(
            name="👮 القرار",
            value=(
                actor.mention
                if isinstance(actor, (discord.Member, discord.User))
                else "النظام الآلي"
            ),
            inline=True,
        )
        embed.set_footer(text="ما كيبان للسجين دابا غير هاد المستوى من الزنازن")
        try:
            await channel.send(content=member.mention, embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def refresh_cell_cards(self, guild: discord.Guild) -> int:
        """كيحدّث بطاقة كل سجين فالزنزانة ديالو."""
        updated = 0
        for uid, record in list(self.store.inmates(guild.id).items()):
            if self.store.in_solitary(guild.id, int(uid)):
                continue
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

    async def _delete_cell_card_at(
        self, guild: discord.Guild, cell_key: str, message_id: int
    ) -> None:
        if not message_id:
            return
        channel = self.prison_channel(guild, cell_key)
        if channel is None:
            return
        try:
            message = await channel.fetch_message(message_id)
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    async def _delete_cell_card(self, guild: discord.Guild, record: dict) -> None:
        await self._delete_cell_card_at(
            guild,
            record.get("cell", "holding"),
            int(record.get("cell_message_id") or 0),
        )

    # ═══════════════════════════════════════════════════
    # ║        5. الشكايات + الحبس الانفرادي              ║
    # ═══════════════════════════════════════════════════

    def complaint_route(self, cell: str) -> str:
        """
        🔀 تقسيم الاختصاص:
          • Holding Cell → الـWarden أو الـOwner
          • Cell Block / Maximum Security → **الـOwner بوحدو**
        """
        return complaint_route_for_cell(cell)

    async def submit_complaint(
        self, author: discord.Member, target_ids: Iterable[int] | int, reason: str
    ) -> dict:
        guild = author.guild
        reason = str(reason or "").strip()

        if not self.store.is_inmate(guild.id, author.id):
            return {"ok": False, "error": "غير السجناء لي كيقدرو يشكيو."}
        if self.store.in_solitary(guild.id, author.id):
            return {"ok": False, "error": "ما تقدرش تدير شكاية جماعية من الانفرادي."}
        if len(reason) < 10:
            return {"ok": False, "error": "شرح أشنو وقع بوضوح (10 حروف على الأقل)."}

        raw_targets = [target_ids] if isinstance(target_ids, int) else list(target_ids)
        targets = self.store.complaint_target_ids({"targets": raw_targets})
        if not targets:
            return {"ok": False, "error": "خاصك تختار سجين واحد على الأقل."}
        if len(targets) > COMPLAINT_MAX_TARGETS:
            return {
                "ok": False,
                "error": f"تقدر تختار حتى {COMPLAINT_MAX_TARGETS} ديال السجناء فالطلب الواحد.",
            }
        if author.id in targets:
            return {"ok": False, "error": "ما تقدرش تشكي من راسك."}

        author_record = self.store.inmate(guild.id, author.id) or {}
        author_cell = author_record.get("cell", "holding")
        for target_id in targets:
            target_record = self.store.inmate(guild.id, target_id)
            if target_record is None:
                return {"ok": False, "error": f"<@{target_id}> ماشي فالسجن."}
            if self.store.in_solitary(guild.id, target_id):
                return {"ok": False, "error": f"<@{target_id}> راه أصلاً فالانفرادي."}
            if target_record.get("cell", "holding") != author_cell:
                return {
                    "ok": False,
                    "error": "تقدر تشكي غير من السجناء اللي معاك فنفس الزنزانة دابا.",
                }

        left = self.store.complaint_cooldown_left(guild.id, author.id)
        if left > 0:
            return {
                "ok": False,
                "error": f"صبر شوية — تقدر تشكي من جديد بعد **{format_duration(left)}**.",
            }
        if len(self.store.pending_complaints(guild.id)) >= COMPLAINT_MAX_PENDING:
            return {"ok": False, "error": "كاين بزاف ديال الشكايات المعلقة. صبر حتى يتحسمو."}

        # ما نقبلوش طلب جديد كيتقاطع مع طلب معلق من نفس الشاكي.
        requested = set(targets)
        for record in self.store.pending_complaints(guild.id).values():
            if int(record["author"]) != author.id:
                continue
            if requested.intersection(self.store.complaint_target_ids(record)):
                return {"ok": False, "error": "عندك شكاية معلقة على شي واحد من هاد اللائحة."}

        route = self.complaint_route(author_cell)
        complaint = self.store.add_complaint(
            guild.id,
            author_id=author.id,
            target_ids=targets,
            reason=reason,
            route=route,
            cell=author_cell,
        )
        posted = await self._post_complaint(guild, complaint)
        if not posted:
            self.store.complaints(guild.id).pop(str(complaint["id"]), None)
            self.store.guild(guild.id).setdefault("complaint_cooldown", {}).pop(
                str(author.id), None
            )
            self.store.save()
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
        author_text = author.mention if author else f"<@{int(complaint['author'])}>"
        target_lines: list[str] = []
        for target_id in self.store.complaint_target_ids(complaint):
            target = guild.get_member(target_id)
            target_record = self.store.inmate(guild.id, target_id) or {}
            offense = self.store.offense(guild.id, target_record.get("offense", "manual"))
            target_text = target.mention if target else f"<@{target_id}>"
            target_lines.append(
                f"• {target_text} — Case #{target_record.get('case', '?')} — {offense['label']}"
            )

        embed = discord.Embed(
            title=f"🆘 طلب تدخل #{complaint['id']} — تسنّا القرار",
            description=(
                f"**الشاكي:** {author_text}\n"
                f"**الزنزانة وقت الحادث:** {_cell_display(complaint.get('cell', 'holding'))}\n\n"
                "**المشكي عليهم:**\n" + "\n".join(target_lines)[:1600]
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="📝 السبب", value=f"```{str(complaint['reason'])[:900]}```", inline=False
        )
        embed.add_field(
            name="🔀 الاختصاص",
            value=(
                "👮 Warden + 👑 Owner (Holding Cell)"
                if route == "warden"
                else "👑 **Owner بوحدو**"
            ),
            inline=True,
        )
        embed.add_field(
            name="🔗 القرار",
            value=(
                "**قبول** → كل مشكي عليه كيمشي لروم انفرادية مستقلة.\n"
                "**رفض** → الشكاية كتطيح، والشاكي كياخد تنبيه."
            ),
            inline=False,
        )
        if author:
            embed.set_thumbnail(url=author.display_avatar.url)
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
        """روم مستقلة: السجين + Owner؛ Warden غير إلا كان أصلها Holding."""
        overwrites = dict(self._category_overwrites(guild))
        blocked = discord.PermissionOverwrite(
            view_channel=False,
            read_messages=False,
            read_message_history=False,
            send_messages=False,
        )
        prisoner = self.prisoner_role(guild)
        if prisoner:
            overwrites[prisoner] = blocked
        for role_id in (self.admin_role_id, self.moderator_role_id):
            role = guild.get_role(role_id) if role_id else None
            if role:
                overwrites[role] = blocked
        record = self.store.inmate(guild.id, member.id) or {}
        warden = self.warden_role(guild)
        if warden:
            if record.get("cell", "holding") == "holding":
                overwrites[warden] = discord.PermissionOverwrite(
                    view_channel=True,
                    read_messages=True,
                    read_message_history=True,
                    send_messages=True,
                    manage_messages=False,
                )
            else:
                overwrites[warden] = blocked
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
            pending_cell = record.get("pending_cell")
            self.store.save()
            if (
                pending_cell in CELL_KEYS
                and CELL_RANK.get(pending_cell, 0) > CELL_RANK.get(record.get("cell", "holding"), 0)
            ):
                await self.transfer_cell(
                    member,
                    new_cell=pending_cell,
                    reason="تصعيد تلقائي كان تسنّى حتى سالا الحبس الانفرادي",
                    actor=None,
                )
                record = self.store.inmate(guild.id, user_id) or record
            else:
                record.pop("pending_cell", None)
                self.store.save()
                await self._grant_cell_access(member)
                await self._post_cell_card(member, record)
            await self._dm(
                member,
                discord.Embed(
                    title="🔓 خرجتي من الانفرادي",
                    description=(
                        f"{reason}\nرجعتي لـ **{_cell_display(record.get('cell', 'holding'))}**."
                    ),
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
    # ║             5أ. بانلات التدخل فالزنازن             ║
    # ═══════════════════════════════════════════════════

    async def publish_cell_help_panels(self, guild: discord.Guild) -> None:
        """بانل فالروم النصية وفالـChat المدمج ديال فويس كل زنزانة."""
        record = self.store.guild(guild.id)
        message_ids = record.setdefault("cell_help_message_ids", {})
        voice_message_ids = record.setdefault("voice_help_message_ids", {})

        for cell in CELL_KEYS:
            channel = self.prison_channel(guild, cell)
            if not isinstance(channel, discord.TextChannel):
                continue

            authority = (
                "👮 الـWarden أو 👑 الـOwner"
                if cell == "holding"
                else "👑 الـOwner بوحدو"
            )
            embed = discord.Embed(
                title=f"🆘 طلب تدخل — {_cell_display(cell)}",
                description=(
                    "إلا وقع صداع، تهديد، مضاربة ولا مشكل مع سجين آخر، "
                    "ضغط على الزر لتحت.\n\n"
                    "1️⃣ اختار سجين واحد أو عدة سجناء من نفس الزنزانة.\n"
                    "2️⃣ شرح أشنو وقع بوضوح.\n"
                    "3️⃣ المسؤول المختص كيقبل الطلب أو يرفضو.\n"
                    "4️⃣ إلا تقبل، كل مسؤول على المشكل كيمشي لانفرادي مستقل ومؤقت."
                ),
                color=(discord.Color.orange() if cell == "holding" else discord.Color.dark_red()),
            )
            embed.add_field(name="⚖️ شكون كيحسم؟", value=authority, inline=False)
            embed.add_field(
                name="🔒 الخصوصية",
                value="الاختيار والسبب كيبانو غير ليك، والقرار كيمشي للمسؤول المختص.",
                inline=False,
            )
            embed.set_footer(
                text="نفس البانل كاينة فالروم النصية وفـOpen Chat ديال فويس الزنزانة"
            )

            message = None
            message_id = int(message_ids.get(cell) or 0)
            if message_id:
                try:
                    message = await channel.fetch_message(message_id)
                    await message.edit(embed=embed, view=CellHelpView())
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    message = None
            if message is None:
                try:
                    message = await channel.send(embed=embed, view=CellHelpView())
                    message_ids[cell] = message.id
                    self.store.save()
                except (discord.Forbidden, discord.HTTPException):
                    continue
            if message is not None and not message.pinned:
                try:
                    await message.pin(reason=f"{REASON_TAG}: cell help panel")
                except (discord.Forbidden, discord.HTTPException):
                    pass

            # Discord عندو Text Chat مدمج داخل الـVoice. كنستعمل PartialMessageable
            # حيت discord.py 2.3 ما كيعطيش send() مباشرة على VoiceChannel model.
            voice_channel = self.cell_voice_channel(guild, cell)
            if not isinstance(voice_channel, discord.VoiceChannel):
                continue
            voice_chat = self.bot.get_partial_messageable(
                voice_channel.id,
                guild_id=guild.id,
                type=discord.ChannelType.voice,
            )
            voice_message = None
            voice_message_id = int(voice_message_ids.get(cell) or 0)
            if voice_message_id:
                try:
                    voice_message = await voice_chat.fetch_message(voice_message_id)
                    await voice_message.edit(embed=embed, view=CellHelpView())
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    voice_message = None
            if voice_message is None:
                try:
                    voice_message = await voice_chat.send(
                        content=(
                            "🔐 الوصول لهاد الـVoice كيتعطى لكل سجين فردياً حسب الـID. "
                            "منين كتضغط، الاختيار والسبب كيبقاو سريين عندك."
                        ),
                        embed=embed,
                        view=CellHelpView(),
                    )
                    voice_message_ids[cell] = voice_message.id
                    self.store.save()
                except (discord.Forbidden, discord.HTTPException):
                    pass

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
                "🔔 ضغط على **طلب زيارة** واختار السجين اللي بغيتي تزور.\n"
                "📨 الدعوة كتمشي للسجين، وهو اللي كيقبلها ولا يرفضها.\n\n"
                f"⏱️ إلا قبل، كتتحل ليكم روم خاصة لمدة **{format_duration(VISIT_DEFAULT_SECONDS)}**.\n"
                "🔒 الروم كتكون غير للزائر والسجين، وكتتسد أوتوماتيكيا منين تسالي المدة."
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

    async def publish_visit_admin_panel(self, guild: discord.Guild) -> None:
        """بانل منفصلة فـ visit-control، مخفية على الجميع ما عدا Warden وOwner."""
        channel = self.visit_admin_channel(guild)
        if channel is None:
            category = self.prison_category(guild)
            if category is None:
                return
            try:
                channel = await guild.create_text_channel(
                    CHANNEL_NAMES["visit_admin"],
                    category=category,
                    overwrites=self._channel_overwrites(guild, "visit_admin"),
                    reason=f"{REASON_TAG}: create private visit control",
                )
                record = self.store.guild(guild.id)
                record["channels"]["visit_admin"] = channel.id
                self.store.save()
            except (discord.Forbidden, discord.HTTPException):
                return
        record = self.store.guild(guild.id)
        embed = discord.Embed(
            title="👮 مراقبة الزيارات",
            description=(
                "📋 **الزيارات الجارية** — شوف الزيارات المعلقة والجارية.\n"
                "📴 **سد زيارة** — سالي زيارة جارية قبل وقتها.\n\n"
                "🔐 هاد البانل كتبان غير لـ **Warden** و **Owner**."
            ),
            color=discord.Color.dark_teal(),
        )
        message_id = int(record.get("visits_admin_message_id") or 0)
        if message_id:
            try:
                message = await channel.fetch_message(message_id)
                await message.edit(embed=embed, view=VisitManagementPanelView())
                return
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        try:
            message = await channel.send(embed=embed, view=VisitManagementPanelView())
            record["visits_admin_message_id"] = message.id
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

    async def accept_visit(self, guild: discord.Guild, visit_id, *, prisoner_id: int) -> dict:
        """السجين هو الوحيد اللي يقدر يوافق على طلب الزيارة."""
        record = self.store.visit(guild.id, visit_id)
        if not record or record.get("status") != "pending":
            return {"ok": False, "error": "هاد الدعوة ماشي صالحة (تلغات ولا تجاوب عليها قبل)."}
        if int(record.get("prisoner_id", 0)) != int(prisoner_id):
            return {"ok": False, "error": "هاد الدعوة ماشي ليك."}
        return await self._activate_visit(guild, visit_id, record)

    async def request_visit(
        self, guild: discord.Guild, *, prisoner_id: int, visitor_id: int, actor
    ) -> dict:
        """
        الزائر كيطلب زيارة، والدعوة كتبعث **للسجين نفسو** باش يوافق أو يرفض.
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
            category = self.prison_category(guild)
            if category is None:
                self.store.remove_visit(guild.id, record["id"])
                return {"ok": False, "error": "الـDM مسدودة وكاتيكوري السجن ماكايناش."}
            try:
                channel = await guild.create_text_channel(
                    f"📨┃visit-invite-{record['id']}",
                    category=category,
                    overwrites=self._visit_invite_overwrites(guild, prisoner),
                    reason=f"{REASON_TAG}: private visit invite",
                )
                self.store.set_visit_invite_channel(guild.id, record["id"], channel.id)
                message = await channel.send(content=prisoner.mention, embed=embed, view=view)
                view.invite_message = message
            except (discord.Forbidden, discord.HTTPException):
                if 'channel' in locals() and channel is not None:
                    try:
                        await channel.delete(reason=f"{REASON_TAG}: failed visit invite")
                    except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                        pass
                self.store.remove_visit(guild.id, record["id"])
                return {"ok": False, "error": "ما قدرتش نوصل الدعوة للسجين فـDM ولا فروم خاصة."}

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
        """كتصاوب روم الفويس الخاصة وكتبدا العداد من لحظة موافقة السجين."""
        prisoner_id = int(record["prisoner_id"])
        visitor_id = int(record["visitor_id"])

        if not self.store.is_inmate(guild.id, prisoner_id):
            return {
                "ok": False,
                "terminal": True,
                "error": "السجين خرج من السجن قبل الزيارة.",
            }
        if self.store.in_solitary(guild.id, prisoner_id):
            return {
                "ok": False,
                "terminal": True,
                "error": "السجين تنقل للحبس الانفرادي — ما يقدرش يستقبلك دابا.",
            }

        prisoner = guild.get_member(prisoner_id)
        visitor = guild.get_member(visitor_id)
        category = self.prison_category(guild)
        if prisoner is None or visitor is None or category is None:
            return {
                "ok": False,
                "terminal": True,
                "error": "شي حد (ولا الكاتيكوري) ماشي متاح دابا.",
            }

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

        notice = discord.Embed(
            title="🔊 بدات الزيارة",
            description=(
                f"دخل للروم الخاصة: {channel.mention}\n"
                f"⏱️ غادي تسالي <t:{int(record['until'])}:R>."
            ),
            color=discord.Color.green(),
        )
        await asyncio.gather(self._dm(prisoner, notice), self._dm(visitor, notice))

        return {"ok": True, "channel": channel, "record": record}

    async def cleanup_visit_invite_channel(self, guild: discord.Guild, visit_id) -> bool:
        """كيمسح روم الدعوة الخاصة ديال fallback من بعد القبول/الرفض/انتهاء المهلة."""
        record = self.store.visit(guild.id, visit_id)
        if not record:
            return False
        channel_id = int(record.get("invite_channel_id") or 0)
        if not channel_id:
            return True
        channel = guild.get_channel(channel_id)
        if channel is not None:
            try:
                await channel.delete(reason=f"{REASON_TAG}: visit invite closed")
            except discord.NotFound:
                pass
            except (discord.Forbidden, discord.HTTPException):
                return False
        self.store.set_visit_invite_channel(guild.id, visit_id, 0)
        return True

    async def decline_visit(
        self, guild: discord.Guild, visit_id, *, reason: str = "مرفوضة"
    ) -> dict:
        await self.cleanup_visit_invite_channel(guild, visit_id)
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

        await self.cleanup_visit_invite_channel(guild, visit_id)
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
        """كتلغي الدعوات القديمة وكتسد الزيارات اللي سالات مدتها أوتوماتيكيا."""
        for guild in list(self.bot.guilds):
            try:
                for visit_id, _record in self.store.expired_pending_visits(guild.id):
                    await self.decline_visit(
                        guild, visit_id, reason="⏳ السجين ما جاوبش فالوقت المحدد"
                    )
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
                await self.publish_cell_help_panels(guild)
                await self.publish_visit_panel(guild)
                await self.publish_visit_admin_panel(guild)
                await self.refresh_board(guild)
                await self.refresh_wanted_board(guild)
                for user_id in list(self.store.inmates(guild.id)):
                    member = guild.get_member(int(user_id))
                    if member is None:
                        continue
                    record = self.store.inmate(guild.id, member.id)
                    if record is None:
                        continue
                    await self._enforce_pre_prison_locks(member, record)
                    required_cell = self._required_cell(record, record.get("cell", "holding"))
                    if self.store.in_solitary(guild.id, member.id):
                        if CELL_RANK.get(required_cell, 0) > CELL_RANK.get(
                            record.get("cell", "holding"), 0
                        ):
                            record["pending_cell"] = required_cell
                            self.store.save()
                        continue
                    active_visit = bool(self.store.active_visit_for_inmate(guild.id, member.id))
                    if CELL_RANK.get(required_cell, 0) > CELL_RANK.get(
                        record.get("cell", "holding"), 0
                    ):
                        await self.transfer_cell(
                            member,
                            new_cell=required_cell,
                            reason="تصعيد تلقائي حسب مجموع العقوبات المحفوظة",
                            actor=None,
                            move_voice=not active_visit,
                        )
                    else:
                        await self._grant_cell_access(member, move_voice=not active_visit)
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
        if after.overwrites_for(role).view_channel is not False:
            await self._apply_hidden(after, role)

        # حتى member-specific Allow ما يقدرش يحل آخر روم على سجين مازال معتاقل.
        for user_id, record in self.store.inmates(after.guild.id).items():
            if not any(
                int(item.get("channel_id", 0) or 0) == after.id
                for item in record.get("pre_prison_overwrites", [])
            ):
                continue
            member = after.guild.get_member(int(user_id))
            if member is None:
                continue
            overwrite = after.overwrites_for(member)
            if (
                overwrite.view_channel is False
                and overwrite.send_messages is False
                and overwrite.connect is False
            ):
                continue
            try:
                await after.set_permissions(
                    member,
                    overwrite=HIDE_OVERWRITE,
                    reason=f"{REASON_TAG}: enforce pre-prison room lock",
                )
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                pass

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
        await self._enforce_pre_prison_locks(member, record)
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
    bot.add_view(CellHelpView())          # persistent: بانل طلب التدخل فكل زنزانة
    bot.add_view(ComplaintReviewView())   # persistent: أزرار قبول/رفض الشكايات
    bot.add_view(VisitPanelView())        # persistent: بانل غرفة الزيارات
    bot.add_view(VisitManagementPanelView())  # persistent: Warden/Owner فقط
    await bot.add_cog(PrisonSystem(bot))
    print("✅ Prison System: السجن واجد — الرولات، الزنازن الصوتية، الزيارات، العدادات الحية")
