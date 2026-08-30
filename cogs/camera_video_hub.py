# -*- coding: utf-8 -*-
"""نظام: Camera Hub — كاتيگوري "video calls" + روم دخول (Gateway) + روم Temp ديال الكاميرا.

الفكرة الكاملة (كيفما تصاوبت من جديد):
1) البوت كيتأكد أن كاينة كاتيگوري سميتها "video calls" (كيخلقها إلا ماكانتش).
2) داخل هاد الكاتيگوري، كاينة روم ثابتة "دخول" (Gateway) — سميتها
   VIDEO_GATEWAY_CHANNEL_NAME — فيها غير رسالة واحدة (بالدارجة + قائمة
   🌐 اللغة تحتها) كتشرح بحال-اش تحل الكاميرا. ديسكورد كيطلب صلاحية
   Send Messages باش تخدم القوائم/الأزرار (components) — فالحقيقة
   الروم مسموح فيها الكتابة تقنياً، ولكن أي رسالة كتبها شي حد (ماشي
   البوت) كتتمسح مباشرة (on_message listener) — فالنتيجة كتبقى الروم
   نظيفة غير فيها رسالة الشرح، وفنفس الوقت قائمة 🌐 اللغة خدامة.
3) ماشي لي حل الكاميرا فأي روم كيفما كانت كيتهز — غير لي حلها **وهو
   داخل روم الدخول (Gateway)** هو اللي كيتهز أوتوماتيك لروم Temp ديال
   الكاميرا (تتخلق أول مرة تلقاها وسط نفس الكاتيگوري، وكتتمسح ملي تبقى
   فارغة) — باش يلقى روحو مع باقي الناس اللي حاليين الكاميرا قبلو.
4) هاد الروم ديال الكاميرا (الهوب) مخصصة غير للي حاليين الكاميرا: لي
   دخلها (بيدو، ولا تطردت منو الكاميرا) وهو ماحاليش الكاميرا، البوت
   كيرجعو تلقائيا للروم اللي كان فيها قبل ما يدخل (غالبا روم الدخول).
   ملي يحل الكاميرا (وياكد منها البوت فالـscan اللي كيجي)، عاد كيرجع
   يتهز لروم الكاميرا.
5) إشعار النقل (بحال-اش تحل الكاميرا ديسكورد سداها أوتوماتيك، وعندك
   مدة سماح باش تعاود تحلها) كيتصيفط فـ **DM خاص بالعضو** — ماشي فروم
   الكاميرا — باش ما يبقاش الروم كيتعمر برسائل بحال كل عضو حل الكاميرا
   قبلو. فالـDM كاين زر "تجاهل ❌" باش يمسح الرسالة، وقائمة 🌐 اللغة.
   إلا كانت الـDM مسدودة عند العضو، الإشعار غير كيتقرا (ماكيتصيفطش،
   بلا ما يوقف والو من العملية).

كلشي كيتشيك كل 5 ثواني بنفس اللوب — بسيط ومركزي.

⚠️ ملاحظة مهمة (سبب باگ "كيخرجني وتسد الكاميرا بوحدها"):
ديسكورد كيسد الكاميرا (self_video) أوتوماتيكياً عند العضو ملي البوت
كينقلو بالقوة (move_to) من روم لروم — هادشي راجع للـ Discord نفسو، ماشي
بگ فالبوت. بلا معالجة، السكان اللي جاي (بعد 5 ثواني) كان كيلقى الكاميرا
مسدودة على طول من بعد النقل وكيرجع العضو تلقائيا (return_from_hub)،
فكيبان للعضو "دخلت الهوب وطاح مني نيت". الحل: مدة سماح (grace period)
بعد كل نقل للهوب، ما كنشيكيوش على self_video ديال العضو حتى تعدي، باش
يقدر يعاود يحل الكاميرا يدويا من بعد النقل بلا ما يتطرد فالسكان الجاي.
"""

import time

import bot_core as core

core.attach_namespace(globals())

