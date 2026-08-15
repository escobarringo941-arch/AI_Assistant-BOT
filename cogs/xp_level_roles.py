# -*- coding: utf-8 -*-
"""اعتماد رولات XP الموجودة باسم Level X وتنظيف الرولات القديمة بأمان."""

from __future__ import annotations

import re
from typing import Optional

import discord


LEVEL_THRESHOLDS = (5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100)

# الـIDs اللي كان الكود القديم كيعتمدها. كنستعملوها غير للتعرّف على الرولات
# القديمة وترحيلها؛ الاختيار الجديد كيتدار بالاسم Level X الموجود فالسيرفر.
LEGACY_LEVEL_ROLE_IDS = {
    5: 1532874771287507135,
    10: 1532877605366268116,
    15: 1532877729052233988,
    20: 1532877833125232740,
    25: 1532877955414360336,
    30: 1532877995306651853,
    35: 1532878086893207653,
    40: 1532878137430380674,
    45: 1532878260428341390,
    50: 1532878348752261331,
    60: 1532878501278125251,
    70: 1532878632371138181,
    80: 1532878710745596064,
    90: 1532878803075076106,
    100: 1532878888986738869,
}

_LEVEL_NAME_RE = re.compile(
    r"(?i)(?<![a-z0-9])level\s*[-_:|]?\s*(100|90|80|70|60|50|45|40|35|30|25|20|15|10|5)(?!\d)"
)


def level_from_role_name(name: str) -> Optional[int]:
    """كيقبل Level 5 وLEVEL-5 وحتى سمية مزوقة، ويرفض أي رقم خارج النظام."""
    matches = _LEVEL_NAME_RE.findall(str(name or ""))
    if len(matches) != 1:
        return None
    level = int(matches[0])
    return level if level in LEVEL_THRESHOLDS else None


def named_level_roles(guild: discord.Guild) -> dict[int, discord.Role]:
    """خريطة Level→Role من الرولات الموجودة، بلا إنشاء أي رول جديدة."""
    result: dict[int, discord.Role] = {}
    for role in guild.roles:
        level = level_from_role_name(role.name)
        if level is None or role.managed:
            continue
        current = result.get(level)
        exact = role.name.strip().casefold() == f"level {level}"
        current_exact = bool(
            current and current.name.strip().casefold() == f"level {level}"
        )
        # الاسم المطابق حرفياً هو الأولوية؛ وإلا ناخدو الأعلى فالـhierarchy.
        if current is None or (exact and not current_exact) or (
            exact == current_exact and role.position > current.position
        ):
            result[level] = role
    return result


def safe_managed_level_role_ids(
    guild: discord.Guild,
    milestone_state: Optional[dict] = None,
) -> set[int]:
    """الرولات اللي يمكن تتحيد من الأعضاء لأن البديل Level X موجود فعلاً."""
    canonical = named_level_roles(guild)
    ids = {role.id for role in canonical.values()}
    for level, role_id in LEGACY_LEVEL_ROLE_IDS.items():
        if level in canonical:
            ids.add(int(role_id))

    state = milestone_state or {}
    for raw_level, role_id in (state.get("tier_roles") or {}).items():
        try:
            level = int(raw_level)
        except (TypeError, ValueError):
            continue
        if level in canonical:
            ids.add(int(role_id))
    if 100 in canonical:
        ids.update(int(role_id) for role_id in (state.get("legend_roles") or {}).values())
    return ids


def _merged_overwrite(
    current: discord.PermissionOverwrite,
    legacy: discord.PermissionOverwrite,
) -> discord.PermissionOverwrite:
    current_allow, current_deny = current.pair()
    legacy_allow, legacy_deny = legacy.pair()
    allow_value = current_allow.value | legacy_allow.value
    deny_value = (current_deny.value | legacy_deny.value) & ~allow_value
    return discord.PermissionOverwrite.from_pair(
        discord.Permissions(allow_value), discord.Permissions(deny_value)
    )


async def consolidate_legacy_xp_roles(
    guild: discord.Guild,
    milestone_state: dict,
) -> dict:
    """ينقل channel overwrites للرولات Level X ثم يمسح غير رولات XP المعروفة."""
    canonical = named_level_roles(guild)
    canonical_ids = {role.id for role in canonical.values()}
    stale_to_level: dict[int, int] = {
        int(role_id): level
        for level, role_id in LEGACY_LEVEL_ROLE_IDS.items()
        if level in canonical and int(role_id) not in canonical_ids
    }
    for raw_level, role_id in (milestone_state.get("tier_roles") or {}).items():
        try:
            level = int(raw_level)
            role_id = int(role_id)
        except (TypeError, ValueError):
            continue
        if level in canonical and role_id not in canonical_ids:
            stale_to_level[role_id] = level
    if 100 in canonical:
        for role_id in (milestone_state.get("legend_roles") or {}).values():
            try:
                role_id = int(role_id)
            except (TypeError, ValueError):
                continue
            if role_id not in canonical_ids:
                stale_to_level[role_id] = 100

    deleted: set[int] = set()
    failed: set[int] = set()
    for role_id, level in stale_to_level.items():
        old_role = guild.get_role(role_id)
        if old_role is None:
            deleted.add(role_id)
            continue
        target_role = canonical[level]

        # Channel-specific permissions كتنتاقل قبل الحذف، والـAllow كيربح
        # التعارض بنفس منطق Discord ملي العضو كان جامع جوج رولات.
        migration_ok = True
        for channel in guild.channels:
            old_overwrite = channel.overwrites.get(old_role)
            if old_overwrite is None:
                continue
            try:
                await channel.set_permissions(
                    target_role,
                    overwrite=_merged_overwrite(
                        channel.overwrites_for(target_role), old_overwrite
                    ),
                    reason=f"XP Role migration: Level {level}",
                )
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                migration_ok = False
                break
        if not migration_ok:
            failed.add(role_id)
            continue
        try:
            await old_role.delete(reason=f"XP Role consolidated into Level {level}")
            deleted.add(role_id)
        except (discord.Forbidden, discord.HTTPException, discord.NotFound):
            failed.add(role_id)

    # نحيد من التخزين غير IDs اللي تمسحات/ما بقاتش موجودة. الفاشلة كتبقى باش
    # البوت يعاود يحاول فالـRestart أو من زر Sync Roles.
    tiers = milestone_state.setdefault("tier_roles", {})
    for key, role_id in list(tiers.items()):
        if int(role_id) in deleted:
            tiers.pop(key, None)
    legends = milestone_state.setdefault("legend_roles", {})
    for key, role_id in list(legends.items()):
        if int(role_id) in deleted:
            legends.pop(key, None)

    return {
        "roles": canonical,
        "missing": [level for level in LEVEL_THRESHOLDS if level not in canonical],
        "deleted": sorted(deleted),
        "failed": sorted(failed),
    }
