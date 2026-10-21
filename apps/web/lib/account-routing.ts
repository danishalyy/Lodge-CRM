/** Choose only a workspace the activated/signed-in account can actually access. */
export function accountHome(user: any): string {
  if (user.is_super_admin)
    return user.mfa_enabled ? "/super-admin" : "/settings";
  const member = user.memberships?.[0];
  const permissions = member?.permissions || [];
  const entitlements = member?.entitlements || [];
  for (const [path, permission, feature] of [
    ["dashboard", "dashboard.view", "dashboard"],
    ["tasks", "tasks.view", "tasks"],
    ["ranger", "ranger.view", "ranger"],
    ["housekeeping", "housekeeping.view", "housekeeping"],
    ["maintenance", "maintenance.view", "maintenance"],
    ["guests", "guests.view", "guests"],
    ["transfers", "transfers.view", "transfers"],
    ["food-beverage", "fb.view", "fb"],
    ["reports", "reports.view", "reports"],
  ] as const) {
    if (permissions.includes(permission) && entitlements.includes(feature))
      return "/" + path;
  }
  return "/settings";
}
export function takeAccountLinkToken(): string {
  const token =
    new URLSearchParams(window.location.hash.slice(1)).get("token") ||
    new URLSearchParams(window.location.search).get("token") ||
    "";
  if (token) window.history.replaceState(null, "", window.location.pathname);
  return token;
}
