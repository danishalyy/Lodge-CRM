"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { ChevronDown, LockKeyhole } from "lucide-react";
import UiIcon, { moduleIcon } from "../UiIcon";
import { uiCopy as c } from "@/lib/strings/redesign";
import { getActiveUserId, getActiveLodgeId } from "@/lib/api";
const groups = [
  { name: c.today, keys: ["dashboard", "arrivals", "tasks", "notifications"] },
  {
    name: c.guests,
    keys: ["guests", "stays", "rooms", "requests", "feedback"],
  },
  {
    name: c.operations,
    keys: [
      "housekeeping",
      "maintenance",
      "food-beverage",
      "transfers",
      "activities",
    ],
  },
  { name: c.safari, keys: ["ranger", "wildlife", "fleet", "fuel"] },
  { name: c.people, keys: ["staff", "hr", "departments", "roles"] },
  { name: c.insight, keys: ["reports", "memory", "knowledge"] },
];
export function GroupedNavigation({
  items,
  knowledge = false,
}: {
  items: readonly (readonly string[])[];
  knowledge?: boolean;
}) {
  const path = usePathname(),
    params = useSearchParams();
  const [closed, setClosed] = useState<string[]>(groups.map((g) => g.name));
  const storageKey = `safarios-nav:${getActiveUserId()}:${getActiveLodgeId()}`;
  useEffect(() => {
    try {
      const raw = localStorage.getItem(storageKey);
      const saved = raw ? JSON.parse(raw) : groups.map((g) => g.name);
      if (Array.isArray(saved))
        setClosed(saved.filter((x) => typeof x === "string"));
    } catch {}
  }, [storageKey]);
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
  function toggle(name: string) {
    const next = closed.includes(name)
      ? closed.filter((n) => n !== name)
      : [...closed, name];
    setClosed(next);
    localStorage.setItem(storageKey, JSON.stringify(next));
  }
  return (
    <nav className="groupedNav" aria-label="Lodge navigation">
      {items.some(([k]) => k === "group") && (
        <Link href="/group" className="navItem">
          <UiIcon name="overview" />
          <span>{c.group}</span>
        </Link>
      )}
      {groups.map((group) => {
        const rows = nav.filter((i) => group.keys.includes(i.key));
        if (!rows.length) return null;
        const expanded =
          !closed.includes(group.name) || rows.some((i) => active(i.key));
        return (
          <div className="navGroup" key={group.name}>
            <button
              className="navGroupToggle"
              aria-expanded={expanded}
              aria-controls={"nav-" + group.keys[0]}
              onClick={() => toggle(group.name)}
            >
              <span>{group.name}</span>
              <ChevronDown size={13} />
            </button>
            <div id={"nav-" + group.keys[0]} hidden={!expanded}>
              {rows.map((i) => (
                <Link
                  href={i.href}
                  key={i.key}
                  className={
                    "navItem" +
                    (active(i.key) ? " active" : "") +
                    (i.locked ? " locked" : "")
                  }
                  aria-label={i.label}
                  aria-current={active(i.key) ? "page" : undefined}
                >
                  <span className="navIcon">
                    <UiIcon
                      name={moduleIcon(
                        i.key === "arrivals"
                          ? "stays"
                          : i.key === "knowledge"
                            ? "lodge-ai"
                            : i.key,
                      )}
                    />
                  </span>
                  <span>{i.label}</span>
                  {i.locked && (
                    <LockKeyhole size={14} aria-label="Locked feature" />
                  )}
                </Link>
              ))}
            </div>
          </div>
        );
      })}
    </nav>
  );
}
