"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import {
  BarChart3,
  Binoculars,
  ChevronDown,
  ClipboardList,
  LockKeyhole,
  Users,
  UsersRound,
} from "lucide-react";
import UiIcon, { moduleIcon } from "../UiIcon";
import { uiCopy as c } from "@/lib/strings/redesign";

// Most-used pages stay on top, everything else sits in a few sections that
// open one at a time, so the menu stays short.
const topKeys = ["dashboard", "tasks"];
const groups = [
  {
    name: c.guests,
    Icon: Users,
    keys: ["arrivals", "guests", "stays", "rooms", "requests", "feedback"],
  },
  {
    name: c.operations,
    Icon: ClipboardList,
    keys: ["housekeeping", "maintenance", "food-beverage", "transfers", "activities"],
  },
  { name: c.safari, Icon: Binoculars, keys: ["ranger", "wildlife", "fleet", "fuel"] },
  { name: c.people, Icon: UsersRound, keys: ["staff", "hr", "departments", "roles"] },
  { name: c.insight, Icon: BarChart3, keys: ["reports", "memory", "knowledge"] },
];
export function GroupedNavigation({
  items,
  knowledge = false,
  ai = { show: false, locked: false },
}: {
  items: readonly (readonly string[])[];
  knowledge?: boolean;
  ai?: { show: boolean; locked: boolean };
}) {
  const path = usePathname(),
    params = useSearchParams();
  const nav = items
    .filter(([key]) => !["lodge-ai", "settings", "group"].includes(key))
    .map((i) => ({
      key: i[0],
      label: i[1],
      href: "/" + i[0],
      locked: i[3] === "locked",
    }));
  if (items.some(([k]) => k === "stays"))
    nav.push({
      key: "arrivals",
      label: c.arrivals,
      href: "/stays?view=arrivals",
      locked: items.find(([k]) => k === "stays")?.[3] === "locked",
    });
  if (knowledge)
    nav.push({
      key: "knowledge",
      label: c.knowledge,
      href: "/lodge-ai?panel=knowledge",
      locked: false,
    });
  const active = (key: string) =>
    key === "arrivals"
      ? path === "/stays" && params.get("view") === "arrivals"
      : key === "knowledge"
        ? path === "/lodge-ai" && params.get("panel") === "knowledge"
        : path === "/" + key &&
          (key !== "stays" || params.get("view") !== "arrivals");
  const activeGroup =
    groups.find((g) => nav.some((i) => g.keys.includes(i.key) && active(i.key)))
      ?.name ?? null;
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => setOpen(null), [path]);
  function toggle(name: string) {
    // In the slim icon rail a section icon opens the full sidebar on that section.
    if (document.documentElement.dataset.sidebar === "collapsed") {
      setOpen(name);
      document.querySelector<HTMLButtonElement>(".collapseSidebar")?.click();
      return;
    }
    if (name === activeGroup) return;
    setOpen((cur) => (cur === name ? null : name));
  }
  const row = (i: { key: string; label: string; href: string; locked: boolean }) => (
    <Link
      href={i.href}
      key={i.key}
      className={
        "navItem" + (active(i.key) ? " active" : "") + (i.locked ? " locked" : "")
      }
      aria-label={i.label}
      aria-current={active(i.key) ? "page" : undefined}
    >
      <span className="navIcon">
        <UiIcon
          name={moduleIcon(
            i.key === "arrivals" ? "stays" : i.key === "knowledge" ? "lodge-ai" : i.key,
          )}
        />
      </span>
      <span>{i.label}</span>
      {i.locked && <LockKeyhole size={14} aria-label="Locked feature" />}
    </Link>
  );
  return (
    <nav className="groupedNav" aria-label="Lodge navigation">
      {items.some(([k]) => k === "group") && (
        <Link href="/group" className="navItem">
          <UiIcon name="overview" />
          <span>{c.group}</span>
        </Link>
      )}
      {nav.filter((i) => topKeys.includes(i.key)).map(row)}
      {ai.show && (
        <Link
          href="/lodge-ai"
          className={"navItem aiItem" + (path === "/lodge-ai" && !params.get("panel") ? " active" : "")}
          aria-current={path === "/lodge-ai" && !params.get("panel") ? "page" : undefined}
        >
          <span className="navIcon">
            <UiIcon name="ai" />
          </span>
          <span>Ask Lodge AI</span>
          {ai.locked && <LockKeyhole size={14} aria-label="Locked feature" />}
        </Link>
      )}
      <div className="navDivider" aria-hidden="true" />
      {groups.map((group) => {
        const rows = nav.filter((i) => group.keys.includes(i.key));
        if (!rows.length) return null;
        const expanded = group.name === activeGroup || group.name === open;
        return (
          <div className="navGroup" key={group.name}>
            <button
              className="navGroupToggle"
              title={group.name}
              aria-expanded={expanded}
              aria-controls={"nav-" + group.keys[0]}
              onClick={() => toggle(group.name)}
            >
              <group.Icon size={18} aria-hidden="true" />
              <span>{group.name}</span>
              <ChevronDown size={14} aria-hidden="true" />
            </button>
            <div className="navGroupBody" data-open={expanded}>
              <div id={"nav-" + group.keys[0]}>{rows.map(row)}</div>
            </div>
          </div>
        );
      })}
    </nav>
  );
}
