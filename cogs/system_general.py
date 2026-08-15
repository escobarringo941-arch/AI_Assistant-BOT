# -*- coding: utf-8 -*-
"""General commands, reminders, AI chat, feeds, and server status.

Extracted mechanically from the legacy ai_bot.py.  Runtime state is attached
to bot_core's shared namespace so existing cross-system references keep the
same object identity and startup order.
"""

import bot_core as core

core.attach_namespace(globals())


# ═══════════════════════════════════════════════════════
# ║              AUTO-INFO TASK (مع APIs حقيقية)           ║
# ═══════════════════════════════════════════════════════

@tasks.loop(minutes=30)
async def auto_info():
    """يبعث معلومات من APIs حقيقية — كل 30 دقيقة. كل فئة معزولة (try/except)
    باش خطأ فـ فئة وحدة ما يوقفش اللي بعدها."""

    # ═══════ 📰 NEWS — أخبار عامة ═══════
    if bot_settings['auto_info_news']:
        try:
            news = await get_news_from_api()
            if news:
                embed = discord.Embed(
                    title=f"📰 {news['title']}",
                    description=news['description'],
                    color=discord.Color.blue(),
                    url=news['url'],
                    timestamp=datetime.now()
                )
                embed.set_author(name=f"📡 {news['source']}")
                if news['image']:
                    embed.set_image(url=news['image'])
                embed.set_footer(text="GGMW9 | NewsAPI")
                ping = get_ping_mention("News Ping") or None
                for channel_id in NEWS_CHANNEL_IDS:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(content=ping, embed=embed)
        except Exception as e:
            print(f"[AUTO_INFO] ❌ خطأ فـ NEWS: {e}")

    await asyncio.sleep(2)

    # ═══════ 🎮 GAMES — أخبار ألعاب ═══════
    if bot_settings['auto_info_games']:
        try:
            game = await get_game_from_rawg()
            if game:
                embed = discord.Embed(
                    title=f"🎮 {game['name']}",
                    description=game['description'][:400] + "...",
                    color=discord.Color.green(),
                    url=game['url'],
                    timestamp=datetime.now()
                )
                embed.add_field(name="📅 تاريخ الصدور", value=game['released'], inline=True)
                embed.add_field(name="⭐ التقييم", value=game['rating'], inline=True)
                embed.add_field(name="🎭 النوع", value=game['genres'], inline=False)
                if game['poster']:
                    embed.set_image(url=game['poster'])
                embed.set_footer(text="GGMW9 | RAWG.io")
                ping = get_ping_mention("Games Ping") or None
                for channel_id in GAMES_CHANNEL_IDS:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(content=ping, embed=embed)
        except Exception as e:
            print(f"[AUTO_INFO] ❌ خطأ فـ GAMES: {e}")

    await asyncio.sleep(2)

    # ═══════ 🎬 MOVIES — أفلام + ملخص ═══════
    if bot_settings['auto_info_movies']:
        try:
            movie = await get_movie_from_omdb()
            if movie:
                embed = discord.Embed(
                    title=f"🎬 {movie['title']} ({movie['year']})",
                    description=movie['plot'][:500] + "...",
                    color=discord.Color.gold(),
                    url=movie['imdb'],
                    timestamp=datetime.now()
                )
                embed.add_field(name="🎭 النوع", value=movie['genre'], inline=True)
                embed.add_field(name="⭐ تقييم IMDB", value=f"{movie['rating']}/10", inline=True)
                if movie['poster'] and movie['poster'] != "N/A":
                    embed.set_image(url=movie['poster'])
                embed.set_footer(text="GGMW9 | IMDB via OMDb")
                ping = get_ping_mention("Movies Ping") or None
                for channel_id in MOVIES_CHANNEL_IDS:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(content=ping, embed=embed)
        except Exception as e:
            print(f"[AUTO_INFO] ❌ خطأ فـ MOVIES: {e}")

    await asyncio.sleep(2)

    # ═══════ 📺 ANIME — أنمي + ملخص ═══════
    if bot_settings['auto_info_anime']:
        try:
            anime = await get_anime_from_jikan()
            print(f"[AUTO_INFO] get_anime_from_jikan رجع: {'فيها داتا' if anime else 'فارغة'}")
            if anime:
                embed = discord.Embed(
                    title=f"📺 {anime['title']}",
                    description=anime['synopsis'][:500] + "...",
                    color=discord.Color.purple(),
                    url=anime['url'],
                    timestamp=datetime.now()
                )
                if anime['title_jp']:
                    embed.add_field(name="🇯🇵 الاسم الياباني", value=anime['title_jp'], inline=False)
                embed.add_field(name="📺 النوع", value=anime['type'], inline=True)
                embed.add_field(name="📊 عدد الحلقات", value=str(anime['episodes']), inline=True)
                embed.add_field(name="⭐ تقييم MAL", value=f"{anime['score']}/10", inline=True)
                embed.add_field(name="🎭 الأنواع", value=anime['genres'], inline=False)
                if anime['poster']:
                    embed.set_image(url=anime['poster'])
                embed.set_footer(text="GGMW9 | MyAnimeList via Jikan")
                ping = get_ping_mention("Anime Ping") or None
                for channel_id in ANIME_CHANNEL_IDS:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(content=ping, embed=embed)
                        print("[AUTO_INFO] ✅ تبعث embed ديال الأنمي")
        except Exception as e:
            print(f"[AUTO_INFO] ❌ خطأ فـ ANIME: {e}")

    await asyncio.sleep(2)

    # ═══════ 🎧 MUSIC — موسيقى + أغاني ═══════
    if bot_settings['auto_info_music']:
        try:
            music = await get_music_from_lastfm()
            if music:
                embed = discord.Embed(
                    title=f"🎵 {music['name']}",
                    description=f"أغنية جديدة من **{music['artist']}**",
                    color=discord.Color.red(),
                    url=music['url'],
                    timestamp=datetime.now()
                )
                embed.add_field(name="🎤 الفنان", value=music['artist'], inline=True)
                embed.add_field(name="👥 المستمعين", value=f"{music['listeners']:,}", inline=True)
                if music['poster']:
                    embed.set_image(url=music['poster'])
                embed.set_footer(text="GGMW9 | Last.fm")
                ping = get_ping_mention("Music Ping") or None
                for channel_id in MUSIC_CHANNEL_IDS:
                    channel = bot.get_channel(channel_id)
                    if channel:
                        await channel.send(content=ping, embed=embed)
        except Exception as e:
            print(f"[AUTO_INFO] ❌ خطأ فـ MUSIC: {e}")


