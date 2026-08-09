# -*- coding: utf-8 -*-
"""Unchanged ordered source component: automation_tasks."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
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
    
    
    @bot.event
    async def on_command_error(ctx, error):
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
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
