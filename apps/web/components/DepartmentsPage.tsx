"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import { operationsApi } from "@/lib/api";

type Department = {
  id: string;
  name: string;
  description: string;
  is_active: boolean;
};
export default function DepartmentsPage() {
  const [rows, setRows] = useState<Department[]>([]),
    [loading, setLoading] = useState(true),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await operationsApi.departments.list<Department[]>());
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
    try {
      await operationsApi.departments.create({
        name: String(f.get("name")),
        description: String(f.get("description") || ""),
      });
      setOpen(false);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  async function toggle(row: Department) {
    try {
      await operationsApi.departments.update(row.id, {
        is_active: !row.is_active,
      });
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">LODGE STRUCTURE</span>
          <h1>Departments</h1>
          <p>Give every team a clear place in your lodge’s daily operations.</p>
        </div>
        <button className="button primary" onClick={() => setOpen(true)}>
          + Department
        </button>
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <section className="panel">
        <div className="panelHeader">
          <div>
            <h2>Departments</h2>
            <p>{rows.length} configured</p>
          </div>
          <button className="button secondary" onClick={load}>
            Refresh
          </button>
        </div>
        {loading ? (
          <div className="empty">Loading…</div>
        ) : (
          <div className="tableWrap">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Description</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td>{r.description || "—"}</td>
                    <td>
                      <StatusPill value={r.is_active ? "Active" : "Inactive"} />
                    </td>
                    <td>
                      <button
                        className="button secondary"
                        onClick={() => toggle(r)}
                      >
                        {r.is_active ? "Deactivate" : "Activate"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!rows.length && (
              <div className="empty">No departments have been created yet.</div>
            )}
          </div>
        )}
      </section>
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <div>
              <h1>New department</h1>
              <div className="sub">Creates a real lodge department.</div>
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
            <Field label="Department name">
              <input className="field" name="name" required minLength={2} />
            </Field>
            <Field label="Description">
              <textarea className="textarea" name="description" />
            </Field>
            <div className="drawerActions">
              <button className="button primary">Create department</button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
