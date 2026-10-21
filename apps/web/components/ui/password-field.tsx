"use client";
import * as React from "react";
import { Eye, EyeOff } from "lucide-react";
import { Field } from "./field";
import { formCopy } from "@/lib/strings/forms";
export function PasswordField({
  label,
  rules = false,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  rules?: boolean;
}) {
  const [visible, setVisible] = React.useState(false);
  const id = React.useId();
  return (
    <div className="passwordField">
      <Field
        label={label}
        helper={
          rules ? (
            <span aria-live="polite">
              {String(props.value || "").length >= 12
                ? formCopy.passwordReady
                : formCopy.passwordRule}
            </span>
          ) : undefined
        }
      >
        <input
          {...props}
          id={props.id || id}
          className="field"
          type={visible ? "text" : "password"}
        />
      </Field>
      <button
        type="button"
        className="iconButton passwordToggle"
        aria-label={visible ? formCopy.hidePassword : formCopy.showPassword}
        aria-pressed={visible}
        aria-controls={props.id || id}
        onClick={() => setVisible(!visible)}
      >
        {visible ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
    </div>
  );
}
