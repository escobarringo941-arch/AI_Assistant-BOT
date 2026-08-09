# -*- coding: utf-8 -*-
"""Unchanged ordered source component: verification_commands."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    @bot.command(name="setlevel", hidden=True)
    @owner_only()
    async def setlevel_cmd(ctx, member: discord.Member, level: int):
        """كيحط عضو مباشرة فمستوى معين (Admin) — مفيد إلا بغيتي تصحح غلط ولا تعطي مستوى بداية.
        كيزبط الرول ديال المستوى أوتوماتيكيا: كيحيد الرول القديم (بحال Level 10)
        وكيعطي الرول الصحيح ديال المستوى الجديد (بحال Level 15) — رول واحد بوحدو فأي وقت."""
        data = get_user_level_data(ctx.guild.id, member.id)
        data["level"] = max(0, level)
        data["xp"] = 0
        save_levels()
    
        roles_added, roles_removed = await sync_level_roles(member, ctx.guild, data["level"])
    
        msg = f"✅ {member.mention} تحط فـ Level {data['level']}."
        if roles_added:
            msg += f"\n🎖️ رول جديد: {', '.join(roles_added)}"
        if roles_removed:
            msg += f"\n🗑️ تحيدو: {', '.join(roles_removed)}"
        await ctx.send(msg)
        await _owner_private_dm(
            member,
            f"🎚️ إدارة GGMW9 بدلات المستوى ديالك بشكل خاص: Level {data['level']}."
        )
    
    
    @bot.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def clearoldverify(ctx):
        """كيمسح رسالة/رسائل 'تفعيل العضوية' القديمة (بالريأكشن ✅) من verify channel"""
        verify_channel = bot.get_channel(VERIFY_CHANNEL_ID)
        rules_channel = bot.get_channel(RULES_CHANNEL_ID)
        deleted = 0
        for channel in {verify_channel, rules_channel}:
            if not channel:
                continue
            async for message in channel.history(limit=50):
                if message.author == bot.user and "تفعيل العضوية" in (message.embeds[0].title if message.embeds else ""):
                    try:
                        await message.delete()
                        deleted += 1
                    except Exception:
                        pass
        await ctx.send(f"✅ تمسحو {deleted} رسالة/رسائل قديمة." if deleted else "ماكاينش شي رسالة قديمة باش تتمسح.", delete_after=8)
    
    
    @bot.hybrid_command(description="صاوب رسالة التفعيل/القوانين (Owner)")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setupverify(ctx):
        await setup_verify_message(ctx.guild)
        await ctx.send("✅ تم صاوب رسالة التفعيل!", delete_after=5)
    
    
    @bot.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setupblacklist(ctx):
        """يصاوب رسالة الممنوعات والعقوبات فـ Blacklist channel"""
        if not BLACKLIST_CHANNEL_ID:
            await ctx.send("❌ خاصك تحط `BLACKLIST_CHANNEL_ID` فالـ CONFIG أولاً!")
            return
        await setup_blacklist_message(ctx.guild)
        await ctx.send("✅ تم صاوب رسالة Blacklist!", delete_after=5)
    
    
    @bot.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setuprules(ctx):
        """يصاوب رسالة القوانين + زرارات كنوافق/كنرفض فـ rules channel"""
        await setup_rules_message(ctx.guild)
        await ctx.send("✅ تم صاوب رسالة القوانين بالأزرار!", delete_after=5)
    
    
    @bot.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setuproles(ctx):
        """يصاوب رسالة اختيار الأدوار بـ Dropdown Menus (خاصك تعمر PICK_ROLES فـ config أولاً)"""
        has_any_valid_role = any(
            r["role_id"] for roles_list in PICK_ROLES.values() for r in roles_list
        )
        if not has_any_valid_role:
            await ctx.send(
                "❌ ماكاين حتى رول صالح فـ `PICK_ROLES`!\n"
                "خاصك تحط IDs ديال الأدوار فـ config (فعّل Developer Mode فـ Discord، "
                "بعدها كليك يمين على الرول → Copy ID)."
            )
            return
    
        description_lines = ["اختار من اللائحة (Dropdown) تحت باش تاخد الأدوار، وعاود اختار باش تبدلها 🔄\n"]
        for category_name, roles_list in PICK_ROLES.items():
            valid = [r for r in roles_list if r["role_id"]]
            if not valid:
                continue
            description_lines.append(f"**{category_name}**")
            description_lines.append(", ".join(f"{r['emoji']} {r['label']}" for r in valid))
            description_lines.append("")
    
        embed = discord.Embed(
            title="🎭 اختار الأدوار ديالك",
            description="\n".join(description_lines),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_footer(text="GGMW9 | Pick Roles")
    
        await ctx.send(embed=embed, view=RolePickerView())
        await ctx.send("✅ تصاوبات رسالة الأدوار!", delete_after=5)
    
    
    @bot.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def listroles(ctx):
        """يبين لائحة الأدوار المعمرة دابا فـ PICK_ROLES"""
        lines = []
        for category_name, roles_list in PICK_ROLES.items():
            valid = [r for r in roles_list if r["role_id"]]
            if not valid:
                continue
            roles_text = ", ".join(f"{r['emoji']} {r['label']} → <@&{r['role_id']}>" for r in valid)
            lines.append(f"**{category_name}**\n{roles_text}")
    
        if not lines:
            await ctx.send("ماكاين حتى رول معمر دابا فـ `PICK_ROLES`. عمر IDs ديال الأدوار فـ config.")
            return
    
        embed = discord.Embed(
            title="🎭 الأدوار المعمرة فـ PICK_ROLES",
            description="\n\n".join(lines),
            color=discord.Color.blue()
        )
        embed.set_footer(text="GGMW9 | Pick Roles")
        await ctx.send(embed=embed)
    
    
    @bot.hybrid_command(description="فعّل عضو يدوياً (Admin)")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def verify(ctx, member: discord.Member):
        unverified_role = ctx.guild.get_role(UNVERIFIED_ROLE_ID)
        if unverified_role and unverified_role in member.roles:
            await member.remove_roles(unverified_role)
        member_role = ctx.guild.get_role(MEMBER_ROLE_ID)
        if member_role:
            await member.add_roles(member_role)
        embed = discord.Embed(
            title="✅ تفعيل يدوي",
            description=f"**{member.mention}** تم تفعيله.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
        embed.set_footer(text="GGMW9 | Verification")
        await ctx.send(embed=embed)
        await log_action(
            ctx.guild,
            "✅ تفعيل يدوي",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**المنفذ:** {ctx.author.mention}",
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
                view=GenderSelectView(target_user_id=member.id, guild_id=ctx.guild.id)
            )
        except Exception:
            pass
    
    
    @bot.hybrid_command()
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def checkroles(ctx):
        """كيتأكد أن role ديال البوت قادر يعطي Member/Unverified/Muted"""
        problems = check_role_hierarchy(ctx.guild)
        if not problems:
            embed = discord.Embed(
                title="✅ كلشي مزيان",
                description="role ديال البوت فوق فالترتيب وعندو الصلاحيات اللازمة. نظام التفعيل خاصو يخدم عادي.",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="⚠️ لقيت مشاكل فترتيب الرولات",
                description="\n\n".join(problems),
                color=discord.Color.red()
            )
        embed.set_footer(text="GGMW9 | Role Hierarchy Check")
        await ctx.send(embed=embed)
    
    
    @bot.hybrid_command(description="رجع عضو Unverified (Admin)")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def unverify(ctx, member: discord.Member):
        member_role = ctx.guild.get_role(MEMBER_ROLE_ID)
        if member_role and member_role in member.roles:
            await member.remove_roles(member_role)
        unverified_role = ctx.guild.get_role(UNVERIFIED_ROLE_ID)
        if unverified_role:
            await member.add_roles(unverified_role)
        embed = discord.Embed(
            title="🔄 إلغاء التفعيل",
            description=f"**{member.mention}** تم إلغاء تفعيله.",
            color=discord.Color.orange(),
            timestamp=datetime.now()
        )
        embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
        embed.set_footer(text="GGMW9 | Verification")
        await ctx.send(embed=embed)
        await log_action(
            ctx.guild,
            "🔄 إلغاء التفعيل",
            f"**المستخدم:** {member.mention} ({member.name})\n"
            f"**المنفذ:** {ctx.author.mention}",
            discord.Color.orange()
        )
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
