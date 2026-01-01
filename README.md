# ai-homework-helper-assistant

Monorepo scaffold for a homework helper assistant (LangChain + LangGraph + MCP).

## Quickstart

This repository is a scaffold. There is no runnable app yet, but you can start
structuring the project and filling in the docs.

```powershell
git clone <repo-url>
cd ai-homework-helper-assistant
```

Next steps:
- Review the architecture notes in `docs/architecture.md`.
- Track implementation tasks in `docs/tasks/`.
- Fill in configuration placeholders under `src/config/`.

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

## Limitations

- No production-ready API or UI exists yet.
- Dependencies, datasets, and external integrations are not wired up.
- Security policies and threat modeling are still draft documents.
- Test suites are empty placeholders.

## Documentation

- `docs/api.md`
- `docs/architecture.md`
- `docs/attribution.md`
- `docs/evaluation.md`
- `docs/threat-model.md`
- `docs/tasks/architecture.md`

## Notes
- Python packages live under `src/` and include placeholder `__init__.py` files.
- Architecture reference lives in `docs/architecture.md`.
