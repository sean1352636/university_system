"""What the Add Student form collects that does not live on ``students``.

The other systems' add forms ask for an emergency contact and medical notes.
The university already keeps both in the health record, so the add form
writes them there, in the same transaction as the student row:

* the emergency contact becomes the student's primary contact in
  ``emergency_contacts`` (what Health > Emergency contacts shows), with the
  one-line summary on ``students.emergency_contact`` that the edit form and
  exports read;
* medical notes are added to the student's ``medical_info`` conditions for
  the health team.

The change history records that each was added, never the medical text.
Functions take an open connection and do not commit.
"""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.application.students import record_rules


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}


def _ensure_table(conn, table: str) -> set[str]:
    """``table``'s columns, creating it from the health schema if this
    database has never had the health tables applied."""
    cols = _columns(conn, table)
    if cols:
        return cols
    from education_system.systems.university.domains.health.infrastructure.health import (
        health_schema,
    )
    health_schema.apply_to_connection(conn)  # inside our transaction: no commit
    return _columns(conn, table)


def contact_summary(name: str, relationship: str, phone: str) -> str:
    """``"Ann Smith (Parent) 07700 900123"`` for ``students.emergency_contact``."""
    return " ".join(p for p in (name, f"({relationship})" if relationship else "", phone) if p)


def add_emergency_contact(conn, student_id: str, *, name: str, relationship: str,
                          phone: str, actor_id) -> int | None:
    """Add the primary contact; returns its id (None when nothing was given)."""
    name, phone = (name or "").strip(), (phone or "").strip()
    relationship = record_rules.relationship_choice(relationship)
    if not (name and phone):
        return None
    cols = _ensure_table(conn, "emergency_contacts")
    values = {"student_id": str(student_id), "contact_name": name,
              "relationship": relationship or None, "phone_primary": phone,
              # Older copies of the table used name/phone.
              "name": name, "phone": phone, "is_primary": 1, "priority_order": 1,
              "medical_decision_maker": 0,
              "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    values = {k: v for k, v in values.items() if k in cols}
    if "is_primary" in cols:
        conn.execute("UPDATE emergency_contacts SET is_primary = 0 WHERE student_id = ?",
                     (str(student_id),))
    cur = conn.execute(
        f"INSERT INTO emergency_contacts ({', '.join(values)}) "  # nosec B608 - fixed names
        f"VALUES ({', '.join('?' * len(values))})", tuple(values.values()))
    summary = contact_summary(name, relationship, phone)
    if "emergency_contact" in _columns(conn, "students"):
        conn.execute("UPDATE students SET emergency_contact = ? WHERE student_id = ?",
                     (summary, str(student_id)))
    record_rules.record_changes(conn, str(student_id), {}, {"emergency_contact": summary},
                                "Emergency contact given on the add form", actor_id)
    return cur.lastrowid


def add_medical_notes(conn, student_id: str, text: str, *, actor_id) -> bool:
    """Append ``text`` to the student's medical conditions; False if blank."""
    text = (text or "").strip()
    if not text:
        return False
    _ensure_table(conn, "medical_info")
    block = f"Given on the Add Student form ({datetime.now():%Y-%m-%d}):\n{text}"
    row = conn.execute("SELECT id, conditions FROM medical_info WHERE student_id = ? "
                       "ORDER BY id DESC LIMIT 1", (str(student_id),)).fetchone()
    if row:
        old = row[1]
        conn.execute("UPDATE medical_info SET conditions = ?, last_updated = CURRENT_TIMESTAMP "
                     "WHERE id = ?", (f"{old}\n\n{block}" if old else block, row[0]))
    else:
        conn.execute("INSERT INTO medical_info (student_id, conditions) VALUES (?, ?)",
                     (str(student_id), block))
    record_rules.record_changes(conn, str(student_id), {},
                                {"medical_record": "medical notes added for the health team"},
                                "Medical notes given on the add form", actor_id)
    return True


def store(conn, student_id: str, command, actor_id) -> None:
    """Both of the above from a validated ``StudentCommand``."""
    add_emergency_contact(conn, student_id, name=command.emergency_contact_name,
                          relationship=command.emergency_contact_relationship,
                          phone=command.emergency_contact_phone, actor_id=actor_id)
    add_medical_notes(conn, student_id, command.medical_notes, actor_id=actor_id)
