"use client";
import Link from "next/link";
import { SyncChip } from "./ui/sync-chip";
import { uiCopy as c } from "@/lib/strings/redesign";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { readableLabel } from "@/lib/strings/content";
import { formatTime, formatDateTime } from "@/lib/formatting";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { operationsApi } from "@/lib/api";
type Day = {
  staff: { id: string; name: string; operational_status: string };
  activities: {
    id: string;
    title: string;
    activity_type: string;
    starts_at: string;
    ends_at: string;
    status: string;
    vehicle_id?: string;
    vehicle_name?: string;
    meeting_point: string;
  }[];
  tasks: {
    id: string;
    title: string;
    priority: string;
    status: string;
    due_at?: string;
  }[];
};
type Vehicle = {
  id: string;
  registration: string;
  name: string;
  odometer_km: number;
  status: string;
};
const checks = [
  ["tyres", "Tyres and wheel condition"],
  ["brakes", "Brakes"],
  ["lights", "Lights and indicators"],
  ["fluids", "Engine fluids / leaks"],
  ["radio", "Radio / communications"],
  ["first_aid", "First-aid and emergency equipment"],
  ["recovery", "Recovery equipment"],
];
export default function RangerPage() {
  const access = useWorkspaceAccess();
  const canManage =
    access.permission("vehicle_checklists.manage") &&
    access.feature("vehicle_checklists");

  const [data, setData] = useState<Day | null>(null),
    [vehicles, setVehicles] = useState<Vehicle[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    if (!access.isCurrent()) return;
    try {
      const [d, v] = await Promise.all([
        operationsApi.rangerToday(),
        canManage &&
        access.feature("fleet") &&
        access.permission("vehicles.view")
          ? operationsApi.vehicles.list<Vehicle[]>()
          : Promise.resolve([]),
      ]);
      if (!access.isCurrent()) return;
      setData(d);
      setVehicles(v);
    } catch (e: any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    setOpen(false);
    setVehicles([]);
    load();
  }, [access.scopeKey]);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!canManage) return;
    if (!data) return;
    const f = new FormData(e.currentTarget);
    const items = checks.map(([key, label]) => ({
      item_key: key,
      label,
      result: String(f.get(key)),
      notes: String(f.get(`${key}_notes`) || ""),
    }));
    try {
      await operationsApi.checklists.create({
        vehicle_id: String(f.get("vehicle_id")),
        performed_by_staff_id: data.staff.id,
        checklist_type: "pre_drive",
        odometer_km: Number(f.get("odometer_km")),
        notes: String(f.get("notes") || ""),
        items,
      });
      setOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">RANGER / GUIDE</span>
          <h1>My safari day</h1>
          <p>
            Your live assigned activities, operational tasks and pre-drive
            workflow.
          </p>
        </div>
        <SyncChip />
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      {data && (
        <>
          <section className="panel fieldNext">
            <span className="eyebrow">{c.nextUp}</span>
            <h2>
              {data.activities.find(
                (a) => !["completed", "cancelled"].includes(a.status),
              )?.title || c.noAssignments}
            </h2>
            <p>
              {data.activities.find(
                (a) => !["completed", "cancelled"].includes(a.status),
              )?.vehicle_name || readableLabel(data.staff.operational_status)}
            </p>
            {canManage && (
              <button className="button primary" onClick={() => setOpen(true)}>
                Pre-drive checklist
              </button>
            )}
          </section>
          {access.feature("wildlife") &&
            access.permission("wildlife.manage") && (
              <Link href="/wildlife?record=1" className="mobileFieldAction">
                {c.recordSighting}
              </Link>
            )}
          <div className="twoCol">
            <section className="panel">
              <div className="panelHeader">
                <h2>Activities</h2>
              </div>
              {data.activities.map((a) => (
                <div className="row" key={a.id}>
                  <span>
                    <strong>{a.title}</strong>
                    <small>
                      {formatTime(a.starts_at)} ·{" "}
                      {a.vehicle_name || "No vehicle"} ·{" "}
                      {a.meeting_point || "No meeting point"}
                    </small>
                  </span>
                  <StatusPill value={a.status} />
                </div>
              ))}
              {!data.activities.length && (
                <div className="empty">No activities assigned today.</div>
              )}
            </section>
            <section className="panel">
              <div className="panelHeader">
                <h2>Tasks</h2>
              </div>
              {data.tasks.map((t) => (
                <div className="row" key={t.id}>
                  <span>
                    <strong>{t.title}</strong>
                    <small>
                      {t.due_at ? formatDateTime(t.due_at) : "No due time"}
                    </small>
                  </span>
                  <StatusPill value={t.status} />
                </div>
              ))}
              {!data.tasks.length && (
                <div className="empty">No open tasks assigned.</div>
              )}
            </section>
          </div>
        </>
      )}
      {open && data && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <div>
              <h1>Pre-drive checklist</h1>
              <div className="sub">
                A failed item automatically places the vehicle into maintenance
                and creates a maintenance ticket.
              </div>
            </div>
            <button
              className="closeButton"
              onClick={() => setOpen(false)}
              aria-label="Close dialog"
              type="button"
            >
              ×
            </button>
          </div>
          <Form onSubmit={submit}>
            <Field label="Vehicle">
              <select className="select" name="vehicle_id" required>
                <option value="">Select…</option>
                {vehicles
                  .filter((v) => !["out_of_service"].includes(v.status))
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name || v.registration} · {v.odometer_km} km ·{" "}
                      {readableLabel(v.status)}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Current odometer">
              <input
                className="field"
                type="number"
                min="0"
                name="odometer_km"
                required
              />
            </Field>
            {checks.map(([key, label]) => (
              <div key={key}>
                <Field label={<>{label}</>}>
                  <select className="select" name={key} required>
                    <option value="pass">Pass</option>
                    <option value="fail">Fail</option>
                    <option value="not_applicable">Not applicable</option>
                  </select>
                </Field>
                <Field label="Notes if needed">
                  <input
                    className="field"
                    name={`${key}_notes`}
                    placeholder="Notes if needed"
                  />
                </Field>
              </div>
            ))}
            <Field label="General notes">
              <textarea className="textarea" name="notes" />
            </Field>
            <div className="drawerActions">
              <button className="button primary">
                Submit completed checklist
              </button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
