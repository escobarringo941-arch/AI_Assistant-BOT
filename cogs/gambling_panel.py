# -*- coding: utf-8 -*-
"""GGMW9 Casino session UI — fixed transparent odds, bankroll limits, player analytics."""

import time
from collections import Counter
from datetime import datetime

import discord
from discord.ext import commands

import games_config as cfg
from storage import JsonStore


GAMBLING_GAMES = [
    {"id":"dice","emoji":"🎲","label":"Dice","desc":"d20 بثلاث مستويات مخاطرة ثابتة","desc_en":"d20 with three fixed risk levels","desc_fr":"d20 avec trois niveaux de risque fixes","cog":"Dice","min_attr":"DICE_MIN_BET","max_attr":"DICE_MAX_BET"},
    {"id":"coinflip","emoji":"🪙","label":"Coinflip","desc":"50/50 بPayout ثابت","desc_en":"50/50 with a fixed payout","desc_fr":"50/50 avec paiement fixe","cog":"Coinflip","min_attr":"COINFLIP_MIN_BET","max_attr":"COINFLIP_MAX_BET"},
    {"id":"slots","emoji":"🎰","label":"Slots","desc":"Reels موزونة + Progressive Jackpot","desc_en":"Weighted reels + Progressive Jackpot","desc_fr":"Rouleaux pondérés + jackpot progressif","cog":"Slots","min_attr":"SLOTS_MIN_BET","max_attr":"SLOTS_MAX_BET"},
    {"id":"scratch","emoji":"🎫","label":"Scratch Card","desc":"نتائج ثابتة ومدروسة بلا 3-match بالغلط","desc_en":"Fixed outcome table with protected match logic","desc_fr":"Table de résultats fixe avec logique de correspondance protégée","cog":"Scratch","min_attr":"SCRATCH_MIN_BET","max_attr":"SCRATCH_MAX_BET"},
    {"id":"lottery","emoji":"🎟️","label":"Lottery","desc":"4 أرقام + Jackpot على 4/4","desc_en":"4 numbers + Jackpot on a 4/4 match","desc_fr":"4 numéros + jackpot sur un 4/4","cog":"Lottery","min_attr":"LOTTERY_MIN_BET","max_attr":"LOTTERY_MAX_BET"},
]
GAME_BY_ID = {g["id"]: g for g in GAMBLING_GAMES}


def _limits(game_id: str):
    meta = GAME_BY_ID[game_id]
    return int(getattr(cfg, meta["min_attr"])), int(getattr(cfg, meta["max_attr"]))


def _game_cog(bot: commands.Bot, game_id: str):
    meta = GAME_BY_ID.get(game_id)
    return bot.get_cog(meta["cog"]) if meta else None


def effective_max_bet(bot: commands.Bot, guild_id: int, user_id: int, game_id: str) -> int:
    """Table max + bankroll protection. Same rule for everybody; never changes odds."""
    min_bet, table_max = _limits(game_id)
    eco = bot.get_cog("Economy")
    if not eco:
        return 0
    wallet = max(0, int(eco.get_balance(guild_id, user_id)))
    if wallet < min_bet:
        return 0
    pct = max(1, int(getattr(cfg, "CASINO_MAX_BET_WALLET_PERCENT", 10) or 10))
    bankroll_max = wallet * pct // 100
    # A small bankroll may still play exactly the table minimum.
    return min(table_max, max(min_bet, bankroll_max))


def build_bet_limit_error(bot: commands.Bot, guild: discord.Guild, user: discord.abc.User, game_id: str, bet: int, lang: str) -> str:
    mn, table_max = _limits(game_id)
    eco = bot.get_cog("Economy")
    wallet = eco.get_balance(guild.id, user.id) if eco else 0
    eff = effective_max_bet(bot, guild.id, user.id, game_id)
    pct = max(1, int(getattr(cfg, "CASINO_MAX_BET_WALLET_PERCENT", 25) or 25))
    if bet < mn:
        if lang == "en": return f"❌ Minimum bet is **{cfg.fmt_money(mn)}**."
        if lang == "fr": return f"❌ La mise minimale est **{cfg.fmt_money(mn)}**."
        return f"❌ أقل Bet هي **{cfg.fmt_money(mn)}**."
    if bet > table_max:
        if lang == "en": return f"❌ Table maximum for this game is **{cfg.fmt_money(table_max)}**."
        if lang == "fr": return f"❌ La mise maximale de cette table est **{cfg.fmt_money(table_max)}**."
        return f"❌ Table Max ديال هاد اللعبة هي **{cfg.fmt_money(table_max)}**."
    if bet > eff:
        if lang == "en":
            return (f"❌ Bet **{cfg.fmt_money(bet)}** is above your current bankroll limit.\n"
                    f"✅ Allowed now: **{cfg.fmt_money(mn)} → {cfg.fmt_money(eff)}**\n"
                    f"💳 Wallet: **{cfg.fmt_money(wallet)}** • protection: **{pct}% per wager**. Savings is not used by Casino.")
        if lang == "fr":
            return (f"❌ La mise **{cfg.fmt_money(bet)}** dépasse ta limite actuelle.\n"
                    f"✅ Autorisé maintenant : **{cfg.fmt_money(mn)} → {cfg.fmt_money(eff)}**\n"
                    f"💳 Wallet : **{cfg.fmt_money(wallet)}** • protection : **{pct}% par pari**. L'épargne n'est pas utilisée au Casino.")
        return (f"❌ Bet **{cfg.fmt_money(bet)}** أكبر من limit ديالك دابا.\n"
                f"✅ المسموح ليك: **{cfg.fmt_money(mn)} → {cfg.fmt_money(eff)}**\n"
                f"💳 Wallet: **{cfg.fmt_money(wallet)}** • حماية Bankroll: **{pct}% فالرهان الواحد**. Savings ماكيدخلش فالقمار.")
    return "❌ Bet خارج limit."


def _activity_db(bot: commands.Bot) -> JsonStore:
    """Persistent recent casino behavior. Used for analytics/anti-bot only, never RNG."""
    if not hasattr(bot, "_ggmw9_casino_activity_db"):
        bot._ggmw9_casino_activity_db = JsonStore("casino_activity.json", default={})
    return bot._ggmw9_casino_activity_db


