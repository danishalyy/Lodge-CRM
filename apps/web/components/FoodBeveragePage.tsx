"use client";
import { readableLabel } from "@/lib/strings/content";
import { formatDateTime } from "@/lib/formatting";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import { authApi, lodgeApi, operationsApi } from "@/lib/api";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
export default function FoodBeveragePage() {
  const [rows, setRows] = useState<any[]>([]),
    [guests, setGuests] = useState<any[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState(""),
    [canManage, setCanManage] = useState(false);
  const load = async () => {
    try {
      const me = await authApi.me(),
        active = localStorage.getItem("active_lodge_id"),
        m = me.memberships?.find((x: any) => x.lodge_id === active);
      setCanManage(me.is_super_admin || m?.permissions?.includes("fb.manage"));
      setRows(await operationsApi.foodBeverage.list());
      try {
        setGuests(await lodgeApi.guests());
      } catch {
        setGuests([]);
      }
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
    await operationsApi.foodBeverage.create({
      name: String(f.get("name")),
      meal_type: String(f.get("meal_type")),
      scheduled_at: new Date(String(f.get("scheduled_at"))).toISOString(),
      location: String(f.get("location") || ""),
      expected_guest_count: Number(f.get("expected_guest_count") || 0),
      notes: String(f.get("notes") || ""),
      guest_ids: f.getAll("guest_ids").map(String),
    });
    setOpen(false);
    load();
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">LODGE OPERATIONS</span>
          <h1>Food & Beverage</h1>
          <p>
            Meal services, guest counts and live dietary/allergy requirements.
          </p>
        </div>
        {canManage && (
          <button className="button primary" onClick={() => setOpen(true)}>
            + Meal service
          </button>
        )}
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Service</th>
              <th>When</th>
              <th>Location</th>
              <th>Guests</th>
              <th>Dietary alerts</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>
                  <strong>{r.name}</strong>
                  <br />
                  <small>{readableLabel(r.meal_type)}</small>
                </td>
                <td>{formatDateTime(r.scheduled_at)}</td>
                <td>{r.location || "—"}</td>
                <td>{r.expected_guest_count}</td>
                <td>
                  {r.guests
                    ?.filter((g: any) => g.dietary_requirements || g.allergies)
                    .map((g: any) => (
                      <div key={g.guest_id}>
                        <strong>{g.guest_name}</strong>:{" "}
                        {[g.dietary_requirements, g.allergies]
                          .filter(Boolean)
                          .join(" • ")}
                      </div>
                    )) || "—"}
                </td>
                <td>
                  <StatusPill value={r.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <div className="empty">No meal services scheduled.</div>
        )}
      </section>
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <h1>Schedule meal service</h1>
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
            <Field label="Name">
              <input className="field" name="name" required />
            </Field>
            <Field label="Meal type">
              <select className="select" name="meal_type">
                <option value="breakfast">{readableLabel("breakfast")}</option>
                <option value="lunch">{readableLabel("lunch")}</option>
                <option value="dinner">{readableLabel("dinner")}</option>
                <option value="special_dinner">special dinner</option>
                <option value="event">{readableLabel("event")}</option>
                <option value="other">{readableLabel("other")}</option>
              </select>
            </Field>
            <Field label="Date & time">
              <input
                className="field"
                type="datetime-local"
                name="scheduled_at"
                required
              />
            </Field>
            <Field label="Location">
              <input className="field" name="location" />
            </Field>
            <Field label="Expected guest count">
              <input
                className="field"
                type="number"
                min="0"
                name="expected_guest_count"
                defaultValue="0"
              />
            </Field>
            <Field label="Guests with requirements">
              <select className="select" name="guest_ids" multiple size={8}>
                {guests.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                    {g.dietary_requirements || g.allergies
                      ? " • dietary alert"
                      : ""}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Notes">
              <textarea className="textarea" name="notes" />
            </Field>
            <button className="button primary">Schedule</button>
          </Form>
        </Drawer>
      )}
    </>
  );
}
