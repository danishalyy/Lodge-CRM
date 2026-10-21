"use client";
import NotificationBell from "./NotificationBell";
import Link from "next/link";
import NavigationEnhancements from "./NavigationEnhancements";
import SafariBrand from "./SafariBrand";
import UiIcon, { moduleIcon } from "./UiIcon";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { authApi } from "@/lib/api";
import ThemeToggle from "./ThemeToggle";
import SignOutButton from "./SignOutButton";
import AccountChangeGuard from "./AccountChangeGuard";
const items = [
  ["", "Overview", "◫"],
  ["lodges", "Lodges", "⌂"],
  ["subscriptions", "Subscriptions", "◷"],
  ["packages", "Packages", "▦"],
  ["users", "Platform Users", "◎"],
  ["audit", "Audit", "≡"],
  ["notifications", "Notifications", "◉"],
  ["settings", "Settings", "⚙"],
];
export default function SuperAdminShell({
  children,
}: {
  children: React.ReactNode;
}) {
  const p = usePathname();
  const router = useRouter();
  const [navOpen, setNavOpen] = useState(false);
  useEffect(() => {
    setNavOpen(false);
  }, [p]);
  const [status, setStatus] = useState<
    "loading" | "allowed" | "denied" | "error"
  >("loading");
  useEffect(() => {
    let active = true;
    authApi
      .me()
      .then((user) => {
        if (!active) return;
        if (!user.is_super_admin) {
          setStatus("denied");
          return;
        }
        if (!user.mfa_enabled) {
          router.replace("/settings");
          return;
        }
        setStatus("allowed");
      })
      .catch(() => {
        if (active) setStatus("error");
      });
    return () => {
      active = false;
    };
  }, [router]);
  if (status === "loading")
    return (
      <main className="content" role="status">
        Checking platform access…
      </main>
    );
  if (status === "denied")
    return (
      <main className="content">
        <section className="panel">
          <h1>Access denied</h1>
          <p>
            Your lodge account does not have platform administration access.
          </p>
          <Link className="button" href="/dashboard">
            Return to lodge dashboard
          </Link>
        </section>
      </main>
    );
  if (status === "error")
    return (
      <main className="content">
        <section className="panel">
          <h1>Unable to verify access</h1>
          <p>
            Please sign in again or retry when your connection is available.
          </p>
          <Link className="button" href="/login">
            Sign in
          </Link>
        </section>
      </main>
    );
  return (
    <div className="appShell">
      <AccountChangeGuard />
      <NavigationEnhancements open={navOpen} onOpenChange={setNavOpen} />
      <button
        className="mobileBackdrop"
        aria-label="Close navigation"
        onClick={() => setNavOpen(false)}
      />
      <aside className="sidebar">
        <SafariBrand />
        <div className="platformBadge">
          <span>PLATFORM CONSOLE</span>
          <strong>Administration</strong>
          <small>Your lodges. One clear view.</small>
        </div>
        <nav aria-label="Platform navigation">
          <div className="navSection">Manage platform</div>
          {items.map(([k, l]) => (
            <Link
              key={k}
              aria-label={l}
              href={`/super-admin${k ? "/" + k : ""}`}
              className={
                p === `/super-admin${k ? "/" + k : ""}`
                  ? "navItem active"
                  : "navItem"
              }
              aria-current={
                p === `/super-admin${k ? "/" + k : ""}` ? "page" : undefined
              }
            >
              <span className="navIcon">
                <UiIcon name={moduleIcon(k)} />
              </span>
              {l}
            </Link>
          ))}
        </nav>
        <div className="sidebarFooter">
          <div className="avatar">SA</div>
          <div>
            <strong>Super Admin</strong>
            <small>SafariOS platform owner</small>
          </div>
        </div>
      </aside>
      <main className="mainArea">
        <header className="topbar">
          <div className="topContext">
            <button
              className="mobileMenu"
              aria-label="Open navigation"
              onClick={() => setNavOpen((v) => !v)}
            >
              <UiIcon name="menu" />
            </button>
            <span>SafariOS</span>
            <span className="breadcrumbDivider">/</span>
            <strong>
              {items.find(
                ([k]) => p === `/super-admin${k ? "/" + k : ""}`,
              )?.[1] || "Administration"}
            </strong>
          </div>
          <div className="topActions">
            <NotificationBell platform />
            <ThemeToggle />
            <SignOutButton />
          </div>
        </header>
        <div className="content">{children}</div>
        <footer className="workspaceFooter">
          SafariOS <span>Considered software for exceptional hospitality.</span>
        </footer>
      </main>
    </div>
  );
}
