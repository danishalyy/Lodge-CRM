// Shared device queue. Legacy function names remain for existing wildlife callers.
export type QueueScope = { userId: string; lodgeId: string };
export type WorkKind =
  | "task.status"
  | "task.checklist"
  | "housekeeping.status"
  | "transfer.status"
  | "wildlife.sighting";
export type WorkState = "queued" | "syncing" | "synced" | "rejected";
export type QueuedWork = {
  id: string;
  kind: WorkKind;
  recordId?: string;
  itemId?: string;
  expected?: string | boolean;
  value?: string | boolean;
  payload?: any;
  photo?: Blob;
  photoName?: string;
  photoType?: string;
  remoteId?: string;
  mediaUpload?: {
    sighting_id: string;
    object_key: string;
    content_type: string;
    size_bytes: number;
    sha256: string;
  };
  createdAt: string;
  order: number;
  state: WorkState;
  attempts: number;
  error?: string;
  leaseUntil?: number;
  leaseOwner?: string;
  nextAttemptAt?: number;
};
export type QueuedSighting = {
  state?: WorkState;
  error?: string;
  id: string;
  payload: any;
  photo?: Blob;
  photoName?: string;
  photoType?: string;
  createdAt: string;
};
const DB = "lodge-crm-offline",
  STORE = "work-queue-v3";
let fence = 0,
  sequence = 0;
