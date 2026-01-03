# ai-homework-helper-assistant

Monorepo scaffold for a homework helper assistant (LangGraph + MCP).

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

## VS Code Dev Container (no local Python)

Use the Dev Containers extension to develop inside Docker without installing
Python on your host machine.

1. Install Docker Desktop (or another Docker runtime).
2. Install the VS Code extension "Dev Containers".
3. Open this repo in VS Code and run "Dev Containers: Reopen in Container".
4. Wait for the container to build, then use the integrated terminal.

The container includes Python 3.12 and Node.js (for MCP tools like `npx`).

## Testing

Set `PYTHONPATH=src` so tests can import project packages under the `src/`
layout.

```powershell
$env:PYTHONPATH = "src"
python -m unittest
```

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
