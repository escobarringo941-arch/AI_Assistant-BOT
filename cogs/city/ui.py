# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import discord
import games_config as root_cfg

from .i18n import t
from .careers import CAREERS, SKILLS, SECTOR_NAMES, career_name, career_rank
from .services import SERVICES, service_name
from .shifts import checkin_ready, shift_due


def _lang_options(current=None):
    return [
        discord.SelectOption(label="Darija",value="darija",emoji="🇲🇦",default=current=="darija"),
        discord.SelectOption(label="English",value="en",emoji="🇬🇧",default=current=="en"),
        discord.SelectOption(label="Français",value="fr",emoji="🇫🇷",default=current=="fr"),
    ]


def _private_title(lang):
    return "🏙️ GGMW9 CITY — المدينة ديالك" if lang=="darija" else "🏙️ GGMW9 CITY — Your City" if lang=="en" else "🏙️ GGMW9 CITY — Ta ville"


def build_home_embed(cog,guild,member,lang):
    p=cog.profile(guild.id,member.id); job=p.get("job_id")
    if lang=="en":
        desc="Your professional dashboard: CV, career, shifts, services, projects, payroll and notifications."
    elif lang=="fr":
        desc="Ton tableau professionnel : CV, carrière, shifts, services, projets, paie et notifications."
    else:
        desc="هاد هي الواجهة المهنية ديالك: CV، الخدمة، الشيفتات، الخدمات، المشاريع، الرواتب والتنبيهات."
    e=discord.Embed(title=_private_title(lang),description=desc,color=discord.Color.blurple())
    if job:
        cp=cog.progress(guild.id,member.id,job); _,rank=career_rank(job,int(cp.get("xp",0))); e.add_field(name=t(lang,"career"),value=f"{CAREERS[job]['emoji']} **{career_name(job,lang)}** • {rank['name']} • XP {int(cp.get('xp',0)):,}",inline=False)
    else:
        e.add_field(name=t(lang,"career"),value="❌ مازال ما خدامش" if lang=="darija" else "❌ Not employed" if lang=="en" else "❌ Sans emploi",inline=False)
    e.add_field(name="🏦 Bank",value="✅ Direct Deposit" if p.get("bank_linked") else "❌ ربط الحساب من CV" if lang=="darija" else "❌ Link it through CV",inline=True)
    e.add_field(name="⭐ Rating",value=f"{cog.rating(guild.id,member.id):.2f}/5" if p.get("rating_count") else "New",inline=True)
    e.set_thumbnail(url=member.display_avatar.url); e.set_footer(text="Africa/Casablanca • DM + city-alerts fallback"); return e


class OwnedView(discord.ui.View):
    def __init__(self,cog,user,lang="darija",timeout=900):
        super().__init__(timeout=timeout); self.cog=cog; self.user=user; self.lang=lang
    async def interaction_check(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(t(self.lang,"not_yours"),ephemeral=True); return False
        return True


class CityLanguageSelect(discord.ui.Select):
    def __init__(self,cog,user,lang,row=4):
        super().__init__(placeholder="🌐 اللغة / Language / Langue",options=_lang_options(lang),min_values=1,max_values=1,row=row)
        self.cog=cog; self.user=user; self.lang=lang
    async def callback(self,interaction):
        if interaction.user.id!=self.user.id:
            await interaction.response.send_message(t(self.lang,"not_yours"),ephemeral=True); return
        lang=self.cog.set_lang(interaction.guild.id,interaction.user.id,self.values[0])
        await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,interaction.user,lang),view=CityHomeView(self.cog,interaction.user,lang))


class PublicLanguageSelect(discord.ui.Select):
    def __init__(self,cog,source,row=1):
        super().__init__(placeholder="🌐 اللغة / Language / Langue",options=_lang_options(),min_values=1,max_values=1,row=row,custom_id=f"ggmw9:city:{source}:language")
        self.cog=cog; self.source=source
    async def callback(self,interaction):
        lang=self.cog.set_lang(interaction.guild.id,interaction.user.id,self.values[0])
        if self.source=="services":
            embed=build_services_home_embed(self.cog,interaction.guild,interaction.user,lang); view=ServicesHomeView(self.cog,interaction.user,lang)
        elif self.source=="projects":
            embed=build_projects_home_embed(self.cog,interaction.guild,interaction.user,lang); view=ProjectsHomeView(self.cog,interaction.user,lang)
        else:
            embed=build_home_embed(self.cog,interaction.guild,interaction.user,lang); view=CityHomeView(self.cog,interaction.user,lang)
        await interaction.response.send_message(embed=embed,view=view,ephemeral=True)


class CareerPublicView(discord.ui.View):
    def __init__(self,cog):
        super().__init__(timeout=None); self.cog=cog; self.add_item(PublicLanguageSelect(cog,"career",row=1))
    @discord.ui.button(label="🏙️ دخل للمدينة",style=discord.ButtonStyle.success,custom_id="ggmw9:city:career:open",row=0)
    async def open(self,interaction,button):
        lang="darija"; await interaction.response.send_message(embed=build_home_embed(self.cog,interaction.guild,interaction.user,lang),view=CityHomeView(self.cog,interaction.user,lang),ephemeral=True)


class ServicesPublicView(discord.ui.View):
    def __init__(self,cog):
        super().__init__(timeout=None); self.cog=cog; self.add_item(PublicLanguageSelect(cog,"services",row=1))
    @discord.ui.button(label="🛍️ فتح سوق الخدمات",style=discord.ButtonStyle.success,custom_id="ggmw9:city:services:open",row=0)
    async def open(self,interaction,button):
        await interaction.response.send_message(embed=build_services_home_embed(self.cog,interaction.guild,interaction.user,"darija"),view=ServicesHomeView(self.cog,interaction.user,"darija"),ephemeral=True)


