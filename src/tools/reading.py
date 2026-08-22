"""
MCP tools for tracking reading items (articles, papers, videos, etc.).

Registers against the shared fastmcp instance defined in src/mcp_server.py.
"""

import asyncio

from src.db import get_connection
from src.mcp import mcp

VALID_TYPES = {"article", "paper", "video", "repo", "other"}


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


def _sync_add_reading_item(
    type: str,
    title: str | None,
    url: str | None,
    summary: str | None,
    tags: list[str] | None,
    raw_content_ref: str | None,
) -> dict:
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO reading_items (type, title, url, summary, tags, raw_content_ref)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (type, title, url, summary, _join_tags(tags), raw_content_ref),
    )
    conn.commit()
    item_id = cursor.lastrowid

    row = conn.execute(
        "SELECT * FROM reading_items WHERE id = ?", (item_id,)
    ).fetchone()
    conn.close()
    result = _row_to_dict(row)
    result["tags"] = _split_tags(result["tags"])
    return result


def _sync_edit_reading_item(item_id: int, updates: dict) -> dict:
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM reading_items WHERE id = ?", (item_id,)
    ).fetchone()
    if existing is None:
        conn.close()
        return {"error": f"No reading item found with id {item_id}"}

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    values = list(updates.values()) + [item_id]
    conn.execute(f"UPDATE reading_items SET {set_clause} WHERE id = ?", values)
    conn.commit()

    row = conn.execute(
        "SELECT * FROM reading_items WHERE id = ?", (item_id,)
    ).fetchone()
    conn.close()
    result = _row_to_dict(row)
    result["tags"] = _split_tags(result["tags"])
    return result


def _sync_get_reading_item(item_id: int) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM reading_items WHERE id = ?", (item_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return {"error": f"No reading item found with id {item_id}"}

    result = _row_to_dict(row)
    result["tags"] = _split_tags(result["tags"])
    return result


def _sync_list_reading_items(type: str | None, tag: str | None, limit: int) -> list[dict]:
    conn = get_connection()
    query = "SELECT * FROM reading_items WHERE 1=1"
    params: list = []

    if type is not None:
        query += " AND type = ?"
        params.append(type)

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


def _sync_search_reading_items(query: str) -> list[dict]:
    conn = get_connection()
    like_query = f"%{query}%"
    rows = conn.execute(
        """
        SELECT * FROM reading_items
        WHERE title LIKE ? COLLATE NOCASE
           OR summary LIKE ? COLLATE NOCASE
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
async def add_reading_item(
    type: str,
    title: str | None = None,
    url: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
    raw_content_ref: str | None = None,
) -> dict:
    """Save a new reading item (article, paper, video, repo, etc.).

    Args:
        type: Kind of item. One of: article, paper, video, repo, other.
        title: Title of the item.
        url: Source URL, if any.
        summary: Short summary or note about the item.
        tags: List of tags, e.g. ["llm", "agents"].
        raw_content_ref: Reference to stored raw content (e.g. a file path),
            if the full content was captured separately.

    Returns:
        The newly created reading item.
    """
    if type not in VALID_TYPES:
        return {"error": f"Invalid type '{type}'. Must be one of: {sorted(VALID_TYPES)}"}

    return await asyncio.to_thread(
        _sync_add_reading_item, type, title, url, summary, tags, raw_content_ref
    )


@mcp.tool()
async def edit_reading_item(
    item_id: int,
    title: str | None = None,
    url: str | None = None,
    summary: str | None = None,
    tags: list[str] | None = None,
    raw_content_ref: str | None = None,
) -> dict:
    """Edit fields of an existing reading item. Only provided fields are changed.

    Args:
        item_id: ID of the reading item to edit.
        title: New title, if changing.
        url: New URL, if changing.
        summary: New summary, if changing (replaces existing summary).
        tags: New full list of tags, if changing (replaces existing tags entirely).
        raw_content_ref: New raw content reference, if changing.

    Returns:
        The updated reading item, or an error dict if not found.
    """
    fields = {
        "title": title,
        "url": url,
        "summary": summary,
        "raw_content_ref": raw_content_ref,
    }
    updates = {k: v for k, v in fields.items() if v is not None}
    if tags is not None:
        updates["tags"] = _join_tags(tags)

    if not updates:
        return {"error": "No fields provided to update."}

    return await asyncio.to_thread(_sync_edit_reading_item, item_id, updates)


@mcp.tool()
async def get_reading_item(item_id: int) -> dict:
    """Fetch a single reading item by id.

    Args:
        item_id: ID of the reading item to fetch.

    Returns:
        The reading item, or an error dict if not found.
    """
    return await asyncio.to_thread(_sync_get_reading_item, item_id)


@mcp.tool()
async def list_reading_items(
    type: str | None = None, tag: str | None = None, limit: int = 50
) -> list[dict]:
    """List saved reading items, most recently saved first.

    Args:
        type: If provided, only return items of this type.
            One of: article, paper, video, repo, other.
        tag: If provided, only return items whose tags include this tag
            (case-insensitive, exact tag match).
        limit: Max number of results to return. Defaults to 50.

    Returns:
        A list of reading items.
    """
    if type is not None and type not in VALID_TYPES:
        return [{"error": f"Invalid type '{type}'. Must be one of: {sorted(VALID_TYPES)}"}]

    return await asyncio.to_thread(_sync_list_reading_items, type, tag, limit)


@mcp.tool()
async def search_reading_items(query: str) -> list[dict]:
    """Search reading items by title or summary (case-insensitive, partial match).

    Args:
        query: Text to search for in title or summary fields.

    Returns:
        A list of matching reading items.
    """
    return await asyncio.to_thread(_sync_search_reading_items, query)