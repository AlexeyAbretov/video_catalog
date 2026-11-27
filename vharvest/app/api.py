import os
import secrets
from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import false, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.db import Actor, Genre, Movie, MovieActor, SessionLocal, movie_genres
from app.filenames import parse_release, year_conflicts
from app.paths import parent_dir_name, parent_relative, playlist_filename, smb_dir_url, smb_url, unc_path
from app.posters import openable_poster
from app.scan_service import STATE, start_reset, start_scan

router = APIRouter(prefix="/api")

_POSTER_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def _attachment(name: str) -> str:
    ascii_name = "".join(ch if 32 < ord(ch) < 127 and ch not in '"\\' else "_" for ch in name)
    if not any(ch.isalnum() for ch in ascii_name):
        ascii_name = "movie.m3u"
    encoded = quote(name, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _authorized(authorization: str | None) -> bool:
    if not authorization or not settings.scan_token or not authorization.startswith("Bearer "):
        return False
    token = authorization.removeprefix("Bearer ").strip()
    if len(token) != len(settings.scan_token):
        return False
    return secrets.compare_digest(token, settings.scan_token)


def _num(value):
    if value is None:
        return None
    return float(value)


def _poster_url(movie: Movie) -> str | None:
    path = openable_poster(movie.poster_path)
    if path is None:
        return None
    try:
        version = int(os.path.getmtime(path))
    except OSError:
        version = 0
    return f"/api/movies/{movie.id}/poster?v={version}"


def _genres(movie: Movie) -> list[dict]:
    return [{"id": genre.id, "name": genre.name} for genre in sorted(movie.genres, key=lambda item: item.name)]


def _paths(movie: Movie) -> dict:
    folder = parent_relative(movie.relative_path)
    return {
        "unc_path": unc_path(settings.smb_host, movie.share_name, movie.relative_path),
        "folder_unc": unc_path(settings.smb_host, movie.share_name, folder),
        "smb_url": smb_url(settings.smb_host, movie.share_name, movie.relative_path),
        "folder_smb_url": smb_dir_url(settings.smb_host, movie.share_name, folder),
    }


def _file_year(movie: Movie) -> int | None:
    return parse_release(movie.file_name, parent_dir_name(movie.relative_path) or None).year


def _card(movie: Movie) -> dict:
    return {
        "id": movie.id,
        "title_ru": movie.title_ru,
        "title_en": movie.title_en,
        "year": movie.year,
        "file_year": _file_year(movie),
        "duration_sec": movie.duration_sec,
        "rating_tmdb": _num(movie.rating_tmdb),
        "rating_kp": _num(movie.rating_kp),
        "status": movie.status,
        "poster_url": _poster_url(movie),
        "genres": _genres(movie),
        "file_name": movie.file_name,
        "share_name": movie.share_name,
    }


def _popular_ids(entries: list[MovieActor]) -> set[int]:
    ranked = sorted(entries, key=lambda entry: entry.actor.popularity or 0, reverse=True)
    picked: list[int] = []
    for entry in ranked:
        if (entry.actor.popularity or 0) >= 5 and len(picked) < 3:
            picked.append(entry.actor_id)
    return set(picked)


def _apply_filters(stmt, year_from: int | None, year_to: int | None, genre_ids: list[int], actor_ids: list[int]):
    if year_from is not None:
        stmt = stmt.where(Movie.year >= year_from)
    if year_to is not None:
        stmt = stmt.where(Movie.year <= year_to)
    if genre_ids:
        stmt = stmt.where(
            Movie.id.in_(
                select(movie_genres.c.movie_id).where(movie_genres.c.genre_id.in_(genre_ids))
            )
        )
    if actor_ids:
        stmt = stmt.where(
            Movie.id.in_(select(MovieActor.movie_id).where(MovieActor.actor_id.in_(actor_ids)))
        )
    return stmt


def _incomplete_card():
    return or_(
        Movie.poster_path.is_(None),
        Movie.overview_ru.is_(None),
        func.trim(Movie.overview_ru) == "",
        Movie.year.is_(None),
        Movie.duration_sec.is_(None),
        Movie.rating_kp.is_(None),
        Movie.rating_tmdb.is_(None),
        Movie.tmdb_id.is_(None),
        Movie.kp_id.is_(None),
        ~Movie.genres.any(),
        ~Movie.cast_entries.any(),
    )


def _narrow(stmt, year_from, year_to, genre_ids, actor_ids, incomplete: bool):
    stmt = _apply_filters(stmt, year_from, year_to, genre_ids, actor_ids)
    if incomplete:
        stmt = stmt.where(_incomplete_card())
    return stmt


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(select(func.now()))
    return {"ok": True}


@router.get("/scan/status")
def scan_status():
    return STATE.snapshot()


@router.post("/scan")
def scan(authorization: str | None = Header(default=None)):
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="Нужен заголовок Authorization: Bearer")
    return start_scan()


class ResetRequest(BaseModel):
    ids: list[Annotated[int, Field(ge=1)]] = Field(min_length=1, max_length=100)


@router.post("/movies/reset")
def reset_movies(body: ResetRequest, authorization: str | None = Header(default=None)):
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="Нужен заголовок Authorization: Bearer")
    result = start_reset(body.ids)
    if result is None:
        raise HTTPException(status_code=409, detail="Уже идёт разбор")
    return result


