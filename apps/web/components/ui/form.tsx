"use client";
import * as React from "react";
import { formCopy } from "@/lib/strings/forms";
import { withSubmittingForm } from "@/lib/form-submission";
export const FieldErrors = React.createContext<Record<string, string>>({});
export function Form({
  onSubmit,
  children,
  ...props
}: React.FormHTMLAttributes<HTMLFormElement>) {
  const ref = React.useRef<HTMLFormElement>(null);
  const [errors, setErrors] = React.useState<Record<string, string>>({});
  const [summary, setSummary] = React.useState("");
  React.useEffect(() => {
    const form = ref.current;
    const receive = (event: Event) => {
      const next = (event as CustomEvent<Record<string, string>>).detail;
      setErrors(next);
      const control = Array.from(form?.elements ?? []).find(
        (el) =>
          el instanceof HTMLElement && next[el.getAttribute("name") || el.id],
      );
      if (control instanceof HTMLElement) control.focus();
    };
    form?.addEventListener("safarios-field-errors", receive);
    return () => form?.removeEventListener("safarios-field-errors", receive);
  }, []);
  return (
    <FieldErrors.Provider value={errors}>
      <form
        {...props}
        ref={ref}
        noValidate
        onInput={(event) => {
          props.onInput?.(event);
          const control = event.target as HTMLInputElement;
          setErrors((previous) => {
            const next = { ...previous };
            delete next[control.name || control.id];
            return next;
          });
        }}
        onSubmit={(event) => {
          event.preventDefault();
          const next: Record<string, string> = {};
          for (const item of Array.from(event.currentTarget.elements)) {
            if (
              !(
                item instanceof HTMLInputElement ||
                item instanceof HTMLSelectElement ||
                item instanceof HTMLTextAreaElement
              ) ||
              item.disabled ||
              !item.willValidate
            )
              continue;
            const v = item.validity;
            if (!v.valid)
              next[item.name || item.id] = v.valueMissing
                ? formCopy.required
                : v.typeMismatch
                  ? formCopy.email
                  : v.tooShort
                    ? formCopy.short((item as HTMLInputElement).minLength)
                    : v.tooLong
                      ? formCopy.long((item as HTMLInputElement).maxLength)
                      : v.rangeOverflow || v.rangeUnderflow
                        ? formCopy.range
                        : formCopy.invalid;
          }
          setErrors(next);
          setSummary("");
          if (Object.keys(next).length) {
            const first = Array.from(event.currentTarget.elements).find(
              (item) => next[item.getAttribute("name") || item.id],
            );
            if (first instanceof HTMLElement) first.focus();
            return;
          }
          const result: unknown = withSubmittingForm(event.currentTarget, () =>
            onSubmit?.(event),
          );
          if (result instanceof Promise)
            result.catch((error) =>
              setSummary(
                error instanceof Error ? error.message : formCopy.failed,
              ),
            );
        }}
      >
        {children}
        {summary && (
          <p role="alert" className="dangerText">
            {summary}
          </p>
        )}
      </form>
    </FieldErrors.Provider>
  );
}
