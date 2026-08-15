#!/usr/bin/env python3
"""Static regression checks for the professional Birthday Center."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
BIRTHDAY = (ROOT / "cogs" / "birthday_center.py").read_text(encoding="utf-8")
BOOTSTRAP = (ROOT / "cogs" / "bootstrap.py").read_text(encoding="utf-8")
ENTRYPOINT = (ROOT / "ai_bot.py").read_text(encoding="utf-8")
READONLY = (ROOT / "cogs" / "panel_channels_readonly.py").read_text(encoding="utf-8")


class BirthdayCenterSourceTests(unittest.TestCase):
    def test_center_channel_is_panel_only_and_auto_cleaned(self):
        self.assertIn("BIRTHDAY_CENTER_CHANNEL_ID = 1533241235630854224", BOOTSTRAP)
        self.assertIn('"cogs.birthday_center"', ENTRYPOINT)
        self.assertIn('getattr(core, "BIRTHDAY_CENTER_CHANNEL_ID", 0)', READONLY)
        self.assertIn("await channel.purge(", BIRTHDAY)
        self.assertIn("limit=None if full else 200", BIRTHDAY)
        self.assertIn("not self.is_center_message(message)", BIRTHDAY)

    def test_panel_has_all_private_actions(self):
        for marker in (
            "سجل / عدّل عيد ميلادي",
            "الملف ديالي",
            "أقرب أعياد الميلاد",
            "البحث عن عضو",
            "حذف عيد ميلادي",
            "BirthdayMemberSelect",
        ):
            self.assertIn(marker, BIRTHDAY)
        self.assertIn("timeout=None", BIRTHDAY)
        self.assertIn("ephemeral=True", BIRTHDAY)

    def test_profiles_show_avatar_zodiac_and_member_dates(self):
        for marker in (
            "display_avatar",
            "تاريخ الميلاد",
            "البرج",
            "داخل السيرفر من",
            "الحساب تخلق فـ",
            "next_occurrence",
        ):
            self.assertIn(marker, BIRTHDAY)

    def test_midnight_role_and_announcement_are_restart_safe(self):
        self.assertIn('BIRTHDAY_TIMEZONE = "Africa/Casablanca"', BOOTSTRAP)
        self.assertIn("last_announced_year", BIRTHDAY)
        self.assertIn("day_expires_at", BIRTHDAY)
        self.assertIn("sync_birthday_role", BIRTHDAY)
        self.assertIn("AllowedMentions(everyone=True", BIRTHDAY)
        self.assertIn("@everyone", BIRTHDAY)
        self.assertIn("@tasks.loop(seconds=30)", BIRTHDAY)

    def test_gender_copy_multiple_birthdays_and_wish_thread(self):
        self.assertIn('return "male"', BIRTHDAY)
        self.assertIn('return "female"', BIRTHDAY)
        self.assertIn("أكثر من فرحة", BIRTHDAY)
        self.assertIn("هنّيه / هنّيها", BIRTHDAY)
        self.assertIn("congratulated_by", BIRTHDAY)
        self.assertIn("await message.create_thread(", BIRTHDAY)
        self.assertIn("archived=True, locked=True", BIRTHDAY)


if __name__ == "__main__":
    unittest.main()
