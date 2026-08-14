# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║  cogs/channel_lockdown.py — 🛡️ قفل صلاحيات الشانيلز   ║
═══════════════════════════════════════════════════════

الهدف:
  • **حتى عضو عادي ما يقدر يبدّل والو** فحتى روم / شانيل / كاتيكوري.
  • الحقوق الإدارية كتبقا غير لـ **Admin** و **Moderator**.
  • ولكن حتى هوما **ماعندهمش الحق** فالمناطق المحمية:
        🔒 PRISON      — الاونر بوحدو
        🎧 TEMP ROOMS  — صاحب الروم بوحدو
        🌑 UNDERGROUND — الاونر بوحدو
        🔐 OWNER PANEL — الاونر بوحدو
  • رولات بحال Boys / Girls / Member = **أعضاء عاديين**، ماعندهم حتى سلطة.

طبقتين ديال الحماية:
  1️⃣ **صلاحيات الرول نفسو** (Guild level) — كنحيدو البيتات الخطيرة من أي
     رول ماشي Admin/Moderator/Bot.
  2️⃣ **الـ Overwrites ديال الشانيلز** — إلا شي حد عطى صلاحية خطيرة لرول
     ولا لعضو فشي روم، كتتحيد.

كيتصلّح أوتوماتيكيا: on_ready، أي روم جديدة، وأي تعديل يدوي.
الاونر بوحدو لي كيتحكم فيه من البانل ديالو.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Iterable, Optional

import discord
from discord.ext import commands

REASON_TAG = "GGMW9 Channel Lockdown"

# ═══════════════════════════════════════════════════════
# ║   الصلاحيات الخطيرة اللي خاص العضو العادي ما يكونش عندو   ║
# ═══════════════════════════════════════════════════════

# على مستوى الرول (Guild permissions)
DANGEROUS_GUILD_PERMS = (
    "administrator",
    "manage_guild",
    "manage_roles",
    "manage_channels",
    "manage_webhooks",
    "manage_messages",
    "manage_threads",
    "manage_nicknames",
    "manage_events",
    "manage_expressions",
    "manage_emojis_and_stickers",
    "moderate_members",
    "kick_members",
    "ban_members",
    "view_audit_log",
    "mention_everyone",
    "move_members",
    "mute_members",
    "deafen_members",
)

# على مستوى الشانيل (Overwrites)
DANGEROUS_CHANNEL_PERMS = (
    "manage_channels",
    "manage_permissions",
    "manage_roles",
    "manage_messages",
    "manage_threads",
    "manage_webhooks",
    "mention_everyone",
    "create_public_threads",
    "create_private_threads",
    "move_members",
    "mute_members",
    "deafen_members",
    "priority_speaker",
)

# هادو كيتخلاو للأعضاء (ماشي خطيرين)
SAFE_MEMBER_PERMS = (
    "view_channel",
    "read_messages",
    "read_message_history",
    "send_messages",
    "embed_links",
    "attach_files",
    "add_reactions",
    "use_external_emojis",
    "connect",
    "speak",
    "stream",
    "use_voice_activation",
)

# ═══════════════════════════════════════════════════════
# ║   ⚠️  الصلاحيات الممنوحة للستاف بدل Administrator      ║
# ═══════════════════════════════════════════════════════
#
# `Administrator` كيتجاوز **كاع** الـoverwrites ديال الشانيلز.
# يعني إلا كان رول Admin عندو Administrator، غادي يشوف السجن و
# Temp Rooms و Underground حتى إلا دنينا عليهم صراحة — والنظام كامل
# كيولي ديكور.
#
# الحل الاحترافي: كنحيدو `Administrator` وكنعوضوه بالصلاحيات المفصّلة
# اللي كيحتاجها الستاف فعلاً. النتيجة: نفس القوة برا المناطق المحمية،
# وصفر قوة داخلها.
ADMIN_GRANTED_PERMS = (
    "manage_channels",
    "manage_roles",
    "manage_messages",
    "manage_threads",
    "manage_webhooks",
    "manage_nicknames",
    "manage_events",
    "kick_members",
    "ban_members",
    "moderate_members",
    "view_audit_log",
    "mute_members",
    "deafen_members",
    "move_members",
    "mention_everyone",
    "manage_expressions",
    "manage_emojis_and_stickers",
)

MODERATOR_GRANTED_PERMS = (
    "manage_messages",
    "manage_threads",
    "manage_nicknames",
    "kick_members",
    "moderate_members",
    "mute_members",
    "deafen_members",
    "move_members",
)


