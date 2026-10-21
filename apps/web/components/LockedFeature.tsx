"use client";
import { useState } from "react";
import { LockKeyhole } from "lucide-react";
import Drawer from "./Drawer";
import { onboardingCopy as copy } from "@/lib/strings/onboarding";
export default function LockedFeature({ module }: { module: string }) {
  const [contact, setContact] = useState(false);
  const plan = module === "lodge-ai" ? "Premium" : "Standard";
  return (
    <section className="panel statePanel">
      <LockKeyhole aria-hidden="true" size={28} />
      <h1>{copy.lockedTitle(plan)}</h1>
      <p>{copy.lockedBody}</p>
      <button className="button primary" onClick={() => setContact(true)}>
        {copy.contact}
      </button>
      {contact && (
        <Drawer onClose={() => setContact(false)}>
          <div className="drawerHead">
            <h2>{copy.contactTitle}</h2>
            <button
              className="closeButton"
              aria-label="Close dialog"
              onClick={() => setContact(false)}
            >
              ×
            </button>
          </div>
          <p>{copy.contactBody}</p>
          <button className="button" onClick={() => setContact(false)}>
            Done
          </button>
        </Drawer>
      )}
    </section>
  );
}
