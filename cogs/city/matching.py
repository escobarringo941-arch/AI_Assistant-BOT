# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from .careers import CAREERS, SKILLS, career_name

KEYWORDS = {
    "design": ["design","designer","photoshop","canva","تصميم","مصمم","ديزاين"],
    "beauty": ["makeup","ميكاب","beauty","cosmetic","مكياج"],
    "fashion": ["fashion","style","outfit","ستايل","موضة","لباس"],
    "tech": ["tech","computer","pc","windows","linux","code","برمجة","حاسوب","تقنية"],
    "gaming": ["gaming","game","games","لعب","العاب","ألعاب"],
    "music": ["music","dj","playlist","موسيقى"],
    "hosting": ["host","present","event","تنشيط","تقديم","فعالية"],
    "content": ["content","tiktok","instagram","copy","محتوى","كتابة"],
    "photo": ["photo","camera","photography","تصوير","كاميرا"],
    "sales": ["sales","sell","marketing","بيع","تسويق","اقناع","إقناع"],
    "finance": ["finance","bank","accounting","مال","بنك","حسابات"],
    "organization": ["organize","delivery","logistic","تنظيم","توصيل","لوجستيك"],
    "repair": ["repair","mechanic","fix","تصليح","ميكانيك","إصلاح"],
    "communication": ["people","talk","communicate","ناس","تواصل","نهضر"],
    "customer": ["customer","client","زبون","زبناء","خدمة الناس"],
    "creativity": ["creative","ideas","ابداع","إبداع","أفكار"],
    "problem_solving": ["solve","problem","حل","مشاكل"],
    "leadership": ["manage","leader","manager","تسيير","قيادة","مدير"],
}


def inferred_skills(free_text: str) -> set[str]:
    text = (free_text or "").lower()
    found = set()
    for skill, words in KEYWORDS.items():
        if any(w.lower() in text for w in words):
            found.add(skill)
    return found


def match_careers(cv: dict, lang: str = "darija", limit: int = 5) -> list[dict]:
    declared = set(cv.get("skills") or [])
    inferred = inferred_skills(cv.get("about", ""))
    all_skills = declared | inferred
    style = str(cv.get("work_style") or "flexible")
    availability = str(cv.get("availability") or "flexible")
    preferred_sector = str(cv.get("preferred_sector") or "")
    experience = max(0, min(5, int(cv.get("experience", 0) or 0)))

    results = []
    for cid, c in CAREERS.items():
        weights = c.get("skills", {})
        max_skill = max(1, sum(int(v) for v in weights.values()))
        skill_points = sum(int(weights.get(s, 0)) for s in all_skills)
        score = 48.0 * min(1.0, skill_points / max_skill)

        styles = c.get("styles", {})
        if style in styles:
            score += 15
        elif style == "flexible":
            score += 8

        if preferred_sector and preferred_sector == c.get("sector"):
            score += 12

        # Availability doesn't reject a person; it only nudges the match.
        work_days = set(c.get("work_days") or [])
        if availability == "weekends" and work_days.intersection({5, 6}):
            score += 8
        elif availability == "weekdays" and work_days.intersection({0,1,2,3,4}):
            score += 8
        elif availability in {"flexible", "evenings"}:
            score += 5

        score += min(10, experience * 2)
        score += min(7, len(inferred.intersection(weights)) * 2)
        score = max(20, min(99, round(score)))

        matched = sorted(all_skills.intersection(weights), key=lambda s: weights.get(s,0), reverse=True)[:3]
        if lang == "en":
            reasons = [SKILLS[s]["en"] for s in matched] or ["Your preferences"]
        elif lang == "fr":
            reasons = [SKILLS[s]["fr"] for s in matched] or ["Tes préférences"]
        else:
            reasons = [SKILLS[s]["darija"] for s in matched] or ["التفضيلات ديالك"]

        results.append({
            "career_id": cid,
            "score": score,
            "name": career_name(cid, lang),
            "emoji": c.get("emoji", "💼"),
            "reasons": reasons,
        })

    results.sort(key=lambda r: (-r["score"], r["career_id"]))
    return results[:max(1, int(limit))]
