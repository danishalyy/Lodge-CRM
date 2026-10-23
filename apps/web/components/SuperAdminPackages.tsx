"use client";
import { useEffect, useState } from "react";
import { superApi } from "@/lib/api";
import { accessCopy as copy } from "@/lib/strings/access";
import { Field } from "./ui/field";
import { Form } from "./ui/form";
import { ConfirmDialog } from "./ui/confirm-dialog";
import Drawer from "./Drawer";
import PackageComparison from "./PackageComparison";
export default function SuperAdminPackages() {
  const [plans, setPlans] = useState<any[]>([]),
    [lodges, setLodges] = useState<any[]>([]),
    [selected, setSelected] = useState(""),
    [ent, setEnt] = useState<any>(null),
    [error, setError] = useState(""),
    [draft, setDraft] = useState<any>(null),
    [exception, setException] = useState<any>(null),
    [confirm, setConfirm] = useState(false),
    [busy, setBusy] = useState(false);
  async function load() {
    try {
      const [p, l] = await Promise.all([superApi.plans(), superApi.lodges()]);
      setPlans(p);
      setLodges(l);
      setSelected((v) => v || l[0]?.id || "");
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    setEnt(null);
    if (selected) {
      let active = true;
      superApi
        .lodgeEntitlements(selected)
        .then((e) => {
          if (active) setEnt(e);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
      return () => {
        active = false;
      };
    }
  }, [selected]);
  async function savePlan() {
    setBusy(true);
    try {
      await superApi.updatePlan(draft.key, {
        features: draft.features,
        expected_revision: draft.revision,
        expected_lodge_count: draft.lodge_count,
      });
      setDraft(null);
      await load();
      if (selected) setEnt(await superApi.lodgeEntitlements(selected));
    } catch (e) {
      setError((e as Error).message);
      await load();
      setDraft(null);
    } finally {
      setBusy(false);
    }
  }
  async function saveException(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    try {
      const result = await superApi.setEntitlement(
        selected,
        exception.feature.key,
        exception.value === "default" ? null : exception.value === "yes",
        exception.reason,
      );
      setEnt(result);
      setException(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const features = plans[0]?.feature_catalog || [];
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">SUPER ADMIN</span>
          <h1>{copy.plans}</h1>
          <p>{copy.previewOnly}</p>
        </div>
      </div>
      {error && (
        <p role="alert" className="dangerText">
          {error}{" "}
          <button className="button secondary" onClick={load}>
            {copy.retry}
          </button>
        </p>
      )}
      <div className="packageCards">
        {plans.map((p) => (
          <section className="card packageCard" key={p.key}>
            <h2>{p.name}</h2>
            <p>{p.description}</p>
            <p>{copy.planImpact(p.lodge_count)}</p>
            <button
              className="button"
              disabled={busy}
              onClick={() => {
                setError("");
                setDraft({ ...p, features: [...p.features] });
              }}
            >
              {copy.editPlan}: {p.name}
            </button>
          </section>
        ))}
      </div>
      <section className="panel packageComparisonPanel">
        <div className="panelHeader">
          <h2>{copy.compare}</h2>
        </div>
        <PackageComparison plans={plans} />
      </section>
      <section className="panel packageExceptionsPanel">
        <div className="packageExceptionControls">
          <h2>{copy.exception}</h2>
          {lodges.length === 0 ? (
            <p>{copy.noLodges}</p>
          ) : (
            <Field label={copy.lodge}>
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                {lodges.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {selected && !ent && <p>{copy.loading}</p>}
        </div>
        {ent && (
          <div className="tableWrap">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>{copy.features}</th>
                  <th>{copy.planIncludes}</th>
                  <th>{copy.exception}</th>
                  <th>{copy.finalResult}</th>
                </tr>
              </thead>
              <tbody>
                {features.map((f: any) => {
                  const override = ent.overrides.find(
                    (o: any) => o.feature_key === f.key,
                  );
                  return (
                    <tr key={f.key}>
                      <th scope="row">
                        {f.name}
                        <p className="muted">{f.description}</p>
                      </th>
                      <td>
                        {!f.available
                          ? copy.coming
                          : ent.base.includes(f.key)
                            ? copy.included
                            : copy.excluded}
                      </td>
                      <td>
                        <button
                          className="button secondary"
                          onClick={() => {
                            setError("");
                            setException({
                              feature: f,
                              value: override
                                ? override.enabled
                                  ? "yes"
                                  : "no"
                                : "default",
                              reason: "",
                            });
                          }}
                        >
                          {override
                            ? override.enabled
                              ? copy.enable
                              : copy.disable
                            : copy.defaultResult}
                        </button>
                        {override?.reason && <p>{override.reason}</p>}
                      </td>
                      <td>
                        {!f.available
                          ? copy.coming
                          : ent.effective.includes(f.key)
                            ? copy.enabled
                            : copy.disabled}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {draft && (
        <Drawer onClose={() => !busy && setDraft(null)}>
          <Form
            onSubmit={(e) => {
              e.preventDefault();
              setConfirm(true);
            }}
          >
            <div className="drawerHead">
              <h2>
                {copy.editPlan}: {draft.name}
              </h2>
              <button
                type="button"
                className="closeButton"
                aria-label={copy.close}
                onClick={() => setDraft(null)}
              >
                ×
              </button>
            </div>
            <p>{copy.planImpact(draft.lodge_count)}</p>
            {features.map((f: any) => (
              <div className="formField" key={f.key}>
                <label className="fieldLabel">
                  <input
                    type="checkbox"
                    disabled={!f.available || busy}
                    checked={f.available && draft.features.includes(f.key)}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        features: e.target.checked
                          ? [...draft.features, f.key]
                          : draft.features.filter(
                              (key: string) => key !== f.key,
                            ),
                      })
                    }
                  />
                  {f.name} {!f.available && ` · ${copy.coming}`}
                </label>
                <p className="fieldHint">{f.description}</p>
              </div>
            ))}
            <div className="drawerActions">
              <button className="button primary" disabled={busy}>
                {copy.planSave}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
      {exception && (
        <Drawer onClose={() => !busy && setException(null)}>
          <Form onSubmit={saveException}>
            <div className="drawerHead">
              <h2>
                {copy.exception}: {exception.feature.name}
              </h2>
              <button
                type="button"
                className="closeButton"
                aria-label={copy.close}
                onClick={() => setException(null)}
              >
                ×
              </button>
            </div>
            {error && (
              <p className="dangerText" role="alert">
                {error}
              </p>
            )}
            <Field label={copy.exception}>
              <select
                value={exception.value}
                onChange={(e) =>
                  setException({ ...exception, value: e.target.value })
                }
              >
                <option value="default">{copy.reset}</option>
                {exception.feature.available && (
                  <option value="yes">{copy.enable}</option>
                )}
                <option value="no">{copy.disable}</option>
              </select>
            </Field>
            <Field label={copy.reason} helper={copy.reasonRequired}>
              <textarea
                name="reason"
                required
                minLength={5}
                maxLength={1000}
                value={exception.reason}
                onChange={(e) =>
                  setException({ ...exception, reason: e.target.value })
                }
              />
            </Field>
            <div className="drawerActions">
              <button className="button primary" disabled={busy}>
                {copy.saveException}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={copy.planSave}
        description={copy.planImpact(draft?.lodge_count || 0)}
        actionLabel={copy.planSave}
        onConfirm={savePlan}
      />
    </>
  );
}
