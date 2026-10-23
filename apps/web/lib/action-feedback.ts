import { accessCopy } from "./strings/access";
import { contentCopy } from "./strings/content";
import { toast } from "sonner";
export function actionFeedback(path: string, method: string, result: any) {
  if (
    !["POST", "PATCH", "PUT", "DELETE"].includes(method) ||
    (!/^\/api\/v1\/(lodges|platform)\//.test(path) &&
      !/^\/api\/v1\/auth\/(sessions|notifications|notification-preferences|mfa\/(enable|disable))(\/|$)/.test(
        path,
      )) ||
    /\/(upload-url|download-url|preview)(\?|$)/.test(path)
  )
    return;
  const resourceNames: Record<string, string> = {
    lodges: "Lodge",
    groups: "Lodge group",
    guests: "Guest",
    rooms: "Room",
    staff: "Staff profile",
    stays: "Stay",
    requests: "Guest request",
    tasks: "Task",
    departments: "Department",
    vehicles: "Vehicle",
    fuel: "Fuel record",
    activities: "Activity",
    transfers: "Transfer",
    wildlife: "Wildlife sighting",
    "housekeeping-jobs": "Housekeeping job",
    maintenance: "Maintenance ticket",
    "maintenance-assets": "Maintenance asset",
    leaves: "Leave request",
    credentials: "Credential",
    training: "Training record",
    shifts: "Shift",
    incidents: "Incident",
    performance: "Performance note",
    "custom-roles": "Role",
    feedback: "Guest feedback",
    meals: "Meal service",
    checklist: "Checklist item",
    comments: "Comment",
    attachments: "Attachment",
    parts: "Maintenance part",
  };
  const segments = path.split("/");
  const resourceKey = [...segments]
    .reverse()
    .find((segment) => resourceNames[segment]);
  const resource = resourceKey ? resourceNames[resourceKey] : "Record";
  let message =
    method === "DELETE"
      ? contentCopy.removed(resource)
      : method === "POST"
        ? contentCopy.created(resource)
        : contentCopy.updated(resource);
  if (/\/platform\/lodges$/.test(path) && method === "POST")
    message = "Lodge registered";
  if (
    /\/(invite|invitation|resend)(\/|$)/.test(path) ||
    result?.activation_email_queued
  )
    message = result?.activation_token
      ? "Private invitation link created"
      : result?.delivery_status === "already_active"
        ? "Account already active"
        : "Invitation queued";
  else if (path.endsWith("/retry")) message = "Delivery queued for retry";
  else if (path.endsWith("/email/test")) message = "Test email queued";
  else if (path.endsWith("/branding")) message = "Lodge branding saved";
  else if (path.endsWith("/revoke-access")) message = "Account access removed";
  else if (path.endsWith("/restore-access"))
    message = "Account access restored";
  else if (path.endsWith("/subscription")) message = "Subscription updated";
  else if (path.endsWith("/entitlements"))
    message = "Feature availability updated";
  if (path.endsWith("/notification-preferences"))
    message = "Notification preferences saved";
  else if (path.endsWith("/read-all"))
    message = "All notifications marked read";
  else if (path.endsWith("/read")) message = "Notification marked read";
  else if (path.endsWith("/archive")) message = "Notification archived";
  else if (path.includes("/auth/sessions/") && method === "DELETE")
    message = "Session access removed";
  else if (path.endsWith("/mfa/enable")) message = "Authenticator enabled";
  else if (path.endsWith("/mfa/disable")) message = "Authenticator disabled";
  if (/\/platform\/lodges$/.test(path) && method === "POST")
    message = "Lodge registered";
  if (path.endsWith("/preferences")) message = "Lodge preferences saved";
  if (path.endsWith("/access-reviews"))
    message = result?.already_pending
      ? accessCopy.reviewPending
      : accessCopy.reviewSent;
  if (/\/platform\/plans\//.test(path)) message = accessCopy.packageSaved;
  toast.success(message, { id: `action:${path}` });
}
