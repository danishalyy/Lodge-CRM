"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { authApi } from "@/lib/api";
export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const r: any = await authApi.requestPasswordReset(email);
      setMsg(
        r.message || "If the account exists, a reset email has been sent.",
      );
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
        <span className="eyebrow">ACCOUNT RECOVERY</span>
        <h1>Reset password</h1>
        <p>Enter the email address used for your Lodge CRM account.</p>
        <Field label="Email">
          <input
            className="field"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </Field>
        {msg && <p>{msg}</p>}
        {err && <p className="dangerText">{err}</p>}
        <button className="button primary full" disabled={busy}>
          {busy ? "Sending…" : "Send reset link"}
        </button>
        <p>
          <Link href="/login">Back to sign in</Link>
        </p>
      </Form>
    </main>
  );
}
