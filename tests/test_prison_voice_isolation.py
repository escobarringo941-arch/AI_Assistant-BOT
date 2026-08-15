#!/usr/bin/env python3
"""Regression checks for voice-cell help panels and per-inmate hard locks."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="prison-voice-isolation-tests-"))

from cogs.prison_core import CELL_KEYS, PrisonStore


ROOT = Path(__file__).resolve().parents[1]
PRISON_PATH = ROOT / "cogs" / "prison.py"
SOURCE = PRISON_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE, filename=str(PRISON_PATH))


def class_node(name: str) -> ast.ClassDef:
    return next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == name)


def method_source(class_name: str, method_name: str) -> str:
    cls = class_node(class_name)
    node = next(
        item
        for item in cls.body
        if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef)) and item.name == method_name
    )
    return ast.get_source_segment(SOURCE, node)


class FakeDB:
    def __init__(self):
        self.data = {"guilds": {}}

    def save(self) -> bool:
        return True


class VoiceIsolationStoreTests(unittest.TestCase):
    def make_store(self) -> PrisonStore:
        store = PrisonStore.__new__(PrisonStore)
        store._db = FakeDB()
        return store

    def test_every_voice_cell_has_durable_help_panel_storage(self):
        store = self.make_store()
        self.assertEqual(
            store.guild(1)["voice_help_message_ids"],
            {cell: 0 for cell in CELL_KEYS},
        )

    def test_new_inmate_has_pre_prison_permission_snapshot_storage(self):
        store = self.make_store()
        record = store.add_inmate(
            1,
            10,
            seconds=600,
            offense_key="manual",
            reason="test",
            cell="holding",
            actor_id=20,
            roles=[],
            nick=None,
        )
        self.assertEqual(record["pre_prison_overwrites"], [])


class VoiceIsolationSourceTests(unittest.TestCase):
    def test_help_panel_is_published_in_embedded_voice_chat(self):
        publish = method_source("PrisonSystem", "publish_cell_help_panels")
        self.assertIn('record.setdefault("voice_help_message_ids", {})', publish)
        self.assertIn("self.bot.get_partial_messageable", publish)
        self.assertIn("discord.ChannelType.voice", publish)
        self.assertIn("await voice_chat.send", publish)
        self.assertIn("view=CellVoiceHelpView()", publish)
        self.assertIn("ملف السجين والسجل الكامل كاينين غير فـ#", publish)

    def test_current_voice_cell_allows_plain_text_chat_only(self):
        access = method_source("PrisonSystem", "_grant_cell_access")
        self.assertIn("await voice_channel.set_permissions", access)
        self.assertIn("view_channel=True", access)
        self.assertIn("read_message_history=True", access)
        self.assertIn("send_messages=True", access)
        self.assertIn("send_tts_messages=False", access)
        self.assertIn("attach_files=False", access)
        self.assertIn("embed_links=False", access)
        self.assertIn("create_public_threads=False", access)
        self.assertIn("create_private_threads=False", access)
        self.assertIn("send_messages_in_threads=False", access)
        self.assertIn("connect=True", access)
        self.assertIn("speak=True", access)

    def test_embedded_voice_chat_uses_the_same_cell_moderation(self):
        on_message = method_source("PrisonSystem", "on_message")
        self.assertIn("self.cell_voice_channel(guild, cell_key)", on_message)
        self.assertIn("allowed_cell_chat_ids", on_message)
        self.assertIn("message.channel.id not in allowed_cell_chat_ids", on_message)

    def test_visit_channels_get_an_explicit_member_deny(self):
        access = method_source("PrisonSystem", "_grant_cell_access")
        self.assertIn('for key in ("visits", "visit_admin")', access)
        self.assertIn("overwrite=HIDE_OVERWRITE", access)
        self.assertIn("hide visit channels from inmate", access)

    def test_arrest_snapshots_and_locks_last_rooms(self):
        imprison = method_source("PrisonSystem", "imprison")
        lock = method_source("PrisonSystem", "_lock_pre_prison_channels")
        self.assertIn("self._pre_prison_origin_channels", imprison)
        self.assertIn("await self._lock_pre_prison_channels", imprison)
        self.assertIn('"had_overwrite"', lock)
        self.assertIn('"allow": int(allow.value)', lock)
        self.assertIn('"deny": int(deny.value)', lock)
        self.assertIn("overwrite=HIDE_OVERWRITE", lock)

    def test_release_restores_the_exact_previous_member_overwrite(self):
        release = method_source("PrisonSystem", "release")
        restore = method_source("PrisonSystem", "_restore_pre_prison_overwrites")
        self.assertIn("await self._restore_pre_prison_overwrites", release)
        self.assertIn("discord.PermissionOverwrite.from_pair", restore)
        self.assertIn('snapshot.get("had_overwrite")', restore)
        self.assertIn("overwrite=overwrite", restore)

    def test_last_message_room_is_tracked_and_locks_are_repaired(self):
        on_message = method_source("PrisonSystem", "on_message")
        on_ready = method_source("PrisonSystem", "on_ready")
        on_join = method_source("PrisonSystem", "on_member_join")
        on_channel_update = method_source("PrisonSystem", "on_guild_channel_update")
        self.assertIn("self._last_non_prison_message_channel", on_message)
        self.assertIn("await self._enforce_pre_prison_locks", on_ready)
        self.assertIn("await self._enforce_pre_prison_locks", on_join)
        self.assertIn('record.get("pre_prison_overwrites", [])', on_channel_update)
        self.assertIn("overwrite=HIDE_OVERWRITE", on_channel_update)


if __name__ == "__main__":
    unittest.main()
