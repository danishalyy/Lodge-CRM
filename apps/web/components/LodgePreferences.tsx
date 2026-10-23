"use client";
import { useEffect, useState } from "react";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { getActiveLodgeId, lodgePreferencesApi } from "@/lib/api";
import { supportedCurrencies } from "@/lib/formatting";
import { contentCopy as copy } from "@/lib/strings/content";
import { Form } from "./ui/form";
import { Field } from "./ui/field";
export default function LodgePreferences() {
  const access = useWorkspaceAccess();
  const allowed =
    access.permission("lodge.settings.manage") && !!getActiveLodgeId();
  const [values, setValues] = useState<{
      date_format: string;
      currency: string;
    } | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (allowed)
      lodgePreferencesApi
        .get()
        .then(setValues)
        .catch((e) => setError(e.message));
  }, [allowed]);
  if (!allowed) return null;
  return (
    <section className="panel">
      <h2>{copy.preferences}</h2>
      <p>{copy.preferencesBody}</p>
      {error && (
        <p role="alert" className="dangerText">
          {error}
        </p>
      )}
      {values ? (
        <Form
          onSubmit={async (e) => {
            e.preventDefault();
            setError("");
            setBusy(true);
            try {
              setValues(
                await lodgePreferencesApi.update({
                  currency: values.currency,
                  date_format: values.date_format,
                }),
              );
            } catch (e) {
              setError(
                e instanceof Error
                  ? e.message
                  : "Unable to save lodge preferences.",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          <div className="formGrid">
            <Field label={copy.dateFormat}>
              <select
                className="select"
                name="date_format"
                value={values.date_format}
                onChange={(e) =>
                  setValues({ ...values, date_format: e.target.value })
                }
              >
                <option value="locale">{copy.browserDates}</option>
                {["dd/MM/yyyy", "MM/dd/yyyy", "yyyy-MM-dd"].map((format) => (
                  <option key={format} value={format}>
                    {format}
                  </option>
                ))}
              </select>
            </Field>
            <Field label={copy.currency}>
              <select
                className="select"
                name="currency"
                value={values.currency}
                onChange={(e) =>
                  setValues({ ...values, currency: e.target.value })
                }
              >
                {supportedCurrencies.map((currency) => (
                  <option key={currency} value={currency}>
                    {currency} ·{" "}
                    {new Intl.DisplayNames([navigator.language], {
                      type: "currency",
                    }).of(currency)}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <button className="button primary" disabled={busy}>
            {copy.savePreferences}
          </button>
        </Form>
      ) : (
        !error && <p role="status">Loading lodge preferences…</p>
      )}
    </section>
  );
}
