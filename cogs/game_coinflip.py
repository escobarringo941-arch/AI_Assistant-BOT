# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_coinflip.py — 🪙 Coinflip (وجه ولا ظهر)     ║
═══════════════════════════════════════════════════════

نفس فكرة Dice بالضبط: راهن → اختار وجه/ظهر بزر → أنيميشن → نتيجة.
50/50 حقيقية، والـ house edge كيجي غير من المضاعف
(cfg.COINFLIP_PAYOUT_MULTIPLIER < 2x).

مربوطة مع Economy: get_balance / spend / add_coins (نفس Dice).
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

RNG = random.SystemRandom()

from storage import JsonStore
import games_config as cfg

SIDES = {
    "heads": {"label": "🪙 وجه", "emoji": "🪙"},
    "tails": {"label": "⚫ ظهر", "emoji": "⚫"},
}

FLIP_FRAMES = ["🪙", "🔄", "🪙", "🔄"]


class Coinflip(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("coinflip_stats.json", default={})
        self.active = set()  # {(guild_id, user_id)}

    def stats(self, guild_id: int, user_id: int) -> dict:
        return self.db.user(guild_id, user_id, default={
            "wins": 0, "losses": 0, "wagered": 0, "won": 0, "biggest_win": 0,
        })

    def economy(self):
        return self.bot.get_cog("Economy")

    def _check_gambling_channel(self, ctx: commands.Context) -> bool:
        if not cfg.GAMBLING_CHANNEL_ID:
            return True
        return ctx.channel.id == cfg.GAMBLING_CHANNEL_ID

    # ═══════════════════════════════════════════════════

    @commands.command(name="coinflip", aliases=["قمرة"], hidden=True)
    @commands.cooldown(1, cfg.COOLDOWN_COINFLIP, commands.BucketType.user)
    async def coinflip_cmd(self, ctx: commands.Context, bet: str):
        eco = self.economy()
        if not eco:
            await ctx.send("❌ نظام الدولار ماشي محمّل دابا.", ephemeral=True)
            return

        if not self._check_gambling_channel(ctx):
            channel = ctx.guild.get_channel(cfg.GAMBLING_CHANNEL_ID)
            hint = channel.mention if channel else "قناة القمار"
            await ctx.send(f"❌ هاد اللعبة كتخدم غير فـ {hint}.", ephemeral=True)
            return

        bet = cfg.parse_money_input(bet)
        if bet is None:
            await ctx.send("❌ دخل Bet بالدولار بحال `5` أو `5.50`.", ephemeral=True)
            return
        from cogs.gambling_panel import effective_max_bet, can_start_casino_round
        allowed, _, _ = can_start_casino_round(self.bot, ctx.guild.id, ctx.author.id)
        if not allowed:
            await ctx.send("⏳ وصلتي Session limit ديال Casino.", ephemeral=True)
            return

        key = (ctx.guild.id, ctx.author.id)
        if key in self.active:
            await ctx.send("❌ عندك رهان خدّام ديجا — سالّيه أولاً.", ephemeral=True)
            return

        max_allowed = effective_max_bet(self.bot, ctx.guild.id, ctx.author.id, "coinflip")
        if bet < cfg.COINFLIP_MIN_BET or bet > max_allowed:
            await ctx.send(f"❌ Bet بين **{cfg.fmt_money(cfg.COINFLIP_MIN_BET)}** و **{cfg.fmt_money(max_allowed)}**.", ephemeral=True)
            return

        balance = eco.get_balance(ctx.guild.id, ctx.author.id)
        if balance < bet:
            await ctx.send(
                f"❌ ناقصك **{cfg.fmt_money(bet-balance)}** فالWallet.",
                ephemeral=True)
            return

        view = SideView(self, ctx.author, bet)
        embed = discord.Embed(
            title="🪙 Coinflip — اختار وجهك",
            description=(f"💵 Bet: **{cfg.fmt_money(bet)}**\n"
                         f"🎯 فرصة: **50%** — مضاعف: **×{cfg.COINFLIP_PAYOUT_MULTIPLIER}**"),
            color=discord.Color.blurple(),
        )
        await ctx.send(embed=embed, view=view, ephemeral=True)

    def build_stats_embed(self, guild: discord.Guild, target: discord.Member) -> discord.Embed:
        """كيتسمى من /gamestats coinflip"""
        s = self.stats(guild.id, target.id)
        total = s["wins"] + s["losses"]
        rate = (s["wins"] / total * 100) if total else 0
        net = s["won"] - s["wagered"]

        embed = discord.Embed(title=f"🪙 Coinflip — {target.display_name}",
                              color=discord.Color.blurple())
        embed.add_field(name="🏆 فوز", value=f"**{s['wins']}**", inline=True)
        embed.add_field(name="💀 خسارة", value=f"**{s['losses']}**", inline=True)
        embed.add_field(name="📊 النسبة", value=f"**{rate:.1f}%**", inline=True)
        embed.add_field(name="💰 أكبر ربح", value=f"**{cfg.fmt_money(s['biggest_win'])}**", inline=True)
        embed.add_field(name="📈 الصافي", value=f"**{cfg.fmt_money(net, signed=True)}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        return embed

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من بانل الـ leaderboards — أكبر رابحين صافي فـ Coinflip."""
        guild_data = self.db.guild(guild.id)
        ranked = sorted(
            [(uid, d) for uid, d in guild_data.items() if d.get("wins", 0) or d.get("losses", 0)],
            key=lambda kv: kv[1].get("won", 0) - kv[1].get("wagered", 0),
            reverse=True,
        )[:10]

        if not ranked:
            return discord.Embed(
                title="🪙 Coinflip — أكبر الرابحين",
                description="📭 مازال حتى واحد ماراهن. دخل من **🎮・ARCADE → 🎰 Casino**!",
                color=discord.Color.blurple(),
            )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, d) in enumerate(ranked):
            m = guild.get_member(int(uid))
            name = m.display_name if m else f"عضو خارج ({uid})"
            net = d.get("won", 0) - d.get("wagered", 0)
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} **{name}** — 📈 {cfg.fmt_money(net, signed=True)}")

        return discord.Embed(
            title="🪙 Coinflip — أكبر الرابحين",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )


# ═══════════════════════════════════════════════════════

class SideView(discord.ui.View):
    def __init__(self, cog: Coinflip, user: discord.abc.User, bet: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.bet = bet

        for side_key, side in SIDES.items():
            btn = discord.ui.Button(
                label=side["label"], style=discord.ButtonStyle.primary, row=0
            )
            btn.callback = self._make_callback(side_key)
            self.add_item(btn)

        change_bet = discord.ui.Button(
            label="💰 زيد/نقص الرهان",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        change_bet.callback = self._change_bet
        self.add_item(change_bet)

        from cogs.gambling_panel import GameSwitchSelect
        self.add_item(GameSwitchSelect(self.cog.bot, self.user, row=2))

    async def _change_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        from cogs.gambling_panel import GameBetModal
        await interaction.response.send_modal(
            GameBetModal(self.cog.bot, self.user, "coinflip", current_bet=self.bet)
        )

    def _make_callback(self, side_key: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
                return

            eco = self.cog.economy()
            from cogs.gambling_panel import can_start_casino_round, effective_max_bet
            allowed, _, _ = can_start_casino_round(self.cog.bot, interaction.guild.id, self.user.id)
            if not allowed:
                await interaction.response.send_message("⏳ Session limit وصل. جرب من بعد.", ephemeral=True)
                return
            if self.bet > effective_max_bet(self.cog.bot, interaction.guild.id, self.user.id, "coinflip"):
                await interaction.response.send_message("❌ Bet ولات فوق bankroll limit ديالك.", ephemeral=True)
                return
            key = (interaction.guild.id, self.user.id)
            if key in self.cog.active:
                await interaction.response.send_message("❌ عندك رهان خدّام ديجا.", ephemeral=True)
                return
            if not eco.spend(interaction.guild.id, self.user.id, self.bet):
                await interaction.response.send_message("❌ ماعندكش الفلوس الكافية دابا.",
                                                        ephemeral=True)
                return

            self.cog.active.add(key)
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)

            await run_flip(self.cog, interaction, self.user, self.bet, side_key)

        return callback

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def run_flip(cog: Coinflip, interaction: discord.Interaction, user: discord.abc.User,
                    bet: int, chosen_side: str):
    # ═══ أنيميشن القلب ═══
    flip_embed = discord.Embed(
        title="🪙 كتقلب...",
        description=f"اخترتي {SIDES[chosen_side]['label']} — Bet: **{cfg.fmt_money(bet)}**",
        color=discord.Color.blurple(),
    )
    flip_embed.add_field(name="النتيجة", value=FLIP_FRAMES[0], inline=False)
    # نفس رسالة الـSession، بلا follow-up جديد.
    msg = await interaction.original_response()
    try:
        await msg.edit(content=None, embed=flip_embed, view=None)
    except discord.HTTPException:
        pass
    for frame in FLIP_FRAMES:
        flip_embed.set_field_at(0, name="النتيجة", value=frame, inline=False)
        try:
            await msg.edit(embed=flip_embed)
        except discord.HTTPException:
            pass
        await asyncio.sleep(0.4)

    result_side = RNG.choice(list(SIDES.keys()))
    won = result_side == chosen_side

    guild_id, user_id = interaction.guild.id, user.id
    eco = cog.economy()
    s = cog.stats(guild_id, user_id)
    s["wagered"] += bet

    if won:
        payout = int(bet * cfg.COINFLIP_PAYOUT_MULTIPLIER)
        granted = eco.add_coins(guild_id, user_id, payout, source="coinflip", respect_cap=False)
        s["wins"] += 1
        s["won"] += granted
        s["biggest_win"] = max(s["biggest_win"], granted)
        cog.db.save()

        color = discord.Color.green()
        title = "🎉 ربحتي!"
        desc_extra = f"\n💰 Payout **{cfg.fmt_money(granted)}** (×{cfg.COINFLIP_PAYOUT_MULTIPLIER})"
    else:
        s["losses"] += 1
        cog.db.save()
        await eco.route_gambling_loss(interaction.guild, user, bet, "coinflip")
        color = discord.Color.red()
        title = "💀 خسرتي"
        desc_extra = f"\n📉 Loss **{cfg.fmt_money(bet)}**"

    from cogs.gambling_panel import record_casino_round
    record_casino_round(cog.bot, guild_id, user_id, "coinflip", bet, granted if won else 0)
    if won:
        await eco.record_gambling_win(
            interaction.guild, user, bet, granted, "coinflip",
            details=f"Result: {SIDES[result_side]['label']} • choice: {SIDES[chosen_side]['label']}",
        )
    new_balance = eco.get_balance(guild_id, user_id)
    final_embed = discord.Embed(
        title=title,
        description=(f"طلعت **{SIDES[result_side]['label']}**{desc_extra}\n\n"
                     f"💳 Wallet: **{cfg.fmt_money(new_balance)}**"),
        color=color,
    )
    cog.active.discard((guild_id, user_id))

    from cogs.gambling_panel import GamblingRoundControls
    await msg.edit(
        content=None,
        embed=final_embed,
        view=GamblingRoundControls(cog.bot, user, "coinflip", bet),
    )


class ReplayView(discord.ui.View):
    """Legacy replay compatibility; routes through the fair/session-aware casino hub."""
    def __init__(self, cog, user: discord.abc.User, last_bet: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.last_bet = int(last_bet)

    @discord.ui.button(label="🔄 عاود (نفس الرهان)", style=discord.ButtonStyle.success)
    async def replay(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        from cogs.gambling_panel import start_game_with_bet
        await start_game_with_bet(
            interaction, self.cog.bot, self.user, "coinflip", self.last_bet, retry_bet=self.last_bet
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Coinflip(bot))
