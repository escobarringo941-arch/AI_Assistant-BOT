# -*- coding: utf-8 -*-
"""Unchanged ordered source component: birthdays."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║        Phase 8 — أوامر نظام Birthdays                   ║
    # ═══════════════════════════════════════════════════════
    
    @bot.hybrid_command(name="setbirthday")
    async def setbirthday_cmd(ctx, day: int, month: int):
        """سجل عيد ميلادك (اليوم والشهر بوحدهم، بلا عام) — البوت غايعطيك رول البرج أوتوماتيكياً"""
        try:
            # كنستعملو عام كبيسة (2024) باش فبراير 29 يخدم زوين
            datetime(2024, month, day)
        except (ValueError, TypeError):
            await ctx.send("❌ التاريخ ماشي صحيح. اكتب مثلا `/setbirthday day:15 month:8`.", delete_after=8)
            return
    
        zodiac_key, zodiac_label, zodiac_emoji = get_zodiac_sign(day, month)
    
        birthdays_db.setdefault("birthdays", {})[str(ctx.author.id)] = {
            "day": day, "month": month, "last_announced_year": None, "zodiac": zodiac_key
        }
        save_birthdays()
    
        zodiac_note = ""
        if isinstance(ctx.author, discord.Member):
            await sync_zodiac_role(ctx.author, zodiac_key)
            if zodiac_key and ZODIAC_ROLE_IDS.get(zodiac_key):
                zodiac_note = f"\n{zodiac_emoji} عطيناك رول برج **{zodiac_label}**!"
            elif zodiac_key:
                zodiac_note = f"\n{zodiac_emoji} البرج ديالك هو **{zodiac_label}** (الرول ديالو ماعادش معطي فالإعدادات)."
    
        await ctx.send(
            f"🎂 تم تسجيل عيد ميلادك: **{day:02d}/{month:02d}**! غادي نهنيوك نهار عيد ميلادك.{zodiac_note}",
            delete_after=15
        )
    
    
    @bot.hybrid_command(name="removebirthday")
    async def removebirthday_cmd(ctx):
        """حيد عيد الميلاد ديالك من السجل (وكيحيد رول البرج زيادة)"""
        removed = birthdays_db.get("birthdays", {}).pop(str(ctx.author.id), None)
        if removed:
            save_birthdays()
            if isinstance(ctx.author, discord.Member):
                await sync_zodiac_role(ctx.author, None)  # كيحيد أي رول برج عندو بلا مايعطي جديد
            await ctx.send("🗑️ تم حيد عيد الميلاد ديالك من السجل.", delete_after=8)
        else:
            await ctx.send("⚠️ ماعندكش عيد ميلاد مسجل أصلاً.", delete_after=8)
    
    
    @bot.hybrid_command(name="birthday")
    async def birthday_cmd(ctx, member: Optional[discord.Member] = None):
        """بين عيد الميلاد ديالك ولا ديال عضو آخر (والبرج ديالو)"""
        target = member or ctx.author
        record = birthdays_db.get("birthdays", {}).get(str(target.id))
        if not record:
            if target == ctx.author:
                await ctx.send("⚠️ ماعندكش عيد ميلاد مسجل. استعمل `/setbirthday`.", delete_after=8)
            else:
                await ctx.send(f"⚠️ {target.mention} ماعندوش عيد ميلاد مسجل.", delete_after=8)
            return
    
        zodiac_key = record.get("zodiac")
        zodiac_line = ""
        if zodiac_key:
            _, zodiac_label, zodiac_emoji = get_zodiac_sign(record["day"], record["month"])
            zodiac_line = f"\n{zodiac_emoji} البرج: **{zodiac_label}**"
        await ctx.send(f"🎂 عيد ميلاد {target.mention}: **{record['day']:02d}/{record['month']:02d}**{zodiac_line}")
    
    
    @bot.hybrid_command(name="birthdays")
    async def birthdays_cmd(ctx):
        """بين لائحة أقرب 10 أعياد ميلاد جاية فالسيرفر"""
        today = datetime.now()
        today_date = today.date()
        entries = []
        for user_id, record in birthdays_db.get("birthdays", {}).items():
            member = ctx.guild.get_member(int(user_id)) if ctx.guild else None
            if not member:
                continue
            day, month = record["day"], record["month"]
            try:
                this_year_date = datetime(today.year, month, day).date()
            except ValueError:
                continue  # 29 فبراير فعام ماشي كبيسة
            next_date = this_year_date if this_year_date >= today_date else datetime(today.year + 1, month, day).date()
            days_left = (next_date - today_date).days
            entries.append((days_left, member, day, month))
    
        if not entries:
            await ctx.send("📭 ماكاين حتى عيد ميلاد مسجل دابا فالسيرفر.")
            return
    
        entries.sort(key=lambda x: x[0])
        lines = []
        for days_left, member, day, month in entries[:10]:
            when = "🎉 اليوم!" if days_left == 0 else f"بعد {days_left} يوم"
            lines.append(f"**{day:02d}/{month:02d}** — {member.mention} ({when})")
    
        embed = discord.Embed(
            title="🎂 أقرب أعياد الميلاد",
            description="\n".join(lines),
            color=discord.Color.pink()
        )
        embed.set_footer(text=f"{SERVER_NAME} | Birthdays")
        await ctx.send(embed=embed)
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
