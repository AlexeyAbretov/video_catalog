import logging
import os
from dataclasses import dataclass

from sqlalchemy import select

from app.cards import clear_movie_card
from app.config import settings
from app.db import Movie, SessionLocal
from app.filenames import is_video_name, should_skip_file
from app.posters import remove_poster

logger = logging.getLogger(__name__)

SKIP_DIRS = {
    "blocklists",
    "resume",
    "torrents",
    "watch",
    "system volume information",
    "$recycle.bin",
    "#recycle",
    "@eadir",
    ".fseventsd",
    ".spotlight-v100",
    ".trashes",
}


@dataclass(frozen=True)
class FoundFile:
    relative_path: str
    file_name: str
    parent_name: str
    size: int
    mtime: int


def iter_videos(mount: str, errors: list[OSError]):
    def on_error(err: OSError) -> None:
        errors.append(err)
        logger.warning("не читается каталог: %s", err)

    for root, dirs, files in os.walk(mount, followlinks=False, onerror=on_error):
        dirs[:] = [
            name
            for name in dirs
            if name.lower() not in SKIP_DIRS and not name.startswith(".")
        ]
        for name in files:
            if not is_video_name(name) or should_skip_file(name):
                continue
            path = os.path.join(root, name)
            try:
                stat = os.stat(path)
            except OSError as exc:
                logger.warning("не читается файл %s: %s", path, exc)
                continue
            if stat.st_size < settings.min_file_bytes:
                continue
            relative = os.path.relpath(path, mount).replace("\\", "/")
            parent = ""
            if "/" in relative:
                parent = relative.rsplit("/", 1)[0].rsplit("/", 1)[-1]
            yield FoundFile(relative, name, parent, stat.st_size, int(stat.st_mtime))


def _apply_fresh_file(movie: Movie, found: FoundFile) -> None:
    movie.file_name = found.file_name
    movie.file_size = found.size
    movie.file_mtime = found.mtime
    clear_movie_card(movie)


def upsert_file(share_name: str, found: FoundFile) -> tuple[int, str, bool]:
    """Возвращает id, статус и признак, что карточку нужно собирать заново."""
    db = SessionLocal()
    try:
        movie = db.scalar(
            select(Movie).where(
                Movie.share_name == share_name,
                Movie.relative_path == found.relative_path,
            )
        )
        if movie is None:
            movie = Movie(
                share_name=share_name,
                relative_path=found.relative_path,
                file_name=found.file_name,
                file_size=found.size,
                file_mtime=found.mtime,
                status="pending",
                kp_checked=False,
            )
            _apply_fresh_file(movie, found)
            db.add(movie)
            changed = True
        else:
            changed = movie.file_size != found.size or movie.file_mtime != found.mtime
            if changed:
                remove_poster(movie.poster_path)
                movie.poster_path = None
                movie.genres.clear()
                movie.cast_entries.clear()
                _apply_fresh_file(movie, found)
        db.commit()
        return movie.id, movie.status, changed
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
