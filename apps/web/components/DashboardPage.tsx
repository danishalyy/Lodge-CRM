"use client";
import { useEffect, useMemo, useState } from "react";
import { lodgeApi, operationsApi } from "@/lib/api";
import {
  BarChart,
  OperationsCalendar,
  CalendarEvent,
  RingChart,
} from "./DataViz";
import UiIcon from "./UiIcon";
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
    taskTotal = (m.open_tasks || 0) + (m.overdue_tasks || 0),
    taskHealthy = Math.max((m.open_tasks || 0) - (m.overdue_tasks || 0), 0);
  const chart = [
    { label: "Guests", value: m.guests_in_house || 0 },
    { label: "Arrivals", value: m.arrivals_today || 0 },
    { label: "Tasks", value: m.open_tasks || 0 },
    { label: "Maint.", value: m.maintenance_open || 0 },
    { label: "Activities", value: m.activities_today || 0 },
    { label: "Transfers", value: m.transfers_today || 0 },
  ];
  return (
    <>
      <div className="pageHeader premiumHeader">
        <div>
          <span className="eyebrow">LODGE COMMAND CENTRE</span>
          <h1>
            {data?.lodge?.branding?.display_name ||
              data?.lodge?.name ||
              "Lodge overview"}
          </h1>
          <p>Your day at a glance. Guests, people and work, in one place.</p>
        </div>
        <div className="headerActions">
          <span className="liveBadge">
            <i />
            Live operations
          </span>
          <span className="dateChip">
            {new Date().toLocaleDateString(undefined, {
              weekday: "short",
              day: "numeric",
              month: "short",
            })}
          </span>
        </div>
      </div>
      <SetupChecklist onEmpty={setEmpty} />
      {!(empty && Object.values(m).every(value=>value === 0 || value == null)) && (
        <>
          <div className="metricGrid dashboardMetrics">
            {[
              [
                "Guests in-house",
                m.guests_in_house,
                "people",
                "Guests currently checked in",
              ],
              [
                "Arrivals today",
                m.arrivals_today,
                "calendar",
                "Expected arrivals",
              ],
              [
                "Open tasks",
                m.open_tasks,
                "tasks",
                "Operational work in progress",
              ],
              [
                "Maintenance",
                m.maintenance_open,
                "settings",
                "Open maintenance tickets",
              ],
              [
                "Activities today",
                m.activities_today,
                "leaf",
                "Scheduled lodge activities",
              ],
              [
                "Transfers today",
                m.transfers_today,
                "fleet",
                "Scheduled transfers",
              ],
              [
                "Vehicles unavailable",
                m.vehicles_unavailable,
                "fleet",
                "Unavailable fleet",
              ],
              ["Overdue tasks", m.overdue_tasks, "tasks", "Past due time"],
            ].map(([label, value, icon, hint]: any) => (
              <div
                className={`metricCard premiumMetric ${label === "Overdue tasks" && Number(value) > 0 ? "attention" : ""}`}
                key={label}
              >
                <div className="metricTop">
                  <span>{label}</span>
                  <span className="metricIcon">
                    <UiIcon name={String(icon)} />
                  </span>
                </div>
                <strong>{value}</strong>
                <small>{hint}</small>
              </div>
            ))}
          </div>
          <div className="dashboardGrid premiumDashboardGrid">
            <section className="panel span2 premiumPanel">
              <div className="panelHeader">
                <div>
                  <span className="panelKicker">TODAY</span>
                  <h2>Operational pulse</h2>
                  <p>Current activity across the lodge</p>
                </div>
                <span className="panelMeta">Real-time snapshot</span>
              </div>
              <div className="chartSurface">
                <BarChart data={chart} />
              </div>
            </section>
            <section className="panel premiumPanel">
              <div className="panelHeader">
                <div>
                  <span className="panelKicker">TASK HEALTH</span>
                  <h2>Completion pressure</h2>
                </div>
              </div>
              <div className="ringPanel">
                <RingChart
                  value={taskHealthy}
                  total={taskTotal}
                  label="On track"
                />
                <div className="ringLegend">
                  <div>
                    <span>Open</span>
                    <strong>{m.open_tasks || 0}</strong>
                  </div>
                  <div>
                    <span>Overdue</span>
                    <strong className={m.overdue_tasks ? "dangerText" : ""}>
                      {m.overdue_tasks || 0}
                    </strong>
                  </div>
                </div>
              </div>
            </section>
            <section className="panel span2 premiumPanel">
              <div className="panelHeader">
                <div>
                  <span className="panelKicker">OPERATIONS CALENDAR</span>
                  <h2>
                    {new Date().toLocaleDateString(undefined, {
                      month: "long",
                      year: "numeric",
                    })}
                  </h2>
                  <p>
                    Arrivals, departures and activities you are authorised to
                    see
                  </p>
                </div>
              </div>
              <OperationsCalendar events={events} />
            </section>
            <section className="panel premiumPanel">
              <div className="panelHeader">
                <div>
                  <span className="panelKicker">ATTENTION</span>
                  <h2>Needs review</h2>
                  <p>Priorities that need your attention</p>
                </div>
              </div>
              <div className="attentionList">
                {attention.length ? (
                  attention.slice(0, 8).map((x: any) => (
                    <div className="attentionItem" key={x.id}>
                      <span className="attentionDot" />
                      <div>
                        <strong>{x.title}</strong>
                        {x.detail && <small>{x.detail}</small>}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="empty compact">
                    Nothing currently requires attention.
                  </div>
                )}
              </div>
            </section>
            <section className="panel premiumPanel">
              <div className="panelHeader">
                <div>
                  <span className="panelKicker">SUBSCRIPTION</span>
                  <h2>Workspace access</h2>
                </div>
              </div>
              <div className="subscriptionCard">
                <div>
                  <span>Package</span>
                  <strong>
                    {data?.subscription?.package || "Not configured"}
                  </strong>
                </div>
                <div>
                  <span>Status</span>
                  <StatusPill
                    value={String(data?.subscription?.status || "unknown")
                      .toLowerCase()
                      .replaceAll(" ", "_")}
                  />
                </div>
                <div>
                  <span>Expiry</span>
                  <strong>{data?.subscription?.expiry_date || "—"}</strong>
                </div>
              </div>
            </section>
            <section className="panel span2 premiumPanel">
              <div className="panelHeader">
                <div>
                  <span className="panelKicker">OPERATIONAL MEMORY</span>
                  <h2>Recent lodge events</h2>
                  <p>The latest activity across your lodge</p>
                </div>
                <span className="panelMeta">
                  {memoryEvents.length} recorded
                </span>
              </div>
              <div className="memoryPreview">
                {memoryEvents.length ? (
                  memoryEvents.slice(0, 6).map((e: any, i: number) => (
                    <div className="memoryEvent" key={e.id || i}>
                      <span className="memoryRail">
                        <i />
                      </span>
                      <div>
                        <strong>
                          {e.title || e.event_type || "Operational event"}
                        </strong>
                        <small>
                          {e.created_at
                            ? new Date(e.created_at).toLocaleString()
                            : e.summary || ""}
                        </small>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="empty compact">
                    No operational events have been recorded yet.
                  </div>
                )}
              </div>
            </section>
          </div>
        </>
      )}
    </>
  );
}
