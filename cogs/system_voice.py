# -*- coding: utf-8 -*-
"""Temporary voice rooms, room mute, AFK, and voice XP.

Extracted mechanically from the legacy ai_bot.py.  Runtime state is attached
to bot_core's shared namespace so existing cross-system references keep the
same object identity and startup order.
"""

import bot_core as core

core.attach_namespace(globals())


# ═══════════════════════════════════════════════════════
# ║        نظام الصوت — Join to Create + Voice XP           ║
# ═══════════════════════════════════════════════════════
TEMP_VOICE_FILE = os.path.join(DATA_DIR, "temp_voice.json")
temp_voice_channels = {}  # {channel_id (str): owner_id (int)} — الروومات المؤقتة اللي تخلقو

# ACL/Panel منفصل باش نبقاو backward-compatible مع temp_voice.json القديم
TEMP_VOICE_ACL_FILE = os.path.join(DATA_DIR, "temp_voice_acl.json")
LEGACY_TEMP_ROOM_FILE = os.path.join(DATA_DIR, "temp_room.json")  # migration ديال الـ Cog القديم
# {channel_id: {owner_id, created_at, private, allowed, denied, muted, attempts, panel_message_id}}
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
        for key, default in (("allowed", []), ("attempts", {}), ("panel_message_id", None)):
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
            ("allowed", []), ("chat_muted", []), ("attempts", {}), ("panel_message_id", None)
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



class JockieVolumeModal(discord.ui.Modal, title="🎵 Jockie Music Volume"):
    volume = discord.ui.TextInput(
        label="دخل الصوت (0 - 100)",
        placeholder="مثال: 50",
        max_length=3,
        required=True
    )

    def __init__(self, voice_channel):
        super().__init__()
        self.voice_channel = voice_channel

    async def on_submit(self, interaction: discord.Interaction):
        ch = self.voice_channel
        value = str(self.volume.value).strip()

        if not value.isdigit() or not 0 <= int(value) <= 100:
            await interaction.response.send_message("❌ دخل رقم بين 0 و 100.", ephemeral=True)
            return

        jockie = next((m for m in ch.members if m.bot and "jockie" in m.name.lower()), None)
        if not jockie:
            await interaction.response.send_message("❌ Jockie Music ما كاينش فهاد الروم الصوتي.", ephemeral=True)
            return

        try:
            await ch.send(f"m!volume {int(value)}")
            await interaction.response.send_message(
                f"✅ تبدل صوت Jockie Music إلى **{value}%**.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ ماقدرتش نرسل الأمر: `{e}`",
                ephemeral=True
            )

class TempVoiceControlView(discord.ui.View):
    """Persistent panel: 11 buttons. كل action كتحل UserSelect ephemeral باش تختار العضو."""
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


    @discord.ui.button(label="🎵 Music Volume", style=discord.ButtonStyle.primary, custom_id="temp_voice_music_volume_button", row=2)
    async def music_volume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = await _temp_voice_require_owner(interaction)
        if not ch:
            return
        await interaction.response.send_modal(JockieVolumeModal(ch))


async def reconcile_temp_voice_rooms(guild: discord.Guild):
    """Self-healing بعد restart: panels + ACL + block/private/mutes."""
    problems = temp_voice_permission_problems(guild)
    if problems:
        print("[TEMP-VOICE] ⚠️ " + " | ".join(problems))
    else:
        print("[TEMP-VOICE] ✅ permissions الأساسية باينة مزيانة")

    stale = []
    for cid, owner_id in list(temp_voice_channels.items()):
        channel = bot.get_channel(int(cid))
        if not channel or not isinstance(channel, discord.VoiceChannel):
            stale.append(str(cid))
            continue
        if channel.guild.id != guild.id:
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
    if stale:
        for cid in stale:
            temp_voice_channels.pop(cid, None)
            temp_voice_acl.pop(cid, None)
        save_temp_voice_channels()
        save_temp_voice_acl()


