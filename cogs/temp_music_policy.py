# -*- coding: utf-8 -*-
"""Pure policy for the Temp Room music-bot pool.

This module deliberately has no discord.py dependency so the ordering and cleanup
rules can be tested offline.
"""

from __future__ import annotations

from typing import NamedTuple, Optional


class TempMusicBotProfile(NamedTuple):
    user_id: int
    name: str
    provider: str
    commands_url: str
    dashboard_url: str
    join_hint: str
    play_hint: str


# First five active Temp Rooms receive the first free entry in this exact order.
TEMP_MUSIC_BOT_POOL = (
    TempMusicBotProfile(
        1241477316891250789,
        "SeshTunes",
        "seshtunes",
        "https://seshtunes.com/commands",
        "https://seshtunes.com/dashboard/seshtunes",
        "/join",
        "/play أو /player",
    ),
    TempMusicBotProfile(
        411916947773587456,
        "Jockie Music",
        "jockie",
        "https://www.jockiemusic.com/commands",
        "https://dashboard.jockiemusic.com/",
        "m!join",
        "m!play اسم الأغنية",
    ),
    TempMusicBotProfile(
        412347257233604609,
        "Jockie Music (1)",
        "jockie",
        "https://www.jockiemusic.com/commands",
        "https://dashboard.jockiemusic.com/",
        "m!join",
        "m!play اسم الأغنية",
    ),
    TempMusicBotProfile(
        412347553141751808,
        "Jockie Music (2)",
        "jockie",
        "https://www.jockiemusic.com/commands",
        "https://dashboard.jockiemusic.com/",
        "m!join",
        "m!play اسم الأغنية",
    ),
    TempMusicBotProfile(
        412347780841865216,
        "Jockie Music (3)",
        "jockie",
        "https://www.jockiemusic.com/commands",
        "https://dashboard.jockiemusic.com/",
        "m!join",
        "m!play اسم الأغنية",
    ),
)

TEMP_MUSIC_BOT_IDS = tuple(profile.user_id for profile in TEMP_MUSIC_BOT_POOL)
TEMP_ROOM_EMPTY_GRACE_SECONDS = 5
TEMP_ROOM_HOUSEKEEPING_SECONDS = 30
TEMP_ROOM_ORPHAN_MIN_AGE_SECONDS = 30


def normalize_music_bot_id(value) -> Optional[int]:
    try:
        value = int(value)
    except (TypeError, ValueError):
        return None
    return value if value in TEMP_MUSIC_BOT_IDS else None


def get_music_bot_profile(value) -> Optional[TempMusicBotProfile]:
    bot_id = normalize_music_bot_id(value)
    if bot_id is None:
        return None
    return next(profile for profile in TEMP_MUSIC_BOT_POOL if profile.user_id == bot_id)


def choose_next_music_bot_id(assigned_ids) -> Optional[int]:
    used = {
        bot_id
        for bot_id in (normalize_music_bot_id(value) for value in assigned_ids)
        if bot_id is not None
    }
    for profile in TEMP_MUSIC_BOT_POOL:
        if profile.user_id not in used:
            return profile.user_id
    return None


def plan_music_bot_leases(room_states) -> dict:
    """Return stable room -> bot leases without reshuffling existing valid rooms.

    Each state is ``(room_id, eligible, current_bot_id, wait_order)``.  Duplicate
    or invalid leases are repaired deterministically; free bots go to the oldest
    waiting eligible room.  Ineligible rooms always receive ``None``.
    """
    normalized = []
    for room_id, eligible, current_bot_id, wait_order in room_states:
        try:
            order = int(wait_order or 0)
        except (TypeError, ValueError):
            order = 0
        try:
            tie_breaker = (0, int(room_id))
        except (TypeError, ValueError):
            tie_breaker = (1, str(room_id))
        normalized.append((order, tie_breaker, room_id, bool(eligible), current_bot_id))
    normalized.sort(key=lambda item: (item[0], item[1]))

    planned = {}
    used = set()
    waiting = []
    for _, _, room_id, eligible, current_bot_id in normalized:
        if not eligible:
            planned[room_id] = None
            continue
        current = normalize_music_bot_id(current_bot_id)
        if current is not None and current not in used:
            planned[room_id] = current
            used.add(current)
            continue
        planned[room_id] = None
        waiting.append(room_id)

    for room_id in waiting:
        next_bot_id = choose_next_music_bot_id(used)
        if next_bot_id is None:
            break
        planned[room_id] = next_bot_id
        used.add(next_bot_id)
    return planned


def has_human_members(members) -> bool:
    return any(not bool(getattr(member, "bot", False)) for member in members)


def is_managed_temp_name(name: str, template: str) -> bool:
    """Recognize only channels produced by TEMP_VC_NAME_TEMPLATE."""
    marker = "{name}"
    if marker not in template:
        return False
    prefix, suffix = template.split(marker, 1)
    name = str(name or "")
    if not name.startswith(prefix) or (suffix and not name.endswith(suffix)):
        return False
    middle_end = len(name) - len(suffix) if suffix else len(name)
    return bool(name[len(prefix):middle_end].strip())
