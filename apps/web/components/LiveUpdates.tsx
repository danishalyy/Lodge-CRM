"use client";
import { useEffect, useRef, useState } from "react";
import { Radio, RefreshCw } from "lucide-react";
import { API_URL, getActiveUserId, getActiveLodgeId } from "@/lib/api";
import { invalidateData } from "@/lib/data-cache";
import { readLiveFrames } from "@/lib/live-stream";
import { liveCopy as c } from "@/lib/strings/live";
type Change = { type: string; id: string; version: string };
const kinds =
  /^(task\.(created|assigned|updated)|request\.(created|updated)|stay\.(created|updated)|room\.(created|updated)|maintenance\.(created|updated)|housekeeping\.(created|updated)|notification\.updated|subscription\.updated)$/;
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export default function LiveUpdates({
  userId,
  lodgeId,
  accessVersion,
  onAccessChange,
}: {
  userId: string;
  lodgeId: string;
  accessVersion: string;
  onAccessChange: () => void;
}) {
  const callback = useRef(onAccessChange);
  callback.current = onAccessChange;
  const [state, setState] = useState("reconnecting"),
    [count, setCount] = useState(0),
    [held, setHeld] = useState(false),
    [editing, setEditing] = useState(false);
  const apply = useRef<() => void>(() => {});
  useEffect(() => {
    let disposed = false,
      restricted = false,
      active: AbortController | null = null,
      cursor = "",
      fingerprint = "",
      attempt = 0,
      ready = false,
      lastFrame = 0,
      lastScroll = 0,
      deferred = false;
    let wake = () => {},
      flushTimer: ReturnType<typeof setTimeout> | undefined;
    const changes = new Map<string, Change>(),
      seen = new Map<string, string>(),
      highlights = new Map<string, number>();
    setCount(0);
    setHeld(false);
    setState("reconnecting");
    const current = () =>
      !disposed &&
      getActiveUserId() === userId &&
      getActiveLodgeId() === lodgeId;
    const busy = () =>
      Boolean(
        document.querySelector(
          '[role="dialog"], [data-dragging], [aria-busy="true"]',
        ) ||
          document.activeElement?.closest(
            'input, textarea, select, [contenteditable="true"]',
          ) ||
          Date.now() - lastScroll < 800,
      );
    const mark = () => {
      if (!current()) return;
      document
        .querySelectorAll<HTMLElement>("[data-record-id]")
        .forEach((node) => {
          const until = highlights.get(node.dataset.recordId || "") || 0;
          if (until > Date.now()) node.dataset.liveUpdated = "true";
          else delete node.dataset.liveUpdated;
        });
    };
    const applied = (event: Event) => {
      if (!current() || restricted) return;
      const changes = (event as CustomEvent).detail?.changes;
      if (!Array.isArray(changes)) return;
      for (const change of changes)
        if (typeof change.id === "string" && uuid.test(change.id))
          highlights.set(change.id, Date.now() + 1800);
      mark();
    };
    window.addEventListener("safarios-live-applied", applied);
    const observer = new MutationObserver(mark);
    observer.observe(document.body, { childList: true, subtree: true });
    const flush = () => {
      if (!current() || restricted) return;
      if (busy()) {
        setEditing(true);
        deferred = true;
        setHeld(true);
        return;
      }
      const batch = [...changes.values()];
      changes.clear();
      deferred = false;
      setCount(0);
      setHeld(false);
      invalidateData();
      window.dispatchEvent(
        new CustomEvent("safarios-data-refresh", {
          detail: { source: "live", changes: batch },
        }),
      );
      if (batch.some((change) => change.type.startsWith("notification.")))
        window.dispatchEvent(new Event("safarios-notifications-changed"));
      mark();
    };
    apply.current = flush;
    const queue = (change?: Change) => {
      if (!current() || restricted) return;
      if (change) {
        const key = change.type.split(".")[0] + ":" + change.id;
        if (seen.get(key) === change.version) return;
        seen.set(key, change.version);
        if (seen.size > 1000) seen.delete(seen.keys().next().value!);
        changes.set(key, change);
        if (changes.size > 1000) changes.delete(changes.keys().next().value!);
      }
      setCount(changes.size);
      if (busy() || deferred) {
        setEditing(busy());
        deferred = true;
        setHeld(true);
        return;
      }
      clearTimeout(flushTimer);
      flushTimer = setTimeout(flush, 150);
    };
    const restrict = () => {
      if (!current() || restricted) return;
      restricted = true;
      active?.abort();
      changes.clear();
      highlights.clear();
      invalidateData();
      callback.current();
    };
    const visibility = () => {
      active?.abort();
      ready = false;
      setState(document.hidden ? "paused" : "reconnecting");
      wake();
    };
    const scroll = () => {
      lastScroll = Date.now();
    };
    document.addEventListener("visibilitychange", visibility);
    window.addEventListener("offline", visibility);
    window.addEventListener("online", visibility);
    window.addEventListener("scroll", scroll, true);
    const interval = setInterval(() => {
      if (!current()) {
        active?.abort();
        return;
      }
      setEditing(busy());
      mark();
      for (const [id, until] of highlights)
        if (until <= Date.now()) highlights.delete(id);
      if (active && Date.now() - lastFrame > 45000) active.abort();
    }, 500);
    const poll = setInterval(() => {
      if (current() && !document.hidden && !restricted) queue();
    }, 30000);
    const wait = (ms: number) =>
      new Promise<void>((resolve) => {
        const timer = setTimeout(resolve, ms);
        wake = () => {
          clearTimeout(timer);
          resolve();
        };
      });
    void (async () => {
      while (current() && !restricted) {
        if (document.hidden || !navigator.onLine) {
          setState("paused");
          await wait(1000);
          continue;
        }
        const controller = new AbortController();
        active = controller;
        ready = false;
        lastFrame = Date.now();
        try {
          const headers = new Headers({
            Accept: "text/event-stream",
            "X-Expected-User-Id": userId,
            "X-Lodge-Context": lodgeId,
          });
          if (cursor) headers.set("Last-Event-ID", cursor);
          const response = await fetch(
            `${API_URL}/api/v1/lodges/${encodeURIComponent(lodgeId)}/events`,
            {
              credentials: "include",
              cache: "no-store",
              headers,
              signal: controller.signal,
            },
          );
          if ([401, 403, 409].includes(response.status)) {
            restrict();
            return;
          }
          if (response.status === 400) cursor = "";
          if (!response.ok) throw new Error("stream unavailable");
          await readLiveFrames(response, controller.signal, (frame) => {
            if (!current() || restricted) return;
            lastFrame = Date.now();
            if (frame.id) cursor = frame.id;
            if (frame.event === "access") {
              restrict();
              return;
            }
            if (frame.event === "ready") {
              const version = String(frame.data.version || "");
              if (fingerprint && version && fingerprint !== version) {
                restrict();
                return;
              }
              fingerprint = version;
              ready = true;
              attempt = 0;
              setState("live");
              queue();
            } else if (frame.event === "change") {
              const { type, id, version } = frame.data;
              if (
                typeof type !== "string" ||
                !kinds.test(type) ||
                typeof id !== "string" ||
                !uuid.test(id) ||
                typeof version !== "string" ||
                !uuid.test(version)
              )
                return;
              if (type === "subscription.updated") restrict();
              else queue({ type, id, version });
            }
          });
        } catch {
          /* Bounded polling and reconnect preserve existing read behavior. */
        } finally {
          if (active === controller) active = null;
          ready = false;
        }
        if (current() && !restricted) {
          setState(document.hidden ? "paused" : "reconnecting");
          await wait(Math.min(30000, 1000 * 2 ** Math.min(attempt++, 5)));
        }
      }
    })();
    return () => {
      disposed = true;
      active?.abort();
      wake();
      clearTimeout(flushTimer);
      clearInterval(interval);
      clearInterval(poll);
      observer.disconnect();
      window.removeEventListener("safarios-live-applied", applied);
      changes.clear();
      seen.clear();
      highlights.clear();
      document
        .querySelectorAll<HTMLElement>("[data-live-updated]")
        .forEach((node) => delete node.dataset.liveUpdated);
      document.removeEventListener("visibilitychange", visibility);
      window.removeEventListener("offline", visibility);
      window.removeEventListener("online", visibility);
      window.removeEventListener("scroll", scroll, true);
      apply.current = () => {};
    };
  }, [userId, lodgeId, accessVersion]);
  return (
    <div className="liveControls">
      <span
        className="liveConnection"
        role="status"
        aria-label={`${c.connection}: ${state === "live" ? c.live : state === "paused" ? c.paused : c.reconnecting}`}
        title={
          state === "live"
            ? c.live
            : state === "paused"
              ? c.paused
              : c.reconnecting
        }
        data-state={state}
      >
        <Radio size={14} aria-hidden="true" />
        {state === "live"
          ? c.live
          : state === "paused"
            ? c.paused
            : c.reconnecting}
      </span>
      {held && (
        <button
          type="button"
          className="button secondary liveUpdatePill"
          disabled={editing}
          title={editing ? c.finish : undefined}
          onClick={() => apply.current()}
        >
          <RefreshCw size={14} />
          {count ? c.updates(count) : c.refresh}
        </button>
      )}
    </div>
  );
}
