"use client";
import { formatMoney, formatting } from "@/lib/formatting";
import { formatDateTime } from "@/lib/formatting";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import { operationsApi } from "@/lib/api";
type Vehicle = {
  id: string;
  registration: string;
  name: string;
  odometer_km: number;
};
type Staff = { id: string; full_name: string; employment_status: string };
type Fuel = {
  id: string;
  vehicle_name: string;
  recorded_by?: string;
  litres: number;
  odometer_km: number;
  cost_cents?: number;
  supplier: string;
  reference: string;
  recorded_at: string;
};
export default function FuelPage() {
  const [rows, setRows] = useState<Fuel[]>([]),
    [vehicles, setVehicles] = useState<Vehicle[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    try {
      const [r, v, s] = await Promise.all([
        operationsApi.fuel.list<Fuel[]>(),
        operationsApi.vehicles.list<Vehicle[]>(),
        operationsApi.staff.list<Staff[]>(),
      ]);
      setRows(r);
      setVehicles(v);
      setStaff(s);
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
      await operationsApi.fuel.create({
        vehicle_id: String(f.get("vehicle_id")),
        recorded_by_staff_id:
          String(f.get("recorded_by_staff_id") || "") || null,
        litres: Number(f.get("litres")),
        odometer_km: Number(f.get("odometer_km")),
        cost_cents: f.get("cost")
          ? Math.round(Number(f.get("cost")) * 100)
          : null,
        supplier: String(f.get("supplier") || ""),
        reference: String(f.get("reference") || ""),
        notes: String(f.get("notes") || ""),
        recorded_at: f.get("recorded_at")
          ? new Date(String(f.get("recorded_at"))).toISOString()
          : null,
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
          <span className="eyebrow">FLEET</span>
          <h1>Fuel</h1>
          <p>Track refuelling, mileage and costs across your fleet.</p>
        </div>
        <button className="button primary" onClick={() => setOpen(true)}>
          + Fuel record
        </button>
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Date</th>
              <th>Vehicle</th>
              <th>Litres</th>
              <th>Odometer</th>
              <th>Cost</th>
              <th>Recorded by</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{formatDateTime(r.recorded_at)}</td>
                <td>{r.vehicle_name}</td>
                <td>{r.litres.toFixed(2)} L</td>
                <td>{r.odometer_km.toLocaleString()} km</td>
                <td>
                  {r.cost_cents == null ? "—" : formatMoney(r.cost_cents)}
                </td>
                <td>{r.recorded_by || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <div className="empty">No fuel records have been entered.</div>
        )}
      </section>
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <h1>Record fuel</h1>
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
            <Field label="Vehicle">
              <select className="select" name="vehicle_id" required>
                <option value="">Select…</option>
                {vehicles.map((v) => (
                  <option value={v.id} key={v.id}>
                    {v.name || v.registration} · {v.odometer_km} km
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Recorded by">
              <select className="select" name="recorded_by_staff_id">
                <option value="">Not linked to staff profile</option>
                {staff
                  .filter((s) => s.employment_status === "active")
                  .map((s) => (
                    <option value={s.id} key={s.id}>
                      {s.full_name}
                    </option>
                  ))}
              </select>
            </Field>
            <div className="inlineForm">
              <div>
                <Field label="Litres">
                  <input
                    className="field"
                    name="litres"
                    type="number"
                    min="0.01"
                    step="0.01"
                    required
                  />
                </Field>
              </div>
              <div>
                <Field label="Odometer (km)">
                  <input
                    className="field"
                    name="odometer_km"
                    type="number"
                    min="0"
                    required
                  />
                </Field>
              </div>
            </div>
            <div className="inlineForm">
              <div>
                <Field label={`Cost (${formatting().currency || "ZAR"})`}>
                  <input
                    className="field"
                    name="cost"
                    type="number"
                    min="0"
                    step="0.01"
                  />
                </Field>
              </div>
              <div>
                <Field label="Date/time">
                  <input
                    className="field"
                    name="recorded_at"
                    type="datetime-local"
                  />
                </Field>
              </div>
            </div>
            <Field label="Supplier">
              <input className="field" name="supplier" />
            </Field>
            <Field label="Reference / receipt">
              <input className="field" name="reference" />
            </Field>
            <Field label="Notes">
              <textarea className="textarea" name="notes" />
            </Field>
            <div className="drawerActions">
              <button className="button primary">Save fuel record</button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
