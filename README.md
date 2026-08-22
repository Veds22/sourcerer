# Sourcerer

A personal AI assistant that tracks job applications, reading lists, links, and todos — accessible from both a desktop AI client (Claude Desktop) and a custom web app, backed by a single shared tool implementation exposed over the Model Context Protocol (MCP).

**Live demo:** [sourcerer-cyan.vercel.app](https://sourcerer-cyan.vercel.app/)


---

## What it does

Sourcerer exposes 22 tools across four domains — job applications, reading items, links, and todos — backed by a single SQLite/Postgres database. The same tool implementation is reachable two ways at once:

- **Claude Desktop**, over stdio, as a local MCP server
- **A custom web chat UI**, over Streamable HTTP, via a LangGraph-orchestrated agent streaming responses over SSE

Ask it things like "add a todo to follow up with the recruiter at Acme by Friday" or "show me all my interview-stage applications" and it calls the right tool, writes to the database, and replies conversationally.

---

## Architecture

```
┌─────────────────────┐
│   Vercel             │
│   React / Vite       │
│   sourcerer-cyan      │
│   .vercel.app         │
└──────────┬───────────┘
           │ HTTPS / REST + SSE
           ▼
┌──────────────────────────────────┐
│  Render — Free Web Service        │
│  ┌────────────────────────────┐  │
│  │  FastAPI                    │  │
│  │  0.0.0.0:$PORT               │  │
│  │  LangGraph agent + LangSmith │  │
│  └──────────────┬──────────────┘  │
│                 │ localhost:8001   │
│  ┌──────────────▼──────────────┐  │
│  │  Remote MCP Server           │  │
│  │  127.0.0.1:8001 (FastMCP)    │  │
│  │  Streamable HTTP transport   │  │
│  └──────────────┬──────────────┘  │
└─────────────────┼─────────────────┘
                   ▼
            ┌─────────────┐
            │  Database    │
            │  (SQLite →   │
            │  Postgres)   │
            └─────────────┘

Claude Desktop ──stdio──► same MCP tool layer (separate process, same codebase)
```

The MCP tool implementations (`src/tools/`) are written once and never duplicated — both the stdio server (for Claude Desktop) and the HTTP server (for the web app) import the same `FastMCP` instance and the same tool functions.

---

## Features

- **22 MCP tools** across `applications`, `reading`, `links`, `todos` — add/edit/get/list/search on each domain, plus status-history tracking for applications
- **Dual interface** — same backend reachable from Claude Desktop (stdio) and a web chat UI (Streamable HTTP), with zero duplicated tool logic
- **LangGraph orchestration** — `StateGraph` with `ToolNode` + `tools_condition` drives the tool-calling loop, supporting multi-round tool calls per turn
- **Streaming responses** — SSE from FastAPI to the React frontend for real-time output
- **LangSmith tracing** — full visibility into agent runs, tool calls, and latency during development
- **Async tool layer** — all tool functions are `async def`, DB calls wrapped in `asyncio.to_thread` to avoid blocking the event loop

---

## Tech stack

| Layer | Tech |
|---|---|
| Frontend | React, Vite |
| Frontend hosting | Vercel |
| Backend | FastAPI, SSE |
| Backend hosting | Render (free tier) |
| Orchestration | LangGraph (`StateGraph`, `ToolNode`, `tools_condition`) |
| Tool protocol | MCP (Model Context Protocol) via `fastmcp` |
| MCP transports | stdio (Claude Desktop), Streamable HTTP (web app) |
| LLM | Groq (`llama-3.3-70b-versatile`) |
| Observability | LangSmith |
| Database | SQLite (migrating to Postgres — Supabase/Render free tier) |
| Package management | `uv` |

---

## Project structure

```
sourcerer/
├── src/
│   ├── db.py                # Schema, connection, message history
│   ├── mcp.py                # Shared FastMCP instance (stdio — Claude Desktop)
│   ├── remote_mcp.py         # Same instance over Streamable HTTP (web app)
│   ├── llm.py                # LangGraph agent, tool-calling loop
│   ├── app.py                # FastAPI app, SSE endpoint
│   └── tools/
│       ├── applications.py   # 6 tools
│       ├── reading.py        # 5 tools
│       ├── links.py          # 5 tools
│       └── todos.py          # 6 tools
├── frontend/                 # React / Vite web UI
├── .env.example
├── pyproject.toml
└── README.md
```

---

## Local development

```bash
# clone
git clone https://github.com/Veds22/sourcerer.git
cd sourcerer

# install deps
uv sync

# configure environment
cp .env.example .env
# fill in GROQ_API_KEY, MCP_SERVER_URL, LANGSMITH_API_KEY, etc.

# initialise the database
uv run python -m src.db

# run the remote MCP server
uv run uvicorn src.remote_mcp:app --port 8001

# run the FastAPI backend (separate terminal)
uv run uvicorn src.app:app --port 8000

# run the frontend (separate terminal)
cd frontend && npm install && npm run dev
```

For Claude Desktop, point its MCP config at `src/mcp.py` via stdio — see `claude_desktop_config.json` in your Claude Desktop settings directory.

---

## Known limitations

- **Ephemeral storage on Render's free tier** — the SQLite file does not persist across deploys/restarts. Migration to a managed Postgres free tier (Supabase or Render Postgres) is in progress to fix this.
- **Streaming output formatting** — SSE output isn't fully markdown-formatted on the frontend yet.
- **Single chat session** — no support for multiple concurrent/saved chat sessions yet.
- **Tool error surfacing** — some malformed tool-result messages can surface raw API errors to the user instead of a friendly fallback (being addressed).

---

## Roadmap

- [ ] Move database to managed Postgres (Supabase/Render free tier) for persistence
- [ ] Deployed, persistent live link
- [ ] Multiple chat sessions
- [ ] Improved streaming markdown rendering
- [ ] Better error handling / friendly fallback messages
- [ ] Telegram interface (planned for a later version)
- [ ] Weekly newsletter auto-ingestion into `reading_items`
- [ ] v3: broader personal life OS — contacts/networking, habits, knowledge management

---
