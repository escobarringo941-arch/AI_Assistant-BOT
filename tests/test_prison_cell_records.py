#!/usr/bin/env python3
"""Regression checks for durable per-cell inmate records and chat cleanup."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="prison-cell-record-tests-"))

from cogs.prison_core import CELL_KEYS, PrisonStore


ROOT = Path(__file__).resolve().parents[1]
PRISON_PATH = ROOT / "cogs" / "prison.py"
SOURCE = PRISON_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE, filename=str(PRISON_PATH))


def method_source(name: str) -> str:
    cls = next(
        node for node in TREE.body
        if isinstance(node, ast.ClassDef) and node.name == "PrisonSystem"
    )
    node = next(
        item for item in cls.body
        if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef)) and item.name == name
    )
    return ast.get_source_segment(SOURCE, node)


def class_method_source(class_name: str, method_name: str) -> str:
    cls = next(
        node for node in TREE.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    node = next(
        item for item in cls.body
        if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef)) and item.name == method_name
    )
    return ast.get_source_segment(SOURCE, node)


def function_source(name: str) -> str:
    node = next(
        item for item in TREE.body
        if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef)) and item.name == name
    )
    return ast.get_source_segment(SOURCE, node)


class FakeDB:
    def __init__(self, data=None):
        self.data = data or {"guilds": {}}

    def save(self) -> bool:
        return True


class DurableCellStatsTests(unittest.TestCase):
    def make_store(self, data=None) -> PrisonStore:
        store = PrisonStore.__new__(PrisonStore)
        store._db = FakeDB(data)
        return store

    def add(self, store: PrisonStore, cell="holding"):
        return store.add_inmate(
            1,
            10,
            seconds=600,
            offense_key="manual",
            reason="test",
            cell=cell,
            actor_id=20,
            roles=[],
        )

    def test_counts_survive_release_and_reentry(self):
        store = self.make_store()
        self.add(store, "holding")
        store.note_cell_entry(1, 10, "block")
        store.remove_inmate(1, 10)

        self.add(store, "holding")
        self.assertEqual(store.case_count(1, 10), 2)
        self.assertEqual(store.record_count(1, 10), 1)
        self.assertEqual(
            store.cell_entry_counts(1, 10),
            {"holding": 2, "block": 1, "max": 0},
        )

    def test_release_history_keeps_cell_audit_details(self):
        store = self.make_store()
        record = self.add(store, "holding")
        record["cell_history"].append({"at": 2, "from": "holding", "to": "block"})
        record["cell"] = "block"
        store.note_cell_entry(1, 10, "block")
        released = store.remove_inmate(1, 10, outcome="expired")
        history = store.history(1, 1)[0]

        self.assertEqual(released["outcome"], "expired")
        self.assertEqual(history["cell"], "block")
        self.assertEqual(history["cell_history"][-1]["to"], "block")
        self.assertGreater(history["ended"], 0)

    def test_new_storage_has_text_and_voice_record_maps(self):
        store = self.make_store()
        guild = store.guild(1)
        self.assertEqual(guild["cell_record_message_ids"], {key: {} for key in CELL_KEYS})
        self.assertEqual(guild["voice_record_message_ids"], {key: {} for key in CELL_KEYS})

    def test_registry_summary_keeps_time_and_last_release(self):
        store = self.make_store()
        self.add(store, "holding")
        released = store.remove_inmate(1, 10, outcome="expired")
        summary = store.inmate_summary(1, 10)
        self.assertIsNotNone(released)
        self.assertEqual(summary["cases"], 1)
        self.assertGreaterEqual(summary["completed_seconds"], 0)
        self.assertGreater(summary["last_release"], 0)
        self.assertEqual(store.registry_user_ids(1, "holding"), [10])

    def test_public_registry_lists_every_real_inmate_across_cells(self):
        store = self.make_store()
        self.add(store, "holding")
        store.add_inmate(
            1,
            11,
            seconds=600,
            offense_key="manual",
            reason="test two",
            cell="max",
            actor_id=20,
            roles=[],
        )
        self.assertEqual(set(store.registry_user_ids(1, None)), {10, 11})


class CellRecordSourceTests(unittest.TestCase):
    def test_live_file_is_ephemeral_from_text_cell_panel_only(self):
        my_file = class_method_source("CellHelpView", "my_file")
        post = method_source("_post_cell_card")
        self.assertIn("_registry_record_embed", my_file)
        self.assertIn("detailed=True", my_file)
        self.assertIn("ephemeral=True", my_file)
        self.assertIn("prison_channel", my_file)
        self.assertNotIn(".send(", post)

    def test_registry_lists_only_real_inmates_with_private_results(self):
        registry = class_method_source("CellHelpView", "registry")
        detail = method_source("_registry_record_embed")
        self.assertIn("registry_user_ids", registry)
        self.assertIn("PrisonRegistryView", registry)
        self.assertIn("ephemeral=True", registry)
        self.assertIn("inmate_summary", detail)
        self.assertIn("total_served_seconds", detail)

    def test_public_registry_panel_is_persistent_and_private_per_click(self):
        self_record = class_method_source("PublicPrisonRegistryView", "my_record")
        search = class_method_source("PublicPrisonRegistryView", "search")
        setup = function_source("setup")
        refresh = method_source("refresh_wanted_board")
        self.assertIn("detailed=True", self_record)
        self.assertIn("ephemeral=True", self_record)
        self.assertIn("registry_user_ids(interaction.guild.id, None)", search)
        self.assertIn("ephemeral=True", search)
        self.assertIn("bot.add_view(PublicPrisonRegistryView())", setup)
        self.assertIn("view=PublicPrisonRegistryView()", refresh)

    def test_public_search_hides_sensitive_reason_and_staff_scope_is_limited(self):
        callback = class_method_source("PrisonRegistrySelect", "callback")
        permissions = method_source("_can_view_private_registry")
        detail = method_source("_registry_record_embed")
        self.assertIn("_can_view_private_registry", callback)
        self.assertIn("requester.id", permissions)
        self.assertIn("is_server_owner", permissions)
        self.assertIn("is_warden", permissions)
        self.assertIn("WARDEN_ALLOWED_CELLS", permissions)
        self.assertIn("if detailed:", detail)
        self.assertIn('name="📝 آخر سبب"', detail)
        self.assertIn("التفاصيل الحساسة مخفية", detail)

    def test_release_removes_active_record_before_permission_restore(self):
        release = method_source("release")
        self.assertLess(
            release.index("self.store.remove_inmate"),
            release.index("await self._restore_pre_prison_overwrites"),
        )
        self.assertIn("role_restore_error", release)

    def test_old_public_cards_are_deleted_from_text_and_voice(self):
        cleanup = method_source("_remove_legacy_cell_record_cards")
        self.assertIn("discord.ChannelType.voice", cleanup)
        self.assertIn("async for message in target.history", cleanup)
        self.assertIn('"ملف السجين"', cleanup)
        self.assertIn(".clear()", cleanup)

    def test_departure_cleanup_preserves_only_official_records_when_empty(self):
        cleanup = method_source("_cleanup_cell_after_departure")
        history = method_source("_clean_messageable_history")
        self.assertIn("_official_cell_message_ids", cleanup)
        self.assertIn("author_filter = None if empty", cleanup)
        self.assertIn("message.id in keep_ids", history)
        self.assertIn("await message.delete()", history)
        official = method_source("_official_cell_message_ids")
        self.assertNotIn("_cell_record_map", official)

    def test_leaving_voice_cleans_departed_user_or_entire_empty_chat(self):
        listener = method_source("on_voice_state_update")
        voice_cleanup = method_source("_cleanup_voice_chat_after_leave")
        self.assertIn("before.channel == after.channel", listener)
        self.assertIn("await self._cleanup_voice_chat_after_leave", listener)
        self.assertIn("remaining_people", voice_cleanup)
        self.assertIn("author_filter = None if not remaining_people", voice_cleanup)


if __name__ == "__main__":
    unittest.main()
