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
-------
U+200F (RIGHT-TO-LEFT MARK, "RLM") is an invisible Unicode character that
tells the renderer "treat this line as RTL from here". Prepending it to any
Arabic line that doesn't already start with an Arabic letter fixes the line
direction.

Mixed Arabic/Latin counters need one more guard.  Discord can render the
logical text ``30 دقيقة`` as ``دقيقة 30`` inside embeds and select-option
descriptions.  Numeric Arabic phrases are therefore wrapped in an invisible
left-to-right embedding (LRE/PDF).  The words and numbers are unchanged; only
their visual order is stabilised.

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
          set_author), plain message content (Messageable.send,
          InteractionResponse.send_message/edit_message, Webhook.send,
          Message.edit), and UI text (select options/placeholders, buttons,
          text inputs and modal titles).

Every patch below is wrapped in try/except: if a discord.py version ever
changes one of these signatures, that one patch is skipped (logged once)
instead of crashing the whole bot.
"""
from __future__ import annotations

import re

RLM = "\u200f"
LRE = "\u202a"
PDF = "\u202c"
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_BIDI_CONTROL_RE = re.compile(r"[\u200e\u200f\u202a-\u202e\u2066-\u2069]")
_NUMBER_ARABIC_PHRASE_RE = re.compile(
    r"(?<![\w<])"
    r"([0-9\u0660-\u0669]+(?:[.,:/-][0-9\u0660-\u0669]+)*"
    r"\s+[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+)"
)


def _line_needs_rlm(line: str) -> bool:
    if not line or line.startswith(RLM):
        return False
    if not _ARABIC_RE.search(line):
        return False
    for ch in line:
        if ch.isalpha():
            return _ARABIC_RE.match(ch) is None
    return False


def _stabilize_mixed_numbers(text: str) -> str:
    """Keep ``number + Arabic word`` in logical order in mixed-direction UI.

    LRE/PDF are deliberately used instead of LRI/PDI here.  Discord's select
    menus and embed renderer keep the Arabic word on the expected side with
    an embedding, while an isolate can still flip the unit on some clients.
    Existing bidi-controlled strings are left untouched to avoid nesting.
    """
    if not _ARABIC_RE.search(text) or _BIDI_CONTROL_RE.search(text):
        return text
    return _NUMBER_ARABIC_PHRASE_RE.sub(
        lambda match: f"{LRE}{match.group(1)}{PDF}", text
    )


def auto_rtl(text):
    """Prefix every Arabic-but-misreads-as-LTR line in *text* with RLM.
    Non-strings, empty strings, and non-Arabic text pass through untouched.
    """
    if not isinstance(text, str) or not text:
        return text
    lines = []
    for line in text.split("\n"):
        fixed = _stabilize_mixed_numbers(line)
        lines.append((RLM + fixed) if _line_needs_rlm(fixed) else fixed)
    return "\n".join(lines)


def _ui_text(text, limit: int):
    """Apply bidi controls without crossing Discord's component text limit."""
    if not isinstance(text, str):
        return text
    candidate = text
    fixed = auto_rtl(candidate)
    while len(fixed) > int(limit) and candidate:
        candidate = candidate[:-1]
        fixed = auto_rtl(candidate)
    return fixed


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

    # ---- UI component text: options, placeholders, labels and modal titles ----
    # Prison judgments and many other panels put durations in SelectOption
    # descriptions, which bypass all message/embed patches above.
    def _patch_select_option():
        orig = discord.SelectOption.__init__

        def _init(self, *args, **kwargs):
            args = list(args)
            if args:
                args[0] = _ui_text(args[0], 100)
            if "label" in kwargs:
                kwargs["label"] = _ui_text(kwargs["label"], 100)
            if "description" in kwargs:
                kwargs["description"] = _ui_text(kwargs["description"], 100)
            return orig(self, *args, **kwargs)

        discord.SelectOption.__init__ = _init

    _safe_patch("SelectOption.__init__", _patch_select_option)

    def _patch_ui_init(cls, limits):
        orig = cls.__init__

        def _init(self, *args, **kwargs):
            for name, limit in limits.items():
                if name in kwargs:
                    kwargs[name] = _ui_text(kwargs[name], limit)
            return orig(self, *args, **kwargs)

        cls.__init__ = _init

    _safe_patch(
        "ui.Button.__init__",
        lambda: _patch_ui_init(discord.ui.Button, {"label": 80}),
    )
    _safe_patch(
        "ui.Select.__init__",
        lambda: _patch_ui_init(discord.ui.Select, {"placeholder": 150}),
    )
    _safe_patch(
        "ui.TextInput.__init__",
        lambda: _patch_ui_init(
            discord.ui.TextInput,
            {"label": 45, "placeholder": 100, "default": 4000},
        ),
    )
    _safe_patch(
        "ui.Modal.__init__",
        lambda: _patch_ui_init(discord.ui.Modal, {"title": 45}),
    )

    print("[RTL PATCH] Darija/Arabic RTL auto-fix active for messages and UI components.")
