# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/prison_panel.py — 🔐 البانل ديال السجن          ║
═══════════════════════════════════════════════════════

  • البانل الكاملة = **Owner ديال السيرفر بوحدو** (guild.owner_id الحي).
  • الـ Warden (الشرطة) عندو بانل مصغّرة: غير أحكام خفيفة فـ holding-cell
    وبمدة قصوى محدودة، وما يقدرش يطلق سراح حتى واحد.
  • حتى ادمين ولا مود ماعندو حتى وصول — بحال Temp Rooms بالضبط.

كل الأزرار ephemeral، يعني حتى إلا شاف شي حد الرسالة ما يقدر يستعملها.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from cogs.prison_core import (
    AUTO_ACTION_LABELS,
    AUTO_RULE_TRIGGER_MAX,
    AUTO_RULE_TRIGGER_MIN,
    CELL_KEYS,
    CHANNEL_NAMES,
    DEFAULT_OFFENSES,
    SOLITARY_MAX_ROOMS,
    WARDEN_ALLOWED_CELLS,
    WARDEN_ALLOWED_SEVERITY,
    WARDEN_MAX_SECONDS,
    format_duration,
    now_ts,
    normalize_auto_rule_pattern,
    parse_duration,
    solitary_default_seconds,
    solitary_max_seconds,
)

CELL_LABELS = {
    "holding": "⛓️ Holding Cell (خفيف)",
    "block": "🔒 Cell Block (متوسط)",
    "max": "🚨 Maximum Security (قاسح)",
}

DISCORD_SELECT_PAGE_SIZE = 25
AUTO_RULE_EMBED_PAGE_SIZE = 8


