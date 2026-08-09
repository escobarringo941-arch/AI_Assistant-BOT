# -*- coding: utf-8 -*-
"""Level panels, XP administration, rank UI, and leaderboard.

Extracted mechanically from the legacy ai_bot.py.  Runtime state is attached
to bot_core's shared namespace so existing cross-system references keep the
same object identity and startup order.
"""

import bot_core as core

core.attach_namespace(globals())


def build_levels_info_embed(guild: discord.Guild, lang: str = "darija") -> discord.Embed:
    lang = lang if lang in {"darija", "en", "fr"} else "darija"
    if lang == "en":
        title = "📊 Levels & XP — progression with real value"
        desc = (
            f"💬 **Chat:** {xp_settings['chat_min']}-{xp_settings['chat_max']} XP per eligible message, cooldown **{xp_settings['chat_cooldown']}s**.\n"
            f"🎙️ **Voice:** **{xp_settings['voice_per_interval']} XP** every {xp_settings['voice_interval_minutes']} minutes.\n"
            f"📡 **Go Live:** **{xp_settings['stream_per_interval']} XP** every {xp_settings['voice_interval_minutes']} minutes.\n\n"
            "## 🔄 How Level Roles work\nYou keep **only your highest Level Role**. When you reach a new threshold, the old Level Role is removed automatically. The bot also self-heals roles after restarts.\n\n"
            "## 🎁 Why level up?\nHigher levels unlock stronger **Shop discounts, Daily bonuses, better loan terms and safe social/Discord perks**.\n\n"
            "## 🖱️ No command needed\nUse the buttons below for your rank, another member's rank, leaderboard, roadmap, Bio, Poll and Legend Title.\n\n"
            "🌐 The language selector opens your **private translated XP panel**. Dismiss is safe; reopen it here anytime."
        )
        roadmap_name, roadmap_more = "🪜 Level Role Roadmap", "🪜 Roadmap (continued)"
        safety_name = "🛡️ Permission safety"
        safety_value = "Level Roles **never grant dangerous management permissions** such as View Audit Log, Manage Threads, Manage Events or Manage Emojis. Their value comes from safe social and economy perks."
        footer = f"{SERVER_NAME} | one Level Role • earn XP • unlock stronger perks • English"
    elif lang == "fr":
        title = "📊 Niveaux & XP — une progression qui a de la valeur"
        desc = (
            f"💬 **Chat :** {xp_settings['chat_min']}-{xp_settings['chat_max']} XP par message éligible, cooldown **{xp_settings['chat_cooldown']}s**.\n"
            f"🎙️ **Vocal :** **{xp_settings['voice_per_interval']} XP** toutes les {xp_settings['voice_interval_minutes']} minutes.\n"
            f"📡 **Go Live :** **{xp_settings['stream_per_interval']} XP** toutes les {xp_settings['voice_interval_minutes']} minutes.\n\n"
            "## 🔄 Fonctionnement des rôles de niveau\nTu gardes **uniquement ton rôle de niveau le plus élevé**. Quand tu atteins un nouveau palier, l'ancien rôle est retiré automatiquement. Le bot répare aussi les rôles après un redémarrage.\n\n"
            "## 🎁 Pourquoi monter de niveau ?\nLes niveaux débloquent de meilleures **réductions Shop, bonus Daily, conditions de prêt et avantages Discord/social sûrs**.\n\n"
            "## 🖱️ Aucune commande nécessaire\nUtilise les boutons pour ton rang, le rang d'un membre, le classement, la progression, la Bio, les sondages et le titre Legend.\n\n"
            "🌐 Le sélecteur ouvre ton **panneau XP privé traduit**. Tu peux le fermer puis le rouvrir ici sans problème."
        )
        roadmap_name, roadmap_more = "🪜 Progression des rôles", "🪜 Progression (suite)"
        safety_name = "🛡️ Sécurité des permissions"
        safety_value = "Les rôles de niveau **ne donnent jamais de permissions de gestion dangereuses** comme View Audit Log, Manage Threads, Manage Events ou Manage Emojis. Leur valeur vient des avantages sociaux et économiques sûrs."
        footer = f"{SERVER_NAME} | un seul rôle de niveau • gagne de l'XP • débloque des avantages • Français"
    else:
        title = "📊 نظام المستويات — XP عندو قيمة حقيقية"
        desc = (
            f"💬 **الشات:** {xp_settings['chat_min']}-{xp_settings['chat_max']} XP لكل رسالة مؤهلة، Cooldown **{xp_settings['chat_cooldown']}ث**.\n"
            f"🎙️ **الفويس:** **{xp_settings['voice_per_interval']} XP** كل {xp_settings['voice_interval_minutes']} دقايق.\n"
            f"📡 **Go Live:** **{xp_settings['stream_per_interval']} XP** كل {xp_settings['voice_interval_minutes']} دقايق.\n\n"
            "## 🔄 كيفاش كتخدم Level Role؟\n**عندك غير Role وحدة ديال Level.** منين توصل Threshold جديدة، البوت كيحيد القديمة وكيعطيك الأعلى أوتوماتيكياً، وحتى بعد Restart كيدير Self-Healing.\n\n"
            "## 🎁 علاش نطلع XP؟\nLevels كيحلو **Shop Discount أكبر، Daily Bonus أكبر، قرض أقوى وشروط أحسن، ومزايا Discord/Social آمنة**.\n\n"
            "## 🖱️ ما تحتاج تكتب حتى Command\nاستعمل الأزرار تحت: Rank ديالك، Rank ديال عضو، Leaderboard، Roadmap، Bio، Poll وLegend Title.\n\n"
            "🌐 اختيار اللغة كيحل **Panel خاصة بيك** مترجمة. إلا سديتيها بـDismiss تقدر ترجع تحلها من هنا فالحين."
        )
        roadmap_name, roadmap_more = "🪜 Roadmap ديال Level Roles", "🪜 Roadmap (تكملة)"
        safety_name = "🛡️ ملاحظة على الصلاحيات"
        safety_value = "Level Roles **ما كتعطيش صلاحيات إدارة خطيرة**. ماكاين لا View Audit Log لا Manage Threads لا Manage Events لا Manage Emojis. القيمة كتجي من امتيازات آمنة واقتصادية."
        footer = f"{SERVER_NAME} | Role وحدة ديال Level • طلع XP وفتح مزايا أقوى • Darija"

    embed = discord.Embed(title=title, description=desc, color=discord.Color.gold(), timestamp=datetime.now())
    lines = []
    for lvl, role_id in sorted(LEVEL_ROLES.items()):
        role = guild.get_role(role_id) if role_id else None
        role_display = role.mention if role else f"`Level {lvl}`"
        p = LEVEL_ROLE_BENEFITS.get(lvl, {})
        if lang == "en":
            line = (f"{role_display} **Lv {lvl} — {p.get('name','')}**\n> 🛒 Shop -{p.get('shop_discount_percent',0)}% • 🎁 Daily +{p.get('daily_bonus_percent',0)}% • 🏦 {cfg.fmt_money(int(p.get('loan_base',0)))} / {p.get('loan_interest',0)}% / {p.get('loan_days',0)}d\n> {p.get('feature','—')}")
        elif lang == "fr":
            line = (f"{role_display} **Nv {lvl} — {p.get('name','')}**\n> 🛒 Shop -{p.get('shop_discount_percent',0)}% • 🎁 Daily +{p.get('daily_bonus_percent',0)}% • 🏦 {cfg.fmt_money(int(p.get('loan_base',0)))} / {p.get('loan_interest',0)}% / {p.get('loan_days',0)}j\n> {p.get('feature','—')}")
        else:
            line = (f"{role_display} **Lv {lvl} — {p.get('name','')}**\n> 🛒 -{p.get('shop_discount_percent',0)}% • 🎁 Daily +{p.get('daily_bonus_percent',0)}% • 🏦 {cfg.fmt_money(int(p.get('loan_base',0)))} / {p.get('loan_interest',0)}% / {p.get('loan_days',0)}d\n> {p.get('feature','—')}")
        lines.append(line)

    chunks, current, current_len = [], [], 0
    for line in lines:
        if current and current_len + len(line) + 2 > 980:
            chunks.append(current); current, current_len = [], 0
        current.append(line); current_len += len(line) + 2
    if current: chunks.append(current)
    for idx, chunk in enumerate(chunks, 1):
        embed.add_field(name=roadmap_name if idx == 1 else roadmap_more, value="\n\n".join(chunk), inline=False)
    embed.add_field(name=safety_name, value=safety_value, inline=False)
    embed.set_footer(text=footer)
    return embed


async def setup_levels_info_message(guild: discord.Guild):
    """Keep one Levels message and reset it to Darija after deploy/Owner Refresh."""
    if not LEVELS_INFO_CHANNEL_ID:
        return
    channel = bot.get_channel(LEVELS_INFO_CHANNEL_ID)
    if not channel:
        return
    existing = None
    try:
        async for message in channel.history(limit=30):
            if message.author != bot.user or not message.embeds:
                continue
            title = message.embeds[0].title or ""
            if any(x in title for x in ("نظام المستويات", "Levels & XP", "Niveaux & XP")):
                existing = message
                break
    except discord.Forbidden:
        return
    embed = build_levels_info_embed(guild, "darija")
    try:
        if existing:
            await existing.edit(content=None, embed=embed, view=LevelsInfoView("darija"))
        else:
            await channel.send(embed=embed, view=LevelsInfoView("darija"))
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[LEVEL INFO] ما قدرتش نحدّث الرسالة: {e}")

# ═══════════════════════════════════════════════════════
# ║         XP Control Panel — لوحة تحكم فـ XP (Admin)       ║
# ═══════════════════════════════════════════════════════
# لوحة تفاعلية كتخلي الإدارة تبدل شحال ديال XP كياخدو الأعضاء من 3 طرق
# (الشات، الفويس، اللايفستريم) مباشرة من ديسكورد بلا ماتمس الكود — /xppanel
# القيم كتتحفظ فـ xp_settings.json وكتبقى حتى بعد ريستارت البوت.

