"use client";
import { useInstantRows, useDataRefresh } from "@/lib/use-instant-actions";
import { instantCopy as instant } from "@/lib/strings/interactivity";
import { Skeleton } from "./ui/skeleton";
import { readableLabel } from "@/lib/strings/content";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import {
  getActiveUserId,
  getActiveLodgeId,
  ApiError,
  lodgeApi,
} from "@/lib/api";
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
  const { rows, setRows, pending, mutate } = useInstantRows<Room>(
    access.scopeKey,
  );
  const [selected, setSelected] = useState<Room | null>(null),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const load = async () => {
    try {
      setRows(await lodgeApi.rooms());
      setError("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
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
  useDataRefresh(load, pending.length > 0 || open);
  async function update(id: string, status: string) {
    const scope = {
      userId: getActiveUserId(),
      lodgeId: getActiveLodgeId(),
      silent: true,
    };
    await mutate(
      id,
      { status },
      (patch) => lodgeApi.updateRoom(id, patch, scope),
      {
        message: instant.room,
        refresh: load,
        onError: (e) => {
          setError((e as Error).message);
          if (
            e instanceof ApiError &&
            [401, 403, 404, 409].includes(e.status)
          ) {
            setRows([]);
            setSelected(null);
          }
        },
      },
    );
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
      {error && (
        <div className="panel dangerText" role="alert">
          {error}
        </div>
      )}
      {loading && !rows.length && (
        <div role="status" aria-label={instant.loading}>
          <Skeleton className="h-20 mb-4" />
        </div>
      )}
      <div className="roomStatusBoard">
        {[
          "available",
          "occupied",
          "cleaning",
          "awaiting_inspection",
          "maintenance",
          "out_of_service",
        ].map((state) => {
          const units = rows.filter((r) =>
            state === "available"
              ? ["available", "ready"].includes(r.status)
              : r.status === state,
          );
          return (
            <section className="roomStatusColumn" key={state}>
              <h2>
                {readableLabel(state)}
                <span>{units.length}</span>
              </h2>
              {units.map((r) => (
                <article className="roomCard" key={r.id}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 8,
                    }}
                  >
                    <button
                      className="linkButton"
                      onClick={() => setSelected(r)}
                    >
                      <b>{r.name}</b>
                    </button>
                    <StatusPill value={r.status} />
                    {pending.includes(r.id) && (
                      <small role="status">{instant.saving}</small>
                    )}
                  </div>
                  <p>
                    {r.unit_type}
                    {r.current_guest ? ` · ${r.current_guest}` : ""}
                  </p>
                  <select
                    className="select"
                    value={r.status}
                    onChange={(e) => update(r.id, e.target.value)}
                    disabled={!canManage || pending.includes(r.id)}
                    aria-busy={pending.includes(r.id)}
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
            </section>
          );
        })}
      </div>
      {selected && (
        <Drawer onClose={() => setSelected(null)}>
          <div className="drawerHead">
            <h2>{selected.name}</h2>
            <button
              className="closeButton"
              aria-label="Close dialog"
              onClick={() => setSelected(null)}
            >
              ×
            </button>
          </div>
          <StatusPill value={selected.status} />
          <p>{selected.unit_type}</p>
          {selected.current_guest && <p>{selected.current_guest}</p>}
          <p>{selected.notes}</p>
        </Drawer>
      )}
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
