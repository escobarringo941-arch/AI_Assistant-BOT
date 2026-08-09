# -*- coding: utf-8 -*-
"""Unchanged ordered source component: applications."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║   Phase 7 — نظام Applications (طلبات الانضمام للإدارة)  ║
    # ═══════════════════════════════════════════════════════
    
    def _is_staff_reviewer(member: discord.Member) -> bool:
        """كيتأكد بلي العضو عندو صلاحية يقبل/يرفض اقتراحات (Owner + الأدوار المعفية، شامل Moderators)"""
        if OWNER_ID and member.id == OWNER_ID:
            return True
        return any(role.id in EXEMPT_ROLE_IDS for role in member.roles)
    
    
    def _is_application_reviewer(member: discord.Member) -> bool:
        """كيتأكد بلي العضو عندو صلاحية يقبل/يرفض طلبات Applications — Owner
        و APPLICATIONS_REVIEWER_ROLE_IDS (Admins) بوحدهم، Moderators ماشي معنيين."""
        if OWNER_ID and member.id == OWNER_ID:
            return True
        return any(role.id in APPLICATIONS_REVIEWER_ROLE_IDS for role in member.roles)
    
    
    def _application_t(lang: str, key: str, **fmt) -> str:
        data={
            "darija":{"title":"📋 قدم لفريق الإدارة","desc":"بغيتي تكون جزء من فريق الإدارة ديال السيرفر؟ من هاد الواجهة تقدر تعمر الاستمارة، والإدارة غادي تجاوبك فالخاص.","apply":"قدم طلب للإدارة","saved":"✅ اللغة ديالك ولات **الدارجة**.","pending":"⚠️ عندك ديجا طلب مبعوث (#{id}) مازال كيتسنى المراجعة.","cooldown":"⏳ طلبك السابق ترفض. خاصك تصبر تقريباً {hours} ساعة قبل ما تعاود تقدم.","sent":"✅ تم بعث طلبك (#{id})! الإدارة غادي تجاوبك فالخاص ملي تراجعو."},
            "en":{"title":"📋 Staff Applications","desc":"Want to join the server staff team? Fill in the application here and staff will reply by DM after reviewing it.","apply":"Apply for Staff","saved":"✅ Your language is now **English**.","pending":"⚠️ You already have application #{id} waiting for review.","cooldown":"⏳ Your previous application was rejected. Wait about {hours} hours before applying again.","sent":"✅ Application #{id} was sent! Staff will reply by DM after reviewing it."},
            "fr":{"title":"📋 Candidatures Staff","desc":"Tu veux rejoindre l'équipe du serveur ? Remplis le formulaire ici et le staff te répondra en DM après l'avoir examiné.","apply":"Postuler au Staff","saved":"✅ Ta langue est maintenant **Français**.","pending":"⚠️ Ta candidature #{id} est déjà en attente de révision.","cooldown":"⏳ Ta candidature précédente a été refusée. Attends environ {hours} heures avant de repostuler.","sent":"✅ Candidature #{id} envoyée ! Le staff te répondra en DM après examen."},
        }
        lang=lang if lang in data else "darija"; value=data[lang].get(key,data["darija"].get(key,key)); return value.format(**fmt) if fmt else value
    
    
    def _application_home_embed(lang: str="darija") -> discord.Embed:
        e=discord.Embed(title=_application_t(lang,"title"),description=_application_t(lang,"desc"),color=discord.Color.blurple())
        foot="🌐 اللغة شخصية وتقدر تبدلها فوقاش بغيتي." if lang=="darija" else "🌐 Your language is personal and can be changed anytime." if lang=="en" else "🌐 Ta langue est personnelle et peut être changée à tout moment."
        e.set_footer(text=foot); return e
    
    
    class ApplicationModal(discord.ui.Modal):
        def __init__(self, lang: str="darija"):
            self.lang=lang
            super().__init__(title="📋 Staff Application" if lang=="en" else "📋 Candidature Staff" if lang=="fr" else "📋 طلب انضمام لفريق الإدارة")
            self.age=discord.ui.TextInput(label="How old are you?" if lang=="en" else "Quel âge as-tu ?" if lang=="fr" else "شحال عندك من عام؟",placeholder="Example: 18" if lang=="en" else "Exemple : 18" if lang=="fr" else "مثلا: 18",max_length=10)
            self.experience=discord.ui.TextInput(label="Previous moderator/admin experience?" if lang=="en" else "Expérience comme modérateur/admin ?" if lang=="fr" else "عندك تجربة سابقة فالإشراف ولا الإدارة؟",style=discord.TextStyle.paragraph,required=False,max_length=500,placeholder="Write 'No' or describe your experience" if lang=="en" else "Écris 'Non' ou décris ton expérience" if lang=="fr" else "اكتب 'لا' إلا ماعندكش، ولا فين ومنين إلا عندك")
            self.why=discord.ui.TextInput(label="Why do you want to join Staff?" if lang=="en" else "Pourquoi veux-tu rejoindre le Staff ?" if lang=="fr" else "علاش بغيتي تكون من فريق الإدارة فهاد السيرفر؟",style=discord.TextStyle.paragraph,max_length=700)
            self.availability=discord.ui.TextInput(label="When/how long are you available?" if lang=="en" else "Quand/combien de temps es-tu disponible ?" if lang=="fr" else "فوقاش/شحال من ساعة كتكون متواجد؟",max_length=150,placeholder="Example: daily 6 PM–11 PM" if lang=="en" else "Exemple : tous les jours 18h–23h" if lang=="fr" else "مثلا: كل نهار من 6 مغرب لـ 11 ليل")
            for item in (self.age,self.experience,self.why,self.availability): self.add_item(item)
    
        async def on_submit(self, interaction: discord.Interaction):
            applicant=interaction.user; app_id=applications_db.get("next_id",1)
            review_channel_id=APPLICATIONS_REVIEW_CHANNEL_ID or MOD_LOGS_CHANNEL_ID; review_channel=bot.get_channel(review_channel_id) if review_channel_id else None
            if not review_channel:
                msg="❌ Review channel is unavailable. Contact staff." if self.lang=="en" else "❌ Le salon de révision est indisponible. Contacte le staff." if self.lang=="fr" else "❌ وقع مشكل تقني فقناة مراجعة الطلبات، بلغ الإدارة."
                await interaction.response.send_message(msg,ephemeral=True); return
            embed=discord.Embed(title=f"📋 طلب انضمام #{app_id}",color=discord.Color.blurple(),timestamp=datetime.now()); embed.set_author(name=str(applicant),icon_url=applicant.display_avatar.url)
            embed.add_field(name="👤 المتقدم",value=applicant.mention,inline=False); embed.add_field(name="🎂 العمر",value=self.age.value or "—",inline=True); embed.add_field(name="🕐 التواجد",value=self.availability.value or "—",inline=True); embed.add_field(name="📜 تجربة سابقة",value=self.experience.value or "بلا تجربة",inline=False); embed.add_field(name="💬 علاش بغيتي تكون من فريق الإدارة",value=self.why.value,inline=False); embed.set_footer(text=f"{SERVER_NAME} | Application #{app_id} | Pending")
            reviewer_mentions=" ".join(f"<@&{rid}>" for rid in APPLICATIONS_REVIEWER_ROLE_IDS)
            try: review_msg=await review_channel.send(content=reviewer_mentions or None,embed=embed,view=ApplicationReviewView())
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}",ephemeral=True); return
            applications_db["next_id"]=app_id+1; applications_db.setdefault("applications",{})[str(app_id)]={"applicant_id":applicant.id,"answers":{"age":str(self.age.value),"experience":str(self.experience.value),"why":str(self.why.value),"availability":str(self.availability.value)},"status":"pending","review_message_id":review_msg.id,"review_channel_id":review_channel.id,"submitted_at":datetime.now().strftime("%Y-%m-%d %H:%M:%S"),"decided_by":None,"decided_at":None}; save_applications()
            await upsert_ephemeral_panel(interaction,"applications",content=_application_t(self.lang,"sent",id=app_id),embed=_application_home_embed(self.lang),view=ApplicationPrivateView(interaction.user.id,self.lang))
    
    
    class ApplicationPrivateLanguageSelect(discord.ui.Select):
        def __init__(self,user_id:int,lang="darija",*,row=1):
            self.user_id,self.lang=int(user_id),lang
            super().__init__(placeholder="🌐 اللغة / Language / Langue",options=[discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦",default=lang=="darija"),discord.SelectOption(label="English",value="en",emoji="🇬🇧",default=lang=="en"),discord.SelectOption(label="Français",value="fr",emoji="🇫🇷",default=lang=="fr")],min_values=1,max_values=1,row=row)
        async def callback(self,interaction):
            if interaction.user.id!=self.user_id: await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.",ephemeral=True); return
            lang=set_panel_language(interaction.guild.id,interaction.user.id,self.values[0]); await interaction.response.edit_message(content=_application_t(lang,"saved"),embed=_application_home_embed(lang),view=ApplicationPrivateView(self.user_id,lang))
    
    
    class ApplicationPrivateView(discord.ui.View):
        def __init__(self,user_id:int,lang="darija"):
            super().__init__(timeout=1800); self.user_id,self.lang=int(user_id),lang
            b=discord.ui.Button(label="📋 "+_application_t(lang,"apply"),style=discord.ButtonStyle.primary,row=0); b.callback=self.apply; self.add_item(b); self.add_item(ApplicationPrivateLanguageSelect(user_id,lang,row=1))
        async def apply(self,interaction):
            if interaction.user.id!=self.user_id: await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.",ephemeral=True); return
            pending_id,_=get_pending_application_for_user(interaction.user.id)
            if pending_id: await interaction.response.edit_message(content=_application_t(self.lang,"pending",id=pending_id),embed=_application_home_embed(self.lang),view=self); return
            remaining=application_cooldown_remaining(interaction.user.id)
            if remaining:
                hours=int(remaining.total_seconds()//3600)+1; await interaction.response.edit_message(content=_application_t(self.lang,"cooldown",hours=hours),embed=_application_home_embed(self.lang),view=self); return
            await interaction.response.send_modal(ApplicationModal(self.lang))
    
    
    class ApplicationLanguageSelect(discord.ui.Select):
        """Public Darija selector; opens a fresh private localized Application panel."""
        def __init__(self, lang: str = "darija"):
            self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
            super().__init__(
                placeholder="🌐 اللغة / Language / Langue",
                options=[
                    discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", default=self.lang == "darija"),
                    discord.SelectOption(label="English", value="en", emoji="🇬🇧", default=self.lang == "en"),
                    discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", default=self.lang == "fr"),
                ],
                min_values=1, max_values=1,
                custom_id="ggmw9:applications:language", row=1,
            )
    
        async def callback(self, interaction: discord.Interaction):
            lang = set_panel_language(interaction.guild.id, interaction.user.id, self.values[0])
            await interaction.response.send_message(
                content=None,
                embed=_application_home_embed(lang),
                view=ApplicationPrivateView(interaction.user.id, lang),
                ephemeral=True,
            )
    
    
    class ApplicationPanelView(discord.ui.View):
        """One public Darija Application message; localized panels are private."""
        def __init__(self, lang: str = "darija"):
            super().__init__(timeout=None)
            self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
            apply_button = discord.ui.Button(
                label=("📋 " + _application_t(self.lang, "apply"))[:80],
                style=discord.ButtonStyle.primary,
                custom_id="open_application_button",
                row=0,
            )
            apply_button.callback = self.open_application_button
            self.add_item(apply_button)
            self.add_item(ApplicationLanguageSelect(self.lang))
    
        async def open_application_button(self, interaction: discord.Interaction):
            member = interaction.user
            if not isinstance(member, discord.Member):
                await interaction.response.send_message("❌ وقع مشكل، عاود من جديد.", ephemeral=True)
                return
            lang = get_panel_language(interaction.guild.id, member.id)
            pending_id, _ = get_pending_application_for_user(member.id)
            if pending_id:
                await interaction.response.send_message(_application_t(lang, "pending", id=pending_id), ephemeral=True)
                return
            remaining = application_cooldown_remaining(member.id)
            if remaining:
                hours = int(remaining.total_seconds() // 3600) + 1
                await interaction.response.send_message(_application_t(lang, "cooldown", hours=hours), ephemeral=True)
                return
            await interaction.response.send_modal(ApplicationModal(lang))
    
    
    class ApplicationReviewView(discord.ui.View):
        """أزرار القبول/الرفض جوة review channel. Persistent — كتلقى الطلب بواسطة
        message id ديال الرسالة اللي فيها الأزرار (بحال TicketControlView كيلقى
        الـ ticket بواسطة channel id)."""
    
        def __init__(self):
            super().__init__(timeout=None)
    
        @discord.ui.button(label="✅ قبول", style=discord.ButtonStyle.success, custom_id="app_accept_button")
        async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._decide(interaction, accepted=True)
    
        @discord.ui.button(label="❌ رفض", style=discord.ButtonStyle.danger, custom_id="app_reject_button")
        async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await self._decide(interaction, accepted=False)
    
        async def _decide(self, interaction: discord.Interaction, accepted: bool):
            member = interaction.user
            if not isinstance(member, discord.Member) or not _is_application_reviewer(member):
                await interaction.response.send_message("❌ هاد الزر خاص غير بـ Owner والـ Admins.", ephemeral=True)
                return
    
            app_id, record = find_application_by_message_id(interaction.message.id)
            if not record:
                await interaction.response.send_message("❌ ماكاينش هاد الطلب فالسجل ديالنا.", ephemeral=True)
                return
            if record.get("status") != "pending":
                await interaction.response.send_message("⚠️ هاد الطلب تدار فيه قرار من قبل.", ephemeral=True)
                return
    
            record["status"] = "accepted" if accepted else "rejected"
            record["decided_by"] = member.id
            record["decided_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if not accepted:
                applications_db.setdefault("last_rejected", {})[str(record["applicant_id"])] = record["decided_at"]
            save_applications()
    
            guild = interaction.guild
            applicant = guild.get_member(record["applicant_id"]) if guild else None
    
            embed = interaction.message.embeds[0]
            embed.color = discord.Color.green() if accepted else discord.Color.red()
            embed.add_field(
                name="✅ القرار" if accepted else "❌ القرار",
                value=f"{'تقبل' if accepted else 'تُرفض'} من طرف {member.mention}",
                inline=False
            )
            embed.set_footer(text=f"{SERVER_NAME} | Application #{app_id} | {'Accepted' if accepted else 'Rejected'}")
    
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=embed, view=self)
    
            if applicant:
                try:
                    if accepted:
                        if APPLICATION_ACCEPTED_ROLE_ID:
                            role = guild.get_role(APPLICATION_ACCEPTED_ROLE_ID)
                            if role:
                                await applicant.add_roles(role, reason=f"Application #{app_id} تقبل")
                        await applicant.send(
                            f"🎉 مبروك! طلبك (#{app_id}) باش تكون Staff فـ **{SERVER_NAME}** تقبل! "
                            f"الإدارة غادي تتواصل معاك قريب."
                        )
                    else:
                        await applicant.send(
                            f"❌ طلبك (#{app_id}) باش تكون Staff فـ **{SERVER_NAME}** تُرفض هاد المرة. "
                            f"تقدر تعاود تقدم من بعد {APPLICATIONS_COOLDOWN_HOURS} ساعة."
                        )
                except Exception:
                    pass
    
            if guild:
                await log_action(
                    guild,
                    f"📋 Application #{app_id} — {'قبول' if accepted else 'رفض'}",
                    f"**المتقدم:** <@{record['applicant_id']}>\n**القرار من طرف:** {member.mention}",
                    discord.Color.green() if accepted else discord.Color.red()
                )
    
    
    async def setup_applications_panel(guild: discord.Guild):
        if not APPLICATIONS_PANEL_CHANNEL_ID: return
        channel=bot.get_channel(APPLICATIONS_PANEL_CHANNEL_ID)
        if not channel: return
        embed=_application_home_embed("darija"); view=ApplicationPanelView("darija")
        message = await upsert_fixed_panel(
            bot,
            channel,
            key="applications",
            matches=lambda message: (
                message.author == bot.user
                and bool(message.embeds)
                and any(
                    marker in (message.embeds[0].title or "")
                    for marker in ("قدم لفريق الإدارة", "Staff Applications", "Candidatures Staff")
                )
            ),
            embed=embed,
            view=view,
            history_limit=None,
        )
        if message is None:
            print("[APPLICATIONS] panel update failed")
    
    
    @bot.hybrid_command(name="setupapplications")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setupapplications_cmd(ctx):
        """كيصاوب/يعاود يصاوب رسالة اللوحة ديال Applications فـ APPLICATIONS_PANEL_CHANNEL_ID (Admin)"""
        if not APPLICATIONS_PANEL_CHANNEL_ID:
            await ctx.send("❌ حط `APPLICATIONS_PANEL_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
            return
        if not APPLICATIONS_REVIEW_CHANNEL_ID:
            await ctx.send("⚠️ `APPLICATIONS_REVIEW_CHANNEL_ID` فارغة — غايستعمل MOD_LOGS_CHANNEL_ID بدلها.", delete_after=10)
        await setup_applications_panel(ctx.guild)
        await ctx.send("✅ رسالة اللوحة ديال Applications تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)
    
    
    @bot.hybrid_command(name="applications")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def applications_cmd(ctx):
        """كيبين لائحة الطلبات اللي مازال Pending (Owner + Admins فقط)"""
        if not _is_application_reviewer(ctx.author):
            await ctx.send("❌ هاد الأمر خاص غير بـ Owner والـ Admins.", delete_after=5)
            return
        pending = [
            (app_id, r) for app_id, r in applications_db.get("applications", {}).items()
            if r.get("status") == "pending"
        ]
        if not pending:
            await ctx.send("✅ ماكاين حتى طلب معلق دابا.")
            return
        lines = [f"**#{app_id}** — <@{r['applicant_id']}> (بعث فـ {r.get('submitted_at', '—')})"
                  for app_id, r in sorted(pending, key=lambda x: int(x[0]))]
        embed = discord.Embed(
            title=f"📋 الطلبات المعلقة ({len(pending)})",
            description="\n".join(lines),
            color=discord.Color.blurple()
        )
        embed.set_footer(text=f"{SERVER_NAME} | Applications")
        await ctx.send(embed=embed)
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
