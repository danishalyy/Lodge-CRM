# Ask Lodge AI setup and acceptance

AI is optional. `docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build` continues to start the core CRM without a GPU or inference server. Existing schema migrations and least-privilege grants run through the existing Compose services. Do not expose database credentials or the inference endpoint to the browser.

## Real inference from a MacBook

Run the CRM on the MacBook. Configure a separately administered vLLM OpenAI-compatible service on a private temporary Linux GPU host. Use a private network/tunnel or authenticated TLS proxy, not an unauthenticated public vLLM listener. No infrastructure is deployed automatically by this repository.

In `infra/.env`, set:

```dotenv
AI_ENABLED=true
AI_PROVIDER=vllm
VLLM_BASE_URL=https://your-private-inference-endpoint/v1
VLLM_API_KEY=your-private-service-key
VLLM_MODEL=the-model-id-served-by-vllm
AI_REQUEST_TIMEOUT=30
AI_MAX_CONTEXT=16384
AI_MAX_OUTPUT_TOKENS=1024
AI_MAX_ROUNDS=4
AI_USER_REQUESTS_PER_MINUTE=6
AI_LODGE_REQUESTS_PER_MINUTE=30
AI_LODGE_CONCURRENCY=2
```

Production AI configuration requires HTTPS and a service key. Development may use a deliberately configured private HTTP endpoint. URLs/models/credentials are configured by the operator only, not accepted from chat/tool arguments. Changing from a temporary GPU to a permanent GPU requires configuration, not a CRM rewrite. Match context/output limits to the actual selected model and GPU; byte budgeting in the gateway is conservative and is not a substitute for model-tokenizer capacity benchmarking.

Choose a vLLM version/model combination that supports OpenAI-compatible structured tool calls and configure its appropriate tool-call parser/chat template and automatic tool choice. A model that cannot reliably call tools is not accepted as an operational assistant. No fine-tuning or per-lodge model training is needed. Provider health checks the configured model in `/v1/models`; successful health alone is not an acceptance test.

Super Admin configures the existing database plan/exception access; Lodge Admin controls `ai.use` through existing grants/custom roles. No second AI subscription system is introduced. Core functions remain available if AI is disabled, misconfigured, offline, overloaded or Redis admission fails. The AI screen must show unavailability rather than fabricated answers.

## Automated provider without a GPU

The deterministic provider is strictly for tests. `AI_PROVIDER=test` is refused unless `APP_ENV=test`, and its API health state is `test_only`, which the frontend never presents as a real assistant. Integration tests supply explicit scripted provider replies through FastAPI dependency overrides. There is no keyword-based fake production chatbot. Run the API suite using the temporary PostgreSQL/Redis test setup described in `apps/api/tests/integration/README.md`; tests must not point at customer databases.

Existing CI services suffice; no GPU is needed for provider transport, permissions, owner/tenant RLS and tool safety tests. `httpx.MockTransport` validates the vLLM wire contract and failures without claiming to test a GPU. The real provider uses pinned existing httpx; no new runtime dependency is needed for Phase 1.

## Privacy and scope

Conversations are private to their creator and selected lodge. Group Admin keeps explicit multi-lodge memberships and may open each assigned lodge normally; single-lodge conversations do not aggregate other properties. Explicit Group Owner comparison mode is documented below. Super Admin AI tenant surveillance is denied; an explicit audited support AI workflow is not implemented. Conversations whose grant/scope/entitlement fingerprint changes cannot be replayed or resumed. Start a new conversation under the current access instead.

Store only user-visible messages, server-created provenance, tool execution names/status and usage (provider/model/tokens/latency/result). Separate hidden reasoning fields are ignored; think blocks are removed/rejected. Secrets and email addresses are redacted from prompt text; do not enter credentials or unnecessary personal data into chat. Retention defaults to explicit operator-controlled database retention; no automatic purge is implemented yet. Set a commercial privacy/retention policy before deployment and implement verified retention jobs before treating this as production accepted.

Network/Redis failures fail closed for AI. Inference POSTs are not retried automatically, to avoid duplicate billed GPU work. Chat request IDs deduplicate completed/in-flight turns; retrying a failed question is a new explicit user request. Per-user/per-lodge Redis limits and expiring concurrency leases bound admission. Provider response size, output/context and tool round counts are bounded. No SQL, URL or shell execution tool is allowed.

## Later-phase acceptance gates

