"use client";
import { contentCopy as copy, readableLabel } from "@/lib/strings/content";
import { TimezonePicker } from "@/components/ui/timezone-picker";
import { dateInputValue, formatDate } from "@/lib/formatting";

import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import { API_URL, setActiveLodgeId, superApi } from "@/lib/api";
import Drawer from "./Drawer";
import PackageComparison from "./PackageComparison";
import { accessCopy } from "@/lib/strings/access";
import { ConfirmDialog } from "./ui/confirm-dialog";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
const brandingSchema = z.object({
  display_name: z
    .string()
    .trim()
    .min(1, "Enter a workspace name.")
    .max(180, "Use 180 characters or fewer."),
});
import UiIcon from "./UiIcon";
import StatusPill from "./StatusPill";
type Lodge = {
  id: string;
  name: string;
  location: string;
  administrator?: {
    id: string;
    email: string;
    account_status: string;
    delivery_status?: string;
  };
  subscription_status: string;
  subscription?: { package: string; expiry_date: string };
  branding?: { display_name: string; logo_url: string | null };
};

async function logoData(file: File | null) {
  if (!file || !file.size) return undefined;
  if (file.size > 256 * 1024)
    throw new Error("Choose a logo smaller than 256 KB.");
  if (!["image/png", "image/jpeg", "image/webp"].includes(file.type))
    throw new Error("Use a PNG, JPEG or WebP logo.");
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",")[1]);
    reader.onerror = () => reject(new Error("Unable to read this logo."));
    reader.readAsDataURL(file);
  });
}
function LodgeLogo({ lodge }: { lodge: Lodge }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [lodge.branding?.logo_url]);
  return (
    <div className="propertyLogo">
      {lodge.branding?.logo_url && !failed ? (
        <img
          src={`${API_URL}${lodge.branding.logo_url}`}
          alt={`${lodge.branding.display_name} logo`}
          onError={() => setFailed(true)}
        />
      ) : (
        <span>
          {lodge.name
            .split(" ")
            .map((w) => w[0])
            .join("")
            .slice(0, 2)}
        </span>
      )}
    </div>
  );
}
function LogoField({
  preview,
  onChange,
}: {
  preview: string;
  onChange: (file: File | null) => void;
}) {
  return (
    <div className="logoUpload">
      <div className="logoPreview">
        {preview ? (
          <img src={preview} alt="Lodge logo preview" />
        ) : (
          <UiIcon name="lodge" />
        )}
      </div>
      <div>
        <Field label="Lodge logo">
          <input
            id="lodge-logo"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => onChange(e.target.files?.[0] || null)}
          />
        </Field>
        <p className="fieldHint">
          PNG, JPEG or WebP · up to 256 KB. SafariOS branding stays visible.
        </p>
      </div>
    </div>
  );
}

