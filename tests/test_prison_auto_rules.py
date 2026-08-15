#!/usr/bin/env python3
"""Regression checks for Arabic timers, voice rosters, and owner auto-rules."""

from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="prison-auto-rule-tests-"))

from cogs.prison_core import (  # noqa: E402
    AUTO_ACTION_LABELS,
    PrisonStore,
    format_duration,
    normalize_auto_rule_pattern,
)


ROOT = Path(__file__).resolve().parents[1]
PRISON_PATH = ROOT / "cogs" / "prison.py"
PANEL_PATH = ROOT / "cogs" / "prison_panel.py"
PRISON_SOURCE = PRISON_PATH.read_text(encoding="utf-8")
PANEL_SOURCE = PANEL_PATH.read_text(encoding="utf-8")
PRISON_TREE = ast.parse(PRISON_SOURCE, filename=str(PRISON_PATH))
PANEL_TREE = ast.parse(PANEL_SOURCE, filename=str(PANEL_PATH))


def method_source(tree: ast.Module, source: str, class_name: str, method_name: str) -> str:
    cls = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    node = next(
        item
        for item in cls.body
        if isinstance(item, (ast.AsyncFunctionDef, ast.FunctionDef))
        and item.name == method_name
    )
    return ast.get_source_segment(source, node)


class FakeDB:
    def __init__(self):
        self.data = {"guilds": {}}

    def save(self) -> bool:
        return True


class ArabicDurationTests(unittest.TestCase):
    def test_minutes_use_singular_dual_and_plural_forms(self):
        self.assertEqual(format_duration(60), "1 دقيقة")
        self.assertEqual(format_duration(2 * 60), "دقيقتان")
        self.assertEqual(format_duration(4 * 60), "4 دقائق")
        self.assertEqual(format_duration(10 * 60), "10 دقائق")
        self.assertEqual(format_duration(11 * 60), "11 دقيقة")
        self.assertEqual(format_duration(20 * 60), "20 دقيقة")

    def test_hours_and_compound_durations_are_grammatical(self):
        self.assertEqual(format_duration(60 * 60), "1 ساعة")
        self.assertEqual(format_duration(2 * 60 * 60), "ساعتان")
        self.assertEqual(format_duration(3 * 60 * 60), "3 ساعات")
        self.assertEqual(format_duration(11 * 60 * 60), "11 ساعة")
        self.assertEqual(format_duration((2 * 60 + 2) * 60), "ساعتان و دقيقتان")