RAG requires actual private upload/verification, Celery extraction, versioned embeddings and pgvector retrieval with tenant/visibility filters before inference. The Phase 4 PostgreSQL image adds pgvector; its migration and backup/restore requirements are documented below. Malicious documents must remain data and must never alter tools or permissions.

Group aggregation must resolve owner/group and explicit lodge memberships and recheck each lodge's subscription/AI entitlement using separate tenant contexts. Writes require actor/lodge/conversation-bound, expiring single-use server confirmation, then the existing CRM mutation logic/audit/events/notifications. Scheduled reports/insights require actor-scoped jobs and deterministic metrics/detection, not privileged global worker data sent wholesale to the model.

Real vLLM acceptance remains manual until a GPU endpoint is supplied: test operational queries, malformed/unauthorised tool calls, outage isolation, simultaneous conversations, first-token/end-to-end latency, tool accuracy, VRAM/utilisation, queue depth and saturation. RAG, writes and cross-property examples are only meaningful after their corresponding phases exist. A successful deterministic test is not real inference acceptance. No production-ready claim is warranted without these results.

## Implemented read-only operational tools

The base `ai` capability now supports fifteen live operational read tools: dashboard, tasks, rooms, current stays, arrivals, departures, requests, housekeeping, maintenance, vehicles, fuel logs, activities, transfers, private notifications and report metrics. The registry is code-defined; permissions, plan grants and lodge exceptions remain database-defined. Suggestions come from authorised registered tools, not frontend role/package lists.

Adapters invoke the existing permission dependency explicitly and reuse operational handlers and their scopes. Five previously unbounded list handlers accept an optional finite limit for adapters while preserving the existing default behaviour of normal screens. Tool responses include the selected lodge, lodge time zone/current day, allowlisted fields and explicit partial-page flags. Date/search filters apply to bounded retrieved pages; when partial, answers must not claim a complete inventory or a zero result across the whole lodge. Use deterministic dashboard/report metrics for supported full-scope counts. Dashboard counts that represent stays are labelled as stays, not fabricated guest totals. Assigned-work base scopes cannot use lodge-wide dashboard/report aggregates.

Guest names are limited to permitted stay/arrival records; contact, dietary/medical, staff HR/performance, financial values, precise wildlife positions, free-form notes and raw event details are not included in these initial DTOs. No registered tool reads arbitrary URLs, SQL, files, HR records, protected coordinates or writes. Source metadata comes from completed server tool execution, never model-authored citations. Each final operational answer requires at least one successful current tool result; a model answer with no tool evidence is refused. This is an evidence-presence check, not proof that a real model's prose is factually accurate: real-model grounding/tool-call quality still needs evaluation.

Invalid optional AI environment values disable AI with a misconfigured state instead of preventing core Settings/application startup. Health probes are cached and release the DB connection before network I/O. Chat likewise releases DB transactions while waiting on the GPU. Redis failure disables admission for AI alone. Existing private GPU configuration must still be supplied before actual inference is usable.

Not implemented: AI actions/confirmations, generated/scheduled AI reports and insights, retention jobs, streaming, and real-GPU/load acceptance. Their capabilities remain future; existing non-AI memory, reports, notifications, Group Admin and CRM actions continue to function normally.

### GPU-free regression command

From `apps/api`, configure a reachable **test-only** `TEST_DATABASE_ADMIN_URL` and `REDIS_URL` as documented in `tests/integration/README.md`, then run:

```sh
python -m pytest -q -p no:cacheprovider --tb=short
```

AI integration tests select the test environment/provider themselves, use real PostgreSQL under a least-privilege role and provide scripted model tool calls. They create/drop only temporary test databases/roles. You do not need to set `AI_ENABLED=true` or run a GPU for this suite. CI already runs the full suite; integration skips without the test database URL are not an acceptance pass. After the web production build, `BROWSER_EXECUTABLE_PATH=/path/to/chromium npm test --prefix e2e` runs browser fixtures. These are not real-GPU or real operational-data inference tests.

## Operational Memory (Phase 3)

`get_operational_history` is the sixteenth read-only tool. It requires `ai.use`, the base `ai` entitlement and `memory.view`; each event family also requires the current module's view permission and entitlement. It queries existing immutable `OperationalEvent` rows under normal tenant RLS after deriving visible resource IDs through the authoritative CRM list handlers. No schema change, customer-data rewrite, or new operational event store is needed.

