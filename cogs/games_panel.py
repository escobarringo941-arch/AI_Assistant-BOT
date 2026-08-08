# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║ cogs/games_panel.py — 🎮 Panel موحّد ديال الألعاب ║
═══════════════════════════════════════════════════════

3 بانلات دائمين، كل واحد فـ channel ديالو:
1. #games-panel — قائمة وحدة فيها كاع الألعاب (اختيار + رصيد)
2. #shop — المتجر
3. #games-leaderboard — لوحة موحّدة فيها لوائح كاع الألعاب

⚠️ نقطة تقنية حرجة — Persistent Views:
الأزرار العادية كيموتو بعد restart ديال البوت (timeout).
باش يبقاو خدّامين للأبد خاص:
• timeout=None
• custom_id ثابت لكل زر
• bot.add_view(...) فـ cog_load()
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

import games_config as cfg

# ═══════════════════════════════════════════════════════
# ║ Panel دائم (Persistent View) — البانل العام ديال الألعاب ║
# ═══════════════════════════════════════════════════════

class GamesPanelView(discord.ui.View):
    """🎮 ARCADE هو الـhub المركزي: mini-games + casino + shop + wallet + tops."""
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🕹️ Mini Games", style=discord.ButtonStyle.success, custom_id="ggmw9:games_panel:open", row=0)
    async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🕹️ اختار Mini Game:", view=GameMenuView(self.bot, interaction.user), ephemeral=True)

    @discord.ui.button(label="🎰 Casino", style=discord.ButtonStyle.danger, custom_id="ggmw9:arcade:casino", row=0)
    async def casino_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        from cogs.gambling_panel import GamblingMenuView, build_session_menu_embed
        await interaction.response.send_message(
            embed=build_session_menu_embed(self.bot, interaction.guild, interaction.user),
            view=GamblingMenuView(self.bot, interaction.user),
            ephemeral=True,
        )

    @discord.ui.button(label="🛒 Shop", style=discord.ButtonStyle.primary, custom_id="ggmw9:arcade:shop", row=0)
    async def shop_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message("❌ Economy/Shop ماشي محمّلة.", ephemeral=True)
            return
        from cogs.economy import ShopView, build_shop_home_embed
        await interaction.response.send_message(
            embed=build_shop_home_embed(eco, interaction.guild, interaction.user),
            view=ShopView(eco, interaction.user),
            ephemeral=True,
        )

    @discord.ui.button(label="🏦 Bank", style=discord.ButtonStyle.primary, custom_id="ggmw9:arcade:bank", row=1)
    async def bank_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message("❌ Bank/Economy ماشي محمّلة.", ephemeral=True)
            return
        from cogs.economy import EconomyBankPanelView
        await interaction.response.send_message(
            embed=eco.build_bank_panel_embed(interaction.guild),
            view=EconomyBankPanelView(eco),
            ephemeral=True,
        )

    @discord.ui.button(label="💵 Wallet", style=discord.ButtonStyle.secondary, custom_id="ggmw9:games_panel:balance", row=1)
    async def balance_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message("❌ Economy ماشي محمّلة.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=eco.build_user_account_embed(interaction.guild, interaction.user), ephemeral=True
        )

    @discord.ui.button(label="🏆 Leaderboards", style=discord.ButtonStyle.secondary, custom_id="ggmw9:games_panel:tops", row=1)
    async def tops_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🏆 اختار Leaderboard:", view=LeaderboardPanelView(self.bot), ephemeral=True
        )

# ═══════════════════════════════════════════════════════
# ║ قائمة الألعاب (منسدلة Ephemeral) ║
# ═══════════════════════════════════════════════════════

