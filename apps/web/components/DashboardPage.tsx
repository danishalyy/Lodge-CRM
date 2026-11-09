"use client";
import Link from "next/link";
import { PageHeader, KpiCard } from "./ui/presentation";
import { uiCopy as c } from "@/lib/strings/redesign";
import { formatDateTime, formatDate } from "@/lib/formatting";
import { eventLabel, readableLabel } from "@/lib/strings/content";

import { useEffect, useMemo, useState } from "react";
import { lodgeApi, operationsApi } from "@/lib/api";
import { OperationsCalendar, CalendarEvent, RingChart } from "./DataViz";
import SetupChecklist from "./SetupChecklist";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import StatusPill from "./StatusPill";

export default function DashboardPage() {
  const access = useWorkspaceAccess();
  const [empty, setEmpty] = useState(false);
  const [data, setData] = useState<any>(null),
    [stays, setStays] = useState<any[]>([]),
    [activities, setActivities] = useState<any[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    (async () => {
      try {
        const [dash, s, a] = await Promise.allSettled([
          lodgeApi.dashboard(),
          access.feature("stays") && access.permission("stays.view")
            ? operationsApi.stays.list<any[]>()
            : Promise.resolve([]),
          access.feature("activities") && access.permission("activities.view")
            ? operationsApi.activities.list<any[]>()
            : Promise.resolve([]),
        ]);
        if (dash.status === "rejected") throw dash.reason;
        setData(dash.value);
        if (s.status === "fulfilled") setStays(s.value);
        if (a.status === "fulfilled") setActivities(a.value);
      } catch (e: any) {
        setError(e.message);
      }
    })();
  }, []);
  const events = useMemo<CalendarEvent[]>(() => {
    const x: CalendarEvent[] = [];
    stays.forEach((s) => {
      if (s.arrival_date)
        x.push({
          date: s.arrival_date,
          label: `Arrival · ${s.guest_name || "Guest"}`,
          kind: "arrival",
        });
      if (s.departure_date)
        x.push({
          date: s.departure_date,
          label: `Departure · ${s.guest_name || "Guest"}`,
          kind: "departure",
        });
    });
    activities.forEach((a) => {
      if (a.starts_at)
        x.push({
          date: String(a.starts_at).slice(0, 10),
          label: a.title || a.activity_type || "Activity",
          kind: "activity",
        });
    });
    return x;
  }, [stays, activities]);
  if (error)
    return (
      <div className="panel statePanel">
        <span className="stateIcon danger">!</span>
        <h2>Command centre unavailable</h2>
        <p>{error}</p>
      </div>
    );
  if (!data)
    return (
      <div className="dashboardSkeleton">
        <div />
        <div />
        <div />
        <div />
      </div>
    );
  const m = data?.metrics || {},
    attention = Array.isArray(data?.attention) ? data.attention : [],
    memoryEvents = Array.isArray(data?.events) ? data.events : [],
    taskTotal = m.open_tasks || 0,
    taskHealthy = Math.max((m.open_tasks || 0) - (m.overdue_tasks || 0), 0);
  const today = new Date(),
    dateKey = [
      today.getFullYear(),
      String(today.getMonth() + 1).padStart(2, "0"),
      String(today.getDate()).padStart(2, "0"),
    ].join("-");
  const greeting =
    today.getHours() < 12
      ? c.morning
      : today.getHours() < 18
        ? c.afternoon
        : c.evening;
  const firstName = access.displayName?.trim().split(" ")[0];
  const taskHref =
    access.permission("tasks.view") && access.feature("tasks")
      ? "/tasks"
      : undefined;
  const stayHref =
    access.permission("stays.view") && access.feature("stays")
      ? "/stays"
      : undefined;
  const schedule = [
    ...stays.flatMap((s) => [
      ...(s.arrival_date === dateKey
        ? [
            {
              id: "a" + s.id,
              time: s.expected_arrival_time || "",
              title: c.arrival + " · " + (s.guest_name || c.guests),
              detail: s.unit_name || "",
              href: stayHref,
            },
          ]
        : []),
      ...(s.departure_date === dateKey
        ? [
            {
              id: "d" + s.id,
              time: s.expected_departure_time || "",
              title: c.departure + " · " + (s.guest_name || c.guests),
              detail: s.unit_name || "",
              href: stayHref,
            },
          ]
        : []),
    ]),
    ...activities
      .filter(
        (a) =>
          String(a.starts_at).slice(0, 10) === dateKey &&
          a.status !== "cancelled",
      )
      .map((a) => ({
        id: a.id,
        time: new Date(a.starts_at).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
          hour12: false,
        }),
        title: a.title || c.activity,
        detail: [a.guide_name, a.vehicle_name].filter(Boolean).join(" · "),
        href: "/activities",
      })),
  ].sort((a, b) => (a.time || "99").localeCompare(b.time || "99"));
  return (
    <>
      <PageHeader
        label={today.toLocaleDateString(undefined, {
          weekday: "long",
          day: "numeric",
          month: "long",
        })}
        title={
          <>
            {greeting}
            {firstName && (
              <>
                , <span className="greetingName">{firstName}</span>
              </>
            )}
          </>
        }
        description={access.lodgeName || data.lodge?.name || c.greetingHint}
        action={
          access.permission("tasks.manage") && access.feature("tasks") ? (
            <Link href="/tasks?create=1" className="button primary">
              {c.newTask}
            </Link>
          ) : undefined
        }
      />
      <SetupChecklist onEmpty={setEmpty} />
      {!(empty && Object.values(m).every((v) => v === 0 || v == null)) && (
        <>
          <div className="commandMetrics">
            <KpiCard
              label={c.inHouse}
              value={m.guests_in_house}
              hint={c.guestsHint}
              href={stayHref && stayHref + "?status=in_house"}
            />
            <KpiCard
              label={c.arrivalsToday}
              value={m.arrivals_today}
              hint={c.arrivalsHint}
              href={stayHref && stayHref + "?view=arrivals"}
            />
            <KpiCard
              label={c.openTasks}
              value={m.open_tasks}
              hint={c.tasksHint}
              href={taskHref}
            />
            <KpiCard
              label={c.overdue}
              value={m.overdue_tasks}
              hint={c.overdueHint}
              href={taskHref && taskHref + "?status=overdue"}
              attention={Number(m.overdue_tasks) > 0}
            />
          </div>
          <div className="commandColumns">
            <section className="panel">
              <h2 className="panelKicker">{c.run}</h2>
              <div className="runTimeline">
                {schedule.length ? (
                  schedule.map((item, index) => (
                    <div className="runEvent" key={item.id || index}>
                      <time>{item.time || "—"}</time>
                      <div>
                        {item.href ? (
                          <Link href={item.href}>{item.title}</Link>
                        ) : (
                          item.title
                        )}
                        {item.detail && <small>{item.detail}</small>}
                        {!item.time && <small>{c.dateOnly}</small>}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="empty">{c.noSchedule}</div>
                )}
              </div>
            </section>
            <section className="panel">
              <h2 className="panelKicker">{c.attention}</h2>
              <div className="attentionList">
                {attention.length ? (
                  attention.slice(0, 10).map((item: any, index: number) => {
                    const route =
                      item.type === "task" && taskHref
                        ? taskHref
                        : item.type === "maintenance" &&
                            access.permission("maintenance.view") &&
                            access.feature("maintenance")
                          ? "/maintenance"
                          : null;
                    return (
                      <div className="attentionItem" key={item.id || index}>
                        <div>
                          {route ? (
                            <Link
                              href={
                                route +
                                "?search=" +
                                encodeURIComponent(
                                  item.title.replace(/^.*?:\s*/, ""),
                                )
                              }
                            >
                              <strong>{item.title}</strong>
                            </Link>
                          ) : (
                            <strong>{item.title}</strong>
                          )}
                          {(item.detail || item.priority) && (
                            <small>
                              {item.detail || readableLabel(item.priority)}
                            </small>
                          )}
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="empty">{c.quiet}</div>
                )}
              </div>
            </section>
          </div>
          <div className="dashboardSecondary">
            {m.open_tasks != null && m.overdue_tasks != null && (
              <section className="panel">
                <h2>{c.taskHealth}</h2>
                <div className="ringPanel">
                  <RingChart
                    value={taskHealthy}
                    total={taskTotal}
                    label="On track"
                  />
                  <div className="ringLegend">
                    <div>
                      <span>{c.openTasks}</span>
                      <strong>{m.open_tasks}</strong>
                    </div>
                    <div>
                      <span>{c.overdue}</span>
                      <strong>{m.overdue_tasks}</strong>
                    </div>
                  </div>
                </div>
              </section>
            )}
            <section className="panel">
              <h2>{c.memory}</h2>
              <div className="memoryPreview">
                {memoryEvents.length ? (
                  memoryEvents.slice(0, 6).map((e: any, index: number) => (
                    <div className="memoryEvent" key={e.id || index}>
                      <span className="memoryRail">
                        <i />
                      </span>
                      <div>
                        <strong>
                          {
                            eventLabel(
                              e.event_type || e.type,
                              e.title || e.summary,
                            ).title
                          }
                        </strong>
                        <small>
                          {e.created_at
                            ? formatDateTime(e.created_at)
                            : e.summary || ""}
                        </small>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="empty">{c.noRecords}</div>
                )}
              </div>
            </section>
          </div>
          <details className="panel dashboardCalendar">
            <summary>{c.calendarLabel}</summary>
            <OperationsCalendar events={events} />
          </details>
          {["lodge_admin", "group_admin"].includes(access.roleKey || "") && (
            <details className="panel dashboardCalendar">
              <summary>{c.subscription}</summary>
              <div className="subscriptionCard">
                <div>
                  <span>{data.subscription?.package}</span>
                  <StatusPill value={data.subscription?.status || "unknown"} />
                </div>
                <small>
                  {data.subscription?.expiry_date
                    ? formatDate(data.subscription.expiry_date)
                    : "—"}
                </small>
              </div>
            </details>
          )}
        </>
      )}
    </>
  );
}