Supported exact event/resource pairs cover tasks, maintenance, rooms, vehicles, guest requests, activities, transfers and identifiable housekeeping status events. Unknown event types, raw summaries/details, actor identities, HR, guest personal/medical information, financial values, precise coordinates and ambiguous unit-level housekeeping creation events are excluded. Fuel events and other unsupported families are excluded from historical retrieval; the existing live fuel tool is unchanged. Current record labels help identify records, but are explicitly not historical name snapshots. Only a strict terminal status enum is extracted from a recognised status-change event; the current record's status is never used as historical state.

The default period is the last 30 lodge-local calendar days including today. Explicit start/end dates are inclusive, span at most 366 days, and convert to timestamp bounds using the lodge's IANA time zone. Results are newest first, up to 50 events. Optional resource type, UUID and text search narrow the already authorised current records. At most 250 current records per module are considered; reaching this bound, the event limit, or the chat context budget marks the result partial. Deleted, inaccessible, older out-of-page and unsupported records/events are excluded. A zero result is not proof that nothing happened. Logs do not establish root causes or complete recurrence counts.

Historical source metadata is server-generated: selected lodge, event IDs, resource references, recorded timestamps, requested period, retrieval time and partial coverage. Raw event text is never persisted as AI tool context. The chat sources disclosure displays event references, the period and limited-coverage warnings, using normal date formatting. Each referenced record is rechecked after inference and before saved-message/retry replay; reassignment, deletion or lost module access refuses the old answer, including when the account's role fingerprint has not changed. Ordinary permission/subscription/session revalidation remains in effect. No historical answer is a database mutation.

Real-model history accuracy, causation restraint and adversarial evaluation remain acceptance work for a configured vLLM/GPU; scripted provider tests verify the gateway boundaries, not model factuality. Private RAG was the next phase; its implemented scope is documented below.

## Private document knowledge (Phase 4)

The optional document pipeline is implemented, with **real external embeddings** in normal operation. There is no hash/keyword/dummy embedding fallback. The two existing DB capabilities `ai_knowledge` and `document_knowledge` are implemented separately from the base AI entitlement. Both grants, `ai.use`, `knowledge.view` and an explicit `AI_KNOWLEDGE_ENABLED=true` are required. Upload/sharing/removal/processing additionally require `knowledge.manage` and an active writable subscription. Existing Lodge/Group Admin presets receive knowledge grants; custom roles can delegate them through the existing permission system. Super Admin does not inherit tenant knowledge access.

Configuration for **both API and worker**:

```dotenv
AI_KNOWLEDGE_ENABLED=true
AI_EMBEDDING_BASE_URL=https://your-private-embedding-server/v1
AI_EMBEDDING_API_KEY=your-private-service-key
AI_EMBEDDING_MODEL=your-embedding-model
AI_EMBEDDING_VERSION=your-pinned-model-revision-and-normalisation-version
```

Use a real OpenAI-compatible `/embeddings` endpoint, such as a separate vLLM pooling/embedding deployment. It must produce **384 finite nonzero dimensions** per input and support the configured model. The chat model and embedding model may need separate servers/processes; configuring a chat-only vLLM server does not make embeddings available. Production requires HTTPS and a server-side API key. URL, credentials, model/version and selected lodge never come from tool arguments. Changing the embedding revision/version excludes old chunks immediately and marks documents for reprocessing; managers can safely reprocess them. Explicitly disabled/unconfigured document processing does not disable core CRM or the existing live/history AI tools.

The Ask Lodge AI screen contains a permission-aware knowledge library. Upload PDF, DOCX or UTF-8 TXT (up to 10 MiB). Metadata starts unprocessed and is excluded from retrieval/download. Private originals use server-generated keys in the existing private S3/MinIO bucket; checksum verification runs before extraction. Files are never publicly listed. Visibility defaults to **Only me**; explicit department/lodge sharing requires the corresponding scope, and department sharing also requires the Departments capability. Even Lodge Admin cannot read someone else's private document. Only the creator, appropriate department manager, or lodge/group administrator for lodge-shared documents can manage a visible file.

An explicit Process action queues an actor/document/lodge/token-bound Celery job. The worker rechecks current account, active employment/membership/group ownership, permissions, subscription and entitlements before processing, before each embedding batch and before publishing. It never uses a privileged/super-admin tenant context. Jobs use locking/tokens to avoid duplicate publication; status/leases allow explicit retries after queue outages or interrupted jobs. Changing visibility or removing a document affects retrieval immediately. Removal deletes chunks transactionally, invalidates pending jobs, and attempts to delete its private original. If object deletion/storage or metadata publication fails, private orphan cleanup is an operator task; no automatic blob garbage collector is implemented.

