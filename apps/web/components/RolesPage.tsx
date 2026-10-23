"use client";
import { useEffect, useState } from "react";
import { operationsApi } from "@/lib/api";
import { accessCopy as copy } from "@/lib/strings/access";
import Drawer from "./Drawer";
import { Field } from "./ui/field";
import { Form } from "./ui/form";
import { ConfirmDialog } from "./ui/confirm-dialog";
export default function RolesPage() {
  const [catalog, setCatalog] = useState<any>(null),
    [roles, setRoles] = useState<any[]>([]),
    [draft, setDraft] = useState<any>(null),
    [advanced, setAdvanced] = useState(false),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [pending, setPending] = useState<any>(null);
  async function load() {
    try {
      setError("");
      const [c, r] = await Promise.all([
        operationsApi.roles.catalog(),
        operationsApi.roles.list(),
      ]);
      setCatalog(c);
      setRoles(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : copy.error);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  function duplicate(role: any, preset = false) {
    const allowed = new Set(
      catalog.permissions
        .filter((p: any) => p.can_grant)
        .map((p: any) => p.key),
    );
    setDraft({
      name: `${role.name} copy`,
      description: role.description,
      base_role_key: preset ? role.copy_base_role_key : role.base_role_key,
      permission_keys: (preset
        ? role.copy_permission_keys
        : role.permission_keys
      ).filter((k: string) => allowed.has(k)),
    });
    setAdvanced(false);
  }
  const groups: any[] = catalog
    ? Object.values(
        catalog.permissions.reduce((groups: any, p: any) => {
          (groups[p.area] ??= {
            key: p.area,
            name: p.area_name,
            permissions: [],
          }).permissions.push(p);
          return groups;
        }, {}),
      )
    : [];
  function level(group: any) {
    const keys = draft?.permission_keys || [];
    const selected = group.permissions.filter((p: any) => keys.includes(p.key));
    if (!selected.length) return "none";
    const view = group.permissions.filter(
        (p: any) => p.level === "view" && p.can_grant,
      ),
      edit = group.permissions.filter(
        (p: any) => p.level !== "advanced" && p.can_grant,
      );
    const matches = (ps: any[]) =>
      ps.length === selected.length && ps.every((p) => keys.includes(p.key));
    return matches(view) ? "view" : matches(edit) ? "edit" : "advanced";
  }
  function setLevel(group: any, value: string) {
    setDraft({
      ...draft,
      permission_keys: [
        ...draft.permission_keys.filter(
          (key: string) => !group.permissions.some((p: any) => p.key === key),
        ),
        ...group.permissions
          .filter(
            (p: any) =>
              p.can_grant &&
              (value === "view"
                ? p.level === "view"
                : value === "edit"
                  ? p.level !== "advanced"
                  : false),
          )
          .map((p: any) => p.key),
      ],
    });
  }
  async function persist(value: any) {
    if (busy) return;
    setBusy(true);
    try {
      if (value.id)
        await operationsApi.roles.update(
          value.id,
          value.deactivating
            ? { is_active: false }
            : value.reactivating
              ? { is_active: true }
              : {
                  name: value.name,
                  description: value.description,
                  permission_keys: value.permission_keys,
                },
        );
      else await operationsApi.roles.create(value);
      setDraft(null);
      setPending(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : copy.saveError);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <h1>{copy.title}</h1>
          <p>{copy.intro}</p>
        </div>
      </div>
      {error && (
        <div className="panel" role="alert">
          <p className="dangerText">{error}</p>
          <button className="button" onClick={load}>
            {copy.retry}
          </button>
        </div>
      )}
      {!catalog && !error && <p role="status">{copy.loading}</p>}
      {catalog && (
        <>
          <h2>{copy.presets}</h2>
          <div className="accessRoleGrid">
            {catalog.presets.map((role: any) => (
              <section className="panel" key={role.key}>
                <span className="eyebrow">{copy.locked}</span>
                <h3>{role.name}</h3>
                <p>{role.description}</p>
                <small>{role.permission_keys.length} actions</small>
                <div className="drawerActions">
                  <button
                    className="button"
                    onClick={() => duplicate(role, true)}
                  >
                    {copy.duplicate}
                  </button>
                </div>
              </section>
            ))}
          </div>
          <h2>{copy.custom}</h2>
          {!roles.length && (
            <section className="panel empty">{copy.empty}</section>
          )}
          {roles.map((role) => (
            <section className="panel roleRow" key={role.id}>
              <div>
                <h3>{role.name}</h3>
                <p>{role.description}</p>
                <p>
                  {copy.count(role.staff_count || 0)} ·{" "}
                  {role.is_active ? copy.active : copy.inactive}
                </p>
              </div>
              <div className="headerActions">
                <button
                  className="button"
                  onClick={() => {
                    setDraft({ ...role });
                    setAdvanced(false);
                  }}
                >
                  {copy.edit}
                </button>
                <button className="button" onClick={() => duplicate(role)}>
                  {copy.duplicate}
                </button>
                <button
                  className="button"
                  disabled={busy}
                  onClick={() =>
                    setPending({
                      ...role,
                      deactivating: role.is_active,
                      reactivating: !role.is_active,
                    })
                  }
                >
                  {role.is_active ? copy.deactivate : copy.restore}
                </button>
              </div>
            </section>
          ))}
        </>
      )}
      {draft && catalog && (
        <Drawer onClose={() => !busy && setDraft(null)}>
          <div className="drawerHead">
            <h2>{draft.id ? copy.edit : copy.create}</h2>
            <button
              className="closeButton"
              aria-label="Close role editor"
              onClick={() => setDraft(null)}
              disabled={busy}
            >
              ×
            </button>
          </div>
          <Form
            onSubmit={(e) => {
              e.preventDefault();
              if (draft.id) setPending(draft);
              else void persist(draft);
            }}
          >
            <Field label={copy.name}>
              <input
                className="field"
                name="name"
                required
                minLength={2}
                maxLength={120}
                value={draft.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
            </Field>
            <Field label={copy.description}>
              <textarea
                className="textarea"
                name="description"
                maxLength={2000}
                value={draft.description}
                onChange={(e) =>
                  setDraft({ ...draft, description: e.target.value })
                }
              />
            </Field>
            <Field
              label={copy.scope}
              helper={
                catalog.scopes.find((s: any) => s.key === draft.base_role_key)
                  ?.description || copy.scopeHint
              }
            >
              <select
                className="select"
                name="base_role_key"
                disabled={!!draft.id}
                value={draft.base_role_key}
                onChange={(e) => {
                  const preset = catalog.presets.find(
                    (p: any) => p.key === e.target.value,
                  );
                  setDraft({
                    ...draft,
                    base_role_key: e.target.value,
                    permission_keys: preset?.copy_permission_keys || [],
                  });
                }}
              >
                {catalog.scopes.map((scope: any) => (
                  <option key={scope.key} value={scope.key}>
                    {scope.label}
                  </option>
                ))}
              </select>
            </Field>
            <label className="checkRow">
              <input
                type="checkbox"
                checked={advanced}
                onChange={(e) => setAdvanced(e.target.checked)}
              />
              {copy.advanced}
            </label>
            {groups.map((group) => (
              <section className="accessArea" key={group.key}>
                {advanced ? (
                  <>
                    <h3>{group.name}</h3>
                    {group.permissions.map((permission: any) => (
                      <label className="checkRow" key={permission.key}>
                        <span>
                          {permission.label}
                          {!permission.can_grant && (
                            <small>{copy.blocked}</small>
                          )}
                          <small>{permission.key}</small>
                        </span>
                        <input
                          type="checkbox"
                          disabled={!permission.can_grant}
                          checked={draft.permission_keys.includes(
                            permission.key,
                          )}
                          onChange={(e) =>
                            setDraft({
                              ...draft,
                              permission_keys: e.target.checked
                                ? [...draft.permission_keys, permission.key]
                                : draft.permission_keys.filter(
                                    (key: string) => key !== permission.key,
                                  ),
                            })
                          }
                        />
                      </label>
                    ))}
                  </>
                ) : (
                  <Field label={group.name}>
                    <select
                      className="select"
                      value={level(group)}
                      onChange={(e) => setLevel(group, e.target.value)}
                    >
                      <option value="none">{copy.no}</option>
                      <option
                        value="view"
                        disabled={
                          !group.permissions.some(
                            (p: any) => p.can_grant && p.level === "view",
                          )
                        }
                      >
                        {copy.view}
                      </option>
                      <option
                        value="edit"
                        disabled={
                          !group.permissions.some(
                            (p: any) => p.can_grant && p.level === "edit",
                          )
                        }
                      >
                        {copy.editAccess}
                      </option>
                      {level(group) === "advanced" && (
                        <option value="advanced">{copy.customAccess}</option>
                      )}
                    </select>
                  </Field>
                )}
              </section>
            ))}
            <section className="roleSummary" aria-live="polite">
              <h3>{copy.summary}</h3>
              {groups.map((group) => (
                <p key={group.key}>
                  {copy.permissionSummary(group.name, level(group))}
                </p>
              ))}
            </section>
            {error && (
              <p className="dangerText" role="alert">
                {error}
              </p>
            )}
            <div className="drawerActions">
              <button className="button primary" disabled={busy}>
                {draft.id ? copy.save : copy.create}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
      <ConfirmDialog
        open={!!pending}
        onOpenChange={(open) => {
          if (!open) setPending(null);
        }}
        title={pending?.deactivating ? copy.deactivate : copy.save}
        description={`${copy.impact(pending?.staff_count || 0)} ${pending?.deactivating ? copy.deactivateHint : ""}`}
        actionLabel={pending?.deactivating ? copy.deactivate : copy.save}
        onConfirm={() => {
          if (pending) void persist(pending);
        }}
      />
    </>
  );
}
