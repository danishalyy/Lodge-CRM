"use client";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { authApi, getActiveLodgeId, operationsApi } from "@/lib/api";

type Department = { id: string; name: string; is_active: boolean };
type Staff = {
  id: string;
  full_name: string;
  email?: string;
  phone: string;
  job_title: string;
  employee_code?: string;
  department_id?: string;
  department_name?: string;
  employment_status: string;
  operational_status: string;
  has_login?: boolean;
  account_status?: string;
  delivery_status?: string;
  supervisor_staff_id?: string;
  supervisor_name?: string;
  hire_date?: string;
  custom_role_id?: string;
  custom_role_name?: string;
};
const roles = [
  ["department_manager", "Department Manager / Supervisor"],
  ["front_office", "Front Office / Guest Services"],
  ["ranger", "Ranger / Guide"],
  ["housekeeping", "Housekeeping"],
  ["maintenance", "Maintenance / Workshop"],
  ["driver", "Driver / Transport"],
  ["fb", "F&B / Kitchen"],
  ["finance", "Finance / Accounts"],
  ["general_staff", "General Staff"],
  ["read_only", "Read Only / Auditor"],
] as const;
export default function StaffPage() {
  const [rows, setRows] = useState<Staff[]>([]),
    [deps, setDeps] = useState<Department[]>([]),
    [customRoles, setCustomRoles] = useState<any[]>([]),
    [open, setOpen] = useState(false),
    [inviteStaff, setInviteStaff] = useState<Staff | null>(null),
    [devLink, setDevLink] = useState(""),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false),
    [inviteOnCreate, setInviteOnCreate] = useState(true),
    [canManage, setCanManage] = useState(false);
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [s, d, cr, me] = await Promise.all([
        operationsApi.staff.list<Staff[]>(),
        operationsApi.departments.list<Department[]>().catch(() => []),
        operationsApi.roles.list().catch(() => []),
        authApi.me(),
      ]);
      const member = me.memberships?.find(
        (m: any) => m.lodge_id === getActiveLodgeId(),
      );
      setCanManage(
        !!me.is_super_admin || !!member?.permissions?.includes("staff.manage"),
      );
      setRows(s);
      setDeps(d);
      setCustomRoles(cr);
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
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await operationsApi.staff.create<any>({
        invite_role_key: inviteOnCreate ? String(f.get("role_key")) : null,
        full_name: String(f.get("full_name")),
        email: String(f.get("email") || "") || null,
        phone: String(f.get("phone") || ""),
        job_title: String(f.get("job_title") || ""),
        employee_code: String(f.get("employee_code") || "") || null,
        department_id: String(f.get("department_id") || "") || null,
        employment_status: "active",
        operational_status: "available",
        supervisor_staff_id: String(f.get("supervisor_staff_id") || "") || null,
        hire_date: String(f.get("hire_date") || "") || null,
      });
      setOpen(false);
      setDevLink(
        result.activation_token
          ? `${location.origin}/activate#token=${result.activation_token}`
          : "",
      );
      setNotice(
        inviteOnCreate
          ? "Staff account created. The owner must use their invitation to choose a password. Email status: " +
              result.delivery_status
          : "Staff profile created.",
      );
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function status(id: string, value: string) {
    try {
      await operationsApi.staff.update(id, { operational_status: value });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function invite(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!inviteStaff) return;
    const f = new FormData(e.currentTarget);
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const r = await operationsApi.staff.invite(
        inviteStaff.id,
        String(f.get("role_key")),
      );
      setDevLink(
        r.activation_token
          ? `${location.origin}/activate#token=${r.activation_token}`
          : "",
      );
      setNotice(
        "Invitation " +
          r.delivery_status +
          ". The owner sets their own password.",
      );
      await load();
      setInviteStaff(null);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function resend(r: Staff) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await operationsApi.staff.resendInvitation(r.id);
      setDevLink(
        result.activation_token
          ? `${location.origin}/activate#token=${result.activation_token}`
          : "",
      );
      setNotice(
        "Replacement invitation " +
          result.delivery_status +
          ". The previous link no longer works.",
      );
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">PEOPLE</span>
          <h1>Staff</h1>
          <p>
            Your team, organised. Manage responsibilities, account access and
            day-to-day availability.
          </p>
        </div>
        {canManage && (
          <button className="button primary" onClick={() => setOpen(true)}>
            + Staff member
          </button>
        )}
      </div>
      {notice && (
        <div className="panel" role="status">
          {notice}
        </div>
      )}
      {devLink && (
        <div className="panel">
          <label htmlFor="development-link" className="label">
            Private development invitation · share only with the account owner
          </label>
          <textarea
            id="development-link"
            className="textarea"
            readOnly
            value={devLink}
          />
          <button className="button" onClick={() => setDevLink("")}>
            Hide link
          </button>
        </div>
      )}
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel">
        <div className="tableWrap">
          {loading ? (
            <div className="empty">Loading…</div>
          ) : (
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Department</th>
                  <th>Job title</th>
                  <th>Employment</th>
                  <th>Operational status</th>
                  <th>Supervisor</th>
                  <th>Role</th>
                  <th>Login</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>
                      <strong>{r.full_name}</strong>
                      <br />
                      <small>{r.email || r.phone || "—"}</small>
                    </td>
                    <td>{r.department_name || "—"}</td>
                    <td>{r.job_title || "—"}</td>
                    <td>
                      <StatusPill value={r.employment_status} />
                    </td>
                    <td>
                      <select
                        className="select"
                        disabled={!canManage}
                        value={r.operational_status}
                        onChange={(e) => status(r.id, e.target.value)}
                      >
                        <option value="available">Available</option>
                        <option value="on_shift">On shift</option>
                        <option value="on_drive">On drive</option>
                        <option value="off_duty">Off duty</option>
                        <option value="leave">Leave</option>
                      </select>
                    </td>
                    <td>{r.supervisor_name || "—"}</td>
                    <td>
                      {r.custom_role_name || "System role"}
                      {canManage && r.has_login && customRoles.length > 0 && (
                        <select
                          className="select"
                          value={r.custom_role_id || ""}
                          onChange={async (e) => {
                            try {
                              await operationsApi.staff.assignCustomRole(
                                r.id,
                                e.target.value || null,
                              );
                              await load();
                            } catch (e: any) {
                              setError(e.message);
                            }
                          }}
                        >
                          <option value="">System role</option>
                          {customRoles
                            .filter((x: any) => x.is_active)
                            .map((x: any) => (
                              <option key={x.id} value={x.id}>
                                {x.name}
                              </option>
                            ))}
                        </select>
                      )}
                    </td>
                    <td>
                      {r.has_login ? (
                        <>
                          <StatusPill value={r.account_status || "active"} />
                          {r.delivery_status && (
                            <small className="textSecondary">
                              Email: {r.delivery_status}
                            </small>
                          )}
                          {canManage && r.account_status !== "active" && (
                            <button
                              className="button secondary"
                              disabled={
                                busy || r.employment_status !== "active"
                              }
                              onClick={() => resend(r)}
                            >
                              Resend invitation
                            </button>
                          )}
                        </>
                      ) : (
                        <button
                          className="button secondary"
                          onClick={() => {
                            setInviteStaff(r);
                            setDevLink("");
                          }}
                          disabled={
                            !canManage ||
                            !r.email ||
                            r.employment_status !== "active"
                          }
                        >
                          Invite
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}{" "}
          {!loading && !rows.length && (
            <div className="empty">
              No staff profiles have been created yet.
            </div>
          )}
        </div>
      </section>
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <div>
              <h1>Add staff member</h1>
              <div className="sub">
                Create a staff profile and invite the owner to choose their own
                password. Gmail and business addresses are supported.
              </div>
            </div>
            <button className="closeButton" onClick={() => setOpen(false)}>
              ×
            </button>
          </div>
          <form onSubmit={create}>
            <label className="label">Full name</label>
            <input className="field" name="full_name" required />
            <label className="label">Employee code</label>
            <input className="field" name="employee_code" />
            <label className="label">Department</label>
            <select className="select" name="department_id">
              <option value="">No department</option>
              {deps
                .filter((d) => d.is_active)
                .map((d) => (
                  <option value={d.id} key={d.id}>
                    {d.name}
                  </option>
                ))}
            </select>
            <label className="label">Job title</label>
            <input className="field" name="job_title" />
            <label className="label">Supervisor</label>
            <select className="select" name="supervisor_staff_id">
              <option value="">No supervisor</option>
              {rows
                .filter((s) => s.employment_status === "active")
                .map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name}
                  </option>
                ))}
            </select>
            <label className="label">Hire date</label>
            <input className="field" type="date" name="hire_date" />
            <label className="label">Email</label>
            <input
              className="field"
              type="email"
              name="email"
              required={inviteOnCreate}
            />
            <label className="checkRow">
              <input
                type="checkbox"
                checked={inviteOnCreate}
                onChange={(e) => setInviteOnCreate(e.target.checked)}
              />
              Invite to SafariOS
            </label>
            {inviteOnCreate && (
              <>
                <label className="label">Account role</label>
                <select
                  className="select"
                  name="role_key"
                  defaultValue="general_staff"
                >
                  {roles.map(([k, n]) => (
                    <option key={k} value={k}>
                      {n}
                    </option>
                  ))}
                </select>
                <p className="sub">
                  An expiring private link is emailed to this address. You never
                  choose or see their password.
                </p>
              </>
            )}
            <label className="label">Phone</label>
            <input className="field" name="phone" />
            <div className="drawerActions">
              <button className="button primary" disabled={busy}>
                {busy
                  ? "Creating…"
                  : inviteOnCreate
                    ? "Create and invite"
                    : "Create staff profile"}
              </button>
            </div>
          </form>
        </Drawer>
      )}
      {inviteStaff && (
        <Drawer onClose={() => setInviteStaff(null)}>
          <div className="drawerHead">
            <div>
              <h1>Invite {inviteStaff.full_name}</h1>
              <div className="sub">
                Creates or links a secure user account and lodge membership.
                Production sends the activation link through configured SMTP.
              </div>
            </div>
            <button
              className="closeButton"
              onClick={() => setInviteStaff(null)}
            >
              ×
            </button>
          </div>
          {devLink ? (
            <>
              <label className="label">Development activation link</label>
              <textarea className="textarea" readOnly value={devLink} />
              <p className="sub">
                Share this private activation link securely with the staff
                member.
              </p>
              <div className="drawerActions">
                <button
                  className="button primary"
                  onClick={() => {
                    navigator.clipboard.writeText(devLink);
                  }}
                >
                  Copy link
                </button>
                <button
                  className="button secondary"
                  onClick={() => setInviteStaff(null)}
                >
                  Close
                </button>
              </div>
            </>
          ) : (
            <form onSubmit={invite}>
              <label className="label">Login email</label>
              <input
                className="field"
                value={inviteStaff.email || ""}
                readOnly
              />
              <label className="label">Role</label>
              <select className="select" name="role_key" required>
                {roles.map(([k, n]) => (
                  <option key={k} value={k}>
                    {n}
                  </option>
                ))}
              </select>
              <div className="drawerActions">
                <button className="button primary" disabled={busy}>
                  {busy ? "Queuing…" : "Send invitation"}
                </button>
              </div>
            </form>
          )}
        </Drawer>
      )}
    </>
  );
}
