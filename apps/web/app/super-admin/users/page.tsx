"use client";
import { useEffect, useState } from "react";
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
    [loading, setLoading] = useState(true);
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
      </div>
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
        <DataTable columns={columns} data={rows} empty="No users found." />
      )}
    </>
  );
}
