# -*- coding: utf-8 -*-
"""Anti-raid, member lifecycle, message pipeline, and moderation commands.

Extracted mechanically from the legacy ai_bot.py.  Runtime state is attached
to bot_core's shared namespace so existing cross-system references keep the
same object identity and startup order.
"""

import bot_core as core

core.attach_namespace(globals())


async def trigger_raid_lockdown(guild: discord.Guild, reason: str, duration_minutes: int = None):
    """كيصعد verification_level ديال السيرفر لأعلى درجة مؤقتاً، وكيبعث تنبيه للإدارة."""
    state = raid_state.setdefault(guild.id, {})
    if state.get("active"):
        return False

    state["active"] = True
    state["previous_verification_level"] = guild.verification_level

    try:
        await guild.edit(verification_level=discord.VerificationLevel.highest, reason="Anti-Raid: Lockdown أوتوماتيكي")
    except Exception as e:
        print(f"[ANTI-RAID] خطأ فـ تصعيد verification level: {e}")

    channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
    if channel:
        mentions = " ".join(f"<@&{rid}>" for rid in EXEMPT_ROLE_IDS)
        embed = discord.Embed(
            title="🚨🚨 Anti-Raid: Lockdown مفعل!",
            description=(
                f"{reason}\n\n"
                f"✅ verification level تصعدات مؤقتاً لأعلى درجة.\n"
                f"⚠️ كل عضو جديد غادي يتـ **{'حظر' if bot_settings['raid_action'] == 'ban' else 'طرد'}** تلقائياً حتى يتسد الـ Lockdown.\n"
                f"استعمل `/unlockdown` باش تسدو يدوياً قبل الوقت، ولا `/raidstatus` باش تشوف الحالة."
            ),
            color=discord.Color.dark_red(),
            timestamp=datetime.now()
        )
        try:
            await channel.send(content=mentions or None, embed=embed)
        except Exception as e:
            print(f"[ANTI-RAID] خطأ فـ بعث التنبيه: {e}")

    duration = bot_settings['raid_lockdown_duration_minutes'] if duration_minutes is None else duration_minutes
    if duration and duration > 0:
        async def _auto_revert():
            await asyncio.sleep(duration * 60)
            if raid_state.get(guild.id, {}).get("active"):
                await end_raid_lockdown(guild, reason="انتهت المدة أوتوماتيكياً")
        state["revert_task"] = asyncio.create_task(_auto_revert())

    return True


async def end_raid_lockdown(guild: discord.Guild, reason: str = "يدوي") -> bool:
    state = raid_state.get(guild.id)
    if not state or not state.get("active"):
        return False

    prev_level = state.get("previous_verification_level", discord.VerificationLevel.medium)
    try:
        await guild.edit(verification_level=prev_level, reason="Anti-Raid: رجوع للحالة العادية")
    except Exception as e:
        print(f"[ANTI-RAID] خطأ فـ رجوع verification level: {e}")

    state["active"] = False
    task = state.get("revert_task")
    if task and not task.done():
        task.cancel()

    channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="✅ Anti-Raid: Lockdown تسد",
            description=f"**السبب:** {reason}\nverification level رجعت للحالة العادية.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"[ANTI-RAID] خطأ فـ بعث التنبيه: {e}")

    return True


async def _check_and_maybe_trigger_raid(guild: discord.Guild) -> bool:
    """كتزيد join جديد لتتبع الأعضاء الجداد، وكتشوف واش عدد الانضمامات
    الأخيرة وصل للعتبة (bot_settings['raid_join_threshold'] فـ bot_settings['raid_join_interval_seconds']).
    كترجع True إلا Lockdown تفعل دابا بالضبط (أول مرة)."""
    now = datetime.now()
    cutoff = now - timedelta(seconds=bot_settings['raid_join_interval_seconds'])
    joins = [t for t in recent_joins[guild.id] if t > cutoff]
    joins.append(now)
    recent_joins[guild.id] = joins

    if len(joins) >= bot_settings['raid_join_threshold']:
        state = raid_state.get(guild.id, {})
        if not state.get("active"):
            await trigger_raid_lockdown(
                guild,
                reason=f"🚨 {len(joins)} عضو دخلو فـ آخر {bot_settings['raid_join_interval_seconds']} ثانية (العتبة: {bot_settings['raid_join_threshold']})."
            )
            return True
    return False


