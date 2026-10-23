"use client";
import * as React from "react";
import { ChevronDown } from "lucide-react";
import { contentCopy } from "@/lib/strings/content";
import { formCopy } from "@/lib/strings/forms";
export function TimezonePicker(
  props: React.InputHTMLAttributes<HTMLInputElement>,
) {
  const listId = React.useId();
  const input = React.useRef<HTMLInputElement>(null);
  const [value, setValue] = React.useState(
    String(
      props.value ??
        props.defaultValue ??
        Intl.DateTimeFormat().resolvedOptions().timeZone,
    ),
  );
  const [open, setOpen] = React.useState(false),
    [index, setIndex] = React.useState(0);
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
  const options = zones.includes(value)
    ? zones
    : zones.filter((zone) =>
        zone
          .toLowerCase()
          .replaceAll("_", " ")
          .includes(value.toLowerCase().replaceAll("_", " ")),
      );
  React.useEffect(() => {
    input.current?.setCustomValidity(
      zones.includes(value) ? "" : formCopy.timezoneChoice,
    );
  }, [value, zones]);
  React.useEffect(() => {
    if (props.value !== undefined) setValue(String(props.value));
  }, [props.value]);
  React.useEffect(() => {
    if (open)
      document
        .getElementById(`${listId}-${index}`)
        ?.scrollIntoView({ block: "nearest" });
  }, [index, open, listId]);
  function choose(zone: string) {
    setValue(zone);
    setOpen(false);
    input.current?.setCustomValidity("");
    input.current?.focus();
    input.current?.dispatchEvent(new Event("input", { bubbles: true }));
  }
  return (
    <div className="timezoneCombobox">
      <input
        {...props}
        ref={input}
        value={value}
        defaultValue={undefined}
        className="field"
        role="combobox"
        aria-autocomplete="list"
        aria-expanded={open}
        aria-controls={listId}
        aria-activedescendant={
          open && options[index] ? `${listId}-${index}` : undefined
        }
        autoComplete="off"
        placeholder={contentCopy.timezone}
        onClick={(e) => {
          setOpen(true);
          props.onClick?.(e);
        }}
        onFocus={(e) => {
          setOpen(true);
          setIndex(Math.max(0, options.indexOf(value)));
          props.onFocus?.(e);
        }}
        onBlur={(e) => {
          setOpen(false);
          props.onBlur?.(e);
        }}
        onChange={(e) => {
          setValue(e.target.value);
          setOpen(true);
          setIndex(Math.max(0, zones.indexOf(e.target.value)));
          props.onChange?.(e);
        }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            setOpen(true);
            setIndex((i) =>
              Math.max(
                0,
                Math.min(
                  options.length - 1,
                  i + (e.key === "ArrowDown" ? 1 : -1),
                ),
              ),
            );
          } else if (e.key === "Enter" && open && options[index]) {
            e.preventDefault();
            choose(options[index]);
          } else if (e.key === "Escape" && open) {
            e.preventDefault();
            e.stopPropagation();
            setOpen(false);
          }
          props.onKeyDown?.(e);
        }}
      />
      <ChevronDown className="timezoneChevron" size={16} aria-hidden="true" />
      {open && (
        <div className="timezoneOptions">
          <div role="listbox" id={listId} aria-label={contentCopy.timezone}>
            {options.map((zone, i) => (
              <div
                id={`${listId}-${i}`}
                key={zone}
                role="option"
                aria-selected={i === index}
                onPointerDown={(e) => e.preventDefault()}
                onClick={() => choose(zone)}
              >
                {zone.replaceAll("_", " ")}
              </div>
            ))}
          </div>
          {!options.length && <p role="status">{contentCopy.noTimezones}</p>}
        </div>
      )}
    </div>
  );
}
