# Architecture — Homework Helper (LangGraph + MCP)

This document describes the architecture of a “homework helper” assistant: a student asks a question about a subject, the agent retrieves relevant explanations/examples from Wikipedia, StackOverflow, and optional electronic textbooks, then produces a guided, citation-backed answer.

---

## 1. Goals

* Provide **step-by-step explanations** and examples that help a student learn, not just copy answers.
* Retrieve information from **trusted external sources** via **MCP** (Wikipedia, StackOverflow) and optionally internal **textbooks**.
* Produce **evidence-backed answers** with **clear attribution/citations**.
* Be resilient to partial failures (e.g., StackOverflow quota/timeout) and still return useful output.
* Mitigate **prompt injection** and enforce **academic integrity** policies.

## 2. Non-goals

* Not a plagiarism engine: the default mode avoids generating “submit-ready” solutions for graded work.
* Not a general web crawler: retrieval is limited to configured MCP servers (and optional internal content).
* Not a long-term memory tutor: personalization is explicit via request context, not hidden profiling.

---

## 3. High-level architecture

### Components

1. **API Host (`apps/assistant_api`)**

   * FastAPI service that exposes `/api/v1/chat` and `/health`
   * Loads config, policies, logging/OTel, rate limiting
   * Runs the LangGraph workflow and returns response + citations + diagnostics

2. **Orchestrator (`packages/orchestrator`)**

   * LangGraph workflow (nodes + state model)
   * Applies policies (coach vs solution-allowed)
   * Coordinates retrieval, normalization, synthesis, self-check

3. **MCP Clients (`packages/mcp_clients`)**

   * Loads MCP server configuration (`config/mcp_servers.*.json`)
   * Creates multi-server MCP client (LangChain adapter)
   * Provides tool wrappers and interceptors (audit, caching, budget)

4. **Content Pipeline (`packages/content_pipeline`)** *(optional)*

   * Ingestion pipeline: PDF/HTML → chunk → embed → vector index
   * Textbooks MCP server exposing tools for search/read/cite

---

## 4. Repository layout

```text
homework-helper-mcp/
  apps/
    assistant_api/
  packages/
    orchestrator/
    mcp_clients/
    content_pipeline/
      ingest/
      mcp_textbooks_server/
  config/
    mcp_servers.dev.json
    mcp_servers.prod.json
    policies.yaml
    subjects.yaml
  docs/
    architecture.md
    threat-model.md
    api.md
    evaluation.md
    attribution.md
    adr/
  tests/
    unit/
    integration/
  infra/
    docker/
    compose/
    k8s/
  scripts/
```

---

## 5. MCP integrations

### 5.1 Config-driven MCP servers

All MCP servers are declared in JSON config (dev/prod variants). Example names:

* `wikipedia` — stdio transport (local MCP server)
* `stackoverflow` — remote MCP server via `npx mcp-remote https://github.com/NoTalkTech/stackoverflow-mcp`
* `textbooks` — local MCP server (optional)

**Key rule:** only servers listed in config may be used (allowlist).

### 5.2 Tool wrappers (stable internal interface)

Because different MCP servers may expose different tool names/structures, we wrap them into a stable internal API:

* `wikipedia_search(query, lang)`
* `wikipedia_summary(page_id_or_title, lang)`
* `so_search(query, tags)`
* `so_get_content(question_id)`
* `textbooks_search(query, filters)`
* `textbooks_read_chunk(chunk_id)`
* `textbooks_cite(chunk_id)`

Wrappers also enforce:

* timeouts / retries (bounded)
* safe truncation of overly large outputs
* consistent error types (e.g., `ToolTimeout`, `ToolBudgetExceeded`)

### 5.3 Interceptors (cross-cutting concerns)

Interceptors are applied to all tool calls:

* **Audit**: log tool name, server, hashed args, latency, response size (redacting secrets)
* **Caching**: TTL cache for search and lookup calls
* **Budget/Throttling**:

  * per-request max tool calls
  * per-server max calls (StackOverflow is limited)
  * max response bytes per tool call

---

## 6. Orchestration with LangGraph

### 6.1 State model

Minimal state fields:

* `question: str`
* `student_context: { subject_hint?, language?, level?, constraints? }`
* `subject: str`
* `intent: str` (explain/debug/solve/define)
* `needs_clarification: bool`
* `tool_budget: { total_calls, per_server_caps, max_bytes }`
* `retrieved_items: list` (raw tool results)
* `evidence: list` (normalized findings)
* `answer_mode: str` (`coach` | `solution_allowed`)
* `draft_answer: str`
* `final_answer: str`
* `citations: list`
* `safety_flags: list`
* `diagnostics: dict`

### 6.2 Nodes

1. **classify**

   * Detect subject + intent
   * Decide if clarification is needed

