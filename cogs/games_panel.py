# -*- coding: utf-8 -*-
"""GGMW9 public hubs — one clean ARCADE, dedicated Shop, dedicated Leaderboards.

Public messages stay in Darija by default. Every member can save a personal
Darija / English / French preference. Public buttons open ONE private session
message and submenus edit that same message instead of stacking replies.
"""

from datetime import datetime

import discord
from discord.ext import commands

import games_config as cfg


# ═══════════════════════════════════════════════════════
# Shared panel helpers
# ═══════════════════════════════════════════════════════

def _lang(bot: commands.Bot, guild_id: int, user_id: int) -> str:
    bridge = getattr(bot, "gg", {}) or {}
    getter = bridge.get("get_panel_language")
    if getter:
        try:
            return getter(guild_id, user_id)
        except Exception:
            pass
    return "darija"


def _set_lang(bot: commands.Bot, guild_id: int, user_id: int, lang: str) -> str:
    bridge = getattr(bot, "gg", {}) or {}
    setter = bridge.get("set_panel_language")
    if setter:
        try:
            return setter(guild_id, user_id, lang)
        except Exception:
            pass
    return lang if lang in {"darija", "en", "fr"} else "darija"


async def _upsert(bot: commands.Bot, interaction: discord.Interaction, key: str, **kwargs):
    helper = (getattr(bot, "gg", {}) or {}).get("upsert_ephemeral_panel")
    if helper:
        return await helper(interaction, key, **kwargs)
    # Safe fallback for old ai_bot.py deployments.
    if not interaction.response.is_done():
        await interaction.response.send_message(ephemeral=True, **kwargs)
    else:
        await interaction.followup.send(ephemeral=True, **kwargs)


def _txt(lang: str, key: str) -> str:
    strings = {
        "darija": {
            "games": "🕹️ Mini Games",
            "trivia": "🧠 Trivia",
            "casino": "🎰 Casino",
            "economy": "💰 Economy",
            "leaders": "🏆 Leaderboards",
            "choose_game": "🕹️ اختار اللعبة اللي بغيتي:",
            "not_yours": "❌ هاد الجلسة ماشي ديالك.",
            "unavailable": "❌ هاد الخدمة ماشي متوفرة دابا.",
            "economy_title": "💰 Economy Quick Access",
            "economy_desc": "ARCADE غير **Quick Access**. البانلات الرسمية والكاملة باقين فـ #bank و #shop باش ما يكون حتى خلط.",
            "official": "القنوات الرسمية",
            "back": "رجع لـARCADE",
            "language_saved": "✅ اللغة ديالك ولات **الدارجة**. هاد الاختيار شخصي وما كيبدلش الواجهة على الناس الآخرين.",
            "trivia_desc": "Trivia جزء رسمي من ARCADE. دخل لقناة Trivia باش تلعب الجولات والأسئلة بلا ما نخربق Channel ديال ARCADE.",
            "leader_pick": "🏆 اختار Leaderboard:",
        },
        "en": {
            "games": "🕹️ Mini Games",
            "trivia": "🧠 Trivia",
            "casino": "🎰 Casino",
            "economy": "💰 Economy",
            "leaders": "🏆 Leaderboards",
            "choose_game": "🕹️ Choose a game:",
            "not_yours": "❌ This session belongs to another member.",
            "unavailable": "❌ This feature is unavailable right now.",
            "economy_title": "💰 Economy Quick Access",
            "economy_desc": "ARCADE is only the **quick-access hub**. The full official panels stay in #bank and #shop so members always know where the main economy lives.",
            "official": "Official channels",
            "back": "Back to ARCADE",
            "language_saved": "✅ Your language is now **English**. This is personal and does not change the public panel for other members.",
            "trivia_desc": "Trivia is an official ARCADE game. Use the dedicated Trivia channel for rounds and questions so ARCADE stays clean.",
            "leader_pick": "🏆 Choose a leaderboard:",
        },
        "fr": {
            "games": "🕹️ Mini-jeux",
            "trivia": "🧠 Trivia",
            "casino": "🎰 Casino",
            "economy": "💰 Économie",
            "leaders": "🏆 Classements",
            "choose_game": "🕹️ Choisis un jeu :",
            "not_yours": "❌ Cette session appartient à un autre membre.",
            "unavailable": "❌ Cette fonction est indisponible pour le moment.",
            "economy_title": "💰 Accès rapide à l'économie",
            "economy_desc": "ARCADE sert d'**accès rapide**. Les panneaux officiels complets restent dans #bank et #shop pour éviter toute confusion.",
            "official": "Salons officiels",
            "back": "Retour à ARCADE",
            "language_saved": "✅ Ta langue est maintenant **Français**. Ce choix est personnel et ne change pas le panneau public des autres membres.",
            "trivia_desc": "Trivia fait partie d'ARCADE. Utilise le salon Trivia dédié pour les manches et questions afin de garder ARCADE propre.",
            "leader_pick": "🏆 Choisis un classement :",
        },
    }
    return strings.get(lang, strings["darija"]).get(key, strings["darija"].get(key, key))


