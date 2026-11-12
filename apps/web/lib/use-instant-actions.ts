"use client";
import { useEffect, useRef, useState, Dispatch, SetStateAction } from "react";
import { toast } from "sonner";
import { ApiError, getActiveUserId, getActiveLodgeId } from "./api";
import { invalidateData } from "./data-cache";
import { instantCopy as c } from "./strings/interactivity";

export function useDataRefresh(refresh: () => unknown, blocked = false) {
  const callback = useRef(refresh),
    busy = useRef(blocked);
  const queued = useRef(false),
    detail = useRef<any>(undefined);
  const invoke = useRef<(detail?: any) => void>(() => {});
  callback.current = refresh;
  busy.current = blocked;
  useEffect(() => {
    let alive = true;
    invoke.current = (change) => {
      const actor = getActiveUserId(),
        lodge = getActiveLodgeId();
      try {
        const result = callback.current();
        void Promise.resolve(result)
          .then(() => {
            if (
              alive &&
              change?.source === "live" &&
              actor === getActiveUserId() &&
              lodge === getActiveLodgeId()
            )
              window.dispatchEvent(
                new CustomEvent("safarios-live-applied", { detail: change }),
              );
          })
          .catch(() => {});
      } catch {
        /* The view owns its error state and Retry. */
      }
    };
    const run = (event: Event) => {
      const change = (event as CustomEvent).detail;
      if (busy.current) {
        queued.current = true;
        detail.current = change;
      } else {
        queued.current = false;
        invoke.current(change);
      }
    };
    window.addEventListener("safarios-data-refresh", run);
    return () => {
      alive = false;
      window.removeEventListener("safarios-data-refresh", run);
      invoke.current = () => {};
    };
  }, []);
  useEffect(() => {
    if (!blocked && queued.current) {
      queued.current = false;
      invoke.current(detail.current);
      detail.current = undefined;
    }
  }, [blocked]);
}

export function useInstantRows<T extends { id: string }>(scopeKey: string) {
  const [rows, rawSet] = useState<T[]>([]);
  const rowsRef = useRef(rows);
  rowsRef.current = rows;
  const active = useRef(true),
    scope = useRef(scopeKey);
  scope.current = scopeKey;
  const previousScope = useRef(scopeKey);
  const owner = useRef(`${getActiveUserId()}:${getActiveLodgeId()}`);
  const locks = useRef(new Map<string, Partial<T>>());
  const [pending, setPending] = useState<string[]>([]);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
    };
  }, []);
  useEffect(() => {
    owner.current = `${getActiveUserId()}:${getActiveLodgeId()}`;
    locks.current.clear();
    setPending([]);
    rawSet([]);
    if (previousScope.current !== scopeKey) {
      previousScope.current = scopeKey;
      invalidateData();
      const timer = setTimeout(
        () => window.dispatchEvent(new Event("safarios-data-refresh")),
        0,
      );
      return () => clearTimeout(timer);
    }
  }, [scopeKey]);
  const setRows: Dispatch<SetStateAction<T[]>> = (value) => {
    rawSet((previous) => {
      const next = typeof value === "function" ? value(previous) : value;
      const result = next.map((row) => ({
        ...row,
        ...locks.current.get(row.id),
      }));
      rowsRef.current = result;
      return result;
    });
  };
  async function mutate(
    id: string,
    patch: Partial<T>,
    write: (patch: Partial<T>) => Promise<unknown>,
    options: {
      message?: string;
      undo?: Partial<T>;
      onError?: (error: unknown) => void;
      refresh?: () => unknown;
    } = {},
  ) {
    if (
      locks.current.has(id) ||
      !active.current ||
      owner.current !== `${getActiveUserId()}:${getActiveLodgeId()}`
    )
      return false;
    const before = rowsRef.current.find((row) => row.id === id);
    if (!before) return false;
    const token = scope.current;
    const actor = `${getActiveUserId()}:${getActiveLodgeId()}`;
    const current = () =>
      active.current &&
      scope.current === token &&
      actor === `${getActiveUserId()}:${getActiveLodgeId()}`;
    const toastId = `instant:${actor}:${id}`;
    locks.current.set(id, patch);
    setPending([...locks.current.keys()]);
    setRows((old) =>
      old.map((row) => (row.id === id ? { ...row, ...patch } : row)),
    );
    try {
      await write(patch);
      if (!current()) return false;
      locks.current.delete(id);
      invalidateData();
      toast.success(options.message || c.saved, {
        id: toastId,
        ...(options.undo
          ? {
              action: {
                label: c.undo,
                onClick: () => {
                  if (current())
                    void mutate(id, options.undo!, write, {
                      ...options,
                      undo: undefined,
                      message: c.undone,
                    });
                },
              },
            }
          : {}),
      });
      void options.refresh?.();
      return true;
    } catch (error) {
      if (!current()) return false;
      locks.current.delete(id);
      rawSet((old) => old.map((row) => (row.id === id ? before : row)));
      // Revoked access clears the screen through the owning module. Never offer
      // an old-authority retry for authorization/account/concurrency failures.
      const retryable = !(
        error instanceof ApiError && [401, 403, 404, 409].includes(error.status)
      );
      toast.error(error instanceof Error ? error.message : c.failed, {
        id: toastId,
        ...(retryable
          ? {
              action: {
                label: c.retry,
                onClick: () => {
                  if (current()) void mutate(id, patch, write, options);
                },
              },
            }
          : {}),
      });
      options.onError?.(error);
      return false;
    } finally {
      if (current()) {
        locks.current.delete(id);
        setPending([...locks.current.keys()]);
      }
    }
  }
  return { rows, setRows, pending, mutate };
}