GAMES = [
    {
        "id": "hangman",
        "emoji": "🪢",
        "label": "المشنوق",
        "desc": "خمّن الكلمة حرف بحرف — 6 محاولات",
    },
    {
        "id": "wordle",
        "emoji": "🔤",
        "label": "Wordle اليومي",
        "desc": "كلمة وحدة كل نهار — 6 محاولات",
    },
    {
        "id": "reaction",
        "emoji": "⚡",
        "label": "أسرع ضغطة",
        "desc": "أول واحد كيضغط الزر كيربح",
    },
    {
        "id": "xo",
        "emoji": "⭕",
        "label": "X/O",
        "desc": "تحدّى عضو — استعمل /xo @عضو",
    },
    {
        "id": "counting",
        "emoji": "🔢",
        "label": "العدّاد",
        "desc": "عدّو جماعة فـ #counting",
    },
]


class GameMenuView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.abc.User):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user

        options = [
            discord.SelectOption(
                label=g["label"],
                value=g["id"],
                emoji=g["emoji"],
                description=g["desc"][:100],
            )
            for g in GAMES
        ]

        select = discord.ui.Select(placeholder="🎮 اختار...", options=options)
        select.callback = self.on_pick
        self.add_item(select)
        self.select = select

    async def on_pick(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return

        choice = self.select.values[0]

        # ═══ المشنوق ═══
        if choice == "hangman":
            cog = self.bot.get_cog("Hangman")
            if not cog or not cog.bank:
                await interaction.response.send_message("❌ المشنوق ماشي متوفر.", ephemeral=True)
                return

            from cogs.game_hangman import CategoryView

            key = (interaction.guild.id, interaction.user.id)
            if key in cog.active:
                await interaction.response.send_message(
                    "❌ عندك جلسة خدّامة ديجا.", ephemeral=True
                )
                return

            await interaction.response.edit_message(
                content="📚 اختار الفئة اللي بغيتي:",
                view=CategoryView(cog, interaction.user),
            )
            return

        # ═══ Wordle ═══
        if choice == "wordle":
            cog = self.bot.get_cog("Wordle")
            if not cog or not cog.words:
                await interaction.response.send_message(
                    "❌ Wordle ماشي متوفر.", ephemeral=True
                )
                return

            from cogs.game_wordle import normalize

            p = cog.player(interaction.guild.id, interaction.user.id)
            answer = normalize(cog.word_of_the_day())
            await interaction.response.edit_message(
                content="اكتب `/wordle <كلمة>` باش تخمّن 👇",
                embed=cog.build_embed(p, answer, interaction.user),
                view=None,
            )
            return

        # ═══ أسرع ضغطة ═══
        if choice == "reaction":
            await interaction.response.edit_message(
                content="⚡ دير `/reaction` فـ الشات باش تبدا جولة جماعية.",
                view=None,
            )
            return

        # ═══ X/O ═══
        if choice == "xo":
            await interaction.response.edit_message(
                content="⭕ دير `/xo @العضو` باش تتحدّاه.", view=None
            )
            return

        # ═══ العدّاد ═══
        if choice == "counting":
            ch = (
                f"<#{cfg.COUNTING_CHANNEL_ID}>"
                if cfg.COUNTING_CHANNEL_ID
                else "#counting"
            )
            await interaction.response.edit_message(
                content=(
                    f"🔢 سير لـ {ch} وعدّ! "
                    "دير `/counting` باش تشوف فين وصلنا والريكورد."
                ),
                view=None,
            )
            return

# ═══════════════════════════════════════════════════════
# ║ بانل المتجر في شانيل خاصة (SHOP_PANEL_CHANNEL_ID) ║
# ═══════════════════════════════════════════════════════

class ShopPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🛒 فتح Marketplace", style=discord.ButtonStyle.success, custom_id="ggmw9:shop_panel:open")
    async def open_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message("❌ Marketplace ماشي محمّلة.", ephemeral=True)
            return
        from cogs.economy import ShopView, build_shop_home_embed
        await interaction.response.send_message(
            embed=build_shop_home_embed(eco, interaction.guild, interaction.user),
            view=ShopView(eco, interaction.user),
            ephemeral=True,
        )


# ═══════════════════════════════════════════════════════
# ║ بانل الـ Leaderboards موحّد (GAMES_LEADERBOARD_CHANNEL_ID) ║
# ═══════════════════════════════════════════════════════

LEADERBOARDS = [
    {"id": "richest", "emoji": "💰", "label": "أغنى الأعضاء", "cog": "Economy", "method": "build_richest_embed"},
    {"id": "wordle", "emoji": "🔤", "label": "Wordle", "cog": "Wordle", "method": "build_top_embed"},
    {"id": "reaction", "emoji": "⚡", "label": "أسرع ضغطة", "cog": "ReactionSpeed", "method": "build_top_embed"},
    {"id": "xo", "emoji": "⭕", "label": "X/O", "cog": "TicTacToe", "method": "build_top_embed"},
    {"id": "hangman", "emoji": "🪢", "label": "المشنوق", "cog": "Hangman", "method": "build_top_embed"},
    {"id": "trivia", "emoji": "🧠", "label": "Trivia", "cog": "Trivia", "method": "build_top_embed"},
    {"id": "dice", "emoji": "🎲", "label": "النرد", "cog": "Dice", "method": "build_top_embed"},
    {"id": "coinflip", "emoji": "🪙", "label": "Coinflip", "cog": "Coinflip", "method": "build_top_embed"},
    {"id": "slots", "emoji": "🎰", "label": "Slots", "cog": "Slots", "method": "build_top_embed"},
    {"id": "scratch", "emoji": "🎫", "label": "Scratch Card", "cog": "Scratch", "method": "build_top_embed"},
    {"id": "lottery", "emoji": "🎟️", "label": "Lottery", "cog": "Lottery", "method": "build_top_embed"},
    {"id": "counting", "emoji": "🔢", "label": "العدّاد", "cog": "Counting", "method": "build_status_embed"},
]


class LeaderboardSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(label=lb["label"], value=lb["id"], emoji=lb["emoji"])
            for lb in LEADERBOARDS
        ]
        super().__init__(
            placeholder="🏆 اختار اللوحة اللي بغيتي تشوف...",
            options=options,
            custom_id="ggmw9:leaderboard_panel:select",
        )

    def _result_key(self, interaction: discord.Interaction):
        """مفتاح فريد لكل عضو + نفس رسالة البانل.

        هكذا كل عضو عندو غير نتيجة ephemeral وحدة مرتبطة بهاد البانل،
        وكل اختيار جديد كيبدل نفس الرسالة بدل ما يزيد رسالة أخرى تحتها.
        """
        guild_id = interaction.guild.id if interaction.guild else 0
        panel_message_id = interaction.message.id if interaction.message else 0
        return (guild_id, panel_message_id, interaction.user.id)

    async def _show_result(
        self,
        interaction: discord.Interaction,
        *,
        embed: discord.Embed = None,
        content: str = None,
    ):
        # نخزنو آخر رسالة ephemeral لكل عضو على نفس البانل.
        # التخزين فالـ bot كيخليه مشترك حتى إلا كان عندنا أكثر من instance ديال الـ View.
        if not hasattr(self.bot, "_leaderboard_ephemeral_results"):
            self.bot._leaderboard_ephemeral_results = {}

        results = self.bot._leaderboard_ephemeral_results
        key = self._result_key(interaction)
        previous = results.get(key)

        # خاصنا نجاوبو الـ interaction الحالية حتى إلا غادي نعدل رسالة قديمة.
        await interaction.response.defer(ephemeral=True)

        if previous is not None:
            try:
                await previous.edit(content=content, embed=embed)
                return
            except (discord.NotFound, discord.HTTPException):
                # ممكن token ديال الرسالة القديمة سالا أو الرسالة تحيدات.
                # فهاد الحالة نصاوبو نتيجة جديدة ونوليو نتبعوها.
                results.pop(key, None)

        try:
            msg = await interaction.followup.send(
                content=content,
                embed=embed,
                ephemeral=True,
                wait=True,
            )
            results[key] = msg
        except discord.HTTPException:
            # fallback نادر: إلا Discord رفض يرجع WebhookMessage مع wait=True.
            await interaction.followup.send(
                content=content,
                embed=embed,
                ephemeral=True,
            )

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        lb = next((x for x in LEADERBOARDS if x["id"] == choice), None)
        if not lb:
            await self._show_result(interaction, content="❌ ماكايناش هاد اللوحة.")
            return

        cog = self.bot.get_cog(lb["cog"])
        if not cog or not hasattr(cog, lb["method"]):
            await self._show_result(
                interaction, content="❌ هاد اللعبة ماشي متوفرة دابا."
            )
            return

        embed = getattr(cog, lb["method"])(interaction.guild)
        await self._show_result(interaction, embed=embed)


