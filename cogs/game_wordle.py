# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_wordle.py — 🔤 Wordle بالدارجة (يومي)      ║
═══════════════════════════════════════════════════════

⭐ هادي **أهم لعبة** فالمجموعة كاملة.

علاش؟ كلشي اللعبات الأخرى كتلعبهم ملي كتمل. Wordle كتلعبها **كل نهار**
فنفس الوقت بحال العادة. هادي هي اللي كتخلي الأعضاء يرجعو للسيرفر.

كلمة وحدة كل نهار للسيرفر كامل، 6 محاولات، والنتيجة كتنشارك بلا spoiler.
"""

import discord
from discord.ext import commands
from discord import app_commands
import hashlib
from datetime import datetime, timezone, timedelta

from storage import JsonStore, load_bank
import games_config as cfg

GREEN = "🟩"
YELLOW = "🟨"
GRAY = "⬜"


def normalize(word: str) -> str:
    mapping = {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
               "ة": "ه", "ى": "ي", "ئ": "ي", "ؤ": "و"}
    return "".join(mapping.get(c, c) for c in word)


def today_key() -> str:
    now = datetime.now(timezone.utc) - timedelta(hours=cfg.WORDLE_RESET_HOUR_UTC)
    return now.strftime("%Y-%m-%d")


class Wordle(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("wordle.json", default={})
        self.words = load_bank("wordle_words.json", default=[])
        # كنفلترو غير الكلمات ديال الطول المطلوب
        self.words = [w for w in self.words
                      if len(normalize(w)) == cfg.WORDLE_WORD_LENGTH]
        self.valid = {normalize(w) for w in self.words}

    def word_of_the_day(self) -> str:
        """نفس الكلمة لكاع السيرفر فنفس النهار — مبنية على hash ديال التاريخ.
        ماشي random عشوائي: باش حتى بعد restart تبقى نفس الكلمة."""
        if not self.words:
            return ""
        h = hashlib.sha256(today_key().encode()).hexdigest()
        index = int(h[:8], 16) % len(self.words)
        return self.words[index]

    def player(self, guild_id: int, user_id: int) -> dict:
        p = self.db.user(guild_id, user_id, default={
            "date": None, "guesses": [], "solved": False,
            "streak": 0, "best_streak": 0, "played": 0, "wins": 0,
        })
        # reset يومي
        if p.get("date") != today_key():
            # إلا فات نهار كامل بلا لعب → الـ streak كيتقطع
            if p.get("date"):
                try:
                    last = datetime.strptime(p["date"], "%Y-%m-%d")
                    today = datetime.strptime(today_key(), "%Y-%m-%d")
                    if (today - last).days > 1:
                        p["streak"] = 0
                except ValueError:
                    pass
            p["date"] = today_key()
            p["guesses"] = []
            p["solved"] = False
        return p

    @staticmethod
    def score(guess: str, answer: str) -> str:
        """خوارزمية Wordle الصحيحة — كتعامل الحروف المكررة مزيان."""
        result = [GRAY] * len(guess)
        answer_chars = list(answer)

        # مرحلة 1: الأخضر
        for i, ch in enumerate(guess):
            if i < len(answer) and ch == answer[i]:
                result[i] = GREEN
                answer_chars[i] = None

        # مرحلة 2: الأصفر
        for i, ch in enumerate(guess):
            if result[i] == GREEN:
                continue
            if ch in answer_chars:
                result[i] = YELLOW
                answer_chars[answer_chars.index(ch)] = None

        return "".join(result)

    # ═══════════════════════════════════════════════════

    @commands.hybrid_command(name="wordle", aliases=["كلمة"],
                             description="لعبة الكلمة اليومية بالدارجة 🔤")
    @app_commands.describe(guess="خمّن كلمة من 5 حروف (خليها فارغة باش تشوف التقدم ديالك)")
    async def wordle_cmd(self, ctx: commands.Context, guess: str = None):
        if not self.words:
            await ctx.send("❌ bank الكلمات خاوي — تأكد من `banks/wordle_words.json`.",
                           ephemeral=True)
            return

        answer = normalize(self.word_of_the_day())
        p = self.player(ctx.guild.id, ctx.author.id)

        # ═══ بلا guess → عرض الحالة ═══
        if not guess:
            await ctx.send(embed=self.build_embed(p, answer, ctx.author), ephemeral=True)
            return

        if p["solved"]:
            await ctx.send("✅ حليتيها اليوم ديجا! رجع غدا لكلمة جديدة.", ephemeral=True)
            return
        if len(p["guesses"]) >= cfg.WORDLE_MAX_ATTEMPTS:
            await ctx.send(f"❌ سالاو المحاولات ديالك اليوم. الكلمة كانت **{self.word_of_the_day()}**",
                           ephemeral=True)
            return

        g = normalize(guess.strip())
        if len(g) != cfg.WORDLE_WORD_LENGTH:
            await ctx.send(f"❌ خاصها تكون **{cfg.WORDLE_WORD_LENGTH}** حروف — نتا كتبتي {len(g)}.",
                           ephemeral=True)
            return
        if g not in self.valid:
            await ctx.send("❌ هاد الكلمة ماكايناش فالقاموس ديالنا. جرب وحدة أخرى.",
                           ephemeral=True)
            return

        pattern = self.score(g, answer)
        p["guesses"].append({"word": g, "pattern": pattern})

        if g == answer:
            p["solved"] = True
            p["wins"] += 1
            p["played"] += 1
            p["streak"] += 1
            p["best_streak"] = max(p["best_streak"], p["streak"])

            eco = self.bot.get_cog("Economy")
            coins = cfg.COINS_WORDLE_WIN
            bonus = min(cfg.COINS_WORDLE_STREAK_BONUS, p["streak"] * 5)
            granted = 0
            if eco:
                granted = eco.add_coins(ctx.guild.id, ctx.author.id,
                                        coins + bonus, source="wordle")
            self.db.save()

            embed = self.build_embed(p, answer, ctx.author, solved=True)
            embed.add_field(
                name="💰 الربح",
                value=(f"{cfg.CURRENCY_EMOJI} **+{granted}** {cfg.CURRENCY_NAME_PLURAL}"
                       + (f" (فيهم +{bonus} بونوس streak)" if bonus else "")),
                inline=False
            )
            await ctx.send(embed=embed, view=ShareView(self, p, ctx.author), ephemeral=True)
            return

        if len(p["guesses"]) >= cfg.WORDLE_MAX_ATTEMPTS:
            p["played"] += 1
            p["streak"] = 0
            self.db.save()
            embed = self.build_embed(p, answer, ctx.author, failed=True)
            await ctx.send(embed=embed, ephemeral=True)
            return

        self.db.save()
        await ctx.send(embed=self.build_embed(p, answer, ctx.author), ephemeral=True)

    def build_embed(self, p: dict, answer: str, user, solved=False, failed=False) -> discord.Embed:
        color = (discord.Color.green() if solved
                 else discord.Color.red() if failed
                 else discord.Color.blurple())
        embed = discord.Embed(title=f"🔤 Wordle — {today_key()}", color=color)

        if p["guesses"]:
            lines = []
            for entry in p["guesses"]:
                letters = " ".join(entry["word"])
                lines.append(f"{entry['pattern']}  `{letters}`")
            embed.description = "\n".join(lines)
        else:
            embed.description = (f"مازال ماخمّنتي والو.\n"
                                 f"دير `/wordle كلمة` باش تبدا — عندك "
                                 f"**{cfg.WORDLE_MAX_ATTEMPTS}** محاولات.")

        remaining = cfg.WORDLE_MAX_ATTEMPTS - len(p["guesses"])
        embed.add_field(name="🎯 المحاولات الباقية", value=f"**{remaining}**", inline=True)
        embed.add_field(name="🔥 Streak", value=f"**{p['streak']}**", inline=True)
        embed.add_field(name="⭐ أحسن Streak", value=f"**{p['best_streak']}**", inline=True)

        if solved:
            embed.add_field(name="🎉 مبروك!",
                            value=f"حليتيها فـ **{len(p['guesses'])}** محاولات!", inline=False)
        elif failed:
            embed.add_field(name="💀 سالاو المحاولات",
                            value=f"الكلمة كانت **{self.word_of_the_day()}**", inline=False)
        else:
            embed.set_footer(text="🟩 الحرف فبلاصتو · 🟨 كاين ولكن ماشي فبلاصتو · ⬜ ماكاينش")
        return embed

    def build_stats_embed(self, guild: discord.Guild, target: discord.Member) -> discord.Embed:
        """كيتسمى من /gamestats wordle"""
        p = self.player(guild.id, target.id)
        rate = (p["wins"] / p["played"] * 100) if p["played"] else 0

        embed = discord.Embed(title=f"🔤 Wordle — {target.display_name}",
                              color=discord.Color.blurple())
        embed.add_field(name="🎮 لعب", value=f"**{p['played']}**", inline=True)
        embed.add_field(name="🏆 ربح", value=f"**{p['wins']}**", inline=True)
        embed.add_field(name="📊 النسبة", value=f"**{rate:.0f}%**", inline=True)
        embed.add_field(name="🔥 Streak حالي", value=f"**{p['streak']}**", inline=True)
        embed.add_field(name="⭐ أحسن Streak", value=f"**{p['best_streak']}**", inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        return embed

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من /gamestats wordletop"""
        guild_data = self.db.guild(guild.id)
        ranked = sorted(guild_data.items(),
                        key=lambda kv: kv[1].get("best_streak", 0), reverse=True)[:10]
        if not ranked:
            return discord.Embed(
                title="🔤 Wordle — أحسن Streaks",
                description="📭 مازال حتى واحد مالعب. كون نتا الأول — `/wordle`!",
                color=discord.Color.blurple())

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, d) in enumerate(ranked):
            m = guild.get_member(int(uid))
            name = m.display_name if m else f"عضو ({uid})"
            prefix = medals[i] if i < 3 else f"`#{i+1}`"
            lines.append(f"{prefix} **{name}** — 🔥 {d.get('best_streak', 0)} "
                         f"(ربح {d.get('wins', 0)})")

        return discord.Embed(title="🔤 Wordle — أحسن Streaks",
                             description="\n".join(lines),
                             color=discord.Color.blurple())


class ShareView(discord.ui.View):
    """زر 'شارك النتيجة' — كينشر الـ pattern بلا الكلمة (بحال Wordle الحقيقي)."""

    def __init__(self, cog: Wordle, p: dict, user: discord.abc.User):
        super().__init__(timeout=300)
        self.cog = cog
        self.p = p
        self.user = user

    @discord.ui.button(label="📤 شارك النتيجة (بلا spoiler)",
                       style=discord.ButtonStyle.primary)
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return

        grid = "\n".join(e["pattern"] for e in self.p["guesses"])
        text = (f"🔤 **Wordle {today_key()}** — {len(self.p['guesses'])}/"
                f"{cfg.WORDLE_MAX_ATTEMPTS}\n"
                f"{interaction.user.mention} 🔥 streak: {self.p['streak']}\n\n{grid}")
        button.disabled = True
        await interaction.response.edit_message(view=self)
        await interaction.channel.send(text)


async def setup(bot: commands.Bot):
    await bot.add_cog(Wordle(bot))
