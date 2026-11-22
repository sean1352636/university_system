"""A student's medical history, read from the tables that hold it.

There is no ``medical_history`` table in the university database: the CLI
screens, exports and reports that queried one failed (or created an empty
one keyed on ``users.id``). The history is

* diagnoses — ``medical_conditions`` (condition, severity, status,
  diagnosed date, provider, notes), and
* encounters — ``health_records`` (record type, date, provider and the
  description, sealed when confidential),

newest first, in one shape: ``date``, ``diagnosis``, ``treatment``,
``provider``, ``notes``, ``severity``, ``status``, ``source``
(``condition`` / ``record``), ``id``, ``student_id``.

Callers do the access check and the audit entry (``access``); these
functions only read and write.
"""

from __future__ import annotations

from datetime import datetime

from education_system.systems.university.domains.health.application.health import (
    access,
    sealed_fields,
)


def _has(conn, table) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                             (table,)).fetchone())


def history(conn, student_id=None, *, since=None, limit=None) -> list[dict]:
    """The history of one student (or everyone, for reports), newest first."""
    rows: list[dict] = []
    if _has(conn, "medical_conditions"):
        sql = ("SELECT id, student_id, condition_name, icd_code, severity, diagnosed_date, "
               "status, provider, notes, created_at FROM medical_conditions WHERE 1 = 1")
        args: list = []
        if student_id is not None:
            sql += " AND student_id = ?"
            args.append(str(student_id))
        for r in conn.execute(sql, args).fetchall():
            (rid, sid, name, icd, severity, diagnosed, status, provider, notes, created) = tuple(r)
            rows.append({"source": "condition", "id": rid, "student_id": sid,
                         "date": str(diagnosed or created or "")[:10],
                         "diagnosis": name + (f" ({icd})" if icd else "") if name else icd,
                         "treatment": None, "provider": provider,
                         "notes": sealed_fields.reveal(notes), "severity": severity,
                         "status": status})
    if _has(conn, "health_records"):
        # health_records.medications is the retired profile copy (never
        # filled); a visit has no treatment column of its own.
        sql = ("SELECT id, student_id, record_type, record_date, description, provider, "
               "created_at FROM health_records WHERE 1 = 1")
        args = []
        if student_id is not None:
            sql += " AND student_id = ?"
            args.append(str(student_id))
        for r in conn.execute(sql, args).fetchall():
            rid, sid, kind, when, description, provider, created = tuple(r)
            rows.append({"source": "record", "id": rid, "student_id": sid,
                         "date": str(when or created or "")[:10], "diagnosis": kind,
                         "treatment": None, "provider": provider,
                         "notes": sealed_fields.reveal(description), "severity": None,
                         "status": None})
    if since:
        rows = [r for r in rows if r["date"] and r["date"] >= str(since)[:10]]
    rows.sort(key=lambda r: r["date"] or "", reverse=True)
    return rows[:limit] if limit else rows


def count_since(conn, since) -> int:
    return len(history(conn, since=since))


def diagnosis_counts(conn, limit=10) -> list[tuple[str, int]]:
    """Most common diagnoses (conditions) across all students."""
    if not _has(conn, "medical_conditions"):
        return []
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT condition_name, COUNT(*) FROM medical_conditions "
        "WHERE COALESCE(condition_name, '') <> '' GROUP BY condition_name "
        "ORDER BY COUNT(*) DESC, condition_name LIMIT ?", (int(limit),))]


def add_condition(conn, who, student_id, condition_name, *, diagnosed_date=None,
                  severity=None, status="active", provider=None, notes=None,
                  icd_code=None) -> int:
    """Record a diagnosis (health team only); the caller commits."""
    access.require_clinician(who, "add to a student's medical history")
    condition_name = str(condition_name or "").strip()
    if not condition_name:
        raise ValueError("Condition name is required")
    if diagnosed_date:
        datetime.strptime(str(diagnosed_date), "%Y-%m-%d")
    if not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                        (str(student_id),)).fetchone():
        raise ValueError(f"No student {student_id}")
    cur = conn.execute(
        "INSERT INTO medical_conditions (student_id, condition_name, icd_code, severity, "
        "diagnosed_date, status, provider, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(student_id), condition_name, icd_code or None, severity or None,
         diagnosed_date or None, status or "active", provider or None, notes or None,
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    from education_system.systems.university.domains.health.domain.health.services.audit import (
        log_audit_event,
    )
    log_audit_event(who.username, "add_medical_condition", "medical_conditions", cur.lastrowid,
                    details={"student_id": str(student_id)}, conn=conn)
    return cur.lastrowid


def __getattr__(name):
    # The CLI screen used to be re-exported from here; kept for its callers
    # without importing the CLI at import time.
    if name == "view_medical_history":
        from education_system.systems.university.domains.health.interfaces.cli.health_portal.medical_history import (
            view_medical_history,
        )
        return view_medical_history
    raise AttributeError(name)


__all__ = ["history", "count_since", "diagnosis_counts", "add_condition",
           "view_medical_history"]
