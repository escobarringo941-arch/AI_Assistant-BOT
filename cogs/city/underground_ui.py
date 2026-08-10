# -*- coding: utf-8 -*-
from __future__ import annotations

import discord

from . import config
from .reliability import ReliableView, ReliableModal, defer_update, defer_private, safe_edit, safe_private, guarded
from .underground import UNDERGROUND_PATHS, VIRTUAL_ITEMS, HEIST_STAGES


async def _open_private(interaction: discord.Interaction, *, embed: discord.Embed, view: discord.ui.View):
    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class UndergroundOwnedView(ReliableView):
    def __init__(self,cog,user,timeout=3600):
        super().__init__(timeout=timeout); self.cog=cog; self.user=user
    async def interaction_check(self,interaction):
        if interaction.user.id!=self.user.id:
            await safe_private(interaction,"❌ هاد البانل ماشي ديالك."); return False
        if interaction.guild and not self.cog.is_underground_member(interaction.guild.id,interaction.user.id):
            await safe_private(interaction,"🌑 ما عندكش Access لهاد العالم."); return False
        return True


def underground_home_embed(cog,guild,member):
    e=cog.underground_profile_embed(guild,member)
    e.title="🌑 THE UNDERGROUND — Private Console"
    e.description="Contracts • Virtual Black Market • Crews • Operations\nكلشي هنا Game Simulation داخل GGMW9 فقط."
    return e


class UndergroundGatePublicView(ReliableView):
    def __init__(self,cog): super().__init__(timeout=None); self.cog=cog
    @discord.ui.button(label="🌑 دخل للعالم المخفي",style=discord.ButtonStyle.secondary,custom_id="ggmw9:city:ug:open")
    async def open(self,interaction,button):
        if not interaction.guild or not self.cog.is_underground_member(interaction.guild.id,interaction.user.id):
            await safe_private(interaction,"🌑 ما عندكش Access."); return
        await _open_private(interaction,embed=underground_home_embed(self.cog,interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,interaction.user))


class UndergroundMarketPublicView(ReliableView):
    def __init__(self,cog): super().__init__(timeout=None); self.cog=cog
    @discord.ui.button(label="🗡️ فتح السوق السري",style=discord.ButtonStyle.secondary,custom_id="ggmw9:city:ug:market:open")
    async def open(self,interaction,button):
        if not interaction.guild or not self.cog.is_underground_member(interaction.guild.id,interaction.user.id):
            await safe_private(interaction,"🌑 ما عندكش Access."); return
        await _open_private(interaction,embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,interaction.user))


class UndergroundCrewsPublicView(ReliableView):
    def __init__(self,cog): super().__init__(timeout=None); self.cog=cog
    @discord.ui.button(label="👥 فتح Crews",style=discord.ButtonStyle.secondary,custom_id="ggmw9:city:ug:crews:open")
    async def open(self,interaction,button):
        if not interaction.guild or not self.cog.is_underground_member(interaction.guild.id,interaction.user.id):
            await safe_private(interaction,"🌑 ما عندكش Access."); return
        await _open_private(interaction,embed=crew_embed(self.cog,interaction.guild,interaction.user),view=UndergroundCrewView(self.cog,interaction.user))


class UndergroundOperationsPublicView(ReliableView):
    def __init__(self,cog): super().__init__(timeout=None); self.cog=cog
    @discord.ui.button(label="🏦 فتح Operations",style=discord.ButtonStyle.secondary,custom_id="ggmw9:city:ug:ops:open")
    async def open(self,interaction,button):
        if not interaction.guild or not self.cog.is_underground_member(interaction.guild.id,interaction.user.id):
            await safe_private(interaction,"🌑 ما عندكش Access."); return
        await _open_private(interaction,embed=operations_embed(self.cog,interaction.guild,interaction.user),view=UndergroundOperationsView(self.cog,interaction.user))


