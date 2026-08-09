#!/usr/bin/env python3
"""Pure offline tests for the temporary-room music allocation policy."""

from __future__ import annotations

import unittest
from pathlib import Path
import sys
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cogs.temp_music_policy import (
    TEMP_MUSIC_BOT_IDS,
    TEMP_MUSIC_BOT_POOL,
    TEMP_ROOM_EMPTY_GRACE_SECONDS,
    TEMP_ROOM_HOUSEKEEPING_SECONDS,
    TEMP_ROOM_ORPHAN_MIN_AGE_SECONDS,
    choose_next_music_bot_id,
    get_music_bot_profile,
    has_human_members,
    is_managed_temp_name,
    normalize_music_bot_id,
    plan_music_bot_leases,
)


EXPECTED_BOT_IDS = (
    1241477316891250789,
    411916947773587456,
    412347257233604609,
    412347553141751808,
    412347780841865216,
)


class MusicBotPoolTests(unittest.TestCase):
    def test_pool_has_five_unique_bots_in_stable_priority_order(self):
        self.assertEqual(TEMP_MUSIC_BOT_IDS, EXPECTED_BOT_IDS)
        self.assertEqual(len(TEMP_MUSIC_BOT_POOL), 5)
        self.assertEqual(len(set(TEMP_MUSIC_BOT_IDS)), 5)
        self.assertEqual(TEMP_MUSIC_BOT_POOL[0].name, "SeshTunes")
        self.assertEqual(
            [profile.provider for profile in TEMP_MUSIC_BOT_POOL],
            ["seshtunes", "jockie", "jockie", "jockie", "jockie"],
        )

    def test_profiles_have_actionable_official_metadata(self):
        for profile in TEMP_MUSIC_BOT_POOL:
            with self.subTest(profile=profile.name):
                self.assertGreater(profile.user_id, 0)
                self.assertTrue(profile.name)
                self.assertTrue(profile.commands_url.startswith("https://"))
                self.assertTrue(profile.dashboard_url.startswith("https://"))
                self.assertTrue(profile.join_hint)
                self.assertTrue(profile.play_hint)

    def test_normalize_accepts_configured_ints_and_numeric_strings(self):
        for bot_id in EXPECTED_BOT_IDS:
            with self.subTest(bot_id=bot_id):
                self.assertEqual(normalize_music_bot_id(bot_id), bot_id)
                self.assertEqual(normalize_music_bot_id(str(bot_id)), bot_id)

    def test_normalize_rejects_bad_or_unconfigured_values(self):
        for value in (None, "", "not-a-number", 0, -1, 123456789):
            with self.subTest(value=value):
                self.assertIsNone(normalize_music_bot_id(value))

    def test_profile_lookup_uses_normalized_id(self):
        for expected in TEMP_MUSIC_BOT_POOL:
            with self.subTest(profile=expected.name):
                self.assertEqual(get_music_bot_profile(str(expected.user_id)), expected)
        self.assertIsNone(get_music_bot_profile("unknown"))

    def test_allocator_chooses_first_free_bot_in_pool_order(self):
        self.assertEqual(choose_next_music_bot_id([]), EXPECTED_BOT_IDS[0])
        self.assertEqual(
            choose_next_music_bot_id([EXPECTED_BOT_IDS[0]]),
            EXPECTED_BOT_IDS[1],
        )
        self.assertEqual(
            choose_next_music_bot_id([EXPECTED_BOT_IDS[0], EXPECTED_BOT_IDS[2]]),
            EXPECTED_BOT_IDS[1],
        )

    def test_allocator_ignores_invalid_and_duplicate_assignments(self):
        assigned = [
            "invalid",
            EXPECTED_BOT_IDS[0],
            str(EXPECTED_BOT_IDS[0]),
            None,
        ]
        self.assertEqual(choose_next_music_bot_id(assigned), EXPECTED_BOT_IDS[1])

    def test_sixth_room_waits_when_pool_is_exhausted(self):
        self.assertIsNone(choose_next_music_bot_id(EXPECTED_BOT_IDS))

    def test_stable_leases_do_not_reshuffle_when_oldest_room_closes(self):
        room_states = [
            (2, True, EXPECTED_BOT_IDS[1], 20),
            (3, True, EXPECTED_BOT_IDS[2], 30),
            (4, True, EXPECTED_BOT_IDS[3], 40),
            (5, True, EXPECTED_BOT_IDS[4], 50),
            (6, True, None, 60),
        ]
        planned = plan_music_bot_leases(room_states)
        self.assertEqual(planned[2], EXPECTED_BOT_IDS[1])
        self.assertEqual(planned[3], EXPECTED_BOT_IDS[2])
        self.assertEqual(planned[4], EXPECTED_BOT_IDS[3])
        self.assertEqual(planned[5], EXPECTED_BOT_IDS[4])
        self.assertEqual(planned[6], EXPECTED_BOT_IDS[0])

    def test_planner_assigns_only_five_and_repairs_duplicates(self):
        room_states = [
            (room_id, True, EXPECTED_BOT_IDS[0] if room_id in {1, 2} else None, room_id)
            for room_id in range(1, 7)
        ]
        planned = plan_music_bot_leases(room_states)
        assigned = [bot_id for bot_id in planned.values() if bot_id is not None]
        self.assertEqual(len(assigned), 5)
        self.assertEqual(len(set(assigned)), 5)
        self.assertEqual(planned[1], EXPECTED_BOT_IDS[0])
        self.assertIsNone(planned[6])

    def test_ineligible_rooms_release_their_lease(self):
        planned = plan_music_bot_leases([
            (1, False, EXPECTED_BOT_IDS[0], 1),
            (2, True, None, 2),
        ])
        self.assertIsNone(planned[1])
        self.assertEqual(planned[2], EXPECTED_BOT_IDS[0])


