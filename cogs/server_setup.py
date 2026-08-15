# -*- coding: utf-8 -*-
"""Unchanged ordered source component: server_setup."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    def build_levels_info_embed(guild: discord.Guild, lang: str = "darija") -> discord.Embed:
        lang = lang if lang in {"darija", "en", "fr"} else "darija"
        if lang == "en":
            title = "📊 Levels & XP — progression with real value"
            desc = (
                f"💬 **Chat:** {xp_settings['chat_min']}-{xp_settings['chat_max']} XP per eligible message, cooldown **{xp_settings['chat_cooldown']}s**.\n"
                f"🎙️ **Voice:** **{xp_settings['voice_per_interval']} XP** every {xp_settings['voice_interval_minutes']} minutes.\n"
                f"📡 **Go Live:** **{xp_settings['stream_per_interval']} XP** every {xp_settings['voice_interval_minutes']} minutes.\n\n"
                "## 🔄 How Level Roles work\nYou keep **only your highest Level Role**. When you reach a new threshold, the old Level Role is removed automatically. The bot also self-heals roles after restarts.\n\n"
                "## 🎁 Why level up?\nHigher levels unlock stronger **Shop discounts, Daily bonuses, better loan terms and safe social/Discord perks**.\n\n"
                "## 🖱️ No command needed\nUse the buttons below for your rank, another member's rank, leaderboard, roadmap, Bio, Poll and Legend Title.\n\n"
                "🌐 The language selector opens your **private translated XP panel**. Dismiss is safe; reopen it here anytime."
            )
            roadmap_name, roadmap_more = "🪜 Level Role Roadmap", "🪜 Roadmap (continued)"
            safety_name = "🛡️ Permission safety"
            safety_value = "Level Roles **never grant dangerous management permissions** such as View Audit Log, Manage Threads, Manage Events or Manage Emojis. Their value comes from safe social and economy perks."
            footer = f"{SERVER_NAME} | one Level Role • earn XP • unlock stronger perks • English"
        elif lang == "fr":
            title = "📊 Niveaux & XP — une progression qui a de la valeur"
            desc = (
                f"💬 **Chat :** {xp_settings['chat_min']}-{xp_settings['chat_max']} XP par message éligible, cooldown **{xp_settings['chat_cooldown']}s**.\n"
                f"🎙️ **Vocal :** **{xp_settings['voice_per_interval']} XP** toutes les {xp_settings['voice_interval_minutes']} minutes.\n"
                f"📡 **Go Live :** **{xp_settings['stream_per_interval']} XP** toutes les {xp_settings['voice_interval_minutes']} minutes.\n\n"
                "## 🔄 Fonctionnement des rôles de niveau\nTu gardes **uniquement ton rôle de niveau le plus élevé**. Quand tu atteins un nouveau palier, l'ancien rôle est retiré automatiquement. Le bot répare aussi les rôles après un redémarrage.\n\n"
                "## 🎁 Pourquoi monter de niveau ?\nLes niveaux débloquent de meilleures **réductions Shop, bonus Daily, conditions de prêt et avantages Discord/social sûrs**.\n\n"
                "## 🖱️ Aucune commande nécessaire\nUtilise les boutons pour ton rang, le rang d'un membre, le classement, la progression, la Bio, les sondages et le titre Legend.\n\n"
                "🌐 Le sélecteur ouvre ton **panneau XP privé traduit**. Tu peux le fermer puis le rouvrir ici sans problème."
            )
            roadmap_name, roadmap_more = "🪜 Progression des rôles", "🪜 Progression (suite)"
            safety_name = "🛡️ Sécurité des permissions"
            safety_value = "Les rôles de niveau **ne donnent jamais de permissions de gestion dangereuses** comme View Audit Log, Manage Threads, Manage Events ou Manage Emojis. Leur valeur vient des avantages sociaux et économiques sûrs."
            footer = f"{SERVER_NAME} | un seul rôle de niveau • gagne de l'XP • débloque des avantages • Français"
        else:
            title = "📊 نظام المستويات — XP عندو قيمة حقيقية"
            desc = (
                f"💬 **الشات:** {xp_settings['chat_min']}-{xp_settings['chat_max']} XP لكل رسالة مؤهلة، Cooldown **{xp_settings['chat_cooldown']}ث**.\n"
                f"🎙️ **الفويس:** **{xp_settings['voice_per_interval']} XP** كل {xp_settings['voice_interval_minutes']} دقايق.\n"
                f"📡 **Go Live:** **{xp_settings['stream_per_interval']} XP** كل {xp_settings['voice_interval_minutes']} دقايق.\n\n"
                "## 🔄 كيفاش كتخدم Level Role؟\n**عندك غير Role وحدة ديال Level.** منين توصل Threshold جديدة، البوت كيحيد القديمة وكيعطيك الأعلى أوتوماتيكياً، وحتى بعد Restart كيدير Self-Healing.\n\n"
                "## 🎁 علاش نطلع XP؟\nLevels كيحلو **Shop Discount أكبر، Daily Bonus أكبر، قرض أقوى وشروط أحسن، ومزايا Discord/Social آمنة**.\n\n"
                "## 🖱️ ما تحتاج تكتب حتى Command\nاستعمل الأزرار تحت: Rank ديالك، Rank ديال عضو، Leaderboard، Roadmap، Bio، Poll وLegend Title.\n\n"
                "🌐 اختيار اللغة كيحل **Panel خاصة بيك** مترجمة. إلا سديتيها بـDismiss تقدر ترجع تحلها من هنا فالحين."
            )
            roadmap_name, roadmap_more = "🪜 Roadmap ديال Level Roles", "🪜 Roadmap (تكملة)"
            safety_name = "🛡️ ملاحظة على الصلاحيات"
            safety_value = "Level Roles **ما كتعطيش صلاحيات إدارة خطيرة**. ماكاين لا View Audit Log لا Manage Threads لا Manage Events لا Manage Emojis. القيمة كتجي من امتيازات آمنة واقتصادية."
            footer = f"{SERVER_NAME} | Role وحدة ديال Level • طلع XP وفتح مزايا أقوى • Darija"
    
        embed = discord.Embed(title=title, description=desc, color=discord.Color.gold(), timestamp=datetime.now())
        lines = []
        current_level_roles = named_level_roles(guild)
        for lvl in LEVEL_THRESHOLDS:
            role = current_level_roles.get(lvl)
            role_display = role.mention if role else f"`Level {lvl}`"
            p = LEVEL_ROLE_BENEFITS.get(lvl, {})
            if lang == "en":
                line = (f"{role_display} **Lv {lvl} — {p.get('name','')}**\n> 🛒 Shop -{p.get('shop_discount_percent',0)}% • 🎁 Daily +{p.get('daily_bonus_percent',0)}% • 🏦 {cfg.fmt_money(int(p.get('loan_base',0)))} / {p.get('loan_interest',0)}% / {p.get('loan_days',0)}d\n> {p.get('feature','—')}")
            elif lang == "fr":
                line = (f"{role_display} **Nv {lvl} — {p.get('name','')}**\n> 🛒 Shop -{p.get('shop_discount_percent',0)}% • 🎁 Daily +{p.get('daily_bonus_percent',0)}% • 🏦 {cfg.fmt_money(int(p.get('loan_base',0)))} / {p.get('loan_interest',0)}% / {p.get('loan_days',0)}j\n> {p.get('feature','—')}")
            else:
                line = (f"{role_display} **Lv {lvl} — {p.get('name','')}**\n> 🛒 -{p.get('shop_discount_percent',0)}% • 🎁 Daily +{p.get('daily_bonus_percent',0)}% • 🏦 {cfg.fmt_money(int(p.get('loan_base',0)))} / {p.get('loan_interest',0)}% / {p.get('loan_days',0)}d\n> {p.get('feature','—')}")
            lines.append(line)
    
        chunks, current, current_len = [], [], 0
        for line in lines:
            if current and current_len + len(line) + 2 > 980:
                chunks.append(current); current, current_len = [], 0
            current.append(line); current_len += len(line) + 2
        if current: chunks.append(current)
        for idx, chunk in enumerate(chunks, 1):
            embed.add_field(name=roadmap_name if idx == 1 else roadmap_more, value="\n\n".join(chunk), inline=False)
        embed.add_field(name=safety_name, value=safety_value, inline=False)
        embed.set_footer(text=footer)
        return embed
    
    
    async def setup_levels_info_message(guild: discord.Guild):
        """Keep one Levels message and reset it to Darija after deploy/Owner Refresh."""
        if not LEVELS_INFO_CHANNEL_ID:
            return
        channel = bot.get_channel(LEVELS_INFO_CHANNEL_ID)
        if not channel:
            return
        embed = build_levels_info_embed(guild, "darija")
        message = await upsert_fixed_panel(
            bot,
            channel,
            key="levels_info",
            matches=lambda message: (
                message.author == bot.user
                and bool(message.embeds)
                and any(
                    marker in (message.embeds[0].title or "")
                    for marker in ("نظام المستويات", "Levels & XP", "Niveaux & XP")
                )
            ),
            content=None,
            embed=embed,
            view=LevelsInfoView("darija"),
            history_limit=None,
        )
        if message is None:
            print("[LEVEL INFO] ما قدرتش نحدّث الرسالة دابا.")
    
    
    @bot.command(name="setuplevels", hidden=True)
    @owner_only()
    async def setuplevels_cmd(ctx):
        """كيصاوب/يعاود يصاوب رسالة شرح نظام الـ Leveling فـ LEVELS_INFO_CHANNEL_ID (Admin)"""
        if not LEVELS_INFO_CHANNEL_ID:
            await ctx.send("❌ حط `LEVELS_INFO_CHANNEL_ID` فالـ CONFIG أولاً.", delete_after=8)
            return
        await setup_levels_info_message(ctx.guild)
        await ctx.send("✅ رسالة شرح نظام الـ Leveling تصاوبات (ولا كانت ديجا موجودة).", delete_after=8)
    
    
    # ملاحظة: الأمر /closeticket تحيد — البانل ديال التذكرة عندو زر
    # "🔒 سد الـ Ticket" (TicketControlView فـ support_system.py) كيدير
    # نفس الخدمة بالضبط.


    async def trigger_raid_lockdown(guild: discord.Guild, reason: str, duration_minutes: int = None):
        """كيصعد verification_level ديال السيرفر لأعلى درجة مؤقتاً، وكيبعث تنبيه للإدارة."""
        state = raid_state.setdefault(guild.id, {})
        if state.get("active"):
            return False
    
        state["active"] = True
        state["previous_verification_level"] = guild.verification_level
    
        try:
            await guild.edit(verification_level=discord.VerificationLevel.highest, reason="Anti-Raid: Lockdown أوتوماتيكي")
        except Exception as e:
            print(f"[ANTI-RAID] خطأ فـ تصعيد verification level: {e}")
    
        channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
        if channel:
            mentions = " ".join(f"<@&{rid}>" for rid in EXEMPT_ROLE_IDS)
            embed = discord.Embed(
                title="🚨🚨 Anti-Raid: Lockdown مفعل!",
                description=(
                    f"{reason}\n\n"
                    f"✅ verification level تصعدات مؤقتاً لأعلى درجة.\n"
                    f"⚠️ كل عضو جديد غادي يتـ **{'حظر' if bot_settings['raid_action'] == 'ban' else 'طرد'}** تلقائياً حتى يتسد الـ Lockdown.\n"
                    f"استعمل `/unlockdown` باش تسدو يدوياً قبل الوقت، ولا `/raidstatus` باش تشوف الحالة."
                ),
                color=discord.Color.dark_red(),
                timestamp=datetime.now()
            )
            try:
                await channel.send(content=mentions or None, embed=embed)
            except Exception as e:
                print(f"[ANTI-RAID] خطأ فـ بعث التنبيه: {e}")
    
        duration = bot_settings['raid_lockdown_duration_minutes'] if duration_minutes is None else duration_minutes
        if duration and duration > 0:
            async def _auto_revert():
                await asyncio.sleep(duration * 60)
                if raid_state.get(guild.id, {}).get("active"):
                    await end_raid_lockdown(guild, reason="انتهت المدة أوتوماتيكياً")
            state["revert_task"] = asyncio.create_task(_auto_revert())
    
        return True
    
    
    async def end_raid_lockdown(guild: discord.Guild, reason: str = "يدوي") -> bool:
        state = raid_state.get(guild.id)
        if not state or not state.get("active"):
            return False
    
        prev_level = state.get("previous_verification_level", discord.VerificationLevel.medium)
        try:
            await guild.edit(verification_level=prev_level, reason="Anti-Raid: رجوع للحالة العادية")
        except Exception as e:
            print(f"[ANTI-RAID] خطأ فـ رجوع verification level: {e}")
    
        state["active"] = False
        task = state.get("revert_task")
        if task and not task.done():
            task.cancel()
    
        channel = bot.get_channel(MOD_LOGS_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="✅ Anti-Raid: Lockdown تسد",
                description=f"**السبب:** {reason}\nverification level رجعت للحالة العادية.",
                color=discord.Color.green(),
                timestamp=datetime.now()
            )
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"[ANTI-RAID] خطأ فـ بعث التنبيه: {e}")
    
        return True
    
    
    async def _check_and_maybe_trigger_raid(guild: discord.Guild) -> bool:
        """كتزيد join جديد لتتبع الأعضاء الجداد، وكتشوف واش عدد الانضمامات
        الأخيرة وصل للعتبة (bot_settings['raid_join_threshold'] فـ bot_settings['raid_join_interval_seconds']).
        كترجع True إلا Lockdown تفعل دابا بالضبط (أول مرة)."""
        now = datetime.now()
        cutoff = now - timedelta(seconds=bot_settings['raid_join_interval_seconds'])
        joins = [t for t in recent_joins[guild.id] if t > cutoff]
        joins.append(now)
        recent_joins[guild.id] = joins
    
        if len(joins) >= bot_settings['raid_join_threshold']:
            state = raid_state.get(guild.id, {})
            if not state.get("active"):
                await trigger_raid_lockdown(
                    guild,
                    reason=f"🚨 {len(joins)} عضو دخلو فـ آخر {bot_settings['raid_join_interval_seconds']} ثانية (العتبة: {bot_settings['raid_join_threshold']})."
                )
                return True
        return False
    
    
    def _load_font(size: int, bold: bool = True):
        """كتحاول تلقى font جميلة، بالأولوية للفونط اللي حطينا فـ assets/fonts/
        (باش تخدم فأي بيئة، حتى Railway/python-slim اللي ماعندهاش فونطات النظام).
        إلا ماكانتش، كتجرب فونطات النظام، وإلا رجعت للـ font الافتراضي ديال Pillow."""
        project_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(project_dir, "assets", "fonts", "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()
    
    
    async def generate_welcome_card(member: discord.Member, member_count: int, returning: bool = False) -> Optional[io.BytesIO]:
        """كتصاوب صورة ترحيبية مخصصة (Welcome Card) فيها صورة العضو + اسمو + رقمو
        فالسيرفر. كترجع None إلا Pillow ماشي متوفرة أو وقع خطأ (باش الكود اللي
        كيسطاها يرجع للـ embed العادي بلا ما يطيح البوت)."""
        if not PIL_AVAILABLE or not bot_settings['welcome_card_enabled']:
            return None
    
        try:
            W, H = 1100, 420
            accent = WELCOME_CARD_ACCENT_RGB
            accent2 = WELCOME_CARD_ACCENT2_RGB
            dark = (13, 13, 18)
    
            # ═══════ الخلفية ═══════
            if WELCOME_CARD_BACKGROUND_PATH and os.path.exists(WELCOME_CARD_BACKGROUND_PATH):
                bg = Image.open(WELCOME_CARD_BACKGROUND_PATH).convert("RGB")
                bg = ImageOps.fit(bg, (W, H), method=Image.LANCZOS).convert("RGBA")
            else:
                # تدرج لوني قطري (diagonal) بين لونين، ممزوج مع الأسود باش يبان depth
                bg = Image.new("RGB", (W, H), dark)
                px = bg.load()
                diag = math.hypot(W, H)
                mix = 0.55
                for y in range(H):
                    for x in range(0, W, 2):
                        t = max(0, min(1, (x + y) / diag))
                        r = int((accent[0] * (1 - t) + accent2[0] * t) * mix + dark[0] * (1 - mix))
                        g = int((accent[1] * (1 - t) + accent2[1] * t) * mix + dark[1] * (1 - mix))
                        b = int((accent[2] * (1 - t) + accent2[2] * t) * mix + dark[2] * (1 - mix))
                        px[x, y] = (r, g, b)
                        if x + 1 < W:
                            px[x + 1, y] = (r, g, b)
                bg = bg.convert("RGBA")
    
                # نقط زخرفية خفيفة (texture) فوق الخلفية
                dots = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                ddraw = ImageDraw.Draw(dots)
                spacing = 34
                for yy in range(0, H, spacing):
                    for xx in range(0, W, spacing):
                        ddraw.ellipse((xx, yy, xx + 2, yy + 2), fill=(255, 255, 255, 18))
                bg = Image.alpha_composite(bg, dots)
    
            # طبقة غامقة شفافة باش النص يبان مزيان فوق أي خلفية
            overlay = Image.new("RGBA", (W, H), (0, 0, 0, 60))
            card = Image.alpha_composite(bg, overlay)
    
            # إطار (frame) خفيف مضيء حول الكارطة
            frame = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(frame).rounded_rectangle((6, 6, W - 6, H - 6), radius=28, outline=(255, 255, 255, 60), width=3)
            card = Image.alpha_composite(card, frame)
            draw = ImageDraw.Draw(card)
    
            # ═══════ صورة العضو (Avatar) دائرية مع ظل + حلقة بتدرج ═══════
            avatar_size = 200
            avatar_x, avatar_y = 70, (H - avatar_size) // 2
    
            # ظل ناعم تحت الصورة
            shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            pad = 14
            ImageDraw.Draw(shadow).ellipse(
                (avatar_x - pad, avatar_y - pad + 10, avatar_x + avatar_size + pad, avatar_y + avatar_size + pad + 10),
                fill=(0, 0, 0, 120)
            )
            shadow = shadow.filter(ImageFilter.GaussianBlur(12))
            card = Image.alpha_composite(card, shadow)
            draw = ImageDraw.Draw(card)
    
            # حلقة بتدرج لوني حول الصورة (رسم أقواس ملونة متدرجة)
            ring_pad = 10
            ring_box = (avatar_x - ring_pad, avatar_y - ring_pad, avatar_x + avatar_size + ring_pad, avatar_y + avatar_size + ring_pad)
            steps = 40
            for i in range(steps):
                t = i / steps
                r = int(accent[0] * (1 - t) + accent2[0] * t)
                g = int(accent[1] * (1 - t) + accent2[1] * t)
                b = int(accent[2] * (1 - t) + accent2[2] * t)
                start = 360 * (i / steps) - 90
                end = 360 * ((i + 1) / steps) - 90
                draw.arc(ring_box, start=start, end=end, fill=(r, g, b, 255), width=8)
            draw.ellipse(ring_box, outline=(255, 255, 255, 90), width=2)
    
            try:
                avatar_bytes = await member.display_avatar.replace(size=256, format="png").read()
                avatar_img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
            except Exception:
                avatar_img = Image.new("RGBA", (256, 256), accent + (255,))
            avatar_img = ImageOps.fit(avatar_img, (avatar_size, avatar_size), method=Image.LANCZOS)
    
            mask = Image.new("L", (avatar_size, avatar_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, avatar_size, avatar_size), fill=255)
            card.paste(avatar_img, (avatar_x, avatar_y), mask)
            draw = ImageDraw.Draw(card)
    
            # ═══════ badge صغيرة فوق الاسم ═══════
            text_x = avatar_x + avatar_size + 55
            badge_font = _load_font(20, bold=True)
            badge_text = "🔁 رجع للسيرفر" if returning else "✨ عضو جديد"
            bbox = draw.textbbox((0, 0), badge_text, font=badge_font)
            btw, bth = bbox[2] - bbox[0], bbox[3] - bbox[1]
            badge_pad_x, badge_pad_y = 18, 10
            badge_y = 78
            draw.rounded_rectangle(
                (text_x, badge_y, text_x + btw + badge_pad_x * 2, badge_y + bth + badge_pad_y * 2),
                radius=16, fill=(255, 255, 255, 235)
            )
            draw.text((text_x + badge_pad_x, badge_y + badge_pad_y - 2), badge_text, font=badge_font, fill=accent + (255,))
    
            # ═══════ اسم العضو (كبير، بارز، بظل خفيف) ═══════
            name_font = _load_font(56, bold=True)
            display_name = member.display_name
            if len(display_name) > 18:
                display_name = display_name[:17] + "…"
            name_y = badge_y + bth + badge_pad_y * 2 + 22
            draw.text((text_x + 2, name_y + 2), display_name, font=name_font, fill=(0, 0, 0, 90))
            draw.text((text_x, name_y), display_name, font=name_font, fill=(255, 255, 255, 255))
    
            # ═══════ subtitle (اسم السيرفر + رقم العضو) ═══════
            sub_font = _load_font(24, bold=False)
            sub_y = name_y + 70
            sub_text = f"{SERVER_NAME}  •  العضو رقم #{member_count}"
            draw.text((text_x, sub_y), sub_text, font=sub_font, fill=(230, 230, 235, 230))
    
            buffer = io.BytesIO()
            card.convert("RGB").save(buffer, format="PNG")
            buffer.seek(0)
            return buffer
        except Exception as e:
            print(f"[WELCOME_CARD] خطأ فـ صنع الصورة: {e}")
            return None
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
