"""
Shared MCP server instance for sourcerer.
 
Tool modules under src/tools/ import `mcp` from here and register their
functions with @mcp.tool(). This file is the single source of truth for
the server instance so there's never more than one FastMCP object alive.
"""

from fastmcp import FastMCP
from src.db import init_db

mcp = FastMCP("sourcerer")

init_db()

from src.tools import applications
from src.tools import reading
from src.tools import links
from src.tools import todos