# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║ cogs/moderation.py — 🛡️ موديريشن + صلاحيات Owner  ║
═══════════════════════════════════════════════════════

أوامر:
 /kick       — طرد
 /ban        — حظر
 /unban      — فك الحظر
 /mute       — كتم
 /unmute     — فك الكتم
 /clear      — مسح رسائل
 /warn       — تحذير
 /warns      — عرض التحذيرات
 /unwarn     — مسح التحذيرات
 /permspanel — بانل تتحكم منّو فصلاحيات هاد الأوامر
"""

import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

OWNER_ID = 1260089246216097832  # ← عدّلها بنفس OWNER_ID ديالك
SERVER_NAME = "GGMW9"

EXEMPT_ROLE_IDS = [
    1525712399456272495,  # Admin
    1526182506272133180,  # Moderator
]

MUTED_ROLE_ID = 1526468718534590574

COLOR_WARN = discord.Color.yellow()
COLOR_MUTE = discord.Color.yellow()
COLOR_UNMUTE = discord.Color.green()
COLOR_KICK = discord.Color.orange()
COLOR_BAN = discord.Color.red()
COLOR_UNBAN = discord.Color.green()

COMMAND_ROLES = {
    "kick":   {"owner_only": False, "allowed_roles": []},
    "ban":    {"owner_only": False, "allowed_roles": []},
    "unban":  {"owner_only": False, "allowed_roles": []},
    "mute":   {"owner_only": False, "allowed_roles": []},
    "unmute": {"owner_only": False, "allowed_roles": []},
    "clear":  {"owner_only": False, "allowed_roles": []},
    "warn":   {"owner_only": False, "allowed_roles": []},
    "warns":  {"owner_only": False, "allowed_roles": []},
    "unwarn": {"owner_only": False, "allowed_roles": []},
}

DISPLAY_NAMES = {
    "kick":   "طرد",
    "ban":    "حظر",
    "unban":  "فك الحظر",
    "mute":   "كتم",
    "unmute": "فك الكتم",
    "clear":  "مسح رسائل",
    "warn":   "تحذير",
    "warns":  "عرض التحذيرات",
    "unwarn": "مسح التحذيرات",
}


def is_exempt(member: discord.Member) -> bool:
    if OWNER_ID and member.id == OWNER_ID:
        return True
    if EXEMPT_ROLE_IDS:
        member_role_ids = {role.id for role in member.roles}
        if member_role_ids.intersection(EXEMPT_ROLE_IDS):
            return True
    return False


def has_custom_command_access(member: discord.Member, command_name: str) -> bool:
    if OWNER_ID and member.id == OWNER_ID:
        return True

    cfg = COMMAND_ROLES.get(command_name)
    if not cfg:
        return True

    if cfg.get("owner_only"):
        return False

    allowed_roles = cfg.get("allowed_roles") or []
    if not allowed_roles:
        return True

    member_roles = {r.id for r in member.roles}
    return bool(member_roles.intersection(allowed_roles))


# ─── تحذيرات بسيطة ───

warns_db = {}  # {user_id: {"count": int, "reasons": [...], "dates": [...]}}


def get_warns(user_id: str) -> dict:
    return warns_db.get(user_id, {"count": 0, "reasons": [], "dates": []})


def clear_warns(user_id: str):
    if user_id in warns_db:
        warns_db[user_id] = {"count": 0, "reasons": [], "dates": []}


async def send_warn_dm(member: discord.Member, count: int, reason: str):
    embed = discord.Embed(
        title="⚠️ تحذير جديد",
        color=discord.Color.orange(),
        timestamp=datetime.now(),
    )
    embed.add_field(
        name="🇲🇦 بالدارجة",
        value=f"خذيتي تحذير فـ **{SERVER_NAME}**.\n"
              f"**السبب:** {reason}\n"
              f"**عدد التحذيرات دابا:** {count}",
        inline=False,
    )
    try:
        await member.send(embed=embed)
    except Exception:
        pass


async def add_warn(member: discord.Member, reason: str) -> int:
    user_id = str(member.id)
    if user_id not in warns_db:
        warns_db[user_id] = {"count": 0, "reasons": [], "dates": []}
    warns_db[user_id]["count"] += 1
    warns_db[user_id]["reasons"].append(reason)
    warns_db[user_id]["dates"].append(datetime.now().strftime("%Y-%m-%d %H:%M"))
    count = warns_db[user_id]["count"]
    await send_warn_dm(member, count, reason)
    return count


# ─── بانل الصلاحيات ───

class PermsSelect(discord.ui.Select):
    def __init__(self, command_name: str):
        self.command_name = command_name
        options = [
            discord.SelectOption(label="Owner فقط", value="owner"),
            discord.SelectOption(label="Admins + Mods", value="staff"),
            discord.SelectOption(label="الكل", value="all"),
        ]
        super().__init__(
            placeholder=f"صلاحيات: {DISPLAY_NAMES.get(command_name, command_name)}",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"perms_select_{command_name}",
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            await interaction.response.send_message(
                "❌ هاد البانل خاص فقط بالـ Owner.", ephemeral=True
            )
            return

        choice = self.values[0]
        cfg = COMMAND_ROLES.setdefault(self.command_name, {})

        if choice == "owner":
            cfg["owner_only"] = True
            cfg["allowed_roles"] = []
            text = "⛔ الأمر دابا Owner فقط."
        elif choice == "staff":
            cfg["owner_only"] = False
            cfg["allowed_roles"] = EXEMPT_ROLE_IDS[:]
            text = "🛡️ الأمر دابا مسموح غير لـ Admins + Mods (+ Owner)."
        else:
            cfg["owner_only"] = False
            cfg["allowed_roles"] = []
            text = "✅ الأمر دابا كيخضع لصلاحيات Discord العادية فقط."

        await interaction.response.send_message(
            f"تم تحديث صلاحيات الأمر **{DISPLAY_NAMES.get(self.command_name, self.command_name)}**.\n{text}",
            ephemeral=True,
        )


class PermsPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        for cmd in COMMAND_ROLES.keys():
            self.add_item(PermsSelect(cmd))


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.mute_tasks = {}  # {user_id: asyncio.Task}

    # ───── بانل الصلاحيات ─────

    @commands.hybrid_command(
        name="permspanel",
        description="لوحة تحكم فصلاحيات أوامر الموديريشن (Owner فقط)",
    )
    async def permspanel(self, ctx: commands.Context):
        if ctx.author.id != OWNER_ID:
            await ctx.send("❌ هاد البانل خاص فقط بالـ Owner.", delete_after=6)
            return

        embed = discord.Embed(
            title="🔧 صلاحيات أوامر الموديريشن",
            description=(
                "اختار لكل أمر شكون يقدر يستعملو:\n"
                "- Owner فقط\n"
                "- Admins + Mods\n"
                "- أو الكل (حسب صلاحيات Discord)\n\n"
                "التغييرات كتطبق فوراً على /kick /ban /mute /clear /warn ..."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(),
        )
        embed.set_footer(text=f"{SERVER_NAME} | Moderation Perms")
        await ctx.send(embed=embed, view=PermsPanelView())

    # ───── Helpers ─────

    async def auto_unmute(self, member: discord.Member, duration_minutes: int):
        await asyncio.sleep(duration_minutes * 60)
        muted_role = member.guild.get_role(MUTED_ROLE_ID)
        if muted_role and muted_role in member.roles:
            try:
                await member.remove_roles(muted_role)
            except Exception:
                pass

    # ───── kick ─────

    @commands.hybrid_command(description="اطرد عضو من السيرفر")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "ما ذكرش سبب"):
        if not has_custom_command_access(ctx.author, ctx.command.name):
            await ctx.send("❌ هاد الأمر مقيد من طرف Owner.", delete_after=6)
            return

        if OWNER_ID and member.id == OWNER_ID:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
            return
        if is_exempt(member):
            await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
            return

        try:
            await member.kick(reason=reason)
            embed = discord.Embed(
                title="👢 طرد",
                description=f"**{member.mention}** تم طرده.",
                color=COLOR_KICK,
                timestamp=datetime.now()
            )
            embed.add_field(name="السبب", value=reason, inline=False)
            embed.add_field(name="الطارد", value=ctx.author.mention, inline=False)
            embed.set_footer(text=f"{SERVER_NAME} | Moderation")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ خطأ: {str(e)}", delete_after=5)

    # ───── ban / unban ─────

    @commands.hybrid_command(description="احظر عضو من السيرفر")
    @app_commands.default_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "ما ذكرش سبب"):
        if not has_custom_command_access(ctx.author, ctx.command.name):
            await ctx.send("❌ هاد الأمر مقيد من طرف Owner.", delete_after=6)
            return

        if OWNER_ID and member.id == OWNER_ID:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
            return
        if is_exempt(member):
            await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
            return

        try:
            await member.ban(reason=reason)
            embed = discord.Embed(
                title="🚫 حظر",
                description=f"**{member.mention}** تم حظره.",
                color=COLOR_BAN,
                timestamp=datetime.now()
            )
            embed.add_field(name="السبب", value=reason, inline=False)
            embed.add_field(name="الحاظر", value=ctx.author.mention, inline=False)
            embed.set_footer(text=f"{SERVER_NAME} | Moderation")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ خطأ: {str(e)}", delete_after=5)

    @commands.hybrid_command(description="فك الحظر على عضو (بالـ User ID)")
    @app_commands.default_permissions(ban_members=True)
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: int):
        if not has_custom_command_access(ctx.author, ctx.command.name):
            await ctx.send("❌ هاد الأمر مقيد من طرف Owner.", delete_after=6)
            return

        try:
            user = await self.bot.fetch_user(user_id)
            await ctx.guild.unban(user)
            embed = discord.Embed(
                title="✅ فك الحظر",
                description=f"**{user.name}** تم فك حظره.",
                color=COLOR_UNBAN,
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"{SERVER_NAME} | Moderation")
            await ctx.send(embed=embed)
        except discord.NotFound:
            await ctx.send("❌ ما لقيتش هاد العضو!", delete_after=5)
        except discord.Forbidden:
            await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)
        except Exception as e:
            await ctx.send(f"❌ خطأ: {str(e)}", delete_after=5)

    # ───── clear ─────

    @commands.hybrid_command(description="امسح عدد من الرسائل فالشانيل")
    @app_commands.default_permissions(manage_messages=True)
    @commands.has_permissions(manage_messages=True)
    async def clear(self, ctx: commands.Context, amount: int = 10):
        if not has_custom_command_access(ctx.author, ctx.command.name):
            await ctx.send("❌ هاد الأمر مقيد من طرف Owner.", delete_after=6)
            return

        if amount < 1 or amount > 100:
            await ctx.send("❌ خاص العدد يكون بين 1 و 100!", delete_after=5)
            return

        try:
            deleted = await ctx.channel.purge(limit=amount + 1)
            msg = await ctx.send(f"🗑️ تم حذف {len(deleted) - 1} رسالة")
            await asyncio.sleep(3)
            await msg.delete()
        except discord.Forbidden:
            await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)

    # ───── mute / unmute ─────

    @commands.hybrid_command(description="كتم عضو (Role) لمدة معيّنة (دقايق)")
    @app_commands.default_permissions(moderate_members=True)
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: int = 5, *, reason: str = "ما ذكرش سبب"):
        if not has_custom_command_access(ctx.author, ctx.command.name):
            await ctx.send("❌ هاد الأمر مقيد من طرف Owner.", delete_after=6)
            return

        if OWNER_ID and member.id == OWNER_ID:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
            return
        if is_exempt(member):
            await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
            return

        muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
        if not muted_role:
            await ctx.send("❌ ما لقيتش دور Mute! حط ID صحيح فـ MUTED_ROLE_ID.", delete_after=5)
            return

        try:
            await member.add_roles(muted_role)
            user_id = str(member.id)
            if user_id in self.mute_tasks and not self.mute_tasks[user_id].done():
                self.mute_tasks[user_id].cancel()
            task = asyncio.create_task(self.auto_unmute(member, duration))
            self.mute_tasks[user_id] = task

            embed = discord.Embed(
                title="🔇 كتم",
                description=f"**{member.mention}** تم كتم صوته.",
                color=COLOR_MUTE,
                timestamp=datetime.now()
            )
            embed.add_field(name="المدة", value=f"{duration} دقيقة", inline=False)
            embed.add_field(name="السبب", value=reason, inline=False)
            embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
            embed.set_footer(text=f"{SERVER_NAME} | Moderation")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)

    @commands.hybrid_command(description="فك الكتم على عضو")
    @app_commands.default_permissions(moderate_members=True)
    @commands.has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        if not has_custom_command_access(ctx.author, ctx.command.name):
            await ctx.send("❌ هاد الأمر مقيد من طرف Owner.", delete_after=6)
            return

        muted_role = ctx.guild.get_role(MUTED_ROLE_ID)
        if not muted_role:
            await ctx.send("❌ ما لقيتش دور Mute!", delete_after=5)
            return

        try:
            await member.remove_roles(muted_role)
            user_id = str(member.id)
            if user_id in self.mute_tasks and not self.mute_tasks[user_id].done():
                self.mute_tasks[user_id].cancel()

            embed = discord.Embed(
                title="🔊 فك الكتم",
                description=f"**{member.mention}** تم فك الكتم.",
                color=COLOR_UNMUTE,
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"{SERVER_NAME} | Moderation")
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("❌ ما عنديش الصلاحية!", delete_after=5)

    # ───── warn / warns / unwarn ─────

    @commands.hybrid_command(description="أعطي تحذير لعضو")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        if not has_custom_command_access(ctx.author, ctx.command.name):
            await ctx.send("❌ هاد الأمر مقيد من طرف Owner.", delete_after=6)
            return

        if OWNER_ID and member.id == OWNER_ID:
            await ctx.send("❌ ما نقدرش نمس فـ Owner ديال السيرفر!")
            return
        if is_exempt(member):
            await ctx.send("❌ هاد العضو معفي من Auto-Mod/Moderation (Admin/Mod)!")
            return

        count = await add_warn(member, reason)

        embed = discord.Embed(
            title="⚠️ تحذير",
            description=f"**{member.mention}** تم تحذيره.",
            color=COLOR_WARN,
            timestamp=datetime.now()
        )
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="عدد التحذيرات", value=f"{count}", inline=False)
        embed.add_field(name="المنفذ", value=ctx.author.mention, inline=False)
        embed.set_footer(text=f"{SERVER_NAME} | Moderation")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="بين التحذيرات ديال عضو")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def warns(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        if not has_custom_command_access(ctx.author, ctx.command.name):
            await ctx.send("❌ هاد الأمر مقيد من طرف Owner.", delete_after=6)
            return

        member = member or ctx.author
        user_warns = get_warns(str(member.id))

        embed = discord.Embed(
            title=f"⚠️ تحذيرات {member.display_name}",
            color=COLOR_WARN,
            timestamp=datetime.now()
        )
        embed.add_field(name="العدد", value=str(user_warns["count"]), inline=False)

        if user_warns["reasons"]:
            reasons_text = "\n".join(
                f"{i+1}. {r} ({user_warns['dates'][i]})"
                for i, r in enumerate(user_warns["reasons"])
            )
            embed.add_field(name="الأسباب والتواريخ", value=reasons_text, inline=False)
        else:
            embed.add_field(name="الأسباب", value="ما كاين والو ✅", inline=False)

        embed.set_footer(text=f"{SERVER_NAME} | Moderation")
        await ctx.send(embed=embed)

    @commands.hybrid_command(description="حيد التحذيرات من عضو")
    @app_commands.default_permissions(kick_members=True)
    @commands.has_permissions(kick_members=True)
    async def unwarn(self, ctx: commands.Context, member: discord.Member):
        if not has_custom_command_access(ctx.author, ctx.command.name):
            await ctx.send("❌ هاد الأمر مقيد من طرف Owner.", delete_after=6)
            return

        clear_warns(str(member.id))
        embed = discord.Embed(
            title="✅ مسح التحذيرات",
            description=f"**{member.mention}** تم مسح تحذيراتو.",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"{SERVER_NAME} | Moderation")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
    print("✅ [Moderation] Cog محمّل بنجاح")
