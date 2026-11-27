import logging
import os
import re
import subprocess
from datetime import datetime, timezone

from sqlalchemy import select

from app.config import settings
from app.db import Actor, Genre, Movie, MovieActor, SessionLocal
from app.filenames import ParsedName, has_cyrillic, parse_release
from app.matching import classify, normalize, score_match, yo_variants
from app.paths import parent_dir_name
from app.posters import fetch_poster, remove_poster, save_poster
from app.providers import KpClient, OllamaClient, TmdbClient
from app.translit import ordered_queries, should_try_alternate

logger = logging.getLogger(__name__)
_JUNK_IN_TITLE = re.compile(r"(?i)bdrip|web-?dl|hdrip|1080p|x264|x265")


def probe_duration(path: str) -> int | None:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("ffprobe %s: %s", path, exc)
        return None
    try:
        value = float((result.stdout or "").strip())
    except ValueError:
        return None
    if value <= 0:
        return None
    return int(round(value))


def _year_from_date(value: str | None) -> int | None:
    if value and len(value) >= 4 and value[:4].isdigit():
        year = int(value[:4])
        if 1888 <= year <= 2035:
            return year
    return None


def _valid_year(value) -> int | None:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    if 1888 <= year <= 2035:
        return year
    return None


def _rating(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return round(number, 1)


def merge_title(file_name: str, parent: str, llm: dict | None) -> ParsedName:
    fallback = parse_release(file_name, parent)
    if not llm:
        return fallback
    title = str(llm.get("title") or "").strip()
    if not title or _JUNK_IN_TITLE.search(title):
        title = fallback.title
    year = fallback.year if fallback.year is not None else _valid_year(llm.get("year"))
    return ParsedName(title or fallback.title, year)


def _english_title(details: dict, original_title: str, original_language: str) -> str:
    if original_language == "en" and original_title:
        return original_title
    for item in (details.get("translations") or {}).get("translations") or []:
        if item.get("iso_639_1") != "en":
            continue
        title = ((item.get("data") or {}).get("title") or "").strip()
        if title:
            return title
    return original_title or ""


def _rank_tmdb(results: list[dict], title: str, year: int | None) -> list[tuple[float, dict]]:
    scored: list[tuple[float, dict]] = []
    for item in results:
        cand_year = _year_from_date(item.get("release_date"))
        score = score_match(
            title,
            year,
            [item.get("title") or "", item.get("original_title") or ""],
            cand_year,
        )
        scored.append((score, item))
    scored.sort(key=lambda row: row[0], reverse=True)
    return scored


def _confident(scored: list[tuple[float, dict]]) -> bool:
    if not scored:
        return False
    second = scored[1][0] if len(scored) > 1 else None
    return classify(scored[0][0], second) == "matched"


def _widen_year(
    tmdb: TmdbClient,
    query: str,
    title: str,
    year: int | None,
    scored: list[tuple[float, dict]],
) -> list[tuple[float, dict]]:
    if not year or not scored or scored[0][0] >= 0.75:
        return scored
    wider = _rank_tmdb(tmdb.search(query, None), title, year)
    if wider and wider[0][0] > scored[0][0]:
        return wider
    return scored


def _choose_tmdb_one(tmdb: TmdbClient, title: str, year: int | None) -> tuple[str, dict | None, float | None]:
    scored = _rank_tmdb(tmdb.search(title, year), title, year)
    if year and (not scored or scored[0][0] < 0.75):
        wider = _rank_tmdb(tmdb.search(title, None), title, year)
        if wider and (not scored or wider[0][0] > scored[0][0]):
            scored = wider
    # TMDB хранит «е» и «ё» как разные буквы: «Зеленая книга» не находит «Зелёная книга».
    if not _confident(scored):
        for variant in yo_variants(title):
            alt = _widen_year(tmdb, variant, title, year, _rank_tmdb(tmdb.search(variant, year), title, year))
            if alt and (not scored or alt[0][0] > scored[0][0]):
                scored = alt
            if _confident(scored):
                break
    if not scored:
        return "failed", None, None
    best_score, best = scored[0]
    second = scored[1][0] if len(scored) > 1 else None
    return classify(best_score, second), best, best_score


def choose_tmdb(tmdb: TmdbClient, title: str, year: int | None) -> tuple[str, dict | None, float | None]:
    queries = ordered_queries(title)
    if not queries:
        return "failed", None, None
    status, candidate, score = _choose_tmdb_one(tmdb, queries[0], year)
    if len(queries) < 2 or not should_try_alternate(title, score):
        return status, candidate, score
    alt_status, alt_candidate, alt_score = _choose_tmdb_one(tmdb, queries[1], year)
    if alt_score is not None and (score is None or alt_score > score):
        return alt_status, alt_candidate, alt_score
    return status, candidate, score


def tmdb_bridge_query(parsed_title: str, title_en: str | None, tmdb_id) -> str | None:
    if tmdb_id is not None:
        return None
    bridge = (title_en or "").strip()
    if not bridge:
        return None
    tried = {normalize(query) for query in ordered_queries(parsed_title)}
    if normalize(bridge) in tried:
        return None
    return bridge


def _prefer_overview(current: str | None, incoming: str | None) -> str | None:
    current_text = (current or "").strip()
    incoming_text = (incoming or "").strip()[:8000]
    if not incoming_text:
        return current_text or None
    if not current_text:
        return incoming_text
    current_ru = has_cyrillic(current_text)
    incoming_ru = has_cyrillic(incoming_text)
    if incoming_ru and not current_ru:
        return incoming_text
    if current_ru and not incoming_ru:
        return current_text
    if len(incoming_text) > len(current_text):
        return incoming_text
    return current_text


def _kp_text(doc: dict) -> str:
    description = (doc.get("description") or "").strip()
    short = (doc.get("shortDescription") or "").strip()
    for text in (description, short):
        if has_cyrillic(text):
            return text[:8000]
    return (description or short)[:8000]


def choose_kp(docs: list[dict], title: str, year: int | None) -> tuple[dict | None, float | None, float | None]:
    scored: list[tuple[float, dict]] = []
    for doc in docs:
        if doc.get("isSeries"):
            continue
        cand_year = doc.get("year") if isinstance(doc.get("year"), int) else None
        score = score_match(
            title,
            year,
            [doc.get("name") or "", doc.get("alternativeName") or "", doc.get("enName") or ""],
            cand_year,
        )
        scored.append((score, doc))
    scored.sort(key=lambda row: row[0], reverse=True)
    if not scored or scored[0][0] < 0.58:
        return None, None, scored[0][0] if scored else None
    second = scored[1][0] if len(scored) > 1 else None
    return scored[0][1], scored[0][0], second


def _search_title(title_ru: str | None, title_en: str | None, parsed: str) -> str:
    if has_cyrillic(title_ru):
        return title_ru or ""
    if has_cyrillic(parsed):
        return parsed
    return title_en or parsed or title_ru or ""


def _get_genre(db, name: str, tmdb_id: int | None) -> Genre | None:
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    genre = None
    if tmdb_id:
        genre = db.scalar(select(Genre).where(Genre.tmdb_id == tmdb_id))
    if genre is None:
        genre = db.scalar(select(Genre).where(Genre.name == cleaned))
    if genre is None:
        genre = Genre(name=cleaned, tmdb_id=tmdb_id)
        db.add(genre)
        db.flush()
        return genre
    if tmdb_id and genre.tmdb_id is None:
        genre.tmdb_id = tmdb_id
    return genre


def _get_actor(db, name: str, person_id: int | None, popularity) -> Actor | None:
    cleaned = (name or "").strip()
    if not cleaned:
        return None
    actor = None
    if person_id:
        actor = db.scalar(select(Actor).where(Actor.tmdb_person_id == person_id))
    if actor is None:
        actor = db.scalar(
            select(Actor).where(Actor.name == cleaned, Actor.tmdb_person_id.is_(None))
        )
    if actor is None:
        actor = Actor(name=cleaned, tmdb_person_id=person_id)
        db.add(actor)
    elif person_id and actor.tmdb_person_id is None:
        actor.tmdb_person_id = person_id
    if popularity is not None:
        try:
            actor.popularity = float(popularity)
        except (TypeError, ValueError):
            pass
    db.flush()
    return actor


def _store_poster(http, movie: Movie, url: str | None) -> None:
    content = fetch_poster(http, url)
    if not content:
        return
    remove_poster(movie.poster_path)
    movie.poster_path = save_poster(movie.id, content)


def _apply_kp(db, http, movie: Movie, doc: dict, allow_status_upgrade: bool, second_score: float | None, score: float) -> None:
    name = (doc.get("name") or "").strip()
    en_name = (doc.get("enName") or doc.get("alternativeName") or "").strip()
    if name and (not movie.title_ru or (has_cyrillic(name) and not has_cyrillic(movie.title_ru))):
        movie.title_ru = name
    if en_name and not movie.title_en:
        movie.title_en = en_name
    overview = _prefer_overview(movie.overview_ru, _kp_text(doc))
    if overview:
        movie.overview_ru = overview
    rating = _rating((doc.get("rating") or {}).get("kp"))
    if rating is not None:
        movie.rating_kp = rating
    if isinstance(doc.get("id"), int):
        movie.kp_id = doc["id"]
    if movie.year is None and isinstance(doc.get("year"), int):
        movie.year = doc["year"]
    if movie.duration_sec is None and isinstance(doc.get("movieLength"), int) and doc["movieLength"] > 0:
        movie.duration_sec = doc["movieLength"] * 60
    poster = (doc.get("poster") or {}).get("url") or (doc.get("poster") or {}).get("previewUrl")
    if poster and not movie.poster_path:
        _store_poster(http, movie, poster)
    if allow_status_upgrade and movie.status == "failed":
        movie.status = classify(score, second_score)
        movie.confidence = round(score, 3)
        if movie.status != "failed":
            movie.error = None


def _apply_tmdb_details(db, http, movie: Movie, details: dict, status: str, score: float) -> str:
    original_language = details.get("original_language") or ""
    tmdb_title = (details.get("title") or "").strip()
    original_title = (details.get("original_title") or "").strip()
    title_en = _english_title(details, original_title, original_language)
    if original_language == "ru" or has_cyrillic(tmdb_title):
        movie.title_ru = tmdb_title
    elif not title_en:
        title_en = tmdb_title
    if title_en:
        movie.title_en = title_en
    overview = (details.get("overview") or "").strip()
    if has_cyrillic(overview):
        chosen = _prefer_overview(movie.overview_ru, overview)
        if chosen:
            movie.overview_ru = chosen
    movie.tmdb_id = details.get("id")
    movie.rating_tmdb = _rating(details.get("vote_average"))
    if movie.year is None:
        movie.year = _year_from_date(details.get("release_date"))
    if movie.duration_sec is None and isinstance(details.get("runtime"), int) and details["runtime"] > 0:
        movie.duration_sec = details["runtime"] * 60
    movie.status = status
    movie.confidence = round(score, 3)
    movie.error = None
    movie.genres.clear()
    movie.cast_entries.clear()
    db.flush()
    for genre in details.get("genres") or []:
        row = _get_genre(db, genre.get("name") or "", genre.get("id"))
        if row is not None and row not in movie.genres:
            movie.genres.append(row)
    seen: set[int] = set()
    people = list((details.get("credits") or {}).get("cast") or [])
    people.sort(key=lambda person: person.get("order") if person.get("order") is not None else 999)
    for person in people[:20]:
        actor = _get_actor(db, person.get("name") or "", person.get("id"), person.get("popularity"))
        if actor is None or actor.id in seen:
            continue
        seen.add(actor.id)
        order = person.get("order") if isinstance(person.get("order"), int) else len(seen)
        db.add(
            MovieActor(
                movie=movie,
                actor=actor,
                billing_order=order,
                character_name=(person.get("character") or "")[:300] or None,
                is_lead=order < 5,
            )
        )
    _store_poster(http, movie, details.get("poster_path"))
    if overview and not has_cyrillic(overview):
        return overview
    return ""


def _media_path(movie: Movie) -> str | None:
    mounts = {share.name: share.mount for share in settings.shares}
    root = mounts.get(movie.share_name)
    if not root:
        return None
    return os.path.join(root, *movie.relative_path.split("/"))


def enrich_movie(movie_id: int, ollama: OllamaClient, tmdb: TmdbClient, kp: KpClient, http) -> str:
    db = SessionLocal()
    try:
        movie = db.get(Movie, movie_id)
        if movie is None:
            return "missing"
        movie.scanned_at = datetime.now(timezone.utc)
        path = _media_path(movie)
        if path and os.path.isfile(path) and movie.duration_sec is None:
            movie.duration_sec = probe_duration(path)
        kp_only = movie.status in {"matched", "ambiguous"} and not movie.kp_checked
        if kp_only:
            _fill_kp(db, http, movie, kp, allow_status_upgrade=False)
            movie.enriched_at = datetime.now(timezone.utc)
            db.commit()
            return movie.status

        parent = parent_dir_name(movie.relative_path)
        parsed = merge_title(movie.file_name, parent, ollama.parse_filename(movie.file_name, parent))
        if not movie.title_ru:
            movie.title_ru = parsed.title or movie.file_name
        if movie.year is None:
            movie.year = parsed.year

        status, candidate, score = choose_tmdb(tmdb, parsed.title, parsed.year)
        english_overview = ""
        if candidate and status != "failed":
            details = tmdb.details(candidate["id"])
            if details:
                english_overview = _apply_tmdb_details(db, http, movie, details, status, score or 0)
            else:
                status = "failed"
        if status == "failed":
            movie.status = "failed"
            movie.confidence = round(score, 3) if score is not None else None
            movie.error = "Не удалось уверенно сопоставить название"
            if has_cyrillic(parsed.title):
                movie.title_ru = parsed.title
            elif parsed.title and not movie.title_en:
                movie.title_en = parsed.title
            if movie.year is None:
                movie.year = parsed.year

        _fill_kp(db, http, movie, kp, allow_status_upgrade=True)
        bridge = tmdb_bridge_query(parsed.title, movie.title_en, movie.tmdb_id)
        if bridge:
            bridged, bridged_hit, bridged_score = choose_tmdb(tmdb, bridge, movie.year)
            if bridged_hit and bridged == "matched":
                details = tmdb.details(bridged_hit["id"])
                if details:
                    english_overview = _apply_tmdb_details(
                        db, http, movie, details, bridged, bridged_score or 0
                    ) or english_overview
        if not movie.overview_ru and english_overview:
            movie.overview_ru = english_overview[:8000]
        if not movie.title_ru and not movie.title_en:
            if has_cyrillic(parsed.title):
                movie.title_ru = parsed.title
            else:
                movie.title_en = parsed.title or movie.file_name
        movie.enriched_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "%s → %s (%s)",
            movie.file_name,
            movie.status,
            movie.title_ru or movie.title_en,
        )
        return movie.status
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _fill_kp(db, http, movie: Movie, kp: KpClient, allow_status_upgrade: bool) -> None:
    if kp.disabled:
        return
    query = _search_title(movie.title_ru, movie.title_en, parse_release(movie.file_name).title)
    queries = ordered_queries(query)
    if not queries:
        return
    best_hit = None
    best_score = None
    best_second = None
    best_raw = None
    completed_any = False
    for index, variant in enumerate(queries):
        if index and not should_try_alternate(query, best_raw):
            break
        docs, completed = kp.search(variant)
        if not completed:
            break
        completed_any = True
        hit, score, extra = choose_kp(docs, variant, movie.year)
        raw = score if hit is not None else extra
        if index == 0:
            best_raw = raw
        if hit is not None and score is not None and (best_score is None or score > best_score):
            best_hit, best_score, best_second = hit, score, extra
            best_raw = score
    if not completed_any:
        return
    movie.kp_checked = True
    if best_hit is None or best_score is None:
        return
    _apply_kp(db, http, movie, best_hit, allow_status_upgrade, best_second, best_score)


def mark_failed(movie_id: int, message: str) -> None:
    db = SessionLocal()
    try:
        movie = db.get(Movie, movie_id)
        if movie is None:
            return
        movie.status = "failed"
        movie.error = message[:500]
        movie.enriched_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