def _activity_store(bot: commands.Bot) -> dict:
    return _activity_db(bot).data


def _save_activity(bot: commands.Bot):
    try:
        _activity_db(bot).save()
    except Exception as exc:
        # Analytics must never break a casino round.
        print(f"[CASINO ANALYTICS] save failed: {exc}")


def _activity_key(guild_id: int, user_id: int) -> str:
    return f"{int(guild_id)}:{int(user_id)}"


def recent_casino_activity(bot: commands.Bot, guild_id: int, user_id: int) -> list:
    store = _activity_store(bot)
    key = _activity_key(guild_id, user_id)
    now = time.time()
    window = max(1, int(getattr(cfg, "CASINO_PROFILE_WINDOW_MINUTES", 30))) * 60
    original = list(store.get(key, []) or [])
    rows = [r for r in original if now - float(r.get("ts", 0)) <= window][-250:]
    if rows != original:
        if rows:
            store[key] = rows
        else:
            store.pop(key, None)
        _save_activity(bot)
    return rows


def can_start_casino_round(bot: commands.Bot, guild_id: int, user_id: int) -> tuple[bool, int, int]:
    rows = recent_casino_activity(bot, guild_id, user_id)
    limit = max(1, int(getattr(cfg, "CASINO_MAX_ROUNDS_30M", 60)))
    return len(rows) < limit, len(rows), limit


def record_casino_round(bot: commands.Bot, guild_id: int, user_id: int, game_id: str, bet: int, payout: int):
    rows = recent_casino_activity(bot, guild_id, user_id)
    rows.append({"ts": time.time(), "game": game_id, "bet": int(bet), "payout": int(payout)})
    _activity_store(bot)[_activity_key(guild_id, user_id)] = rows[-250:]
    _save_activity(bot)


