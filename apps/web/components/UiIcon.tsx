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
  BedDouble,
  MessageSquare,
  Star,
  UserRound,
  ContactRound,
  ShieldCheck,
  Network,
  Brush,
  Wrench,
  UtensilsCrossed,
  Compass,
  ArrowLeftRight,
  Fuel,
  PawPrint,
  Binoculars,
  History,
  Sparkles,
  Package,
  Receipt,
  ScrollText,
  Building,
  CalendarRange,
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
  rooms: BedDouble,
  requests: MessageSquare,
  feedback: Star,
  staff: UserRound,
  hr: ContactRound,
  roles: ShieldCheck,
  departments: Network,
  housekeeping: Brush,
  maintenance: Wrench,
  "food-beverage": UtensilsCrossed,
  activities: Compass,
  transfers: ArrowLeftRight,
  fuel: Fuel,
  wildlife: PawPrint,
  ranger: Binoculars,
  memory: History,
  "lodge-ai": Sparkles,
  packages: Package,
  subscriptions: Receipt,
  audit: ScrollText,
  group: Building,
  stays: CalendarRange,
};
export default function UiIcon({ name }: { name: string }) {
  const Icon = icons[name] || ClipboardCheck;
  return <Icon size={19} strokeWidth={1.5} aria-hidden="true" />;
}
export function moduleIcon(key: string) {
  const module = key.split("/").at(-1) || "overview";
  return module === "super-admin" || module === "dashboard"
    ? "overview"
    : module === "guests" || module === "users"
      ? "people"
      : module === "lodges"
        ? "lodge"
        : module === "notifications"
          ? "bell"
          : module === "groups"
            ? "group"
            : module in icons
              ? module
              : "tasks";
}
