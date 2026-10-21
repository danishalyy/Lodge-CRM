"use client";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "@/components/Drawer";
import { superApi } from "@/lib/api";
import { DataTable } from "@/components/ui/data-table";
import { Skeleton } from "@/components/ui/skeleton";
import type { ColumnDef } from "@tanstack/react-table";
type User = {
  id: string;
  full_name: string;
  email: string;
  is_super_admin: boolean;
  is_active: boolean;
  mfa_enabled: boolean;
  account_status?: string;
  delivery_status?: string;
  memberships: { lodge_id: string; lodge_name: string; role: string }[];
};
const columns: ColumnDef<User, any>[] = [
  {
    accessorKey: "full_name",
    header: "User",
    cell: ({ row }) => (
      <>
        <strong>{row.original.full_name}</strong>
        <div className="textSecondary">{row.original.email}</div>
      </>
    ),
  },
  {
    id: "account",
    accessorFn: (r) =>
      r.is_super_admin ? "Super Admin" : r.is_active ? "Active" : "Inactive",
    header: "Account",
  },
  {
    accessorKey: "mfa_enabled",
    header: "MFA",
    cell: ({ getValue }) => (getValue() ? "Enabled" : "Not enabled"),
  },
  {
    id: "memberships",
    header: "Memberships",
    cell: ({ row }) =>
      row.original.memberships?.map((m) => (
        <div key={m.lodge_id}>
          {m.lodge_name} · {m.role}
        </div>
      )) || "—",
  },
];
export default function Page() {
  const [rows, setRows] = useState<User[]>([]),
    [err, setErr] = useState(""),
    [loading, setLoading] = useState(true),
    [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false),
    [notice, setNotice] = useState(""),
    [devLink, setDevLink] = useState("");
  function feedback(r: any) {
    setDevLink(
      r.activation_token
        ? `${location.origin}/activate#token=${r.activation_token}`
        : "",
    );
    setNotice(
      "Invitation " +
        r.delivery_status +
        ". The owner must use their private link to set a password.",
    );
    load();
  }
  async function invite(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    const f = new FormData(e.currentTarget);
    try {
      const r = await superApi.inviteUser({
        full_name: String(f.get("full_name")),
        email: String(f.get("email")),
      });
      setOpen(false);
      feedback(r);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function resend(id: string) {
    if (busy) return;
    setBusy(true);
    try {
      feedback(await superApi.resendInvitation(id));
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  function load() {
    setErr("");
    setLoading(true);
    superApi
      .users()
      .then(setRows)
      .catch((e: Error) => setErr(e.message))
      .finally(() => setLoading(false));
  }
  useEffect(load, []);
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">SUPER ADMIN</span>
          <h1>Platform Users</h1>
          <p>
            Real user accounts, security status and active lodge memberships.
          </p>
        </div>
        <button className="button primary" onClick={() => setOpen(true)}>
          Invite Super Admin
        </button>
      </div>
      {notice && (
        <section className="panel" role="status">
          {notice}
        </section>
      )}
      {devLink && (
        <section className="panel">
          <label className="label" htmlFor="admin-dev-link">
            Private development invitation
          </label>
          <textarea
            id="admin-dev-link"
            className="textarea"
            readOnly
            value={devLink}
          />
          <button className="button" onClick={() => setDevLink("")}>
            Hide link
          </button>
        </section>
      )}
      {err ? (
        <section className="panel" role="alert">
          <p>{err}</p>
          <button className="button" onClick={load}>
            Try again
          </button>
        </section>
      ) : loading ? (
        <section className="panel" role="status" aria-label="Loading users">
          <Skeleton className="h-12 mb-4" />
          <Skeleton className="h-20" />
        </section>
      ) : (
        <DataTable
          columns={[
            ...columns,
            {
              id: "invitation",
              header: "Invitation",
              cell: ({ row }: any) => (
                <>
                  <span>
                    {row.original.account_status ||
                      (row.original.is_active ? "active" : "inactive")}
                  </span>
                  {row.original.delivery_status && (
                    <div className="textSecondary">
                      Email: {row.original.delivery_status}
                    </div>
                  )}
                  {!row.original.is_active && (
                    <button
                      className="button"
                      disabled={busy}
                      onClick={() => resend(row.original.id)}
                    >
                      Resend invitation
                    </button>
                  )}
                </>
              ),
            },
          ]}
          data={rows}
          empty="No users found."
        />
      )}
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <h1>Invite Super Admin</h1>
            <button
              className="closeButton"
              aria-label="Close invitation"
              onClick={() => setOpen(false)}
            >
              ×
            </button>
          </div>
          <p>
            This person will have platform-wide administrative access. MFA is
            required before they can manage the platform.
          </p>
          <form onSubmit={invite}>
            <label className="label" htmlFor="platform-invite-name">
              Full name
            </label>
            <input
              id="platform-invite-name"
              className="field"
              name="full_name"
              minLength={2}
              maxLength={180}
              required
            />
            <label className="label" htmlFor="platform-invite-email">
              Gmail or business email
            </label>
            <input
              id="platform-invite-email"
              className="field"
              type="email"
              name="email"
              required
            />
            <p>
              The owner receives an expiring link and chooses their own
              password.
            </p>
            {err && (
              <p role="alert" className="dangerText">
                {err}
              </p>
            )}
            <button className="button primary" disabled={busy}>
              {busy ? "Queuing…" : "Send invitation"}
            </button>
          </form>
        </Drawer>
      )}
    </>
  );
}