def analyze_recent_play(rows: list) -> dict:
    """Transparent playstyle signals. They never alter odds or payout tables."""
    if not rows:
        return {
            "rounds": 0, "avg_bet": 0, "max_bet": 0, "win_rate": 0.0,
            "chase_count": 0, "loss_streak": 0, "tempo": "—", "signal": "🟢 No recent play",
        }
    bets = [max(0, int(r.get("bet", 0) or 0)) for r in rows]
    payouts = [max(0, int(r.get("payout", 0) or 0)) for r in rows]
    wins = sum(1 for p in payouts if p > 0)
    chase_count = 0
    for prev, cur in zip(rows, rows[1:]):
        prev_bet = max(0, int(prev.get("bet", 0) or 0))
        cur_bet = max(0, int(cur.get("bet", 0) or 0))
        prev_lost = int(prev.get("payout", 0) or 0) <= 0
        # Bet escalation after a loss; informative only. Minimum +$1 avoids noise on tiny bets.
        if prev_lost and cur_bet >= max(prev_bet * 3 // 2, prev_bet + 100):
            chase_count += 1
    loss_streak = 0
    for r in reversed(rows):
        if int(r.get("payout", 0) or 0) > 0:
            break
        loss_streak += 1
    gaps = []
    for prev, cur in zip(rows, rows[1:]):
        gap = float(cur.get("ts", 0) or 0) - float(prev.get("ts", 0) or 0)
        if gap >= 0:
            gaps.append(gap)
    avg_gap = (sum(gaps) / len(gaps)) if gaps else None
    if avg_gap is None:
        tempo = "—"
    elif avg_gap < 8:
        tempo = "⚡ Very fast"
    elif avg_gap < 20:
        tempo = "🏃 Fast"
    else:
        tempo = "🧘 Normal"
    n = len(rows)
    if n >= 50 or chase_count >= 6 or loss_streak >= 8:
        signal = "🔴 High-intensity session"
    elif n >= 30 or chase_count >= 3 or loss_streak >= 5:
        signal = "🟠 Aggressive session"
    elif n >= 12:
        signal = "🟡 Active session"
    else:
        signal = "🟢 Casual session"
    return {
        "rounds": n,
        "avg_bet": sum(bets) // n,
        "max_bet": max(bets),
        "win_rate": wins * 100.0 / n,
        "chase_count": chase_count,
        "loss_streak": loss_streak,
        "tempo": tempo,
        "signal": signal,
    }


def _lang(bot: commands.Bot, guild_id: int, user_id: int) -> str:
    fn = getattr(bot, "gg", {}).get("get_panel_language")
    if callable(fn):
        try:
            value = str(fn(guild_id, user_id) or "darija").lower()
            return value if value in {"darija", "en", "fr"} else "darija"
        except Exception:
            pass
    return "darija"


def _set_lang(bot: commands.Bot, guild_id: int, user_id: int, lang: str) -> str:
    fn = getattr(bot, "gg", {}).get("set_panel_language")
    if callable(fn):
        try:
            return fn(guild_id, user_id, lang)
        except Exception:
            pass
    return lang if lang in {"darija", "en", "fr"} else "darija"


async def _upsert(interaction: discord.Interaction, session_key: str, **kwargs):
    fn = getattr(interaction.client, "gg", {}).get("upsert_ephemeral_panel")
    if callable(fn):
        return await fn(interaction, session_key, **kwargs)
    if not interaction.response.is_done():
        return await interaction.response.send_message(ephemeral=True, **kwargs)
    return await interaction.followup.send(ephemeral=True, **kwargs)


def _game_desc(meta: dict, lang: str) -> str:
    if lang == "en":
        return meta.get("desc_en", meta["desc"])
    if lang == "fr":
        return meta.get("desc_fr", meta["desc"])
    return meta["desc"]


def _casino_text(lang: str, key: str, **fmt) -> str:
    data = {
        "darija": {
            "session_title": "🎰 GGMW9 Casino — Session عادلة",
            "session_desc": "💳 Wallet: **{wallet}**\n🧾 النشاط: **{rounds}/{limit} rounds** فآخر {window} دقيقة\n\nاختار اللعبة وكتب الرهان بالدولار. نفس الـSession كتتبدل فبلاصتها باش مايبقاش spam.\n🔒 **Odds ثابتة على الجميع**؛ Player Profile غير analytics/anti-bot وما كيبدلش RNG.",
            "tables": "🎮 الطاولات",
            "your_max": "الحد ديالك",
            "guard_title": "⏳ حماية الـSession",
            "guard": "وصلتي حد الجولات فهاد النافذة. استنى شوية؛ Odds ما تبدلوش.",
            "choose": "🎮 اختار لعبة Casino...",
            "not_yours": "❌ هاد Session ماشي ديالك.",
            "unavailable": "❌ اللعبة أو Economy ماشي متوفرة.",
            "active": "❌ عندك round خدامة دابا.",
            "enter_bet": "💵 دخل الرهان",
            "bet_label": "الرهان بالدولار",
            "current_bet": "الحالي {bet} — كتب الرهان الجديد",
            "bad_amount": "❌ دخل مبلغ بحال `5` أو `5.50`.",
            "limit": "❌ Bet **{bet}** خارج limit ديالك.",
            "need": "❌ ناقصك **{amount}** فالWallet.",
            "wallet_changed": "❌ Wallet تبدلت وما بقاتش كافية.",
            "bankroll": "Bankroll max ديالك دابا: **{maxbet}**",
            "bankroll_note": "(max {pct}% من Wallet، مع minimum table bet)",
            "risk": "Fixed odds؛ اختار مستوى المخاطرة.",
            "same_bet": "🔄 نفس الرهان",
            "change_bet": "💵 بدل الرهان",
            "public_desc": "Casino صعيب، شفاف وعادل: **fixed odds للجميع** + progressive jackpot + bankroll/session protection.\nالأرباح ديال Casino ما داخلاش فـDaily mini-game cap.",
            "protection": "🧠 الحماية",
            "fairness_help": "ضغط **Fairness** باش تشوف RTP/House Edge. Player Profile ما كيغيّرش RNG.",
            "langs": "🌍 اللغات",
            "langs_value": "الدارجة هي الأساسية. بدّل لغتك من اللائحة لتحت: 🇲🇦 Darija • 🇬🇧 English • 🇫🇷 Français",
            "wallet_title": "💵 الرصيد",
            "wallet_line": "💳 Wallet: **{wallet}**\n🏦 Savings: **{bank}**\n🎮 باقي Mini-game daily rewards: **{daily}**",
            "stats_none": "مازال ما عندك حتى Casino stats.",
        },
        "en": {
            "session_title": "🎰 GGMW9 Casino — Fair Session",
            "session_desc": "💳 Wallet: **{wallet}**\n🧾 Activity: **{rounds}/{limit} rounds** in the last {window} minutes\n\nChoose a game and enter your bet in USD. The same private session is edited so you do not get message spam.\n🔒 **Odds are identical for everyone**; Player Profile is analytics/anti-bot only and never changes RNG.",
            "tables": "🎮 Tables",
            "your_max": "your max",
            "guard_title": "⏳ Session Guard",
            "guard": "You reached the round limit for this window. Wait a little; your odds are unchanged.",
            "choose": "🎮 Choose a Casino game...",
            "not_yours": "❌ This session is not yours.",
            "unavailable": "❌ The game or Economy is unavailable.",
            "active": "❌ You already have an active round.",
            "enter_bet": "💵 Enter bet",
            "bet_label": "Bet in USD",
            "current_bet": "Current {bet} — enter a new bet",
            "bad_amount": "❌ Enter an amount such as `5` or `5.50`.",
            "limit": "❌ Bet **{bet}** is outside your limit.",
            "need": "❌ You need **{amount}** more in your Wallet.",
            "wallet_changed": "❌ Your Wallet changed and no longer has enough funds.",
            "bankroll": "Your current bankroll max: **{maxbet}**",
            "bankroll_note": "(max {pct}% of Wallet, while respecting the table minimum)",
            "risk": "Fixed odds; choose your risk level.",
            "same_bet": "🔄 Same bet",
            "change_bet": "💵 Change bet",
            "public_desc": "A harder, transparent and fair Casino: **fixed odds for everyone** + progressive jackpot + bankroll/session protection.\nCasino winnings are separate from the non-casino daily mini-game cap.",
            "protection": "🧠 Protection",
            "fairness_help": "Press **Fairness** to see RTP/House Edge. Player Profile never changes RNG.",
            "langs": "🌍 Languages",
            "langs_value": "Darija is the default. Choose your personal language below: 🇲🇦 Darija • 🇬🇧 English • 🇫🇷 Français",
            "wallet_title": "💵 Balance",
            "wallet_line": "💳 Wallet: **{wallet}**\n🏦 Savings: **{bank}**\n🎮 Remaining mini-game daily rewards: **{daily}**",
            "stats_none": "You do not have Casino stats yet.",
        },
        "fr": {
            "session_title": "🎰 GGMW9 Casino — Session équitable",
            "session_desc": "💳 Wallet : **{wallet}**\n🧾 Activité : **{rounds}/{limit} parties** sur les {window} dernières minutes\n\nChoisis un jeu et saisis ta mise en USD. La même session privée est modifiée pour éviter le spam.\n🔒 **Les probabilités sont identiques pour tous** ; le profil joueur sert uniquement aux analyses/anti-bot et ne modifie jamais le RNG.",
            "tables": "🎮 Tables",
            "your_max": "ton maximum",
            "guard_title": "⏳ Protection de session",
            "guard": "Tu as atteint la limite de parties pour cette période. Attends un peu ; tes probabilités ne changent pas.",
            "choose": "🎮 Choisis un jeu de Casino...",
            "not_yours": "❌ Cette session ne t'appartient pas.",
            "unavailable": "❌ Le jeu ou l'Economy est indisponible.",
            "active": "❌ Tu as déjà une partie active.",
            "enter_bet": "💵 Saisir la mise",
            "bet_label": "Mise en USD",
            "current_bet": "Actuelle {bet} — saisis une nouvelle mise",
            "bad_amount": "❌ Saisis un montant comme `5` ou `5.50`.",
            "limit": "❌ La mise **{bet}** dépasse ta limite.",
            "need": "❌ Il te manque **{amount}** dans le Wallet.",
            "wallet_changed": "❌ Ton Wallet a changé et le solde est maintenant insuffisant.",
            "bankroll": "Ton maximum actuel : **{maxbet}**",
            "bankroll_note": "(max {pct}% du Wallet, tout en respectant le minimum de la table)",
            "risk": "Probabilités fixes ; choisis ton niveau de risque.",
            "same_bet": "🔄 Même mise",
            "change_bet": "💵 Changer la mise",
            "public_desc": "Un Casino plus difficile, transparent et équitable : **probabilités fixes pour tous** + jackpot progressif + protection bankroll/session.\nLes gains du Casino sont séparés de la limite quotidienne des mini-jeux hors Casino.",
            "protection": "🧠 Protection",
            "fairness_help": "Appuie sur **Fairness** pour voir le RTP/House Edge. Le profil joueur ne modifie jamais le RNG.",
            "langs": "🌍 Langues",
            "langs_value": "La darija est la langue par défaut. Choisis ta langue personnelle ci-dessous : 🇲🇦 Darija • 🇬🇧 English • 🇫🇷 Français",
            "wallet_title": "💵 Solde",
            "wallet_line": "💳 Wallet : **{wallet}**\n🏦 Épargne : **{bank}**\n🎮 Récompenses quotidiennes mini-jeux restantes : **{daily}**",
            "stats_none": "Tu n'as pas encore de statistiques Casino.",
        },
    }
    value = data.get(lang, data["darija"]).get(key, data["darija"].get(key, key))
    try:
        return value.format(**fmt)
    except Exception:
        return value


def build_session_menu_embed(bot: commands.Bot, guild: discord.Guild, user: discord.abc.User, lang: str = "darija"):
    eco = bot.get_cog("Economy")
    wallet = eco.get_balance(guild.id, user.id) if eco else 0
    ok, rounds, limit = can_start_casino_round(bot, guild.id, user.id)
    window = getattr(cfg, "CASINO_PROFILE_WINDOW_MINUTES", 30)
    embed = discord.Embed(
        title=_casino_text(lang, "session_title"),
        description=_casino_text(
            lang, "session_desc", wallet=cfg.fmt_money(wallet), rounds=rounds, limit=limit, window=window
        ),
        color=discord.Color.gold(),
    )
    lines = []
    for g in GAMBLING_GAMES:
        mn, mx = _limits(g["id"])
        eff = effective_max_bet(bot, guild.id, user.id, g["id"])
        lines.append(
            f"{g['emoji']} **{g['label']}** — {cfg.fmt_money(mn)} → {cfg.fmt_money(mx)} • "
            f"{_casino_text(lang, 'your_max')} {cfg.fmt_money(eff)}"
        )
    embed.add_field(name=_casino_text(lang, "tables"), value="\n".join(lines), inline=False)
    if not ok:
        embed.add_field(name=_casino_text(lang, "guard_title"), value=_casino_text(lang, "guard"), inline=False)
    return embed


def build_bet_error_embed(
    bot: commands.Bot,
    guild: discord.Guild,
    user: discord.abc.User,
    game_id: str,
    text: str,
    lang: str = "darija",
):
    meta = GAME_BY_ID[game_id]
    min_bet, table_max = _limits(game_id)
    eff = effective_max_bet(bot, guild.id, user.id, game_id)
    return discord.Embed(
        title=f"{meta['emoji']} {meta['label']} — Bet",
        description=(
            f"{text}\n\nTable: **{cfg.fmt_money(min_bet)} → {cfg.fmt_money(table_max)}**\n"
            f"{_casino_text(lang, 'bankroll', maxbet=cfg.fmt_money(eff))}\n"
            f"{_casino_text(lang, 'bankroll_note', pct=getattr(cfg, 'CASINO_MAX_BET_WALLET_PERCENT', 10))}"
        ),
        color=discord.Color.red(),
    )


def build_fairness_embed(lang: str = "darija") -> discord.Embed:
    rtp = cfg.CASINO_RTP
    descriptions = {
        "darija": (
            f"**{getattr(cfg,'CASINO_FAIRNESS_VERSION','GGMW9 Fair RNG')}**\n\n"
            "✅ نفس Odds لكل عضو، مهما كان رابح ولا خاسر.\n"
            "✅ RNG من SystemRandom/OS entropy فالألعاب.\n"
            "✅ Player Profile كيقرا النشاط غير للـanalytics/anti-bot.\n"
            "❌ ماكاينش adaptive rigging ولا تغيير سري للفرص."
        ),
        "en": (
            f"**{getattr(cfg,'CASINO_FAIRNESS_VERSION','GGMW9 Fair RNG')}**\n\n"
            "✅ Every member receives the same odds regardless of past results.\n"
            "✅ Games use SystemRandom / OS entropy.\n"
            "✅ Player Profile reads activity only for analytics/anti-bot.\n"
            "❌ No adaptive rigging or hidden personalized odds."
        ),
        "fr": (
            f"**{getattr(cfg,'CASINO_FAIRNESS_VERSION','GGMW9 Fair RNG')}**\n\n"
            "✅ Tous les membres ont les mêmes probabilités, quels que soient leurs résultats passés.\n"
            "✅ Les jeux utilisent SystemRandom / l'entropie du système.\n"
            "✅ Le profil joueur analyse l'activité uniquement pour analytics/anti-bot.\n"
            "❌ Aucun trucage adaptatif ni probabilités personnalisées cachées."
        ),
    }
    embed = discord.Embed(
        title="🛡️ Casino Fairness & RTP",
        description=descriptions.get(lang, descriptions["darija"]),
        color=discord.Color.green(),
    )
    embed.add_field(name="🪙 Coinflip", value=f"RTP **{rtp['coinflip']:.2f}%** • Edge **{100-rtp['coinflip']:.2f}%**", inline=True)
    embed.add_field(name="🎲 Dice Low", value=f"RTP **{rtp['dice_low']:.2f}%** • Edge **{100-rtp['dice_low']:.2f}%**", inline=True)
    embed.add_field(name="🎲 Dice Medium", value=f"RTP **{rtp['dice_medium']:.2f}%** • Edge **{100-rtp['dice_medium']:.2f}%**", inline=True)
    embed.add_field(name="🎲 Dice High", value=f"RTP **{rtp['dice_high']:.2f}%** • Edge **{100-rtp['dice_high']:.2f}%**", inline=True)
    embed.add_field(name="🎰 Slots", value=f"RTP ≈ **{rtp['slots']:.2f}%** • Edge ≈ **{100-rtp['slots']:.2f}%**", inline=True)
    embed.add_field(name="🎫 Scratch", value=f"RTP **{rtp['scratch']:.2f}%** • Edge **{100-rtp['scratch']:.2f}%**", inline=True)
    embed.add_field(name="🎟️ Lottery", value=f"Base RTP ≈ **{rtp['lottery']:.2f}%** + funded Jackpot", inline=True)
    footer = {
        "darija": "RTP هو long-run theoretical return، ماشي ضمان ديال أي session قصيرة",
        "en": "RTP is a long-run theoretical return, not a guarantee for a short session",
        "fr": "Le RTP est un rendement théorique à long terme, pas une garantie sur une courte session",
    }
    embed.set_footer(text=footer.get(lang, footer["darija"]))
    return embed


def build_profile_embed(bot: commands.Bot, guild: discord.Guild, user: discord.Member, lang: str = "darija") -> discord.Embed:
    total_wagered = total_won = total_rounds = wins = losses = 0
    counts = Counter()
    for g in GAMBLING_GAMES:
        cog = _game_cog(bot, g["id"])
        if not cog:
            continue
        s = cog.stats(guild.id, user.id)
        r = int(s.get("wins", 0)) + int(s.get("losses", 0))
        total_rounds += r
        wins += int(s.get("wins", 0))
        losses += int(s.get("losses", 0))
        total_wagered += int(s.get("wagered", 0))
        total_won += int(s.get("won", 0))
        counts[g["id"]] += r
    recent = recent_casino_activity(bot, guild.id, user.id)
    recent_wager = sum(int(r.get("bet", 0)) for r in recent)
    recent_net = sum(int(r.get("payout", 0)) - int(r.get("bet", 0)) for r in recent)
    behavior = analyze_recent_play(recent)
    favorite = counts.most_common(1)[0][0] if counts else None
    fav_meta = GAME_BY_ID.get(favorite)
    n = len(recent)

    labels = {
        "darija": {
            "desc": "Profile تحليلي فقط؛ **ما كيبدلش Odds ولا Payouts**.", "rounds": "🎮 All-time rounds",
            "wl": "🏆 W/L", "fav": "❤️ Favorite", "wager": "💵 Wagered", "payout": "💰 Gross payouts",
            "net": "📈 Net", "recent": "⏱️ آخر {m}m", "signal": "🧠 Playstyle signal", "avg": "💵 Avg / Max bet",
            "rate": "🎯 Recent win rate", "chase": "📈 Loss-chase signal", "streak": "📉 Current loss streak", "tempo": "⏱️ Tempo",
            "fair": "🔒 ملاحظة Fairness", "fairv": "هاد القراءة غير analytics/anti-bot. **RTP، RNG وPayout tables ما كيتبدلوش حسب اللاعب.**",
        },
        "en": {
            "desc": "Analytics profile only; it **never changes odds or payouts**.", "rounds": "🎮 All-time rounds",
            "wl": "🏆 W/L", "fav": "❤️ Favorite", "wager": "💵 Wagered", "payout": "💰 Gross payouts",
            "net": "📈 Net", "recent": "⏱️ Last {m}m", "signal": "🧠 Playstyle signal", "avg": "💵 Avg / Max bet",
            "rate": "🎯 Recent win rate", "chase": "📈 Loss-chase signal", "streak": "📉 Current loss streak", "tempo": "⏱️ Tempo",
            "fair": "🔒 Fairness note", "fairv": "This reading is analytics/anti-bot only. **RTP, RNG and payout tables never change by player.**",
        },
        "fr": {
            "desc": "Profil analytique uniquement ; il **ne modifie jamais les probabilités ni les paiements**.", "rounds": "🎮 Parties totales",
            "wl": "🏆 G/P", "fav": "❤️ Favori", "wager": "💵 Mises", "payout": "💰 Paiements bruts",
            "net": "📈 Net", "recent": "⏱️ Dernières {m} min", "signal": "🧠 Style de jeu", "avg": "💵 Mise moy. / max",
            "rate": "🎯 Taux de victoire récent", "chase": "📈 Signal de poursuite des pertes", "streak": "📉 Série de pertes actuelle", "tempo": "⏱️ Rythme",
            "fair": "🔒 Note d'équité", "fairv": "Cette lecture sert uniquement à analytics/anti-bot. **RTP, RNG et tables de paiement ne changent jamais selon le joueur.**",
        },
    }
    t = labels.get(lang, labels["darija"])
    embed = discord.Embed(title=f"📊 Casino Profile — {user.display_name}", description=t["desc"], color=discord.Color.blurple())
    embed.add_field(name=t["rounds"], value=f"**{total_rounds:,}**", inline=True)
    embed.add_field(name=t["wl"], value=f"**{wins:,} / {losses:,}**", inline=True)
    embed.add_field(name=t["fav"], value=(f"{fav_meta['emoji']} {fav_meta['label']}" if fav_meta else "—"), inline=True)
    embed.add_field(name=t["wager"], value=f"**{cfg.fmt_money(total_wagered)}**", inline=True)
    embed.add_field(name=t["payout"], value=f"**{cfg.fmt_money(total_won)}**", inline=True)
    embed.add_field(name=t["net"], value=f"**{cfg.fmt_money(total_won-total_wagered, signed=True)}**", inline=True)
    embed.add_field(name=t["recent"].format(m=getattr(cfg, 'CASINO_PROFILE_WINDOW_MINUTES', 30)), value=f"{n} rounds • {cfg.fmt_money(recent_wager)} wagered • {cfg.fmt_money(recent_net, signed=True)} net", inline=False)
    embed.add_field(name=t["signal"], value=behavior["signal"], inline=True)
    embed.add_field(name=t["avg"], value=f"{cfg.fmt_money(behavior['avg_bet'])} / {cfg.fmt_money(behavior['max_bet'])}", inline=True)
    embed.add_field(name=t["rate"], value=f"{behavior['win_rate']:.1f}%", inline=True)
    embed.add_field(name=t["chase"], value=f"{behavior['chase_count']} escalations after losses", inline=True)
    embed.add_field(name=t["streak"], value=f"{behavior['loss_streak']} rounds", inline=True)
    embed.add_field(name=t["tempo"], value=behavior["tempo"], inline=True)
    embed.add_field(name=t["fair"], value=t["fairv"], inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    return embed


class CasinoLanguageSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, *, row: int = 1):
        self.bot = bot
        options = [
            discord.SelectOption(label="Darija", value="darija", emoji="🇲🇦", description="اللغة الأساسية"),
            discord.SelectOption(label="English", value="en", emoji="🇬🇧", description="English interface"),
            discord.SelectOption(label="Français", value="fr", emoji="🇫🇷", description="Interface française"),
        ]
        super().__init__(
            placeholder="🌍 Darija • English • Français",
            options=options,
            min_values=1,
            max_values=1,
            custom_id="ggmw9:casino:language",
            row=row,
        )

    async def callback(self, interaction: discord.Interaction):
        lang = _set_lang(self.bot, interaction.guild.id, interaction.user.id, self.values[0])
        await _upsert(
            interaction,
            "casino",
            embed=build_session_menu_embed(self.bot, interaction.guild, interaction.user, lang),
            view=GamblingMenuView(self.bot, interaction.user, lang=lang),
        )


class GamblingPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
        self.add_item(CasinoLanguageSelect(bot, row=1))

    def _user_lang(self, interaction: discord.Interaction) -> str:
        return _lang(self.bot, interaction.guild.id, interaction.user.id)

    @discord.ui.button(label="🎰 Play", style=discord.ButtonStyle.success, custom_id="ggmw9:gambling_panel:open", row=0)
    async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self._user_lang(interaction)
        await _upsert(
            interaction, "casino",
            embed=build_session_menu_embed(self.bot, interaction.guild, interaction.user, lang),
            view=GamblingMenuView(self.bot, interaction.user, lang=lang),
        )

    @discord.ui.button(label="💵 Wallet", style=discord.ButtonStyle.secondary, custom_id="ggmw9:gambling_panel:balance", row=0)
    async def balance_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        eco = self.bot.get_cog("Economy")
        lang = self._user_lang(interaction)
        if not eco:
            await interaction.response.send_message(_casino_text(lang, "unavailable"), ephemeral=True)
            return
        embed = discord.Embed(
            title=_casino_text(lang, "wallet_title"),
            description=_casino_text(
                lang, "wallet_line",
                wallet=cfg.fmt_money(eco.get_balance(interaction.guild.id, interaction.user.id)),
                bank=cfg.fmt_money(eco.get_bank_balance(interaction.guild.id, interaction.user.id)),
                daily=cfg.fmt_money(eco.daily_remaining(interaction.guild.id, interaction.user.id)),
            ),
            color=discord.Color.blurple(),
        )
        await _upsert(interaction, "casino", embed=embed, view=CasinoInfoBackView(self.bot, interaction.user, lang))

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.secondary, custom_id="ggmw9:gambling_panel:stats", row=0)
    async def stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self._user_lang(interaction)
        embeds = [c.build_stats_embed(interaction.guild, interaction.user) for n in ("Dice", "Coinflip", "Slots", "Scratch", "Lottery") if (c := self.bot.get_cog(n))]
        if not embeds:
            embeds = [discord.Embed(description=_casino_text(lang, "stats_none"), color=discord.Color.blurple())]
        await _upsert(interaction, "casino", embeds=embeds, view=CasinoInfoBackView(self.bot, interaction.user, lang))

    @discord.ui.button(label="🧠 Profile", style=discord.ButtonStyle.primary, custom_id="ggmw9:gambling_panel:profile", row=0)
    async def profile_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self._user_lang(interaction)
        await _upsert(interaction, "casino", embed=build_profile_embed(self.bot, interaction.guild, interaction.user, lang), view=CasinoInfoBackView(self.bot, interaction.user, lang))

    @discord.ui.button(label="🛡️ Fairness", style=discord.ButtonStyle.primary, custom_id="ggmw9:gambling_panel:fairness", row=0)
    async def fairness_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        lang = self._user_lang(interaction)
        await _upsert(interaction, "casino", embed=build_fairness_embed(lang), view=CasinoInfoBackView(self.bot, interaction.user, lang))