class AutoRuleStoreTests(unittest.TestCase):
    def make_store(self) -> PrisonStore:
        store = PrisonStore.__new__(PrisonStore)
        store._db = FakeDB()
        return store

    def test_domain_normalization(self):
        self.assertEqual(
            normalize_auto_rule_pattern("domain", "HTTPS://WWW.Example.COM/path?q=1"),
            "example.com",
        )
        self.assertEqual(normalize_auto_rule_pattern("domain", "not a domain"), "")

    def test_rule_lifecycle_is_durable_and_offense_linked(self):
        store = self.make_store()
        self.assertEqual(store.guild(1)["auto_rules"], {})
        rule = store.add_auto_rule(
            1,
            kind="word",
            pattern="  BAD   PHRASE ",
            offense_key="spam",
        )
        self.assertEqual(rule["pattern"], "bad phrase")
        self.assertEqual(rule["offense"], "spam")
        self.assertEqual(rule["trigger_count"], 1)
        self.assertTrue(rule["enabled"])
        self.assertFalse(store.toggle_auto_rule(1, rule["id"])["enabled"])
        self.assertEqual(store.remove_auto_rule(1, rule["id"])["id"], rule["id"])
        self.assertEqual(store.auto_rules(1), {})

    def test_duplicate_and_unknown_action_are_rejected(self):
        store = self.make_store()
        action = next(iter(AUTO_ACTION_LABELS))
        store.add_auto_rule(1, kind="action", pattern=action, offense_key="spam")
        with self.assertRaises(ValueError):
            store.add_auto_rule(1, kind="action", pattern=action, offense_key="links")
        with self.assertRaises(ValueError):
            store.add_auto_rule(1, kind="action", pattern="unknown", offense_key="spam")

    def test_rules_are_unlimited_and_bulk_words_are_deduplicated(self):
        store = self.make_store()
        for index in range(60):
            store.add_auto_rule(
                1,
                kind="word",
                pattern=f"forbidden phrase {index}",
                offense_key="insult",
            )
        result = store.add_auto_rules_bulk(
            1,
            kind="word",
            patterns=["New Word", " new   word ", "Second Word", "forbidden phrase 3"],
            offense_key="spam",
        )
        self.assertEqual(len(store.auto_rules(1)), 62)
        self.assertEqual(
            [rule["pattern"] for rule in result["created"]],
            ["new word", "second word"],
        )
        self.assertEqual(result["skipped"], ["forbidden phrase 3"])

    def test_owner_can_create_edit_reset_and_remove_offenses(self):
        store = self.make_store()
        key, entry = store.add_offense(
            1,
            label="حكم جديد",
            seconds=45 * 60,
            cell="block",
        )
        self.assertTrue(entry["custom"])
        self.assertEqual(entry["severity"], 2)
        edited = store.set_offense(1, key, label="حكم معدل", seconds=2 * 3600, cell="max")
        self.assertEqual(edited["seconds"], 2 * 3600)
        self.assertEqual(edited["cell"], "max")
        self.assertEqual(edited["severity"], 3)

        store.set_offense(1, "spam", seconds=9 * 60, cell="block")
        self.assertEqual(store.offense(1, "spam")["seconds"], 9 * 60)
        reset = store.reset_offense(1, "spam")
        self.assertEqual(reset["seconds"], 30 * 60)
        store.remove_offense(1, key)
        self.assertNotIn(key, store.offenses(1))

    def test_custom_offense_cannot_be_removed_while_auto_rule_uses_it(self):
        store = self.make_store()
        key, _entry = store.add_offense(
            1, label="مرتبط بقانون", seconds=3600, cell="holding"
        )
        store.add_auto_rule(1, kind="word", pattern="blocked", offense_key=key)
        with self.assertRaises(ValueError):
            store.remove_offense(1, key)

    def test_threshold_is_per_rule_per_member_persistent_and_repeats_forever(self):
        store = self.make_store()
        rule = store.add_auto_rule(
            1,
            kind="word",
            pattern="forbidden insult",
            offense_key="insult",
            trigger_count=4,
        )

        first = store.record_auto_rule_match(1, rule["id"], 111)
        second = store.record_auto_rule_match(1, rule["id"], 111)
        self.assertEqual((first["count"], second["count"]), (1, 2))
        self.assertFalse(second["triggered"])

        # نفس الداتا كتبقى من بعد Restart، والعداد ديال عضو آخر مستقل.
        restarted = PrisonStore.__new__(PrisonStore)
        restarted._db = store._db
        other_member = restarted.record_auto_rule_match(1, rule["id"], 222)
        third = restarted.record_auto_rule_match(1, rule["id"], 111)
        fourth = restarted.record_auto_rule_match(1, rule["id"], 111)
        self.assertEqual(other_member["count"], 1)
        self.assertEqual(third["count"], 3)
        self.assertTrue(fourth["triggered"])

        # الحكم كيعاود من الصفر لنفس العضو، ولكن القانون كيبقى شغال ديما.
        self.assertIn(rule["id"], restarted.auto_rules(1))
        again = restarted.record_auto_rule_match(1, rule["id"], 111)
        self.assertEqual(again["count"], 1)
        self.assertFalse(again["triggered"])

    def test_owner_can_change_threshold_and_linked_judgment(self):
        store = self.make_store()
        rule = store.add_auto_rule(
            1, kind="word", pattern="blocked", offense_key="spam"
        )
        store.record_auto_rule_match(1, rule["id"], 333)
        edited = store.set_auto_rule_trigger_count(1, rule["id"], 10)
        self.assertEqual(edited["trigger_count"], 10)
        self.assertNotIn(rule["id"], store.guild(1)["auto_rule_strikes"])

        changed = store.set_auto_rule_offense(1, rule["id"], "insult")
        self.assertEqual(changed["offense"], "insult")
        with self.assertRaises(ValueError):
            store.set_auto_rule_trigger_count(1, rule["id"], 0)
        with self.assertRaises(ValueError):
            store.set_auto_rule_trigger_count(1, rule["id"], 101)

    def test_removing_rule_removes_only_its_saved_member_counters(self):
        store = self.make_store()
        first = store.add_auto_rule(
            1, kind="word", pattern="first", offense_key="spam", trigger_count=4
        )
        second = store.add_auto_rule(
            1, kind="word", pattern="second", offense_key="spam", trigger_count=4
        )
        store.record_auto_rule_match(1, first["id"], 444)
        store.record_auto_rule_match(1, second["id"], 444)
        store.remove_auto_rule(1, first["id"])
        strikes = store.guild(1)["auto_rule_strikes"]
        self.assertNotIn(first["id"], strikes)
        self.assertIn(second["id"], strikes)


