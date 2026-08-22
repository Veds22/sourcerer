"""
LLM orchestration -- NOT USED IN V1.

In v1, Claude Desktop is the MCP client and LLM orchestrator: it connects
to src/mcp_server.py directly over stdio and calls tools from src/tools/
itself. Nothing in v1 imports this module.

This file is reserved for v2, when it will house:
    - A Groq-based summarizer_fn to pass into db.summarize_and_trim()
      for compacting old message history (see db.py's summarizer_fn
      injection pattern -- db.py stays free of any import from this file).
    - Possibly, message-handling/orchestration logic for the WhatsApp
      integration, once sourcerer is no longer driven by Claude Desktop.

Kept as an empty stub for now so the project structure matches the
intended v2 shape without pulling any v2 dependencies (groq, etc.)
into v1's pyproject.toml.
"""