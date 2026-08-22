"""
MCP tools for tracking todos, optionally linked to an application or reading item.

Registers against the shared fastmcp instance defined in src/mcp_server.py.
"""

import asyncio
from datetime import date

from src.db import get_connection
from src.mcp import mcp


## --- Internal DB Helpers --- ##


def _row_to_dict(row) -> dict:
    d = dict(row)
    d["completed"] = bool(d["completed"])
    return d


def _application_exists(conn, application_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        is not None
    )


def _reading_item_exists(conn, reading_item_id: int) -> bool:
    return (
        conn.execute(
            "SELECT 1 FROM reading_items WHERE id = ?", (reading_item_id,)
        ).fetchone()
        is not None
    )


## --- Internal Sync Implementations (run in worker threads) --- ##
 
 
def _sync_add_todo(
    description: str,
    due_date: str | None,
    application_id: int | None,
    reading_item_id: int | None,
) -> dict:
    conn = get_connection()
 
    if application_id is not None and not _application_exists(conn, application_id):
        conn.close()
        return {"error": f"No application found with id {application_id}"}
 
    if reading_item_id is not None and not _reading_item_exists(conn, reading_item_id):
        conn.close()
        return {"error": f"No reading item found with id {reading_item_id}"}
 
    cursor = conn.execute(
        """
        INSERT INTO todos (description, due_date, application_id, reading_item_id)
        VALUES (?, ?, ?, ?)
        """,
        (description, due_date, application_id, reading_item_id),
    )
    conn.commit()
    todo_id = cursor.lastrowid
 
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)
 
 
def _sync_complete_todo(todo_id: int) -> dict:
    conn = get_connection()
    existing = conn.execute("SELECT id FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if existing is None:
        conn.close()
        return {"error": f"No todo found with id {todo_id}"}
 
    conn.execute("UPDATE todos SET completed = 1 WHERE id = ?", (todo_id,))
    conn.commit()
 
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)
 
 
def _sync_edit_todo(todo_id: int, updates: dict) -> dict:
    conn = get_connection()
    existing = conn.execute("SELECT id FROM todos WHERE id = ?", (todo_id,)).fetchone()
    if existing is None:
        conn.close()
        return {"error": f"No todo found with id {todo_id}"}
 
    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [todo_id]
    conn.execute(f"UPDATE todos SET {set_clause} WHERE id = ?", values)
    conn.commit()
 
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.close()
    return _row_to_dict(row)
 
 
def _sync_get_todo(todo_id: int) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
    conn.close()
    if row is None:
        return {"error": f"No todo found with id {todo_id}"}
    return _row_to_dict(row)
 
 
def _sync_list_todos(completed: bool | None, overdue_only: bool, limit: int) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM todos WHERE 1=1"
    params: list = []
 
    if overdue_only:
        query += " AND completed = 0 AND due_date IS NOT NULL AND due_date < ?"
        params.append(date.today().isoformat())
    elif completed is not None:
        query += " AND completed = ?"
        params.append(1 if completed else 0)
 
    query += " ORDER BY (due_date IS NULL), due_date ASC LIMIT ?"
    params.append(limit)
 
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]
 
 
def _sync_search_todos(query: str) -> list[dict]:
    conn = get_connection()
    like_query = f"%{query}%"
    rows = conn.execute(
        """
        SELECT * FROM todos
        WHERE description LIKE ? COLLATE NOCASE
        ORDER BY (due_date IS NULL), due_date ASC
        """,
        (like_query,),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]
 
 
## --- MCP Tools --- ##
 
 
@mcp.tool()
async def add_todo(
    description: str,
    due_date: str | None = None,
    application_id: int | None = None,
    reading_item_id: int | None = None,
) -> dict:
    """Add a new todo, optionally linked to an application or reading item.
 
    Args:
        description: What needs to be done.
        due_date: Optional due date, format YYYY-MM-DD.
        application_id: Optional id of an application this todo relates to
            (e.g. "follow up with recruiter").
        reading_item_id: Optional id of a reading item this todo relates to
            (e.g. "finish reading this paper"). A todo should reference at
            most one of application_id / reading_item_id, not both.
 
    Returns:
        The newly created todo, or an error dict if a referenced id doesn't exist.
    """
    return await asyncio.to_thread(
        _sync_add_todo, description, due_date, application_id, reading_item_id
    )
 
 
@mcp.tool()
async def complete_todo(todo_id: int) -> dict:
    """Mark a todo as completed.
 
    Args:
        todo_id: ID of the todo to mark complete.
 
    Returns:
        The updated todo, or an error dict if not found.
    """
    return await asyncio.to_thread(_sync_complete_todo, todo_id)
 
 
@mcp.tool()
async def edit_todo(
    todo_id: int,
    description: str | None = None,
    due_date: str | None = None,
    completed: bool | None = None,
) -> dict:
    """Edit fields of an existing todo. Only provided fields are changed.
 
    Args:
        todo_id: ID of the todo to edit.
        description: New description, if changing.
        due_date: New due date, YYYY-MM-DD, if changing.
        completed: New completed state, if changing. Use complete_todo for
            the common case of marking something done.
 
    Returns:
        The updated todo, or an error dict if not found.
    """
    fields = {"description": description, "due_date": due_date}
    updates = {k: v for k, v in fields.items() if v is not None}
    if completed is not None:
        updates["completed"] = 1 if completed else 0
 
    if not updates:
        return {"error": "No fields provided to update."}
 
    return await asyncio.to_thread(_sync_edit_todo, todo_id, updates)
 
 
@mcp.tool()
async def get_todo(todo_id: int) -> dict:
    """Fetch a single todo by id.
 
    Args:
        todo_id: ID of the todo to fetch.
 
    Returns:
        The todo, or an error dict if not found.
    """
    return await asyncio.to_thread(_sync_get_todo, todo_id)
 
 
@mcp.tool()
async def list_todos(
    completed: bool | None = None, overdue_only: bool = False, limit: int = 50
) -> list[dict]:
    """List todos, soonest due date first (todos with no due date last).
 
    Args:
        completed: If provided, only return todos with this completed state.
        overdue_only: If True, only return incomplete todos whose due_date
            has already passed. Ignores the completed filter when True
            (overdue implies not completed).
        limit: Max number of results to return. Defaults to 50.
 
    Returns:
        A list of todos.
    """
    return await asyncio.to_thread(_sync_list_todos, completed, overdue_only, limit)
 
 
@mcp.tool()
async def search_todos(query: str) -> list[dict]:
    """Search todos by description (case-insensitive, partial match).
 
    Args:
        query: Text to search for in the todo description.
 
    Returns:
        A list of matching todos.
    """
    return await asyncio.to_thread(_sync_search_todos, query)
 