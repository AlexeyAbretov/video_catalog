import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { getActorsByIds, getGenres, getMovies, getScanStatus, getYears, searchActors } from "./api";
import { STATUS_LABEL, displayTitle, filmCount, formatDuration, formatRating, secondaryTitle } from "./format";

function kinopoiskRating(value, label) {
  const rating = formatRating(value);
  if (rating) return `${label} ${rating}`;
  return <strong>{label} N/A</strong>;
}

function readFilters(params) {
  return {
    yearFrom: params.get("year_from") || "",
    yearTo: params.get("year_to") || "",
    incomplete: params.get("incomplete") === "1",
    yearMismatch: params.get("year_mismatch") === "1",
    genres: params.getAll("genre_id"),
    actors: params.getAll("actor_id"),
    page: params.get("page") || "1",
  };
}

const PHASE = {
  idle: "ожидание",
  scanning: "поиск файлов",
  enriching: "карточки",
  done: "готово",
  error: "ошибка",
};

export function Catalog() {
  const [params, setParams] = useSearchParams();
  const filters = readFilters(params);
  const [genres, setGenres] = useState([]);
  const [years, setYears] = useState([]);
  const [catalog, setCatalog] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);
  const [actorQuery, setActorQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [actorNames, setActorNames] = useState({});
  const [yearFrom, setYearFrom] = useState(filters.yearFrom);
  const [yearTo, setYearTo] = useState(filters.yearTo);

  function update(patch) {
    const next = new URLSearchParams(params);
    for (const [key, item] of Object.entries(patch)) {
      next.delete(key);
      if (Array.isArray(item)) {
        item.filter(Boolean).forEach((part) => next.append(key, part));
      } else if (item) {
        next.set(key, item);
      }
    }
    if (!Object.prototype.hasOwnProperty.call(patch, "page")) {
      next.delete("page");
    }
    setParams(next);
  }

  useEffect(() => {
    setYearFrom(filters.yearFrom);
    setYearTo(filters.yearTo);
  }, [filters.yearFrom, filters.yearTo]);

  useEffect(() => {
    const handle = setTimeout(() => {
      if (yearFrom !== filters.yearFrom || yearTo !== filters.yearTo) {
        update({ year_from: yearFrom, year_to: yearTo });
      }
    }, 400);
    return () => clearTimeout(handle);
  }, [yearFrom, yearTo]);

  useEffect(() => {
    getGenres().then(setGenres).catch(() => setGenres([]));
    getYears().then(setYears).catch(() => setYears([]));
  }, [catalog?.total]);

  useEffect(() => {
    let cancel = false;
    setLoading(true);
    getMovies(filters)
      .then((data) => {
        if (!cancel) {
          setCatalog(data);
          setError("");
        }
      })
      .catch(() => {
        if (!cancel) setError("Не удалось загрузить каталог");
      })
      .finally(() => {
        if (!cancel) setLoading(false);
      });
    return () => {
      cancel = true;
    };
  }, [params]);

  useEffect(() => {
    let cancel = false;
    let timer = 0;
    async function poll() {
      try {
        const next = await getScanStatus();
        if (!cancel) setStatus(next);
      } catch {
        if (!cancel) setStatus(null);
      }
    }
    poll();
    timer = setInterval(poll, 4000);
    return () => {
      cancel = true;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!status || status.running || status.phase === "idle") return undefined;
    const handle = setTimeout(() => {
      getMovies(filters).then(setCatalog).catch(() => {});
      getGenres().then(setGenres).catch(() => {});
      getYears().then(setYears).catch(() => {});
    }, 600);
    return () => clearTimeout(handle);
  }, [status?.running, status?.enriched, status?.found]);

  useEffect(() => {
    let cancel = false;
    if (actorQuery.trim().length < 2) {
      setSuggestions([]);
      return undefined;
    }
    const handle = setTimeout(() => {
      searchActors(actorQuery.trim())
        .then((rows) => {
          if (!cancel) setSuggestions(rows);
        })
        .catch(() => {
          if (!cancel) setSuggestions([]);
        });
    }, 250);
    return () => {
      cancel = true;
      clearTimeout(handle);
    };
  }, [actorQuery]);

  useEffect(() => {
    let cancel = false;
    getActorsByIds(filters.actors)
      .then((rows) => {
        if (cancel) return;
        const names = {};
        rows.forEach((row) => {
          names[String(row.id)] = row.name;
        });
        setActorNames(names);
      })
      .catch(() => {});
    return () => {
      cancel = true;
    };
  }, [filters.actors.join(",")]);

  function toggleGenre(id) {
    const key = String(id);
    const next = filters.genres.includes(key)
      ? filters.genres.filter((item) => item !== key)
      : [...filters.genres, key];
    update({ genre_id: next });
  }

  function addActor(actor) {
    if (!filters.actors.includes(String(actor.id))) {
      update({ actor_id: [...filters.actors, String(actor.id)] });
    }
    setActorQuery("");
    setSuggestions([]);
  }

  function removeActor(id) {
    update({ actor_id: filters.actors.filter((item) => item !== id) });
  }

  const page = Number(filters.page) || 1;

  return (
    <div className="wrap">
      <header className="top">
        <div>
          <p className="eyebrow">Keenetic</p>
          <h1>Каталог фильмов</h1>
          <Link className="service-link" to="/service">
            Служебное
          </Link>
        </div>
        <p className="count">{catalog ? filmCount(catalog.total) : ""}</p>
      </header>

      {status && (status.running || status.last_error) ? (
        <p className={status.last_error && !status.running ? "banner warn" : "banner"}>
          {status.running
            ? `${PHASE[status.phase] || status.phase}: ${status.enriched} карточек из ${status.total}, файлов ${status.found}`
            : status.last_error}
          {status.current_file ? ` · ${status.current_file}` : ""}
        </p>
      ) : null}

      <section className="filters">
        <label>
          Год с
          <input
            inputMode="numeric"
            list="years"
            value={yearFrom}
            onChange={(event) => setYearFrom(event.target.value.replace(/\D/g, "").slice(0, 4))}
          />
        </label>
        <label>
          по
          <input
            inputMode="numeric"
            list="years"
            value={yearTo}
            onChange={(event) => setYearTo(event.target.value.replace(/\D/g, "").slice(0, 4))}
          />
        </label>
        <datalist id="years">
          {years.map((year) => (
            <option key={year} value={year} />
          ))}
        </datalist>
        <div className="actor-filter">
          <label>
            Актёр
            <input
              value={actorQuery}
              placeholder="Фамилия"
              onChange={(event) => setActorQuery(event.target.value)}
            />
          </label>
          {suggestions.length > 0 ? (
            <ul className="suggestions">
              {suggestions.map((actor) => (
                <li key={actor.id}>
                  <button type="button" onClick={() => addActor(actor)}>
                    {actor.name}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <button
          type="button"
          className={filters.incomplete ? "genre on" : "genre"}
          onClick={() => update({ incomplete: filters.incomplete ? "" : "1" })}
        >
          Неполная карточка
        </button>
        <button
          type="button"
          className={filters.yearMismatch ? "genre on" : "genre"}
          onClick={() => update({ year_mismatch: filters.yearMismatch ? "" : "1" })}
        >
          Год не из файла
        </button>
        <button
          type="button"
          className="text-button"
          onClick={() => update({
            year_from: "",
            year_to: "",
            genre_id: [],
            actor_id: [],
            incomplete: "",
            year_mismatch: "",
          })}
        >
          Сбросить
        </button>
      </section>

      {filters.actors.length > 0 ? (
        <div className="chips">
          {filters.actors.map((id) => (
            <button key={id} type="button" className="chip" onClick={() => removeActor(id)}>
              {actorNames[id] || `актёр ${id}`} ×
            </button>
          ))}
        </div>
      ) : null}

      <div className="genre-row">
        {genres.map((genre) => (
          <button
            key={genre.id}
            type="button"
            className={filters.genres.includes(String(genre.id)) ? "genre on" : "genre"}
            onClick={() => toggleGenre(genre.id)}
          >
            {genre.name}
          </button>
        ))}
      </div>

      {error ? <p className="banner warn">{error}</p> : null}
      {loading && !catalog ? <p className="muted">Загрузка…</p> : null}
      {catalog && catalog.items.length === 0 ? (
        <p className="muted">Ничего не нашлось. Скан ещё идёт или фильтр слишком узкий.</p>
      ) : null}

      <div className="grid">
        {(catalog?.items || []).map((movie) => {
          const meta = [
            `№ ${movie.id}`,
            movie.year,
            movie.file_year && movie.file_year !== movie.year ? `в файле ${movie.file_year}` : "",
            formatDuration(movie.duration_sec),
            kinopoiskRating(movie.rating_kp, "КП"),
            formatRating(movie.rating_tmdb) ? `TMDB ${formatRating(movie.rating_tmdb)}` : "",
          ].filter(Boolean);
          return (
            <Link key={movie.id} className="card" to={`/movie/${movie.id}`} state={{ search: params.toString() }}>
              {movie.poster_url ? (
                <img src={movie.poster_url} alt="" />
              ) : (
                <div className="poster-fallback">{displayTitle(movie)}</div>
              )}
              <div className="card-body">
                {STATUS_LABEL[movie.status] ? <span className="tag">{STATUS_LABEL[movie.status]}</span> : null}
                <h2>{displayTitle(movie)}</h2>
                {secondaryTitle(movie) ? <p className="sub">{secondaryTitle(movie)}</p> : null}
                <p className="meta">
                  {meta.map((part, index) => (
                    <span key={index}>
                      {index ? " · " : null}
                      {part}
                    </span>
                  ))}
                </p>
              </div>
            </Link>
          );
        })}
      </div>

      {catalog && catalog.pages > 1 ? (
        <div className="pager">
          <button type="button" disabled={page <= 1} onClick={() => update({ page: String(page - 1) })}>
            Назад
          </button>
          <span>
            {page} / {catalog.pages}
          </span>
          <button type="button" disabled={page >= catalog.pages} onClick={() => update({ page: String(page + 1) })}>
            Дальше
          </button>
        </div>
      ) : null}
    </div>
  );
}
