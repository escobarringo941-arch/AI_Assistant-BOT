#!/usr/bin/env python3
"""Static integration checks for Temp Music; imports neither discord.py nor ai_bot."""

from __future__ import annotations

import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "cogs" / "_component_manifest.json"

EXPECTED_CORE_ORDER = (
    "cogs.temp_voice",
    "cogs.temp_music",
    "cogs.voice_runtime",
)
EXPECTED_LOOPS = (
    "afk_auto_move_loop",
    "update_relationship_lists",
    "birthday_loop",
    "temp_voice_housekeeping_loop",
    "voice_xp_loop",
    "update_leaderboard",
    "auto_info",
    "update_stats",
    "update_admin_list",
    "check_reminders",
)
EXPECTED_EVENTS = (
    "on_voice_state_update",
    "on_member_join",
    "on_member_remove",
    "on_raw_reaction_add",
    "on_message_delete",
    "on_message_edit",
    "on_message",
    "on_command_error",
    "on_ready",
)
EXPECTED_TEMP_BUTTON_IDS = {
    "temp_voice_privacy_toggle",
    "temp_voice_allow_button",
    "temp_voice_deny_button",
    "temp_voice_block_button",
    "temp_voice_unblock_button",
    "temp_voice_kick_button",
    "temp_voice_voice_mute_button",
    "temp_voice_voice_unmute_button",
    "temp_voice_chat_mute_button",
    "temp_voice_chat_unmute_button",
    "temp_voice_panel_refresh",
    "temp_voice_music_button",
}
EXPECTED_ROOM_COMMANDS = {
    "allow",
    "block",
    "unblock",
    "deny",
    "kick",
    "mute",
    "unmute",
    "chatmute",
    "chatunmute",
    "private",
    "public",
    "list",
}


def read(path: str | Path) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def tree(path: str | Path) -> ast.Module:
    return ast.parse(read(path), filename=str(ROOT / path))


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Call):
        node = node.func
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def literal_assignment(module: ast.Module, name: str):
    for node in module.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"assignment not found: {name}")


def component_source(path: str | Path) -> str:
    text = read(path)
    begin_marker = "# ORIGINAL SOURCE BEGIN\n"
    end_marker = "# ORIGINAL SOURCE END\n"
    begin = text.index(begin_marker) + len(begin_marker)
    end = text.index(end_marker)
    guarded = text[begin:end]
    prefix = 'if globals().get("_GGMW9_COMPONENT_EXEC", False):\n'
    if not guarded.startswith(prefix):
        raise AssertionError(f"missing component execution guard: {path}")
    lines = guarded[len(prefix):].splitlines(keepends=True)
    if any(line.strip() and not line.startswith("    ") for line in lines):
        raise AssertionError(f"invalid guarded indentation: {path}")
    return "".join(line[4:] if line.startswith("    ") else line for line in lines)


def core_extensions() -> list[str]:
    return list(literal_assignment(tree("ai_bot.py"), "CORE_COGS"))


def extension_path(extension: str) -> str:
    return extension.replace(".", "/") + ".py"


def ordered_component_paths() -> list[str]:
    return ["cogs/bootstrap.py", *(extension_path(item) for item in core_extensions())]


def registrations(paths: list[str]):
    commands = []
    events = []
    loops = []
    for path in paths:
        module = ast.parse(component_source(path), filename=path)
        for node in module.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                name = dotted_name(decorator)
                if name in {"bot.command", "bot.hybrid_command"}:
                    commands.append(node.name)
                elif name == "bot.event":
                    events.append(node.name)
                elif name == "tasks.loop":
                    loops.append(node.name)
    return commands, events, loops


def find_class(module: ast.Module, name: str) -> ast.ClassDef:
    for node in ast.walk(module):
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"class not found: {name}")


def find_function(module: ast.Module, name: str) -> ast.AST:
    for node in ast.walk(module):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"function not found: {name}")


def literal_keyword(call: ast.Call, name: str):
    for keyword in call.keywords:
        if keyword.arg == name:
            return ast.literal_eval(keyword.value)
    raise AssertionError(f"keyword not found: {name}")