Extraction runs in an isolated Linux subprocess with a 512 MiB address-space limit, 10-second CPU limit and 20-second parent deadline. It bounds PDF pages/content, DOCX archive entries/decompressed size, text length (120,000 characters), chunks (100), and embedding batches (8). Encrypted/unreadable files and textless/scanned PDFs are rejected; OCR is not implemented. DOCX macros/embedded active objects and XML entity expansion are rejected. Extractors do not execute document instructions, links, scripts or macros. Secret/email redaction is limited and is not comprehensive personal-data classification or antivirus scanning. Upload only approved material appropriate for its sharing audience. Downloaded originals are untrusted attachments, with a short (60-second) private signed URL; issued URLs remain usable until expiry. Original-file antivirus/content-disarm services are not implemented.

The seventeenth tool, `search_lodge_knowledge`, accepts a bounded query and at most eight passages. PostgreSQL first materializes ready, currently authorised tenant/visibility/model/version candidates, then computes exact cosine distance with pgvector. FORCE RLS covers documents and chunks, including department/private sharing; there is no global search followed by model-side filtering or a global ANN index. Exact filtered scans are intentional for this bounded initial library; larger library/index scaling needs measured acceptance. A conservative 100-visible-record upload/list limit applies, including deleted metadata for storage-abuse checks; configurable commercial storage quotas/retention remain future work.

Passages are untrusted tool data. They cannot change registered tools, grants, identity or lodge scope. Sources are created by the server with document title, immutable checksum, chunk UUID and page/document locator, and are displayed in chat. Reopening/retrying/returning a saved document answer rechecks each referenced document/chunk, current visibility and embedding version. Removing/unsharing a source refuses the old answer; old privileged context is not silently replayed. No free-form extracted text or full embedding response is stored in AI message/tool logs. Relevant excerpts are sent only to the configured private embedding/chat providers under their respective authorisation checks. Vector proximity is not proof of relevance or answer truth: real-model grounding, prompt-injection resistance and thresholds need real-provider evaluation before commercial acceptance.

### PostgreSQL image and upgrade

Migration **0019_private_knowledge** requires pgvector. `infra/postgres/Dockerfile` retains PostgreSQL 16, the Alpine base and existing data directory, adding checksum-pinned pgvector 0.8.2. CI uses the corresponding PostgreSQL 16 pgvector image. Build the new image **before** running migrations; the old stock image cannot execute `CREATE EXTENSION vector`. Do not delete or replace the existing database volume.

Before updating a real installation, take a database backup and verify that it can be restored on the new image. For a default local Compose installation, run from the repository root:

```sh
docker compose --env-file infra/.env -f infra/docker-compose.yml exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > safarios-before-knowledge.dump
docker compose --env-file infra/.env -f infra/docker-compose.yml build postgres api worker
docker compose --env-file infra/.env -f infra/docker-compose.yml up -d --build
```

Do not run `down -v`. A database administrator runs Alembic and existing `db-grants` as before; the API/worker retain NOSUPERUSER/NOBYPASSRLS roles. Downgrade removes knowledge tables/data, keeps operational tables, and deliberately leaves the shared extension installed. To restore document service, restore both DB and private-object backups; embeddings alone do not back up originals. A configuration change does not move or rewrite customer volumes automatically.

### Phase 4 verification boundary

Automated tests use real PostgreSQL/pgvector and least-privilege RLS, actual isolated extraction, explicit in-memory storage and scripted embedding/model test doubles. A bounded HTTP transport test verifies real embedding request/response validation without claiming a GPU connection. Build, migration upgrade/downgrade/re-upgrade, custom-format vector backup/restore and preservation of an existing operational record were exercised on disposable databases in the separately built PostgreSQL image. Existing customer databases/volumes were not touched. A configured live embedding service, full running MinIO/Celery pipeline, real-model retrieval quality/injection evaluation and load acceptance remain deployment acceptance work in Phase 8.

The browser fixture checks private multipart uploads, processing, sharing, destructive confirmation, precise toast feedback, document citations and both themes at 375/768/1366/1440 px. Fixture text/screenshots are not evidence of real inference. The next phase at that checkpoint was Group Owner AI, implemented below.

## Group Owner AI (Phase 5)

Group Owners can choose **Compare lodges with AI** from the existing group overview. It opens `/lodge-ai?scope=group`, with a clear group name, included lodge names, coverage and separate private conversation history. The current lodge is the **anchor** for private storage, usage and the existing Redis limits; it does not grant access to other lodges. Individual lodge AI stays separate and cannot invoke group tools.

