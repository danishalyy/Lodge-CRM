// Presentation hints only. The API re-authorizes every move, including record
// scope, required fields, checklist/proof, inspection and occupancy constraints.
export const workflowTransitions: Record<
  string,
  Record<string, readonly string[]>
> = {
  tasks: {
    created: ["assigned", "cancelled"],
    assigned: ["accepted", "cancelled"],
    accepted: ["started", "cancelled"],
    started: ["completed", "cancelled"],
    completed: [],
    cancelled: [],
  },
  requests: {
    open: ["assigned", "in_progress", "cancelled"],
    assigned: ["in_progress", "waiting", "cancelled"],
    in_progress: ["waiting", "resolved", "cancelled"],
    waiting: ["in_progress", "resolved", "cancelled"],
    resolved: [],
    cancelled: [],
  },
  maintenance: {
    open: ["assigned", "in_progress", "cancelled"],
    assigned: ["in_progress", "waiting", "cancelled"],
    in_progress: ["waiting", "completed", "cancelled"],
    waiting: ["in_progress", "completed", "cancelled"],
    completed: [],
    cancelled: [],
  },
  housekeeping: {
    assigned: ["accepted", "in_progress", "cancelled"],
    accepted: ["in_progress", "cancelled"],
    in_progress: ["awaiting_inspection", "completed", "cancelled"],
    awaiting_inspection: ["completed", "in_progress", "cancelled"],
    completed: [],
    cancelled: [],
  },
};
export const roomStatuses = [
  "available",
  "occupied",
  "cleaning",
  "awaiting_inspection",
  "ready",
  "maintenance",
  "out_of_service",
] as const;
export function workflowColumns(module: string) {
  return Object.keys(workflowTransitions[module] || {});
}
export function nextStatuses(module: string, status: string) {
  return workflowTransitions[module]?.[status] || [];
}
