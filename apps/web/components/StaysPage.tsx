"use client";
import { readableLabel } from "@/lib/strings/content";
import { formatDate } from "@/lib/formatting";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { lodgeApi, operationsApi } from "@/lib/api";
type Guest = { id: string; name: string };
type Room = { id: string; name: string; status: string };
type Stay = {
  id: string;
  guest_name: string;
  unit_name: string;
  arrival_date: string;
  departure_date: string;
  party_size: number;
  status: string;
  expected_arrival_time: string;
  expected_departure_time: string;
};
const next: Record<string, string | undefined> = {
  upcoming: "arriving",
  arriving: "in_house",
  in_house: "departing",
  departing: "completed",
};
export default function StaysPage() {
  const access = useWorkspaceAccess();
  const canManage = access.permission("stays.manage");
  const [rows, setRows] = useState<Stay[]>([]),
    [guests, setGuests] = useState<Guest[]>([]),
    [rooms, setRooms] = useState<Room[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    try {
      const [s, g, r] = await Promise.all([
        operationsApi.stays.list<Stay[]>(),
        canManage &&
        access.feature("guests") &&
        access.permission("guests.view")
          ? lodgeApi.guests()
          : Promise.resolve([]),
        canManage && access.feature("units") && access.permission("units.view")
          ? lodgeApi.rooms()
          : Promise.resolve([]),
      ]);
      setRows(s);
      setGuests(g);
      setRooms(r);
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
      await operationsApi.stays.create({
        guest_id: String(f.get("guest_id")),
        unit_id: String(f.get("unit_id")),
        arrival_date: String(f.get("arrival_date")),
        departure_date: String(f.get("departure_date")),
        party_size: Number(f.get("party_size") || 1),
        expected_arrival_time: String(f.get("expected_arrival_time") || ""),
        expected_departure_time: String(f.get("expected_departure_time") || ""),
        transfer_notes: String(f.get("transfer_notes") || ""),
        special_requirements: String(f.get("special_requirements") || ""),
      });
      setOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function advance(r: Stay) {
    const s = next[r.status];
    if (!s) return;
    try {
      await operationsApi.stays.update(r.id, { status: s });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">ARRIVALS & DEPARTURES</span>
          <h1>Stays</h1>
          <p>
            Coordinate arrivals, room assignments and departures with
            confidence.
          </p>
        </div>
        {canManage && (
          <button
            className="button primary"
            onClick={() => setOpen(true)}
            disabled={!guests.length || !rooms.length}
          >
            + Stay
          </button>
        )}
      </div>
      {canManage && (!guests.length || !rooms.length) && (
        <div className="panel">
          <p>Create at least one guest and one room before creating a stay.</p>
        </div>
      )}
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Guest</th>
              <th>Unit</th>
              <th>Arrival</th>
              <th>Departure</th>
              <th>Party</th>
              <th>Status</th>
              <th>Workflow</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.guest_name}</td>
                <td>{r.unit_name}</td>
                <td>
                  {formatDate(r.arrival_date)} {r.expected_arrival_time}
                </td>
                <td>
                  {formatDate(r.departure_date)} {r.expected_departure_time}
                </td>
                <td>{r.party_size}</td>
                <td>
                  <StatusPill value={r.status} />
                </td>
                <td>
                  {canManage && next[r.status] ? (
                    <button
                      className="button secondary"
                      onClick={() => advance(r)}
                    >
                      Mark {readableLabel(next[r.status]!)}
                    </button>
                  ) : (
                    <span>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <div className="empty">No stays have been created.</div>
        )}
      </section>
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <div>
              <h1>New stay</h1>
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
          <Form onSubmit={create}>
            <Field label="Guest">
              <select className="select" name="guest_id" required>
                {guests.map((g) => (
                  <option value={g.id} key={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Room / unit">
              <select className="select" name="unit_id" required>
                {rooms
                  .filter(
                    (r) =>
                      !["maintenance", "out_of_service"].includes(r.status),
                  )
                  .map((r) => (
                    <option value={r.id} key={r.id}>
                      {r.name} · {readableLabel(r.status)}
                    </option>
                  ))}
              </select>
            </Field>
            <div className="inlineForm">
              <div>
                <Field label="Arrival date">
                  <input
                    className="field"
                    name="arrival_date"
                    type="date"
                    required
                  />
                </Field>
              </div>
              <div>
                <Field label="Arrival time">
                  <input
                    className="field"
                    name="expected_arrival_time"
                    type="time"
                  />
                </Field>
              </div>
            </div>
            <div className="inlineForm">
              <div>
                <Field label="Departure date">
                  <input
                    className="field"
                    name="departure_date"
                    type="date"
                    required
                  />
                </Field>
              </div>
              <div>
                <Field label="Departure time">
                  <input
                    className="field"
                    name="expected_departure_time"
                    type="time"
                  />
                </Field>
              </div>
            </div>
            <Field label="Party size">
              <input
                className="field"
                name="party_size"
                type="number"
                min="1"
                defaultValue="1"
              />
            </Field>
            <Field label="Transfer notes">
              <textarea className="textarea" name="transfer_notes" />
            </Field>
            <Field label="Special requirements">
              <textarea className="textarea" name="special_requirements" />
            </Field>
            <div className="drawerActions">
              <button className="button primary">Create stay</button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
