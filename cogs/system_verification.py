# -*- coding: utf-8 -*-
"""Verification, roles, rules, and blacklist panels.

Extracted mechanically from the legacy ai_bot.py.  Runtime state is attached
to bot_core's shared namespace so existing cross-system references keep the
same object identity and startup order.
"""

import bot_core as core

core.attach_namespace(globals())


async def setup_verify_message(guild: discord.Guild):
    """Refresh the existing verification message in-place; create it only if missing."""
    verify_channel = bot.get_channel(VERIFY_CHANNEL_ID)
    if not verify_channel:
        return False

    embed = discord.Embed(
        title="✅ تفعيل العضوية",
        description=(
            f"**مرحبا بيك فـ {SERVER_NAME}!**\n\n"
            f"قبل ما تقدر/ي تهضر/ي فالسيرفر، خاصك توافق/ي على القوانين.\n\n"
            f"**الخطوات:**\n"
            f"1️⃣ قرا/ي القوانين فـ <#{RULES_CHANNEL_ID}>\n"
            f"2️⃣ كليك/ي على ✅ تحت\n\n"
            f"**ملاحظة:** إلا ما وافقتيش، ما غاديش تقدر/ي تهضر/ي ولا تفاعل/ي!"
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text="GGMW9 | Verification System")

    matches = []
    try:
        async for message in verify_channel.history(limit=30):
            if message.author != bot.user:
                continue
            title = message.embeds[0].title if message.embeds else ""
            if title == "✅ تفعيل العضوية":
                matches.append(message)
    except discord.Forbidden:
        return False

    try:
        if matches:
            keep = matches[0]
            await keep.edit(embed=embed)
            try:
                # Keep the classic ✅ reaction verification fresh as well.
                if not any(str(r.emoji) == "✅" for r in keep.reactions):
                    await keep.add_reaction("✅")
            except (discord.Forbidden, discord.HTTPException):
                pass
            for extra in matches[1:]:
                try:
                    await extra.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
        else:
            keep = await verify_channel.send(embed=embed)
            await keep.add_reaction("✅")
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


# ═══════════════════════════════════════════════════════
# ║   نظام القوانين + التفعيل بالأزرار (Buttons)           ║
# ║   (كيبان مباشرة تحت القوانين، بحال المواقع)              ║
# ═══════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════
# ║   اختيار اللغة حسب لغة تطبيق الديسكورد ديال المستخدم    ║
# ═══════════════════════════════════════════════════════

def get_user_lang(interaction: discord.Interaction) -> str:
    """
    كيحدد اللغة المناسبة اعتماداً على interaction.locale (لغة تطبيق
    الديسكورد ديال المستخدم لي ضغط على الزر). ماشي كاع اللغات مدعومة،
    فكنرجعو لـ 'ar' (دارجة/عربية) كافتراضي.
    """
    locale = str(interaction.locale) if interaction.locale else ""
    if locale.startswith("fr"):
        return "fr"
    if locale.startswith("en"):
        return "en"
    return "ar"


def t(interaction: discord.Interaction, ar: str, en: str, fr: str) -> str:
    """كيرجع النص بلغة الديسكورد ديال المستخدم لي دار الـ interaction"""
    lang = get_user_lang(interaction)
    return {"ar": ar, "en": en, "fr": fr}[lang]


class GenderSelectView(discord.ui.View):
    """View كتبان بعد التفعيل مباشرة، فيها زوج أزرار: ولد / بنت"""

    def __init__(self, target_user_id: int, guild_id: int):
        super().__init__(timeout=300)  # 5 دقايق باش يختار، من بعد كتسالا
        self.target_user_id = target_user_id
        self.guild_id = guild_id

    async def _assign_gender_role(self, interaction: discord.Interaction, role_id: int, other_role_id: int, label: str):
        if interaction.user.id != self.target_user_id:
            await interaction.response.send_message("❌ هاد الاختيار ماشي ديالك!", ephemeral=True)
            return

        guild = bot.get_guild(self.guild_id)
        if not guild:
            await interaction.response.send_message("❌ وقع مشكل، عاود من جديد.", ephemeral=True)
            return
        member = guild.get_member(interaction.user.id)
        if not member:
            await interaction.response.send_message("❌ ما لقيتكش فالسيرفر.", ephemeral=True)
            return

        if not role_id:
            await interaction.response.send_message(
                "❌ ماكاينش role ديال هاد الاختيار، بلغ الإدارة (خاص `BOYS_ROLE_ID`/`GIRLS_ROLE_ID` يتعمرو فـ CONFIG).",
                ephemeral=True
            )
            return

        role = guild.get_role(role_id)
        other_role = guild.get_role(other_role_id) if other_role_id else None

        try:
            if other_role and other_role in member.roles:
                await member.remove_roles(other_role)
            if role:
                await member.add_roles(role)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ ما قدرتش نعطيك الرول، بلغ الإدارة (البوت ماعندوش صلاحية — تحقق من ترتيب الرولات بـ `/checkroles`).",
                ephemeral=True
            )
            return

        for child in self.children:
            child.disabled = True

        blacklist_note = (
            f"\n\n📌 قبل ما تبدا/ي تهضر/ي، خاصك تقرا/ي الممنوعات والعقوبات فـ <#{BLACKLIST_CHANNEL_ID}>"
            if BLACKLIST_CHANNEL_ID else ""
        )
        success_text = f"✅ تم اختيارك: **{label}**{blacklist_note}\n\n🎉 دابا تقدر/ي تدخل/ي لكاع القنوات المسموحة!"

        try:
            await interaction.response.edit_message(content=success_text, embed=None, view=self)
        except Exception:
            await interaction.response.send_message(success_text, ephemeral=True)

        await log_action(
            guild,
            "🚻 اختيار الجنس",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**الاختيار:** {label}",
            discord.Color.blurple()
        )

    @discord.ui.button(label="ولد", emoji="👦", style=discord.ButtonStyle.primary)
    async def boy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_gender_role(interaction, BOYS_ROLE_ID, GIRLS_ROLE_ID, "ولد 👦")

    @discord.ui.button(label="بنت", emoji="👧", style=discord.ButtonStyle.secondary)
    async def girl_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_gender_role(interaction, GIRLS_ROLE_ID, BOYS_ROLE_ID, "بنت 👧")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        import traceback
        print(f"[GENDER VIEW ERROR] {error}")
        traceback.print_exc()
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ وقع مشكل تقني، حاول عاود من بعد شوية ولا بلغ الإدارة.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ وقع مشكل تقني، حاول عاود من بعد شوية ولا بلغ الإدارة.", ephemeral=True)
        except Exception:
            pass


