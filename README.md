# ai-homework-helper-assistant

Homework helper assistant (LangGraph + MCP) with a FastAPI API + HTMX UI.

## Quickstart

This repository ships a runnable FastAPI host, a LangGraph-based orchestrator,
and a simple chat UI.

```powershell
git clone <repo-url>
cd ai-homework-helper-assistant
```

Next steps:
- Review the architecture notes in `docs/architecture.md`.
- Track implementation tasks in `docs/tasks/`.
- Update configuration under `src/config/`.
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

The devcontainer uses Docker Compose and automatically starts companion
`mcp-wiki` (Wikipedia MCP over SSE on port `8765`) and `mcp-stackoverflow`
containers. The main container includes Python 3.12 and Node.js (for MCP tools
like `npx`).

## Configuration

LLM configuration lives in `src/config/llm.dev.json` and `src/config/llm.prod.json`.
Values support environment expansion (for example, set `api_key` to
`$OPENAI_API_KEY`).

MCP server configuration lives in `src/config/mcp_servers.dev.json` and
`src/config/mcp_servers.prod.json`.

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

## API + UI

The FastAPI host lives in `src/apps/assistant_api/main.py` with:
- `GET /health`
- `POST /api/v1/chat`
- `GET /` and `GET /ui` for the chat UI
- `POST /ui/chat` for HTMX form submissions

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

- The UI is intentionally minimal and intended for local testing only.
- MCP tools must be running or configured for retrieval to return evidence.
- Security policies and threat modeling are still draft documents.
- The LLM client uses the OpenAI chat completions API via `base_url`.

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
