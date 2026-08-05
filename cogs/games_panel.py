# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/games_panel.py — 🎮 Panel موحّد + Setup تلقائي   ║
═══════════════════════════════════════════════════════

جوج حوايج:
  1. `/setupminigames` — كيصاوب **category "Mini Games"** بكاع الـ channels
     أوتوماتيكياً وكيطبع ليك الـ IDs باش تحطهم فـ games_config.py
  2. Panel دائم فـ #games-panel — قائمة وحدة فيها كاع الألعاب

⚠️ نقطة تقنية حرجة — Persistent Views:
   الأزرار العادية كيموتو بعد restart ديال البوت (timeout).
   باش يبقاو خدّامين للأبد خاص:
     • timeout=None
     • custom_id ثابت لكل زر
     • bot.add_view(...) فـ cog_load()
   بلا هاد الثلاثة، الـ panel ديالك غادي يموت كل مرة Railway يعاود يشعل.
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

import games_config as cfg


# ═══════════════════════════════════════════════════════
# ║              Panel دائم (Persistent View)             ║
# ═══════════════════════════════════════════════════════

class GamesPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)          # ← ضروري للـ persistence
        self.bot = bot

    @discord.ui.button(label="🎮 اختار لعبة", style=discord.ButtonStyle.success,
                       custom_id="ggmw9:games_panel:open")   # ← custom_id ثابت
    async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🎮 شنو بغيتي تلعب؟",
            view=GameMenuView(self.bot, interaction.user),
            ephemeral=True
        )

    @discord.ui.button(label="💰 الرصيد ديالي", style=discord.ButtonStyle.secondary,
                       custom_id="ggmw9:games_panel:balance")
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
            f"🛒 دير `/shop` باش تشري",
            ephemeral=True
        )

    @discord.ui.button(label="🏆 اللوائح", style=discord.ButtonStyle.secondary,
                       custom_id="ggmw9:games_panel:tops")
    async def tops_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🏆 **اللوائح المتوفرة:**\n"
            "`/richest` — أغنى الأعضاء 🪙\n"
            "`/wordletop` — أحسن streaks فـ Wordle 🔤\n"
            "`/reactiontop` — أسرع الأعضاء ⚡\n"
            "`/xostats` — إحصائيات X/O ⭕\n"
            "`/hangmanstats` — إحصائيات المشنوق 🪢\n"
            "`/counting` — حالة العدّاد 🔢",
            ephemeral=True
        )


# ═══════════════════════════════════════════════════════
# ║          قائمة الألعاب (ephemeral، ماشي دائمة)         ║
# ═══════════════════════════════════════════════════════

GAMES = [
    {"id": "hangman", "emoji": "🪢", "label": "المشنوق",
     "desc": "خمّن الكلمة حرف بحرف — 6 محاولات"},
    {"id": "wordle", "emoji": "🔤", "label": "Wordle اليومي",
     "desc": "كلمة وحدة كل نهار — 6 محاولات"},
    {"id": "reaction", "emoji": "⚡", "label": "أسرع ضغطة",
     "desc": "أول واحد كيضغط الزر كيربح"},
    {"id": "xo", "emoji": "⭕", "label": "X/O",
     "desc": "تحدّى عضو — استعمل /xo @عضو"},
    {"id": "counting", "emoji": "🔢", "label": "العدّاد",
     "desc": "عدّو جماعة فـ #counting"},
    {"id": "shop", "emoji": "🛒", "label": "المتجر",
     "desc": "شري بالدراهم اللي ربحتي"},
]


