# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_scratch.py — 🎫 Scratch Card (كرت الكشط)   ║
═══════════════════════════════════════════════════════

شبكة 3×3 (9 خانات)، كل خانة فيها رمز عشوائي حسب الوزن ديالو
(cfg.SCRATCH_SYMBOLS). كنكشطو الخانات وحدة وحدة (أنيميشن).

  - إلا طلع نفس الرمز فـ 3 خانات أو كثر → كسبتي، المضاعف ديال
    هاد الرمز (كل ما كان الرمز نادر، كبر المضاعف — 💰 هي الجاكبوت).
  - إلا زادو رمزين ولا كثر عندهم 3 تكرارات، كناخدو الرمز اللي عندو
    أكبر مضاعف.
  - والو ماوصلش لـ 3 تكرارات → خسارة الرهان.

بلا اختيار من اللاعب (بحال Slots) — غير راهن وكشط الكرت.
مربوطة مع Economy: get_balance / spend / add_coins.
نفس الهيكلة ديال cogs/game_slots.py باش يبقى الكود موحّد.
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

RNG = random.SystemRandom()

from storage import JsonStore
import games_config as cfg

SCRATCH_DELAY = 0.35     # الوقت بين كشط خانة وخانة
HIDDEN_CELL = "❔"


def _fill_grid(winning_symbol=None) -> list:
    """Construct a visual grid AFTER the fixed outcome draw. No accidental wins."""
    symbols = list(cfg.SCRATCH_SYMBOLS.keys())
    if winning_symbol:
        fillers = [s for s in symbols if s != winning_symbol]
        cells = [winning_symbol] * cfg.SCRATCH_MATCH_NEEDED
        # Fill remaining cells with max 2 of any other symbol.
        pool = []
        for sym in fillers:
            pool.extend([sym, sym])
        RNG.shuffle(pool)
        cells.extend(pool[: cfg.SCRATCH_GRID_SIZE - len(cells)])
    else:
        # 9 cells, every symbol max twice => mathematically impossible to reach a 3-match.
        pool = []
        for sym in symbols:
            pool.extend([sym, sym])
        RNG.shuffle(pool)
        cells = pool[: cfg.SCRATCH_GRID_SIZE]
    RNG.shuffle(cells)
    return cells


def _resolve(bet: int) -> dict:
    """Fixed transparent outcome table. Theoretical RTP is configured in games_config."""
    outcomes = list(cfg.SCRATCH_OUTCOMES)
    outcome = RNG.choices(outcomes, weights=[o["weight"] for o in outcomes], k=1)[0]
    symbol = outcome.get("symbol")
    multiplier = float(outcome.get("multiplier", 0) or 0)
    grid = _fill_grid(symbol)
    payout = int(bet * multiplier) if multiplier else 0
    return {
        "grid": grid,
        "symbol": symbol,
        "win_type": "match" if symbol else "none",
        "multiplier": multiplier,
        "payout": payout,
        "label": outcome.get("label", ""),
    }


def _grid_text(cells: list) -> str:
    """كيبني الشبكة 3×3 فـ 3 سطور."""
    rows = [cells[i:i + 3] for i in range(0, cfg.SCRATCH_GRID_SIZE, 3)]
    return "\n".join(" | ".join(row) for row in rows)


