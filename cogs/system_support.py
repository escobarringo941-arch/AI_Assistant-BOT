# -*- coding: utf-8 -*-
"""Support center, tickets, applications, and suggestions.

Extracted mechanically from the legacy ai_bot.py.  Runtime state is attached
to bot_core's shared namespace so existing cross-system references keep the
same object identity and startup order.
"""

import bot_core as core

core.attach_namespace(globals())


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
    existing = None
    try:
        async for message in channel.history(limit=30):
            if message.author != bot.user or not message.embeds:
                continue
            title = message.embeds[0].title or ""
            if "Support Center" in title or "Centre d'assistance" in title:
                existing = message
                break
    except discord.Forbidden:
        return

    embed = build_support_center_embed("darija")
    try:
        if existing:
            await existing.edit(content=None, embed=embed, view=SupportCenterView("darija"))
        else:
            await channel.send(embed=embed, view=SupportCenterView("darija"))
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[SUPPORT] ❌ ما قدرتش نصاوب/نحدث Support Center: {e}")


# Compatibility wrapper — ما كيتستعملش كواجهة مستقلة.
async def setup_tickets_panel(guild: discord.Guild):
    await setup_support_center(guild)


# Hidden fallback فقط؛ ما بقاش Slash Command.


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
    matches=[]
    try:
        async for message in channel.history(limit=30):
            if message.author==bot.user and message.embeds and ("قدم لفريق الإدارة" in (message.embeds[0].title or "") or "Staff Applications" in (message.embeds[0].title or "") or "Candidatures Staff" in (message.embeds[0].title or "")):
                matches.append(message)
    except discord.Forbidden: return
    embed=_application_home_embed("darija"); view=ApplicationPanelView("darija")
    try:
        if matches:
            keep=matches[0]; await keep.edit(embed=embed,view=view)
            for old in matches[1:]:
                try: await old.delete()
                except (discord.Forbidden,discord.NotFound,discord.HTTPException): pass
        else: await channel.send(embed=embed,view=view)
    except (discord.Forbidden,discord.HTTPException) as e: print(f"[APPLICATIONS] panel update failed: {e}")






# ═══════════════════════════════════════════════════════
# ║   Phase 7 — نظام Suggestions (اقتراحات الأعضاء)         ║
# ═══════════════════════════════════════════════════════

