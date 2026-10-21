"use client";
import { readableLabel } from "@/lib/strings/content";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { lodgeApi } from "@/lib/api";
type Room = {
  id: string;
  name: string;
  unit_type: string;
  status: string;
  notes: string;
  current_guest?: string;
};
const statuses = [
  "available",
  "occupied",
  "cleaning",
  "awaiting_inspection",
  "ready",
  "maintenance",
  "out_of_service",
];
export default function RoomsPage() {
  const access = useWorkspaceAccess();
  const canManage = access.permission("units.manage");
  const [rows, setRows] = useState<Room[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    try {
      setRows(await lodgeApi.rooms());
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
      await lodgeApi.createRoom({
        name: String(f.get("name")),
        unit_type: String(f.get("unit_type")),
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
      await lodgeApi.updateRoom(id, { status });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">ACCOMMODATION</span>
          <h1>Rooms & Units</h1>
          <p>Authoritative room inventory and live operational status.</p>
        </div>
        {canManage && (
          <button className="button primary" onClick={() => setOpen(true)}>
            + Room / Unit
          </button>
        )}
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <div className="roomGrid">
        {rows.map((r) => (
          <article className="roomCard" key={r.id}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 8,
              }}
            >
              <b>{r.name}</b>
              <StatusPill value={r.status} />
            </div>
            <p>
              {r.unit_type}
              {r.current_guest ? ` · ${r.current_guest}` : ""}
            </p>
            <select
              className="select"
              value={r.status}
              onChange={(e) => update(r.id, e.target.value)}
              disabled={!canManage}
              aria-label="Status"
            >
              {statuses.map((s) => (
                <option value={s} key={s}>
                  {readableLabel(s)}
                </option>
              ))}
            </select>
          </article>
        ))}
      </div>
      {!rows.length && (
        <div className="panel empty">
          No rooms or units have been configured yet.
        </div>
      )}
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <div>
              <h1>Add room / unit</h1>
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
            <Field label="Name">
              <input className="field" name="name" required />
            </Field>
            <Field label="Type">
              <input
                className="field"
                name="unit_type"
                placeholder="Room, Suite, Villa, Tent…"
                required
              />
            </Field>
            <Field label="Notes">
              <textarea className="textarea" name="notes" />
            </Field>
            <div className="drawerActions">
              <button className="button primary">Create unit</button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
