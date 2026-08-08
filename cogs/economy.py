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
import aiohttp

from storage import JsonStore
import games_config as cfg


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def currency_word(amount: int) -> str:
    # Compatibility helper for older game cogs. Currency is now USD.
    return cfg.CURRENCY_NAME


def fmt_coins(amount: int) -> str:
    return cfg.fmt_money(amount)


def _panel_lang(bot: commands.Bot, guild_id: int, user_id: int) -> str:
    bridge = getattr(bot, "gg", {}) or {}
    getter = bridge.get("get_panel_language")
    if getter:
        try:
            return getter(guild_id, user_id)
        except Exception:
            pass
    return "darija"


def _set_panel_lang(bot: commands.Bot, guild_id: int, user_id: int, lang: str) -> str:
    bridge = getattr(bot, "gg", {}) or {}
    setter = bridge.get("set_panel_language")
    if setter:
        try:
            return setter(guild_id, user_id, lang)
        except Exception:
            pass
    return lang if lang in {"darija", "en", "fr"} else "darija"


async def _upsert_panel(bot: commands.Bot, interaction: discord.Interaction, key: str, **kwargs):
    helper = (getattr(bot, "gg", {}) or {}).get("upsert_ephemeral_panel")
    if helper:
        return await helper(interaction, key, **kwargs)
    if not interaction.response.is_done():
        await interaction.response.send_message(ephemeral=True, **kwargs)
    else:
        await interaction.followup.send(ephemeral=True, **kwargs)

async def _fresh_panel(interaction: discord.Interaction, **kwargs):
    """Fresh private session from a public panel; safe after Dismiss."""
    if not interaction.response.is_done():
        return await interaction.response.send_message(ephemeral=True, **kwargs)
    return await interaction.followup.send(ephemeral=True, **kwargs)


def _eco_t(lang: str, key: str) -> str:
    data = {
        "darija": {
            "not_yours":"❌ هاد الجلسة ماشي ديالك.", "back":"رجع للبنك", "account":"حسابي",
            "deposit":"Deposit", "withdraw":"Withdraw", "transfer":"Transfer", "savings":"Savings",
            "loan":"طلب قرض", "repay":"خلص القرض", "transactions":"معاملاتي", "assets":"Assets",
            "stats":"الاقتصاد", "xp":"XP Perks", "open_bank":"فتح البنك ديالي",
            "shop_choose":"🗂️ اختار Category...", "shop_item":"🛒 اختار Item باش تشري...",
            "shop_back":"رجع للـCategories", "lang_saved":"✅ اللغة ديالك ولات **الدارجة**.",
        },
        "en": {
            "not_yours":"❌ This session belongs to another member.", "back":"Back to Bank", "account":"My Account",
            "deposit":"Deposit", "withdraw":"Withdraw", "transfer":"Transfer", "savings":"Savings",
            "loan":"Request Loan", "repay":"Repay Loan", "transactions":"Transactions", "assets":"Assets",
            "stats":"Economy", "xp":"XP Perks", "open_bank":"Open My Bank",
            "shop_choose":"🗂️ Choose a category...", "shop_item":"🛒 Choose an item to buy...",
            "shop_back":"Back to Categories", "lang_saved":"✅ Your language is now **English**.",
        },
        "fr": {
            "not_yours":"❌ Cette session appartient à un autre membre.", "back":"Retour à la banque", "account":"Mon compte",
            "deposit":"Déposer", "withdraw":"Retirer", "transfer":"Transférer", "savings":"Épargne",
            "loan":"Demander un prêt", "repay":"Rembourser", "transactions":"Transactions", "assets":"Actifs",
            "stats":"Économie", "xp":"Avantages XP", "open_bank":"Ouvrir ma banque",
            "shop_choose":"🗂️ Choisis une catégorie...", "shop_item":"🛒 Choisis un article...",
            "shop_back":"Retour aux catégories", "lang_saved":"✅ Ta langue est maintenant **Français**.",
        },
    }
    lang = lang if lang in data else "darija"
    return data[lang].get(key, data["darija"].get(key, key))


SHOP_CATEGORY_I18N = {
    "boosts": {"en":("Boosts","Temporary XP and mini-game boosts."), "fr":("Boosts","Boosts temporaires pour l'XP et les mini-jeux.")},
    "identity": {"en":("Identity","Personal colors, roles and tags."), "fr":("Identité","Couleurs, rôles et tags personnels.")},
    "banking": {"en":("Banking","Savings and transfer advantages."), "fr":("Banque","Avantages d'épargne et de transfert.")},
    "social": {"en":("Social","Visibility and interaction inside the server."), "fr":("Social","Visibilité et interaction dans le serveur.")},
    "assets": {"en":("Assets","Permanent property counted in Net Worth and resellable."), "fr":("Actifs","Biens permanents comptés dans la valeur nette et revendables.")},
    "luxury": {"en":("Luxury","Prestige money sinks for wealthy members."), "fr":("Luxe","Dépenses de prestige pour les membres fortunés.")},
}

SHOP_ITEM_DESC_I18N = {
    "xpboost_small": {"en":"Chat and voice XP ×1.25 for 1 hour.","fr":"XP chat et vocal ×1,25 pendant 1 heure."},
    "xpboost_medium": {"en":"Your XP ×1.5 for 1 full hour.","fr":"Ton XP ×1,5 pendant 1 heure complète."},
    "xpboost_big": {"en":"Strong XP boost ×2 for 1 hour.","fr":"Boost XP puissant ×2 pendant 1 heure."},
    "coinsboost_small": {"en":"Increases non-casino mini-game rewards. Casino odds never change.","fr":"Augmente les récompenses des mini-jeux hors casino. Les probabilités du casino ne changent jamais."},
    "color_basic": {"en":"A personal color role for 7 days.","fr":"Un rôle de couleur personnelle pendant 7 jours."},
    "color_month": {"en":"A personal color role for 30 days.","fr":"Un rôle de couleur personnelle pendant 30 jours."},
    "permanent_color": {"en":"Permanent personal name color.","fr":"Couleur personnelle permanente pour ton nom."},
    "customrole_week": {"en":"A custom-named role for 7 days.","fr":"Un rôle personnalisé pendant 7 jours."},
    "customrole": {"en":"A custom-named role for 30 days.","fr":"Un rôle personnalisé pendant 30 jours."},
    "legend_tag": {"en":"LEGEND tag for 7 days.","fr":"Tag LEGEND pendant 7 jours."},
    "interest_boost_7d": {"en":"Adds +0.05%/day to your Savings rate for 7 days; paid from Treasury.","fr":"Ajoute +0,05 %/jour au taux d'épargne pendant 7 jours ; payé par le Trésor."},
    "transfer_pass_7d": {"en":"0% fee on Bank→Bank transfers for 7 days.","fr":"0 % de frais sur les transferts Banque→Banque pendant 7 jours."},
    "shoutout_public": {"en":"The bot posts a public shoutout for you in the dedicated channel.","fr":"Le bot publie un shoutout public dans le salon dédié."},
    "asset_car": {"en":"Permanent Net Worth asset. Resale = 40% of paid price, funded by Treasury.","fr":"Actif permanent. Revente = 40 % du prix payé, financée par le Trésor."},
    "asset_apartment": {"en":"Permanent property shown in your account and Net Worth; Treasury-funded resale.","fr":"Bien permanent affiché dans ton compte et ta valeur nette ; revente financée par le Trésor."},
    "asset_business": {"en":"Permanent business asset for tycoons; prestige without passive money creation.","fr":"Actif business permanent ; prestige sans création d'argent passif."},
    "asset_yacht": {"en":"Rare luxury asset; 40% resale when Treasury has liquidity.","fr":"Actif de luxe rare ; revente à 40 % si le Trésor a assez de liquidités."},
    "asset_mansion": {"en":"The most expensive GGMW9 asset; a permanent wealth sink.","fr":"L'actif GGMW9 le plus cher ; une dépense de richesse permanente."},
    "high_roller": {"en":"HIGH ROLLER prestige role for 14 days.","fr":"Rôle prestige HIGH ROLLER pendant 14 jours."},
    "banker_title": {"en":"BANKER prestige role for 30 days.","fr":"Rôle prestige BANKER pendant 30 jours."},
    "tycoon_title": {"en":"TYCOON prestige role for 30 days.","fr":"Rôle prestige TYCOON pendant 30 jours."},
}


def _shop_category_text(category_id: str, lang: str):
    cat = cfg.SHOP_CATEGORIES.get(category_id, {"emoji":"🛒","name":"Shop","description":""})
    if lang in {"en","fr"} and category_id in SHOP_CATEGORY_I18N:
        name, desc = SHOP_CATEGORY_I18N[category_id][lang]
        return cat.get("emoji","🛒"), name, desc
    return cat.get("emoji","🛒"), cat.get("name","Shop"), cat.get("description","")


def _shop_item_desc(item: dict, lang: str) -> str:
    if lang in {"en","fr"}:
        return SHOP_ITEM_DESC_I18N.get(item.get("id"), {}).get(lang, item.get("description", ""))
    return item.get("description", "")


