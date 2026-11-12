"use client";
import { useEffect, useState } from "react";
import { Wifi, WifiOff, RefreshCw, AlertCircle } from "lucide-react";
import { getActiveLodgeId, getActiveUserId } from "@/lib/api";
import { queuedWork } from "@/lib/offlineWildlife";
import { offlineCopy as c } from "@/lib/strings/offline";
export function SyncChip() {
  const [online, setOnline] = useState(true),
    [count, setCount] = useState(0),
    [syncing, setSyncing] = useState(false),
    [failed, setFailed] = useState(false),
    [available, setAvailable] = useState(false);
  useEffect(() => {
    let alive = true,
      version = 0;
    const update = async () => {
      const stamp = ++version,
        scope = { userId: getActiveUserId(), lodgeId: getActiveLodgeId() };
      setOnline(navigator.onLine);
      if (!scope.userId || !scope.lodgeId) {
        setAvailable(false);
        return;
      }
      try {
        const rows = await queuedWork(scope);
        if (
          alive &&
          stamp === version &&
          scope.userId === getActiveUserId() &&
          scope.lodgeId === getActiveLodgeId()
        ) {
          setAvailable(true);
          setCount(
            rows.filter(
              (row) => row.state === "queued" || row.state === "syncing",
            ).length,
          );
          setSyncing(rows.some((row) => row.state === "syncing"));
          setFailed(rows.some((row) => row.state === "rejected"));
        }
      } catch {
        if (alive) {
          setAvailable(true);
          setFailed(true);
        }
      }
    };
    void update();
    for (const name of ["online", "offline", "focus", "safarios-queue-changed"])
      window.addEventListener(name, update);
    return () => {
      alive = false;
      for (const name of [
        "online",
        "offline",
        "focus",
        "safarios-queue-changed",
      ])
        window.removeEventListener(name, update);
    };
  }, []);
  if (!available) return null;
  const Icon = syncing
    ? RefreshCw
    : failed
      ? AlertCircle
      : online
        ? Wifi
        : WifiOff;
  return (
    <button
      type="button"
      className={"syncChip" + (!online ? " offline" : "")}
      aria-label={c.open}
      title={`${syncing ? c.syncing : failed ? c.failed : online ? c.online : c.offline}${count ? " · " + c.count(count) : ""}`}
      onClick={() => window.dispatchEvent(new Event("safarios-open-sync"))}
    >
      <Icon size={14} aria-hidden="true" />
      <span role="status">
        {syncing
          ? c.syncing
          : failed
            ? c.failed
            : online
              ? c.online
              : c.offline}
        {count ? " · " + c.count(count) : ""}
      </span>
    </button>
  );
}
