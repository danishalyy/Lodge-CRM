"use client";
import { uiCopy as c } from "@/lib/strings/redesign";
import { CodeInput } from "@/components/ui/code-input";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { securityCopy as security } from "@/lib/strings/security";
import Link from "next/link";
import { PasswordField } from "@/components/ui/password-field";
import ThemeToggle from "@/components/ThemeToggle";
import { accountHome } from "@/lib/account-routing";
import SafariBrand from "@/components/SafariBrand";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, setActiveLodgeId } from "@/lib/api";
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [recovery, setRecovery] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState("");
  const [needsOtp, setNeedsOtp] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await authApi.login(
        email,
        password,
        needsOtp && !recovery ? otp : undefined,
        needsOtp && recovery ? recoveryCode : undefined,
      );
      const me = await authApi.me();
      if (me.memberships?.[0]) setActiveLodgeId(me.memberships[0].lodge_id);
      router.replace(accountHome(me));
    } catch (e: any) {
      if (e.message === "MFA_REQUIRED") {
        setNeedsOtp(true);
        setError("Enter the 6-digit code from your authenticator app.");
      } else setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="authShell">
      <div className="authTheme">
        <ThemeToggle />
      </div>
      <section className="authStory">
        <div className="authStoryInner">
          <SafariBrand />
          <div className="authStatement">
            <span className="eyebrow">{c.loginLabel}</span>
            <h1>
              {c.loginHeadline} <em>{c.loginAccent}</em>
            </h1>
            <p>{c.loginSupport}</p>
          </div>
          <svg
            className="authHorizon"
            viewBox="0 0 600 100"
            fill="none"
            aria-hidden="true"
          >
            <path
              d="M0 75Q250 38 600 75M0 90Q250 58 600 90M400 22Q438-8 475 22M438 15V50"
              stroke="currentColor"
              strokeWidth="1"
            />
          </svg>
        </div>
      </section>
      <section className="authFormSide">
        <Form className="panel authCard" onSubmit={submit}>
          <span className="eyebrow">SECURE ACCESS</span>
          <h1>{c.loginTitle}</h1>
          <p>{c.loginIntro}</p>
          <Field label="Email">
            <input
              id="login-email"
              className="field"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              placeholder="you@lodge.com"
            />
          </Field>
          <PasswordField
            label="Password"
            rules
            id="login-password"
            required
            minLength={12}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
          {needsOtp && (
            <>
              {recovery ? (
                <Field
                  label={security.recoveryLabel}
                  helper={security.recoveryHint}
                >
                  <input
                    className="field"
                    name="recovery_code"
                    required
                    minLength={20}
                    maxLength={40}
                    autoComplete="off"
                    value={recoveryCode}
                    onChange={(e) => setRecoveryCode(e.target.value)}
                  />
                </Field>
              ) : (
                <Field label="Authenticator code">
                  <CodeInput
                    id="login-code"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                    required
                  />
                </Field>
              )}
              <button
                type="button"
                className="button"
                onClick={() => {
                  setRecovery(!recovery);
                  setError("");
                  setOtp("");
                  setRecoveryCode("");
                }}
              >
                {recovery ? security.useAuthenticator : security.useRecovery}
              </button>
            </>
          )}
          {error && (
            <div className="authError" role="alert">
              {error}
            </div>
          )}
          <button className="button primary full authSubmit" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
          <div className="authLinks">
            <Link href="/forgot-password">Forgot password?</Link>
            <span>SafariOS · Secure access</span>
          </div>
        </Form>
      </section>
    </main>
  );
}