class ProjectsPublicView(discord.ui.View):
    def __init__(self,cog):
        super().__init__(timeout=None); self.cog=cog; self.add_item(PublicLanguageSelect(cog,"projects",row=1))
    @discord.ui.button(label="🏗️ فتح المشاريع",style=discord.ButtonStyle.success,custom_id="ggmw9:city:projects:open",row=0)
    async def open(self,interaction,button):
        await interaction.response.send_message(embed=build_projects_home_embed(self.cog,interaction.guild,interaction.user,"darija"),view=ProjectsHomeView(self.cog,interaction.user,"darija"),ephemeral=True)


class CityHomeView(OwnedView):
    def __init__(self,cog,user,lang="darija"):
        super().__init__(cog,user,lang)
        labels=[(t(lang,"career"),"💼",self.career),(t(lang,"cv"),"🧾",self.cv),(t(lang,"matches"),"🎯",self.matches),(t(lang,"shift"),"🕐",self.shift),(t(lang,"orders"),"📦",self.orders),(t(lang,"payslips"),"💳",self.docs),(t(lang,"notifications"),"🔔",self.notifications),(t(lang,"services"),"🛍️",self.services),(t(lang,"projects"),"🏗️",self.projects)]
        for i,(label,emoji,cb) in enumerate(labels):
            b=discord.ui.Button(label=label[:80],emoji=emoji,style=discord.ButtonStyle.primary if i<4 else discord.ButtonStyle.secondary,row=0 if i<5 else 1); b.callback=cb; self.add_item(b)
        self.add_item(CityLanguageSelect(cog,user,lang,row=2))
    async def career(self,interaction): await interaction.response.edit_message(content=None,embed=self.cog.build_profile_embed(interaction.guild,interaction.user,self.lang),view=BackHomeView(self.cog,self.user,self.lang))
    async def cv(self,interaction): await interaction.response.edit_message(content="🧾 اختار حتى 8 مهارات كتعرف تديرهم فالحقيقة:" if self.lang=="darija" else "🧾 Choose up to 8 real skills:",embed=None,view=CVSkillsView(self.cog,self.user,self.lang))
    async def matches(self,interaction): await show_matches(interaction,self.cog,self.user,self.lang)
    async def shift(self,interaction): await show_shift(interaction,self.cog,self.user,self.lang)
    async def orders(self,interaction): await show_orders(interaction,self.cog,self.user,self.lang)
    async def docs(self,interaction): await show_documents(interaction,self.cog,self.user,self.lang)
    async def notifications(self,interaction): await interaction.response.edit_message(content=None,embed=build_notification_embed(self.cog,interaction.guild,interaction.user,self.lang),view=NotificationView(self.cog,self.user,self.lang))
    async def services(self,interaction): await interaction.response.edit_message(content=None,embed=build_services_home_embed(self.cog,interaction.guild,interaction.user,self.lang),view=ServicesHomeView(self.cog,self.user,self.lang))
    async def projects(self,interaction): await interaction.response.edit_message(content=None,embed=build_projects_home_embed(self.cog,interaction.guild,interaction.user,self.lang),view=ProjectsHomeView(self.cog,self.user,self.lang))


class BackHomeView(OwnedView):
    def __init__(self,cog,user,lang):
        super().__init__(cog,user,lang); b=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary); b.callback=self.back; self.add_item(b); self.add_item(CityLanguageSelect(cog,user,lang,row=1))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,interaction.user,self.lang),view=CityHomeView(self.cog,self.user,self.lang))


# ----------------------------------------------------------------------
# CV / Matching
# ----------------------------------------------------------------------
class CVSkillsSelect(discord.ui.Select):
    def __init__(self,cog,user,lang):
        opts=[discord.SelectOption(label=(s[lang] if lang in s else s["darija"])[:100],value=k,emoji=s["emoji"]) for k,s in SKILLS.items()]
        super().__init__(placeholder="🧠 اختار مهاراتك..." if lang=="darija" else "🧠 Choose your skills...",options=opts,min_values=1,max_values=8,row=0); self.cog=cog; self.user=user; self.lang=lang
    async def callback(self,interaction):
        if interaction.user.id!=self.user.id: await interaction.response.send_message(t(self.lang,"not_yours"),ephemeral=True); return
        await interaction.response.send_modal(CVDetailsModal(self.cog,list(self.values),self.lang))

class CVSkillsView(OwnedView):
    def __init__(self,cog,user,lang): super().__init__(cog,user,lang); self.add_item(CVSkillsSelect(cog,user,lang)); b=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,interaction.user,self.lang),view=CityHomeView(self.cog,self.user,self.lang))