# ═══════════════════════════════════════════════════════
# ║   Room Mute Lock — زر يكتم/يفك كتم كاع اللي فروم صوتي     ║
# ═══════════════════════════════════════════════════════
ROOM_MUTE_FILE = os.path.join(DATA_DIR, "room_mute.json")
# panels: {message_id (str): channel_id (int)} — رسايل البانل المرتبطة بكل روم
# muted_channels: [channel_id, ...] — الروومات اللي دابا "مقفولة" (كاع لي فيها مكتوم، وأي واحد يدخل ليها يتكتم توا)
# manual_mutes: {channel_id (str): [user_id, ...]} — الأعضاء اللي تكتمو يدوياً من الـ Select
#               (بحماية): زر "فك الكل" ما كيمسهمش، خاصك تفك عليهم بيدك من الـ Select
room_mute_db = {"panels": {}, "muted_channels": [], "manual_mutes": {}}


def load_room_mute():
    global room_mute_db
    try:
        with open(ROOM_MUTE_FILE, "r", encoding="utf-8") as f:
            room_mute_db = json.load(f)
        room_mute_db.setdefault("panels", {})
        room_mute_db.setdefault("muted_channels", [])
        room_mute_db.setdefault("manual_mutes", {})
    except FileNotFoundError:
        room_mute_db = {"panels": {}, "muted_channels": [], "manual_mutes": {}}
    except Exception as e:
        print(f"[ROOM_MUTE] خطأ فـ التحميل: {e}")
        room_mute_db = {"panels": {}, "muted_channels": [], "manual_mutes": {}}


def save_room_mute():
    try:
        with open(ROOM_MUTE_FILE, "w", encoding="utf-8") as f:
            json.dump(room_mute_db, f, ensure_ascii=False)
    except Exception as e:
        print(f"[ROOM_MUTE] خطأ فـ الحفظ: {e}")


load_room_mute()


def can_toggle_room_mute(member: discord.Member, channel: discord.VoiceChannel) -> bool:
    """شكون يقدر "يستعمل" البانل (يدوس على الأزرار/الـ Select ولا يصاوب بانل جديد)
    — Owner + ROOM_MUTE_PANEL_ALLOWED_USER_IDS بوحدهم، حتى Admin/Moderator
    العاديين ماشي معنيين."""
    if OWNER_ID and member.id == OWNER_ID:
        return True
    return member.id in ROOM_MUTE_PANEL_ALLOWED_USER_IDS


async def apply_room_mute_state(channel: discord.VoiceChannel, muted: bool, protected_ids=None):
    """كيطبق Room Mute على الجميع بما فيهم Admin/Mod، باستثناء Server Owner بوحدو."""
    protected_ids = protected_ids or set()
    targets = [
        m for m in channel.members
        if not m.bot and not is_temp_voice_protected_target(m)
        and bool(m.voice and m.voice.mute) != muted and m.id not in protected_ids
    ]

    async def _apply_one(m: discord.Member):
        try:
            await m.edit(mute=muted, reason="Room Mute Panel — كتم/فك الكل")
        except (discord.Forbidden, discord.HTTPException):
            pass

    if targets:
        await asyncio.gather(*(_apply_one(m) for m in targets))
    return len(targets)


def build_room_mute_embed(channel: discord.VoiceChannel, muted: bool) -> discord.Embed:
    embed = discord.Embed(
        title="🔇 الروم مقفولة" if muted else "🔊 الروم محلولة",
        description=(
            f"**Voice Channel:** {channel.mention}\n"
            + ("🔇 كاع اللي فيها مكتومين، بما فيهم Admin/Mod، غير Server Owner مستثنى.\n"
               "💡 تقدر تفك الكتم على شخص معين بوحدو من القائمة تحت، وغادي يبقى محلول حتى تبدل الحالة ديالو يدوياً."
               if muted else
               "🔊 الكل يقدر يهدر عادي فهاد الروم.\n"
               "💡 تقدر تكتم شخص معين بوحدو من القائمة تحت، وغادي يبقى مكتوم حتى تبدل الحالة ديالو يدوياً.")
        ),
        color=discord.Color.red() if muted else discord.Color.green()
    )
    embed.set_footer(text=f"{SERVER_NAME} | Room Mute Panel | {len(channel.members)} عضو دابا فالروم")
    return embed


