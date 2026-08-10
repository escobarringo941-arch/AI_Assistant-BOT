# -*- coding: utf-8 -*-
"""Unchanged ordered source component: owner_control."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║   🔐 GGMW9 OWNER CONTROL CENTER                    ║
    # ═══════════════════════════════════════════════════════
    
    def _owner_control_is_owner(user, guild: discord.Guild) -> bool:
        """Trust Discord's live guild owner, never a stale configured ID."""
        return bool(user and guild and user.id == guild.owner_id)


    def _owner_control_embed(guild: discord.Guild) -> discord.Embed:
        eco_cog = bot.get_cog("Economy")
        treasury = jackpot = events = 0
        if eco_cog:
            try:
                sys = eco_cog._system(guild.id)
                treasury = int(sys.get("treasury", 0) or 0)
                jackpot = int(sys.get("jackpot", 0) or 0)
                events = int(sys.get("events", 0) or 0)
            except Exception:
                pass
    
        embed = discord.Embed(
            title="🔐 GGMW9 — Owner Control Center",
            description=(
                "هاد الـPanel هي المركز الخاص بالـOwner. ما تحتاجش تكتب أوامر الإدارة فالشات.\n\n"
                "📊 **XP & Levels** — Settings / Adjust XP / Set Level / Audit / Sync Roles\n"
                "💵 **Economy** — Give/Remove USD / Member Account / Economy Stats / Bank Refresh\n"
                "⚙️ **Bot Settings** — Anti-Raid / Warns / Auto-Info / Features / XP Settings\n"
                "🔄 **Refresh All Panels** — يجدّد كاع الواجهات الرسمية بلا حذف Messages وبلا Redeploy\n"
                "🏙️ **GGMW9 CITY** — Setup / Repair ديال المدينة المهنية والقنوات ديالها\n"
                "🔊 **Voice Tools** — صاوب Room Mute Panel باختيار Voice Channel\n\n"
                "🔒 كل Interaction كتتأكد من **Server Owner الحقيقي** حتى إلا شاف شي حد الرسالة بالغلط."
            ),
            color=discord.Color.dark_gold(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="🏛️ Treasury", value=f"**{cfg.fmt_money(treasury)}**", inline=True)
        embed.add_field(name="🎰 Jackpot", value=f"**{cfg.fmt_money(jackpot)}**", inline=True)
        embed.add_field(name="🎉 Events", value=f"**{cfg.fmt_money(events)}**", inline=True)
        embed.set_footer(text="GGMW9 Owner Center • Persistent • No public admin commands needed")
        return embed
    
    
    class OwnerOnlyView(discord.ui.View):
        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if not _owner_control_is_owner(interaction.user, interaction.guild):
                if not interaction.response.is_done():
                    await interaction.response.send_message(
                        "❌ هاد الـControl Center خاص غير بالـOwner.",
                        ephemeral=True,
                    )
                return False
            return True
    
    
    def _parse_owner_integer(value):
        """Owner-only integer parser. No game/economy cap is applied."""
        raw = str(value).strip().replace(",", "").replace(" ", "")
        if not raw:
            return None
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None
    
    
    async def _owner_private_dm(member: discord.Member, message: str) -> bool:
        """Recipient-only notification. Never posts in a server log/channel."""
        try:
            await member.send(message)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False
    
    
    class OwnerXPAdjustModal(discord.ui.Modal, title="🛠️ تعديل XP"):
        def __init__(self, member: discord.Member):
            super().__init__()
            self.member = member
            self.amount = discord.ui.TextInput(
                label="XP (+ زيادة / - نقصان)",
                placeholder="مثال: 100000 أو -25000",
                required=True,
                max_length=32,
            )
            self.reason = discord.ui.TextInput(
                label="ملاحظة خاصة (اختيارية)",
                placeholder="كتبان غير للـOwner والمستلم فالـDM",
                required=False,
                max_length=150,
            )
            self.add_item(self.amount)
            self.add_item(self.reason)
    
        async def on_submit(self, interaction: discord.Interaction):
            if not _owner_control_is_owner(interaction.user, interaction.guild):
                await interaction.response.send_message("❌ Owner فقط.", ephemeral=True)
                return
    
            amount = _parse_owner_integer(self.amount.value)
            if amount is None or amount == 0:
                await interaction.response.send_message(
                    "❌ دخل XP صحيح غير صفر. مثال: `100000` أو `-25000`.",
                    ephemeral=True,
                )
                return
    
            result = await adjust_user_xp(self.member, interaction.guild, amount)
            reason = str(self.reason.value).strip()
    
            verb = "تزادو" if amount > 0 else "تحيدو"
            level_change = (
                "➡️" if result["old_level"] == result["new_level"]
                else ("⬆️" if result["new_level"] > result["old_level"] else "⬇️")
            )
    
            dm = (
                f"⭐ إدارة GGMW9 بدلات XP ديالك بشكل خاص.\n"
                f"**{verb}: {abs(amount):,} XP**\n"
                f"المستوى: **{result['old_level']} → {result['new_level']}**\n"
                f"مجموع XP: **{result['old_total']:,} → {result['new_total']:,}**"
            )
            if reason:
                dm += f"\n📝 ملاحظة: {reason}"
            dm_sent = await _owner_private_dm(self.member, dm)
    
            embed = discord.Embed(
                title="✅ تعديل XP تم بشكل خاص",
                description=(
                    f"**العضو:** {self.member.mention}\n"
                    f"**التغيير:** {amount:+,} XP\n"
                    "🔒 ما تبعث حتى Log من البوت لهاد العملية."
                ),
                color=discord.Color.gold() if amount > 0 else discord.Color.orange(),
            )
            embed.add_field(
                name="المستوى",
                value=f"{result['old_level']} {level_change} **{result['new_level']}**",
                inline=True,
            )
            embed.add_field(
                name="مجموع XP",
                value=f"{result['old_total']:,} → **{result['new_total']:,}**",
                inline=True,
            )
            if result["roles_added"]:
                embed.add_field(name="🎖️ رول تزادت", value=", ".join(result["roles_added"]), inline=False)
            if result["roles_removed"]:
                embed.add_field(name="🗑️ رول تحيدات", value=", ".join(result["roles_removed"]), inline=False)
            if not dm_sent:
                embed.add_field(name="⚠️ DM", value="المستلم ساد الرسائل الخاصة.", inline=False)
    
            await refresh_xp_leaderboard_now()
            await interaction.response.edit_message(embed=embed, content=None, view=OwnerXPView())
    
    
    class OwnerSetLevelModal(discord.ui.Modal, title="🎚️ Set Level"):
        def __init__(self, member: discord.Member):
            super().__init__()
            self.member = member
            self.level_input = discord.ui.TextInput(
                label="Level الجديد (أي رقم غير سالب)",
                placeholder="مثال: 100 أو 250 أو 1000",
                required=True,
                max_length=32,
            )
            self.add_item(self.level_input)
    
        async def on_submit(self, interaction: discord.Interaction):
            if not _owner_control_is_owner(interaction.user, interaction.guild):
                await interaction.response.send_message("❌ Owner فقط.", ephemeral=True)
                return
    
            level = _parse_owner_integer(self.level_input.value)
            if level is None or level < 0:
                await interaction.response.send_message("❌ دخل Level صحيح غير سالب.", ephemeral=True)
                return
    
            data = get_user_level_data(interaction.guild.id, self.member.id)
            old_level = int(data.get("level", 0) or 0)
            data["level"] = int(level)
            data["xp"] = 0
            save_levels()
    
            roles_added, roles_removed = await sync_level_roles(
                self.member, interaction.guild, int(level)
            )
            await refresh_xp_leaderboard_now()
    
            dm_sent = await _owner_private_dm(
                self.member,
                (
                    "🎚️ إدارة GGMW9 بدلات المستوى ديالك بشكل خاص.\n"
                    f"**Level {old_level} → {level}**\n"
                    "إلا المستوى فات أعلى Role مبرمجة، كيبقى عندك أعلى Level Role متوفرة."
                ),
            )
    
            embed = discord.Embed(
                title="✅ Set Level تم بشكل خاص",
                description=(
                    f"{self.member.mention}: **Level {old_level} → {level}**\n"
                    "🔒 ما تبعث حتى Log من البوت لهاد العملية."
                ),
                color=discord.Color.blurple(),
            )
            if roles_added:
                embed.add_field(name="🎖️ رول تزادت", value=", ".join(roles_added), inline=False)
            if roles_removed:
                embed.add_field(name="🗑️ رول تحيدات", value=", ".join(roles_removed), inline=False)
            if not dm_sent:
                embed.add_field(name="⚠️ DM", value="المستلم ساد الرسائل الخاصة.", inline=False)
    
            await interaction.response.edit_message(embed=embed, content=None, view=OwnerXPView())
    
    
    class OwnerCoinsAdjustModal(discord.ui.Modal, title="💰 تعديل الرصيد"):
        def __init__(self, member: discord.Member):
            super().__init__()
            self.member = member
            self.amount = discord.ui.TextInput(
                label="USD (+ زيادة / - نقصان)",
                placeholder="مثال: 100 = $100.00 | -50.25",
                required=True,
                max_length=32,
            )
            self.add_item(self.amount)
    
        async def on_submit(self, interaction: discord.Interaction):
            if not _owner_control_is_owner(interaction.user, interaction.guild):
                await interaction.response.send_message("❌ Owner فقط.", ephemeral=True)
                return
    
            amount = cfg.parse_money_input(self.amount.value, allow_negative=True)
            if amount is None or amount == 0:
                await interaction.response.send_message(
                    "❌ دخل مبلغ USD صحيح. `100` = **$100.00** و `100.50` = **$100.50**.",
                    ephemeral=True,
                )
                return
    
            eco_cog = bot.get_cog("Economy")
            if not eco_cog:
                await interaction.response.send_message("❌ Economy Cog ماشي محمّل.", ephemeral=True)
                return
    
            result = await eco_cog.owner_adjust_balance(
                interaction.guild,
                self.member,
                amount,
                actor=interaction.user,
            )
    
            embed = discord.Embed(
                title="✅ تعديل الرصيد تم بشكل خاص",
                description=(
                    f"**العضو:** {self.member.mention}\n"
                    f"**الرقم اللي طلبتي:** {cfg.fmt_money(amount, signed=True)}\n"
                    f"**التغيير الفعلي:** {cfg.fmt_money(result['applied'], signed=True)}\n"
                    f"**قبل:** {cfg.fmt_money(result['before'])}\n"
                    f"**دابا:** **{cfg.fmt_money(result['after'])}**\n\n"
                    "🔒 بلا Economy Log وبلا Transaction Log ديال Owner."
                ),
                color=discord.Color.green() if result["applied"] >= 0 else discord.Color.orange(),
            )
            if not result["dm_sent"]:
                embed.add_field(name="⚠️ DM", value="المستلم ساد الرسائل الخاصة.", inline=False)
    
            await interaction.response.edit_message(embed=embed, content=None, view=OwnerEconomyView())
    
    
    class OwnerMemberSelect(discord.ui.UserSelect):
        def __init__(self, action: str):
            self.action = action
            labels = {
                "xp_adjust": "اختار العضو باش تبدل XP",
                "set_level": "اختار العضو باش تدير Set Level",
                "xp_audit": "اختار العضو باش تشوف XP Audit",
                "coins": "اختار العضو باش تزيد/تحيد USD",
                "economy_account": "اختار العضو باش تشوف حسابو",
            }
            super().__init__(
                placeholder=labels.get(action, "اختار عضو"),
                min_values=1,
                max_values=1,
                row=0,
            )
    
        async def callback(self, interaction: discord.Interaction):
            if not _owner_control_is_owner(interaction.user, interaction.guild):
                await interaction.response.send_message("❌ Owner فقط.", ephemeral=True)
                return
    
            selected = self.values[0]
            member = interaction.guild.get_member(selected.id)
            if not member:
                try:
                    member = await interaction.guild.fetch_member(selected.id)
                except Exception:
                    member = None
            if not member:
                await interaction.response.send_message("❌ ما قدرتش نجيب هاد العضو.", ephemeral=True)
                return
            if member.bot:
                await interaction.response.send_message("❌ اختار عضو بشري، ماشي Bot.", ephemeral=True)
                return
    
            if self.action == "xp_adjust":
                await interaction.response.send_modal(OwnerXPAdjustModal(member))
                return
            if self.action == "set_level":
                await interaction.response.send_modal(OwnerSetLevelModal(member))
                return
            if self.action == "xp_audit":
                embed = build_xp_audit_embed(interaction.guild, member)
                if not embed:
                    await interaction.response.edit_message(
                        content=f"ℹ️ ماكاين حتى XP Audit مسجل لـ {member.mention}.",
                        embed=None,
                        view=OwnerXPView(),
                    )
                else:
                    await interaction.response.edit_message(
                        content=None, embed=embed, view=OwnerXPView()
                    )
                return
            if self.action == "coins":
                await interaction.response.send_modal(OwnerCoinsAdjustModal(member))
                return
            if self.action == "economy_account":
                eco_cog = bot.get_cog("Economy")
                if not eco_cog:
                    await interaction.response.edit_message(
                        content="❌ Economy Cog ماشي محمّل.",
                        embed=None,
                        view=OwnerEconomyView(),
                    )
                    return
                embeds = [
                    eco_cog.build_user_account_embed(interaction.guild, member),
                    eco_cog.build_user_transactions_embed(interaction.guild, member),
                ]
                await interaction.response.edit_message(
                    content=None,
                    embeds=embeds,
                    view=OwnerEconomyView(),
                )
    
    
    class OwnerMemberSelectView(OwnerOnlyView):
        def __init__(self, action: str):
            super().__init__(timeout=180)
            self.add_item(OwnerMemberSelect(action))
    
    
    class OwnerXPView(OwnerOnlyView):
        def __init__(self):
            super().__init__(timeout=300)
    
        @discord.ui.button(label="XP Settings", emoji="⚙️", style=discord.ButtonStyle.primary)
        async def xp_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())
    
        @discord.ui.button(label="Adjust XP", emoji="🛠️", style=discord.ButtonStyle.success)
        async def adjust_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(
                content="👤 اختار العضو:",
                embed=None,
                view=OwnerMemberSelectView("xp_adjust"),
            )
    
        @discord.ui.button(label="Set Level", emoji="🎚️", style=discord.ButtonStyle.primary)
        async def set_level(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(
                content="👤 اختار العضو:",
                embed=None,
                view=OwnerMemberSelectView("set_level"),
            )
    
        @discord.ui.button(label="XP Audit", emoji="🔍", style=discord.ButtonStyle.secondary)
        async def xp_audit(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(
                content="👤 اختار العضو:",
                embed=None,
                view=OwnerMemberSelectView("xp_audit"),
            )
    
        @discord.ui.button(label="Sync Roles", emoji="🔄", style=discord.ButtonStyle.secondary)
        async def sync_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=True, thinking=True)
            await sync_level_role_permissions(interaction.guild)
            await sync_all_level_member_roles(interaction.guild)
            await interaction.followup.send("✅ Level Roles كاملين تراجعو وتصالحو.", ephemeral=True)
    
        @discord.ui.button(label="Refresh XP Center", emoji="📊", style=discord.ButtonStyle.secondary, row=1)
        async def refresh_xp_center(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=True, thinking=True)
            await setup_levels_info_message(interaction.guild)
            await refresh_xp_leaderboard_now()
            await interaction.followup.send("✅ Levels Info + XP Leaderboard تحدثو.", ephemeral=True)
    
    
    class OwnerEconomyView(OwnerOnlyView):
        def __init__(self):
            super().__init__(timeout=300)
    
        @discord.ui.button(label="Give / Remove USD", emoji="💵", style=discord.ButtonStyle.success)
        async def coins(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(
                content="👤 اختار العضو:",
                embed=None,
                view=OwnerMemberSelectView("coins"),
            )
    
        @discord.ui.button(label="Member Account", emoji="👤", style=discord.ButtonStyle.primary)
        async def member_account(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(
                content="👤 اختار العضو:",
                embed=None,
                view=OwnerMemberSelectView("economy_account"),
            )
    
        @discord.ui.button(label="Economy Stats", emoji="📊", style=discord.ButtonStyle.secondary)
        async def stats(self, interaction: discord.Interaction, button: discord.ui.Button):
            eco_cog = bot.get_cog("Economy")
            if not eco_cog:
                await interaction.response.send_message("❌ Economy Cog ماشي محمّل.", ephemeral=True)
                return
            await interaction.response.edit_message(
                content=None,
                embed=eco_cog.build_global_economy_embed(interaction.guild),
                view=OwnerEconomyView(),
            )
    
        @discord.ui.button(label="Refresh Bank", emoji="🏦", style=discord.ButtonStyle.secondary)
        async def refresh_bank(self, interaction: discord.Interaction, button: discord.ui.Button):
            eco_cog = bot.get_cog("Economy")
            if not eco_cog:
                await interaction.response.send_message("❌ Economy Cog ماشي محمّل.", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            await eco_cog.ensure_bank_panel(interaction.guild)
            await eco_cog.refresh_economy_stats(interaction.guild)
            await interaction.followup.send("✅ Bank Panel + Economy Stats تحدثو.", ephemeral=True)
    
        @discord.ui.button(label="Richest", emoji="🏆", style=discord.ButtonStyle.secondary)
        async def richest(self, interaction: discord.Interaction, button: discord.ui.Button):
            eco_cog = bot.get_cog("Economy")
            if not eco_cog:
                await interaction.response.send_message("❌ Economy Cog ماشي محمّل.", ephemeral=True)
                return
            await interaction.response.edit_message(
                content=None,
                embed=eco_cog.build_richest_embed(interaction.guild),
                view=OwnerEconomyView(),
            )
    
    
    class OwnerVoiceChannelSelect(discord.ui.ChannelSelect):
        def __init__(self):
            super().__init__(
                placeholder="🔊 اختار Voice Channel",
                channel_types=[discord.ChannelType.voice],
                min_values=1,
                max_values=1,
            )
    
        async def callback(self, interaction: discord.Interaction):
            if not _owner_control_is_owner(interaction.user, interaction.guild):
                await interaction.response.send_message("❌ Owner فقط.", ephemeral=True)
                return
    
            selected = self.values[0]
            channel = interaction.guild.get_channel(selected.id)
            if not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message("❌ اختار Voice Channel صحيحة.", ephemeral=True)
                return
    
            muted = channel.id in room_mute_db.get("muted_channels", [])
            embed = build_room_mute_embed(channel, muted)
            msg = await interaction.channel.send(
                embed=embed,
                view=RoomMuteToggleView(muted, channel),
            )
            room_mute_db.setdefault("panels", {})[str(msg.id)] = channel.id
            save_room_mute()
    
            # Owner stealth: no server log entry.
            await interaction.response.edit_message(
                content=f"✅ Room Mute Panel تصاوبات لـ {channel.mention}.",
                view=None,
            )
    
    
    class OwnerVoiceSelectView(OwnerOnlyView):
        def __init__(self):
            super().__init__(timeout=120)
            self.add_item(OwnerVoiceChannelSelect())
    
    
    
    class OwnerChannelMoveSelect(discord.ui.ChannelSelect):
        """اختيار Channel باش نجربو Discord Channel Position API مباشرة."""
    
        def __init__(self):
            super().__init__(
                placeholder="🧪 اختار Channel باش نجربو تحريكها",
                channel_types=[
                    discord.ChannelType.text,
                    discord.ChannelType.news,
                    discord.ChannelType.voice,
                    discord.ChannelType.stage_voice,
                    discord.ChannelType.forum,
                ],
                min_values=1,
                max_values=1,
            )
    
        async def callback(self, interaction: discord.Interaction):
            if not _owner_control_is_owner(interaction.user, interaction.guild):
                await interaction.response.send_message("❌ Owner فقط.", ephemeral=True)
                return
    
            selected = self.values[0]
            channel = interaction.guild.get_channel(selected.id)
            if not channel:
                try:
                    fetched = await interaction.guild.fetch_channels()
                    channel = next((c for c in fetched if c.id == selected.id), None)
                except (discord.Forbidden, discord.HTTPException):
                    channel = None
    
            if not channel:
                await interaction.response.edit_message(
                    content="❌ ما قدرتش نجيب هاد Channel من Discord API.",
                    embed=None,
                    view=None,
                )
                return
    
            category_name = channel.category.name if getattr(channel, "category", None) else "بلا Category"
            bot_member = interaction.guild.me
            manage_channels = False
            if bot_member:
                try:
                    manage_channels = channel.permissions_for(bot_member).manage_channels
                except Exception:
                    pass
    
            embed = discord.Embed(
                title="🧪 Channel Move API Test",
                description=(
                    f"**Channel:** {channel.mention}\n"
                    f"**ID:** `{channel.id}`\n"
                    f"**Category:** `{category_name}`\n"
                    f"**Position الحالية:** `{getattr(channel, 'position', '?')}`\n"
                    f"**Bot Manage Channels هنا:** {'✅ نعم' if manage_channels else '❌ لا'}\n\n"
                    "جرّب تحركها **Position وحدة فقط**. "
                    "إذا API نجحات والموقع مازال ما كيجرّش، فالمشكل من Discord UI/Drag & Drop."
                ),
                color=discord.Color.blurple(),
            )
            await interaction.response.edit_message(
                content=None,
                embed=embed,
                view=OwnerChannelMoveActionView(channel.id),
            )
    
    
    class OwnerChannelMoveSelectView(OwnerOnlyView):
        def __init__(self):
            super().__init__(timeout=180)
            self.add_item(OwnerChannelMoveSelect())
    
    
    class OwnerChannelMoveActionView(OwnerOnlyView):
        def __init__(self, channel_id: int):
            super().__init__(timeout=180)
            self.channel_id = int(channel_id)
    
        @staticmethod
        def _bucket(channel):
            # Discord كيفصل Voice/Stage على Text-like فالتريب المرئي.
            if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                return "voice"
            return "text"
    
        def _ordered_siblings(self, guild: discord.Guild, channel):
            """القنوات المجاورة الحقيقية فنفس Category ونفس sort bucket."""
            cat_id = getattr(channel, "category_id", None)
            bucket = self._bucket(channel)
    
            siblings = [
                c for c in guild.channels
                if not isinstance(c, discord.CategoryChannel)
                and getattr(c, "category_id", None) == cat_id
                and self._bucket(c) == bucket
            ]
            # Discord: same position -> sorted by ID.
            siblings.sort(key=lambda c: (int(getattr(c, "position", 0) or 0), int(c.id)))
            return siblings
    
        async def _run_test(self, interaction: discord.Interaction, delta: int):
            if not _owner_control_is_owner(interaction.user, interaction.guild):
                await interaction.response.send_message("❌ Owner فقط.", ephemeral=True)
                return
    
            channel = interaction.guild.get_channel(self.channel_id)
            if not channel:
                await interaction.response.edit_message(
                    content="❌ Channel ما بقاتش موجودة.",
                    embed=None,
                    view=None,
                )
                return
    
            siblings = self._ordered_siblings(interaction.guild, channel)
            try:
                old_index = next(i for i, c in enumerate(siblings) if c.id == channel.id)
            except StopIteration:
                await interaction.response.edit_message(
                    content="❌ ما قدرتش نحدد بلاصة Channel وسط Category.",
                    embed=None,
                    view=None,
                )
                return
    
            target_index = old_index - 1 if delta < 0 else old_index + 1
            direction = "⬆️ لفوق" if delta < 0 else "⬇️ لتحت"
    
            if target_index < 0 or target_index >= len(siblings):
                await interaction.response.edit_message(
                    content=f"ℹ️ {channel.mention} ما عندهاش Channel أخرى {direction} فنفس المجموعة.",
                    embed=None,
                    view=OwnerChannelMoveActionView(channel.id),
                )
                return
    
            target = siblings[target_index]
    
            await interaction.response.defer(ephemeral=True, thinking=True)
    
            try:
                # Relative move حقيقي، ماشي position integer خام.
                if delta < 0:
                    await channel.move(
                        before=target,
                        reason=f"Owner Channel Move API Test V2 by {interaction.user} ({interaction.user.id})",
                    )
                else:
                    await channel.move(
                        after=target,
                        reason=f"Owner Channel Move API Test V2 by {interaction.user} ({interaction.user.id})",
                    )
    
                # Fetch حقيقي من Discord API من بعد الحركة.
                fresh_channels = await interaction.guild.fetch_channels()
                fresh_channel = next((c for c in fresh_channels if c.id == channel.id), None)
    
                if fresh_channel:
                    fresh_siblings = [
                        c for c in fresh_channels
                        if not isinstance(c, discord.CategoryChannel)
                        and getattr(c, "category_id", None) == getattr(fresh_channel, "category_id", None)
                        and self._bucket(c) == self._bucket(fresh_channel)
                    ]
                    fresh_siblings.sort(
                        key=lambda c: (int(getattr(c, "position", 0) or 0), int(c.id))
                    )
                    new_index = next(
                        (i for i, c in enumerate(fresh_siblings) if c.id == channel.id),
                        old_index,
                    )
                    new_position = int(getattr(fresh_channel, "position", 0) or 0)
                else:
                    fresh_siblings = siblings
                    new_index = old_index
                    new_position = int(getattr(channel, "position", 0) or 0)
    
                actually_moved = new_index != old_index
    
                if actually_moved:
                    title = "✅ CHANNEL MOVE API V2 — MOVED"
                    color = discord.Color.green()
                    conclusion = (
                        "✅ الترتيب تبدل فعلياً فالـDiscord backend. "
                        "إلا PC Web ما كيبينوش ولا Drag كيتبلوكا، فالمشكل فالClient/UI."
                    )
                else:
                    title = "⚠️ API ACCEPTED — ORDER DID NOT CHANGE"
                    color = discord.Color.orange()
                    conclusion = (
                        "⚠️ Discord قبل الطلب ولكن الترتيب الفعلي ما تبدلش حتى بعد Fetch جديد. "
                        "هاد النتيجة كتدل على state/order issue من Discord، ماشي غير Drag UI."
                    )
    
                embed = discord.Embed(
                    title=title,
                    description=(
                        f"**Channel:** <#{channel.id}>\n"
                        f"**Target neighbour:** <#{target.id}>\n"
                        f"**الحركة:** {direction}\n\n"
                        f"**Index قبل:** `{old_index}`\n"
                        f"**Index من API دابا:** `{new_index}`\n"
                        f"**Raw position دابا:** `{new_position}`\n\n"
                        f"{conclusion}"
                    ),
                    color=color,
                )
    
                # Owner stealth: no server log entry.
    
                await interaction.edit_original_response(
                    content=None,
                    embed=embed,
                    view=OwnerChannelMoveActionView(channel.id),
                )
    
            except discord.Forbidden as e:
                status = getattr(e, "status", 403)
                code = getattr(e, "code", "N/A")
                detail = str(e)[:1200]
                embed = discord.Embed(
                    title="❌ CHANNEL MOVE API V2 — FORBIDDEN",
                    description=(
                        f"**HTTP Status:** `{status}`\n"
                        f"**Discord Code:** `{code}`\n"
                        f"```{detail}```"
                    ),
                    color=discord.Color.red(),
                )
                await interaction.edit_original_response(
                    content=None,
                    embed=embed,
                    view=OwnerChannelMoveActionView(channel.id),
                )
    
            except discord.HTTPException as e:
                status = getattr(e, "status", "N/A")
                code = getattr(e, "code", "N/A")
                detail = getattr(e, "text", None) or str(e)
                embed = discord.Embed(
                    title="⚠️ CHANNEL MOVE API V2 — HTTP ERROR",
                    description=(
                        f"**HTTP Status:** `{status}`\n"
                        f"**Discord Code:** `{code}`\n"
                        f"```{str(detail)[:1200]}```"
                    ),
                    color=discord.Color.orange(),
                )
                await interaction.edit_original_response(
                    content=None,
                    embed=embed,
                    view=OwnerChannelMoveActionView(channel.id),
                )
    
            except Exception as e:
                embed = discord.Embed(
                    title="❌ CHANNEL MOVE TEST V2 — INTERNAL ERROR",
                    description=f"```{type(e).__name__}: {str(e)[:1000]}```",
                    color=discord.Color.red(),
                )
                await interaction.edit_original_response(
                    content=None,
                    embed=embed,
                    view=OwnerChannelMoveActionView(channel.id),
                )
    
        @discord.ui.button(
            label="Move Up 1",
            emoji="⬆️",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        async def move_up(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._run_test(interaction, -1)
    
        @discord.ui.button(
            label="Move Down 1",
            emoji="⬇️",
            style=discord.ButtonStyle.primary,
            row=0,
        )
        async def move_down(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._run_test(interaction, 1)
    
        @discord.ui.button(
            label="اختار Channel أخرى",
            emoji="🔁",
            style=discord.ButtonStyle.secondary,
            row=1,
        )
        async def choose_again(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(
                content="🧪 اختار Channel أخرى للاختبار:",
                embed=None,
                view=OwnerChannelMoveSelectView(),
            )
    
    
    async def refresh_all_server_panels(guild: discord.Guild) -> dict:
        """Owner maintenance: refresh every fixed/public GGMW9 panel in-place.
    
        Existing Discord messages are edited whenever possible; a new message is only
        created when the official panel message is actually missing.
        """
        report = {"ok": [], "skip": [], "errors": []}
    
        async def run(label, func):
            try:
                result = await func()
                if result is False:
                    report["skip"].append(label)
                else:
                    report["ok"].append(label)
            except Exception as exc:
                report["errors"].append(f"{label}: {type(exc).__name__}: {exc}")
    
        # Core public/server panels in ai_bot.py
        if RULES_CHANNEL_ID:
            await run("📜 Rules", lambda: setup_rules_message(guild))
        if VERIFY_CHANNEL_ID:
            await run("✅ Verify", lambda: setup_verify_message(guild))
        if BLACKLIST_CHANNEL_ID:
            await run("🚫 Blacklist", lambda: setup_blacklist_message(guild))
        if SUPPORT_CENTER_CHANNEL_ID:
            await run("🆘 Support Center", lambda: setup_support_center(guild))
        if APPLICATIONS_PANEL_CHANNEL_ID:
            await run("📋 Applications", lambda: setup_applications_panel(guild))
        if SUGGESTIONS_CHANNEL_ID:
            await run("💡 Suggestions", lambda: setup_suggestions_info(guild))
        if LEVELS_INFO_CHANNEL_ID:
            await run("⭐ Levels Info", lambda: setup_levels_info_message(guild))
        if LEADERBOARD_CHANNEL_ID:
            await run("🏆 XP Leaderboard", refresh_xp_leaderboard_now)
    
        # ARCADE + Shop + game leaderboards
        games_cog = bot.get_cog("GamesPanel")
        if games_cog:
            await run("🎮 ARCADE / Shop / Game Leaderboards", games_cog.on_ready)
        else:
            report["skip"].append("🎮 GamesPanel Cog")
    
        # Casino
        gambling_cog = bot.get_cog("GamblingPanel")
        if gambling_cog:
            await run("🎰 Casino", gambling_cog.on_ready)
        else:
            report["skip"].append("🎰 GamblingPanel Cog")
    
        # Bank + live economy stats
        eco_cog = bot.get_cog("Economy")
        if eco_cog:
            await run("🏦 Bank", lambda: eco_cog.ensure_bank_panel(guild))
            await run("📊 Economy Stats", lambda: eco_cog.refresh_economy_stats(guild))
        else:
            report["skip"].append("🏦 Economy Cog")
    
        # Trivia dedicated panel
        trivia_cog = bot.get_cog("Trivia")
        if trivia_cog:
            await run("🧠 Trivia", lambda: trivia_cog.setup_trivia_panel(guild, force=True))
        else:
            report["skip"].append("🧠 Trivia Cog")
    
        # GGMW9 CITY — career/services/projects/job-market panels
        city_cog = bot.get_cog("CareerCity")
        if city_cog:
            setup = city_cog.store.guild(guild.id).get("setup", {})
            if setup.get("complete"):
                await run("🏙️ GGMW9 CITY", lambda: city_cog.refresh_city_panels(guild))
            else:
                report["skip"].append("🏙️ GGMW9 CITY (مازال ما تدارش Setup)")
            ug = city_cog.underground(guild.id)
            if (ug.get("setup") or {}).get("complete"):
                await run("🌑 Underground", lambda: city_cog.refresh_underground_panels(guild))
            else:
                report["skip"].append("🌑 Underground (مازال ما تدارش Setup)")
        else:
            report["skip"].append("🏙️ CareerCity Cog")
    
        # Active temporary voice room control panels
        refreshed_temp = 0
        for cid in list(temp_voice_channels.keys()):
            try:
                ch = guild.get_channel(int(cid))
            except (TypeError, ValueError):
                ch = None
            if isinstance(ch, discord.VoiceChannel):
                try:
                    msg = await refresh_temp_voice_control_panel(ch, create_if_missing=False)
                    if msg:
                        refreshed_temp += 1
                except Exception as exc:
                    report["errors"].append(f"🔊 Temp Voice {cid}: {type(exc).__name__}: {exc}")
        if refreshed_temp:
            report["ok"].append(f"🔊 Temp Voice ×{refreshed_temp}")
    
        # Refresh the Owner Control Center last so even this maintenance button gets a fresh View.
        if OWNER_CONTROL_CHANNEL_ID:
            await run("🔐 Owner Control", lambda: setup_owner_control_panel(guild))
    
        return report
    
    
    def _refresh_panels_report_embed(report: dict) -> discord.Embed:
        errors = report.get("errors", [])
        color = discord.Color.orange() if errors else discord.Color.green()
        embed = discord.Embed(
            title="🔄 GGMW9 — All Panels Refreshed" if not errors else "⚠️ GGMW9 — Panel Refresh Completed",
            description=(
                "البوت حاول يجدّد **نفس رسائل البانلز الموجودة**: Embed + Buttons/Selects/View. "
                "كيخلق Message جديدة غير إلا Panel الرسمية ما كانتش موجودة أصلاً."
            ),
            color=color,
            timestamp=datetime.now(),
        )
        ok = report.get("ok", [])
        skipped = report.get("skip", [])
        if ok:
            embed.add_field(name=f"✅ Refreshed ({len(ok)})", value="\n".join(ok)[:1024], inline=False)
        if skipped:
            embed.add_field(name=f"⏭️ Skipped ({len(skipped)})", value="\n".join(skipped)[:1024], inline=False)
        if errors:
            embed.add_field(name=f"❌ Errors ({len(errors)})", value="\n".join(f"• {e}" for e in errors)[:1024], inline=False)
        embed.set_footer(text="Owner Maintenance • ما محتاجش تمسح Panel ولا تعاود Deploy باش غير تجدّد الواجهات")
        return embed
    
    
    class OwnerControlCenterView(OwnerOnlyView):
        def __init__(self):
            super().__init__(timeout=None)
    
        @discord.ui.button(
            label="XP & Levels", emoji="📊", style=discord.ButtonStyle.success,
            custom_id="ggmw9:owner:xp", row=0
        )
        async def xp(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="📊 Owner — XP & Levels",
                description="اختار العملية اللي بغيتي. كل النتائج خاصة بيك.",
                color=discord.Color.gold(),
            )
            await interaction.response.send_message(embed=embed, view=OwnerXPView(), ephemeral=True)
    
        @discord.ui.button(
            label="Economy", emoji="💰", style=discord.ButtonStyle.success,
            custom_id="ggmw9:owner:economy", row=0
        )
        async def economy(self, interaction: discord.Interaction, button: discord.ui.Button):
            embed = discord.Embed(
                title="💰 Owner — Economy",
                description="USD / Accounts / Bank / Economy Stats.",
                color=discord.Color.gold(),
            )
            await interaction.response.send_message(embed=embed, view=OwnerEconomyView(), ephemeral=True)
    
        @discord.ui.button(
            label="Bot Settings", emoji="⚙️", style=discord.ButtonStyle.primary,
            custom_id="ggmw9:owner:bot_settings", row=0
        )
        async def bot_settings_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message(
                embed=_main_panel_embed(),
                view=MainPanelView(),
                ephemeral=True,
            )
    
        @discord.ui.button(
            label="Refresh All Panels", emoji="🔄", style=discord.ButtonStyle.secondary,
            custom_id="ggmw9:owner:refresh_panels", row=0
        )
        async def refresh_panels(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer(ephemeral=True, thinking=True)
            report = await refresh_all_server_panels(interaction.guild)
            await interaction.followup.send(embed=_refresh_panels_report_embed(report), ephemeral=True)
    
        @discord.ui.button(
            label="Voice Tools", emoji="🔊", style=discord.ButtonStyle.secondary,
            custom_id="ggmw9:owner:voice", row=0
        )
        async def voice_tools(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message(
                "🔊 اختار Voice Channel باش نصاوب ليها Room Mute Panel فهاد الشانيل:",
                view=OwnerVoiceSelectView(),
                ephemeral=True,
            )
    
        @discord.ui.button(
            label="Setup GGMW9 CITY", emoji="🏙️", style=discord.ButtonStyle.success,
            custom_id="ggmw9:owner:city_setup", row=1
        )
        async def city_setup(self, interaction: discord.Interaction, button: discord.ui.Button):
            city = bot.get_cog("CareerCity")
            if not city:
                await interaction.response.send_message(
                    "❌ CareerCity Cog ماشي محمّلة. شوف Railway logs.",
                    ephemeral=True,
                )
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            result = await city.setup_city(interaction.guild, force=True)
            if not result.get("ok"):
                await interaction.followup.send(
                    f"❌ Setup CITY فشلت: {result.get('error','Unknown error')}",
                    ephemeral=True,
                )
                return
            seed = result.get("seed") or {}
            embed = discord.Embed(
                title="🏙️ GGMW9 CITY — Setup Complete",
                description=(
                    f"**Category:** {result.get('category')}\n"
                    f"✅ القنوات تخلقات/تصلحات وولات Read-only Panel channels.\n"
                    f"🕐 التوقيت: **Africa/Casablanca**\n"
                    f"📩 التنبيهات: **DM → city-alerts fallback**\n"
                    f"🏦 Direct Deposit: **GGMW9 Bank Savings**"
                ),
                color=discord.Color.green(),
                timestamp=datetime.now(),
            )
            created = result.get("created") or []
            reused = result.get("reused") or []
            if created:
                embed.add_field(name="🆕 تخلقو", value="\n".join(created)[:1024], inline=False)
            if reused:
                embed.add_field(name="♻️ تلقاو وتصلحو", value="\n".join(reused)[:1024], inline=False)
            if int(seed.get("seeded",0) or 0):
                embed.add_field(
                    name="💼 Payroll Seed",
                    value=f"الخزينة موّلت البداية بـ **{cfg.fmt_money(int(seed['seeded']))}** موزعة على شركات المدينة.",
                    inline=False,
                )
            embed.set_footer(text="Setup آمن ضد duplicates • IDs كيتخزنو فـggmw9_city.json")
            await interaction.followup.send(embed=embed, ephemeral=True)
    
        @discord.ui.button(
            label="Underground", emoji="🌑", style=discord.ButtonStyle.secondary,
            custom_id="ggmw9:owner:underground", row=1
        )
        async def underground(self, interaction: discord.Interaction, button: discord.ui.Button):
            city = bot.get_cog("CareerCity")
            if not city:
                await interaction.response.send_message("❌ CareerCity Cog ماشي محمّلة.", ephemeral=True)
                return
            from cogs.city.underground_ui import OwnerUndergroundView
            await interaction.response.send_message(
                embed=city.underground_owner_embed(interaction.guild),
                view=OwnerUndergroundView(city),
                ephemeral=True,
            )
    
        @discord.ui.button(
            label="CITY Health", emoji="🩺", style=discord.ButtonStyle.secondary,
            custom_id="ggmw9:owner:city_health", row=1
        )
        async def city_health(self, interaction: discord.Interaction, button: discord.ui.Button):
            city = bot.get_cog("CareerCity")
            if not city:
                await interaction.response.send_message("❌ CareerCity Cog ماشي محمّلة.", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True, thinking=True)
            try:
                result = await asyncio.wait_for(city.city_diagnostics(interaction.guild), timeout=25)
                lines = [f"{'🟢' if ok else '🔴'} {name}" for name, ok in result.get("checks", [])]
                ug = result.get("underground")
                if ug:
                    lines.append("\n**🌑 Underground**")
                    lines.extend(f"{'🟢' if ok else '🔴'} {name}" for name, ok in ug.get("checks", []))
                    exposure = ug.get("admin_exposure") or []
                    if exposure:
                        lines.append("⚠️ Human Administrator bypass: " + ", ".join(exposure))
                    else:
                        lines.append("🟢 No human Administrator bypass outside Owner")
                embed = discord.Embed(
                    title="🩺 GGMW9 CITY — Health Check",
                    description="\n".join(lines)[:4000],
                    color=discord.Color.green() if result.get("ok") and not (ug and ug.get("admin_exposure")) else discord.Color.orange(),
                    timestamp=datetime.now(),
                )
                embed.set_footer(text="Read-only diagnostics • ما كيبدل لا فلوس لا بيانات الأعضاء")
                await interaction.edit_original_response(embed=embed)
            except Exception as exc:
                await interaction.edit_original_response(content=f"❌ Diagnostics error: {type(exc).__name__}: {exc}")
    
        @discord.ui.button(
            label="Test Channel Move", emoji="🧪", style=discord.ButtonStyle.danger,
            custom_id="ggmw9:owner:channel_move_test", row=1
        )
        async def channel_move_test(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_message(
                "🧪 اختار Channel عادية نجربو عليها الحركة عبر Discord API مباشرة.\n"
                "⚠️ الاختبار كيحركها Position وحدة فقط.",
                view=OwnerChannelMoveSelectView(),
                ephemeral=True,
            )
    
        @discord.ui.button(
            label="Security / Logs", emoji="🧾", style=discord.ButtonStyle.secondary,
            custom_id="ggmw9:owner:logs", row=1
        )
        async def logs(self, interaction: discord.Interaction, button: discord.ui.Button):
            eco_cog = bot.get_cog("Economy")
            eco_log_id = 0
            try:
                if eco_cog:
                    import games_config as _gcfg
                    eco_log_id = int(getattr(_gcfg, "ECONOMY_LOGS_CHANNEL_ID", 0) or 0)
            except Exception:
                pass
            embed = discord.Embed(
                title="🧾 Owner — Logs & Security",
                description=(
                    f"🛡️ Mod Logs: <#{MOD_LOGS_CHANNEL_ID}>\n"
                    f"🚨 Reports: <#{REPORTS_CHANNEL_ID}>\n"
                    f"🎫 Ticket Logs: <#{TICKET_LOGS_CHANNEL_ID or MOD_LOGS_CHANNEL_ID}>\n"
                    f"🆘 Support Center: <#{SUPPORT_CENTER_CHANNEL_ID}>\n"
                    + (f"💰 Economy Logs: <#{eco_log_id}>\n" if eco_log_id else "")
                    + f"👑 Owner ID: `{interaction.guild.owner_id}`\n"
                    f"🔐 Owner Center: <#{OWNER_CONTROL_CHANNEL_ID}>"
                ),
                color=discord.Color.blurple(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    
    async def setup_owner_control_panel(guild: discord.Guild):
        """كيضمن رسالة Owner Control واحدة فالقناة الخاصة."""
        if not OWNER_CONTROL_CHANNEL_ID:
            return
        channel = guild.get_channel(OWNER_CONTROL_CHANNEL_ID)
        if not channel:
            return
    
        embed = _owner_control_embed(guild)
        message = await upsert_fixed_panel(
            bot,
            channel,
            key="owner_control",
            matches=lambda message: (
                message.author == bot.user
                and bool(message.embeds)
                and "Owner Control Center" in (message.embeds[0].title or "")
            ),
            embed=embed,
            view=OwnerControlCenterView(),
            history_limit=None,
        )
        if message is None:
            print("[OWNER CENTER] ما قدرتش نصاوب/نحدث Panel دابا.")
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
