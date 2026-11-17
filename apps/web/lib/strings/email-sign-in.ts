export const emailSignInCopy = {
  title: "Check your email",
  code: "Email sign-in code",
  sent: (email: string) => `A sign-in code has been queued for ${email}.`,
  hint: "Enter the latest six-digit code in this browser. Never share it with anyone.",
  expires: (seconds: number) =>
    `Code expires in ${Math.ceil(seconds / 60)} min.`,
  expired: "This code has expired. Request a new code.",
  resend: "Send a new code",
  resending: "Requesting code…",
  wait: (seconds: number) => `Send a new code in ${seconds}s`,
  another: "Use another account",
  verify: "Verify and sign in",
  verifying: "Verifying…",
  required: "Password and email verification",
  securityBody:
    "Every sign-in requires your password and a one-time code sent to your registered email. This protection is always enabled.",
  securityHint:
    "Keep access to your email account secure. Authenticator setup and authenticator recovery codes are reserved for Super Admin.",
  email: "Registered email",
  queued: "A new sign-in code has been queued.",
  error: "Unable to verify sign-in. Please try again.",
};
