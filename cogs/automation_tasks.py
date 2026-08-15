# -*- coding: utf-8 -*-
"""Unchanged ordered source component: automation_tasks."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║       AUTO-INFO احترافي: جديد، مقيّم وبلا تكرار        ║
    # ═══════════════════════════════════════════════════════

    def _auto_info_excerpt(text: str, limit: int = 650) -> str:
        text = re.sub(r"\s+", " ", str(text or "")).strip()
        if len(text) <= limit:
            return text
        return text[:limit].rsplit(" ", 1)[0].rstrip("،,.;: ") + "…"


    def _auto_info_published_time(value: str) -> str:
        """كيعرض وقت الخبر بصيغة Discord محلية عند كل عضو."""
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return f"<t:{int(parsed.timestamp())}:R>"
        except (TypeError, ValueError, OSError):
            return str(value or "غير محدد")


    async def _get_auto_info_channel(channel_id: int):
        channel = bot.get_channel(int(channel_id))
        if channel is not None:
            return channel
        try:
            return await bot.fetch_channel(int(channel_id))
        except Exception as exc:
            print(f"[AUTO_INFO] ❌ ما قدرناش نوصلو للقناة {channel_id}: {exc}")
            return None


    async def _send_auto_info_embed(channel_ids, ping_role_name: str, embed: discord.Embed) -> int:
        sent = 0
        ping = get_ping_mention(ping_role_name) or None
        for channel_id in dict.fromkeys(int(value) for value in channel_ids):
            channel = await _get_auto_info_channel(channel_id)
            if channel is None or not hasattr(channel, "send"):
                continue
            try:
                await channel.send(content=ping, embed=embed)
                sent += 1
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[AUTO_INFO] ❌ فشل النشر فـ {channel_id}: {exc}")
        return sent


    async def _purge_auto_info_channel(channel) -> tuple[bool, int]:
        """مسح متدرج: كيكمّل القناة كاملة بلا Timeout ديال purge ضخم واحد."""
        total_deleted = 0
        for _batch in range(500):
            try:
                deleted = await channel.purge(
                    limit=100,
                    bulk=True,
                    reason="GGMW9 Auto-Info professional fresh start",
                )
            except discord.Forbidden:
                # بلا Manage Messages نقدر نمسحو غير رسائل البوت؛ القناة ما
                # كتتحسبش صافية إلا بقا فيها مساج ديال شي عضو آخر.
                complete = True
                try:
                    async for message in channel.history(limit=None, oldest_first=False):
                        if bot.user and message.author.id == bot.user.id:
                            await message.delete(reason="GGMW9 Auto-Info fresh start")
                            total_deleted += 1
                        else:
                            complete = False
                    return complete, total_deleted
                except (discord.Forbidden, discord.HTTPException):
                    return False, total_deleted
            except discord.HTTPException as exc:
                print(f"[AUTO_INFO-RESET] ⏳ خطأ مؤقت فـ {channel.id}: {exc}")
                return False, total_deleted

            total_deleted += len(deleted)
            if len(deleted) < 100:
                return True, total_deleted
            # كنخلي Discord rate-limit يتنفس بين الدفعات الكبيرة.
            await asyncio.sleep(1)
        return False, total_deleted


    async def prepare_auto_info_fresh_start() -> bool:
        """كيكمل القنوات الناقصة فقط، وكيرجع True غير ملي الخمسة كاملين تصفرو."""
        if not auto_info_state.get("history_cleared", False):
            clear_all_posted_history()
            mark_auto_info_history_cleared()

        channel_ids = list(dict.fromkeys(
            NEWS_CHANNEL_IDS + GAMES_CHANNEL_IDS + MOVIES_CHANNEL_IDS
            + ANIME_CHANNEL_IDS + MUSIC_CHANNEL_IDS
        ))
        all_complete = True
        for channel_id in channel_ids:
            if is_auto_info_channel_cleared(channel_id):
                continue
            channel = await _get_auto_info_channel(channel_id)
            if channel is None or not hasattr(channel, "purge"):
                print(f"[AUTO_INFO-RESET] ⚠️ {channel_id}: ماشي Text Channel أو ما تلقاتش")
                all_complete = False
                continue
            complete, deleted_count = await _purge_auto_info_channel(channel)
            if complete:
                mark_auto_info_channel_cleared(channel_id)
                print(f"[AUTO_INFO-RESET] ✅ {channel_id}: تمسحو {deleted_count} رسالة")
            else:
                all_complete = False
                print(
                    f"[AUTO_INFO-RESET] ❌ {channel_id}: باقي ما تصفاتش؛ "
                    "غادي يعاود أوتوماتيكياً قبل البث (خاص Manage Messages/Read History)."
                )
        return all_complete and all(
            is_auto_info_channel_cleared(channel_id) for channel_id in channel_ids
        )


    @tasks.loop(hours=AUTO_INFO_INTERVAL_HOURS)
    async def auto_info():
        """منشور ممتاز لكل فئة مباشرة عند التشغيل، ومن بعدها مرة كل ساعة."""

        if bot_settings["auto_info_news"]:
            try:
                news = await get_news_from_api()
                if news:
                    embed = discord.Embed(
                        title=f"📰 {news['title']}",
                        description=_auto_info_excerpt(news["description"]),
                        color=discord.Color.blue(),
                        url=news["url"],
                        timestamp=datetime.now(),
                    )
                    embed.set_author(name=f"📡 المصدر: {news['source']}")
                    if news.get("published_at"):
                        embed.add_field(
                            name="🕒 تاريخ النشر",
                            value=_auto_info_published_time(news["published_at"]),
                            inline=True,
                        )
                    embed.add_field(name="✅ الحالة", value="خبر جديد وما تنشرش من قبل", inline=True)
                    embed.set_image(url=news["image"])
                    embed.set_footer(text="GGMW9 • أخبار مختارة • NewsAPI")
                    if await _send_auto_info_embed(NEWS_CHANNEL_IDS, "News Ping", embed):
                        mark_posted_many("news", news["history_keys"])
            except Exception as exc:
                print(f"[AUTO_INFO] ❌ خطأ فـ NEWS: {exc}")

        await asyncio.sleep(2)

        if bot_settings["auto_info_games"]:
            try:
                game = await get_game_from_rawg()
                if game:
                    embed = discord.Embed(
                        title=f"🎮 {game['name']}",
                        description=_auto_info_excerpt(game["description"]),
                        color=discord.Color.green(),
                        url=game["url"],
                        timestamp=datetime.now(),
                    )
                    embed.add_field(name="⭐ تقييم RAWG", value=f"{game['rating']:.1f}/5", inline=True)
                    embed.add_field(name="👥 عدد التقييمات", value=f"{game['ratings_count']:,}", inline=True)
                    embed.add_field(name="🏅 Metacritic", value=str(game["metacritic"]), inline=True)
                    embed.add_field(name="📅 تاريخ الصدور", value=game["released"], inline=True)
                    embed.add_field(name="🎭 الأنواع", value=game["genres"], inline=False)
                    embed.set_image(url=game["poster"])
                    embed.set_footer(text="GGMW9 • من أفضل الألعاب • RAWG")
                    if await _send_auto_info_embed(GAMES_CHANNEL_IDS, "Games Ping", embed):
                        mark_posted_many("games", game["history_keys"])
            except Exception as exc:
                print(f"[AUTO_INFO] ❌ خطأ فـ GAMES: {exc}")

        await asyncio.sleep(2)

        if bot_settings["auto_info_movies"]:
            try:
                movie = await get_movie_from_omdb()
                if movie:
                    embed = discord.Embed(
                        title=f"🎬 {movie['title']} ({movie['year']})",
                        description=_auto_info_excerpt(movie["plot"]),
                        color=discord.Color.gold(),
                        url=movie["imdb"],
                        timestamp=datetime.now(),
                    )
                    embed.add_field(name="⭐ تقييم IMDb", value=f"{movie['rating']}/10", inline=True)
                    embed.add_field(name="👥 عدد الأصوات", value=f"{movie['votes']:,}", inline=True)
                    embed.add_field(name="🏅 Metascore", value=str(movie["metascore"]), inline=True)
                    embed.add_field(name="🎭 الأنواع", value=movie["genre"], inline=False)
                    embed.set_image(url=movie["poster"])
                    embed.set_footer(text="GGMW9 • من أفضل الأفلام • IMDb / OMDb")
                    if await _send_auto_info_embed(MOVIES_CHANNEL_IDS, "Movies Ping", embed):
                        mark_posted_many("movies", movie["history_keys"])
            except Exception as exc:
                print(f"[AUTO_INFO] ❌ خطأ فـ MOVIES: {exc}")

        await asyncio.sleep(2)

        if bot_settings["auto_info_anime"]:
            try:
                anime = await get_anime_from_jikan()
                if anime:
                    embed = discord.Embed(
                        title=f"📺 {anime['title']}",
                        description=_auto_info_excerpt(anime["synopsis"]),
                        color=discord.Color.purple(),
                        url=anime["url"],
                        timestamp=datetime.now(),
                    )
                    embed.add_field(name="⭐ تقييم MAL", value=f"{anime['score']}/10", inline=True)
                    embed.add_field(name="🏆 الترتيب العالمي", value=f"#{anime['rank']}", inline=True)
                    embed.add_field(name="👥 عدد المقيمين", value=f"{anime['scored_by']:,}", inline=True)
                    embed.add_field(name="📺 النوع والحلقات", value=f"{anime['type']} • {anime['episodes']}", inline=True)
                    embed.add_field(name="🎭 الأنواع", value=anime["genres"], inline=False)
                    if anime.get("title_jp"):
                        embed.add_field(name="🇯🇵 الاسم الياباني", value=anime["title_jp"], inline=False)
                    embed.set_image(url=anime["poster"])
                    embed.set_footer(text="GGMW9 • من أفضل الأنمي • MyAnimeList / Jikan")
                    if await _send_auto_info_embed(ANIME_CHANNEL_IDS, "Anime Ping", embed):
                        mark_posted_many("anime", anime["history_keys"])
            except Exception as exc:
                print(f"[AUTO_INFO] ❌ خطأ فـ ANIME: {exc}")

        await asyncio.sleep(2)

        if bot_settings["auto_info_music"]:
            try:
                music = await get_music_from_lastfm()
                if music:
                    embed = discord.Embed(
                        title=f"🎵 {music['name']}",
                        description=f"اختيار موسيقي مميز من **{music['artist']}**.",
                        color=discord.Color.red(),
                        url=music["url"],
                        timestamp=datetime.now(),
                    )
                    embed.add_field(name="🎤 الفنان", value=music["artist"], inline=True)
                    embed.add_field(name="👥 المستمعون", value=f"{music['listeners']:,}", inline=True)
                    embed.add_field(name="▶️ مرات التشغيل", value=f"{music['playcount']:,}", inline=True)
                    embed.add_field(name="🏆 ترتيبها عند الفنان", value=f"#{music['rank']}", inline=True)
                    embed.set_image(url=music["poster"])
                    embed.set_footer(text="GGMW9 • موسيقى من الأكثر شعبية • Last.fm")
                    if await _send_auto_info_embed(MUSIC_CHANNEL_IDS, "Music Ping", embed):
                        mark_posted_many("music", music["history_keys"])
            except Exception as exc:
                print(f"[AUTO_INFO] ❌ خطأ فـ MUSIC: {exc}")


    @auto_info.before_loop
    async def before_auto_info():
        await bot.wait_until_ready()
        # ما نبداو حتى خبر حتى تكمل حتى آخر قناة (الموسيقى داخلة فالحساب).
        while not bot.is_closed():
            if await prepare_auto_info_fresh_start():
                print("[AUTO_INFO-RESET] ✅ القنوات الخمسة تصفرو؛ البث غادي يبدا دابا.")
                break
            print("[AUTO_INFO-RESET] ⏳ غادي نعاود القنوات الناقصة من بعد 30 ثانية.")
            await asyncio.sleep(30)
    
    
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
        def remember(message_id: int):
            if stats_message_ids.get(str(guild.id)) != int(message_id):
                stats_message_ids[str(guild.id)] = int(message_id)
                save_stats_message_ids()

        await upsert_fixed_panel(
            bot,
            channel,
            key="server_status",
            matches=lambda msg: (
                msg.author == bot.user
                and bool(msg.embeds)
                and (msg.embeds[0].title or "") == f"📊 {SERVER_NAME} STATUS"
                and f"{SERVER_NAME} | آخر تحديث" in (
                    msg.embeds[0].footer.text if msg.embeds[0].footer else ""
                )
            ),
            embed=embed,
            message_id=msg_id,
            save_message_id=remember,
            history_limit=100,
        )
    
    
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
    
    async def build_admin_list_embed(guild: discord.Guild, lang: str = "darija") -> discord.Embed:
        """يبني embed فيه Owner + Admins + Mods مرتبين بالـ roles، باش لي بغا
        يدير report يعرف بسرعة شكون يدير ليه tag."""
        lang = lang if lang in {"darija", "en", "fr"} else "darija"
        if lang == "en":
            title = "👑 Administrators"
            desc = (
                "This is the list of the server's Owner, Admins and Moderators.\n"
                "To file a Report, use <#1535652036324892763> directly."
            )
            owner_label, none_now, missing_role = "👑 Owner", "— nobody right now", "⚠️ This role doesn't exist on the server (check role_id)"
        elif lang == "fr":
            title = "👑 Administration"
            desc = (
                "Voici la liste du Owner, des Admins et des Modérateurs du serveur.\n"
                "Pour faire un Report, utilise directement <#1535652036324892763>."
            )
            owner_label, none_now, missing_role = "👑 Owner", "— personne pour l'instant", "⚠️ Ce rôle n'existe pas sur le serveur (vérifie le role_id)"
        else:
            title = "👑 لائحة الإدارة"
            desc = (
                "هادي لائحة الـ Owner والـ Admins والـ Moderators ديال السيرفر.\n"
                "إلا بغيتي تدير Report، استعمل <#1535652036324892763> مباشرة."
            )
            owner_label, none_now, missing_role = "👑 Owner", "— محدش دابا", "⚠️ هاد الرول ماكاينش فالسيرفر (تأكد من role_id)"

        embed = discord.Embed(
            title=title,
            description=desc,
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
    
        already_listed_ids = set()
    
        # Owner فوق بوحدو
        owner_member = guild.get_member(OWNER_ID) if OWNER_ID else None
        if OWNER_ID:
            already_listed_ids.add(OWNER_ID)
        embed.add_field(
            name=owner_label,
            value=owner_member.mention if owner_member else (f"<@{OWNER_ID}>" if OWNER_ID else "—"),
            inline=False
        )
    
        # باقي الأدوار بالترتيب المحدد فـ STAFF_ROLES_ORDER
        for entry in STAFF_ROLES_ORDER:
            role = guild.get_role(entry["role_id"])
            if not role:
                embed.add_field(name=entry["label"], value=missing_role, inline=False)
                continue
    
            members = [m for m in role.members if m.id not in already_listed_ids]
            already_listed_ids.update(m.id for m in members)
    
            value = "\n".join(m.mention for m in members) if members else none_now
            embed.add_field(name=f"{entry['label']} ({len(members)})", value=value, inline=False)
    
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.set_footer(text=f"{SERVER_NAME} | آخر تحديث")
        return embed


    class _AdminListLanguageSelect(discord.ui.Select):
        """بانل عمومي بالدارجة بشكل ثابت — اختيار اللغة كيحل نسخة خاصة مترجمة (نفس نمط بانل الزواج)."""
        def __init__(self, *, private_user_id: int = None, lang: str = "darija", row: int = 0):
            self.private_user_id = private_user_id
            lang = lang if lang in {"darija", "en", "fr"} else "darija"
            kwargs = dict(
                placeholder="🌐 اللغة / Language / Langue",
                options=[
                    discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", default=lang == "darija"),
                    discord.SelectOption(label="English", value="en", emoji="🇬🇧", default=lang == "en"),
                    discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", default=lang == "fr"),
                ],
                min_values=1, max_values=1, row=row,
            )
            if not private_user_id:
                kwargs["custom_id"] = "ggmw9:admin_list:language"
            super().__init__(**kwargs)

        async def callback(self, interaction: discord.Interaction):
            if self.private_user_id and interaction.user.id != self.private_user_id:
                await interaction.response.send_message("❌ هاد الترجمة ماشي ديالك.", ephemeral=True)
                return
            lang = set_panel_language(interaction.guild.id, interaction.user.id, self.values[0])
            embed = await build_admin_list_embed(interaction.guild, lang)
            view = AdminListView(private_user_id=interaction.user.id, lang=lang)
            if self.private_user_id:
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


    class AdminListView(discord.ui.View):
        """View ثابت على البانل العمومي (Administrators channel) فيه غير select ديال اللغة."""
        def __init__(self, *, private_user_id: int = None, lang: str = "darija"):
            super().__init__(timeout=None if not private_user_id else 1800)
            self.add_item(_AdminListLanguageSelect(private_user_id=private_user_id, lang=lang, row=0))
    
    
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
        def remember(message_id: int):
            if admin_list_message_ids.get(str(guild.id)) != int(message_id):
                admin_list_message_ids[str(guild.id)] = int(message_id)
                save_admin_list_message_ids()

        await upsert_fixed_panel(
            bot,
            channel,
            key="admin_list",
            matches=lambda msg: (
                msg.author == bot.user
                and bool(msg.embeds)
                and (msg.embeds[0].title or "") == "👑 لائحة الإدارة"
                and f"{SERVER_NAME} | آخر تحديث" in (
                    msg.embeds[0].footer.text if msg.embeds[0].footer else ""
                )
            ),
            embed=embed,
            view=AdminListView(),
            message_id=msg_id,
            save_message_id=remember,
            history_limit=100,
        )
    
    
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
