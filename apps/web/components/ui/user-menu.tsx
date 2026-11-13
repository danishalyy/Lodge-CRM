"use client";
import { useEffect, useRef } from "react";
import Link from "next/link";
import { ChevronUp, Compass, Keyboard, Settings, UserRound } from "lucide-react";
import { shortcutCopy as sc } from "@/lib/strings/shortcuts";
import ThemeToggle from "../ThemeToggle";
import { SyncChip } from "./sync-chip";
import SignOutButton from "../SignOutButton";
import { uiCopy as c } from "@/lib/strings/redesign";
export function UserMenu({
  name,
  role,
  tools = false,
}: {
  name?: string;
  role?: string;
  tools?: boolean;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const close = (e: Event) => {
      const node = ref.current;
      if (!node?.open) return;
      if (e instanceof KeyboardEvent && e.key === "Escape") {
        node.open = false;
        node.querySelector("summary")?.focus();
      } else if (e.type === "pointerdown" && !node.contains(e.target as Node))
        node.open = false;
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("pointerdown", close);
      document.removeEventListener("keydown", close);
    };
  }, []);
  return (
    <details className="userMenu" ref={ref}>
      <summary aria-label={c.account}>
        <span className="avatar">
          {name ? (
            name
              .split(" ")
              .map((n) => n[0])
              .join("")
              .slice(0, 2)
          ) : (
            <UserRound size={18} />
          )}
        </span>
        <span className="userMenuName">
          <strong>{name || "SafariOS"}</strong>
          <small>{role || c.security}</small>
        </span>
        <ChevronUp size={14} />
      </summary>
      <div className="userMenuPanel">
        <Link
          href="/settings"
          onClick={() => {
            if (ref.current) ref.current.open = false;
          }}
        >
          <Settings size={16} />
          {c.security}
        </Link>
        {tools && (
          <>
            <button
              type="button"
              onClick={() => {
                if (ref.current) ref.current.open = false;
                window.dispatchEvent(new Event("safarios-open-shortcuts"));
              }}
            >
              <Keyboard size={16} />
              {sc.menuShortcuts}
            </button>
            <button
              type="button"
              onClick={() => {
                if (ref.current) ref.current.open = false;
                window.dispatchEvent(new Event("safarios-open-tour"));
              }}
            >
              <Compass size={16} />
              {sc.menuTour}
            </button>
          </>
        )}
        <div>
          <span>{c.theme}</span>
          <ThemeToggle />
        </div>
        <SyncChip />
        <SignOutButton />
      </div>
    </details>
  );
}
