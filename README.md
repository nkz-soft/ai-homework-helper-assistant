# ai-homework-helper-assistant

Monorepo scaffold for a homework helper assistant (LangChain + LangGraph + MCP).

## Layout

```text
.
├─ src/
│  ├─ apps/assistant_api/          # FastAPI host (API layer)
│  ├─ packages/                   # Shared packages
│  │  ├─ orchestrator/
│  │  ├─ mcp_clients/
│  │  └─ content_pipeline/
│  │     ├─ ingest/
│  │     └─ mcp_textbooks_server/
│  ├─ config/                     # MCP config + policies
│  ├─ tests/                      # Unit + integration tests
│  └─ infra/                      # Docker/Compose/K8s scaffolding
├─ docs/                          # Architecture + design docs
├─ scripts/
└─ .github/workflows/
```

## Notes

- Python packages live under `src/` and include placeholder `__init__.py` files.
- Architecture reference lives in `docs/tasks/architecture.md` (source) and `docs/architecture.md` (placeholder).
