"use client";
import * as React from "react";
import { contentCopy } from "@/lib/strings/content";
export function TimezonePicker(
  props: React.InputHTMLAttributes<HTMLInputElement>,
) {
  const id = React.useId();
  const zones = React.useMemo(
    () =>
      Array.from(
        new Set([
          Intl.DateTimeFormat().resolvedOptions().timeZone,
          "UTC",
          ...(typeof Intl.supportedValuesOf === "function"
            ? Intl.supportedValuesOf("timeZone")
            : [
                "Africa/Johannesburg",
                "Africa/Nairobi",
                "Europe/London",
                "America/New_York",
                "Asia/Karachi",
              ]),
        ]),
      ).sort(),
    [],
  );
  return (
    <>
      <input
        {...props}
        className="field"
        list={id}
        placeholder={contentCopy.timezone}
        autoComplete="off"
      />
      <datalist id={id}>
        {zones.map((zone) => (
          <option key={zone} value={zone} />
        ))}
      </datalist>
    </>
  );
}
