// English source catalogue. Keep validation copy here for future locale catalogues.
export const formCopy = {
  timezoneChoice: "Choose a time zone from the list.",
  date: "Enter a valid date.",
  number: "Enter a valid number.",
  wholeNumber: "Enter a whole number.",
  identifier: "Choose a valid record.",
  choice: "Choose one of the available options.",
  pattern: "Use the requested format.",
  minimum: (n: number, strict = false) =>
    `Enter a value ${strict ? "greater than" : "of at least"} ${n}.`,
  maximum: (n: number, strict = false) =>
    `Enter a value ${strict ? "less than" : "of at most"} ${n}.`,
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
