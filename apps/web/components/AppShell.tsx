"use client";
import { GroupedNavigation } from "./ui/grouped-navigation";
import { UserMenu } from "./ui/user-menu";
import { uiCopy as c } from "@/lib/strings/redesign";
import LiveUpdates from "./LiveUpdates";
import { liveCopy } from "@/lib/strings/live";
import StatusPill from "./StatusPill";
import MfaPrompt from "./MfaPrompt";
import { navigationCopy } from "@/lib/strings/navigation";
import LockedFeature from "./LockedFeature";
import { LockKeyhole } from "lucide-react";
import { Field } from "@/components/ui/field";
import { WorkspaceAccessContext } from "@/lib/workspace-access";
import NotificationBell from "./NotificationBell";
import Link from "next/link";
import WorkspaceCommand from "./WorkspaceCommand";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { modules, moduleFeature } from "@/lib/modules";
import {
  authApi,
  getActiveUserId,
  getActiveLodgeId,
  setActiveLodgeId,
} from "@/lib/api";
import UiIcon, { moduleIcon } from "./UiIcon";
import NavigationEnhancements from "./NavigationEnhancements";
import { accessCopy } from "@/lib/strings/access";
import { designCopy } from "@/lib/strings/design";
import SafariBrand, { SafariMark } from "./SafariBrand";
import LodgeIdentity from "./LodgeIdentity";
import ThemeToggle from "./ThemeToggle";
import SignOutButton from "./SignOutButton";
import AccountChangeGuard from "./AccountChangeGuard";
const groupFor = (key: string) =>
  ["dashboard"].includes(key)
    ? "Overview"
    : ["guests", "stays", "rooms", "requests", "feedback"].includes(key)
      ? "Guests"
      : [
            "staff",
            "hr",
            "roles",
            "departments",
            "tasks",
            "housekeeping",
            "maintenance",
            "food-beverage",
          ].includes(key)
        ? "Operations"
        : [
              "activities",
              "transfers",
              "ranger",
              "fleet",
              "fuel",
              "wildlife",
            ].includes(key)
          ? "Safari & Fleet"
          : "Intelligence";
