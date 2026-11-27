import logging
import os
import threading
from datetime import datetime, timezone

import httpx
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.cards import clear_movie_card
from app.config import settings
from app.db import Movie, SessionLocal
from app.enrich import enrich_movie, mark_failed
from app.posters import remove_poster
from app.providers import KpClient, OllamaClient, TmdbClient
from app.scanner import iter_videos, upsert_file

logger = logging.getLogger(__name__)


class ScanState:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._data = {
            "running": False,
            "phase": "idle",
            "found": 0,
            "skipped": 0,
            "total": 0,
            "enriched": 0,
            "failed": 0,
            "current_file": None,
            "last_error": None,
            "started_at": None,
            "finished_at": None,
        }

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._data)

    def update(self, **kwargs) -> None:
        with self._lock:
            self._data.update(kwargs)

    def try_start(self, phase: str = "scanning") -> bool:
        with self._lock:
            if self._data["running"]:
                return False
            self._data.update(
                running=True,
                phase=phase,
                found=0,
                skipped=0,
                total=0,
                enriched=0,
                failed=0,
                current_file=None,
                last_error=None,
                started_at=_now(),
                finished_at=None,
            )
            return True


STATE = ScanState()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _note_error(message: str) -> None:
    logger.warning(message)
    STATE.update(last_error=message[:300])


def _walk_share(share) -> tuple[set[int], bool]:
    if not os.path.isdir(share.mount):
        _note_error(f"Шара {share.name} не смонтирована: {share.mount}")
        return set(), False
    errors: list[OSError] = []
    seen: set[int] = set()
    for found in iter_videos(share.mount, errors):
        movie_id, status, changed = upsert_file(share.name, found)
        seen.add(movie_id)
        snapshot = STATE.snapshot()
        skipped = snapshot["skipped"] + (0 if changed or status not in {"matched", "ambiguous"} else 1)
        STATE.update(found=snapshot["found"] + 1, skipped=skipped, current_file=found.relative_path)
    if errors:
        _note_error(f"Шара {share.name}: часть каталогов не прочитана, старые записи сохранены")
        return seen, False
    return seen, True


def _delete_missing(share_name: str, seen: set[int]) -> None:
    db = SessionLocal()
    try:
        stmt = select(Movie).where(Movie.share_name == share_name)
        if seen:
            stmt = stmt.where(Movie.id.not_in(seen))
        for movie in db.scalars(stmt):
            remove_poster(movie.poster_path)
            db.delete(movie)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _queue_ids() -> list[int]:
    clauses = [Movie.status.in_(["pending", "failed"])]
    if settings.kp_api_key:
        clauses.append(
            and_(
                Movie.kp_checked.is_(False),
                Movie.status.in_(["matched", "ambiguous"]),
            )
        )
    db = SessionLocal()
    try:
        return list(db.scalars(select(Movie.id).where(or_(*clauses)).order_by(Movie.id)))
    finally:
        db.close()


def _label(movie_id: int) -> str:
    db = SessionLocal()
    try:
        movie = db.get(Movie, movie_id)
        if movie is None:
            return str(movie_id)
        return movie.relative_path
    finally:
        db.close()


def _enrich_queue(movie_ids: list[int]) -> None:
    STATE.update(phase="enriching", total=len(movie_ids), current_file=None)
    if not movie_ids:
        return
    with httpx.Client(
        timeout=30,
        follow_redirects=True,
        headers={"User-Agent": "video-catalog/1.0"},
    ) as http:
        ollama = OllamaClient(http, settings.ollama_host, settings.ollama_model)
        tmdb = TmdbClient(http, settings.tmdb_api_key, settings.tmdb_delay)
        kp = KpClient(http, settings.kp_api_key, settings.kp_delay)
        for movie_id in movie_ids:
            STATE.update(current_file=_label(movie_id))
            try:
                status = enrich_movie(movie_id, ollama, tmdb, kp, http)
            except Exception as exc:
                logger.exception("карточка %s", movie_id)
                mark_failed(movie_id, str(exc))
                status = "failed"
                _note_error(str(exc))
            snapshot = STATE.snapshot()
            if status == "failed":
                STATE.update(failed=snapshot["failed"] + 1)
            elif status in {"matched", "ambiguous"}:
                STATE.update(enriched=snapshot["enriched"] + 1)


def _run() -> None:
    try:
        if not settings.tmdb_api_key:
            _note_error("TMDB_API_KEY пуст: русские карточки будут только из Кинопоиска")
        for share in settings.shares:
            seen, complete = _walk_share(share)
            if complete:
                _delete_missing(share.name, seen)
        _enrich_queue(_queue_ids())
        if STATE.snapshot()["phase"] != "error":
            STATE.update(phase="done")
    except Exception as exc:
        logger.exception("скан остановился")
        STATE.update(phase="error")
        _note_error(str(exc))
    finally:
        STATE.update(running=False, finished_at=_now(), current_file=None)


def start_scan() -> dict:
    if not STATE.try_start():
        return STATE.snapshot()
    threading.Thread(target=_run, name="vharvest-scan", daemon=True).start()
    return STATE.snapshot()


def _reset_cards(ids: list[int]) -> tuple[list[int], list[int]]:
    db = SessionLocal()
    try:
        movies = db.scalars(
            select(Movie)
            .where(Movie.id.in_(ids))
            .options(selectinload(Movie.genres), selectinload(Movie.cast_entries))
        ).all()
        found = {movie.id: movie for movie in movies}
        reset: list[int] = []
        missing: list[int] = []
        for movie_id in ids:
            movie = found.get(movie_id)
            if movie is None:
                missing.append(movie_id)
                continue
            remove_poster(movie.poster_path)
            movie.poster_path = None
            movie.genres.clear()
            movie.cast_entries.clear()
            clear_movie_card(movie)
            reset.append(movie_id)
        db.commit()
        return reset, missing
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _enrich_only(movie_ids: list[int]) -> None:
    try:
        _enrich_queue(movie_ids)
        if STATE.snapshot()["phase"] != "error":
            STATE.update(phase="done")
    except Exception as exc:
        logger.exception("повторный разбор остановился")
        STATE.update(phase="error")
        _note_error(str(exc))
    finally:
        STATE.update(running=False, finished_at=_now(), current_file=None)


def start_reset(movie_ids: list[int]) -> dict | None:
    ids = list(dict.fromkeys(movie_ids))
    if not STATE.try_start(phase="enriching"):
        return None
    try:
        reset, missing = _reset_cards(ids)
    except Exception:
        STATE.update(running=False, phase="error", finished_at=_now())
        raise
    if not reset:
        STATE.update(running=False, phase="idle", finished_at=_now(), current_file=None)
    payload = STATE.snapshot()
    payload["reset"] = reset
    payload["missing"] = missing
    if reset:
        threading.Thread(
            target=_enrich_only,
            args=(reset,),
            name="vharvest-reset",
            daemon=True,
        ).start()
    return payload


def needs_initial_scan() -> bool:
    db = SessionLocal()
    try:
        total = db.scalar(select(func.count()).select_from(Movie)) or 0
        if total == 0:
            return True
        pending = db.scalar(
            select(func.count()).select_from(Movie).where(Movie.status == "pending")
        ) or 0
        if pending:
            return True
        if not settings.kp_api_key:
            return False
        unchecked = db.scalar(
            select(func.count()).select_from(Movie).where(
                Movie.kp_checked.is_(False),
                Movie.status.in_(["matched", "ambiguous"]),
            )
        ) or 0
        return unchecked > 0
    finally:
        db.close()
