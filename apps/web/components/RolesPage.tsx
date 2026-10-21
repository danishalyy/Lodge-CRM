"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import { operationsApi } from "@/lib/api";
const bases = [
  ["department_manager", "Department Manager"],
  ["front_office", "Front Office"],
  ["ranger", "Ranger / Guide"],
  ["housekeeping", "Housekeeping"],
  ["maintenance", "Maintenance"],
  ["driver", "Driver"],
  ["fb", "F&B"],
  ["finance", "Finance"],
  ["general_staff", "General Staff"],
  ["read_only", "Read Only"],
];
export default function RolesPage() {
  const [roles, setRoles] = useState<any[]>([]),
    [perms, setPerms] = useState<any[]>([]),
    [selected, setSelected] = useState<string[]>([]),
    [error, setError] = useState("");
  const load = async () => {
    try {
      const [r, p] = await Promise.all([
        operationsApi.roles.list(),
        operationsApi.roles.permissions(),
      ]);
      setRoles(r);
      setPerms(p);
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
      await operationsApi.roles.create({
        name: String(f.get("name")),
        base_role_key: String(f.get("base_role_key")),
        description: String(f.get("description") || ""),
        permission_keys: selected,
      });
      setSelected([]);
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
          <span className="eyebrow">ACCESS CONTROL</span>
          <h1>Custom roles</h1>
          <p>
            Custom roles use a base operational scope and an explicit permission
            list. Backend authorization remains the source of truth.
          </p>
        </div>
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <div className="twoCol">
        <section className="card formCard">
          <h2>Create role</h2>
          <Form onSubmit={create}>
            <Field label="Role name">
              <input className="field" name="name" required />
            </Field>
            <Field label="Base operational scope">
              <select className="select" name="base_role_key">
                {bases.map(([k, n]) => (
                  <option key={k} value={k}>
                    {n}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Description">
              <textarea className="textarea" name="description" />
            </Field>
            <label className="label">Permissions</label>
            <div style={{ maxHeight: 360, overflow: "auto" }}>
              {perms.map((p) => (
                <label className="checkRow" key={p.key}>
                  <span>
                    <strong>{p.key}</strong>
                    <small>{p.description}</small>
                  </span>
                  <input
                    type="checkbox"
                    checked={selected.includes(p.key)}
                    onChange={(e) =>
                      setSelected(
                        e.target.checked
                          ? [...selected, p.key]
                          : selected.filter((x) => x !== p.key),
                      )
                    }
                  />
                </label>
              ))}
            </div>
            <button className="button primary">Create custom role</button>
          </Form>
        </section>
        <section className="panel">
          <h2>Configured roles</h2>
          {roles.map((r) => (
            <div className="taskRow" key={r.id}>
              <div>
                <strong>{r.name}</strong>
                <small>
                  Base: {r.base_role_name} · {r.permission_keys.length}{" "}
                  permissions
                </small>
                <p>{r.description}</p>
              </div>
              <span>{r.is_active ? "Active" : "Inactive"}</span>
            </div>
          ))}
          {!roles.length && (
            <div className="empty">No custom roles created.</div>
          )}
        </section>
      </div>
    </>
  );
}