class RoleCategorySelect(discord.ui.Select):
    """Select menu واحد كيمثل مجموعة (category) وحدة من PICK_ROLES.
    العضو يقدر يختار عدة خيارات مرة وحدة (multi-select)."""

    def __init__(self, category_name: str, roles_list: list):
        self.category_name = category_name
        # {role_id: label} باش نستعملوها ملي كيوصل اختيار جديد
        self.role_map = {r["role_id"]: r["label"] for r in roles_list if r["role_id"]}

        options = [
            discord.SelectOption(
                label=r["label"],
                emoji=r["emoji"] or None,
                value=str(r["role_id"]),
            )
            for r in roles_list if r["role_id"]
        ]

        super().__init__(
            placeholder=f"اختار من: {category_name}",
            min_values=0,
            max_values=len(options) if options else 1,
            options=options,
            custom_id=f"pickroles_select_{category_name}",
            disabled=not options,
        )

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        if not guild or not isinstance(member, discord.Member):
            await interaction.response.send_message("❌ وقع مشكل، حاول عاود.", ephemeral=True)
            return

        selected_ids = {int(v) for v in self.values}
        all_ids = set(self.role_map.keys())

        added, removed, failed = [], [], []

        for role_id in all_ids:
            role = guild.get_role(role_id)
            if not role:
                continue
            has_it = role in member.roles
            wants_it = role_id in selected_ids
            try:
                if wants_it and not has_it:
                    await member.add_roles(role)
                    added.append(role.name)
                elif has_it and not wants_it:
                    await member.remove_roles(role)
                    removed.append(role.name)
            except discord.Forbidden:
                failed.append(role.name)

        parts = []
        if added:
            parts.append("✅ تزادو: " + ", ".join(added))
        if removed:
            parts.append("🔄 تنزعو: " + ", ".join(removed))
        if failed:
            parts.append("❌ ما قدرتش نعطي (صلاحية): " + ", ".join(failed))
        if not parts:
            parts.append("مافيش تغيير.")

        await interaction.response.send_message("\n".join(parts), ephemeral=True)


class RolePickerView(discord.ui.View):
    """View فيها Select menu واحد لكل category فـ PICK_ROLES.
    Persistent (timeout=None) باش تبقى خدامة حتى بعد ريستارت البوت."""

    def __init__(self):
        super().__init__(timeout=None)
        for category_name, roles_list in PICK_ROLES.items():
            valid = [r for r in roles_list if r["role_id"]]
            if valid:
                self.add_item(RoleCategorySelect(category_name, valid))



def _rules_body(lang: str = "darija") -> str:
    """Return only one language section from SERVER_RULES without changing verify logic."""
    lang = lang if lang in {"darija", "en", "fr"} else "darija"
    markers = {
        "darija": "**🇲🇦 بالدارجة:**",
        "en": "**🇬🇧 English:**",
        "fr": "**🇫🇷 Français :**",
    }
    order = ["darija", "en", "fr"]
    raw = SERVER_RULES
    marker = markers[lang]
    start = raw.find(marker)
    if start < 0:
        return raw
    start += len(marker)
    end = len(raw)
    idx = order.index(lang)
    for nxt in order[idx + 1:]:
        pos = raw.find(markers[nxt], start)
        if pos >= 0:
            end = min(end, pos)
    return raw[start:end].strip()


def _build_rules_translation_embed(guild: discord.Guild, lang: str = "darija") -> discord.Embed:
    lang = lang if lang in {"darija", "en", "fr"} else "darija"
    if lang == "en":
        title = "📜 Server Rules — English"
        note = "This is your private Rules panel. The ✅ Agree / ❌ Refuse buttons below use the same real verification and kick system as the public panel."
        footer = "Private translation • You can switch language as often as you want"
    elif lang == "fr":
        title = "📜 Règles du serveur — Français"
        note = "Ceci est ton panneau privé. Les boutons ✅ Accepter / ❌ Refuser ci-dessous utilisent exactement le même système réel de vérification et d’expulsion."
        footer = "Traduction privée • Tu peux changer de langue autant de fois que tu veux"
    else:
        title = "📜 قوانين السيرفر — الدارجة"
        note = "هادي النسخة الخاصة ديالك. أزرار ✅ كنوافق / ❌ كنرفض لتحت خدامين بنفس آلية التفعيل والطرد الحقيقية ديال الرسالة الأصلية."
        footer = "ترجمة خاصة • تقدر تبدل اللغة بلا حد"
    embed = discord.Embed(
        title=title,
        description=f"{_rules_body(lang)}\n\n> {note}",
        color=discord.Color.blue(),
        timestamp=datetime.now(),
    )
    if guild and guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=footer)
    return embed


