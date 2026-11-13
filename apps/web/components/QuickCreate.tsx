"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { goToNewTask } from "@/lib/quick-actions";
import { ClipboardCheck, PawPrint, Plus, X } from "lucide-react";
import { shortcutCopy as c } from "@/lib/strings/shortcuts";

export default function QuickCreate({
  items,
}: {
  items: readonly (readonly string[])[];
}) {
  const path = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const has = (k: string) => items.some((i) => i[0] === k && i[3] !== "locked");
  const actions = [
    has("tasks") && { href: "/tasks?create=1", label: c.newTask, Icon: ClipboardCheck },
    has("wildlife") && { href: "/wildlife", label: c.recordSighting, Icon: PawPrint },
  ].filter(Boolean) as { href: string; label: string; Icon: typeof Plus }[];
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("pointerdown", away);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);
  if (!actions.length) return null;
  return (
    <div className="quickCreate" ref={box}>
      {open && (
        <div className="quickCreateMenu" role="menu" aria-label={c.quickCreate}>
          {actions.map(({ href, label, Icon }) => (
            <Link
              key={href}
              href={href}
              role="menuitem"
              onClick={(e) => {
                if (href.startsWith("/tasks") && path === "/tasks") {
                  e.preventDefault();
                  goToNewTask(router, path);
                  setOpen(false);
                }
              }}
            >
              <Icon size={18} aria-hidden="true" />
              {label}
            </Link>
          ))}
        </div>
      )}
      <button
        type="button"
        className="quickCreateButton"
        aria-label={c.quickCreate}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <X size={22} /> : <Plus size={22} />}
      </button>
    </div>
  );
}
