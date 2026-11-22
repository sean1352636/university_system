"""Erasing a student's personal data on request (right to erasure), under
dual control.

1. **Request** - a member of staff records the case reference and reason
   for a student who is no longer studying (withdrawn, completed or
   closed). The impact (rows per table) is captured.
2. **Approve / reject** - a different person, who has just re-entered their
   password, decides. Legal holds block approval.
3. **Execute** - someone runs the approved request. Legal holds are checked
   again, then in one transaction:

   * the student row is renamed to an anonymous id (``ERASED-...``) and
     its personal columns are blanked;
   * academic, finance and lifecycle rows (``KEEP``) are moved to the
     anonymous id, so results, statistics and the accounts still add up;
   * every other row about the student - health, visa, contacts, emails,
     letters, profiles and so on - is deleted, and other references to the
     student are cleared (health rows keyed on the login or e-mail - dental
     patients, first-aid reporters, consent flags - by
     ``domains/health/application/health/erasure``);
   * their university login rows go, and (by the caller, after commit) the
     shared sign-in is erased.

   Transcripts can no longer be produced for an erased student.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import json
import secrets

ELIGIBLE = ("Withdrawn", "Completed", "Closed")
#: Tables kept (under the anonymous id) for results, statistics and audit.
KEEP = ("student_modules", "module_grades", "grades", "student_grades", "attendance_records",
        "attendance", "assessment_results", "exam_results", "programme_registrations",
        "module_enrolments", "student_lifecycle_history", "student_lifecycle_actions",
        "payments", "transactions", "student_fees",
        "student_finance_accounts", "student_finance_transactions", "unified_refunds",
        "evaluation_responses")
#: Columns blanked on the student row (those that exist).
PERSONAL = ("title", "first_name", "middle_name", "last_name", "gender", "dob", "age",
            "pronouns", "phone", "address", "personal_email", "nationality",
            "emergency_contact", "parent_email", "parent_phone", "previous_system_id",
            "journey_id", "entry_qualifications", "registration_datetime")
_CLOSED = ("closed", "resolved", "dismissed", "completed", "withdrawn", "no case")
_STUDENT_COLUMNS = ("student_id", "learner_id", "student_ref")


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _has(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
                        (table,)).fetchone()


def _ensure(conn):
    from education_system.systems.university.application.students import (
        record_rules as student_record_rules,
    )
    student_record_rules.ensure(conn)


# ── what refers to a student ────────────────────────────────────────────


def references(conn) -> list[tuple[str, str]]:
    """``(table, column)`` for every column that holds a student id: columns
    named like one, and foreign keys to ``students``."""
    out = set()
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND "
                                 "name NOT LIKE 'sqlite_%' AND name <> 'students'").fetchall():
        for col in conn.execute(f'PRAGMA table_info("{table}")').fetchall():
            if col[1] in _STUDENT_COLUMNS:
                out.add((table, col[1]))
        for fk in conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
            if fk[2] == "students":
                out.add((table, fk[3]))
    return sorted(out)


def impact(conn, student_id) -> dict[str, dict]:
    """Rows per table that would be kept (anonymised) or removed."""
    out = {}
    for table, column in references(conn):
        n = conn.execute(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = ?',
                         (student_id,)).fetchone()[0]
        if n:
            fate = "kept, anonymised" if table in KEEP and column == "student_id" else (
                "removed" if column in _STUDENT_COLUMNS else "reference cleared")
            out[f"{table}.{column}"] = {"rows": n, "fate": fate}
    # Health rows keyed on the login or e-mail rather than the student id.
    from education_system.systems.university.domains.health.application.health import (
        erasure as health_erasure,
    )
    out.update(health_erasure.impact(conn, health_erasure.identities(conn, student_id)))
    return out


def _open_rows(conn, table, sql, args):
    if not _has(conn, table):
        return 0
    try:
        return conn.execute(sql, args).fetchone()[0]
    except Exception:
        return 0


def legal_holds(conn, student_id) -> list[str]:
    """Reasons the record must be kept for now."""
    closed = ", ".join(f"'{c}'" for c in _CLOSED)
    checks = (
        ("university_legal_holds", "SELECT COUNT(*) FROM university_legal_holds WHERE "
         "record_type = 'student' AND record_id = ? AND released_at IS NULL",
         "a legal hold is in place"),
        ("finance_holds", "SELECT COUNT(*) FROM finance_holds WHERE student_id = ? AND "
         "is_active = 1", "an active finance hold"),
        ("student_finance_accounts", "SELECT COUNT(*) FROM student_finance_accounts WHERE "
         "student_id = ? AND COALESCE(balance, 0) > 0", "money is still owed"),
        ("collection_cases", "SELECT COUNT(*) FROM collection_cases WHERE student_id = ? AND "
         f"LOWER(COALESCE(case_status, 'open')) NOT IN ({closed})", "an open debt collection case"),
        ("ftp_cases", "SELECT COUNT(*) FROM ftp_cases WHERE student_id = ? AND date_closed IS "
         "NULL", "an open fitness-to-practise case"),
        ("integrity_cases", "SELECT COUNT(*) FROM integrity_cases WHERE student_id = ? AND "
         "COALESCE(stage, 'referred') <> 'closed'", "an academic integrity case not yet closed"),
    )
    return [why for table, sql, why in checks if _open_rows(conn, table, sql, (student_id,))]


# ── the workflow ────────────────────────────────────────────────────────


def request(conn, student_id, case_reference, reason, actor) -> int:
    _ensure(conn)
    if not (case_reference or "").strip() or not (reason or "").strip():
        raise ValueError("A case reference and a reason are required")
    row = conn.execute("SELECT status FROM students WHERE student_id = ?",
                       (student_id,)).fetchone()
    if not row:
        raise ValueError("No such student")
    if row[0] not in ELIGIBLE:
        raise ValueError(f"Withdraw the student first (status is {row[0]})")
    if conn.execute("SELECT 1 FROM student_erasure_requests WHERE student_id = ? AND status "
                    "IN ('requested', 'approved')", (student_id,)).fetchone():
        raise ValueError("An erasure request for this student is already open")
    return int(conn.execute(
        "INSERT INTO student_erasure_requests (student_id, case_reference, reason, "
        "requested_by, impact_json) VALUES (?, ?, ?, ?, ?)",
        (student_id, case_reference.strip(), reason.strip(), actor,
         json.dumps(impact(conn, student_id)))).lastrowid)


def requests(conn, status=None) -> list[dict]:
    _ensure(conn)
    sql = "SELECT * FROM student_erasure_requests"
    args: tuple = ()
    if status:
        sql += " WHERE status = ?"
        args = (status,)
    rows = _dicts(conn.execute(sql + " ORDER BY request_id DESC", args))
    for r in rows:
        r["impact"] = json.loads(r.pop("impact_json") or "{}")
    return rows


def _get(conn, request_id):
    _ensure(conn)
    rows = _dicts(conn.execute("SELECT * FROM student_erasure_requests WHERE request_id = ?",
                               (request_id,)))
    if not rows:
        raise ValueError("No such erasure request")
    return rows[0]


def decide(conn, request_id, approve: bool, actor, *, reauthenticated: bool, note=""):
    """Approve or reject. The decider must not be the requester and must have
    just re-entered their password; holds block approval."""
    r = _get(conn, request_id)
    if r["status"] != "requested":
        raise ValueError(f"This request is already {r['status']}")
    if not reauthenticated:
        raise ValueError("Re-enter your password to decide an erasure request")
    if actor == r["requested_by"]:
        raise ValueError("Someone other than the requester must decide")
    holds = legal_holds(conn, r["student_id"]) if approve else []
    if holds:
        raise ValueError("Cannot approve: " + "; ".join(holds))
    conn.execute("UPDATE student_erasure_requests SET status = ?, decided_by = ?, decided_at = "
                 "datetime('now'), decision_note = ? WHERE request_id = ?",
                 ("approved" if approve else "rejected", actor, note or None, request_id))


def _children(conn, parent):
    """``(child table, child column, parent column)`` for foreign keys to
    ``parent`` whose delete action leaves the child row behind (NO ACTION /
    RESTRICT) — those rows must go first or the commit fails."""
    out = []
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND "
                                 "name NOT LIKE 'sqlite_%'").fetchall():
        for fk in conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
            # (id, seq, table, from, to, on_update, on_delete, match)
            if fk[2] == parent and str(fk[6]).upper() in ("NO ACTION", "RESTRICT") \
                    and table != parent:
                out.append((table, fk[3], fk[4] or "rowid"))
    return out


def _delete_rows(conn, table, where, args, depth=0):
    """Delete ``table`` rows matching ``where``, their dependent rows first
    (e.g. an AI-writing reading's result rows before the reading)."""
    if depth < 4:
        for child, column, parent_column in _children(conn, table):
            _delete_rows(conn, child,
                         f'"{column}" IN (SELECT "{parent_column}" FROM "{table}" '
                         f"WHERE {where})", args, depth + 1)
    conn.execute(f'DELETE FROM "{table}" WHERE {where}', args)  # nosec B608 - names from schema


def _delete_or_clear(conn, table, column, student_id):
    if column in _STUDENT_COLUMNS:
        _delete_rows(conn, table, f'"{column}" = ?', (student_id,))
        return
    try:
        conn.execute(f'UPDATE "{table}" SET "{column}" = NULL WHERE "{column}" = ?',
                     (student_id,))
    except Exception:
        conn.execute(f'DELETE FROM "{table}" WHERE "{column}" = ?', (student_id,))


def _anonymise_student(conn, student_id, anon):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(students)")}
    blank = [c for c in PERSONAL if c in cols]
    sets = ", ".join(f'"{c}" = NULL' for c in blank)
    extra = ", status = 'Closed'" + (", is_active = 0" if "is_active" in cols else "")
    conn.execute(f"UPDATE students SET {sets}{', ' if sets else ''}student_id = ?, "
                 f"email_address = ?{extra} WHERE student_id = ?",
                 (anon, f"{anon.lower()}@erased.invalid", student_id))
    if "first_name" in cols:
        conn.execute("UPDATE students SET first_name = 'Erased', last_name = 'record' WHERE "
                     "student_id = ?", (anon,))


def _user_references(conn) -> list[tuple[str, str]]:
    """``(table, column)`` for every foreign key to ``users``, plus the
    message columns that hold a user id without one."""
    out = {("messages", "recipient_id"), ("messages", "sender_id"), ("user_accounts", "user_id")}
    for (table,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND "
                                 "name NOT LIKE 'sqlite_%'").fetchall():
        for fk in conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
            if fk[2] == "users":
                out.add((table, fk[3]))
    return sorted(t for t in out if _has(conn, t[0]))


def _remove_logins(conn, student_id):
    """Delete the student's university login and everything pointing at it
    (messages, chat memberships, ...)."""
    if not _has(conn, "users"):
        return
    refs = _user_references(conn)
    for (user_id,) in conn.execute("SELECT id FROM users WHERE student_id = ? OR username = ?",
                                   (student_id, student_id)).fetchall():
        for table, column in refs:
            try:
                _delete_rows(conn, table, f'"{column}" = ?', (user_id,))
            except Exception:
                continue  # column absent in this database
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def execute(conn, request_id, actor) -> dict:
    """Carry out an approved request. Returns the anonymous id and the
    student id whose shared sign-in the caller should then erase
    (``student_provisioning.erase_student_login``)."""
    r = _get(conn, request_id)
    if r["status"] != "approved":
        raise ValueError("Only an approved request can be carried out")
    student_id = r["student_id"]
    holds = legal_holds(conn, student_id)
    if holds:
        raise ValueError("A legal hold has appeared since approval: " + "; ".join(holds))
    anon = f"ERASED-{secrets.token_hex(4).upper()}"
    # Open the transaction first: deferring foreign keys lasts only until
    # the next commit, and the re-keying below is consistent only at the end.
    conn.execute("UPDATE student_erasure_requests SET completed_by = ? WHERE request_id = ?",
                 (actor, request_id))
    conn.execute("PRAGMA defer_foreign_keys = ON")
    # Health rows keyed on the login (dental patients, first-aid reporters,
    # consent flags): read who the student is before the logins go.
    from education_system.systems.university.domains.health.application.health import (
        erasure as health_erasure,
    )
    health_who = health_erasure.identities(conn, student_id)
    health_erasure.erase(conn, health_who, _delete_rows)
    _remove_logins(conn, student_id)
    # AI-writing readings: their comments and reviews hold no foreign key, so
    # the generic pass below would leave them behind.
    from education_system.systems.university.application.integrity import ai as integrity_ai
    integrity_ai.erase(conn, student_id)
    # Closed integrity cases go with the generic pass; their events,
    # statements, evidence (and files) and appeals have no foreign key.
    from education_system.systems.university.application.integrity import (
        records as integrity_records,
    )
    integrity_records.erase_closed_cases(conn, student_id)
    for table, column in references(conn):
        if table in KEEP and column == "student_id":
            conn.execute(f'UPDATE "{table}" SET student_id = ? WHERE student_id = ?',
                         (anon, student_id))
        elif table != "student_erasure_requests":
            _delete_or_clear(conn, table, column, student_id)
    if _has(conn, "university_event_outbox"):
        # Event payloads (e.g. provisioning) carry the name and email.
        conn.execute("DELETE FROM university_event_outbox WHERE aggregate_id = ?", (student_id,))
    _anonymise_student(conn, student_id, anon)
    conn.execute("UPDATE student_erasure_requests SET student_id = ?, status = 'completed', "
                 "completed_by = ?, completed_at = datetime('now') WHERE request_id = ?",
                 (anon, actor, request_id))
    return {"anonymous_id": anon, "login": student_id}