class CasinoInfoBackView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.abc.User, lang: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.lang = lang
        label = {"darija": "رجع للـCasino", "en": "Back to Casino", "fr": "Retour au Casino"}.get(lang, "رجع للـCasino")
        b = discord.ui.Button(label=label, emoji="↩️", style=discord.ButtonStyle.secondary)
        b.callback = self.back
        self.add_item(b)

    async def back(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_casino_text(self.lang, "not_yours"), ephemeral=True)
            return
        await interaction.response.edit_message(
            content=None,
            embed=build_session_menu_embed(self.bot, interaction.guild, self.user, self.lang),
            view=GamblingMenuView(self.bot, self.user, lang=self.lang),
        )


class GameSwitchSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, user: discord.abc.User, *, row: int = 0, lang: str | None = None):
        self.bot = bot
        self.user = user
        guild_id = getattr(getattr(user, "guild", None), "id", 0)
        self.lang = lang or _lang(bot, guild_id, user.id)
        options = [
            discord.SelectOption(
                label=g["label"], value=g["id"], emoji=g["emoji"], description=_game_desc(g, self.lang)[:100]
            ) for g in GAMBLING_GAMES
        ]
        super().__init__(placeholder=_casino_text(self.lang, "choose"), min_values=1, max_values=1, options=options, row=row)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_casino_text(self.lang, "not_yours"), ephemeral=True)
            return
        game_id = self.values[0]
        cog = _game_cog(self.bot, game_id)
        eco = self.bot.get_cog("Economy")
        if not cog or not eco:
            await interaction.response.edit_message(
                content=None,
                embed=build_bet_error_embed(self.bot, interaction.guild, self.user, game_id, _casino_text(self.lang, "unavailable"), self.lang),
                view=BetRetryView(self.bot, self.user, game_id, lang=self.lang),
            )
            return
        if (interaction.guild.id, self.user.id) in getattr(cog, "active", set()):
            await interaction.response.edit_message(
                content=None,
                embed=build_bet_error_embed(self.bot, interaction.guild, self.user, game_id, _casino_text(self.lang, "active"), self.lang),
                view=BetRetryView(self.bot, self.user, game_id, lang=self.lang),
            )
            return
        await interaction.response.send_modal(GameBetModal(self.bot, self.user, game_id, lang=self.lang))