# نستعملو الدوال ديال panel_i18n مباشرة (بحال باقي البانلات فالبوت، شوف
# cogs/prison.py) عوض ما نعتمدو غير على الـ "auto-attach" العام — هادشي
# أضمن وخاصة فروم صوتية فيها صلاحيات خاصة.
from cogs.panel_i18n import attach_panel_language, panel_language_view

CAMERA_HUB_FILE = os.path.join(DATA_DIR, "camera_hub.json")
VIDEO_CALLS_CATEGORY_NAME = "Video call's 📹"
VIDEO_HUB_CHANNEL_NAME = "Camera Room 🎥"
# روم الدخول: هي الوحيدة اللي كيتشيك فيها البوت شكون حل الكاميرا. حل الكاميرا
# فأي روم أخرى ماكيديرش والو — خاصو يدخل من هنا أولا.
VIDEO_GATEWAY_CHANNEL_NAME = "🎥 join for active camera"
SCAN_INTERVAL_SECONDS = 5

# مدة سماح بعد كل نقل للهوب (بالثواني) — كتعطي الوقت للعضو يعاود يحل
# الكاميرا يدويا (ديسكورد كيسدها أوتوماتيك عند move_to)، قبل ما نبداو
# نشيكيو عليه ونرجعوه. راها بزيادة على الـ SCAN_INTERVAL_SECONDS، ماشي بدالها.
MOVE_IN_GRACE_SECONDS = 10

# {"enabled": bool, "guilds": {"<guild_id>": {"category_id": int|None, "hub_channel_id": int|None}}}
camera_hub_config = {"enabled": True, "guilds": {}}

# آخر روم "عادية" (ماشي هوب) شافو فيها كل عضو — باش نقدرو نرجعوه ليها إلا طرد من الهوب
_last_non_hub_channel = {}  # {member_id: channel_id}

# آخر وقت (monotonic) تهز فيه كل عضو للهوب — باش نطبقو مدة السماح قبل نرجعوه
_moved_into_hub_at = {}  # {member_id: float}

# روم الدخول اللي تأكدنا منها هاد الجلسة (channel_id) — باش ماندوزوش نشيكيو
# على الرسالة/الصلاحيات ديالها فكل scan (كل 5 ثواني)، غير مرة وحدة بالكافي.
_gateway_verified = set()


def load_camera_hub_config():
    global camera_hub_config
    try:
        with open(CAMERA_HUB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            camera_hub_config.update(data)
            camera_hub_config.setdefault("guilds", {})
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"[CAMERA-HUB] خطأ فـ تحميل camera_hub.json: {e}")


