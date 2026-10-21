"use client";
import { readableLabel } from "@/lib/strings/content";
import { formatDate, formatDateTime } from "@/lib/formatting";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
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
    <Field label="Staff member">
      <select className="select" name="staff_id" required>
        <option value="">Select staff…</option>
        {staff.map((s) => (
          <option key={s.id} value={s.id}>
            {s.full_name}
          </option>
        ))}
      </select>
    </Field>
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
            <Form
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
              <Field label="Type">
                <select className="select" name="leave_type">
                  <option value="annual">{readableLabel("annual")}</option>
                  <option value="sick">{readableLabel("sick")}</option>
                  <option value="unpaid">{readableLabel("unpaid")}</option>
                  <option value="other">{readableLabel("other")}</option>
                </select>
              </Field>
              <Field label="Start">
                <input
                  className="field"
                  type="date"
                  name="start_date"
                  required
                />
              </Field>
              <Field label="End">
                <input className="field" type="date" name="end_date" required />
              </Field>
              <Field label="Notes">
                <textarea className="textarea" name="notes" />
              </Field>
              <button className="button primary">Create request</button>
            </Form>
          </section>
          <section className="panel">
            <h2>Leave records</h2>
            {leaves.map((x) => (
              <div className="taskRow" key={x.id}>
                <div>
                  <strong>{x.staff_name}</strong>
                  <small>
                    {readableLabel(x.leave_type)} · {formatDate(x.start_date)} →{" "}
                    {formatDate(x.end_date)}
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
            <Form
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
              <Field label="Starts">
                <input
                  className="field"
                  type="datetime-local"
                  name="starts_at"
                  required
                />
              </Field>
              <Field label="Ends">
                <input
                  className="field"
                  type="datetime-local"
                  name="ends_at"
                  required
                />
              </Field>
              <Field label="Notes">
                <textarea className="textarea" name="notes" />
              </Field>
              <button className="button primary">Schedule shift</button>
            </Form>
          </section>
          <section className="panel">
            <h2>Roster</h2>
            {shifts.map((x) => (
              <div className="taskRow" key={x.id}>
                <div>
                  <strong>{x.staff_name}</strong>
                  <small>
                    {formatDateTime(x.starts_at)} → {formatDateTime(x.ends_at)}
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
            <Form
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
              <Field label="Type">
                <input className="field" name="credential_type" required />
              </Field>
              <Field label="Name">
                <input className="field" name="name" required />
              </Field>
              <Field label="Issuer">
                <input className="field" name="issuer" />
              </Field>
              <Field label="Reference">
                <input className="field" name="reference_number" />
              </Field>
              <Field label="Issued">
                <input className="field" type="date" name="issued_date" />
              </Field>
              <Field label="Expiry">
                <input className="field" type="date" name="expiry_date" />
              </Field>
              <button className="button primary">Save credential</button>
            </Form>
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
                    {x.credential_type} · Expiry{" "}
                    {x.expiry_date ? formatDate(x.expiry_date) : "—"}
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
            <Form
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
              <Field label="Training">
                <input className="field" name="title" required />
              </Field>
              <Field label="Provider">
                <input className="field" name="provider" />
              </Field>
              <Field label="Status">
                <select className="select" name="status">
                  <option value="planned">{readableLabel("planned")}</option>
                  <option value="in_progress">
                    {readableLabel("in_progress")}
                  </option>
                  <option value="completed">
                    {readableLabel("completed")}
                  </option>
                  <option value="expired">{readableLabel("expired")}</option>
                </select>
              </Field>
              <Field label="Completed">
                <input className="field" type="date" name="completed_date" />
              </Field>
              <Field label="Renewal due">
                <input className="field" type="date" name="renewal_due_date" />
              </Field>
              <button className="button primary">Save training</button>
            </Form>
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
                    {x.provider || "—"} · Renewal{" "}
                    {x.renewal_due_date ? formatDate(x.renewal_due_date) : "—"}
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
            <Form
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
              <Field label="Type">
                <input
                  className="field"
                  name="incident_type"
                  defaultValue="operational"
                  required
                />
              </Field>
              <Field label="Severity">
                <select className="select" name="severity">
                  <option value="low">{readableLabel("low")}</option>
                  <option selected value="normal">
                    {readableLabel("normal")}
                  </option>
                  <option value="high">{readableLabel("high")}</option>
                  <option value="critical">{readableLabel("critical")}</option>
                </select>
              </Field>
              <Field label="Occurred">
                <input
                  className="field"
                  type="datetime-local"
                  name="occurred_at"
                  required
                />
              </Field>
              <Field label="Description">
                <textarea className="textarea" name="description" required />
              </Field>
              <Field label="Action taken">
                <textarea className="textarea" name="action_taken" />
              </Field>
              <button className="button primary">Record incident</button>
            </Form>
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
                    {formatDateTime(x.occurred_at)} · {x.description}
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
            <Form
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
              <Field label="Type">
                <select className="select" name="note_type">
                  <option value="review">{readableLabel("review")}</option>
                  <option value="recognition">
                    {readableLabel("recognition")}
                  </option>
                  <option value="coaching">{readableLabel("coaching")}</option>
                  <option value="warning">{readableLabel("warning")}</option>
                  <option value="goal">{readableLabel("goal")}</option>
                </select>
              </Field>
              <Field label="Rating">
                <select className="select" name="rating">
                  <option value="">Not scored</option>
                  {[1, 2, 3, 4, 5].map((x) => (
                    <option key={x}>{x}</option>
                  ))}
                </select>
              </Field>
              <Field label="Review date">
                <input
                  className="field"
                  type="date"
                  name="review_date"
                  required
                />
              </Field>
              <Field label="Notes">
                <textarea className="textarea" name="notes" required />
              </Field>
              <button className="button primary">Save note</button>
            </Form>
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
                    {formatDate(x.review_date)} ·{" "}
                    {x.rating ? `${x.rating}/5 · ` : ""}
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
