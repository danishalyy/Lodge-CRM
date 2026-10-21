"use client";
import Link from "next/link";
import { FormEvent, useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { authApi, setActiveLodgeId } from "@/lib/api";
import { accountHome, takeAccountLinkToken } from "@/lib/account-routing";
import SafariBrand from "@/components/SafariBrand";
import { Skeleton } from "@/components/ui/skeleton";
type Invite = {
  name: string;
  email_hint: string;
  workspace: string;
  expires_at: string;
};
export default function Activate() {
  const linkToken = useRef<string | null>(null);
  const router = useRouter();
  const [token, setToken] = useState(""),
    [invite, setInvite] = useState<Invite | null>(null),
    [loading, setLoading] = useState(true),
    [password, setPassword] = useState(""),
    [confirm, setConfirm] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    const value = linkToken.current ?? takeAccountLinkToken();
    linkToken.current = value;
    setToken(value);
    if (!value) {
      setError(
        "This invitation link is incomplete. Open the link in your email, or ask your administrator to send a new invitation.",
      );
      setLoading(false);
      return;
    }
    authApi
      .previewInvitation(value)
      .then((result) => {
        if (active) setInvite(result);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!invite || !token || busy) return;
    if (password !== confirm) {
      setError("Your passwords do not match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await authApi.activate(token, password);
      const me = await authApi.me();
      if (me.memberships?.[0]) setActiveLodgeId(me.memberships[0].lodge_id);
      router.replace(accountHome(me));
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Unable to activate your account.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="accountLinkPage">
      <section className="panel accountLinkCard">
        <SafariBrand />
        <span className="eyebrow">YOUR PRIVATE ACCOUNT</span>
        <h1>Set your password</h1>
        {loading ? (
          <div role="status" aria-label="Checking invitation">
            <Skeleton className="h-12 mb-4" />
            <Skeleton className="h-24" />
          </div>
        ) : invite ? (
          <>
            <p>
              Hello {invite.name}. You’ve been invited to{" "}
              <strong>{invite.workspace}</strong>.
            </p>
            <p className="textSecondary">
              Invitation for {invite.email_hint}. Choose your own SafariOS
              password. Your administrator cannot see it.
            </p>
            <form onSubmit={submit}>
              <label className="fieldLabel" htmlFor="activation-password">
                New password
              </label>
              <input
                id="activation-password"
                className="field"
                type="password"
                minLength={12}
                maxLength={200}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                aria-describedby="password-guidance"
              />
              <p id="password-guidance" className="fieldHint">
                Use at least 12 characters. A unique passphrase is a good
                choice.
              </p>
              <label className="fieldLabel" htmlFor="activation-confirm">
                Confirm password
              </label>
              <input
                id="activation-confirm"
                className="field"
                type="password"
                minLength={12}
                maxLength={200}
                required
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
                aria-invalid={!!confirm && confirm !== password}
              />
              {error && (
                <p className="dangerText" role="alert">
                  {error}
                </p>
              )}
              <button className="button primary full" disabled={busy}>
                {busy ? "Setting up your account…" : "Activate my account"}
              </button>
              <p className="fieldHint">
                One-time invitation · expires{" "}
                {new Date(invite.expires_at).toLocaleString()}. Activating signs
                this browser into your invited account.
              </p>
            </form>
          </>
        ) : (
          <>
            <p className="dangerText" role="alert">
              {error}
            </p>
            <p>
              Ask the person who invited you to resend the invitation. If your
              account is already active, sign in or reset your password.
            </p>
          </>
        )}
        <div className="accountLinkFooter">
          <Link href="/login">Back to sign in</Link>
          <Link href="/forgot-password">Forgot password?</Link>
        </div>
      </section>
    </main>
  );
}