def save_camera_hub_config():
    try:
        with open(CAMERA_HUB_FILE, "w", encoding="utf-8") as f:
            json.dump(camera_hub_config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[CAMERA-HUB] خطأ فـ حفظ camera_hub.json: {e}")


load_camera_hub_config()


def _guild_state(guild_id: int) -> dict:
    guilds = camera_hub_config.setdefault("guilds", {})
    gstate = guilds.setdefault(
        str(guild_id),
        {
            "category_id": None,
            "hub_channel_id": None,
            "gateway_channel_id": None,
            "gateway_message_id": None,
        },
    )
    gstate.setdefault("gateway_channel_id", None)
    gstate.setdefault("gateway_message_id", None)
    return gstate


def _is_private_temp_room(channel) -> bool:
    """True غير إلا كانت روم Temp مدارة Private من طرف مولاها — البوت ما يمسهاش."""
    try:
        if not is_temp_voice_channel(channel):
            return False
        rec = get_temp_voice_acl(channel, create=False)
        return bool(rec and rec.get("private"))
    except NameError:
        return False


async def _ensure_category(guild: "discord.Guild"):
    for cat in guild.categories:
        if cat.name.strip().lower() == VIDEO_CALLS_CATEGORY_NAME.lower():
            return cat
    try:
        return await guild.create_category(VIDEO_CALLS_CATEGORY_NAME, reason="Camera Hub: إنشاء كاتيگوري video calls")
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[CAMERA-HUB] ما قدرتش نخلق الكاتيگوري فـ {guild}: {e}")
        return None


async def _ensure_hub_channel(guild: "discord.Guild"):
    """كيرجع الروم ديال الفيديو الحالية، ولا كيخلق وحدة جديدة وسط كاتيگوري video calls."""
    gstate = _guild_state(guild.id)

    hub_id = gstate.get("hub_channel_id")
    if hub_id:
        existing = guild.get_channel(hub_id)
        if isinstance(existing, discord.VoiceChannel):
            return existing
        gstate["hub_channel_id"] = None

    category = await _ensure_category(guild)
    if category is None:
        return None
    gstate["category_id"] = category.id

    try:
        new_channel = await guild.create_voice_channel(
            VIDEO_HUB_CHANNEL_NAME, category=category, reason="Camera Hub: تلقائي — عضو حالي الكاميرا"
        )
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[CAMERA-HUB] ما قدرتش نخلق روم الفيديو فـ {guild}: {e}")
        return None

    gstate["hub_channel_id"] = new_channel.id
    save_camera_hub_config()
    return new_channel


def _gateway_overwrites(guild: "discord.Guild") -> dict:
    """@everyone خاصو يقدر يستعمل القائمة ديال 🌐 اللغة تحت رسالة الشرح —
    وديسكورد كيطلب صلاحية Send Messages باش تخدم الـ components (قوائم/
    أزرار)، حتى ملي الرسالة ماشي ديالو. فهاد الحالة سيبنا send_messages=True،
    وعوضها كنمسحو أوتوماتيك أي رسالة كتبها شي حد (شوف on_message listener
    فـ CameraHubCog) — كتبقى الروم نظيفة غير فيها رسالة البوت."""
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(
            view_channel=True, connect=True, speak=True,
            send_messages=True, add_reactions=False, create_public_threads=False,
        ),
    }
    if guild.me:
        overwrites[guild.me] = discord.PermissionOverwrite(
            view_channel=True, connect=True, send_messages=True,
            embed_links=True, read_message_history=True, manage_messages=True,
        )
    return overwrites


async def _ensure_gateway_channel(guild: "discord.Guild", category=None):
    """كيرجع روم الدخول (Gateway) الحالية، ولا كيخلق وحدة جديدة وسط كاتيگوري video calls."""
    gstate = _guild_state(guild.id)

    gateway_id = gstate.get("gateway_channel_id")
    if gateway_id:
        existing = guild.get_channel(gateway_id)
        if isinstance(existing, discord.VoiceChannel):
            return existing
        gstate["gateway_channel_id"] = None
        gstate["gateway_message_id"] = None

    if category is None:
        category = await _ensure_category(guild)
        if category is None:
            return None
    gstate["category_id"] = category.id

    try:
        new_channel = await guild.create_voice_channel(
            VIDEO_GATEWAY_CHANNEL_NAME,
            category=category,
            position=0,
            overwrites=_gateway_overwrites(guild),
            reason="Camera Hub: إنشاء روم الدخول (Gateway)",
        )
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[CAMERA-HUB] ما قدرتش نخلق روم الدخول فـ {guild}: {e}")
        return None

    gstate["gateway_channel_id"] = new_channel.id
    gstate["gateway_message_id"] = None
    save_camera_hub_config()
    return new_channel


