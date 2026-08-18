"""Concurrency-safe upserts for public, persistent bot panels.

The bot has a number of independent cogs which can all react to ``on_ready``
and to periodic refresh loops.  A simple ``history()`` then ``send()`` sequence
is racy: two callers can both see an empty history and create two copies.  This
module keeps a lock per bot/guild/channel/panel key and provides one small
upsert primitive shared by the split components.

It intentionally knows nothing about discord.py's concrete classes.  Callers
provide a predicate for identifying their panel, so normal user messages and
event/log messages are never touched.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable


_UNSET = object()
_LOCKS: dict[tuple[int, int, int, str], asyncio.Lock] = {}


def _message_cache(bot: Any) -> dict[tuple[int, int, str], int]:
    cache = getattr(bot, "_ggmw9_panel_message_ids", None)
    if not isinstance(cache, dict):
        cache = {}
        try:
            setattr(bot, "_ggmw9_panel_message_ids", cache)
        except Exception:
            # A very small fake Bot used by offline tests may be slotted.  The
            # helper still works without the process-local optimisation.
            pass
    return cache


def _channel_ids(channel: Any) -> tuple[int, int]:
    channel_id = int(getattr(channel, "id", channel) or 0)
    guild_id = int(getattr(getattr(channel, "guild", None), "id", 0) or 0)
    return guild_id, channel_id


def _lock_for(bot: Any, channel: Any, key: str) -> asyncio.Lock:
    guild_id, channel_id = _channel_ids(channel)
    lock_key = (id(bot), guild_id, channel_id, str(key))
    lock = _LOCKS.get(lock_key)
    if lock is None:
        lock = asyncio.Lock()
        _LOCKS[lock_key] = lock
    return lock


def panel_lock(bot: Any, channel_or_resource: Any, key: str = "panel"):
    """Return the shared async lock for a channel or guild-scoped resource."""
    return _lock_for(bot, channel_or_resource, key)


def _is_discord_exception(exc: BaseException) -> bool:
    """Return True for the transient Discord API errors we may safely ignore."""
    try:
        import discord  # imported lazily so offline source tests stay stdlib-only

        return isinstance(exc, (discord.NotFound, discord.Forbidden, discord.HTTPException))
    except Exception:
        return exc.__class__.__name__ in {"NotFound", "Forbidden", "HTTPException"}


def _discord_error_details(exc: BaseException) -> str:
    """Small, safe diagnostic for a failed panel REST operation.

    The old registry swallowed every Discord exception and callers only saw a
    generic "could not refresh" line.  That made an invalid embed, a missing
    permission and a deleted message look identical.  Status/code/text are the
    useful Discord fields and do not contain the bot token.
    """
    parts = [f"{type(exc).__name__}: {exc}"]
    for name in ("status", "code"):
        value = getattr(exc, name, None)
        if value not in (None, ""):
            parts.append(f"{name}={value}")
    text = str(getattr(exc, "text", "") or "").strip()
    if text and text not in str(exc):
        parts.append(f"details={text[:700]}")
    return " | ".join(parts)


def _normalise_embed_dict(value: Any) -> Any:
    """Return a comparable embed payload across local/API discord.py objects."""
    to_dict = getattr(value, "to_dict", None)
    if not callable(to_dict):
        return None
    try:
        payload = to_dict()
    except Exception:
        return None
    if isinstance(payload, dict):
        payload = dict(payload)
        # Discord may add the default type while a freshly built Embed omits it.
        if payload.get("type") == "rich":
            payload.pop("type", None)
    return payload


def _normalise_components(value: Any) -> Any:
    """Return the action-row payload for either a View or Message.components."""
    if value is None:
        return []
    to_components = getattr(value, "to_components", None)
    if callable(to_components):
        try:
            return to_components()
        except Exception:
            return None
    try:
        rows = list(value)
    except (TypeError, ValueError):
        return None
    output = []
    for row in rows:
        to_dict = getattr(row, "to_dict", None)
        if not callable(to_dict):
            return None
        try:
            output.append(to_dict())
        except Exception:
            return None
    return output


def _payload_is_unchanged(
    message: Any,
    *,
    content: Any,
    embed: Any,
    embeds: Any,
    view: Any,
) -> bool:
    """Compare only values supplied by the caller; unknown shapes fail open."""
    if content is not _UNSET:
        current = getattr(message, "content", None)
        if (current or None) != (content or None):
            return False

    current_embeds = list(getattr(message, "embeds", []) or [])
    if embed is not _UNSET:
        expected = [] if embed is None else [_normalise_embed_dict(embed)]
        actual = [_normalise_embed_dict(item) for item in current_embeds]
        if None in expected or None in actual or actual != expected:
            return False
    elif embeds is not _UNSET:
        expected = [_normalise_embed_dict(item) for item in list(embeds or [])]
        actual = [_normalise_embed_dict(item) for item in current_embeds]
        if None in expected or None in actual or actual != expected:
            return False

    if view is not _UNSET:
        expected_components = _normalise_components(view)
        actual_components = _normalise_components(getattr(message, "components", []))
        if (
            expected_components is None
            or actual_components is None
            or actual_components != expected_components
        ):
            return False
    return True


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def upsert_fixed_panel(
    bot: Any,
    channel: Any,
    *,
    key: str,
    matches: Callable[[Any], bool],
    embed: Any = _UNSET,
    embeds: Any = _UNSET,
    view: Any = _UNSET,
    content: Any = _UNSET,
    message_id: int | None = None,
    save_message_id: Callable[[int], Any] | None = None,
    history_limit: int | None = 100,
    trust_message_id: bool = False,
    trust_empty_channel: bool = False,
    create_if_missing: bool = True,
) -> Any | None:
    """Edit the canonical panel message, or create it once if it is missing.

    ``matches`` must be narrow and panel-specific.  Existing matching messages
    are sorted by Discord snowflake (oldest first), so the original message is
    retained.  All other matching copies are deleted while the same lock is
    held.  If history cannot be read and no trusted saved message exists, the
    function fails closed and does *not* send a new copy. ``trust_empty_channel``
    skips the first history request only for a channel that the caller has just
    created and therefore knows cannot contain an older panel.
    """
    if channel is None:
        return None

    lock = _lock_for(bot, channel, key)
    async with lock:
        candidates: list[Any] = []
        canonical: Any | None = None
        guild_id, channel_id = _channel_ids(channel)
        cache = _message_cache(bot)
        cache_key = (guild_id, channel_id, str(key))
        first_process_scan = cache_key not in cache
        fetched_id = int(message_id or cache.get(cache_key) or 0)
        cached_id = not bool(message_id) and bool(fetched_id)
        fetch_failed = False
        # A persisted ID is the strongest identity signal.  It is still
        # restricted to a bot-authored message unless the caller explicitly
        # opts out of trusting the ID.
        if fetched_id:
            try:
                fetched = await channel.fetch_message(fetched_id)
                author_ok = getattr(fetched, "author", None) == getattr(bot, "user", None)
                if trust_message_id and author_ok:
                    canonical = fetched
                    candidates.append(fetched)
                elif matches(fetched):
                    candidates.append(fetched)
                else:
                    fetch_failed = True
            except Exception as exc:
                fetch_failed = True
                if _is_discord_exception(exc):
                    print(
                        f"[PANEL-REGISTRY] {key}: fetch failed for message "
                        f"{fetched_id} in channel {channel_id} | "
                        f"{_discord_error_details(exc)}"
                    )
                if not _is_discord_exception(exc) and not isinstance(exc, (TypeError, ValueError)):
                    raise

        # First call after a real process restart performs a full migration
        # scan and removes every old duplicate, even when a saved ID exists.
        # A stale ID also triggers a full recovery scan.  Later loop/reconnect
        # refreshes use a bounded scan and the cached ID.
        # Respect the caller's explicit bound even on the first process scan.
        # The previous implementation silently changed every first scan to an
        # unbounded channel walk, so dozens of startup panels could flood the
        # REST bucket and make the Blacklist refresh fail with 429/HTTP errors.
        if first_process_scan or fetch_failed:
            scan_limit = history_limit
        else:
            scan_limit = 100 if cached_id and history_limit is None else history_limit

        history_ok = True
        known_new_empty_channel = bool(
            trust_empty_channel and first_process_scan and not fetched_id
        )
        if not known_new_empty_channel:
            try:
                async for message in channel.history(limit=scan_limit):
                    if any(getattr(message, "id", None) == getattr(item, "id", None) for item in candidates):
                        continue
                    try:
                        if matches(message):
                            candidates.append(message)
                    except Exception:
                        # A malformed old message must not stop the other panel
                        # candidates from being repaired.
                        continue
            except Exception as exc:
                if _is_discord_exception(exc):
                    history_ok = False
                    print(
                        f"[PANEL-REGISTRY] {key}: history failed in channel "
                        f"{channel_id} | {_discord_error_details(exc)}"
                    )
                else:
                    raise

        if candidates and (canonical is None or first_process_scan):
            canonical = min(candidates, key=lambda item: int(getattr(item, "id", 0) or 0))

        if canonical is None and not history_ok:
            # Never blindly send when we cannot inspect the channel: this is
            # exactly the path that creates a duplicate after a permissions or
            # transient gateway failure.
            return None

        edit_kwargs: dict[str, Any] = {}
        if content is not _UNSET:
            edit_kwargs["content"] = content
        if embed is not _UNSET:
            edit_kwargs["embed"] = embed
        if embeds is not _UNSET:
            edit_kwargs["embeds"] = embeds
        if view is not _UNSET:
            edit_kwargs["view"] = view

        if canonical is None and not create_if_missing:
            return None

        if canonical is None:
            try:
                canonical = await channel.send(**edit_kwargs)
            except Exception as exc:
                if _is_discord_exception(exc):
                    print(
                        f"[PANEL-REGISTRY] {key}: send failed in channel "
                        f"{channel_id} | {_discord_error_details(exc)}"
                    )
                    return None
                raise
        else:
            try:
                if edit_kwargs:
                    if not _payload_is_unchanged(
                        canonical,
                        content=content,
                        embed=embed,
                        embeds=embeds,
                        view=view,
                    ):
                        await canonical.edit(**edit_kwargs)
            except Exception as exc:
                if _is_discord_exception(exc):
                    print(
                        f"[PANEL-REGISTRY] {key}: edit failed for message "
                        f"{getattr(canonical, 'id', 0)} in channel {channel_id} | "
                        f"{_discord_error_details(exc)}"
                    )
                    return None
                raise

        # Remove only messages accepted by the caller's narrow predicate.
        for duplicate in candidates:
            if getattr(duplicate, "id", None) == getattr(canonical, "id", None):
                continue
            try:
                await duplicate.delete()
            except Exception as exc:
                if not _is_discord_exception(exc):
                    raise

        canonical_id = int(getattr(canonical, "id", 0) or 0)
        # Cache before the optional disk callback: a failed persistence write
        # must not make the next concurrent refresh send another message.
        if canonical_id:
            cache[cache_key] = canonical_id
        if save_message_id is not None and canonical_id:
            try:
                await _maybe_await(save_message_id(canonical_id))
            except Exception as exc:
                # The Discord message is already canonical; a local JSON write
                # failure must not make the ready handler abort all other panels.
                print(f"[PANEL-REGISTRY] could not persist {key}={canonical_id}: {exc}")
        return canonical


__all__ = ["panel_lock", "upsert_fixed_panel"]