class GamblingMenuView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.abc.User, lang: str | None = None):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        guild_id = getattr(getattr(user, "guild", None), "id", 0)
        self.lang = lang or _lang(bot, guild_id, user.id)
        self.add_item(GameSwitchSelect(bot, user, row=0, lang=self.lang))


class BetRetryView(discord.ui.View):
    def __init__(self, bot, user, game_id, current_bet=None, lang: str | None = None):
        super().__init__(timeout=180)
        self.bot = bot
        self.user = user
        self.game_id = game_id
        self.current_bet = current_bet
        guild_id = getattr(getattr(user, "guild", None), "id", 0)
        self.lang = lang or _lang(bot, guild_id, user.id)
        self.add_item(GameSwitchSelect(bot, user, row=1, lang=self.lang))
        button = discord.ui.Button(label=_casino_text(self.lang, "enter_bet"), style=discord.ButtonStyle.success, row=0)
        button.callback = self.retry_bet
        self.add_item(button)

    async def retry_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_casino_text(self.lang, "not_yours"), ephemeral=True)
            return
        await interaction.response.send_modal(
            GameBetModal(self.bot, self.user, self.game_id, current_bet=self.current_bet, lang=self.lang)
        )


class GameBetModal(discord.ui.Modal):
    def __init__(self, bot, user, game_id, current_bet=None, lang: str | None = None):
        self.bot = bot
        self.user = user
        self.game_id = game_id
        self.current_bet = current_bet
        guild_id = getattr(getattr(user, "guild", None), "id", 0)
        self.lang = lang or _lang(bot, guild_id, user.id)
        meta = GAME_BY_ID[game_id]
        mn, mx = _limits(game_id)
        super().__init__(title=f"{meta['emoji']} {meta['label']} — Bet")
        gid = getattr(getattr(user, "guild", None), "id", 0)
        eff = effective_max_bet(bot, gid, user.id, game_id) if gid else mx
        shown_max = eff if eff > 0 else mx
        placeholder = (
            _casino_text(self.lang, "current_bet", bet=cfg.fmt_money(current_bet))
            if current_bet is not None else f"Allowed: {cfg.fmt_money(mn)} → {cfg.fmt_money(shown_max)}"
        )
        self.amount = discord.ui.TextInput(
            label=_casino_text(self.lang, "bet_label"), placeholder=placeholder,
            min_length=1, max_length=16, required=True,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_casino_text(self.lang, "not_yours"), ephemeral=True)
            return
        bet = cfg.parse_money_input(self.amount.value)
        if bet is None:
            await interaction.response.edit_message(
                content=None,
                embed=build_bet_error_embed(self.bot, interaction.guild, self.user, self.game_id, _casino_text(self.lang, "bad_amount"), self.lang),
                view=BetRetryView(self.bot, self.user, self.game_id, self.current_bet, self.lang),
            )
            return
        await start_game_with_bet(
            interaction, self.bot, self.user, self.game_id, bet, retry_bet=self.current_bet, lang=self.lang
        )