class UndergroundHomeView(UndergroundOwnedView):
    def __init__(self,cog,user):
        super().__init__(cog,user)
        self.add_item(_ActionButton("🕴️ الهوية / Path",discord.ButtonStyle.primary,self.path,row=0))
        self.add_item(_ActionButton("📜 Mission",discord.ButtonStyle.success,self.mission,row=0))
        self.add_item(_ActionButton("🗡️ Black Market",discord.ButtonStyle.secondary,self.market,row=0))
        self.add_item(_ActionButton("👥 Crew",discord.ButtonStyle.secondary,self.crew,row=1))
        self.add_item(_ActionButton("🏦 Operations",discord.ButtonStyle.danger,self.ops,row=1))
        self.add_item(_ActionButton("🔄 Refresh",discord.ButtonStyle.secondary,self.refresh,row=1))
    async def path(self,interaction):
        row=self.cog.underground_member(interaction.guild.id,interaction.user.id,create=True)
        if row.get("path_id"):
            await interaction.response.edit_message(embed=self.cog.underground_profile_embed(interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,self.user)); return
        await interaction.response.edit_message(content="🕴️ اختار Underground Career ديالك. الاختيار كيتثبت:",embed=None,view=UndergroundPathView(self.cog,self.user))
    async def mission(self,interaction): await show_mission(interaction,self.cog,self.user)
    async def market(self,interaction): await interaction.response.edit_message(content=None,embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user))
    async def crew(self,interaction): await interaction.response.edit_message(content=None,embed=crew_embed(self.cog,interaction.guild,interaction.user),view=UndergroundCrewView(self.cog,self.user))
    async def ops(self,interaction): await interaction.response.edit_message(content=None,embed=operations_embed(self.cog,interaction.guild,interaction.user),view=UndergroundOperationsView(self.cog,self.user))
    async def refresh(self,interaction): await interaction.response.edit_message(content=None,embed=underground_home_embed(self.cog,interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,self.user))


class _ActionButton(discord.ui.Button):
    def __init__(self,label,style,callback,row=0,emoji=None,disabled=False):
        super().__init__(label=label,style=style,row=row,emoji=emoji,disabled=disabled); self._cb=callback
    async def callback(self,interaction): await self._cb(interaction)


class UndergroundPathSelect(discord.ui.Select):
    def __init__(self,cog,user):
        opts=[discord.SelectOption(label=p["name"],value=k,emoji=p["emoji"],description=p["desc"][:100]) for k,p in UNDERGROUND_PATHS.items()]
        super().__init__(placeholder="🕴️ اختار Path...",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user
    async def callback(self,interaction):
        if interaction.user.id!=self.user.id: await safe_private(interaction,"❌ هاد البانل ماشي ديالك."); return
        await defer_update(interaction)
        ok,msg=await guarded(self.cog.choose_underground_path(interaction.guild,interaction.user,self.values[0]))
        await safe_edit(interaction,content=msg,embed=self.cog.underground_profile_embed(interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,self.user))


class UndergroundPathView(UndergroundOwnedView):
    def __init__(self,cog,user):
        super().__init__(cog,user); self.add_item(UndergroundPathSelect(cog,user)); self.add_item(_ActionButton("↩️ رجوع",discord.ButtonStyle.secondary,self.back,row=1))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=underground_home_embed(self.cog,interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,self.user))


async def show_mission(interaction,cog,user):
    await defer_update(interaction)
    ok,msg,mission=await guarded(cog.start_underground_mission(interaction.guild,interaction.user))
    if not mission:
        await safe_edit(interaction,content=msg,embed=underground_home_embed(cog,interaction.guild,interaction.user),view=UndergroundHomeView(cog,user)); return
    e=discord.Embed(title=f"📜 Contract {mission['id']}",description=mission["prompt"],color=discord.Color.dark_grey())
    await safe_edit(interaction,content=msg,embed=e,view=UndergroundMissionView(cog,user,mission))


