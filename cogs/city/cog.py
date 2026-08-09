# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

import discord
from discord.ext import commands, tasks

import games_config as root_cfg
from . import config
from .storage import CityStore
from .careers import CAREERS, SKILLS, career_name, career_rank, next_rank, all_business_ids
from .matching import match_careers
from .services import SERVICES, service_name
from .shifts import local_now, can_work_today, build_shift, shift_due, checkin_ready, calculate_shift_pay
from .payroll import next_pay_at, pay_due
from .projects import parse_milestones, current_milestone
from .notifications import CityNotifier
from .underground_engine import UndergroundEngineMixin
from cogs.panel_registry import panel_lock, upsert_fixed_panel


def _iso_now() -> str:
    return datetime.now(ZoneInfo(config.TIMEZONE)).isoformat()


def _parse_dt(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


PROFILE_DEFAULTS = {
    "cv": {},
    "bank_linked": False,
    "job_id": None,
    "job_started_at": None,
    "last_job_change": None,
    "career_progress": {},
    "active_shift": None,
    "pending_wages": 0,
    "unpaid_wages": 0,
    "next_pay_at": None,
    "notifications": dict(config.DEFAULT_NOTIFICATIONS),
    "rating_sum": 0,
    "rating_count": 0,
    "stats": {"shifts":0,"services":0,"projects":0,"on_time":0,"missed":0,"earned":0},
    "week_stats": {"week":"","shifts":0,"services":0,"projects":0,"score":0},
    "last_active": None,
}


class CareerCity(UndergroundEngineMixin, commands.Cog):
    """GGMW9 CITY — careers, services, payroll and projects."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = CityStore()
        self.lock = asyncio.Lock()
        self.notifier = CityNotifier(bot, self.store)
        self._ready_once = False

    # ------------------------------------------------------------------
    # Basic helpers
    # ------------------------------------------------------------------
    @property
    def economy(self):
        return self.bot.get_cog("Economy")

    def profile(self, guild_id: int, user_id: int) -> dict:
        p = self.store.profile(guild_id, user_id, PROFILE_DEFAULTS)
        # Deep-ish migration/defaults for old entries.
        p.setdefault("cv", {})
        p.setdefault("career_progress", {})
        p.setdefault("stats", {}).update({k:p.setdefault("stats", {}).get(k, v) for k,v in PROFILE_DEFAULTS["stats"].items() if k not in p.setdefault("stats", {})})
        p.setdefault("week_stats", {})
        for k,v in PROFILE_DEFAULTS["week_stats"].items():
            p["week_stats"].setdefault(k,v)
        p.setdefault("notifications", dict(config.DEFAULT_NOTIFICATIONS))
        for k,v in config.DEFAULT_NOTIFICATIONS.items():
            p["notifications"].setdefault(k,v)
        return p

    def progress(self, guild_id: int, user_id: int, career_id: Optional[str] = None) -> dict:
        p = self.profile(guild_id, user_id)
        career_id = career_id or p.get("job_id")
        if not career_id:
            return {"xp":0,"stats":{"shifts":0,"services":0,"projects":0}}
        cp = p.setdefault("career_progress", {}).setdefault(career_id, {"xp":0,"stats":{"shifts":0,"services":0,"projects":0}})
        cp.setdefault("xp",0); cp.setdefault("stats",{})
        for k in ("shifts","services","projects"):
            cp["stats"].setdefault(k,0)
        return cp

    def lang(self, guild_id: int, user_id: int) -> str:
        getter = (getattr(self.bot, "gg", {}) or {}).get("get_panel_language")
        if getter:
            try:
                value = getter(guild_id, user_id)
                if value in config.LANGUAGES:
                    return value
            except Exception:
                pass
        return "darija"

    def set_lang(self, guild_id: int, user_id: int, lang: str) -> str:
        lang = lang if lang in config.LANGUAGES else "darija"
        setter = (getattr(self.bot, "gg", {}) or {}).get("set_panel_language")
        if setter:
            try:
                return setter(guild_id,user_id,lang)
            except Exception:
                pass
        return lang

    def channel(self, guild: discord.Guild, key: str):
        setup = self.store.guild(guild.id).get("setup", {})
        cid = int((setup.get("channels") or {}).get(key) or 0)
        return guild.get_channel(cid) if cid else None

    def fmt(self, amount: int) -> str:
        return root_cfg.fmt_money(int(amount))

    def rating(self, guild_id: int, user_id: int) -> float:
        p = self.profile(guild_id,user_id)
        n = int(p.get("rating_count",0) or 0)
        return round(int(p.get("rating_sum",0) or 0)/n,2) if n else 0.0

    def _touch(self, guild_id: int, user_id: int):
        self.profile(guild_id,user_id)["last_active"] = _iso_now()

    def _week_key(self) -> str:
        now = local_now()
        y,w,_ = now.isocalendar()
        return f"{y}-W{w:02d}"

    def _bump_week(self, profile: dict, *, shifts=0, services=0, projects=0, score=0):
        key=self._week_key(); ws=profile.setdefault("week_stats",{})
        if ws.get("week") != key:
            if ws.get("week"):
                profile["previous_week_stats"] = dict(ws)
            ws.clear(); ws.update({"week":key,"shifts":0,"services":0,"projects":0,"score":0})
        ws["shifts"] += shifts; ws["services"] += services; ws["projects"] += projects; ws["score"] += score

    # ------------------------------------------------------------------
    # Career benefits integrated into Economy
    # ------------------------------------------------------------------
    def get_shop_discount_percent(self, guild_id: int, user_id: int) -> int:
        p=self.profile(guild_id,user_id); job=p.get("job_id")
        if not job or job not in CAREERS: return 0
        idx,_=career_rank(job,int(self.progress(guild_id,user_id,job).get("xp",0) or 0))
        arr=CAREERS[job].get("benefits",{}).get("shop_discount_by_rank",[0])
        return int(arr[min(idx,len(arr)-1)] if arr else 0)

    def get_bank_interest_bonus_bps(self, guild_id: int, user_id: int) -> int:
        p=self.profile(guild_id,user_id); job=p.get("job_id")
        if not job or job not in CAREERS: return 0
        idx,_=career_rank(job,int(self.progress(guild_id,user_id,job).get("xp",0) or 0))
        arr=CAREERS[job].get("benefits",{}).get("bank_bps_by_rank",[0])
        return int(arr[min(idx,len(arr)-1)] if arr else 0)

    # ------------------------------------------------------------------
    # Setup: category, channels, permissions, public panels
    # ------------------------------------------------------------------
    async def setup_city(self, guild: discord.Guild, *, force: bool = False) -> dict:
        if not guild.me or not guild.me.guild_permissions.manage_channels:
            return {"ok":False,"error":"البوت خاصو Manage Channels."}

        gdata=self.store.guild(guild.id); setup=gdata.setdefault("setup",{}); channels=setup.setdefault("channels",{})
        category = guild.get_channel(int(setup.get("category_id") or 0)) if setup.get("category_id") else None
        if not isinstance(category, discord.CategoryChannel):
            category = discord.utils.get(guild.categories, name=config.CATEGORY_NAME)
        if not category:
            category = await guild.create_category(config.CATEGORY_NAME, reason="GGMW9 CITY setup")
        setup["category_id"] = category.id

        everyone = guild.default_role
        bot_member = guild.me
        overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=True, send_messages=False, add_reactions=False, create_public_threads=False, create_private_threads=False, send_messages_in_threads=False),
            bot_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True, read_message_history=True, manage_messages=True),
        }

        created=[]; reused=[]
        for key,name in config.CHANNEL_NAMES.items():
            ch = guild.get_channel(int(channels.get(key) or 0)) if channels.get(key) else None
            if not isinstance(ch, discord.TextChannel):
                ch = discord.utils.get(category.text_channels, name=name)
            if not ch:
                ch = await guild.create_text_channel(name, category=category, topic=config.CHANNEL_TOPICS.get(key,"GGMW9 CITY"), overwrites=overwrites, reason="GGMW9 CITY setup")
                created.append(ch.mention)
            else:
                reused.append(ch.mention)
                try:
                    await ch.edit(category=category, topic=config.CHANNEL_TOPICS.get(key,ch.topic), overwrites=overwrites, reason="GGMW9 CITY repair")
                except discord.HTTPException:
                    pass
            channels[key]=ch.id

        setup["complete"] = True; setup["timezone"] = config.TIMEZONE; setup["updated_at"]=_iso_now()
        self.store.save()

        eco=self.economy
        seed={"seeded":0,"businesses":0}
        if eco and hasattr(eco,"city_seed_business_payroll"):
            seed=eco.city_seed_business_payroll(guild.id, all_business_ids())
            try: await eco.refresh_economy_stats(guild)
            except Exception: pass

        await self.refresh_city_panels(guild)
        return {"ok":True,"created":created,"reused":reused,"category":category.mention,"seed":seed}

    async def _upsert_panel(self, channel: discord.TextChannel, *, key: str, embed: discord.Embed, view: discord.ui.View | None):
        g=self.store.guild(channel.guild.id); panels=g.setdefault("setup",{}).setdefault("panels",{})
        mid=int(panels.get(key) or 0)

        def remember(message_id: int):
            panels[key] = int(message_id)
            self.store.save()

        return await upsert_fixed_panel(
            self.bot,
            channel,
            key=f"city:{key}",
            matches=lambda message: (
                message.author == self.bot.user
                and bool(message.embeds)
                and f"CITY:{key}" in (
                    message.embeds[0].footer.text if message.embeds[0].footer else ""
                )
            ),
            content=None,
            embed=embed,
            view=view,
            message_id=mid,
            save_message_id=remember,
            history_limit=100,
        )

    async def refresh_city_panels(self, guild: discord.Guild):
        from .ui import CareerPublicView, ServicesPublicView, ProjectsPublicView
        cc=self.channel(guild,"career_center"); sm=self.channel(guild,"services_market"); pb=self.channel(guild,"projects_board"); jm=self.channel(guild,"job_market"); alerts=self.channel(guild,"city_alerts")
        if isinstance(cc,discord.TextChannel): await self._upsert_panel(cc,key="career",embed=self.build_career_public_embed(guild),view=CareerPublicView(self))
        if isinstance(sm,discord.TextChannel): await self._upsert_panel(sm,key="services",embed=self.build_services_public_embed(guild),view=ServicesPublicView(self))
        if isinstance(pb,discord.TextChannel): await self._upsert_panel(pb,key="projects",embed=self.build_projects_public_embed(guild),view=ProjectsPublicView(self))
        if isinstance(jm,discord.TextChannel): await self._upsert_panel(jm,key="market",embed=self.build_job_market_embed(guild),view=None)
        if isinstance(alerts,discord.TextChannel): await self._upsert_panel(alerts,key="alerts",embed=self.build_alerts_embed(guild),view=None)

    # ------------------------------------------------------------------
    # Embeds
    # ------------------------------------------------------------------
    def build_career_public_embed(self, guild: discord.Guild):
        e=discord.Embed(title="🏙️ GGMW9 CITY — مركز العمل",description=(
            "**خدم، بيع خدماتك، قبض فالBank وتطور فالمهنة ديالك.**\n\n"
            "🧾 صاوب CV حقيقية بمهاراتك وشنو كتعرف تدير فالواقع.\n"
            "🎯 البوت كيعطيك Jobs مناسبة ليك بالـMatch Score، ماشي عشوائياً.\n"
            "🏦 الرواتب والعمولات كيمشيو مباشرة للادخار فـGGMW9 Bank.\n"
            "🕐 التوقيت الرسمي: **Africa/Casablanca** • الشيفتات والـWeekend بالوقت الحقيقي.\n"
            "📩 التنبيهات: DM أولاً، و`city-alerts` غير fallback بلا تفاصيل خاصة."
        ),color=discord.Color.blurple(),timestamp=datetime.now())
        e.add_field(name="💼 18 مهنة",value="ضيافة • عمليات • ترفيه • إعلام • موضة وجمال • تقنية • أعمال",inline=False)
        e.add_field(name="💵 اقتصاد حقيقي",value="الزبون كيخلص → Escrow → العامل/الشركة/الخزينة. Salary كتخرج من Payroll Reserve.",inline=False)
        e.set_footer(text="GGMW9 CITY • CITY:career • الدارجة هي الواجهة العامة")
        return e

    def build_services_public_embed(self,guild):
        workers=sum(1 for p in self.store.guild(guild.id).get("profiles",{}).values() if p.get("job_id"))
        open_orders=sum(1 for o in self.store.guild(guild.id).get("orders",{}).values() if o.get("status") not in {"completed","refunded","rejected","cancelled"})
        e=discord.Embed(title="🛍️ GGMW9 CITY — سوق الخدمات",description=(
            "شري خدمة **من عضو خدام بصح**. فلوسك كتدخل Escrow وماتتحررش حتى الخدمة توصل أو النظام يطلقها حسب القواعد.\n\n"
            "💄 ميكاب • 👗 ستايل • 🎨 تصميم • 💻 Tech • 📸 تصوير • 🎤 Events • ☕ Café • 🏠 Assets…"
        ),color=discord.Color.green(),timestamp=datetime.now())
        e.add_field(name="👷 خدامين حالياً",value=str(workers),inline=True); e.add_field(name="📦 طلبات مفتوحة",value=str(open_orders),inline=True)
        e.set_footer(text="GGMW9 CITY • CITY:services • الدفع من Wallet، الاستلام للعامل فـBank")
        return e

    def build_projects_public_embed(self,guild):
        projects=self.store.guild(guild.id).get("projects",{}); open_n=sum(1 for p in projects.values() if p.get("status") in {"open","assigned","in_progress","delivered"})
        budget=sum(int(p.get("budget",0) or 0) for p in projects.values() if p.get("status") in {"open","assigned","in_progress","delivered"})
        e=discord.Embed(title="🏗️ GGMW9 CITY — المشاريع والعقود",description=(
            "عندك فلوس وفكرة؟ حط Budget حقيقي، اختار Career المطلوبة، وخلي أعضاء المدينة يقدمو يخدمو عندك.\n"
            "الميزانية كتتحجز كاملة فـEscrow، وتتحرر للعامل غير مع Milestones المقبولة."
        ),color=discord.Color.orange(),timestamp=datetime.now())
        e.add_field(name="🏗️ مشاريع خدامة",value=str(open_n),inline=True); e.add_field(name="💰 Budget محجوز",value=self.fmt(budget),inline=True)
        e.set_footer(text="GGMW9 CITY • CITY:projects • حتى 3 Milestones لكل مشروع")
        return e

    def build_alerts_embed(self,guild):
        e=discord.Embed(title="🔔 GGMW9 CITY — تنبيهات احتياطية",description=(
            "هاد القناة **Fallback فقط** إلا كان DM مسدود.\n\n"
            "ما كيبان هنا لا Salary، لا اسم الزبون، لا قيمة Contract. غير تنبيه أنك عندك Update خاص فـCareer Center.\n"
            f"التنبيهات كتتحيد أوتوماتيكياً من بعد **{config.ALERT_DELETE_SECONDS//60} دقيقة**."
        ),color=discord.Color.dark_teal()); e.set_footer(text="GGMW9 CITY • CITY:alerts • الخصوصية أولاً"); return e

    def build_job_market_embed(self,guild):
        g=self.store.guild(guild.id); profiles=g.get("profiles",{}); orders=g.get("orders",{}); projects=g.get("projects",{})
        employed=[p for p in profiles.values() if p.get("job_id")]
        demand={cid:0 for cid in CAREERS}
        for o in orders.values():
            if o.get("status") in {"pending_worker","accepted","delivered"}: demand[o.get("career_id")]=demand.get(o.get("career_id"),0)+1
        for p in projects.values():
            if p.get("status") in {"open","assigned","in_progress","delivered"}: demand[p.get("career_id")]=demand.get(p.get("career_id"),0)+2
        workers={cid:0 for cid in CAREERS}
        for p in employed:
            if p.get("job_id") in workers: workers[p["job_id"]]+=1
        ranked=sorted(CAREERS,key=lambda cid:(demand.get(cid,0)-workers.get(cid,0),demand.get(cid,0)),reverse=True)[:6]
        lines=[]
        for cid in ranked:
            c=CAREERS[cid]; pressure=demand.get(cid,0)-workers.get(cid,0)
            badge="🔥 طلب قوي" if pressure>=2 else "🟡 مطلوب" if pressure>=0 else "🟢 متوازن"
            lines.append(f"{c['emoji']} **{career_name(cid)}** — {badge} • خدامين {workers.get(cid,0)} • طلب {demand.get(cid,0)}")
        week=g.get("employee_week",{}); hero="—"
        if week.get("user_id"):
            m=guild.get_member(int(week["user_id"])); hero=m.mention if m else f"<@{week['user_id']}>"
        e=discord.Embed(title="📊 GGMW9 CITY — سوق الشغل المباشر",description="\n".join(lines) or "مازال السوق جديد.",color=discord.Color.gold(),timestamp=datetime.now())
        e.add_field(name="👥 الموظفين",value=str(len(employed)),inline=True); e.add_field(name="📦 الطلبات",value=str(sum(1 for x in orders.values() if x.get('status') not in {'completed','refunded','cancelled','rejected'})),inline=True); e.add_field(name="🏆 موظف الأسبوع",value=hero,inline=True)
        e.set_footer(text=f"GGMW9 CITY • CITY:market • تحديث كل {config.JOB_MARKET_REFRESH_MINUTES} دقائق • Africa/Casablanca")
        return e

    def build_profile_embed(self,guild:discord.Guild,member:discord.Member,lang="darija"):
        p=self.profile(guild.id,member.id); job=p.get("job_id"); cv=p.get("cv") or {}; eco=self.economy
        if not job:
            desc="مازال ما خدامش. صايب CV وخلي النظام يقترح عليك الخدمات المناسبة." if lang=="darija" else "Not employed yet. Create a CV and get matched." if lang=="en" else "Pas encore employé. Crée ton CV et obtiens des recommandations."
            e=discord.Embed(title=f"💼 {member.display_name}",description=desc,color=discord.Color.blurple())
        else:
            cp=self.progress(guild.id,member.id,job); idx,rank=career_rank(job,int(cp.get("xp",0))); nxt=next_rank(job,int(cp.get("xp",0))); c=CAREERS[job]
            e=discord.Embed(title=f"{c['emoji']} {career_name(job,lang)} — {member.display_name}",description=f"**{rank['name']}** • Career XP **{int(cp.get('xp',0)):,}**",color=discord.Color.green())
            e.add_field(name="💵 الأجر" if lang=="darija" else "💵 Pay",value=f"{self.fmt(c['hourly'])}/h • {c['pay_cycle']}",inline=True)
            e.add_field(name="🏦 Direct Deposit",value="✅ Savings" if p.get("bank_linked") else "❌",inline=True)
            e.add_field(name="⭐ Rating",value=(f"{self.rating(guild.id,member.id):.2f}/5" if p.get('rating_count') else "New"),inline=True)
            if nxt: e.add_field(name="🚀 الترقية الجاية",value=f"{nxt['name']} عند **{nxt['xp']:,} XP**",inline=False)
            e.add_field(name="💰 مستحقات مجمعة",value=self.fmt(int(p.get("pending_wages",0) or 0)+int(p.get("unpaid_wages",0) or 0)),inline=True)
            if p.get("next_pay_at"): e.add_field(name="📅 Payday",value=f"<t:{int(datetime.fromisoformat(p['next_pay_at']).timestamp())}:R>",inline=True)
        e.add_field(name="🧾 CV",value=("✅ مربوطة" if cv else "❌ مازال")+f" • 🏦 Bank {'✅' if p.get('bank_linked') else '❌'}",inline=False)
        e.set_thumbnail(url=member.display_avatar.url); return e

    # ------------------------------------------------------------------
    # CV / matching / employment
    # ------------------------------------------------------------------
    async def save_cv(self,guild:discord.Guild,member:discord.Member,*,skills:list[str],about:str,experience:int,availability:str,work_style:str,preferred_sector:str):
        p=self.profile(guild.id,member.id); p["cv"]={"skills":[s for s in skills if s in SKILLS][:8],"about":about[:800],"experience":max(0,min(5,int(experience))),"availability":availability,"work_style":work_style,"preferred_sector":preferred_sector,"updated_at":_iso_now()}
        p["bank_linked"] = self.economy is not None
        self._touch(guild.id,member.id); self.store.save(); return p["cv"]

    def career_matches(self,guild_id:int,user_id:int,lang="darija"):
        cv=self.profile(guild_id,user_id).get("cv") or {}
        if not cv:
            return []
        rows=match_careers(cv,lang,len(CAREERS))
        g=self.store.guild(guild_id)
        demand={cid:0 for cid in CAREERS}; workers={cid:0 for cid in CAREERS}
        for o in g.get("orders",{}).values():
            if o.get("status") in {"pending_worker","accepted","delivered"} and o.get("career_id") in demand:
                demand[o["career_id"]]+=1
        for p in g.get("projects",{}).values():
            if p.get("status") in {"open","assigned","in_progress","delivered"} and p.get("career_id") in demand:
                demand[p["career_id"]]+=2
        for p in g.get("profiles",{}).values():
            if p.get("job_id") in workers:
                workers[p["job_id"]]+=1
        for row in rows:
            cid=row["career_id"]; pressure=max(0,demand.get(cid,0)-workers.get(cid,0))
            if pressure:
                bonus=min(10,pressure*3); row["score"]=min(99,int(row["score"])+bonus)
                row["reasons"].append("طلب السوق" if lang=="darija" else "Market demand" if lang=="en" else "Demande du marché")
        rows.sort(key=lambda r:(-r["score"],r["career_id"]))
        return rows[:5]

    async def accept_job(self,guild:discord.Guild,member:discord.Member,career_id:str):
        if career_id not in CAREERS: return False,"الخدمة ماشي موجودة."
        p=self.profile(guild.id,member.id)
        if not p.get("cv"): return False,"صايب CV الأول."
        if not self.economy: return False,"Economy ماشي محملة."
        p["bank_linked"]=True
        last=_parse_dt(p.get("last_job_change")); now=local_now()
        if p.get("job_id") and p.get("job_id")!=career_id and last and now < last+timedelta(hours=config.JOB_CHANGE_COOLDOWN_HOURS):
            remain=(last+timedelta(hours=config.JOB_CHANGE_COOLDOWN_HOURS)-now).total_seconds()/3600
            return False,f"خاصك تستنى تقريباً **{remain:.1f}h** قبل تبدل الخدمة."
        old=p.get("job_id")
        # Final settlement before changing employer. This prevents wages earned
        # at one business from later being charged to the new business.
        if old and old != career_id:
            owed=int(p.get("pending_wages",0) or 0)+int(p.get("unpaid_wages",0) or 0)
            if owed>0 and self.economy:
                final_pay=self.economy.city_pay_salary(guild.id,CAREERS[old]["business_id"],member.id,owed,f"Final payroll — {career_name(old)}")
                paid=int(final_pay.get("paid",0)); due=int(final_pay.get("due",0))
                self.add_payslip(guild.id,member.id,career_id=old,gross=owed,paid=paid,due=due,source="final_payday")
                p["pending_wages"]=0; p["unpaid_wages"]=due
                if due>0:
                    self.store.save()
                    return False,f"⚠️ باقي عندك **{self.fmt(due)}** مستحقات من {career_name(old)}. خاصها تتخلص قبل تبدل المشغّل."
            elif owed>0:
                return False,"Economy ماشي محملة باش نصفي الأجر القديم."
        p["job_id"]=career_id; p["job_started_at"]=_iso_now(); p["last_job_change"]=_iso_now(); p["active_shift"]=None
        cycle=CAREERS[career_id]["pay_cycle"]; nxt=next_pay_at(cycle); p["next_pay_at"]=nxt.isoformat() if nxt else None
        self.progress(guild.id,member.id,career_id); self.store.save()
        await self.notifier.send(guild,member,f"💼 **مبروك! وليتي {CAREERS[career_id]['emoji']} {career_name(career_id)}.**\n🏦 Direct Deposit مربوط بـSavings ديالك.\n🕐 التوقيت: Africa/Casablanca.",kind="jobs")
        return True,f"✅ وليتي **{CAREERS[career_id]['emoji']} {career_name(career_id)}**. Bank Direct Deposit مربوط أوتوماتيكياً."

    # ------------------------------------------------------------------
    # Career XP / promotions / payslips
    # ------------------------------------------------------------------
    async def add_career_xp(self,guild:discord.Guild,member:discord.Member,amount:int,source:str):
        p=self.profile(guild.id,member.id); job=p.get("job_id")
        if not job: return None
        cp=self.progress(guild.id,member.id,job); old_idx,old_rank=career_rank(job,int(cp.get("xp",0)))
        cp["xp"]=int(cp.get("xp",0))+max(0,int(amount)); new_idx,new_rank=career_rank(job,int(cp["xp"]))
        self.store.save()
        if new_idx>old_idx:
            await self.notifier.send(guild,member,f"🚀 **ترقية مهنية!**\n{CAREERS[job]['emoji']} {career_name(job)}\n**{old_rank['name']} → {new_rank['name']}**",kind="promotions")
        return {"old":old_idx,"new":new_idx,"rank":new_rank}

    def add_payslip(self,guild_id,user_id,*,career_id,gross,paid,due,source,details=""):
        g=self.store.guild(guild_id); pid=self.store.next_id(guild_id,"payslip","PAY")
        slip={"id":pid,"career_id":career_id,"gross":int(gross),"paid":int(paid),"due":int(due),"source":source,"details":details[:300],"created_at":_iso_now()}
        g.setdefault("payslips",{}).setdefault(str(user_id),[]).append(slip); g["payslips"][str(user_id)]=g["payslips"][str(user_id)][-30:]; self.store.save(); return slip

    def add_invoice(self,guild_id,user_id,data:dict):
        g=self.store.guild(guild_id); iid=self.store.next_id(guild_id,"invoice","INV"); row={"id":iid,**data,"created_at":_iso_now()}; g.setdefault("invoices",{}).setdefault(str(user_id),[]).append(row); g["invoices"][str(user_id)]=g["invoices"][str(user_id)][-40:]; self.store.save(); return row

    # ------------------------------------------------------------------
    # Shifts
    # ------------------------------------------------------------------
    async def start_shift(self,guild,member,minutes:int):
        p=self.profile(guild.id,member.id); job=p.get("job_id")
        if not job: return False,"خاصك تلقى خدمة الأول."
        if not p.get("bank_linked"): return False,"خاص تربط Bank من CV الأول."
        if p.get("active_shift") and p["active_shift"].get("status")=="active": return False,"عندك Shift خدامة ديجا."
        if not can_work_today(job): return False,"هاد الخدمة عندها Weekend/أيام راحة اليوم. شوف Schedule ديالها."
        day=local_now().date().isoformat(); daily=p.setdefault("shift_daily",{})
        if daily.get("date")!=day: daily.clear(); daily.update({"date":day,"count":0})
        if int(daily.get("count",0))>=config.SHIFT_MAX_PER_DAY: return False,f"وصلتي للحد اليومي ديال **{config.SHIFT_MAX_PER_DAY} Shifts**."
        shift=build_shift(job,minutes); p["active_shift"]=shift; daily["count"]+=1; self._touch(guild.id,member.id); self.store.save()
        check_dt=datetime.fromisoformat(shift["checkin_at"]); end_dt=datetime.fromisoformat(shift["planned_end"])
        await self.notifier.send(guild,member,f"🟢 **Shift بدات — {career_name(job)}**\n📋 Check-in من <t:{int(check_dt.timestamp())}:R>\n🏁 Clock-out <t:{int(end_dt.timestamp())}:R>",kind="shifts")
        return True,"✅ Shift بدات. خاصك تدير **مهمة الشيفت** منين يجي وقت Check-in، ومن بعد Clock-out فالوقت."

    async def answer_shift_task(self,guild,member,answer_index:int):
        p=self.profile(guild.id,member.id); shift=p.get("active_shift")
        if not shift or shift.get("status")!="active": return False,"ما عندك حتى Shift خدامة."
        if not checkin_ready(shift):
            dt=datetime.fromisoformat(shift["checkin_at"]); return False,f"المهمة كتفتح <t:{int(dt.timestamp())}:R>."
        task=shift.get("task") or {}
        if task.get("done"): return False,"درت Check-in ديجا."
        task["done"]=True; task["correct_answer"]=int(answer_index)==int(task.get("correct",0)); self.store.save()
        return True,"✅ Check-in تسجل." if task["correct_answer"] else "✅ Check-in تسجل. الجواب ماكانش الأفضل، Performance غادي تتأثر شوية."

    async def clock_out(self,guild,member):
        p=self.profile(guild.id,member.id); shift=p.get("active_shift"); job=p.get("job_id")
        if not shift or shift.get("status")!="active" or not job: return False,"ما عندك حتى Shift خدامة."
        if not shift_due(shift):
            dt=datetime.fromisoformat(shift["planned_end"]); return False,f"Clock-out كتفتح <t:{int(dt.timestamp())}:R>."
        result=calculate_shift_pay(job,shift); cycle=CAREERS[job]["pay_cycle"]
        amount=result["gross"]
        if cycle=="commission": amount//=2  # small retainer; main income is real customer orders.
        paid=0; due=0
        if cycle in {"hourly","commission"}:
            pay=self.economy.city_pay_salary(guild.id,CAREERS[job]["business_id"],member.id,amount,f"Shift — {career_name(job)}") if self.economy else {"paid":0,"due":amount}
            paid=int(pay["paid"]); due=int(pay["due"]); p["unpaid_wages"]=int(p.get("unpaid_wages",0))+due
            slip=self.add_payslip(guild.id,member.id,career_id=job,gross=amount,paid=paid,due=due,source="shift",details=f"Performance {result['performance']}%")
            if paid: await self.notifier.send(guild,member,f"💳 **Direct Deposit وصل**\n{career_name(job)} • {slip['id']}\nGross {self.fmt(amount)} • دخل للبنك **{self.fmt(paid)}**"+(f" • باقي {self.fmt(due)}" if due else ""),kind="payments")
        else:
            p["pending_wages"]=int(p.get("pending_wages",0))+amount
            if not p.get("next_pay_at"):
                nxt=next_pay_at(cycle); p["next_pay_at"]=nxt.isoformat() if nxt else None
        shift["status"]="completed"; shift["completed_at"]=_iso_now(); p["active_shift"]=None; p["stats"]["shifts"]+=1; p["stats"]["earned"]+=paid
        cp=self.progress(guild.id,member.id,job); cp["stats"]["shifts"]+=1; self._bump_week(p,shifts=1,score=10+result["performance"]//10); self.store.save()
        await self.add_career_xp(guild,member,result["career_xp"],"shift")
        try: await self.economy.refresh_economy_stats(guild)
        except Exception: pass
        return True,f"✅ Shift تسالات • Performance **{result['performance']}%** • الأجر **{self.fmt(amount)}**"+(f" → Bank **{self.fmt(paid)}**" if cycle in {'hourly','commission'} else " → تجمع للـPayday")

    # ------------------------------------------------------------------
    # Services market / escrow
    # ------------------------------------------------------------------
    def available_workers(self,guild:discord.Guild,career_id:str):
        out=[]
        for uid,p in self.store.guild(guild.id).get("profiles",{}).items():
            if p.get("job_id")!=career_id or not p.get("bank_linked"): continue
            m=guild.get_member(int(uid))
            if m and not m.bot:
                out.append((m,self.rating(guild.id,m.id),int(self.progress(guild.id,m.id,career_id).get("xp",0))))
        out.sort(key=lambda x:(-x[1],-x[2],x[0].id)); return out[:25]

    async def create_order(self,guild,customer,service_id,worker_id:int):
        service=SERVICES.get(service_id); worker=guild.get_member(int(worker_id))
        if not service or not worker: return False,"الخدمة/العامل ماشي متوفر."
        wp=self.profile(guild.id,worker.id)
        if wp.get("job_id")!=service["career"]: return False,"هاد العامل ما بقاش خدام فهاد الخدمة."
        price=int(service["price"]); oid=self.store.next_id(guild.id,"order","ORD"); escrow=f"order:{oid}"
        if not self.economy or not self.economy.city_hold_escrow(guild.id,customer.id,escrow,price,kind="city_service",description=f"{oid} {service_name(service_id)}"):
            return False,"الرصيد فالWallet ماكافيش ولا تعذر حجز Escrow."
        order={"id":oid,"service_id":service_id,"career_id":service["career"],"customer_id":customer.id,"worker_id":worker.id,"business_id":CAREERS[service["career"]]["business_id"],"price":price,"escrow_key":escrow,"status":"pending_worker","created_at":_iso_now(),"expires_at":(local_now()+timedelta(hours=config.PENDING_ORDER_HOURS)).isoformat(),"delivery":"","rating":None}
        self.store.guild(guild.id)["orders"][oid]=order; self.store.save()
        self.add_invoice(guild.id,customer.id,{"kind":"service_order","order_id":oid,"service_id":service_id,"amount":price,"status":"ESCROW"})
        await self.notifier.send(guild,worker,f"📦 **جاك طلب خدمة جديد**\n{SERVICES[service_id]['emoji']} {service_name(service_id)}\n💵 {self.fmt(price)} فـEscrow\n⏳ جاوب قبل <t:{int(datetime.fromisoformat(order['expires_at']).timestamp())}:R>\nدخل Career Center → الطلبات ديالي.",kind="orders")
        try: await self.economy.refresh_economy_stats(guild)
        except Exception: pass
        return True,f"✅ الطلب **{oid}** تصاوب. {self.fmt(price)} تحجزات فـEscrow حتى العامل يقبل والخدمة تكمل."

    async def worker_order_action(self,guild,member,order_id,action:str,delivery_note:str=""):
        async with self.lock:
            order=self.store.guild(guild.id).get("orders",{}).get(order_id)
            if not order or int(order.get("worker_id",0))!=member.id: return False,"الطلب ماشي ديالك."
            status=order.get("status")
            customer=guild.get_member(int(order.get("customer_id",0)))
            if action=="accept" and status=="pending_worker":
                order["status"]="accepted"; order["accepted_at"]=_iso_now(); order["due_at"]=(local_now()+timedelta(hours=int(SERVICES[order['service_id']].get('hours',12)))).isoformat(); self.store.save()
                if customer: await self.notifier.send(guild,customer,f"✅ العامل **{member.display_name}** قبل طلبك {order_id}.\nموعد تقريبي: <t:{int(datetime.fromisoformat(order['due_at']).timestamp())}:R>",kind="orders")
                return True,"✅ قبلتي الطلب. خدم عليه ومن بعد دير **تسليم**."
            if action=="reject" and status=="pending_worker":
                order["status"]="rejected"; order["closed_at"]=_iso_now(); refunded=self.economy.city_refund_escrow(guild.id,order["escrow_key"],reason=f"Worker rejected {order_id}") if self.economy else 0; self.store.save()
                if customer: await self.notifier.send(guild,customer,f"↩️ العامل رفض {order_id}. رجعو ليك **{self.fmt(refunded)}** للWallet.",kind="orders")
                return True,"↩️ رفضتي الطلب والفلوس رجعات للزبون."
            if action=="deliver" and status=="accepted":
                order["status"]="delivered"; order["delivery"]=delivery_note[:900]; order["delivered_at"]=_iso_now(); order["auto_release_at"]=(local_now()+timedelta(hours=config.DELIVERED_AUTO_RELEASE_HOURS)).isoformat(); self.store.save()
                if customer: await self.notifier.send(guild,customer,f"📦 **الخدمة وصلات — {order_id}**\nدخل Services Market → طلباتي باش تأكد الاستلام. إلا ماجاوبتيش كتتحرر الفلوس أوتوماتيكياً من بعد {config.DELIVERED_AUTO_RELEASE_HOURS}h.",kind="orders")
                return True,"📦 التسليم تسجل. كنتسناو تأكيد الزبون."
            return False,"هاد العملية ماصالحةش مع حالة الطلب دابا."

    async def _release_order(self,guild,order,*,auto=False):
        if order.get("status") not in {"delivered"}: return None
        worker=guild.get_member(int(order["worker_id"])); career=CAREERS[order["career_id"]]
        res=self.economy.city_release_service_escrow(guild.id,order["escrow_key"],worker_id=int(order["worker_id"]),business_id=order["business_id"],worker_share_bps=int(career.get("service_worker_share_bps",0)),tax_bps=config.SERVICE_TAX_BPS,description=f"Service {order['id']}") if self.economy else {"gross":0,"worker":0,"tax":0,"business":0}
        if not res or int(res.get("gross",0))<=0: return None
        order["status"]="completed"; order["completed_at"]=_iso_now(); order["auto_released"]=bool(auto); order["settlement"]=res
        wp=self.profile(guild.id,int(order["worker_id"])); wp["stats"]["services"]+=1; wp["stats"]["earned"]+=int(res.get("worker",0)); self.progress(guild.id,int(order["worker_id"]),order["career_id"])["stats"]["services"]+=1; self._bump_week(wp,services=1,score=18); self.store.save()
        if worker:
            await self.add_career_xp(guild,worker,55,"service"); await self.notifier.send(guild,worker,f"💳 **خدمة {order['id']} تخلصات**\nGross {self.fmt(res['gross'])}\nدخل مباشرة للBank ديالك: **{self.fmt(res['worker'])}**",kind="payments")
        customer=guild.get_member(int(order["customer_id"]));
        if customer: await self.notifier.send(guild,customer,f"✅ الطلب {order['id']} تسالا وتحررات الفلوس للعامل.",kind="orders")
        self.add_invoice(guild.id,int(order["worker_id"]),{"kind":"service_income","order_id":order["id"],"amount":int(res.get("worker",0)),"gross":int(res.get("gross",0)),"status":"PAID"})
        try: await self.economy.refresh_economy_stats(guild)
        except Exception: pass
        return res

    async def customer_confirm_order(self,guild,member,order_id):
        async with self.lock:
            order=self.store.guild(guild.id).get("orders",{}).get(order_id)
            if not order or int(order.get("customer_id",0))!=member.id: return False,"الطلب ماشي ديالك."
            if order.get("status")!="delivered": return False,"الخدمة مازال ما وصلاتش."
            res=await self._release_order(guild,order,auto=False)
            return (True,f"✅ الاستلام تأكد. العامل خدا **{self.fmt(res['worker'])}** فBank ديالو.") if res else (False,"تعذر تحرير Escrow.")

    async def rate_worker(self,guild,customer,order_id,rating:int):
        order=self.store.guild(guild.id).get("orders",{}).get(order_id)
        if not order or int(order.get("customer_id",0))!=customer.id or order.get("status")!="completed": return False,"مايمكنش التقييم دابا."
        if order.get("rating") is not None: return False,"قيّمتي هاد الخدمة ديجا."
        rating=max(1,min(5,int(rating))); order["rating"]=rating; wp=self.profile(guild.id,int(order["worker_id"])); wp["rating_sum"]+=rating; wp["rating_count"]+=1; self._bump_week(wp,score=rating*2); self.store.save(); return True,f"⭐ شكراً! تسجل **{rating}/5**."

    # ------------------------------------------------------------------
    # Projects / contracts / milestones
    # ------------------------------------------------------------------
    async def create_project(self,guild,owner,*,career_id,title,description,budget,deadline_days,milestones_raw):
        if career_id not in CAREERS: return False,"Career ماشي موجودة."
        budget=int(budget); deadline_days=max(1,min(config.PROJECT_MAX_DEADLINE_DAYS,int(deadline_days)))
        if budget<config.PROJECT_MIN_BUDGET: return False,f"أقل Budget هو {self.fmt(config.PROJECT_MIN_BUDGET)}."
        pid=self.store.next_id(guild.id,"project","PRJ"); escrow=f"project:{pid}"
        if not self.economy or not self.economy.city_hold_escrow(guild.id,owner.id,escrow,budget,kind="city_project",description=f"{pid} {title}"): return False,"Wallet ماكافيش أو تعذر حجز Budget."
        p={"id":pid,"owner_id":owner.id,"career_id":career_id,"title":title[:80],"description":description[:1000],"budget":budget,"escrow_key":escrow,"deadline_at":(local_now()+timedelta(days=deadline_days)).isoformat(),"status":"open","applicants":[],"worker_id":None,"created_at":_iso_now(),"milestones":parse_milestones(milestones_raw,budget)}
        self.store.guild(guild.id)["projects"][pid]=p; self.store.save();
        try: await self.economy.refresh_economy_stats(guild)
        except Exception: pass
        return True,f"✅ المشروع **{pid}** تصاوب وBudget **{self.fmt(budget)}** تحجزات فـEscrow."

    async def apply_project(self,guild,member,project_id):
        p=self.store.guild(guild.id).get("projects",{}).get(project_id)
        if not p or p.get("status")!="open": return False,"المشروع ماشي مفتوح."
        if int(p.get("owner_id",0))==member.id: return False,"مايمكنش تقدم للمشروع ديالك."
        prof=self.profile(guild.id,member.id)
        if prof.get("job_id")!=p.get("career_id"): return False,f"هاد المشروع باغي **{career_name(p['career_id'])}**."
        apps=p.setdefault("applicants",[])
        if member.id in apps: return False,"ديجا قدمتي."
        apps.append(member.id); self.store.save(); owner=guild.get_member(int(p["owner_id"]));
        if owner: await self.notifier.send(guild,owner,f"🏗️ {member.display_name} قدم على المشروع **{project_id}**. دخل Projects Board → مشاريعي.",kind="projects")
        return True,"✅ الطلب ديالك للمشروع تبعث."

    async def assign_project(self,guild,owner,project_id,worker_id:int):
        p=self.store.guild(guild.id).get("projects",{}).get(project_id); worker=guild.get_member(int(worker_id))
        if not p or int(p.get("owner_id",0))!=owner.id or p.get("status")!="open": return False,"مايمكنش التعيين."
        if int(worker_id) not in p.get("applicants",[]) or not worker: return False,"هاد العضو ماقدمش للمشروع."
        p["worker_id"]=int(worker_id); p["status"]="assigned"; p["assigned_at"]=_iso_now(); self.store.save(); await self.notifier.send(guild,worker,f"🏗️ **تقبلتي فمشروع {project_id}!**\n{p['title']}\nBudget {self.fmt(p['budget'])}\nDeadline <t:{int(datetime.fromisoformat(p['deadline_at']).timestamp())}:R>",kind="projects"); return True,"✅ العامل تعين والمشروع بدا."

    async def deliver_project_milestone(self,guild,worker,project_id,note):
        p=self.store.guild(guild.id).get("projects",{}).get(project_id)
        if not p or int(p.get("worker_id",0))!=worker.id or p.get("status") not in {"assigned","in_progress"}: return False,"المشروع ماشي جاهز للتسليم."
        m=current_milestone(p)
        if not m or m.get("status")!="pending": return False,"ماكاين حتى Milestone كتستنى التسليم."
        m["status"]="delivered"; m["delivery"]=note[:900]; m["submitted_at"]=_iso_now(); p["status"]="delivered"; self.store.save(); owner=guild.get_member(int(p["owner_id"]));
        if owner: await self.notifier.send(guild,owner,f"📦 **Milestone وصلات — {project_id}**\n{m['title']} • {self.fmt(m['amount'])}\nدخل Projects Board باش تقبلها.",kind="projects")
        return True,"📦 التسليم تسجل ومالك المشروع توصّل بتنبيه."

    async def approve_project_milestone(self,guild,owner,project_id):
        async with self.lock:
            p=self.store.guild(guild.id).get("projects",{}).get(project_id)
            if not p or int(p.get("owner_id",0))!=owner.id or p.get("status")!="delivered": return False,"ماكاين حتى تسليم جاهز للموافقة."
            m=current_milestone(p)
            if not m or m.get("status")!="delivered": return False,"Milestone ماشي جاهزة."
            res=self.economy.city_release_project_escrow(guild.id,p["escrow_key"],worker_id=int(p["worker_id"]),release_amount=int(m["amount"]),tax_bps=config.PROJECT_TAX_BPS,description=f"{project_id} • {m['title']}") if self.economy else {"gross":0,"worker":0,"tax":0}
            if int(res.get("gross",0))<=0: return False,"تعذر تحرير Escrow."
            m["status"]="approved"; m["approved_at"]=_iso_now(); remaining=current_milestone(p)
            if remaining is None: p["status"]="completed"; p["completed_at"]=_iso_now()
            else: p["status"]="in_progress"
            wp=self.profile(guild.id,int(p["worker_id"])); wp["stats"]["projects"]+=1 if p["status"]=="completed" else 0; wp["stats"]["earned"]+=int(res.get("worker",0)); self._bump_week(wp,projects=1 if p["status"]=="completed" else 0,score=22); self.store.save(); worker=guild.get_member(int(p["worker_id"]));
            if worker: await self.add_career_xp(guild,worker,80,"project"); await self.notifier.send(guild,worker,f"💳 **Milestone تخلصات — {project_id}**\n{m['title']}\nدخل للBank: **{self.fmt(res['worker'])}**",kind="payments")
            self.add_invoice(guild.id,int(p["worker_id"]),{"kind":"project_income","project_id":project_id,"amount":int(res.get("worker",0)),"gross":int(res.get("gross",0)),"status":"PAID"})
            try: await self.economy.refresh_economy_stats(guild)
            except Exception: pass
            return True,"✅ Milestone تقبلات وتحرر الأداء."+(" المشروع كامل تسالا 🎉" if p["status"]=="completed" else " دابا خدم على Milestone الجاية.")

    async def cancel_open_project(self,guild,owner,project_id):
        p=self.store.guild(guild.id).get("projects",{}).get(project_id)
        if not p or int(p.get("owner_id",0))!=owner.id or p.get("status")!="open": return False,"تقدر تلغي غير Project مفتوح قبل التعيين."
        refunded=self.economy.city_refund_escrow(guild.id,p["escrow_key"],reason=f"Project cancelled {project_id}") if self.economy else 0; p["status"]="cancelled"; p["cancelled_at"]=_iso_now(); self.store.save(); return True,f"↩️ المشروع تلغى ورجع **{self.fmt(refunded)}** للWallet."

    # ------------------------------------------------------------------
    # Notifications / documents
    # ------------------------------------------------------------------
    def documents(self,guild_id,user_id):
        g=self.store.guild(guild_id); return {"payslips":list(reversed((g.get("payslips",{}).get(str(user_id),[]) or [])[-10:])),"invoices":list(reversed((g.get("invoices",{}).get(str(user_id),[]) or [])[-10:]))}

    async def city_diagnostics(self, guild: discord.Guild) -> dict:
        """Owner-facing health check. Read-only; never mutates balances."""
        checks=[]
        setup=self.store.guild(guild.id).get("setup",{})
        checks.append(("CITY setup", bool(setup.get("complete"))))
        me=guild.me
        for key in config.CHANNEL_NAMES:
            ch=self.channel(guild,key)
            exists=isinstance(ch,discord.TextChannel)
            checks.append((f"Channel {key}", exists))
            if exists and me:
                perms=ch.permissions_for(me)
                checks.append((f"Bot permissions {key}", bool(perms.view_channel and perms.send_messages and perms.embed_links and perms.read_message_history)))
        eco=self.economy
        required=("city_hold_escrow","city_refund_escrow","city_release_service_escrow","city_release_project_escrow","city_pay_salary")
        checks.append(("Economy bridge", bool(eco and all(hasattr(eco,x) for x in required))))
        checks.append(("Timezone Africa/Casablanca", config.TIMEZONE=="Africa/Casablanca"))
        checks.append(("CITY tick loop", bool(self.city_tick.is_running())))
        checks.append(("Market refresh loop", bool(self.market_tick.is_running())))
        persistent_names={type(v).__name__ for v in getattr(self.bot,"persistent_views",[]) or []}
        checks.append(("Persistent Career panel", "CareerPublicView" in persistent_names))
        checks.append(("Persistent Services panel", "ServicesPublicView" in persistent_names))
        checks.append(("Persistent Projects panel", "ProjectsPublicView" in persistent_names))
        panels=(setup.get("panels") or {})
        checks.append(("Career panel message tracked", bool(panels.get("career"))))
        checks.append(("Services panel message tracked", bool(panels.get("services"))))
        checks.append(("Projects panel message tracked", bool(panels.get("projects"))))
        try:
            self.store.path.parent.mkdir(parents=True,exist_ok=True)
            writable=self.store.path.parent.exists()
        except Exception:
            writable=False
        checks.append(("CITY database path", writable))
        ug=None
        if (self.underground(guild.id).get("setup") or {}).get("complete"):
            ug=await self.underground_diagnostics(guild)
        overall=all(v for _,v in checks) and (ug is None or bool(ug.get("ok")))
        return {"ok":overall,"checks":checks,"underground":ug}

    # ------------------------------------------------------------------
    # Scheduled processing
    # ------------------------------------------------------------------
    async def process_payroll(self,guild:discord.Guild):
        if not self.economy: return
        for uid,p in list(self.store.guild(guild.id).get("profiles",{}).items()):
            job=p.get("job_id")
            if not job or job not in CAREERS or CAREERS[job]["pay_cycle"] not in {"daily","weekly"}: continue
            if not pay_due(p): continue
            member=guild.get_member(int(uid)); pending=int(p.get("pending_wages",0))+int(p.get("unpaid_wages",0)); p["pending_wages"]=0; p["unpaid_wages"]=0
            if pending>0:
                res=self.economy.city_pay_salary(guild.id,CAREERS[job]["business_id"],int(uid),pending,f"{CAREERS[job]['pay_cycle'].title()} Payroll — {career_name(job)}")
                p["unpaid_wages"]=int(res["due"]); p["stats"]["earned"]+=int(res["paid"]); slip=self.add_payslip(guild.id,int(uid),career_id=job,gross=pending,paid=int(res["paid"]),due=int(res["due"]),source="payday")
                if member and res["paid"]: await self.notifier.send(guild,member,f"💳 **Payday — {slip['id']}**\nGross {self.fmt(pending)}\nDirect Deposit **{self.fmt(res['paid'])}**"+(f"\n⚠️ باقي مستحق {self.fmt(res['due'])}" if res['due'] else ""),kind="payments")
            nxt=next_pay_at(CAREERS[job]["pay_cycle"]); p["next_pay_at"]=nxt.isoformat() if nxt else None; self.store.save()

    async def process_shifts(self,guild):
        now=local_now()
        dirty=False
        for uid,p in list(self.store.guild(guild.id).get("profiles",{}).items()):
            shift=p.get("active_shift")
            if not shift or shift.get("status")!="active":
                continue
            member=guild.get_member(int(uid))
            if not member:
                continue
            check=_parse_dt(shift.get("checkin_at")); end=_parse_dt(shift.get("planned_end"))
            if check and now>=check and not shift.get("checkin_notified") and not (shift.get("task") or {}).get("done"):
                shift["checkin_notified"]=True; dirty=True
                await self.notifier.send(guild,member,"📋 **Check-in ديال Shift واجد دابا.** دخل Career Center → الشيفت ديالي → مهمة الشيفت.",kind="shifts")
            if end and now>=end and not shift.get("end_notified"):
                shift["end_notified"]=True; dirty=True
                await self.notifier.send(guild,member,"🏁 **Shift سالات فالوقت.** دخل Career Center ودير Clock-out باش يتحسب الأداء والأجر.",kind="shifts")
        if dirty:
            self.store.save()

    async def process_projects(self,guild):
        now=local_now(); dirty=False
        for p in list(self.store.guild(guild.id).get("projects",{}).values()):
            if p.get("status") in {"completed","cancelled","refunded"}:
                continue
            deadline=_parse_dt(p.get("deadline_at"))
            if not deadline:
                continue
            # Reminder 24h before deadline.
            if not p.get("deadline_reminded") and now >= deadline-timedelta(hours=24) and now < deadline:
                p["deadline_reminded"]=True; dirty=True
                for uid in {int(p.get("owner_id",0) or 0),int(p.get("worker_id") or 0)}-{0}:
                    m=guild.get_member(uid)
                    if m: await self.notifier.send(guild,m,f"⏳ المشروع **{p['id']}** باقي ليه أقل من 24 ساعة على Deadline.",kind="projects")
            if now>=deadline and not p.get("overdue_notified"):
                p["overdue_notified"]=True; p["overdue"]=True; dirty=True
                if p.get("status")=="open":
                    refunded=self.economy.city_refund_escrow(guild.id,p["escrow_key"],reason=f"Project expired unassigned {p['id']}") if self.economy else 0
                    p["status"]="refunded"; p["closed_at"]=_iso_now()
                    owner=guild.get_member(int(p.get("owner_id",0)))
                    if owner: await self.notifier.send(guild,owner,f"↩️ المشروع **{p['id']}** سالا بلا عامل. رجع **{self.fmt(refunded)}** للWallet.",kind="projects")
                else:
                    for uid in {int(p.get("owner_id",0) or 0),int(p.get("worker_id") or 0)}-{0}:
                        m=guild.get_member(uid)
                        if m: await self.notifier.send(guild,m,f"⚠️ المشروع **{p['id']}** فات Deadline. الحالة بقات محفوظة باش يتكمل أو تتحل عبر Support بلا ضياع Escrow.",kind="projects")
        if dirty:
            self.store.save()

    async def process_orders(self,guild):
        now=local_now()
        for order in list(self.store.guild(guild.id).get("orders",{}).values()):
            status=order.get("status")
            if status=="pending_worker" and _parse_dt(order.get("expires_at")) and now>=_parse_dt(order.get("expires_at")):
                refunded=self.economy.city_refund_escrow(guild.id,order["escrow_key"],reason=f"Order expired {order['id']}") if self.economy else 0; order["status"]="refunded"; order["closed_at"]=_iso_now(); customer=guild.get_member(int(order["customer_id"]));
                if customer: await self.notifier.send(guild,customer,f"↩️ الطلب {order['id']} سالا قبل القبول ورجع **{self.fmt(refunded)}** للWallet.",kind="orders")
            elif status=="delivered" and _parse_dt(order.get("auto_release_at")) and now>=_parse_dt(order.get("auto_release_at")):
                async with self.lock:
                    if order.get("status")=="delivered": await self._release_order(guild,order,auto=True)
        self.store.save()

    async def process_underground(self, guild: discord.Guild):
        ug=self.underground(guild.id); now=local_now(); dirty=False
        for inv in (ug.get("invites") or {}).values():
            if inv.get("status")!="pending":
                continue
            exp=_parse_dt(inv.get("expires_at"))
            if exp and now>=exp:
                inv["status"]="expired"; inv["expired_at"]=_iso_now(); dirty=True
        for uid,row in (ug.get("members") or {}).items():
            if not row.get("active"):
                continue
            before=int(row.get("heat",0) or 0)
            try: self._decay_heat(row)
            except Exception: pass
            if int(row.get("heat",0) or 0)!=before: dirty=True
        for uid,inv in list((ug.get("crew_invites") or {}).items()):
            exp=_parse_dt((inv or {}).get("expires_at"))
            if exp and now>=exp:
                ug["crew_invites"].pop(uid,None); dirty=True
        if dirty:
            self.store.save()

    async def process_employee_week(self,guild):
        g=self.store.guild(guild.id); key=self._week_key(); current=g.get("employee_week",{})
        # Evaluate previous week only when a new ISO week starts and we have profiles with old week stats.
        if current.get("week")==key: return
        candidates=[]
        for uid,p in g.get("profiles",{}).items():
            ws=p.get("previous_week_stats") or p.get("week_stats",{})
            if ws.get("week") and ws.get("week")!=key and int(ws.get("score",0))>0:
                # Reliability-normalised enough for community use: capped activity components.
                score=min(60,int(ws.get("score",0)))+min(25,int(p.get("rating_count",0))*2)
                candidates.append((score,int(uid)))
        if not candidates:
            g["employee_week"]={"week":key}; self.store.save(); return
        candidates.sort(reverse=True); score,uid=candidates[0]; paid=self.economy.city_treasury_bonus_to_bank(guild.id,uid,config.EMPLOYEE_WEEK_BONUS,"Employee of the Week") if self.economy else 0
        g["employee_week"]={"week":key,"user_id":uid,"score":score,"bonus":paid,"awarded_at":_iso_now()}; self.store.save(); member=guild.get_member(uid)
        if member: await self.notifier.send(guild,member,f"🏆 **موظف الأسبوع!**\nربحتي Bonus **{self.fmt(paid)}** دخل مباشرة للBank ديالك.",kind="promotions")

    @tasks.loop(seconds=max(30,config.TICK_SECONDS))
    async def city_tick(self):
        for guild in self.bot.guilds:
            setup=self.store.guild(guild.id).get("setup",{})
            if not setup.get("complete"): continue
            try:
                await self.process_payroll(guild); await self.process_shifts(guild); await self.process_orders(guild); await self.process_projects(guild); await self.process_underground(guild); await self.process_employee_week(guild)
            except Exception as exc:
                print(f"[CITY TICK] {guild.id}: {type(exc).__name__}: {exc}")

    @tasks.loop(minutes=max(2,config.JOB_MARKET_REFRESH_MINUTES))
    async def market_tick(self):
        for guild in self.bot.guilds:
            if self.store.guild(guild.id).get("setup",{}).get("complete"):
                try: await self.refresh_city_panels(guild)
                except Exception as exc: print(f"[CITY MARKET] {guild.id}: {exc}")

    @city_tick.before_loop
    @market_tick.before_loop
    async def before_loops(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Cog lifecycle
    # ------------------------------------------------------------------
    async def cog_load(self):
        from .ui import CareerPublicView, ServicesPublicView, ProjectsPublicView
        from .underground_ui import (
            UndergroundGatePublicView, UndergroundMarketPublicView,
            UndergroundCrewsPublicView, UndergroundOperationsPublicView,
            UndergroundInviteView,
        )
        self.bot.add_view(CareerPublicView(self))
        self.bot.add_view(ServicesPublicView(self))
        self.bot.add_view(ProjectsPublicView(self))
        # Persistent hidden-world panels + anonymous invitation buttons survive restarts.
        self.bot.add_view(UndergroundGatePublicView(self))
        self.bot.add_view(UndergroundMarketPublicView(self))
        self.bot.add_view(UndergroundCrewsPublicView(self))
        self.bot.add_view(UndergroundOperationsPublicView(self))
        self.bot.add_view(UndergroundInviteView(self))
        self.city_tick.start(); self.market_tick.start()

    async def cog_unload(self):
        self.city_tick.cancel(); self.market_tick.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready_once: return
        self._ready_once=True
        for guild in self.bot.guilds:
            if self.store.guild(guild.id).get("setup",{}).get("complete"):
                try: await self.refresh_city_panels(guild)
                except Exception as exc: print(f"[CITY READY] {guild.id}: {exc}")
            ug = self.underground(guild.id)
            if (ug.get("setup") or {}).get("complete"):
                try:
                    await self.repair_underground_permissions(guild)
                    await self.refresh_underground_panels(guild)
                except Exception as exc:
                    print(f"[UNDERGROUND READY] {guild.id}: {type(exc).__name__}: {exc}")
