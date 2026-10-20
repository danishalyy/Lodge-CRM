"use client";
import Link from "next/link";
import ThemeToggle from "@/components/ThemeToggle";
import SafariBrand from "@/components/SafariBrand";
import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { authApi, setActiveLodgeId } from "@/lib/api";
export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [otp, setOtp] = useState("");
  const [needsOtp, setNeedsOtp] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await authApi.login(email, password, needsOtp ? otp : undefined);
      const me = await authApi.me();
      if (me.memberships?.[0]) setActiveLodgeId(me.memberships[0].lodge_id);
      router.replace(
        me.is_super_admin && !me.memberships?.length
          ? "/super-admin"
          : "/dashboard",
      );
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
            <span className="eyebrow">THOUGHTFULLY CONNECTED</span>
            <h1>Exceptional stays. Effortless operations.</h1>
            <p>
              One considered workspace for your people, your property, and every
              detail of the guest experience.
            </p>
          </div>
          <div className="authSignals">
            <div>
              <i className="statusDot" />
              <span>Operational command centre</span>
            </div>
            <div>
              <i className="statusDot" />
              <span>Role-aware access</span>
            </div>
            <div>
              <i className="statusDot" />
              <span>Offline-ready workflows</span>
            </div>
          </div>
          <small className="authFoot">
            SafariOS · Built around the rhythm of your lodge.
          </small>
        </div>
      </section>
      <section className="authFormSide">
        <form className="panel authCard" onSubmit={submit}>
          <span className="eyebrow">SECURE ACCESS</span>
          <h1>Your lodge. Connected.</h1>
          <p>Welcome back. Sign in to your SafariOS workspace.</p>
          <label className="fieldLabel" htmlFor="login-email">
            Email
          </label>
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
          <label className="fieldLabel" htmlFor="login-password">
            Password
          </label>
          <input
            id="login-password"
            className="field"
            type="password"
            required
            minLength={10}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            placeholder="••••••••••"
          />
          {needsOtp && (
            <>
              <label className="fieldLabel" htmlFor="login-code">
                Authenticator code
              </label>
              <input
                id="login-code"
                className="field otpField"
                inputMode="numeric"
                pattern="[0-9]{6}"
                maxLength={6}
                required
                value={otp}
                onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                autoComplete="one-time-code"
                placeholder="000000"
              />
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
        </form>
      </section>
    </main>
  );
}
