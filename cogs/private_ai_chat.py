# -*- coding: utf-8 -*-
"""Private, temporary AI conversations rooted in the configured AI channel."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Optional

import discord
from discord.ext import commands, tasks


SESSION_PREFIX = "ai-private-"
REASON_TAG = "GGMW9 Private AI"
PANEL_MARKER = "GGMW9:PRIVATE_AI_HOME"


class AIQuestionModal(discord.ui.Modal, title="🤖 سؤال خاص للـAI"):
    def __init__(self):
        super().__init__(timeout=300)
        self.question = discord.ui.TextInput(
            label="شنو بغيتي تسول؟",
            placeholder="كتب سؤالك هنا… غادي يبان غير فالمحادثة الخاصة ديالك.",
            style=discord.TextStyle.paragraph,
            required=True,
            min_length=1,
            max_length=2500,
        )
        self.add_item(self.question)

    async def on_submit(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("PrivateAIChat")
        if (
            cog is None
            or interaction.guild is None
            or not isinstance(interaction.user, discord.Member)
        ):
            await interaction.response.send_message(
                "❌ المحادثة الخاصة ماشي متاحة دابا.", ephemeral=True
            )
            return

        parent = interaction.guild.get_channel(cog.parent_channel_id)
        if not isinstance(parent, discord.TextChannel):
            await interaction.response.send_message(
                "❌ شانيل الـAI ما بقاتش موجودة.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        thread = await cog._ensure_session(parent, interaction.user)
        if thread is None:
            await interaction.followup.send(
                "❌ ما قدرتش نفتح المحادثة. تأكد أن البوت عندو Manage Threads.",
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            f"🔒 المحادثة الخاصة ديالك تحلات هنا: {thread.mention}",
            ephemeral=True,
        )
        await cog._answer(
            thread,
            interaction.user,
            str(self.question.value),
            copy_prompt=True,
        )


class AIHomeView(discord.ui.View):
    """المدخل الوحيد المضمون باش السؤال ما يبانش فالشانيل العامة."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="ابدأ محادثة خاصة",
        emoji="🤖",
        style=discord.ButtonStyle.primary,
        custom_id="ggmw9:private-ai:start",
    )
    async def start_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AIQuestionModal())


