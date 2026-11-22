"""Storage behind the university record-lifecycle rules
(``domains/governance/application/data_lifecycle``).

Which records are past their retention period, and how a disposition is
carried out on them:

* ``applicant`` - an admissions prospect who never became a student, with no
  contact, application or decision for the policy period. Redacted: name,
  e-mail, phone, date of birth and town are blanked; the row stays for
  admissions statistics.
* ``student_record`` - a student whose record was closed longer ago than the
  policy period. Redacted: personal e-mail, phone, address and emergency
  contact (the academic record stays for transcripts and returns).

Finance, health and safeguarding records have their own retention jobs
(finance archive is the ledger itself; the health and safeguarding
purges run from their own workers), so they are never due here.

A legal hold (``services/retention``) blocks a disposition; that check fails
closed. Each record type is OFF until an administrator turns it on
(``data_lifecycle_settings``); until then :func:`due` still reports what
would be disposed. Every disposition is logged in
``data_lifecycle_dispositions``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta

from education_system.systems.university.domains.governance.application.data_lifecycle import (
    UNIVERSITY_POLICIES,
)
from education_system.systems.university.infrastructure.database.db import transaction

_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS data_lifecycle_settings (
        record_type TEXT PRIMARY KEY,
        enabled INTEGER NOT NULL DEFAULT 0,
        updated_by TEXT,
        updated_at TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS data_lifecycle_dispositions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_type TEXT NOT NULL,
        record_id TEXT NOT NULL,
        action TEXT NOT NULL,
        actor_id TEXT NOT NULL,
        disposed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
)

#: Policy field name -> columns on the record's table.
_COLUMNS = {
    "applicant": ("admission_prospects", "prospect_id", {
        "name": ("first_name", "last_name"), "email": ("email",), "phone": ("phone",),
        "address": ("city", "state", "date_of_birth"),
    }),
    "student_record": ("students", "student_id", {
        "personal_email": ("personal_email",), "phone": ("phone",),
        "address": ("address",), "emergency_contact": ("emergency_contact",),
    }),
}
REDACTED = "REDACTED"


def ensure(conn) -> None:
    for sql in _SCHEMA:
        conn.execute(sql)


def _has(conn, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (table,)).fetchone() is not None


def settings() -> dict[str, bool]:
    with transaction() as conn:
        ensure(conn)
        on = dict(conn.execute("SELECT record_type, enabled FROM data_lifecycle_settings"))
    return {name: bool(on.get(name)) for name in UNIVERSITY_POLICIES}


def set_enabled(record_type: str, enabled: bool, *, actor_id: str) -> None:
    if record_type not in UNIVERSITY_POLICIES:
        raise ValueError(f"Unknown record type {record_type!r}")
    with transaction() as conn:
        ensure(conn)
        conn.execute(
            "INSERT INTO data_lifecycle_settings (record_type, enabled, updated_by, updated_at) "
            "VALUES (?, ?, ?, CURRENT_TIMESTAMP) ON CONFLICT(record_type) DO UPDATE SET "
            "enabled=excluded.enabled, updated_by=excluded.updated_by, "
            "updated_at=excluded.updated_at",
            (record_type, int(bool(enabled)), actor_id))


def due(record_type: str, *, today: date | None = None) -> list[str]:
    """Ids of records of ``record_type`` past their retention period and not
    yet disposed of."""
    policy = UNIVERSITY_POLICIES[record_type]
    cutoff = ((today or date.today()) - policy.period).isoformat()
    with transaction() as conn:
        if record_type == "applicant" and _has(conn, "admission_prospects"):
            return [str(r[0]) for r in conn.execute(
                "SELECT p.prospect_id FROM admission_prospects p "
                "WHERE COALESCE(p.first_name, '') <> ? "
                "AND substr(COALESCE(p.last_contact_date, p.created_at, ''), 1, 10) < ? "
                "AND NOT EXISTS (SELECT 1 FROM admission_applications a "
                "  WHERE a.prospect_id = p.prospect_id AND (a.converted_student_id IS NOT NULL "
                "  OR substr(COALESCE(a.decision_date, a.submission_date, ''), 1, 10) >= ?))",
                (REDACTED, cutoff, cutoff))]
        if record_type == "student_record" and _has(conn, "students"):
            return [str(r[0]) for r in conn.execute(
                "SELECT student_id FROM students WHERE record_closed_at IS NOT NULL "
                "AND substr(record_closed_at, 1, 10) < ? "
                "AND (COALESCE(phone, '') <> '' OR COALESCE(address, '') <> '' "
                "OR COALESCE(personal_email, '') <> '' "
                "OR COALESCE(emergency_contact, '') <> '')", (cutoff,))]
    return []


class Repository:
    """The ``LifecycleService`` repository over the live tables."""

    def has_active_hold(self, record_type: str, record_id: str) -> bool:
        if record_type != "student_record":
            return False
        from education_system.systems.university.services.retention import has_active_hold

        return has_active_hold(record_id)

    def redact(self, record_type: str, record_id: str, *, fields: Iterable[str],
               actor_id: str) -> None:
        table, key, mapping = _COLUMNS[record_type]
        columns = [c for f in fields for c in mapping.get(f, ())]
        if not columns:
            return
        with transaction() as conn:
            present = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
            sets = ", ".join(
                f'"{c}" = ?' for c in columns if c in present)  # nosec B608 - fixed names
            values = [REDACTED if c in ("first_name", "last_name") else None
                      for c in columns if c in present]
            conn.execute(f'UPDATE "{table}" SET {sets} WHERE "{key}" = ?',  # nosec B608
                         (*values, record_id))

    def delete(self, record_type: str, record_id: str, *, actor_id: str) -> None:
        raise ValueError(f"{record_type} records are deleted by their own retention job")

    def archive(self, record_type: str, record_id: str, *, actor_id: str) -> None:
        raise ValueError(f"{record_type} records are archived by their own retention job")

    def record_disposition(self, record_type: str, record_id: str, *, action: str,
                           actor_id: str) -> None:
        with transaction() as conn:
            ensure(conn)
            conn.execute(
                "INSERT INTO data_lifecycle_dispositions (record_type, record_id, action, "
                "actor_id) VALUES (?, ?, ?, ?)", (record_type, record_id, action, actor_id))


def daily_job(actor_id: str = "system:data_lifecycle") -> dict:
    """Dispose of every due record of the enabled types; report the rest."""
    from education_system.systems.university.domains.governance.application.data_lifecycle import (
        LegalHoldActive,
        LifecycleService,
    )

    service = LifecycleService(Repository())
    enabled = settings()
    out: dict = {}
    for record_type in _COLUMNS:
        ids = due(record_type)
        if not enabled.get(record_type):
            out[record_type] = {"due": len(ids), "disposed": 0, "enabled": False}
            continue
        disposed = held = 0
        for record_id in ids:
            try:
                service.dispose(record_type, record_id, actor_id=actor_id)
                disposed += 1
            except LegalHoldActive:
                held += 1
        out[record_type] = {"due": len(ids), "disposed": disposed, "held": held,
                            "enabled": True}
    return out


__all__ = ["Repository", "daily_job", "due", "ensure", "set_enabled", "settings"]
