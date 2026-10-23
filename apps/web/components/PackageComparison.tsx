"use client";
import { accessCopy as copy } from "@/lib/strings/access";
export default function PackageComparison({ plans }: { plans: any[] }) {
  const features = plans[0]?.feature_catalog || [];
  if (!plans.length) return <p>{copy.loading}</p>;
  return (
    <div className="tableWrap">
      <table className="dataTable">
        <caption className="sr-only">{copy.compare}</caption>
        <thead>
          <tr>
            <th>{copy.features}</th>
            {plans.map((p) => (
              <th key={p.key}>{p.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {features.map((f: any) => (
            <tr key={f.key}>
              <th scope="row">
                <span className="eyebrow">{f.area}</span>
                <br />
                {f.name}
                <p className="muted">{f.description}</p>
              </th>
              {plans.map((p) => (
                <td key={p.key}>
                  {f.available ? (
                    p.features.includes(f.key) ? (
                      <span aria-label={copy.planIncludes}>✓</span>
                    ) : (
                      "—"
                    )
                  ) : p.planned_features?.includes(f.key) ? (
                    copy.coming
                  ) : (
                    "—"
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
