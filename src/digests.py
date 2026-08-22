"""
Digest content builders for sourcerer proactive messages.

Each function queries the DB and returns a formatted string ready to send.
Called by src/scheduler.py on a fixed schedule.
"""

from datetime import date

from src.db import get_connection


def build_todos_digest() -> str | None:
    """Build a digest of incomplete todos, prioritising overdue and due-today.

    Returns:
        Formatted string ready to send, or None if there are no pending todos.
    """
    today = date.today().isoformat()

    conn = get_connection()
    rows = conn.execute(
        """
        SELECT description, due_date
        FROM todos
        WHERE completed = 0
        ORDER BY (due_date IS NULL), due_date ASC
        LIMIT 20
        """,
    ).fetchall()
    conn.close()

    if not rows:
        return None

    overdue, due_today, upcoming, no_date = [], [], [], []

    for row in rows:
        desc = row["description"]
        due = row["due_date"]

        if due is None:
            no_date.append(f"• {desc}")
        elif due < today:
            overdue.append(f"• {desc} (was {due})")
        elif due == today:
            due_today.append(f"• {desc}")
        else:
            upcoming.append(f"• {desc} (due {due})")

    sections = []
    if overdue:
        sections.append("🔴 Overdue\n" + "\n".join(overdue))
    if due_today:
        sections.append("🟡 Due today\n" + "\n".join(due_today))
    if upcoming:
        sections.append("🟢 Upcoming\n" + "\n".join(upcoming))
    if no_date:
        sections.append("⚪ No due date\n" + "\n".join(no_date))

    return "📋 *Todo digest*\n\n" + "\n\n".join(sections)


def build_applications_digest() -> str | None:
    """Build a digest of active job applications grouped by status.

    Returns:
        Formatted string ready to send, or None if there are no active applications.
    """
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT company, role, status, last_update_date
        FROM applications
        WHERE status NOT IN ('rejected', 'withdrawn')
        ORDER BY
            CASE status
                WHEN 'offer'        THEN 1
                WHEN 'interview'    THEN 2
                WHEN 'phone_screen' THEN 3
                WHEN 'applied'      THEN 4
                ELSE 5
            END,
            last_update_date DESC
        LIMIT 20
        """,
    ).fetchall()
    conn.close()

    if not rows:
        return None

    # Group by status
    groups: dict[str, list[str]] = {}
    for row in rows:
        status = row["status"]
        entry = f"• {row['company']} — {row['role']} (updated {row['last_update_date']})"
        groups.setdefault(status, []).append(entry)

    STATUS_LABELS = {
        "offer":        "🎉 Offer",
        "interview":    "🔵 Interview",
        "phone_screen": "🟡 Phone screen",
        "applied":      "⚪ Applied",
    }

    sections = []
    for status, label in STATUS_LABELS.items():
        if status in groups:
            sections.append(f"{label}\n" + "\n".join(groups[status]))

    return "💼 *Applications digest*\n\n" + "\n\n".join(sections)