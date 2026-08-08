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
    {"id":"dice","emoji":"🎲","label":"Dice","desc":"d20 بثلاث مستويات مخاطرة ثابتة","cog":"Dice","min_attr":"DICE_MIN_BET","max_attr":"DICE_MAX_BET"},
    {"id":"coinflip","emoji":"🪙","label":"Coinflip","desc":"50/50 بPayout ثابت","cog":"Coinflip","min_attr":"COINFLIP_MIN_BET","max_attr":"COINFLIP_MAX_BET"},
    {"id":"slots","emoji":"🎰","label":"Slots","desc":"Weighted reels + Progressive Jackpot","cog":"Slots","min_attr":"SLOTS_MIN_BET","max_attr":"SLOTS_MAX_BET"},
    {"id":"scratch","emoji":"🎫","label":"Scratch Card","desc":"Fixed outcome table، ماكاينش accidental 3-match","cog":"Scratch","min_attr":"SCRATCH_MIN_BET","max_attr":"SCRATCH_MAX_BET"},
    {"id":"lottery","emoji":"🎟️","label":"Lottery","desc":"4 أرقام + Jackpot على 4/4","cog":"Lottery","min_attr":"LOTTERY_MIN_BET","max_attr":"LOTTERY_MAX_BET"},
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


def build_session_menu_embed(bot: commands.Bot, guild: discord.Guild, user: discord.abc.User):
    eco = bot.get_cog("Economy")
    wallet = eco.get_balance(guild.id, user.id) if eco else 0
    ok, rounds, limit = can_start_casino_round(bot, guild.id, user.id)
    embed = discord.Embed(
        title="🎰 GGMW9 Casino — Fair Session",
        description=(
            f"💳 Wallet: **{cfg.fmt_money(wallet)}**\n"
            f"🧾 Activity: **{rounds}/{limit} rounds** فآخر {getattr(cfg,'CASINO_PROFILE_WINDOW_MINUTES',30)} دقيقة\n\n"
            "اختار اللعبة، كتب الرهان بالدولار، ومن بعد كل Result تقدر تعاود أو تبدل اللعبة.\n"
            "🔒 **Odds ثابتة على الجميع**؛ Player Profile كيقرا السلوك غير للـanalytics/anti-bot وما كيبدلش RNG."
        ),
        color=discord.Color.gold(),
    )
    lines=[]
    for g in GAMBLING_GAMES:
        mn,mx=_limits(g["id"])
        eff=effective_max_bet(bot,guild.id,user.id,g["id"])
        lines.append(f"{g['emoji']} **{g['label']}** — {cfg.fmt_money(mn)} → {cfg.fmt_money(mx)} • your max {cfg.fmt_money(eff)}")
    embed.add_field(name="🎮 Tables", value="\n".join(lines), inline=False)
    if not ok:
        embed.add_field(name="⏳ Session Guard", value="وصلتي حد الجولات فـ30 دقيقة. استنى شوية؛ Odds ما تبدلوش.", inline=False)
    return embed


def build_bet_error_embed(bot: commands.Bot, guild: discord.Guild, user: discord.abc.User, game_id: str, text: str):
    meta = GAME_BY_ID[game_id]
    min_bet, table_max = _limits(game_id)
    eff = effective_max_bet(bot, guild.id, user.id, game_id)
    return discord.Embed(
        title=f"{meta['emoji']} {meta['label']} — Bet",
        description=(
            f"{text}\n\nTable: **{cfg.fmt_money(min_bet)} → {cfg.fmt_money(table_max)}**\n"
            f"Bankroll max ديالك دابا: **{cfg.fmt_money(eff)}**\n"
            f"(max {getattr(cfg,'CASINO_MAX_BET_WALLET_PERCENT',10)}% من Wallet، مع minimum table bet)"
        ),
        color=discord.Color.red(),
    )


