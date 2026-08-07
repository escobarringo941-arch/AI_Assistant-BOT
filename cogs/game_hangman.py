# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_hangman.py — 🪢 المشنوق بالدارجة           ║
═══════════════════════════════════════════════════════

نفس الـ pattern ديال Trivia عندك بالضبط:
   panel → اختيار فئة → جلسة ephemeral → إعادة اللعب

الحروف كتتكتب فالشات (ماشي أزرار) — علاش؟
الأبجدية العربية فيها 28 حرف، وديسكورد كيسمح غير بـ 25 زر فـ View وحدة.
فالكتابة أبسط وأسرع للاعب.
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from datetime import datetime

from storage import JsonStore, load_bank
import games_config as cfg

# ═══════ رسم المشنوق حسب عدد الأخطاء ═══════
HANGMAN_STAGES = [
    "```\n     ┌───┐\n     │   │\n         │\n         │\n         │\n    ═════╧═\n```",
    "```\n     ┌───┐\n     │   │\n     😐  │\n         │\n         │\n    ═════╧═\n```",
    "```\n     ┌───┐\n     │   │\n     😐  │\n     │   │\n         │\n    ═════╧═\n```",
    "```\n     ┌───┐\n     │   │\n     😐  │\n    /│   │\n         │\n    ═════╧═\n```",
    "```\n     ┌───┐\n     │   │\n     😟  │\n    /│\\  │\n         │\n    ═════╧═\n```",
    "```\n     ┌───┐\n     │   │\n     😨  │\n    /│\\  │\n    /    │\n    ═════╧═\n```",
    "```\n     ┌───┐\n     │   │\n     💀  │\n    /│\\  │\n    / \\  │\n    ═════╧═\n```",
]


def normalize(char: str) -> str:
    """كتوحّد أشكال الألف والهمزة باش اللاعب ما يعذّبش راسو."""
    mapping = {
        "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
        "ة": "ه",
        "ى": "ي", "ئ": "ي",
        "ؤ": "و",
    }
    return mapping.get(char, char)


