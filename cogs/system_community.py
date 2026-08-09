# -*- coding: utf-8 -*-
"""Birthdays, zodiac roles, marriages, and best friends.

Extracted mechanically from the legacy ai_bot.py.  Runtime state is attached
to bot_core's shared namespace so existing cross-system references keep the
same object identity and startup order.
"""

import bot_core as core

core.attach_namespace(globals())


# ═══════════════════════════════════════════════════════
# ║        Phase 8 — أوامر نظام Birthdays                   ║
# ═══════════════════════════════════════════════════════









# ═══════════════════════════════════════════════════════
# ║   نظام Marry/Bestfriend (أزواج/أصدقاء) — 💌 الأوامر        ║
# ═══════════════════════════════════════════════════════

RELATIONSHIP_LABELS = {
    "marriages": {
        "verb_propose": "يتزوج", "noun": "زواج", "emoji": "💍", "verb_done": "تزوجو",
        "role_prefix": "💍", "color": discord.Color.from_rgb(255, 93, 162),
        "title_propose": "💍 طلب زواج جديد", "title_accept": "💍 مبروك! زواج جديد",
        "exclusive": True,   # ← عضو وحد ما يقدرش يكون عندو كتر من زواج واحد فنفس الوقت
    },
    "bestfriends": {
        "verb_propose": "يكون Best Friend ديال", "noun": "صداقة", "emoji": "🤝", "verb_done": "وليو Best Friends",
        "role_prefix": "🤝", "color": discord.Color.from_rgb(85, 193, 255),
        "title_propose": "🤝 طلب صداقة (Best Friend) جديد", "title_accept": "🤝 مبروك! صداقة جديدة",
        "exclusive": False,  # ← عضو وحد يقدر يكون عندو بزاف ديال الـ Best Friends فنفس الوقت
    },
}


def _relationship_role_id(kind: str) -> int:
    return MARRIAGE_ROLE_ID if kind == "marriages" else BESTFRIEND_ROLE_ID


def _personal_role_color(kind: str) -> int:
    return MARRIAGE_PERSONAL_ROLE_COLOR if kind == "marriages" else BESTFRIEND_PERSONAL_ROLE_COLOR


def _safe_role_name(prefix: str, display_name: str) -> str:
    """كيبني سمية رول صحيحة (Discord كيسمح بحد أقصى 100 حرف)."""
    name = f"{prefix} {display_name}"
    return name[:100]


def _relationship_conflict_message(kind: str, proposer_id: int, target_id: int, target_mention: str) -> Optional[str]:
    """كتشوف واش كاين شي مانع باش هاد الجوج يديرو العلاقة، وكترجع رسالة الخطأ (وإلا None إلا ماكاين والو).
    - marriages: exclusive → حتى واحد فيهم مايكونش عندو زواج آخر.
    - bestfriends: ماشي exclusive → غير كنمنعو نفس الجوج بالضبط يكررو الصداقة مرتين."""
    label = RELATIONSHIP_LABELS[kind]
    if label["exclusive"]:
        existing_key, existing_record = find_relationship(kind, proposer_id)
        if existing_key:
            partner_id = get_partner_id(existing_record, proposer_id)
            return f"❌ عندك ديجا {label['noun']} مع <@{partner_id}>. دير `/divorce` أولاً."
        target_key, _ = find_relationship(kind, target_id)
        if target_key:
            return f"❌ {target_mention} عندو ديجا {label['noun']} مع شي حد آخر."
    else:
        if has_relationship_with(kind, proposer_id, target_id):
            return f"❌ عندك ديجا {label['noun']} مع {target_mention}."
    return None


async def _create_personal_partner_roles(guild: discord.Guild, kind: str,
                                          proposer: discord.Member, target: discord.Member):
    """كتصاوب جوج رولات شخصية: وحدة للـ proposer بسمية الـ target، ووحدة للـ target بسمية الـ proposer.
    كترجع dict {user_id: role_id} — وإلا فشلات (صلاحيات ناقصة مثلا)، كترجع {}."""
    if not RELATIONSHIP_PERSONAL_ROLE_ENABLED:
        return {}
    label = RELATIONSHIP_LABELS[kind]
    color = discord.Color(_personal_role_color(kind))
    result = {}
    try:
        role_for_proposer = await guild.create_role(
            name=_safe_role_name(label["role_prefix"], target.display_name),
            color=color, hoist=False, mentionable=False,
            reason=f"{label['noun']} — رول شخصي لـ {proposer} بسمية {target}"
        )
        role_for_target = await guild.create_role(
            name=_safe_role_name(label["role_prefix"], proposer.display_name),
            color=color, hoist=False, mentionable=False,
            reason=f"{label['noun']} — رول شخصي لـ {target} بسمية {proposer}"
        )
        await proposer.add_roles(role_for_proposer, reason=f"{label['noun']} — قبول")
        await target.add_roles(role_for_target, reason=f"{label['noun']} — قبول")
        result = {proposer.id: role_for_proposer.id, target.id: role_for_target.id}
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[RELATIONSHIPS] ما قدرتش نصاوب الرولات الشخصية: {e}")
    return result


