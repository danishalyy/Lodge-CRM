# Plain-language and ease-of-use pass

Goal: someone who has never used the app should know where they are, what a button will do, and what to do next. Colours, layout system and permissions are unchanged. Only wording and a few layout details changed.

## Buttons say what will happen
`lib/friendly.ts` (`actionLabel`) replaces buttons that named the *next status* ("Assigned", "In progress") with actions:
Tasks: Assign, Accept task, Start, Mark done. Requests: Assign, Start work, Put on hold, Resume, Mark resolved. Maintenance: Start repair, Resume repair, Put on hold, Mark fixed. Housekeeping: Accept job, Start cleaning, Ready for inspection, Passed inspection. Stays: Guest is arriving, Check in, Start check-out, Check out.
Add buttons: "+ Task" is now "Add task" (same for guest, stay, vehicle, request, room, staff member, cleaning job, fuel record, transfer, feedback, activity, department, meal service); "+ Ticket" is "Report a problem"; "+ Sighting" is "Record sighting".

## Menu names
Command Centre → Home, Guest CRM → Guests, Guest Feedback → Feedback, Staff HR → Staff Records, Roles & Permissions → Roles & Access, Operational Memory → Activity History, Ranger View → Ranger Schedule, Knowledge Library → Lodge Documents, group "Insight" → Reports & History. Page titles match (Housekeeping workflow → Housekeeping, Event History → Activity History).

## Page descriptions
Every page subtitle was rewritten in one short, everyday sentence (for example Rooms: "See which rooms are free, occupied, being cleaned or ready for the next guest."). Technical words (authoritative, lifecycle, workflow) removed.

## Smaller clarity changes
- Status "Created" now reads "New"; "Started" reads "In progress".
- Boards: "Move to…" is "Change status…"; empty columns say "Nothing here yet".
- Table column "Workflow" is "Next step". Search placeholder is "Search…".
- The sidebar was simplified further (see "Calm shell" in `INTERACTIVITY_QA.md`): short list, sections open one at a time, search moved into the sidebar, no top-bar search or live indicator, no visible shortcut guide.
- Tasks: the Calendar button sits on the same row as the All/My/Overdue tabs.
- Phones: the rarely used "Saved views" menu is hidden.

## Tests
`e2e/account-isolation.test.cjs` was updated for the new names. It could not be run in the build environment (it needs the full browser test stack), so run `npm run test:e2e` or your usual e2e command once.
