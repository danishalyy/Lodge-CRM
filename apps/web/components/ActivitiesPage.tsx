"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { lodgeApi, operationsApi } from "@/lib/api";
type Activity = {
  id: string;
  activity_type: string;
  title: string;
  starts_at: string;
  ends_at: string;
  guide_name?: string;
  vehicle_name?: string;
  status: string;
  meeting_point: string;
  guests: { id: string; name: string }[];
};
type Staff = { id: string; full_name: string; employment_status: string };
type Vehicle = {
  id: string;
  registration: string;
  name: string;
  status: string;
};
type Guest = { id: string; name: string };
const next: Record<string, string | undefined> = {
  scheduled: "confirmed",
  confirmed: "in_progress",
  in_progress: "completed",
};
export default function ActivitiesPage() {
  const [rows, setRows] = useState<Activity[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
    [vehicles, setVehicles] = useState<Vehicle[]>([]),
    [guests, setGuests] = useState<Guest[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    try {
      const [a, s, v, g] = await Promise.all([
        operationsApi.activities.list<Activity[]>(),
        operationsApi.staff.list<Staff[]>(),
        operationsApi.vehicles.list<Vehicle[]>(),
        lodgeApi.guests(),
      ]);
      setRows(a);
      setStaff(s);
      setVehicles(v);
      setGuests(g);
    } catch (e: any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    load();
  }, []);
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await operationsApi.activities.create({
        activity_type: String(f.get("activity_type")),
        title: String(f.get("title")),
        starts_at: new Date(String(f.get("starts_at"))).toISOString(),
        ends_at: new Date(String(f.get("ends_at"))).toISOString(),
        guide_staff_id: String(f.get("guide_staff_id") || "") || null,
        vehicle_id: String(f.get("vehicle_id") || "") || null,
        guest_ids: f.getAll("guest_ids").map(String),
        meeting_point: String(f.get("meeting_point") || ""),
        notes: String(f.get("notes") || ""),
      });
      setOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function update(id: string, status: string) {
    try {
      await operationsApi.activities.update(id, { status });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">DAILY OPERATIONS</span>
          <h1>Activities & game drives</h1>
          <p>
            Plan memorable experiences. Coordinate guests, guides and vehicles
            without scheduling conflicts.
          </p>
        </div>
        <button className="button primary" onClick={() => setOpen(true)}>
          + Activity
        </button>
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Activity</th>
              <th>Time</th>
              <th>Guide</th>
              <th>Vehicle</th>
              <th>Guests</th>
              <th>Status</th>
              <th>Workflow</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td>
                  <strong>{a.title}</strong>
                  <br />
                  <small>
                    {a.activity_type} · {a.meeting_point || "No meeting point"}
                  </small>
                </td>
                <td>
                  {new Date(a.starts_at).toLocaleString()}
                  <br />
                  <small>to {new Date(a.ends_at).toLocaleTimeString()}</small>
                </td>
                <td>{a.guide_name || "—"}</td>
                <td>{a.vehicle_name || "—"}</td>
                <td>{a.guests.map((g) => g.name).join(", ") || "—"}</td>
                <td>
                  <StatusPill value={a.status} />
                </td>
                <td>
                  {next[a.status] ? (
                    <button
                      className="button secondary"
                      onClick={() => update(a.id, next[a.status]!)}
                    >
                      {next[a.status]!.replaceAll("_", " ")}
                    </button>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <div className="empty">No activities have been scheduled.</div>
        )}
      </section>
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <h1>Schedule activity</h1>
            <button
              className="closeButton"
              onClick={() => setOpen(false)}
              aria-label="Close dialog"
              type="button"
            >
              ×
            </button>
          </div>
          <Form onSubmit={create}>
            <Field label="Type">
              <select className="select" name="activity_type">
                <option>Morning game drive</option>
                <option>Afternoon game drive</option>
                <option>Bush walk</option>
                <option>Spa</option>
                <option>Meal</option>
                <option>Special dinner</option>
                <option>Other</option>
              </select>
            </Field>
            <Field label="Title">
              <input className="field" name="title" required />
            </Field>
            <div className="inlineForm">
              <div>
                <Field label="Starts">
                  <input
                    className="field"
                    name="starts_at"
                    type="datetime-local"
                    required
                  />
                </Field>
              </div>
              <div>
                <Field label="Ends">
                  <input
                    className="field"
                    name="ends_at"
                    type="datetime-local"
                    required
                  />
                </Field>
              </div>
            </div>
            <Field label="Guide / ranger">
              <select className="select" name="guide_staff_id">
                <option value="">Unassigned</option>
                {staff
                  .filter((s) => s.employment_status === "active")
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.full_name}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Vehicle">
              <select className="select" name="vehicle_id">
                <option value="">Unassigned</option>
                {vehicles
                  .filter(
                    (v) =>
                      !["maintenance", "out_of_service"].includes(v.status),
                  )
                  .map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name || v.registration}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Guests (Cmd/Ctrl to select multiple)">
              <select className="select" name="guest_ids" multiple size={6}>
                {guests.map((g) => (
                  <option value={g.id} key={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Meeting point">
              <input className="field" name="meeting_point" />
            </Field>
            <Field label="Notes">
              <textarea className="textarea" name="notes" />
            </Field>
            <div className="drawerActions">
              <button className="button primary">Schedule activity</button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