class RoomMemberSelect(discord.ui.Select):
    """Select كيبين كاع الأعضاء اللي كاينين دابا فالروم — اختيار عضو كيبدل
    (toggle) الحالة ديالو بوحدو (كتم↔فك)، بلا ماتمس الباقي."""

    def __init__(self, channel: Optional[discord.VoiceChannel] = None):
        options = []
        if channel:
            manual_list = room_mute_db.get("manual_mutes", {}).get(str(channel.id), [])
            for m in channel.members:
                if m.bot or is_temp_voice_protected_target(m):
                    continue
                is_muted = bool(m.voice and m.voice.mute)
                is_protected = is_muted and m.id in manual_list
                if is_protected:
                    desc = "🔒 مكتوم يدوياً (محمي من فك الكل) — اختارو باش تفك عليه"
                    emoji = "🔒"
                elif is_muted:
                    desc = "مكتوم دابا — اختارو باش تفك عليه"
                    emoji = "🔇"
                else:
                    desc = "مسموع دابا — اختارو باش تكتمو"
                    emoji = "🎙️"
                options.append(discord.SelectOption(
                    label=m.display_name[:100], value=str(m.id), description=desc, emoji=emoji
                ))
        if not options:
            options = [discord.SelectOption(label="ماكاين حتى عضو (بشري) فالروم دابا", value="none")]

        super().__init__(
            placeholder="🎯 اختار عضو معين باش تبدل الحالة ديالو (كتم/فك كتم)...",
            min_values=1, max_values=1,
            options=options[:25],
            custom_id="room_mute_member_select",
            disabled=(options[0].value == "none"),
        )

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "none":
            await interaction.response.defer()
            return

        actor = interaction.user
        channel_id = room_mute_db.get("panels", {}).get(str(interaction.message.id))
        guild = interaction.guild
        channel = guild.get_channel(channel_id) if guild and channel_id else None
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ الروم ماعادش موجودة.", ephemeral=True)
            return
        if not isinstance(actor, discord.Member) or not can_toggle_room_mute(actor, channel):
            await interaction.response.send_message("❌ ماعندكش صلاحية تستعمل هاد البانل.", ephemeral=True)
            return

        target = guild.get_member(int(self.values[0]))
        if not target or not target.voice or not target.voice.channel or target.voice.channel.id != channel.id:
            await interaction.response.send_message("❌ هاد العضو ماعادش فالروم.", ephemeral=True)
            return

        await interaction.response.defer()
        new_mute = not bool(target.voice.mute)
        try:
            await target.edit(mute=new_mute, reason=f"Room Mute Panel — تبديل يدوي من طرف {actor.display_name}")
        except (discord.Forbidden, discord.HTTPException):
            await interaction.followup.send("❌ ما قدرتش نبدل الحالة ديالو (مشكل صلاحيات).", ephemeral=True)
            return

        # كنسجلو/كنحيدو من manual_mutes باش زر "فك الكل" مايمسوش هاد العضو إلا كتمتيه بيدك
        manual_list = room_mute_db.setdefault("manual_mutes", {}).setdefault(str(channel.id), [])
        if new_mute:
            if target.id not in manual_list:
                manual_list.append(target.id)
        else:
            if target.id in manual_list:
                manual_list.remove(target.id)
        save_room_mute()

        muted_state = channel.id in room_mute_db.get("muted_channels", [])
        embed = build_room_mute_embed(channel, muted_state)
        await interaction.message.edit(embed=embed, view=RoomMuteToggleView(muted_state, channel))
        protect_note = " 🔒 (محمي من زر فك الكل)" if new_mute else ""
        await interaction.followup.send(
            f"{'🔇 تكتم' if new_mute else '🔊 تفك عليه الكتم'} {target.mention}.{protect_note}", ephemeral=True
        )
        if guild:
            await log_action(
                guild,
                "🎯 Room Mute Panel — تبديل عضو معين",
                f"**الروم:** {channel.mention}\n**العضو:** {target.mention}\n"
                f"**الحالة الجديدة:** {'🔇 مكتوم (محمي من فك الكل)' if new_mute else '🔊 مسموع'}\n**من طرف:** {actor.mention}",
                discord.Color.orange()
            )


