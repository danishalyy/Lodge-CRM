"use client";
import * as React from "react";
import { FieldErrors } from "./form";
type ControlProps = React.InputHTMLAttributes<HTMLInputElement>;
export function Field({
  label,
  helper,
  error,
  children,
}: {
  label: React.ReactNode;
  helper?: React.ReactNode;
  error?: string;
  children: React.ReactElement<ControlProps>;
}) {
  const generated = React.useId();
  const errors = React.useContext(FieldErrors);
  const p = children.props;
  const id = p.id || generated;
  const name = p.name || (typeof label === "string" ? label.toLowerCase().replace(/[^a-z0-9]+/g, "_") : id);
  const message = error || errors[name];
  const kind =
    p.name ||
    (typeof label === "string" ? label.toLowerCase().replaceAll(" ", "_") : "");
  const semantics: Partial<ControlProps> = /email/.test(kind)
    ? { type: "email", inputMode: "email", autoComplete: "email" }
    : /phone|telephone/.test(kind)
      ? { type: "tel", inputMode: "tel", autoComplete: "tel" }
      : kind === "first_name"
        ? { autoComplete: "given-name" }
        : kind === "last_name"
          ? { autoComplete: "family-name" }
          : /birth|bday/.test(kind)
            ? { type: "date", autoComplete: "bday" }
            : /country|nationality/.test(kind)
              ? { autoComplete: "country-name" }
              : {};
  const described =
    [
      p["aria-describedby"],
      helper ? `${id}-hint` : "",
      message ? `${id}-error` : "",
    ]
      .filter(Boolean)
      .join(" ") || undefined;
  return (
    <div className="formField">
      <label className="fieldLabel" htmlFor={id}>
        {label}
        {p.required && <span className="requiredMarker" aria-hidden="true" />}
      </label>
      {React.cloneElement(children, {
        ...semantics,
        ...p,
        id,
        name,
        "aria-required": p.required || undefined,
        "aria-invalid": message ? true : p["aria-invalid"],
        "aria-describedby": described,
      })}
      {helper && (
        <div className="fieldHint" id={`${id}-hint`}>
          {helper}
        </div>
      )}
      {message && (
        <div className="fieldError dangerText" id={`${id}-error`} role="alert">
          {message}
        </div>
      )}
    </div>
  );
}