class UndergroundMissionView(UndergroundOwnedView):
    def __init__(self,cog,user,mission):
        super().__init__(cog,user); self.mission=mission
        for i,opt in enumerate(mission.get("options",[])[:3]):
            self.add_item(_ActionButton(opt[:80],discord.ButtonStyle.secondary,self._answer(i),row=i//2))
        self.add_item(_ActionButton("↩️ رجوع",discord.ButtonStyle.secondary,self.back,row=2))
    def _answer(self,index):
        async def cb(interaction):
            await defer_update(interaction)
            ok,msg,out=await guarded(self.cog.resolve_underground_mission(interaction.guild,interaction.user,index))
            await safe_edit(interaction,content=msg,embed=self.cog.underground_profile_embed(interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,self.user))
        return cb
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=underground_home_embed(self.cog,interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,self.user))


def market_embed(cog,guild,member):
    row=cog.underground_member(guild.id,member.id,create=True); rep=int(row.get("reputation",0)); inv=row.get("inventory",{}) or {}
    e=discord.Embed(title="🗡️ BLACK MARKET — Virtual Only",description="Game Items فقط. جميع P2P sales كيدوزو من Escrow وبـGGMW9 USD.",color=discord.Color.dark_grey())
    e.add_field(name="⭐ REP",value=str(rep),inline=True); e.add_field(name="🎒 Inventory",value=str(sum(max(0,int(x)) for x in inv.values())),inline=True)
    opens=[x for x in cog.underground(guild.id).get("listings",{}).values() if x.get("status")=="open"]
    e.add_field(name="🕳️ Open Listings",value=str(len(opens)),inline=True); e.set_footer(text="Virtual simulation only • no real-world weapon sales")
    return e


class UndergroundMarketView(UndergroundOwnedView):
    def __init__(self,cog,user):
        super().__init__(cog,user)
        self.add_item(_ActionButton("🏪 Virtual Supply",discord.ButtonStyle.primary,self.supply,row=0))
        self.add_item(_ActionButton("📤 بيع Item",discord.ButtonStyle.secondary,self.sell,row=0))
        self.add_item(_ActionButton("🛒 P2P Listings",discord.ButtonStyle.success,self.listings,row=0))
        self.add_item(_ActionButton("📦 Listings ديالي",discord.ButtonStyle.secondary,self.my_listings,row=1))
        self.add_item(_ActionButton("↩️ Underground",discord.ButtonStyle.secondary,self.back,row=1))
    async def supply(self,interaction): await interaction.response.edit_message(content="اختار Virtual Item:",embed=None,view=UndergroundSupplyView(self.cog,self.user))
    async def sell(self,interaction):
        inv=self.cog.underground_member(interaction.guild.id,interaction.user.id,create=True).get("inventory",{}) or {}; available=[(k,v) for k,v in inv.items() if k in VIRTUAL_ITEMS and int(v)>0]
        if not available: await interaction.response.edit_message(content="🎒 Inventory فارغة.",embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user)); return
        await interaction.response.edit_message(content="📤 اختار Item باش تعرضها للبيع:",embed=None,view=UndergroundSellSelectView(self.cog,self.user,available))
    async def listings(self,interaction):
        rows=[x for x in self.cog.underground(interaction.guild.id).get("listings",{}).values() if x.get("status")=="open" and int(x.get("seller_id",0))!=interaction.user.id]
        if not rows: await interaction.response.edit_message(content="📭 ماكاين حتى P2P Listing متاحة دابا.",embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user)); return
        await interaction.response.edit_message(content="🛒 اختار Listing:",embed=None,view=UndergroundListingsView(self.cog,self.user,rows[:25]))
    async def my_listings(self,interaction):
        rows=[x for x in self.cog.underground(interaction.guild.id).get("listings",{}).values() if x.get("status")=="open" and int(x.get("seller_id",0))==interaction.user.id]
        if not rows: await interaction.response.edit_message(content="📭 ماعندك حتى Listing مفتوحة.",embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user)); return
        await interaction.response.edit_message(content="📦 اختار Listing إلا بغيتي تلغيها وترجع Item:",embed=None,view=UndergroundMyListingsView(self.cog,self.user,rows[:25]))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=underground_home_embed(self.cog,interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,self.user))


class UndergroundSupplySelect(discord.ui.Select):
    def __init__(self,cog,user):
        opts=[discord.SelectOption(label=x["name"],value=k,emoji=x["emoji"],description=f"{cog.fmt(x['price'])} • {x['rep']} REP") for k,x in VIRTUAL_ITEMS.items()]
        super().__init__(placeholder="🏪 Virtual Supply",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user
    async def callback(self,interaction):
        await defer_update(interaction); ok,msg=await guarded(self.cog.buy_underground_supply(interaction.guild,interaction.user,self.values[0])); await safe_edit(interaction,content=msg,embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user))

class UndergroundSupplyView(UndergroundOwnedView):
    def __init__(self,cog,user): super().__init__(cog,user); self.add_item(UndergroundSupplySelect(cog,user)); self.add_item(_ActionButton("↩️ السوق",discord.ButtonStyle.secondary,self.back,row=1))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user))


class UndergroundSellSelect(discord.ui.Select):
    def __init__(self,cog,user,available):
        opts=[discord.SelectOption(label=VIRTUAL_ITEMS[k]["name"],value=k,emoji=VIRTUAL_ITEMS[k]["emoji"],description=f"عندك ×{v}") for k,v in available[:25]]
        super().__init__(placeholder="📤 Item...",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user
    async def callback(self,interaction): await interaction.response.send_modal(UndergroundSellModal(self.cog,self.values[0]))

class UndergroundSellSelectView(UndergroundOwnedView):
    def __init__(self,cog,user,available): super().__init__(cog,user); self.add_item(UndergroundSellSelect(cog,user,available))


class UndergroundSellModal(ReliableModal):
    def __init__(self,cog,item_id):
        super().__init__(title="🕳️ P2P Listing"); self.cog=cog; self.item_id=item_id
        self.price=discord.ui.TextInput(label="الثمن بالدولار",placeholder="مثال: 25 أو 25.50",max_length=24); self.add_item(self.price)
    async def on_submit(self,interaction):
        await defer_private(interaction,thinking=True)
        amount=None
        try: amount=__import__('games_config').parse_money_input(str(self.price.value))
        except Exception: amount=None
        if amount is None or amount<100:
            await safe_edit(interaction,content="❌ دخل ثمن صحيح $1.00 على الأقل.",embed=None,view=None); return
        ok,msg=await guarded(self.cog.create_underground_listing(interaction.guild,interaction.user,self.item_id,amount))
        await safe_edit(interaction,content=msg,embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,interaction.user))


