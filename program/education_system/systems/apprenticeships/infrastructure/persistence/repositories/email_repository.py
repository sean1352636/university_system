"""Correspondence persistence: the provider's message log."""

from __future__ import annotations

from typing import Any

from education_system.systems.apprenticeships.infrastructure.persistence.repositories.base import (
    col,
    connect,
    init_db,
)

# Names joined for display, so a list screen can caption a row that only
# stores ids. Kept as one string so the SELECT and the mapper cannot drift.
_SELECT = """
SELECT m.*,
       TRIM(COALESCE(a.given_name, '') || ' ' || COALESCE(a.family_name, ''))
           AS apprentice_name,
       e.name AS employer_name
  FROM email_messages m
  LEFT JOIN apprentices a ON a.apprentice_id = m.apprentice_id
  LEFT JOIN employers   e ON e.employer_id   = m.employer_id
"""

_ORDER = " ORDER BY COALESCE(m.sent_at, m.created_at) DESC, m.message_id DESC"

_FIELDS = (
    "direction", "channel", "category", "priority", "status", "subject",
    "body", "from_name", "from_address", "to_name", "to_address",
    "apprentice_id", "employer_id", "sent_by", "tags", "sent_at",
)


def _map(row: Any) -> dict[str, Any]:
    """Rows are returned as plain dicts.

    A message has no behaviour of its own — the rules live in the service
    — so a dataclass here would be a second name for the same shape.
    """
    return {
        "message_id": row["message_id"],
        "direction": row["direction"],
        "channel": row["channel"],
        "category": row["category"],
        "priority": row["priority"],
        "status": row["status"],
        "subject": row["subject"],
        "body": col(row, "body"),
        "from_name": col(row, "from_name"),
        "from_address": col(row, "from_address"),
        "to_name": col(row, "to_name"),
        "to_address": col(row, "to_address"),
        "apprentice_id": col(row, "apprentice_id"),
        "employer_id": col(row, "employer_id"),
        "sent_by": col(row, "sent_by"),
        "tags": col(row, "tags"),
        "created_at": col(row, "created_at"),
        "sent_at": col(row, "sent_at"),
        "apprentice_name": (col(row, "apprentice_name") or "").strip() or None,
        "employer_name": col(row, "employer_name"),
    }


def next_message_id() -> str:
    """Allocate the next ``APM-nnnn`` reference.

    Sequential, so the log reads in the order it was written — which is
    how anyone reconstructing a dispute or an audit trail reads it.
    """
    init_db()
    with connect() as conn:
        rows = conn.execute(
            "SELECT message_id FROM email_messages "
            "WHERE message_id LIKE 'APM-%'").fetchall()
    used = [
        int(r["message_id"][4:])
        for r in rows
        if r["message_id"][4:].isdigit()
    ]
    return f"APM-{(max(used) + 1 if used else 1):04d}"


