export function detectDevice() {
  const agent = navigator.userAgent || "";
  if (/Android|iPhone|iPad|iPod/i.test(agent)) return "android";
  if (/Macintosh|Mac OS X/i.test(agent)) return "mac";
  return "windows";
}

export function filmCount(count) {
  const value = Math.abs(count) % 100;
  const last = value % 10;
  if (value > 10 && value < 20) return `${count} фильмов`;
  if (last > 1 && last < 5) return `${count} фильма`;
  if (last === 1) return `${count} фильм`;
  return `${count} фильмов`;
}

export function formatDuration(seconds) {
  if (!seconds) return "";
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.round((seconds % 3600) / 60);
  if (hours && minutes) return `${hours} ч ${minutes} мин`;
  if (hours) return `${hours} ч`;
  return `${minutes} мин`;
}

export function formatRating(value) {
  const number = Number(value);
  if (!number) return "";
  return number.toFixed(1);
}

export function displayTitle(movie) {
  return movie.title_ru || movie.title_en || movie.file_name;
}

export function secondaryTitle(movie) {
  if (movie.title_ru && movie.title_en && movie.title_ru !== movie.title_en) {
    return movie.title_en;
  }
  return "";
}

export const STATUS_LABEL = {
  pending: "разбор",
  failed: "без карточки",
  ambiguous: "проверить",
};
