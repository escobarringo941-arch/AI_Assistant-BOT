# -*- coding: utf-8 -*-
from __future__ import annotations

import discord
from . import config


class CityNotifier:
    def __init__(self, bot, store):
        self.bot = bot
        self.store = store

    async def send(self, guild: discord.Guild, member: discord.Member, message: str, *, kind: str = "jobs") -> dict:
        profile = self.store.profile(guild.id, member.id, {})
        prefs = profile.setdefault("notifications", dict(config.DEFAULT_NOTIFICATIONS))
        if kind in prefs and not bool(prefs.get(kind, True)):
            return {"dm":False,"fallback":False,"disabled":True}

        dm_ok = False
        if prefs.get("dm", True):
            try:
                await member.send(message)
                dm_ok = True
            except (discord.Forbidden, discord.HTTPException):
                dm_ok = False

        fallback_ok = False
        if not dm_ok and prefs.get("fallback", True):
            setup = self.store.guild(guild.id).get("setup", {})
            cid = int((setup.get("channels") or {}).get("city_alerts") or 0)
            channel = guild.get_channel(cid) if cid else None
            if isinstance(channel, discord.TextChannel):
                try:
                    msg = await channel.send(
                        f"🔔 {member.mention} عندك **تحديث جديد فـGGMW9 CITY**. دخل لـ <#{int((setup.get('channels') or {}).get('career_center') or 0)}> باش تشوف التفاصيل.",
                        allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                    )
                    fallback_ok = True
                    if config.ALERT_DELETE_SECONDS > 0:
                        try:
                            await msg.delete(delay=config.ALERT_DELETE_SECONDS)
                        except Exception:
                            pass
                except (discord.Forbidden, discord.HTTPException):
                    pass
        return {"dm":dm_ok,"fallback":fallback_ok,"disabled":False}
