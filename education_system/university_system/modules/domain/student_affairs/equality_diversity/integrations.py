"""Integrations with the rest of the university system (features 29–36).

- Mirror every write to the main ``audit_log`` table (31)
- Look up student/staff by ref_code and back-link (10, 29, 35, 36)
- Monitoring completeness against the live ``students`` roster (30)
- GDPR subject-access-request (SAR) export (32)
- Right-to-erasure — hard-delete everything linked to a person (33)
- Safeguarding handoff — push serious incidents to safeguarding_referrals (34)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from education_system.university_system.modules.domain.student_affairs.equality_diversity.schema import (
    get_connection,
)


# --------------------------------------------------------------- feature 31 ---
def audit(actor: str, action: str, entity: str, entity_id: Any = None,
          details: Any = None) -> None:
    """Append an event to both the E&D audit log and the system-wide one.

    Failures against the main ``audit_log`` are swallowed so schema drift
    there never blocks E&D operations.
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    details_json = json.dumps(details, default=str) if details is not None else None
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO ed_audit_log (ts, actor, action, entity, entity_id, details) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, actor, action, entity,
             str(entity_id) if entity_id is not None else None, details_json),
        )
        try:
            conn.execute(
                "INSERT INTO audit_log (user_id, action, table_name, record_id, "
                "new_values, timestamp, details) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (None, action, f"ed_{entity}",
                 entity_id if isinstance(entity_id, int) else None,
                 details_json, ts, f"{actor}: {action}"),
            )
        except sqlite3.Error:
            pass
        conn.commit()
    finally:
        conn.close()


