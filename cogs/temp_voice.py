# -*- coding: utf-8 -*-
"""Unchanged ordered source component: temp_voice."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║        نظام الصوت — Join to Create + Voice XP           ║
    # ═══════════════════════════════════════════════════════
    TEMP_VOICE_FILE = os.path.join(DATA_DIR, "temp_voice.json")
    temp_voice_channels = {}  # {channel_id (str): owner_id (int)} — الروومات المؤقتة اللي تخلقو
    
    # ACL/Panel منفصل باش نبقاو backward-compatible مع temp_voice.json القديم
    TEMP_VOICE_ACL_FILE = os.path.join(DATA_DIR, "temp_voice_acl.json")
    LEGACY_TEMP_ROOM_FILE = os.path.join(DATA_DIR, "temp_room.json")  # migration ديال الـ Cog القديم
    # {channel_id: {owner_id, created_at, private, ACL..., panel_message_id, music_bot_id, music_wait_since}}
    temp_voice_acl = {}
    
    
    def load_temp_voice_channels():
        global temp_voice_channels
        try:
            with open(TEMP_VOICE_FILE, "r", encoding="utf-8") as f:
                temp_voice_channels = json.load(f)
        except FileNotFoundError:
            temp_voice_channels = {}
        except Exception as e:
            print(f"[VOICE] خطأ فـ تحميل temp_voice.json: {e}")
            temp_voice_channels = {}
    
    
    def save_temp_voice_channels():
        try:
            with open(TEMP_VOICE_FILE, "w", encoding="utf-8") as f:
                json.dump(temp_voice_channels, f, ensure_ascii=False)
        except Exception as e:
            print(f"[VOICE] خطأ فـ حفظ temp_voice.json: {e}")
    
    
    def load_temp_voice_acl():
        global temp_voice_acl
        try:
            with open(TEMP_VOICE_ACL_FILE, "r", encoding="utf-8") as f:
                temp_voice_acl = json.load(f)
            if not isinstance(temp_voice_acl, dict):
                temp_voice_acl = {}
        except FileNotFoundError:
            temp_voice_acl = {}
        except Exception as e:
            print(f"[TEMP-VOICE ACL] خطأ فـ تحميل temp_voice_acl.json: {e}")
            temp_voice_acl = {}
    
        # Migration من data/temp_room.json القديم + schema القديم ديال denied/muted.
        try:
            with open(LEGACY_TEMP_ROOM_FILE, "r", encoding="utf-8") as f:
                legacy = json.load(f)
        except FileNotFoundError:
            legacy = {}
        except Exception as e:
            print(f"[TEMP-VOICE ACL] migration القديم فشلات بلا ما توقف البوت: {e}")
            legacy = {}
    
        changed = False
        if isinstance(legacy, dict):
            for cid, old_rec in legacy.items():
                if not isinstance(old_rec, dict) or cid not in temp_voice_channels:
                    continue
                rec = temp_voice_acl.setdefault(str(cid), {})
                rec.setdefault("owner_id", old_rec.get("owner") or temp_voice_channels.get(str(cid)))
                rec.setdefault("created_at", 0)
                rec.setdefault("private", False)
                rec.setdefault("allowed", [])
                rec.setdefault("denied", [])
                rec.setdefault("blocked", list(dict.fromkeys(old_rec.get("blocked", []) or [])))
                rec.setdefault("voice_muted", list(dict.fromkeys(old_rec.get("muted", []) or [])))
                rec.setdefault("chat_muted", [])
                rec.setdefault("attempts", {})
                rec.setdefault("panel_message_id", None)
                rec.setdefault("music_bot_id", None)
                rec.setdefault("music_wait_since", old_rec.get("created_at") or 0)
                changed = True
    
        # Upgrade مباشر من النسخة السابقة: Deny كيبقى Deny، و muted القديم -> voice_muted.
        for cid, rec in list(temp_voice_acl.items()):
            if not isinstance(rec, dict):
                temp_voice_acl[cid] = {}
                rec = temp_voice_acl[cid]
                changed = True
            if "denied" not in rec:
                rec["denied"] = []
                changed = True
            if "blocked" not in rec:
                rec["blocked"] = []
                changed = True
            if "voice_muted" not in rec:
                rec["voice_muted"] = list(dict.fromkeys(rec.get("muted", []) or []))
                changed = True
            if "chat_muted" not in rec:
                rec["chat_muted"] = []
                changed = True
            for key, default in (
                ("allowed", []), ("attempts", {}), ("panel_message_id", None),
                ("music_bot_id", None), ("music_wait_since", rec.get("created_at") or 0),
            ):
                if key not in rec:
                    rec[key] = default.copy() if isinstance(default, (dict, list)) else default
                    changed = True
    
        if changed:
            save_temp_voice_acl()
            print("[TEMP-VOICE ACL] ✅ schema/migration تحدّثات")
    
    
    def save_temp_voice_acl():
        try:
            with open(TEMP_VOICE_ACL_FILE, "w", encoding="utf-8") as f:
                json.dump(temp_voice_acl, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[TEMP-VOICE ACL] خطأ فـ حفظ temp_voice_acl.json: {e}")
    
    
    load_temp_voice_channels()
    load_temp_voice_acl()
    
    
    def is_temp_voice_channel(channel) -> bool:
        return bool(channel and str(channel.id) in temp_voice_channels)
    
    
    def get_temp_voice_owner_id(channel: discord.VoiceChannel) -> Optional[int]:
        raw = temp_voice_channels.get(str(channel.id))
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
    
    
    def is_temp_voice_owner(member: discord.Member, channel: discord.VoiceChannel) -> bool:
        """غير مول الروم الحقيقي. Administrator/Manage Channels ما كيعطيش ملكية الروم."""
        owner_id = get_temp_voice_owner_id(channel)
        return owner_id is not None and owner_id == member.id
    
    
    def is_temp_voice_protected_target(member: discord.Member) -> bool:
        """Server Owner بوحدو محمي من Block/Kick/Mute/Private enforcement ديال Temp Rooms."""
        if not member or not getattr(member, "guild", None):
            return False
        if member.id == member.guild.owner_id:
            return True
        return bool(OWNER_ID and member.id == OWNER_ID)
    
    
    def get_temp_voice_acl(channel: discord.VoiceChannel, create: bool = True) -> Optional[dict]:
        cid = str(channel.id)
        rec = temp_voice_acl.get(cid)
        if rec is None and not create:
            return None
        if rec is None:
            owner_id = get_temp_voice_owner_id(channel)
            try:
                created_at = int(channel.created_at.timestamp())
            except Exception:
                created_at = int(datetime.now().timestamp())
            try:
                everyone_ow = channel.overwrites_for(channel.guild.default_role)
                detected_private = everyone_ow.connect is False
            except Exception:
                detected_private = False
            rec = {
                "owner_id": owner_id,
                "created_at": created_at,
                "private": detected_private,
                "allowed": [],
                "denied": [],
                "blocked": [],
                "voice_muted": [],
                "chat_muted": [],
                "attempts": {},
                "panel_message_id": None,
                "music_bot_id": None,
                "music_wait_since": created_at,
            }
            temp_voice_acl[cid] = rec
            save_temp_voice_acl()
        else:
            changed = False
            owner_id = get_temp_voice_owner_id(channel)
            if rec.get("owner_id") != owner_id:
                rec["owner_id"] = owner_id
                changed = True
            if not rec.get("created_at"):
                try:
                    rec["created_at"] = int(channel.created_at.timestamp())
                except Exception:
                    rec["created_at"] = int(datetime.now().timestamp())
                changed = True
            if "private" not in rec:
                try:
                    rec["private"] = channel.overwrites_for(channel.guild.default_role).connect is False
                except Exception:
                    rec["private"] = False
                changed = True
            if "denied" not in rec:
                rec["denied"] = []
                changed = True
            if "blocked" not in rec:
                rec["blocked"] = []
                changed = True
            if "voice_muted" not in rec:
                rec["voice_muted"] = list(dict.fromkeys(rec.get("muted", []) or []))
                changed = True
            for key, default in (
                ("allowed", []), ("chat_muted", []), ("attempts", {}), ("panel_message_id", None),
                ("music_bot_id", None), ("music_wait_since", rec.get("created_at") or 0),
            ):
                if key not in rec:
                    rec[key] = default.copy() if isinstance(default, (dict, list)) else default
                    changed = True
            if changed:
                save_temp_voice_acl()
        return rec
    
    
    def _temp_voice_mentions(ids, limit: int = 8) -> str:
        ids = [int(x) for x in ids if str(x).isdigit()]
        if not ids:
            return "—"
        shown = " ".join(f"<@{uid}>" for uid in ids[:limit])
        if len(ids) > limit:
            shown += f"  +{len(ids) - limit}"
        return shown
    
    
    async def apply_temp_voice_member_permissions(channel: discord.VoiceChannel, member: discord.Member, *, reason: str = "Temp room ACL sync"):
        """كيجمع Block/Private/Allow/VoiceMute/ChatMute فـ overwrite وحدة باش إجراء مايمسحش إجراء آخر."""
        rec = get_temp_voice_acl(channel)
        owner_id = get_temp_voice_owner_id(channel)
    
        if member.id == owner_id:
            overwrite = discord.PermissionOverwrite(
                view_channel=True, connect=True, speak=True,
                send_messages=True, read_message_history=True,
                manage_channels=True, move_members=True, mute_members=True, deafen_members=True,
            )
        elif member.id in rec.get("blocked", []):
            overwrite = discord.PermissionOverwrite(
                view_channel=False, connect=False, speak=False,
                send_messages=False, read_message_history=False,
            )
        else:
            allowed = member.id in rec.get("allowed", [])
            denied = member.id in rec.get("denied", [])
            voice_muted = member.id in rec.get("voice_muted", [])
            chat_muted = member.id in rec.get("chat_muted", [])
            can_connect = False if denied else (allowed or not bool(rec.get("private")))
            overwrite = discord.PermissionOverwrite(
                view_channel=True,
                connect=can_connect,
                speak=(False if voice_muted else (True if allowed else None)),
                send_messages=(False if chat_muted else (True if allowed else None)),
                read_message_history=True,
            )
    
        try:
            await channel.set_permissions(member, overwrite=overwrite, reason=reason)
            return True, None
        except (discord.Forbidden, discord.HTTPException) as e:
            return False, str(e)
    
    
    def build_temp_voice_control_embed(channel: discord.VoiceChannel) -> discord.Embed:
        rec = get_temp_voice_acl(channel)
        owner_id = get_temp_voice_owner_id(channel)
        is_private = bool(rec.get("private"))
        created_at = int(rec.get("created_at") or int(datetime.now().timestamp()))
        allowed = rec.get("allowed", [])
        denied = rec.get("denied", [])
        blocked = rec.get("blocked", [])
        voice_muted = rec.get("voice_muted", [])
        chat_muted = rec.get("chat_muted", [])
    
        embed = discord.Embed(
            title="🎛️ تحكم كامل فالروم المؤقتة",
            description=(
                f"**الروم:** {channel.mention}\n"
                f"**مول الروم:** <@{owner_id}>\n"
                f"**الحالة:** {'🔒 Private — باينة للجميع، الدخول غير لـ Owner + Allowed' if is_private else '🔓 Public — باينة والدخول محلول إلا ماكانش Deny/Block'}\n"
                f"**تصاوبات:** <t:{created_at}:R>  •  <t:{created_at}:t>\n"
                f"**الأعضاء دابا:** {len(channel.members)}  •  **Limit:** {channel.user_limit or '∞'}\n\n"
                "⛔ **Deny:** الروم كتبقى باينة ولكن العضو مايدخلش.\n"
                "🔐 **Block:** كيخبي الروم على العضو وكيمنعو يدخل حتى Unblock؛ Administrator الحقيقي يقدر يتجاوز الإخفاء ديال Discord ولكن البوت كيخرجو فوراً.\n"
                "🚪 **Kick:** غير كيخرجو من الروم؛ الروم كتبقى باينة وماكيتزادش Block.\n"
                "🔇 **Voice Mute:** كتم الصوت فهاد الروم وكيترجع عليه إلا عاود دخل.\n"
                "💬 **Chat Mute:** كتم الكتابة فـ Chat ديال نفس الروم.\n"
                "👑 **Server Owner بوحدو محمي** من Block/Kick/Mute ومن Private enforcement."
            ),
            color=discord.Color.orange() if is_private else discord.Color.green(),
            timestamp=datetime.now()
        )
        embed.add_field(name="🎵 Music Bot", value=temp_music_panel_summary(channel), inline=False)
        embed.add_field(name=f"✅ Allowed ({len(allowed)})", value=_temp_voice_mentions(allowed), inline=False)
        embed.add_field(name=f"⛔ Denied ({len(denied)})", value=_temp_voice_mentions(denied), inline=False)
        embed.add_field(name=f"🔐 Blocked ({len(blocked)})", value=_temp_voice_mentions(blocked), inline=False)
        embed.add_field(name=f"🔇 Voice Muted ({len(voice_muted)})", value=_temp_voice_mentions(voice_muted), inline=False)
        embed.add_field(name=f"💬 Chat Muted ({len(chat_muted)})", value=_temp_voice_mentions(chat_muted), inline=False)
        embed.set_footer(text=f"{SERVER_NAME} | غير مول الروم يقدر يستعمل هاد البانل")
        return embed
    
    
    async def _temp_voice_target_member(guild: discord.Guild, user_obj):
        if isinstance(user_obj, discord.Member):
            return user_obj
        member = guild.get_member(user_obj.id)
        if member:
            return member
        try:
            return await guild.fetch_member(user_obj.id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            return None
    
    
    def _temp_voice_target_guard(channel: discord.VoiceChannel, member: discord.Member, *, allow_room_owner: bool = False):
        if member.bot:
            return "❌ مايمكنش تطبق هاد العملية على Bot."
        if is_temp_voice_protected_target(member):
            return "👑 Server Owner محمي من أوامر الروم ومايمكنش تطبق عليه هاد العملية."
        if not allow_room_owner and member.id == get_temp_voice_owner_id(channel):
            return "❌ مول الروم مايمكنش يطبق هاد العملية على راسو."
        return None
    
    
    async def temp_voice_allow_member(channel: discord.VoiceChannel, member: discord.Member, *, actor=None):
        guard = _temp_voice_target_guard(channel, member, allow_room_owner=True)
        if guard:
            return False, guard
        if member.id == get_temp_voice_owner_id(channel):
            return False, "ℹ️ مول الروم عندو الدخول ديجا."
    
        rec = get_temp_voice_acl(channel)
        if member.id in rec.setdefault("denied", []):
            rec["denied"].remove(member.id)
        if member.id in rec.setdefault("blocked", []):
            rec["blocked"].remove(member.id)
        if member.id not in rec.setdefault("allowed", []):
            rec["allowed"].append(member.id)
        rec.setdefault("attempts", {}).pop(str(member.id), None)
        save_temp_voice_acl()
    
        ok, err = await apply_temp_voice_member_permissions(
            channel, member, reason=f"Temp room allow by {getattr(actor, 'display_name', actor) or 'owner'}"
        )
        if not ok:
            return False, f"❌ تسجل Allow ولكن Discord رفض تحديث permissions: {err}"
        await refresh_temp_voice_control_panel(channel, create_if_missing=True)
        return True, f"✅ {member.mention} ولى Allowed ويقدر يدخل حتى إلا كانت الروم Private."
    
    
    async def temp_voice_deny_member(channel: discord.VoiceChannel, member: discord.Member, *, actor=None):
        """Deny = الروم تبقى باينة، ولكن Connect=False. Admin bypass كيتعالج بالـ event."""
        guard = _temp_voice_target_guard(channel, member)
        if guard:
            return False, guard
    
        rec = get_temp_voice_acl(channel)
        if member.id in rec.setdefault("allowed", []):
            rec["allowed"].remove(member.id)
        if member.id in rec.setdefault("blocked", []):
            rec["blocked"].remove(member.id)
        if member.id not in rec.setdefault("denied", []):
            rec["denied"].append(member.id)
        rec.setdefault("attempts", {})[str(member.id)] = 0
        save_temp_voice_acl()
    
        ok, err = await apply_temp_voice_member_permissions(
            channel, member, reason=f"Temp room deny by {getattr(actor, 'display_name', actor) or 'owner'}"
        )
        if not ok:
            return False, f"❌ تسجل Deny ولكن Discord رفض permissions: {err}"
    
        if member.voice and member.voice.channel and member.voice.channel.id == channel.id:
            try:
                await member.move_to(None, reason="مول الروم دار Deny")
            except (discord.Forbidden, discord.HTTPException):
                pass
        try:
            await member.send(f"⛔ مول **{channel.name}** منعك من الدخول. الروم باقية باينة ليك ولكن ما مسموحش لك تدخل.")
        except (discord.Forbidden, discord.HTTPException):
            pass
    
        await refresh_temp_voice_control_panel(channel, create_if_missing=True)
        return True, f"⛔ {member.mention} تدار ليه Deny: الروم باينة ليه ولكن مايدخلش."
    
    
    async def temp_voice_block_member(channel: discord.VoiceChannel, member: discord.Member, *, actor=None):
        guard = _temp_voice_target_guard(channel, member)
        if guard:
            return False, guard
    
        rec = get_temp_voice_acl(channel)
        if member.id in rec.setdefault("allowed", []):
            rec["allowed"].remove(member.id)
        if member.id in rec.setdefault("denied", []):
            rec["denied"].remove(member.id)
        if member.id not in rec.setdefault("blocked", []):
            rec["blocked"].append(member.id)
        rec.setdefault("attempts", {})[str(member.id)] = 0
        save_temp_voice_acl()
    
        ok, err = await apply_temp_voice_member_permissions(
            channel, member, reason=f"Temp room block by {getattr(actor, 'display_name', actor) or 'owner'}"
        )
        if not ok:
            return False, f"❌ تسجل Block ولكن Discord رفض permissions: {err}"
    
        if member.voice and member.voice.channel and member.voice.channel.id == channel.id:
            try:
                await member.move_to(None, reason="مول الروم دار Block")
            except (discord.Forbidden, discord.HTTPException):
                pass
        admin_note = ""
        if member.guild_permissions.administrator:
            admin_note = " ⚠️ عندو Administrator: Discord يقدر يبقي الروم باينة ليه، ولكن البوت غادي يخرجو فوراً إلا دخل."
        try:
            await member.send(
                f"🔐 مول **{channel.name}** دار لك Block. "
                + ("بسبب Administrator، Discord يقدر يبقي الروم باينة ليك، ولكن ممنوع تبقى داخلها." if member.guild_permissions.administrator
                   else "الروم غادي تبقى مخبية عليك حتى يفك عليك Block.")
            )
        except (discord.Forbidden, discord.HTTPException):
            pass
    
        await refresh_temp_voice_control_panel(channel, create_if_missing=True)
        return True, f"🔐 {member.mention} تدار ليه Block حتى Unblock.{admin_note}"
    
    
    async def temp_voice_unblock_member(channel: discord.VoiceChannel, member: discord.Member, *, actor=None):
        guard = _temp_voice_target_guard(channel, member, allow_room_owner=True)
        if guard:
            return False, guard
        rec = get_temp_voice_acl(channel)
        if member.id not in rec.setdefault("blocked", []):
            return False, f"ℹ️ {member.mention} ماشي Blocked أصلاً."
        rec["blocked"].remove(member.id)
        rec.setdefault("attempts", {}).pop(str(member.id), None)
        save_temp_voice_acl()
    
        ok, err = await apply_temp_voice_member_permissions(
            channel, member, reason=f"Temp room unblock by {getattr(actor, 'display_name', actor) or 'owner'}"
        )
        if not ok:
            return False, f"❌ تحيد Block من السجل ولكن Discord رفض permissions: {err}"
        await refresh_temp_voice_control_panel(channel, create_if_missing=True)
        state = "يقدر يدخل" if (member.id in rec.get("allowed", []) or not rec.get("private")) else "الروم باينة ليه ولكن خاصو Allow باش يدخل حيث Private"
        return True, f"🔓 تفك Block على {member.mention} — {state}."
    
    
    async def temp_voice_kick_member(channel: discord.VoiceChannel, member: discord.Member, *, actor=None):
        guard = _temp_voice_target_guard(channel, member)
        if guard:
            return False, guard
        if not member.voice or not member.voice.channel or member.voice.channel.id != channel.id:
            return False, "❌ هاد العضو ماشي داخل الروم دابا."
        try:
            await member.move_to(None, reason=f"Temp room kick by {getattr(actor, 'display_name', actor) or 'owner'}")
        except (discord.Forbidden, discord.HTTPException) as e:
            return False, f"❌ ما قدرتش نخرجو من الروم: {e}"
        return True, f"🚪 {member.mention} خرج من الروم فقط. ما تدارش ليه Block والروم كتبقى باينة ليه."
    
    
    async def temp_voice_set_voice_mute(channel: discord.VoiceChannel, member: discord.Member, muted: bool, *, actor=None):
        guard = _temp_voice_target_guard(channel, member)
        if guard:
            return False, guard
        rec = get_temp_voice_acl(channel)
        voice_list = rec.setdefault("voice_muted", [])
        if muted and member.id not in voice_list:
            voice_list.append(member.id)
        elif not muted and member.id in voice_list:
            voice_list.remove(member.id)
        save_temp_voice_acl()
    
        ok, err = await apply_temp_voice_member_permissions(channel, member, reason="Temp room voice mute ACL")
        if not ok:
            return False, f"❌ تسجل Voice Mute ولكن Discord رفض overwrite: {err}"
    
        if member.voice and member.voice.channel and member.voice.channel.id == channel.id:
            try:
                await member.edit(mute=muted, reason=f"Temp room voice {'mute' if muted else 'unmute'} by {getattr(actor, 'display_name', actor) or 'owner'}")
            except (discord.Forbidden, discord.HTTPException) as e:
                return False, f"❌ ما قدرتش نبدل Server Voice Mute: {e}"
        await refresh_temp_voice_control_panel(channel, create_if_missing=True)
        return True, (f"🔇 تكتم صوت {member.mention} فهاد الروم." if muted else f"🔊 تفك Voice Mute على {member.mention}.")
    
    
    # الاسم القديم بقى alias لVoice Mute باش /room mute القديم مايتكسرش.
    async def temp_voice_set_manual_mute(channel: discord.VoiceChannel, member: discord.Member, muted: bool, *, actor=None):
        return await temp_voice_set_voice_mute(channel, member, muted, actor=actor)
    
    
    async def temp_voice_set_chat_mute(channel: discord.VoiceChannel, member: discord.Member, muted: bool, *, actor=None):
        guard = _temp_voice_target_guard(channel, member)
        if guard:
            return False, guard
        rec = get_temp_voice_acl(channel)
        chat_list = rec.setdefault("chat_muted", [])
        if muted and member.id not in chat_list:
            chat_list.append(member.id)
        elif not muted and member.id in chat_list:
            chat_list.remove(member.id)
        save_temp_voice_acl()
    
        ok, err = await apply_temp_voice_member_permissions(
            channel, member, reason=f"Temp room chat {'mute' if muted else 'unmute'} by {getattr(actor, 'display_name', actor) or 'owner'}"
        )
        if not ok:
            return False, f"❌ تسجل Chat Mute ولكن Discord رفض permission: {err}"
        await refresh_temp_voice_control_panel(channel, create_if_missing=True)
        return True, (f"💬🔇 {member.mention} ماعادش يقدر يكتب فـ Chat ديال هاد الروم." if muted
                      else f"💬🔊 تفك Chat Mute على {member.mention}.")
    
    
    async def set_temp_voice_private(channel: discord.VoiceChannel, private: bool, *, actor=None):
        """Private = الروم باينة، @everyone connect=False، وOwner + Allowed فقط مسموح لهم."""
        rec = get_temp_voice_acl(channel)
        try:
            await channel.set_permissions(
                channel.guild.default_role,
                view_channel=True,
                connect=(not private),
                reason=f"Temp room {'private' if private else 'public'} by {getattr(actor, 'display_name', actor) or 'owner'}"
            )
        except (discord.Forbidden, discord.HTTPException) as e:
            return False, f"❌ ما قدرتش نبدل Privacy: {e}"
    
        rec["private"] = bool(private)
        save_temp_voice_acl()
    
        # رجع طبّق member overwrites بتركيبة واحدة: Owner/Allowed/Blocked/Mutes.
        relevant_ids = set(rec.get("allowed", [])) | set(rec.get("denied", [])) | set(rec.get("blocked", [])) | set(rec.get("voice_muted", [])) | set(rec.get("chat_muted", []))
        owner_id = get_temp_voice_owner_id(channel)
        if owner_id:
            relevant_ids.add(owner_id)
        for uid in list(relevant_ids):
            m = channel.guild.get_member(int(uid))
            if m:
                await apply_temp_voice_member_permissions(channel, m, reason="Temp room privacy ACL resync")
    
        ejected = 0
        if private:
            allowed_ids = {int(x) for x in rec.get("allowed", [])}
            for current in list(channel.members):
                if current.bot or current.id == owner_id or current.id in allowed_ids or is_temp_voice_protected_target(current):
                    continue
                try:
                    await current.move_to(None, reason="Temp room changed to Private; not Allowed")
                    ejected += 1
                    try:
                        await current.send(f"🔒 **{channel.name}** ولات Private. الدخول غير بإذن مول الروم.")
                    except (discord.Forbidden, discord.HTTPException):
                        pass
                except (discord.Forbidden, discord.HTTPException):
                    pass
    
        await refresh_temp_voice_control_panel(channel, create_if_missing=True)
        if private:
            return True, (f"🔒 الروم ولات Private: باينة للجميع، الدخول غير لـ Owner + Allowed. خرجنا {ejected} عضو." if ejected
                          else "🔒 الروم ولات Private: باينة للجميع، الدخول غير لـ Owner + Allowed.")
        return True, "🔓 الروم ولات Public: الدخول محلول، Denied باقين مايدخلوش وBlocked باقين مخبية عليهم."
    
    
    async def enforce_temp_voice_private_access(member: discord.Member, channel: discord.VoiceChannel) -> bool:
        rec = get_temp_voice_acl(channel, create=False)
        if not rec or not rec.get("private"):
            return False
        if is_temp_voice_protected_target(member):
            return False
        if member.id == get_temp_voice_owner_id(channel) or member.id in rec.get("allowed", []):
            return False
        if member.id in rec.get("blocked", []) or member.id in rec.get("denied", []):
            return False  # Block/Deny عندهم handlers بوحدهم.
    
        moved_out = False
        try:
            await member.move_to(None, reason="Temp room Private: member is not Allowed")
            moved_out = True
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[TEMP-VOICE PRIVATE] ما قدرتش نخرج {member} من {channel.id}: {e}")
        try:
            await member.send(f"🔒 **{channel.name}** راه Private. الروم باينة، ولكن الدخول خاصو Allow من مول الروم.")
        except (discord.Forbidden, discord.HTTPException):
            pass
        if not moved_out:
            await log_action(
                member.guild, "⚠️ فشل إخراج عضو من Private Temp Room",
                f"**الروم:** {channel.mention}\n**العضو:** {member.mention} (`{member.id}`)\nخاص البوت Permission: Move Members.",
                discord.Color.red()
            )
        return True
    
    
    async def enforce_temp_voice_block(member: discord.Member, channel: discord.VoiceChannel) -> bool:
        """Blocked العادي ماكيشوفش الروم. Administrator كيقدر يتجاوز overwrite، لذلك كنخرجو فوراً ونحتافظو بـ 3-attempt fallback."""
        rec = get_temp_voice_acl(channel, create=False)
        if not rec or member.id not in rec.get("blocked", []):
            return False
        if is_temp_voice_protected_target(member) or member.id == get_temp_voice_owner_id(channel):
            return False
    
        attempts = rec.setdefault("attempts", {})
        count = int(attempts.get(str(member.id), 0) or 0) + 1
        attempts[str(member.id)] = count
        save_temp_voice_acl()
    
        moved_out = False
        try:
            await member.move_to(None, reason=f"Temp room Block bypass attempt {count}/{TEMP_VC_DENY_MAX_ATTEMPTS}")
            moved_out = True
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[TEMP-VOICE BLOCK] ما قدرتش نخرج {member} من {channel.id}: {e}")
    
        try:
            await member.send(
                f"🔐 عندك Block من **{channel.name}**. المحاولة: **{count}/{TEMP_VC_DENY_MAX_ATTEMPTS}**. "
                + ("إلا عاودتي مرة أخرى البوت غادي يجرب Kick من السيرفر." if count == TEMP_VC_DENY_MAX_ATTEMPTS - 1 else "")
            )
        except (discord.Forbidden, discord.HTTPException):
            pass
    
        await log_action(
            member.guild, "🔐 محاولة تجاوز Block ديال Temp Room",
            f"**الروم:** {channel.mention}\n**العضو:** {member.mention} (`{member.id}`)\n"
            f"**المحاولة:** {count}/{TEMP_VC_DENY_MAX_ATTEMPTS}\n**خرج من الروم:** {'نعم' if moved_out else 'فشل'}",
            discord.Color.orange()
        )
    
        if count >= TEMP_VC_DENY_MAX_ATTEMPTS and TEMP_VC_DENY_KICK_FROM_SERVER:
            kicked = False
            kick_error = None
            try:
                await member.kick(reason=f"كرر تجاوز Block ديال Temp Room {count} مرات: {channel.name}")
                kicked = True
            except (discord.Forbidden, discord.HTTPException) as e:
                kick_error = str(e)
            if kicked:
                await log_action(
                    member.guild, "👢 Kick تلقائي — تجاوز Block 3 مرات",
                    f"**العضو:** <@{member.id}> (`{member.id}`)\n**الروم:** {channel.mention}\n**المحاولات:** {count}",
                    discord.Color.red()
                )
            else:
                await log_action(
                    member.guild, "⚠️ فشل Kick بعد تجاوز Block",
                    f"**العضو:** {member.mention} (`{member.id}`)\n**الروم:** {channel.mention}\n"
                    f"**السبب:** {kick_error or 'غير معروف'}\nRole ديال البوت خاصها تكون فوق أعلى Role ديال العضو باش Kick يخدم.",
                    discord.Color.red()
                )
    
        await refresh_temp_voice_control_panel(channel, create_if_missing=True)
        return True
    
    
    async def enforce_temp_voice_deny(member: discord.Member, channel: discord.VoiceChannel) -> bool:
        """Deny bypass: Admin يقدر يتجاوز CONNECT=False؛ كنخرجو فوراً، وبعد 3 محاولات Kick من السيرفر إذا ممكن."""
        rec = get_temp_voice_acl(channel, create=False)
        if not rec or member.id not in rec.get("denied", []):
            return False
        if is_temp_voice_protected_target(member) or member.id == get_temp_voice_owner_id(channel):
            return False
    
        attempts = rec.setdefault("attempts", {})
        count = int(attempts.get(str(member.id), 0) or 0) + 1
        attempts[str(member.id)] = count
        save_temp_voice_acl()
    
        moved_out = False
        try:
            await member.move_to(None, reason=f"Temp room Deny bypass attempt {count}/{TEMP_VC_DENY_MAX_ATTEMPTS}")
            moved_out = True
        except (discord.Forbidden, discord.HTTPException) as e:
            print(f"[TEMP-VOICE DENY] ما قدرتش نخرج {member} من {channel.id}: {e}")
        try:
            await member.send(
                f"⛔ ممنوع تدخل **{channel.name}**. المحاولة: **{count}/{TEMP_VC_DENY_MAX_ATTEMPTS}**. "
                + ("إلا عاودتي مرة أخرى البوت غادي يجرب Kick من السيرفر." if count == TEMP_VC_DENY_MAX_ATTEMPTS - 1 else "")
            )
        except (discord.Forbidden, discord.HTTPException):
            pass
    
        await log_action(
            member.guild, "⛔ محاولة تجاوز Deny ديال Temp Room",
            f"**الروم:** {channel.mention}\n**العضو:** {member.mention} (`{member.id}`)\n"
            f"**المحاولة:** {count}/{TEMP_VC_DENY_MAX_ATTEMPTS}\n**خرج من الروم:** {'نعم' if moved_out else 'فشل'}",
            discord.Color.orange()
        )
    
        if count >= TEMP_VC_DENY_MAX_ATTEMPTS and TEMP_VC_DENY_KICK_FROM_SERVER:
            try:
                await member.kick(reason=f"كرر تجاوز Deny ديال Temp Room {count} مرات: {channel.name}")
                await log_action(
                    member.guild, "👢 Kick تلقائي — تجاوز Deny 3 مرات",
                    f"**العضو:** <@{member.id}> (`{member.id}`)\n**الروم:** {channel.mention}\n**المحاولات:** {count}",
                    discord.Color.red()
                )
            except (discord.Forbidden, discord.HTTPException) as e:
                await log_action(
                    member.guild, "⚠️ فشل Kick بعد تجاوز Deny",
                    f"**العضو:** {member.mention} (`{member.id}`)\n**الروم:** {channel.mention}\n**السبب:** {e}",
                    discord.Color.red()
                )
    
        await refresh_temp_voice_control_panel(channel, create_if_missing=True)
        return True
    
    
    temp_voice_chat_mute_notice_cooldowns = {}
    
    
    async def enforce_temp_voice_chat_mute_message(message: discord.Message) -> bool:
        """Fallback مهم للـ Administrator: ADMINISTRATOR كيتجاوز SEND_MESSAGES=False، فنمسحو الرسالة فور وصولها."""
        if not message.guild or not isinstance(message.author, discord.Member):
            return False
        channel = message.channel
        if not isinstance(channel, discord.VoiceChannel) or not is_temp_voice_channel(channel):
            return False
        if is_temp_voice_protected_target(message.author):
            return False
        rec = get_temp_voice_acl(channel, create=False)
        if not rec or message.author.id not in rec.get("chat_muted", []):
            return False
        try:
            await message.delete()
        except (discord.Forbidden, discord.HTTPException):
            return False
    
        key = (channel.id, message.author.id)
        now = datetime.now()
        last = temp_voice_chat_mute_notice_cooldowns.get(key)
        if not last or (now - last).total_seconds() >= 30:
            temp_voice_chat_mute_notice_cooldowns[key] = now
            try:
                await message.author.send(f"💬🔇 مول **{channel.name}** كتم عليك الكتابة فـ Chat ديال هاد الروم.")
            except (discord.Forbidden, discord.HTTPException):
                pass
        return True
    
    
    async def refresh_temp_voice_control_panel(channel: discord.VoiceChannel, create_if_missing: bool = False):
        if not is_temp_voice_channel(channel):
            return None
        rec = get_temp_voice_acl(channel)
        msg_id = rec.get("panel_message_id")
        if msg_id:
            try:
                msg = await channel.fetch_message(int(msg_id))
                await msg.edit(embed=build_temp_voice_control_embed(channel), view=TempVoiceControlView(bool(rec.get("private"))))
                return msg
            except (discord.NotFound, discord.Forbidden, discord.HTTPException, AttributeError, TypeError, ValueError) as e:
                print(f"[TEMP-VOICE PANEL] refresh فشل فـ {channel.id}: {e}")
                rec["panel_message_id"] = None
                save_temp_voice_acl()
        if create_if_missing:
            return await send_temp_voice_control_panel(channel)
        return None
    
    
    async def send_temp_voice_control_panel(channel: discord.VoiceChannel):
        if not is_temp_voice_channel(channel):
            return None
        rec = get_temp_voice_acl(channel)
        try:
            msg = await channel.send(
                content=f"<@{get_temp_voice_owner_id(channel)}> هادي لوحة التحكم الكاملة ديال الروم ديالك 👇",
                embed=build_temp_voice_control_embed(channel),
                view=TempVoiceControlView(bool(rec.get("private")))
            )
            rec["panel_message_id"] = msg.id
            save_temp_voice_acl()
            return msg
        except (discord.Forbidden, discord.HTTPException, AttributeError, TypeError, ValueError) as e:
            print(f"[TEMP-VOICE PANEL] ما قدرتش نبعث البانل فـ {channel.id}: {e}")
            return None
    
    
    def temp_voice_permission_problems(guild: discord.Guild) -> list:
        me = guild.me
        if not me:
            return ["ما لقيناش bot member فـ guild cache"]
        p = me.guild_permissions
        problems = []
        required = [
            ("manage_channels", "Manage Channels"),
            ("manage_roles", "Manage Roles / Permissions"),
            ("move_members", "Move Members"),
            ("mute_members", "Mute Members"),
            ("manage_messages", "Manage Messages (Chat Mute fallback)"),
            ("kick_members", "Kick Members (3-attempt Block fallback)"),
        ]
        for attr, label in required:
            if not getattr(p, attr, False):
                problems.append(f"خاص البوت Permission: {label}")
        for rid, label in ((ADMIN_ROLE_ID, "Admin"), (MODERATOR_ROLE_ID, "Moderator")):
            role = guild.get_role(rid) if rid else None
            if role and me.top_role <= role:
                problems.append(f"Role ديال البوت خاصها تكون فوق Role {label} ({role.name}) باش Kick من السيرفر يخدم")
        return problems
    
    
    async def _temp_voice_interaction_channel(interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
        ch = interaction.channel
        if isinstance(ch, discord.VoiceChannel) and is_temp_voice_channel(ch):
            return ch
        return None
    
    
    async def _temp_voice_require_owner(interaction: discord.Interaction) -> Optional[discord.VoiceChannel]:
        ch = await _temp_voice_interaction_channel(interaction)
        if not ch:
            await interaction.response.send_message("❌ هاد البانل ماعادش مربوط بروم مؤقتة صالحة.", ephemeral=True)
            return None
        if not isinstance(interaction.user, discord.Member) or not is_temp_voice_owner(interaction.user, ch):
            await interaction.response.send_message("❌ غير مول الروم يقدر يستعمل هاد البانل — Admin/Mod ماعندهمش التحكم فيه.", ephemeral=True)
            return None
        return ch
    
    
    TEMP_VOICE_HAS_USER_SELECT = hasattr(discord.ui, "UserSelect")
    
    
    async def _run_temp_voice_action(channel: discord.VoiceChannel, target: discord.Member, action: str, actor):
        if action == "allow":
            return await temp_voice_allow_member(channel, target, actor=actor)
        if action == "deny":
            return await temp_voice_deny_member(channel, target, actor=actor)
        if action == "block":
            return await temp_voice_block_member(channel, target, actor=actor)
        if action == "unblock":
            return await temp_voice_unblock_member(channel, target, actor=actor)
        if action == "kick":
            return await temp_voice_kick_member(channel, target, actor=actor)
        if action == "voice_mute":
            return await temp_voice_set_voice_mute(channel, target, True, actor=actor)
        if action == "voice_unmute":
            return await temp_voice_set_voice_mute(channel, target, False, actor=actor)
        if action == "chat_mute":
            return await temp_voice_set_chat_mute(channel, target, True, actor=actor)
        if action == "chat_unmute":
            return await temp_voice_set_chat_mute(channel, target, False, actor=actor)
        return False, "❌ Action غير معروفة."
    
    
    _TEMP_ACTION_LABELS = {
        "allow": "✅ Allow",
        "deny": "⛔ Deny",
        "block": "🔐 Block",
        "unblock": "🔓 Unblock",
        "kick": "🚪 Kick from room",
        "voice_mute": "🔇 Voice Mute",
        "voice_unmute": "🔊 Voice Unmute",
        "chat_mute": "💬🔇 Chat Mute",
        "chat_unmute": "💬🔊 Chat Unmute",
    }
    
    
    if TEMP_VOICE_HAS_USER_SELECT:
        class TempVoiceActionUserSelect(discord.ui.UserSelect):
            def __init__(self, channel_id: int, action: str):
                self.channel_id = channel_id
                self.action = action
                super().__init__(
                    placeholder=f"{_TEMP_ACTION_LABELS[action]} — اختار العضو...",
                    min_values=1,
                    max_values=1,
                    custom_id=f"temp_voice_action_pick_{action}",
                )
    
            async def callback(self, interaction: discord.Interaction):
                guild = interaction.guild
                channel = guild.get_channel(self.channel_id) if guild else None
                if not guild or not channel or not isinstance(channel, discord.VoiceChannel) or not is_temp_voice_channel(channel):
                    await interaction.response.send_message("❌ الروم ماعادش موجودة.", ephemeral=True)
                    return
                if not isinstance(interaction.user, discord.Member) or not is_temp_voice_owner(interaction.user, channel):
                    await interaction.response.send_message("❌ غير مول الروم يقدر يستعمل هاد العملية.", ephemeral=True)
                    return
                target = await _temp_voice_target_member(guild, self.values[0])
                if not target:
                    await interaction.response.send_message("❌ ما لقيتش هاد العضو فالسيرفر.", ephemeral=True)
                    return
                await interaction.response.defer(ephemeral=True)
                ok, msg = await _run_temp_voice_action(channel, target, self.action, interaction.user)
                await interaction.followup.send(msg, ephemeral=True)
    
    
        class TempVoiceActionTargetView(discord.ui.View):
            def __init__(self, channel_id: int, action: str):
                super().__init__(timeout=60)
                self.add_item(TempVoiceActionUserSelect(channel_id, action))
    else:
        TempVoiceActionUserSelect = None
        TempVoiceActionTargetView = None
    
    
    class TempVoiceMemberIdModal(discord.ui.Modal):
        def __init__(self, channel_id: int, action: str):
            super().__init__(title=_TEMP_ACTION_LABELS.get(action, "🎛️ Temp Room Action"))
            self.channel_id = channel_id
            self.action = action
            self.member_value = discord.ui.TextInput(
                label="Mention أو User ID",
                placeholder="مثال: @Ahmed أو 123456789012345678",
                min_length=2,
                max_length=60,
            )
            self.add_item(self.member_value)
    
        async def on_submit(self, interaction: discord.Interaction):
            guild = interaction.guild
            channel = guild.get_channel(self.channel_id) if guild else None
            if not guild or not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message("❌ الروم ماعادش موجودة.", ephemeral=True)
                return
            if not isinstance(interaction.user, discord.Member) or not is_temp_voice_owner(interaction.user, channel):
                await interaction.response.send_message("❌ غير مول الروم يقدر يدير هاد العملية.", ephemeral=True)
                return
            match = re.search(r"(\d{15,22})", str(self.member_value.value))
            if not match:
                await interaction.response.send_message("❌ دخل Mention صحيح ولا User ID صحيح.", ephemeral=True)
                return
            uid = int(match.group(1))
            target = guild.get_member(uid)
            if not target:
                try:
                    target = await guild.fetch_member(uid)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    target = None
            if not target:
                await interaction.response.send_message("❌ هاد العضو ما لقيتوش فالسيرفر.", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            ok, msg = await _run_temp_voice_action(channel, target, self.action, interaction.user)
            await interaction.followup.send(msg, ephemeral=True)
    
    
    async def _open_temp_voice_action_picker(interaction: discord.Interaction, action: str):
        ch = await _temp_voice_require_owner(interaction)
        if not ch:
            return
        if TEMP_VOICE_HAS_USER_SELECT:
            await interaction.response.send_message(
                f"{_TEMP_ACTION_LABELS[action]} — اختار العضو من اللائحة:",
                view=TempVoiceActionTargetView(ch.id, action),
                ephemeral=True,
            )
        else:
            await interaction.response.send_modal(TempVoiceMemberIdModal(ch.id, action))
    
    
    
    class TempVoiceControlView(discord.ui.View):
        """Persistent panel: 12 buttons. كل action كتحل UserSelect ephemeral باش تختار العضو."""
        def __init__(self, private: bool = False):
            super().__init__(timeout=None)
            for item in self.children:
                if getattr(item, "custom_id", None) == "temp_voice_privacy_toggle":
                    item.label = "🔓 Public" if private else "🔒 Private"
                    item.style = discord.ButtonStyle.success if private else discord.ButtonStyle.secondary
    
        @discord.ui.button(label="🔒 Private", style=discord.ButtonStyle.secondary, custom_id="temp_voice_privacy_toggle", row=0)
        async def privacy_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
            ch = await _temp_voice_require_owner(interaction)
            if not ch:
                return
            new_private = not bool(get_temp_voice_acl(ch).get("private"))
            await interaction.response.defer(ephemeral=True)
            ok, msg = await set_temp_voice_private(ch, new_private, actor=interaction.user)
            await interaction.followup.send(msg, ephemeral=True)
    
        @discord.ui.button(label="✅ Allow", style=discord.ButtonStyle.success, custom_id="temp_voice_allow_button", row=0)
        async def allow_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await _open_temp_voice_action_picker(interaction, "allow")
    
        @discord.ui.button(label="⛔ Deny", style=discord.ButtonStyle.secondary, custom_id="temp_voice_deny_button", row=0)
        async def deny_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await _open_temp_voice_action_picker(interaction, "deny")
    
        @discord.ui.button(label="🔐 Block", style=discord.ButtonStyle.danger, custom_id="temp_voice_block_button", row=0)
        async def block_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await _open_temp_voice_action_picker(interaction, "block")
    
        @discord.ui.button(label="🔓 Unblock", style=discord.ButtonStyle.secondary, custom_id="temp_voice_unblock_button", row=0)
        async def unblock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await _open_temp_voice_action_picker(interaction, "unblock")
    
        @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary, custom_id="temp_voice_panel_refresh", row=2)
        async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            ch = await _temp_voice_require_owner(interaction)
            if not ch:
                return
            await interaction.response.edit_message(
                embed=build_temp_voice_control_embed(ch),
                view=TempVoiceControlView(bool(get_temp_voice_acl(ch).get("private")))
            )
    
        @discord.ui.button(label="🚪 Kick", style=discord.ButtonStyle.danger, custom_id="temp_voice_kick_button", row=1)
        async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await _open_temp_voice_action_picker(interaction, "kick")
    
        @discord.ui.button(label="🔇 Voice Mute", style=discord.ButtonStyle.secondary, custom_id="temp_voice_voice_mute_button", row=1)
        async def voice_mute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await _open_temp_voice_action_picker(interaction, "voice_mute")
    
        @discord.ui.button(label="🔊 Voice Unmute", style=discord.ButtonStyle.secondary, custom_id="temp_voice_voice_unmute_button", row=1)
        async def voice_unmute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await _open_temp_voice_action_picker(interaction, "voice_unmute")
    
        @discord.ui.button(label="💬🔇 Chat Mute", style=discord.ButtonStyle.secondary, custom_id="temp_voice_chat_mute_button", row=1)
        async def chat_mute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await _open_temp_voice_action_picker(interaction, "chat_mute")
    
        @discord.ui.button(label="💬🔊 Chat Unmute", style=discord.ButtonStyle.secondary, custom_id="temp_voice_chat_unmute_button", row=1)
        async def chat_unmute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            await _open_temp_voice_action_picker(interaction, "chat_unmute")
    
    
        @discord.ui.button(label="🎵 Music", style=discord.ButtonStyle.primary, custom_id="temp_voice_music_button", row=2)
        async def music_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            ch = await _temp_voice_require_owner(interaction)
            if not ch:
                return
            await interaction.response.defer(ephemeral=True)
            await open_temp_music_panel(interaction, ch)
    
    
    async def reconcile_temp_voice_rooms(guild: discord.Guild):
        """Self-healing بعد restart: cleanup + music leases + panels + ACL."""
        problems = temp_voice_permission_problems(guild)
        if problems:
            print("[TEMP-VOICE] ⚠️ " + " | ".join(problems))
        else:
            print("[TEMP-VOICE] ✅ permissions الأساسية باينة مزيانة")

        # أولاً نحيدو bot-only rooms والرومات القديمة اللي ضاع tracking ديالها.
        await sweep_empty_temp_voice_rooms(guild)

        stale = []
        active_channels = []
        for cid, owner_id in list(temp_voice_channels.items()):
            try:
                channel_id = int(cid)
            except (TypeError, ValueError):
                stale.append(str(cid))
                continue
            channel = bot.get_channel(channel_id)
            if not channel or not isinstance(channel, discord.VoiceChannel):
                stale.append(str(cid))
                continue
            if channel.guild.id != guild.id:
                continue
            if not has_human_members(channel.members):
                await cleanup_temp_voice_room_if_empty(
                    channel,
                    grace_seconds=0,
                    reason="Restart cleanup — Temp Room بلا أعضاء",
                )
                continue
            active_channels.append(channel)

        if stale:
            for cid in stale:
                temp_voice_channels.pop(cid, None)
                temp_voice_acl.pop(cid, None)
            save_temp_voice_channels()
            save_temp_voice_acl()

        await reconcile_temp_music_assignments(guild)

        for channel in active_channels:
            if str(channel.id) not in temp_voice_channels:
                continue
            rec = get_temp_voice_acl(channel)
            await refresh_temp_voice_control_panel(channel, create_if_missing=True)
    
            relevant_ids = set(rec.get("allowed", [])) | set(rec.get("denied", [])) | set(rec.get("blocked", [])) | set(rec.get("voice_muted", [])) | set(rec.get("chat_muted", []))
            if get_temp_voice_owner_id(channel):
                relevant_ids.add(get_temp_voice_owner_id(channel))
            for uid in relevant_ids:
                m = guild.get_member(int(uid))
                if m:
                    await apply_temp_voice_member_permissions(channel, m, reason="Temp room restore after restart")
    
            for m in list(channel.members):
                if m.bot or m.id == get_temp_voice_owner_id(channel) or is_temp_voice_protected_target(m):
                    continue
                if m.id in rec.get("blocked", []):
                    await enforce_temp_voice_block(m, channel)
                    continue
                if m.id in rec.get("denied", []):
                    await enforce_temp_voice_deny(m, channel)
                    continue
                if rec.get("private") and m.id not in rec.get("allowed", []):
                    await enforce_temp_voice_private_access(m, channel)
                    continue
                if m.id in rec.get("voice_muted", []):
                    try:
                        if not (m.voice and m.voice.mute):
                            await m.edit(mute=True, reason="Temp room Voice Mute restore after restart")
                    except (discord.Forbidden, discord.HTTPException):
                        pass
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
