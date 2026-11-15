"use client";
import { useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { goToNewTask } from "@/lib/quick-actions";
import { shortcutCopy as c } from "@/lib/strings/shortcuts";

// Silent keyboard shortcuts for people who like them. Nothing is shown on
// screen: "/" or Ctrl/Cmd+K searches, "N" adds a task, "G" then a letter
// jumps to a page. Ignored while typing or when a dialog is open.
type Item = readonly string[];

function typing(target: EventTarget | null) {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return el.isContentEditable || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}
const dialogOpen = () => !!document.querySelector('[role="dialog"][data-state="open"]');

export default function KeyboardShortcuts({
  items,
  onSearch,
}: {
  items: readonly Item[];
  onSearch: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const pending = useRef<number | null>(null);
  const usable = new Set(items.filter((i) => i[3] !== "locked").map((i) => i[0]));
  const itemsKey = [...usable].join(",");

  useEffect(() => {
    const clear = () => {
      if (pending.current) window.clearTimeout(pending.current);
      pending.current = null;
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.defaultPrevented) return;
      if (typing(e.target) || dialogOpen()) return;
      const key = e.key.toLowerCase();
      if (pending.current) {
        const mod = c.go[key];
        clear();
        if (mod && usable.has(mod)) {
          e.preventDefault();
          router.push("/" + mod);
        }
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        onSearch();
      } else if (key === "g") {
        pending.current = window.setTimeout(clear, 1200);
      } else if (key === "n" && usable.has("tasks")) {
        e.preventDefault();
        goToNewTask(router, pathname);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      clear();
      window.removeEventListener("keydown", onKey);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemsKey, router, pathname, onSearch]);
  return null;
}