class RoomMuteToggleView(discord.ui.View):
    """بانل كامل: زوج أزرار (كتم الكل بلا استثناء / فك الكل) + Select باش تبدل
    الحالة ديال شخص معين بوحدو. Persistent — كيلقى الروم بواسطة message id
    ديال البانل (room_mute_db['panels'])."""

    def __init__(self, muted: bool = False, channel: Optional[discord.VoiceChannel] = None):
        super().__init__(timeout=None)
        self.add_item(RoomMemberSelect(channel))

    @discord.ui.button(label="🔇 كتم الكل (بلا استثناء)", style=discord.ButtonStyle.danger,
                        custom_id="room_mute_all_button", row=1)
    async def mute_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_global(interaction, True)

    @discord.ui.button(label="🔊 فك الكل", style=discord.ButtonStyle.success,
                        custom_id="room_unmute_all_button", row=1)
    async def unmute_all_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._set_global(interaction, False)

    async def _set_global(self, interaction: discord.Interaction, new_state: bool):
        member = interaction.user
        channel_id = room_mute_db.get("panels", {}).get(str(interaction.message.id))
        if not channel_id:
            await interaction.response.send_message("❌ ماكاينش هاد البانل فالسجل ديالنا.", ephemeral=True)
            return

        guild = interaction.guild
        channel = guild.get_channel(channel_id) if guild else None
        if not channel or not isinstance(channel, discord.VoiceChannel):
            await interaction.response.send_message("❌ الروم ماعادش موجودة.", ephemeral=True)
            return

        if not isinstance(member, discord.Member) or not can_toggle_room_mute(member, channel):
            await interaction.response.send_message("❌ ماعندكش صلاحية تستعمل هاد البانل.", ephemeral=True)
            return

        await interaction.response.defer()

        if new_state:
            if channel_id not in room_mute_db.setdefault("muted_channels", []):
                room_mute_db["muted_channels"].append(channel_id)
            protected_ids = set()  # كتم الكل كيمس الجميع باستثناء Server Owner
        else:
            room_mute_db["muted_channels"] = [c for c in room_mute_db.get("muted_channels", []) if c != channel_id]
            # "فك الكل" ما كيمسش اللي تكتمو يدوياً من الـ Select — كيبقاو مكتومين
            protected_ids = set(room_mute_db.get("manual_mutes", {}).get(str(channel.id), []))
        save_room_mute()

        count = await apply_room_mute_state(channel, new_state, protected_ids=protected_ids)
        protected_still_muted = len(protected_ids) if not new_state else 0

        embed = build_room_mute_embed(channel, new_state)
        await interaction.message.edit(embed=embed, view=RoomMuteToggleView(new_state, channel))

        protect_note = f" (🔒 {protected_still_muted} عضو بقاو مكتومين حيت تكتمو يدوياً)" if protected_still_muted else ""
        await interaction.followup.send(
            f"{'🔇 الروم تقفلات، تكتمو' if new_state else '🔊 الروم تحلات، تفك الكتم على'} {count} عضو.{protect_note}",
            ephemeral=True
        )
        if guild:
            await log_action(
                guild,
                "🔇 Room Mute Panel — كتم الكل" if new_state else "🔊 Room Mute Panel — فك الكل",
                f"**الروم:** {channel.mention}\n**العدد المتأثر:** {count}\n**من طرف:** {member.mention}",
                discord.Color.red() if new_state else discord.Color.green()
            )














