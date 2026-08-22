"""
Tool modules for the sourcerer MCP server.

Each module (applications, reading, links, todos) defines @mcp.tool()
functions against the shared instance in src/mcp_server.py. Importing
a module registers its tools; that's done centrally in mcp_server.py,
not here, so this file intentionally has no re-exports.
"""