class LoaderAndManifestTests(unittest.TestCase):
    def test_temp_music_loads_between_voice_state_and_voice_runtime(self):
        extensions = core_extensions()
        positions = [extensions.index(item) for item in EXPECTED_CORE_ORDER]
        self.assertEqual(positions, list(range(positions[0], positions[0] + 3)))

    def test_manifest_matches_the_complete_core_component_order(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        actual_paths = [item["path"] for item in manifest["components"]]
        self.assertEqual(actual_paths, ordered_component_paths())
        self.assertEqual(len(actual_paths), 28)
        self.assertEqual(len(actual_paths), len(set(actual_paths)))

    def test_manifest_hashes_cover_the_intentional_new_baseline(self):
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        rebuilt = []
        for item in manifest["components"]:
            source = component_source(item["path"])
            rebuilt.append(source)
            actual = hashlib.sha256(source.encode("utf-8")).hexdigest()
            self.assertEqual(actual, item["sha256"], item["path"])
        joined = hashlib.sha256("".join(rebuilt).encode("utf-8")).hexdigest()
        self.assertEqual(joined, manifest["joined_sha256"])

    def test_command_event_and_loop_surface_is_exact(self):
        commands, events, loops = registrations(ordered_component_paths())
        self.assertEqual(len(commands), 61)
        self.assertEqual(events, list(EXPECTED_EVENTS))
        self.assertEqual(loops, list(EXPECTED_LOOPS))

        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        self.assertEqual(manifest["events_before_setup_hook"], list(EXPECTED_EVENTS))
        self.assertEqual(manifest["task_loops"], list(EXPECTED_LOOPS))

    def test_setup_hook_remains_the_only_entrypoint_event(self):
        entrypoint_events = []
        for node in tree("ai_bot.py").body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(dotted_name(item) == "bot.event" for item in node.decorator_list):
                    entrypoint_events.append(node.name)
        self.assertEqual(entrypoint_events, ["setup_hook"])


class TempVoicePanelSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = component_source("cogs/temp_voice.py")
        cls.module = ast.parse(cls.source, filename="cogs/temp_voice.py")
        cls.view = find_class(cls.module, "TempVoiceControlView")

    def button_decorators(self):
        buttons = []
        for node in self.view.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and dotted_name(decorator) == "discord.ui.button":
                    buttons.append({
                        "callback": node.name,
                        "label": literal_keyword(decorator, "label"),
                        "custom_id": literal_keyword(decorator, "custom_id"),
                        "row": literal_keyword(decorator, "row"),
                    })
        return buttons

    def test_persistent_panel_has_exactly_twelve_unique_buttons(self):
        buttons = self.button_decorators()
        ids = [item["custom_id"] for item in buttons]
        self.assertEqual(len(buttons), 12)
        self.assertEqual(set(ids), EXPECTED_TEMP_BUTTON_IDS)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(len(item) <= 100 for item in ids))
        self.assertTrue(all(len(item["label"]) <= 80 for item in buttons))

    def test_button_rows_fit_discord_layout(self):
        counts = Counter(item["row"] for item in self.button_decorators())
        self.assertEqual(counts, {0: 5, 1: 5, 2: 2})
        self.assertTrue(all(0 <= row <= 4 and count <= 5 for row, count in counts.items()))

    def test_music_button_is_owner_gated_regular_callback(self):
        music = next(
            item for item in self.button_decorators()
            if item["custom_id"] == "temp_voice_music_button"
        )
        self.assertEqual(music["label"], "🎵 Music")
        self.assertEqual(music["row"], 2)

        callback = find_function(self.view, music["callback"])
        rendered = ast.unparse(callback)
        self.assertIn("await _temp_voice_require_owner(interaction)", rendered)
        self.assertIn("if not ch", rendered)
        self.assertIn("await interaction.response.defer(ephemeral=True)", rendered)
        self.assertIn("await open_temp_music_panel(interaction, ch)", rendered)
        self.assertNotIn("send_modal", rendered)

    def test_legacy_jockie_volume_ui_is_gone(self):
        class_names = {
            node.name for node in ast.walk(self.module) if isinstance(node, ast.ClassDef)
        }
        self.assertNotIn("JockieVolumeModal", class_names)
        self.assertNotIn("temp_voice_music_volume_button", self.source)
        self.assertNotIn("m!volume", self.source)