const required: Record<string, string | undefined> = {
  dashboard: "dashboard.view",
  guests: "guests.view",
  stays: "stays.view",
  rooms: "units.view",
  requests: "requests.view",
  feedback: "feedback.view",
  staff: "staff.view",
  hr: "staff.hr.manage",
  roles: "roles.custom.manage",
  departments: "departments.view",
  tasks: "tasks.view",
  housekeeping: "housekeeping.view",
  maintenance: "maintenance.view",
  "food-beverage": "fb.view",
  activities: "activities.view",
  transfers: "transfers.view",
  ranger: "ranger.view",
  fleet: "vehicles.view",
  fuel: "fuel.view",
  wildlife: "wildlife.view",
  reports: "reports.view",
  memory: "memory.view",
  notifications: "notifications.view",
  "lodge-ai": "ai.use",
};
const migrated = new Set([
  "dashboard",
  "guests",
  "stays",
  "rooms",
  "requests",
  "feedback",
  "staff",
  "hr",
  "roles",
  "departments",
  "tasks",
  "housekeeping",
  "maintenance",
  "food-beverage",
  "activities",
  "transfers",
  "ranger",
  "fleet",
  "fuel",
  "wildlife",
  "reports",
  "memory",
  "notifications",
  "settings",
  "lodge-ai",
]);
export default function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname(),
    router = useRouter();
  const [me, setMe] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [navOpen, setNavOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [q, setQ] = useState("");
  const [checkingAccess, setCheckingAccess] = useState(false);
  const [accessError, setAccessError] = useState(false);
  const recheckAccess = async () => {
    const actor = getActiveUserId(),
      lodge = getActiveLodgeId();
    setCheckingAccess(true);
    setAccessError(false);
    try {
      const fresh = await authApi.me();
      if (actor !== getActiveUserId() || lodge !== getActiveLodgeId()) return;
      setMe(fresh);
      setCheckingAccess(false);
    } catch {
      if (actor === getActiveUserId() && lodge === getActiveLodgeId())
        setAccessError(true);
    }
  };
  useEffect(() => {
    authApi
      .me()
      .then(async (v) => {
        setMe(v);
        if (!v.is_super_admin && !getActiveLodgeId() && v.memberships?.[0])
          setActiveLodgeId(v.memberships[0].lodge_id);
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);
  useEffect(() => {
    setNavOpen(false);
    setSearchOpen(false);
    setQ("");
  }, [path]);
  useEffect(() => {
    let alive = true;
    const refresh = async () => {
      try {
        const user = await authApi.me();
        if (alive) setMe(user);
      } catch {}
    };
    const focus = () => {
      if (!document.hidden) void refresh();
    };
    window.addEventListener("safarios-feature-unavailable", focus);
    window.addEventListener("focus", focus);
    const timer = setInterval(focus, 60000);
    return () => {
      alive = false;
      clearInterval(timer);
      window.removeEventListener("safarios-feature-unavailable", focus);
      window.removeEventListener("focus", focus);
    };
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
      if (e.key === "Escape") setSearchOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  if (loading)
    return (
      <div className="appLoading">
        <SafariBrand />
        <span>Loading secure workspace…</span>
      </div>
    );
  if (!me) return null;
  if (checkingAccess)
    return (
      <main className="content">
        <AccountChangeGuard />
        <section className="panel statePanel" role="status">
          <p>{accessError ? liveCopy.accessError : liveCopy.checking}</p>
          {accessError && (
            <button
              type="button"
              className="button primary"
              onClick={() => void recheckAccess()}
            >
              {liveCopy.retry}
            </button>
          )}
        </section>
      </main>
    );
  if (me.is_super_admin && path !== "/settings")
    return (
      <main className="content">
        <AccountChangeGuard />
        <section className="panel statePanel">
          <h1>{accessCopy.platformOnlyTitle}</h1>
          <p>{accessCopy.platformOnlyDescription}</p>
          <Link
            className="button primary"
            href={me.mfa_enabled ? "/super-admin" : "/settings"}
          >
            {me.mfa_enabled
              ? accessCopy.platformConsole
              : accessCopy.accountSecurity}
          </Link>
          <SignOutButton />
        </section>
      </main>
    );
  const active = getActiveLodgeId();
  const realMembership = me.is_super_admin
    ? null
    : me.memberships?.find((m: any) => m.lodge_id === active) ||
      me.memberships?.[0];
  const membership = realMembership;
  const roleAllowed = (key: string) => {
    if (!migrated.has(key)) return false;
    if (key === "settings") return true;
    if (me.is_super_admin) return false;
    const p = required[key];
    return !p || membership?.permissions?.includes(p);
  };
  const locked = (key: string) => {
    const feature = moduleFeature[key as keyof typeof moduleFeature];
    return !!feature && !membership?.entitlements?.includes(feature);
  };
  const allowed = (key: string) => roleAllowed(key) && !locked(key);
  const requestedModule = path.split("/")[1];
  if (me.is_super_admin && !me.mfa_enabled && requestedModule !== "settings")
    return (
      <main className="content">
        <AccountChangeGuard />
        <section className="panel">
          <h1>Authenticator setup required</h1>
          <p>
            Complete MFA setup before accessing operational or platform data.
          </p>
          <Link className="button" href="/settings">
            Account security
          </Link>
          <SignOutButton />
        </section>
      </main>
    );
  const requestedFeature =
    moduleFeature[requestedModule as keyof typeof moduleFeature];
  if (
    !me.is_super_admin &&
    ((!membership && requestedModule !== "settings") ||
      (migrated.has(requestedModule) && !roleAllowed(requestedModule)))
  )
    return (
      <main className="content">
        <AccountChangeGuard />
        <section className="panel">
          <h1>Access denied</h1>
          <p>Your account does not have access to this module.</p>
          <Link className="button" href="/settings">
            Account security
          </Link>
          <SignOutButton />
        </section>
      </main>
    );
  const visible: readonly (readonly string[])[] = [
    ...(me.groups?.length ? [["group", "Group overview", "⌂"]] : []),
    ...modules
      .filter(([key]) => roleAllowed(key))
      .map(([key, label, icon]) => [
        key,
        label,
        icon,
        locked(key) ? "locked" : "",
      ]),
  ];

  const blocked =
    membership &&
    !me.is_super_admin &&
    ["Suspended", "Pending"].includes(membership.subscription_status);
  if (blocked && path !== "/settings")
    return (
      <div className="appShell">
        <aside className="sidebar">
          <SafariBrand />
          <div className="lodgeMini">
            <strong>{membership.lodge_name}</strong>
            <small>
              {membership.package || membership.subscription_status}
            </small>
          </div>
          <nav>
            <div className="navSection">Account</div>
            <Link href="/settings" className="navItem">
              Account Security
            </Link>
          </nav>
        </aside>
        <main className="mainArea">
          <header className="topbar">
            <ThemeToggle />
            <SignOutButton />
          </header>
          <div className="content">
            <section className="panel statePanel">
              <span className="stateIcon danger">!</span>
              <span className="eyebrow">ACCESS RESTRICTED</span>
              <h1>
                {membership.subscription_status === "Suspended"
                  ? "Lodge access suspended"
                  : "Subscription not started"}
              </h1>
              <p>
                Operational CRM access is unavailable. Contact the platform
                administrator. Your account-security settings remain available.
              </p>
              <Link href="/settings" className="button">
                Account Security
              </Link>
            </section>
          </div>
        </main>
      </div>
    );
  let last = "";
  return (
    <div className="appShell">
      <AccountChangeGuard />
      <NavigationEnhancements
        role={membership?.role_key}
        items={visible}
        open={navOpen}
        onOpenChange={setNavOpen}
      />
      <button
        className="mobileBackdrop"
        aria-label="Close navigation"
        onClick={() => setNavOpen(false)}
      />
      <aside className="sidebar">
        <SafariBrand />
        {me.memberships?.length > 1 && (
          <div className="roleBox">
            <Field label="ACTIVE LODGE">
              <select
                className="roleSelect"
                value={realMembership?.lodge_id || ""}
                onChange={(e) => {
                  if (e.target.value === "group") {
                    location.href = "/group";
                    return;
                  }
                  setActiveLodgeId(e.target.value);
                  location.reload();
                }}
              >
                {me.groups?.length > 0 && (
                  <option value="group">{c.group}</option>
                )}
                {me.memberships.map((m: any) => (
                  <option value={m.lodge_id} key={m.lodge_id}>
                    {m.lodge_name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
        )}
        <div className="lodgeMini">
          {membership ? (
            <LodgeIdentity
              lodgeId={membership.lodge_id}
              name={membership.lodge_name}
            />
          ) : (
            <strong>No lodge selected</strong>
          )}
          <small>
            {membership?.role || (me.is_super_admin ? "Super Admin" : "")}
          </small>
          {membership?.subscription_status && (
            <small>
              {membership.package || membership.subscription_status}
            </small>
          )}
        </div>
        {membership && (
          <GroupedNavigation
            items={visible}
            knowledge={
              allowed("lodge-ai") &&
              membership.entitlements?.includes("ai_knowledge") &&
              membership.entitlements?.includes("document_knowledge") &&
              membership.permissions?.includes("knowledge.view")
            }
          />
        )}
        {visible.some(([key]) => key === "lodge-ai") && (
          <Link className="navItem pinnedAI" href="/lodge-ai">
            <UiIcon name="ai" />
            <span>Ask Lodge AI</span>
            {locked("lodge-ai") && (
              <LockKeyhole size={14} aria-label="Locked feature" />
            )}
          </Link>
        )}
        {me.is_super_admin && (
          <nav className="platformNav">
            <div className="navSection">Platform</div>
            <Link href="/super-admin" className="navItem">
              <span className="navIcon">
                <UiIcon name="overview" />
              </span>
              <span>Super Admin</span>
            </Link>
          </nav>
        )}
        <div className="sidebarFooter">
          <UserMenu
            name={me.full_name}
            role={membership?.role || "Super Admin"}
          />
        </div>
      </aside>
      <main className="mainArea">
        <header className="topbar">
          <div className="topContext">
            <button
              className="mobileMenu"
              onClick={() => setNavOpen((v) => !v)}
              aria-label="Open navigation"
            >
              <UiIcon name="menu" />
            </button>
            <span className="statusDot" />
            <span className="desktopOnly workspaceBreadcrumb">
              <span>{membership?.lodge_name || designCopy.workspace}</span>
              <span className="breadcrumbDivider" aria-hidden="true">
                /
              </span>
              <strong>
                {visible.find(([key]) => key === requestedModule)?.[1] ||
                  designCopy.workspace}
              </strong>
            </span>
            <span className="mobileBrandMark">
              <SafariMark />
            </span>
            <strong className="mobilePlatformName">SafariOS</strong>
          </div>
          <div className="topActions">
            {!me.is_super_admin &&
              membership &&
              requestedModule !== "group" &&
              !blocked && (
                <LiveUpdates
                  userId={me.id}
                  lodgeId={membership.lodge_id}
                  accessVersion={JSON.stringify([
                    membership.role_key,
                    membership.permissions,
                    membership.entitlements,
                    membership.subscription_status,
                    membership.department_id,
                  ])}
                  onAccessChange={() => void recheckAccess()}
                />
              )}
            <button
              className="searchButton"
              aria-label={navigationCopy.search}
              onClick={() => setSearchOpen(true)}
            >
              <UiIcon name="search" />
              <span>{navigationCopy.search}</span>
              <kbd>⌘ K</kbd>
            </button>
            {allowed("notifications") && <NotificationBell />}
            {["Expiring Soon", "Expired"].includes(
              membership?.subscription_status,
            ) && <StatusPill value={membership.subscription_status} />}
            <div className="mobileUserMenu">
              <UserMenu name={me.full_name} role={membership?.role} />
            </div>
          </div>
        </header>
        <div className="content">
          {!me.mfa_enabled &&
            !me.is_super_admin &&
            membership?.mfa_recommended &&
            path !== "/settings" && <MfaPrompt key={me.id} userId={me.id} />}
          {membership?.subscription_status === "Expired" && (
            <section className="expiryBanner">
              <strong>Subscription expired</strong>
              <span>
                Read-only access is active until Super Admin extends the
                subscription.
              </span>
            </section>
          )}
          <WorkspaceAccessContext.Provider
            value={{
              readOnly: ["Expired", "Pending", "Suspended"].includes(
                membership?.subscription_status,
              ),
              features: membership?.entitlements || [],
              permissions: membership?.permissions || [],
              displayName: me.full_name,
              roleKey: membership?.role_key,
              lodgeName:
                membership?.branding?.display_name || membership?.lodge_name,
              contextId: `${me.id}:${membership?.lodge_id || ""}`,
              platform: !!me.is_super_admin,
            }}
          >
            {requestedFeature && locked(requestedModule) ? (
              <LockedFeature module={requestedModule} />
            ) : (
              children
            )}
          </WorkspaceAccessContext.Provider>
        </div>
      </main>
      <WorkspaceCommand
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        items={visible}
      />
    </div>
  );
}
