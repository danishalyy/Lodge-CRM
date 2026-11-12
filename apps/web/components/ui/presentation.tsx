"use client";
import { motion, useReducedMotion } from "framer-motion";
import Link from "next/link";
import type { ReactNode } from "react";
import { uiCopy as c } from "@/lib/strings/redesign";
export function PageHeader({
  label,
  title,
  description,
  action,
}: {
  label?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="pageHeader">
      <div>
        {label && <span className="eyebrow">{label}</span>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action && <div className="headerActions">{action}</div>}
    </div>
  );
}
export function KpiCard({
  label,
  value,
  hint,
  href,
  attention = false,
}: {
  label: string;
  value?: number | null;
  hint: string;
  href?: string;
  attention?: boolean;
}) {
  const reduced = useReducedMotion();
  const content = (
    <>
      <div className="metricTop">
        <span>{label}</span>
      </div>
      <motion.strong
        key={String(value)}
        initial={reduced ? false : { opacity: 0.65, y: 2 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
      >
        {value == null ? "—" : value.toLocaleString()}
      </motion.strong>
      <small>{value == null ? c.unavailable : hint}</small>
    </>
  );
  return href ? (
    <Link
      href={href}
      className={
        "metricCard premiumMetric kpiLink" + (attention ? " attention" : "")
      }
    >
      {content}
    </Link>
  ) : (
    <div
      className={
        "metricCard premiumMetric kpiLink" + (attention ? " attention" : "")
      }
    >
      {content}
    </div>
  );
}
