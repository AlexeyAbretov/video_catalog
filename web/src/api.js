async function getJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(String(response.status));
  }
  return response.json();
}

export function getMovies(filters) {
  const query = new URLSearchParams();
  if (filters.yearFrom) query.set("year_from", filters.yearFrom);
  if (filters.yearTo) query.set("year_to", filters.yearTo);
  if (filters.incomplete) query.set("incomplete", "1");
  if (filters.yearMismatch) query.set("year_mismatch", "1");
  filters.genres.forEach((id) => query.append("genre_id", id));
  filters.actors.forEach((id) => query.append("actor_id", id));
  query.set("page", filters.page || "1");
  return getJson(`/api/movies?${query.toString()}`);
}

export function getMovie(id) {
  return getJson(`/api/movies/${id}`);
}

export function getGenres() {
  return getJson("/api/genres");
}

export function getYears() {
  return getJson("/api/years");
}

export function searchActors(text) {
  return getJson(`/api/actors?q=${encodeURIComponent(text)}`);
}

export function getActorsByIds(ids) {
  if (!ids.length) return Promise.resolve([]);
  const query = new URLSearchParams();
  ids.forEach((id) => query.append("id", id));
  return getJson(`/api/actors?${query.toString()}`);
}

export function getScanStatus() {
  return getJson("/api/scan/status");
}

async function postAuthorized(url, token, body) {
  const headers = { Authorization: `Bearer ${token}` };
  const init = { method: "POST", headers };
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const response = await fetch(url, init);
  let payload = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }
  if (!response.ok) {
    const detail = payload && payload.detail;
    const message = typeof detail === "string" ? detail : "";
    const error = new Error(message || String(response.status));
    error.status = response.status;
    throw error;
  }
  return payload;
}

export function startScan(token) {
  return postAuthorized("/api/scan", token);
}

export function resetMovies(ids, token) {
  return postAuthorized("/api/movies/reset", token, { ids });
}
