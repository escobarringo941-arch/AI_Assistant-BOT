# -*- coding: utf-8 -*-
"""Career catalogue for GGMW9 CITY.

No career is gender-locked. Matching is based on skills, preferences,
availability and the member's own real-world description.
"""
from __future__ import annotations

SKILLS = {
    "communication": {"emoji":"🤝","darija":"التواصل مع الناس","en":"Communication","fr":"Communication"},
    "customer": {"emoji":"😊","darija":"خدمة الزبناء","en":"Customer Service","fr":"Service client"},
    "creativity": {"emoji":"🎨","darija":"الإبداع","en":"Creativity","fr":"Créativité"},
    "design": {"emoji":"🖌️","darija":"التصميم","en":"Design","fr":"Design"},
    "fashion": {"emoji":"👗","darija":"الموضة والستايل","en":"Fashion & Styling","fr":"Mode & Style"},
    "beauty": {"emoji":"💄","darija":"الجمال والميكاب","en":"Beauty & Makeup","fr":"Beauté & Maquillage"},
    "tech": {"emoji":"💻","darija":"التقنية والحواسيب","en":"Technology","fr":"Technologie"},
    "problem_solving": {"emoji":"🧠","darija":"حل المشاكل","en":"Problem Solving","fr":"Résolution de problèmes"},
    "gaming": {"emoji":"🎮","darija":"الألعاب","en":"Gaming","fr":"Gaming"},
    "music": {"emoji":"🎧","darija":"الموسيقى","en":"Music","fr":"Musique"},
    "hosting": {"emoji":"🎤","darija":"التقديم والتنشيط","en":"Hosting","fr":"Animation"},
    "content": {"emoji":"📱","darija":"صناعة المحتوى","en":"Content Creation","fr":"Création de contenu"},
    "photo": {"emoji":"📸","darija":"التصوير","en":"Photography","fr":"Photographie"},
    "sales": {"emoji":"💼","darija":"البيع والإقناع","en":"Sales","fr":"Vente"},
    "finance": {"emoji":"📊","darija":"المال والحسابات","en":"Finance","fr":"Finance"},
    "organization": {"emoji":"📦","darija":"التنظيم واللوجستيك","en":"Organization","fr":"Organisation"},
    "repair": {"emoji":"🔧","darija":"الإصلاح والميكانيك","en":"Repair","fr":"Réparation"},
    "leadership": {"emoji":"👑","darija":"القيادة والتسيير","en":"Leadership","fr":"Leadership"},
}

# Helper: rank thresholds are Career XP within the current career.
def ranks(*names):
    thresholds = (0, 350, 1000, 2500, 5500)
    return [{"name": n, "xp": thresholds[i]} for i, n in enumerate(names)]


