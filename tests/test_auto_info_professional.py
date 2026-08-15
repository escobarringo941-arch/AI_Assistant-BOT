#!/usr/bin/env python3
"""Regression checks for the hourly professional Auto-Info pipeline."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def component_source(path: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    begin = text.index("# ORIGINAL SOURCE BEGIN\n") + len("# ORIGINAL SOURCE BEGIN\n")
    end = text.index("# ORIGINAL SOURCE END\n")
    guarded = text[begin:end]
    prefix = 'if globals().get("_GGMW9_COMPONENT_EXEC", False):\n'
    if not guarded.startswith(prefix):
        raise AssertionError(f"missing execution guard: {path}")
    lines = guarded[len(prefix):].splitlines(keepends=True)
    return "".join(line[4:] if line.startswith("    ") else line for line in lines)


class AutoInfoProfessionalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = component_source("cogs/bootstrap.py")
        cls.settings = component_source("cogs/settings_storage.py")
        cls.ai = component_source("cogs/ai_conversation.py")
        cls.apis = component_source("cogs/content_apis.py")
        cls.tasks = component_source("cogs/automation_tasks.py")

    def test_all_categories_start_enabled_and_run_hourly(self):
        for category in ("NEWS", "GAMES", "MOVIES", "ANIME", "MUSIC"):
            self.assertIn(f"AUTO_INFO_{category}_ENABLED = True", self.bootstrap)
        self.assertIn("AUTO_INFO_INTERVAL_HOURS = 1", self.bootstrap)
        self.assertIn("@tasks.loop(hours=AUTO_INFO_INTERVAL_HOURS)", self.tasks)
        self.assertNotIn("@tasks.loop(minutes=30)\nasync def auto_info", self.tasks)

    def test_chat_and_translation_use_separate_economic_models(self):
        self.assertIn('AI_MODEL = "openai/gpt-5.6-luna"', self.bootstrap)
        self.assertIn('AUTO_INFO_AI_MODEL = "google/gemini-2.5-flash-lite"', self.bootstrap)
        self.assertIn("primary_model=AUTO_INFO_AI_MODEL", self.apis)
        self.assertIn("fallback_models=AUTO_INFO_AI_FALLBACKS", self.apis)
        call = next(
            node for node in ast.walk(ast.parse(self.ai))
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "call_openrouter_chat"
        )
        keyword_names = {arg.arg for arg in call.args.kwonlyargs}
        self.assertTrue({"enable_web", "primary_model", "fallback_models"}.issubset(keyword_names))

    def test_fresh_start_is_one_time_and_per_channel(self):
        self.assertIn("AUTO_INFO_SETUP_VERSION", self.bootstrap)
        self.assertIn("apply_auto_info_setup_migration", self.settings)
        self.assertIn("auto_info_state.json", self.settings)
        self.assertIn("history_cleared", self.settings)
        self.assertIn("channels_cleared", self.settings)
        self.assertIn("await prepare_auto_info_fresh_start()", self.tasks)
        self.assertIn("await channel.purge(", self.tasks)
        self.assertIn("mark_auto_info_channel_cleared(channel_id)", self.tasks)
        self.assertIn("async def _purge_auto_info_channel", self.tasks)
        self.assertIn("while not bot.is_closed()", self.tasks)
        self.assertIn("if await prepare_auto_info_fresh_start()", self.tasks)
        self.assertIn("NEWS_CHANNEL_IDS + GAMES_CHANNEL_IDS + MOVIES_CHANNEL_IDS", self.tasks)
        self.assertIn("+ ANIME_CHANNEL_IDS + MUSIC_CHANNEL_IDS", self.tasks)

    def test_restart_keeps_the_real_hourly_deadline(self):
        for marker in (
            "next_dispatch_at",
            "last_dispatch_at",
            "get_auto_info_next_dispatch_at",
            "seconds_until_auto_info_dispatch",
            "reserve_auto_info_dispatch",
        ):
            self.assertIn(marker, self.settings)
        self.assertIn("if not reserve_auto_info_dispatch():", self.tasks)
        self.assertIn("remaining = seconds_until_auto_info_dispatch()", self.tasks)
        self.assertLess(
            self.tasks.index("if not reserve_auto_info_dispatch():"),
            self.tasks.index('if bot_settings["auto_info_news"]:'),
        )
        self.assertIn("next_dispatch += AUTO_INFO_INTERVAL_SECONDS", self.settings)

    def test_history_is_permanent_and_music_never_resets(self):
        self.assertNotIn("MAX_HISTORY", self.settings)
        self.assertNotIn("lst[-limit:]", self.settings)
        self.assertNotIn('reset_category_history("music")', self.apis)
        self.assertIn("mark_posted_many", self.tasks)
        self.assertIn("news_story_was_posted", self.apis)

    def test_best_content_has_quality_thresholds_images_and_ratings(self):
        for constant in (
            "AUTO_INFO_MOVIE_MIN_RATING",
            "AUTO_INFO_MOVIE_MIN_VOTES",
            "AUTO_INFO_ANIME_MIN_SCORE",
            "AUTO_INFO_GAME_MIN_RATING",
            "AUTO_INFO_GAME_MIN_RATINGS_COUNT",
        ):
            self.assertIn(constant, self.bootstrap)
            self.assertIn(constant, self.apis)
        self.assertIn("تقييم IMDb", self.tasks)
        self.assertIn("تقييم MAL", self.tasks)
        self.assertIn("تقييم RAWG", self.tasks)
        self.assertIn("مرات التشغيل", self.tasks)
        self.assertIn("embed.set_image", self.tasks)
        self.assertIn('startswith("rx")', self.apis)

    def test_item_is_recorded_only_after_successful_discord_send(self):
        for category in ("news", "games", "movies", "anime", "music"):
            self.assertIn(f'mark_posted_many("{category}"', self.tasks)
        self.assertNotIn('mark_posted("movies"', self.apis)
        self.assertNotIn('mark_posted("games"', self.apis)
        self.assertNotIn('mark_posted("anime"', self.apis)
        self.assertNotIn('mark_posted("music"', self.apis)
        self.assertNotIn('mark_posted("news"', self.apis)


if __name__ == "__main__":
    unittest.main()
