# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║ cogs/moderation.py — 🛡️ موديريشن + صلاحيات Owner  ║
═══════════════════════════════════════════════════════
"""

import asyncio
from datetime import datetime
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

# هاد القيم خاصها تكون هي نفسها اللي عندك فـ ai_bot-63-3.py
OWNER_ID = 1260089246216097832  # ← عدّلها بنفس OWNER_ID ديالك
SERVER_NAME = "GGMW9"

# IDs ديال الرولات المعفاة (Admins / Mods)
EXEMPT_ROLE_IDS = [
    1525712399456272495,  # Admin
    1526182506272133180,  # Moderator
]

# رول الكتم
MUTED_ROLE_ID = 1526468718534590574  # عدّلها إذا مختلفة فالسيرفر ديالك

# ألوان
COLOR_WARN = discord.Color.yellow()
COLOR_MUTE = discord.Color.yellow()
COLOR_UNMUTE = discord.Color.green()
COLOR_KICK = discord.Color.orange()
COLOR_BAN = discord.Color.red()
COLOR_UNBAN = discord.Color.green()

# ═══════════════════════════════════════════════════════
# نظام صلاحيات إضافي للأوامر (Owner يتحكم)
# ═══════════════════════════════════════════════════════
# owner_only = True  → غير Owner يقدر يستعمل الأمر
# allowed_roles      → إلا بغيتي تحصر أمر فـ رولات معينة (حالياً نخليها فارغة)

COMMAND_ROLES = {
    "ownerkick":  {"owner_only": True, "allowed_roles": []},
    "ownerban":   {"owner_only": True, "allowed_roles": []},
    "ownermute":  {"owner_only": True, "allowed_roles": []},
    "muteall":    {"owner_only": True, "allowed_roles": []},
    "unmuteall":  {"owner_only": True, "allowed_roles": []},

    "kick":   {"owner_only": False, "allowed_roles": []},
    "ban":
