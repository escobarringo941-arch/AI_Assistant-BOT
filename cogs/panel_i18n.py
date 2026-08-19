# -*- coding: utf-8 -*-
"""Universal private translation layer for GGMW9 Discord panels.

Public panels remain Darija so one shared channel never flips language for every
member.  A standard language select opens a private copy for the requester and
keeps the original panel actions functional.  Responses, nested views and
modals opened from that private copy inherit the chosen language.
"""

from __future__ import annotations

import asyncio
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
from typing import Any, Awaitable, Callable
from weakref import WeakKeyDictionary

import discord


# ═══════════════════════════════════════════════════════════════════════
# ║  ZID SHI LOGHA JDIDA / ADDING A NEW PANEL LANGUAGE                   ║
# ║  Zid GHIR wahed satr hna o safi. Kolshi kayjbed men had jadwal:      ║
# ║  la liste dyal les langues, menu dyal Discord, smiya li kayakhod     ║
# ║  l'AI bach ytarjem, o l'warmup dyal la cache.                        ║
# ║                                                                       ║
# ║  code -> (label f-menu, emoji dyal l3alam, smiya b-l'anglais l-AI)   ║
# ║  "darija" hiya loghat l'masdar: kolla panel maktob biha, 3lahaqqash  ║
# ║  target dyalha = None (mahtajach terjama).                           ║
# ═══════════════════════════════════════════════════════════════════════
PANEL_LANGUAGE_MENU: dict[str, tuple[str, str, str | None]] = {
    "darija": ("Darija", "🇲🇦", None),
    "ar": ("العربية الفصحى", "🇸🇦", "Modern Standard Arabic"),
    "en": ("English", "🇬🇧", "English"),
    "fr": ("Français", "🇫🇷", "French"),
    "es": ("Español", "🇪🇸", "Spanish"),
    "it": ("Italiano", "🇮🇹", "Italian"),
}

LANGUAGES = set(PANEL_LANGUAGE_MENU)
TARGET_NAMES = {
    code: target
    for code, (_label, _emoji, target) in PANEL_LANGUAGE_MENU.items()
    if target
}
# Panels ship reviewed, hand-written copy in these three languages, so they
# render instantly and never touch the AI.  Every other language in the table
# above is produced by the translation wrapper further down - which means a
# newly added language is wired into it automatically instead of silently
# falling back to Darija.
NATIVE_LANGUAGES = {"darija", "en", "fr"}
AI_TRANSLATED_LANGUAGES = LANGUAGES - NATIVE_LANGUAGES
TRANSLATABLE_LANGUAGES = tuple(code for code in PANEL_LANGUAGE_MENU if code in TARGET_NAMES)
LANGUAGE_PLACEHOLDER = "🌐 اللغة / Language / Langue / Idioma / Lingua"

# ═══════════════════════════════════════════════════════════════════════
# ║  TRANSLATION MODEL                                                   ║
# ║  Panel translation is short, highly repetitive work, not a chat, so  ║
# ║  it runs on the cheap model first and only falls back to the         ║
# ║  expensive one when that fails.  Change these two lines to switch.   ║
# ║  Do NOT add "openrouter/free" here: it is the model that returned    ║
# ║  broken JSON and left panels rendering in Darija.                    ║
# ═══════════════════════════════════════════════════════════════════════
TRANSLATION_MODEL = "google/gemini-2.5-flash-lite"
TRANSLATION_FALLBACK_MODELS = ["openai/gpt-5.6-luna"]

_PROTECTED_RE = re.compile(
    r"<(?:(?:@!?|@&|#)[0-9]+|t:[0-9]+(?::[A-Za-z])?|a?:[^>]+)>"
    r"|https?://[^\s<>]+|discord\.gg/[^\s<>]+",
    re.IGNORECASE,
)
# Panels are authored in Darija (Arabic script).  A Latin-script target that
# comes back still containing Arabic letters was not translated at all - the
# model echoed the source.  Detecting that is what stops Spanish/Italian
# panels from silently rendering as Darija.
_ARABIC_SCRIPT_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)
_LATIN_TARGETS = {"en", "fr", "es", "it"}
# Small batches keep every reply well inside the model's output budget.  The
# previous 25-item / 9000-character batches regularly overflowed it, and a
# truncated reply made the whole batch fall back to the untranslated source.
_MAX_BATCH_ITEMS = 12
_MAX_BATCH_CHARS = 3000
_MAX_SPLIT_DEPTH = 3
# Warmup used to fire five languages at once next to the member's own live
# request.  That produced 429s, which pushed the call onto the weakest
# fallback model and back to Darija.  Two in flight is enough to stay fast.
_TRANSLATION_CONCURRENCY = asyncio.Semaphore(2)
_ACTIVE_PANEL: ContextVar[tuple[str, int, str] | None] = ContextVar(
    "ggmw9_active_panel_language", default=None
)
_UNSET = object()
_CONFIG: dict[str, Any] = {}
_CACHE: dict[str, str] = {}
_CACHE_PATH: Path | None = None
_CACHE_LOCKS: dict[str, asyncio.Lock] = {}
_ITEM_LOCKS: WeakKeyDictionary[Any, asyncio.Lock] = WeakKeyDictionary()
_WARMUP_TASKS: set[asyncio.Task[Any]] = set()
_WARMUP_KEYS: set[str] = set()
_PATCHED = False


def _cache_lock(lang: str) -> asyncio.Lock:
    key = _normalise_lang(lang)
    lock = _CACHE_LOCKS.get(key)
    if lock is None:
        lock = asyncio.Lock()
        _CACHE_LOCKS[key] = lock
    return lock


def _accepts_model_override(call_chat: Any) -> bool:
    """Check once whether the bot's chat helper takes model overrides.

    Checked by signature rather than by catching TypeError from a real call:
    a TypeError raised *after* the HTTP request would make a retry pay for the
    same translation twice.
    """
    try:
        parameters = inspect.signature(call_chat).parameters
    except (TypeError, ValueError):
        return False
    if any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD
        for parameter in parameters.values()
    ):
        return True
    return "primary_model" in parameters and "fallback_models" in parameters