def _rules_lang_text(lang: str, darija: str, en: str, fr: str) -> str:
    lang = lang if lang in {"darija", "en", "fr"} else "darija"
    return {"darija": darija, "en": en, "fr": fr}[lang]


def _rules_member_is_exempt(member: discord.Member) -> bool:
    if member.id == OWNER_ID:
        return True
    return any(role.id in EXEMPT_ROLE_IDS for role in member.roles)


async def _rules_private_status(interaction: discord.Interaction, text: str, color: discord.Color):
    embed = discord.Embed(description=text, color=color, timestamp=datetime.now())
    await interaction.response.edit_message(content=None, embed=embed, view=None)


async def _handle_rules_agree(interaction: discord.Interaction, lang: str = "darija", *, private_panel: bool = False):
    """One source of truth for BOTH the public Rules buttons and translated private buttons."""
    lang = lang if lang in {"darija", "en", "fr"} else "darija"
    member = interaction.user
    guild = interaction.guild
    if not guild or not isinstance(member, discord.Member):
        msg = _rules_lang_text(lang, "❌ وقع مشكل، عاود من جديد.", "❌ Something went wrong. Please try again.", "❌ Une erreur est survenue. Réessaie.")
        if private_panel:
            await _rules_private_status(interaction, msg, discord.Color.red())
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    member_role = guild.get_role(MEMBER_ROLE_ID)
    unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)

    if member_role and member_role in member.roles:
        msg = _rules_lang_text(lang, "✅ راك مفعل من قبل، مرحبا بيك!", "✅ You're already verified. Welcome!", "✅ Tu es déjà vérifié(e). Bienvenue !")
        if private_panel:
            await _rules_private_status(interaction, msg, discord.Color.green())
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    if unverified_role and unverified_role in member.roles:
        try:
            await member.remove_roles(unverified_role, reason="GGMW9 Rules verification accepted")
        except discord.Forbidden:
            pass

    if member_role:
        try:
            await member.add_roles(member_role, reason="GGMW9 Rules verification accepted")
        except discord.Forbidden:
            msg = _rules_lang_text(
                lang,
                "❌ ما قدرتش نفعلك. بلغ الإدارة: Role ديال البوت خاصها تكون فوق Role ديال Member.",
                "❌ I couldn't verify you. Please contact staff: the bot role must be above the Member role.",
                "❌ Impossible de te vérifier. Contacte le staff : le rôle du bot doit être au-dessus du rôle Member.",
            )
            if private_panel:
                await _rules_private_status(interaction, msg, discord.Color.red())
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            await log_action(
                guild,
                "⚠️ فشل التفعيل (صلاحية)",
                f"**المستخدم:** {member.mention} ({member.name})\n"
                "**السبب:** bot role ماعندهاش الصلاحية/الترتيب باش تعطي Member role.",
                discord.Color.orange(),
            )
            return

    success = _rules_lang_text(
        lang,
        f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك 🎉",
        f"✅ You're verified in **{SERVER_NAME}**! Welcome 🎉",
        f"✅ Tu es vérifié(e) dans **{SERVER_NAME}** ! Bienvenue 🎉",
    )
    if private_panel:
        await _rules_private_status(interaction, success, discord.Color.green())
    else:
        await interaction.response.send_message(success, ephemeral=True)

    await log_action(
        guild,
        "✅ تفعيل (زر القوانين)",
        f"**المستخدم:** {member.mention} ({member.name})\n**الحالة:** وافق على القوانين وتفعل",
        discord.Color.green(),
    )

    gender_embed = discord.Embed(
        title=_rules_lang_text(lang, "🚻 واش نتا/نتي ولد ولا بنت؟", "🚻 Are you a boy or a girl?", "🚻 Es-tu un garçon ou une fille ?"),
        description=_rules_lang_text(lang, "ضغط/ي على الزر المناسب باش نعطيوك الرول الصحيح.", "Choose the correct button to receive the right role.", "Choisis le bon bouton pour recevoir le rôle correspondant."),
        color=discord.Color.blurple(),
    )
    try:
        await interaction.followup.send(
            embed=gender_embed,
            view=GenderSelectView(target_user_id=member.id, guild_id=guild.id),
            ephemeral=True,
        )
    except (discord.HTTPException, discord.NotFound):
        pass


