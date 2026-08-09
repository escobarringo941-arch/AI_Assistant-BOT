# -*- coding: utf-8 -*-
"""Unchanged ordered source component: content_apis."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║              APIs حقيقية (جديد)                        ║
    # ═══════════════════════════════════════════════════════
    
    async def fetch_json(url: str, params: dict = None, headers: dict = None) -> dict:
        """جيب JSON من أي API (مع logging باش نعرفو شنو وقع بالضبط)"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                async with session.get(url, params=params, headers=headers) as resp:
                    if resp.status == 200:
                        try:
                            return await resp.json()
                        except Exception as e:
                            print(f"[FETCH_JSON] JSON decode error من {url}: {e}")
                            return {}
                    else:
                        body = await resp.text()
                        print(f"[FETCH_JSON] {url} رجع status {resp.status}: {body[:200]}")
                        return {}
        except asyncio.TimeoutError:
            print(f"[FETCH_JSON] Timeout فـ {url}")
            return {}
        except Exception as e:
            print(f"[FETCH_JSON] Exception فـ {url}: {e}")
            return {}
    
    
    async def fetch_html(url: str, headers: dict = None) -> str:
        """جيب HTML خام من أي رابط (باش نقدرو نقرأو og:image مثلا)"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 200:
                        return await resp.text(errors="ignore")
                    return ""
        except Exception as e:
            print(f"[FETCH_HTML] Exception فـ {url}: {e}")
            return ""
    
    
    async def get_wikipedia_image(title: str) -> str:
        """صورة احتياطية (fallback) من Wikipedia REST API — مجاني وبلا API key"""
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
            data = await fetch_json(url)
            if not data:
                return ""
            original = data.get("originalimage", {}).get("source", "")
            if original:
                return original
            return data.get("thumbnail", {}).get("source", "")
        except Exception as e:
            print(f"[WIKI] خطأ فـ جلب الصورة لـ '{title}': {e}")
            return ""
    
    
    async def get_og_image(page_url: str) -> str:
        """صورة احتياطية من og:image meta tag ديال صفحة الويب نفسها (مثلا صفحة الخبر) — بلا API key"""
        try:
            html = await fetch_html(page_url, headers={"User-Agent": "Mozilla/5.0 (compatible; GGMW9Bot/1.0)"})
            if not html:
                return ""
            match = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if not match:
                match = re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', html, re.IGNORECASE)
            return match.group(1) if match else ""
        except Exception as e:
            print(f"[OG_IMAGE] خطأ فـ جلب الصورة من {page_url}: {e}")
            return ""
    
    
    GENRE_TRANSLATIONS = {
        "action": "أكشن", "adventure": "مغامرة", "comedy": "كوميديا",
        "drama": "دراما", "horror": "رعب", "thriller": "تشويق",
        "romance": "رومانسية", "sci-fi": "خيال علمي", "science fiction": "خيال علمي",
        "fantasy": "فانتازيا", "mystery": "غموض", "crime": "جريمة",
        "animation": "أنيميشن", "documentary": "وثائقي", "family": "عائلي",
        "musical": "موسيقي", "music": "موسيقى", "war": "حرب", "history": "تاريخي",
        "western": "وسترن", "biography": "سيرة ذاتية", "sport": "رياضي",
        "sports": "رياضي", "shounen": "شونين", "shoujo": "شوجو", "seinen": "سينين",
        "josei": "جوسي", "slice of life": "حياة يومية", "supernatural": "خوارق",
        "psychological": "نفسي", "school": "مدرسي", "isekai": "إيسيكاي",
        "ecchi": "إيتشي", "mecha": "ميكا", "sci fi": "خيال علمي", "indie": "إندي",
        "rpg": "لعب أدوار", "role-playing (rpg)": "لعب أدوار", "shooter": "تصويب",
        "strategy": "استراتيجية", "puzzle": "ألغاز", "racing": "سباق",
        "simulation": "محاكاة", "platformer": "منصات", "fighting": "قتال",
        "arcade": "أركيد", "casual": "كاجوال", "massively multiplayer": "متعدد اللاعبين",
        "board games": "ألعاب طاولة", "card": "ورق", "educational": "تعليمي",
        "kids": "أطفال", "superhero": "أبطال خارقين", "suspense": "إثارة",
        "short": "قصير", "film-noir": "نوار", "talk-show": "برنامج حواري",
        "reality-tv": "واقعي", "news": "أخبار", "game-show": "مسابقات",
    }
    
    
    async def translate_genres(genres_text: str) -> str:
        """
        يترجم لائحة الأنواع (Action, Comedy...) للعربية/الدارجة.
        كنبداو بقاموس ثابت (سريع وموثوق) لأشهر الأنواع، وإلا لقينا نوع
        ماكاينش فالقاموس كنعيطو لـ AI باش يترجموه (fallback).
        ملاحظة: جربنا الترجمة بـ AI وحدها فـ الأول، ولكن الموديل كان
        كيخلي الأنواع كيفما هي (كيتعامل معاها كـ tags ثابتة ماشي نص عادي)،
        فـ القاموس أوثق بزاف لهاد الحالة.
        """
        if not genres_text or genres_text == "N/A":
            return genres_text
        parts = [p.strip() for p in genres_text.split(",")]
        result = []
        for p in parts:
            mapped = GENRE_TRANSLATIONS.get(p.lower())
            if mapped:
                result.append(mapped)
            else:
                ai_translated = await translate_to_darija(p)
                result.append(ai_translated if ai_translated and ai_translated.lower() != p.lower() else p)
        return "، ".join(result)
    
    
    async def translate_to_darija(text: str) -> str:
        """يترجم نص من الانجليزية للدارجة المغربية عبر AI (مع fallback أوتوماتيك للموديل)"""
        if not text:
            return text
        if not OPENROUTER_API_KEY:
            print("[TRANSLATE] ⚠️ OPENROUTER_API_KEY ماكايناش (فارغة)! ماغاديش نترجمو والو.")
            return text
    
        messages = [
            {
                "role": "system",
                "content": (
                    "نتا مترجم محترف. ترجم النص التالي من الانجليزية للدارجة المغربية "
                    "بطريقة طبيعية وسلسة ومفهومة. غير الترجمة، بلا مقدمات، بلا تعليقات، "
                    "بلا علامات تنصيص."
                )
            },
            {"role": "user", "content": text}
        ]
    
        translated, error = await call_openrouter_chat(messages, 700, 0.3)
    
        if error:
            print(f"[TRANSLATE] ❌ فشلو كاع الموديلات: {error}")
            return text
    
        translated = translated.strip()
        print(f"[TRANSLATE] ✅ قبل: '{text[:50]}' | بعد: '{translated[:50]}'")
        return translated if translated else text
    
    
    async def translate_text(text: str, target_language_en: str) -> Optional[str]:
        """يترجم نص لأي لغة (مستعملة فـ الترجمة التلقائية بالـ Reaction). كيرجع None إلا فشلت الترجمة،
        باش نفرقو بين 'ماكاينش OPENROUTER_API_KEY' و 'النص هو نفسو الترجمة' (contrairement لـ translate_to_darija)."""
        if not text or not text.strip():
            return None
        if not OPENROUTER_API_KEY:
            print("[AUTO-TRANSLATE] ❌ OPENROUTER_API_KEY ماكاينش/فارغة — ماقدرش نترجم حتى نص.")
            return None
    
        messages = [
            {
                "role": "system",
                "content": (
                    f"You are a professional translator. Translate the user's message into "
                    f"{target_language_en}. Reply with ONLY the translation, no preamble, "
                    f"no quotation marks, no explanations. If the message is already in "
                    f"{target_language_en}, reply with it unchanged."
                )
            },
            {"role": "user", "content": text}
        ]
    
        translated, error = await call_openrouter_chat(messages, 700, 0.3)
        if error or not translated:
            print(f"[AUTO-TRANSLATE] ❌ فشلت الترجمة لـ {target_language_en}: {error}")
            return None
    
        return translated.strip()
    
    
    async def get_movie_from_omdb() -> dict:
        """
        اكتشاف عشوائي حقيقي للأفلام (بلا لائحة ثابتة):
        1) TMDb /discover/movie بصفحة عشوائية → لائحة أفلام معروفة (مفلترة بعدد الأصوات)
        2) نجيبو imdb_id ديال كل واحد عبر TMDb external_ids
        3) نستعملو OMDb (i=imdb_id) باش نجيبو التفاصيل الكاملة + rating (نفس الفورمات ديال قبل)
        """
        if not TMDB_API_KEY or not OMDB_API_KEY:
            print("[MOVIE] TMDB_API_KEY أو OMDB_API_KEY ماكاينين! خاصك تزيدهم فـ Railway Variables.")
            return {}
    
        discover_url = f"{TMDB_URL}/discover/movie"
        omdb_url = "https://www.omdbapi.com/"
    
        for page_attempt in range(5):  # يجرب حتى 5 صفحات عشوائية ديال TMDb قبل ما يستسلم
            params = {
                "api_key": TMDB_API_KEY,
                "language": "en-US",
                "sort_by": random.choice(["vote_average.desc", "popularity.desc"]),
                "vote_count.gte": 300,   # نتفاداو الأفلام المغمورة اللي عندها صوت ولا صوتين
                "include_adult": "false",
                "page": random.randint(1, 40),
            }
            data = await fetch_json(discover_url, params)
            results = data.get("results", []) if data else []
            if not results:
                continue
    
            random.shuffle(results)
    
            for movie in results[:12]:  # يجرب حتى 12 فيلم من نفس الصفحة
                tmdb_id = movie.get("id")
                if not tmdb_id:
                    continue
    
                ext_data = await fetch_json(
                    f"{TMDB_URL}/movie/{tmdb_id}/external_ids",
                    {"api_key": TMDB_API_KEY}
                )
                imdb_id = ext_data.get("imdb_id") if ext_data else None
                if not imdb_id or is_posted("movies", imdb_id):
                    continue
    
                omdb_data = await fetch_json(omdb_url, {
                    "i": imdb_id,
                    "apikey": OMDB_API_KEY,
                    "plot": "full"
                })
                if not omdb_data or omdb_data.get("Response") != "True":
                    continue
    
                rating = omdb_data.get("imdbRating", "0")
                try:
                    if rating in ("N/A", None) or float(rating) < 6.0:
                        continue
                except ValueError:
                    continue
    
                plot = omdb_data.get("Plot", "No plot available.")
                plot_ar = await translate_to_darija(plot)
    
                mark_posted("movies", imdb_id)
    
                poster = omdb_data.get("Poster", "")
                if not poster or poster == "N/A":
                    poster = await get_wikipedia_image(f"{omdb_data.get('Title', '')} (film)")
    
                return {
                    "title": omdb_data.get("Title", "Unknown"),
                    "year": omdb_data.get("Year", "N/A"),
                    "genre": await translate_genres(omdb_data.get("Genre", "N/A")),
                    "plot": plot_ar,
                    "rating": rating,
                    "poster": poster,
                    "imdb": f"https://www.imdb.com/title/{imdb_id}/"
                }
    
        return {}
    
    
    async def get_anime_from_jikan() -> dict:
        """
        اكتشاف عشوائي للأنمي عبر Jikan /top/anime بصفحة عشوائية (بلا لائحة ثابتة).
        بدلنا /random/anime (كان كيرجع من كامل قاعدة بيانات MAL بما فيها آلاف
        الحوايج المغمورة، فمعدل النجاح كان ضعيف بزاف وكيحتاج بزاف طلبات) بـ
        /top/anime اللي معاها كل نتيجة مضمونة الجودة من البداية (مرتبة بالـ score)،
        فطلب واحد فـ الغالب كافي.
        """
        jikan_headers = {"User-Agent": "Mozilla/5.0 (compatible; GGMW9Bot/1.0)"}
        list_url = "https://api.jikan.moe/v4/top/anime"
    
        for page_attempt in range(6):  # يجرب حتى 6 صفحات عشوائية قبل ما يستسلم
            if page_attempt > 0:
                await asyncio.sleep(1.5)  # نحترمو rate-limit ديال Jikan
    
            params = {"page": random.randint(1, 50), "limit": 25}  # top 1250 أنمي تقريبا
            data = await fetch_json(list_url, params, headers=jikan_headers)
            results = data.get("data", []) if data else []
    
            if not results:
                print(f"[JIKAN] محاولة {page_attempt+1}: الصفحة رجعت فارغة (data={bool(data)})")
                continue
    
            random.shuffle(results)
    
            for anime in results:
                mal_id = anime.get("mal_id")
                if not mal_id or is_posted("anime", str(mal_id)):
                    continue
                if not anime.get("synopsis"):
                    continue
    
                print(f"[JIKAN] ✅ اختار: {anime.get('title')} (score={anime.get('score')})")
                return await _build_anime_embed_data(anime)
    
            print(f"[JIKAN] محاولة {page_attempt+1}: كاع نتائج الصفحة مبعوتين من قبل ولا بلا synopsis")
    
        print("[JIKAN] ❌ ماكاينش نتيجة بعد كل المحاولات")
        return {}
    
    
    async def _build_anime_embed_data(anime: dict) -> dict:
        """يبني الـ dict الجاهز للـ embed انطلاقا من داتا أنمي جاية من Jikan"""
        mal_id = anime.get("mal_id")
        synopsis = anime.get("synopsis") or "No synopsis available."
        synopsis_ar = await translate_to_darija(synopsis)
    
        mark_posted("anime", str(mal_id))
    
        poster = anime.get("images", {}).get("jpg", {}).get("large_image_url", "")
        if not poster:
            poster = await get_wikipedia_image(f"{anime.get('title', '')} (anime)")
    
        return {
            "title": anime.get("title", "Unknown"),
            "title_jp": anime.get("title_japanese", ""),
            "type": anime.get("type", "TV"),
            "episodes": anime.get("episodes", "N/A"),
            "genres": await translate_genres(", ".join([g["name"] for g in anime.get("genres", [])])),
            "synopsis": synopsis_ar,
            "score": anime.get("score", 0),
            "poster": poster,
            "url": anime.get("url", "")
        }
    
    
    async def get_game_from_rawg() -> dict:
        """
        اكتشاف عشوائي حقيقي للألعاب عبر RAWG /games (بلا لائحة ثابتة).
        كنختارو صفحة عشوائية من أعلى الألعاب تقييما (ordering)، ومنبعد كنجيبو
        التفاصيل الكاملة ديال اللعبة المختارة.
        """
        if not RAWG_API_KEY:
            print("[RAWG] RAWG_API_KEY ماكاينش!")
            return {}
    
        list_url = "https://api.rawg.io/api/games"
    
        for page_attempt in range(5):  # يجرب حتى 5 صفحات عشوائية قبل ما يستسلم
            params = {
                "key": RAWG_API_KEY,
                "ordering": random.choice(["-rating", "-metacritic", "-added"]),
                "page_size": 40,
                "page": random.randint(1, 150),  # كنبقاو فـ نطاق الألعاب المعروفة بزاف
            }
            data = await fetch_json(list_url, params)
            results = data.get("results", []) if data else []
            if not results:
                continue
    
            random.shuffle(results)
    
            for game in results[:10]:  # يجرب حتى 10 ألعاب من نفس الصفحة
                slug = game.get("slug")
                rating = game.get("rating", 0)
                if not slug or is_posted("games", slug) or rating < 3.2:
                    continue
    
                detail = await fetch_json(f"{list_url}/{slug}", {"key": RAWG_API_KEY})
                if not detail or not detail.get("name"):
                    continue
    
                description = detail.get("description_raw", "No description available.")[:500]
                description_ar = await translate_to_darija(description)
    
                mark_posted("games", slug)
    
                poster = detail.get("background_image", "")
                if not poster:
                    poster = await get_wikipedia_image(f"{detail.get('name', '')} (video game)")
    
                return {
                    "name": detail.get("name", "Unknown"),
                    "released": detail.get("released", "N/A"),
                    "genres": await translate_genres(", ".join([g["name"] for g in detail.get("genres", [])])),
                    "description": description_ar,
                    "rating": f"{rating}/5",
                    "poster": poster,
                    "url": f"https://rawg.io/games/{slug}"
                }
    
        return {}
    
    
    async def get_track_artwork(artist: str, track_name: str) -> str:
        """يجيب ملصق (poster) ديال الأغنية: يجرب iTunes أولا، ولا Deezer كـ fallback (الاثنين مجانيين بلا API key)"""
        # ═══ المحاولة 1: iTunes Search API ═══
        try:
            url = "https://itunes.apple.com/search"
            params = {
                "term": f"{artist} {track_name}",
                "media": "music",
                "entity": "song",
                "limit": 1
            }
            data = await fetch_json(url, params)
            results = data.get("results", []) if data else []
            if results:
                artwork = results[0].get("artworkUrl100", "")
                if artwork:
                    # نكبرو الحجم من 100x100 لـ 600x600 (كيفما كان الفورمات ديال الرابط)
                    return artwork.replace("100x100", "600x600")
            else:
                print(f"[ITUNES] ماكاينش نتيجة لـ '{artist} - {track_name}'")
        except Exception as e:
            print(f"[ITUNES] خطأ فـ جلب الملصق: {e}")
    
        # ═══ المحاولة 2: Deezer API (fallback) ═══
        try:
            url = "https://api.deezer.com/search"
            params = {"q": f"artist:\"{artist}\" track:\"{track_name}\""}
            data = await fetch_json(url, params)
            results = data.get("data", []) if data else []
            if results:
                album = results[0].get("album", {})
                cover = album.get("cover_xl", "") or album.get("cover_big", "") or album.get("cover_medium", "")
                if cover:
                    return cover
            else:
                print(f"[DEEZER] ماكاينش نتيجة لـ '{artist} - {track_name}'")
        except Exception as e:
            print(f"[DEEZER] خطأ فـ جلب الملصق: {e}")
    
        return ""
    
    
    async def get_music_from_lastfm() -> dict:
        """
        جيب أغنية عشوائية من Last.fm. لائحة الفنانين ماشي ثابتة —
        كنجيبوها ديناميكيا من chart.getTopArtists (top chart عالمي محين)
        باش يتوسع الاختيار وميبقاش محدود فـ 30 فنان.
        """
        if not LASTFM_API_KEY:
            return {}
    
        url = "http://ws.audioscrobbler.com/2.0/"
    
        chart_data = await fetch_json(url, {
            "method": "chart.getTopArtists",
            "api_key": LASTFM_API_KEY,
            "format": "json",
            "limit": 200,
        })
        popular_artists = [
            a.get("name") for a in chart_data.get("artists", {}).get("artist", [])
            if a.get("name")
        ] if chart_data else []
    
        if not popular_artists:
            # fallback بسيط إلا chart API طاح مؤقتا
            popular_artists = [
                "The Weeknd", "Drake", "Taylor Swift", "Dua Lipa", "Bad Bunny"
            ]
    
        artists_to_try = random.sample(popular_artists, min(len(popular_artists), 15))
    
        for artist in artists_to_try:  # يجرب حتى 15 فنان (من التشارت الديناميكي) قبل ما يستسلم
            params = {
                "method": "artist.gettoptracks",
                "artist": artist,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "limit": 10
            }
    
            data = await fetch_json(url, params)
    
            if data and "toptracks" in data and "track" in data["toptracks"]:
                tracks = data["toptracks"]["track"]
                fresh_tracks = [
                    t for t in tracks
                    if not is_posted("music", f"{artist}|{t.get('name', '')}")
                ]
                if not fresh_tracks:
                    continue  # كاع الأغاني ديال هاد الفنان تبعثاو، نجربو فنان آخر
    
                track = random.choice(fresh_tracks)
                listeners_str = track.get("listeners", "0")
                try:
                    listeners = int(listeners_str)
                except (ValueError, TypeError):
                    listeners = 0
    
                mark_posted("music", f"{artist}|{track.get('name', '')}")
    
                poster = await get_track_artwork(artist, track.get("name", ""))
    
                return {
                    "name": track.get("name", "Unknown"),
                    "artist": artist,
                    "listeners": listeners,
                    "url": track.get("url", ""),
                    "poster": poster
                }
    
        # إلا كاع الفنانين تسالاو، نبداو من جديد
        reset_category_history("music")
        return {}
    
    
    async def get_news_from_api() -> dict:
        """جيب خبر من NewsAPI"""
        if not NEWS_API_KEY:
            return {}
        
        url = "https://newsapi.org/v2/top-headlines"
        categories = random.sample(["technology", "entertainment", "science", "sports"], 4)
    
        for category in categories:  # يجرب كاع الفئات باش يلقى خبر جديد ما تبعثش
            params = {
                "apiKey": NEWS_API_KEY,
                "category": category,
                "language": "en",
                "pageSize": 30
            }
    
            data = await fetch_json(url, params)
    
            if not data or "articles" not in data or not data["articles"]:
                continue
    
            # يفلتر المقالات اللي عندها عنوان ووصف حقيقيين (NewsAPI كترجع بزاف [Removed])
            # وما تبعثاتش من قبل، باش يكون دايما خبر جديد 100%
            valid_articles = [
                a for a in data["articles"]
                if a.get("title") and a.get("title") != "[Removed]"
                and a.get("url") and not is_posted("news", a["url"])
            ]
            if not valid_articles:
                continue
    
            article = random.choice(valid_articles)
            title_ar = await translate_to_darija(article.get("title", "Unknown"))
            desc_ar = await translate_to_darija(article.get("description", "No description."))
    
            mark_posted("news", article["url"])
    
            image = article.get("urlToImage", "")
            if not image:
                image = await get_og_image(article.get("url", ""))
    
            return {
                "title": title_ar,
                "description": desc_ar,
                "url": article.get("url", ""),
                "source": article.get("source", {}).get("name", "Unknown"),
                "image": image
            }
    
        # ماكاينش خبر جديد دابا فـ كاع الفئات، غادي نعاودو نجربو فـ الدورة الجاية
        return {}
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