export default function SuperAdminLodges() {
  const [selectedPackage, setSelectedPackage] = useState("");
  const [plans, setPlans] = useState<any[]>([]);
  const [pendingRemoval, setPendingRemoval] = useState<z.infer<
    typeof brandingSchema
  > | null>(null);
  const brandForm = useForm<z.infer<typeof brandingSchema>>({
    resolver: zodResolver(brandingSchema),
    mode: "onBlur",
  });
  const [rows, setRows] = useState<Lodge[]>([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [open, setOpen] = useState(false),
    [branding, setBranding] = useState<Lodge | null>(null),
    [activation, setActivation] = useState(""),
    [busy, setBusy] = useState(false),
    [search, setSearch] = useState(""),
    [notice, setNotice] = useState("");
  const [file, setFile] = useState<File | null>(null),
    [preview, setPreview] = useState(""),
    [removeLogo, setRemoveLogo] = useState(false);
  const load = async () => {
    setLoading(true);
    try {
      const [lodges, packages] = await Promise.all([
        superApi.lodges(),
        superApi.plans(),
      ]);
      setRows(lodges);
      setPlans(packages);
      setSelectedPackage((value) => value || packages[0]?.key || "");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to load lodges.");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function choose(file: File | null) {
    setFile(file);
    setRemoveLogo(false);
  }
  function close() {
    if (busy) return;
    setOpen(false);
    setBranding(null);
    setFile(null);
    setError("");
  }
  function edit(lodge: Lodge) {
    setError("");
    setFile(null);
    setRemoveLogo(false);
    brandForm.reset({
      display_name: lodge.branding?.display_name || lodge.name,
    });
    setBranding(lodge);
  }
  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    setNotice("");
    let created = false;
    try {
      const logo = await logoData(file);
      const result = await superApi.createLodge({
        name: String(f.get("name")),
        location: String(f.get("location")),
        timezone: String(f.get("timezone")),
        package: String(f.get("package")),
        start_date: String(f.get("start_date")),
        expiry_date: String(f.get("expiry_date")),
        admin_email: String(f.get("admin_email")),
        admin_name: String(f.get("admin_name")),
      });
      created = true;
      if (result.activation_token)
        setActivation(
          `${location.origin}/activate#token=${encodeURIComponent(result.activation_token)}`,
        );
      if (logo)
        await superApi.updateBranding(result.id, {
          display_name: String(f.get("name")),
          logo_base64: logo,
        });
      setNotice(
        "Lodge registered. The administrator must activate their account using the invitation link.",
      );
      setOpen(false);
      setFile(null);
    } catch (e) {
      setError(
        (created
          ? "Lodge was created. Update its logo using Manage branding. "
          : "") + (e instanceof Error ? e.message : "Registration failed."),
      );
      if (created) {
        setOpen(false);
        setFile(null);
      }
    } finally {
      setBusy(false);
      await load();
    }
  }
  async function saveBranding(values: z.infer<typeof brandingSchema>) {
    if (!branding) return;
    setBusy(true);
    setError("");
    try {
      const logo = await logoData(file);
      await superApi.updateBranding(branding.id, {
        display_name: values.display_name,
        logo_base64: logo,
        remove_logo: removeLogo,
      });
      setNotice(`Branding updated for ${branding.name}.`);

      setBranding(null);
      setFile(null);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save branding.");
    } finally {
      setBusy(false);
    }
  }
  const visible = rows.filter((r) =>
    `${r.name} ${r.location} ${r.branding?.display_name || ""}`
      .toLowerCase()
      .includes(search.toLowerCase()),
  );
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">YOUR PORTFOLIO</span>
          <h1>Lodges</h1>
          <p>Distinct identities. One SafariOS platform.</p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            setOpen(true);
            setError("");
            setFile(null);
          }}
        >
          + Register lodge
        </button>
      </div>
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {error && !open && !branding && (
        <p className="dangerText" role="alert">
          {error}
        </p>
      )}
      {activation && (
        <section className="panel activationPanel">
          <div>
            <span className="eyebrow">NEXT STEP</span>
            <h2>Invite your lodge administrator</h2>
            <p>
              Share this private activation link securely. It expires in 72
              hours.
            </p>
          </div>
          <input
            aria-label="Lodge administrator activation link"
            className="field"
            readOnly
            value={activation}
          />
          <div className="headerActions">
            <button
              className="button"
              onClick={() =>
                navigator.clipboard
                  .writeText(activation)
                  .then(() => setNotice("Activation link copied."))
                  .catch(() => setNotice("Copy the link from the field above."))
              }
            >
              Copy link
            </button>
            <button
              className="button secondary"
              onClick={() => setActivation("")}
            >
              Dismiss
            </button>
          </div>
        </section>
      )}
      <div className="collectionToolbar">
        <div>
          <strong>
            {rows.length} {rows.length === 1 ? "property" : "properties"}
          </strong>
          <span>Registered on SafariOS</span>
        </div>
        <label className="searchField">
          <UiIcon name="search" />
          <input
            type="search"
            aria-label="Search lodges"
            placeholder="Search properties…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>
      {loading ? (
        <section className="panel empty" role="status">
          Loading your properties…
        </section>
      ) : !visible.length ? (
        <section className="panel propertyEmpty">
          <UiIcon name="lodge" />
          <h2>
            {search ? "No matching lodges" : "Your first lodge starts here"}
          </h2>
          <p>
            {search
              ? "Try a different name or location."
              : "Register a lodge, set its subscription, and make the workspace its own."}
          </p>
          {!search && (
            <button className="button primary" onClick={() => setOpen(true)}>
              Register your first lodge
            </button>
          )}
        </section>
      ) : (
        <div className="propertyGrid">
          {visible.map((lodge) => (
            <article className="propertyCard" key={lodge.id}>
              <div className="propertyCardTop">
                <LodgeLogo lodge={lodge} />
                <StatusPill value={lodge.subscription_status} />
              </div>
              <h2>{lodge.branding?.display_name || lodge.name}</h2>
              <p className="propertyLocation">
                {lodge.location || "Location not specified"}
              </p>
              <dl className="propertyDetails">
                <div>
                  <dt>Subscription</dt>
                  <dd>{lodge.subscription?.package || "Not configured"}</dd>
                </div>
                <div>
                  <dt>Valid until</dt>
                  <dd>
                    {lodge.subscription?.expiry_date
                      ? formatDate(lodge.subscription.expiry_date)
                      : "—"}
                  </dd>
                </div>
              </dl>
              {lodge.administrator && (
                <div className="propertyAdmin">
                  <p className="textSecondary">
                    {lodge.administrator.email}
                    <br />
                    Account: {readableLabel(lodge.administrator.account_status)}
                    {lodge.administrator.delivery_status
                      ? ` · Email: ${readableLabel(lodge.administrator.delivery_status)}`
                      : ""}
                  </p>
                  {lodge.administrator.account_status !== "active" && (
                    <button
                      className="button"
                      onClick={async () => {
                        try {
                          const r = await superApi.resendInvitation(
                            lodge.administrator!.id,
                          );
                          if (r.activation_token)
                            setActivation(
                              `${location.origin}/activate#token=${r.activation_token}`,
                            );

                          await load();
                        } catch (e: any) {
                          setError(e.message);
                        }
                      }}
                    >
                      Resend administrator invitation
                    </button>
                  )}
                </div>
              )}
              <div className="propertyProvider">
                Powered by <strong>SafariOS</strong>
              </div>
              <div className="propertyActions">
                <button
                  className="button secondary"
                  onClick={() => edit(lodge)}
                >
                  Manage branding
                </button>
                <button
                  className="button"
                  onClick={() => {
                    setActiveLodgeId(lodge.id);
                    localStorage.setItem("active_lodge_name", lodge.name);
                    location.href = "/dashboard";
                  }}
                >
                  Open lodge <UiIcon name="arrow" />
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      {open && (
        <Drawer onClose={close}>
          <div className="drawerHead">
            <div>
              <span className="eyebrow">NEW PROPERTY</span>
              <h1>Welcome a lodge</h1>
              <p>Set its identity, subscription and administrator.</p>
            </div>
            <button
              className="closeButton"
              aria-label="Close registration"
              disabled={busy}
              onClick={close}
            >
              <UiIcon name="close" />
            </button>
          </div>
          <Form onSubmit={add}>
            <section className="formSection">
              <h2>01 / Property identity</h2>
              <Field label="Lodge name">
                <input
                  id="property-name"
                  className="field"
                  name="name"
                  required
                  maxLength={180}
                  placeholder="e.g. Acacia River Lodge"
                />
              </Field>
              <div className="formGrid">
                <div>
                  <Field label="Location">
                    <input
                      id="property-location"
                      className="field"
                      name="location"
                      placeholder="Region, country"
                    />
                  </Field>
                </div>
                <div>
                  <Field label="Time zone">
                    <TimezonePicker
                      id="property-timezone"
                      className="field"
                      name="timezone"
                      required
                      defaultValue={
                        Intl.DateTimeFormat().resolvedOptions().timeZone
                      }
                    />
                  </Field>
                </div>
              </div>
              <LogoField preview={preview} onChange={choose} />
            </section>
            <section className="formSection">
              <h2>02 / Subscription</h2>
              <Field label="Package">
                <select
                  id="property-package"
                  className="field"
                  name="package"
                  value={selectedPackage}
                  onChange={(e) => setSelectedPackage(e.target.value)}
                >
                  {plans.map((plan) => (
                    <option key={plan.key} value={plan.key}>
                      {plan.name} — {plan.description}
                    </option>
                  ))}
                </select>
              </Field>
              <p className="fieldHint" aria-live="polite">
                {
                  plans.find((plan) => plan.key === selectedPackage)
                    ?.description
                }
              </p>
              <details>
                <summary>{accessCopy.compare}</summary>
                <PackageComparison plans={plans} />
              </details>
              <div className="formGrid">
                <div>
                  <Field label="Start date">
                    <input
                      id="property-start"
                      className="field"
                      name="start_date"
                      defaultValue={dateInputValue()}
                      type="date"
                      required
                    />
                  </Field>
                </div>
                <div>
                  <Field label="Expiry date">
                    <input
                      id="property-expiry"
                      className="field"
                      name="expiry_date"
                      defaultValue={dateInputValue(
                        new Date(
                          new Date().setFullYear(new Date().getFullYear() + 1),
                        ),
                      )}
                      type="date"
                      required
                    />
                  </Field>
                </div>
              </div>
              <p className="fieldHint">
                Payment is collected outside SafariOS. You control subscription
                access.
              </p>
            </section>
            <section className="formSection">
              <h2>03 / Lodge administrator</h2>
              <Field label="Full name">
                <input
                  id="admin-name"
                  className="field"
                  name="admin_name"
                  required
                />
              </Field>
              <Field label="Email address">
                <input
                  id="admin-email"
                  className="field"
                  name="admin_email"
                  type="email"
                  required
                />
              </Field>
              <p className="fieldHint">
                Use a separate account from your Super Admin login.
              </p>
            </section>
            {error && (
              <p role="alert" className="dangerText">
                {error}
              </p>
            )}
            <div className="drawerActions">
              <button
                className="button secondary"
                type="button"
                disabled={busy}
                onClick={close}
              >
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                {busy ? "Registering…" : "Register lodge"}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
      <ConfirmDialog
        open={!!pendingRemoval}
        onOpenChange={(open) => {
          if (!open) setPendingRemoval(null);
        }}
        title="Remove this lodge logo?"
        description="The workspace will show lodge initials until a new logo is uploaded. SafariOS branding stays visible."
        onConfirm={() => {
          if (pendingRemoval) void saveBranding(pendingRemoval);
        }}
      />
      {branding && (
        <Drawer onClose={close}>
          <div className="drawerHead">
            <div>
              <span className="eyebrow">PROPERTY IDENTITY</span>
              <h1>Manage branding</h1>
              <p>{branding.name}</p>
            </div>
            <button
              className="closeButton"
              aria-label="Close branding"
              onClick={close}
              disabled={busy}
            >
              <UiIcon name="close" />
            </button>
          </div>
          <Form
            noValidate
            onSubmit={brandForm.handleSubmit((values) => {
              if (removeLogo) setPendingRemoval(values);
              else void saveBranding(values);
            })}
          >
            <section className="formSection">
              <Field label="Workspace display name">
                <input
                  id="brand-display-name"
                  className="field"
                  {...brandForm.register("display_name")}
                  aria-invalid={!!brandForm.formState.errors.display_name}
                  aria-describedby="brand-name-error"
                  maxLength={180}
                  required
                />
              </Field>
              <p id="brand-name-error" className="dangerText" role="alert">
                {brandForm.formState.errors.display_name?.message}
              </p>
              <LogoField
                preview={
                  preview ||
                  (!removeLogo && branding.branding?.logo_url
                    ? `${API_URL}${branding.branding.logo_url}`
                    : "")
                }
                onChange={choose}
              />
              {branding.branding?.logo_url && (
                <label className="checkRow">
                  <input
                    type="checkbox"
                    checked={removeLogo}
                    onChange={(e) => {
                      setRemoveLogo(e.target.checked);
                      if (e.target.checked) setFile(null);
                    }}
                  />
                  Remove existing logo
                </label>
              )}
              <div className="brandNote">
                <strong>Your lodge. Powered by SafariOS.</strong>
                <p>
                  The lodge name and logo appear in its authenticated workspace.
                  SafariOS identity stays visible and cannot be removed.
                </p>
              </div>
            </section>
            {error && (
              <p role="alert" className="dangerText">
                {error}
              </p>
            )}
            <div className="drawerActions">
              <button
                type="button"
                className="button secondary"
                onClick={close}
                disabled={busy}
              >
                Cancel
              </button>
              <button className="button primary" disabled={busy}>
                {busy ? "Saving…" : "Save branding"}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