def build_fairness_embed() -> discord.Embed:
    rtp = cfg.CASINO_RTP
    embed = discord.Embed(
        title="🛡️ Casino Fairness & RTP",
        description=(
            f"**{getattr(cfg,'CASINO_FAIRNESS_VERSION','GGMW9 Fair RNG')}**\n\n"
            "✅ نفس Odds لكل عضو، مهما كان رابح ولا خاسر.\n"
            "✅ RNG من SystemRandom/OS entropy فالألعاب.\n"
            "✅ البوت يقدر يقرا rounds / turnover / favorite game للـProfile والـanti-bot فقط.\n"
            "❌ ماكاينش adaptive rigging، loss chasing، ولا تغيير سري للفرص."
        ), color=discord.Color.green()
    )
    embed.add_field(name="🪙 Coinflip", value=f"RTP **{rtp['coinflip']:.2f}%** • Edge **{100-rtp['coinflip']:.2f}%**", inline=True)
    embed.add_field(name="🎲 Dice Low", value=f"RTP **{rtp['dice_low']:.2f}%** • Edge **{100-rtp['dice_low']:.2f}%**", inline=True)
    embed.add_field(name="🎲 Dice Medium", value=f"RTP **{rtp['dice_medium']:.2f}%** • Edge **{100-rtp['dice_medium']:.2f}%**", inline=True)
    embed.add_field(name="🎲 Dice High", value=f"RTP **{rtp['dice_high']:.2f}%** • Edge **{100-rtp['dice_high']:.2f}%**", inline=True)
    embed.add_field(name="🎰 Slots", value=f"RTP ≈ **{rtp['slots']:.2f}%** • Edge ≈ **{100-rtp['slots']:.2f}%**", inline=True)
    embed.add_field(name="🎫 Scratch", value=f"RTP **{rtp['scratch']:.2f}%** • Edge **{100-rtp['scratch']:.2f}%**", inline=True)
    embed.add_field(name="🎟️ Lottery", value=f"Base RTP ≈ **{rtp['lottery']:.2f}%** + funded Jackpot", inline=True)
    embed.set_footer(text="RTP هو long-run theoretical return، ماشي ضمان ديال أي session قصيرة")
    return embed


def build_profile_embed(bot: commands.Bot, guild: discord.Guild, user: discord.Member) -> discord.Embed:
    rows=[]
    total_wagered=total_won=total_rounds=wins=losses=0
    counts=Counter()
    for g in GAMBLING_GAMES:
        cog=_game_cog(bot,g["id"])
        if not cog:
            continue
        s=cog.stats(guild.id,user.id)
        r=int(s.get("wins",0))+int(s.get("losses",0))
        total_rounds+=r; wins+=int(s.get("wins",0)); losses+=int(s.get("losses",0))
        total_wagered+=int(s.get("wagered",0)); total_won+=int(s.get("won",0)); counts[g["id"]]+=r
    recent=recent_casino_activity(bot,guild.id,user.id)
    recent_wager=sum(int(r.get("bet",0)) for r in recent)
    recent_net=sum(int(r.get("payout",0))-int(r.get("bet",0)) for r in recent)
    behavior=analyze_recent_play(recent)
    favorite=counts.most_common(1)[0][0] if counts else None
    fav_meta=GAME_BY_ID.get(favorite)
    n=len(recent)
    embed=discord.Embed(
        title=f"📊 Casino Profile — {user.display_name}",
        description="Profile تحليلي فقط؛ **ما كيبدلش Odds ولا Payouts**.",
        color=discord.Color.blurple(),
    )
    embed.add_field(name="🎮 All-time rounds", value=f"**{total_rounds:,}**", inline=True)
    embed.add_field(name="🏆 W/L", value=f"**{wins:,} / {losses:,}**", inline=True)
    embed.add_field(name="❤️ Favorite", value=(f"{fav_meta['emoji']} {fav_meta['label']}" if fav_meta else "—"), inline=True)
    embed.add_field(name="💵 Wagered", value=f"**{cfg.fmt_money(total_wagered)}**", inline=True)
    embed.add_field(name="💰 Gross payouts", value=f"**{cfg.fmt_money(total_won)}**", inline=True)
    embed.add_field(name="📈 Net", value=f"**{cfg.fmt_money(total_won-total_wagered, signed=True)}**", inline=True)
    embed.add_field(name=f"⏱️ Last {getattr(cfg,'CASINO_PROFILE_WINDOW_MINUTES',30)}m", value=f"{n} rounds • {cfg.fmt_money(recent_wager)} wagered • {cfg.fmt_money(recent_net, signed=True)} net", inline=False)
    embed.add_field(name="🧠 Playstyle signal", value=behavior["signal"], inline=True)
    embed.add_field(name="💵 Avg / Max bet", value=f"{cfg.fmt_money(behavior['avg_bet'])} / {cfg.fmt_money(behavior['max_bet'])}", inline=True)
    embed.add_field(name="🎯 Recent win rate", value=f"{behavior['win_rate']:.1f}%", inline=True)
    embed.add_field(name="📈 Loss-chase signal", value=f"{behavior['chase_count']} escalations after losses", inline=True)
    embed.add_field(name="📉 Current loss streak", value=f"{behavior['loss_streak']} rounds", inline=True)
    embed.add_field(name="⏱️ Tempo", value=behavior["tempo"], inline=True)
    embed.add_field(name="🔒 Fairness note", value="هاد القراءة غير analytics/anti-bot. **RTP، RNG وPayout tables ما كيتبدلوش حسب اللاعب.**", inline=False)
    embed.set_thumbnail(url=user.display_avatar.url)
    return embed