async def _delete_personal_partner_roles(guild: discord.Guild, record: dict):
    """كتحيد وكتمسح الرولات الشخصية المرتبطة بهاد العلاقة (منين تنتهي)."""
    role_ids = record.get("personal_role_ids", {}) or {}
    for uid_str, role_id in role_ids.items():
        role = guild.get_role(role_id)
        if not role:
            continue
        try:
            await role.delete(reason="العلاقة انتهات")
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[RELATIONSHIPS] ما قدرتش نمسح الرول {role_id}: {e}")


async def _send_relationship_announcement(guild: discord.Guild, embed: discord.Embed, content: Optional[str] = None):
    """كتبعث إعلان عام فـ RELATIONSHIP_ANNOUNCE_CHANNEL_ID (مثلا #general) — مفيدة للاحتفال
    بزواج/صداقة جديدة، ولا لتبيان بلي علاقة انتهات. كتفشل بصمت إلا الـ channel ماكاينش/ماعندوش صلاحية."""
    if not RELATIONSHIP_ANNOUNCE_CHANNEL_ID:
        return
    channel = guild.get_channel(RELATIONSHIP_ANNOUNCE_CHANNEL_ID)
    if not channel:
        return
    try:
        await channel.send(content=content, embed=embed)
    except (discord.Forbidden, discord.HTTPException) as e:
        print(f"[RELATIONSHIPS] ما قدرتش نبعث الإعلان فـ #general: {e}")


async def _finalize_end_relationship(guild: discord.Guild, kind: str, key: str, record: dict,
                                      ended_by_id: int):
    """المنطق المشترك باش نسالو علاقة: كتحيد الرول العام + الرولات الشخصية، كتمسح السجل،
    وكتبعث تنبيه DM للطرف الآخر + إعلان عام. كترجع partner_id."""
    label = RELATIONSHIP_LABELS[kind]
    partner_id = get_partner_id(record, ended_by_id)

    role_id = _relationship_role_id(kind)
    if role_id:
        role = guild.get_role(role_id)
        if role:
            partner_member = guild.get_member(partner_id)
            ender_member = guild.get_member(ended_by_id)
            for m in (ender_member, partner_member):
                if m and role in m.roles:
                    # نتأكدو بلي ماعندوش علاقة أخرى بنفس النوع قبل ما نحيدو الرول العام (حالة bestfriends المتعددة)
                    if label["exclusive"] or not find_all_relationships(kind, m.id):
                        try:
                            await m.remove_roles(role, reason=f"{kind} — سالات")
                        except (discord.Forbidden, discord.HTTPException):
                            pass

    await _delete_personal_partner_roles(guild, record)
    end_relationship(kind, key)

    await log_action(
        guild, f"💔 {label['noun'].capitalize()} انتهى",
        f"<@{ended_by_id}> + <@{partner_id}>", discord.Color.dark_grey()
    )

    end_verb = "طلقو بعضياتهم 💔" if kind == "marriages" else "ماعادوش أصدقاء مقربين 💔"
    ender_member_for_announce = guild.get_member(ended_by_id)
    end_announce = discord.Embed(
        description=(
            f"## 💔 {label['noun'].capitalize()} انتهى\n"
            f"### <@{ended_by_id}>  ⛓️‍💥  <@{partner_id}>\n\n"
            f"{label['emoji']} {end_verb}"
        ),
        color=discord.Color.dark_grey(), timestamp=datetime.now()
    )
    if ender_member_for_announce:
        end_announce.set_thumbnail(url=ender_member_for_announce.display_avatar.url)
    end_announce.set_footer(text=SERVER_NAME)
    end_content = f"# 💔 {label['noun'].capitalize()} انتهى"
    await _send_relationship_announcement(guild, end_announce, content=end_content)

    partner_member = guild.get_member(partner_id)
    if partner_member:
        try:
            ender = guild.get_member(ended_by_id)
            ender_name = str(ender) if ender else "شي عضو"
            await partner_member.send(embed=discord.Embed(
                description=f"💔 **{ender_name}** نهى معاك {label['noun']} ديالكم.",
                color=discord.Color.dark_grey()
            ))
        except discord.HTTPException:
            pass

    return partner_id


