"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Bell } from "lucide-react";
import { accountNotificationsApi } from "@/lib/api";
export default function NotificationBell({
  platform = false,
}: {
  platform?: boolean;
}) {
  const [unread, setUnread] = useState(0),
    [available, setAvailable] = useState(true);
  useEffect(() => {
    let version = 0,
      optimistic = false;
    let live = true,
      running = false;
    async function load() {
      if (running || document.hidden || optimistic) return;
      running = true;
      const started = version;
      try {
        const r = await accountNotificationsApi.summary();
        if (live && started === version) {
          setUnread(Number(r.unread) || 0);
          setAvailable(true);
        }
      } catch {
        if (live) setAvailable(false);
      } finally {
        running = false;
        if (live && started !== version) void load();
      }
    }
    const changed = (event: Event) => {
      const delta = (event as CustomEvent).detail?.delta;
      if (typeof delta === "number") {
        optimistic = true;
        version++;
        setUnread((old) => Math.max(0, old + delta));
      } else {
        optimistic = false;
        void load();
      }
    };
    void load();
    const timer = setInterval(load, 30000);
    window.addEventListener("safarios-data-refresh", load);
    window.addEventListener("safarios-notifications-changed", changed);
    document.addEventListener("visibilitychange", load);
    return () => {
      live = false;
      clearInterval(timer);
      window.removeEventListener("safarios-data-refresh", load);
      window.removeEventListener("safarios-notifications-changed", changed);
      document.removeEventListener("visibilitychange", load);
    };
  }, []);
  return (
    <Link
      href={platform ? "/super-admin/notifications" : "/notifications"}
      className="iconButton notificationBell"
      aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
      title={
        available
          ? "Your notifications"
          : "Notifications could not be refreshed"
      }
    >
      <Bell size={18} />
      {unread > 0 && (
        <span className="notificationCount" aria-hidden="true">
          {unread > 99 ? "99+" : unread}
        </span>
      )}
      {!available && (
        <span className="notificationOffline" aria-hidden="true" />
      )}
    </Link>
  );
}
