"use client";
import { useEffect, useState } from "react";
import { superApi } from "@/lib/api";
export default function EmailDeliverySettings() {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(""),
    [notice, setNotice] = useState("");
  async function load() {
    try {
      setData(await superApi.emailStatus());
      setError("");
    } catch (e: any) {
      setError(e.message);
    }
  }
  useEffect(() => {
    void load();
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 15000);
    return () => clearInterval(timer);
  }, []);
  async function act(id?: string) {
    setBusy(id || "test");
    try {
      if (id) await superApi.retryEmail(id);
      else await superApi.testEmail();
      setNotice(
        id
          ? "Delivery queued for retry."
          : "Test queued to your own account email. Check the delivery status below.",
      );
      await load();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setBusy("");
    }
  }
  return (
    <section className="panel emailDeliveryPanel">
      <div className="sectionHeader">
        <div>
          <span className="eyebrow">GMAIL & BUSINESS EMAIL</span>
          <h2>Email delivery</h2>
        </div>
        <button className="button" onClick={load}>
          Refresh
        </button>
      </div>
      <p>
        Invitations, password recovery and operational alerts use the configured
        SMTP sender. Credentials stay on the server.
      </p>
      {error && (
        <p role="alert" className="dangerText">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      {!data ? (
        <p role="status">Loading sender status…</p>
      ) : (
        <>
          <p>
            <strong>
              {data.configured ? "Sender configured" : "Sender not configured"}
            </strong>{" "}
            · {data.provider || "SMTP"}
            {data.sender ? ` · ${data.sender}` : ""}
          </p>
          <p className="textSecondary">
            Encrypted transport:{" "}
            {data.encrypted_transport ? "enabled" : "not enabled"} · Outbox
            encryption:{" "}
            {data.outbox_encryption_configured
              ? "configured"
              : "not configured"}
          </p>
          <button
            className="button primary"
            disabled={!!busy || !data.configured}
            onClick={() => act()}
          >
            {busy === "test" ? "Queuing…" : "Send test to my email"}
          </button>
          <p className="fieldHint">
            “Sent” means the mail server accepted the email. Delivery to an
            inbox depends on the provider.
          </p>
          <div className="tableWrap">
            <table className="dataTable">
              <thead>
                <tr>
                  <th>Recipient</th>
                  <th>Purpose</th>
                  <th>Status</th>
                  <th>Attempts</th>
                  <th>Details</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {(data.account_deliveries || []).map((r: any) => (
                  <tr key={r.id}>
                    <td>{r.destination}</td>
                    <td>{r.kind}</td>
                    <td>{r.status}</td>
                    <td>{r.attempts}</td>
                    <td>{r.last_error || "—"}</td>
                    <td>
                      {["failed", "dead"].includes(r.status) && (
                        <button
                          className="button"
                          disabled={!!busy}
                          onClick={() => act(r.id)}
                        >
                          Retry
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!data.account_deliveries?.length && (
              <p className="empty">No account emails have been queued yet.</p>
            )}
          </div>
        </>
      )}
    </section>
  );
}
