# ai-homework-helper-assistant

Monorepo scaffold for a homework helper assistant (LangGraph + MCP).

## Quickstart

This repository is a scaffold with a runnable FastAPI host and LangGraph-based
orchestrator nodes.

```powershell
git clone <repo-url>
cd ai-homework-helper-assistant
```

Next steps:
- Review the architecture notes in `docs/architecture.md`.
- Track implementation tasks in `docs/tasks/`.
- Adjust configuration under `src/config/`.
- Run the LangGraph pipeline with `packages.orchestrator.graph.build_graph.run`.
- Start the API with `uvicorn apps.assistant_api.main:app --reload`.

## Configuration

LLM settings are read from environment variables via `src/config/llm.dev.json`
and `src/config/llm.prod.json`.

Required environment variables:
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`

## VS Code Dev Container (no local Python)

Use the Dev Containers extension to develop inside Docker without installing
Python on your host machine.

1. Install Docker Desktop (or another Docker runtime).
2. Install the VS Code extension "Dev Containers".
3. Open this repo in VS Code and run "Dev Containers: Reopen in Container".
4. Wait for the container to build, then use the integrated terminal.

The devcontainer uses Docker Compose and automatically starts a companion
`mcp-wiki` service (Wikipedia MCP over SSE on port `8765`). The main container
includes Python 3.12 and Node.js (for MCP tools like `npx`).

## Testing

Install dev dependencies from `pyproject.toml`, then set `PYTHONPATH=src` so
tests can import project packages under the `src/` layout.

```powershell
python -m pip install -e ".[dev]"
$env:PYTHONPATH = "src"
pytest
ruff format .
ruff check .
mypy
```

## LangGraph

The orchestrator workflow is assembled with LangGraph in
`src/packages/orchestrator/graph/build_graph.py`. Use `run(question, context)`
to execute the pipeline.

## API

The FastAPI host lives in `src/apps/assistant_api/main.py` with:
- `GET /health`
- `POST /api/v1/chat`

Environment variables:
- `APP_NAME` (default: Homework Helper API)
- `LOG_LEVEL` (default: INFO)
- `RATE_LIMIT_REQUESTS` (default: 60)
- `RATE_LIMIT_WINDOW_SECONDS` (default: 60)
- `CACHE_TTL_SECONDS` (default: 300)

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
- Orchestrator nodes are implemented, but the end-to-end product UI is not.

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
