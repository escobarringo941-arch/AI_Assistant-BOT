# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_lottery.py — 🎟️ Lottery (اليانصيب)         ║
═══════════════════════════════════════════════════════

اللاعب كياخد تيكي فيه cfg.LOTTERY_PICK_COUNT أرقام عشوائية (بلا اختيار
منو — بحال Slots/Scratch) من بين 1 و cfg.LOTTERY_POOL_SIZE. من بعد
كيتسحب رقم آخر بنفس العدد، وكنقارنو:

  - كل ما زاد عدد الأرقام المتطابقين، كبر المضاعف (cfg.LOTTERY_PAYOUTS).
  - تطابق كامل (LOTTERY_PICK_COUNT/LOTTERY_PICK_COUNT) = 🎉 جاكبوت.
  - تطابق 0 أو 1 (ماكاينش فـ LOTTERY_PAYOUTS) = خسارة الرهان.

⚠️ عمدا commands.command ماشي hybrid_command (نفس السبب ديال Scratch):
   البوت قريب من الحد الأقصى ديال ديسكورد (100 slash command globally)،
   واللعب الحقيقي كيمر من البانل (زر → مودال → _play_out) ماشي من
   كتابة /lottery يدوي.

مربوطة مع Economy: get_balance / spend / add_coins.
نفس الهيكلة ديال cogs/game_scratch.py باش يبقى الكود موحّد.
"""

import discord
from discord.ext import commands
import random
import asyncio

from storage import JsonStore
import games_config as cfg

DRAW_DELAY = 0.45     # الوقت بين رقم وآخر فالسحب


def _draw_numbers() -> list:
    return sorted(random.sample(range(1, cfg.LOTTERY_POOL_SIZE + 1), cfg.LOTTERY_PICK_COUNT))


def _resolve(bet: int) -> dict:
    """كيصاوب التيكي والسحب وكيحسب الربح. ماكيمسش الاقتصاد — غير كيحسب."""
    ticket = _draw_numbers()
    draw = _draw_numbers()
    matches = sorted(set(ticket) & set(draw))
    count = len(matches)

    multiplier = cfg.LOTTERY_PAYOUTS.get(count, 0)
    win_type = "jackpot" if count == cfg.LOTTERY_PICK_COUNT else ("match" if multiplier else "none")
    payout = int(bet * multiplier) if multiplier else 0

    return {"ticket": ticket, "draw": draw, "matches": matches, "count": count,
            "win_type": win_type, "multiplier": multiplier, "payout": payout}


def _nums_text(nums: list, highlight: set = frozenset()) -> str:
    return " ".join(f"`{n:02d}`✅" if n in highlight else f"`{n:02d}`" for n in nums)


class Lottery(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("lottery_stats.json", default={})
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

    @commands.command(name="lottery", aliases=["يانصيب"])
    @commands.cooldown(1, cfg.COOLDOWN_LOTTERY, commands.BucketType.user)
    async def lottery_cmd(self, ctx: commands.Context, bet: int):
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

        if bet < cfg.LOTTERY_MIN_BET or bet > cfg.LOTTERY_MAX_BET:
            await ctx.send(
                f"❌ الرهان خاصو يكون بين **{cfg.LOTTERY_MIN_BET}** و "
                f"**{cfg.LOTTERY_MAX_BET}** {cfg.CURRENCY_EMOJI}.", ephemeral=True)
            return

        if not eco.spend(ctx.guild.id, ctx.author.id, bet):
            await ctx.send("❌ ماعندكش الفلوس الكافية.", ephemeral=True)
            return

        self.active.add(key)
        result = _resolve(bet)
        msg = await ctx.send(embed=_ticket_embed(bet, result["ticket"]), ephemeral=True)
        await _play_out(self, msg, ctx.guild.id, ctx.author, bet, result)

    def build_stats_embed(self, guild: discord.Guild, target: discord.Member) -> discord.Embed:
        """كيتسمى من /gamestats lottery"""
        s = self.stats(guild.id, target.id)
        total = s["wins"] + s["losses"]
        rate = (s["wins"] / total * 100) if total else 0
        net = s["won"] - s["wagered"]

        embed = discord.Embed(title=f"🎟️ Lottery — {target.display_name}",
                              color=discord.Color.blurple())
        embed.add_field(name="🏆 فوز", value=f"**{s['wins']}**", inline=True)
        embed.add_field(name="💀 خسارة", value=f"**{s['losses']}**", inline=True)
        embed.add_field(name="📊 النسبة", value=f"**{rate:.1f}%**", inline=True)
        embed.add_field(name="💰 أكبر ربح", value=f"**{s['biggest_win']:,}**", inline=True)
        embed.add_field(name="🎉 جاكبوتات", value=f"**{s.get('jackpots', 0)}**", inline=True)
        embed.add_field(name="📈 الصافي", value=f"**{net:+,}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        return embed

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من بانل الـ leaderboards — أكبر رابحين صافي فـ Lottery."""
        guild_data = self.db.guild(guild.id)
        ranked = sorted(
            [(uid, d) for uid, d in guild_data.items() if d.get("wins", 0) or d.get("losses", 0)],
            key=lambda kv: kv[1].get("won", 0) - kv[1].get("wagered", 0),
            reverse=True,
        )[:10]

        if not ranked:
            return discord.Embed(
                title="🎟️ Lottery — أكبر الرابحين",
                description="📭 مازال حتى واحد ماشرا تيكي. دير `!lottery`!",
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
            title="🎟️ Lottery — أكبر الرابحين",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )


