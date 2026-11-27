import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getScanStatus, resetMovies, startScan } from "./api";

const TOKEN_KEY = "catalog-scan-token";

const PHASE = {
  idle: "ожидание",
  scanning: "поиск файлов",
  enriching: "карточки",
  done: "готово",
  error: "ошибка",
};

function parseIds(text) {
  const parts = text.split(/[\s,;]+/).filter(Boolean);
  const ids = [];
  for (const part of parts) {
    if (!/^\d+$/.test(part)) {
      return { error: `«${part}» не номер карточки` };
    }
    ids.push(Number(part));
  }
  const unique = [...new Set(ids)];
  if (!unique.length) {
    return { error: "Нужен хотя бы один номер" };
  }
  if (unique.length > 100) {
    return { error: "Не больше 100 карточек за раз" };
  }
  return { ids: unique };
}

function failureText(error) {
  if (error.status === 401) return "Пароль не подошёл";
  if (error.status === 409) return "Уже идёт разбор";
  return error.message || "Команда не выполнилась";
}

export function ServicePage() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) || "");
  const [rawIds, setRawIds] = useState("");
  const [status, setStatus] = useState(null);
  const [followedStart, setFollowedStart] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function rememberRun(next) {
    if (next?.running && next.started_at) setFollowedStart(next.started_at);
    setStatus(next);
  }

  useEffect(() => {
    let cancel = false;
    async function poll() {
      try {
        const next = await getScanStatus();
        if (!cancel) rememberRun(next);
      } catch {
        if (!cancel) setStatus(null);
      }
    }
    poll();
    const timer = setInterval(poll, 2000);
    return () => {
      cancel = true;
      clearInterval(timer);
    };
  }, []);

  function saveToken(value) {
    setToken(value);
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  }

  async function rebuild(event) {
    event.preventDefault();
    setError("");
    setResult(null);
    const password = token.trim();
    if (!password) {
      setError("Нужен пароль из SCAN_TOKEN");
      return;
    }
    const parsed = parseIds(rawIds);
    if (parsed.error) {
      setError(parsed.error);
      return;
    }
    setBusy(true);
    try {
      const accepted = await resetMovies(parsed.ids, password);
      setResult(accepted);
      rememberRun(accepted);
    } catch (err) {
      setError(failureText(err));
    } finally {
      setBusy(false);
    }
  }

  async function scanAll() {
    setError("");
    setResult(null);
    const password = token.trim();
    if (!password) {
      setError("Нужен пароль из SCAN_TOKEN");
      return;
    }
    setBusy(true);
    try {
      rememberRun(await startScan(password));
    } catch (err) {
      setError(failureText(err));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!result?.reset?.length || !status?.started_at) return;
    if (status.started_at !== result.started_at || status.running) return;
    setResult((current) => {
      if (!current?.reset?.length) return current;
      if (!current.missing?.length) return null;
      return { ...current, reset: [] };
    });
  }, [status, result]);

  const running = Boolean(status?.running);
  const locked = busy || running;
  const showDone =
    status?.phase === "done" &&
    Boolean(status.started_at) &&
    status.started_at === followedStart;

  return (
    <div className="wrap">
      <Link className="back" to="/">
        К каталогу
      </Link>
      <header className="top">
        <div>
          <p className="eyebrow">Keenetic</p>
          <h1>Служебное</h1>
        </div>
      </header>
      <p className="muted">
        Номер карточки копируется кнопкой «Карточка N» на странице фильма. Сброс собирает только указанные карточки заново. Полный скан заново читает шары.
      </p>

      {status && (running || status.last_error || showDone) ? (
        <p className={status.last_error && !running ? "banner warn" : "banner"}>
          {PHASE[status.phase] || status.phase}
          {status.total ? `: ${status.enriched} карточек из ${status.total}` : ""}
          {status.current_file ? ` · ${status.current_file}` : ""}
          {status.last_error && !running ? ` · ${status.last_error}` : ""}
        </p>
      ) : null}

      <form className="service" onSubmit={rebuild}>
        <label>
          Пароль
          <input
            type="password"
            autoComplete="current-password"
            value={token}
            onChange={(event) => saveToken(event.target.value)}
          />
        </label>
        <label>
          Номера карточек
          <textarea
            value={rawIds}
            placeholder="1, 2, 20"
            onChange={(event) => setRawIds(event.target.value)}
          />
        </label>
        <div className="service-actions">
          <button className="play" type="submit" disabled={locked}>
            Собрать заново
          </button>
          <button className="play secondary" type="button" disabled={locked} onClick={scanAll}>
            Полный скан
          </button>
        </div>
      </form>

      {error ? <p className="banner warn service-follow">{error}</p> : null}
      {result?.reset?.length || result?.missing?.length ? (
        <div className="note service-follow">
          {result.reset?.length ? <p>В очереди: {result.reset.join(", ")}</p> : null}
          {result.missing?.length ? <p>Не найдены: {result.missing.join(", ")}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
