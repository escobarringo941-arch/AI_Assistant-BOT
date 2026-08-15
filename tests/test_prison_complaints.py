#!/usr/bin/env python3
"""Regression checks for cell incidents, staff authority and solitary isolation."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="prison-complaint-tests-"))

from cogs.prison_core import (
    CELL_KEYS,
    COMPLAINT_MAX_TARGETS,
    PrisonStore,
    complaint_route_for_cell,
    solitary_channel_name,
)


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


class ComplaintStoreTests(unittest.TestCase):
    def make_store(self) -> PrisonStore:
        store = PrisonStore.__new__(PrisonStore)
        store._db = FakeDB()
        return store

    def test_route_is_based_on_cell_not_offense(self):
        self.assertEqual(complaint_route_for_cell("holding"), "warden")
        self.assertEqual(complaint_route_for_cell("block"), "owner")
        self.assertEqual(complaint_route_for_cell("max"), "owner")

    def test_multi_target_complaint_is_stored_with_cell_snapshot(self):
        store = self.make_store()
        with patch("cogs.prison_core.now_ts", return_value=1_000):
            record = store.add_complaint(
                1,
                author_id=10,
                target_ids=[20, 30, 20],
                reason="fight in holding",
                route="warden",
                cell="holding",
            )

        self.assertEqual(record["targets"], [20, 30])
        self.assertEqual(record["target"], 20)
        self.assertEqual(record["cell"], "holding")
        self.assertEqual(store.complaint_target_ids(record), [20, 30])

    def test_old_single_target_complaint_migrates_safely(self):
        store = self.make_store()
        guild = store.guild(1)
        guild["complaints"] = {
            "7": {"id": "7", "author": 10, "target": 22, "route": "owner", "status": "pending"}
        }

        migrated = store.complaints(1)["7"]
        self.assertEqual(migrated["targets"], [22])
        self.assertEqual(migrated["cell"], "block")

    def test_solitary_room_names_are_unique_for_duplicate_names(self):
        self.assertNotEqual(solitary_channel_name("same", 11), solitary_channel_name("same", 12))

    def test_each_cell_has_durable_help_panel_storage(self):
        store = self.make_store()
        self.assertEqual(
            store.guild(1)["cell_help_message_ids"],
            {cell: 0 for cell in CELL_KEYS},
        )


class ComplaintSourceTests(unittest.TestCase):
    def test_fixed_help_panel_is_published_in_every_text_cell(self):
        publish = method_source("PrisonSystem", "publish_cell_help_panels")
        ensure = method_source("PrisonSystem", "ensure_infrastructure")
        ready = method_source("PrisonSystem", "on_ready")
        setup = next(
            node
            for node in TREE.body
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "setup"
        )
        setup_source = ast.get_source_segment(SOURCE, setup)

        self.assertIn("for cell in CELL_KEYS", publish)
        self.assertIn('record.setdefault("cell_help_message_ids", {})', publish)
        self.assertIn("view=CellHelpView()", publish)
        self.assertIn("await message.pin", publish)
        self.assertIn("await self.publish_cell_help_panels(guild)", ensure)
        self.assertIn("await self.publish_cell_help_panels(guild)", ready)
        self.assertIn("bot.add_view(CellHelpView())", setup_source)

    def test_cellmates_share_text_and_voice_access(self):
        access = method_source("PrisonSystem", "_grant_cell_access")
        self.assertIn("for key in CELL_KEYS", access)
        self.assertIn("send_messages=True", access)
        self.assertIn("connect=True", access)
        self.assertIn("speak=True", access)

    def test_searchable_multi_member_selector_is_used(self):
        self.assertLessEqual(COMPLAINT_MAX_TARGETS, 25)
        select = ast.get_source_segment(SOURCE, class_node("ComplaintTargetSelect"))
        self.assertIn("discord.ui.UserSelect", select)
        self.assertIn("max_values=COMPLAINT_MAX_TARGETS", select)

    def test_submission_requires_every_target_to_share_the_authors_cell(self):
        submit = method_source("PrisonSystem", "submit_complaint")
        self.assertIn('target_record.get("cell", "holding") != author_cell', submit)
        self.assertIn("self.complaint_route(author_cell)", submit)
        self.assertIn("requested.intersection", submit)

    def test_warden_authority_is_holding_only(self):
        authority = method_source("PrisonSystem", "can_handle_complaint")
        text_permissions = method_source("PrisonSystem", "_channel_overwrites")
        voice_permissions = method_source("PrisonSystem", "_cell_voice_overwrites")
        solitary_permissions = method_source("PrisonSystem", "solitary_overwrites")
        self.assertIn('complaint.get("cell") == "holding"', authority)
        self.assertIn('if key == "holding"', text_permissions)
        self.assertIn('if key == "holding"', voice_permissions)
        self.assertIn('record.get("cell", "holding") == "holding"', solitary_permissions)

    def test_group_approval_is_atomic_and_creates_one_room_per_target(self):
        approve = method_source("SolitaryDurationModal", "on_submit")
        self.assertIn("async with cog.complaint_lock", approve)
        self.assertIn("for target in targets", approve)
        self.assertIn("await cog.send_to_solitary", approve)
        self.assertIn("for created_member, _created_result in created", approve)
        self.assertIn("await cog.release_from_solitary", approve)
        self.assertIn("available < len(targets)", approve)


if __name__ == "__main__":
    unittest.main()
