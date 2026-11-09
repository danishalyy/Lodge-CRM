"use client";
import { useEffect, useRef, useState, type HTMLAttributes } from "react";
import { designCopy } from "@/lib/strings/design";
// Keyboard scrolling is exposed only when columns actually overflow.
export function TableScroll({
  as: Tag = "div",
  children,
  ...props
}: HTMLAttributes<HTMLElement> & { as?: "div" | "section" }) {
  const element = useRef<HTMLElement | null>(null);
  const [overflow, setOverflow] = useState(false);
  useEffect(() => {
    const node = element.current;
    if (!node) return;
    let active = true;
    const measure = () => {
      if (active) setOverflow(node.scrollWidth > node.clientWidth + 1);
    };
    measure();
    const observer =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(measure)
        : null;
    observer?.observe(node);
    const table = node.querySelector("table");
    if (table) observer?.observe(table);
    window.addEventListener("resize", measure);
    void document.fonts?.ready.then(measure);
    return () => {
      active = false;
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [children]);
  return (
    <Tag
      {...props}
      ref={(node) => {
        element.current = node;
      }}
      tabIndex={overflow ? 0 : props.tabIndex}
      role={overflow ? "region" : props.role}
      aria-label={
        overflow
          ? props["aria-label"] || designCopy.tableScroll
          : props["aria-label"]
      }
    >
      {children}
    </Tag>
  );
}
