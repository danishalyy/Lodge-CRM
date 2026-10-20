import {
  ArrowUpRight,
  LayoutDashboard,
  Building2,
  Users,
  ClipboardCheck,
  Settings,
  ChartNoAxesCombined,
  Car,
  CalendarDays,
  Leaf,
  Search,
  Bell,
  Menu,
  X,
  type LucideIcon,
} from "lucide-react";
const icons: Record<string, LucideIcon> = {
  arrow: ArrowUpRight,
  overview: LayoutDashboard,
  lodge: Building2,
  people: Users,
  tasks: ClipboardCheck,
  settings: Settings,
  reports: ChartNoAxesCombined,
  fleet: Car,
  calendar: CalendarDays,
  leaf: Leaf,
  search: Search,
  bell: Bell,
  menu: Menu,
  close: X,
};
export default function UiIcon({ name }: { name: string }) {
  const Icon = icons[name] || ClipboardCheck;
  return <Icon size={19} strokeWidth={1.5} aria-hidden="true" />;
}
export function moduleIcon(key: string) {
  return ["guests", "staff", "hr", "roles"].includes(key)
    ? "people"
    : ["rooms", "housekeeping", "lodges"].includes(key)
      ? "lodge"
      : ["activities", "stays", "transfers"].includes(key)
        ? "calendar"
        : ["fleet", "fuel", "maintenance"].includes(key)
          ? "fleet"
          : ["wildlife", "ranger"].includes(key)
            ? "leaf"
            : [
                  "reports",
                  "memory",
                  "audit",
                  "packages",
                  "subscriptions",
                ].includes(key)
              ? "reports"
              : key === "settings"
                ? "settings"
                : key === "dashboard" || key === ""
                  ? "overview"
                  : "tasks";
}
