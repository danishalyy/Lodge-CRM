export const aiCopy = {
  title: "Ask Lodge AI",
  groupTitle: "Ask Group Owner AI",
  groupIntro:
    "Compare authorised operational metrics across your explicitly assigned lodges.",
  compareGroup: "Compare lodges with AI",
  groupScope: "Group scope",
  metricCoverage: "Metric coverage",
  includedLodges: "Included lodges",
  excludedLodges: (count: number) =>
    `${count} assigned ${count === 1 ? "lodge is" : "lodges are"} excluded because AI or subscription access is unavailable.`,
  groupCoverage:
    "Each metric uses only lodges with the required permission and feature. Missing values are unavailable; current vehicle counts do not measure downtime duration.",
  eyebrow: "LODGE INTELLIGENCE",
  intro: "Ask about your lodge’s authorised operational information.",
  scope: "Current lodge",
  conversations: "Private conversations",
  newConversation: "New conversation",
  question: "Your question",
  send: "Ask Lodge AI",
  busy: "Checking authorised sources…",
  loading: "Checking AI availability…",
  unavailable: "Lodge AI is unavailable",
  unavailableBody:
    "Your operational workspace continues to work. Try again when the AI connection and approved data sources are available.",
  testOnly: "AI test mode",
  testOnlyBody:
    "The deterministic provider is for automated tests. It is not a real AI assistant.",
  empty:
    "Start with an operational question. Answers use only the sources your account can access.",
  retry: "Check again",
  sources: "Sources checked",
  live: "Live operational data",
  memory: "Recorded history",
  partial: "Limited coverage",
  period: "History period",
  event: "Recorded event",
  noSources: "No source was supplied for this response.",
  you: "You",
  assistant: "Lodge AI",
  failed: "Unable to complete this AI request.",
  historyFailed:
    "Unable to load this conversation. Your access may have changed.",
  suggestion: "Suggested questions",
  noHistory: "No conversations for your current access.",
  emptyReply: "The AI returned no usable response.",
};
