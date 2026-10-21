"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { FormEvent, useEffect, useState } from "react";
import StatusPill from "./StatusPill";
import Drawer from "./Drawer";
import { authApi, getActiveLodgeId, lodgeApi, operationsApi } from "@/lib/api";
type Issue = {
  id: string;
  title: string;
  category: string;
  priority: string;
  status: string;
  unit_name?: string;
  vehicle_name?: string;
  assigned_staff_name?: string;
  cost_cents?: number;
  resolution?: string;
  asset_id?: string;
  scheduled_for?: string;
  recurrence_interval_days?: number;
};
type Room = { id: string; name: string };
type Staff = { id: string; full_name: string; employment_status: string };
type Vehicle = { id: string; registration: string; name?: string };
const next: Record<string, string | undefined> = {
  open: "in_progress",
  assigned: "in_progress",
  in_progress: "waiting",
  waiting: "in_progress",
};
export default function MaintenancePage() {
  const access = useWorkspaceAccess();
  const [createOpen, setCreateOpen] = useState(false);
  const [assetOpen, setAssetOpen] = useState(false);
  const [issues, setIssues] = useState<Issue[]>([]),
    [rooms, setRooms] = useState<Room[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
    [vehicles, setVehicles] = useState<Vehicle[]>([]),
    [assets, setAssets] = useState<any[]>([]),
    [tab, setTab] = useState("tickets"),
    [selected, setSelected] = useState<Issue | null>(null),
    [parts, setParts] = useState<any[]>([]),
    [error, setError] = useState(""),
    [canManage, setCanManage] = useState(false);
  const workshop = access.feature("maintenance_workshop"),
    canAssets = workshop && access.permission("maintenance.assets.manage");
  useEffect(() => {
    if (!canAssets && tab === "assets") setTab("tickets");
  }, [canAssets, tab]);
  const load = async () => {
    try {
      const me = await authApi.me();
      const m = me.memberships?.find(
        (x: any) => x.lodge_id === getActiveLodgeId(),
      );
      const manage = Boolean(
        me.is_super_admin || m?.permissions?.includes("maintenance.manage"),
      );
      const assetManage = Boolean(
        me.is_super_admin ||
        m?.permissions?.includes("maintenance.assets.manage"),
      );
      setCanManage(manage);
      const ws = access.feature("maintenance_workshop");

      const [i, r, s, v, a] = await Promise.all([
        lodgeApi.maintenance(),
        access.feature("units") && access.permission("units.view")
          ? lodgeApi.rooms()
          : Promise.resolve([]),
        manage && access.feature("staff") && access.permission("staff.view")
          ? operationsApi.staff.list<Staff[]>()
          : Promise.resolve([]),
        access.feature("fleet") && access.permission("vehicles.view")
          ? operationsApi.vehicles.list<Vehicle[]>()
          : Promise.resolve([]),
        assetManage && ws
          ? operationsApi.maintenanceAssets.list()
          : Promise.resolve([]),
      ]);
      setIssues(i);
      setRooms(r);
      setStaff(s);
      setVehicles(v);
      setAssets(a);
    } catch (e: any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    load();
  }, []);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await lodgeApi.createMaintenance({
        title: String(f.get("title")),
        description: String(f.get("description") || ""),
        category: String(f.get("category") || "general"),
        priority: String(f.get("priority")),
        unit_id: String(f.get("unit_id") || "") || null,
        asset_id: String(f.get("asset_id") || "") || null,
        vehicle_id: String(f.get("vehicle_id") || "") || null,
        assigned_staff_id: String(f.get("assigned_staff_id") || "") || null,
        scheduled_for: String(f.get("scheduled_for") || "")
          ? new Date(String(f.get("scheduled_for"))).toISOString()
          : null,
        recurrence_interval_days:
          Number(f.get("recurrence_interval_days") || 0) || null,
      });
      form.reset();
      setCreateOpen(false);
      setAssetOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function createAsset(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await operationsApi.maintenanceAssets.create({
        asset_code: String(f.get("asset_code")),
        name: String(f.get("name")),
        category: String(f.get("category") || "general"),
        unit_id: String(f.get("unit_id") || "") || null,
        vehicle_id: String(f.get("vehicle_id") || "") || null,
        service_interval_days:
          Number(f.get("service_interval_days") || 0) || null,
        next_service_date: String(f.get("next_service_date") || "") || null,
        notes: String(f.get("notes") || ""),
      });
      form.reset();
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function update(id: string, body: any) {
    try {
      await lodgeApi.updateMaintenance(id, body);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function complete(i: Issue) {
    const resolution = window.prompt("Repair / resolution notes");
    if (!resolution) return;
    await update(i.id, { status: "completed", resolution });
  }
  async function openIssue(i: Issue) {
    if (!workshop) return;
    setSelected(i);
    try {
      setParts(await operationsApi.maintenanceAssets.parts(i.id));
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function addPart(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected) return;
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await operationsApi.maintenanceAssets.addPart(selected.id, {
        part_name: String(f.get("part_name")),
        quantity: Number(f.get("quantity")),
        unit_cost_cents: Math.round(Number(f.get("unit_cost") || 0) * 100),
        notes: String(f.get("notes") || ""),
      });
      form.reset();
      await openIssue(selected);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">MAINTENANCE & WORKSHOP</span>
          <h1>Maintenance</h1>
          <p>
            Property, vehicle and asset maintenance with scheduling, downtime,
            parts and recurring service workflows.
          </p>
        </div>
        {(tab === "assets" ? canAssets : canManage) && (
          <button
            className="button primary"
            onClick={() =>
              tab === "assets" ? setAssetOpen(true) : setCreateOpen(true)
            }
          >
            {tab === "assets" ? "+ Add asset" : "+ Add ticket"}
          </button>
        )}
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <div className="tabs">
        <button
          className={tab === "tickets" ? "button primary" : "button"}
          onClick={() => setTab("tickets")}
        >
          Tickets
        </button>
        {canAssets && (
          <button
            className={tab === "assets" ? "button primary" : "button"}
            onClick={() => setTab("assets")}
          >
            Assets
          </button>
        )}
      </div>
      {tab === "tickets" && (
        <div className="moduleContent">
          {canManage && (
            <>
              {createOpen && (
                <Drawer onClose={() => setCreateOpen(false)}>
                  <div className="drawerHead">
                    <h2>Create maintenance ticket</h2>
                    <button
                      className="closeButton"
                      aria-label="Close dialog"
                      onClick={() => setCreateOpen(false)}
                    >
                      ×
                    </button>
                  </div>

                  <Form onSubmit={submit}>
                    <Field label="Title">
                      <input className="field" name="title" required />
                    </Field>
                    <Field label="Description">
                      <textarea className="textarea" name="description" />
                    </Field>
                    <Field label="Category">
                      <input className="field" name="category" />
                    </Field>
                    {workshop && (
                      <>
                        <Field label="Asset">
                          <select className="select" name="asset_id">
                            <option value="">No registered asset</option>
                            {assets.map((a) => (
                              <option key={a.id} value={a.id}>
                                {a.asset_code} · {a.name}
                              </option>
                            ))}
                          </select>
                        </Field>
                      </>
                    )}
                    <Field label="Room / unit">
                      <select className="select" name="unit_id">
                        <option value="">Not room-related</option>
                        {rooms.map((r) => (
                          <option value={r.id} key={r.id}>
                            {r.name}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Vehicle">
                      <select className="select" name="vehicle_id">
                        <option value="">Not vehicle-related</option>
                        {vehicles.map((v) => (
                          <option value={v.id} key={v.id}>
                            {v.name || v.registration}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label="Assign to">
                      <select className="select" name="assigned_staff_id">
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
                    <Field label="Priority">
                      <select className="select" name="priority">
                        <option>low</option>
                        <option selected value="normal">
                          normal
                        </option>
                        <option>high</option>
                        <option>critical</option>
                      </select>
                    </Field>
                    {workshop && (
                      <>
                        <Field label="Scheduled for">
                          <input
                            className="field"
                            type="datetime-local"
                            name="scheduled_for"
                          />
                        </Field>
                        <Field label="Repeat every N days">
                          <input
                            className="field"
                            type="number"
                            min="1"
                            name="recurrence_interval_days"
                          />
                        </Field>
                      </>
                    )}
                    <div className="drawerActions">
                      <button className="button primary">Create ticket</button>
                    </div>
                  </Form>
                </Drawer>
              )}
            </>
          )}
          <section className="panel">
            <h2>Maintenance queue</h2>
            {issues.map((i) => (
              <div className="taskRow" key={i.id}>
                <div className="taskMain">
                  <button
                    className="linkButton"
                    onClick={() => openIssue(i)}
                    disabled={!workshop}
                  >
                    <strong>{i.title}</strong>
                  </button>
                  <small>
                    {i.unit_name || i.vehicle_name || i.category} ·{" "}
                    {i.assigned_staff_name || "Unassigned"}
                    {i.scheduled_for
                      ? ` · ${new Date(i.scheduled_for).toLocaleString()}`
                      : ""}
                  </small>
                </div>
                <div className="taskMeta">
                  <StatusPill value={i.priority} />{" "}
                  <StatusPill value={i.status} />
                  <div style={{ marginTop: 6 }}>
                    {next[i.status] && (
                      <button
                        className="button secondary"
                        onClick={() => update(i.id, { status: next[i.status] })}
                      >
                        {next[i.status]!.replaceAll("_", " ")}
                      </button>
                    )}{" "}
                    {!["completed", "cancelled"].includes(i.status) && (
                      <button
                        className="button secondary"
                        onClick={() => complete(i)}
                      >
                        Complete
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {!issues.length && (
              <div className="empty">
                No maintenance tickets have been created.
              </div>
            )}
          </section>
        </div>
      )}
      {tab === "assets" && canAssets && (
        <div className="moduleContent">
          {assetOpen && (
            <Drawer onClose={() => setAssetOpen(false)}>
              <div className="drawerHead">
                <h2>Register asset</h2>
                <button
                  className="closeButton"
                  aria-label="Close dialog"
                  onClick={() => setAssetOpen(false)}
                >
                  ×
                </button>
              </div>

              <Form onSubmit={createAsset}>
                <Field label="Asset code">
                  <input className="field" name="asset_code" required />
                </Field>
                <Field label="Name">
                  <input className="field" name="name" required />
                </Field>
                <Field label="Category">
                  <input className="field" name="category" />
                </Field>
                <Field label="Unit">
                  <select className="select" name="unit_id">
                    <option value="">None</option>
                    {rooms.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.name}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Vehicle">
                  <select className="select" name="vehicle_id">
                    <option value="">None</option>
                    {vehicles.map((v) => (
                      <option key={v.id} value={v.id}>
                        {v.name || v.registration}
                      </option>
                    ))}
                  </select>
                </Field>
                <Field label="Service interval days">
                  <input
                    className="field"
                    type="number"
                    min="1"
                    name="service_interval_days"
                  />
                </Field>
                <Field label="Next service">
                  <input
                    className="field"
                    type="date"
                    name="next_service_date"
                  />
                </Field>
                <Field label="Notes">
                  <textarea className="textarea" name="notes" />
                </Field>
                <div className="drawerActions">
                  <button className="button primary">Register asset</button>
                </div>
              </Form>
            </Drawer>
          )}
          <section className="panel">
            <h2>Asset register</h2>
            {assets.map((a) => (
              <div className="taskRow" key={a.id}>
                <div>
                  <strong>
                    {a.asset_code} · {a.name}
                  </strong>
                  <small>
                    {a.category} · Next service {a.next_service_date || "—"}
                  </small>
                </div>
                <StatusPill value={a.status} />
              </div>
            ))}
            {!assets.length && (
              <div className="empty">No maintenance assets registered.</div>
            )}
          </section>
        </div>
      )}
      {selected && workshop && (
        <Drawer onClose={() => setSelected(null)}>
          <div className="drawerHead">
            <div>
              <h1>{selected.title}</h1>
              <div className="sub">
                Parts used are added to the ticket cost and retained in service
                history.
              </div>
            </div>
            <button
              className="closeButton"
              onClick={() => setSelected(null)}
              aria-label="Close dialog"
              type="button"
            >
              ×
            </button>
          </div>
          <h2>Parts used</h2>
          {parts.map((p) => (
            <div className="row" key={p.id}>
              <span>
                {p.part_name} × {p.quantity}
              </span>
              <strong>{(p.total_cost_cents / 100).toFixed(2)}</strong>
            </div>
          ))}
          <Form onSubmit={addPart}>
            <Field label="Part">
              <input className="field" name="part_name" required />
            </Field>
            <Field label="Quantity">
              <input
                className="field"
                type="number"
                min="1"
                name="quantity"
                defaultValue="1"
                required
              />
            </Field>
            <Field label="Unit cost">
              <input
                className="field"
                type="number"
                step="0.01"
                min="0"
                name="unit_cost"
              />
            </Field>
            <Field label="Notes">
              <textarea className="textarea" name="notes" />
            </Field>
            <button className="button primary">Add part</button>
          </Form>
        </Drawer>
      )}
    </>
  );
}