class Hangman(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("hangman_stats.json", default={})
        self.bank = load_bank("hangman_words.json", default={})
        self.active = set()   # {(guild_id, user_id)}

    def stats(self, guild_id: int, user_id: int) -> dict:
        return self.db.user(guild_id, user_id, default={"wins": 0, "losses": 0, "streak": 0,
                                                        "best_streak": 0})

    # ═══════════════════════════════════════════════════

    @commands.hybrid_command(name="hangman", aliases=["مشنوق"],
                             description="لعبة المشنوق بالدارجة 🪢")
    @commands.cooldown(1, cfg.COOLDOWN_HANGMAN, commands.BucketType.user)
    async def hangman_cmd(self, ctx: commands.Context):
        if not self.bank:
            await ctx.send("❌ bank الكلمات خاوي — تأكد من `banks/hangman_words.json`.",
                           ephemeral=True)
            return
        key = (ctx.guild.id, ctx.author.id)
        if key in self.active:
            await ctx.send("❌ عندك جلسة خدّامة ديجا — سالّيها أولاً.", ephemeral=True)
            return

        view = CategoryView(self, ctx.author)
        await ctx.send("📚 اختار الفئة اللي بغيتي:", view=view, ephemeral=True)

    def build_stats_embed(self, guild: discord.Guild, target: discord.Member) -> discord.Embed:
        """كيتسمى من /gamestats hangman"""
        s = self.stats(guild.id, target.id)
        total = s["wins"] + s["losses"]
        rate = (s["wins"] / total * 100) if total else 0

        embed = discord.Embed(title=f"🪢 المشنوق — {target.display_name}",
                              color=discord.Color.orange())
        embed.add_field(name="🏆 فوز", value=f"**{s['wins']}**", inline=True)
        embed.add_field(name="💀 خسارة", value=f"**{s['losses']}**", inline=True)
        embed.add_field(name="📊 النسبة", value=f"**{rate:.1f}%**", inline=True)
        embed.add_field(name="🔥 السلسلة الحالية", value=f"**{s['streak']}**", inline=True)
        embed.add_field(name="⭐ أحسن سلسلة", value=f"**{s['best_streak']}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        return embed

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من بانل الـ leaderboards — أحسن سلاسل فوز فالمشنوق."""
        guild_data = self.db.guild(guild.id)
        ranked = sorted(
            [(uid, d) for uid, d in guild_data.items() if d.get("best_streak", 0) > 0],
            key=lambda kv: kv[1].get("best_streak", 0),
            reverse=True,
        )[:10]

        if not ranked:
            return discord.Embed(
                title="🪢 المشنوق — أحسن السلاسل",
                description="📭 مازال حتى واحد مالعب. دير `/hangman`!",
                color=discord.Color.orange(),
            )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, d) in enumerate(ranked):
            m = guild.get_member(int(uid))
            name = m.display_name if m else f"عضو خارج ({uid})"
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} **{name}** — 🔥 {d.get('best_streak', 0)} (فوز {d.get('wins', 0)})")

        return discord.Embed(
            title="🪢 المشنوق — أحسن السلاسل",
            description="\n".join(lines),
            color=discord.Color.orange(),
        )


# ═══════════════════════════════════════════════════════

class CategoryView(discord.ui.View):
    def __init__(self, cog: Hangman, user: discord.abc.User):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user

        options = [
            discord.SelectOption(label=cat, value=cat,
                                 description=f"{len(words)} كلمة")
            for cat, words in cog.bank.items()
        ][:25]
        options.insert(0, discord.SelectOption(
            label="🎲 عشوائي (كاع الفئات)", value="__all__"))

        select = discord.ui.Select(placeholder="📚 اختار الفئة...", options=options)
        select.callback = self.on_pick
        self.add_item(select)
        self.select = select

    async def on_pick(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return

        choice = self.select.values[0]
        if choice == "__all__":
            pool = [w for words in self.cog.bank.values() for w in words]
            label = "🎲 عشوائي"
        else:
            pool = self.cog.bank.get(choice, [])
            label = choice

        if not pool:
            await interaction.response.send_message("❌ ماكايناش كلمات فهاد الفئة.",
                                                    ephemeral=True)
            return

        word = random.choice(pool)
        game = HangmanSession(self.cog, self.user, word, label)
        await interaction.response.edit_message(
            content=None, embed=game.build_embed(), view=game)
        game.message = await interaction.original_response()
        self.cog.active.add((interaction.guild.id, self.user.id))
        game.guild_id = interaction.guild.id
        game.start_listener(interaction.channel)


class HangmanSession(discord.ui.View):
    def __init__(self, cog: Hangman, user: discord.abc.User, word: str, category: str):
        super().__init__(timeout=cfg.HANGMAN_SESSION_SECONDS)
        self.cog = cog
        self.user = user
        self.word = word
        self.norm_word = [normalize(c) for c in word]
        self.category = category
        self.guessed = set()
        self.mistakes = 0
        self.message = None
        self.guild_id = None
        self.finished = False
        self._task = None

    # ═══ العرض ═══

    def masked(self) -> str:
        out = []
        for original, norm in zip(self.word, self.norm_word):
            if norm == " ":
                out.append("  ")
            elif norm in self.guessed:
                out.append(f"**{original}**")
            else:
                out.append("＿")
        return " ".join(out)

    def build_embed(self, result: str = None) -> discord.Embed:
        color = (discord.Color.green() if result == "win"
                 else discord.Color.red() if result == "lose"
                 else discord.Color.orange())

        embed = discord.Embed(title="🪢 المشنوق", color=color)
        embed.description = HANGMAN_STAGES[min(self.mistakes, len(HANGMAN_STAGES) - 1)]
        embed.add_field(name="📝 الكلمة", value=self.masked(), inline=False)
        embed.add_field(name="📚 الفئة", value=self.category, inline=True)
        embed.add_field(name="❤️ المحاولات الباقية",
                        value=f"**{cfg.HANGMAN_MAX_MISTAKES - self.mistakes}**", inline=True)

        wrong = sorted(g for g in self.guessed if g not in self.norm_word)
        if wrong:
            embed.add_field(name="❌ حروف غالطة", value=" ".join(wrong), inline=False)

        if result == "win":
            embed.add_field(name="🎉 مبروك!", value=f"الكلمة كانت **{self.word}**", inline=False)
        elif result == "lose":
            embed.add_field(name="💀 خسرتي", value=f"الكلمة كانت **{self.word}**", inline=False)
        else:
            embed.set_footer(text="كتب حرف واحد فالشات باش تخمّن (ولا الكلمة كاملة)")
        return embed

    # ═══ الاستماع للحروف فالشات ═══

    def start_listener(self, channel):
        self._task = asyncio.create_task(self._listen(channel))

    async def _listen(self, channel):
        def check(m: discord.Message):
            return (m.author.id == self.user.id
                    and m.channel.id == channel.id
                    and len(m.content.strip()) >= 1)

        while not self.finished:
            try:
                msg = await self.cog.bot.wait_for(
                    "message", check=check, timeout=cfg.HANGMAN_SESSION_SECONDS)
            except asyncio.TimeoutError:
                await self.end("lose")
                return

            guess = msg.content.strip()
            try:
                await msg.delete()
            except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                pass

            # ═══ خمّن الكلمة كاملة ═══
            if len(guess) > 1:
                if [normalize(c) for c in guess] == self.norm_word:
                    self.guessed.update(self.norm_word)
                    await self.end("win")
                    return
                self.mistakes += 1
                if self.mistakes >= cfg.HANGMAN_MAX_MISTAKES:
                    await self.end("lose")
                    return
                await self.refresh()
                continue

            # ═══ حرف واحد ═══
            letter = normalize(guess)
            if letter in self.guessed:
                continue
            self.guessed.add(letter)

            if letter not in self.norm_word:
                self.mistakes += 1
                if self.mistakes >= cfg.HANGMAN_MAX_MISTAKES:
                    await self.end("lose")
                    return

            if all(c in self.guessed or c == " " for c in self.norm_word):
                await self.end("win")
                return

            await self.refresh()

    async def refresh(self):
        if self.message:
            try:
                await self.message.edit(embed=self.build_embed(), view=self)
            except discord.HTTPException:
                pass

    async def end(self, result: str):
        if self.finished:
            return
        self.finished = True
        self.stop()

        s = self.cog.stats(self.guild_id, self.user.id)
        coins_line = ""
        if result == "win":
            s["wins"] += 1
            s["streak"] += 1
            s["best_streak"] = max(s["best_streak"], s["streak"])
            eco = self.cog.bot.get_cog("Economy")
            if eco:
                granted = eco.add_coins(self.guild_id, self.user.id,
                                        cfg.COINS_HANGMAN_WIN, source="hangman")
                coins_line = (f"\n{cfg.CURRENCY_EMOJI} +{granted} {cfg.CURRENCY_NAME_PLURAL}"
                              if granted else "\n⚠️ وصلتي للسقف اليومي.")
        else:
            s["losses"] += 1
            s["streak"] = 0
        self.cog.db.save()
        self.cog.active.discard((self.guild_id, self.user.id))

        embed = self.build_embed(result)
        if coins_line:
            embed.add_field(name="💰 الربح", value=coins_line.strip(), inline=False)

        if self.message:
            try:
                await self.message.edit(embed=embed, view=ReplayView(self.cog, self.user))
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        if not self.finished:
            await self.end("lose")


class ReplayView(discord.ui.View):
    def __init__(self, cog: Hangman, user: discord.abc.User):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user

    @discord.ui.button(label="🔄 العب مرة أخرى", style=discord.ButtonStyle.success)
    async def replay(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        await interaction.response.edit_message(
            content="📚 اختار الفئة اللي بغيتي:", embed=None,
            view=CategoryView(self.cog, self.user))


async def setup(bot: commands.Bot):
    await bot.add_cog(Hangman(bot))
