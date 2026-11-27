const VIDEO_MIME = {
  mkv: "video/x-matroska",
  mp4: "video/mp4",
  m4v: "video/mp4",
  mov: "video/quicktime",
  avi: "video/x-msvideo",
  wmv: "video/x-ms-wmv",
  ts: "video/mp2t",
};

export function detectDevice() {
  const agent = navigator.userAgent || "";
  if (/Android/i.test(agent)) return "android";
  if (/iPhone|iPad|iPod/i.test(agent)) return "ios";
  if (/Macintosh|Mac OS X/i.test(agent)) return "mac";
  return "windows";
}

export function videoMime(fileName) {
  const base = String(fileName || "").replace(/\\/g, "/").split("/").pop() || "";
  const dot = base.lastIndexOf(".");
  const ext = dot > 0 ? base.slice(dot + 1).toLowerCase() : "";
  return VIDEO_MIME[ext] || "video/mp4";
}

function intentExtra(value) {
  return encodeURIComponent(value).replace(/[!'()*]/g, (ch) => `%${ch.charCodeAt(0).toString(16).toUpperCase()}`);
}

function fileBaseName(fileName) {
  return String(fileName || "").replace(/[\r\n]/g, " ").replace(/\\/g, "/").split("/").pop()?.trim() || "";
}

// VLC принимает smb только вместе с MIME-типом. Голая ссылка из Chrome не совпадает с фильтром, и нажатие пропадает.
// Имя файла уходит отдельным extra: свой разбор пути плеер показывает кракозябрами.
export function androidVlcUrl(smbUrl, fileName) {
  let parsed;
  try {
    parsed = new URL(smbUrl);
  } catch {
    return smbUrl;
  }
  if (parsed.protocol !== "smb:") return smbUrl;
  const target = `${parsed.host}${parsed.pathname}${parsed.search}`;
  const mime = videoMime(fileName);
  const name = fileBaseName(fileName);
  const title = name ? `;S.title=${intentExtra(name)}` : "";
  return `intent://${target}#Intent;action=android.intent.action.VIEW;scheme=smb;type=${mime};package=org.videolan.vlc${title};end`;
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
