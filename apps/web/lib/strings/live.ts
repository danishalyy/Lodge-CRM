export const liveCopy = {
  live: "Live",
  reconnecting: "Reconnecting",
  paused: "Updates paused",
  connection: "Live update connection",
  refresh: "Refresh data",
  updates: (n: number) => `${n} new ${n === 1 ? "update" : "updates"}`,
  finish: "Finish editing before applying updates.",
  checking: "Checking your access…",
  accessError: "Access could not be checked. Try again to continue.",
  retry: "Check access again",
};
