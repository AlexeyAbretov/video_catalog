import logging
import os

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def looks_like_image(content: bytes) -> bool:
    if len(content) < 12:
        return False
    if content.startswith(b"\xff\xd8\xff"):
        return True
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    return content[:4] == b"RIFF" and content[8:12] == b"WEBP"


def _inside_poster_dir(path: str) -> bool:
    root = os.path.abspath(settings.poster_dir)
    target = os.path.abspath(path)
    return target == root or target.startswith(root + os.sep)


def openable_poster(path: str | None) -> str | None:
    if not path or not _inside_poster_dir(path) or not os.path.isfile(path):
        return None
    return path


def remove_poster(path: str | None) -> None:
    if not path or not _inside_poster_dir(path):
        return
    if os.path.isfile(path):
        os.remove(path)


def save_poster(movie_id: int, content: bytes) -> str | None:
    if not looks_like_image(content):
        return None
    if content.startswith(b"\x89PNG"):
        ext = "png"
    elif content[:4] == b"RIFF":
        ext = "webp"
    else:
        ext = "jpg"
    os.makedirs(settings.poster_dir, exist_ok=True)
    path = os.path.join(settings.poster_dir, f"{movie_id}.{ext}")
    for other in ("jpg", "png", "webp"):
        candidate = os.path.join(settings.poster_dir, f"{movie_id}.{other}")
        if candidate != path and os.path.isfile(candidate):
            os.remove(candidate)
    with open(path, "wb") as handle:
        handle.write(content)
    return path


def fetch_poster(http: httpx.Client, url: str | None) -> bytes | None:
    if not url:
        return None
    if url.startswith("/"):
        url = "https://image.tmdb.org/t/p/w500" + url
    try:
        response = http.get(url, timeout=40)
    except httpx.HTTPError as exc:
        logger.warning("постер: %s", exc)
        return None
    if response.status_code != 200 or not looks_like_image(response.content):
        return None
    return response.content
