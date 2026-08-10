# -*- coding: utf-8 -*-
"""Pure policy constants/helpers for the GGMW9 owner security system.

This module deliberately does not import discord.py so the critical permission and
voice-lock rules can be tested offline.
"""

from __future__ import annotations


COMMON_STAFF_PERMISSIONS = frozenset({
    "add_reactions",
    "attach_files",
    "change_nickname",
    "connect",
    "create_instant_invite",
    "embed_links",
    "external_emojis",
    "priority_speaker",
    "read_message_history",
    "request_to_speak",
    "send_messages",
    "send_polls",
    "send_tts_messages",
    "send_voice_messages",
    "speak",
    "stream",
    "use_application_commands",
    "use_embedded_activities",
    "use_external_emojis",
    "use_external_stickers",
    "use_soundboard",
    "use_voice_activation",
    "view_channel",
})


ADMIN_PERMISSION_NAMES = COMMON_STAFF_PERMISSIONS | frozenset({
    "ban_members",
    "create_private_threads",
    "create_public_threads",
    "deafen_members",
    "kick_members",
    "manage_channels",
    "manage_emojis_and_stickers",
    "manage_events",
    "manage_guild",
    "manage_messages",
    "manage_nicknames",
    "manage_roles",
    "manage_threads",
    "manage_webhooks",
    "moderate_members",
    "move_members",
    "mute_members",
    "send_messages_in_threads",
    "view_audit_log",
})


MODERATOR_PERMISSION_NAMES = COMMON_STAFF_PERMISSIONS | frozenset({
    "deafen_members",
    "kick_members",
    "manage_messages",
    "manage_nicknames",
    "manage_threads",
    "moderate_members",
    "move_members",
    "mute_members",
    "send_messages_in_threads",
    "view_audit_log",
})


# These are denied for human staff in every TEMP room and in the channel currently
# occupied by the server owner.  The bot performs TEMP panel actions on their behalf.
VOICE_SECURITY_PERMISSION_NAMES = (
    "manage_channels",
    "manage_roles",
    "move_members",
    "mute_members",
    "deafen_members",
)


def resolve_owner_voice_lock(
    locked: bool,
    before_state: bool,
    after_state: bool,
    *,
    actor_is_owner: bool,
) -> tuple[bool, bool]:
    """Return ``(new_lock, must_reapply)`` for one mute/deafen field.

    The real owner creates or clears a lock by changing the state.  Everyone else
    may change an unlocked state, but cannot clear an active owner lock.
    """
    locked = bool(locked)
    before_state = bool(before_state)
    after_state = bool(after_state)

    if actor_is_owner and before_state != after_state:
        return after_state, False
    if locked and not after_state:
        return True, True
    return locked, False


def is_configured_staff(role_ids, admin_role_id: int, moderator_role_id: int) -> bool:
    wanted = {int(x) for x in (admin_role_id, moderator_role_id) if int(x or 0)}
    present = {int(x) for x in role_ids}
    return bool(wanted.intersection(present))