class Economy(commands.Cog):
    """نظام العملة — كاع الـ cogs الأخرى كتعيّط عليه بـ bot.get_cog("Economy")"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = JsonStore("economy.json", default={})
        # حسابات النظام المركزي: Treasury / Jackpot / Events / Burn / Bank / Ledger.
        self.system_db = JsonStore("economy_system.json", default={})
        # FX is display-only. Internal balances/transactions ALWAYS stay USD cents.
        self.fx_db = JsonStore("fx_rates.json", default={"base":"USD","rates":{"USD":1.0},"date":None,"source":"Frankfurter"})

    async def cog_load(self):
        self.expire_purchases_loop.start()
        self.economy_stats_loop.start()
        self.loan_collection_loop.start()
        self.bank_interest_loop.start()
        self.fx_rates_loop.start()
        # Persistent View: ما كيزيد حتى Slash Command جديد.
        self.bot.add_view(EconomyBankPanelView(self,"darija"))

    def cog_unload(self):
        self.expire_purchases_loop.cancel()
        self.economy_stats_loop.cancel()
        self.loan_collection_loop.cancel()
        self.bank_interest_loop.cancel()
        self.fx_rates_loop.cancel()

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
            "total_gambling_won": 0,
            "big_win_channel_id": None,
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

    # ════════════════════════════════════════════════
    # Display Currency / FX — presentation only
    # ════════════════════════════════════════════════

    def get_display_currency(self, guild_id: int, user_id: int) -> str:
        code = str(self._acc(guild_id, user_id).get("display_currency", "USD") or "USD").upper()
        return code if code in getattr(cfg, "DISPLAY_CURRENCIES", {"USD": {}}) else "USD"

    def set_display_currency(self, guild_id: int, user_id: int, code: str) -> str:
        code = str(code or "USD").upper()
        if code not in getattr(cfg, "DISPLAY_CURRENCIES", {"USD": {}}):
            code = "USD"
        acc = self._acc(guild_id, user_id)
        acc["display_currency"] = code
        self.db.save()
        return code

    def _fx_rate(self, code: str) -> Optional[float]:
        code = str(code or "USD").upper()
        if code == "USD":
            return 1.0
        try:
            rate = float((self.fx_db.data.get("rates") or {}).get(code))
            return rate if rate > 0 else None
        except (TypeError, ValueError):
            return None

    def format_currency_value(self, cents: int, code: str) -> Optional[str]:
        code = str(code or "USD").upper()
        if code == "USD":
            return cfg.fmt_money(cents)
        meta = getattr(cfg, "DISPLAY_CURRENCIES", {}).get(code)
        rate = self._fx_rate(code)
        if not meta or rate is None:
            return None
        value = (int(cents or 0) / float(getattr(cfg, "MONEY_SCALE", 100) or 100)) * rate
        decimals = int(meta.get("decimals", 2))
        symbol = meta.get("symbol", code)
        if code in {"MAD", "DZD"}:
            return f"{value:,.{decimals}f} {symbol}"
        return f"{symbol}{value:,.{decimals}f}"

    def money_with_preference(self, guild_id: int, user_id: int, cents: int) -> str:
        """USD is source of truth; the optional second line is reference FX only."""
        usd = cfg.fmt_money(cents)
        code = self.get_display_currency(guild_id, user_id)
        if code == "USD":
            return usd
        converted = self.format_currency_value(cents, code)
        meta = getattr(cfg, "DISPLAY_CURRENCIES", {}).get(code, {})
        if converted is None:
            return f"{usd}\n⏳ {meta.get('emoji','💱')} {code} rate loading"
        return f"{usd}\n≈ {meta.get('emoji','💱')} {converted}"

    async def refresh_fx_rates(self) -> bool:
        """Fetch USD→EUR/MAD/DZD reference rates; failures keep the last cache."""
        url = str(getattr(cfg, "FX_API_URL", "") or "")
        if not url:
            return False
        try:
            timeout = aiohttp.ClientTimeout(total=12)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        return False
                    payload = await resp.json()
            rows = payload if isinstance(payload, list) else []
            rates = {"USD": 1.0}
            rate_date = None
            for row in rows:
                quote = str(row.get("quote", "")).upper()
                if quote in getattr(cfg, "DISPLAY_CURRENCIES", {}) and quote != "USD":
                    try:
                        rate = float(row.get("rate"))
                    except (TypeError, ValueError):
                        continue
                    if rate > 0:
                        rates[quote] = rate
                        rate_date = rate_date or row.get("date")
            if not all(code in rates for code in ("EUR", "MAD", "DZD")):
                return False
            self.fx_db.data.clear()
            self.fx_db.data.update({"base":"USD","rates":rates,"date":rate_date,"source":"Frankfurter"})
            self.fx_db.save()
            return True
        except Exception as exc:
            print(f"[FX] refresh failed; keeping last cached rates: {type(exc).__name__}: {exc}")
            return False

    @tasks.loop(minutes=max(30, int(getattr(cfg, "FX_REFRESH_MINUTES", 360) or 360)))
    async def fx_rates_loop(self):
        await self.refresh_fx_rates()

    @fx_rates_loop.before_loop
    async def before_fx_rates_loop(self):
        await self.bot.wait_until_ready()

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

    async def ensure_big_win_channel(self, guild: discord.Guild):
        """Find/create public read-only highlight feed for exceptional one-bet wins."""
        configured = int(getattr(cfg, "CASINO_BIG_WIN_CHANNEL_ID", 0) or 0)
        if configured:
            ch = guild.get_channel(configured)
            if ch:
                return ch
        sys = self._system(guild.id)
        saved = int(sys.get("big_win_channel_id") or 0)
        if saved:
            ch = guild.get_channel(saved)
            if ch:
                return ch
        ch = discord.utils.get(guild.text_channels, name="💎・big-wins") or discord.utils.get(guild.text_channels, name="big-wins")
        if ch:
            sys["big_win_channel_id"] = ch.id
            self.system_db.save()
            return ch
        category = guild.get_channel(int(getattr(cfg, "ECONOMY_CATEGORY_ID", 0) or 0))
        if category is not None and not isinstance(category, discord.CategoryChannel):
            category = None
        me = guild.me
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=False),
        }
        if me:
            overwrites[me] = discord.PermissionOverwrite(view_channel=True, read_message_history=True, send_messages=True, embed_links=True)
        try:
            ch = await guild.create_text_channel(
                "💎・big-wins",
                category=category,
                topic="GGMW9 Casino — exceptional single-wager wins only. Read-only highlight feed.",
                overwrites=overwrites,
                reason="GGMW9 Economy: dedicated large casino wins feed",
            )
            sys["big_win_channel_id"] = ch.id
            self.system_db.save()
            return ch
        except (discord.Forbidden, discord.HTTPException):
            return None

    async def _post_big_win(self, guild: discord.Guild, user: discord.abc.User, *, game: str, bet: int, payout: int, profit: int, details: str = "", is_jackpot: bool = False):
        threshold = int(getattr(cfg, "CASINO_BIG_WIN_MIN_PROFIT", 25000) or 25000)
        multiplier = (payout / bet) if bet > 0 else 0.0
        mult_threshold = float(getattr(cfg, "CASINO_BIG_WIN_MIN_PAYOUT_MULTIPLIER", 10.0) or 10.0)
        qualifies = bool(is_jackpot or profit >= threshold or (profit >= threshold // 2 and multiplier >= mult_threshold))
        if not qualifies:
            return
        channel = await self.ensure_big_win_channel(guild)
        if not channel:
            return
        embed = discord.Embed(
            title="💎 BIG WIN — GGMW9 CASINO",
            description=(
                f"🎉 {user.mention} دار **Big Win** من رهان واحد!\n\n"
                f"🎮 **Game:** `{game}`\n"
                f"🎟️ **Bet:** {cfg.fmt_money(bet)}\n"
                f"💰 **Payout:** {cfg.fmt_money(payout)}\n"
                f"📈 **Net Profit:** **+{cfg.fmt_money(profit)}**\n"
                f"✖️ **Return:** `{multiplier:.2f}x`"
                + (f"\n\n{details}" if details else "")
            ),
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        if is_jackpot:
            embed.add_field(name="🏆 Jackpot", value="✅ Jackpot / progressive prize included", inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text="GGMW9 • Exceptional wins only • same odds for everyone")
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def record_gambling_win(self, guild: discord.Guild, user: discord.abc.User, bet: int, payout: int, game: str, *, details: str = "", is_jackpot: bool = False) -> dict:
        """Audit a real casino win AFTER payout. This does not alter the balance."""
        bet = max(0, int(bet or 0)); payout = max(0, int(payout or 0))
        profit = max(0, payout - bet)
        sys = self._system(guild.id)
        sys["total_gambling_won"] = int(sys.get("total_gambling_won", 0) or 0) + profit
        tx_id = self._record_transaction(
            guild.id, user_id=user.id, kind="gambling_win", amount=profit, source=game,
            description=f"ربح رهان فـ {game}", splits={"bet":bet,"payout":payout,"profit":profit},
        )
        multiplier = (payout / bet) if bet > 0 else 0.0
        await self._economy_log(
            guild, f"🎉 ربح رهان — TX #{tx_id}",
            (f"**العضو:** {user.mention}\n**اللعبة:** `{game}`\n"
             f"**Bet:** **{cfg.fmt_money(bet)}**\n**Payout:** **{cfg.fmt_money(payout)}**\n"
             f"**Net Profit:** **+{cfg.fmt_money(profit)}**\n**Return:** `{multiplier:.2f}x`"
             + (f"\n**Details:** {details}" if details else "")),
            discord.Color.green(),
        )
        await self._post_big_win(guild, user, game=game, bet=bet, payout=payout, profit=profit, details=details, is_jackpot=is_jackpot)
        return {"tx_id":tx_id,"bet":bet,"payout":payout,"profit":profit}

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

    def build_bank_panel_embed(self, guild: discord.Guild, lang: str = "darija") -> discord.Embed:
        sys = self._system(guild.id)
        if lang == "en":
            desc = (
                "**A real server bank:** Wallet, Savings, Transfers, Loans, Credit and Assets.\n\n"
                "💳 **Wallet** — gaming and purchases.\n🏦 **Savings** — protected from casino bets and earns Treasury-funded daily interest.\n"
                "💸 **Transfers** — Bank→Bank with a ledger and transparent fee.\n💳 **Loans** — funded by Treasury; Credit + Level determine terms.\n"
                "🏠 **Assets** — property counted in Net Worth and resellable.\n\n"
                "📍 **This #bank channel is the official full Bank panel. ARCADE only provides quick access.**"
            )
            rate_name, trans_name, redenom_name = "📈 Savings Rate", "💸 Transfers", "💵 USD System"
            footer = "GGMW9 Bank • real ledger • Treasury-funded yield • personal language"
        elif lang == "fr":
            desc = (
                "**Une vraie banque du serveur :** Wallet, Épargne, Transferts, Prêts, Crédit et Actifs.\n\n"
                "💳 **Wallet** — jeux et achats.\n🏦 **Épargne** — protégée des paris et rémunérée par le Trésor.\n"
                "💸 **Transferts** — Banque→Banque avec registre et frais transparents.\n💳 **Prêts** — financés par le Trésor ; Crédit + Niveau définissent les conditions.\n"
                "🏠 **Actifs** — biens inclus dans la valeur nette et revendables.\n\n"
                "📍 **Ce salon #bank est le panneau bancaire officiel complet. ARCADE sert uniquement d'accès rapide.**"
            )
            rate_name, trans_name, redenom_name = "📈 Taux d'épargne", "💸 Transferts", "💵 Système USD"
            footer = "GGMW9 Bank • registre réel • rendement financé par le Trésor"
        else:
            desc = (
                "**Bank حقيقي داخل اقتصاد السيرفر:** Wallet، Savings، Transfers، Loans، Credit وAssets.\n\n"
                "💳 **Wallet** — اللعب والشراء.\n🏦 **Savings** — محمية من الرهانات وكتربح Daily Interest من Treasury.\n"
                "💸 **Transfers** — Bank→Bank مع Ledger وFee واضحة.\n💳 **Loans** — ممولة من Treasury؛ Credit + Level كيحددو الشروط.\n"
                "🏠 **Assets** — ممتلكات كتدخل فـNet Worth ويمكن تعاود تبيعها.\n\n"
                "📍 **هاد #bank هو البانل الرسمي والكامل ديال البنك؛ ARCADE غير Quick Access.**"
            )
            rate_name, trans_name, redenom_name = "📈 Savings Rate", "💸 Transfers", "💵 USD Re-denomination"
            footer = "GGMW9 Bank • real ledger • no hidden balance reset"
        embed = discord.Embed(title="🏦 GGMW9 Central Bank", description=desc, color=discord.Color.gold(), timestamp=datetime.now())
        embed.add_field(name="🏛️ Treasury", value=f"**{cfg.fmt_money(sys['treasury'])}**", inline=True)
        embed.add_field(name="🎰 Global Jackpot", value=f"**{cfg.fmt_money(sys['jackpot'])}**", inline=True)
        embed.add_field(name="🎉 Events Fund", value=f"**{cfg.fmt_money(sys['events'])}**", inline=True)
        if lang == "en":
            rv = f"Base **{getattr(cfg,'BANK_INTEREST_BASE_BPS_DAILY',5)/100:.2f}%/day**\nMinimum **{cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}**\nLevel and Shop pass may increase it."
            tv = f"Base fee **{getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%**\nDaily limit starts at **{cfg.fmt_money(getattr(cfg,'BANK_TRANSFER_DAILY_LIMIT',100000))}**"
            dv = "Balances are stored in cents and displayed as USD. No hidden reset is performed."
        elif lang == "fr":
            rv = f"Base **{getattr(cfg,'BANK_INTEREST_BASE_BPS_DAILY',5)/100:.2f}%/jour**\nMinimum **{cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}**\nLe niveau et le pass Boutique peuvent l'augmenter."
            tv = f"Frais de base **{getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%**\nLimite quotidienne dès **{cfg.fmt_money(getattr(cfg,'BANK_TRANSFER_DAILY_LIMIT',100000))}**"
            dv = "Les soldes sont stockés en cents et affichés en USD. Aucun reset caché."
        else:
            rv = f"Base **{getattr(cfg,'BANK_INTEREST_BASE_BPS_DAILY',5)/100:.2f}%/day**\nMin balance **{cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}**\nLevel وShop pass يقدرو يزيدو rate."
            tv = f"Base fee **{getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%**\nDaily limit من **{cfg.fmt_money(getattr(cfg,'BANK_TRANSFER_DAILY_LIMIT',100000))}**"
            dv = "الأرصدة كتتعرض بالدولار وبالسنت؛ ما كاين حتى Reset مخفي."
        embed.add_field(name=rate_name, value=rv, inline=True)
        embed.add_field(name=trans_name, value=tv, inline=True)
        embed.add_field(name=redenom_name, value=dv, inline=False)
        embed.add_field(name="🌐 Languages", value="🇲🇦 Darija (Default) • 🇬🇧 English • 🇫🇷 Français", inline=False)
        embed.add_field(name="💱 Display Currency", value="الحساب الحقيقي ديما **USD**. من Account كل عضو يقدر يشوف تقريباً حتى **MAD / EUR / DZD** بلا ما يتبدل الرصيد أو الرهان.", inline=False)
        embed.set_footer(text=footer + " • FX display: USD/MAD/EUR/DZD")
        return embed

    def build_global_economy_embed(self, guild: discord.Guild, lang: str = "darija") -> discord.Embed:
        sys = self._system(guild.id)
        guild_data = self.db.guild(guild.id)
        wallets = sum(max(0, int(acc.get("coins", 0) or 0)) for acc in guild_data.values())
        bank_total = sum(max(0, int(v or 0)) for v in sys.get("bank_accounts", {}).values())
        assets_total = sum(sum(max(0, int(a.get("paid_price", 0) or 0)) for a in (acc.get("assets") or {}).values()) for acc in guild_data.values())
        active_loans = [loan for loan in sys.get("loans", {}).values() if loan and int(loan.get("remaining", 0) or 0) > 0]
        loans_outstanding = sum(int(loan.get("remaining", 0) or 0) for loan in active_loans)
        overdue_loans = sum(1 for loan in active_loans if self._loan_is_overdue(loan))
        live_supply = wallets + bank_total + sys["treasury"] + sys["jackpot"] + sys["events"]
        if lang == "en":
            title, desc = "📊 GGMW9 Economy — Live", "Live USD economy: Wallet + Bank + Treasury + Casino + Shop + Assets."
            names = ["💳 Wallets","🏦 Bank Deposits","🏛️ Treasury","🎰 Jackpot","🎉 Events","🔥 Burned","🏠 Asset Book Value","💳 Loans Outstanding","⚠️ Overdue Loans","💵 Live Money Supply"]
        elif lang == "fr":
            title, desc = "📊 Économie GGMW9 — Live", "Économie USD en direct : Wallet + Banque + Trésor + Casino + Boutique + Actifs."
            names = ["💳 Wallets","🏦 Dépôts bancaires","🏛️ Trésor","🎰 Jackpot","🎉 Événements","🔥 Détruit","🏠 Valeur des actifs","💳 Prêts en cours","⚠️ Prêts en retard","💵 Masse monétaire"]
        else:
            title, desc = "📊 اقتصاد GGMW9 — Live", "USD economy: Wallet + Bank + Treasury + Casino + Shop + Assets."
            names = ["💳 Wallets","🏦 Bank Deposits","🏛️ Treasury","🎰 Jackpot","🎉 Events","🔥 Burned","🏠 Asset Book Value","💳 Loans Outstanding","⚠️ Overdue Loans","💵 Live Money Supply"]
        embed = discord.Embed(title=title, description=desc, color=discord.Color.blurple(), timestamp=datetime.now())
        vals=[wallets,bank_total,sys['treasury'],sys['jackpot'],sys['events'],sys['burned'],assets_total,loans_outstanding,overdue_loans,live_supply]
        for i,(name,val) in enumerate(zip(names,vals)):
            value = f"**{val}**" if i==8 else f"**{cfg.fmt_money(val)}**"
            embed.add_field(name=name,value=value,inline=True)
        if lang == "en":
            loss_name, win_name = "🎰 Casino Losses Routed", "🎉 Casino Net Wins Logged"
        elif lang == "fr":
            loss_name, win_name = "🎰 Pertes Casino routées", "🎉 Gains nets Casino journalisés"
        else:
            loss_name, win_name = "🎰 Casino Losses Routed", "🎉 Casino Net Wins Logged"
        embed.add_field(name=loss_name,value=f"**{cfg.fmt_money(int(sys.get('total_gambling_lost',0) or 0))}**",inline=True)
        embed.add_field(name=win_name,value=f"**{cfg.fmt_money(int(sys.get('total_gambling_won',0) or 0))}**",inline=True)
        embed.set_footer(text="🌐 Darija • English • Français")
        return embed

    def build_user_account_embed(self, guild: discord.Guild, user: discord.abc.User, lang: str = "darija") -> discord.Embed:
        wallet = self.get_balance(guild.id, user.id); bank = self.get_bank_balance(guild.id, user.id)
        assets_value = self.get_assets_value(guild.id, user.id); terms = self.get_loan_terms(guild.id, user.id)
        net_worth = wallet + bank + assets_value; rate_bps = self.get_bank_interest_bps(guild.id, user.id)
        sent_today = self.get_transfer_sent_today(guild.id, user.id); transfer_limit = self.get_transfer_daily_limit(guild.id, user.id)
        fee_free = self._perk_active(guild.id, user.id, "transfer_fee_pass_expires")
        if lang == "en":
            title=f"🏦 {user.display_name}'s Account"; net="Net Worth"; trans="💸 Transfers Today"; loan_terms="🏦 Loan Terms"; footer="Savings are protected from Casino until withdrawn • Assets can be sold from Bank"
            yield_v=f"**{rate_bps/100:.2f}% / day**\nMin: {cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}\nTreasury-funded"
            trans_v=f"{cfg.fmt_money(sent_today)} / {cfg.fmt_money(transfer_limit)}\n"+("✅ Fee Pass active" if fee_free else f"Fee {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")
            terms_v=f"Limit: **{cfg.fmt_money(terms['effective_limit'])}**\nInterest: **{terms['interest_percent']}%** • Term: **{terms['term_days']}d**"
        elif lang == "fr":
            title=f"🏦 Compte de {user.display_name}"; net="Valeur nette"; trans="💸 Transferts aujourd'hui"; loan_terms="🏦 Conditions du prêt"; footer="L'épargne est protégée du Casino tant qu'elle n'est pas retirée • Les actifs peuvent être revendus depuis la Banque"
            yield_v=f"**{rate_bps/100:.2f}% / jour**\nMin : {cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}\nFinancé par le Trésor"
            trans_v=f"{cfg.fmt_money(sent_today)} / {cfg.fmt_money(transfer_limit)}\n"+("✅ Pass sans frais actif" if fee_free else f"Frais {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")
            terms_v=f"Limite : **{cfg.fmt_money(terms['effective_limit'])}**\nIntérêt : **{terms['interest_percent']}%** • Durée : **{terms['term_days']}j**"
        else:
            title=f"🏦 حساب {user.display_name}"; net="Net Worth"; trans="💸 Transfers اليوم"; loan_terms="🏦 Loan Terms"; footer="Savings ماكيدخلش Casino حتى تسحبو | Assets تقدر تبيعهم من Bank"
            yield_v=f"**{rate_bps/100:.2f}% / day**\nMin: {cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}\nTreasury-funded"
            trans_v=f"{cfg.fmt_money(sent_today)} / {cfg.fmt_money(transfer_limit)}\n"+("✅ Fee Pass active" if fee_free else f"Fee {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")
            terms_v=f"Limit: **{cfg.fmt_money(terms['effective_limit'])}**\nInterest: **{terms['interest_percent']}%** • Term: **{terms['term_days']}d**"
        display_code=self.get_display_currency(guild.id,user.id)
        embed=discord.Embed(title=title,description=f"**{net}:**\n{self.money_with_preference(guild.id,user.id,net_worth)}",color=discord.Color.green())
        embed.add_field(name="💳 Wallet",value=f"**{self.money_with_preference(guild.id,user.id,wallet)}**",inline=True); embed.add_field(name="🏦 Savings",value=f"**{self.money_with_preference(guild.id,user.id,bank)}**",inline=True); embed.add_field(name="🏠 Assets",value=f"**{self.money_with_preference(guild.id,user.id,assets_value)}**",inline=True)
        embed.add_field(name="📈 Savings Yield",value=yield_v,inline=True); embed.add_field(name=trans,value=trans_v,inline=True); embed.add_field(name="💳 Credit",value=f"**{terms['credit_score']}/100** • {terms['tier_name']} • Lv {terms['level']}",inline=True)
        embed.add_field(name=loan_terms,value=terms_v,inline=False)
        loan=self.get_active_loan(guild.id,user.id)
        if loan:
            overdue=self._loan_is_overdue(loan)
            state=("⚠️ Overdue" if overdue else "🟢 Active") if lang!="fr" else ("⚠️ En retard" if overdue else "🟢 Actif")
            rem="Remaining" if lang=="en" else "Restant" if lang=="fr" else "Remaining"
            due="Due" if lang=="en" else "Échéance" if lang=="fr" else "Due"
            embed.add_field(name=f"💳 Loan #{loan.get('id')} — {state}",value=f"{rem}: **{cfg.fmt_money(int(loan.get('remaining',0)))}**\n{due}: <t:{self._loan_due_unix(loan)}:F> (<t:{self._loan_due_unix(loan)}:R>)",inline=False)
        fx_date=self.fx_db.data.get("date")
        fx_note=(f" • Display: {display_code} ≈ Frankfurter reference FX" + (f" ({fx_date})" if fx_date else "")) if display_code!="USD" else ""
        embed.set_thumbnail(url=user.display_avatar.url); embed.set_footer(text=footer+fx_note)
        return embed

    def build_xp_bank_perks_embed(self, guild: discord.Guild, user: discord.abc.User, lang: str = "darija") -> discord.Embed:
        terms=self.get_loan_terms(guild.id,user.id); next_tier=self.get_next_xp_loan_tier(guild.id,user.id)
        if lang=="en": title=f"⭐ Bank Privileges — {user.display_name}"; desc="Level increases loan capacity, Savings rate and transfer limit; Credit measures repayment reliability."; now_name="📊 Current"; loan_name="💰 Loan"; next_name="🚀 Next Tier"
        elif lang=="fr": title=f"⭐ Avantages bancaires — {user.display_name}"; desc="Le niveau augmente la capacité de prêt, le taux d'épargne et la limite de transfert ; le Crédit mesure la fiabilité des remboursements."; now_name="📊 Actuel"; loan_name="💰 Prêt"; next_name="🚀 Niveau suivant"
        else: title=f"⭐ Bank Privileges — {user.display_name}"; desc="Level كيزيد Loan capacity وكيحسن Savings rate وTransfer limit؛ Credit كيقيس الالتزام بالأداء."; now_name="📊 دابا"; loan_name="💰 Loan"; next_name="🚀 Next Tier"
        embed=discord.Embed(title=title,description=desc,color=discord.Color.gold())
        embed.add_field(name=now_name,value=f"⭐ Lv **{terms['level']}** — {terms['tier_name']}\n💳 Credit **{terms['credit_score']}/100**\n📈 Savings **{self.get_bank_interest_bps(guild.id,user.id)/100:.2f}%/day**\n💸 Transfer limit **{cfg.fmt_money(self.get_transfer_daily_limit(guild.id,user.id))}/day**",inline=False)
        embed.add_field(name=loan_name,value=f"Base: **{cfg.fmt_money(terms['base_limit'])}**\nAfter Credit: **{cfg.fmt_money(terms['credit_adjusted_limit'])}**\nLiquidity Cap: **{cfg.fmt_money(terms['liquidity_cap'])}**\n✅ Effective: **{cfg.fmt_money(terms['effective_limit'])}**\nInterest **{terms['interest_percent']}%** • **{terms['term_days']}d**",inline=False)
        if next_tier:
            embed.add_field(name=next_name,value=f"Lv **{int(next_tier.get('min_level',0))}** — {next_tier.get('name','Tier')}\nBase Loan **{cfg.fmt_money(int(next_tier.get('base_limit',0)))}** • {int(next_tier.get('interest',0))}% • {int(next_tier.get('term_days',0))}d",inline=False)
        embed.set_thumbnail(url=user.display_avatar.url); return embed

    def build_user_transactions_embed(self, guild: discord.Guild, user: discord.abc.User, lang: str = "darija") -> discord.Embed:
        txs=self.get_user_transactions(guild.id,user.id,limit=12)
        if not txs:
            title="🧾 Recent Transactions" if lang=="en" else "🧾 Transactions récentes" if lang=="fr" else "🧾 آخر المعاملات"
            empty="📭 No transactions recorded yet." if lang=="en" else "📭 Aucune transaction enregistrée." if lang=="fr" else "📭 ماكايناش معاملات مسجلة."
            return discord.Embed(title=title,description=empty,color=discord.Color.blurple())
        kind_icons={"gambling_loss":"🎰","gambling_win":"🎉","shop_purchase":"🛒","jackpot_payout":"🏆","bank_deposit":"🏦","bank_withdraw":"💸","bank_transfer_out":"📤","bank_transfer_in":"📥","bank_interest":"📈","asset_sale":"🏠","loan_issued":"💳","loan_repayment":"💸","loan_paid":"✅","level_daily_bonus":"⭐","admin_adjustment":"🛡️"}
        lines=[]
        for tx in txs:
            icon=kind_icons.get(tx.get("kind"),"💱")
            try: unix=int(datetime.fromisoformat(tx.get("ts","")).timestamp()); when=f"<t:{unix}:R>"
            except Exception: when="—"
            lines.append(f"{icon} **TX #{tx.get('id')}** • {tx.get('description',tx.get('source','transaction'))} • **{cfg.fmt_money(int(tx.get('amount',0)))}** • {when}")
        title=(f"🧾 {user.display_name}'s Transactions" if lang=="en" else f"🧾 Transactions de {user.display_name}" if lang=="fr" else f"🧾 معاملات {user.display_name}")
        return discord.Embed(title=title,description="\n".join(lines),color=discord.Color.blurple())

    async def ensure_bank_panel(self, guild: discord.Guild):
        """Keep exactly one official Darija Bank panel; localized sessions are private."""
        channel_id = int(getattr(cfg, "ECONOMY_BANK_CHANNEL_ID", 0) or 0)
        channel = guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return
        matches = []
        try:
            async for msg in channel.history(limit=60):
                if (
                    msg.author == self.bot.user and msg.embeds
                    and (msg.embeds[0].title or "") == "🏦 GGMW9 Central Bank"
                ):
                    matches.append(msg)
        except discord.Forbidden:
            return
        embed = self.build_bank_panel_embed(guild, lang="darija")
        try:
            if matches:
                keep = matches[0]
                await keep.edit(content=None, embed=embed, view=EconomyBankPanelView(self,"darija"))
                for old in matches[1:]:
                    try:
                        await old.delete()
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        pass
            else:
                await channel.send(embed=embed, view=EconomyBankPanelView(self,"darija"))
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
        await self.refresh_fx_rates()
        for guild in self.bot.guilds:
            await self.process_bank_interest(guild)
            await self.ensure_bank_panel(guild)
            await self.ensure_big_win_channel(guild)
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
                "display_currency": "USD",
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
    def __init__(self, cog: "Economy", action: str, lang: str = "darija", session_key: str = "bank"):
        self.cog, self.action, self.lang, self.session_key = cog, action, lang, session_key
        if lang == "en":
            title = "🏦 Deposit to Savings" if action == "deposit" else "💸 Withdraw from Savings"; label="Amount in USD"; placeholder="Example: 25 or 25.50"
        elif lang == "fr":
            title = "🏦 Déposer sur l'épargne" if action == "deposit" else "💸 Retirer de l'épargne"; label="Montant en USD"; placeholder="Exemple : 25 ou 25.50"
        else:
            title = "🏦 Deposit فـSavings" if action == "deposit" else "💸 Withdraw من Savings"; label="المبلغ بالدولار"; placeholder="مثال: 25 أو 25.50"
        super().__init__(title=title)
        self.amount=discord.ui.TextInput(label=label,placeholder=placeholder,min_length=1,max_length=16,required=True); self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        amount=cfg.parse_money_input(self.amount.value)
        if amount is None:
            msg="❌ Enter a valid USD amount, e.g. `25` or `25.50`." if self.lang=="en" else "❌ Entre un montant USD valide, ex. `25` ou `25.50`." if self.lang=="fr" else "❌ دخل مبلغ دولار صحيح أكبر من $0.00. مثال: `25` أو `25.50`."
        else:
            ok,msg = await (self.cog.bank_deposit(interaction.guild,interaction.user,amount) if self.action=="deposit" else self.cog.bank_withdraw(interaction.guild,interaction.user,amount))
        await _upsert_panel(self.cog.bot,interaction,self.session_key,content=msg,embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=self.lang),view=BankSessionView(self.cog,interaction.user,self.lang,session_key=self.session_key))


class BankTransferAmountModal(discord.ui.Modal):
    def __init__(self,cog:"Economy",recipient:discord.Member,lang="darija",session_key="bank"):
        self.cog,self.recipient,self.lang,self.session_key=cog,recipient,lang,session_key
        super().__init__(title=f"💸 Transfer → {recipient.display_name}"[:45])
        label="Amount in USD" if lang=="en" else "Montant en USD" if lang=="fr" else "المبلغ بالدولار"
        placeholder="Example: 50 or 125.75" if lang=="en" else "Exemple : 50 ou 125.75" if lang=="fr" else "مثال: 50 أو 125.75"
        self.amount=discord.ui.TextInput(label=label,placeholder=placeholder,min_length=1,max_length=16,required=True); self.add_item(self.amount)
    async def on_submit(self,interaction):
        amount=cfg.parse_money_input(self.amount.value)
        if amount is None:
            msg="❌ Enter a valid amount." if self.lang=="en" else "❌ Entre un montant valide." if self.lang=="fr" else "❌ دخل مبلغ صحيح."
        else:
            ok,msg=await self.cog.bank_transfer(interaction.guild,interaction.user,self.recipient,amount)
        await _upsert_panel(self.cog.bot,interaction,self.session_key,content=msg,embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=self.lang),view=BankSessionView(self.cog,interaction.user,self.lang,session_key=self.session_key))


class BankTransferUserSelect(discord.ui.UserSelect):
    def __init__(self,cog:"Economy",owner_id:int,lang="darija",session_key="bank"):
        self.cog,self.owner_id,self.lang,self.session_key=cog,int(owner_id),lang,session_key
        ph="👤 Choose recipient..." if lang=="en" else "👤 Choisis le destinataire..." if lang=="fr" else "👤 اختار شكون غادي توصّلو الفلوس..."
        super().__init__(placeholder=ph,min_values=1,max_values=1)
    async def callback(self,interaction):
        if interaction.user.id!=self.owner_id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        picked=self.values[0]; recipient=interaction.guild.get_member(picked.id)
        if recipient is None:
            try: recipient=await interaction.guild.fetch_member(picked.id)
            except Exception: recipient=None
        if recipient is None or recipient.bot or recipient.id==interaction.user.id:
            msg="❌ Choose another human member." if self.lang=="en" else "❌ Choisis un autre membre humain." if self.lang=="fr" else "❌ اختار عضو بشري آخر."
            await interaction.response.edit_message(content=msg,embed=None,view=BankSessionView(self.cog,interaction.user,self.lang,session_key=self.session_key)); return
        await interaction.response.send_modal(BankTransferAmountModal(self.cog,recipient,self.lang,self.session_key))


class BankTransferUserView(discord.ui.View):
    def __init__(self,cog,owner_id,lang="darija",session_key="bank"):
        super().__init__(timeout=120); self.add_item(BankTransferUserSelect(cog,owner_id,lang,session_key))
        b=discord.ui.Button(label=_eco_t(lang,"back"),emoji="↩️",style=discord.ButtonStyle.secondary,row=1)
        async def back(interaction):
            await interaction.response.edit_message(content=None,embed=cog.build_user_account_embed(interaction.guild,interaction.user,lang=lang),view=BankSessionView(cog,interaction.user,lang,session_key=session_key))
        b.callback=back; self.add_item(b)


class LoanRequestModal(discord.ui.Modal):
    def __init__(self,cog:"Economy",guild_id:int,user_id:int,lang="darija",session_key="bank"):
        self.cog,self.lang,self.session_key=cog,lang,session_key; terms=cog.get_loan_terms(guild_id,user_id); limit=int(terms["effective_limit"]); minimum=int(getattr(cfg,"LOAN_MIN_AMOUNT",2500))
        title="💳 Request a GGMW9 Bank Loan" if lang=="en" else "💳 Demander un prêt GGMW9" if lang=="fr" else "💳 طلب قرض من GGMW9 Bank"
        super().__init__(title=title)
        label="Loan amount in USD" if lang=="en" else "Montant du prêt en USD" if lang=="fr" else "شحال بغيتي تسلف بالدولار؟"
        self.amount=discord.ui.TextInput(label=label,placeholder=f"{cfg.fmt_money(minimum)} → {cfg.fmt_money(limit)}",min_length=1,max_length=16,required=True); self.add_item(self.amount)
    async def on_submit(self,interaction):
        amount=cfg.parse_money_input(self.amount.value)
        if amount is None: msg="❌ Enter a valid USD amount." if self.lang=="en" else "❌ Entre un montant USD valide." if self.lang=="fr" else "❌ دخل مبلغ دولار صحيح."
        else: ok,msg=await self.cog.request_loan(interaction.guild,interaction.user,amount)
        await _upsert_panel(self.cog.bot,interaction,self.session_key,content=msg,embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=self.lang),view=BankSessionView(self.cog,interaction.user,self.lang,session_key=self.session_key))


class LoanRepayModal(discord.ui.Modal):
    def __init__(self,cog:"Economy",loan:dict,lang="darija",session_key="bank"):
        self.cog,self.lang,self.session_key=cog,lang,session_key; super().__init__(title=f"💸 Repay Loan #{loan.get('id')}")
        label="Amount to repay now" if lang=="en" else "Montant à rembourser" if lang=="fr" else "شحال بغيتي تخلص دابا بالدولار؟"
        ph=("Remaining " if lang=="en" else "Restant " if lang=="fr" else "الباقي ")+cfg.fmt_money(int(loan.get("remaining",0)))
        self.amount=discord.ui.TextInput(label=label,placeholder=ph,min_length=1,max_length=16,required=True); self.add_item(self.amount)
    async def on_submit(self,interaction):
        amount=cfg.parse_money_input(self.amount.value)
        if amount is None: msg="❌ Enter a valid USD amount." if self.lang=="en" else "❌ Entre un montant USD valide." if self.lang=="fr" else "❌ دخل مبلغ دولار صحيح."
        else: ok,msg=await self.cog.repay_loan(interaction.guild,interaction.user,amount)
        await _upsert_panel(self.cog.bot,interaction,self.session_key,content=msg,embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=self.lang),view=BankSessionView(self.cog,interaction.user,self.lang,session_key=self.session_key))


def _build_savings_embed(cog:"Economy",guild:discord.Guild,user:discord.Member,lang="darija"):
    bank=cog.get_bank_balance(guild.id,user.id); bps=cog.get_bank_interest_bps(guild.id,user.id); minimum=int(getattr(cfg,"BANK_INTEREST_MIN_BALANCE",2500)); cap=int(getattr(cfg,"BANK_INTEREST_DAILY_ACCOUNT_CAP",2500)); estimate=min(cap,bank*bps//10000) if bank>=minimum else 0; boost=cog._perk_active(guild.id,user.id,"bank_interest_boost_expires")
    if lang=="en": desc=f"🏦 Balance: **{cfg.fmt_money(bank)}**\n📈 Your rate: **{bps/100:.2f}% / day**\n🧮 Estimated next yield: **{cfg.fmt_money(estimate)}**\n\nInterest is paid **only from Treasury**; money is not created from nothing."; min_n="Minimum eligible balance"; cap_n="Daily account cap"; footer="Savings pay once per UTC day"
    elif lang=="fr": desc=f"🏦 Solde : **{cfg.fmt_money(bank)}**\n📈 Ton taux : **{bps/100:.2f}% / jour**\n🧮 Rendement estimé : **{cfg.fmt_money(estimate)}**\n\nLes intérêts sont payés **uniquement par le Trésor** ; aucun argent n'est créé."; min_n="Solde minimum éligible"; cap_n="Plafond quotidien"; footer="L'épargne est rémunérée une fois par jour UTC"
    else: desc=f"🏦 Balance: **{cfg.fmt_money(bank)}**\n📈 Rate ديالك: **{bps/100:.2f}% / day**\n🧮 Estimated next yield: **{cfg.fmt_money(estimate)}**\n\nالأرباح كتخلص **غير من Treasury** وما كنخلقوش فلوس من والو."; min_n="Minimum eligible balance"; cap_n="Daily account cap"; footer="Savings كتخلص مرة وحدة فكل UTC day"
    e=discord.Embed(title="📈 Savings Account",description=desc,color=discord.Color.green()); e.add_field(name=min_n,value=cfg.fmt_money(minimum),inline=True); e.add_field(name=cap_n,value=cfg.fmt_money(cap),inline=True); e.add_field(name="Shop Rate Boost",value="✅ Active" if boost else "—",inline=True); e.set_footer(text=footer); return e


def _build_assets_embed(cog:"Economy",guild:discord.Guild,user:discord.Member,lang="darija"):
    assets=cog.get_owned_assets(guild.id,user.id); book=cog.get_assets_value(guild.id,user.id); resale_pct=int(getattr(cfg,"ASSET_RESALE_PERCENT",40))
    if not assets: desc="📭 No assets yet. Buy them from Shop → Assets." if lang=="en" else "📭 Aucun actif. Achète-en dans Boutique → Actifs." if lang=="fr" else "📭 ماعندك حتى Asset دابا. شري الممتلكات من 🛒 Shop → 🏠 Assets."
    else:
        lines=[]
        for item_id,a in assets.items():
            paid=int(a.get("paid_price",0) or 0); resale=paid*resale_pct//100; lines.append(f"{a.get('emoji','🏠')} **{a.get('name',item_id)}** • Book {cfg.fmt_money(paid)} • Sell {cfg.fmt_money(resale)}")
        desc="\n".join(lines)
    title=f"🏠 Assets — {user.display_name}" if lang!="fr" else f"🏠 Actifs — {user.display_name}"
    e=discord.Embed(title=title,description=desc,color=discord.Color.gold()); e.add_field(name="Book Value" if lang!="fr" else "Valeur comptable",value=f"**{cfg.fmt_money(book)}**",inline=True); e.add_field(name="Market resale" if lang!="fr" else "Revente",value=f"**{resale_pct}%**",inline=True); return e


class AssetSellSelect(discord.ui.Select):
    def __init__(self,cog,user,lang="darija",session_key="bank"):
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key; assets=cog.get_owned_assets(user.guild.id,user.id); resale_pct=int(getattr(cfg,"ASSET_RESALE_PERCENT",40)); opts=[]
        for item_id,a in list(assets.items())[:25]:
            paid=int(a.get("paid_price",0) or 0); opts.append(discord.SelectOption(label=f"{a.get('name',item_id)} — {cfg.fmt_money(paid*resale_pct//100)}",value=item_id,emoji=a.get("emoji","🏠")))
        ph="🏷️ Choose an asset to sell..." if lang=="en" else "🏷️ Choisis un actif à vendre..." if lang=="fr" else "🏷️ اختار Asset باش تبيعها..."; super().__init__(placeholder=ph,options=opts,min_values=1,max_values=1)
    async def callback(self,interaction):
        if interaction.user.id!=self.user.id: await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.defer(ephemeral=True); ok,msg=await self.cog.sell_asset(interaction.guild,interaction.user,self.values[0]); await interaction.edit_original_response(content=msg,embed=_build_assets_embed(self.cog,interaction.guild,interaction.user,self.lang),view=AssetsView(self.cog,interaction.user,self.lang,self.session_key))


class AssetsView(discord.ui.View):
    def __init__(self,cog,user,lang="darija",session_key="bank"):
        super().__init__(timeout=180); self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
        if cog.get_owned_assets(user.guild.id,user.id): self.add_item(AssetSellSelect(cog,user,lang,session_key))
        b=discord.ui.Button(label=_eco_t(lang,"back"),emoji="↩️",style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)
        self.add_item(BankSessionLanguageSelect(cog,user,lang,session_key,row=2))
    async def back(self,interaction):
        if interaction.user.id!=self.user.id: await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.edit_message(content=None,embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=self.lang),view=BankSessionView(self.cog,interaction.user,self.lang,self.session_key))


class BankDisplayCurrencySelect(discord.ui.Select):
    def __init__(self,cog:"Economy",user:discord.Member,lang="darija",session_key="bank"):
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
        current=cog.get_display_currency(user.guild.id,user.id)
        labels={"USD":("US Dollar","Dollar US","الدولار الأمريكي"),"MAD":("Moroccan Dirham","Dirham marocain","الدرهم المغربي"),"EUR":("Euro","Euro","الأورو الأوروبي"),"DZD":("Algerian Dinar","Dinar algérien","الدينار الجزائري")}
        idx=1 if lang=="fr" else 0 if lang=="en" else 2
        opts=[]
        for code,meta in getattr(cfg,"DISPLAY_CURRENCIES",{}).items():
            text=labels.get(code,(meta.get("name",code),)*3)[idx]
            opts.append(discord.SelectOption(label=f"{text} ({code})",value=code,emoji=meta.get("emoji","💱"),default=(code==current)))
        placeholder="💱 Display currency" if lang=="en" else "💱 Devise d'affichage" if lang=="fr" else "💱 العملة اللي بغيتي تشوف بها الرصيد"
        super().__init__(placeholder=placeholder,options=opts,min_values=1,max_values=1,row=3)
    async def callback(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        code=self.cog.set_display_currency(interaction.guild.id,interaction.user.id,self.values[0])
        if self.lang=="en": msg=f"✅ Display currency: **{code}**. GGMW9 accounting still settles in USD."
        elif self.lang=="fr": msg=f"✅ Devise d'affichage : **{code}**. La comptabilité GGMW9 reste en USD."
        else: msg=f"✅ دابا الرصيد غادي يبان ليك حتى بـ **{code}**. الحسابات والرهانات كيبقاو بالدولار USD."
        await interaction.response.edit_message(content=msg,embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=self.lang),view=BankSessionView(self.cog,interaction.user,self.lang,self.session_key))



class BankSessionLanguageSelect(discord.ui.Select):
    """Rebuilds the member bank in the selected language on the SAME message."""
    def __init__(self, cog:"Economy", user:discord.Member, lang="darija", session_key="bank", *, row:int=4):
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
        options=[
            discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦",default=lang=="darija"),
            discord.SelectOption(label="English",value="en",emoji="🇬🇧",default=lang=="en"),
            discord.SelectOption(label="Français",value="fr",emoji="🇫🇷",default=lang=="fr"),
        ]
        super().__init__(placeholder="🌐 اللغة / Language / Langue",options=options,min_values=1,max_values=1,row=row)

    async def callback(self,interaction:discord.Interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        lang=_set_panel_lang(self.cog.bot,interaction.guild.id,interaction.user.id,self.values[0])
        await interaction.response.edit_message(
            content=_eco_t(lang,"lang_saved"),
            embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=lang),
            view=BankSessionView(self.cog,interaction.user,lang,self.session_key),
        )


class BankSessionView(discord.ui.View):
    """Private member bank. Every non-modal navigation edits the same message."""
    def __init__(self,cog:"Economy",user:discord.Member,lang="darija",session_key="bank"):
        super().__init__(timeout=300); self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
        items=[
            ("💳 "+_eco_t(lang,"account"),discord.ButtonStyle.primary,self.account),
            ("🏦 "+_eco_t(lang,"deposit"),discord.ButtonStyle.success,self.deposit),
            ("💸 "+_eco_t(lang,"withdraw"),discord.ButtonStyle.secondary,self.withdraw),
            ("💵 "+_eco_t(lang,"transfer"),discord.ButtonStyle.primary,self.transfer),
            ("📈 "+_eco_t(lang,"savings"),discord.ButtonStyle.success,self.savings),
            ("💳 "+_eco_t(lang,"loan"),discord.ButtonStyle.success,self.loan),
            ("💸 "+_eco_t(lang,"repay"),discord.ButtonStyle.primary,self.repay),
            ("🧾 "+_eco_t(lang,"transactions"),discord.ButtonStyle.secondary,self.transactions),
            ("🏠 "+_eco_t(lang,"assets"),discord.ButtonStyle.secondary,self.assets),
            ("⭐ "+_eco_t(lang,"xp"),discord.ButtonStyle.secondary,self.xp),
            ("📊 "+_eco_t(lang,"stats"),discord.ButtonStyle.secondary,self.stats),
        ]
        for i,(label,style,cb) in enumerate(items):
            b=discord.ui.Button(label=label[:80],style=style,row=i//5); b.callback=cb; self.add_item(b)
        self.add_item(BankDisplayCurrencySelect(cog,user,lang,session_key))
        self.add_item(BankSessionLanguageSelect(cog,user,lang,session_key,row=4))
    async def _ok(self,interaction):
        if interaction.user.id!=self.user.id: await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return False
        return True
    async def account(self,interaction):
        if await self._ok(interaction): await interaction.response.edit_message(content=None,embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=self.lang),view=self)
    async def deposit(self,interaction):
        if await self._ok(interaction): await interaction.response.send_modal(BankAmountModal(self.cog,"deposit",self.lang,self.session_key))
    async def withdraw(self,interaction):
        if await self._ok(interaction): await interaction.response.send_modal(BankAmountModal(self.cog,"withdraw",self.lang,self.session_key))
    async def transfer(self,interaction):
        if not await self._ok(interaction): return
        sent=self.cog.get_transfer_sent_today(interaction.guild.id,interaction.user.id); limit=self.cog.get_transfer_daily_limit(interaction.guild.id,interaction.user.id); fee_free=self.cog._perk_active(interaction.guild.id,interaction.user.id,"transfer_fee_pass_expires")
        if self.lang=="en": content=f"💵 **Bank→Bank Transfer**\n🏦 Savings: **{cfg.fmt_money(self.cog.get_bank_balance(interaction.guild.id,interaction.user.id))}**\n📊 Today: **{cfg.fmt_money(sent)} / {cfg.fmt_money(limit)}**\n"+("✅ Fee Pass active" if fee_free else f"💸 Fee: {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")+"\n\nChoose the recipient:"
        elif self.lang=="fr": content=f"💵 **Transfert Banque→Banque**\n🏦 Épargne : **{cfg.fmt_money(self.cog.get_bank_balance(interaction.guild.id,interaction.user.id))}**\n📊 Aujourd'hui : **{cfg.fmt_money(sent)} / {cfg.fmt_money(limit)}**\n"+("✅ Pass sans frais actif" if fee_free else f"💸 Frais : {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")+"\n\nChoisis le destinataire :"
        else: content=f"💵 **Bank→Bank Transfer**\n🏦 Savings: **{cfg.fmt_money(self.cog.get_bank_balance(interaction.guild.id,interaction.user.id))}**\n📊 Today: **{cfg.fmt_money(sent)} / {cfg.fmt_money(limit)}**\n"+("✅ Fee Pass active" if fee_free else f"💸 Fee: {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")+"\n\nاختار العضو اللي بغيتي تحول ليه:"
        await interaction.response.edit_message(content=content,embed=None,view=BankTransferUserView(self.cog,self.user.id,self.lang,self.session_key))
    async def savings(self,interaction):
        if await self._ok(interaction): await interaction.response.edit_message(content=None,embed=_build_savings_embed(self.cog,interaction.guild,interaction.user,self.lang),view=self)
    async def loan(self,interaction):
        if not await self._ok(interaction): return
        loan=self.cog.get_active_loan(interaction.guild.id,interaction.user.id)
        if loan:
            state="⚠️ Overdue" if self.cog._loan_is_overdue(loan) else "🟢 Active"; await interaction.response.edit_message(content=f"💳 Loan **#{loan.get('id')}** {state}\nRemaining: **{cfg.fmt_money(int(loan.get('remaining',0)))}**\nDue: <t:{self.cog._loan_due_unix(loan)}:F>",embed=None,view=self); return
        terms=self.cog.get_loan_terms(interaction.guild.id,interaction.user.id); minimum=int(getattr(cfg,"LOAN_MIN_AMOUNT",2500))
        if int(terms["effective_limit"])<minimum:
            await interaction.response.edit_message(content=f"❌ Loan limit: **{cfg.fmt_money(terms['effective_limit'])}** • minimum {cfg.fmt_money(minimum)}",embed=None,view=self); return
        await interaction.response.send_modal(LoanRequestModal(self.cog,interaction.guild.id,interaction.user.id,self.lang,self.session_key))
    async def repay(self,interaction):
        if not await self._ok(interaction): return
        loan=self.cog.get_active_loan(interaction.guild.id,interaction.user.id)
        if not loan:
            msg="ℹ️ No active loan." if self.lang=="en" else "ℹ️ Aucun prêt actif." if self.lang=="fr" else "ℹ️ ماعندك حتى قرض خدام دابا."; await interaction.response.edit_message(content=msg,embed=None,view=self); return
        await interaction.response.send_modal(LoanRepayModal(self.cog,loan,self.lang,self.session_key))
    async def transactions(self,interaction):
        if await self._ok(interaction): await interaction.response.edit_message(content=None,embed=self.cog.build_user_transactions_embed(interaction.guild,interaction.user,lang=self.lang),view=self)
    async def assets(self,interaction):
        if await self._ok(interaction): await interaction.response.edit_message(content=None,embed=_build_assets_embed(self.cog,interaction.guild,interaction.user,self.lang),view=AssetsView(self.cog,interaction.user,self.lang,self.session_key))
    async def xp(self,interaction):
        if await self._ok(interaction): await interaction.response.edit_message(content=None,embed=self.cog.build_xp_bank_perks_embed(interaction.guild,interaction.user,lang=self.lang),view=self)
    async def stats(self,interaction):
        if await self._ok(interaction): await interaction.response.edit_message(content=None,embed=self.cog.build_global_economy_embed(interaction.guild,lang=self.lang),view=self)


class BankLanguageSelect(discord.ui.Select):
    """Public Darija Bank selector; opens a fresh private localized bank session."""
    def __init__(self,cog,lang="darija"):
        self.cog=cog; self.lang=lang if lang in {"darija","en","fr"} else "darija"
        super().__init__(
            placeholder="🌐 اللغة / Language / Langue",
            options=[
                discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦",default=self.lang=="darija"),
                discord.SelectOption(label="English",value="en",emoji="🇬🇧",default=self.lang=="en"),
                discord.SelectOption(label="Français",value="fr",emoji="🇫🇷",default=self.lang=="fr"),
            ],
            custom_id="ggmw9:economy:language",row=1,
        )
    async def callback(self,interaction):
        lang=_set_panel_lang(self.cog.bot,interaction.guild.id,interaction.user.id,self.values[0])
        await _fresh_panel(
            interaction,
            content=_eco_t(lang,"lang_saved"),
            embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=lang),
            view=BankSessionView(self.cog,interaction.user,lang,"bank"),
        )


class EconomyBankPanelView(discord.ui.View):
    """Official public Bank panel is ALWAYS Darija; localized sessions are private."""
    def __init__(self,cog,lang="darija"):
        super().__init__(timeout=None); self.cog=cog; self.lang="darija"
        open_label="🏦 فتح البنك ديالي"
        stats_label="📊 إحصائيات الاقتصاد"
        b1=discord.ui.Button(label=open_label,style=discord.ButtonStyle.success,custom_id="ggmw9:economy:open_bank",row=0); b1.callback=self.open_bank; self.add_item(b1)
        b2=discord.ui.Button(label=stats_label,style=discord.ButtonStyle.secondary,custom_id="ggmw9:economy:public_stats",row=0); b2.callback=self.stats; self.add_item(b2)
        self.add_item(BankLanguageSelect(cog,self.lang))

    def _sync(self,interaction):
        return _panel_lang(self.cog.bot,interaction.guild.id,interaction.user.id)

    async def open_bank(self,interaction):
        lang=self._sync(interaction)
        await _fresh_panel(interaction,content=None,embed=self.cog.build_user_account_embed(interaction.guild,interaction.user,lang=lang),view=BankSessionView(self.cog,interaction.user,lang,"bank"))

    async def stats(self,interaction):
        lang=self._sync(interaction)
        await _fresh_panel(interaction,content=None,embed=self.cog.build_global_economy_embed(interaction.guild,lang=lang),view=BankSessionView(self.cog,interaction.user,lang,"bank"))


def build_shop_home_embed(cog:"Economy",guild:discord.Guild,user:discord.Member,lang="darija"):
    balance=cog.get_balance(guild.id,user.id); bank=cog.get_bank_balance(guild.id,user.id); discount=cog.get_shop_discount_percent(guild.id,user.id); lines=[]
    for cid,cat in cfg.SHOP_CATEGORIES.items():
        emoji,name,desc=_shop_category_text(cid,lang); count=sum(1 for i in cfg.SHOP_ITEMS if i.get("category")==cid); lines.append(f"{emoji} **{name}** — {desc} `({count})`")
    if lang=="en": intro=f"💳 Wallet: **{cfg.fmt_money(balance)}** • 🏦 Savings: **{cfg.fmt_money(bank)}**\n"+(f"⭐ Level Discount: **-{discount}%**\n" if discount else "")+"\n"+"\n".join(lines)+"\n\nChoose a category. Every item has a real server utility, asset or prestige purpose."
    elif lang=="fr": intro=f"💳 Wallet : **{cfg.fmt_money(balance)}** • 🏦 Épargne : **{cfg.fmt_money(bank)}**\n"+(f"⭐ Réduction de niveau : **-{discount}%**\n" if discount else "")+"\n"+"\n".join(lines)+"\n\nChoisis une catégorie. Chaque article a une utilité, un actif ou un rôle de prestige."
    else: intro=f"💳 Wallet: **{cfg.fmt_money(balance)}** • 🏦 Savings: **{cfg.fmt_money(bank)}**\n"+(f"⭐ Level Discount: **-{discount}%**\n" if discount else "")+"\n"+"\n".join(lines)+"\n\nاختار Category من اللائحة. المتجر فيه utility + assets + prestige باش الفلوس يكون عندها معنى."
    e=discord.Embed(title="🛒 GGMW9 Marketplace",description=intro,color=discord.Color.blurple()); e.set_footer(text="🌐 Darija • English • Français | Shop spend → Treasury + Events + Burn"); return e


def build_shop_category_embed(cog:"Economy",guild:discord.Guild,user:discord.Member,category_id:str,lang="darija"):
    emoji,name,desc=_shop_category_text(category_id,lang); balance=cog.get_balance(guild.id,user.id); discount=cog.get_shop_discount_percent(guild.id,user.id); items=[i for i in cfg.SHOP_ITEMS if i.get("category")==category_id]; lines=[]
    for item in items:
        price=cog.get_shop_price(guild.id,user.id,item["price"]); affordable="✅" if balance>=price else "❌"; price_text=f"~~{cfg.fmt_money(item['price'])}~~ → **{cfg.fmt_money(price)}**" if price!=int(item["price"]) else f"**{cfg.fmt_money(price)}**"; lines.append(f"{affordable} {item['emoji']} **{item['name']}** — {price_text}\n↳ {_shop_item_desc(item,lang)}")
    empty="📭 This category is empty." if lang=="en" else "📭 Cette catégorie est vide." if lang=="fr" else "📭 هاد Category خاوية دابا."
    return discord.Embed(title=f"{emoji} {name}",description=f"💳 Wallet: **{cfg.fmt_money(balance)}**"+(f" • ⭐ -{discount}%" if discount else "")+"\n\n"+("\n\n".join(lines) if lines else empty),color=discord.Color.blurple())


class ShopCategorySelect(discord.ui.Select):
    def __init__(self,cog,user,lang="darija",session_key="shop"):
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key; opts=[]
        for cid in cfg.SHOP_CATEGORIES:
            emoji,name,desc=_shop_category_text(cid,lang); opts.append(discord.SelectOption(label=name,value=cid,emoji=emoji,description=desc[:100]))
        super().__init__(placeholder=_eco_t(lang,"shop_choose"),options=opts,min_values=1,max_values=1)
    async def callback(self,interaction):
        if interaction.user.id!=self.user.id: await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        cid=self.values[0]; await interaction.response.edit_message(content=None,embed=build_shop_category_embed(self.cog,interaction.guild,interaction.user,cid,self.lang),view=ShopItemsView(self.cog,interaction.user,cid,self.lang,self.session_key))



class ShopSessionLanguageSelect(discord.ui.Select):
    def __init__(self,cog:"Economy",user:discord.Member,lang="darija",session_key="shop",*,row:int=1):
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
        options=[
            discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦",default=lang=="darija"),
            discord.SelectOption(label="English",value="en",emoji="🇬🇧",default=lang=="en"),
            discord.SelectOption(label="Français",value="fr",emoji="🇫🇷",default=lang=="fr"),
        ]
        super().__init__(placeholder="🌐 اللغة / Language / Langue",options=options,min_values=1,max_values=1,row=row)

    async def callback(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        lang=_set_panel_lang(self.cog.bot,interaction.guild.id,interaction.user.id,self.values[0])
        await interaction.response.edit_message(
            content=_eco_t(lang,"lang_saved"),
            embed=build_shop_home_embed(self.cog,interaction.guild,interaction.user,lang),
            view=ShopView(self.cog,interaction.user,lang,self.session_key),
        )


class ShopView(discord.ui.View):
    def __init__(self,cog,user,lang="darija",session_key="shop"):
        super().__init__(timeout=900); self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
        self.add_item(ShopCategorySelect(cog,user,lang,session_key))
        self.add_item(ShopSessionLanguageSelect(cog,user,lang,session_key,row=1))


class ShopBackButton(discord.ui.Button):
    def __init__(self,cog,user,lang="darija",session_key="shop"):
        super().__init__(label=_eco_t(lang,"shop_back"),emoji="↩️",style=discord.ButtonStyle.secondary,row=1); self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
    async def callback(self,interaction):
        if interaction.user.id!=self.user.id: await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.edit_message(content=None,embed=build_shop_home_embed(self.cog,interaction.guild,interaction.user,self.lang),view=ShopView(self.cog,interaction.user,self.lang,self.session_key))


class ShopItemsView(discord.ui.View):
    def __init__(self,cog,user,category_id,lang="darija",session_key="shop"):
        super().__init__(timeout=900)
        self.add_item(ShopItemSelect(cog,user,category_id,lang,session_key))
        self.add_item(ShopBackButton(cog,user,lang,session_key))
        self.add_item(ShopSessionLanguageSelect(cog,user,lang,session_key,row=2))


class ShopItemSelect(discord.ui.Select):
    def __init__(self,cog,user,category_id,lang="darija",session_key="shop"):
        self.cog,self.user,self.category_id,self.lang,self.session_key=cog,user,category_id,lang,session_key; items=[i for i in cfg.SHOP_ITEMS if i.get("category")==category_id]; opts=[]
        for item in items[:25]:
            price=cog.get_shop_price(user.guild.id,user.id,item["price"]); opts.append(discord.SelectOption(label=f"{item['name']} — {cfg.fmt_money(price)}"[:100],value=item["id"],emoji=item["emoji"],description=_shop_item_desc(item,lang)[:100]))
        super().__init__(placeholder=_eco_t(lang,"shop_item"),options=opts,min_values=1,max_values=1)
    async def callback(self,interaction):
        if interaction.user.id!=self.user.id: await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        item=next((i for i in cfg.SHOP_ITEMS if i["id"]==self.values[0]),None)
        if not item: await interaction.response.edit_message(content="❌ Item unavailable.",embed=None,view=ShopView(self.cog,self.user,self.lang,self.session_key)); return
        price=self.cog.get_shop_price(interaction.guild.id,interaction.user.id,item["price"]); balance=self.cog.get_balance(interaction.guild.id,interaction.user.id)
        if balance<price:
            msg=f"❌ You need **{cfg.fmt_money(price-balance)}** more in Wallet." if self.lang=="en" else f"❌ Il te manque **{cfg.fmt_money(price-balance)}** dans le Wallet." if self.lang=="fr" else f"❌ ناقصك **{cfg.fmt_money(price-balance)}** فالWallet."
            await interaction.response.edit_message(content=msg,embed=build_shop_category_embed(self.cog,interaction.guild,interaction.user,self.category_id,self.lang),view=ShopItemsView(self.cog,self.user,self.category_id,self.lang,self.session_key)); return
        priced=dict(item); priced["_final_price"]=price
        if item["type"] in {"role_color","role_color_perm"}:
            await interaction.response.edit_message(content=f"🎨 {item['name']} — {cfg.fmt_money(price)}",embed=None,view=ColorPickView(self.cog,self.user,priced,self.category_id,self.lang,self.session_key)); return
        if item["type"]=="custom_role":
            await interaction.response.send_modal(CustomRoleModal(self.cog,priced,self.category_id,self.lang,self.session_key)); return
        await interaction.response.defer(ephemeral=True); ok,msg,_=await execute_purchase(self.cog,interaction.guild,interaction.user,priced); prefix="✅ " if ok else "❌ "; await interaction.edit_original_response(content=prefix+msg,embed=build_shop_category_embed(self.cog,interaction.guild,interaction.user,self.category_id,self.lang),view=ShopItemsView(self.cog,self.user,self.category_id,self.lang,self.session_key))


class ColorPickView(discord.ui.View):
    def __init__(self,cog,user,item,category_id="identity",lang="darija",session_key="shop"):
        super().__init__(timeout=120); self.cog,self.user,self.item,self.category_id,self.lang,self.session_key=cog,user,item,category_id,lang,session_key
        opts=[discord.SelectOption(label=name,value=str(value)) for name,value in cfg.SHOP_COLORS.items()]; sel=discord.ui.Select(placeholder="🎨 Choose color..." if lang=="en" else "🎨 Choisis une couleur..." if lang=="fr" else "🎨 اختار اللون...",options=opts); sel.callback=self.on_pick; self.select=sel; self.add_item(sel); self.add_item(ShopBackButton(cog,user,lang,session_key)); self.add_item(ShopSessionLanguageSelect(cog,user,lang,session_key,row=2))
    async def on_pick(self,interaction):
        if interaction.user.id!=self.user.id: await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.defer(ephemeral=True); item=dict(self.item); item["color"]=int(self.select.values[0]); ok,msg,_=await execute_purchase(self.cog,interaction.guild,interaction.user,item); await interaction.edit_original_response(content=("✅ " if ok else "❌ ")+msg,embed=build_shop_category_embed(self.cog,interaction.guild,interaction.user,self.category_id,self.lang),view=ShopItemsView(self.cog,self.user,self.category_id,self.lang,self.session_key))


class CustomRoleModal(discord.ui.Modal):
    def __init__(self,cog,item,category_id="identity",lang="darija",session_key="shop"):
        self.cog,self.item,self.category_id,self.lang,self.session_key=cog,item,category_id,lang,session_key
        title="🏷️ Your Custom Role" if lang=="en" else "🏷️ Ton rôle personnalisé" if lang=="fr" else "🏷️ الرول المخصص ديالك"; super().__init__(title=title)
        label="Role name" if lang=="en" else "Nom du rôle" if lang=="fr" else "سمية الرول"; self.role_name=discord.ui.TextInput(label=label,max_length=32,placeholder="King of GGMW9"); self.add_item(self.role_name)
    async def on_submit(self,interaction):
        item=dict(self.item); item["custom_name"]=str(self.role_name.value).strip()
        if not item["custom_name"]: msg="❌ Empty name."
        else: ok,msg,_=await execute_purchase(self.cog,interaction.guild,interaction.user,item); msg=("✅ " if ok else "❌ ")+msg
        await _upsert_panel(self.cog.bot,interaction,self.session_key,content=msg,embed=build_shop_category_embed(self.cog,interaction.guild,interaction.user,self.category_id,self.lang),view=ShopItemsView(self.cog,interaction.user,self.category_id,self.lang,self.session_key))


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
