# cogs/advanced_moderation.py
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import discord
from discord.ext import commands
from discord import app_commands

# IMPORTS مهمّة من الكود الأساسي ديالك
# عدّل المسار ai_bot حسب اسم الملف الحقيقي (ai_bot.py → ai_bot في import)
from ai_bot import (
    OWNER_ID,
    SERVER_NAME,
    MUTED_ROLE_ID,
    # warns / cases
    get_warns,
    clear_warns,
    add_warn,
    log_case,
    get_case,
    get_cases_for_user,
    is_exempt,
    mute_tasks,
    apply_warn_escalation,
    # banned words / actions
    BANNED_WORDS,
    banned_words_state,
    BANNEDACTIONS,
    save_banned_lists,
    get_active_banned_words,
    # anti-raid
    trigger_raid_lockdown,
    end_raid_lockdown,
    raid_state,
    recent_joins,
    bot_settings,
)


class AdvancedModeration(commands.Cog):
    """
    جميع أوامر الموديريشن المتقدمة اللي كانت فـ ai_bot-64.py
    منفصلة فـ Cog واحد باش مايدوبلوش مع cogs.moderation.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # =====================
    # WARN / OLD WARNS SYSTEM
    # =====================

    @commands.hybridcommand(
        description="Old warn command (legacy auto-mod escalation)",
        with_app_command=True,
    )
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def oldwarn(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str,
    ):
        if OWNERID and member.id == OWNERID:
            await ctx.send("Owner !", delete_after=5)
            return
        if isexemptmember(member):
            await ctx.send("Auto-Mod/Moderation Admin/Mod!", delete_after=5)
            return

        count = await addwarnmember(member, reason)

        caseid = await logcase(
            ctx.guild,
            "Warn",
            "",
            discord.Color.yellow,
            target=member,
            moderator=ctx.author,
            reason=reason,
            extra=str(count),
        )

        embed = discord.Embed(
            title="Warn",
            description=f"{member.mention} تم تحذيرو.",
            color=discord.Color.yellow,
            timestamp=datetime.now(),
        )
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(
            name="Count",
            value=f"{count} (Mute: {botsettingsmuteafterwarns}, Kick: {botsettingskickafterwarns}, Ban: {botsettingsbanafterwarns})",
            inline=False,
        )
        embed.add_field(name="Moderator", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"{SERVERNAME} Moderation • Case {caseid}")
        await ctx.send(embed=embed)

        action = await applywarnescalation(
            member,
            ctx.guild,
            count,
            reason,
            channel=ctx.channel,
        )
        if action is None and count == botsettingsmuteafterwarns:
            await ctx.send(
                "Reached mute threshold but auto-mute failed.",
                delete_after=10,
            )

    @commands.hybridcommand(
        description="Old warns summary (legacy)",
        with_app_command=True,
    )
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def oldwarns(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        member = member or ctx.author
        userwarns = getwarns(str(member.id))  # dict: count, reasons, dates

        embed = discord.Embed(
            title=f"Warns • {member.display_name}",
            color=discord.Color.yellow,
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="Count",
            value=f"{userwarns.get('count', 0)} (Mute: {botsettingsmuteafterwarns}, Kick: {botsettingskickafterwarns}, Ban: {botsettingsbanafterwarns})",
            inline=False,
        )

        reasons = userwarns.get("reasons", [])
        dates = userwarns.get("dates", [])
        if reasons:
            lines = []
            for i, r in enumerate(reasons):
                date_str = dates[i] if i < len(dates) else "Unknown date"
                lines.append(f"{i+1}. {r} ({date_str})")
            embed.add_field(
                name="Reasons",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="Reasons",
                value="No warns.",
                inline=False,
            )

        embed.set_footer(text=f"{SERVERNAME} Moderation")
        await ctx.send(embed=embed)

    @commands.hybridcommand(
        description="Old unwarn (clear all warns)",
        with_app_command=True,
    )
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def oldunwarn(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ):
        clearwarns(str(member.id))
        caseid = await logcase(
            ctx.guild,
            "Unwarn",
            "",
            discord.Color.green,
            target=member,
            moderator=ctx.author,
            reason="Cleared all warns",
        )
        embed = discord.Embed(
            title="Unwarn",
            description=f"{member.mention} تم حدف جميع التحذيرات.",
            color=discord.Color.green,
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"{SERVERNAME} Moderation • Case {caseid}")
        await ctx.send(embed=embed)

    # =====================
    # CASE / HISTORY
    # =====================

    @commands.hybridcommand(
        name="case",
        description="Show a moderation case by ID",
        with_app_command=True,
    )
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def casecmd(self, ctx: commands.Context, caseid: int):
        record = getcase(caseid)
        if not record:
            await ctx.send(f"Case {caseid} not found.")
            return

        color = discord.Color.blurple

        embed = discord.Embed(
            title=f"Case {record.get('id')} • {record.get('action')}",
            color=color,
            timestamp=datetime.now(),
        )

        targetvalue = (
            f"{record.get('targetid')} ({record.get('targetname')})"
            if record.get("targetid")
            else record.get("targetname")
        )
        modvalue = (
            f"{record.get('moderatorid')} ({record.get('moderatorname')})"
            if record.get("moderatorid")
            else record.get("moderatorname")
        )

        embed.add_field(name="Target", value=targetvalue, inline=False)
        embed.add_field(name="Moderator", value=modvalue, inline=False)
        embed.add_field(name="Reason", value=record.get("reason", "None"), inline=False)
        if record.get("extra"):
            embed.add_field(name="Extra", value=record["extra"], inline=False)
        embed.add_field(
            name="Time",
            value=record.get("timestamp", "Unknown"),
            inline=False,
        )
        embed.set_footer(text=f"{SERVERNAME} Case {record.get('id')}")
        await ctx.send(embed=embed)

    @commands.hybridcommand(
        name="history",
        description="Moderation history for a member",
        with_app_command=True,
    )
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def historycmd(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        member = member or ctx.author
        usercases = getcasesforuser(member.id)

        embed = discord.Embed(
            title=f"Moderation history • {member.display_name}",
            color=discord.Color.blurple,
            timestamp=datetime.now(),
        )

        if not usercases:
            embed.add_field(name="Cases", value="No cases.", inline=False)
        else:
            lines = []
            for c in usercases[:15]:
                moddisplay = c.get("moderatorname", "Unknown")
                lines.append(
                    f"#{c.get('id')} • {c.get('action')} • {c.get('reason')} • {moddisplay} • {c.get('timestamp')}"
                )
            embed.description = "\n".join(lines)
            embed.add_field(name="Total cases", value=str(len(usercases)), inline=False)

        embed.set_footer(text=f"{SERVERNAME} Moderation History")
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
        await ctx.send(embed=embed)

    # =====================
    # BANNED WORDS / ACTIONS
    # =====================

    @commands.hybridcommand(
        name="addword",
        description="Add banned word (Auto-Mod)",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def addwordcmd(self, ctx: commands.Context, *, word: str):
        word = word.strip()
        if not word:
            return
        if not ctx.author.guild_permissions.administrator:
            return

        if word in bannedwordsstateremoved:
            bannedwordsstateremoved.remove(word)
        if word not in bannedwordsstateextra and word not in BANNEDWORDS:
            bannedwordsstateextra.append(word)
        savebannedlists()
        try:
            await ctx.author.send(
                f"تم إضافة الكلمة.\nالكلمات النشيطة: {len(getactivebannedwords())}"
            )
        except Exception:
            pass

    @commands.hybridcommand(
        name="removeword",
        description="Remove banned word (Auto-Mod)",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def removewordcmd(self, ctx: commands.Context, *, word: str):
        word = word.strip()
        if not word:
            return
        if not ctx.author.guild_permissions.administrator:
            return

        if word in bannedwordsstateextra:
            bannedwordsstateextra.remove(word)
        if word in BANNEDWORDS and word not in bannedwordsstateremoved:
            bannedwordsstateremoved.append(word)
        savebannedlists()
        try:
            await ctx.author.send(
                f"تم حذف الكلمة.\nالكلمات النشيطة: {len(getactivebannedwords())}"
            )
        except Exception:
            pass

    @commands.hybridcommand(
        name="addaction",
        description="Add Auto-Mod action phrase (Owner)",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def addactioncmd(self, ctx: commands.Context, *, phrase: str):
        phrase = phrase.strip()
        if not phrase or phrase in BANNEDACTIONS:
            return
        if not ctx.author.guild_permissions.administrator or (
            OWNERID and ctx.author.id != OWNERID
        ):
            return

        BANNEDACTIONS.append(phrase)
        savebannedlists()
        try:
            await ctx.author.send(
                f"تم إضافة phrase.\nعدد الأفعال النشيطة: {len(BANNEDACTIONS)}"
            )
        except Exception:
            pass

    @commands.hybridcommand(
        name="removeaction",
        description="Remove Auto-Mod action phrase (Owner)",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def removeactioncmd(self, ctx: commands.Context, *, phrase: str):
        phrase = phrase.strip()
        if not phrase:
            return
        if not ctx.author.guild_permissions.administrator or (
            OWNERID and ctx.author.id != OWNERID
        ):
            return

        if phrase in BANNEDACTIONS:
            BANNEDACTIONS.remove(phrase)
            savebannedlists()
        try:
            await ctx.author.send(
                f"تم حذف phrase.\nعدد الأفعال النشيطة: {len(BANNEDACTIONS)}"
            )
        except Exception:
            pass

    @commands.hybridcommand(
        name="listbanned",
        description="List banned words & actions (DM to Owner/Admin)",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def listbannedcmd(self, ctx: commands.Context):
        if not ctx.author.guild_permissions.administrator:
            return

        words = getactivebannedwords()
        actions = BANNEDACTIONS

        text_words = "\n".join(f"- {w}" for w in words) or "No words."
        text_actions = "\n".join(f"- {a}" for a in actions) or "No actions."

        try:
            await ctx.author.send(
                f"Active banned words ({len(words)}):\n{text_words}\n\n"
                f"Active actions ({len(actions)}):\n{text_actions}"
            )
        except Exception:
            pass

    # =====================
    # OWNER MODERATION + MUTEALL / UNMUTEALL
    # =====================

    @commands.hybridcommand(
        name="ownerkick",
        description="Owner-only kick",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def ownerkickcmd(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str = "No reason",
    ):
        if OWNERID and ctx.author.id != OWNERID:
            return
        if member.id == OWNERID:
            await ctx.send("Owner !", delete_after=5)
            return
        try:
            await member.kick(reason=reason)
            caseid = await logcase(
                ctx.guild,
                "Owner Kick",
                "",
                discord.Color.orange,
                target=member,
                moderator=ctx.author,
                reason=reason,
            )
            await ctx.send(
                f"{member.mention} تم طرده من طرف Owner. Case {caseid}",
                delete_after=6,
            )
        except discord.Forbidden:
            await ctx.send("! ماقدرش يطردو (Discord permissions).", delete_after=5)
        except Exception as e:
            await ctx.send(str(e), delete_after=5)

    @commands.hybridcommand(
        name="ownerban",
        description="Owner-only ban",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def ownerbancmd(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str = "No reason",
    ):
        if OWNERID and ctx.author.id != OWNERID:
            return
        if member.id == OWNERID:
            await ctx.send("Owner !", delete_after=5)
            return
        try:
            await member.ban(reason=reason)
            caseid = await logcase(
                ctx.guild,
                "Owner Ban",
                "",
                discord.Color.red,
                target=member,
                moderator=ctx.author,
                reason=reason,
            )
            await ctx.send(
                f"{member.mention} تم حظرو من طرف Owner. Case {caseid}",
                delete_after=6,
            )
        except discord.Forbidden:
            await ctx.send("! ماقدرش يبانيو (Discord permissions).", delete_after=5)
        except Exception as e:
            await ctx.send(str(e), delete_after=5)

    @commands.hybridcommand(
        name="ownermute",
        description="Owner-only manual mute",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def ownermutecmd(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: int = 5,
        *,
        reason: str = "No reason",
    ):
        if OWNERID and ctx.author.id != OWNERID:
            return
        if member.id == OWNERID:
            await ctx.send("Owner !", delete_after=5)
            return

        mutedrole = ctx.guild.get_role(MUTEDROLEID)
        if not mutedrole:
            await ctx.send(f"Mute role not found! ID = {MUTEDROLEID}", delete_after=5)
            return

        try:
            await member.add_roles(mutedrole)
            userid = str(member.id)
            if userid in mutetasks and not mutetasks[userid].done():
                mutetasks[userid].cancel()
            task = asyncio.create_task(
                self._autounmute(member, duration, ctx.guild)
            )
            mutetasks[userid] = task

            caseid = await logcase(
                ctx.guild,
                "Owner Mute",
                "",
                discord.Color.yellow,
                target=member,
                moderator=ctx.author,
                reason=reason,
                extra=str(duration),
            )
            await ctx.send(
                f"{member.mention} تم ميوت لمدة {duration} دقيقة من طرف Owner. Case {caseid}",
                delete_after=6,
            )
        except discord.Forbidden:
            await ctx.send("! ماقدرش يدير الميوت (Discord permissions).", delete_after=5)
        except Exception as e:
            await ctx.send(str(e), delete_after=5)

    async def _autounmute(self, member: discord.Member, duration: int, guild: discord.Guild):
        await asyncio.sleep(duration * 60)
        mutedrole = guild.get_role(MUTEDROLEID)
        if mutedrole and mutedrole in member.roles:
            try:
                await member.remove_roles(mutedrole)
            except Exception:
                pass

    @commands.hybridcommand(
        name="muteall",
        description="Owner: mute all non-exempt members (Server Lockdown)",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def muteallcmd(self, ctx: commands.Context, *, reason: str):
        if OWNERID and ctx.author.id != OWNERID:
            return

        mutedrole = ctx.guild.get_role(MUTEDROLEID)
        if not mutedrole:
            await ctx.send(f"Mute role not found! ID = {MUTEDROLEID}", delete_after=5)
            return

        statusmsg = await ctx.send("Starting mute-all...")
        mutedcount = 0

        for member in ctx.guild.members:
            if (
                member.bot
                or member.id == OWNERID
                or isexemptmember(member)
                or mutedrole in member.roles
            ):
                continue
            try:
                await member.add_roles(mutedrole, reason=reason)
                mutedcount += 1
                await asyncio.sleep(0.4)
            except (discord.Forbidden, discord.HTTPException):
                continue

        await statusmsg.edit(content=f"Muted {mutedcount} members (Owner mute-all).")

    @commands.hybridcommand(
        name="unmuteall",
        description="Owner: unmute all members",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    async def unmuteallcmd(self, ctx: commands.Context):
        if OWNERID and ctx.author.id != OWNERID:
            return

        mutedrole = ctx.guild.get_role(MUTEDROLEID)
        if not mutedrole:
            await ctx.send("Mute role not found!", delete_after=5)
            return

        statusmsg = await ctx.send("Starting unmute-all...")
        unmutedcount = 0

        for member in list(mutedrole.members):
            try:
                await member.remove_roles(mutedrole)
                unmutedcount += 1
                userid = str(member.id)
                if userid in mutetasks and not mutetasks[userid].done():
                    mutetasks[userid].cancel()
                await asyncio.sleep(0.4)
            except (discord.Forbidden, discord.HTTPException):
                continue

        await statusmsg.edit(content=f"Unmuted {unmutedcount} members.")

    # =====================
    # ANTI-RAID COMMANDS
    # =====================

    @commands.hybridcommand(
        name="lockdown",
        description="Anti-Raid Lockdown",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def lockdowncmd(
        self,
        ctx: commands.Context,
        durationminutes: Optional[int] = None,
    ):
        started = await triggerraidlockdown(
            ctx.guild,
            reason=f"Lockdown by {ctx.author.mention}.",
            durationminutes=durationminutes,
        )
        if started:
            durtxt = (
                f"{durationminutes}m"
                if durationminutes
                else f"{botsettingsraidlockdowndurationminutes}m"
                if botsettingsraidlockdowndurationminutes
                else "until manual unlock"
            )
            await ctx.send(f"Lockdown started. Duration: {durtxt}.")
        else:
            await ctx.send("Lockdown is already active.", delete_after=6)

    @commands.hybridcommand(
        name="unlockdown",
        description="End Anti-Raid lockdown",
        with_app_command=True,
    )
    @app_commands.default_permissions(administrator=True)
    @commands.has_permissions(administrator=True)
    async def unlockdowncmd(self, ctx: commands.Context):
        ended = await endraidlockdown(
            ctx.guild,
            reason=f"Manual unlock by {ctx.author.mention}",
        )
        if ended:
            await ctx.send("Lockdown ended.")
        else:
            await ctx.send("No active lockdown.", delete_after=6)

    @commands.hybridcommand(
        name="raidstatus",
        description="Anti-Raid status",
        with_app_command=True,
    )
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def raidstatuscmd(self, ctx: commands.Context):
        now = datetime.now()
        state = raidstate.get(ctx.guild.id, {})
        cutoff = now - timedelta(seconds=botsettingsraidjoinintervalseconds)
        recent = [t for t in recentjoins.get(ctx.guild.id, []) if t > cutoff]

        embed = discord.Embed(
            title="Anti-Raid Status",
            color=discord.Color.red if state.get("active") else discord.Color.green,
            timestamp=datetime.now(),
        )
        embed.add_field(
            name="Lockdown",
            value="Active" if state.get("active") else "Inactive",
            inline=False,
        )
        embed.add_field(
            name="Recent joins",
            value=f"{len(recent)} / {botsettingsraidjointhreshold} in {botsettingsraidjoinintervalseconds}s",
            inline=False,
        )
        embed.add_field(
            name="Lockdown action",
            value="Ban" if botsettingsraidaction == "ban" else "Kick",
            inline=False,
        )
        embed.set_footer(text=f"{SERVERNAME} Anti-Raid Protection")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdvancedModeration(bot))
    print("Advanced Moderation Cog loaded")
