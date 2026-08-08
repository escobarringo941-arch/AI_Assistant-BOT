# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║ cogs/gambling_panel.py — 🎰 Gambling Session Panel ║
═══════════════════════════════════════════════════════

الهدف:
- Panel عام ثابت فـ cfg.GAMBLING_CHANNEL_ID.
- كل عضو منين يضغط "راهن دابا" كياخد Session ephemeral وحدة.
- داخل نفس الرسالة: اختيار لعبة → Modal ديال الرهان → اللعب → النتيجة.
- بعد كل جولة: يقدر يعاود بنفس الرهان، يكتب أي رهان جديد، أو يختار لعبة أخرى.
- اختيار لعبة أخرى كيبدل نفس الرسالة؛ ما كيتراكم حتى Result تحت Result.
- ما تزاد حتى Slash Command جديدة.
"""

import discord
from discord.ext import commands
from datetime import datetime

import games_config as cfg


GAMBLING_GAMES = [
    {"id": "dice", "emoji": "🎲", "label": "النرد",
     "desc": "اختار المخاطرة وارمي d20", "cog": "Dice",
     "min_attr": "DICE_MIN_BET", "max_attr": "DICE_MAX_BET"},
    {"id": "coinflip", "emoji": "🪙", "label": "Coinflip",
     "desc": "اختار وجه ولا ظهر", "cog": "Coinflip",
     "min_attr": "COINFLIP_MIN_BET", "max_attr": "COINFLIP_MAX_BET"},
    {"id": "slots", "emoji": "🎰", "label": "Slots",
     "desc": "دور العجلة وربح بالمطابقة", "cog": "Slots",
     "min_attr": "SLOTS_MIN_BET", "max_attr": "SLOTS_MAX_BET"},
    {"id": "scratch", "emoji": "🎫", "label": "Scratch Card",
     "desc": "كشط 9 خانات وربح بالمطابقة", "cog": "Scratch",
     "min_attr": "SCRATCH_MIN_BET", "max_attr": "SCRATCH_MAX_BET"},
    {"id": "lottery", "emoji": "🎟️", "label": "Lottery",
     "desc": "تيكي وسحب أرقام", "cog": "Lottery",
     "min_attr": "LOTTERY_MIN_BET", "max_attr": "LOTTERY_MAX_BET"},
]

GAME_BY_ID = {g["id"]: g for g in GAMBLING_GAMES}


def _limits(game_id: str):
    meta = GAME_BY_ID[game_id]
    return int(getattr(cfg, meta["min_attr"])), int(getattr(cfg, meta["max_attr"]))


def _game_cog(bot: commands.Bot, game_id: str):
    meta = GAME_BY_ID.get(game_id)
    return bot.get_cog(meta["cog"]) if meta else None


def build_session_menu_embed(bot: commands.Bot, guild: discord.Guild, user: discord.abc.User):
    eco = bot.get_cog("Economy")
    balance = eco.get_balance(guild.id, user.id) if eco else 0
    embed = discord.Embed(
        title="🎰 شنو بغيتي تلعب؟",
        description=(
            f"💳 الرصيد ديالك: **{balance:,}** {cfg.CURRENCY_EMOJI}\n"
            f"💰 أقل رهان فكاع الألعاب: **15** {cfg.CURRENCY_EMOJI}\n\n"
            "اختار اللعبة من اللائحة تحت. من بعد كل جولة تقدر تبدل الرهان "
            "**بأي رقم بغيتي** ولا تبدل اللعبة، ونفس الرسالة هي اللي كتتحدث."
        ),
        color=discord.Color.gold(),
    )
    embed.add_field(
        name="🎮 الألعاب",
        value="\n".join(f"{g['emoji']} **{g['label']}** — {g['desc']}" for g in GAMBLING_GAMES),
        inline=False,
    )
    return embed


def build_bet_error_embed(game_id: str, text: str):
    meta = GAME_BY_ID[game_id]
    min_bet, max_bet = _limits(game_id)
    return discord.Embed(
        title=f"{meta['emoji']} {meta['label']} — الرهان",
        description=(
            f"{text}\n\n"
            f"المسموح: **{min_bet:,} → {max_bet:,}** {cfg.CURRENCY_EMOJI}\n"
            "ضغط على **دخل الرهان** وكتب المبلغ اللي بغيتي."
        ),
        color=discord.Color.red(),
    )


class GamblingPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="🎰 راهن دابا",
        style=discord.ButtonStyle.success,
        custom_id="ggmw9:gambling_panel:open",
    )
    async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=build_session_menu_embed(self.bot, interaction.guild, interaction.user),
            view=GamblingMenuView(self.bot, interaction.user),
            ephemeral=True,
        )

    @discord.ui.button(
        label="💰 الرصيد ديالي",
        style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:gambling_panel:balance",
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
            f"📊 باقي ليك **{remaining}** من سقف المكافآت اليومية (ماشي أرباح الرهانات)",
            ephemeral=True,
        )

    @discord.ui.button(
        label="📊 الإحصائيات ديالي",
        style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:gambling_panel:stats",
    )
    async def stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embeds = []
        for cog_name in ("Dice", "Coinflip", "Slots", "Scratch", "Lottery"):
            cog = self.bot.get_cog(cog_name)
            if cog:
                embeds.append(cog.build_stats_embed(interaction.guild, interaction.user))
        if not embeds:
            await interaction.response.send_message(
                "❌ ماكاين حتى لعبة رهان محمّلة دابا.", ephemeral=True
            )
            return
        await interaction.response.send_message(embeds=embeds, ephemeral=True)


class GameSwitchSelect(discord.ui.Select):
    """Dropdown ديال 'شنو بغيتي تلعب؟' — صالح فالمينيو وبعد أي Result."""

    def __init__(self, bot: commands.Bot, user: discord.abc.User, *, row: int = 0):
        self.bot = bot
        self.user = user
        options = [
            discord.SelectOption(
                label=g["label"],
                value=g["id"],
                emoji=g["emoji"],
                description=g["desc"][:100],
            )
            for g in GAMBLING_GAMES
        ]
        super().__init__(
            placeholder="🎮 شنو بغيتي تلعب؟",
            min_values=1,
            max_values=1,
            options=options,
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ هاد الـSession ماشي ديالك.", ephemeral=True)
            return

        game_id = self.values[0]
        cog = _game_cog(self.bot, game_id)
        eco = self.bot.get_cog("Economy")
        if not cog or not eco:
            await interaction.response.edit_message(
                content=None,
                embed=build_bet_error_embed(game_id, "❌ هاد اللعبة ماشي متوفرة دابا."),
                view=BetRetryView(self.bot, self.user, game_id),
            )
            return

        key = (interaction.guild.id, self.user.id)
        if key in getattr(cog, "active", set()):
            await interaction.response.edit_message(
                content=None,
                embed=build_bet_error_embed(game_id, "❌ عندك جولة خدامة دابا، سالّيها أولاً."),
                view=BetRetryView(self.bot, self.user, game_id),
            )
            return

        await interaction.response.send_modal(GameBetModal(self.bot, self.user, game_id))


class GamblingMenuView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.abc.User):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.add_item(GameSwitchSelect(bot, user, row=0))


class BetRetryView(discord.ui.View):
    """إلا الرهان غلط/ماكافيش: نفس الرسالة كتولي Error مع Retry، بلا رسالة جديدة."""

    def __init__(
        self,
        bot: commands.Bot,
        user: discord.abc.User,
        game_id: str,
        current_bet: int = None,
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.user = user
        self.game_id = game_id
        self.current_bet = current_bet
        self.add_item(GameSwitchSelect(bot, user, row=1))

    @discord.ui.button(label="💰 دخل الرهان", style=discord.ButtonStyle.success, row=0)
    async def retry_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        await interaction.response.send_modal(
            GameBetModal(self.bot, self.user, self.game_id, current_bet=self.current_bet)
        )


class GameBetModal(discord.ui.Modal):
    """Modal موحد: نفسو لكل الألعاب، والـsubmit كيعدل نفس Session message."""

    def __init__(
        self,
        bot: commands.Bot,
        user: discord.abc.User,
        game_id: str,
        current_bet: int = None,
    ):
        self.bot = bot
        self.user = user
        self.game_id = game_id
        self.current_bet = current_bet
        meta = GAME_BY_ID[game_id]
        min_bet, max_bet = _limits(game_id)
        super().__init__(title=f"{meta['emoji']} {meta['label']} — شحال تراهن؟")
        placeholder = (
            f"الحالي {current_bet:,} — كتب الجديد"
            if current_bet is not None
            else f"من {min_bet} حتى {max_bet}"
        )
        self.amount = discord.ui.TextInput(
            label="المبلغ",
            placeholder=placeholder,
            min_length=1,
            max_length=12,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return

        raw = str(self.amount.value).strip().replace(",", "").replace(" ", "")
        if not raw.isdigit():
            await interaction.response.edit_message(
                content=None,
                embed=build_bet_error_embed(self.game_id, "❌ خاصك تكتب رقم صحيح."),
                view=BetRetryView(self.bot, self.user, self.game_id, self.current_bet),
            )
            return

        bet = int(raw)
        await start_game_with_bet(
            interaction, self.bot, self.user, self.game_id, bet,
            retry_bet=self.current_bet,
        )


async def start_game_with_bet(
    interaction: discord.Interaction,
    bot: commands.Bot,
    user: discord.abc.User,
    game_id: str,
    bet: int,
    *,
    retry_bet: int = None,
):
    """
    كيدخل اللعبة بنفس Session message:
    - Dice/Coinflip: كيعرض اختيار Risk/Side، والخصم كيوقع ملي يضغط.
    - Slots/Scratch/Lottery: كيخصم وكيبدا مباشرة.
    """
    meta = GAME_BY_ID[game_id]
    min_bet, max_bet = _limits(game_id)
    cog = _game_cog(bot, game_id)
    eco = bot.get_cog("Economy")

    if not cog or not eco:
        await interaction.response.edit_message(
            content=None,
            embed=build_bet_error_embed(game_id, "❌ اللعبة ولا Economy ماشي متوفرين."),
            view=BetRetryView(bot, user, game_id, retry_bet),
        )
        return

    if bet < min_bet or bet > max_bet:
        await interaction.response.edit_message(
            content=None,
            embed=build_bet_error_embed(
                game_id,
                f"❌ الرهان **{bet:,}** خارج الحدود.",
            ),
            view=BetRetryView(bot, user, game_id, bet),
        )
        return

    key = (interaction.guild.id, user.id)
    if key in getattr(cog, "active", set()):
        await interaction.response.edit_message(
            content=None,
            embed=build_bet_error_embed(game_id, "❌ عندك جولة خدامة ديجا."),
            view=BetRetryView(bot, user, game_id, bet),
        )
        return

    balance = eco.get_balance(interaction.guild.id, user.id)
    if balance < bet:
        await interaction.response.edit_message(
            content=None,
            embed=build_bet_error_embed(
                game_id,
                f"❌ ماعندكش الفلوس الكافية. ناقصك **{bet - balance:,}** {cfg.CURRENCY_EMOJI}.",
            ),
            view=BetRetryView(bot, user, game_id, bet),
        )
        return

    # Dice — الرهان كيتخصم ملي يختار Risk.
    if game_id == "dice":
        from cogs.game_dice import RiskView
        embed = discord.Embed(
            title="🎲 النرد — اختار المخاطرة",
            description=(
                f"💰 الرهان: **{bet:,}** {cfg.CURRENCY_EMOJI}\n\n"
                "كل ما زادت المخاطرة، قلّت الفرصة وزاد المضاعف."
            ),
            color=discord.Color.blurple(),
        )
        for lvl in cfg.DICE_RISK_LEVELS.values():
            chance = round((21 - lvl["threshold"]) / 20 * 100)
            embed.add_field(
                name=lvl["label"],
                value=f"فرصة: **{chance}%**\nمضاعف: **×{lvl['multiplier']}**",
                inline=True,
            )
        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=RiskView(cog, user, bet),
        )
        return

    # Coinflip — الرهان كيتخصم ملي يختار Side.
    if game_id == "coinflip":
        from cogs.game_coinflip import SideView
        embed = discord.Embed(
            title="🪙 Coinflip — اختار وجهك",
            description=(
                f"💰 الرهان: **{bet:,}** {cfg.CURRENCY_EMOJI}\n"
                f"🎯 فرصة: **50%** — مضاعف: **×{cfg.COINFLIP_PAYOUT_MULTIPLIER}**"
            ),
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(
            content=None,
            embed=embed,
            view=SideView(cog, user, bet),
        )
        return

    # الألعاب اللي كيبداو مباشرة: الخصم قبل الأنيميشن.
    if not eco.spend(interaction.guild.id, user.id, bet):
        await interaction.response.edit_message(
            content=None,
            embed=build_bet_error_embed(game_id, "❌ الرصيد تبدل وما بقاش كافي."),
            view=BetRetryView(bot, user, game_id, bet),
        )
        return

    cog.active.add(key)

    if game_id == "slots":
        from cogs.game_slots import _spinning_embed, _play_out
        await interaction.response.edit_message(
            content=None, embed=_spinning_embed(bet), view=None
        )
        msg = await interaction.original_response()
        await _play_out(cog, msg, interaction.guild.id, user, bet)
        return

    if game_id == "scratch":
        from cogs.game_scratch import _card_embed, _play_out
        await interaction.response.edit_message(
            content=None, embed=_card_embed(bet), view=None
        )
        msg = await interaction.original_response()
        await _play_out(cog, msg, interaction.guild.id, user, bet)
        return

    if game_id == "lottery":
        from cogs.game_lottery import _resolve, _ticket_embed, _play_out
        result = _resolve(bet)
        await interaction.response.edit_message(
            content=None, embed=_ticket_embed(bet, result["ticket"]), view=None
        )
        msg = await interaction.original_response()
        await _play_out(cog, msg, interaction.guild.id, user, bet, result)
        return


class GamblingRoundControls(discord.ui.View):
    """
    كيبان بعد النتيجة:
    - عاود بنفس الرهان.
    - زيد/نقص الرهان: Modal بأي رقم.
    - Dropdown "شنو بغيتي تلعب؟" باش تبدل اللعبة مباشرة.
    """

    def __init__(
        self,
        bot: commands.Bot,
        user: discord.abc.User,
        game_id: str,
        last_bet: int,
    ):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.game_id = game_id
        self.last_bet = int(last_bet)
        self.add_item(GameSwitchSelect(bot, user, row=1))

    @discord.ui.button(
        label="🔄 عاود بنفس الرهان",
        style=discord.ButtonStyle.success,
        row=0,
    )
    async def replay_same(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        await start_game_with_bet(
            interaction, self.bot, self.user, self.game_id, self.last_bet,
            retry_bet=self.last_bet,
        )

    @discord.ui.button(
        label="💰 زيد/نقص الرهان",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def change_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        await interaction.response.send_modal(
            GameBetModal(
                self.bot, self.user, self.game_id,
                current_bet=self.last_bet,
            )
        )


class GamblingPanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(GamblingPanelView(self.bot))
        print("✅ [GAMBLING] Persistent panel view مسجّل.")

    @commands.Cog.listener()
    async def on_ready(self):
        if not cfg.GAMBLING_CHANNEL_ID:
            return
        channel = self.bot.get_channel(cfg.GAMBLING_CHANNEL_ID)
        if not channel:
            return
        try:
            async for msg in channel.history(limit=20):
                if (
                    msg.author == self.bot.user
                    and msg.embeds
                    and msg.embeds[0].title
                    and "قمار" in msg.embeds[0].title
                ):
                    return
        except discord.Forbidden:
            return
        await self._send_panel(channel)

    async def _send_panel(self, channel):
        eco = self.bot.get_cog("Economy")
        cap_word = eco.currency_word(cfg.COINS_DAILY_CAP) if eco else cfg.CURRENCY_NAME_PLURAL
        embed = discord.Embed(
            title="🎰 قناة القمار",
            description=(
                "هادي القناة ديال الألعاب اللي فيها رهان بالدراهم.\n"
                "كل لاعب عندو **Session وحدة**: بدّل الرهان ولا اللعبة من نفس النتيجة بلا رسائل زايدة."
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="🎲 الألعاب المتوفرة",
            value="\n".join(
                f"{g['emoji']} **{g['label']}** — {g['desc']}"
                for g in GAMBLING_GAMES
            ),
            inline=False,
        )
        embed.add_field(
            name="💰 حدود الرهان",
            value=(
                f"**أقل رهان فكاع الألعاب: 15 {cfg.CURRENCY_EMOJI}**\n"
                f"🎲 النرد: **{cfg.DICE_MIN_BET}**-**{cfg.DICE_MAX_BET}**\n"
                f"🪙 Coinflip: **{cfg.COINFLIP_MIN_BET}**-**{cfg.COINFLIP_MAX_BET}**\n"
                f"🎰 Slots: **{cfg.SLOTS_MIN_BET}**-**{cfg.SLOTS_MAX_BET}**\n"
                f"🎫 Scratch: **{cfg.SCRATCH_MIN_BET}**-**{cfg.SCRATCH_MAX_BET}**\n"
                f"🎟️ Lottery: **{cfg.LOTTERY_MIN_BET}**-**{cfg.LOTTERY_MAX_BET}**\n"
                f"📊 سقف المكافآت اليومية: **{cfg.COINS_DAILY_CAP}** {cap_word}\n"
                "🎰 **ربح الرهانات ماعندوش Daily Cap** — إلا ربحت، كتشد الـpayout كامل."
            ),
            inline=False,
        )
        embed.set_footer(text="اختار اللعبة والرهان من الـPanel — ما تحتاجش Slash Commands")
        await channel.send(embed=embed, view=GamblingPanelView(self.bot))

    # الأمر القديم بقى كما هو؛ ما زدنا حتى Slash جديد.
    @commands.command(name="gamblingpanel", hidden=True)
    @commands.has_permissions(administrator=True)
    async def gamblingpanel_cmd(self, ctx: commands.Context):
        await self._send_panel(ctx.channel)
        await ctx.send("✅ Panel القمار تبعث.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamblingPanel(bot))
