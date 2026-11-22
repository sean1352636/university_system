"""The student's side of a case and the evidence in it.

* **Statements** — when a case is opened the student has ``statement_days``
  (``integrity_cases.response_due``) to give their account. They can send
  more than one statement until the case is decided. An outcome other than
  "no case to answer" cannot be decided before the deadline unless the
  student has responded; an officer can move the deadline, with a reason.
* **Evidence** — what the decision rests on: the similarity report, an
  AI-detection result, an exam incident, a disciplinary record (all added
  automatically by whatever opened the case), and files, notes and meeting
  records added by an officer or the member of staff who raised the case.
  The student sees every item unless an officer marks it internal (e.g. a
  third party's personal data), with the reason recorded. Files are copied
  in with their SHA-256 (``infrastructure/integrity/evidence_store``).
  Evidence is withdrawn, never deleted, while the case is open.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from education_system.systems.university.application.integrity import access

EVIDENCE_KINDS = ("file", "note", "meeting_record", "similarity_result", "ai_result",
                  "exam_incident", "disciplinary_record", "legacy")
STAFF_KINDS = ("file", "note", "meeting_record")
OPEN_STAGES = ("referred", "investigating", "meeting")


def _case(conn, case_id) -> dict:
    access.ensure(conn)
    row = access.one(conn, "SELECT * FROM integrity_cases WHERE id = ?", (case_id,))
    if not row:
        raise ValueError(f"No case {case_id}")
    return row


def _may_handle(conn, who: access.Person, case) -> bool:
    return access.is_officer(conn, who) or (who.is_staff and case["created_by"] == who.username)


def _may_see(conn, who: access.Person, case) -> bool:
    return _may_handle(conn, who, case) or (who.student_id and case["student_id"] == who.student_id)


def response_due(conn, at=None) -> str:
    days = int(access.number(conn, "statement_days"))
    return ((at or datetime.now()) + timedelta(days=days)).strftime("%Y-%m-%d")


# ── statements ──────────────────────────────────────────────────────────


def submit_statement(conn, who: access.Person, case_id, text) -> list[tuple]:
    """The student's account. Returns e-mails for the integrity officers."""
    case = _case(conn, case_id)
    access.require(who.is_student and case["student_id"] == who.student_id,
                   "Only the student the case is about can send a statement")
    if (case["stage"] or "referred") not in OPEN_STAGES:
        raise ValueError("This case has been decided; you can appeal instead")
    text = str(text or "").strip()
    if len(text) < 20:
        raise ValueError("Write your statement (at least a sentence)")
    conn.execute("INSERT INTO integrity_statements (case_id, author, statement, submitted_at) "
                 "VALUES (?, ?, ?, ?)", (case_id, who.username, text, access.now()))
    conn.execute("INSERT INTO integrity_case_events (case_id, stage, note, actor, at) VALUES "
                 "(?, ?, 'Statement received from the student', ?, ?)",
                 (case_id, case["stage"] or "referred", who.username, access.now()))
    access.audit(conn, who.username, "case", case_id, "statement submitted")
    return [(address, f"Academic integrity case {case_id}: statement received",
             f"The student has sent a statement for case {case_id}. It is in the case record.")
            for address in access.officer_emails(conn)]


def statements(conn, who: access.Person, case_id) -> list[dict]:
    case = _case(conn, case_id)
    access.require(_may_see(conn, who, case), "You cannot see this case")
    return access.dicts(conn.execute("SELECT * FROM integrity_statements WHERE case_id = ? "
                                     "ORDER BY statement_id", (case_id,)))


def has_statement(conn, case_id) -> bool:
    return conn.execute("SELECT 1 FROM integrity_statements WHERE case_id = ?",
                        (case_id,)).fetchone() is not None


def set_response_due(conn, who: access.Person, case_id, date, reason) -> list[tuple]:
    """Move the statement deadline (an extension, or earlier when the
    student says they will not respond). Returns the student's e-mail."""
    access.require(access.is_officer(conn, who), "Only an integrity officer can change this")
    case = _case(conn, case_id)
    if (case["stage"] or "referred") not in OPEN_STAGES:
        raise ValueError("This case has been decided")
    try:
        day = datetime.strptime(str(date).strip(), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        raise ValueError("Give the date as YYYY-MM-DD") from None
    if not str(reason or "").strip():
        raise ValueError("Give the reason for the change")
    conn.execute("UPDATE integrity_cases SET response_due = ?, updated_at = ? WHERE id = ?",
                 (day, access.now(), case_id))
    conn.execute("INSERT INTO integrity_case_events (case_id, stage, note, actor, at) VALUES "
                 "(?, ?, ?, ?, ?)", (case_id, case["stage"] or "referred",
                                     f"Statement deadline now {day}: {reason.strip()}",
                                     who.username, access.now()))
    access.audit(conn, who.username, "case", case_id, "response deadline changed",
                 {"date": day, "reason": reason.strip()})
    address = _student_email(conn, case["student_id"])
    return [(address, f"Academic integrity case {case_id}: your deadline",
             f"The deadline for your statement on case {case_id} is now {day}. {reason.strip()}")
            ] if address else []


def _student_email(conn, student_id):
    for sql, params in (("SELECT email_address FROM students WHERE student_id = ?",
                         (student_id,)),
                        ("SELECT email FROM users WHERE student_id = ? OR username = ?",
                         (student_id, student_id))):
        try:
            row = conn.execute(sql, params).fetchone()
        except Exception:
            continue
        if row and row[0]:
            return row[0]
    return None


# ── evidence ────────────────────────────────────────────────────────────


def add_system_evidence(conn, case_id, kind, title, detail="", ref=None, actor="automatic",
                        visible=True) -> int:
    """Evidence added by whatever opened the case (no person check)."""
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f"kind must be one of {', '.join(EVIDENCE_KINDS)}")
    cur = conn.execute("INSERT INTO integrity_evidence (case_id, kind, title, detail, ref, "
                       "visible_to_student, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (case_id, kind, str(title)[:200], detail, None if ref is None else str(ref),
                        1 if visible else 0, actor, access.now()))
    return cur.lastrowid


