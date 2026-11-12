"use client";
import { StatusBoard } from "./ui/status-board";
import { workflowColumns, nextStatuses } from "@/lib/status-transitions";
import { Skeleton } from "./ui/skeleton";
import { useInstantRows, useDataRefresh } from "@/lib/use-instant-actions";
import { instantCopy as instant } from "@/lib/strings/interactivity";
import { readableLabel } from "@/lib/strings/content";
import { formatDateTime } from "@/lib/formatting";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { FormEvent, useEffect, useState } from "react";
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
type Room = {
  id: string;
  name: string;
  status: string;
  current_guest?: string;
};
type Staff = {
  id: string;
  full_name: string;
  employment_status: string;
  department_name?: string;
};
const next: Record<string, string | undefined> = {
  assigned: "accepted",
  accepted: "in_progress",
  in_progress: "awaiting_inspection",
  awaiting_inspection: "completed",
};
export default function HousekeepingPage() {
  const access = useWorkspaceAccess();
  const [createOpen, setCreateOpen] = useState(false);
  const [assetOpen, setAssetOpen] = useState(false);
  const [rooms, setRooms] = useState<Room[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
    [error, setError] = useState(""),
    [canManage, setCanManage] = useState(false);
  const {
    rows: jobs,
    setRows: setJobs,
    pending,
    mutate,
  } = useInstantRows<any>(access.scopeKey);
  const fullWorkflow = access.feature("housekeeping_full");
  const [loading, setLoading] = useState(true);
  const load = async () => {
    try {
      const me = await authApi.me();
      const m = me.memberships?.find(
        (x: any) => x.lodge_id === getActiveLodgeId(),
      );
      const manage =
        !access.readOnly &&
        Boolean(m?.permissions?.includes("housekeeping.manage"));
      setCanManage(manage);

      const [r, s, j] = await Promise.all([
        access.feature("units") && access.permission("units.view")
          ? lodgeApi.rooms()
          : Promise.resolve([]),
        manage && access.feature("staff") && access.permission("staff.view")
          ? operationsApi.staff.list().catch(() => [])
          : Promise.resolve([]),
        operationsApi.housekeeping.list(),
      ]);
      setRooms(r);
      setStaff(s);
      setJobs(j);
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
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await operationsApi.housekeeping.create({
        unit_id: String(f.get("unit_id")),
        assigned_staff_id: String(f.get("assigned_staff_id") || "") || null,
        inspector_staff_id: String(f.get("inspector_staff_id") || "") || null,
        job_type: String(f.get("job_type")),
        linen_notes: String(f.get("linen_notes") || ""),
        notes: String(f.get("notes") || ""),
        due_at: String(f.get("due_at") || "")
          ? new Date(String(f.get("due_at"))).toISOString()
          : null,
      });
      form.reset();
      setCreateOpen(false);
      setAssetOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  useDataRefresh(load, pending.length > 0 || createOpen || assetOpen);
  async function update(id: string, status: string) {
    const scope = {
      userId: getActiveUserId(),
      lodgeId: getActiveLodgeId(),
      silent: true,
    };
    return await mutate(
      id,
      { status },
      (patch) => operationsApi.housekeeping.update(id, patch, scope),
      {
        message: instant.housekeeping,
        refresh: load,
        onError: (e) => {
          setError((e as Error).message);
          if (
            e instanceof ApiError &&
            ([401, 403, 404].includes(e.status) ||
              (e.status === 409 &&
                /account changed|access changed/i.test(e.message)))
          ) {
            setJobs([]);
            setRooms([]);
          }
        },
      },
    );
  }
  return (
    <>
      {loading && !jobs.length && (
        <div role="status" aria-label={instant.loading}>
          <Skeleton className="h-20 mb-4" />
          <Skeleton className="h-20" />
        </div>
      )}
      <div className="pageHeader">
        <div>
          <span className="eyebrow">HOUSEKEEPING</span>
          <h1>Housekeeping workflow</h1>
          <p>
            Cleaning, turndown, linen and inspections use assigned jobs and
            authoritative room readiness states.
          </p>
        </div>
        {canManage && (
          <button
            className="button primary"
            onClick={() => setCreateOpen(true)}
          >
            + Add job
          </button>
        )}
      </div>
      {error && (
        <div className="panel dangerText" role="alert">
          {error}
        </div>
      )}
      <div className="summaryStrip">
        {[
          "ready",
          "occupied",
          "cleaning",
          "awaiting_inspection",
          "maintenance",
        ].map((s) => (
          <div className="summaryBox" key={s}>
            <strong>{rooms.filter((r) => r.status === s).length}</strong>
            <span>{readableLabel(s)}</span>
          </div>
        ))}
      </div>
      <div className="moduleContent">
        {canManage && (
          <>
            {createOpen && (
              <Drawer onClose={() => setCreateOpen(false)}>
                <div className="drawerHead">
                  <h2>Create housekeeping job</h2>
                  <button
                    className="closeButton"
                    aria-label="Close dialog"
                    onClick={() => setCreateOpen(false)}
                  >
                    ×
                  </button>
                </div>

                <Form onSubmit={create}>
                  <Field label="Room / unit">
                    <select className="select" name="unit_id" required>
                      <option value="">Select unit…</option>
                      {rooms.map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.name} · {readableLabel(r.status)}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field label="Job type">
                    <select className="select" name="job_type">
                      <option value="cleaning">Cleaning</option>
                      {fullWorkflow && (
                        <>
                          <option value="turndown">Turndown</option>
                          <option value="inspection">Inspection</option>
                          <option value="linen">Linen</option>
                        </>
                      )}
                      <option value="guest_request">Guest request</option>
                    </select>
                  </Field>
                  <Field label="Assigned housekeeper">
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
                  {fullWorkflow && (
                    <>
                      <Field label="Inspector">
                        <select className="select" name="inspector_staff_id">
                          <option value="">No named inspector</option>
                          {staff
                            .filter((s) => s.employment_status === "active")
                            .map((s) => (
                              <option key={s.id} value={s.id}>
                                {s.full_name}
                              </option>
                            ))}
                        </select>
                      </Field>
                    </>
                  )}
                  <Field label="Due">
                    <input
                      className="field"
                      type="datetime-local"
                      name="due_at"
                    />
                  </Field>
                  {fullWorkflow && (
                    <>
                      <Field label="Linen requirements">
                        <textarea className="textarea" name="linen_notes" />
                      </Field>
                    </>
                  )}
                  <Field label="Notes">
                    <textarea className="textarea" name="notes" />
                  </Field>
                  <div className="drawerActions">
                    <button className="button primary">Create job</button>
                  </div>
                </Form>
              </Drawer>
            )}
          </>
        )}
        <section className="panel">
          <h2>Active housekeeping</h2>
          <StatusBoard
            name="housekeeping"
            cardsView
            items={jobs.map((row) => ({
              ...row,
              title: row.unit_name || row.job_type,
            }))}
            actions={{
              columns: workflowColumns("housekeeping"),
              pending: (id) => pending.includes(id),
              allowed: (id) => {
                const row = jobs.find((row) => row.id === id);
                return !access.readOnly && canManage && row
                  ? nextStatuses("housekeeping", row.status).filter(
                      (s) =>
                        !(
                          row.status === "in_progress" &&
                          s === "completed" &&
                          row.inspector_staff_id
                        ),
                    )
                  : [];
              },
              onMove: (id, status) => {
                const row = jobs.find((row) => row.id === id);
                if (!row) return Promise.resolve(false);
                return update(id, status);
              },
            }}
            renderCard={(j) => (
              <div className="taskRow" key={j.id}>
                <div>
                  <strong>
                    {j.unit_name} · {readableLabel(j.job_type)}
                  </strong>
                  <small>
                    {j.assigned_staff_name || "Unassigned"} · Due{" "}
                    {j.due_at ? formatDateTime(j.due_at) : "—"}
                  </small>
                  {j.linen_notes && <p>{j.linen_notes}</p>}
                </div>
                <div>
                  <StatusPill value={j.status} />
                  {pending.includes(j.id) && (
                    <small role="status">{instant.saving}</small>
                  )}
                  {canManage && (next[j.status] || pending.includes(j.id)) && (
                    <div style={{ marginTop: 6 }}>
                      <button
                        className="button secondary"
                        disabled={pending.includes(j.id)}
                        aria-busy={pending.includes(j.id)}
                        onClick={() => update(j.id, next[j.status]!)}
                      >
                        {next[j.status]
                          ? readableLabel(next[j.status]!)
                          : instant.saving}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}
          />
          {!loading && !jobs.length && (
            <div className="empty">No housekeeping jobs have been created.</div>
          )}
        </section>
      </div>
    </>
  );
}
