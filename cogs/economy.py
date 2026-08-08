# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║ cogs/economy.py — 🪙 الدراهم + Shop                ║
═══════════════════════════════════════════════════════

هادا **قلب** النظام. كاع الألعاب كتعيّط عليه باش تعطي دراهم.

الأوامر:
 /balance — شحال عندك
 /daily   — مكافأة يومية
 /shop    — المتجر
 /richest — أغنى 10 أعضاء
 /givecoins — (Owner فقط) عطي/حيّد دراهم
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import random

from storage import JsonStore
import games_config as cfg


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def currency_word(amount: int) -> str:
    last_two = abs(int(amount)) % 100
    if last_two == 1:
        return cfg.CURRENCY_NAME
    if 2 <= last_two <= 10:
        return cfg.CURRENCY_NAME_PLURAL
    return cfg.CURRENCY_NAME


def fmt_coins(amount: int) -> str:
    return f"{amount:,} {currency_word(amount)}"


class Economy(commands.Cog):
    """نظام العملة — كاع الـ cogs الأخرى كتعيّط عليه بـ bot.get_cog("Economy")"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("economy.json", default={})

    async def cog_load(self):
        self.expire_purchases_loop.start()

    def cog_unload(self):
        self.expire_purchases_loop.cancel()

    @tasks.loop(minutes=15)
    async def expire_purchases_loop(self):
        """كل 15 دقيقة كتفحص الحوايج المشرية اللي عندها مدة صلاحية (لون، رول مخصص،
        VIP، Legend Tag...) وكتحيد الرول بصح ملي تخلص المدة — باش "المؤقت" يبقى
        مؤقت فعلاً وماشي دائم بالغلط."""
        now = datetime.now(timezone.utc)
        changed = False

        for guild_id_str, users in list(self.db.data.items()):
            try:
                guild_id = int(guild_id_str)
            except (TypeError, ValueError):
                continue
            guild = self.bot.get_guild(guild_id)

            for user_id_str, acc in list(users.items()):
                purchases = acc.get("purchases") or []
                if not purchases:
                    continue

                still_active = []
                for p in purchases:
                    expires = p.get("expires")
                    if not expires:
                        still_active.append(p)
                        continue
                    try:
                        expired = datetime.fromisoformat(expires) <= now
                    except Exception:
                        still_active.append(p)
                        continue

                    if not expired:
                        still_active.append(p)
                        continue

                    # الشراء خلصت مدتو — نحاولو نحيدو الرول بصح
                    changed = True
                    if guild is not None:
                        try:
                            member = guild.get_member(int(user_id_str)) or await guild.fetch_member(int(user_id_str))
                        except discord.NotFound:
                            member = None
                        except Exception:
                            member = None

                        role = guild.get_role(p.get("role_id", 0)) if p.get("role_id") else None
                        if member and role and role in member.roles:
                            try:
                                await member.remove_roles(role, reason="انتهت مدة الشراء من المتجر")
                            except Exception as e:
                                print(f"[SHOP EXPIRE] ⚠️ ماقدرتش نحيد {role} من {user_id_str}: {e}")
                    # كنسقطو الـ entry فكل الحالات (حتى لو الرول ماتحيدش) باش
                    # ما يبقاش يعاود يحاول كل 15 دقيقة لبلاصة

                if len(still_active) != len(purchases):
                    acc["purchases"] = still_active

        if changed:
            self.db.save()

    @expire_purchases_loop.before_loop
    async def before_expire_purchases_loop(self):
        await self.bot.wait_until_ready()

    # ════════════════════════════════════════════════
    # API داخلي
    # ════════════════════════════════════════════════

    def _acc(self, guild_id: int, user_id: int) -> dict:
        return self.db.user(
            guild_id,
            user_id,
            default={
                "coins": 0,
                "total_earned": 0,
                "daily_last": None,
                "daily_streak": 0,
                "earned_today": 0,
                "earned_today_date": _today_key(),
                "purchases": [],
            },
        )

    def get_balance(self, guild_id: int, user_id: int) -> int:
        return self._acc(guild_id, user_id).get("coins", 0)

    def currency_word(self, amount: int) -> str:
        return currency_word(amount)

    def fmt_coins(self, amount: int) -> str:
        return fmt_coins(amount)

    def add_coins(
        self,
        guild_id: int,
        user_id: int,
        amount: int,
        source: str = "game",
        respect_cap: bool = True,
    ) -> int:
        acc = self._acc(guild_id, user_id)

        today = _today_key()
        if acc.get("earned_today_date") != today:
            acc["earned_today"] = 0
            acc["earned_today_date"] = today

        granted = amount
        if respect_cap and amount > 0:
            remaining = cfg.COINS_DAILY_CAP - acc.get("earned_today", 0)
            granted = max(0, min(amount, remaining))

        acc["coins"] = max(0, acc.get("coins", 0) + granted)
        if granted > 0:
            acc["total_earned"] = acc.get("total_earned", 0) + granted
            if respect_cap:
                acc["earned_today"] = acc.get("earned_today", 0) + granted

        self.db.save()
        return granted

    def spend(self, guild_id: int, user_id: int, amount: int) -> bool:
        acc = self._acc(guild_id, user_id)
        if acc.get("coins", 0) < amount:
            return False
        acc["coins"] -= amount
        self.db.save()
        return True

    def daily_remaining(self, guild_id: int, user_id: int) -> int:
        acc = self._acc(guild_id, user_id)
        if acc.get("earned_today_date") != _today_key():
            return cfg.COINS_DAILY_CAP
        return max(0, cfg.COINS_DAILY_CAP - acc.get("earned_today", 0))

    async def reward(self, interaction_or_ctx, amount: int, source: str = "game") -> int:
        guild = interaction_or_ctx.guild
        user = getattr(interaction_or_ctx, "user", None) or interaction_or_ctx.author
        if guild is None:
            return 0
        amount = self._apply_coins_boost(guild.id, user.id, amount)
        return self.add_coins(guild.id, user.id, amount, source=source)

    def _apply_coins_boost(self, guild_id: int, user_id: int, amount: int) -> int:
        """إلا كان عند العضو بوست فلوس فعّال (مشرِي من المتجر)، كتضاعف المبلغ. كتحيد
        البوست أوتوماتيكياً إلا كانت مدتو خلصات."""
        if amount <= 0:
            return amount
        acc = self._acc(guild_id, user_id)
        expires = acc.get("coins_boost_expires")
        if not expires:
            return amount
        try:
            if datetime.now(timezone.utc) <= datetime.fromisoformat(expires):
                multiplier = acc.get("coins_boost_multiplier", 1.0)
                return int(round(amount * multiplier))
            acc.pop("coins_boost_multiplier", None)
            acc.pop("coins_boost_expires", None)
            self.db.save()
        except Exception:
            pass
        return amount

    # ════════════════════════════════════════════════
    # أوامر /balance /daily /richest
    # ════════════════════════════════════════════════

    @commands.hybrid_command(
        name="balance",
        aliases=["bal", "فلوسي"],
        description="شوف شحال عندك من الدراهم 🪙",
    )
    @app_commands.describe(member="العضو اللي بغيتي تشوف الرصيد ديالو (اختياري)")
    async def balance_cmd(
        self, ctx: commands.Context, member: Optional[discord.Member] = None
    ):
        target = member or ctx.author
        acc = self._acc(ctx.guild.id, target.id)

        embed = discord.Embed(
            title=f"{cfg.CURRENCY_EMOJI} الرصيد ديال {target.display_name}",
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="💰 الرصيد الحالي",
            value=f"**{acc['coins']:,}** {currency_word(acc['coins'])}",
            inline=True,
        )
        embed.add_field(
            name="📈 المجموع من البداية",
            value=f"**{acc.get('total_earned', 0):,}**",
            inline=True,
        )
        embed.add_field(
            name="🔥 Streak ديال /daily",
            value=f"**{acc.get('daily_streak', 0)}** أيام",
            inline=True,
        )

        remaining = self.daily_remaining(ctx.guild.id, target.id)
        embed.add_field(
            name="📊 السقف اليومي",
            value=f"باقي ليك **{remaining}** / {cfg.COINS_DAILY_CAP} اليوم",
            inline=False,
        )

        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="استعمل /shop باش تشري بيهم")
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="daily",
        aliases=["يومي"],
        description="خود المكافأة اليومية ديالك 🪙",
    )
    async def daily_cmd(self, ctx: commands.Context):
        acc = self._acc(ctx.guild.id, ctx.author.id)
        now = datetime.now(timezone.utc)

        last = acc.get("daily_last")
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                elapsed = now - last_dt
                if elapsed < timedelta(hours=cfg.COOLDOWN_DAILY_HOURS):
                    ready_at = last_dt + timedelta(hours=cfg.COOLDOWN_DAILY_HOURS)
                    await ctx.send(
                        f"⏳ ماشي دابا خويا — رجع <t:{int(ready_at.timestamp())}:R> باش تاخد اليومية.",
                        ephemeral=True,
                    )
                    return
                if elapsed > timedelta(hours=48):
                    acc["daily_streak"] = 0
            except (ValueError, TypeError):
                pass

        acc["daily_streak"] = acc.get("daily_streak", 0) + 1
        bonus = min(
            cfg.COINS_DAILY_STREAK_BONUS * (acc["daily_streak"] - 1),
            cfg.COINS_DAILY_STREAK_MAX,
        )
        total = cfg.COINS_DAILY + bonus

        acc["daily_last"] = now.isoformat()
        self.db.save()

        self.add_coins(
            ctx.guild.id,
            ctx.author.id,
            total,
            source="daily",
            respect_cap=False,
        )

        embed = discord.Embed(
            title="🎁 المكافأة اليومية",
            description=f"خديتي **{total}** {currency_word(total)} {cfg.CURRENCY_EMOJI}",
            color=discord.Color.green(),
        )
        if bonus > 0:
            embed.add_field(
                name="🔥 بونوس Streak",
                value=f"+{bonus} (نهار {acc['daily_streak']} متتالي)",
                inline=False,
            )
        embed.add_field(
            name="💰 الرصيد الجديد",
            value=f"**{self.get_balance(ctx.guild.id, ctx.author.id):,}**",
            inline=False,
        )
        embed.set_footer(text="رجع غدا باش تكبّر الـ streak!")
        await ctx.send(embed=embed)

    def build_richest_embed(self, guild: discord.Guild) -> discord.Embed:
        guild_data = self.db.guild(guild.id)
        ranked = sorted(
            guild_data.items(),
            key=lambda kv: kv[1].get("coins", 0),
            reverse=True,
        )[:10]

        if not ranked:
            return discord.Embed(
                title=f"{cfg.CURRENCY_EMOJI} أغنى الأعضاء",
                description="📭 مازال حتى واحد ماعندو دراهم. كون نتا الأول — دير `/daily`!",
                color=discord.Color.gold(),
            )

        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, (uid, data) in enumerate(ranked):
            member = guild.get_member(int(uid))
            name = member.display_name if member else f"عضو خارج ({uid})"
            prefix = medals[i] if i < 3 else f"`#{i + 1}`"
            lines.append(
                f"{prefix} **{name}** — {data.get('coins', 0):,} {cfg.CURRENCY_EMOJI}"
            )

        embed = discord.Embed(
            title=f"{cfg.CURRENCY_EMOJI} أغنى الأعضاء",
            description="\n".join(lines),
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"{guild.name} | Mini Games")
        return embed

    def admin_give(self, guild: discord.Guild, member: discord.Member, amount: int) -> str:
        self.add_coins(guild.id, member.id, amount, source="admin", respect_cap=False)
        verb = "تزادو لـ" if amount >= 0 else "تحيدو من"
        return (
            f"✅ {abs(amount)} {currency_word(amount)} {verb} {member.mention}\n"
            f"الرصيد الجديد: **{self.get_balance(guild.id, member.id):,}** "
            f"{cfg.CURRENCY_EMOJI}"
        )

    # ════════════════════════════════════════════════
    # SHOP
    # ════════════════════════════════════════════════

    @commands.hybrid_command(
        name="shop", aliases=["متجر"], description="المتجر — شري بالدراهم 🛒"
    )
    async def shop_cmd(self, ctx: commands.Context):
        balance = self.get_balance(ctx.guild.id, ctx.author.id)

        embed = discord.Embed(
            title="🛒 المتجر",
            description=(
                f"الرصيد ديالك: **{balance:,}** {cfg.CURRENCY_EMOJI}\n"
                "اختار شي حاجة من اللائحة تحت."
            ),
            color=discord.Color.blurple(),
        )

        for item in cfg.SHOP_ITEMS:
            if item["type"] == "temp_role" and not item.get("role_id"):
                continue
            affordable = "✅" if balance >= item["price"] else "❌"
            embed.add_field(
                name=(
                    f"{item['emoji']} {item['name']} — "
                    f"{item['price']:,} {cfg.CURRENCY_EMOJI} {affordable}"
                ),
                value=item["description"],
                inline=False,
            )

        embed.set_footer(text="ربح الدراهم من الألعاب فـ #games-panel ولا /daily")
        await ctx.send(embed=embed, view=ShopView(self, ctx.author))

    # ════════════════════════════════════════════════
    # أمر givecoins — Owner فقط
    # ════════════════════════════════════════════════

    @commands.hybrid_command(
        name="givecoins",
        description="(Owner فقط) عطي/حيّد دراهم لعضو",
    )
    @app_commands.describe(
        member="العضو اللي بغيتي تعطيه الفلوس",
        amount="العدد (موجب = تزاد، سالب = يتحيد)",
    )
    async def givecoins_cmd(
        self, ctx: commands.Context, member: discord.Member, amount: int
    ):
        # Owner فقط (OWNER_ID كيوصل عبر bot.gg، البريدج المعرف فـ ai_bot.py)
        OWNER_ID = getattr(self.bot, "gg", {}).get("OWNER_ID")

        if not OWNER_ID or ctx.author.id != OWNER_ID:
            # ما نخرجو حتى جواب علني: Slash = ephemeral، Prefix fallback = DM.
            if ctx.interaction:
                await ctx.send(
                    "❌ هاد الأمر خاص غير بـ Owner الحقيقي للسيرفر.",
                    ephemeral=True,
                )
            else:
                try:
                    await ctx.author.send("❌ هاد الأمر خاص غير بـ Owner الحقيقي للسيرفر.")
                except discord.HTTPException:
                    pass
            return

        # طبّق التغيير فالفلوس، ولكن بلا حتى رسالة عامة فالسيرفر.
        self.admin_give(ctx.guild, member, amount)
        new_balance = self.get_balance(ctx.guild.id, member.id)

        # غير العضو المستفيد كيتوصل بإشعار خاص فـ DM.
        if amount >= 0:
            dm_text = (
                f"💰 وصلك **{amount:,}** {currency_word(amount)} {cfg.CURRENCY_EMOJI}!\n"
                f"الرصيد ديالك دابا: **{new_balance:,}** {cfg.CURRENCY_EMOJI}"
            )
        else:
            dm_text = (
                f"💸 تحيدو من رصيدك **{abs(amount):,}** {currency_word(amount)} {cfg.CURRENCY_EMOJI}.\n"
                f"الرصيد ديالك دابا: **{new_balance:,}** {cfg.CURRENCY_EMOJI}"
            )

        dm_sent = True
        try:
            await member.send(dm_text)
        except (discord.Forbidden, discord.HTTPException):
            dm_sent = False

        # تأكيد سري للـ Owner فقط؛ ما كيبان لحتى واحد آخر فالسيرفر.
        owner_confirmation = (
            f"✅ تم تعديل رصيد {member.mention} بسرية. "
            f"الرصيد الجديد: **{new_balance:,}** {cfg.CURRENCY_EMOJI}"
        )
        if not dm_sent:
            owner_confirmation += "\n⚠️ العضو ساد الـ DM، لذلك ما قدرش يتوصل بالإشعار الخاص."

        if ctx.interaction:
            await ctx.send(owner_confirmation, ephemeral=True)
        else:
            try:
                await ctx.author.send(owner_confirmation)
            except discord.HTTPException:
                pass


class ShopView(discord.ui.View):
    def __init__(self, cog: "Economy", user: discord.abc.User):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user

        options = []
        for item in cfg.SHOP_ITEMS:
            if item["type"] == "temp_role" and not item.get("role_id"):
                continue
            options.append(
                discord.SelectOption(
                    label=f"{item['name']} — {item['price']} 🪙",
                    value=item["id"],
                    emoji=item["emoji"],
                    description=item["description"][:100],
                )
            )
        if options:
            self.add_item(ShopSelect(cog, user, options))


class ShopSelect(discord.ui.Select):
    def __init__(self, cog: "Economy", user: discord.abc.User, options: list):
        super().__init__(placeholder="🛒 اختار شنو بغيتي تشري...", options=options)
        self.cog = cog
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ هاد المتجر ماشي ديالك — دير `/shop` نتا.",
                ephemeral=True,
            )
            return

        item = next((i for i in cfg.SHOP_ITEMS if i["id"] == self.values[0]), None)
        if not item:
            await interaction.response.send_message(
                "❌ هاد الحاجة ماكايناش.", ephemeral=True
            )
            return

        balance = self.cog.get_balance(interaction.guild.id, interaction.user.id)
        if balance < item["price"]:
            await interaction.response.send_message(
                f"❌ ماكافيوش — خاصك **{item['price'] - balance:,}** "
                f"{cfg.CURRENCY_EMOJI} زيادة.",
                ephemeral=True,
            )
            return

        if item["type"] == "role_color":
            await interaction.response.send_message(
                f"🎨 اختار اللون اللي بغيتي "
                f"({item['price']} {cfg.CURRENCY_EMOJI}):",
                view=ColorPickView(self.cog, interaction.user, item),
                ephemeral=True,
            )
            return

        if item["type"] == "custom_role":
            await interaction.response.send_modal(CustomRoleModal(self.cog, item))
            return

        await interaction.response.defer(ephemeral=True)
        ok, msg = await apply_purchase(
            self.cog, interaction.guild, interaction.user, item
        )
        if ok:
            self.cog.spend(interaction.guild.id, interaction.user.id, item["price"])
            new_balance = self.cog.get_balance(
                interaction.guild.id, interaction.user.id
            )
            await interaction.followup.send(
                f"✅ {msg}\n💰 الرصيد الجديد: **{new_balance:,}** {cfg.CURRENCY_EMOJI}",
                ephemeral=True,
            )
        else:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)


class ColorPickView(discord.ui.View):
    def __init__(self, cog: "Economy", user: discord.abc.User, item: dict):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.item = item

        options = [
            discord.SelectOption(label=name, value=str(value))
            for name, value in cfg.SHOP_COLORS.items()
        ]
        select = discord.ui.Select(placeholder="🎨 اختار اللون...", options=options)
        select.callback = self.on_pick
        self.add_item(select)
        self.select = select

    async def on_pick(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ ماشي ديالك.", ephemeral=True
            )
            return
        await interaction.response.defer(ephemeral=True)
        color_value = int(self.select.values[0])
        item = dict(self.item)
        item["color"] = color_value
        ok, msg = await apply_purchase(
            self.cog, interaction.guild, interaction.user, item
        )
        if ok:
            self.cog.spend(interaction.guild.id, interaction.user.id, item["price"])
            await interaction.followup.send(f"✅ {msg}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)


class CustomRoleModal(discord.ui.Modal, title="🏷️ الرول المخصص ديالك"):
    role_name = discord.ui.TextInput(
        label="سمية الرول", max_length=32, placeholder="مثلا: ملك السيرفر"
    )

    def __init__(self, cog: "Economy", item: dict):
        super().__init__()
        self.cog = cog
        self.item = item

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        item = dict(self.item)
        item["custom_name"] = str(self.role_name.value)
        ok, msg = await apply_purchase(
            self.cog, interaction.guild, interaction.user, item
        )
        if ok:
            self.cog.spend(interaction.guild.id, interaction.user.id, item["price"])
            await interaction.followup.send(f"✅ {msg}", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ {msg}", ephemeral=True)


# ═══════════════════════════════════════════════════════
# تطبيق الشراء — الربط مع XP / الرولات
# ═══════════════════════════════════════════════════════

async def apply_purchase(
    cog: "Economy", guild: discord.Guild, user: discord.Member, item: dict
) -> Tuple[bool, str]:
    bot = cog.bot

    # XP Boost
    if item["type"] == "xp_boost":
        bridge = getattr(bot, "gg", None)
        if not bridge or "get_user_level_data" not in bridge:
            return False, "نظام الـ XP ماشي مربوط (bot.gg ناقص) — شوف ai_bot.py."

        from datetime import datetime as _dt, timedelta as _td

        try:
            data = bridge["get_user_level_data"](guild.id, user.id)
            data["xp_boost_multiplier"] = item.get("multiplier", 2.0)
            data["xp_boost_expires"] = (
                _dt.now() + _td(hours=item.get("duration_hours", 1))
            ).isoformat()
            bridge["save_levels"]()
            return True, (
                f"⚡ XP Boost **{item.get('multiplier', 2.0)}x** مفعّل لمدة "
                f"**{item.get('duration_hours', 1)} ساعة**!"
            )
        except Exception as e:
            return False, f"خطأ فـ تفعيل الـ boost: {e}"

    # لون شخصي مؤقت
    if item["type"] == "role_color":
        try:
            role_name = f"🎨 {user.display_name}"
            existing = discord.utils.get(guild.roles, name=role_name)
            if existing:
                await existing.edit(colour=discord.Colour(item["color"]))
                role = existing
            else:
                role = await guild.create_role(
                    name=role_name,
                    colour=discord.Colour(item["color"]),
                    reason=f"شراء من المتجر — {user}",
                )

            if cfg.SHOP_COLOR_ROLE_ANCHOR_ID:
                anchor = guild.get_role(cfg.SHOP_COLOR_ROLE_ANCHOR_ID)
                if anchor:
                    await role.edit(position=max(1, anchor.position - 1))

            await user.add_roles(role, reason="شراء لون شخصي")
            _record_purchase(
                cog, guild.id, user.id, item, role.id, days=item.get("duration_days", 7)
            )
            return True, f"🎨 اللون مفعّل لمدة **{item.get('duration_days', 7)} أيام**!"
        except discord.Forbidden:
            return False, "ماعنديش صلاحية Manage Roles — قول للأدمين."
        except Exception as e:
            return False, f"خطأ: {e}"

    # لون شخصي دائم
    if item["type"] == "role_color_perm":
        try:
            role_name = f"🎨 {user.display_name}"
            existing = discord.utils.get(guild.roles, name=role_name)
            if existing:
                await existing.edit(colour=discord.Colour.random())
                role = existing
            else:
                role = await guild.create_role(
                    name=role_name,
                    colour=discord.Colour.random(),
                    reason=f"شراء لون دائم — {user}",
                )

            if cfg.SHOP_COLOR_ROLE_ANCHOR_ID:
                anchor = guild.get_role(cfg.SHOP_COLOR_ROLE_ANCHOR_ID)
                if anchor:
                    await role.edit(position=max(1, anchor.position - 1))

            await user.add_roles(role, reason="شراء لون دائم")
            _record_purchase(cog, guild.id, user.id, item, role.id, days=0)
            return True, "♾️ لون شخصي دائم تعمّد ليك!"
        except discord.Forbidden:
            return False, "ماعنديش صلاحية Manage Roles."
        except Exception as e:
            return False, f"خطأ: {e}"

    # رول مخصص
    if item["type"] == "custom_role":
        try:
            role = await guild.create_role(
                name=item["custom_name"],
                colour=discord.Colour.random(),
                reason=f"شراء رول مخصص — {user}",
            )
            await user.add_roles(role, reason="شراء رول مخصص")
            _record_purchase(
                cog,
                guild.id,
                user.id,
                item,
                role.id,
                days=item.get("duration_days", 30),
            )
            return True, (
                f"🏷️ الرول **{item['custom_name']}** تصاوب وتعطى ليك "
                f"لمدة **{item.get('duration_days', 30)} يوم**!"
            )
        except discord.Forbidden:
            return False, "ماعنديش صلاحية Manage Roles."
        except Exception as e:
            return False, f"خطأ: {e}"

    # رول مؤقت (VIP)
    if item["type"] == "temp_role":
        role = guild.get_role(item.get("role_id", 0))
        if not role:
            return False, "هاد الرول ماكاينش (role_id ماشي مزبوط فالـ config)."
        try:
            await user.add_roles(role, reason="شراء رول مؤقت")
            _record_purchase(
                cog,
                guild.id,
                user.id,
                item,
                role.id,
                days=item.get("duration_days", 14),
            )
            return True, (
                f"💎 الرول {role.mention} تعطى ليك لمدة "
                f"**{item.get('duration_days', 14)} يوم**!"
            )
        except discord.Forbidden:
            return False, "ماعنديش صلاحية Manage Roles."
        except Exception as e:
            return False, f"خطأ: {e}"

    # Legend Tag
    if item["type"] == "legend_tag":
        try:
            role_name = "👑 LEGEND"
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                role = await guild.create_role(
                    name=role_name,
                    colour=discord.Colour.gold(),
                    hoist=False,
                    mentionable=False,
                    reason="Legend Tag من المتجر",
                )
            await user.add_roles(role, reason="Legend Tag purchase")
            _record_purchase(
                cog, guild.id, user.id, item, role.id, days=item.get("duration_days", 7)
            )
            return True, "👑 خديتي Legend Tag لمدة أسبوع!"
        except discord.Forbidden:
            return False, "ماعنديش صلاحية Manage Roles."
        except Exception as e:
            return False, f"خطأ: {e}"

    # بوست فلوس مؤقت
    if item["type"] == "coins_boost":
        acc = cog._acc(guild.id, user.id)
        acc["coins_boost_multiplier"] = item.get("multiplier", 1.5)
        acc["coins_boost_expires"] = (
            datetime.now(timezone.utc) + timedelta(hours=item.get("duration_hours", 1))
        ).isoformat()
        cog.db.save()
        return True, (
            f"💰 بوست الفلوس **{item.get('multiplier', 1.5)}x** مفعّل لمدة "
            f"**{item.get('duration_hours', 1)} ساعة**!"
        )

    # حيّد آخر تحذير
    if item["type"] == "warn_removal":
        mod_cog = bot.get_cog("Moderation")
        if not mod_cog or not hasattr(mod_cog, "remove_last_warning"):
            return False, "نظام التحذيرات ماشي مربوط دابا — قول للأدمين."
        removed = mod_cog.remove_last_warning(str(user.id))
        if not removed:
            return False, "ماعندكش شي تحذير باش نحيدو — ماخصكش تشري هاد الحاجة."
        return True, "🛡️ تحيد آخر تحذير ديالك!"

    # شوتاوت عمومي
    if item["type"] == "shoutout":
        channel_id = getattr(cfg, "SHOP_SHOUTOUT_CHANNEL_ID", 0) or getattr(
            cfg, "GAMES_PANEL_CHANNEL_ID", 0
        )
        channel = guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return False, "شانيل الشوتاوت ماشي معمّرة (SHOP_SHOUTOUT_CHANNEL_ID) — قول للأدمين."
        embed = discord.Embed(
            title="📣 شوتاوت!",
            description=f"{user.mention} خدام ديالو زوين وشرا شوتاوت باش الكل يشوفو! 🎉",
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"{cfg.CURRENCY_NAME_PLURAL} ديال المتجر")
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            return False, "ماعنديش صلاحية نبعث فهاد الشانيل — قول للأدمين."
        return True, f"📣 الشوتاوت ديالك تبعث فـ <#{channel_id}>!"

    # صندوق الحظ — نتيجة عشوائية
    if item["type"] == "mystery_box":
        outcomes = item.get("outcomes") or []
        if not outcomes:
            return False, "هاد الصندوق ماشي معمّر (outcomes فارغين) — قول للأدمين."
        pick = random.choices(
            outcomes, weights=[o.get("weight", 1) for o in outcomes], k=1
        )[0]
        coins_won = pick.get("coins", 0)
        cog.add_coins(guild.id, user.id, coins_won, source="mystery_box", respect_cap=False)
        label = pick.get("label", f"{coins_won} 🪙")
        return True, f"🎁 حليتي الصندوق ولقيتي: **{label}**!"

    return False, "نوع الحاجة ماشي معروف (ولا مازال ماخدامش دابا)."


def _record_purchase(
    cog: "Economy", guild_id: int, user_id: int, item: dict, role_id: int, days: int
):
    acc = cog._acc(guild_id, user_id)
    acc.setdefault("purchases", []).append(
        {
            "item_id": item["id"],
            "role_id": role_id,
            "expires": None
            if days <= 0
            else (datetime.now(timezone.utc) + timedelta(days=days)).isoformat(),
        }
    )
    cog.db.save()


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
