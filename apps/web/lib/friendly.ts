import { readableLabel } from "@/lib/strings/content";

// Buttons should say what will happen ("Start cleaning"), not name the next
// status ("In progress"). Keys are "from>to" first, then just "to".
const actions: Record<string, Record<string, string>> = {
  tasks: {
    assigned: "Assign",
    accepted: "Accept task",
    started: "Start",
    completed: "Mark done",
  },
  requests: {
    assigned: "Assign",
    in_progress: "Start work",
    "waiting>in_progress": "Resume",
    waiting: "Put on hold",
    resolved: "Mark resolved",
  },
  maintenance: {
    in_progress: "Start repair",
    "waiting>in_progress": "Resume repair",
    waiting: "Put on hold",
    completed: "Mark fixed",
  },
  housekeeping: {
    accepted: "Accept job",
    in_progress: "Start cleaning",
    awaiting_inspection: "Ready for inspection",
    completed: "Passed inspection",
  },
  stays: {
    arriving: "Guest is arriving",
    in_house: "Check in",
    departing: "Start check-out",
    completed: "Check out",
  },
};

export function actionLabel(module: string, to: string, from?: string): string {
  const m = actions[module] || {};
  return (from && m[`${from}>${to}`]) || m[to] || readableLabel(to);
}
