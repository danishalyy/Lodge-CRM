"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { authApi, getActiveLodgeId, lodgeApi, operationsApi } from "@/lib/api";
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
};
type Staff = { id: string; full_name: string; employment_status: string };
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
  const access = useWorkspaceAccess();
  const attachmentsEnabled = access.feature("task_attachments");
  const [rows, setRows] = useState<Task[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
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
  const load = async () => {
    try {
      const me = await authApi.me();
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

      const [t, s, d, r, g] = await Promise.all([
        lodgeApi.tasks(),
        manage && access.feature("staff")
          ? operationsApi.staff.list().catch(() => [])
          : Promise.resolve([]),
        manage && access.feature("departments")
          ? operationsApi.departments.list().catch(() => [])
          : Promise.resolve([]),
        manage && access.feature("units")
          ? lodgeApi.rooms().catch(() => [])
          : Promise.resolve([]),
        manage && access.feature("guests")
          ? lodgeApi.guests().catch(() => [])
          : Promise.resolve([]),
      ]);
      setRows(t);
      setStaff(s);
      setDeps(d);
      setRooms(r);
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
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await lodgeApi.createTask({
        title: String(f.get("title")),
        description: String(f.get("description") || ""),
        department_id: String(f.get("department_id") || "") || null,
        assigned_staff_id: String(f.get("assigned_staff_id") || "") || null,
        guest_id: String(f.get("guest_id") || "") || null,
        unit_id: String(f.get("unit_id") || "") || null,
        priority: String(f.get("priority")),
        due_at: String(f.get("due_at") || "")
          ? new Date(String(f.get("due_at"))).toISOString()
          : null,
        recurrence_interval_days:
          Number(f.get("recurrence_interval_days") || 0) || null,
        recurrence_end_date: String(f.get("recurrence_end_date") || "") || null,
      });
      setOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function update(id: string, body: any) {
    try {
      await lodgeApi.updateTask(id, body);
      await load();
      if (selected?.id === id) await openTask({ ...selected, ...body });
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function openTask(t: Task) {
    setSelected(t);
    try {
      const [c, m, a] = await Promise.all([
        operationsApi.taskWorkflow.checklist(t.id),
        operationsApi.taskWorkflow.comments(t.id),
        attachmentsEnabled
          ? operationsApi.taskAttachments.list(t.id)
          : Promise.resolve([]),
      ]);
      setChecklist(c);
      setComments(m);
      setAttachments(a);
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function addChecklist(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected) return;
    const form = e.currentTarget;
    const f = new FormData(form);
    await operationsApi.taskWorkflow.addChecklist(selected.id, {
      label: String(f.get("label")),
      position: checklist.length,
      is_required: true,
    });
    form.reset();
    openTask(selected);
  }
  async function addComment(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected) return;
    const form = e.currentTarget;
    const f = new FormData(form);
    await operationsApi.taskWorkflow.addComment(
      selected.id,
      String(f.get("body")),
    );
    form.reset();
    openTask(selected);
  }
  async function uploadAttachment(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!selected) return;
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
      const prep = await operationsApi.taskAttachments.uploadUrl(selected.id, {
        file_name: file.name,
        content_type: file.type,
        size_bytes: file.size,
        sha256,
      });
      const up = await fetch(prep.upload_url, {
        method: "PUT",
        headers: prep.required_headers,
        body: file,
      });
      if (!up.ok) throw new Error(`Upload failed (${up.status})`);
      await operationsApi.taskAttachments.register(selected.id, {
        object_key: prep.object_key,
        file_name: file.name,
        content_type: file.type,
        size_bytes: file.size,
        sha256,
      });
      input.value = "";
      await openTask(selected);
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function downloadAttachment(id: string) {
    if (!selected) return;
    try {
      const r = await operationsApi.taskAttachments.download(selected.id, id);
      window.open(r.url, "_blank", "noopener,noreferrer");
    } catch (e: any) {
      setError(e.message);
    }
  }

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
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel tableWrap">
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
            {rows.map((r) => (
              <tr key={r.id}>
                <td>
                  <button className="linkButton" onClick={() => openTask(r)}>
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
                <td>{r.due_at ? new Date(r.due_at).toLocaleString() : "—"}</td>
                <td>
                  <StatusPill value={r.status} />
                </td>
                <td>
                  {next[r.status] && (canManage || canOwnManage) && (
                    <button
                      className="button secondary"
                      onClick={() => update(r.id, { status: next[r.status] })}
                    >
                      {next[r.status]!.replaceAll("_", " ")}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && (
          <div className="empty">No tasks have been created.</div>
        )}
      </section>
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
          <Form onSubmit={create}>
            <Field label="Title">
              <input className="field" name="title" required />
            </Field>
            <Field label="Description">
              <textarea className="textarea" name="description" />
            </Field>
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
            <button className="button primary">Create task</button>
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
                disabled={!(canManage || canOwnManage)}
                onChange={async (e) => {
                  await operationsApi.taskWorkflow.updateChecklist(
                    selected.id,
                    i.id,
                    e.target.checked,
                  );
                  openTask(selected);
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
                <small>{new Date(c.created_at).toLocaleString()}</small>
              </div>
            </div>
          ))}
          {advanced && (canManage || canOwnManage) && (
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
          {attachmentsEnabled && (canManage || canOwnManage) && (
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
