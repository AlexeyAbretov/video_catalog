import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Share:
    mount: str
    name: str


@dataclass(frozen=True)
class Settings:
    database_url: str
    ollama_host: str
    ollama_model: str
    tmdb_api_key: str
    kp_api_key: str
    scan_token: str
    scan_cron: str
    smb_host: str
    min_file_bytes: int
    poster_dir: str
    tmdb_delay: float
    kp_delay: float
    shares: tuple[Share, ...]


def _shares_from_env() -> tuple[Share, ...]:
    raw = os.environ.get(
        "SHARE_MOUNTS",
        "/media/adata=ADATA SC610;/media/kingston=KINGSTON",
    )
    shares: list[Share] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        mount, name = part.split("=", 1)
        shares.append(Share(mount.strip(), name.strip()))
    return tuple(shares)


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ["DATABASE_URL"],
        ollama_host=os.environ.get("OLLAMA_HOST", "http://host.docker.internal:11434"),
        ollama_model=os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b"),
        tmdb_api_key=os.environ.get("TMDB_API_KEY", ""),
        kp_api_key=os.environ.get("KP_API_KEY", ""),
        scan_token=os.environ.get("SCAN_TOKEN", ""),
        scan_cron=os.environ.get("SCAN_CRON", "0 3 * * *"),
        smb_host=os.environ.get("SMB_HOST", "Keenetic-1601"),
        min_file_bytes=int(os.environ.get("MIN_FILE_BYTES", "52428800")),
        poster_dir=os.environ.get("POSTER_DIR", "/posters"),
        tmdb_delay=float(os.environ.get("TMDB_DELAY", "0.3")),
        kp_delay=float(os.environ.get("KP_DELAY", "1.5")),
        shares=_shares_from_env(),
    )


settings = load_settings()
