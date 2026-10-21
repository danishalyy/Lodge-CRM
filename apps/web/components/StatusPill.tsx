import { readableLabel } from "@/lib/strings/content";
export function statusTone(value: string) {
  const v = value.toLowerCase();
  if (
    v.includes("expired") ||
    v.includes("urgent") ||
    v.includes("critical") ||
    v.includes("maintenance") ||
    v.includes("suspended")
  )
    return "bad";
  if (
    v.includes("soon") ||
    v.includes("high") ||
    v.includes("overdue") ||
    v.includes("cleaning") ||
    v.includes("inspection") ||
    v.includes("waiting")
  )
    return "warn";
  if (v === "inactive") return "";
  if (
    v.includes("active") ||
    v.includes("ready") ||
    v.includes("completed") ||
    v.includes("progress") ||
    v.includes("synced") ||
    v.includes("occupied")
  )
    return "ok";
  return "";
}
export default function StatusPill({ value }: { value: string }) {
  const t = statusTone(value);
  return (
    <em className={`statusPill ${t}`}>
      <i className={`dot ${t}`}></i>
      {readableLabel(value)}
    </em>
  );
}
