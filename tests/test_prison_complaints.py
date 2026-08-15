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
    solitary_default_seconds,
    solitary_max_seconds,
    solitary_role_name,
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
        self.assertIn("11", solitary_channel_name("same", 11))

    def test_solitary_role_is_unique_to_id_case_and_cell(self):
        role = solitary_role_name(123456789, 42, "max")
        self.assertIn("123456789", role)
        self.assertIn("Case 42", role)
        self.assertIn("MAX", role)

    def test_solitary_time_is_harsher_for_each_cell(self):
        self.assertLess(
            solitary_default_seconds("holding"), solitary_default_seconds("block")
        )
        self.assertLess(solitary_default_seconds("block"), solitary_default_seconds("max"))
        self.assertLess(solitary_max_seconds("holding"), solitary_max_seconds("block"))
        self.assertLess(solitary_max_seconds("block"), solitary_max_seconds("max"))

    def test_solitary_record_remembers_unique_role_and_multiplies_repeat_noise(self):
        store = self.make_store()
        with patch("cogs.prison_core.now_ts", return_value=1_000):
            record = store.add_solitary(
                1,
                10,
                channel_id=100,
                role_id=200,
                seconds=600,
                reason="fight",
                by=1,
                cell="holding",
            )
        self.assertEqual(record["role_id"], 200)
        with patch("cogs.prison_core.now_ts", return_value=1_100):
            punished = store.punish_solitary_violation(1, 10, reason="spam")
        self.assertEqual(punished["violations"], 1)
        self.assertEqual(punished["discipline"][-1]["multiplier"], 2)
        self.assertGreater(punished["until"], record["since"] + 600)

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

    def test_warden_authority_is_holding_only_but_private_solitary_stays_hidden(self):
        authority = method_source("PrisonSystem", "can_handle_complaint")
        text_permissions = method_source("PrisonSystem", "_channel_overwrites")
        voice_permissions = method_source("PrisonSystem", "_cell_voice_overwrites")
        solitary_permissions = method_source("PrisonSystem", "solitary_overwrites")
        self.assertIn('complaint.get("cell") == "holding"', authority)
        self.assertIn('if key == "holding"', text_permissions)
        self.assertIn('if key == "holding"', voice_permissions)
        self.assertIn("overwrites[warden] = blocked", solitary_permissions)
        self.assertIn("overwrites[access_role]", solitary_permissions)
        self.assertIn("overwrites[member]", solitary_permissions)

    def test_group_approval_is_atomic_and_creates_one_room_per_target(self):
        approve = method_source("SolitaryDurationModal", "on_submit")
        self.assertIn("async with cog.complaint_lock", approve)
        self.assertIn("for target in targets", approve)
        self.assertIn("await cog.send_to_solitary", approve)
        self.assertIn("for created_member, _created_result in created", approve)
        self.assertIn("await cog.release_from_solitary", approve)
        self.assertIn("available < len(targets)", approve)

    def test_solitary_uses_one_id_voice_role_and_deletes_both_on_release(self):
        create = method_source("PrisonSystem", "send_to_solitary")
        release = method_source("PrisonSystem", "release_from_solitary")
        restore = method_source("PrisonSystem", "_restore_solitary_session")
        message = method_source("PrisonSystem", "on_message")
        self.assertIn("_create_solitary_role", create)
        self.assertIn("create_voice_channel", create)
        self.assertIn("user_limit=1", create)
        self.assertIn("role_id=access_role.id", create)
        self.assertIn("await role.delete", release)
        self.assertIn("await channel.delete", release)
        self.assertIn("_clear_solitary_member_blackout", release)
        self.assertIn("_restore_solitary_session", restore)
        self.assertIn("_punish_solitary_violation", message)


if __name__ == "__main__":
    unittest.main()
