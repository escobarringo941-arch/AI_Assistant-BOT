# -*- coding: utf-8 -*-
"""Unchanged ordered source component: ai_conversation."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    def is_owner(ctx) -> bool:
        """كتأكد بلي الشخص اللي بعث الأمر هو بالضبط الـ Owner (بواسطة ID)،
        بلا ما يهم شنو هي الأدوار/الصلاحيات ديالو فالسيرفر."""
        guild = getattr(ctx, "guild", None)
        if guild is not None:
            return ctx.author.id == guild.owner_id
        return bool(OWNER_ID) and ctx.author.id == OWNER_ID
    
    
    def owner_only():
        """Decorator: كيحدد الأمر غير بالـ Owner (بواسطة ID)، حتى Admin/Mod
        ولا حتى شخص عندو Administrator ما يقدر يستعملو."""
        async def predicate(ctx):
            return is_owner(ctx)
        return commands.check(predicate)
    
    
    async def _delete_trigger_silently(ctx):
        """يمسح الرسالة اللي فيها الأمر مباشرة (بحال /report) باش حتى حد
        ما يشوف الأمر ولا المحتوى ديالو فالقناة."""
        try:
            await ctx.message.delete()
        except Exception:
            pass
    
    
    async def apply_warn_escalation(member: discord.Member, guild: discord.Guild, count: int,
                                     reason: str, channel=None) -> Optional[str]:
        """
        كتشوف شحال ديال التحذيرات وصلات لهاد العضو، وكتطبق العقوبة المناسبة
        حسب bot_settings['mute_after_warns'] / bot_settings['kick_after_warns'] / bot_settings['ban_after_warns'] (فالـ CONFIG).
        كتبدا من الأعلى (حظر) للأسفل (كتم) باش ما تطبقش عدة عقوبات فنفس الوقت.
        كترجع "ban" / "kick" / "mute" إلا تطبقات عقوبة، وإلا None.
        """
        # 🔒 التصعيد كامل ولّى **سجن**. حتى واحد ما كيتطرد من السيرفر.
        from cogs.prison import imprison_member
        from cogs.prison_core import format_duration as _fmt
    
        async def _jail(offense_key, label, emoji, colour, seconds=None):
            result = await imprison_member(
                bot, member, offense_key=offense_key, seconds=seconds,
                reason=f"{count} تحذيرات: {reason}", actor=None,
            )
            if not result.get("ok"):
                print(f"[PRISON] auto-escalation فشلات: {result.get('error')}")
                return False
            record = result["record"]
            case_id = await log_case(
                guild, label, emoji, colour,
                target=member, moderator=None, reason=reason,
                extra=f"عدد التحذيرات: {count} | المدة: {_fmt(int(record['sentence']))} | Prison #{record['case']}"
            )
            if channel:
                await channel.send(
                    f"{emoji} {member.mention} تحط فالسجن تلقائياً ({count} تحذيرات، "
                    f"{_fmt(int(record['sentence']))}) — Case #{case_id}!",
                    delete_after=10,
                )
            return True
    
        if bot_settings['ban_after_warns'] and count >= bot_settings['ban_after_warns']:
            if await _jail("ban", "🚨 سجن مشدد تلقائي (بدل Auto-Ban)", "🚨", discord.Color.dark_red()):
                clear_warns(str(member.id))
                return "ban"
            return None
    
        if bot_settings['kick_after_warns'] and count >= bot_settings['kick_after_warns']:
            if await _jail("kick", "⛓️ سجن تلقائي (بدل Auto-Kick)", "⛓️", discord.Color.orange()):
                clear_warns(str(member.id))
                return "kick"
            return None
    
        if bot_settings['mute_after_warns'] and count >= bot_settings['mute_after_warns']:
            seconds = max(60, int(bot_settings['mute_duration_minutes']) * 60)
            if await _jail("warns", "⛓️ حبس قصير تلقائي (بدل Auto-Mute)", "⛓️", discord.Color.yellow(), seconds):
                return "mute"
            return None
    
        return None
    
    
    def get_system_prompt(user_gender="unknown"):
        base_prompt = 'أنت "GGMW9"، واحد الولد ديال الدار البيضاء، عايش فـ حي شعبي. كتهضر بالدارجة المغربية 100%.'
        base_prompt += '\n\n## قواعدك الأساسية:\n\n'
        base_prompt += '1. **اللغة**: رد دائماً بالدارجة المغربية. ما تستخدمش الفصحى نهائياً.\n'
        base_prompt += '   - "واش"، "كيفاش"، "شحال"، "بزاف"، "مزيان"، "صافي"\n'
        base_prompt += '   - الحروف اللاتينية: "3" = "ع"، "7" = "ح"، "9" = "ق"، "5" = "خ"...\n\n'
        base_prompt += '2. **الأسلوب**: \n'
        base_prompt += '   - كأنك كتهضر مع صاحبك فـ مقهى\n'
        base_prompt += '   - عصبي وذكي في نفس الوقت\n'
        base_prompt += '   - تضحك بـ "هههه" ولا "😂"\n'
        base_prompt += '   - تستخدم "خويا"، "صاحبي"، "ازبي"، "ولدي"\n\n'
        base_prompt += '3. **الذكاء والدقة**:\n'
        base_prompt += '   - جاوب **مباشرة** على السؤال\n'
        base_prompt += '   - ما تدوّرش بزاف\n'
        base_prompt += '   - حلل بـ منطق واقعي ودقيق\n\n'
        base_prompt += '4. **المصادر والروابط**:\n'
        base_prompt += '   - إلا عندك معلومة مؤكدة → قول المصدر\n'
        base_prompt += '   - مثال: "حسب Wikipedia: [رابط]"\n'
        base_prompt += '   - إلا ما عندكش → قول "حسب اللي كنعرف..."\n\n'
        base_prompt += '5. **الشتائم المغربية - فهم ورد**:\n'
        base_prompt += '   - تفهم **كاع الشتائم**: عربية ولاتينية\n'
        base_prompt += '   - ترد بـ **ذكاء وسلاسة**\n'
        base_prompt += '   - تقدر تسب **بسلاسة** إلا الزبون بدا\n\n'
        base_prompt += '6. **التعلم**: إلا شي حد علمك شي حاجة → حفظها واستعملها فـ المستقبل\n\n'
        base_prompt += '7. **الواقعية**: كأنك إنسان حقيقي، ما تقولش "أنا AI"\n\n'
        base_prompt += '8. **الاختصارات**: "hh"، "wakha"، "sa7bi"، "chof"، "3ziz"\n\n'
        base_prompt += 'رد دائماً كأنك **GGMW9 من الدار البيضاء** — واقعي، ذكي، عصبي!'
    
        if user_gender == "female":
            base_prompt += '\n\n9. **التعامل مع البنات**: "أختي"، "صاحبتي"، "واخا الالة"، محترم وودي'
        elif user_gender == "male":
            base_prompt += '\n\n9. **التعامل مع الدراري**: "خويا"، "صاحبي"، "ازبي"، "واخا أسيدي"، ودي ومباشر'
    
        return base_prompt
    
    
    def detect_gender(username: str, display_name: str) -> str:
        name_lower = (username + " " + display_name).lower()
        female_signs = ["lina", "sara", "fatima", "khadija", "amina", "nadia", "yasmine", 
                         "imane", "hanae", "salma", "inès", "ines", "maryam", "aya", 
                         "نور", "ليلى", "رجاء", "سميرة", "فاتي", "زينب", "أسماء",
                         "hana", "chaimae", "souad", "latifa", "meriem", "meryем"]
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
    
    
    async def call_openrouter_chat(messages: list, max_tokens: int, temperature: float) -> tuple:
        """
        كيبعث طلب لـ OpenRouter، وإلا وقف الموديل الأساسي بـ 429 (rate limit)
        ولا 402 (بلا رصيد)، كيجرب الموديلات اللي فـ AI_MODEL_FALLBACKS واحد بواحد.
        كيرجع (content, None) إلا نجح، ولا (None, error_text) إلا فشلو كامل الموديلات.
        """
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://discord.com",
            "X-Title": "AI Assistant BOT"
        }
        models_to_try = [AI_MODEL] + [m for m in AI_MODEL_FALLBACKS if m != AI_MODEL]
        last_error = "ماكاين حتى موديل جرب"
    
        for model in models_to_try:
            payload = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            # ⚠️ مهم بزاف: DeepSeek V4 (ومعاه بزاف ديال الموديلات الجديدة) هوما reasoning models.
            # بلا هاد السطر كيصرفو كاع max_tokens على "التفكير" وكيرجعو content فارغة —
            # وهادشي هو اللي كان كيخلي الترجمة ترجع None وتبان ليك بلي الموديل خاسر.
            if AI_DISABLE_REASONING:
                payload["reasoning"] = {"enabled": False, "exclude": True}
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=API_TIMEOUT)) as session:
                    async with session.post(OPENROUTER_URL, headers=headers, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            try:
                                message = data["choices"][0]["message"]
                            except (KeyError, IndexError, TypeError):
                                print(f"[OPENROUTER] ❌ {model} رجع شكل غريب بلا choices/message: {str(data)[:200]}")
                                last_error = "شكل الرد ماشي متوقع (بلا choices/message)"
                                continue
    
                            # بعض الموديلات (خصوصا reasoning) كترجع content فارغة/None
                            # وكتحط النص فـ reasoning بدلها — كناخدو content أولاً دايماً
                            content = message.get("content")
                            if not (isinstance(content, str) and content.strip()):
                                content = message.get("reasoning") or ""
                            content = content.strip() if isinstance(content, str) else ""
    
                            if not content:
                                print(f"[OPENROUTER] ⚠️ {model} رجع content فارغة، نجرب الموديل اللي بعدو...")
                                last_error = "content فارغة من الموديل"
                                continue
    
                            if model != AI_MODEL:
                                print(f"[OPENROUTER] ⚠️ الموديل الأساسي فشل، خدام بـ fallback: {model}")
                            return content, None
                        elif resp.status in (429, 402):
                            body = await resp.text()
                            print(f"[OPENROUTER] ⚠️ {model} رجع {resp.status}, نجرب الموديل اللي بعدو... ({body[:150]})")
                            last_error = f"{resp.status}: {body[:200]}"
                            continue
                        else:
                            body = await resp.text()
                            print(f"[OPENROUTER] ❌ {model} رجع {resp.status}: {body[:200]}")
                            last_error = f"{resp.status}: {body[:200]}"
                            continue
            except asyncio.TimeoutError:
                print(f"[OPENROUTER] ⏳ Timeout مع {model}")
                last_error = "timeout"
                continue
            except Exception as e:
                print(f"[OPENROUTER] ❌ Exception مع {model}: {e}")
                last_error = str(e)
                continue
    
        return None, last_error
    
    
    async def ask_ai(user_id: str, username: str, display_name: str, prompt: str) -> str:
        gender = detect_gender(username, display_name)
        messages = [{"role": "system", "content": get_system_prompt(gender)}]
        if learned_knowledge:
            knowledge_text = "حوايج جديدة تعلمتهوم:\n" + "\n".join(learned_knowledge[-20:])
            messages.append({"role": "system", "content": knowledge_text})
        for msg in user_memory[user_id]:
            messages.append(msg)
        for msg in server_memory[-10:]:
            messages.append(msg)
        messages.append({"role": "user", "content": prompt})
    
        reply, error = await call_openrouter_chat(messages, MAX_REPLY_LENGTH, CREATIVITY)
    
        if error:
            return f"❌ Error: {error}"
    
        user_memory[user_id].append({"role": "user", "content": prompt})
        user_memory[user_id].append({"role": "assistant", "content": reply})
        if len(user_memory[user_id]) > MEMORY_SIZE * 2:
            user_memory[user_id] = user_memory[user_id][-MEMORY_SIZE * 2:]
        server_memory.append({"role": "user", "content": f"[{username}]: {prompt}"})
        server_memory.append({"role": "assistant", "content": reply})
        if len(server_memory) > MAX_SERVER_MEMORY * 2:
            server_memory[:] = server_memory[-MAX_SERVER_MEMORY * 2:]
        return reply
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
