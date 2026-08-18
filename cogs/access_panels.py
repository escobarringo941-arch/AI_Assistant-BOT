# -*- coding: utf-8 -*-
"""Unchanged ordered source component: access_panels."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
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
        if guild is not None:
            for field_name, field_value in _owner_prison_rules_blacklist_field(guild, lang):
                embed.add_field(name=field_name, value=field_value, inline=False)
        embed.set_footer(text=footer)
        return embed
    
    
    def _rules_lang_text(lang: str, darija: str, en: str, fr: str) -> str:
        lang = lang if lang in {"darija", "en", "fr"} else "darija"
        return {"darija": darija, "en": en, "fr": fr}[lang]
    
    
    def _rules_member_is_exempt(member: discord.Member) -> bool:
        if member.id == member.guild.owner_id:
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
    
        # وافق على القوانين → كنمسحو ليه الرسالة الترحيبية (وأي رسالة أخرى) من الـ DM
        await purge_bot_dm_messages(member)
    
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
    
        # رفض القوانين → كنمسحو ليه الرسالة الترحيبية (وأي رسالة أخرى) من الـ DM،
        # وكنمسحو الرولات المحفوظة ديالو باش إلا رجع بـ invite جديد يتعامل معاه
        # البوت كعضو جديد بصح (رسالة ترحيبية جديدة، ماشي "رجع للسيرفر").
        await purge_bot_dm_messages(member)
        forget_member_roles(member)
    
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
        for field_name, field_value in _owner_prison_rules_blacklist_field(guild, "darija"):
            embed.add_field(name=field_name, value=field_value, inline=False)
        embed.set_footer(text="GGMW9 | القوانين والتفعيل • الدارجة هي الأساسية")
        message = await upsert_fixed_panel(
            bot,
            rules_channel,
            key="rules",
            matches=lambda message: (
                message.author == bot.user
                and bool(message.embeds)
                and any(
                    marker in (message.embeds[0].title or "")
                    for marker in ("قوانين السيرفر", "Server Rules", "Règles du serveur")
                )
            ),
            content=None,
            embed=embed,
            view=RulesVerifyView(),
            history_limit=None,
        )
        return message is not None
    
    
    def _owner_prison_rules_blacklist_field(guild: discord.Guild, lang: str):
        """Build chunked public fields from the complete live Owner catalogue.

        No offense allow-list lives here.  Original offenses, the important
        security offenses and every custom judgment created later in the Owner
        panel are read from ``PrisonStore.offenses`` on every refresh.  Only the
        public label, duration and warning threshold are exposed; private rule
        patterns and internal detector details stay hidden.
        """
        prison_cog = bot.get_cog("PrisonSystem") if guild is not None else None
        if prison_cog is None:
            return []
        from cogs.prison_core import format_duration, warning_trigger_note

        catalogue = prison_cog.store.offenses(guild.id)
        titles = {
            "darija": "⏱️ الأحكام والمدد (كتحدّث أوتوماتيكياً)",
            "en": "⏱️ Judgments & Durations (auto-updated)",
            "fr": "⏱️ Jugements et durées (mise à jour automatique)",
        }
        ordered = sorted(
            catalogue.items(),
            key=lambda item: (
                int(item[1].get("severity", 1) or 1),
                int(item[1].get("seconds", 3600) or 3600),
                str(item[1].get("label", item[0])).casefold(),
            ),
        )
        lines: list[str] = []
        for key, entry in ordered:
            try:
                trigger = prison_cog.store.offense_trigger_count(guild.id, key)
            except Exception:
                trigger = 1
            note = warning_trigger_note(trigger, lang)
            lines.append(
                f"• **{entry.get('label', key)}** — "
                f"`{format_duration(int(entry.get('seconds', 3600)))}` • {note}"
            )
        if not lines:
            return []

        chunks: list[str] = []
        current: list[str] = []
        current_size = 0
        for line in lines:
            added = len(line) + (1 if current else 0)
            if current and current_size + added > 980:
                chunks.append("\n".join(current))
                current = []
                current_size = 0
            current.append(line)
            current_size += len(line) + (1 if len(current) > 1 else 0)
        if current:
            chunks.append("\n".join(current))

        # Blacklist already uses seven fields. Discord accepts 25 fields, so
        # eighteen catalogue chunks still leave the panel valid and cover far
        # more judgments than the Owner UI can reasonably hold at once.
        chunks = chunks[:18]
        return [
            (
                titles[lang] if index == 0 else f"{titles[lang]} • {index + 1}",
                value,
            )
            for index, value in enumerate(chunks)
        ]



    def _build_blacklist_embed(
        lang: str = "darija",
        guild: Optional[discord.Guild] = None,
    ) -> discord.Embed:
        """Same Blacklist content in 3 languages.
    
        The shared channel message is ALWAYS Darija. EN/FR are rendered only in a
        member's private ephemeral panel so the channel never contains 3 duplicate
        rule messages.

        Always includes the live "⏱️ الأحكام والمدد" field — label + duration +
        warning count per offense, pulled straight from the Owner's Prison
        catalogue. Never includes raw patterns/words/links or internal
        auto-rule details.
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
                ("⚖️ Sanctions progressives", f"1️⃣ **Avertissement** — chaque infraction légère déclenche un avertissement automatique\n2️⃣ **Mute** — à {bot_settings['mute_after_warns']} avertissements ({bot_settings['mute_duration_minutes']} min)\n3️⃣ **Kick** — à {bot_settings['kick_after_warns']} avertissements\n4️⃣ **Ban** — à {bot_settings['ban_after_warns']} avertissements, ou immédiatement en cas de doxxing/contenu +18/menace grave\n🔗 Les seuils de spam, liens, mots et actions sont toujours ceux de la liste dynamique ci-dessous."),
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
                ("⚖️ Escalating Penalties", f"1️⃣ **Warning** — every minor offense triggers an automatic warning\n2️⃣ **Mute** — at {bot_settings['mute_after_warns']} warnings ({bot_settings['mute_duration_minutes']} minutes)\n3️⃣ **Kick** — upon reaching {bot_settings['kick_after_warns']} warnings\n4️⃣ **Ban** — upon reaching {bot_settings['ban_after_warns']} warnings, or immediately for doxxing/NSFW content/serious threats\n🔗 Spam, link, word and action thresholds always use the live Owner rules below."),
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
                ("⚖️ العقوبات المتدرجة", f"1️⃣ **تحذير** — كل مخالفة خفيفة كتبان تحذير أوتوماتيكي\n2️⃣ **كتم** — عند {bot_settings['mute_after_warns']} تحذيرات ({bot_settings['mute_duration_minutes']} دقيقة)\n3️⃣ **طرد** — عند الوصول لـ {bot_settings['kick_after_warns']} تحذيرات\n4️⃣ **حظر** — عند الوصول لـ {bot_settings['ban_after_warns']} تحذيرات، ولا مباشرة فحالة نشر معلومات شخصية/محتوى +18/تهديد خطير\n🔗 عدد مرات السبام والروابط والكلمات والأفعال كيتقرا دائماً من قوانين الـOwner الحية لتحت."),
            ]
            if REPORTS_CHANNEL_ID:
                # Keep the public guide practical with the unified Support Center.
                fields.append(("🚨 كيفاش تبلغ عن مخالفة", "دخل لـ **مركز المساعدة** واختار **بلغ على عضو** إلا كان البلاغ على شخص محدد، أو **بلاغ عام** إلا كان مشكل عام. البلاغ كيمشي مباشرة للإدارة وبشكل خاص."))
            footer = "GGMW9 | نظام المراقبة والعقوبات الأوتوماتيكي"
    
        if guild is not None:
            fields.extend(_owner_prison_rules_blacklist_field(guild, lang))

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
                embed=_build_blacklist_embed(lang, interaction.guild),
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
                embed=_build_blacklist_embed(lang, interaction.guild),
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
    
        message = await upsert_fixed_panel(
            bot,
            channel,
            key="blacklist",
            matches=lambda message: (
                message.author == bot.user
                and bool(message.embeds)
                and any(
                    marker in (message.embeds[0].title or "")
                    for marker in (
                        "الممنوعات والعقوبات",
                        "Règles et Sanctions",
                        "Rules & Penalties",
                    )
                )
            ),
            content=None,
            embed=_build_blacklist_embed("darija", guild),
            view=BlacklistLanguageView("darija"),
            history_limit=None,
        )
        if message is None:
            print("[BLACKLIST] ما قدرتش نحدّث الواجهة دابا.")
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