class CVDetailsModal(discord.ui.Modal):
    def __init__(self,cog,skills,lang):
        self.cog=cog; self.skills=skills; self.lang=lang; super().__init__(title="🧾 CV ديالك فـGGMW9 CITY" if lang=="darija" else "🧾 Your GGMW9 CITY CV")
        self.about=discord.ui.TextInput(label="شنو كتعرف تدير فالحقيقة؟" if lang=="darija" else "What can you really do?",placeholder="مثال: كنعرف نصمم، نتعامل مع الناس، Gaming...",style=discord.TextStyle.paragraph,min_length=10,max_length=800)
        self.experience=discord.ui.TextInput(label="التجربة من 0 حتى 5" if lang=="darija" else "Experience 0 to 5",placeholder="0",min_length=1,max_length=1)
        self.availability=discord.ui.TextInput(label="الوقت: weekdays/weekends/evenings/flexible",placeholder="flexible",max_length=20)
        self.work_style=discord.ui.TextInput(label="الستايل: people/solo/creative/technical/flexible",placeholder="flexible",max_length=20)
        self.sector=discord.ui.TextInput(label="المجال المفضل (اختياري)",placeholder="media / fashion / technical / business...",required=False,max_length=20)
        for x in (self.about,self.experience,self.availability,self.work_style,self.sector): self.add_item(x)
    async def on_submit(self,interaction):
        try: exp=int(str(self.experience.value).strip())
        except: exp=0
        avail=str(self.availability.value).strip().lower(); style=str(self.work_style.value).strip().lower(); sector=str(self.sector.value).strip().lower()
        valid_avail={"weekdays","weekends","evenings","flexible"}; valid_style={"people","solo","creative","technical","active","business","flexible"}
        if avail not in valid_avail: avail="flexible"
        if style not in valid_style: style="flexible"
        if sector not in SECTOR_NAMES: sector=""
        await self.cog.save_cv(interaction.guild,interaction.user,skills=self.skills,about=str(self.about.value),experience=exp,availability=avail,work_style=style,preferred_sector=sector)
        matches=self.cog.career_matches(interaction.guild.id,interaction.user.id,self.lang)
        e=build_matches_embed(self.cog,interaction.guild,interaction.user,self.lang,matches); await interaction.response.edit_message(content="✅ CV تحفضات وBank تربط بـDirect Deposit." if self.lang=="darija" else "✅ CV saved and Bank linked.",embed=e,view=CareerMatchesView(self.cog,interaction.user,self.lang,matches))


def build_matches_embed(cog,guild,user,lang,matches):
    e=discord.Embed(title="🎯 الخدمات المناسبة ليك" if lang=="darija" else "🎯 Best Career Matches",color=discord.Color.gold())
    if not matches: e.description="صايب CV الأول."; return e
    e.description="\n".join(f"{m['emoji']} **{m['name']} — {m['score']}%**\n↳ "+" • ".join(m['reasons']) for m in matches); e.set_footer(text="الـMatch مبني على مهاراتك، الوصف ديالك، التفضيلات والتوقيت — ماشي Random."); return e

async def show_matches(interaction,cog,user,lang):
    matches=cog.career_matches(interaction.guild.id,user.id,lang); await interaction.response.edit_message(content=None,embed=build_matches_embed(cog,interaction.guild,user,lang,matches),view=CareerMatchesView(cog,user,lang,matches) if matches else BackHomeView(cog,user,lang))

class CareerMatchesSelect(discord.ui.Select):
    def __init__(self,cog,user,lang,matches):
        opts=[discord.SelectOption(label=f"{m['name']} — {m['score']}%"[:100],value=m["career_id"],emoji=m["emoji"],description=(" • ".join(m["reasons"]))[:100]) for m in matches]
        super().__init__(placeholder="💼 اختار الخدمة اللي بغيتي تقبل..." if lang=="darija" else "💼 Choose a career...",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user; self.lang=lang
    async def callback(self,interaction):
        if interaction.user.id!=self.user.id: await interaction.response.send_message(t(self.lang,"not_yours"),ephemeral=True); return
        ok,msg=await self.cog.accept_job(interaction.guild,interaction.user,self.values[0]); await interaction.response.edit_message(content=msg,embed=self.cog.build_profile_embed(interaction.guild,interaction.user,self.lang),view=BackHomeView(self.cog,self.user,self.lang))

class CareerMatchesView(OwnedView):
    def __init__(self,cog,user,lang,matches): super().__init__(cog,user,lang); self.add_item(CareerMatchesSelect(cog,user,lang,matches)); b=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,self.user,self.lang),view=CityHomeView(self.cog,self.user,self.lang))


# ----------------------------------------------------------------------
# Shifts
# ----------------------------------------------------------------------
def build_shift_embed(cog,guild,user,lang):
    p=cog.profile(guild.id,user.id); shift=p.get("active_shift"); job=p.get("job_id")
    if not job: return discord.Embed(title="🕐 Shift",description="❌ خاصك خدمة الأول.",color=discord.Color.orange())
    if not shift:
        c=CAREERS[job]; return discord.Embed(title=f"🕐 Shift — {c['emoji']} {career_name(job,lang)}",description=f"اختار 30/60/90 دقيقة. الأجر الأساسي **{cog.fmt(c['hourly'])}/h**.\nاليوم {'✅ خدام' if __import__('cogs.city.shifts',fromlist=['can_work_today']).can_work_today(job) else '🏖️ يوم راحة'}.",color=discord.Color.blurple())
    task=shift.get("task") or {}; end=datetime.fromisoformat(shift["planned_end"]); check=datetime.fromisoformat(shift["checkin_at"])
    e=discord.Embed(title="🟢 Shift خدامة",description=f"{CAREERS[job]['emoji']} **{career_name(job,lang)}**\n🏁 النهاية <t:{int(end.timestamp())}:R>\n📋 Check-in <t:{int(check.timestamp())}:R>",color=discord.Color.green())
    e.add_field(name="📋 المهمة",value=("✅ تسجلات" if task.get("done") else "🔓 واجدة دابا" if checkin_ready(shift) else f"⏳ كتفتح <t:{int(check.timestamp())}:R>"),inline=False); return e

async def show_shift(interaction,cog,user,lang):
    p=cog.profile(interaction.guild.id,user.id); view=ShiftActiveView(cog,user,lang) if p.get("active_shift") else ShiftStartView(cog,user,lang); await interaction.response.edit_message(content=None,embed=build_shift_embed(cog,interaction.guild,user,lang),view=view)