class GamblingPanelView(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None); self.bot=bot

    @discord.ui.button(label="🎰 Play", style=discord.ButtonStyle.success, custom_id="ggmw9:gambling_panel:open", row=0)
    async def open_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_session_menu_embed(self.bot,interaction.guild,interaction.user), view=GamblingMenuView(self.bot,interaction.user), ephemeral=True)

    @discord.ui.button(label="💵 Wallet", style=discord.ButtonStyle.secondary, custom_id="ggmw9:gambling_panel:balance", row=0)
    async def balance_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        eco=self.bot.get_cog("Economy")
        if not eco:
            await interaction.response.send_message("❌ Economy ماشي محمّلة.",ephemeral=True); return
        await interaction.response.send_message(
            f"💳 Wallet: **{cfg.fmt_money(eco.get_balance(interaction.guild.id,interaction.user.id))}**\n"
            f"🏦 Savings: **{cfg.fmt_money(eco.get_bank_balance(interaction.guild.id,interaction.user.id))}**\n"
            f"🎮 Non-casino daily reward room: **{cfg.fmt_money(eco.daily_remaining(interaction.guild.id,interaction.user.id))}**",
            ephemeral=True,
        )

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.secondary, custom_id="ggmw9:gambling_panel:stats", row=0)
    async def stats_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embeds=[c.build_stats_embed(interaction.guild,interaction.user) for n in ("Dice","Coinflip","Slots","Scratch","Lottery") if (c:=self.bot.get_cog(n))]
        await interaction.response.send_message(embeds=embeds or [discord.Embed(description="No casino stats yet")],ephemeral=True)

    @discord.ui.button(label="🧠 Profile", style=discord.ButtonStyle.primary, custom_id="ggmw9:gambling_panel:profile", row=0)
    async def profile_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_profile_embed(self.bot,interaction.guild,interaction.user),ephemeral=True)

    @discord.ui.button(label="🛡️ Fairness", style=discord.ButtonStyle.primary, custom_id="ggmw9:gambling_panel:fairness", row=0)
    async def fairness_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(embed=build_fairness_embed(),ephemeral=True)


class GameSwitchSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, user: discord.abc.User, *, row:int=0):
        self.bot=bot; self.user=user
        options=[discord.SelectOption(label=g["label"],value=g["id"],emoji=g["emoji"],description=g["desc"][:100]) for g in GAMBLING_GAMES]
        super().__init__(placeholder="🎮 اختار Casino game...",min_values=1,max_values=1,options=options,row=row)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ هاد Session ماشي ديالك.",ephemeral=True); return
        game_id=self.values[0]; cog=_game_cog(self.bot,game_id); eco=self.bot.get_cog("Economy")
        if not cog or not eco:
            await interaction.response.edit_message(content=None,embed=build_bet_error_embed(self.bot,interaction.guild,self.user,game_id,"❌ اللعبة/Economy ماشي متوفرة."),view=BetRetryView(self.bot,self.user,game_id)); return
        if (interaction.guild.id,self.user.id) in getattr(cog,"active",set()):
            await interaction.response.edit_message(content=None,embed=build_bet_error_embed(self.bot,interaction.guild,self.user,game_id,"❌ عندك round خدامة."),view=BetRetryView(self.bot,self.user,game_id)); return
        await interaction.response.send_modal(GameBetModal(self.bot,self.user,game_id))


class GamblingMenuView(discord.ui.View):
    def __init__(self, bot: commands.Bot, user: discord.abc.User):
        super().__init__(timeout=300); self.bot=bot; self.user=user; self.add_item(GameSwitchSelect(bot,user,row=0))


