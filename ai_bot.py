import os
import discord
import aiohttp
import base64
from discord.ext import commands
from collections import defaultdict

# ═══════════════════════════════════════════════════════
# ║                    CONFIG سهل التعديل                  ║
# ═══════════════════════════════════════════════════════

TARGET_CHANNEL_ID = 1526358328190566420

# ====== GEMINI MODELS ======
# "gemini-2.0-flash" - أقوى + سريع + مجاني ⭐
# "gemini-2.0-flash-lite" - أخف + مجاني
# "gemini-1.5-flash" - قوي + مجاني
# "gemini-1.5-pro" - أقوى (ولكن محدود)
AI_MODEL = "gemini-2.0-flash"  # ← غير هنا!

# ====== API ======
# سجل فـ aistudio.google.com/app/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{AI_MODEL}:generateContent"

MEMORY_SIZE = 50
CREATIVITY = 0.75
MAX_REPLY_LENGTH = 1500

# ═══════════════════════════════════════════════════════

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========== ذاكرة ==========
user_memory = defaultdict(list)
server_memory = []
MAX_SERVER_MEMORY = 100


def get_system_prompt(user_gender="unknown"):
    base_prompt = """أنت واحد الشخص ناضج وذكي وواقعي. كتهضر بالدارجة المغربية.

## قواعدك الأساسية:

1. **اللغة**: رد بالدارجة المغربية، مختصر ومفيد.
   - "واش"، "كيفاش"، "شحال"، "بزاف"، "مزيان"، "صافي"

2. **الأسلوب**:
   - ناضج وجدي، ماشي "برهوش"
   - شوية دعابة خفيفة إلا لقيتي فرصة
   - ما تهدرش بزاف → رد مختصر ومباشر
   - ما تدكرش سميتك ولا شكون أنت

3. **الذكاء**:
   - حلل أي موضوع بـ منطق وواقعية
   - إلا عندك مصدر → قول "حسب..." ولا "من اللي كنعرف..."
   - إلا ما عندكش → قول "ما كنعرفش بالضبط"
   - ما تكذبش وما تبالغش

4. **التصاور (Images)**:
   - إلا بعتولك تصويرة → شوفها وحللها
   - وصف التفاصيل المهمة
   - رد بالدارجة على اللي كتشوف

5. **الواقعية**:
   - كأنك إنسان عادي عندو تجربة
   - تقدر تقول "ما فهمتش" ولا "ما عندي فكرة"
   - ما تتكبرش

6. **الدعابة**: خفيفة وناضجة

7. **الشتائم**: تفهمها بس رد بـ ذكاء ونضج

8. **الذاكرة**: تتذكر المحادثات السابقة مع كل شخص ومع السيرفر كامل

9. **المصادر**: إلا عندك معلومة مؤكدة → ذكر المصدر

10. **ما تدكرش**: ما تقولش "أنا AI" ولا "أنا مساعد" ولا سميتك"""

    if user_gender == "female":
        gender_addition = """

11. **التعامل مع البنات**: محترم وودي، "أختي"، "صاحبتي" (بلا مبالغة)"""
    elif user_gender == "male":
        gender_addition = """

11. **التعامل مع الدراري**: ودي ومباشر، "خويا"، "صاحبي" (بلا مبالغة)"""
    else:
        gender_addition = ""

    return base_prompt + gender_addition


def detect_gender(username: str, display_name: str) -> str:
    name_lower = (username + " " + display_name).lower()
    
    female_signs = ["lina", "sara", "fatima", "khadija", "amina", "nadia", "yasmine", 
                     "imane", "hanae", "salma", "inès", "ines", "maryam", "aya", 
                     "nour", "laila", "rajae", "samira", "fati", "zineb", "asmae",
                     "بنت", "فاطمة", "خديجة", "أمينة", "نادية", "ياسمين", "إيمان",
                     "hana", "chaimae", "souad", "latifa", "meriem", "meryem"]
    
    male_signs = ["mohamed", "ahmed", "youssef", "omar", "karim", "amine", "hassan",
                   "mehdi", "reda", "adil", "khalid", "brahim", "said", "mustapha",
                   "عبد", "محمد", "أحمد", "يوسف", "عمر", "كريم", "أمين", "حسن",
                   "مهدي", "رضا", "عادل", "خالد", "براهيم", "سعيد", "مصطفى"]
    
    for sign in female_signs:
        if sign in name_lower:
            return "female"
    
    for sign in male_signs:
        if sign in name_lower:
            return "male"
    
    return "unknown"


