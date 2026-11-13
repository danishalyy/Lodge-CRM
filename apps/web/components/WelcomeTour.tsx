"use client";
import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { tourCopy as t } from "@/lib/strings/shortcuts";

const OPEN_EVENT = "safarios-open-tour";
export const openTour = () => window.dispatchEvent(new Event(OPEN_EVENT));

export default function WelcomeTour({
  userId,
  lodgeId,
  items,
}: {
  userId: string;
  lodgeId: string;
  items: readonly (readonly string[])[];
}) {
  const has = (k: string) => items.some((i) => i[0] === k && i[3] !== "locked");
  const steps = [
    t.steps.nav,
    t.steps.search,
    has("tasks") && t.steps.tasks,
    has("lodge-ai") && t.steps.ai,
    has("wildlife") && t.steps.wildlife,
  ].filter(Boolean) as { title: string; body: string }[];
  const key = `safarios-tour:${userId}:${lodgeId}`;
  const [open, setOpen] = useState(false);
  const [i, setI] = useState(0);
  useEffect(() => {
    try {
      if (!localStorage.getItem(key) && items.length) setOpen(true);
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, items.length > 0]);
  useEffect(() => {
    const show = () => {
      setI(0);
      setOpen(true);
    };
    window.addEventListener(OPEN_EVENT, show);
    return () => window.removeEventListener(OPEN_EVENT, show);
  }, []);
  const finish = () => {
    try {
      localStorage.setItem(key, "done");
    } catch {}
    setOpen(false);
  };
  const step = steps[Math.min(i, steps.length - 1)];
  const last = i >= steps.length - 1;
  if (!step) return null;
  return (
    <Dialog.Root open={open} onOpenChange={(v) => (v ? setOpen(true) : finish())}>
      <Dialog.Portal>
        <Dialog.Overlay className="glassOverlay" />
        <Dialog.Content className="glassDialog tourDialog">
          <p className="tourStep">{t.step(i + 1, steps.length)}</p>
          <Dialog.Title>{step.title}</Dialog.Title>
          <Dialog.Description>{step.body}</Dialog.Description>
          <div className="tourDots" aria-hidden="true">
            {steps.map((_, n) => (
              <i key={n} className={n === i ? "on" : ""} />
            ))}
          </div>
          <div className="drawerActions">
            <button type="button" className="button" onClick={finish}>
              {t.skip}
            </button>
            {i > 0 && (
              <button type="button" className="button" onClick={() => setI(i - 1)}>
                {t.back}
              </button>
            )}
            <button
              type="button"
              className="button primary"
              onClick={() => (last ? finish() : setI(i + 1))}
            >
              {last ? t.done : t.next}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