async def _handle_rules_refuse(interaction: discord.Interaction, lang: str = "darija", *, private_panel: bool = False):
    """Same kick logic whether Refuse is clicked on public or translated private Rules."""
    lang = lang if lang in {"darija", "en", "fr"} else "darija"
    member = interaction.user
    guild = interaction.guild
    if not guild or not isinstance(member, discord.Member):
        msg = _rules_lang_text(lang, "❌ وقع مشكل، عاود من جديد.", "❌ Something went wrong. Please try again.", "❌ Une erreur est survenue. Réessaie.")
        if private_panel:
            await _rules_private_status(interaction, msg, discord.Color.red())
        else:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    if _rules_member_is_exempt(member):
        await interaction.response.send_message(
            _rules_lang_text(
                lang,
                "⚠️ راك أدمن/مشرف، ماغاديش نطردك. للأعضاء العاديين هاد الزر = رفض القوانين والطرد.",
                "⚠️ You're an admin/moderator, so you won't be kicked. For regular members this button rejects the rules and kicks them.",
                "⚠️ Tu es admin/modérateur, donc tu ne seras pas expulsé(e). Pour un membre normal, ce bouton refuse les règles et l'expulse.",
            ),
            ephemeral=True,
        )
        return

    reject_msg = _rules_lang_text(
        lang,
        "❌ رفضتي القوانين، غادي تتطرد من السيرفر...",
        "❌ You refused the rules. You will be kicked from the server...",
        "❌ Tu as refusé les règles. Tu vas être expulsé(e) du serveur...",
    )
    try:
        if private_panel:
            await _rules_private_status(interaction, reject_msg, discord.Color.red())
        else:
            await interaction.response.send_message(reject_msg, ephemeral=True)
    except Exception:
        pass

    try:
        await member.send(
            _rules_lang_text(
                lang,
                f"❌ رفضتي القوانين ديال **{SERVER_NAME}**، تم طردك من السيرفر تلقائياً.",
                f"❌ You refused the rules of **{SERVER_NAME}** and were automatically kicked.",
                f"❌ Tu as refusé les règles de **{SERVER_NAME}** et tu as été automatiquement expulsé(e).",
            )
        )
    except Exception:
        pass

    await log_action(
        guild,
        "🚫 رفض القوانين + طرد تلقائي",
        f"**المستخدم:** {member.mention} ({member.name})\n**ID:** `{member.id}`\n**السبب:** رفض الموافقة على القوانين (زر ❌)",
        discord.Color.red(),
    )
    try:
        await guild.kick(member, reason="رفض الموافقة على قوانين السيرفر")
    except discord.Forbidden:
        await log_action(
            guild,
            "⚠️ فشل الطرد",
            f"ماقدرتش نطرد {member.mention} — البوت ماعندوش صلاحية كافية.",
            discord.Color.orange(),
        )


