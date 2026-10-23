export type LodgeFormatting = {
  date_format?: string;
  timezone?: string;
};
function storageKey() {
  return `lodge-format:${localStorage.getItem("active_user_id") || ""}:${localStorage.getItem("active_lodge_id") || ""}`;
}
export function storeFormatting(preferences: LodgeFormatting) {
  if (typeof window !== "undefined")
    localStorage.setItem(
      storageKey(),
      JSON.stringify({
        date_format: preferences.date_format,
        timezone: preferences.timezone,
      }),
    );
}
export function formatting(): LodgeFormatting {
  if (typeof window === "undefined") return {};
  try {
    const stored = JSON.parse(localStorage.getItem(storageKey()) || "{}");
    return { date_format: stored.date_format, timezone: stored.timezone };
  } catch {
    return {};
  }
}
function locale() {
  return typeof navigator === "undefined" ? undefined : navigator.language;
}
function dateParts(value: string | number | Date) {
  const prefs = formatting();
  const onlyDate =
    typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  let zone = onlyDate ? "UTC" : prefs.timezone;
  try {
    new Intl.DateTimeFormat("en", { timeZone: zone });
  } catch {
    zone = undefined;
  }
  return { date, prefs, zone };
}
export function formatDate(value: string | number | Date) {
  const parts = dateParts(value);
  if (!parts) return "—";
  const { date, prefs, zone } = parts;
  const [year, month, day] = ["year", "month", "day"].map((type) =>
    new Intl.DateTimeFormat("en-US", {
      [type]: type === "year" ? "numeric" : "2-digit",
      timeZone: zone,
    } as Intl.DateTimeFormatOptions).format(date),
  );
  if (prefs.date_format === "dd/MM/yyyy") return `${day}/${month}/${year}`;
  if (prefs.date_format === "MM/dd/yyyy") return `${month}/${day}/${year}`;
  if (prefs.date_format === "yyyy-MM-dd") return `${year}-${month}-${day}`;
  return new Intl.DateTimeFormat(locale(), {
    dateStyle: "medium",
    timeZone: zone,
  }).format(date);
}
export function formatTime(value: string | number | Date) {
  const p = dateParts(value);
  return p
    ? new Intl.DateTimeFormat(locale(), {
        timeStyle: "short",
        timeZone: p.zone,
      }).format(p.date)
    : "—";
}
export function formatDateTime(value: string | number | Date) {
  return `${formatDate(value)} · ${formatTime(value)}`;
}
export function dateInputValue(value = new Date()) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}