def _gateway_instructions_embed() -> "discord.Embed":
    """رسالة ثابتة بالدارجة كتشرح بحال-اش تحل الكاميرا. من بغا لغة أخرى
    كيختارها بروحه من قائمة 🌐 اللغة اللي كتزادها panel_i18n تحت هاد الرسالة."""
    embed = discord.Embed(
        title="🎥 دخل هنا باش تفعل الكاميرا",
        description=(
            "مرحبا بيك 👋 هاد الروم كتخدم غير باش تنضم للناس اللي حاليين "
            "الكاميرا ديالهم فـ **Video Calls**.\n\n"
            "**كيفاش تخدم:**\n"
            "1️⃣ راك دايرها من دابا.\n"
            "2️⃣ حل الكاميرا ديالك من ديسكورد (🎥 فتحت، ولا من الإعدادات).\n"
            "3️⃣ من بعد شي ثواني قليلة البوت غايهزك أوتوماتيك لروم الكاميرا، "
            "فين كاينين اللي حاليين كاميراتهم قبلك.\n\n"
            "⚠️ ماشي مسموح تكتب هنا — هاد الروم بقات غير للتوضيح والدخول.\n"
            "إلا سديتي الكاميرا من بعد، البوت غايرجعك للروم لي كنتي فيها."
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="Camera Hub • اختار لغتك 🌐 من تحت")
    return embed


async def _ensure_gateway_message(channel: "discord.VoiceChannel", gstate: dict):
    """كيتأكد أن رسالة الشرح كاينة فروم الدخول — كيصاوبها إلا ماكانتش
    (أول مرة، ولا إلا تحيدات بالغلط). ماكيديرش هاد التأكد كل 5 ثواني، غير
    مرة وحدة فهاد الجلسة (شوف _gateway_verified)."""
    if channel.id in _gateway_verified:
        return

    message_id = gstate.get("gateway_message_id")
    if message_id:
        try:
            await channel.fetch_message(message_id)
            _gateway_verified.add(channel.id)
            return
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    try:
        # كنستعملو panel_language_view بحال باقي البانلات (شوف الاستيراد
        # فراس الملف) — كتصاوب View فيها قائمة 🌐 اللغة بشكل مضمون.
        msg = await channel.send(
            embed=_gateway_instructions_embed(),
            view=panel_language_view("camera_gateway_instructions"),
        )
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[CAMERA-HUB] ما قدرتش نصيفط رسالة روم الدخول: {e}")
        return

    gstate["gateway_message_id"] = msg.id
    save_camera_hub_config()
    _gateway_verified.add(channel.id)


async def resend_gateway_message(guild: "discord.Guild"):
    """كيعاود يصيفط رسالة الشرح فروم الدخول من الصفر — كتستعملها لوحة
    تحكم الـ Owner Panel (زر Camera Hub)."""
    gstate = _guild_state(guild.id)
    gateway_channel = await _ensure_gateway_channel(guild)
    if gateway_channel is None:
        return None
    gstate["gateway_message_id"] = None
    _gateway_verified.discard(gateway_channel.id)
    await _ensure_gateway_message(gateway_channel, gstate)
    return gateway_channel


def _move_notice_embed(member: "discord.Member", guild: "discord.Guild") -> "discord.Embed":
    """إشعار بالدارجة فقط — من بغا لغة أخرى كيختارها بروحه من القائمة 🌐 تحت.
    كيتصيفط فـ DM خاص بالعضو (ماشي فروم الكاميرا) باش يبقى خاص بيه وماشي
    ظاهر لكلشي."""
    embed = discord.Embed(
        title="🎥 Video Calls — Camera Room",
        description=(
            f"تهزيتي أوتوماتيك لروم الكاميرا فـ **{guild.name}** حيت كنتي "
            f"حالي الكاميرا وأنت داخل روم الدخول.\n\n"
            f"⚠️ ديسكورد كيسد الكاميرا أوتوماتيك ملي بوت كينقلك — عندك "
            f"**{MOVE_IN_GRACE_SECONDS} ثانية** باش تعاود تحلها يدويا، وإلا "
            f"البوت غايرجعك للروم لي كنتي فيها."
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"{member.display_name} • Camera Hub")
    return embed


class DismissNoticeView(discord.ui.View):
    """زر تجاهل ❌ تحت إشعار النقل ديال الـ DM — كيمسح الرسالة."""

    def __init__(self, member_id: int):
        super().__init__(timeout=None)
        self.member_id = member_id

    @discord.ui.button(label="تجاهل", emoji="❌", style=discord.ButtonStyle.secondary)
    async def dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer()
        except (discord.NotFound, discord.HTTPException):
            pass
        try:
            await interaction.message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass


class CameraHubCog(commands.Cog):
    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance
        self.camera_scan_loop.start()

    def cog_unload(self):
        self.camera_scan_loop.cancel()

    # روم الدخول (Gateway) مسموح فيها الكتابة تقنياً (خاصها Send Messages
    # باش تخدم قائمة 🌐 اللغة)، فكنمسحو مباشرة أي رسالة كتبها شي حد ماشي
    # البوت — كتبقى الروم نظيفة غير فيها رسالة الشرح.
    @commands.Cog.listener("on_message")
    async def _guard_gateway_channel(self, message: "discord.Message"):
        if message.author.bot or message.guild is None:
            return
        gstate = _guild_state(message.guild.id)
        if message.channel.id != gstate.get("gateway_channel_id"):
            return
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    # ═══════════════════ اللوب الرئيسي: كل 5 ثواني ═══════════════════
    @tasks.loop(seconds=SCAN_INTERVAL_SECONDS)
    async def camera_scan_loop(self):
        if not camera_hub_config.get("enabled", True):
            return
        for guild in list(self.bot.guilds):
            try:
                await self._scan_guild(guild)
            except Exception as e:
                print(f"[CAMERA-HUB] خطأ فـ scan ديال {guild}: {e}")

    @camera_scan_loop.before_loop
    async def _before_scan(self):
        await self.bot.wait_until_ready()

    async def _scan_guild(self, guild: "discord.Guild"):
        gstate = _guild_state(guild.id)

        # روم الدخول (Gateway) — ثابتة، ماكتمسحش، وفيها رسالة الشرح بلا كتابة.
        gateway_channel = await _ensure_gateway_channel(guild)
        if gateway_channel is not None:
            await _ensure_gateway_message(gateway_channel, gstate)

        hub_channel = None
        hub_id = gstate.get("hub_channel_id")
        if hub_id:
            candidate = guild.get_channel(hub_id)
            if isinstance(candidate, discord.VoiceChannel):
                hub_channel = candidate

        # روم الفيديو بقات فارغة -> نمسحوها (Temp حقيقية)
        if hub_channel is not None and len(hub_channel.members) == 0:
            try:
                await hub_channel.delete(reason="Camera Hub: بقات فارغة")
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass
            gstate["hub_channel_id"] = None
            save_camera_hub_config()
            hub_channel = None

        hub_id = hub_channel.id if hub_channel else None

        # 1) نسجلو آخر روم "عادية" (ماشي هوب) كان فيها كل عضو دابا
        for vc in guild.voice_channels:
            if hub_id and vc.id == hub_id:
                continue
            for m in vc.members:
                if not m.bot:
                    _last_non_hub_channel[m.id] = vc.id

        # 2) لي كاين فروم الفيديو وماحاليش الكاميرا -> يرجع لفين كان
        #    (إلا ماعداتش عليه مدة السماح ديال بعد النقل — شوف MOVE_IN_GRACE_SECONDS)
        if hub_channel is not None:
            now = time.monotonic()
            hub_member_ids = {m.id for m in hub_channel.members if not m.bot}
            # تنظيف: نحيدو التوقيتات ديال أي عضو خرج من الهوب (بيدو ولا تطرد)
            for stale_id in list(_moved_into_hub_at.keys()):
                if stale_id not in hub_member_ids:
                    _moved_into_hub_at.pop(stale_id, None)

            for m in list(hub_channel.members):
                if m.bot:
                    continue
                if m.voice and m.voice.self_video:
                    continue
                moved_at = _moved_into_hub_at.get(m.id)
                if moved_at is not None and (now - moved_at) < MOVE_IN_GRACE_SECONDS:
                    # مازال فمدة السماح — عطيه الوقت يعاود يحل الكاميرا يدويا
                    continue
                await self._return_from_hub(m, guild)

        # 3) لي حالي الكاميرا وهو داخل روم الدخول (Gateway) بالذات -> يتهز
        #    لروم الكاميرا. حل الكاميرا فأي روم أخرى ماكيديرش والو — خاصو
        #    يدخل لروم الدخول أولا باش يتشيكيا عليه.
        if gateway_channel is not None:
            for m in list(gateway_channel.members):
                if m.bot:
                    continue
                if m.voice and m.voice.self_video:
                    if hub_channel is None:
                        hub_channel = await _ensure_hub_channel(guild)
                        if hub_channel is None:
                            return
                        hub_id = hub_channel.id
                    try:
                        await m.move_to(hub_channel, reason="Camera Hub: حالي الكاميرا فروم الدخول")
                        _moved_into_hub_at[m.id] = time.monotonic()
                        await log_action(
                            guild,
                            "🎥 Camera Hub — نقل تلقائي",
                            f"**العضو:** {m.mention}\n**من:** {gateway_channel.mention}\n**لـ:** {hub_channel.mention}",
                            discord.Color.blurple(),
                        )
                        try:
                            # كنصيفطو الإشعار فـ DM خاص بالعضو (ماشي فروم
                            # الكاميرا) باش يبقى خاص بيه وماشي ظاهر لكلشي.
                            # attach_panel_language: قائمة 🌐 اللغة مضمونة،
                            # وزر "تجاهل ❌" باش يمسح الرسالة من عندو.
                            await m.send(
                                embed=_move_notice_embed(m, guild),
                                view=attach_panel_language(
                                    DismissNoticeView(m.id), "camera_hub_move_notice"
                                ),
                            )
                        except (discord.Forbidden, discord.HTTPException):
                            # الـDM مسدودة عند العضو — ماكاين حل، غير نكملو
                            # بلا إشعار (النقل ديال الكاميرا نفسو ماشي متأثر).
                            pass
                    except (discord.Forbidden, discord.HTTPException):
                        pass

    async def _return_from_hub(self, member: "discord.Member", guild: "discord.Guild"):
        _moved_into_hub_at.pop(member.id, None)
        return_channel_id = _last_non_hub_channel.get(member.id)
        return_channel = guild.get_channel(return_channel_id) if return_channel_id else None
        try:
            if isinstance(return_channel, discord.VoiceChannel):
                await member.move_to(return_channel, reason="Camera Hub: بلا كاميرا — رجوع للروم الأصلية")
            else:
                await member.move_to(None, reason="Camera Hub: بلا كاميرا وماكاين فين يرجع")
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ═══════════════════ أوامر تحكم بسيطة ═══════════════════
    # ملاحظة: التفاصيل الكاملة (الحالة، روم الدخول، إعادة صيفط الرسالة...)
    # كاينة فـ لوحة تحكم الـ Owner (bot_admin_panel.py -> زر "Camera Hub").
    # هنا خلينا غير أمر سريع للتفعيل/التوقيف.
    @commands.hybrid_group(name="camerahub", description="إعدادات Camera Hub")
    @commands.has_permissions(manage_channels=True)
    async def camerahub_group(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send(
                "ℹ️ استعمل `/camerahub toggle` باش تفعّل/توقّف النظام. "
                "التفاصيل الكاملة (الحالة، روم الدخول، إعادة صيفط الرسالة...) "
                "كاينة فـ لوحة تحكم الـ Owner Panel."
            )

    @camerahub_group.command(name="toggle", description="فعّل/وقّف نظام Camera Hub")
    async def camerahub_toggle(self, ctx):
        camera_hub_config["enabled"] = not camera_hub_config.get("enabled", True)
        save_camera_hub_config()
        status = "🟢 تفعّل" if camera_hub_config["enabled"] else "🔴 توقّف"
        await ctx.send(f"✅ Camera Hub دابا {status}.")


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(CameraHubCog(bot_instance))