class RelationshipProposalView(discord.ui.View):
    """طلب الزواج/الصداقة — كتتبعث فـ DM للشخص المطلوب، غير هو لي يقدر يدوس على الأزرار.
    كنخزنو الـ guild و IDs (ماشي discord.Member) حيت فـ DM ماكاينش guild context."""

    def __init__(self, kind: str, guild: discord.Guild, proposer: discord.Member, target: discord.Member):
        super().__init__(timeout=RELATIONSHIP_PROPOSAL_TIMEOUT_SECONDS)
        self.kind = kind
        self.guild = guild
        self.proposer_id = proposer.id
        self.target_id = target.id
        self.proposer_display = str(proposer)
        self.target_display = str(target)
        self.responded = False
        self.message: Optional[discord.Message] = None

    async def on_timeout(self):
        if self.responded:
            return
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    content=None,
                    embed=discord.Embed(
                        description=f"⏱️ الطلب انتهت مدتو، {self.target_display} ما ردش فالوقت.",
                        color=discord.Color.dark_grey()
                    ),
                    view=self
                )
            except discord.HTTPException:
                pass
        proposer = self.guild.get_member(self.proposer_id)
        if proposer:
            try:
                await proposer.send(f"⏱️ الطلب ديالك لـ **{self.target_display}** انتهت مدتو بلا رد.")
            except discord.HTTPException:
                pass

    async def _fetch_pair(self):
        target = self.guild.get_member(self.target_id) or await self.guild.fetch_member(self.target_id)
        proposer = self.guild.get_member(self.proposer_id) or await self.guild.fetch_member(self.proposer_id)
        return proposer, target

    @discord.ui.button(label="✅ قبول", style=discord.ButtonStyle.success)
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ هاد الطلب ماشي ليك.", ephemeral=True)
            return
        if self.responded:
            return
        self.responded = True
        label = RELATIONSHIP_LABELS[self.kind]

        try:
            proposer, target = await self._fetch_pair()
        except discord.NotFound:
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=discord.Embed(
                description="❌ ما قدرتش نلقى العضو فالسيرفر (يمكن خرج).", color=discord.Color.red()
            ), view=self)
            return

        # نتأكدو مرة أخرى بلي مازال ماكاين حتى مانع (بين ما تصاوب الطلب ودابا)
        conflict = _relationship_conflict_message(self.kind, proposer.id, target.id, target.mention)
        if conflict:
            for child in self.children:
                child.disabled = True
            await interaction.response.edit_message(embed=discord.Embed(
                description=f"❌ {conflict.lstrip('❌ ')}\nالطلب لغي.", color=discord.Color.red()
            ), view=self)
            return

        pair_key = create_relationship(self.kind, proposer.id, target.id)

        # ═══ الرول العام (اختياري) ═══
        role_note = ""
        general_role_id = _relationship_role_id(self.kind)
        if general_role_id:
            general_role = self.guild.get_role(general_role_id)
            if general_role:
                try:
                    await proposer.add_roles(general_role, reason=f"{label['noun']} — قبول")
                    await target.add_roles(general_role, reason=f"{label['noun']} — قبول")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # ═══ الرولات الشخصية بسمية الشريك ═══
        personal_roles = await _create_personal_partner_roles(self.guild, self.kind, proposer, target)
        if personal_roles:
            set_relationship_personal_roles(self.kind, pair_key, personal_roles)
            role_note = "\n✨ كل واحد فيكم ياخد رول شخصي بسمية الآخر."

        for child in self.children:
            child.disabled = True
        result_embed = discord.Embed(
            title=label["title_accept"],
            description=(
                f"**{proposer.mention}** {label['emoji']} **{target.mention}**\n\n"
                f"{label['verb_done'].capitalize()} رسمياً دابا!{role_note}"
            ),
            color=label["color"], timestamp=datetime.now()
        )
        result_embed.set_footer(text=SERVER_NAME)
        await interaction.response.edit_message(content=None, embed=result_embed, view=self)

        # نعلمو الـ proposer بلي تقبل (هو ماشي حاضر فهاد الـ DM)
        try:
            notify_embed = discord.Embed(
                title=label["title_accept"],
                description=f"{target.mention} قبل الطلب ديالك ديال {label['noun']}! {label['emoji']}{role_note}",
                color=label["color"]
            )
            await proposer.send(embed=notify_embed)
        except discord.HTTPException:
            pass

        await log_action(
            self.guild, f"{label['emoji']} {label['noun'].capitalize()} جديد",
            f"**{proposer.mention}** + **{target.mention}**", label["color"]
        )

        # ═══ إعلان عام فـ #general — كبير وعاطي لعين، يبان قدام الناس ═══
        announce_embed = discord.Embed(
            description=(
                f"## {label['emoji']} {label['verb_done'].capitalize()} رسمياً! {label['emoji']}\n"
                f"### {proposer.mention}  ✨  {target.mention}\n\n"
                f"{'💍 علاقة زواج جديدة انولدات فـ' if self.kind == 'marriages' else '🤝 صداقة جديدة انولدات فـ'} "
                f"**{self.guild.name}**! مبروك عليكم 🎉"
            ),
            color=label["color"], timestamp=datetime.now()
        )
        announce_embed.set_author(name=f"{label['noun'].capitalize()} جديد 🎊",
                                   icon_url=target.display_avatar.url)
        announce_embed.set_thumbnail(url=proposer.display_avatar.url)
        announce_embed.set_image(url=target.display_avatar.url)
        announce_embed.add_field(name="📅 بدات", value=f"<t:{int(datetime.now().timestamp())}:F>", inline=True)
        announce_embed.set_footer(
            text=f"{SERVER_NAME} • مبروك للجوج! 🎊",
            icon_url=self.guild.icon.url if self.guild.icon else None
        )
        announce_content = f"# {label['emoji']} {proposer.display_name} × {target.display_name} {label['emoji']}"
        await _send_relationship_announcement(self.guild, announce_embed, content=announce_content)

    @discord.ui.button(label="❌ رفض", style=discord.ButtonStyle.danger)
    async def decline_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.target_id:
            await interaction.response.send_message("❌ هاد الطلب ماشي ليك.", ephemeral=True)
            return
        if self.responded:
            return
        self.responded = True
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=None,
            embed=discord.Embed(description=f"💔 رفضتي الطلب ديال **{self.proposer_display}**.",
                                 color=discord.Color.dark_grey()),
            view=self
        )
        proposer = self.guild.get_member(self.proposer_id)
        if proposer:
            try:
                label = RELATIONSHIP_LABELS[self.kind]
                await proposer.send(embed=discord.Embed(
                    description=f"💔 **{self.target_display}** رفض الطلب ديالك ديال {label['noun']}.",
                    color=discord.Color.dark_grey()
                ))
            except discord.HTTPException:
                pass


