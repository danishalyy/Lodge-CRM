import {
  authApi,
  offlineApi,
  operationsApi,
  ApiError,
  getActiveUserId,
  getActiveLodgeId,
} from "./api";
import {
  queuedWork,
  changeQueuedWork,
  queueWork,
  QueueScope,
  QueuedWork,
  WorkKind,
} from "./offlineWildlife";
import { invalidateData } from "./data-cache";
import { offlineCopy as c } from "./strings/offline";
import { toast } from "sonner";
const current = (scope: QueueScope) =>
  scope.userId === getActiveUserId() && scope.lodgeId === getActiveLodgeId();
let running = false;
export async function queueChange(
  access: {
    feature: (key: string) => boolean;
    isCurrent: () => boolean;
    readOnly: boolean;
  },
  kind: Exclude<WorkKind, "wildlife.sighting">,
  recordId: string,
  expected: string | boolean,
  value: string | boolean,
  itemId?: string,
) {
  if (access.readOnly || !access.isCurrent()) throw new Error(c.unavailable);
  if (!access.feature("offline_mobile")) throw new Error(c.feature);
  const scope = { userId: getActiveUserId(), lodgeId: getActiveLodgeId() };
  try {
    await queueWork(scope, {
      id: crypto.randomUUID(),
      kind,
      recordId,
      itemId,
      expected,
      value,
      createdAt: new Date().toISOString(),
    });
  } catch {
    throw new Error(c.storageError);
  }
  if (current(scope) && access.isCurrent()) toast.message(c.waiting);
}
async function photo(scope: QueueScope, item: QueuedWork, owner: string) {
  if (!item.photo || !item.remoteId || !current(scope)) return;
  let descriptor = item.mediaUpload;
  if (!descriptor) {
    const digest = await crypto.subtle.digest(
      "SHA-256",
      await item.photo.arrayBuffer(),
    );
    const sha256 = Array.from(new Uint8Array(digest))
      .map((x) => x.toString(16).padStart(2, "0"))
      .join("");
    if (!current(scope)) throw new Error(c.signIn);
    const signed = await operationsApi.wildlife.uploadUrl(
      {
        content_type: item.photoType || "image/jpeg",
        size_bytes: item.photo.size,
        sha256,
      },
      scope,
    );
    if (!current(scope)) throw new Error(c.signIn);
    const result = await fetch(signed.upload_url, {
      method: "PUT",
      headers: signed.required_headers,
      body: item.photo,
      signal: AbortSignal.timeout(120000),
    });
    if (!result.ok)
      throw new ApiError(
        "Photo could not be uploaded. Retry when your connection is available.",
        result.status,
      );
    descriptor = {
      sighting_id: item.remoteId,
      object_key: signed.object_key,
      content_type: item.photoType || "image/jpeg",
      size_bytes: item.photo.size,
      sha256,
    };
    if (
      !current(scope) ||
      !(await changeQueuedWork(
        scope,
        item.id,
        { mediaUpload: descriptor },
        false,
        owner,
      ))
    )
      throw new Error(c.signIn);
  }
  if (
    !current(scope) ||
    !(await changeQueuedWork(
      scope,
      item.id,
      { leaseUntil: Date.now() + 60000 },
      false,
      owner,
    ))
  )
    throw new Error(c.signIn);
  await operationsApi.wildlife.registerMedia(descriptor, {
    ...scope,
    silent: true,
  });
}
export async function syncOffline(scope: QueueScope) {
  if (running || !navigator.onLine || !current(scope) || document.hidden)
    return;
  running = true;
  try {
    const work = async () => {
      if (!current(scope)) return;
      const items = await queuedWork(scope);
      if (
        !items.some(
          (item) =>
            (item.state === "queued" &&
              (item.nextAttemptAt || 0) <= Date.now()) ||
            (item.state === "syncing" && (item.leaseUntil || 0) < Date.now()),
        )
      )
        return;
      const me = await authApi.me();
      if (
        !current(scope) ||
        me.id !== scope.userId ||
        me.is_super_admin ||
        !me.memberships?.some((m: any) => m.lodge_id === scope.lodgeId)
      )
        return;
      let changed = false;
      try {
        for (const item of items) {
          if (!current(scope) || !navigator.onLine || document.hidden) return;
          const owner = crypto.randomUUID();
          if (
            !(await changeQueuedWork(
              scope,
              item.id,
              {
                state: "syncing",
                leaseOwner: owner,
                leaseUntil: Date.now() + 60000,
                attempts: item.attempts + 1,
                error: "",
              },
              true,
            ))
          )
            continue;
          const fresh = (await queuedWork(scope)).find(
            (row) => row.id === item.id,
          );
          if (!current(scope) || !fresh || fresh.leaseOwner !== owner) return;
          Object.assign(item, fresh);
          const heartbeat = setInterval(() => {
            if (current(scope))
              void changeQueuedWork(
                scope,
                item.id,
                { leaseUntil: Date.now() + 60000 },
                false,
                owner,
              ).catch(() => {});
          }, 15000);
          try {
            if (item.kind === "wildlife.sighting") {
              if (!item.remoteId) {
                const created = await offlineApi.sighting(item.payload, scope);
                if (
                  !current(scope) ||
                  !(await changeQueuedWork(
                    scope,
                    item.id,
                    { remoteId: created.id },
                    false,
                    owner,
                  ))
                )
                  return;
                item.remoteId = created.id;
              }
              await photo(scope, item, owner);
            } else
              await offlineApi.apply(
                {
                  id: item.id,
                  kind: item.kind,
                  record_id: item.recordId,
                  item_id: item.itemId,
                  expected: item.expected,
                  value: item.value,
                },
                scope,
              );
            if (!current(scope)) return;
            changed =
              (await changeQueuedWork(
                scope,
                item.id,
                {
                  state: "synced",
                  error: "",
                  leaseUntil: 0,
                  leaseOwner: undefined,
                  payload: undefined,
                  photo: undefined,
                  mediaUpload: undefined,
                  photoName: undefined,
                  photoType: undefined,
                },
                false,
                owner,
              )) || changed;
          } catch (error) {
            if (!current(scope)) return;
            const permanent =
              error instanceof ApiError &&
              error.status >= 400 &&
              error.status < 500 &&
              ![408, 429].includes(error.status);
            const updated = await changeQueuedWork(
              scope,
              item.id,
              {
                state: permanent ? "rejected" : "queued",
                error:
                  permanent && error instanceof Error
                    ? error.message
                    : c.connectionError,
                leaseUntil: 0,
                leaseOwner: undefined,
                nextAttemptAt:
                  Date.now() +
                  Math.min(300000, 3000 * 2 ** Math.min(item.attempts, 6)),
              },
              false,
              owner,
            );
            changed = changed || (updated && permanent);
            if (
              !permanent ||
              (error instanceof ApiError &&
                (error.status === 401 ||
                  (error.status === 409 &&
                    /account changed|access changed/i.test(error.message))))
            )
              break;
          } finally {
            clearInterval(heartbeat);
          }
        }
      } finally {
        if (changed && current(scope)) {
          invalidateData();
          window.dispatchEvent(new Event("safarios-data-refresh"));
        }
      }
    };
    if (navigator.locks)
      await navigator.locks.request(
        `safarios-sync:${scope.userId}:${scope.lodgeId}`,
        { ifAvailable: true },
        async (lock) => {
          if (lock) await work();
        },
      );
    else await work(); // Atomic per-item leases also fence browsers without Web Locks.
  } catch {
    /* Keep work on this device until an authenticated retry is possible. */
  } finally {
    running = false;
  }
}
