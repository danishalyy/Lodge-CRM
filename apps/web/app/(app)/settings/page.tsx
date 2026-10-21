"use client";

import Link from "next/link";
import { onboardingCopy as copy } from "@/lib/strings/onboarding";
import { Field } from "@/components/ui/field";
import { useEffect, useState } from "react";
import { authApi } from "@/lib/api";

type Account = { mfa_enabled: boolean; is_super_admin: boolean };
type Enrollment = { secret: string; otpauth_uri: string };

export default function Settings() {
  const [me, setMe] = useState<Account | null>(null);
  const [setup, setSetup] = useState<Enrollment | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    authApi
      .me()
      .then(setMe)
      .catch((e: Error) => setError(e.message));
  }, []);

  async function update(action: "setup" | "confirm" | "disable") {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      if (action === "setup") {
        setSetup(await authApi.mfaSetup());
      } else {
        if (action === "confirm") await authApi.mfaConfirm(code);
        else await authApi.mfaDisable(code, password);
        setSetup(null);
        setCode("");
        setMessage(
          action === "confirm"
            ? "Multi-factor authentication is enabled."
            : "Multi-factor authentication is disabled.",
        );
        setMe(await authApi.me());
      }
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to update security settings.",
      );
    } finally {
      setPassword("");
      setBusy(false);
    }
  }

  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">ACCOUNT SECURITY</span>
          <h1>Security settings</h1>
          <p>Protect your account with an authenticator app.</p>
        </div>
      </div>
      {me?.is_super_admin && (
        <section className="panel">
          <h2>{copy.securityTitle}</h2>
          <p>{copy.securityBody}</p>
          {me.mfa_enabled && (
            <Link className="button primary" href="/super-admin">
              {copy.openConsole}
            </Link>
          )}
        </section>
      )}
      <section className="panel" aria-busy={busy}>
        <h2>Multi-factor authentication</h2>
        <p>
          Status:{" "}
          <strong>
            {me ? (me.mfa_enabled ? "Enabled" : "Not enabled") : "Loading…"}
          </strong>
        </p>
        {me && !me.mfa_enabled && !setup && (
          <button
            className="button"
            disabled={busy}
            onClick={() => update("setup")}
          >
            Set up authenticator
          </button>
        )}
        {setup && (
          <>
            <p>
              Add this secret to your authenticator app, then enter its
              verification code.
            </p>
            <div className="checkRow">
              <span>Secret</span>
              <code>{setup.secret}</code>
            </div>
          </>
        )}
        {me?.is_super_admin && me.mfa_enabled && (
          <p>
            MFA is required for platform administrators and cannot be disabled.
          </p>
        )}
        {(setup || (me?.mfa_enabled && !me.is_super_admin)) && (
          <>
            <Field label="6-digit authenticator code">
              <input
                id="mfa-code"
                className="field"
                autoComplete="one-time-code"
                inputMode="numeric"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
              />
            </Field>
            {!setup && (
              <>
                <Field label="Current password">
                  <input
                    id="current-password"
                    className="field"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </Field>
              </>
            )}
            <button
              className="button primary"
              onClick={() => update(setup ? "confirm" : "disable")}
              disabled={busy || code.length !== 6 || (!setup && !password)}
            >
              {busy ? "Updating…" : setup ? "Confirm MFA" : "Disable MFA"}
            </button>
          </>
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
