// Localized dates, durations, sizes and countdowns.
import { locale, t } from "./i18n.js";

function formatCountdown(ts) {
  if (!ts) return "-";
  const seconds = Math.max(0, Math.floor(ts - Date.now() / 1000));
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${minutes}:${String(rest).padStart(2, "0")}`;
}

function formatDateTime(value) {
  if (!value) return t("never");
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale.lang === "ru" ? "ru-RU" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  }).format(date);
}

function formatDurationSeconds(value) {
  if (value == null || value === "") return "-";
  const seconds = Number(value);
  if (!Number.isFinite(seconds)) return String(value);
  const units = locale.lang === "ru"
    ? {second: "с", minute: "мин", hour: "ч", day: "дн"}
    : {second: "s", minute: "m", hour: "h", day: "d"};
  if (seconds < 60) return `${Math.round(seconds * 10) / 10}${units.second}`;
  if (seconds >= 86400) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    return hours ? `${days} ${units.day} ${hours} ${units.hour}` : `${days} ${units.day}`;
  }
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return minutes ? `${hours} ${units.hour} ${minutes} ${units.minute}` : `${hours} ${units.hour}`;
  }
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return `${minutes} ${units.minute} ${rest}${units.second}`;
}

function formatSecondsShort(value) {
  if (value == null || value === "") return "-";
  return formatDurationSeconds(value);
}

function formatBytes(value) {
  const bytes = Number(value);
  if (!Number.isFinite(bytes)) return "-";
  const units = ["B", "KB", "MB", "GB"];
  let size = bytes;
  let unit = 0;
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024;
    unit += 1;
  }
  return `${Math.round(size * 10) / 10} ${units[unit]}`;
}

function yesNo(value) {
  return value ? t("yes") : t("no");
}

export { formatBytes, formatCountdown, formatDateTime, formatDurationSeconds, formatSecondsShort, yesNo };
