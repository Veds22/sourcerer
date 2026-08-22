"""
MCP tools for saving and retrieving links.

Registers against the shared fastmcp instance defined in src/mcp.py.
"""

import asyncio

from src.db import get_connection
from src.mcp import mcp


## --- Internal Helpers --- ##


def _row_to_dict(row) -> dict:
    return dict(row)


def _split_tags(tags: str | None) -> list[str]:
    if not tags:
        return []
    return [t.strip() for t in tags.split(",") if t.strip()]


def _join_tags(tags: list[str] | None) -> str | None:
    if not tags:
        return None
    return ", ".join(t.strip() for t in tags if t.strip())


## --- Internal Sync Implementations (run in worker threads) --- ##


def _sync_add_link(
    url: str,
    title: str | None,
    tags: list[str] | None,
) -> dict:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO links (url, title, tags)
        VALUES (?, ?, ?)
        """,
        (url, title, _join_tags(tags)),
    )
    conn.commit()
    link_id = cursor.lastrowid

    row = conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
    conn.close()
    result = _row_to_dict(row)
    result["tags"] = _split_tags(result["tags"])
    return result


def _sync_edit_link(link_id: int, updates: dict) -> dict:
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM links WHERE id = ?", (link_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return {"error": f"No link found with id {link_id}"}

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [link_id]
    conn.execute(f"UPDATE links SET {set_clause} WHERE id = ?", values)
    conn.commit()

    row = conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
    conn.close()
    result = _row_to_dict(row)
    result["tags"] = _split_tags(result["tags"])
    return result


def _sync_get_link(link_id: int) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
    conn.close()
    if row is None:
        return {"error": f"No link found with id {link_id}"}
    result = _row_to_dict(row)
    result["tags"] = _split_tags(result["tags"])
    return result


def _sync_list_links(tag: str | None, limit: int) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM links WHERE 1=1"
    params: list = []

    if tag is not None:
        query += " AND (',' || LOWER(tags) || ',') LIKE ?"
        params.append(f"%,{tag.strip().lower()},%")

    query += " ORDER BY saved_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    results = [_row_to_dict(r) for r in rows]
    for r in results:
        r["tags"] = _split_tags(r["tags"])
    return results


def _sync_search_links(query: str) -> list[dict]:
    conn = get_connection()
    like_query = f"%{query}%"
    rows = conn.execute(
        """
        SELECT * FROM links
        WHERE url LIKE ? COLLATE NOCASE
           OR title LIKE ? COLLATE NOCASE
        ORDER BY saved_at DESC
        """,
        (like_query, like_query),
    ).fetchall()
    conn.close()
    results = [_row_to_dict(r) for r in rows]
    for r in results:
        r["tags"] = _split_tags(r["tags"])
    return results


## --- MCP Tools --- ##


@mcp.tool()
async def add_link(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Save a new link.

    Args:
        url: The URL to save.
        title: Optional title or description for the link.
        tags: Optional list of tags, e.g. ["llm", "paper"].

    Returns:
        The newly created link record.
    """
    return await asyncio.to_thread(_sync_add_link, url, title, tags)


@mcp.tool()
async def edit_link(
    link_id: int,
    url: str | None = None,
    title: str | None = None,
    tags: list[str] | None = None,
) -> dict:
    """Edit fields of an existing link. Only provided fields are changed.

    Args:
        link_id: ID of the link to edit.
        url: New URL, if changing.
        title: New title, if changing.
        tags: New full list of tags, if changing (replaces existing tags entirely).

    Returns:
        The updated link record, or an error dict if not found.
    """
    fields = {"url": url, "title": title}
    updates = {k: v for k, v in fields.items() if v is not None}
    if tags is not None:
        updates["tags"] = _join_tags(tags)

    if not updates:
        return {"error": "No fields provided to update."}

    return await asyncio.to_thread(_sync_edit_link, link_id, updates)


@mcp.tool()
async def get_link(link_id: int) -> dict:
    """Fetch a single link by id.

    Args:
        link_id: ID of the link to fetch.

    Returns:
        The link record, or an error dict if not found.
    """
    return await asyncio.to_thread(_sync_get_link, link_id)


@mcp.tool()
async def list_links(
    tag: str | None = None, limit: int = 50
) -> list[dict]:
    """List saved links, most recently saved first.

    Args:
        tag: If provided, only return links whose tags include this tag
            (case-insensitive, exact tag match).
        limit: Max number of results to return. Defaults to 50.

    Returns:
        A list of link records.
    """
    return await asyncio.to_thread(_sync_list_links, tag, limit)


@mcp.tool()
async def search_links(query: str) -> list[dict]:
    """Search links by URL or title (case-insensitive, partial match).

    Args:
        query: Text to search for in url or title fields.

    Returns:
        A list of matching link records.
    """
    return await asyncio.to_thread(_sync_search_links, query)