class UndergroundListingSelect(discord.ui.Select):
    def __init__(self,cog,user,rows):
        opts=[]
        for x in rows:
            item=VIRTUAL_ITEMS.get(x["item_id"],{}); seller=user.guild.get_member(int(x.get("seller_id",0))) if isinstance(user,discord.Member) else None
            opts.append(discord.SelectOption(label=f"{item.get('name','Item')} • {cog.fmt(x['price'])}"[:100],value=x["id"],emoji=item.get("emoji","🕳️"),description=f"Seller: {seller.display_name if seller else x['seller_id']}"[:100]))
        super().__init__(placeholder="🛒 Listing...",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user
    async def callback(self,interaction):
        await defer_update(interaction); ok,msg=await guarded(self.cog.buy_underground_listing(interaction.guild,interaction.user,self.values[0])); await safe_edit(interaction,content=msg,embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user))

class UndergroundListingsView(UndergroundOwnedView):
    def __init__(self,cog,user,rows): super().__init__(cog,user); self.add_item(UndergroundListingSelect(cog,user,rows)); self.add_item(_ActionButton("↩️ السوق",discord.ButtonStyle.secondary,self.back,row=1))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user))

class UndergroundMyListingSelect(discord.ui.Select):
    def __init__(self,cog,user,rows):
        opts=[]
        for x in rows:
            item=VIRTUAL_ITEMS.get(x.get("item_id"),{})
            opts.append(discord.SelectOption(label=f"{item.get('name','Item')} • {cog.fmt(x.get('price',0))}"[:100],value=x["id"],emoji=item.get("emoji","📦"),description="إلغاء Listing ورجوع Item"))
        super().__init__(placeholder="📦 Listing ديالك...",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user
    async def callback(self,interaction):
        await defer_update(interaction)
        ok,msg=await guarded(self.cog.cancel_underground_listing(interaction.guild,interaction.user,self.values[0]))
        await safe_edit(interaction,content=msg,embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user))

class UndergroundMyListingsView(UndergroundOwnedView):
    def __init__(self,cog,user,rows):
        super().__init__(cog,user); self.add_item(UndergroundMyListingSelect(cog,user,rows)); self.add_item(_ActionButton("↩️ السوق",discord.ButtonStyle.secondary,self.back,row=1))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=market_embed(self.cog,interaction.guild,interaction.user),view=UndergroundMarketView(self.cog,self.user))


def crew_embed(cog,guild,member):
    row=cog.underground_member(guild.id,member.id,create=True); cid=row.get("crew_id"); crew=cog.underground(guild.id).get("crews",{}).get(cid) if cid else None; inv=cog.underground(guild.id).get("crew_invites",{}).get(str(member.id))
    e=discord.Embed(title="👥 Underground Crews",color=discord.Color.dark_grey())
    if crew:
        vault=cog.economy.city_crew_account(guild.id,cid).get("balance",0) if cog.economy else 0
        e.description=f"**{crew['name']}** • `{cid}`"; e.add_field(name="👥 Members",value=str(len(crew.get('members',[]))),inline=True); e.add_field(name="⭐ Crew REP",value=str(int(crew.get('reputation',0))),inline=True); e.add_field(name="🏦 Crew Vault",value=cog.fmt(vault),inline=True); e.add_field(name="👑 Leader",value=f"<@{crew['leader_id']}>",inline=False)
    else:
        e.description="ما عندكش Crew دابا. تقدر تصاوب وحدة أو تقبل دعوة."; 
        if inv:
            c=cog.underground(guild.id).get("crews",{}).get(inv.get("crew_id")); e.add_field(name="📨 Pending Invite",value=c.get("name") if c else inv.get("crew_id"),inline=False)
    return e


