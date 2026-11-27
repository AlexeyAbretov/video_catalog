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

function encodeUncForSearchMs(unc) {
  return String(unc)
    .trim()
    .replace(/\\/g, "%5C")
    .replace(/ /g, "%20");
}

// smb:// в браузере на Windows не зарегистрирован. explorer /select из HTTPS недоступен — только
// search-ms: папка в location, имя файла во втором crumb (близко к выделению, не синяя рамка /select).
export function windowsFolderUrl(folderUnc, fileName) {
  let path = String(folderUnc || "").trim();
  if (!path) return "";
  if (!path.endsWith("\\")) path += "\\";
  const location = encodeUncForSearchMs(path);
  const title = encodeURIComponent("Каталог фильмов");
  const base = fileBaseName(fileName);
  if (base) {
    const fileTerm = encodeURIComponent(base);
    return `search-ms:displayname=${title}&crumb=filename%3A${fileTerm}&crumb=location:${location},include,nonrecursive&`;
  }
  return `search-ms:displayname=${title}&query=*&crumb=location:${location},include,nonrecursive&`;
}

export function videoMime(fileName) {
  const base = String(fileName || "").replace(/\\/g, "/").split("/").pop() || "";
  const dot = base.lastIndexOf(".");
  const ext = dot > 0 ? base.slice(dot + 1).toLowerCase() : "";
  return VIDEO_MIME[ext] || "video/mp4";
}

function fileBaseName(fileName) {
  return String(fileName || "").replace(/[\r\n]/g, " ").replace(/\\/g, "/").split("/").pop()?.trim() || "";
}

function intentExtra(value) {
  return encodeURIComponent(value).replace(/[!'()*]/g, (ch) => `%${ch.charCodeAt(0).toString(16).toUpperCase()}`);
}

function androidSmbIntent(smbUrl, { mime, packageId, title, directory }) {
  let parsed;
  try {
    parsed = new URL(smbUrl);
  } catch {
    return smbUrl;
  }
  if (parsed.protocol !== "smb:") return smbUrl;
  let path = parsed.pathname;
  if (directory && !path.endsWith("/")) path += "/";
  const target = `${parsed.host}${path}${parsed.search}`;
  const parts = [
    "action=android.intent.action.VIEW",
    "scheme=smb",
    "category=android.intent.category.BROWSABLE",
    "category=android.intent.category.DEFAULT",
  ];
  if (mime) parts.push(`type=${mime}`);
  if (packageId) parts.push(`package=${packageId}`);
  if (title) parts.push(`S.title=${intentExtra(title)}`);
  return `intent://${target}#Intent;${parts.join(";")};end`;
}

// VLC принимает smb только вместе с MIME-типом. Голая ссылка из Chrome не совпадает с фильтром, и нажатие пропадает.
// Имя файла уходит отдельным extra: свой разбор пути плеер показывает кракозябрами.
export function androidVlcUrl(smbUrl, fileName) {
  const mime = videoMime(fileName);
  const name = fileBaseName(fileName);
  return androidSmbIntent(smbUrl, { mime, packageId: "org.videolan.vlc", title: name || "" });
}

const ANDSMB_PACKAGE = "lysesoft.andsmb";
const MIXPLORER_PACKAGE = "com.mixplorer";

function smbAndsmbParts(smbUrl) {
  let parsed;
  try {
    parsed = new URL(smbUrl);
  } catch {
    return null;
  }
  if (parsed.protocol !== "smb:") return null;
  const segments = parsed.pathname.split("/").filter(Boolean).map((part) => decodeURIComponent(part));
  const port = parsed.port || "445";
  const authority = `${parsed.hostname}:${port}`;
  const remotePath = segments.length ? `/${segments.join("/")}` : "/";
  return { authority, remotePath };
}

function androidAndsmbFolderIntent(folderSmbUrl) {
  const parts = smbAndsmbParts(folderSmbUrl);
  if (!parts) return "";
  const remote = encodeURIComponent(parts.remotePath);
  return `intent://${parts.authority}#Intent;action=android.intent.action.VIEW;scheme=smb;package=${ANDSMB_PACKAGE};S.remote_folder=${remote};end`;
}

function androidMixplorerFolderIntent(folderSmbUrl) {
  const path = encodeURIComponent(String(folderSmbUrl || "").trim());
  if (!path) return "";
  return `intent://#Intent;action=com.mixplorer.ACTION_OPEN_FOLDER;package=${MIXPLORER_PACKAGE};S.path=${path};end`;
}

// CX и большинство проводников не принимают smb из Chrome. AndSMB — см. lysesoft.com/andsmb/intent.html
export async function openAndroidFolder(folderSmbUrl, onNote) {
  const mode = (import.meta.env.VITE_ANDROID_FOLDER_APP || "andsmb").toLowerCase();
  const intent =
    mode === "mixplorer" ? androidMixplorerFolderIntent(folderSmbUrl) : androidAndsmbFolderIntent(folderSmbUrl);
  if (!intent) {
    onNote?.("Ссылку на папку не собрать — скопируйте smb-путь вручную");
    return false;
  }
  try {
    await navigator.clipboard.writeText(folderSmbUrl);
  } catch {
    /* буфер не обязателен */
  }
  window.location.assign(intent);
  onNote?.(
    mode === "mixplorer"
      ? "Открываем папку в MiXplorer…"
      : "Открываем папку в AndSMB… при первом входе приложение может спросить логин шары",
  );
  return true;
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
