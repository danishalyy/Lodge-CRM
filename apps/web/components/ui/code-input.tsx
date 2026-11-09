"use client";
import { useState, type InputHTMLAttributes } from "react";
export function CodeInput(props: InputHTMLAttributes<HTMLInputElement>) {
  const [focused, setFocused] = useState(false),
    [cursor, setCursor] = useState(0);
  const value = String(props.value || "");
  return (
    <div className="codeInput">
      <div className="codeInputBoxes" aria-hidden="true">
        {Array.from({ length: 6 }, (_, i) => (
          <span
            key={i}
            className={focused && i === Math.min(cursor, 5) ? "active" : ""}
          >
            {value[i] || ""}
          </span>
        ))}
      </div>
      <input
        {...props}
        className="field otpField"
        type="text"
        inputMode="numeric"
        pattern="[0-9]{6}"
        maxLength={6}
        autoComplete="one-time-code"
        onFocus={(e) => {
          setFocused(true);
          setCursor(e.currentTarget.selectionStart ?? value.length);
          props.onFocus?.(e);
        }}
        onBlur={(e) => {
          setFocused(false);
          props.onBlur?.(e);
        }}
        onSelect={(e) =>
          setCursor(e.currentTarget.selectionStart ?? value.length)
        }
        onChange={(e) => {
          props.onChange?.(e);
          setCursor(e.currentTarget.selectionStart ?? e.target.value.length);
        }}
      />
    </div>
  );
}