class LeaderboardPanelView(discord.ui.View):
    """بانل دائم فـ #games-leaderboard — Select menu فيه لوحة لكل لعبة، كل واحد
    كيختار وكتبان ليه بوحدو (ephemeral) — بلا ما يخربق الشانيل."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(LeaderboardSelect(bot))


class GamesPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """كيتسمى أوتوماتيك ملي كيتحمّل الـ cog — هنا كنسجّلو الـ persistent views."""
        self.bot.add_view(GamesPanelView(self.bot))
        self.bot.add_view(ShopPanelView(self.bot))
        self.bot.add_view(LeaderboardPanelView(self.bot))
        print("✅ [GAMES] Persistent panel view مسجّل.")
        print("✅ [SHOP] Persistent shop panel view مسجّل.")
        print("✅ [LEADERBOARD] Persistent leaderboard panel view مسجّل.")

    @commands.Cog.listener()
    async def on_ready(self):
        # 🎮 ARCADE — edit old Mini Games panel in place when possible.
        if cfg.GAMES_PANEL_CHANNEL_ID:
            channel = self.bot.get_channel(cfg.GAMES_PANEL_CHANNEL_ID)
            if channel:
                found = None
                try:
                    async for msg in channel.history(limit=30):
                        title = msg.embeds[0].title if msg.author == self.bot.user and msg.embeds else ""
                        if title and ("Mini Games" in title or "ARCADE" in title):
                            found = msg; break
                    embed = self._build_arcade_embed()
                    if found:
                        await found.edit(embed=embed, view=GamesPanelView(self.bot))
                    else:
                        await channel.send(embed=embed, view=GamesPanelView(self.bot))
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # Marketplace panel
        if getattr(cfg, "SHOP_PANEL_CHANNEL_ID", 0):
            shop_ch = self.bot.get_channel(cfg.SHOP_PANEL_CHANNEL_ID)
            if shop_ch:
                found = None
                try:
                    async for msg in shop_ch.history(limit=30):
                        title = msg.embeds[0].title if msg.author == self.bot.user and msg.embeds else ""
                        if title and ("المتجر" in title or "Marketplace" in title):
                            found = msg; break
                    embed = self._build_shop_panel_embed()
                    if found:
                        await found.edit(embed=embed, view=ShopPanelView(self.bot))
                    else:
                        await shop_ch.send(embed=embed, view=ShopPanelView(self.bot))
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # Leaderboards panel
        if getattr(cfg, "GAMES_LEADERBOARD_CHANNEL_ID", 0):
            lb_ch = self.bot.get_channel(cfg.GAMES_LEADERBOARD_CHANNEL_ID)
            if lb_ch:
                found = None
                try:
                    async for msg in lb_ch.history(limit=30):
                        title = msg.embeds[0].title if msg.author == self.bot.user and msg.embeds else ""
                        if title and "Leaderboards" in title:
                            found = msg; break
                    embed = self._build_leaderboard_embed()
                    if found:
                        await found.edit(embed=embed, view=LeaderboardPanelView(self.bot))
                    else:
                        await lb_ch.send(embed=embed, view=LeaderboardPanelView(self.bot))
                except (discord.Forbidden, discord.HTTPException):
                    pass

    def _build_arcade_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎮・ARCADE — GGMW9 World",
            description=(
                "**ARCADE هو القلب ديال العالم الاقتصادي.** من هنا كتدخل Mini Games، Casino، Marketplace، Bank، Wallet وLeaderboards.\n\n"
                "💵 العملة: **USD** • Wallet للعب/الشراء • Savings فـBank • Assets كيدخلو فـNet Worth."
            ),
            color=discord.Color.blurple(), timestamp=datetime.now(),
        )
        embed.add_field(
            name="🕹️ Earn — Mini Games",
            value=(
                f"`/daily` {cfg.fmt_money(cfg.COINS_DAILY)} • Wordle {cfg.fmt_money(cfg.COINS_WORDLE_WIN)} • "
                f"X/O {cfg.fmt_money(cfg.COINS_PVP_WIN)}\n"
                f"Hangman {cfg.fmt_money(cfg.COINS_HANGMAN_WIN)} • Reaction {cfg.fmt_money(cfg.COINS_REACTION_WIN)} • "
                f"Counting {cfg.fmt_money(cfg.COINS_COUNTING_MILESTONE)} / milestone\n"
                f"Non-casino daily reward cap: **{cfg.fmt_money(cfg.COINS_DAILY_CAP)}**"
            ), inline=False,
        )
        embed.add_field(
            name="🎰 Casino — fixed fair odds",
            value=(
                "Dice • Coinflip • Slots • Scratch • Lottery\n"
                f"Max bet = table limit + bankroll protection ({getattr(cfg,'CASINO_MAX_BET_WALLET_PERCENT',10)}% Wallet). "
                "Fairness panel كيبين RTP/House Edge."
            ), inline=False,
        )
        embed.add_field(
            name="🛒 Spend / Build Wealth",
            value="Boosts • Identity • Banking • Social • Assets • Luxury. الفلوس دابا عندها استعمال وماشي غير رقم كيتجمع.",
            inline=False,
        )
        embed.set_footer(text="GGMW9 ARCADE • play → earn → save → spend → own assets")
        return embed

    def _build_shop_panel_embed(self) -> discord.Embed:
        return discord.Embed(
            title="🛒 GGMW9 Marketplace",
            description=(
                "Marketplace منظم بـCategories: ⚡ Boosts • 🎨 Identity • 🏦 Banking • 📣 Social • 🏠 Assets • 👑 Luxury.\n"
                "ضغط الزر وشوف الثمن ديالك بعد Level Discount."
            ),
            color=discord.Color.blurple(), timestamp=datetime.now(),
        )

    def _build_leaderboard_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🏆 Leaderboards",
            description="اختار اللوحة من اللائحة؛ النتيجة كتبان ليك Ephemeral.",
            color=discord.Color.gold(), timestamp=datetime.now(),
        )
        embed.add_field(name="📋 Available", value="\n".join(f"{lb['emoji']} {lb['label']}" for lb in LEADERBOARDS), inline=False)
        return embed

    async def _send_panel(self, channel: discord.TextChannel):
        await channel.send(embed=self._build_arcade_embed(), view=GamesPanelView(self.bot))

    async def _send_shop_panel(self, channel: discord.TextChannel):
        await channel.send(embed=self._build_shop_panel_embed(), view=ShopPanelView(self.bot))

    async def _send_leaderboard_panel(self, channel: discord.TextChannel):
        await channel.send(embed=self._build_leaderboard_embed(), view=LeaderboardPanelView(self.bot))


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesPanel(bot))
    # ShopPanel و LeaderboardPanel داخل GamesPanel — ماخصهمش Cog منفصل
    # حيت حطينا الدوال ديالهم فنفس الكلاس.
