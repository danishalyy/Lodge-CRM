"use client";
import { useEffect, useState } from "react";
import { superApi } from "@/lib/api";
export default function SuperAdminSubscriptions() {
  const [plans, setPlans] = useState<any[]>([]);
  const [rows, setRows] = useState<any[]>([]),
    [alerts, setAlerts] = useState<any[]>([]),
    [drafts, setDrafts] = useState<Record<string, any>>({}),
    [error, setError] = useState("");
  const load = async () => {
    try {
      const [r, a, p] = await Promise.all([
        superApi.lodges(),
        superApi.platformNotifications(),
        superApi.plans(),
      ]);
      setRows(r);
      setPlans(p);
      setAlerts(a.filter((x: any) => x.type === "subscription.expiry"));
      setDrafts(
        Object.fromEntries(
          r.map((x: any) => [
            x.id,
            {
              package: x.subscription?.package || p[0]?.key || "",
              start_date: x.subscription?.start_date || "",
              expiry_date: x.subscription?.expiry_date || "",
              suspended: !!x.subscription?.suspended,
            },
          ]),
        ),
      );
    } catch (e: any) {
      setError(e.message);
    }
  };
  useEffect(() => {
    load();
  }, []);
  async function save(id: string) {
    try {
      await superApi.updateSubscription(id, drafts[id]);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">PLATFORM</span>
          <h1>Subscriptions</h1>
          <p>Manage packages, access dates and renewals.</p>
        </div>
      </div>
      {error && <p className="dangerText">{error}</p>}
      {alerts.length > 0 && (
        <section className="panel" style={{ marginBottom: 12 }}>
          <h2>Expiry alerts</h2>
          {alerts.map((a: any) => (
            <div className="row" key={a.id}>
              <div>
                <strong>{a.title}</strong>
                <div style={{ color: "var(--tx3)", fontSize: 12 }}>
                  {a.body}
                </div>
              </div>
              <span className="tag">{a.severity}</span>
            </div>
          ))}
        </section>
      )}
      <section className="panel">
        <div className="tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>Lodge</th>
                <th>Package</th>
                <th>Start</th>
                <th>Expiry</th>
                <th>Suspended</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const d = drafts[r.id] || {};
                return (
                  <tr key={r.id}>
                    <td>
                      {r.name}
                      <div style={{ color: "var(--tx3)", fontSize: 12 }}>
                        {r.subscription_status}
                      </div>
                    </td>
                    <td>
                      <select
                        className="field"
                        value={d.package || plans[0]?.key || ""}
                        onChange={(e) =>
                          setDrafts((x) => ({
                            ...x,
                            [r.id]: { ...d, package: e.target.value },
                          }))
                        }
                        aria-label="Package"
                      >
                        {plans.map((plan) => (
                          <option key={plan.key} value={plan.key}>
                            {plan.name}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <input
                        className="field"
                        type="date"
                        value={d.start_date || ""}
                        onChange={(e) =>
                          setDrafts((x) => ({
                            ...x,
                            [r.id]: { ...d, start_date: e.target.value },
                          }))
                        }
                        aria-label="Start date"
                      />
                    </td>
                    <td>
                      <input
                        className="field"
                        type="date"
                        value={d.expiry_date || ""}
                        onChange={(e) =>
                          setDrafts((x) => ({
                            ...x,
                            [r.id]: { ...d, expiry_date: e.target.value },
                          }))
                        }
                        aria-label="Expiry date"
                      />
                    </td>
                    <td>
                      <input
                        type="checkbox"
                        checked={!!d.suspended}
                        onChange={(e) =>
                          setDrafts((x) => ({
                            ...x,
                            [r.id]: { ...d, suspended: e.target.checked },
                          }))
                        }
                        aria-label="Suspend subscription"
                      />
                    </td>
                    <td>
                      <button className="button" onClick={() => save(r.id)}>
                        Save
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!rows.length && (
          <p style={{ color: "var(--tx3)" }}>No subscriptions yet.</p>
        )}
      </section>
    </>
  );
}