def _xp_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎛️ لوحة تحكم XP",
        description="بدل شحال ديال XP كياخدو الأعضاء من كل طريقة، بالأزرار تحت. القيم كتتحفظ أوتوماتيك.",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="💬 الشات",
        value=(
            f"**{xp_settings['chat_min']}-{xp_settings['chat_max']}** XP / رسالة\n"
            f"Cooldown: **{xp_settings['chat_cooldown']}** ثانية"
        ),
        inline=True
    )
    embed.add_field(
        name="🎙️ الفويس",
        value=(
            f"**{xp_settings['voice_per_interval']}** XP / {xp_settings['voice_interval_minutes']} دقايق\n"
            f"أدنى بشر فالروم: **{xp_settings['voice_min_humans']}**"
        ),
        inline=True
    )
    embed.add_field(
        name="📡 اللايفستريم",
        value=f"**{xp_settings['stream_per_interval']}** XP / {xp_settings['voice_interval_minutes']} دقايق",
        inline=True
    )
    cap = int(xp_settings.get("afk_daily_cap", 0) or 0)
    embed.add_field(
        name="💤 الـ AFK",
        value=(
            f"فالروم ديال AFK: **{xp_settings['afk_channel_per_interval']}** XP\n"
            f"مايك مسدود فروم عادية: **{xp_settings['afk_muted_per_interval']}** XP\n"
            f"سقف يومي: **{cap if cap > 0 else 'بلا سقف'}**"
        ),
        inline=True
    )
    mult = xp_settings.get("level_xp_multiplier", 1.0)
    sample_lvl5 = xp_needed_for_level(5)
    sample_lvl20 = xp_needed_for_level(20)
    embed.add_field(
        name="📈 صعوبة المستويات",
        value=(
            f"مضاعف: **×{mult}**\n"
            f"مثال: Level 5 كيحتاج **{sample_lvl5}** XP | Level 20 كيحتاج **{sample_lvl20}** XP"
        ),
        inline=True
    )
    per_hour = 60 / xp_settings["voice_interval_minutes"]
    ratio_voice = (xp_settings["stream_per_interval"] / xp_settings["voice_per_interval"]) if xp_settings["voice_per_interval"] else 0
    embed.add_field(
        name="📐 مقارنة سريعة (تقريبية، فـ الساعة)",
        value=(
            f"اللايفستريم كياخد تقريبا **×{ratio_voice:.1f}** من الفويس العادي.\n"
            f"📡 لايفستريم ≈ **{xp_settings['stream_per_interval'] * per_hour:.0f}** | "
            f"🎙️ فويس ≈ **{xp_settings['voice_per_interval'] * per_hour:.0f}** | "
            f"💤 AFK روم ≈ **{xp_settings['afk_channel_per_interval'] * per_hour:.0f}** | "
            f"🔇 AFK عادي ≈ **{xp_settings['afk_muted_per_interval'] * per_hour:.0f}** XP/ساعة"
        ),
        inline=False
    )
    embed.set_footer(text=f"{SERVER_NAME} | XP Control Panel")
    return embed


