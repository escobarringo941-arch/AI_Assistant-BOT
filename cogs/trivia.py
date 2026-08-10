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
from cogs.panel_registry import upsert_fixed_panel
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


TRIVIA_CATEGORY_I18N = {
    "general": {"darija":"🌍 ثقافة عامة","en":"🌍 General Knowledge","fr":"🌍 Culture générale"},
    "science": {"darija":"🔬 علوم","en":"🔬 Science","fr":"🔬 Sciences"},
    "sports": {"darija":"⚽ رياضة","en":"⚽ Sports","fr":"⚽ Sport"},
    "history": {"darija":"📜 تاريخ","en":"📜 History","fr":"📜 Histoire"},
    "geography": {"darija":"🗺️ جغرافيا","en":"🗺️ Geography","fr":"🗺️ Géographie"},
    "movies": {"darija":"🎬 أفلام","en":"🎬 Movies","fr":"🎬 Films"},
    "music": {"darija":"🎵 موسيقى","en":"🎵 Music","fr":"🎵 Musique"},
    "games": {"darija":"🎮 ألعاب فيديو","en":"🎮 Video Games","fr":"🎮 Jeux vidéo"},
    "anime": {"darija":"📺 أنمي ومانغا","en":"📺 Anime & Manga","fr":"📺 Anime & Manga"},
}


def _tr_lang(lang: str) -> str:
    return lang if lang in {"darija","en","fr"} else "darija"


def _tr(bot: commands.Bot, guild_id: int, user_id: int) -> str:
    getter=(getattr(bot,"gg",{}) or {}).get("get_panel_language")
    if getter:
        try: return _tr_lang(getter(guild_id,user_id))
        except Exception: pass
    return "darija"


def _set_tr(bot: commands.Bot, guild_id: int, user_id: int, lang: str) -> str:
    lang=_tr_lang(lang)
    setter=(getattr(bot,"gg",{}) or {}).get("set_panel_language")
    if setter:
        try: return _tr_lang(setter(guild_id,user_id,lang))
        except Exception: pass
    return lang


def _tri(lang: str, darija: str, en: str, fr: str) -> str:
    return {"darija":darija,"en":en,"fr":fr}[_tr_lang(lang)]


def _trivia_category_label(category: str, lang: str) -> str:
    entry=TRIVIA_CATEGORY_I18N.get(category)
    if entry: return entry.get(_tr_lang(lang),entry["darija"])
    return TRIVIA_CATEGORY_LABELS.get(category,category)


def _trivia_difficulty_label(difficulty: str, lang: str) -> str:
    labels={
        "darija":{"easy":"🟢 ساهل","medium":"🟡 متوسط","hard":"🔴 صعيب"},
        "en":{"easy":"🟢 Easy","medium":"🟡 Medium","hard":"🔴 Hard"},
        "fr":{"easy":"🟢 Facile","medium":"🟡 Moyen","hard":"🔴 Difficile"},
    }
    return labels[_tr_lang(lang)].get(difficulty,difficulty)


