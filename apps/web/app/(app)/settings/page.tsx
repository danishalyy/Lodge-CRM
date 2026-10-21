"use client";
import LodgePreferences from "@/components/LodgePreferences";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Form } from "@/components/ui/form";
import { Field } from "@/components/ui/field";
import { PasswordField } from "@/components/ui/password-field";
import AuthenticatorQR from "@/components/AuthenticatorQR";
import { authApi } from "@/lib/api";
import { onboardingCopy } from "@/lib/strings/onboarding";
import { securityCopy as copy } from "@/lib/strings/security";
type Account = { mfa_enabled: boolean; is_super_admin: boolean };
type Enrollment = { secret: string; otpauth_uri: string };
export default function Settings() {
  const [me, setMe] = useState<Account | null>(null),
    [setup, setSetup] = useState<Enrollment | null>(null),
    [code, setCode] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [codes, setCodes] = useState<string[]>([]),
    [regenerating, setRegenerating] = useState(false);
  useEffect(() => {
    authApi
      .me()
      .then(setMe)
      .catch((e) => setError(e.message));
  }, []);
  async function update(
    action: "setup" | "confirm" | "disable" | "regenerate",
  ) {
    if (busy) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (action === "setup") setSetup(await authApi.mfaSetup());
      else {
        const result =
          action === "confirm"
            ? await authApi.mfaConfirm(code)
            : action === "regenerate"
              ? await authApi.mfaRegenerate(code, password)
              : await authApi.mfaDisable(code, password);
        setCodes(result.recovery_codes || []);
        setSetup(null);
        setRegenerating(false);
        setCode("");
        setMessage(
          action === "confirm"
            ? copy.enabledMessage
            : action === "regenerate"
              ? copy.regenerated
              : copy.disabledMessage,
        );
        setMe(await authApi.me());
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : copy.updateError);
    } finally {
      setPassword("");
      setBusy(false);
    }
  }
  function download() {
    const url = URL.createObjectURL(
      new Blob(
        [
          `SafariOS MFA recovery codes\n\n${copy.recoveryBody}\n\n${codes.join("\n")}\n`,
        ],
        { type: "text/plain" },
      ),
    );
    const a = document.createElement("a");
    a.href = url;
    a.download = "safarios-recovery-codes.txt";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">ACCOUNT SECURITY</span>
          <h1>{copy.title}</h1>
          <p>{copy.subtitle}</p>
        </div>
      </div>
      {me?.is_super_admin && (
        <section className="panel">
          <h2>{onboardingCopy.securityTitle}</h2>
          <p>{me.mfa_enabled ? copy.protected : onboardingCopy.securityBody}</p>
          {me.mfa_enabled && (
            <Link href="/super-admin" className="button primary">
              {onboardingCopy.openConsole}
            </Link>
          )}
        </section>
      )}
      <LodgePreferences />
      <section className="panel" aria-busy={busy}>
        <h2>{copy.mfa}</h2>
        <p>
          <strong>
            {me
              ? me.mfa_enabled
                ? copy.enabled
                : copy.disabled
              : copy.loading}
          </strong>
        </p>
        {me && !me.mfa_enabled && !setup && (
          <button
            className="button primary"
            disabled={busy}
            onClick={() => update("setup")}
          >
            {copy.setup}
          </button>
        )}
        {setup && (
          <>
            <p>{copy.scan}</p>
            <AuthenticatorQR uri={setup.otpauth_uri} />
            <div className="checkRow">
              <span>{copy.secret}</span>
              <code className="manualSecret">{setup.secret}</code>
            </div>
          </>
        )}
        {codes.length > 0 && (
          <section className="recoveryCodes">
            <h2>{copy.recoveryTitle}</h2>
            <p>{copy.recoveryBody}</p>
            <ul>
              {codes.map((value) => (
                <li key={value}>
                  <code>{value}</code>
                </li>
              ))}
            </ul>
            <div className="drawerActions">
              <button className="button primary" onClick={download}>
                {copy.download}
              </button>
              <button className="button" onClick={() => setCodes([])}>
                {copy.saved}
              </button>
            </div>
          </section>
        )}
        {me?.mfa_enabled && !setup && !codes.length && !regenerating && (
          <button
            className="button"
            onClick={() => {
              setRegenerating(true);
              setCode("");
              setPassword("");
            }}
          >
            {copy.regenerate}
          </button>
        )}
        {regenerating && <p>{copy.regenerateBody}</p>}
        {me?.is_super_admin && me.mfa_enabled && <p>{copy.mandatory}</p>}
        {(setup ||
          regenerating ||
          (me?.mfa_enabled && !me.is_super_admin && !codes.length)) && (
          <Form
            onSubmit={(e) => {
              e.preventDefault();
              void update(
                setup ? "confirm" : regenerating ? "regenerate" : "disable",
              );
            }}
          >
            <Field label={copy.code}>
              <input
                className="field"
                name="code"
                autoComplete="one-time-code"
                inputMode="numeric"
                pattern="[0-9]{6}"
                minLength={6}
                maxLength={6}
                required
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              />
            </Field>
            {!setup && (
              <PasswordField
                label={copy.password}
                name="current_password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
            <button className="button primary" disabled={busy}>
              {busy
                ? copy.updating
                : setup
                  ? copy.confirm
                  : regenerating
                    ? copy.regenerate
                    : copy.disable}
            </button>
          </Form>
        )}
        {message && <p role="status">{message}</p>}
        {error && (
          <p role="alert" className="dangerText">
            {error}
          </p>
        )}
      </section>
    </>
  );
}
