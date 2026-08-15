#!/usr/bin/env python3
"""Regression checks for automatic prison-cell escalation."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="prison-escalation-tests-"))

from cogs.prison_core import DAY, HOUR, PrisonStore, cell_for_penalty


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


class CellThresholdTests(unittest.TestCase):
    def test_duration_thresholds_and_offense_floor(self):
        self.assertEqual(cell_for_penalty(24 * HOUR - 1), "holding")
        self.assertEqual(cell_for_penalty(24 * HOUR), "block")
        self.assertEqual(cell_for_penalty(30 * DAY), "max")
        self.assertEqual(cell_for_penalty(30 * HOUR, "max"), "max")
        self.assertEqual(cell_for_penalty(-1), "max")

    def test_new_inmate_has_auditable_discipline_history(self):
        store = PrisonStore.__new__(PrisonStore)
        store._db = FakeDB()
        record = store.add_inmate(
            1,
            10,
            seconds=HOUR,
            offense_key="spam",
            reason="spam test",
            cell="holding",
            actor_id=99,
            roles=[],
        )
        self.assertEqual(record["penalty_seconds_total"], HOUR)
        self.assertEqual(record["discipline_log"][0]["reason"], "spam test")
        self.assertEqual(record["cell_history"][0]["to"], "holding")


class EscalationSourceTests(unittest.TestCase):
    def test_added_offense_can_raise_existing_prisoner_cell(self):
        imprison = method_source("PrisonSystem", "imprison")
        extend = method_source("PrisonSystem", "extend_sentence")
        self.assertIn("minimum_cell=cell_key", imprison)
        self.assertIn("required_cell = self._required_cell", extend)
        self.assertIn("await self.transfer_cell(", extend)

    def test_transfer_moves_card_access_voice_and_posts_reason(self):
        transfer = method_source("PrisonSystem", "transfer_cell")
        access = method_source("PrisonSystem", "_grant_cell_access")
        self.assertIn("_delete_cell_card_at", transfer)
        self.assertIn("_post_cell_escalation_notice", transfer)
        self.assertIn("view_channel=False", access)
        self.assertIn("connect=False", access)
        self.assertIn("member.move_to(", access)

    def test_solitary_card_refresh_is_isolated(self):
        refresh = method_source("PrisonSystem", "refresh_cell_cards")
        ready = method_source("PrisonSystem", "on_ready")
        self.assertIn("if self.store.in_solitary", refresh)
        self.assertIn("await self._grant_cell_access(", ready)
        self.assertIn("required_cell = self._required_cell", ready)
        self.assertIn("await self.transfer_cell(", ready)


if __name__ == "__main__":
    unittest.main()
