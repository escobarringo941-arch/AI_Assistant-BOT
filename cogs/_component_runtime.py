# -*- coding: utf-8 -*-
"""Shared execution namespace for the mechanically split GGMW9 extensions.

The original bot was one module, so its functions intentionally shared one global
namespace.  These helpers keep that exact property while Discord loads each ordered
feature file as a normal extension from ``cogs``.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import MappingProxyType
from typing import Any


_RUNTIME_NAME = "ggmw9_runtime"
_shared: dict[str, Any] = {
    "__name__": _RUNTIME_NAME,
    "__package__": None,
    "_GGMW9_COMPONENT_EXEC": False,
}
_loaded_components: set[str] = set()
_root_file: Path | None = None
_bot = None
_missing = object()
_component_events: dict[str, dict[str, Any]] = {}
_component_loops: dict[str, tuple[str, ...]] = {}


def _decorator_name(node) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _registered_names(source: str, filename: str):
    tree = ast.parse(source, filename=filename)
    events = []
    loops = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = {_decorator_name(item) for item in node.decorator_list}
        if "bot.event" in names:
            events.append(node.name)
        if "tasks.loop" in names:
            loops.append(node.name)
    return tuple(events), tuple(loops)


def _restore_component_events(module_name: str) -> None:
    active_bot = _shared.get("bot")
    if active_bot is None:
        return
    for event_name, previous in _component_events.pop(module_name, {}).items():
        current = active_bot.__dict__.get(event_name, _missing)
        if current is _missing or getattr(current, "__module__", None) != module_name:
            continue
        if previous is _missing:
            del active_bot.__dict__[event_name]
        else:
            setattr(active_bot, event_name, previous)


def _cancel_component_loops(module_name: str) -> None:
    for loop_name in _component_loops.pop(module_name, ()):
        loop = _shared.get(loop_name)
        cancel = getattr(loop, "cancel", None)
        if cancel is not None:
            cancel()


def _execute(path: Path, module_name: str) -> None:
    if module_name in _loaded_components:
        return

    source = path.read_text(encoding="utf-8")
    event_names, loop_names = _registered_names(source, str(path))
    active_bot = _shared.get("bot")
    previous_events = {
        name: active_bot.__dict__.get(name, _missing)
        for name in event_names
    } if active_bot is not None else {}

    old_name = _shared.get("__name__", _RUNTIME_NAME)
    old_package = _shared.get("__package__")
    old_flag = _shared.get("_GGMW9_COMPONENT_EXEC", False)
    _shared["__name__"] = module_name
    _shared["__package__"] = module_name.rpartition(".")[0] or None
    _shared["_GGMW9_COMPONENT_EXEC"] = True
    try:
        exec(compile(source, str(path), "exec"), _shared, _shared)
    except Exception:
        _component_events[module_name] = previous_events
        _component_loops[module_name] = loop_names
        _restore_component_events(module_name)
        _cancel_component_loops(module_name)
        raise
    finally:
        _shared["__name__"] = old_name
        _shared["__package__"] = old_package
        _shared["_GGMW9_COMPONENT_EXEC"] = old_flag
    _component_events[module_name] = previous_events
    _component_loops[module_name] = loop_names
    _loaded_components.add(module_name)


def bootstrap_component(component_file: str, module_name: str):
    global _root_file, _bot
    path = Path(component_file).resolve()
    if _bot is None:
        _root_file = path.parent.parent / "ai_bot.py"
        _shared["__file__"] = str(_root_file)
        _execute(path, module_name)
        _bot = _shared["bot"]
    return _bot


def install_component(bot, component_file: str, module_name: str) -> None:
    if _bot is None or bot is not _bot:
        raise RuntimeError("GGMW9 component loaded before the shared bot bootstrap")
    _execute(Path(component_file).resolve(), module_name)


def uninstall_component(module_name: str) -> None:
    _restore_component_events(module_name)
    _cancel_component_loops(module_name)
    _loaded_components.discard(module_name)


def runtime_namespace() -> dict[str, Any]:
    return _shared


def runtime_view():
    return MappingProxyType(_shared)


def runtime_value(name: str) -> Any:
    try:
        return _shared[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
