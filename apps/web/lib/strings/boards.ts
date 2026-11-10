export const boardCopy = {
  board: "Status board",
  cards: "Cards",
  view: "Workflow view",
  move: (title: string) => `Move ${title}`,
  moveTo: (title: string) => `Move to… ${title}`,
  choose: "Move to…",
  collapse: (label: string) => `Collapse ${label}`,
  expand: (label: string) => `Expand ${label}`,
  empty: "No records",
  instructions:
    "Press Space to pick up a card. Use Left and Right arrows to choose a column. Press Space to drop, or Escape to cancel. You can also use the Move to menu.",
  picked: (title: string) =>
    `${title} picked up. Use Left and Right arrows to choose a column.`,
  over: (label: string) => `Destination: ${label}. Press Space to drop.`,
  refused: (label: string) => `Cannot move to ${label}.`,
  moved: (title: string, label: string) => `${title} moved to ${label}.`,
  failed: (title: string) =>
    `${title} was not moved. Review the message and try a permitted action.`,
  cancelled: "Move cancelled.",
  saving: "Saving move…",
  cancelTitle: "Cancel this record?",
  cancelDescription:
    "Cancelling ends this workflow. Review the record before continuing.",
  cancelAction: "Cancel record",
};
