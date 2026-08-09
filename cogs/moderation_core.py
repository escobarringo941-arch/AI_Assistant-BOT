# -*- coding: utf-8 -*-
"""Unchanged ordered source component: moderation_core."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║              MODERATION FUNCTIONS                       ║
    # ═══════════════════════════════════════════════════════
    
    async def log_action(guild, title: str, description: str, color: discord.Color):
        channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"GGMW9 | {datetime.now().strftime('%H:%M:%S')}")
            await channel.send(embed=embed)
    
    
    async def log_case(guild, action: str, emoji: str, color: discord.Color,
                        target, moderator, reason: str, extra: str = None) -> int:
        """
        كتسجل عقوبة/إجراء كـ 'Case' برقم فريد ومتزايد، كتحفظها فـ cases.json
        (باقية حتى بعد ريستارت)، وكتبعث embed احترافي موحد فـ MOD_LOGS_CHANNEL_ID.
        target/moderator: discord.Member/discord.User أو None (مثلا Auto-Mod بلا منفذ بشري).
        كترجع رقم الـ Case باش تقدر تبينو للمستخدم مباشرة.
        """
        case_id = cases_db.get("next_id", 1)
        cases_db["next_id"] = case_id + 1
    
        target_id = getattr(target, "id", None)
        target_name = str(target) if target else "غير معروف"
        mod_id = getattr(moderator, "id", None)
        mod_name = str(moderator) if moderator else "Auto-Mod (System)"
    
        record = {
            "id": case_id,
            "action": action,
            "target_id": target_id,
            "target_name": target_name,
            "moderator_id": mod_id,
            "moderator_name": mod_name,
            "reason": reason or "ما ذكرش سبب",
            "extra": extra,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        cases_db.setdefault("cases", {})[str(case_id)] = record
        save_cases()
    
        channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title=f"{emoji} {action} — Case #{case_id}",
                color=color,
                timestamp=datetime.now()
            )
            embed.add_field(
                name="🎯 العضو",
                value=f"{target.mention} ({target_name})" if hasattr(target, "mention") else target_name,
                inline=False
            )
            embed.add_field(
                name="🛡️ نفذ من طرف",
                value=(moderator.mention if hasattr(moderator, "mention") else mod_name),
                inline=False
            )
            embed.add_field(name="📝 السبب", value=reason or "ما ذكرش سبب", inline=False)
            if extra:
                embed.add_field(name="ℹ️ تفاصيل إضافية", value=extra, inline=False)
            embed.set_footer(text=f"{SERVER_NAME} | Case #{case_id}")
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[CASES] خطأ فـ بعث embed ديال Case #{case_id}: {e}")
    
        return case_id
    
    
    def get_case(case_id) -> Optional[dict]:
        return cases_db.get("cases", {}).get(str(case_id))
    
    
    def get_cases_for_user(user_id: int) -> list:
        """كترجع كاع الحالات ديال عضو معين، الأحدث فالأول"""
        all_cases = list(cases_db.get("cases", {}).values())
        user_cases = [c for c in all_cases if c.get("target_id") == user_id]
        user_cases.sort(key=lambda c: c["id"], reverse=True)
        return user_cases
    
    
    def check_role_hierarchy(guild: discord.Guild) -> list:
        """
        كيتأكد أن role ديال البوت فوق فالترتيب من الرولات اللي خاصو يعطي/يهزها
        (Member, Unverified, Muted). كيرجع لائحة ديال المشاكل (فاضية = كلشي مزيان).
        """
        problems = []
        bot_member = guild.me
        if not bot_member:
            return ["❌ ما قدرتش نلقى البوت فالسيرفر."]
    
        bot_top_role = bot_member.top_role
    
        roles_to_check = {
            "Member": MEMBER_ROLE_ID,
            "Unverified": UNVERIFIED_ROLE_ID,
            "Muted": MUTED_ROLE_ID,
        }
    
        for role_name, role_id in roles_to_check.items():
            role = guild.get_role(role_id)
            if not role:
                problems.append(f"⚠️ role ديال **{role_name}** (ID: `{role_id}`) ماكاينش فالسيرفر — تأكد من الـ ID فالـ CONFIG.")
                continue
            if role >= bot_top_role:
                problems.append(
                    f"❌ role ديال **{role_name}** (`{role.name}`) فوق ولا مساوي لـ role ديال البوت (`{bot_top_role.name}`) "
                    f"فالترتيب — خاصك تسحب role ديال البوت فوق منو فـ **Server Settings → Roles**."
                )
    
        if not bot_member.guild_permissions.manage_roles:
            problems.append("❌ role ديال البوت ماعندوش صلاحية **Manage Roles** — خاصك تفعلها.")
    
        return problems
    
    
    async def send_warn_dm(member: discord.Member, count: int, reason: str):
        """
        كيبعث فـ DM تنبيه احترافي للعضو ملي ياخد تحذير (يدوي ولا أوتوماتيكي)،
        فيه رقم التحذير، السبب، وجدول العقوبات المتدرجة (كتم/طرد/حظر) مبني
        على الأرقام الحقيقية ديال الـ CONFIG. مكتوب بـ 3 لغات: الدارجة، الفرنسية، الإنجليزية.
        """
        embed = discord.Embed(
            title="⚠️ تحذير جديد | Avertissement | Warning",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
    
        embed.add_field(
            name="🇲🇦 بالدارجة",
            value=(
                f"خذيتي تحذير فـ **{SERVER_NAME}**.\n"
                f"**السبب:** {reason}\n"
                f"**عدد التحذيرات ديالك دابا:** {count}\n\n"
                f"⚠️ **خاصك تعرف:**\n"
                f"🔇 عند {bot_settings['mute_after_warns']} تحذيرات → كتم تلقائي لمدة {bot_settings['mute_duration_minutes']} دقيقة\n"
                f"👢 عند {bot_settings['kick_after_warns']} تحذيرات → طرد تلقائي من السيرفر\n"
                f"🚫 عند {bot_settings['ban_after_warns']} تحذيرات → حظر نهائي من السيرفر\n\n"
                f"من فضلك احترم/ي قوانين السيرفر باش ما توصلش لهاد المراحل."
            ),
            inline=False
        )
        embed.add_field(
            name="🇫🇷 En Français",
            value=(
                f"Vous avez reçu un avertissement sur **{SERVER_NAME}**.\n"
                f"**Raison :** {reason}\n"
                f"**Nombre total d'avertissements :** {count}\n\n"
                f"⚠️ **À savoir :**\n"
                f"🔇 À {bot_settings['mute_after_warns']} avertissements → mute automatique pendant {bot_settings['mute_duration_minutes']} minutes\n"
                f"👢 À {bot_settings['kick_after_warns']} avertissements → expulsion automatique du serveur\n"
                f"🚫 À {bot_settings['ban_after_warns']} avertissements → bannissement définitif du serveur\n\n"
                f"Merci de respecter les règles du serveur pour éviter d'en arriver là."
            ),
            inline=False
        )
        embed.add_field(
            name="🇬🇧 In English",
            value=(
                f"You have received a warning on **{SERVER_NAME}**.\n"
                f"**Reason:** {reason}\n"
                f"**Total warnings:** {count}\n\n"
                f"⚠️ **Please note:**\n"
                f"🔇 At {bot_settings['mute_after_warns']} warnings → automatic mute for {bot_settings['mute_duration_minutes']} minutes\n"
                f"👢 At {bot_settings['kick_after_warns']} warnings → automatic kick from the server\n"
                f"🚫 At {bot_settings['ban_after_warns']} warnings → permanent ban from the server\n\n"
                f"Please follow the server rules to avoid reaching these stages."
            ),
            inline=False
        )
        embed.set_footer(text=f"{SERVER_NAME} | Moderation System")
    
        try:
            await member.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass
    
    
    async def add_warn(member: discord.Member, reason: str) -> int:
        user_id = str(member.id)
        if user_id not in warns_db:
            warns_db[user_id] = {"count": 0, "reasons": [], "dates": []}
        warns_db[user_id]["count"] += 1
        warns_db[user_id]["reasons"].append(reason)
        warns_db[user_id]["dates"].append(datetime.now().strftime("%Y-%m-%d %H:%M"))
        count = warns_db[user_id]["count"]
        await send_warn_dm(member, count, reason)
        return count
    
    
    def is_exempt(member: discord.Member) -> bool:
        """واش هاد العضو معفي من Auto-Mod (Owner ولا شي رول معفي)"""
        if OWNER_ID and member.id == OWNER_ID:
            return True
        if EXEMPT_ROLE_IDS:
            member_role_ids = {role.id for role in member.roles}
            if member_role_ids.intersection(EXEMPT_ROLE_IDS):
                return True
        return False
    
    
    def get_warns(user_id: str) -> dict:
        return warns_db.get(user_id, {"count": 0, "reasons": [], "dates": []})
    
    
    def clear_warns(user_id: str):
        if user_id in warns_db:
            warns_db[user_id] = {"count": 0, "reasons": [], "dates": []}
    
    
    async def auto_unmute(member: discord.Member, duration_minutes: int, guild: discord.Guild):
        await asyncio.sleep(duration_minutes * 60)
        muted_role = guild.get_role(MUTED_ROLE_ID)
        if muted_role and muted_role in member.roles:
            try:
                await member.remove_roles(muted_role)
                await log_action(
                    guild,
                    "🔊 فك الكتم (تلقائي)",
                    f"**المستخدم:** {member.mention}\n"
                    f"**المدة:** {duration_minutes} دقيقة\n"
                    f"**السبب:** انتهت المدة",
                    discord.Color.green()
                )
            except discord.Forbidden:
                pass
    
    
    async def setup_verify_message(guild: discord.Guild):
        """Refresh the existing verification message in-place; create it only if missing."""
        verify_channel = bot.get_channel(VERIFY_CHANNEL_ID)
        if not verify_channel:
            return False
    
        embed = discord.Embed(
            title="✅ تفعيل العضوية",
            description=(
                f"**مرحبا بيك فـ {SERVER_NAME}!**\n\n"
                f"قبل ما تقدر/ي تهضر/ي فالسيرفر، خاصك توافق/ي على القوانين.\n\n"
                f"**الخطوات:**\n"
                f"1️⃣ قرا/ي القوانين فـ <#{RULES_CHANNEL_ID}>\n"
                f"2️⃣ كليك/ي على ✅ تحت\n\n"
                f"**ملاحظة:** إلا ما وافقتيش، ما غاديش تقدر/ي تهضر/ي ولا تفاعل/ي!"
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.set_footer(text="GGMW9 | Verification System")
    
        matches = []
        try:
            async for message in verify_channel.history(limit=30):
                if message.author != bot.user:
                    continue
                title = message.embeds[0].title if message.embeds else ""
                if title == "✅ تفعيل العضوية":
                    matches.append(message)
        except discord.Forbidden:
            return False
    
        try:
            if matches:
                keep = matches[0]
                await keep.edit(embed=embed)
                try:
                    # Keep the classic ✅ reaction verification fresh as well.
                    if not any(str(r.emoji) == "✅" for r in keep.reactions):
                        await keep.add_reaction("✅")
                except (discord.Forbidden, discord.HTTPException):
                    pass
                for extra in matches[1:]:
                    try:
                        await extra.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
            else:
                keep = await verify_channel.send(embed=embed)
                await keep.add_reaction("✅")
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
