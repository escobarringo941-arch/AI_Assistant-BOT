# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_slots.py — 🎰 Slots                       ║
═══════════════════════════════════════════════════════

3 reels، كل واحد كيطلع رمز عشوائي حسب الوزن ديالو (cfg.SLOTS_SYMBOLS).
  - 3 رموز متطابقين  → المضاعف الكامل ديال الرمز (كل ما كان الرمز نادر،
    كبر المضاعف — 7️⃣ هي الجاكبوت).
  - رمزين متطابقين بس → مكافأة صغيرة (cfg.SLOTS_PAIR_MULTIPLIER).
  - والو ماتطابق              → خسارة الرهان.

بلا اختيار من اللاعب (بخلاف Dice وCoinflip) — غير راهن ودور العجلة.
مربوطة مع Economy: get_balance / spend / add_coins.
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio

from storage import JsonStore
import games_config as cfg

SPIN_FRAMES = 4          # عدد الأنيميشن قبل ما توقف العجلة
SPIN_DELAY = 0.45


def _spin_reel() -> str:
    symbols = list(cfg.SLOTS_SYMBOLS.keys())
    weights = [cfg.SLOTS_SYMBOLS[s]["weight"] for s in symbols]
    return random.choices(symbols, weights=weights, k=1)[0]


def _resolve(bet: int) -> dict:
    """كيدور الـ 3 reels وكيحسب الربح. ماكيمسش الاقتصاد — غير كيحسب."""
    reels = [_spin_reel(), _spin_reel(), _spin_reel()]

    if reels[0] == reels[1] == reels[2]:
        symbol = reels[0]
        multiplier = cfg.SLOTS_SYMBOLS[symbol]["multiplier"]
        win_type = "triple"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        multiplier = cfg.SLOTS_PAIR_MULTIPLIER
        win_type = "pair"
    else:
        multiplier = 0
        win_type = "none"

    payout = int(bet * multiplier) if multiplier else 0
    return {"reels": reels, "win_type": win_type, "multiplier": multiplier, "payout": payout}