CAREERS = {
    "barista": {
        "emoji":"☕","sector":"hospitality","business_id":"ggmw9_cafe",
        "name":{"darija":"باريستا","en":"Barista","fr":"Barista"},
        "desc":{"darija":"تحضير الطلبات وخدمة زبناء المقهى.","en":"Prepare café orders and serve customers.","fr":"Préparer les commandes du café et servir les clients."},
        "skills":{"customer":5,"communication":4,"organization":2}, "styles":{"people":3,"active":2},
        "pay_cycle":"hourly","hourly":650,"service_worker_share_bps":1000,"work_days":[0,1,2,3,4,5,6],
        "ranks":ranks("متدرب","باريستا","باريستا محترف","مشرف المقهى","مدير المقهى"),
        "benefits":{"shop_discount_by_rank":[0,0,1,1,2],"bank_bps_by_rank":[0,0,0,1,1]},
    },
    "restaurant": {
        "emoji":"🍔","sector":"hospitality","business_id":"ggmw9_restaurant",
        "name":{"darija":"طاقم المطعم","en":"Restaurant Crew","fr":"Équipe restaurant"},
        "desc":{"darija":"طلبات الماكلة، التنظيم وخدمة الزبناء.","en":"Food orders, service and organisation.","fr":"Commandes, service et organisation."},
        "skills":{"customer":4,"organization":4,"communication":3},"styles":{"people":3,"active":3},
        "pay_cycle":"hourly","hourly":700,"service_worker_share_bps":1200,"work_days":[0,1,2,3,4,5,6],
        "ranks":ranks("متدرب","طاقم المطعم","محترف","مشرف","مدير المطعم"),
        "benefits":{"shop_discount_by_rank":[0,0,0,1,2],"bank_bps_by_rank":[0,0,0,0,1]},
    },
    "delivery": {
        "emoji":"📦","sector":"operations","business_id":"ggmw9_delivery",
        "name":{"darija":"موصل الطلبات","en":"Delivery Driver","fr":"Livreur"},
        "desc":{"darija":"تنظيم وتسليم الطلبات بسرعة واعتمادية.","en":"Organise and deliver orders reliably.","fr":"Organiser et livrer les commandes avec fiabilité."},
        "skills":{"organization":5,"communication":2,"problem_solving":2},"styles":{"active":4,"solo":2},
        "pay_cycle":"commission","hourly":300,"service_worker_share_bps":4500,"work_days":[0,1,2,3,4,5,6],
        "ranks":ranks("متدرب","موصل","موصل محترف","منسق التوصيل","مدير اللوجستيك"),
        "benefits":{"shop_discount_by_rank":[0,0,0,1,1],"bank_bps_by_rank":[0,0,0,0,1]},
    },
    "shop_assistant": {
        "emoji":"🛒","sector":"operations","business_id":"ggmw9_market",
        "name":{"darija":"مساعد المتجر","en":"Shop Assistant","fr":"Assistant boutique"},
        "desc":{"darija":"مساعدة الزبناء وتنظيم المبيعات.","en":"Help customers and organise sales.","fr":"Aider les clients et organiser les ventes."},
        "skills":{"customer":5,"sales":3,"organization":3},"styles":{"people":4},
        "pay_cycle":"daily","hourly":675,"service_worker_share_bps":1000,"work_days":[0,1,2,3,4,5,6],
        "ranks":ranks("متدرب","مساعد متجر","مساعد أول","مشرف المتجر","مدير المتجر"),
        "benefits":{"shop_discount_by_rank":[1,2,3,4,5],"bank_bps_by_rank":[0,0,0,0,1]},
    },
    "maintenance": {
        "emoji":"🧹","sector":"operations","business_id":"ggmw9_facilities",
        "name":{"darija":"فريق الصيانة","en":"Maintenance Crew","fr":"Équipe maintenance"},
        "desc":{"darija":"تنظيم وصيانة المساحات والمهام التشغيلية.","en":"Keep spaces and operations organised.","fr":"Maintenir les espaces et opérations organisés."},
        "skills":{"organization":5,"problem_solving":3,"repair":2},"styles":{"solo":3,"active":2},
        "pay_cycle":"daily","hourly":625,"service_worker_share_bps":0,"work_days":[0,1,2,3,4],
        "ranks":ranks("متدرب","عامل صيانة","تقني صيانة","مشرف الصيانة","مدير المرافق"),
        "benefits":{"shop_discount_by_rank":[0,0,0,1,1],"bank_bps_by_rank":[0,0,0,0,1]},
    },
    "dj": {
        "emoji":"🎧","sector":"entertainment","business_id":"ggmw9_entertainment",
        "name":{"darija":"DJ","en":"DJ","fr":"DJ"},
        "desc":{"darija":"جلسات موسيقية واختيار أجواء للفعاليات.","en":"Music sessions and event atmosphere.","fr":"Sessions musicales et ambiance d'événements."},
        "skills":{"music":5,"hosting":3,"communication":2},"styles":{"creative":4,"people":2},
        "pay_cycle":"commission","hourly":400,"service_worker_share_bps":6000,"work_days":[4,5,6],
        "ranks":ranks("متدرب","DJ","DJ محترف","Head DJ","مدير الترفيه"),
        "benefits":{"shop_discount_by_rank":[0,0,1,2,2],"bank_bps_by_rank":[0,0,0,0,1]},
    },
    "event_host": {
        "emoji":"🎤","sector":"entertainment","business_id":"ggmw9_events",
        "name":{"darija":"منشط الفعاليات","en":"Event Host","fr":"Animateur d'événements"},
        "desc":{"darija":"تقديم وتنظيم فعاليات المجتمع.","en":"Host and organise community events.","fr":"Animer et organiser les événements communautaires."},
        "skills":{"hosting":5,"communication":5,"leadership":2},"styles":{"people":5,"active":2},
        "pay_cycle":"commission","hourly":450,"service_worker_share_bps":6000,"work_days":[4,5,6],
        "ranks":ranks("متدرب","منشط","منشط محترف","منسق فعاليات","مدير الفعاليات"),
        "benefits":{"shop_discount_by_rank":[0,0,1,2,2],"bank_bps_by_rank":[0,0,0,0,1]},
    },
    "gaming_host": {
        "emoji":"🎮","sector":"entertainment","business_id":"ggmw9_gaming",
        "name":{"darija":"منشط الألعاب","en":"Gaming Host","fr":"Animateur gaming"},
        "desc":{"darija":"تنظيم جلسات ألعاب وتحديات وبطولات.","en":"Run gaming sessions, challenges and tournaments.","fr":"Organiser des sessions, défis et tournois gaming."},
        "skills":{"gaming":5,"hosting":4,"communication":3},"styles":{"people":3,"active":3},
        "pay_cycle":"commission","hourly":425,"service_worker_share_bps":6000,"work_days":[4,5,6],
        "ranks":ranks("متدرب","Gaming Host","Host محترف","منسق البطولات","Gaming Manager"),
        "benefits":{"shop_discount_by_rank":[0,0,1,2,2],"bank_bps_by_rank":[0,0,0,0,1]},
    },
    "content_creator": {
        "emoji":"📱","sector":"media","business_id":"ggmw9_media",
        "name":{"darija":"صانع محتوى","en":"Content Creator","fr":"Créateur de contenu"},
        "desc":{"darija":"أفكار، كتابة ومحتوى للمجتمع والمشاريع.","en":"Ideas, writing and content for community projects.","fr":"Idées, rédaction et contenu pour les projets."},
        "skills":{"content":5,"creativity":4,"communication":2},"styles":{"creative":5,"solo":2},
        "pay_cycle":"commission","hourly":400,"service_worker_share_bps":7000,"work_days":[0,1,2,3,4,5,6],
        "ranks":ranks("متدرب","صانع محتوى","Creator محترف","Content Lead","Media Director"),
        "benefits":{"shop_discount_by_rank":[0,0,2,3,4],"bank_bps_by_rank":[0,0,0,1,1]},
    },
    "photographer": {
        "emoji":"📸","sector":"media","business_id":"ggmw9_media",
        "name":{"darija":"مصور","en":"Photographer","fr":"Photographe"},
        "desc":{"darija":"تصوير، أفكار بصرية وتوجيه جلسات الصور.","en":"Photography and visual direction.","fr":"Photographie et direction visuelle."},
        "skills":{"photo":5,"creativity":4,"design":2},"styles":{"creative":5,"solo":2},
        "pay_cycle":"commission","hourly":400,"service_worker_share_bps":7000,"work_days":[0,1,2,3,4,5,6],
        "ranks":ranks("متدرب","مصور","مصور محترف","Art Lead","Photo Director"),
        "benefits":{"shop_discount_by_rank":[0,0,2,3,4],"bank_bps_by_rank":[0,0,0,1,1]},
    },
    "fashion_stylist": {
        "emoji":"👗","sector":"fashion","business_id":"ggmw9_style_studio",
        "name":{"darija":"ستايلست أزياء","en":"Fashion Stylist","fr":"Styliste mode"},
        "desc":{"darija":"تنسيق الستايل والملابس والاستشارات البصرية.","en":"Outfit styling and visual consultation.","fr":"Conseil en style et tenues."},
        "skills":{"fashion":5,"creativity":4,"customer":3},"styles":{"creative":5,"people":2},
        "pay_cycle":"commission","hourly":350,"service_worker_share_bps":7000,"work_days":[0,1,2,3,4,5,6],
        "ranks":ranks("متدرب","ستايلست","ستايلست محترف","Senior Stylist","Style Director"),
        "benefits":{"shop_discount_by_rank":[1,2,4,6,8],"bank_bps_by_rank":[0,0,0,1,1]},
    },
    "makeup_artist": {
        "emoji":"💄","sector":"fashion","business_id":"ggmw9_beauty_studio",
        "name":{"darija":"ميكاب أرتيست","en":"Makeup Artist","fr":"Maquilleur·se"},
        "desc":{"darija":"استشارات ميكاب وألوان وستايل جمالي.","en":"Makeup, color and beauty consultation.","fr":"Conseil maquillage, couleurs et beauté."},
        "skills":{"beauty":5,"creativity":4,"customer":4},"styles":{"creative":5,"people":3},
        "pay_cycle":"commission","hourly":350,"service_worker_share_bps":7000,"work_days":[0,1,2,3,4,5,6],
        "ranks":ranks("متدرب","Makeup Artist","محترف","Senior Artist","Beauty Director"),
        "benefits":{"shop_discount_by_rank":[1,2,4,6,8],"bank_bps_by_rank":[0,0,0,1,1]},
    },
    "mechanic": {
        "emoji":"🔧","sector":"technical","business_id":"ggmw9_workshop",
        "name":{"darija":"ميكانيكي","en":"Mechanic","fr":"Mécanicien"},
        "desc":{"darija":"تشخيص وإصلاح الأصول والمشاكل التقنية الافتراضية.","en":"Diagnose and repair virtual assets and issues.","fr":"Diagnostiquer et réparer les actifs et problèmes."},
        "skills":{"repair":5,"problem_solving":4,"tech":2},"styles":{"technical":5,"solo":2},
        "pay_cycle":"daily","hourly":825,"service_worker_share_bps":5500,"work_days":[0,1,2,3,4,5],
        "ranks":ranks("متدرب","ميكانيكي","تقني محترف","Workshop Lead","Workshop Manager"),
        "benefits":{"shop_discount_by_rank":[0,0,1,2,3],"bank_bps_by_rank":[0,0,0,1,1]},
    },
    "it_technician": {
        "emoji":"💻","sector":"technical","business_id":"ggmw9_tech",
        "name":{"darija":"تقني معلوماتي","en":"IT Technician","fr":"Technicien IT"},
        "desc":{"darija":"حل مشاكل تقنية ومساعدة المستخدمين.","en":"Troubleshoot technical problems and help users.","fr":"Résoudre les problèmes techniques et aider les utilisateurs."},
        "skills":{"tech":5,"problem_solving":5,"communication":2},"styles":{"technical":5,"solo":2},
        "pay_cycle":"daily","hourly":900,"service_worker_share_bps":6000,"work_days":[0,1,2,3,4],
        "ranks":ranks("متدرب","تقني IT","تقني محترف","Senior Technician","Tech Lead"),
        "benefits":{"shop_discount_by_rank":[0,0,1,2,3],"bank_bps_by_rank":[0,0,1,1,2]},
    },
    "graphic_designer": {
        "emoji":"🎨","sector":"media","business_id":"ggmw9_design",
        "name":{"darija":"مصمم غرافيك","en":"Graphic Designer","fr":"Graphiste"},
        "desc":{"darija":"لوغوهات، بانرات وهوية بصرية للمشاريع.","en":"Logos, banners and visual identity.","fr":"Logos, bannières et identité visuelle."},
        "skills":{"design":5,"creativity":5,"tech":2},"styles":{"creative":5,"solo":4},
        "pay_cycle":"commission","hourly":450,"service_worker_share_bps":7000,"work_days":[0,1,2,3,4,5,6],
        "ranks":ranks("متدرب","مصمم","مصمم محترف","Senior Designer","Creative Director"),
        "benefits":{"shop_discount_by_rank":[0,1,2,3,5],"bank_bps_by_rank":[0,0,0,1,1]},
    },
    "bank_employee": {
        "emoji":"🏦","sector":"business","business_id":"ggmw9_bank_office",
        "name":{"darija":"موظف بنك","en":"Bank Employee","fr":"Employé de banque"},
        "desc":{"darija":"توجيه مالي وتثقيف بنكي بلا صلاحية على حسابات الآخرين.","en":"Financial guidance without access to other accounts.","fr":"Conseil financier sans accès aux comptes des autres."},
        "skills":{"finance":5,"customer":4,"organization":3},"styles":{"people":3,"technical":2},
        "pay_cycle":"weekly","hourly":950,"service_worker_share_bps":1000,"work_days":[0,1,2,3,4],
        "ranks":ranks("متدرب","موظف بنك","موظف أول","مشرف البنك","Bank Manager"),
        "benefits":{"shop_discount_by_rank":[0,0,1,2,2],"bank_bps_by_rank":[1,1,2,2,3]},
    },
    "real_estate": {
        "emoji":"🏠","sector":"business","business_id":"ggmw9_realty",
        "name":{"darija":"وكيل عقاري","en":"Real Estate Agent","fr":"Agent immobilier"},
        "desc":{"darija":"استشارات أصول وعروض وبيع ممتلكات افتراضية.","en":"Asset advice, listings and virtual property sales.","fr":"Conseil, annonces et vente d'actifs virtuels."},
        "skills":{"sales":5,"communication":4,"finance":3},"styles":{"people":4,"business":4},
        "pay_cycle":"commission","hourly":350,"service_worker_share_bps":6500,"work_days":[0,1,2,3,4,5],
        "ranks":ranks("متدرب","وكيل عقاري","وكيل محترف","Senior Agent","Realty Director"),
        "benefits":{"shop_discount_by_rank":[0,0,1,2,3],"bank_bps_by_rank":[0,0,1,2,2]},
    },
    "sales_rep": {
        "emoji":"💼","sector":"business","business_id":"ggmw9_sales",
        "name":{"darija":"ممثل مبيعات","en":"Sales Representative","fr":"Commercial"},
        "desc":{"darija":"عروض، إقناع وحملات مبيعات للمشاريع.","en":"Offers, persuasion and sales campaigns.","fr":"Offres, persuasion et campagnes commerciales."},
        "skills":{"sales":5,"communication":5,"customer":3},"styles":{"people":5,"business":4},
        "pay_cycle":"weekly","hourly":800,"service_worker_share_bps":6000,"work_days":[0,1,2,3,4],
        "ranks":ranks("متدرب","Sales Rep","Sales Pro","Sales Lead","Sales Director"),
        "benefits":{"shop_discount_by_rank":[0,0,1,2,3],"bank_bps_by_rank":[0,0,0,1,2]},
    },
}