async def start_game_with_bet(interaction, bot, user, game_id, bet, *, retry_bet=None, lang: str | None = None):
    if lang is None:
        lang = _lang(bot, interaction.guild.id if interaction.guild else 0, user.id)
    mn, table_max = _limits(game_id)
    cog = _game_cog(bot, game_id)
    eco = bot.get_cog("Economy")
    if not cog or not eco:
        await interaction.response.edit_message(
            content=None,
            embed=build_bet_error_embed(bot, interaction.guild, user, game_id, _casino_text(lang, "unavailable"), lang),
            view=BetRetryView(bot, user, game_id, retry_bet, lang),
        )
        return
    allowed, rounds, limit = can_start_casino_round(bot, interaction.guild.id, user.id)
    if not allowed:
        guard = {
            "darija": f"⏳ وصلتي **{rounds}/{limit}** rounds. استنى حتى يخرج أقدم round من window.",
            "en": f"⏳ You reached **{rounds}/{limit}** rounds. Wait until the oldest round leaves the window.",
            "fr": f"⏳ Tu as atteint **{rounds}/{limit}** parties. Attends que la plus ancienne sorte de la fenêtre.",
        }[lang]
        await interaction.response.edit_message(content=None, embed=build_bet_error_embed(bot, interaction.guild, user, game_id, guard, lang), view=BetRetryView(bot, user, game_id, bet, lang))
        return
    eff = effective_max_bet(bot, interaction.guild.id, user.id, game_id)
    if bet < mn or bet > table_max or bet > eff:
        reason = build_bet_limit_error(bot, interaction.guild, user, game_id, bet, lang)
        await interaction.response.edit_message(content=None, embed=build_bet_error_embed(bot, interaction.guild, user, game_id, reason, lang), view=BetRetryView(bot, user, game_id, bet, lang))
        return
    key = (interaction.guild.id, user.id)
    if key in getattr(cog, "active", set()):
        await interaction.response.edit_message(content=None, embed=build_bet_error_embed(bot, interaction.guild, user, game_id, _casino_text(lang, "active"), lang), view=BetRetryView(bot, user, game_id, bet, lang))
        return
    wallet = eco.get_balance(interaction.guild.id, user.id)
    if wallet < bet:
        await interaction.response.edit_message(content=None, embed=build_bet_error_embed(bot, interaction.guild, user, game_id, _casino_text(lang, "need", amount=cfg.fmt_money(bet-wallet)), lang), view=BetRetryView(bot, user, game_id, bet, lang))
        return

    if game_id == "dice":
        from cogs.game_dice import RiskView
        embed = discord.Embed(
            title="🎲 Dice — Risk",
            description=f"Bet: **{cfg.fmt_money(bet)}**\n{_casino_text(lang, 'risk')}",
            color=discord.Color.blurple(),
        )
        for lvl in cfg.DICE_RISK_LEVELS.values():
            chance = (21 - int(lvl["threshold"])) / 20 * 100
            embed.add_field(name=lvl["label"], value=f"Win **{chance:.0f}%** • ×{lvl['multiplier']}", inline=True)
        await interaction.response.edit_message(content=None, embed=embed, view=RiskView(cog, user, bet))
        return
    if game_id == "coinflip":
        from cogs.game_coinflip import SideView
        embed = discord.Embed(
            title="🪙 Coinflip — Side",
            description=f"Bet: **{cfg.fmt_money(bet)}**\nChance **50%** • payout **×{cfg.COINFLIP_PAYOUT_MULTIPLIER}**",
            color=discord.Color.blurple(),
        )
        await interaction.response.edit_message(content=None, embed=embed, view=SideView(cog, user, bet))
        return

    if not eco.spend(interaction.guild.id, user.id, bet):
        await interaction.response.edit_message(content=None, embed=build_bet_error_embed(bot, interaction.guild, user, game_id, _casino_text(lang, "wallet_changed"), lang), view=BetRetryView(bot, user, game_id, bet, lang))
        return
    cog.active.add(key)
    if game_id == "slots":
        from cogs.game_slots import _spinning_embed, _play_out
        await interaction.response.edit_message(content=None, embed=_spinning_embed(bet), view=None)
        msg = await interaction.original_response()
        await _play_out(cog, msg, interaction.guild.id, user, bet)
        return
    if game_id == "scratch":
        from cogs.game_scratch import _card_embed, _play_out
        await interaction.response.edit_message(content=None, embed=_card_embed(bet), view=None)
        msg = await interaction.original_response()
        await _play_out(cog, msg, interaction.guild.id, user, bet)
        return
    if game_id == "lottery":
        from cogs.game_lottery import _resolve, _ticket_embed, _play_out
        result = _resolve(bet)
        await interaction.response.edit_message(content=None, embed=_ticket_embed(bet, result["ticket"]), view=None)
        msg = await interaction.original_response()
        await _play_out(cog, msg, interaction.guild.id, user, bet, result)
        return


