--- orig/AI_Assistant-BOT-main/bot_core.py	2026-08-18 11:08:38.000000000 +0000
+++ AI_Assistant-BOT-main/bot_core.py	2026-08-19 05:56:31.611697669 +0000
@@ -56,14 +56,24 @@
     return f"{int(guild_id or 0)}:{int(user_id)}"
 
 
+# اللغات المقبولة كيجيو من جدول واحد فـ cogs/panel_i18n.py (PANEL_LANGUAGE_MENU).
+# ملي تزيد شي لغة جديدة تما، كتولي مقبولة هنا أوتوماتيكياً بلا ما تبدل هاد الملف.
+# الـ fallback كاين غير إلا تحمل هاد الملف بوحدو بلا مجلد cogs.
+try:
+    from cogs.panel_i18n import LANGUAGES as PANEL_LANGUAGE_CODES
+except Exception as _e:
+    print(f"[PANEL-LANG] ما قدرتش نقرا لائحة اللغات من panel_i18n: {_e}")
+    PANEL_LANGUAGE_CODES = {"darija", "ar", "en", "fr", "es", "it"}
+
+
 def get_panel_language(guild_id: int, user_id: int) -> str:
     lang = str(PANEL_LANGUAGES.get(_panel_lang_key(guild_id, user_id), "darija") or "darija").lower()
-    return lang if lang in {"darija", "en", "fr"} else "darija"
+    return lang if lang in PANEL_LANGUAGE_CODES else "darija"
 
 
 def set_panel_language(guild_id: int, user_id: int, lang: str) -> str:
     lang = str(lang or "darija").lower()
-    if lang not in {"darija", "en", "fr"}:
+    if lang not in PANEL_LANGUAGE_CODES:
         lang = "darija"
     PANEL_LANGUAGES[_panel_lang_key(guild_id, user_id)] = lang
     try:
