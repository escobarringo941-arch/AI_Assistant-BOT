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


class CellRecordSourceTests(unittest.TestCase):
    def test_active_card_is_upserted_in_text_and_voice_chat(self):
        upsert = method_source("_upsert_cell_record_card")
        post = method_source("_post_cell_card")
        self.assertIn("for is_voice in (False, True)", upsert)
        self.assertIn("discord.ChannelType.voice", upsert)
        self.assertIn("cell_record_message_ids", SOURCE)
        self.assertIn("voice_record_message_ids", SOURCE)
        self.assertIn("PrisonerCardView()", post)

    def test_release_keeps_card_and_marks_user_free(self):
        release = method_source("release")
        archive = method_source("_archived_cell_card_embed")
        self.assertIn('status="released"', release)
        self.assertNotIn("await self._delete_cell_card", release)
        self.assertIn("حر طليق", archive)
        self.assertIn("self.store.cell_entry_counts", archive)
        self.assertIn("self.store.case_count", archive)

    def test_departure_cleanup_preserves_only_official_records_when_empty(self):
        cleanup = method_source("_cleanup_cell_after_departure")
        history = method_source("_clean_messageable_history")
        self.assertIn("_official_cell_message_ids", cleanup)
        self.assertIn("author_filter = None if empty", cleanup)
        self.assertIn("message.id in keep_ids", history)
        self.assertIn("await message.delete()", history)

    def test_leaving_voice_cleans_departed_user_or_entire_empty_chat(self):
        listener = method_source("on_voice_state_update")
        voice_cleanup = method_source("_cleanup_voice_chat_after_leave")
        self.assertIn("before.channel == after.channel", listener)
        self.assertIn("await self._cleanup_voice_chat_after_leave", listener)
        self.assertIn("remaining_people", voice_cleanup)
        self.assertIn("author_filter = None if not remaining_people", voice_cleanup)


if __name__ == "__main__":
    unittest.main()
