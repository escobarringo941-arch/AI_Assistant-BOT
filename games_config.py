# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/gambling_panel.py — 🎰 Panel ديال الرهانات      ║
═══════════════════════════════════════════════════════

بحال games_panel.py، ولكن مخصص **غير** للألعاب اللي فيها رهان
(دابا Dice، وأي لعبة رهان جديدة كتزاد فـ GAMBLING_GAMES تحت).

- Panel دائم (persistent) كيتبعث أوتوماتيك فـ cfg.GAMBLING_CHANNEL_ID
  ملي البوت يشعل (on_ready)، بحال شكل games_panel.py بالضبط.
- الرهان كيتدار بمودال (اللاعب كيكتب المبلغ) → مباشرة RiskView
  ديال Dice، بلا ما يخرج من الـ panel ولا يكتب `/dice`.
- كل لعبة رهان (Dice دابا) عندها `_check_gambling_channel()` ديالها
  اللي كتأكد بلي `/dice` نفسها ماخدامش برا هاد القناة.

⚠️ نفس القاعدة التقنية ديال Persistent Views:
   timeout=None + custom_id ثابت + bot.add_view() فـ cog_load().
"""

import discord
from discord.ext import commands
from datetime import datetime

import games_config as cfg

# ═══════ زيد هنا أي لعبة رهان جديدة (Slots, Coinflip...) ═══════
GAMBLING_GAMES = [
    {"id": "dice", "emoji": "🎲", "label": "النرد",
     "desc": "راهن، اختار المخاطرة (سهل/متوسط/صعب)، ارمي النرد"},
    {"id": "coinflip", "emoji": "🪙", "label": "Coinflip",
     "desc": "راهن، اختار وجه ولا ظهر، قلب العملة"},
]


# ═══════════════════════════════════════════════════════
# ║              Panel دائم (Persistent View)             ║
# ═══════════════════════════════════════════════════════

class GamblingPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)          # ← ضروري للـ persistence
        self.bot = bot

    @discord.ui.button(label="🎰 راهن دابا", style=discord.ButtonStyle.success,
                       custom_id="ggmw9:gambling_panel:open")   # ← custom_id ثابت
    async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "🎰 شنو بغيتي تلعب؟",
            view=GamblingMenuView(self.bot, interaction.user),
            ephemeral=True
        )

    @discord.ui.button(label="💰 الرصيد ديالي", style=discord.ButtonStyle.secondary,
                       custom_id="ggmw9:gambling_panel:balance")
    async def balance_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message("❌ نظام الدراهم ماشي محمّل.", ephemeral=True)
            return
        balance = eco.get_balance(interaction.guild.id, interaction.user.id)
        remaining = eco.daily_remaining(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            f"{cfg.CURRENCY_EMOJI} عندك **{balance:,}** {cfg.CURRENCY_NAME_PLURAL}\n"
            f"📊 باقي ليك **{remaining}** من السقف اليومي",
            ephemeral=True
        )

    @discord.ui.button(label="📊 الإحصائيات ديالي", style=discord.ButtonStyle.secondary,
                       custom_id="ggmw9:gambling_panel:stats")
    async def stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embeds = []
        dice_cog = self.bot.get_cog("Dice")
        if dice_cog:
            embeds.append(dice_cog.build_stats_embed(interaction.guild, interaction.user))
        cf_cog = self.bot.get_cog("Coinflip")
        if cf_cog:
            embeds.append(cf_cog.build_stats_embed(interaction.guild, interaction.user))

        if not embeds:
            await interaction.response.send_message("❌ ماكاين حتى لعبة رهان محمّلة دابا.",
                                                    ephemeral=True)
            return
        await interaction.response.send_message(embeds=embeds, ephemeral=True)


# ═══════════════════════════════════════════════════════
# ║          قائمة الرهانات (ephemeral، ماشي دائمة)        ║
# ═══════════════════════════════════════════════════════

class GamblingMenuView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.abc.User):
        super().__init__(timeout=120)
        self.bot = bot
        self.user = user

        options = [
            discord.SelectOption(label=g["label"], value=g["id"],
                                 emoji=g["emoji"], description=g["desc"][:100])
            for g in GAMBLING_GAMES
        ]
        select = discord.ui.Select(placeholder="🎰 اختار لعبة رهان...", options=options)
        select.callback = self.on_pick
        self.add_item(select)
        self.select = select

    async def on_pick(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return

        choice = self.select.values[0]

        # ═══ النرد ═══
        if choice == "dice":
            cog = self.bot.get_cog("Dice")
            eco = self.bot.get_cog("Economy")
            if not cog or not eco:
                await interaction.response.send_message("❌ النرد ماشي متوفر دابا.", ephemeral=True)
                return
            key = (interaction.guild.id, self.user.id)
            if key in cog.active:
                await interaction.response.send_message("❌ عندك رهان خدّام ديجا — سالّيه أولاً.",
                                                        ephemeral=True)
                return
            await interaction.response.send_modal(DiceBetModal(self.bot))
            return

        # ═══ Coinflip ═══
        if choice == "coinflip":
            cog = self.bot.get_cog("Coinflip")
            eco = self.bot.get_cog("Economy")
            if not cog or not eco:
                await interaction.response.send_message("❌ Coinflip ماشي متوفر دابا.", ephemeral=True)
                return
            key = (interaction.guild.id, self.user.id)
            if key in cog.active:
                await interaction.response.send_message("❌ عندك رهان خدّام ديجا — سالّيه أولاً.",
                                                        ephemeral=True)
                return
            await interaction.response.send_modal(CoinflipBetModal(self.bot))
            return

        # ═══ ألعاب رهان جايين (Slots...) ═══
        await interaction.response.send_message("🚧 هاد اللعبة جاية قريب.", ephemeral=True)


# ═══════════════════════════════════════════════════════
# ║              المودال ديال مبلغ الرهان (Dice)          ║
# ═══════════════════════════════════════════════════════

class DiceBetModal(discord.ui.Modal, title="🎲 شحال بغيتي تراهن؟"):
    amount = discord.ui.TextInput(
        label="المبلغ", placeholder="مثلا 50", max_length=6, required=True)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        raw = str(self.amount.value).strip()
        if not raw.isdigit():
            await interaction.response.send_message("❌ خاصك تكتب رقم صحيح.", ephemeral=True)
            return
        bet = int(raw)

        cog = self.bot.get_cog("Dice")
        eco = self.bot.get_cog("Economy")
        if not cog or not eco:
            await interaction.response.send_message("❌ النرد ماشي متوفر دابا.", ephemeral=True)
            return

        if bet < cfg.DICE_MIN_BET or bet > cfg.DICE_MAX_BET:
            await interaction.response.send_message(
                f"❌ الرهان خاصو يكون بين **{cfg.DICE_MIN_BET}** و **{cfg.DICE_MAX_BET}** "
                f"{cfg.CURRENCY_EMOJI}.", ephemeral=True)
            return

        key = (interaction.guild.id, interaction.user.id)
        if key in cog.active:
            await interaction.response.send_message("❌ عندك رهان خدّام ديجا.", ephemeral=True)
            return

        balance = eco.get_balance(interaction.guild.id, interaction.user.id)
        if balance < bet:
            await interaction.response.send_message(
                f"❌ ماعندكش الفلوس الكافية — خاصك **{bet - balance:,}** {cfg.CURRENCY_EMOJI} زيادة.",
                ephemeral=True)
            return

        from cogs.game_dice import RiskView   # ← بدّل المسار إلا ملف Dice ماشي فـ cogs/

        embed = discord.Embed(
            title="🎲 النرد — اختار المخاطرة",
            description=(f"💰 الرهان: **{bet:,}** {cfg.CURRENCY_EMOJI}\n\n"
                         "كل ما زادت المخاطرة، قلّت الفرصة وزاد المضاعف."),
            color=discord.Color.blurple(),
        )
        for _, lvl in cfg.DICE_RISK_LEVELS.items():
            chance = round((21 - lvl["threshold"]) / 20 * 100)
            embed.add_field(
                name=lvl["label"],
                value=f"فرصة: **{chance}%**\nمضاعف: **×{lvl['multiplier']}**",
                inline=True,
            )
        await interaction.response.send_message(
            embed=embed, view=RiskView(cog, interaction.user, bet), ephemeral=True)


# ═══════════════════════════════════════════════════════
# ║           المودال ديال مبلغ الرهان (Coinflip)         ║
# ═══════════════════════════════════════════════════════

class CoinflipBetModal(discord.ui.Modal, title="🪙 شحال بغيتي تراهن؟"):
    amount = discord.ui.TextInput(
        label="المبلغ", placeholder="مثلا 50", max_length=6, required=True)

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        raw = str(self.amount.value).strip()
        if not raw.isdigit():
            await interaction.response.send_message("❌ خاصك تكتب رقم صحيح.", ephemeral=True)
            return
        bet = int(raw)

        cog = self.bot.get_cog("Coinflip")
        eco = self.bot.get_cog("Economy")
        if not cog or not eco:
            await interaction.response.send_message("❌ Coinflip ماشي متوفر دابا.", ephemeral=True)
            return

        if bet < cfg.COINFLIP_MIN_BET or bet > cfg.COINFLIP_MAX_BET:
            await interaction.response.send_message(
                f"❌ الرهان خاصو يكون بين **{cfg.COINFLIP_MIN_BET}** و **{cfg.COINFLIP_MAX_BET}** "
                f"{cfg.CURRENCY_EMOJI}.", ephemeral=True)
            return

        key = (interaction.guild.id, interaction.user.id)
        if key in cog.active:
            await interaction.response.send_message("❌ عندك رهان خدّام ديجا.", ephemeral=True)
            return

        balance = eco.get_balance(interaction.guild.id, interaction.user.id)
        if balance < bet:
            await interaction.response.send_message(
                f"❌ ماعندكش الفلوس الكافية — خاصك **{bet - balance:,}** {cfg.CURRENCY_EMOJI} زيادة.",
                ephemeral=True)
            return

        from cogs.game_coinflip import SideView   # ← بدّل المسار إلا ملف Coinflip ماشي فـ cogs/

        embed = discord.Embed(
            title="🪙 Coinflip — اختار وجهك",
            description=(f"💰 الرهان: **{bet:,}** {cfg.CURRENCY_EMOJI}\n"
                         f"🎯 فرصة: **50%** — مضاعف: **×{cfg.COINFLIP_PAYOUT_MULTIPLIER}**"),
            color=discord.Color.blurple(),
        )
        await interaction.response.send_message(
            embed=embed, view=SideView(cog, interaction.user, bet), ephemeral=True)


# ═══════════════════════════════════════════════════════
# ║                       الـ Cog                          ║
# ═══════════════════════════════════════════════════════

class GamblingPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        """كيتسمى أوتوماتيك ملي كيتحمّل الـ cog — هنا كنسجّلو الـ persistent view."""
        self.bot.add_view(GamblingPanelView(self.bot))
        print("✅ [GAMBLING] Persistent panel view مسجّل.")

    @commands.Cog.listener()
    async def on_ready(self):
        """كيصاوب الـ panel أوتوماتيك إلا كان GAMBLING_CHANNEL_ID معمّر."""
        if not cfg.GAMBLING_CHANNEL_ID:
            return
        channel = self.bot.get_channel(cfg.GAMBLING_CHANNEL_ID)
        if not channel:
            return
        # ماتعاودش تبعثها إلا كانت ديجا
        try:
            async for msg in channel.history(limit=20):
                if (msg.author == self.bot.user and msg.embeds
                        and msg.embeds[0].title
                        and "قمار" in msg.embeds[0].title):
                    return
        except discord.Forbidden:
            return
        await self._send_panel(channel)

    async def _send_panel(self, channel):
        embed = discord.Embed(
            title="🎰 قناة القمار",
            description=("هادي القناة ديال الألعاب اللي فيها رهان بالدراهم. "
                         "راهن بحكمة — ماكاين حتى ضمان، غير الحظ 🍀"),
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="🎲 الألعاب المتوفرة",
            value="\n".join(f"{g['emoji']} **{g['label']}** — {g['desc']}"
                            for g in GAMBLING_GAMES),
            inline=False
        )
        embed.add_field(
            name="⚠️ ملاحظة",
            value=(f"🎲 النرد: رهان بين **{cfg.DICE_MIN_BET}**-**{cfg.DICE_MAX_BET}**\n"
                  f"🪙 Coinflip: رهان بين **{cfg.COINFLIP_MIN_BET}**-**{cfg.COINFLIP_MAX_BET}**\n"
                  f"السقف اليومي ديال الربح: **{cfg.COINS_DAILY_CAP}** "
                  f"{cfg.CURRENCY_NAME_PLURAL} كيفما باقي الألعاب."),
            inline=False
        )
        embed.set_footer(text="هاد الألعاب كتخدم غير فهاد القناة")
        await channel.send(embed=embed, view=GamblingPanelView(self.bot))

    # ═══════════════════════════════════════════════════
    # ║   /gamblingpanel — بعث/عاود بعث الـ panel (Admin)   ║
    # ═══════════════════════════════════════════════════

    @commands.hybrid_command(name="gamblingpanel",
                             description="⚙️ بعث panel القمار فهاد الـ channel (Admin)")
    @commands.has_permissions(administrator=True)
    async def gamblingpanel_cmd(self, ctx: commands.Context):
        await self._send_panel(ctx.channel)
        await ctx.send("✅ Panel القمار تبعث.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamblingPanel(bot))
