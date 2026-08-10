# -*- coding: utf-8 -*-
"""Unchanged ordered source component: xp_admin."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║         XP Control Panel — لوحة تحكم فـ XP (Admin)       ║
    # ═══════════════════════════════════════════════════════
    # لوحة تفاعلية كتخلي الإدارة تبدل شحال ديال XP كياخدو الأعضاء من 3 طرق
    # (الشات، الفويس، اللايفستريم) مباشرة من ديسكورد بلا ماتمس الكود — /xppanel
    # القيم كتتحفظ فـ xp_settings.json وكتبقى حتى بعد ريستارت البوت.
    
    def _xp_panel_embed() -> discord.Embed:
        embed = discord.Embed(
            title="🎛️ لوحة تحكم XP",
            description="بدل شحال ديال XP كياخدو الأعضاء من كل طريقة، بالأزرار تحت. القيم كتتحفظ أوتوماتيك.",
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="💬 الشات",
            value=(
                f"**{xp_settings['chat_min']}-{xp_settings['chat_max']}** XP / رسالة\n"
                f"Cooldown: **{xp_settings['chat_cooldown']}** ثانية"
            ),
            inline=True
        )
        embed.add_field(
            name="🎙️ الفويس",
            value=(
                f"**{xp_settings['voice_per_interval']}** XP / {xp_settings['voice_interval_minutes']} دقايق\n"
                f"أدنى بشر فالروم: **{xp_settings['voice_min_humans']}**"
            ),
            inline=True
        )
        embed.add_field(
            name="📡 اللايفستريم",
            value=f"**{xp_settings['stream_per_interval']}** XP / {xp_settings['voice_interval_minutes']} دقايق",
            inline=True
        )
        cap = int(xp_settings.get("afk_daily_cap", 0) or 0)
        embed.add_field(
            name="💤 الـ AFK",
            value=(
                f"فالروم ديال AFK: **{xp_settings['afk_channel_per_interval']}** XP\n"
                f"مايك مسدود فروم عادية: **{xp_settings['afk_muted_per_interval']}** XP\n"
                f"سقف يومي: **{cap if cap > 0 else 'بلا سقف'}**"
            ),
            inline=True
        )
        mult = xp_settings.get("level_xp_multiplier", 1.0)
        sample_lvl5 = xp_needed_for_level(5)
        sample_lvl20 = xp_needed_for_level(20)
        embed.add_field(
            name="📈 صعوبة المستويات",
            value=(
                f"مضاعف: **×{mult}**\n"
                f"مثال: Level 5 كيحتاج **{sample_lvl5}** XP | Level 20 كيحتاج **{sample_lvl20}** XP"
            ),
            inline=True
        )
        per_hour = 60 / xp_settings["voice_interval_minutes"]
        ratio_voice = (xp_settings["stream_per_interval"] / xp_settings["voice_per_interval"]) if xp_settings["voice_per_interval"] else 0
        embed.add_field(
            name="📐 مقارنة سريعة (تقريبية، فـ الساعة)",
            value=(
                f"اللايفستريم كياخد تقريبا **×{ratio_voice:.1f}** من الفويس العادي.\n"
                f"📡 لايفستريم ≈ **{xp_settings['stream_per_interval'] * per_hour:.0f}** | "
                f"🎙️ فويس ≈ **{xp_settings['voice_per_interval'] * per_hour:.0f}** | "
                f"💤 AFK روم ≈ **{xp_settings['afk_channel_per_interval'] * per_hour:.0f}** | "
                f"🔇 AFK عادي ≈ **{xp_settings['afk_muted_per_interval'] * per_hour:.0f}** XP/ساعة"
            ),
            inline=False
        )
        embed.set_footer(text=f"{SERVER_NAME} | XP Control Panel")
        return embed
    
    
    class ChatXPModal(discord.ui.Modal, title="💬 إعدادات XP الشات"):
        def __init__(self):
            super().__init__()
            self.min_xp = discord.ui.TextInput(
                label="أدنى XP فكل رسالة", default=str(xp_settings["chat_min"]), max_length=5
            )
            self.max_xp = discord.ui.TextInput(
                label="أقصى XP فكل رسالة", default=str(xp_settings["chat_max"]), max_length=5
            )
            self.cooldown = discord.ui.TextInput(
                label="Cooldown بالثواني بين رسالة ورسالة", default=str(xp_settings["chat_cooldown"]), max_length=6
            )
            self.add_item(self.min_xp)
            self.add_item(self.max_xp)
            self.add_item(self.cooldown)
    
        async def on_submit(self, interaction: discord.Interaction):
            try:
                new_min = int(self.min_xp.value)
                new_max = int(self.max_xp.value)
                new_cooldown = int(self.cooldown.value)
            except ValueError:
                await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
                return
            if new_min < 0 or new_max < 0 or new_cooldown < 0:
                await interaction.response.send_message("❌ ماكاينش أرقام سالبة.", ephemeral=True)
                return
            if new_min > new_max:
                await interaction.response.send_message("❌ الأدنى خاصو يكون أصغر ولا يساوي الأقصى.", ephemeral=True)
                return
    
            xp_settings["chat_min"] = new_min
            xp_settings["chat_max"] = new_max
            xp_settings["chat_cooldown"] = new_cooldown
            save_xp_settings()
    
            await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())
    
    
    class VoiceXPModal(discord.ui.Modal, title="🎙️ إعدادات XP الفويس"):
        def __init__(self):
            super().__init__()
            self.per_interval = discord.ui.TextInput(
                label="XP كل فترة (فويس عادي)", default=str(xp_settings["voice_per_interval"]), max_length=5
            )
            self.interval_minutes = discord.ui.TextInput(
                label="الفترة بالدقايق (مشتركة مع اللايفستريم)",
                default=str(xp_settings["voice_interval_minutes"]), max_length=4
            )
            self.min_humans = discord.ui.TextInput(
                label="أدنى عدد بشر فالروم باش ياخدو XP", default=str(xp_settings["voice_min_humans"]), max_length=3
            )
            self.add_item(self.per_interval)
            self.add_item(self.interval_minutes)
            self.add_item(self.min_humans)
    
        async def on_submit(self, interaction: discord.Interaction):
            try:
                new_amount = int(self.per_interval.value)
                new_interval = int(self.interval_minutes.value)
                new_min_humans = int(self.min_humans.value)
            except ValueError:
                await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
                return
            if new_amount < 0 or new_interval <= 0 or new_min_humans < 1:
                await interaction.response.send_message(
                    "❌ الفترة خاصها تكون أكبر من 0، وأدنى البشر خاصو يكون 1 ولا أكثر.", ephemeral=True
                )
                return
    
            interval_changed = new_interval != xp_settings["voice_interval_minutes"]
            xp_settings["voice_per_interval"] = new_amount
            xp_settings["voice_interval_minutes"] = new_interval
            xp_settings["voice_min_humans"] = new_min_humans
            save_xp_settings()
    
            # الفترة (VOICE_XP_INTERVAL_MINUTES) مشتركة بين الفويس واللايفستريم (نفس الـ loop)،
            # فـ إلا تبدلات خاصنا نبدلو الـ loop نفسو ماشي غير الرقم فالـ dict
            if interval_changed and voice_xp_loop.is_running():
                voice_xp_loop.change_interval(minutes=new_interval)
    
            await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())
    
    
    class StreamXPModal(discord.ui.Modal, title="📡 إعدادات XP اللايفستريم"):
        def __init__(self):
            super().__init__()
            self.per_interval = discord.ui.TextInput(
                label="XP كل فترة (ملي كيدير Go Live)",
                default=str(xp_settings["stream_per_interval"]), max_length=5
            )
            self.add_item(self.per_interval)
    
        async def on_submit(self, interaction: discord.Interaction):
            try:
                new_amount = int(self.per_interval.value)
            except ValueError:
                await interaction.response.send_message("❌ خاص القيمة تكون رقم صحيح.", ephemeral=True)
                return
            if new_amount < 0:
                await interaction.response.send_message("❌ ماكاينش رقم سالب.", ephemeral=True)
                return
    
            xp_settings["stream_per_interval"] = new_amount
            save_xp_settings()
    
            await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())
    
    
    class AfkXPModal(discord.ui.Modal, title="💤 إعدادات XP ديال الـ AFK"):
        def __init__(self):
            super().__init__()
            self.afk_channel_xp = discord.ui.TextInput(
                label="XP كل فترة فالروم ديال AFK",
                default=str(xp_settings["afk_channel_per_interval"]), max_length=5
            )
            self.afk_muted_xp = discord.ui.TextInput(
                label="XP كل فترة (مايك مسدود فروم عادية)",
                default=str(xp_settings["afk_muted_per_interval"]), max_length=5
            )
            self.daily_cap = discord.ui.TextInput(
                label="سقف يومي لـ XP ديال AFK (0 = بلا سقف)",
                default=str(xp_settings.get("afk_daily_cap", 0)), max_length=6
            )
            self.add_item(self.afk_channel_xp)
            self.add_item(self.afk_muted_xp)
            self.add_item(self.daily_cap)
    
        async def on_submit(self, interaction: discord.Interaction):
            try:
                ch_xp = int(self.afk_channel_xp.value)
                mut_xp = int(self.afk_muted_xp.value)
                cap = int(self.daily_cap.value)
            except ValueError:
                await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
                return
            if min(ch_xp, mut_xp, cap) < 0:
                await interaction.response.send_message("❌ ماكاينش رقم سالب.", ephemeral=True)
                return
            if ch_xp > xp_settings["voice_per_interval"] or mut_xp > xp_settings["voice_per_interval"]:
                await interaction.response.send_message(
                    f"❌ XP ديال AFK خاصو يكون **أقل** من الفويس العادي "
                    f"({xp_settings['voice_per_interval']} XP) — وإلا الناس غادي يفرميو وهوما ناعسين 😴",
                    ephemeral=True
                )
                return
    
            xp_settings["afk_channel_per_interval"] = ch_xp
            xp_settings["afk_muted_per_interval"] = mut_xp
            xp_settings["afk_daily_cap"] = cap
            save_xp_settings()
    
            await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())
    
    
    class LevelXPModal(discord.ui.Modal, title="📈 صعوبة المستويات (Levels)"):
        def __init__(self):
            super().__init__()
            self.multiplier = discord.ui.TextInput(
                label="مضاعف XP المطلوب للمستويات",
                default=str(xp_settings.get("level_xp_multiplier", 1.0)),
                placeholder="1.0 = عادي | 0.5 = نص (أسهل) | 2.0 = ضعف (أصعب)",
                max_length=6
            )
            self.add_item(self.multiplier)
    
        async def on_submit(self, interaction: discord.Interaction):
            try:
                new_mult = float(self.multiplier.value)
            except ValueError:
                await interaction.response.send_message("❌ خاصها تكون رقم (مثلا 1.0 ولا 0.5).", ephemeral=True)
                return
            if new_mult <= 0:
                await interaction.response.send_message("❌ خاصها تكون أكبر من 0.", ephemeral=True)
                return
    
            xp_settings["level_xp_multiplier"] = round(new_mult, 3)
            save_xp_settings()
    
            await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())
    
    
    class XPPanelView(discord.ui.View):
        """أزرار لوحة تحكم XP — كل واحد كيحل Modal باش تبدل القيم ديال طريقة معينة.
        خاص الـ Owner بوحدو باش يستعملها، حتى ملي تكون الرسالة بانة لكل واحد."""
    
        def __init__(self):
            super().__init__(timeout=300)
    
        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if not interaction.guild or interaction.user.id != interaction.guild.owner_id:
                await interaction.response.send_message("❌ هاد اللوحة خاصة غير بالـ Owner.", ephemeral=True)
                return False
            return True
    
        @discord.ui.button(label="عدل الشات", emoji="💬", style=discord.ButtonStyle.primary)
        async def edit_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(ChatXPModal())
    
        @discord.ui.button(label="عدل الفويس", emoji="🎙️", style=discord.ButtonStyle.primary)
        async def edit_voice(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(VoiceXPModal())
    
        @discord.ui.button(label="عدل اللايفستريم", emoji="📡", style=discord.ButtonStyle.primary)
        async def edit_stream(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(StreamXPModal())
    
        @discord.ui.button(label="عدل الـ AFK", emoji="💤", style=discord.ButtonStyle.primary)
        async def edit_afk(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(AfkXPModal())
    
        @discord.ui.button(label="صعوبة المستويات", emoji="📈", style=discord.ButtonStyle.primary, row=1)
        async def edit_level_difficulty(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(LevelXPModal())
    
        @discord.ui.button(label="رجّع الافتراضي", emoji="↩️", style=discord.ButtonStyle.danger, row=1)
        async def reset_defaults(self, interaction: discord.Interaction, button: discord.ui.Button):
            interval_changed = xp_settings["voice_interval_minutes"] != VOICE_XP_INTERVAL_MINUTES
            xp_settings["chat_min"] = XP_MIN_PER_MESSAGE
            xp_settings["chat_max"] = XP_MAX_PER_MESSAGE
            xp_settings["chat_cooldown"] = XP_COOLDOWN_SECONDS
            xp_settings["voice_per_interval"] = VOICE_XP_PER_INTERVAL
            xp_settings["voice_interval_minutes"] = VOICE_XP_INTERVAL_MINUTES
            xp_settings["voice_min_humans"] = VOICE_XP_MIN_HUMANS_IN_CHANNEL
            xp_settings["stream_per_interval"] = STREAM_XP_PER_INTERVAL
            xp_settings["afk_channel_per_interval"] = AFK_CHANNEL_XP_PER_INTERVAL
            xp_settings["afk_muted_per_interval"] = AFK_MUTED_XP_PER_INTERVAL
            xp_settings["afk_daily_cap"] = AFK_XP_DAILY_CAP
            xp_settings["level_xp_multiplier"] = 1.0
            save_xp_settings()
            if interval_changed and voice_xp_loop.is_running():
                voice_xp_loop.change_interval(minutes=VOICE_XP_INTERVAL_MINUTES)
            await interaction.response.edit_message(embed=_xp_panel_embed(), view=self)
    
    
    @bot.command(name="xppanel", hidden=True)
    @owner_only()
    async def xppanel_cmd(ctx):
        """لوحة تحكم تفاعلية باش تبدل شحال ديال XP كياخدو الأعضاء من الشات، الفويس، اللايفستريم، وصعوبة المستويات — Admin"""
        await ctx.send(embed=_xp_panel_embed(), view=XPPanelView())
    
    
    def recompute_level_from_total_xp(total_xp: int):
        """كتحسب (level, xp_داخل_المستوى) من مجموع XP كلي، حسب صيغة xp_needed_for_level
        الحالية (بحال xp_settings['level_xp_multiplier'] دابا). كتستعمل باش نعاودو نبنيو
        المستوى الصحيح بعد ما نزيدو/ننقصو XP يدوياً."""
        total_xp = max(0, total_xp)
        level = 0
        remaining = total_xp
        while remaining >= xp_needed_for_level(level):
            remaining -= xp_needed_for_level(level)
            level += 1
        return level, remaining
    
    
    async def adjust_user_xp(member: discord.Member, guild: discord.Guild, amount: int) -> dict:
        """كيزيد/كينقص XP لعضو مباشرة (amount يقدر يكون سالب)، وكيعاود يحسب المستوى
        بالكامل من مجموع XP الكلي — يعني المستوى كيطلع ولا كيهبط تلقائياً حسب
        العدد الجديد (بحال طلبتي: نقصان XP يقدر يرجع العضو لمستوى تحتاني).
        كيعطي الرولات الناقصة إلا صعد لمستوى جديد."""
        data = get_user_level_data(guild.id, member.id)
        old_level = data["level"]
        old_total = total_xp_earned(data)
    
        new_total = max(0, old_total + amount)
        new_level, new_xp = recompute_level_from_total_xp(new_total)
    
        data["level"] = new_level
        data["xp"] = new_xp
        save_levels()
    
        roles_added, roles_removed = [], []
        if new_level != old_level:   # تبدل المستوى (صعد ولا هبط) → نعاودو نظبطو الرول
            roles_added, roles_removed = await sync_level_roles(member, guild, new_level)
    
        return {
            "old_level": old_level, "new_level": new_level,
            "old_total": old_total, "new_total": new_total,
            "roles_added": roles_added,
            "roles_removed": roles_removed,
        }
    
    
    @bot.command(name="xpadjust", hidden=True)
    async def xpadjust_cmd(ctx, member: discord.Member, amount: int, *, reason: str = "بلا سبب محدد"):
        """زيد ولا نقص XP لعضو معين مباشرة، والمستوى كيتبدل أوتوماتيكياً حسب المجموع الجديد — Owner بوحدو"""
        if not ctx.guild or ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ هاد الأمر خاص غير بـ Owner.", delete_after=8)
            return
        if amount == 0:
            await ctx.send("❌ عطيني رقم غير صفر (موجب باش تزيد، سالب باش تنقص).", delete_after=8)
            return
        if member.bot:
            await ctx.send("❌ ما تقدرش تبدل XP ديال بوت.", delete_after=8)
            return
    
        result = await adjust_user_xp(member, ctx.guild, amount)
    
        verb = "زدت" if amount > 0 else "نقصت"
        embed = discord.Embed(
            title="🛠️ تعديل XP يدوي",
            description=f"{verb} **{abs(amount)}** XP لـ {member.mention}",
            color=discord.Color.gold() if amount > 0 else discord.Color.orange()
        )
        level_change = "➡️" if result["old_level"] == result["new_level"] else ("⬆️" if result["new_level"] > result["old_level"] else "⬇️")
        embed.add_field(name="المستوى", value=f"{result['old_level']} {level_change} **{result['new_level']}**", inline=True)
        embed.add_field(name="XP الكلية", value=f"{result['old_total']} → **{result['new_total']}**", inline=True)
        if result["roles_added"]:
            embed.add_field(name="🎁 رول جديد", value=", ".join(result["roles_added"]), inline=False)
        if result["roles_removed"]:
            embed.add_field(name="🗑️ رولات تحيدو", value=", ".join(result["roles_removed"]), inline=False)
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.set_footer(text=f"من طرف {ctx.author.display_name}")
        await ctx.send(embed=embed)
        await _owner_private_dm(
            member,
            f"⭐ إدارة GGMW9 بدلات XP ديالك بشكل خاص: {amount:+,} XP • "
            f"Level {result['old_level']} → {result['new_level']}."
        )
    
    
    SOURCE_LABELS_AR = {
        "chat": "💬 شات",
        "voice": "🎤 فويس",
        "afk_channel": "💤 AFK (روم AFK)",
        "afk_muted": "🔇 AFK (مايك مسدود)",
        "stream": "🎥 لايفستريم",
        "unknown": "❓ ماشي معروف",
    }
    
    
    def build_xp_audit_embed(guild: discord.Guild, member: discord.Member) -> Optional[discord.Embed]:
        """نفس /xpaudit القديم ولكن قابل للاستعمال من Owner Panel."""
        summary = get_xp_audit_summary(guild.id, member.id)
        if summary["total_events"] == 0:
            return None
    
        embed = discord.Embed(
            title=f"🔍 XP Audit — {member.display_name}",
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
    
        data = get_user_level_data(guild.id, member.id)
        embed.add_field(
            name="📊 الوضع الحالي",
            value=(
                f"Level **{data['level']}** • "
                f"{data['xp']}/{xp_needed_for_level(data['level'])} XP للمستوى الجاي\n"
                f"مجموع XP إجمالي: **{total_xp_earned(data)}**"
            ),
            inline=False
        )
    
        dist_lines = []
        for src, info in sorted(summary["by_source"].items(), key=lambda x: -x[1]["total"]):
            label = SOURCE_LABELS_AR.get(src, src)
            dist_lines.append(f"{label}: **{info['total']}** XP ({info['count']} events)")
        embed.add_field(
            name=f"📈 التوزيع حسب المصدر ({summary['total_events']} events)",
            value="\n".join(dist_lines) if dist_lines else "—",
            inline=False
        )
    
        recent = summary["recent"][-15:]
        recent_lines = []
        for e in reversed(recent):
            ts = e.get("ts", "")[:16].replace("T", " ")
            label = SOURCE_LABELS_AR.get(e.get("source"), e.get("source"))
            ch = f" <#{e['channel']}>" if e.get("channel") else ""
            recent_lines.append(f"`{ts}` {label} +{e.get('amount')} XP{ch}")
        embed.add_field(
            name="🕒 آخر 15 events",
            value="\n".join(recent_lines) if recent_lines else "—",
            inline=False
        )
    
        chat_events = [e for e in summary["recent"] if e.get("source") == "chat"]
        if len(chat_events) >= 5:
            gaps = []
            for i in range(1, len(chat_events)):
                try:
                    t1 = datetime.fromisoformat(chat_events[i - 1]["ts"])
                    t2 = datetime.fromisoformat(chat_events[i]["ts"])
                    gaps.append((t2 - t1).total_seconds())
                except Exception:
                    pass
            if gaps:
                avg_gap = sum(gaps) / len(gaps)
                tight = sum(
                    1 for g in gaps
                    if xp_settings["chat_cooldown"] <= g <= xp_settings["chat_cooldown"] + 3
                )
                ratio = tight / len(gaps)
                if ratio >= 0.7 and avg_gap < xp_settings["chat_cooldown"] + 5:
                    embed.add_field(
                        name="⚠️ ملاحظة",
                        value=(
                            f"{ratio*100:.0f}% من رسائلو الأخيرة قريبين بزاف من "
                            f"cooldown ({xp_settings['chat_cooldown']}ث). "
                            "يمكن نشاط عادي، ولكن يستاهل تشيك."
                        ),
                        inline=False
                    )
    
        return embed
    
    
    # Hidden prefix fallback فقط — ما بقاش Slash Command.
    @bot.command(name="xpaudit", hidden=True)
    @owner_only()
    async def xpaudit_cmd(ctx, member: discord.Member):
        embed = build_xp_audit_embed(ctx.guild, member)
        if not embed:
            await ctx.send(f"❌ ماكاين حتى XP Audit مسجل لـ {member.mention}.")
            return
        await ctx.send(embed=embed)
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
