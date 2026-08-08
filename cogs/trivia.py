# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   cogs/trivia.py — 🧠 Trivia (rewards in GGMW9 USD)       ║
═══════════════════════════════════════════════════════
منقولة من ai_bot.py بتبديل واحد كبير:
❌ ماكاينش XP هنا — ✅ الربح بالدولار GGMW9 (USD)،
   مع احترام السقف اليومي COINS_DAILY_CAP ديال الألعاب.

الاعتماديات:
  • cogs/economy.py  → 💵 USD rewards كتتعطى عبر bot.get_cog("Economy").add_coins()
       (نفس الطريقة ديال باقي الألعاب — سقف يومي واحد وعداد واحد للجميع)
  • games_config.py  → CONFIG ديال Trivia + العملة
  • storage.py       → JsonStore (نفس النظام ديال باقي الـ cogs)
  • trivia_bank.py   → TRIVIA_DARIJA_BANK (فالجذر ديال المشروع)
  • bot.gg["call_openrouter_chat"] → الترجمة للدارجة ديال أسئلة OpenTDB
       (اختيارية — إلا ماكانتش، اللعبة كتخدم غير بالبنك المحلي)

الملفات فالـ Volume (DATA_DIR):
  • trivia_stats.json        → إحصائيات اللعبة (صحيح/جولات/أحسن سلسلة/USD مجموع)
       ⤷ أول مرة كيتحمّل، كيهاجر التاريخ القديم من trivia_scores.json
         و trivia_xp_totals.json أوتوماتيك (بلا ما يمسحهم)
  • trivia_darija_cache.json → نفس كاش الترجمة القديم (كيتعاود استعمالو كيف ما هو)
  ℹ️ economy.json كيبقى ملكية حصرية ديال cogs/economy.py — هاد الـ cog ماكيقيسوش
