export const onboardingCopy = {
  setupTitle: "Make this lodge your own",
  setupBody: "A few essentials will get your team ready for its first stay.",
  steps: [
    {
      key: "rooms",
      label: "Add rooms",
      description: "Set up the rooms and units guests can stay in.",
      permission: "units.view",
      manage: "units.manage",
      feature: "units",
    },
    {
      key: "guests",
      label: "Add guests",
      description: "Create your first guest profile.",
      permission: "guests.view",
      manage: "guests.manage",
      feature: "guests",
    },
    {
      key: "staff",
      label: "Invite staff",
      description: "Give your team their own secure accounts.",
      permission: "staff.view",
      manage: "staff.manage",
      feature: "staff",
    },
    {
      key: "stays",
      label: "Create first stay",
      description: "Connect a guest, a room and their travel dates.",
      permission: "stays.view",
      manage: "stays.manage",
      feature: "stays",
    },
  ],
  progress: (done: number, total: number) =>
    `${done} of ${total} essentials ready`,
  retry: "Unable to check setup progress. Try again.",
  lockedTitle: (plan: string) => `Available on ${plan}`,
  lockedBody:
    "This feature is not included in your current workspace access. Your lodge administrator or SafariOS provider can review your subscription and enabled features.",
  contact: "Request access review",
  contactTitle: "Ask your administrator",
  contactBody:
    "Contact the person who invited you or your SafariOS subscription provider. Ask them to review this lodge’s package and feature settings.",
  securityTitle: "Welcome to your platform account",
  securityBody:
    "Your invitation is activated. Super Admin accounts must enable an authenticator before opening the platform console. Add SafariOS to your authenticator, enter its verification code, then open the console.",
  openConsole: "Open platform console",
};
