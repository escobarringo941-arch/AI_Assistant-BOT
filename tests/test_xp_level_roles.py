#!/usr/bin/env python3
"""Regression checks for the manual Level X role consolidation."""

from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest

try:
    import discord
except ModuleNotFoundError:  # CI ديال هاد المشروع كيدير static tests بلا discord.py
    class _Permissions:
        _BITS = {"send_messages": 1, "attach_files": 2}

        def __init__(self, value=0, **kwargs):
            self.value = int(value)
            for name, enabled in kwargs.items():
                if enabled:
                    self.value |= self._BITS.get(name, 0)

        @classmethod
        def none(cls):
            return cls(0)

    class _PermissionOverwrite:
        def __init__(self, **kwargs):
            self._allow = _Permissions(**{key: value for key, value in kwargs.items() if value is True})
            self._deny = _Permissions(**{key: True for key, value in kwargs.items() if value is False})

        def pair(self):
            return self._allow, self._deny

        @classmethod
        def from_pair(cls, allow, deny):
            item = cls()
            item._allow, item._deny = allow, deny
            return item

        def __getattr__(self, name):
            bit = _Permissions._BITS.get(name, 0)
            if self._allow.value & bit:
                return True
            if self._deny.value & bit:
                return False
            return None

    class _DiscordError(Exception):
        pass

    discord = types.SimpleNamespace(
        Permissions=_Permissions,
        PermissionOverwrite=_PermissionOverwrite,
        Guild=object,
        Role=object,
        Forbidden=_DiscordError,
        HTTPException=_DiscordError,
        NotFound=_DiscordError,
    )
    sys.modules.setdefault("discord", discord)

from cogs.xp_level_roles import (
    LEGACY_LEVEL_ROLE_IDS,
    consolidate_legacy_xp_roles,
    level_from_role_name,
    named_level_roles,
    safe_managed_level_role_ids,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeRole:
    def __init__(self, role_id: int, name: str, position: int = 1, *, managed=False):
        self.id = int(role_id)
        self.name = name
        self.position = int(position)
        self.managed = managed
        self.deleted = False
        self.permissions = discord.Permissions.none()

    def __hash__(self):
        return hash(self.id)

    async def delete(self, *, reason=None):
        self.deleted = True


class FakeChannel:
    def __init__(self, overwrites=None):
        self.overwrites = dict(overwrites or {})

    def overwrites_for(self, role):
        return self.overwrites.get(role, discord.PermissionOverwrite())

    async def set_permissions(self, role, *, overwrite, reason=None):
        self.overwrites[role] = overwrite


class FakeGuild:
    def __init__(self, roles, channels=None):
        self.roles = list(roles)
        self.channels = list(channels or [])

    def get_role(self, role_id):
        return next((role for role in self.roles if role.id == int(role_id)), None)


class XPLevelRoleMappingTests(unittest.TestCase):
    def test_manual_decorated_names_are_recognized_from_5_to_100(self):
        self.assertEqual(level_from_role_name("Level 5 عضو شبه نشيط"), 5)
        self.assertEqual(level_from_role_name("🏆 LEVEL-100 أسطورة"), 100)
        self.assertEqual(level_from_role_name("Level 55"), None)
        self.assertEqual(level_from_role_name("member"), None)

    def test_exact_name_wins_duplicate_then_higher_position_is_deterministic(self):
        decorated = FakeRole(10, "🌱 Level 5 عضو شبه نشيط", 40)
        exact = FakeRole(11, "Level 5", 10)
        level_ten_low = FakeRole(12, "Level 10 Bronze", 3)
        level_ten_high = FakeRole(13, "Level 10 Active", 8)
        mapping = named_level_roles(
            FakeGuild([decorated, exact, level_ten_low, level_ten_high])
        )
        self.assertIs(mapping[5], exact)
        self.assertIs(mapping[10], level_ten_high)

    def test_old_role_is_safe_to_manage_only_when_manual_replacement_exists(self):
        level_five = FakeRole(999, "Level 5 عضو شبه نشيط")
        guild = FakeGuild([level_five])
        managed = safe_managed_level_role_ids(guild, {"tier_roles": {}, "legend_roles": {}})
        self.assertIn(level_five.id, managed)
        self.assertIn(LEGACY_LEVEL_ROLE_IDS[5], managed)
        self.assertNotIn(LEGACY_LEVEL_ROLE_IDS[10], managed)


class XPLevelRoleMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_channel_permissions_move_before_known_old_role_is_deleted(self):
        manual = FakeRole(999, "Level 5 عضو شبه نشيط", 20)
        old = FakeRole(LEGACY_LEVEL_ROLE_IDS[5], "Bot Starter", 5)
        channel = FakeChannel(
            {old: discord.PermissionOverwrite(send_messages=True, attach_files=True)}
        )
        state = {"tier_roles": {}, "legend_roles": {}}
        result = await consolidate_legacy_xp_roles(
            FakeGuild([manual, old], [channel]), state
        )
        self.assertTrue(old.deleted)
        self.assertIn(old.id, result["deleted"])
        migrated = channel.overwrites_for(manual)
        self.assertTrue(migrated.send_messages)
        self.assertTrue(migrated.attach_files)

    async def test_bot_milestone_role_is_not_deleted_if_target_level_is_missing(self):
        milestone = FakeRole(777, "old milestone")
        state = {"tier_roles": {"10": milestone.id}, "legend_roles": {}}
        result = await consolidate_legacy_xp_roles(FakeGuild([milestone]), state)
        self.assertFalse(milestone.deleted)
        self.assertIn("10", state["tier_roles"])
        self.assertIn(10, result["missing"])


class XPLevelRoleSourceTests(unittest.TestCase):
    def test_runtime_never_creates_extra_milestone_or_legend_roles(self):
        persistent = (ROOT / "cogs" / "persistent_state.py").read_text(encoding="utf-8")
        levels = (ROOT / "cogs" / "levels_center.py").read_text(encoding="utf-8")
        self.assertNotIn("await guild.create_role", persistent)
        self.assertNotIn('reason=f"Milestone Level {level}"', persistent)
        self.assertNotIn("await role.edit(name=new_name", levels)
        self.assertIn('data["legend_title"] = new_title', levels)

    def test_sync_uses_manual_roles_and_removes_every_non_target_level_role(self):
        persistent = (ROOT / "cogs" / "persistent_state.py").read_text(encoding="utf-8")
        bootstrap = (ROOT / "cogs" / "bootstrap.py").read_text(encoding="utf-8")
        self.assertIn("named_level_roles(guild)", persistent)
        self.assertIn("safe_managed_level_role_ids", persistent)
        self.assertIn("r.id != target_role_id", persistent)
        self.assertIn("consolidate_legacy_xp_roles", bootstrap)


if __name__ == "__main__":
    unittest.main()