def add_evidence(conn, who: access.Person, case_id, *, kind, title, detail="", file_path=None,
                 visible_to_student=True, internal_reason="") -> int:
    """A file, note or meeting record added by an officer or by the member
    of staff who raised the case. An internal item needs a reason."""
    case = _case(conn, case_id)
    access.require(_may_handle(conn, who, case),
                   "Only an integrity officer or the person who raised the case can add evidence")
    if case["stage"] == "closed":
        raise ValueError("This case is closed")
    if kind not in STAFF_KINDS:
        raise ValueError(f"kind must be one of {', '.join(STAFF_KINDS)}")
    if not str(title or "").strip():
        raise ValueError("Give the evidence a title")
    if kind == "file" and not file_path:
        raise ValueError("Choose the file")
    if kind != "file" and not str(detail or "").strip():
        raise ValueError("Write the note or the meeting record")
    if not visible_to_student:
        access.require(access.is_officer(conn, who),
                       "Only an integrity officer can keep evidence from the student")
        if not str(internal_reason or "").strip():
            raise ValueError("Say why the student cannot see this item")
    stored = name = digest = None
    if file_path:
        from education_system.systems.university.infrastructure.integrity import evidence_store
        stored, name, digest = evidence_store.store(case_id, file_path)
    note = str(detail or "").strip()
    if not visible_to_student:
        note = f"{note}\n[Internal: {internal_reason.strip()}]".strip()
    cur = conn.execute(
        "INSERT INTO integrity_evidence (case_id, kind, title, detail, file_name, file_path, "
        "sha256, visible_to_student, added_by, added_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (case_id, kind, title.strip(), note, name, stored, digest, 1 if visible_to_student else 0,
         who.username, access.now()))
    conn.execute("INSERT INTO integrity_case_events (case_id, stage, note, actor, at) VALUES "
                 "(?, ?, ?, ?, ?)", (case_id, case["stage"] or "referred",
                                     f"Evidence added: {title.strip()}", who.username,
                                     access.now()))
    access.audit(conn, who.username, "evidence", cur.lastrowid, "added",
                 {"case": case_id, "kind": kind, "visible": bool(visible_to_student),
                  "sha256": digest})
    return cur.lastrowid


def evidence(conn, who: access.Person, case_id) -> list[dict]:
    """The case's evidence: everything for staff who handle it, the items
    the student may see for the student. Withdrawn items are listed as such."""
    case = _case(conn, case_id)
    access.require(_may_see(conn, who, case), "You cannot see this case")
    rows = access.dicts(conn.execute("SELECT * FROM integrity_evidence WHERE case_id = ? "
                                     "ORDER BY evidence_id", (case_id,)))
    if not _may_handle(conn, who, case):
        rows = [r for r in rows if r["visible_to_student"]]
        for r in rows:
            r.pop("file_path", None)
    return rows


def evidence_file(conn, who: access.Person, evidence_id) -> dict:
    """The stored file of one item, after the access check, with whether it
    still matches the hash taken when it was attached."""
    item = access.one(conn, "SELECT * FROM integrity_evidence WHERE evidence_id = ?",
                      (evidence_id,))
    if not item or not item["file_path"] or item["removed_at"]:
        raise ValueError("No file for that evidence item")
    case = _case(conn, item["case_id"])
    allowed = _may_handle(conn, who, case) or (
        item["visible_to_student"] and who.student_id and case["student_id"] == who.student_id)
    access.require(allowed, "You cannot open this evidence")
    from education_system.systems.university.infrastructure.integrity import evidence_store
    access.audit(conn, who.username, "evidence", evidence_id, "opened")
    return {"path": item["file_path"], "name": item["file_name"],
            "intact": evidence_store.verify(item["file_path"], item["sha256"])}


def withdraw_evidence(conn, who: access.Person, evidence_id, reason) -> None:
    """Take an item out of consideration (it stays on the record)."""
    access.require(access.is_officer(conn, who), "Only an integrity officer can withdraw evidence")
    item = access.one(conn, "SELECT * FROM integrity_evidence WHERE evidence_id = ?",
                      (evidence_id,))
    if not item or item["removed_at"]:
        raise ValueError("No evidence item with that number")
    if not str(reason or "").strip():
        raise ValueError("Give the reason")
    conn.execute("UPDATE integrity_evidence SET removed_at = ?, detail = COALESCE(detail, '') || "
                 "? WHERE evidence_id = ?",
                 (access.now(), f"\n[Withdrawn by {who.username}: {reason.strip()}]", evidence_id))
    access.audit(conn, who.username, "evidence", evidence_id, "withdrawn",
                 {"reason": reason.strip()})


def kinds_in_case(conn, case_id) -> set[str]:
    return {r[0] for r in conn.execute("SELECT kind FROM integrity_evidence WHERE case_id = ? "
                                       "AND removed_at IS NULL", (case_id,))}
