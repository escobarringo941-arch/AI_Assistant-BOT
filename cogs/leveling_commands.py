# -*- coding: utf-8 -*-
"""Unchanged ordered source component: leveling_commands."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║              Leveling System — أوامر                     ║
    # ═══════════════════════════════════════════════════════
    
    def _progress_bar(current: int, needed: int, length: int = 20) -> str:
        ratio = max(0, min(1, current / needed)) if needed else 0
        filled = int(length * ratio)
        return "🟩" * filled + "⬛" * (length - filled)
    
    
    def get_current_member_xp_ranking(guild: discord.Guild):
        """
        Ranking ديال XP كيشمل غير الأعضاء اللي مازالين داخل السيرفر دابا.
    
        مهم:
        - ما كنمسحوش levels_db ديال اللي خرج.
        - غير كنخبيه من الترتيب وهو خارج.
        - إلا رجع، نفس XP المحفوظة كتردو للمركز اللي كيستحق حسب XP.
        """
        guild_data = levels_db.get(str(guild.id), {})
        if not guild_data:
            return []
    
        # intents.members=True عند البوت، لذلك guild.members هو source واضح للأعضاء الحاليين.
        current_member_ids = {
            str(member.id)
            for member in guild.members
            if not member.bot
        }
    
        return sorted(
            (
                (uid, data)
                for uid, data in guild_data.items()
                if uid in current_member_ids
            ),
            key=lambda item: total_xp_earned(item[1]),
            reverse=True,
        )
    
    
    def build_rank_embed(guild: discord.Guild, member: discord.Member) -> discord.Embed:
        """نفس Rank ديال /rank، قابل للاستعمال من الـ Levels Info Panel بلا كتابة."""
        data = get_user_level_data(guild.id, member.id)
        needed = xp_needed_for_level(data["level"])
    
        ranking = get_current_member_xp_ranking(guild)
        rank_position = next(
            (i + 1 for i, (uid, _) in enumerate(ranking) if uid == str(member.id)),
            None
        )
    
        badge = ""
        if data["level"] >= 100:
            badge = "👑 "
        elif data["level"] >= 70:
            badge = "🌟 "
    
        embed = discord.Embed(
            title=f"📊 المستوى ديال {badge}{member.display_name}",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="🏆 Level", value=str(data["level"]), inline=True)
        embed.add_field(
            name="🥇 الترتيب",
            value=f"#{rank_position}" if rank_position else "—",
            inline=True
        )
        embed.add_field(name="✨ XP", value=f"{data['xp']} / {needed}", inline=True)
        embed.add_field(
            name="التقدم",
            value=_progress_bar(data["xp"], needed),
            inline=False
        )
    
        active_perks = get_level_perks(data["level"])
        embed.add_field(
            name="🎁 الامتيازات الحالية",
            value=(
                f"**{active_perks['name']}**\n"
                f"🛒 Shop: **-{active_perks['shop_discount_percent']}%** • "
                f"🎁 Daily: **+{active_perks['daily_bonus_percent']}%**\n"
                f"🏦 Loan Base: **{cfg.fmt_money(active_perks['loan_base'])}** • "
                f"Interest **{active_perks['loan_interest']}%** • "
                f"**{active_perks['loan_days']}d**\n"
                f"{active_perks['feature']}"
            ),
            inline=False,
        )
    
        next_perks = get_next_level_perks(data["level"])
        if next_perks:
            embed.add_field(
                name="🚀 الهدف الجاي",
                value=(
                    f"Level **{next_perks['threshold']}** — **{next_perks['name']}**\n"
                    f"🛒 -{next_perks['shop_discount_percent']}% • "
                    f"🎁 +{next_perks['daily_bonus_percent']}% • "
                    f"🏦 {cfg.fmt_money(next_perks['loan_base'])} / "
                    f"{next_perks['loan_interest']}% / {next_perks['loan_days']}d"
                ),
                inline=False,
            )
    
        if get_active_xp_multiplier(data) > 1.0:
            try:
                expires_dt = datetime.fromisoformat(data["xp_boost_expires"])
                embed.add_field(
                    name="🚀 بونيص XP نشط",
                    value=(
                        f"+{LEVEL_MILESTONE_XP_BOOST_PERCENT}% حتى "
                        f"<t:{int(expires_dt.timestamp())}:R>"
                    ),
                    inline=False
                )
            except Exception:
                pass
    
        if data.get("bio"):
            embed.add_field(name="📝 بيو", value=data["bio"][:200], inline=False)

        if data.get("legend_title") and data["level"] >= 100:
            embed.add_field(
                name="👑 اللقب الأسطوري",
                value=str(data["legend_title"])[:90],
                inline=False,
            )
    
        embed.set_footer(text=f"{SERVER_NAME} | Leveling System")
        return embed
    
    
    @bot.command(name="rank", hidden=True)
    async def rank_cmd(ctx, member: Optional[discord.Member] = None):
        """كيبين المستوى والـ XP ديال عضو (نتا ولا شخص آخر)"""
        if not bot_settings['leveling_enabled']:
            await ctx.send(
                "❌ نظام Leveling معطل دابا. شعلو من `/botpanel` (Admin).",
                delete_after=6
            )
            return
        member = member or ctx.author
        await ctx.send(embed=build_rank_embed(ctx.guild, member))
    
    
    @bot.command(name="setbio", hidden=True)
    async def setbio_cmd(ctx, *, text: str = ""):
        """بدل البيو الشخصي ديالك اللي كيبان فـ /rank — متاحة من Level 20 (Milestone perk)"""
        data = get_user_level_data(ctx.guild.id, ctx.author.id)
        if data["level"] < 20:
            await ctx.send("🔒 هاد الميزة كتفتح فـ **Level 20**. كمل شوية باقي ليك!", ephemeral=True, delete_after=8)
            return
        data["bio"] = text.strip()[:200]
        save_levels()
        if data["bio"]:
            await ctx.send(f"✅ تبدل البيو ديالك لـ: \"{data['bio']}\"", ephemeral=True)
        else:
            await ctx.send("✅ تمسح البيو ديالك.", ephemeral=True)
    
    
    class SimplePollView(discord.ui.View):
        def __init__(self, options: list):
            super().__init__(timeout=None)
            self.votes = {opt: set() for opt in options}
            for i, opt in enumerate(options):
                self.add_item(self._make_button(opt, i))
    
        def _make_button(self, option_text: str, index: int):
            emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
            btn = discord.ui.Button(label=option_text[:80], emoji=emojis[index] if index < len(emojis) else None,
                                     style=discord.ButtonStyle.primary, custom_id=f"poll_opt_{index}")
    
            async def callback(interaction: discord.Interaction):
                for voters in self.votes.values():
                    voters.discard(interaction.user.id)
                self.votes[option_text].add(interaction.user.id)
                lines = [f"**{opt}** — {len(voters)} صوت" for opt, voters in self.votes.items()]
                await interaction.response.edit_message(
                    embed=discord.Embed(
                        title=interaction.message.embeds[0].title,
                        description="\n".join(lines),
                        color=discord.Color.blurple()
                    ),
                    view=self
                )
    
            btn.callback = callback
            return btn
    
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
