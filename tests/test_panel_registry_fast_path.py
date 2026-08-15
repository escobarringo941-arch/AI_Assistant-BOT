#!/usr/bin/env python3
"""Runtime regression check for newly-created channel panel fast path."""

from __future__ import annotations

import unittest

from cogs.panel_registry import upsert_fixed_panel


class FakeMessage:
    def __init__(self, message_id: int, author):
        self.id = message_id
        self.author = author


class FakeChannel:
    def __init__(self):
        self.id = 222
        self.guild = type("Guild", (), {"id": 111})()
        self.history_calls = 0
        self.send_calls = 0

    def history(self, *, limit=None):
        self.history_calls += 1
        raise AssertionError("fresh channel fast path must not request history")

    async def send(self, **kwargs):
        self.send_calls += 1
        return FakeMessage(333, kwargs.get("author"))


class FakeBot:
    def __init__(self):
        self.user = object()


class PanelRegistryFastPathTests(unittest.IsolatedAsyncioTestCase):
    async def test_trusted_new_channel_sends_without_history_request(self):
        bot = FakeBot()
        channel = FakeChannel()

        message = await upsert_fixed_panel(
            bot,
            channel,
            key="new-temp-panel",
            matches=lambda candidate: candidate.author == bot.user,
            content="panel",
            trust_empty_channel=True,
        )

        self.assertEqual(message.id, 333)
        self.assertEqual(channel.history_calls, 0)
        self.assertEqual(channel.send_calls, 1)


if __name__ == "__main__":
    unittest.main()
