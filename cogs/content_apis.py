# -*- coding: utf-8 -*-
"""Unchanged ordered source component: content_apis."""

from cogs._component_runtime import install_component, uninstall_component

# ORIGINAL SOURCE BEGIN
if globals().get("_GGMW9_COMPONENT_EXEC", False):
    # ═══════════════════════════════════════════════════════
    # ║              APIs حقيقية (جديد)                        ║
    # ═══════════════════════════════════════════════════════
    
    async def fetch_json(url: str, params: dict = None, headers: dict = None) -> dict:
        """جيب JSON مع retry قصير للـrate-limit والأعطال المؤقتة."""
        retryable = {429, 500, 502, 503, 504}
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as session:
                    async with session.get(url, params=params, headers=headers) as resp:
                        if resp.status == 200:
                            try:
                                return await resp.json()
                            except Exception as exc:
                                print(f"[FETCH_JSON] JSON decode error من {url}: {exc}")
                                return {}
                        body = await resp.text()
                        if resp.status in retryable and attempt < 2:
                            retry_after = _safe_float(resp.headers.get("Retry-After"), attempt + 1)
                            await asyncio.sleep(max(0.5, min(retry_after, 4.0)))
                            continue
                        print(f"[FETCH_JSON] {url} رجع status {resp.status}: {body[:200]}")
                        return {}
            except asyncio.TimeoutError:
                if attempt < 2:
                    await asyncio.sleep(attempt + 1)
                    continue
                print(f"[FETCH_JSON] Timeout فـ {url}")
            except Exception as exc:
                if attempt < 2:
                    await asyncio.sleep(attempt + 1)
                    continue
                print(f"[FETCH_JSON] Exception فـ {url}: {exc}")
        return {}
    
    
    async def fetch_html(url: str, headers: dict = None) -> str:
        """جيب HTML خام مع محاولة احتياطية للصورة ديال الخبر."""
        for attempt in range(2):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            return await resp.text(errors="ignore")
                        if resp.status in {429, 500, 502, 503, 504} and attempt == 0:
                            await asyncio.sleep(1)
                            continue
                        return ""
            except Exception as exc:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue
                print(f"[FETCH_HTML] Exception فـ {url}: {exc}")
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
        """ترجمة Auto-Info بموديل اقتصادي مخصص وLuna كاحتياط مدفوع."""
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
                    "بطريقة طبيعية وسلسة ومفهومة، وحافظ بدقة على الأسماء والأرقام والتواريخ "
                    "والمعنى الأصلي. غير الترجمة، بلا مقدمات، بلا تعليقات، بلا علامات تنصيص."
                )
            },
            {"role": "user", "content": text}
        ]
    
        translated, error = await call_openrouter_chat(
            messages,
            AUTO_INFO_TRANSLATION_MAX_TOKENS,
            0.2,
            primary_model=AUTO_INFO_AI_MODEL,
            fallback_models=AUTO_INFO_AI_FALLBACKS,
        )
    
        if error:
            print(f"[TRANSLATE] ❌ فشلو كاع الموديلات: {error}")
            return text
    
        translated = translated.strip()
        print(f"[TRANSLATE] ✅ قبل: '{text[:50]}' | بعد: '{translated[:50]}'")
        return translated if translated else text


    def normalize_content_key(text: str) -> str:
        """بصمة مستقرة للعناوين باش نفس المحتوى ما يرجعش برابط آخر."""
        cleaned = html.unescape(str(text or "")).casefold()
        cleaned = re.sub(r"[^\w\s]", " ", cleaned, flags=re.UNICODE)
        return re.sub(r"\s+", " ", cleaned).strip()[:300]


    _NEWS_TITLE_STOPWORDS = {
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
        "has", "have", "in", "is", "it", "of", "on", "or", "that", "the",
        "this", "to", "was", "were", "will", "with", "after", "new", "says",
    }


    def news_story_was_posted(title: str) -> bool:
        """كيمنع نفس القصة حتى إلا تبدل الناشر والصياغة شوية."""
        normalized = normalize_content_key(title)
        exact_key = f"title:{normalized}"
        if not normalized or is_posted("news", exact_key):
            return True
        candidate = {
            word for word in normalized.split()
            if len(word) > 2 and word not in _NEWS_TITLE_STOPWORDS
        }
        if len(candidate) < 3:
            return False
        for stored in posted_history.get("news", []):
            if not str(stored).startswith("title:"):
                continue
            previous = {
                word for word in str(stored)[6:].split()
                if len(word) > 2 and word not in _NEWS_TITLE_STOPWORDS
            }
            if len(previous) < 3:
                continue
            overlap = len(candidate & previous)
            union = len(candidate | previous)
            if union and overlap / union >= 0.62:
                return True
            if overlap / min(len(candidate), len(previous)) >= 0.80:
                return True
        return False


    def _safe_int(value, default=0) -> int:
        try:
            return int(str(value or "0").replace(",", ""))
        except (TypeError, ValueError):
            return default


    def _safe_float(value, default=0.0) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return default
    
    
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
    
        for page_attempt in range(6):
            params = {
                "api_key": TMDB_API_KEY,
                "language": "en-US",
                "sort_by": random.choice(["vote_average.desc", "popularity.desc"]),
                "vote_count.gte": AUTO_INFO_MOVIE_MIN_VOTES,
                "include_adult": "false",
                # أول الصفحات ديال الأعلى تقييماً/الأكثر شعبية: قديم وجديد بلا الرديء.
                "page": random.randint(1, 35),
            }
            data = await fetch_json(discover_url, params)
            results = data.get("results", []) if data else []
            if not results:
                continue
    
            random.shuffle(results)
    
            for movie in results[:15]:
                tmdb_id = movie.get("id")
                if not tmdb_id:
                    continue
                if _safe_float(movie.get("vote_average")) < AUTO_INFO_MOVIE_MIN_RATING:
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
                if _safe_float(rating) < AUTO_INFO_MOVIE_MIN_RATING:
                    continue

                imdb_votes = _safe_int(omdb_data.get("imdbVotes"))
                if imdb_votes < AUTO_INFO_MOVIE_MIN_VOTES:
                    continue
    
                plot = omdb_data.get("Plot", "No plot available.")
                plot_ar = await translate_to_darija(plot)
    
                poster = omdb_data.get("Poster", "")
                if not poster or poster == "N/A":
                    poster_path = movie.get("poster_path")
                    poster = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else ""
                if not poster:
                    poster = await get_wikipedia_image(f"{omdb_data.get('Title', '')} (film)")
                if not poster:
                    continue
    
                return {
                    "title": omdb_data.get("Title", "Unknown"),
                    "year": omdb_data.get("Year", "N/A"),
                    "genre": await translate_genres(omdb_data.get("Genre", "N/A")),
                    "plot": plot_ar,
                    "rating": rating,
                    "votes": imdb_votes,
                    "metascore": omdb_data.get("Metascore", "N/A"),
                    "poster": poster,
                    "imdb": f"https://www.imdb.com/title/{imdb_id}/",
                    "history_keys": [imdb_id],
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
    
        for page_attempt in range(6):
            if page_attempt > 0:
                await asyncio.sleep(1.5)  # نحترمو rate-limit ديال Jikan
    
            # Top 750 تقريباً، مع اختيار عشوائي باش القديم والجديد يبقاو مخلوطين.
            params = {"page": random.randint(1, 30), "limit": 25}
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
                if _safe_float(anime.get("score")) < AUTO_INFO_ANIME_MIN_SCORE:
                    continue
                # السيرفر احترافي ونظيف: محتوى Hentai/Rx ما كيدخلش للقناة.
                if str(anime.get("rating") or "").lower().startswith("rx"):
                    continue
    
                print(f"[JIKAN] ✅ اختار: {anime.get('title')} (score={anime.get('score')})")
                built = await _build_anime_embed_data(anime)
                if built:
                    return built
    
            print(f"[JIKAN] محاولة {page_attempt+1}: كاع نتائج الصفحة مبعوتين من قبل ولا بلا synopsis")
    
        print("[JIKAN] ❌ ماكاينش نتيجة بعد كل المحاولات")
        return {}
    
    
    async def _build_anime_embed_data(anime: dict) -> dict:
        """يبني الـ dict الجاهز للـ embed انطلاقا من داتا أنمي جاية من Jikan"""
        mal_id = anime.get("mal_id")
        poster = anime.get("images", {}).get("jpg", {}).get("large_image_url", "")
        if not poster:
            poster = await get_wikipedia_image(f"{anime.get('title', '')} (anime)")
        if not poster:
            return {}

        synopsis = anime.get("synopsis") or "No synopsis available."
        synopsis_ar = await translate_to_darija(synopsis)
    
        return {
            "title": anime.get("title", "Unknown"),
            "title_jp": anime.get("title_japanese", ""),
            "type": anime.get("type", "TV"),
            "episodes": anime.get("episodes", "N/A"),
            "genres": await translate_genres(", ".join([g["name"] for g in anime.get("genres", [])])),
            "synopsis": synopsis_ar,
            "score": anime.get("score", 0),
            "rank": anime.get("rank") or "N/A",
            "scored_by": _safe_int(anime.get("scored_by")),
            "poster": poster,
            "url": anime.get("url", ""),
            "history_keys": [str(mal_id)],
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
    
        for page_attempt in range(6):
            params = {
                "key": RAWG_API_KEY,
                "ordering": random.choice(["-rating", "-metacritic", "-added"]),
                "metacritic": "70,100",
                "page_size": 40,
                "page": random.randint(1, 50),
            }
            data = await fetch_json(list_url, params)
            results = data.get("results", []) if data else []
            if not results:
                continue
    
            random.shuffle(results)
    
            for game in results[:15]:
                slug = game.get("slug")
                rating = _safe_float(game.get("rating"))
                ratings_count = _safe_int(game.get("ratings_count"))
                if (
                    not slug
                    or is_posted("games", slug)
                    or rating < AUTO_INFO_GAME_MIN_RATING
                    or ratings_count < AUTO_INFO_GAME_MIN_RATINGS_COUNT
                ):
                    continue
    
                detail = await fetch_json(f"{list_url}/{slug}", {"key": RAWG_API_KEY})
                if not detail or not detail.get("name"):
                    continue
    
                description = detail.get("description_raw", "No description available.")[:500]
                description_ar = await translate_to_darija(description)
    
                poster = detail.get("background_image", "")
                if not poster:
                    poster = await get_wikipedia_image(f"{detail.get('name', '')} (video game)")
                if not poster:
                    continue

                detail_rating = _safe_float(detail.get("rating"), rating)
                detail_ratings_count = _safe_int(detail.get("ratings_count"), ratings_count)
    
                return {
                    "name": detail.get("name", "Unknown"),
                    "released": detail.get("released", "N/A"),
                    "genres": await translate_genres(", ".join([g["name"] for g in detail.get("genres", [])])),
                    "description": description_ar,
                    "rating": detail_rating,
                    "ratings_count": detail_ratings_count,
                    "metacritic": detail.get("metacritic") or game.get("metacritic") or "N/A",
                    "poster": poster,
                    "url": f"https://rawg.io/games/{slug}",
                    "history_keys": [slug],
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
    
        url = "https://ws.audioscrobbler.com/2.0/"
    
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
                    if not is_posted(
                        "music",
                        f"track:{normalize_content_key(artist + ' ' + str(t.get('name', '')))}",
                    )
                ]
                if not fresh_tracks:
                    continue  # كاع الأغاني ديال هاد الفنان تبعثاو، نجربو فنان آخر
    
                track = random.choice(fresh_tracks)
                listeners_str = track.get("listeners", "0")
                try:
                    listeners = int(listeners_str)
                except (ValueError, TypeError):
                    listeners = 0
    
                poster = await get_track_artwork(artist, track.get("name", ""))
                if not poster:
                    poster = await get_wikipedia_image(artist)
                if not poster:
                    continue

                playcount = _safe_int(track.get("playcount"))
                rank = _safe_int(track.get("@attr", {}).get("rank"))
                history_key = f"track:{normalize_content_key(artist + ' ' + str(track.get('name', '')))}"
    
                return {
                    "name": track.get("name", "Unknown"),
                    "artist": artist,
                    "listeners": listeners,
                    "playcount": playcount,
                    "rank": rank or "N/A",
                    "url": track.get("url", ""),
                    "poster": poster,
                    "history_keys": [history_key],
                }
    
        # إلا سالاو الاختيارات الحالية كنستناو chart يتجدد؛ ما نعاودو حتى أغنية.
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
    
            # URL + بصمة العنوان كيمنعو نفس القصة ترجع من رابط/ناشر آخر.
            valid_articles = [
                a for a in data["articles"]
                if a.get("title") and a.get("title") != "[Removed]"
                and a.get("url") and not is_posted("news", a["url"])
                and not news_story_was_posted(a.get("title", ""))
            ]
            if not valid_articles:
                continue

            random.shuffle(valid_articles)
            for article in valid_articles[:8]:
                image = article.get("urlToImage", "")
                if not image:
                    image = await get_og_image(article.get("url", ""))
                # القناة احترافية وبالصور: المقال بلا صورة كيتفوت وما كيتنشرش ناقص.
                if not image:
                    continue

                original_title = article.get("title", "Unknown")
                original_desc = article.get("description") or article.get("content") or original_title
                title_ar = await translate_to_darija(original_title)
                desc_ar = await translate_to_darija(original_desc)
                title_key = f"title:{normalize_content_key(original_title)}"

                return {
                    "title": title_ar,
                    "description": desc_ar,
                    "url": article.get("url", ""),
                    "source": article.get("source", {}).get("name", "Unknown"),
                    "published_at": article.get("publishedAt", ""),
                    "image": image,
                    "history_keys": [article["url"], title_key],
                }
    
        # ماكاينش خبر جديد دابا فـ كاع الفئات، غادي نعاودو نجربو فـ الدورة الجاية
        return {}
    
    
# ORIGINAL SOURCE END
else:
    async def setup(bot):
        install_component(bot, __file__, __name__)

    async def teardown(bot):
        uninstall_component(__name__)