async def _propose_relationship(ctx, kind: str, target: discord.Member):
    label = RELATIONSHIP_LABELS[kind]
    proposer = ctx.author

    if target.id == proposer.id:
        await ctx.send(f"❌ ما تقدرش {label['verb_propose']} نفسك 😅", delete_after=8, ephemeral=True)
        return
    if target.bot:
        await ctx.send("❌ ما تقدرش تدير هادشي مع بوت 🤖", delete_after=8, ephemeral=True)
        return

    conflict = _relationship_conflict_message(kind, proposer.id, target.id, target.mention)
    if conflict:
        await ctx.send(conflict, delete_after=10, ephemeral=True)
        return

    view = RelationshipProposalView(kind, ctx.guild, proposer, target)
    proposal_embed = discord.Embed(
        title=label["title_propose"],
        description=(
            f"{proposer.mention} بغا {label['verb_propose']}ك فـ **{ctx.guild.name}**! {label['emoji']}\n\n"
            f"واش كتقبل؟ (عندك {RELATIONSHIP_PROPOSAL_TIMEOUT_SECONDS // 60} دقايق باش تجاوب)"
        ),
        color=label["color"], timestamp=datetime.now()
    )
    proposal_embed.set_thumbnail(url=proposer.display_avatar.url)
    proposal_embed.set_footer(text=SERVER_NAME)

    sent_in_dm = False
    if RELATIONSHIP_DM_PROPOSALS:
        try:
            msg = await target.send(embed=proposal_embed, view=view)
            view.message = msg
            sent_in_dm = True
        except discord.HTTPException:
            sent_in_dm = False

    if sent_in_dm:
        # كتبان غير للشخص لي دار الأمر (ephemeral) — حتى واحد آخر فالشات ما غايشوفها.
        # الطلب الحقيقي راه تبعث فـ DM ديال target، هو لي غايشوف الـ embed والأزرار.
        await ctx.send(
            f"📨 بعثت الطلب ديال {label['noun']} لـ {target.mention} فـ DM ديالو، فـ انتظار الرد.",
            delete_after=15, ephemeral=True
        )
    else:
        # الـ DMs ديالو سادين — ماكاين حل آخر غير نبعثو الطلب هنا فنفس الـ channel كـ fallback
        # (خاص يكون view/embed مبان له باش يقدر يدوس على الأزرار، فهاد الحالة بوحدها كيبان فالشات)
        note = "" if not RELATIONSHIP_DM_PROPOSALS else "\n*(ما قدرتش نبعثلو DM — الطلب هنا)*"
        proposal_embed.description += note
        msg = await ctx.send(content=target.mention, embed=proposal_embed, view=view)
        view.message = msg


