# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/game_counting.py — 🔢 قناة العدّاد               ║
═══════════════════════════════════════════════════════

أبسط لعبة فالمشروع، وأكثر وحدة كتخلق إدمان.
الأعضاء كيعدّو 1، 2، 3... فـ channel مخصص. إلا غلط شي حد كيرجع لـ 1.

⚠️ ملاحظة تقنية مهمة:
   هاد الـ cog كيستعمل listener `on_message` **ديالو بوحدو**.
   discord.py كيسمح بعدة listeners لنفس الحدث — يعني `on_message` اللي
   فـ ai_bot.py كيبقى خدّام عادي. ماكاين حتى تعارض.
"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

from storage import JsonStore
import games_config as cfg


class Counting(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("counting.json", default={})

    def _state(self, guild_id: int) -> dict:
        g = self.db.data.setdefault(str(guild_id), {})
        g.setdefault("current", 0)
        g.setdefault("last_user", None)
        g.setdefault("record", 0)
        g.setdefault("record_date", None)
        g.setdefault("contributors", {})
        return g

    # ═══════════════════════════════════════════════════

    @commands.Cog.listener("on_message")
    async def counting_listener(self, message: discord.Message):
        if not cfg.COUNTING_ENABLED:
            return
        if message.author.bot or not message.guild:
            return
        if not cfg.COUNTING_CHANNEL_ID or message.channel.id != cfg.COUNTING_CHANNEL_ID:
            return

        content = message.content.strip()
        # كنقبلو غير الأرقام الصافية (باش الناس تقدر تهضر بلا ما تكسّر اللعبة؟ لا —
        # فـ channel ديال العدّاد كلشي خاصو يكون رقم. الرسائل الأخرى كنتجاهلوها.)
        if not content.isdigit():
            return

        number = int(content)
        state = self._state(message.guild.id)
        expected = state["current"] + 1

        # ═══ نفس العضو مرتين متتاليتين ═══
        if (not cfg.COUNTING_SAME_USER_TWICE
                and state["last_user"] == message.author.id
                and state["current"] > 0):
            await self._fail(message, state,
                             f"ماتقدرش تعدّ مرتين متتاليتين! رجعنا لـ **1**")
            return

        # ═══ رقم غالط ═══
        if number != expected:
            await self._fail(message, state,
                             f"الرقم غالط — كان خاصو يكون **{expected}**. رجعنا لـ **1**")
            return

        # ═══ رقم صحيح ═══
        state["current"] = number
        state["last_user"] = message.author.id
        contributors = state["contributors"]
        uid = str(message.author.id)
        contributors[uid] = contributors.get(uid, 0) + 1

        if number > state["record"]:
            state["record"] = number
            state["record_date"] = datetime.now().isoformat()

        self.db.save()

        try:
            await message.add_reaction("✅")
        except discord.HTTPException:
            pass

        # ═══ Milestone كل 100 ═══
        if cfg.COUNTING_MILESTONE_EVERY and number % cfg.COUNTING_MILESTONE_EVERY == 0:
            await self._milestone(message, state, number)

    async def _fail(self, message: discord.Message, state: dict, reason: str):
        reached = state["current"]
        state["current"] = 0
        state["last_user"] = None
        self.db.save()

        try:
            await message.add_reaction("❌")
        except discord.HTTPException:
            pass

        if cfg.COUNTING_DELETE_WRONG:
            try:
                await message.delete()
            except (discord.Forbidden, discord.NotFound):
                pass

        embed = discord.Embed(
            title="💥 تكسّر العدّاد!",
            description=f"{message.author.mention} {reason}",
            color=discord.Color.red()
        )
        embed.add_field(name="📉 وصلنا لـ", value=f"**{reached}**", inline=True)
        embed.add_field(name="🏆 الريكورد", value=f"**{state['record']}**", inline=True)
        embed.set_footer(text="بدا من 1 — الله يعاون")
        await message.channel.send(embed=embed, delete_after=20)

    async def _milestone(self, message: discord.Message, state: dict, number: int):
        eco = self.bot.get_cog("Economy")
        rewarded = []
        if eco:
            # كنكافؤو غير اللي شاركو فهاد المية الأخيرة (الحاليين فالـ contributors)
            top = sorted(state["contributors"].items(), key=lambda kv: kv[1], reverse=True)[:10]
            for uid, _count in top:
                granted = eco.add_coins(message.guild.id, int(uid),
                                        cfg.COINS_COUNTING_MILESTONE, source="counting")
                if granted > 0:
                    rewarded.append(f"<@{uid}>")

        embed = discord.Embed(
            title=f"🎉 وصلنا لـ {number}!",
            description="مبروك عليكم كاملين 👏",
            color=discord.Color.gold()
        )
        if rewarded:
            embed.add_field(
                name=f"{cfg.CURRENCY_EMOJI} +{cfg.COINS_COUNTING_MILESTONE} لكل واحد",
                value=" ".join(rewarded[:10]),
                inline=False
            )
        embed.add_field(name="🏆 الريكورد", value=f"**{state['record']}**", inline=True)
        await message.channel.send(embed=embed)

    # ═══════════════════════════════════════════════════
    # ║                     الأوامر                        ║
    # ═══════════════════════════════════════════════════

    def build_status_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من /gamestats counting"""
        state = self._state(guild.id)

        embed = discord.Embed(
            title="🔢 العدّاد",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📍 الرقم الحالي", value=f"**{state['current']}**", inline=True)
        embed.add_field(name="➡️ الجاي", value=f"**{state['current'] + 1}**", inline=True)
        embed.add_field(name="🏆 الريكورد", value=f"**{state['record']}**", inline=True)

        if state["last_user"]:
            embed.add_field(name="👤 آخر واحد عدّ",
                            value=f"<@{state['last_user']}>", inline=False)

        top = sorted(state["contributors"].items(), key=lambda kv: kv[1], reverse=True)[:5]
        if top:
            lines = [f"`#{i+1}` <@{uid}> — **{c}** رقم" for i, (uid, c) in enumerate(top)]
            embed.add_field(name="🥇 أكثر اللي عدّو", value="\n".join(lines), inline=False)

        if cfg.COUNTING_CHANNEL_ID:
            # ملاحظة: mentions ديال القنوات (<#id>) ماكيتـرندراوش فالـ footer،
            # علاش كنحطوها فالـ description باش تبان كرابط قابل للكليك
            embed.description = f"العب فـ <#{cfg.COUNTING_CHANNEL_ID}> — كتب الرقم الجاي وصافي!"
        return embed

    @commands.hybrid_command(name="counting",
                             description="🔢 شوف حالة العدّاد: الرقم الحالي، الريكورد، وأحسن اللي عدّو")
    async def counting_cmd(self, ctx: commands.Context):
        """كيوري فين وصل العدّاد وشكون أكثر واحد عدّ — وفين كتلعب اللعبة."""
        if not ctx.guild:
            return
        await ctx.send(embed=self.build_status_embed(ctx.guild))

    def admin_reset(self, guild: discord.Guild) -> str:
        """كيتسمى من /gamesadmin resetcounting"""
        state = self._state(guild.id)
        state["current"] = 0
        state["last_user"] = None
        self.db.save()
        return "✅ العدّاد رجع لـ **0**. الريكورد مازال محفوظ."


async def setup(bot: commands.Bot):
    await bot.add_cog(Counting(bot))
