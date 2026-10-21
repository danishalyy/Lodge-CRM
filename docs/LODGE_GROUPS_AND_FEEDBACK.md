# Lodge groups, feature visibility and action feedback

The owner reintroduced Group Admin / Owner and multi-lodge management on 21 October 2026. This instruction supersedes the earlier exclusion in the workflow document and previous scope reviews. Ordinary Lodge Admin and staff accounts remain confined to one lodge.

## Set up a group

1. Super Admin opens **Lodge groups → Create group**, enters a group name and the Group Admin’s name/email, and selects existing lodges.
2. A new Group Admin receives the same expiring, single-use password setup invitation used by other accounts. Use a separate email from an ordinary Lodge Admin/staff account. An existing Group Admin can own additional groups with the same account.
3. After activation/sign-in, the owner lands on **Group overview**. It lists only explicitly assigned lodges, subscription status and enabled operational totals. Owners with several groups can switch groups.
4. **Open lodge** enters that lodge’s workspace. The lodge selector switches between authorized lodges, and **Group overview** returns to the portfolio. A Group Admin can invite separate Lodge Admin accounts, see pending setup, resend invitations, and remove/restore Lodge Admin access from the portfolio. Removing access revokes existing sessions and invalidates pending setup links. They can also use the lodge’s operational staff/role management.
5. Super Admin can change lodge assignments or suspend/restore the group. Removing a lodge or suspending the group immediately removes the owner’s corresponding API access, including existing sessions. Local Lodge Admins and staff retain their own accounts.

Super Admin still provisions lodges, subscriptions and lodge branding. Group Admin is not Super Admin: platform user management, subscription overrides, other groups and unassigned lodges stay inaccessible. Each lodge retains its own subscription and entitlements; membership in a group does not unlock disabled features. Group totals include only authorized modules that are enabled in the relevant lodge. This portfolio provides operational counts, not a new financial consolidation or billing system.

A lodge can belong to one group. To move it, remove it from its current group before adding it elsewhere. Suspending a group keeps its lodge assignments; it does not suspend the lodges’ subscriptions. Groups may initially have no lodges. Existing pending owners can receive additional groups without invalidating their current setup link.

## Disabled features

Navigation, mobile menus and command search use effective server entitlements, including Super Admin overrides. Disabled screens are omitted. Opening a disabled screen’s saved URL returns the user to an available workspace screen without mounting the disabled page. Role-denied access remains protected separately.

HR roster, confidential incidents/performance, advanced task controls, task attachments, workshop/assets and advanced housekeeping controls and report sections follow their own feature gates. The app avoids loading disabled subfeatures alongside enabled ones. The workspace refreshes access on focus and periodically; a server feature denial refreshes current capabilities and hides the affected view rather than displaying the raw subscription error. Server-side subscription, permission and tenant guards remain in force.

## Action popups

The shared API client displays a Sonner success popup after the server confirms a mutation, including saves, removals, subscription/feature changes, invitations, delivery retries, notification actions and session removal. Failed changes show an error; failed or preview requests never produce a save-success popup. Invitation wording says **queued**, not delivered. Existing inline validation remains available.

Shared feedback applies to future screens using `lib/api.ts`. Client-only actions may provide their own feedback. Do not add another success toast around an API call already covered by the shared handler. Destructive actions must still ask for confirmation before the request.

## Updating an installation

Keep your existing `infra/.env`, database volumes and encryption keys. From the repository root:

```sh
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

The migration adds group ownership, a Group Admin role, explicit per-lodge memberships, and database checks that preserve the one-lodge restriction for ordinary accounts. Database role grants must finish successfully. A downgrade refuses to silently discard real multi-lodge memberships.

[Invitation/email setup](EMAIL_AND_INVITATIONS.md) · [Role access](ROLE_ACCESS_MATRIX.md)