@auto_info.before_loop
async def before_auto_info():
    await bot.wait_until_ready()


# ═══════════════════════════════════════════════════════
# ║              GGMW9 STATUS (كل 30 دقيقة)                ║
# ═══════════════════════════════════════════════════════

async def build_stats_embed(guild: discord.Guild) -> discord.Embed:
    """يبني embed فيه الأرقام المباشرة ديال السيرفر"""
    members_count = guild.member_count or len(guild.members)

    # Online = عضو status ديالو ماشي offline (خاص intents.presences مفعلة، وماشي حسبان البوتات)
    online_count = sum(
        1 for m in guild.members
        if not m.bot and m.status != discord.Status.offline
    )

    voice_count = sum(len(vc.members) for vc in guild.voice_channels)

    boosts_count = guild.premium_subscription_count or 0
    boost_level = guild.premium_tier or 0
    boosters_count = len(guild.premium_subscribers) if guild.premium_subscribers else 0

    embed = discord.Embed(
        title=f"📊 {SERVER_NAME} STATUS",
        description=f"[Stats]({SERVER_INVITE_LINK})",
        color=discord.Color.blurple(),
        timestamp=datetime.now()
    )
    embed.add_field(name="👥 Members Count", value=f"{members_count:,}", inline=False)
    embed.add_field(name="🟢 Online Members", value=f"{online_count:,}", inline=False)
    embed.add_field(name="🔊 Members In Voice", value=f"{voice_count:,}", inline=False)
    embed.add_field(
        name="🚀 Server Boosts",
        value=f"Boosts Count : {boosts_count} (Level : {boost_level})",
        inline=False
    )
    embed.add_field(
        name="💎 Boosters",
        value=f"Members Are Boosting: {boosters_count}",
        inline=False
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    if STATS_IMAGE_URL:
        embed.set_image(url=STATS_IMAGE_URL)
    embed.set_footer(text=f"{SERVER_NAME} | آخر تحديث")
    return embed


@tasks.loop(minutes=STATS_UPDATE_MINUTES)
async def update_stats():
    if not STATS_CHANNEL_ID:
        return
    channel = bot.get_channel(STATS_CHANNEL_ID)
    if not channel:
        print(f"[STATS] ❌ ماكاينش channel بـ ID {STATS_CHANNEL_ID}")
        return

    guild = channel.guild
    embed = await build_stats_embed(guild)
    msg_id = stats_message_ids.get(str(guild.id))

    if msg_id:
        try:
            msg = await channel.fetch_message(int(msg_id))
            await msg.edit(embed=embed)
            return
        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception as e:
            print(f"[STATS] خطأ فـ التعديل: {e}")

    try:
        new_msg = await channel.send(embed=embed)
        stats_message_ids[str(guild.id)] = new_msg.id
        save_stats_message_ids()
    except Exception as e:
        print(f"[STATS] خطأ فـ البعث: {e}")


@update_stats.before_loop
async def before_update_stats():
    await bot.wait_until_ready()


@update_stats.error
async def update_stats_error(error):
    print(f"[STATS] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not update_stats.is_running():
        update_stats.restart()


# ═══════════════════════════════════════════════════════
# ║      لائحة الإدارة (Administrators) — كل 30 دقيقة       ║
# ═══════════════════════════════════════════════════════

async def build_admin_list_embed(guild: discord.Guild) -> discord.Embed:
    """يبني embed فيه Owner + Admins + Mods مرتبين بالـ roles، باش لي بغا
    يدير report يعرف بسرعة شكون يدير ليه tag."""
    embed = discord.Embed(
        title="👑 لائحة الإدارة",
        description=(
            "هادي لائحة الـ Owner والـ Admins والـ Moderators ديال السيرفر.\n"
            "إلا بغيتي تدير Report، استعمل <#1535652036324892763> مباشرة."
        ),
        color=discord.Color.gold(),
        timestamp=datetime.now()
    )

    already_listed_ids = set()

    # Owner فوق بوحدو
    owner_member = guild.get_member(OWNER_ID) if OWNER_ID else None
    if OWNER_ID:
        already_listed_ids.add(OWNER_ID)
    embed.add_field(
        name="👑 Owner",
        value=owner_member.mention if owner_member else (f"<@{OWNER_ID}>" if OWNER_ID else "—"),
        inline=False
    )

    # باقي الأدوار بالترتيب المحدد فـ STAFF_ROLES_ORDER
    for entry in STAFF_ROLES_ORDER:
        role = guild.get_role(entry["role_id"])
        if not role:
            embed.add_field(name=entry["label"], value="⚠️ هاد الرول ماكاينش فالسيرفر (تأكد من role_id)", inline=False)
            continue

        members = [m for m in role.members if m.id not in already_listed_ids]
        already_listed_ids.update(m.id for m in members)

        value = "\n".join(m.mention for m in members) if members else "— محدش دابا"
        embed.add_field(name=f"{entry['label']} ({len(members)})", value=value, inline=False)

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.set_footer(text=f"{SERVER_NAME} | آخر تحديث")
    return embed


@tasks.loop(minutes=ADMIN_LIST_UPDATE_MINUTES)
async def update_admin_list():
    if not ADMINISTRATORS_CHANNEL_ID:
        return
    channel = bot.get_channel(ADMINISTRATORS_CHANNEL_ID)
    if not channel:
        print(f"[ADMIN_LIST] ❌ ماكاينش channel بـ ID {ADMINISTRATORS_CHANNEL_ID}")
        return

    guild = channel.guild
    embed = await build_admin_list_embed(guild)
    msg_id = admin_list_message_ids.get(str(guild.id))

    if msg_id:
        try:
            msg = await channel.fetch_message(int(msg_id))
            await msg.edit(embed=embed)
            return
        except (discord.NotFound, discord.Forbidden):
            pass
        except Exception as e:
            print(f"[ADMIN_LIST] خطأ فـ التعديل: {e}")

    try:
        new_msg = await channel.send(embed=embed)
        admin_list_message_ids[str(guild.id)] = new_msg.id
        save_admin_list_message_ids()
    except Exception as e:
        print(f"[ADMIN_LIST] خطأ فـ البعث: {e}")


@update_admin_list.before_loop
async def before_update_admin_list():
    await bot.wait_until_ready()


@update_admin_list.error
async def update_admin_list_error(error):
    print(f"[ADMIN_LIST] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not update_admin_list.is_running():
        update_admin_list.restart()


@auto_info.error
async def auto_info_error(error):
    """إلا وقع خطأ ما تصيدوش try/except ديال الفئات، هادي كنسجلوه، وكنعاودو نشغلو
    الـ loop (بلا هاد الشي، tasks.loop كيوقف نهائيا بصمت ملي يطيح خطأ ما تصيدش)."""
    print(f"[AUTO_INFO] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not auto_info.is_running():
        auto_info.restart()


# ═══════════════════════════════════════════════════════
# ║           Loop: كيتحقق من التذكيرات كل 30 ثانية        ║
# ═══════════════════════════════════════════════════════
@tasks.loop(seconds=30)
async def check_reminders():
    if not reminders:
        return

    now = datetime.now()
    due = [r for r in reminders if datetime.fromisoformat(r["remind_at"]) <= now]
    if not due:
        return

    for r in due:
        try:
            channel = bot.get_channel(r["channel_id"])
            if channel:
                embed = discord.Embed(
                    title="⏰ تذكير!",
                    description=r["message"],
                    color=discord.Color.gold(),
                    timestamp=datetime.now()
                )
                embed.set_footer(text=f"GGMW9 | ID: {r['id']}")
                await channel.send(content=f"<@{r['user_id']}>", embed=embed)
            else:
                print(f"[REMINDERS] ❌ ماكاينش channel بـ ID {r['channel_id']} (تذكير #{r['id']})")
        except Exception as e:
            print(f"[REMINDERS] خطأ فـ بعث التذكير #{r['id']}: {e}")
        reminders.remove(r)

    save_reminders()


@check_reminders.before_loop
async def before_check_reminders():
    await bot.wait_until_ready()


@check_reminders.error
async def check_reminders_error(error):
    print(f"[REMINDERS] ❌❌ خطأ كبير وقف الـ loop: {error}")
    await asyncio.sleep(5)
    if not check_reminders.is_running():
        check_reminders.restart()


class GeneralCog(commands.Cog):
    """Discord command/event registration for this subsystem."""

    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance

    @commands.hybrid_command(description="بين سرعة استجابة البوت")
    async def ping(self, ctx):
        latency = round(bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"**Latency:** {latency}ms\n**API:** DeepSeek V3",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="GGMW9")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="بين معلومات عامة على البوت")
    async def info(self, ctx):
        embed = discord.Embed(
            title="🤖 معلومات GGMW9",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.add_field(name="💬 AI Channel", value=f"`{TARGET_CHANNEL_ID}`", inline=True)
        embed.add_field(name="👋 Welcome", value=f"`{WELCOME_CHANNEL_ID}`", inline=True)
        embed.add_field(name="✅ Verify", value=f"`{VERIFY_CHANNEL_ID}`", inline=True)
        embed.add_field(name="🧠 Memory", value=f"`{MEMORY_SIZE}` msg/user", inline=True)
        embed.add_field(name="⏱️ Timeout", value=f"`{API_TIMEOUT}`s", inline=True)
        embed.add_field(name="🤖 Model", value=f"`{AI_MODEL}`", inline=True)
        embed.add_field(name="📊 Servers", value=f"`{len(bot.guilds)}`", inline=True)
        embed.add_field(name="🛡️ Moderation", value="✅ نشط", inline=False)
        embed.add_field(name="✅ Verification", value="✅ نشط", inline=False)
        embed.add_field(name="📰 Auto-Info", value="✅ نشط (5 channels)", inline=False)
        embed.add_field(
            name="⚠️ Warn Escalation",
            value=f"Mute@{bot_settings['mute_after_warns']} / Kick@{bot_settings['kick_after_warns']} / Ban@{bot_settings['ban_after_warns']}",
            inline=True
        )
        embed.add_field(name="🚫 Banned Words", value=f"`{len(get_active_banned_words())}`", inline=True)
        embed.set_footer(text="GGMW9")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="remind", aliases=["تذكير", "reminder"],
                         description="صاوب تذكير ليك: /remind [#شانيل] 10m/21:00 الرسالة")
    async def remind_cmd(self, ctx, channel: Optional[discord.TextChannel] = None, *, rest: str):
        """
        كل واحد يصاوب تذكير لراسو، فأي وقت وأي شانيل بغى:
        /remind 10m اشرب الما                     ← بعد 10 دقايق، فنفس الشانيل
        /remind 21:00 نوض                         ← اليوم/غدا فـ 21:00، فنفس الشانيل
        /remind #general 2h30m سلام              ← بعد ساعتين ونص، فـ #general
        /remind #announcements 2026-07-25-18:00 حدث ← نهار محدد بالضبط
        """
        parts = rest.strip().split(maxsplit=1)
        if len(parts) < 2:
            await ctx.send(
                "❌ خاصك تحط الوقت والرسالة. مثال: `/remind 10m اشرب الما`\n"
                "استعمل `/help` باش تشوف كاع الصيغ الممكنة.",
                delete_after=15
            )
            return

        وقت, رسالة = parts[0], parts[1]
        target_channel = channel or ctx.channel

        if ctx.guild and target_channel.guild and target_channel.guild.id != ctx.guild.id:
            await ctx.send("❌ الشانيل خاصو يكون فنفس السيرفر.", delete_after=10)
            return

        if ctx.guild:
            perms = target_channel.permissions_for(ctx.guild.me)
            if not perms.send_messages:
                await ctx.send(f"❌ ما عنديش صلاحية نبعث فـ {target_channel.mention}.", delete_after=10)
                return

        target_dt = parse_time_input(وقت)
        if not target_dt:
            embed = discord.Embed(
                title="❌ الوقت ماشي صحيح!",
                description=(
                    "استعمل شي صيغة من هادو:\n"
                    "`10m` / `2h` / `1h30m` / `1d` — بعد مدة من دابا\n"
                    "`21:00` — اليوم فهاد الساعة (وإلا غدا إلا فاتت)\n"
                    "`2026-07-25-21:00` — نهار محدد بالضبط\n\n"
                    "مثال كامل: `/remind #general 2h30m سلام`"
                ),
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=25)
            return

        if target_dt <= datetime.now():
            await ctx.send("❌ الوقت لي حطيتي فات! حط وقت فالمستقبل.", delete_after=10)
            return

        if target_dt > datetime.now() + timedelta(days=90):
            await ctx.send("❌ ما نقدرش نحط تذكير فوق 90 يوم.", delete_after=10)
            return

        global next_reminder_id
        reminder = {
            "id": next_reminder_id,
            "user_id": str(ctx.author.id),
            "channel_id": target_channel.id,
            "guild_id": ctx.guild.id if ctx.guild else None,
            "message": رسالة,
            "remind_at": target_dt.isoformat(),
            "created_at": datetime.now().isoformat(),
        }
        reminders.append(reminder)
        next_reminder_id += 1
        core.next_reminder_id = next_reminder_id
        save_reminders()

        ts = int(target_dt.timestamp())
        embed = discord.Embed(
            title="⏰ تسجل التذكير!",
            description=f"غادي نذكرك بـ:\n> {رسالة}",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="📅 وقت التذكير", value=f"<t:{ts}:F> (<t:{ts}:R>)", inline=False)
        embed.add_field(name="📍 الشانيل", value=target_channel.mention, inline=False)
        embed.set_footer(text=f"GGMW9 | ID: {reminder['id']}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="reminders", aliases=["تذكيراتي"])
    async def reminders_cmd(self, ctx):
        """كيبين التذكيرات المبرمجة ديال الشخص اللي طلب الأمر"""
        user_id = str(ctx.author.id)
        user_reminders = sorted(
            (r for r in reminders if r["user_id"] == user_id),
            key=lambda r: r["remind_at"]
        )
        if not user_reminders:
            await ctx.send("📭 ماعندكش أي تذكير مبرمج دابا.", delete_after=10)
            return

        embed = discord.Embed(title="⏰ التذكيرات ديالك", color=discord.Color.blue(), timestamp=datetime.now())
        for r in user_reminders[:15]:
            ts = int(datetime.fromisoformat(r["remind_at"]).timestamp())
            text = r["message"] if len(r["message"]) <= 200 else r["message"][:200] + "..."
            chan_txt = f"<#{r['channel_id']}>"
            embed.add_field(name=f"#{r['id']}", value=f"{text}\n<t:{ts}:R> — {chan_txt}", inline=False)
        embed.set_footer(text="/delreminder <ID> باش تلغي وحدة")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="delreminder", aliases=["حذف_تذكير"])
    async def delreminder_cmd(self, ctx, reminder_id: int):
        """كيحيد تذكير (غير ديال الشخص اللي صاوبو)"""
        user_id = str(ctx.author.id)
        target = next((r for r in reminders if r["id"] == reminder_id and r["user_id"] == user_id), None)
        if not target:
            await ctx.send("❌ ماكاينش هاد التذكير عندك (تأكد من الـ ID).", delete_after=10)
            return
        reminders.remove(target)
        save_reminders()
        await ctx.send(f"✅ تحذاف التذكير #{reminder_id}.", delete_after=10)

    @commands.hybrid_command(description="بين لائحة كاع الأوامر")
    async def help(self, ctx):
        embed = discord.Embed(
            title="📋 قائمة أوامر GGMW9",
            description=(
                "**GGMW9** — بوت AI مغربي + Moderation + Verification + Auto-Info\n"
                "💡 كاع الأوامر دابا Slash Commands (`/`) بوحدها — اكتب `/` باش تشوف اللائحة ديال Discord."
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        ai_cmds = (
            "`/chat <رسالة>` — هضر مع GGMW9\n"
            "`/نسيني` — امسح ذاكرتك\n"
            "`/ذاكرة` — شحال من رسالة فالذاكرة\n"
            "`/انعلمك <حاجة>` — علم GGMW9 شي حاجة"
        )
        embed.add_field(name="🤖 AI & ذاكرة", value=ai_cmds, inline=False)
        mod_cmds = (
            "`/kick @user [سبب]` — طرد عضو\n"
            "`/ban @user [سبب]` — حظر عضو\n"
            "`/unban <user_id>` — فك الحظر\n"
            "`/mute @user <دقائق> [سبب]` — كتم\n"
            "`/unmute @user` — فك الكتم\n"
            "`/warn @user <سبب>` — تحذير\n"
            "`/warns [@user]` — عرض التحذيرات\n"
            "`/unwarn @user` — مسح التحذيرات\n"
            "`/case <رقم>` — تفاصيل Case معين\n"
            "`/history [@user]` — سجل الـ Cases ديال عضو\n"
            "`/clear <عدد>` — حذف رسائل (1-100)"
        )
        embed.add_field(name="🛡️ موديراتورز", value=mod_cmds, inline=False)
        verif_cmds = (
            "`/setupverify` — صاوب رسالة التفعيل بـ ✅ (Admin)\n"
            "`/setuprules` — صاوب رسالة القوانين بـ أزرار كنوافق/كنرفض (Admin)\n"
            "`/verify @user` — يفعّل عضو يدوياً (Admin)\n"
            "`/unverify @user` — يرجعو @Unverified (Admin)"
        )
        embed.add_field(name="✅ تفعيل", value=verif_cmds, inline=False)
        ticket_cmds = (
            "`/setuptickets` — صاوب/عاود صاوب لوحة الـ Tickets (Admin)\n"
            "🎫 ضغط على الزر فاللوحة → كيتحلق channel خاص\n"
            "`/closeticket` — سد ticket بأمر (بديل للزر، جوة channel الـ ticket)"
        )
        embed.add_field(name="🎫 Tickets", value=ticket_cmds, inline=False)
        application_cmds = (
            "📋 ضغط على الزر فاللوحة → عمر الاستمارة (Modal)\n"
            "`/setupapplications` — صاوب/عاود صاوب لوحة الـ Applications (Admin)\n"
            "`/applications` — بين الطلبات المعلقة (Admin)\n"
            "✅/❌ أزرار قبول/رفض فـ channel المراجعة (Staff)"
        )
        embed.add_field(name="📋 Applications", value=application_cmds, inline=False)
        suggestion_cmds = (
            "`/suggest <فكرة>` — بعث اقتراح جديد\n"
            "👍/👎 صوّت على الاقتراحات ديال الآخرين\n"
            "✅/❌ أزرار قبول/رفض (Staff)"
        )
        embed.add_field(name="💡 Suggestions", value=suggestion_cmds, inline=False)
        birthday_cmds = (
            "`/setbirthday <يوم> <شهر>` — سجل عيد ميلادك (كيعطيك رول البرج أوتوماتيكياً ♈)\n"
            "`/birthday [@عضو]` — بين عيد ميلادك ولا ديال عضو (والبرج)\n"
            "`/birthdays` — أقرب 10 أعياد ميلاد جاية\n"
            "`/removebirthday` — حيد عيد ميلادك من السجل (وحيد رول البرج)"
        )
        embed.add_field(name="🎂 Birthdays", value=birthday_cmds, inline=False)
        relationship_cmds = (
            "`/marry @عضو` — اطلب زواج 💍 (خاصو يقبل بزر)\n"
            "`/divorce` — طلق الزوج/الزوجة ديالك\n"
            "`/marriage [@عضو]` — بين معلومات الزواج\n"
            "`/marriages` — أطول 10 علاقات فالسيرفر\n"
            "`/bestfriend @عضو` — اطلب Best Friend 🤝\n"
            "`/unbestfriend` — قطع الصداقة\n"
            "`/bestfriendinfo [@عضو]`, `/bestfriends` — معلومات و Leaderboard"
        )
        embed.add_field(name="💌 Marry / Bestfriend", value=relationship_cmds, inline=False)
        voice_room_cmds = (
            "`/roommutepanel [روم]` — بانل كامل للتحكم فروم صوتي (Staff/صاحب الروم):\n"
            "🔇 **كتم الكل** — كيكتم كاع اللي فالروم بلا استثناء (حتى Admin/Mod) + أي واحد يدخل من بعد كيتكتم توا\n"
            "🔊 **فك الكل** — كيفك الكتم على الجميع ويحل الروم عادي\n"
            "🎯 **Select عضو معين** — بدل الحالة (كتم/فك) ديال شخص وحدو بوحدو، بلا ماتمس الباقي\n"
            "`/voicerename`, `/voicelimit`, `/voicelock`, `/voiceunlock` — تحكم فالروم المؤقت ديالك"
        )
        embed.add_field(name="🎙️ Voice Rooms", value=voice_room_cmds, inline=False)
        raid_cmds = (
            "`/lockdown [دقائق]` — فعّل Anti-Raid Lockdown يدوياً (Admin)\n"
            "`/unlockdown` — سد الـ Lockdown يدوياً (Admin)\n"
            "`/raidstatus` — شوف الحالة دابا"
        )
        embed.add_field(name="🚨 Anti-Raid", value=raid_cmds, inline=False)
        embed.add_field(
            name="🖼️ Welcome Card",
            value="`/testwelcome [@عضو]` — جرب شكل الكارطة الترحيبية هنا فالشات (Admin)",
            inline=False
        )
        level_cmds = (
            "`/rank [@user]` — شوف المستوى والـ XP ديالك ولا ديال عضو آخر\n"
            "`/leaderboard` — أفضل 10 أعضاء نشيطين\n"
            "`/setlevel @user <رقم>` — حط عضو فمستوى معين يدوياً (Admin)\n"
            "`/setuplevels` — صاوب/عاود صاوب رسالة شرح النظام (Admin)"
        )
        embed.add_field(name="📊 Leveling", value=level_cmds, inline=False)
        roles_cmds = (
            "`/setuproles` — صاوب رسالة اختيار الأدوار (Admin)\n"
            "`/listroles` — بين رسائل Reaction Roles الفعّالة (Admin)"
        )
        embed.add_field(name="🎭 Reaction Roles", value=roles_cmds, inline=False)
        util_cmds = (
            "`/ping` — سرعة البوت\n"
            "`/info` — معلومات البوت\n"
            "`/help` — هاد القائمة"
        )
        embed.add_field(name="🔧 أدوات", value=util_cmds, inline=False)
        reminder_cmds = (
            "`/remind [#شانيل] <وقت> <رسالة>` — صاوب تذكير\n"
            "`/remind 10m اشرب الما` — بعد 10 دقايق، فنفس الشانيل\n"
            "`/remind 21:00 نوض` — اليوم فـ 21:00 (وإلا غدا إلا فاتت)\n"
            "`/remind #general 2h30m سلام` — بعد ساعتين ونص، فـ #general\n"
            "`/remind #الشانيل 2026-07-25-18:00 حدث` — نهار محدد بالضبط\n"
            "`/reminders` — التذكيرات ديالك المبرمجة\n"
            "`/delreminder <ID>` — لغي تذكير"
        )
        embed.add_field(name="⏰ تذكيرات", value=reminder_cmds, inline=False)
        auto_mod = (
            "✅ كلمات ممنوعة\n"
            "✅ كشف السبام (5 msg/5s)\n"
            "✅ Auto-mute\n"
            "✅ Auto-kick (3 warns)\n"
            "✅ Logs كاملة فـ #mod-logs بـ Case ID (`/case`, `/history`)"
        )
        embed.add_field(name="🤖 Auto-Mod", value=auto_mod, inline=False)
        auto_info_cmds = (
            "📰 #news — أخبار عامة (NewsAPI)\n"
            "🎮 #games — أخبار ألعاب (RAWG)\n"
            "🎬 #movies — أفلام + ملخصات (IMDB/OMDb)\n"
            "📺 #anime — أنمي + ملخصات (MyAnimeList/Jikan)\n"
            "🎧 #music — أخبار موسيقى + أغاني (Last.fm)\n"
            "⏱️ كل 30 دقيقة"
        )
        embed.add_field(name="📰 Auto-Info", value=auto_info_cmds, inline=False)
        verif_info = (
            "🔒 @Unverified — جديد (ما يهضرش)\n"
            "✅ @Member — مفعل (يهضر)\n"
            "🔄 كليك ✅ فـ verify channel، ولا الأزرار (كنوافق/كنرفض) فـ rules channel"
        )
        embed.add_field(name="🔐 نظام التفعيل", value=verif_info, inline=False)
        embed.set_footer(text="GGMW9 | Slash Commands: /")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="هضر مع البوت (AI)")
    @commands.cooldown(1, AI_USER_COOLDOWN_SECONDS, commands.BucketType.user)
    async def chat(self, ctx, *, message: str):
        if ctx.channel.id != TARGET_CHANNEL_ID:
            return
        user_id = str(ctx.author.id)
        response = await ask_ai(user_id, ctx.author.name, ctx.author.display_name, message)
        await ctx.send(response[:MAX_REPLY_LENGTH])

    @commands.hybrid_command(description="امسح الذاكرة ديال المحادثة (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def نسيني(self, ctx):
        user_id = str(ctx.author.id)
        if user_id in user_memory:
            user_memory[user_id] = []
            await ctx.send("✅ نسيت كلشي! جديد من هنا.")
        else:
            await ctx.send("ما عندي والو ننساه!")

    @commands.hybrid_command(description="بين الذاكرة ديال المحادثة (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def ذاكرة(self, ctx):
        user_id = str(ctx.author.id)
        count = len(user_memory.get(user_id, [])) // 2
        await ctx.send(f"🧠 عندي {count} رسالة فـ الذاكرة ديالك.")

    @commands.hybrid_command(description="علم البوت شي معلومة جديدة (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def انعلمك(self, ctx, *, knowledge: str):
        learned_knowledge.append(knowledge)
        gender = detect_gender(ctx.author.name, ctx.author.display_name)
        if gender == "female":
            await ctx.send(f"✅ **واخا الالة!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")
        else:
            await ctx.send(f"✅ **واخا أسيدي!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ ما عندكش الصلاحية!",
                description="خاصك تكون موديراتور باش تستخدم هاد الأمر.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=5)
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = discord.Embed(
                title="❌ ناقص شي حاجة!",
                description=f"استخدم `/help` باش تشوف كيفاش تستخدم الأمر.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=5)
        elif isinstance(error, commands.MemberNotFound):
            embed = discord.Embed(
                title="❌ ما لقيتش هاد العضو!",
                description="تأكد من الـ mention ولا الـ ID.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=5)
        elif isinstance(error, commands.BadArgument):
            embed = discord.Embed(
                title="❌ خطأ فـ المدخلات!",
                description="الرقم ولا الـ ID ما صحيحش.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=5)
        elif isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                title="❌ ما عندكش الصلاحية!",
                description="هاد الأمر خاص غير بـ Owner ديال السيرفر.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, delete_after=5)
        else:
            print(f"[ERROR] {error}")


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(GeneralCog(bot_instance))
