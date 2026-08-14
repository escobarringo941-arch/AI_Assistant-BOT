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
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from cogs.prison_core import (
    CELL_KEYS,
    CHANNEL_NAMES,
    SOLITARY_DEFAULT_SECONDS,
    SOLITARY_MAX_ROOMS,
    SOLITARY_MAX_SECONDS,
    WARDEN_ALLOWED_CELLS,
    WARDEN_ALLOWED_SEVERITY,
    WARDEN_MAX_SECONDS,
    format_duration,
    now_ts,
    parse_duration,
)

CELL_LABELS = {
    "holding": "⛓️ Holding Cell (خفيف)",
    "block": "🔒 Cell Block (متوسط)",
    "max": "🚨 Maximum Security (قاسح)",
}


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


class OffenseSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild, member: discord.Member, warden_mode: bool):
        self.cog = cog
        self.member = member
        self.warden_mode = warden_mode

        catalogue = cog.store.offenses(guild.id)
        options: list[discord.SelectOption] = []
        for key, entry in sorted(
            catalogue.items(), key=lambda item: (item[1].get("severity", 1), item[1]["seconds"])
        ):
            if warden_mode and int(entry.get("severity", 1)) > WARDEN_ALLOWED_SEVERITY:
                continue
            options.append(
                discord.SelectOption(
                    label=entry["label"][:100],
                    value=key,
                    description=f"{format_duration(entry['seconds'])} • {entry.get('cell','holding')}"[:100],
                )
            )
        super().__init__(
            placeholder="اختار المخالفة…",
            options=options[:25] or [discord.SelectOption(label="—", value="manual")],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(
            ImprisonModal(self.member, self.values[0], self.warden_mode)
        )


class OffenseSelectView(WardenScopedView):
    def __init__(self, cog, guild: discord.Guild, member: discord.Member, warden_mode: bool):
        super().__init__()
        self.add_item(OffenseSelect(cog, guild, member, warden_mode))


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
            cog.store.update_inmate(interaction.guild.id, self.user_id, until=-1)
            await cog._post_cell_card(member, cog.store.inmate(interaction.guild.id, self.user_id))
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
            placeholder=f"مثال: 2h — أقصى {SOLITARY_MAX_SECONDS // 3600} ساعة",
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

        seconds = SOLITARY_DEFAULT_SECONDS
        raw = str(self.duration.value or "").strip()
        if raw:
            parsed = parse_duration(raw)
            if parsed is None or parsed < 0:
                await _deny(interaction, "❌ المدة ماشي صالحة. مثال: `2h` ولا `45m`.")
                return
            seconds = parsed
        if seconds > SOLITARY_MAX_SECONDS:
            await _deny(
                interaction,
                f"❌ أقصى مدة عزل هي **{format_duration(SOLITARY_MAX_SECONDS)}**.",
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
            f"⏱️ العزل يسالي بعد **{format_duration(seconds)}**.",
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


class SolitaryReleaseSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild):
        options = []
        for uid, record in list(cog.store.solitary(guild.id).items())[:25]:
            member = guild.get_member(int(uid))
            left = max(0, int(record.get("until", 0)) - now_ts())
            options.append(
                discord.SelectOption(
                    label=(member.display_name if member else f"ID {uid}")[:100],
                    value=str(uid),
                    description=f"باقي: {format_duration(left)}"[:100],
                )
            )
        super().__init__(
            placeholder="اخرج شي واحد من الانفرادي…",
            options=options or [discord.SelectOption(label="الانفرادي خاوي", value="none")],
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await _deny(interaction, "🕊️ الانفرادي خاوي.")
            return
        cog = _cog(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        result = await cog.release_from_solitary(
            interaction.guild, int(self.values[0]), reason="عفو من طرف الاونر"
        )
        if not result.get("ok"):
            await interaction.followup.send(f"❌ {result['error']}", ephemeral=True)
            return
        await interaction.followup.send(
            "🔓 خرج من الانفرادي والروم تمسحات. رجع لزنزانتو.", ephemeral=True
        )


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
    def __init__(self, key: str, entry: dict):
        super().__init__()
        self.key = key
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
        cog.store.set_offense(
            interaction.guild.id,
            self.key,
            label=str(self.label_input.value).strip(),
            seconds=seconds,
            cell=cell,
            severity=severity,
        )
        await interaction.response.defer(ephemeral=True, thinking=True)
        await cog.publish_prison_code(interaction.guild)
        await interaction.followup.send(
            f"✅ تعدلات: **{self.label_input.value}** → `{format_duration(seconds)}` فـ `{cell}`.\n"
            "📜 لوحة `prison-code` تحدثات.",
            ephemeral=True,
        )


def _seconds_to_text(seconds: int) -> str:
    if seconds < 0:
        return "perm"
    for size, suffix in ((7 * 86400, "w"), (86400, "d"), (3600, "h"), (60, "m")):
        if seconds >= size and seconds % size == 0:
            return f"{seconds // size}{suffix}"
    return f"{max(1, seconds // 60)}m"


class OffenseEditSelect(discord.ui.Select):
    def __init__(self, cog, guild: discord.Guild):
        catalogue = cog.store.offenses(guild.id)
        options = [
            discord.SelectOption(
                label=entry["label"][:100],
                value=key,
                description=f"{format_duration(entry['seconds'])} • {entry.get('cell','holding')}"[:100],
            )
            for key, entry in sorted(
                catalogue.items(), key=lambda i: (i[1].get("severity", 1), i[1]["seconds"])
            )
        ][:25]
        super().__init__(placeholder="اختار المخالفة اللي بغيتي تعدل…", options=options)

    async def callback(self, interaction: discord.Interaction):
        cog = _cog(interaction)
        entry = cog.store.offense(interaction.guild.id, self.values[0])
        await interaction.response.send_modal(OffenseEditModal(self.values[0], entry))


class OffenseEditView(OwnerOnlyPrisonView):
    def __init__(self, cog, guild: discord.Guild):
        super().__init__()
        self.add_item(OffenseEditSelect(cog, guild))


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
            "⚖️ **Offenses** — تعديل القانون والمدد\n"
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
                "كل سجين معزول عندو روم خاصة بسميتو، كيشوفها هو والاونر بوحدهم.\n"
                "ملي تسالي مدة العزل الروم **كتتمسح أوتوماتيكيا** وكيرجع لزنزانتو.\n\n"
                "ℹ️ العزل **ما كيزيدش** فالحكم الأصلي — غير عزل."
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

    @discord.ui.button(label="Offenses", emoji="⚖️", style=discord.ButtonStyle.secondary, row=1)
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