# --------------------------------------------------------------- feature 10/29
def link_person_by_ref(ref_code: str) -> dict | None:
    """Best-effort link of a ref_code to an existing student or staff row."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT student_id, first_name, last_name, email_address "
            "FROM students WHERE student_id=? OR email_address=?",
            (ref_code, ref_code),
        ).fetchone()
        if row:
            return {"kind": "student", "student_id": row[0],
                    "name": f"{row[1]} {row[2]}", "email": row[3]}
        row = conn.execute(
            "SELECT id, name, email FROM staff WHERE username=? OR email=?",
            (ref_code, ref_code),
        ).fetchone()
        if row:
            return {"kind": "staff", "staff_id": row[0],
                    "name": row[1], "email": row[2]}
    except sqlite3.Error:
        return None
    finally:
        conn.close()
    return None


def sync_link(person_id: int, ref_code: str) -> dict | None:
    """Populate ``student_id`` / ``staff_id`` on an ed_people row if matchable."""
    hit = link_person_by_ref(ref_code)
    if not hit:
        return None
    conn = get_connection()
    try:
        if hit["kind"] == "student":
            conn.execute(
                "UPDATE ed_people SET student_id=? WHERE id=?",
                (hit["student_id"], person_id),
            )
        else:
            conn.execute(
                "UPDATE ed_people SET staff_id=? WHERE id=?",
                (hit["staff_id"], person_id),
            )
        conn.commit()
    finally:
        conn.close()
    return hit


# ---------------------------------------------------------------- feature 30
def monitoring_completeness() -> dict:
    """Return rough completeness stats vs the live student roster."""
    conn = get_connection()
    try:
        total_students = conn.execute(
            "SELECT COUNT(*) FROM students WHERE COALESCE(status,'active')='active'"
        ).fetchone()[0] or 0
        monitored = conn.execute(
            "SELECT COUNT(DISTINCT ref_code) FROM ed_people "
            "WHERE person_type='Student' AND deleted_at IS NULL"
        ).fetchone()[0] or 0
        per_field = {}
        fields = ("gender", "ethnicity", "age_group", "disability",
                  "religion", "sexual_orientation", "nationality")
        for f in fields:
            filled = conn.execute(
                f"SELECT COUNT(*) FROM ed_people "
                f"WHERE deleted_at IS NULL AND {f} IS NOT NULL AND {f}!='' "
                f"AND {f}!='Prefer not to say'"
            ).fetchone()[0] or 0
            total = conn.execute(
                "SELECT COUNT(*) FROM ed_people WHERE deleted_at IS NULL"
            ).fetchone()[0] or 0
            per_field[f] = (filled, total)
    finally:
        conn.close()
    coverage = (monitored / total_students * 100) if total_students else 0.0
    return {
        "student_roster": total_students,
        "students_monitored": monitored,
        "coverage_pct": coverage,
        "per_field": per_field,
    }


# --------------------------------------------------------------- feature 32
def sar_export(ref_code: str) -> dict:
    """Collect everything we hold about one ref_code (GDPR SAR)."""
    conn = get_connection()
    try:
        person = conn.execute(
            "SELECT * FROM ed_people WHERE ref_code=?", (ref_code,)
        ).fetchone()
        if not person:
            return {"ref_code": ref_code, "found": False}
        cols = [d[0] for d in conn.execute("PRAGMA table_info(ed_people)")]
        # PRAGMA returns (cid, name, type, notnull, dflt, pk) — use column name
        cols = [r[1] for r in conn.execute("PRAGMA table_info(ed_people)")]
        record = dict(zip(cols, person))
        pid = record["id"]
        incidents = [dict(zip(
            [c[1] for c in conn.execute("PRAGMA table_info(ed_incidents)")],
            row,
        )) for row in conn.execute(
            "SELECT * FROM ed_incidents WHERE reported_by=? OR respondent=?",
            (ref_code, ref_code),
        )]
        views = conn.execute(
            "SELECT viewer, viewed_at FROM ed_view_log WHERE entity='person' "
            "AND entity_id=? ORDER BY viewed_at",
            (pid,),
        ).fetchall()
        consent = conn.execute(
            "SELECT consent_flags, updated_at FROM ed_consent WHERE person_id=?",
            (pid,),
        ).fetchone()
    finally:
        conn.close()
    return {
        "ref_code": ref_code,
        "found": True,
        "record": record,
        "incidents": incidents,
        "view_log": [{"viewer": v[0], "viewed_at": v[1]} for v in views],
        "consent": {"flags": consent[0], "updated_at": consent[1]} if consent else None,
    }


# ---------------------------------------------------------------- feature 33
def erase_person(ref_code: str, actor: str) -> int:
    """Hard-delete a person and every linked row. Returns total rows removed."""
    conn = get_connection()
    total = 0
    try:
        row = conn.execute(
            "SELECT id FROM ed_people WHERE ref_code=?", (ref_code,)
        ).fetchone()
        if not row:
            return 0
        pid = row[0]
        for sql, params in [
            ("DELETE FROM ed_view_log WHERE entity='person' AND entity_id=?", (pid,)),
            ("DELETE FROM ed_consent WHERE person_id=?", (pid,)),
            ("UPDATE ed_incidents SET reported_by='[erased]' WHERE reported_by=?", (ref_code,)),
            ("UPDATE ed_incidents SET respondent='[erased]' WHERE respondent=?", (ref_code,)),
            ("DELETE FROM ed_people WHERE id=?", (pid,)),
        ]:
            cur = conn.execute(sql, params)
            total += cur.rowcount or 0
        conn.commit()
    finally:
        conn.close()
    audit(actor, "erase", "person", ref_code, {"rows_affected": total})
    return total


# ---------------------------------------------------------------- feature 34
def refer_to_safeguarding(incident_id: int, actor: str, reason: str) -> bool:
    """Push an incident to the safeguarding module if it exists."""
    conn = get_connection()
    try:
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS safeguarding_referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT, source_id INTEGER,
                    referred_by TEXT, referred_at TEXT,
                    reason TEXT, status TEXT DEFAULT 'open'
                )
            """)
            conn.execute(
                "INSERT INTO safeguarding_referrals (source, source_id, referred_by, "
                "referred_at, reason) VALUES ('ed_incident', ?, ?, ?, ?)",
                (incident_id, actor,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S"), reason),
            )
            conn.execute(
                "UPDATE ed_incidents SET referred_to='safeguarding', referred_at=? "
                "WHERE id=?",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), incident_id),
            )
            conn.commit()
            ok = True
        except sqlite3.Error:
            ok = False
    finally:
        conn.close()
    if ok:
        audit(actor, "refer", "incident", incident_id, {"to": "safeguarding", "reason": reason})
    return ok


# ---------------------------------------------------------------- feature 35
def staff_roster_for_monitoring() -> list[tuple]:
    conn = get_connection()
    try:
        return conn.execute(
            "SELECT id, username, name, email, role FROM staff "
            "WHERE COALESCE(status,'active')='active'"
        ).fetchall()
    finally:
        conn.close()


# ---------------------------------------------------------------- feature 36
def applicant_monitoring_seed() -> int:
    """Create ed_people rows for any applicant who isn't yet tracked."""
    conn = get_connection()
    created = 0
    try:
        try:
            candidates = conn.execute(
                "SELECT student_id, gender FROM students "
                "WHERE status IN ('applicant','applied') LIMIT 500"
            ).fetchall()
        except sqlite3.Error:
            return 0
        for sid, gender in candidates:
            existing = conn.execute(
                "SELECT 1 FROM ed_people WHERE ref_code=?", (sid,)
            ).fetchone()
            if existing:
                continue
            conn.execute(
                "INSERT INTO ed_people (ref_code, person_type, gender, date_added) "
                "VALUES (?, 'Student', ?, ?)",
                (sid, gender or "Prefer not to say",
                 datetime.now().strftime("%Y-%m-%d %H:%M")),
            )
            created += 1
        conn.commit()
    finally:
        conn.close()
    return created
