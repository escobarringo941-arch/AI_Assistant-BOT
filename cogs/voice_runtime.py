# -*- coding: utf-8 -*-
"""Unchanged ordered source component: voice_runtime."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║   Room Mute Lock — زر يكتم/يفك كتم كاع اللي فروم صوتي     ║
    # ═══════════════════════════════════════════════════════
    ROOM_MUTE_FILE = os.path.join(DATA_DIR, "room_mute.json")
    # panels: {message_id (str): channel_id (int)} — رسايل البانل المرتبطة بكل روم
    # muted_channels: [channel_id, ...] — الروومات اللي دابا "مقفولة" (كاع لي فيها مكتوم، وأي واحد يدخل ليها يتكتم توا)
    # manual_mutes: {channel_id (str): [user_id, ...]} — الأعضاء اللي تكتمو يدوياً من الـ Select
    #               (بحماية): زر "فك الكل" ما كيمسهمش، خاصك تفك عليهم بيدك من الـ Select
    room_mute_db = {"panels": {}, "muted_channels": [], "manual_mutes": {}}
    
    
    def load_room_mute():
        global room_mute_db
        try:
            with open(ROOM_MUTE_FILE, "r", encoding="utf-8") as f:
                room_mute_db = json.load(f)
            room_mute_db.setdefault("panels", {})
            room_mute_db.setdefault("muted_channels", [])
            room_mute_db.setdefault("manual_mutes", {})
        except FileNotFoundError:
            room_mute_db = {"panels": {}, "muted_channels": [], "manual_mutes": {}}
        except Exception as e:
            print(f"[ROOM_MUTE] خطأ فـ التحميل: {e}")
            room_mute_db = {"panels": {}, "muted_channels": [], "manual_mutes": {}}
    
    
    def save_room_mute():
        try:
            with open(ROOM_MUTE_FILE, "w", encoding="utf-8") as f:
                json.dump(room_mute_db, f, ensure_ascii=False)
        except Exception as e:
            print(f"[ROOM_MUTE] خطأ فـ الحفظ: {e}")
    
    
    load_room_mute()
    
    
    def can_toggle_room_mute(member: discord.Member, channel: discord.VoiceChannel) -> bool:
        """شكون يقدر "يستعمل" البانل (يدوس على الأزرار/الـ Select ولا يصاوب بانل جديد)
        — Owner + ROOM_MUTE_PANEL_ALLOWED_USER_IDS بوحدهم، حتى Admin/Moderator
        العاديين ماشي معنيين."""
        # Generic Room Mute must never become a staff bypass inside TEMP rooms.
        # TEMP's own guarded panel stays available to the actual room owner.
        if is_temp_voice_channel(channel):
            return is_temp_voice_protected_target(member)
        if is_temp_voice_protected_target(member):
            return True
        return member.id in ROOM_MUTE_PANEL_ALLOWED_USER_IDS


    async def apply_guarded_bot_voice_mute(
        member: discord.Member,
        muted: bool,
        *,
        reason: str,
        source: str,
    ):
        security = bot.get_cog("OwnerSecurity")
        if security:
            return await security.edit_member_voice_with_owner_lock(
                member.guild,
                bot.user,
                member,
                mute=muted,
                reason=reason,
                source=source,
            )
        return await member.edit(mute=muted, reason=reason)
    
    
    async def apply_room_mute_state(
        channel: discord.VoiceChannel,
        muted: bool,
        protected_ids=None,
        *,
        actor=None,
        lock_source: str = "Generic Room Mute all button",
    ):
        """كيطبق Room Mute على الجميع بما فيهم Admin/Mod، باستثناء Server Owner بوحدو."""
        protected_ids = protected_ids or set()
        targets = [
            m for m in channel.members
            if not m.bot and not is_temp_voice_protected_target(m)
            and bool(m.voice and m.voice.mute) != muted and m.id not in protected_ids
        ]
    
        security = bot.get_cog("OwnerSecurity")

        async def _apply_one(m: discord.Member):
            try:
                if security:
                    await security.edit_member_voice_with_owner_lock(
                        channel.guild,
                        actor,
                        m,
                        mute=muted,
                        reason="Room Mute Panel — كتم/فك الكل",
                        source=lock_source,
                    )
                else:
                    await m.edit(mute=muted, reason="Room Mute Panel — كتم/فك الكل")
                return True
            except (discord.Forbidden, discord.HTTPException):
                return False
    
        results = await asyncio.gather(*(_apply_one(m) for m in targets)) if targets else []
        successful_targets = [m for m, success in zip(targets, results) if success]
        return len(successful_targets), successful_targets
    
    
    def build_room_mute_embed(channel: discord.VoiceChannel, muted: bool) -> discord.Embed:
        embed = discord.Embed(
            title="🔇 الروم مقفولة" if muted else "🔊 الروم محلولة",
            description=(
                f"**Voice Channel:** {channel.mention}\n"
                + ("🔇 كاع اللي فيها مكتومين، بما فيهم Admin/Mod، غير Server Owner مستثنى.\n"
                   "💡 تقدر تفك الكتم على شخص معين بوحدو من القائمة تحت، وغادي يبقى محلول حتى تبدل الحالة ديالو يدوياً."
                   if muted else
                   "🔊 الكل يقدر يهدر عادي فهاد الروم.\n"
                   "💡 تقدر تكتم شخص معين بوحدو من القائمة تحت، وغادي يبقى مكتوم حتى تبدل الحالة ديالو يدوياً.")
            ),
            color=discord.Color.red() if muted else discord.Color.green()
        )
        embed.set_footer(text=f"{SERVER_NAME} | Room Mute Panel | {len(channel.members)} عضو دابا فالروم")
        return embed
    
    
    class RoomMemberSelect(discord.ui.Select):
        """Select كيبين كاع الأعضاء اللي كاينين دابا فالروم — اختيار عضو كيبدل
        (toggle) الحالة ديالو بوحدو (كتم↔فك)، بلا ماتمس الباقي."""
    
        def __init__(self, channel: Optional[discord.VoiceChannel] = None):
            options = []
            if channel:
                manual_list = room_mute_db.get("manual_mutes", {}).get(str(channel.id), [])
                for m in channel.members:
                    if m.bot or is_temp_voice_protected_target(m):
                        continue
                    is_muted = bool(m.voice and m.voice.mute)
                    is_protected = is_muted and m.id in manual_list
                    if is_protected:
                        desc = "🔒 مكتوم يدوياً (محمي من فك الكل) — اختارو باش تفك عليه"
                        emoji = "🔒"
                    elif is_muted:
                        desc = "مكتوم دابا — اختارو باش تفك عليه"
                        emoji = "🔇"
                    else:
                        desc = "مسموع دابا — اختارو باش تكتمو"
                        emoji = "🎙️"
                    options.append(discord.SelectOption(
                        label=m.display_name[:100], value=str(m.id), description=desc, emoji=emoji
                    ))
            if not options:
                options = [discord.SelectOption(label="ماكاين حتى عضو (بشري) فالروم دابا", value="none")]
    
            super().__init__(
                placeholder="🎯 اختار عضو معين باش تبدل الحالة ديالو (كتم/فك كتم)...",
                min_values=1, max_values=1,
                options=options[:25],
                custom_id="room_mute_member_select",
                disabled=(options[0].value == "none"),
            )
    
        async def callback(self, interaction: discord.Interaction):
            if self.values[0] == "none":
                await interaction.response.defer()
                return
    
            actor = interaction.user
            channel_id = room_mute_db.get("panels", {}).get(str(interaction.message.id))
            guild = interaction.guild
            channel = guild.get_channel(channel_id) if guild and channel_id else None
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message("❌ الروم ماعادش موجودة.", ephemeral=True)
                return
            if not isinstance(actor, discord.Member) or not can_toggle_room_mute(actor, channel):
                await interaction.response.send_message("❌ ماعندكش صلاحية تستعمل هاد البانل.", ephemeral=True)
                return
    
            target = guild.get_member(int(self.values[0]))
            if not target or not target.voice or not target.voice.channel or target.voice.channel.id != channel.id:
                await interaction.response.send_message("❌ هاد العضو ماعادش فالروم.", ephemeral=True)
                return
    
            await interaction.response.defer()
            new_mute = not bool(target.voice.mute)
            security = bot.get_cog("OwnerSecurity")
            try:
                reason = f"Room Mute Panel — تبديل يدوي من طرف {actor.display_name}"
                if security:
                    await security.edit_member_voice_with_owner_lock(
                        guild,
                        actor,
                        target,
                        mute=new_mute,
                        reason=reason,
                        source="Generic Room Mute member selector",
                    )
                else:
                    await target.edit(mute=new_mute, reason=reason)
            except (discord.Forbidden, discord.HTTPException):
                await interaction.followup.send("❌ ما قدرتش نبدل الحالة ديالو (مشكل صلاحيات).", ephemeral=True)
                return
            if security:
                await security.log_actor_action(
                    guild,
                    actor,
                    "Room Mute member" if new_mute else "Room Unmute member",
                    target=target,
                    channel=channel,
                )
    
            # كنسجلو/كنحيدو من manual_mutes باش زر "فك الكل" مايمسوش هاد العضو إلا كتمتيه بيدك
            manual_list = room_mute_db.setdefault("manual_mutes", {}).setdefault(str(channel.id), [])
            if new_mute:
                if target.id not in manual_list:
                    manual_list.append(target.id)
            else:
                if target.id in manual_list:
                    manual_list.remove(target.id)
            save_room_mute()
    
            muted_state = channel.id in room_mute_db.get("muted_channels", [])
            embed = build_room_mute_embed(channel, muted_state)
            await interaction.message.edit(embed=embed, view=RoomMuteToggleView(muted_state, channel))
            protect_note = " 🔒 (محمي من زر فك الكل)" if new_mute else ""
            await interaction.followup.send(
                f"{'🔇 تكتم' if new_mute else '🔊 تفك عليه الكتم'} {target.mention}.{protect_note}", ephemeral=True
            )
            # Owner stealth: هاد البانل غير للـ Owner + ROOM_MUTE_PANEL_ALLOWED_USER_IDS
            # (can_toggle_room_mute) — بلا log_action ولا trace فأي log channel.
    
    
    class RoomMuteToggleView(discord.ui.View):
        """بانل كامل: زوج أزرار (كتم الكل بلا استثناء / فك الكل) + Select باش تبدل
        الحالة ديال شخص معين بوحدو. Persistent — كيلقى الروم بواسطة message id
        ديال البانل (room_mute_db['panels'])."""
    
        def __init__(self, muted: bool = False, channel: Optional[discord.VoiceChannel] = None):
            super().__init__(timeout=None)
            self.add_item(RoomMemberSelect(channel))
    
        @discord.ui.button(label="🔇 كتم الكل (بلا استثناء)", style=discord.ButtonStyle.danger,
                            custom_id="room_mute_all_button", row=1)
        async def mute_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._set_global(interaction, True)
    
        @discord.ui.button(label="🔊 فك الكل", style=discord.ButtonStyle.success,
                            custom_id="room_unmute_all_button", row=1)
        async def unmute_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._set_global(interaction, False)
    
        async def _set_global(self, interaction: discord.Interaction, new_state: bool):
            member = interaction.user
            channel_id = room_mute_db.get("panels", {}).get(str(interaction.message.id))
            if not channel_id:
                await interaction.response.send_message("❌ ماكاينش هاد البانل فالسجل ديالنا.", ephemeral=True)
                return
    
            guild = interaction.guild
            channel = guild.get_channel(channel_id) if guild else None
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message("❌ الروم ماعادش موجودة.", ephemeral=True)
                return
    
            if not isinstance(member, discord.Member) or not can_toggle_room_mute(member, channel):
                await interaction.response.send_message("❌ ماعندكش صلاحية تستعمل هاد البانل.", ephemeral=True)
                return
    
            await interaction.response.defer()
    
            if new_state:
                if channel_id not in room_mute_db.setdefault("muted_channels", []):
                    room_mute_db["muted_channels"].append(channel_id)
                protected_ids = set()  # كتم الكل كيمس الجميع باستثناء Server Owner
            else:
                room_mute_db["muted_channels"] = [c for c in room_mute_db.get("muted_channels", []) if c != channel_id]
                # "فك الكل" ما كيمسش اللي تكتمو يدوياً من الـ Select — كيبقاو مكتومين
                protected_ids = set(room_mute_db.get("manual_mutes", {}).get(str(channel.id), []))
            save_room_mute()
    
            count, _changed_targets = await apply_room_mute_state(
                channel,
                new_state,
                protected_ids=protected_ids,
                actor=member,
                lock_source="Generic Room Mute all button",
            )
            security = bot.get_cog("OwnerSecurity")
            if security:
                await security.log_actor_action(
                    guild,
                    member,
                    "Room Mute all" if new_state else "Room Unmute all",
                    channel=channel,
                    details=f"Successful targets: {count}",
                )
            protected_still_muted = len(protected_ids) if not new_state else 0
    
            embed = build_room_mute_embed(channel, new_state)
            await interaction.message.edit(embed=embed, view=RoomMuteToggleView(new_state, channel))
    
            protect_note = f" (🔒 {protected_still_muted} عضو بقاو مكتومين حيت تكتمو يدوياً)" if protected_still_muted else ""
            await interaction.followup.send(
                f"{'🔇 الروم تقفلات، تكتمو' if new_state else '🔊 الروم تحلات، تفك الكتم على'} {count} عضو.{protect_note}",
                ephemeral=True
            )
            # Owner stealth: هاد البانل غير للـ Owner + ROOM_MUTE_PANEL_ALLOWED_USER_IDS
            # (can_toggle_room_mute) — بلا log_action ولا trace فأي log channel.
    
    
    @bot.command(name="roommutepanel", hidden=True)
    async def roommutepanel_cmd(ctx, channel: Optional[discord.VoiceChannel] = None):
        target_channel = channel
        if not target_channel:
            if isinstance(ctx.author, discord.Member) and ctx.author.voice and ctx.author.voice.channel:
                target_channel = ctx.author.voice.channel
            else:
                await ctx.send("❌ خاصك تكون داخل Voice Channel، ولا تعطي channel كـ parameter.", delete_after=8)
                return
    
        if not can_toggle_room_mute(ctx.author, target_channel):
            await ctx.send("❌ ماعندكش صلاحية تصاوب هاد البانل.", delete_after=8)
            return
    
        muted = target_channel.id in room_mute_db.get("muted_channels", [])
        embed = build_room_mute_embed(target_channel, muted)
        view = RoomMuteToggleView(muted, target_channel)
        msg = await ctx.send(embed=embed, view=view)
    
        room_mute_db.setdefault("panels", {})[str(msg.id)] = target_channel.id
        save_room_mute()
    
        # Owner stealth: نفس الدائرة المحدودة (can_toggle_room_mute) — بلا log_action.
    
    
    @bot.event
    async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        # رجوع Human للروم كيلغي cleanup المنتظر بلا ما نقطع coroutine وسط عملية حذف.
        if after.channel and str(after.channel.id) in temp_voice_channels:
            cancel_scheduled_temp_voice_cleanup(after.channel.id)
    
        # ═══════ Auto AFK: حتى Owner كيتنقل؛ Undeafen فـ AFK كيرجع للروم الأصلية ═══════
        try:
            returned_from_afk = await handle_afk_auto_return(member, before, after)
            update_afk_deafen_tracking(member, before, after)
        except Exception as e:
            returned_from_afk = False
            print(f"[AFK-AUTO-MOVE] خطأ فـ voice tracking/return ديال {member}: {e}")
    
        # ═══════ Temp Room ACL: Block > Private > Voice Mute. Server Owner محمي. ═══════
        blocked_entry_handled = False
        denied_entry_handled = False
        private_entry_handled = False
        if after.channel and (not before.channel or before.channel.id != after.channel.id) and is_temp_voice_channel(after.channel):
            if not is_temp_voice_protected_target(member):
                blocked_entry_handled = await enforce_temp_voice_block(member, after.channel)
                if not blocked_entry_handled:
                    denied_entry_handled = await enforce_temp_voice_deny(member, after.channel)
                if not blocked_entry_handled and not denied_entry_handled:
                    private_entry_handled = await enforce_temp_voice_private_access(member, after.channel)
                if not blocked_entry_handled and not denied_entry_handled and not private_entry_handled:
                    rec = get_temp_voice_acl(after.channel, create=False)
                    if rec and member.id in rec.get("voice_muted", []):
                        try:
                            if not after.mute:
                                await apply_guarded_bot_voice_mute(
                                    member,
                                    True,
                                    reason="Temp room Voice Mute persisted",
                                    source="TEMP persisted mute restore",
                                )
                        except (discord.Forbidden, discord.HTTPException):
                            pass
    
        # Voice Mute ديال temp room محلي للروم: ملي يخرج نفكو server mute، وملي يرجع كيتطبق من جديد.
        if before.channel and (not after.channel or before.channel.id != after.channel.id) and is_temp_voice_channel(before.channel):
            before_rec = get_temp_voice_acl(before.channel, create=False)
            if before_rec and member.id in before_rec.get("voice_muted", []) and not is_temp_voice_protected_target(member):
                try:
                    security = bot.get_cog("OwnerSecurity")
                    owner_locked = bool(
                        security
                        and security.is_owner_voice_locked(member.guild.id, member.id, "mute")
                    )
                    if after.mute and not owner_locked:
                        await apply_guarded_bot_voice_mute(
                            member,
                            False,
                            reason="خرج من temp room اللي كان Voice Muted فيها",
                            source="TEMP local mute cleanup",
                        )
                except (discord.Forbidden, discord.HTTPException):
                    pass
    
        # ═══════ Room Mute Lock: Admin/Mod كيتكتمو عادي؛ Server Owner بوحدو مستثنى ═══════
        muted_channels = room_mute_db.get("muted_channels", [])
        if muted_channels and not blocked_entry_handled and not denied_entry_handled and not private_entry_handled and not is_temp_voice_protected_target(member):
            after_channel_id = after.channel.id if after.channel else None
            before_channel_id = before.channel.id if before.channel else None
    
            if after_channel_id in muted_channels and after_channel_id != before_channel_id:
                try:
                    if not (after.mute):
                        await apply_guarded_bot_voice_mute(
                            member,
                            True,
                            reason="دخل لروم مقفولة (Room Mute Lock)",
                            source="Room Mute entry enforcement",
                        )
                except (discord.Forbidden, discord.HTTPException):
                    pass
            elif before_channel_id in muted_channels and after_channel_id != before_channel_id:
                try:
                    security = bot.get_cog("OwnerSecurity")
                    owner_locked = bool(
                        security
                        and security.is_owner_voice_locked(member.guild.id, member.id, "mute")
                    )
                    if after.mute and not owner_locked:
                        await apply_guarded_bot_voice_mute(
                            member,
                            False,
                            reason="خرج من روم مقفولة (Room Mute Lock)",
                            source="Room Mute exit cleanup",
                        )
                except (discord.Forbidden, discord.HTTPException):
                    pass
    
        # ═══════ Join to Create: العضو دخل لـ channel "➕ دير روم" ═══════
        if (bot_settings['join_to_create_enabled'] and JOIN_TO_CREATE_CHANNEL_ID
                and after.channel and after.channel.id == JOIN_TO_CREATE_CHANNEL_ID):
            creator_channel = after.channel
            guild = member.guild
            category = None
            if TEMP_VC_CATEGORY_ID:
                category = guild.get_channel(TEMP_VC_CATEGORY_ID)
            if not category:
                category = creator_channel.category
    
            overwrites = {
                # الروم كتبان للجميع من البداية. Privacy من بعد غادي تسد غير Connect وما غاديش تخبيها.
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=True, connect=True,
                    manage_channels=False, manage_roles=False,
                    move_members=False, mute_members=False, deafen_members=False,
                ),
                member: discord.PermissionOverwrite(
                    view_channel=True, connect=True, speak=True, send_messages=True, read_message_history=True,
                    manage_channels=False, manage_roles=False,
                    move_members=False, mute_members=False, deafen_members=False,
                ),
            }
            for staff_role_id in (ADMIN_ROLE_ID, MODERATOR_ROLE_ID):
                staff_role = guild.get_role(staff_role_id) if staff_role_id else None
                if staff_role:
                    overwrites[staff_role] = discord.PermissionOverwrite(
                        manage_channels=False, manage_roles=False,
                        move_members=False, mute_members=False, deafen_members=False,
                    )
            # البوت خاصو يبقى قادر يبعث/يحدّث البانل ويطبق Block/Kick/Mutes.
            if guild.me:
                overwrites[guild.me] = discord.PermissionOverwrite(
                    view_channel=True, connect=True, send_messages=True, read_message_history=True,
                    manage_messages=(True if guild.me.guild_permissions.manage_messages else None),
                    manage_channels=True, manage_roles=True, move_members=True,
                    mute_members=True, deafen_members=True,
                )
            # Unverified حتى هو يشوف اسم الروم، ولكن ما يدخلش حتى يتفعل.
            unverified_role = guild.get_role(UNVERIFIED_ROLE_ID) if UNVERIFIED_ROLE_ID else None
            if unverified_role:
                overwrites[unverified_role] = discord.PermissionOverwrite(view_channel=True, connect=False)
            new_channel = None
            try:
                new_channel = await guild.create_voice_channel(
                    name=TEMP_VC_NAME_TEMPLATE.format(name=member.display_name)[:100],
                    category=category,
                    overwrites=overwrites,
                    user_limit=TEMP_VC_DEFAULT_LIMIT,
                    reason=f"Join to Create — {member.display_name}"
                )
                temp_voice_channels[str(new_channel.id)] = member.id
                save_temp_voice_channels()
                rec = get_temp_voice_acl(new_channel)
                rec["owner_id"] = member.id
                rec["created_at"] = int(new_channel.created_at.timestamp())
                rec["private"] = False
                rec["music_bot_id"] = None
                rec["music_wait_since"] = rec["created_at"]
                save_temp_voice_acl()
                await enforce_temp_voice_security_overwrites(new_channel)
                await member.move_to(new_channel, reason="Join to Create")
            except discord.Forbidden:
                print("[VOICE] ⚠️ ماعندش صلاحية Manage Channels باش نخلق الروومات المؤقتة.")
                if new_channel is not None and str(new_channel.id) in temp_voice_channels:
                    await cleanup_temp_voice_room_if_empty(
                        new_channel,
                        grace_seconds=0,
                        reason="Join to Create فشل قبل ما يدخل Owner",
                    )
            except Exception as e:
                print(f"[VOICE] خطأ فـ خلق روم مؤقت: {e}")
                if new_channel is not None and str(new_channel.id) in temp_voice_channels:
                    await cleanup_temp_voice_room_if_empty(
                        new_channel,
                        grace_seconds=0,
                        reason="Join to Create فشل قبل ما يكمل",
                    )
            else:
                try:
                    await assign_temp_music_bot(new_channel, attempt_move=True)
                except Exception as e:
                    # Music integration ما خاصهاش توقف الروم الأساسية.
                    print(f"[TEMP-MUSIC] فشل تعيين Music Bot للروم {new_channel.id}: {e}")
                await send_temp_voice_control_panel(new_channel)
    
        # ═══════ تنظيف: bots ماكيحسبوش أعضاء؛ آخر Human كيخرج كنراجع ونمسحوها ═══════
        if before.channel and str(before.channel.id) in temp_voice_channels:
            left_channel = before.channel
            if not has_human_members(left_channel.members):
                schedule_temp_voice_cleanup(
                    left_channel,
                    reason="آخر Human خرج من Temp Room",
                )
    
    
    @bot.hybrid_command(name="voicerename", description="بدل سمية الروم الصوتي المؤقت ديالك")
    async def voicerename_cmd(ctx, *, new_name: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت باش تبدل سميتو.", ephemeral=True)
            return
        channel = ctx.author.voice.channel
        if not is_temp_voice_owner(ctx.author, channel):
            await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
            return
        try:
            await channel.edit(name=new_name[:100], reason=f"Renamed by {ctx.author.display_name}")
            await refresh_temp_voice_control_panel(channel, create_if_missing=True)
            await ctx.send(f"✅ تبدلات سمية الروم لـ **{new_name[:100]}**")
        except discord.HTTPException as e:
            await ctx.send(f"❌ ما قدرتش نبدل السمية: {e}", ephemeral=True)
    
    
    @bot.hybrid_command(name="voicelimit", description="حدد عدد الأعضاء المسموح فالروم الصوتي ديالك (0 = بلا حد)")
    async def voicelimit_cmd(ctx, limit: int):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت.", ephemeral=True)
            return
        channel = ctx.author.voice.channel
        if not is_temp_voice_owner(ctx.author, channel):
            await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
            return
        limit = max(0, min(limit, 99))
        try:
            await channel.edit(user_limit=limit, reason=f"Limit set by {ctx.author.display_name}")
            await refresh_temp_voice_control_panel(channel, create_if_missing=True)
            await ctx.send(f"✅ الحد الأقصى دابا هو **{limit if limit else 'بلا حدود'}**")
        except discord.HTTPException as e:
            await ctx.send(f"❌ خطأ: {e}", ephemeral=True)
    
    
    @bot.hybrid_command(name="voicelock", description="سد الروم الصوتي المؤقت ديالك (حتى واحد ما يقدر يدخل من بعد)")
    async def voicelock_cmd(ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت.", ephemeral=True)
            return
        channel = ctx.author.voice.channel
        if not is_temp_voice_owner(ctx.author, channel):
            await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
            return
        ok, msg = await set_temp_voice_private(channel, True, actor=ctx.author)
        await ctx.send(msg, ephemeral=not ok)
    
    
    @bot.hybrid_command(name="voiceunlock", description="حل الروم الصوتي المؤقت ديالك")
    async def voiceunlock_cmd(ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت.", ephemeral=True)
            return
        channel = ctx.author.voice.channel
        if not is_temp_voice_owner(ctx.author, channel):
            await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
            return
        ok, msg = await set_temp_voice_private(channel, False, actor=ctx.author)
        await ctx.send(msg, ephemeral=not ok)
    
    
    def is_afk_channel(channel: discord.VoiceChannel, guild: discord.Guild) -> bool:
        """واش هاد الروم هي روم AFK؟ (الروم الرسمية ديال السيرفر ولا وحدة من AFK_CHANNEL_IDS)"""
        if guild.afk_channel and channel.id == guild.afk_channel.id:
            return True
        return channel.id in AFK_CHANNEL_IDS
    
    
    def classify_voice_member(m: discord.Member, channel: discord.VoiceChannel,
                              guild: discord.Guild) -> tuple:
        """كيحدد أشمن درجة ديال XP تستاهل هاد العضو دابا.
        كيرجع (نوع, شحال من XP, واش هو AFK).
    
        الدرجات:
          stream  🎥 كيدير Go Live / كاميرا      → أكبر XP
          voice   🎤 حال المايك / كيهضر          → XP عادي
          afk_ch  💤 مريح فالروم ديال AFK        → XP مخفض (ولكن أكثر من اللي تحت)
          afk_mut 🔇 سد المايك/Deafen فروم عادية → أصغر XP
        """
        v = m.voice
        if not v:
            return None, 0, False
    
        # 🎥 لايفستريم ولا كاميرا مشعولة = أعلى درجة، حتى لو المايك مسدود
        if v.self_stream or v.self_video:
            return "stream", int(xp_settings["stream_per_interval"]), False
    
        in_afk_room = is_afk_channel(channel, guild)
        is_quiet = bool(v.self_mute or v.self_deaf or v.deaf or v.mute)
    
        # 💤 الروم ديال AFK: مهما كان الحال، هادي درجة AFK ديال الروم
        if in_afk_room:
            return "afk_channel", int(xp_settings["afk_channel_per_interval"]), True
    
        # 🔇 مايك مسدود / Deafen فروم عادية
        if is_quiet:
            if VOICE_XP_COUNT_MUTED_DEAFENED:
                return "voice", int(xp_settings["voice_per_interval"]), False
            return "afk_muted", int(xp_settings["afk_muted_per_interval"]), True
    
        # 🎤 المايك محلول = مشارك عادي
        return "voice", int(xp_settings["voice_per_interval"]), False
    
    
    @tasks.loop(minutes=xp_settings["voice_interval_minutes"])
    async def voice_xp_loop():
        if not bot_settings['voice_xp_enabled'] or not bot_settings['leveling_enabled']:
            return
        for guild in bot.guilds:
            for channel in guild.voice_channels:
                # رومات محيدة كامل — حتى XP ديال AFK ماكيتعطاش فيهم
                if channel.id in VOICE_XP_EXCLUDE_CHANNEL_IDS:
                    continue
                # روم "دير روم" (Join to Create) ماشي روم حقيقية، غير ممر
                if bot_settings['join_to_create_enabled'] and channel.id == JOIN_TO_CREATE_CHANNEL_ID:
                    continue
    
                humans = [m for m in channel.members if not m.bot]
                if not humans:
                    continue
                meets_min_humans = len(humans) >= xp_settings["voice_min_humans"]
    
                for m in humans:
                    kind, amount, is_afk = classify_voice_member(m, channel, guild)
                    if not kind or amount <= 0:
                        continue
    
                    # ═══ شرط عدد الناس فالروم (مكافحة الفارمينغ بوحدك) ═══
                    if kind == "stream":
                        pass                      # اللايفستريم دايما كيتحسب
                    elif is_afk:
                        if not AFK_XP_ENABLED:
                            continue
                        # الروم ديال AFK طبيعي تكون خاوية، علاش الشرط اختياري هنا
                        if AFK_XP_REQUIRE_MIN_HUMANS and not meets_min_humans:
                            continue
                    elif not meets_min_humans:
                        continue                  # فويس عادي بوحدو = ماكاين XP
    
                    # ═══ السقف اليومي ديال XP ديال AFK ═══
                    if is_afk:
                        amount = afk_xp_allowed(guild.id, m.id, amount)
                        if amount <= 0:
                            continue
    
                    try:
                        await grant_xp_and_announce(m, guild, amount, fallback_channel=channel, source=kind)
                        if is_afk:
                            bump_afk_xp_used(guild.id, m.id, amount)
                    except Exception as e:
                        print(f"[VOICE-XP] خطأ فـ إعطاء XP لـ {m}: {e}")
    
    
    @voice_xp_loop.before_loop
    async def before_voice_xp_loop():
        await bot.wait_until_ready()
    
    
    @voice_xp_loop.error
    async def voice_xp_loop_error(error):
        print(f"[VOICE-XP] خطأ كبير وقف الـ loop: {error}")
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