class TempRoomCleanupPolicyTests(unittest.TestCase):
    @staticmethod
    def member(*, bot: bool):
        return SimpleNamespace(bot=bot)

    def test_empty_room_has_no_humans(self):
        self.assertFalse(has_human_members([]))

    def test_bots_never_keep_a_temp_room_alive(self):
        members = [self.member(bot=True), self.member(bot=True)]
        self.assertFalse(has_human_members(members))

    def test_one_human_keeps_a_temp_room_alive(self):
        members = [self.member(bot=True), self.member(bot=False)]
        self.assertTrue(has_human_members(members))

    def test_unknown_member_shape_is_treated_conservatively_as_human(self):
        self.assertTrue(has_human_members([object()]))

    def test_cleanup_timing_constants_are_safe_and_positive(self):
        self.assertGreaterEqual(TEMP_ROOM_EMPTY_GRACE_SECONDS, 0)
        self.assertGreater(TEMP_ROOM_HOUSEKEEPING_SECONDS, 0)
        self.assertGreaterEqual(
            TEMP_ROOM_ORPHAN_MIN_AGE_SECONDS,
            TEMP_ROOM_EMPTY_GRACE_SECONDS,
        )


class ManagedRoomNameTests(unittest.TestCase):
    def test_exact_template_shape_is_recognized(self):
        template = "🔊 روم ديال {name}"
        self.assertTrue(is_managed_temp_name("🔊 روم ديال Aya", template))
        self.assertTrue(is_managed_temp_name("🔊 روم ديال Aya Smith", template))

    def test_prefix_and_suffix_are_both_required(self):
        template = "temp-{name}-voice"
        self.assertTrue(is_managed_temp_name("temp-Aya-voice", template))
        self.assertFalse(is_managed_temp_name("other-Aya-voice", template))
        self.assertFalse(is_managed_temp_name("temp-Aya-other", template))

    def test_empty_owner_name_is_not_managed(self):
        self.assertFalse(is_managed_temp_name("🔊 روم ديال ", "🔊 روم ديال {name}"))
        self.assertFalse(is_managed_temp_name("temp--voice", "temp-{name}-voice"))

    def test_template_without_name_marker_is_rejected(self):
        self.assertFalse(is_managed_temp_name("fixed-room", "fixed-room"))


if __name__ == "__main__":
    unittest.main()
