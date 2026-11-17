"use client";
import { useState, useEffect } from "react";
import { CodeInput } from "./ui/code-input";
import { Field } from "./ui/field";
import { emailSignInCopy as c } from "@/lib/strings/email-sign-in";

export type EmailProof = {
  email_challenge?: string;
  email_code?: string;
  resend?: boolean;
};
type Challenge = {
  challenge_token: string;
  masked_email: string;
  expires_in: number;
  resend_after: number;
};
export function useEmailSignIn() {
  const [challenge, setChallenge] = useState<Challenge | null>(null),
    [code, setCode] = useState(""),
    [now, setNow] = useState(0),
    [issued, setIssued] = useState(0),
    [resending, setResending] = useState(false);
  useEffect(() => {
    if (!challenge) return;
    const clock = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(clock);
    };
  }, [challenge?.challenge_token]);
  return {
    challenge,
    resending,
    setResending,
    code,
    setCode,
    reset: () => {
      setChallenge(null);
      setResending(false);
      setCode("");
    },
    accept: (result: any) => {
      if (result?.status !== "email_otp_required") return false;
      setChallenge(result);
      setCode("");
      const time = Date.now();
      setIssued(time);
      setNow(time);
      return true;
    },
    proof: (resend = false): EmailProof =>
      challenge
        ? {
            email_challenge: challenge.challenge_token,
            email_code: resend ? undefined : code || undefined,
            resend,
          }
        : {},
    expires: challenge
      ? Math.max(0, challenge.expires_in - Math.floor((now - issued) / 1000))
      : 0,
    wait: challenge
      ? Math.max(0, challenge.resend_after - Math.floor((now - issued) / 1000))
      : 0,
  };
}
export function EmailOtpFields({
  flow,
  busy,
  onResend,
  onReset,
}: {
  flow: ReturnType<typeof useEmailSignIn>;
  busy: boolean;
  onResend: () => void;
  onReset: () => void;
}) {
  if (!flow.challenge) return null;
  return (
    <section className="emailSignInStep" aria-label={c.title}>
      <h2>{c.title}</h2>
      <p role="status">{c.sent(flow.challenge.masked_email)}</p>
      <Field label={c.code} helper={c.hint}>
        <CodeInput
          key={flow.challenge.challenge_token}
          autoFocus
          name="email_code"
          value={flow.code}
          required
          disabled={busy || !flow.expires}
          onChange={(e) => flow.setCode(e.target.value.replace(/\D/g, ""))}
        />
      </Field>
      <p className="fieldHint" role={flow.expires ? "status" : "alert"}>
        {flow.expires ? c.expires(flow.expires) : c.expired}
      </p>
      <div className="emailSignInActions">
        <button
          type="button"
          className="button secondary"
          disabled={busy || flow.wait > 0}
          onClick={onResend}
        >
          {flow.resending
            ? c.resending
            : flow.wait
              ? c.wait(flow.wait)
              : c.resend}
        </button>
        <button
          type="button"
          className="linkButton"
          disabled={busy}
          onClick={onReset}
        >
          {c.another}
        </button>
      </div>
    </section>
  );
}