def _load_font(size: int, bold: bool = True):
    """كتحاول تلقى font جميلة، بالأولوية للفونط اللي حطينا فـ assets/fonts/
    (باش تخدم فأي بيئة، حتى Railway/python-slim اللي ماعندهاش فونطات النظام).
    إلا ماكانتش، كتجرب فونطات النظام، وإلا رجعت للـ font الافتراضي ديال Pillow."""
    project_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(project_dir, "assets", "fonts", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


async def generate_welcome_card(member: discord.Member, member_count: int, returning: bool = False) -> Optional[io.BytesIO]:
    """كتصاوب صورة ترحيبية مخصصة (Welcome Card) فيها صورة العضو + اسمو + رقمو
    فالسيرفر. كترجع None إلا Pillow ماشي متوفرة أو وقع خطأ (باش الكود اللي
    كيسطاها يرجع للـ embed العادي بلا ما يطيح البوت)."""
    if not PIL_AVAILABLE or not bot_settings['welcome_card_enabled']:
        return None

    try:
        W, H = 1100, 420
        accent = WELCOME_CARD_ACCENT_RGB
        accent2 = WELCOME_CARD_ACCENT2_RGB
        dark = (13, 13, 18)

        # ═══════ الخلفية ═══════
        if WELCOME_CARD_BACKGROUND_PATH and os.path.exists(WELCOME_CARD_BACKGROUND_PATH):
            bg = Image.open(WELCOME_CARD_BACKGROUND_PATH).convert("RGB")
            bg = ImageOps.fit(bg, (W, H), method=Image.LANCZOS).convert("RGBA")
        else:
            # تدرج لوني قطري (diagonal) بين لونين، ممزوج مع الأسود باش يبان depth
            bg = Image.new("RGB", (W, H), dark)
            px = bg.load()
            diag = math.hypot(W, H)
            mix = 0.55
            for y in range(H):
                for x in range(0, W, 2):
                    t = max(0, min(1, (x + y) / diag))
                    r = int((accent[0] * (1 - t) + accent2[0] * t) * mix + dark[0] * (1 - mix))
                    g = int((accent[1] * (1 - t) + accent2[1] * t) * mix + dark[1] * (1 - mix))
                    b = int((accent[2] * (1 - t) + accent2[2] * t) * mix + dark[2] * (1 - mix))
                    px[x, y] = (r, g, b)
                    if x + 1 < W:
                        px[x + 1, y] = (r, g, b)
            bg = bg.convert("RGBA")

            # نقط زخرفية خفيفة (texture) فوق الخلفية
            dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ddraw = ImageDraw.Draw(dots)
            spacing = 34
            for yy in range(0, H, spacing):
                for xx in range(0, W, spacing):
                    ddraw.ellipse((xx, yy, xx + 2, yy + 2), fill=(255, 255, 255, 18))
            bg = Image.alpha_composite(bg, dots)

        # طبقة غامقة شفافة باش النص يبان مزيان فوق أي خلفية
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 60))
        card = Image.alpha_composite(bg, overlay)

        # إطار (frame) خفيف مضيء حول الكارطة
        frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(frame).rounded_rectangle((6, 6, W - 6, H - 6), radius=28, outline=(255, 255, 255, 60), width=3)
        card = Image.alpha_composite(card, frame)
        draw = ImageDraw.Draw(card)

        # ═══════ صورة العضو (Avatar) دائرية مع ظل + حلقة بتدرج ═══════
        avatar_size = 200
        avatar_x, avatar_y = 70, (H - avatar_size) // 2

        # ظل ناعم تحت الصورة
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        pad = 14
        ImageDraw.Draw(shadow).ellipse(
            (avatar_x - pad, avatar_y - pad + 10, avatar_x + avatar_size + pad, avatar_y + avatar_size + pad + 10),
            fill=(0, 0, 0, 120)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
        card = Image.alpha_composite(card, shadow)
        draw = ImageDraw.Draw(card)

        # حلقة بتدرج لوني حول الصورة (رسم أقواس ملونة متدرجة)
        ring_pad = 10
        ring_box = (avatar_x - ring_pad, avatar_y - ring_pad, avatar_x + avatar_size + ring_pad, avatar_y + avatar_size + ring_pad)
        steps = 40
        for i in range(steps):
            t = i / steps
            r = int(accent[0] * (1 - t) + accent2[0] * t)
            g = int(accent[1] * (1 - t) + accent2[1] * t)
            b = int(accent[2] * (1 - t) + accent2[2] * t)
            start = 360 * (i / steps) - 90
            end = 360 * ((i + 1) / steps) - 90
            draw.arc(ring_box, start=start, end=end, fill=(r, g, b, 255), width=8)
        draw.ellipse(ring_box, outline=(255, 255, 255, 90), width=2)

        try:
            avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
            avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        except Exception:
            avatar_img = Image.new("RGBA", (256, 256), accent + (255,))
        avatar_img = ImageOps.fit(avatar_img, (avatar_size, avatar_size), method=Image.LANCZOS)

        mask = Image.new("L", (avatar_size, avatar_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
        card.paste(avatar_img, (avatar_x, avatar_y), mask)
        draw = ImageDraw.Draw(card)

        # ═══════ badge صغيرة فوق الاسم ═══════
        text_x = avatar_x + avatar_size + 55
        badge_font = _load_font(20, bold=True)
        badge_text = "🔁 رجع للسيرفر" if returning else "✨ عضو جديد"
        bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
        btw, bth = bbox[2] - bbox[0], bbox[3] - bbox[1]
        badge_pad_x, badge_pad_y = 18, 10
        badge_y = 78
        draw.rounded_rectangle(
            (text_x, badge_y, text_x + btw + badge_pad_x * 2, badge_y + bth + badge_pad_y * 2),
            radius=16, fill=(255, 255, 255, 235)
        )
        draw.text((text_x + badge_pad_x, badge_y + badge_pad_y - 2), badge_text, font=badge_font, fill=accent + (255,))

        # ═══════ اسم العضو (كبير، بارز، بظل خفيف) ═══════
        name_font = _load_font(56, bold=True)
        display_name = member.display_name
        if len(display_name) > 18:
            display_name = display_name[:17] + "…"
        name_y = badge_y + bth + badge_pad_y * 2 + 22
        draw.text((text_x + 2, name_y + 2), display_name, font=name_font, fill=(0, 0, 0, 90))
        draw.text((text_x, name_y), display_name, font=name_font, fill=(255, 255, 255, 255))

        # ═══════ subtitle (اسم السيرفر + رقم العضو) ═══════
        sub_font = _load_font(24, bold=False)
        sub_y = name_y + 70
        sub_text = f"{SERVER_NAME}  •  العضو رقم #{member_count}"
        draw.text((text_x, sub_y), sub_text, font=sub_font, fill=(230, 230, 235, 230))

        buffer = io.BytesIO()
        card.convert("RGB").save(buffer, format="PNG")
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"[WELCOME_CARD] خطأ فـ صنع الصورة: {e}")
        return None






translated_messages_cache = {}  # {(message_id, lang_en): النص المترجم} — كيفادي إعادة الترجمة إلا رد بزاف ناس بنفس العلم


async def handle_flag_translation(payload: discord.RawReactionActionEvent,
                                   guild: discord.Guild, member: discord.Member):
    """كيترجم الرسالة اللي تحطات عليها reaction بعلم دولة، ويرد بإيمبيد فيه الترجمة."""
    channel = guild.get_channel(payload.channel_id) or bot.get_channel(payload.channel_id)
    if not channel:
        print(f"[AUTO-TRANSLATE] ❌ ما لقيتش channel بـ ID {payload.channel_id}")
        return
    try:
        message = await channel.fetch_message(payload.message_id)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
        print(f"[AUTO-TRANSLATE] ❌ ما قدرتش نجيب الرسالة (Forbidden/NotFound؟): {e}")
        return

    # ماكاينش نص (رسالة بلا محتوى، صورة وحدها، ولا حتى ترجمة سابقة ديالنا) → ماكاين والو نترجمو
    if message.author.bot or not message.content or not message.content.strip():
        print(f"[AUTO-TRANSLATE] ⏭️ تجاوزت الرسالة (بوت={message.author.bot}, بلا نص={not message.content})")
        return

    lang_display, lang_en = FLAG_TO_LANGUAGE[str(payload.emoji)]
    print(f"[AUTO-TRANSLATE] 🔄 كنترجم رسالة #{message.id} لـ {lang_en}...")
    cache_key = (message.id, lang_en)

    translated = translated_messages_cache.get(cache_key)
    if not translated:
        translated = await translate_text(message.content, lang_en)
        if not translated:
            print(f"[AUTO-TRANSLATE] ❌ translate_text رجع خاوي لـ رسالة #{message.id}")
            return
        translated_messages_cache[cache_key] = translated
        if len(translated_messages_cache) > 500:   # كنخليو الكاش ماكيكبرش بلا حدود
            translated_messages_cache.pop(next(iter(translated_messages_cache)))

    embed = discord.Embed(
        description=translated[:MAX_REPLY_LENGTH],
        color=discord.Color.blurple()
    )
    embed.set_author(
        name=f"🌐 ترجمة لـ {lang_display} — طلب/ات {member.display_name}",
        icon_url=member.display_avatar.url
    )
    try:
        await message.reply(embed=embed, mention_author=False)
    except discord.HTTPException:
        pass


async def maybe_auto_react_translate(message: discord.Message):
    """كيزيد الأعلام ديال AUTO_REACT_FLAGS أوتوماتيك على كل رسالة (إلا فيها نص)،
    باش العضو غير يكليكي على العلم بلا ما يقلب عليه/يكتبو بيدو."""
    if message.channel.id != TARGET_CHANNEL_ID:
        return
    if not bot_settings['auto_react_enabled'] or not bot_settings['auto_translate_enabled']:
        return
    if not message.content or not message.content.strip():
        return
    if AUTO_REACT_CHANNEL_IDS and message.channel.id not in AUTO_REACT_CHANNEL_IDS:
        return
    for flag in AUTO_REACT_FLAGS:
        try:
            await message.add_reaction(flag)
        except discord.HTTPException:
            pass








async def process_message_xp(message: discord.Message):
    """كتزيد XP للعضو ملي يهضر، وكتشوف واش صعد لمستوى جديد (ممكن أكثر من مستوى
    فمرة وحدة إلا خذا XP كثيرة). كتعطي الرولات ديال LEVEL_ROLES تلقائياً."""
    if not bot_settings['leveling_enabled'] or not message.guild:
        return

    if not isinstance(message.author, discord.Member):
        return

    key = (message.guild.id, message.author.id)
    now = datetime.now()
    last = xp_cooldowns.get(key)
    if last and (now - last).total_seconds() < xp_settings["chat_cooldown"]:
        return
    xp_cooldowns[key] = now

    gained = random.randint(xp_settings["chat_min"], xp_settings["chat_max"])
    await grant_xp_and_announce(message.author, message.guild, gained,
                                fallback_channel=message.channel, source="chat")











# ═══════════════════════════════════════════════════════
# ║        /case و /history — تصفح سجل الـ Cases            ║
# ═══════════════════════════════════════════════════════

CASE_ACTION_COLORS = {
    "⚠️": discord.Color.yellow(),
    "🔇": discord.Color.yellow(),
    "🔊": discord.Color.green(),
    "👢": discord.Color.orange(),
    "🚫": discord.Color.red(),
    "✅": discord.Color.green(),
}






# ═══════════════════════════════════════════════════════
# ║   OWNER ONLY — إدارة اللائحة الممنوعة (سري، ماشي فالقناة)  ║
# ═══════════════════════════════════════════════════════
# هاد الأوامر خاصة غير بالـ Owner (بواسطة الـ ID فـ OWNER_ID)، حتى
# الـ Admins والـ Moderators ما يقدروش يستعملوها. الرسالة ديال الأمر
# كتمسح مباشرة، والجواب كيوصل بـ DM للـ Owner فقط — باش حتى حد آخر فالسيرفر
# ما يشوف واش تزادت/تحيدت شي كلمة، وواش شكون دارها.











# ═══════════════════════════════════════════════════════
# ║   OWNER ONLY — تحكم كامل فالسيرفر (كتم/حظر/طرد)          ║
# ═══════════════════════════════════════════════════════
# هاد الأوامر منفصلة على /kick//ban//mute العاديين (اللي خدامين بالصلاحيات
# ديال Discord)، وخاصة غير بالـ Owner بواسطة الـ ID — حتى admin/mod ما
# يقدروش يستعملوها. الـ Admins والـ Moderators كيبقاو خدامين بالأوامر
# العادية فوق حسب الصلاحيات ديال الـ role ديالهم بحال ماكانو.











# ═══════════════════════════════════════════════════════
# ║        Anti-Raid — أوامر التحكم اليدوي (Admin/Owner)     ║
# ═══════════════════════════════════════════════════════


class CoreModerationCog(commands.Cog):
    """Discord command/event registration for this subsystem."""

    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance
        self.ai_chat_inflight = set()
        self.ai_chat_last_request = {}

    @commands.Cog.listener()
    async def on_member_join(self, member):
        # ═══════════════════════════════════════════════════════
        # ║              Anti-Raid Protection                       ║
        # ═══════════════════════════════════════════════════════
        if bot_settings['anti_raid_enabled']:
            raid_triggered_now = await _check_and_maybe_trigger_raid(member.guild)
            state = raid_state.get(member.guild.id, {})

            if state.get("active"):
                # Raid Mode مفعل → كل عضو جديد كيتطبق عليه bot_settings['raid_action'] مباشرة
                try:
                    if bot_settings['raid_action'] == "ban":
                        await member.ban(reason="Anti-Raid: Lockdown مفعل، عضو جديد تلقائياً")
                        action_label = "🚫 حظر تلقائي (Anti-Raid)"
                        color = discord.Color.dark_red()
                    else:
                        await member.kick(reason="Anti-Raid: Lockdown مفعل، عضو جديد تلقائياً")
                        action_label = "👢 طرد تلقائي (Anti-Raid)"
                        color = discord.Color.orange()

                    await log_case(
                        member.guild, action_label, action_label.split(" ")[0], color,
                        target=member, moderator=None,
                        reason="انضم خلال فترة Anti-Raid Lockdown",
                    )
                except discord.Forbidden:
                    print(f"[ANTI-RAID] ❌ ماقدرتش نطبق {bot_settings['raid_action']} على {member} — صلاحية ناقصة")
                except Exception as e:
                    print(f"[ANTI-RAID] خطأ: {e}")
                return  # ما نكملوش الترحيب/استرجاع الرولات لعضو تفلتر

            # تنبيه بسيط (بلا عقوبة) إلا كان الحساب جديد بزاف — حتى ملي Raid Mode ماشي مفعل
            account_age = datetime.now(member.created_at.tzinfo) - member.created_at
            if account_age < timedelta(hours=RAID_MIN_ACCOUNT_AGE_HOURS):
                await log_action(
                    member.guild,
                    "⚠️ حساب جديد بزاف",
                    f"**المستخدم:** {member.mention} ({member.name})\n"
                    f"**عمر الحساب:** {account_age}\n"
                    f"غير تنبيه — ماتديرش شي حاجة يدوياً إلا شكيتي فيه.",
                    discord.Color.orange()
                )

        guild_id = str(member.guild.id)
        user_id = str(member.id)
        saved_role_ids = member_roles_data.get(guild_id, {}).get(user_id)

        # ═══════ عضو رجع للسيرفر (بعد كيك/بان/خروج) — رجع ليه نفس الرولات ═══════
        if saved_role_ids:
            roles_to_add = []
            for rid in saved_role_ids:
                role = member.guild.get_role(rid)
                if role:
                    roles_to_add.append(role)

            restore_error = None
            if roles_to_add:
                try:
                    await member.add_roles(*roles_to_add, reason="استرجاع الرولات القديمة بعد الرجوع للسيرفر")
                except discord.Forbidden as e:
                    restore_error = str(e)

            welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
            if welcome_channel:
                embed = discord.Embed(
                    title=f"👋 مرحبا بيك مرة أخرى {member.display_name}!",
                    description="رجعنا ليك نفس الرولات اللي كانت عندك من قبل. 🎉",
                    color=discord.Color.blue(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text="GGMW9 | Welcome Back")
                card_buffer = await generate_welcome_card(member, member.guild.member_count, returning=True)
                if card_buffer:
                    file = discord.File(card_buffer, filename="welcome.png")
                    embed.set_image(url="attachment://welcome.png")
                    await welcome_channel.send(embed=embed, file=file)
                else:
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await welcome_channel.send(embed=embed)

            await log_action(
                member.guild,
                "🔁 عضو رجع للسيرفر",
                f"**المستخدم:** {member.mention} ({member.name})\n"
                f"**الرولات المسترجعة:** {', '.join(r.mention for r in roles_to_add) if roles_to_add else 'ماكانش عندو رولات صالحة باش ترجع'}"
                + (f"\n⚠️ **خطأ:** ما قدرتش نعطي بعض الرولات (صلاحية/ترتيب الرولات): {restore_error}" if restore_error else ""),
                discord.Color.blue()
            )
            return

        # ═══════ عضو جديد بصح — نظام Unverified/Welcome العادي ═══════
        unverified_role = member.guild.get_role(UNVERIFIED_ROLE_ID)
        if unverified_role:
            try:
                await member.add_roles(unverified_role)
            except discord.Forbidden:
                pass
        welcome_channel = bot.get_channel(WELCOME_CHANNEL_ID)
        if welcome_channel:
            embed = discord.Embed(
                title=f"👋 مرحبا بيك {member.display_name}!",
                description=(
                    f"واخا أخويا/أختي! **{SERVER_NAME}** هو السيرفر ديالك.\n\n"
                    f"**قبل ما تبدأ/ي:**\n"
                    f"1️⃣ قرا/ي القوانين فـ <#{RULES_CHANNEL_ID}>\n"
                    f"2️⃣ وافق/ي فـ <#{VERIFY_CHANNEL_ID}>\n"
                    f"3️⃣ استمتع/ي! 🎉"
                ),
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.set_footer(text="GGMW9 | Verification System")
            card_buffer = await generate_welcome_card(member, member.guild.member_count, returning=False)
            if card_buffer:
                file = discord.File(card_buffer, filename="welcome.png")
                embed.set_image(url="attachment://welcome.png")
                await welcome_channel.send(embed=embed, file=file)
            else:
                embed.set_thumbnail(url=member.display_avatar.url)
                await welcome_channel.send(embed=embed)
        try:
            welcome_dm = discord.Embed(
                title=f"👋 مرحبا بيك | أهلاً بك | Welcome | Bienvenue",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            welcome_dm.add_field(
                name="🇲🇦 بالدارجة",
                value=(
                    f"مرحبا بيك فـ **{SERVER_NAME}**!\n"
                    f"قبل ما تقدر/ي تهضر/ي فالسيرفر، خاصك توافق/ي على القوانين.\n"
                    f"سير/ي لـ <#{VERIFY_CHANNEL_ID}> وكليك على ✅\n"
                    f"شكرا! 🙏"
                ),
                inline=False
            )
            welcome_dm.add_field(
                name="🇸🇦 بالعربية الفصحى",
                value=(
                    f"مرحبًا بك في **{SERVER_NAME}**!\n"
                    f"قبل أن تتمكن من التحدث في السيرفر، يجب عليك الموافقة على القوانين.\n"
                    f"توجّه إلى <#{VERIFY_CHANNEL_ID}> واضغط على ✅\n"
                    f"شكرًا لك! 🙏"
                ),
                inline=False
            )
            welcome_dm.add_field(
                name="🇬🇧 In English",
                value=(
                    f"Welcome to **{SERVER_NAME}**!\n"
                    f"Before you can chat on the server, you need to agree to the rules.\n"
                    f"Go to <#{VERIFY_CHANNEL_ID}> and click ✅\n"
                    f"Thank you! 🙏"
                ),
                inline=False
            )
            welcome_dm.add_field(
                name="🇫🇷 En Français",
                value=(
                    f"Bienvenue sur **{SERVER_NAME}** !\n"
                    f"Avant de pouvoir discuter sur le serveur, vous devez accepter les règles.\n"
                    f"Rendez-vous dans <#{VERIFY_CHANNEL_ID}> et cliquez sur ✅\n"
                    f"Merci ! 🙏"
                ),
                inline=False
            )
            welcome_dm.set_footer(text=f"{SERVER_NAME} | Verification System")
            await member.send(embed=welcome_dm)
        except discord.Forbidden:
            pass
        await log_action(
            member.guild,
            "👤 عضو جديد (Unverified)",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**الحالة:** غير مفعل\n"
            f"**الدور:** {unverified_role.mention if unverified_role else 'N/A'}",
            discord.Color.orange()
        )

        # إذا كان عضو قديم ورجع، XP القديمة ديالو باقية:
        # Leaderboard كتعاود ترتبو فوراً حسب XP ديالو.
        try:
            await refresh_xp_leaderboard_now()
        except Exception as e:
            print(f"[LEADERBOARD] refresh بعد رجوع عضو فشل: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        # كنسجلو الرولات ديالو قبل ما يخرج (كيك، بان، ولا خرج بنفسو).
        # XP ما كنمسحوهاش: كتبقى محفوظة إلا رجع من بعد.
        remember_member_roles(member)
        await log_action(
            member.guild,
            "👋 عضو خرج",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**ID:** `{member.id}`",
            discord.Color.greyple()
        )

        # خرج من السيرفر → يتحيد فوراً من Top ويتحركو اللي تحتو لفوق.
        try:
            await refresh_xp_leaderboard_now()
        except Exception as e:
            print(f"[LEADERBOARD] refresh بعد خروج عضو فشل: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        guild = bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return

        # ═══════ الترجمة التلقائية بالـ Reaction (علم الدولة 🇬🇧🇫🇷) — كتخدم فأي channel ═══════
        if (
            payload.channel_id == TARGET_CHANNEL_ID
            and bot_settings['auto_translate_enabled']
            and str(payload.emoji) in FLAG_TO_LANGUAGE
        ):
            await handle_flag_translation(payload, guild, member)
            return

        # ═══════ Verification ═══════
        if payload.channel_id != VERIFY_CHANNEL_ID:
            return
        if str(payload.emoji) != "✅":
            return
        unverified_role = guild.get_role(UNVERIFIED_ROLE_ID)
        if unverified_role and unverified_role in member.roles:
            try:
                await member.remove_roles(unverified_role)
            except discord.Forbidden:
                pass
        member_role = guild.get_role(MEMBER_ROLE_ID)
        if member_role:
            try:
                await member.add_roles(member_role)
            except discord.Forbidden:
                await log_action(
                    guild,
                    "⚠️ فشل التفعيل (صلاحية)",
                    f"**المستخدم:** {member.mention} ({member.name})\n"
                    f"**السبب:** role ديال البوت ماعندوش صلاحية يعطي role ديال Member.\n"
                    f"**الحل:** استعمل `/checkroles` باش تشوف المشكل بالضبط.",
                    discord.Color.orange()
                )
                return
        await log_action(
            guild,
            "✅ تفعيل",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**الحالة:** مفعل\n"
            f"**الطريقة:** Reaction ✅",
            discord.Color.green()
        )
        try:
            gender_embed = discord.Embed(
                title="🚻 واش نتا/نتي ولد ولا بنت؟",
                description="ضغط/ي على الزر المناسب باش نعطيوك الرول الصحيح.",
                color=discord.Color.blurple()
            )
            await member.send(
                f"✅ تم تفعيلك فـ **{SERVER_NAME}**! مرحبا بيك! 🎉",
                embed=gender_embed,
                view=GenderSelectView(target_user_id=member.id, guild_id=guild.id)
            )
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot:
            return
        await log_action(
            message.guild,
            "🗑️ رسالة محذوفة",
            f"**المستخدم:** {message.author.mention}\n"
            f"**القناة:** {message.channel.mention}\n"
            f"**المحتوى:** {message.content[:1000]}",
            discord.Color.red()
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.content == after.content:
            return
        await log_action(
            before.guild,
            "✏️ رسالة معدّلة",
            f"**المستخدم:** {before.author.mention}\n"
            f"**القناة:** {before.channel.mention}\n"
            f"**قبل:** {before.content[:500]}\n"
            f"**بعد:** {after.content[:500]}",
            discord.Color.yellow()
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == bot.user:
            return
        if message.author.bot:
            return
        # Temp Voice Chat Mute: حتى Administrator إلا كتب كيتمسح المساج فوراً؛ Server Owner محمي.
        if await enforce_temp_voice_chat_mute_message(message):
            return
        # ═══════ Prefix Commands (!) معطلين — كاع الأوامر دابا Slash (/) بوحدها ═══════
        # (bot.process_commands ماعادش كيتصاوب، حيت الأوامر ديال ! معطلة نهائياً)
        await process_message_xp(message)
        msg_lower = message.content.lower()

        if not is_exempt(message.author):
            for word in get_active_banned_words() + BANNED_ACTIONS:
                if word.lower() in msg_lower:
                    try:
                        await message.delete()
                        await message.channel.send(
                            f"🚫 {message.author.mention} ممنوع السبام والروابط!",
                            delete_after=5
                        )
                        count = await add_warn(message.author, f"رسالة محذوفة (Auto-Mod): {word}")
                        await log_action(
                            message.guild,
                            "🚨 Auto-Mod | رسالة محذوفة",
                            f"**المستخدم:** {message.author.mention}\n"
                            f"**القناة:** {message.channel.mention}\n"
                            f"**الكلمة الممنوعة:** `{word}`\n"
                            f"**المحتوى:** {message.content[:500]}\n"
                            f"**التحذيرات:** {count} (كتم عند {bot_settings['mute_after_warns']}, طرد عند {bot_settings['kick_after_warns']}, حظر عند {bot_settings['ban_after_warns']})",
                            discord.Color.red()
                        )
                        await apply_warn_escalation(
                            message.author, message.guild, count,
                            f"Auto-Mod: {word}", channel=message.channel
                        )
                        return
                    except discord.Forbidden:
                        pass
            user_id = str(message.author.id)
            now = datetime.now()
            if user_id not in spam_tracker:
                spam_tracker[user_id] = []
            spam_tracker[user_id].append(now)
            spam_tracker[user_id] = [
                t for t in spam_tracker[user_id]
                if now - t < timedelta(seconds=SPAM_INTERVAL)
            ]
            if len(spam_tracker[user_id]) >= SPAM_THRESHOLD:
                try:
                    await message.channel.send(
                        f"🛑 {message.author.mention} توقف عن السبام!",
                        delete_after=5
                    )
                    muted_role = message.guild.get_role(MUTED_ROLE_ID)
                    if muted_role:
                        await message.author.add_roles(muted_role)
                        if user_id in mute_tasks and not mute_tasks[user_id].done():
                            mute_tasks[user_id].cancel()
                        task = asyncio.create_task(auto_unmute(message.author, 5, message.guild))
                        mute_tasks[user_id] = task
                        await log_action(
                            message.guild,
                            "🛑 Auto-Mod | سبام مكتشف",
                            f"**المستخدم:** {message.author.mention}\n"
                            f"**الإجراء:** Mute 5 دقائق (تلقائي)\n"
                            f"**الرسائل:** {len(spam_tracker[user_id])} فـ {SPAM_INTERVAL} ثواني",
                            discord.Color.orange()
                        )
                        spam_tracker[user_id] = []
                except discord.Forbidden:
                    pass

        await maybe_auto_react_translate(message)

        # الردود الحوارية ديال البوت ممنوعة حرفياً خارج روم الـAI المحددة.
        if message.channel.id != TARGET_CHANNEL_ID:
            return
        clean_content = (message.content or "").strip()
        if not clean_content:
            return

        user_id = str(message.author.id)
        now_mono = asyncio.get_running_loop().time()
        if user_id in self.ai_chat_inflight:
            return
        last_request = float(self.ai_chat_last_request.get(user_id, 0.0) or 0.0)
        if now_mono - last_request < AI_USER_COOLDOWN_SECONDS:
            return

        self.ai_chat_last_request[user_id] = now_mono
        self.ai_chat_inflight.add(user_id)
        try:
            async with message.channel.typing():
                response = await ask_ai(
                    user_id,
                    message.author.name,
                    message.author.display_name,
                    clean_content,
                )
            await message.reply(response[:MAX_REPLY_LENGTH], mention_author=False)
        except discord.HTTPException:
            pass
        finally:
            self.ai_chat_inflight.discard(user_id)

    @commands.command(name="report", hidden=True)
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def report(self, 
        ctx,
        member: Optional[discord.Member] = None,
        *,
        reason: str = "ماكاينش تفاصيل",
    ):
        """Hidden prefix fallback. الواجهة الحقيقية هي #support-center."""
        if not isinstance(ctx.author, discord.Member):
            return

        ok, msg = await send_support_report(
            ctx.guild,
            ctx.author,
            target=member,
            details=reason,
            context_link="",
        )
        try:
            await ctx.author.send(msg)
        except discord.HTTPException:
            pass

        try:
            await ctx.message.delete()
        except Exception:
            pass

    @report.error
    async def report_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            try:
                await ctx.author.send(
                    f"⏳ صبر شوية ({error.retry_after:.0f}ث) قبل بلاغ آخر."
                )
            except discord.HTTPException:
                pass

    @commands.hybrid_command(name="case")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def case_cmd(self, ctx, case_id: int):
        """كيبين التفاصيل الكاملة ديال Case معين برقمو"""
        record = get_case(case_id)
        if not record:
            await ctx.send(f"❌ ماكاينش Case #{case_id}.")
            return

        emoji = record["action"].split(" ")[0] if record["action"] else "📋"
        color = CASE_ACTION_COLORS.get(emoji, discord.Color.blurple())

        embed = discord.Embed(
            title=f"📋 Case #{record['id']} — {record['action']}",
            color=color,
            timestamp=datetime.now()
        )
        target_value = f"<@{record['target_id']}> ({record['target_name']})" if record.get("target_id") else record["target_name"]
        mod_value = f"<@{record['moderator_id']}> ({record['moderator_name']})" if record.get("moderator_id") else record["moderator_name"]
        embed.add_field(name="🎯 العضو", value=target_value, inline=False)
        embed.add_field(name="🛡️ نفذ من طرف", value=mod_value, inline=False)
        embed.add_field(name="📝 السبب", value=record["reason"], inline=False)
        if record.get("extra"):
            embed.add_field(name="ℹ️ تفاصيل إضافية", value=record["extra"], inline=False)
        embed.add_field(name="🕐 التاريخ", value=record["timestamp"], inline=False)
        embed.set_footer(text=f"{SERVER_NAME} | Case #{record['id']}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="history")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def history_cmd(self, ctx, member: Optional[discord.Member] = None):
        """كيبين كاع الـ Cases ديال عضو معين، الأحدث فالأول (آخر 15)"""
        member = member or ctx.author
        user_cases = get_cases_for_user(member.id)

        embed = discord.Embed(
            title=f"📋 سجل {member.display_name}",
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )

        if not user_cases:
            embed.add_field(name="النتيجة", value="ما كاين حتى Case فسجل هاد العضو ✅", inline=False)
        else:
            lines = []
            for c in user_cases[:15]:
                mod_display = f"<@{c['moderator_id']}>" if c.get("moderator_id") else c["moderator_name"]
                lines.append(
                    f"**#{c['id']} — {c['action']}**\n"
                    f"السبب: {c['reason']} | نفذ من طرف: {mod_display} | {c['timestamp']}"
                )
            embed.description = "\n\n".join(lines)
            embed.add_field(name="📊 مجموع الـ Cases", value=str(len(user_cases)), inline=False)
            if len(user_cases) > 15:
                embed.set_footer(text=f"{SERVER_NAME} | كيبان غير آخر 15 Case، استعمل /case <رقم> باش تشوف واحد قديم")
            else:
                embed.set_footer(text=f"{SERVER_NAME} | Moderation History")

        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="addword", description="زيد كلمة للائحة الكلمات الممنوعة")
    @app_commands.default_permissions(administrator=True)
    async def addword_cmd(self, ctx, *, word: str = ""):
        await _delete_trigger_silently(ctx)
        if not is_owner(ctx):
            return
        word = word.strip()
        if not word:
            return
        if word in banned_words_state["removed"]:
            banned_words_state["removed"].remove(word)
        if word not in banned_words_state["extra"] and word not in BANNED_WORDS:
            banned_words_state["extra"].append(word)
        save_banned_lists()
        try:
            await ctx.author.send(f"✅ تزادت الكلمة للائحة الممنوعة. (المجموع الحالي: {len(get_active_banned_words())})")
        except Exception:
            pass

    @commands.hybrid_command(name="removeword", description="حيد كلمة من لائحة الكلمات الممنوعة")
    @app_commands.default_permissions(administrator=True)
    async def removeword_cmd(self, ctx, *, word: str = ""):
        await _delete_trigger_silently(ctx)
        if not is_owner(ctx):
            return
        word = word.strip()
        if not word:
            return
        if word in banned_words_state["extra"]:
            banned_words_state["extra"].remove(word)
        if word in BANNED_WORDS and word not in banned_words_state["removed"]:
            banned_words_state["removed"].append(word)
        save_banned_lists()
        try:
            await ctx.author.send(f"✅ تحيدت الكلمة من اللائحة. (المجموع الحالي: {len(get_active_banned_words())})")
        except Exception:
            pass

    @commands.hybrid_command(name="addaction", description="زيد عبارة/سلوك ممنوع (Owner)")
    @app_commands.default_permissions(administrator=True)
    async def addaction_cmd(self, ctx, *, phrase: str = ""):
        """كتزيد عبارة/سلوك ممنوع (بحال كلمة، غير كتقدر تكون جملة كاملة)،
        وكيتبع نفس آلية الحذف/التحذير ديال BANNED_WORDS."""
        await _delete_trigger_silently(ctx)
        if not is_owner(ctx):
            return
        phrase = phrase.strip()
        if not phrase or phrase in BANNED_ACTIONS:
            return
        BANNED_ACTIONS.append(phrase)
        save_banned_lists()
        try:
            await ctx.author.send(f"✅ تزادت العبارة/الفعل الممنوع. (المجموع الحالي: {len(BANNED_ACTIONS)})")
        except Exception:
            pass

    @commands.hybrid_command(name="removeaction", description="حيد جملة من لائحة الجمل الممنوعة")
    @app_commands.default_permissions(administrator=True)
    async def removeaction_cmd(self, ctx, *, phrase: str = ""):
        await _delete_trigger_silently(ctx)
        if not is_owner(ctx):
            return
        phrase = phrase.strip()
        if phrase in BANNED_ACTIONS:
            BANNED_ACTIONS.remove(phrase)
            save_banned_lists()
            try:
                await ctx.author.send(f"✅ تحيدت العبارة. (المجموع الحالي: {len(BANNED_ACTIONS)})")
            except Exception:
                pass

    @commands.hybrid_command(name="listbanned")
    @app_commands.default_permissions(administrator=True)
    async def listbanned_cmd(self, ctx):
        """كيبعث اللائحة الكاملة بـ DM للـ Owner فقط (حتى الأدمن ما شايفينهاش)"""
        await _delete_trigger_silently(ctx)
        if not is_owner(ctx):
            return
        words = get_active_banned_words()
        actions = BANNED_ACTIONS
        text_words = "\n".join(f"- {w}" for w in words) or "ماكاين والو"
        text_actions = "\n".join(f"- {a}" for a in actions) or "ماكاين والو"
        try:
            await ctx.author.send(
                f"🚫 **الكلمات الممنوعة ({len(words)}):**\n{text_words}\n\n"
                f"🚫 **الأفعال/العبارات الممنوعة ({len(actions)}):**\n{text_actions}"
            )
        except Exception:
            pass

    @commands.hybrid_command(name="ownerkick", description="اطرد عضو (Owner بوحدو)")
    @app_commands.default_permissions(administrator=True)
    async def ownerkick_cmd(self, ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
        if not is_owner(ctx):
            return
        if member.id == OWNER_ID:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
            return
        try:
            await member.kick(reason=reason)
            case_id = await log_case(
                ctx.guild, "👢 طرد (Owner)", "👢", discord.Color.orange(),
                target=member, moderator=ctx.author, reason=reason
            )
            await ctx.send(f"👢 {member.mention} تم طرده من طرف Owner. Case #{case_id}", delete_after=6)
        except discord.Forbidden:
            await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ خطأ: {str(e)}", delete_after=5)

    @commands.hybrid_command(name="ownerban", description="احظر عضو (Owner بوحدو)")
    @app_commands.default_permissions(administrator=True)
    async def ownerban_cmd(self, ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
        if not is_owner(ctx):
            return
        if member.id == OWNER_ID:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
            return
        try:
            await member.ban(reason=reason)
            case_id = await log_case(
                ctx.guild, "🚫 حظر (Owner)", "🚫", discord.Color.red(),
                target=member, moderator=ctx.author, reason=reason
            )
            await ctx.send(f"🚫 {member.mention} تم حظره من طرف Owner. Case #{case_id}", delete_after=6)
        except discord.Forbidden:
            await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ خطأ: {str(e)}", delete_after=5)

    @commands.hybrid_command(name="ownermute", description="كتم عضو (Owner بوحدو)")
    @app_commands.default_permissions(administrator=True)
    async def ownermute_cmd(self, ctx, member: discord.Member, duration: int = 5, *, reason="ما ذكرش سبب"):
        if not is_owner(ctx):
            return
        if member.id == OWNER_ID:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
            return
        muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
        if not muted_role:
            await ctx.send("❌ ما لقيتش دور Mute! حط ID صحيح فـ MUTED_ROLE_ID.", delete_after=5)
            return
        try:
            await member.add_roles(muted_role)
            user_id = str(member.id)
            if user_id in mute_tasks and not mute_tasks[user_id].done():
                mute_tasks[user_id].cancel()
            task = asyncio.create_task(auto_unmute(member, duration, ctx.guild))
            mute_tasks[user_id] = task
            case_id = await log_case(
                ctx.guild, "🔇 كتم (Owner)", "🔇", discord.Color.yellow(),
                target=member, moderator=ctx.author, reason=reason,
                extra=f"المدة: {duration} دقيقة"
            )
            await ctx.send(f"🔇 {member.mention} تكتم من طرف Owner ({duration} دقيقة). Case #{case_id}", delete_after=6)
        except discord.Forbidden:
            await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)

    @commands.hybrid_command(name="muteall")
    @app_commands.default_permissions(administrator=True)
    async def muteall_cmd(self, ctx, *, reason="Server Lockdown (Owner)"):
        """كتكتم كاع الأعضاء فالسيرفر (ما عدا Owner والأدوار المعفية) — Owner فقط"""
        if not is_owner(ctx):
            return
        muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
        if not muted_role:
            await ctx.send("❌ ما لقيتش دور Mute! حط ID صحيح فـ MUTED_ROLE_ID.", delete_after=5)
            return
        status_msg = await ctx.send("⏳ كنكتم كاع الأعضاء، صبر شوية...")
        muted_count = 0
        for member in ctx.guild.members:
            if member.bot or member.id == OWNER_ID or is_exempt(member):
                continue
            if muted_role in member.roles:
                continue
            try:
                await member.add_roles(muted_role, reason=reason)
                muted_count += 1
                await asyncio.sleep(0.4)
            except (discord.Forbidden, discord.HTTPException):
                continue
        await status_msg.edit(content=f"🔇 تكتمو {muted_count} عضو من طرف Owner.")
        await log_action(
            ctx.guild, "🔇 Mute All (Owner)",
            f"**العدد:** {muted_count}\n**السبب:** {reason}\n**المنفذ:** {ctx.author.mention}",
            discord.Color.yellow()
        )

    @commands.hybrid_command(name="unmuteall")
    @app_commands.default_permissions(administrator=True)
    async def unmuteall_cmd(self, ctx):
        """كتفك الكتم على كاع الأعضاء المكتومين — Owner فقط"""
        if not is_owner(ctx):
            return
        muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
        if not muted_role:
            await ctx.send("❌ ما لقيتش دور Mute!", delete_after=5)
            return
        status_msg = await ctx.send("⏳ كنفك الكتم على الجميع، صبر شوية...")
        unmuted_count = 0
        for member in list(muted_role.members):
            try:
                await member.remove_roles(muted_role)
                unmuted_count += 1
                user_id = str(member.id)
                if user_id in mute_tasks and not mute_tasks[user_id].done():
                    mute_tasks[user_id].cancel()
                await asyncio.sleep(0.4)
            except (discord.Forbidden, discord.HTTPException):
                continue
        await status_msg.edit(content=f"🔊 تفك الكتم على {unmuted_count} عضو.")
        await log_action(
            ctx.guild, "🔊 Unmute All (Owner)",
            f"**العدد:** {unmuted_count}\n**المنفذ:** {ctx.author.mention}",
            discord.Color.green()
        )

    @commands.hybrid_command(name="lockdown")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def lockdown_cmd(self, ctx, duration_minutes: int = None):
        """كيفعّل Anti-Raid Lockdown يدوياً (بلا ماتوصل عتبة الانضمامات) — Admin/Owner"""
        started = await trigger_raid_lockdown(
            ctx.guild,
            reason=f"🔒 Lockdown يدوي من طرف {ctx.author.mention}.",
            duration_minutes=duration_minutes
        )
        if started:
            dur_txt = f"{duration_minutes} دقيقة" if duration_minutes else (
                f"{bot_settings['raid_lockdown_duration_minutes']} دقيقة" if bot_settings['raid_lockdown_duration_minutes'] else "حتى `/unlockdown` يدوي"
            )
            await ctx.send(f"🔒 Lockdown تفعل. غادي يدوم: {dur_txt}.")
        else:
            await ctx.send("⚠️ Lockdown مفعل ديجا.", delete_after=6)

    @commands.hybrid_command(name="unlockdown")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def unlockdown_cmd(self, ctx):
        """كيسد Anti-Raid Lockdown يدوياً ويرجع verification level للحالة العادية — Admin/Owner"""
        ended = await end_raid_lockdown(ctx.guild, reason=f"يدوي من طرف {ctx.author.mention}")
        if ended:
            await ctx.send("✅ Lockdown تسد، الوضعية رجعت عادية.")
        else:
            await ctx.send("ℹ️ ماكاين حتى Lockdown مفعل دابا.", delete_after=6)

    @commands.hybrid_command(name="raidstatus")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def raidstatus_cmd(self, ctx):
        """كيبين الحالة ديال Anti-Raid دابا (مفعل ولا لا، عدد الانضمامات الأخيرة)"""
        state = raid_state.get(ctx.guild.id, {})
        now = datetime.now()
        cutoff = now - timedelta(seconds=bot_settings['raid_join_interval_seconds'])
        recent = [t for t in recent_joins.get(ctx.guild.id, []) if t > cutoff]

        embed = discord.Embed(
            title="🚨 Anti-Raid Status",
            color=discord.Color.red() if state.get("active") else discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="الحالة", value="🔒 Lockdown مفعل" if state.get("active") else "✅ عادي", inline=False)
        embed.add_field(
            name="الانضمامات الأخيرة",
            value=f"{len(recent)} / {bot_settings['raid_join_threshold']} (فـ آخر {bot_settings['raid_join_interval_seconds']}ث)",
            inline=False
        )
        embed.add_field(name="العمل ملي يتفعل Lockdown", value="🚫 حظر" if bot_settings['raid_action'] == "ban" else "👢 طرد", inline=False)
        embed.set_footer(text=f"{SERVER_NAME} | Anti-Raid Protection")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="testwelcome", description="بعث Welcome Card تجريبية هنا فالشات (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def testwelcome_cmd(self, ctx, member: Optional[discord.Member] = None, returning: bool = False):
        """كيبعث Welcome Card تجريبية هنا فالشات بلا ما تحتاج عضو يدخل بصح للسيرفر (Admin).
        استعمال: /testwelcome [@عضو] [true/false للـ returning]"""
        member = member or ctx.author
        if not PIL_AVAILABLE:
            await ctx.send("❌ Pillow ماشي مثبتة، الصورة ماغاديش تتصاوب. دير `pip install Pillow`.")
            return
        if not bot_settings['welcome_card_enabled']:
            await ctx.send("⚠️ Welcome Cards معطلة دابا، شعلها من `/botpanel` (زر 🖼️ الترحيب) ولا Admin.")
            return

        card_buffer = await generate_welcome_card(member, ctx.guild.member_count, returning=returning)
        if not card_buffer:
            await ctx.send("❌ وقع خطأ فـ صنع الصورة، شوف الـ logs ديال البوت (`[WELCOME_CARD]`).")
            return

        file = discord.File(card_buffer, filename="welcome.png")
        await ctx.send(content=f"🖼️ هاكذا غادي تبان الكارطة (تجريبي، ماشي رسالة حقيقية):", file=file)


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(CoreModerationCog(bot_instance))