class ShiftDurationSelect(discord.ui.Select):
    def __init__(self,cog,user,lang):
        opts=[discord.SelectOption(label=f"{m} دقيقة",value=str(m),emoji="🕐") for m in (30,60,90)]; super().__init__(placeholder="🕐 اختار مدة الشيفت...",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user; self.lang=lang
    async def callback(self,interaction):
        ok,msg=await self.cog.start_shift(interaction.guild,interaction.user,int(self.values[0])); await interaction.response.edit_message(content=msg,embed=build_shift_embed(self.cog,interaction.guild,interaction.user,self.lang),view=ShiftActiveView(self.cog,self.user,self.lang) if ok else ShiftStartView(self.cog,self.user,self.lang))

class ShiftStartView(OwnedView):
    def __init__(self,cog,user,lang): super().__init__(cog,user,lang); self.add_item(ShiftDurationSelect(cog,user,lang)); b=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,self.user,self.lang),view=CityHomeView(self.cog,self.user,self.lang))

class ShiftActiveView(OwnedView):
    def __init__(self,cog,user,lang):
        super().__init__(cog,user,lang); a=discord.ui.Button(label="📋 مهمة الشيفت",style=discord.ButtonStyle.primary); a.callback=self.task; self.add_item(a); b=discord.ui.Button(label="🏁 Clock-out",style=discord.ButtonStyle.success); b.callback=self.clock; self.add_item(b); c=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary); c.callback=self.back; self.add_item(c)
    async def task(self,interaction):
        shift=self.cog.profile(interaction.guild.id,self.user.id).get("active_shift")
        if not shift: await interaction.response.edit_message(content="❌ Shift سالات.",embed=None,view=BackHomeView(self.cog,self.user,self.lang)); return
        if not checkin_ready(shift):
            dt=datetime.fromisoformat(shift["checkin_at"]); await interaction.response.send_message(f"⏳ المهمة كتفتح <t:{int(dt.timestamp())}:R>.",ephemeral=True); return
        await interaction.response.edit_message(content=shift["task"]["prompt"],embed=None,view=ShiftTaskView(self.cog,self.user,self.lang,shift["task"]["options"]))
    async def clock(self,interaction):
        ok,msg=await self.cog.clock_out(interaction.guild,interaction.user); await interaction.response.edit_message(content=msg,embed=build_shift_embed(self.cog,interaction.guild,self.user,self.lang) if not ok else self.cog.build_profile_embed(interaction.guild,self.user,self.lang),view=ShiftActiveView(self.cog,self.user,self.lang) if not ok else BackHomeView(self.cog,self.user,self.lang))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,self.user,self.lang),view=CityHomeView(self.cog,self.user,self.lang))

class ShiftTaskView(OwnedView):
    def __init__(self,cog,user,lang,options):
        super().__init__(cog,user,lang)
        for i,opt in enumerate(options[:4]):
            b=discord.ui.Button(label=str(opt)[:80],style=discord.ButtonStyle.secondary,row=i//2); b.callback=self._cb(i); self.add_item(b)
    def _cb(self,i):
        async def cb(interaction):
            ok,msg=await self.cog.answer_shift_task(interaction.guild,interaction.user,i); await interaction.response.edit_message(content=msg,embed=build_shift_embed(self.cog,interaction.guild,self.user,self.lang),view=ShiftActiveView(self.cog,self.user,self.lang))
        return cb


# ----------------------------------------------------------------------
# Services / Orders
# ----------------------------------------------------------------------
def build_services_home_embed(cog,guild,user,lang):
    e=discord.Embed(title="🛍️ سوق الخدمات" if lang=="darija" else "🛍️ Services Market",description="اختار خدمة، من بعد اختار عضو خدام فيها. الفلوس كتدخل Escrow حتى الخدمة تكمل." if lang=="darija" else "Choose a service, then a real member worker. Payment stays in escrow until delivery.",color=discord.Color.green()); e.set_footer(text="Customer Wallet → Escrow → Worker Bank + Business + City Tax"); return e

class ServicesHomeView(OwnedView):
    def __init__(self,cog,user,lang):
        super().__init__(cog,user,lang); a=discord.ui.Button(label="🛍️ شري خدمة" if lang=="darija" else "🛍️ Buy Service",style=discord.ButtonStyle.success); a.callback=self.buy; self.add_item(a); b=discord.ui.Button(label="📦 طلباتي",style=discord.ButtonStyle.primary); b.callback=self.orders; self.add_item(b); c=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary); c.callback=self.back; self.add_item(c); self.add_item(CityLanguageSelect(cog,user,lang,row=1))
    async def buy(self,interaction): await interaction.response.edit_message(content="اختار الخدمة:" if self.lang=="darija" else "Choose a service:",embed=None,view=ServiceSelectView(self.cog,self.user,self.lang))
    async def orders(self,interaction): await show_orders(interaction,self.cog,self.user,self.lang)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,self.user,self.lang),view=CityHomeView(self.cog,self.user,self.lang))

class ServiceSelect(discord.ui.Select):
    def __init__(self,cog,user,lang):
        opts=[]
        for sid,s in SERVICES.items(): opts.append(discord.SelectOption(label=service_name(sid,lang)[:100],value=sid,emoji=s["emoji"],description=(f"{cog.fmt(s['price'])} • {career_name(s['career'],lang)}")[:100]))
        super().__init__(placeholder="🛍️ اختار خدمة...",options=opts[:25],min_values=1,max_values=1); self.cog=cog; self.user=user; self.lang=lang
    async def callback(self,interaction):
        sid=self.values[0]; workers=self.cog.available_workers(interaction.guild,SERVICES[sid]["career"])
        if not workers: await interaction.response.edit_message(content="📭 ماكاين حتى عامل متوفر فهاد الخدمة دابا. Career Market غادي يبان فيها الطلب." ,embed=None,view=ServicesHomeView(self.cog,self.user,self.lang)); return
        await interaction.response.edit_message(content=f"{SERVICES[sid]['emoji']} **{service_name(sid,self.lang)}** — {self.cog.fmt(SERVICES[sid]['price'])}\nاختار العامل:",embed=None,view=WorkerSelectView(self.cog,self.user,self.lang,sid,workers))