SECTOR_NAMES = {
    "hospitality":{"emoji":"🍽️","darija":"الضيافة والمطاعم","en":"Hospitality","fr":"Hospitalité"},
    "operations":{"emoji":"🚚","darija":"العمليات واللوجستيك","en":"Operations","fr":"Opérations"},
    "entertainment":{"emoji":"🎮","darija":"الترفيه","en":"Entertainment","fr":"Divertissement"},
    "media":{"emoji":"📱","darija":"الإعلام والإبداع","en":"Media & Creative","fr":"Média & Créatif"},
    "fashion":{"emoji":"💄","darija":"الموضة والجمال","en":"Fashion & Beauty","fr":"Mode & Beauté"},
    "technical":{"emoji":"🔧","darija":"التقنية والصيانة","en":"Technical","fr":"Technique"},
    "business":{"emoji":"💼","darija":"الأعمال والمال","en":"Business","fr":"Business"},
}


def career_name(career_id: str, lang: str = "darija") -> str:
    c = CAREERS.get(career_id, {})
    names = c.get("name", {})
    return names.get(lang, names.get("darija", career_id))


def career_rank(career_id: str, career_xp: int) -> tuple[int, dict]:
    ranks_ = CAREERS.get(career_id, {}).get("ranks", [])
    if not ranks_:
        return 0, {"name":"—","xp":0}
    idx = 0
    for i, r in enumerate(ranks_):
        if int(career_xp) >= int(r.get("xp", 0)):
            idx = i
    return idx, ranks_[idx]


def next_rank(career_id: str, career_xp: int):
    idx, _ = career_rank(career_id, career_xp)
    ranks_ = CAREERS.get(career_id, {}).get("ranks", [])
    return ranks_[idx+1] if idx+1 < len(ranks_) else None


def all_business_ids() -> list[str]:
    return sorted({str(c.get("business_id")) for c in CAREERS.values() if c.get("business_id")})
