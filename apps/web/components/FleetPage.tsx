"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { operationsApi } from "@/lib/api";
type Vehicle = {
  id: string;
  registration: string;
  name: string;
  make: string;
  model: string;
  year?: number;
  odometer_km: number;
  status: string;
  service_due_odometer_km?: number;
  service_due_in_km?: number;
  notes: string;
};
export default function FleetPage() {
  const [rows, setRows] = useState<Vehicle[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    try {
      setRows(await operationsApi.vehicles.list<Vehicle[]>());
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
      await operationsApi.vehicles.create({
        registration: String(f.get("registration")),
        name: String(f.get("name") || ""),
        make: String(f.get("make") || ""),
        model: String(f.get("model") || ""),
        year: f.get("year") ? Number(f.get("year")) : null,
        odometer_km: Number(f.get("odometer_km") || 0),
        fuel_capacity_litres: f.get("fuel_capacity_litres")
          ? Number(f.get("fuel_capacity_litres"))
          : null,
        service_due_odometer_km: f.get("service_due_odometer_km")
          ? Number(f.get("service_due_odometer_km"))
          : null,
        notes: String(f.get("notes") || ""),
      });
      setOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function upd(id: string, body: any) {
    try {
      await operationsApi.vehicles.update(id, body);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">SAFARI OPERATIONS</span>
          <h1>Fleet</h1>
          <p>
            Keep your fleet ready, maintained and available for the next
            journey.
          </p>
        </div>
        <button className="button primary" onClick={() => setOpen(true)}>
          + Vehicle
        </button>
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Vehicle</th>
              <th>Registration</th>
              <th>Odometer</th>
              <th>Service</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((v) => (
              <tr key={v.id}>
                <td>
                  <strong>
                    {v.name || `${v.make} ${v.model}`.trim() || "Vehicle"}
                  </strong>
                  <br />
                  <small>
                    {[v.make, v.model, v.year].filter(Boolean).join(" ") || "—"}
                  </small>
                </td>
                <td>{v.registration}</td>
                <td>{v.odometer_km.toLocaleString()} km</td>
                <td>
                  {v.service_due_in_km == null ? (
                    "—"
                  ) : v.service_due_in_km <= 0 ? (
                    <span className="dangerText">Due now</span>
                  ) : (
                    `${v.service_due_in_km.toLocaleString()} km`
                  )}
                </td>
                <td>
                  <select
                    className="select"
                    value={v.status}
                    onChange={(e) => upd(v.id, { status: e.target.value })}
                    aria-label="Status"
                  >
                    <option value="ready">Ready</option>
                    <option value="assigned">Assigned</option>
                    <option value="maintenance">Maintenance</option>
                    <option value="out_of_service">Out of service</option>
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <div className="empty">No vehicles have been added.</div>
        )}
      </section>
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <h1>Add vehicle</h1>
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
            <Field label="Registration">
              <input className="field" name="registration" required />
            </Field>
            <Field label="Internal name">
              <input className="field" name="name" />
            </Field>
            <div className="inlineForm">
              <div>
                <Field label="Make">
                  <input className="field" name="make" />
                </Field>
              </div>
              <div>
                <Field label="Model">
                  <input className="field" name="model" />
                </Field>
              </div>
            </div>
            <div className="inlineForm">
              <div>
                <Field label="Year">
                  <input
                    className="field"
                    name="year"
                    type="number"
                    min="1900"
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
                    defaultValue="0"
                  />
                </Field>
              </div>
            </div>
            <div className="inlineForm">
              <div>
                <Field label="Fuel capacity (L)">
                  <input
                    className="field"
                    name="fuel_capacity_litres"
                    type="number"
                    min="0"
                    step="0.1"
                  />
                </Field>
              </div>
              <div>
                <Field label="Service due odometer">
                  <input
                    className="field"
                    name="service_due_odometer_km"
                    type="number"
                    min="0"
                  />
                </Field>
              </div>
            </div>
            <Field label="Notes">
              <textarea className="textarea" name="notes" />
            </Field>
            <div className="drawerActions">
              <button className="button primary">Create vehicle</button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
