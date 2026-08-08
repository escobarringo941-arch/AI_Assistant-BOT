# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_dice.py — 🎲 النرد (راهن وربح مضاعف)        ║
═══════════════════════════════════════════════════════

الفكرة: اللاعب كيراهن بمبلغ، كيختار مستوى المخاطرة (سهل/متوسط/صعب)،
وكيرمي نرد d20. إلا طلع الرقم فوق العتبة ديال المستوى، كيربح
الرهان مضاعف (×). كل ما زادت المخاطرة، قلّت فرصة الربح وزاد المضاعف.

مربوطة مباشرة مع Economy:
  - eco.get_balance(guild_id, user_id)      → يتأكد عندو الفلوس
  - eco.spend(guild_id, user_id, amount)    → كيخصم الرهان
  - eco.add_coins(guild_id, user_id, amount, source="dice") → كيعطي الربح
    (كترجع العدد اللي تزاد فعلاً — ممكن تكون أقل بسبب السقف اليومي)
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

RNG = random.SystemRandom()

from storage import JsonStore
import games_config as cfg

# مستويات المخاطرة كتجي من games_config.py (cfg.DICE_RISK_LEVELS) — بدّلهم من تما
DICE_RISK_LEVELS = cfg.DICE_RISK_LEVELS

DICE_ROLL_FRAMES = ["🎲", "🎲・", "🎲・・", "🎲・・・"]


