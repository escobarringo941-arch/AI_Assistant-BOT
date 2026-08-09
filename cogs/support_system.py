# -*- coding: utf-8 -*-
"""Unchanged ordered source component: support_system."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║              نظام Tickets (channels خاصة)               ║
    # ═══════════════════════════════════════════════════════
    
    def _is_ticket_staff(member: discord.Member) -> bool:
        if OWNER_ID and member.id == OWNER_ID:
            return True
        return any(role.id in EXEMPT_ROLE_IDS for role in member.roles)
    
    
    def _can_claim_ticket(member: discord.Member) -> bool:
        """واش هاد العضو يقدر يستلم (Claim) Ticket — Owner + Admin بوحدو (ماشي Moderator)."""
        if OWNER_ID and member.id == OWNER_ID:
            return True
        return any(role.id == ADMIN_ROLE_ID for role in member.roles)
    
    
    class TicketControlView(discord.ui.View):
        """الأزرار جوة channel ديال ticket وحدة (Claim + Close). Persistent —
        كتخدم بـ interaction.channel باش تعرف شنو الـ ticket، بلا ما تحتاج تخزن
        شي حاجة خاصة بكل ticket فـ الـ View نفسها."""
    
        def __init__(self):
            super().__init__(timeout=None)
    
        @discord.ui.button(label="🙋 نستلمو (Claim)", style=discord.ButtonStyle.secondary, custom_id="ticket_claim_button")
        async def claim_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            member = interaction.user
            if not isinstance(member, discord.Member) or not _can_claim_ticket(member):
                await interaction.response.send_message("❌ هاد الزر خاص غير بالـ Owner و الـ Admin.", ephemeral=True)
                return
    
            record = tickets_db.get("open", {}).get(str(interaction.channel.id))
            if not record:
                await interaction.response.send_message("❌ ماكاينش هاد الـ ticket فالسجل ديالنا.", ephemeral=True)
                return
    
            record["claimed_by"] = member.id
            save_tickets()
            await interaction.response.send_message(f"✅ {member.mention} استلم هاد الـ ticket ودابا كيتكلف بيه.")
    
        @discord.ui.button(label="🔒 سد الـ Ticket", style=discord.ButtonStyle.danger, custom_id="ticket_close_button")
        async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            member = interaction.user
            record = tickets_db.get("open", {}).get(str(interaction.channel.id))
            if not record:
                await interaction.response.send_message("❌ ماكاينش هاد الـ ticket فالسجل ديالنا (ممكن تسد من قبل).", ephemeral=True)
                return
    
            is_opener = member.id == record.get("opener_id")
            if not (is_opener or (isinstance(member, discord.Member) and _is_ticket_staff(member))):
                await interaction.response.send_message("❌ غير صاحب الـ ticket ولا الإدارة يقدرو يسدوه.", ephemeral=True)
                return
    
            await interaction.response.send_message("🔒 غادي نسدو هاد الـ ticket من بعد 5 ثواني... كنجمعو transcript.")
    
            channel = interaction.channel
            guild = interaction.guild
            ticket_id = record["id"]
    
            # ═══════ تجميع transcript بسيط (نص) ═══════
            lines = []
            try:
                async for msg in channel.history(limit=500, oldest_first=True):
                    ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
                    content = msg.content or "[بلا نص / embed / attachment]"
                    lines.append(f"[{ts}] {msg.author}: {content}")
            except Exception as e:
                lines.append(f"[خطأ فـ تجميع transcript: {e}]")
    
            transcript_text = "\n".join(lines) if lines else "ماكاين حتى رسالة."
            transcript_path = f"/tmp/ticket_{ticket_id}_transcript.txt"
            try:
                with open(transcript_path, "w", encoding="utf-8") as f:
                    f.write(transcript_text)
            except Exception as e:
                print(f"[TICKETS] خطأ فـ كتابة transcript: {e}")
                transcript_path = None
    
            log_channel_id = TICKET_LOGS_CHANNEL_ID or MOD_LOGS_CHANNEL_ID
            log_channel = bot.get_channel(log_channel_id) if log_channel_id else None
            if log_channel:
                opener_id = record.get("opener_id")
                claimed_by = record.get("claimed_by")
                embed = discord.Embed(
                    title=f"🎫 Ticket #{ticket_id} — تسد",
                    color=discord.Color.dark_grey(),
                    timestamp=datetime.now()
                )
                embed.add_field(name="👤 صاحب الـ Ticket", value=f"<@{opener_id}>" if opener_id else "غير معروف", inline=False)
                embed.add_field(name="🙋 استلمو", value=(f"<@{claimed_by}>" if claimed_by else "محدش استلمو"), inline=False)
                embed.add_field(name="🔒 سداه", value=member.mention, inline=False)
                embed.add_field(name="🕐 تحلق فـ", value=record.get("opened_at", "—"), inline=False)
                embed.set_footer(text=f"{SERVER_NAME} | Ticket #{ticket_id}")
                try:
                    if transcript_path:
                        await log_channel.send(embed=embed, file=discord.File(transcript_path, filename=f"ticket-{ticket_id}-transcript.txt"))
                    else:
                        await log_channel.send(embed=embed)
                except Exception as e:
                    print(f"[TICKETS] خطأ فـ بعث الـ transcript: {e}")
    
            if str(channel.id) in tickets_db.get("open", {}):
                del tickets_db["open"][str(channel.id)]
                save_tickets()
    
            await asyncio.sleep(5)
            try:
                await channel.delete(reason=f"Ticket #{ticket_id} تسد من طرف {member}")
            except Exception as e:
                print(f"[TICKETS] خطأ فـ حذف الـ channel: {e}")
    
    
    
    # ═══════════════════════════════════════════════════════
    # ║   🆘 Unified Support Center — Reports + Tickets     ║
    # ═══════════════════════════════════════════════════════
    
    _support_report_cooldowns = {}
    
    
    def _support_report_cooldown_remaining(user_id: int, seconds: int = 60) -> int:
        now = datetime.now().timestamp()
        last = float(_support_report_cooldowns.get(int(user_id), 0) or 0)
        remaining = int(seconds - (now - last))
        return max(0, remaining)
    
    
    def _mark_support_report(user_id: int):
        _support_report_cooldowns[int(user_id)] = datetime.now().timestamp()
    
    
    async def send_support_report(
        guild: discord.Guild,
        reporter: discord.Member,
        *,
        target: Optional[discord.Member] = None,
        details: str,
        context_link: str = "",
    ) -> tuple:
        """كيبعث Report للـStaff backend بلا حتى رسالة عامة."""
        if not REPORTS_CHANNEL_ID:
            return False, "❌ Reports backend ماشي مكوّن."
    
        reports_channel = guild.get_channel(REPORTS_CHANNEL_ID) or bot.get_channel(REPORTS_CHANNEL_ID)
        if not reports_channel:
            return False, "❌ ما قدرتش نلقى Reports Channel ديال الإدارة."
    
        remaining = _support_report_cooldown_remaining(reporter.id)
        if remaining > 0:
            return False, f"⏳ صبر **{remaining}ث** قبل ما تبعث بلاغ آخر."
    
        details = (details or "").strip()
        if not details:
            return False, "❌ خاصك تشرح شنو وقع."
    
        _mark_support_report(reporter.id)
    
        embed = discord.Embed(
            title="🚨 بلاغ جديد — Support Center",
            color=discord.Color.orange(),
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="👤 المبلّغ",
            value=f"{reporter.mention} ({reporter})\nID: `{reporter.id}`",
            inline=False,
        )
        if target:
            embed.add_field(
                name="🎯 العضو المبلَّغ عنه",
                value=f"{target.mention} ({target})\nID: `{target.id}`",
                inline=False,
            )
        else:
            embed.add_field(name="⚠️ نوع البلاغ", value="بلاغ عام / بلا عضو محدد", inline=False)
    
        embed.add_field(name="📝 التفاصيل", value=details[:1024], inline=False)
    
        if context_link.strip():
            embed.add_field(
                name="🔗 Channel / Message Link",
                value=context_link.strip()[:1000],
                inline=False,
            )
    
        embed.add_field(
            name="📍 من Support Center",
            value=f"<#{SUPPORT_CENTER_CHANNEL_ID}>",
            inline=False,
        )
        embed.set_footer(text="GGMW9 | Private Report System")
    
        mention_roles = " ".join(f"<@&{rid}>" for rid in EXEMPT_ROLE_IDS)
        try:
            await reports_channel.send(
                content=mention_roles or None,
                embed=embed,
                allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False),
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            return False, f"❌ ما قدرتش نوصل البلاغ للإدارة: {e}"
    
        # Owner DM — نفس السلوك القديم
        if OWNER_ID:
            try:
                owner = guild.get_member(OWNER_ID) or await bot.fetch_user(OWNER_ID)
                if owner:
                    await owner.send(embed=embed)
            except Exception:
                pass
    
        return True, "✅ توصل البلاغ للإدارة **بشكل خاص**. شكراً على التبليغ."
    
    
    async def create_support_ticket(
        interaction: discord.Interaction,
        *,
        ticket_kind: str = "دعم عام",
        initial_details: str = "",
    ):
        """Source of truth واحد لإنشاء Ticket من Support Center أو fallback القديم."""
        member = interaction.user
        guild = interaction.guild
    
        if not guild or not isinstance(member, discord.Member):
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ وقع مشكل، عاود من جديد.", ephemeral=True)
            return
    
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True, thinking=True)
    
        if not TICKETS_CATEGORY_ID:
            await interaction.followup.send(
                "❌ نظام Tickets ماشي مكوّن دابا. بلغ الإدارة.",
                ephemeral=True,
            )
            return
    
        category = guild.get_channel(TICKETS_CATEGORY_ID)
        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.followup.send(
                "❌ ما لقيتش Category ديال Tickets. بلغ الإدارة.",
                ephemeral=True,
            )
            return
    
        existing_channel_id, _existing_record = get_open_ticket_for_user(member.id)
        if existing_channel_id:
            existing_channel = guild.get_channel(int(existing_channel_id))
            if existing_channel:
                await interaction.followup.send(
                    f"⚠️ عندك ديجا Ticket مفتوح: {existing_channel.mention}",
                    ephemeral=True,
                )
                return
            else:
                tickets_db.get("open", {}).pop(existing_channel_id, None)
                save_tickets()
    
        ticket_id = int(tickets_db.get("next_id", 1) or 1)
        tickets_db["next_id"] = ticket_id + 1
    
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                read_message_history=True,
            ),
        }
        for rid in EXEMPT_ROLE_IDS:
            role = guild.get_role(rid)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                )
    
        safe_name = re.sub(
            r"[^a-z0-9\-]",
            "",
            member.name.lower().replace(" ", "-"),
        ) or "user"
        channel_name = f"ticket-{ticket_id}-{safe_name}"[:90]
    
        try:
            new_channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason=f"Ticket #{ticket_id} ({ticket_kind}) فتحو {member}",
            )
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ البوت خاصو **Manage Channels** باش يفتح Ticket.",
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.followup.send(
                f"❌ خطأ فـخلق Ticket: {e}",
                ephemeral=True,
            )
            return
    
        tickets_db.setdefault("open", {})[str(new_channel.id)] = {
            "id": ticket_id,
            "opener_id": member.id,
            "opened_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "claimed_by": None,
            "kind": ticket_kind,
            "source": "support_center",
        }
        save_tickets()
    
        staff_mentions = " ".join(f"<@&{rid}>" for rid in EXEMPT_ROLE_IDS)
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_id} — {ticket_kind}",
            description=(
                f"مرحبا {member.mention}! هادي محادثة خاصة بينك وبين الإدارة.\n\n"
                "🙋 الإدارة تقدر تدير **Claim**.\n"
                "🔒 ملي تسالي، نتا ولا الإدارة يقدرو يسدو Ticket، "
                "والـTranscript كيمشي للـLogs."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        if initial_details.strip():
            embed.add_field(
                name="📝 التفاصيل اللي عطيتينا",
                value=initial_details.strip()[:1024],
                inline=False,
            )
        embed.set_footer(text=f"{SERVER_NAME} | Ticket #{ticket_id}")
    
        await new_channel.send(
            content=f"{member.mention} {staff_mentions}".strip(),
            embed=embed,
            view=TicketControlView(),
            allowed_mentions=discord.AllowedMentions(users=True, roles=True, everyone=False),
        )
        await interaction.followup.send(
            f"✅ تحل Ticket ديالك: {new_channel.mention}",
            ephemeral=True,
        )
    
    
    def _support_t(lang: str, key: str) -> str:
        data = {
            "darija": {
                "report_member":"بلغ على عضو", "general":"بلاغ عام", "ticket":"فتح تذكرة", "help":"طلب مساعدة",
                "member_prompt":"👤 اختار العضو اللي بغيتي تبلغ عليه. إلا ما بانش، قلب عليه بالسميّة فالبحث.",
                "not_yours":"❌ هاد الجلسة ماشي ديالك.", "back":"رجع لمركز المساعدة", "saved":"✅ اللغة ديالك ولات **الدارجة**.",
                "human":"❌ اختار عضو حقيقي، ماشي بوت.", "self":"❌ ما تقدرش تبلغ على راسك.", "missing":"❌ ما قدرتش نجيب هاد العضو.",
                "report_ok":"✅ توصل البلاغ للإدارة **بشكل خاص**. شكراً على التبليغ.",
            },
            "en": {
                "report_member":"Report Member", "general":"General Report", "ticket":"Open Ticket", "help":"Get Help",
                "member_prompt":"👤 Choose the member you want to report. If they are not suggested, search their name.",
                "not_yours":"❌ This private panel belongs to another member.", "back":"Back to Support Center", "saved":"✅ Your language is now **English**.",
                "human":"❌ Choose a human member, not a bot.", "self":"❌ You cannot report yourself.", "missing":"❌ I couldn't load that member.",
                "report_ok":"✅ Your report was sent **privately** to staff. Thank you.",
            },
            "fr": {
                "report_member":"Signaler un membre", "general":"Signalement général", "ticket":"Ouvrir un Ticket", "help":"Demander de l'aide",
                "member_prompt":"👤 Choisis le membre à signaler. S'il n'apparaît pas, recherche son nom.",
                "not_yours":"❌ Ce panneau privé appartient à un autre membre.", "back":"Retour au Support Center", "saved":"✅ Ta langue est maintenant **Français**.",
                "human":"❌ Choisis un membre humain, pas un bot.", "self":"❌ Tu ne peux pas te signaler toi-même.", "missing":"❌ Impossible de charger ce membre.",
                "report_ok":"✅ Ton signalement a été envoyé **en privé** au staff. Merci.",
            },
        }
        lang = lang if lang in data else "darija"
        return data[lang].get(key, data["darija"].get(key, key))
    
    
    class SupportReportMemberModal(discord.ui.Modal):
        def __init__(self, target: discord.Member, lang: str = "darija"):
            self.target, self.lang = target, lang
            title = "🚨 Report Member" if lang == "en" else "🚨 Signaler un membre" if lang == "fr" else "🚨 بلغ على عضو"
            super().__init__(title=title)
            self.details = discord.ui.TextInput(
                label="What happened?" if lang == "en" else "Que s'est-il passé ?" if lang == "fr" else "شنو وقع؟",
                placeholder="Explain the violation..." if lang == "en" else "Explique l'infraction..." if lang == "fr" else "شرح المخالفة بالتفصيل...",
                style=discord.TextStyle.paragraph, required=True, max_length=1000,
            )
            self.context_link = discord.ui.TextInput(
                label="Message/channel link (optional)" if lang == "en" else "Lien message/salon (optionnel)" if lang == "fr" else "رابط الرسالة/القناة (اختياري)",
                placeholder="Copy Message Link if available" if lang == "en" else "Copie le lien du message si disponible" if lang == "fr" else "لسّق رابط الرسالة إلا كان متوفر",
                required=False, max_length=500,
            )
            self.add_item(self.details); self.add_item(self.context_link)
    
        async def on_submit(self, interaction: discord.Interaction):
            reporter = interaction.user
            if not isinstance(reporter, discord.Member):
                await interaction.response.send_message("❌ Error." if self.lang == "en" else "❌ Erreur." if self.lang == "fr" else "❌ وقع مشكل.", ephemeral=True); return
            ok, msg = await send_support_report(interaction.guild, reporter, target=self.target, details=str(self.details.value), context_link=str(self.context_link.value))
            shown = _support_t(self.lang, "report_ok") if ok else msg
            await upsert_ephemeral_panel(interaction, "support", content=shown, embed=_panel_language_guide_embed("support", self.lang), view=SupportPrivateView(interaction.user.id, self.lang))
    
    
    class SupportGeneralReportModal(discord.ui.Modal):
        def __init__(self, lang: str = "darija"):
            self.lang = lang
            super().__init__(title="⚠️ General Report" if lang == "en" else "⚠️ Signalement général" if lang == "fr" else "⚠️ بلاغ عام")
            self.details = discord.ui.TextInput(
                label="Report details" if lang == "en" else "Détails du signalement" if lang == "fr" else "شرح البلاغ",
                placeholder="What should staff know?" if lang == "en" else "Quel problème veux-tu signaler ?" if lang == "fr" else "شنو المشكل اللي بغيتي توصل للإدارة؟",
                style=discord.TextStyle.paragraph, required=True, max_length=1000,
            )
            self.context_link = discord.ui.TextInput(
                label="Message/channel link (optional)" if lang == "en" else "Lien message/salon (optionnel)" if lang == "fr" else "رابط الرسالة/القناة (اختياري)",
                placeholder="Copy Message Link if available" if lang == "en" else "Copie le lien du message si disponible" if lang == "fr" else "لسّق رابط الرسالة إلا كان متوفر",
                required=False, max_length=500,
            )
            self.add_item(self.details); self.add_item(self.context_link)
    
        async def on_submit(self, interaction: discord.Interaction):
            reporter = interaction.user
            if not isinstance(reporter, discord.Member):
                await interaction.response.send_message("❌ Error." if self.lang == "en" else "❌ Erreur." if self.lang == "fr" else "❌ وقع مشكل.", ephemeral=True); return
            ok, msg = await send_support_report(interaction.guild, reporter, target=None, details=str(self.details.value), context_link=str(self.context_link.value))
            shown = _support_t(self.lang, "report_ok") if ok else msg
            await upsert_ephemeral_panel(interaction, "support", content=shown, embed=_panel_language_guide_embed("support", self.lang), view=SupportPrivateView(interaction.user.id, self.lang))
    
    
    class SupportHelpTicketModal(discord.ui.Modal):
        def __init__(self, lang: str = "darija"):
            self.lang = lang
            super().__init__(title="❓ Get Help" if lang == "en" else "❓ Demander de l'aide" if lang == "fr" else "❓ طلب مساعدة")
            self.subject = discord.ui.TextInput(
                label="Subject" if lang == "en" else "Sujet" if lang == "fr" else "الموضوع",
                placeholder="Example: role / account / server issue" if lang == "en" else "Exemple : problème de rôle / compte / serveur" if lang == "fr" else "مثال: عندي مشكل فالرول / الحساب / السيرفر",
                required=True, max_length=100,
            )
            self.details = discord.ui.TextInput(
                label="Details" if lang == "en" else "Détails" if lang == "fr" else "شرح المشكل",
                placeholder="Explain the issue so staff has context..." if lang == "en" else "Explique le problème pour donner le contexte au staff..." if lang == "fr" else "شرح لينا المشكل بالتفصيل باش الإدارة تفهمو ملي تتحل التذكرة...",
                style=discord.TextStyle.paragraph, required=True, max_length=1000,
            )
            self.add_item(self.subject); self.add_item(self.details)
    
        async def on_submit(self, interaction: discord.Interaction):
            prefix = "Help" if self.lang == "en" else "Aide" if self.lang == "fr" else "مساعدة"
            await create_support_ticket(interaction, ticket_kind=f"{prefix} — {str(self.subject.value).strip()[:60]}", initial_details=str(self.details.value))
    
    
    class SupportReportMemberSelect(discord.ui.UserSelect):
        def __init__(self, user_id: int, lang: str = "darija"):
            self.user_id, self.lang = int(user_id), lang
            super().__init__(placeholder=_support_t(lang, "member_prompt")[:150], min_values=1, max_values=1, row=0)
    
        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message(_support_t(self.lang, "not_yours"), ephemeral=True); return
            selected = self.values[0]
            member = interaction.guild.get_member(selected.id)
            if not member:
                try: member = await interaction.guild.fetch_member(selected.id)
                except Exception: member = None
            if not member:
                await interaction.response.edit_message(content=_support_t(self.lang,"missing"), embed=None, view=SupportReportMemberSelectView(self.user_id,self.lang)); return
            if member.bot:
                await interaction.response.edit_message(content=_support_t(self.lang,"human"), embed=None, view=SupportReportMemberSelectView(self.user_id,self.lang)); return
            if member.id == interaction.user.id:
                await interaction.response.edit_message(content=_support_t(self.lang,"self"), embed=None, view=SupportReportMemberSelectView(self.user_id,self.lang)); return
            await interaction.response.send_modal(SupportReportMemberModal(member, self.lang))
    
    
    class SupportReportMemberSelectView(discord.ui.View):
        def __init__(self, user_id: int, lang: str = "darija"):
            super().__init__(timeout=1800)
            self.user_id,self.lang=int(user_id),lang
            self.add_item(SupportReportMemberSelect(user_id,lang))
            back=discord.ui.Button(label="↩️ "+_support_t(lang,"back"),style=discord.ButtonStyle.secondary,row=1); back.callback=self.back; self.add_item(back)
            self.add_item(GlobalPrivateLanguageSelect("support",user_id,lang,row=2))
        async def back(self,interaction):
            if interaction.user.id!=self.user_id:
                await interaction.response.send_message(_support_t(self.lang,"not_yours"),ephemeral=True); return
            await interaction.response.edit_message(content=None,embed=_panel_language_guide_embed("support",self.lang),view=SupportPrivateView(self.user_id,self.lang))
    
    
    def _panel_language_guide_embed(kind: str, lang: str) -> discord.Embed:
        lang = lang if lang in {"darija", "en", "fr"} else "darija"
        if kind == "support":
            if lang == "en":
                title = "🆘 GGMW9 Support Center — English"
                desc = "Everything here is private to you.\n\n🚨 **Report Member** — report a specific member.\n⚠️ **General Report** — report a broader issue.\n🎫 **Open Ticket** — private conversation with staff.\n❓ **Get Help** — explain a problem and create a detailed ticket."
            elif lang == "fr":
                title = "🆘 Centre d'assistance GGMW9 — Français"
                desc = "Cette interface est privée pour toi.\n\n🚨 **Signaler un membre** — signaler une personne précise.\n⚠️ **Signalement général** — signaler un problème global.\n🎫 **Ouvrir un Ticket** — discussion privée avec le staff.\n❓ **Demander de l'aide** — expliquer un problème et créer un ticket détaillé."
            else:
                title = "🆘 مركز المساعدة ديال GGMW9 — الدارجة"
                desc = "هاد الواجهة خاصة بيك بوحدك.\n\n🚨 **بلغ على عضو** — بلاغ على شخص محدد.\n⚠️ **بلاغ عام** — مشكل عام.\n🎫 **فتح تذكرة** — محادثة خاصة مع الإدارة.\n❓ **طلب مساعدة** — شرح المشكل وفتح تذكرة بالتفاصيل."
        else:
            if lang == "en":
                title = "⭐ Levels & XP — English"
                desc = "📊 **My Rank** • 👤 **Member Rank** • 🏆 **Leaderboard** • 🪜 **Roadmap**\n📝 **Bio** unlocks at Lv20 • 🗳️ **Create Poll** at Lv60 • 👑 **Legend Title** at Lv100."
            elif lang == "fr":
                title = "⭐ Niveaux & XP — Français"
                desc = "📊 **Mon rang** • 👤 **Rang d'un membre** • 🏆 **Classement** • 🪜 **Progression**\n📝 **Bio** au niv.20 • 🗳️ **Créer un sondage** au niv.60 • 👑 **Titre Legend** au niv.100."
            else:
                title = "⭐ المستويات وXP — الدارجة"
                desc = "📊 **الرتبة ديالي** • 👤 **رتبة عضو** • 🏆 **الترتيب** • 🪜 **مسار التقدم**\n📝 **النبذة الشخصية** فالمستوى 20 • 🗳️ **استفتاء** فالمستوى 60 • 👑 **اللقب الأسطوري** فالمستوى 100."
        embed = discord.Embed(title=title, description=desc, color=discord.Color.blurple())
        foot = "🌐 Language is personal. You can switch anytime." if lang=="en" else "🌐 La langue est personnelle. Tu peux la changer à tout moment." if lang=="fr" else "🌐 اللغة شخصية ديالك وتقدر تبدلها فوقاش بغيتي."
        embed.set_footer(text=foot)
        return embed
    
    
    class GlobalPrivateLanguageSelect(discord.ui.Select):
        def __init__(self, kind: str, user_id: int, lang: str = "darija", *, row: int = 1):
            self.kind,self.user_id,self.lang=kind,int(user_id),lang
            super().__init__(placeholder="🌐 اللغة / Language / Langue",options=[
                discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦",default=lang=="darija"),
                discord.SelectOption(label="English",value="en",emoji="🇬🇧",default=lang=="en"),
                discord.SelectOption(label="Français",value="fr",emoji="🇫🇷",default=lang=="fr"),
            ],min_values=1,max_values=1,row=row)
    
        async def callback(self, interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ هاد الجلسة ماشي ديالك.",ephemeral=True); return
            lang=set_panel_language(interaction.guild.id if interaction.guild else 0,interaction.user.id,self.values[0])
            if self.kind=="support": view=SupportPrivateView(self.user_id,lang)
            else: view=LevelsPrivateView(self.user_id,lang)
            await interaction.response.edit_message(content=None,embed=_panel_language_guide_embed(self.kind,lang),view=view)
    
    
    class GlobalPanelLanguageSelect(discord.ui.Select):
        """Public selector that opens a fresh private localized panel.
    
        No ephemeral message is cached, so Dismiss is always safe: selecting a
        language again from the public Darija panel creates a new clean session.
        """
        def __init__(self, kind: str, lang: str = "darija", *, row: int = 1):
            self.kind = kind
            self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
            super().__init__(
                placeholder="🌐 اللغة / Language / Langue",
                options=[
                    discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", default=self.lang == "darija"),
                    discord.SelectOption(label="English", value="en", emoji="🇬🇧", default=self.lang == "en"),
                    discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", default=self.lang == "fr"),
                ],
                min_values=1,
                max_values=1,
                custom_id=f"ggmw9:{kind}:language",
                row=row,
            )
    
        async def callback(self, interaction: discord.Interaction):
            lang = set_panel_language(
                interaction.guild.id if interaction.guild else 0,
                interaction.user.id,
                self.values[0],
            )
            if self.kind == "support":
                embed = build_support_center_embed(lang)
                view = SupportPrivateView(interaction.user.id, lang)
            elif self.kind == "levels":
                embed = build_levels_info_embed(interaction.guild, lang)
                view = LevelsPrivateView(interaction.user.id, lang)
            else:
                await interaction.response.send_message("❌ Unknown panel.", ephemeral=True)
                return
    
            # Fresh response on EVERY public selection. No cached webhook/message reference.
            await interaction.response.send_message(
                content=None,
                embed=embed,
                view=view,
                ephemeral=True,
            )
    
    
    class SupportPrivateView(discord.ui.View):
        def __init__(self, user_id: int, lang: str = "darija"):
            super().__init__(timeout=1800)
            self.user_id,self.lang=int(user_id),lang
            items=[
                ("🚨 "+_support_t(lang,"report_member"),discord.ButtonStyle.danger,self.report_member),
                ("⚠️ "+_support_t(lang,"general"),discord.ButtonStyle.secondary,self.general_report),
                ("🎫 "+_support_t(lang,"ticket"),discord.ButtonStyle.success,self.open_ticket),
                ("❓ "+_support_t(lang,"help"),discord.ButtonStyle.primary,self.help_ticket),
            ]
            for label,style,cb in items:
                b=discord.ui.Button(label=label[:80],style=style,row=0); b.callback=cb; self.add_item(b)
            self.add_item(GlobalPrivateLanguageSelect("support",self.user_id,lang,row=1))
        async def _ok(self,interaction):
            if interaction.user.id!=self.user_id:
                await interaction.response.send_message(_support_t(self.lang,"not_yours"),ephemeral=True); return False
            return True
        async def report_member(self,interaction):
            if not await self._ok(interaction): return
            await interaction.response.edit_message(content=_support_t(self.lang,"member_prompt"),embed=None,view=SupportReportMemberSelectView(self.user_id,self.lang))
        async def general_report(self,interaction):
            if await self._ok(interaction): await interaction.response.send_modal(SupportGeneralReportModal(self.lang))
        async def open_ticket(self,interaction):
            if not await self._ok(interaction): return
            kind="General Support" if self.lang=="en" else "Support général" if self.lang=="fr" else "دعم عام"
            await create_support_ticket(interaction,ticket_kind=kind)
        async def help_ticket(self,interaction):
            if await self._ok(interaction): await interaction.response.send_modal(SupportHelpTicketModal(self.lang))
    
    
    class SupportCenterView(discord.ui.View):
        """Persistent public Support Center. Public message stays Darija; language opens a private session."""
        def __init__(self, lang: str = "darija"):
            super().__init__(timeout=None)
            self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
    
            items = [
                ("ggmw9:support:report_member", "🚨", _support_t(self.lang, "report_member"), discord.ButtonStyle.danger, self.report_member),
                ("ggmw9:support:general_report", "⚠️", _support_t(self.lang, "general"), discord.ButtonStyle.secondary, self.general_report),
                ("ggmw9:support:ticket", "🎫", _support_t(self.lang, "ticket"), discord.ButtonStyle.success, self.open_ticket),
                ("ggmw9:support:help", "❓", _support_t(self.lang, "help"), discord.ButtonStyle.primary, self.help_ticket),
            ]
            for custom_id, emoji, label, style, cb in items:
                b = discord.ui.Button(label=label[:80], emoji=emoji, style=style, custom_id=custom_id, row=0)
                b.callback = cb
                self.add_item(b)
            self.add_item(GlobalPanelLanguageSelect("support", self.lang, row=1))
    
        def _sync_user_lang(self, interaction: discord.Interaction) -> str:
            return get_panel_language(interaction.guild.id if interaction.guild else 0, interaction.user.id)
    
        async def report_member(self, interaction: discord.Interaction):
            lang = self._sync_user_lang(interaction)
            await upsert_ephemeral_panel(
                interaction, "support",
                content=_support_t(lang, "member_prompt"), embed=None,
                view=SupportReportMemberSelectView(interaction.user.id, lang),
            )
    
        async def general_report(self, interaction: discord.Interaction):
            lang = self._sync_user_lang(interaction)
            await interaction.response.send_modal(SupportGeneralReportModal(lang))
    
        async def open_ticket(self, interaction: discord.Interaction):
            lang = self._sync_user_lang(interaction)
            kind = "General Support" if lang == "en" else "Support général" if lang == "fr" else "دعم عام"
            await create_support_ticket(interaction, ticket_kind=kind)
    
        async def help_ticket(self, interaction: discord.Interaction):
            lang = self._sync_user_lang(interaction)
            await interaction.response.send_modal(SupportHelpTicketModal(lang))
    
    
    class TicketPanelView(discord.ui.View):
        """Legacy compatibility فقط. الواجهة العامة الجديدة هي SupportCenterView."""
    
        def __init__(self):
            super().__init__(timeout=None)
    
        @discord.ui.button(
            label="🎫 دير Ticket",
            style=discord.ButtonStyle.success,
            custom_id="open_ticket_button",
        )
        async def open_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await create_support_ticket(interaction, ticket_kind="دعم عام")
    
    
    async def cleanup_legacy_ticket_panel(guild: discord.Guild):
        """كيمسح غير Panel القديمة ديال البوت، ما كيمسش channel ولا رسائل الناس."""
        if not LEGACY_TICKETS_PANEL_CHANNEL_ID:
            return
        if LEGACY_TICKETS_PANEL_CHANNEL_ID == SUPPORT_CENTER_CHANNEL_ID:
            return
    
        channel = guild.get_channel(LEGACY_TICKETS_PANEL_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            return
    
        try:
            async for message in channel.history(limit=30):
                if message.author != bot.user:
                    continue
                title = ""
                if message.embeds and message.embeds[0].title:
                    title = message.embeds[0].title
                if "الدعم / Support" in title or "Ticket" in title:
                    try:
                        await message.delete()
                    except (discord.Forbidden, discord.HTTPException):
                        pass
        except discord.Forbidden:
            pass
    
    
    def build_support_center_embed(lang: str = "darija") -> discord.Embed:
        lang = lang if lang in {"darija", "en", "fr"} else "darija"
        if lang == "en":
            title = "🆘 GGMW9 Support Center"
            desc = (
                "All support and reporting tools are organized here.\n\n"
                "🚨 **Report Member** — report a specific member and explain what happened.\n"
                "⚠️ **General Report** — report an issue not tied to one member.\n"
                "🎫 **Open Ticket** — private conversation with staff.\n"
                "❓ **Get Help** — describe your issue and create a detailed ticket.\n\n"
                "🔒 Reports go directly to staff and are not posted publicly.\n"
                "💬 Tickets are private between you and staff.\n"
                "📎 For evidence, use **Copy Message Link** or attach images inside the ticket.\n\n"
                "🌐 Choose a language below to open your **private translated panel**. If you Dismiss it, choose a language here again anytime."
            )
            field_name = "💡 Which option should I use?"
            field_value = "**Report** for cases staff can review quickly.\n**Ticket** for questions, appeals, private issues, or anything that needs a conversation."
            footer = f"{SERVER_NAME} | Support • Reports • Tickets • English"
        elif lang == "fr":
            title = "🆘 Centre d'assistance GGMW9"
            desc = (
                "Tous les outils d'assistance et de signalement sont réunis ici.\n\n"
                "🚨 **Signaler un membre** — signaler une personne précise et expliquer le problème.\n"
                "⚠️ **Signalement général** — signaler un problème global.\n"
                "🎫 **Ouvrir un Ticket** — discussion privée avec le staff.\n"
                "❓ **Demander de l'aide** — expliquer ton problème et créer un ticket détaillé.\n\n"
                "🔒 Les signalements vont directement au staff et ne sont pas publics.\n"
                "💬 Les tickets sont privés entre toi et le staff.\n"
                "📎 Pour une preuve, utilise **Copier le lien du message** ou joins des images dans le ticket.\n\n"
                "🌐 Choisis une langue ci-dessous pour ouvrir ton **panneau privé traduit**. Si tu le fermes, choisis simplement une langue ici à nouveau."
            )
            field_name = "💡 Que choisir ?"
            field_value = "**Signalement** pour les cas que le staff peut vérifier rapidement.\n**Ticket** pour les questions, appels, problèmes privés ou les cas nécessitant une discussion."
            footer = f"{SERVER_NAME} | Support • Reports • Tickets • Français"
        else:
            title = "🆘 GGMW9 Support Center"
            desc = (
                "كلشي ديال الدعم والتبليغ مجموع هنا باش السيرفر يبقى منظم.\n\n"
                "🚨 **بلغ على عضو** — مخالفة مرتبطة بشخص؛ كتختارو وكتشرح شنو وقع.\n"
                "⚠️ **بلاغ عام** — مشكل ما مرتبطش بعضو محدد.\n"
                "🎫 **فتح Ticket** — إلا خاصك محادثة خاصة مع الإدارة.\n"
                "❓ **طلب مساعدة** — كتب الموضوع والمشكل، والبوت كيفتح Ticket بالتفاصيل.\n\n"
                "🔒 **البلاغات ما كيبانوش للناس:** كيمشيو مباشرة لقناة الإدارة.\n"
                "💬 **Tickets خاصة:** غير نتا والإدارة كتشوفوها.\n"
                "📎 إلا عندك دليل، دير **Copy Message Link** وحطو فالبلاغ، أو زيد الصور داخل Ticket.\n\n"
                "🌐 اختار اللغة من اللائحة لتحت باش تحل **نسختك الخاصة**. إلا درتي Dismiss، رجع اختار أي لغة من هنا وغادي تتحل من جديد."
            )
            field_name = "💡 شنو نختار؟"
            field_value = "**Report** للحالات اللي الإدارة تقدر تراجعها بلا نقاش طويل.\n**Ticket** للأسئلة، المشاكل الخاصة، Appeals، أو الحالات اللي خاص فيها حوار."
            footer = f"{SERVER_NAME} | Support • Reports • Tickets • Darija"
        e = discord.Embed(title=title, description=desc, color=discord.Color.blurple(), timestamp=datetime.now())
        e.add_field(name=field_name, value=field_value, inline=False)
        e.set_footer(text=footer)
        return e
    
    
    async def setup_support_center(guild: discord.Guild):
        if not SUPPORT_CENTER_CHANNEL_ID:
            return
        channel = guild.get_channel(SUPPORT_CENTER_CHANNEL_ID)
        if not isinstance(channel, discord.TextChannel):
            print(f"[SUPPORT] ❌ Support Center channel {SUPPORT_CENTER_CHANNEL_ID} ما لقيتهاش.")
            return
    
        await cleanup_legacy_ticket_panel(guild)
        embed = build_support_center_embed("darija")
        message = await upsert_fixed_panel(
            bot,
            channel,
            key="support_center",
            matches=lambda message: (
                message.author == bot.user
                and bool(message.embeds)
                and any(
                    marker in (message.embeds[0].title or "")
                    for marker in ("Support Center", "Centre d'assistance")
                )
            ),
            content=None,
            embed=embed,
            view=SupportCenterView("darija"),
            history_limit=None,
        )
        if message is None:
            print("[SUPPORT] ❌ ما قدرتش نصاوب/نحدث Support Center دابا.")
    
    
    # Compatibility wrapper — ما كيتستعملش كواجهة مستقلة.
    async def setup_tickets_panel(guild: discord.Guild):
        await setup_support_center(guild)
    
    
    # Hidden fallback فقط؛ ما بقاش Slash Command.
    @bot.command(name="setuptickets", hidden=True)
    @owner_only()
    async def setuptickets_cmd(ctx):
        await setup_support_center(ctx.guild)
        try:
            await ctx.author.send(f"✅ Support Center تحدثات فـ <#{SUPPORT_CENTER_CHANNEL_ID}>.")
        except discord.HTTPException:
            pass
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