async def ask_ai(user_id: str, username: str, display_name: str, prompt: str, image_url: str = None) -> str:
    headers = {
        "Content-Type": "application/json"
    }
    
    gender = detect_gender(username, display_name)
    system_prompt = get_system_prompt(gender)
    
    # نبني المحتوى
    parts = [{"text": system_prompt + "\n\nالمستخدم: " + prompt}]
    
    # إلا فيه تصويرة
    if image_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as img_resp:
                    if img_resp.status == 200:
                        image_data = await img_resp.read()
                        image_base64 = base64.b64encode(image_data).decode('utf-8')
                        
                        content_type = img_resp.headers.get('Content-Type', 'image/jpeg')
                        
                        parts = [
                            {"text": system_prompt + "\n\nالمستخدم: " + prompt},
                            {
                                "inline_data": {
                                    "mime_type": content_type,
                                    "data": image_base64
                                }
                            }
                        ]
        except:
            pass
    
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": CREATIVITY,
            "maxOutputTokens": MAX_REPLY_LENGTH,
            "topP": 0.9,
            "topK": 40
        }
    }
    
    url = f"{GEMINI_URL}?key={GEMINI_API_KEY}"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    
                    if "candidates" in data and len(data["candidates"]) > 0:
                        candidate = data["candidates"][0]
                        if "content" in candidate and "parts" in candidate["content"]:
                            reply = candidate["content"]["parts"][0]["text"]
                            
                            # حفظ فـ الذاكرة
                            user_memory[user_id].append({"role": "user", "content": prompt})
                            user_memory[user_id].append({"role": "assistant", "content": reply})
                            
                            if len(user_memory[user_id]) > MEMORY_SIZE * 2:
                                user_memory[user_id] = user_memory[user_id][-MEMORY_SIZE * 2:]
                            
                            server_memory.append({"role": "user", "content": f"[{username}]: {prompt}"})
                            server_memory.append({"role": "assistant", "content": reply})
                            
                            if len(server_memory) > MAX_SERVER_MEMORY * 2:
                                server_memory[:] = server_memory[-MAX_SERVER_MEMORY * 2:]
                            
                            return reply
                    
                    return "❌ ما فهمتش الجواب ديال Gemini"
                else:
                    error = await resp.text()
                    return f"❌ Error {resp.status}: {error[:500]}"
    except Exception as e:
        return f"❌ Exception: {str(e)}"


@bot.event
async def on_ready():
    print(f"✅ البوت شغال!")
    print(f"🤖 Model: {AI_MODEL}")
    print(f"📍 Channel: {TARGET_CHANNEL_ID}")
    print(f"🧠 Memory: {MEMORY_SIZE} messages")
    print(f"🌍 Server Memory: {MAX_SERVER_MEMORY}")


@bot.command()
async def chat(ctx, *, message: str):
    user_id = str(ctx.author.id)
    async with ctx.typing():
        response = await ask_ai(user_id, ctx.author.name, ctx.author.display_name, message)
    await ctx.send(response[:MAX_REPLY_LENGTH])


@bot.command()
async def نسيني(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        user_memory[user_id] = []
        await ctx.send("✅ نسيت كلشي! جديد من هنا.")
    else:
        await ctx.send("ما عندي والو ننساه!")


@bot.command()
async def ذاكرة(ctx):
    user_id = str(ctx.author.id)
    count = len(user_memory.get(user_id, [])) // 2
    await ctx.send(f"🧠 عندي {count} رسالة فـ الذاكرة ديالك.")


@bot.command()
async def info(ctx):
    await ctx.send(f"""🤖 **معلومات البوت:**
📍 Channel: `{TARGET_CHANNEL_ID}`
🧠 Memory: `{MEMORY_SIZE}` messages/user
🌍 Server Memory: `{MAX_SERVER_MEMORY}` messages
🎨 Creativity: `{CREATIVITY}`
🤖 Model: `{AI_MODEL}`""")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if message.author.bot:
        return
    
    await bot.process_commands(message)
    
    if message.content.startswith("!"):
        return
    
    if message.channel.id != TARGET_CHANNEL_ID:
        return
    
    user_id = str(message.author.id)
    
    image_url = None
    if message.attachments:
        for att in message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                image_url = att.url
                break
    
    async with message.channel.typing():
        response = await ask_ai(
            user_id, 
            message.author.name, 
            message.author.display_name, 
            message.content,
            image_url
        )
    
    await message.reply(response[:MAX_REPLY_LENGTH], mention_author=False)


if __name__ == "__main__":
    if not DISCORD_TOKEN or not GEMINI_API_KEY:
        print("❌ Missing tokens! Check Railway Variables.")
    else:
        bot.run(DISCORD_TOKEN)
