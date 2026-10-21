"use client";
import { PasswordField } from "@/components/ui/password-field";

import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, Suspense, useRef, useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { authApi } from "@/lib/api";
import { takeAccountLinkToken } from "@/lib/account-routing";
import SafariBrand from "@/components/SafariBrand";

function ResetPasswordForm() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const linkToken = useRef<string | null>(null);
  useEffect(() => {
    linkToken.current ??= takeAccountLinkToken();
    setToken(linkToken.current);
  }, []);
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    if (pw !== pw2) {
      setErr("Passwords do not match");
      return;
    }
    setBusy(true);
    try {
      await authApi.confirmPasswordReset(token, pw);
      router.replace("/login");
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 24,
      }}
    >
      <Form
        className="panel"
        onSubmit={submit}
        style={{ width: "min(430px,100%)" }}
      >
        <SafariBrand />
        <span className="eyebrow">SECURE PASSWORD RESET</span>
        <h1>Choose a new password</h1>
        <p>
          After updating your password, sign in again with your authenticator if
          MFA is enabled.
        </p>
        {!token && <p className="dangerText">Reset token is missing.</p>}
        <PasswordField
          label="New password"
          rules
          id="reset-password"
          required
          minLength={12}
          maxLength={200}
          value={pw}
          onChange={(e) => setPw(e.target.value)}
          autoComplete="new-password"
        />
        <PasswordField
          label="Confirm password"
          rules
          id="reset-confirm"
          required
          minLength={12}
          maxLength={200}
          value={pw2}
          onChange={(e) => setPw2(e.target.value)}
          autoComplete="new-password"
        />
        {err && (
          <p role="alert" className="dangerText">
            {err}
          </p>
        )}
        <button className="button primary full" disabled={busy || !token}>
          {busy ? "Updating…" : "Update password"}
        </button>
      </Form>
    </main>
  );
}

export default function ResetPassword() {
  return (
    <Suspense
      fallback={
        <main
          style={{
            minHeight: "100vh",
            display: "grid",
            placeItems: "center",
            padding: 24,
          }}
        >
          <div className="panel">Loading secure reset form…</div>
        </main>
      }
    >
      <ResetPasswordForm />
    </Suspense>
  );
}