class GameMenuView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.abc.User):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user

        options = [
            discord.SelectOption(label=g["label"], value=g["id"],
                                 emoji=g["emoji"], description=g["desc"][:100])
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

        # ═══ المشنوق — كنطلقو الجلسة مباشرة ═══
        if choice == "hangman":
            cog = self.bot.get_cog("Hangman")
            if not cog or not cog.bank:
                await interaction.response.send_message("❌ المشنوق ماشي متوفر.", ephemeral=True)
                return
            from cogs.game_hangman import CategoryView
            key = (interaction.guild.id, interaction.user.id)
            if key in cog.active:
                await interaction.response.send_message(
                    "❌ عندك جلسة خدّامة ديجا.", ephemeral=True)
                return
            await interaction.response.edit_message(
                content="📚 اختار الفئة اللي بغيتي:",
                view=CategoryView(cog, interaction.user))
            return

        # ═══ Wordle — كنوريو الحالة ═══
        if choice == "wordle":
            cog = self.bot.get_cog("Wordle")
            if not cog or not cog.words:
                await interaction.response.send_message("❌ Wordle ماشي متوفر.", ephemeral=True)
                return
            from cogs.game_wordle import normalize
            p = cog.player(interaction.guild.id, interaction.user.id)
            answer = normalize(cog.word_of_the_day())
            await interaction.response.edit_message(
                content="اكتب `/wordle <كلمة>` باش تخمّن 👇",
                embed=cog.build_embed(p, answer, interaction.user), view=None)
            return

        # ═══ أسرع ضغطة ═══
        if choice == "reaction":
            await interaction.response.edit_message(
                content="⚡ دير `/reaction` فـ الشات باش تبدا جولة جماعية.", view=None)
            return

        # ═══ X/O ═══
        if choice == "xo":
            await interaction.response.edit_message(
                content="⭕ دير `/xo @العضو` باش تتحدّاه.", view=None)
            return

        # ═══ العدّاد ═══
        if choice == "counting":
            ch = f"<#{cfg.COUNTING_CHANNEL_ID}>" if cfg.COUNTING_CHANNEL_ID else "#counting"
            await interaction.response.edit_message(
                content=f"🔢 سير لـ {ch} وعدّ! دير `/counting` باش تشوف فين وصلنا.",
                view=None)
            return

        # ═══ المتجر ═══
        if choice == "shop":
            eco = self.bot.get_cog("Economy")
            if not eco:
                await interaction.response.send_message("❌ المتجر ماشي متوفر.", ephemeral=True)
                return
            from cogs.economy import ShopView
            balance = eco.get_balance(interaction.guild.id, interaction.user.id)
            embed = discord.Embed(
                title="🛒 المتجر",
                description=f"الرصيد ديالك: **{balance:,}** {cfg.CURRENCY_EMOJI}",
                color=discord.Color.blurple()
            )
            for item in cfg.SHOP_ITEMS:
                if item["type"] == "temp_role" and not item.get("role_id"):
                    continue
                ok = "✅" if balance >= item["price"] else "❌"
                embed.add_field(
                    name=f"{item['emoji']} {item['name']} — {item['price']:,} 🪙 {ok}",
                    value=item["description"], inline=False)
            await interaction.response.edit_message(
                content=None, embed=embed, view=ShopView(eco, interaction.user))
            return


# ═══════════════════════════════════════════════════════
# ║                       الـ Cog                          ║
# ═══════════════════════════════════════════════════════

class GamesPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """كيتسمى أوتوماتيك ملي كيتحمّل الـ cog — هنا كنسجّلو الـ persistent view."""
        self.bot.add_view(GamesPanelView(self.bot))
        print("✅ [GAMES] Persistent panel view مسجّل.")

    @commands.Cog.listener()
    async def on_ready(self):
        """كيصاوب الـ panel أوتوماتيك إلا كان GAMES_PANEL_CHANNEL_ID معمّر."""
        if not cfg.GAMES_PANEL_CHANNEL_ID:
            return
        channel = self.bot.get_channel(cfg.GAMES_PANEL_CHANNEL_ID)
        if not channel:
            return
        # ماتعاودش تبعثها إلا كانت ديجا
        try:
            async for msg in channel.history(limit=20):
                if (msg.author == self.bot.user and msg.embeds
                        and msg.embeds[0].title
                        and "Mini Games" in msg.embeds[0].title):
                    return
        except discord.Forbidden:
            return
        await self._send_panel(channel)

    async def _send_panel(self, channel):
        eco = self.bot.get_cog("Economy")
        cap_word = eco.currency_word(cfg.COINS_DAILY_CAP) if eco else cfg.CURRENCY_NAME_PLURAL
        embed = discord.Embed(
            title="🎮 Mini Games",
            description="مرحبا بيك فـ قسم الألعاب! العب، ربح "
                        f"**{cfg.CURRENCY_NAME_PLURAL}** {cfg.CURRENCY_EMOJI}، "
                        "وشريهم من المتجر.",
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="🕹️ الألعاب المتوفرة",
            value="\n".join(f"{g['emoji']} **{g['label']}** — {g['desc']}"
                            for g in GAMES if g["id"] != "shop"),
            inline=False
        )
        embed.add_field(
            name=f"{cfg.CURRENCY_EMOJI} كيفاش تربح {cfg.CURRENCY_NAME_PLURAL}",
            value=(f"• `/daily` — **{cfg.COINS_DAILY}** كل نهار (+بونوس streak)\n"
                   f"• Wordle — **{cfg.COINS_WORDLE_WIN}**\n"
                   f"• X/O — **{cfg.COINS_PVP_WIN}**\n"
                   f"• المشنوق — **{cfg.COINS_HANGMAN_WIN}**\n"
                   f"• أسرع ضغطة — **{cfg.COINS_REACTION_WIN}**\n"
                   f"• العدّاد — **{cfg.COINS_COUNTING_MILESTONE}** كل "
                   f"{cfg.COUNTING_MILESTONE_EVERY} رقم"),
            inline=False
        )
        embed.add_field(
            name="⚠️ ملاحظة",
            value=f"السقف اليومي: **{cfg.COINS_DAILY_CAP}** "
                  f"{cap_word} — باش الكل يبقى عندو الشانص.",
            inline=False
        )
        embed.set_footer(text="الألعاب ماكتعطيش XP — الـ XP كيبقى غير من الشات والفويس")
        await channel.send(embed=embed, view=GamesPanelView(self.bot))

    # ═══════════════════════════════════════════════════
    # ║              /setupminigames (Admin)               ║
    # ═══════════════════════════════════════════════════

    # ⚠️ Discord كيسمح بـ 100 slash command بوحدهم لكل سيرفر.
    #    البوت عندك واصل 86. علاش كاع الإحصائيات والإدارة محطوطين
    #    فـ **groups**: أمر فيه subcommands كيتحسب **واحد** عند Discord.
    #    /gamestats + /gamesadmin = 2 بدل 9. (المجموع الجديد: 95/100)

    # ═══════════════════════════════════════════════════
    # ║   /gamestats — كاع الإحصائيات واللوائح (أمر واحد)   ║
    # ═══════════════════════════════════════════════════

    stats_group = app_commands.Group(
        name="gamestats", description="📊 الإحصائيات واللوائح ديال الألعاب")

    @stats_group.command(name="wordle", description="🔤 الإحصائيات ديالك فـ Wordle")
    @app_commands.describe(member="عضو آخر (اختياري)")
    async def gs_wordle(self, interaction: discord.Interaction,
                        member: discord.Member = None):
        cog = self.bot.get_cog("Wordle")
        if not cog:
            await interaction.response.send_message("❌ Wordle ماشي محمّل.", ephemeral=True)
            return
        target = member or interaction.user
        await interaction.response.send_message(
            embed=cog.build_stats_embed(interaction.guild, target))

    @stats_group.command(name="wordletop", description="🔤 أحسن streaks فـ Wordle")
    async def gs_wordletop(self, interaction: discord.Interaction):
        cog = self.bot.get_cog("Wordle")
        if not cog:
            await interaction.response.send_message("❌ Wordle ماشي محمّل.", ephemeral=True)
            return
        await interaction.response.send_message(embed=cog.build_top_embed(interaction.guild))

    @stats_group.command(name="hangman", description="🪢 الإحصائيات ديالك فـ المشنوق")
    @app_commands.describe(member="عضو آخر (اختياري)")
    async def gs_hangman(self, interaction: discord.Interaction,
                         member: discord.Member = None):
        cog = self.bot.get_cog("Hangman")
        if not cog:
            await interaction.response.send_message("❌ المشنوق ماشي محمّل.", ephemeral=True)
            return
        target = member or interaction.user
        await interaction.response.send_message(
            embed=cog.build_stats_embed(interaction.guild, target))

    @stats_group.command(name="xo", description="⭕ الإحصائيات ديالك فـ X/O")
    @app_commands.describe(member="عضو آخر (اختياري)")
    async def gs_xo(self, interaction: discord.Interaction, member: discord.Member = None):
        cog = self.bot.get_cog("TicTacToe")
        if not cog:
            await interaction.response.send_message("❌ X/O ماشي محمّل.", ephemeral=True)
            return
        target = member or interaction.user
        await interaction.response.send_message(
            embed=cog.build_stats_embed(interaction.guild, target))

    @stats_group.command(name="reaction", description="⚡ أسرع 10 أعضاء")
    async def gs_reaction(self, interaction: discord.Interaction):
        cog = self.bot.get_cog("ReactionSpeed")
        if not cog:
            await interaction.response.send_message("❌ اللعبة ماشي محمّلة.", ephemeral=True)
            return
        await interaction.response.send_message(embed=cog.build_top_embed(interaction.guild))

    @stats_group.command(name="counting", description="🔢 حالة العدّاد والريكورد")
    async def gs_counting(self, interaction: discord.Interaction):
        cog = self.bot.get_cog("Counting")
        if not cog:
            await interaction.response.send_message("❌ العدّاد ماشي محمّل.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=cog.build_status_embed(interaction.guild))

    @stats_group.command(name="richest", description="🪙 أغنى 10 أعضاء")
    async def gs_richest(self, interaction: discord.Interaction):
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message("❌ الدراهم ماشي محمّلين.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=eco.build_richest_embed(interaction.guild))

    # ═══════════════════════════════════════════════════
    # ║   /gamesadmin — أوامر الإدارة (أمر واحد)            ║
    # ═══════════════════════════════════════════════════

    admin_group = app_commands.Group(
        name="gamesadmin", description="⚙️ إدارة الألعاب (Admin)",
        default_permissions=discord.Permissions(administrator=True))

    @admin_group.command(name="setup",
                         description="صاوب category Mini Games بكاع الـ channels")
    async def ga_setup(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self._do_setup(interaction)

    @admin_group.command(name="panel", description="بعث panel الألعاب فهاد الـ channel")
    async def ga_panel(self, interaction: discord.Interaction):
        await self._send_panel(interaction.channel)
        await interaction.response.send_message("✅ Panel تبعث.", ephemeral=True)

    @admin_group.command(name="resetcounting", description="رجّع العدّاد لـ 0")
    async def ga_reset(self, interaction: discord.Interaction):
        cog = self.bot.get_cog("Counting")
        if not cog:
            await interaction.response.send_message("❌ العدّاد ماشي محمّل.", ephemeral=True)
            return
        await interaction.response.send_message(cog.admin_reset(interaction.guild))

    @admin_group.command(name="givecoins", description="عطي ولا حيّد دراهم لعضو")
    @app_commands.describe(member="العضو", amount="العدد (سالب باش تحيّد)")
    async def ga_give(self, interaction: discord.Interaction,
                      member: discord.Member, amount: int):
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message("❌ الدراهم ماشي محمّلين.", ephemeral=True)
            return
        await interaction.response.send_message(
            eco.admin_give(interaction.guild, member, amount))

    # ═══════════════════════════════════════════════════
    # ║              منطق /gamesadmin setup               ║
    # ═══════════════════════════════════════════════════

    async def _do_setup(self, ctx):
        guild = ctx.guild

        try:
            # ═══ 1. Category ═══
            category = None
            if cfg.MINIGAMES_CATEGORY_ID:
                category = guild.get_channel(cfg.MINIGAMES_CATEGORY_ID)
            if not category:
                category = discord.utils.get(guild.categories, name="🎮 MINI GAMES")
            if not category:
                category = await guild.create_category("🎮 MINI GAMES")

            created = {"category": category.id}

            # ═══ 2. الـ channels ═══
            async def ensure(name: str, topic: str):
                existing = discord.utils.get(category.text_channels, name=name)
                if existing:
                    return existing
                return await guild.create_text_channel(name, category=category, topic=topic)

            panel_ch = await ensure("🎮│games-panel",
                                    "لوحة الألعاب — اختار لعبة وابدا")
            counting_ch = await ensure("🔢│counting",
                                       "عدّو جماعة! 1، 2، 3... ماتغلطوش 😅")
            top_ch = await ensure("🏆│games-top",
                                  "لوائح الشرف ديال الألعاب")

            created["panel"] = panel_ch.id
            created["counting"] = counting_ch.id
            created["top"] = top_ch.id

            # ═══ 3. الـ panel ═══
            await self._send_panel(panel_ch)

            # ═══ 4. رسالة تعريفية فـ counting ═══
            intro = discord.Embed(
                title="🔢 قناة العدّاد",
                description=(
                    "**القوانين:**\n"
                    "1️⃣ كتبو الأرقام بالترتيب: 1، 2، 3، 4...\n"
                    f"2️⃣ {'ممنوع' if not cfg.COUNTING_SAME_USER_TWICE else 'مسموح'} "
                    "نفس العضو يعدّ مرتين متتاليتين\n"
                    "3️⃣ إلا غلط شي حد → كنرجعو لـ **1** 💥\n"
                    f"4️⃣ كل **{cfg.COUNTING_MILESTONE_EVERY}** رقم = "
                    f"**{cfg.COINS_COUNTING_MILESTONE}** {cfg.CURRENCY_EMOJI} للمشاركين\n\n"
                    "دير `/counting` باش تشوف فين وصلنا والريكورد."
                ),
                color=discord.Color.blue()
            )
            await counting_ch.send(embed=intro)

            # ═══ 5. النتيجة + الـ IDs ═══
            result = discord.Embed(
                title="✅ Mini Games تصاوبو!",
                description="دابا **كوبي هاد الـ IDs** وحطهم فـ `games_config.py`:",
                color=discord.Color.green()
            )
            result.add_field(
                name="📋 games_config.py",
                value=(
                    f"```python\n"
                    f"GAMES_PANEL_CHANNEL_ID = {created['panel']}\n"
                    f"COUNTING_CHANNEL_ID = {created['counting']}\n"
                    f"GAMES_LEADERBOARD_CHANNEL_ID = {created['top']}\n"
                    f"MINIGAMES_CATEGORY_ID = {created['category']}\n"
                    f"```"
                ),
                inline=False
            )
            result.add_field(
                name="⚠️ مهم",
                value="من بعد ما تحطهم، دير **restart** للبوت باش العدّاد يبدا يخدم.",
                inline=False
            )
            await ctx.followup.send(embed=result)

        except discord.Forbidden:
            await ctx.followup.send("❌ ماعنديش صلاحية **Manage Channels** — عطيها للبوت وعاود.")
        except Exception as e:
            await ctx.followup.send(f"❌ خطأ: `{e}`")

async def setup(bot: commands.Bot):
    await bot.add_cog(GamesPanel(bot))