class SuggestionReviewView(discord.ui.View):
    """أزرار قبول/رفض الاقتراح، بنفس المنطق ديال ApplicationReviewView. Persistent."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ مقبول", style=discord.ButtonStyle.success, custom_id="suggestion_accept_button")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, accepted=True)

    @discord.ui.button(label="❌ مرفوض", style=discord.ButtonStyle.danger, custom_id="suggestion_reject_button")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._decide(interaction, accepted=False)

    async def _decide(self, interaction: discord.Interaction, accepted: bool):
        member = interaction.user
        if not isinstance(member, discord.Member) or not _is_staff_reviewer(member):
            await interaction.response.send_message("❌ هاد الزر خاص غير بالإدارة.", ephemeral=True)
            return

        sug_id, record = find_suggestion_by_message_id(interaction.message.id)
        if not record:
            await interaction.response.send_message("❌ ماكاينش هاد الاقتراح فالسجل ديالنا.", ephemeral=True)
            return
        if record.get("status") != "pending":
            await interaction.response.send_message("⚠️ هاد الاقتراح تدار فيه قرار من قبل.", ephemeral=True)
            return

        record["status"] = "accepted" if accepted else "rejected"
        record["decided_by"] = member.id
        record["decided_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_suggestions()

        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green() if accepted else discord.Color.red()
        embed.set_footer(
            text=f"{SERVER_NAME} | Suggestion #{sug_id} | "
                 f"{'✅ Accepted' if accepted else '❌ Rejected'} من طرف {member.display_name}"
        )
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

        guild = interaction.guild
        author = guild.get_member(record["author_id"]) if guild else None
        if author:
            try:
                if accepted:
                    await author.send(f"🎉 الاقتراح ديالك (#{sug_id}) تقبل من طرف الإدارة فـ **{SERVER_NAME}**!")
                else:
                    await author.send(f"❌ الاقتراح ديالك (#{sug_id}) تُرفض هاد المرة فـ **{SERVER_NAME}**.")
            except Exception:
                pass


def _suggestion_t(lang: str, key: str, **fmt) -> str:
    data = {
        "darija": {
            "title": "💡 اقتراحات GGMW9",
            "desc": (
                "عندك فكرة تقدر تحسن السيرفر؟ صيفطها من هنا مباشرة.\n\n"
                "📌 الاقتراح ديالك غادي يبان **فنفس قناة الاقتراحات** تحت هاد البانل.\n"
                "👍👎 الأعضاء يقدرو يصوتو عليه، والإدارة كتراجعو وتقبلو ولا ترفضو."
            ),
            "create": "دير اقتراح",
            "saved": "✅ تحلات ليك واجهة الاقتراحات بالدارجة.",
            "modal_title": "💡 اقتراح جديد",
            "idea_label": "شرح الفكرة",
            "idea_placeholder": "شرح الفكرة بوضوح: شنو بغيتي يتزاد أو يتبدل، وعلاش غادي يفيد السيرفر؟",
            "sent": "✅ الاقتراح ديالك **#{id}** تبعث وظهر فـ {channel}.",
            "failed": "❌ ما قدرناش نصيفطو الاقتراح دابا. جرب من بعد أو بلغ الإدارة.",
            "not_yours": "❌ هاد الجلسة ماشي ديالك.",
        },
        "en": {
            "title": "💡 GGMW9 Suggestions",
            "desc": (
                "Have an idea that could improve the server? Submit it directly here.\n\n"
                "📌 Your suggestion will appear **in this Suggestions channel** below the main panel.\n"
                "👍👎 Members can vote on it, and staff can review and accept or reject it."
            ),
            "create": "Submit Suggestion",
            "saved": "✅ Your Suggestions panel is now in English.",
            "modal_title": "💡 New Suggestion",
            "idea_label": "Describe your idea",
            "idea_placeholder": "Explain clearly what should be added or changed and why it would help the server.",
            "sent": "✅ Suggestion **#{id}** was submitted and posted in {channel}.",
            "failed": "❌ We couldn't submit the suggestion right now. Try again later or contact staff.",
            "not_yours": "❌ This session belongs to another member.",
        },
        "fr": {
            "title": "💡 Suggestions GGMW9",
            "desc": (
                "Tu as une idée pour améliorer le serveur ? Envoie-la directement ici.\n\n"
                "📌 Ta suggestion apparaîtra **dans ce salon Suggestions** sous le panneau principal.\n"
                "👍👎 Les membres pourront voter, puis le staff pourra l'accepter ou la refuser."
            ),
            "create": "Faire une suggestion",
            "saved": "✅ Ton panneau Suggestions est maintenant en français.",
            "modal_title": "💡 Nouvelle suggestion",
            "idea_label": "Décris ton idée",
            "idea_placeholder": "Explique clairement ce qu'il faudrait ajouter ou modifier et pourquoi ce serait utile au serveur.",
            "sent": "✅ La suggestion **#{id}** a été envoyée et publiée dans {channel}.",
            "failed": "❌ Impossible d'envoyer la suggestion pour le moment. Réessaie plus tard ou contacte le staff.",
            "not_yours": "❌ Cette session appartient à un autre membre.",
        },
    }
    lang = lang if lang in data else "darija"
    value = data[lang].get(key, data["darija"].get(key, key))
    return value.format(**fmt) if fmt else value


def _suggestions_home_embed(lang: str = "darija") -> discord.Embed:
    lang = lang if lang in {"darija", "en", "fr"} else "darija"
    embed = discord.Embed(
        title=_suggestion_t(lang, "title"),
        description=_suggestion_t(lang, "desc"),
        color=discord.Color.blurple(),
        timestamp=datetime.now(),
    )

    if lang == "en":
        embed.add_field(
            name="✅ Good suggestions",
            value="• New bot feature\n• New channel/role\n• Event or competition\n• Server organization improvement\n• Any useful server idea",
            inline=False,
        )
        embed.add_field(
            name="🚫 Use Support instead for",
            value="• Bugs/technical problems\n• Reports about a member\n• Staff applications",
            inline=False,
        )
        embed.set_footer(text=f"{SERVER_NAME} | Suggestions • English")
    elif lang == "fr":
        embed.add_field(
            name="✅ Bonnes suggestions",
            value="• Nouvelle fonction du bot\n• Nouveau salon/rôle\n• Événement ou compétition\n• Amélioration de l'organisation\n• Toute idée utile au serveur",
            inline=False,
        )
        embed.add_field(
            name="🚫 Utilise plutôt le Support pour",
            value="• Bugs/problèmes techniques\n• Signalement d'un membre\n• Candidatures Staff",
            inline=False,
        )
        embed.set_footer(text=f"{SERVER_NAME} | Suggestions • Français")
    else:
        embed.add_field(
            name="✅ شنو تقدر تقترح",
            value="• ميزة جديدة فالبوت\n• قناة ولا رول جديد\n• فعالية ولا مسابقة\n• تحسين فتنظيم السيرفر\n• أي فكرة مفيدة للسيرفر",
            inline=False,
        )
        embed.add_field(
            name="🚫 شنو ديرو فمركز المساعدة بلاصة الاقتراحات",
            value="• بوغ ولا مشكل تقني\n• بلاغ على عضو\n• طلب الانضمام للإدارة",
            inline=False,
        )
        embed.set_footer(text=f"{SERVER_NAME} | نظام الاقتراحات • الدارجة")
    return embed


async def _create_suggestion_from_panel(
    guild: discord.Guild,
    author: discord.abc.User,
    idea: str,
) -> tuple:
    """Single source of truth for Panel and /suggest fallback."""
    if not SUGGESTIONS_CHANNEL_ID:
        return False, None, None, "SUGGESTIONS_CHANNEL_ID missing"

    channel = bot.get_channel(SUGGESTIONS_CHANNEL_ID)
    if not channel:
        return False, None, None, "Suggestions channel not found"

    sug_id = int(suggestions_db.get("next_id", 1))
    embed = discord.Embed(
        title=f"💡 اقتراح #{sug_id}",
        description=str(idea).strip()[:1000],
        color=discord.Color.blurple(),
        timestamp=datetime.now(),
    )
    embed.set_author(name=str(author), icon_url=author.display_avatar.url)
    embed.set_footer(text=f"{SERVER_NAME} | اقتراح #{sug_id} | قيد المراجعة")

    try:
        msg = await channel.send(embed=embed, view=SuggestionReviewView())
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
    except Exception as exc:
        print(f"[SUGGESTIONS] submit failed: {type(exc).__name__}: {exc}")
        return False, None, channel, str(exc)

    suggestions_db["next_id"] = sug_id + 1
    suggestions_db.setdefault("suggestions", {})[str(sug_id)] = {
        "author_id": int(author.id),
        "text": str(idea).strip(),
        "status": "pending",
        "message_id": int(msg.id),
        "channel_id": int(channel.id),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "decided_by": None,
        "decided_at": None,
    }
    save_suggestions()
    return True, sug_id, channel, None


class SuggestionModal(discord.ui.Modal):
    def __init__(self, lang: str = "darija"):
        self.lang = lang if lang in {"darija", "en", "fr"} else "darija"
        super().__init__(title=_suggestion_t(self.lang, "modal_title"))
        self.idea = discord.ui.TextInput(
            label=_suggestion_t(self.lang, "idea_label"),
            placeholder=_suggestion_t(self.lang, "idea_placeholder"),
            style=discord.TextStyle.paragraph,
            min_length=10,
            max_length=1000,
            required=True,
        )
        self.add_item(self.idea)

    async def on_submit(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message(
                _suggestion_t(self.lang, "failed"),
                ephemeral=True,
            )
            return

        ok, sug_id, channel, _ = await _create_suggestion_from_panel(
            interaction.guild,
            interaction.user,
            self.idea.value,
        )
        if not ok:
            await interaction.response.send_message(
                _suggestion_t(self.lang, "failed"),
                ephemeral=True,
            )
            return

        await interaction.response.send_message(
            _suggestion_t(
                self.lang,
                "sent",
                id=sug_id,
                channel=channel.mention,
            ),
            ephemeral=True,
        )


class SuggestionsPrivateLanguageSelect(discord.ui.Select):
    def __init__(self, user_id: int, lang: str = "darija"):
        self.user_id = int(user_id)
        self.lang = lang
        super().__init__(
            placeholder="🌐 اللغة / Language / Langue",
            options=[
                discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", default=lang == "darija"),
                discord.SelectOption(label="English", value="en", emoji="🇬🇧", default=lang == "en"),
                discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", default=lang == "fr"),
            ],
            min_values=1,
            max_values=1,
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                _suggestion_t(self.lang, "not_yours"),
                ephemeral=True,
            )
            return

        lang = set_panel_language(
            interaction.guild.id,
            interaction.user.id,
            self.values[0],
        )
        await interaction.response.edit_message(
            content=_suggestion_t(lang, "saved"),
            embed=_suggestions_home_embed(lang),
            view=SuggestionsPrivateView(self.user_id, lang),
        )


class SuggestionsPrivateView(discord.ui.View):
    def __init__(self, user_id: int, lang: str = "darija"):
        super().__init__(timeout=1800)
        self.user_id = int(user_id)
        self.lang = lang if lang in {"darija", "en", "fr"} else "darija"

        create = discord.ui.Button(
            label="💡 " + _suggestion_t(self.lang, "create"),
            style=discord.ButtonStyle.success,
            row=0,
        )
        create.callback = self.create_suggestion
        self.add_item(create)
        self.add_item(SuggestionsPrivateLanguageSelect(self.user_id, self.lang))

    async def create_suggestion(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                _suggestion_t(self.lang, "not_yours"),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(SuggestionModal(self.lang))


class SuggestionsPublicLanguageSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="🌐 اللغة / Language / Langue",
            options=[
                discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦"),
                discord.SelectOption(label="English", value="en", emoji="🇬🇧"),
                discord.SelectOption(label="Français", value="fr", emoji="🇫🇷"),
            ],
            min_values=1,
            max_values=1,
            custom_id="ggmw9:suggestions:language",
            row=1,
        )

    async def callback(self, interaction: discord.Interaction):
        lang = set_panel_language(
            interaction.guild.id,
            interaction.user.id,
            self.values[0],
        )
        # Always a fresh private session. Dismiss is safe; the public panel
        # can open another session immediately afterwards.
        await interaction.response.send_message(
            content=_suggestion_t(lang, "saved"),
            embed=_suggestions_home_embed(lang),
            view=SuggestionsPrivateView(interaction.user.id, lang),
            ephemeral=True,
        )


class SuggestionsPanelView(discord.ui.View):
    """Persistent public Darija Suggestions panel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="💡 دير اقتراح",
        style=discord.ButtonStyle.success,
        custom_id="ggmw9:suggestions:create",
        row=0,
    )
    async def create_suggestion(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        await interaction.response.send_modal(SuggestionModal("darija"))

    def add_language_selector(self):
        if not any(isinstance(x, SuggestionsPublicLanguageSelect) for x in self.children):
            self.add_item(SuggestionsPublicLanguageSelect())
        return self



# ═══════════════════════════════════════════════════════
# ║   🔎 /aicheck — تشيك مباشر على الموديل والرصيد ديال OpenRouter   ║
# ═══════════════════════════════════════════════════════

async def test_single_model(model: str) -> tuple:
    """كيجرب موديل واحد بالضبط (بلا fallback) بسؤال صغير بزاف.
    كيرجع (نجح?, وصف, الوقت بالثواني)."""
    if not OPENROUTER_API_KEY:
        return False, "ماكاينش OPENROUTER_API_KEY فـ الـ environment", 0.0

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://discord.com",
        "X-Title": "AI Assistant BOT",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
        "max_tokens": 20,
        "temperature": 0,
    }
    if AI_DISABLE_REASONING:
        payload["reasoning"] = {"enabled": False, "exclude": True}

    start = asyncio.get_event_loop().time()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=25)) as session:
            async with session.post(OPENROUTER_URL, headers=headers, json=payload) as resp:
                took = asyncio.get_event_loop().time() - start
                body = await resp.text()
                if resp.status != 200:
                    short = body[:120].replace("\n", " ")
                    return False, f"HTTP {resp.status} — {short}", took
                data = json.loads(body)
                msg = data.get("choices", [{}])[0].get("message", {}) or {}
                content = (msg.get("content") or msg.get("reasoning") or "").strip()
                if not content:
                    return False, "رجع رد فارغ (reasoning صرف كاع الـ tokens)", took
                return True, content[:60], took
    except asyncio.TimeoutError:
        return False, "Timeout (تعدا 25 ثانية)", 25.0
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"[:120], asyncio.get_event_loop().time() - start


