/** Choose only a workspace the activated/signed-in account can actually access. */
export function accountHome(user: any): string {
  if (user.is_super_admin)
    return user.mfa_enabled ? "/super-admin" : "/settings";
  if (user.groups?.length) return "/group";
  const member = user.memberships?.[0];
  const permissions = member?.permissions || [];
  const fieldRoutes: Record<string, [string, string, string]> = {
    ranger: ["ranger", "ranger.view", "ranger"],
    driver: ["transfers", "transfers.view", "transfers"],
    housekeeping: ["housekeeping", "housekeeping.view", "housekeeping"],
    maintenance: ["maintenance", "maintenance.view", "maintenance"],
    fb: ["food-beverage", "fb.view", "fb_operations"],
    general_staff: ["tasks", "tasks.view", "tasks"],
  };
  const field = fieldRoutes[member?.role_key];
  if (
    field &&
    permissions.includes(field[1]) &&
    member?.entitlements?.includes(field[2])
  )
    return "/" + field[0];

  const entitlements = member?.entitlements || [];
  for (const [path, permission, feature] of [
    ["dashboard", "dashboard.view", "dashboard"],
    ["tasks", "tasks.view", "tasks"],
    ["ranger", "ranger.view", "ranger"],
    ["housekeeping", "housekeeping.view", "housekeeping"],
    ["maintenance", "maintenance.view", "maintenance"],
    ["guests", "guests.view", "guests"],
    ["transfers", "transfers.view", "transfers"],
    ["food-beverage", "fb.view", "fb_operations"],
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
