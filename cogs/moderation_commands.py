# -*- coding: utf-8 -*-
"""Unchanged ordered source component: moderation_commands."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
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
    
    
    @bot.hybrid_command(name="case")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def case_cmd(ctx, case_id: int):
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
    
    
    @bot.hybrid_command(name="history")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def history_cmd(ctx, member: Optional[discord.Member] = None):
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
    
    
    # ═══════════════════════════════════════════════════════
    # ║   OWNER ONLY — إدارة اللائحة الممنوعة (سري، ماشي فالقناة)  ║
    # ═══════════════════════════════════════════════════════
    # هاد الأوامر خاصة غير بالـ Owner (بواسطة الـ ID فـ OWNER_ID)، حتى
    # الـ Admins والـ Moderators ما يقدروش يستعملوها. الرسالة ديال الأمر
    # كتمسح مباشرة، والجواب كيوصل بـ DM للـ Owner فقط — باش حتى حد آخر فالسيرفر
    # ما يشوف واش تزادت/تحيدت شي كلمة، وواش شكون دارها.
    
    @bot.hybrid_command(name="addword", description="زيد كلمة للائحة الكلمات الممنوعة")
    @app_commands.default_permissions(administrator=True)
    async def addword_cmd(ctx, *, word: str = ""):
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
    
    
    @bot.hybrid_command(name="removeword", description="حيد كلمة من لائحة الكلمات الممنوعة")
    @app_commands.default_permissions(administrator=True)
    async def removeword_cmd(ctx, *, word: str = ""):
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
    
    
    @bot.hybrid_command(name="addaction", description="زيد عبارة/سلوك ممنوع (Owner)")
    @app_commands.default_permissions(administrator=True)
    async def addaction_cmd(ctx, *, phrase: str = ""):
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
    
    
    @bot.hybrid_command(name="removeaction", description="حيد جملة من لائحة الجمل الممنوعة")
    @app_commands.default_permissions(administrator=True)
    async def removeaction_cmd(ctx, *, phrase: str = ""):
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
    
    
    @bot.hybrid_command(name="listbanned")
    @app_commands.default_permissions(administrator=True)
    async def listbanned_cmd(ctx):
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
    
    
    # ═══════════════════════════════════════════════════════
    # ║   OWNER ONLY — تحكم كامل فالسيرفر (كتم/حظر/طرد)          ║
    # ═══════════════════════════════════════════════════════
    # هاد الأوامر منفصلة على /kick//ban//mute العاديين (اللي خدامين بالصلاحيات
    # ديال Discord)، وخاصة غير بالـ Owner الحقيقي ديال السيرفر فديسكورد
    # (guild.owner_id) — نفس الفحص بالضبط اللي كيدير بانل السجن، باش يبقى
    # موحّد بين البانل والأوامر اليدوية. حتى admin/mod ما يقدروش يستعملوها.
    # الـ Admins والـ Moderators كيبقاو خدامين بالأوامر العادية فوق حسب
    # الصلاحيات ديال الـ role ديالهم بحال ماكانو.
    
    def _is_real_owner(ctx) -> bool:
        """كيتأكد بلي الشخص هو بالضبط الأونر الحقيقي ديال السيرفر فديسكورد
        (guild.owner_id) — نفس المنطق ديال prison_panel.py."""
        return bool(ctx.guild) and ctx.author.id == ctx.guild.owner_id
    
    @bot.hybrid_command(name="ownerkick", description="اطرد عضو (Owner بوحدو)")
    @app_commands.default_permissions(administrator=True)
    async def ownerkick_cmd(ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
        if not _is_real_owner(ctx):
            return
        if member.id == member.guild.owner_id:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
            return
        # 🔒 ما بقاش كاين طرد — كيمشي للسجن.
        from cogs.prison import imprison_member
        from cogs.prison_core import format_duration as _fmt
        result = await imprison_member(
            bot, member, offense_key="kick", reason=reason, actor=ctx.author
        )
        if not result.get("ok"):
            await ctx.send(f"❌ {result.get('error')}", delete_after=8)
            return
        record = result["record"]
        # 🕵️ Owner stealth: ما كيتسجل والو فـ Mod-Logs، والرد خاص بالاونر بوحدو.
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(
            f"⛓️ {member.mention} تحط فالسجن ({_fmt(int(record['sentence']))}). "
            f"Prison Case #{record['case']}",
            ephemeral=True,
            delete_after=10,
        )
    
    
    @bot.hybrid_command(name="ownerban", description="احظر عضو (Owner بوحدو)")
    @app_commands.default_permissions(administrator=True)
    async def ownerban_cmd(ctx, member: discord.Member, *, reason="ما ذكرش سبب"):
        if not _is_real_owner(ctx):
            return
        if member.id == member.guild.owner_id:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
            return
        # 🔒 ما بقاش كاين حظر — سجن مشدد فـ maximum-security.
        from cogs.prison import imprison_member
        from cogs.prison_core import format_duration as _fmt
        result = await imprison_member(
            bot, member, offense_key="ban", reason=reason, actor=ctx.author
        )
        if not result.get("ok"):
            await ctx.send(f"❌ {result.get('error')}", delete_after=8)
            return
        record = result["record"]
        # 🕵️ Owner stealth: ما كيتسجل والو فـ Mod-Logs.
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(
            f"🚨 {member.mention} تحط فـ Maximum Security ({_fmt(int(record['sentence']))}). "
            f"Prison Case #{record['case']}",
            ephemeral=True,
            delete_after=10,
        )
    
    
    @bot.hybrid_command(name="ownermute", description="كتم عضو (Owner بوحدو)")
    @app_commands.default_permissions(administrator=True)
    async def ownermute_cmd(ctx, member: discord.Member, duration: int = 5, *, reason="ما ذكرش سبب"):
        if not _is_real_owner(ctx):
            return
        if member.id == member.guild.owner_id:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!", delete_after=5)
            return
        # 🔒 الكتم ولّى حبس قصير فـ holding-cell.
        from cogs.prison import imprison_member
        from cogs.prison_core import format_duration as _fmt
        result = await imprison_member(
            bot, member, offense_key="mute",
            seconds=max(60, int(duration) * 60), reason=reason, actor=ctx.author
        )
        if not result.get("ok"):
            await ctx.send(f"❌ {result.get('error')}", delete_after=8)
            return
        record = result["record"]
        # 🕵️ Owner stealth: ما كيتسجل والو فـ Mod-Logs.
        try:
            await ctx.message.delete()
        except Exception:
            pass
        await ctx.send(
            f"⛓️ {member.mention} تحط فـ Holding Cell ({_fmt(int(record['sentence']))}). "
            f"Prison Case #{record['case']}",
            ephemeral=True,
            delete_after=10,
        )
    
    
    @bot.hybrid_command(name="muteall")
    @app_commands.default_permissions(administrator=True)
    async def muteall_cmd(ctx, *, reason="Server Lockdown (Owner)"):
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
            if member.bot or member.id == member.guild.owner_id or is_exempt(member):
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
    
    
    @bot.hybrid_command(name="unmuteall")
    @app_commands.default_permissions(administrator=True)
    async def unmuteall_cmd(ctx):
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
    
    
    # ═══════════════════════════════════════════════════════
    # ║        Anti-Raid — أوامر التحكم اليدوي (Admin/Owner)     ║
    # ═══════════════════════════════════════════════════════
    
    @bot.hybrid_command(name="lockdown")
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def lockdown_cmd(ctx, duration_minutes: int = None):
        """كيفعّل Anti-Raid Lockdown يدوياً (بلا ماتوصل عتبة الانضمامات) — Admin/Owner"""
        if not (is_owner(ctx) or any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)):
            await ctx.send("❌ هاد الأمر خاص غير بـ Owner والـ Admin.", delete_after=6)
            return
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
    
    
    @bot.hybrid_command(name="unlockdown")
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def unlockdown_cmd(ctx):
        """كيسد Anti-Raid Lockdown يدوياً ويرجع verification level للحالة العادية — Admin/Owner"""
        if not (is_owner(ctx) or any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)):
            await ctx.send("❌ هاد الأمر خاص غير بـ Owner والـ Admin.", delete_after=6)
            return
        ended = await end_raid_lockdown(ctx.guild, reason=f"يدوي من طرف {ctx.author.mention}")
        if ended:
            await ctx.send("✅ Lockdown تسد، الوضعية رجعت عادية.")
        else:
            await ctx.send("ℹ️ ماكاين حتى Lockdown مفعل دابا.", delete_after=6)
    
    
    @bot.hybrid_command(name="raidstatus")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def raidstatus_cmd(ctx):
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
    
    
    @bot.hybrid_command(name="testwelcome", description="بعث Welcome Card تجريبية هنا فالشات (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def testwelcome_cmd(ctx, member: Optional[discord.Member] = None, returning: bool = False):
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
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