class ServiceSelectView(OwnedView):
    def __init__(self,cog,user,lang): super().__init__(cog,user,lang); self.add_item(ServiceSelect(cog,user,lang)); b=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_services_home_embed(self.cog,interaction.guild,self.user,self.lang),view=ServicesHomeView(self.cog,self.user,self.lang))

class WorkerSelect(discord.ui.Select):
    def __init__(self,cog,user,lang,sid,workers):
        opts=[]
        for m,rating,xp in workers:
            opts.append(discord.SelectOption(label=m.display_name[:100],value=str(m.id),description=(f"⭐ {rating:.2f}/5 • Career XP {xp:,}" if rating else f"🆕 New Worker • XP {xp:,}")[:100]))
        super().__init__(placeholder="👷 اختار العامل...",options=opts[:25],min_values=1,max_values=1); self.cog=cog; self.user=user; self.lang=lang; self.sid=sid
    async def callback(self,interaction):
        await interaction.response.defer(ephemeral=True); ok,msg=await self.cog.create_order(interaction.guild,interaction.user,self.sid,int(self.values[0])); await interaction.edit_original_response(content=msg,embed=build_services_home_embed(self.cog,interaction.guild,self.user,self.lang),view=ServicesHomeView(self.cog,self.user,self.lang))

class WorkerSelectView(OwnedView):
    def __init__(self,cog,user,lang,sid,workers): super().__init__(cog,user,lang); self.add_item(WorkerSelect(cog,user,lang,sid,workers)); b=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_services_home_embed(self.cog,interaction.guild,self.user,self.lang),view=ServicesHomeView(self.cog,self.user,self.lang))


def user_orders(cog,guild_id,user_id):
    rows=[]
    for o in cog.store.guild(guild_id).get("orders",{}).values():
        if int(o.get("customer_id",0))==user_id or int(o.get("worker_id",0))==user_id: rows.append(o)
    rows.sort(key=lambda x:x.get("created_at",""),reverse=True); return rows[:25]

async def show_orders(interaction,cog,user,lang):
    rows=user_orders(cog,interaction.guild.id,user.id)
    if not rows: await interaction.response.edit_message(content="📭 ماعندك حتى طلب." if lang=="darija" else "📭 No orders.",embed=None,view=BackHomeView(cog,user,lang)); return
    await interaction.response.edit_message(content="📦 اختار الطلب:" if lang=="darija" else "📦 Choose an order:",embed=None,view=OrdersListView(cog,user,lang,rows))

class OrderSelect(discord.ui.Select):
    def __init__(self,cog,user,lang,rows):
        opts=[]
        for o in rows: opts.append(discord.SelectOption(label=f"{o['id']} • {service_name(o['service_id'],lang)}"[:100],value=o["id"],description=f"{o['status']} • {cog.fmt(o['price'])}"[:100],emoji=SERVICES[o['service_id']]["emoji"]))
        super().__init__(placeholder="📦 الطلب...",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user; self.lang=lang
    async def callback(self,interaction): await show_order_detail(interaction,self.cog,self.user,self.lang,self.values[0])

class OrdersListView(OwnedView):
    def __init__(self,cog,user,lang,rows): super().__init__(cog,user,lang); self.add_item(OrderSelect(cog,user,lang,rows)); b=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,self.user,self.lang),view=CityHomeView(self.cog,self.user,self.lang))

async def show_order_detail(interaction,cog,user,lang,oid):
    o=cog.store.guild(interaction.guild.id).get("orders",{}).get(oid)
    if not o: await interaction.response.edit_message(content="❌ الطلب ما بقاش موجود.",embed=None,view=BackHomeView(cog,user,lang)); return
    worker=interaction.guild.get_member(int(o["worker_id"])); customer=interaction.guild.get_member(int(o["customer_id"])); role="العامل" if user.id==int(o["worker_id"]) else "الزبون"
    e=discord.Embed(title=f"📦 {o['id']} — {service_name(o['service_id'],lang)}",description=f"الحالة: **{o['status']}**\n💵 {cog.fmt(o['price'])}\n👷 {worker.mention if worker else o['worker_id']}\n🛍️ {customer.mention if customer else o['customer_id']}\n👤 نتا: **{role}**",color=discord.Color.blurple())
    if o.get("delivery"): e.add_field(name="📦 التسليم",value=o["delivery"][:1024],inline=False)
    await interaction.response.edit_message(content=None,embed=e,view=OrderDetailView(cog,user,lang,o))

class OrderDetailView(OwnedView):
    def __init__(self,cog,user,lang,order):
        super().__init__(cog,user,lang); self.order=order; oid=order["id"]; worker=user.id==int(order["worker_id"]); customer=user.id==int(order["customer_id"]); status=order["status"]
        if worker and status=="pending_worker":
            a=discord.ui.Button(label="✅ قبول",style=discord.ButtonStyle.success); a.callback=self.accept; self.add_item(a); r=discord.ui.Button(label="❌ رفض",style=discord.ButtonStyle.danger); r.callback=self.reject; self.add_item(r)
        if worker and status=="accepted":
            d=discord.ui.Button(label="📦 تسليم الخدمة",style=discord.ButtonStyle.success); d.callback=self.deliver; self.add_item(d)
        if customer and status=="delivered":
            c=discord.ui.Button(label="✅ تأكيد الاستلام",style=discord.ButtonStyle.success); c.callback=self.confirm; self.add_item(c)
        if customer and status=="completed" and order.get("rating") is None:
            self.add_item(RatingSelect(cog,user,lang,oid))
        b=discord.ui.Button(label="↩️ الطلبات",style=discord.ButtonStyle.secondary,row=2); b.callback=self.back; self.add_item(b)
    async def accept(self,interaction): ok,msg=await self.cog.worker_order_action(interaction.guild,interaction.user,self.order["id"],"accept"); await interaction.response.edit_message(content=msg,embed=None,view=BackHomeView(self.cog,self.user,self.lang))
    async def reject(self,interaction): ok,msg=await self.cog.worker_order_action(interaction.guild,interaction.user,self.order["id"],"reject"); await interaction.response.edit_message(content=msg,embed=None,view=BackHomeView(self.cog,self.user,self.lang))
    async def deliver(self,interaction): await interaction.response.send_modal(DeliveryModal(self.cog,self.order["id"],self.lang))
    async def confirm(self,interaction):
        await interaction.response.defer(ephemeral=True); ok,msg=await self.cog.customer_confirm_order(interaction.guild,interaction.user,self.order["id"]); await interaction.edit_original_response(content=msg,embed=None,view=BackHomeView(self.cog,self.user,self.lang))
    async def back(self,interaction): await show_orders(interaction,self.cog,self.user,self.lang)

