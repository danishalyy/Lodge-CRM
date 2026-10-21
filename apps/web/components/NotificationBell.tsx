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
    let live = true,
      running = false;
    async function load() {
      if (running || document.hidden) return;
      running = true;
      try {
        const r = await accountNotificationsApi.summary();
        if (live) {
          setUnread(Number(r.unread) || 0);
          setAvailable(true);
        }
      } catch {
        if (live) setAvailable(false);
      } finally {
        running = false;
      }
    }
    void load();
    const timer = setInterval(load, 30000);
    window.addEventListener("safarios-notifications-changed", load);
    document.addEventListener("visibilitychange", load);
    return () => {
      live = false;
      clearInterval(timer);
      window.removeEventListener("safarios-notifications-changed", load);
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