class CrossComponentSourceTests(unittest.TestCase):
    def test_temp_music_component_exposes_required_services(self):
        module = tree("cogs/temp_music.py")
        function_names = {
            node.name
            for node in ast.walk(module)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertTrue({
            "assign_temp_music_bot",
            "reconcile_temp_music_assignments",
            "temp_music_panel_summary",
            "open_temp_music_panel",
            "cleanup_temp_voice_room_if_empty",
            "schedule_temp_voice_cleanup",
            "sweep_empty_temp_voice_rooms",
            "temp_voice_housekeeping_loop",
            "before_temp_voice_housekeeping_loop",
            "shutdown_temp_music_runtime",
        }.issubset(function_names))

        imports = [
            node for node in module.body
            if isinstance(node, ast.ImportFrom) and node.module == "cogs.temp_music_policy"
        ]
        self.assertEqual(len(imports), 1)

        teardown = find_function(module, "teardown")
        rendered_teardown = ast.unparse(teardown)
        self.assertIn("runtime_namespace().get('shutdown_temp_music_runtime')", rendered_teardown)
        self.assertIn("await shutdown()", rendered_teardown)

    def test_housekeeping_waits_for_ready_and_is_started_once(self):
        music_module = tree("cogs/temp_music.py")
        loop_fn = find_function(music_module, "temp_voice_housekeeping_loop")
        self.assertTrue(any(dotted_name(item) == "tasks.loop" for item in loop_fn.decorator_list))

        before_fn = find_function(music_module, "before_temp_voice_housekeeping_loop")
        self.assertIn(
            "await bot.wait_until_ready()",
            ast.unparse(before_fn),
        )

        ready = find_function(tree("cogs/ready_events.py"), "on_ready")
        rendered = ast.unparse(ready)
        self.assertIn("if not temp_voice_housekeeping_loop.is_running()", rendered)
        self.assertEqual(rendered.count("temp_voice_housekeeping_loop.start()"), 1)

    def test_voice_runtime_uses_human_aware_scheduled_cleanup(self):
        rendered = ast.unparse(ast.parse(component_source("cogs/voice_runtime.py")))
        self.assertIn("assign_temp_music_bot(channel, attempt_move=True)", rendered)
        self.assertIn("cancel_scheduled_temp_voice_cleanup(after.channel.id)", rendered)
        self.assertIn("if not has_human_members(left_channel.members)", rendered)
        self.assertIn("schedule_temp_voice_cleanup(", rendered)

    def test_join_to_create_fast_path_moves_before_background_setup(self):
        runtime = ast.parse(component_source("cogs/voice_runtime.py"))
        create = ast.unparse(find_function(runtime, "_create_temp_voice_room_fast"))
        finish = ast.unparse(find_function(runtime, "_finish_new_temp_voice_room"))
        event = ast.unparse(find_function(runtime, "on_voice_state_update"))

        create_pos = create.index("await guild.create_voice_channel(")
        move_pos = create.index("await member.move_to(")
        schedule_pos = create.index("_schedule_temp_voice_post_create(new_channel)")
        critical_path = create[create_pos:move_pos]

        self.assertLess(create_pos, move_pos)
        self.assertLess(move_pos, schedule_pos)
        self.assertNotIn("save_temp_voice_channels()", critical_path)
        self.assertNotIn("save_temp_voice_acl()", critical_path)
        self.assertNotIn("enforce_temp_voice_security_overwrites", critical_path)
        self.assertNotIn("assign_temp_music_bot", critical_path)
        self.assertNotIn("send_temp_voice_control_panel", critical_path)
        self.assertIn("asyncio.gather(", finish)
        self.assertIn("enforce_temp_voice_security_overwrites(channel)", finish)
        self.assertIn("assign_temp_music_bot(channel, attempt_move=True)", finish)
        self.assertIn("send_temp_voice_control_panel(channel, newly_created=True)", finish)
        self.assertLess(
            event.index("await _create_temp_voice_room_fast(member, after.channel)"),
            event.index("await handle_afk_auto_return(member, before, after)"),
        )

    def test_temp_permissions_skip_redundant_http_and_new_panel_skips_history(self):
        temp = ast.parse(component_source("cogs/temp_voice.py"))
        apply_permissions = ast.unparse(
            find_function(temp, "apply_temp_voice_member_permissions")
        )
        send_panel = ast.unparse(find_function(temp, "send_temp_voice_control_panel"))
        panel_registry = read("cogs/panel_registry.py")

        self.assertIn("before_allow, before_deny = overwrite.pair()", apply_permissions)
        self.assertIn("after_allow, after_deny = overwrite.pair()", apply_permissions)
        self.assertLess(
            apply_permissions.index("return (True, None)"),
            apply_permissions.index("await channel.set_permissions("),
        )
        self.assertIn("newly_created: bool=False", send_panel)
        self.assertIn("trust_empty_channel=newly_created", send_panel)
        self.assertIn("known_new_empty_channel", panel_registry)
        self.assertIn("if not known_new_empty_channel:", panel_registry)

    def test_cleanup_rechecks_humans_and_orphans_need_durable_ownership(self):
        music = ast.parse(component_source("cogs/temp_music.py"))
        cleanup = ast.unparse(find_function(music, "cleanup_temp_voice_room_if_empty"))
        last_human_check = cleanup.rindex("has_human_members(current.members)")
        delete_call = cleanup.index("await current.delete(")
        self.assertLess(last_human_check, delete_call)

        sweep = ast.unparse(find_function(music, "sweep_empty_temp_voice_rooms"))
        self.assertIn("ownership_record = temp_voice_acl.get(str(channel.id))", sweep)
        self.assertIn("ownership_record.get('owner_id')", sweep)
        self.assertIn("ownership_record.get('created_at')", sweep)

    def test_assignment_rejects_stale_rooms_and_permission_repairs_are_idempotent(self):
        music = ast.parse(component_source("cogs/temp_music.py"))
        assign = ast.unparse(find_function(music, "assign_temp_music_bot"))
        self.assertIn("channel.guild.get_channel(channel.id)", assign)
        self.assertIn("not has_human_members(current.members)", assign)
        self.assertIn("return (None, 'inactive')", assign)

        ensure = ast.unparse(find_function(music, "_ensure_temp_music_permissions"))
        self.assertIn("if all(", ensure)
        self.assertIn("return True", ensure)
        self.assertLess(ensure.index("if all("), ensure.index("await channel.set_permissions("))

    def test_empty_temp_rooms_override_legacy_afk_keepalive(self):
        bootstrap = ast.parse(component_source("cogs/bootstrap.py"))
        self.assertFalse(literal_assignment(bootstrap, "AFK_AUTO_RETURN_KEEP_TEMP_ROOM"))

        music = ast.parse(component_source("cogs/temp_music.py"))
        purge = ast.unparse(find_function(music, "_purge_temp_voice_state"))
        self.assertIn("_purge_afk_auto_return_state(channel_id)", purge)

    def test_temp_voice_reconciles_cleanup_before_music_and_panels(self):
        fn = find_function(
            ast.parse(component_source("cogs/temp_voice.py")),
            "reconcile_temp_voice_rooms",
        )
        rendered = ast.unparse(fn)
        sweep_pos = rendered.index("await sweep_empty_temp_voice_rooms(guild)")
        music_pos = rendered.index("await reconcile_temp_music_assignments(guild)")
        panel_pos = rendered.index("await refresh_temp_voice_control_panel(")
        self.assertLess(sweep_pos, music_pos)
        self.assertLess(music_pos, panel_pos)

    def test_room_slash_command_surface_is_unchanged(self):
        module = tree("cogs/temp_room_full_control.py")
        names = set()
        for node in ast.walk(module):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and dotted_name(decorator) == "room.command":
                    names.add(literal_keyword(decorator, "name"))
        self.assertEqual(names, EXPECTED_ROOM_COMMANDS)
        self.assertEqual(len(names), 12)


if __name__ == "__main__":
    unittest.main()
