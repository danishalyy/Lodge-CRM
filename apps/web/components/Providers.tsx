"use client";
import { useEffect } from "react";
import { startDataRefresh } from "@/lib/data-cache";
import { MotionConfig } from "framer-motion";
import { Toaster } from "sonner";
export default function Providers({ children }: { children: React.ReactNode }) {
  useEffect(startDataRefresh, []);
  return (
    <MotionConfig
      reducedMotion="user"
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
    >
      <div className="surfaceBackdrop" aria-hidden="true">
        <i />
        <i />
        <i />
      </div>
      <div className="grain" aria-hidden="true" />
      {children}
      <Toaster
        richColors
        closeButton
        position="bottom-right"
        toastOptions={{ className: "glassToast" }}
      />
    </MotionConfig>
  );
}
