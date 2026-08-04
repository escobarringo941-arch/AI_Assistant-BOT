# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_reaction.py — ⚡ أسرع ضغطة                 ║
═══════════════════════════════════════════════════════

البوت كيقول "استعدو..."، وبعد وقت **عشوائي** كيبان زر أحمر.
أول واحد كيضغطو كيربح.

بلا معرفة، بلا لغة، بلا مهارة خاصة — الكل كيقدر يلعب.
وكتخلق لحظات جماعية فالشات (الناس كتبقى واقفة تسنّى).
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import time
from datetime import datetime

from storage import JsonStore
import games_config as cfg


class ReactionSpeed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("reaction_stats.json", default={})
        self.active_channels = set()

    def stats(self, guild_id: int, user_id: int) -> dict:
        return self.db.user(guild_id, user_id, default={"wins": 0, "best_ms": None,
                                                        "total_ms": 0, "attempts": 0})

    @commands.hybrid_command(name="reaction", aliases=["ضغطة", "fastest"],
                             description="لعبة أسرع ضغطة ⚡ (جماعية)")
    @commands.cooldown(1, cfg.COOLDOWN_REACTION, commands.BucketType.channel)
    async def reaction_cmd(self, ctx: commands.Context):
        if ctx.channel.id in self.active_channels:
            await ctx.send("⏳ كاينة جولة خدّامة فهاد الـ channel — سنّى.", ephemeral=True)
            return

        self.active_channels.add(ctx.channel.id)
        try:
            embed = discord.Embed(
                title="⚡ أسرع ضغطة",
                description="**استعدو...**\n\nالزر غادي يبان فأي لحظة.\n"
                            "⚠️ ماتضغطش قبل — الزر مازال ماكاينش!",
                color=discord.Color.orange()
            )
            embed.set_footer(text="أول واحد كيضغط كيربح")
            message = await ctx.send(embed=embed)

            delay = random.uniform(cfg.REACTION_MIN_DELAY, cfg.REACTION_MAX_DELAY)
            await asyncio.sleep(delay)

            view = ReactionButton(self, ctx.guild.id)
            go_embed = discord.Embed(
                title="🔴 دابا! اضغط!",
                description="# ⬇️",
                color=discord.Color.red()
            )
            view.started_at = time.perf_counter()
            await message.edit(embed=go_embed, view=view)

            await view.wait()

            if view.winner is None:
                timeout_embed = discord.Embed(
                    title="😴 حتى واحد ماضغط",
                    description="الجولة سالات بلا رابح.",
                    color=discord.Color.dark_gray()
                )
                await message.edit(embed=timeout_embed, view=None)
        finally:
            self.active_channels.discard(ctx.channel.id)

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من /gamestats reaction"""
        guild_data = self.db.guild(guild.id)
        valid = [(uid, d) for uid, d in guild_data.items() if d.get("best_ms")]
        ranked = sorted(valid, key=lambda kv: kv[1]["best_ms"])[:10]

        if not ranked:
            return discord.Embed(
                title="⚡ أسرع الأعضاء",
                description="📭 مازال حتى واحد مالعب. دير `/reaction`!",
                color=discord.Color.yellow())

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, d) in enumerate(ranked):
            m = guild.get_member(int(uid))
            name = m.display_name if m else f"عضو ({uid})"
            prefix = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{prefix} **{name}** — ⚡ {d['best_ms']}ms ({d.get('wins', 0)} فوز)")

        return discord.Embed(title="⚡ أسرع الأعضاء",
                             description="\n".join(lines),
                             color=discord.Color.yellow(),
                             timestamp=datetime.now())


class ReactionButton(discord.ui.View):
    def __init__(self, cog: ReactionSpeed, guild_id: int):
        super().__init__(timeout=cfg.REACTION_WINDOW_SECONDS)
        self.cog = cog
        self.guild_id = guild_id
        self.started_at = None
        self.winner = None

    @discord.ui.button(label="🔴 اضغط!", style=discord.ButtonStyle.danger)
    async def press(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.winner is not None:
            await interaction.response.send_message(
                f"⚡ فات الأوان — {self.winner.display_name} سبقك!", ephemeral=True)
            return

        elapsed_ms = int((time.perf_counter() - self.started_at) * 1000)
        self.winner = interaction.user
        button.disabled = True
        button.label = "✅ سالا"
        self.stop()

        s = self.cog.stats(self.guild_id, interaction.user.id)
        s["wins"] += 1
        s["attempts"] += 1
        s["total_ms"] += elapsed_ms
        is_record = s["best_ms"] is None or elapsed_ms < s["best_ms"]
        if is_record:
            s["best_ms"] = elapsed_ms
        self.cog.db.save()

        eco = self.cog.bot.get_cog("Economy")
        coins_line = ""
        if eco:
            granted = eco.add_coins(self.guild_id, interaction.user.id,
                                    cfg.COINS_REACTION_WIN, source="reaction")
            if granted:
                coins_line = f"\n{cfg.CURRENCY_EMOJI} +{granted} {cfg.CURRENCY_NAME_PLURAL}"

        embed = discord.Embed(
            title="⚡ الرابح!",
            description=f"🏆 {interaction.user.mention} ربح بـ **{elapsed_ms}ms**"
                        f"{coins_line}",
            color=discord.Color.green()
        )
        if is_record:
            embed.add_field(name="🎉 ريكورد شخصي جديد!", value="\u200b", inline=False)
        embed.set_footer(text=f"أحسن وقت ديالك: {s['best_ms']}ms")

        await interaction.response.edit_message(embed=embed, view=self)


async def setup(bot: commands.Bot):
    await bot.add_cog(ReactionSpeed(bot))
