![](https://i.postimg.cc/mkwnDnZf/Sauron.png)

# Sauron

AI-powered error analysis agent for software systems. Sauron receives application errors — with or without stack traces — and uses LLM-driven analysis to explain what happened, identify root causes, and suggest fixes.

## Features

- **Automated Error Analysis** — Submit error events and get structured analysis: what happened, why, and how to fix it.
- **Source Code Awareness** — Connects to GitHub and GitLab repositories to read relevant source files referenced in stack traces.
- **Async Job Processing** — Analysis requests are queued and processed by a background worker, so the API stays responsive.
- **Error Event Tracking** — Deduplicates errors by fingerprint and tracks occurrence counts over time.
- **Multi-Provider LLM** — Configurable LLM backend (default: Gemini).

## Tech Stack

- **Python 3.13** / **FastAPI** / **Uvicorn**
- **LangChain + LangGraph** — Agent workflow with tool-calling loop
- **PostgreSQL** — Job queue, error events, repository metadata
- **SQLAlchemy + asyncpg** — Async database access
- **uv** — Dependency management

## Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)
- Docker & Docker Compose

### 1. Set up environment variables

```bash
cp .env.example .env
# Fill in GOOGLE_API_KEY, ENV_DB_PASSWORD, SCM_AUTH_ENCRYPTION_KEY
```

### 2. Start dependencies

```bash
docker compose --env-file .env -f dependency/docker-compose.yml up -d
```

### 3. Run the server

```bash
uv run uvicorn main:app --host 127.0.0.1 --port 8002
```

The API is available at `http://localhost:8002`. Check health at `GET /health`.

## Project Structure

```
main.py                          # FastAPI app entrypoint
src/
  apis/                          # Route handlers
  services/                      # Business logic
  repositories/                  # Database access (SQLAlchemy)
  clients/                       # External clients (LLM)
  core/                          # Database init, job worker, auth utilities
  workflows/                     # LangGraph agent definition & tools
    v1/sauron_agent_v1.py        # Agent graph: prepare → LLM → tools loop
    tools/github_tools.py        # SCM tools available to the agent
    templates/                   # System prompts
environments/                    # Per-environment config (local, dev, live)
dependency/                      # Docker Compose & DB init scripts
```

## Configuration

Environment-specific settings live in `environments/<env>/config.yaml`. The active environment is set via the `ENV` variable (default: `local`).

Key config sections: CORS origins, PostgreSQL connection, LLM provider/model, source control encryption key, and logging.

## Docker

```bash
docker build -t sauron .
docker run -p 8002:8002 --env-file .env sauron
```

## License

Private — All rights reserved.