class DeliveryModal(discord.ui.Modal):
    def __init__(self,cog,oid,lang): self.cog=cog; self.oid=oid; self.lang=lang; super().__init__(title="📦 تسليم الخدمة"); self.note=discord.ui.TextInput(label="شنو سلمتي للزبون؟",style=discord.TextStyle.paragraph,min_length=5,max_length=900); self.add_item(self.note)
    async def on_submit(self,interaction): ok,msg=await self.cog.worker_order_action(interaction.guild,interaction.user,self.oid,"deliver",str(self.note.value)); await interaction.response.edit_message(content=msg,embed=None,view=BackHomeView(self.cog,interaction.user,self.lang))

class RatingSelect(discord.ui.Select):
    def __init__(self,cog,user,lang,oid): super().__init__(placeholder="⭐ قيّم الخدمة...",options=[discord.SelectOption(label=f"{i}/5",value=str(i),emoji="⭐") for i in range(1,6)],min_values=1,max_values=1,row=1); self.cog=cog; self.user=user; self.lang=lang; self.oid=oid
    async def callback(self,interaction): ok,msg=await self.cog.rate_worker(interaction.guild,interaction.user,self.oid,int(self.values[0])); await interaction.response.edit_message(content=msg,embed=None,view=BackHomeView(self.cog,self.user,self.lang))


# ----------------------------------------------------------------------
# Projects
# ----------------------------------------------------------------------
def build_projects_home_embed(cog,guild,user,lang):
    e=discord.Embed(title="🏗️ المشاريع والعقود" if lang=="darija" else "🏗️ Projects & Contracts",description="حط Budget حقيقي فـEscrow، خلي العامل المناسب يقدم، وحرر الأداء Milestone بMilestone." if lang=="darija" else "Fund real escrow, recruit a suitable worker, and release milestone payments.",color=discord.Color.orange()); return e

class ProjectsHomeView(OwnedView):
    def __init__(self,cog,user,lang):
        super().__init__(cog,user,lang); a=discord.ui.Button(label="➕ صاوب مشروع",style=discord.ButtonStyle.success); a.callback=self.create; self.add_item(a); b=discord.ui.Button(label="🔎 المشاريع المفتوحة",style=discord.ButtonStyle.primary); b.callback=self.browse; self.add_item(b); c=discord.ui.Button(label="📁 مشاريعي",style=discord.ButtonStyle.secondary); c.callback=self.mine; self.add_item(c); d=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary); d.callback=self.back; self.add_item(d); self.add_item(CityLanguageSelect(cog,user,lang,row=1))
    async def create(self,interaction): await interaction.response.edit_message(content="💼 اختار Career اللي المشروع محتاجها:",embed=None,view=ProjectCareerView(self.cog,self.user,self.lang))
    async def browse(self,interaction): await show_open_projects(interaction,self.cog,self.user,self.lang)
    async def mine(self,interaction): await show_my_projects(interaction,self.cog,self.user,self.lang)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,self.user,self.lang),view=CityHomeView(self.cog,self.user,self.lang))

class ProjectCareerSelect(discord.ui.Select):
    def __init__(self,cog,user,lang):
        opts=[discord.SelectOption(label=career_name(cid,lang)[:100],value=cid,emoji=c["emoji"]) for cid,c in CAREERS.items()]; super().__init__(placeholder="💼 Career المطلوبة...",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user; self.lang=lang
    async def callback(self,interaction): await interaction.response.send_modal(ProjectCreateModal(self.cog,self.values[0],self.lang))

class ProjectCareerView(OwnedView):
    def __init__(self,cog,user,lang): super().__init__(cog,user,lang); self.add_item(ProjectCareerSelect(cog,user,lang)); b=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_projects_home_embed(self.cog,interaction.guild,self.user,self.lang),view=ProjectsHomeView(self.cog,self.user,self.lang))

