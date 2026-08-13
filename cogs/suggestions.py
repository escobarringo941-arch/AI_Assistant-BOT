# -*- coding: utf-8 -*-
"""Unchanged ordered source component: suggestions."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║   Phase 7 — نظام Suggestions (اقتراحات الأعضاء)         ║
    # ═══════════════════════════════════════════════════════
    
    class SuggestionRejectReasonModal(discord.ui.Modal):
        """كيطلب سبب مختصر قبل ما يتسجل رفض الاقتراح."""

        def __init__(self, review_view, message):
            super().__init__(title="❌ سبب رفض الاقتراح")
            self.review_view = review_view
            self.message = message
            self.reason = discord.ui.TextInput(
                label="سبب الرفض",
                placeholder="كتب سبب مختصر وواضح لصاحب الاقتراح...",
                style=discord.TextStyle.paragraph,
                min_length=3,
                max_length=500,
                required=True,
            )
            self.add_item(self.reason)

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            await self.review_view._decide(
                interaction,
                accepted=False,
                reason=str(self.reason.value or "").strip(),
                message=self.message,
            )


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

        async def _reply(self, interaction: discord.Interaction, text: str):
            if interaction.response.is_done():
                await interaction.followup.send(text, ephemeral=True)
            else:
                await interaction.response.send_message(text, ephemeral=True)

        async def _decide(
            self,
            interaction: discord.Interaction,
            accepted: bool,
            *,
            reason: str | None = None,
            message=None,
        ):
            member = interaction.user
            if not isinstance(member, discord.Member) or not _is_staff_reviewer(member):
                await self._reply(interaction, "❌ هاد الزر خاص غير بالإدارة.")
                return

            message = message or interaction.message
            if message is None:
                await self._reply(interaction, "❌ ما قدرناش نلقاو رسالة الاقتراح.")
                return

            # الرفض كيتأكد بسبب مختصر قبل ما يتبدل السجل أو الرسالة.
            if not accepted and reason is None:
                await interaction.response.send_modal(SuggestionRejectReasonModal(self, message))
                return

            sug_id, record = find_suggestion_by_message_id(message.id)
            if not record:
                await self._reply(interaction, "❌ ماكاينش هاد الاقتراح فالسجل ديالنا.")
                return
            if record.get("status") != "pending":
                await self._reply(interaction, "⚠️ هاد الاقتراح تدار فيه قرار من قبل.")
                return

            decided_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            reason = (reason or "").strip()[:500] if not accepted else ""
            record["status"] = "accepted" if accepted else "rejected"
            record["decided_by"] = member.id
            record["decided_at"] = decided_at
            record["reason"] = reason if not accepted else None
            save_suggestions()

            embed = message.embeds[0]
            embed.color = discord.Color.green() if accepted else discord.Color.red()
            decision_label = "✅ مقبول" if accepted else "❌ مرفوض"
            decision_value = (
                f"**الحالة:** {decision_label}\n"
                f"**من طرف:** {member.mention}\n"
                f"**التاريخ:** {decided_at}"
            )
            if not accepted:
                decision_value += f"\n**السبب:** {reason or 'ما تعطاتش شي تفاصيل إضافية.'}"
            decision_field_index = next(
                (index for index, field in enumerate(embed.fields) if field.name == "📌 القرار"),
                None,
            )
            if decision_field_index is None:
                embed.add_field(name="📌 القرار", value=decision_value, inline=False)
            else:
                embed.set_field_at(decision_field_index, name="📌 القرار", value=decision_value, inline=False)
            embed.set_footer(
                text=f"{SERVER_NAME} | Suggestion #{sug_id} | "
                     f"{'✅ Accepted' if accepted else '❌ Rejected'} من طرف {member.display_name} | {decided_at}"
            )
            for child in self.children:
                child.disabled = True
            if interaction.response.is_done():
                await message.edit(embed=embed, view=self)
                await interaction.followup.send("✅ تسجل القرار وبقات الرسالة فالقناة.", ephemeral=True)
            else:
                await interaction.response.edit_message(embed=embed, view=self)

            guild = interaction.guild
            author = guild.get_member(record["author_id"]) if guild else None
            if author is None:
                try:
                    author = await bot.fetch_user(int(record["author_id"]))
                except Exception:
                    author = None
            if author:
                try:
                    if accepted:
                        dm_title = f"✅ الاقتراح ديالك تقبل • #{sug_id}"
                        dm_description = (
                            "شكراً على الفكرة ديالك! الإدارة راجعاتها وقررات أنها مناسبة "
                            "لتطوير السيرفر."
                        )
                        dm_color = discord.Color.green()
                    else:
                        dm_title = f"❌ الاقتراح ديالك ترفض • #{sug_id}"
                        dm_description = (
                            "شكراً على المشاركة. الإدارة راجعات الاقتراح، ولكن ما غاديش "
                            "نعتمدو هاد الفكرة دابا."
                        )
                        dm_color = discord.Color.red()

                    dm_embed = discord.Embed(
                        title=dm_title,
                        description=dm_description,
                        color=dm_color,
                        timestamp=datetime.now(),
                    )
                    dm_embed.add_field(
                        name="💡 الاقتراح ديالك",
                        value=str(record.get("text") or "—")[:1024],
                        inline=False,
                    )
                    dm_embed.add_field(
                        name="👤 القرار من طرف",
                        value=f"{member.display_name}\n📅 {decided_at}",
                        inline=True,
                    )
                    if not accepted:
                        dm_embed.add_field(
                            name="📝 سبب الرفض",
                            value=reason or "ما تعطاتش شي تفاصيل إضافية.",
                            inline=False,
                        )
                    jump_url = getattr(message, "jump_url", None)
                    if jump_url:
                        dm_embed.add_field(
                            name="🔗 التفاصيل",
                            value=f"[شوف الاقتراح فالسيرفر]({jump_url})",
                            inline=False,
                        )
                    dm_embed.set_footer(text=f"{SERVER_NAME} • GGMW9 Suggestions")
                    await author.send(
                        embed=dm_embed,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except Exception:
                    # A closed DM must never undo a decision already recorded
                    # in the suggestions channel.
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
    
            # The public suggestion is already visible in the channel.  We
            # still acknowledge the modal interaction, then remove the
            # success response immediately so it does not sit underneath the
            # suggestion as an extra ephemeral message.
            await interaction.response.send_message("✅", ephemeral=True)
            try:
                await interaction.delete_original_response()
            except (discord.NotFound, discord.HTTPException):
                # If Discord rejects the cleanup, the fallback is only the
                # short check mark rather than a duplicate public message.
                pass
    
    
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
    
    
    @bot.hybrid_command(name="aicheck", description="تشيك واش الموديل ديال الـ AI والرصيد خدامين مزيان")
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def aicheck_cmd(ctx):
        """كيدير تشيك حقيقي (ماشي نظري): كيبعث طلب فعلي للموديل المدفوع، كيقيس الوقت،
        كيجيب الرصيد اللي باقي، وكيجرب الترجمة للدارجة."""
        if not (is_owner(ctx) or any(role.id == ADMIN_ROLE_ID for role in ctx.author.roles)):
            await ctx.send("❌ هاد الأمر خاص غير بـ Owner والـ Admin.", delete_after=6)
            return
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
    
    
    # ملاحظة: الأمر /suggest تحيد — البانل عندو زر "💡 دير اقتراح" كيدير
    # نفس الخدمة بالضبط (كيستافد من نفس الدالة _create_suggestion_from_panel).

    
    async def setup_suggestions_info(guild: discord.Guild):
        """Keep ONE public Darija Suggestions panel; language sessions are private."""
        if not SUGGESTIONS_CHANNEL_ID:
            return False
        channel = bot.get_channel(SUGGESTIONS_CHANNEL_ID)
        if not channel:
            return False
    
        embed = _suggestions_home_embed("darija")
        view = SuggestionsPanelView().add_language_selector()
    
        message = await upsert_fixed_panel(
            bot,
            channel,
            key="suggestions_info",
            matches=lambda message: (
                message.author == bot.user
                and bool(message.embeds)
                and any(
                    marker in (message.embeds[0].title or "")
                    for marker in (
                        "الاقتراحات",
                        "اقتراحات GGMW9",
                        "GGMW9 Suggestions",
                        "Suggestions GGMW9",
                    )
                )
            ),
            content=None,
            embed=embed,
            view=view,
            history_limit=None,
        )
        if message is None:
            print("[SUGGESTIONS] panel update failed")
        return message is not None
    
    
    @bot.hybrid_command(name="setupsuggestions")
    @app_commands.default_permissions(administrator=True)
    @owner_only()
    async def setupsuggestions_cmd(ctx):
        """كيصاوب/يعاود يصاوب رسالة الشرح ديال channel الاقتراحات فـ SUGGESTIONS_CHANNEL_ID (Admin)"""
        if not SUGGESTIONS_CHANNEL_ID:
            await ctx.send("❌ حط `SUGGESTIONS_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
            return
        await setup_suggestions_info(ctx.guild)
        await ctx.send("✅ رسالة الشرح ديال الاقتراحات تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
