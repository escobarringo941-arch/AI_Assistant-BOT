# -*- coding: utf-8 -*-
"""Unchanged ordered source component: general_commands."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    @bot.hybrid_command(description="بين سرعة استجابة البوت")
    async def ping(ctx):
        latency = round(bot.latency * 1000)
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"**Latency:** {latency}ms\n**API:** DeepSeek V3",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="GGMW9")
        await ctx.send(embed=embed)
    
    
    @bot.hybrid_command(description="بين معلومات عامة على البوت")
    async def info(ctx):
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
    
    
    @bot.hybrid_command(name="remind", aliases=["تذكير", "reminder"],
                         description="صاوب تذكير ليك: /remind [#شانيل] 10m/21:00 الرسالة")
    async def remind_cmd(ctx, channel: Optional[discord.TextChannel] = None, *, rest: str):
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
    
    
    @bot.hybrid_command(name="reminders", aliases=["تذكيراتي"])
    async def reminders_cmd(ctx):
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
    
    
    @bot.hybrid_command(name="delreminder", aliases=["حذف_تذكير"])
    async def delreminder_cmd(ctx, reminder_id: int):
        """كيحيد تذكير (غير ديال الشخص اللي صاوبو)"""
        user_id = str(ctx.author.id)
        target = next((r for r in reminders if r["id"] == reminder_id and r["user_id"] == user_id), None)
        if not target:
            await ctx.send("❌ ماكاينش هاد التذكير عندك (تأكد من الـ ID).", delete_after=10)
            return
        reminders.remove(target)
        save_reminders()
        await ctx.send(f"✅ تحذاف التذكير #{reminder_id}.", delete_after=10)
    
    
    @bot.hybrid_command(description="بين لائحة كاع الأوامر")
    async def help(ctx):
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
    
    
    @bot.hybrid_command(description="هضر مع البوت (AI)")
    @commands.cooldown(1, AI_USER_COOLDOWN_SECONDS, commands.BucketType.user)
    async def chat(ctx, *, message: str):
        if not (
            ctx.channel.id == TARGET_CHANNEL_ID
            or (
                isinstance(ctx.channel, discord.Thread)
                and ctx.channel.parent_id == TARGET_CHANNEL_ID
            )
        ):
            return
        private_ai = bot.get_cog("PrivateAIChat")
        if private_ai is not None:
            await private_ai.handle_hybrid_chat(ctx, message)
    
    
    @bot.hybrid_command(description="امسح الذاكرة ديال المحادثة (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def نسيني(ctx):
        user_id = str(ctx.author.id)
        if user_id in user_memory:
            user_memory[user_id] = []
            await ctx.send("✅ نسيت كلشي! جديد من هنا.")
        else:
            await ctx.send("ما عندي والو ننساه!")
    
    
    @bot.hybrid_command(description="بين الذاكرة ديال المحادثة (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def ذاكرة(ctx):
        user_id = str(ctx.author.id)
        count = len(user_memory.get(user_id, [])) // 2
        await ctx.send(f"🧠 عندي {count} رسالة فـ الذاكرة ديالك.")
    
    
    @bot.hybrid_command(description="علم البوت شي معلومة جديدة (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def انعلمك(ctx, *, knowledge: str):
        learned_knowledge.append(knowledge)
        gender = detect_gender(ctx.author.name, ctx.author.display_name)
        if gender == "female":
            await ctx.send(f"✅ **واخا الالة!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")
        else:
            await ctx.send(f"✅ **واخا أسيدي!** تعلمت: {knowledge[:100]}... نتذكرها دايمن! 🧠")
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
