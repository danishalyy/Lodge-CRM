"use client";
import { useEffect, useState } from "react";
import { Wifi, WifiOff } from "lucide-react";
import { getActiveLodgeId, getActiveUserId } from "@/lib/api";
import { queuedSightings } from "@/lib/offlineWildlife";
import { uiCopy as c } from "@/lib/strings/redesign";
export function SyncChip() {
  const [online, setOnline] = useState(true),
    [count, setCount] = useState(0);
  useEffect(() => {
    let alive = true;
    const update = () => {
      setOnline(navigator.onLine);
      const scope = { userId: getActiveUserId(), lodgeId: getActiveLodgeId() };
      queuedSightings(scope)
        .then((rows) => {
          if (
            alive &&
            scope.userId === getActiveUserId() &&
            scope.lodgeId === getActiveLodgeId()
          )
            setCount(rows.length);
        })
        .catch(() => {});
    };
    update();
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    window.addEventListener("focus", update);
    return () => {
      alive = false;
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
      window.removeEventListener("focus", update);
    };
  }, []);
  return (
    <span className={"syncChip" + (!online ? " offline" : "")} role="status">
      {online ? <Wifi size={13} /> : <WifiOff size={13} />}
      <span>
        {online ? c.online : c.offline}
        {count ? " · " + c.queued(count) : ""}
      </span>
    </span>
  );
}