def _channel_mention(channel_id: int, fallback: str) -> str:
    return f"<#{int(channel_id)}>" if int(channel_id or 0) else fallback


# ═══════════════════════════════════════════════════════
# ARCADE public hub
# ═══════════════════════════════════════════════════════

class ArcadeLanguageSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, *, custom_id: str = "ggmw9:arcade:language", row: int = 1):
        self.bot = bot
        super().__init__(
            placeholder="🌐 اللغة / Language / Langue",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", description="Default / اللغة الأساسية"),
                discord.SelectOption(label="English", value="en", emoji="🇬🇧"),
                discord.SelectOption(label="Français", value="fr", emoji="🇫🇷"),
            ],
            custom_id=custom_id,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        lang = _set_lang(self.bot, interaction.guild.id, interaction.user.id, self.values[0])
        await _upsert(
            self.bot,
            interaction,
            "arcade",
            content=_txt(lang, "language_saved"),
            embed=build_arcade_personal_embed(lang),
            view=ArcadePrivateHomeView(self.bot, interaction.user, lang),
        )


class GamesPanelView(discord.ui.View):
    """Persistent public ARCADE. Five clear destinations + personal language."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(ArcadeLanguageSelect(bot, row=1))

    @discord.ui.button(label="🕹️ Mini Games", style=discord.ButtonStyle.success, custom_id="ggmw9:arcade:games", row=0)
    async def open_games(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = _lang(self.bot, interaction.guild.id, interaction.user.id)
        await _upsert(
            self.bot, interaction, "arcade",
            content=_txt(lang, "choose_game"),
            embed=build_games_menu_embed(lang),
            view=GameMenuView(self.bot, interaction.user, lang),
        )

    @discord.ui.button(label="🧠 Trivia", style=discord.ButtonStyle.primary, custom_id="ggmw9:arcade:trivia", row=0)
    async def trivia_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = _lang(self.bot, interaction.guild.id, interaction.user.id)
        await _upsert(
            self.bot, interaction, "arcade",
            content=None,
            embed=build_trivia_embed(lang),
            view=TriviaQuickView(self.bot, interaction.user, lang),
        )

    @discord.ui.button(label="🎰 Casino", style=discord.ButtonStyle.danger, custom_id="ggmw9:arcade:casino", row=0)
    async def casino_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = _lang(self.bot, interaction.guild.id, interaction.user.id)
        try:
            from cogs.gambling_panel import GamblingMenuView, build_session_menu_embed
        except ImportError:
            from gambling_panel import GamblingMenuView, build_session_menu_embed
        await _upsert(
            self.bot, interaction, "arcade",
            content=None,
            embed=build_session_menu_embed(self.bot, interaction.guild, interaction.user, lang=lang),
            view=GamblingMenuView(self.bot, interaction.user, lang=lang),
        )

    @discord.ui.button(label="💰 Economy", style=discord.ButtonStyle.primary, custom_id="ggmw9:arcade:economy", row=0)
    async def economy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = _lang(self.bot, interaction.guild.id, interaction.user.id)
        await _upsert(
            self.bot, interaction, "arcade",
            content=None,
            embed=build_economy_quick_embed(lang),
            view=ArcadeEconomyView(self.bot, interaction.user, lang),
        )

    @discord.ui.button(label="🏆 Leaderboards", style=discord.ButtonStyle.secondary, custom_id="ggmw9:arcade:leaderboards", row=0)
    async def leaders_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = _lang(self.bot, interaction.guild.id, interaction.user.id)
        await _upsert(
            self.bot, interaction, "arcade",
            content=_txt(lang, "leader_pick"),
            embed=build_leaderboard_home_embed(lang),
            view=LeaderboardPanelView(self.bot, owner=interaction.user, lang=lang, session_key="arcade", persistent=False),
        )


def build_arcade_personal_embed(lang: str) -> discord.Embed:
    if lang == "en":
        desc = (
            "**ARCADE is the heart of GGMW9.** Games, Trivia, Casino and quick access to the economy live here.\n\n"
            "🕹️ Mini Games • 🧠 Trivia • 🎰 Casino • 💰 Economy • 🏆 Leaderboards\n"
            "🏦 The dedicated **Bank** and 🛒 **Shop** channels remain the official full panels."
        )
    elif lang == "fr":
        desc = (
            "**ARCADE est le cœur de GGMW9.** Jeux, Trivia, Casino et accès rapide à l'économie sont réunis ici.\n\n"
            "🕹️ Mini-jeux • 🧠 Trivia • 🎰 Casino • 💰 Économie • 🏆 Classements\n"
            "🏦 Les salons **Bank** et 🛒 **Shop** restent les panneaux officiels complets."
        )
    else:
        desc = (
            "**ARCADE هو القلب ديال GGMW9.** الألعاب، Trivia، Casino وQuick Access للاقتصاد مجموعين هنا.\n\n"
            "🕹️ Mini Games • 🧠 Trivia • 🎰 Casino • 💰 Economy • 🏆 Leaderboards\n"
            "🏦 **Bank** و🛒 **Shop** فـGGMW9 Economy باقين هما البانلات الرسمية والكاملة."
        )
    e = discord.Embed(title="🎮・ARCADE — GGMW9", description=desc, color=discord.Color.blurple())
    e.set_footer(text="🌐 Darija default • English • Français")
    return e


def build_games_menu_embed(lang: str) -> discord.Embed:
    if lang == "en":
        desc = "Pick a mini-game. Trivia is also available as a dedicated ARCADE destination."
    elif lang == "fr":
        desc = "Choisis un mini-jeu. Trivia est aussi disponible directement depuis ARCADE."
    else:
        desc = "اختار Mini Game. Trivia حتى هي موجودة مباشرة فـARCADE باش تكون باينة وواضحة."
    return discord.Embed(title=_txt(lang, "games"), description=desc, color=discord.Color.green())


def build_trivia_embed(lang: str) -> discord.Embed:
    ch = _channel_mention(getattr(cfg, "TRIVIA_CHANNEL_ID", 0), "#trivia")
    if lang == "en":
        title, desc = "🧠 Trivia", f"{_txt(lang,'trivia_desc')}\n\n📍 Trivia channel: {ch}\n🏆 Trivia also has its own leaderboard inside ARCADE."
    elif lang == "fr":
        title, desc = "🧠 Trivia", f"{_txt(lang,'trivia_desc')}\n\n📍 Salon Trivia : {ch}\n🏆 Le classement Trivia est aussi accessible depuis ARCADE."
    else:
        title, desc = "🧠 Trivia", f"{_txt(lang,'trivia_desc')}\n\n📍 قناة Trivia: {ch}\n🏆 Leaderboard ديال Trivia موجود حتى هو فـARCADE."
    return discord.Embed(title=title, description=desc, color=discord.Color.purple())


def build_economy_quick_embed(lang: str) -> discord.Embed:
    bank = _channel_mention(getattr(cfg, "ECONOMY_BANK_CHANNEL_ID", 0), "#bank")
    shop = _channel_mention(getattr(cfg, "SHOP_PANEL_CHANNEL_ID", 0), "#shop")
    e = discord.Embed(title=_txt(lang, "economy_title"), description=_txt(lang, "economy_desc"), color=discord.Color.gold())
    e.add_field(name=f"🏦 {_txt(lang,'official')}", value=f"Bank: {bank}\nShop: {shop}", inline=False)
    return e


class ArcadeEconomyView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.abc.User, lang: str):
        super().__init__(timeout=300)
        self.bot, self.user, self.lang = bot, user, lang
        labels = {
            "darija": ["🏦 البنك", "🛒 المتجر", "💳 حسابي", "📊 الاقتصاد", "↩️ ARCADE"],
            "en": ["🏦 Bank", "🛒 Shop", "💳 My Account", "📊 Economy", "↩️ ARCADE"],
            "fr": ["🏦 Banque", "🛒 Boutique", "💳 Mon compte", "📊 Économie", "↩️ ARCADE"],
        }[lang if lang in {"darija","en","fr"} else "darija"]
        for label, style, callback in [
            (labels[0], discord.ButtonStyle.success, self.bank),
            (labels[1], discord.ButtonStyle.primary, self.shop),
            (labels[2], discord.ButtonStyle.secondary, self.account),
            (labels[3], discord.ButtonStyle.secondary, self.stats),
            (labels[4], discord.ButtonStyle.secondary, self.back),
        ]:
            b = discord.ui.Button(label=label, style=style)
            b.callback = callback
            self.add_item(b)

    async def _owner(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_txt(self.lang, "not_yours"), ephemeral=True)
            return False
        return True

    async def bank(self, interaction):
        if not await self._owner(interaction): return
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.edit_message(content=_txt(self.lang,"unavailable"), embed=None, view=self); return
        try:
            from cogs.economy import BankSessionView
        except ImportError:
            from economy import BankSessionView
        await interaction.response.edit_message(
            content=None,
            embed=eco.build_user_account_embed(interaction.guild, interaction.user, lang=self.lang),
            view=BankSessionView(eco, interaction.user, self.lang, session_key="arcade"),
        )

    async def shop(self, interaction):
        if not await self._owner(interaction): return
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.edit_message(content=_txt(self.lang,"unavailable"), embed=None, view=self); return
        try:
            from cogs.economy import ShopView, build_shop_home_embed
        except ImportError:
            from economy import ShopView, build_shop_home_embed
        await interaction.response.edit_message(
            content=None,
            embed=build_shop_home_embed(eco, interaction.guild, interaction.user, lang=self.lang),
            view=ShopView(eco, interaction.user, lang=self.lang, session_key="arcade"),
        )

    async def account(self, interaction):
        if not await self._owner(interaction): return
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.edit_message(content=_txt(self.lang,"unavailable"), embed=None, view=self); return
        await interaction.response.edit_message(content=None, embed=eco.build_user_account_embed(interaction.guild, interaction.user, lang=self.lang), view=self)

    async def stats(self, interaction):
        if not await self._owner(interaction): return
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.edit_message(content=_txt(self.lang,"unavailable"), embed=None, view=self); return
        await interaction.response.edit_message(content=None, embed=eco.build_global_economy_embed(interaction.guild, lang=self.lang), view=self)

    async def back(self, interaction):
        if not await self._owner(interaction): return
        await interaction.response.edit_message(content=None, embed=build_arcade_personal_embed(self.lang), view=ArcadePrivateHomeView(self.bot, self.user, self.lang))


class ArcadePrivateHomeView(discord.ui.View):
    """Localized private ARCADE navigation. All clicks edit one private message."""
    def __init__(self, bot: commands.Bot, user: discord.abc.User, lang: str):
        super().__init__(timeout=300)
        self.bot, self.user, self.lang = bot, user, lang
        items = [
            (_txt(lang,"games"), discord.ButtonStyle.success, self.games),
            (_txt(lang,"trivia"), discord.ButtonStyle.primary, self.trivia),
            (_txt(lang,"casino"), discord.ButtonStyle.danger, self.casino),
            (_txt(lang,"economy"), discord.ButtonStyle.primary, self.economy),
            (_txt(lang,"leaders"), discord.ButtonStyle.secondary, self.leaders),
        ]
        for label, style, cb in items:
            b=discord.ui.Button(label=label,style=style); b.callback=cb; self.add_item(b)

    async def _ok(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_txt(self.lang,"not_yours"),ephemeral=True); return False
        return True

    async def games(self, interaction):
        if not await self._ok(interaction): return
        await interaction.response.edit_message(content=_txt(self.lang,"choose_game"),embed=build_games_menu_embed(self.lang),view=GameMenuView(self.bot,self.user,self.lang))
    async def trivia(self, interaction):
        if not await self._ok(interaction): return
        await interaction.response.edit_message(content=None,embed=build_trivia_embed(self.lang),view=TriviaQuickView(self.bot,self.user,self.lang))
    async def casino(self, interaction):
        if not await self._ok(interaction): return
        try:
            from cogs.gambling_panel import GamblingMenuView, build_session_menu_embed
        except ImportError:
            from gambling_panel import GamblingMenuView, build_session_menu_embed
        await interaction.response.edit_message(content=None,embed=build_session_menu_embed(self.bot,interaction.guild,interaction.user,lang=self.lang),view=GamblingMenuView(self.bot,self.user,lang=self.lang))
    async def economy(self, interaction):
        if not await self._ok(interaction): return
        await interaction.response.edit_message(content=None,embed=build_economy_quick_embed(self.lang),view=ArcadeEconomyView(self.bot,self.user,self.lang))
    async def leaders(self, interaction):
        if not await self._ok(interaction): return
        await interaction.response.edit_message(content=_txt(self.lang,"leader_pick"),embed=build_leaderboard_home_embed(self.lang),view=LeaderboardPanelView(self.bot,owner=self.user,lang=self.lang,session_key="arcade",persistent=False))


class TriviaQuickView(discord.ui.View):
    def __init__(self, bot, user, lang):
        super().__init__(timeout=300); self.bot=bot; self.user=user; self.lang=lang
        if getattr(cfg, "TRIVIA_CHANNEL_ID", 0):
            url = f"https://discord.com/channels/{user.guild.id}/{int(cfg.TRIVIA_CHANNEL_ID)}" if isinstance(user, discord.Member) else None
            if url:
                self.add_item(discord.ui.Button(label="🧠 Open Trivia Channel", style=discord.ButtonStyle.link, url=url))
        b=discord.ui.Button(label="↩️ ARCADE",style=discord.ButtonStyle.secondary); b.callback=self.back; self.add_item(b)

    async def back(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_txt(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.edit_message(content=None,embed=build_arcade_personal_embed(self.lang),view=ArcadePrivateHomeView(self.bot,self.user,self.lang))


# ═══════════════════════════════════════════════════════
# Mini-games
# ═══════════════════════════════════════════════════════

GAMES = [
    {"id":"hangman","emoji":"🪢","darija":"المشنوق","en":"Hangman","fr":"Pendu","desc_d":"خمّن الكلمة حرف بحرف — 6 محاولات","desc_e":"Guess the word letter by letter — 6 tries","desc_f":"Devine le mot lettre par lettre — 6 essais"},
    {"id":"wordle","emoji":"🔤","darija":"Wordle اليومي","en":"Daily Wordle","fr":"Wordle quotidien","desc_d":"كلمة وحدة كل نهار — 6 محاولات","desc_e":"One daily word — 6 tries","desc_f":"Un mot par jour — 6 essais"},
    {"id":"reaction","emoji":"⚡","darija":"أسرع ضغطة","en":"Reaction","fr":"Réaction","desc_d":"أول واحد كيضغط كيربح","desc_e":"First click wins","desc_f":"Le premier clic gagne"},
    {"id":"xo","emoji":"⭕","darija":"X/O","en":"Tic-Tac-Toe","fr":"Morpion","desc_d":"تحدّى عضو","desc_e":"Challenge another member","desc_f":"Défie un membre"},
    {"id":"counting","emoji":"🔢","darija":"العدّاد","en":"Counting","fr":"Comptage","desc_d":"عدّو جماعة فـ #counting","desc_e":"Count together in #counting","desc_f":"Comptez ensemble dans #counting"},
    {"id":"trivia","emoji":"🧠","darija":"Trivia","en":"Trivia","fr":"Trivia","desc_d":"أسئلة ومعرفة عامة فـقناة Trivia","desc_e":"Knowledge rounds in the Trivia channel","desc_f":"Questions de culture générale dans le salon Trivia"},
]


class GameMenuView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.abc.User, lang: str = "darija"):
        super().__init__(timeout=300)
        self.bot, self.user, self.lang = bot, user, lang
        lk={"darija":"darija","en":"en","fr":"fr"}.get(lang,"darija")
        dk={"darija":"desc_d","en":"desc_e","fr":"desc_f"}.get(lang,"desc_d")
        opts=[discord.SelectOption(label=g[lk],value=g["id"],emoji=g["emoji"],description=g[dk][:100]) for g in GAMES]
        sel=discord.ui.Select(placeholder=_txt(lang,"choose_game")[:150],options=opts,min_values=1,max_values=1)
        sel.callback=self.on_pick; self.select=sel; self.add_item(sel)
        b=discord.ui.Button(label="↩️ ARCADE",style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)

    async def back(self, interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_txt(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.edit_message(content=None,embed=build_arcade_personal_embed(self.lang),view=ArcadePrivateHomeView(self.bot,self.user,self.lang))

    async def on_pick(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_txt(self.lang,"not_yours"), ephemeral=True); return
        choice=self.select.values[0]
        if choice=="trivia":
            await interaction.response.edit_message(content=None,embed=build_trivia_embed(self.lang),view=TriviaQuickView(self.bot,self.user,self.lang)); return
        if choice=="hangman":
            cog=self.bot.get_cog("Hangman")
            if not cog or not cog.bank:
                await interaction.response.edit_message(content=_txt(self.lang,"unavailable"),embed=None,view=self); return
            try: from cogs.game_hangman import CategoryView
            except ImportError: from game_hangman import CategoryView
            key=(interaction.guild.id,interaction.user.id)
            if key in cog.active:
                await interaction.response.edit_message(content=("❌ You already have an active session." if self.lang=="en" else "❌ عندك جلسة خدّامة ديجا."),embed=None,view=self); return
            prompt="📚 Choose a category:" if self.lang=="en" else "📚 Choisis une catégorie :" if self.lang=="fr" else "📚 اختار الفئة اللي بغيتي:"
            await interaction.response.edit_message(content=prompt,embed=None,view=CategoryView(cog,interaction.user)); return
        if choice=="wordle":
            cog=self.bot.get_cog("Wordle")
            if not cog or not cog.words:
                await interaction.response.edit_message(content=_txt(self.lang,"unavailable"),embed=None,view=self); return
            try: from cogs.game_wordle import normalize
            except ImportError: from game_wordle import normalize
            p=cog.player(interaction.guild.id,interaction.user.id); answer=normalize(cog.word_of_the_day())
            prompt="Type `/wordle <word>` to guess 👇" if self.lang=="en" else "Écris `/wordle <mot>` pour essayer 👇" if self.lang=="fr" else "اكتب `/wordle <كلمة>` باش تخمّن 👇"
            await interaction.response.edit_message(content=prompt,embed=cog.build_embed(p,answer,interaction.user),view=None); return
        if choice=="reaction":
            msg="⚡ Use `/reaction` in chat to start a group round." if self.lang=="en" else "⚡ Utilise `/reaction` dans le chat pour lancer une manche." if self.lang=="fr" else "⚡ دير `/reaction` فـ الشات باش تبدا جولة جماعية."
        elif choice=="xo":
            msg="⭕ Use `/xo @member` to challenge someone." if self.lang=="en" else "⭕ Utilise `/xo @membre` pour lancer un défi." if self.lang=="fr" else "⭕ دير `/xo @العضو` باش تتحدّاه."
        else:
            ch=_channel_mention(getattr(cfg,"COUNTING_CHANNEL_ID",0),"#counting")
            msg=f"🔢 Go to {ch} and keep the count going." if self.lang=="en" else f"🔢 Va dans {ch} et continue le comptage." if self.lang=="fr" else f"🔢 سير لـ {ch} وكمل العدّاد."
        await interaction.response.edit_message(content=msg,embed=None,view=self)


# ═══════════════════════════════════════════════════════
# Dedicated Shop public panel
# ═══════════════════════════════════════════════════════

class ShopLanguageSelect(discord.ui.Select):
    def __init__(self, bot):
        self.bot=bot
        super().__init__(placeholder="🌐 اللغة / Language / Langue",options=[
            discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦"),
            discord.SelectOption(label="English",value="en",emoji="🇬🇧"),
            discord.SelectOption(label="Français",value="fr",emoji="🇫🇷"),
        ],custom_id="ggmw9:shop_panel:language",row=1)
    async def callback(self,interaction):
        lang=_set_lang(self.bot,interaction.guild.id,interaction.user.id,self.values[0]); eco=self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message(_txt(lang,"unavailable"),ephemeral=True); return
        try: from cogs.economy import ShopView, build_shop_home_embed
        except ImportError: from economy import ShopView, build_shop_home_embed
        await _upsert(self.bot,interaction,"shop",content=None,embed=build_shop_home_embed(eco,interaction.guild,interaction.user,lang=lang),view=ShopView(eco,interaction.user,lang=lang,session_key="shop"))


class ShopPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None); self.bot=bot; self.add_item(ShopLanguageSelect(bot))

    @discord.ui.button(label="🛒 فتح Marketplace",style=discord.ButtonStyle.success,custom_id="ggmw9:shop_panel:open",row=0)
    async def open_shop(self,interaction,button):
        eco=self.bot.get_cog("Economy"); lang=_lang(self.bot,interaction.guild.id,interaction.user.id)
        if not eco:
            await interaction.response.send_message(_txt(lang,"unavailable"),ephemeral=True); return
        try: from cogs.economy import ShopView, build_shop_home_embed
        except ImportError: from economy import ShopView, build_shop_home_embed
        await _upsert(self.bot,interaction,"shop",content=None,embed=build_shop_home_embed(eco,interaction.guild,interaction.user,lang=lang),view=ShopView(eco,interaction.user,lang=lang,session_key="shop"))


# ═══════════════════════════════════════════════════════
# Leaderboards
# ═══════════════════════════════════════════════════════

LEADERBOARDS=[
    {"id":"richest","emoji":"💰","label":"Richest","cog":"Economy","method":"build_richest_embed"},
    {"id":"wordle","emoji":"🔤","label":"Wordle","cog":"Wordle","method":"build_top_embed"},
    {"id":"reaction","emoji":"⚡","label":"Reaction","cog":"ReactionSpeed","method":"build_top_embed"},
    {"id":"xo","emoji":"⭕","label":"X/O","cog":"TicTacToe","method":"build_top_embed"},
    {"id":"hangman","emoji":"🪢","label":"Hangman","cog":"Hangman","method":"build_top_embed"},
    {"id":"trivia","emoji":"🧠","label":"Trivia","cog":"Trivia","method":"build_top_embed"},
    {"id":"dice","emoji":"🎲","label":"Dice","cog":"Dice","method":"build_top_embed"},
    {"id":"coinflip","emoji":"🪙","label":"Coinflip","cog":"Coinflip","method":"build_top_embed"},
    {"id":"slots","emoji":"🎰","label":"Slots","cog":"Slots","method":"build_top_embed"},
    {"id":"scratch","emoji":"🎫","label":"Scratch","cog":"Scratch","method":"build_top_embed"},
    {"id":"lottery","emoji":"🎟️","label":"Lottery","cog":"Lottery","method":"build_top_embed"},
    {"id":"counting","emoji":"🔢","label":"Counting","cog":"Counting","method":"build_status_embed"},
]


def build_leaderboard_home_embed(lang="darija"):
    desc="اختار اللعبة؛ النتيجة كتبان فـنفس الرسالة الخاصة." if lang=="darija" else "Choose a board; the result replaces this same private message." if lang=="en" else "Choisis un classement ; le résultat remplace ce même message privé."
    return discord.Embed(title="🏆 Leaderboards",description=desc,color=discord.Color.gold())


class LeaderboardSelect(discord.ui.Select):
    def __init__(self,bot,owner=None,lang="darija",session_key="leaderboards",persistent=True):
        self.bot,self.owner,self.lang,self.session_key=bot,owner,lang,session_key
        super().__init__(placeholder=_txt(lang,"leader_pick")[:150],options=[discord.SelectOption(label=x["label"],value=x["id"],emoji=x["emoji"]) for x in LEADERBOARDS],custom_id=("ggmw9:leaderboard_panel:select" if persistent else None),row=0)
    async def callback(self,interaction):
        if self.owner and interaction.user.id!=self.owner.id:
            await interaction.response.send_message(_txt(self.lang,"not_yours"),ephemeral=True); return
        choice=self.values[0]; lb=next((x for x in LEADERBOARDS if x["id"]==choice),None)
        cog=self.bot.get_cog(lb["cog"]) if lb else None
        if not lb or not cog or not hasattr(cog,lb["method"]):
            if self.owner:
                await interaction.response.edit_message(content=_txt(self.lang,"unavailable"),embed=None,view=LeaderboardPanelView(self.bot,owner=self.owner,lang=self.lang,session_key=self.session_key,persistent=False))
            else:
                await _upsert(self.bot,interaction,self.session_key,content=_txt(self.lang,"unavailable"),embed=None,view=None)
            return
        embed=getattr(cog,lb["method"])(interaction.guild)
        if self.owner:
            await interaction.response.edit_message(content=None,embed=embed,view=LeaderboardPanelView(self.bot,owner=self.owner,lang=self.lang,session_key=self.session_key,persistent=False))
        else:
            lang=_lang(self.bot,interaction.guild.id,interaction.user.id)
            await _upsert(self.bot,interaction,self.session_key,content=None,embed=embed,view=LeaderboardPanelView(self.bot,owner=interaction.user,lang=lang,session_key=self.session_key,persistent=False))


class LeaderboardLanguageSelect(discord.ui.Select):
    def __init__(self,bot):
        self.bot=bot
        super().__init__(placeholder="🌐 اللغة / Language / Langue",options=[
            discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦"),
            discord.SelectOption(label="English",value="en",emoji="🇬🇧"),
            discord.SelectOption(label="Français",value="fr",emoji="🇫🇷"),
        ],custom_id="ggmw9:leaderboards:language",row=1)
    async def callback(self,interaction):
        lang=_set_lang(self.bot,interaction.guild.id,interaction.user.id,self.values[0])
        await _upsert(self.bot,interaction,"leaderboards",content=_txt(lang,"leader_pick"),embed=build_leaderboard_home_embed(lang),view=LeaderboardPanelView(self.bot,owner=interaction.user,lang=lang,session_key="leaderboards",persistent=False))


class LeaderboardPanelView(discord.ui.View):
    def __init__(self,bot,owner=None,lang="darija",session_key="leaderboards",persistent=True):
        super().__init__(timeout=None if persistent else 300); self.bot=bot
        self.add_item(LeaderboardSelect(bot,owner=owner,lang=lang,session_key=session_key,persistent=persistent))
        if persistent:
            self.add_item(LeaderboardLanguageSelect(bot))


# ═══════════════════════════════════════════════════════
# Cog + single-message public panel maintenance
# ═══════════════════════════════════════════════════════

class GamesPanel(commands.Cog):
    def __init__(self,bot): self.bot=bot

    async def cog_load(self):
        self.bot.add_view(GamesPanelView(self.bot))
        self.bot.add_view(ShopPanelView(self.bot))
        self.bot.add_view(LeaderboardPanelView(self.bot,persistent=True))
        print("✅ [ARCADE] Persistent hub + Shop + Leaderboards registered.")

    async def _ensure_single(self,channel,match,embed,view):
        matches=[]
        try:
            async for msg in channel.history(limit=60):
                if msg.author!=self.bot.user or not msg.embeds: continue
                title=msg.embeds[0].title or ""
                if match(title): matches.append(msg)
            if matches:
                keep=matches[0]
                await keep.edit(embed=embed,view=view)
                for extra in matches[1:]:
                    try: await extra.delete()
                    except (discord.Forbidden,discord.HTTPException): pass
            else:
                await channel.send(embed=embed,view=view)
        except (discord.Forbidden,discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        if cfg.GAMES_PANEL_CHANNEL_ID and (ch:=self.bot.get_channel(cfg.GAMES_PANEL_CHANNEL_ID)):
            await self._ensure_single(ch,lambda t:("ARCADE" in t or "Mini Games" in t),self._build_arcade_embed(),GamesPanelView(self.bot))
        if getattr(cfg,"SHOP_PANEL_CHANNEL_ID",0) and (ch:=self.bot.get_channel(cfg.SHOP_PANEL_CHANNEL_ID)):
            await self._ensure_single(ch,lambda t:("Marketplace" in t or "المتجر" in t),self._build_shop_panel_embed(),ShopPanelView(self.bot))
        if getattr(cfg,"GAMES_LEADERBOARD_CHANNEL_ID",0) and (ch:=self.bot.get_channel(cfg.GAMES_LEADERBOARD_CHANNEL_ID)):
            await self._ensure_single(ch,lambda t:"Leaderboards" in t,self._build_leaderboard_embed(),LeaderboardPanelView(self.bot,persistent=True))

    def _build_arcade_embed(self):
        bank=_channel_mention(getattr(cfg,"ECONOMY_BANK_CHANNEL_ID",0),"#bank"); shop=_channel_mention(getattr(cfg,"SHOP_PANEL_CHANNEL_ID",0),"#shop"); trivia=_channel_mention(getattr(cfg,"TRIVIA_CHANNEL_ID",0),"#trivia")
        e=discord.Embed(
            title="🎮・ARCADE — GGMW9",
            description=(
                "**هاد هي البوابة الرئيسية للترفيه والاقتصاد.** كل عضو كيدخل لجلسة خاصة وحدة، وكل اختيار جديد كيدير **Edit لنفس الرسالة** بلا Spam.\n\n"
                "🕹️ **Mini Games** — Hangman • Wordle • Reaction • X/O • Counting\n"
                f"🧠 **Trivia** — {trivia}\n"
                "🎰 **Casino** — ألعاب الرهان والـFairness/Profile\n"
                "💰 **Economy** — Quick Access للحساب والبنك والمتجر\n"
                "🏆 **Leaderboards** — كاع الترتيبات من بلاصة وحدة"
            ),color=discord.Color.blurple(),timestamp=datetime.now())
        e.add_field(name="🏦 باش ما يكونش خلط",value=f"ARCADE = **Hub/Shortcuts** فقط.\nالبنك الرسمي: {bank}\nالمتجر الرسمي: {shop}",inline=False)
        e.add_field(name="🌐 Languages",value="🇲🇦 **Darija (Default)** • 🇬🇧 English • 🇫🇷 Français\nاللغة كتتحفظ لكل عضو بوحدو.",inline=False)
        e.set_footer(text="GGMW9 ARCADE • one hub • one private session • no panel spam")
        return e

    def _build_shop_panel_embed(self):
        e=discord.Embed(title="🛒 GGMW9 Marketplace",description="هاد Channel هي **الواجهة الرسمية والكاملة للمتجر**. ARCADE غير Shortcut سريع ليها.\n\n🌐 Darija Default • English • Français",color=discord.Color.blurple(),timestamp=datetime.now())
        e.set_footer(text="Open Marketplace → نفس الجلسة الخاصة كتتبدل بلا Spam")
        return e

    def _build_leaderboard_embed(self):
        e=discord.Embed(title="🏆 Leaderboards",description="اختار أي لعبة؛ النتيجة كتبان فـ**رسالة خاصة وحدة** وكتتبدل مع كل اختيار.\n\n🧠 Trivia داخلة حتى هي هنا.\n🌐 Darija Default • English • Français",color=discord.Color.gold(),timestamp=datetime.now())
        return e


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesPanel(bot))
