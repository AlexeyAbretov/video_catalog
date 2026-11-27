import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { getMovie } from "./api";
import { STATUS_LABEL, detectDevice, displayTitle, formatDuration, formatRating, secondaryTitle } from "./format";

export function MoviePage() {
  const { id } = useParams();
  const location = useLocation();
  const device = detectDevice();
  const fileRef = useRef(null);
  const folderRef = useRef(null);
  const [movie, setMovie] = useState(null);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    let cancel = false;
    getMovie(id)
      .then((data) => {
        if (!cancel) setMovie(data);
      })
      .catch(() => {
        if (!cancel) setError("Карточка не открылась");
      });
    return () => {
      cancel = true;
    };
  }, [id]);

  async function copyValue(value, input) {
    try {
      await navigator.clipboard.writeText(value);
      setNote("Путь скопирован");
    } catch {
      input.current?.focus();
      input.current?.select();
      setNote("Выделите путь и скопируйте его вручную");
    }
  }

  const back = location.state?.search ? `/?${location.state.search}` : "/";

  if (error) {
    return (
      <div className="wrap">
        <p className="banner warn">{error}</p>
        <Link to={back}>К каталогу</Link>
      </div>
    );
  }
  if (!movie) {
    return (
      <div className="wrap">
        <p className="muted">Загрузка…</p>
      </div>
    );
  }

  const meta = [
    movie.year,
    movie.file_year && movie.file_year !== movie.year ? `в файле ${movie.file_year}` : "",
    formatDuration(movie.duration_sec),
    formatRating(movie.rating_kp) ? `Кинопоиск ${formatRating(movie.rating_kp)}` : "",
    formatRating(movie.rating_tmdb) ? `TMDB ${formatRating(movie.rating_tmdb)}` : "",
    movie.share_name,
  ].filter(Boolean);

  async function copyId() {
    const value = String(movie.id);
    try {
      await navigator.clipboard.writeText(value);
      setNote("Номер карточки скопирован");
    } catch {
      setNote(`Номер карточки: ${value}`);
    }
  }

  return (
    <div className="wrap">
      <Link className="back" to={back}>
        К каталогу
      </Link>
      <article className="detail">
        {movie.poster_url ? (
          <img className="detail-poster" src={movie.poster_url} alt="" />
        ) : (
          <div className="poster-fallback detail-poster">{displayTitle(movie)}</div>
        )}
        <div>
          {STATUS_LABEL[movie.status] ? <span className="tag">{STATUS_LABEL[movie.status]}</span> : null}
          <h1>{displayTitle(movie)}</h1>
          {secondaryTitle(movie) ? <p className="sub title-en">{secondaryTitle(movie)}</p> : null}
          <p className="meta">
            <button type="button" className="text-button" onClick={copyId}>
              Карточка {movie.id}
            </button>
            {meta.length ? ` · ${meta.join(" · ")}` : ""}
          </p>
          <div className="genre-row">
            {movie.genres.map((genre) => (
              <Link key={genre.id} className="genre" to={`/?genre_id=${genre.id}`}>
                {genre.name}
              </Link>
            ))}
          </div>
          {movie.overview_ru ? <p className="overview">{movie.overview_ru}</p> : null}
          {movie.error && movie.status === "failed" ? <p className="muted">{movie.error}</p> : null}
        </div>
      </article>

      <section className="paths">
        <label>
          Файл
          <input ref={fileRef} readOnly value={movie.unc_path} />
        </label>
        <button type="button" onClick={() => copyValue(movie.unc_path, fileRef)}>
          Копировать файл
        </button>
        <label>
          Папка
          <input ref={folderRef} readOnly value={movie.folder_unc} />
        </label>
        <button type="button" onClick={() => copyValue(movie.folder_unc, folderRef)}>
          Копировать папку
        </button>
        {device === "windows" ? (
          <a className="play" href={`/api/movies/${movie.id}/playlist.m3u`}>
            В плеер
          </a>
        ) : (
          <a className="play" href={movie.smb_url}>
            В плеер
          </a>
        )}
        {device !== "windows" ? (
          <a className="play secondary" href={movie.folder_smb_url}>
            Открыть папку
          </a>
        ) : null}
        <p className="muted">
          {device === "windows"
            ? "«В плеер» скачивает короткий список для VLC или MPC-HC: файл читается с шары Keenetic. Папку вставьте в адресную строку Проводника."
            : "Ссылки smb:// открывают файл в VLC или IINA и папку в Finder или CX Проводнике, если шара уже доступна на этом устройстве."}
        </p>
        {note ? <p className="note">{note}</p> : null}
      </section>

      <section>
        <h2>Актёры</h2>
        {movie.actors.length === 0 ? <p className="muted">Список появится после сопоставления с TMDB.</p> : null}
        <ul className="cast">
          {movie.actors.map((actor) => (
            <li key={actor.id}>
              <Link to={`/?actor_id=${actor.id}`}>{actor.name}</Link>
              {actor.character ? <span className="muted"> · {actor.character}</span> : null}
              {actor.is_lead ? <span className="tag">главная роль</span> : null}
              {actor.popular ? <span className="tag gold">популярный</span> : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
