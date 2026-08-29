# -*- coding: utf-8 -*-
"""نظام: Camera Hub — كاتيگوري "video calls" + روم Temp تلقائية لي حاليين الكاميرا.

الفكرة الكاملة (كيفما تصاوبت):
1) البوت كيتأكد أن كاينة كاتيگوري سميتها "video calls" (كيخلقها إلا ماكانتش).
2) كل 5 ثواني، البوت كيشيكي على السيرفر كامل: شكون حالي الكاميرا (self_video)
   فأي روم صوتي — ماعدا الرومات Temp اللي مدارين Private من طرف مولاهم.
3) لي لقاه حالي الكاميرا، كيهزو ويدخلو لروم Temp واحدة كتحل وسط كاتيگوري
   "video calls" (كتتخلق أول مرة تلقاها، وكتتمسح ملي تبقى فارغة).
4) هاد الروم مخصصة غير للي حاليين الكاميرا: لي دخلها وهو ماحاليش الكاميرا
   (سواء دخل بيدو ولا تبقات محلولة عندو من قبل)، البوت كيرجعو تلقائيا
   للروم اللي كان فيها قبل ما يدخل. ملي يحل الكاميرا (وياكد منها البوت
   فالـscan اللي كيجي)، عاد كيرجع يتهز لروم الفيديو.

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

CAMERA_HUB_FILE = os.path.join(DATA_DIR, "camera_hub.json")
VIDEO_CALLS_CATEGORY_NAME = "Video call's 📹"
VIDEO_HUB_CHANNEL_NAME = "Camera Room 🎥"
SCAN_INTERVAL_SECONDS = 5

# مدة سماح بعد كل نقل للهوب (بالثواني) — كتعطي الوقت للعضو يعاود يحل
# الكاميرا يدويا (ديسكورد كيسدها أوتوماتيك عند move_to)، قبل ما نبداو
# نشيكيو عليه ونرجعوه. راها بزيادة على الـ SCAN_INTERVAL_SECONDS، ماشي بدالها.
MOVE_IN_GRACE_SECONDS = 20

# {"enabled": bool, "guilds": {"<guild_id>": {"category_id": int|None, "hub_channel_id": int|None}}}
camera_hub_config = {"enabled": True, "guilds": {}}

# آخر روم "عادية" (ماشي هوب) شافو فيها كل عضو — باش نقدرو نرجعوه ليها إلا طرد من الهوب
_last_non_hub_channel = {}  # {member_id: channel_id}

# آخر وقت (monotonic) تهز فيه كل عضو للهوب — باش نطبقو مدة السماح قبل نرجعوه
_moved_into_hub_at = {}  # {member_id: float}


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
    return guilds.setdefault(str(guild_id), {"category_id": None, "hub_channel_id": None})


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


def _move_notice_embed(member: "discord.Member") -> "discord.Embed":
    """إشعار بالدارجة فقط — من بغا لغة أخرى كيختارها بروحه من القائمة 🌐 تحت."""
    embed = discord.Embed(
        title="🎥 Video Calls — Camera Room",
        description=(
            f"{member.mention} هاد الروم خاصة غير بـ **Video Calls**. تهزيتي ليها "
            f"تلقائياً حيت كنتي حالي الكاميرا فروم أخرى.\n\n"
            f"⚠️ ديسكورد كيسد الكاميرا أوتوماتيك ملي بوت كينقلك — عندك "
            f"**{MOVE_IN_GRACE_SECONDS} ثانية** باش تعاود تحلها يدويا، وإلا "
            f"البوت غايرجعك للروم لي كنتي فيها."
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text=f"{member.display_name} • Camera Hub")
    return embed


class CameraHubCog(commands.Cog):
    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance
        self.camera_scan_loop.start()

    def cog_unload(self):
        self.camera_scan_loop.cancel()

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

        # 3) لي حالي الكاميرا فبراها (وماشي Temp Private) -> يتهز لروم الفيديو
        for vc in guild.voice_channels:
            if hub_id and vc.id == hub_id:
                continue
            if _is_private_temp_room(vc):
                continue
            for m in list(vc.members):
                if m.bot:
                    continue
                if m.voice and m.voice.self_video:
                    if hub_channel is None:
                        hub_channel = await _ensure_hub_channel(guild)
                        if hub_channel is None:
                            return
                        hub_id = hub_channel.id
                    try:
                        await m.move_to(hub_channel, reason="Camera Hub: حالي الكاميرا")
                        _moved_into_hub_at[m.id] = time.monotonic()
                        await log_action(
                            guild,
                            "🎥 Camera Hub — نقل تلقائي",
                            f"**العضو:** {m.mention}\n**من:** {vc.mention}\n**لـ:** {hub_channel.mention}",
                            discord.Color.blurple(),
                        )
                        try:
                            # view فارغة و timeout=None: نظام الترجمة العام ديال
                            # البانلات (cogs/panel_i18n.py) كيزيد ليها وحدو قائمة
                            # 🌐 اللغة، وكل عضو يقدر يختار لغتو الخاصة بروحو —
                            # الرسالة كتبقى (بلا delete_after) بحال باقي البانلات.
                            await hub_channel.send(
                                content=m.mention,
                                embed=_move_notice_embed(m),
                                view=discord.ui.View(timeout=None),
                                allowed_mentions=discord.AllowedMentions(users=[m]),
                            )
                        except (discord.Forbidden, discord.HTTPException):
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
    @commands.hybrid_group(name="camerahub", description="إعدادات Camera Hub")
    @commands.has_permissions(manage_channels=True)
    async def camerahub_group(self, ctx):
        if ctx.invoked_subcommand is None:
            await self.camerahub_status.callback(self, ctx)

    @camerahub_group.command(name="status", description="عرض حالة Camera Hub")
    async def camerahub_status(self, ctx):
        gstate = _guild_state(ctx.guild.id)
        category = ctx.guild.get_channel(gstate.get("category_id")) if gstate.get("category_id") else None
        hub_channel = ctx.guild.get_channel(gstate.get("hub_channel_id")) if gstate.get("hub_channel_id") else None
        embed = discord.Embed(title="🎥 Camera Hub — الحالة", color=discord.Color.blurple())
        embed.add_field(name="النظام", value="🟢 مفعول" if camera_hub_config.get("enabled", True) else "🔴 موقّف", inline=True)
        embed.add_field(name="الفحص كل", value=f"{SCAN_INTERVAL_SECONDS} ثواني", inline=True)
        embed.add_field(name="الكاتيگوري", value=category.mention if category else f"غادي تتخلق باسم `{VIDEO_CALLS_CATEGORY_NAME}`", inline=False)
        embed.add_field(name="روم الفيديو الحالية", value=hub_channel.mention if hub_channel else "— ماكاينش دابا (كتتخلق أوتوماتيك) —", inline=False)
        await ctx.send(embed=embed)

    @camerahub_group.command(name="toggle", description="فعّل/وقّف نظام Camera Hub")
    async def camerahub_toggle(self, ctx):
        camera_hub_config["enabled"] = not camera_hub_config.get("enabled", True)
        save_camera_hub_config()
        status = "🟢 تفعّل" if camera_hub_config["enabled"] else "🔴 توقّف"
        await ctx.send(f"✅ Camera Hub دابا {status}.")


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(CameraHubCog(bot_instance))
