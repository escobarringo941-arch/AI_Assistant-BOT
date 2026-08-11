# -*- coding: utf-8 -*-
"""Bot construction and unchanged base configuration."""

from cogs._component_runtime import bootstrap_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    import os
    import sys
    import discord
    import aiohttp
    import random
    import asyncio
    import json
    import re
    import io
    import math
    import html
    from typing import Optional
    from datetime import datetime, timedelta
    from discord.ext import commands, tasks
    from discord import app_commands
    from collections import defaultdict
    import games_config as cfg
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
    
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
        PIL_AVAILABLE = True
    except ImportError:
        PIL_AVAILABLE = False
        print("⚠️ Pillow ماشي مثبت — Welcome Cards (الصور) غادي تكون معطلة. دير: pip install Pillow")
    
    # ═══════ باش print() يطلع مباشرة فـ logs (Railway/containers كيعملو buffer) ═══════
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    
    # ═══════════════════════════════════════════════════════
    # ║                    CONFIG سهل التعديل                  ║
    # ═══════════════════════════════════════════════════════
    
    # ═══════ مجلد التخزين الدائم (Railway Volume) ═══════
    # لازم يكون مطابق تماماً للـ Mount Path اللي حطيتي فـ Railway → Volumes.
    DATA_DIR = "/app/data"
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # ═══════ Public Panels — fixed Darija + fresh private language sessions ═══════
    # Public messages stay Darija. A language choice ALWAYS opens a fresh ephemeral panel; private selectors edit that same ephemeral message.
    PANEL_LANGUAGES_FILE = os.path.join(DATA_DIR, "panel_languages.json")
    PANEL_LANGUAGES = {}
    try:
        if os.path.exists(PANEL_LANGUAGES_FILE):
            with open(PANEL_LANGUAGES_FILE, "r", encoding="utf-8") as _f:
                _loaded_panel_langs = json.load(_f)
                if isinstance(_loaded_panel_langs, dict):
                    PANEL_LANGUAGES = _loaded_panel_langs
    except Exception as _e:
        print(f"[PANEL-LANG] load failed: {_e}")
    
    
    def _panel_lang_key(guild_id: int, user_id: int) -> str:
        return f"{int(guild_id or 0)}:{int(user_id)}"
    
    
    def get_panel_language(guild_id: int, user_id: int) -> str:
        lang = str(PANEL_LANGUAGES.get(_panel_lang_key(guild_id, user_id), "darija") or "darija").lower()
        return lang if lang in {"darija", "en", "fr"} else "darija"
    
    
    def set_panel_language(guild_id: int, user_id: int, lang: str) -> str:
        lang = str(lang or "darija").lower()
        if lang not in {"darija", "en", "fr"}:
            lang = "darija"
        PANEL_LANGUAGES[_panel_lang_key(guild_id, user_id)] = lang
        try:
            with open(PANEL_LANGUAGES_FILE, "w", encoding="utf-8") as _f:
                json.dump(PANEL_LANGUAGES, _f, ensure_ascii=False, indent=2)
        except Exception as _e:
            print(f"[PANEL-LANG] save failed: {_e}")
        return lang
    
    
    async def upsert_ephemeral_panel(
        interaction: discord.Interaction,
        session_key: str,
        *,
        content=None,
        embed=None,
        embeds=None,
        view=None,
    ):
        """One private panel message per guild+user+session.
    
        Public buttons never pile ephemeral messages: a later click edits the previous
        private panel when Discord's webhook token is still valid, otherwise it safely
        creates a fresh one. Submenus can keep using interaction.response.edit_message.
        """
        if not hasattr(bot, "_ggmw9_panel_sessions"):
            bot._ggmw9_panel_sessions = {}
        guild_id = interaction.guild.id if interaction.guild else 0
        key = (int(guild_id), int(interaction.user.id), str(session_key))
        sessions = bot._ggmw9_panel_sessions
    
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)
    
        kwargs = {"content": content, "view": view}
        if embeds is not None:
            kwargs["embeds"] = embeds
        elif embed is not None:
            kwargs["embed"] = embed
        else:
            kwargs["embeds"] = []
    
        previous = sessions.get(key)
        if previous is not None:
            try:
                await previous.edit(**kwargs)
                return previous
            except (discord.NotFound, discord.HTTPException):
                sessions.pop(key, None)
    
        send_kwargs = dict(kwargs)
        send_kwargs["ephemeral"] = True
        send_kwargs["wait"] = True
        try:
            msg = await interaction.followup.send(**send_kwargs)
            sessions[key] = msg
            return msg
        except discord.HTTPException:
            send_kwargs.pop("wait", None)
            await interaction.followup.send(**send_kwargs)
            return None
    
    TARGET_CHANNEL_ID = 1526384339670270012
    WELCOME_CHANNEL_ID = 1524957892925456545
    
    # ═══════ Welcome Cards (صورة ترحيبية مخصصة لكل عضو جديد) ═══════
    WELCOME_CARD_ENABLED = False
    WELCOME_CARD_BACKGROUND_PATH = None  # ← حط هنا path ديال صورة (مثلا "assets/welcome_bg.png")، None = خلفية بتدرج لوني افتراضي
    WELCOME_CARD_ACCENT_RGB = (88, 101, 242)  # لون Discord Blurple، تقدر تبدلو بأي لون RGB (R, G, B)
    WELCOME_CARD_ACCENT2_RGB = (235, 90, 180)  # لون ثاني للتدرج القطري (وردي/بنفسجي بشكل افتراضي)
    SERVER_NAME = "GGMW9"
    
    # ═══════ STATUS المباشر ديال السيرفر (كل 30 دقيقة) ═══════
    STATS_CHANNEL_ID = 1527800975195377804  # ← channel "STATU"
    SERVER_INVITE_LINK = "https://discord.gg/5sWatSkSCY"  # ← بدلها بالرابط ديال السيرفر ديالك
    STATS_UPDATE_MINUTES = 30
    STATS_IMAGE_URL = ""  # ← حط هنا رابط مباشر ديال صورة (بانر) باش تبان فـ رسالة الـ STATUS، ولا خليها فارغة
    # ⚠️ خاص الرابط يكون Direct Link ديال صورة حقيقية (يسالي بـ .png/.jpg/.gif فـ الرابط نفسو
    # وتقدر تفتحو فـ المتصفح ويبان ليك غير الصورة بوحدها بلا حتى صفحة حداها).
    # أحسن طريقة: بعث الصورة فـ أي channel ديال ديسكورد، كليك يمين عليها → Copy Link،
    # وحط هاد الرابط هنا (كيبدا بـ https://cdn.discordapp.com/attachments/...).
    # مواقع بحال animated-gif-creator.com عادة ماخدامينش كـ hotlink، البوت ما غاديش يقدر يبين الصورة بيهم.
    
    AI_MODEL = "deepseek/deepseek-v4-flash"  # ← موديل مدفوع رخيص بزاف ($0.0983/مليون token دخول، $0.1966/مليون خروج)
    #   ✅ متحقق منو فـ openrouter.ai/deepseek — الاسم صحيح 100% وخدام (نسخة أبريل 2026، 1M context).
    #   بـ 9$ ديال الرصيد عندك تقريبا 90 مليون token دخول — يعني آلاف الردود. ماكاين حتى مشكل هنا.
    
    # ⚠️ DeepSeek V4 Flash هو reasoning model: كيصرف جزء من max_tokens على "التفكير"
    # قبل ما يكتب الجواب. علاش خاصنا نطفيو الـ reasoning فـ المهام القصيرة (بحال الترجمة)،
    # وإلا كيرجع content فارغة وكيبان ليك بلي "الموديل ماخدامش". شوف AI_DISABLE_REASONING تحت.
    AI_DISABLE_REASONING = True
    
    # ═══════ سلسلة الاحتياط (Fallback) ═══════
    # إلا AI_MODEL فشل لسبب ما (بحال خلص الرصيد)، البوت كيجرب أوتوماتيكيا الموديلات
    # المجانية اللي فـ هاد اللائحة، واحد بواحد، قبل ما يستسلم.
    # ✅ هاد اللائحة تحققت منها فـ 3 غشت 2026 من openrouter.ai (كاع الأسماء خدامة).
    # ⚠️ ملاحظة: "qwen/qwen3-next-80b-a3b-instruct:free" اللي كان هنا قبل تحيد من OpenRouter
    # فـ يوليوز 2026 — كان كيرجع 404 وهو من الأسباب اللي خلات الترجمة ما تخدمش.
    AI_MODEL_FALLBACKS = [
        "nvidia/nemotron-3-ultra-550b-a55b:free",   # أقوى موديل مجاني حاليا (1M context)
        "openai/gpt-oss-20b:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "google/gemma-4-31b-it:free",
        "openrouter/free",   # ← auto-router ديال OpenRouter: كيختار وحدو شي موديل مجاني متاح.
                             #   خليه دايما فالآخر — هو اللي كيضمن ليك البوت مايوقفش ملي
                             #   OpenRouter يحيد شي موديل مجاني بلا سابق إنذار.
    ]
    
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
    
    # ═══════ APIs جداد ═══════
    OMDB_API_KEY = os.getenv("OMDB_API_KEY")           # ← سجل فـ omdbapi.com (تفاصيل الفيلم + rating)
    TMDB_API_KEY = os.getenv("TMDB_API_KEY")           # ← سجل فـ themoviedb.org/settings/api (اكتشاف عشوائي)
    NEWS_API_KEY = os.getenv("NEWS_API_KEY")           # ← سجل فـ newsapi.org
    LASTFM_API_KEY = os.getenv("LASTFM_API_KEY")       # ← سجل فـ last.fm/api
    RAWG_API_KEY = os.getenv("RAWG_API_KEY")           # ← سجل فـ rawg.io/apidocs
    
    TMDB_URL = "https://api.themoviedb.org/3"
    
    MEMORY_SIZE = 100
    CREATIVITY = 0.85
    MAX_REPLY_LENGTH = 1500
    API_TIMEOUT = 15
    
    # ═══════════════════════════════════════════════════════
    # ║              CHANNELS ديال AUTO-INFO                 ║
    # ═══════════════════════════════════════════════════════
    
    NEWS_CHANNEL_IDS = [1526701863141900319]      # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الأخبار
    GAMES_CHANNEL_IDS = [1524957892925456546]      # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الألعاب
    MOVIES_CHANNEL_IDS = [1526721884434206820]     # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الأفلام
    ANIME_CHANNEL_IDS = [1526726257012772985]      # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الأنمي
    MUSIC_CHANNEL_IDS = [1524957892925456547]      # ← زيد IDs آخرين هنا بـ , إلا بغيتي عدة channels ديال الموسيقى
    
    # ═══════ تفعيل/تعطيل كل فئة ديال Auto-Info بوحدها ═══════
    # (كل فئة كتستعمل translate_to_darija → طلب OpenRouter. عطلها مؤقتا باش توفر
    # الحصة اليومية المجانية للترجمة بالعلم، وشعلها ملي تزيد رصيد ولا تبغي)
    AUTO_INFO_NEWS_ENABLED = False
    AUTO_INFO_GAMES_ENABLED = False
    AUTO_INFO_MOVIES_ENABLED = False
    AUTO_INFO_ANIME_ENABLED = False
    AUTO_INFO_MUSIC_ENABLED = False
    
    
    # ═══════════════════════════════════════════════════════
    # ║              MODERATION & VERIFICATION CONFIG          ║
    # ═══════════════════════════════════════════════════════
    
    MOD_LOGS_CHANNEL_ID = 1526470164235681832
    VERIFY_CHANNEL_ID = 1526481352264781854
    RULES_CHANNEL_ID = 1526474691789721700
    BLACKLIST_CHANNEL_ID = 1526858911477661786  # ← حط هنا ID ديال channel "Blacklist things"
    REPORTS_CHANNEL_ID = 1526884019105431562    # 🔒 backend staff reports — ماشي واجهة للأعضاء
    
    # ═══════ Support Center موحد قدام الأعضاء ═══════
    SUPPORT_CENTER_CHANNEL_ID = 1535652036324892763
    LEGACY_TICKETS_PANEL_CHANNEL_ID = 1532144216958959839  # غير باش نمسحو Panel القديمة ديال البوت
    TICKETS_PANEL_CHANNEL_ID = 0  # تعطلت الواجهة القديمة؛ Support Center هي الواجهة الوحيدة
    TICKETS_CATEGORY_ID = 1532144108754440355        # backend: فين كيتخلقو ticket channels الخاصة
    TICKET_LOGS_CHANNEL_ID = 1532144316611428352     # backend: transcripts/logs ديال tickets
    
    # ═══════ نظام Applications (طلبات الانضمام لفريق الإدارة/Staff) ═══════
    APPLICATIONS_PANEL_CHANNEL_ID = 1532910298585890927     # ← حط هنا ID ديال channel فين غادي تبان رسالة "📋 قدم طلب" بالزر
    APPLICATIONS_REVIEW_CHANNEL_ID = 1532910345352515666    # ← حط هنا ID ديال channel فين كتوصل الطلبات (خاصك تحطو Private، يشوفو غير Owner+Admins فـ Discord)
    APPLICATION_ACCEPTED_ROLE_ID = 1532910587301068930      # ← (اختياري) رول كيتعطى أوتوماتيكياً ملي يتقبل الطلب — خليها 0 إلا مابغيتيش
    APPLICATIONS_COOLDOWN_HOURS = 168     # ← شحال ديال الساعات خاص العضو يصبر بعد الرفض قبل ما يقدر يعاود يقدم (168 = أسبوع)
    # ═══════ شكون يقدر يقبل/يرفض الطلبات (Owner + هاد الأدوار فقط — Moderators ماشي معنيين) ═══════
    APPLICATIONS_REVIEWER_ROLE_IDS = [
        1525712399456272495,  # نفس role "Admin"
    ]
    
    # ═══════ نظام Suggestions (اقتراحات الأعضاء) ═══════
    SUGGESTIONS_CHANNEL_ID = 1532913868509155358            # ← حط هنا ID ديال channel فين كيتبعثو الاقتراحات
    
    # ═══════ نظام Birthdays (أعياد الميلاد) ═══════
    BIRTHDAY_ANNOUNCE_CHANNEL_ID = 1533241235630854224   # ← حط هنا ID ديال channel فين كيتبعث تهنئة عيد الميلاد (بحال #general)
    BIRTHDAY_ROLE_ID = 1533241332473008229               # ← (اختياري) رول 🎂 كيتعطى نهار عيد الميلاد وكيتحيد الغد — خليها 0 إلا مابغيتيش
    BIRTHDAY_ANNOUNCE_HOUR = 9         # ← فأي ساعة (UTC، من 0 لـ 23) كيتبعث التهنئة كل نهار
    
    # ═══════ نظام Marry/Bestfriend (أزواج/أصدقاء) ═══════
    MARRIAGE_ROLE_ID = 1533987822216810706     # ← (اختياري) رول عام 💍 كيتعطى للجوج ملي يتزوجو (بزيادة على الرول الشخصي) — خليها 0 إلا مابغيتيش
    BESTFRIEND_ROLE_ID = 1533988290011594824   # ← (اختياري) رول عام 🤝 كيتعطى للجوج ملي يوليو Best Friends (بزيادة على الرول الشخصي) — خليها 0 إلا مابغيتيش
    RELATIONSHIP_PROPOSAL_TIMEOUT_SECONDS = 300   # ← شحال ديال الوقت (بالثواني) عندو الشخص التاني باش يرد على الطلب
    RELATIONSHIP_DM_PROPOSALS = True    # ← الطلب يتبعث فـ DM للشخص المطلوب (True)، ولا فنفس الـ channel ديال السيرفر (False)
    RELATIONSHIP_ANNOUNCE_CHANNEL_ID = 1524957892925456545   # ← الـ channel (# general) فين كيتبعث إعلان عام ملي شي حد يقبل الزواج/الصداقة، ولا يطلق/يقطع الصداقة — خليها 0 إلا مابغيتيش
    MARRIAGE_CENTER_CHANNEL_ID = 1536602981359685724   # ← channel "marriage-club" — فيها كتصاوب البانلات ديال الزواج/الصداقة
    RELATIONSHIP_LIST_UPDATE_MINUTES = 15       # ← كل شحال ديال الدقايق كتتحدث لائحة الأزواج/الأصدقاء أوتوماتيكياً (بحال Leaderboard)
    RELATIONSHIP_PERSONAL_ROLE_ENABLED = True   # ← كل واحد فالعلاقة ياخد رول شخصي بسمية الشريك ديالو (بحال "💍 Aya")
    MARRIAGE_PERSONAL_ROLE_COLOR = 0xd41b1b     # ← لون الرولات الشخصية ديال الزواج (روز)
    BESTFRIEND_PERSONAL_ROLE_COLOR = 0xffd119   # ← لون الرولات الشخصية ديال الصداقة (أزرق فاتح)
    
    # ═══════ رولات الأبراج — كيتعطى أوتوماتيكياً ملي العضو يدير /setbirthday حسب التاريخ ═══════
    # ⚠️ بدل كل 0 برقم الـ Role ID الحقيقي ديالك (Server Settings → Roles → كليك يمين → Copy Role ID)
    # خلي شي واحد 0 إلا مابغيتيش رول لهاد البرج (البوت غايتخطاه بلا مشكل)
    ZODIAC_ROLE_IDS = {
        "aries": 1533244997858492426,        # ♈ الحمل (21 مارس - 19 أبريل)
        "taurus": 1533245155782561904,       # ♉ الثور (20 أبريل - 20 ماي)
        "gemini": 1533245357805404260,       # ♊ الجوزاء (21 ماي - 20 يونيو)
        "cancer": 1533245304789274744,       # ♋ السرطان (21 يونيو - 22 يوليوز)
        "leo": 1533245515871948952,          # ♌ الأسد (23 يوليوز - 22 غشت)
        "virgo": 1533245580615352380,        # ♍ العذراء (23 غشت - 22 شتنبر)
        "libra": 1533245685141340354,        # ♎ الميزان (23 شتنبر - 22 أكتوبر)
        "scorpio": 1533245753252905070,      # ♏ العقرب (23 أكتوبر - 21 نونبر)
        "sagittarius": 1533245801088684145,  # ♐ القوس (22 نونبر - 21 دجنبر)
        "capricorn": 1533245849964908614,    # ♑ الجدي (22 دجنبر - 19 يناير)
        "aquarius": 1533245909561901249,     # ♒ الدلو (20 يناير - 18 فبراير)
        "pisces": 1533245967275393137,       # ♓ الحوت (19 فبراير - 20 مارس)
    }
    
    # ═══════ شكون يقدر يستعمل Room Mute Panel (/roommutepanel) — Owner + هاد اللائحة بوحدهم ═══════
    ROOM_MUTE_PANEL_ALLOWED_USER_IDS = [
        900839094106603671,  # ← الأدمين اللي زدتي
    ]
    
    UNVERIFIED_ROLE_ID = 1526452828267085915
    MEMBER_ROLE_ID = 1526451890399739934
    MUTED_ROLE_ID = 1526468718534590574
    BOYS_ROLE_ID = 1526407092813037588   # ← حط هنا ID ديال role "Boys"
    GIRLS_ROLE_ID = 1526337114164301824  # ← حط هنا ID ديال role "Girls"
    
    # ═══════ القوانين ديال السيرفر (بدلها بالقوانين الحقيقية ديالك) ═══════
    SERVER_RULES = (
        "**🇲🇦 بالدارجة:**\n"
        "1️⃣ الاحترام واجب بين كاع الأعضاء — ممنوع السب خارج نطاق المزاح، العنصرية، والتنمر.\n"
        "2️⃣ ممنوع السبام والإعلانات بلا إذن من الإدارة.\n"
        "3️⃣ ممنوع المحتوى ديال +18 ولا العنيف ولا الصادم.\n"
        "4️⃣ هضر فـ الشات المخصص ليه (بحال #games للألعاب).\n"
        "5️⃣ احترم القرارات ديال الأدمن والمشرفين.\n"
        "6️⃣ ممنوع مشاركة معلومات شخصية ديال الآخرين (Doxxing).\n"
        "7️⃣ عدم الالتزام بالقوانين غادي يأدي لعقوبة (تحذير، كتم، طرد).\n\n"
        "**🇬🇧 English:**\n"
        "1️⃣ Respect everyone — Insults/cursing are not allowed outside of joking around, racism, or bullying.\n"
        "2️⃣ No spam or ads without staff permission.\n"
        "3️⃣ No NSFW, violent, or shocking content.\n"
        "4️⃣ Talk in the right channel for each topic (e.g. #games for games).\n"
        "5️⃣ Respect staff/admin decisions.\n"
        "6️⃣ No sharing others' personal info (doxxing).\n"
        "7️⃣ Breaking the rules leads to punishment (warning, mute, kick).\n\n"
        "**🇫🇷 Français :**\n"
        "1️⃣ Le respect est obligatoire — Les insultes sont interdites en dehors du cadre de la plaisanterie., de racisme ou de harcèlement.\n"
        "2️⃣ Pas de spam ni de publicité sans autorisation.\n"
        "3️⃣ Contenu +18, violent ou choquant interdit.\n"
        "4️⃣ Parlez dans le salon approprié à chaque sujet (ex. #games pour les jeux).\n"
        "5️⃣ Respectez les décisions de l'administration.\n"
        "6️⃣ Ne partagez pas les infos personnelles des autres (doxxing).\n"
        "7️⃣ Le non-respect des règles entraîne une sanction (avertissement, mute, exclusion)."
    )
    
    # ═══════ الاستثناءات ديال Auto-Mod (Owner + أدوار معفيين) ═══════
    OWNER_ID = 1260089246216097832  # صاحب السيرفر
    EXEMPT_ROLE_IDS = [
        1525712399456272495,  # Admin
        1526182506272133180,  # Moderator
    ]
    ADMIN_ROLE_ID = 1525712399456272495
    MODERATOR_ROLE_ID = 1526182506272133180
    
    # ═══════ لائحة الإدارة (Owner + Admins + Mods) فـ channel "Administrators" ═══════
    ADMINISTRATORS_CHANNEL_ID = 1532115828450000967  # ← حط هنا ID ديال channel "Administrators"
    ADMIN_LIST_UPDATE_MINUTES = 30  # ← كل شحال ديال الدقائق كيتحدث المساج
    
    # الأدوار اللي غادي تبان فـ اللائحة، بالترتيب اللي بغيتي تبان بيه (من فوق لتحت).
    # زيد/بدل label و role_id حسب الرولات ديالك (الـ Owner كيبان فوق بوحدو من OWNER_ID).
    STAFF_ROLES_ORDER = [
        {"label": "🔱 Admins", "role_id": 1525712399456272495},      # نفس role "Admin"
        {"label": "🛡️ Moderators", "role_id": 1526182506272133180},  # نفس role "Moderator"
    ]
    
    BANNED_WORDS = [
        'سبام', 'spam', 'naked.', 'discord.gg', 'العزية', 'عزي',
        'nude', 'porn', 'xxx', 'sex', 'fuck', 'shit', 'bitch'
    ]
    
    # ═══════ لائحة ديناميكية: كلمات وأفعال ممنوعة كتزاد/كتحيد بالأوامر ═══════
    # BANNED_WORDS فوق هي القائمة الأساسية المكتوبة فالكود. أي كلمة/عبارة كتزاد
    # ولا كتحيد بالأوامر (/addword, /addaction) كتتسجل فـ BANNED_LISTS_FILE
    # باش تبقى محفوظة حتى بعد ريستارت البوت. BANNED_ACTIONS هي عبارات/سلوكيات
    # ممنوعة زيادة على الكلمات، وكتتبع نفس آلية الحذف/التحذير ديال BANNED_WORDS.
    BANNED_LISTS_FILE = os.path.join(DATA_DIR, "banned_lists.json")
    BANNED_ACTIONS = []  # كتتعمر من الملف فـ load_banned_lists()
    banned_words_state = {"extra": [], "removed": []}  # كتتعمر من الملف
    
    SPAM_THRESHOLD = 5
    SPAM_INTERVAL = 5
    
    # ═══════ Anti-Raid Protection (كشف الهجوم الجماعي) ═══════
    ANTI_RAID_ENABLED = True
    RAID_JOIN_THRESHOLD = 10          # عدد الأعضاء الجداد
    RAID_JOIN_INTERVAL_SECONDS = 30   # فـ هاد المدة (بالثواني) → إلا توصلات = Raid محتمل
    RAID_ACTION = "kick"              # شنو يتدار فالعضو ملي يكون Raid Mode مفعل: "kick" ولا "ban"
    RAID_LOCKDOWN_DURATION_MINUTES = 30  # شحال كيدوم Lockdown قبل ما يرجع عادي أوتوماتيكياً (0 = يبقى حتى /unlockdown يدوي)
    
    # كشف الحسابات الجداد بزاف (كثير ما كتكون هي لي فراود) — كيبعث غير تنبيه،
    # ما كيديرش عقوبة تلقائية إلا كان Raid Mode مفعل
    RAID_MIN_ACCOUNT_AGE_HOURS = 24
    
    # ═══════ Leveling System (XP + Levels + رولات أوتوماتيكية) ═══════
    LEVELING_ENABLED = True
    XP_MIN_PER_MESSAGE = 10
    XP_MAX_PER_MESSAGE = 25
    XP_COOLDOWN_SECONDS = 60   # ماخذيش XP مرة أخرى من نفس العضو قبل ما تعدي هاد المدة
    LEVEL_UP_CHANNEL_ID = 1532872432778743978    # ← channel فين كيتبعث "مبروك وصلتي لـ Level X" (0 = نفس channel لي هضر فيه العضو)
    LEVELS_INFO_CHANNEL_ID = 1532613980466446387  # ← channel فين غادي تبان رسالة شرح نظام الـ Leveling + لائحة كاع المستويات ورولاتهم
    OWNER_CONTROL_CHANNEL_ID = 1535635483302821938  # 🔐 Owner Control Center — Owner بوحدو
    
    # ═══════ Leaderboard أوتوماتيكي (كيتحدث بروحو فـ channel معين) ═══════
    LEADERBOARD_CHANNEL_ID = 1532613980466446387   # ← channel فين غادي تتبعث/تتحدث لائحة الشرف أوتوماتيكياً
    LEADERBOARD_UPDATE_MINUTES = 15                 # ← كل شحال ديال الدقايق كيتحدث
    
    # رولات أوتوماتيكية عند مستويات معينة: {level: role_id}
    # ✅ العضو عندو غير Role وحدة من LEVEL_ROLES: أعلى threshold وصل ليها.
    # مثال: Level 10 → Role 10، منين يوصل Level 15 كتتحيد Role 10 وكتتعطى Role 15.
    # البوت كيدير Self-Healing حتى بعد Restart باش يصلح أي رول ناقصة/قديمة.
    LEVEL_ROLES = {
        5: 1532874771287507135,
        10: 1532877605366268116,
        15: 1532877729052233988,
        20: 1532877833125232740,
        25: 1532877955414360336,
        30: 1532877995306651853,
        35: 1532878086893207653,
        40: 1532878137430380674,
        45: 1532878260428341390,
        50: 1532878348752261331,
        60: 1532878501278125251,
        70: 1532878632371138181,
        80: 1532878710745596064,
        90: 1532878803075076106,
        100: 1532878888986738869,
    }
    
    # ═══════ Discord permissions آمنة فقط ═══════
    # ما كنعطيوش View Audit Log / Manage Threads / Manage Events / Manage Emojis...
    # حيت هادو صلاحيات إدارة وقد يخربقو السيرفر. الرولات العليا كتستافد أكثر من
    # Economy/Bank/Shop/Daily + الميزات الاجتماعية، ماشي من صلاحيات Moderation.
    LEVEL_PERK_ADDITIONS = {
        5:  discord.Permissions(use_external_emojis=True, use_external_stickers=True),
        10: discord.Permissions(use_soundboard=True),
        15: discord.Permissions(use_external_sounds=True, send_voice_messages=True),
        20: discord.Permissions(embed_links=True, attach_files=True),
        25: discord.Permissions(create_public_threads=True, send_messages_in_threads=True),
        30: discord.Permissions(use_embedded_activities=True),
        35: discord.Permissions(stream=True),
        40: discord.Permissions(create_private_threads=True),
        45: discord.Permissions(request_to_speak=True),
    }
    
    # ═══════ القيمة الحقيقية ديال كل Level Role ═══════
    # shop_discount_percent = تخفيض دائم فالمتجر.
    # daily_bonus_percent = بونيص فوق /daily، كيتخلص من Treasury باش ما نخلقوش تضخم.
    # loan_* = شروط البنك الأساسية قبل Credit Score وسيولة Treasury.
    LEVEL_ROLE_BENEFITS = {
        5:   {"name": "🌱 Starter",     "shop_discount_percent": 1,  "daily_bonus_percent": 2,  "loan_base": 5000,  "loan_interest": 15, "loan_days": 2, "feature": "😀 External Emojis + Stickers"},
        10:  {"name": "🥉 Bronze I",    "shop_discount_percent": 2,  "daily_bonus_percent": 4,  "loan_base": 7500,  "loan_interest": 14, "loan_days": 2, "feature": "🔊 Soundboard"},
        15:  {"name": "🥉 Bronze II",   "shop_discount_percent": 3,  "daily_bonus_percent": 6,  "loan_base": 10000,  "loan_interest": 13, "loan_days": 3, "feature": "🎙️ Voice Messages + External Sounds"},
        20:  {"name": "🥈 Silver I",    "shop_discount_percent": 4,  "daily_bonus_percent": 8,  "loan_base": 15000,  "loan_interest": 12, "loan_days": 3, "feature": "📎 Embeds/Attachments + Bio"},
        25:  {"name": "🥈 Silver II",   "shop_discount_percent": 5,  "daily_bonus_percent": 10, "loan_base": 20000, "loan_interest": 11, "loan_days": 3, "feature": "🧵 Public Threads"},
        30:  {"name": "💠 Sapphire I",  "shop_discount_percent": 6,  "daily_bonus_percent": 12, "loan_base": 30000, "loan_interest": 10, "loan_days": 3, "feature": "🎮 Discord Activities + XP Milestone Boost"},
        35:  {"name": "💠 Sapphire II", "shop_discount_percent": 7,  "daily_bonus_percent": 14, "loan_base": 40000, "loan_interest": 10, "loan_days": 4, "feature": "📡 Go Live / Stream"},
        40:  {"name": "🥇 Gold I",      "shop_discount_percent": 8,  "daily_bonus_percent": 16, "loan_base": 50000, "loan_interest": 9,  "loan_days": 4, "feature": "🔐 Private Threads + XP Milestone Boost"},
        45:  {"name": "🥇 Gold II",     "shop_discount_percent": 9,  "daily_bonus_percent": 18, "loan_base": 65000, "loan_interest": 9,  "loan_days": 4, "feature": "🎤 Request to Speak + أقوى Economy Tier"},
        50:  {"name": "💎 Platinum",    "shop_discount_percent": 10, "daily_bonus_percent": 20, "loan_base": 80000, "loan_interest": 8,  "loan_days": 5, "feature": "👑 Milestone Announcement + XP Boost"},
        60:  {"name": "💎 Diamond",     "shop_discount_percent": 11, "daily_bonus_percent": 22, "loan_base": 100000, "loan_interest": 8,  "loan_days": 5, "feature": "🗳️ Create Poll + XP Boost"},
        70:  {"name": "🌟 Elite",       "shop_discount_percent": 12, "daily_bonus_percent": 24, "loan_base": 125000, "loan_interest": 7,  "loan_days": 5, "feature": "🌟 Elite Badge + XP Boost"},
        80:  {"name": "👑 Master",      "shop_discount_percent": 13, "daily_bonus_percent": 26, "loan_base": 150000, "loan_interest": 6,  "loan_days": 6, "feature": "💫 Master Economy Tier + XP Boost"},
        90:  {"name": "🔱 Mythic",      "shop_discount_percent": 14, "daily_bonus_percent": 28, "loan_base": 200000, "loan_interest": 5,  "loan_days": 6, "feature": "🔱 Mythic Economy Tier + XP Boost"},
        100: {"name": "🏆 Legend",      "shop_discount_percent": 15, "daily_bonus_percent": 30, "loan_base": 300000, "loan_interest": 4,  "loan_days": 7, "feature": "👑 Legend Personal Role + أفضل شروط البنك"},
    }
    
    
    def get_level_perks(level: int) -> dict:
        """كترجع الامتيازات الحالية ديال أعلى LEVEL_ROLE threshold وصل ليها."""
        level = max(0, int(level))
        current = {
            "threshold": 0,
            "name": "👤 Member",
            "shop_discount_percent": 0,
            "daily_bonus_percent": 0,
            "loan_base": 2500,
            "loan_interest": 16,
            "loan_days": 2,
            "feature": "طلع Level 5 باش تفتح أول امتيازات.",
        }
        for threshold, info in sorted(LEVEL_ROLE_BENEFITS.items()):
            if level >= threshold:
                current = {"threshold": threshold, **info}
            else:
                break
        return dict(current)
    
    
    def get_next_level_perks(level: int) -> Optional[dict]:
        level = max(0, int(level))
        for threshold, info in sorted(LEVEL_ROLE_BENEFITS.items()):
            if threshold > level:
                return {"threshold": threshold, **info}
        return None
    
    
    def format_level_perk_summary(level: int) -> str:
        p = get_level_perks(level)
        return (
            f"{p['name']} • 🛒 **-{p['shop_discount_percent']}% Shop** • "
            f"🎁 **+{p['daily_bonus_percent']}% Daily** • "
            f"🏦 **{cfg.fmt_money(p['loan_base'])} / {p['loan_interest']}% / {p['loan_days']}d** • "
            f"{p['feature']}"
        )
    
    
    
    def get_cumulative_level_permissions(level: int) -> discord.Permissions:
        """كترجع الصلاحيات التراكمية (كاع اللي تزادو من المستوى 5 حتى هاد المستوى)
        — كل رول ديال LEVEL_ROLES خاصو يكون فيه المجموع الكامل، حيت العضو عندو غير
        رول واحد فأي وقت (أعلى مستوى وصل ليه، بفضل sync_level_roles)."""
        value = 0
        for lvl, perms in sorted(LEVEL_PERK_ADDITIONS.items()):
            if lvl <= level:
                value |= perms.value
        return discord.Permissions(value)
    
    
    async def sync_level_role_permissions(guild: discord.Guild):
        """كتأكد بلي كل رول فـ LEVEL_ROLES عندو بالضبط الصلاحيات التراكمية المطلوبة —
        self-healing، كتخدم فـ on_ready بلا ما يحتاج حد يتدخل يدوياً."""
        for level, role_id in LEVEL_ROLES.items():
            role = guild.get_role(role_id)
            if not role:
                continue
            desired = get_cumulative_level_permissions(level)
            if role.permissions.value != desired.value:
                try:
                    await role.edit(permissions=desired, reason=f"Level {level} Perks Sync")
                except (discord.Forbidden, discord.HTTPException) as e:
                    print(f"[LEVEL PERKS] ما قدرتش نبدل صلاحيات رول Level {level}: {e}")
    
    # ═══════ نظام مكافآت الـ Milestones (10 → 100) — أوتوماتيكي بالكامل ═══════
    # كل رول هنا كيتصاوب أوتوماتيكياً من طرف البوت أول مرة يوصل ليها شي عضو (ماخصكش
    # تصاوب حتى رول يدوياً) — وكيبقى مكتسب للأبد (تراكمي، ماشي بديل بحال LEVEL_ROLES).
    # 'perk' كتحدد شنو زيادة كيستافد بيه العضو، بزيادة على البادج نفسها.
    LEVEL_MILESTONES = {
        10: {"name": "🌱 عضو نشيط", "color": 0x77DD77, "hoist": False, "perk": None,
             "desc": "بادج + بداية الطريق 🌱"},
        15: {"name": "🔥 نشيط بزاف", "color": 0xFF8C42, "hoist": False, "perk": None,
             "desc": "بادج 🔥"},
        20: {"name": "⭐ معروف", "color": 0xFFD700, "hoist": False, "perk": "bio",
             "desc": "بادج + 📝 Bio من Panel ديال #levels-info"},
        25: {"name": "💎 VIP صغير", "color": 0x00CFFF, "hoist": False, "perk": None,
             "desc": "بادج 💎"},
        30: {"name": "🎖️ متمرس", "color": 0xB388FF, "hoist": False, "perk": "xp_boost",
             "desc": "بادج + بونيص XP مؤقت"},
        40: {"name": "🏆 محترف", "color": 0xFF6F91, "hoist": False, "perk": "xp_boost",
             "desc": "بادج + بونيص XP مؤقت"},
        50: {"name": "👑 نص الطريق", "color": 0xFFC300, "hoist": True, "perk": "xp_boost+announce",
             "desc": "بادج + إعلان خاص فـ #general + بونيص XP"},
        60: {"name": "🛡️ Veteran", "color": 0x4CD9C0, "hoist": True, "perk": "poll+xp_boost",
             "desc": "بادج + 🗳️ Create Poll من Panel ديال #levels-info + بونيص XP"},
        70: {"name": "🌟 نخبة", "color": 0xFF3F8E, "hoist": True, "perk": "xp_boost",
             "desc": "بادج + 🌟 كيبان فالـLeaderboard Panel + بونيص XP"},
        80: {"name": "💫 أسطورة صاعدة", "color": 0x845EC2, "hoist": True, "perk": "xp_boost",
             "desc": "بادج + بونيص XP"},
        90: {"name": "🔱 قريب من القمة", "color": 0xD65DB1, "hoist": True, "perk": "xp_boost",
             "desc": "بادج + بونيص XP"},
        100: {"name": "👑 أسطورة السيرفر", "color": 0xFFD700, "hoist": True, "perk": "legend+announce",
              "desc": "رول شخصي فريد قابل للتسمية من 👑 Legend Title فـ #levels-info + إعلان كبير"},
    }
    LEVEL_MILESTONE_XP_BOOST_PERCENT = 15     # ← نسبة البونيص المؤقت ديال XP (15 = +15%)
    LEVEL_MILESTONE_XP_BOOST_DAYS = 7         # ← شحال ديال الأيام كيدوم البونيص كل مرة كيتكسب
    LEVEL_MILESTONE_ANNOUNCE_CHANNEL_ID = RELATIONSHIP_ANNOUNCE_CHANNEL_ID   # ← نفس الـ #general لي كتستعمل الزواج/الصداقة
    
    # ═══════ الترجمة التلقائية بالـ Reaction (علم الدولة 🇬🇧🇫🇷 على أي رسالة) ═══════
    AUTO_TRANSLATE_ENABLED = True
    # ⚠️ كل عضو (ماشي بوت) يقدر يستعملها فأي channel — البوت خاصو صلاحية "Add Reactions" و"Send Messages"
    # زيد/بدل الأعلام اللي بغيتي هنا: emoji العلم → (الاسم بالعربية للعرض، الاسم بالانجليزية للـ AI)
    FLAG_TO_LANGUAGE = {
        "🇬🇧": ("الإنجليزية", "English"),
        "🇺🇸": ("الإنجليزية", "English"),
        "🇫🇷": ("الفرنسية", "French"),
        "🇪🇸": ("الإسبانية", "Spanish"),
        "🇩🇪": ("الألمانية", "German"),
        "🇮🇹": ("الإيطالية", "Italian"),
        "🇵🇹": ("البرتغالية", "Portuguese"),
        "🇹🇷": ("التركية", "Turkish"),
        "🇷🇺": ("الروسية", "Russian"),
        "🇯🇵": ("اليابانية", "Japanese"),
        "🇰🇷": ("الكورية", "Korean"),
        "🇨🇳": ("الصينية", "Chinese"),
        "🇸🇦": ("العربية الفصحى", "Modern Standard Arabic"),
        "🇲🇦": ("الدارجة المغربية", "Moroccan Darija"),
    }
    
    # ═══════ Auto-React: البوت كيزيد الأعلام كـ reactions أوتوماتيك على كل رسالة ═══════
    # (بدل ما العضو يكتب/يلقى العلم بيدو، البوت كيحطهم ليه جاهزين، وغير يكليكي على اللي بغا)
    AUTO_REACT_TRANSLATE_ENABLED = False   # ← بدلها True باش تخدم
    AUTO_REACT_FLAGS = ["🇬🇧", "🇫🇷", "🇪🇸"]  # ← الأعلام اللي غادي تتزاد أوتوماتيك (خاصهم يكونو موجودين فـ FLAG_TO_LANGUAGE فوق)
    AUTO_REACT_CHANNEL_IDS = []   # ← خاوية [] = فكاع الـ channels. إلا بغيتي غير channels معينة، زيد IDs هنا مثلا [111, 222]
    
    for _flag in AUTO_REACT_FLAGS:
        if _flag not in FLAG_TO_LANGUAGE:
            print(f"[CONFIG] ⚠️ AUTO_REACT_FLAGS فيها علم '{_flag}' ماكاينش فـ FLAG_TO_LANGUAGE — زيدو لهاديك اللائحة ولا حيدو من AUTO_REACT_FLAGS.")
    
    # ═══════ نظام الصوت — Join to Create (روم صوتية مؤقتة) ═══════
    JOIN_TO_CREATE_ENABLED = True
    JOIN_TO_CREATE_CHANNEL_ID = 1536132541185265705   # ← ID ديال الـ voice channel "➕ دير روم" (العضو كيدخل ليه فيتخلق ليه روم خاص بيه)
    TEMP_VC_CATEGORY_ID = 1533257707543461939          # ← ID ديال الـ Category فين غادي تتخلق الروومات المؤقتة (0 = نفس category ديال JOIN_TO_CREATE_CHANNEL_ID)
    TEMP_VC_NAME_TEMPLATE = "{name}'s Room 🔊"
    TEMP_VC_DEFAULT_LIMIT = 0        # ← 0 = بلا حد أقصى للأعضاء
    # Block fallback خصوصاً للي عندهم Administrator: 1/2 خروج+إنذار، المحاولة 3 = Kick من السيرفر إذا hierarchy تسمح
    TEMP_VC_DENY_MAX_ATTEMPTS = 3
    TEMP_VC_DENY_KICK_FROM_SERVER = True
    
    # ═══════ نظام الصوت — Voice XP (نقط XP على الوقت فالـ Voice) ═══════
    VOICE_XP_ENABLED = True
    VOICE_XP_PER_INTERVAL = 10        # ← شحال ديال XP كياخد العضو كل VOICE_XP_INTERVAL_MINUTES (غير كيهضر/كيتواجد فـ فويس عادي)
    VOICE_XP_INTERVAL_MINUTES = 5
    VOICE_XP_MIN_HUMANS_IN_CHANNEL = 2   # ← خاص يكونو على الأقل هاد العدد ديال البشر (ماشي بوتات) فنفس الروم باش ياخدو XP (كيمنع الفارمينغ وحدك)
    VOICE_XP_COUNT_MUTED_DEAFENED = False  # ← False = العضو اللي self-mute/self-deafen كياخد نسبة AFK المخفضة (ماشي القيمة الكاملة). True = كياخد نفس XP بحال اللي حال المايك
    VOICE_XP_EXCLUDE_CHANNEL_IDS = []   # ← زيد هنا IDs ديال أي voice channel ماباغيش يعطي حتى XP فيه (كيتحيد كامل، حتى XP ديال AFK)
    STREAM_XP_PER_INTERVAL = 20   # ← شحال ديال XP كياخد العضو كل VOICE_XP_INTERVAL_MINUTES ملي كيدير Go Live (لايفستريم) — بالافتراض أكثر من الفويس العادي حيت المجهود أكبر (كيبان لكل الروم، ماشي غير كيتواجد)
    
    # ═══════ نظام الصوت — XP ديال الـ AFK (درجات مخفضة) ═══════
    # الفكرة: حتى اللي سد المايك ولا دار Deafen كياخد XP، ولكن أقل من اللي كيهضر.
    # وباش نشجعو الناس يمشيو للروم ديال AFK بدل ما يبقاو ساكنين فالرومات النشيطة،
    # الـ AFK فالروم الرسمية ديال AFK كياخد أكثر من الـ AFK فروم عادية.
    #
    # 📊 الترتيب من الأكثر للأقل:
    #    🎥 لايفستريم (Go Live)          → STREAM_XP_PER_INTERVAL      (20)
    #    🎤 مايك محلول / كيهضر          → VOICE_XP_PER_INTERVAL       (10)
    #    💤 AFK فالروم الرسمية ديال AFK  → AFK_CHANNEL_XP_PER_INTERVAL  (4)
    #    🔇 AFK (مايك مسدود) فروم عادية → AFK_MUTED_XP_PER_INTERVAL    (2)
    AFK_XP_ENABLED = True
    AFK_CHANNEL_XP_PER_INTERVAL = 10   # ← XP كل فترة للي مريح فالروم ديال AFK (guild.afk_channel ولا AFK_CHANNEL_IDS تحت)
    AFK_MUTED_XP_PER_INTERVAL = 14     # ← XP كل فترة للي سد المايك/دار Deafen وهو فروم عادية
    AFK_CHANNEL_IDS = []              # ← (اختياري) زيد هنا IDs ديال رومات AFK إضافية. البوت أصلا كيعرف الروم الرسمية ديال السيرفر (Server Settings → Overview → Inactive Channel)
    AFK_XP_REQUIRE_MIN_HUMANS = False # ← False = XP ديال AFK كيتعطى حتى لو كان بوحدو (طبيعي، حيت الروم ديال AFK غالبا خاوية)
    AFK_XP_DAILY_CAP = 150            # ← سقف يومي لـ XP ديال AFK لكل عضو (0 = بلا سقف). كيمنع اللي كيخلي البيسي شعال 24/24 يفرمي
    
    # ═══════ Auto AFK Move — Self-Deafen مستمر 30 دقيقة → روم AFK ═══════
    AFK_AUTO_MOVE_ENABLED = True
    AFK_AUTO_MOVE_AFTER_MINUTES = 30      # خاص Self-Deafen يبقى متواصل هاد المدة
    AFK_AUTO_MOVE_CHECK_SECONDS = 30      # كل شحال البوت يشيك واش سالات المدة
    AFK_AUTO_RETURN_ENABLED = True        # ملي يفك Self-Deafen فـ AFK يرجع للروم الأصلية
    # False حسب سياسة Temp Rooms الحالية: أي روم بلا Humans كتتحذف، حتى إلا المالك تهبط للـ AFK.
    AFK_AUTO_RETURN_KEEP_TEMP_ROOM = False
    # الهدف: guild.afk_channel أولاً (Server Settings → Inactive Channel)، وإلا أول ID صالح فـ AFK_CHANNEL_IDS
    
    # ⚠️ القيم اللي فوق (XP_MIN_PER_MESSAGE, XP_MAX_PER_MESSAGE, XP_COOLDOWN_SECONDS,
    # VOICE_XP_PER_INTERVAL, VOICE_XP_INTERVAL_MINUTES, VOICE_XP_MIN_HUMANS_IN_CHANNEL,
    # STREAM_XP_PER_INTERVAL) هي غير القيم الافتراضية عند أول تشغيل. من بعد، تقدر تبدلهم
    # مباشرة من ديسكورد بالأمر /xppanel (Admin) بلا ماتمس الكود ولا تعاود ريستارت البوت،
    # والتبديلات كيتحفظو فـ xp_settings.json باش يبقاو حتى بعد ريستارت.
    
    # ═══════ درجات العقوبة حسب عدد التحذيرات (سهل التعديل) ═══════
    # كل عضو كيبدا بلا تحذيرات. كل تحذير (Auto-Mod ولا /warn يدوي) كيزيد
    # العداد ديالو بـ 1. من غير ما يوصل لعتبة، ما كتوقع حتى عقوبة.
    # غيّر الأرقام هنا حسب بغيتك — بلا ما تمس شي حاجة أخرى فالكود.
    MUTE_AFTER_WARNS = 2     # عدد التحذيرات باش يتكتم أوتوماتيكياً
    MUTE_DURATION_MINUTES = 20  # شحال ديال الدقائق كيدوم الكتم التلقائي
    KICK_AFTER_WARNS = 4     # عدد التحذيرات باش يتطرد أوتوماتيكياً
    BAN_AFTER_WARNS = 6      # عدد التحذيرات باش يتحظر أوتوماتيكياً (نهائي)
    
    WARN_LIMIT = KICK_AFTER_WARNS  # مستعملة فبعض الرسائل القديمة، كتبقى مرتبطة بمرحلة الطرد
    
    # ═══════════════════════════════════════════════════════
    # ║              PICK ROLES CONFIG (Dropdown)               ║
    # ═══════════════════════════════════════════════════════
    # نظام اختيار الأدوار بـ Dropdown Menu (بدل الـ Reactions القديمة).
    # كل مجموعة (category) كتبان فـ Select Menu وحدها فـ الرسالة، والعضو
    # يقدر يختار عدة أدوار من نفس المجموعة مرة وحدة.
    # حط هنا label + emoji + ID ديال الرول (كليك يمين على الرول فـ Discord → Copy ID)
    # خاصك تفعّل "Developer Mode" فـ Discord Settings > Advanced باش يبان ليك Copy ID
    PICK_ROLES = {
        "🎯 الهوايات": [
            {"label": "Gamer", "emoji": "🎮", "role_id": 1526800480007880845},
            {"label": "Anime Fan", "emoji": "📺", "role_id": 1526800623419523072},
            {"label": "Movie Fan", "emoji": "🎬", "role_id": 1526801019458158642},
            {"label": "Music Fan", "emoji": "🎧", "role_id": 1526801165692702842},
            {"label": "Book Worm", "emoji": "📚", "role_id": 1528897494400897066},   # ← حط ID
            {"label": "Artist", "emoji": "🎨", "role_id": 1528897791089315880},      # ← حط ID
            {"label": "Coder / Tech", "emoji": "💻", "role_id": 1528897975638822924},  # ← حط ID
            {"label": "Sports Fan", "emoji": "⚽", "role_id": 1528898014863691996},  # ← حط ID
        ],
        "🔔 إشعارات (Pings)": [
            {"label": "News Ping", "emoji": "📰", "role_id": 1528916802510389278},     # ← حط ID
            {"label": "Games Ping", "emoji": "🎮", "role_id": 1528916898262159440},    # ← حط ID
            {"label": "Movies Ping", "emoji": "🎬", "role_id": 1528916993304957019},   # ← حط ID
            {"label": "Anime Ping", "emoji": "📺", "role_id": 1528917042630230097},    # ← حط ID
            {"label": "Music Ping", "emoji": "🎧", "role_id": 1528917090071871588},    # ← حط ID
            {"label": "Announcements Ping", "emoji": "📢", "role_id": 1528917133839433851},  # ← حط ID
        ],
        "🌍 اللغة": [
            {"label": "Darija", "emoji": "🇲🇦", "role_id": 1528919040792334497},   # ← حط ID
            {"label": "English", "emoji": "🇬🇧", "role_id": 1528919152767664259},  # ← حط ID
            {"label": "Français", "emoji": "🇫🇷", "role_id": 1528919222888173699},  # ← حط ID
            {"label": "Italiano", "emoji": "🇮🇹", "role_id": 1528921431990337727},   # ← حط ID
            {"label": "Español", "emoji": "🇪🇸", "role_id": 1528921497421222028},    # ← حط ID
            {"label": "العربية", "emoji": "🇸🇦", "role_id": 1528921564354056362},  # ← حط ID
        ],
    }
    
    
    def get_ping_mention(label: str) -> str:
        """كيرجع نص الـ mention ديال رول (بحال '<@&123> ') إلا كان معمر فـ PICK_ROLES،
        وإلا كايرجع string فارغ (باش الرسالة تبعث عادي بلا مشكل)."""
        for roles_list in PICK_ROLES.values():
            for r in roles_list:
                if r["label"] == label and r["role_id"]:
                    return f"<@&{r['role_id']}> "
        return ""
    
    
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    
    intents = discord.Intents.default()
    intents.moderation = True  # audit-log gateway events + ban/unban security tracking
    intents.message_content = True
    intents.members = True
    intents.reactions = True
    intents.presences = True  # ← ضروري باش نقدرو نحسبو "Online Members"، خاصك تفعلها من Discord Developer Portal
    # (https://discord.com/developers/applications → البوت ديالك → Bot → Privileged Gateway Intents → Presence Intent)
    # ═══════ ملاحظة: command_prefix باقي محطوط تقنياً (discord.py كيطلبو)، ولكن
    # ماعادش كيتستعمل — bot.process_commands() تنيح فـ on_message، فـ "!" ماعادش
    # كيخدم. كاع الأوامر دابا Slash (/) بوحدها. ═══════
    bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
    
    user_memory = defaultdict(list)
    server_memory = []
    MAX_SERVER_MEMORY = 100
    learned_knowledge = []
    warns_db = {}
    spam_tracker = {}
    mute_tasks = {}
    _slash_synced = False  # باش ما نعاودوش sync ديال Slash Commands كل مرة on_ready يتلاق (reconnect)
    
# ORIGINAL SOURCE END
else:
    bot = bootstrap_component(__file__, __name__)
