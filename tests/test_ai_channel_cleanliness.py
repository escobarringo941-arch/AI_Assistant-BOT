#!/usr/bin/env python3
"""Static regression checks for the professional, channel-only AI chat."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TARGET_CHANNEL_ID = 1526384339670270012


def component_source(path: str) -> str:
    text = (ROOT / path).read_text(encoding="utf-8")
    begin_marker = "# ORIGINAL SOURCE BEGIN\n"
    end_marker = "# ORIGINAL SOURCE END\n"
    begin = text.index(begin_marker) + len(begin_marker)
    end = text.index(end_marker)
    guarded = text[begin:end]
    prefix = 'if globals().get("_GGMW9_COMPONENT_EXEC", False):\n'
    if not guarded.startswith(prefix):
        raise AssertionError(f"missing component execution guard: {path}")
    lines = guarded[len(prefix):].splitlines(keepends=True)
    return "".join(line[4:] if line.startswith("    ") else line for line in lines)


def find_function(source: str, name: str) -> ast.AsyncFunctionDef:
    module = ast.parse(source)
    for node in ast.walk(module):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function not found: {name}")


class AIChannelCleanlinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bootstrap = component_source("cogs/bootstrap.py")
        cls.ai = component_source("cogs/ai_conversation.py")
        cls.events = component_source("cogs/member_events.py")
        cls.commands = component_source("cogs/general_commands.py")

    def test_chat_channel_and_economy_limits_are_fixed(self):
        self.assertIn(f"TARGET_CHANNEL_ID = {TARGET_CHANNEL_ID}", self.bootstrap)
        self.assertIn('AI_MODEL = "deepseek/deepseek-v4-flash"', self.bootstrap)
        self.assertIn("AI_MAX_OUTPUT_TOKENS = 320", self.bootstrap)
        self.assertIn("AI_MAX_PROMPT_CHARS = 2500", self.bootstrap)
        self.assertIn("AI_USER_COOLDOWN_SECONDS = 6", self.bootstrap)

    def test_plain_messages_are_hard_gated_before_ai_call(self):
        rendered = ast.unparse(find_function(self.events, "on_message"))
        gate = "if message.channel.id != TARGET_CHANNEL_ID"
        self.assertIn(gate, rendered)
        self.assertLess(rendered.index(gate), rendered.index("await ask_ai"))
        self.assertIn("ai_chat_inflight", rendered)
        self.assertIn("AI_USER_COOLDOWN_SECONDS", rendered)

    def test_slash_chat_is_silent_outside_the_ai_channel(self):
        rendered = ast.unparse(find_function(self.commands, "chat"))
        self.assertIn("if ctx.channel.id != TARGET_CHANNEL_ID", rendered)
        self.assertLess(rendered.index("if ctx.channel.id != TARGET_CHANNEL_ID"), rendered.index("await ask_ai"))
        outside_gate = rendered.split("await ask_ai", 1)[0]
        self.assertNotIn("await ctx.send", outside_gate)

    def test_ai_prompt_and_output_have_independent_cleanliness_guards(self):
        self.assertIn("ممنوع عليك السب", self.ai)
        self.assertIn("sanitize_ai_reply(reply)", self.ai)
        self.assertIn('"provider": {"sort": "price"}', self.ai)
        self.assertIn("AI_MAX_OUTPUT_TOKENS", self.ai)
        self.assertNotIn("server_memory.append", self.ai)

    def test_old_random_insult_replies_are_not_in_message_handler(self):
        rendered = ast.unparse(find_function(self.events, "on_message")).lower()
        old_reply_fragments = ("ggmw9", "wld l9ahba", "nik mok", "9a7ba", "zamel", "tabon")
        for fragment in old_reply_fragments:
            self.assertNotIn(fragment, rendered)


if __name__ == "__main__":
    unittest.main()