class RulesPrivateLanguageSelect(discord.ui.Select):
    def __init__(self, user_id: int, lang: str = "darija"):
        self.user_id = int(user_id)
        self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
        super().__init__(
            placeholder="🌐 اللغة / Language / Langue",
            options=[
                discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", default=self.lang == "darija"),
                discord.SelectOption(label="English", value="en", emoji="🇬🇧", default=self.lang == "en"),
                discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", default=self.lang == "fr"),
            ],
            min_values=1,
            max_values=1,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ هاد الترجمة ماشي ديالك.", ephemeral=True)
            return
        lang = set_panel_language(interaction.guild.id if interaction.guild else 0, interaction.user.id, self.values[0])
        await interaction.response.edit_message(
            embed=_build_rules_translation_embed(interaction.guild, lang),
            view=RulesPrivateLanguageView(interaction.user.id, lang),
        )


class RulesPrivateLanguageView(discord.ui.View):
    """Private translated Rules with fully localized verify/refuse buttons."""
    def __init__(self, user_id: int, lang: str = "darija"):
        super().__init__(timeout=1800)
        self.user_id = int(user_id)
        self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
        labels = {
            "darija": ("✅ كنوافق", "❌ كنرفض"),
            "en": ("✅ I Agree", "❌ I Refuse"),
            "fr": ("✅ J'accepte", "❌ Je refuse"),
        }[self.lang]
        agree = discord.ui.Button(label=labels[0], style=discord.ButtonStyle.success, row=0)
        refuse = discord.ui.Button(label=labels[1], style=discord.ButtonStyle.danger, row=0)
        agree.callback = self._agree
        refuse.callback = self._refuse
        self.add_item(agree)
        self.add_item(refuse)
        self.add_item(RulesPrivateLanguageSelect(user_id, self.lang))

    async def _guard(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                _rules_lang_text(self.lang, "❌ هاد النسخة ماشي ديالك.", "❌ This panel isn't yours.", "❌ Ce panneau ne t'appartient pas."),
                ephemeral=True,
            )
            return False
        return True

    async def _agree(self, interaction: discord.Interaction):
        if await self._guard(interaction):
            await _handle_rules_agree(interaction, self.lang, private_panel=True)

    async def _refuse(self, interaction: discord.Interaction):
        if await self._guard(interaction):
            await _handle_rules_refuse(interaction, self.lang, private_panel=True)


class RulesLanguageSelect(discord.ui.Select):
    """Public mini selector. Every use opens a brand-new private Rules panel."""
    def __init__(self):
        super().__init__(
            placeholder="🌐 ترجمة القوانين / Rules language / Langue",
            options=[
                discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦"),
                discord.SelectOption(label="English", value="en", emoji="🇬🇧"),
                discord.SelectOption(label="Français", value="fr", emoji="🇫🇷"),
            ],
            min_values=1,
            max_values=1,
            custom_id="ggmw9:rules:language",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        lang = set_panel_language(interaction.guild.id if interaction.guild else 0, interaction.user.id, self.values[0])
        await interaction.response.send_message(
            embed=_build_rules_translation_embed(interaction.guild, lang),
            view=RulesPrivateLanguageView(interaction.user.id, lang),
            ephemeral=True,
        )


class RulesVerifyView(discord.ui.View):
    """Original public Rules mechanics stay unchanged; public buttons are Darija-only."""
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(RulesLanguageSelect())

    @discord.ui.button(label="✅ كنوافق", style=discord.ButtonStyle.success, custom_id="rules_agree_button", row=0)
    async def agree_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = get_panel_language(interaction.guild.id if interaction.guild else 0, interaction.user.id)
        await _handle_rules_agree(interaction, lang, private_panel=False)

    @discord.ui.button(label="❌ كنرفض", style=discord.ButtonStyle.danger, custom_id="rules_refuse_button", row=0)
    async def refuse_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = get_panel_language(interaction.guild.id if interaction.guild else 0, interaction.user.id)
        await _handle_rules_refuse(interaction, lang, private_panel=False)


async def setup_rules_message(guild: discord.Guild):
    """Refresh the one official Rules panel in-place. Public content stays Darija."""
    rules_channel = bot.get_channel(RULES_CHANNEL_ID)
    if not rules_channel:
        return False

    embed = discord.Embed(
        title="📜 قوانين السيرفر",
        description=(
            f"{_rules_body('darija')}\n\n"
            "⚠️ **بالضغط على ✅ كتوافق على القوانين وكيتم التفعيل ديالك أوتوماتيكياً.**\n"
            "**الرفض ❌ = طرد أوتوماتيكي من السيرفر.**\n\n"
            "🌐 إلا بغيتي ترجمة، اختار اللغة من اللائحة لتحت. الترجمة كتبان غير ليك وما كتبدلش الرسالة العامة."
        ),
        color=discord.Color.blue(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text="GGMW9 | القوانين والتفعيل • الدارجة هي الأساسية")

    matches = []
    try:
        async for message in rules_channel.history(limit=30):
            if message.author != bot.user or not message.embeds:
                continue
            title = message.embeds[0].title or ""
            if "قوانين السيرفر" in title or "Server Rules" in title or "Règles du serveur" in title:
                matches.append(message)
    except discord.Forbidden:
        return False

    try:
        if matches:
            keep = matches[0]
            await keep.edit(embed=embed, view=RulesVerifyView())
            for extra in matches[1:]:
                try:
                    await extra.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass
        else:
            await rules_channel.send(embed=embed, view=RulesVerifyView())
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


def _build_blacklist_embed(lang: str = "darija") -> discord.Embed:
    """Same Blacklist content in 3 languages.

    The shared channel message is ALWAYS Darija. EN/FR are rendered only in a
    member's private ephemeral panel so the channel never contains 3 duplicate
    rule messages.
    """
    lang = lang if lang in {"darija", "en", "fr"} else "darija"
    if lang == "fr":
        embed = discord.Embed(
            title="🚫 Blacklist Things — Règles et Sanctions",
            description=(
                "Lisez cette page en entier avant de discuter sur le serveur. "
                "Le bot surveille ces points **automatiquement 24h/24**, et chaque infraction a un prix.\n"
                "Le but de cette page n'est pas de vous effrayer, mais de vous faire comprendre exactement ce qui est interdit "
                "pour éviter d'être sanctionné sans le savoir."
            ),
            color=discord.Color.dark_red(),
            timestamp=datetime.now(),
        )
        fields = [
            ("1️⃣ Spam et Publicité", "**Interdit :** répéter le même message, poster un lien d'invitation Discord vers un autre serveur sans permission, faire de la publicité pour un salon/produit/service sans l'accord du staff, mentions excessives (@everyone/@here sans droit).\n**Exemple :** poster `discord.gg/xxxx` dans #general pour attirer des membres vers un autre serveur → avertissement + message supprimé."),
            ("2️⃣ Respect entre les membres", "**Interdit :** insultes directes hors contexte de plaisanterie, harcèlement, racisme, insultes personnelles, menaces sous toute forme.\n**Exemple :** tenir des propos racistes ou insultants envers un autre membre → avertissement immédiat, en cas de récidive : exclusion/bannissement."),
            ("3️⃣ Contenu +18 / Violent / Choquant", "**Interdit :** images/vidéos/liens à caractère sexuel, contenu violent explicite (sang, torture...), scènes choquantes.\n**Exemple :** envoyer une image/un lien à caractère sexuel même « pour rire » → **bannissement immédiat, sans avertissement**."),
            ("4️⃣ Vie privée (Doxxing)", "**Interdit :** publier un numéro de téléphone, une adresse, des photos personnelles, ou toute information identifiant quelqu'un sans son consentement.\n**Exemple :** publier une capture d'écran contenant le numéro d'un autre membre → **bannissement immédiat**."),
            ("5️⃣ Mauvaise utilisation des salons", "**Interdit :** discuter hors sujet dans un salon dédié (ex. discussion informelle dans #announcements).\n**Exemple :** poster un mème dans le salon d'actualités officiel → message supprimé + rappel."),
            ("⚖️ Sanctions progressives", f"1️⃣ **Avertissement** — chaque infraction légère déclenche un avertissement automatique\n2️⃣ **Mute** — à {bot_settings['mute_after_warns']} avertissements ({bot_settings['mute_duration_minutes']} min), ou après {SPAM_THRESHOLD} messages en {SPAM_INTERVAL}s (spam)\n3️⃣ **Kick** — à {bot_settings['kick_after_warns']} avertissements\n4️⃣ **Ban** — à {bot_settings['ban_after_warns']} avertissements, ou immédiatement en cas de doxxing/contenu +18/menace grave"),
        ]
        if REPORTS_CHANNEL_ID:
            fields.append(("🚨 Comment signaler une infraction", "Utilise le **Support Center** du serveur : choisis **Signaler un membre** pour une personne précise ou **Signalement général** pour un problème global. Les signalements sont privés et envoyés directement au staff."))
        footer = "GGMW9 | Système de Modération Automatique"
    elif lang == "en":
        embed = discord.Embed(
            title="🚫 Blacklist Things — Rules & Penalties",
            description=(
                "Read this page in full before chatting on the server. "
                "The bot monitors these points **automatically 24/7**, and every violation has a cost.\n"
                "The goal of this page isn't to scare you — we just want you to understand exactly what's forbidden "
                "so you don't get punished without knowing why."
            ),
            color=discord.Color.dark_red(),
            timestamp=datetime.now(),
        )
        fields = [
            ("1️⃣ Spam & Advertising", "**Forbidden:** repeating the same message, posting a Discord invite link to another server without permission, advertising a channel/product/service without staff approval, excessive mentions (@everyone/@here without the right to).\n**Example:** posting `discord.gg/xxxx` in #general to bring people to another server → warning + message deleted."),
            ("2️⃣ Respect Among Members", "**Forbidden:** direct insults outside of joking around, bullying, racism, personal insults, threats of any kind.\n**Example:** posting racist or insulting comments about another member → immediate warning, repeated offenses lead to kick/ban."),
            ("3️⃣ NSFW / Violent / Shocking Content", "**Forbidden:** sexual images/videos/links, explicit violent content (blood, torture...), shocking scenes.\n**Example:** sending sexual content even as a 'joke' → **immediate ban, no warning**."),
            ("4️⃣ Privacy (Doxxing)", "**Forbidden:** sharing a phone number, address, personal photos, or any identifying information about someone without their consent.\n**Example:** posting a screenshot showing another member's phone number → **immediate ban**."),
            ("5️⃣ Misusing Channels", "**Forbidden:** off-topic chat in a dedicated channel (e.g. casual talk in #announcements).\n**Example:** posting a meme in the official news channel → message deleted + reminder."),
            ("⚖️ Escalating Penalties", f"1️⃣ **Warning** — every minor offense triggers an automatic warning\n2️⃣ **Mute** — at {bot_settings['mute_after_warns']} warnings ({bot_settings['mute_duration_minutes']} minutes), or after {SPAM_THRESHOLD} messages in {SPAM_INTERVAL}s (spam)\n3️⃣ **Kick** — upon reaching {bot_settings['kick_after_warns']} warnings\n4️⃣ **Ban** — upon reaching {bot_settings['ban_after_warns']} warnings, or immediately for doxxing/NSFW content/serious threats"),
        ]
        if REPORTS_CHANNEL_ID:
            fields.append(("🚨 How to report a violation", "Use the server **Support Center**: choose **Report member** for a specific person or **General report** for a broader issue. Reports are private and go directly to staff."))
        footer = "GGMW9 | Automatic Moderation & Penalty System"
    else:
        # IMPORTANT: the public Darija wording stays the main/source message.
        embed = discord.Embed(
            title="🚫 الممنوعات والعقوبات",
            description=(
                "قرا/ي هاد الصفحة بالكامل قبل ما تبدا/ي تهضر/ي فالسيرفر. "
                "البوت كيراقب هاد النقاط **أوتوماتيكياً 24/24**، وكل مخالفة عندها ثمن.\n"
                "الهدف من هاد الصفحة ماشي نخوفوك، بغينا غير تفهم/ي شنو ممنوع بالضبط باش ما تتعاقب/ي بلا وعي."
            ),
            color=discord.Color.dark_red(),
            timestamp=datetime.now(),
        )
        fields = [
            ("1️⃣ السبام والإعلانات", "**ممنوع:** تكرار نفس الرسالة، بعث رابط ديسكورد ديال سيرفر آخر بلا إذن، الإعلان لقناة/منتوج/خدمة بلا موافقة الإدارة، منشن بزاف (@everyone/@here بلا حق).\n**مثال:** بعثتي `discord.gg/xxxx` فـ #general باش تجيب ناس لسيرفر آخر → تحذير + مسح الرسالة."),
            ("2️⃣ الاحترام بين الأعضاء", "**ممنوع:** السب المباشر خارج نطاق المزاح، التنمر، العنصرية، الإهانة الشخصية، التهديد بأي شكل.\n**مثال:** كتبتي كلام عنصري ولا مهين على عضو آخر → تحذير مباشر، ومع التكرار طرد/حظر."),
            ("3️⃣ محتوى +18 / عنيف / صادم", "**ممنوع:** صور/فيديوهات/روابط جنسية، محتوى عنيف صريح (دم، تعذيب...)، مشاهد صادمة.\n**مثال:** بعثتي صورة/رابط فيه محتوى جنسي حتى بشكل 'مزحة' → **حظر مباشر بلا تحذير**."),
            ("4️⃣ الخصوصية ونشر المعلومات الشخصية", "**ممنوع:** نشر رقم تيليفون، عنوان، صور شخصية، ولا أي معلومة كتعرف بشخص آخر بلا إذنو.\n**مثال:** نشرتي سكرين شوت فيه رقم ديال عضو آخر → **حظر مباشر**."),
            ("5️⃣ استعمال القنوات بطريقة غالطة", "**ممنوع:** الهضرة خارج الموضوع فقناة مخصصة (مثلاً هضرة عادية فقناة الإعلانات).\n**مثال:** كتبتي ميم فقناة الأخبار الرسمية → مسح الرسالة + تنبيه."),
            ("⚖️ العقوبات المتدرجة", f"1️⃣ **تحذير** — كل مخالفة خفيفة كتبان تحذير أوتوماتيكي\n2️⃣ **كتم** — عند {bot_settings['mute_after_warns']} تحذيرات ({bot_settings['mute_duration_minutes']} دقيقة)، ولا إلا بعتي {SPAM_THRESHOLD} رسايل فـ {SPAM_INTERVAL} ثواني (سبام)\n3️⃣ **طرد** — عند الوصول لـ {bot_settings['kick_after_warns']} تحذيرات\n4️⃣ **حظر** — عند الوصول لـ {bot_settings['ban_after_warns']} تحذيرات، ولا مباشرة فحالة نشر معلومات شخصية/محتوى +18/تهديد خطير"),
        ]
        if REPORTS_CHANNEL_ID:
            # Keep the public guide practical with the unified Support Center.
            fields.append(("🚨 كيفاش تبلغ عن مخالفة", "دخل لـ **مركز المساعدة** واختار **بلغ على عضو** إلا كان البلاغ على شخص محدد، أو **بلاغ عام** إلا كان مشكل عام. البلاغ كيمشي مباشرة للإدارة وبشكل خاص."))
        footer = "GGMW9 | نظام المراقبة والعقوبات الأوتوماتيكي"

    for name, value in fields:
        embed.add_field(name=name, value=value, inline=False)
    embed.set_footer(text=footer)
    return embed


class BlacklistPrivateLanguageSelect(discord.ui.Select):
    def __init__(self, user_id: int, lang: str = "darija"):
        self.user_id = int(user_id)
        self.lang = lang
        super().__init__(
            placeholder="🌐 اللغة / Language / Langue",
            options=[
                discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", default=lang == "darija"),
                discord.SelectOption(label="English", value="en", emoji="🇬🇧", default=lang == "en"),
                discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", default=lang == "fr"),
            ],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ هاد الترجمة ماشي ديالك.", ephemeral=True)
            return
        lang = set_panel_language(interaction.guild.id if interaction.guild else 0, interaction.user.id, self.values[0])
        await interaction.response.edit_message(
            content=None,
            embed=_build_blacklist_embed(lang),
            view=BlacklistPrivateLanguageView(interaction.user.id, lang),
        )


class BlacklistPrivateLanguageView(discord.ui.View):
    def __init__(self, user_id: int, lang: str = "darija"):
        super().__init__(timeout=1800)
        self.add_item(BlacklistPrivateLanguageSelect(user_id, lang))


class BlacklistLanguageSelect(discord.ui.Select):
    """Public Darija selector — opens a fresh private translation every time."""
    def __init__(self, lang: str = "darija"):
        lang = lang if lang in {"darija", "en", "fr"} else "darija"
        self.lang = lang
        super().__init__(
            placeholder="🌐 اللغة / Language / Langue",
            options=[
                discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", default=lang == "darija"),
                discord.SelectOption(label="English", value="en", emoji="🇬🇧", default=lang == "en"),
                discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", default=lang == "fr"),
            ],
            min_values=1,
            max_values=1,
            custom_id="ggmw9:blacklist:language",
        )

    async def callback(self, interaction: discord.Interaction):
        lang = set_panel_language(
            interaction.guild.id if interaction.guild else 0,
            interaction.user.id,
            self.values[0],
        )
        # Always create a fresh private translation. Dismiss never poisons the public selector.
        await interaction.response.send_message(
            embed=_build_blacklist_embed(lang),
            view=BlacklistPrivateLanguageView(interaction.user.id, lang),
            ephemeral=True,
        )


class BlacklistLanguageView(discord.ui.View):
    def __init__(self, lang: str = "darija"):
        super().__init__(timeout=None)
        self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
        self.add_item(BlacklistLanguageSelect(self.lang))


async def setup_blacklist_message(guild: discord.Guild):
    """Keep ONE public Darija blacklist message; translations are always private and fresh."""
    channel = bot.get_channel(BLACKLIST_CHANNEL_ID)
    if not channel:
        return

    darija_messages = []
    translated_messages = []
    try:
        async for message in channel.history(limit=40):
            if message.author != bot.user or not message.embeds:
                continue
            title = message.embeds[0].title or ""
            if "الممنوعات والعقوبات" in title:
                darija_messages.append(message)
            elif "Règles et Sanctions" in title or "Rules & Penalties" in title:
                translated_messages.append(message)
    except discord.Forbidden:
        return

    # Keep the SAME existing message regardless of its current language.
    all_panels = darija_messages + translated_messages
    all_panels.sort(key=lambda m: m.id)
    keep = all_panels[0] if all_panels else None
    try:
        if keep:
            await keep.edit(content=None, embed=_build_blacklist_embed("darija"), view=BlacklistLanguageView("darija"))
        else:
            keep = await channel.send(embed=_build_blacklist_embed("darija"), view=BlacklistLanguageView("darija"))

        # Clean only true duplicates; never delete the kept original message.
        for old in all_panels:
            if keep and old.id == keep.id:
                continue
            try:
                await old.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[BLACKLIST] ما قدرتش نحدّث الواجهة: {e}")


class VerificationCog(commands.Cog):
    """Discord command/event registration for this subsystem."""

    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance

    @commands.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def clearoldverify(self, ctx):
        """كيمسح رسالة/رسائل 'تفعيل العضوية' القديمة (بالريأكشن ✅) من verify channel"""
        verify_channel = bot.get_channel(VERIFY_CHANNEL_ID)
        rules_channel = bot.get_channel(RULES_CHANNEL_ID)
        deleted = 0
        for channel in {verify_channel, rules_channel}:
            if not channel:
                continue
            async for message in channel.history(limit=50):
                if message.author == bot.user and "تفعيل العضوية" in (message.embeds[0].title if message.embeds else ""):
                    try:
                        await message.delete()
                        deleted += 1
                    except Exception:
                        pass
        await ctx.send(f"✅ تمسحو {deleted} رسالة/رسائل قديمة." if deleted else "ماكاينش شي رسالة قديمة باش تتمسح.", delete_after=8)

    @commands.hybrid_command(description="صاوب رسالة التفعيل/القوانين (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setupverify(self, ctx):
        await setup_verify_message(ctx.guild)
        await ctx.send("✅ تم صاوب رسالة التفعيل!", delete_after=5)

    @commands.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setupblacklist(self, ctx):
        """يصاوب رسالة الممنوعات والعقوبات فـ Blacklist channel"""
        if not BLACKLIST_CHANNEL_ID:
            await ctx.send("❌ خاصك تحط `BLACKLIST_CHANNEL_ID` فالـ CONFIG أولاً!")
            return
        await setup_blacklist_message(ctx.guild)
        await ctx.send("✅ تم صاوب رسالة Blacklist!", delete_after=5)

    @commands.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setuprules(self, ctx):
        """يصاوب رسالة القوانين + زرارات كنوافق/كنرفض فـ rules channel"""
        await setup_rules_message(ctx.guild)
        await ctx.send("✅ تم صاوب رسالة القوانين بالأزرار!", delete_after=5)

    @commands.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setuproles(self, ctx):
        """يصاوب رسالة اختيار الأدوار بـ Dropdown Menus (خاصك تعمر PICK_ROLES فـ config أولاً)"""
        has_any_valid_role = any(
            r["role_id"] for roles_list in PICK_ROLES.values() for r in roles_list
        )
        if not has_any_valid_role:
            await ctx.send(
                "❌ ماكاين حتى رول صالح فـ `PICK_ROLES`!\n"
                "خاصك تحط IDs ديال الأدوار فـ config (فعّل Developer Mode فـ Discord، "
                "بعدها كليك يمين على الرول → Copy ID)."
            )
            return

        description_lines = ["اختار من اللائحة (Dropdown) تحت باش تاخد الأدوار، وعاود اختار باش تبدلها 🔄\n"]
        for category_name, roles_list in PICK_ROLES.items():
            valid = [r for r in roles_list if r["role_id"]]
            if not valid:
                continue
            description_lines.append(f"**{category_name}**")
            description_lines.append(", ".join(f"{r['emoji']} {r['label']}" for r in valid))
            description_lines.append("")

        embed = discord.Embed(
            title="🎭 اختار الأدوار ديالك",
            description="\n".join(description_lines),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="GGMW9 | Pick Roles")

        await ctx.send(embed=embed, view=RolePickerView())
        await ctx.send("✅ تصاوبات رسالة الأدوار!", delete_after=5)

    @commands.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def listroles(self, ctx):
        """يبين لائحة الأدوار المعمرة دابا فـ PICK_ROLES"""
        lines = []
        for category_name, roles_list in PICK_ROLES.items():
            valid = [r for r in roles_list if r["role_id"]]
            if not valid:
                continue
            roles_text = ", ".join(f"{r['emoji']} {r['label']} → <@&{r['role_id']}>" for r in valid)
            lines.append(f"**{category_name}**\n{roles_text}")

        if not lines:
            await ctx.send("ماكاين حتى رول معمر دابا فـ `PICK_ROLES`. عمر IDs ديال الأدوار فـ config.")
            return

        embed = discord.Embed(
            title="🎭 الأدوار المعمرة فـ PICK_ROLES",
            description="\n\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text="GGMW9 | Pick Roles")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="فعّل عضو يدوياً (Admin)")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def verify(self, ctx, member: discord.Member):
        unverified_role = ctx.guild.get_role(UNVERIFIED_ROLE_ID)
        if unverified_role and unverified_role in member.roles:
            await member.remove_roles(unverified_role)
        member_role = ctx.guild.get_role(MEMBER_ROLE_ID)
        if member_role:
            await member.add_roles(member_role)
        embed = discord.Embed(
            title="✅ تفعيل يدوي",
            description=f"**{member.mention}** تم تفعيله.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
        embed.set_footer(text="GGMW9 | Verification")
        await ctx.send(embed=embed)
        await log_action(
            ctx.guild,
            "✅ تفعيل يدوي",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**المنفذ:** {ctx.author.mention}",
            discord.Color.green()
        )
        try:
            gender_embed = discord.Embed(
                title="🚻 واش نتا/نتي ولد ولا بنت؟",
                description="ضغط/ي على الزر المناسب باش نعطيوك الرول الصحيح.",
                color=discord.Color.blurple()
            )
            await member.send(
                f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك! 🎉",
                embed=gender_embed,
                view=GenderSelectView(target_user_id=member.id, guild_id=ctx.guild.id)
            )
        except Exception:
            pass

    @commands.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def checkroles(self, ctx):
        """كيتأكد أن role ديال البوت قادر يعطي Member/Unverified/Muted"""
        problems = check_role_hierarchy(ctx.guild)
        if not problems:
            embed = discord.Embed(
                title="✅ كلشي مزيان",
                description="role ديال البوت فوق فالترتيب وعندو الصلاحيات اللازمة. نظام التفعيل خاصو يخدم عادي.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="⚠️ لقيت مشاكل فترتيب الرولات",
                description="\n\n".join(problems),
                color=discord.Color.red()
            )
        embed.set_footer(text="GGMW9 | Role Hierarchy Check")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="رجع عضو Unverified (Admin)")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def unverify(self, ctx, member: discord.Member):
        member_role = ctx.guild.get_role(MEMBER_ROLE_ID)
        if member_role and member_role in member.roles:
            await member.remove_roles(member_role)
        unverified_role = ctx.guild.get_role(UNVERIFIED_ROLE_ID)
        if unverified_role:
            await member.add_roles(unverified_role)
        embed = discord.Embed(
            title="🔄 إلغاء التفعيل",
            description=f"**{member.mention}** تم إلغاء تفعيله.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
        embed.set_footer(text="GGMW9 | Verification")
        await ctx.send(embed=embed)
        await log_action(
            ctx.guild,
            "🔄 إلغاء التفعيل",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**المنفذ:** {ctx.author.mention}",
            discord.Color.orange()
        )


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(VerificationCog(bot_instance))
