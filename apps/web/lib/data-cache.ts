// Ephemeral data only. Never persist API responses or cache authentication.
type Entry = { expires: number; value: Promise<unknown> };
const entries = new Map<string, Entry>();
let revision = 0;
export function invalidateData() {
  revision++;
  entries.clear();
}
export async function cachedRead<T>(
  key: string,
  load: () => Promise<T>,
): Promise<T> {
  const version = revision;
  let entry = entries.get(key);
  if (!entry || entry.expires <= Date.now()) {
    entry = { expires: Date.now() + 2000, value: load() };
    entries.set(key, entry);
  }
  try {
    const result = (await entry.value) as T;
    // A write may have overtaken this read. Fetch the current server state.
    if (version !== revision) return cachedRead(key, load);
    return structuredClone(result);
  } catch (error) {
    if (entries.get(key) === entry) entries.delete(key);
    throw error;
  }
}
export function startDataRefresh() {
  const refresh = () => {
    if (document.hidden) return;
    invalidateData();
    window.dispatchEvent(new Event("safarios-data-refresh"));
  };
  window.addEventListener("focus", refresh);
  window.addEventListener("online", refresh);
  document.addEventListener("visibilitychange", refresh);
  const clear = () => invalidateData();
  window.addEventListener("storage", clear);
  window.addEventListener("safarios-lodge-changed", clear);
  return () => {
    window.removeEventListener("focus", refresh);
    window.removeEventListener("online", refresh);
    document.removeEventListener("visibilitychange", refresh);
    window.removeEventListener("storage", clear);
    window.removeEventListener("safarios-lodge-changed", clear);
  };
}