"""

import os
import json
import html
import random
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks

from storage import JsonStore
from games_config import (
    DATA_DIR,
    CURRENCY_NAME, CURRENCY_NAME_PLURAL, CURRENCY_EMOJI, COINS_DAILY_CAP, fmt_money,
    TRIVIA_ENABLED, TRIVIA_CHANNEL_ID, TRIVIA_AUTO_CHANNEL_IDS,
    TRIVIA_AUTO_INTERVAL_MINUTES, TRIVIA_ANSWER_SECONDS,
    TRIVIA_ROUNDS_PER_DIFFICULTY, TRIVIA_COINS, TRIVIA_SINGLE_COINS,
    TRIVIA_OPENTDB_IDS, TRIVIA_CATEGORIES, TRIVIA_CATEGORY_LABELS,
)
from trivia_bank import TRIVIA_DARIJA_BANK


TRIVIA_DIFFICULTY_LABELS = {
    "easy": "🟢 ساهل",
    "medium": "🟡 متوسط",
    "hard": "🔴 صعيب",
}


def get_trivia_coins(difficulty: str) -> int:
    """Reward بالسنت؛ العرض للمستخدم كيدوز من fmt_money()."""
    return int(TRIVIA_COINS.get(difficulty, TRIVIA_COINS.get("easy", 4)))


def get_trivia_difficulty(round_num: int) -> str:
    if round_num <= TRIVIA_ROUNDS_PER_DIFFICULTY:
        return "easy"
    elif round_num <= TRIVIA_ROUNDS_PER_DIFFICULTY * 2:
        return "medium"
    return "hard"


def count_bank_questions() -> int:
    return sum(len(qs) for diffs in TRIVIA_DARIJA_BANK.values() for qs in diffs.values())


# ═══════════════════════════════════════════════════════
# ║        محرك الأسئلة (بنك دارجة + احتياط OpenTDB)        ║
# ═══════════════════════════════════════════════════════

def build_bank_question(category: str, difficulty: str, used_keys: set) -> Optional[dict]:
    """كيختار سؤال عشوائي بالدارجة من البنك المحلي، بلا ما يعاود شي سؤال تسول ديجا
    فنفس الجلسة. كيخلط ترتيب الأجوبة كل مرة باش ماتحفظش «دايما الأول»."""
    pool = TRIVIA_DARIJA_BANK.get(category, {}).get(difficulty, [])
    available = [
        (i, q) for i, q in enumerate(pool)
        if f"{category}:{difficulty}:{i}" not in used_keys
    ]
    if not available:
        return None

    idx, (question_text, options, correct_idx) = random.choice(available)
    correct = options[correct_idx]
    shuffled = list(options)
    random.shuffle(shuffled)

    return {
        "question": question_text,
        "correct": correct,
        "options": shuffled,
        "category": TRIVIA_CATEGORY_LABELS.get(category, category),
        "difficulty": difficulty,
        "key": f"{category}:{difficulty}:{idx}",
        "source": "bank",
    }


# ═══════ حماية من الـ rate limit ديال OpenTDB ═══════
# OpenTDB كيسمح غير بطلب واحد كل 5 ثواني لكل IP (كيرجع response_code=5 ولا HTTP 429).
# هاد الـ lock كيضمن التباعد بين الطلبات حتى إلا تزامنو بزاف ديال اللاعبين.
_opentdb_lock = asyncio.Lock()
_opentdb_last_call = 0.0
OPENTDB_MIN_INTERVAL = 5.5   # ثواني بين كل طلبين (5 هو الحد الرسمي، زدنا 0.5 احتياط)


async def _fetch_json(url: str, params: dict = None) -> dict:
    """جيب JSON من أي API — نسخة محلية صغيرة باش الـ cog يبقى مستقل."""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
            async with session.get(url, params=params) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json()
                    except Exception as e:
                        print(f"[TRIVIA] JSON decode error من {url}: {e}")
                        return {}
                body = await resp.text()
                print(f"[TRIVIA] {url} رجع status {resp.status}: {body[:200]}")
                return {}
    except asyncio.TimeoutError:
        print(f"[TRIVIA] Timeout فـ {url}")
        return {}
    except Exception as e:
        print(f"[TRIVIA] Exception فـ {url}: {e}")
        return {}


async def opentdb_request(url: str, params: dict) -> dict:
    """كل طلب لـ OpenTDB كيعدا من هنا — مضمون التباعد بيناتهم."""
    global _opentdb_last_call
    async with _opentdb_lock:
        elapsed = asyncio.get_event_loop().time() - _opentdb_last_call
        if elapsed < OPENTDB_MIN_INTERVAL:
            await asyncio.sleep(OPENTDB_MIN_INTERVAL - elapsed)
        data = await _fetch_json(url, params=params)
        _opentdb_last_call = asyncio.get_event_loop().time()
        return data


async def fetch_trivia_question(category: str = None, difficulty: str = None) -> Optional[dict]:
    """جيب سؤال Trivia من OpenTDB (بالإنجليزية). كيرجع None إلا فشل.
    كيتعامل مع code 5 (rate limit → استنى وعاود).
    ℹ️ نظام الـ Session Token القديم تحيد — كان dead code (ماكان كيتستعمل حتى بلاصة)."""
    params = {"amount": 1, "type": "multiple"}
    if category and category in TRIVIA_OPENTDB_IDS:
        params["category"] = TRIVIA_OPENTDB_IDS[category]
    if difficulty in ("easy", "medium", "hard"):
        params["difficulty"] = difficulty

    data = await opentdb_request("https://opentdb.com/api.php", params)
    code = data.get("response_code") if data else None

    if code == 5:   # rate limit → التباعد كيتكفل بيه opentdb_request، غير نعاودو
        print("[TRIVIA] OpenTDB rate limit (code 5) — كنعاود المحاولة...")
        data = await opentdb_request("https://opentdb.com/api.php", params)
        code = data.get("response_code") if data else None

    if not data or code != 0 or not data.get("results"):
        return None

    q = data["results"][0]
    correct = html.unescape(q["correct_answer"])
    options = [html.unescape(a) for a in q["incorrect_answers"]] + [correct]
    random.shuffle(options)

    return {
        "question": html.unescape(q["question"]),
        "correct": correct,
        "options": options,
        "category": html.unescape(q.get("category", "عامة")),
        "difficulty": q.get("difficulty", "medium"),
        "source": "opentdb",
    }


# ═══════════════════════════════════════════════════════
# ║        🧠 سؤال عام فـ channel (أول واحد يجاوب يربح)       ║
# ═══════════════════════════════════════════════════════

class TriviaView(discord.ui.View):
    """أزرار الأجوبة ديال سؤال Trivia العام. أول واحد يكليكي على الجواب الصحيح كيربح USD من اقتصاد GGMW9.
    ماشي Persistent (timeout محدد) حيت كل سؤال مرتبط بمثيل واحد ديال هاد الـ View."""

    def __init__(self, cog: "Trivia", correct_answer: str, options: list, reward: int, timeout_seconds: int):
        super().__init__(timeout=timeout_seconds)
        self.cog = cog
        self.correct_answer = correct_answer
        self.reward = reward
        self.answered_users = set()
        self.winner = None
        self.message: Optional[discord.Message] = None

        for option in options:
            btn = discord.ui.Button(label=option[:80], style=discord.ButtonStyle.secondary)
            btn.callback = self._make_callback(option)
            self.add_item(btn)

    def _make_callback(self, option_text: str):
        async def callback(interaction: discord.Interaction):
            if self.winner:
                await interaction.response.send_message("⏱️ هاد السؤال تسالا ديجا، استنى السؤال الجاي!", ephemeral=True)
                return
            if interaction.user.id in self.answered_users:
                await interaction.response.send_message("❌ درتي جواب ديجا فهاد السؤال — استنى السؤال الجاي.", ephemeral=True)
                return
            self.answered_users.add(interaction.user.id)

            if option_text != self.correct_answer:
                await interaction.response.send_message("❌ جواب غالط، جرب مرة أخرى!", ephemeral=True)
                return

            self.winner = interaction.user
            for child in self.children:
                child.disabled = True
                if isinstance(child, discord.ui.Button) and child.label == self.correct_answer[:80]:
                    child.style = discord.ButtonStyle.success
            self.stop()

            await interaction.response.edit_message(view=self)

            if not interaction.guild:
                await interaction.followup.send(
                    f"🎉 {interaction.user.mention} جاوب صحيح! الجواب هو **{self.correct_answer}**"
                )
                return

            # ═══ 💵 هنا كنعطيو USD (بلاصة XP القديمة) ═══
            real = self.cog.award_coins(interaction.guild.id, interaction.user.id, self.reward, source="trivia")
            self.cog.bump_stats(interaction.guild.id, interaction.user.id, coins=real, correct=1)
            balance = self.cog.get_balance(interaction.guild.id, interaction.user.id)

            cap_note = ""
            if real < self.reward:
                cap_note = f"\n🧢 وصلتي للسقف اليومي ديال Mini Games (**{fmt_money(COINS_DAILY_CAP)}**) — دخل ليك غير **{fmt_money(real)}**."
            await interaction.followup.send(
                f"🎉 {interaction.user.mention} جاوب صحيح! الجواب هو **{self.correct_answer}** "
                f"(+{fmt_money(real)}){cap_note}\n"
                f"💼 الرصيد ديالك دابا: **{fmt_money(balance)}**"
            )

        return callback

    async def on_timeout(self):
        if self.winner or not self.message:
            return
        for child in self.children:
            child.disabled = True
        try:
            await self.message.edit(view=self)
            await self.message.reply(
                f"⏱️ خلص الوقت! حتى واحد ما جاوب صحيح. الجواب الصحيح كان: **{self.correct_answer}**",
                mention_author=False
            )
        except discord.HTTPException:
            pass


# ═══════════════════════════════════════════════════════
# ║   Trivia — جلسة فردية (صعوبة متصاعدة) + panel دائم      ║
# ═══════════════════════════════════════════════════════

def build_trivia_session_embed(question_text: str, options: list, category_label: str, difficulty: str,
                               round_num: int, streak: int, expires_at: datetime,
                               prefix: str = "") -> discord.Embed:
    reward = get_trivia_coins(difficulty)
    letters = ["🇦", "🇧", "🇨", "🇩"]
    options_text = "\n".join(f"{letters[i]} {opt}" for i, opt in enumerate(options))
    embed = discord.Embed(
        title=f"🧠 Trivia — سؤال #{round_num}",
        description=f"{prefix}**{question_text}**\n\n{options_text}",
        color=discord.Color.teal(),
    )
    embed.add_field(name="📚 المجال", value=category_label, inline=True)
    embed.add_field(name="🎯 الصعوبة", value=TRIVIA_DIFFICULTY_LABELS.get(difficulty, difficulty), inline=True)
    embed.add_field(name="🔥 السلسلة", value=f"{streak} صحيح متتالي", inline=True)
    # ⏱️ عدّاد حقيقي كيتحدّث من البوت (Discord ماكيحدّثش <t:R> كل ثانية،
    # علاش كان كيبان مجمد فـ "29") — شوف TriviaSessionView._watchdog
    remaining = max(0, int(round((expires_at - datetime.now()).total_seconds())))
    total = max(TRIVIA_ANSWER_SECONDS, 1)
    filled = max(0, min(6, -(-remaining * 6 // total)))   # ceil(remaining/total * 6)
    bar = "🟩" * filled + "⬛" * (6 - filled)
    warn = " ⚠️" if remaining <= 10 else ""
    embed.add_field(name="⏱️ الوقت", value=f"{bar}\nباقي **{remaining}** ثانية{warn}", inline=True)
    embed.set_footer(text=f"جاوب صحيح تربح +{fmt_money(reward)}")
    return embed


class TriviaReplayView(discord.ui.View):
    """زر 'العب مرة أخرى' فآخر الجلسة — كيرجع لاختيار المجال بلا ما يحتاج العضو يرجع لـ channel."""

    def __init__(self, cog: "Trivia", user: discord.abc.User):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user

    @discord.ui.button(label="🔄 العب مرة أخرى", style=discord.ButtonStyle.success)
    async def replay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ هاد اللعبة ماشي ديالك.", ephemeral=True)
            return
        view = TriviaCategorySelectView(self.cog, self.user)
        await interaction.response.edit_message(
            content="📚 شنو المجال لي بغيتي تلعب فيه؟", embed=None, view=view
        )


class TriviaSessionView(discord.ui.View):
    """جلسة لعب فردية (ephemeral، غير صاحبها كيشوفها): كل ما جاوب صحيح، كيجي سؤال جديد
    أصعب وReward USD أكبر، حتى يغلط ولا يخلص الوقت.

    🇲🇦 الأسئلة كيجيو من البنك المحلي بالدارجة، وإلا سالا المجال كيتكمل من OpenTDB
    مع ترجمة أوتوماتيكية (شوف Trivia.get_darija_question).

    ⏱️ الوقت كيتحسب بـ watchdog يدوي (asyncio.sleep) مربوط بـ self.expires_at الثابتة —
    ماشي بـ discord.py timeout العادي (timeout=None).

    ⚠️ ملاحظة تقنية مهمة: الرسالة ephemeral، وDiscord ماكيسمحش تعدلها بـ message.edit().
    علاش كنحتافظو بآخر Interaction وكنعدلو بـ interaction.edit_original_response() —
    هادشي هو اللي كان خلي شاشة «سالا الوقت» ماكتبانش فالنسخة القديمة."""

    def __init__(self, cog: "Trivia", user: discord.abc.User, category: str, round_num: int, streak: int,
                 question: dict, interaction: discord.Interaction,
                 used_keys: Optional[set] = None,
                 session_coins: int = 0, correct_by_difficulty: Optional[dict] = None,
                 hit_cap: bool = False):
        super().__init__(timeout=None)   # كنعطلو الـ timeout الأوتوماتيكي، وكنديرو واحد يدوي تحت
        self.cog = cog
        self.user = user
        self.category = category
        self.round_num = round_num
        self.streak = streak
        self.interaction = interaction          # ← آخر interaction، بيه كنعدلو الرسالة ephemeral
        self.used_keys = used_keys if used_keys is not None else set()
        self.ended = False
        self.prefix = ""   # السطر الفوقاني (✅ صحيح! +X...) — كيتحفظ باش يبقى بايـن مع تحديثات العدّاد

        # ═══ تتبع الربح USD ديال هاد الجولة (باش نوريوه ملي يخسر) ═══
        self.session_coins = session_coins
        self.correct_by_difficulty = correct_by_difficulty or {"easy": 0, "medium": 0, "hard": 0}
        self.hit_cap = hit_cap   # واش وصل للسقف اليومي فهاد الجولة

        self.question_text = question["question"]
        self.options = list(question["options"])
        self.correct_index = self.options.index(question["correct"])
        self.difficulty = question["difficulty"]
        self.category_label = question.get("category", TRIVIA_CATEGORY_LABELS.get(category, category))
        if question.get("key"):
            self.used_keys.add(question["key"])

        self.expires_at = datetime.now() + timedelta(seconds=TRIVIA_ANSWER_SECONDS)
        self._build_components()
        self._watchdog_task = asyncio.create_task(self._watchdog())

    def build_embed(self, prefix: str = None) -> discord.Embed:
        if prefix is not None:
            self.prefix = prefix
        return build_trivia_session_embed(
            self.question_text, self.options, self.category_label, self.difficulty,
            self.round_num, self.streak, self.expires_at, prefix=self.prefix
        )

    def build_summary(self, title: str, top_text: str, color: discord.Color,
                      guild: Optional[discord.Guild]) -> discord.Embed:
        """ملخص نهاية الجولة — كيبين شحال جمع من USD فهاد اللعبة، التفصيل حسب الصعوبة،
        والمجموع الدائم ديالو من Trivia كامل + الرصيد الحالي."""
        embed = discord.Embed(title=title, description=top_text, color=color)

        # ═══ الربح ديال هاد الجولة ═══
        breakdown = []
        for diff in ("easy", "medium", "hard"):
            n = self.correct_by_difficulty.get(diff, 0)
            if n:
                breakdown.append(f"{TRIVIA_DIFFICULTY_LABELS[diff]} × {n}")
        cap_line = f"\n🧢 وصلتي للسقف اليومي (**{fmt_money(COINS_DAILY_CAP)}**)" if self.hit_cap else ""

        embed.add_field(
            name="💰 ربحتي فهاد الجولة",
            value=(
                f"**+{fmt_money(self.session_coins)}**\n"
                + ("\n".join(breakdown) if breakdown else "*ماجاوبتي على حتى سؤال صحيح*")
                + cap_line
            ),
            inline=True
        )
        embed.add_field(
            name="🎯 النتيجة",
            value=f"**{self.streak}** صحيح متتالي\n📚 {TRIVIA_CATEGORY_LABELS.get(self.category, self.category)}",
            inline=True
        )

        # ═══ المجموع الدائم + الرصيد ═══
        if guild:
            stats = self.cog.finish_game(guild.id, self.user.id, self.streak)
            balance = self.cog.get_balance(guild.id, self.user.id)
            record_line = "\n🏅 **رقم قياسي جديد ديالك!** 🎉" if stats["is_record"] else \
                          f"\n🥇 أحسن سلسلة ديالك: **{stats['best_streak']}**"
            embed.add_field(
                name="🏆 المجموع ديالك من Trivia",
                value=(
                    f"💵 **{fmt_money(stats['coins'])}** مجموعين من Trivia\n"
                    f"✅ **{stats['correct']}** جواب صحيح\n"
                    f"🎮 **{stats['games']}** جولة تلعبات"
                    f"{record_line}\n"
                    f"💼 الرصيد ديالك دابا: **{fmt_money(balance)}**"
                ),
                inline=False
            )

        embed.set_footer(text="كليكي 🔄 باش تعاود من جديد")
        return embed

    async def _watchdog(self):
        """جوج مهام فنفس الوقت:
          1) كيسالي اللعبة بالضبط ملي يخلص الوقت (المنطق الأصلي)
          2) كيحدّث العدّاد فالرسالة كل 5 ثواني — حيت Discord ماكيحدّثش
             الـ timestamps النسبية (<t:R>) كل ثانية، فكان العد كيبان مجمد.
        التحديث كل 5 ثواني (ماشي كل ثانية) باش ما نضربوش rate limit ديال
        Discord ملي كيلعبو بزاف ديال الأعضاء فنفس الوقت."""
        try:
            while not self.ended:
                remaining = (self.expires_at - datetime.now()).total_seconds()
                if remaining <= 0:
                    break
                await asyncio.sleep(min(5, remaining))
                if self.ended:
                    return
                # إلا بقات أقل من ثانية، دوز نيشان لشاشة النهاية بلا تحديث زايد
                if (self.expires_at - datetime.now()).total_seconds() < 1:
                    break
                try:
                    # embed فقط — الأزرار كيبقاو كيف ما هوما
                    await self.interaction.edit_original_response(embed=self.build_embed())
                except (discord.HTTPException, discord.NotFound):
                    pass   # تحديث فيزوال فقط — إلا فشل، اللعبة كتكمل عادي
            if not self.ended:
                await self._end_session_timeout()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[TRIVIA] خطأ فـ watchdog: {e}")

    def _cancel_watchdog(self):
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()

    def _build_components(self):
        self.clear_items()
        letters = ["🇦", "🇧", "🇨", "🇩"]
        for i, option in enumerate(self.options):
            btn = discord.ui.Button(
                label=f"{letters[i]} {option}"[:80],
                style=discord.ButtonStyle.secondary,
                row=i // 2
            )
            btn.callback = self._make_answer_callback(i)
            self.add_item(btn)

    def _disable_and_reveal(self):
        for i, child in enumerate(self.children):
            if isinstance(child, discord.ui.Button):
                child.disabled = True
                if i == self.correct_index:
                    child.style = discord.ButtonStyle.success

    def _make_answer_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ هاد اللعبة ماشي ديالك.", ephemeral=True)
                return
            if self.ended:
                await interaction.response.defer()
                return

            self.ended = True
            self._cancel_watchdog()
            self.stop()
            self.interaction = interaction
            await interaction.response.defer()   # جلب السؤال الجاي (ممكن OpenTDB + ترجمة) ياخد شوية

            # ═══ جواب غالط → سالات اللعبة ═══
            if index != self.correct_index:
                self._disable_and_reveal()
                embed = self.build_summary(
                    title="❌ جواب غالط — سالات اللعبة!",
                    top_text=f"الجواب الصحيح كان: **{self.options[self.correct_index]}**",
                    color=discord.Color.red(),
                    guild=interaction.guild
                )
                await interaction.edit_original_response(embed=embed, view=TriviaReplayView(self.cog, self.user))
                return

            # ═══ جواب صحيح → 💵 USD (بلاصة XP القديمة) ═══
            reward = get_trivia_coins(self.difficulty)
            real = reward
            if interaction.guild:
                real = self.cog.award_coins(interaction.guild.id, interaction.user.id, reward, source="trivia_panel")
                self.cog.bump_stats(interaction.guild.id, interaction.user.id, coins=real, correct=1)
            if real < reward:
                self.hit_cap = True
            self.session_coins += real
            self.correct_by_difficulty[self.difficulty] = self.correct_by_difficulty.get(self.difficulty, 0) + 1

            next_round = self.round_num + 1
            next_streak = self.streak + 1
            next_q = await self.cog.get_darija_question(
                self.category, get_trivia_difficulty(next_round), self.used_keys
            )

            if not next_q:
                self.streak = next_streak
                embed = self.build_summary(
                    title="🎉 صحيح! سالاو الأسئلة ديال هاد المجال",
                    top_text=(
                        f"وصلتي لـ **{next_streak}** سؤال صحيح متتالي وكملتي المجال كامل! 🔥\n"
                        f"جرب مجال آخر باش تكمل تجمع."
                    ),
                    color=discord.Color.gold(),
                    guild=interaction.guild
                )
                await interaction.edit_original_response(embed=embed, view=TriviaReplayView(self.cog, self.user))
                return

            gained_txt = f"✅ صحيح! (+{fmt_money(real)})"
            if real < reward:
                gained_txt += " — 🧢 السقف اليومي"
            new_view = TriviaSessionView(
                self.cog, self.user, self.category, next_round, next_streak, next_q,
                interaction, self.used_keys,
                session_coins=self.session_coins, correct_by_difficulty=self.correct_by_difficulty,
                hit_cap=self.hit_cap
            )
            await interaction.edit_original_response(
                embed=new_view.build_embed(
                    prefix=f"{gained_txt} — مجموعك فهاد الجولة: **{fmt_money(self.session_coins)}**\n\n"
                ),
                view=new_view
            )

        return callback

    async def _end_session_timeout(self):
        self.ended = True
        self.stop()
        funny_lines = [
            "حاول مرة أخرى! ⏱️",
            "معرفتيش لعيبة بحالك 😅 جرب عاود!",
            "الوقت هرب منك هاد المرة، عاود الكرة!",
        ]
        guild = self.interaction.guild if self.interaction else None
        embed = self.build_summary(
            title="⏱️ سالا الوقت!",
            top_text=(
                f"الجواب الصحيح كان: **{self.options[self.correct_index]}**\n\n"
                f"{random.choice(funny_lines)}"
            ),
            color=discord.Color.orange(),
            guild=guild
        )
        try:
            await self.interaction.edit_original_response(embed=embed, view=TriviaReplayView(self.cog, self.user))
        except (discord.HTTPException, discord.NotFound) as e:
            print(f"[TRIVIA] ماقدرتش نعدل رسالة نهاية الوقت: {e}")


class TriviaCategorySelectView(discord.ui.View):
    """Select menu باش يختار المجال قبل ما تبدا الجلسة.
    ⚡ السؤال الأول كيجي من البنك المحلي بالدارجة → فوري، بلا API، بلا rate limit."""

    def __init__(self, cog: "Trivia", user: discord.abc.User):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        select = discord.ui.Select(
            placeholder="📚 اختار المجال لي بغيتي الأسئلة ديالو...",
            min_values=1, max_values=1,
            options=[discord.SelectOption(label=TRIVIA_CATEGORY_LABELS[c], value=c) for c in TRIVIA_CATEGORIES]
        )
        select.callback = self._make_select_callback(select)
        self.add_item(select)

    def _make_select_callback(self, select: discord.ui.Select):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user.id:
                await interaction.response.send_message("❌ هاد الاختيار ماشي ديالك.", ephemeral=True)
                return

            await interaction.response.defer()
            self.stop()

            category = select.values[0]
            used_keys = set()
            q = await self.cog.get_darija_question(category, "easy", used_keys)

            if not q:
                await interaction.edit_original_response(
                    content="❌ ما قدرتش نجيب سؤال دابا، جرب مجال آخر ولا عاود من بعد شوية.",
                    embed=None, view=None
                )
                return

            view = TriviaSessionView(self.cog, self.user, category, 1, 0, q, interaction, used_keys)
            await interaction.edit_original_response(content=None, embed=view.build_embed(), view=view)

        return callback


class TriviaGamePanelView(discord.ui.View):
    """الزر الدائم فـ channel اللعبة. Persistent.
    ⚠️ نفس custom_id القديم — الـ panels لي تصيفطو قبل الترحيل غادي يبقاو خدامين."""

    def __init__(self, cog: "Trivia"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="🎮 ابدأ اللعب", style=discord.ButtonStyle.success, custom_id="trivia_start_game_button")
    async def start_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not TRIVIA_ENABLED:
            await interaction.response.send_message("❌ لعبة Trivia معطلة دابا.", ephemeral=True)
            return
        view = TriviaCategorySelectView(self.cog, interaction.user)
        await interaction.response.send_message("📚 شنو المجال لي بغيتي تلعب فيه؟", view=view, ephemeral=True)


# ═══════════════════════════════════════════════════════
# ║                      الـ Cog                           ║
# ═══════════════════════════════════════════════════════

class Trivia(commands.Cog):
    """🧠 لعبة Trivia بالدارجة — Rewards بالدولار GGMW9 💵"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # إحصائيات اللعبة: {guild: {user: {"correct", "coins", "games", "best_streak"}}}
        self.stats = JsonStore("trivia_stats.json", default={})
        # كاش الترجمة — نفس الملف القديم بالضبط، الترجمات المحفوظة كيتعاود استعمالهم
        self.darija_cache = JsonStore("trivia_darija_cache.json", default={})
        if self.darija_cache.data:
            print(f"✅ تحملو {len(self.darija_cache.data)} ترجمة محفوظة ديال Trivia")

    async def cog_load(self):
        self._migrate_old_stats()
        # تسجيل الـ persistent view باش الزر يخدم حتى من بعد restart
        self.bot.add_view(TriviaGamePanelView(self))
        if TRIVIA_ENABLED and TRIVIA_AUTO_CHANNEL_IDS:
            self.trivia_auto_loop.start()

    async def cog_unload(self):
        self.trivia_auto_loop.cancel()

    # ═══════════════════════════════════════════════════
    # ║   ترحيل الإحصائيات القديمة (مرة وحدة أوتوماتيك)      ║
    # ═══════════════════════════════════════════════════

    def _migrate_old_stats(self):
        """أول مرة كيخدم الـ cog: كيجيب التاريخ من trivia_scores.json (الأجوبة الصحيحة)
        و trivia_xp_totals.json (الجولات + أحسن سلسلة) وكيحطهم فـ trivia_stats.json.
        ⚠️ الـ XP القديم ماكيتهاجرش — Stats ديال USD rewards كيبداو من 0 (نظام جديد).
        الملفات القديمة ماكيتمسحوش (باقيين فالـ Volume إلا حتاجيتيهم)."""
        if self.stats.data:
            return   # ديجا كاينين إحصائيات — الترحيل داز ولا اللعبة جديدة

        migrated_users = 0
        old_scores, old_totals = {}, {}
        try:
            p = os.path.join(DATA_DIR, "trivia_scores.json")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    old_scores = json.load(f)
        except Exception as e:
            print(f"[TRIVIA] ما قدرتش نقرا trivia_scores.json القديم: {e}")
        try:
            p = os.path.join(DATA_DIR, "trivia_xp_totals.json")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    old_totals = json.load(f)
        except Exception as e:
            print(f"[TRIVIA] ما قدرتش نقرا trivia_xp_totals.json القديم: {e}")

        if not old_scores and not old_totals:
            return

        for gid in set(old_scores) | set(old_totals):
            g_scores = old_scores.get(gid, {})
            g_totals = old_totals.get(gid, {})
            for uid in set(g_scores) | set(g_totals):
                entry = g_totals.get(uid, {})
                self.stats.data.setdefault(gid, {})[uid] = {
                    "correct": int(g_scores.get(uid, 0)),
                    "coins": 0,   # USD reward stats جديدة — كتبدأ من الصفر
                    "games": int(entry.get("games", 0)),
                    "best_streak": int(entry.get("best_streak", 0)),
                }
                migrated_users += 1

        if migrated_users:
            self.stats.save()
            print(f"✅ [TRIVIA] تهاجرو الإحصائيات ديال {migrated_users} عضو من النظام القديم")

    # ═══════════════════════════════════════════════════
    # ║   💵 USD — النقطة الوحيدة ديال الربط مع الاقتصاد      ║
    # ═══════════════════════════════════════════════════
    # USD rewards كيتعطاو عبر الـ API الرسمي ديال cogs/economy.py — نفس الطريقة
    # ديال باقي الألعاب (X/O، Wordle...). هو اللي كيتكلف بالسقف اليومي
    # (COINS_DAILY_CAP عبر earned_today) والحفظ فـ economy.json.
    # هاد الـ cog عمرو ماكيقيس economy.json مباشرة — باش ما يكونش تضارب
    # بين جوج نسخ فالذاكرة على نفس الملف.

    def _economy(self):
        return self.bot.get_cog("Economy")

    def award_coins(self, guild_id: int, user_id: int, amount: int,
                    source: str = "trivia") -> int:
        """كيزيد USD cents عبر Economy.add_coins() مع احترام السقف اليومي.
        كيرجع شحال دخل **فعليا** (ممكن أقل من amount إلا وصل للسقف)."""
        eco = self._economy()
        if eco is None:
            print("[TRIVIA] ⚠️ cog Economy ماشي محمّل — ماقدرتش نعطي USD "
                  "(تأكد بلي cogs.economy قبل cogs.trivia فـ GAMES_COGS)")
            return 0
        return eco.add_coins(guild_id, user_id, amount, source=source, respect_cap=True)

    def get_balance(self, guild_id: int, user_id: int) -> int:
        eco = self._economy()
        return eco.get_balance(guild_id, user_id) if eco else 0

    # ═══════════════════════════════════════════════════
    # ║              إحصائيات اللعبة (trivia_stats)          ║
    # ═══════════════════════════════════════════════════

    def _user_stats(self, guild_id: int, user_id: int) -> dict:
        return self.stats.user(guild_id, user_id,
                               {"correct": 0, "coins": 0, "games": 0, "best_streak": 0})

    def bump_stats(self, guild_id: int, user_id: int, coins: int = 0, correct: int = 0):
        u = self._user_stats(guild_id, user_id)
        u["coins"] = int(u.get("coins", 0)) + coins
        u["correct"] = int(u.get("correct", 0)) + correct
        self.stats.save()

    def finish_game(self, guild_id: int, user_id: int, streak: int) -> dict:
        """كيتسجل نهاية جولة: +1 للجولات، وتحديث أحسن سلسلة. كيرجع الإحصائيات الكاملة."""
        u = self._user_stats(guild_id, user_id)
        u["games"] = int(u.get("games", 0)) + 1
        is_record = streak > int(u.get("best_streak", 0))
        if is_record:
            u["best_streak"] = streak
        self.stats.save()
        return {
            "coins": int(u.get("coins", 0)),
            "correct": int(u.get("correct", 0)),
            "games": int(u.get("games", 0)),
            "best_streak": int(u.get("best_streak", 0)),
            "is_record": is_record and streak > 0,
        }

    def build_top_embed(self, guild: discord.Guild) -> discord.Embed:
        """كيتسمى من بانل الـ leaderboards — أكثر الأعضاء جاوبو صحيح فـ Trivia."""
        guild_data = self.stats.guild(guild.id)
        ranked = sorted(
            [(uid, d) for uid, d in guild_data.items() if d.get("correct", 0) > 0],
            key=lambda kv: kv[1].get("correct", 0),
            reverse=True,
        )[:10]

        if not ranked:
            return discord.Embed(
                title="🧠 Trivia — أكثر الأجوبة الصحيحة",
                description="📭 مازال حتى واحد ماجاوب. جرب سؤال Trivia!",
                color=discord.Color.teal(),
            )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, d) in enumerate(ranked):
            m = guild.get_member(int(uid))
            name = m.display_name if m else f"عضو خارج ({uid})"
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(f"{prefix} **{name}** — ✅ {d.get('correct', 0)} (🔥 {d.get('best_streak', 0)})")

        return discord.Embed(
            title="🧠 Trivia — أكثر الأجوبة الصحيحة",
            description="\n".join(lines),
            color=discord.Color.teal(),
        )

    # ═══════════════════════════════════════════════════
    # ║        الترجمة للدارجة (لأسئلة OpenTDB فقط)          ║
    # ═══════════════════════════════════════════════════

    async def translate_question_to_darija(self, question: str, options: list) -> Optional[tuple]:
        """كيترجم السؤال + 4 أجوبة للدارجة المغربية بطلب واحد عبر bot.gg["call_openrouter_chat"].
        كيحفظ النتيجة فـ كاش دائم باش نفس السؤال ماياخدش طلب ثاني أبدا.
        كيرجع (سؤال, [أجوبة]) ولا None (وساعتها اللعبة كتكمل بالبنك المحلي)."""
        cache_key = question.strip()
        cached = self.darija_cache.data.get(cache_key)
        if cached and len(cached.get("options", [])) == 4:
            return cached["question"], cached["options"]

        chat_fn = getattr(self.bot, "gg", {}).get("call_openrouter_chat")
        if chat_fn is None:
            return None   # الترجمة ماشي مربوطة — البنك المحلي كافي

        lines = [f"Q: {question}"] + [f"{chr(65 + i)}: {opt}" for i, opt in enumerate(options)]
        messages = [
            {
                "role": "system",
                "content": (
                    "You translate quiz content into MOROCCAN DARIJA written in Arabic script "
                    "(the everyday spoken Moroccan dialect, NOT Modern Standard Arabic). "
                    "Use natural Darija words like: شنو، شحال، أشمن، فين، علاش، كيفاش، واش، بزاف، دابا. "
                    "Keep proper nouns (names of people, films, games, brands) in their original spelling. "
                    "Reply with EXACTLY 5 lines and nothing else: one line starting with 'Q:' "
                    "then four lines starting with 'A:', 'B:', 'C:', 'D:'. "
                    "No preamble, no explanation, no markdown."
                )
            },
            {"role": "user", "content": "\n".join(lines)}
        ]
        result, error = await chat_fn(messages, 900, 0.3)
        if error or not result:
            print(f"[TRIVIA] فشلت الترجمة للدارجة: {error}")
            return None

        parsed = {}
        for line in result.strip().split("\n"):
            line = line.strip().lstrip("*").strip()
            for key in ("Q", "A", "B", "C", "D"):
                prefix = f"{key}:"
                if line.startswith(prefix) and key not in parsed:
                    parsed[key] = line[len(prefix):].strip()
                    break

        if not all(parsed.get(k) for k in ("Q", "A", "B", "C", "D")):
            print(f"[TRIVIA] الرد ديال الترجمة جا بشكل غير متوقع: {result[:150]}")
            return None

        translated = (parsed["Q"], [parsed["A"], parsed["B"], parsed["C"], parsed["D"]])
        self.darija_cache.data[cache_key] = {"question": translated[0], "options": translated[1]}
        self.darija_cache.save()
        return translated

    async def get_darija_question(self, category: str, difficulty: str, used_keys: set) -> Optional[dict]:
        """المصدر الوحيد ديال الأسئلة فاللعبة — دايما كيرجع سؤال بالدارجة:
          1) كيقلب أولا فـ البنك المحلي (فوري، بلا إنترنت، بلا فلوس)
          2) إلا سالاو أسئلة هاد المجال/الصعوبة، كيجيب من OpenTDB وكيترجمو أوتوماتيك
          3) إلا فشلات الترجمة تاهي، كيرجع لسؤال من البنك حتى لو تعاود
        """
        q = build_bank_question(category, difficulty, used_keys)
        if q:
            return q

        online = await fetch_trivia_question(category, difficulty)
        if online:
            translated = await self.translate_question_to_darija(online["question"], online["options"])
            if translated:
                new_question, new_options = translated
                correct_idx = online["options"].index(online["correct"])
                online["question"] = new_question
                online["options"] = new_options
                online["correct"] = new_options[correct_idx]
                online["category"] = TRIVIA_CATEGORY_LABELS.get(category, online["category"])
                online["key"] = f"otdb:{new_question[:60]}"
                return online

        # آخر حل: نعاودو من البنك (كنمسحو التاريخ ديال هاد المجال/الصعوبة)
        fallback_keys = {k for k in used_keys if not k.startswith(f"{category}:{difficulty}:")}
        return build_bank_question(category, difficulty, fallback_keys)

    # ═══════════════════════════════════════════════════
    # ║                  إرسال سؤال عام                     ║
    # ═══════════════════════════════════════════════════

    async def send_trivia_question(self, channel: discord.abc.Messageable, category: str = None):
        """كتجيب سؤال بالدارجة وتبعثو فـ channel معينة، بـ view ديال الأجوبة.
        مستعملة من الأمر /trivia ومن الـ loop التلقائي."""
        cat = category if category in TRIVIA_CATEGORIES else random.choice(list(TRIVIA_CATEGORIES))
        difficulty = random.choice(["easy", "medium", "medium", "hard"])
        q = await self.get_darija_question(cat, difficulty, set())
        if not q:
            return None

        embed = discord.Embed(
            title="🧠 Trivia — سؤال ثقافة عامة",
            description=f"**{q['question']}**",
            color=discord.Color.teal(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📚 المجال", value=q["category"], inline=True)
        embed.add_field(name="🎯 الصعوبة", value=TRIVIA_DIFFICULTY_LABELS.get(q["difficulty"], q["difficulty"]), inline=True)
        embed.set_footer(
            text=f"عندك {TRIVIA_ANSWER_SECONDS} ثانية — أول واحد يجاوب صحيح ياخد +{fmt_money(TRIVIA_SINGLE_COINS)}"
        )

        view = TriviaView(self, q["correct"], q["options"], TRIVIA_SINGLE_COINS, TRIVIA_ANSWER_SECONDS)
        msg = await channel.send(embed=embed, view=view)
        view.message = msg
        return msg

    # ═══════════════════════════════════════════════════
    # ║                  panel اللعبة                       ║
    # ═══════════════════════════════════════════════════

    async def setup_trivia_panel(self, guild: discord.Guild,
                                 channel: Optional[discord.abc.Messageable] = None,
                                 force: bool = False):
        """Refresh the official Trivia panel in-place; create it only if missing.

        ``force`` is kept for compatibility with the Owner refresh button, but it
        never means "send a duplicate" anymore.
        """
        if channel is None:
            if not TRIVIA_CHANNEL_ID:
                return False
            channel = self.bot.get_channel(TRIVIA_CHANNEL_ID)
        if not channel:
            return False

        embed = discord.Embed(
            title="🧠 مرحبا بيك فـ لعبة Trivia",
            description=f"اختبر معلوماتك وربح **USD** {CURRENCY_EMOJI}! "
                        "كليكي على الزر تحت، اختار المجال لي بغيتي، وابدا تجاوب على الأسئلة.",
            color=discord.Color.teal(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="🎯 كيفاش كتخدم",
            value=(
                "1️⃣ كليكي **🎮 ابدأ اللعب** تحت\n"
                f"2️⃣ اختار المجال لي بغيتي (من {len(TRIVIA_CATEGORIES)} مجالات)\n"
                f"3️⃣ جاوب على الأسئلة — عندك {TRIVIA_ANSWER_SECONDS} ثانية لكل سؤال\n"
                "4️⃣ كل ما جاوبتي صحيح، الأسئلة كتزاد صعوبة والـReward بالدولار كيزيد — حتى تغلط ولا يخلص الوقت!"
            ), inline=False
        )
        embed.add_field(
            name="🇲🇦 كلشي بالدارجة",
            value=(
                f"كاع الأسئلة والأجوبة مكتوبين بالدارجة المغربية من الأصل ({count_bank_questions()} سؤال) — "
                "بلا ترجمة، بلا انتظار، وكيبانو ليك فالحين ملي تختار المجال."
            ), inline=False
        )
        embed.add_field(
            name="💵 Rewards بالدولار",
            value=(
                f"🟢 سهل: **{fmt_money(get_trivia_coins('easy'))}**\n"
                f"🟡 متوسط: **{fmt_money(get_trivia_coins('medium'))}**\n"
                f"🔴 صعيب: **{fmt_money(get_trivia_coins('hard'))}**\n"
                f"(غلطة وحدة كتوقف السلسلة — Daily Mini Games cap هو {fmt_money(COINS_DAILY_CAP)})"
            ), inline=False
        )
        embed.set_footer(text=f"{guild.name} | Trivia Game")

        matches = []
        try:
            async for message in channel.history(limit=40):
                if (
                    message.author == self.bot.user
                    and message.embeds
                    and "Trivia" in (message.embeds[0].title or "")
                ):
                    matches.append(message)
        except discord.Forbidden:
            return False

        try:
            if matches:
                keep = matches[0]
                await keep.edit(embed=embed, view=TriviaGamePanelView(self))
                for extra in matches[1:]:
                    try:
                        await extra.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
            else:
                await channel.send(embed=embed, view=TriviaGamePanelView(self))
            return True
        except discord.HTTPException as e:
            print(f"[TRIVIA] ما قدرتش نحدّث panel: {e}")
            return False

    # ═══════════════════════════════════════════════════
    # ║                    الأوامر                          ║
    # ═══════════════════════════════════════════════════

    @commands.hybrid_command(name="setuptrivia", description="كيصاوب panel لعبة Trivia فالـ channel الحالي (Admin)")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def setuptrivia_cmd(self, ctx: commands.Context):
        """كيصاوب panel لعبة Trivia. إلا TRIVIA_CHANNEL_ID = 0، كيصاوبو فالـ channel
        اللي درتي فيها الأمر — يعني ماعندكش علاش تبدل الـ CONFIG (Admin)"""
        target = self.bot.get_channel(TRIVIA_CHANNEL_ID) if TRIVIA_CHANNEL_ID else ctx.channel
        if not target:
            await ctx.send("❌ ما لقيتش الـ channel ديال Trivia — تأكد من `TRIVIA_CHANNEL_ID`.", delete_after=10)
            return
        ok = await self.setup_trivia_panel(ctx.guild, channel=target, force=True)
        if ok:
            await ctx.send(f"✅ panel لعبة Trivia تصاوب فـ {target.mention}.", delete_after=8)
        else:
            await ctx.send("❌ ما قدرتش نصاوب الـ panel — شوف الصلاحيات ديال البوت فهاد الـ channel.", delete_after=10)

    @commands.hybrid_command(name="trivia", description="لعبة أسئلة ثقافة عامة — جاوب صحيح وربح USD!")
    @app_commands.describe(category="اختياري: فئة السؤال")
    @app_commands.choices(category=[
        app_commands.Choice(name="🌍 ثقافة عامة", value="general"),
        app_commands.Choice(name="🔬 علوم", value="science"),
        app_commands.Choice(name="⚽ رياضة", value="sports"),
        app_commands.Choice(name="📜 تاريخ", value="history"),
        app_commands.Choice(name="🗺️ جغرافيا", value="geography"),
        app_commands.Choice(name="🎬 أفلام", value="movies"),
        app_commands.Choice(name="🎵 موسيقى", value="music"),
        app_commands.Choice(name="🎮 ألعاب فيديو", value="games"),
        app_commands.Choice(name="📺 أنمي ومانغا", value="anime"),
    ])
    async def trivia_cmd(self, ctx: commands.Context, category: Optional[str] = None):
        if not TRIVIA_ENABLED:
            await ctx.send("❌ لعبة Trivia معطلة دابا.", delete_after=6)
            return
        result = await self.send_trivia_question(ctx.channel, category)
        if not result:
            await ctx.send("❌ ما قدرتش نجيب سؤال دابا، جرب مرة أخرى بعد شوية.", delete_after=8)

    @commands.hybrid_command(name="triviatop", aliases=["trivialb"],
                             description="أفضل 10 أعضاء فـ Trivia (الأكثر USD rewards)")
    async def triviatop_cmd(self, ctx: commands.Context):
        if not ctx.guild:
            return
        guild_stats = self.stats.guild(ctx.guild.id)
        if not guild_stats:
            await ctx.send("ماكاين حتى عضو جاوب صحيح فـ Trivia دابا — كون أول واحد بـ `/trivia`!")
            return

        # كنرتبو بـUSD rewards المجموعة (وإلا تعادلو، بعدد الأجوبة الصحيحة)
        ranked = sorted(
            guild_stats.items(),
            key=lambda kv: (int(kv[1].get("coins", 0)), int(kv[1].get("correct", 0))),
            reverse=True
        )[:10]

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (user_id, st) in enumerate(ranked):
            member = ctx.guild.get_member(int(user_id))
            name = member.display_name if member else f"عضو غادر ({user_id})"
            prefix = medals[i] if i < 3 else f"#{i + 1}"
            best = int(st.get("best_streak", 0))
            lines.append(
                f"{prefix} **{name}** — 💵 {fmt_money(int(st.get('coins', 0)))} • ✅ {int(st.get('correct', 0))} صحيح"
                + (f" • 🔥 أحسن سلسلة {best}" if best else "")
            )

        embed = discord.Embed(
            title="🧠 أفضل 10 فـ Trivia",
            description="\n".join(lines),
            color=discord.Color.teal(),
            timestamp=datetime.now()
        )
        # الإحصائيات الشخصية ديال اللي طلب الأمر
        me = self._user_stats(ctx.guild.id, ctx.author.id)
        if me.get("games") or me.get("coins") or me.get("correct"):
            embed.add_field(
                name="👤 أنت",
                value=(
                    f"💵 **{fmt_money(int(me.get('coins', 0)))}** • ✅ **{int(me.get('correct', 0))}** صحيح • "
                    f"🎮 **{int(me.get('games', 0))}** جولة • 🔥 أحسن سلسلة **{int(me.get('best_streak', 0))}**"
                ),
                inline=False
            )
        embed.set_footer(text=f"{ctx.guild.name} | Trivia Leaderboard")
        await ctx.send(embed=embed)

    # ═══════════════════════════════════════════════════
    # ║               الـ loop التلقائي                     ║
    # ═══════════════════════════════════════════════════

    @tasks.loop(minutes=max(TRIVIA_AUTO_INTERVAL_MINUTES, 1))
    async def trivia_auto_loop(self):
        if not TRIVIA_ENABLED or not TRIVIA_AUTO_CHANNEL_IDS:
            return
        for channel_id in TRIVIA_AUTO_CHANNEL_IDS:
            channel = self.bot.get_channel(channel_id)
            if channel:
                try:
                    await self.send_trivia_question(channel)
                except Exception as e:
                    print(f"[TRIVIA] خطأ فـ trivia_auto_loop لـ channel {channel_id}: {e}")

    @trivia_auto_loop.before_loop
    async def before_trivia_auto_loop(self):
        await self.bot.wait_until_ready()

    @trivia_auto_loop.error
    async def trivia_auto_loop_error(self, error):
        print(f"[TRIVIA] خطأ كبير وقف trivia_auto_loop: {error}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Trivia(bot))
