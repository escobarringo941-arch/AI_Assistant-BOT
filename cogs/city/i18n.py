# -*- coding: utf-8 -*-
from __future__ import annotations

STRINGS = {
    "darija": {
        "open":"دخل للمدينة","language":"اللغة","career":"الخدمة ديالي","cv":"صاوب / حدّث CV","matches":"الخدمات المناسبة ليا","shift":"الشيفت ديالي","orders":"الطلبات ديالي","payslips":"الفواتير والرواتب","notifications":"إعدادات التنبيهات",
        "services":"سوق الخدمات","projects":"المشاريع","my_projects":"مشاريعي","back":"رجع","not_yours":"❌ هاد الجلسة ماشي ديالك.",
    },
    "en": {
        "open":"Enter CITY","language":"Language","career":"My Career","cv":"Create / Update CV","matches":"My Job Matches","shift":"My Shift","orders":"My Orders","payslips":"Payslips & Invoices","notifications":"Notification Settings",
        "services":"Services Market","projects":"Projects","my_projects":"My Projects","back":"Back","not_yours":"❌ This session belongs to another member.",
    },
    "fr": {
        "open":"Entrer dans CITY","language":"Langue","career":"Ma carrière","cv":"Créer / Modifier le CV","matches":"Mes emplois recommandés","shift":"Mon shift","orders":"Mes commandes","payslips":"Fiches de paie & Factures","notifications":"Paramètres notifications",
        "services":"Marché des services","projects":"Projets","my_projects":"Mes projets","back":"Retour","not_yours":"❌ Cette session appartient à un autre membre.",
    },
}


def t(lang: str, key: str) -> str:
    lang = lang if lang in STRINGS else "darija"
    return STRINGS[lang].get(key, STRINGS["darija"].get(key, key))
