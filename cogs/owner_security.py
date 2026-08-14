# -*- coding: utf-8 -*-
"""Owner-only security boundary, audit mirror and voice protections for GGMW9."""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time
from typing import Iterable, Optional

import discord
from discord.ext import commands, tasks

from cogs._component_runtime import runtime_namespace
from cogs.owner_security_policy import (
    ADMIN_PERMISSION_NAMES,
    MODERATOR_PERMISSION_NAMES,
    VOICE_SECURITY_PERMISSION_NAMES,
    is_configured_staff,
    resolve_owner_voice_lock,
)


# ═══════════════════════════════════════════════════════
# ║   🕵️ OWNER STEALTH — تسجيل أفعال الاونر مطفي نهائياً   ║
# ═══════════════════════════════════════════════════════
#
# False = ما كيتسجل **والو**: لا قناة أمنية، لا DM، لا mirror.
#         الاونر كيبقا يدير اللي بغا بلا ما يتخلا حتى أثر.
#
# ⚠️ هادشي كيطفي **التسجيل بوحدو**. الحماية باقية خدامة 100%:
#      • سحب Administrator من الرولات (ضروري باش السجن يخدم)
#      • حماية الاونر من Timeout/Kick/Ban
#      • أقفال الفويس والدروع ديال قنوات الاونر
#    ما تحيدش الـCog من ai_bot.py — إلا حيدتيها، أي رول عندو
#    Administrator غادي يشوف السجن كامل ويكسر النظام.
OWNER_SECURITY_LOGGING_ENABLED = False

SECURITY_LOG_CHANNEL_NAME = "owner-security-logs"
SECURITY_LOG_CHANNEL_TOPIC = (
    "GGMW9 owner-only security and audit mirror. Do not expose this channel."
)
STATE_VERSION = 1
AUDIT_CACHE_SECONDS = 15


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clip(value, limit: int) -> str:
    text = str(value if value is not None else "—")
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def _entity_id(value) -> Optional[int]:
    try:
        return int(getattr(value, "id", 0) or 0) or None
    except (TypeError, ValueError):
        return None


