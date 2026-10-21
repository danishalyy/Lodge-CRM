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
  let message =
    method === "DELETE" ? "Removed successfully" : "Saved successfully";
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
  toast.success(message, { id: `action:${path}` });
}