def get(message_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as conn:
        row = conn.execute(
            _SELECT + " WHERE m.message_id = ?", (message_id,)).fetchone()
    return _map(row) if row else None


def search(
    *,
    direction: str | None = None,
    status: str | None = None,
    category: str | None = None,
    apprentice_id: int | None = None,
    employer_id: int | None = None,
    apprentice_ids: list[int] | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Filtered log, newest first.

    ``apprentice_ids`` scopes the whole result to a set of learners — how
    an employer or a tutor is confined to their own people without every
    caller rebuilding that rule.
    """
    init_db()
    clauses: list[str] = []
    params: list[Any] = []
    if direction:
        clauses.append("m.direction = ?")
        params.append(direction)
    if status:
        clauses.append("m.status = ?")
        params.append(status)
    if category:
        clauses.append("m.category = ?")
        params.append(category)
    if apprentice_id is not None:
        clauses.append("m.apprentice_id = ?")
        params.append(apprentice_id)
    if employer_id is not None:
        clauses.append("m.employer_id = ?")
        params.append(employer_id)
    if apprentice_ids is not None:
        if not apprentice_ids:
            return []          # scoped to nobody: no rows, not all rows
        placeholders = ", ".join("?" for _ in apprentice_ids)
        clauses.append(f"m.apprentice_id IN ({placeholders})")
        params.extend(apprentice_ids)
    if query and query.strip():
        like = f"%{query.strip()}%"
        clauses.append(
            "(m.subject LIKE ? OR m.body LIKE ? OR m.to_address LIKE ? "
            "OR m.to_name LIKE ? OR m.from_address LIKE ? OR m.message_id LIKE ?)")
        params.extend([like] * 6)

    sql = _SELECT + (" WHERE " + " AND ".join(clauses) if clauses else "") + _ORDER
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_map(r) for r in rows]


def create(payload: dict[str, Any]) -> str:
    """Insert a message and return its reference."""
    init_db()
    message_id = payload.get("message_id") or next_message_id()
    columns = ["message_id"] + [f for f in _FIELDS if f in payload]
    values = [message_id] + [payload[c] for c in columns[1:]]
    placeholders = ", ".join("?" for _ in columns)
    with connect() as conn:
        conn.execute(
            f"INSERT INTO email_messages ({', '.join(columns)}) "  # noqa: S608
            f"VALUES ({placeholders})",
            values,
        )
    return message_id


def update(message_id: str, payload: dict[str, Any]) -> None:
    """Update the supplied fields only; anything absent is untouched."""
    init_db()
    columns = [f for f in _FIELDS if f in payload]
    if not columns:
        return
    assignments = ", ".join(f"{c} = ?" for c in columns)
    with connect() as conn:
        conn.execute(
            f"UPDATE email_messages SET {assignments} "  # noqa: S608
            "WHERE message_id = ?",
            [*[payload[c] for c in columns], message_id],
        )


def delete(message_id: str) -> bool:
    init_db()
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM email_messages WHERE message_id = ?", (message_id,))
        return cur.rowcount > 0


def counts(apprentice_ids: list[int] | None = None) -> dict[str, int]:
    """Header totals, scoped the same way as :func:`search`."""
    init_db()
    where, params = "", []
    if apprentice_ids is not None:
        if not apprentice_ids:
            return {"total": 0, "drafts": 0, "sent": 0, "incoming": 0, "failed": 0}
        placeholders = ", ".join("?" for _ in apprentice_ids)
        where = f" WHERE apprentice_id IN ({placeholders})"
        params = list(apprentice_ids)
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'Draft'     THEN 1 ELSE 0 END) AS drafts,
                   SUM(CASE WHEN status = 'Sent'      THEN 1 ELSE 0 END) AS sent,
                   SUM(CASE WHEN direction='Incoming' THEN 1 ELSE 0 END) AS incoming,
                   SUM(CASE WHEN status = 'Failed'    THEN 1 ELSE 0 END) AS failed
              FROM email_messages{where}
            """, params).fetchone()  # noqa: S608
    return {
        "total": row["total"] or 0,
        "drafts": row["drafts"] or 0,
        "sent": row["sent"] or 0,
        "incoming": row["incoming"] or 0,
        "failed": row["failed"] or 0,
    }


def recipients() -> list[dict[str, Any]]:
    """Everyone the compose screen can address.

    Apprentices, then employer contacts, then the EPAOs — the three
    parties a provider actually corresponds with.
    """
    init_db()
    with connect() as conn:
        apprentices = conn.execute(
            "SELECT apprentice_id, given_name, family_name, email, status "
            "FROM apprentices ORDER BY family_name, given_name").fetchall()
        # Contacts are people, not a column on the employer: an employer
        # has a workplace manager who signs reviews and often a separate
        # account contact, so the directory lists the named managers
        # rather than one address per organisation.
        employers = conn.execute(
            """SELECT m.employer_id, m.full_name, m.job_title, m.email,
                      m.is_primary, e.name AS employer_name
                 FROM employer_managers m
                 JOIN employers e ON e.employer_id = m.employer_id
                WHERE m.active = 1
                ORDER BY e.name, m.is_primary DESC, m.full_name""").fetchall()
        epaos = conn.execute(
            "SELECT epao_id, name, contact_name, contact_email FROM epaos "
            "WHERE active = 1 ORDER BY name").fetchall()

    out: list[dict[str, Any]] = []
    for a in apprentices:
        name = f"{a['given_name']} {a['family_name']}".strip()
        email = a["email"] or ""
        out.append({
            "kind": "Apprentice",
            "label": f"{name} ({a['status']})"
                     + (f" — {email}" if email else " — no email on file"),
            "to_name": name,
            "to_address": email,
            "apprentice_id": a["apprentice_id"],
            "employer_id": None,
        })
    for e in employers:
        email = e["email"] or ""
        role = f", {e['job_title']}" if e["job_title"] else ""
        signatory = " — signatory" if e["is_primary"] else ""
        out.append({
            "kind": "Employer",
            "label": f"{e['full_name']}{role} at {e['employer_name']}{signatory}"
                     + (f" — {email}" if email else " — no email on file"),
            "to_name": e["full_name"],
            "to_address": email,
            "apprentice_id": None,
            "employer_id": e["employer_id"],
        })
    for p in epaos:
        email = p["contact_email"] or ""
        contact = p["contact_name"] or p["name"]
        out.append({
            "kind": "EPAO",
            "label": f"{contact} at {p['name']} (EPAO)"
                     + (f" — {email}" if email else " — no email on file"),
            "to_name": contact,
            "to_address": email,
            "apprentice_id": None,
            "employer_id": None,
        })
    return out
