# -*- coding: utf-8 -*-
"""Unchanged ordered source component: settings_storage."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║   Bot Settings — إعدادات عامة قابلة للتعديل من /botpanel   ║
    # ═══════════════════════════════════════════════════════
    # نفس المبدأ ديال xp_settings: dict وحدة هي المصدر الحقيقي (source of truth)
    # لكل التبديلات والعتبات الكبيرة فالبوت، كتبدا بالقيم الافتراضية من فوق فالـ
    # CONFIG، ومن بعد كتقرا فوقهم أي تبديل محفوظ فـ bot_settings.json. التحكم كامل
    # من ديسكورد بالأمر /botpanel (Admin)، بلا ماتمس الكود ولا تعاود ريستارت البوت.
    BOT_SETTINGS_FILE = os.path.join(DATA_DIR, "bot_settings.json")
    bot_settings = {
        "leveling_enabled": LEVELING_ENABLED,
        "voice_xp_enabled": VOICE_XP_ENABLED,
        "join_to_create_enabled": JOIN_TO_CREATE_ENABLED,
        "welcome_card_enabled": WELCOME_CARD_ENABLED,
        "auto_translate_enabled": AUTO_TRANSLATE_ENABLED,
        "auto_react_enabled": AUTO_REACT_TRANSLATE_ENABLED,
        "auto_info_news": AUTO_INFO_NEWS_ENABLED,
        "auto_info_games": AUTO_INFO_GAMES_ENABLED,
        "auto_info_movies": AUTO_INFO_MOVIES_ENABLED,
        "auto_info_anime": AUTO_INFO_ANIME_ENABLED,
        "auto_info_music": AUTO_INFO_MUSIC_ENABLED,
        "anti_raid_enabled": ANTI_RAID_ENABLED,
        "raid_join_threshold": RAID_JOIN_THRESHOLD,
        "raid_join_interval_seconds": RAID_JOIN_INTERVAL_SECONDS,
        "raid_action": RAID_ACTION,
        "raid_lockdown_duration_minutes": RAID_LOCKDOWN_DURATION_MINUTES,
        "mute_after_warns": MUTE_AFTER_WARNS,
        "mute_duration_minutes": MUTE_DURATION_MINUTES,
        "kick_after_warns": KICK_AFTER_WARNS,
        "ban_after_warns": BAN_AFTER_WARNS,
    }
    
    
    def load_bot_settings():
        global bot_settings
        try:
            with open(BOT_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            bot_settings.update({k: v for k, v in saved.items() if k in bot_settings})
            print(f"[BOT-SETTINGS] تحملات الإعدادات المحفوظة: {bot_settings}")
        except FileNotFoundError:
            print("[BOT-SETTINGS] ماكاينش إعدادات محفوظة، غادي نستعملو القيم الافتراضية من الكود.")
        except Exception as e:
            print(f"[BOT-SETTINGS] خطأ فـ التحميل: {e}")
    
    
    def save_bot_settings():
        try:
            with open(BOT_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(bot_settings, f, ensure_ascii=False)
        except Exception as e:
            print(f"[BOT-SETTINGS] خطأ فـ الحفظ: {e}")
    
    
    load_bot_settings()
    
    # ═══════════════════════════════════════════════════════
    # ║   سجل المحتوى المنشور (باش ما يتعاودش تا شي حاجة)      ║
    # ═══════════════════════════════════════════════════════
    POSTED_HISTORY_FILE = os.path.join(DATA_DIR, "posted_history.json")
    
    posted_history = {
        "news": [],     # روابط الأخبار اللي تبعثات
        "games": [],    # slugs ديال الألعاب اللي تبعثات
        "movies": [],   # IMDB IDs ديال الأفلام اللي تبعثات
        "anime": [],    # mal_id ديال الأنميات اللي تبعثات
        "music": [],    # "artist|track" اللي تبعثات
    }
    
    MAX_HISTORY = {
        "news": 500,
        "games": 250,
        "movies": 250,
        "anime": 250,
        "music": 500,
    }
    
    
    def load_posted_history():
        """يقرا السجل ديال المحتوى المنشور من ملف JSON (إلا كان موجود)"""
        global posted_history
        try:
            with open(POSTED_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for key in posted_history:
                if isinstance(data.get(key), list):
                    posted_history[key] = data[key]
            print(f"[HISTORY] تحمل السجل: { {k: len(v) for k, v in posted_history.items()} }")
        except FileNotFoundError:
            print("[HISTORY] ماكاينش سجل سابق، غادي نبداو من الصفر")
        except Exception as e:
            print(f"[HISTORY] خطأ فـ التحميل: {e}")
    
    
    def save_posted_history():
        """يحفظ السجل ديال المحتوى المنشور فـ ملف JSON"""
        try:
            with open(POSTED_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(posted_history, f, ensure_ascii=False)
        except Exception as e:
            print(f"[HISTORY] خطأ فـ الحفظ: {e}")
    
    
    def is_posted(category: str, item_id: str) -> bool:
        return item_id in posted_history.get(category, [])
    
    
    def mark_posted(category: str, item_id: str):
        """يسجل حاجة كـ 'تبعثات' باش ما تتعاودش، ويقلّم السجل إلا كبر بزاف"""
        lst = posted_history.setdefault(category, [])
        if item_id not in lst:
            lst.append(item_id)
        limit = MAX_HISTORY.get(category, 300)
        if len(lst) > limit:
            posted_history[category] = lst[-limit:]
        save_posted_history()
    
    
    def reset_category_history(category: str):
        """كي تسالا كاع الاختيارات ديال شي category، كنبداو من جديد"""
        posted_history[category] = []
        save_posted_history()
        print(f"[HISTORY] {category}: سالات كاع الاختيارات، بدينا من جديد")
    
    
    load_posted_history()
    
    # ملاحظة: نظام Dropdown ماعادش محتاج يحفظ IDs ديال الرسائل فـ JSON،
    # لأن الـ View كتشتغل بـ custom_id ثابت (persistent view) — كتخدم
    # فـ أي رسالة وحتى بعد ريستارت البوت، بلا ما نحتاجو نخزنو شي حاجة.
    
    STATS_MESSAGE_FILE = os.path.join(DATA_DIR, "stats_message.json")
    stats_message_ids = {}  # {guild_id (str): message_id}
    
    
    def load_stats_message_ids():
        """يقرا ID ديال رسالة الـ status المحفوظة، باش يبدلها بدل ما يبعث وحدة جديدة كل مرة"""
        global stats_message_ids
        try:
            with open(STATS_MESSAGE_FILE, "r", encoding="utf-8") as f:
                stats_message_ids = json.load(f)
            print(f"[STATS] تحمل {len(stats_message_ids)} رسالة status محفوظة")
        except FileNotFoundError:
            print("[STATS] ماكاينش رسالة status سابقة، غادي نبعثو وحدة جديدة")
        except Exception as e:
            print(f"[STATS] خطأ فـ التحميل: {e}")
    
    
    def save_stats_message_ids():
        try:
            with open(STATS_MESSAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(stats_message_ids, f, ensure_ascii=False)
        except Exception as e:
            print(f"[STATS] خطأ فـ الحفظ: {e}")
    
    
    load_stats_message_ids()
    
    ADMIN_LIST_MESSAGE_FILE = os.path.join(DATA_DIR, "admin_list_message.json")
    admin_list_message_ids = {}  # {guild_id (str): message_id}
    
    
    def load_admin_list_message_ids():
        """يقرا ID ديال رسالة لائحة الإدارة المحفوظة، باش يبدلها بدل ما يبعث وحدة جديدة كل مرة"""
        global admin_list_message_ids
        try:
            with open(ADMIN_LIST_MESSAGE_FILE, "r", encoding="utf-8") as f:
                admin_list_message_ids = json.load(f)
            print(f"[ADMIN_LIST] تحمل {len(admin_list_message_ids)} رسالة لائحة محفوظة")
        except FileNotFoundError:
            print("[ADMIN_LIST] ماكاينش رسالة لائحة سابقة، غادي نبعثو وحدة جديدة")
        except Exception as e:
            print(f"[ADMIN_LIST] خطأ فـ التحميل: {e}")
    
    
    def save_admin_list_message_ids():
        try:
            with open(ADMIN_LIST_MESSAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(admin_list_message_ids, f, ensure_ascii=False)
        except Exception as e:
            print(f"[ADMIN_LIST] خطأ فـ الحفظ: {e}")
    
    
    load_admin_list_message_ids()
    
    
    # ═══════════════════════════════════════════════════════
    # ║                  نظام التذكيرات (Reminders)             ║
    # ═══════════════════════════════════════════════════════
    # كل واحد يقدر يصاوب تذكير لراسو بـ /remind <وقت> <رسالة>
    # مثال: /remind 10m اشرب الما  /  /remind 2h30m اجتماع  /  /remind 1d تذكير
    # البوت كيحفظ التذكيرات فـ ملف JSON باش ما تضيعش حتى ملي يعاود ريستارت.
    REMINDERS_FILE = os.path.join(DATA_DIR, "reminders.json")
    reminders = []  # [{id, user_id, channel_id, guild_id, message, remind_at, created_at}]
    next_reminder_id = 1
    
    
    def load_reminders():
        """يقرا التذكيرات المحفوظة من ملف JSON (إلا كانت موجودة)"""
        global reminders, next_reminder_id
        try:
            with open(REMINDERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                reminders = data
            if reminders:
                next_reminder_id = max(r.get("id", 0) for r in reminders) + 1
            print(f"[REMINDERS] تحمل {len(reminders)} تذكير محفوظ")
        except FileNotFoundError:
            print("[REMINDERS] ماكاينش تذكيرات سابقة، غادي نبداو من الصفر")
        except Exception as e:
            print(f"[REMINDERS] خطأ فـ التحميل: {e}")
    
    
    def save_reminders():
        """يحفظ التذكيرات فـ ملف JSON"""
        try:
            with open(REMINDERS_FILE, "w", encoding="utf-8") as f:
                json.dump(reminders, f, ensure_ascii=False)
        except Exception as e:
            print(f"[REMINDERS] خطأ فـ الحفظ: {e}")
    
    
    def parse_duration(text: str):
        """
        يحول صيغة بحال '10m' / '2h' / '1h30m' / '1d' / '45s' لـ timedelta.
        الوحدات: s=ثواني، m=دقايق، h=ساعات، d=أيام. كتقدر تخلط بينهم (بحال 1h30m).
        كيرجع None إلا الصيغة ماشي صحيحة.
        """
        cleaned = text.strip().lower().replace(" ", "")
        matches = re.findall(r'(\d+)(d|h|m|s)', cleaned)
        if not matches:
            return None
        # تأكد بلي الماتشات كيغطيو كامل النص (باش ما يقبلش حاجة غريبة زايدة)
        rebuilt = "".join(f"{num}{unit}" for num, unit in matches)
        if rebuilt != cleaned:
            return None
        units = {"d": "days", "h": "hours", "m": "minutes", "s": "seconds"}
        kwargs = {}
        for num, unit in matches:
            key = units[unit]
            kwargs[key] = kwargs.get(key, 0) + int(num)
        return timedelta(**kwargs)
    
    
    def parse_time_input(text: str):
        """
        كيقبل 3 صيغ ديال الوقت (باش كل واحد يحدد الوقت اللي بغى بالضبط):
        1) مدة نسبية:      10m / 2h / 1h30m / 1d   → بعد X من دابا
        2) وقت اليوم:      21:00                    → اليوم إلا مازال ماجاش، وإلا غدا
        3) تاريخ + وقت:    2026-07-25-21:00         → نهار محدد بالضبط
        كيرجع datetime إلا الصيغة صحيحة، وإلا None.
        """
        text = text.strip()
        now = datetime.now()
    
        # 1) مدة نسبية
        delta = parse_duration(text)
        if delta is not None and delta.total_seconds() > 0:
            return now + delta
    
        # 2) وقت اليوم بالساعة:دقيقة (HH:MM)
        m = re.match(r'^(\d{1,2}):(\d{2})$', text)
        if m:
            hour, minute = int(m.group(1)), int(m.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                return target
            return None
    
        # 3) تاريخ كامل: YYYY-MM-DD-HH:MM
        m = re.match(r'^(\d{4})-(\d{2})-(\d{2})-(\d{1,2}):(\d{2})$', text)
        if m:
            year, month, day, hour, minute = map(int, m.groups())
            try:
                return datetime(year, month, day, hour, minute)
            except ValueError:
                return None
    
        return None
    
    
    load_reminders()
    
    
    # ═══════════════════════════════════════════════════════
    # ║   لائحة الكلمات/الأفعال الممنوعة الديناميكية (Owner only) ║
    # ═══════════════════════════════════════════════════════
    
    def load_banned_lists():
        """يقرا الكلمات/الأفعال الممنوعة اللي تزادو بالأوامر من ملف JSON"""
        global BANNED_ACTIONS
        try:
            with open(BANNED_LISTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            banned_words_state["extra"] = data.get("extra_words", [])
            banned_words_state["removed"] = data.get("removed_words", [])
            BANNED_ACTIONS[:] = data.get("actions", [])
            print(f"[BANNED_LISTS] تحمل {len(banned_words_state['extra'])} كلمة إضافية، "
                  f"{len(banned_words_state['removed'])} كلمة محيدة، {len(BANNED_ACTIONS)} فعل ممنوع")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[BANNED_LISTS] خطأ فـ التحميل: {e}")
    
    
    def save_banned_lists():
        """يحفظ الكلمات/الأفعال الممنوعة الديناميكية فـ ملف JSON"""
        try:
            with open(BANNED_LISTS_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "extra_words": banned_words_state["extra"],
                    "removed_words": banned_words_state["removed"],
                    "actions": BANNED_ACTIONS,
                }, f, ensure_ascii=False)
        except Exception as e:
            print(f"[BANNED_LISTS] خطأ فـ الحفظ: {e}")
    
    
    def get_active_banned_words() -> list:
        """كترجع اللائحة الفعلية: الأساسية (ناقص لي تحيد) + الإضافية"""
        words = [w for w in BANNED_WORDS if w not in banned_words_state["removed"]]
        for w in banned_words_state["extra"]:
            if w not in words:
                words.append(w)
        return words
    
    
    load_banned_lists()
    
    
    # ═══════════════════════════════════════════════════════
    # ║   حفظ الرولات ديال العضو (باش يرجعو ليه ملي يرجع للسيرفر)   ║
    # ═══════════════════════════════════════════════════════
    # كل مرة عضو يخرج من السيرفر (كيك، بان، ولا خرج بنفسو) كنسجلو الرولات
    # اللي كانت عندو. ملي يرجع (بعد فك الحظر ولا رجع من بعد الكيك/الخروج)
    # كنعطيوه نفس الرولات مباشرة بلا ما يعاود Verification.
    MEMBER_ROLES_FILE = os.path.join(DATA_DIR, "member_roles.json")
    member_roles_data = {}  # {guild_id (str): {user_id (str): [role_id, ...]}}
    
    
    def load_member_roles():
        global member_roles_data
        try:
            with open(MEMBER_ROLES_FILE, "r", encoding="utf-8") as f:
                member_roles_data = json.load(f)
            print(f"[MEMBER_ROLES] تحمل بيانات الرولات ديال {sum(len(v) for v in member_roles_data.values())} عضو")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[MEMBER_ROLES] خطأ فـ التحميل: {e}")
    
    
    def save_member_roles():
        try:
            with open(MEMBER_ROLES_FILE, "w", encoding="utf-8") as f:
                json.dump(member_roles_data, f, ensure_ascii=False)
        except Exception as e:
            print(f"[MEMBER_ROLES] خطأ فـ الحفظ: {e}")
    
    
    def remember_member_roles(member: discord.Member):
        """كتسجل الرولات الحالية ديال العضو (ناقص @everyone) قبل ما يخرج
        (كيك، بان، ولا خروج عادي) باش يقدر يرجع ليهم ملي يرجع للسيرفر."""
        guild_id = str(member.guild.id)
        user_id = str(member.id)
        role_ids = [r.id for r in member.roles if r.id != member.guild.id]
        if role_ids:
            member_roles_data.setdefault(guild_id, {})[user_id] = role_ids
            save_member_roles()
    
    
    load_member_roles()
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