class Dice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("dice_stats.json", default={})
        self.active = set()  # {(guild_id, user_id)} — يمنع رهانات متوازية لنفس اللاعب

    def stats(self, guild_id: int, user_id: int) -> dict:
        return self.db.user(guild_id, user_id, default={
            "wins": 0, "losses": 0, "wagered": 0, "won": 0, "biggest_win": 0,
        })

    def economy(self):
        return self.bot.get_cog("Economy")

    def _check_gambling_channel(self, ctx: commands.Context) -> bool:
        """كتأكد بلي الأمر تندار فقناة القمار (إلا كانت محددة). قابلة لإعادة الاستعمال
        فأي لعبة رهان أخرى (Slots, Coinflip...)."""
        if not cfg.GAMBLING_CHANNEL_ID:
            return True
        return ctx.channel.id == cfg.GAMBLING_CHANNEL_ID

    # ═══════════════════════════════════════════════════

    @commands.command(name="dice", aliases=["نرد"], hidden=True)
    @commands.cooldown(1, cfg.COOLDOWN_DICE, commands.BucketType.user)
    async def dice_cmd(self, ctx: commands.Context, bet: str):
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
            await ctx.send("⏳ وصلتي Session limit ديال Casino. جرب من بعد.", ephemeral=True)
            return

        key = (ctx.guild.id, ctx.author.id)
        if key in self.active:
            await ctx.send("❌ عندك رهان خدّام ديجا — سالّيه أولاً.", ephemeral=True)
            return

        max_allowed = effective_max_bet(self.bot, ctx.guild.id, ctx.author.id, "dice")
        if bet < cfg.DICE_MIN_BET or bet > max_allowed:
            await ctx.send(
                f"❌ Bet خاصو يكون بين **{cfg.fmt_money(cfg.DICE_MIN_BET)}** و **{cfg.fmt_money(max_allowed)}**.", ephemeral=True)
            return

        balance = eco.get_balance(ctx.guild.id, ctx.author.id)
        if balance < bet:
            await ctx.send(
                f"❌ ناقصك **{cfg.fmt_money(bet - balance)}** فالWallet.",
                ephemeral=True)
            return

        view = RiskView(self, ctx.author, bet)
        embed = discord.Embed(
            title="🎲 النرد — اختار المخاطرة",
            description=f"💵 Bet: **{cfg.fmt_money(bet)}**\n\nFixed odds: كل ما زادت المخاطرة قلّت الفرصة وزاد Payout.",
            color=discord.Color.blurple(),
        )
        for key_name, lvl in DICE_RISK_LEVELS.items():
            chance = round((21 - lvl["threshold"]) / 20 * 100)
            embed.add_field(
                name=lvl["label"],
                value=f"فرصة: **{chance}%**\nمضاعف: **×{lvl['multiplier']}**",
                inline=True,
            )
        await ctx.send(embed=embed, view=view, ephemeral=True)

    def build_stats_embed(self, guild: discord.Guild, target: discord.Member) -> discord.Embed:
        """كيتسمى من /gamestats dice"""
        s = self.stats(guild.id, target.id)
        total = s["wins"] + s["losses"]
        rate = (s["wins"] / total * 100) if total else 0
        net = s["won"] - s["wagered"]

        embed = discord.Embed(title=f"🎲 النرد — {target.display_name}",
                              color=discord.Color.blurple())
        embed.add_field(name="🏆 فوز", value=f"**{s['wins']}**", inline=True)
        embed.add_field(name="💀 خسارة", value=f"**{s['losses']}**", inline=True)
        embed.add_field(name="📊 النسبة", value=f"**{rate:.1f}%**", inline=True)
        embed.add_field(name="💰 أكبر ربح", value=f"**{cfg.fmt_money(s['biggest_win'])}**", inline=True)
        embed.add_field(name="📈 الصافي", value=f"**{cfg.fmt_money(net, signed=True)}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        return embed

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من بانل الـ leaderboards — أكبر رابحين صافي فـ النرد."""
        guild_data = self.db.guild(guild.id)
        ranked = sorted(
            [(uid, d) for uid, d in guild_data.items() if d.get("wins", 0) or d.get("losses", 0)],
            key=lambda kv: kv[1].get("won", 0) - kv[1].get("wagered", 0),
            reverse=True,
        )[:10]

        if not ranked:
            return discord.Embed(
                title="🎲 النرد — أكبر الرابحين",
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
            title="🎲 النرد — أكبر الرابحين",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )


# ═══════════════════════════════════════════════════════

class RiskView(discord.ui.View):
    def __init__(self, cog: Dice, user: discord.abc.User, bet: int):
        super().__init__(timeout=60)
        self.cog = cog
        self.user = user
        self.bet = bet

        for key_name, lvl in DICE_RISK_LEVELS.items():
            btn = discord.ui.Button(
                label=lvl["label"], style=discord.ButtonStyle.primary, row=0
            )
            btn.callback = self._make_callback(key_name)
            self.add_item(btn)

        change_bet = discord.ui.Button(
            label="💰 زيد/نقص الرهان",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        change_bet.callback = self._change_bet
        self.add_item(change_bet)

        # نفس Dropdown ديال Session: يقدر يبدل اللعبة حتى قبل ما يرمي.
        from cogs.gambling_panel import GameSwitchSelect
        self.add_item(GameSwitchSelect(self.cog.bot, self.user, row=2))

    async def _change_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        from cogs.gambling_panel import GameBetModal
        await interaction.response.send_modal(
            GameBetModal(self.cog.bot, self.user, "dice", current_bet=self.bet)
        )

    def _make_callback(self, risk_key: str):
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
            if self.bet > effective_max_bet(self.cog.bot, interaction.guild.id, self.user.id, "dice"):
                await interaction.response.send_message("❌ Bet ولات فوق bankroll limit ديالك.", ephemeral=True)
                return
            # نخصمو الرهان دابا (بعد الضغط على الزر) باش نتجنبو رهانات مزدوجة
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

            await run_roll(self.cog, interaction, self.user, self.bet, risk_key)

        return callback

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


async def run_roll(cog: Dice, interaction: discord.Interaction, user: discord.abc.User,
                    bet: int, risk_key: str):
    lvl = DICE_RISK_LEVELS[risk_key]
    threshold = lvl["threshold"]
    multiplier = lvl["multiplier"]

    # ═══ أنيميشن الرمي ═══
    roll_embed = discord.Embed(
        title="🎲 كيتقلب...",
        description=f"{lvl['label']} — Bet: **{cfg.fmt_money(bet)}**",
        color=discord.Color.blurple(),
    )
    # نفس رسالة الـSession، بلا follow-up جديد.
    msg = await interaction.original_response()
    roll_embed.add_field(name="النتيجة", value=DICE_ROLL_FRAMES[0], inline=False)
    try:
        await msg.edit(content=None, embed=roll_embed, view=None)
    except discord.HTTPException:
        pass
    for frame in DICE_ROLL_FRAMES:
        roll_embed.set_field_at(0, name="النتيجة", value=frame, inline=False)
        try:
            await msg.edit(embed=roll_embed)
        except discord.HTTPException:
            pass
        await asyncio.sleep(0.5)

    result = RNG.randint(1, 20)
    won = result >= threshold

    guild_id, user_id = interaction.guild.id, user.id
    eco = cog.economy()
    s = cog.stats(guild_id, user_id)
    s["wagered"] += bet

    if won:
        payout = int(bet * multiplier)
        granted = eco.add_coins(guild_id, user_id, payout, source="dice", respect_cap=False)
        s["wins"] += 1
        s["won"] += granted
        s["biggest_win"] = max(s["biggest_win"], granted)
        cog.db.save()

        color = discord.Color.green()
        title = "🎉 ربحتي!"
        desc_extra = f"\n💰 Payout **{cfg.fmt_money(granted)}** (×{multiplier})"
    else:
        s["losses"] += 1
        cog.db.save()
        await eco.route_gambling_loss(interaction.guild, user, bet, "dice")
        color = discord.Color.red()
        title = "💀 خسرتي"
        desc_extra = f"\n📉 Loss **{cfg.fmt_money(bet)}**"

    from cogs.gambling_panel import record_casino_round
    record_casino_round(cog.bot, guild_id, user_id, "dice", bet, granted if won else 0)
    if won:
        await eco.record_gambling_win(
            interaction.guild, user, bet, granted, "dice",
            details=f"{lvl['label']} • roll {result}/20 • threshold {threshold}+ • x{multiplier}",
        )
    new_balance = eco.get_balance(guild_id, user_id)
    final_embed = discord.Embed(
        title=title,
        description=(f"{lvl['label']} — العتبة **{threshold}+**\n"
                     f"🎲 طلع: **{result}**{desc_extra}\n\n"
                     f"💳 Wallet: **{cfg.fmt_money(new_balance)}**"),
        color=color,
    )
    cog.active.discard((guild_id, user_id))

    from cogs.gambling_panel import GamblingRoundControls
    await msg.edit(
        content=None,
        embed=final_embed,
        view=GamblingRoundControls(cog.bot, user, "dice", bet),
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
            interaction, self.cog.bot, self.user, "dice", self.last_bet, retry_bet=self.last_bet
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Dice(bot))
