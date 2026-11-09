# Remaining delivery after the conversational workspace

The owner reaffirmed the original documents as the acceptance criteria. [The current 63-item source map](REQUIREMENTS_DELIVERY.md) governs priorities; optional additions do not replace documented workflows.

The owner requested completion of the remaining work on 9 November 2026. Deliver in tested phases, preserving the current stack, permissions, RLS, MFA, subscription gates and charcoal UI. The owner has not selected external booking/accounting/messaging services; these provider-specific connections remain pending that choice. Hosting was previously deferred to a future Hostinger VPS. Do not purchase infrastructure or claim a production deployment.

## 1. Confirmed actions

Implemented in migration 0021 and the shared chat review drawer: task create/update, maintenance reporting and housekeeping creation. The operator flag, DB capability and dedicated role grant are additive. Normal mutations, audit/events, notifications and linked state remain authoritative. Validated: 682 API tests, production build, all 42 browser checks and migration roundtrip. See AI_IMPLEMENTATION_AUDIT.md for recorded results.

## 2. Scheduled briefs, reports and insights

Implemented in migration 0022: private opt-in daily/weekly schedules, local lodge times, bounded deterministic facts, configured-provider generation, current actor permissions at execution and delivery, durable leases/retries, deduplicated owner notifications and accessible report views/downloads. Server-only report principals do not store browser sessions or grant tenant-global access. Group reports recheck each property. Deterministic findings describe counts and coverage, not causes. Validated: 706 API tests, production build, 43 browser checks and migration roundtrip. Actual model quality and the live worker/email pipeline remain operational acceptance work.

## 3. Product completion review and implementation

The three originals are reconciled in the 63-item source map. Guest occasions, repeat/safari preferences and a tenant-scoped communication log are implemented in `0023_guest_profiles`; see [the guest CRM checkpoint](GUEST_CRM_DELIVERY.md). Validated: 725 API tests, production build, all 44 browser checks and guest migration roundtrip. Guest CRM remains partial pending the unified operational timeline and connected-role acceptance. Next are task responsibility/timing/vehicle-maintenance relationships. Reconcile current source against the original requirements, rather than treating old milestone inventories as current completion evidence. Track guest/stay profiles and histories, connected task relationships/timing, restricted guest web access, expanded report/export views, offline workflow scope and operational acceptance. Payroll, native applications and payment processing remain outside the agreed initial web release. South Africa is the target market; preserve ZAR defaults and lodge formatting choices.

## 4. Operational and real-provider acceptance

Prepare repeatable real-provider evaluation and operational test commands, production configuration, backup/restore/upgrade rehearsals, monitoring and incident guidance. Verify the full storage/worker/email pipeline with configured services. The user's LM Studio is on their laptop and cannot be tested from this cloud workspace without an accessible endpoint; the recorded local connection/tool probe is not full model acceptance. Actual email delivery needs a configured sender. Actual Hostinger/HTTPS/DNS deployment needs the selected environment and operator credentials through an appropriate secret channel.

## 5. Additional AI lifecycle work

Streaming must expose actual provider output, never a typing simulation or unverified partial operational results. Add explicit retention/deletion and configurable commercial usage/storage allowances with bounded cleanup and preserved append-only operational audit. Provider-specific integrations require the selected service's supported API, credentials and sandbox/contract tests. Keep unimplemented capabilities unavailable rather than selling feature flags as working integrations.
