#!/usr/bin/env python3
"""Static validation for the reviewed ai_bot Cog component baseline."""

from __future__ import annotations

import ast
import hashlib
import json
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "cogs" / "_component_manifest.json").read_text(encoding="utf-8"))


def component_source(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    begin = text.index("# ORIGINAL SOURCE BEGIN\n") + len("# ORIGINAL SOURCE BEGIN\n")
    end = text.index("# ORIGINAL SOURCE END\n")
    guarded = text[begin:end]
    prefix = 'if globals().get("_GGMW9_COMPONENT_EXEC", False):\n'
    if not guarded.startswith(prefix):
        raise AssertionError(f"missing execution guard in {path}")
    body_lines = guarded[len(prefix):].splitlines(keepends=True)
    if any(line.strip() and not line.startswith("    ") for line in body_lines):
        raise AssertionError(f"invalid source indentation in {path}")
    return "".join(line[4:] if line.startswith("    ") else line for line in body_lines)


def decorators(tree):
    commands = []
    events = []
    loops = []
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            rendered = ast.unparse(decorator)
            if rendered.startswith(("bot.command", "bot.hybrid_command")):
                commands.append(node.name)
            elif rendered == "bot.event":
                events.append(node.name)
            elif rendered.startswith("tasks.loop"):
                loops.append(node.name)
    return commands, events, loops


def main() -> None:
    rebuilt = []
    for item in MANIFEST["components"]:
        path = ROOT / item["path"]
        source = component_source(path)
        actual = hashlib.sha256(source.encode("utf-8")).hexdigest()
        if actual != item["sha256"]:
            raise AssertionError(f"source changed unexpectedly: {item['path']}")
        rebuilt.append(source)
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    joined = "".join(rebuilt)
    if hashlib.sha256(joined.encode("utf-8")).hexdigest() != MANIFEST["joined_sha256"]:
        raise AssertionError("ordered component source no longer matches the reviewed manifest")

    tree = ast.parse(joined, filename="ai_bot.reviewed-components.py")
    commands, events, loops = decorators(tree)
    if len(commands) != 72:
        raise AssertionError(f"expected 72 commands, found {len(commands)}")
    if events != MANIFEST["events_before_setup_hook"]:
        raise AssertionError(f"event mismatch: {events}")
    if loops != MANIFEST["task_loops"]:
        raise AssertionError(f"task-loop mismatch: {loops}")

    entrypoint = (ROOT / "ai_bot.py").read_text(encoding="utf-8")
    ast.parse(entrypoint, filename="ai_bot.py")
    if len(entrypoint.splitlines()) > 220:
        raise AssertionError("ai_bot.py is no longer the small bootstrap entrypoint")

    for path in ROOT.rglob("*.py"):
        if "__pycache__" not in path.parts:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    print(
        f"OK: {len(MANIFEST['components'])} components, "
        f"{len(commands)} commands, {len(events) + 1} bot events including setup_hook, "
        f"{len(loops)} task loops; all Python files parse."
    )


if __name__ == "__main__":
    main()