# ═══════════════════════════════════════════════════════

def _ticket_embed(bet: int, ticket: list) -> discord.Embed:
    embed = discord.Embed(
        title="🎟️ التيكي ديالك",
        description=f"الرهان: **{bet:,}** {cfg.CURRENCY_EMOJI}",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="الأرقام ديالك", value=_nums_text(ticket), inline=False)
    embed.add_field(name="السحب", value="🎟️ كيتسحب...", inline=False)
    return embed


async def _play_out(cog: Lottery, msg: discord.Message, guild_id: int,
                    user: discord.abc.User, bet: int, result: dict):
    """الأنيميشن + الحساب + التحديث فالاقتصاد — مستعملة من الأمر والـ panel بحال بعضياتهم."""
    ticket = result["ticket"]
    matches_set = set(result["matches"])
    embed = _ticket_embed(bet, ticket)

    # ═══ أنيميشن السحب — رقم برقم ═══
    revealed = []
    for n in result["draw"]:
        revealed.append(n)
        embed.set_field_at(1, name="السحب", value=_nums_text(revealed), inline=False)
        try:
            await msg.edit(embed=embed)
        except discord.HTTPException:
            pass
        await asyncio.sleep(DRAW_DELAY)

    eco = cog.economy()
    user_id = user.id
    s = cog.stats(guild_id, user_id)
    s["wagered"] += bet
    jackpot_bonus = 0

    if result["win_type"] != "none":
        granted = eco.add_coins(guild_id, user_id, result["payout"], source="lottery")
        s["wins"] += 1
        s["won"] += granted
        s["biggest_win"] = max(s["biggest_win"], granted)
        if result["win_type"] == "jackpot":
            s["jackpots"] = s.get("jackpots", 0) + 1
            guild = cog.bot.get_guild(guild_id)
            if guild:
                jackpot_bonus = await eco.claim_global_jackpot(guild, user, "lottery")
        cog.db.save()

        color = discord.Color.green()
        title = "🎉 جاكبوت!" if result["win_type"] == "jackpot" else f"🎉 تطابق {result['count']} أرقام!"
        desc_extra = f"\n💰 ربحتي **{granted:,}** {eco.currency_word(granted)} (×{result['multiplier']})"
        if jackpot_bonus:
            desc_extra += f"\n🏆 **Global Jackpot:** +**{jackpot_bonus:,}** {cfg.CURRENCY_EMOJI}"
        if granted < result["payout"]:
            desc_extra += f"\n⚠️ وصلتي قريب من السقف اليومي — كان خاصك تربح {result['payout']:,}."
    else:
        s["losses"] += 1
        cog.db.save()
        guild = cog.bot.get_guild(guild_id)
        if guild:
            await eco.route_gambling_loss(guild, user, bet, "lottery")
        color = discord.Color.red()
        title = "💀 خسرتي"
        desc_extra = f"\n📉 خسرتي **{bet:,}** {eco.currency_word(bet)}"

    new_balance = eco.get_balance(guild_id, user_id)
    final_embed = discord.Embed(
        title=title,
        description=(f"🎟️ **التطابقات: {result['count']}/{cfg.LOTTERY_PICK_COUNT}**{desc_extra}\n\n"
                     f"💳 الرصيد الجديد: **{new_balance:,}** {eco.currency_word(new_balance)}"),
        color=color,
    )
    final_embed.add_field(name="الأرقام ديالك", value=_nums_text(ticket, matches_set), inline=False)
    final_embed.add_field(name="السحب", value=_nums_text(result["draw"], matches_set), inline=False)
    cog.active.discard((guild_id, user_id))

    try:
        await msg.edit(embed=final_embed, view=ReplayView(cog, user, bet))
    except discord.HTTPException:
        pass


class ReplayView(discord.ui.View):
    def __init__(self, cog: Lottery, user: discord.abc.User, last_bet: int):
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
        result = _resolve(self.last_bet)
        await interaction.response.edit_message(
            embed=_ticket_embed(self.last_bet, result["ticket"]), view=None)
        msg = await interaction.original_response()
        await _play_out(self.cog, msg, interaction.guild.id, self.user, self.last_bet, result)


async def setup(bot: commands.Bot):
    await bot.add_cog(Lottery(bot))
