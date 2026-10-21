"use client";
import { FormEvent, useEffect, useState } from "react";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { operationsApi } from "@/lib/api";
import StatusPill from "./StatusPill";
type Staff = { id: string; full_name: string };
export default function HRPage() {
  const access = useWorkspaceAccess();
  const rosterEnabled =
    access.feature("staff_roster") && access.permission("staff.hr.view");
  const performanceEnabled =
    access.feature("staff_performance") &&
    access.permission("staff.performance.manage");
  const [staff, setStaff] = useState<Staff[]>([]),
    [leaves, setLeaves] = useState<any[]>([]),
    [credentials, setCredentials] = useState<any[]>([]),
    [training, setTraining] = useState<any[]>([]),
    [shifts, setShifts] = useState<any[]>([]),
    [incidents, setIncidents] = useState<any[]>([]),
    [performance, setPerformance] = useState<any[]>([]),
    [tab, setTab] = useState("leave"),
    [error, setError] = useState("");
  const load = async () => {
    try {
      const [s, l, c, t, sh, i, p] = await Promise.all([
        access.feature("staff")
          ? operationsApi.staff.list()
          : Promise.resolve([]),
        operationsApi.hr.leaves.list(),
        operationsApi.hr.credentials.list(),
        operationsApi.hr.training.list(),
        rosterEnabled ? operationsApi.hr.shifts.list() : Promise.resolve([]),
        performanceEnabled
          ? operationsApi.hr.incidents.list()
          : Promise.resolve([]),
        performanceEnabled
          ? operationsApi.hr.performance.list()
          : Promise.resolve([]),
      ]);
      setStaff(s);
      setLeaves(l);
      setCredentials(c);
      setTraining(t);
      setShifts(sh);
      setIncidents(i);
      setPerformance(p);
    } catch (e: any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    if (
      (tab === "shifts" && !rosterEnabled) ||
      (["incidents", "performance"].includes(tab) && !performanceEnabled)
    )
      setTab("leave");
    void load();
  }, [rosterEnabled, performanceEnabled]);
  const StaffSelect = () => (
    <select className="select" name="staff_id" required>
      <option value="">Select staff…</option>
      {staff.map((s) => (
        <option key={s.id} value={s.id}>
          {s.full_name}
        </option>
      ))}
    </select>
  );
  async function submit(
    e: FormEvent<HTMLFormElement>,
    fn: (body: any) => Promise<any>,
    body: (f: FormData) => any,
  ) {
    e.preventDefault();
    const form = e.currentTarget;
    const f = new FormData(form);
    try {
      await fn(body(f));
      form.reset();
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">PEOPLE OPERATIONS</span>
          <h1>Staff HR</h1>
          <p>
            Support your people with coordinated leave, rosters, training and
            confidential staff records.
          </p>
        </div>
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <div className="tabs">
        {[
          ["leave", "Leave"],
          ["shifts", "Roster"],
          ["credentials", "Credentials"],
          ["training", "Training"],
          ["incidents", "Incidents"],
          ["performance", "Performance"],
        ]
          .filter(([key]) =>
            key === "shifts"
              ? rosterEnabled
              : ["incidents", "performance"].includes(key)
                ? performanceEnabled
                : true,
          )
          .map(([k, l]) => (
            <button
              key={k}
              className={tab === k ? "button primary" : "button"}
              onClick={() => setTab(k)}
            >
              {l}
            </button>
          ))}
      </div>
      {tab === "leave" && (
        <div className="twoCol">
          <section className="card formCard">
            <h2>New leave request</h2>
            <form
              onSubmit={(e) =>
                submit(e, operationsApi.hr.leaves.create, (f) => ({
                  staff_id: String(f.get("staff_id")),
                  leave_type: String(f.get("leave_type")),
                  start_date: String(f.get("start_date")),
                  end_date: String(f.get("end_date")),
                  notes: String(f.get("notes") || ""),
                }))
              }
            >
              <StaffSelect />
              <label className="label">Type</label>
              <select className="select" name="leave_type">
                <option>annual</option>
                <option>sick</option>
                <option>unpaid</option>
                <option>other</option>
              </select>
              <label className="label">Start</label>
              <input className="field" type="date" name="start_date" required />
              <label className="label">End</label>
              <input className="field" type="date" name="end_date" required />
              <label className="label">Notes</label>
              <textarea className="textarea" name="notes" />
              <button className="button primary">Create request</button>
            </form>
          </section>
          <section className="panel">
            <h2>Leave records</h2>
            {leaves.map((x) => (
              <div className="taskRow" key={x.id}>
                <div>
                  <strong>{x.staff_name}</strong>
                  <small>
                    {x.leave_type} · {x.start_date} → {x.end_date}
                  </small>
                </div>
                <div>
                  <StatusPill value={x.status} />
                  {x.status === "pending" && (
                    <div style={{ marginTop: 6 }}>
                      <button
                        className="button secondary"
                        onClick={async () => {
                          await operationsApi.hr.leaves.update(x.id, {
                            status: "approved",
                          });
                          load();
                        }}
                      >
                        Approve
                      </button>{" "}
                      <button
                        className="button secondary"
                        onClick={async () => {
                          await operationsApi.hr.leaves.update(x.id, {
                            status: "rejected",
                          });
                          load();
                        }}
                      >
                        Reject
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </section>
        </div>
      )}
      {tab === "shifts" && rosterEnabled && (
        <div className="twoCol">
          <section className="card formCard">
            <h2>Schedule shift</h2>
            <form
              onSubmit={(e) =>
                submit(e, operationsApi.hr.shifts.create, (f) => ({
                  staff_id: String(f.get("staff_id")),
                  starts_at: new Date(String(f.get("starts_at"))).toISOString(),
                  ends_at: new Date(String(f.get("ends_at"))).toISOString(),
                  notes: String(f.get("notes") || ""),
                }))
              }
            >
              <StaffSelect />
              <label className="label">Starts</label>
              <input
                className="field"
                type="datetime-local"
                name="starts_at"
                required
              />
              <label className="label">Ends</label>
              <input
                className="field"
                type="datetime-local"
                name="ends_at"
                required
              />
              <label className="label">Notes</label>
              <textarea className="textarea" name="notes" />
              <button className="button primary">Schedule shift</button>
            </form>
          </section>
          <section className="panel">
            <h2>Roster</h2>
            {shifts.map((x) => (
              <div className="taskRow" key={x.id}>
                <div>
                  <strong>{x.staff_name}</strong>
                  <small>
                    {new Date(x.starts_at).toLocaleString()} →{" "}
                    {new Date(x.ends_at).toLocaleString()}
                  </small>
                </div>
                <StatusPill value={x.status} />
              </div>
            ))}
          </section>
        </div>
      )}
      {tab === "credentials" && (
        <div className="twoCol">
          <section className="card formCard">
            <h2>Add credential</h2>
            <form
              onSubmit={(e) =>
                submit(e, operationsApi.hr.credentials.create, (f) => ({
                  staff_id: String(f.get("staff_id")),
                  credential_type: String(f.get("credential_type")),
                  name: String(f.get("name")),
                  issuer: String(f.get("issuer") || ""),
                  reference_number: String(f.get("reference_number") || ""),
                  issued_date: String(f.get("issued_date") || "") || null,
                  expiry_date: String(f.get("expiry_date") || "") || null,
                  notes: "",
                }))
              }
            >
              <StaffSelect />
              <label className="label">Type</label>
              <input className="field" name="credential_type" required />
              <label className="label">Name</label>
              <input className="field" name="name" required />
              <label className="label">Issuer</label>
              <input className="field" name="issuer" />
              <label className="label">Reference</label>
              <input className="field" name="reference_number" />
              <label className="label">Issued</label>
              <input className="field" type="date" name="issued_date" />
              <label className="label">Expiry</label>
              <input className="field" type="date" name="expiry_date" />
              <button className="button primary">Save credential</button>
            </form>
          </section>
          <section className="panel">
            <h2>Credentials</h2>
            {credentials.map((x) => (
              <div className="taskRow" key={x.id}>
                <div>
                  <strong>
                    {x.staff_name} · {x.name}
                  </strong>
                  <small>
                    {x.credential_type} · Expiry {x.expiry_date || "—"}
                  </small>
                </div>
              </div>
            ))}
          </section>
        </div>
      )}
      {tab === "training" && (
        <div className="twoCol">
          <section className="card formCard">
            <h2>Add training</h2>
            <form
              onSubmit={(e) =>
                submit(e, operationsApi.hr.training.create, (f) => ({
                  staff_id: String(f.get("staff_id")),
                  title: String(f.get("title")),
                  provider: String(f.get("provider") || ""),
                  completed_date: String(f.get("completed_date") || "") || null,
                  renewal_due_date:
                    String(f.get("renewal_due_date") || "") || null,
                  status: String(f.get("status")),
                  notes: "",
                }))
              }
            >
              <StaffSelect />
              <label className="label">Training</label>
              <input className="field" name="title" required />
              <label className="label">Provider</label>
              <input className="field" name="provider" />
              <label className="label">Status</label>
              <select className="select" name="status">
                <option>planned</option>
                <option>in_progress</option>
                <option>completed</option>
                <option>expired</option>
              </select>
              <label className="label">Completed</label>
              <input className="field" type="date" name="completed_date" />
              <label className="label">Renewal due</label>
              <input className="field" type="date" name="renewal_due_date" />
              <button className="button primary">Save training</button>
            </form>
          </section>
          <section className="panel">
            <h2>Training records</h2>
            {training.map((x) => (
              <div className="taskRow" key={x.id}>
                <div>
                  <strong>
                    {x.staff_name} · {x.title}
                  </strong>
                  <small>
                    {x.provider || "—"} · Renewal {x.renewal_due_date || "—"}
                  </small>
                </div>
                <StatusPill value={x.status} />
              </div>
            ))}
          </section>
        </div>
      )}
      {tab === "incidents" && performanceEnabled && (
        <div className="twoCol">
          <section className="card formCard">
            <h2>Record incident</h2>
            <form
              onSubmit={(e) =>
                submit(e, operationsApi.hr.incidents.create, (f) => ({
                  staff_id: String(f.get("staff_id")),
                  incident_type: String(f.get("incident_type")),
                  severity: String(f.get("severity")),
                  occurred_at: new Date(
                    String(f.get("occurred_at")),
                  ).toISOString(),
                  description: String(f.get("description")),
                  action_taken: String(f.get("action_taken") || ""),
                  is_confidential: true,
                }))
              }
            >
              <StaffSelect />
              <label className="label">Type</label>
              <input
                className="field"
                name="incident_type"
                defaultValue="operational"
                required
              />
              <label className="label">Severity</label>
              <select className="select" name="severity">
                <option>low</option>
                <option selected>normal</option>
                <option>high</option>
                <option>critical</option>
              </select>
              <label className="label">Occurred</label>
              <input
                className="field"
                type="datetime-local"
                name="occurred_at"
                required
              />
              <label className="label">Description</label>
              <textarea className="textarea" name="description" required />
              <label className="label">Action taken</label>
              <textarea className="textarea" name="action_taken" />
              <button className="button primary">Record incident</button>
            </form>
          </section>
          <section className="panel">
            <h2>Incident history</h2>
            {incidents.map((x) => (
              <div className="taskRow" key={x.id}>
                <div>
                  <strong>
                    {x.staff_name} · {x.incident_type}
                  </strong>
                  <small>
                    {new Date(x.occurred_at).toLocaleString()} · {x.description}
                  </small>
                </div>
                <StatusPill value={x.severity} />
              </div>
            ))}
          </section>
        </div>
      )}
      {tab === "performance" && performanceEnabled && (
        <div className="twoCol">
          <section className="card formCard">
            <h2>Add performance note</h2>
            <form
              onSubmit={(e) =>
                submit(e, operationsApi.hr.performance.create, (f) => ({
                  staff_id: String(f.get("staff_id")),
                  note_type: String(f.get("note_type")),
                  rating: f.get("rating") ? Number(f.get("rating")) : null,
                  notes: String(f.get("notes")),
                  review_date: String(f.get("review_date")),
                }))
              }
            >
              <StaffSelect />
              <label className="label">Type</label>
              <select className="select" name="note_type">
                <option>review</option>
                <option>recognition</option>
                <option>coaching</option>
                <option>warning</option>
                <option>goal</option>
              </select>
              <label className="label">Rating</label>
              <select className="select" name="rating">
                <option value="">Not scored</option>
                {[1, 2, 3, 4, 5].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
              <label className="label">Review date</label>
              <input
                className="field"
                type="date"
                name="review_date"
                required
              />
              <label className="label">Notes</label>
              <textarea className="textarea" name="notes" required />
              <button className="button primary">Save note</button>
            </form>
          </section>
          <section className="panel">
            <h2>Performance history</h2>
            {performance.map((x) => (
              <div className="taskRow" key={x.id}>
                <div>
                  <strong>
                    {x.staff_name} · {x.note_type}
                  </strong>
                  <small>
                    {x.review_date} · {x.rating ? `${x.rating}/5 · ` : ""}
                    {x.notes}
                  </small>
                </div>
              </div>
            ))}
          </section>
        </div>
      )}
    </>
  );
}