async def _end_relationship_cmd(ctx, kind: str):
    """للـ marriages (exclusive) — عندو غير علاقة وحدة، نسالوها مباشرة بلا اختيار.
    الرد هنا ephemeral (خاص بالشخص وحدو) — الإعلان الحقيقي كيتبعث فـ #general (_finalize_end_relationship)."""
    label = RELATIONSHIP_LABELS[kind]
    key, record = find_relationship(kind, ctx.author.id)
    if not key:
        await ctx.send(f"⚠️ ماعندكش {label['noun']} دابا.", delete_after=8, ephemeral=True)
        return

    partner_id = await _finalize_end_relationship(ctx.guild, kind, key, record, ctx.author.id)
    verb = "طلقتي" if kind == "marriages" else "قطعتي الصداقة مع"
    await ctx.send(f"{label['emoji']} {verb} <@{partner_id}>. 💔", ephemeral=True)


class BestfriendRemoveSelect(discord.ui.Select):
    def __init__(self, owner_id: int, guild: discord.Guild, pairs: list):
        # pairs: [(pair_key, record), ...] — كل وحدة كتولي خيار فـ dropdown
        options = []
        for key, record in pairs[:25]:
            partner_id = get_partner_id(record, owner_id)
            member = guild.get_member(partner_id)
            label_text = member.display_name if member else f"عضو ({partner_id})"
            duration = format_duration_since(record["since"])
            options.append(discord.SelectOption(label=label_text[:100], description=f"صديق مقرب منذ {duration}"[:100], value=key))
        super().__init__(placeholder="اختار شكون بغيتي تحيد من لائحة Best Friends ديالك...",
                          min_values=1, max_values=1, options=options)
        self.owner_id = owner_id
        self.guild = guild

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ هادي مقاديرش تستعملها.", ephemeral=True)
            return
        key = self.values[0]
        record = relationships_db.get("bestfriends", {}).get(key)
        if not record:
            await interaction.response.edit_message(content="⚠️ هاد العلاقة ماعادش موجودة (يمكن تحيدات من قبل).", embed=None, view=None)
            return

        partner_id = await _finalize_end_relationship(self.guild, "bestfriends", key, record, self.owner_id)
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(
            content=None,
            embed=discord.Embed(description=f"🤝💔 قطعتي الصداقة مع <@{partner_id}>.", color=discord.Color.dark_grey()),
            view=self.view
        )


class BestfriendRemoveView(discord.ui.View):
    def __init__(self, owner_id: int, guild: discord.Guild, pairs: list):
        super().__init__(timeout=60)
        self.add_item(BestfriendRemoveSelect(owner_id, guild, pairs))


async def unbestfriend_interactive(ctx):
    """بدل ما نحيدو مباشرة، كنوريو للعضو لائحة (dropdown) بكل الـ Best Friends ديالو دابا
    باش يختار بالضبط شكون بغى يحيد — مفيدة حيت عضو وحد يقدر يكون عندو بزاف ديالهم فنفس الوقت.
    كلشي هنا ephemeral (خاص بالشخص وحدو) — الإعلان الحقيقي كيتبعث فـ #general (_finalize_end_relationship)."""
    label = RELATIONSHIP_LABELS["bestfriends"]
    pairs = find_all_relationships("bestfriends", ctx.author.id)
    if not pairs:
        await ctx.send(f"⚠️ ماعندكش حتى {label['noun']} دابا.", delete_after=8, ephemeral=True)
        return

    lines = []
    for key, record in pairs:
        partner_id = get_partner_id(record, ctx.author.id)
        duration = format_duration_since(record["since"])
        lines.append(f"• <@{partner_id}> — منذ **{duration}**")

    embed = discord.Embed(
        title="🤝 شكون بغيتي تحيد؟",
        description="\n".join(lines) + "\n\nختار من اللائحة تحت 👇",
        color=label["color"]
    )
    view = BestfriendRemoveView(ctx.author.id, ctx.guild, pairs)
    await ctx.send(embed=embed, view=view, ephemeral=True)


