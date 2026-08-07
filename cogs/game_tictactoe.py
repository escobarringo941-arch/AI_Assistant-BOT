# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_tictactoe.py — ⭕ X/O بالتحدي (PvP)        ║
═══════════════════════════════════════════════════════

`/xo @عضو` → كيوصلو تحدي بزر قبلت/رفضت → grid ديال 9 أزرار.
الرابح كياخد دراهم. تعادل = دراهم أقل للجوج.

هادا **PvP حقيقي** — التنافس بين الأعضاء بوحدهم، ماشي مع البوت.
هادشي هو اللي كيخلق الأجواء فالسيرفر.
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

from storage import JsonStore
import games_config as cfg

# ═══════ الخطوط الرابحة (indices ديال الـ grid 3×3) ═══════
WIN_LINES = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),   # صفوف
    (0, 3, 6), (1, 4, 7), (2, 5, 8),   # أعمدة
    (0, 4, 8), (2, 4, 6),              # قطريات
]

EMPTY = None
MARKS = {0: "❌", 1: "⭕"}


class TicTacToe(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("tictactoe_stats.json", default={})
        # {(guild_id, user_id)} — باش عضو ما يكونش فجوج ماتشات فنفس الوقت
        self.busy = set()

    def stats(self, guild_id: int, user_id: int) -> dict:
        return self.db.user(guild_id, user_id, default={"wins": 0, "losses": 0, "draws": 0})

    def record(self, guild_id: int, winner_id, loser_id, draw: bool = False):
        if draw:
            for uid in (winner_id, loser_id):
                self.stats(guild_id, uid)["draws"] += 1
        else:
            self.stats(guild_id, winner_id)["wins"] += 1
            self.stats(guild_id, loser_id)["losses"] += 1
        self.db.save()

    # ═══════════════════════════════════════════════════

    @commands.hybrid_command(name="xo", aliases=["tictactoe", "اكس"],
                             description="تحدّى عضو فـ X/O ⭕")
    @app_commands.describe(member="العضو اللي بغيتي تتحداه")
    @commands.cooldown(1, cfg.COOLDOWN_TICTACTOE, commands.BucketType.user)
    async def xo_cmd(self, ctx: commands.Context, member: discord.Member):
        if member.bot:
            await ctx.send("❌ ماتقدرش تتحدّى بوت.", ephemeral=True)
            return
        if member.id == ctx.author.id:
            await ctx.send("❌ ماتقدرش تتحدّى راسك 😂", ephemeral=True)
            return

        key_a = (ctx.guild.id, ctx.author.id)
        key_b = (ctx.guild.id, member.id)
        if key_a in self.busy:
            await ctx.send("❌ عندك ماتش خدّام ديجا — سالي هاداك أولاً.", ephemeral=True)
            return
        if key_b in self.busy:
            await ctx.send(f"❌ {member.display_name} عندو ماتش خدّام دابا.", ephemeral=True)
            return

        embed = discord.Embed(
            title="⭕ تحدي X/O",
            description=f"{ctx.author.mention} تحدّى {member.mention}!\n\n"
                        f"{member.mention}، واش قابل؟",
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"التحدي كيـexpiri بعد {cfg.TICTACTOE_CHALLENGE_SECONDS} ثانية")
        view = ChallengeView(self, ctx.author, member)
        view.message = await ctx.send(content=member.mention, embed=embed, view=view)

    def build_stats_embed(self, guild: discord.Guild, target: discord.Member) -> discord.Embed:
        """كيتسمى من /gamestats xo"""
        s = self.stats(guild.id, target.id)
        total = s["wins"] + s["losses"] + s["draws"]
        rate = (s["wins"] / total * 100) if total else 0

        embed = discord.Embed(
            title=f"⭕ X/O — {target.display_name}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="🏆 فوز", value=f"**{s['wins']}**", inline=True)
        embed.add_field(name="💀 خسارة", value=f"**{s['losses']}**", inline=True)
        embed.add_field(name="🤝 تعادل", value=f"**{s['draws']}**", inline=True)
        embed.add_field(name="📊 نسبة الفوز", value=f"**{rate:.1f}%** ({total} ماتش)", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        return embed

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من بانل الـ leaderboards — أكثر الأعضاء فوز فـ X/O."""
        guild_data = self.db.guild(guild.id)
        ranked = sorted(
            [(uid, d) for uid, d in guild_data.items() if d.get("wins", 0) > 0],
            key=lambda kv: kv[1].get("wins", 0),
            reverse=True,
        )[:10]

        if not ranked:
            return discord.Embed(
                title="⭕ X/O — أكثر فوز",
                description="📭 مازال حتى واحد مالعب. دير `/xo @عضو`!",
                color=discord.Color.blurple(),
            )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, d) in enumerate(ranked):
            m = guild.get_member(int(uid))
            name = m.display_name if m else f"عضو خارج ({uid})"
            total = d.get("wins", 0) + d.get("losses", 0) + d.get("draws", 0)
            rate = (d.get("wins", 0) / total * 100) if total else 0
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} **{name}** — 🏆 {d.get('wins', 0)} ({rate:.0f}%)")

        return discord.Embed(
            title="⭕ X/O — أكثر فوز",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )


# ═══════════════════════════════════════════════════════
# ║                  View ديال التحدي                     ║
# ═══════════════════════════════════════════════════════

class ChallengeView(discord.ui.View):
    def __init__(self, cog: TicTacToe, challenger: discord.Member, opponent: discord.Member):
        super().__init__(timeout=cfg.TICTACTOE_CHALLENGE_SECONDS)
        self.cog = cog
        self.challenger = challenger
        self.opponent = opponent
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.opponent.id:
            await interaction.response.send_message(
                "❌ هاد التحدي ماشي ليك.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ قبلت", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        key_a = (interaction.guild.id, self.challenger.id)
        key_b = (interaction.guild.id, self.opponent.id)
        if key_a in self.cog.busy or key_b in self.cog.busy:
            await interaction.response.send_message("❌ واحد منكم بدا ماتش آخر.", ephemeral=True)
            return

        self.cog.busy.add(key_a)
        self.cog.busy.add(key_b)
        self.stop()

        game = GameView(self.cog, self.challenger, self.opponent)
        await interaction.response.edit_message(
            content=None, embed=game.build_embed(), view=game)
        game.message = await interaction.original_response()

    @discord.ui.button(label="❌ رفضت", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        embed = discord.Embed(
            title="❌ التحدي مرفوض",
            description=f"{self.opponent.mention} رفض التحدي ديال {self.challenger.mention}.",
            color=discord.Color.dark_gray()
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    async def on_timeout(self):
        if self.message:
            embed = discord.Embed(
                title="⏰ التحدي سالا الوقت",
                description=f"{self.opponent.mention} ماردّش على التحدي.",
                color=discord.Color.dark_gray()
            )
            try:
                await self.message.edit(content=None, embed=embed, view=None)
            except discord.HTTPException:
                pass


# ═══════════════════════════════════════════════════════
# ║                  View ديال اللعب                      ║
# ═══════════════════════════════════════════════════════

class GameView(discord.ui.View):
    def __init__(self, cog: TicTacToe, player_x: discord.Member, player_o: discord.Member):
        super().__init__(timeout=cfg.TICTACTOE_TURN_SECONDS)
        self.cog = cog
        self.players = [player_x, player_o]   # 0 = ❌ ، 1 = ⭕
        self.board = [EMPTY] * 9
        self.turn = 0
        self.message = None
        self.finished = False

        for i in range(9):
            self.add_item(CellButton(i))

    @property
    def current(self) -> discord.Member:
        return self.players[self.turn]

    def build_embed(self, result: str = None) -> discord.Embed:
        embed = discord.Embed(
            title="⭕ X/O",
            color=discord.Color.green() if result else discord.Color.blurple()
        )
        embed.add_field(name="❌", value=self.players[0].mention, inline=True)
        embed.add_field(name="⭕", value=self.players[1].mention, inline=True)
        if result:
            embed.description = result
        else:
            embed.description = f"🎯 الدور ديال {self.current.mention} ({MARKS[self.turn]})"
            embed.set_footer(text=f"عندك {cfg.TICTACTOE_TURN_SECONDS} ثانية")
        return embed

    def winner(self):
        for a, b, c in WIN_LINES:
            if self.board[a] is not EMPTY and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    def full(self) -> bool:
        return all(cell is not EMPTY for cell in self.board)

    def release(self):
        for p in self.players:
            self.cog.busy.discard((self.message.guild.id if self.message else 0, p.id))

    async def finish(self, interaction: discord.Interaction, winner_idx):
        self.finished = True
        self.stop()
        for child in self.children:
            child.disabled = True

        eco = self.cog.bot.get_cog("Economy")
        guild_id = interaction.guild.id

        if winner_idx is None:
            self.cog.record(guild_id, self.players[0].id, self.players[1].id, draw=True)
            coins_txt = ""
            if eco:
                for p in self.players:
                    eco.add_coins(guild_id, p.id, cfg.COINS_PVP_DRAW, source="xo")
                coins_txt = (f"\n{cfg.CURRENCY_EMOJI} +{cfg.COINS_PVP_DRAW} "
                             f"{cfg.CURRENCY_NAME_PLURAL} للجوج")
            result = f"🤝 **تعادل!** حتى واحد ماربح.{coins_txt}"
        else:
            win = self.players[winner_idx]
            lose = self.players[1 - winner_idx]
            self.cog.record(guild_id, win.id, lose.id)
            coins_txt = ""
            if eco:
                granted = eco.add_coins(guild_id, win.id, cfg.COINS_PVP_WIN, source="xo")
                if granted > 0:
                    coins_txt = (f"\n{cfg.CURRENCY_EMOJI} +{granted} "
                                 f"{cfg.CURRENCY_NAME_PLURAL}")
                else:
                    coins_txt = "\n⚠️ وصلتي للسقف اليومي ديال الدراهم."
            result = f"🏆 **{win.mention} ربح!** ({MARKS[winner_idx]}){coins_txt}"

        for p in self.players:
            self.cog.busy.discard((guild_id, p.id))

        await interaction.response.edit_message(embed=self.build_embed(result), view=self)

    async def on_timeout(self):
        if self.finished or not self.message:
            return
        self.finished = True
        for child in self.children:
            child.disabled = True

        loser = self.current
        winner = self.players[1 - self.turn]
        guild_id = self.message.guild.id
        self.cog.record(guild_id, winner.id, loser.id)

        eco = self.cog.bot.get_cog("Economy")
        if eco:
            eco.add_coins(guild_id, winner.id, cfg.COINS_PVP_WIN, source="xo")

        for p in self.players:
            self.cog.busy.discard((guild_id, p.id))

        result = f"⏰ {loser.mention} ماخدّامش دورو — **{winner.mention} ربح** بالوقت."
        try:
            await self.message.edit(embed=self.build_embed(result), view=self)
        except discord.HTTPException:
            pass


class CellButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="\u200b",
            row=index // 3,
            custom_id=f"xo_cell_{index}"
        )
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        view: GameView = self.view

        if interaction.user.id != view.current.id:
            if interaction.user.id in (view.players[0].id, view.players[1].id):
                await interaction.response.send_message("⏳ ماشي دورك.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ هاد الماتش ماشي ديالك.", ephemeral=True)
            return

        if view.board[self.index] is not EMPTY:
            await interaction.response.send_message("❌ هاد الخانة معمّرة.", ephemeral=True)
            return

        # ═══ اللعب ═══
        view.board[self.index] = view.turn
        self.label = MARKS[view.turn]
        self.style = (discord.ButtonStyle.danger if view.turn == 0
                      else discord.ButtonStyle.primary)
        self.disabled = True

        win = view.winner()
        if win is not None:
            await view.finish(interaction, win)
            return
        if view.full():
            await view.finish(interaction, None)
            return

        view.turn = 1 - view.turn
        # كنعاودو نطلقو الـ timeout من الأول لكل دور
        await interaction.response.edit_message(embed=view.build_embed(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicTacToe(bot))
