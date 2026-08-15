#!/usr/bin/env python3
"""Regression checks for the prisoner-approved visit flow."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="prison-visit-tests-"))

from cogs.prison_core import CHANNEL_NAMES, PrisonStore


ROOT = Path(__file__).resolve().parents[1]
PRISON_PATH = ROOT / "cogs" / "prison.py"
SOURCE = PRISON_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE, filename=str(PRISON_PATH))


def class_node(name: str) -> ast.ClassDef:
    return next(node for node in TREE.body if isinstance(node, ast.ClassDef) and node.name == name)


def method_node(class_name: str, method_name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    cls = class_node(class_name)
    return next(
        node
        for node in cls.body
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == method_name
    )


def button_ids(class_name: str) -> set[str]:
    result: set[str] = set()
    for node in class_node(class_name).body:
        if not isinstance(node, ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            for keyword in decorator.keywords:
                if keyword.arg == "custom_id" and isinstance(keyword.value, ast.Constant):
                    result.add(str(keyword.value.value))
    return result


class FakeDB:
    def __init__(self):
        self.data = {"guilds": {}}

    def save(self) -> bool:
        return True


class VisitSourceTests(unittest.TestCase):
    def test_public_panel_contains_only_request_button(self):
        self.assertEqual(button_ids("VisitPanelView"), {"ggmw9:visit:request"})

    def test_management_panel_is_separate(self):
        self.assertEqual(
            button_ids("VisitManagementPanelView"),
            {"ggmw9:visit:list", "ggmw9:visit:end"},
        )
        self.assertEqual(CHANNEL_NAMES["visit_admin"], "👮┃visit-control")
        staff_check = next(
            node
            for node in TREE.body
            if isinstance(node, ast.FunctionDef) and node.name == "_is_visit_staff"
        )
        staff_source = ast.get_source_segment(SOURCE, staff_check)
        self.assertIn("is_server_owner", staff_source)
        self.assertIn("is_warden", staff_source)
        self.assertNotIn("admin_role_id", staff_source)
        self.assertNotIn("moderator_role_id", staff_source)
        publish_source = ast.get_source_segment(
            SOURCE, method_node("PrisonSystem", "publish_visit_admin_panel")
        )
        self.assertIn('guild.create_text_channel(', publish_source)
        self.assertIn('record["channels"]["visit_admin"] = channel.id', publish_source)

    def test_request_targets_prisoner_and_acceptance_requires_prisoner(self):
        request_source = ast.get_source_segment(
            SOURCE, method_node("PrisonSystem", "request_visit")
        )
        accept_source = ast.get_source_segment(
            SOURCE, method_node("PrisonSystem", "accept_visit")
        )
        self.assertIn("PrisonerVisitInviteView", request_source)
        self.assertIn("await prisoner.send", request_source)
        self.assertNotIn("view = VisitInviteView(", request_source)
        self.assertIn("prisoner_id", accept_source.splitlines()[0:3].__str__())
        self.assertNotIn("visitor_id", accept_source.splitlines()[0:3].__str__())

    def test_temporary_voice_room_does_not_inherit_staff_access(self):
        source = ast.get_source_segment(
            SOURCE, method_node("PrisonSystem", "_visit_voice_overwrites")
        )
        self.assertNotIn("_category_overwrites", source)
        self.assertIn("overwrites[warden] = blocked", source)
        self.assertIn("overwrites[prisoner] = full", source)
        self.assertIn("overwrites[visitor] = full", source)


class VisitStoreTests(unittest.TestCase):
    def make_store(self) -> PrisonStore:
        store = PrisonStore.__new__(PrisonStore)
        store._db = FakeDB()
        return store

    def test_pending_invite_expiry_survives_restart_style_polling(self):
        store = self.make_store()
        with patch("cogs.prison_core.now_ts", return_value=1_000):
            record = store.add_visit(
                1, prisoner_id=10, visitor_id=20, seconds=900, by=20
            )
        store.set_visit_invite_channel(1, record["id"], 777)

        with patch("cogs.prison_core.now_ts", return_value=1_299):
            self.assertEqual(store.expired_pending_visits(1), [])
        with patch("cogs.prison_core.now_ts", return_value=1_300):
            expired = store.expired_pending_visits(1)

        self.assertEqual(expired[0][0], record["id"])
        self.assertEqual(expired[0][1]["invite_channel_id"], 777)


if __name__ == "__main__":
    unittest.main()
