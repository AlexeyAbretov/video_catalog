from app.filenames import parse_release
from app.paths import parent_dir_name


def clear_movie_card(movie) -> None:
    parsed = parse_release(movie.file_name, parent_dir_name(movie.relative_path))
    movie.status = "pending"
    movie.kp_checked = False
    movie.error = None
    movie.confidence = None
    movie.title_ru = parsed.title or None
    movie.title_en = None
    movie.year = parsed.year
    movie.overview_ru = None
    movie.rating_tmdb = None
    movie.rating_kp = None
    movie.tmdb_id = None
    movie.kp_id = None
    movie.duration_sec = None
    movie.enriched_at = None