class ChannelLockdown(commands.Cog):
    """كيفرض سياسة صلاحيات موحدة على كاع السيرفر."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bridge = getattr(bot, "gg", {}) or {}
        self.admin_role_id = int(bridge.get("ADMIN_ROLE_ID") or 0)
        self.moderator_role_id = int(bridge.get("MODERATOR_ROLE_ID") or 0)
        self.owner_control_channel_id = int(bridge.get("OWNER_CONTROL_CHANNEL_ID") or 0)
        self.join_to_create_id = int(bridge.get("JOIN_TO_CREATE_CHANNEL_ID") or 0)
        self.temp_vc_category_id = int(bridge.get("TEMP_VC_CATEGORY_ID") or 0)
        self.mod_logs_channel_id = int(bridge.get("MOD_LOGS_CHANNEL_ID") or 0)

        self._locks: dict[int, asyncio.Lock] = {}
        self._ready_done = False

    # ═══════════════════════════════════════════════════
    # ║                  أدوات                            ║
    # ═══════════════════════════════════════════════════

    def _lock(self, guild_id: int) -> asyncio.Lock:
        lock = self._locks.get(guild_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[guild_id] = lock
        return lock

    def staff_role_ids(self, guild: discord.Guild) -> set[int]:
        """الرولات اللي عندها الحق تدير إدارة (برا المناطق المحمية)."""
        return {rid for rid in (self.admin_role_id, self.moderator_role_id) if rid}

    def is_staff_role(self, role: discord.Role) -> bool:
        if role.managed:  # رولات البوتات و Nitro Booster — ما كنمسوهاش
            return True
        if role.is_default():
            return False
        return role.id in self.staff_role_ids(role.guild)

    # ───── المناطق المحمية ─────

    def protected_channel_ids(self, guild: discord.Guild) -> set[int]:
        """
        رومز/كاتيكوريز اللي **حتى الادمين والمود ماعندهمش فيهم الحق**.
        هنا كنقراو الـIDs من الأنظمة الحية، ماشي من قيم مكتوبة.
        """
        ids: set[int] = set()

        # 🔒 السجن
        prison = self.bot.get_cog("PrisonSystem")
        if prison is not None:
            try:
                ids |= prison.prison_channel_ids(guild)
            except Exception:
                pass

        # 🔐 بانل الاونر
        if self.owner_control_channel_id:
            ids.add(self.owner_control_channel_id)

        # 🎧 الرومات المؤقتة
        if self.join_to_create_id:
            ids.add(self.join_to_create_id)
        if self.temp_vc_category_id:
            ids.add(self.temp_vc_category_id)
        bridge = getattr(self.bot, "gg", {}) or {}
        temp_channels = bridge.get("temp_voice_channels")
        if isinstance(temp_channels, dict):
            for key in temp_channels:
                try:
                    ids.add(int(key))
                except (TypeError, ValueError):
                    continue

        # 🌑 Underground ديال المدينة
        city = self.bot.get_cog("CareerCity")
        if city is not None:
            for attr in ("underground_channel_ids", "_underground_channel_ids"):
                getter = getattr(city, attr, None)
                try:
                    values = getter(guild) if callable(getter) else getter
                    if values:
                        ids |= {int(v) for v in values}
                except Exception:
                    continue

        ids.discard(0)
        return ids

    def is_protected(self, channel: discord.abc.GuildChannel) -> bool:
        protected = self.protected_channel_ids(channel.guild)
        if channel.id in protected:
            return True
        parent = getattr(channel, "category_id", None)
        return bool(parent and parent in protected)

    async def _log(self, guild: discord.Guild, embed: discord.Embed) -> None:
        """
        🕵️ Owner stealth: التنبيهات كتمشي **غير** لقناة بانل الاونر المخفية.
        ما كيمشي حتى شي حاجة لـ Mod-Logs — الادمين والمود ما كيشوفوش.
        """
        if not self.owner_control_channel_id:
            return
        channel = guild.get_channel(self.owner_control_channel_id)
        if channel is None:
            return
        try:
            await channel.send(embed=embed)
        except (discord.Forbidden, discord.HTTPException):
            pass

    # ═══════════════════════════════════════════════════
    # ║      الطبقة 1: صلاحيات الرولات (Guild level)      ║
    # ═══════════════════════════════════════════════════

    async def harden_roles(self, guild: discord.Guild) -> list[str]:
        """
        كتحيد الصلاحيات الخطيرة من الرولات.

        • رول عادي  → كتتحيد منو كاع الصلاحيات الخطيرة
        • رول ستاف   → كيتحيد منو **Administrator بوحدو** وكيتعوض
                       بالصلاحيات المفصّلة (باش الـoverwrites تخدم عليه)
        • رول بوت    → ما كيتمسش (managed)
        """
        fixed: list[str] = []
        me = guild.me
        if me is None:
            return fixed
        top = me.top_role.position
        staff_ids = self.staff_role_ids(guild)

        for role in list(guild.roles):
            if role.managed:  # رولات البوتات و Booster
                continue
            if role.position >= top and not role.is_default():
                continue  # البوت ما يقدرش يمسو

            permissions = discord.Permissions(role.permissions.value)
            stripped: list[str] = []

            if role.id in staff_ids:
                # ── ستاف: نحيدو Administrator ونعوضوه ──
                if not permissions.administrator:
                    continue
                permissions.administrator = False
                stripped.append("administrator")

                granted = (
                    ADMIN_GRANTED_PERMS
                    if role.id == self.admin_role_id
                    else MODERATOR_GRANTED_PERMS
                )
                for name in granted:
                    if hasattr(permissions, name):
                        setattr(permissions, name, True)
                note = f"@{role.name} → تحيد Administrator، تعوض بـ {len(granted)} صلاحية مفصّلة"
            else:
                # ── عضو عادي: نحيدو كلشي خطير ──
                for name in DANGEROUS_GUILD_PERMS:
                    if not hasattr(permissions, name):
                        continue
                    if getattr(permissions, name):
                        setattr(permissions, name, False)
                        stripped.append(name)
                if not stripped:
                    continue
                note = f"@{role.name} → {', '.join(stripped)}"

            try:
                await role.edit(
                    permissions=permissions,
                    reason=f"{REASON_TAG}: enforce permission policy",
                )
                fixed.append(note)
                await asyncio.sleep(0.4)
            except (discord.Forbidden, discord.HTTPException) as exc:
                print(f"[LOCKDOWN] ⚠️ رول {role.name}: {exc}")
        return fixed

    def administrator_bypass_report(self, guild: discord.Guild) -> list[str]:
        """
        ⚠️ أي رول باقي عندو Administrator = **كيكسر السجن كامل**.
        كيشوف كاع الرومز حتى إلا دنينا عليه. هاد التقرير كيوريهم للاونر.
        """
        offenders: list[str] = []
        for role in guild.roles:
            if not role.permissions.administrator or role.is_default():
                continue
            if role.managed:
                members = [m.name for m in role.members if m.bot]
                offenders.append(f"🤖 @{role.name} (بوت: {', '.join(members[:3]) or '—'})")
            else:
                offenders.append(f"👤 @{role.name} ({len(role.members)} عضو)")
        return offenders

    # ═══════════════════════════════════════════════════
    # ║      الطبقة 2: Overwrites ديال كل شانيل           ║
    # ═══════════════════════════════════════════════════

    @staticmethod
    def _clean_overwrite(
        overwrite: discord.PermissionOverwrite, *, force_deny: bool
    ) -> tuple[discord.PermissionOverwrite, list[str]]:
        """
        كتنقّي overwrite من الصلاحيات الخطيرة.
        force_deny=True → كتحطها False صراحة (للـ@everyone).
        force_deny=False → كتحطها None (كترجع للوراثة).
        """
        changed: list[str] = []
        cleaned = discord.PermissionOverwrite(**{
            key: value for key, value in overwrite  # noqa
            if value is not None
        })
        for name in DANGEROUS_CHANNEL_PERMS:
            if not hasattr(cleaned, name):
                continue
            current = getattr(cleaned, name)
            if current is True:
                setattr(cleaned, name, False if force_deny else None)
                changed.append(name)
            elif force_deny and current is None and name in (
                "manage_channels",
                "manage_permissions",
                "manage_messages",
                "manage_threads",
                "manage_webhooks",
                "mention_everyone",
            ):
                setattr(cleaned, name, False)
                changed.append(name)
        return cleaned, changed

    async def harden_channel(self, channel: discord.abc.GuildChannel) -> list[str]:
        """كتفرض السياسة على شانيل وحدة. كترجع لائحة التغييرات."""
        guild = channel.guild
        changes: list[str] = []
        staff_ids = self.staff_role_ids(guild)
        protected = self.is_protected(channel)

        for target, overwrite in list(channel.overwrites.items()):
            # البوتات والاونر ما كنمسوهمش
            if isinstance(target, discord.Member):
                if target.bot or target.id == guild.owner_id:
                    continue
            if isinstance(target, discord.Role):
                if target.managed:
                    continue
                # الادمين/المود عندهم الحق — إلا فالمناطق المحمية
                if target.id in staff_ids and not protected:
                    continue

            is_everyone = isinstance(target, discord.Role) and target.is_default()
            cleaned, changed = self._clean_overwrite(overwrite, force_deny=is_everyone)
            if not changed:
                continue
            try:
                await channel.set_permissions(
                    target,
                    overwrite=cleaned,
                    reason=f"{REASON_TAG}: enforce permission policy",
                )
                label = getattr(target, "name", str(target))
                changes.append(f"{channel.name} / {label}: {', '.join(changed)}")
                await asyncio.sleep(0.3)
            except (discord.Forbidden, discord.HTTPException, discord.NotFound) as exc:
                print(f"[LOCKDOWN] ⚠️ {channel.name}: {exc}")
        return changes

    async def harden_guild(self, guild: discord.Guild) -> dict:
        """المسح الكامل: الرولات + كاع الشانيلز."""
        async with self._lock(guild.id):
            roles_fixed = await self.harden_roles(guild)

            channel_changes: list[str] = []
            ordered = sorted(
                guild.channels,
                key=lambda c: (
                    0 if isinstance(c, discord.CategoryChannel) else 1,
                    int(getattr(c, "position", 0)),
                ),
            )
            for channel in ordered:
                channel_changes.extend(await self.harden_channel(channel))

            bypass = self.administrator_bypass_report(guild)
            result = {
                "roles": roles_fixed,
                "channels": channel_changes,
                "scanned": len(guild.channels),
                "protected": len(self.protected_channel_ids(guild)),
                "admin_bypass": bypass,
            }
            if bypass:
                print(f"[LOCKDOWN] ⚠️ {guild.name}: رولات باقي عندها Administrator: {bypass}")
            print(
                f"[LOCKDOWN] 🛡️ {guild.name}: {len(roles_fixed)} رول، "
                f"{len(channel_changes)} overwrite تصلحو، {result['scanned']} شانيل تفحصو."
            )
            return result

    # ═══════════════════════════════════════════════════
    # ║                   الأحداث                         ║
    # ═══════════════════════════════════════════════════

    @commands.Cog.listener()
    async def on_ready(self):
        if self._ready_done:
            return
        self._ready_done = True
        await asyncio.sleep(12)  # نخليو السجن يكمل الـsetup الأول
        for guild in self.bot.guilds:
            try:
                await self.harden_guild(guild)
            except Exception as exc:
                print(f"[LOCKDOWN] ❌ {guild.id}: {type(exc).__name__}: {exc}")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        await asyncio.sleep(1.5)  # نخليو الأنظمة الأخرى تسجل الروم الأول
        try:
            await self.harden_channel(channel)
        except Exception as exc:
            print(f"[LOCKDOWN] ❌ channel_create: {type(exc).__name__}: {exc}")

    @commands.Cog.listener()
    async def on_guild_channel_update(
        self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel
    ):
        if before.overwrites == after.overwrites:
            return
        try:
            changes = await self.harden_channel(after)
            if changes:
                embed = discord.Embed(
                    title="🛡️ Lockdown — تصحيح صلاحيات",
                    description=(
                        f"**الشانيل:** {after.mention if hasattr(after, 'mention') else after.name}\n"
                        f"شي حد عطى صلاحيات خطيرة — البوت رجّعها."
                    ),
                    color=discord.Color.orange(),
                    timestamp=datetime.now(),
                )
                embed.add_field(
                    name="التغييرات", value="\n".join(changes)[:1024], inline=False
                )
                await self._log(after.guild, embed)
        except Exception as exc:
            print(f"[LOCKDOWN] ❌ channel_update: {type(exc).__name__}: {exc}")

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        if before.permissions == after.permissions:
            return
        if self.is_staff_role(after):
            return
        try:
            fixed = await self.harden_roles(after.guild)
            if fixed:
                embed = discord.Embed(
                    title="🛡️ Lockdown — رول تعدّل",
                    description=f"**الرول:** {after.mention}\nتحيدو منو صلاحيات خطيرة.",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(),
                )
                embed.add_field(name="التفاصيل", value="\n".join(fixed)[:1024], inline=False)
                await self._log(after.guild, embed)
        except Exception as exc:
            print(f"[LOCKDOWN] ❌ role_update: {type(exc).__name__}: {exc}")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        if self.is_staff_role(role):
            return
        try:
            await self.harden_roles(role.guild)
        except Exception as exc:
            print(f"[LOCKDOWN] ❌ role_create: {type(exc).__name__}: {exc}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelLockdown(bot))
    print("✅ Channel Lockdown: صلاحيات الشانيلز مقفلة — غير Admin/Mod")