class PrivateAIChat(commands.Cog):
    """One private thread and one isolated memory per Discord user ID."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bridge = getattr(bot, "gg", {}) or {}
        self.parent_channel_id = int(bridge.get("TARGET_CHANNEL_ID") or 0)
        self.cooldown_seconds = max(0, int(bridge.get("AI_USER_COOLDOWN_SECONDS") or 0))
        self.idle_seconds = max(
            60,
            int(bridge.get("AI_PRIVATE_THREAD_IDLE_SECONDS") or 15 * 60),
        )
        self.max_reply_length = max(200, int(bridge.get("MAX_REPLY_LENGTH") or 1800))
        self.ask_ai = bridge.get("ask_ai")
        self.user_memory = bridge.get("user_memory")
        self.staff_role_ids = {
            int(role_id)
            for role_id in (
                bridge.get("ADMIN_ROLE_ID"),
                bridge.get("MODERATOR_ROLE_ID"),
            )
            if int(role_id or 0)
        }
        self.participant_role_ids = {
            int(role_id)
            for role_id in (
                bridge.get("MEMBER_ROLE_ID"),
                bridge.get("BOYS_ROLE_ID"),
                bridge.get("GIRLS_ROLE_ID"),
            )
            if int(role_id or 0)
        }

        self._user_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self._last_request: dict[tuple[int, int], float] = {}
        self._last_activity: dict[int, float] = {}
        self._archived_cleanup_done: set[int] = set()
        self._panel_message_id = 0
        self._parent_sync_lock = asyncio.Lock()
        self.cleanup_loop.start()

    @staticmethod
    def _session_name(user_id: int) -> str:
        return f"{SESSION_PREFIX}{int(user_id)}"

    def _session_owner_id(self, thread: discord.Thread) -> Optional[int]:
        if int(getattr(thread, "parent_id", 0) or 0) != self.parent_channel_id:
            return None
        match = re.fullmatch(rf"{re.escape(SESSION_PREFIX)}(\d{{15,22}})", str(thread.name))
        return int(match.group(1)) if match else None

    def is_session_thread(self, channel) -> bool:
        return isinstance(channel, discord.Thread) and self._session_owner_id(channel) is not None

    def _lock(self, guild_id: int, user_id: int) -> asyncio.Lock:
        key = (int(guild_id), int(user_id))
        lock = self._user_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._user_locks[key] = lock
        return lock

    def _touch(self, thread: discord.Thread) -> None:
        self._last_activity[int(thread.id)] = time.time()

    def _forget_user(self, guild_id: int, user_id: int, thread_id: int = 0) -> None:
        key = (int(guild_id), int(user_id))
        self._last_request.pop(key, None)
        self._user_locks.pop(key, None)
        if thread_id:
            self._last_activity.pop(int(thread_id), None)
        if isinstance(self.user_memory, dict):
            self.user_memory.pop(str(int(user_id)), None)

    @staticmethod
    def _thread_last_activity(thread: discord.Thread) -> float:
        if thread.last_message_id:
            return discord.utils.snowflake_time(thread.last_message_id).timestamp()
        if thread.created_at:
            return thread.created_at.timestamp()
        return time.time()

    async def _delete_source_message(self, message: discord.Message) -> None:
        try:
            await message.delete()
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    @staticmethod
    def _panel_embed() -> discord.Embed:
        embed = discord.Embed(
            title="🤖 المساعد الذكي — محادثة خاصة",
            description=(
                "ضغط على الزر لتحت وكتب سؤالك فالخانة الخاصة.\n\n"
                "🔒 السؤال ديالك ما كيتنشرش فهاد الشانيل.\n"
                "🧵 البوت كيفتح ليك Private Thread مربوطة بالـDiscord ID ديالك.\n"
                "🌐 كيستعمل الإنترنت أوتوماتيكياً غير ملي السؤال محتاج معلومات حديثة.\n"
                "💬 كمل الحوار داخل الـThread، وكل مستخدم عندو ذاكرة مستقلة.\n"
                "🧹 المحادثة والذاكرة كيتمسحو أوتوماتيكياً من بعد 15 دقيقة بلا نشاط."
            ),
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name="طريقة الاستعمال",
            value="**1.** ضغط على «ابدأ محادثة خاصة»\n**2.** كتب السؤال\n**3.** دخل للـThread وكمل الحوار",
            inline=False,
        )
        embed.set_footer(text=f"{PANEL_MARKER} • غير البانل الرسمية كتبقى فهاد الشانيل")
        return embed

    @staticmethod
    def _is_home_panel(message: discord.Message) -> bool:
        return bool(
            message.embeds
            and message.embeds[0].footer
            and PANEL_MARKER in str(message.embeds[0].footer.text or "")
        )

    async def _enforce_parent_privacy(self, parent: discord.TextChannel) -> None:
        """الشانيل بانل فقط، لكن أعضاء الـPrivate Thread يقدرو يكتبو بلا Read-only."""
        guild = parent.guild
        role_targets: list[discord.Role] = [guild.default_role]
        for role in guild.roles:
            if role == guild.default_role or role.managed:
                continue
            current = parent.overwrites_for(role)
            if (
                role.id in self.staff_role_ids
                or role.id in self.participant_role_ids
                or current.send_messages is True
                or current.send_messages_in_threads is False
                or current.create_private_threads is True
                or current.create_public_threads is True
            ):
                role_targets.append(role)

        for role in role_targets:
            overwrite = parent.overwrites_for(role)
            desired = {
                "view_channel": True,
                "read_message_history": True,
                "send_messages": False,
                "send_messages_in_threads": True,
                "create_public_threads": False,
                "create_private_threads": False,
                "add_reactions": False,
            }
            if role.id in self.staff_role_ids:
                desired["manage_threads"] = False
            if all(getattr(overwrite, key) is value for key, value in desired.items()):
                continue
            for key, value in desired.items():
                setattr(overwrite, key, value)
            try:
                await parent.set_permissions(
                    role,
                    overwrite=overwrite,
                    reason=f"{REASON_TAG}: private-thread access and clean parent",
                )
            except (discord.Forbidden, discord.HTTPException):
                continue

        me = guild.me
        if me is not None:
            overwrite = parent.overwrites_for(me)
            desired = {
                "view_channel": True,
                "read_message_history": True,
                "send_messages": True,
                "send_messages_in_threads": True,
                "create_private_threads": True,
                "manage_threads": True,
                "manage_messages": True,
            }
            if not all(getattr(overwrite, key) is value for key, value in desired.items()):
                for key, value in desired.items():
                    setattr(overwrite, key, value)
                try:
                    await parent.set_permissions(
                        me,
                        overwrite=overwrite,
                        reason=f"{REASON_TAG}: bot thread permissions",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    pass

    async def _sync_parent_panel(self, parent: discord.TextChannel) -> None:
        """كيصفر الشانيل وكيبقي رسالة تعليمية رسمية واحدة فقط."""
        async with self._parent_sync_lock:
            await self._enforce_parent_privacy(parent)
            panel = None
            try:
                async for message in parent.history(limit=None, oldest_first=False):
                    if panel is None and self._is_home_panel(message):
                        panel = message
                        continue
                    await self._delete_source_message(message)
            except (discord.Forbidden, discord.HTTPException):
                pass

            if panel is not None:
                try:
                    await panel.edit(embed=self._panel_embed(), view=AIHomeView(), content=None)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    panel = None
            if panel is None:
                try:
                    panel = await parent.send(embed=self._panel_embed(), view=AIHomeView())
                except (discord.Forbidden, discord.HTTPException):
                    return
            self._panel_message_id = int(panel.id)
            try:
                await panel.pin(reason=f"{REASON_TAG}: official instructions")
            except (discord.Forbidden, discord.HTTPException):
                pass

    async def _find_active_session(
        self,
        parent: discord.TextChannel,
        user_id: int,
    ) -> Optional[discord.Thread]:
        wanted = self._session_name(user_id)
        candidates = list(parent.threads)
        candidates.extend(
            thread
            for thread in parent.guild.threads
            if thread.parent_id == parent.id and thread not in candidates
        )
        for thread in candidates:
            if thread.name != wanted:
                continue
            if thread.archived:
                try:
                    await thread.edit(
                        archived=False,
                        locked=False,
                        reason=f"{REASON_TAG}: resume session",
                    )
                except (discord.Forbidden, discord.HTTPException):
                    return None
            elif thread.locked:
                try:
                    await thread.edit(locked=False, reason=f"{REASON_TAG}: unlock session")
                except (discord.Forbidden, discord.HTTPException):
                    return None
            return thread
        return None

    async def _ensure_session(
        self,
        parent: discord.TextChannel,
        member: discord.Member,
    ) -> Optional[discord.Thread]:
        await self._enforce_parent_privacy(parent)
        thread = await self._find_active_session(parent, member.id)
        if thread is None:
            try:
                thread = await parent.create_thread(
                    name=self._session_name(member.id),
                    type=discord.ChannelType.private_thread,
                    invitable=False,
                    auto_archive_duration=60,
                    reason=f"{REASON_TAG}: private session for {member.id}",
                )
            except (discord.Forbidden, discord.HTTPException):
                return None
        try:
            await thread.add_user(member)
        except (discord.Forbidden, discord.HTTPException):
            try:
                await thread.delete(reason=f"{REASON_TAG}: could not grant private access")
            except (discord.Forbidden, discord.HTTPException, discord.NotFound):
                pass
            return None
        if thread.last_message_id is None:
            try:
                await thread.send(
                    embed=discord.Embed(
                        title="🤖 محادثة AI خاصة",
                        description=(
                            f"هاد المحادثة مربوطة بالـID ديالك: `{member.id}`.\n"
                            "غير نتا كتشوف رسائلك بين الأعضاء العاديين، "
                            f"وغادي تتمسح كاملة من بعد **{self.idle_seconds // 60} دقيقة** بلا نشاط."
                        ),
                        color=discord.Color.blurple(),
                    ),
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except (discord.Forbidden, discord.HTTPException):
                pass
        self._touch(thread)
        return thread

    async def _copy_initial_prompt(
        self,
        thread: discord.Thread,
        member: discord.Member,
        prompt: str,
    ) -> None:
        embed = discord.Embed(description=prompt[:4000], color=discord.Color.dark_teal())
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
        try:
            await thread.send(
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except (discord.Forbidden, discord.HTTPException):
            pass

    async def _answer(
        self,
        thread: discord.Thread,
        member: discord.Member,
        prompt: str,
        *,
        copy_prompt: bool,
    ) -> None:
        if not callable(self.ask_ai):
            return
        clean_prompt = str(prompt or "").strip()
        if not clean_prompt:
            return

        key = (int(member.guild.id), int(member.id))
        async with self._lock(*key):
            if copy_prompt:
                await self._copy_initial_prompt(thread, member, clean_prompt)

            elapsed = time.monotonic() - float(self._last_request.get(key, 0.0) or 0.0)
            if elapsed < self.cooldown_seconds:
                await asyncio.sleep(self.cooldown_seconds - elapsed)
            self._last_request[key] = time.monotonic()

            try:
                async with thread.typing():
                    response = await self.ask_ai(
                        str(member.id),
                        member.name,
                        member.display_name,
                        clean_prompt,
                    )
                await thread.send(
                    str(response or "")[: self.max_reply_length],
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return
            finally:
                self._touch(thread)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return
        clean_prompt = str(message.content or "").strip()

        if message.channel.id == self.parent_channel_id:
            # الرسالة العمومية كتتحيد أولاً، ومن بعد كتنسخ للمحادثة الخاصة.
            await self._delete_source_message(message)
            if not clean_prompt or not isinstance(message.author, discord.Member):
                return
            parent = message.channel
            if not isinstance(parent, discord.TextChannel):
                return
            thread = await self._ensure_session(parent, message.author)
            if thread is None:
                return
            await self._answer(thread, message.author, clean_prompt, copy_prompt=True)
            return

        if not self.is_session_thread(message.channel):
            return
        owner_id = self._session_owner_id(message.channel)
        if owner_id != message.author.id:
            await self._delete_source_message(message)
            return
        self._touch(message.channel)
        if clean_prompt and isinstance(message.author, discord.Member):
            await self._answer(message.channel, message.author, clean_prompt, copy_prompt=False)

    async def handle_hybrid_chat(self, ctx: commands.Context, prompt: str) -> bool:
        """كيحوّل /chat لنفس الجلسة الخاصة بلا حتى جواب عام."""
        if ctx.guild is None or not isinstance(ctx.author, discord.Member):
            return False
        channel = ctx.channel
        if channel.id == self.parent_channel_id and isinstance(channel, discord.TextChannel):
            thread = await self._ensure_session(channel, ctx.author)
            if thread is None:
                return False
            await ctx.send(f"🔒 تحلات ليك المحادثة الخاصة: {thread.mention}", ephemeral=True)
            await self._answer(thread, ctx.author, prompt, copy_prompt=True)
            return True
        if self.is_session_thread(channel) and self._session_owner_id(channel) == ctx.author.id:
            await self._answer(channel, ctx.author, prompt, copy_prompt=True)
            return True
        return False

    async def _cleanup_archived_sessions(self, parent: discord.TextChannel) -> None:
        if parent.id in self._archived_cleanup_done:
            return
        self._archived_cleanup_done.add(parent.id)
        try:
            async for thread in parent.archived_threads(
                limit=100,
                private=True,
                joined=True,
            ):
                owner_id = self._session_owner_id(thread)
                if owner_id is None:
                    continue
                self._forget_user(parent.guild.id, owner_id, thread.id)
                try:
                    await thread.delete(reason=f"{REASON_TAG}: remove archived private session")
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue
        except (discord.Forbidden, discord.HTTPException):
            pass

    @tasks.loop(seconds=60)
    async def cleanup_loop(self):
        now = time.time()
        for guild in list(self.bot.guilds):
            parent = guild.get_channel(self.parent_channel_id)
            if not isinstance(parent, discord.TextChannel):
                continue
            await self._enforce_parent_privacy(parent)
            await self._cleanup_archived_sessions(parent)
            for thread in list(parent.threads):
                owner_id = self._session_owner_id(thread)
                if owner_id is None:
                    continue
                last = self._last_activity.get(thread.id, self._thread_last_activity(thread))
                if now - last < self.idle_seconds:
                    continue
                self._forget_user(guild.id, owner_id, thread.id)
                try:
                    await thread.delete(reason=f"{REASON_TAG}: idle timeout")
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    continue

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in list(self.bot.guilds):
            parent = guild.get_channel(self.parent_channel_id)
            if isinstance(parent, discord.TextChannel):
                await self._sync_parent_panel(parent)

    @cleanup_loop.before_loop
    async def _before_cleanup(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_thread_delete(self, thread: discord.Thread):
        owner_id = self._session_owner_id(thread)
        if owner_id is not None:
            self._forget_user(thread.guild.id, owner_id, thread.id)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before, after):
        if isinstance(after, discord.TextChannel) and after.id == self.parent_channel_id:
            await self._enforce_parent_privacy(after)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if (
            int(payload.channel_id) != self.parent_channel_id
            or int(payload.message_id) != self._panel_message_id
            or payload.guild_id is None
        ):
            return
        guild = self.bot.get_guild(int(payload.guild_id))
        parent = guild.get_channel(self.parent_channel_id) if guild else None
        if isinstance(parent, discord.TextChannel):
            self._panel_message_id = 0
            await self._sync_parent_panel(parent)

    async def cog_unload(self):
        self.cleanup_loop.cancel()


async def setup(bot: commands.Bot):
    bot.add_view(AIHomeView())
    await bot.add_cog(PrivateAIChat(bot))
