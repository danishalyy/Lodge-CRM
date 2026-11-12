// Public device binding only; never stores authentication tokens or API responses.
export type DeviceBinding = { id: string; userId: string; lodgeId: string };
let generation = 0;
export async function deviceBinding(
  value?: DeviceBinding | null,
  expected?: string | null,
): Promise<DeviceBinding | null> {
  const stamp = generation;
  if (value !== undefined && typeof localStorage !== "undefined") {
    try {
      if (value)
        localStorage.setItem("safarios_push_binding", JSON.stringify(value));
      else if (
        expected === undefined ||
        JSON.parse(localStorage.getItem("safarios_push_binding") || "null")
          ?.id === expected
      )
        localStorage.removeItem("safarios_push_binding");
    } catch {}
  }
  return new Promise((resolve, reject) => {
    const r = indexedDB.open("safarios-device", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("binding");
    r.onerror = () => reject(r.error);
    r.onsuccess = () => {
      const db = r.result,
        tx = db.transaction(
          "binding",
          value === undefined ? "readonly" : "readwrite",
        ),
        store = tx.objectStore("binding");
      const get = store.get("push");
      if (value === null)
        get.onsuccess = () => {
          if (
            expected === undefined ||
            !get.result ||
            get.result.id === expected
          )
            store.delete("push");
        };
      else if (
        value !== undefined &&
        stamp === generation &&
        localStorage.getItem("active_user_id") === value.userId &&
        localStorage.getItem("active_lodge_id") === value.lodgeId
      )
        store.put(value, "push");
      tx.oncomplete = () => {
        db.close();
        resolve(value === undefined ? get.result || null : value);
      };
      tx.onerror = tx.onabort = () => {
        db.close();
        reject(tx.error);
      };
    };
  });
}
export async function clearPushDevice() {
  const stamp = ++generation;
  const owner = {
    userId: localStorage.getItem("active_user_id"),
    lodgeId: localStorage.getItem("active_lodge_id"),
  };
  let previous: DeviceBinding | null = null;
  try {
    previous = JSON.parse(
      localStorage.getItem("safarios_push_binding") || "null",
    );
    localStorage.removeItem("safarios_push_binding");
  } catch {}
  if (!previous) {
    const stored = await deviceBinding().catch(() => null);
    if (stored?.userId === owner.userId && stored?.lodgeId === owner.lodgeId)
      previous = stored;
  }
  navigator.serviceWorker?.controller?.postMessage({
    type: "CLEAR_SESSION",
    binding: previous?.id || null,
  });
  await deviceBinding(null, previous?.id || null).catch(() => {});
  const cleanup = async () => {
    try {
      const registration = await navigator.serviceWorker?.getRegistration();
      const subscription = await registration?.pushManager?.getSubscription();
      if (subscription && stamp === generation)
        await subscription.unsubscribe();
    } catch {}
    if (previous) {
      const csrf =
        document.cookie
          .split("; ")
          .find((row) => row.startsWith("lodge_csrf="))
          ?.split("=")
          .slice(1)
          .join("=") || "";
      try {
        await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || ""}/api/v1/auth/push/subscriptions`,
          {
            method: "DELETE",
            credentials: "include",
            cache: "no-store",
            keepalive: true,
            headers: {
              "Content-Type": "application/json",
              "X-CSRF-Token": decodeURIComponent(csrf),
              "X-Expected-User-Id": previous.userId,
              "X-Lodge-Context": previous.lodgeId,
            },
            body: JSON.stringify({
              id: previous.id,
              lodge_id: previous.lodgeId,
            }),
          },
        );
      } catch {}
    }
  };
  await Promise.race([
    cleanup(),
    new Promise<void>((resolve) => setTimeout(resolve, 3000)),
  ]);
}
