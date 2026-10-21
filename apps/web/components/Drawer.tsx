"use client";
import { useEffect, useState, useRef } from "react";
import { motion, useReducedMotion } from "framer-motion";
import * as Dialog from "@radix-ui/react-dialog";
import { Drawer as Vaul } from "vaul";
export default function Drawer({
  children,
  onClose,
}: {
  children: React.ReactNode;
  onClose: () => void;
}) {
  const returnFocus = useRef<HTMLElement | null>(
    typeof document !== "undefined" &&
      document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null,
  );
  useEffect(() => {
    return () => {
      const target = returnFocus.current;
      requestAnimationFrame(() => {
        if (target?.isConnected) target.focus();
      });
    };
  }, []);
  const reduced = useReducedMotion();
  const [mobile, setMobile] = useState(false);
  useEffect(() => {
    const m = matchMedia("(max-width: 767px)");
    const change = () => setMobile(m.matches);
    change();
    m.addEventListener("change", change);
    return () => m.removeEventListener("change", change);
  }, []);
  if (mobile)
    return (
      <Vaul.Root
        open
        onOpenChange={(open) => {
          if (!open) onClose();
        }}
      >
        <Vaul.Portal>
          <Vaul.Overlay className="glassOverlay" />
          <Vaul.Content className="glassDrawer">
            <div className="drawerHandle" />
            <Vaul.Title className="sr-only">Details and actions</Vaul.Title>
            <Vaul.Description className="sr-only">
              Review and update the selected record.
            </Vaul.Description>
            <div className="drawer">{children}</div>
          </Vaul.Content>
        </Vaul.Portal>
      </Vaul.Root>
    );
  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="glassOverlay" />
        <Dialog.Content asChild>
          <motion.div
            className="glassDialog"
            initial={reduced ? false : { opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            style={{ x: "-50%", y: "-50%" }}
          >
            <Dialog.Title className="sr-only">Details and actions</Dialog.Title>
            <Dialog.Description className="sr-only">
              Review and update the selected record.
            </Dialog.Description>
            <div className="drawer">{children}</div>
          </motion.div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