def configure_panel_i18n(
    bot: Any,
    call_openrouter_chat: Callable[..., Awaitable[tuple[Any, Any]]],
    get_language: Callable[[int, int], str],
    set_language: Callable[[int, int, str], str],
    data_dir: str,
) -> Callable[[int, int, str], str]:
    """Connect the generic panel layer to the bot's existing language store."""
    global _CACHE_PATH

    def contextual_set_language(guild_id: int, user_id: int, lang: str) -> str:
        selected = _normalise_lang(set_language(guild_id, user_id, lang))
        # Existing hand-localized selectors across Economy/City/Games/etc.
        # call this shared setter immediately before responding.  Keeping the
        # selected language in the current interaction task lets the universal
        # response wrappers translate any nested panel those selectors open.
        # Darija/English/French panels already own reviewed, instant copy.
        # Every other language in PANEL_LANGUAGE_MENU needs the automatic
        # translation wrapper, so adding one to that table is enough.
        _ACTIVE_PANEL.set(
            (selected, int(user_id), "panel_session")
            if selected in AI_TRANSLATED_LANGUAGES
            else None
        )
        return selected

    _CONFIG.update(
        bot=bot,
        call_chat=call_openrouter_chat,
        call_chat_accepts_models=_accepts_model_override(call_openrouter_chat),
        get_language=get_language,
        set_language=contextual_set_language,
        raw_set_language=set_language,
    )
    _CACHE_PATH = Path(str(data_dir)) / "panel_translation_cache.json"
    try:
        loaded = json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            _CACHE.update(
                (str(key), str(value))
                for key, value in loaded.items()
                if isinstance(key, str) and isinstance(value, str)
            )
    except (OSError, ValueError, TypeError):
        pass
    _patch_discord_panel_responses()
    return contextual_set_language


def _normalise_lang(lang: Any) -> str:
    value = str(lang or "darija").lower()
    return value if value in LANGUAGES else "darija"


def _language_custom_id(panel_key: str) -> str:
    digest = hashlib.sha1(str(panel_key).encode("utf-8")).hexdigest()[:16]
    return f"ggmw9:i18n:{digest}"


def _is_language_item(item: Any) -> bool:
    custom_id = str(getattr(item, "custom_id", "") or "").lower()
    placeholder = str(getattr(item, "placeholder", "") or "").lower()
    return (
        custom_id.startswith("ggmw9:i18n:")
        or "language" in custom_id
        or "اللغة" in placeholder
        or "language" in placeholder
        or "langue" in placeholder
    )


def _language_options(lang: str) -> list[discord.SelectOption]:
    lang = _normalise_lang(lang)
    return [
        discord.SelectOption(label=label, value=code, emoji=emoji, default=lang == code)
        for code, (label, emoji, _target) in PANEL_LANGUAGE_MENU.items()
    ]


def _upgrade_language_item(item: Any) -> None:
    """Give legacy three-language selectors the universal five-language menu."""
    if not isinstance(item, discord.ui.Select):
        return
    current = "darija"
    for option in list(getattr(item, "options", []) or []):
        if bool(getattr(option, "default", False)):
            current = _normalise_lang(getattr(option, "value", "darija"))
            break
    try:
        item.options.clear()
        for option in _language_options(current):
            item.append_option(option)
        item.placeholder = LANGUAGE_PLACEHOLDER
    except Exception as exc:
        print(f"[PANEL-I18N] could not upgrade language selector: {exc}")


def _rendered_row(item: Any) -> int | None:
    row = getattr(item, "row", None)
    if row is None:
        row = getattr(item, "_rendered_row", None)
    try:
        return int(row) if row is not None else None
    except (TypeError, ValueError):
        return None


def _free_select_row(view: discord.ui.View) -> int | None:
    occupied = {
        row
        for child in view.children
        if (row := _rendered_row(child)) is not None
    }
    for row in range(4, -1, -1):
        if row not in occupied:
            return row
    return None


def attach_panel_language(view: Any, panel_key: str) -> Any:
    """Add one persistent language select unless the panel already owns one."""
    if view is None:
        view = discord.ui.View(timeout=None)
    if not isinstance(view, discord.ui.View):
        return view
    language_items = [child for child in view.children if _is_language_item(child)]
    if language_items:
        for item in language_items:
            _upgrade_language_item(item)
        return view
    row = _free_select_row(view)
    if row is None:
        print(f"[PANEL-I18N] {panel_key}: no free action row for language selector")
        return view
    try:
        view.add_item(UniversalPanelLanguageSelect(str(panel_key), row=row))
    except Exception as exc:
        print(f"[PANEL-I18N] {panel_key}: could not attach language selector: {exc}")
    return view


def panel_language_view(panel_key: str) -> discord.ui.View:
    return attach_panel_language(None, panel_key)


def _future_panel_key(target: Any, view: discord.ui.View) -> str:
    channel = getattr(target, "channel", None) or target
    channel_id = int(getattr(channel, "id", 0) or 0)
    view_type = type(view)
    identity = f"{view_type.__module__}.{view_type.__qualname__}"
    return f"future_panel:{channel_id}:{identity}"


