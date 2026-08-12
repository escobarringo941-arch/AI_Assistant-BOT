# -*- coding: utf-8 -*-
"""Global Discord RTL (right-to-left) rendering fix for Arabic/Darija text.

THE PROBLEM
------------
Discord decides a *line's* direction from its first "strong" Unicode
character. Almost every Darija line in this bot starts with an emoji, a
digit, or a backtick-code (e.g. "📚 التعليم", "`PLOT-01` مملوكة"). Discord
reads that leading character as LTR and renders the whole line left-to-right
— even though every word after it is Arabic.

THE FIX
--------
U+200F (RIGHT-TO-LEFT MARK, "RLM") is an invisible Unicode character that
tells the renderer "treat this line as RTL from here". Prepending it to any
Arabic line that doesn't already start with an Arabic letter fixes the
rendering, with zero visual side effect.

WHY A GLOBAL PATCH INSTEAD OF EDITING EVERY STRING
----------------------------------------------------
This bot builds embeds/messages in dozens of cogs. Hand-editing every
literal string is a huge, error-prone diff. Instead, this module patches
discord.py **once, at startup**, so every embed (title/description/fields/
footer/author) and every plain message this bot ever sends — in ANY cog,
present or future — is auto-corrected transparently. Nothing elsewhere in
the codebase needs to change.

SCOPE (intentionally conservative)
------------------------------------
Patched:  discord.Embed (title, description, add_field, set_footer,
          set_author) + plain message content (Messageable.send,
          InteractionResponse.send_message/edit_message, Webhook.send,
          Message.edit).
NOT patched: discord.ui component labels/placeholders and Modal titles.
In this codebase's own convention, emoji is always passed as a *separate*
`emoji=` kwarg on buttons/selects (never concatenated into the label text),
and modal titles are plain Arabic words with no leading emoji — so those
already render correctly RTL and don't need the fix. Leaving them alone
also avoids touching less-stable internal discord.py hooks.

Every patch below is wrapped in try/except: if a discord.py version ever
changes one of these signatures, that one patch is skipped (logged once)
instead of crashing the whole bot.
"""
from __future__ import annotations

import re

RLM = "\u200f"
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")


def _line_needs_rlm(line: str) -> bool:
    if not line or line.startswith(RLM):
        return False
    if not _ARABIC_RE.search(line):
        return False
    for ch in line:
        if ch.isalpha():
            return _ARABIC_RE.match(ch) is None
    return False


def auto_rtl(text):
    """Prefix every Arabic-but-misreads-as-LTR line in *text* with RLM.
    Non-strings, empty strings, and non-Arabic text pass through untouched.
    """
    if not isinstance(text, str) or not text:
        return text
    return "\n".join(
        (RLM + line) if _line_needs_rlm(line) else line
        for line in text.split("\n")
    )


_PATCHED = False


def patch_discord_rtl():
    """Monkeypatch discord.py once so Arabic/Darija text renders RTL
    everywhere the bot sends it, without touching individual cogs.
    Safe to call more than once (no-op after the first call)."""
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    import discord

    def _safe_patch(label, fn):
        try:
            fn()
        except Exception as exc:  # pragma: no cover - defensive only
            print(f"[RTL PATCH] skipped '{label}': {exc!r}")

    # ---- Embed: title / description ----
    def _patch_embed_init():
        orig_init = discord.Embed.__init__

        def _init(self, *args, **kwargs):
            if "title" in kwargs:
                kwargs["title"] = auto_rtl(kwargs["title"])
            if "description" in kwargs:
                kwargs["description"] = auto_rtl(kwargs["description"])
            return orig_init(self, *args, **kwargs)

        discord.Embed.__init__ = _init

    _safe_patch("Embed.__init__", _patch_embed_init)

    # ---- Embed: add_field(name=, value=) ----
    def _patch_add_field():
        orig = discord.Embed.add_field

        def _add_field(self, *, name=None, value=None, inline=True):
            return orig(self, name=auto_rtl(name), value=auto_rtl(value), inline=inline)

        discord.Embed.add_field = _add_field

    _safe_patch("Embed.add_field", _patch_add_field)

    # ---- Embed: set_footer(text=) ----
    def _patch_set_footer():
        orig = discord.Embed.set_footer

        def _set_footer(self, *, text=None, icon_url=None):
            return orig(self, text=auto_rtl(text), icon_url=icon_url)

        discord.Embed.set_footer = _set_footer

    _safe_patch("Embed.set_footer", _patch_set_footer)

    # ---- Embed: set_author(name=) ----
    def _patch_set_author():
        orig = discord.Embed.set_author

        def _set_author(self, *, name=None, url=None, icon_url=None):
            return orig(self, name=auto_rtl(name), url=url, icon_url=icon_url)

        discord.Embed.set_author = _set_author

    _safe_patch("Embed.set_author", _patch_set_author)

    # ---- Plain message content: channel.send / member.send / DM ----
    # A sentinel (not None) preserves "content not passed at all" exactly as
    # discord.py's own default behaves — some internals distinguish
    # "omitted" from "explicitly None", so we never invent a value that
    # wasn't there.
    _MISSING = object()

    def _patch_messageable_send():
        import discord.abc as _abc

        orig = _abc.Messageable.send

        async def _send(self, content=_MISSING, *args, **kwargs):
            if content is _MISSING:
                return await orig(self, *args, **kwargs)
            return await orig(self, auto_rtl(content), *args, **kwargs)

        _abc.Messageable.send = _send

    _safe_patch("Messageable.send", _patch_messageable_send)

    # ---- interaction.response.send_message(content=...) ----
    def _patch_response_send_message():
        orig = discord.InteractionResponse.send_message

        async def _send_message(self, content=_MISSING, *args, **kwargs):
            if content is _MISSING:
                return await orig(self, *args, **kwargs)
            return await orig(self, auto_rtl(content), *args, **kwargs)

        discord.InteractionResponse.send_message = _send_message

    _safe_patch("InteractionResponse.send_message", _patch_response_send_message)

    # ---- interaction.response.edit_message(content=...) ----
    def _patch_response_edit_message():
        orig = discord.InteractionResponse.edit_message

        async def _edit_message(self, **kwargs):
            if "content" in kwargs and kwargs["content"] is not None:
                kwargs["content"] = auto_rtl(kwargs["content"])
            return await orig(self, **kwargs)

        discord.InteractionResponse.edit_message = _edit_message

    _safe_patch("InteractionResponse.edit_message", _patch_response_edit_message)

    # ---- interaction.followup.send(...) / any Webhook.send(...) ----
    def _patch_webhook_send():
        orig = discord.Webhook.send

        async def _send(self, content=_MISSING, *args, **kwargs):
            if content is _MISSING:
                return await orig(self, *args, **kwargs)
            return await orig(self, auto_rtl(content), *args, **kwargs)

        discord.Webhook.send = _send

    _safe_patch("Webhook.send", _patch_webhook_send)

    # ---- message.edit(content=...) — used when panels update in place ----
    def _patch_message_edit():
        orig = discord.Message.edit

        async def _edit(self, **kwargs):
            if "content" in kwargs and kwargs["content"] is not None:
                kwargs["content"] = auto_rtl(kwargs["content"])
            return await orig(self, **kwargs)

        discord.Message.edit = _edit

    _safe_patch("Message.edit", _patch_message_edit)

    print("[RTL PATCH] Darija/Arabic RTL auto-fix active for embeds and messages.")
