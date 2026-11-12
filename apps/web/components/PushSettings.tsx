"use client";
import { useEffect, useState } from "react";
import { X, Bell } from "lucide-react";
import { browserPushApi, getActiveUserId, getActiveLodgeId } from "@/lib/api";
import { deviceBinding, clearPushDevice } from "@/lib/device-state";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { pushCopy as c } from "@/lib/strings/offline";
import { Field } from "./ui/field";
import { toast } from "sonner";
type Categories = {
  task_assigned: boolean;
  request: boolean;
  overdue: boolean;
  arrival: boolean;
};
export default function PushSettings() {
  const access = useWorkspaceAccess(),
    [open, setOpen] = useState(false),
    [supported, setSupported] = useState(false),
    [config, setConfig] = useState<any>(null),
    [enabled, setEnabled] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [categories, setCategories] = useState<Categories>({
      task_assigned: true,
      request: true,
      overdue: true,
      arrival: true,
    });
  const scope = { userId: getActiveUserId(), lodgeId: getActiveLodgeId() },
    current = () =>
      access.isCurrent() &&
      scope.userId === getActiveUserId() &&
      scope.lodgeId === getActiveLodgeId();
  useEffect(() => {
    const ready =
      window.isSecureContext &&
      "serviceWorker" in navigator &&
      "PushManager" in window &&
      "Notification" in window;
    setSupported(ready);
    if (!ready || !open) return;
    let alive = true;
    void (async () => {
      try {
        const next = await browserPushApi.preferences(),
          binding = await deviceBinding();
        const registration = await navigator.serviceWorker.getRegistration(),
          subscription = await registration?.pushManager.getSubscription();
        if (alive && current()) {
          setConfig(next);
          setCategories(next.categories);
          setEnabled(
            Boolean(
              next.enabled &&
                binding &&
                binding.userId === scope.userId &&
                binding.lodgeId === scope.lodgeId &&
                next.bindings?.includes(binding.id) &&
                subscription,
            ),
          );
        }
      } catch {
        if (alive && current()) setError(c.error);
      }
    })();
    return () => {
      alive = false;
    };
  }, [access.scopeKey, open]);
  async function enable() {
    if (busy || access.readOnly || !current() || !config?.configured) return;
    // Permission prompt is exclusively inside this explicit user action.
    const permission = await Notification.requestPermission();
    if (permission !== "granted") {
      if (current()) setError(c.denied);
      return;
    }
    if (!current()) return;
    setBusy(true);
    setError("");
    try {
      await clearPushDevice();
      const registration = await navigator.serviceWorker.ready;
      if (!current()) return;
      const key = Uint8Array.from(
        atob(
          config.public_key.replace(/-/g, "+").replace(/_/g, "/") +
            "=".repeat((4 - (config.public_key.length % 4)) % 4),
        ),
        (x) => x.charCodeAt(0),
      );
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: key,
      });
      if (!current()) return;
      const json = subscription.toJSON(),
        result = await browserPushApi.subscribe({
          endpoint: json.endpoint,
          keys: json.keys,
        });
      if (!current()) return;
      await deviceBinding({ id: result.id, ...scope });
      if (current()) setEnabled(true);
    } catch {
      if (current()) {
        await clearPushDevice();
        if (current()) setError(c.error);
      }
    } finally {
      if (current()) setBusy(false);
    }
  }
  async function disable() {
    if (busy || !current()) return;
    setBusy(true);
    await clearPushDevice();
    if (current()) {
      setEnabled(false);
      setBusy(false);
      setError("");
    }
  }
  async function save() {
    if (busy || access.readOnly || !current()) return;
    setBusy(true);
    setError("");
    try {
      await browserPushApi.save({ enabled: true, categories });
      if (current()) toast.success(c.saved);
    } catch {
      if (current()) setError(c.error);
    } finally {
      if (current()) setBusy(false);
    }
  }
  return (
    <section className="panel pushSettings">
      <button
        type="button"
        className="linkButton"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <Bell size={18} aria-hidden="true" />
        {c.title}
      </button>
      {open && (
        <>
          <p>{c.description}</p>
          {!supported ? (
            <>
              <p>{c.unsupported}</p>
              <p>{c.ios}</p>
            </>
          ) : config && !config.configured ? (
            <p>{c.unconfigured}</p>
          ) : config ? (
            <>
              {enabled ? (
                <>
                  <p role="status">{c.enabled}</p>
                  {(Object.keys(categories) as (keyof Categories)[]).map(
                    (key) => (
                      <Field key={key} label={c.categories[key]}>
                        <input
                          type="checkbox"
                          checked={categories[key]}
                          disabled={busy || access.readOnly}
                          onChange={(event) =>
                            setCategories((old) => ({
                              ...old,
                              [key]: event.target.checked,
                            }))
                          }
                        />
                      </Field>
                    ),
                  )}
                  <div className="headerActions">
                    <button
                      type="button"
                      className="button primary"
                      disabled={busy || access.readOnly}
                      onClick={() => void save()}
                    >
                      {busy ? c.busy : c.save}
                    </button>
                    <button
                      type="button"
                      className="button secondary"
                      disabled={busy}
                      onClick={() => void disable()}
                    >
                      {c.disable}
                    </button>
                  </div>
                </>
              ) : (
                <button
                  type="button"
                  className="button primary"
                  disabled={busy || access.readOnly}
                  onClick={() => void enable()}
                >
                  {busy ? c.busy : c.enable}
                </button>
              )}
            </>
          ) : !error ? (
            <p role="status">{c.busy}</p>
          ) : null}
          {error && <p role="alert">{error}</p>}
        </>
      )}
    </section>
  );
}
