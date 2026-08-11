# -*- coding: utf-8 -*-
"""GGMW9 CITY businesses, construction and private appointments.

This extension deliberately reuses CareerCity's store/lock/notifier and Economy's
escrow API.  It does not register appointment rooms as Temp Voice rooms.
"""
from __future__ import annotations

import asyncio
import math
import re
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

import games_config as root_cfg
from cogs.panel_registry import upsert_fixed_panel


LAND_PRICE = 150_000
CONSTRUCTION_JOBS = (
    ("foundation", "الأساس والبنية", 6_000),
    ("interior", "التجهيز الداخلي", 5_000),
    ("technology", "الصوتيات والتقنيات", 4_000),
)
MIN_SERVICE_PRICE = 500
MAX_SERVICE_PRICE = 50_000
MIN_DURATION = 15
MAX_DURATION = 240
MIN_LEAD_MINUTES = 10
EMPTY_GRACE_SECONDS = 120
MIN_JOINT_SECONDS = 180
TERMINAL_APPOINTMENTS = {"completed", "cancelled", "rejected", "expired", "no_show", "payment_error"}
BUSINESS_TYPES = {
    "consultation": "🩺 استشارات وعيادة افتراضية",
    "education": "📚 تعليم وتدريب",
    "design": "🎨 تصميم وخدمات إبداعية",
    "agency": "💼 وكالة وخدمات رقمية",
    "media": "🎙️ إعلام وصناعة محتوى",
    "other": "🏢 مشروع خدمات افتراضية",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utcnow().isoformat()


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def clean_text(value: str, limit: int) -> str:
    value = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    value = value.replace("@everyone", "everyone").replace("@here", "here")
    value = re.sub(r"\s+", " ", value).strip()
    return value[:limit]


def slug(value: str) -> str:
    value = clean_text(value, 70).lower().replace(" ", "-")
    value = re.sub(r"[^\w\-]", "", value, flags=re.UNICODE).strip("-")
    return value[:70] or "business"


def fmt(amount: int) -> str:
    return root_cfg.fmt_money(int(amount))


async def private_reply(interaction: discord.Interaction, text: str, *, embed=None, view=None):
    kwargs = {"ephemeral": True, "allowed_mentions": discord.AllowedMentions.none()}
    if embed is not None:
        kwargs["embed"] = embed
    else:
        kwargs["content"] = text
    if view is not None:
        kwargs["view"] = view
    if interaction.response.is_done():
        return await interaction.followup.send(**kwargs)
    return await interaction.response.send_message(**kwargs)


class BuyLandModal(discord.ui.Modal, title="شراء أرض داخل GGMW9 CITY"):
    plot_id = discord.ui.TextInput(label="رقم الأرض", placeholder="PLOT-01", max_length=20)

    def __init__(self, hub):
        super().__init__()
        self.hub = hub

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, msg = await self.hub.buy_land(interaction, str(self.plot_id))
        await interaction.followup.send(msg, ephemeral=True)


class BusinessApplicationModal(discord.ui.Modal, title="طلب بناء مشروع"):
    plot_id = discord.ui.TextInput(label="رقم الأرض", placeholder="PLOT-01", max_length=20)
    name = discord.ui.TextInput(label="اسم المشروع", placeholder="عيادة ليلى", max_length=60)
    business_type = discord.ui.TextInput(label="نوع المشروع", placeholder="consultation / education / design / agency", max_length=20)
    description = discord.ui.TextInput(label="وصف الخدمات", style=discord.TextStyle.paragraph, max_length=500)
    schedule = discord.ui.TextInput(label="ساعات العمل", placeholder="18:00-23:00", max_length=80)

    def __init__(self, hub):
        super().__init__()
        self.hub = hub

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, msg = await self.hub.submit_business(
            interaction, str(self.plot_id), str(self.name), str(self.business_type),
            str(self.description), str(self.schedule),
        )
        await interaction.followup.send(msg, ephemeral=True)


class AddServiceModal(discord.ui.Modal, title="إضافة خدمة للمشروع"):
    business_id = discord.ui.TextInput(label="رقم المشروع", placeholder="BIZ-000001", max_length=30)
    name = discord.ui.TextInput(label="اسم الخدمة", placeholder="استشارة خاصة", max_length=70)
    price = discord.ui.TextInput(label="الثمن بالدولار", placeholder="25.00", max_length=12)
    duration = discord.ui.TextInput(label="المدة بالدقائق", placeholder="60", max_length=4)
    description = discord.ui.TextInput(label="تفاصيل الخدمة", style=discord.TextStyle.paragraph, max_length=500)

    def __init__(self, hub):
        super().__init__()
        self.hub = hub

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, msg = await self.hub.add_service(
            interaction, str(self.business_id), str(self.name), str(self.price),
            str(self.duration), str(self.description),
        )
        await interaction.followup.send(msg, ephemeral=True)


class BookAppointmentModal(discord.ui.Modal, title="حجز خدمة"):
    business_id = discord.ui.TextInput(label="رقم المشروع", placeholder="BIZ-000001", max_length=30)
    service_id = discord.ui.TextInput(label="رقم الخدمة", placeholder="SVC-001", max_length=30)
    when = discord.ui.TextInput(label="الموعد بتوقيت UTC", placeholder="2026-08-12 20:30", max_length=25)
    note = discord.ui.TextInput(label="ملاحظة لصاحب المشروع", required=False, style=discord.TextStyle.paragraph, max_length=400)

    def __init__(self, hub):
        super().__init__()
        self.hub = hub

    async def on_submit(self, interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        ok, msg = await self.hub.book_appointment(
            interaction, str(self.business_id), str(self.service_id), str(self.when), str(self.note),
        )
        await interaction.followup.send(msg, ephemeral=True)


_BUSINESS_BTN_LABELS = {
    "darija": {"land": "شراء أرض", "apply": "فتح مشروع", "book": "حجز خدمة", "add_service": "إضافة خدمة",
               "listing": "المشاريع والخدمات", "jobs": "أشغال البناء", "not_verified": "❌ خاصك تفعل الحساب ديالك أولاً."},
    "en": {"land": "Buy Land", "apply": "Open a Venture", "book": "Book a Service", "add_service": "Add a Service",
           "listing": "Ventures & Services", "jobs": "Construction Jobs", "not_verified": "❌ You need to verify your account first."},
    "fr": {"land": "Acheter un terrain", "apply": "Ouvrir une entreprise", "book": "Réserver un service", "add_service": "Ajouter un service",
           "listing": "Entreprises & Services", "jobs": "Chantiers", "not_verified": "❌ Il faut d'abord vérifier ton compte."},
}


class _BusinessLanguageSelect(discord.ui.Select):
    """بانل عمومي بالدارجة بشكل ثابت — اختيار اللغة كيحل نسخة خاصة مترجمة (نفس نمط بانل الزواج)."""
    def __init__(self, hub, *, private_user_id: int = None, lang: str = "darija", row: int = 1):
        self.hub = hub
        self.private_user_id = private_user_id
        lang = lang if lang in {"darija", "en", "fr"} else "darija"
        super().__init__(
            placeholder="🌐 اللغة / Language / Langue",
            options=[
                discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", default=lang == "darija"),
                discord.SelectOption(label="English", value="en", emoji="🇬🇧", default=lang == "en"),
                discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", default=lang == "fr"),
            ],
            min_values=1, max_values=1, row=row,
            custom_id=None if private_user_id else "ggmw9:business:directory:language",
        )

    async def callback(self, interaction: discord.Interaction):
        if self.private_user_id and interaction.user.id != self.private_user_id:
            await interaction.response.send_message("❌ هاد الترجمة ماشي ديالك.", ephemeral=True)
            return
        lang = self.hub.set_lang(interaction.guild.id, interaction.user.id, self.values[0])
        embed = self.hub.directory_embed(interaction.guild, lang)
        view = _BusinessDirectoryPrivateView(self.hub, interaction.user.id, lang)
        if self.private_user_id:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class BusinessDirectoryView(discord.ui.View):
    def __init__(self, hub):
        super().__init__(timeout=None)
        self.hub = hub
        self.add_item(_BusinessLanguageSelect(hub, row=2))

    @discord.ui.button(label="شراء أرض", emoji="🏞️", style=discord.ButtonStyle.success, custom_id="ggmw9:business:land", row=0)
    async def land(self, interaction, button):
        if not self.hub.verified(interaction.user):
            return await private_reply(interaction, "❌ خاصك تفعل الحساب ديالك أولاً.")
        await interaction.response.send_modal(BuyLandModal(self.hub))

    @discord.ui.button(label="فتح مشروع", emoji="🏢", style=discord.ButtonStyle.primary, custom_id="ggmw9:business:apply", row=0)
    async def apply(self, interaction, button):
        if not self.hub.verified(interaction.user):
            return await private_reply(interaction, "❌ خاصك تفعل الحساب ديالك أولاً.")
        await interaction.response.send_modal(BusinessApplicationModal(self.hub))

    @discord.ui.button(label="حجز خدمة", emoji="📅", style=discord.ButtonStyle.primary, custom_id="ggmw9:business:book", row=0)
    async def book(self, interaction, button):
        if not self.hub.verified(interaction.user):
            return await private_reply(interaction, "❌ خاصك تفعل الحساب ديالك أولاً.")
        await interaction.response.send_modal(BookAppointmentModal(self.hub))

    @discord.ui.button(label="إضافة خدمة", emoji="➕", style=discord.ButtonStyle.secondary, custom_id="ggmw9:business:add_service", row=1)
    async def add_service(self, interaction, button):
        if not self.hub.verified(interaction.user):
            return await private_reply(interaction, "❌ خاصك تفعل الحساب ديالك أولاً.")
        await interaction.response.send_modal(AddServiceModal(self.hub))

    @discord.ui.button(label="المشاريع والخدمات", emoji="📋", style=discord.ButtonStyle.secondary, custom_id="ggmw9:business:list", row=1)
    async def listing(self, interaction, button):
        await private_reply(interaction, "", embed=self.hub.listing_embed(interaction.guild))

    @discord.ui.button(label="أشغال البناء", emoji="🏗️", style=discord.ButtonStyle.secondary, custom_id="ggmw9:business:jobs", row=1)
    async def jobs(self, interaction, button):
        await private_reply(interaction, "", embed=self.hub.jobs_embed(interaction.guild))


class _BusinessDirectoryPrivateView(discord.ui.View):
    """نسخة خاصة (ephemeral) مترجمة — نفس الأزرار بلغة مختلفة."""
    def __init__(self, hub, user_id: int, lang: str = "darija"):
        super().__init__(timeout=1800)
        self.hub = hub
        self.user_id = int(user_id)
        self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
        labels = _BUSINESS_BTN_LABELS[self.lang]

        land_btn = discord.ui.Button(label=labels["land"], emoji="🏞️", style=discord.ButtonStyle.success, row=0)
        land_btn.callback = self._land
        self.add_item(land_btn)

        apply_btn = discord.ui.Button(label=labels["apply"], emoji="🏢", style=discord.ButtonStyle.primary, row=0)
        apply_btn.callback = self._apply
        self.add_item(apply_btn)

        book_btn = discord.ui.Button(label=labels["book"], emoji="📅", style=discord.ButtonStyle.primary, row=0)
        book_btn.callback = self._book
        self.add_item(book_btn)

        add_service_btn = discord.ui.Button(label=labels["add_service"], emoji="➕", style=discord.ButtonStyle.secondary, row=1)
        add_service_btn.callback = self._add_service
        self.add_item(add_service_btn)

        listing_btn = discord.ui.Button(label=labels["listing"], emoji="📋", style=discord.ButtonStyle.secondary, row=1)
        listing_btn.callback = self._listing
        self.add_item(listing_btn)

        jobs_btn = discord.ui.Button(label=labels["jobs"], emoji="🏗️", style=discord.ButtonStyle.secondary, row=1)
        jobs_btn.callback = self._jobs
        self.add_item(jobs_btn)

        self.add_item(_BusinessLanguageSelect(hub, private_user_id=self.user_id, lang=self.lang, row=2))

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.", ephemeral=True)
            return False
        return True

    async def _need_verify(self, interaction: discord.Interaction) -> bool:
        if not self.hub.verified(interaction.user):
            await private_reply(interaction, _BUSINESS_BTN_LABELS[self.lang]["not_verified"])
            return True
        return False

    async def _land(self, interaction):
        if not await self._guard(interaction) or await self._need_verify(interaction):
            return
        await interaction.response.send_modal(BuyLandModal(self.hub))

    async def _apply(self, interaction):
        if not await self._guard(interaction) or await self._need_verify(interaction):
            return
        await interaction.response.send_modal(BusinessApplicationModal(self.hub))

    async def _book(self, interaction):
        if not await self._guard(interaction) or await self._need_verify(interaction):
            return
        await interaction.response.send_modal(BookAppointmentModal(self.hub))

    async def _add_service(self, interaction):
        if not await self._guard(interaction) or await self._need_verify(interaction):
            return
        await interaction.response.send_modal(AddServiceModal(self.hub))

    async def _listing(self, interaction):
        if not await self._guard(interaction):
            return
        await private_reply(interaction, "", embed=self.hub.listing_embed(interaction.guild, self.lang))

    async def _jobs(self, interaction):
        if not await self._guard(interaction):
            return
        await private_reply(interaction, "", embed=self.hub.jobs_embed(interaction.guild, self.lang))


class AppointmentRoomView(discord.ui.View):
    def __init__(self, hub, appointment_id: str):
        super().__init__(timeout=None)
        self.hub = hub
        self.appointment_id = appointment_id
        for item in self.children:
            item.custom_id = f"{item.custom_id}:{appointment_id}"[:100]

    async def interaction_check(self, interaction):
        apt = self.hub.appointments(interaction.guild.id).get(self.appointment_id)
        if not apt or interaction.user.id not in {int(apt["owner_id"]), int(apt["customer_id"])}:
            await private_reply(interaction, "❌ هاد التحكم غير للزبون وصاحب المشروع.")
            return False
        if not self.hub.verified(interaction.user):
            await private_reply(interaction, "❌ خاص الحساب ديالك يبقى مفعّل.")
            return False
        return True

    @discord.ui.button(label="سالينا الجلسة", emoji="✅", style=discord.ButtonStyle.success, custom_id="ggmw9:apt:end")
    async def end(self, interaction, button):
        await interaction.response.defer(ephemeral=True)
        ok, msg = await self.hub.confirm_end(interaction.guild, self.appointment_id, interaction.user.id)
        await interaction.followup.send(msg, ephemeral=True)

    @discord.ui.button(label="عرض الوقت", emoji="⏳", style=discord.ButtonStyle.secondary, custom_id="ggmw9:apt:time")
    async def timer(self, interaction, button):
        apt = self.hub.appointments(interaction.guild.id).get(self.appointment_id) or {}
        end = parse_dt(apt.get("end_at"))
        left = max(0, int((end - utcnow()).total_seconds())) if end else 0
        await private_reply(interaction, f"⏳ باقي تقريباً **{math.ceil(left / 60)} دقيقة**.")


class BusinessHub(commands.Cog):
    """Legal virtual businesses with construction, services and appointments."""

    def __init__(self, bot):
        self.bot = bot
        self._ready = False

    @property
    def city(self):
        return self.bot.get_cog("CareerCity")

    @property
    def economy(self):
        return self.bot.get_cog("Economy")

    def lang(self, guild_id: int, user_id: int) -> str:
        getter = (getattr(self.bot, "gg", {}) or {}).get("get_panel_language")
        if getter:
            try:
                value = getter(guild_id, user_id)
                if value in {"darija", "en", "fr"}:
                    return value
            except Exception:
                pass
        return "darija"

    def set_lang(self, guild_id: int, user_id: int, lang: str) -> str:
        lang = lang if lang in {"darija", "en", "fr"} else "darija"
        setter = (getattr(self.bot, "gg", {}) or {}).get("set_panel_language")
        if setter:
            try:
                return setter(guild_id, user_id, lang)
            except Exception:
                pass
        return lang

    @property
    def store(self):
        return self.city.store

    @property
    def lock(self):
        return self.city.lock

    def state(self, guild_id: int) -> dict:
        g = self.store.guild(guild_id)
        state = g.setdefault("business_hub", {})
        state.setdefault("setup", {})
        state.setdefault("plots", {})
        state.setdefault("businesses", {})
        state.setdefault("appointments", {})
        state.setdefault("rooms", {})
        state.setdefault("counters", {"business": 1, "service": 1, "appointment": 1, "job": 1})
        if not state["plots"]:
            for i in range(1, 13):
                state["plots"][f"PLOT-{i:02d}"] = {"id": f"PLOT-{i:02d}", "status": "available", "owner_id": None}
        return state

    def businesses(self, guild_id):
        return self.state(guild_id)["businesses"]

    def appointments(self, guild_id):
        return self.state(guild_id)["appointments"]

    def next_id(self, guild_id: int, key: str, prefix: str) -> str:
        counters = self.state(guild_id)["counters"]
        n = int(counters.get(key, 1) or 1)
        counters[key] = n + 1
        return f"{prefix}-{guild_id}-{n:06d}"

    def verified(self, member) -> bool:
        if not isinstance(member, discord.Member):
            return False
        uid = int((getattr(self.bot, "gg", {}) or {}).get("UNVERIFIED_ROLE_ID") or 0)
        return not uid or all(role.id != uid for role in member.roles)

    def is_admin(self, member) -> bool:
        return isinstance(member, discord.Member) and (member.guild_permissions.administrator or member.guild_permissions.manage_guild)

    async def notify(self, guild, user_id: int, text: str):
        member = guild.get_member(int(user_id))
        if member:
            try:
                await member.send(text, allowed_mentions=discord.AllowedMentions.none())
                return
            except (discord.Forbidden, discord.HTTPException):
                pass
        if member:
            await self.city.notifier.send(guild, member, "عندك تحديث جديد متعلق بالمشروع أو الموعد.", kind="projects")

    def parse_money(self, text: str) -> int:
        return int(round(float(str(text).replace(",", ".")) * 100))

    async def cog_load(self):
        if not self.city or not self.economy:
            raise RuntimeError("BusinessHub requires CareerCity and Economy")
        self.bot.add_view(BusinessDirectoryView(self))
        self.business_tick.start()

    async def cog_unload(self):
        self.business_tick.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready:
            return
        self._ready = True
        for guild in self.bot.guilds:
            try:
                await self.ensure_infrastructure(guild)
                await self.reconcile(guild)
            except Exception as exc:
                print(f"[BUSINESS] ready failed in {guild.id}: {exc}")

    async def ensure_infrastructure(self, guild: discord.Guild):
        state = self.state(guild.id)
        setup = state["setup"]
        category = guild.get_channel(int(setup.get("category_id") or 0))
        if not isinstance(category, discord.CategoryChannel):
            category = discord.utils.get(guild.categories, name="🏢・CITY BUSINESSES")
        if not category:
            category = await guild.create_category("🏢・CITY BUSINESSES", reason="GGMW9 CITY businesses")

        channel = guild.get_channel(int(setup.get("directory_channel_id") or 0))
        if not isinstance(channel, discord.TextChannel):
            channel = discord.utils.get(category.text_channels, name="business-directory")
        if not channel:
            channel = await guild.create_text_channel("business-directory", category=category, reason="GGMW9 CITY directory")

        private = guild.get_channel(int(setup.get("appointment_category_id") or 0))
        if not isinstance(private, discord.CategoryChannel):
            private = discord.utils.get(guild.categories, name="🔒・CITY APPOINTMENTS")
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, send_messages=True, manage_channels=True),
        }
        uid = int((getattr(self.bot, "gg", {}) or {}).get("UNVERIFIED_ROLE_ID") or 0)
        unverified = guild.get_role(uid) if uid else None
        if unverified:
            overwrites[unverified] = discord.PermissionOverwrite(view_channel=False, connect=False)
        if not private:
            private = await guild.create_category("🔒・CITY APPOINTMENTS", overwrites=overwrites, reason="Private appointments")
        else:
            for target, overwrite in overwrites.items():
                await private.set_permissions(target, overwrite=overwrite, reason="Repair private appointment access")

        setup.update({"category_id": category.id, "directory_channel_id": channel.id, "appointment_category_id": private.id})
        self.store.save()
        await self.refresh_directory(guild)
        return channel

    def directory_embed(self, guild, lang="darija"):
        state = self.state(guild.id)
        free = sum(1 for p in state["plots"].values() if p["status"] == "available")
        active = sum(1 for b in state["businesses"].values() if b["status"] == "active")
        pending = sum(1 for b in state["businesses"].values() if b["status"] in {"permit_pending", "construction"})
        if lang == "en":
            title = "🏙️ GGMW9 CITY — Private Ventures"
            desc = (
                "Buy land, go through the permit and construction process, then open your real venture inside the city.\n"
                "Services are settled through Escrow, and appointments open a private room that closes automatically."
            )
            f_free, f_active, f_pending, f_price = "🏞️ Available Plots", "🏢 Open Ventures", "🏗️ In Progress", "Land Price"
            f_default_name, f_default_val = "Default Venture", "Services must be deliverable inside Discord via voice or digital content."
        elif lang == "fr":
            title = "🏙️ GGMW9 CITY — Entreprises privées"
            desc = (
                "Achète un terrain, passe par le permis et la construction, puis ouvre ta vraie entreprise dans la ville.\n"
                "Les services se règlent via Escrow, et les rendez-vous ouvrent une salle privée qui se ferme automatiquement."
            )
            f_free, f_active, f_pending, f_price = "🏞️ Terrains disponibles", "🏢 Entreprises ouvertes", "🏗️ En cours", "Prix du terrain"
            f_default_name, f_default_val = "Entreprise par défaut", "Les services doivent être livrables sur Discord, via voix ou contenu numérique."
        else:
            title = "🏙️ GGMW9 CITY — المشاريع الخاصة"
            desc = (
                "شري الأرض، دوز من الترخيص والبناء، ومن بعد افتح مشروعك الحقيقي داخل المدينة.\n"
                "الخدمات كتتخلص بالـEscrow، والمواعيد كتفتح ليها غرفة خاصة كتسد تلقائياً."
            )
            f_free, f_active, f_pending, f_price = "🏞️ الأراضي المتاحة", "🏢 المشاريع المفتوحة", "🏗️ قيد الإجراءات", "ثمن الأرض"
            f_default_name, f_default_val = "المشروع الافتراضي", "الخدمات خاصها تكون قابلة للتقديم داخل Discord بالصوت أو المحتوى الرقمي."
        e = discord.Embed(title=title, color=0x2B7FFF)
        e.description = desc
        e.add_field(name=f_free, value=str(free), inline=True)
        e.add_field(name=f_active, value=str(active), inline=True)
        e.add_field(name=f_pending, value=str(pending), inline=True)
        e.add_field(name=f_price, value=fmt(LAND_PRICE), inline=True)
        e.add_field(name=f_default_name, value=f_default_val, inline=False)
        e.set_footer(text="GGMW9:BUSINESS:DIRECTORY")
        return e

    async def refresh_directory(self, guild):
        setup = self.state(guild.id)["setup"]
        channel = guild.get_channel(int(setup.get("directory_channel_id") or 0))
        if not isinstance(channel, discord.TextChannel):
            return
        msg = await upsert_fixed_panel(
            self.bot, channel, key="city_business_directory", embed=self.directory_embed(guild),
            view=BusinessDirectoryView(self),
            matches=lambda m: bool(m.author.id == self.bot.user.id and m.embeds and m.embeds[0].footer and m.embeds[0].footer.text == "GGMW9:BUSINESS:DIRECTORY"),
            history_limit=None,
        )
        if msg:
            setup["directory_message_id"] = msg.id
            self.store.save()

    def listing_embed(self, guild, lang="darija"):
        if lang == "en":
            title, no_service, no_items = "📋 Available Ventures & Services", "No service added yet", "No open venture right now."
        elif lang == "fr":
            title, no_service, no_items = "📋 Entreprises et services disponibles", "Aucun service ajouté pour l'instant", "Aucune entreprise ouverte pour l'instant."
        else:
            title, no_service, no_items = "📋 المشاريع والخدمات المتاحة", "مازال ما تزادت خدمة", "ما كاين حتى مشروع مفتوح دابا."
        e = discord.Embed(title=title, color=0x57F287)
        rows = []
        for bid, b in self.businesses(guild.id).items():
            if b["status"] != "active":
                continue
            services = b.get("services", {})
            srv = ", ".join(f"`{sid}` {s['name']} ({fmt(s['price'])})" for sid, s in list(services.items())[:4]) or no_service
            rows.append(f"**{b['name']}** • `{bid}`\n{srv}")
        e.description = "\n\n".join(rows[:15]) or no_items
        return e

    def jobs_embed(self, guild, lang="darija"):
        if lang == "en":
            title, no_items, footer = "🏗️ Open Construction Jobs", "No open job right now.", "Use /businessjobapply JOB-ID to apply"
        elif lang == "fr":
            title, no_items, footer = "🏗️ Chantiers de construction ouverts", "Aucun chantier ouvert pour l'instant.", "Utilise /businessjobapply JOB-ID pour postuler"
        else:
            title, no_items, footer = "🏗️ أوراش البناء المفتوحة", "ما كاين حتى ورش مفتوح دابا.", "استعمل /businessjobapply JOB-ID باش تقدم"
        e = discord.Embed(title=title, color=0xFEE75C)
        rows = []
        for b in self.businesses(guild.id).values():
            for jid, job in b.get("jobs", {}).items():
                if job["status"] in {"open", "assigned"}:
                    rows.append(f"`{jid}` • **{job['name']}** • {fmt(job['amount'])} • `{job['status']}`")
        e.description = "\n".join(rows[:20]) or no_items
        e.set_footer(text=footer)
        return e

    async def buy_land(self, interaction, plot_id):
        if not interaction.guild or not self.verified(interaction.user):
            return False, "❌ خاص الحساب يكون مفعّل."
        plot_id = clean_text(plot_id, 20).upper()
        async with self.lock:
            plot = self.state(interaction.guild.id)["plots"].get(plot_id)
            if not plot:
                return False, "❌ رقم الأرض غير صحيح."
            if plot["status"] != "available":
                return False, "❌ هاد الأرض مملوكة ديجا."
            if any(int(p.get("owner_id") or 0) == interaction.user.id for p in self.state(interaction.guild.id)["plots"].values()):
                return False, "❌ عندك أرض ديجا؛ كمل المشروع ديالك الأول."
            if not self.economy.spend(interaction.guild.id, interaction.user.id, LAND_PRICE):
                return False, f"❌ خاصك {fmt(LAND_PRICE)} فالـWallet."
            plot.update({"status": "owned", "owner_id": interaction.user.id, "bought_at": iso_now()})
            self.store.save()
        await self.notify(interaction.guild, interaction.user.id, f"🏞️ مبروك! شريتي الأرض {plot_id}. دابا قدم طلب بناء المشروع من البانل.")
        await self.refresh_directory(interaction.guild)
        return True, f"✅ شريتي **{plot_id}** بـ **{fmt(LAND_PRICE)}**. دابا دير طلب فتح المشروع."

    async def submit_business(self, interaction, plot_id, name, business_type, description, schedule):
        if not interaction.guild or not self.verified(interaction.user):
            return False, "❌ خاص الحساب يكون مفعّل."
        plot_id = clean_text(plot_id, 20).upper()
        name = clean_text(name, 60)
        business_type = clean_text(business_type, 20).lower()
        if business_type not in BUSINESS_TYPES:
            return False, "❌ النوع خاصو يكون: consultation / education / design / agency / media / other"
        if len(name) < 3 or len(clean_text(description, 500)) < 20:
            return False, "❌ الاسم أو الوصف قصير بزاف."
        async with self.lock:
            state = self.state(interaction.guild.id)
            plot = state["plots"].get(plot_id)
            if not plot or int(plot.get("owner_id") or 0) != interaction.user.id:
                return False, "❌ هاد الأرض ماشي ديالك."
            if plot["status"] != "owned":
                return False, "❌ كاين طلب/مشروع مربوط بهاد الأرض ديجا."
            bid = self.next_id(interaction.guild.id, "business", "BIZ")
            state["businesses"][bid] = {
                "id": bid, "plot_id": plot_id, "owner_id": interaction.user.id,
                "name": name, "type": business_type, "description": clean_text(description, 500),
                "schedule": clean_text(schedule, 80), "status": "permit_pending", "created_at": iso_now(),
                "services": {}, "jobs": {}, "channel_id": None,
            }
            plot["status"] = "permit_pending"
            self.store.save()
        await self.notify(interaction.guild, interaction.user.id, f"📑 تسجل طلب المشروع {bid}. الإدارة خاصها تراجعه دابا.")
        await self.refresh_directory(interaction.guild)
        return True, f"✅ الطلب `{bid}` تسجل. من بعد موافقة الإدارة غادي يفتحو أوراش البناء."

    async def review_business(self, guild, admin, business_id, approve: bool):
        if not self.is_admin(admin):
            return False, "❌ خاصك Manage Server."
        async with self.lock:
            b = self.businesses(guild.id).get(business_id)
            if not b or b["status"] != "permit_pending":
                return False, "❌ الطلب ما لقيتوش أو تراجع ديجا."
            if not approve:
                b["status"] = "rejected"
                self.state(guild.id)["plots"][b["plot_id"]]["status"] = "owned"
                self.store.save()
                owner_id = int(b["owner_id"])
            else:
                held = []
                for key, label, amount in CONSTRUCTION_JOBS:
                    jid = self.next_id(guild.id, "job", "JOB")
                    escrow = f"business:construction:{jid}"
                    if not self.economy.city_hold_escrow(guild.id, int(b["owner_id"]), escrow, amount, kind="business_construction", description=f"{business_id} {label}"):
                        for old in held:
                            self.economy.city_refund_escrow(guild.id, old, reason="Construction setup rollback")
                        return False, "❌ Wallet ديال مول المشروع ما كافياش لمصاريف البناء."
                    held.append(escrow)
                    b["jobs"][jid] = {"id": jid, "key": key, "name": label, "amount": amount, "status": "open", "applicants": [], "worker_id": None, "escrow_key": escrow}
                b["status"] = "construction"
                self.state(guild.id)["plots"][b["plot_id"]]["status"] = "construction"
                b["approved_by"] = admin.id
                b["approved_at"] = iso_now()
                self.store.save()
                owner_id = int(b["owner_id"])
        await self.notify(guild, owner_id, f"{'✅ تقبل المشروع وبدات مرحلة البناء.' if approve else '❌ ترفض طلب المشروع. الأرض بقات ديالك وتقدر تعاود الطلب.'}")
        await self.refresh_directory(guild)
        return True, "✅ القرار تسجل وتم إشعار مول المشروع فالـDM."

    def find_job(self, guild_id, job_id):
        for b in self.businesses(guild_id).values():
            if job_id in b.get("jobs", {}):
                return b, b["jobs"][job_id]
        return None, None

    async def apply_job(self, guild, member, job_id):
        if not self.verified(member):
            return False, "❌ خاص الحساب يكون مفعّل."
        async with self.lock:
            b, job = self.find_job(guild.id, job_id)
            if not job or job["status"] != "open":
                return False, "❌ الورش ماشي مفتوح."
            if member.id == int(b["owner_id"]):
                return False, "❌ مول المشروع ما يقدرش يخدم ورشو بوحدو."
            if member.id not in job["applicants"]:
                job["applicants"].append(member.id)
                self.store.save()
        await self.notify(guild, int(b["owner_id"]), f"🏗️ {member.display_name} قدم على الورش {job_id}. استعمل /businessjobassign {job_id} @member")
        return True, "✅ تسجل طلبك ومول المشروع توصّل بإشعار."

    async def assign_job(self, guild, owner, job_id, worker):
        if not self.verified(owner) or not self.verified(worker):
            return False, "❌ الحسابات خاصها تكون مفعّلة."
        async with self.lock:
            b, job = self.find_job(guild.id, job_id)
            if not job or int(b["owner_id"]) != owner.id:
                return False, "❌ الورش ماشي تابع لمشروعك."
            if job["status"] != "open" or worker.id not in job["applicants"]:
                return False, "❌ العامل ما قدمش لهاد الورش أو الورش تسند ديجا."
            job.update({"status": "assigned", "worker_id": worker.id, "assigned_at": iso_now()})
            self.store.save()
        await self.notify(guild, worker.id, f"✅ تقبلتي فالورش {job_id}: {job['name']}. منين تسالي استعمل /businessjobdone {job_id}")
        return True, "✅ تسند الورش وتم إشعار العامل."

    async def complete_job(self, guild, worker, job_id):
        if not self.verified(worker):
            return False, "❌ خاص الحساب يكون مفعّل."
        async with self.lock:
            b, job = self.find_job(guild.id, job_id)
            if not job or int(job.get("worker_id") or 0) != worker.id or job["status"] != "assigned":
                return False, "❌ ما عندكش هاد الورش أو الحالة غير صحيحة."
            job.update({"status": "delivered", "delivered_at": iso_now()})
            self.store.save()
        await self.notify(guild, int(b["owner_id"]), f"🏗️ العامل سالا {job_id}. راجع الخدمة واستعمل /businessjobapprove {job_id}")
        return True, "✅ تسجل أن الخدمة سالات ومول المشروع توصّل بإشعار."

    async def approve_job(self, guild, owner, job_id):
        async with self.lock:
            b, job = self.find_job(guild.id, job_id)
            if not job or int(b["owner_id"]) != owner.id or job["status"] != "delivered":
                return False, "❌ الورش ماشي جاهز للموافقة."
            res = self.economy.city_release_project_escrow(guild.id, job["escrow_key"], worker_id=int(job["worker_id"]), release_amount=int(job["amount"]), tax_bps=500, description=f"Construction {job_id}")
            if int(res.get("gross", 0)) <= 0:
                return False, "❌ تعذر أداء العامل؛ تاصل بالإدارة وما تعاودش العملية."
            job.update({"status": "approved", "approved_at": iso_now()})
            ready = all(j["status"] == "approved" for j in b["jobs"].values())
            if ready:
                b["status"] = "activating"
            self.store.save()
        await self.notify(guild, int(job["worker_id"]), f"💰 تقبل الورش {job_id} وتخلصتي {fmt(res['worker'])} فالبنك.")
        if ready:
            await self.activate_business(guild, b["id"])
        return True, "✅ تخلص العامل." + (" المشروع تحل دابا." if ready else "")

    async def activate_business(self, guild, business_id):
        async with self.lock:
            b = self.businesses(guild.id).get(business_id)
            if not b or b["status"] not in {"activating", "active"}:
                return False
            category = guild.get_channel(int(self.state(guild.id)["setup"].get("category_id") or 0))
            existing = guild.get_channel(int(b.get("channel_id") or 0))
            if not isinstance(existing, discord.TextChannel):
                existing = discord.utils.get(category.text_channels if category else [], topic=f"GGMW9-BUSINESS:{business_id}")
            if not existing:
                owner = guild.get_member(int(b["owner_id"]))
                overwrites = {guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=False)}
                if owner and self.verified(owner):
                    overwrites[owner] = discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_messages=True)
                existing = await guild.create_text_channel(slug(b["name"]), category=category, topic=f"GGMW9-BUSINESS:{business_id}", overwrites=overwrites, reason="Business construction completed")
            b.update({"status": "active", "channel_id": existing.id, "activated_at": b.get("activated_at") or iso_now()})
            self.state(guild.id)["plots"][b["plot_id"]]["status"] = "active"
            self.store.save()
        await self.refresh_business_panel(guild, business_id)
        await self.notify(guild, int(b["owner_id"]), f"🎉 المشروع ديالك {b['name']} تحل رسمياً: {existing.mention}")
        await self.refresh_directory(guild)
        return True

    def business_embed(self, b):
        e = discord.Embed(title=f"🏢 {b['name']}", description=b["description"], color=0x5865F2)
        e.add_field(name="النوع", value=BUSINESS_TYPES.get(b["type"], b["type"]), inline=True)
        e.add_field(name="ساعات العمل", value=b["schedule"], inline=True)
        lines = [f"`{sid}` • **{s['name']}** — {fmt(s['price'])} / {s['duration']} دقيقة\n{s['description']}" for sid, s in b.get("services", {}).items() if s.get("active", True)]
        e.add_field(name="الخدمات", value="\n\n".join(lines[:10]) or "مازال ما تزادت خدمات.", inline=False)
        e.set_footer(text=f"GGMW9:BUSINESS:{b['id']} • الحجز من Business Directory")
        return e

    async def refresh_business_panel(self, guild, business_id):
        b = self.businesses(guild.id).get(business_id)
        channel = guild.get_channel(int((b or {}).get("channel_id") or 0))
        if not b or not isinstance(channel, discord.TextChannel):
            return
        msg = await upsert_fixed_panel(self.bot, channel, key=f"business_{business_id}", embed=self.business_embed(b), matches=lambda m: bool(m.author.id == self.bot.user.id and m.embeds and m.embeds[0].footer and f"GGMW9:BUSINESS:{business_id}" in (m.embeds[0].footer.text or "")), history_limit=None)
        if msg:
            b["panel_message_id"] = msg.id
            self.store.save()

    async def add_service(self, interaction, business_id, name, price_text, duration_text, description):
        if not interaction.guild or not self.verified(interaction.user):
            return False, "❌ خاص الحساب يكون مفعّل."
        try:
            price = self.parse_money(price_text)
            duration = int(duration_text)
        except (ValueError, TypeError):
            return False, "❌ الثمن أو المدة غير صحيحة."
        if not MIN_SERVICE_PRICE <= price <= MAX_SERVICE_PRICE or not MIN_DURATION <= duration <= MAX_DURATION:
            return False, f"❌ الثمن بين {fmt(MIN_SERVICE_PRICE)} و{fmt(MAX_SERVICE_PRICE)}، والمدة بين {MIN_DURATION} و{MAX_DURATION} دقيقة."
        async with self.lock:
            b = self.businesses(interaction.guild.id).get(clean_text(business_id, 30))
            if not b or b["status"] != "active" or int(b["owner_id"]) != interaction.user.id:
                return False, "❌ المشروع ماشي ديالك أو مازال ما تحلش."
            sid = self.next_id(interaction.guild.id, "service", "SVC")
            b["services"][sid] = {"id": sid, "name": clean_text(name, 70), "price": price, "duration": duration, "description": clean_text(description, 500), "active": True}
            self.store.save()
        await self.refresh_business_panel(interaction.guild, b["id"])
        await self.refresh_directory(interaction.guild)
        return True, f"✅ تزادت الخدمة `{sid}` للبانل الدائمة ديال المشروع."

    def parse_when(self, text):
        text = text.strip().replace("T", " ")
        for pattern in ("%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M"):
            try:
                return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return None

    async def book_appointment(self, interaction, business_id, service_id, when_text, note):
        if not interaction.guild or not self.verified(interaction.user):
            return False, "❌ خاص الحساب يكون مفعّل."
        start = self.parse_when(when_text)
        if not start or start < utcnow() + timedelta(minutes=MIN_LEAD_MINUTES):
            return False, "❌ الموعد خاصو يكون بصيغة `YYYY-MM-DD HH:MM` وبـ10 دقايق على الأقل من دابا (UTC)."
        async with self.lock:
            b = self.businesses(interaction.guild.id).get(clean_text(business_id, 30))
            service = (b or {}).get("services", {}).get(clean_text(service_id, 30))
            if not b or b["status"] != "active" or not service or not service.get("active", True):
                return False, "❌ المشروع أو الخدمة ما لقيتهاش."
            if int(b["owner_id"]) == interaction.user.id:
                return False, "❌ ما تقدرش تحجز خدمتك لنفسك."
            end = start + timedelta(minutes=int(service["duration"]))
            for apt in self.appointments(interaction.guild.id).values():
                if apt["status"] in TERMINAL_APPOINTMENTS:
                    continue
                a, z = parse_dt(apt.get("start_at")), parse_dt(apt.get("end_at"))
                same_person = interaction.user.id in {int(apt["customer_id"]), int(apt["owner_id"])} or int(b["owner_id"]) in {int(apt["customer_id"]), int(apt["owner_id"])}
                if same_person and a and z and start < z and end > a:
                    return False, "❌ كاين موعد آخر متداخل للزبون أو لصاحب المشروع."
            aid = self.next_id(interaction.guild.id, "appointment", "APT")
            escrow = f"business:appointment:{aid}"
            if not self.economy.city_hold_escrow(interaction.guild.id, interaction.user.id, escrow, int(service["price"]), kind="business_appointment", description=f"{aid} {service['name']}"):
                return False, "❌ Wallet ما كافياش أو تعذر حجز المبلغ."
            self.appointments(interaction.guild.id)[aid] = {
                "id": aid, "business_id": b["id"], "service_id": service["id"], "service_name": service["name"],
                "owner_id": int(b["owner_id"]), "customer_id": interaction.user.id, "price": int(service["price"]),
                "start_at": start.isoformat(), "end_at": end.isoformat(), "status": "pending_owner", "escrow_key": escrow,
                "note": clean_text(note, 400), "created_at": iso_now(), "room_id": None, "panel_message_id": None,
                "joint_seconds": 0, "end_confirmations": [], "empty_since": None,
            }
            self.store.save()
        await self.notify(interaction.guild, int(b["owner_id"]), f"📅 طلب موعد `{aid}` لخدمة {service['name']} يوم <t:{int(start.timestamp())}:F>. وافق بـ /businessappointmentapprove {aid} أو ارفض بـ /businessappointmentreject {aid}")
        await self.notify(interaction.guild, interaction.user.id, f"🔒 تحجز {fmt(service['price'])} فالـEscrow للموعد `{aid}`. كتسنى موافقة مول المشروع.")
        return True, f"✅ طلب الموعد `{aid}` تسجل والمبلغ فـEscrow حتى تكمل الخدمة."

    async def decide_appointment(self, guild, owner, appointment_id, approve):
        async with self.lock:
            apt = self.appointments(guild.id).get(appointment_id)
            if not apt or apt["status"] != "pending_owner" or int(apt["owner_id"]) != owner.id:
                return False, "❌ الطلب ما لقيتوش أو ماشي ديالك."
            if not approve:
                amount = self.economy.city_refund_escrow(guild.id, apt["escrow_key"], reason=f"Appointment rejected {appointment_id}")
                apt.update({"status": "rejected", "closed_at": iso_now()})
                self.store.save()
                customer = int(apt["customer_id"])
            else:
                if parse_dt(apt["start_at"]) <= utcnow():
                    amount = self.economy.city_refund_escrow(guild.id, apt["escrow_key"], reason="Appointment approval too late")
                    apt.update({"status": "expired", "closed_at": iso_now()})
                    self.store.save()
                    customer = int(apt["customer_id"])
                    approve = False
                else:
                    apt.update({"status": "confirmed", "approved_at": iso_now()})
                    self.store.save()
                    customer = int(apt["customer_id"])
                    amount = 0
        if approve:
            await self.notify(guild, customer, f"✅ تقبل الموعد `{appointment_id}`. غادي توصلك الغرفة الخاصة فوقتها.")
            return True, "✅ تقبل الموعد وتم إشعار الزبون."
        await self.notify(guild, customer, f"↩️ الموعد `{appointment_id}` ما تقبلش ورجع ليك {fmt(amount)} للـWallet.")
        return True, "✅ ترفض/تقادا الطلب ورجع المبلغ للزبون."

    async def create_appointment_room(self, guild, apt):
        owner = guild.get_member(int(apt["owner_id"]))
        customer = guild.get_member(int(apt["customer_id"]))
        if not owner or not customer or not self.verified(owner) or not self.verified(customer):
            return None
        category = guild.get_channel(int(self.state(guild.id)["setup"].get("appointment_category_id") or 0))
        if not isinstance(category, discord.CategoryChannel):
            return None
        existing = guild.get_channel(int(apt.get("room_id") or 0))
        if isinstance(existing, discord.VoiceChannel):
            return existing
        marker = apt["id"].lower()
        existing = next((c for c in category.voice_channels if marker in c.name.lower()), None)
        if existing:
            return existing
        ow = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, send_messages=True, manage_channels=True),
            owner: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, stream=True, send_messages=True, read_message_history=True),
            customer: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, stream=True, send_messages=True, read_message_history=True),
        }
        uid = int((getattr(self.bot, "gg", {}) or {}).get("UNVERIFIED_ROLE_ID") or 0)
        role = guild.get_role(uid) if uid else None
        if role:
            ow[role] = discord.PermissionOverwrite(view_channel=False, connect=False)
        return await guild.create_voice_channel(f"🩺・{apt['id']}-session", category=category, overwrites=ow, reason="Scheduled private business appointment")

    async def start_appointment(self, guild, apt):
        room = await self.create_appointment_room(guild, apt)
        if not room:
            return False
        async with self.lock:
            current = self.appointments(guild.id).get(apt["id"])
            if not current or current["status"] not in {"confirmed", "starting", "live"}:
                return False
            current.update({"status": "live", "room_id": room.id, "started_at": current.get("started_at") or iso_now()})
            self.state(guild.id)["rooms"][str(room.id)] = current["id"]
            self.store.save()
        end = parse_dt(apt["end_at"])
        embed = discord.Embed(title=f"🔒 جلسة خاصة — {apt['service_name']}", color=0x2B7FFF)
        embed.description = f"الزبون: <@{apt['customer_id']}>\nصاحب المشروع: <@{apt['owner_id']}>\nالنهاية: <t:{int(end.timestamp())}:R>"
        embed.add_field(name="الحماية", value="المبلغ باقٍ فالـEscrow حتى تكمّل الجلسة. الغرفة كتسد تلقائياً.", inline=False)
        embed.set_footer(text=f"GGMW9:APPOINTMENT:{apt['id']}")
        view = AppointmentRoomView(self, apt["id"])
        msg = await room.send(embed=embed, view=view, allowed_mentions=discord.AllowedMentions.none())
        async with self.lock:
            apt = self.appointments(guild.id).get(apt["id"])
            if apt:
                apt["panel_message_id"] = msg.id
                self.store.save()
        self.bot.add_view(view, message_id=msg.id)
        await self.notify(guild, int(apt["owner_id"]), f"🔔 بدات الجلسة `{apt['id']}`: {room.mention}")
        await self.notify(guild, int(apt["customer_id"]), f"🔔 بدات الجلسة `{apt['id']}`: {room.mention}")
        return True

    async def close_room(self, guild, apt):
        room = guild.get_channel(int(apt.get("room_id") or 0))
        if room:
            try:
                await room.delete(reason=f"Appointment closed {apt['id']}")
            except (discord.Forbidden, discord.HTTPException):
                return False
        async with self.lock:
            self.state(guild.id)["rooms"].pop(str(apt.get("room_id") or 0), None)
            apt["room_id"] = None
            self.store.save()
        return True

    async def finish_appointment(self, guild, appointment_id, *, no_show=False):
        async with self.lock:
            apt = self.appointments(guild.id).get(appointment_id)
            if not apt or apt["status"] in TERMINAL_APPOINTMENTS:
                return False, "الموعد تسد ديجا."
            if no_show or int(apt.get("joint_seconds", 0)) < MIN_JOINT_SECONDS:
                amount = self.economy.city_refund_escrow(guild.id, apt["escrow_key"], reason=f"Appointment no-show {appointment_id}")
                apt.update({"status": "no_show", "closed_at": iso_now()})
                result = (False, amount)
            else:
                res = self.economy.city_release_service_escrow(guild.id, apt["escrow_key"], worker_id=int(apt["owner_id"]), business_id=apt["business_id"], worker_share_bps=9500, tax_bps=500, description=f"Appointment {appointment_id}")
                if int(res.get("gross", 0)) <= 0:
                    return False, "تعذر تسوية المبلغ؛ تاصل بالإدارة."
                apt.update({"status": "completed", "closed_at": iso_now()})
                result = (True, int(res.get("worker", 0)))
            self.store.save()
        await self.close_room(guild, apt)
        if result[0]:
            await self.notify(guild, int(apt["owner_id"]), f"💰 كمل الموعد `{appointment_id}` ودخل {fmt(result[1])} للبنك.")
            await self.notify(guild, int(apt["customer_id"]), f"✅ تسد الموعد `{appointment_id}` وتأكد الأداء.")
            return True, "✅ سالات الجلسة وتطلق الأداء."
        await self.notify(guild, int(apt["customer_id"]), f"↩️ الموعد `{appointment_id}` تسد بلا جلسة كاملة ورجع {fmt(result[1])} للـWallet.")
        return True, "↩️ تسد الموعد ورجع المبلغ للزبون."

    async def confirm_end(self, guild, appointment_id, user_id):
        async with self.lock:
            apt = self.appointments(guild.id).get(appointment_id)
            if not apt or apt["status"] != "live":
                return False, "❌ الموعد ماشي Live."
            if int(apt.get("joint_seconds", 0)) < MIN_JOINT_SECONDS:
                return False, "⏳ خاص الجلسة تجمع 3 دقايق على الأقل بجوج داخل الروم."
            confirmations = apt.setdefault("end_confirmations", [])
            if user_id not in confirmations:
                confirmations.append(user_id)
            ready = {int(apt["owner_id"]), int(apt["customer_id"])}.issubset(set(confirmations))
            self.store.save()
        if not ready:
            other = int(apt["customer_id"]) if user_id == int(apt["owner_id"]) else int(apt["owner_id"])
            await self.notify(guild, other, f"✅ الطرف الآخر أكد نهاية `{appointment_id}`. دخل للروم وأكد حتى نطلقو الأداء.")
            return True, "✅ تسجل التأكيد ديالك، باقينا كنتسناو الطرف الآخر."
        return await self.finish_appointment(guild, appointment_id)

    async def reconcile(self, guild):
        await self.ensure_infrastructure(guild)
        for b in list(self.businesses(guild.id).values()):
            if b["status"] == "active":
                if not isinstance(guild.get_channel(int(b.get("channel_id") or 0)), discord.TextChannel):
                    b["status"] = "activating"
                    self.store.save()
                    await self.activate_business(guild, b["id"])
                else:
                    await self.refresh_business_panel(guild, b["id"])
        for apt in list(self.appointments(guild.id).values()):
            if apt["status"] == "live" and apt.get("panel_message_id"):
                try:
                    self.bot.add_view(AppointmentRoomView(self, apt["id"]), message_id=int(apt["panel_message_id"]))
                except Exception:
                    pass

    @tasks.loop(seconds=60)
    async def business_tick(self):
        for guild in self.bot.guilds:
            now = utcnow()
            for apt in list(self.appointments(guild.id).values()):
                status = apt["status"]
                start, end = parse_dt(apt.get("start_at")), parse_dt(apt.get("end_at"))
                if status == "pending_owner" and start and now >= start:
                    async with self.lock:
                        amount = self.economy.city_refund_escrow(guild.id, apt["escrow_key"], reason="Appointment request expired")
                        apt.update({"status": "expired", "closed_at": iso_now()})
                        self.store.save()
                    await self.notify(guild, int(apt["customer_id"]), f"↩️ تقادا طلب `{apt['id']}` بلا موافقة ورجع {fmt(amount)}.")
                elif status in {"confirmed", "starting"} and start and end:
                    if now >= end:
                        await self.finish_appointment(guild, apt["id"], no_show=True)
                    elif now >= start:
                        apt["status"] = "starting"
                        self.store.save()
                        await self.start_appointment(guild, apt)
                elif status == "live" and end:
                    room = guild.get_channel(int(apt.get("room_id") or 0))
                    owner = guild.get_member(int(apt["owner_id"]))
                    customer = guild.get_member(int(apt["customer_id"]))
                    if not room or not owner or not customer or not self.verified(owner) or not self.verified(customer):
                        await self.finish_appointment(guild, apt["id"], no_show=int(apt.get("joint_seconds", 0)) < MIN_JOINT_SECONDS)
                        continue
                    ids = {m.id for m in room.members if not m.bot}
                    if {owner.id, customer.id}.issubset(ids):
                        apt["joint_seconds"] = int(apt.get("joint_seconds", 0)) + 60
                        apt["empty_since"] = None
                        self.store.save()
                    elif not ids:
                        empty = parse_dt(apt.get("empty_since"))
                        if not empty:
                            apt["empty_since"] = iso_now(); self.store.save()
                        elif (now - empty).total_seconds() >= EMPTY_GRACE_SECONDS:
                            await self.finish_appointment(guild, apt["id"], no_show=int(apt.get("joint_seconds", 0)) < MIN_JOINT_SECONDS)
                            continue
                    else:
                        apt["empty_since"] = None
                    if now >= end:
                        await self.finish_appointment(guild, apt["id"], no_show=int(apt.get("joint_seconds", 0)) < MIN_JOINT_SECONDS)

    @business_tick.before_loop
    async def before_business_tick(self):
        await self.bot.wait_until_ready()

    @commands.hybrid_command(name="businesssetup", description="Setup GGMW9 CITY businesses")
    @commands.has_guild_permissions(manage_guild=True)
    async def businesssetup(self, ctx):
        await ctx.defer(ephemeral=True)
        channel = await self.ensure_infrastructure(ctx.guild)
        await ctx.send(f"✅ Business Hub واجد: {channel.mention}", ephemeral=True)

    @commands.hybrid_command(name="businessreview", description="Approve/reject a business application")
    @commands.has_guild_permissions(manage_guild=True)
    async def businessreview(self, ctx, business_id: str, decision: str):
        await ctx.defer(ephemeral=True)
        ok, msg = await self.review_business(ctx.guild, ctx.author, business_id, decision.lower() in {"approve", "accept", "yes", "نعم", "قبول"})
        await ctx.send(msg, ephemeral=True)

    @commands.hybrid_command(name="businessjobapply", description="Apply for a construction job")
    async def businessjobapply(self, ctx, job_id: str):
        ok, msg = await self.apply_job(ctx.guild, ctx.author, job_id)
        await ctx.send(msg, ephemeral=True)

    @commands.hybrid_command(name="businessjobassign", description="Assign your construction job")
    async def businessjobassign(self, ctx, job_id: str, worker: discord.Member):
        ok, msg = await self.assign_job(ctx.guild, ctx.author, job_id, worker)
        await ctx.send(msg, ephemeral=True)

    @commands.hybrid_command(name="businessjobdone", description="Mark construction work delivered")
    async def businessjobdone(self, ctx, job_id: str):
        ok, msg = await self.complete_job(ctx.guild, ctx.author, job_id)
        await ctx.send(msg, ephemeral=True)

    @commands.hybrid_command(name="businessjobapprove", description="Approve delivered construction work")
    async def businessjobapprove(self, ctx, job_id: str):
        ok, msg = await self.approve_job(ctx.guild, ctx.author, job_id)
        await ctx.send(msg, ephemeral=True)

    @commands.hybrid_command(name="businessappointmentapprove", description="Approve a customer appointment")
    async def businessappointmentapprove(self, ctx, appointment_id: str):
        ok, msg = await self.decide_appointment(ctx.guild, ctx.author, appointment_id, True)
        await ctx.send(msg, ephemeral=True)

    @commands.hybrid_command(name="businessappointmentreject", description="Reject a customer appointment")
    async def businessappointmentreject(self, ctx, appointment_id: str):
        ok, msg = await self.decide_appointment(ctx.guild, ctx.author, appointment_id, False)
        await ctx.send(msg, ephemeral=True)


async def setup(bot):
    await bot.add_cog(BusinessHub(bot))