async def get_openrouter_credits() -> Optional[dict]:
    """كيجيب الرصيد الحقيقي من OpenRouter."""
    if not OPENROUTER_API_KEY:
        return None
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}"}
    data = await fetch_json("https://openrouter.ai/api/v1/credits", headers=headers)
    return (data or {}).get("data")






async def setup_suggestions_info(guild: discord.Guild):
    """Keep ONE public Darija Suggestions panel; language sessions are private."""
    if not SUGGESTIONS_CHANNEL_ID:
        return False
    channel = bot.get_channel(SUGGESTIONS_CHANNEL_ID)
    if not channel:
        return False

    embed = _suggestions_home_embed("darija")
    view = SuggestionsPanelView().add_language_selector()

    matches = []
    try:
        async for message in channel.history(limit=40):
            if (
                message.author == bot.user
                and message.embeds
                and (
                    "الاقتراحات" in (message.embeds[0].title or "")
                    or "اقتراحات GGMW9" in (message.embeds[0].title or "")
                    or "GGMW9 Suggestions" in (message.embeds[0].title or "")
                    or "Suggestions GGMW9" in (message.embeds[0].title or "")
                )
            ):
                matches.append(message)
    except discord.Forbidden:
        return False

    try:
        if matches:
            keep = matches[0]
            await keep.edit(content=None, embed=embed, view=view)
            for extra in matches[1:]:
                # Only clean duplicate panel/info messages, never suggestion posts.
                title = extra.embeds[0].title if extra.embeds else ""
                if title and "اقتراح #" not in title:
                    try:
                        await extra.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
        else:
            await channel.send(embed=embed, view=view)
        return True
    except (discord.Forbidden, discord.HTTPException) as exc:
        print(f"[SUGGESTIONS] panel update failed: {exc}")
        return False