class ChatXPModal(discord.ui.Modal, title="💬 إعدادات XP الشات"):
    def __init__(self):
        super().__init__()
        self.min_xp = discord.ui.TextInput(
            label="أدنى XP فكل رسالة", default=str(xp_settings["chat_min"]), max_length=5
        )
        self.max_xp = discord.ui.TextInput(
            label="أقصى XP فكل رسالة", default=str(xp_settings["chat_max"]), max_length=5
        )
        self.cooldown = discord.ui.TextInput(
            label="Cooldown بالثواني بين رسالة ورسالة", default=str(xp_settings["chat_cooldown"]), max_length=6
        )
        self.add_item(self.min_xp)
        self.add_item(self.max_xp)
        self.add_item(self.cooldown)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_min = int(self.min_xp.value)
            new_max = int(self.max_xp.value)
            new_cooldown = int(self.cooldown.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
            return
        if new_min < 0 or new_max < 0 or new_cooldown < 0:
            await interaction.response.send_message("❌ ماكاينش أرقام سالبة.", ephemeral=True)
            return
        if new_min > new_max:
            await interaction.response.send_message("❌ الأدنى خاصو يكون أصغر ولا يساوي الأقصى.", ephemeral=True)
            return

        xp_settings["chat_min"] = new_min
        xp_settings["chat_max"] = new_max
        xp_settings["chat_cooldown"] = new_cooldown
        save_xp_settings()

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class VoiceXPModal(discord.ui.Modal, title="🎙️ إعدادات XP الفويس"):
    def __init__(self):
        super().__init__()
        self.per_interval = discord.ui.TextInput(
            label="XP كل فترة (فويس عادي)", default=str(xp_settings["voice_per_interval"]), max_length=5
        )
        self.interval_minutes = discord.ui.TextInput(
            label="الفترة بالدقايق (مشتركة مع اللايفستريم)",
            default=str(xp_settings["voice_interval_minutes"]), max_length=4
        )
        self.min_humans = discord.ui.TextInput(
            label="أدنى عدد بشر فالروم باش ياخدو XP", default=str(xp_settings["voice_min_humans"]), max_length=3
        )
        self.add_item(self.per_interval)
        self.add_item(self.interval_minutes)
        self.add_item(self.min_humans)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_amount = int(self.per_interval.value)
            new_interval = int(self.interval_minutes.value)
            new_min_humans = int(self.min_humans.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
            return
        if new_amount < 0 or new_interval <= 0 or new_min_humans < 1:
            await interaction.response.send_message(
                "❌ الفترة خاصها تكون أكبر من 0، وأدنى البشر خاصو يكون 1 ولا أكثر.", ephemeral=True
            )
            return

        interval_changed = new_interval != xp_settings["voice_interval_minutes"]
        xp_settings["voice_per_interval"] = new_amount
        xp_settings["voice_interval_minutes"] = new_interval
        xp_settings["voice_min_humans"] = new_min_humans
        save_xp_settings()

        # الفترة (VOICE_XP_INTERVAL_MINUTES) مشتركة بين الفويس واللايفستريم (نفس الـ loop)،
        # فـ إلا تبدلات خاصنا نبدلو الـ loop نفسو ماشي غير الرقم فالـ dict
        if interval_changed and voice_xp_loop.is_running():
            voice_xp_loop.change_interval(minutes=new_interval)

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class StreamXPModal(discord.ui.Modal, title="📡 إعدادات XP اللايفستريم"):
    def __init__(self):
        super().__init__()
        self.per_interval = discord.ui.TextInput(
            label="XP كل فترة (ملي كيدير Go Live)",
            default=str(xp_settings["stream_per_interval"]), max_length=5
        )
        self.add_item(self.per_interval)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_amount = int(self.per_interval.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص القيمة تكون رقم صحيح.", ephemeral=True)
            return
        if new_amount < 0:
            await interaction.response.send_message("❌ ماكاينش رقم سالب.", ephemeral=True)
            return

        xp_settings["stream_per_interval"] = new_amount
        save_xp_settings()

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class AfkXPModal(discord.ui.Modal, title="💤 إعدادات XP ديال الـ AFK"):
    def __init__(self):
        super().__init__()
        self.afk_channel_xp = discord.ui.TextInput(
            label="XP كل فترة فالروم ديال AFK",
            default=str(xp_settings["afk_channel_per_interval"]), max_length=5
        )
        self.afk_muted_xp = discord.ui.TextInput(
            label="XP كل فترة (مايك مسدود فروم عادية)",
            default=str(xp_settings["afk_muted_per_interval"]), max_length=5
        )
        self.daily_cap = discord.ui.TextInput(
            label="سقف يومي لـ XP ديال AFK (0 = بلا سقف)",
            default=str(xp_settings.get("afk_daily_cap", 0)), max_length=6
        )
        self.add_item(self.afk_channel_xp)
        self.add_item(self.afk_muted_xp)
        self.add_item(self.daily_cap)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            ch_xp = int(self.afk_channel_xp.value)
            mut_xp = int(self.afk_muted_xp.value)
            cap = int(self.daily_cap.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
            return
        if min(ch_xp, mut_xp, cap) < 0:
            await interaction.response.send_message("❌ ماكاينش رقم سالب.", ephemeral=True)
            return
        if ch_xp > xp_settings["voice_per_interval"] or mut_xp > xp_settings["voice_per_interval"]:
            await interaction.response.send_message(
                f"❌ XP ديال AFK خاصو يكون **أقل** من الفويس العادي "
                f"({xp_settings['voice_per_interval']} XP) — وإلا الناس غادي يفرميو وهوما ناعسين 😴",
                ephemeral=True
            )
            return

        xp_settings["afk_channel_per_interval"] = ch_xp
        xp_settings["afk_muted_per_interval"] = mut_xp
        xp_settings["afk_daily_cap"] = cap
        save_xp_settings()

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class LevelXPModal(discord.ui.Modal, title="📈 صعوبة المستويات (Levels)"):
    def __init__(self):
        super().__init__()
        self.multiplier = discord.ui.TextInput(
            label="مضاعف XP المطلوب للمستويات",
            default=str(xp_settings.get("level_xp_multiplier", 1.0)),
            placeholder="1.0 = عادي | 0.5 = نص (أسهل) | 2.0 = ضعف (أصعب)",
            max_length=6
        )
        self.add_item(self.multiplier)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_mult = float(self.multiplier.value)
        except ValueError:
            await interaction.response.send_message("❌ خاصها تكون رقم (مثلا 1.0 ولا 0.5).", ephemeral=True)
            return
        if new_mult <= 0:
            await interaction.response.send_message("❌ خاصها تكون أكبر من 0.", ephemeral=True)
            return

        xp_settings["level_xp_multiplier"] = round(new_mult, 3)
        save_xp_settings()

        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())


class XPPanelView(discord.ui.View):
    """أزرار لوحة تحكم XP — كل واحد كيحل Modal باش تبدل القيم ديال طريقة معينة.
    خاص الـ Owner بوحدو باش يستعملها، حتى ملي تكون الرسالة بانة لكل واحد."""

    def __init__(self):
        super().__init__(timeout=300)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not (OWNER_ID and interaction.user.id == OWNER_ID):
            await interaction.response.send_message("❌ هاد اللوحة خاصة غير بالـ Owner.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="عدل الشات", emoji="💬", style=discord.ButtonStyle.primary)
    async def edit_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ChatXPModal())

    @discord.ui.button(label="عدل الفويس", emoji="🎙️", style=discord.ButtonStyle.primary)
    async def edit_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(VoiceXPModal())

    @discord.ui.button(label="عدل اللايفستريم", emoji="📡", style=discord.ButtonStyle.primary)
    async def edit_stream(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(StreamXPModal())

    @discord.ui.button(label="عدل الـ AFK", emoji="💤", style=discord.ButtonStyle.primary)
    async def edit_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AfkXPModal())

    @discord.ui.button(label="صعوبة المستويات", emoji="📈", style=discord.ButtonStyle.primary, row=1)
    async def edit_level_difficulty(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LevelXPModal())

    @discord.ui.button(label="رجّع الافتراضي", emoji="↩️", style=discord.ButtonStyle.danger, row=1)
    async def reset_defaults(self, interaction: discord.Interaction, button: discord.ui.Button):
        interval_changed = xp_settings["voice_interval_minutes"] != VOICE_XP_INTERVAL_MINUTES
        xp_settings["chat_min"] = XP_MIN_PER_MESSAGE
        xp_settings["chat_max"] = XP_MAX_PER_MESSAGE
        xp_settings["chat_cooldown"] = XP_COOLDOWN_SECONDS
        xp_settings["voice_per_interval"] = VOICE_XP_PER_INTERVAL
        xp_settings["voice_interval_minutes"] = VOICE_XP_INTERVAL_MINUTES
        xp_settings["voice_min_humans"] = VOICE_XP_MIN_HUMANS_IN_CHANNEL
        xp_settings["stream_per_interval"] = STREAM_XP_PER_INTERVAL
        xp_settings["afk_channel_per_interval"] = AFK_CHANNEL_XP_PER_INTERVAL
        xp_settings["afk_muted_per_interval"] = AFK_MUTED_XP_PER_INTERVAL
        xp_settings["afk_daily_cap"] = AFK_XP_DAILY_CAP
        xp_settings["level_xp_multiplier"] = 1.0
        save_xp_settings()
        if interval_changed and voice_xp_loop.is_running():
            voice_xp_loop.change_interval(minutes=VOICE_XP_INTERVAL_MINUTES)
        await interaction.response.edit_message(embed=_xp_panel_embed(), view=self)




def recompute_level_from_total_xp(total_xp: int):
    """كتحسب (level, xp_داخل_المستوى) من مجموع XP كلي، حسب صيغة xp_needed_for_level
    الحالية (بحال xp_settings['level_xp_multiplier'] دابا). كتستعمل باش نعاودو نبنيو
    المستوى الصحيح بعد ما نزيدو/ننقصو XP يدوياً."""
    total_xp = max(0, total_xp)
    level = 0
    remaining = total_xp
    while remaining >= xp_needed_for_level(level):
        remaining -= xp_needed_for_level(level)
        level += 1
    return level, remaining


async def adjust_user_xp(member: discord.Member, guild: discord.Guild, amount: int) -> dict:
    """كيزيد/كينقص XP لعضو مباشرة (amount يقدر يكون سالب)، وكيعاود يحسب المستوى
    بالكامل من مجموع XP الكلي — يعني المستوى كيطلع ولا كيهبط تلقائياً حسب
    العدد الجديد (بحال طلبتي: نقصان XP يقدر يرجع العضو لمستوى تحتاني).
    كيعطي الرولات الناقصة إلا صعد لمستوى جديد."""
    data = get_user_level_data(guild.id, member.id)
    old_level = data["level"]
    old_total = total_xp_earned(data)

    new_total = max(0, old_total + amount)
    new_level, new_xp = recompute_level_from_total_xp(new_total)

    data["level"] = new_level
    data["xp"] = new_xp
    save_levels()

    roles_added, roles_removed = [], []
    if new_level != old_level:   # تبدل المستوى (صعد ولا هبط) → نعاودو نظبطو الرول
        roles_added, roles_removed = await sync_level_roles(member, guild, new_level)

    return {
        "old_level": old_level, "new_level": new_level,
        "old_total": old_total, "new_total": new_total,
        "roles_added": roles_added,
        "roles_removed": roles_removed,
    }




SOURCE_LABELS_AR = {
    "chat": "💬 شات",
    "voice": "🎤 فويس",
    "afk_channel": "💤 AFK (روم AFK)",
    "afk_muted": "🔇 AFK (مايك مسدود)",
    "stream": "🎥 لايفستريم",
    "unknown": "❓ ماشي معروف",
}


def build_xp_audit_embed(guild: discord.Guild, member: discord.Member) -> Optional[discord.Embed]:
    """نفس /xpaudit القديم ولكن قابل للاستعمال من Owner Panel."""
    summary = get_xp_audit_summary(guild.id, member.id)
    if summary["total_events"] == 0:
        return None

    embed = discord.Embed(
        title=f"🔍 XP Audit — {member.display_name}",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    data = get_user_level_data(guild.id, member.id)
    embed.add_field(
        name="📊 الوضع الحالي",
        value=(
            f"Level **{data['level']}** • "
            f"{data['xp']}/{xp_needed_for_level(data['level'])} XP للمستوى الجاي\n"
            f"مجموع XP إجمالي: **{total_xp_earned(data)}**"
        ),
        inline=False
    )

    dist_lines = []
    for src, info in sorted(summary["by_source"].items(), key=lambda x: -x[1]["total"]):
        label = SOURCE_LABELS_AR.get(src, src)
        dist_lines.append(f"{label}: **{info['total']}** XP ({info['count']} events)")
    embed.add_field(
        name=f"📈 التوزيع حسب المصدر ({summary['total_events']} events)",
        value="\n".join(dist_lines) if dist_lines else "—",
        inline=False
    )

    recent = summary["recent"][-15:]
    recent_lines = []
    for e in reversed(recent):
        ts = e.get("ts", "")[:16].replace("T", " ")
        label = SOURCE_LABELS_AR.get(e.get("source"), e.get("source"))
        ch = f" <#{e['channel']}>" if e.get("channel") else ""
        recent_lines.append(f"`{ts}` {label} +{e.get('amount')} XP{ch}")
    embed.add_field(
        name="🕒 آخر 15 events",
        value="\n".join(recent_lines) if recent_lines else "—",
        inline=False
    )

    chat_events = [e for e in summary["recent"] if e.get("source") == "chat"]
    if len(chat_events) >= 5:
        gaps = []
        for i in range(1, len(chat_events)):
            try:
                t1 = datetime.fromisoformat(chat_events[i - 1]["ts"])
                t2 = datetime.fromisoformat(chat_events[i]["ts"])
                gaps.append((t2 - t1).total_seconds())
            except Exception:
                pass
        if gaps:
            avg_gap = sum(gaps) / len(gaps)
            tight = sum(
                1 for g in gaps
                if xp_settings["chat_cooldown"] <= g <= xp_settings["chat_cooldown"] + 3
            )
            ratio = tight / len(gaps)
            if ratio >= 0.7 and avg_gap < xp_settings["chat_cooldown"] + 5:
                embed.add_field(
                    name="⚠️ ملاحظة",
                    value=(
                        f"{ratio*100:.0f}% من رسائلو الأخيرة قريبين بزاف من "
                        f"cooldown ({xp_settings['chat_cooldown']}ث). "
                        "يمكن نشاط عادي، ولكن يستاهل تشيك."
                    ),
                    inline=False
                )

    return embed


# Hidden prefix fallback فقط — ما بقاش Slash Command.


# ═══════════════════════════════════════════════════════
# ║      Bot Control Panel — لوحة تحكم شاملة (Admin)         ║
# ═══════════════════════════════════════════════════════
# لوحة واحدة كتجمع أغلب الحوايج اللي محتاجة تحكم متكرر (تفعيل/تعطيل، عتبات،
# مدد) بلا ماتمس الكود ولا تعاود ريستارت البوت — /botpanel

def _bool_emoji(value: bool) -> str:
    return "✅" if value else "❌"


def _main_panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎛️ لوحة تحكم البوت",
        description="اختار قسم من الأزرار تحت باش تشوف/تبدل الإعدادات ديالو. XP ليها لوحة خاصة بيها `/xppanel`.",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.add_field(
        name="🚨 Anti-Raid",
        value=(
            f"{_bool_emoji(bot_settings['anti_raid_enabled'])} الحالة\n"
            f"عتبة: **{bot_settings['raid_join_threshold']}** فـ **{bot_settings['raid_join_interval_seconds']}**ث\n"
            f"العمل: **{'حظر' if bot_settings['raid_action'] == 'ban' else 'طرد'}** | Lockdown: **{bot_settings['raid_lockdown_duration_minutes'] or '∞'}**د"
        ),
        inline=True
    )
    embed.add_field(
        name="⚠️ التحذيرات (Warns)",
        value=(
            f"🔇 كتم عند **{bot_settings['mute_after_warns']}** ({bot_settings['mute_duration_minutes']}د)\n"
            f"👢 طرد عند **{bot_settings['kick_after_warns']}**\n"
            f"🚫 حظر عند **{bot_settings['ban_after_warns']}**"
        ),
        inline=True
    )
    embed.add_field(
        name="📰 Auto-Info",
        value=(
            f"{_bool_emoji(bot_settings['auto_info_news'])} أخبار | "
            f"{_bool_emoji(bot_settings['auto_info_games'])} ألعاب | "
            f"{_bool_emoji(bot_settings['auto_info_movies'])} أفلام\n"
            f"{_bool_emoji(bot_settings['auto_info_anime'])} أنمي | "
            f"{_bool_emoji(bot_settings['auto_info_music'])} موسيقى"
        ),
        inline=False
    )
    embed.add_field(
        name="🧩 مميزات عامة",
        value=(
            f"{_bool_emoji(bot_settings['leveling_enabled'])} Leveling/XP | "
            f"{_bool_emoji(bot_settings['voice_xp_enabled'])} Voice XP\n"
            f"{_bool_emoji(bot_settings['join_to_create_enabled'])} Join to Create | "
            f"{_bool_emoji(bot_settings['welcome_card_enabled'])} Welcome Cards\n"
            f"{_bool_emoji(bot_settings['auto_translate_enabled'])} Auto-Translate | "
            f"{_bool_emoji(bot_settings['auto_react_enabled'])} Auto-React"
        ),
        inline=False
    )
    embed.set_footer(text=f"{SERVER_NAME} | Bot Control Panel")
    return embed


class BackToMainButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="رجوع", emoji="🔙", style=discord.ButtonStyle.secondary, row=4)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=_main_panel_embed(), view=MainPanelView())


class PanelPermissionView(discord.ui.View):
    """View بيز فيها فحص الصلاحية (Owner بوحدو) مشترك بين كل صفحات اللوحة."""

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not (OWNER_ID and interaction.user.id == OWNER_ID):
            await interaction.response.send_message("❌ هاد اللوحة خاصة غير بالـ Owner.", ephemeral=True)
            return False
        return True


# ───────────── Anti-Raid ─────────────

def _anti_raid_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🚨 إعدادات Anti-Raid",
        color=discord.Color.red() if bot_settings["anti_raid_enabled"] else discord.Color.greyple(),
        timestamp=datetime.now()
    )
    embed.add_field(name="الحالة", value=_bool_emoji(bot_settings["anti_raid_enabled"]), inline=True)
    embed.add_field(name="العمل", value="🚫 حظر" if bot_settings["raid_action"] == "ban" else "👢 طرد", inline=True)
    embed.add_field(
        name="مدة Lockdown",
        value=f"{bot_settings['raid_lockdown_duration_minutes']} دقيقة" if bot_settings["raid_lockdown_duration_minutes"] else "حتى /unlockdown يدوي",
        inline=True
    )
    embed.add_field(
        name="العتبة",
        value=f"**{bot_settings['raid_join_threshold']}** عضو جديد فـ **{bot_settings['raid_join_interval_seconds']}** ثانية",
        inline=False
    )
    return embed


class AntiRaidSettingsModal(discord.ui.Modal, title="🚨 إعدادات Anti-Raid"):
    def __init__(self):
        super().__init__()
        self.threshold = discord.ui.TextInput(
            label="عدد الأعضاء الجداد (العتبة)", default=str(bot_settings["raid_join_threshold"]), max_length=4
        )
        self.interval = discord.ui.TextInput(
            label="فـ هاد المدة بالثواني", default=str(bot_settings["raid_join_interval_seconds"]), max_length=5
        )
        self.action = discord.ui.TextInput(
            label="العمل: اكتب kick ولا ban", default=bot_settings["raid_action"], max_length=4
        )
        self.lockdown_minutes = discord.ui.TextInput(
            label="مدة Lockdown بالدقايق (0 = يدوي فقط)",
            default=str(bot_settings["raid_lockdown_duration_minutes"]), max_length=5
        )
        self.add_item(self.threshold)
        self.add_item(self.interval)
        self.add_item(self.action)
        self.add_item(self.lockdown_minutes)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_threshold = int(self.threshold.value)
            new_interval = int(self.interval.value)
            new_lockdown = int(self.lockdown_minutes.value)
        except ValueError:
            await interaction.response.send_message("❌ العتبة/المدة/Lockdown خاصهم يكونو أرقام صحيحة.", ephemeral=True)
            return
        new_action = self.action.value.strip().lower()
        if new_action not in ("kick", "ban"):
            await interaction.response.send_message("❌ العمل خاصو يكون `kick` ولا `ban` فقط.", ephemeral=True)
            return
        if new_threshold < 1 or new_interval < 1 or new_lockdown < 0:
            await interaction.response.send_message("❌ العتبة والمدة خاصهم يكونو أكبر من 0.", ephemeral=True)
            return

        bot_settings["raid_join_threshold"] = new_threshold
        bot_settings["raid_join_interval_seconds"] = new_interval
        bot_settings["raid_action"] = new_action
        bot_settings["raid_lockdown_duration_minutes"] = new_lockdown
        save_bot_settings()

        await interaction.response.edit_message(embed=_anti_raid_embed(), view=AntiRaidView())


class AntiRaidView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(BackToMainButton())

    @discord.ui.button(label="تفعيل/تعطيل", emoji="🔌", style=discord.ButtonStyle.primary)
    async def toggle_enabled(self, interaction: discord.Interaction, button: discord.ui.Button):
        bot_settings["anti_raid_enabled"] = not bot_settings["anti_raid_enabled"]
        save_bot_settings()
        await interaction.response.edit_message(embed=_anti_raid_embed(), view=self)

    @discord.ui.button(label="عدل القيم", emoji="✏️", style=discord.ButtonStyle.primary)
    async def edit_values(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AntiRaidSettingsModal())


# ───────────── Warns Escalation ─────────────

def _warns_embed() -> discord.Embed:
    embed = discord.Embed(title="⚠️ تصعيد التحذيرات (Warns)", color=discord.Color.orange(), timestamp=datetime.now())
    embed.add_field(name="🔇 كتم", value=f"عند **{bot_settings['mute_after_warns']}** تحذيرات، **{bot_settings['mute_duration_minutes']}** دقيقة", inline=False)
    embed.add_field(name="👢 طرد", value=f"عند **{bot_settings['kick_after_warns']}** تحذيرات", inline=False)
    embed.add_field(name="🚫 حظر", value=f"عند **{bot_settings['ban_after_warns']}** تحذيرات", inline=False)
    return embed


class WarnsSettingsModal(discord.ui.Modal, title="⚠️ تصعيد التحذيرات"):
    def __init__(self):
        super().__init__()
        self.mute_after = discord.ui.TextInput(label="كتم عند شحال تحذير", default=str(bot_settings["mute_after_warns"]), max_length=3)
        self.mute_minutes = discord.ui.TextInput(label="مدة الكتم بالدقايق", default=str(bot_settings["mute_duration_minutes"]), max_length=5)
        self.kick_after = discord.ui.TextInput(label="طرد عند شحال تحذير", default=str(bot_settings["kick_after_warns"]), max_length=3)
        self.ban_after = discord.ui.TextInput(label="حظر عند شحال تحذير", default=str(bot_settings["ban_after_warns"]), max_length=3)
        self.add_item(self.mute_after)
        self.add_item(self.mute_minutes)
        self.add_item(self.kick_after)
        self.add_item(self.ban_after)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_mute_after = int(self.mute_after.value)
            new_mute_minutes = int(self.mute_minutes.value)
            new_kick_after = int(self.kick_after.value)
            new_ban_after = int(self.ban_after.value)
        except ValueError:
            await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
            return
        if min(new_mute_after, new_mute_minutes, new_kick_after, new_ban_after) < 0:
            await interaction.response.send_message("❌ ماكاينش أرقام سالبة.", ephemeral=True)
            return
        if not (new_mute_after <= new_kick_after <= new_ban_after):
            await interaction.response.send_message(
                "❌ خاص الترتيب يكون منطقي: كتم ≤ طرد ≤ حظر (بعدد التحذيرات).", ephemeral=True
            )
            return

        bot_settings["mute_after_warns"] = new_mute_after
        bot_settings["mute_duration_minutes"] = new_mute_minutes
        bot_settings["kick_after_warns"] = new_kick_after
        bot_settings["ban_after_warns"] = new_ban_after
        save_bot_settings()

        await interaction.response.edit_message(embed=_warns_embed(), view=WarnsView())


class WarnsView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(BackToMainButton())

    @discord.ui.button(label="عدل القيم", emoji="✏️", style=discord.ButtonStyle.primary)
    async def edit_values(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WarnsSettingsModal())


# ───────────── Auto-Info Toggles ─────────────

def _auto_info_embed() -> discord.Embed:
    embed = discord.Embed(title="📰 Auto-Info — تفعيل/تعطيل كل فئة", color=discord.Color.teal(), timestamp=datetime.now())
    embed.add_field(name="📰 أخبار", value=_bool_emoji(bot_settings["auto_info_news"]), inline=True)
    embed.add_field(name="🎮 ألعاب", value=_bool_emoji(bot_settings["auto_info_games"]), inline=True)
    embed.add_field(name="🎬 أفلام", value=_bool_emoji(bot_settings["auto_info_movies"]), inline=True)
    embed.add_field(name="📺 أنمي", value=_bool_emoji(bot_settings["auto_info_anime"]), inline=True)
    embed.add_field(name="🎧 موسيقى", value=_bool_emoji(bot_settings["auto_info_music"]), inline=True)
    return embed


class AutoInfoView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(BackToMainButton())

    async def _toggle(self, interaction: discord.Interaction, key: str):
        bot_settings[key] = not bot_settings[key]
        save_bot_settings()
        await interaction.response.edit_message(embed=_auto_info_embed(), view=self)

    @discord.ui.button(label="أخبار", emoji="📰", style=discord.ButtonStyle.secondary)
    async def toggle_news(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_news")

    @discord.ui.button(label="ألعاب", emoji="🎮", style=discord.ButtonStyle.secondary)
    async def toggle_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_games")

    @discord.ui.button(label="أفلام", emoji="🎬", style=discord.ButtonStyle.secondary)
    async def toggle_movies(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_movies")

    @discord.ui.button(label="أنمي", emoji="📺", style=discord.ButtonStyle.secondary)
    async def toggle_anime(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_anime")

    @discord.ui.button(label="موسيقى", emoji="🎧", style=discord.ButtonStyle.secondary)
    async def toggle_music(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_info_music")


# ───────────── مميزات عامة (Feature Toggles) ─────────────

def _features_embed() -> discord.Embed:
    embed = discord.Embed(title="🧩 مميزات عامة — تفعيل/تعطيل", color=discord.Color.blurple(), timestamp=datetime.now())
    embed.add_field(name="📊 Leveling/XP", value=_bool_emoji(bot_settings["leveling_enabled"]), inline=True)
    embed.add_field(name="🎙️ Voice XP", value=_bool_emoji(bot_settings["voice_xp_enabled"]), inline=True)
    embed.add_field(name="🔊 Join to Create", value=_bool_emoji(bot_settings["join_to_create_enabled"]), inline=True)
    embed.add_field(name="🖼️ Welcome Cards", value=_bool_emoji(bot_settings["welcome_card_enabled"]), inline=True)
    embed.add_field(name="🌐 Auto-Translate", value=_bool_emoji(bot_settings["auto_translate_enabled"]), inline=True)
    embed.add_field(name="⚡ Auto-React", value=_bool_emoji(bot_settings["auto_react_enabled"]), inline=True)
    return embed


class FeaturesView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(BackToMainButton())

    async def _toggle(self, interaction: discord.Interaction, key: str):
        bot_settings[key] = not bot_settings[key]
        save_bot_settings()
        await interaction.response.edit_message(embed=_features_embed(), view=self)

    @discord.ui.button(label="Leveling/XP", emoji="📊", style=discord.ButtonStyle.secondary)
    async def toggle_leveling(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "leveling_enabled")

    @discord.ui.button(label="Voice XP", emoji="🎙️", style=discord.ButtonStyle.secondary)
    async def toggle_voice_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "voice_xp_enabled")

    @discord.ui.button(label="Join to Create", emoji="🔊", style=discord.ButtonStyle.secondary)
    async def toggle_j2c(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "join_to_create_enabled")

    @discord.ui.button(label="Welcome Cards", emoji="🖼️", style=discord.ButtonStyle.secondary)
    async def toggle_welcome(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not PIL_AVAILABLE:
            await interaction.response.send_message("❌ Pillow ماشي مثبتة فالسيرفر، Welcome Cards ماغاديش تخدم حتى لو شعلتيها.", ephemeral=True)
            return
        await self._toggle(interaction, "welcome_card_enabled")

    @discord.ui.button(label="Auto-Translate", emoji="🌐", style=discord.ButtonStyle.secondary)
    async def toggle_translate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_translate_enabled")

    @discord.ui.button(label="Auto-React", emoji="⚡", style=discord.ButtonStyle.secondary)
    async def toggle_react(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "auto_react_enabled")


# ───────────── اللوحة الرئيسية ─────────────

class MainPanelView(PanelPermissionView):
    def __init__(self):
        super().__init__(timeout=300)

    @discord.ui.button(label="Anti-Raid", emoji="🚨", style=discord.ButtonStyle.primary)
    async def open_anti_raid(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_anti_raid_embed(), view=AntiRaidView())

    @discord.ui.button(label="التحذيرات", emoji="⚠️", style=discord.ButtonStyle.primary)
    async def open_warns(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_warns_embed(), view=WarnsView())

    @discord.ui.button(label="Auto-Info", emoji="📰", style=discord.ButtonStyle.primary)
    async def open_auto_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_auto_info_embed(), view=AutoInfoView())

    @discord.ui.button(label="مميزات عامة", emoji="🧩", style=discord.ButtonStyle.primary)
    async def open_features(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_features_embed(), view=FeaturesView())

    @discord.ui.button(label="XP Panel", emoji="📊", style=discord.ButtonStyle.success, row=1)
    async def open_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())




# ═══════════════════════════════════════════════════════
# ║              Leveling System — أوامر                     ║
# ═══════════════════════════════════════════════════════

def _progress_bar(current: int, needed: int, length: int = 20) -> str:
    ratio = max(0, min(1, current / needed)) if needed else 0
    filled = int(length * ratio)
    return "🟩" * filled + "⬛" * (length - filled)


def get_current_member_xp_ranking(guild: discord.Guild):
    """
    Ranking ديال XP كيشمل غير الأعضاء اللي مازالين داخل السيرفر دابا.

    مهم:
    - ما كنمسحوش levels_db ديال اللي خرج.
    - غير كنخبيه من الترتيب وهو خارج.
    - إلا رجع، نفس XP المحفوظة كتردو للمركز اللي كيستحق حسب XP.
    """
    guild_data = levels_db.get(str(guild.id), {})
    if not guild_data:
        return []

    # intents.members=True عند البوت، لذلك guild.members هو source واضح للأعضاء الحاليين.
    current_member_ids = {
        str(member.id)
        for member in guild.members
        if not member.bot
    }

    return sorted(
        (
            (uid, data)
            for uid, data in guild_data.items()
            if uid in current_member_ids
        ),
        key=lambda item: total_xp_earned(item[1]),
        reverse=True,
    )


def build_rank_embed(guild: discord.Guild, member: discord.Member) -> discord.Embed:
    """نفس Rank ديال /rank، قابل للاستعمال من الـ Levels Info Panel بلا كتابة."""
    data = get_user_level_data(guild.id, member.id)
    needed = xp_needed_for_level(data["level"])

    ranking = get_current_member_xp_ranking(guild)
    rank_position = next(
        (i + 1 for i, (uid, _) in enumerate(ranking) if uid == str(member.id)),
        None
    )

    badge = ""
    if data["level"] >= 100:
        badge = "👑 "
    elif data["level"] >= 70:
        badge = "🌟 "

    embed = discord.Embed(
        title=f"📊 المستوى ديال {badge}{member.display_name}",
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏆 Level", value=str(data["level"]), inline=True)
    embed.add_field(
        name="🥇 الترتيب",
        value=f"#{rank_position}" if rank_position else "—",
        inline=True
    )
    embed.add_field(name="✨ XP", value=f"{data['xp']} / {needed}", inline=True)
    embed.add_field(
        name="التقدم",
        value=_progress_bar(data["xp"], needed),
        inline=False
    )

    active_perks = get_level_perks(data["level"])
    embed.add_field(
        name="🎁 الامتيازات الحالية",
        value=(
            f"**{active_perks['name']}**\n"
            f"🛒 Shop: **-{active_perks['shop_discount_percent']}%** • "
            f"🎁 Daily: **+{active_perks['daily_bonus_percent']}%**\n"
            f"🏦 Loan Base: **{cfg.fmt_money(active_perks['loan_base'])}** • "
            f"Interest **{active_perks['loan_interest']}%** • "
            f"**{active_perks['loan_days']}d**\n"
            f"{active_perks['feature']}"
        ),
        inline=False,
    )

    next_perks = get_next_level_perks(data["level"])
    if next_perks:
        embed.add_field(
            name="🚀 الهدف الجاي",
            value=(
                f"Level **{next_perks['threshold']}** — **{next_perks['name']}**\n"
                f"🛒 -{next_perks['shop_discount_percent']}% • "
                f"🎁 +{next_perks['daily_bonus_percent']}% • "
                f"🏦 {cfg.fmt_money(next_perks['loan_base'])} / "
                f"{next_perks['loan_interest']}% / {next_perks['loan_days']}d"
            ),
            inline=False,
        )

    if get_active_xp_multiplier(data) > 1.0:
        try:
            expires_dt = datetime.fromisoformat(data["xp_boost_expires"])
            embed.add_field(
                name="🚀 بونيص XP نشط",
                value=(
                    f"+{LEVEL_MILESTONE_XP_BOOST_PERCENT}% حتى "
                    f"<t:{int(expires_dt.timestamp())}:R>"
                ),
                inline=False
            )
        except Exception:
            pass

    if data.get("bio"):
        embed.add_field(name="📝 بيو", value=data["bio"][:200], inline=False)

    embed.set_footer(text=f"{SERVER_NAME} | Leveling System")
    return embed






class SimplePollView(discord.ui.View):
    def __init__(self, options: list):
        super().__init__(timeout=None)
        self.votes = {opt: set() for opt in options}
        for i, opt in enumerate(options):
            self.add_item(self._make_button(opt, i))

    def _make_button(self, option_text: str, index: int):
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        btn = discord.ui.Button(label=option_text[:80], emoji=emojis[index] if index < len(emojis) else None,
                                 style=discord.ButtonStyle.primary, custom_id=f"poll_opt_{index}")

        async def callback(interaction: discord.Interaction):
            for voters in self.votes.values():
                voters.discard(interaction.user.id)
            self.votes[option_text].add(interaction.user.id)
            lines = [f"**{opt}** — {len(voters)} صوت" for opt, voters in self.votes.items()]
            await interaction.response.edit_message(
                embed=discord.Embed(
                    title=interaction.message.embeds[0].title,
                    description="\n".join(lines),
                    color=discord.Color.blurple()
                ),
                view=self
            )

        btn.callback = callback
        return btn



# ═══════════════════════════════════════════════════════
# ║   📊 Levels Info Center — كلشي Click بلا Commands      ║
# ═══════════════════════════════════════════════════════

class XPBioModal(discord.ui.Modal, title="📝 البيو ديالك"):
    bio_text = discord.ui.TextInput(
        label="البيو",
        placeholder="كتب bio قصيرة... وخليها خاوية باش تمسحها",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=200,
    )

    async def on_submit(self, interaction: discord.Interaction):
        data = get_user_level_data(interaction.guild.id, interaction.user.id)
        if data["level"] < 20:
            await interaction.response.send_message(
                "🔒 Bio كتفتح فـ **Level 20**.",
                ephemeral=True,
            )
            return
        data["bio"] = str(self.bio_text.value).strip()[:200]
        save_levels()
        if data["bio"]:
            await interaction.response.send_message(
                f"✅ تبدلات الـBio ديالك لـ:\n> {data['bio']}",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "✅ تمسحات الـBio ديالك.",
                ephemeral=True,
            )


class XPLegendTitleModal(discord.ui.Modal, title="👑 Legend Title"):
    title_text = discord.ui.TextInput(
        label="سمية الرول الشخصية",
        placeholder="مثال: GGMW9 King",
        required=True,
        max_length=90,
    )

    async def on_submit(self, interaction: discord.Interaction):
        data = get_user_level_data(interaction.guild.id, interaction.user.id)
        if data["level"] < 100:
            await interaction.response.send_message(
                "🔒 Legend Title كتفتح غير فـ **Level 100**.",
                ephemeral=True,
            )
            return

        role = await get_or_create_legend_role(interaction.guild, interaction.user)
        if not role:
            await interaction.response.send_message(
                "❌ ما قدرتش نصاوب/نلقى Legend Role ديالك. شيك صلاحيات البوت.",
                ephemeral=True,
            )
            return

        new_name = f"👑 {str(self.title_text.value).strip()}"[:100]
        try:
            await role.edit(
                name=new_name,
                reason=f"Levels Info Panel — Legend title — {interaction.user}",
            )
            await interaction.response.send_message(
                f"✅ Legend Role ديالك ولات: **{new_name}**",
                ephemeral=True,
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.response.send_message(
                f"❌ ما قدرتش نبدل السمية: {e}",
                ephemeral=True,
            )


class XPCreatePollModal(discord.ui.Modal, title="🗳️ صاوب Poll"):
    question = discord.ui.TextInput(
        label="السؤال",
        placeholder="شنو بغيتي تسول الناس؟",
        required=True,
        max_length=200,
    )
    options_text = discord.ui.TextInput(
        label="الاختيارات — فرق بينهم بـ |",
        placeholder="مثال: PS5 | Xbox | PC",
        required=True,
        max_length=500,
    )

    def __init__(self, user_id: int, target_channel):
        super().__init__()
        self.user_id = user_id
        self.target_channel = target_channel

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return

        data = get_user_level_data(interaction.guild.id, interaction.user.id)
        if data["level"] < 60:
            await interaction.response.send_message(
                "🔒 إنشاء Poll كيتفتح فـ **Level 60**.",
                ephemeral=True,
            )
            return

        opts = [
            o.strip()
            for o in str(self.options_text.value).split("|")
            if o.strip()
        ][:5]
        if len(opts) < 2:
            await interaction.response.send_message(
                "❌ خاص على الأقل جوج اختيارات مفصولين بـ `|`.",
                ephemeral=True,
            )
            return

        embed = discord.Embed(
            title=f"🗳️ {str(self.question.value).strip()}",
            description="\n".join(f"**{o}** — 0 صوت" for o in opts),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(
            text=f"صاوبها {interaction.user.display_name} | {SERVER_NAME}"
        )
        try:
            sent = await self.target_channel.send(
                embed=embed,
                view=SimplePollView(opts),
            )
            await interaction.response.send_message(
                f"✅ الـPoll تنشرات فـ {self.target_channel.mention}.\n{sent.jump_url}",
                ephemeral=True,
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            await interaction.response.send_message(
                f"❌ ما قدرتش نبعث فالشانيل المختارة: {e}",
                ephemeral=True,
            )


class XPPollChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(
            placeholder="📍 اختار الشانيل اللي غادي تنشر فيه الـPoll",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        target = self.values[0]
        await interaction.response.send_modal(
            XPCreatePollModal(interaction.user.id, target)
        )


class XPPollDestinationView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=120)
        self.add_item(XPPollChannelSelect(user_id))


class XPRankMemberSelect(discord.ui.UserSelect):
    """Transient User Select: كيبان داخل ephemeral response فقط."""

    def __init__(self):
        super().__init__(
            placeholder="👤 اختار عضو باش تشوف الرتبة ديالو",
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if not bot_settings["leveling_enabled"]:
            await interaction.response.edit_message(
                content="❌ نظام XP معطل دابا.",
                embed=None,
                view=None,
            )
            return

        selected = self.values[0]
        member = interaction.guild.get_member(selected.id)
        if not member:
            try:
                member = await interaction.guild.fetch_member(selected.id)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                member = None

        if not member:
            await interaction.response.edit_message(
                content="❌ ما قدرتش نجيب معلومات هاد العضو.",
                embed=None,
                view=None,
            )
            return

        await interaction.response.edit_message(
            content=None,
            embed=build_rank_embed(interaction.guild, member),
            view=None,
        )


class XPRankMemberView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(XPRankMemberSelect())


class LevelsResultView(discord.ui.View):
    def __init__(self,user_id:int,lang="darija"):
        super().__init__(timeout=1800); self.user_id,self.lang=int(user_id),lang
        label="Back to Levels" if lang=="en" else "Retour aux niveaux" if lang=="fr" else "رجع للمستويات"
        b=discord.ui.Button(label="↩️ "+label,style=discord.ButtonStyle.secondary,row=0); b.callback=self.back; self.add_item(b); self.add_item(GlobalPrivateLanguageSelect("levels",user_id,lang,row=1))
    async def back(self,interaction):
        if interaction.user.id!=self.user_id: await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.",ephemeral=True); return
        await interaction.response.edit_message(content=None,embed=_panel_language_guide_embed("levels",self.lang),view=LevelsPrivateView(self.user_id,self.lang))


class XPRankMemberPrivateSelect(discord.ui.UserSelect):
    def __init__(self,user_id:int,lang="darija"):
        self.user_id,self.lang=int(user_id),lang
        ph="👤 Choose a member" if lang=="en" else "👤 Choisis un membre" if lang=="fr" else "👤 اختار عضو باش تشوف الرتبة ديالو"
        super().__init__(placeholder=ph,min_values=1,max_values=1,row=0)
    async def callback(self,interaction):
        if interaction.user.id!=self.user_id: await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.",ephemeral=True); return
        selected=self.values[0]; member=interaction.guild.get_member(selected.id)
        if not member:
            try: member=await interaction.guild.fetch_member(selected.id)
            except Exception: member=None
        if not member:
            msg="❌ Could not load that member." if self.lang=="en" else "❌ Impossible de charger ce membre." if self.lang=="fr" else "❌ ما قدرتش نجيب معلومات هاد العضو."
            await interaction.response.edit_message(content=msg,embed=None,view=LevelsResultView(self.user_id,self.lang)); return
        await interaction.response.edit_message(content=None,embed=build_rank_embed(interaction.guild,member),view=LevelsResultView(self.user_id,self.lang))


class XPRankMemberPrivateView(discord.ui.View):
    def __init__(self,user_id:int,lang="darija"):
        super().__init__(timeout=1800); self.add_item(XPRankMemberPrivateSelect(user_id,lang)); self.add_item(GlobalPrivateLanguageSelect("levels",user_id,lang,row=1))


class LevelsPrivateView(discord.ui.View):
    def __init__(self,user_id:int,lang="darija"):
        super().__init__(timeout=1800); self.user_id,self.lang=int(user_id),lang
        labels={
            "darija":["الرتبة ديالي","رتبة عضو","الترتيب","مسار التقدم","بدل النبذة","صاوب استفتاء","اللقب الأسطوري"],
            "en":["My Rank","Member Rank","Leaderboard","Roadmap","Edit Bio","Create Poll","Legend Title"],
            "fr":["Mon rang","Rang d'un membre","Classement","Progression","Modifier Bio","Créer un sondage","Titre Legend"],
        }[lang if lang in {"darija","en","fr"} else "darija"]
        defs=[("📊",labels[0],discord.ButtonStyle.success,self.my_rank),("👤",labels[1],discord.ButtonStyle.primary,self.member_rank),("🏆",labels[2],discord.ButtonStyle.primary,self.leaderboard),("🪜",labels[3],discord.ButtonStyle.secondary,self.roadmap),("📝",labels[4],discord.ButtonStyle.secondary,self.bio),("🗳️",labels[5],discord.ButtonStyle.secondary,self.create_poll),("👑",labels[6],discord.ButtonStyle.secondary,self.legend_title)]
        for i,(emoji,label,style,cb) in enumerate(defs):
            b=discord.ui.Button(label=label,emoji=emoji,style=style,row=0 if i<4 else 1); b.callback=cb; self.add_item(b)
        self.add_item(GlobalPrivateLanguageSelect("levels",self.user_id,lang,row=2))
    async def _ok(self,interaction):
        if interaction.user.id!=self.user_id: await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.",ephemeral=True); return False
        return True
    async def my_rank(self,interaction):
        if not await self._ok(interaction): return
        if not bot_settings["leveling_enabled"]:
            msg="❌ XP system is disabled." if self.lang=="en" else "❌ Le système XP est désactivé." if self.lang=="fr" else "❌ نظام XP معطل دابا."; await interaction.response.edit_message(content=msg,embed=None,view=self); return
        await interaction.response.edit_message(content=None,embed=build_rank_embed(interaction.guild,interaction.user),view=LevelsResultView(self.user_id,self.lang))
    async def member_rank(self,interaction):
        if not await self._ok(interaction): return
        msg="👤 Choose the member:" if self.lang=="en" else "👤 Choisis le membre :" if self.lang=="fr" else "👤 اختار العضو اللي بغيتي تشوف الرتبة ديالو:"
        await interaction.response.edit_message(content=msg,embed=None,view=XPRankMemberPrivateView(self.user_id,self.lang))
    async def leaderboard(self,interaction):
        if not await self._ok(interaction): return
        embed=build_leaderboard_embed(interaction.guild)
        if not embed:
            msg="ℹ️ No XP recorded yet." if self.lang=="en" else "ℹ️ Aucun XP enregistré." if self.lang=="fr" else "ℹ️ ماكاين حتى XP مسجل دابا."; await interaction.response.edit_message(content=msg,embed=None,view=self); return
        await interaction.response.edit_message(content=None,embed=embed,view=LevelsResultView(self.user_id,self.lang))
    async def roadmap(self,interaction):
        if await self._ok(interaction): await interaction.response.edit_message(content=None,embed=build_levelroadmap_embed(),view=LevelsResultView(self.user_id,self.lang))
    async def bio(self,interaction):
        if not await self._ok(interaction): return
        data=get_user_level_data(interaction.guild.id,interaction.user.id)
        if data["level"]<20:
            msg=(f"🔒 Bio unlocks at **Level 20**. You are Level **{data['level']}**." if self.lang=="en" else f"🔒 La Bio se débloque au **niveau 20**. Tu es niveau **{data['level']}**." if self.lang=="fr" else f"🔒 النبذة الشخصية كتفتح فـ **المستوى 20**. نتا دابا فالمستوى **{data['level']}**."); await interaction.response.edit_message(content=msg,embed=None,view=self); return
        await interaction.response.send_modal(XPBioModal())
    async def create_poll(self,interaction):
        if not await self._ok(interaction): return
        data=get_user_level_data(interaction.guild.id,interaction.user.id)
        if data["level"]<60:
            msg=(f"🔒 Polls unlock at **Level 60**. You are Level **{data['level']}**." if self.lang=="en" else f"🔒 Les sondages se débloquent au **niveau 60**. Tu es niveau **{data['level']}**." if self.lang=="fr" else f"🔒 الاستفتاءات كتفتح فـ **المستوى 60**. نتا دابا فالمستوى **{data['level']}**."); await interaction.response.edit_message(content=msg,embed=None,view=self); return
        msg="📍 Choose the channel for your poll:" if self.lang=="en" else "📍 Choisis le salon du sondage :" if self.lang=="fr" else "📍 اختار القناة اللي بغيتي تنشر فيها الاستفتاء:"
        await interaction.response.edit_message(content=msg,embed=None,view=XPPollDestinationView(interaction.user.id))
    async def legend_title(self,interaction):
        if not await self._ok(interaction): return
        data=get_user_level_data(interaction.guild.id,interaction.user.id)
        if data["level"]<100:
            msg=(f"🔒 Legend Title unlocks at **Level 100**. You are Level **{data['level']}**." if self.lang=="en" else f"🔒 Le titre Legend se débloque au **niveau 100**. Tu es niveau **{data['level']}**." if self.lang=="fr" else f"🔒 اللقب الأسطوري كيفتح فـ **المستوى 100**. نتا دابا فالمستوى **{data['level']}**."); await interaction.response.edit_message(content=msg,embed=None,view=self); return
        await interaction.response.send_modal(XPLegendTitleModal())


class LevelsInfoView(discord.ui.View):
    """Persistent public XP Center. Public message stays Darija; localized sessions are private."""
    def __init__(self, lang: str = "darija"):
        super().__init__(timeout=None)
        self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
        labels = {
            "darija": ["Rank ديالي", "Rank ديال عضو", "Leaderboard", "Roadmap", "بدل Bio", "صاوب Poll", "Legend Title"],
            "en": ["My Rank", "Member Rank", "Leaderboard", "Roadmap", "Edit Bio", "Create Poll", "Legend Title"],
            "fr": ["Mon rang", "Rang d'un membre", "Classement", "Progression", "Modifier Bio", "Créer un sondage", "Titre Legend"],
        }[self.lang]
        specs = [
            ("ggmw9:levels:my_rank", "📊", labels[0], discord.ButtonStyle.success, self.my_rank, 0),
            ("ggmw9:levels:member_rank_button", "👤", labels[1], discord.ButtonStyle.primary, self.member_rank, 0),
            ("ggmw9:levels:leaderboard", "🏆", labels[2], discord.ButtonStyle.primary, self.leaderboard, 0),
            ("ggmw9:levels:roadmap", "🪜", labels[3], discord.ButtonStyle.secondary, self.roadmap, 0),
            ("ggmw9:levels:bio", "📝", labels[4], discord.ButtonStyle.secondary, self.bio, 2),
            ("ggmw9:levels:create_poll", "🗳️", labels[5], discord.ButtonStyle.secondary, self.create_poll, 2),
            ("ggmw9:levels:legend_title", "👑", labels[6], discord.ButtonStyle.secondary, self.legend_title, 2),
        ]
        for custom_id, emoji, label, style, cb, row in specs:
            b = discord.ui.Button(custom_id=custom_id, emoji=emoji, label=label[:80], style=style, row=row)
            b.callback = cb
            self.add_item(b)
        self.add_item(GlobalPanelLanguageSelect("levels", self.lang, row=1))

    def _sync(self, interaction):
        return get_panel_language(interaction.guild.id, interaction.user.id)

    async def my_rank(self, interaction):
        lang = self._sync(interaction)
        if not bot_settings["leveling_enabled"]:
            msg = "❌ XP is disabled right now." if lang=="en" else "❌ Le système XP est désactivé." if lang=="fr" else "❌ نظام XP معطل دابا."
            await interaction.response.send_message(msg, ephemeral=True); return
        await interaction.response.send_message(embed=build_rank_embed(interaction.guild, interaction.user), ephemeral=True)

    async def member_rank(self, interaction):
        lang = self._sync(interaction)
        if not bot_settings["leveling_enabled"]:
            msg = "❌ XP is disabled right now." if lang=="en" else "❌ Le système XP est désactivé." if lang=="fr" else "❌ نظام XP معطل دابا."
            await interaction.response.send_message(msg, ephemeral=True); return
        prompt = "👤 Choose a member:" if lang=="en" else "👤 Choisis un membre :" if lang=="fr" else "👤 اختار العضو اللي بغيتي تشوف الرتبة ديالو:"
        await interaction.response.send_message(prompt, view=XPRankMemberView(), ephemeral=True)

    async def leaderboard(self, interaction):
        lang = self._sync(interaction)
        embed = build_leaderboard_embed(interaction.guild)
        if not embed:
            msg = "ℹ️ No XP recorded yet." if lang=="en" else "ℹ️ Aucun XP enregistré." if lang=="fr" else "ℹ️ ماكاين حتى XP مسجل دابا."
            await interaction.response.send_message(msg, ephemeral=True); return
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def roadmap(self, interaction):
        self._sync(interaction)
        await interaction.response.send_message(embed=build_levelroadmap_embed(), ephemeral=True)

    async def bio(self, interaction):
        lang = self._sync(interaction)
        data = get_user_level_data(interaction.guild.id, interaction.user.id)
        if data["level"] < 20:
            msg = (f"🔒 Bio unlocks at **Level 20**. You are Level **{data['level']}**." if lang=="en" else f"🔒 La Bio se débloque au **niveau 20**. Tu es niveau **{data['level']}**." if lang=="fr" else f"🔒 النبذة الشخصية كتفتح فـ **المستوى 20**. نتا دابا فالمستوى **{data['level']}**.")
            await interaction.response.send_message(msg, ephemeral=True); return
        await interaction.response.send_modal(XPBioModal())

    async def create_poll(self, interaction):
        lang = self._sync(interaction)
        data = get_user_level_data(interaction.guild.id, interaction.user.id)
        if data["level"] < 60:
            msg = (f"🔒 Polls unlock at **Level 60**. You are Level **{data['level']}**." if lang=="en" else f"🔒 Les sondages se débloquent au **niveau 60**. Tu es niveau **{data['level']}**." if lang=="fr" else f"🔒 الاستفتاءات كتفتح فـ **المستوى 60**. نتا دابا فالمستوى **{data['level']}**.")
            await interaction.response.send_message(msg, ephemeral=True); return
        prompt = "📍 Choose the channel for your poll:" if lang=="en" else "📍 Choisis le salon du sondage :" if lang=="fr" else "📍 اختار القناة اللي بغيتي تنشر فيها الاستفتاء:"
        await interaction.response.send_message(prompt, view=XPPollDestinationView(interaction.user.id), ephemeral=True)

    async def legend_title(self, interaction):
        lang = self._sync(interaction)
        data = get_user_level_data(interaction.guild.id, interaction.user.id)
        if data["level"] < 100:
            msg = (f"🔒 Legend Title unlocks at **Level 100**. You are Level **{data['level']}**." if lang=="en" else f"🔒 Le titre Legend se débloque au **niveau 100**. Tu es niveau **{data['level']}**." if lang=="fr" else f"🔒 اللقب الأسطوري كيفتح فـ **المستوى 100**. نتا دابا فالمستوى **{data['level']}**.")
            await interaction.response.send_message(msg, ephemeral=True); return
        await interaction.response.send_modal(XPLegendTitleModal())






def build_levelroadmap_embed() -> discord.Embed:
    lines = []
    for lvl in sorted(LEVEL_ROLES.keys()):
        p = LEVEL_ROLE_BENEFITS[lvl]
        lines.append(
            f"**Lv.{lvl} — {p['name']}**\n"
            f"> 🛒 -{p['shop_discount_percent']}% Shop • "
            f"🎁 +{p['daily_bonus_percent']}% Daily • "
            f"🏦 {cfg.fmt_money(p['loan_base'])} / {p['loan_interest']}% / {p['loan_days']}d\n"
            f"> {p['feature']}"
        )
    embed = discord.Embed(
        title="🪜 خارطة طريق Level Roles (5 → 100)",
        description="\n\n".join(lines)[:4000],
        color=discord.Color.gold()
    )
    embed.set_footer(
        text=f"{SERVER_NAME} | عندك غير أعلى Level Role — القديمة كتتحيد أوتوماتيكياً"
    )
    return embed




def build_leaderboard_embed(guild: discord.Guild) -> Optional[discord.Embed]:
    """
    أفضل 10 من الأعضاء الحاليين فقط.

    XP ديال العضو اللي خرج كتبقى محفوظة فـ levels_db:
    - وهو خارج: ما كيبانش فالLeaderboard.
    - إلا رجع: كيرجع أوتوماتيكياً للمركز اللي كتستحق XP ديالو.
    """
    ranking = get_current_member_xp_ranking(guild)[:10]
    if not ranking:
        return None

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, (user_id, data) in enumerate(ranking):
        member = guild.get_member(int(user_id))
        if not member:
            # حماية إضافية ضد أي cache race نادر.
            continue

        prefix = medals[i] if i < len(medals) else f"#{i + 1}"
        badge = "👑 " if data["level"] >= 100 else ("🌟 " if data["level"] >= 70 else "")
        lines.append(
            f"{prefix} {badge}{member.mention} — "
            f"Level {data['level']} ({total_xp_earned(data)} XP)"
        )

    if not lines:
        return None

    embed = discord.Embed(
        title="🏆 لائحة الشرف (Leaderboard)",
        description="\n".join(lines),
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )
    embed.set_footer(
        text=f"{SERVER_NAME} | غير الأعضاء الحاليين • XP كتبقى محفوظة إلا خرجتي"
    )
    return embed




async def refresh_xp_leaderboard_now():
    """Refresh فوري للرسالة العامة ديال Leaderboard."""
    if not bot_settings['leveling_enabled'] or not LEADERBOARD_CHANNEL_ID:
        return
    channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
    if not channel:
        return

    guild = channel.guild
    embed = build_leaderboard_embed(guild)
    msg_id = leaderboard_message_ids.get(str(guild.id))

    # إذا ما بقا حتى عضو مؤهل، نبدلو نفس الرسالة بدل نخلي Top قديم.
    if not embed:
        embed = discord.Embed(
            title="🏆 لائحة الشرف (Leaderboard)",
            description="ماكاين حتى عضو حالي عندو XP مسجلة دابا.",
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"{SERVER_NAME} | Leveling System")

    if msg_id:
        try:
            msg = await channel.fetch_message(int(msg_id))
            await msg.edit(embed=embed)
            return
        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception as e:
            print(f"[LEADERBOARD] refresh فوري فشل: {e}")

    try:
        new_msg = await channel.send(embed=embed)
        leaderboard_message_ids[str(guild.id)] = new_msg.id
        save_leaderboard_message_ids()
    except Exception as e:
        print(f"[LEADERBOARD] refresh فوري — خطأ فالبعث: {e}")


@tasks.loop(minutes=LEADERBOARD_UPDATE_MINUTES)
async def update_leaderboard():
    """كتحدث رسالة لائحة الشرف أوتوماتيكياً فـ LEADERBOARD_CHANNEL_ID كل LEADERBOARD_UPDATE_MINUTES
    (كتبدل نفس الرسالة، ماكتبعثش وحدة جديدة كل مرة)."""
    await refresh_xp_leaderboard_now()


@update_leaderboard.before_loop
async def before_update_leaderboard():
    await bot.wait_until_ready()


@update_leaderboard.error
async def update_leaderboard_error(error):
    print(f"[LEADERBOARD] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not update_leaderboard.is_running():
        update_leaderboard.restart()


class LevelingCog(commands.Cog):
    """Discord command/event registration for this subsystem."""

    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance

    @commands.command(name="setuplevels", hidden=True)
    @owner_only()
    async def setuplevels_cmd(self, ctx):
        """كيصاوب/يعاود يصاوب رسالة شرح نظام الـ Leveling فـ LEVELS_INFO_CHANNEL_ID (Admin)"""
        if not LEVELS_INFO_CHANNEL_ID:
            await ctx.send("❌ حط `LEVELS_INFO_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
            return
        await setup_levels_info_message(ctx.guild)
        await ctx.send("✅ رسالة شرح نظام الـ Leveling تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)

    @commands.command(name="xppanel", hidden=True)
    @owner_only()
    async def xppanel_cmd(self, ctx):
        """لوحة تحكم تفاعلية باش تبدل شحال ديال XP كياخدو الأعضاء من الشات، الفويس، اللايفستريم، وصعوبة المستويات — Admin"""
        await ctx.send(embed=_xp_panel_embed(), view=XPPanelView())

    @commands.command(name="xpadjust", hidden=True)
    async def xpadjust_cmd(self, ctx, member: discord.Member, amount: int, *, reason: str = "بلا سبب محدد"):
        """زيد ولا نقص XP لعضو معين مباشرة، والمستوى كيتبدل أوتوماتيكياً حسب المجموع الجديد — Owner بوحدو"""
        if not (OWNER_ID and ctx.author.id == OWNER_ID):
            await ctx.send("❌ هاد الأمر خاص غير بـ Owner.", delete_after=8)
            return
        if amount == 0:
            await ctx.send("❌ عطيني رقم غير صفر (موجب باش تزيد، سالب باش تنقص).", delete_after=8)
            return
        if not ctx.guild:
            return
        if member.bot:
            await ctx.send("❌ ما تقدرش تبدل XP ديال بوت.", delete_after=8)
            return

        result = await adjust_user_xp(member, ctx.guild, amount)

        verb = "زدت" if amount > 0 else "نقصت"
        embed = discord.Embed(
            title="🛠️ تعديل XP يدوي",
            description=f"{verb} **{abs(amount)}** XP لـ {member.mention}",
            color=discord.Color.gold() if amount > 0 else discord.Color.orange()
        )
        level_change = "➡️" if result["old_level"] == result["new_level"] else ("⬆️" if result["new_level"] > result["old_level"] else "⬇️")
        embed.add_field(name="المستوى", value=f"{result['old_level']} {level_change} **{result['new_level']}**", inline=True)
        embed.add_field(name="XP الكلية", value=f"{result['old_total']} → **{result['new_total']}**", inline=True)
        if result["roles_added"]:
            embed.add_field(name="🎁 رول جديد", value=", ".join(result["roles_added"]), inline=False)
        if result["roles_removed"]:
            embed.add_field(name="🗑️ رولات تحيدو", value=", ".join(result["roles_removed"]), inline=False)
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.set_footer(text=f"من طرف {ctx.author.display_name}")
        await ctx.send(embed=embed)
        await _owner_private_dm(
            member,
            f"⭐ إدارة GGMW9 بدلات XP ديالك بشكل خاص: {amount:+,} XP • "
            f"Level {result['old_level']} → {result['new_level']}."
        )

    @commands.command(name="xpaudit", hidden=True)
    @owner_only()
    async def xpaudit_cmd(self, ctx, member: discord.Member):
        embed = build_xp_audit_embed(ctx.guild, member)
        if not embed:
            await ctx.send(f"❌ ماكاين حتى XP Audit مسجل لـ {member.mention}.")
            return
        await ctx.send(embed=embed)

    @commands.command(name="botpanel", hidden=True)
    @owner_only()
    async def botpanel_cmd(self, ctx):
        """لوحة تحكم شاملة فأغلب إعدادات البوت (Anti-Raid، التحذيرات، Auto-Info، مميزات عامة، وXP) — Owner"""
        await ctx.send(embed=_main_panel_embed(), view=MainPanelView())

    @commands.command(name="rank", hidden=True)
    async def rank_cmd(self, ctx, member: Optional[discord.Member] = None):
        """كيبين المستوى والـ XP ديال عضو (نتا ولا شخص آخر)"""
        if not bot_settings['leveling_enabled']:
            await ctx.send(
                "❌ نظام Leveling معطل دابا. شعلو من `/botpanel` (Admin).",
                delete_after=6
            )
            return
        member = member or ctx.author
        await ctx.send(embed=build_rank_embed(ctx.guild, member))

    @commands.command(name="setbio", hidden=True)
    async def setbio_cmd(self, ctx, *, text: str = ""):
        """بدل البيو الشخصي ديالك اللي كيبان فـ /rank — متاحة من Level 20 (Milestone perk)"""
        data = get_user_level_data(ctx.guild.id, ctx.author.id)
        if data["level"] < 20:
            await ctx.send("🔒 هاد الميزة كتفتح فـ **Level 20**. كمل شوية باقي ليك!", ephemeral=True, delete_after=8)
            return
        data["bio"] = text.strip()[:200]
        save_levels()
        if data["bio"]:
            await ctx.send(f"✅ تبدل البيو ديالك لـ: \"{data['bio']}\"", ephemeral=True)
        else:
            await ctx.send("✅ تمسح البيو ديالك.", ephemeral=True)

    @commands.command(name="createpoll", hidden=True)
    async def createpoll_cmd(self, ctx, question: str, *, options: str):
        """صاوب استفتاء بأزرار تفاعلية (بلا حاجة لـ Admin) — متاحة من Level 60 (Milestone perk)"""
        data = get_user_level_data(ctx.guild.id, ctx.author.id)
        if data["level"] < 60:
            await ctx.send("🔒 هاد الميزة كتفتح فـ **Level 60**. كمل شوية باقي ليك!", ephemeral=True, delete_after=8)
            return

        opts = [o.strip() for o in options.split("|") if o.strip()][:5]
        if len(opts) < 2:
            await ctx.send("❌ خاصك على الأقل خياريين مفصولين بـ `|` (مثال: `بيتزا | تاكوس`).", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🗳️ {question}",
            description="\n".join(f"**{o}** — 0 صوت" for o in opts),
            color=discord.Color.blurple(), timestamp=datetime.now()
        )
        embed.set_footer(text=f"صاوبها {ctx.author.display_name} | {SERVER_NAME}")
        await ctx.send(embed=embed, view=SimplePollView(opts))

    @commands.command(name="legendtitle", hidden=True)
    async def legendtitle_cmd(self, ctx, *, title: str):
        """بدل سمية الرول الشخصي الفريد ديالك — متاحة غير لمن وصل Level 100"""
        data = get_user_level_data(ctx.guild.id, ctx.author.id)
        if data["level"] < 100:
            await ctx.send("🔒 هاد الميزة كتفتح فـ **Level 100**، الحد الأقصى. باقي بزاف الطريق!", ephemeral=True, delete_after=8)
            return
        role = await get_or_create_legend_role(ctx.guild, ctx.author)
        if not role:
            await ctx.send("❌ ما قدرتش نلقى/نصاوب الرول ديالك (يمكن صلاحيات ناقصة عند البوت).", ephemeral=True)
            return
        new_name = f"👑 {title.strip()}"[:100]
        try:
            await role.edit(name=new_name, reason=f"/legendtitle — {ctx.author}")
            await ctx.send(f"✅ الرول ديالك دابا سميتو: **{new_name}**", ephemeral=True)
        except (discord.Forbidden, discord.HTTPException) as e:
            await ctx.send(f"❌ ما قدرتش نبدل السمية: {e}", ephemeral=True)

    @commands.command(name="levelroadmap", aliases=["milestones"], hidden=True)
    async def levelroadmap_cmd(self, ctx):
        """كيبين لائحة كاملة بكل Level Roles والمكافآت ديالهم."""
        await ctx.send(embed=build_levelroadmap_embed())

    @commands.command(name="leaderboard", aliases=["lb", "top"], hidden=True)
    async def leaderboard_cmd(self, ctx):
        """كيبين أفضل 10 أعضاء نشيطين فالسيرفر (الأكثر XP)"""
        if not bot_settings['leveling_enabled']:
            await ctx.send("❌ نظام Leveling معطل دابا. شعلو من `/botpanel` (Admin).", delete_after=6)
            return

        embed = build_leaderboard_embed(ctx.guild)
        if not embed:
            await ctx.send("ماكاين حتى عضو ربح XP دابا.")
            return
        await ctx.send(embed=embed)

    @commands.command(name="setlevel", hidden=True)
    @owner_only()
    async def setlevel_cmd(self, ctx, member: discord.Member, level: int):
        """كيحط عضو مباشرة فمستوى معين (Admin) — مفيد إلا بغيتي تصحح غلط ولا تعطي مستوى بداية.
        كيزبط الرول ديال المستوى أوتوماتيكيا: كيحيد الرول القديم (بحال Level 10)
        وكيعطي الرول الصحيح ديال المستوى الجديد (بحال Level 15) — رول واحد بوحدو فأي وقت."""
        data = get_user_level_data(ctx.guild.id, member.id)
        data["level"] = max(0, level)
        data["xp"] = 0
        save_levels()

        roles_added, roles_removed = await sync_level_roles(member, ctx.guild, data["level"])

        msg = f"✅ {member.mention} تحط فـ Level {data['level']}."
        if roles_added:
            msg += f"\n🎖️ رول جديد: {', '.join(roles_added)}"
        if roles_removed:
            msg += f"\n🗑️ تحيدو: {', '.join(roles_removed)}"
        await ctx.send(msg)
        await _owner_private_dm(
            member,
            f"🎚️ إدارة GGMW9 بدلات المستوى ديالك بشكل خاص: Level {data['level']}."
        )


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(LevelingCog(bot_instance))
