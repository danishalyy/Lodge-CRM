"use client";
import * as React from "react";
import { countryCodes } from "@/lib/countries";
import { contentCopy } from "@/lib/strings/content";
export function CountryPicker(
  props: React.SelectHTMLAttributes<HTMLSelectElement>,
) {
  const options = React.useMemo(() => {
    const english = new Intl.DisplayNames(["en"], { type: "region" }),
      localized = new Intl.DisplayNames(
        [typeof navigator === "undefined" ? "en" : navigator.language],
        { type: "region" },
      );
    return countryCodes
      .map((code) => ({
        value: english.of(code) || code,
        label: localized.of(code) || code,
      }))
      .sort((a, b) => a.label.localeCompare(b.label));
  }, []);
  return (
    <select {...props} className="select" autoComplete="country-name">
      <option value="">{contentCopy.chooseCountry}</option>
      {options.map(({ value, label }) => (
        <option value={value} key={value}>
          {label}
        </option>
      ))}
    </select>
  );
}
