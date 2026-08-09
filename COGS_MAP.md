# GGMW9 Cog map

`ai_bot.py` is now only the bootstrap/loader. The former monolith is preserved in
the same execution order across focused extensions in `cogs/`.

| Area | Extensions |
| --- | --- |
| Base state and persistence | `bootstrap`, `persistent_state`, `xp_runtime`, `settings_storage` |
| AI and external content | `ai_conversation`, `content_apis` |
| Moderation and access | `moderation_core`, `access_panels`, `moderation_commands` |
| Community systems | `support_system`, `applications`, `suggestions`, `birthdays`, `relationships` |
| Voice | `temp_voice`, `temp_music`, `voice_runtime` |
| Members and server setup | `server_setup`, `member_events`, `verification_commands` |
| XP and administration | `xp_admin`, `bot_admin_panel`, `leveling_commands`, `levels_center`, `owner_control` |
| General and scheduled work | `general_commands`, `automation_tasks`, `ready_events` |

The pre-existing economy, city, games, trivia, moderation and temporary-room Cogs
remain unchanged and are loaded after the split core extensions, exactly as before.

Run the static preservation check with:

```bash
python tests/validate_refactor.py
```

It verifies the reviewed hashes and dependency order of all 28 core components,
the unchanged 72-command surface, 10 bot events (including the small
`setup_hook`), nine task loops, and Python syntax for the complete project.

The focused Temp Music policy/integration checks run offline (without connecting
to Discord):

```bash
python -B -m unittest discover -s tests -p 'test_temp_music_*.py' -v
```
