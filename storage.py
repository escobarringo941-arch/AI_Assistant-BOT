# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════
║   storage.py — helpers ديال JSON (مشتركين بين الـ Cogs) ║
═══════════════════════════════════════════════════════

فـ ai_bot.py عندك ~24 مرة نفس الكود مكرر:
    def load_xxx(): ... try/except ... json.load ...
    def save_xxx(): ... json.dump ...

هنا كتبناه **مرة وحدة**. أي cog جديد كيستعمل غير:
    from storage import JsonStore
    db = JsonStore("economy.json", default={})

⚠️ زيادة مهمة: الكتابة كتدار بـ "atomic write" (كيكتب فـ ملف مؤقت
   من بعد كيبدّلو). هادشي كيمنع فساد الملف إلا طاح Railway فوسط الكتابة —
   مشكل حقيقي كيوقع مع الملفات ديالك الحالية.
"""

import os
import json
import tempfile
from typing import Any

from games_config import DATA_DIR

os.makedirs(DATA_DIR, exist_ok=True)


class JsonStore:
    """طبقة تخزين بسيطة على ملف JSON واحد.

    الاستعمال:
        db = JsonStore("economy.json", default={})
        db.data["123"] = {"coins": 50}
        db.save()
    """

    def __init__(self, filename: str, default: Any = None):
        self.path = os.path.join(DATA_DIR, filename)
        self.default = default if default is not None else {}
        self.data = self.load()

    def load(self) -> Any:
        if not os.path.exists(self.path):
            return json.loads(json.dumps(self.default))  # نسخة عميقة
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"[STORAGE] ⚠️ {self.path} فاسد ({e}) — كنبداو من الصفر.")
            # كنحتافظو بالملف الفاسد باش تقدر تشوفو من بعد
            try:
                os.rename(self.path, self.path + ".corrupted")
            except OSError:
                pass
            return json.loads(json.dumps(self.default))
        except Exception as e:
            print(f"[STORAGE] ❌ خطأ فـ قراءة {self.path}: {e}")
            return json.loads(json.dumps(self.default))

    def save(self) -> bool:
        """كتابة ذرية (atomic) — إما تكتب كاملة ولا ما تكتب والو."""
        try:
            directory = os.path.dirname(self.path)
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=directory, delete=False, suffix=".tmp"
            ) as tmp:
                json.dump(self.data, tmp, ensure_ascii=False, indent=2)
                tmp_path = tmp.name
            os.replace(tmp_path, self.path)
            return True
        except Exception as e:
            print(f"[STORAGE] ❌ خطأ فـ حفظ {self.path}: {e}")
            return False

    # ═══════ اختصارات ═══════

    def guild(self, guild_id: int) -> dict:
        """كترجع (وكتصاوب إلا ماكانتش) الخانة ديال سيرفر معيّن."""
        return self.data.setdefault(str(guild_id), {})

    def user(self, guild_id: int, user_id: int, default: dict = None) -> dict:
        """كترجع (وكتصاوب إلا ماكانتش) الخانة ديال عضو معيّن."""
        g = self.guild(guild_id)
        return g.setdefault(str(user_id), dict(default or {}))


def load_bank(filename: str, default=None):
    """كتقرا ملف من مجلد banks/ (كلمات، ألغاز...) — read-only."""
    from games_config import BANKS_DIR
    path = os.path.join(BANKS_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[BANKS] ⚠️ ماكاينش الملف: {path}")
        return default if default is not None else []
    except Exception as e:
        print(f"[BANKS] ❌ خطأ فـ قراءة {path}: {e}")
        return default if default is not None else []
