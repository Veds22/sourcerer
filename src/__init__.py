"""
sourcerer: a personal assistant, currently run via Claude Desktop (v1).

Package layout:
    db.py          SQLite schema + connection management
    mcp_server.py  Shared fastmcp instance; imports tools/ to register them
    llm.py         (v2) Groq summarizer for message history compaction
    tools/         MCP tools grouped by domain: applications, reading, links, todos
"""