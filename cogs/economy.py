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
import re
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
    """Bank/Shop UI labels. No mixed-language controls are allowed."""
    data = {
        "darija": {
            "not_yours":"❌ هاد الجلسة ماشي ديالك.",
            "back":"رجع للبنك",
            "account":"حسابي",
            "deposit":"إيداع",
            "withdraw":"سحب",
            "transfer":"تحويل",
            "savings":"الادخار",
            "loan":"طلب قرض",
            "repay":"تسديد القرض",
            "transactions":"المعاملات",
            "assets":"الممتلكات",
            "stats":"الاقتصاد",
            "xp":"امتيازات XP",
            "open_bank":"فتح البنك ديالي",
            "shop_choose":"🗂️ اختار القسم...",
            "shop_item":"🛒 اختار المنتوج اللي بغيتي تشري...",
            "shop_back":"رجع للأقسام",
            "lang_saved":"✅ اللغة ديالك ولات **الدارجة**.",
        },
        "en": {
            "not_yours":"❌ This session belongs to another member.",
            "back":"Back to Bank",
            "account":"My Account",
            "deposit":"Deposit",
            "withdraw":"Withdraw",
            "transfer":"Transfer",
            "savings":"Savings",
            "loan":"Request Loan",
            "repay":"Repay Loan",
            "transactions":"Transactions",
            "assets":"Assets",
            "stats":"Economy",
            "xp":"XP Perks",
            "open_bank":"Open My Bank",
            "shop_choose":"🗂️ Choose a category...",
            "shop_item":"🛒 Choose an item to buy...",
            "shop_back":"Back to Categories",
            "lang_saved":"✅ Your language is now **English**.",
        },
        "fr": {
            "not_yours":"❌ Cette session appartient à un autre membre.",
            "back":"Retour à la banque",
            "account":"Mon compte",
            "deposit":"Déposer",
            "withdraw":"Retirer",
            "transfer":"Transférer",
            "savings":"Épargne",
            "loan":"Demander un prêt",
            "repay":"Rembourser le prêt",
            "transactions":"Transactions",
            "assets":"Actifs",
            "stats":"Économie",
            "xp":"Avantages XP",
            "open_bank":"Ouvrir ma banque",
            "shop_choose":"🗂️ Choisis une catégorie...",
            "shop_item":"🛒 Choisis un article...",
            "shop_back":"Retour aux catégories",
            "lang_saved":"✅ Ta langue est maintenant **le français**.",
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
        supported_shop_types = {
            "xp_boost","coins_boost","role_color","role_color_perm","custom_role",
            "legend_tag","title_role","bank_interest_boost","transfer_fee_pass",
            "collectible_asset","shoutout",
        }
        configured_types = {str(i.get("type")) for i in getattr(cfg,"SHOP_ITEMS",[]) if i.get("type")}
        unknown = sorted(configured_types - supported_shop_types)
        if unknown:
            print(f"[SHOP AUDIT] ❌ Product types without real handler: {unknown}")
        else:
            print(f"[SHOP AUDIT] ✅ All {len(getattr(cfg,'SHOP_ITEMS',[]))} products map to real handlers.")
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

                    # الشراء خلصت مدتو — خاص التأثير يتحيد بصح.
                    # إلا Discord رفض العملية، نخلي الـentry باش نعاود المحاولة
                    # وما نخليوش perk مؤقت يتحول لدائم بالغلط.
                    if guild is None:
                        still_active.append(p)
                        continue

                    try:
                        member = guild.get_member(int(user_id_str)) or await guild.fetch_member(int(user_id_str))
                    except discord.NotFound:
                        member = None
                    except Exception:
                        still_active.append(p)
                        continue

                    role = guild.get_role(int(p.get("role_id") or 0)) if p.get("role_id") else None
                    removed_ok = True

                    if member and role and role in member.roles:
                        try:
                            await member.remove_roles(role, reason="انتهت مدة الشراء من المتجر")
                        except Exception as e:
                            removed_ok = False
                            print(f"[SHOP EXPIRE] ⚠️ ماقدرتش نحيد {role} من {user_id_str}: {e}")

                    if not removed_ok:
                        still_active.append(p)
                        continue

                    # Personal color/custom-role purchases are unique roles.
                    # Delete them too so the server role list does not fill up.
                    if role and p.get("delete_role_on_expiry"):
                        try:
                            await role.delete(reason="انتهت مدة Role المشتراة من GGMW9 Shop")
                        except discord.Forbidden:
                            # The benefit is already removed from the member.
                            print(f"[SHOP EXPIRE] ⚠️ تحيدات من العضو ولكن ماقدرتش نمسح Role {role.id}")
                        except discord.HTTPException as e:
                            print(f"[SHOP EXPIRE] ⚠️ Discord ماقبلش مسح Role {role.id}: {e}")

                    changed = True

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
            # role_id -> {"original_color": int, "fallback_role_id": int}
            # Used so Admin/Moderator can keep their sidebar group while
            # a lower personal color role controls only the visible name color.
            "staff_color_passthrough": {},
            # GGMW9 CITY — money never disappears outside the central ledger.
            "city_escrow": {},
            "city_business_accounts": {},
            "city_wage_protection": {"date": None, "used": 0},
            "city_seed_done": False,
            "total_city_tax": 0,
            "total_city_payroll": 0,
            "total_city_services": 0,
            "total_city_projects": 0,
            # Underground stays inside the same USD money supply, but it is
            # intentionally not exposed as a public Economy panel category.
            "city_crew_accounts": {},
            "total_city_underground": 0,
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
    # GGMW9 CITY — Escrow / Business / Payroll API
    # ════════════════════════════════════════════════

    def city_business_account(self, guild_id: int, business_id: str) -> dict:
        sys = self._system(guild_id)
        return sys.setdefault("city_business_accounts", {}).setdefault(
            str(business_id),
            {"operating": 0, "payroll": 0, "profit": 0, "revenue": 0, "payroll_paid": 0},
        )

    def city_business_totals(self, guild_id: int) -> dict:
        accounts = self._system(guild_id).get("city_business_accounts", {}) or {}
        totals = {"operating": 0, "payroll": 0, "profit": 0, "revenue": 0, "payroll_paid": 0}
        for acc in accounts.values():
            for key in totals:
                totals[key] += max(0, int(acc.get(key, 0) or 0))
        return totals

    def city_escrow_total(self, guild_id: int) -> int:
        total = 0
        for entry in (self._system(guild_id).get("city_escrow", {}) or {}).values():
            total += max(0, int((entry or {}).get("amount", 0) or 0))
        return total

    def city_get_escrow(self, guild_id: int, escrow_key: str) -> dict:
        return dict((self._system(guild_id).get("city_escrow", {}) or {}).get(str(escrow_key)) or {})

    def city_hold_escrow(
        self,
        guild_id: int,
        user_id: int,
        escrow_key: str,
        amount: int,
        *,
        kind: str,
        description: str,
    ) -> bool:
        amount = max(0, int(amount))
        if amount <= 0 or not self.spend(guild_id, user_id, amount):
            return False
        sys = self._system(guild_id)
        key = str(escrow_key)
        if key in sys.setdefault("city_escrow", {}):
            # Defensive rollback: a duplicate escrow key must never double-charge.
            self.add_coins(guild_id, user_id, amount, source="city_escrow_rollback", respect_cap=False, count_as_earned=False)
            return False
        sys["city_escrow"][key] = {
            "amount": amount,
            "owner_id": int(user_id),
            "kind": str(kind),
            "description": str(description)[:300],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._record_transaction(
            guild_id,
            user_id=user_id,
            kind="city_escrow_hold",
            amount=-amount,
            source=kind,
            description=description,
            splits={"escrow_key": key},
        )
        self.system_db.save()
        return True

    def city_refund_escrow(self, guild_id: int, escrow_key: str, *, reason: str = "refund") -> int:
        sys = self._system(guild_id)
        entry = sys.setdefault("city_escrow", {}).pop(str(escrow_key), None)
        if not entry:
            return 0
        amount = max(0, int(entry.get("amount", 0) or 0))
        user_id = int(entry.get("owner_id", 0) or 0)
        if user_id and amount:
            self.add_coins(guild_id, user_id, amount, source="city_escrow_refund", respect_cap=False, count_as_earned=False)
            self._record_transaction(
                guild_id,
                user_id=user_id,
                kind="city_escrow_refund",
                amount=amount,
                source=str(entry.get("kind") or "city"),
                description=reason,
                splits={"escrow_key": str(escrow_key)},
            )
        self.system_db.save()
        return amount

    def city_release_service_escrow(
        self,
        guild_id: int,
        escrow_key: str,
        *,
        worker_id: int,
        business_id: str,
        worker_share_bps: int,
        tax_bps: int,
        description: str,
    ) -> dict:
        sys = self._system(guild_id)
        entry = sys.setdefault("city_escrow", {}).pop(str(escrow_key), None)
        if not entry:
            return {"gross": 0, "worker": 0, "tax": 0, "business": 0}
        gross = max(0, int(entry.get("amount", 0) or 0))
        tax_bps = max(0, min(3000, int(tax_bps)))
        worker_share_bps = max(0, min(9500, int(worker_share_bps)))
        tax = gross * tax_bps // 10000
        distributable = gross - tax
        worker_pay = distributable * worker_share_bps // 10000
        business_total = distributable - worker_pay

        payroll_bps = int(getattr(cfg, "CITY_BUSINESS_PAYROLL_SHARE_BPS", 5500) or 5500)
        operating_bps = int(getattr(cfg, "CITY_BUSINESS_OPERATING_SHARE_BPS", 3000) or 3000)
        payroll = business_total * payroll_bps // 10000
        operating = business_total * operating_bps // 10000
        profit = business_total - payroll - operating

        if worker_pay:
            self._set_bank_balance(guild_id, worker_id, self.get_bank_balance(guild_id, worker_id) + worker_pay)
        business = self.city_business_account(guild_id, business_id)
        business["payroll"] = max(0, int(business.get("payroll", 0) or 0)) + payroll
        business["operating"] = max(0, int(business.get("operating", 0) or 0)) + operating
        business["profit"] = max(0, int(business.get("profit", 0) or 0)) + profit
        business["revenue"] = max(0, int(business.get("revenue", 0) or 0)) + gross
        sys["treasury"] = max(0, int(sys.get("treasury", 0) or 0)) + tax
        sys["total_city_tax"] = int(sys.get("total_city_tax", 0) or 0) + tax
        sys["total_city_services"] = int(sys.get("total_city_services", 0) or 0) + gross

        self._record_transaction(
            guild_id,
            user_id=worker_id,
            kind="city_service_income",
            amount=worker_pay,
            source="services_market",
            description=description,
            splits={
                "gross": gross, "tax": tax, "business": business_total,
                "payroll": payroll, "operating": operating, "profit": profit,
            },
        )
        self.system_db.save()
        return {
            "gross": gross, "worker": worker_pay, "tax": tax, "business": business_total,
            "payroll": payroll, "operating": operating, "profit": profit,
        }

    def city_release_project_escrow(
        self,
        guild_id: int,
        escrow_key: str,
        *,
        worker_id: int,
        release_amount: int,
        tax_bps: int,
        description: str,
    ) -> dict:
        sys = self._system(guild_id)
        key = str(escrow_key)
        entry = sys.setdefault("city_escrow", {}).get(key)
        if not entry:
            return {"gross": 0, "worker": 0, "tax": 0, "remaining": 0}
        remaining = max(0, int(entry.get("amount", 0) or 0))
        gross = min(remaining, max(0, int(release_amount)))
        if gross <= 0:
            return {"gross": 0, "worker": 0, "tax": 0, "remaining": remaining}
        tax = gross * max(0, min(3000, int(tax_bps))) // 10000
        worker_pay = gross - tax
        entry["amount"] = remaining - gross
        if int(entry["amount"]) <= 0:
            sys["city_escrow"].pop(key, None)
        if worker_pay:
            self._set_bank_balance(guild_id, worker_id, self.get_bank_balance(guild_id, worker_id) + worker_pay)
        sys["treasury"] = max(0, int(sys.get("treasury", 0) or 0)) + tax
        sys["total_city_tax"] = int(sys.get("total_city_tax", 0) or 0) + tax
        sys["total_city_projects"] = int(sys.get("total_city_projects", 0) or 0) + gross
        self._record_transaction(
            guild_id,
            user_id=worker_id,
            kind="city_project_income",
            amount=worker_pay,
            source="projects_board",
            description=description,
            splits={"gross": gross, "tax": tax, "escrow_key": key},
        )
        self.system_db.save()
        return {"gross": gross, "worker": worker_pay, "tax": tax, "remaining": max(0, remaining-gross)}

    def city_direct_tip(self, guild_id: int, customer_id: int, worker_id: int, amount: int, description: str) -> bool:
        amount = max(0, int(amount))
        if amount <= 0 or not self.spend(guild_id, customer_id, amount):
            return False
        self._set_bank_balance(guild_id, worker_id, self.get_bank_balance(guild_id, worker_id) + amount)
        self._record_transaction(
            guild_id, user_id=customer_id, kind="city_tip_sent", amount=-amount,
            source="city_tip", description=description, splits={"worker_id": worker_id},
        )
        self._record_transaction(
            guild_id, user_id=worker_id, kind="city_tip_received", amount=amount,
            source="city_tip", description=description, splits={"customer_id": customer_id},
        )
        self.system_db.save()
        return True

    def city_treasury_bonus_to_bank(self, guild_id: int, user_id: int, amount: int, description: str) -> int:
        sys = self._system(guild_id)
        amount = min(max(0, int(amount)), max(0, int(sys.get("treasury", 0) or 0)))
        if amount <= 0:
            return 0
        sys["treasury"] -= amount
        self._set_bank_balance(guild_id, user_id, self.get_bank_balance(guild_id, user_id) + amount)
        self._record_transaction(
            guild_id, user_id=user_id, kind="city_treasury_bonus", amount=amount,
            source="ggmw9_city", description=description, splits={"treasury": -amount},
        )
        self.system_db.save()
        return amount

    def city_pay_salary(
        self,
        guild_id: int,
        business_id: str,
        worker_id: int,
        amount: int,
        description: str,
    ) -> dict:
        amount = max(0, int(amount))
        business = self.city_business_account(guild_id, business_id)
        payroll_available = max(0, int(business.get("payroll", 0) or 0))
        from_business = min(amount, payroll_available)
        short = amount - from_business

        sys = self._system(guild_id)
        today = datetime.now(timezone.utc).date().isoformat()
        protection = sys.setdefault("city_wage_protection", {"date": None, "used": 0})
        if protection.get("date") != today:
            protection.clear(); protection.update({"date": today, "used": 0})
        treasury = max(0, int(sys.get("treasury", 0) or 0))
        dynamic_cap = treasury * int(getattr(cfg, "CITY_WAGE_PROTECTION_TREASURY_BPS", 300) or 300) // 10000
        daily_cap = min(int(getattr(cfg, "CITY_WAGE_PROTECTION_DAILY_CAP", 25000) or 25000), dynamic_cap)
        remaining_protection = max(0, daily_cap - int(protection.get("used", 0) or 0))
        from_protection = min(short, treasury, remaining_protection)
        paid = from_business + from_protection

        if from_business:
            business["payroll"] = payroll_available - from_business
        if from_protection:
            sys["treasury"] = treasury - from_protection
            protection["used"] = int(protection.get("used", 0) or 0) + from_protection
        if paid:
            self._set_bank_balance(guild_id, worker_id, self.get_bank_balance(guild_id, worker_id) + paid)
            business["payroll_paid"] = int(business.get("payroll_paid", 0) or 0) + paid
            sys["total_city_payroll"] = int(sys.get("total_city_payroll", 0) or 0) + paid
            self._record_transaction(
                guild_id, user_id=worker_id, kind="city_salary", amount=paid,
                source=str(business_id), description=description,
                splits={"business_payroll": from_business, "wage_protection": from_protection, "due": amount-paid},
            )
        self.system_db.save()
        return {"requested": amount, "paid": paid, "due": max(0, amount-paid), "business": from_business, "protection": from_protection}

    def city_crew_account(self, guild_id: int, crew_id: str) -> dict:
        sys = self._system(guild_id)
        return sys.setdefault("city_crew_accounts", {}).setdefault(
            str(crew_id), {"balance": 0, "deposited": 0, "heist_income": 0, "spent": 0}
        )

    def city_crew_total(self, guild_id: int) -> int:
        total = 0
        for acc in (self._system(guild_id).get("city_crew_accounts", {}) or {}).values():
            total += max(0, int((acc or {}).get("balance", 0) or 0))
        return total

    def city_crew_deposit(self, guild_id: int, user_id: int, crew_id: str, amount: int) -> bool:
        amount = max(0, int(amount))
        if amount <= 0 or not self.spend(guild_id, user_id, amount):
            return False
        acc = self.city_crew_account(guild_id, crew_id)
        acc["balance"] = int(acc.get("balance", 0) or 0) + amount
        acc["deposited"] = int(acc.get("deposited", 0) or 0) + amount
        self._record_transaction(
            guild_id, user_id=user_id, kind="city_crew_deposit", amount=-amount,
            source="underground_crew", description=f"Crew vault deposit {crew_id}",
            splits={"crew_id": str(crew_id)},
        )
        self.system_db.save()
        return True

    def city_crew_spend(self, guild_id: int, crew_id: str, amount: int, description: str) -> bool:
        amount = max(0, int(amount))
        acc = self.city_crew_account(guild_id, crew_id)
        balance = max(0, int(acc.get("balance", 0) or 0))
        if amount <= 0 or balance < amount:
            return False
        acc["balance"] = balance - amount
        acc["spent"] = int(acc.get("spent", 0) or 0) + amount
        # Preparation spending becomes Treasury revenue rather than vanishing.
        sys = self._system(guild_id)
        sys["treasury"] = max(0, int(sys.get("treasury", 0) or 0)) + amount
        sys["total_city_underground"] = int(sys.get("total_city_underground", 0) or 0) + amount
        self._record_transaction(
            guild_id, user_id=0, kind="city_crew_spend", amount=-amount,
            source="underground_operation", description=description,
            splits={"crew_id": str(crew_id), "treasury": amount},
        )
        self.system_db.save()
        return True

    def city_underground_supply_purchase(self, guild_id: int, buyer_id: int, amount: int, description: str) -> bool:
        amount = max(0, int(amount))
        if amount <= 0 or not self.spend(guild_id, buyer_id, amount):
            return False
        # The fictional supplier is the CITY Treasury; no money disappears.
        sys = self._system(guild_id)
        sys["treasury"] = max(0, int(sys.get("treasury", 0) or 0)) + amount
        sys["total_city_underground"] = int(sys.get("total_city_underground", 0) or 0) + amount
        self._record_transaction(
            guild_id, user_id=buyer_id, kind="city_underground_supply", amount=-amount,
            source="black_market", description=description, splits={"treasury": amount},
        )
        self.system_db.save()
        return True

    def city_release_underground_escrow(
        self, guild_id: int, escrow_key: str, *, seller_id: int, tax_bps: int, description: str
    ) -> dict:
        sys = self._system(guild_id)
        entry = sys.setdefault("city_escrow", {}).pop(str(escrow_key), None)
        if not entry:
            return {"gross": 0, "seller": 0, "tax": 0}
        gross = max(0, int(entry.get("amount", 0) or 0))
        tax = gross * max(0, min(3000, int(tax_bps))) // 10000
        seller_pay = gross - tax
        if seller_pay:
            self._set_bank_balance(guild_id, seller_id, self.get_bank_balance(guild_id, seller_id) + seller_pay)
        sys["treasury"] = max(0, int(sys.get("treasury", 0) or 0)) + tax
        sys["total_city_underground"] = int(sys.get("total_city_underground", 0) or 0) + gross
        self._record_transaction(
            guild_id, user_id=seller_id, kind="city_underground_market_income", amount=seller_pay,
            source="black_market", description=description,
            splits={"gross": gross, "tax": tax, "escrow_key": str(escrow_key)},
        )
        self.system_db.save()
        return {"gross": gross, "seller": seller_pay, "tax": tax}

    def city_underground_reward_to_bank(self, guild_id: int, user_id: int, amount: int, description: str) -> int:
        # Mission rewards are paid from Treasury, never minted.
        sys = self._system(guild_id)
        grant = min(max(0, int(amount)), max(0, int(sys.get("treasury", 0) or 0)))
        if grant <= 0:
            return 0
        sys["treasury"] -= grant
        self._set_bank_balance(guild_id, user_id, self.get_bank_balance(guild_id, user_id) + grant)
        sys["total_city_underground"] = int(sys.get("total_city_underground", 0) or 0) + grant
        self._record_transaction(
            guild_id, user_id=user_id, kind="city_underground_mission", amount=grant,
            source="underground_contract", description=description, splits={"treasury": -grant},
        )
        self.system_db.save()
        return grant

    def city_underground_heist_payout(
        self, guild_id: int, crew_id: str, member_ids: list[int], amount: int,
        *, crew_share_bps: int = 2500, description: str = "Virtual bank operation"
    ) -> dict:
        sys = self._system(guild_id)
        available = max(0, int(sys.get("treasury", 0) or 0))
        gross = min(max(0, int(amount)), available)
        ids = [int(x) for x in dict.fromkeys(member_ids) if int(x) > 0]
        if gross <= 0 or not ids:
            return {"gross": 0, "crew": 0, "members": {}, "treasury_left": available}
        crew_share_bps = max(0, min(8000, int(crew_share_bps)))
        crew_take = gross * crew_share_bps // 10000
        people_pool = gross - crew_take
        each = people_pool // len(ids)
        remainder = people_pool - each * len(ids)
        paid = {}
        for i, uid in enumerate(ids):
            share = each + (remainder if i == 0 else 0)
            if share:
                self._set_bank_balance(guild_id, uid, self.get_bank_balance(guild_id, uid) + share)
            paid[uid] = share
            self._record_transaction(
                guild_id, user_id=uid, kind="city_underground_heist_share", amount=share,
                source="virtual_bank_operation", description=description,
                splits={"crew_id": str(crew_id), "gross": gross},
            )
        crew = self.city_crew_account(guild_id, crew_id)
        crew["balance"] = int(crew.get("balance", 0) or 0) + crew_take
        crew["heist_income"] = int(crew.get("heist_income", 0) or 0) + crew_take
        sys["treasury"] = available - gross
        sys["total_city_underground"] = int(sys.get("total_city_underground", 0) or 0) + gross
        self.system_db.save()
        return {"gross": gross, "crew": crew_take, "members": paid, "treasury_left": sys["treasury"]}

    def city_seed_business_payroll(self, guild_id: int, business_ids: list) -> dict:
        sys = self._system(guild_id)
        if sys.get("city_seed_done"):
            return {"seeded": 0, "businesses": 0, "already_done": True}
        treasury = max(0, int(sys.get("treasury", 0) or 0))
        cap = min(
            int(getattr(cfg, "CITY_INITIAL_PAYROLL_SEED_CAP", 50000) or 50000),
            treasury * int(getattr(cfg, "CITY_INITIAL_PAYROLL_SEED_BPS", 800) or 800) // 10000,
        )
        ids = [str(x) for x in dict.fromkeys(business_ids) if x]
        if not ids or cap <= 0:
            sys["city_seed_done"] = True
            self.system_db.save()
            return {"seeded": 0, "businesses": len(ids), "already_done": False}
        each = cap // len(ids)
        used = 0
        for bid in ids:
            if each <= 0: break
            acc = self.city_business_account(guild_id, bid)
            acc["payroll"] = int(acc.get("payroll", 0) or 0) + each
            used += each
        sys["treasury"] = max(0, treasury - used)
        sys["city_seed_done"] = True
        self.system_db.save()
        return {"seeded": used, "businesses": len(ids), "already_done": False}

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
        career_bonus = 0
        career = self.bot.get_cog("CareerCity")
        if career and hasattr(career, "get_bank_interest_bonus_bps"):
            try:
                career_bonus = int(career.get_bank_interest_bonus_bps(guild_id, user_id) or 0)
            except Exception:
                career_bonus = 0
        return max(0, base + level_bonus + boost + career_bonus)

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
            return False, "❌ هاد الممتلك ماشي عندك."
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
        level_discount = int(perks.get("shop_discount_percent", 0) or 0)
        career_discount = 0
        career = self.bot.get_cog("CareerCity")
        if career and hasattr(career, "get_shop_discount_percent"):
            try:
                career_discount = int(career.get_shop_discount_percent(guild_id, user_id) or 0)
            except Exception:
                career_discount = 0
        return max(0, min(50, level_discount + career_discount))

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
            f"💳 المحفظة: **{cfg.fmt_money(self.get_balance(guild.id, user.id))}**"
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
            f"💳 المحفظة: **{cfg.fmt_money(self.get_balance(guild.id, user.id))}**"
        )

    def build_bank_panel_embed(self, guild: discord.Guild, lang: str = "darija") -> discord.Embed:
        lang = lang if lang in {"darija","en","fr"} else "darija"
        sys = self._system(guild.id)

        if lang == "en":
            title = "🏦 GGMW9 Central Bank"
            desc = (
                "**The official server bank:** Wallet, Savings, Transfers, Loans, Credit and Assets.\n\n"
                "💳 **Wallet** — gaming and purchases.\n"
                "🏦 **Savings** — protected from casino bets and earns Treasury-funded daily interest.\n"
                "💸 **Transfers** — Bank→Bank with a ledger and transparent fee.\n"
                "💳 **Loans** — funded by Treasury; Credit + Level determine the terms.\n"
                "🏠 **Assets** — property counted in Net Worth and resellable.\n\n"
                "📍 **This #bank channel is the official full Bank panel. ARCADE is only quick access.**"
            )
            names = ("🏛️ Treasury","🎰 Global Jackpot","🎉 Events Fund","📈 Savings Rate","💸 Transfers","💵 USD System","🌐 Languages","💱 Display Currency")
            rv = f"Base **{getattr(cfg,'BANK_INTEREST_BASE_BPS_DAILY',5)/100:.2f}%/day**\nMinimum **{cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}**\nLevel and Shop pass may increase it."
            tv = f"Base fee **{getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%**\nDaily limit starts at **{cfg.fmt_money(getattr(cfg,'BANK_TRANSFER_DAILY_LIMIT',100000))}**"
            dv = "Balances are stored in cents and displayed as USD. No hidden reset is performed."
            lv = "🇲🇦 Darija • 🇬🇧 English • 🇫🇷 Français"
            cv = "The real account is always **USD**. Each member can display an approximate **MAD / EUR / DZD** equivalent."
            footer = "GGMW9 Bank • real ledger • Treasury-funded yield • FX display: USD/MAD/EUR/DZD"
        elif lang == "fr":
            title = "🏦 Banque centrale GGMW9"
            desc = (
                "**La banque officielle du serveur :** Portefeuille, Épargne, Transferts, Prêts, Crédit et Actifs.\n\n"
                "💳 **Portefeuille** — jeux et achats.\n"
                "🏦 **Épargne** — protégée des paris et rémunérée par le Trésor.\n"
                "💸 **Transferts** — Banque→Banque avec registre et frais transparents.\n"
                "💳 **Prêts** — financés par le Trésor ; Crédit + Niveau définissent les conditions.\n"
                "🏠 **Actifs** — biens inclus dans la valeur nette et revendables.\n\n"
                "📍 **Le salon #bank est le panneau bancaire officiel complet. ARCADE sert seulement d'accès rapide.**"
            )
            names = ("🏛️ Trésor","🎰 Jackpot global","🎉 Fonds événements","📈 Taux d'épargne","💸 Transferts","💵 Système USD","🌐 Langues","💱 Devise d'affichage")
            rv = f"Base **{getattr(cfg,'BANK_INTEREST_BASE_BPS_DAILY',5)/100:.2f}%/jour**\nMinimum **{cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}**\nLe niveau et le pass Boutique peuvent l'augmenter."
            tv = f"Frais de base **{getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%**\nLimite quotidienne dès **{cfg.fmt_money(getattr(cfg,'BANK_TRANSFER_DAILY_LIMIT',100000))}**"
            dv = "Les soldes sont stockés en cents et affichés en USD. Aucun reset caché."
            lv = "🇲🇦 Darija • 🇬🇧 English • 🇫🇷 Français"
            cv = "Le compte réel reste toujours en **USD**. Chaque membre peut afficher une estimation en **MAD / EUR / DZD**."
            footer = "Banque GGMW9 • registre réel • rendement financé par le Trésor • affichage USD/MAD/EUR/DZD"
        else:
            title = "🏦 البنك المركزي ديال GGMW9"
            desc = (
                "**هاد هو البنك الرسمي ديال السيرفر:** المحفظة، الادخار، التحويلات، القروض، التقييم الائتماني والممتلكات.\n\n"
                "💳 **المحفظة** — منها كتخلص فاللعب والشراء.\n"
                "🏦 **الادخار** — محمي من الرهانات وكيجيب ربح يومي ممول من الخزينة.\n"
                "💸 **التحويلات** — من بنك لبنك، وكل عملية كتتسجل والرسوم واضحة.\n"
                "💳 **القروض** — ممولة من الخزينة؛ المستوى والتقييم الائتماني كيحددو الشروط.\n"
                "🏠 **الممتلكات** — كيدخلو فصافي الثروة وتقدر تعاود تبيعهم.\n\n"
                "📍 **هاد #bank هو البانل الرسمي والكامل ديال البنك؛ ARCADE غير وصول سريع.**"
            )
            names = ("🏛️ الخزينة","🎰 الجائزة الكبرى","🎉 صندوق الفعاليات","📈 نسبة أرباح الادخار","💸 التحويلات","💵 نظام الدولار","🌐 اللغات","💱 عملة العرض")
            rv = f"النسبة الأساسية **{getattr(cfg,'BANK_INTEREST_BASE_BPS_DAILY',5)/100:.2f}% فالنهار**\nأقل رصيد مؤهل **{cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}**\nالمستوى وامتياز المتجر يقدرو يطلعو النسبة."
            tv = f"الرسوم الأساسية **{getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%**\nالحد اليومي كيبدا من **{cfg.fmt_money(getattr(cfg,'BANK_TRANSFER_DAILY_LIMIT',100000))}**"
            dv = "الأرصدة كتتحفظ بالسنت وكتتحسب بالدولار. ماكاين حتى تصفير مخفي."
            lv = "🇲🇦 الدارجة • 🇬🇧 الإنجليزية • 🇫🇷 الفرنسية"
            cv = "الحساب الحقيقي ديما **USD**. من الحساب ديالو، كل عضو يقدر يشوف تقريباً القيمة بـ **MAD / EUR / DZD** بلا ما يتبدل الرصيد الحقيقي."
            footer = "بنك GGMW9 • سجل معاملات حقيقي • أرباح الادخار من الخزينة • عرض USD/MAD/EUR/DZD"

        embed = discord.Embed(title=title, description=desc, color=discord.Color.gold(), timestamp=datetime.now())
        embed.add_field(name=names[0], value=f"**{cfg.fmt_money(sys['treasury'])}**", inline=True)
        embed.add_field(name=names[1], value=f"**{cfg.fmt_money(sys['jackpot'])}**", inline=True)
        embed.add_field(name=names[2], value=f"**{cfg.fmt_money(sys['events'])}**", inline=True)
        embed.add_field(name=names[3], value=rv, inline=True)
        embed.add_field(name=names[4], value=tv, inline=True)
        embed.add_field(name=names[5], value=dv, inline=False)
        embed.add_field(name=names[6], value=lv, inline=False)
        embed.add_field(name=names[7], value=cv, inline=False)
        embed.set_footer(text=footer)
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
        city_escrow = self.city_escrow_total(guild.id)
        city_business = self.city_business_totals(guild.id)
        city_crew_total = self.city_crew_total(guild.id)
        city_business_total = city_business["operating"] + city_business["payroll"] + city_business["profit"] + city_crew_total
        live_supply = wallets + bank_total + sys["treasury"] + sys["jackpot"] + sys["events"] + city_escrow + city_business_total
        if lang == "en":
            title, desc = "📊 GGMW9 Economy — Live", "Live USD economy: Wallet + Bank + Treasury + Casino + Shop + Assets."
            names = ["💳 Wallets","🏦 Bank Deposits","🏛️ Treasury","🎰 Jackpot","🎉 Events","🔥 Burned","🏠 Asset Book Value","💳 Loans Outstanding","⚠️ Overdue Loans","💵 Live Money Supply"]
        elif lang == "fr":
            title, desc = "📊 Économie GGMW9 — Live", "Économie USD en direct : Portefeuilles + Banque + Trésor + Casino + Boutique + Actifs."
            names = ["💳 Portefeuilles","🏦 Dépôts bancaires","🏛️ Trésor","🎰 Jackpot","🎉 Événements","🔥 Détruit","🏠 Valeur des actifs","💳 Prêts en cours","⚠️ Prêts en retard","💵 Masse monétaire"]
        else:
            title, desc = "📊 اقتصاد GGMW9 — مباشر", "نظرة مباشرة على الدولار داخل السيرفر: المحافظ + البنك + الخزينة + الرهانات + المتجر + الممتلكات."
            names = ["💳 المحافظ","🏦 ودائع البنك","🏛️ الخزينة","🎰 الجائزة الكبرى","🎉 صندوق الفعاليات","🔥 الأموال المحروقة","🏠 قيمة الممتلكات","💳 القروض المتبقية","⚠️ القروض المتأخرة","💵 الأموال المتداولة"]
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
            loss_name, win_name = "🎰 خسائر الرهانات المسجلة", "🎉 أرباح الرهانات الصافية المسجلة"
        embed.add_field(name=loss_name,value=f"**{cfg.fmt_money(int(sys.get('total_gambling_lost',0) or 0))}**",inline=True)
        embed.add_field(name=win_name,value=f"**{cfg.fmt_money(int(sys.get('total_gambling_won',0) or 0))}**",inline=True)
        if lang == "en":
            city_escrow_name, city_business_name = "🏙️ CITY Escrow", "🏢 CITY Business Funds"
        elif lang == "fr":
            city_escrow_name, city_business_name = "🏙️ Séquestre CITY", "🏢 Fonds des entreprises CITY"
        else:
            city_escrow_name, city_business_name = "🏙️ الأموال المحجوزة فالمدينة", "🏢 أموال شركات المدينة"
        embed.add_field(name=city_escrow_name,value=f"**{cfg.fmt_money(city_escrow)}**",inline=True)
        embed.add_field(name=city_business_name,value=f"**{cfg.fmt_money(city_business_total)}**",inline=True)
        embed.set_footer(text=("🌐 الدارجة • الإنجليزية • الفرنسية" if lang=="darija" else "🌐 Darija • English • Français"))
        return embed

    def build_user_account_embed(self, guild: discord.Guild, user: discord.abc.User, lang: str = "darija") -> discord.Embed:
        lang = lang if lang in {"darija","en","fr"} else "darija"
        wallet = self.get_balance(guild.id, user.id)
        bank = self.get_bank_balance(guild.id, user.id)
        assets_value = self.get_assets_value(guild.id, user.id)
        terms = self.get_loan_terms(guild.id, user.id)
        net_worth = wallet + bank + assets_value
        rate_bps = self.get_bank_interest_bps(guild.id, user.id)
        sent_today = self.get_transfer_sent_today(guild.id, user.id)
        transfer_limit = self.get_transfer_daily_limit(guild.id, user.id)
        fee_free = self._perk_active(guild.id, user.id, "transfer_fee_pass_expires")

        if lang == "en":
            title = f"🏦 {user.display_name}'s Account"
            labels = {
                "net":"Net Worth","wallet":"Wallet","savings":"Savings","assets":"Assets",
                "yield":"Savings Yield","transfers":"Transfers Today","credit":"Credit Score",
                "loan_terms":"Loan Terms","remaining":"Remaining","due":"Due",
                "active":"Active","overdue":"Overdue",
            }
            yield_v = (
                f"**{rate_bps/100:.2f}% / day**\n"
                f"Minimum: {cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}\n"
                "Paid from Treasury"
            )
            trans_v = (
                f"{cfg.fmt_money(sent_today)} / {cfg.fmt_money(transfer_limit)}\n"
                + ("✅ Fee Pass active" if fee_free else f"Fee {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")
            )
            terms_v = (
                f"Limit: **{cfg.fmt_money(terms['effective_limit'])}**\n"
                f"Interest: **{terms['interest_percent']}%** • Term: **{terms['term_days']} days**"
            )
            footer = "Savings stay outside Casino until withdrawn • Assets can be sold from Bank"
        elif lang == "fr":
            title = f"🏦 Compte de {user.display_name}"
            labels = {
                "net":"Valeur nette","wallet":"Portefeuille","savings":"Épargne","assets":"Actifs",
                "yield":"Rendement de l’épargne","transfers":"Transferts aujourd’hui","credit":"Score de crédit",
                "loan_terms":"Conditions du prêt","remaining":"Restant","due":"Échéance",
                "active":"Actif","overdue":"En retard",
            }
            yield_v = (
                f"**{rate_bps/100:.2f}% / jour**\n"
                f"Minimum : {cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}\n"
                "Payé par le Trésor"
            )
            trans_v = (
                f"{cfg.fmt_money(sent_today)} / {cfg.fmt_money(transfer_limit)}\n"
                + ("✅ Pass sans frais actif" if fee_free else f"Frais {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")
            )
            terms_v = (
                f"Limite : **{cfg.fmt_money(terms['effective_limit'])}**\n"
                f"Intérêt : **{terms['interest_percent']}%** • Durée : **{terms['term_days']} jours**"
            )
            footer = "L’épargne reste hors Casino jusqu’au retrait • Les actifs peuvent être revendus depuis la Banque"
        else:
            title = f"🏦 حساب {user.display_name}"
            labels = {
                "net":"صافي الثروة","wallet":"المحفظة","savings":"الادخار","assets":"الممتلكات",
                "yield":"أرباح الادخار","transfers":"تحويلات اليوم","credit":"التقييم الائتماني",
                "loan_terms":"شروط القرض","remaining":"الباقي","due":"آخر أجل",
                "active":"خدام","overdue":"متأخر",
            }
            yield_v = (
                f"**{rate_bps/100:.2f}% فالنهار**\n"
                f"أقل رصيد مؤهل: {cfg.fmt_money(getattr(cfg,'BANK_INTEREST_MIN_BALANCE',2500))}\n"
                "الأرباح كتخلص من الخزينة"
            )
            trans_v = (
                f"{cfg.fmt_money(sent_today)} / {cfg.fmt_money(transfer_limit)}\n"
                + ("✅ الإعفاء من الرسوم خدام" if fee_free else f"الرسوم {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")
            )
            terms_v = (
                f"الحد: **{cfg.fmt_money(terms['effective_limit'])}**\n"
                f"الفائدة: **{terms['interest_percent']}%** • المدة: **{terms['term_days']} أيام**"
            )
            footer = "فلوس الادخار ماكيدخلوش للرهانات حتى تسحبهم • الممتلكات تقدر تبيعهم من البنك"

        display_code = self.get_display_currency(guild.id, user.id)
        embed = discord.Embed(
            title=title,
            description=f"**{labels['net']}:**\n{self.money_with_preference(guild.id,user.id,net_worth)}",
            color=discord.Color.green(),
        )
        embed.add_field(name=f"💳 {labels['wallet']}", value=f"**{self.money_with_preference(guild.id,user.id,wallet)}**", inline=True)
        embed.add_field(name=f"🏦 {labels['savings']}", value=f"**{self.money_with_preference(guild.id,user.id,bank)}**", inline=True)
        embed.add_field(name=f"🏠 {labels['assets']}", value=f"**{self.money_with_preference(guild.id,user.id,assets_value)}**", inline=True)
        embed.add_field(name=f"📈 {labels['yield']}", value=yield_v, inline=True)
        embed.add_field(name=f"💸 {labels['transfers']}", value=trans_v, inline=True)
        embed.add_field(
            name=f"💳 {labels['credit']}",
            value=f"**{terms['credit_score']}/100** • {terms['tier_name']} • Lv {terms['level']}",
            inline=True,
        )
        embed.add_field(name=f"🏦 {labels['loan_terms']}", value=terms_v, inline=False)

        loan = self.get_active_loan(guild.id,user.id)
        if loan:
            overdue = self._loan_is_overdue(loan)
            state = labels["overdue"] if overdue else labels["active"]
            loan_name = (
                f"💳 Loan #{loan.get('id')} — {state}" if lang=="en" else
                f"💳 Prêt #{loan.get('id')} — {state}" if lang=="fr" else
                f"💳 القرض رقم #{loan.get('id')} — {state}"
            )
            embed.add_field(
                name=loan_name,
                value=(
                    f"{labels['remaining']}: **{cfg.fmt_money(int(loan.get('remaining',0)))}**\n"
                    f"{labels['due']}: <t:{self._loan_due_unix(loan)}:F> (<t:{self._loan_due_unix(loan)}:R>)"
                ),
                inline=False,
            )

        fx_date = self.fx_db.data.get("date")
        if display_code != "USD":
            if lang == "en":
                fx_note = f" • Display: {display_code} ≈ reference FX" + (f" ({fx_date})" if fx_date else "")
            elif lang == "fr":
                fx_note = f" • Affichage : {display_code} ≈ taux de référence" + (f" ({fx_date})" if fx_date else "")
            else:
                fx_note = f" • العرض: {display_code} ≈ سعر صرف مرجعي" + (f" ({fx_date})" if fx_date else "")
        else:
            fx_note = ""

        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=footer + fx_note)
        return embed

    def build_xp_bank_perks_embed(self, guild: discord.Guild, user: discord.abc.User, lang: str = "darija") -> discord.Embed:
        lang=lang if lang in {"darija","en","fr"} else "darija"
        terms=self.get_loan_terms(guild.id,user.id)
        next_tier=self.get_next_xp_loan_tier(guild.id,user.id)
        rate=self.get_bank_interest_bps(guild.id,user.id)/100
        tlimit=cfg.fmt_money(self.get_transfer_daily_limit(guild.id,user.id))
        if lang=="en":
            title=f"⭐ Bank Privileges — {user.display_name}"
            desc="Level increases loan capacity, Savings rate and transfer limit; Credit measures repayment reliability."
            now_name,loan_name,next_name="📊 Current","💰 Loan","🚀 Next Tier"
            now=f"⭐ Level **{terms['level']}** — {terms['tier_name']}\n💳 Credit **{terms['credit_score']}/100**\n📈 Savings **{rate:.2f}%/day**\n💸 Transfer limit **{tlimit}/day**"
            loan=f"Base: **{cfg.fmt_money(terms['base_limit'])}**\nAfter Credit: **{cfg.fmt_money(terms['credit_adjusted_limit'])}**\nLiquidity Cap: **{cfg.fmt_money(terms['liquidity_cap'])}**\n✅ Effective: **{cfg.fmt_money(terms['effective_limit'])}**\nInterest **{terms['interest_percent']}%** • **{terms['term_days']} days**"
        elif lang=="fr":
            title=f"⭐ Avantages bancaires — {user.display_name}"
            desc="Le niveau augmente la capacité de prêt, le taux d'épargne et la limite de transfert ; le Crédit mesure la fiabilité des remboursements."
            now_name,loan_name,next_name="📊 Actuel","💰 Prêt","🚀 Niveau suivant"
            now=f"⭐ Niveau **{terms['level']}** — {terms['tier_name']}\n💳 Crédit **{terms['credit_score']}/100**\n📈 Épargne **{rate:.2f}%/jour**\n💸 Limite de transfert **{tlimit}/jour**"
            loan=f"Base : **{cfg.fmt_money(terms['base_limit'])}**\nAprès crédit : **{cfg.fmt_money(terms['credit_adjusted_limit'])}**\nPlafond de liquidité : **{cfg.fmt_money(terms['liquidity_cap'])}**\n✅ Disponible : **{cfg.fmt_money(terms['effective_limit'])}**\nIntérêt **{terms['interest_percent']}%** • **{terms['term_days']} jours**"
        else:
            title=f"⭐ امتيازات البنك — {user.display_name}"
            desc="المستوى كيرفع سقف القرض ونسبة أرباح الادخار وحد التحويلات؛ والتقييم الائتماني كيقيس الالتزام فالتسديد."
            now_name,loan_name,next_name="📊 وضعك دابا","💰 القرض","🚀 المستوى البنكي الجاي"
            now=f"⭐ المستوى **{terms['level']}** — {terms['tier_name']}\n💳 التقييم الائتماني **{terms['credit_score']}/100**\n📈 أرباح الادخار **{rate:.2f}% فالنهار**\n💸 حد التحويل **{tlimit} فالنهار**"
            loan=f"السقف الأساسي: **{cfg.fmt_money(terms['base_limit'])}**\nبعد التقييم الائتماني: **{cfg.fmt_money(terms['credit_adjusted_limit'])}**\nسقف السيولة: **{cfg.fmt_money(terms['liquidity_cap'])}**\n✅ المتاح فعلياً: **{cfg.fmt_money(terms['effective_limit'])}**\nالفائدة **{terms['interest_percent']}%** • المدة **{terms['term_days']} أيام**"
        embed=discord.Embed(title=title,description=desc,color=discord.Color.gold())
        embed.add_field(name=now_name,value=now,inline=False)
        embed.add_field(name=loan_name,value=loan,inline=False)
        if next_tier:
            if lang=="en":
                nxt=f"Level **{int(next_tier.get('min_level',0))}** — {next_tier.get('name','Tier')}\nBase Loan **{cfg.fmt_money(int(next_tier.get('base_limit',0)))}** • {int(next_tier.get('interest',0))}% • {int(next_tier.get('term_days',0))} days"
            elif lang=="fr":
                nxt=f"Niveau **{int(next_tier.get('min_level',0))}** — {next_tier.get('name','Niveau')}\nPrêt de base **{cfg.fmt_money(int(next_tier.get('base_limit',0)))}** • {int(next_tier.get('interest',0))}% • {int(next_tier.get('term_days',0))} jours"
            else:
                nxt=f"المستوى **{int(next_tier.get('min_level',0))}** — {next_tier.get('name','المرحلة الجاية')}\nسقف القرض الأساسي **{cfg.fmt_money(int(next_tier.get('base_limit',0)))}** • فائدة {int(next_tier.get('interest',0))}% • مدة {int(next_tier.get('term_days',0))} أيام"
            embed.add_field(name=next_name,value=nxt,inline=False)
        embed.set_thumbnail(url=user.display_avatar.url)
        return embed

    def build_user_transactions_embed(self, guild: discord.Guild, user: discord.abc.User, lang: str = "darija") -> discord.Embed:
        lang=lang if lang in {"darija","en","fr"} else "darija"
        txs=self.get_user_transactions(guild.id,user.id,limit=12)
        if not txs:
            title="🧾 Recent Transactions" if lang=="en" else "🧾 Transactions récentes" if lang=="fr" else "🧾 آخر المعاملات"
            empty="📭 No transactions recorded yet." if lang=="en" else "📭 Aucune transaction enregistrée." if lang=="fr" else "📭 ماكايناش معاملات مسجلة."
            return discord.Embed(title=title,description=empty,color=discord.Color.blurple())
        kind_icons={"gambling_loss":"🎰","gambling_win":"🎉","shop_purchase":"🛒","jackpot_payout":"🏆","bank_deposit":"🏦","bank_withdraw":"💸","bank_transfer_out":"📤","bank_transfer_in":"📥","bank_interest":"📈","asset_sale":"🏠","loan_issued":"💳","loan_repayment":"💸","loan_paid":"✅","level_daily_bonus":"⭐","admin_adjustment":"🛡️"}
        names_dz={"gambling_loss":"خسارة فالرهانات","gambling_win":"ربح فالرهانات","shop_purchase":"شراء من المتجر","jackpot_payout":"الجائزة الكبرى","bank_deposit":"إيداع فالبنك","bank_withdraw":"سحب من البنك","bank_transfer_out":"تحويل خارج","bank_transfer_in":"تحويل داخل","bank_interest":"أرباح الادخار","asset_sale":"بيع ممتلكات","loan_issued":"قرض جديد","loan_repayment":"تسديد القرض","loan_paid":"القرض تسد كامل","level_daily_bonus":"مكافأة المستوى","admin_adjustment":"تعديل من الإدارة"}
        names_en={"gambling_loss":"Casino loss","gambling_win":"Casino win","shop_purchase":"Shop purchase","jackpot_payout":"Jackpot payout","bank_deposit":"Bank deposit","bank_withdraw":"Bank withdrawal","bank_transfer_out":"Transfer sent","bank_transfer_in":"Transfer received","bank_interest":"Savings interest","asset_sale":"Asset sale","loan_issued":"Loan issued","loan_repayment":"Loan repayment","loan_paid":"Loan paid","level_daily_bonus":"Level bonus","admin_adjustment":"Admin adjustment"}
        names_fr={"gambling_loss":"Perte Casino","gambling_win":"Gain Casino","shop_purchase":"Achat boutique","jackpot_payout":"Jackpot","bank_deposit":"Dépôt bancaire","bank_withdraw":"Retrait bancaire","bank_transfer_out":"Transfert envoyé","bank_transfer_in":"Transfert reçu","bank_interest":"Intérêt épargne","asset_sale":"Vente d'actif","loan_issued":"Prêt accordé","loan_repayment":"Remboursement","loan_paid":"Prêt remboursé","level_daily_bonus":"Bonus de niveau","admin_adjustment":"Ajustement admin"}
        lines=[]
        for tx in txs:
            kind=tx.get("kind")
            icon=kind_icons.get(kind,"💱")
            try: unix=int(datetime.fromisoformat(tx.get("ts","")).timestamp()); when=f"<t:{unix}:R>"
            except Exception: when="—"
            label=(names_en if lang=="en" else names_fr if lang=="fr" else names_dz).get(kind, "معاملة" if lang=="darija" else tx.get("source","Transaction"))
            lines.append(f"{icon} **#{tx.get('id')}** • {label} • **{cfg.fmt_money(int(tx.get('amount',0)))}** • {when}")
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
                        and (old.embeds[0].title or "") in {"📊 اقتصاد GGMW9 — Live","📊 اقتصاد GGMW9 — مباشر"}
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
            await self.repair_guild_shop_roles(guild)

    # ════════════════════════════════════════════════
    # Shop Role Health / Repair
    # ════════════════════════════════════════════════

    @staticmethod
    def _parse_shop_expiry(value):
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _shop_purchase_active(entry: dict) -> bool:
        expires = Economy._parse_shop_expiry(entry.get("expires"))
        return expires is None or expires > datetime.now(timezone.utc)

    def _find_active_purchase(self, guild_id: int, user_id: int, *, effect_key: str = None, item_ids=None):
        item_ids = set(item_ids or [])
        for p in self._acc(guild_id, user_id).get("purchases", []) or []:
            if effect_key and p.get("effect_key") == effect_key and self._shop_purchase_active(p):
                return p
            if item_ids and p.get("item_id") in item_ids and self._shop_purchase_active(p):
                return p
        return None

    @staticmethod
    def _is_protected_staff_role(role: discord.Role) -> bool:
        if role.is_default() or role.managed:
            return False
        perms = role.permissions
        permission_names = getattr(
            cfg,
            "SHOP_ROLE_STAFF_PERMISSION_NAMES",
            (
                "administrator","manage_guild","manage_roles",
                "kick_members","ban_members","moderate_members","manage_messages",
            ),
        )
        if any(bool(getattr(perms, name, False)) for name in permission_names):
            return True
        normalized = re.sub(r"[^a-zA-Z\u0600-\u06FF]+", " ", role.name).strip().lower()
        return normalized in {
            "owner","server owner","admin","administrator","moderator","mod","staff","management",
            "المالك","مالك","الإدارة","ادارة","أدمن","ادمن","مود","موديراتور","مشرف","المشرفين",
        }

    def _staff_color_state(self, guild_id: int) -> dict:
        return self._system(guild_id).setdefault("staff_color_passthrough", {})

    def _active_personal_color_role_id(self, guild_id: int, user_id: int) -> int:
        purchase = self._find_active_purchase(
            guild_id,
            user_id,
            effect_key="personal_color",
            item_ids={"color_basic", "color_month", "permanent_color"},
        )
        return int(purchase.get("role_id") or 0) if purchase else 0

    async def _ensure_staff_color_passthrough(self, guild: discord.Guild) -> list:
        """Preserve staff grouping/permissions while allowing personal colors.

        Staff/Admin/Moderator roles stay ABOVE Shop colors and keep their hoist.
        If a protected staff role has a real color, we:
          1) remember that color,
          2) create a no-permission, non-hoisted fallback role with that color,
          3) make the staff role itself colorless,
          4) assign fallback to staff members.

        A purchased Personal Color sits above the fallback, so it wins visually.
        Without a purchase, the fallback preserves the staff's old color.
        """
        notes = []
        me = guild.me or (guild.get_member(self.bot.user.id) if self.bot.user else None)
        if not me or not me.guild_permissions.manage_roles:
            return ["⚠️ البوت خاصو Manage Roles باش يدير Staff Color Passthrough."]

        state = self._staff_color_state(guild.id)
        changed_state = False

        protected = [
            r for r in guild.roles
            if r.id != me.top_role.id
            and not r.managed
            and self._is_protected_staff_role(r)
            and r < me.top_role
        ]
        protected_ids = {r.id for r in protected}

        for role in protected:
            key = str(role.id)
            entry = state.get(key) or {}
            original_color = int(entry.get("original_color") or 0)
            fallback_role = guild.get_role(int(entry.get("fallback_role_id") or 0)) if entry.get("fallback_role_id") else None

            # First migration: capture the current staff color before neutralizing it.
            if not entry:
                original_color = int(role.colour.value or 0)
                entry = {
                    "original_color": original_color,
                    "fallback_role_id": None,
                    "staff_role_name": role.name,
                }
                state[key] = entry
                changed_state = True

            # If an admin manually changes the staff role color later, treat it as
            # the new base/fallback color and neutralize the staff role again.
            current_staff_color = int(role.colour.value or 0)
            if current_staff_color != 0:
                original_color = current_staff_color
                entry["original_color"] = original_color
                changed_state = True

            # No fallback is necessary for a role that has always been colorless.
            # It still remains a valid hoisted staff grouping role.
            if original_color == 0 and fallback_role is None:
                if current_staff_color != 0:
                    try:
                        await role.edit(
                            colour=discord.Colour.default(),
                            reason="GGMW9 Shop — staff color passthrough",
                        )
                    except Exception as exc:
                        notes.append(f"⚠️ {role.name}: {exc}")
                continue

            # Create/recreate the fallback role.
            if fallback_role is None:
                try:
                    fallback_role = await guild.create_role(
                        name=f"🎨 Staff Base • {role.name}"[:100],
                        colour=discord.Colour(original_color),
                        permissions=discord.Permissions.none(),
                        hoist=False,
                        mentionable=False,
                        reason="GGMW9 Shop — preserve staff base color",
                    )
                    entry["fallback_role_id"] = fallback_role.id
                    changed_state = True
                except (discord.Forbidden, discord.HTTPException) as exc:
                    notes.append(f"⚠️ ماقدرتش نصاوب fallback ديال {role.name}: {exc}")
                    continue
            else:
                # Keep fallback visual-only and synced to the remembered base color.
                try:
                    if (
                        int(fallback_role.colour.value or 0) != original_color
                        or fallback_role.hoist
                        or fallback_role.permissions.value != 0
                    ):
                        await fallback_role.edit(
                            colour=discord.Colour(original_color),
                            permissions=discord.Permissions.none(),
                            hoist=False,
                            mentionable=False,
                            reason="GGMW9 Shop — sync staff base color",
                        )
                except (discord.Forbidden, discord.HTTPException) as exc:
                    notes.append(f"⚠️ ماقدرتش نحدّث fallback ديال {role.name}: {exc}")

            # Staff role remains the real authority/grouping role, but with no color.
            if int(role.colour.value or 0) != 0:
                try:
                    await role.edit(
                        colour=discord.Colour.default(),
                        reason="GGMW9 Shop — personal colors without changing staff group",
                    )
                except (discord.Forbidden, discord.HTTPException) as exc:
                    notes.append(f"⚠️ ماقدرتش نخلي {role.name} بلا لون: {exc}")
                    continue

            # Sync fallback membership to the actual staff-role membership.
            # Purchased personal color is higher than fallback, so it overrides.
            if fallback_role:
                for member in role.members:
                    if fallback_role not in member.roles:
                        try:
                            await member.add_roles(
                                fallback_role,
                                reason="GGMW9 Shop — staff base color fallback",
                            )
                        except (discord.Forbidden, discord.HTTPException):
                            pass

                # Remove fallback from members who no longer have that staff role.
                for member in list(fallback_role.members):
                    if role not in member.roles:
                        try:
                            await member.remove_roles(
                                fallback_role,
                                reason="GGMW9 Shop — staff role removed",
                            )
                        except (discord.Forbidden, discord.HTTPException):
                            pass

        # Clean stale passthrough entries if a protected staff role was deleted.
        for key in list(state.keys()):
            try:
                rid = int(key)
            except Exception:
                continue
            if rid in protected_ids:
                continue
            entry = state.get(key) or {}
            fallback = guild.get_role(int(entry.get("fallback_role_id") or 0)) if entry.get("fallback_role_id") else None
            if fallback:
                try:
                    await fallback.delete(reason="GGMW9 Shop — stale staff color fallback")
                except (discord.Forbidden, discord.HTTPException):
                    pass
            state.pop(key, None)
            changed_state = True

        if changed_state:
            self.system_db.save()

        return notes

    async def _sync_staff_fallback_for_member(self, member: discord.Member):
        """Lightweight role-change repair for a single member."""
        guild = member.guild
        state = self._staff_color_state(guild.id)
        for role in guild.roles:
            if str(role.id) not in state:
                continue
            entry = state[str(role.id)]
            fallback = guild.get_role(int(entry.get("fallback_role_id") or 0)) if entry.get("fallback_role_id") else None
            if not fallback:
                continue
            has_staff = role in member.roles
            has_fallback = fallback in member.roles
            try:
                if has_staff and not has_fallback:
                    await member.add_roles(fallback, reason="GGMW9 Shop — staff fallback sync")
                elif not has_staff and has_fallback:
                    await member.remove_roles(fallback, reason="GGMW9 Shop — staff fallback sync")
            except (discord.Forbidden, discord.HTTPException):
                pass

    def _shop_role_records(self, guild: discord.Guild):
        item_types = {i.get("id"): i.get("type") for i in getattr(cfg, "SHOP_ITEMS", [])}
        records = {}
        for _, acc in (self.db.guild(guild.id) or {}).items():
            for p in acc.get("purchases", []) or []:
                if not self._shop_purchase_active(p):
                    continue
                rid = int(p.get("role_id") or 0)
                if not rid:
                    continue
                item_type = item_types.get(p.get("item_id"))
                effect_key = str(p.get("effect_key") or "")
                if effect_key == "personal_color" or item_type in {"role_color","role_color_perm"}:
                    priority = 0
                elif item_type == "custom_role" or effect_key.startswith("custom_role:"):
                    priority = 2
                elif item_type in {"legend_tag","title_role"} or effect_key.startswith("shared_role:"):
                    priority = 3
                else:
                    priority = 4
                records[rid] = min(priority, records.get(rid, priority))
        # Staff base-color fallbacks live BELOW personal colors but ABOVE
        # custom/prestige roles. They have no permissions and hoist=False.
        for entry in self._staff_color_state(guild.id).values():
            rid = int(entry.get("fallback_role_id") or 0)
            if rid:
                records[rid] = min(1, records.get(rid, 1))

        return records

    async def sync_shop_role_hierarchy(
        self,
        guild: discord.Guild,
        *,
        extra_role: discord.Role = None,
        extra_priority: int = 3,
    ) -> Tuple[bool, str]:
        """Shop roles = one smart block below staff and above normal roles."""
        me = guild.me or (guild.get_member(self.bot.user.id) if self.bot.user else None)
        if not me:
            return False, "ماقدرتش نحدد رول ديال البوت."
        if not me.guild_permissions.manage_roles:
            return False, "البوت خاصو صلاحية **إدارة الرولات / Manage Roles**."
        if me.top_role.is_default() or me.top_role.position <= 1:
            return False, "رول ديال البوت خاصها تكون فوق الرولات المشتراة."

        records = self._shop_role_records(guild)
        if extra_role is not None:
            records[extra_role.id] = min(extra_priority, records.get(extra_role.id, extra_priority))

        shop_roles = []
        for rid, priority in records.items():
            role = guild.get_role(int(rid))
            if not role or role.managed:
                continue
            if role >= me.top_role:
                return False, f"{role.mention} فوق/نفس مستوى رول البوت."
            shop_roles.append((priority, role))

        if not shop_roles:
            return True, ""

        shop_ids = {r.id for _, r in shop_roles}
        staff_roles = [
            r for r in guild.roles
            if r.id not in shop_ids
            and r.id != me.top_role.id
            and self._is_protected_staff_role(r)
        ]

        target_top = int(me.top_role.position) - 1
        if staff_roles:
            # Always under the lowest protected Admin/Moderator role.
            target_top = min(
                target_top,
                min(int(r.position) for r in staff_roles) - 1,
            )

        if target_top < 1:
            return False, (
                "ماكايناش بلاصة آمنة تحت الإدارة. "
                "طلع رول البوت وRoles ديال Admin/Moderator لفوق."
            )

        # Highest inside Shop block: Personal Color > Staff Base Fallback > Custom/Decoration > Prestige.
        ordered = sorted(shop_roles, key=lambda x: (x[0], x[1].id))
        if len(ordered) > target_top:
            return False, "عدد Shop Roles كبير بزاف مقارنة بالبلاصة المتوفرة."

        desired = [(role, target_top - idx) for idx, (_, role) in enumerate(ordered)]

        try:
            for role, position in reversed(desired):
                current = guild.get_role(role.id) or role
                if int(current.position) != int(position):
                    await current.edit(
                        position=int(position),
                        reason="GGMW9 Shop — smart role hierarchy sync",
                    )
        except discord.Forbidden:
            return False, (
                "Discord منع ترتيب الرولات. تأكد أن البوت عندو **Manage Roles** "
                "وRole ديالو فوق Shop Roles."
            )
        except discord.HTTPException as exc:
            return False, f"Discord رفض ترتيب Shop Roles: {exc}"

        return True, ""

    async def _position_cosmetic_role(self, guild: discord.Guild, role: discord.Role) -> Tuple[bool, str]:
        return await self.sync_shop_role_hierarchy(
            guild,
            extra_role=role,
            extra_priority=0,
        )

    async def _position_shop_role(
        self,
        guild: discord.Guild,
        role: discord.Role,
        *,
        priority: int,
    ) -> Tuple[bool, str]:
        return await self.sync_shop_role_hierarchy(
            guild,
            extra_role=role,
            extra_priority=priority,
        )

    @staticmethod
    def _effective_colored_role(member: discord.Member):
        colored = [r for r in member.roles if not r.is_default() and int(r.colour.value or 0) != 0]
        if not colored:
            return None
        return max(colored, key=lambda r: (r.position, r.id))

    async def repair_member_shop_roles(self, guild: discord.Guild, member: discord.Member) -> list:
        """Self-heal active role purchases for one member.

        Especially important for legacy personal-color purchases made before
        the shop started positioning cosmetic roles automatically.
        """
        notes = []
        purchases = self._acc(guild.id, member.id).get("purchases", []) or []

        # Legacy purchases do not have effect_key yet, so recognize item ids.
        color_ids = {"color_basic", "color_month", "permanent_color"}
        color_entries = [
            p for p in purchases
            if self._shop_purchase_active(p)
            and (p.get("effect_key") == "personal_color" or p.get("item_id") in color_ids)
        ]

        if color_entries:
            # Prefer newest entry / latest role that still exists.
            entry = color_entries[-1]
            role = guild.get_role(int(entry.get("role_id") or 0)) if entry.get("role_id") else None

            # Migration fallback for the old naming scheme.
            if role is None:
                legacy_names = {
                    f"🎨 {member.display_name}",
                    f"🎨 {member.display_name} • {member.id}",
                }
                role = next(
                    (r for r in guild.roles if r.name in legacy_names and r in member.roles),
                    None,
                )
                if role:
                    entry["role_id"] = role.id
                    entry["effect_key"] = "personal_color"
                    entry.setdefault("delete_role_on_expiry", True)
                    self.db.save()

            if role:
                try:
                    unique_name = f"🎨 {member.display_name[:55]} • {member.id}"[:100]
                    if role.name != unique_name:
                        await role.edit(name=unique_name, reason="GGMW9 Shop color migration")
                    ok, reason = await self._position_cosmetic_role(guild, role)
                    if not ok:
                        notes.append(f"⚠️ {reason}")
                    if role not in member.roles:
                        await member.add_roles(role, reason="GGMW9 Shop color repair")
                    fresh = await guild.fetch_member(member.id)
                    effective = self._effective_colored_role(fresh)
                    if effective and effective.id == role.id:
                        notes.append(f"✅ اللون الشخصي خدام: {role.mention}")
                    elif effective:
                        notes.append(
                            f"⚠️ اللون الشخصي موجود ولكن {effective.mention} عندها أولوية أعلى."
                        )
                    else:
                        notes.append(f"⚠️ الرول {role.mention} موجودة ولكن اللون ما بانش.")
                except Exception as exc:
                    notes.append(f"⚠️ إصلاح اللون فشل: {type(exc).__name__}: {exc}")
            else:
                notes.append("⚠️ شراء اللون مسجل ولكن Role ديالو ما بقاتش موجودة.")

        return notes

    async def repair_guild_shop_roles(self, guild: discord.Guild):
        """Repair Shop colors + staff passthrough + purchased-role hierarchy."""
        await self._ensure_staff_color_passthrough(guild)
        guild_data = self.db.guild(guild.id)
        for uid, acc in list(guild_data.items()):
            purchases = acc.get("purchases", []) or []
            if not any(
                self._shop_purchase_active(p)
                and (
                    p.get("effect_key") == "personal_color"
                    or p.get("item_id") in {"color_basic","color_month","permanent_color"}
                )
                for p in purchases
            ):
                continue
            try:
                member = guild.get_member(int(uid)) or await guild.fetch_member(int(uid))
            except Exception:
                continue
            await self.repair_member_shop_roles(guild, member)

        await self.sync_shop_role_hierarchy(guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.guild.id != after.guild.id:
            return
        before_ids = {r.id for r in before.roles}
        after_ids = {r.id for r in after.roles}
        if before_ids == after_ids:
            return

        watched = {int(k) for k in self._staff_color_state(after.guild.id).keys() if str(k).isdigit()}
        if watched.intersection(before_ids.symmetric_difference(after_ids)):
            await self._sync_staff_fallback_for_member(after)

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

    def build_richest_embed(self, guild: discord.Guild, lang: str = "darija") -> discord.Embed:
        lang = lang if lang in {"darija","en","fr"} else "darija"
        guild_data=self.db.guild(guild.id)
        ranked=[]
        for uid,data in guild_data.items():
            member=guild.get_member(int(uid)) if str(uid).isdigit() else None
            if not member:
                continue
            net=int(data.get("coins",0) or 0)+self.get_bank_balance(guild.id,int(uid))+self.get_assets_value(guild.id,int(uid))
            ranked.append((member,net))
        ranked.sort(key=lambda x:x[1],reverse=True)
        ranked=ranked[:10]

        if lang=="en":
            title="💵 GGMW9 Rich List"; empty="📭 No ranking yet."; worth="Net Worth"
        elif lang=="fr":
            title="💵 Les plus riches de GGMW9"; empty="📭 Aucun classement pour le moment."; worth="Valeur nette"
        else:
            title="💵 أغنى الأعضاء فـ GGMW9"; empty="📭 مازال ماكاين حتى ترتيب."; worth="صافي الثروة"

        if not ranked:
            return discord.Embed(title=title,description=empty,color=discord.Color.gold())

        medals=["🥇","🥈","🥉"]
        lines=[]
        for i,(member,net) in enumerate(ranked):
            prefix=medals[i] if i<3 else f"`#{i+1}`"
            lines.append(f"{prefix} **{member.display_name}** — **{cfg.fmt_money(net)}** {worth}")
        return discord.Embed(title=title,description="\n".join(lines),color=discord.Color.gold(),timestamp=datetime.now())

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
        """Owner-only direct wallet adjustment in INTERNAL CENTS.

        No Daily Cap, no game cap, no total-earned counter, no bot log and
        no transaction-ledger entry. The recipient only gets a DM.
        """
        amount = int(amount)
        before = self.get_balance(guild.id, member.id)

        if amount >= 0:
            applied = self.add_coins(
                guild.id,
                member.id,
                amount,
                source="owner_private_adjustment",
                respect_cap=False,
                count_as_earned=False,
            )
        else:
            # Keep Wallet non-negative so the rest of the economy stays valid.
            remove = min(before, abs(amount))
            acc = self._acc(guild.id, member.id)
            acc["coins"] = before - remove
            self.db.save()
            applied = -remove

        after = self.get_balance(guild.id, member.id)

        dm_sent = True
        try:
            if applied >= 0:
                await member.send(
                    "💰 إدارة GGMW9 زادت ليك رصيد بشكل خاص.\n"
                    f"**+{cfg.fmt_money(applied)}**\n"
                    f"الرصيد دابا: **{cfg.fmt_money(after)}**"
                )
            else:
                await member.send(
                    "💸 إدارة GGMW9 نقصات من الرصيد بشكل خاص.\n"
                    f"**-{cfg.fmt_money(abs(applied))}**\n"
                    f"الرصيد دابا: **{cfg.fmt_money(after)}**"
                )
        except (discord.Forbidden, discord.HTTPException):
            dm_sent = False

        # Aggregate stats may refresh; this does not identify the Owner action.
        await self.refresh_economy_stats(guild)

        return {
            "before": before,
            "after": after,
            "applied": applied,
            "requested": amount,
            "dm_sent": dm_sent,
            "tx_id": None,
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
            title = "🏦 إيداع فالادخار" if action == "deposit" else "💸 سحب من الادخار"; label="المبلغ بالدولار"; placeholder="مثال: 25 أو 25.50"
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
        super().__init__(title=(f"💸 Transfer → {recipient.display_name}" if lang=="en" else f"💸 Transfert → {recipient.display_name}" if lang=="fr" else f"💸 تحويل لـ {recipient.display_name}")[:45])
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
    else: desc=f"🏦 الرصيد المدخر: **{cfg.fmt_money(bank)}**\n📈 النسبة ديالك: **{bps/100:.2f}% فالنهار**\n🧮 الربح المتوقع الجاي: **{cfg.fmt_money(estimate)}**\n\nالأرباح كتخلص **غير من الخزينة** وما كنخلقوش فلوس من والو."; min_n="أقل رصيد مؤهل"; cap_n="أقصى ربح يومي للحساب"; footer="أرباح الادخار كتخلص مرة وحدة كل نهار UTC"
    title="📈 حساب الادخار" if lang=="darija" else "📈 Savings Account" if lang=="en" else "📈 Compte d’épargne"
    boost_name="تعزيز النسبة من المتجر" if lang=="darija" else "Shop Rate Boost" if lang=="en" else "Boost de taux de la boutique"
    boost_value=("✅ خدام" if boost else "—") if lang=="darija" else ("✅ Active" if boost else "—") if lang=="en" else ("✅ Actif" if boost else "—")
    e=discord.Embed(title=title,description=desc,color=discord.Color.green()); e.add_field(name=min_n,value=cfg.fmt_money(minimum),inline=True); e.add_field(name=cap_n,value=cfg.fmt_money(cap),inline=True); e.add_field(name=boost_name,value=boost_value,inline=True); e.set_footer(text=footer); return e


def _build_assets_embed(cog:"Economy",guild:discord.Guild,user:discord.Member,lang="darija"):
    assets=cog.get_owned_assets(guild.id,user.id); book=cog.get_assets_value(guild.id,user.id); resale_pct=int(getattr(cfg,"ASSET_RESALE_PERCENT",40))
    if not assets: desc="📭 No assets yet. Buy them from Shop → Assets." if lang=="en" else "📭 Aucun actif. Achète-en dans Boutique → Actifs." if lang=="fr" else "📭 ماعندك حتى Asset دابا. شري الممتلكات من 🛒 Shop → 🏠 Assets."
    else:
        lines=[]
        for item_id,a in assets.items():
            paid=int(a.get("paid_price",0) or 0); resale=paid*resale_pct//100
            if lang=="en": detail=f"Book {cfg.fmt_money(paid)} • Sell {cfg.fmt_money(resale)}"
            elif lang=="fr": detail=f"Valeur {cfg.fmt_money(paid)} • Revente {cfg.fmt_money(resale)}"
            else: detail=f"القيمة المسجلة {cfg.fmt_money(paid)} • البيع {cfg.fmt_money(resale)}"
            lines.append(f"{a.get('emoji','🏠')} **{a.get('name',item_id)}** • {detail}")
        desc="\n".join(lines)
    title=(f"🏠 الممتلكات — {user.display_name}" if lang=="darija" else f"🏠 Assets — {user.display_name}" if lang=="en" else f"🏠 Actifs — {user.display_name}")
    book_name="القيمة المسجلة" if lang=="darija" else "Book Value" if lang=="en" else "Valeur comptable"
    resale_name="نسبة إعادة البيع" if lang=="darija" else "Market resale" if lang=="en" else "Revente"
    e=discord.Embed(title=title,description=desc,color=discord.Color.gold()); e.add_field(name=book_name,value=f"**{cfg.fmt_money(book)}**",inline=True); e.add_field(name=resale_name,value=f"**{resale_pct}%**",inline=True); return e


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
        else: content=f"💵 **تحويل من بنك لبنك**\n🏦 الادخار: **{cfg.fmt_money(self.cog.get_bank_balance(interaction.guild.id,interaction.user.id))}**\n📊 تحويلات اليوم: **{cfg.fmt_money(sent)} / {cfg.fmt_money(limit)}**\n"+("✅ الإعفاء من الرسوم خدام" if fee_free else f"💸 الرسوم: {getattr(cfg,'BANK_TRANSFER_FEE_BPS',100)/100:.2f}%")+"\n\nاختار العضو اللي بغيتي تحول ليه:"
        await interaction.response.edit_message(content=content,embed=None,view=BankTransferUserView(self.cog,self.user.id,self.lang,self.session_key))
    async def savings(self,interaction):
        if await self._ok(interaction): await interaction.response.edit_message(content=None,embed=_build_savings_embed(self.cog,interaction.guild,interaction.user,self.lang),view=self)
    async def loan(self,interaction):
        if not await self._ok(interaction): return
        loan=self.cog.get_active_loan(interaction.guild.id,interaction.user.id)
        if loan:
            overdue=self.cog._loan_is_overdue(loan)
            if self.lang=="en":
                content=f"💳 Loan **#{loan.get('id')}** {'⚠️ Overdue' if overdue else '🟢 Active'}\nRemaining: **{cfg.fmt_money(int(loan.get('remaining',0)))}**\nDue: <t:{self.cog._loan_due_unix(loan)}:F>"
            elif self.lang=="fr":
                content=f"💳 Prêt **#{loan.get('id')}** {'⚠️ En retard' if overdue else '🟢 Actif'}\nRestant : **{cfg.fmt_money(int(loan.get('remaining',0)))}**\nÉchéance : <t:{self.cog._loan_due_unix(loan)}:F>"
            else:
                content=f"💳 القرض **#{loan.get('id')}** {'⚠️ متأخر' if overdue else '🟢 خدام'}\nالباقي: **{cfg.fmt_money(int(loan.get('remaining',0)))}**\nآخر أجل: <t:{self.cog._loan_due_unix(loan)}:F>"
            await interaction.response.edit_message(content=content,embed=None,view=self); return
        terms=self.cog.get_loan_terms(interaction.guild.id,interaction.user.id); minimum=int(getattr(cfg,"LOAN_MIN_AMOUNT",2500))
        if int(terms["effective_limit"])<minimum:
            msg=(f"❌ Loan limit: **{cfg.fmt_money(terms['effective_limit'])}** • minimum {cfg.fmt_money(minimum)}" if self.lang=="en" else
                 f"❌ Limite du prêt : **{cfg.fmt_money(terms['effective_limit'])}** • minimum {cfg.fmt_money(minimum)}" if self.lang=="fr" else
                 f"❌ سقف القرض ديالك: **{cfg.fmt_money(terms['effective_limit'])}** • أقل مبلغ هو {cfg.fmt_money(minimum)}")
            await interaction.response.edit_message(content=msg,embed=None,view=self); return
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
    if lang=="en": intro=f"💳 المحفظة: **{cfg.fmt_money(balance)}** • 🏦 Savings: **{cfg.fmt_money(bank)}**\n"+(f"⭐ Level Discount: **-{discount}%**\n" if discount else "")+"\n"+"\n".join(lines)+"\n\nChoose a category. Every item has a real server utility, asset or prestige purpose."
    elif lang=="fr": intro=f"💳 Wallet : **{cfg.fmt_money(balance)}** • 🏦 Épargne : **{cfg.fmt_money(bank)}**\n"+(f"⭐ Réduction de niveau : **-{discount}%**\n" if discount else "")+"\n"+"\n".join(lines)+"\n\nChoisis une catégorie. Chaque article a une utilité, un actif ou un rôle de prestige."
    else: intro=f"💳 المحفظة: **{cfg.fmt_money(balance)}** • 🏦 الادخار: **{cfg.fmt_money(bank)}**\n"+(f"⭐ تخفيض المستوى: **-{discount}%**\n" if discount else "")+"\n"+"\n".join(lines)+"\n\nاختار القسم من اللائحة. المتجر فيه امتيازات، ممتلكات وحوايج للهيبة باش الفلوس يكون عندها معنى."
    title="🛒 متجر GGMW9" if lang=="darija" else "🛒 GGMW9 Marketplace" if lang=="en" else "🛒 Boutique GGMW9"
    footer="🌐 الدارجة • الإنجليزية • الفرنسية | الشراء كيمول الخزينة والفعاليات وكيحرق جزء من الفلوس" if lang=="darija" else "🌐 Darija • English • Français | Shop spend → Treasury + Events + Burn" if lang=="en" else "🌐 Darija • English • Français | Achats → Trésor + Événements + destruction"
    e=discord.Embed(title=title,description=intro,color=discord.Color.blurple()); e.set_footer(text=footer); return e


def build_shop_category_embed(cog:"Economy",guild:discord.Guild,user:discord.Member,category_id:str,lang="darija"):
    emoji,name,desc=_shop_category_text(category_id,lang); balance=cog.get_balance(guild.id,user.id); discount=cog.get_shop_discount_percent(guild.id,user.id); items=[i for i in cfg.SHOP_ITEMS if i.get("category")==category_id]; lines=[]
    for item in items:
        price=cog.get_shop_price(guild.id,user.id,item["price"]); affordable="✅" if balance>=price else "❌"; price_text=f"~~{cfg.fmt_money(item['price'])}~~ → **{cfg.fmt_money(price)}**" if price!=int(item["price"]) else f"**{cfg.fmt_money(price)}**"; lines.append(f"{affordable} {item['emoji']} **{item['name']}** — {price_text}\n↳ {_shop_item_desc(item,lang)}")
    empty="📭 This category is empty." if lang=="en" else "📭 Cette catégorie est vide." if lang=="fr" else "📭 هاد Category خاوية دابا."
    return discord.Embed(title=f"{emoji} {name}",description=(f"💳 المحفظة: **{cfg.fmt_money(balance)}**" if lang=="darija" else f"💳 المحفظة: **{cfg.fmt_money(balance)}**" if lang=="en" else f"💳 Portefeuille : **{cfg.fmt_money(balance)}**")+(f" • ⭐ -{discount}%" if discount else "")+"\n\n"+("\n\n".join(lines) if lines else empty),color=discord.Color.blurple())


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
        self.add_item(MyPurchasesButton(cog,user,lang,session_key))


def _shop_expiry_line(entry: dict, lang: str = "darija") -> str:
    expires = Economy._parse_shop_expiry(entry.get("expires"))
    if expires is None:
        return "♾️ دائم" if lang=="darija" else "♾️ Permanent" if lang=="en" else "♾️ Permanent"
    unix = int(expires.timestamp())
    return (
        f"⏳ حتى <t:{unix}:F> (<t:{unix}:R>)"
        if lang=="darija"
        else f"⏳ Until <t:{unix}:F> (<t:{unix}:R>)"
        if lang=="en"
        else f"⏳ Jusqu’au <t:{unix}:F> (<t:{unix}:R>)"
    )


def build_my_purchases_embed(cog:"Economy", guild:discord.Guild, user:discord.Member, lang="darija"):
    lang = lang if lang in {"darija","en","fr"} else "darija"
    acc = cog._acc(guild.id, user.id)
    now = datetime.now(timezone.utc)
    lines = []

    # Role-based purchases
    for p in acc.get("purchases", []) or []:
        exp = cog._parse_shop_expiry(p.get("expires"))
        if exp is not None and exp <= now:
            continue
        item = next((i for i in cfg.SHOP_ITEMS if i.get("id")==p.get("item_id")), None)
        role = guild.get_role(int(p.get("role_id") or 0)) if p.get("role_id") else None
        name = item.get("name") if item else p.get("item_id","شراء")
        role_txt = role.mention if role else ("⚠️ Role مفقودة" if lang=="darija" else "⚠️ Missing role")
        meta = p.get("meta") or {}
        color_txt = f" • 🎨 **{meta.get('hex')}**" if meta.get("hex") else ""
        lines.append(f"• **{name}** — {role_txt}{color_txt}\n  {_shop_expiry_line(p,lang)}")

    # Account perks
    perk_fields = [
        ("coins_boost_expires", "🎮 تعزيز جوائز الألعاب المصغرة"),
        ("bank_interest_boost_expires", "📈 تعزيز أرباح الادخار"),
        ("transfer_fee_pass_expires", "💸 تحويلات بلا رسوم"),
    ]
    for key, dz_name in perk_fields:
        dt = cog._parse_shop_expiry(acc.get(key))
        if dt and dt > now:
            unix = int(dt.timestamp())
            lines.append(f"• **{dz_name}**\n  ⏳ حتى <t:{unix}:F> (<t:{unix}:R>)")

    # XP boost lives in the Leveling store.
    bridge = getattr(cog.bot, "gg", {}) or {}
    get_level = bridge.get("get_user_level_data")
    if get_level:
        try:
            data = get_level(guild.id, user.id)
            raw = data.get("xp_boost_expires")
            if raw:
                xp_dt = datetime.fromisoformat(raw)
                if xp_dt.tzinfo is None:
                    xp_dt = xp_dt.replace(tzinfo=timezone.utc)
                if xp_dt > now:
                    unix = int(xp_dt.timestamp())
                    mult = data.get("xp_boost_multiplier", 1.0)
                    lines.append(f"• **⚡ تعزيز XP {mult}x**\n  ⏳ حتى <t:{unix}:F> (<t:{unix}:R>)")
        except Exception:
            pass

    credits = _shoutout_credits(cog,guild.id,user.id)
    if credits > 0:
        if lang=="en":
            lines.append(f"• **📣 Public Shoutout** — **{credits}** ready to publish")
        elif lang=="fr":
            lines.append(f"• **📣 Public Shoutout** — **{credits}** prêt(s) à publier")
        else:
            lines.append(f"• **📣 نشر عام** — عندك **{credits}** جاهزين للنشر")

    # Permanent assets
    assets = cog.get_owned_assets(guild.id, user.id)
    if assets:
        for asset in assets.values():
            lines.append(
                f"• **{asset.get('emoji','🏠')} {asset.get('name','ممتلك')}** — ♾️ دائم"
            )

    if lang=="en":
        title=f"🧾 {user.display_name}'s Purchases"
        desc="\n\n".join(lines) if lines else "📭 You don't have any active Shop benefits yet."
        footer="Real benefits • role purchases are checked and repaired automatically"
    elif lang=="fr":
        title=f"🧾 Achats de {user.display_name}"
        desc="\n\n".join(lines) if lines else "📭 Tu n’as aucun avantage actif de la boutique."
        footer="Avantages réels • les rôles achetés sont vérifiés et réparés automatiquement"
    else:
        title=f"🧾 مشتريات {user.display_name}"
        desc="\n\n".join(lines) if lines else "📭 ماعندك حتى امتياز خدام من المتجر دابا."
        footer="كل شراء عندو تأثير حقيقي • اللون ما كيبدلش Group ديال العضو فالليست • Staff كيبقا Staff"

    embed=discord.Embed(title=title,description=desc,color=discord.Color.teal(),timestamp=datetime.now())
    effective = cog._effective_colored_role(user)
    if lang=="darija":
        embed.add_field(
            name="🎨 اللون اللي باين دابا",
            value=(
                f"{effective.mention} • **#{int(effective.colour.value):06X}**"
                if effective else "ماكاين حتى لون من الرولات دابا."
            ),
            inline=False,
        )
    return embed


class ShopPurchasesView(discord.ui.View):
    def __init__(self,cog,user,lang="darija",session_key="shop"):
        super().__init__(timeout=900)
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
        self.add_item(ShopBackButton(cog,user,lang,session_key))
        self.add_item(RedeemShoutoutButton(cog,user,lang,session_key))
        self.add_item(ShopSessionLanguageSelect(cog,user,lang,session_key,row=2))


class MyPurchasesButton(discord.ui.Button):
    def __init__(self,cog,user,lang="darija",session_key="shop"):
        label="🧾 مشترياتي" if lang=="darija" else "🧾 My Purchases" if lang=="en" else "🧾 Mes achats"
        super().__init__(label=label,style=discord.ButtonStyle.primary,row=2)
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key

    async def callback(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        notes = await self.cog.repair_member_shop_roles(interaction.guild, interaction.user)
        fresh = interaction.guild.get_member(interaction.user.id) or interaction.user
        embed = build_my_purchases_embed(self.cog,interaction.guild,fresh,self.lang)
        if notes:
            repair_title="🔧 فحص تلقائي" if self.lang=="darija" else "🔧 Automatic check"
            embed.add_field(name=repair_title,value="\n".join(notes)[:1024],inline=False)
        await interaction.edit_original_response(
            content=None,
            embed=embed,
            view=ShopPurchasesView(self.cog,interaction.user,self.lang,self.session_key),
        )


SHOUTOUT_TYPES = {
    "promo": {
        "emoji": "🛍️",
        "color": 0xE91E63,
        "darija": "إشهار / مشروع",
        "en": "Promotion / Project",
        "fr": "Promotion / Projet",
        "title_d": "🛍️ إشهار من مجتمع GGMW9",
        "title_e": "🛍️ GGMW9 Community Promotion",
        "title_f": "🛍️ Promotion de la communauté GGMW9",
    },
    "announcement": {
        "emoji": "📢",
        "color": 0x3498DB,
        "darija": "إعلان عام",
        "en": "Public Announcement",
        "fr": "Annonce publique",
        "title_d": "📢 إعلان للمجتمع",
        "title_e": "📢 Community Announcement",
        "title_f": "📢 Annonce à la communauté",
    },
    "achievement": {
        "emoji": "🎉",
        "color": 0xF1C40F,
        "darija": "إنجاز / مناسبة",
        "en": "Achievement / Celebration",
        "fr": "Réussite / Célébration",
        "title_d": "🎉 إنجاز أو مناسبة",
        "title_e": "🎉 Achievement / Celebration",
        "title_f": "🎉 Réussite / Célébration",
    },
    "event": {
        "emoji": "🎮",
        "color": 0x9B59B6,
        "darija": "فعالية / تجمع",
        "en": "Event / Meetup",
        "fr": "Événement / Rencontre",
        "title_d": "🎮 فعالية من المجتمع",
        "title_e": "🎮 Community Event",
        "title_f": "🎮 Événement communautaire",
    },
    "looking": {
        "emoji": "🔎",
        "color": 0x2ECC71,
        "darija": "طلب / كنقلب على...",
        "en": "Looking For...",
        "fr": "Je recherche...",
        "title_d": "🔎 كنقلب على...",
        "title_e": "🔎 Looking For...",
        "title_f": "🔎 Je recherche...",
    },
    "community": {
        "emoji": "💬",
        "color": 0x5865F2,
        "darija": "رسالة للمجتمع",
        "en": "Community Message",
        "fr": "Message à la communauté",
        "title_d": "💬 رسالة للمجتمع",
        "title_e": "💬 Community Message",
        "title_f": "💬 Message à la communauté",
    },
}


def _shoutout_type_name(kind: str, lang: str) -> str:
    meta = SHOUTOUT_TYPES.get(kind, SHOUTOUT_TYPES["community"])
    return meta.get(lang, meta["darija"])


def _shoutout_credits(cog: "Economy", guild_id: int, user_id: int) -> int:
    return max(0, int(cog._acc(guild_id, user_id).get("shoutout_credits", 0) or 0))


def build_shoutout_studio_embed(cog:"Economy", guild:discord.Guild, user:discord.Member, lang="darija") -> discord.Embed:
    lang = lang if lang in {"darija","en","fr"} else "darija"
    credits = _shoutout_credits(cog, guild.id, user.id)
    channel_id = int(getattr(cfg, "SHOP_SHOUTOUT_CHANNEL_ID", 0) or 0)
    channel = guild.get_channel(channel_id) if channel_id else None
    ch = channel.mention if channel else "⚠️ غير مضبوطة"

    if lang == "en":
        title = "📣 Public Shoutout Studio"
        desc = (
            f"You have **{credits}** Public Shoutout credit(s).\n\n"
            "Choose what you want to publish. After that, a form opens for the title, message and optional link.\n"
            "A credit is consumed **only after the post is successfully published**."
        )
        footer = "No @everyone/@here pings • one credit = one public post"
        field = "Publishing channel"
    elif lang == "fr":
        title = "📣 Studio Public Shoutout"
        desc = (
            f"Tu as **{credits}** crédit(s) Public Shoutout.\n\n"
            "Choisis le type de publication, puis remplis le titre, le message et le lien optionnel.\n"
            "Le crédit est utilisé **uniquement après une publication réussie**."
        )
        footer = "Aucun ping @everyone/@here • un crédit = une publication"
        field = "Salon de publication"
    else:
        title = "📣 ستوديو النشر العام"
        desc = (
            f"عندك **{credits}** Shoutout جاهزة للنشر.\n\n"
            "اختار شنو بغيتي توصل للناس، ومن بعد كتتحل ليك استمارة تكتب فيها العنوان، الرسالة والرابط إلا كان.\n"
            "الرصيد كيتنقص **غير من بعد ما المنشور يتبعث بنجاح**."
        )
        footer = "بلا @everyone/@here • كل Shoutout = منشور عام واحد"
        field = "قناة النشر"

    embed = discord.Embed(title=title, description=desc, color=discord.Color.gold(), timestamp=datetime.now())
    embed.add_field(name=f"📍 {field}", value=ch, inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=footer)
    return embed


class ShoutoutTypeSelect(discord.ui.Select):
    def __init__(self,cog,user,lang="darija",session_key="shop"):
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
        options=[]
        for key,meta in SHOUTOUT_TYPES.items():
            options.append(discord.SelectOption(
                label=_shoutout_type_name(key,lang)[:100],
                value=key,
                emoji=meta["emoji"],
            ))
        placeholder = (
            "📣 شنو النوع ديال المنشور؟"
            if lang=="darija"
            else "📣 What kind of post?"
            if lang=="en"
            else "📣 Quel type de publication ?"
        )
        super().__init__(placeholder=placeholder,options=options,min_values=1,max_values=1,row=0)

    async def callback(self,interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True)
            return
        credits=_shoutout_credits(self.cog,interaction.guild.id,interaction.user.id)
        if credits <= 0:
            msg = (
                "❌ ماعندك حتى Shoutout جاهزة. شري وحدة من المتجر أولاً."
                if self.lang=="darija"
                else "❌ You have no Shoutout credit. Buy one from the Shop first."
                if self.lang=="en"
                else "❌ Tu n’as aucun crédit Shoutout. Achète-en un dans la boutique."
            )
            await interaction.response.edit_message(
                content=msg,
                embed=build_shop_home_embed(self.cog,interaction.guild,interaction.user,self.lang),
                view=ShopView(self.cog,interaction.user,self.lang,self.session_key),
            )
            return
        await interaction.response.send_modal(
            ShoutoutComposeModal(self.cog,self.values[0],self.lang,self.session_key)
        )


class ShoutoutStudioView(discord.ui.View):
    def __init__(self,cog,user,lang="darija",session_key="shop"):
        super().__init__(timeout=900)
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key
        self.add_item(ShoutoutTypeSelect(cog,user,lang,session_key))
        self.add_item(ShopBackButton(cog,user,lang,session_key))
        self.add_item(ShopSessionLanguageSelect(cog,user,lang,session_key,row=2))


class ShoutoutComposeModal(discord.ui.Modal):
    def __init__(self,cog,kind,lang="darija",session_key="shop"):
        self.cog,self.kind,self.lang,self.session_key=cog,kind,lang,session_key
        meta=SHOUTOUT_TYPES.get(kind,SHOUTOUT_TYPES["community"])
        title = (
            f"{meta['emoji']} {_shoutout_type_name(kind,lang)}"
        )[:45]
        super().__init__(title=title)

        self.headline=discord.ui.TextInput(
            label=(
                "العنوان (اختياري)" if lang=="darija"
                else "Headline (optional)" if lang=="en"
                else "Titre (optionnel)"
            ),
            placeholder=(
                "مثال: سيرفر جديد / فعالية السبت / إنجاز مهم"
                if lang=="darija"
                else "Example: New project / Saturday event / Big achievement"
                if lang=="en"
                else "Ex. : Nouveau projet / événement samedi / belle réussite"
            ),
            required=False,max_length=80,
        )
        self.message=discord.ui.TextInput(
            label=(
                "شنو بغيتي تقول للناس؟" if lang=="darija"
                else "What do you want to tell everyone?" if lang=="en"
                else "Que veux-tu dire à la communauté ?"
            ),
            placeholder=(
                "كتب الرسالة بوضوح..."
                if lang=="darija"
                else "Write your message clearly..."
                if lang=="en"
                else "Écris ton message clairement..."
            ),
            style=discord.TextStyle.paragraph,
            min_length=10,max_length=900,required=True,
        )
        self.link=discord.ui.TextInput(
            label=(
                "رابط (اختياري)" if lang=="darija"
                else "Link (optional)" if lang=="en"
                else "Lien (optionnel)"
            ),
            placeholder="https://...",
            required=False,max_length=300,
        )
        self.add_item(self.headline)
        self.add_item(self.message)
        self.add_item(self.link)

    async def on_submit(self,interaction):
        if not interaction.guild:
            await interaction.response.send_message("❌ Server only.",ephemeral=True)
            return

        credits=_shoutout_credits(self.cog,interaction.guild.id,interaction.user.id)
        if credits <= 0:
            await interaction.response.send_message(
                "❌ ماعندك حتى Shoutout جاهزة." if self.lang=="darija" else "❌ No Shoutout credit available.",
                ephemeral=True,
            )
            return

        channel_id=int(getattr(cfg,"SHOP_SHOUTOUT_CHANNEL_ID",0) or 0)
        channel=interaction.guild.get_channel(channel_id) if channel_id else None
        if not channel:
            await interaction.response.send_message(
                "❌ قناة النشر العام ماشي مضبوطة. الرصيد ديالك بقى محفوظ."
                if self.lang=="darija"
                else "❌ The Shoutout channel is not configured. Your credit was kept.",
                ephemeral=True,
            )
            return

        meta=SHOUTOUT_TYPES.get(self.kind,SHOUTOUT_TYPES["community"])
        clean_head=discord.utils.escape_mentions(str(self.headline.value).strip())
        clean_msg=discord.utils.escape_mentions(str(self.message.value).strip())
        clean_link=discord.utils.escape_mentions(str(self.link.value).strip())

        default_title = (
            meta["title_d"] if self.lang=="darija"
            else meta["title_e"] if self.lang=="en"
            else meta["title_f"]
        )
        embed=discord.Embed(
            title=(clean_head or default_title)[:256],
            description=clean_msg[:4096],
            color=int(meta["color"]),
            timestamp=datetime.now(),
        )
        embed.set_author(
            name=f"{interaction.user.display_name} • {_shoutout_type_name(self.kind,self.lang)}",
            icon_url=interaction.user.display_avatar.url,
        )
        if clean_link:
            embed.add_field(
                name="🔗 الرابط" if self.lang=="darija" else "🔗 Link" if self.lang=="en" else "🔗 Lien",
                value=clean_link[:1024],
                inline=False,
            )
        embed.set_footer(text="GGMW9 • Public Shoutout • منشور مدفوع من المتجر")

        try:
            posted=await channel.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden,discord.HTTPException) as exc:
            print(f"[SHOUTOUT] publish failed: {type(exc).__name__}: {exc}")
            await interaction.response.send_message(
                "❌ النشر فشل، وما تحيد حتى Shoutout من رصيدك."
                if self.lang=="darija"
                else "❌ Publishing failed. Your Shoutout credit was not consumed.",
                ephemeral=True,
            )
            return

        acc=self.cog._acc(interaction.guild.id,interaction.user.id)
        acc["shoutout_credits"]=max(0,int(acc.get("shoutout_credits",0) or 0)-1)
        history=acc.setdefault("shoutout_history",[])
        history.append({
            "kind":self.kind,
            "message_id":posted.id,
            "channel_id":channel.id,
            "created_at":datetime.now(timezone.utc).isoformat(),
        })
        del history[:-20]
        self.cog.db.save()

        remaining=int(acc.get("shoutout_credits",0) or 0)
        if self.lang=="en":
            msg=f"✅ Published in {channel.mention}. Remaining Shoutouts: **{remaining}**."
        elif self.lang=="fr":
            msg=f"✅ Publié dans {channel.mention}. Shoutouts restants : **{remaining}**."
        else:
            msg=f"✅ المنشور تبعث فـ {channel.mention}. بقاو عندك **{remaining}** Shoutout."

        await interaction.response.send_message(
            msg,
            ephemeral=True,
        )


class RedeemShoutoutButton(discord.ui.Button):
    def __init__(self,cog,user,lang="darija",session_key="shop"):
        credits=_shoutout_credits(cog,user.guild.id,user.id) if isinstance(user,discord.Member) else 0
        label=(
            f"📣 استعمل Shoutout ({credits})"
            if lang=="darija"
            else f"📣 Use Shoutout ({credits})"
            if lang=="en"
            else f"📣 Utiliser Shoutout ({credits})"
        )
        super().__init__(label=label[:80],style=discord.ButtonStyle.success,row=1,disabled=credits<=0)
        self.cog,self.user,self.lang,self.session_key=cog,user,lang,session_key

    async def callback(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True)
            return
        await interaction.response.edit_message(
            content=None,
            embed=build_shoutout_studio_embed(self.cog,interaction.guild,interaction.user,self.lang),
            view=ShoutoutStudioView(self.cog,interaction.user,self.lang,self.session_key),
        )


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
        if not item:
            msg="❌ Item unavailable." if self.lang=="en" else "❌ Article indisponible." if self.lang=="fr" else "❌ هاد المنتوج ماشي متوفر دابا."
            await interaction.response.edit_message(content=msg,embed=None,view=ShopView(self.cog,self.user,self.lang,self.session_key)); return
        price=self.cog.get_shop_price(interaction.guild.id,interaction.user.id,item["price"]); balance=self.cog.get_balance(interaction.guild.id,interaction.user.id)
        if balance<price:
            msg=f"❌ You need **{cfg.fmt_money(price-balance)}** more in Wallet." if self.lang=="en" else f"❌ Il te manque **{cfg.fmt_money(price-balance)}** dans le Wallet." if self.lang=="fr" else f"❌ ناقصك **{cfg.fmt_money(price-balance)}** فالمحفظة."
            await interaction.response.edit_message(content=msg,embed=build_shop_category_embed(self.cog,interaction.guild,interaction.user,self.category_id,self.lang),view=ShopItemsView(self.cog,self.user,self.category_id,self.lang,self.session_key)); return
        priced=dict(item); priced["_final_price"]=price
        if item["type"] in {"role_color","role_color_perm"}:
            await interaction.response.edit_message(content=f"🎨 {item['name']} — {cfg.fmt_money(price)}",embed=None,view=ColorPickView(self.cog,self.user,priced,self.category_id,self.lang,self.session_key)); return
        if item["type"]=="custom_role":
            await interaction.response.send_modal(CustomRoleModal(self.cog,priced,self.category_id,self.lang,self.session_key)); return
        await interaction.response.defer(ephemeral=True)
        ok,msg,_=await execute_purchase(self.cog,interaction.guild,interaction.user,priced)
        if ok and item.get("type")=="shoutout":
            await interaction.edit_original_response(
                content="✅ "+msg,
                embed=build_shoutout_studio_embed(self.cog,interaction.guild,interaction.user,self.lang),
                view=ShoutoutStudioView(self.cog,interaction.user,self.lang,self.session_key),
            )
            return
        prefix="✅ " if ok else "❌ "
        await interaction.edit_original_response(
            content=prefix+msg,
            embed=build_shop_category_embed(self.cog,interaction.guild,interaction.user,self.category_id,self.lang),
            view=ShopItemsView(self.cog,self.user,self.category_id,self.lang,self.session_key),
        )


def _palette_name(palette: dict, lang: str) -> str:
    names = palette.get("name") or {}
    return names.get(lang, names.get("darija", "ألوان"))


def _shop_color_name(color: dict, lang: str) -> str:
    names = color.get("name") or {}
    return names.get(lang, names.get("darija", color.get("id", "لون")))


class ColorPaletteSelect(discord.ui.Select):
    def __init__(self,cog,user,item,category_id="identity",lang="darija",session_key="shop"):
        self.cog,self.user,self.item,self.category_id,self.lang,self.session_key=cog,user,item,category_id,lang,session_key
        options=[]
        for pid,data in list(getattr(cfg,"SHOP_COLOR_PALETTES",{}).items())[:25]:
            count=len(data.get("colors",[]))
            options.append(discord.SelectOption(
                label=_palette_name(data,lang)[:100],
                value=pid,
                emoji=data.get("emoji","🎨"),
                description=(
                    f"{count} ألوان" if lang=="darija"
                    else f"{count} colors" if lang=="en"
                    else f"{count} couleurs"
                )[:100],
            ))
        super().__init__(
            placeholder=(
                "🎨 اختار مجموعة الألوان..." if lang=="darija"
                else "🎨 Choose a color palette..." if lang=="en"
                else "🎨 Choisis une palette..."
            ),
            options=options,min_values=1,max_values=1,row=0
        )

    async def callback(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.edit_message(
            content=(
                "🎨 اختار اللون. HEX ديالو باين تحت السمية." if self.lang=="darija"
                else "🎨 Choose a color. Its HEX is shown below." if self.lang=="en"
                else "🎨 Choisis une couleur. Son HEX est affiché."
            ),
            embed=None,
            view=PaletteColorsView(
                self.cog,self.user,self.item,self.values[0],
                self.category_id,self.lang,self.session_key
            ),
        )


class CustomHexButton(discord.ui.Button):
    def __init__(self,cog,user,item,category_id="identity",lang="darija",session_key="shop",row=1):
        super().__init__(
            label=(
                "🎯 لون HEX مخصص" if lang=="darija"
                else "🎯 Custom HEX" if lang=="en"
                else "🎯 HEX personnalisé"
            ),
            style=discord.ButtonStyle.primary,row=row
        )
        self.cog,self.user,self.item,self.category_id,self.lang,self.session_key=cog,user,item,category_id,lang,session_key

    async def callback(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.send_modal(
            CustomHexColorModal(self.cog,self.item,self.category_id,self.lang,self.session_key)
        )


class ColorPickView(discord.ui.View):
    def __init__(self,cog,user,item,category_id="identity",lang="darija",session_key="shop"):
        super().__init__(timeout=300)
        self.add_item(ColorPaletteSelect(cog,user,item,category_id,lang,session_key))
        self.add_item(CustomHexButton(cog,user,item,category_id,lang,session_key,row=1))
        self.add_item(ShopBackButton(cog,user,lang,session_key))
        self.add_item(ShopSessionLanguageSelect(cog,user,lang,session_key,row=2))


class PaletteColorSelect(discord.ui.Select):
    def __init__(self,cog,user,item,palette_id,category_id="identity",lang="darija",session_key="shop"):
        self.cog,self.user,self.item,self.palette_id,self.category_id,self.lang,self.session_key=cog,user,item,palette_id,category_id,lang,session_key
        palette=getattr(cfg,"SHOP_COLOR_PALETTES",{}).get(palette_id,{})
        options=[]
        for color in palette.get("colors",[])[:25]:
            value=int(color["value"])
            options.append(discord.SelectOption(
                label=_shop_color_name(color,lang)[:100],
                value=str(value),
                emoji=color.get("emoji","🎨"),
                description=f"#{value:06X}",
            ))
        super().__init__(
            placeholder=(
                "🎨 اختار اللون..." if lang=="darija"
                else "🎨 Choose a color..." if lang=="en"
                else "🎨 Choisis une couleur..."
            ),
            options=options,min_values=1,max_values=1,row=0
        )

    async def callback(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.defer(ephemeral=True)
        item=dict(self.item); item["color"]=int(self.values[0])
        ok,msg,_=await execute_purchase(self.cog,interaction.guild,interaction.user,item)
        await interaction.edit_original_response(
            content=("✅ " if ok else "❌ ")+msg,
            embed=build_shop_category_embed(self.cog,interaction.guild,interaction.user,self.category_id,self.lang),
            view=ShopItemsView(self.cog,self.user,self.category_id,self.lang,self.session_key),
        )


class PaletteBackButton(discord.ui.Button):
    def __init__(self,cog,user,item,category_id="identity",lang="darija",session_key="shop"):
        super().__init__(
            label=(
                "↩️ رجع لمجموعات الألوان" if lang=="darija"
                else "↩️ Back to palettes" if lang=="en"
                else "↩️ Retour aux palettes"
            ),
            style=discord.ButtonStyle.secondary,row=1
        )
        self.cog,self.user,self.item,self.category_id,self.lang,self.session_key=cog,user,item,category_id,lang,session_key

    async def callback(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(_eco_t(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.edit_message(
            content=(
                "🎨 اختار مجموعة، أو استعمل HEX مخصص." if self.lang=="darija"
                else "🎨 Choose a palette or use Custom HEX." if self.lang=="en"
                else "🎨 Choisis une palette ou utilise un HEX personnalisé."
            ),
            embed=None,
            view=ColorPickView(self.cog,self.user,self.item,self.category_id,self.lang,self.session_key),
        )


class PaletteColorsView(discord.ui.View):
    def __init__(self,cog,user,item,palette_id,category_id="identity",lang="darija",session_key="shop"):
        super().__init__(timeout=300)
        self.add_item(PaletteColorSelect(cog,user,item,palette_id,category_id,lang,session_key))
        self.add_item(CustomHexButton(cog,user,item,category_id,lang,session_key,row=1))
        self.add_item(PaletteBackButton(cog,user,item,category_id,lang,session_key))
        self.add_item(ShopSessionLanguageSelect(cog,user,lang,session_key,row=2))


class CustomHexColorModal(discord.ui.Modal):
    def __init__(self,cog,item,category_id="identity",lang="darija",session_key="shop"):
        self.cog,self.item,self.category_id,self.lang,self.session_key=cog,item,category_id,lang,session_key
        super().__init__(title=(
            "🎯 لون HEX مخصص" if lang=="darija"
            else "🎯 Custom HEX Color" if lang=="en"
            else "🎯 Couleur HEX personnalisée"
        ))
        self.hex_input=discord.ui.TextInput(
            label=(
                "HEX ديال اللون" if lang=="darija"
                else "Color HEX" if lang=="en"
                else "HEX de la couleur"
            ),
            placeholder="#8B5CF6",min_length=6,max_length=7,required=True
        )
        self.add_item(self.hex_input)

    async def on_submit(self,interaction):
        raw=str(self.hex_input.value).strip().upper()
        if raw.startswith("#"): raw=raw[1:]
        if not re.fullmatch(r"[0-9A-F]{6}",raw):
            await interaction.response.send_message(
                "❌ دخل HEX صحيح بحال `#8B5CF6`." if self.lang=="darija"
                else "❌ Enter a valid HEX such as `#8B5CF6`." if self.lang=="en"
                else "❌ Entre un HEX valide comme `#8B5CF6`.",
                ephemeral=True
            ); return
        value=int(raw,16)
        if value==0:
            await interaction.response.send_message(
                "❌ `#000000` عند Discord كيتحسب بلا لون. استعمل `#010101` للأسود." if self.lang=="darija"
                else "❌ Discord treats `#000000` as no color. Use `#010101` for black." if self.lang=="en"
                else "❌ Discord traite `#000000` comme aucune couleur. Utilise `#010101`.",
                ephemeral=True
            ); return
        await interaction.response.defer(ephemeral=True)
        item=dict(self.item); item["color"]=value
        ok,msg,_=await execute_purchase(self.cog,interaction.guild,interaction.user,item)
        await interaction.edit_original_response(
            content=("✅ " if ok else "❌ ")+msg,
            embed=build_shop_category_embed(self.cog,interaction.guild,interaction.user,self.category_id,self.lang),
            view=ShopItemsView(self.cog,interaction.user,self.category_id,self.lang,self.session_key),
        )


class CustomRoleModal(discord.ui.Modal):
    def __init__(self,cog,item,category_id="identity",lang="darija",session_key="shop"):
        self.cog,self.item,self.category_id,self.lang,self.session_key=cog,item,category_id,lang,session_key
        title="🏷️ Your رول خاص" if lang=="en" else "🏷️ Ton rôle personnalisé" if lang=="fr" else "🏷️ الرول المخصص ديالك"; super().__init__(title=title)
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
        return False, f"الرصيد تبدل. خاصك **{cfg.fmt_money(final_price)}** فالمحفظة.", final_price
    try:
        ok, msg = await apply_purchase(cog, guild, user, item)
    except Exception as exc:
        ok, msg = False, f"Purchase handler error: {type(exc).__name__}: {exc}"
    if not ok:
        cog.add_coins(guild.id, user.id, final_price, source="shop_refund", respect_cap=False, count_as_earned=False)
        return False, f"{msg}\n↩️ ترجيع تلقائي للفلوس: **{cfg.fmt_money(final_price)}**.", final_price
    try:
        await cog.route_shop_purchase(guild, user, final_price, item)
    except Exception as exc:
        # Item/benefit was applied, so do not duplicate/refund here. Log locally.
        print(f"[SHOP ROUTE] ⚠️ benefit applied but route/log failed: {exc}")
    saved = max(0, int(item["price"]) - final_price)
    note = f"\n⭐ تخفيض المستوى وفّر ليك **{cfg.fmt_money(saved)}**." if saved else ""
    return True, f"{msg}{note}\n💳 المحفظة: **{cfg.fmt_money(cog.get_balance(guild.id,user.id))}**", final_price


async def apply_purchase(cog: "Economy", guild: discord.Guild, user: discord.Member, item: dict) -> Tuple[bool, str]:
    bot = cog.bot
    item_type = item.get("type")

    if item_type == "xp_boost":
        bridge = getattr(bot, "gg", None)
        if not bridge or "get_user_level_data" not in bridge:
            return False, "نظام XP ماشي مربوط (bot.gg ناقص)."
        try:
            data = bridge["get_user_level_data"](guild.id, user.id)
            now = datetime.now()
            hours = int(item.get("duration_hours", 1))
            try:
                current = datetime.fromisoformat(data.get("xp_boost_expires")) if data.get("xp_boost_expires") else now
            except Exception:
                current = now
            start_at = current if current > now else now
            data["xp_boost_multiplier"] = item.get("multiplier", 2.0)
            data["xp_boost_expires"] = (start_at + timedelta(hours=hours)).isoformat()
            bridge["save_levels"]()
            return True, f"⚡ تعزيز XP **{item.get('multiplier',2.0)}x** تفعّل؛ تزادت **{hours} ساعة** للمدة."
        except Exception as exc:
            return False, f"خطأ فتفعيل تعزيز XP: {exc}"

    if item_type in {"role_color", "role_color_perm"}:
        if "color" not in item:
            return False, "خاصك تختار اللون أولاً."

        desired_color = int(item["color"])
        acc = cog._acc(guild.id, user.id)
        color_item_ids = {"color_basic", "color_month", "permanent_color"}

        # Reuse the member's existing personal color role instead of creating
        # duplicate roles every time the member buys another color/duration.
        existing_entry = cog._find_active_purchase(
            guild.id,
            user.id,
            effect_key="personal_color",
            item_ids=color_item_ids,
        )
        role = None
        if existing_entry and existing_entry.get("role_id"):
            role = guild.get_role(int(existing_entry["role_id"]))

        if role is None:
            legacy_names = {
                f"🎨 {user.display_name}",
                f"🎨 {user.display_name} • {user.id}",
            }
            role = next(
                (r for r in guild.roles if r.name in legacy_names and r in user.roles),
                None,
            )

        created = False
        previous_colour = int(role.colour.value) if role else None
        unique_name = f"🎨 {user.display_name[:55]} • {user.id}"[:100]

        try:
            if role is None:
                role = await guild.create_role(
                    name=unique_name,
                    colour=discord.Colour(desired_color),
                    hoist=False,
                    mentionable=False,
                    reason=f"GGMW9 Shop personal color — {user}",
                )
                created = True
            else:
                await role.edit(
                    name=unique_name,
                    colour=discord.Colour(desired_color),
                    hoist=False,
                    mentionable=False,
                    reason=f"GGMW9 Shop color change — {user}",
                )

            # If buyer is staff, neutralize only the staff role COLOR while
            # preserving its position/permissions/hoist. A fallback role keeps
            # the old staff color for staff members without a purchased color.
            await cog._ensure_staff_color_passthrough(guild)

            ok, reason = await cog._position_cosmetic_role(guild, role)
            if not ok:
                raise RuntimeError(reason)

            if role not in user.roles:
                await user.add_roles(role, reason="GGMW9 Shop personal color")

            # Verify the visible Discord color, not just that API calls returned 200.
            fresh = await guild.fetch_member(user.id)
            effective = cog._effective_colored_role(fresh)
            if not effective or effective.id != role.id or int(fresh.colour.value or 0) != desired_color:
                higher = effective.mention if effective else "Role أخرى"
                raise RuntimeError(
                    f"اللون ماقدرش يولي هو اللون الفعلي ديال الاسم؛ {higher} عندها أولوية أعلى."
                )

            days = 0 if item_type == "role_color_perm" else int(item.get("duration_days", 7))
            entry = _record_purchase(
                cog,
                guild.id,
                user.id,
                item,
                role.id,
                days,
                effect_key="personal_color",
                delete_role_on_expiry=True,
                meta={"color": desired_color, "hex": f"#{desired_color:06X}"},
                extend=True,
            )

            expires = entry.get("expires")
            if expires:
                try:
                    unix = int(datetime.fromisoformat(expires).timestamp())
                    duration_txt = f"حتى <t:{unix}:F> (<t:{unix}:R>)"
                except Exception:
                    duration_txt = f"لمدة {days} أيام"
            else:
                duration_txt = "بشكل دائم"

            return True, (
                f"🎨 اللون الشخصي تفعّل بصح: {role.mention}\n"
                f"🎨 اللون: **#{desired_color:06X}** • {duration_txt}\n"
                "✅ دابا خاص اللون يبان فاسمك فالرسائل ولائحة الأعضاء."
            )

        except discord.Forbidden:
            # Roll back a role created for a failed purchase.
            if created and role:
                try:
                    await role.delete(reason="Rollback failed shop color purchase")
                except Exception:
                    pass
            return False, (
                "البوت ماقدرش يطبق اللون. خاصو **Manage Roles** وRole ديالو "
                "تكون فوق رولات الأعضاء."
            )
        except Exception as exc:
            # Restore previous state because execute_purchase will refund money.
            if role:
                try:
                    if created:
                        await role.delete(reason="Rollback failed shop color purchase")
                    elif previous_colour is not None:
                        await role.edit(
                            colour=discord.Colour(previous_colour),
                            reason="Rollback failed shop color change",
                        )
                except Exception:
                    pass
            return False, f"ماقدرتش نفعّل اللون بشكل مرئي: {exc}"

    if item_type == "custom_role":
        try:
            # Custom Role buys the NAME/identity. Keep it colorless so it does
            # not override a separately purchased Personal Color.
            role = await guild.create_role(
                name=item["custom_name"][:32],
                colour=discord.Colour.default(),
                hoist=False,
                mentionable=False,
                reason=f"رول خاص من المتجر — {user}",
            )
            ok, reason = await cog._position_shop_role(guild, role, priority=3)
            if not ok:
                try:
                    await role.delete(reason="Rollback custom role hierarchy failure")
                except Exception:
                    pass
                return False, reason
            await user.add_roles(role, reason="GGMW9 Shop custom role")
            days = int(item.get("duration_days", 30))
            entry = _record_purchase(
                cog, guild.id, user.id, item, role.id, days=days,
                effect_key=f"custom_role:{role.id}",
                delete_role_on_expiry=True,
                meta={"role_name": role.name},
            )
            try:
                unix = int(datetime.fromisoformat(entry["expires"]).timestamp())
                expiry_txt = f"حتى <t:{unix}:F> (<t:{unix}:R>)"
            except Exception:
                expiry_txt = f"لمدة {days} يوم"
            # Restore personal color priority if the member owns one.
            await cog.repair_member_shop_roles(guild, user)
            return True, f"🏷️ الرول الخاصة {role.mention} تصاوبات وتركبات عليك {expiry_txt}."
        except discord.Forbidden:
            return False, "البوت ماعندوش صلاحية إدارة الرولات كافية."
        except Exception as exc:
            return False, f"خطأ فالرول الخاصة: {exc}"

    if item_type == "legend_tag":
        try:
            role = discord.utils.get(guild.roles, name="👑 LEGEND")
            if not role:
                role = await guild.create_role(name="👑 LEGEND", colour=discord.Colour.gold(), mentionable=False, reason="Legend Tag shop")
            ok, reason = await cog._position_shop_role(guild, role, priority=3)
            if not ok:
                return False, reason
            await user.add_roles(role, reason="Legend Tag purchase")
            days = int(item.get("duration_days", 7))
            entry = _record_purchase(
                cog, guild.id, user.id, item, role.id, days=days,
                effect_key=f"shared_role:{role.id}",
                delete_role_on_expiry=False,
                extend=True,
            )
            await cog.repair_member_shop_roles(guild, user)
            return True, f"👑 LEGEND Tag تفعّل **{days} أيام** (والمدة كتتزاد إلا شريتيه مرة أخرى)."
        except discord.Forbidden:
            return False, "البوت ماعندوش صلاحية إدارة الرولات كافية."
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
            ok, reason = await cog._position_shop_role(guild, role, priority=2)
            if not ok:
                return False, reason
            await user.add_roles(role, reason="GGMW9 Prestige purchase")
            days = int(item.get("duration_days", 30))
            entry = _record_purchase(
                cog, guild.id, user.id, item, role.id, days=days,
                effect_key=f"shared_role:{role.id}",
                delete_role_on_expiry=False,
                extend=True,
            )
            await cog.repair_member_shop_roles(guild, user)
            return True, f"👑 رول الهيبة {role.mention} تفعّلات **{days} يوم** (والمدة كتتزاد مع إعادة الشراء)."
        except discord.Forbidden:
            return False, "البوت ماعندوش صلاحية إدارة الرولات كافية."
        except Exception as exc:
            return False, f"خطأ: {exc}"

    if item_type == "coins_boost":
        acc = cog._acc(guild.id, user.id)
        now = datetime.now(timezone.utc)
        hours = int(item.get("duration_hours", 2))
        try:
            current = datetime.fromisoformat(acc.get("coins_boost_expires")) if acc.get("coins_boost_expires") else now
            if current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
        except Exception:
            current = now
        start_at = current if current > now else now
        acc["coins_boost_multiplier"] = item.get("multiplier", 1.25)
        acc["coins_boost_expires"] = (start_at + timedelta(hours=hours)).isoformat()
        cog.db.save()
        return True, f"🎮 تعزيز جوائز الألعاب المصغرة **{item.get('multiplier',1.25)}x** تفعّل؛ تزادت **{hours} ساعات** للمدة. الرهانات ما كتتأثرش."

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
            return True, f"📈 تعزيز نسبة أرباح الادخار تزاد **{days} أيام**. النسبة دابا **{cog.get_bank_interest_bps(guild.id,user.id)/100:.2f}%/day**."
        return True, f"💸 تحويلات بنكية بلا رسوم تفعّلو **{days} أيام**."

    if item_type == "collectible_asset":
        acc = cog._acc(guild.id, user.id)
        assets = acc.setdefault("assets", {})
        if item["id"] in assets:
            return False, "هاد الممتلك ديجا عندك؛ كل ممتلك كتملك منها نسخة وحدة."
        paid = int(item.get("_final_price", item["price"]))
        assets[item["id"]] = {
            "name": item["name"], "emoji": item.get("emoji", "🏠"),
            "paid_price": paid, "bought_at": datetime.now(timezone.utc).isoformat(),
        }
        cog.db.save()
        resale = paid * int(getattr(cfg, "ASSET_RESALE_PERCENT", 40)) // 100
        return True, f"{item.get('emoji','🏠')} **{item['name']}** دخلات للممتلكات ديالك. القيمة المسجلة {cfg.fmt_money(paid)} • إعادة البيع {cfg.fmt_money(resale)}."

    if item_type == "shoutout":
        channel_id = int(getattr(cfg, "SHOP_SHOUTOUT_CHANNEL_ID", 0) or 0)
        channel = guild.get_channel(channel_id) if channel_id else None
        if not channel:
            return False, "قناة النشر العام ماشي مضبوطة."

        acc = cog._acc(guild.id, user.id)
        acc["shoutout_credits"] = int(acc.get("shoutout_credits", 0) or 0) + 1
        cog.db.save()
        credits = int(acc["shoutout_credits"])
        return True, (
            f"📣 شريتي **Public Shoutout** وحدة. عندك دابا **{credits}** جاهزة للنشر.\n"
            "اختار النوع من ستوديو النشر، ومن بعد كتب الرسالة ديالك. "
            "إلا سديتي البانل، الرصيد كيبقى محفوظ فـ **🧾 مشترياتي**."
        )


    return False, "هاد النوع ديال المنتوج مازال ماخدامش."


def _record_purchase(
    cog: "Economy",
    guild_id: int,
    user_id: int,
    item: dict,
    role_id: int,
    days: int,
    *,
    effect_key: str = None,
    delete_role_on_expiry: bool = False,
    meta: dict = None,
    extend: bool = False,
):
    """Record a real active shop benefit.

    effect_key prevents a repeated purchase of the same effect from creating
    two independent expiry records that would remove the role too early.
    """
    acc = cog._acc(guild_id, user_id)
    purchases = acc.setdefault("purchases", [])
    now = datetime.now(timezone.utc)

    def parse(value):
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(str(value))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    existing = None
    if effect_key:
        for p in reversed(purchases):
            if p.get("effect_key") == effect_key:
                exp = parse(p.get("expires"))
                if p.get("expires") is None or exp is None or exp > now:
                    existing = p
                    break

    # Permanent purchase always wins over temporary duration.
    if days <= 0:
        expiry = None
    elif existing and existing.get("expires") is None:
        expiry = None
    else:
        base = now
        if extend and existing:
            old_exp = parse(existing.get("expires"))
            if old_exp and old_exp > now:
                base = old_exp
        expiry = (base + timedelta(days=days)).isoformat()

    payload = {
        "item_id": item["id"],
        "role_id": int(role_id) if role_id else None,
        "expires": expiry,
        "effect_key": effect_key,
        "delete_role_on_expiry": bool(delete_role_on_expiry),
        "meta": dict(meta or {}),
        "updated_at": now.isoformat(),
    }

    if existing is not None:
        existing.update(payload)
        entry = existing
    else:
        payload["bought_at"] = now.isoformat()
        purchases.append(payload)
        entry = payload

    cog.db.save()
    return entry


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
