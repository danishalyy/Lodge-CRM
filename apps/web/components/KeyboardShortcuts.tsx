"use client";
import { useEffect, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { goToNewTask } from "@/lib/quick-actions";
import * as Dialog from "@radix-ui/react-dialog";
import { shortcutCopy as c } from "@/lib/strings/shortcuts";

type Item = readonly string[];
const OPEN_EVENT = "safarios-open-shortcuts";
export const openShortcuts = () => window.dispatchEvent(new Event(OPEN_EVENT));

function typing(target: EventTarget | null) {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return (
    el.isContentEditable ||
    tag === "INPUT" ||
    tag === "TEXTAREA" ||
    tag === "SELECT"
  );
}
const dialogOpen = () =>
  !!document.querySelector('[role="dialog"][data-state="open"]');

export default function KeyboardShortcuts({
  items,
  onSearch,
}: {
  items: readonly Item[];
  onSearch: () => void;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const pending = useRef<number | null>(null);
  const usable = new Map(
    items.filter((i) => i[3] !== "locked").map((i) => [i[0], i[1]] as const),
  );
  const goKeys = Object.entries(c.go).filter(([, mod]) => usable.has(mod));
  const itemsKey = [...usable.keys()].join(",");

  useEffect(() => {
    const show = () => setOpen(true);
    window.addEventListener(OPEN_EVENT, show);
    return () => window.removeEventListener(OPEN_EVENT, show);
  }, []);

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
      if (e.key === "?") {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === "/") {
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

  const Row = ({
    keys,
    label,
    join = c.then,
  }: {
    keys: string[];
    label: string;
    join?: string;
  }) => (
    <li>
      <span>{label}</span>
      <span className="shortcutKeys">
        {keys.map((k, i) => (
          <span key={i}>
            {i > 0 && <small>{join}</small>}
            <kbd>{k}</kbd>
          </span>
        ))}
      </span>
    </li>
  );
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="glassOverlay" />
        <Dialog.Content className="glassDialog shortcutDialog">
          <Dialog.Title>{c.title}</Dialog.Title>
          <Dialog.Description>{c.description}</Dialog.Description>
          <h3>{c.general}</h3>
          <ul className="shortcutList">
            <Row keys={["Ctrl/⌘", "K"]} label={c.search} join="+" />
            <Row keys={["/"]} label={c.searchQuick} />
            <Row keys={["?"]} label={c.help} />
            <Row keys={["Esc"]} label={c.closeAny} />
          </ul>
          {usable.has("tasks") && (
            <>
              <h3>{c.create}</h3>
              <ul className="shortcutList">
                <Row keys={["N"]} label={c.newTask} />
              </ul>
            </>
          )}
          {goKeys.length > 0 && (
            <>
              <h3>{c.goTo}</h3>
              <ul className="shortcutList">
                {goKeys.map(([k, mod]) => (
                  <Row key={k} keys={["G", k.toUpperCase()]} label={usable.get(mod) || mod} />
                ))}
              </ul>
            </>
          )}
          <div className="drawerActions">
            <Dialog.Close className="button primary">{c.close}</Dialog.Close>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
