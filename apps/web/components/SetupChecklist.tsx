"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Circle } from "lucide-react";
import { lodgeApi, operationsApi } from "@/lib/api";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { onboardingCopy as copy } from "@/lib/strings/onboarding";
export default function SetupChecklist({
  onEmpty,
}: {
  onEmpty: (empty: boolean) => void;
}) {
  const access = useWorkspaceAccess();
  const steps = copy.steps.filter(
    (step) =>
      access.feature(step.feature) &&
      access.permission(step.permission) &&
      access.permission(step.manage),
  );
  const signature = steps.map((s) => s.key).join(",");
  const [counts, setCounts] = useState<Record<string, number> | null>(null),
    [error, setError] = useState(false),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    let live = true;
    setCounts(null);
    setError(false);
    const loaders: Record<string, () => Promise<any[]>> = {
      rooms: lodgeApi.rooms,
      guests: lodgeApi.guests,
      staff: operationsApi.staff.list,
      stays: operationsApi.stays.list,
    };
    Promise.all(
      steps.map(
        async (step) => [step.key, (await loaders[step.key]()).length] as const,
      ),
    )
      .then((entries) => {
        if (!live) return;
        const values = Object.fromEntries(entries);
        setCounts(values);
        onEmpty(
          entries.length > 0 && entries.every(([, count]) => count === 0),
        );
      })
      .catch(() => {
        if (live) {
          setError(true);
          onEmpty(false);
        }
      });
    return () => {
      live = false;
    };
    // The signature captures all permission/feature-dependent steps.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [signature, retry, onEmpty]);
  if (!steps.length) return null;
  if (error)
    return (
      <section className="panel">
        <p role="alert">{copy.retry}</p>
        <button className="button" onClick={() => setRetry((x) => x + 1)}>
          Retry
        </button>
      </section>
    );
  if (!counts)
    return (
      <section className="panel" role="status">
        Checking lodge setup…
      </section>
    );
  const done = steps.filter((step) => counts[step.key] > 0).length;
  if (done === steps.length) return null;
  const next = steps.find((step) => !counts[step.key]);
  return (
    <section className="panel setupChecklist">
      <h2>{copy.setupTitle}</h2>
      <p>{copy.setupBody}</p>
      <p>{copy.progress(done, steps.length)}</p>
      <progress
        value={done}
        max={steps.length}
        aria-label="Lodge setup progress"
      />
      <ul>
        {steps.map((step) => (
          <li key={step.key}>
            {counts[step.key] > 0 ? (
              <CheckCircle2 size={20} aria-label="Complete" />
            ) : (
              <Circle size={20} aria-label="To do" />
            )}
            <div>
              <strong>{step.label}</strong>
              <p>{step.description}</p>
            </div>
            {step === next ? (
              <Link className="button primary" href={"/" + step.key}>
                {step.label}
              </Link>
            ) : (
              <Link className="button" href={"/" + step.key}>
                Open
              </Link>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