async def _fresh_trivia_private(interaction: discord.Interaction, **kwargs):
    """Always create a fresh private response from the fixed Darija public panel."""
    if not interaction.response.is_done():
        return await interaction.response.send_message(ephemeral=True, **kwargs)
    return await interaction.followup.send(ephemeral=True, **kwargs)


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
                               prefix: str = "", lang: str = "darija") -> discord.Embed:
    lang=_tr_lang(lang)
    reward=get_trivia_coins(difficulty)
    letters=["🇦","🇧","🇨","🇩"]
    options_text="\n".join(f"{letters[i]} {opt}" for i,opt in enumerate(options))
    title=_tri(lang,f"🧠 Trivia — سؤال #{round_num}",f"🧠 Trivia — Question #{round_num}",f"🧠 Trivia — Question #{round_num}")
    embed=discord.Embed(title=title,description=f"{prefix}**{question_text}**\n\n{options_text}",color=discord.Color.teal())
    embed.add_field(name=_tri(lang,"📚 المجال","📚 Category","📚 Catégorie"),value=category_label,inline=True)
    embed.add_field(name=_tri(lang,"🎯 الصعوبة","🎯 Difficulty","🎯 Difficulté"),value=_trivia_difficulty_label(difficulty,lang),inline=True)
    embed.add_field(name=_tri(lang,"🔥 السلسلة","🔥 Streak","🔥 Série"),value=_tri(lang,f"{streak} صحيح متتالي",f"{streak} correct in a row",f"{streak} bonnes réponses de suite"),inline=True)
    remaining=max(0,int(round((expires_at-datetime.now()).total_seconds())))
    total=max(TRIVIA_ANSWER_SECONDS,1); filled=max(0,min(6,-(-remaining*6//total))); bar="🟩"*filled+"⬛"*(6-filled); warn=" ⚠️" if remaining<=10 else ""
    embed.add_field(name=_tri(lang,"⏱️ الوقت","⏱️ Time","⏱️ Temps"),value=_tri(lang,f"{bar}\nباقي **{remaining}** ثانية{warn}",f"{bar}\n**{remaining}** seconds left{warn}",f"{bar}\nIl reste **{remaining}** secondes{warn}"),inline=True)
    embed.set_footer(text=_tri(lang,f"جاوب صحيح تربح +{fmt_money(reward)}",f"Correct answer = +{fmt_money(reward)}",f"Bonne réponse = +{fmt_money(reward)}"))
    return embed


def build_trivia_panel_embed(guild: discord.Guild, lang: str = "darija") -> discord.Embed:
    lang=_tr_lang(lang)
    title=_tri(lang,"🧠 مرحبا بيك فـ لعبة Trivia","🧠 Welcome to Trivia","🧠 Bienvenue dans Trivia")
    desc=_tri(
        lang,
        f"اختبر معلوماتك وربح **USD** {CURRENCY_EMOJI}! اختار المجال وبدا تجاوب على الأسئلة.",
        f"Test your knowledge and earn **USD** {CURRENCY_EMOJI}! Pick a category and answer the questions.",
        f"Teste tes connaissances et gagne des **USD** {CURRENCY_EMOJI} ! Choisis une catégorie et réponds aux questions.",
    )
    e=discord.Embed(title=title,description=desc,color=discord.Color.teal(),timestamp=datetime.now())
    e.add_field(
        name=_tri(lang,"🎯 كيفاش كتخدم","🎯 How it works","🎯 Comment ça marche"),
        value=_tri(
            lang,
            f"1️⃣ ضغط **🎮 ابدأ اللعب**\n2️⃣ اختار المجال (من {len(TRIVIA_CATEGORIES)} مجالات)\n3️⃣ عندك {TRIVIA_ANSWER_SECONDS} ثانية لكل سؤال\n4️⃣ كل جواب صحيح كيزيد الصعوبة والمكافأة — الغلطة ولا الوقت كيساليو الجولة.",
            f"1️⃣ Press **🎮 Start Game**\n2️⃣ Pick a category ({len(TRIVIA_CATEGORIES)} available)\n3️⃣ You have {TRIVIA_ANSWER_SECONDS} seconds per question\n4️⃣ Correct answers raise the difficulty and reward; one wrong answer or timeout ends the run.",
            f"1️⃣ Appuie sur **🎮 Commencer**\n2️⃣ Choisis une catégorie ({len(TRIVIA_CATEGORIES)} disponibles)\n3️⃣ Tu as {TRIVIA_ANSWER_SECONDS} secondes par question\n4️⃣ Les bonnes réponses augmentent la difficulté et la récompense ; une erreur ou le temps écoulé termine la partie.",
        ),inline=False,
    )
    e.add_field(
        name=_tri(lang,"🌐 اللغات","🌐 Languages","🌐 Langues"),
        value=_tri(
            lang,
            "🇲🇦 الدارجة هي الأصل. 🇬🇧 الإنجليزية و🇫🇷 الفرنسية كيتعرضو فجلسة خاصة ديالك، والأسئلة حتى هي كتترجم وكتتحفظ مؤقتاً باش مايتعاودش نفس الطلب.",
            "🇲🇦 Darija is the default public language. 🇬🇧 English and 🇫🇷 French run in your private session; questions are localized and cached.",
            "🇲🇦 La darija reste la langue publique par défaut. 🇬🇧 L’anglais et 🇫🇷 le français fonctionnent dans ta session privée ; les questions sont localisées et mises en cache.",
        ),inline=False,
    )
    e.add_field(
        name=_tri(lang,"💵 الجوائز بالدولار","💵 USD Rewards","💵 Récompenses USD"),
        value=(
            f"{_trivia_difficulty_label('easy',lang)}: **{fmt_money(get_trivia_coins('easy'))}**\n"
            f"{_trivia_difficulty_label('medium',lang)}: **{fmt_money(get_trivia_coins('medium'))}**\n"
            f"{_trivia_difficulty_label('hard',lang)}: **{fmt_money(get_trivia_coins('hard'))}**\n"
            + _tri(lang,f"السقف اليومي ديال الألعاب المصغرة: **{fmt_money(COINS_DAILY_CAP)}**",f"Daily Mini Games cap: **{fmt_money(COINS_DAILY_CAP)}**",f"Plafond quotidien Mini Games : **{fmt_money(COINS_DAILY_CAP)}**")
        ),inline=False,
    )
    e.set_footer(text=_tri(lang,f"{guild.name} | تحدي المعلومات • الدارجة هي الواجهة العامة",f"{guild.name} | Trivia • Private English session",f"{guild.name} | Trivia • Session française privée"))
    return e


class TriviaPrivateLanguageSelect(discord.ui.Select):
    def __init__(self,cog:"Trivia",user:discord.abc.User,lang:str="darija",mode:str="home",*,row:int=1):
        self.cog,self.user,self.lang,self.mode=cog,user,_tr_lang(lang),mode
        super().__init__(placeholder="🌐 اللغة / Language / Langue",options=[
            discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦",default=self.lang=="darija"),
            discord.SelectOption(label="English",value="en",emoji="🇬🇧",default=self.lang=="en"),
            discord.SelectOption(label="Français",value="fr",emoji="🇫🇷",default=self.lang=="fr"),
        ],min_values=1,max_values=1,row=row)

    async def callback(self,interaction:discord.Interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_tri(self.lang,"❌ هاد الجلسة ماشي ديالك.","❌ This session isn't yours.","❌ Cette session ne t'appartient pas."),ephemeral=True); return
        lang=_set_tr(self.cog.bot,interaction.guild.id,interaction.user.id,self.values[0])
        if self.mode=="category":
            await interaction.response.edit_message(content=_tri(lang,"📚 اختار المجال لي بغيتي:","📚 Choose a category:","📚 Choisis une catégorie :"),embed=None,view=TriviaCategorySelectView(self.cog,self.user,lang))
        else:
            await interaction.response.edit_message(content=None,embed=build_trivia_panel_embed(interaction.guild,lang),view=TriviaPrivateHomeView(self.cog,self.user,lang))


class TriviaPublicLanguageSelect(discord.ui.Select):
    def __init__(self,cog:"Trivia"):
        self.cog=cog
        super().__init__(placeholder="🌐 اللغة / Language / Langue",options=[
            discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦"),
            discord.SelectOption(label="English",value="en",emoji="🇬🇧"),
            discord.SelectOption(label="Français",value="fr",emoji="🇫🇷"),
        ],min_values=1,max_values=1,custom_id="ggmw9:trivia:language",row=1)

    async def callback(self,interaction:discord.Interaction):
        lang=_set_tr(self.cog.bot,interaction.guild.id,interaction.user.id,self.values[0])
        await _fresh_trivia_private(interaction,embed=build_trivia_panel_embed(interaction.guild,lang),view=TriviaPrivateHomeView(self.cog,interaction.user,lang))


class TriviaPrivateHomeView(discord.ui.View):
    def __init__(self,cog:"Trivia",user:discord.abc.User,lang:str="darija"):
        super().__init__(timeout=1800); self.cog,self.user,self.lang=cog,user,_tr_lang(lang)
        start=discord.ui.Button(label=_tri(self.lang,"🎮 ابدأ اللعب","🎮 Start Game","🎮 Commencer"),style=discord.ButtonStyle.success,row=0)
        start.callback=self.start_game; self.add_item(start)
        self.add_item(TriviaPrivateLanguageSelect(cog,user,self.lang,"home",row=1))

    async def start_game(self,interaction:discord.Interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_tri(self.lang,"❌ هاد الجلسة ماشي ديالك.","❌ This session isn't yours.","❌ Cette session ne t'appartient pas."),ephemeral=True); return
        if not TRIVIA_ENABLED:
            await interaction.response.edit_message(content=_tri(self.lang,"❌ لعبة Trivia معطلة دابا.","❌ Trivia is disabled right now.","❌ Trivia est désactivé pour le moment."),embed=None,view=None); return
        await interaction.response.edit_message(content=_tri(self.lang,"📚 اختار المجال لي بغيتي:","📚 Choose a category:","📚 Choisis une catégorie :"),embed=None,view=TriviaCategorySelectView(self.cog,self.user,self.lang))


class TriviaReplayView(discord.ui.View):
    def __init__(self,cog:"Trivia",user:discord.abc.User,lang:str="darija"):
        super().__init__(timeout=900); self.cog,self.user,self.lang=cog,user,_tr_lang(lang)
        b=discord.ui.Button(label=_tri(self.lang,"🔄 العب مرة أخرى","🔄 Play Again","🔄 Rejouer"),style=discord.ButtonStyle.success,row=0); b.callback=self.replay; self.add_item(b)
        self.add_item(TriviaPrivateLanguageSelect(cog,user,self.lang,"home",row=1))

    async def replay(self,interaction:discord.Interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_tri(self.lang,"❌ هاد اللعبة ماشي ديالك.","❌ This game isn't yours.","❌ Cette partie ne t'appartient pas."),ephemeral=True); return
        await interaction.response.edit_message(content=_tri(self.lang,"📚 اختار المجال لي بغيتي:","📚 Choose a category:","📚 Choisis une catégorie :"),embed=None,view=TriviaCategorySelectView(self.cog,self.user,self.lang))


class TriviaSessionLanguageSelect(discord.ui.Select):
    """Change language inside the SAME active private Trivia message, without resetting the timer."""
    def __init__(self,session:"TriviaSessionView"):
        self.session=session
        super().__init__(placeholder="🌐 اللغة / Language / Langue",options=[
            discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦",default=session.lang=="darija"),
            discord.SelectOption(label="English",value="en",emoji="🇬🇧",default=session.lang=="en"),
            discord.SelectOption(label="Français",value="fr",emoji="🇫🇷",default=session.lang=="fr"),
        ],min_values=1,max_values=1,row=2)

    async def callback(self,interaction:discord.Interaction):
        s=self.session
        if interaction.user.id!=s.user.id:
            await interaction.response.send_message(_tri(s.lang,"❌ هاد اللعبة ماشي ديالك.","❌ This game isn't yours.","❌ Cette partie ne t'appartient pas."),ephemeral=True); return
        if s.ended:
            await interaction.response.defer(); return
        await interaction.response.defer()
        new_lang=_set_tr(s.cog.bot,interaction.guild.id,interaction.user.id,self.values[0])
        payload=await s.cog.localize_question_payload(
            s.base_question_text,s.base_options,s.base_correct,s.category,s.difficulty,new_lang,key=s.question_key
        )
        if s.ended: return
        s.lang=new_lang
        s.question_text=payload["question"]; s.options=list(payload["options"]); s.correct_index=s.options.index(payload["correct"]); s.category_label=_trivia_category_label(s.category,new_lang)
        s._build_components()
        await interaction.edit_original_response(embed=s.build_embed(),view=s)


class TriviaSessionView(discord.ui.View):
    def __init__(self,cog:"Trivia",user:discord.abc.User,category:str,round_num:int,streak:int,question:dict,interaction:discord.Interaction,
                 used_keys:Optional[set]=None,session_coins:int=0,correct_by_difficulty:Optional[dict]=None,hit_cap:bool=False,lang:str="darija"):
        super().__init__(timeout=None)
        self.cog,self.user,self.category,self.round_num,self.streak=cog,user,category,round_num,streak
        self.lang=_tr_lang(lang); self.interaction=interaction; self.used_keys=used_keys if used_keys is not None else set(); self.ended=False; self.prefix=""
        self.session_coins=session_coins; self.correct_by_difficulty=correct_by_difficulty or {"easy":0,"medium":0,"hard":0}; self.hit_cap=hit_cap
        self.question_text=question["question"]; self.options=list(question["options"]); self.correct_index=self.options.index(question["correct"]); self.difficulty=question["difficulty"]
        self.category_label=_trivia_category_label(category,self.lang); self.question_key=question.get("key")
        self.base_question_text=question.get("_base_question",question["question"]); self.base_options=list(question.get("_base_options",question["options"])); self.base_correct=question.get("_base_correct",question["correct"])
        if self.question_key: self.used_keys.add(self.question_key)
        self.expires_at=datetime.now()+timedelta(seconds=TRIVIA_ANSWER_SECONDS)
        self._build_components(); self._watchdog_task=asyncio.create_task(self._watchdog())

    def build_embed(self,prefix:str=None):
        if prefix is not None: self.prefix=prefix
        return build_trivia_session_embed(self.question_text,self.options,self.category_label,self.difficulty,self.round_num,self.streak,self.expires_at,prefix=self.prefix,lang=self.lang)

    def build_summary(self,title:str,top_text:str,color:discord.Color,guild:Optional[discord.Guild]):
        e=discord.Embed(title=title,description=top_text,color=color)
        breakdown=[]
        for diff in ("easy","medium","hard"):
            n=self.correct_by_difficulty.get(diff,0)
            if n: breakdown.append(f"{_trivia_difficulty_label(diff,self.lang)} × {n}")
        cap_line=_tri(self.lang,f"\n🧢 وصلتي للسقف اليومي (**{fmt_money(COINS_DAILY_CAP)}**)",f"\n🧢 Daily cap reached (**{fmt_money(COINS_DAILY_CAP)}**)",f"\n🧢 Plafond quotidien atteint (**{fmt_money(COINS_DAILY_CAP)}**)") if self.hit_cap else ""
        empty=_tri(self.lang,"*ماجاوبتي على حتى سؤال صحيح*","*No correct answers in this run*","*Aucune bonne réponse dans cette partie*")
        e.add_field(name=_tri(self.lang,"💰 ربحتي فهاد الجولة","💰 Run Earnings","💰 Gains de la partie"),value=f"**+{fmt_money(self.session_coins)}**\n"+("\n".join(breakdown) if breakdown else empty)+cap_line,inline=True)
        e.add_field(name=_tri(self.lang,"🎯 النتيجة","🎯 Result","🎯 Résultat"),value=_tri(self.lang,f"**{self.streak}** صحيح متتالي\n📚 {_trivia_category_label(self.category,self.lang)}",f"**{self.streak}** correct in a row\n📚 {_trivia_category_label(self.category,self.lang)}",f"**{self.streak}** bonnes réponses de suite\n📚 {_trivia_category_label(self.category,self.lang)}"),inline=True)
        if guild:
            stats=self.cog.finish_game(guild.id,self.user.id,self.streak); balance=self.cog.get_balance(guild.id,self.user.id)
            record=_tri(self.lang,"\n🏅 **رقم قياسي جديد!** 🎉" if stats["is_record"] else f"\n🥇 أحسن سلسلة: **{stats['best_streak']}**","\n🏅 **New personal record!** 🎉" if stats["is_record"] else f"\n🥇 Best streak: **{stats['best_streak']}**","\n🏅 **Nouveau record personnel !** 🎉" if stats["is_record"] else f"\n🥇 Meilleure série : **{stats['best_streak']}**")
            value=_tri(self.lang,
                f"💵 **{fmt_money(stats['coins'])}** مجموعين من Trivia\n✅ **{stats['correct']}** جواب صحيح\n🎮 **{stats['games']}** جولة{record}\n💼 الرصيد: **{fmt_money(balance)}**",
                f"💵 **{fmt_money(stats['coins'])}** earned from Trivia\n✅ **{stats['correct']}** correct answers\n🎮 **{stats['games']}** games{record}\n💼 Balance: **{fmt_money(balance)}**",
                f"💵 **{fmt_money(stats['coins'])}** gagnés dans Trivia\n✅ **{stats['correct']}** bonnes réponses\n🎮 **{stats['games']}** parties{record}\n💼 Solde : **{fmt_money(balance)}**")
            e.add_field(name=_tri(self.lang,"🏆 المجموع ديالك من تحدي المعلومات","🏆 Your Trivia Totals","🏆 Tes totaux Trivia"),value=value,inline=False)
        e.set_footer(text=_tri(self.lang,"ضغط 🔄 باش تعاود","Press 🔄 to play again","Appuie sur 🔄 pour rejouer")); return e

    async def _watchdog(self):
        try:
            while not self.ended:
                remaining=(self.expires_at-datetime.now()).total_seconds()
                if remaining<=0: break
                await asyncio.sleep(min(5,remaining))
                if self.ended: return
                if (self.expires_at-datetime.now()).total_seconds()<1: break
                try: await self.interaction.edit_original_response(embed=self.build_embed())
                except (discord.HTTPException,discord.NotFound): pass
            if not self.ended: await self._end_session_timeout()
        except asyncio.CancelledError: pass
        except Exception as e: print(f"[TRIVIA] watchdog error: {e}")

    def _cancel_watchdog(self):
        if self._watchdog_task and not self._watchdog_task.done(): self._watchdog_task.cancel()

    def _build_components(self):
        self.clear_items(); letters=["🇦","🇧","🇨","🇩"]
        for i,opt in enumerate(self.options):
            b=discord.ui.Button(label=f"{letters[i]} {opt}"[:80],style=discord.ButtonStyle.secondary,row=i//2); b.callback=self._make_answer_callback(i); self.add_item(b)
        self.add_item(TriviaSessionLanguageSelect(self))

    def _disable_and_reveal(self):
        answer_i=0
        for child in self.children:
            if isinstance(child,discord.ui.Button):
                child.disabled=True
                if answer_i==self.correct_index: child.style=discord.ButtonStyle.success
                answer_i+=1
            elif isinstance(child,discord.ui.Select): child.disabled=True

    def _make_answer_callback(self,index:int):
        async def callback(interaction:discord.Interaction):
            if interaction.user.id!=self.user.id:
                await interaction.response.send_message(_tri(self.lang,"❌ هاد اللعبة ماشي ديالك.","❌ This game isn't yours.","❌ Cette partie ne t'appartient pas."),ephemeral=True); return
            if self.ended: await interaction.response.defer(); return
            self.ended=True; self._cancel_watchdog(); self.stop(); self.interaction=interaction; await interaction.response.defer()
            if index!=self.correct_index:
                self._disable_and_reveal(); embed=self.build_summary(
                    _tri(self.lang,"❌ جواب غالط — سالات اللعبة!","❌ Wrong answer — run over!","❌ Mauvaise réponse — partie terminée !"),
                    _tri(self.lang,f"الجواب الصحيح كان: **{self.options[self.correct_index]}**",f"The correct answer was: **{self.options[self.correct_index]}**",f"La bonne réponse était : **{self.options[self.correct_index]}**"),
                    discord.Color.red(),interaction.guild)
                await interaction.edit_original_response(embed=embed,view=TriviaReplayView(self.cog,self.user,self.lang)); return
            reward=get_trivia_coins(self.difficulty); real=reward
            if interaction.guild:
                real=self.cog.award_coins(interaction.guild.id,interaction.user.id,reward,source="trivia_panel"); self.cog.bump_stats(interaction.guild.id,interaction.user.id,coins=real,correct=1)
            if real<reward: self.hit_cap=True
            self.session_coins+=real; self.correct_by_difficulty[self.difficulty]=self.correct_by_difficulty.get(self.difficulty,0)+1
            next_round=self.round_num+1; next_streak=self.streak+1
            next_q=await self.cog.get_question_for_language(self.category,get_trivia_difficulty(next_round),self.used_keys,self.lang)
            if not next_q:
                self.streak=next_streak; embed=self.build_summary(
                    _tri(self.lang,"🎉 صحيح! سالاو الأسئلة ديال هاد المجال","🎉 Correct! Category completed","🎉 Bonne réponse ! Catégorie terminée"),
                    _tri(self.lang,f"وصلتي لـ **{next_streak}** صحيح متتالي وكملتي المجال! 🔥",f"You reached **{next_streak}** correct answers in a row and completed the category! 🔥",f"Tu as atteint **{next_streak}** bonnes réponses de suite et terminé la catégorie ! 🔥"),
                    discord.Color.gold(),interaction.guild)
                await interaction.edit_original_response(embed=embed,view=TriviaReplayView(self.cog,self.user,self.lang)); return
            gained=_tri(self.lang,f"✅ صحيح! (+{fmt_money(real)})",f"✅ Correct! (+{fmt_money(real)})",f"✅ Bonne réponse ! (+{fmt_money(real)})")
            if real<reward: gained+=_tri(self.lang," — 🧢 السقف اليومي"," — 🧢 daily cap"," — 🧢 plafond quotidien")
            new_view=TriviaSessionView(self.cog,self.user,self.category,next_round,next_streak,next_q,interaction,self.used_keys,session_coins=self.session_coins,correct_by_difficulty=self.correct_by_difficulty,hit_cap=self.hit_cap,lang=self.lang)
            prefix=_tri(self.lang,f"{gained} — مجموع الجولة: **{fmt_money(self.session_coins)}**\n\n",f"{gained} — Run total: **{fmt_money(self.session_coins)}**\n\n",f"{gained} — Total de la partie : **{fmt_money(self.session_coins)}**\n\n")
            await interaction.edit_original_response(embed=new_view.build_embed(prefix=prefix),view=new_view)
        return callback

    async def _end_session_timeout(self):
        self.ended=True; self.stop(); guild=self.interaction.guild if self.interaction else None
        top=_tri(self.lang,f"الجواب الصحيح كان: **{self.options[self.correct_index]}**\n\nالوقت هرب منك، جرب عاود!",f"The correct answer was: **{self.options[self.correct_index]}**\n\nTime ran out — try again!",f"La bonne réponse était : **{self.options[self.correct_index]}**\n\nLe temps est écoulé — réessaie !")
        embed=self.build_summary(_tri(self.lang,"⏱️ سالا الوقت!","⏱️ Time's up!","⏱️ Temps écoulé !"),top,discord.Color.orange(),guild)
        try: await self.interaction.edit_original_response(embed=embed,view=TriviaReplayView(self.cog,self.user,self.lang))
        except (discord.HTTPException,discord.NotFound) as e: print(f"[TRIVIA] timeout edit failed: {e}")


class TriviaCategorySelectView(discord.ui.View):
    def __init__(self,cog:"Trivia",user:discord.abc.User,lang:str="darija"):
        super().__init__(timeout=900); self.cog,self.user,self.lang=cog,user,_tr_lang(lang)
        select=discord.ui.Select(placeholder=_tri(self.lang,"📚 اختار المجال...","📚 Choose a category...","📚 Choisis une catégorie..."),min_values=1,max_values=1,options=[discord.SelectOption(label=_trivia_category_label(c,self.lang)[:100],value=c) for c in TRIVIA_CATEGORIES],row=0)
        select.callback=self._select; self.select=select; self.add_item(select)
        back=discord.ui.Button(label=_tri(self.lang,"↩️ رجع","↩️ Back","↩️ Retour"),style=discord.ButtonStyle.secondary,row=1); back.callback=self._back; self.add_item(back)
        self.add_item(TriviaPrivateLanguageSelect(cog,user,self.lang,"category",row=2))

    async def _back(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_tri(self.lang,"❌ هاد الجلسة ماشي ديالك.","❌ This session isn't yours.","❌ Cette session ne t'appartient pas."),ephemeral=True); return
        await interaction.response.edit_message(content=None,embed=build_trivia_panel_embed(interaction.guild,self.lang),view=TriviaPrivateHomeView(self.cog,self.user,self.lang))

    async def _select(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_tri(self.lang,"❌ هاد الاختيار ماشي ديالك.","❌ This selection isn't yours.","❌ Ce choix ne t'appartient pas."),ephemeral=True); return
        await interaction.response.defer(); category=self.select.values[0]; used=set(); q=await self.cog.get_question_for_language(category,"easy",used,self.lang)
        if not q:
            await interaction.edit_original_response(content=_tri(self.lang,"❌ ما قدرتش نجيب سؤال دابا. جرب عاود.","❌ I couldn't load a question. Try again.","❌ Impossible de charger une question. Réessaie."),embed=None,view=TriviaCategorySelectView(self.cog,self.user,self.lang)); return
        view=TriviaSessionView(self.cog,self.user,category,1,0,q,interaction,used,lang=self.lang); await interaction.edit_original_response(content=None,embed=view.build_embed(),view=view)


class TriviaGamePanelView(discord.ui.View):
    """Fixed public Darija Trivia panel. Language choices always open a fresh private session."""
    def __init__(self,cog:"Trivia"):
        super().__init__(timeout=None); self.cog=cog
        start=discord.ui.Button(label="🎮 ابدأ اللعب",style=discord.ButtonStyle.success,custom_id="trivia_start_game_button",row=0); start.callback=self.start_btn; self.add_item(start)
        self.add_item(TriviaPublicLanguageSelect(cog))

    async def start_btn(self,interaction:discord.Interaction):
        if not TRIVIA_ENABLED:
            await interaction.response.send_message("❌ لعبة Trivia معطلة دابا.",ephemeral=True); return
        # Original public button is intentionally Darija.
        _set_tr(self.cog.bot,interaction.guild.id,interaction.user.id,"darija")
        await _fresh_trivia_private(interaction,content="📚 اختار المجال لي بغيتي:",view=TriviaCategorySelectView(self.cog,interaction.user,"darija"))


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
        self.language_cache = JsonStore("trivia_language_cache.json", default={})
        if self.darija_cache.data:
            print(f"✅ تحملو {len(self.darija_cache.data)} ترجمة محفوظة ديال Trivia")
        if self.language_cache.data:
            print(f"✅ [TRIVIA] loaded {len(self.language_cache.data)} EN/FR cached question translations")

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

    def build_top_embed(self, guild: discord.Guild, lang: str = "darija") -> discord.Embed:
        lang=_tr_lang(lang); guild_data=self.stats.guild(guild.id)
        ranked=sorted([(uid,d) for uid,d in guild_data.items() if d.get("correct",0)>0],key=lambda kv:kv[1].get("correct",0),reverse=True)[:10]
        title=_tri(lang,"🧠 Trivia — أكثر الأجوبة الصحيحة","🧠 Trivia — Most Correct Answers","🧠 Trivia — Plus de bonnes réponses")
        if not ranked:
            return discord.Embed(title=title,description=_tri(lang,"📭 مازال حتى واحد ماجاوب.","📭 No results yet.","📭 Aucun résultat pour le moment."),color=discord.Color.teal())
        medals=["🥇","🥈","🥉"]; lines=[]
        for i,(uid,d) in enumerate(ranked):
            m=guild.get_member(int(uid)); name=m.display_name if m else _tri(lang,f"عضو خارج ({uid})",f"Former member ({uid})",f"Ancien membre ({uid})"); prefix=medals[i] if i<3 else f"`#{i+1}`"
            lines.append(f"{prefix} **{name}** — ✅ {d.get('correct',0)} (🔥 {d.get('best_streak',0)})")
        return discord.Embed(title=title,description="\n".join(lines),color=discord.Color.teal())

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


    async def translate_darija_question(self, question: str, options: list, lang: str) -> Optional[tuple]:
        """Translate one Darija question to EN/FR once, then keep it in a persistent cache."""
        lang=_tr_lang(lang)
        if lang=="darija": return question,list(options)
        cache_key=f"{lang}|{question.strip()}|"+"¦".join(str(x) for x in options)
        cached=self.language_cache.data.get(cache_key)
        if cached and len(cached.get("options",[]))==4:
            return cached.get("question",question),list(cached["options"])
        chat_fn=(getattr(self.bot,"gg",{}) or {}).get("call_openrouter_chat")
        if not chat_fn: return None
        target="natural English" if lang=="en" else "natural French"
        lines=[f"Q: {question}"]+[f"{chr(65+i)}: {opt}" for i,opt in enumerate(options)]
        messages=[{"role":"system","content":(
            f"Translate this quiz into {target}. Keep the meaning and difficulty exactly the same. "
            "Keep proper names/brands accurate. Reply with EXACTLY 5 lines: Q:, A:, B:, C:, D:. "
            "No markdown, explanations, or extra text.")},{"role":"user","content":"\n".join(lines)}]
        result,error=await chat_fn(messages,900,0.2)
        if error or not result:
            print(f"[TRIVIA] {lang} translation failed: {error}"); return None
        parsed={}
        for line in result.strip().splitlines():
            clean=line.strip().lstrip("*").strip()
            for key in ("Q","A","B","C","D"):
                pref=f"{key}:"
                if clean.startswith(pref) and key not in parsed:
                    parsed[key]=clean[len(pref):].strip(); break
        if not all(parsed.get(k) for k in ("Q","A","B","C","D")):
            print(f"[TRIVIA] malformed {lang} translation: {result[:180]}"); return None
        translated=(parsed["Q"],[parsed["A"],parsed["B"],parsed["C"],parsed["D"]])
        self.language_cache.data[cache_key]={"question":translated[0],"options":translated[1]}; self.language_cache.save(); return translated

    async def localize_question_payload(self, base_question: str, base_options: list, base_correct: str,
                                        category: str, difficulty: str, lang: str, key: str = None) -> dict:
        lang=_tr_lang(lang); options=list(base_options); question=base_question; correct=base_correct
        if lang in {"en","fr"}:
            translated=await self.translate_darija_question(base_question,options,lang)
            if translated:
                correct_idx=options.index(base_correct)
                question,new_options=translated; options=list(new_options); correct=options[correct_idx]
        return {"question":question,"options":options,"correct":correct,"category":_trivia_category_label(category,lang),"difficulty":difficulty,"key":key,
                "_base_question":base_question,"_base_options":list(base_options),"_base_correct":base_correct}

    async def get_question_for_language(self, category: str, difficulty: str, used_keys: set, lang: str) -> Optional[dict]:
        base=await self.get_darija_question(category,difficulty,used_keys)
        if not base: return None
        return await self.localize_question_payload(base["question"],list(base["options"]),base["correct"],category,difficulty,lang,key=base.get("key"))

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

        embed = build_trivia_panel_embed(guild, "darija")

        message = await upsert_fixed_panel(
            self.bot,
            channel,
            key="trivia",
            matches=lambda message: (
                message.author == self.bot.user
                and bool(message.embeds)
                and (message.embeds[0].title or "") in {
                    "🧠 مرحبا بيك فـ لعبة Trivia",
                    "🧠 Welcome to Trivia",
                    "🧠 Bienvenue dans Trivia",
                }
            ),
            embed=embed,
            view=TriviaGamePanelView(self),
            history_limit=None,
        )
        if message is None:
            print("[TRIVIA] ما قدرتش نحدّث panel دابا.")
        return message is not None

    # ═══════════════════════════════════════════════════
    # ║                    الأوامر                          ║
    # ═══════════════════════════════════════════════════

    @commands.hybrid_command(name="setuptrivia", description="كيصاوب panel لعبة Trivia فالـ channel الحالي (Admin)")
    @app_commands.default_permissions(manage_channels=True)
    @commands.has_permissions(manage_channels=True)
    async def setuptrivia_cmd(self, ctx: commands.Context):
        """كيصاوب panel لعبة Trivia. إلا TRIVIA_CHANNEL_ID = 0، كيصاوبو فالـ channel
        اللي درتي فيها الأمر — يعني ماعندكش علاش تبدل الـ CONFIG (Admin)"""
        gg = getattr(self.bot, "gg", {}) or {}
        admin_role_id = int(gg.get("ADMIN_ROLE_ID") or 0)
        if not (
            ctx.author.id == ctx.guild.owner_id
            or any(role.id == admin_role_id for role in ctx.author.roles)
        ):
            await ctx.send("❌ هاد الأمر خاص غير بـ Owner والـ Admin.", delete_after=6)
            return
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