class SupportCog(commands.Cog):
    """Discord command/event registration for this subsystem."""

    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance

    @commands.command(name="setuptickets", hidden=True)
    @owner_only()
    async def setuptickets_cmd(self, ctx):
        await setup_support_center(ctx.guild)
        try:
            await ctx.author.send(f"✅ Support Center تحدثات فـ <#{SUPPORT_CENTER_CHANNEL_ID}>.")
        except discord.HTTPException:
            pass

    @commands.hybrid_command(name="setupapplications")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setupapplications_cmd(self, ctx):
        """كيصاوب/يعاود يصاوب رسالة اللوحة ديال Applications فـ APPLICATIONS_PANEL_CHANNEL_ID (Admin)"""
        if not APPLICATIONS_PANEL_CHANNEL_ID:
            await ctx.send("❌ حط `APPLICATIONS_PANEL_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
            return
        if not APPLICATIONS_REVIEW_CHANNEL_ID:
            await ctx.send("⚠️ `APPLICATIONS_REVIEW_CHANNEL_ID` فارغة — غايستعمل MOD_LOGS_CHANNEL_ID بدلها.", delete_after=10)
        await setup_applications_panel(ctx.guild)
        await ctx.send("✅ رسالة اللوحة ديال Applications تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)

    @commands.hybrid_command(name="applications")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def applications_cmd(self, ctx):
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

    @commands.hybrid_command(name="aicheck", description="تشيك واش الموديل ديال الـ AI والرصيد خدامين مزيان")
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def aicheck_cmd(self, ctx):
        """كيدير تشيك حقيقي (ماشي نظري): كيبعث طلب فعلي للموديل المدفوع، كيقيس الوقت،
        كيجيب الرصيد اللي باقي، وكيجرب الترجمة للدارجة."""
        msg = await ctx.send("🔎 كنشيكي على OpenRouter... صبر شوية (تقريبا 30 ثانية).")

        lines = []

        # 1) الرصيد
        credits = await get_openrouter_credits()
        if credits:
            total = float(credits.get("total_credits", 0) or 0)
            used = float(credits.get("total_usage", 0) or 0)
            left = total - used
            lines.append(
                f"💳 **الرصيد**: خلصتي `${total:.2f}` — صرفتي `${used:.4f}` — "
                f"باقي ليك **`${left:.4f}`**"
            )
            # DeepSeek V4 Flash: $0.0983/M in, $0.1966/M out
            approx_msgs = int(left / 0.0004) if left > 0 else 0
            lines.append(f"   └ يعني تقريبا **{approx_msgs:,}** رد آخر بهاد الموديل 🎯")
        else:
            lines.append("💳 **الرصيد**: ما قدرتش نجيبو (تأكد من `OPENROUTER_API_KEY`)")

        # 2) الموديل الأساسي المدفوع
        ok, detail, took = await test_single_model(AI_MODEL)
        icon = "✅" if ok else "❌"
        lines.append(f"\n{icon} **الموديل الأساسي** `{AI_MODEL}`")
        lines.append(f"   └ {'خدام مزيان' if ok else 'ماخدامش'} — `{took:.2f}s` — {detail}")

        # 3) موديلات الاحتياط
        lines.append("\n🔁 **موديلات الاحتياط (المجانية):**")
        for fb in AI_MODEL_FALLBACKS:
            fok, fdetail, ftook = await test_single_model(fb)
            lines.append(f"   {'✅' if fok else '❌'} `{fb}` — `{ftook:.2f}s`" + ("" if fok else f" — {fdetail}"))


        embed = discord.Embed(
            title="🔎 تشيك على نظام الـ AI",
            description="\n".join(lines)[:4000],
            color=discord.Color.green() if ok else discord.Color.red(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"{SERVER_NAME} | AI Health Check")
        try:
            await msg.edit(content=None, embed=embed)
        except discord.HTTPException:
            await ctx.send(embed=embed)

    @commands.hybrid_command(name="suggest")
    async def suggest_cmd(self, ctx, *, idea: str):
        """Compatibility fallback. The main Suggestions flow is now the panel."""
        if not ctx.guild:
            return
        ok, sug_id, channel, error = await _create_suggestion_from_panel(
            ctx.guild,
            ctx.author,
            idea,
        )
        if not ok:
            await ctx.send(
                "❌ ما قدرناش نصيفطو الاقتراح دابا. جرب من بعد أو بلغ الإدارة.",
                delete_after=8,
            )
            return

        if channel.id != ctx.channel.id:
            await ctx.send(
                f"✅ تم بعث الاقتراح ديالك (#{sug_id}) فـ {channel.mention}!",
                delete_after=8,
            )
        else:
            await ctx.send(
                f"✅ تم بعث الاقتراح ديالك (#{sug_id})!",
                delete_after=5,
            )

    @commands.hybrid_command(name="setupsuggestions")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setupsuggestions_cmd(self, ctx):
        """كيصاوب/يعاود يصاوب رسالة الشرح ديال channel الاقتراحات فـ SUGGESTIONS_CHANNEL_ID (Admin)"""
        if not SUGGESTIONS_CHANNEL_ID:
            await ctx.send("❌ حط `SUGGESTIONS_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
            return
        await setup_suggestions_info(ctx.guild)
        await ctx.send("✅ رسالة الشرح ديال الاقتراحات تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)

    @commands.hybrid_command(name="closeticket")
    async def closeticket_cmd(self, ctx):
        """كيسد ticket بأمر (بديل للزر) — خدام غير جوة channel ديال ticket"""
        record = tickets_db.get("open", {}).get(str(ctx.channel.id))
        if not record:
            await ctx.send("❌ هاد الأمر خدام غير جوة channel ديال ticket.", delete_after=6)
            return
        is_opener = ctx.author.id == record.get("opener_id")
        if not (is_opener or _is_ticket_staff(ctx.author)):
            await ctx.send("❌ غير صاحب الـ ticket ولا الإدارة يقدرو يسدوه.", delete_after=6)
            return

        await ctx.send("🔒 غادي نسدو هاد الـ ticket من بعد 5 ثواني...")
        ticket_id = record["id"]
        channel = ctx.channel

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
        except Exception:
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
            embed.add_field(name="🔒 سداه", value=ctx.author.mention, inline=False)
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
            await channel.delete(reason=f"Ticket #{ticket_id} تسد من طرف {ctx.author}")
        except Exception as e:
            print(f"[TICKETS] خطأ فـ حذف الـ channel: {e}")


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(SupportCog(bot_instance))
