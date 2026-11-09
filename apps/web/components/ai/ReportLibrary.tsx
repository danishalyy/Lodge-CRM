"use client";
import { useEffect, useRef, useState } from "react";
import {
  CalendarClock,
  ChevronLeft,
  Download,
  Pencil,
  RefreshCw,
  X,
} from "lucide-react";
import { toast } from "sonner";
import {
  aiReportApi,
  ApiError,
  getActiveLodgeId,
  getActiveUserId,
} from "@/lib/api";
import { reportCopy as copy } from "@/lib/strings/ai-reports";
import { formatDate, formatDateTime } from "@/lib/formatting";
import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import Drawer from "@/components/Drawer";
import ChatMessage from "./ChatMessage";
type Kind = "daily" | "weekly";
type Schedule = {
  id: string;
  kind: Kind;
  hour: number;
  minute: number;
  weekday: number;
  timezone: string;
  enabled: boolean;
  scope: "lodge" | "group";
  next_run_at: string;
};
export default function ReportLibrary({
  scopeType,
  onDenied,
  initialReportId,
}: {
  scopeType: "lodge" | "group";
  onDenied: (message: string) => void;
  initialReportId?: string;
}) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [editing, setEditing] = useState<Partial<Schedule> | null>(null),
    [detail, setDetail] = useState<any>(null),
    [opening, setOpening] = useState(false);
  const mounted = useRef(true),
    generation = useRef(0),
    detailGeneration = useRef(0),
    locked = useRef(false),
    origin = useRef(`${getActiveUserId()}:${getActiveLodgeId()}`);
  const current = () =>
    mounted.current &&
    origin.current === `${getActiveUserId()}:${getActiveLodgeId()}`;
  function fail(e: unknown) {
    if (!current()) return;
    const message = (e as Error).message;
    setError(message);
    if (e instanceof ApiError && [401, 403, 404, 409].includes(e.status)) {
      setData(null);
      setDetail(null);
      setEditing(null);
      onDenied(message);
    }
  }
  async function load() {
    const token = ++generation.current;
    try {
      const result = await aiReportApi.list(scopeType);
      if (current() && token === generation.current) {
        setData(result);
        setError("");
      }
    } catch (e) {
      fail(e);
    }
  }
  async function open(id: string) {
    const token = ++detailGeneration.current;
    setOpening(true);
    setError("");
    try {
      const result = await aiReportApi.read(id);
      if (current() && token === detailGeneration.current) setDetail(result);
    } catch (e) {
      fail(e);
    } finally {
      if (current() && token === detailGeneration.current) setOpening(false);
    }
  }
  useEffect(() => {
    mounted.current = true;
    void load();
    if (initialReportId) void open(initialReportId);
    return () => {
      mounted.current = false;
      generation.current++;
      detailGeneration.current++;
    };
  }, [scopeType]);
  useEffect(() => {
    if (
      !data?.runs?.some(
        (r: any) => r.status === "queued" || r.status === "running",
      )
    )
      return;
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 5000);
    return () => clearInterval(timer);
  }, [data?.runs]);
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!editing || locked.current) return;
    locked.current = true;
    setBusy(true);
    try {
      await aiReportApi.save({
        kind: editing.kind,
        hour: editing.hour,
        minute: editing.minute,
        weekday: editing.weekday,
        enabled: editing.enabled,
        scope: scopeType,
      });
      if (!current()) return;
      setEditing(null);
      toast.success(copy.saved);
      await load();
    } catch (e) {
      fail(e);
    } finally {
      locked.current = false;
      if (current()) setBusy(false);
    }
  }
  async function generate(schedule: Schedule) {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    try {
      await aiReportApi.run(schedule.id);
      if (!current()) return;
      toast.success(copy.queued);
      await load();
    } catch (e) {
      fail(e);
    } finally {
      locked.current = false;
      if (current()) setBusy(false);
    }
  }
  async function download() {
    if (!detail || locked.current) return;
    locked.current = true;
    setBusy(true);
    try {
      const fresh = await aiReportApi.read(detail.id);
      if (!current()) return;
      const content = [
        copy.kinds[fresh.kind as Kind],
        formatDateTime(fresh.generated_at),
        "",
        fresh.message.content,
        "",
        JSON.stringify(fresh.message.sources, null, 2),
      ].join("\n");
      const url = URL.createObjectURL(
        new Blob([content], { type: "text/plain;charset=utf-8" }),
      );
      const link = document.createElement("a");
      link.href = url;
      link.download = `SafariOS-${fresh.kind}-${fresh.generated_at.slice(0, 10)}.txt`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      fail(e);
    } finally {
      locked.current = false;
      if (current()) setBusy(false);
    }
  }
  const missingKinds: Kind[] =
    data?.kinds?.filter(
      (kind: Kind) => !data.schedules.some((s: Schedule) => s.kind === kind),
    ) || [];
  const clock = (s: Schedule) =>
    new Intl.DateTimeFormat(undefined, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: "UTC",
    }).format(new Date(Date.UTC(2000, 0, 1, s.hour, s.minute)));
  return (
    <section className="aiReportLibrary">
      <div className="pageHead">
        <div>
          <h2>{copy.title}</h2>
          <p>{copy.intro}</p>
        </div>
        <Button variant="secondary" onClick={load} aria-label={copy.refresh}>
          <RefreshCw size={17} />
        </Button>
      </div>
      <p className="muted">{copy.privacy}</p>
      {error && (
        <p role="alert" className="dangerText">
          {error}
        </p>
      )}
      {!data && !error && <p role="status">{copy.loading}</p>}
      {opening ? (
        <p role="status">{copy.opening}</p>
      ) : detail ? (
        <>
          <div className="aiReportToolbar">
            <Button
              variant="secondary"
              onClick={() => {
                setDetail(null);
                ++detailGeneration.current;
              }}
            >
              <ChevronLeft size={16} />
              {copy.all}
            </Button>
            <Button variant="secondary" disabled={busy} onClick={download}>
              <Download size={16} />
              {copy.download}
            </Button>
          </div>
          <article className="panel padded aiReportBody">
            <h2>{copy.kinds[detail.kind as Kind]}</h2>
            <p className="muted">
              {detail.scope === "group" ? copy.group : copy.lodge} ·{" "}
              {copy.generated} {formatDateTime(detail.generated_at)}
            </p>
            {detail.period?.start_date ? (
              <>
                <p>
                  {copy.cohort}: {formatDate(detail.period.start_date)} –{" "}
                  {formatDate(detail.period.end_date)}
                </p>
                <p className="muted">{copy.periodHint}</p>
              </>
            ) : (
              <p className="muted">
                {copy.snapshot} · {detail.period?.timezone}
              </p>
            )}
            {detail.insights_enabled && (
              <section className="aiReportFindings">
                <h3>{copy.followUps}</h3>
                {detail.insights.length ? (
                  <ul>
                    {detail.insights.map((f: any, i: number) => (
                      <li key={i}>
                        <strong>{f.count}</strong>{" "}
                        {
                          copy.findingLabels[
                            f.key as keyof typeof copy.findingLabels
                          ]
                        }
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p>{copy.noFollowUps}</p>
                )}
                <p className="muted">{copy.findingsHint}</p>
              </section>
            )}
            <ChatMessage
              message={detail.message}
              conversationId=""
              onDenied={onDenied}
            />
          </article>
        </>
      ) : (
        data && (
          <>
            <div className="aiReportSectionHead">
              <h3>{copy.schedules}</h3>
              {missingKinds.length > 0 && (
                <Button
                  onClick={() =>
                    setEditing({
                      kind: missingKinds[0],
                      hour: 6,
                      minute: 0,
                      weekday: 0,
                      enabled: true,
                    })
                  }
                >
                  {copy.newSchedule}
                </Button>
              )}
            </div>
            {!data.schedules.length && (
              <div className="panel padded">
                <CalendarClock size={24} />
                <p>{copy.noSchedules}</p>
              </div>
            )}
            <div className="aiReportScheduleGrid">
              {data.schedules.map((s: Schedule) => (
                <article className="panel padded" key={s.id}>
                  <div className="aiReportSectionHead">
                    <h3>{copy.kinds[s.kind]}</h3>
                    <Button
                      variant="ghost"
                      size="icon"
                      aria-label={copy.edit + ": " + copy.kinds[s.kind]}
                      onClick={() => setEditing(s)}
                    >
                      <Pencil size={17} />
                    </Button>
                  </div>
                  <p>
                    {s.kind === "weekly" ? copy.days[s.weekday] + " · " : ""}
                    {clock(s)} · {s.timezone}
                  </p>
                  <p className="muted">
                    {s.enabled
                      ? copy.next + ": " + formatDateTime(s.next_run_at)
                      : copy.paused}
                  </p>
                  <Button
                    variant="secondary"
                    disabled={busy || !s.enabled}
                    onClick={() => generate(s)}
                  >
                    {copy.generate}
                  </Button>
                </article>
              ))}
            </div>
            <div className="aiReportSectionHead">
              <h3>{copy.recent}</h3>
            </div>
            {!data.runs.length ? (
              <p className="muted">{copy.noReports}</p>
            ) : (
              <div className="aiReportRunList">
                {data.runs.map((r: any) => (
                  <article className="panel padded" key={r.id}>
                    <div>
                      <strong>{copy.kinds[r.kind as Kind]}</strong>
                      <p className="muted">
                        {r.generated_at
                          ? copy.generated +
                            " " +
                            formatDateTime(r.generated_at)
                          : copy.scheduled +
                            " " +
                            formatDateTime(r.scheduled_for)}
                      </p>
                      <span
                        role={
                          r.status === "queued" || r.status === "running"
                            ? "status"
                            : undefined
                        }
                      >
                        {copy.status[r.status as keyof typeof copy.status]}
                      </span>
                    </div>
                    {r.status === "complete" && (
                      <Button variant="secondary" onClick={() => open(r.id)}>
                        {copy.view}
                      </Button>
                    )}
                  </article>
                ))}
              </div>
            )}
            {data.runs.some(
              (r: any) => r.status === "queued" || r.status === "running",
            ) && <p className="muted">{copy.queueHint}</p>}
          </>
        )
      )}
      {editing && data && (
        <Drawer
          onClose={() => {
            if (!busy) setEditing(null);
          }}
        >
          <div className="aiActionReviewHeader">
            <h2>{editing.id ? copy.edit : copy.newSchedule}</h2>
            <Button
              variant="ghost"
              size="icon"
              aria-label={copy.close}
              disabled={busy}
              onClick={() => setEditing(null)}
            >
              <X size={18} />
            </Button>
          </div>
          <p className="muted">{data.timezone}</p>
          <Form onSubmit={save}>
            <Field label={copy.kind}>
              <select
                name="kind"
                required
                value={editing.kind}
                disabled={Boolean(editing.id)}
                onChange={(e) =>
                  setEditing({ ...editing, kind: e.target.value as Kind })
                }
              >
                {(editing.id ? [editing.kind as Kind] : missingKinds).map(
                  (k: Kind) => (
                    <option key={k} value={k}>
                      {copy.kinds[k]}
                    </option>
                  ),
                )}
              </select>
            </Field>
            <Field label={copy.time} helper={copy.timeHint}>
              <input
                type="time"
                name="local_time"
                required
                value={`${String(editing.hour ?? 6).padStart(2, "0")}:${String(editing.minute ?? 0).padStart(2, "0")}`}
                onChange={(e) => {
                  const [hour, minute] = e.target.value.split(":").map(Number);
                  setEditing({ ...editing, hour, minute });
                }}
              />
            </Field>
            {editing.kind === "weekly" && (
              <Field label={copy.day}>
                <select
                  name="weekday"
                  value={editing.weekday ?? 0}
                  onChange={(e) =>
                    setEditing({ ...editing, weekday: Number(e.target.value) })
                  }
                >
                  {copy.days.map((day, i) => (
                    <option key={day} value={i}>
                      {day}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field label={copy.enabled}>
              <input
                name="enabled"
                type="checkbox"
                checked={Boolean(editing.enabled)}
                onChange={(e) =>
                  setEditing({ ...editing, enabled: e.target.checked })
                }
              />
            </Field>
            <div className="drawerActions">
              <Button type="submit" disabled={busy}>
                {copy.save}
              </Button>
            </div>
          </Form>
        </Drawer>
      )}
    </section>
  );
}