class UndergroundCrewView(UndergroundOwnedView):
    def __init__(self,cog,user):
        super().__init__(cog,user); guild=user.guild if isinstance(user,discord.Member) else None; row=cog.underground_member(guild.id,user.id,create=True) if guild else {}; cid=row.get("crew_id"); crew=cog.underground(guild.id).get("crews",{}).get(cid) if guild and cid else None; inv=cog.underground(guild.id).get("crew_invites",{}).get(str(user.id)) if guild else None
        if not crew:
            self.add_item(_ActionButton("➕ صاوب Crew",discord.ButtonStyle.success,self.create,row=0))
            if inv:
                self.add_item(_ActionButton("✅ قبل Crew Invite",discord.ButtonStyle.success,self.accept,row=0)); self.add_item(_ActionButton("❌ رفض",discord.ButtonStyle.danger,self.decline,row=0))
        else:
            self.add_item(_ActionButton("🏦 Deposit للVault",discord.ButtonStyle.primary,self.deposit,row=0))
            if int(crew.get("leader_id",0))==user.id:
                self.add_item(_ActionButton("📨 دعا عضو",discord.ButtonStyle.secondary,self.invite,row=0))
        self.add_item(_ActionButton("↩️ Underground",discord.ButtonStyle.secondary,self.back,row=2))
    async def create(self,interaction): await interaction.response.send_modal(CrewCreateModal(self.cog))
    async def accept(self,interaction):
        await defer_update(interaction); ok,msg=await guarded(self.cog.answer_crew_invite(interaction.guild,interaction.user,True)); await safe_edit(interaction,content=msg,embed=crew_embed(self.cog,interaction.guild,interaction.user),view=UndergroundCrewView(self.cog,self.user))
    async def decline(self,interaction):
        await defer_update(interaction); ok,msg=await guarded(self.cog.answer_crew_invite(interaction.guild,interaction.user,False)); await safe_edit(interaction,content=msg,embed=crew_embed(self.cog,interaction.guild,interaction.user),view=UndergroundCrewView(self.cog,self.user))
    async def deposit(self,interaction): await interaction.response.send_modal(CrewDepositModal(self.cog))
    async def invite(self,interaction): await interaction.response.edit_message(content="📨 اختار Underground member:",embed=None,view=CrewInviteMemberView(self.cog,self.user))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=underground_home_embed(self.cog,interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,self.user))


class CrewCreateModal(ReliableModal):
    def __init__(self,cog): super().__init__(title="👥 Create Crew"); self.cog=cog; self.name_i=discord.ui.TextInput(label="Crew name",min_length=3,max_length=32); self.add_item(self.name_i)
    async def on_submit(self,interaction):
        await defer_private(interaction,thinking=True); ok,msg=await guarded(self.cog.create_crew(interaction.guild,interaction.user,str(self.name_i.value))); await safe_edit(interaction,content=msg,embed=crew_embed(self.cog,interaction.guild,interaction.user),view=UndergroundCrewView(self.cog,interaction.user))

class CrewDepositModal(ReliableModal):
    def __init__(self,cog): super().__init__(title="🏦 Crew Vault Deposit"); self.cog=cog; self.amount=discord.ui.TextInput(label="المبلغ بالدولار",placeholder="مثال: 50",max_length=24); self.add_item(self.amount)
    async def on_submit(self,interaction):
        await defer_private(interaction,thinking=True)
        try: amount=__import__('games_config').parse_money_input(str(self.amount.value))
        except Exception: amount=None
        if amount is None or amount<100: await safe_edit(interaction,content="❌ مبلغ غير صالح.",embed=None,view=None); return
        ok,msg=await guarded(self.cog.crew_deposit(interaction.guild,interaction.user,amount)); await safe_edit(interaction,content=msg,embed=crew_embed(self.cog,interaction.guild,interaction.user),view=UndergroundCrewView(self.cog,interaction.user))

class CrewInviteUserSelect(discord.ui.UserSelect):
    def __init__(self,cog,user): super().__init__(placeholder="👥 العضو...",min_values=1,max_values=1); self.cog=cog; self.user=user
    async def callback(self,interaction):
        await defer_update(interaction)
        picked=self.values[0]; target=interaction.guild.get_member(int(picked.id))
        if not target:
            await safe_edit(interaction,content="❌ العضو ما بقاش فالسيرفر.",embed=crew_embed(self.cog,interaction.guild,interaction.user),view=UndergroundCrewView(self.cog,self.user)); return
        ok,msg=await guarded(self.cog.invite_to_crew(interaction.guild,interaction.user,target)); await safe_edit(interaction,content=msg,embed=crew_embed(self.cog,interaction.guild,interaction.user),view=UndergroundCrewView(self.cog,self.user))
class CrewInviteMemberView(UndergroundOwnedView):
    def __init__(self,cog,user): super().__init__(cog,user); self.add_item(CrewInviteUserSelect(cog,user))