def is_afk_channel(channel: discord.VoiceChannel, guild: discord.Guild) -> bool:
    """واش هاد الروم هي روم AFK؟ (الروم الرسمية ديال السيرفر ولا وحدة من AFK_CHANNEL_IDS)"""
    if guild.afk_channel and channel.id == guild.afk_channel.id:
        return True
    return channel.id in AFK_CHANNEL_IDS


def classify_voice_member(m: discord.Member, channel: discord.VoiceChannel,
                          guild: discord.Guild) -> tuple:
    """كيحدد أشمن درجة ديال XP تستاهل هاد العضو دابا.
    كيرجع (نوع, شحال من XP, واش هو AFK).

    الدرجات:
      stream  🎥 كيدير Go Live / كاميرا      → أكبر XP
      voice   🎤 حال المايك / كيهضر          → XP عادي
      afk_ch  💤 مريح فالروم ديال AFK        → XP مخفض (ولكن أكثر من اللي تحت)
      afk_mut 🔇 سد المايك/Deafen فروم عادية → أصغر XP
    """
    v = m.voice
    if not v:
        return None, 0, False

    # 🎥 لايفستريم ولا كاميرا مشعولة = أعلى درجة، حتى لو المايك مسدود
    if v.self_stream or v.self_video:
        return "stream", int(xp_settings["stream_per_interval"]), False

    in_afk_room = is_afk_channel(channel, guild)
    is_quiet = bool(v.self_mute or v.self_deaf or v.deaf or v.mute)

    # 💤 الروم ديال AFK: مهما كان الحال، هادي درجة AFK ديال الروم
    if in_afk_room:
        return "afk_channel", int(xp_settings["afk_channel_per_interval"]), True

    # 🔇 مايك مسدود / Deafen فروم عادية
    if is_quiet:
        if VOICE_XP_COUNT_MUTED_DEAFENED:
            return "voice", int(xp_settings["voice_per_interval"]), False
        return "afk_muted", int(xp_settings["afk_muted_per_interval"]), True

    # 🎤 المايك محلول = مشارك عادي
    return "voice", int(xp_settings["voice_per_interval"]), False


@tasks.loop(minutes=xp_settings["voice_interval_minutes"])
async def voice_xp_loop():
    if not bot_settings['voice_xp_enabled'] or not bot_settings['leveling_enabled']:
        return
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            # رومات محيدة كامل — حتى XP ديال AFK ماكيتعطاش فيهم
            if channel.id in VOICE_XP_EXCLUDE_CHANNEL_IDS:
                continue
            # روم "دير روم" (Join to Create) ماشي روم حقيقية، غير ممر
            if bot_settings['join_to_create_enabled'] and channel.id == JOIN_TO_CREATE_CHANNEL_ID:
                continue

            humans = [m for m in channel.members if not m.bot]
            if not humans:
                continue
            meets_min_humans = len(humans) >= xp_settings["voice_min_humans"]

            for m in humans:
                kind, amount, is_afk = classify_voice_member(m, channel, guild)
                if not kind or amount <= 0:
                    continue

                # ═══ شرط عدد الناس فالروم (مكافحة الفارمينغ بوحدك) ═══
                if kind == "stream":
                    pass                      # اللايفستريم دايما كيتحسب
                elif is_afk:
                    if not AFK_XP_ENABLED:
                        continue
                    # الروم ديال AFK طبيعي تكون خاوية، علاش الشرط اختياري هنا
                    if AFK_XP_REQUIRE_MIN_HUMANS and not meets_min_humans:
                        continue
                elif not meets_min_humans:
                    continue                  # فويس عادي بوحدو = ماكاين XP

                # ═══ السقف اليومي ديال XP ديال AFK ═══
                if is_afk:
                    amount = afk_xp_allowed(guild.id, m.id, amount)
                    if amount <= 0:
                        continue

                try:
                    await grant_xp_and_announce(m, guild, amount, fallback_channel=channel, source=kind)
                    if is_afk:
                        bump_afk_xp_used(guild.id, m.id, amount)
                except Exception as e:
                    print(f"[VOICE-XP] خطأ فـ إعطاء XP لـ {m}: {e}")


