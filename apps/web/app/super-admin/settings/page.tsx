import EmailDeliverySettings from "@/components/EmailDeliverySettings";
import Link from "next/link";
export default function Page() {
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">SUPER ADMIN</span>
          <h1>Platform Settings</h1>
          <p>
            No placeholder configuration is exposed. Runtime secrets and
            infrastructure settings are managed through the deployment
            environment.
          </p>
        </div>
      </div>
      <section className="panel">
        <h2>Account security</h2>
        <p>
          Manage MFA for your signed-in Super Admin account from Account
          Security.
        </p>
        <Link className="button" href="/settings">
          Open Account Security
        </Link>
      </section>
      <section className="panel" style={{ marginTop: 12 }}>
        <h2>Deployment configuration</h2>
        <p>
          SMTP, object storage, HTTPS origins, database credentials and
          encryption keys are deployment settings and are intentionally not
          editable from the browser.
        </p>
      </section>
      <EmailDeliverySettings />
    </>
  );
}
