# -*- coding: utf-8 -*-
"""
🎤 نظام الروم المؤقتة - أمر واحد فقط!
"""

import discord
from discord.ext import commands
from discord import app_commands
import json
import os

class TempRoom(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = {}
        self.load_data()
    
    def load_data(self):
        os.makedirs("data", exist_ok=True)
        if os.path.exists("data/temp_room.json"):
            with open("data/temp_room.json", "r", encoding="utf-8") as f:
                self.data = json.load(f)
    
    def save_data(self):
        with open("data/temp_room.json", "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def is_temp_room(self, channel):
        if not channel or not channel.category:
            return False
        return "🎤" in channel.category.name or "temp" in channel.category.name.lower()
    
    def is_owner(self, member, channel):
        cid = str(channel.id)
        if cid in self.data:
            return self.data[cid]["owner"] == member.id
        return member.guild_permissions.manage_channels
    
    def register_owner(self, channel, owner):
        cid = str(channel.id)
        if cid not in self.data:
            self.data[cid] = {
                "owner": owner.id,
                "muted": [],
                "blocked": []
            }
            self.save_data()
    
    # ═══════════════════════════════════════════════════════════════
    # أمر واحد فقط: /room
    # ═══════════════════════════════════════════════════════════════
    
    room = app_commands.Group(name="room", description="🎤 إدارة الروم")
    
    @room.command(name="mute", description="🔇 كتم الصوت")
    async def mute(self, ctx: discord.Interaction, user: discord.User):
        if not ctx.user.voice or not ctx.user.voice.channel:
            return await ctx.response.send_message("❌ أنت ما في روم!", ephemeral=True)
        
        ch = ctx.user.voice.channel
        if not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ ما هاد روم مؤقتة!", ephemeral=True)
        
        if not self.is_owner(ctx.user, ch):
            return await ctx.response.send_message("❌ أنت ما مالك الروم!", ephemeral=True)
        
        cid = str(ch.id)
        self.register_owner(ch, ctx.user)
        
        if user.id in self.data[cid]["muted"]:
            return await ctx.response.send_message("⚠️ محكوم بالفعل", ephemeral=True)
        
        self.data[cid]["muted"].append(user.id)
        self.save_data()
        
        member = ch.guild.get_member(user.id)
        if member:
            await member.edit(mute=True)
            await ctx.response.send_message(f"🔇 {user.mention} مكتوم!")
    
    @room.command(name="unmute", description="🔊 فك الكتم")
    async def unmute(self, ctx: discord.Interaction, user: discord.User):
        if not ctx.user.voice or not ctx.user.voice.channel:
            return await ctx.response.send_message("❌ أنت ما في روم!", ephemeral=True)
        
        ch = ctx.user.voice.channel
        if not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ ما هاد روم مؤقتة!", ephemeral=True)
        
        if not self.is_owner(ctx.user, ch):
            return await ctx.response.send_message("❌ أنت ما مالك الروم!", ephemeral=True)
        
        cid = str(ch.id)
        if cid not in self.data or user.id not in self.data[cid]["muted"]:
            return await ctx.response.send_message("⚠️ ما كان مكتوم", ephemeral=True)
        
        self.data[cid]["muted"].remove(user.id)
        self.save_data()
        
        member = ch.guild.get_member(user.id)
        if member:
            await member.edit(mute=False)
            await ctx.response.send_message(f"🔊 الكتم رفع على {user.mention}!")
    
    @room.command(name="kick", description="🚫 طيح من الروم")
    async def kick(self, ctx: discord.Interaction, user: discord.User):
        if not ctx.user.voice or not ctx.user.voice.channel:
            return await ctx.response.send_message("❌ أنت ما في روم!", ephemeral=True)
        
        ch = ctx.user.voice.channel
        if not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ ما هاد روم مؤقتة!", ephemeral=True)
        
        if not self.is_owner(ctx.user, ch):
            return await ctx.response.send_message("❌ أنت ما مالك الروم!", ephemeral=True)
        
        member = ch.guild.get_member(user.id)
        if member and member in ch.members:
            await member.move_to(None)
            await ctx.response.send_message(f"🚫 {user.mention} طيح من الروم!")
    
    @room.command(name="block", description="🔐 حظر كامل")
    async def block(self, ctx: discord.Interaction, user: discord.User):
        if not ctx.user.voice or not ctx.user.voice.channel:
            return await ctx.response.send_message("❌ أنت ما في روم!", ephemeral=True)
        
        ch = ctx.user.voice.channel
        if not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ ما هاد روم مؤقتة!", ephemeral=True)
        
        if not self.is_owner(ctx.user, ch):
            return await ctx.response.send_message("❌ أنت ما مالك الروم!", ephemeral=True)
        
        cid = str(ch.id)
        self.register_owner(ch, ctx.user)
        
        if user.id in self.data[cid]["blocked"]:
            return await ctx.response.send_message("⚠️ محظور بالفعل", ephemeral=True)
        
        self.data[cid]["blocked"].append(user.id)
        self.save_data()
        
        overwrite = discord.PermissionOverwrite(
            view_channel=False, send_messages=False, connect=False, speak=False
        )
        await ch.set_permissions(user, overwrite=overwrite)
        
        member = ch.guild.get_member(user.id)
        if member and member in ch.members:
            await member.move_to(None)
        
        await ctx.response.send_message(f"🔐 {user.mention} محظور!")
    
    @room.command(name="unblock", description="✅ فك الحظر")
    async def unblock(self, ctx: discord.Interaction, user: discord.User):
        if not ctx.user.voice or not ctx.user.voice.channel:
            return await ctx.response.send_message("❌ أنت ما في روم!", ephemeral=True)
        
        ch = ctx.user.voice.channel
        if not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ ما هاد روم مؤقتة!", ephemeral=True)
        
        if not self.is_owner(ctx.user, ch):
            return await ctx.response.send_message("❌ أنت ما مالك الروم!", ephemeral=True)
        
        cid = str(ch.id)
        if cid not in self.data or user.id not in self.data[cid]["blocked"]:
            return await ctx.response.send_message("⚠️ ما كان محظور", ephemeral=True)
        
        self.data[cid]["blocked"].remove(user.id)
        self.save_data()
        
        await ch.set_permissions(user, overwrite=None)
        await ctx.response.send_message(f"✅ الحظر رفع على {user.mention}!")
    
    @room.command(name="list", description="📋 شوف المحظورين والمكتومين")
    async def list_cmd(self, ctx: discord.Interaction):
        if not ctx.user.voice or not ctx.user.voice.channel:
            return await ctx.response.send_message("❌ أنت ما في روم!", ephemeral=True)
        
        ch = ctx.user.voice.channel
        if not self.is_temp_room(ch):
            return await ctx.response.send_message("❌ ما هاد روم مؤقتة!", ephemeral=True)
        
        if not self.is_owner(ctx.user, ch):
            return await ctx.response.send_message("❌ أنت ما مالك الروم!", ephemeral=True)
        
        cid = str(ch.id)
        if cid not in self.data:
            return await ctx.response.send_message("✅ ما عندك حد!", ephemeral=True)
        
        muted = "\n".join([f"🔇 <@{m}>" for m in self.data[cid]["muted"]]) or "بلا"
        blocked = "\n".join([f"🔐 <@{b}>" for b in self.data[cid]["blocked"]]) or "بلا"
        
        embed = discord.Embed(
            title=f"📋 {ch.name}",
            color=discord.Color.blue()
        )
        embed.add_field(name="🔇 مكتومين", value=muted, inline=False)
        embed.add_field(name="🔐 محظورين", value=blocked, inline=False)
        
        await ctx.response.send_message(embed=embed, ephemeral=True)
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if after.channel and not before.channel:
            ch = after.channel
            cid = str(ch.id)
            
            if cid not in self.data and self.is_temp_room(ch):
                self.register_owner(ch, member)
            
            if cid in self.data and member.id in self.data[cid]["blocked"]:
                try:
                    await member.move_to(None)
                except:
                    pass
            
            if cid in self.data and member.id in self.data[cid]["muted"]:
                try:
                    await member.edit(mute=True)
                except:
                    pass

async def setup(bot):
    await bot.add_cog(TempRoom(bot))
    print("✅ نظام الروم: /room (أمر واحد فقط!)")
