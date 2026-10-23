"use client";
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
  getActiveLodgeId,
  setActiveLodgeId,
  superApi,
  lodgePreferencesApi,
} from "@/lib/api";
import UiIcon, { moduleIcon } from "./UiIcon";
import NavigationEnhancements from "./NavigationEnhancements";
import SafariBrand from "./SafariBrand";
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
  useEffect(() => {
    authApi
      .me()
      .then(async (v) => {
        if (v.is_super_admin && v.mfa_enabled && getActiveLodgeId())
          v.support_entitlements =
            (await superApi.lodgeEntitlements(getActiveLodgeId())).effective ||
            [];
        if (v.is_super_admin && v.mfa_enabled && getActiveLodgeId())
          await lodgePreferencesApi.get();
        setMe(v);
        if (!getActiveLodgeId() && v.memberships?.[0])
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
        if (user.is_super_admin && user.mfa_enabled && getActiveLodgeId())
          user.support_entitlements =
            (await superApi.lodgeEntitlements(getActiveLodgeId())).effective ||
            [];
        if (user.is_super_admin && user.mfa_enabled && getActiveLodgeId())
          await lodgePreferencesApi.get();
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
  const active = getActiveLodgeId();
  const realMembership =
    me.memberships?.find((m: any) => m.lodge_id === active) ||
    (!me.is_super_admin ? me.memberships?.[0] : null);
  const membership =
    realMembership ||
    (me.is_super_admin && active
      ? {
          lodge_id: active,
          lodge_name:
            typeof window !== "undefined"
              ? localStorage.getItem("active_lodge_name") || "Selected lodge"
              : "Selected lodge",
          role: "Super Admin",
          permissions: [],
          entitlements: me.support_entitlements || [],
          subscription_status: "Platform access",
        }
      : null);
  const roleAllowed = (key: string) => {
    if (!migrated.has(key)) return false;
    if (key === "settings") return true;
    if (me.is_super_admin) return true;
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
            <small>{membership.subscription_status}</small>
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
                  setActiveLodgeId(e.target.value);
                  location.reload();
                }}
              >
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
            <small>{membership.subscription_status}</small>
          )}
        </div>
        {membership && (
          <nav>
            {visible.map(([key, label, icon]) => {
              const g = groupFor(key);
              const heading = g !== last;
              last = g;
              return (
                <div key={key}>
                  {heading && <div className="navSection">{g}</div>}
                  <Link
                    href={`/${key}`}
                    aria-label={label}
                    title={
                      locked(key)
                        ? "Available with additional workspace access"
                        : undefined
                    }
                    className={
                      path === `/${key}` ? "navItem active" : "navItem"
                    }
                  >
                    <span className="navIcon">
                      <UiIcon name={moduleIcon(key)} />
                    </span>
                    <span>{label}</span>
                    {locked(key) && (
                      <LockKeyhole size={14} aria-label="Locked feature" />
                    )}
                    {path === `/${key}` && <i className="activeRail" />}
                  </Link>
                </div>
              );
            })}
          </nav>
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
          <div className="avatar">
            {me.full_name
              ?.split(" ")
              .map((x: string) => x[0])
              .join("")
              .slice(0, 2)}
          </div>
          <div className="profileText">
            <strong>{me.full_name}</strong>
            <small>{me.email}</small>
          </div>
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
            <span className="desktopOnly">SafariOS / Workspace</span>
            <strong className="mobilePlatformName">SafariOS</strong>
          </div>
          <div className="topActions">
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
            <ThemeToggle />
            <SignOutButton />
            <button className="avatarButton" title={me.full_name}>
              {me.full_name
                ?.split(" ")
                .map((x: string) => x[0])
                .join("")
                .slice(0, 2)}
            </button>
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
              features: membership?.entitlements || [],
              permissions: membership?.permissions || [],
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
