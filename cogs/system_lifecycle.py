# -*- coding: utf-8 -*-
"""Ordered startup and self-healing lifecycle.

Extracted mechanically from the legacy ai_bot.py.  Runtime state is attached
to bot_core's shared namespace so existing cross-system references keep the
same object identity and startup order.
"""

import bot_core as core

core.attach_namespace(globals())





class LifecycleCog(commands.Cog):
    """Discord command/event registration for this subsystem."""

    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"✅ GGMW9 شغال!")
        print(f"🤖 Model: {AI_MODEL}")
        print(f"💬 AI Channel: {TARGET_CHANNEL_ID}")
        print(f"👋 Welcome: {WELCOME_CHANNEL_ID}")
        print(f"✅ Verify: {VERIFY_CHANNEL_ID}")
        print(f"🛡️ Mod Logs: {MOD_LOGS_CHANNEL_ID}")
        print(f"📰 News: {'نشط' if bot_settings['auto_info_news'] else 'معطل مؤقتا'} {NEWS_CHANNEL_IDS}")
        print(f"🎮 Games: {'نشط' if bot_settings['auto_info_games'] else 'معطل مؤقتا'} {GAMES_CHANNEL_IDS}")
        print(f"🎬 Movies: {'نشط' if bot_settings['auto_info_movies'] else 'معطل مؤقتا'} {MOVIES_CHANNEL_IDS}")
        print(f"📺 Anime: {'نشط' if bot_settings['auto_info_anime'] else 'معطل مؤقتا'} {ANIME_CHANNEL_IDS}")
        print(f"🎧 Music: {'نشط' if bot_settings['auto_info_music'] else 'معطل مؤقتا'} {MUSIC_CHANNEL_IDS}")
        print(f"⏱️ Timeout: {API_TIMEOUT}s")
        print(f"🛡️ Moderation: نشط")
        print(f"✅ Verification: نشط")
        print(f"📰 Auto-Info: نشط (5 channels + APIs حقيقية)")
        print(f"⚠️ Warn Escalation: Mute@{bot_settings['mute_after_warns']} / Kick@{bot_settings['kick_after_warns']} / Ban@{bot_settings['ban_after_warns']}")
        print(f"📊 Stats Channel: {STATS_CHANNEL_ID if STATS_CHANNEL_ID else 'ماشي معطي بعد'} (كل {STATS_UPDATE_MINUTES} د)")
        print(f"🏆 Leaderboard أوتوماتيكي: {LEADERBOARD_CHANNEL_ID if LEADERBOARD_CHANNEL_ID else 'ماشي معطي بعد'} (كل {LEADERBOARD_UPDATE_MINUTES} د)")
        print(f"👑 Administrators Channel: {ADMINISTRATORS_CHANNEL_ID if ADMINISTRATORS_CHANNEL_ID else 'ماشي معطي بعد'} (كل {ADMIN_LIST_UPDATE_MINUTES} د)")
        print(f"🆘 Support: Center={SUPPORT_CENTER_CHANNEL_ID or 'ماشي معطي'} | Reports={REPORTS_CHANNEL_ID or 'ماشي معطي'} | Tickets Category={TICKETS_CATEGORY_ID or 'ماشي معطي'} | Ticket Logs={TICKET_LOGS_CHANNEL_ID or 'MOD_LOGS_CHANNEL_ID'}")
        print(f"📋 Applications: Panel={APPLICATIONS_PANEL_CHANNEL_ID or 'ماشي معطي'} | Review={APPLICATIONS_REVIEW_CHANNEL_ID or 'MOD_LOGS_CHANNEL_ID'} | Cooldown={APPLICATIONS_COOLDOWN_HOURS}h")
        print(f"💡 Suggestions: Channel={SUGGESTIONS_CHANNEL_ID or 'ماشي معطي'}")
        print(f"🎂 Birthdays: Channel={BIRTHDAY_ANNOUNCE_CHANNEL_ID or 'ماشي معطي'} | Role={BIRTHDAY_ROLE_ID or 'بلا رول'} | Hour={BIRTHDAY_ANNOUNCE_HOUR}:00 UTC")
        print(f"🚨 Anti-Raid: {'نشط' if bot_settings['anti_raid_enabled'] else 'معطل'} (عتبة: {bot_settings['raid_join_threshold']} فـ {bot_settings['raid_join_interval_seconds']}ث | عمل: {bot_settings['raid_action']})")
        print(f"🖼️ Welcome Cards: {'نشط' if (bot_settings['welcome_card_enabled'] and PIL_AVAILABLE) else ('معطل (Pillow ماشي مثبت)' if not PIL_AVAILABLE else 'معطل')}")
        print(f"📊 Leveling: {'نشط' if bot_settings['leveling_enabled'] else 'معطل'} (شات: {xp_settings['chat_min']}-{xp_settings['chat_max']} XP/رسالة، cooldown {xp_settings['chat_cooldown']}ث)")
        print(f"⏰ Reminders: {len(reminders)} مبرمجين (كيتفقّد كل 30 ثانية)")
        print(f"🌐 Auto-Translate: {'نشط' if bot_settings['auto_translate_enabled'] else 'معطل'} ({len(FLAG_TO_LANGUAGE)} علم مدعوم) | Auto-React: {'نشط' if bot_settings['auto_react_enabled'] else 'معطل'} ({', '.join(AUTO_REACT_FLAGS) if AUTO_REACT_FLAGS else 'بلا أعلام'})")
        print(f"🔊 Join to Create: {'نشط' if (bot_settings['join_to_create_enabled'] and JOIN_TO_CREATE_CHANNEL_ID) else 'معطل'} | Voice XP: {'نشط' if bot_settings['voice_xp_enabled'] else 'معطل'} (فويس: {xp_settings['voice_per_interval']} / لايفستريم: {xp_settings['stream_per_interval']} XP كل {xp_settings['voice_interval_minutes']}د)")
        print(f"💤 Auto AFK Move: {'نشط' if AFK_AUTO_MOVE_ENABLED else 'معطل'} | Self-Deafen {AFK_AUTO_MOVE_AFTER_MINUTES}د → AFK | Undeafen → Previous Room")

        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name=f"/help | {len(bot.guilds)} سيرفرات"
            )
        )

        if not auto_info.is_running():
            auto_info.start()

        if STATS_CHANNEL_ID and not update_stats.is_running():
            update_stats.start()

        if LEADERBOARD_CHANNEL_ID and not update_leaderboard.is_running():
            update_leaderboard.start()

        if ADMINISTRATORS_CHANNEL_ID and not update_admin_list.is_running():
            update_admin_list.start()

        if not check_reminders.is_running():
            check_reminders.start()

        if not birthday_loop.is_running():
            birthday_loop.start()

        if not voice_xp_loop.is_running():
            voice_xp_loop.start()

        if AFK_AUTO_MOVE_ENABLED and not afk_auto_move_loop.is_running():
            afk_auto_move_loop.start()


        bot.add_view(RulesVerifyView())  # باش الأزرار يبقاو خدامين حتى بعد ريستارت البوت
        bot.add_view(RolePickerView())   # باش الـ Dropdown ديال الأدوار يبقى خدام حتى بعد ريستارت البوت
        bot.add_view(TicketPanelView())    # Legacy compatibility إلا بقات شي رسالة قديمة قبل migration
        bot.add_view(TicketControlView())  # Claim/Close ديال Tickets المفتوحة
        bot.add_view(ApplicationPanelView())   # باش زر "قدم طلب Staff" يبقى خدام حتى بعد ريستارت البوت
        bot.add_view(BlacklistLanguageView())  # Blacklist public Darija + personal translation selector
        bot.add_view(ApplicationReviewView())  # باش أزرار قبول/رفض الطلبات يبقاو خدامين
        bot.add_view(SuggestionReviewView())   # باش أزرار قبول/رفض الاقتراحات يبقاو خدامين
        bot.add_view(SuggestionsPanelView().add_language_selector())  # Public Suggestions panel
        bot.add_view(RoomMuteToggleView())     # باش زر كتم/فك كتم الروم يبقى خدام حتى بعد ريستارت البوت
        bot.add_view(TempVoiceControlView())    # Panel: Private/Allow/Deny/Block/Kick/VoiceMute/ChatMute

        for guild in bot.guilds:
            # ═══ Self-healing ديال Auto AFK tracking بعد restart ═══
            try:
                reconcile_afk_deafen_tracking(guild)
                reconcile_afk_auto_return(guild)
            except Exception as e:
                print(f"[AFK-AUTO-MOVE] خطأ فـ reconcile: {e}")

            # ═══ Self-healing ديال الرومات المؤقتة + panels بعد restart ═══
            try:
                await reconcile_temp_voice_rooms(guild)
            except Exception as e:
                print(f"[TEMP-VOICE] خطأ فـ reconcile: {e}")

            # ═══ Self-healing: Level Roles — صلاحيات آمنة + Role الصحيحة لكل عضو ═══
            try:
                await sync_level_role_permissions(guild)
                await sync_all_level_member_roles(guild)
            except Exception as e:
                print(f"[LEVEL PERKS] خطأ فـ sync LEVEL_ROLES: {e}")

            # ═══ Self-healing: نتأكدو بلي صلاحيات رولات الـ Milestones (10/15/25...) مزبوطة ═══
            # حتى للرولات اللي تصاوبو من قبل (قبل ما نزيدو الصلاحيات الجداد) — بلا ما نحتاجو
            # حد يعاود يطلع لهاد المستوى باش يتصلح.
            for _lvl in LEVEL_MILESTONES:
                try:
                    await get_or_create_tier_role(guild, _lvl)
                except Exception as e:
                    print(f"[MILESTONES] خطأ فـ sync صلاحيات Level {_lvl}: {e}")

            # ملاحظة: ماعادش كنبعثو رسالة "تفعيل العضوية" القديمة (بالريأكشن ✅)
            # باش ما تبقاش مكررة مع رسالة القوانين الجديدة بالأزرار (setup_rules_message)
            await setup_rules_message(guild)
            if BLACKLIST_CHANNEL_ID:
                await setup_blacklist_message(guild)
            if SUPPORT_CENTER_CHANNEL_ID:
                await setup_support_center(guild)
            if APPLICATIONS_PANEL_CHANNEL_ID:
                await setup_applications_panel(guild)
            if LEVELS_INFO_CHANNEL_ID:
                await setup_levels_info_message(guild)
            if OWNER_CONTROL_CHANNEL_ID:
                await setup_owner_control_panel(guild)
            if SUGGESTIONS_CHANNEL_ID:
                await setup_suggestions_info(guild)

            problems = check_role_hierarchy(guild)
            if problems:
                print(f"[ROLE CHECK] ⚠️ {guild.name}: مشاكل فترتيب الرولات:")
                for p in problems:
                    print(f"  - {p}")
                await log_action(
                    guild,
                    "⚠️ مشكل فترتيب الرولات",
                    "نظام التفعيل ممكن ما يخدمش مزيان:\n\n" + "\n\n".join(problems) +
                    "\n\nاستعمل `/checkroles` بعد ما تصلح باش تتأكد.",
                    discord.Color.orange()
                )

        # ═══════ Slash Commands (/) — sync مرة وحدة فقط (on_ready يقدر يتكرر عند reconnect) ═══════
        global _slash_synced
        if not _slash_synced:
            try:
                for guild in bot.guilds:
                    bot.tree.copy_global_to(guild=guild)
                    await bot.tree.sync(guild=guild)
                print(f"✅ Slash Commands (/) تزامنو مع {len(bot.guilds)} سيرفر (فوريين).")
            except discord.HTTPException as e:
                print(f"⚠️ خطأ فـ sync ديال Slash Commands: {e}")
                print(f"[SYNC-DEBUG] status={e.status} code={e.code}")
                print(f"[SYNC-DEBUG] تفاصيل دقيقة من Discord:\n{e.text}")
            except Exception as e:
                print(f"⚠️ خطأ فـ sync ديال Slash Commands: {e}")
            _slash_synced = True


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(LifecycleCog(bot_instance))
