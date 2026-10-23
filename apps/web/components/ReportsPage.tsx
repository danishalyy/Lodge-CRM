"use client";
import { readableLabel } from "@/lib/strings/content";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { intelligenceApi } from "@/lib/api";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { BarChart, RingChart } from "./DataViz";
const iso = (d: Date) => d.toISOString().slice(0, 10);
export default function ReportsPage() {
  const access = useWorkspaceAccess();
  const [start, setStart] = useState(iso(new Date(Date.now() - 29 * 86400000))),
    [end, setEnd] = useState(iso(new Date())),
    [data, setData] = useState<any>(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  async function load(feedback = false) {
    setLoading(true);
    setError("");
    try {
      const result = await intelligenceApi.reportSummary(start, end);
      setData(result);
      if (feedback) toast.success("Report updated");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  const enabled = (feature: string, value: any) =>
    access.feature(feature) && value != null;
  const chart = data
    ? [
        { label: "Tasks", feature: "tasks", value: data.tasks?.created },
        {
          label: "Maintenance",
          feature: "maintenance",
          value: data.maintenance?.created,
        },
        {
          label: "Requests",
          feature: "guest_requests",
          value: data.guest_requests?.created,
        },
        {
          label: "Activities",
          feature: "activities",
          value: data.safari?.activities,
        },
        {
          label: "Transfers",
          feature: "transfers",
          value: data.safari?.transfers,
        },
        {
          label: "Sightings",
          feature: "wildlife",
          value: data.safari?.wildlife_sightings,
        },
      ].filter((r) => enabled(r.feature, r.value))
    : [];
  const operations = data
    ? [
        {
          label: "Tasks created",
          feature: "tasks",
          value: data.tasks?.created,
        },
        {
          label: "Average task completion",
          feature: "tasks",
          value: data.tasks
            ? data.tasks.average_completion_hours == null
              ? "—"
              : `${data.tasks.average_completion_hours} h`
            : null,
        },
        {
          label: "Maintenance created",
          feature: "maintenance",
          value: data.maintenance?.created,
        },
        {
          label: "Overlapping stays",
          feature: "stays",
          value: data.stays?.overlapping_period,
        },
      ].filter((r) => enabled(r.feature, r.value))
    : [];
  const safari = data
    ? [
        {
          label: "Activities",
          feature: "activities",
          value: data.safari?.activities,
        },
        {
          label: "Transfers",
          feature: "transfers",
          value: data.safari?.transfers,
        },
        {
          label: "Wildlife sightings",
          feature: "wildlife",
          value: data.safari?.wildlife_sightings,
        },
      ].filter((r) => enabled(r.feature, r.value))
    : [];
  return (
    <>
      <div className="pageHeader premiumHeader">
        <div>
          <span className="eyebrow">REPORTS & ANALYTICS</span>
          <h1>Operational intelligence</h1>
          <p>
            A clear view of authorized, enabled operations for your selected
            period.
          </p>
        </div>
      </div>
      <section className="panel filterPanel">
        <div className="filterGroup">
          <label>
            From
            <input
              className="field"
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
            />
          </label>
          <label>
            To
            <input
              className="field"
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
            />
          </label>
        </div>
        <button
          className="button primary"
          disabled={loading}
          onClick={() => load(true)}
        >
          {loading ? "Running…" : "Run report"}
        </button>
      </section>
      {error && (
        <section className="panel dangerText" role="alert">
          <p>{error}</p>
          <button className="button" onClick={() => load()}>
            Try again
          </button>
        </section>
      )}
      {loading ? (
        <section className="panel" role="status">
          Loading operational report…
        </section>
      ) : (
        data && (
          <>
            <div className="metricGrid">
              {enabled("tasks", data.tasks) && (
                <section className="metricCard">
                  <span>Tasks completed</span>
                  <strong>{data.tasks.completed}</strong>
                  <small>{data.tasks.completion_rate}% completion rate</small>
                </section>
              )}
              {enabled("maintenance", data.maintenance) && (
                <section className="metricCard">
                  <span>Maintenance completed</span>
                  <strong>{data.maintenance.completed}</strong>
                  <small>{data.maintenance.critical} critical created</small>
                </section>
              )}
              {enabled("guest_requests", data.guest_requests) && (
                <section className="metricCard">
                  <span>Requests resolved</span>
                  <strong>{data.guest_requests.resolved}</strong>
                  <small>{data.guest_requests.created} created</small>
                </section>
              )}
              {enabled("fuel", data.fleet) && (
                <section className="metricCard">
                  <span>Fuel used</span>
                  <strong>{data.fleet.fuel_litres.toLocaleString()} L</strong>
                  <small>{data.fleet.fuel_records} records</small>
                </section>
              )}
            </div>
            <div className="analyticsGrid">
              {!!chart.length && (
                <section className="panel premiumPanel span2">
                  <div className="panelHeader">
                    <div>
                      <span className="panelKicker">WORKLOAD</span>
                      <h2>Operational volume</h2>
                      <p>Records created during the selected period</p>
                    </div>
                  </div>
                  <div className="chartSurface">
                    <BarChart data={chart} />
                  </div>
                </section>
              )}
              {enabled("tasks", data.tasks) && (
                <section className="panel premiumPanel">
                  <div className="panelHeader">
                    <h2>Completion rate</h2>
                  </div>
                  <div className="ringPanel">
                    <RingChart
                      value={data.tasks.completed}
                      total={data.tasks.created}
                      label="Completed"
                    />
                  </div>
                </section>
              )}
            </div>
            <div className="twoCol">
              {!!operations.length && (
                <section className="panel">
                  <h2>Operations</h2>
                  {operations.map((r) => (
                    <div className="checkRow" key={r.label}>
                      <span>{r.label}</span>
                      <strong>{String(r.value)}</strong>
                    </div>
                  ))}
                </section>
              )}
              {!!safari.length && (
                <section className="panel">
                  <h2>Safari & Fleet</h2>
                  {safari.map((r) => (
                    <div className="checkRow" key={r.label}>
                      <span>{r.label}</span>
                      <strong>{String(r.value)}</strong>
                    </div>
                  ))}
                </section>
              )}
            </div>
            {enabled("units", data.rooms) && (
              <section className="panel" style={{ marginTop: 24 }}>
                <div className="panelHeader">
                  <h2>Room status now</h2>
                </div>
                <div className="statusTiles">
                  {Object.entries(data.rooms.by_status || {}).map(
                    ([key, value]) => (
                      <div className="statusTile" key={key}>
                        <span>{readableLabel(key)}</span>
                        <strong>{String(value)}</strong>
                      </div>
                    ),
                  )}
                  {!Object.keys(data.rooms.by_status || {}).length && (
                    <p className="empty">No rooms have been created.</p>
                  )}
                </div>
              </section>
            )}
            {!chart.length &&
              !operations.length &&
              !safari.length &&
              !enabled("units", data.rooms) && (
                <section className="panel empty">
                  <h2>No report sections available</h2>
                  <p>There are no enabled report sections for this account.</p>
                </section>
              )}
          </>
        )
      )}
    </>
  );
}
