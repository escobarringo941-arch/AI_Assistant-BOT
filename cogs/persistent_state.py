# -*- coding: utf-8 -*-
"""Unchanged ordered source component: persistent_state."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════ Anti-Raid: تتبع الأعضاء الجداد + حالة الـ Lockdown ═══════
    recent_joins = defaultdict(list)  # {guild_id: [datetime, datetime, ...]}
    raid_state = {}                   # {guild_id: {"active": bool, "previous_verification_level": ..., "revert_task": Task}}
    
    # ═══════════════════════════════════════════════════════
    # ║   نظام Case ID (سجل كامل لكل عقوبة برقم فريد)          ║
    # ═══════════════════════════════════════════════════════
    # كل عقوبة (warn/mute/kick/ban/unmute/unban/unwarn) كتاخد رقم Case فريد
    # ومتزايد (#1, #2, #3...)، وكتتسجل فـ cases.json باش تبقى محفوظة حتى
    # بعد ريستارت البوت. استعمل /history @user باش تشوف كاع الحالات ديال
    # عضو معين، ولا /case <رقم> باش تشوف حالة معينة بالتفصيل.
    CASES_FILE = os.path.join(DATA_DIR, "cases.json")
    cases_db = {"next_id": 1, "cases": {}}  # cases: {"1": {...}, "2": {...}}
    
    
    def load_cases():
        global cases_db
        try:
            with open(CASES_FILE, "r", encoding="utf-8") as f:
                cases_db = json.load(f)
            print(f"[CASES] تحمل {len(cases_db.get('cases', {}))} حالة محفوظة (التالية: #{cases_db.get('next_id', 1)})")
        except FileNotFoundError:
            print("[CASES] ماكاينش حالات سابقة، غادي نبداو من Case #1")
        except Exception as e:
            print(f"[CASES] خطأ فـ التحميل: {e}")
    
    
    def save_cases():
        try:
            with open(CASES_FILE, "w", encoding="utf-8") as f:
                json.dump(cases_db, f, ensure_ascii=False)
        except Exception as e:
            print(f"[CASES] خطأ فـ الحفظ: {e}")
    
    
    load_cases()
    
    # ═══════════════════════════════════════════════════════
    # ║   نظام Tickets (channels خاصة لكل مشكل/استفسار)         ║
    # ═══════════════════════════════════════════════════════
    TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
    tickets_db = {"next_id": 1, "open": {}}  # open: {channel_id (str): {id, opener_id, opened_at, claimed_by}}
    
    
    def load_tickets():
        global tickets_db
        try:
            with open(TICKETS_FILE, "r", encoding="utf-8") as f:
                tickets_db = json.load(f)
            print(f"[TICKETS] تحمل {len(tickets_db.get('open', {}))} ticket مفتوح")
        except FileNotFoundError:
            print("[TICKETS] ماكاينش tickets سابقين، غادي نبداو من Ticket #1")
        except Exception as e:
            print(f"[TICKETS] خطأ فـ التحميل: {e}")
    
    
    def save_tickets():
        try:
            with open(TICKETS_FILE, "w", encoding="utf-8") as f:
                json.dump(tickets_db, f, ensure_ascii=False)
        except Exception as e:
            print(f"[TICKETS] خطأ فـ الحفظ: {e}")
    
    
    def get_open_ticket_for_user(user_id: int):
        """كترجع (channel_id, record) ديال ticket مفتوح ديال هاد العضو، وإلا None"""
        for channel_id, record in tickets_db.get("open", {}).items():
            if record.get("opener_id") == user_id:
                return channel_id, record
        return None, None
    
    
    load_tickets()
    
    # ═══════════════════════════════════════════════════════
    # ║   نظام Applications (طلبات الانضمام لفريق الإدارة)      ║
    # ═══════════════════════════════════════════════════════
    APPLICATIONS_FILE = os.path.join(DATA_DIR, "applications.json")
    # applications: {"1": {applicant_id, answers, status, review_message_id, review_channel_id, submitted_at, decided_by, decided_at}}
    # last_rejected: {user_id (str): "YYYY-MM-DD HH:MM:SS"} — باش نحسبو الـ cooldown
    applications_db = {"next_id": 1, "applications": {}, "last_rejected": {}}
    
    
    def load_applications():
        global applications_db
        try:
            with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
                applications_db = json.load(f)
            applications_db.setdefault("last_rejected", {})
            print(f"[APPLICATIONS] تحمل {len(applications_db.get('applications', {}))} طلب محفوظ")
        except FileNotFoundError:
            print("[APPLICATIONS] ماكاينش طلبات سابقة، غادي نبداو من Application #1")
        except Exception as e:
            print(f"[APPLICATIONS] خطأ فـ التحميل: {e}")
    
    
    def save_applications():
        try:
            with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(applications_db, f, ensure_ascii=False)
        except Exception as e:
            print(f"[APPLICATIONS] خطأ فـ الحفظ: {e}")
    
    
    def find_application_by_message_id(message_id: int):
        """كترجع (app_id, record) ديال الطلب اللي رسالة المراجعة ديالو هي هاد الـ message_id، وإلا (None, None)"""
        for app_id, record in applications_db.get("applications", {}).items():
            if record.get("review_message_id") == message_id:
                return app_id, record
        return None, None
    
    
    def get_pending_application_for_user(user_id: int):
        for app_id, record in applications_db.get("applications", {}).items():
            if record.get("applicant_id") == user_id and record.get("status") == "pending":
                return app_id, record
        return None, None
    
    
    def application_cooldown_remaining(user_id: int) -> Optional[timedelta]:
        """كترجع الوقت الباقي فالـ cooldown (Timedelta) إلا العضو مازال ما يقدرش يعاود يقدم، وإلا None"""
        last = applications_db.get("last_rejected", {}).get(str(user_id))
        if not last:
            return None
        try:
            elapsed = datetime.now() - datetime.fromisoformat(last)
        except Exception:
            return None
        remaining = timedelta(hours=APPLICATIONS_COOLDOWN_HOURS) - elapsed
        return remaining if remaining.total_seconds() > 0 else None
    
    
    load_applications()
    
    # ═══════════════════════════════════════════════════════
    # ║              نظام Suggestions (اقتراحات الأعضاء)        ║
    # ═══════════════════════════════════════════════════════
    SUGGESTIONS_FILE = os.path.join(DATA_DIR, "suggestions.json")
    # suggestions: {"1": {author_id, text, status, message_id, channel_id, created_at, decided_by, decided_at, reason}}
    suggestions_db = {"next_id": 1, "suggestions": {}}
    
    
    def load_suggestions():
        global suggestions_db
        try:
            with open(SUGGESTIONS_FILE, "r", encoding="utf-8") as f:
                suggestions_db = json.load(f)
            print(f"[SUGGESTIONS] تحمل {len(suggestions_db.get('suggestions', {}))} اقتراح محفوظ")
        except FileNotFoundError:
            print("[SUGGESTIONS] ماكاينش اقتراحات سابقة، غادي نبداو من Suggestion #1")
        except Exception as e:
            print(f"[SUGGESTIONS] خطأ فـ التحميل: {e}")
    
    
    def save_suggestions():
        try:
            with open(SUGGESTIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(suggestions_db, f, ensure_ascii=False)
        except Exception as e:
            print(f"[SUGGESTIONS] خطأ فـ الحفظ: {e}")
    
    
    def find_suggestion_by_message_id(message_id: int):
        for sug_id, record in suggestions_db.get("suggestions", {}).items():
            if record.get("message_id") == message_id:
                return sug_id, record
        return None, None
    
    
    load_suggestions()
    
    # ═══════════════════════════════════════════════════════
    # ║        Phase 8 — نظام Birthdays (أعياد الميلاد)         ║
    # ═══════════════════════════════════════════════════════
    BIRTHDAYS_FILE = os.path.join(DATA_DIR, "birthdays.json")
    # birthdays: {"<user_id>": {"day": int, "month": int, "last_announced_year": int|null}}
    # role_holders: [user_id, ...] — العضاء اللي عندهم الرول ديال اليوم دابا، باش نحيدوه غدا
    birthdays_db = {"birthdays": {}, "role_holders": []}
    
    
    def load_birthdays():
        global birthdays_db
        try:
            with open(BIRTHDAYS_FILE, "r", encoding="utf-8") as f:
                birthdays_db = json.load(f)
            birthdays_db.setdefault("role_holders", [])
            print(f"[BIRTHDAYS] تحمل {len(birthdays_db.get('birthdays', {}))} عيد ميلاد محفوظ")
        except FileNotFoundError:
            print("[BIRTHDAYS] ماكاينش أعياد ميلاد محفوظين من قبل")
        except Exception as e:
            print(f"[BIRTHDAYS] خطأ فـ التحميل: {e}")
    
    
    def save_birthdays():
        try:
            with open(BIRTHDAYS_FILE, "w", encoding="utf-8") as f:
                json.dump(birthdays_db, f, ensure_ascii=False)
        except Exception as e:
            print(f"[BIRTHDAYS] خطأ فـ الحفظ: {e}")
    
    
    load_birthdays()
    
    # ═══════════════════════════════════════════════════════
    # ║   نظام Marry/Bestfriend (أزواج/أصدقاء) — 💌               ║
    # ═══════════════════════════════════════════════════════
    RELATIONSHIPS_FILE = os.path.join(DATA_DIR, "relationships.json")
    # marriages/bestfriends: {"pair_key": {"user_a": id, "user_b": id, "since": "YYYY-MM-DD HH:MM:SS"}}
    # pair_key = "min_id-max_id" باش يبقى فريد لكل زوج
    relationships_db = {"marriages": {}, "bestfriends": {}}
    
    
    def load_relationships():
        global relationships_db
        try:
            with open(RELATIONSHIPS_FILE, "r", encoding="utf-8") as f:
                relationships_db = json.load(f)
            relationships_db.setdefault("marriages", {})
            relationships_db.setdefault("bestfriends", {})
            print(f"[RELATIONSHIPS] تحمل {len(relationships_db['marriages'])} زواج و {len(relationships_db['bestfriends'])} صداقة")
        except FileNotFoundError:
            print("[RELATIONSHIPS] ماكاينش علاقات محفوظة من قبل")
        except Exception as e:
            print(f"[RELATIONSHIPS] خطأ فـ التحميل: {e}")
            relationships_db = {"marriages": {}, "bestfriends": {}}
    
    
    def save_relationships():
        try:
            with open(RELATIONSHIPS_FILE, "w", encoding="utf-8") as f:
                json.dump(relationships_db, f, ensure_ascii=False)
        except Exception as e:
            print(f"[RELATIONSHIPS] خطأ فـ الحفظ: {e}")
    
    
    def _pair_key(user_id_1: int, user_id_2: int) -> str:
        a, b = sorted([user_id_1, user_id_2])
        return f"{a}-{b}"
    
    
    def find_relationship(kind: str, user_id: int):
        """كترجع (pair_key, record) ديال أول علاقة كتلقاها للعضو (marriages ولا bestfriends)، وإلا (None, None).
        للـ marriages (علاقة وحدة بالضرورة) هادي كافية. للـ bestfriends خاصك find_all_relationships حيت ممكن يكون بزاف."""
        for key, record in relationships_db.get(kind, {}).items():
            if record.get("user_a") == user_id or record.get("user_b") == user_id:
                return key, record
        return None, None
    
    
    def find_all_relationships(kind: str, user_id: int):
        """كترجع لائحة [(pair_key, record), ...] ديال كل العلاقات ديال العضو من نوع معين.
        مفيدة للـ bestfriends حيت عضو وحد يقدر يكون عندو بزاف ديال الأصدقاء المقربين فنفس الوقت."""
        result = []
        for key, record in relationships_db.get(kind, {}).items():
            if record.get("user_a") == user_id or record.get("user_b") == user_id:
                result.append((key, record))
        return result
    
    
    def has_relationship_with(kind: str, user_id_1: int, user_id_2: int) -> bool:
        """واش كاينة ديجا علاقة (من هاد النوع) بالضبط بين هاد الجوج ديال الناس."""
        return _pair_key(user_id_1, user_id_2) in relationships_db.get(kind, {})
    
    
    def get_partner_id(record: dict, user_id: int) -> int:
        return record["user_b"] if record["user_a"] == user_id else record["user_a"]
    
    
    def create_relationship(kind: str, user_id_1: int, user_id_2: int) -> str:
        key = _pair_key(user_id_1, user_id_2)
        relationships_db.setdefault(kind, {})[key] = {
            "user_a": user_id_1, "user_b": user_id_2,
            "since": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "personal_role_ids": {}  # {"<user_id>": role_id} — الرول الشخصي بسمية الشريك، لكل واحد فيهم
        }
        save_relationships()
        return key
    
    
    def set_relationship_personal_roles(kind: str, pair_key: str, role_id_for_user: dict):
        """كتسجل الـ IDs ديال الرولات الشخصية (بسمية الشريك) باش نقدرو نحيدوهم/نمسحوهم منين تنتهي العلاقة.
        role_id_for_user: {user_id (int): role_id (int)}"""
        record = relationships_db.get(kind, {}).get(pair_key)
        if not record:
            return
        record.setdefault("personal_role_ids", {})
        for uid, rid in role_id_for_user.items():
            record["personal_role_ids"][str(uid)] = rid
        save_relationships()
    
    
    def end_relationship(kind: str, pair_key: str):
        relationships_db.get(kind, {}).pop(pair_key, None)
        save_relationships()
    
    
    def format_duration_since(since_str: str) -> str:
        try:
            since_dt = datetime.strptime(since_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return "—"
        delta = datetime.now() - since_dt
        days = delta.days
        if days < 1:
            hours = delta.seconds // 3600
            return f"{hours} ساعة" if hours > 0 else "دقايق قلال"
        if days < 30:
            return f"{days} يوم"
        if days < 365:
            months = days // 30
            return f"{months} شهر"
        years = days // 365
        remaining_months = (days % 365) // 30
        return f"{years} عام" + (f" و{remaining_months} شهر" if remaining_months else "")
    
    
    load_relationships()
    
    # ═══════ حساب البرج من التاريخ (يوم/شهر) ═══════
    ZODIAC_SIGNS = [
        # (key, الاسم بالعربية, emoji, (شهر البداية, يوم البداية), (شهر النهاية, يوم النهاية))
        ("capricorn", "الجدي", "♑", (12, 22), (1, 19)),
        ("aquarius", "الدلو", "♒", (1, 20), (2, 18)),
        ("pisces", "الحوت", "♓", (2, 19), (3, 20)),
        ("aries", "الحمل", "♈", (3, 21), (4, 19)),
        ("taurus", "الثور", "♉", (4, 20), (5, 20)),
        ("gemini", "الجوزاء", "♊", (5, 21), (6, 20)),
        ("cancer", "السرطان", "♋", (6, 21), (7, 22)),
        ("leo", "الأسد", "♌", (7, 23), (8, 22)),
        ("virgo", "العذراء", "♍", (8, 23), (9, 22)),
        ("libra", "الميزان", "♎", (9, 23), (10, 22)),
        ("scorpio", "العقرب", "♏", (10, 23), (11, 21)),
        ("sagittarius", "القوس", "♐", (11, 22), (12, 21)),
    ]
    
    
    def get_zodiac_sign(day: int, month: int):
        """كترجع (key, الاسم بالعربية, emoji) ديال البرج حسب اليوم والشهر، وإلا (None, None, None)"""
        for key, label, emoji, start, end in ZODIAC_SIGNS:
            start_month, start_day = start
            end_month, end_day = end
            if start_month == end_month:
                if month == start_month and start_day <= day <= end_day:
                    return key, label, emoji
            else:
                # البرج كيمتد عبر شهرين (بحال الجدي: 22 دجنبر - 19 يناير)
                if (month == start_month and day >= start_day) or (month == end_month and day <= end_day):
                    return key, label, emoji
        return None, None, None
    
    
    async def sync_zodiac_role(member: discord.Member, zodiac_key: Optional[str]):
        """كتبدل رول البرج ديال العضو: كتحيد أي رول برج قديم عندو (إلا بدل التاريخ)
        وكتعطيه الرول الجديد المطابق للبرج ديالو."""
        all_zodiac_role_ids = {rid for rid in ZODIAC_ROLE_IDS.values() if rid}
        if not all_zodiac_role_ids:
            return
        new_role_id = ZODIAC_ROLE_IDS.get(zodiac_key) if zodiac_key else None
        to_remove = [r for r in member.roles if r.id in all_zodiac_role_ids and r.id != new_role_id]
        try:
            if to_remove:
                await member.remove_roles(*to_remove, reason="تبديل رول البرج")
            if new_role_id:
                new_role = member.guild.get_role(new_role_id)
                if new_role and new_role not in member.roles:
                    await member.add_roles(new_role, reason="رول البرج حسب عيد الميلاد")
        except Exception:
            pass
    
    
    # ═══════════════════════════════════════════════════════
    # ║              Leveling System (XP + Levels)               ║
    # ═══════════════════════════════════════════════════════
    LEVELS_FILE = os.path.join(DATA_DIR, "levels.json")
    levels_db = {}  # {guild_id (str): {user_id (str): {"xp": int, "level": int}}}
    xp_cooldowns = {}  # {(guild_id, user_id): datetime آخر مرة خذا XP}
    
    
    def load_levels():
        global levels_db
        try:
            with open(LEVELS_FILE, "r", encoding="utf-8") as f:
                levels_db = json.load(f)
            print(f"[LEVELS] تحمل بيانات {sum(len(v) for v in levels_db.values())} عضو")
        except FileNotFoundError:
            print("[LEVELS] ماكاينش بيانات سابقة، غادي نبداو من الصفر")
        except Exception as e:
            print(f"[LEVELS] خطأ فـ التحميل: {e}")
    
    
    def save_levels():
        try:
            with open(LEVELS_FILE, "w", encoding="utf-8") as f:
                json.dump(levels_db, f, ensure_ascii=False)
        except Exception as e:
            print(f"[LEVELS] خطأ فـ الحفظ: {e}")
    
    
    def xp_needed_for_level(level: int) -> int:
        """صيغة كتخلي كل مستوى محتاج XP أكثر من لي قبلو (بحال MEE6 تقريباً).
        من بعد Level 30، كتزاد صعوبة إضافية (نمو أسرع) باش المستويات العالية
        يبقاو يستاهلو أكثر وقت/جهد. كتضرب فـ level_xp_multiplier (قابلة للتعديل
        من /xppanel) — 0.5 يهبط الكل بالنص، 2.0 يضاعف، إلخ."""
        base = 5 * (level ** 2) + 50 * level + 100
        if level >= 30:
            extra_levels = level - 30
            base += 15 * (extra_levels ** 2) + 200 * extra_levels
        multiplier = xp_settings.get("level_xp_multiplier", 1.0) if "xp_settings" in globals() else 1.0
        return max(1, round(base * multiplier))
    
    
    def get_user_level_data(guild_id: int, user_id: int) -> dict:
        g = levels_db.setdefault(str(guild_id), {})
        return g.setdefault(str(user_id), {"xp": 0, "level": 0})
    
    
    def total_xp_earned(data: dict) -> int:
        """XP الكلية اللي ربحها العضو من بداياتو (مجموع كل المستويات السابقة + التقدم الحالي)"""
        total = data["xp"]
        for lvl in range(data["level"]):
            total += xp_needed_for_level(lvl)
        return total
    
    
    def get_target_level_role(new_level: int):
        """كترجع (target_level, role_id) ديال أعلى threshold فـ LEVEL_ROLES اللي
        new_level وصل ليه ولا فاقو، وإلا (None, None) إلا مازال ماوصلش لحتى واحد."""
        eligible = [lvl for lvl in LEVEL_ROLES if lvl <= new_level]
        if not eligible:
            return None, None
        target_level = max(eligible)
        return target_level, LEVEL_ROLES[target_level]
    
    
    async def sync_level_roles(member: discord.Member, guild: discord.Guild, new_level: int):
        """كيخلي عند العضو غير الرول اللي كيمثل أعلى level وصل ليه (من LEVEL_ROLES)،
        وكيحيد أي رولات ديال levels تحتانية/فوقانية كانت عندو من قبل — يعني رول
        واحد بوحدو ديال الـ level فأي وقت (سواء صعد ولا هبط المستوى). كترجع
        (roles_added, roles_removed) — لائحتين ديال mentions."""
        all_level_role_ids = {rid for rid in LEVEL_ROLES.values()}
        _, target_role_id = get_target_level_role(new_level)
    
        roles_added, roles_removed = [], []
    
        to_remove = [r for r in member.roles if r.id in all_level_role_ids and r.id != target_role_id]
        if to_remove:
            try:
                await member.remove_roles(*to_remove, reason=f"Level Role Sync — دابا Level {new_level}")
                roles_removed = [r.mention for r in to_remove]
            except (discord.Forbidden, discord.HTTPException):
                pass
    
        if target_role_id:
            target_role = guild.get_role(target_role_id)
            if target_role and target_role not in member.roles:
                try:
                    await member.add_roles(target_role, reason=f"Level Role Sync — دابا Level {new_level}")
                    roles_added.append(target_role.mention)
                except (discord.Forbidden, discord.HTTPException):
                    pass
    
        return roles_added, roles_removed
    
    
    async def sync_all_level_member_roles(guild: discord.Guild):
        """Self-healing كامل:
        - كل عضو عندو غير أعلى LEVEL_ROLE كتوافق Level الحقيقي ديالو.
        - أي Role قديمة كتتحيد.
        - أي Role ناقصة كتتعطى.
        كيخدم بعد restart بلا ما نستناو العضو يكتب شي رسالة.
        """
        changed_members = 0
        errors = 0
        guild_levels = levels_db.get(str(guild.id), {})
    
        for member in guild.members:
            if member.bot:
                continue
            data = guild_levels.get(str(member.id), {"level": 0})
            level = max(0, int(data.get("level", 0) or 0))
            before_ids = {r.id for r in member.roles if r.id in set(LEVEL_ROLES.values())}
            try:
                added, removed = await sync_level_roles(member, guild, level)
                if added or removed:
                    changed_members += 1
            except Exception as e:
                errors += 1
                print(f"[LEVEL ROLE SYNC] خطأ مع {member} ({member.id}): {e}")
    
        print(
            f"[LEVEL ROLE SYNC] ✅ {guild.name}: تصلحو {changed_members} عضو"
            + (f" | أخطاء: {errors}" if errors else "")
        )
    
    
    # ═══════════════════════════════════════════════════════
    # ║   طبقة تخزين وإدارة رولات الـ Milestones (أوتوماتيكية) ║
    # ═══════════════════════════════════════════════════════
    MILESTONE_ROLES_FILE = os.path.join(DATA_DIR, "milestone_roles.json")
    # {"tier_roles": {"10": role_id, ...}, "legend_roles": {"user_id": role_id}}
    milestone_roles_db = {"tier_roles": {}, "legend_roles": {}}
    
    
    def load_milestone_roles():
        global milestone_roles_db
        try:
            with open(MILESTONE_ROLES_FILE, "r", encoding="utf-8") as f:
                milestone_roles_db = json.load(f)
        except FileNotFoundError:
            milestone_roles_db = {"tier_roles": {}, "legend_roles": {}}
        except Exception as e:
            print(f"[MILESTONES] خطأ فـ تحميل milestone_roles.json: {e}")
            milestone_roles_db = {"tier_roles": {}, "legend_roles": {}}
        milestone_roles_db.setdefault("tier_roles", {})
        milestone_roles_db.setdefault("legend_roles", {})
    
    
    def save_milestone_roles():
        try:
            with open(MILESTONE_ROLES_FILE, "w", encoding="utf-8") as f:
                json.dump(milestone_roles_db, f, ensure_ascii=False)
        except Exception as e:
            print(f"[MILESTONES] خطأ فـ حفظ milestone_roles.json: {e}")
    
    
    async def get_or_create_tier_role(guild: discord.Guild, level: int) -> Optional[discord.Role]:
        """كترجع الرول المشترك ديال هاد الـ tier (level 10, 15, 20...) — كتصاوبو أوتوماتيكياً
        أول مرة، وكتحطو مباشرة فوق الرول الأساسي ديال LEVEL_ROLES بنفس المستوى (إلا كاين) باش
        يبقاو مجموعين بجانب بعضياتهم فترتيب الرولات. (بادج/cosmetic بوحدها — الصلاحيات الحقيقية
        دابا كلها فرولات LEVEL_ROLES نفسها، شوف LEVEL_PERK_ADDITIONS)."""
        info = LEVEL_MILESTONES.get(level)
        if not info:
            return None
        stored_id = milestone_roles_db["tier_roles"].get(str(level))
        if stored_id:
            role = guild.get_role(stored_id)
            if role:
                return role
    
        try:
            role = await guild.create_role(
                name=info["name"][:100], color=discord.Color(info["color"]),
                hoist=info["hoist"], mentionable=False,
                reason=f"Milestone Level {level} — تصاوبات أوتوماتيكياً"
            )
            milestone_roles_db["tier_roles"][str(level)] = role.id
            save_milestone_roles()
            # نحاولو نحطوها جنب الرول الأساسي ديال نفس الـ level (تنظيم بصري، ماشي إجباري)
            base_role_id = LEVEL_ROLES.get(level)
            if base_role_id:
                base_role = guild.get_role(base_role_id)
                if base_role:
                    try:
                        await role.edit(position=base_role.position)
                    except (discord.Forbidden, discord.HTTPException):
                        pass
            return role
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[MILESTONES] ما قدرتش نصاوب رول Level {level}: {e}")
            return None
    
    
    async def get_or_create_legend_role(guild: discord.Guild, member: discord.Member) -> Optional[discord.Role]:
        """رول شخصي فريد (ماشي مشترك) لكل عضو يوصل لـ Level 100 — كل واحد رول ديالو بوحدو
        باش يقدر يسميه كيفما بغى بـ /legendtitle بلا ما يأثر على حتى واحد آخر."""
        stored_id = milestone_roles_db["legend_roles"].get(str(member.id))
        if stored_id:
            role = guild.get_role(stored_id)
            if role:
                return role
    
        info = LEVEL_MILESTONES[100]
        try:
            role = await guild.create_role(
                name=f"{info['name']} — {member.display_name}"[:100],
                color=discord.Color(info["color"]), hoist=True, mentionable=False,
                reason=f"Milestone Level 100 (شخصي) — {member}"
            )
            milestone_roles_db["legend_roles"][str(member.id)] = role.id
            save_milestone_roles()
            return role
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[MILESTONES] ما قدرتش نصاوب رول Legend لـ {member}: {e}")
            return None
    
    
    def apply_xp_boost(data: dict):
        """كتعطي/كتجدد بونيص XP مؤقت (LEVEL_MILESTONE_XP_BOOST_PERCENT% لمدة
        LEVEL_MILESTONE_XP_BOOST_DAYS أيام) — كتبدا من اللحظة اللي كيتكسب فيها، وإلا
        كان عندو بونيص قدام مازال ماساليش، كتمدد الوقت بلا ما تراكم النسبة."""
        data["xp_boost_multiplier"] = 1.0 + (LEVEL_MILESTONE_XP_BOOST_PERCENT / 100)
        data["xp_boost_expires"] = (datetime.now() + timedelta(days=LEVEL_MILESTONE_XP_BOOST_DAYS)).isoformat()
    
    
    def get_active_xp_multiplier(data: dict) -> float:
        """كترجع 1.0 (عادي) ولا 1.XX إلا كان عندو بونيص XP مازال ماساليش."""
        expires = data.get("xp_boost_expires")
        if not expires:
            return 1.0
        try:
            if datetime.now() < datetime.fromisoformat(expires):
                return data.get("xp_boost_multiplier", 1.0)
        except Exception:
            pass
        return 1.0
    
    
    async def apply_level_milestones(member: discord.Member, guild: discord.Guild,
                                      crossed_levels: list, data: dict) -> list:
        """كتخدم أوتوماتيكياً ملي عضو يعدي شي milestone (وحدة ولا بزاف فمرة وحدة إلا قفز
        بزاف ديال المستويات). كتصاوب/كتعطي الرول، كتفعل البونيصات، كتبعث الإعلانات.
        كترجع لائحة سطور (وصف مختصر) باش تتزاد فرسالة "مبروك" ديال level up."""
        perk_lines = []
        for level in sorted(crossed_levels):
            info = LEVEL_MILESTONES.get(level)
            if not info:
                continue
            perk = info.get("perk") or ""
    
            if level == 100:
                role = await get_or_create_legend_role(guild, member)
            else:
                role = await get_or_create_tier_role(guild, level)
            if role:
                try:
                    await member.add_roles(role, reason=f"Milestone Level {level}")
                except (discord.Forbidden, discord.HTTPException):
                    pass
    
            line = f"{info['name']} (Level {level})"
    
            if "xp_boost" in perk:
                apply_xp_boost(data)
                line += f" — 🚀 بونيص +{LEVEL_MILESTONE_XP_BOOST_PERCENT}% XP لمدة {LEVEL_MILESTONE_XP_BOOST_DAYS} أيام"
    
            if "poll" in perk:
                line += " — 🗳️ Create Poll تفتح ليك فـ #levels-info"
    
            if "bio" in perk:
                line += " — 📝 Bio تفتحات ليك فـ #levels-info"
    
            if "legend" in perk:
                line += " — 👑 رول شخصي فريد! سميه من Legend Title فـ #levels-info"
    
            perk_lines.append(line)
    
            if "announce" in perk:
                await _send_milestone_announcement(guild, member, level, info)
    
        save_levels()
        return perk_lines
    
    
    async def _send_milestone_announcement(guild: discord.Guild, member: discord.Member, level: int, info: dict):
        """إعلان كبير فـ #general — غير للـ milestones الكبار (50 و100) باش يبقى معنى للاحتفال."""
        channel_id = LEVEL_MILESTONE_ANNOUNCE_CHANNEL_ID
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        embed = discord.Embed(
            description=(
                f"## {info['name'].split(' ')[0]} {member.mention} وصل لـ **Level {level}**! {info['name'].split(' ')[0]}\n"
                f"### {info['name']}\n\nمبروك! 🎉"
            ),
            color=discord.Color(info["color"]), timestamp=datetime.now()
        )
        embed.set_image(url=member.display_avatar.url)
        embed.set_footer(text=SERVER_NAME)
        content = f"# {info['name'].split(' ')[0]} {member.display_name} — Level {level}! {info['name'].split(' ')[0]}"
        try:
            await channel.send(content=content, embed=embed)
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[MILESTONES] ما قدرتش نبعث الإعلان: {e}")
    
    
    load_milestone_roles()
    
    
    async def grant_xp_and_announce(member: discord.Member, guild: discord.Guild, amount: int,
                                     fallback_channel: Optional[discord.abc.Messageable] = None,
                                     source: str = "unknown"):
        """كتزيد XP للعضو (من رسالة ولا من Voice)، كتشوف واش صعد لمستوى جديد،
        كتعطي الرولات ديال LEVEL_ROLES، وكتبعث رسالة "مبروك" إلا صعد.
        نفس المنطق اللي كان مستعمل غير مع رسائل الشات، دابا مشترك بين النصين والـ Voice.
        'source' كيتسجل فـ xp_log.jsonl باش نقدرو نتبعو منين جاي كل XP (audit)."""
        if not bot_settings['leveling_enabled'] or not guild:
            return
    
        data = get_user_level_data(guild.id, member.id)
    
        # ═══ بونيص XP مؤقت (إلا كان عندو واحد فعال دابا من شي milestone سابق) ═══
        multiplier = get_active_xp_multiplier(data)
        if multiplier > 1.0:
            amount = round(amount * multiplier)
    
        prev_level = data["level"]
        data["xp"] += amount
    
        leveled_up = False
        while data["xp"] >= xp_needed_for_level(data["level"]):
            data["xp"] -= xp_needed_for_level(data["level"])
            data["level"] += 1
            leveled_up = True
    
        save_levels()
    
        # Self-healing صغير فكل XP event: إلا الرول تحيدات بالغلط، كترد مباشرة.
        new_level = data["level"]
        roles_added = []
        try:
            roles_added, _ = await sync_level_roles(member, guild, new_level)
        except Exception as e:
            print(f"[LEVEL ROLE SYNC] خطأ فـ grant_xp مع {member}: {e}")
    
        channel_id = getattr(fallback_channel, "id", None) if fallback_channel else None
        log_xp_event(guild.id, member.id, source, amount, channel_id=channel_id,
                     new_total_level=data["level"])
        try:
            await check_xp_anomaly(member, guild, source)
        except Exception as e:
            print(f"[XP-AUDIT] خطأ فـ check_xp_anomaly: {e}")
    
        if not leveled_up:
            return
    
        # ═══ Milestones (10 → 100) — أوتوماتيكي بالكامل ═══
        crossed_levels = [lvl for lvl in LEVEL_MILESTONES if prev_level < lvl <= new_level]
        milestone_lines = []
        if crossed_levels:
            try:
                milestone_lines = await apply_level_milestones(member, guild, crossed_levels, data)
            except Exception as e:
                print(f"[MILESTONES] خطأ فـ apply_level_milestones: {e}")
    
        target_channel = bot.get_channel(LEVEL_UP_CHANNEL_ID) if LEVEL_UP_CHANNEL_ID else fallback_channel
        if target_channel:
            desc = f"🎉 {member.mention} وصل/ات لـ **Level {new_level}**!"
            if roles_added:
                desc += f"\n🎁 حصل/ات على: {', '.join(roles_added)}"
            if milestone_lines:
                desc += "\n\n**🏅 مكافآت جديدة:**\n" + "\n".join(f"• {ln}" for ln in milestone_lines)
            embed = discord.Embed(description=desc, color=discord.Color.gold(), timestamp=datetime.now())
            embed.set_thumbnail(url=member.display_avatar.url)
            try:
                await target_channel.send(embed=embed)
            except Exception as e:
                print(f"[LEVELS] خطأ فـ بعث رسالة Level Up: {e}")
    
    
    load_levels()
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
