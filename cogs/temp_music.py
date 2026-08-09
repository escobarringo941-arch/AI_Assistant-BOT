# -*- coding: utf-8 -*-
"""Music-bot leases and self-healing cleanup for temporary voice rooms."""

from cogs._component_runtime import install_component, runtime_namespace, uninstall_component
from cogs.temp_music_policy import (
    TEMP_ROOM_EMPTY_GRACE_SECONDS,
    TEMP_ROOM_HOUSEKEEPING_SECONDS,
    TEMP_ROOM_ORPHAN_MIN_AGE_SECONDS,
    get_music_bot_profile,
    has_human_members,
    is_managed_temp_name,
    normalize_music_bot_id,
    plan_music_bot_leases,
)


# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    temp_music_guild_locks = {}
    temp_voice_cleanup_tasks = {}
    temp_voice_cleanup_cancel_events = {}


    def _temp_music_lock(guild_id: int):
        lock = temp_music_guild_locks.get(int(guild_id))
        if lock is None:
            lock = asyncio.Lock()
            temp_music_guild_locks[int(guild_id)] = lock
        return lock


    def _music_wait_timestamp(rec: dict) -> int:
        value = rec.get("music_wait_since") or rec.get("created_at") or 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


    def _tracked_temp_rooms(guild: discord.Guild) -> list:
        rooms = []
        for channel_id in list(temp_voice_channels):
            try:
                channel = guild.get_channel(int(channel_id))
            except (TypeError, ValueError):
                channel = None
            if isinstance(channel, discord.VoiceChannel):
                rooms.append(channel)
        return rooms


    def _temp_room_is_lease_eligible(channel: discord.VoiceChannel) -> bool:
        # Music leases belong only to rooms that currently contain a human.
        return has_human_members(channel.members)


    def _repair_temp_music_leases_locked(guild: discord.Guild) -> tuple:
        """Preserve valid leases, repair duplicates, then fill waiting rooms FIFO."""
        rooms = _tracked_temp_rooms(guild)
        rooms.sort(
            key=lambda channel: (
                _music_wait_timestamp(get_temp_voice_acl(channel)),
                int(channel.id),
            )
        )
        changed_ids = set()
        room_states = []
        for channel in rooms:
            rec = get_temp_voice_acl(channel)
            eligible = _temp_room_is_lease_eligible(channel)
            room_states.append((
                channel.id,
                eligible,
                rec.get("music_bot_id"),
                _music_wait_timestamp(rec),
            ))

        planned = plan_music_bot_leases(room_states)
        now_ts = int(datetime.now().timestamp())
        for channel in rooms:
            rec = get_temp_voice_acl(channel)
            desired = planned.get(channel.id)
            eligible = _temp_room_is_lease_eligible(channel)
            if rec.get("music_bot_id") != desired:
                rec["music_bot_id"] = desired
                changed_ids.add(channel.id)
            if desired is not None:
                if rec.get("music_wait_since") is not None:
                    rec["music_wait_since"] = None
                    changed_ids.add(channel.id)
            elif eligible and not rec.get("music_wait_since"):
                rec["music_wait_since"] = rec.get("created_at") or now_ts
                changed_ids.add(channel.id)

        return rooms, changed_ids


    def _temp_music_connection_status(channel: discord.VoiceChannel, bot_id: int) -> tuple:
        member = channel.guild.get_member(int(bot_id))
        if member is None:
            return "missing", None
        if any(getattr(item, "id", None) == member.id for item in channel.members):
            return "ready", member
        current_channel = getattr(getattr(member, "voice", None), "channel", None)
        if current_channel is None:
            return "not_connected", member
        if is_temp_voice_channel(current_channel):
            if not has_human_members(current_channel.members):
                return "retiring", member
            return "busy", member
        # A bot-only channel may still contain a 24/7 session or an unattended
        # queue.  Never infer that an arbitrary external channel is a safe park.
        return "external", member


    async def _ensure_temp_music_permissions(channel: discord.VoiceChannel, bot_id: int) -> bool:
        member = channel.guild.get_member(int(bot_id))
        if member is None:
            return False
        overwrite = channel.overwrites_for(member)
        required = {
            "view_channel": True,
            "connect": True,
            "speak": True,
            "use_voice_activation": True,
            "send_messages": True,
            "embed_links": True,
            "read_message_history": True,
        }
        if all(getattr(overwrite, name, None) is value for name, value in required.items()):
            return True
        overwrite.update(**required)
        try:
            await channel.set_permissions(
                member,
                overwrite=overwrite,
                reason="Temp Room assigned music bot",
            )
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False


    async def _try_move_assigned_music_bot_locked(channel: discord.VoiceChannel) -> tuple:
        rec = get_temp_voice_acl(channel)
        bot_id = normalize_music_bot_id(rec.get("music_bot_id"))
        if bot_id is None:
            return "none", None

        status, member = _temp_music_connection_status(channel, bot_id)
        if status != "retiring" or member is None:
            return status, member
        try:
            await member.move_to(channel, reason="Assigned to an active Temp Room")
            return "moved", member
        except (discord.Forbidden, discord.HTTPException):
            return "move_failed", member


    async def assign_temp_music_bot(channel: discord.VoiceChannel, *, attempt_move: bool = True) -> tuple:
        """Allocate a stable lease; the sixth active room waits for a released bot."""
        async with _temp_music_lock(channel.guild.id):
            current = channel.guild.get_channel(channel.id)
            if (not isinstance(current, discord.VoiceChannel)
                    or str(channel.id) not in temp_voice_channels
                    or not has_human_members(current.members)):
                return None, "inactive"
            channel = current
            rooms, changed_ids = _repair_temp_music_leases_locked(channel.guild)
            if changed_ids:
                save_temp_voice_acl()
            rec = get_temp_voice_acl(channel)
            profile = get_music_bot_profile(rec.get("music_bot_id"))
            if profile is None:
                return None, "none"
            await _ensure_temp_music_permissions(channel, profile.user_id)
            if attempt_move:
                status, _ = await _try_move_assigned_music_bot_locked(channel)
            else:
                status, _ = _temp_music_connection_status(channel, profile.user_id)
            return profile, status


    async def reconcile_temp_music_assignments(guild: discord.Guild) -> None:
        """Idempotent restart repair without stealing a bot from an active session."""
        async with _temp_music_lock(guild.id):
            rooms, changed_ids = _repair_temp_music_leases_locked(guild)
            if changed_ids:
                save_temp_voice_acl()
            changed_channel_ids = set(changed_ids)
            permission_targets = []
            for channel in rooms:
                rec = get_temp_voice_acl(channel)
                bot_id = normalize_music_bot_id(rec.get("music_bot_id"))
                if bot_id is not None:
                    permission_targets.append((channel, bot_id))
        # Permission HTTP calls do not hold the lease lock. The helper skips the
        # request entirely when the seven required overwrites are already True.
        for channel, bot_id in permission_targets:
            current = guild.get_channel(channel.id)
            if not isinstance(current, discord.VoiceChannel) or not has_human_members(current.members):
                continue
            current_rec = get_temp_voice_acl(current, create=False) or {}
            if normalize_music_bot_id(current_rec.get("music_bot_id")) != bot_id:
                continue
            await _ensure_temp_music_permissions(current, bot_id)
        for channel_id in changed_channel_ids:
            current = guild.get_channel(channel_id)
            if not isinstance(current, discord.VoiceChannel) or not has_human_members(current.members):
                continue
            try:
                await refresh_temp_voice_control_panel(current, create_if_missing=False)
            except Exception as exc:
                print(f"[TEMP-MUSIC] refresh بعد lease repair فشل فـ {channel_id}: {exc}")


    def temp_music_panel_summary(channel: discord.VoiceChannel) -> str:
        rec = get_temp_voice_acl(channel, create=False) or {}
        profile = get_music_bot_profile(rec.get("music_bot_id"))
        if profile is None:
            return "🚫 ما متعيّن حتى Music Bot لهاد الروم (الخمسة الأوائل مستعملين)."
        status, _ = _temp_music_connection_status(channel, profile.user_id)
        labels = {
            "ready": "✅ داخل الروم وجاهز",
            "retiring": "🟡 باقي وحدو فـTemp Room كتسد وغادي ينتقل بأمان",
            "busy": "🟠 مستعمل دابا فـروم أخرى",
            "external": "🟠 متصل فـروم أخرى — ما غاديش البوت ينقلو بلا إذن",
            "not_connected": "⚪ ما داخلش للصوت دابا — خاص Owner يستعمل أمر Join الرسمي",
            "missing": "⚠️ ما لقيتش البوت داخل السيرفر",
        }
        return f"<@{profile.user_id}> — **{profile.name}**\n{labels.get(status, status)}"


    class TempMusicLinksView(discord.ui.View):
        def __init__(self, profile):
            super().__init__(timeout=120)
            if profile.dashboard_url:
                self.add_item(discord.ui.Button(
                    label=("Player Dashboard" if profile.provider == "seshtunes" else "Statistics Dashboard"),
                    style=discord.ButtonStyle.link,
                    url=profile.dashboard_url,
                    emoji="🌐",
                ))
            self.add_item(discord.ui.Button(
                label="شوف Commands",
                style=discord.ButtonStyle.link,
                url=profile.commands_url,
                emoji="📖",
            ))


    def _temp_music_help_embed(channel: discord.VoiceChannel, profile, status: str) -> discord.Embed:
        status_lines = {
            "ready": "✅ البوت راه داخل الروم وجاهز.",
            "moved": "✅ تنقل البوت أوتوماتيكياً لهاد الروم.",
            "retiring": "🟡 البوت باقي بوحدو فـTemp Room قديمة؛ النظام غادي ينقلو ملي تسد.",
            "busy": "🟠 البوت مستعمل فـروم أخرى، وما غاديش نسرقوه من الناس اللي كيسمعو دابا.",
            "external": "🟠 البوت متصل فـروم أخرى؛ ما غاديش ننقلوه حيت ممكن تكون فيه جلسة موسيقى خدامة.",
            "not_connected": "⚪ البوت ما داخلش للصوت. Discord ما كيسمحش لبوت آخر يربطو نيابةً عليه.",
            "missing": "⚠️ هاد Music Bot ما بانش داخل السيرفر.",
            "move_failed": "⚠️ حاولت ننقل البوت ولكن Discord رفض العملية؛ راجع Move Members وConnect.",
        }
        if profile.provider == "seshtunes":
            commands_text = (
                "**SeshTunes:** دخل لهاد الروم، كتب `/join` واختار Command ديال **SeshTunes**، "
                "ومن بعد `/play`، ولا `/player` باش يطلع Player الرسمي."
            )
        else:
            commands_text = (
                f"**Jockie:** استعمل `<@{profile.user_id}> join`، "
                f"ومن بعد `<@{profile.user_id}> play اسم الأغنية` باش تستهدف نفس البوت بالضبط."
            )
        return discord.Embed(
            title=f"🎵 {profile.name} — {channel.name}",
            description=(
                f"{status_lines.get(status, status)}\n\n{commands_text}\n\n"
                "ℹ️ الزر ما كينفذش Command ديال بوت آخر؛ الأمر خاص يرسلو User حقيقي من Discord."
            ),
            color=discord.Color.green() if status in {"ready", "moved"} else discord.Color.orange(),
        )


    async def open_temp_music_panel(interaction: discord.Interaction, channel: discord.VoiceChannel) -> None:
        # Opening a help panel must never move a third-party bot unexpectedly.
        profile, status = await assign_temp_music_bot(channel, attempt_move=False)
        if status == "inactive":
            await interaction.followup.send(
                "❌ هاد Temp Room تسدات ولا ما بقاتش فيها حتى Human.",
                ephemeral=True,
            )
            return
        if profile is None:
            await interaction.followup.send(
                "🚫 هادي روم رقم 6 ولا أكثر: الخمسة Music Bots متعيّنين لرومات أخرى دابا.",
                ephemeral=True,
            )
            return
        try:
            await refresh_temp_voice_control_panel(channel, create_if_missing=False)
        except Exception as exc:
            print(f"[TEMP-MUSIC] refresh من Music button فشل فـ {channel.id}: {exc}")
        await interaction.followup.send(
            embed=_temp_music_help_embed(channel, profile, status),
            view=TempMusicLinksView(profile),
            ephemeral=True,
        )


    def _purge_room_mute_state(channel_id: int) -> None:
        db = globals().get("room_mute_db")
        save_fn = globals().get("save_room_mute")
        if not isinstance(db, dict):
            return
        changed = False
        if channel_id in db.get("muted_channels", []):
            db["muted_channels"] = [item for item in db.get("muted_channels", []) if item != channel_id]
            changed = True
        if str(channel_id) in db.get("manual_mutes", {}):
            db.get("manual_mutes", {}).pop(str(channel_id), None)
            changed = True
        panels = db.get("panels", {})
        stale_panels = [message_id for message_id, saved_id in panels.items() if saved_id == channel_id]
        for message_id in stale_panels:
            panels.pop(message_id, None)
            changed = True
        if changed and callable(save_fn):
            save_fn()


    def _purge_afk_auto_return_state(channel_id: int) -> None:
        """A deleted room must never stay as a future Auto-AFK return target."""
        db = globals().get("afk_auto_return")
        save_fn = globals().get("save_afk_auto_return")
        if not isinstance(db, dict):
            return
        changed = False
        for key, rec in list(db.items()):
            if not isinstance(rec, dict):
                continue
            try:
                saved_channel_id = int(rec.get("channel_id", 0) or 0)
            except (TypeError, ValueError):
                saved_channel_id = 0
            if saved_channel_id == int(channel_id):
                db.pop(key, None)
                changed = True
        if changed and callable(save_fn):
            save_fn()


    def _purge_temp_voice_state(channel_id: int) -> None:
        temp_voice_channels.pop(str(channel_id), None)
        temp_voice_acl.pop(str(channel_id), None)
        save_temp_voice_channels()
        save_temp_voice_acl()
        _purge_room_mute_state(channel_id)
        _purge_afk_auto_return_state(channel_id)


    async def cleanup_temp_voice_room_if_empty(
        channel: discord.VoiceChannel,
        *,
        grace_seconds: int = TEMP_ROOM_EMPTY_GRACE_SECONDS,
        reason: str = "Temp Room بقات بلا أعضاء",
        allow_untracked: bool = False,
    ) -> bool:
        """Delete a no-human room exactly once; bots never keep a Temp Room alive."""
        if grace_seconds > 0:
            await asyncio.sleep(grace_seconds)

        guild = channel.guild
        async with _temp_music_lock(guild.id):
            current = guild.get_channel(channel.id)
            tracked = str(channel.id) in temp_voice_channels
            if current is None:
                if tracked or allow_untracked:
                    _purge_temp_voice_state(channel.id)
                return tracked or allow_untracked
            if not isinstance(current, discord.VoiceChannel):
                return False
            if not tracked and not allow_untracked:
                return False
            if has_human_members(current.members):
                return False
            released_bot_id = None
            if tracked:
                rec = get_temp_voice_acl(current)
                released_bot_id = normalize_music_bot_id(rec.get("music_bot_id"))
                rec["music_bot_id"] = None
                rec.setdefault("music_wait_since", rec.get("created_at") or int(datetime.now().timestamp()))

                rooms, changed_ids = _repair_temp_music_leases_locked(guild)
                save_temp_voice_acl()

                # If a sixth room was waiting, hand it this lease before deleting
                # the old room so an already-connected bot can be moved directly.
                if released_bot_id is not None:
                    target = next((
                        room for room in rooms
                        if room.id != current.id
                        and normalize_music_bot_id(get_temp_voice_acl(room).get("music_bot_id")) == released_bot_id
                    ), None)
                    member = guild.get_member(released_bot_id)
                    member_channel = getattr(getattr(member, "voice", None), "channel", None) if member else None
                    if target is not None:
                        await _ensure_temp_music_permissions(target, released_bot_id)
                        if member is not None and member_channel is not None and member_channel.id == current.id:
                            try:
                                await member.move_to(target, reason="Music lease انتقل للروم المنتظرة")
                            except (discord.Forbidden, discord.HTTPException):
                                pass
                        try:
                            await refresh_temp_voice_control_panel(target, create_if_missing=True)
                        except Exception as exc:
                            print(f"[TEMP-MUSIC] refresh ديال الروم المنتظرة فشل: {exc}")

            # Network calls above can take long enough for a human to rejoin.
            # Re-fetch and re-plan instead of ever deleting an occupied room.
            current = guild.get_channel(channel.id)
            if not isinstance(current, discord.VoiceChannel):
                _purge_temp_voice_state(channel.id)
                return True
            if has_human_members(current.members):
                rooms, changed_ids = _repair_temp_music_leases_locked(guild)
                if changed_ids:
                    save_temp_voice_acl()
                return False

            deleted = False
            try:
                await current.delete(reason=reason)
                deleted = True
            except discord.NotFound:
                deleted = True
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[TEMP-VOICE CLEANUP] حذف الروم {current.id} فشل وغادي نعاود نحاول: {exc}")

            if deleted:
                _purge_temp_voice_state(current.id)
            return deleted


    def cancel_scheduled_temp_voice_cleanup(channel_id: int) -> None:
        channel_id = int(channel_id)
        temp_voice_cleanup_tasks.pop(channel_id, None)
        cancel_event = temp_voice_cleanup_cancel_events.pop(channel_id, None)
        if cancel_event is not None:
            cancel_event.set()


    def schedule_temp_voice_cleanup(
        channel: discord.VoiceChannel,
        *,
        reason: str = "آخر عضو خرج من Temp Room",
    ):
        channel_id = int(channel.id)
        current = temp_voice_cleanup_tasks.get(channel_id)
        if current is not None and not current.done():
            return current
        cancel_event = asyncio.Event()

        async def runner():
            try:
                try:
                    await asyncio.wait_for(
                        cancel_event.wait(),
                        timeout=TEMP_ROOM_EMPTY_GRACE_SECONDS,
                    )
                    return False
                except asyncio.TimeoutError:
                    pass
                return await cleanup_temp_voice_room_if_empty(
                    channel,
                    grace_seconds=0,
                    reason=reason,
                )
            except asyncio.CancelledError:
                return False
            except Exception as exc:
                print(f"[TEMP-VOICE CLEANUP] خطأ غير متوقع فـ {channel_id}: {exc}")
                return False
            finally:
                if temp_voice_cleanup_tasks.get(channel_id) is asyncio.current_task():
                    temp_voice_cleanup_tasks.pop(channel_id, None)
                    temp_voice_cleanup_cancel_events.pop(channel_id, None)

        task = asyncio.create_task(runner(), name=f"temp-room-cleanup-{channel_id}")
        temp_voice_cleanup_tasks[channel_id] = task
        temp_voice_cleanup_cancel_events[channel_id] = cancel_event
        return task


    def _temp_category_id(guild: discord.Guild) -> int:
        if TEMP_VC_CATEGORY_ID:
            return int(TEMP_VC_CATEGORY_ID)
        creator = guild.get_channel(JOIN_TO_CREATE_CHANNEL_ID) if JOIN_TO_CREATE_CHANNEL_ID else None
        return int(creator.category_id) if creator and creator.category_id else 0


    def _old_enough_to_be_orphan(channel: discord.VoiceChannel) -> bool:
        try:
            created_at = channel.created_at
            now = datetime.now(created_at.tzinfo) if created_at.tzinfo else datetime.now()
            return (now - created_at).total_seconds() >= TEMP_ROOM_ORPHAN_MIN_AGE_SECONDS
        except Exception:
            return False


    async def sweep_empty_temp_voice_rooms(guild: discord.Guild) -> int:
        """Retry tracked failures and clean ACL-backed orphan Temp Rooms."""
        removed = 0
        for channel in list(_tracked_temp_rooms(guild)):
            if not has_human_members(channel.members):
                removed += int(await cleanup_temp_voice_room_if_empty(
                    channel,
                    grace_seconds=0,
                    reason="Temp Room housekeeping — بلا أعضاء",
                ))

        category_id = _temp_category_id(guild)
        if category_id:
            for channel in list(guild.voice_channels):
                if channel.id == JOIN_TO_CREATE_CHANNEL_ID or channel.category_id != category_id:
                    continue
                if str(channel.id) in temp_voice_channels:
                    continue
                ownership_record = temp_voice_acl.get(str(channel.id))
                if not isinstance(ownership_record, dict):
                    continue
                if not ownership_record.get("owner_id") or not ownership_record.get("created_at"):
                    continue
                if not is_managed_temp_name(channel.name, TEMP_VC_NAME_TEMPLATE):
                    continue
                if has_human_members(channel.members) or not _old_enough_to_be_orphan(channel):
                    continue
                removed += int(await cleanup_temp_voice_room_if_empty(
                    channel,
                    grace_seconds=0,
                    reason="تنظيف Temp Room قديمة وبلا Owner",
                    allow_untracked=True,
                ))
        return removed


    @tasks.loop(seconds=TEMP_ROOM_HOUSEKEEPING_SECONDS)
    async def temp_voice_housekeeping_loop():
        for guild in list(bot.guilds):
            try:
                await sweep_empty_temp_voice_rooms(guild)
                await reconcile_temp_music_assignments(guild)
            except Exception as exc:
                print(f"[TEMP-VOICE HOUSEKEEPING] خطأ فـ {guild.id}: {exc}")


    @temp_voice_housekeeping_loop.before_loop
    async def before_temp_voice_housekeeping_loop():
        await bot.wait_until_ready()


    async def shutdown_temp_music_runtime() -> None:
        """Stop raw cleanup runners before an extension unload/reload."""
        for cancel_event in list(temp_voice_cleanup_cancel_events.values()):
            cancel_event.set()
        pending_tasks = [task for task in temp_voice_cleanup_tasks.values() if not task.done()]
        if pending_tasks:
            _, still_pending = await asyncio.wait(pending_tasks, timeout=5)
            for task in still_pending:
                task.cancel()
            if still_pending:
                await asyncio.gather(*still_pending, return_exceptions=True)
        temp_voice_cleanup_tasks.clear()
        temp_voice_cleanup_cancel_events.clear()
        temp_music_guild_locks.clear()


# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        shutdown = runtime_namespace().get("shutdown_temp_music_runtime")
        uninstall_component(__name__)
        if callable(shutdown):
            await shutdown()
