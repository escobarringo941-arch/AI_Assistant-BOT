# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║ cogs/economy.py — 💵 USD Economy + Marketplace       ║
═══════════════════════════════════════════════════════

هادا **قلب** النظام. كاع الألعاب كتعيّط عليه باش تعطي/تحيد USD بالسنت.

الأوامر:
 /balance — شحال عندك
 /daily   — مكافأة يومية
 /shop    — المتجر
 /richest — أغنى 10 أعضاء
 givecoins — (Owner فقط) hidden fallback لتعديل USD
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
    # Compatibility helper for older game cogs. Currency is now USD.
    return cfg.CURRENCY_NAME


def fmt_coins(amount: int) -> str:
    return cfg.fmt_money(amount)


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
        self.bank_interest_loop.start()
        # Persistent View: ما كيزيد حتى Slash Command جديد.
        self.bot.add_view(EconomyBankPanelView(self))

    def cog_unload(self):
        self.expire_purchases_loop.cancel()
        self.economy_stats_loop.cancel()
        self.loan_collection_loop.cancel()
        self.bank_interest_loop.cancel()

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
            "bank_interest_last_day": None,
            "total_interest_paid": 0,
            "bank_transfer_daily": {},
            "total_transfer_fees": 0,
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
        jackpot = amount * int(getattr(cfg, "GAMBLING_LOSS_JACKPOT_PERCENT", 15)) // 100
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
                f"**الخسارة:** **{cfg.fmt_money(amount)}**\n\n"
                f"🏛️ Treasury: **+{cfg.fmt_money(treasury)}**\n"
                f"🎰 Global Jackpot: **+{cfg.fmt_money(jackpot)}**\n"
                f"🔥 Burned: **{cfg.fmt_money(burned)}**"
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
        treasury = amount * int(getattr(cfg, "SHOP_TREASURY_PERCENT", 55)) // 100
        events = amount * int(getattr(cfg, "SHOP_EVENTS_PERCENT", 15)) // 100
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
                f"**الثمن:** **{cfg.fmt_money(amount)}**\n\n"
                f"🏛️ Treasury: **+{cfg.fmt_money(treasury)}**\n"
                f"🎉 Events Fund: **+{cfg.fmt_money(events)}**\n"
                f"🔥 Burned: **{cfg.fmt_money(burned)}**"
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
                f"**الجائزة من الـPool:** **{cfg.fmt_money(granted)}**\n"
                f"🎰 الـJackpot Pool رجع دابا لـ **0**."
            ),
            discord.Color.gold(),
        )
        await self.refresh_economy_stats(guild)
        return granted

    # ════════════════════════════════════════════════
    # Real Bank — Savings interest / transfers / assets
    # ════════════════════════════════════════════════

    def _perk_active(self, guild_id: int, user_id: int, key: str) -> bool:
        acc = self._acc(guild_id, user_id)
        expires = acc.get(key)
        if not expires:
            return False
        try:
            if datetime.now(timezone.utc) < datetime.fromisoformat(expires):
                return True
        except Exception:
            pass
        acc.pop(key, None)
        self.db.save()
        return False

    def get_bank_interest_bps(self, guild_id: int, user_id: int) -> int:
        base = int(getattr(cfg, "BANK_INTEREST_BASE_BPS_DAILY", 5) or 5)
        level_bonus = min(
            int(getattr(cfg, "BANK_INTEREST_LEVEL_BONUS_BPS_MAX", 5) or 5),
            max(0, self.get_user_level(guild_id, user_id) // 20),
        )
        boost = int(getattr(cfg, "BANK_INTEREST_BOOST_BPS", 5) or 5) if self._perk_active(
            guild_id, user_id, "bank_interest_boost_expires"
        ) else 0
        return max(0, base + level_bonus + boost)

    def get_bank_interest_rate_text(self, guild_id: int, user_id: int) -> str:
        bps = self.get_bank_interest_bps(guild_id, user_id)
        return f"{bps / 100:.2f}% / day"

    def get_transfer_daily_limit(self, guild_id: int, user_id: int) -> int:
        base = int(getattr(cfg, "BANK_TRANSFER_DAILY_LIMIT", 100000) or 100000)
        bonus_each = int(getattr(cfg, "BANK_TRANSFER_LEVEL_BONUS_PER_10", 10000) or 10000)
        hard = int(getattr(cfg, "BANK_TRANSFER_MAX_DAILY_LIMIT", 200000) or 200000)
        level = self.get_user_level(guild_id, user_id)
        return min(hard, base + (level // 10) * bonus_each)

    def get_transfer_sent_today(self, guild_id: int, user_id: int) -> int:
        sys = self._system(guild_id)
        rec = sys.setdefault("bank_transfer_daily", {}).setdefault(str(user_id), {})
        today = _today_key()
        if rec.get("date") != today:
            rec.clear()
            rec.update({"date": today, "sent": 0})
            self.system_db.save()
        return int(rec.get("sent", 0) or 0)

    def _bank_transfer_fee(self, guild_id: int, user_id: int, amount: int) -> int:
        if self._perk_active(guild_id, user_id, "transfer_fee_pass_expires"):
            return 0
        bps = int(getattr(cfg, "BANK_TRANSFER_FEE_BPS", 100) or 100)
        minimum = int(getattr(cfg, "BANK_TRANSFER_MIN_FEE", 10) or 10)
        maximum = int(getattr(cfg, "BANK_TRANSFER_MAX_FEE", 500) or 500)
        return min(maximum, max(minimum, int(amount) * bps // 10000))

    async def bank_transfer(
        self,
        guild: discord.Guild,
        sender: discord.Member,
        recipient: discord.Member,
        amount: int,
    ) -> Tuple[bool, str]:
        amount = int(amount)
        if amount <= 0:
            return False, "❌ المبلغ خاصو يكون أكبر من 0."
        if sender.id == recipient.id:
            return False, "❌ مايمكنش تصيفط الفلوس لنفسك."
        if recipient.bot:
            return False, "❌ التحويلات للحسابات ديال Bots ممنوعة."

        sent_today = self.get_transfer_sent_today(guild.id, sender.id)
        daily_limit = self.get_transfer_daily_limit(guild.id, sender.id)
        if sent_today + amount > daily_limit:
            left = max(0, daily_limit - sent_today)
            return False, f"❌ Daily transfer limit. باقي ليك اليوم **{cfg.fmt_money(left)}**."

        fee = self._bank_transfer_fee(guild.id, sender.id, amount)
        total = amount + fee
        sender_bank = self.get_bank_balance(guild.id, sender.id)
        if sender_bank < total:
            return False, (
                f"❌ Bank balance ماكافيش. التحويل **{cfg.fmt_money(amount)}**"
                f" + fee **{cfg.fmt_money(fee)}** = **{cfg.fmt_money(total)}**."
            )

        sys = self._system(guild.id)
        sys["bank_accounts"][str(sender.id)] = sender_bank - total
        sys["bank_accounts"][str(recipient.id)] = self.get_bank_balance(guild.id, recipient.id) + amount

        treasury_pct = int(getattr(cfg, "BANK_TRANSFER_TREASURY_PERCENT", 70) or 70)
        treasury_fee = fee * max(0, min(100, treasury_pct)) // 100
        burned_fee = fee - treasury_fee
        sys["treasury"] += treasury_fee
        sys["burned"] += burned_fee
        sys["total_transfer_fees"] = int(sys.get("total_transfer_fees", 0) or 0) + fee
        rec = sys.setdefault("bank_transfer_daily", {}).setdefault(str(sender.id), {})
        rec.update({"date": _today_key(), "sent": sent_today + amount})
        self.system_db.save()

        out_id = self._record_transaction(
            guild.id, user_id=sender.id, kind="bank_transfer_out", amount=amount,
            source="bank_transfer", description=f"Transfer → {recipient.display_name}",
            splits={"recipient_id": recipient.id, "fee": fee, "treasury": treasury_fee, "burned": burned_fee},
        )
        in_id = self._record_transaction(
            guild.id, user_id=recipient.id, kind="bank_transfer_in", amount=amount,
            source="bank_transfer", description=f"Transfer ← {sender.display_name}",
            splits={"sender_id": sender.id},
        )
        await self._economy_log(
            guild,
            f"💸 Bank Transfer — TX #{out_id}",
            f"**From:** {sender.mention}\n**To:** {recipient.mention}\n"
            f"**Amount:** **{cfg.fmt_money(amount)}**\n**Fee:** **{cfg.fmt_money(fee)}**\n"
            f"🏛️ Treasury fee: {cfg.fmt_money(treasury_fee)} • 🔥 Burn: {cfg.fmt_money(burned_fee)}",
            discord.Color.blurple(),
        )
        try:
            await recipient.send(
                f"🏦 توصّلتي بتحويل Bank ديال **{cfg.fmt_money(amount)}** من **{sender.display_name}** "
                f"فـ {guild.name}. TX #{in_id}"
            )
        except (discord.Forbidden, discord.HTTPException):
            pass
        await self.refresh_economy_stats(guild)
        return True, (
            f"✅ تصيفطات **{cfg.fmt_money(amount)}** لـ {recipient.mention}.\n"
            f"💸 Fee: **{cfg.fmt_money(fee)}** • 🏦 Bank دابا: **{cfg.fmt_money(sender_bank-total)}**"
        )

    async def process_bank_interest(self, guild: discord.Guild) -> int:
        """Pays one transparent daily savings yield, funded only from Treasury."""
        sys = self._system(guild.id)
        today = _today_key()
        if sys.get("bank_interest_last_day") == today:
            return 0

        minimum = int(getattr(cfg, "BANK_INTEREST_MIN_BALANCE", 2500) or 2500)
        account_cap = int(getattr(cfg, "BANK_INTEREST_DAILY_ACCOUNT_CAP", 2500) or 2500)
        wanted = []
        for uid_str, raw_balance in list(sys.get("bank_accounts", {}).items()):
            balance = max(0, int(raw_balance or 0))
            if balance < minimum:
                continue
            try:
                uid = int(uid_str)
            except (TypeError, ValueError):
                continue
            bps = self.get_bank_interest_bps(guild.id, uid)
            interest = min(account_cap, balance * bps // 10000)
            if interest > 0:
                wanted.append((uid, interest, bps))

        total_wanted = sum(x[1] for x in wanted)
        treasury = max(0, int(sys.get("treasury", 0) or 0))
        budget_pct = int(getattr(cfg, "BANK_INTEREST_TREASURY_BUDGET_PERCENT", 5) or 5)
        budget = min(treasury, treasury * max(0, min(100, budget_pct)) // 100)
        paid_total = 0

        for uid, interest, bps in wanted:
            if total_wanted <= 0 or budget <= 0:
                paid = 0
            elif total_wanted <= budget:
                paid = interest
            else:
                paid = max(0, interest * budget // total_wanted)
            if paid <= 0:
                continue
            sys["bank_accounts"][str(uid)] = int(sys["bank_accounts"].get(str(uid), 0) or 0) + paid
            paid_total += paid
            self._record_transaction(
                guild.id, user_id=uid, kind="bank_interest", amount=paid,
                source="savings", description=f"Daily Savings Interest ({bps/100:.2f}%)",
                splits={"rate_bps": bps},
            )

        sys["treasury"] = max(0, treasury - paid_total)
        sys["total_interest_paid"] = int(sys.get("total_interest_paid", 0) or 0) + paid_total
        sys["bank_interest_last_day"] = today
        self.system_db.save()
        if paid_total:
            await self._economy_log(
                guild, "📈 Daily Savings Interest",
                f"**Total paid:** {cfg.fmt_money(paid_total)}\n"
                f"**Accounts:** {sum(1 for _,i,_ in wanted if i > 0)}\n"
                "Interest was funded from Treasury; no money was created.",
                discord.Color.green(),
            )
            await self.refresh_economy_stats(guild)
        return paid_total

    @tasks.loop(minutes=60)
    async def bank_interest_loop(self):
        for guild in self.bot.guilds:
            await self.process_bank_interest(guild)

    @bank_interest_loop.before_loop
    async def before_bank_interest_loop(self):
        await self.bot.wait_until_ready()

    def get_owned_assets(self, guild_id: int, user_id: int) -> dict:
        return dict(self._acc(guild_id, user_id).get("assets") or {})

    def get_assets_value(self, guild_id: int, user_id: int) -> int:
        return sum(max(0, int(a.get("paid_price", 0) or 0)) for a in self.get_owned_assets(guild_id, user_id).values())

    async def sell_asset(self, guild: discord.Guild, user: discord.Member, item_id: str) -> Tuple[bool, str]:
        acc = self._acc(guild.id, user.id)
        assets = acc.setdefault("assets", {})
        asset = assets.get(item_id)
        if not asset:
            return False, "❌ هاد Asset ماشي عندك."
        paid_price = max(0, int(asset.get("paid_price", 0) or 0))
        resale_pct = int(getattr(cfg, "ASSET_RESALE_PERCENT", 40) or 40)
        resale = paid_price * resale_pct // 100
        sys = self._system(guild.id)
        if int(sys.get("treasury", 0) or 0) < resale:
            return False, "❌ السوق ماعندوش Liquidity كافية دابا لهاد البيع. جرب من بعد."
        sys["treasury"] -= resale
        assets.pop(item_id, None)
        self.add_coins(guild.id, user.id, resale, source="asset_sale", respect_cap=False, count_as_earned=False)
        self.db.save(); self.system_db.save()
        tx_id = self._record_transaction(
            guild.id, user_id=user.id, kind="asset_sale", amount=resale,
            source=item_id, description=f"Asset resale: {asset.get('name', item_id)}",
            splits={"original_paid": paid_price, "resale_percent": resale_pct},
        )
        await self._economy_log(
            guild, f"🏠 Asset Sale — TX #{tx_id}",
            f"**Member:** {user.mention}\n**Asset:** {asset.get('emoji','🏠')} {asset.get('name',item_id)}\n"
            f"**Paid by market:** {cfg.fmt_money(resale)}",
            discord.Color.orange(),
        )
        await self.refresh_economy_stats(guild)
        return True, f"✅ تباع **{asset.get('name', item_id)}** بـ **{cfg.fmt_money(resale)}** ودخلو للWallet."

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
            "loan_base": 2500,
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
                f"**Bonus:** **+{cfg.fmt_money(granted)}** ({pct}%)\n"
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
                "base_limit": 2500, "interest": 16, "term_days": 2,
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
        min_amount = int(getattr(cfg, "LOAN_MIN_AMOUNT", 2500) or 2500)
        if amount < min_amount:
            return False, f"❌ أقل قرض هو **{cfg.fmt_money(min_amount)}**."

        existing = self.get_active_loan(guild.id, user.id)
        if existing:
            due_ts = self._loan_due_unix(existing)
            state = "⚠️ متأخر" if self._loan_is_overdue(existing) else "🟢 خدام"
            return False, (
                f"❌ عندك قرض {state} ديجا: **{cfg.fmt_money(int(existing['remaining']))}** باقي.\n"
                f"📅 الأجل: <t:{due_ts}:F> (<t:{due_ts}:R>)\n"
                "خاصك تساليه قبل ما تاخد قرض جديد."
            )

        terms = self.get_loan_terms(guild.id, user.id)
        score = int(terms["credit_score"])
        level = int(terms["level"])
        limit = int(terms["effective_limit"])
        min_amount = int(getattr(cfg, "LOAN_MIN_AMOUNT", 2500) or 2500)

        if limit < min_amount:
            return False, (
                f"❌ البنك ما يقدرش يخرج ليك قرض دابا.\n"
                f"⭐ Level: **{level}** ({terms['tier_name']})\n"
                f"💳 Credit Score: **{score}/100**\n"
                f"🏛️ الحد الفعلي حسب السيولة: **{cfg.fmt_money(limit)}**\n"
                "طلع XP / حسن Credit Score / خلي Treasury تكبر ومن بعد عاود."
            )

        if amount > limit:
            return False, (
                f"❌ الحد الفعلي ديالك دابا هو **{cfg.fmt_money(limit)}**.\n"
                f"⭐ Level **{level}** — {terms['tier_name']} | "
                f"Base **{cfg.fmt_money(terms['base_limit'])}**\n"
                f"💳 Credit **{score}/100** (×{terms['credit_multiplier']:.2f}) | "
                f"🏛️ Liquidity Cap **{cfg.fmt_money(terms['liquidity_cap'])}**"
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
                f"**Principal:** **{cfg.fmt_money(amount)}**\n"
                f"**الفائدة ({interest_pct}%):** **{cfg.fmt_money(interest)}**\n"
                f"**المطلوب يرجع:** **{cfg.fmt_money(total_due)}**\n"
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
            f"💵 دخل للـWallet: **{cfg.fmt_money(amount)}**\n"
            f"⭐ Level **{level}** — **{terms['tier_name']}**\n"
            f"📈 الفائدة: **{cfg.fmt_money(interest)}** (**{interest_pct}%**)\n"
            f"💳 خاصك ترجع: **{cfg.fmt_money(total_due)}**\n"
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
                f"**الأداء:** **{cfg.fmt_money(paid)}**\n"
                f"**من:** {source_label}\n"
                f"🏛️ Treasury: **+{cfg.fmt_money(int(breakdown['treasury']))}**\n"
                f"🔥 Burn من الفائدة: **{cfg.fmt_money(int(breakdown['burn']))}**\n"
                f"**الباقي:** **{cfg.fmt_money(int(loan['remaining']))}**"
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
            parts.append(f"Bank {cfg.fmt_money(from_bank)}")
        if from_wallet:
            parts.append(f"Wallet {cfg.fmt_money(from_wallet)}")
        paid, updated = await self._apply_loan_payment(
            guild, user, actual,
            reason="أداء يدوي للقرض",
            source_label=" + ".join(parts),
        )

        if not updated:
            return False, "❌ القرض ماعادش موجود."
        if int(updated.get("remaining", 0) or 0) <= 0:
            return True, (
                f"✅ تسالا القرض **#{updated.get('id')}** كامل! خلصتي **{cfg.fmt_money(paid)}** دابا.\n"
                f"⭐ Credit Score ديالك دابا: **{self.get_credit_score(guild.id, user.id)}/100**"
            )
        return True, (
            f"✅ تخلص **{cfg.fmt_money(paid)}** من القرض.\n"
            f"💳 باقي عليك: **{cfg.fmt_money(int(updated['remaining']))}**\n"
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
                    f"**الباقي:** **{cfg.fmt_money(int(loan.get('remaining', 0)))}**\n"
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
            labels.append(f"Bank {cfg.fmt_money(from_bank)}")
        if from_wallet:
            labels.append(f"Wallet {cfg.fmt_money(from_wallet)}")
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
                        f"⚠️ تخلص أوتوماتيكياً **{cfg.fmt_money(paid)}** من القرض المتأخر. "
                        f"باقي **{cfg.fmt_money(int(updated.get('remaining', 0)))}**."
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
            return False, "❌ Wallet ماكافيش."

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

        if bank_part > 0:
            new_bank = self.get_bank_balance(guild.id, user.id) + bank_part
            self._set_bank_balance(guild.id, user.id, new_bank)
            tx_id = self._record_transaction(
                guild.id, user_id=user.id, kind="bank_deposit", amount=bank_part,
                source="bank", description="Wallet → Bank deposit"
            )
            await self._economy_log(
                guild, f"🏦 Bank Deposit — TX #{tx_id}",
                f"**العضو:** {user.mention}\n**Deposit:** **{cfg.fmt_money(bank_part)}**\n"
                f"**Bank Balance:** **{cfg.fmt_money(new_bank)}**",
                discord.Color.green(),
            )

        extra = ""
        if debt_paid:
            extra = f"\n⚠️ **{cfg.fmt_money(debt_paid)}** مشاو للقرض المتأخر أولاً."
            if bank_part:
                extra += f" الباقي **{cfg.fmt_money(bank_part)}** دخل Savings."

        return True, (
            f"✅ Deposit تم.{extra}\n"
            f"🏦 Bank: **{cfg.fmt_money(self.get_bank_balance(guild.id, user.id))}** | "
            f"💳 Wallet: **{cfg.fmt_money(self.get_balance(guild.id, user.id))}**"
        )

    async def bank_withdraw(self, guild: discord.Guild, user: discord.abc.User, amount: int) -> Tuple[bool, str]:
        amount = int(amount)
        if amount <= 0:
            return False, "❌ المبلغ خاصو يكون أكبر من 0."
        bank = self.get_bank_balance(guild.id, user.id)
        if bank < amount:
            return False, f"❌ Bank ماكافيش. عندك **{cfg.fmt_money(bank)}**."

        self._set_bank_balance(guild.id, user.id, bank - amount)
        self.add_coins(
            guild.id, user.id, amount, source="bank_withdraw",
            respect_cap=False, count_as_earned=False
        )
        tx_id = self._record_transaction(
            guild.id, user_id=user.id, kind="bank_withdraw", amount=amount,
            source="bank", description="Bank → Wallet withdrawal"
        )
        await self._economy_log(
            guild, f"💸 Bank Withdraw — TX #{tx_id}",
            f"**العضو:** {user.mention}\n**Withdraw:** **{cfg.fmt_money(amount)}**\n"
            f"**Bank Balance:** **{cfg.fmt_money(bank - amount)}**",
            discord.Color.orange(),
        )
        return True, (
            f"✅ خرجتي **{cfg.fmt_money(amount)}** من البنك.\n"
            f"🏦 Bank: **{cfg.fmt_money(bank - amount)}** | "
            f"💳 Wallet: **{cfg.fmt_money(self.get_balance(guild.id, user.id))}**"
        )

    def build_bank_panel_embed(self, guild: discord.Guild) -> discord.Embed:
        sys = self._system(guild.id)
        embed = discord.Embed(
            title="🏦 GGMW9 Central Bank",
            description=(
                "**Bank حقيقي داخل اقتصاد السيرفر:** Wallet، Savings، Transfers، Loans، Credit وAssets.\n\n"
                "💳 **Wallet** — اللعب والشراء.\n"
                "🏦 **Savings** — محمية من الرهانات وكتربح Daily Interest من Treasury.\n"
                "💸 **Transfers** — Bank→Bank مع Ledger وFee واضحة.\n"
                "💳 **Loans** — ممولة من Treasury؛ Credit + Level كيحددو الشروط.\n"
                "🏠 **Assets** — ممتلكات كتدخل فـNet Worth ويمكن تعاود تبيعها.\n\n"
                "💡 الاقتصاد ماكيخلقش Interest من والو: Savings yield كتخلص من Treasury."
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="🏛️ Treasury", value=f"**{cfg.fmt_money(sys['treasury'])}**", inline=True)
        embed.add_field(name="🎰 Global Jackpot", value=f"**{cfg.fmt_money(sys['jackpot'])}**", inline=True)
        embed.add_field(name="🎉 Events Fund", value=f"**{cfg.fmt_money(sys['events'])}**", inline=True)
        embed.add_field(
            name="📈 Savings Rate",
            value=(
                f"Base **{getattr(cfg,'BANK_INTEREST_BASE_BPS_DAILY',5)/100:.2f}%/day**\n"
                f"Min balance **{cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}**\n"
                "Level وShop pass يقدرو يزيدو rate."
            ), inline=True,
        )
        embed.add_field(
            name="💸 Transfers",
            value=(
                f"Base fee **{getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%**\n"
                f"Daily limit من **{cfg.fmt_money(getattr(cfg,'BANK_TRANSFER_DAILY_LIMIT',100000))}**"
            ), inline=True,
        )
        embed.add_field(
            name="💵 USD Re-denomination",
            value="الأرصدة القديمة ما تحيد منها والو: كل 100 وحدة قديمة كتظهر دابا **$1.00**. نفس القيمة الداخلية محفوظة.",
            inline=False,
        )
        embed.set_footer(text="GGMW9 Bank • real ledger • no hidden balance reset")
        return embed

    def build_global_economy_embed(self, guild: discord.Guild) -> discord.Embed:
        sys = self._system(guild.id)
        guild_data = self.db.guild(guild.id)
        wallets = sum(max(0, int(acc.get("coins", 0) or 0)) for acc in guild_data.values())
        bank_total = sum(max(0, int(v or 0)) for v in sys.get("bank_accounts", {}).values())
        assets_total = sum(
            sum(max(0, int(a.get("paid_price", 0) or 0)) for a in (acc.get("assets") or {}).values())
            for acc in guild_data.values()
        )
        active_loans = [
            loan for loan in sys.get("loans", {}).values()
            if loan and int(loan.get("remaining", 0) or 0) > 0
        ]
        loans_outstanding = sum(int(loan.get("remaining", 0) or 0) for loan in active_loans)
        overdue_loans = sum(1 for loan in active_loans if self._loan_is_overdue(loan))
        live_supply = wallets + bank_total + sys["treasury"] + sys["jackpot"] + sys["events"]

        embed = discord.Embed(
            title="📊 اقتصاد GGMW9 — Live",
            description="USD economy: Wallet + Bank + Treasury + Casino + Shop + Assets.",
            color=discord.Color.blurple(), timestamp=datetime.now(),
        )
        embed.add_field(name="💳 Wallets", value=f"**{cfg.fmt_money(wallets)}**", inline=True)
        embed.add_field(name="🏦 Bank Deposits", value=f"**{cfg.fmt_money(bank_total)}**", inline=True)
        embed.add_field(name="🏛️ Treasury", value=f"**{cfg.fmt_money(sys['treasury'])}**", inline=True)
        embed.add_field(name="🎰 Jackpot", value=f"**{cfg.fmt_money(sys['jackpot'])}**", inline=True)
        embed.add_field(name="🎉 Events", value=f"**{cfg.fmt_money(sys['events'])}**", inline=True)
        embed.add_field(name="🔥 Burned", value=f"**{cfg.fmt_money(sys['burned'])}**", inline=True)
        embed.add_field(name="📉 Casino Losses", value=f"**{cfg.fmt_money(sys['total_gambling_lost'])}**", inline=True)
        embed.add_field(name="🛒 Shop Spend", value=f"**{cfg.fmt_money(sys['total_shop_spent'])}**", inline=True)
        embed.add_field(name="🏆 Jackpot Paid", value=f"**{cfg.fmt_money(sys['total_jackpot_paid'])}**", inline=True)
        embed.add_field(name="📈 Interest Paid", value=f"**{cfg.fmt_money(sys.get('total_interest_paid',0))}**", inline=True)
        embed.add_field(name="💸 Transfer Fees", value=f"**{cfg.fmt_money(sys.get('total_transfer_fees',0))}**", inline=True)
        embed.add_field(name="🏠 Asset Book Value", value=f"**{cfg.fmt_money(assets_total)}**", inline=True)
        embed.add_field(name="💳 Loans Outstanding", value=f"**{cfg.fmt_money(loans_outstanding)}**", inline=True)
        embed.add_field(name="⚠️ Overdue Loans", value=f"**{overdue_loans}**", inline=True)
        embed.add_field(name="💹 Live Money Supply", value=f"**{cfg.fmt_money(live_supply)}**", inline=False)
        embed.set_footer(text="Burn + Assets ما داخلينش فـliquid supply | Interest funded by Treasury")
        return embed

    def build_user_account_embed(self, guild: discord.Guild, user: discord.abc.User) -> discord.Embed:
        wallet = self.get_balance(guild.id, user.id)
        bank = self.get_bank_balance(guild.id, user.id)
        assets_value = self.get_assets_value(guild.id, user.id)
        terms = self.get_loan_terms(guild.id, user.id)
        net_worth = wallet + bank + assets_value
        rate_bps = self.get_bank_interest_bps(guild.id, user.id)
        sent_today = self.get_transfer_sent_today(guild.id, user.id)
        transfer_limit = self.get_transfer_daily_limit(guild.id, user.id)
        fee_free = self._perk_active(guild.id, user.id, "transfer_fee_pass_expires")

        embed = discord.Embed(
            title=f"🏦 حساب {user.display_name}",
            description=f"**Net Worth: {cfg.fmt_money(net_worth)}**",
            color=discord.Color.green(),
        )
        embed.add_field(name="💳 Wallet", value=f"**{cfg.fmt_money(wallet)}**", inline=True)
        embed.add_field(name="🏦 Savings", value=f"**{cfg.fmt_money(bank)}**", inline=True)
        embed.add_field(name="🏠 Assets", value=f"**{cfg.fmt_money(assets_value)}**", inline=True)
        embed.add_field(
            name="📈 Savings Yield",
            value=(f"**{rate_bps/100:.2f}% / day**\n"
                   f"Min: {cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}\n"
                   "Treasury-funded"), inline=True,
        )
        embed.add_field(
            name="💸 Transfers اليوم",
            value=(f"{cfg.fmt_money(sent_today)} / {cfg.fmt_money(transfer_limit)}\n"
                   + ("✅ Fee Pass active" if fee_free else f"Fee {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")),
            inline=True,
        )
        embed.add_field(
            name="💳 Credit",
            value=f"**{terms['credit_score']}/100** • {terms['tier_name']} • Lv {terms['level']}",
            inline=True,
        )
        embed.add_field(
            name="🏦 Loan Terms",
            value=(f"Limit: **{cfg.fmt_money(terms['effective_limit'])}**\n"
                   f"Interest: **{terms['interest_percent']}%** • Term: **{terms['term_days']}d**"),
            inline=False,
        )
        loan = self.get_active_loan(guild.id, user.id)
        if loan:
            state = "⚠️ Overdue" if self._loan_is_overdue(loan) else "🟢 Active"
            embed.add_field(
                name=f"💳 Loan #{loan.get('id')} — {state}",
                value=(f"Remaining: **{cfg.fmt_money(int(loan.get('remaining',0)))}**\n"
                       f"Due: <t:{self._loan_due_unix(loan)}:F> (<t:{self._loan_due_unix(loan)}:R>)"),
                inline=False,
            )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="Savings ماكيدخلش Casino حتى تسحبو | Assets تقدر تبيعهم من Bank")
        return embed

    def build_xp_bank_perks_embed(self, guild: discord.Guild, user: discord.abc.User) -> discord.Embed:
        terms = self.get_loan_terms(guild.id, user.id)
        next_tier = self.get_next_xp_loan_tier(guild.id, user.id)
        embed = discord.Embed(
            title=f"⭐ Bank Privileges — {user.display_name}",
            description="Level كيزيد Loan capacity وكيحسن Savings rate وTransfer limit؛ Credit كيقيس الالتزام بالأداء.",
            color=discord.Color.gold(),
        )
        embed.add_field(
            name="📊 دابا",
            value=(f"⭐ Lv **{terms['level']}** — {terms['tier_name']}\n"
                   f"💳 Credit **{terms['credit_score']}/100**\n"
                   f"📈 Savings **{self.get_bank_interest_bps(guild.id,user.id)/100:.2f}%/day**\n"
                   f"💸 Transfer limit **{cfg.fmt_money(self.get_transfer_daily_limit(guild.id,user.id))}/day**"),
            inline=False,
        )
        embed.add_field(
            name="💰 Loan",
            value=(f"Base: **{cfg.fmt_money(terms['base_limit'])}**\n"
                   f"After Credit: **{cfg.fmt_money(terms['credit_adjusted_limit'])}**\n"
                   f"Liquidity Cap: **{cfg.fmt_money(terms['liquidity_cap'])}**\n"
                   f"✅ Effective: **{cfg.fmt_money(terms['effective_limit'])}**\n"
                   f"Interest **{terms['interest_percent']}%** • **{terms['term_days']}d**"),
            inline=False,
        )
        if next_tier:
            embed.add_field(
                name="🚀 Next Tier",
                value=(f"Lv **{int(next_tier.get('min_level',0))}** — {next_tier.get('name','Tier')}\n"
                       f"Base Loan **{cfg.fmt_money(int(next_tier.get('base_limit',0)))}** • "
                       f"{int(next_tier.get('interest',0))}% • {int(next_tier.get('term_days',0))}d"),
                inline=False,
            )
        embed.set_thumbnail(url=user.display_avatar.url)
        return embed

    def build_user_transactions_embed(self, guild: discord.Guild, user: discord.abc.User) -> discord.Embed:
        txs = self.get_user_transactions(guild.id, user.id, limit=12)
        if not txs:
            return discord.Embed(title="🧾 آخر المعاملات", description="📭 ماكايناش معاملات مسجلة.", color=discord.Color.blurple())
        kind_icons = {
            "gambling_loss":"🎰", "shop_purchase":"🛒", "jackpot_payout":"🏆",
            "bank_deposit":"🏦", "bank_withdraw":"💸", "bank_transfer_out":"📤",
            "bank_transfer_in":"📥", "bank_interest":"📈", "asset_sale":"🏠",
            "loan_issued":"💳", "loan_repayment":"💸", "loan_paid":"✅",
            "level_daily_bonus":"⭐", "admin_adjustment":"🛡️",
        }
        lines=[]
        for tx in txs:
            icon=kind_icons.get(tx.get("kind"),"💱")
            try:
                unix=int(datetime.fromisoformat(tx.get("ts","")).timestamp()); when=f"<t:{unix}:R>"
            except Exception:
                when="—"
            lines.append(
                f"{icon} **TX #{tx.get('id')}** • {tx.get('description',tx.get('source','عملية'))} • "
                f"**{cfg.fmt_money(int(tx.get('amount',0)))}** • {when}"
            )
        return discord.Embed(title=f"🧾 معاملات {user.display_name}", description="\n".join(lines), color=discord.Color.blurple())

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
            await self.process_bank_interest(guild)
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
                "assets": {},
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
    async def balance_cmd(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        target = member or ctx.author
        acc = self._acc(ctx.guild.id, target.id)
        wallet = self.get_balance(ctx.guild.id, target.id)
        bank = self.get_bank_balance(ctx.guild.id, target.id)
        assets = self.get_assets_value(ctx.guild.id, target.id)
        embed = discord.Embed(title=f"💵 {target.display_name}", color=discord.Color.gold(), timestamp=datetime.now())
        embed.add_field(name="💳 Wallet", value=f"**{cfg.fmt_money(wallet)}**", inline=True)
        embed.add_field(name="🏦 Bank", value=f"**{cfg.fmt_money(bank)}**", inline=True)
        embed.add_field(name="🏠 Assets", value=f"**{cfg.fmt_money(assets)}**", inline=True)
        embed.add_field(name="💰 Net Worth", value=f"**{cfg.fmt_money(wallet+bank+assets)}**", inline=False)
        embed.add_field(name="📊 Daily reward cap", value=f"باقي **{cfg.fmt_money(self.daily_remaining(ctx.guild.id,target.id))}** اليوم", inline=False)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="daily", aliases=["يومي"], description="خود المكافأة اليومية ديالك 💵",
    )
    async def daily_cmd(self, ctx: commands.Context):
        acc = self._acc(ctx.guild.id, ctx.author.id)
        now = datetime.now(timezone.utc)
        last = acc.get("daily_last")
        if last:
            try:
                last_dt=datetime.fromisoformat(last); elapsed=now-last_dt
                if elapsed < timedelta(hours=cfg.COOLDOWN_DAILY_HOURS):
                    ready_at=last_dt+timedelta(hours=cfg.COOLDOWN_DAILY_HOURS)
                    await ctx.send(f"⏳ رجع <t:{int(ready_at.timestamp())}:R> باش تاخد Daily.", ephemeral=True); return
                if elapsed > timedelta(hours=48): acc["daily_streak"]=0
            except (ValueError,TypeError): pass
        acc["daily_streak"]=acc.get("daily_streak",0)+1
        bonus=min(cfg.COINS_DAILY_STREAK_BONUS*(acc["daily_streak"]-1),cfg.COINS_DAILY_STREAK_MAX)
        total=cfg.COINS_DAILY+bonus
        level_bonus, level_bonus_pct, level_bonus_wanted = await self.grant_level_daily_bonus(ctx.guild,ctx.author,total)
        final_total=total+level_bonus
        acc["daily_last"]=now.isoformat(); self.db.save()
        self.add_coins(ctx.guild.id,ctx.author.id,final_total,source="daily",respect_cap=False)
        embed=discord.Embed(title="🎁 Daily Paycheck",description=f"دخل ليك **{cfg.fmt_money(final_total)}**",color=discord.Color.green())
        if bonus>0: embed.add_field(name="🔥 Streak",value=f"+{cfg.fmt_money(bonus)} • day {acc['daily_streak']}",inline=False)
        if level_bonus>0: embed.add_field(name="⭐ Level Bonus",value=f"+{cfg.fmt_money(level_bonus)} (+{level_bonus_pct}% من Treasury)",inline=False)
        elif level_bonus_pct>0 and level_bonus_wanted>0: embed.add_field(name="⭐ Level Bonus",value="Treasury liquidity ماكفاتش للبونوس دابا.",inline=False)
        embed.add_field(name="💳 Wallet",value=f"**{cfg.fmt_money(self.get_balance(ctx.guild.id,ctx.author.id))}**",inline=False)
        await ctx.send(embed=embed)

    def build_richest_embed(self, guild: discord.Guild) -> discord.Embed:
        guild_data=self.db.guild(guild.id)
        ranked=[]
        for uid,data in guild_data.items():
            member=guild.get_member(int(uid)) if str(uid).isdigit() else None
            if not member: continue
            net=int(data.get("coins",0) or 0)+self.get_bank_balance(guild.id,int(uid))+self.get_assets_value(guild.id,int(uid))
            ranked.append((member,net))
        ranked.sort(key=lambda x:x[1],reverse=True); ranked=ranked[:10]
        if not ranked:
            return discord.Embed(title="💵 أغنى الأعضاء",description="📭 مازال ماكاينش ranking.",color=discord.Color.gold())
        medals=["🥇","🥈","🥉"]; lines=[]
        for i,(member,net) in enumerate(ranked):
            prefix=medals[i] if i<3 else f"`#{i+1}`"
            lines.append(f"{prefix} **{member.display_name}** — **{cfg.fmt_money(net)}** Net Worth")
        return discord.Embed(title="💵 GGMW9 Rich List",description="\n".join(lines),color=discord.Color.gold(),timestamp=datetime.now())

    def admin_give(self, guild: discord.Guild, member: discord.Member, amount: int) -> str:
        self.add_coins(guild.id, member.id, amount, source="admin", respect_cap=False)
        verb = "تزادو لـ" if amount >= 0 else "تحيدو من"
        return (
            f"✅ **{cfg.fmt_money(abs(amount))}** {verb} {member.mention}\n"
            f"الرصيد الجديد: **{cfg.fmt_money(self.get_balance(guild.id, member.id))}**"
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
                    f"💰 تزادو ليك **{cfg.fmt_money(applied)}** من إدارة السيرفر.\n"
                    f"الرصيد دابا: **{cfg.fmt_money(after)}**"
                )
            else:
                await member.send(
                    f"💸 تحيدو من رصيدك **{cfg.fmt_money(abs(applied))}** من إدارة السيرفر.\n"
                    f"الرصيد دابا: **{cfg.fmt_money(after)}**"
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
                f"**العضو:** {member.mention}\n"
                f"**التغيير الفعلي:** **{cfg.fmt_money(applied, signed=True)}**\n"
                f"**قبل:** **{cfg.fmt_money(before)}** → **بعد:** **{cfg.fmt_money(after)}**\n"
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
        """Hidden prefix fallback; Marketplace الحقيقي Panel/Category based."""
        await ctx.send(
            embed=build_shop_home_embed(self, ctx.guild, ctx.author),
            view=ShopView(self, ctx.author),
        )


    # ════════════════════════════════════════════════
    # أمر givecoins — Owner فقط
    # ════════════════════════════════════════════════

    @commands.command(name="givecoins", hidden=True)
    async def givecoins_cmd(
        self, ctx: commands.Context, member: discord.Member, amount: str
    ):
        """Hidden prefix fallback. Amount is USD input (e.g. 25 or -10.50)."""
        owner_id = getattr(self.bot, "gg", {}).get("OWNER_ID")
        if not owner_id or ctx.author.id != owner_id:
            return
        parsed = cfg.parse_money_input(amount, allow_negative=True)
        if parsed is None or parsed == 0:
            try:
                await ctx.author.send("❌ دخل USD صحيح بحال `25`, `10.50` أو `-5`.")
            except discord.HTTPException:
                pass
            return
        result = await self.owner_adjust_balance(
            ctx.guild, member, parsed, actor=ctx.author
        )
        try:
            await ctx.author.send(
                f"✅ {member} | {cfg.fmt_money(result['applied'], signed=True)} | "
                f"Balance: {cfg.fmt_money(result['after'])}"
            )
        except discord.HTTPException:
            pass



class BankAmountModal(discord.ui.Modal):
    def __init__(self, cog: "Economy", action: str):
        title = "🏦 Deposit فـSavings" if action == "deposit" else "💸 Withdraw من Savings"
        super().__init__(title=title)
        self.cog = cog
        self.action = action
        self.amount = discord.ui.TextInput(
            label="المبلغ بالدولار",
            placeholder="مثال: 25 أو 25.50",
            min_length=1,
            max_length=16,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        amount = cfg.parse_money_input(self.amount.value)
        if amount is None:
            await interaction.response.send_message(
                "❌ دخل مبلغ دولار صحيح أكبر من $0.00. مثال: `25` أو `25.50`.",
                ephemeral=True,
            )
            return
        if self.action == "deposit":
            ok, msg = await self.cog.bank_deposit(interaction.guild, interaction.user, amount)
        else:
            ok, msg = await self.cog.bank_withdraw(interaction.guild, interaction.user, amount)
        await interaction.response.send_message(msg, ephemeral=True)


class BankTransferAmountModal(discord.ui.Modal):
    def __init__(self, cog: "Economy", recipient: discord.Member):
        super().__init__(title=f"💸 Transfer → {recipient.display_name}"[:45])
        self.cog = cog
        self.recipient = recipient
        self.amount = discord.ui.TextInput(
            label="المبلغ بالدولار",
            placeholder="مثال: 50 أو 125.75",
            min_length=1,
            max_length=16,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        amount = cfg.parse_money_input(self.amount.value)
        if amount is None:
            await interaction.response.send_message(
                "❌ دخل مبلغ صحيح. مثال: `50` أو `125.75`.", ephemeral=True
            )
            return
        ok, msg = await self.cog.bank_transfer(
            interaction.guild, interaction.user, self.recipient, amount
        )
        await interaction.response.send_message(msg, ephemeral=True)


class BankTransferUserSelect(discord.ui.UserSelect):
    def __init__(self, cog: "Economy", owner_id: int):
        self.cog = cog
        self.owner_id = int(owner_id)
        super().__init__(placeholder="👤 اختار شكون غادي توصّلو الفلوس...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ هاد التحويل ماشي ديالك.", ephemeral=True)
            return
        picked = self.values[0]
        recipient = interaction.guild.get_member(picked.id)
        if recipient is None:
            try:
                recipient = await interaction.guild.fetch_member(picked.id)
            except Exception:
                recipient = None
        if recipient is None:
            await interaction.response.send_message("❌ ما قدرتش نجيب هاد العضو.", ephemeral=True)
            return
        if recipient.bot:
            await interaction.response.send_message("❌ مايمكنش تحول لـBot.", ephemeral=True)
            return
        if recipient.id == interaction.user.id:
            await interaction.response.send_message("❌ مايمكنش تحول لنفسك.", ephemeral=True)
            return
        await interaction.response.send_modal(BankTransferAmountModal(self.cog, recipient))


class BankTransferUserView(discord.ui.View):
    def __init__(self, cog: "Economy", owner_id: int):
        super().__init__(timeout=120)
        self.add_item(BankTransferUserSelect(cog, owner_id))


class LoanRequestModal(discord.ui.Modal):
    def __init__(self, cog: "Economy", guild_id: int, user_id: int):
        terms = cog.get_loan_terms(guild_id, user_id)
        limit = int(terms["effective_limit"])
        minimum = int(getattr(cfg, "LOAN_MIN_AMOUNT", 2500))
        super().__init__(title="💳 طلب قرض من GGMW9 Bank")
        self.cog = cog
        self.amount = discord.ui.TextInput(
            label="شحال بغيتي تسلف بالدولار؟",
            placeholder=f"{cfg.fmt_money(minimum)} → {cfg.fmt_money(limit)}",
            min_length=1,
            max_length=16,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        amount = cfg.parse_money_input(self.amount.value)
        if amount is None:
            await interaction.response.send_message("❌ دخل مبلغ دولار صحيح.", ephemeral=True)
            return
        ok, msg = await self.cog.request_loan(interaction.guild, interaction.user, amount)
        await interaction.response.send_message(msg, ephemeral=True)


class LoanRepayModal(discord.ui.Modal):
    def __init__(self, cog: "Economy", loan: dict):
        super().__init__(title=f"💸 أداء Loan #{loan.get('id')}")
        self.cog = cog
        self.amount = discord.ui.TextInput(
            label="شحال بغيتي تخلص دابا بالدولار؟",
            placeholder=f"الباقي {cfg.fmt_money(int(loan.get('remaining', 0)))}",
            min_length=1,
            max_length=16,
            required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        amount = cfg.parse_money_input(self.amount.value)
        if amount is None:
            await interaction.response.send_message("❌ دخل مبلغ دولار صحيح.", ephemeral=True)
            return
        ok, msg = await self.cog.repay_loan(interaction.guild, interaction.user, amount)
        await interaction.response.send_message(msg, ephemeral=True)


def _build_savings_embed(cog: "Economy", guild: discord.Guild, user: discord.Member) -> discord.Embed:
    bank = cog.get_bank_balance(guild.id, user.id)
    bps = cog.get_bank_interest_bps(guild.id, user.id)
    minimum = int(getattr(cfg, "BANK_INTEREST_MIN_BALANCE", 2500))
    cap = int(getattr(cfg, "BANK_INTEREST_DAILY_ACCOUNT_CAP", 2500))
    estimate = min(cap, bank * bps // 10000) if bank >= minimum else 0
    boost = cog._perk_active(guild.id, user.id, "bank_interest_boost_expires")
    embed = discord.Embed(
        title="📈 Savings Account",
        description=(
            f"🏦 Balance: **{cfg.fmt_money(bank)}**\n"
            f"📈 Rate ديالك: **{bps/100:.2f}% / day**\n"
            f"🧮 Estimated next yield: **{cfg.fmt_money(estimate)}**\n\n"
            "الأرباح كتخلص **غير من Treasury** وما كنخلقوش فلوس من والو. "
            "إلا ميزانية Treasury اليومية ماكفاتش، الأرباح كتتوزع proportional بين الحسابات المؤهلة."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(name="Minimum eligible balance", value=cfg.fmt_money(minimum), inline=True)
    embed.add_field(name="Daily account cap", value=cfg.fmt_money(cap), inline=True)
    embed.add_field(name="Shop Rate Boost", value="✅ Active" if boost else "—", inline=True)
    embed.set_footer(text="Savings كتخلص مرة وحدة فكل UTC day")
    return embed


def _build_assets_embed(cog: "Economy", guild: discord.Guild, user: discord.Member) -> discord.Embed:
    assets = cog.get_owned_assets(guild.id, user.id)
    book = cog.get_assets_value(guild.id, user.id)
    resale_pct = int(getattr(cfg, "ASSET_RESALE_PERCENT", 40))
    if not assets:
        desc = "📭 ماعندك حتى Asset دابا. شري الممتلكات من 🛒 Shop → 🏠 Assets."
    else:
        lines = []
        for item_id, a in assets.items():
            paid = int(a.get("paid_price", 0) or 0)
            resale = paid * resale_pct // 100
            lines.append(
                f"{a.get('emoji','🏠')} **{a.get('name',item_id)}** • Book {cfg.fmt_money(paid)} • Sell {cfg.fmt_money(resale)}"
            )
        desc = "\n".join(lines)
    embed = discord.Embed(
        title=f"🏠 Assets — {user.display_name}", description=desc, color=discord.Color.gold()
    )
    embed.add_field(name="Book Value", value=f"**{cfg.fmt_money(book)}**", inline=True)
    embed.add_field(name="Market resale", value=f"**{resale_pct}%** of paid price", inline=True)
    embed.set_footer(text="Resale كيتخلص من Treasury liquidity؛ Assets كيدخلو فـNet Worth")
    return embed


class AssetSellSelect(discord.ui.Select):
    def __init__(self, cog: "Economy", user: discord.Member):
        self.cog = cog
        self.user = user
        assets = cog.get_owned_assets(user.guild.id, user.id)
        options = []
        resale_pct = int(getattr(cfg, "ASSET_RESALE_PERCENT", 40))
        for item_id, a in list(assets.items())[:25]:
            paid = int(a.get("paid_price", 0) or 0)
            options.append(discord.SelectOption(
                label=f"{a.get('name',item_id)} — {cfg.fmt_money(paid * resale_pct // 100)}",
                value=item_id,
                emoji=a.get("emoji", "🏠"),
                description="Sell back to market"[:100],
            ))
        super().__init__(placeholder="🏷️ اختار Asset باش تبيعها...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ هاد Assets ماشي ديالك.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        ok, msg = await self.cog.sell_asset(interaction.guild, interaction.user, self.values[0])
        await interaction.edit_original_response(
            content=msg,
            embed=_build_assets_embed(self.cog, interaction.guild, interaction.user),
            view=AssetsView(self.cog, interaction.user),
        )


class AssetsView(discord.ui.View):
    def __init__(self, cog: "Economy", user: discord.Member):
        super().__init__(timeout=180)
        if cog.get_owned_assets(user.guild.id, user.id):
            self.add_item(AssetSellSelect(cog, user))


class EconomyBankPanelView(discord.ui.View):
    """Central Bank persistent panel: Wallet, Savings, transfers, loans, assets."""

    def __init__(self, cog: "Economy"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="💳 حسابي", style=discord.ButtonStyle.primary, custom_id="ggmw9:economy:account", row=0)
    async def account_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=self.cog.build_user_account_embed(interaction.guild, interaction.user), ephemeral=True
        )

    @discord.ui.button(label="🏦 Deposit", style=discord.ButtonStyle.success, custom_id="ggmw9:economy:deposit", row=0)
    async def deposit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BankAmountModal(self.cog, "deposit"))

    @discord.ui.button(label="💸 Withdraw", style=discord.ButtonStyle.secondary, custom_id="ggmw9:economy:withdraw", row=0)
    async def withdraw_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(BankAmountModal(self.cog, "withdraw"))

    @discord.ui.button(label="💵 Transfer", style=discord.ButtonStyle.primary, custom_id="ggmw9:economy:transfer", row=0)
    async def transfer_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        sent = self.cog.get_transfer_sent_today(interaction.guild.id, interaction.user.id)
        limit = self.cog.get_transfer_daily_limit(interaction.guild.id, interaction.user.id)
        fee_free = self.cog._perk_active(interaction.guild.id, interaction.user.id, "transfer_fee_pass_expires")
        await interaction.response.send_message(
            (
                f"💵 **Bank→Bank Transfer**\n"
                f"🏦 Savings: **{cfg.fmt_money(self.cog.get_bank_balance(interaction.guild.id, interaction.user.id))}**\n"
                f"📊 Today: **{cfg.fmt_money(sent)} / {cfg.fmt_money(limit)}**\n"
                + ("✅ Fee Pass active\n" if fee_free else f"💸 Fee: **{getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%** (min {cfg.fmt_money(getattr(cfg,'BANK_TRANSFER_MIN_FEE',10))}, max {cfg.fmt_money(getattr(cfg,'BANK_TRANSFER_MAX_FEE',500))})\n")
                + "\nاختار العضو اللي بغيتي تحول ليه:"
            ),
            view=BankTransferUserView(self.cog, interaction.user.id),
            ephemeral=True,
        )

    @discord.ui.button(label="🏛️ Treasury", style=discord.ButtonStyle.secondary, custom_id="ggmw9:economy:treasury", row=0)
    async def treasury_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        sys = self.cog._system(interaction.guild.id)
        embed = discord.Embed(
            title="🏛️ خزينة السيرفر",
            description=(
                f"🏛️ **Treasury:** {cfg.fmt_money(sys['treasury'])}\n"
                f"🎉 **Events Fund:** {cfg.fmt_money(sys['events'])}\n"
                f"🔥 **Burned:** {cfg.fmt_money(sys['burned'])}\n\n"
                "Treasury كتمول Savings Interest، Loans وAsset resale. Burn كيتحيد نهائياً ضد التضخم."
            ), color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎰 Jackpot", style=discord.ButtonStyle.danger, custom_id="ggmw9:economy:jackpot", row=1)
    async def jackpot_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        sys = self.cog._system(interaction.guild.id)
        embed = discord.Embed(
            title="🎰 Progressive Global Jackpot",
            description=(
                f"# **{cfg.fmt_money(sys['jackpot'])}**\n\n"
                "كيكبر من جزء من **الخسارات الحقيقية** ديال Casino. كيتصرف كامل فـ:\n"
                "• 🎰 Slots — `7️⃣ | 7️⃣ | 7️⃣`\n"
                "• 🎫 Scratch — `💰` Jackpot\n"
                "• 🎟️ Lottery — 4/4"
            ), color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="📊 الاقتصاد", style=discord.ButtonStyle.primary, custom_id="ggmw9:economy:stats", row=1)
    async def stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.cog.build_global_economy_embed(interaction.guild), ephemeral=True)

    @discord.ui.button(label="🧾 معاملاتي", style=discord.ButtonStyle.secondary, custom_id="ggmw9:economy:transactions", row=1)
    async def transactions_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.cog.build_user_transactions_embed(interaction.guild, interaction.user), ephemeral=True)

    @discord.ui.button(label="💳 طلب قرض", style=discord.ButtonStyle.success, custom_id="ggmw9:economy:loan_request", row=1)
    async def loan_request_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        loan = self.cog.get_active_loan(interaction.guild.id, interaction.user.id)
        if loan:
            state = "⚠️ متأخر" if self.cog._loan_is_overdue(loan) else "🟢 خدام"
            await interaction.response.send_message(
                f"💳 عندك Loan **#{loan.get('id')}** {state}.\nالباقي: **{cfg.fmt_money(int(loan.get('remaining',0)))}**\nالأجل: <t:{self.cog._loan_due_unix(loan)}:F>",
                ephemeral=True,
            )
            return
        terms = self.cog.get_loan_terms(interaction.guild.id, interaction.user.id)
        min_amount = int(getattr(cfg, "LOAN_MIN_AMOUNT", 2500))
        if int(terms["effective_limit"]) < min_amount:
            await interaction.response.send_message(
                f"❌ الحد الفعلي ديالك دابا **{cfg.fmt_money(terms['effective_limit'])}** وماوصلش للحد الأدنى {cfg.fmt_money(min_amount)}.",
                ephemeral=True,
            )
            return
        await interaction.response.send_modal(LoanRequestModal(self.cog, interaction.guild.id, interaction.user.id))

    @discord.ui.button(label="💸 خلص القرض", style=discord.ButtonStyle.primary, custom_id="ggmw9:economy:loan_repay", row=1)
    async def loan_repay_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        loan = self.cog.get_active_loan(interaction.guild.id, interaction.user.id)
        if not loan:
            await interaction.response.send_message("ℹ️ ماعندك حتى قرض خدام دابا.", ephemeral=True)
            return
        await interaction.response.send_modal(LoanRepayModal(self.cog, loan))

    @discord.ui.button(label="⭐ XP Perks", style=discord.ButtonStyle.secondary, custom_id="ggmw9:economy:xp_perks", row=2)
    async def xp_perks_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=self.cog.build_xp_bank_perks_embed(interaction.guild, interaction.user), ephemeral=True)

    @discord.ui.button(label="📈 Savings", style=discord.ButtonStyle.success, custom_id="ggmw9:economy:savings", row=2)
    async def savings_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=_build_savings_embed(self.cog, interaction.guild, interaction.user), ephemeral=True)

    @discord.ui.button(label="🏠 Assets", style=discord.ButtonStyle.secondary, custom_id="ggmw9:economy:assets", row=2)
    async def assets_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            embed=_build_assets_embed(self.cog, interaction.guild, interaction.user),
            view=AssetsView(self.cog, interaction.user),
            ephemeral=True,
        )


def build_shop_home_embed(cog: "Economy", guild: discord.Guild, user: discord.Member) -> discord.Embed:
    balance = cog.get_balance(guild.id, user.id)
    bank = cog.get_bank_balance(guild.id, user.id)
    discount = cog.get_shop_discount_percent(guild.id, user.id)
    lines = []
    for category_id, cat in cfg.SHOP_CATEGORIES.items():
        count = sum(1 for i in cfg.SHOP_ITEMS if i.get("category") == category_id)
        lines.append(f"{cat['emoji']} **{cat['name']}** — {cat['description']} `({count})`")
    embed = discord.Embed(
        title="🛒 GGMW9 Marketplace",
        description=(
            f"💳 Wallet: **{cfg.fmt_money(balance)}** • 🏦 Savings: **{cfg.fmt_money(bank)}**\n"
            + (f"⭐ Level Discount: **-{discount}%**\n" if discount else "")
            + "\n" + "\n".join(lines)
            + "\n\nاختار Category من اللائحة. المتجر دابا فيه **utility + assets + prestige** باش الفلوس يكون عندها معنى."
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="Shop spend → Treasury + Events + permanent Burn")
    return embed


def build_shop_category_embed(cog: "Economy", guild: discord.Guild, user: discord.Member, category_id: str) -> discord.Embed:
    cat = cfg.SHOP_CATEGORIES.get(category_id, {"emoji":"🛒","name":"Shop","description":""})
    balance = cog.get_balance(guild.id, user.id)
    discount = cog.get_shop_discount_percent(guild.id, user.id)
    items = [i for i in cfg.SHOP_ITEMS if i.get("category") == category_id]
    lines = []
    for item in items:
        price = cog.get_shop_price(guild.id, user.id, item["price"])
        affordable = "✅" if balance >= price else "❌"
        if price != int(item["price"]):
            price_text = f"~~{cfg.fmt_money(item['price'])}~~ → **{cfg.fmt_money(price)}**"
        else:
            price_text = f"**{cfg.fmt_money(price)}**"
        lines.append(f"{affordable} {item['emoji']} **{item['name']}** — {price_text}\n↳ {item['description']}")
    embed = discord.Embed(
        title=f"{cat['emoji']} {cat['name']}",
        description=(
            f"💳 Wallet: **{cfg.fmt_money(balance)}**" + (f" • ⭐ -{discount}%" if discount else "") + "\n\n"
            + ("\n\n".join(lines) if lines else "📭 هاد Category خاوية دابا.")
        ),
        color=discord.Color.blurple(),
    )
    return embed


class ShopCategorySelect(discord.ui.Select):
    def __init__(self, cog: "Economy", user: discord.Member):
        self.cog = cog
        self.user = user
        options = [
            discord.SelectOption(
                label=cat["name"], value=cid, emoji=cat["emoji"], description=cat["description"][:100]
            ) for cid, cat in cfg.SHOP_CATEGORIES.items()
        ]
        super().__init__(placeholder="🗂️ اختار Category...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ هاد المتجر ماشي ديالك.", ephemeral=True)
            return
        cid = self.values[0]
        await interaction.response.edit_message(
            content=None,
            embed=build_shop_category_embed(self.cog, interaction.guild, interaction.user, cid),
            view=ShopItemsView(self.cog, interaction.user, cid),
        )


class ShopView(discord.ui.View):
    def __init__(self, cog: "Economy", user: discord.Member):
        super().__init__(timeout=300)
        self.cog = cog
        self.user = user
        self.add_item(ShopCategorySelect(cog, user))


class ShopBackButton(discord.ui.Button):
    def __init__(self, cog: "Economy", user: discord.Member):
        super().__init__(label="رجع للـCategories", emoji="↩️", style=discord.ButtonStyle.secondary, row=1)
        self.cog = cog
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        await interaction.response.edit_message(
            content=None,
            embed=build_shop_home_embed(self.cog, interaction.guild, interaction.user),
            view=ShopView(self.cog, interaction.user),
        )


class ShopItemsView(discord.ui.View):
    def __init__(self, cog: "Economy", user: discord.Member, category_id: str):
        super().__init__(timeout=300)
        self.add_item(ShopItemSelect(cog, user, category_id))
        self.add_item(ShopBackButton(cog, user))


class ShopItemSelect(discord.ui.Select):
    def __init__(self, cog: "Economy", user: discord.Member, category_id: str):
        self.cog = cog
        self.user = user
        self.category_id = category_id
        items = [i for i in cfg.SHOP_ITEMS if i.get("category") == category_id]
        options = []
        for item in items[:25]:
            price = cog.get_shop_price(user.guild.id, user.id, item["price"])
            options.append(discord.SelectOption(
                label=f"{item['name']} — {cfg.fmt_money(price)}"[:100],
                value=item["id"], emoji=item["emoji"], description=item["description"][:100]
            ))
        super().__init__(placeholder="🛒 اختار Item باش تشري...", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ هاد المتجر ماشي ديالك.", ephemeral=True)
            return
        item = next((i for i in cfg.SHOP_ITEMS if i["id"] == self.values[0]), None)
        if not item:
            await interaction.response.send_message("❌ Item ما بقاتش موجودة.", ephemeral=True)
            return
        price = self.cog.get_shop_price(interaction.guild.id, interaction.user.id, item["price"])
        balance = self.cog.get_balance(interaction.guild.id, interaction.user.id)
        if balance < price:
            await interaction.response.send_message(
                f"❌ ناقصك **{cfg.fmt_money(price-balance)}** فالWallet.", ephemeral=True
            )
            return
        priced = dict(item); priced["_final_price"] = price
        if item["type"] in {"role_color", "role_color_perm"}:
            await interaction.response.edit_message(
                content=f"🎨 اختار اللون لـ **{item['name']}** — {cfg.fmt_money(price)}",
                embed=None,
                view=ColorPickView(self.cog, interaction.user, priced, self.category_id),
            )
            return
        if item["type"] == "custom_role":
            await interaction.response.send_modal(CustomRoleModal(self.cog, priced))
            return
        await interaction.response.defer(ephemeral=True)
        ok, msg, final_price = await execute_purchase(self.cog, interaction.guild, interaction.user, priced)
        await interaction.edit_original_response(
            content=("✅ " if ok else "❌ ") + msg,
            embed=build_shop_category_embed(self.cog, interaction.guild, interaction.user, self.category_id),
            view=ShopItemsView(self.cog, interaction.user, self.category_id),
        )


class ColorPickView(discord.ui.View):
    def __init__(self, cog: "Economy", user: discord.Member, item: dict, category_id: str = "identity"):
        super().__init__(timeout=120)
        self.cog = cog; self.user = user; self.item = item; self.category_id = category_id
        options = [discord.SelectOption(label=name, value=str(value)) for name, value in cfg.SHOP_COLORS.items()]
        select = discord.ui.Select(placeholder="🎨 اختار اللون...", options=options)
        select.callback = self.on_pick
        self.add_item(select); self.select = select
        self.add_item(ShopBackButton(cog, user))

    async def on_pick(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        item = dict(self.item); item["color"] = int(self.select.values[0])
        ok, msg, _ = await execute_purchase(self.cog, interaction.guild, interaction.user, item)
        await interaction.edit_original_response(
            content=("✅ " if ok else "❌ ") + msg,
            embed=build_shop_category_embed(self.cog, interaction.guild, interaction.user, self.category_id),
            view=ShopItemsView(self.cog, interaction.user, self.category_id),
        )


class CustomRoleModal(discord.ui.Modal, title="🏷️ الرول المخصص ديالك"):
    role_name = discord.ui.TextInput(label="سمية الرول", max_length=32, placeholder="مثال: King of GGMW9")

    def __init__(self, cog: "Economy", item: dict):
        super().__init__(); self.cog = cog; self.item = item

    async def on_submit(self, interaction: discord.Interaction):
        item = dict(self.item); item["custom_name"] = str(self.role_name.value).strip()
        if not item["custom_name"]:
            await interaction.response.send_message("❌ الاسم خاوي.", ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        ok, msg, _ = await execute_purchase(self.cog, interaction.guild, interaction.user, item)
        await interaction.followup.send(("✅ " if ok else "❌ ") + msg, ephemeral=True)


async def execute_purchase(cog: "Economy", guild: discord.Guild, user: discord.Member, item: dict) -> Tuple[bool, str, int]:
    """Atomic-ish purchase: charge first, apply utility, refund automatically on apply failure."""
    final_price = int(item.get("_final_price", cog.get_shop_price(guild.id, user.id, item["price"])))
    if final_price <= 0:
        return False, "الثمن غير صالح.", 0
    if not cog.spend(guild.id, user.id, final_price):
        return False, f"الرصيد تبدل. خاصك **{cfg.fmt_money(final_price)}** فالWallet.", final_price
    try:
        ok, msg = await apply_purchase(cog, guild, user, item)
    except Exception as exc:
        ok, msg = False, f"Purchase handler error: {type(exc).__name__}: {exc}"
    if not ok:
        cog.add_coins(guild.id, user.id, final_price, source="shop_refund", respect_cap=False, count_as_earned=False)
        return False, f"{msg}\n↩️ Refund تلقائي: **{cfg.fmt_money(final_price)}**.", final_price
    try:
        await cog.route_shop_purchase(guild, user, final_price, item)
    except Exception as exc:
        # Item/benefit was applied, so do not duplicate/refund here. Log locally.
        print(f"[SHOP ROUTE] ⚠️ benefit applied but route/log failed: {exc}")
    saved = max(0, int(item["price"]) - final_price)
    note = f"\n⭐ Level Discount saved **{cfg.fmt_money(saved)}**." if saved else ""
    return True, f"{msg}{note}\n💳 Wallet: **{cfg.fmt_money(cog.get_balance(guild.id,user.id))}**", final_price


async def apply_purchase(cog: "Economy", guild: discord.Guild, user: discord.Member, item: dict) -> Tuple[bool, str]:
    bot = cog.bot
    item_type = item.get("type")

    if item_type == "xp_boost":
        bridge = getattr(bot, "gg", None)
        if not bridge or "get_user_level_data" not in bridge:
            return False, "نظام XP ماشي مربوط (bot.gg ناقص)."
        try:
            data = bridge["get_user_level_data"](guild.id, user.id)
            data["xp_boost_multiplier"] = item.get("multiplier", 2.0)
            data["xp_boost_expires"] = (datetime.now() + timedelta(hours=item.get("duration_hours", 1))).isoformat()
            bridge["save_levels"]()
            return True, f"⚡ XP Boost **{item.get('multiplier',2.0)}x** تفعّل لمدة **{item.get('duration_hours',1)} ساعة**."
        except Exception as exc:
            return False, f"خطأ فتفعيل XP Boost: {exc}"

    if item_type in {"role_color", "role_color_perm"}:
        try:
            if "color" not in item:
                return False, "خاصك تختار اللون أولاً."
            role_name = f"🎨 {user.display_name}"
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                await role.edit(colour=discord.Colour(int(item["color"])))
            else:
                role = await guild.create_role(name=role_name, colour=discord.Colour(int(item["color"])), reason=f"Shop color — {user}")
            if cfg.SHOP_COLOR_ROLE_ANCHOR_ID:
                anchor = guild.get_role(cfg.SHOP_COLOR_ROLE_ANCHOR_ID)
                if anchor:
                    await role.edit(position=max(1, anchor.position - 1))
            await user.add_roles(role, reason="GGMW9 Shop color")
            days = 0 if item_type == "role_color_perm" else int(item.get("duration_days", 7))
            _record_purchase(cog, guild.id, user.id, item, role.id, days=days)
            return True, "♾️ اللون الشخصي تفعّل دائم." if days == 0 else f"🎨 اللون تفعّل **{days} أيام**."
        except discord.Forbidden:
            return False, "البوت خاصو Manage Roles وRole ديالو تكون فوق Role اللي كيصاوب."
        except Exception as exc:
            return False, f"خطأ فالRole: {exc}"

    if item_type == "custom_role":
        try:
            role = await guild.create_role(name=item["custom_name"][:32], colour=discord.Colour.random(), reason=f"Custom Role shop — {user}")
            await user.add_roles(role, reason="GGMW9 Shop custom role")
            days = int(item.get("duration_days", 30))
            _record_purchase(cog, guild.id, user.id, item, role.id, days=days)
            return True, f"🏷️ Role **{role.name}** تصاوب لمدة **{days} يوم**."
        except discord.Forbidden:
            return False, "البوت ماعندوش Manage Roles كافية."
        except Exception as exc:
            return False, f"خطأ فالCustom Role: {exc}"

    if item_type == "legend_tag":
        try:
            role = discord.utils.get(guild.roles, name="👑 LEGEND")
            if not role:
                role = await guild.create_role(name="👑 LEGEND", colour=discord.Colour.gold(), mentionable=False, reason="Legend Tag shop")
            await user.add_roles(role, reason="Legend Tag purchase")
            days = int(item.get("duration_days", 7))
            _record_purchase(cog, guild.id, user.id, item, role.id, days=days)
            return True, f"👑 LEGEND Tag تفعّل **{days} أيام**."
        except discord.Forbidden:
            return False, "البوت ماعندوش Manage Roles كافية."
        except Exception as exc:
            return False, f"خطأ: {exc}"

    if item_type == "title_role":
        try:
            role_name = str(item.get("role_name") or item.get("name") or "GGMW9 TITLE")[:100]
            role = discord.utils.get(guild.roles, name=role_name)
            if not role:
                role = await guild.create_role(
                    name=role_name,
                    colour=discord.Colour(int(item.get("role_color", 0xF1C40F))),
                    mentionable=False,
                    reason=f"Prestige title shop — {user}",
                )
            await user.add_roles(role, reason="GGMW9 Prestige purchase")
            days = int(item.get("duration_days", 30))
            _record_purchase(cog, guild.id, user.id, item, role.id, days=days)
            return True, f"👑 Prestige Role **{role.name}** تفعّل **{days} يوم**."
        except discord.Forbidden:
            return False, "البوت ماعندوش Manage Roles كافية."
        except Exception as exc:
            return False, f"خطأ: {exc}"

    if item_type == "coins_boost":
        acc = cog._acc(guild.id, user.id)
        acc["coins_boost_multiplier"] = item.get("multiplier", 1.25)
        acc["coins_boost_expires"] = (datetime.now(timezone.utc) + timedelta(hours=item.get("duration_hours", 2))).isoformat()
        cog.db.save()
        return True, f"🎮 Mini-game Reward Boost **{item.get('multiplier',1.25)}x** تفعّل **{item.get('duration_hours',2)} ساعات**. Casino ماكيتأثرش."

    if item_type in {"bank_interest_boost", "transfer_fee_pass"}:
        acc = cog._acc(guild.id, user.id)
        key = "bank_interest_boost_expires" if item_type == "bank_interest_boost" else "transfer_fee_pass_expires"
        now = datetime.now(timezone.utc)
        try:
            current = datetime.fromisoformat(acc.get(key)) if acc.get(key) else now
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
        except Exception:
            current = now
        start_at = current if current > now else now
        days = int(item.get("duration_days", 7))
        acc[key] = (start_at + timedelta(days=days)).isoformat()
        cog.db.save()
        if item_type == "bank_interest_boost":
            return True, f"📈 Savings Rate Boost تزاد **{days} أيام**. Rate دابا **{cog.get_bank_interest_bps(guild.id,user.id)/100:.2f}%/day**."
        return True, f"💸 Free Bank Transfers تفعّلو **{days} أيام**."

    if item_type == "collectible_asset":
        acc = cog._acc(guild.id, user.id)
        assets = acc.setdefault("assets", {})
        if item["id"] in assets:
            return False, "هاد Asset ديجا عندك؛ كل Asset كتملك منها نسخة وحدة."
        paid = int(item.get("_final_price", item["price"]))
        assets[item["id"]] = {
            "name": item["name"], "emoji": item.get("emoji", "🏠"),
            "paid_price": paid, "bought_at": datetime.now(timezone.utc).isoformat(),
        }
        cog.db.save()
        resale = paid * int(getattr(cfg, "ASSET_RESALE_PERCENT", 40)) // 100
        return True, f"{item.get('emoji','🏠')} **{item['name']}** دخلات Assets ديالك. Book {cfg.fmt_money(paid)} • Market resale {cfg.fmt_money(resale)}."

    if item_type == "shoutout":
        channel_id = getattr(cfg, "SHOP_SHOUTOUT_CHANNEL_ID", 0) or getattr(cfg, "GAMES_PANEL_CHANNEL_ID", 0)
        channel = guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return False, "Shoutout channel ماشي مضبوطة."
        embed = discord.Embed(
            title="📣 GGMW9 Shoutout",
            description=f"✨ Shoutout رسمي لـ {user.mention}!",
            color=discord.Color.gold(), timestamp=datetime.now(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            return False, "البوت ماعندوش صلاحية يكتب فـShoutout channel."
        return True, f"📣 Shoutout تبعث فـ <#{channel_id}>."

    return False, "هاد Item type مازال ماخدامش."


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