def _clamp_page(page: int, total: int, page_size: int) -> tuple[int, int]:
    """كيعطي page وpage count صالحين حتى إلا تبدلات اللائحة وسط التفاعل."""
    pages = max(1, (max(0, int(total)) + page_size - 1) // page_size)
    return max(0, min(int(page), pages - 1)), pages


def _cog(interaction: discord.Interaction):
    return interaction.client.get_cog("PrisonSystem")


def _is_owner(interaction: discord.Interaction) -> bool:
    return bool(
        interaction.guild
        and interaction.user
        and interaction.user.id == interaction.guild.owner_id
    )


async def _deny(interaction: discord.Interaction, message: str) -> None:
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


# ═══════════════════════════════════════════════════════
# ║                  قواعد الوصول                        ║
# ═══════════════════════════════════════════════════════

class OwnerOnlyPrisonView(discord.ui.View):
    """أي View كيرث من هادي = Owner بوحدو."""

    def __init__(self, timeout: float = 300):
        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not _is_owner(interaction):
            await _deny(interaction, "❌ السجن كيتحكم فيه **Owner ديال السيرفر بوحدو**.")
            return False
        return True


class WardenScopedView(discord.ui.View):
    """Owner أو Warden — ولكن الصلاحيات كتتفحص مرة أخرى فكل عملية."""

    def __init__(self, timeout: float = 300):
        super().__init__(timeout=timeout)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        cog = _cog(interaction)
        if _is_owner(interaction):
            return True
        if cog and isinstance(interaction.user, discord.Member) and cog.is_warden(interaction.user):
            return True
        await _deny(interaction, "❌ هاد البانل خاصة بـ **Owner** و **Warden** بوحدهم.")
        return False


# ═══════════════════════════════════════════════════════
# ║                  1. سجن عضو                          ║
# ═══════════════════════════════════════════════════════

class ImprisonModal(discord.ui.Modal):
    def __init__(self, member: discord.Member, offense_key: str, warden_mode: bool):
        super().__init__(title=f"⛓️ سجن {member.display_name}"[:45])
        self.member = member
        self.offense_key = offense_key
        self.warden_mode = warden_mode

        cog = None  # كيتجاب فـ on_submit
        self.reason = discord.ui.TextInput(
            label="السبب",
            placeholder="مثال: سبام متكرر فـ general بعد 3 تحذيرات",
            required=True,
            max_length=300,
            style=discord.TextStyle.paragraph,
        )
        self.duration = discord.ui.TextInput(
            label="المدة (خليها خاوية = المدة الرسمية)",
            placeholder="مثال: 30m / 12h / 7d / 2w — ولا perm للمؤبد",
            required=False,
            max_length=32,
        )
        self.cell = discord.ui.TextInput(
            label="الزنزانة (holding / block / max)",
            placeholder="خليها خاوية = حسب القانون",
            required=False,
            max_length=16,
        )
        self.add_item(self.reason)
        self.add_item(self.duration)
        if not warden_mode:
            self.add_item(self.cell)

    async def on_submit(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        if cog is None:
            await _deny(interaction, "❌ PrisonSystem ماشي محمّلة.")
            return

        is_owner = _is_owner(interaction)
        offense = cog.store.offense(interaction.guild.id, self.offense_key)

        seconds = None
        raw_duration = str(self.duration.value or "").strip()
        if raw_duration:
            seconds = parse_duration(raw_duration)
            if seconds is None:
                await _deny(
                    interaction,
                    "❌ المدة ماشي صالحة. استعمل بحال `30m` / `12h` / `7d` / `2w` / `perm`.",
                )
                return

        cell = str(getattr(self, "cell", None) and self.cell.value or "").strip().lower() or None
        if cell and cell not in CELL_KEYS:
            await _deny(interaction, f"❌ الزنزانة خاصها تكون وحدة من: {', '.join(CELL_KEYS)}")
            return

        # ───── حدود الـ Warden ─────
        if not is_owner:
            if int(offense.get("severity", 1)) > WARDEN_ALLOWED_SEVERITY:
                await _deny(
                    interaction,
                    "❌ هاد المخالفة فوق الصلاحية ديالك. الـWarden كيدير غير الأحكام الخفيفة.",
                )
                return
            effective = seconds if seconds is not None else int(offense["seconds"])
            if effective < 0 or effective > WARDEN_MAX_SECONDS:
                await _deny(
                    interaction,
                    f"❌ أقصى مدة عندك هي **{format_duration(WARDEN_MAX_SECONDS)}**.",
                )
                return
            cell = WARDEN_ALLOWED_CELLS[0]
            if isinstance(self.member, discord.Member) and cog.is_warden(self.member):
                await _deny(interaction, "❌ ما تقدرش تسجن Warden آخر.")
                return
            if self.member.guild_permissions.administrator:
                await _deny(interaction, "❌ ما تقدرش تسجن شي حد فوق منك.")
                return

        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await cog.imprison(
            self.member,
            offense_key=self.offense_key,
            seconds=seconds,
            reason=str(self.reason.value or "").strip(),
            actor=interaction.user,
            cell=cell,
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
            return

        record = result["record"]
        until = int(record.get("until", 0))
        embed = discord.Embed(
            title="✅ تسجن",
            description=(
                f"**العضو:** {self.member.mention}\n"
                f"**المخالفة:** {offense['label']}\n"
                f"**المدة:** {format_duration(int(record['sentence']))}\n"
                f"**الزنزانة:** {CHANNEL_NAMES.get(record['cell'], record['cell'])}\n"
                f"**Case:** #{record['case']}\n"
                + (f"**الخروج:** <t:{until}:F> (<t:{until}:R>)" if until > 0 else "**مؤبّد ♾️**")
            ),
            color=discord.Color.dark_red(),
            timestamp=datetime.now(),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


def _sorted_offense_items(cog, guild: discord.Guild, warden_mode: bool = False):
    items = []
    for key, entry in sorted(
        cog.store.offenses(guild.id).items(),
        key=lambda item: (
            int(item[1].get("severity", 1)),
            int(item[1].get("seconds", 0)),
            str(item[1].get("label", "")).casefold(),
        ),
    ):
        if warden_mode and int(entry.get("severity", 1)) > WARDEN_ALLOWED_SEVERITY:
            continue
        items.append((key, entry))
    return items


class OffenseSelect(discord.ui.Select):
    def __init__(
        self,
        cog,
        guild: discord.Guild,
        member: discord.Member,
        warden_mode: bool,
        page: int = 0,
    ):
        self.cog = cog
        self.member = member
        self.warden_mode = warden_mode
        items = _sorted_offense_items(cog, guild, warden_mode)
        page, pages = _clamp_page(page, len(items), DISCORD_SELECT_PAGE_SIZE)
        start = page * DISCORD_SELECT_PAGE_SIZE
        options = [
            discord.SelectOption(
                label=entry["label"][:100],
                value=key,
                description=f"{format_duration(entry['seconds'])} • {entry.get('cell','holding')}"[:100],
            )
            for key, entry in items[start : start + DISCORD_SELECT_PAGE_SIZE]
        ]
        super().__init__(
            placeholder=f"اختار المخالفة… الصفحة {page + 1}/{pages}",
            options=options or [discord.SelectOption(label="—", value="manual")],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ImprisonModal(self.member, self.values[0], self.warden_mode)
        )


class OffenseSelectView(WardenScopedView):
    def __init__(
        self,
        cog,
        guild: discord.Guild,
        member: discord.Member,
        warden_mode: bool,
        page: int = 0,
    ):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.member = member
        self.warden_mode = warden_mode
        items = _sorted_offense_items(cog, guild, warden_mode)
        self.page, self.pages = _clamp_page(page, len(items), DISCORD_SELECT_PAGE_SIZE)
        self.add_item(OffenseSelect(cog, guild, member, warden_mode, self.page))
        self.previous_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.pages - 1

    async def _show_page(self, interaction: discord.Interaction, page: int):
        await interaction.response.edit_message(
            content=f"⚖️ **{self.member.display_name}** — اختار المخالفة:",
            view=OffenseSelectView(
                self.cog, self.guild, self.member, self.warden_mode, page
            ),
        )

    @discord.ui.button(label="السابق", emoji="⬅️", row=1)
    async def previous_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show_page(interaction, self.page - 1)

    @discord.ui.button(label="التالي", emoji="➡️", row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._show_page(interaction, self.page + 1)


class ImprisonMemberSelect(discord.ui.UserSelect):
    def __init__(self, warden_mode: bool):
        super().__init__(placeholder="اختار العضو اللي غادي تسجنو…", min_values=1, max_values=1)
        self.warden_mode = warden_mode

    async def callback(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        member = self.values[0]
        if not isinstance(member, discord.Member):
            member = interaction.guild.get_member(member.id)
        if member is None:
            await _deny(interaction, "❌ ما لقيتش هاد العضو فالسيرفر.")
            return
        if member.bot:
            await _deny(interaction, "❌ ما كنسجنوش البوتات.")
            return
        if member.id == interaction.guild.owner_id:
            await _deny(interaction, "❌ Owner ديال السيرفر محمي.")
            return
        if cog and cog.store.is_inmate(interaction.guild.id, member.id):
            await _deny(
                interaction,
                f"⚠️ {member.mention} راه أصلاً فالسجن. استعمل **Adjust Sentence** باش تزيد المدة.",
            )
            return

        await interaction.response.edit_message(
            content=f"⚖️ **{member.display_name}** — اختار المخالفة:",
            view=OffenseSelectView(cog, interaction.guild, member, self.warden_mode),
        )


class ImprisonFlowView(WardenScopedView):
    def __init__(self, warden_mode: bool):
        super().__init__()
        self.add_item(ImprisonMemberSelect(warden_mode))


# ═══════════════════════════════════════════════════════
# ║               2. إطلاق سراح (Owner فقط)              ║
# ═══════════════════════════════════════════════════════

class ReleaseSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild):
        self.cog = cog
        inmates = cog.store.inmates(guild.id)
        options: list[discord.SelectOption] = []
        for uid, record in list(inmates.items())[:25]:
            member = guild.get_member(int(uid))
            name = member.display_name if member else f"ID {uid}"
            until = int(record.get("until", 0))
            left = "مؤبّد" if until < 0 else format_duration(max(0, until - now_ts()))
            options.append(
                discord.SelectOption(
                    label=f"#{record.get('case','?')} • {name}"[:100],
                    value=str(uid),
                    description=f"باقي: {left} • {record.get('cell','holding')}"[:100],
                )
            )
        super().__init__(
            placeholder="اختار السجين اللي غادي تطلق سراحو…",
            options=options or [discord.SelectOption(label="السجن خاوي", value="none")],
            min_values=1,
            max_values=1,
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        if self.values[0] == "none" or cog is None:
            await _deny(interaction, "🕊️ السجن خاوي.")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await cog.release(
            interaction.guild,
            int(self.values[0]),
            reason="عفو من طرف الاونر",
            actor=interaction.user,
            outcome="pardoned",
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
            return
        restored = result.get("restored") or []
        await interaction.followup.send(
            f"🔓 تطلق السراح.\n**رولات ترجعات:** {len(restored)}"
            + (f"\n`{', '.join(restored)[:800]}`" if restored else ""),
            ephemeral=True,
        )


class ReleaseView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__()
        self.add_item(ReleaseSelect(cog, guild))


# ═══════════════════════════════════════════════════════
# ║              3. تعديل المدة (Owner فقط)              ║
# ═══════════════════════════════════════════════════════

class AdjustModal(discord.ui.Modal, title="⏳ تعديل مدة الحكم"):
    def __init__(self, user_id: int, display: str):
        super().__init__()
        self.user_id = user_id
        self.change = discord.ui.TextInput(
            label=f"المدة لـ {display}"[:45],
            placeholder="زيادة: 3d   |   نقصان: -12h   |   مؤبد: perm",
            required=True,
            max_length=32,
        )
        self.add_item(self.change)

    async def on_submit(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        member = interaction.guild.get_member(self.user_id)
        if cog is None or member is None:
            await _deny(interaction, "❌ ما لقيتش العضو فالسيرفر.")
            return

        raw = str(self.change.value or "").strip()
        negative = raw.startswith("-")
        seconds = parse_duration(raw.lstrip("+-"))
        if seconds is None:
            await _deny(interaction, "❌ المدة ماشي صالحة. مثال: `3d` ولا `-12h` ولا `perm`.")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        if seconds < 0:  # perm
            result = await cog.extend_sentence(
                member,
                extra_seconds=-1,
                reason="الحكم تبدل لمؤبد من طرف الاونر",
                actor=interaction.user,
                offense_key="severe",
                minimum_cell="max",
            )
            if not result.get("ok"):
                await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
                return
            await interaction.followup.send("♾️ الحكم ولّى **مؤبّد**.", ephemeral=True)
            return

        if negative:
            result = await cog.reduce_sentence(member, seconds=seconds, actor=interaction.user)
            verb = "تنقصات"
        else:
            result = await cog.extend_sentence(
                member, extra_seconds=seconds, reason="تعديل من الاونر", actor=interaction.user
            )
            verb = "تزادت"

        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result.get('error')}", ephemeral=True)
            return
        until = int(result["record"].get("until", 0))
        await interaction.followup.send(
            f"✅ المدة {verb} بـ **{format_duration(seconds)}**.\n"
            + (f"🔓 الخروج: <t:{until}:F> (<t:{until}:R>)" if until > 0 else "♾️ مؤبّد"),
            ephemeral=True,
        )


class AdjustSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild):
        inmates = cog.store.inmates(guild.id)
        options: list[discord.SelectOption] = []
        for uid, record in list(inmates.items())[:25]:
            member = guild.get_member(int(uid))
            name = member.display_name if member else f"ID {uid}"
            until = int(record.get("until", 0))
            left = "مؤبّد" if until < 0 else format_duration(max(0, until - now_ts()))
            options.append(
                discord.SelectOption(
                    label=f"#{record.get('case','?')} • {name}"[:100],
                    value=str(uid),
                    description=f"باقي: {left}"[:100],
                )
            )
        super().__init__(
            placeholder="اختار السجين…",
            options=options or [discord.SelectOption(label="السجن خاوي", value="none")],
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await _deny(interaction, "🕊️ السجن خاوي.")
            return
        member = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(
            AdjustModal(int(self.values[0]), member.display_name if member else "السجين")
        )


class AdjustView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__()
        self.add_item(AdjustSelect(cog, guild))


# ═══════════════════════════════════════════════════════
# ║          3.5 الحبس الانفرادي (Owner فقط)             ║
# ═══════════════════════════════════════════════════════

class SolitarySendModal(discord.ui.Modal, title="🔗 حبس انفرادي"):
    def __init__(self, user_id: int, display: str):
        super().__init__()
        self.user_id = user_id
        self.duration = discord.ui.TextInput(
            label=f"مدة العزل لـ {display}"[:45],
            placeholder="مثال: 2h — السقف كيتحسب حسب الزنزانة",
            required=False,
            max_length=16,
        )
        self.reason = discord.ui.TextInput(
            label="سبب العزل",
            placeholder="مثال: تعدّى على سجين آخر",
            style=discord.TextStyle.paragraph,
            required=True,
            max_length=300,
        )
        self.add_item(self.duration)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        member = interaction.guild.get_member(self.user_id)
        if cog is None or member is None:
            await _deny(interaction, "❌ ما لقيتش العضو.")
            return

        inmate = cog.store.inmate(interaction.guild.id, self.user_id) or {}
        cell = str(inmate.get("cell") or "holding")
        seconds = solitary_default_seconds(cell)
        maximum = solitary_max_seconds(cell)
        raw = str(self.duration.value or "").strip()
        if raw:
            parsed = parse_duration(raw)
            if parsed is None or parsed < 0:
                await _deny(interaction, "❌ المدة ماشي صالحة. مثال: `2h` ولا `45m`.")
                return
            seconds = parsed
        if seconds > maximum:
            await _deny(
                interaction,
                f"❌ أقصى مدة عزل فـ **{CELL_LABELS.get(cell, cell)}** هي "
                f"**{format_duration(maximum)}**.",
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await cog.send_to_solitary(
            member,
            seconds=seconds,
            reason=str(self.reason.value).strip(),
            actor=interaction.user,
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result['error']}", ephemeral=True)
            return
        await interaction.followup.send(
            f"🔗 {member.mention} تنقل للانفرادي — {result['channel'].mention}\n"
            f"⏱️ العزل يسالي بعد **{format_duration(int(result['record']['until']) - int(result['record']['since']))}**.",
            ephemeral=True,
        )


class SolitarySendSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild):
        options = []
        for uid, record in list(cog.store.inmates(guild.id).items())[:25]:
            if cog.store.in_solitary(guild.id, int(uid)):
                continue
            member = guild.get_member(int(uid))
            offense = cog.store.offense(guild.id, record.get("offense", "manual"))
            options.append(
                discord.SelectOption(
                    label=f"#{record.get('case','?')} • "
                          f"{member.display_name if member else uid}"[:100],
                    value=str(uid),
                    description=offense["label"][:100],
                )
            )
        super().__init__(
            placeholder="اختار سجين باش تعزلو…",
            options=options or [discord.SelectOption(label="ماكاين حتى سجين متاح", value="none")],
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await _deny(interaction, "ماكاين حتى سجين متاح للعزل.")
            return
        member = interaction.guild.get_member(int(self.values[0]))
        await interaction.response.send_modal(
            SolitarySendModal(int(self.values[0]), member.display_name if member else "السجين")
        )


class SolitaryReleaseSelect(discord.ui.UserSelect):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__(
            placeholder="🔓 إخراج يدوي من الانفرادي…",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        user_id = int(self.values[0].id)
        if not cog.store.in_solitary(interaction.guild.id, user_id):
            await _deny(interaction, "❌ هاد العضو ماشي فالحبس الانفرادي دابا.")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await cog.release_from_solitary(
            interaction.guild, user_id, reason="إخراج يدوي من طرف الـOwner"
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result['error']}", ephemeral=True)
            return
        if result.get("released_from_prison"):
            message = "🕊️ خرج من الانفرادي ومن السجن حيت الحكم الأصلي كان سالا. الروم والرول تمسحو."
        elif result.get("prison_release_error"):
            message = (
                "⚠️ خرج من الانفرادي والروم والرول تمسحو، ولكن الإفراج الكامل "
                f"تعطل: {result['prison_release_error']}"
            )
        else:
            message = "🔓 خرج يدوياً من الانفرادي، الروم والرول تمسحو، ورجع لزنزانتو."
        await interaction.followup.send(message, ephemeral=True)


class SolitaryView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__()
        self.add_item(SolitarySendSelect(cog, guild))
        self.add_item(SolitaryReleaseSelect(cog, guild))


# ═══════════════════════════════════════════════════════
# ║           4. إدارة الـ Warden (Owner فقط)            ║
# ═══════════════════════════════════════════════════════

class WardenAddSelect(discord.ui.UserSelect):
    def __init__(self):
        super().__init__(
            placeholder="اختار شكون غادي يولي Warden…", min_values=1, max_values=5
        )

    async def callback(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        role = cog.warden_role(interaction.guild) if cog else None
        if role is None:
            await _deny(interaction, "❌ رول Warden ماكاينش. دير **Setup / Repair** الأول.")
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        done, failed = [], []
        for user in self.values:
            member = interaction.guild.get_member(user.id)
            if member is None or member.bot:
                failed.append(f"{user} (ماشي عضو صالح)")
                continue
            if cog.store.is_inmate(interaction.guild.id, member.id):
                failed.append(f"{member.display_name} (راه سجين)")
                continue
            try:
                await member.add_roles(role, reason="GGMW9 Prison: grant Warden")
                done.append(member.mention)
            except (discord.Forbidden, discord.HTTPException) as exc:
                failed.append(f"{member.display_name} ({exc})")

        lines = []
        if done:
            lines.append(f"✅ ولاو Warden: {', '.join(done)}")
        if failed:
            lines.append(f"⚠️ ما تدارش: {', '.join(failed)[:800]}")
        await interaction.followup.send("\n".join(lines) or "ما تبدل والو.", ephemeral=True)


class WardenRemoveSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild):
        role = cog.warden_role(guild)
        members = list(role.members)[:25] if role else []
        super().__init__(
            placeholder="اختار شكون غادي تحيد ليه Warden…",
            options=[
                discord.SelectOption(label=m.display_name[:100], value=str(m.id))
                for m in members
            ]
            or [discord.SelectOption(label="ماكاين حتى Warden", value="none")],
            disabled=not members,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await _deny(interaction, "ماكاين حتى Warden.")
            return
        cog = _cog(interaction)
        role = cog.warden_role(interaction.guild)
        member = interaction.guild.get_member(int(self.values[0]))
        if role is None or member is None:
            await _deny(interaction, "❌ ما لقيتش العضو ولا الرول.")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await member.remove_roles(role, reason="GGMW9 Prison: revoke Warden")
            await interaction.followup.send(f"✅ تحيد Warden من {member.mention}.", ephemeral=True)
        except (discord.Forbidden, discord.HTTPException) as exc:
            await interaction.followup.send(f"❌ {exc}", ephemeral=True)


class WardenManageView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__()
        self.add_item(WardenAddSelect())
        self.add_item(WardenRemoveSelect(cog, guild))


# ═══════════════════════════════════════════════════════
# ║          5. تعديل القانون (Owner فقط)                ║
# ═══════════════════════════════════════════════════════

class OffenseEditModal(discord.ui.Modal, title="⚖️ تعديل مخالفة"):
    def __init__(self, key: str, entry: dict, page: int = 0):
        super().__init__()
        self.key = key
        self.page = page
        self.label_input = discord.ui.TextInput(
            label="الاسم", default=entry["label"], required=True, max_length=80
        )
        self.duration_input = discord.ui.TextInput(
            label="المدة (30m / 12h / 7d / 2w / perm)",
            default=_seconds_to_text(int(entry["seconds"])),
            required=True,
            max_length=32,
        )
        self.cell_input = discord.ui.TextInput(
            label="الزنزانة (holding / block / max)",
            default=entry.get("cell", "holding"),
            required=True,
            max_length=16,
        )
        self.add_item(self.label_input)
        self.add_item(self.duration_input)
        self.add_item(self.cell_input)

    async def on_submit(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        seconds = parse_duration(str(self.duration_input.value))
        cell = str(self.cell_input.value).strip().lower()
        if seconds is None:
            await _deny(interaction, "❌ المدة ماشي صالحة.")
            return
        if cell not in CELL_KEYS:
            await _deny(interaction, f"❌ الزنزانة خاصها تكون: {', '.join(CELL_KEYS)}")
            return

        severity = {"holding": 1, "block": 2, "max": 3}[cell]
        try:
            entry = cog.store.set_offense(
                interaction.guild.id,
                self.key,
                label=str(self.label_input.value).strip(),
                seconds=seconds,
                cell=cell,
                severity=severity,
            )
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await cog.refresh_rule_surfaces(interaction.guild)
        await interaction.followup.send(
            content="✅ تعدّل الحكم وتحدثات لوحة `prison-code`.",
            embed=offense_control_embed(self.key, entry),
            view=OffenseSelectedView(cog, interaction.guild, self.key, self.page),
            ephemeral=True,
        )


def _seconds_to_text(seconds: int) -> str:
    if seconds < 0:
        return "perm"
    for size, suffix in ((7 * 86400, "w"), (86400, "d"), (3600, "h"), (60, "m")):
        if seconds >= size and seconds % size == 0:
            return f"{seconds // size}{suffix}"
    return f"{max(1, seconds // 60)}m"


def offense_control_embed(key: str, entry: dict) -> discord.Embed:
    custom = bool(entry.get("custom", key not in DEFAULT_OFFENSES))
    embed = discord.Embed(
        title=f"⚖️ {entry.get('label', key)}",
        description=(
            f"**المدة:** {format_duration(int(entry.get('seconds', 3600)))}\n"
            f"**الزنزانة:** `{entry.get('cell', 'holding')}`\n"
            f"**النوع:** {'حكم مخصص' if custom else 'حكم أصلي'}\n"
            f"**المعرف الداخلي:** `{key}`"
        ),
        color=discord.Color.gold(),
    )
    embed.set_footer(text="تعديل المدة هنا كيطبق على السجن اليدوي وAuto Rules")
    return embed


class OffenseCreateModal(discord.ui.Modal, title="➕ إضافة حكم جديد"):
    def __init__(self, page: int = 0):
        super().__init__()
        self.page = page
        self.label_input = discord.ui.TextInput(
            label="اسم / وصف الحكم",
            placeholder="مثال: إزعاج متكرر بعد الإنذار",
            required=True,
            max_length=80,
        )
        self.duration_input = discord.ui.TextInput(
            label="المدة (30m / 12h / 7d / 2w / perm)",
            placeholder="مثال: 6h",
            required=True,
            max_length=32,
        )
        self.cell_input = discord.ui.TextInput(
            label="الزنزانة (holding / block / max)",
            placeholder="holding",
            default="holding",
            required=True,
            max_length=16,
        )
        self.add_item(self.label_input)
        self.add_item(self.duration_input)
        self.add_item(self.cell_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not _is_owner(interaction):
            await _deny(interaction, "❌ هاد الإعدادات ديال Owner بوحدو.")
            return
        seconds = parse_duration(str(self.duration_input.value))
        cell = str(self.cell_input.value).strip().lower()
        if seconds is None:
            await _deny(interaction, "❌ المدة ماشي صالحة.")
            return
        if cell not in CELL_KEYS:
            await _deny(interaction, f"❌ الزنزانة خاصها تكون: {', '.join(CELL_KEYS)}")
            return
        cog = _cog(interaction)
        try:
            key, entry = cog.store.add_offense(
                interaction.guild.id,
                label=str(self.label_input.value),
                seconds=seconds,
                cell=cell,
            )
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await cog.refresh_rule_surfaces(interaction.guild)
        await interaction.followup.send(
            content="✅ تزاد الحكم الجديد وولا متاح فالسجن وAuto Rules.",
            embed=offense_control_embed(key, entry),
            view=OffenseSelectedView(cog, interaction.guild, key, self.page),
            ephemeral=True,
        )


class OffenseEditSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild, page: int = 0):
        items = _sorted_offense_items(cog, guild)
        page, pages = _clamp_page(page, len(items), DISCORD_SELECT_PAGE_SIZE)
        start = page * DISCORD_SELECT_PAGE_SIZE
        options = [
            discord.SelectOption(
                label=entry["label"][:100],
                value=key,
                description=f"{format_duration(entry['seconds'])} • {entry.get('cell','holding')}"[:100],
            )
            for key, entry in items[start : start + DISCORD_SELECT_PAGE_SIZE]
        ]
        self.page = page
        super().__init__(
            placeholder=f"اختار الحكم… الصفحة {page + 1}/{pages}", options=options
        )

    async def callback(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        key = self.values[0]
        entry = cog.store.offense(interaction.guild.id, key)
        await interaction.response.edit_message(
            content=None,
            embed=offense_control_embed(key, entry),
            view=OffenseSelectedView(cog, interaction.guild, key, self.page),
        )


class OffenseSelectedView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild, key: str, page: int = 0):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.key = key
        self.page = page
        custom = key not in DEFAULT_OFFENSES
        self.reset_or_delete_btn.label = "مسح الحكم" if custom else "رجّع للافتراضي"
        self.reset_or_delete_btn.emoji = "🗑️" if custom else "♻️"
        self.reset_or_delete_btn.style = (
            discord.ButtonStyle.danger if custom else discord.ButtonStyle.secondary
        )

    @discord.ui.button(label="تعديل", emoji="✏️", style=discord.ButtonStyle.primary)
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        entry = self.cog.store.offense(interaction.guild.id, self.key)
        await interaction.response.send_modal(OffenseEditModal(self.key, entry, self.page))

    @discord.ui.button(label="مسح / Reset", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def reset_or_delete_btn(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        try:
            if self.key in DEFAULT_OFFENSES:
                self.cog.store.reset_offense(interaction.guild.id, self.key)
                message = "♻️ رجع الحكم للإعدادات الأصلية."
            else:
                self.cog.store.remove_offense(interaction.guild.id, self.key)
                message = "🗑️ تمسح الحكم المخصص."
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        await interaction.response.edit_message(
            content=message,
            embed=None,
            view=OffenseEditView(self.cog, interaction.guild, self.page),
        )
        await self.cog.refresh_rule_surfaces(interaction.guild)

    @discord.ui.button(label="رجوع للأحكام", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="⚖️ اختار الحكم باش تعدل الاسم/المدة/الزنزانة:",
            embed=None,
            view=OffenseEditView(self.cog, interaction.guild, self.page),
        )


class OffenseEditView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild, page: int = 0):
        super().__init__()
        self.cog = cog
        self.guild = guild
        items = _sorted_offense_items(cog, guild)
        self.page, self.pages = _clamp_page(page, len(items), DISCORD_SELECT_PAGE_SIZE)
        self.add_item(OffenseEditSelect(cog, guild, self.page))
        self.previous_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.pages - 1

    @discord.ui.button(label="حكم جديد", emoji="➕", style=discord.ButtonStyle.success, row=1)
    async def create_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(OffenseCreateModal(self.page))

    @discord.ui.button(label="السابق", emoji="⬅️", row=1)
    async def previous_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="⚖️ اختار الحكم باش تعدل الاسم/المدة/الزنزانة:",
            embed=None,
            view=OffenseEditView(self.cog, self.guild, self.page - 1),
        )

    @discord.ui.button(label="التالي", emoji="➡️", row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="⚖️ اختار الحكم باش تعدل الاسم/المدة/الزنزانة:",
            embed=None,
            view=OffenseEditView(self.cog, self.guild, self.page + 1),
        )


# ═══════════════════════════════════════════════════════
# ║          5ب. القوانين التلقائية ديال الـOwner        ║
# ═══════════════════════════════════════════════════════

AUTO_RULE_KIND_LABELS = {
    "word": "📝 كلمة/عبارة ممنوعة",
    "domain": "🌐 موقع ممنوع",
    "action": "⚙️ فعل ممنوع",
}


def _trigger_count_value(raw) -> int:
    try:
        count = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError("كتب عدد صحيح بحال 2 ولا 4 ولا 10.")
    if not AUTO_RULE_TRIGGER_MIN <= count <= AUTO_RULE_TRIGGER_MAX:
        raise ValueError(
            f"عدد التكرارات خاصو يكون بين {AUTO_RULE_TRIGGER_MIN} و {AUTO_RULE_TRIGGER_MAX}."
        )
    return count


def _auto_rule_subject(rule: dict) -> str:
    kind = rule.get("kind")
    pattern = str(rule.get("pattern", ""))
    if kind == "action":
        return AUTO_ACTION_LABELS.get(pattern, pattern)
    return pattern


def auto_rules_embed(cog, guild: discord.Guild, page: int = 0) -> discord.Embed:
    rules = list(cog.store.auto_rules(guild.id).values())
    rules.sort(key=lambda item: int(item.get("id", 0) or 0))
    page, pages = _clamp_page(page, len(rules), AUTO_RULE_EMBED_PAGE_SIZE)
    start = page * AUTO_RULE_EMBED_PAGE_SIZE
    visible_rules = rules[start : start + AUTO_RULE_EMBED_PAGE_SIZE]
    embed = discord.Embed(
        title="🛡️ القوانين التلقائية — Owner Only",
        description=(
            "زيد لائحة كلمات/عبارات دفعة وحدة، موقع، أو فعل ممنوع وربطهم بحكم من "
            "**Prison Code**.\n"
            "إلا وقع الخرق، البوت كيمسح الرسالة وكيطبق مدة المخالفة وزنزانتها؛ "
            "وإلا كان العضو مسجون من قبل كتزاد العقوبة وكيوقع التصعيد العادي.\n"
            "كل قانون عندو **عدد تكرارات مستقل لكل Discord ID**، والعداد كيتصفر "
            "غير منين يطبق الحكم.\n\n"
            "♾️ **عدد القوانين بلا حد** — استعمل السابق/التالي للتنقل.\n"
            "🔐 التحكم فهاد اللوحة ديال **Owner بوحدو**."
        ),
        color=discord.Color.dark_teal(),
        timestamp=datetime.now(),
    )
    if not rules:
        embed.add_field(
            name="📋 القوانين الحالية",
            value="ماكاين حتى قانون تلقائي دابا.",
            inline=False,
        )
    else:
        for rule in visible_rules:
            offense = cog.store.offense(guild.id, rule.get("offense", "manual"))
            state = "🟢" if bool(rule.get("enabled", True)) else "⚫"
            subject = _auto_rule_subject(rule)[:55]
            kind = AUTO_RULE_KIND_LABELS.get(rule.get("kind"), "قاعدة")
            embed.add_field(
                name=f"{state} #{rule.get('id')} • {kind}",
                value=(
                    f"`{subject}`\n↳ **{offense['label']}** • "
                    f"{format_duration(int(offense['seconds']))} • "
                    f"`{offense.get('cell', 'holding')}` • "
                    f"🎯 العقوبة فالخرق **{int(rule.get('trigger_count', 1) or 1)}** "
                    f"(قبلها {max(0, int(rule.get('trigger_count', 1) or 1) - 1)} تحذيرات)"
                ),
                inline=False,
            )
    embed.set_footer(
        text=(
            f"القوانين: {len(rules)} • الصفحة {page + 1}/{pages} • بلا حد | "
            "أقوى عقوبة كتطبق مرة وحدة إلا تطابقو عدة قوانين"
        )
    )
    return embed


class AutoRuleOffenseSelect(discord.ui.Select):
    def __init__(
        self,
        cog,
        guild: discord.Guild,
        kind: str,
        patterns: list[str],
        trigger_count: int,
        page: int = 0,
    ):
        self.kind = kind
        self.patterns = patterns
        self.trigger_count = _trigger_count_value(trigger_count)
        items = _sorted_offense_items(cog, guild)
        page, pages = _clamp_page(page, len(items), DISCORD_SELECT_PAGE_SIZE)
        start = page * DISCORD_SELECT_PAGE_SIZE
        options = [
            discord.SelectOption(
                label=entry["label"][:100],
                value=key,
                description=(
                    f"{format_duration(int(entry['seconds']))} • {entry.get('cell', 'holding')}"
                )[:100],
            )
            for key, entry in items[start : start + DISCORD_SELECT_PAGE_SIZE]
        ]
        super().__init__(
            placeholder=f"اختار الحكم… الصفحة {page + 1}/{pages}",
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        try:
            result = cog.store.add_auto_rules_bulk(
                interaction.guild.id,
                kind=self.kind,
                patterns=self.patterns,
                offense_key=self.values[0],
                trigger_count=self.trigger_count,
            )
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        created = len(result["created"])
        skipped = len(result["skipped"])
        invalid = len(result["invalid"])
        total = len(cog.store.auto_rules(interaction.guild.id))
        home_page, _pages = _clamp_page(
            max(0, total - 1), total, AUTO_RULE_EMBED_PAGE_SIZE
        )
        details = [
            f"✅ تزادو **{created}** قانون تلقائي؛ الحكم كيتطبق من المرة "
            f"**{self.trigger_count}** لكل Discord ID."
        ]
        if skipped:
            details.append(f"↪️ {skipped} كانو مزادين من قبل وتفوتو.")
        if invalid:
            details.append(f"⚠️ {invalid} قيم ماكانوش صالحين وتفوتو.")
        await interaction.response.edit_message(
            content="\n".join(details),
            embed=auto_rules_embed(cog, interaction.guild, home_page),
            view=AutoRulesHomeView(cog, interaction.guild, home_page),
        )
        await cog.refresh_rule_surfaces(interaction.guild)


class AutoRuleOffenseView(OwnerOnlyPrisonView):
    def __init__(
        self,
        cog,
        guild: discord.Guild,
        kind: str,
        patterns,
        trigger_count: int,
        page: int = 0,
    ):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.kind = kind
        self.patterns = [str(item) for item in patterns] if isinstance(patterns, list) else [str(patterns)]
        self.trigger_count = _trigger_count_value(trigger_count)
        items = _sorted_offense_items(cog, guild)
        self.page, self.pages = _clamp_page(page, len(items), DISCORD_SELECT_PAGE_SIZE)
        self.add_item(
            AutoRuleOffenseSelect(
                cog, guild, kind, self.patterns, self.trigger_count, self.page
            )
        )
        self.previous_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.pages - 1

    @discord.ui.button(label="السابق", emoji="⬅️", row=1)
    async def previous_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            view=AutoRuleOffenseView(
                self.cog, self.guild, self.kind, self.patterns,
                self.trigger_count, self.page - 1
            )
        )

    @discord.ui.button(label="التالي", emoji="➡️", row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            view=AutoRuleOffenseView(
                self.cog, self.guild, self.kind, self.patterns,
                self.trigger_count, self.page + 1
            )
        )


class AutoRulePatternModal(discord.ui.Modal):
    def __init__(self, kind: str):
        title = "📝 كلمة/عبارة ممنوعة" if kind == "word" else "🌐 موقع ممنوع"
        super().__init__(title=title)
        self.kind = kind
        self.pattern_input = discord.ui.TextInput(
            label="الكلمة أو العبارة" if kind == "word" else "الدومين / الموقع",
            placeholder=(
                "مثال: عبارة ممنوعة"
                if kind == "word"
                else "مثال: example.com — الرابط الكامل مقبول حتى هو"
            ),
            required=True,
            max_length=120 if kind == "word" else 253,
        )
        self.count_input = discord.ui.TextInput(
            label=f"عدد الخروقات حتى العقوبة ({AUTO_RULE_TRIGGER_MIN}-{AUTO_RULE_TRIGGER_MAX})",
            placeholder="مثال: 4 = 3 تحذيرات والعقوبة فالرابعة",
            default="1",
            required=True,
            max_length=3,
        )
        self.add_item(self.pattern_input)
        self.add_item(self.count_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not _is_owner(interaction):
            await _deny(interaction, "❌ هاد الإعدادات ديال Owner بوحدو.")
            return
        cog = _cog(interaction)
        pattern = normalize_auto_rule_pattern(self.kind, str(self.pattern_input.value))
        if not pattern:
            await _deny(interaction, "❌ القيمة ماشي صالحة. راجعها وعاود جرّب.")
            return
        try:
            trigger_count = _trigger_count_value(self.count_input.value)
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        await interaction.response.send_message(
            f"⚖️ دابا اختار العقوبة ديال **{pattern}** من المرة **{trigger_count}**:",
            view=AutoRuleOffenseView(
                cog, interaction.guild, self.kind, [pattern], trigger_count
            ),
            ephemeral=True,
        )


class BulkWordRulesModal(discord.ui.Modal, title="📝 إضافة كلمات وألفاظ ممنوعة"):
    def __init__(self):
        super().__init__()
        self.words_input = discord.ui.TextInput(
            label="الكلمات / العبارات (كل وحدة فسطر أو بفاصلة)",
            placeholder="كلمة ممنوعة\nعبارة ممنوعة\nلفظ آخر",
            required=True,
            max_length=4000,
            style=discord.TextStyle.paragraph,
        )
        self.count_input = discord.ui.TextInput(
            label=f"عدد الخروقات حتى العقوبة ({AUTO_RULE_TRIGGER_MIN}-{AUTO_RULE_TRIGGER_MAX})",
            placeholder="مثال: 4 — نفس العدد للكلمات كاملة",
            default="1",
            required=True,
            max_length=3,
        )
        self.add_item(self.words_input)
        self.add_item(self.count_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not _is_owner(interaction):
            await _deny(interaction, "❌ هاد الإعدادات ديال Owner بوحدو.")
            return
        raw_items = re.split(r"[\n,;،؛]+", str(self.words_input.value))
        patterns: list[str] = []
        seen: set[str] = set()
        for raw in raw_items:
            pattern = normalize_auto_rule_pattern("word", raw)
            if pattern and pattern not in seen:
                seen.add(pattern)
                patterns.append(pattern)
        if not patterns:
            await _deny(interaction, "❌ ما لقيت حتى كلمة ولا عبارة صالحة.")
            return
        try:
            trigger_count = _trigger_count_value(self.count_input.value)
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        cog = _cog(interaction)
        await interaction.response.send_message(
            f"✅ تقراو **{len(patterns)}** كلمات/عبارات. اختار الحكم اللي غادي "
            f"يطبق عليهم من المرة **{trigger_count}**:",
            view=AutoRuleOffenseView(
                cog, interaction.guild, "word", patterns, trigger_count
            ),
            ephemeral=True,
        )


class AutoActionThresholdModal(discord.ui.Modal, title="🔢 تحذيرات الفعل الممنوع"):
    def __init__(self, action: str):
        super().__init__()
        self.action = action
        self.count_input = discord.ui.TextInput(
            label=f"عدد الخروقات حتى العقوبة ({AUTO_RULE_TRIGGER_MIN}-{AUTO_RULE_TRIGGER_MAX})",
            placeholder="مثال: 4 = 3 تحذيرات والعقوبة فالرابعة",
            default="1",
            required=True,
            max_length=3,
        )
        self.add_item(self.count_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not _is_owner(interaction):
            await _deny(interaction, "❌ هاد الإعدادات ديال Owner بوحدو.")
            return
        try:
            trigger_count = _trigger_count_value(self.count_input.value)
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        cog = _cog(interaction)
        await interaction.response.edit_message(
            content=(
                f"⚖️ اختار العقوبة ديال **{AUTO_ACTION_LABELS[self.action]}**؛ "
                f"غتطبق فالخرق **{trigger_count}**."
            ),
            embed=None,
            view=AutoRuleOffenseView(
                cog, interaction.guild, "action", [self.action], trigger_count
            ),
        )


class AutoActionSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="اختار الفعل اللي بغيتي تمنع…",
            options=[
                discord.SelectOption(label=label[:100], value=key)
                for key, label in AUTO_ACTION_LABELS.items()
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        action = self.values[0]
        await interaction.response.send_modal(AutoActionThresholdModal(action))


class AutoActionView(OwnerOnlyPrisonView):
    def __init__(self):
        super().__init__()
        self.add_item(AutoActionSelect())


class AutoRuleManageSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild, page: int = 0):
        rules = list(cog.store.auto_rules(guild.id).values())
        rules.sort(key=lambda item: int(item.get("id", 0) or 0))
        page, pages = _clamp_page(page, len(rules), DISCORD_SELECT_PAGE_SIZE)
        start = page * DISCORD_SELECT_PAGE_SIZE
        self.page = page
        options = []
        for rule in rules[start : start + DISCORD_SELECT_PAGE_SIZE]:
            state = "مفعّل" if bool(rule.get("enabled", True)) else "موقوف"
            options.append(
                discord.SelectOption(
                    label=f"#{rule.get('id')} • {_auto_rule_subject(rule)}"[:100],
                    value=str(rule.get("id")),
                    description=(
                        f"{state} • من المرة {int(rule.get('trigger_count', 1) or 1)} • "
                        f"{AUTO_RULE_KIND_LABELS.get(rule.get('kind'), 'قاعدة')}"
                    )[:100],
                )
            )
        super().__init__(
            placeholder=f"اختار قانون… الصفحة {page + 1}/{pages}", options=options
        )

    async def callback(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        rule = cog.store.auto_rule(interaction.guild.id, self.values[0])
        if rule is None:
            await _deny(interaction, "❌ هاد القانون تمسح من قبل.")
            return
        offense = cog.store.offense(interaction.guild.id, rule.get("offense", "manual"))
        embed = discord.Embed(
            title=f"🛡️ القانون #{rule.get('id')}",
            description=(
                f"**النوع:** {AUTO_RULE_KIND_LABELS.get(rule.get('kind'), 'قاعدة')}\n"
                f"**القيمة:** `{_auto_rule_subject(rule)}`\n"
                f"**الحالة:** {'🟢 مفعّل' if rule.get('enabled', True) else '⚫ موقوف'}\n"
                f"**تنفيذ الحكم:** فالخرق **{int(rule.get('trigger_count', 1) or 1)}** لكل عضو "
                f"(قبلها {max(0, int(rule.get('trigger_count', 1) or 1) - 1)} تحذيرات)\n"
                f"**العقوبة:** {offense['label']} — {format_duration(int(offense['seconds']))} "
                f"فـ `{offense.get('cell', 'holding')}`"
            ),
            color=discord.Color.orange(),
        )
        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=AutoRuleSelectedView(
                cog, interaction.guild, str(rule.get("id")), self.page
            ),
        )


class AutoRuleManageView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild, page: int = 0):
        super().__init__()
        self.cog = cog
        self.guild = guild
        rules = list(cog.store.auto_rules(guild.id).values())
        self.page, self.pages = _clamp_page(page, len(rules), DISCORD_SELECT_PAGE_SIZE)
        self.add_item(AutoRuleManageSelect(cog, guild, self.page))
        self.previous_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.pages - 1

    @discord.ui.button(label="السابق", emoji="⬅️", row=1)
    async def previous_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="🧰 اختار القانون:",
            embed=None,
            view=AutoRuleManageView(self.cog, self.guild, self.page - 1),
        )

    @discord.ui.button(label="التالي", emoji="➡️", row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="🧰 اختار القانون:",
            embed=None,
            view=AutoRuleManageView(self.cog, self.guild, self.page + 1),
        )

    @discord.ui.button(label="رجوع", emoji="↩️", row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        home_page = self.page * DISCORD_SELECT_PAGE_SIZE // AUTO_RULE_EMBED_PAGE_SIZE
        await interaction.response.edit_message(
            content=None,
            embed=auto_rules_embed(self.cog, self.guild, home_page),
            view=AutoRulesHomeView(self.cog, self.guild, home_page),
        )


class AutoRuleThresholdModal(discord.ui.Modal, title="🔢 عدد التكرارات قبل الحكم"):
    def __init__(self, rule_id: str, page: int, current: int):
        super().__init__()
        self.rule_id = str(rule_id)
        self.page = int(page)
        self.count_input = discord.ui.TextInput(
            label=f"عدد الخروقات حتى العقوبة ({AUTO_RULE_TRIGGER_MIN}-{AUTO_RULE_TRIGGER_MAX})",
            placeholder="مثال: 4 = 3 تحذيرات والعقوبة فالرابعة",
            default=str(int(current)),
            required=True,
            min_length=1,
            max_length=3,
        )
        self.add_item(self.count_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not _is_owner(interaction):
            await _deny(interaction, "❌ هاد الإعدادات ديال Owner بوحدو.")
            return
        try:
            count = int(str(self.count_input.value).strip())
        except ValueError:
            await _deny(interaction, "❌ كتب عدد صحيح بحال `2` ولا `6` ولا `10`.")
            return
        cog = _cog(interaction)
        try:
            rule = cog.store.set_auto_rule_trigger_count(
                interaction.guild.id, self.rule_id, count
            )
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        if rule is None:
            await _deny(interaction, "❌ هاد القانون تمسح من قبل.")
            return
        await interaction.response.edit_message(
            content=(
                f"✅ القانون **#{self.rule_id}** غادي يطبق الحكم من المرة "
                f"**{count}** لكل Discord ID؛ قبلها كيوصلو **{max(0, count - 1)}** "
                "تحذيرات. العداد القديم ديالو تصفر."
            ),
            embed=None,
            view=AutoRuleManageView(cog, interaction.guild, self.page),
        )
        await cog.refresh_rule_surfaces(interaction.guild)


class AutoRuleChangeOffenseSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild, rule_id: str, page: int = 0):
        self.rule_id = str(rule_id)
        self.page = int(page)
        items = _sorted_offense_items(cog, guild)
        page, pages = _clamp_page(page, len(items), DISCORD_SELECT_PAGE_SIZE)
        self.page = page
        start = page * DISCORD_SELECT_PAGE_SIZE
        options = [
            discord.SelectOption(
                label=entry["label"][:100],
                value=key,
                description=(
                    f"{format_duration(int(entry['seconds']))} • {entry.get('cell', 'holding')}"
                )[:100],
            )
            for key, entry in items[start : start + DISCORD_SELECT_PAGE_SIZE]
        ]
        super().__init__(
            placeholder=f"اختار الحكم الجديد… الصفحة {page + 1}/{pages}",
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        try:
            rule = cog.store.set_auto_rule_offense(
                interaction.guild.id, self.rule_id, self.values[0]
            )
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        if rule is None:
            await _deny(interaction, "❌ هاد القانون تمسح من قبل.")
            return
        offense = cog.store.offense(interaction.guild.id, self.values[0])
        await interaction.response.edit_message(
            content=f"✅ تبدل حكم القانون **#{self.rule_id}** لـ **{offense['label']}**.",
            embed=None,
            view=AutoRuleManageView(cog, interaction.guild),
        )
        await cog.refresh_rule_surfaces(interaction.guild)


class AutoRuleChangeOffenseView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild, rule_id: str, page: int = 0):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.rule_id = str(rule_id)
        items = _sorted_offense_items(cog, guild)
        self.page, self.pages = _clamp_page(page, len(items), DISCORD_SELECT_PAGE_SIZE)
        self.add_item(
            AutoRuleChangeOffenseSelect(cog, guild, self.rule_id, self.page)
        )
        self.previous_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.pages - 1

    @discord.ui.button(label="السابق", emoji="⬅️", row=1)
    async def previous_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            view=AutoRuleChangeOffenseView(
                self.cog, self.guild, self.rule_id, self.page - 1
            )
        )

    @discord.ui.button(label="التالي", emoji="➡️", row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            view=AutoRuleChangeOffenseView(
                self.cog, self.guild, self.rule_id, self.page + 1
            )
        )

    @discord.ui.button(label="رجوع", emoji="↩️", row=1)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="🧰 اختار القانون:",
            embed=None,
            view=AutoRuleManageView(self.cog, self.guild),
        )


class AutoRulePenaltyDurationModal(discord.ui.Modal, title="⚖️ الحكم والمدة والزنزانة"):
    def __init__(self, rule_id: str, page: int, offense_key: str, entry: dict):
        super().__init__()
        self.rule_id = str(rule_id)
        self.page = int(page)
        self.offense_key = str(offense_key)
        self.label_input = discord.ui.TextInput(
            label="اسم الحكم", default=str(entry.get("label", "")), max_length=80
        )
        self.duration_input = discord.ui.TextInput(
            label="مدة السجن (30m / 12h / 7d / perm)",
            default=_seconds_to_text(int(entry.get("seconds", 3600))),
            max_length=32,
        )
        self.cell_input = discord.ui.TextInput(
            label="الزنزانة (holding / block / max)",
            default=str(entry.get("cell", "holding")),
            max_length=16,
        )
        self.add_item(self.label_input)
        self.add_item(self.duration_input)
        self.add_item(self.cell_input)

    async def on_submit(self, interaction: discord.Interaction):
        if not _is_owner(interaction):
            await _deny(interaction, "❌ هاد الإعدادات ديال Owner بوحدو.")
            return
        seconds = parse_duration(str(self.duration_input.value))
        cell = str(self.cell_input.value).strip().lower()
        if seconds is None:
            await _deny(interaction, "❌ المدة ماشي صالحة.")
            return
        if cell not in CELL_KEYS:
            await _deny(interaction, f"❌ الزنزانة خاصها تكون: {', '.join(CELL_KEYS)}")
            return
        cog = _cog(interaction)
        try:
            entry = cog.store.set_offense(
                interaction.guild.id,
                self.offense_key,
                label=str(self.label_input.value).strip(),
                seconds=seconds,
                cell=cell,
            )
        except ValueError as exc:
            await _deny(interaction, f"❌ {exc}")
            return
        await interaction.response.edit_message(
            content=(
                f"✅ الحكم المرتبط بالقانون **#{self.rule_id}** تحدث: "
                f"**{entry['label']}** — {format_duration(int(entry['seconds']))} "
                f"فـ `{entry.get('cell', 'holding')}`."
            ),
            embed=None,
            view=AutoRuleManageView(cog, interaction.guild, self.page),
        )
        await cog.refresh_rule_surfaces(interaction.guild)


class AutoRulePenaltyView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild, rule_id: str, page: int = 0):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.rule_id = str(rule_id)
        self.page = int(page)

    @discord.ui.button(label="تعديل المدة والزنزانة", emoji="⏳", style=discord.ButtonStyle.primary)
    async def duration_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        rule = self.cog.store.auto_rule(interaction.guild.id, self.rule_id)
        if rule is None:
            await _deny(interaction, "❌ هاد القانون تمسح من قبل.")
            return
        offense_key = str(rule.get("offense", "manual"))
        entry = self.cog.store.offense(interaction.guild.id, offense_key)
        await interaction.response.send_modal(
            AutoRulePenaltyDurationModal(
                self.rule_id, self.page, offense_key, entry
            )
        )

    @discord.ui.button(label="بدل الحكم", emoji="⚖️", style=discord.ButtonStyle.secondary)
    async def change_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=f"⚖️ اختار الحكم الجديد للقانون **#{self.rule_id}**:",
            embed=None,
            view=AutoRuleChangeOffenseView(
                self.cog, interaction.guild, self.rule_id
            ),
        )

    @discord.ui.button(label="رجوع للقانون", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="🧰 اختار القانون:",
            embed=None,
            view=AutoRuleManageView(self.cog, interaction.guild, self.page),
        )


class AutoRuleSelectedView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild, rule_id: str, page: int = 0):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.rule_id = str(rule_id)
        self.page = page

    @discord.ui.button(label="عدد التحذيرات", emoji="🔢", style=discord.ButtonStyle.primary)
    async def threshold_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        rule = self.cog.store.auto_rule(interaction.guild.id, self.rule_id)
        if rule is None:
            await _deny(interaction, "❌ هاد القانون تمسح من قبل.")
            return
        await interaction.response.send_modal(
            AutoRuleThresholdModal(
                self.rule_id,
                self.page,
                int(rule.get("trigger_count", 1) or 1),
            )
        )

    @discord.ui.button(label="الحكم والمدة", emoji="⚖️", style=discord.ButtonStyle.primary)
    async def offense_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        rule = self.cog.store.auto_rule(interaction.guild.id, self.rule_id)
        if rule is None:
            await _deny(interaction, "❌ هاد القانون تمسح من قبل.")
            return
        offense = self.cog.store.offense(
            interaction.guild.id, str(rule.get("offense", "manual"))
        )
        await interaction.response.edit_message(
            content=(
                f"⚖️ **{offense['label']}** — {format_duration(int(offense['seconds']))} "
                f"فـ `{offense.get('cell', 'holding')}`\n"
                "تقدر تبدل الحكم كامل، أو تعدل مدتو وزنزانتو من هنا. "
                "إلا كان نفس الحكم مربوط بقوانين أخرى غيتحدث عندهم كاملين."
            ),
            embed=None,
            view=AutoRulePenaltyView(
                self.cog, interaction.guild, self.rule_id, self.page
            ),
        )

    @discord.ui.button(label="تشغيل / توقيف", emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def toggle_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        rule = self.cog.store.toggle_auto_rule(interaction.guild.id, self.rule_id)
        if rule is None:
            await _deny(interaction, "❌ هاد القانون تمسح من قبل.")
            return
        await interaction.response.edit_message(
            content=("✅ القانون تفعّل." if rule["enabled"] else "⏸️ القانون توقف مؤقتاً."),
            embed=None,
            view=AutoRuleManageView(self.cog, interaction.guild, self.page),
        )
        await self.cog.refresh_rule_surfaces(interaction.guild)

    @discord.ui.button(label="مسح نهائي", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def delete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        removed = self.cog.store.remove_auto_rule(interaction.guild.id, self.rule_id)
        if removed is None:
            await _deny(interaction, "❌ هاد القانون تمسح من قبل.")
            return
        rules_left = bool(self.cog.store.auto_rules(interaction.guild.id))
        await interaction.response.edit_message(
            content=f"🗑️ تمسح القانون **#{self.rule_id}** نهائياً.",
            embed=None,
            view=(
                AutoRuleManageView(self.cog, interaction.guild, self.page)
                if rules_left
                else AutoRulesHomeView(self.cog, interaction.guild)
            ),
        )
        await self.cog.refresh_rule_surfaces(interaction.guild)

    @discord.ui.button(label="رجوع", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="🧰 اختار القانون:",
            embed=None,
            view=AutoRuleManageView(self.cog, self.guild, self.page),
        )


class AutoRulesHomeView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild, page: int = 0):
        super().__init__()
        self.cog = cog
        self.guild = guild
        rules = list(cog.store.auto_rules(guild.id).values())
        self.page, self.pages = _clamp_page(page, len(rules), AUTO_RULE_EMBED_PAGE_SIZE)
        self.previous_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.pages - 1

    @discord.ui.button(label="زيد كلمات/عبارات", emoji="📝", style=discord.ButtonStyle.primary, row=0)
    async def add_word_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BulkWordRulesModal())

    @discord.ui.button(label="زيد موقع", emoji="🌐", style=discord.ButtonStyle.primary, row=0)
    async def add_domain_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AutoRulePatternModal("domain"))

    @discord.ui.button(label="زيد فعل", emoji="⚙️", style=discord.ButtonStyle.primary, row=0)
    async def add_action_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "⚙️ اختار الفعل الممنوع:", view=AutoActionView(), ephemeral=True
        )

    @discord.ui.button(label="إدارة القوانين", emoji="🧰", style=discord.ButtonStyle.secondary, row=1)
    async def manage_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.cog.store.auto_rules(interaction.guild.id):
            await _deny(interaction, "📭 ماكاين حتى قانون باش تدبّرو دابا.")
            return
        await interaction.response.send_message(
            "🧰 اختار القانون:",
            view=AutoRuleManageView(self.cog, interaction.guild),
            ephemeral=True,
        )

    @discord.ui.button(label="السابق", emoji="⬅️", row=1)
    async def previous_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=None,
            embed=auto_rules_embed(self.cog, self.guild, self.page - 1),
            view=AutoRulesHomeView(self.cog, self.guild, self.page - 1),
        )

    @discord.ui.button(label="التالي", emoji="➡️", row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content=None,
            embed=auto_rules_embed(self.cog, self.guild, self.page + 1),
            view=AutoRulesHomeView(self.cog, self.guild, self.page + 1),
        )


# ═══════════════════════════════════════════════════════
# ║                6. البانل الرئيسية                    ║
# ═══════════════════════════════════════════════════════

def prison_panel_embed(cog, guild: discord.Guild) -> discord.Embed:
    record = cog.store.guild(guild.id)
    inmates = cog.store.inmates(guild.id)
    prisoner = cog.prisoner_role(guild)
    warden = cog.warden_role(guild)
    category = cog.prison_category(guild)

    counts = {key: 0 for key in CELL_KEYS}
    for data in inmates.values():
        cell = data.get("cell", "holding")
        if cell in counts:
            counts[cell] += 1

    embed = discord.Embed(
        title="🔒 GGMW9 PRISON — Owner Control",
        description=(
            "المركز الكامل ديال السجن. **الاونر بوحدو** لي عندو الوصول لهاد البانل.\n"
            "الادمين والمود **ماعندهم حتى سلطة** داخل السجن — تسقط عليهم كاملة.\n\n"
            "⛓️ **Imprison** — سجن عضو بالمخالفة والمدة\n"
            "🔗 **Solitary** — عزل سجين فروم خاصة بسميتو\n"
            "🔓 **Release** — عفو وإطلاق سراح (كترجع الرولات أوتوماتيكيا)\n"
            "⏳ **Adjust** — زيادة/نقصان المدة ولا تحويلها لمؤبد\n"
            "👮 **Wardens** — شكون كيولي شرطة (أحكام خفيفة بوحدها)\n"
            "⚖️ **الأحكام والمدد** — تعديل الاسم والمدة والزنزانة أو إضافة حكم جديد\n"
            "🛡️ **القوانين والتكرارات** — الممنوعات والحكم ومن أي مرة يتطبق لكل عضو\n"
            "🛠️ **Setup / Repair** — بناء ولا إصلاح الرومز والصلاحيات"
        ),
        color=discord.Color.dark_red(),
        timestamp=datetime.now(),
    )
    embed.add_field(name="👥 السجناء", value=f"**{len(inmates)}**", inline=True)
    embed.add_field(name="⛓️ Holding", value=str(counts["holding"]), inline=True)
    embed.add_field(name="🔒 Block", value=str(counts["block"]), inline=True)
    embed.add_field(name="🚨 Maximum", value=str(counts["max"]), inline=True)
    embed.add_field(
        name="👮 Wardens",
        value=str(len(warden.members)) if warden else "—",
        inline=True,
    )
    embed.add_field(
        name="🔗 انفرادي",
        value=f"{cog.store.solitary_count(guild.id)} / {SOLITARY_MAX_ROOMS}",
        inline=True,
    )
    pending = len(cog.store.pending_complaints(guild.id))
    embed.add_field(
        name="📮 شكايات معلقة",
        value=(f"**{pending}** ⚠️" if pending else "0"),
        inline=True,
    )
    active_rules = sum(
        1
        for rule in cog.store.auto_rules(guild.id).values()
        if bool(rule.get("enabled", True))
    )
    embed.add_field(name="🛡️ قوانين تلقائية", value=str(active_rules), inline=True)
    embed.add_field(
        name="🏗️ الحالة",
        value=("🟢 مركّب" if (category and prisoner) else "🔴 خاصو Setup"),
        inline=True,
    )
    embed.add_field(
        name="🎭 الرولات",
        value=(
            f"Prisoner: {prisoner.mention if prisoner else '❌'}\n"
            f"Warden: {warden.mention if warden else '❌'}"
        ),
        inline=False,
    )
    embed.set_footer(text="GGMW9 Prison • Owner-only • كل حكم كيتسجل بـ Case ID")
    return embed


class PrisonOwnerPanelView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__()
        self.cog = cog

    @discord.ui.button(label="Imprison", emoji="⛓️", style=discord.ButtonStyle.danger, row=0)
    async def imprison_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "⛓️ اختار العضو اللي غادي تسجنو:", view=ImprisonFlowView(False), ephemeral=True
        )

    @discord.ui.button(label="Release", emoji="🔓", style=discord.ButtonStyle.success, row=0)
    async def release_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🔓 اختار السجين:", view=ReleaseView(self.cog, interaction.guild), ephemeral=True
        )

    @discord.ui.button(label="Adjust", emoji="⏳", style=discord.ButtonStyle.primary, row=0)
    async def adjust_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "⏳ اختار السجين باش تعدل المدة:",
            view=AdjustView(self.cog, interaction.guild),
            ephemeral=True,
        )

    @discord.ui.button(label="Solitary", emoji="🔗", style=discord.ButtonStyle.danger, row=0)
    async def solitary_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        count = self.cog.store.solitary_count(interaction.guild.id)
        pending = len(self.cog.store.pending_complaints(interaction.guild.id))
        embed = discord.Embed(
            title="🔗 الحبس الانفرادي",
            description=(
                f"**الرومز المفتوحة:** {count} / {SOLITARY_MAX_ROOMS}\n"
                f"**شكايات معلقة:** {pending}\n\n"
                "كل سجين معزول عندو **Voice+Chat** ورول مؤقت فريد مربوط بالـID والـCase.\n"
                "حتى مع عدة سجناء، كل واحد كيشوف غير الروم ديالو بحد عضو واحد.\n"
                "ملي تسالي المدة الروم والرول **كيتمسحو أوتوماتيكيا** وكيرجع لزنزانتو.\n\n"
                "🚨 أي صداع داخل الانفرادي كيضاعف الوقت؛ Holding أخف، Block أقسح، وMaximum الأقسى."
            ),
            color=discord.Color.dark_purple(),
        )
        await interaction.response.send_message(
            embed=embed, view=SolitaryView(self.cog, interaction.guild), ephemeral=True
        )

    @discord.ui.button(label="Wardens", emoji="👮", style=discord.ButtonStyle.secondary, row=1)
    async def wardens_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        warden = self.cog.warden_role(interaction.guild)
        current = (
            ", ".join(m.mention for m in warden.members) if warden and warden.members else "ماكاين حتى واحد"
        )
        embed = discord.Embed(
            title="👮 Warden Management",
            description=(
                f"**الـWardens الحاليين:** {current}\n\n"
                f"الـWarden كيقدر:\n"
                f"• يسجن غير فـ **{CELL_LABELS['holding']}**\n"
                f"• بمدة قصوى **{format_duration(WARDEN_MAX_SECONDS)}**\n"
                f"• غير المخالفات الخفيفة\n\n"
                "❌ **ما يقدرش** يطلق سراح، ولا يعدل المدد، ولا يسجن Warden آخر."
            ),
            color=discord.Color.teal(),
        )
        await interaction.response.send_message(
            embed=embed, view=WardenManageView(self.cog, interaction.guild), ephemeral=True
        )

    @discord.ui.button(label="الأحكام والمدد", emoji="⚖️", style=discord.ButtonStyle.secondary, row=1)
    async def offenses_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "⚖️ اختار المخالفة باش تعدل الاسم/المدة/الزنزانة:",
            view=OffenseEditView(self.cog, interaction.guild),
            ephemeral=True,
        )

    @discord.ui.button(label="Inmates", emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def inmates_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=self.cog.board_embed(interaction.guild), ephemeral=True
        )

    @discord.ui.button(label="القوانين والتكرارات", emoji="🛡️", style=discord.ButtonStyle.secondary, row=1)
    async def auto_rules_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=auto_rules_embed(self.cog, interaction.guild),
            view=AutoRulesHomeView(self.cog, interaction.guild),
            ephemeral=True,
        )

    @discord.ui.button(label="Setup / Repair", emoji="🛠️", style=discord.ButtonStyle.primary, row=2)
    async def setup_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await self.cog.ensure_infrastructure(interaction.guild)
        hidden = await self.cog.hide_everywhere(interaction.guild)
        embed = discord.Embed(
            title="🛠️ Prison Setup",
            color=discord.Color.green() if not result["errors"] else discord.Color.orange(),
            timestamp=datetime.now(),
        )
        if result["created"]:
            embed.add_field(
                name=f"🆕 تخلقو ({len(result['created'])})",
                value="\n".join(result["created"])[:1024],
                inline=False,
            )
        if result["repaired"]:
            embed.add_field(
                name=f"♻️ تصلحو ({len(result['repaired'])})",
                value="\n".join(result["repaired"])[:1024],
                inline=False,
            )
        embed.add_field(name="🔒 رومز تخباو على السجناء", value=str(hidden), inline=False)
        if result["errors"]:
            embed.add_field(
                name=f"❌ أخطاء ({len(result['errors'])})",
                value="\n".join(result["errors"])[:1024],
                inline=False,
            )
        else:
            embed.description = "✅ كلشي واجد. الرولات، الزنازن، والصلاحيات مركّبين."
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Refresh", emoji="🔄", style=discord.ButtonStyle.secondary, row=2)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await self.cog.publish_prison_code(interaction.guild)
        await self.cog.refresh_board(interaction.guild)
        await interaction.followup.send(
            "🔄 لوحة القانون ولوحة السجناء تحدثو.", ephemeral=True
        )


