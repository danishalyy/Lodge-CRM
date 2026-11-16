"use client";
import { FormEvent, useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { toast } from "sonner";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { Field } from "./ui/field";
import { Form } from "./ui/form";
import { ConfirmDialog } from "./ui/confirm-dialog";
import {
  ApiError,
  getActiveLodgeId,
  getActiveUserId,
  guestPortalAdminApi,
} from "@/lib/api";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { formatDate } from "@/lib/formatting";
import { portalCopy as c } from "@/lib/strings/guest-portal";

function usePortalScope() {
  const access = useWorkspaceAccess();
  const actor = useRef({
    userId: getActiveUserId(),
    lodgeId: getActiveLodgeId(),
  });
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
    };
  }, []);
  return {
    actor: actor.current,
    access,
    valid: () =>
      live.current &&
      access.isCurrent() &&
      actor.current.userId === getActiveUserId() &&
      actor.current.lodgeId === getActiveLodgeId(),
  };
}
function SignInQr({ url }: { url: string }) {
  const [image, setImage] = useState("");
  useEffect(() => {
    let live = true;
    setImage("");
    void QRCode.toDataURL(url, {
      width: 256,
      margin: 4,
      color: { dark: "#17181c", light: "#ffffff" },
    })
      .then((value) => {
        if (live) setImage(value);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [url]);
  return (
    <>
      {image && (
        <img
          className="guestQr"
          src={image}
          alt={c.qr}
          width={200}
          height={200}
        />
      )}
      <p>{c.qrHint}</p>
      <a
        className="guestSafeLink"
        href={url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {url}
      </a>
    </>
  );
}
export function GuestAccessManager({
  guestId,
  canInvite,
}: {
  guestId: string;
  canInvite: boolean;
}) {
  const { actor, access, valid } = usePortalScope();
  const [data, setData] = useState<any>(null),
    [stay, setStay] = useState(""),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<any>(null),
    [revoke, setRevoke] = useState<string | null>(null),
    [qr, setQr] = useState("");
  const lock = useRef(false);
  const writable = canInvite && !access.readOnly;
  async function load() {
    setLoading(true);
    try {
      const value = await guestPortalAdminApi.access(guestId, actor);
      if (!valid()) return;
      setData(value);
      setStay(
        (old) =>
          old ||
          value.stays.find(
            (row: any) => !["completed", "cancelled"].includes(row.status),
          )?.id ||
          "",
      );
      setError("");
    } catch (e) {
      if (valid()) {
        if (e instanceof ApiError && [401, 403, 404].includes(e.status)) {
          setData(null);
          setResult(null);
          setQr("");
        }
        setError((e as Error).message);
      }
    } finally {
      if (valid()) setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, [guestId]);
  async function invite(event: FormEvent) {
    event.preventDefault();
    if (lock.current || !valid() || !writable) return;
    lock.current = true;
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const value = await guestPortalAdminApi.invite(guestId, stay, actor);
      if (!valid()) return;
      setResult(value);
      toast.success(c.invited);
      await load();
    } catch (e) {
      if (valid()) setError((e as Error).message);
    } finally {
      if (valid()) {
        lock.current = false;
        setBusy(false);
      }
    }
  }
  async function revokeAccess(id: string) {
    if (lock.current || !valid() || !writable) return;
    lock.current = true;
    setBusy(true);
    try {
      await guestPortalAdminApi.revoke(id, actor);
      if (!valid()) return;
      setResult(null);
      setQr("");
      toast.success(c.revoked);
      await load();
    } catch (e) {
      if (valid()) setError((e as Error).message);
    } finally {
      if (valid()) {
        lock.current = false;
        setBusy(false);
      }
    }
  }
  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      if (valid()) toast.success(c.copied);
    } catch {
      if (valid()) setError(c.copyFailed);
    }
  }
  return (
    <section className="guestPortalAdmin">
      <h2>{c.manage}</h2>
      <p>{c.manageHint}</p>
      {error && (
        <p className="dangerText" role="alert">
          {error}
          <button className="linkButton" onClick={() => void load()}>
            {c.retry}
          </button>
        </p>
      )}
      {loading ? (
        <p role="status">{c.checking}</p>
      ) : (
        data && (
          <>
            {writable && data.stays.length > 0 && (
              <Form onSubmit={invite}>
                <Field label={c.staySelect}>
                  <select
                    className="field"
                    name="stay_id"
                    value={stay}
                    onChange={(e) => setStay(e.target.value)}
                    required
                  >
                    <option value="" disabled>
                      {c.staySelect}
                    </option>
                    {data.stays
                      .filter(
                        (row: any) =>
                          !["completed", "cancelled"].includes(row.status),
                      )
                      .map((row: any) => (
                        <option key={row.id} value={row.id}>
                          {formatDate(row.arrival_date)} –{" "}
                          {formatDate(row.departure_date)}
                        </option>
                      ))}
                  </select>
                </Field>
                <button className="button secondary" disabled={busy || !stay}>
                  {busy ? c.inviting : c.invite}
                </button>
              </Form>
            )}
            {!data.stays.length && <p>{c.unavailableStay}</p>}
            {result && (
              <div role="status">
                <p>
                  {result.delivery_status === "ready"
                    ? c.ready
                    : result.delivery_status === "pending"
                      ? c.queued
                      : c.invited}
                </p>
                {result.activation_token && (
                  <button
                    type="button"
                    className="button secondary"
                    onClick={() =>
                      void copy(
                        location.origin +
                          "/activate#token=" +
                          encodeURIComponent(result.activation_token),
                      )
                    }
                  >
                    {c.setupLink}
                  </button>
                )}
              </div>
            )}
            {!data.accesses.length ? (
              <p>{c.noAccess}</p>
            ) : (
              data.accesses.map((row: any) => (
                <article className="guestAccessEntry" key={row.id}>
                  <StatusPill
                    value={
                      row.revoked
                        ? "revoked"
                        : row.account_active
                          ? "active"
                          : "pending"
                    }
                  />
                  <div className="guestAccessActions">
                    {!row.revoked && (
                      <button
                        type="button"
                        className="button secondary"
                        onClick={() =>
                          setQr(qr === row.portal_url ? "" : row.portal_url)
                        }
                      >
                        {c.showQr}
                      </button>
                    )}
                    {!row.revoked && writable && (
                      <button
                        type="button"
                        className="button secondary"
                        disabled={busy}
                        onClick={() => setRevoke(row.id)}
                      >
                        {c.revoke}
                      </button>
                    )}
                  </div>
                  {qr === row.portal_url && !row.revoked && (
                    <SignInQr url={row.portal_url} />
                  )}
                </article>
              ))
            )}
          </>
        )
      )}
      <ConfirmDialog
        open={!!revoke}
        onOpenChange={(value) => {
          if (!value) setRevoke(null);
        }}
        title={c.revoke}
        description={c.revokeConfirm}
        actionLabel={c.revoke}
        onConfirm={() => {
          if (revoke) void revokeAccess(revoke);
        }}
      />
    </section>
  );
}
export function GuestPortalEditor({ onClose }: { onClose: () => void }) {
  const { actor, access, valid } = usePortalScope();
  const blank = () => ({
    kind: "information",
    title: "",
    body: "",
    published: false,
    position: 0,
    starts_at: null,
    ends_at: null,
  });
  const [rows, setRows] = useState<any[]>([]),
    [form, setForm] = useState<any>(blank),
    [id, setId] = useState<string | null>(null),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const lock = useRef(false);
  async function load() {
    try {
      const result = await guestPortalAdminApi.content(actor);
      if (valid()) {
        setRows(result);
        setError("");
      }
    } catch (e) {
      if (valid()) {
        setError((e as Error).message);
        if (e instanceof ApiError && [401, 403, 404].includes(e.status)) {
          setRows([]);
          setForm(blank());
          setId(null);
        }
      }
    } finally {
      if (valid()) setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    if (lock.current || !valid() || access.readOnly) return;
    lock.current = true;
    setBusy(true);
    setError("");
    try {
      const { kind, title, body, published, position, starts_at, ends_at } =
        form;
      await guestPortalAdminApi.save(
        { kind, title, body, published, position, starts_at, ends_at },
        id,
        actor,
      );
      if (!valid()) return;
      setForm(blank());
      setId(null);
      toast.success(c.saved);
      await load();
    } catch (e) {
      if (valid()) setError((e as Error).message);
    } finally {
      if (valid()) {
        lock.current = false;
        setBusy(false);
      }
    }
  }
  return (
    <Drawer onClose={onClose}>
      <div className="drawerHead">
        <h1>{c.content}</h1>
        <button
          type="button"
          className="closeButton"
          aria-label={c.close}
          onClick={onClose}
        >
          ×
        </button>
      </div>
      <p>{c.publishHint}</p>
      {error && (
        <p className="dangerText" role="alert">
          {error}
          <button className="linkButton" onClick={() => void load()}>
            {c.retry}
          </button>
        </p>
      )}
      {loading ? (
        <p role="status">{c.checking}</p>
      ) : (
        <div className="guestContentList">
          {!rows.length && <p>{c.noContent}</p>}
          {rows.map((row) => (
            <button
              type="button"
              className="button secondary"
              key={row.id}
              onClick={() => {
                setForm({ ...row });
                setId(row.id);
              }}
            >
              {row.title}
              <span>{row.published ? c.published : c.draft}</span>
            </button>
          ))}
        </div>
      )}
      <h2>{id ? c.editContent : c.addContent}</h2>
      <Form onSubmit={save}>
        <Field label={c.contentKind}>
          <select
            className="field"
            name="kind"
            value={form.kind}
            disabled={access.readOnly}
            onChange={(e) => setForm({ ...form, kind: e.target.value })}
          >
            {Object.entries(c.kinds).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </Field>
        <Field label={c.contentTitle}>
          <input
            className="field"
            name="title"
            maxLength={160}
            value={form.title}
            required
            disabled={access.readOnly}
            onChange={(e) => setForm({ ...form, title: e.target.value })}
          />
        </Field>
        <Field label={c.contentBody}>
          <textarea
            className="textarea"
            name="body"
            maxLength={4000}
            value={form.body}
            required
            disabled={access.readOnly}
            onChange={(e) => setForm({ ...form, body: e.target.value })}
          />
        </Field>
        <Field label={c.published}>
          <input
            type="checkbox"
            name="published"
            checked={form.published}
            disabled={access.readOnly}
            onChange={(e) => setForm({ ...form, published: e.target.checked })}
          />
        </Field>
        <div className="drawerActions">
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={() => {
              setForm(blank());
              setId(null);
            }}
          >
            {c.cancel}
          </button>
          <button className="button primary" disabled={busy || access.readOnly}>
            {busy ? c.saving : c.save}
          </button>
        </div>
      </Form>
    </Drawer>
  );
}
