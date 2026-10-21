"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import { groupsApi, superApi } from "@/lib/api";
import Drawer from "@/components/Drawer";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
export default function Groups() {
  const [groups, setGroups] = useState<any[]>([]),
    [lodges, setLodges] = useState<any[]>([]),
    [edit, setEdit] = useState<any>(null),
    [selected, setSelected] = useState<string[]>([]),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [link, setLink] = useState(""),
    [confirm, setConfirm] = useState<any>(null);
  async function load() {
    try {
      const [g, l] = await Promise.all([groupsApi.list(), superApi.lodges()]);
      setGroups(g);
      setLodges(l);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function save(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    const f = new FormData(e.currentTarget);
    try {
      const body = { name: String(f.get("name")), lodge_ids: selected };
      const result = edit.id
        ? await groupsApi.update(edit.id, {
            ...body,
            is_active: edit.is_active,
          })
        : await groupsApi.create({
            ...body,
            admin_name: String(f.get("admin_name")),
            admin_email: String(f.get("admin_email")),
          });
      setLink(
        result.activation_token
          ? `${location.origin}/activate#token=${result.activation_token}`
          : "",
      );
      setEdit(null);
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function toggle(g: any) {
    try {
      await groupsApi.update(g.id, {
        name: g.name,
        lodge_ids: g.lodge_ids,
        is_active: !g.is_active,
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
          <span className="eyebrow">MULTI-LODGE OWNERSHIP</span>
          <h1>Lodge groups</h1>
          <p>
            Assign a Group Admin and their lodges. Each lodge retains its own
            subscription, features and staff accounts.
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            setEdit({ is_active: true });
            setSelected([]);
          }}
        >
          Create group
        </button>
      </div>
      {error && (
        <p className="panel dangerText" role="alert">
          {error}
        </p>
      )}
      {link && (
        <section className="panel">
          <Field label="Private development invitation">
            <textarea
              id="group-dev-link"
              className="textarea"
              readOnly
              value={link}
            />
          </Field>
          <button className="button" onClick={() => setLink("")}>
            Hide link
          </button>
        </section>
      )}
      {loading ? (
        <p role="status">Loading groups…</p>
      ) : !groups.length ? (
        <section className="panel empty">
          <h2>No lodge groups yet</h2>
          <p>Create a group for an owner with multiple lodges.</p>
        </section>
      ) : (
        <div className="propertyGrid">
          {groups.map((g) => (
            <section className="panel" key={g.id}>
              <h2>{g.name}</h2>
              <p>
                {g.administrator.name}
                <br />
                {g.administrator.email}
              </p>
              <p>
                {g.lodge_ids.length} lodges ·{" "}
                {g.is_active ? "Active" : "Suspended"} ·{" "}
                {g.administrator.account_status.replaceAll("_", " ")}
              </p>
              <div className="notificationActions">
                <button
                  className="button"
                  onClick={() => {
                    setEdit(g);
                    setSelected(g.lodge_ids);
                  }}
                >
                  Manage group
                </button>
                {g.is_active ? (
                  <button className="button" onClick={() => setConfirm(g)}>
                    Suspend
                  </button>
                ) : (
                  <button className="button" onClick={() => toggle(g)}>
                    Restore access
                  </button>
                )}
                {g.is_active && g.administrator.account_status !== "active" && (
                  <button
                    className="button"
                    onClick={async () => {
                      try {
                        const r = await superApi.resendInvitation(
                          g.administrator.id,
                        );
                        setLink(
                          r.activation_token
                            ? `${location.origin}/activate#token=${r.activation_token}`
                            : "",
                        );
                      } catch (e: any) {
                        setError(e.message);
                      }
                    }}
                  >
                    Resend invitation
                  </button>
                )}
              </div>
            </section>
          ))}
        </div>
      )}
      <ConfirmDialog
        open={!!confirm}
        onOpenChange={(open) => {
          if (!open) setConfirm(null);
        }}
        title="Suspend group access?"
        description="The Group Admin loses access to this group’s lodges. Lodge Admins and staff keep their own accounts."
        actionLabel="Suspend group"
        onConfirm={() => {
          void toggle(confirm);
          setConfirm(null);
        }}
      />
      {edit && (
        <Drawer onClose={() => setEdit(null)}>
          <div className="drawerHead">
            <h1>{edit.id ? "Manage group" : "Create lodge group"}</h1>
            <button
              className="closeButton"
              aria-label="Close group form"
              onClick={() => setEdit(null)}
            >
              ×
            </button>
          </div>
          <Form onSubmit={save}>
            <Field label="Group name">
              <input
                id="group-name"
                className="field"
                name="name"
                required
                minLength={2}
                maxLength={180}
                defaultValue={edit.name || ""}
              />
            </Field>
            {!edit.id && (
              <>
                <Field label="Group Admin name">
                  <input
                    id="group-admin-name"
                    name="admin_name"
                    className="field"
                    minLength={2}
                    maxLength={180}
                    required
                  />
                </Field>
                <Field label="Group Admin email">
                  <input
                    id="group-admin-email"
                    name="admin_email"
                    className="field"
                    type="email"
                    required
                  />
                </Field>
                <p className="fieldHint">
                  The owner sets their own password through an invitation. Use a
                  separate email from any Lodge Admin or staff account.
                </p>
              </>
            )}
            <h2>Assigned lodges</h2>
            <p className="fieldHint">
              Only selected lodges are accessible. Assignments do not change
              lodge subscriptions.
            </p>
            {lodges
              .filter(
                (l) =>
                  !groups.some(
                    (g) => g.id !== edit.id && g.lodge_ids.includes(l.id),
                  ),
              )
              .map((l) => (
                <label className="checkRow" key={l.id}>
                  <span>{l.name}</span>
                  <input
                    type="checkbox"
                    checked={selected.includes(l.id)}
                    onChange={(e) =>
                      setSelected(
                        e.target.checked
                          ? [...selected, l.id]
                          : selected.filter((id) => id !== l.id),
                      )
                    }
                  />
                </label>
              ))}
            {error && (
              <p role="alert" className="dangerText">
                {error}
              </p>
            )}
            <div className="drawerActions">
              <button className="button primary" disabled={busy}>
                {busy
                  ? "Saving…"
                  : edit.id
                    ? "Save group"
                    : "Create group and invite"}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
