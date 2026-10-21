"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { lodgeApi, operationsApi } from "@/lib/api";
type Transfer = {
  id: string;
  transfer_type: string;
  guest_name: string;
  driver_name?: string;
  vehicle_name?: string;
  scheduled_at: string;
  expected_end_at: string;
  pickup_location: string;
  dropoff_location: string;
  flight_number: string;
  passenger_count: number;
  status: string;
};
type Staff = { id: string; full_name: string; employment_status: string };
type Vehicle = {
  id: string;
  registration: string;
  name: string;
  status: string;
};
type Guest = { id: string; name: string };
type Stay = {
  id: string;
  guest_id: string;
  guest_name: string;
  status: string;
};
const next: Record<string, string | undefined> = {
  scheduled: "confirmed",
  confirmed: "en_route",
  en_route: "arrived",
  arrived: "completed",
};
export default function TransfersPage() {
  const [rows, setRows] = useState<Transfer[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
    [vehicles, setVehicles] = useState<Vehicle[]>([]),
    [guests, setGuests] = useState<Guest[]>([]),
    [stays, setStays] = useState<Stay[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    try {
      const [t, s, v, g, st] = await Promise.all([
        operationsApi.transfers.list<Transfer[]>(),
        operationsApi.staff.list<Staff[]>(),
        operationsApi.vehicles.list<Vehicle[]>(),
        lodgeApi.guests(),
        operationsApi.stays.list<Stay[]>(),
      ]);
      setRows(t);
      setStaff(s);
      setVehicles(v);
      setGuests(g);
      setStays(st);
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
      await operationsApi.transfers.create({
        transfer_type: String(f.get("transfer_type")),
        guest_id: String(f.get("guest_id")),
        stay_id: String(f.get("stay_id") || "") || null,
        driver_staff_id: String(f.get("driver_staff_id") || "") || null,
        vehicle_id: String(f.get("vehicle_id") || "") || null,
        scheduled_at: new Date(String(f.get("scheduled_at"))).toISOString(),
        expected_end_at: new Date(
          String(f.get("expected_end_at")),
        ).toISOString(),
        pickup_location: String(f.get("pickup_location")),
        dropoff_location: String(f.get("dropoff_location")),
        flight_number: String(f.get("flight_number") || ""),
        flight_time: f.get("flight_time")
          ? new Date(String(f.get("flight_time"))).toISOString()
          : null,
        passenger_count: Number(f.get("passenger_count") || 1),
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
      await operationsApi.transfers.update(id, { status });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">GUEST LOGISTICS</span>
          <h1>Transfers</h1>
          <p>
            Coordinate every pickup and drop-off, from flight details to driver
            assignments.
          </p>
        </div>
        <button className="button primary" onClick={() => setOpen(true)}>
          + Transfer
        </button>
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Guest</th>
              <th>Route</th>
              <th>Time</th>
              <th>Driver</th>
              <th>Vehicle</th>
              <th>Status</th>
              <th>Workflow</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id}>
                <td>
                  <strong>{t.guest_name}</strong>
                  <br />
                  <small>
                    {t.transfer_type}
                    {t.flight_number ? ` · ${t.flight_number}` : ""}
                  </small>
                </td>
                <td>
                  {t.pickup_location} → {t.dropoff_location}
                </td>
                <td>{new Date(t.scheduled_at).toLocaleString()}</td>
                <td>{t.driver_name || "—"}</td>
                <td>{t.vehicle_name || "—"}</td>
                <td>
                  <StatusPill value={t.status} />
                </td>
                <td>
                  {next[t.status] ? (
                    <button
                      className="button secondary"
                      onClick={() => update(t.id, next[t.status]!)}
                    >
                      {next[t.status]!.replaceAll("_", " ")}
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
          <div className="empty">No transfers have been scheduled.</div>
        )}
      </section>
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <h1>Schedule transfer</h1>
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
            <Field label="Transfer type">
              <select className="select" name="transfer_type">
                <option value="pickup">Airport pickup</option>
                <option value="dropoff">Airport drop-off</option>
                <option value="guest_transfer">Guest transfer</option>
                <option value="other">Other</option>
              </select>
            </Field>
            <Field label="Guest">
              <select className="select" name="guest_id" required>
                <option value="">Select…</option>
                {guests.map((g) => (
                  <option value={g.id} key={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Stay (optional)">
              <select className="select" name="stay_id">
                <option value="">None</option>
                {stays
                  .filter((s) => !["completed", "cancelled"].includes(s.status))
                  .map((s) => (
                    <option value={s.id} key={s.id}>
                      {s.guest_name} · {s.status}
                    </option>
                  ))}
              </select>
            </Field>
            <div className="inlineForm">
              <div>
                <Field label="Starts">
                  <input
                    className="field"
                    name="scheduled_at"
                    type="datetime-local"
                    required
                  />
                </Field>
              </div>
              <div>
                <Field label="Expected end">
                  <input
                    className="field"
                    name="expected_end_at"
                    type="datetime-local"
                    required
                  />
                </Field>
              </div>
            </div>
            <Field label="Driver">
              <select className="select" name="driver_staff_id">
                <option value="">Unassigned</option>
                {staff
                  .filter((s) => s.employment_status === "active")
                  .map((s) => (
                    <option value={s.id} key={s.id}>
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
                    <option value={v.id} key={v.id}>
                      {v.name || v.registration}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Pickup location">
              <input className="field" name="pickup_location" required />
            </Field>
            <Field label="Drop-off location">
              <input className="field" name="dropoff_location" required />
            </Field>
            <div className="inlineForm">
              <div>
                <Field label="Flight number">
                  <input className="field" name="flight_number" />
                </Field>
              </div>
              <div>
                <Field label="Flight time">
                  <input
                    className="field"
                    name="flight_time"
                    type="datetime-local"
                  />
                </Field>
              </div>
            </div>
            <Field label="Passengers">
              <input
                className="field"
                type="number"
                name="passenger_count"
                min="1"
                defaultValue="1"
              />
            </Field>
            <Field label="Notes">
              <textarea className="textarea" name="notes" />
            </Field>
            <div className="drawerActions">
              <button className="button primary">Schedule transfer</button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
