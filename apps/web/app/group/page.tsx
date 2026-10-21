"use client";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { authApi, groupsApi, setActiveLodgeId } from "@/lib/api";
import { accountHome } from "@/lib/account-routing";
import SafariBrand from "@/components/SafariBrand";
import Drawer from "@/components/Drawer";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import ThemeToggle from "@/components/ThemeToggle";
import SignOutButton from "@/components/SignOutButton";
import AccountChangeGuard from "@/components/AccountChangeGuard";
export default function GroupOverview() {
  const router = useRouter();
  const requestSequence = useRef(0);
  const [me, setMe] = useState<any>(null),
    [selected, setSelected] = useState(""),
    [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true),
    [invite, setInvite] = useState<any>(null),
    [busy, setBusy] = useState(false),
    [link, setLink] = useState(""),
    [revoke, setRevoke] = useState<any>(null);
  useEffect(() => {
    let live = true;
    authApi
      .me()
      .then((u) => {
        if (live) {
          setMe(u);
          setSelected(u.groups?.[0]?.id || "");
          if (!u.groups?.length) setLoading(false);
        }
      })
      .catch(() => router.replace("/login"));
    return () => {
      live = false;
    };
  }, [router]);
  async function load(id: string) {
    const sequence = ++requestSequence.current;
    setLoading(true);
    setError("");
    try {
      const result = await groupsApi.overview(id);
      if (sequence === requestSequence.current) setData(result);
    } catch (e: any) {
      if (sequence === requestSequence.current) {
        setError(e.message);
        setData(null);
      }
    } finally {
      if (sequence === requestSequence.current) setLoading(false);
    }
  }
  useEffect(() => {
    if (selected) void load(selected);
  }, [selected]);
  async function send(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    const f = new FormData(e.currentTarget);
    try {
      const r = await groupsApi.inviteAdmin(invite.id, {
        email: String(f.get("email")),
        full_name: String(f.get("full_name")),
      });
      setLink(
        r.activation_token
          ? `${location.origin}/activate#token=${r.activation_token}`
          : "",
      );
      setInvite(null);
      await load(selected);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function adminAction(
    action: "resend" | "revoke" | "restore",
    lodge: string,
    id: string,
  ) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const result =
        action === "resend"
          ? await groupsApi.resendAdmin(lodge, id)
          : action === "revoke"
            ? await groupsApi.revokeAdmin(lodge, id)
            : await groupsApi.restoreAdmin(lodge, id);
      setLink(
        result.activation_token
          ? `${location.origin}/activate#token=${result.activation_token}`
          : "",
      );
      await load(selected);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (me && !me.groups?.length)
    return (
      <main className="content">
        <AccountChangeGuard />
        <h1>Access denied</h1>
        <p>This account is not a Group Admin.</p>
        <Link href="/settings">Account security</Link>
      </main>
    );
  return (
    <main className="groupPortfolio">
      <AccountChangeGuard />
      <header className="groupTopbar">
        <SafariBrand />
        <div className="topActions">
          <Link className="button" href="/settings">
            Account security
          </Link>
          <ThemeToggle />
          <SignOutButton />
        </div>
      </header>
      <div className="content">
        <div className="pageHeader">
          <div>
            <span className="eyebrow">GROUP ADMIN</span>
            <h1>{data?.name || "Your lodge group"}</h1>
            <p>
              One view of your assigned lodges. Access and features follow each
              lodge’s subscription.
            </p>
          </div>
          {me?.groups?.length > 1 && (
            <label>
              Active group
              <select
                className="select"
                value={selected}
                onChange={(e) => {
                  setData(null);
                  setSelected(e.target.value);
                }}
              >
                {me.groups.map((g: any) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {error && (
          <section className="panel dangerText" role="alert">
            <p>{error}</p>
            <button className="button" onClick={() => load(selected)}>
              Try again
            </button>
          </section>
        )}
        {link && (
          <section className="panel">
            <Field label="Private development invitation">
              <textarea
                id="group-invite-link"
                className="textarea"
                readOnly
                value={link}
              />
            </Field>
            <button className="button" onClick={() => setLink("")}>
              Hide link
            </button>
          </section>
        )}
        {loading ? (
          <section className="panel" role="status">
            Loading group overview…
          </section>
        ) : (
          data && (
            <>
              <div className="metricGrid">
                {Object.entries(data.totals).map(([key, value]) => (
                  <section className="metricCard" key={key}>
                    <span>{key.replaceAll("_", " ")}</span>
                    <strong>{String(value)}</strong>
                  </section>
                ))}
              </div>
              <p className="fieldHint">
                Totals include only the relevant enabled features in accessible
                lodges.
              </p>
              <div className="propertyGrid">
                {data.lodges.map((l: any) => (
                  <section key={l.id} className="propertyCard">
                    <h2>{l.name}</h2>
                    <p>{l.location || "Location not specified"}</p>
                    <p>
                      {l.package || "No package"} · {l.subscription_status}
                    </p>
                    {Object.entries(l.metrics).map(([key, value]) => (
                      <p key={key}>
                        {key.replaceAll("_", " ")}:{" "}
                        <strong>{String(value)}</strong>
                      </p>
                    ))}
                    {!!l.administrators?.length && (
                      <div className="groupAdministrators">
                        <h3>Lodge administrators</h3>
                        {l.administrators.map((admin: any) => (
                          <div key={admin.id} className="groupAdministrator">
                            <strong>{admin.name}</strong>
                            <p>{admin.email}</p>
                            <p className="fieldHint">
                              {admin.access_enabled
                                ? admin.account_status.replaceAll("_", " ")
                                : "Access removed"}
                            </p>
                            {["Active", "Expiring Soon"].includes(
                              l.subscription_status,
                            ) && (
                              <div className="notificationActions">
                                {!admin.access_enabled ? (
                                  <button
                                    className="button"
                                    disabled={busy}
                                    onClick={() =>
                                      adminAction("restore", l.id, admin.id)
                                    }
                                  >
                                    Restore access
                                  </button>
                                ) : (
                                  <>
                                    {admin.account_status !== "active" && (
                                      <button
                                        className="button"
                                        disabled={busy}
                                        onClick={() =>
                                          adminAction("resend", l.id, admin.id)
                                        }
                                      >
                                        Resend invitation
                                      </button>
                                    )}
                                    <button
                                      className="button"
                                      disabled={busy}
                                      onClick={() =>
                                        setRevoke({ lodge: l.id, admin })
                                      }
                                    >
                                      Remove access
                                    </button>
                                  </>
                                )}
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                    <div className="notificationActions">
                      <button
                        className="button primary"
                        onClick={() => {
                          const member = me.memberships.find(
                            (m: any) => m.lodge_id === l.id,
                          );
                          if (!member) return;
                          setActiveLodgeId(l.id);
                          router.push(
                            accountHome({
                              ...me,
                              groups: [],
                              memberships: [member],
                            }),
                          );
                        }}
                      >
                        Open lodge
                      </button>
                      {["Active", "Expiring Soon"].includes(
                        l.subscription_status,
                      ) && (
                        <button
                          className="button"
                          onClick={() => {
                            setError("");
                            setInvite(l);
                          }}
                        >
                          Invite Lodge Admin
                        </button>
                      )}
                    </div>
                  </section>
                ))}
              </div>
              {!data.lodges.length && (
                <section className="panel empty">
                  <h2>No lodges assigned yet</h2>
                  <p>Your Super Admin can assign lodges to this group.</p>
                </section>
              )}
            </>
          )
        )}
        <ConfirmDialog
          open={!!revoke}
          onOpenChange={(open) => {
            if (!open) setRevoke(null);
          }}
          title="Remove Lodge Admin access?"
          description="This administrator will be signed out and lose access to this lodge. Their invitations will be invalidated. You can restore access later."
          actionLabel="Remove access"
          onConfirm={() => {
            void adminAction("revoke", revoke.lodge, revoke.admin.id);
            setRevoke(null);
          }}
        />
        {invite && (
          <Drawer onClose={() => setInvite(null)}>
            <div className="drawerHead">
              <h1>Invite Lodge Admin</h1>
              <button
                className="closeButton"
                aria-label="Close invitation"
                onClick={() => setInvite(null)}
              >
                ×
              </button>
            </div>
            <p>
              Access is limited to {invite.name}. The owner chooses their own
              password.
            </p>
            <Form onSubmit={send}>
              <Field label="Full name">
                <input
                  id="lodge-admin-name"
                  name="full_name"
                  className="field"
                  minLength={2}
                  required
                />
              </Field>
              <Field label="Email">
                <input
                  id="lodge-admin-email"
                  name="email"
                  type="email"
                  className="field"
                  required
                />
              </Field>
              {error && (
                <p role="alert" className="dangerText">
                  {error}
                </p>
              )}
              <div className="drawerActions">
                <button className="button primary" disabled={busy}>
                  {busy ? "Queuing…" : "Send invitation"}
                </button>
              </div>
            </Form>
          </Drawer>
        )}
      </div>
    </main>
  );
}
