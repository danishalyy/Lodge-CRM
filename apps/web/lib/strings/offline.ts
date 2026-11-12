export const offlineCopy = {
  complete: "Complete",
  incomplete: "Incomplete",
  online: "Online",
  offline: "Offline",
  syncing: "Syncing",
  failed: "Needs attention",
  synced: "Synced",
  queued: "Queued",
  rejected: "Rejected",
  title: "Work on this device",
  description:
    "Queued changes belong to your current account and lodge. SafariOS checks your access and the current record before applying each one.",
  empty: "No queued work on this device.",
  open: "Review device sync",
  retry: "Retry",
  discard: "Discard",
  removed: "Removed from this device",
  stateChanged:
    "This change is syncing or has already finished. Review its current status before trying again.",
  removeCompleted: "Remove from device",
  removeCompletedConfirm:
    "Remove this completed item from this device? The lodge record will remain saved.",
  close: "Close device sync",
  discardConfirm:
    "Discard this queued change? It will not be sent to the lodge.",
  waiting: "Saved on this device. Waiting to sync.",
  unavailable: "This action needs an internet connection.",
  feature: "Offline work is not included in this lodge’s current access.",
  localSignout:
    "This device is signed out. Reconnect to finish ending the server session before signing in again.",
  signIn: "Reconnect and sign in to sync your queued work.",
  connectionError:
    "Connection interrupted. Your change remains queued on this device.",
  storageError:
    "SafariOS could not access device storage. Close older tabs or try again.",
  count: (n: number) => `${n} queued`,
  connection: "Device sync status",
  kinds: {
    "task.status": "Task status",
    "task.checklist": "Task checklist",
    "housekeeping.status": "Housekeeping status",
    "transfer.status": "Transfer status",
    "wildlife.sighting": "Wildlife sighting",
  },
};
export const pushCopy = {
  title: "Browser notifications",
  description:
    "Receive a private SafariOS alert on this device. Guest names, room details and message contents are never included.",
  enable: "Enable on this device",
  disable: "Turn off on this device",
  enabled: "Enabled on this device",
  unsupported: "This browser does not support push notifications.",
  unconfigured:
    "Browser notifications are not configured for this installation yet.",
  denied:
    "Notifications are blocked. You can allow them in your browser’s site settings.",
  ios: "On iPhone or iPad, add SafariOS to your Home Screen first, then open it from there to enable notifications.",
  categories: {
    task_assigned: "Task assignments",
    request: "Guest requests",
    overdue: "Overdue work",
    arrival: "Arrivals",
  },
  saved: "Notification preferences updated",
  save: "Save preferences",
  busy: "Updating…",
  error: "Browser notifications could not be updated. Try again.",
};
