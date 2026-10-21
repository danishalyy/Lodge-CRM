"use client";
import { useEffect, useState } from "react";
import Drawer from "./Drawer";
import UiIcon, { moduleIcon } from "./UiIcon";
import Link from "next/link";
import { LockKeyhole } from "lucide-react";
import { usePathname } from "next/navigation";
import {
  PanelLeftClose,
  PanelLeftOpen,
  LayoutDashboard,
  Building2,
  Settings,
  Menu,
  Users,
} from "lucide-react";
export default function NavigationEnhancements({
  items,
  open,
  onOpenChange,
}: {
  items?: readonly (readonly string[])[];
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
}) {
  const [internalMore, setInternalMore] = useState(false);
  const more = open ?? internalMore;
  const setMore = onOpenChange ?? setInternalMore;
  const [collapsed, setCollapsed] = useState(false);
  const path = usePathname();
  const platform = path.startsWith("/super-admin");
  useEffect(() => {
    const value = localStorage.getItem("sidebar-collapsed") === "true";
    setCollapsed(value);
    document.documentElement.dataset.sidebar = value ? "collapsed" : "expanded";
    return () => {
      delete document.documentElement.dataset.sidebar;
    };
  }, []);
  function toggle() {
    const next = !collapsed;
    setCollapsed(next);
    document.documentElement.dataset.sidebar = next ? "collapsed" : "expanded";
    localStorage.setItem("sidebar-collapsed", String(next));
  }
  const links = platform
    ? ([
        ["/super-admin", "Overview", LayoutDashboard],
        ["/super-admin/lodges", "Lodges", Building2],
        ["/super-admin/settings", "Settings", Settings],
      ] as const)
    : ([
        ["/dashboard", "Home", LayoutDashboard],
        ["/guests", "Guests", Users],
        ["/settings", "Settings", Settings],
      ] as const);
  const visibleLinks = links.filter(
    ([href]) => platform || !items || items.some(([key]) => href === "/" + key),
  );
  return (
    <>
      <button
        className="collapseSidebar iconButton"
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        onClick={toggle}
      >
        {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
      </button>
      <nav className="bottomTabs" aria-label="Quick navigation">
        {visibleLinks.map(([href, label, Icon]) => (
          <Link
            key={href}
            href={href}
            aria-current={path === href ? "page" : undefined}
          >
            <Icon size={20} />
            <span>{label}</span>
          </Link>
        ))}
        <button onClick={() => setMore(true)}>
          <Menu size={20} />
          <span>More</span>
        </button>
      </nav>
      {more && (
        <Drawer onClose={() => setMore(false)}>
          <div className="drawerHead">
            <h2>Navigate SafariOS</h2>
            <button className="button" onClick={() => setMore(false)}>
              Close
            </button>
          </div>
          <nav aria-label="All screens">
            {(
              items || [
                ["super-admin", "Overview"],
                ["super-admin/lodges", "Lodges"],
                ["super-admin/groups", "Lodge groups"],
                ["super-admin/subscriptions", "Subscriptions"],
                ["super-admin/packages", "Packages"],
                ["super-admin/users", "Platform Users"],
                ["super-admin/audit", "Audit"],
                ["super-admin/notifications", "Notifications"],
                ["super-admin/settings", "Settings"],
              ]
            ).map(([key, label, , state]) => (
              <Link
                className="navItem"
                href={"/" + key}
                key={key}
                onClick={() => setMore(false)}
              >
                <UiIcon name={moduleIcon(key)} />
                <span>{label}</span>
                {state === "locked" && (
                  <LockKeyhole size={14} aria-label="Locked feature" />
                )}
              </Link>
            ))}
          </nav>
        </Drawer>
      )}
    </>
  );
}