class AutoRuleSourceTests(unittest.TestCase):
    def test_voice_panel_shows_and_refreshes_every_inmate_timer(self):
        roster = method_source(
            PRISON_TREE, PRISON_SOURCE, "PrisonSystem", "_cell_sentence_roster"
        )
        publish = method_source(
            PRISON_TREE, PRISON_SOURCE, "PrisonSystem", "publish_cell_help_panels"
        )
        loop = method_source(PRISON_TREE, PRISON_SOURCE, "PrisonSystem", "card_loop")
        self.assertIn("remaining_seconds", roster)
        self.assertIn("format_duration", roster)
        self.assertIn("المدة الباقية لكل سجين", publish)
        self.assertIn("voice_only", publish)
        self.assertIn("voice_only=True", loop)

    def test_server_wide_rules_delete_and_use_existing_prison_pipeline(self):
        matching = method_source(
            PRISON_TREE, PRISON_SOURCE, "PrisonSystem", "_matching_auto_rules"
        )
        enforce = method_source(
            PRISON_TREE, PRISON_SOURCE, "PrisonSystem", "_enforce_auto_message_rules"
        )
        on_message = method_source(
            PRISON_TREE, PRISON_SOURCE, "PrisonSystem", "on_message"
        )
        self.assertIn('kind == "word"', matching)
        self.assertIn('kind == "domain"', matching)
        self.assertIn('kind == "action"', matching)
        self.assertIn("await message.delete()", enforce)
        self.assertIn("record_auto_rule_matches", enforce)
        self.assertIn("if not triggered", enforce)
        self.assertIn("await self.imprison(", enforce)
        self.assertIn("await self._enforce_auto_message_rules(message)", on_message)

    def test_owner_panel_has_full_rule_management(self):
        owner_panel = method_source(
            PANEL_TREE, PANEL_SOURCE, "PrisonOwnerPanelView", "auto_rules_btn"
        )
        home_names = {
            node.name
            for node in PANEL_TREE.body
            if isinstance(node, ast.ClassDef)
        }
        self.assertIn("AutoRulesHomeView", owner_panel)
        self.assertIn("AutoRulePatternModal", home_names)
        self.assertIn("AutoActionView", home_names)
        self.assertIn("AutoRuleManageView", home_names)
        self.assertIn("AutoRuleSelectedView", home_names)
        self.assertIn("AutoRuleThresholdModal", home_names)
        self.assertIn("AutoRuleChangeOffenseView", home_names)
        self.assertIn("BulkWordRulesModal", home_names)
        self.assertIn("OffenseCreateModal", home_names)
        self.assertIn("OffenseSelectedView", home_names)
        self.assertIn("add_auto_rules_bulk", PANEL_SOURCE)
        self.assertIn("set_auto_rule_trigger_count", PANEL_SOURCE)
        self.assertIn("set_auto_rule_offense", PANEL_SOURCE)
        self.assertIn('label="الأحكام والمدد"', PANEL_SOURCE)
        self.assertIn('label="القوانين والتكرارات"', PANEL_SOURCE)
        self.assertIn("DISCORD_SELECT_PAGE_SIZE", PANEL_SOURCE)


if __name__ == "__main__":
    unittest.main()
