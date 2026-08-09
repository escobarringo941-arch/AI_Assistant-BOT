# -*- coding: utf-8 -*-
"""Unchanged ordered source component: levels_center."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║   📊 Levels Info Center — كلشي Click بلا Commands      ║
    # ═══════════════════════════════════════════════════════
    
    class XPBioModal(discord.ui.Modal, title="📝 البيو ديالك"):
        bio_text = discord.ui.TextInput(
            label="البيو",
            placeholder="كتب bio قصيرة... وخليها خاوية باش تمسحها",
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=200,
        )
    
        async def on_submit(self, interaction: discord.Interaction):
            data = get_user_level_data(interaction.guild.id, interaction.user.id)
            if data["level"] < 20:
                await interaction.response.send_message(
                    "🔒 Bio كتفتح فـ **Level 20**.",
                    ephemeral=True,
                )
                return
            data["bio"] = str(self.bio_text.value).strip()[:200]
            save_levels()
            if data["bio"]:
                await interaction.response.send_message(
                    f"✅ تبدلات الـBio ديالك لـ:\n> {data['bio']}",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "✅ تمسحات الـBio ديالك.",
                    ephemeral=True,
                )
    
    
    class XPLegendTitleModal(discord.ui.Modal, title="👑 Legend Title"):
        title_text = discord.ui.TextInput(
            label="سمية الرول الشخصية",
            placeholder="مثال: GGMW9 King",
            required=True,
            max_length=90,
        )
    
        async def on_submit(self, interaction: discord.Interaction):
            data = get_user_level_data(interaction.guild.id, interaction.user.id)
            if data["level"] < 100:
                await interaction.response.send_message(
                    "🔒 Legend Title كتفتح غير فـ **Level 100**.",
                    ephemeral=True,
                )
                return
    
            role = await get_or_create_legend_role(interaction.guild, interaction.user)
            if not role:
                await interaction.response.send_message(
                    "❌ ما قدرتش نصاوب/نلقى Legend Role ديالك. شيك صلاحيات البوت.",
                    ephemeral=True,
                )
                return
    
            new_name = f"👑 {str(self.title_text.value).strip()}"[:100]
            try:
                await role.edit(
                    name=new_name,
                    reason=f"Levels Info Panel — Legend title — {interaction.user}",
                )
                await interaction.response.send_message(
                    f"✅ Legend Role ديالك ولات: **{new_name}**",
                    ephemeral=True,
                )
            except (discord.Forbidden, discord.HTTPException) as e:
                await interaction.response.send_message(
                    f"❌ ما قدرتش نبدل السمية: {e}",
                    ephemeral=True,
                )
    
    
    class XPCreatePollModal(discord.ui.Modal, title="🗳️ صاوب Poll"):
        question = discord.ui.TextInput(
            label="السؤال",
            placeholder="شنو بغيتي تسول الناس؟",
            required=True,
            max_length=200,
        )
        options_text = discord.ui.TextInput(
            label="الاختيارات — فرق بينهم بـ |",
            placeholder="مثال: PS5 | Xbox | PC",
            required=True,
            max_length=500,
        )
    
        def __init__(self, user_id: int, target_channel):
            super().__init__()
            self.user_id = user_id
            self.target_channel = target_channel
    
        async def on_submit(self, interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
                return
    
            data = get_user_level_data(interaction.guild.id, interaction.user.id)
            if data["level"] < 60:
                await interaction.response.send_message(
                    "🔒 إنشاء Poll كيتفتح فـ **Level 60**.",
                    ephemeral=True,
                )
                return
    
            opts = [
                o.strip()
                for o in str(self.options_text.value).split("|")
                if o.strip()
            ][:5]
            if len(opts) < 2:
                await interaction.response.send_message(
                    "❌ خاص على الأقل جوج اختيارات مفصولين بـ `|`.",
                    ephemeral=True,
                )
                return
    
            embed = discord.Embed(
                title=f"🗳️ {str(self.question.value).strip()}",
                description="\n".join(f"**{o}** — 0 صوت" for o in opts),
                color=discord.Color.blurple(),
                timestamp=datetime.now(),
            )
            embed.set_footer(
                text=f"صاوبها {interaction.user.display_name} | {SERVER_NAME}"
            )
            try:
                sent = await self.target_channel.send(
                    embed=embed,
                    view=SimplePollView(opts),
                )
                await interaction.response.send_message(
                    f"✅ الـPoll تنشرات فـ {self.target_channel.mention}.\n{sent.jump_url}",
                    ephemeral=True,
                )
            except (discord.Forbidden, discord.HTTPException) as e:
                await interaction.response.send_message(
                    f"❌ ما قدرتش نبعث فالشانيل المختارة: {e}",
                    ephemeral=True,
                )
    
    
    class XPPollChannelSelect(discord.ui.ChannelSelect):
        def __init__(self, user_id: int):
            self.user_id = user_id
            super().__init__(
                placeholder="📍 اختار الشانيل اللي غادي تنشر فيه الـPoll",
                channel_types=[discord.ChannelType.text, discord.ChannelType.news],
                min_values=1,
                max_values=1,
                row=0,
            )
    
        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
                return
            target = self.values[0]
            await interaction.response.send_modal(
                XPCreatePollModal(interaction.user.id, target)
            )
    
    
    class XPPollDestinationView(discord.ui.View):
        def __init__(self, user_id: int):
            super().__init__(timeout=120)
            self.add_item(XPPollChannelSelect(user_id))
    
    
    class XPRankMemberSelect(discord.ui.UserSelect):
        """Transient User Select: كيبان داخل ephemeral response فقط."""
    
        def __init__(self):
            super().__init__(
                placeholder="👤 اختار عضو باش تشوف الرتبة ديالو",
                min_values=1,
                max_values=1,
            )
    
        async def callback(self, interaction: discord.Interaction):
            if not bot_settings["leveling_enabled"]:
                await interaction.response.edit_message(
                    content="❌ نظام XP معطل دابا.",
                    embed=None,
                    view=None,
                )
                return
    
            selected = self.values[0]
            member = interaction.guild.get_member(selected.id)
            if not member:
                try:
                    member = await interaction.guild.fetch_member(selected.id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    member = None
    
            if not member:
                await interaction.response.edit_message(
                    content="❌ ما قدرتش نجيب معلومات هاد العضو.",
                    embed=None,
                    view=None,
                )
                return
    
            await interaction.response.edit_message(
                content=None,
                embed=build_rank_embed(interaction.guild, member),
                view=None,
            )
    
    
    class XPRankMemberView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.add_item(XPRankMemberSelect())
    
    
    class LevelsResultView(discord.ui.View):
        def __init__(self,user_id:int,lang="darija"):
            super().__init__(timeout=1800); self.user_id,self.lang=int(user_id),lang
            label="Back to Levels" if lang=="en" else "Retour aux niveaux" if lang=="fr" else "رجع للمستويات"
            b=discord.ui.Button(label="↩️ "+label,style=discord.ButtonStyle.secondary,row=0); b.callback=self.back; self.add_item(b); self.add_item(GlobalPrivateLanguageSelect("levels",user_id,lang,row=1))
        async def back(self,interaction):
            if interaction.user.id!=self.user_id: await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.",ephemeral=True); return
            await interaction.response.edit_message(content=None,embed=_panel_language_guide_embed("levels",self.lang),view=LevelsPrivateView(self.user_id,self.lang))
    
    
    class XPRankMemberPrivateSelect(discord.ui.UserSelect):
        def __init__(self,user_id:int,lang="darija"):
            self.user_id,self.lang=int(user_id),lang
            ph="👤 Choose a member" if lang=="en" else "👤 Choisis un membre" if lang=="fr" else "👤 اختار عضو باش تشوف الرتبة ديالو"
            super().__init__(placeholder=ph,min_values=1,max_values=1,row=0)
        async def callback(self,interaction):
            if interaction.user.id!=self.user_id: await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.",ephemeral=True); return
            selected=self.values[0]; member=interaction.guild.get_member(selected.id)
            if not member:
                try: member=await interaction.guild.fetch_member(selected.id)
                except Exception: member=None
            if not member:
                msg="❌ Could not load that member." if self.lang=="en" else "❌ Impossible de charger ce membre." if self.lang=="fr" else "❌ ما قدرتش نجيب معلومات هاد العضو."
                await interaction.response.edit_message(content=msg,embed=None,view=LevelsResultView(self.user_id,self.lang)); return
            await interaction.response.edit_message(content=None,embed=build_rank_embed(interaction.guild,member),view=LevelsResultView(self.user_id,self.lang))
    
    
    class XPRankMemberPrivateView(discord.ui.View):
        def __init__(self,user_id:int,lang="darija"):
            super().__init__(timeout=1800); self.add_item(XPRankMemberPrivateSelect(user_id,lang)); self.add_item(GlobalPrivateLanguageSelect("levels",user_id,lang,row=1))
    
    
    class LevelsPrivateView(discord.ui.View):
        def __init__(self,user_id:int,lang="darija"):
            super().__init__(timeout=1800); self.user_id,self.lang=int(user_id),lang
            labels={
                "darija":["الرتبة ديالي","رتبة عضو","الترتيب","مسار التقدم","بدل النبذة","صاوب استفتاء","اللقب الأسطوري"],
                "en":["My Rank","Member Rank","Leaderboard","Roadmap","Edit Bio","Create Poll","Legend Title"],
                "fr":["Mon rang","Rang d'un membre","Classement","Progression","Modifier Bio","Créer un sondage","Titre Legend"],
            }[lang if lang in {"darija","en","fr"} else "darija"]
            defs=[("📊",labels[0],discord.ButtonStyle.success,self.my_rank),("👤",labels[1],discord.ButtonStyle.primary,self.member_rank),("🏆",labels[2],discord.ButtonStyle.primary,self.leaderboard),("🪜",labels[3],discord.ButtonStyle.secondary,self.roadmap),("📝",labels[4],discord.ButtonStyle.secondary,self.bio),("🗳️",labels[5],discord.ButtonStyle.secondary,self.create_poll),("👑",labels[6],discord.ButtonStyle.secondary,self.legend_title)]
            for i,(emoji,label,style,cb) in enumerate(defs):
                b=discord.ui.Button(label=label,emoji=emoji,style=style,row=0 if i<4 else 1); b.callback=cb; self.add_item(b)
            self.add_item(GlobalPrivateLanguageSelect("levels",self.user_id,lang,row=2))
        async def _ok(self,interaction):
            if interaction.user.id!=self.user_id: await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.",ephemeral=True); return False
            return True
        async def my_rank(self,interaction):
            if not await self._ok(interaction): return
            if not bot_settings["leveling_enabled"]:
                msg="❌ XP system is disabled." if self.lang=="en" else "❌ Le système XP est désactivé." if self.lang=="fr" else "❌ نظام XP معطل دابا."; await interaction.response.edit_message(content=msg,embed=None,view=self); return
            await interaction.response.edit_message(content=None,embed=build_rank_embed(interaction.guild,interaction.user),view=LevelsResultView(self.user_id,self.lang))
        async def member_rank(self,interaction):
            if not await self._ok(interaction): return
            msg="👤 Choose the member:" if self.lang=="en" else "👤 Choisis le membre :" if self.lang=="fr" else "👤 اختار العضو اللي بغيتي تشوف الرتبة ديالو:"
            await interaction.response.edit_message(content=msg,embed=None,view=XPRankMemberPrivateView(self.user_id,self.lang))
        async def leaderboard(self,interaction):
            if not await self._ok(interaction): return
            embed=build_leaderboard_embed(interaction.guild)
            if not embed:
                msg="ℹ️ No XP recorded yet." if self.lang=="en" else "ℹ️ Aucun XP enregistré." if self.lang=="fr" else "ℹ️ ماكاين حتى XP مسجل دابا."; await interaction.response.edit_message(content=msg,embed=None,view=self); return
            await interaction.response.edit_message(content=None,embed=embed,view=LevelsResultView(self.user_id,self.lang))
        async def roadmap(self,interaction):
            if await self._ok(interaction): await interaction.response.edit_message(content=None,embed=build_levelroadmap_embed(),view=LevelsResultView(self.user_id,self.lang))
        async def bio(self,interaction):
            if not await self._ok(interaction): return
            data=get_user_level_data(interaction.guild.id,interaction.user.id)
            if data["level"]<20:
                msg=(f"🔒 Bio unlocks at **Level 20**. You are Level **{data['level']}**." if self.lang=="en" else f"🔒 La Bio se débloque au **niveau 20**. Tu es niveau **{data['level']}**." if self.lang=="fr" else f"🔒 النبذة الشخصية كتفتح فـ **المستوى 20**. نتا دابا فالمستوى **{data['level']}**."); await interaction.response.edit_message(content=msg,embed=None,view=self); return
            await interaction.response.send_modal(XPBioModal())
        async def create_poll(self,interaction):
            if not await self._ok(interaction): return
            data=get_user_level_data(interaction.guild.id,interaction.user.id)
            if data["level"]<60:
                msg=(f"🔒 Polls unlock at **Level 60**. You are Level **{data['level']}**." if self.lang=="en" else f"🔒 Les sondages se débloquent au **niveau 60**. Tu es niveau **{data['level']}**." if self.lang=="fr" else f"🔒 الاستفتاءات كتفتح فـ **المستوى 60**. نتا دابا فالمستوى **{data['level']}**."); await interaction.response.edit_message(content=msg,embed=None,view=self); return
            msg="📍 Choose the channel for your poll:" if self.lang=="en" else "📍 Choisis le salon du sondage :" if self.lang=="fr" else "📍 اختار القناة اللي بغيتي تنشر فيها الاستفتاء:"
            await interaction.response.edit_message(content=msg,embed=None,view=XPPollDestinationView(interaction.user.id))
        async def legend_title(self,interaction):
            if not await self._ok(interaction): return
            data=get_user_level_data(interaction.guild.id,interaction.user.id)
            if data["level"]<100:
                msg=(f"🔒 Legend Title unlocks at **Level 100**. You are Level **{data['level']}**." if self.lang=="en" else f"🔒 Le titre Legend se débloque au **niveau 100**. Tu es niveau **{data['level']}**." if self.lang=="fr" else f"🔒 اللقب الأسطوري كيفتح فـ **المستوى 100**. نتا دابا فالمستوى **{data['level']}**."); await interaction.response.edit_message(content=msg,embed=None,view=self); return
            await interaction.response.send_modal(XPLegendTitleModal())
    
    
    class LevelsInfoView(discord.ui.View):
        """Persistent public XP Center. Public message stays Darija; localized sessions are private."""
        def __init__(self, lang: str = "darija"):
            super().__init__(timeout=None)
            self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
            labels = {
                "darija": ["Rank ديالي", "Rank ديال عضو", "Leaderboard", "Roadmap", "بدل Bio", "صاوب Poll", "Legend Title"],
                "en": ["My Rank", "Member Rank", "Leaderboard", "Roadmap", "Edit Bio", "Create Poll", "Legend Title"],
                "fr": ["Mon rang", "Rang d'un membre", "Classement", "Progression", "Modifier Bio", "Créer un sondage", "Titre Legend"],
            }[self.lang]
            specs = [
                ("ggmw9:levels:my_rank", "📊", labels[0], discord.ButtonStyle.success, self.my_rank, 0),
                ("ggmw9:levels:member_rank_button", "👤", labels[1], discord.ButtonStyle.primary, self.member_rank, 0),
                ("ggmw9:levels:leaderboard", "🏆", labels[2], discord.ButtonStyle.primary, self.leaderboard, 0),
                ("ggmw9:levels:roadmap", "🪜", labels[3], discord.ButtonStyle.secondary, self.roadmap, 0),
                ("ggmw9:levels:bio", "📝", labels[4], discord.ButtonStyle.secondary, self.bio, 2),
                ("ggmw9:levels:create_poll", "🗳️", labels[5], discord.ButtonStyle.secondary, self.create_poll, 2),
                ("ggmw9:levels:legend_title", "👑", labels[6], discord.ButtonStyle.secondary, self.legend_title, 2),
            ]
            for custom_id, emoji, label, style, cb, row in specs:
                b = discord.ui.Button(custom_id=custom_id, emoji=emoji, label=label[:80], style=style, row=row)
                b.callback = cb
                self.add_item(b)
            self.add_item(GlobalPanelLanguageSelect("levels", self.lang, row=1))
    
        def _sync(self, interaction):
            return get_panel_language(interaction.guild.id, interaction.user.id)
    
        async def my_rank(self, interaction):
            lang = self._sync(interaction)
            if not bot_settings["leveling_enabled"]:
                msg = "❌ XP is disabled right now." if lang=="en" else "❌ Le système XP est désactivé." if lang=="fr" else "❌ نظام XP معطل دابا."
                await interaction.response.send_message(msg, ephemeral=True); return
            await interaction.response.send_message(embed=build_rank_embed(interaction.guild, interaction.user), ephemeral=True)
    
        async def member_rank(self, interaction):
            lang = self._sync(interaction)
            if not bot_settings["leveling_enabled"]:
                msg = "❌ XP is disabled right now." if lang=="en" else "❌ Le système XP est désactivé." if lang=="fr" else "❌ نظام XP معطل دابا."
                await interaction.response.send_message(msg, ephemeral=True); return
            prompt = "👤 Choose a member:" if lang=="en" else "👤 Choisis un membre :" if lang=="fr" else "👤 اختار العضو اللي بغيتي تشوف الرتبة ديالو:"
            await interaction.response.send_message(prompt, view=XPRankMemberView(), ephemeral=True)
    
        async def leaderboard(self, interaction):
            lang = self._sync(interaction)
            embed = build_leaderboard_embed(interaction.guild)
            if not embed:
                msg = "ℹ️ No XP recorded yet." if lang=="en" else "ℹ️ Aucun XP enregistré." if lang=="fr" else "ℹ️ ماكاين حتى XP مسجل دابا."
                await interaction.response.send_message(msg, ephemeral=True); return
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
        async def roadmap(self, interaction):
            self._sync(interaction)
            await interaction.response.send_message(embed=build_levelroadmap_embed(), ephemeral=True)
    
        async def bio(self, interaction):
            lang = self._sync(interaction)
            data = get_user_level_data(interaction.guild.id, interaction.user.id)
            if data["level"] < 20:
                msg = (f"🔒 Bio unlocks at **Level 20**. You are Level **{data['level']}**." if lang=="en" else f"🔒 La Bio se débloque au **niveau 20**. Tu es niveau **{data['level']}**." if lang=="fr" else f"🔒 النبذة الشخصية كتفتح فـ **المستوى 20**. نتا دابا فالمستوى **{data['level']}**.")
                await interaction.response.send_message(msg, ephemeral=True); return
            await interaction.response.send_modal(XPBioModal())
    
        async def create_poll(self, interaction):
            lang = self._sync(interaction)
            data = get_user_level_data(interaction.guild.id, interaction.user.id)
            if data["level"] < 60:
                msg = (f"🔒 Polls unlock at **Level 60**. You are Level **{data['level']}**." if lang=="en" else f"🔒 Les sondages se débloquent au **niveau 60**. Tu es niveau **{data['level']}**." if lang=="fr" else f"🔒 الاستفتاءات كتفتح فـ **المستوى 60**. نتا دابا فالمستوى **{data['level']}**.")
                await interaction.response.send_message(msg, ephemeral=True); return
            prompt = "📍 Choose the channel for your poll:" if lang=="en" else "📍 Choisis le salon du sondage :" if lang=="fr" else "📍 اختار القناة اللي بغيتي تنشر فيها الاستفتاء:"
            await interaction.response.send_message(prompt, view=XPPollDestinationView(interaction.user.id), ephemeral=True)
    
        async def legend_title(self, interaction):
            lang = self._sync(interaction)
            data = get_user_level_data(interaction.guild.id, interaction.user.id)
            if data["level"] < 100:
                msg = (f"🔒 Legend Title unlocks at **Level 100**. You are Level **{data['level']}**." if lang=="en" else f"🔒 Le titre Legend se débloque au **niveau 100**. Tu es niveau **{data['level']}**." if lang=="fr" else f"🔒 اللقب الأسطوري كيفتح فـ **المستوى 100**. نتا دابا فالمستوى **{data['level']}**.")
                await interaction.response.send_message(msg, ephemeral=True); return
            await interaction.response.send_modal(XPLegendTitleModal())
    
    
    @bot.command(name="createpoll", hidden=True)
    async def createpoll_cmd(ctx, question: str, *, options: str):
        """صاوب استفتاء بأزرار تفاعلية (بلا حاجة لـ Admin) — متاحة من Level 60 (Milestone perk)"""
        data = get_user_level_data(ctx.guild.id, ctx.author.id)
        if data["level"] < 60:
            await ctx.send("🔒 هاد الميزة كتفتح فـ **Level 60**. كمل شوية باقي ليك!", ephemeral=True, delete_after=8)
            return
    
        opts = [o.strip() for o in options.split("|") if o.strip()][:5]
        if len(opts) < 2:
            await ctx.send("❌ خاصك على الأقل خياريين مفصولين بـ `|` (مثال: `بيتزا | تاكوس`).", ephemeral=True)
            return
    
        embed = discord.Embed(
            title=f"🗳️ {question}",
            description="\n".join(f"**{o}** — 0 صوت" for o in opts),
            color=discord.Color.blurple(), timestamp=datetime.now()
        )
        embed.set_footer(text=f"صاوبها {ctx.author.display_name} | {SERVER_NAME}")
        await ctx.send(embed=embed, view=SimplePollView(opts))
    
    
    @bot.command(name="legendtitle", hidden=True)
    async def legendtitle_cmd(ctx, *, title: str):
        """بدل سمية الرول الشخصي الفريد ديالك — متاحة غير لمن وصل Level 100"""
        data = get_user_level_data(ctx.guild.id, ctx.author.id)
        if data["level"] < 100:
            await ctx.send("🔒 هاد الميزة كتفتح فـ **Level 100**، الحد الأقصى. باقي بزاف الطريق!", ephemeral=True, delete_after=8)
            return
        role = await get_or_create_legend_role(ctx.guild, ctx.author)
        if not role:
            await ctx.send("❌ ما قدرتش نلقى/نصاوب الرول ديالك (يمكن صلاحيات ناقصة عند البوت).", ephemeral=True)
            return
        new_name = f"👑 {title.strip()}"[:100]
        try:
            await role.edit(name=new_name, reason=f"/legendtitle — {ctx.author}")
            await ctx.send(f"✅ الرول ديالك دابا سميتو: **{new_name}**", ephemeral=True)
        except (discord.Forbidden, discord.HTTPException) as e:
            await ctx.send(f"❌ ما قدرتش نبدل السمية: {e}", ephemeral=True)
    
    
    def build_levelroadmap_embed() -> discord.Embed:
        lines = []
        for lvl in sorted(LEVEL_ROLES.keys()):
            p = LEVEL_ROLE_BENEFITS[lvl]
            lines.append(
                f"**Lv.{lvl} — {p['name']}**\n"
                f"> 🛒 -{p['shop_discount_percent']}% Shop • "
                f"🎁 +{p['daily_bonus_percent']}% Daily • "
                f"🏦 {cfg.fmt_money(p['loan_base'])} / {p['loan_interest']}% / {p['loan_days']}d\n"
                f"> {p['feature']}"
            )
        embed = discord.Embed(
            title="🪜 خارطة طريق Level Roles (5 → 100)",
            description="\n\n".join(lines)[:4000],
            color=discord.Color.gold()
        )
        embed.set_footer(
            text=f"{SERVER_NAME} | عندك غير أعلى Level Role — القديمة كتتحيد أوتوماتيكياً"
        )
        return embed
    
    
    @bot.command(name="levelroadmap", aliases=["milestones"], hidden=True)
    async def levelroadmap_cmd(ctx):
        """كيبين لائحة كاملة بكل Level Roles والمكافآت ديالهم."""
        await ctx.send(embed=build_levelroadmap_embed())
    
    
    def build_leaderboard_embed(guild: discord.Guild) -> Optional[discord.Embed]:
        """
        أفضل 10 من الأعضاء الحاليين فقط.
    
        XP ديال العضو اللي خرج كتبقى محفوظة فـ levels_db:
        - وهو خارج: ما كيبانش فالLeaderboard.
        - إلا رجع: كيرجع أوتوماتيكياً للمركز اللي كتستحق XP ديالو.
        """
        ranking = get_current_member_xp_ranking(guild)[:10]
        if not ranking:
            return None
    
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (user_id, data) in enumerate(ranking):
            member = guild.get_member(int(user_id))
            if not member:
                # حماية إضافية ضد أي cache race نادر.
                continue
    
            prefix = medals[i] if i < len(medals) else f"#{i + 1}"
            badge = "👑 " if data["level"] >= 100 else ("🌟 " if data["level"] >= 70 else "")
            lines.append(
                f"{prefix} {badge}{member.mention} — "
                f"Level {data['level']} ({total_xp_earned(data)} XP)"
            )
    
        if not lines:
            return None
    
        embed = discord.Embed(
            title="🏆 لائحة الشرف (Leaderboard)",
            description="\n".join(lines),
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.set_footer(
            text=f"{SERVER_NAME} | غير الأعضاء الحاليين • XP كتبقى محفوظة إلا خرجتي"
        )
        return embed
    
    
    @bot.command(name="leaderboard", aliases=["lb", "top"], hidden=True)
    async def leaderboard_cmd(ctx):
        """كيبين أفضل 10 أعضاء نشيطين فالسيرفر (الأكثر XP)"""
        if not bot_settings['leveling_enabled']:
            await ctx.send("❌ نظام Leveling معطل دابا. شعلو من `/botpanel` (Admin).", delete_after=6)
            return
    
        embed = build_leaderboard_embed(ctx.guild)
        if not embed:
            await ctx.send("ماكاين حتى عضو ربح XP دابا.")
            return
        await ctx.send(embed=embed)
    
    
    async def refresh_xp_leaderboard_now():
        """Refresh فوري للرسالة العامة ديال Leaderboard."""
        if not bot_settings['leveling_enabled'] or not LEADERBOARD_CHANNEL_ID:
            return
        channel = bot.get_channel(LEADERBOARD_CHANNEL_ID)
        if not channel:
            return
    
        guild = channel.guild
        embed = build_leaderboard_embed(guild)
        msg_id = leaderboard_message_ids.get(str(guild.id))
    
        # إذا ما بقا حتى عضو مؤهل، نبدلو نفس الرسالة بدل نخلي Top قديم.
        if not embed:
            embed = discord.Embed(
                title="🏆 لائحة الشرف (Leaderboard)",
                description="ماكاين حتى عضو حالي عندو XP مسجلة دابا.",
                color=discord.Color.gold(),
                timestamp=datetime.now(),
            )
            embed.set_footer(text=f"{SERVER_NAME} | Leveling System")
    
        def remember(message_id: int):
            if leaderboard_message_ids.get(str(guild.id)) != int(message_id):
                leaderboard_message_ids[str(guild.id)] = int(message_id)
                save_leaderboard_message_ids()

        await upsert_fixed_panel(
            bot,
            channel,
            key="xp_leaderboard",
            matches=lambda msg: (
                msg.author == bot.user
                and bool(msg.embeds)
                and (msg.embeds[0].title or "") == "🏆 لائحة الشرف (Leaderboard)"
                and (
                    f"{SERVER_NAME} | Leveling System" in (
                        msg.embeds[0].footer.text if msg.embeds[0].footer else ""
                    )
                    or f"{SERVER_NAME} | غير الأعضاء الحاليين" in (
                        msg.embeds[0].footer.text if msg.embeds[0].footer else ""
                    )
                )
            ),
            embed=embed,
            message_id=msg_id,
            save_message_id=remember,
            history_limit=100,
        )
    
    
    @tasks.loop(minutes=LEADERBOARD_UPDATE_MINUTES)
    async def update_leaderboard():
        """كتحدث رسالة لائحة الشرف أوتوماتيكياً فـ LEADERBOARD_CHANNEL_ID كل LEADERBOARD_UPDATE_MINUTES
        (كتبدل نفس الرسالة، ماكتبعثش وحدة جديدة كل مرة)."""
        await refresh_xp_leaderboard_now()
    
    
    @update_leaderboard.before_loop
    async def before_update_leaderboard():
        await bot.wait_until_ready()
    
    
    @update_leaderboard.error
    async def update_leaderboard_error(error):
        print(f"[LEADERBOARD] ❌❌ خطأ كبير وقف الـ loop: {error}")
        await asyncio.sleep(5)
        if not update_leaderboard.is_running():
            update_leaderboard.restart()
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