2. **plan**

   * Build retrieval plan using `config/subjects.yaml` and `config/policies.yaml`
   * Choose sources and search queries

3. **retrieve (parallel)**

   * Execute MCP tool calls asynchronously
   * Respect budget/timeouts
   * Return partial results on failures

4. **normalize**

   * Convert raw retrieval results into `evidence[]` items:

     * `claim`
     * `supporting_excerpt` (short; avoid long copying)
     * `source` (`wikipedia`/`stackoverflow`/`textbooks`)
     * `ref` (url/id/title)
     * `license_note`
     * `confidence`

5. **safety**

   * Detect prompt injection patterns inside retrieved content
   * Enforce academic integrity: default to `coach`
   * Remove/ignore malicious or irrelevant instructions from sources

6. **synthesize**

   * Generate structured response:

     * Explanation
     * Steps
     * Example
     * Self-check questions
     * Sources / citations

7. **self_check**

   * Verify that key claims are supported by `evidence`
   * Remove unsupported claims or downgrade language

8. **finalize**

   * Produce `final_answer` + `citations` + minimal `diagnostics`

### 6.3 Workflow diagram

```mermaid
flowchart LR
  Q[User Question] --> A[classify]
  A --> B[plan]
  B --> C[retrieve (parallel MCP)]
  C --> D[normalize evidence]
  D --> E[safety]
  E --> F[synthesize]
  F --> G[self_check]
  G --> H[finalize]
  H --> R[API Response]
```

---

## 7. Retrieval strategy

### 7.1 Source selection heuristics (examples)

* **Programming / debugging**:

  * StackOverflow first (search + 1–2 top contents)
  * Wikipedia for definitions/concepts
  * Textbooks if available for course-style explanations

* **Definitions / theory**:

  * Wikipedia first
  * Textbooks for deeper explanation

* **When StackOverflow quota is exhausted**:

  * Skip `get_content`, keep only search summaries (if available)
  * Fall back to Wikipedia/textbooks
  * Surface a diagnostic: `{"source":"stackoverflow","reason":"quota_exhausted"}`

### 7.2 Evidence and citation discipline

* Never paste large verbatim excerpts.
* Store only short supporting snippets (for grounding).
* Always include attribution links/ids in citations metadata.
* See `docs/attribution.md` for licensing rules.

---

## 8. Policies: academic integrity + answer modes

Policies live in `config/policies.yaml`.

* `coach` (default):

  * guided explanation
  * hints and partial steps
  * asks student to attempt next step
  * avoids giving full “submit-ready” solutions for graded tasks

* `solution_allowed`:

  * full worked solution allowed
  * still includes explanation and “how to verify”
  * still requires citations

Triggers for strict `coach`:

* “do it for me”
* “only final answer”
* exam/graded contexts (if detected)

---

## 9. Security model

### 9.1 Threats

* Prompt injection from retrieved pages
* Malicious MCP servers / supply-chain risk
* Data leakage via logs or tool call arguments
* Denial of service via expensive retrieval or huge payloads

### 9.2 Mitigations

* MCP allowlist (config only) + version pinning
* Tool-call budget + response size limits + timeouts
* Sanitization: strip/ignore “system-like” directives from sources
* Structured logs with redaction
* No secrets in prompts; strict env-based secret handling
* Rate limiting at API level

More details: `docs/threat-model.md`

---

## 10. Observability

* OpenTelemetry tracing:

  * request span
  * graph run span
  * per-tool-call spans (server/tool/latency/status)
* Metrics:

  * tool calls count & latency
  * cache hit rate
  * partial failure rate
  * average evidence items per request

---

## 11. Testing strategy

### 11.1 Unit tests

* State model validation
* Planning heuristics
* Normalization correctness (evidence schema)
* Safety filters (prompt injection patterns)

### 11.2 Integration tests

* MCP contract tests:

  * tools exist and are callable
  * graceful skipping if MCP server not available
* Graph happy-path tests:

  * answer structure present
  * at least 1 citation when sources available
  * no policy violations

---

## 12. Deployment & packaging

* Docker images:

  * API service image
  * Textbooks MCP server image (optional)
* Dev:

  * docker-compose with API + textbooks MCP
* Prod:

  * Helm charts for k8s
  * configmaps/secrets for MCP config and policies
  * health probes, resource limits

---

## 13. Configuration

* `config/mcp_servers.*.json` — MCP servers definitions
* `config/policies.yaml` — academic integrity and response modes
* `config/subjects.yaml` — source priorities and query heuristics
* Environment variables (API):

  * `APP_ENV`, `LOG_LEVEL`, `OTEL_EXPORTER_*`, rate-limit settings, etc.

---

## 14. Response contract (API-level)

The API returns:

* `answer` (final text)
* `citations` (list of sources with refs/urls)
* `diagnostics` (optional; tool failures, quota fallback, safety flags)

See `docs/api.md` for OpenAPI details.
