"use client";
import { toast } from "sonner";
import { useEffect, useState } from "react";
import { X, RefreshCw, Trash2 } from "lucide-react";
import Drawer from "./Drawer";
import { ConfirmDialog } from "./ui/confirm-dialog";
import {
  queuedWork,
  changeQueuedWork,
  removeQueuedWork,
  QueuedWork,
} from "@/lib/offlineWildlife";
import { readableLabel } from "@/lib/strings/content";
import { syncOffline } from "@/lib/offline-sync";
import { getActiveLodgeId, getActiveUserId } from "@/lib/api";
import { offlineCopy as c } from "@/lib/strings/offline";
export default function OfflineManager({
  userId,
  lodgeId,
}: {
  userId: string;
  lodgeId: string;
}) {
  const [open, setOpen] = useState(false),
    [rows, setRows] = useState<QueuedWork[]>([]),
    [error, setError] = useState(""),
    [discard, setDiscard] = useState("");
  const scope = { userId, lodgeId },
    current = () =>
      getActiveUserId() === userId && getActiveLodgeId() === lodgeId;
  useEffect(() => {
    let alive = true,
      revision = 0;
    const update = async () => {
      const version = ++revision;
      try {
        const next = await queuedWork(scope);
        if (alive && current() && version === revision) {
          setRows(next);
          setError("");
        }
      } catch {
        if (alive && current()) setError(c.storageError);
      }
    };
    const sync = () => {
      void update();
      if (current()) void syncOffline(scope);
    };
    const show = () => {
      setOpen(true);
      void update();
    };
    void update();
    void syncOffline(scope);
    const timer = setInterval(sync, 15000);
    window.addEventListener("safarios-queue-changed", update);
    window.addEventListener("online", sync);
    document.addEventListener("visibilitychange", sync);
    window.addEventListener("safarios-open-sync", show);
    return () => {
      alive = false;
      clearInterval(timer);
      window.removeEventListener("safarios-queue-changed", update);
      window.removeEventListener("online", sync);
      document.removeEventListener("visibilitychange", sync);
      window.removeEventListener("safarios-open-sync", show);
    };
  }, [userId, lodgeId]);
  async function changedElsewhere() {
    const fresh = await queuedWork(scope);
    if (current()) {
      setRows(fresh);
      setError(c.stateChanged);
    }
  }
  async function retry(id: string) {
    if (!current()) return;
    const changed = await changeQueuedWork(
      scope,
      id,
      { state: "queued", nextAttemptAt: 0, leaseUntil: 0, error: "" },
      false,
      undefined,
      "rejected",
    );
    if (!changed) {
      await changedElsewhere();
      return;
    }
    void syncOffline(scope);
  }
  async function remove(id: string) {
    if (!current()) return;
    if (await removeQueuedWork(scope, id)) {
      if (current()) toast.success(c.removed);
    } else await changedElsewhere();
  }
  if (!open) return null;
  return (
    <Drawer
      onClose={() => {
        if (!discard) setOpen(false);
      }}
    >
      <div className="drawerHead">
        <h2>{c.title}</h2>
        <button
          type="button"
          className="iconButton"
          aria-label={c.close}
          onClick={() => setOpen(false)}
        >
          <X size={18} />
        </button>
      </div>
      <p>{c.description}</p>
      {error && <p role="alert">{error}</p>}
      {!error && !rows.length && <div className="panel empty">{c.empty}</div>}
      <div className="offlineWorkList">
        {rows.map((row) => (
          <article className="panel" key={row.id} data-queue-state={row.state}>
            <div className="offlineWorkHead">
              <h3>{c.kinds[row.kind]}</h3>
              <span className="statusPill" role="status">
                {c[row.state]}
              </span>
            </div>
            <p>{new Date(row.createdAt).toLocaleString()}</p>
            {row.recordId && (
              <p>
                {row.recordId.slice(0, 8)} ·{" "}
                {typeof row.expected === "boolean"
                  ? row.expected
                    ? c.complete
                    : c.incomplete
                  : readableLabel(String(row.expected || ""))}{" "}
                →{" "}
                {typeof row.value === "boolean"
                  ? row.value
                    ? c.complete
                    : c.incomplete
                  : readableLabel(String(row.value || ""))}
              </p>
            )}
            {row.kind === "wildlife.sighting" && row.payload?.species && (
              <p>{String(row.payload.species)}</p>
            )}
            {row.error && <p role="alert">{row.error}</p>}
            <div className="headerActions">
              {row.state === "rejected" && (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() =>
                    void retry(row.id).catch(() => setError(c.storageError))
                  }
                >
                  <RefreshCw size={16} />
                  {c.retry}
                </button>
              )}
              {row.state !== "syncing" && (
                <button
                  type="button"
                  className="button secondary"
                  onClick={() => setDiscard(row.id)}
                >
                  <Trash2 size={16} />
                  {row.state === "synced" ? c.removeCompleted : c.discard}
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
      <ConfirmDialog
        open={!!discard}
        onOpenChange={(next) => {
          if (!next) setDiscard("");
        }}
        title={
          rows.find((row) => row.id === discard)?.state === "synced"
            ? c.removeCompleted
            : c.discard
        }
        description={
          rows.find((row) => row.id === discard)?.state === "synced"
            ? c.removeCompletedConfirm
            : c.discardConfirm
        }
        actionLabel={
          rows.find((row) => row.id === discard)?.state === "synced"
            ? c.removeCompleted
            : c.discard
        }
        onConfirm={() =>
          void remove(discard).catch(() => setError(c.storageError))
        }
      />
    </Drawer>
  );
}