class Scratch(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("scratch_stats.json", default={})
        self.active = set()  # {(guild_id, user_id)}

    def stats(self, guild_id: int, user_id: int) -> dict:
        return self.db.user(guild_id, user_id, default={
            "wins": 0, "losses": 0, "wagered": 0, "won": 0, "biggest_win": 0, "jackpots": 0,
        })

    def economy(self):
        return self.bot.get_cog("Economy")

    def _check_gambling_channel(self, ctx: commands.Context) -> bool:
        if not cfg.GAMBLING_CHANNEL_ID:
            return True
        return ctx.channel.id == cfg.GAMBLING_CHANNEL_ID

    # ═══════════════════════════════════════════════════

    # ⚠️ عمدا commands.command ماشي hybrid_command: البوت قريب من الحد الأقصى
    # ديال ديسكورد (100 slash command globally) — واللعب الحقيقي كيمر من
    # البانل (زر → مودال → _play_out)، فـ /scratch كـ slash ماشي ضروري.
    # إلا حريتي بلاصة فالعدّاد ديال الـ slash commands وبغيتي ترجعها hybrid،
    # بدّل commands.command لـ commands.hybrid_command وزيد وسط:
    #   @app_commands.describe(bet="شحال بغيتي تراهن")
    @commands.command(name="scratch", aliases=["كشط"])
    @commands.cooldown(1, cfg.COOLDOWN_SCRATCH, commands.BucketType.user)
    async def scratch_cmd(self, ctx: commands.Context, bet: str):
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

        max_allowed = effective_max_bet(self.bot, ctx.guild.id, ctx.author.id, "scratch")
        if bet < cfg.SCRATCH_MIN_BET or bet > max_allowed:
            await ctx.send(f"❌ Bet بين **{cfg.fmt_money(cfg.SCRATCH_MIN_BET)}** و **{cfg.fmt_money(max_allowed)}**.", ephemeral=True)
            return

        if not eco.spend(ctx.guild.id, ctx.author.id, bet):
            await ctx.send("❌ ماعندكش الفلوس الكافية.", ephemeral=True)
            return

        self.active.add(key)
        msg = await ctx.send(embed=_card_embed(bet), ephemeral=True)
        await _play_out(self, msg, ctx.guild.id, ctx.author, bet)

    def build_stats_embed(self, guild: discord.Guild, target: discord.Member) -> discord.Embed:
        """كيتسمى من /gamestats scratch"""
        s = self.stats(guild.id, target.id)
        total = s["wins"] + s["losses"]
        rate = (s["wins"] / total * 100) if total else 0
        net = s["won"] - s["wagered"]

        embed = discord.Embed(title=f"🎫 Scratch Card — {target.display_name}",
                              color=discord.Color.blurple())
        embed.add_field(name="🏆 فوز", value=f"**{s['wins']}**", inline=True)
        embed.add_field(name="💀 خسارة", value=f"**{s['losses']}**", inline=True)
        embed.add_field(name="📊 النسبة", value=f"**{rate:.1f}%**", inline=True)
        embed.add_field(name="💰 أكبر ربح", value=f"**{cfg.fmt_money(s['biggest_win'])}**", inline=True)
        embed.add_field(name="💰 جاكبوتات", value=f"**{s.get('jackpots', 0)}**", inline=True)
        embed.add_field(name="📈 الصافي", value=f"**{cfg.fmt_money(net, signed=True)}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        return embed

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من بانل الـ leaderboards — أكبر رابحين صافي فـ Scratch."""
        guild_data = self.db.guild(guild.id)
        ranked = sorted(
            [(uid, d) for uid, d in guild_data.items() if d.get("wins", 0) or d.get("losses", 0)],
            key=lambda kv: kv[1].get("won", 0) - kv[1].get("wagered", 0),
            reverse=True,
        )[:10]

        if not ranked:
            return discord.Embed(
                title="🎫 Scratch Card — أكبر الرابحين",
                description="📭 مازال حتى واحد ماكشط. دخل من **🎮・ARCADE → 🎰 Casino**!",
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
            title="🎫 Scratch Card — أكبر الرابحين",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )


# ═══════════════════════════════════════════════════════

def _card_embed(bet: int) -> discord.Embed:
    embed = discord.Embed(
        title="🎫 كتكشط...",
        description=f"Bet: **{cfg.fmt_money(bet)}**",
        color=discord.Color.blurple(),
    )
    hidden = [HIDDEN_CELL] * cfg.SCRATCH_GRID_SIZE
    embed.add_field(name="الكرت", value=_grid_text(hidden), inline=False)
    return embed


async def _play_out(cog: Scratch, msg: discord.Message, guild_id: int,
                    user: discord.abc.User, bet: int):
    """الأنيميشن + الحساب + التحديث فالاقتصاد — مستعملة من الأمر والـ panel بحال بعضياتهم."""
    result = _resolve(bet)
    grid = result["grid"]
    embed = _card_embed(bet)

    # ═══ أنيميشن الكشط — خانة بخانة ═══
    revealed = [HIDDEN_CELL] * cfg.SCRATCH_GRID_SIZE
    order = list(range(cfg.SCRATCH_GRID_SIZE))
    RNG.shuffle(order)  # fair OS-backed shuffle

    for idx in order:
        revealed[idx] = grid[idx]
        embed.set_field_at(0, name="الكرت", value=_grid_text(revealed), inline=False)
        try:
            await msg.edit(embed=embed)
        except discord.HTTPException:
            pass
        await asyncio.sleep(SCRATCH_DELAY)

    grid_display = _grid_text(grid)

    eco = cog.economy()
    user_id = user.id
    s = cog.stats(guild_id, user_id)
    s["wagered"] += bet
    jackpot_bonus = 0

    if result["win_type"] != "none":
        granted = eco.add_coins(guild_id, user_id, result["payout"], source="scratch", respect_cap=False)
        s["wins"] += 1
        s["won"] += granted
        s["biggest_win"] = max(s["biggest_win"], granted)
        if result["symbol"] == "💰":
            s["jackpots"] = s.get("jackpots", 0) + 1
            guild = cog.bot.get_guild(guild_id)
            if guild:
                jackpot_bonus = await eco.claim_global_jackpot(guild, user, "scratch")
                if jackpot_bonus:
                    s["won"] += jackpot_bonus
                    s["biggest_win"] = max(s["biggest_win"], granted + jackpot_bonus)
        cog.db.save()

        color = discord.Color.green()
        title = "🎉 جاكبوت!" if result["symbol"] == "💰" else "🎉 3 متطابقين!"
        desc_extra = f"\n💰 Payout **{cfg.fmt_money(granted)}** (×{result['multiplier']})"
        if jackpot_bonus:
            desc_extra += f"\n🏆 **Global Jackpot:** +**{cfg.fmt_money(jackpot_bonus)}**"
    else:
        s["losses"] += 1
        cog.db.save()
        guild = cog.bot.get_guild(guild_id)
        if guild:
            await eco.route_gambling_loss(guild, user, bet, "scratch")
        color = discord.Color.red()
        title = "💀 خسرتي"
        desc_extra = f"\n📉 Loss **{cfg.fmt_money(bet)}**"

    from cogs.gambling_panel import record_casino_round
    round_payout = (granted + jackpot_bonus) if result["win_type"] != "none" else 0
    record_casino_round(cog.bot, guild_id, user_id, "scratch", bet, round_payout)
    if result["win_type"] != "none":
        await eco.record_gambling_win(
            interaction.guild, user, bet, round_payout, "scratch",
            details=f"Symbol: {result['symbol']} • x{result['multiplier']}",
            is_jackpot=bool(jackpot_bonus or result.get("symbol") == "💰"),
        )
    new_balance = eco.get_balance(guild_id, user_id)
    final_embed = discord.Embed(
        title=title,
        description=(f"🎫 **الكرت مكشوط**{desc_extra}\n\n"
                     f"💳 Wallet: **{cfg.fmt_money(new_balance)}**"),
        color=color,
    )
    final_embed.add_field(name="النتيجة", value=grid_display, inline=False)
    cog.active.discard((guild_id, user_id))

    try:
        from cogs.gambling_panel import GamblingRoundControls
        await msg.edit(
            content=None,
            embed=final_embed,
            view=GamblingRoundControls(cog.bot, user, "scratch", bet),
        )
    except discord.HTTPException:
        pass


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
            interaction, self.cog.bot, self.user, "scratch", self.last_bet, retry_bet=self.last_bet
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Scratch(bot))