function ownerFence(userId: string) {
  try {
    return localStorage.getItem(`safarios-queue-fence:${userId}`) || "";
  } catch {
    return "";
  }
}
function validate(scope: QueueScope) {
  if (!scope.userId || !scope.lodgeId)
    throw new Error(
      "Sign in and select a lodge before accessing offline records",
    );
}
function changed() {
  if (typeof window !== "undefined")
    window.dispatchEvent(new Event("safarios-queue-changed"));
}
function openDb() {
  return new Promise<IDBDatabase>((resolve, reject) => {
    const r = indexedDB.open(DB, 3);
    r.onupgradeneeded = () => {
      const store = r.result.createObjectStore(STORE, {
        keyPath: ["userId", "lodgeId", "id"],
      });
      store.createIndex("owner", ["userId", "lodgeId"]);
      store.createIndex("user", "userId");
      if (r.result.objectStoreNames.contains("wildlife-queue-v2")) {
        const old = r.transaction!.objectStore("wildlife-queue-v2"),
          rows = old.getAll();
        rows.onsuccess = () => {
          for (const item of rows.result)
            if (item.userId && item.lodgeId)
              store.put({
                ...item,
                kind: "wildlife.sighting",
                state: "queued",
                attempts: 0,
                order: Date.parse(item.createdAt) * 1000 + sequence++,
              });
          // Only scoped v2 rows are migrated. Unscoped legacy data is never adopted.
          old.clear();
        };
      }
    };
    r.onsuccess = () => {
      r.result.onversionchange = () => r.result.close();
      resolve(r.result);
    };
    r.onerror = () => reject(r.error);
    r.onblocked = () =>
      reject(new Error("Close older SafariOS tabs to update offline storage"));
  });
}
export async function queueWork(
  scope: QueueScope,
  item: Omit<QueuedWork, "state" | "attempts" | "order">,
) {
  validate(scope);
  const stamp = fence,
    ownerStamp = ownerFence(scope.userId),
    db = await openDb();
  if (stamp !== fence || ownerStamp !== ownerFence(scope.userId)) {
    db.close();
    throw new Error("Account changed before the offline action could be saved");
  }
  return new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, "readwrite"),
      store = tx.objectStore(STORE);
    const existing = store.get([scope.userId, scope.lodgeId, item.id]);
    existing.onsuccess = () => {
      if (stamp !== fence || ownerStamp !== ownerFence(scope.userId)) {
        tx.abort();
        reject(
          new Error("Account changed before the offline action could be saved"),
        );
        return;
      }
      if (!existing.result)
        store.add({
          ...item,
          ...scope,
          state: "queued",
          attempts: 0,
          order: Date.now() * 1000 + (sequence++ % 1000),
        });
    };
    tx.oncomplete = () => {
      db.close();
      changed();
      resolve();
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(tx.error);
    };
  });
}
export async function queuedWork(scope: QueueScope): Promise<QueuedWork[]> {
  validate(scope);
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE),
      r = tx
        .objectStore(STORE)
        .index("owner")
        .getAll([scope.userId, scope.lodgeId]);
    tx.oncomplete = () => {
      db.close();
      resolve(r.result.sort((a, b) => a.order - b.order));
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(tx.error);
    };
  });
}
export async function changeQueuedWork(
  scope: QueueScope,
  id: string,
  patch: Partial<QueuedWork>,
  claim = false,
  expectedOwner?: string,
  expectedState?: WorkState,
): Promise<boolean> {
  validate(scope);
  const stamp = fence,
    db = await openDb();
  if (stamp !== fence) {
    db.close();
    return false;
  }
  return new Promise((resolve, reject) => {
    let applied = false;
    const tx = db.transaction(STORE, "readwrite"),
      store = tx.objectStore(STORE),
      r = store.get([scope.userId, scope.lodgeId, id]);
    r.onsuccess = () => {
      const item = r.result;
      if (
        !item ||
        (expectedOwner && item.leaseOwner !== expectedOwner) ||
        (expectedState && item.state !== expectedState) ||
        (claim &&
          !(
            (item.state === "queued" &&
              (item.nextAttemptAt || 0) <= Date.now()) ||
            (item.state === "syncing" && item.leaseUntil < Date.now())
          ))
      )
        return;
      store.put({ ...item, ...patch, ...scope, id });
      applied = true;
    };
    tx.oncomplete = () => {
      db.close();
      if (applied) changed();
      resolve(applied);
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(tx.error);
    };
  });
}
export async function removeQueuedWork(
  scope: QueueScope,
  id: string,
): Promise<boolean> {
  validate(scope);
  const db = await openDb();
  return new Promise((resolve, reject) => {
    let removed = false;
    const tx = db.transaction(STORE, "readwrite"),
      store = tx.objectStore(STORE),
      get = store.get([scope.userId, scope.lodgeId, id]);
    get.onsuccess = () => {
      if (!get.result || get.result.state === "syncing") return;
      store.delete([scope.userId, scope.lodgeId, id]);
      removed = true;
    };
    tx.oncomplete = () => {
      db.close();
      if (removed) changed();
      resolve(removed);
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(tx.error);
    };
  });
}
export async function clearOfflineUser(userId: string) {
  fence++;
  try {
    localStorage.setItem(
      `safarios-queue-fence:${userId}`,
      `${Date.now()}:${Math.random()}`,
    );
  } catch {}
  const db = await openDb();
  return new Promise<void>((resolve, reject) => {
    const tx = db.transaction(Array.from(db.objectStoreNames), "readwrite"),
      store = tx.objectStore(STORE);
    const r = store.index("user").openCursor(IDBKeyRange.only(userId));
    r.onsuccess = () => {
      const cursor = r.result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };
    // Old stores have no safe owner index and are never used after migration.
    for (const name of Array.from(db.objectStoreNames))
      if (name !== STORE) tx.objectStore(name).clear();
    tx.oncomplete = () => {
      db.close();
      changed();
      resolve();
    };
    tx.onerror = tx.onabort = () => {
      db.close();
      reject(tx.error);
    };
  });
}
export async function queueSighting(scope: QueueScope, item: QueuedSighting) {
  return queueWork(scope, { ...item, kind: "wildlife.sighting" });
}
export async function queuedSightings(
  scope: QueueScope,
): Promise<QueuedSighting[]> {
  return (await queuedWork(scope)).filter(
    (x) => x.kind === "wildlife.sighting" && x.state !== "synced",
  ) as QueuedSighting[];
}
export const removeQueuedSighting = removeQueuedWork;
