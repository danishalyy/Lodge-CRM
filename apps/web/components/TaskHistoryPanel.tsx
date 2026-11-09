"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  lodgeApi,
  ApiError,
  getActiveLodgeId,
  getActiveUserId,
} from "@/lib/api";
import { taskCopy as copy, taskDuration } from "@/lib/strings/tasks";
import { readableLabel } from "@/lib/strings/content";
import { formatDate, formatDateTime } from "@/lib/formatting";
type Snapshot = Record<string, any>;
type Event = {
  id: string;
  kind: string;
  actor?: string;
  occurred_at: string;
  changed_fields: string[];
  before: Snapshot | null;
  after: Snapshot;
};
export default function TaskHistoryPanel({
  taskId,
  onDenied,
}: {
  taskId: string;
  onDenied: (message: string) => void;
}) {
  const [items, setItems] = useState<Event[]>([]),
    [timing, setTiming] = useState<Snapshot | null>(null),
    [loading, setLoading] = useState(true),
    [more, setMore] = useState(false),
    [error, setError] = useState("");
  const mounted = useRef(false),
    epoch = useRef(0),
    scope = useRef({ userId: getActiveUserId(), lodgeId: getActiveLodgeId() }),
    deny = useRef(onDenied);
  deny.current = onDenied;
  const current = (n: number) =>
    mounted.current &&
    epoch.current === n &&
    scope.current.userId === getActiveUserId() &&
    scope.current.lodgeId === getActiveLodgeId();
  const load = useCallback(
    async (offset = 0) => {
      const n = ++epoch.current;
      setLoading(true);
      setError("");
      try {
        const data = await lodgeApi.taskHistory(taskId, offset, scope.current);
        if (!current(n)) return;
        setItems((old) => (offset ? [...old, ...data.items] : data.items));
        setTiming(data.timing);
        setMore(data.has_more);
      } catch (e) {
        if (current(n)) {
          if (e instanceof ApiError && [401, 403, 404].includes(e.status)) {
            setItems([]);
            setTiming(null);
            setMore(false);
            deny.current(e.message);
          }
          setError((e as Error).message);
        }
      } finally {
        if (current(n)) setLoading(false);
      }
    },
    [taskId],
  );
  useEffect(() => {
    mounted.current = true;
    void load();
    return () => {
      mounted.current = false;
      epoch.current++;
    };
  }, [load]);
  function value(key: string, row: Snapshot): string {
    const v = row[key];
    if (v == null || v === "")
      return key === "assigned_staff_id"
        ? copy.unassigned
        : ["vehicle_id", "maintenance_ticket_id"].includes(key)
          ? copy.none
          : copy.unknown;
    if (key === "assigned_staff_id")
      return row.assigned_staff_name || copy.unknown;
    if (key === "department_id") return row.department_name || copy.unknown;
    if (key === "vehicle_id") return row.vehicle_name || copy.unknown;
    if (key === "maintenance_ticket_id")
      return row.maintenance_title || copy.unknown;
    if (key.endsWith("_at")) return formatDateTime(v);
    if (key === "recurrence_end_date") return formatDate(v);
    if (typeof v === "boolean") return v ? copy.yes : copy.no;
    if (["status", "priority"].includes(key)) return readableLabel(v);
    return String(v);
  }
  return (
    <section className="taskHistory" aria-labelledby="task-history-heading">
      <h2 id="task-history-heading">{copy.history}</h2>
      {error && (
        <p role="alert" className="dangerText">
          {error}{" "}
          <button
            type="button"
            className="linkButton"
            onClick={() => void load()}
          >
            {copy.retry}
          </button>
        </p>
      )}
      {loading && (
        <p role="status" className="sub">
          {copy.loading}
        </p>
      )}
      {timing && (
        <>
          <h3>{copy.timing}</h3>
          <dl className="taskTiming">
            {[
              "created_at",
              "assigned_at",
              "accepted_at",
              "started_at",
              "completed_at",
            ].map((key) => (
              <div key={key}>
                <dt>{copy.fields[key]}</dt>
                <dd>
                  {timing[key] ? formatDateTime(timing[key]) : copy.unknown}
                </dd>
              </div>
            ))}
            {timing.vehicle_name && (
              <div>
                <dt>{copy.vehicle}</dt>
                <dd>{timing.vehicle_name}</dd>
              </div>
            )}
            {timing.maintenance_title && (
              <div>
                <dt>{copy.maintenance}</dt>
                <dd>{timing.maintenance_title}</dd>
              </div>
            )}
            <div>
              <dt>{copy.completion}</dt>
              <dd>{taskDuration(timing.completion_seconds)}</dd>
            </div>
            {timing.overdue_seconds > 0 && (
              <div>
                <dt>{copy.overdue}</dt>
                <dd>{taskDuration(timing.overdue_seconds)}</dd>
              </div>
            )}
          </dl>
        </>
      )}
      {!loading && !error && !items.length && (
        <p className="sub">{copy.empty}</p>
      )}
      {items.length > 0 && <p className="sub">{copy.coverage}</p>}
      {items.map((item) => (
        <article className="taskHistoryEvent" key={item.id}>
          <div>
            <strong>
              {item.kind === "created" ? copy.created : copy.updated}
            </strong>
            <time dateTime={item.occurred_at}>
              {formatDateTime(item.occurred_at)}
            </time>
          </div>
          <p className="sub">
            {copy.by} {item.actor || copy.unknownActor}
          </p>
          {item.kind === "created" ? (
            <p>
              {copy.fields.status}: {readableLabel(item.after.status)}
              {item.after.assigned_staff_name
                ? ` · ${item.after.assigned_staff_name}`
                : ""}
            </p>
          ) : (
            <ul>
              {item.changed_fields
                .filter(
                  (key) =>
                    ![
                      "assigned_at",
                      "accepted_at",
                      "started_at",
                      "completed_at",
                    ].includes(key),
                )
                .map((key) => (
                  <li key={key}>
                    {["title", "description", "guest_id", "unit_id"].includes(
                      key,
                    ) ? (
                      copy.changed(copy.fields[key] || readableLabel(key))
                    ) : (
                      <>
                        {copy.fields[key] || readableLabel(key)}:{" "}
                        {value(key, item.before || {})} →{" "}
                        {value(key, item.after)}
                      </>
                    )}
                  </li>
                ))}
            </ul>
          )}
        </article>
      ))}
      {more && (
        <button
          type="button"
          className="button"
          disabled={loading}
          onClick={() => void load(items.length)}
        >
          {copy.more}
        </button>
      )}
    </section>
  );
}
