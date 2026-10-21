"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { useCallback, useEffect, useState } from "react";
import { Bell, Archive, CheckCheck, RefreshCw } from "lucide-react";
import { accountNotificationsApi } from "@/lib/api";
import { Skeleton } from "./ui/skeleton";
type Notice = {
  id: string;
  title: string;
  body: string;
  severity: string;
  created_at: string;
  read_at: string | null;
  email_status: string | null;
};
type Prefs = {
  email_enabled: boolean;
  email_min_severity: string;
  email_verified?: boolean;
  email_configured?: boolean;
};
export default function NotificationsPage() {
  const [rows, setRows] = useState<Notice[]>([]),
    [prefs, setPrefs] = useState<Prefs>({
      email_enabled: true,
      email_min_severity: "normal",
    }),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [unreadOnly, setUnreadOnly] = useState(false),
    [severity, setSeverity] = useState(""),
    [saving, setSaving] = useState(false);
  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true);
      try {
        const data = await accountNotificationsApi.list(unreadOnly, severity);
        setRows(data);
        setError("");
      } catch (e) {
        setError(
          e instanceof Error ? e.message : "Unable to load notifications.",
        );
      } finally {
        setLoading(false);
      }
    },
    [unreadOnly, severity],
  );
  useEffect(() => {
    void load();
    let alive = true;
    accountNotificationsApi
      .preferences()
      .then((p) => {
        if (alive) setPrefs(p);
      })
      .catch((e) => {
        if (alive) setError(e.message);
      });
    const timer = setInterval(() => {
      if (!document.hidden) void load(true);
    }, 30000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [load]);
  function announce() {
    window.dispatchEvent(new Event("safarios-notifications-changed"));
  }
  async function act(action: "read" | "archive" | "all", id = "") {
    if (busy) return;
    setBusy(id || "all");
    try {
      if (action === "all") await accountNotificationsApi.readAll();
      else if (action === "read") await accountNotificationsApi.read(id);
      else await accountNotificationsApi.archive(id);
      await load(true);
      announce();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to update notification.",
      );
    } finally {
      setBusy("");
    }
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const p = await accountNotificationsApi.updatePreferences({
        email_enabled: prefs.email_enabled,
        email_min_severity: prefs.email_min_severity,
      });
      setPrefs(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save preferences.");
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">YOUR UPDATES</span>
          <h1>Notifications</h1>
          <p>
            Your assignments, important alerts, and operational updates. Only
            notifications addressed to your account appear here.
          </p>
        </div>
        <button
          className="button"
          onClick={() => act("all")}
          disabled={!!busy || !rows.some((r) => !r.read_at)}
        >
          <CheckCheck size={16} />
          Mark all read
        </button>
      </div>
      {error && (
        <div className="panel dangerText" role="alert">
          <p>{error}</p>
          <button className="button" onClick={() => load()}>
            Try again
          </button>
        </div>
      )}
      <div className="notificationLayout">
        <section className="panel">
          <div className="notificationToolbar">
            <label className="checkRow">
              <input
                type="checkbox"
                checked={unreadOnly}
                onChange={(e) => setUnreadOnly(e.target.checked)}
              />
              Unread only
            </label>
            <Field label="Filter by priority">
              <select
                id="notification-priority"
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
              >
                <option value="">All priorities</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="normal">Normal</option>
                <option value="low">Low</option>
              </select>
            </Field>
            <button
              className="iconButton"
              aria-label="Refresh notifications"
              onClick={() => load()}
            >
              <RefreshCw size={16} />
            </button>
          </div>
          {loading ? (
            <div role="status" aria-label="Loading notifications">
              <Skeleton className="h-20 mb-4" />
              <Skeleton className="h-20" />
            </div>
          ) : rows.length ? (
            <div className="notificationList">
              {rows.map((n) => (
                <article
                  key={n.id}
                  className={`notificationItem ${n.read_at ? "" : "unread"}`}
                >
                  <div className={`notificationPriority ${n.severity}`}>
                    <Bell size={18} />
                  </div>
                  <div className="notificationText">
                    <div className="notificationTitle">
                      <h2>{n.title}</h2>
                      <span className={`noticeSeverity ${n.severity}`}>
                        {n.severity}
                      </span>
                    </div>
                    <p>{n.body}</p>
                    <small>
                      {new Date(n.created_at).toLocaleString()}
                      {n.email_status
                        ? ` · Email ${n.email_status === "sent" ? "accepted by mail server" : n.email_status}`
                        : ""}
                    </small>
                    <div className="notificationActions">
                      {!n.read_at && (
                        <button
                          className="button"
                          disabled={!!busy}
                          onClick={() => act("read", n.id)}
                        >
                          Mark read
                        </button>
                      )}
                      <button
                        className="button"
                        disabled={!!busy}
                        onClick={() => act("archive", n.id)}
                        aria-label={`Archive ${n.title}`}
                      >
                        <Archive size={14} />
                        Archive
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty">
              <Bell size={28} aria-hidden="true" />
              <h2>
                {unreadOnly
                  ? "You’re all caught up"
                  : "No notifications here yet"}
              </h2>
              <p>
                {severity
                  ? "No notifications match this priority."
                  : "Assignments and important updates will appear here."}
              </p>
            </div>
          )}
        </section>
        <section className="panel">
          <h2>Email preferences</h2>
          <p>
            Invitations and password recovery are always sent. Choose which
            operational updates you also receive by email.
          </p>
          {prefs.email_configured === false && (
            <p className="notice">
              Email delivery is not configured yet. Contact your platform
              administrator. In-app notifications still work.
            </p>
          )}
          {prefs.email_verified === false && (
            <p className="notice">
              Email alerts require a verified address. New accounts are verified
              when activated; existing account owners can verify through
              password recovery.
            </p>
          )}
          <Form onSubmit={save}>
            <label className="checkRow">
              <span>Email operational notifications</span>
              <input
                type="checkbox"
                checked={prefs.email_enabled}
                onChange={(e) =>
                  setPrefs({ ...prefs, email_enabled: e.target.checked })
                }
              />
            </label>
            <Field label="Minimum email priority">
              <select
                id="notification-email-priority"
                className="field"
                value={prefs.email_min_severity}
                onChange={(e) =>
                  setPrefs({ ...prefs, email_min_severity: e.target.value })
                }
              >
                <option value="low">All updates</option>
                <option value="normal">Normal and above</option>
                <option value="high">High and critical</option>
                <option value="critical">Critical only</option>
              </select>
            </Field>
            <button className="button primary" disabled={saving}>
              {saving ? "Saving…" : "Save preferences"}
            </button>
          </Form>
        </section>
      </div>
    </>
  );
}
