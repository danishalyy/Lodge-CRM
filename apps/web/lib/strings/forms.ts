// English source catalogue. Keep validation copy here for future locale catalogues.
export const formCopy = {
  required: "This field is required.",
  email: "Enter a valid email address.",
  invalid: "Check this value.",
  short: (length: number) => `Use at least ${length} characters.`,
  long: (length: number) => `Use no more than ${length} characters.`,
  range: "Enter a value within the allowed range.",
  review: "Please check the highlighted fields.",
  forbidden: "You do not have permission to perform this action.",
  expired: "Your session has expired. Please sign in again.",
  conflict: "This record has changed or already exists. Refresh and try again.",
  unavailable: "Something went wrong. Please try again shortly.",
  failed: "We could not complete this request. Please try again.",
  connection: "Connection interrupted. Check the record before trying again.",
  showPassword: "Show password",
  hidePassword: "Hide password",
  passwordRule:
    "Use at least 12 characters. A unique passphrase is a good choice.",
  passwordReady: "At least 12 characters — ready.",
};