Migration **0020_group_ai_scope** adds `scope_type`/`group_id` to the existing private conversation table. Existing rows default to lodge scope; owner/lodge FORCE RLS and composite message/usage references remain unchanged. Only Group Admin receives the new `ai.group.view` preset grant. The existing editable `advanced_ai` capability now means read-only Group Owner comparisons/reports; it does not enable automated summaries, actions or other future capabilities. No plan names are hardcoded. Super Admin controls the normal DB plan/exception grants per lodge, as before.

Every participating lodge must have an explicit active Group Admin membership in the selected active group, owned by the authenticated actor, and current `ai.use`/`ai.group.view`, `ai`/`advanced_ai` access with an active writable subscription. An expired/suspended/pending/missing subscription, revoked membership/grant or disabled feature never contributes operational facts. Unassigned properties and properties in another group are not searched, including another group owned by the same person. Super Admin does not inherit tenant AI access. The model cannot supply group, lodge or user IDs. Group scope is an explicit browser conversation choice, resolved from the anchor and database ownership/memberships, never from model text.

Two additional tools bring the registry to **nineteen**: `get_group_overview` and `get_group_report_metrics`. Group conversations expose only these aggregate tools; granular lodge tools, private knowledge/memory and writes are unavailable in group mode. Each property enters its own non-super-admin RLS context, checks permissions/entitlements, reuses authoritative dashboard/report readers and restores the anchor before private history/usage writes. Report sections also require their own module view grants and features; period-based housekeeping reports require both Reports and Housekeeping access. A deterministic service adds housekeeping status counts. No guest/staff names, contact/medical/HR details, raw notes, financial values or protected coordinates enter group tool DTOs.

Overview figures use each lodge's local calendar day. Report date filters default to the last 30 UTC calendar days and accept at most 366 inclusive days, matching the existing report reader's timestamp boundaries. Reports describe records **created in the period** and their current completion status, not all work completed during that period. Server-computed additive totals, maxima, ties and per-metric contributor IDs prevent the model from having to calculate them. A missing metric means unavailable, never zero. Percentages/averages are not added or averaged across lodges; no workload-normalised performance/priority score is invented. Vehicle unavailability counts are current state, not downtime durations. Overlapping stays count stays, not unique people. Queries are sequential per property, not a globally atomic operational snapshot; sources retain per-property retrieval timestamps, dates/periods and time zones.

The initial group bound is **20 explicitly assigned lodges**; larger groups receive an explicit limit error instead of a silent incomplete comparison. AI-ineligible properties are omitted with an excluded count. Per-metric sources identify actual contributing properties, and the source disclosure offers readable metric coverage. If the model context budget removes property rows, totals/maxima/contributors are recomputed for the retained rows and the answer is marked partial. Do not present those comparisons as covering the entire group. No cross-group search, global RLS bypass, cross-property document search or scheduled group report is added.

A group conversation's access fingerprint includes its selected group, explicit membership set, each property's scope/grants/plans/overrides/subscription and eligibility. Reopening/retrying a saved answer, every inference boundary and the final response re-resolve that snapshot. Changed access refuses the old conversation instead of replaying privileged data. A new conversation uses the current authorised scope. Permission denial clears old answers and group coverage from the UI. Group Admin's new preset grant may also invalidate existing single-lodge AI fingerprints; this is the existing conservative history policy, not a deletion of normal lodge history.

Normal AI user/anchor Redis admission, CSRF, account assertions, provider failure isolation, redaction, usage, tool logs and audit remain in force. Group usage can be attributed by joining the usage row's conversation and `group_id`; there is no duplicate group model/provider or subscription engine. A real vLLM service is still required for actual explanations. The existing non-AI group overview continues to work if inference is disabled/offline.

Upgrade by backing up the database, then rebuilding the API/web images and running the existing migration/grants flow. Downgrade requires a privileged migration administrator able to bypass FORCE RLS for cleanup, deletes group conversations and their dependent rows, and preserves individual-lodge conversations and operational records. It refuses an unprivileged downgrade rather than silently reinterpreting group history as lodge history. Upgrade/downgrade/re-upgrade were tested in a disposable database with legacy lodge history and an existing room record.

Remaining acceptance includes real-model grounding/causal restraint, large-group/context/latency/concurrency benchmarks and operational load. Group report snapshots are read-only on-demand comparisons; saved/scheduled management reports, notifications and controlled actions belong to later phases. The next implementation phase is expiring, single-use action confirmations.
