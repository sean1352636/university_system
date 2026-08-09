"""Correspondence persistence: the college's message log."""

from __future__ import annotations

from education_system.systems.fe_college.domain.communications.messages import (
    Message,
    Outbox,
    next_message_id,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.infrastructure.persistence import (
    read_only,
    transaction,
)

# Names joined in for display. Kept in one string so the SELECT and
# ``Message.from_row`` cannot drift apart.
_SELECT = """
SELECT m.*,
       TRIM(COALESCE(st.first_name, '') || ' ' || COALESCE(st.last_name, ''))
           AS student_name,
       TRIM(COALESCE(sf.first_name, '') || ' ' || COALESCE(sf.last_name, ''))
           AS staff_name
  FROM email_messages m
  LEFT JOIN students st ON st.student_id = m.student_id
  LEFT JOIN staff    sf ON sf.staff_id   = m.staff_id
"""

_ORDER = " ORDER BY COALESCE(m.sent_at, m.created_at) DESC, m.message_id DESC"


def all_message_ids() -> list[str]:
    with read_only() as conn:
        return [r[0] for r in
                conn.execute("SELECT message_id FROM email_messages").fetchall()]


def get(message_id: str) -> Message | None:
    with read_only() as conn:
        row = conn.execute(
            _SELECT + " WHERE m.message_id = ?", (message_id,)).fetchone()
    return Message.from_row(row) if row else None


def search(
    *,
    direction: str | None = None,
    status: str | None = None,
    category: str | None = None,
    student_id: str | None = None,
    query: str | None = None,
) -> list[Message]:
    """Filtered message list, newest first.

    Every filter is optional and they compose, so the same call backs the
    inbox, the outbox, the drafts view and one learner's correspondence.
    """
    clauses: list[str] = []
    params: list[object] = []
    if direction:
        clauses.append("m.direction = ?")
        params.append(direction)
    if status:
        clauses.append("m.status = ?")
        params.append(status)
    if category:
        clauses.append("m.category = ?")
        params.append(category)
    if student_id:
        clauses.append("m.student_id = ?")
        params.append(student_id)
    if query and query.strip():
        like = f"%{query.strip()}%"
        clauses.append(
            "(m.subject LIKE ? OR m.body LIKE ? OR m.to_address LIKE ? "
            "OR m.to_name LIKE ? OR m.from_address LIKE ? OR m.message_id LIKE ?)")
        params.extend([like] * 6)

    sql = _SELECT + (" WHERE " + " AND ".join(clauses) if clauses else "") + _ORDER
    with read_only() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Message.from_row(r) for r in rows]


def create(message: Message) -> Message:
    """Insert a validated message, allocating its reference."""
    message.validate()
    if not message.message_id:
        message.message_id = next_message_id(all_message_ids())
    row = message.to_row()
    placeholders = ", ".join("?" for _ in row)
    with transaction() as conn:
        conn.execute(
            f"INSERT INTO email_messages ({', '.join(row)}) "  # noqa: S608
            f"VALUES ({placeholders})",
            list(row.values()),
        )
    return message


def update(message: Message) -> Message:
    if not message.message_id:
        raise ValidationError("Cannot update a message without a reference")
    message.validate()
    row = message.to_row()
    row.pop("message_id")
    assignments = ", ".join(f"{c} = ?" for c in row)
    with transaction() as conn:
        cur = conn.execute(
            f"UPDATE email_messages SET {assignments} "  # noqa: S608
            "WHERE message_id = ?",
            [*row.values(), message.message_id],
        )
        if cur.rowcount == 0:
            raise ValidationError(f"No message with reference {message.message_id}")
    return message


def delete(message_id: str) -> bool:
    with transaction() as conn:
        cur = conn.execute(
            "DELETE FROM email_messages WHERE message_id = ?", (message_id,))
        return cur.rowcount > 0


def outbox() -> Outbox:
    """Counts for the email centre header, in one pass over the table."""
    with read_only() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'Draft'    THEN 1 ELSE 0 END) AS drafts,
                   SUM(CASE WHEN status = 'Sent'     THEN 1 ELSE 0 END) AS sent,
                   SUM(CASE WHEN direction='Incoming' THEN 1 ELSE 0 END) AS incoming,
                   SUM(CASE WHEN status = 'Failed'   THEN 1 ELSE 0 END) AS failed
              FROM email_messages
            """).fetchone()
    return Outbox(
        total=row["total"] or 0,
        drafts=row["drafts"] or 0,
        sent=row["sent"] or 0,
        incoming=row["incoming"] or 0,
        failed=row["failed"] or 0,
    )


def recipients() -> list[dict]:
    """Everyone the compose screen can address.

    Learners first (they are who the college writes to most), then staff.
    Each entry carries what a new message needs, so picking one fills the
    form rather than the user retyping an address that is already on file.
    """
    with read_only() as conn:
        learners = conn.execute(
            "SELECT student_id, first_name, last_name, email, tutor_group "
            "FROM students WHERE status IN ('applicant','enrolled') "
            "ORDER BY last_name, first_name").fetchall()
        staff = conn.execute(
            "SELECT staff_id, first_name, last_name, role, email FROM staff "
            "ORDER BY last_name, first_name").fetchall()

    out: list[dict] = []
    for r in learners:
        name = f"{r['first_name']} {r['last_name']}".strip()
        group = f" — {r['tutor_group']}" if r["tutor_group"] else ""
        email = r["email"] or ""
        out.append({
            "kind": "Learner",
            "label": f"{name} ({r['student_id']}){group}"
                     + (f" — {email}" if email else " — no email on file"),
            "to_name": name,
            "to_address": email,
            "student_id": r["student_id"],
            "staff_id": "",
        })
    for r in staff:
        name = f"{r['first_name']} {r['last_name']}".strip()
        email = r["email"] or ""
        out.append({
            "kind": "Staff",
            "label": f"{name} ({r['role']})" + (f" — {email}" if email else ""),
            "to_name": name,
            "to_address": email,
            "student_id": "",
            "staff_id": r["staff_id"],
        })
    return out
