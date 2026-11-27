import json
import logging
import time

import httpx

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Ты разбираешь имена файлов с фильмами и отвечаешь только JSON-объектом {"title": string, "year": number|null}.
title — название фильма без качества, кодека, источника, озвучки, разрешения и релиз-группы.
Не включай BDRip, WEB-DL, HDRip, Dub, AVC, x264, 1080p, Kubik, Kube, New-Team, ivanes, Dalemake.
Точки и подчёркивания между словами замени пробелами.
year — год выпуска фильма. Если года в имени нет, верни null. Не выдумывай год.
Похожее написание не делает фильм другим. Armageddec — это «Армагеддец» (The World's End, 2013), не Armageddon (1998).
Явную опечатку исправляй только если уверен, что это тот же фильм. Если не уверен, оставь как в файле.
Русское название, записанное латиницей, верни кириллицей. Koloniya — это «Колония», не Colony и не Kolónia.
Примеры:
Жмот (2016) BDRip-AVC_ivanes20031987.mkv → {"title":"Жмот","year":2016}
Bastarden.2023.HDRip AVC.mkv → {"title":"Bastarden","year":2023}
Die Hard [1988 HDRip].avi → {"title":"Die Hard","year":1988}
K-Pax.2001.DTheaterRip.1080p.mkv → {"title":"K-Pax","year":2001}
Minecraft в кино_2025_WEB-DLRip.avi → {"title":"Minecraft в кино","year":2025}
Shaun.of.the.Dead.HDRip.Kubik.v.Kube.mkv → {"title":"Shaun of the Dead","year":null}
Armageddec_2013_BDRip_by_Dalemake.avi → {"title":"Армагеддец","year":2013}
Koloniya.2026.D.WEB-DLRip_ELEKTRI4KA.avi → {"title":"Колония","year":2026}
Chernoknizhnik.1989.BDRip.DUB.avi → {"title":"Чернокнижник","year":1989}
"""


def _json_object(text: str) -> dict | None:
    raw = (text or "").strip()
    if not raw:
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            value = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    if isinstance(value, list):
        value = value[0] if value else None
    if not isinstance(value, dict):
        return None
    return value


class OllamaClient:
    def __init__(self, http: httpx.Client, base_url: str, model: str):
        self.http = http
        self.base_url = base_url.rstrip("/")
        self.model = model

    def parse_filename(self, file_name: str, parent: str) -> dict | None:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Файл: {file_name}\nПапка: {parent or '—'}",
                },
            ],
            "options": {"temperature": 0, "num_predict": 120},
        }
        try:
            response = self.http.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=180,
            )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("ollama: %s", exc)
            return None
        return _json_object(content)


class TmdbClient:
    def __init__(self, http: httpx.Client, api_key: str, delay: float):
        self.http = http
        self.api_key = api_key
        self.delay = delay
        self.disabled = not api_key

    def _get(self, path: str, params: dict) -> dict | None:
        if self.disabled:
            return None
        time.sleep(self.delay)
        query = {"api_key": self.api_key, "language": "ru-RU", **params}
        for attempt in range(3):
            try:
                response = self.http.get(
                    f"https://api.themoviedb.org/3{path}",
                    params=query,
                    timeout=30,
                )
            except httpx.HTTPError as exc:
                logger.warning("tmdb: %s", exc)
                return None
            if response.status_code == 429:
                time.sleep(2 + attempt)
                continue
            if response.status_code == 401:
                logger.warning("tmdb: ключ отклонён")
                self.disabled = True
                return None
            if response.status_code >= 400:
                logger.warning("tmdb %s: %s", path, response.status_code)
                return None
            return response.json()
        return None

    def search(self, title: str, year: int | None) -> list[dict]:
        params: dict = {"query": title, "include_adult": "false", "page": 1}
        if year:
            params["year"] = year
        data = self._get("/search/movie", params)
        if not data:
            return []
        return list(data.get("results") or [])[:8]

    def details(self, movie_id: int) -> dict | None:
        return self._get(
            f"/movie/{movie_id}",
            {"append_to_response": "credits,translations"},
        )


class KpClient:
    def __init__(self, http: httpx.Client, api_key: str, delay: float):
        self.http = http
        self.api_key = api_key
        self.delay = delay
        self.disabled = not api_key
        self._url = "https://api.poiskkino.dev/v1.4/movie/search"

    def search(self, title: str, *, fallback: bool = True) -> tuple[list[dict], bool]:
        if self.disabled or not title:
            return [], False
        time.sleep(self.delay)
        try:
            response = self.http.get(
                self._url,
                params={"query": title, "limit": 5, "page": 1},
                headers={"X-API-KEY": self.api_key},
                timeout=30,
            )
        except httpx.HTTPError as exc:
            logger.warning("kinopoisk: %s", exc)
            return [], False
        if response.status_code in {401, 402, 403, 429}:
            logger.warning("kinopoisk остановлен на этот прогон: %s", response.status_code)
            self.disabled = True
            return [], False
        if response.status_code == 404 and fallback and self._url.endswith("/search"):
            self._url = "https://api.poiskkino.dev/v1.4/movie"
            return self.search(title, fallback=False)
        if response.status_code >= 400:
            logger.warning("kinopoisk: %s", response.status_code)
            return [], False
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return [], False
        return list(payload.get("docs") or []), True