class Slots(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("slots_stats.json", default={})
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

    @commands.hybrid_command(name="slots", aliases=["سلوتس"],
                             description="راهن ودور العجلة 🎰")
    @app_commands.describe(bet="شحال بغيتي تراهن")
    @commands.cooldown(1, cfg.COOLDOWN_SLOTS, commands.BucketType.user)
    async def slots_cmd(self, ctx: commands.Context, bet: int):
        eco = self.economy()
        if not eco:
            await ctx.send("❌ نظام الدراهم ماشي محمّل دابا.", ephemeral=True)
            return

        if not self._check_gambling_channel(ctx):
            channel = ctx.guild.get_channel(cfg.GAMBLING_CHANNEL_ID)
            hint = channel.mention if channel else "قناة القمار"
            await ctx.send(f"❌ هاد اللعبة كتخدم غير فـ {hint}.", ephemeral=True)
            return

        key = (ctx.guild.id, ctx.author.id)
        if key in self.active:
            await ctx.send("❌ عندك رهان خدّام ديجا — سالّيه أولاً.", ephemeral=True)
            return

        if bet < cfg.SLOTS_MIN_BET or bet > cfg.SLOTS_MAX_BET:
            await ctx.send(
                f"❌ الرهان خاصو يكون بين **{cfg.SLOTS_MIN_BET}** و "
                f"**{cfg.SLOTS_MAX_BET}** {cfg.CURRENCY_EMOJI}.", ephemeral=True)
            return

        if not eco.spend(ctx.guild.id, ctx.author.id, bet):
            await ctx.send("❌ ماعندكش الفلوس الكافية.", ephemeral=True)
            return

        self.active.add(key)
        msg = await ctx.send(embed=_spinning_embed(bet), ephemeral=True)
        await _play_out(self, msg, ctx.guild.id, ctx.author, bet)

    def build_stats_embed(self, guild: discord.Guild, target: discord.Member) -> discord.Embed:
        """كيتسمى من /gamestats slots"""
        s = self.stats(guild.id, target.id)
        total = s["wins"] + s["losses"]
        rate = (s["wins"] / total * 100) if total else 0
        net = s["won"] - s["wagered"]

        embed = discord.Embed(title=f"🎰 Slots — {target.display_name}",
                              color=discord.Color.blurple())
        embed.add_field(name="🏆 فوز", value=f"**{s['wins']}**", inline=True)
        embed.add_field(name="💀 خسارة", value=f"**{s['losses']}**", inline=True)
        embed.add_field(name="📊 النسبة", value=f"**{rate:.1f}%**", inline=True)
        embed.add_field(name="💰 أكبر ربح", value=f"**{s['biggest_win']:,}**", inline=True)
        embed.add_field(name="7️⃣ جاكبوتات", value=f"**{s.get('jackpots', 0)}**", inline=True)
        embed.add_field(name="📈 الصافي", value=f"**{net:+,}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        return embed

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من بانل الـ leaderboards — أكبر رابحين صافي فـ Slots."""
        guild_data = self.db.guild(guild.id)
        ranked = sorted(
            [(uid, d) for uid, d in guild_data.items() if d.get("wins", 0) or d.get("losses", 0)],
            key=lambda kv: kv[1].get("won", 0) - kv[1].get("wagered", 0),
            reverse=True,
        )[:10]

        if not ranked:
            return discord.Embed(
                title="🎰 Slots — أكبر الرابحين",
                description="📭 مازال حتى واحد ماراهن. دير `/slots`!",
                color=discord.Color.blurple(),
            )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, d) in enumerate(ranked):
            m = guild.get_member(int(uid))
            name = m.display_name if m else f"عضو خارج ({uid})"
            net = d.get("won", 0) - d.get("wagered", 0)
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} **{name}** — 📈 {net:+,} {cfg.CURRENCY_EMOJI}")

        return discord.Embed(
            title="🎰 Slots — أكبر الرابحين",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )


# ═══════════════════════════════════════════════════════

def _spinning_embed(bet: int) -> discord.Embed:
    embed = discord.Embed(
        title="🎰 كتدور...",
        description=f"الرهان: **{bet:,}** {cfg.CURRENCY_EMOJI}",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="النتيجة", value="🎰 | 🎰 | 🎰", inline=False)
    return embed


async def _play_out(cog: Slots, msg: discord.Message, guild_id: int,
                    user: discord.abc.User, bet: int):
    """الأنيميشن + الحساب + التحديث فالاقتصاد — مستعملة من الأمر والـ panel بحال بعضياتهم."""
    embed = _spinning_embed(bet)

    # ═══ أنيميشن ═══
    for _ in range(SPIN_FRAMES):
        frame = " | ".join(_spin_reel() for _ in range(3))
        embed.set_field_at(0, name="النتيجة", value=frame, inline=False)
        try:
            await msg.edit(embed=embed)
        except discord.HTTPException:
            pass
        await asyncio.sleep(SPIN_DELAY)

    result = _resolve(bet)
    reels_display = " | ".join(result["reels"])

    eco = cog.economy()
    user_id = user.id
    s = cog.stats(guild_id, user_id)
    s["wagered"] += bet
    jackpot_bonus = 0

    if result["win_type"] != "none":
        granted = eco.add_coins(guild_id, user_id, result["payout"], source="slots")
        s["wins"] += 1
        s["won"] += granted
        s["biggest_win"] = max(s["biggest_win"], granted)
        if result["win_type"] == "triple" and result["reels"][0] == "7️⃣":
            s["jackpots"] = s.get("jackpots", 0) + 1
            guild = cog.bot.get_guild(guild_id)
            if guild:
                jackpot_bonus = await eco.claim_global_jackpot(guild, user, "slots")
        cog.db.save()

        color = discord.Color.green()
        if result["win_type"] == "triple":
            title = "🎉 جاكبوت!" if result["reels"][0] == "7️⃣" else "🎉 3 متطابقين!"
        else:
            title = "🙂 رمزين متطابقين"
        desc_extra = f"\n💰 ربحتي **{granted:,}** {cfg.CURRENCY_EMOJI} (×{result['multiplier']})"
        if jackpot_bonus:
            desc_extra += f"\n🏆 **Global Jackpot:** +**{jackpot_bonus:,}** {cfg.CURRENCY_EMOJI}"
        if granted < result["payout"]:
            desc_extra += f"\n⚠️ وصلتي قريب من السقف اليومي — كان خاصك تربح {result['payout']:,}."
    else:
        s["losses"] += 1
        cog.db.save()
        guild = cog.bot.get_guild(guild_id)
        if guild:
            await eco.route_gambling_loss(guild, user, bet, "slots")
        color = discord.Color.red()
        title = "💀 خسرتي"
        desc_extra = f"\n📉 خسرتي **{bet:,}** {cfg.CURRENCY_EMOJI}"

    new_balance = eco.get_balance(guild_id, user_id)
    final_embed = discord.Embed(
        title=title,
        description=(f"🎰 **{reels_display}**{desc_extra}\n\n"
                     f"💳 الرصيد الجديد: **{new_balance:,}** {cfg.CURRENCY_EMOJI}"),
        color=color,
    )
    cog.active.discard((guild_id, user_id))

    try:
        from cogs.gambling_panel import GamblingRoundControls
        await msg.edit(
            content=None,
            embed=final_embed,
            view=GamblingRoundControls(cog.bot, user, "slots", bet),
        )
    except discord.HTTPException:
        pass


class ReplayView(discord.ui.View):
    def __init__(self, cog: Slots, user: discord.abc.User, last_bet: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.last_bet = last_bet

    @discord.ui.button(label="🔄 عاود (نفس الرهان)", style=discord.ButtonStyle.success)
    async def replay(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return

        eco = self.cog.economy()
        key = (interaction.guild.id, self.user.id)
        if key in self.cog.active:
            await interaction.response.send_message("❌ عندك رهان خدّام ديجا.", ephemeral=True)
            return
        if not eco.spend(interaction.guild.id, self.user.id, self.last_bet):
            await interaction.response.send_message(
                f"❌ ماعندكش الفلوس الكافية للرهان ديال **{self.last_bet:,}** {cfg.CURRENCY_EMOJI}.",
                ephemeral=True)
            return

        self.cog.active.add(key)
        await interaction.response.edit_message(embed=_spinning_embed(self.last_bet), view=None)
        msg = await interaction.original_response()
        await _play_out(self.cog, msg, interaction.guild.id, self.user, self.last_bet)


async def setup(bot: commands.Bot):
    await bot.add_cog(Slots(bot))
