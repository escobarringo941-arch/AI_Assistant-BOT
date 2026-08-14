# -*- coding: utf-8 -*-
"""Unchanged ordered source component: member_events."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    @bot.event
    async def on_member_join(member):
        # ═══════════════════════════════════════════════════════
        # ║              Anti-Raid Protection                       ║
        # ═══════════════════════════════════════════════════════
        if bot_settings['anti_raid_enabled']:
            raid_triggered_now = await _check_and_maybe_trigger_raid(member.guild)
            state = raid_state.get(member.guild.id, {})
    
            if state.get("active"):
                # Raid Mode مفعل → كل عضو جديد كيتطبق عليه bot_settings['raid_action'] مباشرة
                # (كيطرد "kick" ولا كيبان "ban" — كيفما هو مضبوط، ماشي حبس)
                try:
                    action = bot_settings['raid_action']
                    reason = "انضم خلال فترة Anti-Raid Lockdown"
                    if action == "ban":
                        await member.guild.ban(member, reason=reason, delete_message_seconds=0)
                        action_label = "🚨 حظر تلقائي (Anti-Raid)"
                    else:
                        await member.guild.kick(member, reason=reason)
                        action_label = "🚨 طرد تلقائي (Anti-Raid)"
                    color = discord.Color.dark_red()
    
                    await log_case(
                        member.guild, action_label, action_label.split(" ")[0], color,
                        target=member, moderator=None,
                        reason=reason,
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
    
    
    @bot.event
    async def on_member_remove(member):
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
    
    
    @bot.event
    async def on_raw_reaction_add(payload):
        guild = bot.get_guild(payload.guild_id)
        if not guild:
            return
        member = guild.get_member(payload.user_id)
        if not member or member.bot:
            return
    
        # ═══════ الترجمة التلقائية بالـ Reaction (علم الدولة 🇬🇧🇫🇷) — كتخدم فأي channel ═══════
        if bot_settings['auto_translate_enabled'] and str(payload.emoji) in FLAG_TO_LANGUAGE:
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
        # وافق على القوانين → كنمسحو ليه الرسالة الترحيبية (وأي رسالة أخرى) من الـ DM
        await purge_bot_dm_messages(member)
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
    
    
    @bot.event
    async def on_message_delete(message):
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
    
    
    @bot.event
    async def on_message_edit(before, after):
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
    
    
    @bot.event
    async def on_message(message):
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
        gender = detect_gender(message.author.name, message.author.display_name)
    
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
                    # 🔒 السبام كيدير حبس فـ holding-cell بدل الـMute.
                    from cogs.prison import imprison_member
                    from cogs.prison_core import format_duration as _fmt
                    result = await imprison_member(
                        bot, message.author, offense_key="spam",
                        reason=f"سبام: {len(spam_tracker[user_id])} رسالة فـ {SPAM_INTERVAL} ثواني",
                        actor=None,
                    )
                    if result.get("ok"):
                        record = result["record"]
                        await log_action(
                            message.guild,
                            "🛑 Auto-Mod | سبام مكتشف",
                            f"**المستخدم:** {message.author.mention}\n"
                            f"**الإجراء:** ⛓️ سجن {_fmt(int(record['sentence']))} (تلقائي)\n"
                            f"**Prison Case:** #{record['case']}\n"
                            f"**الرسائل:** {len(spam_tracker[user_id])} فـ {SPAM_INTERVAL} ثواني",
                            discord.Color.orange()
                        )
                        spam_tracker[user_id] = []
                except discord.Forbidden:
                    pass
    
        await maybe_auto_react_translate(message)
    
        if "ggmw9" in msg_lower:
            await message.reply("نعام! 😂 واش بغيتي؟", mention_author=False)
            return
        if "غيرها" in msg_lower:
            await message.reply("وخا أسي زبي 😂", mention_author=False)
            return
        if "سير تقود" in msg_lower or "تقود" in msg_lower:
            await message.reply("وخا هاني غادي نتقود دابا 🏃‍♂️", mention_author=False)
            return
        if "مالك" in msg_lower and ("ازبي" in msg_lower or "زبي" in msg_lower):
            if gender == "female":
                await message.reply("زبي فكرك مخبي ابنت القحبة 😂", mention_author=False)
            else:
                await message.reply("زبي فكرك مخبي اولد القحبة 😂", mention_author=False)
            return
        if "قحبة" in msg_lower:
            await message.reply("القحبة هي مك 😂", mention_author=False)
            return
        if "سير تحوا" in msg_lower:
            if gender == "female":
                await message.reply("سيري تحواي نتي نيت 😂", mention_author=False)
            else:
                await message.reply("سير تحوا نتا نيت 😂", mention_author=False)
            return
        if "اهيا" in msg_lower or "اه" in msg_lower:
            await message.reply("وي مالك؟ 🤔", mention_author=False)
            return
        if "شحال" in msg_lower and "ساعة" in msg_lower:
            await message.reply("ساعاتو لله 🕐", mention_author=False)
            return
        if "زبي" in msg_lower or "ازبي" in msg_lower:
            replies = [
                "ههههه ونتا؟ 😂",
                "صافي صافي، ريح مع كرك",
                "ياك خويا، هدي راسك شوية",
                "زبي فكرك مخبي 😂"
            ]
            await message.reply(random.choice(replies), mention_author=False)
            return
        if "لقلاوي" in msg_lower or "لقلاو" in msg_lower:
            await message.reply("ههههه لقلاوي نتا 😂", mention_author=False)
            return
        if "زامل" in msg_lower:
            if gender == "female":
                await message.reply("ههههه زاملة نتي 😂", mention_author=False)
            else:
                await message.reply("ههههه زامل نتا 😂", mention_author=False)
            return
        insults = ["حمار", "غبي", "قحبة", "زامل", "طاحون", "بوليس", "ولد القحبة", 
                   "wld l9ahba", "nik mok", "tabon", "zamel", "7mar", "9a7ba", "tahwan",
                   "لي حواك", "قواد", "طبون مك", "ابن القحبة", "ابنت القحبة",
                   "نيك", "زب", "احا", "فمك", "كسمك", "كس"]
        is_insult = any(insult in msg_lower for insult in insults)
        if is_insult:
            if gender == "female":
                replies = [
                    "ههههه ونتي نيت ابنت القحبة 😂",
                    "صافي صافي، ريحي مع كرك 😂",
                    "ياك اختي، هدي راسك شوية",
                    "ههههه نتي اللي جاييا تهضري معايا؟"
                ]
            else:
                replies = [
                    "ههههه ونتا نيت اولد القحبة 😂",
                    "صافي صافي، ريح مع كرك 😂",
                    "ياك خويا، هدي راسك شوية",
                    "ههههه نتا اللي جاي تهضر معايا؟"
                ]
            await message.reply(random.choice(replies), mention_author=False)
            return
        if message.channel.id != TARGET_CHANNEL_ID:
            return
        user_id = str(message.author.id)
        response = await ask_ai(
            user_id, 
            message.author.name, 
            message.author.display_name, 
            message.content
        )
        await message.reply(response[:MAX_REPLY_LENGTH], mention_author=False)
    
    
    
    
    
    @bot.command(name="report", hidden=True)
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def report(
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
    async def report_error(ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            try:
                await ctx.author.send(
                    f"⏳ صبر شوية ({error.retry_after:.0f}ث) قبل بلاغ آخر."
                )
            except discord.HTTPException:
                pass
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
