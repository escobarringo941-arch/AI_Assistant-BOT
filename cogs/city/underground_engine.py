# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import discord
from cogs.panel_registry import upsert_fixed_panel

from . import config
from .underground import (
    UNDERGROUND_PATHS,
    VIRTUAL_ITEMS,
    HEIST_STAGES,
    choose_mission,
    mission_outcome,
    heist_success_chance,
    heist_gross_reward,
    cooldown_ready,
    operation_modifiers,
    prepare_heist_stages,
    local_now as underground_now,
)


def _iso_ug() -> str:
    return underground_now().isoformat()


def _parse(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


class UndergroundEngineMixin:
    """Fictional hidden-world engine mixed into CareerCity.

    Access is stored by Discord user ID, never by a visible criminal role.
    """

    def guild_owner_id(self, guild_id: int) -> int:
        """Resolve authority from Discord's live guild state, not configuration."""
        guild = self.bot.get_guild(int(guild_id))
        return int(guild.owner_id) if guild else 0

    def underground(self, guild_id: int) -> dict:
        return self.store.underground(guild_id)

    def underground_member(self, guild_id: int, user_id: int, *, create: bool = False) -> dict:
        ug = self.underground(guild_id)
        members = ug.setdefault("members", {})
        key = str(int(user_id))
        if key not in members and create:
            members[key] = {
                "active": False,
                "joined_at": None,
                "path_id": None,
                "reputation": 0,
                "heat": 0,
                "heat_updated_at": _iso_ug(),
                "inventory": {},
                "mission": None,
                "last_mission_at": None,
                "crew_id": None,
                "heist_ready": False,
                "missions_done": 0,
                "earned": 0,
            }
        row = members.get(key) or {}
        if row and row.get("active"):
            self._decay_heat(row)
        return row

    def _decay_heat(self, row: dict) -> None:
        last = _parse(row.get("heat_updated_at"))
        now = underground_now()
        if not last:
            row["heat_updated_at"] = now.isoformat()
            return
        hours = max(1, int(config.UNDERGROUND_HEAT_DECAY_HOURS))
        steps = int((now - last).total_seconds() // (hours * 3600))
        if steps > 0:
            row["heat"] = max(0, int(row.get("heat", 0) or 0) - steps)
            row["heat_updated_at"] = (last + timedelta(hours=steps * hours)).isoformat()

    def is_underground_member(self, guild_id: int, user_id: int) -> bool:
        owner_id = self.guild_owner_id(guild_id)
        if owner_id and int(user_id) == owner_id:
            return True
        return bool(self.underground_member(guild_id, user_id).get("active"))

    def underground_channel(self, guild: discord.Guild, key: str):
        setup = self.underground(guild.id).get("setup", {})
        cid = int((setup.get("channels") or {}).get(key) or 0)
        return guild.get_channel(cid) if cid else None

    async def setup_underground(self, guild: discord.Guild, *, force: bool = False) -> dict:
        me = guild.me
        if not me or not me.guild_permissions.manage_channels:
            return {"ok": False, "error": "البوت خاصو Manage Channels."}
        owner = guild.owner
        if not owner:
            return {"ok": False, "error": "Discord Server Owner ما تلقاش فالسيرفر."}

        ug = self.underground(guild.id)
        setup = ug.setdefault("setup", {})
        channels = setup.setdefault("channels", {})
        category = guild.get_channel(int(setup.get("category_id") or 0)) if setup.get("category_id") else None
        if not isinstance(category, discord.CategoryChannel):
            category = discord.utils.get(guild.categories, name=config.UNDERGROUND_CATEGORY_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False, send_messages=False, read_message_history=False,
                create_public_threads=False, create_private_threads=False,
            ),
            me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True,
                embed_links=True, manage_messages=True, manage_channels=True,
            ),
            owner: discord.PermissionOverwrite(
                view_channel=True, send_messages=False, read_message_history=True,
            ),
        }
        if not category:
            category = await guild.create_category(
                config.UNDERGROUND_CATEGORY_NAME,
                overwrites=overwrites,
                reason="GGMW9 CITY — fictional Underground setup",
            )
        else:
            try:
                await category.edit(overwrites=overwrites, reason="GGMW9 CITY — Underground permission repair")
            except (discord.Forbidden, discord.HTTPException):
                pass
        setup["category_id"] = category.id

        created, reused = [], []
        topics = {
            "shadow_gate": "GGMW9 Underground • hidden fictional career hub. Virtual game simulation only.",
            "black_market": "GGMW9 Underground • virtual game items and member-to-member escrow market.",
            "crews": "GGMW9 Underground • hidden crews, reputation and shared operations.",
            "contracts": "GGMW9 Underground • fictional missions and secret contracts.",
            "operations": "GGMW9 Underground • simulated high-risk operations. No real-world instructions.",
        }
        for key, name in config.UNDERGROUND_CHANNEL_NAMES.items():
            ch = guild.get_channel(int(channels.get(key) or 0)) if channels.get(key) else None
            if not isinstance(ch, discord.TextChannel):
                ch = discord.utils.get(category.text_channels, name=name)
            if not ch:
                ch = await guild.create_text_channel(
                    name,
                    category=category,
                    topic=topics.get(key, "GGMW9 Underground"),
                    overwrites=overwrites,
                    reason="GGMW9 CITY — Underground channel",
                )
                created.append(ch.mention)
            else:
                reused.append(ch.mention)
                try:
                    await ch.edit(
                        category=category,
                        topic=topics.get(key, ch.topic),
                        overwrites=overwrites,
                        reason="GGMW9 CITY — Underground repair",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass
            channels[key] = ch.id

        setup["complete"] = True
        setup["updated_at"] = _iso_ug()
        self.store.save()
        await self.repair_underground_permissions(guild)
        await self.refresh_underground_panels(guild)
        return {"ok": True, "category": category.mention, "created": created, "reused": reused}

    async def _set_underground_access(self, guild: discord.Guild, member: discord.Member, allow: bool) -> None:
        setup = self.underground(guild.id).get("setup", {})
        category = guild.get_channel(int(setup.get("category_id") or 0)) if setup.get("category_id") else None
        targets = [category] if isinstance(category, discord.CategoryChannel) else []
        for cid in (setup.get("channels") or {}).values():
            ch = guild.get_channel(int(cid or 0))
            if isinstance(ch, discord.TextChannel):
                targets.append(ch)
        for target in targets:
            try:
                if allow:
                    await target.set_permissions(
                        member,
                        view_channel=True,
                        read_message_history=True,
                        send_messages=False,
                        create_public_threads=False,
                        create_private_threads=False,
                        reason="GGMW9 Underground whitelist",
                    )
                else:
                    await target.set_permissions(member, overwrite=None, reason="GGMW9 Underground access removed")
            except (discord.Forbidden, discord.HTTPException):
                continue

    async def repair_underground_permissions(self, guild: discord.Guild) -> dict:
        ug = self.underground(guild.id)
        setup = ug.get("setup", {})
        if not setup.get("complete"):
            return {"ok": False, "error": "Underground مازال ما تدارش Setup."}
        locked = bool(ug.get("locked", False))
        active = 0
        for uid, row in list(ug.get("members", {}).items()):
            member = guild.get_member(int(uid))
            if not member:
                continue
            allow = bool(row.get("active")) and not locked
            await self._set_underground_access(guild, member, allow)
            if allow:
                active += 1
        owner = guild.owner
        if owner:
            await self._set_underground_access(guild, owner, True)
        self.store.save()
        return {"ok": True, "active": active, "locked": locked}

    async def create_underground_invite(self, guild: discord.Guild, target: discord.Member) -> tuple[bool, str]:
        if not (self.underground(guild.id).get("setup") or {}).get("complete"):
            return False, "دير **Setup / Repair** ديال Underground الأول، عاد بعث الدعوات."
        if target.bot:
            return False, "مايمكنش ندعو Bot."
        row = self.underground_member(guild.id, target.id)
        if row.get("active"):
            return False, "هاد العضو داخل Underground ديجا."
        ug = self.underground(guild.id)
        for inv in ug.setdefault("invites", {}).values():
            if int(inv.get("user_id", 0)) == target.id and inv.get("status") == "pending":
                exp = _parse(inv.get("expires_at"))
                if exp and underground_now() < exp:
                    return False, "عندو دعوة Pending ديجا."
        iid = self.store.next_underground_id(guild.id, "invite", "UGI")
        inv = {
            "id": iid, "user_id": target.id, "guild_id": guild.id,
            "status": "pending", "created_at": _iso_ug(),
            "expires_at": (underground_now()+timedelta(hours=config.UNDERGROUND_INVITE_HOURS)).isoformat(),
        }
        ug["invites"][iid] = inv
        self.store.save()
        from .underground_ui import UndergroundInviteView
        try:
            embed = discord.Embed(
                title="🌑 Unknown Contact",
                description=(
                    "عندك عرض خاص للدخول لعالم مخفي داخل **GGMW9 CITY**.\n\n"
                    "الدخول اختياري. إلا وافقت غادي يتحل ليك عالم إضافي ديال Game Careers، "
                    "Crews، Virtual Black Market وعمليات خيالية داخل اقتصاد السيرفر.\n\n"
                    "**هوية اللي بعث الدعوة ما كتبانش.**"
                ),
                color=discord.Color.dark_grey(),
                timestamp=underground_now(),
            )
            embed.set_footer(text=f"الدعوة كتسالي بعد {config.UNDERGROUND_INVITE_HOURS}h • GGMW9")
            await target.send(embed=embed, view=UndergroundInviteView(self))
        except (discord.Forbidden, discord.HTTPException):
            inv["status"] = "dm_failed"
            self.store.save()
            return False, "❌ DM ديال العضو مسدودة؛ الدعوة ما تبعثاتش وما تفعلاتش."
        return True, f"📨 تبعثات دعوة مجهولة لـ **{target.display_name}**."

    def _pending_invite_for_user(self, user_id: int) -> tuple[Optional[int], Optional[dict]]:
        newest = None
        for gid, g in self.store.data.items():
            if not isinstance(g, dict):
                continue
            ug = (g.get("underground") or {})
            for inv in (ug.get("invites") or {}).values():
                if int(inv.get("user_id", 0) or 0) != int(user_id) or inv.get("status") != "pending":
                    continue
                exp = _parse(inv.get("expires_at"))
                if not exp or underground_now() >= exp:
                    inv["status"] = "expired"
                    continue
                created = _parse(inv.get("created_at")) or underground_now()
                if newest is None or created > newest[0]:
                    newest = (created, int(gid), inv)
        self.store.save()
        return (newest[1], newest[2]) if newest else (None, None)

    async def answer_underground_invite(self, user: discord.User, accept: bool) -> tuple[bool, str]:
        guild_id, inv = self._pending_invite_for_user(user.id)
        if not inv or not guild_id:
            return False, "هاد الدعوة ما بقاتش صالحة أو تجاوبتي عليها من قبل."
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return False, "السيرفر ما متوفرش دابا."
        member = guild.get_member(user.id)
        if not member:
            return False, "خاصك تبقى عضو فالسيرفر باش تقبل الدعوة."
        if not accept:
            inv["status"] = "declined"; inv["answered_at"] = _iso_ug(); self.store.save()
            return True, "❌ رفضتي العرض. ما تبدل والو فحسابك."
        row = self.underground_member(guild_id, user.id, create=True)
        row["active"] = True
        row["joined_at"] = row.get("joined_at") or _iso_ug()
        inv["status"] = "accepted"; inv["answered_at"] = _iso_ug()
        self.store.save()
        if not self.underground(guild_id).get("locked", False):
            await self._set_underground_access(guild, member, True)
            return True, "🌑 **قبلتي العرض.** العالم المخفي تحل ليك دابا داخل GGMW9."
        return True, "🌑 **قبلتي العرض.** تسجلتي فالـwhitelist، ولكن Underground مسدود مؤقتاً من عند Owner."

    async def cancel_underground_invite(self, guild: discord.Guild, target: discord.Member) -> tuple[bool, str]:
        changed = 0
        for inv in self.underground(guild.id).setdefault("invites", {}).values():
            if int(inv.get("user_id", 0) or 0) == target.id and inv.get("status") == "pending":
                inv["status"] = "cancelled"
                inv["cancelled_at"] = _iso_ug()
                changed += 1
        if changed:
            self.store.save()
            return True, f"🗑️ تلغات الدعوة المعلقة ديال **{target.display_name}**."
        return False, "هاد العضو ما عندوش دعوة Pending."

    async def revoke_underground_access(self, guild: discord.Guild, target: discord.Member) -> tuple[bool, str]:
        row = self.underground_member(guild.id, target.id)
        if not row.get("active"):
            return False, "هاد العضو ماشي Active فـUnderground."
        row["active"] = False; row["revoked_at"] = _iso_ug()
        self.store.save()
        await self._set_underground_access(guild, target, False)
        return True, f"🚫 تحيد Underground access من **{target.display_name}**. History بقات محفوظة."

    async def set_underground_lock(self, guild: discord.Guild, locked: bool) -> tuple[bool, str]:
        self.underground(guild.id)["locked"] = bool(locked)
        self.store.save()
        await self.repair_underground_permissions(guild)
        return True, "🔒 Underground تسد على جميع الأعضاء." if locked else "🔓 Underground تحل للـwhitelist من جديد."

    async def choose_underground_path(self, guild: discord.Guild, member: discord.Member, path_id: str) -> tuple[bool, str]:
        if path_id not in UNDERGROUND_PATHS:
            return False, "Path ماشي موجودة."
        row = self.underground_member(guild.id, member.id, create=True)
        if not row.get("active"):
            return False, "ما عندكش Underground access."
        if row.get("path_id"):
            return False, "اخترتي Path ديالك ديجا. التغيير كيدوز من Owner دابا."
        row["path_id"] = path_id; row["path_started_at"] = _iso_ug()
        self.store.save()
        p = UNDERGROUND_PATHS[path_id]
        return True, f"🌑 وليتي **{p['emoji']} {p['name']}** فالعالم المخفي."

    async def start_underground_mission(self, guild: discord.Guild, member: discord.Member) -> tuple[bool, str, Optional[dict]]:
        row = self.underground_member(guild.id, member.id, create=True)
        if not row.get("active") or self.underground(guild.id).get("locked"):
            return False, "Underground access مسدود دابا.", None
        if not row.get("path_id"):
            return False, "اختار Underground Career الأول.", None
        active = row.get("mission") or {}
        if active.get("status") == "active":
            return True, "عندك Mission خدامة ديجا.", active
        ready, at = cooldown_ready(row.get("last_mission_at"), max(1, config.UNDERGROUND_MISSION_COOLDOWN_MINUTES)/60)
        if not ready:
            return False, f"⏳ Mission جديدة كتفتح <t:{int(at.timestamp())}:R>.", None
        prompt, options, correct = choose_mission(row["path_id"])
        mid = self.store.next_underground_id(guild.id, "operation", "UGM")
        mission = {"id":mid,"status":"active","prompt":prompt,"options":options,"correct":correct,"created_at":_iso_ug()}
        row["mission"] = mission
        self.store.save()
        return True, "🕳️ Contract جديدة تفتحات.", mission

    async def resolve_underground_mission(self, guild: discord.Guild, member: discord.Member, choice: int) -> tuple[bool, str, dict]:
        row = self.underground_member(guild.id, member.id, create=True)
        mission = row.get("mission") or {}
        if mission.get("status") != "active":
            return False, "ما عندك حتى Mission خدامة.", {}
        correct = int(choice) == int(mission.get("correct", 0))
        out = mission_outcome(correct=correct, reputation=int(row.get("reputation",0)), heat=int(row.get("heat",0)))
        mods = operation_modifiers(row.get("inventory", {}))
        if out["success"] and int(mods.get("mission_reward_bps", 0)):
            out["reward"] = int(out["reward"]) + int(out["reward"]) * int(mods["mission_reward_bps"]) // 10000
        out["heat"] = max(1, int(out.get("heat", 0)) - int(mods.get("heat_reduction", 0)) // 2)
        paid = 0
        if out["success"] and self.economy:
            paid = self.economy.city_underground_reward_to_bank(
                guild.id, member.id, int(out["reward"]), f"Underground mission {mission['id']}"
            )
        out["paid"] = paid
        row["reputation"] = max(0, int(row.get("reputation",0))+int(out["rep"]))
        row["heat"] = min(100, max(0, int(row.get("heat",0))+int(out["heat"])))
        row["heat_updated_at"] = _iso_ug()
        row["last_mission_at"] = _iso_ug()
        row["missions_done"] = int(row.get("missions_done",0))+1
        row["earned"] = int(row.get("earned",0))+paid
        crew_id = row.get("crew_id")
        if crew_id:
            crew = self.underground(guild.id).get("crews", {}).get(crew_id)
            if crew:
                crew["reputation"] = int(crew.get("reputation", 0) or 0) + (12 if out["success"] else 3)
                crew["missions_done"] = int(crew.get("missions_done", 0) or 0) + 1
        if out.get("item"):
            inv = row.setdefault("inventory", {})
            inv[out["item"]] = int(inv.get(out["item"],0))+1
        mission["status"] = "success" if out["success"] else "failed"
        mission["resolved_at"] = _iso_ug(); mission["outcome"] = out
        row["mission"] = None
        self.store.save()
        if out["success"]:
            item_txt = f"\n🎁 لقيتي **{VIRTUAL_ITEMS[out['item']]['name']}**" if out.get("item") else ""
            return True, f"✅ Mission نجحات • +{out['rep']} REP • +{out['heat']} Heat • Bank **{self.fmt(paid)}**{item_txt}", out
        return True, f"❌ Mission فشلات • +{out['rep']} REP • +{out['heat']} Heat • ماكاينش payout.", out

    async def buy_underground_supply(self, guild: discord.Guild, member: discord.Member, item_id: str) -> tuple[bool, str]:
        row = self.underground_member(guild.id, member.id, create=True)
        item = VIRTUAL_ITEMS.get(item_id)
        if not row.get("active") or not item:
            return False, "Item/access ماشي صالح."
        if int(row.get("reputation",0)) < int(item.get("rep",0)):
            return False, f"خاصك **{item['rep']} REP** باش يتحل هاد الـVirtual Item."
        if not self.economy or not self.economy.city_underground_supply_purchase(guild.id,member.id,int(item["price"]),f"Virtual item {item['name']}"):
            return False, "Wallet ماكافيش."
        inv=row.setdefault("inventory",{}); inv[item_id]=int(inv.get(item_id,0))+1; self.store.save()
        return True, f"✅ شريتي **{item['emoji']} {item['name']}** بـ{self.fmt(item['price'])}. هادي Game Item فقط."

    async def create_underground_listing(self, guild: discord.Guild, seller: discord.Member, item_id: str, price: int) -> tuple[bool, str]:
        row=self.underground_member(guild.id,seller.id,create=True); item=VIRTUAL_ITEMS.get(item_id); price=max(100,int(price))
        if not row.get("active") or not item: return False,"Item ماشي موجودة."
        inv=row.setdefault("inventory",{})
        if int(inv.get(item_id,0))<=0: return False,"ما عندكش هاد Item فالInventory."
        inv[item_id]=int(inv.get(item_id,0))-1
        lid=self.store.next_underground_id(guild.id,"listing","UGL")
        self.underground(guild.id)["listings"][lid]={"id":lid,"seller_id":seller.id,"item_id":item_id,"price":price,"status":"open","created_at":_iso_ug()}
        self.store.save(); return True,f"🕳️ Listing **{lid}** تفتحات بـ **{self.fmt(price)}**."

    async def cancel_underground_listing(self, guild: discord.Guild, seller: discord.Member, listing_id: str) -> tuple[bool, str]:
        async with self.lock:
            listing = self.underground(guild.id).get("listings", {}).get(str(listing_id))
            if not listing or listing.get("status") != "open":
                return False, "Listing ما بقاتش مفتوحة."
            if int(listing.get("seller_id", 0) or 0) != seller.id:
                return False, "Listing ماشي ديالك."
            item_id = listing.get("item_id")
            if item_id not in VIRTUAL_ITEMS:
                return False, "Virtual Item ما بقاتش معروفة."
            row = self.underground_member(guild.id, seller.id, create=True)
            inv = row.setdefault("inventory", {})
            inv[item_id] = int(inv.get(item_id, 0) or 0) + 1
            listing["status"] = "cancelled"
            listing["cancelled_at"] = _iso_ug()
            self.store.save()
            return True, f"↩️ Listing **{listing_id}** تلغات و**{VIRTUAL_ITEMS[item_id]['name']}** رجعات للInventory."

    async def buy_underground_listing(self, guild: discord.Guild, buyer: discord.Member, listing_id: str) -> tuple[bool, str]:
        async with self.lock:
            listing=self.underground(guild.id).get("listings",{}).get(listing_id)
            if not listing or listing.get("status")!="open": return False,"Listing ما بقاتش متاحة."
            if int(listing.get("seller_id",0))==buyer.id: return False,"مايمكنش تشري Listing ديالك."
            price=int(listing.get("price",0)); key=f"ugmarket:{listing_id}"
            if not self.economy or not self.economy.city_hold_escrow(guild.id,buyer.id,key,price,kind="underground_market",description=f"Virtual listing {listing_id}"):
                return False,"Wallet ماكافيش."
            res=self.economy.city_release_underground_escrow(guild.id,key,seller_id=int(listing["seller_id"]),tax_bps=config.UNDERGROUND_MARKET_TAX_BPS,description=f"Virtual listing {listing_id}")
            if int(res.get("gross",0))<=0:
                self.economy.city_refund_escrow(guild.id,key,reason="Underground listing release failed")
                return False,"تعذر settlement."
            listing["status"]="sold"; listing["buyer_id"]=buyer.id; listing["sold_at"]=_iso_ug(); listing["settlement"]=res
            br=self.underground_member(guild.id,buyer.id,create=True); inv=br.setdefault("inventory",{}); iid=listing["item_id"]; inv[iid]=int(inv.get(iid,0))+1
            self.store.save(); seller=guild.get_member(int(listing["seller_id"]))
            if seller:
                try: await seller.send(f"🌑 Listing **{listing_id}** تباعت. دخل للBank ديالك **{self.fmt(res['seller'])}**.")
                except (discord.Forbidden,discord.HTTPException): pass
            return True,f"✅ شريتي **{VIRTUAL_ITEMS[iid]['name']}**. Seller تخلص فBank وTax مشات Treasury."

    async def create_crew(self, guild: discord.Guild, leader: discord.Member, name: str) -> tuple[bool, str]:
        row=self.underground_member(guild.id,leader.id,create=True)
        if not row.get("active"): return False,"ما عندكش Underground access."
        if row.get("crew_id"): return False,"راك داخل Crew ديجا."
        name=" ".join(str(name).strip().split())[:32]
        if len(name)<3: return False,"سمية Crew قصيرة بزاف."
        cid=self.store.next_underground_id(guild.id,"crew","CRW")
        if not self.economy or not self.economy.city_crew_deposit(guild.id,leader.id,cid,config.UNDERGROUND_CREW_CREATE_COST):
            return False,f"خاصك **{self.fmt(config.UNDERGROUND_CREW_CREATE_COST)}** فالWallet باش تفتح Crew Vault."
        crew={"id":cid,"name":name,"leader_id":leader.id,"members":[leader.id],"reputation":0,"created_at":_iso_ug(),"last_heist_at":None}
        self.underground(guild.id)["crews"][cid]=crew; row["crew_id"]=cid; self.store.save()
        return True,f"👥 Crew **{name}** تخلقات • Vault البداية **{self.fmt(config.UNDERGROUND_CREW_CREATE_COST)}**."

    async def invite_to_crew(self, guild: discord.Guild, leader: discord.Member, target: discord.Member) -> tuple[bool, str]:
        lr=self.underground_member(guild.id,leader.id); cid=lr.get("crew_id"); crew=self.underground(guild.id).get("crews",{}).get(cid)
        tr=self.underground_member(guild.id,target.id)
        if not crew or int(crew.get("leader_id",0))!=leader.id: return False,"خاصك تكون Leader ديال Crew."
        if not tr.get("active"): return False,"هاد العضو ماشي داخل Underground."
        if tr.get("crew_id"): return False,"هاد العضو داخل Crew ديجا."
        self.underground(guild.id).setdefault("crew_invites",{})[str(target.id)]={
            "crew_id":cid,"from":leader.id,"created_at":_iso_ug(),
            "expires_at":(underground_now()+timedelta(hours=config.UNDERGROUND_CREW_INVITE_HOURS)).isoformat(),
        }; self.store.save()
        try: await target.send(f"👥 **دعوة Crew سرية**\nCrew: **{crew['name']}**\nدخل Underground → Crew باش تقبل أو ترفض.")
        except (discord.Forbidden,discord.HTTPException): pass
        return True,f"📨 تبعثات Crew invite لـ **{target.display_name}**."

    async def answer_crew_invite(self, guild: discord.Guild, member: discord.Member, accept: bool) -> tuple[bool, str]:
        ug=self.underground(guild.id); inv=ug.setdefault("crew_invites",{}).get(str(member.id))
        if not inv: return False,"ما عندك حتى Crew invite."
        exp=_parse(inv.get("expires_at"))
        if exp and underground_now()>=exp:
            ug["crew_invites"].pop(str(member.id),None); self.store.save(); return False,"Crew invite سالات الصلاحية ديالها."
        crew=ug.get("crews",{}).get(inv.get("crew_id"))
        if not crew: ug["crew_invites"].pop(str(member.id),None); self.store.save(); return False,"Crew ما بقاتش موجودة."
        if accept:
            row=self.underground_member(guild.id,member.id,create=True)
            if row.get("crew_id"): return False,"راك داخل Crew ديجا."
            crew.setdefault("members",[]).append(member.id); row["crew_id"]=crew["id"]
            msg=f"✅ دخلتي Crew **{crew['name']}**."
        else:
            msg="❌ رفضتي Crew invite."
        ug["crew_invites"].pop(str(member.id),None); self.store.save(); return True,msg

    async def crew_deposit(self, guild: discord.Guild, member: discord.Member, amount: int) -> tuple[bool, str]:
        row=self.underground_member(guild.id,member.id); cid=row.get("crew_id")
        if not cid: return False,"ما عندكش Crew."
        amount=max(100,int(amount))
        if not self.economy or not self.economy.city_crew_deposit(guild.id,member.id,cid,amount): return False,"Wallet ماكافيش."
        return True,f"🏦 زدتي **{self.fmt(amount)}** لـCrew Vault."

    async def set_heist_ready(self, guild: discord.Guild, member: discord.Member, ready: bool = True) -> tuple[bool, str]:
        row=self.underground_member(guild.id,member.id,create=True); cid=row.get("crew_id")
        crew=self.underground(guild.id).get("crews",{}).get(cid) if cid else None
        if not row.get("active") or not crew:
            return False,"خاصك تكون داخل Crew Active."
        row["heist_ready"]=bool(ready); row["heist_ready_at"]=_iso_ug() if ready else None; self.store.save()
        return True,"✅ تسجلتي Ready للعملية الجاية." if ready else "⏸️ تحيدات Ready ديالك."

    async def start_virtual_heist(self, guild: discord.Guild, leader: discord.Member) -> tuple[bool, str, Optional[dict]]:
        row=self.underground_member(guild.id,leader.id); cid=row.get("crew_id"); crew=self.underground(guild.id).get("crews",{}).get(cid)
        if not crew or int(crew.get("leader_id",0))!=leader.id: return False,"غير Crew Leader يقدر يبدا العملية.",None
        active_members=[]
        for uid in crew.get("members",[]):
            uid=int(uid); mr=self.underground_member(guild.id,uid)
            if not mr.get("active") or not guild.get_member(uid): continue
            if uid==leader.id or mr.get("heist_ready"):
                active_members.append(uid)
        if len(active_members)<config.UNDERGROUND_HEIST_MIN_CREW:
            return False,f"خاص **{config.UNDERGROUND_HEIST_MIN_CREW} أعضاء Ready** على الأقل. باقي الأعضاء يدخلو Operations ويديرو Ready.",None
        if int(crew.get("reputation",0))<config.UNDERGROUND_HEIST_MIN_REP: return False,f"Crew خاصها **{config.UNDERGROUND_HEIST_MIN_REP} REP**.",None
        if int(row.get("heat",0))>60: return False,"Heat ديالك طالعة بزاف. خليه يبرد قبل عملية كبيرة.",None
        ready,at=cooldown_ready(crew.get("last_heist_at"),config.UNDERGROUND_HEIST_COOLDOWN_HOURS)
        if not ready: return False,f"⏳ Bank Operation كتفتح <t:{int(at.timestamp())}:R>.",None
        if not self.economy: return False,"Economy ماشي محملة.",None
        treasury=int(self.economy._system(guild.id).get("treasury",0) or 0)
        if treasury<config.UNDERGROUND_HEIST_MIN_TREASURY: return False,f"🏦 Bank reserve خاصها تكون على الأقل **{self.fmt(config.UNDERGROUND_HEIST_MIN_TREASURY)}** باش العملية تكون منطقية.",None
        if not self.economy.city_crew_spend(guild.id,cid,config.UNDERGROUND_HEIST_PREP_COST,f"Virtual bank operation prep {cid}"):
            return False,f"Crew Vault خاصها **{self.fmt(config.UNDERGROUND_HEIST_PREP_COST)}** للتحضير.",None
        oid=self.store.next_underground_id(guild.id,"operation","UGH")
        mods=operation_modifiers(row.get("inventory",{}))
        op={"id":oid,"crew_id":cid,"leader_id":leader.id,"participants":active_members,"status":"active","stage":0,"correct_steps":0,"created_at":_iso_ug(),"stages":prepare_heist_stages(),"equipment_mods":mods}
        self.underground(guild.id)["operations"][oid]=op; crew["last_heist_at"]=_iso_ug()
        for uid in active_members:
            mr=self.underground_member(guild.id,uid,create=True); mr["heist_ready"]=False; mr["heist_ready_at"]=None
        self.store.save()
        for uid in active_members:
            if uid==leader.id: continue
            m=guild.get_member(uid)
            if m:
                try: await m.send(f"🌑 Crew ديالك بدات **Virtual Bank Operation {oid}** وانت مسجل Participant. النتيجة غادي توصلك فالـDM.")
                except (discord.Forbidden,discord.HTTPException): pass
        return True,f"🏦 **Virtual Bank Operation {oid}** بدات بـ**{len(active_members)} Participants**. Preparation خرجات من Crew Vault.",op

    async def resolve_virtual_heist_step(self, guild: discord.Guild, leader: discord.Member, operation_id: str, choice: int) -> tuple[bool,str,Optional[dict]]:
        async with self.lock:
            ug=self.underground(guild.id); op=ug.get("operations",{}).get(operation_id)
            if not op or op.get("status")!="active" or int(op.get("leader_id",0))!=leader.id: return False,"Operation ماشي Active ديالك.",None
            stage=int(op.get("stage",0))
            stages=op.get("stages") or HEIST_STAGES
            if stage>=len(stages): return False,"Operation سالات.",op
            spec=stages[stage]
            if int(choice)==int(spec["correct"]): op["correct_steps"]=int(op.get("correct_steps",0))+1
            op["stage"]=stage+1
            if op["stage"]<len(stages): self.store.save(); return True,"✅ Phase تسجلات. المرحلة الجاية واجدة.",op
            crew=ug.get("crews",{}).get(op["crew_id"]) or {}; row=self.underground_member(guild.id,leader.id,create=True)
            mods=op.get("equipment_mods") or operation_modifiers(row.get("inventory",{}))
            chance=heist_success_chance(crew_reputation=int(crew.get("reputation",0)),leader_heat=int(row.get("heat",0)),correct_steps=int(op.get("correct_steps",0)),equipment_bonus=int(mods.get("chance_bonus",0)))
            import secrets
            success=secrets.randbelow(100)<chance
            op["chance"]=chance; op["resolved_at"]=_iso_ug(); op["status"]="success" if success else "failed"
            participants=[int(x) for x in op.get("participants",[]) if guild.get_member(int(x))]
            if success:
                gross=heist_gross_reward(len(participants)); gross += gross * int(mods.get("reward_bps",0)) // 10000
                payout=self.economy.city_underground_heist_payout(guild.id,op["crew_id"],participants,gross,crew_share_bps=config.UNDERGROUND_CREW_HEIST_SHARE_BPS,description=f"Virtual bank operation {operation_id}") if self.economy else {"gross":0,"crew":0,"members":{}}
                op["payout"]=payout; crew["reputation"]=int(crew.get("reputation",0))+70
                for uid in participants:
                    r=self.underground_member(guild.id,uid,create=True); r["reputation"]=int(r.get("reputation",0))+35; r["heat"]=min(100,int(r.get("heat",0))+max(5,18-int(mods.get("heat_reduction",0)))); r["heat_updated_at"]=_iso_ug(); r["earned"]=int(r.get("earned",0))+int((payout.get("members") or {}).get(uid,0))
                msg=f"✅ العملية نجحات • Gross **{self.fmt(payout.get('gross',0))}** • Crew Vault +**{self.fmt(payout.get('crew',0))}** • الباقي تقسم على المشاركين."
            else:
                crew["reputation"]=int(crew.get("reputation",0))+10
                for uid in participants:
                    r=self.underground_member(guild.id,uid,create=True); r["reputation"]=int(r.get("reputation",0))+5; r["heat"]=min(100,int(r.get("heat",0))+max(12,30-int(mods.get("heat_reduction",0)))); r["heat_updated_at"]=_iso_ug()
                msg="❌ العملية فشلات. Preparation تضاعت وHeat طلعات، ولكن ما تمسات حتى فلوس ديال حسابات الأعضاء فالبنك."
            self.store.save()
            for uid in participants:
                m=guild.get_member(uid)
                if m:
                    try: await m.send(f"🌑 **{operation_id}**\n{msg}")
                    except (discord.Forbidden,discord.HTTPException): pass
            return True,msg,op

    def underground_profile_embed(self, guild: discord.Guild, member: discord.Member) -> discord.Embed:
        row=self.underground_member(guild.id,member.id,create=True); path=UNDERGROUND_PATHS.get(row.get("path_id")); crew=self.underground(guild.id).get("crews",{}).get(row.get("crew_id")) if row.get("crew_id") else None
        e=discord.Embed(title="🌑 Underground Identity",description="هوية سرية مخزنة بالـDiscord ID فقط • بلا Role علنية.",color=discord.Color.dark_grey())
        e.add_field(name="🕴️ Path",value=f"{path['emoji']} {path['name']}" if path else "❔ مازال ما اخترتيش",inline=False)
        e.add_field(name="⭐ Reputation",value=str(int(row.get("reputation",0))),inline=True); e.add_field(name="🔥 Heat",value=f"{int(row.get('heat',0))}/100",inline=True)
        e.add_field(name="👥 Crew",value=crew.get("name") if crew else "—",inline=True); e.add_field(name="💵 Underground Earned",value=self.fmt(int(row.get("earned",0))),inline=True)
        inv=row.get("inventory",{}) or {}; items=[f"{VIRTUAL_ITEMS[k]['emoji']} {VIRTUAL_ITEMS[k]['name']} ×{v}" for k,v in inv.items() if k in VIRTUAL_ITEMS and int(v)>0]
        e.add_field(name="🎒 Virtual Inventory",value="\n".join(items[:10]) if items else "فارغة",inline=False); e.set_footer(text="Game simulation only • لا تعليمات ولا معاملات خارج السيرفر")
        return e

    def underground_owner_embed(self, guild: discord.Guild) -> discord.Embed:
        ug=self.underground(guild.id); active=sum(1 for x in ug.get("members",{}).values() if x.get("active")); pending=sum(1 for x in ug.get("invites",{}).values() if x.get("status")=="pending")
        e=discord.Embed(title="🌑 Owner — Underground Control",description="أنت وحدك كتقرر شكون يقدر يدخل. Access بالـDiscord ID + permission overwrites، بلا Role علنية.",color=discord.Color.dark_grey())
        e.add_field(name="👥 Active",value=str(active),inline=True); e.add_field(name="📨 Pending Invites",value=str(pending),inline=True); e.add_field(name="🔒 Status",value="LOCKED" if ug.get("locked") else "OPEN TO WHITELIST",inline=True)
        return e

    async def underground_diagnostics(self, guild: discord.Guild) -> dict:
        rows=[]; ug=self.underground(guild.id); setup=ug.get("setup",{}); eco=self.economy
        rows.append(("Underground setup",bool(setup.get("complete"))))
        cat=guild.get_channel(int(setup.get("category_id") or 0)) if setup.get("category_id") else None
        rows.append(("Hidden category",isinstance(cat,discord.CategoryChannel)))
        if isinstance(cat,discord.CategoryChannel):
            rows.append(("@everyone hidden",cat.overwrites_for(guild.default_role).view_channel is False))
            owner=guild.owner
            rows.append(("Owner explicit access",bool(owner and cat.overwrites_for(owner).view_channel is True)))
        for key in config.UNDERGROUND_CHANNEL_NAMES:
            ch=self.underground_channel(guild,key); exists=isinstance(ch,discord.TextChannel); rows.append((f"Channel {key}",exists))
            if exists:
                rows.append((f"Hidden {key}",ch.overwrites_for(guild.default_role).view_channel is False))
        locked=bool(ug.get("locked"))
        whitelist_ok=True
        if isinstance(cat,discord.CategoryChannel):
            for uid,row in (ug.get("members") or {}).items():
                if not row.get("active"): continue
                member=guild.get_member(int(uid))
                if not member: continue
                ov=cat.overwrites_for(member).view_channel
                expected = False if locked else True
                # Locked members normally have no explicit overwrite (None); both
                # None and False are safe because @everyone is denied.
                if (expected and ov is not True) or (not expected and ov is True):
                    whitelist_ok=False; break
        rows.append(("Whitelist permission parity",whitelist_ok))
        rows.append(("Economy bridge",bool(eco and all(hasattr(eco,x) for x in ("city_underground_reward_to_bank","city_release_underground_escrow","city_crew_deposit","city_underground_heist_payout")))))
        persistent_names={type(v).__name__ for v in getattr(self.bot,"persistent_views",[]) or []}
        for name in ("UndergroundGatePublicView","UndergroundMarketPublicView","UndergroundCrewsPublicView","UndergroundOperationsPublicView","UndergroundInviteView"):
            rows.append((f"Persistent {name}",name in persistent_names))
        admin_exposure=[]
        for m in guild.members:
            if m.bot or m.id==guild.owner_id: continue
            if m.guild_permissions.administrator:
                admin_exposure.append(m.display_name)
        return {"checks":rows,"admin_exposure":admin_exposure,"ok":all(v for _,v in rows)}

    async def refresh_underground_panels(self, guild: discord.Guild):
        from .underground_ui import UndergroundGatePublicView, UndergroundMarketPublicView, UndergroundCrewsPublicView, UndergroundOperationsPublicView
        mapping={
            "shadow_gate":("shadow_gate","🌑・THE UNDERGROUND","العالم المخفي مفتوح فقط للـIDs اللي وافقو على دعوة Owner.",UndergroundGatePublicView(self)),
            "black_market":("black_market","🗡️・BLACK MARKET","Virtual Game Items + P2P Escrow. ماكاين حتى بيع/شراء خارج السيرفر.",UndergroundMarketPublicView(self)),
            "crews":("crews","👥・CREWS","صاوب Crew، جمع Reputation وخدم عمليات مشتركة.",UndergroundCrewsPublicView(self)),
            "operations":("operations","🏦・OPERATIONS","عمليات ومحاكاة Bank Heist خيالية؛ حسابات الأعضاء الشخصية محمية.",UndergroundOperationsPublicView(self)),
            "contracts":("contracts","📜・CONTRACTS","Missions ديال Underground Paths وReputation/Heat.",UndergroundGatePublicView(self)),
        }
        setup=self.underground(guild.id).setdefault("setup",{}); panels=setup.setdefault("panels",{})
        for key,(pkey,title,desc,view) in mapping.items():
            ch=self.underground_channel(guild,key)
            if not isinstance(ch,discord.TextChannel): continue
            e=discord.Embed(title=title,description=desc,color=discord.Color.dark_grey()); e.set_footer(text=f"GGMW9 UNDERGROUND • {pkey}")
            def remember(message_id: int, panel_key=pkey):
                panels[panel_key] = int(message_id)

            await upsert_fixed_panel(
                self.bot,
                ch,
                key=f"underground:{pkey}",
                matches=lambda message, panel_key=pkey: (
                    message.author == self.bot.user
                    and bool(message.embeds)
                    and f"GGMW9 UNDERGROUND • {panel_key}" in (
                        message.embeds[0].footer.text if message.embeds[0].footer else ""
                    )
                ),
                embed=e,
                view=view,
                message_id=panels.get(pkey),
                save_message_id=remember,
                history_limit=100,
            )
        self.store.save()