class OwnerSecurity(commands.Cog):
    """Fail-closed owner protection plus a complete administrative audit mirror."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        gg = getattr(bot, "gg", {})
        self.data_dir = Path(gg.get("DATA_DIR") or "/app/data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.state_path = self.data_dir / "owner_security_state.json"
        self.configured_owner_id = int(gg.get("OWNER_ID") or 0)
        self.admin_role_id = int(gg.get("ADMIN_ROLE_ID") or 0)
        self.moderator_role_id = int(gg.get("MODERATOR_ROLE_ID") or 0)
        self.muted_role_id = int(gg.get("MUTED_ROLE_ID") or 0)
        self.join_to_create_channel_id = int(gg.get("JOIN_TO_CREATE_CHANNEL_ID") or 0)

        self.state = self._load_state()
        self._log_channel_lock = asyncio.Lock()
        self._role_sync_lock = asyncio.Lock()
        self._audit_fetch_lock = asyncio.Lock()
        self._audit_process_lock = asyncio.Lock()
        self._owner_shield_locks: dict[int, asyncio.Lock] = {}
        self._voice_lock_action_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._muted_role_action_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._recent_audits = deque(maxlen=300)
        self._seen_audit_ids = deque(maxlen=1500)
        self._seen_audit_id_set: set[int] = set()
        self._correlated_audit_ids = deque(maxlen=1500)
        self._correlated_audit_id_set: set[int] = set()
        self._internal_voice_ops: dict[tuple[int, int], list[dict]] = {}
        self._internal_role_ops: dict[tuple[int, int], list[dict]] = {}
        self._original_log_action = None
        self._log_wrapper = None
        self._startup_complete: set[int] = set()

    async def cog_load(self):
        self._install_existing_log_mirror()
        if not self.audit_backfill_loop.is_running():
            self.audit_backfill_loop.start()

    def cog_unload(self):
        self.audit_backfill_loop.cancel()
        shared = runtime_namespace()
        if self._log_wrapper is not None and shared.get("log_action") is self._log_wrapper:
            shared["log_action"] = self._original_log_action
            if hasattr(self.bot, "gg"):
                self.bot.gg["log_action"] = self._original_log_action

    # ------------------------------------------------------------------
    # Persistent state
    # ------------------------------------------------------------------

    def _load_state(self) -> dict:
        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                loaded.setdefault("version", STATE_VERSION)
                loaded.setdefault("guilds", {})
                return loaded
        except FileNotFoundError:
            pass
        except Exception as exc:
            print(f"[OWNER-SECURITY] state load failed: {exc}")
        return {"version": STATE_VERSION, "guilds": {}}

    def _save_state(self) -> None:
        self.state["version"] = STATE_VERSION
        temporary = self.state_path.with_suffix(".json.tmp")
        try:
            temporary.write_text(
                json.dumps(self.state, ensure_ascii=False, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            os.replace(temporary, self.state_path)
        except Exception as exc:
            print(f"[OWNER-SECURITY] state save failed: {exc}")
            try:
                temporary.unlink(missing_ok=True)
            except Exception:
                pass

    def _guild_state(self, guild_id: int) -> dict:
        record = self.state.setdefault("guilds", {}).setdefault(str(int(guild_id)), {})
        record.setdefault("log_channel_id", 0)
        record.setdefault("last_audit_id", 0)
        record.setdefault("voice_locks", {})
        record.setdefault("owner_shield", {})
        record.setdefault("owner_shield_restore_queue", [])
        return record

    # ------------------------------------------------------------------
    # Identity and permissions
    # ------------------------------------------------------------------

    def is_owner(self, member_or_user, guild: Optional[discord.Guild] = None) -> bool:
        user_id = _entity_id(member_or_user)
        if not user_id:
            return False
        if guild is None:
            guild = getattr(member_or_user, "guild", None)
        if guild is not None:
            # Discord's actual guild owner is the sole security authority. A
            # stale OWNER_ID must never gain lock/unlock privileges.
            return user_id == guild.owner_id
        return bool(self.configured_owner_id and user_id == self.configured_owner_id)

    def is_staff(self, member: discord.Member) -> bool:
        if (
            not isinstance(member, discord.Member)
            or member.bot
            or self.is_owner(member, member.guild)
        ):
            return False
        return is_configured_staff(
            (role.id for role in member.roles),
            self.admin_role_id,
            self.moderator_role_id,
        )

    def _staff_roles(self, guild: discord.Guild) -> list[discord.Role]:
        roles = []
        for role_id in (self.admin_role_id, self.moderator_role_id):
            role = guild.get_role(role_id) if role_id else None
            if role and role not in roles:
                roles.append(role)
        return roles

    def _staff_members(self, guild: discord.Guild) -> list[discord.Member]:
        members: dict[int, discord.Member] = {}
        for role in self._staff_roles(guild):
            for member in role.members:
                if not member.bot and not self.is_owner(member, guild):
                    members[member.id] = member
        return list(members.values())

    @staticmethod
    def _permissions_from_names(names: Iterable[str]) -> discord.Permissions:
        permissions = discord.Permissions.none()
        valid = getattr(discord.Permissions, "VALID_FLAGS", {})
        for name in names:
            if name in valid or hasattr(permissions, name):
                try:
                    setattr(permissions, name, True)
                except (AttributeError, TypeError):
                    pass
        permissions.administrator = False
        return permissions

    async def sync_staff_roles(self, guild: discord.Guild) -> tuple[list[str], list[str]]:
        """Remove Administrator and apply explicit Admin/Moderator profiles."""
        changed: list[str] = []
        warnings: list[str] = []
        async with self._role_sync_lock:
            me = guild.me
            if not me:
                return changed, ["Bot member is missing from guild cache."]

            # Administrator bypasses all channel security. Strip it from every
            # editable human role, not only the two configured staff roles.
            for role in guild.roles:
                if role.managed or not role.permissions.administrator:
                    continue
                if not role.is_default() and me.top_role <= role:
                    warnings.append(
                        f"Cannot remove Administrator from {role.name} ({role.id}); bot role is not higher."
                    )
                    continue
                new_permissions = discord.Permissions(role.permissions.value)
                new_permissions.administrator = False
                try:
                    await role.edit(
                        permissions=new_permissions,
                        reason="Owner Security: Administrator is forbidden on @everyone/human roles",
                    )
                    changed.append(f"Removed Administrator from {role.name} ({role.id})")
                except (discord.Forbidden, discord.HTTPException) as exc:
                    warnings.append(f"Failed to clean {role.name} ({role.id}): {exc}")

            desired_profiles = [(self.admin_role_id, "Admin", ADMIN_PERMISSION_NAMES)]
            if self.moderator_role_id == self.admin_role_id and self.admin_role_id:
                warnings.append(
                    f"Admin and Moderator use the same role ID {self.admin_role_id}; "
                    "the safer Admin profile was kept, but the IDs must be separated."
                )
            else:
                desired_profiles.append(
                    (self.moderator_role_id, "Moderator", MODERATOR_PERMISSION_NAMES)
                )
            for role_id, label, names in desired_profiles:
                role = guild.get_role(role_id) if role_id else None
                if not role:
                    warnings.append(f"Configured {label} role is missing (ID {role_id or 0}).")
                    continue
                if role.is_default():
                    warnings.append(
                        f"Configured {label} role ID points to @everyone ({role.id}); profile was not applied."
                    )
                    continue
                if role.managed:
                    warnings.append(f"Configured {label} role is managed and cannot be edited ({role.id}).")
                    continue
                if me.top_role <= role:
                    warnings.append(f"Bot role must be above {label} ({role.name}, {role.id}).")
                    continue
                if label == "Admin":
                    # A real Admin keeps every Discord permission supported by
                    # the installed discord.py version except Administrator,
                    # which would bypass all channel security overwrites.
                    desired = discord.Permissions.all()
                    desired.administrator = False
                else:
                    desired = self._permissions_from_names(names)
                if role.permissions.value != desired.value:
                    try:
                        await role.edit(
                            permissions=desired,
                            reason=f"Owner Security: synchronize {label} granular permissions",
                        )
                        changed.append(f"Synchronized {label} permissions ({role.id})")
                    except (discord.Forbidden, discord.HTTPException) as exc:
                        warnings.append(f"Failed to synchronize {label} ({role.id}): {exc}")

            effective_admins = [
                member
                for member in guild.members
                if not member.bot
                and not self.is_owner(member, guild)
                and member.guild_permissions.administrator
            ]
            if effective_admins:
                warnings.append(
                    "Human members still have effective Administrator: "
                    + ", ".join(f"{m} ({m.id})" for m in effective_admins[:20])
                )

        return changed, warnings

    # ------------------------------------------------------------------
    # Owner-only log channel and DM mirror
    # ------------------------------------------------------------------

    def _log_channel_from_state(self, guild: discord.Guild):
        channel_id = int(self._guild_state(guild.id).get("log_channel_id", 0) or 0)
        channel = guild.get_channel(channel_id) if channel_id else None
        return channel if isinstance(channel, discord.TextChannel) else None

    def _owner_log_overwrites(self, guild: discord.Guild) -> dict:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
        }
        owner = guild.owner
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                manage_messages=True,
            )
        if guild.me:
            overwrites[guild.me] = discord.PermissionOverwrite(
                view_channel=True,
                read_message_history=True,
                send_messages=True,
                embed_links=True,
                attach_files=True,
                manage_messages=True,
                manage_channels=True,
            )
        # @everyone deny + the two staff-role denies keep the overwrite count
        # bounded (Discord channels cap overwrites); per-member entries are not
        # needed after Administrator is removed.
        for target in self._staff_roles(guild):
            overwrites[target] = discord.PermissionOverwrite(
                view_channel=False,
                read_message_history=False,
                send_messages=False,
                manage_messages=False,
                manage_channels=False,
                manage_roles=False,
            )
        return overwrites

    @staticmethod
    def _overwrites_signature(overwrites: dict) -> dict:
        signature = {}
        for target, overwrite in overwrites.items():
            try:
                allow, deny = overwrite.pair()
                signature[int(target.id)] = (allow.value, deny.value)
            except (AttributeError, TypeError, ValueError):
                continue
        return signature

    async def ensure_owner_log_channel(
        self, guild: discord.Guild, *, repair_permissions: bool = False
    ) -> Optional[discord.TextChannel]:
        # 🕵️ Owner stealth: ما كنصاوبو لا كنصلحو حتى قناة أمنية.
        if not OWNER_SECURITY_LOGGING_ENABLED:
            return None
        async with self._log_channel_lock:
            channel = self._log_channel_from_state(guild)
            if channel is None:
                # Reuse only a channel created for this exact purpose.
                channel = discord.utils.find(
                    lambda ch: isinstance(ch, discord.TextChannel)
                    and ch.name == SECURITY_LOG_CHANNEL_NAME
                    and ch.topic == SECURITY_LOG_CHANNEL_TOPIC,
                    guild.channels,
                )
            overwrites = self._owner_log_overwrites(guild)
            if channel is None:
                try:
                    channel = await guild.create_text_channel(
                        SECURITY_LOG_CHANNEL_NAME,
                        topic=SECURITY_LOG_CHANNEL_TOPIC,
                        overwrites=overwrites,
                        reason="Owner Security: create owner-only audit log",
                    )
                except (discord.Forbidden, discord.HTTPException) as exc:
                    print(f"[OWNER-SECURITY] cannot create log channel in {guild.id}: {exc}")
                    return None
                record = self._guild_state(guild.id)
                record["log_channel_id"] = channel.id
                self._save_state()
            else:
                record = self._guild_state(guild.id)
                if int(record.get("log_channel_id", 0) or 0) != channel.id:
                    record["log_channel_id"] = channel.id
                    self._save_state()
                if repair_permissions:
                    needs_repair = (
                        channel.name != SECURITY_LOG_CHANNEL_NAME
                        or channel.topic != SECURITY_LOG_CHANNEL_TOPIC
                        or self._overwrites_signature(channel.overwrites)
                        != self._overwrites_signature(overwrites)
                    )
                    if needs_repair:
                        try:
                            await channel.edit(
                                name=SECURITY_LOG_CHANNEL_NAME,
                                topic=SECURITY_LOG_CHANNEL_TOPIC,
                                overwrites=overwrites,
                                reason="Owner Security: repair owner-only log permissions",
                            )
                        except (discord.Forbidden, discord.HTTPException) as exc:
                            print(f"[OWNER-SECURITY] cannot repair log channel {channel.id}: {exc}")
            return channel

    @staticmethod
    def _entity_text(value) -> str:
        if value is None:
            return "Self / Discord System"
        value_id = _entity_id(value)
        mention = getattr(value, "mention", None)
        name = str(value)
        if mention:
            return f"{mention} • {name} • ID `{value_id}`"
        return f"{name}" + (f" • ID `{value_id}`" if value_id else "")

    def _audit_actor(self, entry, guild: discord.Guild):
        actor = getattr(entry, "user", None)
        if actor is not None:
            return actor
        actor_id = int(getattr(entry, "user_id", 0) or 0)
        if not actor_id:
            return None
        return guild.get_member(actor_id) or self.bot.get_user(actor_id) or discord.Object(id=actor_id)

    async def emit_security_event(
        self,
        guild: discord.Guild,
        title: str,
        details: str,
        *,
        actor=None,
        target=None,
        channel=None,
        reason: Optional[str] = None,
        audit_entry_id: Optional[int] = None,
        color: Optional[discord.Color] = None,
        occurred_at: Optional[datetime] = None,
    ) -> None:
        # 🕵️ Owner stealth: التسجيل مطفي نهائياً — لا قناة لا DM.
        if not OWNER_SECURITY_LOGGING_ENABLED:
            return
        if guild is None:
            return
        occurred_at = occurred_at or _utcnow()
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        unix = int(occurred_at.timestamp())
        embed = discord.Embed(
            title=_clip(title, 256),
            description=_clip(details or "—", 3500),
            color=color or discord.Color.blurple(),
            timestamp=occurred_at,
        )
        embed.add_field(name="Actor", value=_clip(self._entity_text(actor), 1024), inline=False)
        if target is not None:
            embed.add_field(name="Target", value=_clip(self._entity_text(target), 1024), inline=False)
        if channel is not None:
            embed.add_field(name="Channel", value=_clip(self._entity_text(channel), 1024), inline=False)
        if reason:
            embed.add_field(name="Reason", value=_clip(reason, 1024), inline=False)
        id_line = f"Guild `{guild.id}`"
        if audit_entry_id:
            id_line += f" • Audit `{audit_entry_id}`"
        embed.add_field(
            name="Exact time / IDs",
            value=f"<t:{unix}:F> • `{occurred_at.isoformat()}`\n{id_line}",
            inline=False,
        )
        embed.set_footer(text="GGMW9 • Owner Security • owner-only + DM mirror")
        allowed_mentions = discord.AllowedMentions.none()

        log_channel = await self.ensure_owner_log_channel(guild)
        if log_channel:
            try:
                await log_channel.send(embed=embed, allowed_mentions=allowed_mentions)
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[OWNER-SECURITY] log channel send failed in {guild.id}: {exc}")

        owner = guild.owner
        if owner:
            try:
                await owner.send(embed=embed, allowed_mentions=allowed_mentions)
            except (discord.Forbidden, discord.HTTPException):
                # DM privacy settings are controlled by the owner; channel logging
                # remains authoritative and must never fail because DM is closed.
                pass

    def _install_existing_log_mirror(self) -> None:
        # 🕵️ Owner stealth: ما كنعكسو حتى شي حاجة للسجل الأمني.
        if not OWNER_SECURITY_LOGGING_ENABLED:
            return
        shared = runtime_namespace()
        original = shared.get("log_action")
        if not callable(original) or getattr(original, "_owner_security_mirror", False):
            return
        self._original_log_action = original

        async def mirrored_log_action(guild, title: str, description: str, color):
            original_error = None
            try:
                await original(guild, title, description, color)
            except Exception as exc:
                original_error = exc
            try:
                await self.emit_security_event(
                    guild,
                    f"Bot action • {title}",
                    description,
                    actor=self.bot.user,
                    color=color,
                )
            except Exception as exc:
                print(f"[OWNER-SECURITY] bot log mirror failed: {exc}")
            if original_error:
                raise original_error

        mirrored_log_action._owner_security_mirror = True
        self._log_wrapper = mirrored_log_action
        shared["log_action"] = mirrored_log_action
        if hasattr(self.bot, "gg"):
            self.bot.gg["log_action"] = mirrored_log_action

    # ------------------------------------------------------------------
    # TEMP room restrictions and dynamic owner channel shield
    # ------------------------------------------------------------------

    @staticmethod
    def _overwrite_snapshot(overwrite: discord.PermissionOverwrite) -> dict:
        return {
            name: getattr(overwrite, name, None)
            for name in VOICE_SECURITY_PERMISSION_NAMES
        }

    @staticmethod
    def _apply_overwrite_values(overwrite: discord.PermissionOverwrite, values: dict) -> None:
        for name in VOICE_SECURITY_PERMISSION_NAMES:
            setattr(overwrite, name, values.get(name))

    async def _set_sensitive_overwrite(
        self,
        channel,
        target,
        value: bool,
        *,
        reason: str,
    ) -> bool:
        overwrite = channel.overwrites_for(target)
        changed = False
        for name in VOICE_SECURITY_PERMISSION_NAMES:
            if getattr(overwrite, name, None) is not value:
                setattr(overwrite, name, value)
                changed = True
        if not changed:
            return False
        try:
            await channel.set_permissions(target, overwrite=overwrite, reason=reason)
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            print(f"[OWNER-SECURITY] overwrite failed {channel.id}/{getattr(target, 'id', 0)}: {exc}")
            return False

    async def restrict_temp_room(self, channel: discord.VoiceChannel) -> None:
        is_temp = getattr(self.bot, "gg", {}).get("is_temp_voice_channel")
        if not callable(is_temp) or not is_temp(channel):
            return
        targets = [channel.guild.default_role, *self._staff_roles(channel.guild)]
        for target in targets:
            await self._set_sensitive_overwrite(
                channel,
                target,
                False,
                reason="Owner Security: TEMP room human moderation boundary",
            )
        for member in self._staff_members(channel.guild):
            await self._set_sensitive_overwrite(
                channel,
                member,
                False,
                reason="Owner Security: TEMP room staff-specific deny",
            )
        if channel.guild.me:
            await self._set_sensitive_overwrite(
                channel,
                channel.guild.me,
                True,
                reason="Owner Security: TEMP room bot control",
            )

    async def _restore_shield_snapshot(self, guild: discord.Guild, shield: dict) -> bool:
        channel_id = int(shield.get("channel_id", 0) or 0)
        channel = guild.get_channel(channel_id) if channel_id else None
        members = shield.get("members") or {}
        restored = True
        if channel is not None:
            for member_id, values in list(members.items()):
                member = guild.get_member(int(member_id))
                if not member:
                    continue
                overwrite = channel.overwrites_for(member)
                self._apply_overwrite_values(overwrite, values)
                try:
                    await channel.set_permissions(
                        member,
                        overwrite=None if overwrite.is_empty() else overwrite,
                        reason="Owner Security: restore staff voice permissions after Owner left",
                    )
                except (discord.Forbidden, discord.HTTPException) as exc:
                    restored = False
                    print(f"[OWNER-SECURITY] shield restore failed {channel_id}/{member_id}: {exc}")
        return restored

    async def _drain_shield_restore_queue(self, guild: discord.Guild) -> None:
        guild_state = self._guild_state(guild.id)
        queue = list(guild_state.get("owner_shield_restore_queue") or [])
        if not queue:
            return
        remaining = []
        for shield in queue:
            if not isinstance(shield, dict):
                continue
            if not await self._restore_shield_snapshot(guild, shield):
                remaining.append(shield)
        guild_state["owner_shield_restore_queue"] = remaining
        self._save_state()

    def _needs_owner_channel_shield(
        self,
        member: discord.Member,
        channel,
        previous_values: Optional[dict] = None,
    ) -> bool:
        if self.is_owner(member, member.guild) or member == member.guild.me:
            return False
        if self.is_staff(member):
            return True
        permissions = member.guild_permissions
        if permissions.administrator or any(
            getattr(permissions, name, False) for name in VOICE_SECURITY_PERMISSION_NAMES
        ):
            return True
        # Channel role/member overwrites can grant a sensitive permission even
        # when the base guild role does not. Inspect those explicit grants too.
        for role in member.roles:
            overwrite = channel.overwrites_for(role)
            if any(getattr(overwrite, name, None) is True for name in VOICE_SECURITY_PERMISSION_NAMES):
                return True
        member_overwrite = channel.overwrites_for(member)
        if any(
            getattr(member_overwrite, name, None) is True
            for name in VOICE_SECURITY_PERMISSION_NAMES
        ):
            return True
        if previous_values and any(
            previous_values.get(name) is True for name in VOICE_SECURITY_PERMISSION_NAMES
        ):
            return True
        return False

    async def sync_owner_channel_shield(self, guild: discord.Guild) -> None:
        lock = self._owner_shield_locks.setdefault(guild.id, asyncio.Lock())
        async with lock:
            await self._sync_owner_channel_shield_locked(guild)

    async def _sync_owner_channel_shield_locked(self, guild: discord.Guild) -> None:
        owner = guild.owner
        owner_channel = owner.voice.channel if owner and owner.voice else None
        guild_state = self._guild_state(guild.id)
        shield = guild_state.get("owner_shield") or {}
        shield_channel_id = int(shield.get("channel_id", 0) or 0)
        desired_channel_id = int(getattr(owner_channel, "id", 0) or 0)

        if shield_channel_id and shield_channel_id != desired_channel_id:
            queue = guild_state.setdefault("owner_shield_restore_queue", [])
            if not any(
                int(item.get("channel_id", 0) or 0) == shield_channel_id
                for item in queue
                if isinstance(item, dict)
            ):
                queue.append(shield)
            guild_state["owner_shield"] = {}
            shield = {}
        if not owner_channel:
            self._save_state()
            await self._drain_shield_restore_queue(guild)
            return

        members_state = shield.setdefault("members", {})
        shield["channel_id"] = owner_channel.id
        # Put configured Admin/Moderator members first so the highest-risk
        # native controls are denied before broader privileged identities.
        protected_by_id = {str(member.id): member for member in self._staff_members(guild)}
        for member in guild.members:
            previous_values = members_state.get(str(member.id))
            if self._needs_owner_channel_shield(member, owner_channel, previous_values):
                protected_by_id[str(member.id)] = member

        removed_ids = [member_id for member_id in members_state if member_id not in protected_by_id]
        # Snapshot every new target and persist it before the first REST await.
        # Channel-update events triggered by set_permissions will queue behind
        # the per-guild lock and can never overwrite the original tri-state.
        for member_id, member in protected_by_id.items():
            overwrite = owner_channel.overwrites_for(member)
            if member_id not in members_state:
                members_state[member_id] = self._overwrite_snapshot(overwrite)
        guild_state["owner_shield"] = shield
        self._save_state()

        for member_id in removed_ids:
            member = guild.get_member(int(member_id))
            restored = True
            if member:
                overwrite = owner_channel.overwrites_for(member)
                self._apply_overwrite_values(overwrite, members_state[member_id])
                try:
                    await owner_channel.set_permissions(
                        member,
                        overwrite=None if overwrite.is_empty() else overwrite,
                        reason="Owner Security: privileged role removed, restore voice overwrite",
                    )
                except (discord.Forbidden, discord.HTTPException) as exc:
                    restored = False
                    print(
                        f"[OWNER-SECURITY] current shield restore failed "
                        f"{owner_channel.id}/{member_id}: {exc}"
                    )
            if restored:
                members_state.pop(member_id, None)

        for member_id, member in protected_by_id.items():
            overwrite = owner_channel.overwrites_for(member)
            changed = False
            for name in VOICE_SECURITY_PERMISSION_NAMES:
                if getattr(overwrite, name, None) is not False:
                    setattr(overwrite, name, False)
                    changed = True
            if changed:
                try:
                    await owner_channel.set_permissions(
                        member,
                        overwrite=overwrite,
                        reason="Owner Security: nobody may move/mute/deafen the server Owner",
                    )
                except (discord.Forbidden, discord.HTTPException) as exc:
                    print(f"[OWNER-SECURITY] owner shield failed {owner_channel.id}/{member.id}: {exc}")

        guild_state["owner_shield"] = shield
        self._save_state()
        # Destination is now secured; restoring old channels cannot create a
        # protection gap for the Owner.
        await self._drain_shield_restore_queue(guild)

    # ------------------------------------------------------------------
    # Owner mute/deafen locks
    # ------------------------------------------------------------------

    def _voice_lock_record(self, guild_id: int, user_id: int, *, create: bool = True):
        locks = self._guild_state(guild_id).setdefault("voice_locks", {})
        key = str(int(user_id))
        record = locks.get(key)
        if not isinstance(record, dict) and create:
            record = {
                "mute": False,
                "deaf": False,
                "mute_owner_action_at": None,
                "deaf_owner_action_at": None,
                "updated_at": _utcnow().isoformat(),
            }
            locks[key] = record
        elif isinstance(record, dict):
            record.setdefault("mute", False)
            record.setdefault("deaf", False)
            record.setdefault("mute_owner_action_at", None)
            record.setdefault("deaf_owner_action_at", None)
        return record

    @staticmethod
    def _state_datetime(value) -> Optional[datetime]:
        if not value:
            return None
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    def is_owner_voice_locked(self, guild_id: int, user_id: int, field: str = "mute") -> bool:
        record = self._voice_lock_record(guild_id, user_id, create=False) or {}
        return bool(record.get(field, False))

    def prime_owner_voice_lock(
        self,
        guild: discord.Guild,
        actor,
        target,
        *,
        mute: Optional[bool] = None,
        deaf: Optional[bool] = None,
        occurred_at: Optional[datetime] = None,
    ) -> Optional[dict]:
        """Persist an Owner lock before the corresponding Discord API action.

        The synchronous state write closes the gateway race where the voice-state
        event can arrive before the command coroutine resumes after ``member.edit``.
        Call :meth:`finalize_owner_voice_lock` after the API request so a failed
        request restores the exact previous lock state.
        """
        if not self.is_owner(actor, guild) or self.is_owner(target, guild):
            return None
        target_id = _entity_id(target)
        if not target_id:
            return None
        record = self._voice_lock_record(guild.id, target_id)
        requested = {
            name: bool(value)
            for name, value in (("mute", mute), ("deaf", deaf))
            if value is not None
        }
        previous = {name: bool(record.get(name, False)) for name in requested}
        previous_action_times = {
            name: record.get(f"{name}_owner_action_at") for name in requested
        }
        action_time = occurred_at or _utcnow()
        if action_time.tzinfo is None:
            action_time = action_time.replace(tzinfo=timezone.utc)
        action_time_iso = action_time.astimezone(timezone.utc).isoformat()
        changed = [name for name, value in requested.items() if previous[name] != value]
        for name, value in requested.items():
            record[name] = value
            record[f"{name}_owner_action_at"] = action_time_iso
        record["updated_at"] = action_time_iso
        self._save_state()
        return {
            "guild": guild,
            "actor": actor,
            "target": target,
            "target_id": target_id,
            "requested": requested,
            "previous": previous,
            "previous_action_times": previous_action_times,
            "action_time": action_time_iso,
            "changed": changed,
        }

    async def finalize_owner_voice_lock(
        self,
        token: Optional[dict],
        *,
        success: bool,
        source: str = "Owner action",
    ) -> bool:
        if token is None:
            return False
        guild = token["guild"]
        target_id = int(token["target_id"])
        if not success:
            record = self._voice_lock_record(guild.id, target_id)
            # Do not overwrite a newer concurrent Owner choice.
            for name, old_value in token["previous"].items():
                if (
                    bool(record.get(name, False)) == bool(token["requested"][name])
                    and record.get(f"{name}_owner_action_at") == token["action_time"]
                ):
                    record[name] = bool(old_value)
                    record[f"{name}_owner_action_at"] = token["previous_action_times"][name]
            record["updated_at"] = _utcnow().isoformat()
            self._save_state()
            return False
        if not token["changed"]:
            return True
        details = [
            f"{name.title()} lock = {token['requested'][name]}"
            for name in token["changed"]
        ]
        target = token["target"]
        await self.emit_security_event(
            guild,
            "🔐 Owner Voice Lock updated",
            f"{source}\n" + "\n".join(details),
            actor=token["actor"],
            target=target,
            channel=getattr(getattr(target, "voice", None), "channel", None),
            color=discord.Color.gold(),
        )
        return True

    async def record_owner_voice_lock(
        self,
        guild: discord.Guild,
        actor,
        target,
        *,
        mute: Optional[bool] = None,
        deaf: Optional[bool] = None,
        source: str = "Owner action",
        occurred_at: Optional[datetime] = None,
    ) -> bool:
        target_id = _entity_id(target)
        if not target_id:
            return False
        lock = self._voice_lock_action_locks.setdefault((guild.id, target_id), asyncio.Lock())
        async with lock:
            token = self.prime_owner_voice_lock(
                guild,
                actor,
                target,
                mute=mute,
                deaf=deaf,
                occurred_at=occurred_at,
            )
            if token is None:
                return False
            return await self.finalize_owner_voice_lock(token, success=True, source=source)

    async def edit_member_voice_with_owner_lock(
        self,
        guild: discord.Guild,
        actor,
        target: discord.Member,
        *,
        mute: Optional[bool] = None,
        deaf: Optional[bool] = None,
        reason: str,
        source: str,
    ) -> bool:
        """Serialize Owner panel changes from state prime through Discord REST."""
        target_id = _entity_id(target)
        if not target_id:
            return False
        lock = self._voice_lock_action_locks.setdefault((guild.id, target_id), asyncio.Lock())
        async with lock:
            token = self.prime_owner_voice_lock(
                guild,
                actor,
                target,
                mute=mute,
                deaf=deaf,
            )
            kwargs = {"reason": reason}
            if mute is not None:
                kwargs["mute"] = bool(mute)
            if deaf is not None:
                kwargs["deafen"] = bool(deaf)
            voice = getattr(target, "voice", None)
            expected = {}
            if mute is not None and (
                voice is None or bool(getattr(voice, "mute", False)) != bool(mute)
            ):
                expected["mute"] = bool(mute)
            if deaf is not None and (
                voice is None or bool(getattr(voice, "deaf", False)) != bool(deaf)
            ):
                expected["deaf"] = bool(deaf)
            internal_token = (
                self._mark_internal_voice_op(target, **expected) if expected else None
            )
            try:
                await target.edit(**kwargs)
            except Exception:
                self._discard_internal_voice_op(target, internal_token)
                await self.finalize_owner_voice_lock(token, success=False, source=source)
                raise
            await self.finalize_owner_voice_lock(token, success=True, source=source)
            return True

    async def _apply_owner_audit_voice_lock(self, entry, guild: discord.Guild) -> None:
        """Apply native Discord mute/deafen actions authored by the real Owner.

        Voice-state gateway events and audit-log events do not have a guaranteed
        ordering.  This audit path is therefore authoritative when actor
        correlation in ``on_voice_state_update`` arrives too early.
        """
        if getattr(entry, "action", None) != discord.AuditLogAction.member_update:
            return
        actor = self._audit_actor(entry, guild)
        if not self.is_owner(actor, guild):
            return

        target_id = _entity_id(getattr(entry, "target", None))
        if not target_id or target_id == guild.owner_id:
            return
        before = getattr(entry, "before", None)
        after = getattr(entry, "after", None)
        occurred_at = getattr(entry, "created_at", None) or _utcnow()
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        record = self._voice_lock_record(guild.id, target_id)
        updates: dict[str, bool] = {}
        for field in ("mute", "deaf"):
            if not hasattr(after, field):
                continue
            new_value = bool(getattr(after, field))
            old_value = getattr(before, field, None)
            last_owner_action = self._state_datetime(
                record.get(f"{field}_owner_action_at")
            )
            if (
                (old_value is None or bool(old_value) != new_value)
                and (last_owner_action is None or occurred_at > last_owner_action)
            ):
                updates[field] = new_value
        if not updates:
            return

        target = guild.get_member(target_id) or getattr(entry, "target", None)
        if target is None:
            target = discord.Object(id=target_id)
        await self.record_owner_voice_lock(
            guild,
            actor,
            target,
            mute=updates.get("mute"),
            deaf=updates.get("deaf"),
            source=f"Native Discord action • Audit {getattr(entry, 'id', 0)}",
            occurred_at=occurred_at,
        )

        # A delayed audit event can arrive after the fail-closed voice listener
        # temporarily reverted the action. Honour the Owner's exact value now.
        member = guild.get_member(target_id)
        voice = getattr(member, "voice", None) if member else None
        desired_mute = (
            updates["mute"]
            if "mute" in updates and bool(getattr(voice, "mute", False)) != updates["mute"]
            else None
        )
        desired_deaf = (
            updates["deaf"]
            if "deaf" in updates and bool(getattr(voice, "deaf", False)) != updates["deaf"]
            else None
        )
        if member and voice and (desired_mute is not None or desired_deaf is not None):
            await self._edit_voice_state(
                member,
                mute=desired_mute,
                deaf=desired_deaf,
                reason="Owner Security: honour delayed Owner voice-lock audit action",
            )

    async def log_denied_attempt(
        self,
        guild: discord.Guild,
        actor,
        target,
        action: str,
        *,
        channel=None,
        details: str = "",
    ) -> None:
        await self.emit_security_event(
            guild,
            "🛑 Denied owner/security action",
            f"**Blocked action:** {action}\n{details or 'Security policy rejected the action.'}",
            actor=actor,
            target=target,
            channel=channel,
            color=discord.Color.red(),
        )

    async def log_actor_action(
        self,
        guild: discord.Guild,
        actor,
        action: str,
        *,
        target=None,
        channel=None,
        details: str = "",
    ) -> None:
        """Log the human initiator behind a guarded bot panel/command action."""
        await self.emit_security_event(
            guild,
            f"✅ Panel/command • {action}",
            details or "The guarded bot action completed successfully.",
            actor=actor,
            target=target,
            channel=channel,
            color=discord.Color.green(),
        )

    async def edit_member_muted_role(
        self,
        guild: discord.Guild,
        actor,
        target: discord.Member,
        *,
        muted: bool,
        reason: str,
    ) -> bool:
        """Apply the configured Muted role with a one-shot trusted gateway marker."""
        role = guild.get_role(self.muted_role_id) if self.muted_role_id else None
        if not role:
            return False
        channel = target.voice.channel if target.voice else None
        is_temp = getattr(self.bot, "gg", {}).get("is_temp_voice_channel")
        if (
            channel
            and callable(is_temp)
            and is_temp(channel)
            and not self.is_owner(actor, guild)
            and isinstance(actor, discord.Member)
            and self.is_staff(actor)
        ):
            await self.log_denied_attempt(
                guild,
                actor,
                target,
                "Muted-role change inside TEMP",
                channel=channel,
                details="Admin/Moderator Muted-role changes are disabled inside TEMP rooms.",
            )
            return False

        lock = self._muted_role_action_locks.setdefault((guild.id, target.id), asyncio.Lock())
        async with lock:
            currently_muted = role in target.roles
            if currently_muted == bool(muted):
                return True
            token = self._mark_internal_role_op(target, muted=bool(muted))
            try:
                if muted:
                    await target.add_roles(role, reason=reason)
                else:
                    await target.remove_roles(role, reason=reason)
            except Exception:
                self._discard_internal_role_op(target, token)
                raise
            return True

    async def reconcile_owner_voice_locks(self, guild: discord.Guild) -> list[str]:
        """Reapply persisted Owner locks after startup/reconnect."""
        notes: list[str] = []
        protected_owners = {guild.owner.id: guild.owner} if guild.owner else {}
        for owner in protected_owners.values():
            muted_role = guild.get_role(self.muted_role_id) if self.muted_role_id else None
            if muted_role and muted_role in owner.roles:
                token = self._mark_internal_role_op(owner, muted=False)
                try:
                    await owner.remove_roles(
                        muted_role,
                        reason="Owner Security: remove Muted role from protected Owner",
                    )
                    notes.append(f"Removed Muted role from protected Owner {owner} ({owner.id})")
                except (discord.Forbidden, discord.HTTPException) as exc:
                    self._discard_internal_role_op(owner, token)
                    notes.append(
                        f"WARNING: failed to remove Muted role from Owner {owner.id}: {exc}"
                    )
            voice = getattr(owner, "voice", None)
            desired_mute = False if voice and voice.mute else None
            desired_deaf = False if voice and voice.deaf else None
            if voice and voice.channel and (desired_mute is not None or desired_deaf is not None):
                if await self._edit_voice_state(
                    owner,
                    mute=desired_mute,
                    deaf=desired_deaf,
                    reason="Owner Security: clear server mute/deafen from protected Owner",
                ):
                    notes.append(f"Cleared server mute/deafen from protected Owner {owner} ({owner.id})")
        locks = self._guild_state(guild.id).setdefault("voice_locks", {})
        changed_state = False
        for raw_user_id, record in list(locks.items()):
            try:
                user_id = int(raw_user_id)
            except (TypeError, ValueError):
                locks.pop(raw_user_id, None)
                changed_state = True
                continue
            if not isinstance(record, dict):
                locks.pop(raw_user_id, None)
                changed_state = True
                continue
            member = guild.get_member(user_id)
            if member and self.is_owner(member, guild):
                locks.pop(raw_user_id, None)
                changed_state = True
                continue
            if (
                not record.get("mute")
                and not record.get("deaf")
                and not record.get("mute_owner_action_at")
                and not record.get("deaf_owner_action_at")
            ):
                locks.pop(raw_user_id, None)
                changed_state = True
                continue
            voice = getattr(member, "voice", None) if member else None
            if not member or not voice or not voice.channel:
                # Keep the lock: it will be enforced on the member's next join.
                continue
            desired_mute = True if record.get("mute") and not voice.mute else None
            desired_deaf = True if record.get("deaf") and not voice.deaf else None
            if desired_mute is None and desired_deaf is None:
                continue
            if await self._edit_voice_state(
                member,
                mute=desired_mute,
                deaf=desired_deaf,
                reason="Owner Security: restore persisted Owner voice lock",
            ):
                fields = "/".join(
                    name
                    for name, enabled in (("mute", desired_mute), ("deafen", desired_deaf))
                    if enabled
                )
                notes.append(f"Restored {fields} lock for {member} ({member.id})")
        if changed_state:
            self._save_state()
        return notes

    # ------------------------------------------------------------------
    # Audit log mirror and actor correlation
    # ------------------------------------------------------------------

    def _remember_audit(self, entry) -> None:
        entry_id = int(getattr(entry, "id", 0) or 0)
        if not entry_id:
            return
        self._recent_audits.append(entry)

    def _mark_audit_emitted(self, entry_id: int) -> None:
        if entry_id in self._seen_audit_id_set:
            return
        if len(self._seen_audit_ids) == self._seen_audit_ids.maxlen:
            expired = self._seen_audit_ids.popleft()
            self._seen_audit_id_set.discard(expired)
        self._seen_audit_ids.append(entry_id)
        self._seen_audit_id_set.add(entry_id)

    @staticmethod
    def _audit_age_seconds(entry) -> float:
        created = getattr(entry, "created_at", None)
        if not created:
            return 999999.0
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return abs((_utcnow() - created).total_seconds())

    @staticmethod
    def _audit_changes_text(entry) -> str:
        lines = []
        before = getattr(entry, "before", None)
        after = getattr(entry, "after", None)
        keys = set()
        for diff in (before, after):
            try:
                keys.update(name for name, _ in diff)
            except (TypeError, AttributeError):
                keys.update(getattr(diff, "__dict__", {}).keys())
        for key in sorted(keys):
            old = getattr(before, key, "—")
            new = getattr(after, key, "—")
            if old != new:
                lines.append(f"• `{key}`: `{_clip(old, 240)}` → `{_clip(new, 240)}`")
        extra = getattr(entry, "extra", None)
        if extra is not None:
            extra_parts = []
            for name in ("channel", "count", "delete_member_days", "members_removed", "message_id"):
                value = getattr(extra, name, None)
                if value is not None:
                    extra_parts.append(f"{name}={value}")
            if extra_parts:
                lines.append("• extra: " + ", ".join(extra_parts))
        return _clip("\n".join(lines) or "No public change fields were supplied by Discord.", 3000)

    async def _handle_audit_entry(
        self,
        entry,
        *,
        emit: bool = True,
        advance_cursor: bool = False,
    ) -> None:
        async with self._audit_process_lock:
            await self._handle_audit_entry_locked(
                entry,
                emit=emit,
                advance_cursor=advance_cursor,
            )

    async def _handle_audit_entry_locked(
        self,
        entry,
        *,
        emit: bool,
        advance_cursor: bool,
    ) -> None:
        entry_id = int(getattr(entry, "id", 0) or 0)
        already_seen = entry_id in self._seen_audit_id_set
        self._remember_audit(entry)
        guild = getattr(entry, "guild", None)
        if not guild:
            return
        record = self._guild_state(guild.id)
        # Only the ordered REST backfill advances the persistent cursor. Gateway
        # events may arrive ahead of missed entries after reconnect.
        if advance_cursor and entry_id > int(record.get("last_audit_id", 0) or 0):
            record["last_audit_id"] = entry_id
            self._save_state()
        if already_seen:
            return
        if emit or self._audit_age_seconds(entry) <= AUDIT_CACHE_SECONDS:
            try:
                await self._apply_owner_audit_voice_lock(entry, guild)
            except Exception as exc:
                # Audit mirroring must stay alive even if one partial entry cannot be
                # interpreted as a voice lock.
                print(f"[OWNER-SECURITY] native owner voice-lock audit failed: {exc}")
        self._mark_audit_emitted(entry_id)
        if not emit:
            return
        action = getattr(getattr(entry, "action", None), "name", "unknown")
        await self.emit_security_event(
            guild,
            f"📚 Audit • {action.replace('_', ' ').title()}",
            self._audit_changes_text(entry),
            actor=self._audit_actor(entry, guild),
            target=getattr(entry, "target", None),
            channel=getattr(getattr(entry, "extra", None), "channel", None),
            reason=getattr(entry, "reason", None),
            audit_entry_id=entry_id,
            occurred_at=getattr(entry, "created_at", None),
            color=discord.Color.dark_teal(),
        )

    @commands.Cog.listener()
    async def on_audit_log_entry_create(self, entry):
        await self._handle_audit_entry(entry, emit=True, advance_cursor=False)

    @tasks.loop(seconds=15)
    async def audit_backfill_loop(self):
        for guild in list(self.bot.guilds):
            record = self._guild_state(guild.id)
            last_id = int(record.get("last_audit_id", 0) or 0)
            try:
                if not last_id:
                    latest = [entry async for entry in guild.audit_logs(limit=1)]
                    if latest:
                        await self._handle_audit_entry(
                            latest[0],
                            emit=False,
                            advance_cursor=True,
                        )
                    continue
                while True:
                    batch_start = last_id
                    after = discord.Object(id=last_id)
                    entries = [
                        entry
                        async for entry in guild.audit_logs(
                            limit=100,
                            after=after,
                            oldest_first=True,
                        )
                    ]
                    for entry in entries:
                        await self._handle_audit_entry(
                            entry,
                            emit=True,
                            advance_cursor=True,
                        )
                    last_id = int(
                        self._guild_state(guild.id).get("last_audit_id", batch_start) or batch_start
                    )
                    if len(entries) < 100 or last_id <= batch_start:
                        break
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[OWNER-SECURITY] audit backfill failed in {guild.id}: {exc}")

    @audit_backfill_loop.before_loop
    async def before_audit_backfill_loop(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def _entry_target_matches(entry, target_id: Optional[int]) -> bool:
        if target_id is None:
            return True
        return _entity_id(getattr(entry, "target", None)) == int(target_id)

    @staticmethod
    def _entry_destination_matches(entry, destination_id: Optional[int]) -> bool:
        if destination_id is None:
            return True
        extra_channel = getattr(getattr(entry, "extra", None), "channel", None)
        return _entity_id(extra_channel) == int(destination_id)

    def _mark_audit_correlated(self, entry) -> bool:
        """Reserve one audit entry for exactly one gateway-state correlation."""
        entry_id = _entity_id(entry)
        if not entry_id:
            return True
        if entry_id in self._correlated_audit_id_set:
            return False
        if len(self._correlated_audit_ids) == self._correlated_audit_ids.maxlen:
            expired = self._correlated_audit_ids.popleft()
            self._correlated_audit_id_set.discard(expired)
        self._correlated_audit_ids.append(entry_id)
        self._correlated_audit_id_set.add(entry_id)
        return True

    async def _find_recent_audit(
        self,
        guild: discord.Guild,
        actions: set,
        *,
        target_id: Optional[int] = None,
        destination_id: Optional[int] = None,
        expected_changes: Optional[dict] = None,
        expected_role_change: Optional[tuple[int, bool]] = None,
        max_age_seconds: float = AUDIT_CACHE_SECONDS,
        allow_fetch: bool = True,
    ):
        def match(entry):
            entry_id = _entity_id(entry)
            base_match = (
                getattr(entry, "action", None) in actions
                and (not entry_id or entry_id not in self._correlated_audit_id_set)
                and self._audit_age_seconds(entry) <= max_age_seconds
                and self._entry_target_matches(entry, target_id)
                and self._entry_destination_matches(entry, destination_id)
            )
            if not base_match:
                return False
            for name, expected in (expected_changes or {}).items():
                if not hasattr(getattr(entry, "after", None), name):
                    return False
                if bool(getattr(entry.after, name)) != bool(expected):
                    return False
            if expected_role_change is not None:
                role_id, role_added = expected_role_change
                role_diff = getattr(
                    getattr(entry, "after" if role_added else "before", None),
                    "roles",
                    None,
                )
                if role_diff is None:
                    return False
                try:
                    changed_role_ids = {_entity_id(role) for role in role_diff}
                except TypeError:
                    return False
                if int(role_id) not in changed_role_ids:
                    return False
            return True

        for entry in reversed(self._recent_audits):
            if getattr(entry, "guild", None) == guild and match(entry):
                if self._mark_audit_correlated(entry):
                    return entry

        if not allow_fetch:
            return None

        async with self._audit_fetch_lock:
            for delay in (0.35, 0.8):
                await asyncio.sleep(delay)
                try:
                    entries = [entry async for entry in guild.audit_logs(limit=15)]
                except (discord.Forbidden, discord.HTTPException):
                    return None
                for entry in entries:
                    self._remember_audit(entry)
                    if match(entry) and self._mark_audit_correlated(entry):
                        return entry
        return None

    # ------------------------------------------------------------------
    # Voice enforcement and detailed movement logs
    # ------------------------------------------------------------------

    def _mark_internal_voice_op(self, member: discord.Member, **expected) -> dict:
        key = (member.guild.id, member.id)
        expected["expires"] = time.monotonic() + 10
        self._internal_voice_ops.setdefault(key, []).append(expected)
        return expected

    def _discard_internal_voice_op(self, member: discord.Member, token: Optional[dict]) -> None:
        if token is None:
            return
        key = (member.guild.id, member.id)
        records = self._internal_voice_ops.get(key, [])
        records = [record for record in records if record is not token]
        if records:
            self._internal_voice_ops[key] = records
        else:
            self._internal_voice_ops.pop(key, None)

    def _consume_internal_voice_op(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> bool:
        key = (member.guild.id, member.id)
        now = time.monotonic()
        records = [x for x in self._internal_voice_ops.get(key, []) if x.get("expires", 0) > now]
        matched = False
        keep = []
        after_channel_id = _entity_id(after.channel)
        for record in records:
            checks = []
            if "mute" in record:
                checks.append(
                    bool(before.mute) != bool(after.mute)
                    and bool(after.mute) == bool(record["mute"])
                )
            if "deaf" in record:
                checks.append(
                    bool(before.deaf) != bool(after.deaf)
                    and bool(after.deaf) == bool(record["deaf"])
                )
            if "channel_id" in record:
                checks.append(
                    before.channel != after.channel
                    and after_channel_id == record["channel_id"]
                )
            if checks and all(checks) and not matched:
                matched = True
            else:
                keep.append(record)
        if keep:
            self._internal_voice_ops[key] = keep
        else:
            self._internal_voice_ops.pop(key, None)
        return matched

    async def _edit_voice_state(
        self,
        member: discord.Member,
        *,
        mute: Optional[bool] = None,
        deaf: Optional[bool] = None,
        reason: str,
    ) -> bool:
        expected = {}
        kwargs = {"reason": reason}
        if mute is not None:
            expected["mute"] = bool(mute)
            kwargs["mute"] = bool(mute)
        if deaf is not None:
            expected["deaf"] = bool(deaf)
            kwargs["deafen"] = bool(deaf)
        token = self._mark_internal_voice_op(member, **expected)
        try:
            await member.edit(**kwargs)
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            self._discard_internal_voice_op(member, token)
            print(f"[OWNER-SECURITY] voice state repair failed for {member.id}: {exc}")
            return False

    async def _move_member_back(
        self, member: discord.Member, channel, *, reason: str
    ) -> bool:
        if channel is None or not member.voice or not member.voice.channel:
            return False
        token = self._mark_internal_voice_op(member, channel_id=channel.id)
        try:
            await member.move_to(channel, reason=reason)
            return True
        except (discord.Forbidden, discord.HTTPException) as exc:
            self._discard_internal_voice_op(member, token)
            print(f"[OWNER-SECURITY] move repair failed for {member.id}: {exc}")
            return False

    async def _resolve_voice_actor(self, member, before, after, *, allow_fetch: bool = True):
        guild = member.guild
        if bool(before.mute) != bool(after.mute) or bool(before.deaf) != bool(after.deaf):
            expected_changes = {}
            if bool(before.mute) != bool(after.mute):
                expected_changes["mute"] = bool(after.mute)
            if bool(before.deaf) != bool(after.deaf):
                expected_changes["deaf"] = bool(after.deaf)
            return await self._find_recent_audit(
                guild,
                {discord.AuditLogAction.member_update},
                target_id=member.id,
                expected_changes=expected_changes,
                max_age_seconds=8,
                allow_fetch=allow_fetch,
            )
        # MEMBER_MOVE/MEMBER_DISCONNECT audit records do not carry a reliable
        # target ID. The separate audit mirror records their actor/channel/count;
        # guessing here could misattribute a voluntary move and trigger a false
        # security action.
        return None

    @commands.Cog.listener()
    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ):
        channel_changed = before.channel != after.channel
        server_state_changed = (
            bool(before.mute) != bool(after.mute)
            or bool(before.deaf) != bool(after.deaf)
        )
        visible_change = channel_changed or server_state_changed or any(
            getattr(before, name, None) != getattr(after, name, None)
            for name in ("self_mute", "self_deaf", "self_stream", "self_video", "suppress")
        )
        if not visible_change:
            return

        # Permission pre-emption is the only reliable protection against a
        # Discord "Disconnect" action (a bot cannot reconnect a user). Secure
        # the Owner's destination before waiting for audit-log correlation.
        if channel_changed and self.is_owner(member, member.guild):
            await self.sync_owner_channel_shield(member.guild)

        internal = self._consume_internal_voice_op(member, before, after)
        existing_lock = self._voice_lock_record(member.guild.id, member.id, create=False) or {}
        locked_clear = (
            bool(existing_lock.get("mute")) and bool(before.mute) and not bool(after.mute)
        ) or (
            bool(existing_lock.get("deaf")) and bool(before.deaf) and not bool(after.deaf)
        )
        if (
            internal
            or locked_clear
            or (self.is_owner(member, member.guild) and server_state_changed)
        ):
            audit_entry = None
        else:
            # An active Owner lock is re-applied immediately. If this was the
            # Owner's own native clear, the authoritative audit listener clears
            # it and restores False as soon as Discord supplies the entry.
            audit_entry = await self._resolve_voice_actor(
                member,
                before,
                after,
                allow_fetch=True,
            )
        actor = self.bot.user if internal else (
            self._audit_actor(audit_entry, member.guild) if audit_entry else None
        )
        actor_is_owner = self.is_owner(actor, member.guild)
        actor_is_this_bot = bool(self.bot.user and _entity_id(actor) == self.bot.user.id)
        is_temp = getattr(self.bot, "gg", {}).get("is_temp_voice_channel")
        before_temp = bool(callable(is_temp) and is_temp(before.channel))
        after_temp = bool(callable(is_temp) and is_temp(after.channel))
        enforcement_notes = []

        # The server owner is never a valid target for server mute/deafen.
        desired_mute = None
        desired_deaf = None
        if self.is_owner(member, member.guild) and server_state_changed:
            if after.mute:
                desired_mute = False
            if after.deaf:
                desired_deaf = False
            if desired_mute is not None or desired_deaf is not None:
                enforcement_notes.append("Removed an unauthorized server mute/deafen from Owner.")

        # In TEMP rooms only the real Owner or this bot's guarded panel may perform
        # a server mute/deafen. Unknown actors fail closed.
        active_temp = after.channel if after_temp else before.channel if before_temp else None
        if server_state_changed and active_temp and not self.is_owner(member, member.guild):
            if not actor_is_owner and not actor_is_this_bot:
                if bool(before.mute) != bool(after.mute):
                    desired_mute = bool(before.mute)
                if bool(before.deaf) != bool(after.deaf):
                    desired_deaf = bool(before.deaf)
                enforcement_notes.append("Reverted unauthorized TEMP room mute/deafen.")

        # Owner-authored locks are global and survive disconnects/restarts.
        if not self.is_owner(member, member.guild):
            record = self._voice_lock_record(member.guild.id, member.id)
            if bool(before.mute) != bool(after.mute):
                new_lock, reapply = resolve_owner_voice_lock(
                    bool(record.get("mute")),
                    bool(before.mute),
                    bool(after.mute),
                    actor_is_owner=actor_is_owner,
                )
                record["mute"] = new_lock
                if actor_is_owner:
                    owner_action_at = getattr(audit_entry, "created_at", None) or _utcnow()
                    if owner_action_at.tzinfo is None:
                        owner_action_at = owner_action_at.replace(tzinfo=timezone.utc)
                    record["mute_owner_action_at"] = owner_action_at.isoformat()
                if reapply:
                    desired_mute = True
                    enforcement_notes.append("Reapplied Owner's Mute lock.")
            if bool(before.deaf) != bool(after.deaf):
                new_lock, reapply = resolve_owner_voice_lock(
                    bool(record.get("deaf")),
                    bool(before.deaf),
                    bool(after.deaf),
                    actor_is_owner=actor_is_owner,
                )
                record["deaf"] = new_lock
                if actor_is_owner:
                    owner_action_at = getattr(audit_entry, "created_at", None) or _utcnow()
                    if owner_action_at.tzinfo is None:
                        owner_action_at = owner_action_at.replace(tzinfo=timezone.utc)
                    record["deaf_owner_action_at"] = owner_action_at.isoformat()
                if reapply:
                    desired_deaf = True
                    enforcement_notes.append("Reapplied Owner's Deafen lock.")
            if after.channel:
                if record.get("mute") and not after.mute and desired_mute is None:
                    desired_mute = True
                    enforcement_notes.append("Applied persisted Owner Mute lock on voice join.")
                if record.get("deaf") and not after.deaf and desired_deaf is None:
                    desired_deaf = True
                    enforcement_notes.append("Applied persisted Owner Deafen lock on voice join.")
            record["updated_at"] = _utcnow().isoformat()
            if (
                not record.get("mute")
                and not record.get("deaf")
                and not record.get("mute_owner_action_at")
                and not record.get("deaf_owner_action_at")
            ):
                self._guild_state(member.guild.id)["voice_locks"].pop(str(member.id), None)
            self._save_state()

        if after.channel and (desired_mute is not None or desired_deaf is not None):
            await self._edit_voice_state(
                member,
                mute=desired_mute,
                deaf=desired_deaf,
                reason="Owner Security: restore protected voice state",
            )

        changes = []
        if channel_changed:
            changes.append(
                f"Channel: {self._entity_text(before.channel)} → {self._entity_text(after.channel)}"
            )
        for name, label in (
            ("mute", "Server mute"),
            ("deaf", "Server deafen"),
            ("self_mute", "Self mute"),
            ("self_deaf", "Self deafen"),
            ("self_stream", "Stream"),
            ("self_video", "Camera"),
            ("suppress", "Stage suppress"),
        ):
            old = getattr(before, name, None)
            new = getattr(after, name, None)
            if old != new:
                changes.append(f"{label}: `{old}` → `{new}`")
        changes.extend(f"SECURITY: {note}" for note in enforcement_notes)
        await self.emit_security_event(
            member.guild,
            "🎙️ Voice state activity",
            "\n".join(changes),
            actor=actor,
            target=member,
            channel=after.channel or before.channel,
            audit_entry_id=_entity_id(audit_entry),
            reason=getattr(audit_entry, "reason", None) if audit_entry else None,
            color=discord.Color.red() if enforcement_notes else discord.Color.blue(),
        )

    # ------------------------------------------------------------------
    # Other non-audit activity and self-healing listeners
    # ------------------------------------------------------------------

    async def _startup_sync(self, guild: discord.Guild) -> None:
        changed, warnings = await self.sync_staff_roles(guild)
        if self.configured_owner_id and self.configured_owner_id != guild.owner_id:
            warnings.append(
                f"Configured OWNER_ID {self.configured_owner_id} does not match Discord guild owner {guild.owner_id}."
            )
        if guild.me:
            required_bot_permissions = {
                "view_audit_log": "View Audit Log",
                "manage_roles": "Manage Roles",
                "manage_channels": "Manage Channels",
                "move_members": "Move Members",
                "mute_members": "Mute Members",
                "deafen_members": "Deafen Members",
                "moderate_members": "Moderate Members",
            }
            missing = [
                label
                for name, label in required_bot_permissions.items()
                if not getattr(guild.me.guild_permissions, name, False)
            ]
            if missing:
                warnings.append("Bot is missing required permissions: " + ", ".join(missing))
        privileged_bots = [
            member
            for member in guild.members
            if member.bot
            and member != guild.me
            and member.guild_permissions.administrator
        ]
        if privileged_bots:
            warnings.append(
                "Other bots still have Administrator and can bypass hidden-channel overwrites: "
                + ", ".join(f"{member} ({member.id})" for member in privileged_bots[:20])
            )
        await self.ensure_owner_log_channel(guild, repair_permissions=True)
        changed.extend(await self.reconcile_owner_voice_locks(guild))
        await self.sync_owner_channel_shield(guild)
        is_temp = getattr(self.bot, "gg", {}).get("is_temp_voice_channel")
        if callable(is_temp):
            for channel in guild.voice_channels:
                if is_temp(channel):
                    await self.restrict_temp_room(channel)
        if changed or warnings:
            await self.emit_security_event(
                guild,
                "🛡️ Owner Security startup reconciliation",
                "**Changed**\n"
                + ("\n".join(f"• {item}" for item in changed) or "• Nothing")
                + "\n\n**Warnings**\n"
                + ("\n".join(f"• {item}" for item in warnings) or "• None"),
                actor=self.bot.user,
                target=guild.owner,
                color=discord.Color.orange() if warnings else discord.Color.green(),
            )
        self._startup_complete.add(guild.id)

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in list(self.bot.guilds):
            try:
                await self._startup_sync(guild)
            except Exception as exc:
                print(f"[OWNER-SECURITY] startup sync failed for {guild.id}: {exc}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await self.emit_security_event(
            member.guild,
            "📥 Member joined",
            f"Account created: <t:{int(member.created_at.timestamp())}:F>",
            target=member,
            color=discord.Color.green(),
        )

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        await self.emit_security_event(
            member.guild,
            "📤 Member left / was removed",
            "The audit mirror identifies a moderator separately when this was a kick or ban. "
            "Any Owner voice lock is retained and will apply if this account rejoins.",
            target=member,
            color=discord.Color.orange(),
        )

    def _mark_internal_role_op(self, member: discord.Member, *, muted: bool) -> dict:
        key = (member.guild.id, member.id)
        token = {"muted": bool(muted), "expires": time.monotonic() + 10}
        self._internal_role_ops.setdefault(key, []).append(token)
        return token

    def _discard_internal_role_op(self, member: discord.Member, token: Optional[dict]) -> None:
        if token is None:
            return
        key = (member.guild.id, member.id)
        records = [record for record in self._internal_role_ops.get(key, []) if record is not token]
        if records:
            self._internal_role_ops[key] = records
        else:
            self._internal_role_ops.pop(key, None)

    def _consume_internal_role_op(self, member: discord.Member, *, muted: bool) -> bool:
        key = (member.guild.id, member.id)
        now = time.monotonic()
        records = [
            record
            for record in self._internal_role_ops.get(key, [])
            if record.get("expires", 0) > now
        ]
        matched = False
        keep = []
        for record in records:
            if not matched and bool(record.get("muted")) == bool(muted):
                matched = True
            else:
                keep.append(record)
        if keep:
            self._internal_role_ops[key] = keep
        else:
            self._internal_role_ops.pop(key, None)
        return matched

    async def _guard_owner_muted_role_change(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> bool:
        """Never allow the configured Muted role to remain on the real Owner."""
        if not self.muted_role_id or not self.is_owner(after, after.guild):
            return False
        before_has = any(role.id == self.muted_role_id for role in before.roles)
        after_has = any(role.id == self.muted_role_id for role in after.roles)
        if before_has == after_has:
            return False
        if self._consume_internal_role_op(after, muted=after_has):
            return True
        if not after_has:
            return False
        muted_role = after.guild.get_role(self.muted_role_id)
        if not muted_role:
            return False

        token = self._mark_internal_role_op(after, muted=False)
        try:
            await after.remove_roles(
                muted_role,
                reason="Owner Security: Owner cannot receive the Muted role",
            )
        except (discord.Forbidden, discord.HTTPException) as exc:
            self._discard_internal_role_op(after, token)
            await self.log_denied_attempt(
                after.guild,
                None,
                after,
                "Apply Muted role to Owner (reversal failed)",
                details=str(exc),
            )
            return True

        entry = await self._find_recent_audit(
            after.guild,
            {discord.AuditLogAction.member_role_update},
            target_id=after.id,
            expected_role_change=(self.muted_role_id, True),
            max_age_seconds=8,
        )
        actor = self._audit_actor(entry, after.guild) if entry else None
        await self.log_denied_attempt(
            after.guild,
            actor,
            after,
            "Apply Muted role to Owner",
            details="The Muted role was removed automatically; the real Server Owner is protected.",
        )
        return True

    async def _guard_temp_muted_role_change(
        self,
        before: discord.Member,
        after: discord.Member,
    ) -> None:
        if not self.muted_role_id:
            return
        before_has = any(role.id == self.muted_role_id for role in before.roles)
        after_has = any(role.id == self.muted_role_id for role in after.roles)
        if before_has == after_has:
            return
        if self._consume_internal_role_op(after, muted=after_has):
            return
        channel = after.voice.channel if after.voice else None
        is_temp = getattr(self.bot, "gg", {}).get("is_temp_voice_channel")
        if not channel or not callable(is_temp) or not is_temp(channel):
            return
        entry = await self._find_recent_audit(
            after.guild,
            {discord.AuditLogAction.member_role_update},
            target_id=after.id,
            expected_role_change=(self.muted_role_id, after_has),
            max_age_seconds=8,
        )
        actor = self._audit_actor(entry, after.guild) if entry else None
        if self.is_owner(actor, after.guild):
            return
        muted_role = after.guild.get_role(self.muted_role_id)
        if not muted_role:
            return
        internal_token = self._mark_internal_role_op(after, muted=before_has)
        try:
            if before_has:
                await after.add_roles(
                    muted_role,
                    reason="Owner Security: restore TEMP Muted role removed by staff",
                )
                action = "Remove Muted role inside TEMP"
            else:
                await after.remove_roles(
                    muted_role,
                    reason="Owner Security: remove TEMP Muted role added by staff",
                )
                action = "Add Muted role inside TEMP"
        except (discord.Forbidden, discord.HTTPException) as exc:
            self._discard_internal_role_op(after, internal_token)
            await self.log_denied_attempt(
                after.guild,
                actor,
                after,
                "TEMP Muted-role change (reversal failed)",
                channel=channel,
                details=str(exc),
            )
            return
        await self.log_denied_attempt(
            after.guild,
            actor,
            after,
            action,
            channel=channel,
            details=(
                "The unauthorized role change was reverted automatically."
                if actor is not None
                else "Discord did not provide a trustworthy actor in time; TEMP security failed closed and reverted it."
            ),
        )

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        owner_role_handled = await self._guard_owner_muted_role_change(before, after)
        if not owner_role_handled:
            await self._guard_temp_muted_role_change(before, after)
        if self.is_owner(after, after.guild):
            before_timeout = getattr(before, "timed_out_until", None)
            after_timeout = getattr(after, "timed_out_until", None)
            if after_timeout and before_timeout != after_timeout:
                try:
                    await after.timeout(None, reason="Owner Security: Owner cannot be timed out")
                except (discord.Forbidden, discord.HTTPException):
                    pass
                await self.log_denied_attempt(
                    after.guild,
                    None,
                    after,
                    "Timeout Owner",
                    details="The timeout was removed automatically.",
                )
        if before.roles != after.roles:
            await self.sync_staff_roles(after.guild)
            await self.sync_owner_channel_shield(after.guild)
            if self.is_staff(after):
                is_temp = getattr(self.bot, "gg", {}).get("is_temp_voice_channel")
                if callable(is_temp):
                    for channel in after.guild.voice_channels:
                        if is_temp(channel):
                            await self._set_sensitive_overwrite(
                                channel,
                                after,
                                False,
                                reason="Owner Security: staff role update in TEMP rooms",
                            )

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if (
            after.id in {self.admin_role_id, self.moderator_role_id}
            or after.permissions.administrator
        ):
            changed, warnings = await self.sync_staff_roles(after.guild)
            if changed or warnings:
                await self.emit_security_event(
                    after.guild,
                    "🛡️ Staff role security repair",
                    "\n".join([*(f"• {x}" for x in changed), *(f"⚠️ {x}" for x in warnings)]),
                    actor=self.bot.user,
                    target=after,
                    color=discord.Color.orange() if warnings else discord.Color.green(),
                )
        await self.sync_owner_channel_shield(after.guild)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        if role.permissions.administrator:
            changed, warnings = await self.sync_staff_roles(role.guild)
            await self.emit_security_event(
                role.guild,
                "🛡️ New Administrator role security repair",
                "\n".join([*(f"• {x}" for x in changed), *(f"⚠️ {x}" for x in warnings)])
                or "Administrator was reviewed; no editable change was available.",
                actor=self.bot.user,
                target=role,
                color=discord.Color.orange() if warnings else discord.Color.green(),
            )
        await self.sync_owner_channel_shield(role.guild)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if _entity_id(after) == int(self._guild_state(after.guild.id).get("log_channel_id", 0) or 0):
            await self.ensure_owner_log_channel(after.guild, repair_permissions=True)
        is_temp = getattr(self.bot, "gg", {}).get("is_temp_voice_channel")
        if isinstance(after, discord.VoiceChannel) and callable(is_temp) and is_temp(after):
            await self.restrict_temp_room(after)
        owner = after.guild.owner
        if owner and owner.voice and owner.voice.channel == after:
            await self.sync_owner_channel_shield(after.guild)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        record = self._guild_state(channel.guild.id)
        if channel.id == int(record.get("log_channel_id", 0) or 0):
            record["log_channel_id"] = 0
            self._save_state()
            await self.ensure_owner_log_channel(channel.guild, repair_permissions=True)

    def _is_security_log_channel(self, channel) -> bool:
        guild = getattr(channel, "guild", None)
        if not guild:
            return False
        return channel.id == int(self._guild_state(guild.id).get("log_channel_id", 0) or 0)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if not message.guild or self._is_security_log_channel(message.channel):
            return
        await self.emit_security_event(
            message.guild,
            "🗑️ Message deleted",
            f"Content: {_clip(message.content or '[no text]', 1800)}\nAttachments: {len(message.attachments)}\nMessage ID: `{message.id}`",
            target=message.author,
            channel=message.channel,
            color=discord.Color.orange(),
        )

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if (
            not before.guild
            or self._is_security_log_channel(before.channel)
            or before.content == after.content
        ):
            return
        await self.emit_security_event(
            before.guild,
            "✏️ Message edited",
            f"Before: {_clip(before.content or '[no text]', 1300)}\nAfter: {_clip(after.content or '[no text]', 1300)}\nMessage ID: `{before.id}`",
            target=before.author,
            channel=before.channel,
            color=discord.Color.gold(),
        )

    @commands.Cog.listener()
    async def on_bulk_message_delete(self, messages):
        messages = list(messages)
        if not messages or not messages[0].guild or self._is_security_log_channel(messages[0].channel):
            return
        ids = ", ".join(str(message.id) for message in messages[:50])
        await self.emit_security_event(
            messages[0].guild,
            "🧹 Bulk message delete",
            f"Count: {len(messages)}\nMessage IDs: `{_clip(ids, 2500)}`",
            channel=messages[0].channel,
            color=discord.Color.red(),
        )

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if payload.cached_message is not None or payload.guild_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id) if guild else None
        if not guild or self._is_security_log_channel(channel):
            return
        await self.emit_security_event(
            guild,
            "🗑️ Uncached message deleted",
            f"Message ID: `{payload.message_id}`\nContent was not present in Discord.py's message cache.",
            channel=channel,
            color=discord.Color.orange(),
        )

    @commands.Cog.listener()
    async def on_raw_message_edit(self, payload: discord.RawMessageUpdateEvent):
        if payload.cached_message is not None or payload.guild_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id) if guild else None
        if not guild or self._is_security_log_channel(channel):
            return
        content = payload.data.get("content", "[content unavailable in partial gateway payload]")
        author_id = int((payload.data.get("author") or {}).get("id", 0) or 0)
        target = guild.get_member(author_id) or (discord.Object(id=author_id) if author_id else None)
        await self.emit_security_event(
            guild,
            "✏️ Uncached message edited",
            f"New/partial content: {_clip(content, 1800)}\nMessage ID: `{payload.message_id}`",
            target=target,
            channel=channel,
            color=discord.Color.gold(),
        )

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload: discord.RawBulkMessageDeleteEvent):
        if payload.guild_id is None:
            return
        guild = self.bot.get_guild(payload.guild_id)
        channel = guild.get_channel(payload.channel_id) if guild else None
        if not guild or self._is_security_log_channel(channel):
            return
        cached_ids = {message.id for message in getattr(payload, "cached_messages", [])}
        missing_ids = sorted(set(payload.message_ids).difference(cached_ids))
        if not missing_ids:
            return
        rendered = ", ".join(str(message_id) for message_id in missing_ids[:100])
        await self.emit_security_event(
            guild,
            "🧹 Uncached bulk message delete",
            f"Uncached count: {len(missing_ids)}\nMessage IDs: `{_clip(rendered, 2800)}`",
            channel=channel,
            color=discord.Color.red(),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(OwnerSecurity(bot))
    print("✅ Owner Security: locked voice states + owner-only logs + staff permission sync")
