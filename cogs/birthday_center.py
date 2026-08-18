# -*- coding: utf-8 -*-
"""Professional, restart-safe birthday center for GGMW9."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from math import ceil
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from cogs.panel_registry import upsert_fixed_panel


CENTER_MARKER = "GGMW9:BIRTHDAY_CENTER:v1"
PAGE_SIZE = 10


def _chunks(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]


class BirthdayDateModal(discord.ui.Modal, title="🎂 تسجيل عيد الميلاد"):
    def __init__(self, cog: "BirthdayCenter", member: discord.Member):
        super().__init__(timeout=180)
        self.cog = cog
        self.member = member
        current = cog.record(member.id) or {}
        self.day_input = discord.ui.TextInput(
            label="النهار",
            placeholder="مثال: 15",
            default=str(current.get("day", "")),
            min_length=1,
            max_length=2,
        )
        self.month_input = discord.ui.TextInput(
            label="الشهر",
            placeholder="مثال: 8",
            default=str(current.get("month", "")),
            min_length=1,
            max_length=2,
        )
        self.add_item(self.day_input)
        self.add_item(self.month_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            day = int(str(self.day_input.value).strip())
            month = int(str(self.month_input.value).strip())
            datetime(2024, month, day)
        except (TypeError, ValueError):
            await interaction.response.send_message(
                "❌ التاريخ ماشي صحيح. مثال: النهار `15` والشهر `8`.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        await self.cog.store_member_birthday(self.member, day, month)
        await self.cog.setup_center(interaction.guild)
        await self.cog.private_panel(
            interaction,
            "birthday-profile",
            embed=self.cog.profile_embed(self.member),
            view=None,
        )


class BirthdayMemberSelect(discord.ui.UserSelect):
    def __init__(self, cog: "BirthdayCenter"):
        super().__init__(
            placeholder="🔍 اختار الشخص اللي باغي تشوف الملف ديالو…",
            min_values=1,
            max_values=1,
        )
        self.cog = cog

    async def callback(self, interaction: discord.Interaction):
        selected = self.values[0]
        member = interaction.guild.get_member(selected.id) if interaction.guild else None
        if member is None:
            await interaction.response.send_message("❌ هاد العضو ما بقاش فالسيرفر.", ephemeral=True)
            return
        await interaction.response.edit_message(
            embed=self.cog.profile_embed(member),
            view=BirthdaySearchView(self.cog),
        )


class BirthdaySearchView(discord.ui.View):
    def __init__(self, cog: "BirthdayCenter"):
        super().__init__(timeout=180)
        self.add_item(BirthdayMemberSelect(cog))


class UpcomingBirthdaysView(discord.ui.View):
    def __init__(self, cog: "BirthdayCenter", guild: discord.Guild, page: int = 0):
        super().__init__(timeout=180)
        self.cog = cog
        self.guild = guild
        self.page = max(0, page)
        pages = max(1, ceil(len(cog.upcoming_entries(guild)) / PAGE_SIZE))
        self.previous.disabled = self.page <= 0
        self.next.disabled = self.page >= pages - 1

    @discord.ui.button(label="السابق", emoji="⬅️", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, _button: discord.ui.Button):
        page = max(0, self.page - 1)
        await interaction.response.edit_message(
            embed=self.cog.upcoming_embed(self.guild, page),
            view=UpcomingBirthdaysView(self.cog, self.guild, page),
        )

    @discord.ui.button(label="التالي", emoji="➡️", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, _button: discord.ui.Button):
        page = self.page + 1
        await interaction.response.edit_message(
            embed=self.cog.upcoming_embed(self.guild, page),
            view=UpcomingBirthdaysView(self.cog, self.guild, page),
        )


class BirthdayDeleteConfirmView(discord.ui.View):
    def __init__(self, cog: "BirthdayCenter", owner_id: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id:
            return True
        await interaction.response.send_message("❌ هاد التأكيد ماشي ديالك.", ephemeral=True)
        return False

    @discord.ui.button(label="نعم، حذف التاريخ", emoji="🗑️", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        removed = await self.cog.remove_member_birthday(interaction.user)
        await self.cog.setup_center(interaction.guild)
        text = "✅ تحيد عيد الميلاد والرول ديال البرج." if removed else "⚠️ ماعندكش عيد ميلاد مسجل."
        await interaction.edit_original_response(
            embed=discord.Embed(description=text, color=discord.Color.green() if removed else discord.Color.orange()),
            view=None,
        )

    @discord.ui.button(label="إلغاء", emoji="✖️", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=discord.Embed(description="تم الإلغاء.", color=discord.Color.light_grey()),
            view=None,
        )


class BirthdayCenterView(discord.ui.View):
    def __init__(self, cog: "BirthdayCenter"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="سجل / عدّل عيد ميلادي",
        emoji="🎂",
        style=discord.ButtonStyle.success,
        custom_id="ggmw9:birthday:set",
        row=0,
    )
    async def set_birthday(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("❌ خاص هاد الزر يتستعمل داخل السيرفر.", ephemeral=True)
            return
        await interaction.response.send_modal(BirthdayDateModal(self.cog, interaction.user))

    @discord.ui.button(
        label="الملف ديالي",
        emoji="👤",
        style=discord.ButtonStyle.primary,
        custom_id="ggmw9:birthday:profile",
        row=0,
    )
    async def my_profile(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                "❌ خاص زر الملف يتستعمل داخل السيرفر.",
                ephemeral=True,
            )
            return
        await self.cog.private_panel(
            interaction,
            "birthday-profile",
            embed=self.cog.profile_embed(interaction.user),
            view=None,
        )

    @discord.ui.button(
        label="أقرب أعياد الميلاد",
        emoji="📅",
        style=discord.ButtonStyle.primary,
        custom_id="ggmw9:birthday:upcoming",
        row=1,
    )
    async def upcoming(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await self.cog.private_panel(
            interaction,
            "birthday-upcoming",
            embed=self.cog.upcoming_embed(interaction.guild, 0),
            view=UpcomingBirthdaysView(self.cog, interaction.guild, 0),
        )

    @discord.ui.button(
        label="البحث عن عضو",
        emoji="🔍",
        style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:birthday:search",
        row=1,
    )
    async def search(self, interaction: discord.Interaction, _button: discord.ui.Button):
        embed = discord.Embed(
            title="🔍 البحث فـسجل أعياد الميلاد",
            description="اختار أي عضو من القائمة باش تشوف بطاقة عيد الميلاد ديالو.",
            color=discord.Color.blurple(),
        )
        await self.cog.private_panel(
            interaction,
            "birthday-search",
            embed=embed,
            view=BirthdaySearchView(self.cog),
        )

    @discord.ui.button(
        label="حذف عيد ميلادي",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="ggmw9:birthday:delete",
        row=1,
    )
    async def delete(self, interaction: discord.Interaction, _button: discord.ui.Button):
        if not self.cog.record(interaction.user.id):
            await interaction.response.send_message("⚠️ ماعندكش عيد ميلاد مسجل.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🗑️ حذف عيد الميلاد",
            description="واش متأكد؟ حتى رول البرج غيتحيد.",
            color=discord.Color.red(),
        )
        await self.cog.private_panel(
            interaction,
            "birthday-delete",
            embed=embed,
            view=BirthdayDeleteConfirmView(self.cog, interaction.user.id),
        )


class BirthdayGreetingView(discord.ui.View):
    def __init__(self, cog: "BirthdayCenter", count: int = 0):
        super().__init__(timeout=None)
        self.cog = cog
        self.congratulate.label = f"هنّيه / هنّيها ({max(0, int(count))})"

    @discord.ui.button(
        label="هنّيه / هنّيها (0)",
        emoji="🎉",
        style=discord.ButtonStyle.success,
        custom_id="ggmw9:birthday:congratulate",
    )
    async def congratulate(self, interaction: discord.Interaction, _button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        message_id = str(interaction.message.id)
        async with self.cog.action_lock:
            celebration = self.cog.db.setdefault("celebrations", {}).get(message_id)
            if not celebration or self.cog.celebration_expired(celebration):
                await interaction.followup.send("⌛ وقت التهاني ديال هاد العيد سالا.", ephemeral=True)
                return
            celebrants = {int(item) for item in celebration.get("member_ids", [])}
            if interaction.user.id in celebrants:
                await interaction.followup.send("🎂 اليوم الناس هوما اللي كيهنيوك!", ephemeral=True)
                return
            voters = celebration.setdefault("congratulated_by", [])
            if str(interaction.user.id) in voters:
                await interaction.followup.send("✅ راك هنيتيه/هنيتيها ديجا.", ephemeral=True)
                return
            voters.append(str(interaction.user.id))
            self.cog.save()
            count = len(voters)
            try:
                await interaction.message.edit(view=BirthdayGreetingView(self.cog, count))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
        await interaction.followup.send("💖 وصلت التهنئة ديالك، شكراً!", ephemeral=True)


class BirthdayCenter(commands.Cog):
    """Birthday profiles, midnight celebrations, exact-day role and clean panel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.gg = bot.gg
        self.db = self.gg["birthdays_db"]
        self.db.setdefault("birthdays", {})
        self.db.setdefault("role_holders", [])
        self.db.setdefault("celebrations", {})
        self.db.setdefault("panel_messages", {})
        self.timezone = ZoneInfo(self.gg.get("BIRTHDAY_TIMEZONE", "Africa/Casablanca"))
        self.utc = ZoneInfo("UTC")
        self.action_lock = asyncio.Lock()
        self._reconcile_locks: dict[int, asyncio.Lock] = {}
        self._ready_guilds: set[int] = set()
        self.birthday_clock.change_interval(
            seconds=max(15, int(self.gg.get("BIRTHDAY_CHECK_SECONDS", 30) or 30))
        )
        self.birthday_clock.start()
        self.center_sweep.start()

    def cog_unload(self):
        self.birthday_clock.cancel()
        self.center_sweep.cancel()

    def save(self):
        self.gg["save_birthdays"]()

    def now(self) -> datetime:
        return datetime.now(self.timezone)

    def record(self, user_id: int):
        return self.db.get("birthdays", {}).get(str(user_id))

    def zodiac(self, day: int, month: int):
        return self.gg["get_zodiac_sign"](day, month)

    def occurs_today(self, record: dict, now: datetime | None = None) -> bool:
        now = now or self.now()
        day, month = int(record.get("day", 0)), int(record.get("month", 0))
        if (day, month) == (now.day, now.month):
            return True
        if (day, month) != (29, 2) or (now.day, now.month) != (28, 2):
            return False
        try:
            datetime(now.year, 2, 29)
            return False
        except ValueError:
            return True

    def occurrence(self, record: dict, year: int) -> datetime:
        day, month = int(record["day"]), int(record["month"])
        try:
            return datetime(year, month, day, tzinfo=self.timezone)
        except ValueError:
            return datetime(year, 2, 28, tzinfo=self.timezone)

    def next_occurrence(self, record: dict, now: datetime | None = None) -> datetime:
        now = now or self.now()
        candidate = self.occurrence(record, now.year)
        if candidate.date() < now.date():
            candidate = self.occurrence(record, now.year + 1)
        return candidate

    @staticmethod
    def days_label(days: int) -> str:
        if days == 0:
            return "🎉 اليوم!"
        if days == 1:
            return "غداً"
        if days == 2:
            return "من بعد يومين"
        return f"من بعد {days} أيام"

    def upcoming_entries(self, guild: discord.Guild):
        now = self.now()
        entries = []
        for user_id, record in self.db.get("birthdays", {}).items():
            member = guild.get_member(int(user_id))
            if member is None:
                continue
            next_date = self.next_occurrence(record, now)
            entries.append(((next_date.date() - now.date()).days, next_date, member, record))
        entries.sort(key=lambda item: (item[0], item[2].display_name.casefold()))
        return entries

    def profile_embed(self, member: discord.Member) -> discord.Embed:
        record = self.record(member.id)
        if not record:
            embed = discord.Embed(
                title=f"🎂 {member.display_name}",
                description=f"{member.mention} مازال ما سجلش عيد الميلاد ديالو.",
                color=discord.Color.orange(),
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            return embed

        next_date = self.next_occurrence(record)
        days = (next_date.date() - self.now().date()).days
        _key, zodiac_label, zodiac_emoji = self.zodiac(record["day"], record["month"])
        embed = discord.Embed(
            title=f"🎂 ملف عيد الميلاد • {member.display_name}",
            description=f"## {member.mention}\n{self.days_label(days)}",
            color=discord.Color.from_rgb(255, 105, 180),
        )
        embed.add_field(name="📅 تاريخ الميلاد", value=f"**{record['day']:02d}/{record['month']:02d}**", inline=True)
        embed.add_field(name="✨ البرج", value=f"{zodiac_emoji} **{zodiac_label}**", inline=True)
        embed.add_field(name="⏳ الموعد القادم", value=f"<t:{int(next_date.timestamp())}:D>\n<t:{int(next_date.timestamp())}:R>", inline=False)
        if member.joined_at:
            embed.add_field(name="🏠 داخل السيرفر من", value=f"<t:{int(member.joined_at.timestamp())}:D>", inline=True)
        embed.add_field(name="🪪 الحساب تخلق فـ", value=f"<t:{int(member.created_at.timestamp())}:D>", inline=True)
        if member.top_role != member.guild.default_role:
            embed.add_field(name="🏅 أعلى رتبة", value=member.top_role.mention, inline=True)
        embed.set_thumbnail(url=member.display_avatar.replace(size=512).url)
        embed.set_footer(text=f"{self.gg['SERVER_NAME']} • Birthday ID: {member.id}")
        return embed

    def upcoming_embed(self, guild: discord.Guild, page: int = 0) -> discord.Embed:
        entries = self.upcoming_entries(guild)
        pages = max(1, ceil(len(entries) / PAGE_SIZE))
        page = min(max(0, page), pages - 1)
        selected = entries[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
        if selected:
            lines = []
            for days, _next_date, member, record in selected:
                _key, label, emoji = self.zodiac(record["day"], record["month"])
                lines.append(
                    f"**{record['day']:02d}/{record['month']:02d}** • {member.mention}\n"
                    f"└ {emoji} {label} • **{self.days_label(days)}**"
                )
            description = "\n\n".join(lines)
        else:
            description = "📭 ماكاين حتى عيد ميلاد مسجل دابا."
        embed = discord.Embed(
            title="📅 أقرب أعياد الميلاد",
            description=description,
            color=discord.Color.from_rgb(255, 105, 180),
        )
        embed.set_footer(text=f"الصفحة {page + 1}/{pages} • {len(entries)} عيد ميلاد مسجل")
        return embed

    def center_embed(self, guild: discord.Guild) -> discord.Embed:
        entries = self.upcoming_entries(guild)
        preview = []
        for days, _next_date, member, record in entries[:5]:
            preview.append(
                f"🎈 {member.mention} • **{record['day']:02d}/{record['month']:02d}** • {self.days_label(days)}"
            )
        upcoming = "\n".join(preview) if preview else "مازال ما تسجل حتى عيد ميلاد."
        embed = discord.Embed(
            title="🎂 Birthday Center • مركز أعياد الميلاد",
            description=(
                "سجّل عيد ميلادك بسهولة، شوف الملف ديالك، قلب على أي عضو، "
                "وتابع أقرب الاحتفالات. جميع النتائج الخاصة بالأزرار كيبانو غير ليك.\n\n"
                "### 🎉 الاحتفالات القريبة\n" + upcoming
            ),
            color=discord.Color.from_rgb(255, 84, 167),
        )
        embed.add_field(
            name="✨ كيفاش كيخدم؟",
            value=(
                "• الاحتفال كيبدا مع **00:00 بتوقيت المغرب**.\n"
                "• إعلان كبير كيمشي لـ **General**.\n"
                "• رول عيد الميلاد كتبقى نهار كامل.\n"
                "• نفس الشخص كيحتافل مرة وحدة فقط فكل عام."
            ),
            inline=False,
        )
        embed.set_footer(text=f"{CENTER_MARKER} • {len(entries)} عضو مسجل")
        return embed

    async def private_panel(self, interaction: discord.Interaction, key: str, **kwargs):
        """Always acknowledge the current click with a visible ephemeral panel."""
        helper = self.gg.get("upsert_ephemeral_panel")
        if callable(helper):
            return await helper(interaction, key, **kwargs)
        if not interaction.response.is_done():
            await interaction.response.send_message(ephemeral=True, **kwargs)
            try:
                return await interaction.original_response()
            except (discord.NotFound, discord.HTTPException):
                return None
        return await interaction.followup.send(ephemeral=True, wait=True, **kwargs)

    async def store_member_birthday(self, member: discord.Member, day: int, month: int):
        old = self.record(member.id) or {}
        zodiac_key, _label, _emoji = self.zodiac(day, month)
        self.db.setdefault("birthdays", {})[str(member.id)] = {
            "day": day,
            "month": month,
            "zodiac": zodiac_key,
            "last_announced_year": old.get("last_announced_year"),
            "registered_at": old.get("registered_at") or datetime.now(self.utc).isoformat(),
            "updated_at": datetime.now(self.utc).isoformat(),
        }
        self.save()
        await self.gg["sync_zodiac_role"](member, zodiac_key)
        if not self.occurs_today(self.record(member.id)):
            await self.remove_birthday_role(member)

    async def remove_birthday_role(self, member: discord.Member):
        role = member.guild.get_role(int(self.gg.get("BIRTHDAY_ROLE_ID", 0) or 0))
        if role and role in member.roles:
            try:
                await member.remove_roles(role, reason="Birthday Center: التاريخ ماشي ديال اليوم")
            except (discord.Forbidden, discord.HTTPException):
                pass
        holders = self.db.setdefault("role_holders", [])
        self.db["role_holders"] = [item for item in holders if str(item) != str(member.id)]
        self.save()

    async def remove_member_birthday(self, member: discord.Member) -> bool:
        removed = self.db.setdefault("birthdays", {}).pop(str(member.id), None)
        if not removed:
            return False
        await self.gg["sync_zodiac_role"](member, None)
        await self.remove_birthday_role(member)
        self.save()
        return True

    def is_center_message(self, message: discord.Message) -> bool:
        if not self.bot.user or message.author.id != self.bot.user.id or not message.embeds:
            return False
        footer = message.embeds[0].footer.text if message.embeds[0].footer else ""
        return CENTER_MARKER in (footer or "")

    async def setup_center(self, guild: discord.Guild):
        channel_id = int(self.gg.get("BIRTHDAY_CENTER_CHANNEL_ID", 0) or 0)
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            return None
        panel_ids = self.db.setdefault("panel_messages", {})
        saved_id = int(panel_ids.get(str(guild.id), 0) or 0)

        def persist(message_id: int):
            panel_ids[str(guild.id)] = int(message_id)
            self.save()

        return await upsert_fixed_panel(
            self.bot,
            channel,
            key="birthday-center",
            matches=self.is_center_message,
            embed=self.center_embed(guild),
            view=BirthdayCenterView(self),
            message_id=saved_id or None,
            save_message_id=persist,
            history_limit=None,
            trust_message_id=True,
        )

    async def purge_center_extras(self, guild: discord.Guild, *, full: bool) -> int:
        channel = guild.get_channel(int(self.gg.get("BIRTHDAY_CENTER_CHANNEL_ID", 0) or 0))
        if not isinstance(channel, discord.TextChannel):
            return 0
        try:
            deleted = await channel.purge(
                limit=None if full else 200,
                check=lambda message: not self.is_center_message(message),
                bulk=True,
                reason="Birthday Center: القناة مخصصة للبانل الرسمية فقط",
            )
            return len(deleted)
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[BIRTHDAY-CENTER] تعذر تنظيف {channel.id}: {exc}")
            return 0

    def gender(self, member: discord.Member) -> str:
        role_ids = {role.id for role in member.roles}
        is_boy = int(self.gg.get("BOYS_ROLE_ID", 0) or 0) in role_ids
        is_girl = int(self.gg.get("GIRLS_ROLE_ID", 0) or 0) in role_ids
        if is_boy and not is_girl:
            return "male"
        if is_girl and not is_boy:
            return "female"
        return "neutral"

    def celebration_embed(self, member: discord.Member, record: dict) -> discord.Embed:
        gender = self.gender(member)
        if gender == "male":
            message = f"اليوم **هو نجم نهارنا** ⭐ نتمنّاو ليه عام جديد عامر بالفرحة والنجاح والمحبة."
        elif gender == "female":
            message = f"اليوم **هي نجمة نهارنا** ⭐ نتمنّاو ليها عام جديد عامر بالفرحة والنجاح والمحبة."
        else:
            message = "اليوم عندنا شخص مميز كيحتافل بنهار مميز ⭐ نتمنّاو عام جديد عامر بالفرح والنجاح والمحبة."
        _key, label, emoji = self.zodiac(record["day"], record["month"])
        embed = discord.Embed(
            title=f"🎉🎂 عيد ميلاد سعيد {member.display_name}!",
            description=f"## {member.mention}\n\n{message}\n\nكاع أعضاء **{self.gg['SERVER_NAME']}** فرحانين معاك فهاد اليوم الجميل! 🥳🎈🎁",
            color=discord.Color.from_rgb(255, 73, 153),
            timestamp=self.now(),
        )
        embed.add_field(name="🎂 تاريخ الميلاد", value=f"**{record['day']:02d}/{record['month']:02d}**", inline=True)
        embed.add_field(name="✨ البرج", value=f"{emoji} **{label}**", inline=True)
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)
        embed.set_image(url=member.display_avatar.replace(size=1024).url)
        embed.set_footer(text=f"Happy Birthday • ID: {member.id}")
        return embed

    def day_expires_at(self, now: datetime | None = None) -> datetime:
        now = now or self.now()
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(self.utc)

    def celebration_expired(self, celebration: dict) -> bool:
        try:
            expires = datetime.fromisoformat(celebration["expires_at"])
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=self.utc)
            return datetime.now(self.utc) >= expires
        except (KeyError, TypeError, ValueError):
            return True

    async def sync_birthday_role(self, guild: discord.Guild, today_members: list[discord.Member]):
        role = guild.get_role(int(self.gg.get("BIRTHDAY_ROLE_ID", 0) or 0))
        if role is None:
            self.db["role_holders"] = []
            return
        today_ids = {member.id for member in today_members}
        for member in list(role.members):
            if member.id in today_ids:
                continue
            try:
                await member.remove_roles(role, reason="Birthday Center: سالا نهار عيد الميلاد")
            except (discord.Forbidden, discord.HTTPException):
                pass
        active = []
        for member in today_members:
            if role not in member.roles:
                try:
                    await member.add_roles(role, reason="Birthday Center: عيد الميلاد ديال اليوم")
                except (discord.Forbidden, discord.HTTPException):
                    continue
            active.append(str(member.id))
        self.db["role_holders"] = active

    async def send_celebrations(self, guild: discord.Guild, pending):
        channel = guild.get_channel(int(self.gg.get("BIRTHDAY_ANNOUNCE_CHANNEL_ID", 0) or 0))
        if not isinstance(channel, discord.TextChannel):
            return
        now = self.now()
        for group in _chunks(pending, 10):
            mentions = " ".join(member.mention for member, _record in group)
            if len(group) == 1:
                content = f"@everyone\n# 🎉 اليوم عندنا عيد ميلاد مميز!\n🎂 كل عام وأنت بخير {mentions}"
            else:
                content = f"@everyone\n# 🎉 اليوم عندنا أكثر من فرحة!\n🎂 كل عام وأنتم بخير {mentions}"
            embeds = [self.celebration_embed(member, record) for member, record in group]
            try:
                message = await channel.send(
                    content=content,
                    embeds=embeds,
                    view=BirthdayGreetingView(self, 0),
                    allowed_mentions=discord.AllowedMentions(everyone=True, users=True, roles=False),
                )
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[BIRTHDAY] تعذر إرسال الإعلان العام: {exc}")
                continue

            member_ids = [str(member.id) for member, _record in group]
            self.db.setdefault("celebrations", {})[str(message.id)] = {
                "guild_id": str(guild.id),
                "channel_id": str(channel.id),
                "member_ids": member_ids,
                "congratulated_by": [],
                "thread_id": None,
                "created_at": datetime.now(self.utc).isoformat(),
                "expires_at": self.day_expires_at(now).isoformat(),
            }
            for _member, record in group:
                record["last_announced_year"] = now.year
            self.save()

            try:
                names = "، ".join(member.display_name for member, _record in group)
                thread = await message.create_thread(
                    name=f"💌 دفتر التهاني • {names}"[:100],
                    auto_archive_duration=1440,
                    reason="Birthday Center: دفتر تهاني لمدة يوم",
                )
                await thread.send(
                    f"# 💌 دفتر التهاني\nكتبو هنا أحلى التمنيات لـ {mentions} 🎂💖",
                    allowed_mentions=discord.AllowedMentions(users=True, everyone=False, roles=False),
                )
                self.db["celebrations"][str(message.id)]["thread_id"] = str(thread.id)
                self.save()
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def close_expired_celebrations(self, guild: discord.Guild):
        celebrations = self.db.setdefault("celebrations", {})
        changed = False
        for message_id, celebration in list(celebrations.items()):
            if str(celebration.get("guild_id")) != str(guild.id) or not self.celebration_expired(celebration):
                continue
            thread_id = int(celebration.get("thread_id") or 0)
            thread = guild.get_thread(thread_id) if thread_id else None
            if thread:
                try:
                    await thread.edit(archived=True, locked=True, reason="Birthday Center: سالات 24 ساعة")
                except (discord.Forbidden, discord.HTTPException):
                    pass
            channel = guild.get_channel(int(celebration.get("channel_id") or 0))
            if channel:
                try:
                    message = await channel.fetch_message(int(message_id))
                    await message.edit(view=None)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
            celebrations.pop(message_id, None)
            changed = True
        if changed:
            self.save()

    async def reconcile_guild(self, guild: discord.Guild):
        lock = self._reconcile_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            await self._reconcile_guild_locked(guild)

    async def _reconcile_guild_locked(self, guild: discord.Guild):
        now = self.now()
        today = []
        pending = []
        for user_id, record in self.db.get("birthdays", {}).items():
            if not self.occurs_today(record, now):
                continue
            member = guild.get_member(int(user_id))
            if member is None:
                continue
            today.append(member)
            if record.get("last_announced_year") != now.year:
                pending.append((member, record))
        await self.sync_birthday_role(guild, today)
        await self.close_expired_celebrations(guild)
        if pending:
            await self.send_celebrations(guild, pending)
        current_date = now.date().isoformat()
        if self.db.get("last_center_refresh_date") != current_date:
            self.db["last_center_refresh_date"] = current_date
            self.save()
            await self.setup_center(guild)

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            if guild.id in self._ready_guilds:
                continue
            self._ready_guilds.add(guild.id)
            try:
                await self.setup_center(guild)
                removed = await self.purge_center_extras(guild, full=True)
                if removed:
                    print(f"[BIRTHDAY-CENTER] 🧹 تمسحو {removed} رسالة قديمة؛ بقات غير البانل.")
                await self.reconcile_guild(guild)
            except Exception as exc:
                print(f"[BIRTHDAY-CENTER] on_ready failed for {guild.id}: {type(exc).__name__}: {exc}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.channel.id != int(self.gg.get("BIRTHDAY_CENTER_CHANNEL_ID", 0) or 0):
            return
        if self.is_center_message(message):
            return
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    @tasks.loop(seconds=30)
    async def birthday_clock(self):
        for guild in self.bot.guilds:
            try:
                await self.reconcile_guild(guild)
            except Exception as exc:
                print(f"[BIRTHDAY] clock error for {guild.id}: {type(exc).__name__}: {exc}")

    @birthday_clock.before_loop
    async def before_birthday_clock(self):
        await self.bot.wait_until_ready()

    @tasks.loop(minutes=5)
    async def center_sweep(self):
        for guild in self.bot.guilds:
            await self.purge_center_extras(guild, full=False)

    @center_sweep.before_loop
    async def before_center_sweep(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    cog = BirthdayCenter(bot)
    await bot.add_cog(cog)
    bot.add_view(BirthdayCenterView(cog))
    bot.add_view(BirthdayGreetingView(cog, 0))
    print("✅ Birthday Center: بانل خاصة + 00:00 المغرب + تهاني + رول 24 ساعة")
