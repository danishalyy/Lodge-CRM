// Only set during the synchronous submit handler. Each request captures its own
// originating form before awaiting the network, so concurrent forms stay isolated.
let submittingForm: HTMLFormElement | null = null;
export function withSubmittingForm<T>(
  form: HTMLFormElement,
  submit: () => T,
): T {
  const previous = submittingForm;
  submittingForm = form;
  try {
    return submit();
  } finally {
    submittingForm = previous;
  }
}
export function originatingForm(): HTMLFormElement | null {
  if (submittingForm) return submittingForm;
  return typeof document === "undefined"
    ? null
    : (document.activeElement?.closest("form") ?? null);
}