class BetRetryView(discord.ui.View):
    def __init__(self, bot, user, game_id, current_bet=None):
        super().__init__(timeout=180); self.bot=bot; self.user=user; self.game_id=game_id; self.current_bet=current_bet; self.add_item(GameSwitchSelect(bot,user,row=1))

    @discord.ui.button(label="💵 دخل الرهان",style=discord.ButtonStyle.success,row=0)
    async def retry_bet(self,interaction,button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.",ephemeral=True); return
        await interaction.response.send_modal(GameBetModal(self.bot,self.user,self.game_id,current_bet=self.current_bet))


class GameBetModal(discord.ui.Modal):
    def __init__(self, bot, user, game_id, current_bet=None):
        self.bot=bot; self.user=user; self.game_id=game_id; self.current_bet=current_bet
        meta=GAME_BY_ID[game_id]; mn,mx=_limits(game_id)
        super().__init__(title=f"{meta['emoji']} {meta['label']} — Bet")
        self.amount=discord.ui.TextInput(
            label="Bet بالدولار",
            placeholder=(f"Current {cfg.fmt_money(current_bet)} — كتب الجديد" if current_bet is not None else f"{cfg.fmt_money(mn)} → {cfg.fmt_money(mx)}"),
            min_length=1,max_length=16,required=True,
        ); self.add_item(self.amount)

    async def on_submit(self,interaction):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.",ephemeral=True); return
        bet=cfg.parse_money_input(self.amount.value)
        if bet is None:
            await interaction.response.edit_message(content=None,embed=build_bet_error_embed(self.bot,interaction.guild,self.user,self.game_id,"❌ دخل مبلغ بحال `5` أو `5.50`."),view=BetRetryView(self.bot,self.user,self.game_id,self.current_bet)); return
        await start_game_with_bet(interaction,self.bot,self.user,self.game_id,bet,retry_bet=self.current_bet)


async def start_game_with_bet(interaction, bot, user, game_id, bet, *, retry_bet=None):
    meta=GAME_BY_ID[game_id]; mn,table_max=_limits(game_id); cog=_game_cog(bot,game_id); eco=bot.get_cog("Economy")
    if not cog or not eco:
        await interaction.response.edit_message(content=None,embed=build_bet_error_embed(bot,interaction.guild,user,game_id,"❌ اللعبة/Economy ماشي متوفرة."),view=BetRetryView(bot,user,game_id,retry_bet)); return
    allowed,rounds,limit=can_start_casino_round(bot,interaction.guild.id,user.id)
    if not allowed:
        await interaction.response.edit_message(content=None,embed=build_bet_error_embed(bot,interaction.guild,user,game_id,f"⏳ وصلتي **{rounds}/{limit}** rounds فآخر 30 دقيقة. استنى حتى يخرج أقدم round من window."),view=BetRetryView(bot,user,game_id,bet)); return
    eff=effective_max_bet(bot,interaction.guild.id,user.id,game_id)
    if bet < mn or bet > table_max or bet > eff:
        await interaction.response.edit_message(content=None,embed=build_bet_error_embed(bot,interaction.guild,user,game_id,f"❌ Bet **{cfg.fmt_money(bet)}** خارج limit ديالك."),view=BetRetryView(bot,user,game_id,bet)); return
    key=(interaction.guild.id,user.id)
    if key in getattr(cog,"active",set()):
        await interaction.response.edit_message(content=None,embed=build_bet_error_embed(bot,interaction.guild,user,game_id,"❌ عندك round خدامة."),view=BetRetryView(bot,user,game_id,bet)); return
    wallet=eco.get_balance(interaction.guild.id,user.id)
    if wallet < bet:
        await interaction.response.edit_message(content=None,embed=build_bet_error_embed(bot,interaction.guild,user,game_id,f"❌ ناقصك **{cfg.fmt_money(bet-wallet)}**."),view=BetRetryView(bot,user,game_id,bet)); return

    if game_id=="dice":
        from cogs.game_dice import RiskView
        embed=discord.Embed(title="🎲 Dice — Risk",description=f"Bet: **{cfg.fmt_money(bet)}**\nFixed odds؛ اختار risk.",color=discord.Color.blurple())
        for lvl in cfg.DICE_RISK_LEVELS.values():
            chance=(21-int(lvl["threshold"]))/20*100
            embed.add_field(name=lvl["label"],value=f"Win **{chance:.0f}%** • ×{lvl['multiplier']}",inline=True)
        await interaction.response.edit_message(content=None,embed=embed,view=RiskView(cog,user,bet)); return
    if game_id=="coinflip":
        from cogs.game_coinflip import SideView
        embed=discord.Embed(title="🪙 Coinflip — Side",description=f"Bet: **{cfg.fmt_money(bet)}**\nChance **50%** • payout **×{cfg.COINFLIP_PAYOUT_MULTIPLIER}**",color=discord.Color.blurple())
        await interaction.response.edit_message(content=None,embed=embed,view=SideView(cog,user,bet)); return

    if not eco.spend(interaction.guild.id,user.id,bet):
        await interaction.response.edit_message(content=None,embed=build_bet_error_embed(bot,interaction.guild,user,game_id,"❌ Wallet تبدلت وما بقاتش كافية."),view=BetRetryView(bot,user,game_id,bet)); return
    cog.active.add(key)
    if game_id=="slots":
        from cogs.game_slots import _spinning_embed,_play_out
        await interaction.response.edit_message(content=None,embed=_spinning_embed(bet),view=None); msg=await interaction.original_response(); await _play_out(cog,msg,interaction.guild.id,user,bet); return
    if game_id=="scratch":
        from cogs.game_scratch import _card_embed,_play_out
        await interaction.response.edit_message(content=None,embed=_card_embed(bet),view=None); msg=await interaction.original_response(); await _play_out(cog,msg,interaction.guild.id,user,bet); return
    if game_id=="lottery":
        from cogs.game_lottery import _resolve,_ticket_embed,_play_out
        result=_resolve(bet); await interaction.response.edit_message(content=None,embed=_ticket_embed(bet,result["ticket"]),view=None); msg=await interaction.original_response(); await _play_out(cog,msg,interaction.guild.id,user,bet,result); return


class GamblingRoundControls(discord.ui.View):
    def __init__(self, bot, user, game_id, last_bet):
        super().__init__(timeout=300); self.bot=bot; self.user=user; self.game_id=game_id; self.last_bet=int(last_bet); self.add_item(GameSwitchSelect(bot,user,row=1))

    @discord.ui.button(label="🔄 نفس الرهان",style=discord.ButtonStyle.success,row=0)
    async def replay_same(self,interaction,button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.",ephemeral=True); return
        await start_game_with_bet(interaction,self.bot,self.user,self.game_id,self.last_bet,retry_bet=self.last_bet)

    @discord.ui.button(label="💵 بدل الرهان",style=discord.ButtonStyle.primary,row=0)
    async def change_bet(self,interaction,button):
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ ماشي ديالك.",ephemeral=True); return
        await interaction.response.send_modal(GameBetModal(self.bot,self.user,self.game_id,current_bet=self.last_bet))


class GamblingPanel(commands.Cog):
    def __init__(self,bot): self.bot=bot

    async def cog_load(self):
        self.bot.add_view(GamblingPanelView(self.bot)); print("✅ [CASINO] Fair persistent panel registered.")

    @commands.Cog.listener()
    async def on_ready(self):
        if not cfg.GAMBLING_CHANNEL_ID: return
        channel=self.bot.get_channel(cfg.GAMBLING_CHANNEL_ID)
        if not channel: return
        embed=self.build_public_panel_embed()
        found=None
        try:
            async for msg in channel.history(limit=30):
                if msg.author==self.bot.user and msg.embeds and any(x in (msg.embeds[0].title or "") for x in ("قمار","Casino")):
                    found=msg; break
        except discord.Forbidden: return
        try:
            if found: await found.edit(embed=embed,view=GamblingPanelView(self.bot))
            else: await channel.send(embed=embed,view=GamblingPanelView(self.bot))
        except (discord.Forbidden,discord.HTTPException): pass

    def build_public_panel_embed(self):
        embed=discord.Embed(
            title="🎰 GGMW9 Casino",
            description=(
                "Casino صعيب، شفاف وعادل: **fixed odds للجميع** + progressive jackpot + bankroll/session protection.\n"
                "الأرباح ديال Casino ما داخلاش فـDaily mini-game cap."
            ), color=discord.Color.gold(), timestamp=datetime.now()
        )
        embed.add_field(name="🎮 Games",value="\n".join(f"{g['emoji']} **{g['label']}** — {g['desc']}" for g in GAMBLING_GAMES),inline=False)
        embed.add_field(name="💵 Table limits",value="\n".join(f"{g['emoji']} {cfg.fmt_money(_limits(g['id'])[0])} → {cfg.fmt_money(_limits(g['id'])[1])}" for g in GAMBLING_GAMES),inline=True)
        embed.add_field(name="🧠 Protection",value=f"Per bet max **{getattr(cfg,'CASINO_MAX_BET_WALLET_PERCENT',10)}% Wallet**\nMax **{getattr(cfg,'CASINO_MAX_ROUNDS_30M',60)} rounds/30m**",inline=True)
        embed.add_field(name="🛡️ Fairness",value="ضغط **Fairness** باش تشوف RTP/House Edge. Player Profile ما كيغيّرش RNG.",inline=False)
        embed.set_footer(text="GGMW9 Fair Casino • USD • no personalized rigging")
        return embed

    async def _send_panel(self,channel):
        await channel.send(embed=self.build_public_panel_embed(),view=GamblingPanelView(self.bot))

    @commands.command(name="gamblingpanel",hidden=True)
    @commands.has_permissions(administrator=True)
    async def gamblingpanel_cmd(self,ctx):
        await self._send_panel(ctx.channel)


async def setup(bot: commands.Bot):
    await bot.add_cog(GamblingPanel(bot))