@router.get("/genres")
def genres(db: Session = Depends(get_db)):
    rows = db.scalars(select(Genre).order_by(Genre.name)).all()
    return [{"id": row.id, "name": row.name} for row in rows]


@router.get("/years")
def years(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(Movie.year).where(Movie.year.is_not(None)).distinct().order_by(Movie.year.desc())
    ).all()
    return list(rows)


@router.get("/actors")
def actors(
    db: Session = Depends(get_db),
    q: str | None = None,
    id: list[int] = Query(default=[]),
):
    if id:
        rows = db.scalars(select(Actor).where(Actor.id.in_(id)).order_by(Actor.name)).all()
    else:
        text = (q or "").strip()
        if len(text) < 2:
            return []
        escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = db.scalars(
            select(Actor)
            .where(Actor.name.ilike(f"%{escaped}%", escape="\\"))
            .order_by(Actor.popularity.desc().nulls_last(), Actor.name)
            .limit(20)
        ).all()
    return [{"id": row.id, "name": row.name} for row in rows]


@router.get("/movies")
def movies(
    db: Session = Depends(get_db),
    year_from: int | None = None,
    year_to: int | None = None,
    genre_id: list[int] = Query(default=[]),
    actor_id: list[int] = Query(default=[]),
    incomplete: bool = False,
    year_mismatch: bool = False,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=24, ge=1, le=60),
):
    if year_from is not None and year_to is not None and year_from > year_to:
        year_from, year_to = year_to, year_from
    filtered = _narrow(select(Movie), year_from, year_to, genre_id, actor_id, incomplete)
    if year_mismatch:
        rows = db.execute(
            _narrow(
                select(Movie.id, Movie.year, Movie.file_name, Movie.relative_path),
                year_from,
                year_to,
                genre_id,
                actor_id,
                incomplete,
            )
        ).all()
        ids = [
            row.id
            for row in rows
            if year_conflicts(row.file_name, parent_dir_name(row.relative_path), row.year)
        ]
        filtered = select(Movie).where(Movie.id.in_(ids)) if ids else select(Movie).where(false())
    total = db.scalar(select(func.count()).select_from(filtered.subquery())) or 0
    rows = db.scalars(
        filtered.options(selectinload(Movie.genres))
        .order_by(Movie.year.desc().nulls_last(), Movie.title_ru.asc().nulls_last(), Movie.file_name.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    ).all()
    pages = max(1, (total + limit - 1) // limit) if total else 1
    return {"total": total, "page": page, "pages": pages, "items": [_card(movie) for movie in rows]}


@router.get("/movies/{movie_id}")
def movie_detail(movie_id: int, db: Session = Depends(get_db)):
    movie = db.scalar(
        select(Movie)
        .options(
            selectinload(Movie.genres),
            selectinload(Movie.cast_entries).selectinload(MovieActor.actor),
        )
        .where(Movie.id == movie_id)
    )
    if movie is None:
        raise HTTPException(status_code=404, detail="Фильм не найден")
    popular = _popular_ids(movie.cast_entries)
    actors_out = []
    for entry in sorted(movie.cast_entries, key=lambda item: item.billing_order):
        actors_out.append(
            {
                "id": entry.actor.id,
                "name": entry.actor.name,
                "character": entry.character_name,
                "is_lead": entry.is_lead,
                "popular": entry.actor_id in popular,
                "billing_order": entry.billing_order,
            }
        )
    payload = _card(movie)
    payload.update(
        {
            "overview_ru": movie.overview_ru,
            "confidence": _num(movie.confidence),
            "error": movie.error,
            "actors": actors_out,
            "scanned_at": movie.scanned_at.isoformat() if isinstance(movie.scanned_at, datetime) else None,
        }
    )
    payload.update(_paths(movie))
    return payload


@router.get("/movies/{movie_id}/poster")
def poster(movie_id: int, db: Session = Depends(get_db)):
    movie = db.get(Movie, movie_id)
    path = openable_poster(movie.poster_path) if movie else None
    if path is None:
        raise HTTPException(status_code=404, detail="Постера нет")
    ext = path[path.rfind(".") :].lower() if "." in path else ""
    return FileResponse(path, media_type=_POSTER_TYPES.get(ext, "image/jpeg"), headers={"Cache-Control": "public, max-age=86400"})


@router.get("/movies/{movie_id}/playlist.m3u")
def playlist(movie_id: int, db: Session = Depends(get_db)):
    movie = db.get(Movie, movie_id)
    if movie is None:
        raise HTTPException(status_code=404, detail="Фильм не найден")
    title = (movie.title_ru or movie.title_en or movie.file_name).replace("\r", " ").replace("\n", " ")
    target = unc_path(settings.smb_host, movie.share_name, movie.relative_path)
    body = f"\ufeff#EXTM3U\n#EXTINF:-1,{title}\n{target}\n"
    name = playlist_filename(movie.file_name)
    return Response(
        content=body.encode("utf-8"),
        media_type="audio/x-mpegurl",
        headers={"Content-Disposition": _attachment(name)},
    )
