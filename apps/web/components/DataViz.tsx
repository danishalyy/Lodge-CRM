"use client";
import {
  ResponsiveContainer,
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { useState } from "react";
import { Calendar } from "./ui/calendar";
import { useReducedMotion } from "framer-motion";

export type BarDatum = { label: string; value: number; hint?: string };

export function BarChart({
  data,
  max: providedMax,
}: {
  data: BarDatum[];
  max?: number;
}) {
  const reduced = useReducedMotion();
  if (!data.length)
    return <div className="empty">No activity recorded yet.</div>;
  return (
    <div
      className="premiumChart"
      role="img"
      aria-label={data.map((d) => `${d.label}: ${d.value}`).join(", ")}
    >
      <ResponsiveContainer width="100%" height={220}>
        <RechartsBarChart data={data}>
          <CartesianGrid vertical={false} stroke="var(--bd)" />
          <XAxis
            dataKey="label"
            tick={{ fill: "var(--tx2)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[0, providedMax || "auto"]}
            tick={{ fill: "var(--tx2)", fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              background: "var(--side)",
              border: "1px solid var(--bd)",
              borderRadius: 14,
              color: "var(--tx)",
            }}
            cursor={{ fill: "var(--sec)" }}
          />
          <Bar
            dataKey="value"
            fill="var(--accent)"
            radius={[8, 8, 0, 0]}
            isAnimationActive={!reduced}
          />
        </RechartsBarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function RingChart({
  value,
  total,
  label,
}: {
  value: number;
  total: number;
  label: string;
}) {
  const safeTotal = Math.max(total, 1),
    pct = Math.max(0, Math.min(100, Math.round((value / safeTotal) * 100)));
  const r = 40,
    c = 2 * Math.PI * r,
    dash = (c * pct) / 100;
  return (
    <div className="ringChart" role="img" aria-label={`${label}: ${pct}%`}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle className="ringTrack" cx="50" cy="50" r={r} />
        <circle
          className="ringValue"
          cx="50"
          cy="50"
          r={r}
          strokeDasharray={`${dash} ${c - dash}`}
          transform="rotate(-90 50 50)"
        />
      </svg>
      <div className="ringCenter">
        <strong>{pct}%</strong>
        <span>{label}</span>
      </div>
    </div>
  );
}

export type CalendarEvent = {
  date: string;
  label: string;
  kind?: "arrival" | "departure" | "activity" | "transfer" | "other";
};
const key = (d: Date) => {
  const y = d.getFullYear(),
    m = String(d.getMonth() + 1).padStart(2, "0"),
    day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
};
export function OperationsCalendar({
  events = [],
  monthDate = new Date(),
}: {
  events?: CalendarEvent[];
  monthDate?: Date;
}) {
  const [selected, setSelected] = useState<Date | undefined>();
  const dayEvents = selected
    ? events.filter((e) => e.date === key(selected))
    : events.filter((e) => e.date.startsWith(key(monthDate).slice(0, 7)));
  return (
    <div className="operationsDatePicker">
      <Calendar
        mode="single"
        defaultMonth={monthDate}
        selected={selected}
        onSelect={setSelected}
        modifiers={{
          scheduled: events.map((e) => {
            const [y, m, d] = e.date.split("-").map(Number);
            return new Date(y, m - 1, d);
          }),
        }}
        modifiersClassNames={{ scheduled: "scheduledDay" }}
      />
      <div className="calendarAgenda" aria-live="polite">
        <h3>
          {selected
            ? selected.toLocaleDateString(undefined, {
                month: "long",
                day: "numeric",
              })
            : "This month"}
        </h3>
        {dayEvents.length ? (
          dayEvents.map((e, i) => (
            <div className="calendarAgendaItem" key={i}>
              <span>{e.date}</span>
              <strong>{e.label}</strong>
            </div>
          ))
        ) : (
          <p className="textSecondary">No scheduled events for this period.</p>
        )}
      </div>
    </div>
  );
}
