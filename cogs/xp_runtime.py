# -*- coding: utf-8 -*-
"""Unchanged ordered source component: xp_runtime."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║   XP Settings — الإعدادات القابلة للتعديل من /xppanel   ║
    # ═══════════════════════════════════════════════════════
    # هاد الـ dict هو المصدر الحقيقي (source of truth) لكل قيم XP فالبوت وهو خدام.
    # كيتبدا بالقيم الافتراضية من فوق، ومن بعد كيتقرا فوقهم أي تبديل محفوظ فـ
    # xp_settings.json (يعني إلا بدلتي شي حاجة من /xppanel قبل، غادي تتحافظ حتى
    # بعد ريستارت البوت). ماكاينش داعي تبدل الكود، كامل التحكم من ديسكورد.
    XP_SETTINGS_FILE = os.path.join(DATA_DIR, "xp_settings.json")
    xp_settings = {
        "chat_min": XP_MIN_PER_MESSAGE,
        "chat_max": XP_MAX_PER_MESSAGE,
        "chat_cooldown": XP_COOLDOWN_SECONDS,
        "voice_per_interval": VOICE_XP_PER_INTERVAL,
        "voice_interval_minutes": VOICE_XP_INTERVAL_MINUTES,
        "voice_min_humans": VOICE_XP_MIN_HUMANS_IN_CHANNEL,
        "stream_per_interval": STREAM_XP_PER_INTERVAL,
        "afk_channel_per_interval": AFK_CHANNEL_XP_PER_INTERVAL,
        "afk_muted_per_interval": AFK_MUTED_XP_PER_INTERVAL,
        "afk_daily_cap": AFK_XP_DAILY_CAP,
        "level_xp_multiplier": 1.0,   # ← 1.0 = عادي، 0.5 = يهبط المستويات بنص الـ XP المطلوب، 2.0 = يضاعفو
    }
    
    
    def load_xp_settings():
        global xp_settings
        try:
            with open(XP_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            xp_settings.update({k: v for k, v in saved.items() if k in xp_settings})
            print(f"[XP-SETTINGS] تحملات الإعدادات المحفوظة: {xp_settings}")
        except FileNotFoundError:
            print("[XP-SETTINGS] ماكاينش إعدادات محفوظة، غادي نستعملو القيم الافتراضية من الكود.")
        except Exception as e:
            print(f"[XP-SETTINGS] خطأ فـ التحميل: {e}")
    
    
    def save_xp_settings():
        try:
            with open(XP_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(xp_settings, f, ensure_ascii=False)
        except Exception as e:
            print(f"[XP-SETTINGS] خطأ فـ الحفظ: {e}")
    
    
    load_xp_settings()
    
    # ═══════════════════════════════════════════════════════
    # ║   عداد يومي لـ XP ديال AFK (باش السقف اليومي يخدم)     ║
    # ═══════════════════════════════════════════════════════
    # كيتصيفط أوتوماتيكيا كل نهار جديد (حسب UTC). كيتحفظ فـ الديسك باش السقف
    # يبقى محترم حتى إلا تعاود ريستارت البوت وسط النهار.
    AFK_XP_DAILY_FILE = os.path.join(DATA_DIR, "afk_xp_daily.json")
    afk_xp_daily = {"date": "", "users": {}}
    
    
    def load_afk_xp_daily():
        global afk_xp_daily
        try:
            with open(AFK_XP_DAILY_FILE, "r", encoding="utf-8") as f:
                afk_xp_daily = json.load(f)
        except FileNotFoundError:
            afk_xp_daily = {"date": "", "users": {}}
        except Exception as e:
            print(f"[AFK-XP] خطأ فـ التحميل: {e}")
            afk_xp_daily = {"date": "", "users": {}}
    
    
    def save_afk_xp_daily():
        try:
            with open(AFK_XP_DAILY_FILE, "w", encoding="utf-8") as f:
                json.dump(afk_xp_daily, f, ensure_ascii=False)
        except Exception as e:
            print(f"[AFK-XP] خطأ فـ الحفظ: {e}")
    
    
    def _afk_reset_if_new_day():
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if afk_xp_daily.get("date") != today:
            afk_xp_daily["date"] = today
            afk_xp_daily["users"] = {}
            save_afk_xp_daily()
    
    
    def afk_xp_used_today(guild_id: int, user_id: int) -> int:
        _afk_reset_if_new_day()
        return int(afk_xp_daily["users"].get(f"{guild_id}:{user_id}", 0))
    
    
    def afk_xp_allowed(guild_id: int, user_id: int, wanted: int) -> int:
        """كيرجع شحال من XP مسموح لهاد العضو ياخد دابا (كيحترم السقف اليومي).
        0 = وصل للسقف ديال النهار."""
        cap = int(xp_settings.get("afk_daily_cap", 0) or 0)
        if cap <= 0:
            return wanted
        used = afk_xp_used_today(guild_id, user_id)
        return max(0, min(wanted, cap - used))
    
    
    def bump_afk_xp_used(guild_id: int, user_id: int, amount: int):
        _afk_reset_if_new_day()
        key = f"{guild_id}:{user_id}"
        afk_xp_daily["users"][key] = afk_xp_used_today(guild_id, user_id) + amount
        save_afk_xp_daily()
    
    
    load_afk_xp_daily()
    
    
    # ═══════════════════════════════════════════════════════
    # ║   Auto AFK Move + Auto Return                         ║
    # ║   Self-Deafen X min → AFK | Undeafen → previous room ║
    # ═══════════════════════════════════════════════════════
    AFK_DEAF_TRACK_FILE = os.path.join(DATA_DIR, "afk_deafen_tracking.json")
    AFK_AUTO_RETURN_FILE = os.path.join(DATA_DIR, "afk_auto_return.json")
    # tracking: {"guild_id:user_id": {"since": unix_ts, "channel_id": voice_channel_id}}
    afk_deafen_tracking = {}
    # returns: {"guild_id:user_id": {"channel_id": previous_voice_id, "moved_at": unix_ts}}
    afk_auto_return = {}
    
    
    def load_afk_deafen_tracking():
        global afk_deafen_tracking
        try:
            with open(AFK_DEAF_TRACK_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            afk_deafen_tracking = data if isinstance(data, dict) else {}
        except FileNotFoundError:
            afk_deafen_tracking = {}
        except Exception as e:
            print(f"[AFK-AUTO-MOVE] خطأ فـ تحميل التتبع: {e}")
            afk_deafen_tracking = {}
    
    
    def save_afk_deafen_tracking():
        try:
            with open(AFK_DEAF_TRACK_FILE, "w", encoding="utf-8") as f:
                json.dump(afk_deafen_tracking, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AFK-AUTO-MOVE] خطأ فـ حفظ التتبع: {e}")
    
    
    def load_afk_auto_return():
        global afk_auto_return
        try:
            with open(AFK_AUTO_RETURN_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            afk_auto_return = data if isinstance(data, dict) else {}
        except FileNotFoundError:
            afk_auto_return = {}
        except Exception as e:
            print(f"[AFK-AUTO-RETURN] خطأ فـ تحميل السجل: {e}")
            afk_auto_return = {}
    
    
    def save_afk_auto_return():
        try:
            with open(AFK_AUTO_RETURN_FILE, "w", encoding="utf-8") as f:
                json.dump(afk_auto_return, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[AFK-AUTO-RETURN] خطأ فـ حفظ السجل: {e}")
    
    
    def _afk_deafen_key(guild_id: int, user_id: int) -> str:
        return f"{guild_id}:{user_id}"
    
    
    def get_afk_move_target(guild: discord.Guild) -> Optional[discord.VoiceChannel]:
        """الروم اللي غادي نهبطو ليها AFK: الرسمية أولاً، وإلا أول ID صالح فـ AFK_CHANNEL_IDS."""
        if guild.afk_channel and isinstance(guild.afk_channel, discord.VoiceChannel):
            return guild.afk_channel
        for channel_id in AFK_CHANNEL_IDS:
            channel = guild.get_channel(channel_id)
            if isinstance(channel, discord.VoiceChannel):
                return channel
        return None
    
    
    def _channel_is_afk_target(channel: Optional[discord.VoiceChannel], guild: discord.Guild) -> bool:
        if not channel:
            return False
        if guild.afk_channel and channel.id == guild.afk_channel.id:
            return True
        return channel.id in AFK_CHANNEL_IDS
    
    
    def _has_pending_afk_return_to_channel(guild_id: int, channel_id: int) -> bool:
        """كيحمي Temp Room من الحذف إلا شي عضو تهبط منها للـ AFK ومازال خاصو يرجع ليها."""
        if not AFK_AUTO_RETURN_ENABLED or not AFK_AUTO_RETURN_KEEP_TEMP_ROOM:
            return False
        prefix = f"{guild_id}:"
        return any(
            key.startswith(prefix) and int(rec.get("channel_id", 0) or 0) == channel_id
            for key, rec in afk_auto_return.items()
        )
    
    
    async def _cleanup_abandoned_afk_origin(guild: discord.Guild, channel_id: int):
        """إلا تلغى Auto Return والروم الأصلية Temp وبقات خاوية، نمسحوها باش ما تبقاش orphan."""
        channel = guild.get_channel(channel_id)
        if not isinstance(channel, discord.VoiceChannel):
            return
        if str(channel.id) not in temp_voice_channels:
            return
        if has_human_members(channel.members) or _has_pending_afk_return_to_channel(guild.id, channel.id):
            return
        await cleanup_temp_voice_room_if_empty(
            channel,
            grace_seconds=0,
            reason="Auto AFK Return تلغى والروم المؤقتة بقات بلا Humans",
        )
    
    
    def _can_auto_return_to_channel(member: discord.Member, channel: discord.VoiceChannel) -> bool:
        """يحترم ACL ديال Temp Rooms؛ Administrator ماكيستعملش هنا باش يتجاوز قرار مول الروم."""
        if is_temp_voice_channel(channel):
            rec = get_temp_voice_acl(channel, create=False)
            if rec:
                uid = member.id
                # Server Owner مسموح ليه يرجع؛ الاستثناء هنا غير من ACL، ماشي من Auto-AFK.
                if is_temp_voice_protected_target(member):
                    return True
                if uid in rec.get("blocked", []) or uid in rec.get("denied", []):
                    return False
                owner_id = int(rec.get("owner_id", 0) or 0)
                if rec.get("private") and uid != owner_id and uid not in rec.get("allowed", []):
                    return False
        perms = channel.permissions_for(member)
        return bool(perms.view_channel and perms.connect)
    
    
    def update_afk_deafen_tracking(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """
        كيتحسب AFK غير Self-Deafen الحقيقي (self_deaf=True) لمدة متواصلة.
        - كيتطبق على الجميع، حتى Server Owner
        - Server Deafen بوحدو ما كيتحسبش
        - تبديل الروم وهو Self-Deaf كيرجع العداد للصفر
        - Undeafen / خروج من voice / الدخول لروم AFK كيمسح العداد
        """
        key = _afk_deafen_key(member.guild.id, member.id)
    
        if not AFK_AUTO_MOVE_ENABLED:
            if afk_deafen_tracking.pop(key, None) is not None:
                save_afk_deafen_tracking()
            return
    
        after_channel = after.channel if isinstance(after.channel, discord.VoiceChannel) else None
        if not after_channel or not after.self_deaf or _channel_is_afk_target(after_channel, member.guild):
            if afk_deafen_tracking.pop(key, None) is not None:
                save_afk_deafen_tracking()
            return
    
        channel_changed = (before.channel is None or before.channel.id != after_channel.id)
        just_deafened = not bool(before.self_deaf) and bool(after.self_deaf)
    
        if key not in afk_deafen_tracking or channel_changed or just_deafened:
            afk_deafen_tracking[key] = {
                "since": int(datetime.now().timestamp()),
                "channel_id": after_channel.id,
            }
            save_afk_deafen_tracking()
    
    
    def reconcile_afk_deafen_tracking(guild: discord.Guild):
        """بعد restart: نحافظ على timer لأي عضو، بما فيه Owner، إلا مازال Self-Deaf فنفس الروم."""
        changed = False
        active_keys = set()
        now_ts = int(datetime.now().timestamp())
    
        for channel in guild.voice_channels:
            if _channel_is_afk_target(channel, guild):
                continue
            for member in channel.members:
                if member.bot:
                    continue
                if not member.voice or not member.voice.self_deaf:
                    continue
                key = _afk_deafen_key(guild.id, member.id)
                active_keys.add(key)
                rec = afk_deafen_tracking.get(key)
                if not rec or int(rec.get("channel_id", 0)) != channel.id:
                    afk_deafen_tracking[key] = {"since": now_ts, "channel_id": channel.id}
                    changed = True
    
        prefix = f"{guild.id}:"
        for key in list(afk_deafen_tracking.keys()):
            if key.startswith(prefix) and key not in active_keys:
                afk_deafen_tracking.pop(key, None)
                changed = True
    
        if changed:
            save_afk_deafen_tracking()
    
    
    def reconcile_afk_auto_return(guild: discord.Guild):
        """بعد restart: نخلي return غير لعضو مازال فعلاً فـ AFK والروم الأصلية مازالت موجودة."""
        changed = False
        prefix = f"{guild.id}:"
        for key, rec in list(afk_auto_return.items()):
            if not key.startswith(prefix):
                continue
            try:
                user_id = int(key.split(":", 1)[1])
            except (ValueError, IndexError):
                afk_auto_return.pop(key, None)
                changed = True
                continue
            member = guild.get_member(user_id)
            origin = guild.get_channel(int(rec.get("channel_id", 0) or 0))
            current = member.voice.channel if member and member.voice else None
            if (not member or member.bot or not isinstance(origin, discord.VoiceChannel)
                    or not _channel_is_afk_target(current, guild)):
                afk_auto_return.pop(key, None)
                changed = True
        if changed:
            save_afk_auto_return()
    
    
    async def handle_afk_auto_return(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """ملي عضو نقله البوت للـ AFK يفك Self-Deafen، يرجعو للروم اللي كان فيها قبل."""
        if not AFK_AUTO_RETURN_ENABLED:
            return False
        key = _afk_deafen_key(member.guild.id, member.id)
        rec = afk_auto_return.get(key)
        if not rec:
            return False
    
        before_channel = before.channel if isinstance(before.channel, discord.VoiceChannel) else None
        after_channel = after.channel if isinstance(after.channel, discord.VoiceChannel) else None
    
        # إلا خرج/بدل AFK بيدو، نلغي الرجوع القديم. إذا بقى Deaf فروم أخرى، tracking غادي يبدا من جديد.
        if not after_channel or not _channel_is_afk_target(after_channel, member.guild):
            origin_id = int(rec.get("channel_id", 0) or 0)
            afk_auto_return.pop(key, None)
            save_afk_auto_return()
            await _cleanup_abandoned_afk_origin(member.guild, origin_id)
            return False
    
        just_undeafened = bool(before.self_deaf) and not bool(after.self_deaf)
        if not (_channel_is_afk_target(before_channel, member.guild) and just_undeafened):
            return False
    
        origin_id = int(rec.get("channel_id", 0) or 0)
        origin = member.guild.get_channel(origin_id)
        # نمسحو قبل move_to باش الـ voice event الجديد ما يعاودش نفس العملية.
        afk_auto_return.pop(key, None)
        save_afk_auto_return()
    
        if not isinstance(origin, discord.VoiceChannel):
            return False
        if not _can_auto_return_to_channel(member, origin):
            try:
                await member.send(f"⚠️ ماقدرتش نرجعك لـ **{origin.name}** حيت الدخول ليها ماعادش مسموح ليك.")
            except discord.HTTPException:
                pass
            await _cleanup_abandoned_afk_origin(member.guild, origin.id)
            return False
    
        try:
            await member.move_to(origin, reason="Auto AFK Return: العضو فك Self-Deafen فـ AFK")
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[AFK-AUTO-RETURN] ماقدرتش نرجع {member} لـ {origin}: {e}")
            await _cleanup_abandoned_afk_origin(member.guild, origin.id)
            return False
    
        try:
            await log_action(
                member.guild,
                "🔙 Auto AFK Return",
                f"**العضو:** {member.mention}\n**رجع إلى:** {origin.mention}\n"
                f"**السبب:** فك Self-Deafen وهو فـ AFK",
                discord.Color.green()
            )
        except Exception:
            pass
        return True
    
    
    load_afk_deafen_tracking()
    load_afk_auto_return()
    
    
    @tasks.loop(seconds=AFK_AUTO_MOVE_CHECK_SECONDS)
    async def afk_auto_move_loop():
        """كيهبط أي عضو (حتى Owner) بقى Self-Deaf المدة المحددة، ويحفظ الروم باش يرجعو منين يفك Deafen."""
        if not AFK_AUTO_MOVE_ENABLED:
            return
    
        now_ts = int(datetime.now().timestamp())
        required_seconds = max(1, int(AFK_AUTO_MOVE_AFTER_MINUTES * 60))
        tracking_changed = False
        return_changed = False
    
        for guild in bot.guilds:
            target = get_afk_move_target(guild)
            if not target:
                continue
    
            prefix = f"{guild.id}:"
            for key, rec in list(afk_deafen_tracking.items()):
                if not key.startswith(prefix):
                    continue
                try:
                    user_id = int(key.split(":", 1)[1])
                except (ValueError, IndexError):
                    afk_deafen_tracking.pop(key, None)
                    tracking_changed = True
                    continue
    
                member = guild.get_member(user_id)
                if not member or member.bot:
                    afk_deafen_tracking.pop(key, None)
                    tracking_changed = True
                    continue
    
                voice = member.voice
                current_channel = voice.channel if voice else None
                if (not voice or not current_channel or not voice.self_deaf
                        or _channel_is_afk_target(current_channel, guild)):
                    afk_deafen_tracking.pop(key, None)
                    tracking_changed = True
                    continue
    
                if int(rec.get("channel_id", 0)) != current_channel.id:
                    rec["channel_id"] = current_channel.id
                    rec["since"] = now_ts
                    tracking_changed = True
                    continue
    
                since = int(rec.get("since", now_ts))
                if now_ts - since < required_seconds:
                    continue
    
                old_channel = current_channel
                # نسجلو الروم قبل النقل باش cleanup ديال Temp Room يشوفها محمية ومايحذفهاش.
                afk_auto_return[key] = {"channel_id": old_channel.id, "moved_at": now_ts}
                save_afk_auto_return()
                return_changed = True
    
                try:
                    await member.move_to(target, reason=f"Auto AFK: Self-Deafen لمدة {AFK_AUTO_MOVE_AFTER_MINUTES} دقيقة")
                except (discord.Forbidden, discord.HTTPException) as e:
                    afk_auto_return.pop(key, None)
                    save_afk_auto_return()
                    print(f"[AFK-AUTO-MOVE] ماقدرتش نهبط {member} لـ {target}: {e}")
                    continue
    
                afk_deafen_tracking.pop(key, None)
                tracking_changed = True
                try:
                    await log_action(
                        guild,
                        "💤 Auto AFK Move",
                        f"**العضو:** {member.mention}\n"
                        f"**من:** {old_channel.mention}\n"
                        f"**إلى:** {target.mention}\n"
                        f"**السبب:** Self-Deafen متواصل لمدة {AFK_AUTO_MOVE_AFTER_MINUTES} دقيقة\n"
                        f"**Auto Return:** منين يفك Deafen فـ AFK يرجع للروم الأصلية",
                        discord.Color.greyple()
                    )
                except Exception:
                    pass
    
        if tracking_changed:
            save_afk_deafen_tracking()
        if return_changed:
            save_afk_auto_return()
    
    
    @afk_auto_move_loop.before_loop
    async def before_afk_auto_move_loop():
        await bot.wait_until_ready()
    
    
    @afk_auto_move_loop.error
    async def afk_auto_move_loop_error(error):
        print(f"[AFK-AUTO-MOVE] خطأ كبير فالـ loop: {error}")
    
    
    # ═══════════════════════════════════════════════════════
    # ║   XP Audit Log — سجل دائم لكل XP event (باش نكشفو الغش)   ║
    # ═══════════════════════════════════════════════════════
    # كل مرة كيتعطى XP (شات/فويس/afk) كيتسجل سطر JSON فهاد الملف.
    # ماكيتحيدش شي حاجة قديمة — فقط كيزاد. تقدر تفتحو بأي text editor
    # ولا تقراه بـ /xpaudit فديسكورد.
    XP_LOG_FILE = os.path.join(DATA_DIR, "xp_log.jsonl")
    
    # تتبع فالذاكرة (ماشي محفوظ فالديسك) باش نكتشفو سرعة مشبوهة فـ الوقت الحقيقي.
    # كل مفتاح (guild_id, user_id) → لائحة ديال الأوقات (datetime) ديال آخر XP events.
    xp_event_times: dict = defaultdict(list)
    # آخر مرة تبعث فيها تنبيه لهاد العضو، باش ما نبعتوش تنبيه على كل رسالة زايدة.
    xp_alert_cooldowns: dict = {}
    
    # ═══ إعدادات الكشف عن السرعة المشبوهة (بدلهم كيفما بغيتي) ═══
    XP_ANOMALY_WINDOW_MINUTES = 15   # ← النافذة الزمنية اللي كنشوفو فيها عدد الـ events
    XP_ANOMALY_THRESHOLD = 12        # ← إلا وصل عدد XP events لهاد الرقم فالنافذة ← تنبيه
    XP_ANOMALY_ALERT_COOLDOWN_MINUTES = 60  # ← ما نبعتوش تنبيه ثاني لنفس العضو قبل ما تعدي هاد المدة
    
    
    def log_xp_event(guild_id: int, user_id: int, source: str, amount: int,
                      channel_id: Optional[int] = None, new_total_level: Optional[int] = None):
        """كيسجل سطر واحد JSON فـ xp_log.jsonl لكل XP event. source مثلا:
        'chat', 'voice', 'afk_channel', 'afk_muted', 'stream'."""
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "guild": guild_id,
            "user": user_id,
            "source": source,
            "amount": amount,
            "channel": channel_id,
        }
        if new_total_level is not None:
            entry["level_after"] = new_total_level
        try:
            with open(XP_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[XP-AUDIT] خطأ فـ تسجيل XP event: {e}")
    
    
    async def check_xp_anomaly(member: discord.Member, guild: discord.Guild, source: str):
        """كيشوف واش هاد العضو كيربح XP بسرعة مشبوهة، وإلا كان كيبعث تنبيه لـ MOD_LOGS
        (بلا ما يعاقبو حتى واحد أوتوماتيكيا — غير كيعلم الإدارة باش تشيك بعينها)."""
        key = (guild.id, member.id)
        now = datetime.now()
        window = timedelta(minutes=XP_ANOMALY_WINDOW_MINUTES)
    
        times = [t for t in xp_event_times[key] if now - t < window]
        times.append(now)
        xp_event_times[key] = times
    
        if len(times) < XP_ANOMALY_THRESHOLD:
            return
    
        last_alert = xp_alert_cooldowns.get(key)
        if last_alert and (now - last_alert).total_seconds() < XP_ANOMALY_ALERT_COOLDOWN_MINUTES * 60:
            return
        xp_alert_cooldowns[key] = now
    
        await log_action(
            guild,
            "🚩 سرعة مشبوهة فـ كسب XP",
            f"**العضو:** {member.mention} (`{member.id}`)\n"
            f"**آخر مصدر:** `{source}`\n"
            f"**العدد:** {len(times)} XP events فـ آخر {XP_ANOMALY_WINDOW_MINUTES} دقيقة\n\n"
            f"ماشي بالضرورة غش — يمكن نشاط عادي مكثف. تقدر تشيك التفاصيل بـ `/xpaudit @{member.display_name}`.",
            discord.Color.orange()
        )
    
    
    def get_xp_audit_summary(guild_id: int, user_id: int, limit: int = 20) -> dict:
        """كيقرا xp_log.jsonl وكيرجع ملخص لعضو معين: التوزيع حسب المصدر + آخر events."""
        by_source = defaultdict(lambda: {"count": 0, "total": 0})
        events = []
        try:
            with open(XP_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except Exception:
                        continue
                    if e.get("guild") != guild_id or e.get("user") != user_id:
                        continue
                    src = e.get("source", "unknown")
                    by_source[src]["count"] += 1
                    by_source[src]["total"] += int(e.get("amount", 0))
                    events.append(e)
        except FileNotFoundError:
            pass
        events.sort(key=lambda e: e.get("ts", ""))
        return {
            "by_source": dict(by_source),
            "total_events": len(events),
            "total_xp": sum(int(e.get("amount", 0)) for e in events),
            "recent": events[-limit:],
        }
    
    
    # ═══════ Leaderboard أوتوماتيكي — تخزين ID ديال الرسالة (باش تتبدل ماشي تتبعث من جديد) ═══════
    LEADERBOARD_MESSAGE_FILE = os.path.join(DATA_DIR, "leaderboard_message.json")
    leaderboard_message_ids = {}  # {guild_id (str): message_id}
    
    
    def load_leaderboard_message_ids():
        global leaderboard_message_ids
        try:
            with open(LEADERBOARD_MESSAGE_FILE, "r", encoding="utf-8") as f:
                leaderboard_message_ids = json.load(f)
            print(f"[LEADERBOARD] تحمل {len(leaderboard_message_ids)} رسالة leaderboard محفوظة")
        except FileNotFoundError:
            print("[LEADERBOARD] ماكاينش رسالة leaderboard سابقة، غادي نبعثو وحدة جديدة")
        except Exception as e:
            print(f"[LEADERBOARD] خطأ فـ التحميل: {e}")
    
    
    def save_leaderboard_message_ids():
        try:
            with open(LEADERBOARD_MESSAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(leaderboard_message_ids, f, ensure_ascii=False)
        except Exception as e:
            print(f"[LEADERBOARD] خطأ فـ الحفظ: {e}")
    
    
    load_leaderboard_message_ids()
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
