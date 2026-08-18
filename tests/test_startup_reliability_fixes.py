#!/usr/bin/env python3
"""Static regression checks for startup/panel/role reliability fixes."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = (ROOT / "cogs" / "bootstrap.py").read_text(encoding="utf-8")
ACCESS = (ROOT / "cogs" / "access_panels.py").read_text(encoding="utf-8")
PERSISTENT = (ROOT / "cogs" / "persistent_state.py").read_text(encoding="utf-8")
OWNER = (ROOT / "cogs" / "owner_control.py").read_text(encoding="utf-8")
LOCKDOWN = (ROOT / "cogs" / "channel_lockdown.py").read_text(encoding="utf-8")


class StartupReliabilityFixTests(unittest.TestCase):
    def test_ephemeral_helper_never_passes_a_none_view(self):
        self.assertIn('kwargs = {"content": content}', BOOTSTRAP)
        self.assertIn('if view is not None:', BOOTSTRAP)
        self.assertNotIn('kwargs = {"content": content, "view": view}', BOOTSTRAP)

    def test_blacklist_is_bounded_and_has_bounded_retries(self):
        self.assertIn("BLACKLIST_EMBED_MAX_CHARS = 5800", ACCESS)
        self.assertIn("_add_bounded_blacklist_fields", ACCESS)
        self.assertIn("len(embed.fields) >= 24", ACCESS)
        self.assertIn("for attempt, delay in enumerate((0, 2, 5), start=1)", ACCESS)
        self.assertIn("من بعد 3 محاولات", ACCESS)

    def test_level_role_api_and_hierarchy_failures_are_reported(self):
        self.assertIn("class LevelRoleSyncResult", PERSISTENT)
        self.assertIn("البوت ماعندوش Manage Roles", PERSISTENT)
        self.assertIn("role >= bot_member.top_role", PERSISTENT)
        self.assertIn("_level_role_http_detail", PERSISTENT)
        self.assertIn('"error_details": error_details', PERSISTENT)
        self.assertIn("أخطاء حقيقية", OWNER)

    def test_lockdown_policy_remains_enabled_and_separate(self):
        self.assertIn("class ChannelLockdown", LOCKDOWN)
        self.assertIn("if role.managed", LOCKDOWN)
        self.assertIn("administrator_bypass_report", LOCKDOWN)


if __name__ == "__main__":
    unittest.main()