async def _relationship_info_cmd(ctx, kind: str, member: Optional[discord.Member]):
    label = RELATIONSHIP_LABELS[kind]
    target = member or ctx.author

    if not label["exclusive"]:
        # bestfriends: نوريو الكل (ممكن يكون عندو بزاف)
        pairs = find_all_relationships(kind, target.id)
        if not pairs:
            who = "عندك" if target == ctx.author else f"عند {target.mention}"
            await ctx.send(f"💔 ما{who}ش {label['noun']} دابا.", delete_after=8)
            return
        lines = []
        for key, record in pairs:
            partner_id = get_partner_id(record, target.id)
            duration = format_duration_since(record["since"])
            lines.append(f"• <@{partner_id}> — منذ **{duration}**")
        embed = discord.Embed(
            title=f"{label['emoji']} {label['noun'].capitalize()} ديال {target.display_name}",
            description="\n".join(lines),
            color=label["color"]
        )
        await ctx.send(embed=embed)
        return

    key, record = find_relationship(kind, target.id)
    if not key:
        who = "عندك" if target == ctx.author else f"عند {target.mention}"
        await ctx.send(f"💔 ما{who}ش {label['noun']} دابا.", delete_after=8)
        return

    partner_id = get_partner_id(record, target.id)
    duration = format_duration_since(record["since"])
    embed = discord.Embed(
        title=f"{label['emoji']} {label['noun'].capitalize()}",
        description=f"{target.mention} + <@{partner_id}>\n⏳ منذ **{duration}**",
        color=label["color"]
    )
    await ctx.send(embed=embed)


