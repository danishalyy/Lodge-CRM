"use client";
import { useEffect, useState } from "react";
import { LockKeyhole } from "lucide-react";
import { featureAccessApi } from "@/lib/api";
import { moduleFeature, type ModuleKey } from "@/lib/modules";
import { accessCopy as copy } from "@/lib/strings/access";
import { Field } from "./ui/field";
import { Form } from "./ui/form";
export default function LockedFeature({ module }: { module: string }) {
  const feature = moduleFeature[module as ModuleKey];
  const [info, setInfo] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [sent, setSent] = useState(false);
  async function load() {
    if (!feature) return;
    try {
      setInfo(await featureAccessApi.info(feature));
      setError("");
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    setInfo(null);
    setSent(false);
    void load();
  }, [feature]);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!feature) return;
    setBusy(true);
    try {
      await featureAccessApi.review(
        feature,
        String(new FormData(e.currentTarget).get("reason") || ""),
      );
      setSent(true);
      setError("");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const title =
    info?.status === "coming_soon"
      ? copy.coming
      : info?.status === "plan_required" && info.unlocking_plans[0]
        ? copy.planRequired(info.unlocking_plans[0].name)
        : copy.unavailable;
  return (
    <section className="panel statePanel">
      <LockKeyhole aria-hidden="true" size={28} />
      <h1>{info ? title : copy.loading}</h1>
      {error && (
        <p role="alert" className="dangerText">
          {error}{" "}
          <button className="button" onClick={load}>
            {copy.retry}
          </button>
        </p>
      )}
      {info && (
        <>
          <h2>{info.feature.name}</h2>
          <p>{info.feature.description}</p>
          <p>{copy.reviewBody}</p>
          {sent ? (
            <p role="status">{copy.reviewSent}</p>
          ) : (
            <Form onSubmit={submit}>
              <Field label={copy.reason}>
                <textarea name="reason" maxLength={1000} />
              </Field>
              <button className="button primary" disabled={busy}>
                {copy.accessReview}
              </button>
            </Form>
          )}
        </>
      )}
    </section>
  );
}
