"use client";
import { formatDateTime } from "@/lib/formatting";
import { readableLabel } from "@/lib/strings/content";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { useCallback, useEffect, useState, useRef } from "react";
import { Bell, Archive, CheckCheck, RefreshCw } from "lucide-react";
import { reportCopy } from "@/lib/strings/ai-reports";
import {
  accountNotificationsApi,
  getActiveUserId,
  getActiveLodgeId,
  ApiError,
  setActiveLodgeId,
} from "@/lib/api";
import { toast } from "sonner";
import { useDataRefresh } from "@/lib/use-instant-actions";
import { instantCopy as instant } from "@/lib/strings/interactivity";
import { Skeleton } from "./ui/skeleton";
type Notice = {
  resource_type?: string;
  resource_id?: string;
  lodge_id?: string;
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
  const actionLock = useRef(false);
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      if (actionLock.current)
        window.dispatchEvent(new Event("safarios-notifications-changed"));
    };
  }, []);
  const load = useCallback(
    async (quiet = false) => {
      if (!quiet) setLoading(true);
      try {
        const data = await accountNotificationsApi.list(unreadOnly, severity);
        if (!actionLock.current) setRows(data);
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
  useDataRefresh(() => load(true), !!busy);
  function announce(delta?: number) {
    window.dispatchEvent(
      new CustomEvent("safarios-notifications-changed", { detail: { delta } }),
    );
  }
  async function act(action: "read" | "archive" | "all", id = "") {
    if (actionLock.current) return;
    actionLock.current = true;
    const actor = `${getActiveUserId()}:${getActiveLodgeId()}`;
    const current = () =>
      alive.current && actor === `${getActiveUserId()}:${getActiveLodgeId()}`;
    const before = rows;
    const optimistic = action !== "archive";
    const delta =
      action === "all"
        ? -rows.filter((n) => !n.read_at).length
        : before.find((n) => n.id === id)?.read_at
          ? 0
          : -1;
    setBusy(id || "all");
    setError("");
    if (optimistic) {
      setRows((old) =>
        old.map((n) =>
          action === "all" || n.id === id
            ? { ...n, read_at: n.read_at || new Date().toISOString() }
            : n,
        ),
      );
      announce(action === "all" ? -Infinity : delta);
    }
    try {
      if (action === "all") await accountNotificationsApi.readAll(true);
      else if (action === "read") await accountNotificationsApi.read(id, true);
      else await accountNotificationsApi.archive(id);
      if (!current()) return;
      if (optimistic)
        toast.success(
          action === "all" ? instant.allRead : instant.notification,
        );
    } catch (e) {
      if (!current()) return;
      setRows(before);
      const message =
        e instanceof Error ? e.message : "Unable to update notification.";
      setError(message);
      if (!(e instanceof ApiError && [401, 403, 404, 409].includes(e.status)))
        toast.error(message, {
          action: {
            label: instant.retry,
            onClick: () => {
              if (current()) void act(action, id);
            },
          },
        });
    } finally {
      actionLock.current = false;
      if (current()) {
        setBusy("");
        await load(true);
      }
      if (actor === `${getActiveUserId()}:${getActiveLodgeId()}`) announce();
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
          {busy === "all" ? instant.saving : "Mark all read"}
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
          {loading && !rows.length ? (
            <div role="status" aria-label="Loading notifications">
              <Skeleton className="h-20 mb-4" />
              <Skeleton className="h-20" />
            </div>
          ) : rows.length ? (
            <div className="notificationList">
              {rows.map((n) => (
                <article
                  key={n.id}
                  data-record-id={n.id}
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
                      {formatDateTime(n.created_at)}
                      {n.email_status
                        ? ` · Email ${readableLabel(n.email_status)}`
                        : ""}
                    </small>
                    <div className="notificationActions">
                      {["ai_report", "ai_group_report"].includes(
                        n.resource_type || "",
                      ) &&
                        n.resource_id &&
                        n.lodge_id && (
                          <button
                            className="button"
                            onClick={() => {
                              setActiveLodgeId(n.lodge_id!);
                              location.assign(
                                "/lodge-ai?scope=" +
                                  (n.resource_type === "ai_group_report"
                                    ? "group"
                                    : "lodge") +
                                  "&report=" +
                                  encodeURIComponent(n.resource_id!),
                              );
                            }}
                          >
                            {reportCopy.view}
                          </button>
                        )}
                      {(!n.read_at || busy === n.id) && (
                        <button
                          className="button"
                          disabled={!!busy}
                          onClick={() => act("read", n.id)}
                        >
                          {busy === n.id ? instant.saving : "Mark read"}
                        </button>
                      )}
                      <button
                        className="button"
                        disabled={!!busy}
                        onClick={() => act("archive", n.id)}
                        aria-busy={busy === n.id}
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
