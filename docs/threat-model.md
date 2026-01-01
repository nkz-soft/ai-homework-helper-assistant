# Threat Model (Draft)

This document focuses on risks from external content and tool integrations.

## Scope

- User requests and responses
- MCP tool calls (Wikipedia, StackOverflow, textbooks)
- Internal prompts and policies
- Logs and diagnostics

## Assets

- User input and generated answers
- API keys / secrets (env-only)
- Retrieval results and citations
- Policy configuration

## Trust boundaries

- User input boundary
- MCP servers (external or local)
- LLM runtime
- Logging / storage

## Key risks

1. Prompt injection from retrieved content
2. Malicious or compromised MCP server output
3. Data leakage via logs or tool arguments
4. Denial of service via expensive tool calls or huge payloads

## Mitigations (required)

### MCP allowlist

- Only MCP servers listed in `src/config/mcp_servers.*.json` may be used.
- No ad-hoc tool URLs or dynamic server discovery.
- Prefer pinned versions for local MCP servers.

### Tool budget

- Per-request max tool calls (global and per-server).
- Response size limits per tool call.
- Timeouts and retries with backoff.
- Abort or degrade to partial answers when budget is exceeded.

### Sanitization

- Strip or ignore system-like instructions from retrieved text.
- Treat retrieved content as untrusted data, never as instructions.
- Keep excerpts short; remove HTML/script content.

## Additional mitigations

- Redact secrets in logs; avoid logging full prompts.
- Cache only safe, normalized evidence.
- Rate limit API endpoints.
- Validate citations and disallow unsupported sources.

## Residual risks

- Sophisticated prompt injection may bypass heuristics.
- MCP server outages may reduce answer quality.
- Incorrect citations if upstream metadata is missing.