async def _relationship_leaderboard_cmd(ctx, kind: str):
    label = RELATIONSHIP_LABELS[kind]
    records = list(relationships_db.get(kind, {}).values())
    if not records:
        await ctx.send(f"📭 ماكاين حتى {label['noun']} مسجلة دابا فالسيرفر.")
        return

    def _sort_key(r):
        try:
            return datetime.strptime(r["since"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return datetime.now()

    records.sort(key=_sort_key)  # الأقدم = الأطول مدة
    lines = []
    for i, r in enumerate(records[:10], 1):
        duration = format_duration_since(r["since"])
        lines.append(f"**{i}.** <@{r['user_a']}> + <@{r['user_b']}> — **{duration}**")

    embed = discord.Embed(
        title=f"{label['emoji']} أطول {label['noun']}ات فالسيرفر",
        description="\n".join(lines),
        color=label["color"]
    )
    embed.set_footer(text=f"{SERVER_NAME} | {label['noun'].capitalize()} Leaderboard")
    await ctx.send(embed=embed)


















async def check_and_announce_birthdays():
    """كتشيك كل الأعياد المسجلة، كتهني اللي عيد ميلادهم اليوم، وكتحيد الرول
    ديال البارح. كتصاوب فحالها من tasks.loop تحت (birthday_loop)."""
    channel = bot.get_channel(BIRTHDAY_ANNOUNCE_CHANNEL_ID) if BIRTHDAY_ANNOUNCE_CHANNEL_ID else None
    guild = channel.guild if channel else (bot.guilds[0] if bot.guilds else None)
    if not guild:
        return
    now = datetime.now()

    # 1) حيد الرول ديال البارح من اللي بقاو فـ role_holders
    if BIRTHDAY_ROLE_ID and birthdays_db.get("role_holders"):
        role = guild.get_role(BIRTHDAY_ROLE_ID)
        if role:
            for user_id in list(birthdays_db["role_holders"]):
                member = guild.get_member(int(user_id))
                if member and role in member.roles:
                    try:
                        await member.remove_roles(role, reason="عيد الميلاد سالي")
                    except Exception:
                        pass
        birthdays_db["role_holders"] = []

    # 2) شوف شكون عيد ميلادو اليوم
    changed = False
    for user_id, record in birthdays_db.get("birthdays", {}).items():
        if record.get("day") != now.day or record.get("month") != now.month:
            continue
        if record.get("last_announced_year") == now.year:
            continue  # تهنى ديجا هاد العام

        member = guild.get_member(int(user_id))
        record["last_announced_year"] = now.year
        changed = True
        if not member:
            continue

        if channel:
            zodiac_key = record.get("zodiac")
            zodiac_line = ""
            if zodiac_key:
                _, zodiac_label, zodiac_emoji = get_zodiac_sign(record["day"], record["month"])
                if zodiac_label:
                    zodiac_line = f"\n{zodiac_emoji} البرج: **{zodiac_label}**"

            embed = discord.Embed(
                title="🎉🎂 عيد ميلاد سعيد!",
                description=(
                    f"### 🎊 اليوم عيد ميلاد {member.mention}! 🎊\n"
                    f"كاع أعضاء **{SERVER_NAME}** كيهنيوك بهاد اليوم السعيد! 🥳🎈🎁"
                    f"{zodiac_line}"
                ),
                color=discord.Color.pink(),
                timestamp=datetime.now()
            )
            embed.set_author(name=str(member), icon_url=member.display_avatar.url)
            embed.set_image(url=member.display_avatar.replace(size=512).url)  # الصورة كبيرة وواضحة
            embed.set_footer(text=f"{SERVER_NAME} | Happy Birthday 🎂 | ID: {member.id}")
            try:
                await channel.send(content=f"🎉🎂 {member.mention} عيد ميلادك سعيد! 🎂🎉", embed=embed)
            except Exception:
                pass

        if BIRTHDAY_ROLE_ID:
            role = guild.get_role(BIRTHDAY_ROLE_ID)
            if role:
                try:
                    await member.add_roles(role, reason="عيد ميلاد اليوم")
                    birthdays_db.setdefault("role_holders", []).append(user_id)
                except Exception:
                    pass

    if changed:
        save_birthdays()


@tasks.loop(minutes=60)
async def birthday_loop():
    if not birthdays_db.get("birthdays") and not birthdays_db.get("role_holders"):
        return
    if datetime.now().hour != BIRTHDAY_ANNOUNCE_HOUR:
        return
    await check_and_announce_birthdays()


@birthday_loop.before_loop
async def before_birthday_loop():
    await bot.wait_until_ready()


@birthday_loop.error
async def birthday_loop_error(error):
    print(f"[BIRTHDAYS] خطأ فـ birthday_loop: {error}")


class CommunityCog(commands.Cog):
    """Discord command/event registration for this subsystem."""

    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance

    @commands.hybrid_command(name="setbirthday")
    async def setbirthday_cmd(self, ctx, day: int, month: int):
        """سجل عيد ميلادك (اليوم والشهر بوحدهم، بلا عام) — البوت غايعطيك رول البرج أوتوماتيكياً"""
        try:
            # كنستعملو عام كبيسة (2024) باش فبراير 29 يخدم زوين
            datetime(2024, month, day)
        except (ValueError, TypeError):
            await ctx.send("❌ التاريخ ماشي صحيح. اكتب مثلا `/setbirthday day:15 month:8`.", delete_after=8)
            return

        zodiac_key, zodiac_label, zodiac_emoji = get_zodiac_sign(day, month)

        birthdays_db.setdefault("birthdays", {})[str(ctx.author.id)] = {
            "day": day, "month": month, "last_announced_year": None, "zodiac": zodiac_key
        }
        save_birthdays()

        zodiac_note = ""
        if isinstance(ctx.author, discord.Member):
            await sync_zodiac_role(ctx.author, zodiac_key)
            if zodiac_key and ZODIAC_ROLE_IDS.get(zodiac_key):
                zodiac_note = f"\n{zodiac_emoji} عطيناك رول برج **{zodiac_label}**!"
            elif zodiac_key:
                zodiac_note = f"\n{zodiac_emoji} البرج ديالك هو **{zodiac_label}** (الرول ديالو ماعادش معطي فالإعدادات)."

        await ctx.send(
            f"🎂 تم تسجيل عيد ميلادك: **{day:02d}/{month:02d}**! غادي نهنيوك نهار عيد ميلادك.{zodiac_note}",
            delete_after=15
        )

    @commands.hybrid_command(name="removebirthday")
    async def removebirthday_cmd(self, ctx):
        """حيد عيد الميلاد ديالك من السجل (وكيحيد رول البرج زيادة)"""
        removed = birthdays_db.get("birthdays", {}).pop(str(ctx.author.id), None)
        if removed:
            save_birthdays()
            if isinstance(ctx.author, discord.Member):
                await sync_zodiac_role(ctx.author, None)  # كيحيد أي رول برج عندو بلا مايعطي جديد
            await ctx.send("🗑️ تم حيد عيد الميلاد ديالك من السجل.", delete_after=8)
        else:
            await ctx.send("⚠️ ماعندكش عيد ميلاد مسجل أصلاً.", delete_after=8)

    @commands.hybrid_command(name="birthday")
    async def birthday_cmd(self, ctx, member: Optional[discord.Member] = None):
        """بين عيد الميلاد ديالك ولا ديال عضو آخر (والبرج ديالو)"""
        target = member or ctx.author
        record = birthdays_db.get("birthdays", {}).get(str(target.id))
        if not record:
            if target == ctx.author:
                await ctx.send("⚠️ ماعندكش عيد ميلاد مسجل. استعمل `/setbirthday`.", delete_after=8)
            else:
                await ctx.send(f"⚠️ {target.mention} ماعندوش عيد ميلاد مسجل.", delete_after=8)
            return

        zodiac_key = record.get("zodiac")
        zodiac_line = ""
        if zodiac_key:
            _, zodiac_label, zodiac_emoji = get_zodiac_sign(record["day"], record["month"])
            zodiac_line = f"\n{zodiac_emoji} البرج: **{zodiac_label}**"
        await ctx.send(f"🎂 عيد ميلاد {target.mention}: **{record['day']:02d}/{record['month']:02d}**{zodiac_line}")

    @commands.hybrid_command(name="birthdays")
    async def birthdays_cmd(self, ctx):
        """بين لائحة أقرب 10 أعياد ميلاد جاية فالسيرفر"""
        today = datetime.now()
        today_date = today.date()
        entries = []
        for user_id, record in birthdays_db.get("birthdays", {}).items():
            member = ctx.guild.get_member(int(user_id)) if ctx.guild else None
            if not member:
                continue
            day, month = record["day"], record["month"]
            try:
                this_year_date = datetime(today.year, month, day).date()
            except ValueError:
                continue  # 29 فبراير فعام ماشي كبيسة
            next_date = this_year_date if this_year_date >= today_date else datetime(today.year + 1, month, day).date()
            days_left = (next_date - today_date).days
            entries.append((days_left, member, day, month))

        if not entries:
            await ctx.send("📭 ماكاين حتى عيد ميلاد مسجل دابا فالسيرفر.")
            return

        entries.sort(key=lambda x: x[0])
        lines = []
        for days_left, member, day, month in entries[:10]:
            when = "🎉 اليوم!" if days_left == 0 else f"بعد {days_left} يوم"
            lines.append(f"**{day:02d}/{month:02d}** — {member.mention} ({when})")

        embed = discord.Embed(
            title="🎂 أقرب أعياد الميلاد",
            description="\n".join(lines),
            color=discord.Color.pink()
        )
        embed.set_footer(text=f"{SERVER_NAME} | Birthdays")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="marry", description="اطلب من عضو يتزوجك 💍 (كيتبعث ليه DM)")
    async def marry_cmd(self, ctx, user: discord.Member):
        """اطلب من عضو يتزوجك 💍 — كيتبعث ليه طلب فـ DM وخاصو يقبل بزر"""
        await _propose_relationship(ctx, "marriages", user)

    @commands.hybrid_command(name="divorce")
    async def divorce_cmd(self, ctx):
        """طلق الزوج/الزوجة ديالك 💔 (كيحيد الرولات الشخصية ديال الجوج)"""
        await _end_relationship_cmd(ctx, "marriages")

    @commands.hybrid_command(name="marriage")
    async def marriage_cmd(self, ctx, user: Optional[discord.Member] = None):
        """بين معلومات الزواج ديالك ولا ديال عضو آخر"""
        await _relationship_info_cmd(ctx, "marriages", user)

    @commands.hybrid_command(name="marriages")
    async def marriages_cmd(self, ctx):
        """أطول 10 علاقات زواج فالسيرفر (Leaderboard)"""
        await _relationship_leaderboard_cmd(ctx, "marriages")

    @commands.hybrid_command(name="bestfriend", description="اطلب من عضو يكون Best Friend ديالك 🤝 (كيتبعث ليه DM)")
    async def bestfriend_cmd(self, ctx, user: discord.Member):
        """اطلب من عضو يكون Best Friend ديالك 🤝 — كيتبعث ليه طلب فـ DM وخاصو يقبل بزر
        (تقدر يكون عندك بزاف ديال الـ Best Friends فنفس الوقت)"""
        await _propose_relationship(ctx, "bestfriends", user)

    @commands.hybrid_command(name="unbestfriend", description="حيد شي صديق مقرب — كتوري ليك لائحة تختار منها")
    async def unbestfriend_cmd(self, ctx):
        """قطع الصداقة مع واحد من الـ Best Friends ديالك — كتوري ليك لائحة (dropdown) تختار منها بالضبط شكون"""
        await unbestfriend_interactive(ctx)

    @commands.hybrid_command(name="bestfriendinfo")
    async def bestfriendinfo_cmd(self, ctx, user: Optional[discord.Member] = None):
        """بين لائحة الـ Best Friends ديالك ولا ديال عضو آخر"""
        await _relationship_info_cmd(ctx, "bestfriends", user)

    @commands.hybrid_command(name="bestfriends")
    async def bestfriends_cmd(self, ctx):
        """أطول 10 صداقات فالسيرفر (Leaderboard)"""
        await _relationship_leaderboard_cmd(ctx, "bestfriends")


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(CommunityCog(bot_instance))
