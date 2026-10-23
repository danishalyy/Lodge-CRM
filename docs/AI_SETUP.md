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

Conversations are private to their creator and selected lodge. Group Admin keeps explicit multi-lodge memberships and may open each assigned lodge normally; this does not constitute all-property AI aggregation. Super Admin AI tenant surveillance is denied; an explicit audited support AI workflow is not implemented. Conversations whose grant/scope/entitlement fingerprint changes cannot be replayed or resumed. Start a new conversation under the current access instead.

Store only user-visible messages, server-created provenance, tool execution names/status and usage (provider/model/tokens/latency/result). Separate hidden reasoning fields are ignored; think blocks are removed/rejected. Secrets and email addresses are redacted from prompt text; do not enter credentials or unnecessary personal data into chat. Retention defaults to explicit operator-controlled database retention; no automatic purge is implemented yet. Set a commercial privacy/retention policy before deployment and implement verified retention jobs before treating this as production accepted.

Network/Redis failures fail closed for AI. Inference POSTs are not retried automatically, to avoid duplicate billed GPU work. Chat request IDs deduplicate completed/in-flight turns; retrying a failed question is a new explicit user request. Per-user/per-lodge Redis limits and expiring concurrency leases bound admission. Provider response size, output/context and tool round counts are bounded. No SQL, URL or shell execution tool is allowed.

## Later-phase acceptance gates

RAG requires actual private upload/verification, Celery extraction, versioned embeddings and pgvector retrieval with tenant/visibility filters before inference. The current PostgreSQL image has no pgvector; a compatible image/extension migration and backup/restore test are required before enabling that capability. Malicious documents must remain data and must never alter tools or permissions.

Group aggregation must resolve owner/group and explicit lodge memberships and recheck each lodge's subscription/AI entitlement using separate tenant contexts. Writes require actor/lodge/conversation-bound, expiring single-use server confirmation, then the existing CRM mutation logic/audit/events/notifications. Scheduled reports/insights require actor-scoped jobs and deterministic metrics/detection, not privileged global worker data sent wholesale to the model.

Real vLLM acceptance remains manual until a GPU endpoint is supplied: test operational queries, malformed/unauthorised tool calls, outage isolation, simultaneous conversations, first-token/end-to-end latency, tool accuracy, VRAM/utilisation, queue depth and saturation. RAG, writes and cross-property examples are only meaningful after their corresponding phases exist. A successful deterministic test is not real inference acceptance. No production-ready claim is warranted without these results.

## Implemented read-only operational tools

The base `ai` capability now supports fifteen registered read tools: dashboard, tasks, rooms, current stays, arrivals, departures, requests, housekeeping, maintenance, vehicles, fuel logs, activities, transfers, private notifications and report metrics. The registry is code-defined; permissions, plan grants and lodge exceptions remain database-defined. Suggestions come from authorised registered tools, not frontend role/package lists.

Adapters invoke the existing permission dependency explicitly and reuse operational handlers and their scopes. Five previously unbounded list handlers accept an optional finite limit for adapters while preserving the existing default behaviour of normal screens. Tool responses include the selected lodge, lodge time zone/current day, allowlisted fields and explicit partial-page flags. Date/search filters apply to bounded retrieved pages; when partial, answers must not claim a complete inventory or a zero result across the whole lodge. Use deterministic dashboard/report metrics for supported full-scope counts. Dashboard counts that represent stays are labelled as stays, not fabricated guest totals. Assigned-work base scopes cannot use lodge-wide dashboard/report aggregates.

Guest names are limited to permitted stay/arrival records; contact, dietary/medical, staff HR/performance, financial values, precise wildlife positions, free-form notes and raw event details are not included in these initial DTOs. No registered tool reads arbitrary URLs, SQL, files, HR records, protected coordinates or writes. Source metadata comes from completed server tool execution, never model-authored citations. Each final operational answer requires at least one successful current tool result; a model answer with no tool evidence is refused. This is an evidence-presence check, not proof that a real model's prose is factually accurate: real-model grounding/tool-call quality still needs evaluation.

Invalid optional AI environment values disable AI with a misconfigured state instead of preventing core Settings/application startup. Health probes are cached and release the DB connection before network I/O. Chat likewise releases DB transactions while waiting on the GPU. Redis failure disables admission for AI alone. Existing private GPU configuration must still be supplied before actual inference is usable.

Not implemented: Operational Memory retrieval, RAG ingestion/pgvector/embeddings, multi-property AI comparisons, AI actions/confirmations, generated/scheduled AI reports and insights, retention jobs, streaming, and real-GPU/load acceptance. Their capabilities remain future; existing non-AI memory, reports, notifications, Group Admin and CRM actions continue to function normally.

### GPU-free regression command

From `apps/api`, configure a reachable **test-only** `TEST_DATABASE_ADMIN_URL` and `REDIS_URL` as documented in `tests/integration/README.md`, then run:

```sh
python -m pytest -q -p no:cacheprovider --tb=short
```

AI integration tests select the test environment/provider themselves, use real PostgreSQL under a least-privilege role and provide scripted model tool calls. They create/drop only temporary test databases/roles. You do not need to set `AI_ENABLED=true` or run a GPU for this suite. CI already runs the full suite; integration skips without the test database URL are not an acceptance pass. After the web production build, `BROWSER_EXECUTABLE_PATH=/path/to/chromium npm test --prefix e2e` runs browser fixtures. These are not real-GPU or real operational-data inference tests.