class ProjectCreateModal(discord.ui.Modal):
    def __init__(self,cog,career_id,lang):
        self.cog=cog; self.career_id=career_id; self.lang=lang; super().__init__(title="🏗️ مشروع جديد")
        self.title_i=discord.ui.TextInput(label="اسم المشروع",max_length=80); self.desc=discord.ui.TextInput(label="شنو خاص يتدار؟",style=discord.TextStyle.paragraph,min_length=10,max_length=1000); self.budget=discord.ui.TextInput(label="Budget بالدولار",placeholder="مثال: 50 أو 120.50",max_length=20); self.deadline=discord.ui.TextInput(label="Deadline بالأيام",placeholder="7",max_length=2); self.milestones=discord.ui.TextInput(label="Milestones (قسمهم بـ |)",placeholder="Logo | Banner | Final Pack",required=False,max_length=240)
        for x in (self.title_i,self.desc,self.budget,self.deadline,self.milestones): self.add_item(x)
    async def on_submit(self,interaction):
        amount=root_cfg.parse_money_input(str(self.budget.value));
        try: days=int(str(self.deadline.value).strip())
        except: days=7
        if amount is None: await interaction.response.send_message("❌ Budget ماصالحاش.",ephemeral=True); return
        await interaction.response.defer(ephemeral=True); ok,msg=await self.cog.create_project(interaction.guild,interaction.user,career_id=self.career_id,title=str(self.title_i.value),description=str(self.desc.value),budget=amount,deadline_days=days,milestones_raw=str(self.milestones.value)); await interaction.edit_original_response(content=msg,embed=build_projects_home_embed(self.cog,interaction.guild,interaction.user,self.lang),view=ProjectsHomeView(self.cog,interaction.user,self.lang))


def open_projects(cog,guild):
    rows=[p for p in cog.store.guild(guild.id).get("projects",{}).values() if p.get("status")=="open"]; rows.sort(key=lambda x:x.get("created_at",""),reverse=True); return rows[:25]

async def show_open_projects(interaction,cog,user,lang):
    rows=open_projects(cog,interaction.guild)
    if not rows: await interaction.response.edit_message(content="📭 ماكاين حتى مشروع مفتوح دابا.",embed=None,view=ProjectsHomeView(cog,user,lang)); return
    await interaction.response.edit_message(content="🔎 اختار مشروع:",embed=None,view=OpenProjectsListView(cog,user,lang,rows))

class ProjectSelect(discord.ui.Select):
    def __init__(self,cog,user,lang,rows,mode="open"):
        opts=[discord.SelectOption(label=f"{p['id']} • {p['title']}"[:100],value=p["id"],emoji=CAREERS[p["career_id"]]["emoji"],description=f"{career_name(p['career_id'],lang)} • {cog.fmt(p['budget'])} • {p['status']}"[:100]) for p in rows]; super().__init__(placeholder="🏗️ المشروع...",options=opts,min_values=1,max_values=1); self.cog=cog; self.user=user; self.lang=lang; self.mode=mode
    async def callback(self,interaction): await show_project_detail(interaction,self.cog,self.user,self.lang,self.values[0])

class OpenProjectsListView(OwnedView):
    def __init__(self,cog,user,lang,rows): super().__init__(cog,user,lang); self.add_item(ProjectSelect(cog,user,lang,rows)); b=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary,row=1); b.callback=self.back; self.add_item(b)
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_projects_home_embed(self.cog,interaction.guild,self.user,self.lang),view=ProjectsHomeView(self.cog,self.user,self.lang))

async def show_my_projects(interaction,cog,user,lang):
    rows=[p for p in cog.store.guild(interaction.guild.id).get("projects",{}).values() if int(p.get("owner_id",0))==user.id or int(p.get("worker_id") or 0)==user.id or user.id in (p.get("applicants") or [])]; rows.sort(key=lambda x:x.get("created_at",""),reverse=True); rows=rows[:25]
    if not rows: await interaction.response.edit_message(content="📭 ماعندك حتى Project.",embed=None,view=ProjectsHomeView(cog,user,lang)); return
    await interaction.response.edit_message(content="📁 اختار المشروع:",embed=None,view=OpenProjectsListView(cog,user,lang,rows))

async def show_project_detail(interaction,cog,user,lang,pid):
    p=cog.store.guild(interaction.guild.id).get("projects",{}).get(pid)
    if not p: await interaction.response.edit_message(content="❌ Project ما بقاش موجود.",embed=None,view=ProjectsHomeView(cog,user,lang)); return
    e=discord.Embed(title=f"🏗️ {p['id']} — {p['title']}",description=f"{p['description']}\n\n💼 **{career_name(p['career_id'],lang)}** • 💰 **{cog.fmt(p['budget'])}** • الحالة **{p['status']}**\n⏳ Deadline <t:{int(datetime.fromisoformat(p['deadline_at']).timestamp())}:R>",color=discord.Color.orange())
    ms=[]
    for m in p.get("milestones",[]): ms.append(f"{'✅' if m['status']=='approved' else '📦' if m['status']=='delivered' else '⬜'} **{m['title']}** — {cog.fmt(m['amount'])} • {m['status']}")
    e.add_field(name="📋 Milestones",value="\n".join(ms),inline=False); e.add_field(name="👥 Applicants",value=str(len(p.get("applicants",[]))),inline=True)
    await interaction.response.edit_message(content=None,embed=e,view=ProjectDetailView(cog,user,lang,p))

