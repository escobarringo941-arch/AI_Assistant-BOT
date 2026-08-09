# -*- coding: utf-8 -*-
from __future__ import annotations

# Fixed-price member services. Prices are cents. The actual worker share comes
# from their career config; the rest goes to the employer business account.
SERVICES = {
    "coffee_order":{"career":"barista","emoji":"☕","price":300,"hours":1,"name":{"darija":"طلب قهوة","en":"Coffee Order","fr":"Commande café"},"desc":{"darija":"قهوة افتراضية + تفاعل من الباريستا.","en":"Virtual café order served by a member barista.","fr":"Commande virtuelle servie par un barista membre."}},
    "cafe_combo":{"career":"barista","emoji":"🍰","price":500,"hours":1,"name":{"darija":"قهوة + حلوة","en":"Coffee Combo","fr":"Combo café"},"desc":{"darija":"طلب كومبو من المقهى.","en":"Café combo order.","fr":"Commande combo du café."}},
    "meal_order":{"career":"restaurant","emoji":"🍔","price":700,"hours":2,"name":{"darija":"طلب وجبة","en":"Meal Order","fr":"Commande repas"},"desc":{"darija":"خدمة طلب افتراضي من المطعم.","en":"Virtual restaurant order.","fr":"Commande virtuelle du restaurant."}},
    "delivery_service":{"career":"delivery","emoji":"📦","price":600,"hours":3,"name":{"darija":"خدمة توصيل","en":"Delivery Service","fr":"Service livraison"},"desc":{"darija":"تنسيق وتسليم طلب داخل نظام المدينة.","en":"Coordinate a CITY delivery order.","fr":"Coordonner une livraison CITY."}},
    "shopping_help":{"career":"shop_assistant","emoji":"🛒","price":500,"hours":3,"name":{"darija":"مساعدة فالشراء","en":"Shopping Help","fr":"Aide shopping"},"desc":{"darija":"مساعدة لاختيار منتج/امتياز داخل السيرفر.","en":"Help choosing a server product/perk.","fr":"Aide pour choisir un produit/avantage serveur."}},
    "organization_cleanup":{"career":"maintenance","emoji":"🧹","price":900,"hours":6,"name":{"darija":"تنظيم وصيانة بسيطة","en":"Organisation Check","fr":"Contrôle d’organisation"},"desc":{"darija":"Checklist وتنظيم لمشروع/مساحة رقمية بلا صلاحيات إدارية.","en":"Organisation checklist for a digital project/space without admin access.","fr":"Checklist d’organisation pour un projet/espace sans accès admin."}},
    "dj_session":{"career":"dj","emoji":"🎧","price":1800,"hours":6,"name":{"darija":"جلسة DJ","en":"DJ Session","fr":"Session DJ"},"desc":{"darija":"اختيار أجواء/Playlist لفعالية.","en":"Playlist and atmosphere for an event.","fr":"Playlist et ambiance pour un événement."}},
    "event_hosting":{"career":"event_host","emoji":"🎤","price":2200,"hours":12,"name":{"darija":"تنشيط فعالية","en":"Event Hosting","fr":"Animation événement"},"desc":{"darija":"منشط عضو يساعدك فتنظيم وتقديم فعالية.","en":"A member host helps run your event.","fr":"Un membre animateur aide à gérer l'événement."}},
    "gaming_session":{"career":"gaming_host","emoji":"🎮","price":1600,"hours":8,"name":{"darija":"تنظيم تحدي ألعاب","en":"Gaming Session","fr":"Session gaming"},"desc":{"darija":"تنظيم جلسة/تحدي ألعاب للمجتمع.","en":"Run a gaming session or challenge.","fr":"Organiser une session ou un défi gaming."}},
    "content_pack":{"career":"content_creator","emoji":"📱","price":2000,"hours":24,"name":{"darija":"باك محتوى","en":"Content Pack","fr":"Pack contenu"},"desc":{"darija":"أفكار + نصوص قصيرة لمشروع أو إعلان.","en":"Ideas and short copy for a project/promo.","fr":"Idées et textes courts pour un projet/promo."}},
    "photo_direction":{"career":"photographer","emoji":"📸","price":1800,"hours":24,"name":{"darija":"توجيه جلسة تصوير","en":"Photo Direction","fr":"Direction photo"},"desc":{"darija":"Concept وposes وأفكار بصرية.","en":"Concept, poses and visual direction.","fr":"Concept, poses et direction visuelle."}},
    "fashion_consult":{"career":"fashion_stylist","emoji":"👗","price":1600,"hours":12,"name":{"darija":"استشارة ستايل","en":"Style Consultation","fr":"Conseil style"},"desc":{"darija":"تنسيق Outfit/ستايل حسب الهدف.","en":"Outfit/style consultation.","fr":"Conseil tenue/style."}},
    "makeup_consult":{"career":"makeup_artist","emoji":"💄","price":1600,"hours":12,"name":{"darija":"استشارة ميكاب","en":"Makeup Consultation","fr":"Conseil maquillage"},"desc":{"darija":"اقتراح ميكاب وألوان حسب اللوك.","en":"Makeup and color recommendations.","fr":"Recommandations maquillage et couleurs."}},
    "asset_tuneup":{"career":"mechanic","emoji":"🔧","price":1400,"hours":12,"name":{"darija":"فحص ممتلك افتراضي","en":"Asset Tune-up","fr":"Révision d'actif"},"desc":{"darija":"خدمة Roleplay/تقييم لأصل افتراضي.","en":"Roleplay virtual-asset tune-up.","fr":"Révision roleplay d'un actif virtuel."}},
    "tech_help":{"career":"it_technician","emoji":"💻","price":1800,"hours":12,"name":{"darija":"مساعدة تقنية","en":"Tech Help","fr":"Aide technique"},"desc":{"darija":"تشخيص مشكل تقني عام وإرشادات.","en":"General technical troubleshooting guidance.","fr":"Aide générale de dépannage technique."}},
    "banner_design":{"career":"graphic_designer","emoji":"🎨","price":2800,"hours":48,"name":{"darija":"تصميم Banner","en":"Banner Design","fr":"Design bannière"},"desc":{"darija":"Concept/تصميم Banner أو هوية بسيطة.","en":"Banner or simple visual identity concept.","fr":"Concept bannière ou identité simple."}},
    "bank_guidance":{"career":"bank_employee","emoji":"🏦","price":800,"hours":12,"name":{"darija":"توجيه بنكي","en":"Bank Guidance","fr":"Conseil bancaire"},"desc":{"darija":"شرح نظام البنك والادخار بلا وصول لحسابك.","en":"Explain Bank/Savings with no account access.","fr":"Expliquer Banque/Épargne sans accès au compte."}},
    "asset_advice":{"career":"real_estate","emoji":"🏠","price":1500,"hours":24,"name":{"darija":"استشارة ممتلكات","en":"Asset Advice","fr":"Conseil actifs"},"desc":{"darija":"مقارنة ممتلكات المتجر وخطة شراء.","en":"Compare Shop assets and buying strategy.","fr":"Comparer les actifs et la stratégie d'achat."}},
    "sales_campaign":{"career":"sales_rep","emoji":"💼","price":2200,"hours":24,"name":{"darija":"خطة مبيعات","en":"Sales Campaign","fr":"Campagne commerciale"},"desc":{"darija":"عرض/خطة إقناع وتسويق لمشروع.","en":"Sales pitch and campaign plan.","fr":"Pitch et plan de campagne commerciale."}},
}


def service_name(service_id: str, lang="darija") -> str:
    s = SERVICES.get(service_id, {})
    names = s.get("name", {})
    return names.get(lang, names.get("darija", service_id))


def services_for_career(career_id: str):
    return [(sid, s) for sid, s in SERVICES.items() if s.get("career") == career_id]
