"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { securityCopy as copy } from "@/lib/strings/security";
export default function MfaPrompt({ userId }: { userId: string }) {
  const [dismissed, setDismissed] = useState(true);
  const key = `mfa-prompt-dismissed:${userId}`;
  useEffect(() => {
    setDismissed(localStorage.getItem(key) === "true");
  }, [key]);
  if (dismissed) return null;
  return (
    <section className="expiryBanner">
      <div>
        <strong>{copy.promptTitle}</strong>
        <p>{copy.promptBody}</p>
      </div>
      <Link className="button" href="/settings">
        {copy.promptAction}
      </Link>
      <button
        className="iconButton"
        aria-label={copy.dismiss}
        onClick={() => {
          localStorage.setItem(key, "true");
          setDismissed(true);
        }}
      >
        ×
      </button>
    </section>
  );
}
