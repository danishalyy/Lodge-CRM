"use client";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { guestCopy as copy } from "@/lib/strings/guests";
import {
  lodgeApi,
  ApiError,
  getActiveLodgeId,
  getActiveUserId,
} from "@/lib/api";
import { formatDateTime } from "@/lib/formatting";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
type Interaction = {
  id: string;
  channel: keyof typeof copy.channels;
  direction: keyof typeof copy.directions;
  subject: string;
  message: string;
  occurred_at: string;
  redacted_at?: string;
};
export default function GuestCommunications({
  guestId,
  canManage,
}: {
  guestId: string;
  canManage: boolean;
}) {
  const [rows, setRows] = useState<Interaction[]>([]),
    [more, setMore] = useState(false),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [editing, setEditing] = useState(false),
    [busy, setBusy] = useState(false);
  const epoch = useRef(0),
    mounted = useRef(false),
    lock = useRef(false),
    reference = useRef("");
  const current = () => `${getActiveUserId()}:${getActiveLodgeId()}`;
  const scope = useRef(current());
  const actor = useRef({
    userId: getActiveUserId(),
    lodgeId: getActiveLodgeId(),
  });
  const valid = (version: number) =>
    mounted.current && epoch.current === version && scope.current === current();
  const load = useCallback(
    async (offset = 0) => {
      const version = ++epoch.current;
      setLoading(true);
      setError("");
      try {
        const data = await lodgeApi.guestCommunications(
          guestId,
          offset,
          actor.current,
        );
        if (!valid(version)) return;
        setRows((previous) =>
          offset
            ? [
                ...previous,
                ...data.items.filter(
                  (item: Interaction) =>
                    !previous.some((row) => row.id === item.id),
                ),
              ]
            : data.items,
        );
        setMore(data.has_more);
      } catch (e) {
        if (valid(version)) {
          if (e instanceof ApiError && [401, 403, 404].includes(e.status)) {
            setRows([]);
            setEditing(false);
            setMore(false);
          }
          setError((e as Error).message);
        }
      } finally {
        if (valid(version)) setLoading(false);
      }
    },
    [guestId],
  );
  useEffect(() => {
    mounted.current = true;
    scope.current = current();
    void load();
    const clear = (event: Event) => {
      if (
        event instanceof StorageEvent &&
        event.key &&
        !["active_user_id", "active_lodge_id"].includes(event.key)
      )
        return;
      epoch.current++;
      setRows([]);
      setMore(false);
      setEditing(false);
      setError("");
    };
    window.addEventListener("safarios-lodge-changed", clear);
    window.addEventListener("storage", clear);
    return () => {
      mounted.current = false;
      epoch.current++;
      window.removeEventListener("safarios-lodge-changed", clear);
      window.removeEventListener("storage", clear);
    };
  }, [load]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (lock.current || !valid(epoch.current)) return;
    lock.current = true;
    setBusy(true);
    setError("");
    const version = epoch.current,
      f = new FormData(event.currentTarget);
    try {
      await lodgeApi.logGuestCommunication(
        guestId,
        {
          client_reference: reference.current,
          channel: f.get("channel"),
          direction: f.get("direction"),
          subject: f.get("subject"),
          message: f.get("message"),
        },
        actor.current,
      );
      if (!valid(version)) return;
      setEditing(false);
      await load();
    } catch (e) {
      if (valid(version)) {
        if (e instanceof ApiError && [401, 403, 404].includes(e.status)) {
          setRows([]);
          setMore(false);
          setEditing(false);
        }
        setError((e as Error).message);
      }
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <section
      aria-labelledby="guest-communications-heading"
      className="guestCommunications"
    >
      <h2 id="guest-communications-heading">{copy.communications}</h2>
      {error && (
        <div role="alert" className="dangerText">
          {error}{" "}
          <button
            type="button"
            className="linkButton"
            onClick={() => void load()}
          >
            {copy.retry}
          </button>
        </div>
      )}
      {loading && (
        <p role="status" className="sub">
          {copy.loading}
        </p>
      )}
      {!loading && !error && !rows.length && (
        <p className="sub">{copy.empty}</p>
      )}
      {rows.map((row) => (
        <article className="panel" key={row.id}>
          <small className="sub">
            {copy.channels[row.channel]} · {copy.directions[row.direction]} ·{" "}
            {formatDateTime(row.occurred_at)}
          </small>
          <h3>{row.redacted_at ? copy.redacted : row.subject}</h3>
          {!row.redacted_at && (
            <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
              {row.message}
            </p>
          )}
        </article>
      ))}
      {more && (
        <button
          type="button"
          className="button"
          disabled={loading}
          onClick={() => void load(rows.length)}
        >
          {copy.more}
        </button>
      )}
      {canManage && !editing && (
        <button
          type="button"
          className="button"
          onClick={() => {
            reference.current = crypto.randomUUID();
            setEditing(true);
          }}
        >
          {copy.log}
        </button>
      )}
      {canManage && editing && (
        <Form onSubmit={submit}>
          <p className="sub">{copy.logHint}</p>
          <div className="inlineForm">
            <Field label={copy.channel}>
              <select name="channel" className="field" defaultValue="phone">
                {Object.entries(copy.channels).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={copy.direction}>
              <select name="direction" className="field" defaultValue="inbound">
                {Object.entries(copy.directions).map(([key, label]) => (
                  <option key={key} value={key}>
                    {label}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label={copy.subject}>
            <input
              autoFocus
              className="field"
              name="subject"
              required
              maxLength={200}
            />
          </Field>
          <Field label={copy.message}>
            <textarea
              className="textarea"
              name="message"
              required
              maxLength={4000}
            />
          </Field>
          <div className="drawerActions">
            <button className="button primary" disabled={busy}>
              {busy ? copy.saving : copy.saveLog}
            </button>
          </div>
        </Form>
      )}
    </section>
  );
}
