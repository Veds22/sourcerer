"""
MCP tools for tracking job applications (applications + application_status_history).
 
Registers against the shared fastmcp instance defined in src/mcp_server.py.
"""

import asyncio
from datetime import date

from src.db import get_connection
from src.mcp import mcp

VALID_STATUSES = {
    "applied",
    "phone_screen",
    "interview",
    "offer",
    "rejected",
    "withdrawn",
}
 
 
## --- Internal DB Helpers --- ##


def _row_to_dict(row) -> dict:
    return dict(row)
 
def _get_status_history(conn, application_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT status, changed_at
        FROM application_status_history
        WHERE application_id = ?
        ORDER BY changed_at ASC
        """,
        (application_id,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


## --- Internal Sync Implementations (run in worker threads) --- ##
 
 
def _sync_add_application(
    company: str,
    role: str,
    referral: str | None,
    status: str,
    applied_date: str | None,
    deadline: str | None,
    notes: str | None,
) -> dict:
    applied = applied_date or date.today().isoformat()
 
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO applications (company, role, referral, status, applied_date, last_update_date, deadline, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (company, role, referral, status, applied, applied, deadline, notes),
    )
 
    application_id = cursor.lastrowid
    conn.execute(
        """
        INSERT INTO application_status_history (application_id, status)
        VALUES (?, ?)
        """,
        (application_id, status),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    conn.close()
    return _row_to_dict(row)
 
 
def _sync_update_application_status(application_id: int, new_status: str) -> dict:
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return {"error": f"No application found with id {application_id}"}
 
    today = date.today().isoformat()
    conn.execute(
        "UPDATE applications SET status = ?, last_update_date = ? WHERE id = ?",
        (new_status, today, application_id),
    )
    conn.execute(
        "INSERT INTO application_status_history (application_id, status) VALUES (?, ?)",
        (application_id, new_status),
    )
    conn.commit()
 
    row = conn.execute(
        "SELECT * FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    conn.close()
    return _row_to_dict(row)
 
 
def _sync_edit_application(application_id: int, updates: dict) -> dict:
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return {"error": f"No application found with id {application_id}"}
 
    updates["last_update_date"] = date.today().isoformat()
    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [application_id]
    conn.execute(f"UPDATE applications SET {set_clause} WHERE id = ?", values)
    conn.commit()
 
    row = conn.execute(
        "SELECT * FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    conn.close()
    return _row_to_dict(row)
 
 
def _sync_get_application(application_id: int) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM applications WHERE id = ?", (application_id,)
    ).fetchone()
    if row is None:
        conn.close()
        return {"error": f"No application found with id {application_id}"}
 
    result = _row_to_dict(row)
    result["status_history"] = _get_status_history(conn, application_id)
    conn.close()
    return result
 
 
def _sync_list_applications(status: str | None, limit: int) -> list[dict]:
    conn = get_connection()
    if status is not None:
        rows = conn.execute(
            """
            SELECT * FROM applications
            WHERE status = ?
            ORDER BY last_update_date DESC
            LIMIT ?
            """,
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM applications
            ORDER BY last_update_date DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]
 
 
def _sync_search_applications(query: str) -> list[dict]:
    conn = get_connection()
    like_query = f"%{query}%"
    rows = conn.execute(
        """
        SELECT * FROM applications
        WHERE company LIKE ? COLLATE NOCASE
           OR role LIKE ? COLLATE NOCASE
        ORDER BY last_update_date DESC
        """,
        (like_query, like_query),
    ).fetchall()
    conn.close()
    return [_row_to_dict(r) for r in rows]
 

## --- MCP Tools --- ##
 
 
@mcp.tool
async def add_application(
    company: str,
    role: str,
    referral: str | None = None,
    status: str = "applied",
    applied_date: str | None = None,
    deadline: str | None = None,
    notes: str | None = None,
) -> dict:
    """Add a new job application to track.
 
    Args:
        company: Company name.
        role: Job title / role applied to.
        referral: Name of referrer, if any.
        status: Initial status. One of: applied, phone_screen, interview,
            offer, rejected, withdrawn. Defaults to 'applied'.
        applied_date: Date applied, format YYYY-MM-DD. Defaults to today.
        deadline: Optional deadline (e.g. for an offer decision), YYYY-MM-DD.
        notes: Freeform notes.
 
    Returns:
        The newly created application record.
    """
    if status not in VALID_STATUSES:
        return {
            "error": f"Invalid status '{status}'. Must be one of: {', '.join(VALID_STATUSES)}"
        }
 
    return await asyncio.to_thread(
        _sync_add_application,
        company,
        role,
        referral,
        status,
        applied_date,
        deadline,
        notes,
    )
 
 
@mcp.tool
async def update_application_status(application_id: int, new_status: str) -> dict:
    """Change the status of an existing application, logging the transition.
 
    Args:
        application_id: ID of the application to update.
        new_status: One of: applied, phone_screen, interview, offer, rejected, withdrawn.
 
    Returns:
        The updated application record, or an error dict if invalid.
    """
    if new_status not in VALID_STATUSES:
        return {
            "error": f"Invalid status '{new_status}'. Must be one of: {sorted(VALID_STATUSES)}"
        }
 
    return await asyncio.to_thread(
        _sync_update_application_status, application_id, new_status
    )
 
 
@mcp.tool
async def edit_application(
    application_id: int,
    company: str | None = None,
    role: str | None = None,
    referral: str | None = None,
    deadline: str | None = None,
    notes: str | None = None,
) -> dict:
    """Edit application fields other than status. Only provided fields are changed.
 
    Args:
        application_id: ID of the application to edit.
        company: New company name, if changing.
        role: New role/title, if changing.
        referral: New referral name, if changing.
        deadline: New deadline, YYYY-MM-DD, if changing.
        notes: New notes, if changing (replaces existing notes).
 
    Returns:
        The updated application record, or an error dict if not found.
    """
    fields = {
        "company": company,
        "role": role,
        "referral": referral,
        "deadline": deadline,
        "notes": notes,
    }
    updates = {k: v for k, v in fields.items() if v is not None}
 
    if not updates:
        return {"error": "No fields provided to update."}
 
    return await asyncio.to_thread(_sync_edit_application, application_id, updates)
 
 
@mcp.tool
async def get_application(application_id: int) -> dict:
    """Fetch a single application along with its full status history.
 
    Args:
        application_id: ID of the application to fetch.
 
    Returns:
        The application record with a 'status_history' list attached,
        or an error dict if not found.
    """
    return await asyncio.to_thread(_sync_get_application, application_id)
 
 
@mcp.tool
async def list_applications(status: str | None = None, limit: int = 25) -> list[dict]:
    """List tracked applications, most recently updated first.
 
    Args:
        status: If provided, only return applications with this status.
            One of: applied, phone_screen, interview, offer, rejected, withdrawn.
        limit: Max number of results to return. Defaults to 25.
 
    Returns:
        A list of application records.
    """
    if status is not None and status not in VALID_STATUSES:
        return [
            {
                "error": f"Invalid status '{status}'. Must be one of: {sorted(VALID_STATUSES)}"
            }
        ]
 
    return await asyncio.to_thread(_sync_list_applications, status, limit)
 
 
@mcp.tool
async def search_applications(query: str) -> list[dict]:
    """Search applications by company name or role (case-insensitive, partial match).
 
    Args:
        query: Text to search for in company or role fields.
 
    Returns:
        A list of matching application records.
    """
    return await asyncio.to_thread(_sync_search_applications, query)
 