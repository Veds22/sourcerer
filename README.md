# Sourcerer

A personal assistant MCP server for tracking job applications, reading lists, links, and todos — exposed as MCP tools and tested via Claude Desktop.

## Stack

- **[fastmcp](https://github.com/jlowin/fastmcp)** — MCP server
- **SQLite** — local database (`data/sourcerer.db`)
- **Python 3.11+**
- **[uv](https://github.com/astral-sh/uv)** — package management

## Project Structure

```
sourcerer/
├── data/               # SQLite DB (gitignored)
├── src/
│   ├── db.py           # Schema + connection management
│   ├── mcp_server.py   # FastMCP instance + tool registration
│   ├── llm.py          # Reserved for v2
│   └── tools/
│       ├── applications.py
│       ├── reading.py
│       ├── links.py
│       └── todos.py
├── pyproject.toml
└── uv.lock
```

## Setup

```bash
uv sync
```

## Running

### Claude Desktop (v1 interface)
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "sourcerer": {
      "command": "uv",
      "args": ["--directory", "/path/to/sourcerer", "run", "python", "-m", "src.mcp_server"]
    }
  }
}
```

### Inspector (testing)
```bash
uv run fastmcp dev inspector src/mcp_server.py -e .
```

## Tools

| Module | Tools |
|--------|-------|
| `applications` | `add_application`, `update_application_status`, `edit_application`, `get_application`, `list_applications`, `search_applications` |
| `reading` | `add_reading_item`, `edit_reading_item`, `get_reading_item`, `list_reading_items`, `search_reading_items` |
| `links` | `add_link`, `edit_link`, `get_link`, `list_links`, `search_links` |
| `todos` | `add_todo`, `complete_todo`, `edit_todo`, `get_todo`, `list_todos`, `search_todos` |

## v2 Backlog

- WhatsApp as the primary interface
- FastAPI webhook host + APScheduler for proactive digests
- Groq LLM orchestration + message history summarization
- Weekly newsletter auto-ingestion from GitHub repo
- Google Sheets mirror, Excel export, voice note support