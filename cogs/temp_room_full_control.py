# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════
║ 🎤 نظام إدارة كامل Temp Rooms — صاحب الروم = الملك الحقيقي    ║
═══════════════════════════════════════════════════════════════════

الميزات:
 🔇 MUTE        — كتم الصوت (يشوف بلا يتكلم)
 🚫 KICK        — طيح من الروم (مؤقتاً)
 🔐 BLOCK       — حظر كامل (نهائي)
 ✅ UNMUTE      — فك الكتم
 ✅ UNBLOCK     — فك الحظر

الصلاحيات:
 ✅ فقط صاحب الروم يقدر يستعمل هاد الأوامر
 ✅ حتى Admin/Mod ما عندهم قوة
 ✅ صلاحيات الـ Roles = بلا فائدة
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from datetime import datetime
import json
import os

# ═══════════════════════════════════════════════════════════════════
# ║  نظام الإدارة الكاملة                                           ║
# ═══════════════════════════════════════════════════════════════════

class TempRoomFullControl(commands.Cog):
    """نظام إدارة كامل للروم المؤقتة"""
    
    def __init__(self, bot):
        self.bot = bot
        self.room_data = {}  # {channel_id: {"owner_id": int, "muted": [int], "blocked": [int]}}
        self.load_room_data()
    
    def load_room_data(self):
        """تحميل بيانات الروم"""
        os.makedirs("data", exist_ok=True)
        filepath = "data/temp_room_control.json"
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    self.room_data = json.load(f)
            except:
                self.room_data = {}
    
    def save_room_data(self):
        """حفظ بيانات الروم"""
        os.makedirs("data", exist_ok=True)
        with open("data/temp_room_control.json", "w", encoding="utf-8") as f:
            json.dump(self.room_data, f, ensure_ascii=False, indent=2)
    
    def is_temp_room(self, channel: discord.VoiceChannel) -> bool:
        """هل هاد روم مؤقتة؟"""
        if not channel or not channel.category:
            return False
        
        category_name = channel.category.name.lower()
        return "🎤" in channel.category.name or "temp" in category_name or "مؤقت" in category_name
    
    def is_room_owner(self, member: discord.Member, channel: discord.VoiceChannel) -> bool:
        """هل هاد الشخص مالك الروم؟"""
        channel_id = str(channel.id)
        
        if channel_id in self.room_data:
            return self.room_data[channel_id].get("owner_id") == member.id
        
        try:
            perms = channel.permissions_for(member)
            return perms.manage_channels or perms.administrator
        except:
            return False
    
    def register_room_owner(self, channel: discord.VoiceChannel, owner: discord.Member):
        """تسجيل مالك الروم"""
        channel_id = str(channel.id)
        if channel_id not in self.room_data:
            self.room_data[channel_id] = {
                "owner_id": owner.id,
                "owner_name": owner.name,
                "created_at": str(datetime.now()),
                "muted": [],
                "blocked": []
            }
            self.save_room_data()
    
    # ═══════════════════════════════════════════════════════════════
    # ║  أمر MUTE (كتم الصوت)                                      ║
    # ═══════════════════════════════════════════════════════════════
    
    @app_commands.command(
        name="room_mute",
        description="🔇 كتم الصوت — الشخص يشوف بلا يتكلم"
    )
    @app_commands.describe(
        user="الشخص اللي بغيتي تكتمو (أي حد حتى Admin!)"
    )
    async def room_mute(self, interaction: discord.Interaction, user: discord.User):
        """كتم الصوت (الشخص يشوف الروم لكن ما يتكلم)"""
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ انت ما انت فـ روم فويس!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if not self.is_temp_room(channel):
            return await interaction.response.send_message(
                "❌ هاد ماشي روم مؤقتة!",
                ephemeral=True
            )
        
        if not self.is_room_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "❌ انت ما انت مالك هاد الروم!",
                ephemeral=True
            )
        
        channel_id = str(channel.id)
        
        if channel_id not in self.room_data:
            self.register_room_owner(channel, interaction.user)
        
        if user.id in self.room_data[channel_id]["muted"]:
            return await interaction.response.send_message(
                f"⚠️ {user.mention} مكتوم بالفعل",
                ephemeral=True
            )
        
        self.room_data[channel_id]["muted"].append(user.id)
        self.save_room_data()
        
        # تطبيق الكتم
        guild = channel.guild
        member = guild.get_member(user.id)
        if member:
            try:
                # كتم صوت الشخص بالقوة
                await member.edit(mute=True, reason=f"Muted by {interaction.user.name} (room owner)")
                
                await interaction.response.send_message(
                    f"🔇 **{user.mention} مكتوم!**\n"
                    f"📌 يقدر يشوف و يقرا لكن ما يقدرش يتكلم\n"
                    f"🔓 فقط مالك الروم يقدر يفك الكتم"
                )
                
                # رسالة DM
                try:
                    await user.send(
                        f"🔇 **تم كتم صوتك** فـ {channel.mention}\n"
                        f"👤 من قبل: {interaction.user.mention}\n"
                        f"📌 انت ما تقدرش تتكلم لكن تقدر تشوف\n"
                        f"🔓 اتكلم مع مالك الروم باش يفك الكتم"
                    )
                except:
                    pass
                
            except Exception as e:
                await interaction.response.send_message(f"❌ خطأ فـ الكتم: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما لقيتش هاد الشخص فـ الروم", ephemeral=True)
    
    # ═══════════════════════════════════════════════════════════════
    # ║  أمر UNMUTE (فك الكتم)                                     ║
    # ═══════════════════════════════════════════════════════════════
    
    @app_commands.command(
        name="room_unmute",
        description="🔊 فك الكتم"
    )
    @app_commands.describe(
        user="الشخص"
    )
    async def room_unmute(self, interaction: discord.Interaction, user: discord.User):
        """فك الكتم"""
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ انت ما انت فـ روم فويس!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if not self.is_temp_room(channel):
            return await interaction.response.send_message(
                "❌ هاد ماشي روم مؤقتة!",
                ephemeral=True
            )
        
        if not self.is_room_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "❌ انت ما انت مالك هاد الروم!",
                ephemeral=True
            )
        
        channel_id = str(channel.id)
        
        if channel_id not in self.room_data or user.id not in self.room_data[channel_id]["muted"]:
            return await interaction.response.send_message(
                f"⚠️ {user.mention} ما كان مكتوم",
                ephemeral=True
            )
        
        self.room_data[channel_id]["muted"].remove(user.id)
        self.save_room_data()
        
        # فك الكتم
        guild = channel.guild
        member = guild.get_member(user.id)
        if member:
            try:
                await member.edit(mute=False)
                await interaction.response.send_message(f"🔊 الكتم رفع على {user.mention}! يقدر يتكلم الآن")
            except:
                pass
    
    # ═══════════════════════════════════════════════════════════════
    # ║  أمر KICK (طيح من الروم)                                   ║
    # ═══════════════════════════════════════════════════════════════
    
    @app_commands.command(
        name="room_kick",
        description="🚫 طيح من الروم (مؤقتاً)"
    )
    @app_commands.describe(
        user="الشخص اللي بغيتي تطيحو (أي حد حتى Admin!)"
    )
    async def room_kick(self, interaction: discord.Interaction, user: discord.User):
        """طيح من الروم (يقدر يدخل تاني)"""
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ انت ما انت فـ روم فويس!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if not self.is_temp_room(channel):
            return await interaction.response.send_message(
                "❌ هاد ماشي روم مؤقتة!",
                ephemeral=True
            )
        
        if not self.is_room_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "❌ انت ما انت مالك هاد الروم!",
                ephemeral=True
            )
        
        guild = channel.guild
        member = guild.get_member(user.id)
        
        if member and member in channel.members:
            try:
                await member.move_to(None)
                
                await interaction.response.send_message(
                    f"🚫 **{user.mention} طيح من الروم!**\n"
                    f"📌 يقدر يدخل تاني (بخلاف الحظر)"
                )
                
                try:
                    await user.send(
                        f"🚫 **تم طيحك من** {channel.mention}\n"
                        f"👤 من قبل: {interaction.user.mention}\n"
                        f"📌 انت يقدرك تدخل تاني لكن احترم الحدود!"
                    )
                except:
                    pass
                
            except Exception as e:
                await interaction.response.send_message(f"❌ خطأ: {e}", ephemeral=True)
        else:
            await interaction.response.send_message("❌ ما لقيتش هاد الشخص فـ الروم", ephemeral=True)
    
    # ═══════════════════════════════════════════════════════════════
    # ║  أمر BLOCK (حظر كامل)                                      ║
    # ═══════════════════════════════════════════════════════════════
    
    @app_commands.command(
        name="room_block",
        description="🔐 حظر كامل (بلا دخول نهائياً)"
    )
    @app_commands.describe(
        user="الشخص اللي بغيتي تحظريه (أي حد حتى Admin!)"
    )
    async def room_block(self, interaction: discord.Interaction, user: discord.User):
        """حظر كامل (بلا دخول نهائياً)"""
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ انت ما انت فـ روم فويس!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if not self.is_temp_room(channel):
            return await interaction.response.send_message(
                "❌ هاد ماشي روم مؤقتة!",
                ephemeral=True
            )
        
        if not self.is_room_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "❌ انت ما انت مالك هاد الروم!",
                ephemeral=True
            )
        
        channel_id = str(channel.id)
        
        if channel_id not in self.room_data:
            self.register_room_owner(channel, interaction.user)
        
        if user.id in self.room_data[channel_id]["blocked"]:
            return await interaction.response.send_message(
                f"⚠️ {user.mention} محظور بالفعل",
                ephemeral=True
            )
        
        self.room_data[channel_id]["blocked"].append(user.id)
        self.save_room_data()
        
        # تطبيق الحظر المطلق
        await self._apply_absolute_block(channel, user)
        
        guild = channel.guild
        member = guild.get_member(user.id)
        if member and member in channel.members:
            try:
                await member.move_to(None)
            except:
                pass
        
        await interaction.response.send_message(
            f"🔐 **{user.mention} محظور حظر كامل!**\n"
            f"📌 بلا دخول، بلا صوت، بلا كتابة\n"
            f"🔒 حتى Admin/Mod ما يقدرو يتجاوز هاد الحظر"
        )
        
        try:
            await user.send(
                f"🔐 **أنت محظور بشكل كامل** من {channel.mention}\n"
                f"👤 من قبل: {interaction.user.mention}\n"
                f"🚫 بلا دخول، بلا صوت، بلا كتابة\n"
                f"⏳ الحظر مطلق حتى يرفعوه عنك"
            )
        except:
            pass
    
    # ═══════════════════════════════════════════════════════════════
    # ║  أمر UNBLOCK (فك الحظر)                                    ║
    # ═══════════════════════════════════════════════════════════════
    
    @app_commands.command(
        name="room_unblock",
        description="✅ فك الحظر"
    )
    @app_commands.describe(
        user="الشخص"
    )
    async def room_unblock(self, interaction: discord.Interaction, user: discord.User):
        """فك الحظر"""
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ انت ما انت فـ روم فويس!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if not self.is_temp_room(channel):
            return await interaction.response.send_message(
                "❌ هاد ماشي روم مؤقتة!",
                ephemeral=True
            )
        
        if not self.is_room_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "❌ انت ما انت مالك هاد الروم!",
                ephemeral=True
            )
        
        channel_id = str(channel.id)
        
        if channel_id not in self.room_data or user.id not in self.room_data[channel_id]["blocked"]:
            return await interaction.response.send_message(
                f"⚠️ {user.mention} ما كان محظور",
                ephemeral=True
            )
        
        self.room_data[channel_id]["blocked"].remove(user.id)
        self.save_room_data()
        
        # فك الحظر
        await self._remove_absolute_block(channel, user)
        
        await interaction.response.send_message(f"✅ الحظر رفع على {user.mention}! يقدر يدخل الآن")
    
    # ═══════════════════════════════════════════════════════════════
    # ║  أوامر العرض (Lists)                                       ║
    # ═══════════════════════════════════════════════════════════════
    
    @app_commands.command(
        name="room_mutelist",
        description="🔇 شوف قائمة المكتومين"
    )
    async def room_mutelist(self, interaction: discord.Interaction):
        """عرض المكتومين"""
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ انت ما انت فـ روم فويس!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if not self.is_temp_room(channel):
            return await interaction.response.send_message(
                "❌ هاد ماشي روم مؤقتة!",
                ephemeral=True
            )
        
        if not self.is_room_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "❌ انت ما انت مالك هاد الروم!",
                ephemeral=True
            )
        
        channel_id = str(channel.id)
        
        if channel_id not in self.room_data or not self.room_data[channel_id]["muted"]:
            return await interaction.response.send_message(
                "✅ ما عندك حد مكتوم",
                ephemeral=True
            )
        
        guild = channel.guild
        muted_list = []
        
        for muted_id in self.room_data[channel_id]["muted"]:
            try:
                member = await guild.fetch_member(muted_id)
                muted_list.append(f"🔇 {member.mention}")
            except:
                muted_list.append(f"🔇 `{muted_id}`")
        
        embed = discord.Embed(
            title=f"🔇 المكتومين من {channel.name}",
            description="\n".join(muted_list),
            color=discord.Color.yellow()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(
        name="room_blocklist",
        description="🔐 شوف قائمة المحظورين"
    )
    async def room_blocklist(self, interaction: discord.Interaction):
        """عرض المحظورين"""
        
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "❌ انت ما انت فـ روم فويس!",
                ephemeral=True
            )
        
        channel = interaction.user.voice.channel
        
        if not self.is_temp_room(channel):
            return await interaction.response.send_message(
                "❌ هاد ماشي روم مؤقتة!",
                ephemeral=True
            )
        
        if not self.is_room_owner(interaction.user, channel):
            return await interaction.response.send_message(
                "❌ انت ما انت مالك هاد الروم!",
                ephemeral=True
            )
        
        channel_id = str(channel.id)
        
        if channel_id not in self.room_data or not self.room_data[channel_id]["blocked"]:
            return await interaction.response.send_message(
                "✅ ما عندك حد محظور",
                ephemeral=True
            )
        
        guild = channel.guild
        blocked_list = []
        
        for blocked_id in self.room_data[channel_id]["blocked"]:
            try:
                member = await guild.fetch_member(blocked_id)
                blocked_list.append(f"🔐 {member.mention}")
            except:
                blocked_list.append(f"🔐 `{blocked_id}`")
        
        embed = discord.Embed(
            title=f"🔐 المحظورين من {channel.name}",
            description="\n".join(blocked_list),
            color=discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # ═══════════════════════════════════════════════════════════════
    # ║  دوال مساعدة                                                ║
    # ═══════════════════════════════════════════════════════════════
    
    async def _apply_absolute_block(self, channel: discord.VoiceChannel, user: discord.User):
        """تطبيق الحظر المطلق"""
        try:
            overwrite = discord.PermissionOverwrite(
                view_channel=False,
                send_messages=False,
                connect=False,
                speak=False,
                stream=False,
                read_message_history=False
            )
            
            await channel.set_permissions(user, overwrite=overwrite)
        except Exception as e:
            print(f"[ROOM BLOCK] خطأ: {e}")
    
    async def _remove_absolute_block(self, channel: discord.VoiceChannel, user: discord.User):
        """فك الحظر المطلق"""
        try:
            await channel.set_permissions(user, overwrite=None)
        except Exception as e:
            print(f"[ROOM UNBLOCK] خطأ: {e}")
    
    # ═══════════════════════════════════════════════════════════════
    # ║  الحماية التلقائية                                          ║
    # ═══════════════════════════════════════════════════════════════
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """تفقد عند الدخول و المحاولة"""
        
        # إذا الشخص دخل روم جديد
        if after.channel and not before.channel:
            channel = after.channel
            channel_id = str(channel.id)
            
            if self.is_temp_room(channel) and channel_id not in self.room_data:
                self.register_room_owner(channel, member)
            
            # التفقد من البلوكليست
            if channel_id in self.room_data and member.id in self.room_data[channel_id]["blocked"]:
                try:
                    await member.move_to(None)
                    
                    try:
                        owner_id = self.room_data[channel_id]["owner_id"]
                        owner = channel.guild.get_member(owner_id)
                        owner_name = owner.mention if owner else "مالك الروم"
                        
                        await member.send(
                            f"🔐 **أنت محظور من** {channel.mention}\n"
                            f"👤 من قبل: {owner_name}\n"
                            f"🔒 الحظر مطلق"
                        )
                    except:
                        pass
                except:
                    pass
            
            # التفقد من قائمة الكتم
            if channel_id in self.room_data and member.id in self.room_data[channel_id]["muted"]:
                try:
                    await member.edit(mute=True)
                except:
                    pass
        
        # إذا الشخص حاول يتكلم و مكتوم
        if after.channel and not after.self_mute and before.self_mute != after.self_mute:
            channel = after.channel
            channel_id = str(channel.id)
            
            if self.is_temp_room(channel) and channel_id in self.room_data:
                if member.id in self.room_data[channel_id]["muted"]:
                    try:
                        await member.edit(mute=True)
                    except:
                        pass


# ═══════════════════════════════════════════════════════════════════
# ║  تحميل الـ Cog                                                  ║
# ═══════════════════════════════════════════════════════════════════

async def setup(bot: commands.Bot):
    """تحميل الـ Cog"""
    await bot.add_cog(TempRoomFullControl(bot))
    print("✅ نظام الإدارة الكامل للروم محمّل! (Mute/Kick/Block)")
