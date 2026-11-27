import os
import re
from typing import NamedTuple

VIDEO_EXTENSIONS = {"mkv", "mp4", "avi", "mov", "m4v", "wmv", "ts"}

_JUNK = {
    "bdrip", "bdremux", "bluray", "brrip", "webrip", "web-dl", "webdl", "web-dlrip",
    "webdlrip", "hdrip", "hdtv", "hdtvrip", "dvdrip", "dvd", "x264", "x265", "h264",
    "h265", "avc", "hevc", "xvid", "divx", "ac3", "aac", "dts", "hdr", "hdr10",
    "1080p", "720p", "2160p", "480p", "dub", "dubbed", "rus", "eng", "lostfilm",
    "newstudio", "baibako", "hdrezka", "kubik", "kube", "new-team", "newteam",
    "megapeer", "exkinoray", "dalemake", "lbs", "engineer", "hrime", "ivanes",
    "nf", "web", "dl", "dlrip", "rip", "by", "remux", "proper", "repack", "extended",
    "directors", "cut", "dtheaterrip", "hd", "sd",
}

_YEAR = re.compile(r"(?<![0-9])((?:19|20)\d{2})(?![0-9])")
_SIZE = re.compile(r"\d+(?:\.\d+)?gb", re.IGNORECASE)


class ParsedName(NamedTuple):
    title: str
    year: int | None


def has_cyrillic(text: str | None) -> bool:
    return bool(text and re.search(r"[А-Яа-яЁё]", text))


def is_video_name(name: str) -> bool:
    ext = os.path.splitext(name)[1].lower().lstrip(".")
    return ext in VIDEO_EXTENSIONS


def should_skip_file(name: str) -> bool:
    base = os.path.basename(name)
    if base.startswith(".") or base.startswith("._"):
        return True
    stem = os.path.splitext(base)[0]
    tokens = [token for token in re.split(r"[. _\-()\[\]]+", stem.lower()) if token]
    if "sample" in tokens:
        return True
    if "trailer" in tokens and (tokens[-1] == "trailer" or len(tokens) <= 2):
        return True
    return False


def _strip_video_ext(name: str) -> str:
    stem, ext = os.path.splitext(name)
    if ext.lower().lstrip(".") in VIDEO_EXTENSIONS:
        return stem
    return name


def _take_year(text: str) -> tuple[str, int | None]:
    matches = list(_YEAR.finditer(text))
    if not matches:
        return text, None
    chosen = matches[0]
    for match in matches:
        before = text[match.start() - 1] if match.start() else ""
        if before in "([{":
            chosen = match
            break
    year = int(chosen.group(1))
    if not 1888 <= year <= 2035:
        return text, None
    return text[: chosen.start()] + " " + text[chosen.end() :], year


def _is_junk_token(token: str) -> bool:
    key = token.lower().strip(".-")
    if not key:
        return True
    if key in _JUNK:
        return True
    if re.fullmatch(r"ivanes\d+", key):
        return True
    if _SIZE.fullmatch(key):
        return True
    if re.fullmatch(r"\d{3,4}p", key):
        return True
    if re.fullmatch(r"[a-z]", key):
        return True
    parts = [part for part in re.split(r"-+", key) if part]
    if parts and all(part in _JUNK for part in parts):
        return True
    return False


def parse_release_name(file_name: str) -> ParsedName:
    text = _strip_video_ext(os.path.basename(file_name.strip()))
    text, year = _take_year(text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\d+(?:\.\d+)?\s?gb", " ", text, flags=re.IGNORECASE)
    versions: list[str] = []

    def protect(match: re.Match[str]) -> str:
        versions.append(match.group(0))
        return f" ver{len(versions) - 1}ver "

    text = re.sub(r"(?<!\d)\d\.\d(?!\d)", protect, text)
    text = text.replace("_", " ").replace("&", " & ")
    text = re.sub(r"[.]+", " ", text)
    for index, value in enumerate(versions):
        text = text.replace(f"ver{index}ver", value)
    text = re.sub(r"[,:;]+", " ", text)
    kept: list[str] = []
    for token in text.split():
        raw = token.strip(".-")
        if raw == "&":
            kept.append("&")
            continue
        if not raw or _is_junk_token(raw):
            continue
        kept.append(raw)
    title = re.sub(r"\s+&\s+", " & ", " ".join(kept))
    title = re.sub(r"\s+", " ", title).strip(" &-.")
    if not title:
        title = _strip_video_ext(os.path.basename(file_name.strip()))
    return ParsedName(title, year)


def parse_release(file_name: str, parent_name: str | None = None) -> ParsedName:
    parsed = parse_release_name(file_name)
    if parent_name and len(parsed.title) < 2:
        parent = parse_release_name(parent_name)
        if len(parent.title) > len(parsed.title):
            return parent
    return parsed


def year_conflicts(file_name: str, parent_name: str | None, stored_year: int | None) -> bool:
    parsed = parse_release(file_name, parent_name).year
    return parsed is not None and parsed != stored_year
