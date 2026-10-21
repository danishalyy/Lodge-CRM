"use client";
import { formatDate, formatDateTime } from "@/lib/formatting";
import { eventLabel, readableLabel } from "@/lib/strings/content";

import { Field } from "@/components/ui/field";
import { useEffect, useState } from "react";
import { intelligenceApi } from "@/lib/api";
type Event = {
  id: string;
  event_type: string;
  resource_type: string;
  resource_id: string;
  summary: string;
  detail: string;
  created_at: string;
};
export default function OperationalMemoryPage() {
  const [rows, setRows] = useState<Event[]>([]),
    [type, setType] = useState(""),
    [resource, setResource] = useState(""),
    [error, setError] = useState("");
  const load = async () => {
    try {
      setRows(
        await intelligenceApi.operationalMemory({
          event_type: type || undefined,
          resource_type: resource || undefined,
        }),
      );
    } catch (e: any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    load();
  }, []);
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">OPERATIONAL MEMORY</span>
          <h1>Event History</h1>
          <p>
            A connected timeline of the decisions and activity across your
            lodge.
          </p>
        </div>
      </div>
      <div className="toolbar">
        <Field label="Event type">
          <input
            className="field"
            placeholder="Event type"
            value={type}
            onChange={(e) => setType(e.target.value)}
          />
        </Field>
        <Field label="Resource type">
          <input
            className="field"
            placeholder="Resource type"
            value={resource}
            onChange={(e) => setResource(e.target.value)}
          />
        </Field>
        <button className="button" onClick={load}>
          Filter
        </button>
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel">
        {rows.map((e) => (
          <div className="timelineRow" key={e.id}>
            <time>{formatDate(e.created_at)}</time>
            <span className="timelineDot" />
            <div>
              <strong>{eventLabel(e.event_type, e.summary).title}</strong>
              <small>
                {formatDateTime(e.created_at)} ·{" "}
                {eventLabel(e.event_type).title} ·{" "}
                {readableLabel(e.resource_type)}
              </small>
              {e.detail && (
                <p
                  style={{
                    fontSize: 12,
                    color: "var(--tx2)",
                    margin: "5px 0 0",
                  }}
                >
                  {e.detail}
                </p>
              )}
            </div>
          </div>
        ))}
        {!rows.length && (
          <div className="empty">No operational events match this filter.</div>
        )}
      </section>
    </>
  );
}