class ProjectDetailView(OwnedView):
    def __init__(self,cog,user,lang,p):
        super().__init__(cog,user,lang); self.p=p; owner=user.id==int(p["owner_id"]); worker=user.id==int(p.get("worker_id") or 0); status=p["status"]
        if status=="open" and not owner:
            a=discord.ui.Button(label="📝 قدم نخدم",style=discord.ButtonStyle.success); a.callback=self.apply; self.add_item(a)
        if status=="open" and owner and p.get("applicants"):
            self.add_item(AssignApplicantSelect(cog,user,lang,p))
        if status=="open" and owner:
            c=discord.ui.Button(label="🗑️ إلغاء + Refund",style=discord.ButtonStyle.danger,row=1); c.callback=self.cancel; self.add_item(c)
        if worker and status in {"assigned","in_progress"}:
            d=discord.ui.Button(label="📦 سلم Milestone",style=discord.ButtonStyle.success); d.callback=self.deliver; self.add_item(d)
        if owner and status=="delivered":
            a=discord.ui.Button(label="✅ قبول Milestone + Pay",style=discord.ButtonStyle.success); a.callback=self.approve; self.add_item(a)
        b=discord.ui.Button(label="↩️ المشاريع",style=discord.ButtonStyle.secondary,row=2); b.callback=self.back; self.add_item(b)
    async def apply(self,interaction): ok,msg=await self.cog.apply_project(interaction.guild,interaction.user,self.p["id"]); await interaction.response.edit_message(content=msg,embed=None,view=ProjectsHomeView(self.cog,self.user,self.lang))
    async def cancel(self,interaction): ok,msg=await self.cog.cancel_open_project(interaction.guild,interaction.user,self.p["id"]); await interaction.response.edit_message(content=msg,embed=None,view=ProjectsHomeView(self.cog,self.user,self.lang))
    async def deliver(self,interaction): await interaction.response.send_modal(ProjectDeliveryModal(self.cog,self.p["id"],self.lang))
    async def approve(self,interaction):
        await interaction.response.defer(ephemeral=True); ok,msg=await self.cog.approve_project_milestone(interaction.guild,interaction.user,self.p["id"]); await interaction.edit_original_response(content=msg,embed=None,view=ProjectsHomeView(self.cog,self.user,self.lang))
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_projects_home_embed(self.cog,interaction.guild,self.user,self.lang),view=ProjectsHomeView(self.cog,self.user,self.lang))

class AssignApplicantSelect(discord.ui.Select):
    def __init__(self,cog,user,lang,p):
        opts=[]
        for uid in p.get("applicants",[])[:25]:
            m=user.guild.get_member(int(uid)) if isinstance(user,discord.Member) else None
            if m: opts.append(discord.SelectOption(label=m.display_name[:100],value=str(uid),description=f"⭐ {cog.rating(user.guild.id,m.id):.2f}/5" if cog.rating(user.guild.id,m.id) else "New Worker"))
        super().__init__(placeholder="👷 اختار العامل...",options=opts,min_values=1,max_values=1,row=0); self.cog=cog; self.user=user; self.lang=lang; self.pid=p["id"]
    async def callback(self,interaction): ok,msg=await self.cog.assign_project(interaction.guild,interaction.user,self.pid,int(self.values[0])); await interaction.response.edit_message(content=msg,embed=None,view=ProjectsHomeView(self.cog,self.user,self.lang))

class ProjectDeliveryModal(discord.ui.Modal):
    def __init__(self,cog,pid,lang): self.cog=cog; self.pid=pid; self.lang=lang; super().__init__(title="📦 تسليم Milestone"); self.note=discord.ui.TextInput(label="شنو تسلم؟",style=discord.TextStyle.paragraph,min_length=5,max_length=900); self.add_item(self.note)
    async def on_submit(self,interaction): ok,msg=await self.cog.deliver_project_milestone(interaction.guild,interaction.user,self.pid,str(self.note.value)); await interaction.response.edit_message(content=msg,embed=None,view=ProjectsHomeView(self.cog,interaction.user,self.lang))


# ----------------------------------------------------------------------
# Documents / Notifications
# ----------------------------------------------------------------------
async def show_documents(interaction,cog,user,lang):
    docs=cog.documents(interaction.guild.id,user.id); lines=[]
    for p in docs["payslips"][:5]: lines.append(f"💳 **{p['id']}** • {career_name(p['career_id'],lang)} • Paid {cog.fmt(p['paid'])}"+(f" • Due {cog.fmt(p['due'])}" if p['due'] else ""))
    for i in docs["invoices"][:5]: lines.append(f"🧾 **{i['id']}** • {i.get('kind')} • {cog.fmt(i.get('amount',0))} • {i.get('status','')}")
    e=discord.Embed(title="💳 الرواتب والفواتير" if lang=="darija" else "💳 Payslips & Invoices",description="\n".join(lines) if lines else "📭 مازال ماكاين والو.",color=discord.Color.teal()); await interaction.response.edit_message(content=None,embed=e,view=BackHomeView(cog,user,lang))

def build_notification_embed(cog,guild,user,lang):
    prefs=cog.profile(guild.id,user.id).get("notifications",{}); names={"dm":"DM","fallback":"city-alerts fallback","jobs":"Job Offers","orders":"Orders","shifts":"Shifts","payments":"Payments","promotions":"Promotions","projects":"Projects"}; e=discord.Embed(title="🔔 إعدادات التنبيهات",description="\n".join(f"{'✅' if prefs.get(k,True) else '❌'} **{v}**" for k,v in names.items()),color=discord.Color.blurple()); return e

class NotificationView(OwnedView):
    def __init__(self,cog,user,lang):
        super().__init__(cog,user,lang); prefs=cog.profile(user.guild.id,user.id).get("notifications",{}) if isinstance(user,discord.Member) else {}
        for i,k in enumerate(("dm","fallback","orders","shifts","payments","projects")):
            b=discord.ui.Button(label=f"{'✅' if prefs.get(k,True) else '❌'} {k}",style=discord.ButtonStyle.secondary,row=i//3); b.callback=self._toggle(k); self.add_item(b)
        back=discord.ui.Button(label="↩️ "+t(lang,"back"),style=discord.ButtonStyle.secondary,row=2); back.callback=self.back; self.add_item(back)
    def _toggle(self,key):
        async def cb(interaction):
            p=self.cog.profile(interaction.guild.id,interaction.user.id); p["notifications"][key]=not bool(p["notifications"].get(key,True)); self.cog.store.save(); await interaction.response.edit_message(embed=build_notification_embed(self.cog,interaction.guild,interaction.user,self.lang),view=NotificationView(self.cog,interaction.user,self.lang))
        return cb
    async def back(self,interaction): await interaction.response.edit_message(content=None,embed=build_home_embed(self.cog,interaction.guild,self.user,self.lang),view=CityHomeView(self.cog,self.user,self.lang))
