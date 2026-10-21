"use client";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { FormEvent, useEffect, useState } from "react";
import StatusPill from "./StatusPill";
import { authApi, getActiveLodgeId, lodgeApi, operationsApi } from "@/lib/api";
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
  const [rooms, setRooms] = useState<Room[]>([]),
    [staff, setStaff] = useState<Staff[]>([]),
    [jobs, setJobs] = useState<any[]>([]),
    [error, setError] = useState(""),
    [canManage, setCanManage] = useState(false);
  const fullWorkflow = access.feature("housekeeping_full");
  const load = async () => {
    try {
      const me = await authApi.me();
      const m = me.memberships?.find(
        (x: any) => x.lodge_id === getActiveLodgeId(),
      );
      const manage = Boolean(
        me.is_super_admin || m?.permissions?.includes("housekeeping.manage"),
      );
      setCanManage(manage);

      const [r, s, j] = await Promise.all([
        access.feature("units") ? lodgeApi.rooms() : Promise.resolve([]),
        manage && access.feature("staff")
          ? operationsApi.staff.list().catch(() => [])
          : Promise.resolve([]),
        operationsApi.housekeeping.list(),
      ]);
      setRooms(r);
      setStaff(s);
      setJobs(j);
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
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function update(id: string, status: string) {
    try {
      await operationsApi.housekeeping.update(id, { status });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">HOUSEKEEPING</span>
          <h1>Housekeeping workflow</h1>
          <p>
            Cleaning, turndown, linen and inspections use assigned jobs and
            authoritative room readiness states.
          </p>
        </div>
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <div className="summaryStrip">
        {[
          "ready",
          "occupied",
          "cleaning",
          "cleaning",
          "awaiting_inspection",
          "maintenance",
        ].map((s) => (
          <div className="summaryBox" key={s}>
            <strong>{rooms.filter((r) => r.status === s).length}</strong>
            <span>{s.replaceAll("_", " ")}</span>
          </div>
        ))}
      </div>
      <div className={canManage ? "twoCol" : ""}>
        {canManage && (
          <section className="card formCard">
            <h2>Create housekeeping job</h2>
            <form onSubmit={create}>
              <label className="label">Room / unit</label>
              <select className="select" name="unit_id" required>
                <option value="">Select unit…</option>
                {rooms.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name} · {r.status}
                  </option>
                ))}
              </select>
              <label className="label">Job type</label>
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
              <label className="label">Assigned housekeeper</label>
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
              {fullWorkflow && (
                <>
                  <label className="label">Inspector</label>
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
                </>
              )}
              <label className="label">Due</label>
              <input className="field" type="datetime-local" name="due_at" />
              {fullWorkflow && (
                <>
                  <label className="label">Linen requirements</label>
                  <textarea className="textarea" name="linen_notes" />
                </>
              )}
              <label className="label">Notes</label>
              <textarea className="textarea" name="notes" />
              <button className="button primary">Create job</button>
            </form>
          </section>
        )}
        <section className="panel">
          <h2>Active housekeeping</h2>
          {jobs.map((j) => (
            <div className="taskRow" key={j.id}>
              <div>
                <strong>
                  {j.unit_name} · {j.job_type.replaceAll("_", " ")}
                </strong>
                <small>
                  {j.assigned_staff_name || "Unassigned"} · Due{" "}
                  {j.due_at ? new Date(j.due_at).toLocaleString() : "—"}
                </small>
                {j.linen_notes && <p>{j.linen_notes}</p>}
              </div>
              <div>
                <StatusPill value={j.status} />
                {next[j.status] && (
                  <div style={{ marginTop: 6 }}>
                    <button
                      className="button secondary"
                      onClick={() => update(j.id, next[j.status]!)}
                    >
                      {next[j.status]!.replaceAll("_", " ")}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {!jobs.length && (
            <div className="empty">No housekeeping jobs have been created.</div>
          )}
        </section>
      </div>
    </>
  );
}
