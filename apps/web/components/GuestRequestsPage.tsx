"use client";
import { useInstantRows, useDataRefresh } from "@/lib/use-instant-actions";
import { instantCopy as instant } from "@/lib/strings/interactivity";
import { CollectionView } from "@/components/ui/collection-view";
import { TableScroll } from "@/components/ui/table-scroll";

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
  operationsApi,
} from "@/lib/api";
type Req = {
  id: string;
  guest_name: string;
  request_type: string;
  description: string;
  department_name?: string;
  assigned_staff_name?: string;
  assigned_staff_id?: string | null;
  task_id?: string;
  priority: string;
  status: string;
  resolution: string;
};
type Guest = { id: string; name: string };
type Department = { id: string; name: string; is_active: boolean };
type Staff = { id: string; full_name: string; employment_status: string };
const next: Record<string, string | undefined> = {
  open: "in_progress",
  assigned: "in_progress",
  in_progress: "waiting",
  waiting: "in_progress",
};
export default function GuestRequestsPage() {
  const [collectionLoading, setCollectionLoading] = useState(true);
  const access = useWorkspaceAccess();
  const canManage = access.permission("requests.manage");
  const { rows, setRows, pending, mutate } = useInstantRows<Req>(
    access.scopeKey,
  );
  const [guests, setGuests] = useState<Guest[]>([]),
    [deps, setDeps] = useState<Department[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    setCollectionLoading(true);
    try {
      const [r, g, d, s] = await Promise.all([
        operationsApi.requests.list<Req[]>(),
        canManage &&
        access.feature("guests") &&
        access.permission("guests.view")
          ? lodgeApi.guests()
          : Promise.resolve([]),
        canManage &&
        access.feature("departments") &&
        access.permission("departments.view")
          ? operationsApi.departments.list<Department[]>()
          : Promise.resolve([]),
        canManage && access.feature("staff") && access.permission("staff.view")
          ? operationsApi.staff.list<Staff[]>()
          : Promise.resolve([]),
      ]);
      setRows(r);
      setGuests(g);
      setDeps(d);
      setStaff(s);
      setError("");
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCollectionLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    try {
      await operationsApi.requests.create({
        guest_id: String(f.get("guest_id")),
        request_type: String(f.get("request_type")),
        description: String(f.get("description")),
        department_id: String(f.get("department_id") || "") || null,
        assigned_staff_id: String(f.get("assigned_staff_id") || "") || null,
        priority: String(f.get("priority")),
      });
      setOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  useDataRefresh(load, pending.length > 0 || open);
  async function update(id: string, body: any) {
    const before = rows.find((row) => row.id === id);
    const scope = {
      userId: getActiveUserId(),
      lodgeId: getActiveLodgeId(),
      silent: true,
    };
    const patch = {
      ...body,
      ...(body.assigned_staff_id !== undefined
        ? {
            assigned_staff_name:
              staff.find((s) => s.id === body.assigned_staff_id)?.full_name ||
              "",
          }
        : {}),
    };
    await mutate(
      id,
      patch,
      (value) => {
        const { assigned_staff_name, ...payload } = value as any;
        return operationsApi.requests.update(id, payload, scope);
      },
      {
        message: instant.request,
        undo:
          body.assigned_staff_id && before?.assigned_staff_id
            ? {
                assigned_staff_id: before.assigned_staff_id,
                assigned_staff_name: before.assigned_staff_name,
              }
            : before &&
                ["waiting", "in_progress"].includes(before.status) &&
                ["waiting", "in_progress"].includes(body.status)
              ? { status: before.status }
              : undefined,
        refresh: load,
        onError: (e) => {
          setError((e as Error).message);
          if (e instanceof ApiError && [401, 403, 404, 409].includes(e.status))
            setRows([]);
        },
      },
    );
  }
  async function createTask(id: string) {
    try {
      await operationsApi.requests.createTask(id);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function resolve(r: Req) {
    const resolution = prompt("Resolution notes");
    if (!resolution) return;
    await update(r.id, { status: "resolved", resolution });
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">GUEST SERVICE</span>
          <h1>Guest Requests</h1>
          <p>
            Turn every guest request into a clear assignment, and follow it
            through to completion.
          </p>
        </div>
        {canManage && (
          <button
            className="button primary"
            onClick={() => setOpen(true)}
            disabled={!guests.length}
          >
            + Request
          </button>
        )}
      </div>
      {canManage && !guests.length && (
        <div className="panel">
          Create a guest before recording a guest request.
        </div>
      )}
      {error && (
        <div className="panel dangerText" role="alert">
          {error}
        </div>
      )}
      <CollectionView
        loading={collectionLoading}
        error={Boolean(error)}
        onRetry={() => {
          setError("");
          void load();
        }}
        name="GuestRequestsPage"
        defaultView="board"
      >
        <TableScroll as="section" className="panel tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>Guest</th>
                <th>Request</th>
                <th>Team</th>
                <th>Priority</th>
                <th>Status</th>
                <th>Task</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>{r.guest_name}</td>
                  <td>
                    <strong>{readableLabel(r.request_type)}</strong>
                    <br />
                    <small>{r.description}</small>
                  </td>
                  <td>
                    {r.department_name || "—"}
                    <br />
                    <small>{r.assigned_staff_name || "Unassigned"}</small>
                    {canManage && staff.length > 0 && (
                      <select
                        className="field"
                        aria-label={instant.assignRequest(r.description)}
                        disabled={pending.includes(r.id)}
                        value={r.assigned_staff_id || ""}
                        onChange={(e) =>
                          update(r.id, { assigned_staff_id: e.target.value })
                        }
                      >
                        <option value="" disabled>
                          {instant.unassigned}
                        </option>
                        {staff
                          .filter((s) => s.employment_status === "active")
                          .map((s) => (
                            <option key={s.id} value={s.id}>
                              {s.full_name}
                            </option>
                          ))}
                      </select>
                    )}
                  </td>
                  <td>
                    <StatusPill value={r.priority} />
                  </td>
                  <td>
                    <StatusPill value={r.status} />
                    {pending.includes(r.id) && (
                      <small role="status">{instant.saving}</small>
                    )}
                  </td>
                  <td>
                    {r.task_id ? (
                      "Created"
                    ) : canManage && access.feature("tasks") ? (
                      <button
                        className="button secondary"
                        onClick={() => createTask(r.id)}
                      >
                        Create task
                      </button>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {canManage &&
                      (!["resolved", "cancelled"].includes(r.status) ||
                        pending.includes(r.id)) && (
                        <>
                          <button
                            className="button secondary"
                            disabled={pending.includes(r.id)}
                            aria-busy={pending.includes(r.id)}
                            onClick={() =>
                              next[r.status] &&
                              update(r.id, { status: next[r.status] })
                            }
                          >
                            {next[r.status]?.replaceAll("_", " ") || "Update"}
                          </button>{" "}
                          <button
                            className="button secondary"
                            disabled={pending.includes(r.id)}
                            onClick={() => resolve(r)}
                          >
                            Resolve
                          </button>
                        </>
                      )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && (
            <div className="empty">No guest requests have been recorded.</div>
          )}
        </TableScroll>
      </CollectionView>
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <div>
              <h1>New guest request</h1>
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
            <Field label="Request type">
              <input
                className="field"
                name="request_type"
                required
                placeholder="Housekeeping, dietary, transfer…"
              />
            </Field>
            <Field label="Description">
              <textarea className="textarea" name="description" required />
            </Field>
            <Field label="Department">
              <select className="select" name="department_id">
                <option value="">Unassigned</option>
                {deps
                  .filter((d) => d.is_active)
                  .map((d) => (
                    <option value={d.id} key={d.id}>
                      {d.name}
                    </option>
                  ))}
              </select>
            </Field>
            <Field label="Staff member">
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
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="critical">Critical</option>
              </select>
            </Field>
            <div className="drawerActions">
              <button className="button primary">Create request</button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
