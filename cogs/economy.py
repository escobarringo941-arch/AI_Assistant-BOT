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
        # حسابات النظام المركزي: Treasury / Jackpot / Events / Burn / Bank / Ledger.
        self.system_db = JsonStore("economy_system.json", default={})

    async def cog_load(self):
        self.expire_purchases_loop.start()
        self.economy_stats_loop.start()
        self.loan_collection_loop.start()
        # Persistent View: ما كيزيد حتى Slash Command جديد.
        self.bot.add_view(EconomyBankPanelView(self))

    def cog_unload(self):
        self.expire_purchases_loop.cancel()
        self.economy_stats_loop.cancel()
        self.loan_collection_loop.cancel()

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
    # Real Economy — Treasury / Jackpot / Bank / Ledger
    # ════════════════════════════════════════════════

    def _system(self, guild_id: int) -> dict:
        """الحساب المركزي ديال السيرفر. ماشي فلوس لاعب؛ هادي دفاتر الاقتصاد."""
        gid = str(guild_id)
        root = self.system_db.data.setdefault(gid, {})
        defaults = {
            "treasury": 0,
            "jackpot": 0,
            "events": 0,
            "burned": 0,
            "total_gambling_lost": 0,
            "total_shop_spent": 0,
            "total_jackpot_paid": 0,
            "bank_accounts": {},
            "loans": {},
            "credit_scores": {},
            "loan_next_id": 1,
            "transactions": [],
            "next_tx_id": 1,
            "stats_message_id": None,
        }
        for key, value in defaults.items():
            if key not in root:
                root[key] = value.copy() if isinstance(value, (dict, list)) else value
        return root

    def get_bank_balance(self, guild_id: int, user_id: int) -> int:
        sys = self._system(guild_id)
        return int(sys["bank_accounts"].get(str(user_id), 0) or 0)

    def _set_bank_balance(self, guild_id: int, user_id: int, amount: int):
        sys = self._system(guild_id)
        sys["bank_accounts"][str(user_id)] = max(0, int(amount))
        self.system_db.save()

    def _record_transaction(
        self,
        guild_id: int,
        *,
        user_id: Optional[int],
        kind: str,
        amount: int,
        source: str,
        description: str,
        splits: Optional[dict] = None,
    ) -> int:
        sys = self._system(guild_id)
        tx_id = int(sys.get("next_tx_id", 1) or 1)
        sys["next_tx_id"] = tx_id + 1
        sys["transactions"].append({
            "id": tx_id,
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "kind": kind,
            "amount": int(amount),
            "source": source,
            "description": description,
            "splits": splits or {},
        })
        limit = int(getattr(cfg, "ECONOMY_TRANSACTION_HISTORY_LIMIT", 500) or 500)
        if len(sys["transactions"]) > limit:
            sys["transactions"] = sys["transactions"][-limit:]
        self.system_db.save()
        return tx_id

    def get_user_transactions(self, guild_id: int, user_id: int, limit: int = 10) -> list:
        txs = [
            tx for tx in self._system(guild_id).get("transactions", [])
            if int(tx.get("user_id") or 0) == int(user_id)
        ]
        return txs[-limit:][::-1]

    async def _economy_log(
        self,
        guild: discord.Guild,
        title: str,
        description: str,
        color: discord.Color = discord.Color.blurple(),
    ):
        channel_id = int(getattr(cfg, "ECONOMY_LOGS_CHANNEL_ID", 0) or 0)
        channel = guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"{guild.name} | Economy Ledger")
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def route_gambling_loss(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        amount: int,
        game: str,
    ) -> dict:
        """الرهان راه تخصم من قبل. هنا غير كنقسمو الخسارة الحقيقية بلا خصم ثاني."""
        amount = max(0, int(amount))
        if amount <= 0:
            return {"treasury": 0, "jackpot": 0, "burned": 0}

        treasury = amount * int(getattr(cfg, "GAMBLING_LOSS_TREASURY_PERCENT", 60)) // 100
        jackpot = amount * int(getattr(cfg, "GAMBLING_LOSS_JACKPOT_PERCENT", 25)) // 100
        burned = amount - treasury - jackpot

        sys = self._system(guild.id)
        sys["treasury"] += treasury
        sys["jackpot"] += jackpot
        sys["burned"] += burned
        sys["total_gambling_lost"] += amount
        splits = {"treasury": treasury, "jackpot": jackpot, "burned": burned}
        tx_id = self._record_transaction(
            guild.id,
            user_id=user.id,
            kind="gambling_loss",
            amount=amount,
            source=game,
            description=f"خسارة رهان فـ {game}",
            splits=splits,
        )

        await self._economy_log(
            guild,
            f"🎰 خسارة رهان — TX #{tx_id}",
            (
                f"**العضو:** {user.mention}\n"
                f"**اللعبة:** `{game}`\n"
                f"**الخسارة:** **{amount:,}** {cfg.CURRENCY_EMOJI}\n\n"
                f"🏛️ Treasury: **+{treasury:,}**\n"
                f"🎰 Global Jackpot: **+{jackpot:,}**\n"
                f"🔥 Burned: **{burned:,}**"
            ),
            discord.Color.red(),
        )
        # باش الاقتصاد العام يبان متحدث فوراً، ما نستناوش loop ديال الدقيقتين.
        await self.refresh_economy_stats(guild)
        return splits

    async def route_shop_purchase(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        amount: int,
        item: dict,
    ) -> dict:
        """الثمن راه تخصم من اللاعب. هنا كنقسموه على Treasury / Events / Burn."""
        amount = max(0, int(amount))
        treasury = amount * int(getattr(cfg, "SHOP_TREASURY_PERCENT", 50)) // 100
        events = amount * int(getattr(cfg, "SHOP_EVENTS_PERCENT", 10)) // 100
        burned = amount - treasury - events

        sys = self._system(guild.id)
        sys["treasury"] += treasury
        sys["events"] += events
        sys["burned"] += burned
        sys["total_shop_spent"] += amount
        splits = {"treasury": treasury, "events": events, "burned": burned}
        tx_id = self._record_transaction(
            guild.id,
            user_id=user.id,
            kind="shop_purchase",
            amount=amount,
            source=item.get("id", "shop"),
            description=f"شراء: {item.get('name', item.get('id', 'Shop Item'))}",
            splits=splits,
        )

        await self._economy_log(
            guild,
            f"🛒 شراء من المتجر — TX #{tx_id}",
            (
                f"**العضو:** {user.mention}\n"
                f"**المنتج:** {item.get('emoji', '🛒')} **{item.get('name', item.get('id', 'Item'))}**\n"
                f"**الثمن:** **{amount:,}** {cfg.CURRENCY_EMOJI}\n\n"
                f"🏛️ Treasury: **+{treasury:,}**\n"
                f"🎉 Events Fund: **+{events:,}**\n"
                f"🔥 Burned: **{burned:,}**"
            ),
            discord.Color.gold(),
        )
        await self.refresh_economy_stats(guild)
        return splits

    async def claim_global_jackpot(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        game: str,
    ) -> int:
        """كيحوّل Jackpot Pool كامل للاعب عند Jackpot حقيقي، بلا خلق فلوس جديدة."""
        if not getattr(cfg, "GLOBAL_JACKPOT_ENABLED", True):
            return 0
        sys = self._system(guild.id)
        prize = max(0, int(sys.get("jackpot", 0) or 0))
        if prize <= 0:
            return 0

        # نصفر الـPool قبل أول await: مايمكنش نفس الجاكبوت يتصرف لجوج فنفس اللحظة.
        sys["jackpot"] = 0
        sys["total_jackpot_paid"] += prize
        self.system_db.save()
        granted = self.add_coins(
            guild.id, user.id, prize, source=f"global_jackpot:{game}",
            respect_cap=False, count_as_earned=True
        )
        tx_id = self._record_transaction(
            guild.id,
            user_id=user.id,
            kind="jackpot_payout",
            amount=granted,
            source=game,
            description=f"Global Jackpot من {game}",
        )
        await self._economy_log(
            guild,
            f"🏆 GLOBAL JACKPOT — TX #{tx_id}",
            (
                f"# 🎉 {user.mention} ضرب الـGlobal Jackpot!\n"
                f"**اللعبة:** `{game}`\n"
                f"**الجائزة من الـPool:** **{granted:,}** {cfg.CURRENCY_EMOJI}\n"
                f"🎰 الـJackpot Pool رجع دابا لـ **0**."
            ),
            discord.Color.gold(),
        )
        await self.refresh_economy_stats(guild)
        return granted

    # ════════════════════════════════════════════════
    # Loans / Credit Score
    # ════════════════════════════════════════════════

    def get_credit_score(self, guild_id: int, user_id: int) -> int:
        sys = self._system(guild_id)
        default = int(getattr(cfg, "LOAN_DEFAULT_CREDIT_SCORE", 50) or 50)
        score = int(sys["credit_scores"].get(str(user_id), default) or default)
        return max(0, min(100, score))

    def _set_credit_score(self, guild_id: int, user_id: int, score: int):
        sys = self._system(guild_id)
        sys["credit_scores"][str(user_id)] = max(0, min(100, int(score)))
        self.system_db.save()

    def get_user_level(self, guild_id: int, user_id: int) -> int:
        """Level الحقيقي من ai_bot عبر bot.gg bridge. Fallback=0 إلا ماكانش الربط."""
        bridge = getattr(self.bot, "gg", None) or {}
        getter = bridge.get("get_user_level_data")
        if not callable(getter):
            return 0
        try:
            data = getter(guild_id, user_id) or {}
            return max(0, int(data.get("level", 0) or 0))
        except Exception:
            return 0


    def get_level_perks(self, guild_id: int, user_id: int) -> dict:
        """كيجيب نفس source of truth ديال Level benefits من ai_bot."""
        level = self.get_user_level(guild_id, user_id)
        bridge = getattr(self.bot, "gg", None) or {}
        getter = bridge.get("get_level_perks")
        if callable(getter):
            try:
                return dict(getter(level) or {})
            except Exception:
                pass
        return {
            "threshold": 0,
            "name": "👤 Member",
            "shop_discount_percent": 0,
            "daily_bonus_percent": 0,
            "loan_base": 200,
            "loan_interest": 16,
            "loan_days": 2,
            "feature": "—",
        }

    def get_shop_discount_percent(self, guild_id: int, user_id: int) -> int:
        perks = self.get_level_perks(guild_id, user_id)
        return max(0, min(50, int(perks.get("shop_discount_percent", 0) or 0)))

    def get_shop_price(self, guild_id: int, user_id: int, base_price: int) -> int:
        base_price = max(0, int(base_price))
        if base_price <= 0:
            return 0
        discount = self.get_shop_discount_percent(guild_id, user_id)
        # ceil-like safe integer: المنتوج ما يولي 0 بالغلط.
        discounted = (base_price * (100 - discount) + 99) // 100
        return max(1, discounted)

    async def grant_level_daily_bonus(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        base_daily_amount: int,
    ) -> tuple:
        """Level Daily Bonus كيتخلص من Treasury، يعني ما كيخلقش فلوس جديدة."""
        perks = self.get_level_perks(guild.id, user.id)
        pct = max(0, int(perks.get("daily_bonus_percent", 0) or 0))
        wanted = max(0, int(base_daily_amount) * pct // 100)
        if wanted <= 0:
            return 0, pct, 0

        sys = self._system(guild.id)
        available = max(0, int(sys.get("treasury", 0) or 0))
        granted = min(wanted, available)
        if granted <= 0:
            return 0, pct, wanted

        sys["treasury"] -= granted
        self.system_db.save()
        tx_id = self._record_transaction(
            guild.id,
            user_id=user.id,
            kind="level_daily_bonus",
            amount=granted,
            source=f"level:{self.get_user_level(guild.id, user.id)}",
            description=f"Level Daily Bonus +{pct}%",
            splits={"treasury": -granted},
        )
        await self._economy_log(
            guild,
            f"🎁 Level Daily Bonus — TX #{tx_id}",
            (
                f"**العضو:** {user.mention}\n"
                f"⭐ Level: **{self.get_user_level(guild.id, user.id)}**\n"
                f"**Bonus:** **+{granted:,}** {cfg.CURRENCY_EMOJI} ({pct}%)\n"
                f"🏛️ ممول من Treasury"
            ),
            discord.Color.green(),
        )
        await self.refresh_economy_stats(guild)
        return granted, pct, wanted

    def get_xp_loan_tier(self, guild_id: int, user_id: int) -> dict:
        level = self.get_user_level(guild_id, user_id)
        tiers = getattr(cfg, "LOAN_XP_TIERS", []) or []
        if not tiers:
            return {
                "min_level": 0, "max_level": 999, "name": "🌱 Rookie",
                "base_limit": 300, "interest": 15, "term_days": 2,
            }
        chosen = dict(tiers[0])
        for tier in sorted(tiers, key=lambda t: int(t.get("min_level", 0))):
            if level >= int(tier.get("min_level", 0)):
                chosen = dict(tier)
            else:
                break
        return chosen

    def get_next_xp_loan_tier(self, guild_id: int, user_id: int) -> Optional[dict]:
        level = self.get_user_level(guild_id, user_id)
        for tier in sorted(
            getattr(cfg, "LOAN_XP_TIERS", []) or [],
            key=lambda t: int(t.get("min_level", 0))
        ):
            if int(tier.get("min_level", 0)) > level:
                return dict(tier)
        return None

    def get_credit_limit_multiplier(self, guild_id: int, user_id: int) -> float:
        score = self.get_credit_score(guild_id, user_id)
        tiers = getattr(
            cfg, "LOAN_CREDIT_MULTIPLIERS",
            [(0, 0.50), (30, 0.75), (50, 1.00), (70, 1.15), (85, 1.25)]
        )
        multiplier = 0.50
        for min_score, mult in sorted(tiers, key=lambda x: int(x[0])):
            if score >= int(min_score):
                multiplier = float(mult)
        return max(0.0, multiplier)

    def get_loan_terms(self, guild_id: int, user_id: int) -> dict:
        """Level = privileges | Credit = trust | Treasury = liquidity protection."""
        level = self.get_user_level(guild_id, user_id)
        score = self.get_credit_score(guild_id, user_id)
        tier = self.get_xp_loan_tier(guild_id, user_id)
        credit_mult = self.get_credit_limit_multiplier(guild_id, user_id)

        base_limit = max(0, int(tier.get("base_limit", 0) or 0))
        credit_adjusted = max(0, int(base_limit * credit_mult))

        treasury = max(0, int(self._system(guild_id).get("treasury", 0) or 0))
        treasury_pct = max(
            0, min(100, int(getattr(cfg, "LOAN_TREASURY_MAX_PERCENT", 20) or 20))
        )
        liquidity_cap = treasury * treasury_pct // 100
        effective_limit = min(credit_adjusted, liquidity_cap, treasury)

        return {
            "level": level,
            "tier_name": tier.get("name", "🌱 Rookie"),
            "base_limit": base_limit,
            "credit_score": score,
            "credit_multiplier": credit_mult,
            "credit_adjusted_limit": credit_adjusted,
            "treasury": treasury,
            "liquidity_cap": liquidity_cap,
            "effective_limit": max(0, effective_limit),
            "interest_percent": max(0, int(tier.get("interest", 15) or 0)),
            "term_days": max(1, int(tier.get("term_days", 2) or 2)),
        }

    def get_loan_limit(self, guild_id: int, user_id: int) -> int:
        return int(self.get_loan_terms(guild_id, user_id)["effective_limit"])

    def get_active_loan(self, guild_id: int, user_id: int) -> Optional[dict]:
        loan = self._system(guild_id).get("loans", {}).get(str(user_id))
        if not loan:
            return None
        if int(loan.get("remaining", 0) or 0) <= 0 or loan.get("status") == "paid":
            return None
        return loan

    def _loan_is_overdue(self, loan: Optional[dict]) -> bool:
        if not loan or int(loan.get("remaining", 0) or 0) <= 0:
            return False
        try:
            due = datetime.fromisoformat(loan["due_at"])
            return datetime.now(timezone.utc) >= due
        except Exception:
            return False

    def _loan_due_unix(self, loan: dict) -> int:
        try:
            return int(datetime.fromisoformat(loan["due_at"]).timestamp())
        except Exception:
            return int(datetime.now(timezone.utc).timestamp())

    def _loan_payment_breakdown(self, loan: dict, amount: int) -> dict:
        """
        الأداء كيمشي للفائدة أولاً، من بعد Principal.
        Burn كيتطبق غير على الجزء ديال الفائدة.
        """
        amount = max(0, min(int(amount), int(loan.get("remaining", 0) or 0)))
        interest_remaining = max(
            0,
            int(loan.get("interest_total", 0) or 0) - int(loan.get("interest_paid", 0) or 0),
        )
        interest_part = min(amount, interest_remaining)
        principal_part = amount - interest_part

        burn_pct = int(getattr(cfg, "LOAN_INTEREST_BURN_PERCENT", 33) or 0)
        interest_burn = interest_part * max(0, min(100, burn_pct)) // 100
        treasury_gain = principal_part + (interest_part - interest_burn)
        return {
            "amount": amount,
            "interest": interest_part,
            "principal": principal_part,
            "burn": interest_burn,
            "treasury": treasury_gain,
        }

    async def request_loan(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        amount: int,
    ) -> Tuple[bool, str]:
        amount = int(amount)
        min_amount = int(getattr(cfg, "LOAN_MIN_AMOUNT", 100) or 100)
        if amount < min_amount:
            return False, f"❌ أقل قرض هو **{min_amount:,}** {cfg.CURRENCY_EMOJI}."

        existing = self.get_active_loan(guild.id, user.id)
        if existing:
            due_ts = self._loan_due_unix(existing)
            state = "⚠️ متأخر" if self._loan_is_overdue(existing) else "🟢 خدام"
            return False, (
                f"❌ عندك قرض {state} ديجا: **{int(existing['remaining']):,}** {cfg.CURRENCY_EMOJI} باقي.\n"
                f"📅 الأجل: <t:{due_ts}:F> (<t:{due_ts}:R>)\n"
                "خاصك تساليه قبل ما تاخد قرض جديد."
            )

        terms = self.get_loan_terms(guild.id, user.id)
        score = int(terms["credit_score"])
        level = int(terms["level"])
        limit = int(terms["effective_limit"])
        min_amount = int(getattr(cfg, "LOAN_MIN_AMOUNT", 100) or 100)

        if limit < min_amount:
            return False, (
                f"❌ البنك ما يقدرش يخرج ليك قرض دابا.\n"
                f"⭐ Level: **{level}** ({terms['tier_name']})\n"
                f"💳 Credit Score: **{score}/100**\n"
                f"🏛️ الحد الفعلي حسب السيولة: **{limit:,}** {cfg.CURRENCY_EMOJI}\n"
                "طلع XP / حسن Credit Score / خلي Treasury تكبر ومن بعد عاود."
            )

        if amount > limit:
            return False, (
                f"❌ الحد الفعلي ديالك دابا هو **{limit:,}** {cfg.CURRENCY_EMOJI}.\n"
                f"⭐ Level **{level}** — {terms['tier_name']} | "
                f"Base **{terms['base_limit']:,}**\n"
                f"💳 Credit **{score}/100** (×{terms['credit_multiplier']:.2f}) | "
                f"🏛️ Liquidity Cap **{terms['liquidity_cap']:,}**"
            )

        sys = self._system(guild.id)
        treasury = int(sys.get("treasury", 0) or 0)

        interest_pct = int(terms["interest_percent"])
        interest = max(1, amount * interest_pct // 100) if interest_pct > 0 else 0
        total_due = amount + interest
        now = datetime.now(timezone.utc)
        due_at = now + timedelta(days=int(terms["term_days"]))
        loan_id = int(sys.get("loan_next_id", 1) or 1)
        sys["loan_next_id"] = loan_id + 1

        # Treasury -> Wallet: transfer حقيقي، ماشي خلق فلوس.
        sys["treasury"] -= amount
        sys["loans"][str(user.id)] = {
            "id": loan_id,
            "principal": amount,
            "interest_total": interest,
            "interest_paid": 0,
            "total_due": total_due,
            "remaining": total_due,
            "issued_at": now.isoformat(),
            "due_at": due_at.isoformat(),
            "status": "active",
            "overdue_penalty_applied": False,
            "paid_at": None,
        }
        self.system_db.save()

        self.add_coins(
            guild.id, user.id, amount,
            source=f"loan:{loan_id}",
            respect_cap=False,
            count_as_earned=False,
        )
        tx_id = self._record_transaction(
            guild.id,
            user_id=user.id,
            kind="loan_issued",
            amount=amount,
            source=f"loan:{loan_id}",
            description=f"قرض #{loan_id} من Treasury",
            splits={"interest": interest, "total_due": total_due},
        )

        await self._economy_log(
            guild,
            f"💳 Loan Issued — Loan #{loan_id} / TX #{tx_id}",
            (
                f"**العضو:** {user.mention}\n"
                f"**Principal:** **{amount:,}** {cfg.CURRENCY_EMOJI}\n"
                f"**الفائدة ({interest_pct}%):** **{interest:,}**\n"
                f"**المطلوب يرجع:** **{total_due:,}**\n"
                f"⭐ **Level/Tier:** **{level}** — {terms['tier_name']}\n"
                f"💳 **Credit Score:** **{score}/100**\n"
                f"📉 **الفائدة:** **{interest_pct}%** | ⏳ **المدة:** **{terms['term_days']} أيام**\n"
                f"**الأجل:** <t:{int(due_at.timestamp())}:F>"
            ),
            discord.Color.blurple(),
        )
        await self.refresh_economy_stats(guild)
        return True, (
            f"✅ تقبل القرض **#{loan_id}**.\n"
            f"💵 دخل للـWallet: **{amount:,}** {cfg.CURRENCY_EMOJI}\n"
            f"⭐ Level **{level}** — **{terms['tier_name']}**\n"
            f"📈 الفائدة: **{interest:,}** (**{interest_pct}%**)\n"
            f"💳 خاصك ترجع: **{total_due:,}**\n"
            f"⏳ المدة: **{terms['term_days']} أيام**\n"
            f"📅 قبل: <t:{int(due_at.timestamp())}:F> (<t:{int(due_at.timestamp())}:R>)\n"
            f"💳 Credit Score: **{score}/100**"
        )

    async def _apply_loan_payment(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        amount: int,
        *,
        reason: str,
        source_label: str,
    ) -> Tuple[int, Optional[dict]]:
        loan = self.get_active_loan(guild.id, user.id)
        if not loan:
            return 0, None

        breakdown = self._loan_payment_breakdown(loan, amount)
        paid = int(breakdown["amount"])
        if paid <= 0:
            return 0, loan

        sys = self._system(guild.id)
        sys["treasury"] += int(breakdown["treasury"])
        sys["burned"] += int(breakdown["burn"])
        loan["interest_paid"] = int(loan.get("interest_paid", 0) or 0) + int(breakdown["interest"])
        loan["remaining"] = max(0, int(loan.get("remaining", 0) or 0) - paid)

        fully_paid = loan["remaining"] <= 0
        if fully_paid:
            was_overdue = bool(loan.get("overdue_penalty_applied")) or self._loan_is_overdue(loan)
            loan["status"] = "paid"
            loan["remaining"] = 0
            loan["paid_at"] = datetime.now(timezone.utc).isoformat()

            if not was_overdue:
                old_score = self.get_credit_score(guild.id, user.id)
                bonus = int(getattr(cfg, "LOAN_CREDIT_ON_TIME_BONUS", 8) or 8)
                self._set_credit_score(guild.id, user.id, old_score + bonus)

        self.system_db.save()

        tx_id = self._record_transaction(
            guild.id,
            user_id=user.id,
            kind="loan_paid" if fully_paid else "loan_repayment",
            amount=paid,
            source=f"loan:{loan.get('id')}",
            description=reason,
            splits={
                "treasury": int(breakdown["treasury"]),
                "burned_interest": int(breakdown["burn"]),
                "interest_paid": int(breakdown["interest"]),
                "principal_paid": int(breakdown["principal"]),
                "payment_source": source_label,
                "remaining": int(loan["remaining"]),
            },
        )
        await self._economy_log(
            guild,
            f"{'✅ Loan Paid' if fully_paid else '💸 Loan Repayment'} — Loan #{loan.get('id')} / TX #{tx_id}",
            (
                f"**العضو:** {user.mention}\n"
                f"**الأداء:** **{paid:,}** {cfg.CURRENCY_EMOJI}\n"
                f"**من:** {source_label}\n"
                f"🏛️ Treasury: **+{int(breakdown['treasury']):,}**\n"
                f"🔥 Burn من الفائدة: **{int(breakdown['burn']):,}**\n"
                f"**الباقي:** **{int(loan['remaining']):,}**"
            ),
            discord.Color.green() if fully_paid else discord.Color.orange(),
        )
        await self.refresh_economy_stats(guild)
        return paid, loan

    async def repay_loan(
        self,
        guild: discord.Guild,
        user: discord.abc.User,
        amount: int,
    ) -> Tuple[bool, str]:
        loan = self.get_active_loan(guild.id, user.id)
        if not loan:
            return False, "ℹ️ ماعندك حتى قرض خدام دابا."

        remaining = int(loan.get("remaining", 0) or 0)
        amount = max(0, min(int(amount), remaining))
        if amount <= 0:
            return False, "❌ دخل مبلغ صحيح أكبر من 0."

        bank = self.get_bank_balance(guild.id, user.id)
        wallet = self.get_balance(guild.id, user.id)
        available = bank + wallet
        if available <= 0:
            return False, "❌ ماعندكش فلوس لا فالبنك لا فالـWallet باش تخلص."

        actual = min(amount, available, remaining)
        from_bank = min(bank, actual)
        from_wallet = actual - from_bank

        if from_bank:
            self._set_bank_balance(guild.id, user.id, bank - from_bank)
        if from_wallet and not self.spend(guild.id, user.id, from_wallet):
            # حماية احتياطية: رجع Bank إذا وقع race نادر.
            if from_bank:
                self._set_bank_balance(guild.id, user.id, bank)
            return False, "❌ الرصيد تبدل قبل ما يكمل الأداء، عاود المحاولة."

        parts = []
        if from_bank:
            parts.append(f"Bank {from_bank:,}")
        if from_wallet:
            parts.append(f"Wallet {from_wallet:,}")
        paid, updated = await self._apply_loan_payment(
            guild, user, actual,
            reason="أداء يدوي للقرض",
            source_label=" + ".join(parts),
        )

        if not updated:
            return False, "❌ القرض ماعادش موجود."
        if int(updated.get("remaining", 0) or 0) <= 0:
            return True, (
                f"✅ تسالا القرض **#{updated.get('id')}** كامل! خلصتي **{paid:,}** دابا.\n"
                f"⭐ Credit Score ديالك دابا: **{self.get_credit_score(guild.id, user.id)}/100**"
            )
        return True, (
            f"✅ تخلص **{paid:,}** {cfg.CURRENCY_EMOJI} من القرض.\n"
            f"💳 باقي عليك: **{int(updated['remaining']):,}**\n"
            f"📅 الأجل: <t:{self._loan_due_unix(updated)}:R>"
        )

    async def _collect_overdue_loan(self, guild: discord.Guild, member: discord.Member, loan: dict):
        """بعد الأجل: Bank أولاً، من بعد Wallet. إلا بقا الدين كيبقى Overdue."""
        if not self._loan_is_overdue(loan):
            return

        if not loan.get("overdue_penalty_applied"):
            old_score = self.get_credit_score(guild.id, member.id)
            penalty = int(getattr(cfg, "LOAN_CREDIT_OVERDUE_PENALTY", 15) or 15)
            self._set_credit_score(guild.id, member.id, old_score - penalty)
            loan["overdue_penalty_applied"] = True
            loan["status"] = "overdue"
            self.system_db.save()
            await self._economy_log(
                guild,
                f"⚠️ Loan Overdue — Loan #{loan.get('id')}",
                (
                    f"**العضو:** {member.mention}\n"
                    f"**الباقي:** **{int(loan.get('remaining', 0)):,}** {cfg.CURRENCY_EMOJI}\n"
                    f"⭐ Credit Score: **{old_score} → {self.get_credit_score(guild.id, member.id)}**\n"
                    "البوت غادي يحاول يجمع المتوفر من Bank ثم Wallet."
                ),
                discord.Color.red(),
            )

        remaining = int(loan.get("remaining", 0) or 0)
        if remaining <= 0:
            return

        bank = self.get_bank_balance(guild.id, member.id)
        wallet = self.get_balance(guild.id, member.id)
        available = bank + wallet
        if available <= 0:
            return

        actual = min(remaining, available)
        from_bank = min(bank, actual)
        from_wallet = actual - from_bank

        if from_bank:
            self._set_bank_balance(guild.id, member.id, bank - from_bank)
        if from_wallet:
            if not self.spend(guild.id, member.id, from_wallet):
                if from_bank:
                    self._set_bank_balance(guild.id, member.id, bank)
                return

        labels = []
        if from_bank:
            labels.append(f"Bank {from_bank:,}")
        if from_wallet:
            labels.append(f"Wallet {from_wallet:,}")
        paid, updated = await self._apply_loan_payment(
            guild, member, actual,
            reason="Auto-Collection بعد انتهاء الأجل",
            source_label=" + ".join(labels),
        )
        if paid:
            try:
                if updated and int(updated.get("remaining", 0) or 0) <= 0:
                    await member.send(
                        f"✅ القرض ديالك **#{updated.get('id')}** تخلص كامل أوتوماتيكياً بعد الأجل."
                    )
                else:
                    await member.send(
                        f"⚠️ تخلص أوتوماتيكياً **{paid:,}** {cfg.CURRENCY_EMOJI} من القرض المتأخر. "
                        f"باقي **{int(updated.get('remaining', 0)):,}**."
                    )
            except discord.HTTPException:
                pass

    @tasks.loop(minutes=15)
    async def loan_collection_loop(self):
        """كيشيك القروض المتأخرة ويجمع المتوفر أوتوماتيكياً."""
        for guild in self.bot.guilds:
            sys = self._system(guild.id)
            for uid_str, loan in list(sys.get("loans", {}).items()):
                if not loan or int(loan.get("remaining", 0) or 0) <= 0:
                    continue
                if not self._loan_is_overdue(loan):
                    continue
                try:
                    uid = int(uid_str)
                except (TypeError, ValueError):
                    continue
                member = guild.get_member(uid)
                if not member:
                    try:
                        member = await guild.fetch_member(uid)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        member = None
                if member:
                    await self._collect_overdue_loan(guild, member, loan)

    @loan_collection_loop.before_loop
    async def before_loan_collection_loop(self):
        await self.bot.wait_until_ready()

    async def bank_deposit(self, guild: discord.Guild, user: discord.abc.User, amount: int) -> Tuple[bool, str]:
        amount = int(amount)
        if amount <= 0:
            return False, "❌ المبلغ خاصو يكون أكبر من 0."
        if not self.spend(guild.id, user.id, amount):
            return False, "❌ الرصيد ديالك فالمحفظة ماكافيش."

        # إلا القرض متأخر، ما نسمحوش بإخفاء الفلوس فالبنك:
        # الدين كيتخلص أولاً، والباقي فقط كيدخل للBank.
        loan = self.get_active_loan(guild.id, user.id)
        debt_paid = 0
        if loan and self._loan_is_overdue(loan):
            debt_part = min(amount, int(loan.get("remaining", 0) or 0))
            debt_paid, loan = await self._apply_loan_payment(
                guild, user, debt_part,
                reason="Deposit تحول تلقائياً للقرض المتأخر",
                source_label="Wallet Deposit",
            )
        bank_part = amount - debt_paid

        new_bank = self.get_bank_balance(guild.id, user.id)
        if bank_part > 0:
            new_bank += bank_part
            self._set_bank_balance(guild.id, user.id, new_bank)
            tx_id = self._record_transaction(
                guild.id, user_id=user.id, kind="bank_deposit", amount=bank_part,
                source="bank", description="إيداع من Wallet للبنك"
            )
            await self._economy_log(
                guild, f"🏦 Bank Deposit — TX #{tx_id}",
                f"**العضو:** {user.mention}\n**إيداع:** **{bank_part:,}** {cfg.CURRENCY_EMOJI}\n"
                f"**Bank Balance:** **{new_bank:,}**",
                discord.Color.green(),
            )

        if debt_paid:
            extra = (
                f"\n⚠️ كان عندك قرض متأخر: **{debt_paid:,}** مشاو مباشرة للدين."
            )
            if bank_part:
                extra += f" والباقي **{bank_part:,}** دخل للبنك."
        else:
            extra = ""

        return True, (
            f"✅ تمت العملية.{extra}\n"
            f"🏦 حساب البنك: **{self.get_bank_balance(guild.id, user.id):,}** | "
            f"💳 Wallet: **{self.get_balance(guild.id, user.id):,}**"
        )

    async def bank_withdraw(self, guild: discord.Guild, user: discord.abc.User, amount: int) -> Tuple[bool, str]:
        amount = int(amount)
        if amount <= 0:
            return False, "❌ المبلغ خاصو يكون أكبر من 0."
        bank = self.get_bank_balance(guild.id, user.id)
        if bank < amount:
            return False, f"❌ ماعندكش هاد المبلغ فالبنك. عندك **{bank:,}**."

        self._set_bank_balance(guild.id, user.id, bank - amount)
        self.add_coins(
            guild.id, user.id, amount, source="bank_withdraw",
            respect_cap=False, count_as_earned=False
        )
        tx_id = self._record_transaction(
            guild.id, user_id=user.id, kind="bank_withdraw", amount=amount,
            source="bank", description="سحب من البنك للـWallet"
        )
        await self._economy_log(
            guild, f"💸 Bank Withdraw — TX #{tx_id}",
            f"**العضو:** {user.mention}\n**سحب:** **{amount:,}** {cfg.CURRENCY_EMOJI}\n"
            f"**Bank Balance:** **{bank - amount:,}**",
            discord.Color.orange(),
        )
        return True, (
            f"✅ خرجتي **{amount:,}** {cfg.CURRENCY_EMOJI} من البنك.\n"
            f"🏦 حساب البنك: **{bank - amount:,}** | 💳 Wallet: **{self.get_balance(guild.id, user.id):,}**"
        )

    def build_bank_panel_embed(self, guild: discord.Guild) -> discord.Embed:
        sys = self._system(guild.id)
        embed = discord.Embed(
            title="🏦 GGMW9 Central Bank",
            description=(
                "مرحبا بيك فالنظام الاقتصادي ديال السيرفر. كلشي هنا خدام بـ **Buttons/Modals** "
                "باش ما نزيدو حتى Slash Command جديد.\n\n"
                "💳 **Wallet** = الفلوس اللي كتقدر تلعب وتشري بيها.\n"
                "🏦 **Bank** = فلوس مخزنة، الألعاب ماكتقدرش تمسها حتى تسحبها.\n"
                "💳 **Loans** = قرض حقيقي كيخرج من Treasury، بفائدة وCredit Score وأجل للأداء.\n"
                "⭐ **XP مهم:** كل ما طلع Level ديالك، كيزيد حد القرض، كتنقص الفائدة وكتطول مدة الأداء.\n"
                "🎰 الخسائر الحقيقية كتغذي Treasury وGlobal Jackpot، وجزء كيتحرق ضد التضخم."
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="🏛️ Treasury", value=f"**{sys['treasury']:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="🎰 Global Jackpot", value=f"**{sys['jackpot']:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="🎉 Events Fund", value=f"**{sys['events']:,}** {cfg.CURRENCY_EMOJI}", inline=True)

        roadmap = []
        for tier in getattr(cfg, "LOAN_XP_TIERS", []) or []:
            min_lvl = int(tier.get("min_level", 0))
            max_lvl = int(tier.get("max_level", min_lvl))
            lvl = f"Lv {min_lvl}" if min_lvl >= 100 else f"Lv {min_lvl}-{max_lvl}"
            roadmap.append(
                f"{tier.get('name', 'Tier')} • **{lvl}** → "
                f"**{int(tier.get('base_limit', 0)):,}** | "
                f"**{int(tier.get('interest', 0))}%** | "
                f"**{int(tier.get('term_days', 0))}d**"
            )
        embed.add_field(
            name="⭐ XP → امتيازات البنك",
            value="\n".join(roadmap)[:1024] if roadmap else "طلع Level باش تفتح شروط أحسن.",
            inline=False,
        )
        embed.add_field(
            name="💡 كيفاش كيتحسب الحد الفعلي؟",
            value=(
                "**Level** = الحد الأساسي + الفائدة + المدة. "
                "**Credit Score** = معامل الثقة. "
                "**Treasury** = سقف السيولة باش عضو واحد مايفرغش البنك.\n"
                "ضغط **⭐ امتيازات XP** باش تشوف وضعيتك والمستوى الجاي."
            ),
            inline=False,
        )
        embed.set_footer(text="GGMW9 Economy • طلع XP = امتيازات مالية أقوى")
        return embed

    def build_global_economy_embed(self, guild: discord.Guild) -> discord.Embed:
        sys = self._system(guild.id)
        guild_data = self.db.guild(guild.id)
        wallets = sum(max(0, int(acc.get("coins", 0) or 0)) for acc in guild_data.values())
        bank_total = sum(max(0, int(v or 0)) for v in sys.get("bank_accounts", {}).values())
        active_loans = [
            loan for loan in sys.get("loans", {}).values()
            if loan and int(loan.get("remaining", 0) or 0) > 0
        ]
        loans_outstanding = sum(int(loan.get("remaining", 0) or 0) for loan in active_loans)
        overdue_loans = sum(1 for loan in active_loans if self._loan_is_overdue(loan))
        live_supply = wallets + bank_total + sys["treasury"] + sys["jackpot"] + sys["events"]

        embed = discord.Embed(
            title="📊 اقتصاد GGMW9 — Live",
            description="لوحة عامة بلا معلومات خاصة بالأعضاء. كتتحدث أوتوماتيكياً.",
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="💳 Wallets ديال الأعضاء", value=f"**{wallets:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="🏦 ودائع البنك", value=f"**{bank_total:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="🏛️ Treasury", value=f"**{sys['treasury']:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="🎰 Global Jackpot", value=f"**{sys['jackpot']:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="🎉 Events Fund", value=f"**{sys['events']:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="🔥 Burned (من البداية)", value=f"**{sys['burned']:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="📉 خسائر القمار", value=f"**{sys['total_gambling_lost']:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="🛒 مصاريف المتجر", value=f"**{sys['total_shop_spent']:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="🏆 Jackpot تصرف", value=f"**{sys['total_jackpot_paid']:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="💳 Loans Outstanding", value=f"**{loans_outstanding:,}** {cfg.CURRENCY_EMOJI}", inline=True)
        embed.add_field(name="⚠️ Overdue Loans", value=f"**{overdue_loans}**", inline=True)
        embed.add_field(name="💹 Money Supply الحالي", value=f"**{live_supply:,}** {cfg.CURRENCY_EMOJI}", inline=False)
        embed.set_footer(text="Wallet + Bank + Treasury + Jackpot + Events | Burn ما داخلش فالـSupply")
        return embed

    def build_user_account_embed(self, guild: discord.Guild, user: discord.abc.User) -> discord.Embed:
        wallet = self.get_balance(guild.id, user.id)
        bank = self.get_bank_balance(guild.id, user.id)
        embed = discord.Embed(
            title=f"💳 الحساب ديال {user.display_name}",
            description=f"المجموع ديالك: **{wallet + bank:,}** {cfg.CURRENCY_EMOJI}",
            color=discord.Color.green(),
        )
        embed.add_field(name="💳 Wallet", value=f"**{wallet:,}**", inline=True)
        embed.add_field(name="🏦 Bank", value=f"**{bank:,}**", inline=True)
        terms = self.get_loan_terms(guild.id, user.id)
        score = int(terms["credit_score"])
        embed.add_field(
            name="⭐ Level / Bank Tier",
            value=f"**Level {terms['level']}**\n{terms['tier_name']}",
            inline=True,
        )
        embed.add_field(
            name="💳 Credit Score",
            value=f"**{score}/100**\n×{terms['credit_multiplier']:.2f} على الحد",
            inline=True,
        )
        embed.add_field(
            name="🏦 شروط القرض دابا",
            value=(
                f"حد فعلي: **{terms['effective_limit']:,}** {cfg.CURRENCY_EMOJI}\n"
                f"فائدة: **{terms['interest_percent']}%** • مدة: **{terms['term_days']} أيام**"
            ),
            inline=False,
        )
        loan = self.get_active_loan(guild.id, user.id)
        if loan:
            state = "⚠️ متأخر" if self._loan_is_overdue(loan) else "🟢 خدام"
            embed.add_field(
                name=f"💳 Loan #{loan.get('id')} — {state}",
                value=(
                    f"الباقي: **{int(loan.get('remaining', 0)):,}** {cfg.CURRENCY_EMOJI}\n"
                    f"الأجل: <t:{self._loan_due_unix(loan)}:F> (<t:{self._loan_due_unix(loan)}:R>)"
                ),
                inline=False,
            )
        else:
            embed.add_field(name="💳 القرض", value="ما عندك حتى قرض خدام.", inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Bank محمي من الرهان | القرض المتأخر كيتجمع من Bank ثم Wallet")
        return embed

    def build_xp_bank_perks_embed(self, guild: discord.Guild, user: discord.abc.User) -> discord.Embed:
        terms = self.get_loan_terms(guild.id, user.id)
        next_tier = self.get_next_xp_loan_tier(guild.id, user.id)
        min_amount = int(getattr(cfg, "LOAN_MIN_AMOUNT", 100) or 100)

        embed = discord.Embed(
            title=f"⭐ امتيازات XP — {user.display_name}",
            description=(
                "**XP/Level = الخبرة والسمعة داخل السيرفر.**\n"
                "كل Tier جديد كيعطيك قرض أكبر، فائدة أقل، ووقت أكثر للأداء. "
                "Credit Score كيبقى مقياس الثقة واش كتخلص مزيان."
            ),
            color=discord.Color.gold(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(
            name="📊 وضعيتك دابا",
            value=(
                f"⭐ **Level {terms['level']}** — {terms['tier_name']}\n"
                f"💳 Credit Score: **{terms['credit_score']}/100**\n"
                f"🏛️ Treasury: **{terms['treasury']:,}** {cfg.CURRENCY_EMOJI}"
            ),
            inline=False,
        )
        embed.add_field(
            name="💰 الامتيازات ديالك",
            value=(
                f"Base Loan من Level: **{terms['base_limit']:,}**\n"
                f"بعد Credit (×{terms['credit_multiplier']:.2f}): "
                f"**{terms['credit_adjusted_limit']:,}**\n"
                f"Liquidity Cap: **{terms['liquidity_cap']:,}**\n"
                f"✅ **الحد الفعلي: {terms['effective_limit']:,} {cfg.CURRENCY_EMOJI}**\n"
                f"📉 الفائدة: **{terms['interest_percent']}%**\n"
                f"⏳ المدة: **{terms['term_days']} أيام**"
            ),
            inline=False,
        )

        if next_tier:
            nxt = int(next_tier.get("min_level", 0))
            left = max(0, nxt - int(terms["level"]))
            embed.add_field(
                name="🚀 الهدف الجاي",
                value=(
                    f"باقي **{left} Level** لـ **{next_tier.get('name', 'Tier جديد')}** (Lv {nxt}).\n"
                    f"💰 Base Loan: **{int(next_tier.get('base_limit', 0)):,}**\n"
                    f"📉 Interest: **{int(next_tier.get('interest', 0))}%**\n"
                    f"⏳ Term: **{int(next_tier.get('term_days', 0))} أيام**"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="🔱 القمة",
                value="راك فـ **Legend Tier** — أقوى شروط البنك مفتوحة ليك.",
                inline=False,
            )

        if int(terms["effective_limit"]) < min_amount:
            embed.add_field(
                name="⚠️ السيولة",
                value=(
                    f"الحد الفعلي دابا أقل من أقل قرض (**{min_amount:,}**) بسبب Treasury/Credit. "
                    "Level ديالك باقي محسوب؛ منين تتحسن السيولة/الثقة غادي يبان أثره."
                ),
                inline=False,
            )

        embed.set_footer(text="نشاط أكثر → XP أكثر → Bank Tier أقوى")
        return embed

    def build_user_transactions_embed(self, guild: discord.Guild, user: discord.abc.User) -> discord.Embed:
        txs = self.get_user_transactions(guild.id, user.id, limit=10)
        if not txs:
            return discord.Embed(
                title="🧾 آخر المعاملات",
                description="📭 ماكايناش معاملات مسجلة ليك فالنظام الجديد دابا.",
                color=discord.Color.blurple(),
            )
        kind_icons = {
            "gambling_loss": "🎰",
            "shop_purchase": "🛒",
            "jackpot_payout": "🏆",
            "bank_deposit": "🏦",
            "bank_withdraw": "💸",
            "loan_issued": "💳",
            "loan_repayment": "💸",
            "loan_paid": "✅",
            "level_daily_bonus": "⭐",
            "admin_adjustment": "🛡️",
        }
        lines = []
        for tx in txs:
            icon = kind_icons.get(tx.get("kind"), "💱")
            ts = tx.get("ts", "")
            try:
                unix = int(datetime.fromisoformat(ts).timestamp())
                when = f"<t:{unix}:R>"
            except Exception:
                when = "—"
            lines.append(
                f"{icon} **TX #{tx.get('id')}** • {tx.get('description', tx.get('source', 'عملية'))} "
                f"• **{int(tx.get('amount', 0)):,}** {cfg.CURRENCY_EMOJI} • {when}"
            )
        return discord.Embed(
            title=f"🧾 آخر معاملات {user.display_name}",
            description="\n".join(lines),
            color=discord.Color.blurple(),
        )

    async def ensure_bank_panel(self, guild: discord.Guild):
        channel_id = int(getattr(cfg, "ECONOMY_BANK_CHANNEL_ID", 0) or 0)
        channel = guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return
        found = None
        try:
            async for msg in channel.history(limit=25):
                if (
                    msg.author == self.bot.user and msg.embeds
                    and (msg.embeds[0].title or "") == "🏦 GGMW9 Central Bank"
                ):
                    found = msg
                    break
        except discord.Forbidden:
            return
        embed = self.build_bank_panel_embed(guild)
        try:
            if found:
                await found.edit(embed=embed, view=EconomyBankPanelView(self))
            else:
                await channel.send(embed=embed, view=EconomyBankPanelView(self))
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def refresh_economy_stats(self, guild: discord.Guild):
        channel_id = int(getattr(cfg, "ECONOMY_STATS_CHANNEL_ID", 0) or 0)
        channel = guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return

        sys = self._system(guild.id)
        msg = None
        msg_id = sys.get("stats_message_id")
        if msg_id:
            try:
                msg = await channel.fetch_message(int(msg_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, TypeError, ValueError):
                msg = None

        if msg is None:
            try:
                async for old in channel.history(limit=25):
                    if (
                        old.author == self.bot.user and old.embeds
                        and (old.embeds[0].title or "") == "📊 اقتصاد GGMW9 — Live"
                    ):
                        msg = old
                        break
            except discord.Forbidden:
                return

        embed = self.build_global_economy_embed(guild)
        try:
            if msg:
                await msg.edit(embed=embed)
            else:
                msg = await channel.send(embed=embed)
            if sys.get("stats_message_id") != msg.id:
                sys["stats_message_id"] = msg.id
                self.system_db.save()
        except (discord.Forbidden, discord.HTTPException):
            pass

    @tasks.loop(minutes=2)
    async def economy_stats_loop(self):
        for guild in self.bot.guilds:
            await self.refresh_economy_stats(guild)

    @economy_stats_loop.before_loop
    async def before_economy_stats_loop(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.ensure_bank_panel(guild)
            await self.refresh_economy_stats(guild)

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
        count_as_earned: bool = True,
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
            if count_as_earned:
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

    @commands.command(name="balance", aliases=["bal", "فلوسي"], hidden=True)
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

        # Level Bonus حقيقي وممول من Treasury.
        level_bonus, level_bonus_pct, level_bonus_wanted = await self.grant_level_daily_bonus(
            ctx.guild, ctx.author, total
        )
        final_total = total + level_bonus

        acc["daily_last"] = now.isoformat()
        self.db.save()

        self.add_coins(
            ctx.guild.id,
            ctx.author.id,
            final_total,
            source="daily",
            respect_cap=False,
        )

        embed = discord.Embed(
            title="🎁 المكافأة اليومية",
            description=f"خديتي **{final_total}** {currency_word(final_total)} {cfg.CURRENCY_EMOJI}",
            color=discord.Color.green(),
        )
        if bonus > 0:
            embed.add_field(
                name="🔥 بونوس Streak",
                value=f"+{bonus} (نهار {acc['daily_streak']} متتالي)",
                inline=False,
            )
        if level_bonus > 0:
            embed.add_field(
                name="⭐ بونوس Level",
                value=(
                    f"+**{level_bonus:,}** {cfg.CURRENCY_EMOJI} "
                    f"(+{level_bonus_pct}%، ممول من Treasury)"
                ),
                inline=False,
            )
        elif level_bonus_pct > 0 and level_bonus_wanted > 0:
            embed.add_field(
                name="⭐ بونوس Level",
                value=(
                    f"عندك **+{level_bonus_pct}%** مفتوحة، ولكن Treasury ما فيهاش "
                    "سيولة كافية للبونوس دابا."
                ),
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

    async def owner_adjust_balance(
        self,
        guild: discord.Guild,
        member: discord.Member,
        amount: int,
        *,
        actor: Optional[discord.abc.User] = None,
    ) -> dict:
        """Source of truth واحد لـ Owner Panel وfallback command."""
        amount = int(amount)
        before = self.get_balance(guild.id, member.id)

        if amount >= 0:
            applied = self.add_coins(
                guild.id,
                member.id,
                amount,
                source="owner_adjustment",
                respect_cap=False,
                count_as_earned=False,
            )
        else:
            remove = min(before, abs(amount))
            acc = self._acc(guild.id, member.id)
            acc["coins"] = max(0, before - remove)
            self.db.save()
            applied = -remove

        after = self.get_balance(guild.id, member.id)

        dm_sent = True
        try:
            if applied >= 0:
                await member.send(
                    f"💰 تزادو ليك **{applied:,}** {cfg.CURRENCY_EMOJI} من إدارة السيرفر.\\n"
                    f"الرصيد دابا: **{after:,}** {cfg.CURRENCY_EMOJI}"
                )
            else:
                await member.send(
                    f"💸 تحيدو من رصيدك **{abs(applied):,}** {cfg.CURRENCY_EMOJI} من إدارة السيرفر.\\n"
                    f"الرصيد دابا: **{after:,}** {cfg.CURRENCY_EMOJI}"
                )
        except (discord.Forbidden, discord.HTTPException):
            dm_sent = False

        tx_id = self._record_transaction(
            guild.id,
            user_id=member.id,
            kind="admin_adjustment",
            amount=abs(applied),
            source="owner_control",
            description="Owner balance adjustment",
            splits={"delta": applied, "before": before, "after": after},
        )
        actor_text = actor.mention if actor else "Owner"
        await self._economy_log(
            guild,
            f"🛡️ Owner Balance Adjustment — TX #{tx_id}",
            (
                f"**العضو:** {member.mention}\\n"
                f"**التغيير الفعلي:** **{applied:+,}** {cfg.CURRENCY_EMOJI}\\n"
                f"**قبل:** **{before:,}** → **بعد:** **{after:,}**\\n"
                f"**من طرف:** {actor_text}"
            ),
            discord.Color.blurple(),
        )
        await self.refresh_economy_stats(guild)
        return {
            "before": before,
            "after": after,
            "applied": applied,
            "dm_sent": dm_sent,
            "tx_id": tx_id,
        }


    # ════════════════════════════════════════════════
    # SHOP
    # ════════════════════════════════════════════════

    @commands.command(name="shop", aliases=["متجر"], hidden=True)
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

        discount = self.get_shop_discount_percent(ctx.guild.id, ctx.author.id)
        if discount:
            embed.description += f"\n⭐ Level Discount ديالك: **-{discount}%**"

        for item in cfg.SHOP_ITEMS:
            if item["type"] == "temp_role" and not item.get("role_id"):
                continue
            final_price = self.get_shop_price(ctx.guild.id, ctx.author.id, item["price"])
            affordable = "✅" if balance >= final_price else "❌"
            price_text = (
                f"~~{item['price']:,}~~ → **{final_price:,}**"
                if final_price != item["price"]
                else f"**{final_price:,}**"
            )
            embed.add_field(
                name=f"{item['emoji']} {item['name']} — {price_text} {cfg.CURRENCY_EMOJI} {affordable}",
                value=item["description"],
                inline=False,
            )

        embed.set_footer(text="ربح الدراهم من الألعاب فـ #games-panel ولا /daily")
        await ctx.send(embed=embed, view=ShopView(self, ctx.author))

    # ════════════════════════════════════════════════
    # أمر givecoins — Owner فقط
    # ════════════════════════════════════════════════

    @commands.command(name="givecoins", hidden=True)
    async def givecoins_cmd(
        self, ctx: commands.Context, member: discord.Member, amount: int
    ):
        """Hidden prefix fallback. Owner workflow الحقيقي كاين فـ Owner Control Center."""
        owner_id = getattr(self.bot, "gg", {}).get("OWNER_ID")
        if not owner_id or ctx.author.id != owner_id:
            return
        result = await self.owner_adjust_balance(
            ctx.guild, member, amount, actor=ctx.author
        )
        try:
            await ctx.author.send(
                f"✅ {member} | {result['applied']:+,} {cfg.CURRENCY_EMOJI} | "
                f"Balance: {result['after']:,}"
            )
        except discord.HTTPException:
            pass



class BankAmountModal(discord.ui.Modal):
    def __init__(self, cog: "Economy", action: str):
        title = "🏦 إيداع فالبنك" if action == "deposit" else "💸 سحب من البنك"
        super().__init__(title=title)
        self.cog = cog
        self.action = action
        self.amount = discord.ui.TextInput(
            label="المبلغ",
            placeholder="مثلا 500",
            min_length=1,
            max_length=12,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        raw = str(self.amount.value).strip().replace(",", "").replace(" ", "")
        if not raw.isdigit() or int(raw) <= 0:
            await interaction.response.send_message("❌ دخل مبلغ صحيح أكبر من 0.", ephemeral=True)
            return
        amount = int(raw)
        if self.action == "deposit":
            ok, msg = await self.cog.bank_deposit(interaction.guild, interaction.user, amount)
        else:
            ok, msg = await self.cog.bank_withdraw(interaction.guild, interaction.user, amount)
        await interaction.response.send_message(msg, ephemeral=True)



class LoanRequestModal(discord.ui.Modal):
    def __init__(self, cog: "Economy", guild_id: int, user_id: int):
        terms = cog.get_loan_terms(guild_id, user_id)
        limit = int(terms["effective_limit"])
        super().__init__(title="💳 طلب قرض من GGMW9 Bank")
        self.cog = cog
        self.amount = discord.ui.TextInput(
            label="شحال بغيتي تسلف؟",
            placeholder=f"من {getattr(cfg, 'LOAN_MIN_AMOUNT', 100)} حتى {limit}",
            min_length=1,
            max_length=12,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        raw = str(self.amount.value).strip().replace(",", "").replace(" ", "")
        if not raw.isdigit() or int(raw) <= 0:
            await interaction.response.send_message("❌ دخل مبلغ صحيح.", ephemeral=True)
            return
        ok, msg = await self.cog.request_loan(
            interaction.guild, interaction.user, int(raw)
        )
        await interaction.response.send_message(msg, ephemeral=True)


class LoanRepayModal(discord.ui.Modal):
    def __init__(self, cog: "Economy", loan: dict):
        super().__init__(title=f"💸 أداء Loan #{loan.get('id')}")
        self.cog = cog
        self.amount = discord.ui.TextInput(
            label="شحال بغيتي تخلص دابا؟",
            placeholder=f"الباقي {int(loan.get('remaining', 0))}",
            min_length=1,
            max_length=12,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        raw = str(self.amount.value).strip().replace(",", "").replace(" ", "")
        if not raw.isdigit() or int(raw) <= 0:
            await interaction.response.send_message("❌ دخل مبلغ صحيح.", ephemeral=True)
            return
        ok, msg = await self.cog.repay_loan(
            interaction.guild, interaction.user, int(raw)
        )
        await interaction.response.send_message(msg, ephemeral=True)


class EconomyBankPanelView(discord.ui.View):
    """Central Bank Panel دائم — كاع الوظائف هنا Buttons/Modals، بلا حتى Slash جديد."""

    def __init__(self, cog: "Economy"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="💳 حسابي", style=discord.ButtonStyle.primary,
        custom_id="ggmw9:economy:account", row=0
    )
    async def account_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=self.cog.build_user_account_embed(interaction.guild, interaction.user),
            ephemeral=True,
        )

    @discord.ui.button(
        label="🏦 إيداع", style=discord.ButtonStyle.success,
        custom_id="ggmw9:economy:deposit", row=0
    )
    async def deposit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BankAmountModal(self.cog, "deposit"))

    @discord.ui.button(
        label="💸 سحب", style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:economy:withdraw", row=0
    )
    async def withdraw_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BankAmountModal(self.cog, "withdraw"))

    @discord.ui.button(
        label="🏛️ الخزينة", style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:economy:treasury", row=0
    )
    async def treasury_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        sys = self.cog._system(interaction.guild.id)
        embed = discord.Embed(
            title="🏛️ خزينة السيرفر",
            description=(
                f"🏛️ **Treasury:** {sys['treasury']:,} {cfg.CURRENCY_EMOJI}\n"
                f"🎉 **Events Fund:** {sys['events']:,} {cfg.CURRENCY_EMOJI}\n"
                f"🔥 **Burned من البداية:** {sys['burned']:,} {cfg.CURRENCY_EMOJI}\n\n"
                "الخزينة وصندوق Events فلوس حقيقية خارجة من الاقتصاد ديال اللاعبين؛ "
                "الـBurn هو اللي كيتحيد نهائياً ضد التضخم."
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="🎰 Jackpot", style=discord.ButtonStyle.danger,
        custom_id="ggmw9:economy:jackpot", row=1
    )
    async def jackpot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        sys = self.cog._system(interaction.guild.id)
        embed = discord.Embed(
            title="🎰 Global Jackpot",
            description=(
                f"# **{sys['jackpot']:,}** {cfg.CURRENCY_EMOJI}\n\n"
                "كيكبر من جزء من الرهانات اللي **تخسرو فعلاً**.\n"
                "🏆 كيتصرف كامل تلقائياً ملي يجي Jackpot حقيقي فـ:\n"
                "• 🎰 Slots — `7️⃣ | 7️⃣ | 7️⃣`\n"
                "• 🎫 Scratch — رمز `💰` الفائز\n"
                "• 🎟️ Lottery — تطابق كامل"
            ),
            color=discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="📊 الاقتصاد", style=discord.ButtonStyle.primary,
        custom_id="ggmw9:economy:stats", row=1
    )
    async def stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=self.cog.build_global_economy_embed(interaction.guild),
            ephemeral=True,
        )

    @discord.ui.button(
        label="🧾 معاملاتي", style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:economy:transactions", row=1
    )
    async def transactions_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=self.cog.build_user_transactions_embed(interaction.guild, interaction.user),
            ephemeral=True,
        )


    @discord.ui.button(
        label="💳 طلب قرض", style=discord.ButtonStyle.success,
        custom_id="ggmw9:economy:loan_request", row=1
    )
    async def loan_request_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        loan = self.cog.get_active_loan(interaction.guild.id, interaction.user.id)
        if loan:
            state = "⚠️ متأخر" if self.cog._loan_is_overdue(loan) else "🟢 خدام"
            await interaction.response.send_message(
                (
                    f"💳 عندك Loan **#{loan.get('id')}** {state}.\\n"
                    f"الباقي: **{int(loan.get('remaining', 0)):,}** {cfg.CURRENCY_EMOJI}\\n"
                    f"الأجل: <t:{self.cog._loan_due_unix(loan)}:F> "
                    f"(<t:{self.cog._loan_due_unix(loan)}:R>)\\n"
                    "خاصك تساليه قبل قرض جديد."
                ),
                ephemeral=True,
            )
            return
        terms = self.cog.get_loan_terms(interaction.guild.id, interaction.user.id)
        min_amount = int(getattr(cfg, "LOAN_MIN_AMOUNT", 100) or 100)
        if int(terms["effective_limit"]) < min_amount:
            await interaction.response.send_message(
                (
                    f"❌ الحد ديالك ماكافيش لقرض دابا.\n"
                    f"⭐ Level **{terms['level']}** — {terms['tier_name']}\n"
                    f"💳 Credit **{terms['credit_score']}/100**\n"
                    f"🏛️ الحد الفعلي: **{terms['effective_limit']:,}** {cfg.CURRENCY_EMOJI}\n\n"
                    "ضغط **⭐ امتيازات XP** باش تشوف الطريق للـTier الجاي."
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(
            LoanRequestModal(self.cog, interaction.guild.id, interaction.user.id)
        )

    @discord.ui.button(
        label="💸 خلص القرض", style=discord.ButtonStyle.primary,
        custom_id="ggmw9:economy:loan_repay", row=1
    )
    async def loan_repay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        loan = self.cog.get_active_loan(interaction.guild.id, interaction.user.id)
        if not loan:
            await interaction.response.send_message(
                "ℹ️ ماعندك حتى قرض خدام دابا.", ephemeral=True
            )
            return
        await interaction.response.send_modal(LoanRepayModal(self.cog, loan))


    @discord.ui.button(
        label="⭐ امتيازات XP", style=discord.ButtonStyle.secondary,
        custom_id="ggmw9:economy:xp_perks", row=2
    )
    async def xp_perks_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=self.cog.build_xp_bank_perks_embed(interaction.guild, interaction.user),
            ephemeral=True,
        )



class ShopView(discord.ui.View):
    def __init__(self, cog: "Economy", user: discord.abc.User):
        super().__init__(timeout=180)
        self.cog = cog
        self.user = user

        options = []
        guild = getattr(user, "guild", None)
        for item in cfg.SHOP_ITEMS:
            if item["type"] == "temp_role" and not item.get("role_id"):
                continue
            shown_price = (
                cog.get_shop_price(guild.id, user.id, item["price"])
                if guild else item["price"]
            )
            options.append(
                discord.SelectOption(
                    label=f"{item['name']} — {shown_price} 🪙",
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

        price = self.cog.get_shop_price(
            interaction.guild.id, interaction.user.id, item["price"]
        )
        discount = self.cog.get_shop_discount_percent(
            interaction.guild.id, interaction.user.id
        )
        balance = self.cog.get_balance(interaction.guild.id, interaction.user.id)
        if balance < price:
            await interaction.response.send_message(
                f"❌ ماكافيوش — خاصك **{price - balance:,}** "
                f"{cfg.CURRENCY_EMOJI} زيادة.",
                ephemeral=True,
            )
            return

        priced_item = dict(item)
        priced_item["_final_price"] = price

        if item["type"] == "role_color":
            await interaction.response.send_message(
                f"🎨 اختار اللون اللي بغيتي "
                f"(**{price}** {cfg.CURRENCY_EMOJI}"
                + (f" بعد -{discount}% Level Discount" if discount else "")
                + "):",
                view=ColorPickView(self.cog, interaction.user, priced_item),
                ephemeral=True,
            )
            return

        if item["type"] == "custom_role":
            await interaction.response.send_modal(CustomRoleModal(self.cog, priced_item))
            return

        await interaction.response.defer(ephemeral=True)
        ok, msg = await apply_purchase(
            self.cog, interaction.guild, interaction.user, item
        )
        if ok:
            if not self.cog.spend(interaction.guild.id, interaction.user.id, price):
                await interaction.followup.send("❌ الرصيد تبدل قبل ما يكمل الشراء.", ephemeral=True)
                return
            await self.cog.route_shop_purchase(
                interaction.guild, interaction.user, price, item
            )
            new_balance = self.cog.get_balance(
                interaction.guild.id, interaction.user.id
            )
            saved = max(0, int(item["price"]) - int(price))
            discount_note = f"\n⭐ Level Discount: وفرتي **{saved:,}**" if saved else ""
            await interaction.followup.send(
                f"✅ {msg}{discount_note}\n💰 الرصيد الجديد: **{new_balance:,}** {cfg.CURRENCY_EMOJI}",
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
            final_price = int(item.get("_final_price", item["price"]))
            if not self.cog.spend(interaction.guild.id, interaction.user.id, final_price):
                await interaction.followup.send("❌ الرصيد تبدل قبل ما يكمل الشراء.", ephemeral=True)
                return
            await self.cog.route_shop_purchase(
                interaction.guild, interaction.user, final_price, item
            )
            saved = max(0, int(item["price"]) - final_price)
            note = f"\n⭐ Level Discount: وفرتي **{saved:,}**" if saved else ""
            await interaction.followup.send(f"✅ {msg}{note}", ephemeral=True)
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
            final_price = int(item.get("_final_price", item["price"]))
            if not self.cog.spend(interaction.guild.id, interaction.user.id, final_price):
                await interaction.followup.send("❌ الرصيد تبدل قبل ما يكمل الشراء.", ephemeral=True)
                return
            await self.cog.route_shop_purchase(
                interaction.guild, interaction.user, final_price, item
            )
            saved = max(0, int(item["price"]) - final_price)
            note = f"\n⭐ Level Discount: وفرتي **{saved:,}**" if saved else ""
            await interaction.followup.send(f"✅ {msg}{note}", ephemeral=True)
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