class WardenPanelView(WardenScopedView):
    """بانل مصغّرة للشرطة."""

    def __init__(self, cog):
        super().__init__()
        self.cog = cog

    @discord.ui.button(label="Imprison (خفيف)", emoji="⛓️", style=discord.ButtonStyle.danger)
    async def imprison_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "⛓️ اختار العضو:", view=ImprisonFlowView(True), ephemeral=True
        )

    @discord.ui.button(label="Inmates", emoji="📋", style=discord.ButtonStyle.secondary)
    async def inmates_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=self.cog.board_embed(interaction.guild), ephemeral=True
        )


# ═══════════════════════════════════════════════════════
# ║                     الـ Cog                          ║
# ═══════════════════════════════════════════════════════

class PrisonPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="prison", description="🔒 البانل ديال السجن (Owner / Warden)")
    @app_commands.default_permissions(administrator=True)
    @commands.guild_only()
    async def prison_cmd(self, ctx: commands.Context):
        cog = self.bot.get_cog("PrisonSystem")
        if cog is None:
            await ctx.send("❌ PrisonSystem ماشي محمّلة.", ephemeral=True)
            return

        try:
            await ctx.message.delete()
        except Exception:
            pass

        if ctx.author.id == ctx.guild.owner_id:
            await ctx.send(
                embed=prison_panel_embed(cog, ctx.guild),
                view=PrisonOwnerPanelView(cog, ctx.guild),
                ephemeral=True,
            )
            return

        if cog.is_warden(ctx.author):
            embed = discord.Embed(
                title="👮 Warden Panel",
                description=(
                    f"مرحبا {ctx.author.mention}.\n\n"
                    f"تقدر تسجن غير فـ **{CELL_LABELS['holding']}** "
                    f"وبمدة قصوى **{format_duration(WARDEN_MAX_SECONDS)}**.\n"
                    "❌ ما تقدرش تطلق سراح ولا تعدل المدد — هادشي ديال الاونر بوحدو."
                ),
                color=discord.Color.teal(),
            )
            await ctx.send(embed=embed, view=WardenPanelView(cog), ephemeral=True)
            return

        await ctx.send(
            "❌ هاد البانل خاصة بـ **Owner** و **Warden** بوحدهم.", ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PrisonPanel(bot))
    print("✅ Prison Panel: بانل الاونر + بانل الـWarden واجدين")