def operations_embed(cog,guild,member):
    row=cog.underground_member(guild.id,member.id,create=True); cid=row.get("crew_id"); crew=cog.underground(guild.id).get("crews",{}).get(cid) if cid else None
    e=discord.Embed(title="🏦 Underground Operations",description="Bank Heist هنا **محاكاة خيالية** ممولة من Treasury reserve؛ حسابات Savings/Wallet ديال الأعضاء ما كتتمسش.",color=discord.Color.dark_grey())
    if crew:
        vault=cog.economy.city_crew_account(guild.id,cid).get("balance",0) if cog.economy else 0
        ready=sum(1 for uid in crew.get("members",[]) if int(uid)==int(crew.get("leader_id",0)) or cog.underground_member(guild.id,int(uid)).get("heist_ready"))
        e.add_field(name="👥 Crew",value=crew["name"],inline=True); e.add_field(name="⭐ REP",value=str(int(crew.get('reputation',0))),inline=True); e.add_field(name="🏦 Vault",value=cog.fmt(vault),inline=True); e.add_field(name="✅ Ready",value=f"{ready}/{len(crew.get('members',[]))}",inline=True)
    e.add_field(name="📋 Requirements",value=f"Leader • {config.UNDERGROUND_HEIST_MIN_CREW}+ Ready • {config.UNDERGROUND_HEIST_MIN_REP} REP • Prep {cog.fmt(config.UNDERGROUND_HEIST_PREP_COST)} • Cooldown {config.UNDERGROUND_HEIST_COOLDOWN_HOURS//24}d",inline=False)
    return e


class UndergroundOperationsView(UndergroundOwnedView):
    def __init__(self,cog,user):
        super().__init__(cog,user)
        guild=user.guild if isinstance(user,discord.Member) else None; row=cog.underground_member(guild.id,user.id,create=True) if guild else {}
        self.add_item(_ActionButton("🏦 بدا Bank Operation",discord.ButtonStyle.danger,self.start,row=0))
        self.add_item(_ActionButton("⏸️ حيد Ready" if row.get("heist_ready") else "✅ Ready للعملية",discord.ButtonStyle.success if not row.get("heist_ready") else discord.ButtonStyle.secondary,self.ready,row=0))
        self.add_item(_ActionButton("↩️ Underground",discord.ButtonStyle.secondary,self.back,row=1))
    async def ready(self,interaction):
        await defer_update(interaction)
        row=self.cog.underground_member(interaction.guild.id,interaction.user.id,create=True)
        ok,msg=await guarded(self.cog.set_heist_ready(interaction.guild,interaction.user,not bool(row.get("heist_ready"))))
        await safe_edit(interaction,content=msg,embed=operations_embed(self.cog,interaction.guild,interaction.user),view=UndergroundOperationsView(self.cog,self.user))
    async def start(self,interaction):
        await defer_update(interaction); ok,msg,op=await guarded(self.cog.start_virtual_heist(interaction.guild,interaction.user))
        if not op: await safe_edit(interaction,content=msg,embed=operations_embed(self.cog,interaction.guild,interaction.user),view=UndergroundOperationsView(self.cog,self.user)); return
        stages=op.get("stages") or HEIST_STAGES; spec=stages[0]; e=discord.Embed(title=f"{spec['title']} • {op['id']}",description=spec["prompt"],color=discord.Color.dark_red()); await safe_edit(interaction,content=msg,embed=e,view=HeistStageView(self.cog,self.user,op))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=underground_home_embed(self.cog,interaction.guild,interaction.user),view=UndergroundHomeView(self.cog,self.user))


