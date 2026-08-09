#!/usr/bin/env python3
"""Offline discord.py registration probe; it never connects to Discord."""

from __future__ import annotations

import asyncio
import json
import os


_real_makedirs = os.makedirs


def _probe_makedirs(path, *args, **kwargs):
    # The production bot intentionally uses /app/data (Railway volume). The
    # validation container has a read-only /app, so only bypass that one mkdir.
    if os.fspath(path) == "/app/data":
        return None
    return _real_makedirs(path, *args, **kwargs)


os.makedirs = _probe_makedirs

import ai_bot


def _app_names(commands):
    names = []
    for command in commands:
        names.append(command.qualified_name)
        children = getattr(command, "commands", None)
        if children:
            names.extend(_app_names(children))
    return names


async def main():
    bot = ai_bot.bot
    await bot.setup_hook()

    expected = set(ai_bot.GAMES_COGS)
    if hasattr(ai_bot, "CORE_COGS"):
        expected.update(ai_bot.CORE_COGS)
    missing = sorted(expected.difference(bot.extensions))

    result = {
        "missing_extensions": missing,
        "extensions": sorted(bot.extensions),
        "cogs": sorted(bot.cogs),
        "prefix_commands": sorted(
            {
                command.qualified_name
                for command in bot.walk_commands()
                if command.qualified_name != "help"
            }
        ),
        "app_commands": sorted(set(_app_names(bot.tree.get_commands()))),
        "persistent_views": sorted(type(view).__name__ for view in bot.persistent_views),
        "bridge_keys": sorted(getattr(bot, "gg", {})),
    }
    print("RUNTIME_PROBE=" + json.dumps(result, ensure_ascii=False, sort_keys=True))

    if missing:
        raise SystemExit(f"extensions failed to load: {missing}")

    await bot.close()


if __name__ == "__main__":
    asyncio.run(main())
