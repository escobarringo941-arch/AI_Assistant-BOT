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
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)  # ← ضروري للـ persistence
        self.bot = bot

    @discord.ui.button(
        label="🎮 اختار لعبة",
        style=discord.ButtonStyle.success,
        custom_id="ggmw9:games_panel:open",
    )
    async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🎮 شنو بغيتي تلعب؟",
            view=GameMenuView(self.bot, interaction.user),
            ephemeral=True,
        )

    @discord.ui.button(
        label="💰 الرصيد ديالي",
        style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:games_panel:balance",
    )
    async def balance_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message("❌ نظام الدراهم ماشي محمّل.", ephemeral=True)
            return

        balance = eco.get_balance(interaction.guild.id, interaction.user.id)
        remaining = eco.daily_remaining(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            f"{cfg.CURRENCY_EMOJI} عندك **{balance:,}** {eco.currency_word(balance)}\n"
            f"📊 باقي ليك **{remaining}** من السقف اليومي\n"
            f"🛒 دير `/shop` ولا استعمل بانل المتجر فـ #shop باش تشري",
            ephemeral=True,
        )

    @discord.ui.button(
        label="🏆 اللوائح",
        style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:games_panel:tops",
    )
    async def tops_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = (
            f"<#{cfg.GAMES_LEADERBOARD_CHANNEL_ID}>"
            if getattr(cfg, "GAMES_LEADERBOARD_CHANNEL_ID", 0)
            else "#games-leaderboard"
        )
        await interaction.response.send_message(
            f"🏆 كاع اللوائح كاينين فبانل موحّد فـ {ch} — اختار اللعبة من القائمة تما!",
            ephemeral=True,
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
    """بانل المتجر: رسالة وحدة فشانيل #shop، فيها زر كيحل ShopView لكل واحد."""

    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="🛒 فتح المتجر",
        style=discord.ButtonStyle.success,
        custom_id="ggmw9:shop_panel:open",
    )
    async def open_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message(
                "❌ نظام المتجر ماشي محمّل دابا.", ephemeral=True
            )
            return

        from cogs.economy import ShopView

        balance = eco.get_balance(interaction.guild.id, interaction.user.id)
        embed = discord.Embed(
            title="🛒 المتجر",
            description=f"الرصيد ديالك: **{balance:,}** {cfg.CURRENCY_EMOJI}",
            color=discord.Color.blurple(),
        )

        for item in cfg.SHOP_ITEMS:
            if item["type"] == "temp_role" and not item.get("role_id"):
                continue
            ok = "✅" if balance >= item["price"] else "❌"
            embed.add_field(
                name=f"{item['emoji']} {item['name']} — {item['price']:,} 🪙 {ok}",
                value=item["description"],
                inline=False,
            )

        await interaction.response.send_message(
            embed=embed,
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
        """كيصاوب الـ panel أوتوماتيك إلا كان GAMES_PANEL_CHANNEL_ID معمّر."""
        # بانل الألعاب
        if cfg.GAMES_PANEL_CHANNEL_ID:
            channel = self.bot.get_channel(cfg.GAMES_PANEL_CHANNEL_ID)
            if channel:
                try:
                    async for msg in channel.history(limit=20):
                        if (
                            msg.author == self.bot.user
                            and msg.embeds
                            and msg.embeds[0].title
                            and "Mini Games" in msg.embeds[0].title
                        ):
                            break
                    else:
                        await self._send_panel(channel)
                except discord.Forbidden:
                    pass

        # بانل المتجر (شانيل خاصة)
        if getattr(cfg, "SHOP_PANEL_CHANNEL_ID", 0):
            shop_ch = self.bot.get_channel(cfg.SHOP_PANEL_CHANNEL_ID)
            if shop_ch:
                try:
                    async for msg in shop_ch.history(limit=20):
                        if (
                            msg.author == self.bot.user
                            and msg.embeds
                            and msg.embeds[0].title
                            and "المتجر" in msg.embeds[0].title
                        ):
                            break
                    else:
                        await self._send_shop_panel(shop_ch)
                except discord.Forbidden:
                    pass

        # بانل الـ Leaderboards (شانيل خاصة)
        if getattr(cfg, "GAMES_LEADERBOARD_CHANNEL_ID", 0):
            lb_ch = self.bot.get_channel(cfg.GAMES_LEADERBOARD_CHANNEL_ID)
            if lb_ch:
                try:
                    async for msg in lb_ch.history(limit=20):
                        if (
                            msg.author == self.bot.user
                            and msg.embeds
                            and msg.embeds[0].title
                            and "Leaderboards" in msg.embeds[0].title
                        ):
                            break
                    else:
                        await self._send_leaderboard_panel(lb_ch)
                except discord.Forbidden:
                    pass

    async def _send_panel(self, channel: discord.TextChannel):
        eco = self.bot.get_cog("Economy")
        cap_word = (
            eco.currency_word(cfg.COINS_DAILY_CAP)
            if eco
            else cfg.CURRENCY_NAME_PLURAL
        )

        embed = discord.Embed(
            title="🎮 Mini Games",
            description=(
                "مرحبا بيك فـ قسم الألعاب! العب، ربح "
                f"**{cfg.CURRENCY_NAME_PLURAL}** {cfg.CURRENCY_EMOJI}، "
                "وشريهم من المتجر."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )

        embed.add_field(
            name="🕹️ الألعاب المتوفرة",
            value="\n".join(
                f"{g['emoji']} **{g['label']}** — {g['desc']}"
                for g in GAMES
                if g["id"] != "shop"
            ),
            inline=False,
        )

        embed.add_field(
            name=f"{cfg.CURRENCY_EMOJI} كيفاش تربح {cfg.CURRENCY_NAME_PLURAL}",
            value=(
                f"• `/daily` — **{cfg.COINS_DAILY}** كل نهار (+بونوس streak)\n"
                f"• Wordle — **{cfg.COINS_WORDLE_WIN}**\n"
                f"• X/O — **{cfg.COINS_PVP_WIN}**\n"
                f"• المشنوق — **{cfg.COINS_HANGMAN_WIN}**\n"
                f"• أسرع ضغطة — **{cfg.COINS_REACTION_WIN}**\n"
                f"• العدّاد — **{cfg.COINS_COUNTING_MILESTONE}** كل "
                f"{cfg.COUNTING_MILESTONE_EVERY} رقم"
            ),
            inline=False,
        )

        embed.add_field(
            name="⚠️ ملاحظة",
            value=(
                f"السقف اليومي: **{cfg.COINS_DAILY_CAP}** "
                f"{cap_word} — باش الكل يبقى عندو الشانص."
            ),
            inline=False,
        )

        embed.set_footer(
            text="الألعاب ماكتعطيش XP — الـ XP كيبقى غير من الشات والفويس"
        )
        await channel.send(embed=embed, view=GamesPanelView(self.bot))

    async def _send_shop_panel(self, channel: discord.TextChannel):
        embed = discord.Embed(
            title="🛒 المتجر",
            description=(
                "هنا المتجر الرسمي ديال السيرفر.\n"
                f"جمع {cfg.CURRENCY_NAME_PLURAL} {cfg.CURRENCY_EMOJI} من الألعاب و `/daily`, "
                "ومن بعد كليكي على الزر تحت باش تشوف العروض وتشرِي."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text="متجر GGMW9 | الحوايج الرخيصة والغالية موجودة 😉")

        await channel.send(embed=embed, view=ShopPanelView(self.bot))

    async def _send_leaderboard_panel(self, channel: discord.TextChannel):
        embed = discord.Embed(
            title="🏆 Leaderboards",
            description=(
                "هنا كاع اللوائح ديال الألعاب فبلاصة وحدة!\n"
                "اختار من القائمة تحت باش تشوف الترتيب — النتيجة كتبان ليك نتا بوحدك."
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="📋 اللوائح المتوفرة",
            value="\n".join(f"{lb['emoji']} {lb['label']}" for lb in LEADERBOARDS),
            inline=False,
        )
        embed.set_footer(text="GGMW9 | اختار من القائمة تحت")
        await channel.send(embed=embed, view=LeaderboardPanelView(self.bot))


async def setup(bot: commands.Bot):
    await bot.add_cog(GamesPanel(bot))
    # ShopPanel و LeaderboardPanel داخل GamesPanel — ماخصهمش Cog منفصل
    # حيت حطينا الدوال ديالهم فنفس الكلاس.