class HeistStageView(UndergroundOwnedView):
    def __init__(self,cog,user,op):
        super().__init__(cog,user); self.op=op; stage=int(op.get("stage",0)); stages=op.get("stages") or HEIST_STAGES; spec=stages[min(stage,len(stages)-1)]
        for i,opt in enumerate(spec["options"]): self.add_item(_ActionButton(opt,discord.ButtonStyle.danger if i else discord.ButtonStyle.secondary,self._pick(i),row=i//2))
    def _pick(self,i):
        async def cb(interaction):
            await defer_update(interaction); ok,msg,op=await guarded(self.cog.resolve_virtual_heist_step(interaction.guild,interaction.user,self.op["id"],i))
            if not op or op.get("status")!="active": await safe_edit(interaction,content=msg,embed=operations_embed(self.cog,interaction.guild,interaction.user),view=UndergroundOperationsView(self.cog,self.user)); return
            stage=int(op.get("stage",0)); stages=op.get("stages") or HEIST_STAGES; spec=stages[stage]; e=discord.Embed(title=f"{spec['title']} • {op['id']}",description=spec["prompt"],color=discord.Color.dark_red()); await safe_edit(interaction,content=msg,embed=e,view=HeistStageView(self.cog,self.user,op))
        return cb


class UndergroundInviteView(ReliableView):
    def __init__(self,cog): super().__init__(timeout=None); self.cog=cog
    @discord.ui.button(label="✅ قبول العرض",style=discord.ButtonStyle.success,custom_id="ggmw9:city:ug:invite:accept")
    async def accept(self,interaction,button):
        await defer_update(interaction); ok,msg=await guarded(self.cog.answer_underground_invite(interaction.user,True)); await safe_edit(interaction,content=msg,embed=None,view=None)
    @discord.ui.button(label="❌ رفض",style=discord.ButtonStyle.danger,custom_id="ggmw9:city:ug:invite:decline")
    async def decline(self,interaction,button):
        await defer_update(interaction); ok,msg=await guarded(self.cog.answer_underground_invite(interaction.user,False)); await safe_edit(interaction,content=msg,embed=None,view=None)


# ------------------------- OWNER UI ----------------------------------
class OwnerUndergroundView(ReliableView):
    def __init__(self,cog):
        super().__init__(timeout=3600); self.cog=cog
    async def interaction_check(self,interaction):
        if not interaction.guild or interaction.user.id != interaction.guild.owner_id: await safe_private(interaction,"❌ Owner فقط."); return False
        return True
    @discord.ui.button(label="Setup / Repair",emoji="🌑",style=discord.ButtonStyle.success,row=0)
    async def setup(self,interaction,button):
        await defer_update(interaction); result=await guarded(self.cog.setup_underground(interaction.guild,force=True)); msg="✅ Underground تخلقات/تصلحات." if result.get("ok") else f"❌ {result.get('error')}"; await safe_edit(interaction,content=msg,embed=self.cog.underground_owner_embed(interaction.guild),view=OwnerUndergroundView(self.cog))
    @discord.ui.button(label="Send Anonymous Invite",emoji="📨",style=discord.ButtonStyle.primary,row=0)
    async def invite(self,interaction,button): await interaction.response.edit_message(content="📨 اختار العضو اللي بغيتي توصله الدعوة المجهولة:",embed=None,view=OwnerInviteMemberView(self.cog))
    @discord.ui.button(label="Members",emoji="👥",style=discord.ButtonStyle.secondary,row=0)
    async def members(self,interaction,button):
        ug=self.cog.underground(interaction.guild.id); lines=[]
        for uid,row in ug.get("members",{}).items():
            if row.get("active"): lines.append(f"• <@{uid}> • {row.get('path_id') or 'No Path'} • REP {int(row.get('reputation',0))} • Heat {int(row.get('heat',0))}")
        e=self.cog.underground_owner_embed(interaction.guild); e.add_field(name="👥 Whitelist",value="\n".join(lines)[:1024] if lines else "—",inline=False); await interaction.response.edit_message(content=None,embed=e,view=OwnerUndergroundView(self.cog))
    @discord.ui.button(label="Pending Invites",emoji="⏳",style=discord.ButtonStyle.secondary,row=0)
    async def pending(self,interaction,button):
        rows=[x for x in self.cog.underground(interaction.guild.id).get("invites",{}).values() if x.get("status")=="pending"]; e=self.cog.underground_owner_embed(interaction.guild); e.add_field(name="⏳ Pending",value="\n".join(f"• <@{x['user_id']}> • `{x['id']}`" for x in rows)[:1024] if rows else "—",inline=False); await interaction.response.edit_message(content=None,embed=e,view=OwnerUndergroundView(self.cog))
    @discord.ui.button(label="Revoke Access",emoji="🚫",style=discord.ButtonStyle.danger,row=1)
    async def revoke(self,interaction,button): await interaction.response.edit_message(content="🚫 اختار العضو:",embed=None,view=OwnerRevokeMemberView(self.cog))
    @discord.ui.button(label="Lock / Unlock",emoji="🔒",style=discord.ButtonStyle.danger,row=1)
    async def lock(self,interaction,button):
        await defer_update(interaction); locked=not bool(self.cog.underground(interaction.guild.id).get("locked")); ok,msg=await guarded(self.cog.set_underground_lock(interaction.guild,locked)); await safe_edit(interaction,content=msg,embed=self.cog.underground_owner_embed(interaction.guild),view=OwnerUndergroundView(self.cog))
    @discord.ui.button(label="Repair Permissions",emoji="🛠️",style=discord.ButtonStyle.secondary,row=1)
    async def repair(self,interaction,button):
        await defer_update(interaction); result=await guarded(self.cog.repair_underground_permissions(interaction.guild)); await safe_edit(interaction,content=f"✅ Permission repair • Active {result.get('active',0)} • Locked {result.get('locked')}",embed=self.cog.underground_owner_embed(interaction.guild),view=OwnerUndergroundView(self.cog))
    @discord.ui.button(label="Diagnostics",emoji="🩺",style=discord.ButtonStyle.secondary,row=1)
    async def diag(self,interaction,button):
        await defer_update(interaction); result=await guarded(self.cog.underground_diagnostics(interaction.guild)); lines=[f"{'🟢' if ok else '🔴'} {name}" for name,ok in result['checks']]; exposure=result.get('admin_exposure') or []; lines.append("\n⚠️ Administrator bypass كيشوف hidden channels: "+", ".join(exposure) if exposure else "\n🟢 ماكاين حتى Human Administrator خارج Owner."); e=discord.Embed(title="🩺 Underground Diagnostics",description="\n".join(lines)[:4000],color=discord.Color.green() if result['ok'] and not exposure else discord.Color.orange()); await safe_edit(interaction,content=None,embed=e,view=OwnerUndergroundView(self.cog))
    @discord.ui.button(label="Cancel Pending Invite",emoji="🗑️",style=discord.ButtonStyle.secondary,row=2)
    async def cancel_invite(self,interaction,button):
        await interaction.response.edit_message(content="🗑️ اختار العضو اللي بغيتي تلغي ليه الدعوة المعلقة:",embed=None,view=OwnerCancelInviteMemberView(self.cog))

class OwnerInviteUserSelect(discord.ui.UserSelect):
    def __init__(self,cog): super().__init__(placeholder="📨 Member...",min_values=1,max_values=1); self.cog=cog
    async def callback(self,interaction):
        await defer_update(interaction)
        picked=self.values[0]; target=interaction.guild.get_member(int(picked.id))
        if not target:
            await safe_edit(interaction,content="❌ العضو ما بقاش فالسيرفر.",embed=self.cog.underground_owner_embed(interaction.guild),view=OwnerUndergroundView(self.cog)); return
        ok,msg=await guarded(self.cog.create_underground_invite(interaction.guild,target)); await safe_edit(interaction,content=msg,embed=self.cog.underground_owner_embed(interaction.guild),view=OwnerUndergroundView(self.cog))
class OwnerInviteMemberView(ReliableView):
    def __init__(self,cog): super().__init__(timeout=300); self.cog=cog; self.add_item(OwnerInviteUserSelect(cog))
    async def interaction_check(self,interaction): return bool(interaction.guild and interaction.user.id == interaction.guild.owner_id)

class OwnerRevokeUserSelect(discord.ui.UserSelect):
    def __init__(self,cog): super().__init__(placeholder="🚫 Member...",min_values=1,max_values=1); self.cog=cog
    async def callback(self,interaction):
        await defer_update(interaction)
        picked=self.values[0]; target=interaction.guild.get_member(int(picked.id))
        if not target:
            await safe_edit(interaction,content="❌ العضو ما بقاش فالسيرفر.",embed=self.cog.underground_owner_embed(interaction.guild),view=OwnerUndergroundView(self.cog)); return
        ok,msg=await guarded(self.cog.revoke_underground_access(interaction.guild,target)); await safe_edit(interaction,content=msg,embed=self.cog.underground_owner_embed(interaction.guild),view=OwnerUndergroundView(self.cog))
class OwnerRevokeMemberView(ReliableView):
    def __init__(self,cog): super().__init__(timeout=300); self.cog=cog; self.add_item(OwnerRevokeUserSelect(cog))
    async def interaction_check(self,interaction): return bool(interaction.guild and interaction.user.id == interaction.guild.owner_id)

class OwnerCancelInviteUserSelect(discord.ui.UserSelect):
    def __init__(self,cog): super().__init__(placeholder="🗑️ Member...",min_values=1,max_values=1); self.cog=cog
    async def callback(self,interaction):
        await defer_update(interaction)
        picked=self.values[0]; target=interaction.guild.get_member(int(picked.id))
        if not target:
            await safe_edit(interaction,content="❌ العضو ما بقاش فالسيرفر.",embed=self.cog.underground_owner_embed(interaction.guild),view=OwnerUndergroundView(self.cog)); return
        ok,msg=await guarded(self.cog.cancel_underground_invite(interaction.guild,target))
        await safe_edit(interaction,content=msg,embed=self.cog.underground_owner_embed(interaction.guild),view=OwnerUndergroundView(self.cog))

class OwnerCancelInviteMemberView(ReliableView):
    def __init__(self,cog): super().__init__(timeout=300); self.cog=cog; self.add_item(OwnerCancelInviteUserSelect(cog))
    async def interaction_check(self,interaction):
        if not interaction.guild or interaction.user.id != interaction.guild.owner_id:
            await safe_private(interaction,"❌ Owner فقط."); return False
        return True
