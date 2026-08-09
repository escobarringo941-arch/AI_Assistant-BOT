# -*- coding: utf-8 -*-
"""Unchanged ordered source component: bot_admin_panel."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║      Bot Control Panel — لوحة تحكم شاملة (Admin)         ║
    # ═══════════════════════════════════════════════════════
    # لوحة واحدة كتجمع أغلب الحوايج اللي محتاجة تحكم متكرر (تفعيل/تعطيل، عتبات،
    # مدد) بلا ماتمس الكود ولا تعاود ريستارت البوت — /botpanel
    
    def _bool_emoji(value: bool) -> str:
        return "✅" if value else "❌"
    
    
    def _main_panel_embed() -> discord.Embed:
        embed = discord.Embed(
            title="🎛️ لوحة تحكم البوت",
            description="اختار قسم من الأزرار تحت باش تشوف/تبدل الإعدادات ديالو. XP ليها لوحة خاصة بيها `/xppanel`.",
            color=discord.Color.blurple(),
            timestamp=datetime.now()
        )
        embed.add_field(
            name="🚨 Anti-Raid",
            value=(
                f"{_bool_emoji(bot_settings['anti_raid_enabled'])} الحالة\n"
                f"عتبة: **{bot_settings['raid_join_threshold']}** فـ **{bot_settings['raid_join_interval_seconds']}**ث\n"
                f"العمل: **{'حظر' if bot_settings['raid_action'] == 'ban' else 'طرد'}** | Lockdown: **{bot_settings['raid_lockdown_duration_minutes'] or '∞'}**د"
            ),
            inline=True
        )
        embed.add_field(
            name="⚠️ التحذيرات (Warns)",
            value=(
                f"🔇 كتم عند **{bot_settings['mute_after_warns']}** ({bot_settings['mute_duration_minutes']}د)\n"
                f"👢 طرد عند **{bot_settings['kick_after_warns']}**\n"
                f"🚫 حظر عند **{bot_settings['ban_after_warns']}**"
            ),
            inline=True
        )
        embed.add_field(
            name="📰 Auto-Info",
            value=(
                f"{_bool_emoji(bot_settings['auto_info_news'])} أخبار | "
                f"{_bool_emoji(bot_settings['auto_info_games'])} ألعاب | "
                f"{_bool_emoji(bot_settings['auto_info_movies'])} أفلام\n"
                f"{_bool_emoji(bot_settings['auto_info_anime'])} أنمي | "
                f"{_bool_emoji(bot_settings['auto_info_music'])} موسيقى"
            ),
            inline=False
        )
        embed.add_field(
            name="🧩 مميزات عامة",
            value=(
                f"{_bool_emoji(bot_settings['leveling_enabled'])} Leveling/XP | "
                f"{_bool_emoji(bot_settings['voice_xp_enabled'])} Voice XP\n"
                f"{_bool_emoji(bot_settings['join_to_create_enabled'])} Join to Create | "
                f"{_bool_emoji(bot_settings['welcome_card_enabled'])} Welcome Cards\n"
                f"{_bool_emoji(bot_settings['auto_translate_enabled'])} Auto-Translate | "
                f"{_bool_emoji(bot_settings['auto_react_enabled'])} Auto-React"
            ),
            inline=False
        )
        embed.set_footer(text=f"{SERVER_NAME} | Bot Control Panel")
        return embed
    
    
    class BackToMainButton(discord.ui.Button):
        def __init__(self):
            super().__init__(label="رجوع", emoji="🔙", style=discord.ButtonStyle.secondary, row=4)
    
        async def callback(self, interaction: discord.Interaction):
            await interaction.response.edit_message(embed=_main_panel_embed(), view=MainPanelView())
    
    
    class PanelPermissionView(discord.ui.View):
        """View بيز فيها فحص الصلاحية (Owner بوحدو) مشترك بين كل صفحات اللوحة."""
    
        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if not (OWNER_ID and interaction.user.id == OWNER_ID):
                await interaction.response.send_message("❌ هاد اللوحة خاصة غير بالـ Owner.", ephemeral=True)
                return False
            return True
    
    
    # ───────────── Anti-Raid ─────────────
    
    def _anti_raid_embed() -> discord.Embed:
        embed = discord.Embed(
            title="🚨 إعدادات Anti-Raid",
            color=discord.Color.red() if bot_settings["anti_raid_enabled"] else discord.Color.greyple(),
            timestamp=datetime.now()
        )
        embed.add_field(name="الحالة", value=_bool_emoji(bot_settings["anti_raid_enabled"]), inline=True)
        embed.add_field(name="العمل", value="🚫 حظر" if bot_settings["raid_action"] == "ban" else "👢 طرد", inline=True)
        embed.add_field(
            name="مدة Lockdown",
            value=f"{bot_settings['raid_lockdown_duration_minutes']} دقيقة" if bot_settings["raid_lockdown_duration_minutes"] else "حتى /unlockdown يدوي",
            inline=True
        )
        embed.add_field(
            name="العتبة",
            value=f"**{bot_settings['raid_join_threshold']}** عضو جديد فـ **{bot_settings['raid_join_interval_seconds']}** ثانية",
            inline=False
        )
        return embed
    
    
    class AntiRaidSettingsModal(discord.ui.Modal, title="🚨 إعدادات Anti-Raid"):
        def __init__(self):
            super().__init__()
            self.threshold = discord.ui.TextInput(
                label="عدد الأعضاء الجداد (العتبة)", default=str(bot_settings["raid_join_threshold"]), max_length=4
            )
            self.interval = discord.ui.TextInput(
                label="فـ هاد المدة بالثواني", default=str(bot_settings["raid_join_interval_seconds"]), max_length=5
            )
            self.action = discord.ui.TextInput(
                label="العمل: اكتب kick ولا ban", default=bot_settings["raid_action"], max_length=4
            )
            self.lockdown_minutes = discord.ui.TextInput(
                label="مدة Lockdown بالدقايق (0 = يدوي فقط)",
                default=str(bot_settings["raid_lockdown_duration_minutes"]), max_length=5
            )
            self.add_item(self.threshold)
            self.add_item(self.interval)
            self.add_item(self.action)
            self.add_item(self.lockdown_minutes)
    
        async def on_submit(self, interaction: discord.Interaction):
            try:
                new_threshold = int(self.threshold.value)
                new_interval = int(self.interval.value)
                new_lockdown = int(self.lockdown_minutes.value)
            except ValueError:
                await interaction.response.send_message("❌ العتبة/المدة/Lockdown خاصهم يكونو أرقام صحيحة.", ephemeral=True)
                return
            new_action = self.action.value.strip().lower()
            if new_action not in ("kick", "ban"):
                await interaction.response.send_message("❌ العمل خاصو يكون `kick` ولا `ban` فقط.", ephemeral=True)
                return
            if new_threshold < 1 or new_interval < 1 or new_lockdown < 0:
                await interaction.response.send_message("❌ العتبة والمدة خاصهم يكونو أكبر من 0.", ephemeral=True)
                return
    
            bot_settings["raid_join_threshold"] = new_threshold
            bot_settings["raid_join_interval_seconds"] = new_interval
            bot_settings["raid_action"] = new_action
            bot_settings["raid_lockdown_duration_minutes"] = new_lockdown
            save_bot_settings()
    
            await interaction.response.edit_message(embed=_anti_raid_embed(), view=AntiRaidView())
    
    
    class AntiRaidView(PanelPermissionView):
        def __init__(self):
            super().__init__(timeout=300)
            self.add_item(BackToMainButton())
    
        @discord.ui.button(label="تفعيل/تعطيل", emoji="🔌", style=discord.ButtonStyle.primary)
        async def toggle_enabled(self, interaction: discord.Interaction, button: discord.ui.Button):
            bot_settings["anti_raid_enabled"] = not bot_settings["anti_raid_enabled"]
            save_bot_settings()
            await interaction.response.edit_message(embed=_anti_raid_embed(), view=self)
    
        @discord.ui.button(label="عدل القيم", emoji="✏️", style=discord.ButtonStyle.primary)
        async def edit_values(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(AntiRaidSettingsModal())
    
    
    # ───────────── Warns Escalation ─────────────
    
    def _warns_embed() -> discord.Embed:
        embed = discord.Embed(title="⚠️ تصعيد التحذيرات (Warns)", color=discord.Color.orange(), timestamp=datetime.now())
        embed.add_field(name="🔇 كتم", value=f"عند **{bot_settings['mute_after_warns']}** تحذيرات، **{bot_settings['mute_duration_minutes']}** دقيقة", inline=False)
        embed.add_field(name="👢 طرد", value=f"عند **{bot_settings['kick_after_warns']}** تحذيرات", inline=False)
        embed.add_field(name="🚫 حظر", value=f"عند **{bot_settings['ban_after_warns']}** تحذيرات", inline=False)
        return embed
    
    
    class WarnsSettingsModal(discord.ui.Modal, title="⚠️ تصعيد التحذيرات"):
        def __init__(self):
            super().__init__()
            self.mute_after = discord.ui.TextInput(label="كتم عند شحال تحذير", default=str(bot_settings["mute_after_warns"]), max_length=3)
            self.mute_minutes = discord.ui.TextInput(label="مدة الكتم بالدقايق", default=str(bot_settings["mute_duration_minutes"]), max_length=5)
            self.kick_after = discord.ui.TextInput(label="طرد عند شحال تحذير", default=str(bot_settings["kick_after_warns"]), max_length=3)
            self.ban_after = discord.ui.TextInput(label="حظر عند شحال تحذير", default=str(bot_settings["ban_after_warns"]), max_length=3)
            self.add_item(self.mute_after)
            self.add_item(self.mute_minutes)
            self.add_item(self.kick_after)
            self.add_item(self.ban_after)
    
        async def on_submit(self, interaction: discord.Interaction):
            try:
                new_mute_after = int(self.mute_after.value)
                new_mute_minutes = int(self.mute_minutes.value)
                new_kick_after = int(self.kick_after.value)
                new_ban_after = int(self.ban_after.value)
            except ValueError:
                await interaction.response.send_message("❌ خاص كاع القيم يكونو أرقام صحيحة.", ephemeral=True)
                return
            if min(new_mute_after, new_mute_minutes, new_kick_after, new_ban_after) < 0:
                await interaction.response.send_message("❌ ماكاينش أرقام سالبة.", ephemeral=True)
                return
            if not (new_mute_after <= new_kick_after <= new_ban_after):
                await interaction.response.send_message(
                    "❌ خاص الترتيب يكون منطقي: كتم ≤ طرد ≤ حظر (بعدد التحذيرات).", ephemeral=True
                )
                return
    
            bot_settings["mute_after_warns"] = new_mute_after
            bot_settings["mute_duration_minutes"] = new_mute_minutes
            bot_settings["kick_after_warns"] = new_kick_after
            bot_settings["ban_after_warns"] = new_ban_after
            save_bot_settings()
    
            await interaction.response.edit_message(embed=_warns_embed(), view=WarnsView())
    
    
    class WarnsView(PanelPermissionView):
        def __init__(self):
            super().__init__(timeout=300)
            self.add_item(BackToMainButton())
    
        @discord.ui.button(label="عدل القيم", emoji="✏️", style=discord.ButtonStyle.primary)
        async def edit_values(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.send_modal(WarnsSettingsModal())
    
    
    # ───────────── Auto-Info Toggles ─────────────
    
    def _auto_info_embed() -> discord.Embed:
        embed = discord.Embed(title="📰 Auto-Info — تفعيل/تعطيل كل فئة", color=discord.Color.teal(), timestamp=datetime.now())
        embed.add_field(name="📰 أخبار", value=_bool_emoji(bot_settings["auto_info_news"]), inline=True)
        embed.add_field(name="🎮 ألعاب", value=_bool_emoji(bot_settings["auto_info_games"]), inline=True)
        embed.add_field(name="🎬 أفلام", value=_bool_emoji(bot_settings["auto_info_movies"]), inline=True)
        embed.add_field(name="📺 أنمي", value=_bool_emoji(bot_settings["auto_info_anime"]), inline=True)
        embed.add_field(name="🎧 موسيقى", value=_bool_emoji(bot_settings["auto_info_music"]), inline=True)
        return embed
    
    
    class AutoInfoView(PanelPermissionView):
        def __init__(self):
            super().__init__(timeout=300)
            self.add_item(BackToMainButton())
    
        async def _toggle(self, interaction: discord.Interaction, key: str):
            bot_settings[key] = not bot_settings[key]
            save_bot_settings()
            await interaction.response.edit_message(embed=_auto_info_embed(), view=self)
    
        @discord.ui.button(label="أخبار", emoji="📰", style=discord.ButtonStyle.secondary)
        async def toggle_news(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "auto_info_news")
    
        @discord.ui.button(label="ألعاب", emoji="🎮", style=discord.ButtonStyle.secondary)
        async def toggle_games(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "auto_info_games")
    
        @discord.ui.button(label="أفلام", emoji="🎬", style=discord.ButtonStyle.secondary)
        async def toggle_movies(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "auto_info_movies")
    
        @discord.ui.button(label="أنمي", emoji="📺", style=discord.ButtonStyle.secondary)
        async def toggle_anime(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "auto_info_anime")
    
        @discord.ui.button(label="موسيقى", emoji="🎧", style=discord.ButtonStyle.secondary)
        async def toggle_music(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "auto_info_music")
    
    
    # ───────────── مميزات عامة (Feature Toggles) ─────────────
    
    def _features_embed() -> discord.Embed:
        embed = discord.Embed(title="🧩 مميزات عامة — تفعيل/تعطيل", color=discord.Color.blurple(), timestamp=datetime.now())
        embed.add_field(name="📊 Leveling/XP", value=_bool_emoji(bot_settings["leveling_enabled"]), inline=True)
        embed.add_field(name="🎙️ Voice XP", value=_bool_emoji(bot_settings["voice_xp_enabled"]), inline=True)
        embed.add_field(name="🔊 Join to Create", value=_bool_emoji(bot_settings["join_to_create_enabled"]), inline=True)
        embed.add_field(name="🖼️ Welcome Cards", value=_bool_emoji(bot_settings["welcome_card_enabled"]), inline=True)
        embed.add_field(name="🌐 Auto-Translate", value=_bool_emoji(bot_settings["auto_translate_enabled"]), inline=True)
        embed.add_field(name="⚡ Auto-React", value=_bool_emoji(bot_settings["auto_react_enabled"]), inline=True)
        return embed
    
    
    class FeaturesView(PanelPermissionView):
        def __init__(self):
            super().__init__(timeout=300)
            self.add_item(BackToMainButton())
    
        async def _toggle(self, interaction: discord.Interaction, key: str):
            bot_settings[key] = not bot_settings[key]
            save_bot_settings()
            await interaction.response.edit_message(embed=_features_embed(), view=self)
    
        @discord.ui.button(label="Leveling/XP", emoji="📊", style=discord.ButtonStyle.secondary)
        async def toggle_leveling(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "leveling_enabled")
    
        @discord.ui.button(label="Voice XP", emoji="🎙️", style=discord.ButtonStyle.secondary)
        async def toggle_voice_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "voice_xp_enabled")
    
        @discord.ui.button(label="Join to Create", emoji="🔊", style=discord.ButtonStyle.secondary)
        async def toggle_j2c(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "join_to_create_enabled")
    
        @discord.ui.button(label="Welcome Cards", emoji="🖼️", style=discord.ButtonStyle.secondary)
        async def toggle_welcome(self, interaction: discord.Interaction, button: discord.ui.Button):
            if not PIL_AVAILABLE:
                await interaction.response.send_message("❌ Pillow ماشي مثبتة فالسيرفر، Welcome Cards ماغاديش تخدم حتى لو شعلتيها.", ephemeral=True)
                return
            await self._toggle(interaction, "welcome_card_enabled")
    
        @discord.ui.button(label="Auto-Translate", emoji="🌐", style=discord.ButtonStyle.secondary)
        async def toggle_translate(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "auto_translate_enabled")
    
        @discord.ui.button(label="Auto-React", emoji="⚡", style=discord.ButtonStyle.secondary)
        async def toggle_react(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._toggle(interaction, "auto_react_enabled")
    
    
    # ───────────── اللوحة الرئيسية ─────────────
    
    class MainPanelView(PanelPermissionView):
        def __init__(self):
            super().__init__(timeout=300)
    
        @discord.ui.button(label="Anti-Raid", emoji="🚨", style=discord.ButtonStyle.primary)
        async def open_anti_raid(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=_anti_raid_embed(), view=AntiRaidView())
    
        @discord.ui.button(label="التحذيرات", emoji="⚠️", style=discord.ButtonStyle.primary)
        async def open_warns(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=_warns_embed(), view=WarnsView())
    
        @discord.ui.button(label="Auto-Info", emoji="📰", style=discord.ButtonStyle.primary)
        async def open_auto_info(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=_auto_info_embed(), view=AutoInfoView())
    
        @discord.ui.button(label="مميزات عامة", emoji="🧩", style=discord.ButtonStyle.primary)
        async def open_features(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=_features_embed(), view=FeaturesView())
    
        @discord.ui.button(label="XP Panel", emoji="📊", style=discord.ButtonStyle.success, row=1)
        async def open_xp(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(embed=_xp_panel_embed(), view=XPPanelView())
    
    
    @bot.command(name="botpanel", hidden=True)
    @owner_only()
    async def botpanel_cmd(ctx):
        """لوحة تحكم شاملة فأغلب إعدادات البوت (Anti-Raid، التحذيرات، Auto-Info، مميزات عامة، وXP) — Owner"""
        await ctx.send(embed=_main_panel_embed(), view=MainPanelView())
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
