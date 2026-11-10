"use client";
import { workflowColumns, nextStatuses } from "@/lib/status-transitions";
import { useInstantRows, useDataRefresh } from "@/lib/use-instant-actions";
import { instantCopy as instant } from "@/lib/strings/interactivity";
import { OperationsCalendar } from "./DataViz";
import { dateInputValue } from "@/lib/formatting";
import { CollectionView } from "@/components/ui/collection-view";
import { uiCopy as ui } from "@/lib/strings/redesign";
import { TableScroll } from "@/components/ui/table-scroll";

import { readableLabel } from "@/lib/strings/content";
import { formatDateTime } from "@/lib/formatting";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { FormEvent, useEffect, useState, useRef } from "react";
import TaskHistoryPanel from "./TaskHistoryPanel";
import { taskCopy as copy } from "@/lib/strings/tasks";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import {
  authApi,
  getActiveLodgeId,
  getActiveUserId,
  ApiError,
  lodgeApi,
  operationsApi,
} from "@/lib/api";
type Task = {
  id: string;
  title: string;
  description: string;
  department_name?: string;
  assigned_staff_name?: string;
  unit_name?: string;
  priority: string;
  status: string;
  due_at?: string;
  recurrence_interval_days?: number;
  assigned_staff_id?: string | null;
  department_id?: string | null;
  vehicle_id?: string | null;
  maintenance_ticket_id?: string | null;
  can_transition?: boolean;
};
type Staff = {
  user_id?: string;
  id: string;
  full_name: string;
  employment_status: string;
};
type Department = { id: string; name: string; is_active: boolean };
type Room = { id: string; name: string };
type Guest = { id: string; name: string };
const next: Record<string, string | undefined> = {
  created: "assigned",
  assigned: "accepted",
  accepted: "started",
  started: "completed",
};
export default function TasksPage() {
  const [calendarView, setCalendarView] = useState(false);
  const [taskFilter, setTaskFilter] = useState(() =>
    typeof window !== "undefined" &&
    new URLSearchParams(location.search).get("status") === "overdue"
      ? "overdue"
      : "all",
  );
  const access = useWorkspaceAccess();
  const attachmentsEnabled = access.feature("task_attachments");
  const { rows, setRows, pending, mutate } = useInstantRows<Task>(
    access.scopeKey,
  );
  const [staff, setStaff] = useState<Staff[]>([]),
    [deps, setDeps] = useState<Department[]>([]),
    [rooms, setRooms] = useState<Room[]>([]),
    [guests, setGuests] = useState<Guest[]>([]),
    [open, setOpen] = useState(false),
    [selected, setSelected] = useState<Task | null>(null),
    [checklist, setChecklist] = useState<any[]>([]),
    [comments, setComments] = useState<any[]>([]),
    [attachments, setAttachments] = useState<any[]>([]),
    [error, setError] = useState(""),
    [canManage, setCanManage] = useState(false),
    [canOwnManage, setCanOwnManage] = useState(false);
  const advanced = access.feature("advanced_tasks");
  const vehicleLinks =
    access.feature("fleet") && access.permission("vehicles.view");
  const maintenanceLinks =
    access.feature("maintenance") && access.permission("maintenance.view");
  const staffDirectory =
    access.feature("staff") && access.permission("staff.view");
  const departmentDirectory =
    access.feature("departments") && access.permission("departments.view");
  const [vehicles, setVehicles] = useState<any[]>([]),
    [tickets, setTickets] = useState<any[]>([]),
    [loading, setLoading] = useState(true),
    [formBusy, setBusy] = useState(false),
    [detailVersion, setDetailVersion] = useState(0);
  const busy = formBusy || Boolean(selected && pending.includes(selected.id));
  const mounted = useRef(false),
    generation = useRef(0),
    details = useRef(0),
    mutation = useRef(false),
    actor = useRef({ userId: getActiveUserId(), lodgeId: getActiveLodgeId() });
  const current = () =>
    mounted.current &&
    actor.current.userId === getActiveUserId() &&
    actor.current.lodgeId === getActiveLodgeId();
  function denied(message: string) {
    setSelected(null);
    setRows([]);
    setChecklist([]);
    setComments([]);
    setAttachments([]);
    setError(message);
  }
  function failure(e: any) {
    if (!current()) return;
    if (e instanceof ApiError && [401, 403, 404].includes(e.status))
      denied(e.message);
    else setError(e.message);
  }
  const mayProgress = (task: Task) =>
    canManage || (canOwnManage && task.can_transition === true);
  const load = async () => {
    const n = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const me = await authApi.me();
      if (!current() || n !== generation.current) return [];
      const m = me.memberships?.find(
        (x: any) => x.lodge_id === getActiveLodgeId(),
      );
      const manage = Boolean(
        me.is_super_admin || m?.permissions?.includes("tasks.manage"),
      );
      const ownManage = Boolean(
        me.is_super_admin || m?.permissions?.includes("tasks.own.manage"),
      );
      setCanManage(manage);
      setCanOwnManage(ownManage);

      const [t, s, d, r, g, v, mt] = await Promise.all([
        lodgeApi.tasks(),
        manage && staffDirectory
          ? operationsApi.staff.list().catch(() => [])
          : Promise.resolve([]),
        manage && departmentDirectory
          ? operationsApi.departments.list().catch(() => [])
          : Promise.resolve([]),
        manage && access.feature("units") && access.permission("units.view")
          ? lodgeApi.rooms().catch(() => [])
          : Promise.resolve([]),
        manage && access.feature("guests") && access.permission("guests.view")
          ? lodgeApi.guests().catch(() => [])
          : Promise.resolve([]),
        manage && vehicleLinks
          ? operationsApi.vehicles.list()
          : Promise.resolve([]),
        manage && maintenanceLinks
          ? lodgeApi.maintenance()
          : Promise.resolve([]),
      ]);
      if (!current() || n !== generation.current) return [];
      setVehicles(v);
      setTickets(mt);
      setRows(t);
      setStaff(s);
      setDeps(d);
      setRooms(r);
      setGuests(g);
      return t as Task[];
    } catch (e: any) {
      if (n === generation.current) failure(e);
      return [];
    } finally {
      if (current() && n === generation.current) setLoading(false);
    }
  };
  useEffect(() => {
    mounted.current = true;
    void load();
    const clear = (event: Event) => {
      if (
        event instanceof StorageEvent &&
        event.key &&
        !["active_user_id", "active_lodge_id"].includes(event.key)
      )
        return;
      generation.current++;
      details.current++;
      setSelected(null);
      setOpen(false);
      setRows([]);
      setStaff([]);
      setDeps([]);
      setRooms([]);
      setGuests([]);
      setVehicles([]);
      setTickets([]);
      setChecklist([]);
      setComments([]);
      setAttachments([]);
      setError("");
    };
    window.addEventListener("storage", clear);
    window.addEventListener("safarios-lodge-changed", clear);
    return () => {
      mounted.current = false;
      generation.current++;
      details.current++;
      window.removeEventListener("storage", clear);
      window.removeEventListener("safarios-lodge-changed", clear);
    };
  }, []);
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!current() || mutation.current) return;
    mutation.current = true;
    setBusy(true);
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await lodgeApi.createTask(
        {
          title: String(f.get("title")),
          description: String(f.get("description") || ""),
          department_id: String(f.get("department_id") || "") || null,
          assigned_staff_id: String(f.get("assigned_staff_id") || "") || null,
          guest_id: String(f.get("guest_id") || "") || null,
          unit_id: String(f.get("unit_id") || "") || null,
          ...(vehicleLinks
            ? { vehicle_id: String(f.get("vehicle_id") || "") || null }
            : {}),
          ...(maintenanceLinks
            ? {
                maintenance_ticket_id:
                  String(f.get("maintenance_ticket_id") || "") || null,
              }
            : {}),
          priority: String(f.get("priority")),
          due_at: String(f.get("due_at") || "")
            ? new Date(String(f.get("due_at"))).toISOString()
            : null,
          recurrence_interval_days:
            Number(f.get("recurrence_interval_days") || 0) || null,
          recurrence_end_date:
            String(f.get("recurrence_end_date") || "") || null,
        },
        actor.current,
      );
      if (!current()) return;
      setOpen(false);
      await load();
    } catch (e: any) {
      failure(e);
    } finally {
      mutation.current = false;
      if (current()) setBusy(false);
    }
  }
  useDataRefresh(load, pending.length > 0 || busy);
  async function update(id: string, body: any) {
    if (!current() || mutation.current) return false;
    const success = await mutate(
      id,
      body,
      (patch) =>
        lodgeApi.updateTask(id, patch, { ...actor.current, silent: true }),
      {
        message: instant.task,
        onError: failure,
      },
    );
    if (success && current()) {
      const fresh = await load();
      const row = fresh?.find((task: Task) => task.id === id);
      if (current() && selected?.id === id && row) await openTask(row);
    }
    return success;
  }
  async function saveDetails(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || pending.includes(selected.id)) return;
    const f = new FormData(event.currentTarget),
      body: any = {};
    if (f.get("assigned_staff_id"))
      body.assigned_staff_id = String(f.get("assigned_staff_id"));
    if (f.get("department_id"))
      body.department_id = String(f.get("department_id"));
    if (vehicleLinks)
      body.vehicle_id = String(f.get("vehicle_id") || "") || null;
    if (maintenanceLinks)
      body.maintenance_ticket_id =
        String(f.get("maintenance_ticket_id") || "") || null;
    await update(selected.id, body);
  }
  async function openTask(t: Task) {
    if (!current()) return;
    const n = ++details.current;
    setDetailVersion(n);
    setChecklist([]);
    setComments([]);
    setAttachments([]);
    setSelected(t);
    try {
      const [c, m, a] = await Promise.all([
        operationsApi.taskWorkflow.checklist(t.id),
        operationsApi.taskWorkflow.comments(t.id),
        attachmentsEnabled
          ? operationsApi.taskAttachments.list(t.id)
          : Promise.resolve([]),
      ]);
      if (!current() || details.current !== n) return;
      setChecklist(c);
      setComments(m);
      setAttachments(a);
    } catch (e: any) {
      if (details.current === n) failure(e);
    }
  }
  async function addChecklist(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected || !current()) return;
    const stamp = details.current;
    const form = e.currentTarget;
    const f = new FormData(form);
    await operationsApi.taskWorkflow.addChecklist(selected.id, {
      label: String(f.get("label")),
      position: checklist.length,
      is_required: true,
    });
    if (current() && stamp === details.current) {
      form.reset();
      await openTask(selected);
    }
  }
  async function addComment(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected || !current()) return;
    const stamp = details.current;
    const form = e.currentTarget;
    const f = new FormData(form);
    await operationsApi.taskWorkflow.addComment(
      selected.id,
      String(f.get("body")),
    );
    if (current() && stamp === details.current) {
      form.reset();
      await openTask(selected);
    }
  }
  async function uploadAttachment(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected || !current()) return;
    const stamp = details.current;
    const input = e.currentTarget.elements.namedItem(
      "file",
    ) as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    try {
      const buf = await file.arrayBuffer();
      const digest = await crypto.subtle.digest("SHA-256", buf);
      const sha256 = Array.from(new Uint8Array(digest))
        .map((b) => b.toString(16).padStart(2, "0"))
        .join("");
      if (!current() || stamp !== details.current) return;
      const prep = await operationsApi.taskAttachments.uploadUrl(selected.id, {
        file_name: file.name,
        content_type: file.type,
        size_bytes: file.size,
        sha256,
      });
      if (!current() || stamp !== details.current) return;
      const up = await fetch(prep.upload_url, {
        method: "PUT",
        headers: prep.required_headers,
        body: file,
      });
      if (!up.ok) throw new Error(`Upload failed (${up.status})`);
      if (!current() || stamp !== details.current) return;
      await operationsApi.taskAttachments.register(selected.id, {
        object_key: prep.object_key,
        file_name: file.name,
        content_type: file.type,
        size_bytes: file.size,
        sha256,
      });
      if (!current() || stamp !== details.current) return;
      input.value = "";
      await openTask(selected);
    } catch (e: any) {
      failure(e);
    }
  }
  async function downloadAttachment(id: string) {
    if (!selected || !current()) return;
    const stamp = details.current;
    try {
      const r = await operationsApi.taskAttachments.download(selected.id, id);
      if (!current() || stamp !== details.current) return;
      window.open(r.url, "_blank", "noopener,noreferrer");
    } catch (e: any) {
      failure(e);
    }
  }

  useEffect(() => {
    if (canManage && new URLSearchParams(location.search).get("create") === "1")
      setOpen(true);
  }, [canManage]);
  const visibleTasks = rows.filter((r) =>
    taskFilter === "overdue"
      ? !!r.due_at &&
        new Date(r.due_at) < new Date() &&
        !["completed", "cancelled"].includes(r.status)
      : taskFilter === "mine"
        ? staff.some(
            (s) =>
              s.user_id === getActiveUserId() && s.id === r.assigned_staff_id,
          ) ||
          (!canManage && Boolean(r.can_transition))
        : true,
  );
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">OPERATIONS</span>
          <h1>Tasks</h1>
          <p>
            Tasks support lifecycle timestamps, recurring work, required
            checklists and comments.
          </p>
        </div>
        {canManage && (
          <button className="button primary" onClick={() => setOpen(true)}>
            + Task
          </button>
        )}
      </div>
      {error && !open && !selected && (
        <div className="panel dangerText" role="alert">
          {error}{" "}
          <button className="linkButton" onClick={() => void load()}>
            {copy.retry}
          </button>
        </div>
      )}
      {loading && <p role="status">{copy.loadingTasks}</p>}
      <div className="filterBar">
        <div className="viewSwitcher">
          {[
            ["all", ui.taskTabs[0]],
            ["mine", ui.taskTabs[1]],
            ["overdue", ui.taskTabs[2]],
          ].map(([key, label]) => (
            <button
              type="button"
              key={key}
              aria-pressed={taskFilter === key}
              onClick={() => setTaskFilter(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      <div className="filterBar">
        <button
          type="button"
          className="button secondary"
          aria-pressed={calendarView}
          onClick={() => setCalendarView((value) => !value)}
        >
          {ui.calendar}
        </button>
      </div>
      {calendarView ? (
        <section className="panel">
          <OperationsCalendar
            events={visibleTasks
              .filter((task) => task.due_at)
              .map((task) => ({
                date: dateInputValue(new Date(task.due_at!)),
                label: task.title,
                kind: "other" as const,
                onSelect: () => {
                  void openTask(task);
                },
              }))}
          />
        </section>
      ) : (
        <CollectionView
          loading={loading}
          error={Boolean(error)}
          onRetry={() => {
            setError("");
            void load();
          }}
          statusBoard={{
            columns: workflowColumns("tasks"),
            pending: (id) => pending.includes(id),
            allowed: (id) => {
              const row = rows.find((r) => r.id === id);
              return !access.readOnly && row && mayProgress(row)
                ? nextStatuses("tasks", row.status).filter(
                    (s) =>
                      (canManage ||
                        ["accepted", "started", "completed"].includes(s)) &&
                      (s !== "assigned" || !!row.assigned_staff_id),
                  )
                : [];
            },
            onMove: (id, status) => update(id, { status }),
          }}
          name="TasksPage"
          defaultView={
            [
              "general_staff",
              "ranger",
              "driver",
              "housekeeping",
              "maintenance",
              "fb",
            ].includes(access.roleKey || "")
              ? "cards"
              : "list"
          }
        >
          <TableScroll as="section" className="panel tableWrap">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Department</th>
                  <th>Assignee</th>
                  <th>Priority</th>
                  <th>Due</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {visibleTasks.map((r) => (
                  <tr key={r.id} data-record-id={r.id}>
                    <td>
                      <button
                        className="linkButton"
                        onClick={() => openTask(r)}
                      >
                        <strong>{r.title}</strong>
                      </button>
                      <br />
                      <small>
                        {r.recurrence_interval_days
                          ? `Repeats every ${r.recurrence_interval_days} days`
                          : r.description || "—"}
                      </small>
                    </td>
                    <td>{r.department_name || "—"}</td>
                    <td>{r.assigned_staff_name || "Unassigned"}</td>
                    <td>
                      <StatusPill value={r.priority} />
                    </td>
                    <td>{r.due_at ? formatDateTime(r.due_at) : "—"}</td>
                    <td>
                      <StatusPill value={r.status} />
                      {pending.includes(r.id) && (
                        <small role="status">{instant.saving}</small>
                      )}
                    </td>
                    <td>
                      {(next[r.status] || pending.includes(r.id)) &&
                        mayProgress(r) && (
                          <button
                            className="button secondary"
                            disabled={busy || pending.includes(r.id)}
                            aria-busy={pending.includes(r.id)}
                            onClick={() =>
                              r.status === "created"
                                ? openTask(r)
                                : update(r.id, { status: next[r.status] })
                            }
                          >
                            {next[r.status]
                              ? readableLabel(next[r.status]!)
                              : instant.saving}
                          </button>
                        )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!loading && !error && !rows.length && (
              <div className="empty">No tasks have been created.</div>
            )}
          </TableScroll>
        </CollectionView>
      )}
      {open && canManage && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <div>
              <h1>New task</h1>
              <div className="sub">
                Create real operational work and optionally make it recurring.
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
          {error && (
            <p className="dangerText" role="alert">
              {error}
            </p>
          )}
          <Form onSubmit={create}>
            <Field label="Title">
              <input className="field" name="title" required />
            </Field>
            <Field label="Description">
              <textarea className="textarea" name="description" />
            </Field>
            {departmentDirectory && (
              <Field label="Department">
                <select className="select" name="department_id">
                  <option value="">No department</option>
                  {deps.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {staffDirectory && (
              <Field label="Assign staff">
                <select className="select" name="assigned_staff_id">
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
            )}
            {access.feature("guests") && access.permission("guests.view") && (
              <Field label="Guest">
                <select className="select" name="guest_id">
                  <option value="">None</option>
                  {guests.map((g) => (
                    <option key={g.id} value={g.id}>
                      {g.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {access.feature("units") && access.permission("units.view") && (
              <Field label="Room / unit">
                <select className="select" name="unit_id">
                  <option value="">None</option>
                  {rooms.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {vehicleLinks && (
              <Field label={copy.vehicle}>
                <select className="select" name="vehicle_id">
                  <option value="">{copy.none}</option>
                  {vehicles.map((v) => (
                    <option key={v.id} value={v.id}>
                      {v.name || v.registration}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            {maintenanceLinks && (
              <Field label={copy.maintenance}>
                <select className="select" name="maintenance_ticket_id">
                  <option value="">{copy.none}</option>
                  {tickets.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.title}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <Field label="Priority">
              <select className="select" name="priority" defaultValue="normal">
                <option value="low">{readableLabel("low")}</option>
                <option value="normal">{readableLabel("normal")}</option>
                <option value="high">{readableLabel("high")}</option>
                <option value="critical">{readableLabel("critical")}</option>
              </select>
            </Field>
            <Field label="Due">
              <input className="field" type="datetime-local" name="due_at" />
            </Field>
            {advanced && (
              <>
                <Field label="Repeat every N days">
                  <input
                    className="field"
                    type="number"
                    min="1"
                    name="recurrence_interval_days"
                  />
                </Field>
                <Field label="Stop recurrence after">
                  <input
                    className="field"
                    type="date"
                    name="recurrence_end_date"
                  />
                </Field>
              </>
            )}
            <div className="drawerActions">
              <button className="button primary" disabled={busy}>
                {busy ? copy.saving : "Create task"}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
      {selected && (
        <Drawer onClose={() => setSelected(null)}>
          <div className="drawerHead">
            <div>
              <h1>{selected.title}</h1>
              <div className="sub">{selected.description}</div>
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
          {error && (
            <p className="dangerText" role="alert">
              {error}
            </p>
          )}
          <TaskHistoryPanel
            key={selected.id + ":" + detailVersion}
            taskId={selected.id}
            onDenied={denied}
          />
          {canManage &&
            (staffDirectory ||
              departmentDirectory ||
              vehicleLinks ||
              maintenanceLinks) && (
              <section className="taskManagement">
                <h2>{copy.manage}</h2>
                <Form
                  key={selected.id + ":" + detailVersion}
                  onSubmit={saveDetails}
                >
                  {staffDirectory && (
                    <Field label={copy.assignment}>
                      <select
                        className="select"
                        name="assigned_staff_id"
                        defaultValue={selected.assigned_staff_id || ""}
                      >
                        <option value="">{copy.noChange}</option>
                        {staff
                          .filter((s) => s.employment_status === "active")
                          .map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.full_name}
                            </option>
                          ))}
                      </select>
                    </Field>
                  )}
                  {departmentDirectory && (
                    <Field label={copy.department}>
                      <select
                        className="select"
                        name="department_id"
                        defaultValue={selected.department_id || ""}
                      >
                        <option value="">{copy.noChange}</option>
                        {deps
                          .filter((d) => d.is_active)
                          .map((d) => (
                            <option key={d.id} value={d.id}>
                              {d.name}
                            </option>
                          ))}
                      </select>
                    </Field>
                  )}
                  {vehicleLinks && (
                    <Field label={copy.vehicle}>
                      <select
                        className="select"
                        name="vehicle_id"
                        defaultValue={selected.vehicle_id || ""}
                      >
                        <option value="">{copy.none}</option>
                        {vehicles.map((v) => (
                          <option key={v.id} value={v.id}>
                            {v.name || v.registration}
                          </option>
                        ))}
                      </select>
                    </Field>
                  )}
                  {maintenanceLinks && (
                    <Field label={copy.maintenance}>
                      <select
                        className="select"
                        name="maintenance_ticket_id"
                        defaultValue={selected.maintenance_ticket_id || ""}
                      >
                        <option value="">{copy.none}</option>
                        {tickets.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.title}
                          </option>
                        ))}
                      </select>
                    </Field>
                  )}
                  <div className="drawerActions">
                    <button className="button primary" disabled={busy}>
                      {busy ? copy.saving : copy.save}
                    </button>
                  </div>
                </Form>
              </section>
            )}
          <h2>Checklist</h2>
          {checklist.map((i) => (
            <label className="checkRow" key={i.id}>
              <span>
                {i.label}
                {i.is_required && " *"}
              </span>
              <input
                type="checkbox"
                checked={i.completed}
                disabled={!mayProgress(selected)}
                onChange={async (e) => {
                  const stamp = details.current;
                  if (!current()) return;
                  try {
                    await operationsApi.taskWorkflow.updateChecklist(
                      selected.id,
                      i.id,
                      e.target.checked,
                    );
                    if (current() && stamp === details.current)
                      await openTask(selected);
                  } catch (e) {
                    failure(e);
                  }
                }}
              />
            </label>
          ))}
          {advanced && canManage && (
            <Form onSubmit={addChecklist} style={{ marginTop: 12 }}>
              <Field label="Add required checklist item">
                <input
                  className="field"
                  name="label"
                  placeholder="Add required checklist item"
                  required
                />
              </Field>
              <button className="button secondary">Add item</button>
            </Form>
          )}
          <h2 style={{ marginTop: 24 }}>Comments</h2>
          {comments.map((c) => (
            <div className="row" key={c.id}>
              <div>
                <strong>{c.author}</strong>
                <p>{c.body}</p>
                <small>{formatDateTime(c.created_at)}</small>
              </div>
            </div>
          ))}
          {advanced && mayProgress(selected) && (
            <Form onSubmit={addComment}>
              <Field label="Add operational note or comment">
                <textarea
                  className="textarea"
                  name="body"
                  placeholder="Add operational note or comment"
                  required
                />
              </Field>
              <button className="button primary">Add comment</button>
            </Form>
          )}
          {attachmentsEnabled && <h2 style={{ marginTop: 24 }}>Attachments</h2>}
          {attachmentsEnabled &&
            attachments.map((a) => (
              <div className="row" key={a.id}>
                <div>
                  <strong>{a.file_name}</strong>
                  <br />
                  <small>{Math.round(a.size_bytes / 1024)} KB</small>
                </div>
                <button
                  className="button secondary"
                  onClick={() => downloadAttachment(a.id)}
                >
                  Open
                </button>
              </div>
            ))}
          {attachmentsEnabled && mayProgress(selected) && (
            <Form onSubmit={uploadAttachment}>
              <Field label="Attachment">
                <input
                  className="field"
                  type="file"
                  name="file"
                  accept="image/jpeg,image/png,image/webp,image/heic,image/heif,application/pdf"
                  required
                />
              </Field>
              <button className="button secondary">Upload attachment</button>
            </Form>
          )}
        </Drawer>
      )}
    </>
  );
}