class GamblingRoundControls(discord.ui.View):
    def __init__(self, bot, user, game_id, last_bet, lang: str | None = None):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.game_id = game_id
        self.last_bet = int(last_bet)
        guild_id = getattr(getattr(user, "guild", None), "id", 0)
        self.lang = lang or _lang(bot, guild_id, user.id)
        same = discord.ui.Button(label=_casino_text(self.lang, "same_bet"), style=discord.ButtonStyle.success, row=0)
        same.callback = self.replay_same
        self.add_item(same)
        change = discord.ui.Button(label=_casino_text(self.lang, "change_bet"), style=discord.ButtonStyle.primary, row=0)
        change.callback = self.change_bet
        self.add_item(change)
        self.add_item(GameSwitchSelect(bot, user, row=1, lang=self.lang))

    async def replay_same(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_casino_text(self.lang, "not_yours"), ephemeral=True)
            return
        await start_game_with_bet(interaction, self.bot, self.user, self.game_id, self.last_bet, retry_bet=self.last_bet, lang=self.lang)

    async def change_bet(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(_casino_text(self.lang, "not_yours"), ephemeral=True)
            return
        await interaction.response.send_modal(GameBetModal(self.bot, self.user, self.game_id, current_bet=self.last_bet, lang=self.lang))


class GamblingPanel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.add_view(GamblingPanelView(self.bot))
        print("✅ [CASINO] Multilang persistent panel registered.")

    @commands.Cog.listener()
    async def on_ready(self):
        if not cfg.GAMBLING_CHANNEL_ID:
            return
        channel = self.bot.get_channel(cfg.GAMBLING_CHANNEL_ID)
        if not channel:
            return
        embed = self.build_public_panel_embed("darija")
        matches = []
        try:
            async for msg in channel.history(limit=60):
                if msg.author == self.bot.user and msg.embeds and any(x in (msg.embeds[0].title or "") for x in ("قمار", "Casino")):
                    matches.append(msg)
        except discord.Forbidden:
            return
        try:
            if matches:
                keep = matches[0]
                await keep.edit(embed=embed, view=GamblingPanelView(self.bot))
                for old in matches[1:]:
                    try:
                        await old.delete()
                    except (discord.Forbidden, discord.NotFound, discord.HTTPException):
                        pass
            else:
                await channel.send(embed=embed, view=GamblingPanelView(self.bot))
        except (discord.Forbidden, discord.HTTPException):
            pass

    def build_public_panel_embed(self, lang: str = "darija"):
        # Public shared panel stays Darija by default. Language choice opens a personal localized session.
        embed = discord.Embed(
            title="🎰 GGMW9 Casino",
            description=_casino_text(lang, "public_desc"),
            color=discord.Color.gold(),
            timestamp=datetime.now(),
        )
        embed.add_field(name="🎮 Games", value="\n".join(f"{g['emoji']} **{g['label']}** — {_game_desc(g, lang)}" for g in GAMBLING_GAMES), inline=False)
        embed.add_field(name="💵 Table limits", value="\n".join(f"{g['emoji']} {cfg.fmt_money(_limits(g['id'])[0])} → {cfg.fmt_money(_limits(g['id'])[1])}" for g in GAMBLING_GAMES), inline=True)
        embed.add_field(name=_casino_text(lang, "protection"), value=f"Per bet max **{getattr(cfg,'CASINO_MAX_BET_WALLET_PERCENT',10)}% Wallet**\nMax **{getattr(cfg,'CASINO_MAX_ROUNDS_30M',60)} rounds/30m**", inline=True)
        embed.add_field(name="🛡️ Fairness", value=_casino_text(lang, "fairness_help"), inline=False)
        embed.add_field(name=_casino_text(lang, "langs"), value=_casino_text(lang, "langs_value"), inline=False)
        embed.set_footer(text="GGMW9 Fair Casino • USD • no personalized rigging")
        return embed

    async def _send_panel(self, channel):
        await channel.send(embed=self.build_public_panel_embed("darija"), view=GamblingPanelView(self.bot))

    @commands.command(name="gamblingpanel", hidden=True)
    @commands.has_permissions(administrator=True)
    async def gamblingpanel_cmd(self, ctx):
        await self._send_panel(ctx.channel)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamblingPanel(bot))