def _auto_attach_future_panel(target: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Future-proof direct sends/edits of persistent interactive panels.

    Fixed official panels are already covered by ``upsert_fixed_panel``. This
    safety net covers a future developer sending a persistent View directly,
    while deliberately ignoring short-lived games, confirmations and alerts.
    """
    output = dict(kwargs)
    view = output.get("view")
    if isinstance(view, discord.ui.View):
        language_items = [child for child in view.children if _is_language_item(child)]
        if language_items:
            for item in language_items:
                _upgrade_language_item(item)
            output["view"] = view
            return output
    if (
        _ACTIVE_PANEL.get() is None
        and isinstance(view, discord.ui.View)
        and view.timeout is None
    ):
        output["view"] = attach_panel_language(
            view, _future_panel_key(target, view)
        )
    return output


def _protect(text: str) -> tuple[str, dict[str, str]]:
    protected: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        token = f"__GGMW9_KEEP_{len(protected)}__"
        protected[token] = match.group(0)
        return token

    return _PROTECTED_RE.sub(replace, text), protected


def _restore(text: str, protected: dict[str, str]) -> str:
    restored = str(text)
    for token, original in protected.items():
        restored = restored.replace(token, original)
    return restored


def _translation_key(lang: str, text: str) -> str:
    return hashlib.sha256(f"{lang}\0{text}".encode("utf-8")).hexdigest()


async def _save_cache() -> None:
    if _CACHE_PATH is None:
        return
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Keep the durable cache bounded while preserving the newest entries.
        items = list(_CACHE.items())[-10000:]
        payload = json.dumps(dict(items), ensure_ascii=False, indent=2)
        temporary = _CACHE_PATH.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, _CACHE_PATH)
    except OSError as exc:
        print(f"[PANEL-I18N] cache save failed: {exc}")


def _needs_translation(text: str) -> bool:
    """Pure emoji / number / mention strings have nothing to translate."""
    stripped = _PROTECTED_RE.sub(" ", str(text))
    return any(character.isalpha() for character in stripped)


def _looks_untranslated(source: str, translated: Any, lang: str) -> bool:
    """Reject a reply that is really the untouched Darija source.

    This is the guard that fixes the reported bug: a Spanish, Italian, English
    or French panel can never legitimately come back with the original Arabic
    script still in it.  When it does, the model echoed the input instead of
    translating, and the panel would render as Darija.  Returning ``True``
    sends that one string back for another attempt instead of shipping it.
    """
    if not isinstance(translated, str) or not translated.strip():
        return True
    if lang in _LATIN_TARGETS and _ARABIC_SCRIPT_RE.search(str(source)):
        if _ARABIC_SCRIPT_RE.search(translated):
            return True
        if translated.strip() == str(source).strip():
            return True
    return False


def _parse_translation_array(raw: Any, expected: int) -> list[str | None] | None:
    """Read the model reply as leniently as possible.

    A missing or malformed entry becomes ``None`` for that position only, so a
    single bad item no longer drags the whole batch back to Darija.
    """
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

    payload: Any = None
    for candidate in _json_candidates(text):
        try:
            payload = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        break
    if payload is None:
        return None

    values: Any = None
    if isinstance(payload, list):
        values = payload
    elif isinstance(payload, dict):
        for key in ("translations", "texts", "results", "output"):
            if isinstance(payload.get(key), list):
                values = payload[key]
                break
        if values is None:
            # Some models answer {"0": "...", "1": "..."} instead of a list.
            indexed = {}
            for key, value in payload.items():
                try:
                    indexed[int(str(key))] = value
                except (TypeError, ValueError):
                    continue
            if indexed:
                values = [indexed.get(index) for index in range(expected)]
    if not isinstance(values, list):
        return None

    output: list[str | None] = []
    for index in range(expected):
        value = values[index] if index < len(values) else None
        output.append(str(value) if isinstance(value, str) and value.strip() else None)
    return output


def _json_candidates(text: str) -> list[str]:
    candidates = [text]
    for opening, closing in (("{", "}"), ("[", "]")):
        start, end = text.find(opening), text.rfind(closing)
        if 0 <= start < end:
            candidates.append(text[start:end + 1])
    return candidates


async def _call_translation(messages: list[dict[str, str]], max_tokens: int) -> Any:
    call_chat = _CONFIG.get("call_chat")
    if not callable(call_chat):
        return None
    extra: dict[str, Any] = {}
    if _CONFIG.get("call_chat_accepts_models"):
        extra["primary_model"] = TRANSLATION_MODEL
        extra["fallback_models"] = list(TRANSLATION_FALLBACK_MODELS)
    async with _TRANSLATION_CONCURRENCY:
        try:
            raw, error = await call_chat(messages, int(max_tokens), 0.0, **extra)
        except Exception as exc:
            print(f"[PANEL-I18N] translation call failed: {exc}")
            return None
    return None if error else raw


async def _translate_batch(texts: list[str], lang: str) -> list[str | None]:
    """Translate one small batch.  ``None`` marks an item that must be retried."""
    target = TARGET_NAMES.get(lang)
    if not texts or target is None:
        return [None] * len(texts)
    protected_texts: list[str] = []
    protection_maps: list[dict[str, str]] = []
    for text in texts:
        protected, mapping = _protect(text)
        protected_texts.append(protected)
        protection_maps.append(mapping)
    request = json.dumps({"texts": protected_texts}, ensure_ascii=False)
    # Arabic source text is token-heavy, so the output budget is derived from
    # the real payload size instead of one fixed number that used to truncate
    # long panels into invalid JSON.
    budget = min(12000, max(1200, int(len(request) * 1.8) + 800))
    messages = [
        {
            "role": "system",
            "content": (
                f"Translate every string in texts into natural {target}. The source is "
                "Moroccan Darija written in Arabic script. Return ONLY valid JSON with "
                'exactly this schema: {"translations":["..."]}. Keep the same item count '
                "and order. Preserve all Markdown, emojis, line breaks, numbers, Discord "
                "channel/role/user mentions, timestamps, custom emoji, URLs and every "
                "__GGMW9_KEEP_N__ token exactly. Translate visible headings, descriptions, "
                "field text, buttons, select placeholders and option descriptions. Never "
                f"copy a source string unchanged - every string must be rewritten in {target}. "
                "Do not add explanations."
            ),
        },
        {"role": "user", "content": request},
    ]
    raw = await _call_translation(messages, budget)
    values = _parse_translation_array(raw, len(texts))
    if values is None:
        print(f"[PANEL-I18N] {lang} batch reply was unusable, retrying smaller")
        return [None] * len(texts)
    output: list[str | None] = []
    for index, value in enumerate(values):
        if value is None:
            output.append(None)
            continue
        restored = _restore(value, protection_maps[index])
        output.append(
            None if _looks_untranslated(texts[index], restored, lang) else restored
        )
    return output


async def _translate_single(text: str, lang: str) -> str | None:
    """Last-resort per-string attempt using plain text instead of JSON.

    Weaker fallback models answer a plain 'translate this' prompt reliably even
    when they cannot produce a correct JSON array, so this rescues the strings
    that the batch path could not deliver.
    """
    target = TARGET_NAMES.get(lang)
    if target is None:
        return None
    protected, mapping = _protect(text)
    messages = [
        {
            "role": "system",
            "content": (
                f"You are a translator. Translate the user's message from Moroccan Darija "
                f"into natural {target}. Reply with ONLY the translation, no quotes, no "
                "explanation, no extra line. Keep every emoji, Markdown symbol, number, "
                "URL, Discord mention and __GGMW9_KEEP_N__ token exactly where it is. "
                "Never reply with the original text."
            ),
        },
        {"role": "user", "content": protected},
    ]
    budget = min(4000, max(300, len(protected) * 3 + 200))
    raw = await _call_translation(messages, budget)
    if not isinstance(raw, str) or not raw.strip():
        return None
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[A-Za-z]*\s*", "", candidate)
        candidate = re.sub(r"\s*```$", "", candidate).strip()
    restored = _restore(candidate, mapping)
    return None if _looks_untranslated(text, restored, lang) else restored


async def _translate_group(
    texts: list[str], lang: str, depth: int = 0
) -> dict[str, str]:
    """Translate a group, halving and retrying whatever came back unusable."""
    results: dict[str, str] = {}
    if not texts:
        return results
    values = await _translate_batch(texts, lang)
    pending: list[str] = []
    for text, value in zip(texts, values):
        if value is None:
            pending.append(text)
        else:
            results[text] = value
    if not pending:
        return results
    if len(pending) == 1 or depth >= _MAX_SPLIT_DEPTH:
        for text in pending:
            single = await _translate_single(text, lang)
            if single is not None:
                results[text] = single
            else:
                print(f"[PANEL-I18N] {lang}: keeping source for one string")
        return results
    middle = len(pending) // 2
    for half in (pending[:middle], pending[middle:]):
        results.update(await _translate_group(half, lang, depth + 1))
    return results


async def _translate_texts(texts: list[str], lang: str) -> dict[str, str]:
    lang = _normalise_lang(lang)
    unique = list(dict.fromkeys(str(text) for text in texts if str(text).strip()))
    if lang == "darija" or not unique:
        return {text: text for text in unique}

    result: dict[str, str] = {}
    missing: list[str] = []
    for text in unique:
        cached = _CACHE.get(_translation_key(lang, text))
        if cached is None:
            missing.append(text)
        else:
            result[text] = cached
    if not missing:
        return result

    async with _cache_lock(lang):
        still_missing: list[str] = []
        for text in missing:
            cached = _CACHE.get(_translation_key(lang, text))
            if cached is None:
                still_missing.append(text)
            else:
                result[text] = cached

        changed = False
        translatable: list[str] = []
        for text in still_missing:
            if _needs_translation(text):
                translatable.append(text)
                continue
            # Emoji/number-only labels are stored as-is.  Previously they were
            # never cached (translation == source), so every panel refresh sent
            # them to the API again and helped trigger the rate limits that made
            # real strings fall back to Darija.
            result[text] = text
            _CACHE[_translation_key(lang, text)] = text
            changed = True

        batch: list[str] = []
        batch_chars = 0
        batches: list[list[str]] = []
        for text in translatable:
            if batch and (
                len(batch) >= _MAX_BATCH_ITEMS
                or batch_chars + len(text) > _MAX_BATCH_CHARS
            ):
                batches.append(batch)
                batch, batch_chars = [], 0
            batch.append(text)
            batch_chars += len(text)
        if batch:
            batches.append(batch)

        for current in batches:
            values = await _translate_group(current, lang)
            for source in current:
                translated = values.get(source)
                if translated is None:
                    # Every attempt failed: keep the Darija source so the panel
                    # still renders, and do not poison the cache with it.
                    result[source] = source
                    continue
                result[source] = translated
                _CACHE[_translation_key(lang, source)] = translated
                changed = True
        if changed:
            await _save_cache()
    return result


async def translate_panel_text(text: str, lang: str) -> str:
    """Translate one dynamic Owner-provided label through the shared cache.

    Prison judgments created or renamed from the Owner panel use this helper
    to persist all translated names. That keeps later Blacklist refreshes
    fully localized without making a new AI request for every member click.
    """
    source = str(text or "").strip()
    lang = _normalise_lang(lang)
    if not source or lang == "darija":
        return source
    translated = await _translate_texts([source], lang)
    return str(translated.get(source, source) or source).strip()


def _component_specs(view: Any) -> tuple[list[Any], list[dict[str, Any]]]:
    if not isinstance(view, discord.ui.View):
        return [], []
    items: list[Any] = []
    specs: list[dict[str, Any]] = []
    for child in view.children:
        if _is_language_item(child):
            continue
        spec: dict[str, Any] = {
            "label": getattr(child, "label", None),
            "placeholder": getattr(child, "placeholder", None),
            "options": [],
        }
        for option in list(getattr(child, "options", []) or []):
            spec["options"].append(
                {
                    "label": getattr(option, "label", None),
                    "description": getattr(option, "description", None),
                }
            )
        items.append(child)
        specs.append(spec)
    return items, specs


def _collect_slots(
    content: Any,
    embeds: list[dict[str, Any]],
    components: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[tuple[dict[str, Any], str]]]:
    holder = {
        "content": content,
        "embeds": deepcopy(embeds),
        "components": deepcopy(components),
    }
    slots: list[tuple[dict[str, Any], str]] = []

    def add(container: dict[str, Any], key: str) -> None:
        value = container.get(key)
        if isinstance(value, str) and value.strip():
            slots.append((container, key))

    if isinstance(holder["content"], str) and holder["content"].strip():
        slots.append((holder, "content"))
    for embed in holder["embeds"]:
        add(embed, "title")
        add(embed, "description")
        if isinstance(embed.get("footer"), dict):
            add(embed["footer"], "text")
        if isinstance(embed.get("author"), dict):
            add(embed["author"], "name")
        for field in embed.get("fields", []) or []:
            if isinstance(field, dict):
                add(field, "name")
                add(field, "value")
    for component in holder["components"]:
        add(component, "label")
        add(component, "placeholder")
        for option in component.get("options", []) or []:
            if isinstance(option, dict):
                add(option, "label")
                add(option, "description")
    return holder, slots


def _trim(value: Any, limit: int) -> Any:
    return str(value)[:limit] if isinstance(value, str) else value


def _fit_embed_dicts(embeds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fitted = deepcopy(embeds[:10])
    for embed in fitted:
        if "title" in embed:
            embed["title"] = _trim(embed["title"], 256)
        if "description" in embed:
            embed["description"] = _trim(embed["description"], 4096)
        footer = embed.get("footer")
        if isinstance(footer, dict) and "text" in footer:
            footer["text"] = _trim(footer["text"], 2048)
        author = embed.get("author")
        if isinstance(author, dict) and "name" in author:
            author["name"] = _trim(author["name"], 256)
        fields = embed.get("fields")
        if isinstance(fields, list):
            embed["fields"] = fields[:25]
            for field in embed["fields"]:
                if isinstance(field, dict):
                    field["name"] = _trim(field.get("name", "\u200b"), 256)
                    field["value"] = _trim(field.get("value", "\u200b"), 1024)

    def total_chars() -> int:
        total = 0
        for embed in fitted:
            total += len(str(embed.get("title", "")))
            total += len(str(embed.get("description", "")))
            total += len(str((embed.get("footer") or {}).get("text", "")))
            total += len(str((embed.get("author") or {}).get("name", "")))
            for field in embed.get("fields", []) or []:
                total += len(str(field.get("name", ""))) + len(str(field.get("value", "")))
        return total

    # Discord's 6000-character limit is shared across all embeds in a message.
    while total_chars() > 5900:
        candidate = None
        for embed in fitted:
            for field in embed.get("fields", []) or []:
                value = str(field.get("value", ""))
                if len(value) > 80 and (candidate is None or len(value) > len(candidate[0])):
                    candidate = (value, field, "value")
            description = str(embed.get("description", ""))
            if len(description) > 120 and (candidate is None or len(description) > len(candidate[0])):
                candidate = (description, embed, "description")
        if candidate is None:
            break
        value, container, key = candidate
        container[key] = value[: max(40, len(value) - 200)].rstrip() + "…"
    return fitted


async def _translated_parts(
    content: Any,
    embed_dicts: list[dict[str, Any]],
    source_view: Any,
    lang: str,
) -> tuple[Any, list[dict[str, Any]], list[Any], list[dict[str, Any]]]:
    items, specs = _component_specs(source_view)
    holder, slots = _collect_slots(content, embed_dicts, specs)
    translations = await _translate_texts(
        [str(container[key]) for container, key in slots], lang
    )
    for container, key in slots:
        source = str(container[key])
        container[key] = translations.get(source, source)
    return (
        holder["content"],
        _fit_embed_dicts(holder["embeds"]),
        items,
        holder["components"],
    )


def _warmup_languages(view: Any) -> tuple[str, ...]:
    """Languages this panel genuinely has to buy from the AI.

    A panel wearing the universal selector is Darija-only, so every other
    language on it is machine-made and worth pre-caching.  A panel that owns a
    hand-written selector already has reviewed English and French copy, so only
    the AI-served languages need warming.
    """
    children = list(getattr(view, "children", []) or [])
    if any(isinstance(child, UniversalPanelLanguageSelect) for child in children):
        return TRANSLATABLE_LANGUAGES
    return tuple(
        code for code in TRANSLATABLE_LANGUAGES if code in AI_TRANSLATED_LANGUAGES
    )


def schedule_panel_translation_warmup(
    content: Any,
    embeds: list[Any],
    source_view: Any,
) -> None:
    """Pre-cache every non-Darija panel language in the background.

    Publishing stays non-blocking. By the time members use a normal fixed
    panel, its translations are usually already cached and switching languages
    only performs the Discord message edit.
    """
    if not callable(_CONFIG.get("call_chat")):
        return
    embed_dicts: list[dict[str, Any]] = []
    for embed in list(embeds or [])[:10]:
        if isinstance(embed, dict):
            embed_dicts.append(deepcopy(embed))
        elif hasattr(embed, "to_dict"):
            try:
                embed_dicts.append(embed.to_dict())
            except Exception:
                continue
    view = source_view if isinstance(source_view, discord.ui.View) else discord.ui.View(timeout=None)
    _items, specs = _component_specs(view)
    holder, slots = _collect_slots(content, embed_dicts, specs)
    source_texts = [str(container[key]) for container, key in slots]
    if not source_texts:
        return
    signature = hashlib.sha256(
        json.dumps(source_texts, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if signature in _WARMUP_KEYS:
        return

    async def warm() -> None:
        # A panel that carries its own language selector already ships reviewed
        # Darija/English/French copy, so warming those three would pay for
        # translations nobody ever displays.  Only a Darija-only panel wearing
        # the universal selector needs every language pre-cached.
        languages = _warmup_languages(view)
        # One language at a time.  Firing them together used to collide with
        # the member's own live request and trigger 429s, which pushed the call
        # onto the weakest fallback model and back to untranslated Darija.
        for language in languages:
            try:
                await _translate_texts(source_texts, language)
            except Exception as exc:
                print(f"[PANEL-I18N] {language} warmup failed: {exc}")

    try:
        task = asyncio.create_task(warm())
    except RuntimeError:
        return
    _WARMUP_KEYS.add(signature)
    _WARMUP_TASKS.add(task)

    def finished(done: asyncio.Task[Any]) -> None:
        _WARMUP_TASKS.discard(done)
        _WARMUP_KEYS.discard(signature)
        try:
            done.result()
        except Exception as exc:
            print(f"[PANEL-I18N] translation warmup failed: {exc}")

    task.add_done_callback(finished)


def _schedule_outgoing_panel_warmup(content: Any, kwargs: dict[str, Any]) -> None:
    view = kwargs.get("view")
    if not isinstance(view, discord.ui.View):
        return
    if not any(_is_language_item(child) for child in view.children):
        return
    embed_values: list[Any] = []
    if kwargs.get("embeds") is not None:
        embed_values = list(kwargs.get("embeds") or [])
    elif kwargs.get("embed") is not None:
        embed_values = [kwargs["embed"]]
    schedule_panel_translation_warmup(
        None if content is _UNSET else content,
        embed_values,
        view,
    )


async def _run_source_item(
    source_view: discord.ui.View,
    source_item: Any,
    translated_item: Any,
    interaction: discord.Interaction,
    lang: str,
    panel_key: str,
) -> None:
    token = _ACTIVE_PANEL.set((lang, int(interaction.user.id), panel_key))
    try:
        lock = _ITEM_LOCKS.get(source_item)
        if lock is None:
            lock = asyncio.Lock()
            _ITEM_LOCKS[source_item] = lock
        async with lock:
            allowed = await source_view.interaction_check(interaction)
            if not allowed:
                return
            old_values = getattr(source_item, "_values", _UNSET)
            try:
                if hasattr(source_item, "_values") and hasattr(translated_item, "values"):
                    source_item._values = list(translated_item.values)
                await source_item.callback(interaction)
            finally:
                if old_values is not _UNSET:
                    source_item._values = old_values
    except Exception as exc:
        await source_view.on_error(interaction, exc, source_item)
    finally:
        _ACTIVE_PANEL.reset(token)


def _common_select_kwargs(source: Any, spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "custom_id": getattr(source, "custom_id", None),
        "placeholder": _trim(spec.get("placeholder"), 150),
        "min_values": int(getattr(source, "min_values", 1) or 0),
        "max_values": int(getattr(source, "max_values", 1) or 1),
        "disabled": bool(getattr(source, "disabled", False)),
        "row": _rendered_row(source),
    }


def _clone_item(
    source_view: discord.ui.View,
    source: Any,
    spec: dict[str, Any],
    lang: str,
    panel_key: str,
) -> Any | None:
    try:
        if isinstance(source, discord.ui.Button):
            clone = discord.ui.Button(
                style=source.style,
                label=_trim(spec.get("label"), 80),
                disabled=source.disabled,
                custom_id=source.custom_id,
                url=source.url,
                emoji=source.emoji,
                row=_rendered_row(source),
            )
        elif isinstance(source, discord.ui.ChannelSelect):
            kwargs = _common_select_kwargs(source, spec)
            kwargs["channel_types"] = getattr(source, "channel_types", None)
            default_values = getattr(source, "default_values", None)
            if default_values:
                kwargs["default_values"] = default_values
            try:
                clone = discord.ui.ChannelSelect(**kwargs)
            except TypeError:
                kwargs.pop("default_values", None)
                clone = discord.ui.ChannelSelect(**kwargs)
        elif isinstance(source, discord.ui.UserSelect):
            kwargs = _common_select_kwargs(source, spec)
            default_values = getattr(source, "default_values", None)
            if default_values:
                kwargs["default_values"] = default_values
            try:
                clone = discord.ui.UserSelect(**kwargs)
            except TypeError:
                kwargs.pop("default_values", None)
                clone = discord.ui.UserSelect(**kwargs)
        elif isinstance(source, discord.ui.RoleSelect):
            kwargs = _common_select_kwargs(source, spec)
            default_values = getattr(source, "default_values", None)
            if default_values:
                kwargs["default_values"] = default_values
            try:
                clone = discord.ui.RoleSelect(**kwargs)
            except TypeError:
                kwargs.pop("default_values", None)
                clone = discord.ui.RoleSelect(**kwargs)
        elif isinstance(source, discord.ui.MentionableSelect):
            kwargs = _common_select_kwargs(source, spec)
            default_values = getattr(source, "default_values", None)
            if default_values:
                kwargs["default_values"] = default_values
            try:
                clone = discord.ui.MentionableSelect(**kwargs)
            except TypeError:
                kwargs.pop("default_values", None)
                clone = discord.ui.MentionableSelect(**kwargs)
        elif isinstance(source, discord.ui.Select):
            options: list[discord.SelectOption] = []
            translated_options = spec.get("options", []) or []
            for index, option in enumerate(list(source.options or [])):
                translated = translated_options[index] if index < len(translated_options) else {}
                options.append(
                    discord.SelectOption(
                        label=_trim(translated.get("label") or option.label, 100),
                        value=option.value,
                        description=_trim(translated.get("description"), 100),
                        emoji=option.emoji,
                        default=option.default,
                    )
                )
            clone = discord.ui.Select(options=options, **_common_select_kwargs(source, spec))
        else:
            return None

        if not (isinstance(clone, discord.ui.Button) and (clone.url or getattr(clone, "sku_id", None))):
            async def proxy(interaction: discord.Interaction, _source=source, _clone=clone):
                await _run_source_item(
                    source_view, _source, _clone, interaction, lang, panel_key
                )
            clone.callback = proxy
        return clone
    except Exception as exc:
        print(f"[PANEL-I18N] could not clone {type(source).__name__}: {exc}")
        return None


class TranslatedPanelView(discord.ui.View):
    def __init__(
        self,
        source_view: discord.ui.View,
        owner_id: int,
        lang: str,
        panel_key: str,
        source_content: Any,
        source_embeds: list[dict[str, Any]],
        source_items: list[Any],
        component_specs: list[dict[str, Any]],
    ):
        super().__init__(timeout=1800)
        self.source_view = source_view
        self.owner_id = int(owner_id)
        self.lang = _normalise_lang(lang)
        self.panel_key = str(panel_key)
        self.source_content = source_content
        self.source_embeds = deepcopy(source_embeds)
        for source, spec in zip(source_items, component_specs):
            clone = _clone_item(source_view, source, spec, self.lang, self.panel_key)
            if clone is not None:
                try:
                    self.add_item(clone)
                except Exception as exc:
                    print(f"[PANEL-I18N] could not add translated component: {exc}")
        row = _free_select_row(self)
        if row is not None:
            self.add_item(
                UniversalPanelLanguageSelect(
                    self.panel_key,
                    lang=self.lang,
                    row=row,
                    owner_id=self.owner_id,
                    source_content=self.source_content,
                    source_embeds=self.source_embeds,
                    source_view=self.source_view,
                )
            )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if int(interaction.user.id) == self.owner_id:
            return True
        await interaction.response.send_message(
            "❌ This private translated panel belongs to another member.", ephemeral=True
        )
        return False


def _embeds_from_dicts(values: list[dict[str, Any]]) -> list[discord.Embed]:
    output: list[discord.Embed] = []
    for value in values:
        try:
            output.append(discord.Embed.from_dict(value))
        except Exception as exc:
            print(f"[PANEL-I18N] invalid translated embed: {exc}")
    return output


class UniversalPanelLanguageSelect(discord.ui.Select):
    def __init__(
        self,
        panel_key: str,
        lang: str = "darija",
        *,
        row: int,
        owner_id: int | None = None,
        source_content: Any = _UNSET,
        source_embeds: list[dict[str, Any]] | None = None,
        source_view: discord.ui.View | None = None,
    ):
        self.panel_key = str(panel_key)
        self.lang = _normalise_lang(lang)
        self.owner_id = int(owner_id) if owner_id is not None else None
        self.source_content = source_content
        self.source_embeds = deepcopy(source_embeds) if source_embeds is not None else None
        self.source_view = source_view
        super().__init__(
            placeholder=LANGUAGE_PLACEHOLDER,
            options=_language_options(self.lang),
            min_values=1,
            max_values=1,
            custom_id=_language_custom_id(self.panel_key),
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        if self.owner_id is not None and int(interaction.user.id) != self.owner_id:
            await interaction.response.send_message(
                "❌ This private translated panel belongs to another member.", ephemeral=True
            )
            return
        lang = _normalise_lang(self.values[0])
        guild_id = int(interaction.guild.id) if interaction.guild else 0
        setter = _CONFIG.get("raw_set_language")
        if callable(setter):
            lang = _normalise_lang(setter(guild_id, int(interaction.user.id), lang))

        message = interaction.message
        source_content = (
            getattr(message, "content", None)
            if self.source_content is _UNSET
            else self.source_content
        )
        source_embeds = (
            [embed.to_dict() for embed in list(getattr(message, "embeds", []) or [])]
            if self.source_embeds is None
            else deepcopy(self.source_embeds)
        )
        source_view = self.source_view or self.view
        if not isinstance(source_view, discord.ui.View):
            source_view = discord.ui.View(timeout=None)

        # Public selector: create exactly one private original response.
        # Private selector: defer a message update, then edit that same message.
        # In both cases no follow-up message is created.
        if self.owner_id is None:
            await interaction.response.defer(ephemeral=True, thinking=True)
        else:
            await interaction.response.defer()
        content, embeds, items, specs = await _translated_parts(
            source_content, source_embeds, source_view, lang
        )
        translated_view = TranslatedPanelView(
            source_view,
            interaction.user.id,
            lang,
            self.panel_key,
            source_content,
            source_embeds,
            items,
            specs,
        )
        kwargs: dict[str, Any] = {
            "content": _trim(content, 2000) if isinstance(content, str) and content else None,
            "view": translated_view,
        }
        rendered_embeds = _embeds_from_dicts(embeds)
        kwargs["embeds"] = rendered_embeds
        await interaction.edit_original_response(**kwargs)


async def _translate_outgoing(
    content: Any,
    kwargs: dict[str, Any],
    active: tuple[str, int, str],
) -> tuple[Any, dict[str, Any]]:
    lang, owner_id, panel_key = active
    output = dict(kwargs)
    source_view = output.get("view")
    embed_mode = None
    embed_dicts: list[dict[str, Any]] = []
    if output.get("embed") is not None:
        embed_mode = "embed"
        embed_dicts = [output["embed"].to_dict()]
    elif output.get("embeds") is not None:
        embed_mode = "embeds"
        embed_dicts = [embed.to_dict() for embed in list(output["embeds"] or [])]

    translated_content, translated_embeds, items, specs = await _translated_parts(
        content if content is not _UNSET else None,
        embed_dicts,
        source_view,
        lang,
    )
    if content is not _UNSET:
        content = _trim(translated_content, 2000)
    rendered = _embeds_from_dicts(translated_embeds)
    if embed_mode == "embed":
        output["embed"] = rendered[0] if rendered else output.get("embed")
    elif embed_mode == "embeds":
        output["embeds"] = rendered
    if isinstance(source_view, discord.ui.View):
        output["view"] = TranslatedPanelView(
            source_view,
            owner_id,
            lang,
            panel_key,
            content if content is not _UNSET else None,
            embed_dicts,
            items,
            specs,
        )
    return content, output


async def _translate_modal(modal: Any, active: tuple[str, int, str]) -> Any:
    lang, _owner_id, panel_key = active
    slots: list[tuple[Any, str]] = []
    if isinstance(getattr(modal, "title", None), str):
        slots.append((modal, "title"))
    for child in list(getattr(modal, "children", []) or []):
        for key in ("label", "placeholder"):
            if isinstance(getattr(child, key, None), str):
                slots.append((child, key))
    translations = await _translate_texts(
        [str(getattr(container, key)) for container, key in slots], lang
    )
    for container, key in slots:
        source = str(getattr(container, key))
        try:
            limit = 45 if key in {"title", "label"} else 100
            setattr(container, key, _trim(translations.get(source, source), limit))
        except Exception:
            pass
    original_submit = modal.on_submit

    async def translated_submit(interaction: discord.Interaction):
        token = _ACTIVE_PANEL.set((lang, int(interaction.user.id), panel_key))
        try:
            await original_submit(interaction)
        finally:
            _ACTIVE_PANEL.reset(token)

    try:
        modal.on_submit = translated_submit
    except (AttributeError, TypeError):
        pass
    return modal


def _patch_discord_panel_responses() -> None:
    global _PATCHED
    if _PATCHED:
        return
    _PATCHED = True

    original_response_send = discord.InteractionResponse.send_message
    original_response_defer = discord.InteractionResponse.defer
    original_interaction_edit = discord.Interaction.edit_original_response
    original_messageable_send = discord.abc.Messageable.send

    async def messageable_send(self, content=_UNSET, *args, **kwargs):
        kwargs = _auto_attach_future_panel(self, kwargs)
        _schedule_outgoing_panel_warmup(content, kwargs)
        if content is _UNSET:
            return await original_messageable_send(self, *args, **kwargs)
        return await original_messageable_send(self, content, *args, **kwargs)

    discord.abc.Messageable.send = messageable_send

    def final_edit_fields(content: Any, kwargs: dict[str, Any], fallback_content: Any) -> dict[str, Any]:
        fields: dict[str, Any] = {}
        fields["content"] = fallback_content if content is _UNSET else content
        for key in ("embed", "embeds", "view", "attachments", "allowed_mentions"):
            if key in kwargs:
                fields[key] = kwargs[key]
        return fields

    async def response_send(self, content=_UNSET, *args, **kwargs):
        active = _ACTIVE_PANEL.get()
        if active is None:
            kwargs = _auto_attach_future_panel(getattr(self, "_parent", self), kwargs)
        if active is not None:
            # A first-time AI translation can take longer than Discord's
            # three-second acknowledgement window.  Acknowledge immediately,
            # then replace the small private placeholder with the translated
            # panel.  Special payloads such as files/polls keep the normal path.
            special = any(
                key in kwargs for key in ("file", "files", "poll", "delete_after", "tts")
            )
            if not special and getattr(self, "_parent", None) is not None:
                response = await original_response_defer(
                    self,
                    ephemeral=bool(kwargs.get("ephemeral", False)),
                    thinking=True,
                )
                content, kwargs = await _translate_outgoing(content, kwargs, active)
                await original_interaction_edit(
                    self._parent,
                    **final_edit_fields(content, kwargs, None),
                )
                return response
            content, kwargs = await _translate_outgoing(content, kwargs, active)
        if content is _UNSET:
            return await original_response_send(self, *args, **kwargs)
        return await original_response_send(self, content, *args, **kwargs)

    discord.InteractionResponse.send_message = response_send

    original_response_edit = discord.InteractionResponse.edit_message

    async def response_edit(self, **kwargs):
        active = _ACTIVE_PANEL.get()
        if active is None:
            kwargs = _auto_attach_future_panel(getattr(self, "_parent", self), kwargs)
        if active is not None:
            parent = getattr(self, "_parent", None)
            original_content = getattr(getattr(parent, "message", None), "content", None)
            if parent is not None:
                response = await original_response_defer(self)
            content = kwargs.pop("content", _UNSET)
            content, kwargs = await _translate_outgoing(content, kwargs, active)
            if parent is not None:
                await original_interaction_edit(
                    parent,
                    **final_edit_fields(content, kwargs, original_content),
                )
                return response
            if content is not _UNSET:
                kwargs["content"] = content
        return await original_response_edit(self, **kwargs)

    discord.InteractionResponse.edit_message = response_edit

    original_send_modal = discord.InteractionResponse.send_modal

    async def response_modal(self, modal):
        active = _ACTIVE_PANEL.get()
        if active is not None:
            modal = await _translate_modal(modal, active)
        return await original_send_modal(self, modal)

    discord.InteractionResponse.send_modal = response_modal

    original_webhook_send = discord.Webhook.send

    async def webhook_send(self, content=_UNSET, *args, **kwargs):
        active = _ACTIVE_PANEL.get()
        if active is None:
            kwargs = _auto_attach_future_panel(self, kwargs)
        if active is not None:
            content, kwargs = await _translate_outgoing(content, kwargs, active)
        if content is _UNSET:
            return await original_webhook_send(self, *args, **kwargs)
        return await original_webhook_send(self, content, *args, **kwargs)

    discord.Webhook.send = webhook_send

    async def interaction_edit(self, **kwargs):
        active = _ACTIVE_PANEL.get()
        if active is None:
            kwargs = _auto_attach_future_panel(self, kwargs)
        if active is not None:
            content = kwargs.pop("content", _UNSET)
            content, kwargs = await _translate_outgoing(content, kwargs, active)
            if content is not _UNSET:
                kwargs["content"] = content
        return await original_interaction_edit(self, **kwargs)

    discord.Interaction.edit_original_response = interaction_edit

    original_message_edit = discord.Message.edit

    async def message_edit(self, **kwargs):
        active = _ACTIVE_PANEL.get()
        if active is None:
            kwargs = _auto_attach_future_panel(self, kwargs)
            _schedule_outgoing_panel_warmup(kwargs.get("content", _UNSET), kwargs)
        if active is not None:
            content = kwargs.pop("content", _UNSET)
            content, kwargs = await _translate_outgoing(content, kwargs, active)
            if content is not _UNSET:
                kwargs["content"] = content
        return await original_message_edit(self, **kwargs)

    discord.Message.edit = message_edit


__all__ = [
    "attach_panel_language",
    "configure_panel_i18n",
    "panel_language_view",
    "translate_panel_text",
]
