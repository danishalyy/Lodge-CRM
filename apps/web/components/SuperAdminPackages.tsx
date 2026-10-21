"use client";
import { Field } from "@/components/ui/field";
import { useEffect, useMemo, useState } from "react";
import { superApi } from "@/lib/api";
export default function SuperAdminPackages() {
  const [plans, setPlans] = useState<any[]>([]),
    [lodges, setLodges] = useState<any[]>([]),
    [selected, setSelected] = useState(""),
    [ent, setEnt] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    Promise.all([superApi.plans(), superApi.lodges()])
      .then(([p, l]) => {
        setPlans(p);
        setLodges(l);
        if (l[0]) setSelected(l[0].id);
      })
      .catch((e: any) => setError(e.message));
  }, []);
  useEffect(() => {
    if (selected)
      superApi
        .lodgeEntitlements(selected)
        .then(setEnt)
        .catch((e: any) => setError(e.message));
  }, [selected]);
  const allFeatures = useMemo(
    () => Array.from(new Set(plans.flatMap((p: any) => p.features))).sort(),
    [plans],
  );
  async function toggle(feature: string) {
    if (!selected || !ent) return;
    const base = ent.base.includes(feature),
      effective = ent.effective.includes(feature);
    const next = !effective;
    await superApi.setEntitlement(
      selected,
      feature,
      next === base ? null : next,
    );
    setEnt(await superApi.lodgeEntitlements(selected));
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">SUPER ADMIN</span>
          <h1>Packages & entitlements</h1>
          <p>
            The plan definitions are server-backed. Lodge-specific overrides are
            audited and enforced by the API.
          </p>
        </div>
      </div>
      {error && <p className="dangerText">{error}</p>}
      <div className="packageCards">
        {plans.map((p: any) => (
          <section className="card packageCard" key={p.key}>
            <h3>{p.name}</h3>
            <p>{p.features.length} enabled server entitlements</p>
            <div className="featureList">
              {p.features.map((f: string) => (
                <span key={f}>✓ {f}</span>
              ))}
            </div>
          </section>
        ))}
      </div>
      <section className="panel" style={{ marginTop: 16 }}>
        <div className="panelHeader">
          <div>
            <h2>Lodge override</h2>
            <p>
              Enable or disable a feature for one lodge without changing its
              plan.
            </p>
          </div>
        </div>
        <Field label="Lodge">
          <select
            className="field"
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
          >
            {lodges.map((l: any) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </select>
        </Field>
        {ent && (
          <>
            <p>
              Package: <strong>{ent.package}</strong>
            </p>
            <div className="tableWrap">
              <table className="dataTable">
                <thead>
                  <tr>
                    <th>Feature</th>
                    <th>Plan default</th>
                    <th>Effective</th>
                    <th>Override</th>
                  </tr>
                </thead>
                <tbody>
                  {allFeatures.map((f: any) => {
                    const base = ent.base.includes(f),
                      effective = ent.effective.includes(f),
                      override = ent.overrides.find(
                        (x: any) => x.feature_key === f,
                      );
                    return (
                      <tr key={f}>
                        <td>{f}</td>
                        <td>{base ? "Enabled" : "Disabled"}</td>
                        <td>{effective ? "Enabled" : "Disabled"}</td>
                        <td>
                          <button
                            className="button secondary"
                            onClick={() => toggle(f)}
                          >
                            {override
                              ? `${override.enabled ? "Disable" : "Enable"} / reset via next change`
                              : effective
                                ? "Disable"
                                : "Enable"}
                          </button>
                          {override && (
                            <button
                              className="button secondary"
                              style={{ marginLeft: 6 }}
                              onClick={async () => {
                                await superApi.setEntitlement(
                                  selected,
                                  f,
                                  null,
                                );
                                setEnt(
                                  await superApi.lodgeEntitlements(selected),
                                );
                              }}
                            >
                              Reset
                            </button>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </>
  );
}
