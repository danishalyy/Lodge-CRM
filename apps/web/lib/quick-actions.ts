export const NEW_TASK_EVENT = "safarios-new-task";

// Opens the New task form. When the user is already on the Tasks page the URL
// does not change, so a plain navigation would do nothing; tell the page instead.
export function goToNewTask(
  router: { push: (href: string) => void },
  pathname: string | null,
) {
  if (pathname === "/tasks") window.dispatchEvent(new Event(NEW_TASK_EVENT));
  else router.push("/tasks?create=1");
}