@voice_xp_loop.before_loop
async def before_voice_xp_loop():
    await bot.wait_until_ready()


@voice_xp_loop.error
async def voice_xp_loop_error(error):
    print(f"[VOICE-XP] خطأ كبير وقف الـ loop: {error}")


class VoiceCog(commands.Cog):
    """Discord command/event registration for this subsystem."""

    def __init__(self, bot_instance: commands.Bot):
        self.bot = bot_instance

    @commands.command(name="roommutepanel", hidden=True)
    async def roommutepanel_cmd(self, ctx, channel: Optional[discord.VoiceChannel] = None):
        target_channel = channel
        if not target_channel:
            if isinstance(ctx.author, discord.Member) and ctx.author.voice and ctx.author.voice.channel:
                target_channel = ctx.author.voice.channel
            else:
                await ctx.send("❌ خاصك تكون داخل Voice Channel، ولا تعطي channel كـ parameter.", delete_after=8)
                return

        if not can_toggle_room_mute(ctx.author, target_channel):
            await ctx.send("❌ ماعندكش صلاحية تصاوب هاد البانل.", delete_after=8)
            return

        muted = target_channel.id in room_mute_db.get("muted_channels", [])
        embed = build_room_mute_embed(target_channel, muted)
        view = RoomMuteToggleView(muted, target_channel)
        msg = await ctx.send(embed=embed, view=view)

        room_mute_db.setdefault("panels", {})[str(msg.id)] = target_channel.id
        save_room_mute()

        await log_action(
            ctx.guild,
            "🎛️ Room Mute Panel — تصاوب",
            f"**الروم:** {target_channel.mention}\n**channel البانل:** {ctx.channel.mention}\n**من طرف:** {ctx.author.mention}",
            discord.Color.blue()
        )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return

        # ═══════ Auto AFK: حتى Owner كيتنقل؛ Undeafen فـ AFK كيرجع للروم الأصلية ═══════
        try:
            returned_from_afk = await handle_afk_auto_return(member, before, after)
            update_afk_deafen_tracking(member, before, after)
        except Exception as e:
            returned_from_afk = False
            print(f"[AFK-AUTO-MOVE] خطأ فـ voice tracking/return ديال {member}: {e}")

        # ═══════ Temp Room ACL: Block > Private > Voice Mute. Server Owner محمي. ═══════
        blocked_entry_handled = False
        denied_entry_handled = False
        private_entry_handled = False
        if after.channel and (not before.channel or before.channel.id != after.channel.id) and is_temp_voice_channel(after.channel):
            if not is_temp_voice_protected_target(member):
                blocked_entry_handled = await enforce_temp_voice_block(member, after.channel)
                if not blocked_entry_handled:
                    denied_entry_handled = await enforce_temp_voice_deny(member, after.channel)
                if not blocked_entry_handled and not denied_entry_handled:
                    private_entry_handled = await enforce_temp_voice_private_access(member, after.channel)
                if not blocked_entry_handled and not denied_entry_handled and not private_entry_handled:
                    rec = get_temp_voice_acl(after.channel, create=False)
                    if rec and member.id in rec.get("voice_muted", []):
                        try:
                            if not after.mute:
                                await member.edit(mute=True, reason="Temp room Voice Mute persisted")
                        except (discord.Forbidden, discord.HTTPException):
                            pass

        # Voice Mute ديال temp room محلي للروم: ملي يخرج نفكو server mute، وملي يرجع كيتطبق من جديد.
        if before.channel and (not after.channel or before.channel.id != after.channel.id) and is_temp_voice_channel(before.channel):
            before_rec = get_temp_voice_acl(before.channel, create=False)
            if before_rec and member.id in before_rec.get("voice_muted", []) and not is_temp_voice_protected_target(member):
                try:
                    if after.mute:
                        await member.edit(mute=False, reason="خرج من temp room اللي كان Voice Muted فيها")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # ═══════ Room Mute Lock: Admin/Mod كيتكتمو عادي؛ Server Owner بوحدو مستثنى ═══════
        muted_channels = room_mute_db.get("muted_channels", [])
        if muted_channels and not blocked_entry_handled and not denied_entry_handled and not private_entry_handled and not is_temp_voice_protected_target(member):
            after_channel_id = after.channel.id if after.channel else None
            before_channel_id = before.channel.id if before.channel else None

            if after_channel_id in muted_channels and after_channel_id != before_channel_id:
                try:
                    if not (after.mute):
                        await member.edit(mute=True, reason="دخل لروم مقفولة (Room Mute Lock)")
                except (discord.Forbidden, discord.HTTPException):
                    pass
            elif before_channel_id in muted_channels and after_channel_id != before_channel_id:
                try:
                    if after.mute:
                        await member.edit(mute=False, reason="خرج من روم مقفولة (Room Mute Lock)")
                except (discord.Forbidden, discord.HTTPException):
                    pass

        # ═══════ Join to Create: العضو دخل لـ channel "➕ دير روم" ═══════
        if (bot_settings['join_to_create_enabled'] and JOIN_TO_CREATE_CHANNEL_ID
                and after.channel and after.channel.id == JOIN_TO_CREATE_CHANNEL_ID):
            creator_channel = after.channel
            guild = member.guild
            category = None
            if TEMP_VC_CATEGORY_ID:
                category = guild.get_channel(TEMP_VC_CATEGORY_ID)
            if not category:
                category = creator_channel.category

            overwrites = {
                # الروم كتبان للجميع من البداية. Privacy من بعد غادي تسد غير Connect وما غاديش تخبيها.
                guild.default_role: discord.PermissionOverwrite(view_channel=True, connect=True),
                member: discord.PermissionOverwrite(
                    view_channel=True, connect=True, speak=True, send_messages=True, read_message_history=True,
                    manage_channels=True, move_members=True, mute_members=True, deafen_members=True
                ),
            }
            # البوت خاصو يبقى قادر يبعث/يحدّث البانل ويطبق Block/Kick/Mutes.
            if guild.me:
                overwrites[guild.me] = discord.PermissionOverwrite(
                    view_channel=True, connect=True, send_messages=True, read_message_history=True,
                    manage_messages=(True if guild.me.guild_permissions.manage_messages else None),
                    manage_channels=True, move_members=True,
                    mute_members=(True if guild.me.guild_permissions.mute_members else None)
                )
            # Unverified حتى هو يشوف اسم الروم، ولكن ما يدخلش حتى يتفعل.
            unverified_role = guild.get_role(UNVERIFIED_ROLE_ID) if UNVERIFIED_ROLE_ID else None
            if unverified_role:
                overwrites[unverified_role] = discord.PermissionOverwrite(view_channel=True, connect=False)
            try:
                new_channel = await guild.create_voice_channel(
                    name=TEMP_VC_NAME_TEMPLATE.format(name=member.display_name)[:100],
                    category=category,
                    overwrites=overwrites,
                    user_limit=TEMP_VC_DEFAULT_LIMIT,
                    reason=f"Join to Create — {member.display_name}"
                )
                temp_voice_channels[str(new_channel.id)] = member.id
                save_temp_voice_channels()
                rec = get_temp_voice_acl(new_channel)
                rec["owner_id"] = member.id
                rec["created_at"] = int(new_channel.created_at.timestamp())
                rec["private"] = False
                save_temp_voice_acl()
                await member.move_to(new_channel, reason="Join to Create")
                await send_temp_voice_control_panel(new_channel)
            except discord.Forbidden:
                print("[VOICE] ⚠️ ماعندش صلاحية Manage Channels باش نخلق الروومات المؤقتة.")
            except Exception as e:
                print(f"[VOICE] خطأ فـ خلق روم مؤقت: {e}")

        # ═══════ تنظيف: العضو خرج من روم مؤقت وبقات فارغة ═══════
        if before.channel and str(before.channel.id) in temp_voice_channels:
            left_channel = before.channel
            if len(left_channel.members) == 0:
                # إلا البوت هبط شي واحد من هاد الروم للـ AFK، نخليها موجودة باش يقدر يرجع ليها ملي يفك Deafen.
                if _has_pending_afk_return_to_channel(member.guild.id, left_channel.id):
                    pass
                else:
                    temp_voice_channels.pop(str(left_channel.id), None)
                    temp_voice_acl.pop(str(left_channel.id), None)
                    save_temp_voice_channels()
                    save_temp_voice_acl()
                    try:
                        await left_channel.delete(reason="روم مؤقت بقات فارغة")
                    except (discord.NotFound, discord.Forbidden):
                        pass

    @commands.hybrid_command(name="voicerename", description="بدل سمية الروم الصوتي المؤقت ديالك")
    async def voicerename_cmd(self, ctx, *, new_name: str):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت باش تبدل سميتو.", ephemeral=True)
            return
        channel = ctx.author.voice.channel
        if not is_temp_voice_owner(ctx.author, channel):
            await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
            return
        try:
            await channel.edit(name=new_name[:100], reason=f"Renamed by {ctx.author.display_name}")
            await refresh_temp_voice_control_panel(channel, create_if_missing=True)
            await ctx.send(f"✅ تبدلات سمية الروم لـ **{new_name[:100]}**")
        except discord.HTTPException as e:
            await ctx.send(f"❌ ما قدرتش نبدل السمية: {e}", ephemeral=True)

    @commands.hybrid_command(name="voicelimit", description="حدد عدد الأعضاء المسموح فالروم الصوتي ديالك (0 = بلا حد)")
    async def voicelimit_cmd(self, ctx, limit: int):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت.", ephemeral=True)
            return
        channel = ctx.author.voice.channel
        if not is_temp_voice_owner(ctx.author, channel):
            await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
            return
        limit = max(0, min(limit, 99))
        try:
            await channel.edit(user_limit=limit, reason=f"Limit set by {ctx.author.display_name}")
            await refresh_temp_voice_control_panel(channel, create_if_missing=True)
            await ctx.send(f"✅ الحد الأقصى دابا هو **{limit if limit else 'بلا حدود'}**")
        except discord.HTTPException as e:
            await ctx.send(f"❌ خطأ: {e}", ephemeral=True)

    @commands.hybrid_command(name="voicelock", description="سد الروم الصوتي المؤقت ديالك (حتى واحد ما يقدر يدخل من بعد)")
    async def voicelock_cmd(self, ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت.", ephemeral=True)
            return
        channel = ctx.author.voice.channel
        if not is_temp_voice_owner(ctx.author, channel):
            await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
            return
        ok, msg = await set_temp_voice_private(channel, True, actor=ctx.author)
        await ctx.send(msg, ephemeral=not ok)

    @commands.hybrid_command(name="voiceunlock", description="حل الروم الصوتي المؤقت ديالك")
    async def voiceunlock_cmd(self, ctx):
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ خاصك تكون داخل لروم صوتي مؤقت.", ephemeral=True)
            return
        channel = ctx.author.voice.channel
        if not is_temp_voice_owner(ctx.author, channel):
            await ctx.send("❌ هاد الروم ماشي ديالك.", ephemeral=True)
            return
        ok, msg = await set_temp_voice_private(channel, False, actor=ctx.author)
        await ctx.send(msg, ephemeral=not ok)


async def setup(bot_instance: commands.Bot):
    core.publish_namespace(globals())
    await bot_instance.add_cog(VoiceCog(bot_instance))
