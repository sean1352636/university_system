"""AI-writing indicators in academic integrity.

Readings come from :mod:`ai_indicators` (stock phrasing, leftover chat text,
unusually even sentences and paragraphs, formulaic openings — indicators,
never proof). They are kept in the detector tables
``ai_detector_submissions`` / ``ai_detector_results`` with the real ids:
``student_id`` is the student number, ``course_code`` the module code,
``assignment_id`` the assignment id and ``assignment_submission_id`` the
submission.

* :func:`check_submission` — the automatic reading after a student submits
  (``integrity/submission_hook``), when ``ai_auto_check`` is on and the
  module has not turned it off. Code and short texts get no reading.
* :func:`run_check` — a member of staff reads a piece of work on a module
  they teach (a submission, or text they paste for a named student).
* :func:`flags` / :func:`review_flag` — readings at or above
  ``ai_review_threshold`` wait for module staff: ``no_concern`` (with a
  reason) or ``refer``, which opens an ``ai_misuse`` case with the reading
  as evidence. A case resting only on a reading cannot end in a penalty
  (``integrity_review.decide``).
* :func:`results` / :func:`result_detail` — staff see readings on modules
  they review; a student sees their own once it is released (below the
  threshold straight away; above it once reviewed, when
  ``release_after_review`` is on) and can comment on it
  (:func:`comment`), which module staff see.
* :func:`signal_for` — the latest reading for a student's work on an
  assignment, shown beside the similarity report.
"""

from __future__ import annotations

import json

from education_system.systems.university.application.integrity import ai_indicators
from education_system.systems.university.application.integrity import access

DECISIONS = ("no_concern", "refer")
NOTICE = ("These are indicators, not evidence: no tool can tell reliably whether a person or a "
          "model wrote a text, and the student's account matters more than any reading.")


def _has_detector(conn) -> bool:
    return conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name IN "
                        "('ai_detector_results', 'ai_detector_submissions')").fetchone()[0] == 2


def _title(conn) -> str:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ai_detector_submissions)")}
    return "COALESCE(s.title, s.submission_title)" if "submission_title" in cols else "s.title"


def _assignment_id(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


# ── taking a reading ────────────────────────────────────────────────────


def _store(conn, *, student_id, module_code, assignment_id, submission_id, title, text,
           file_type, checked_by) -> int:
    """Take the reading through the AI detector's analysis
    (``shared/ai/ai_detector/detector/reading``) and store it; a
    reading at the review level also lands in the detector's alert queue."""
    from education_system.systems.university.shared.ai.ai_detector.detector import (
        reading as detector_reading,
    )
    found = detector_reading.analyse(conn, text, file_type)
    return detector_reading.store(conn, found, text=text, student_id=student_id,
                                  module_code=module_code, assignment_id=assignment_id,
                                  submission_id=submission_id, title=title,
                                  file_type=file_type, checked_by=checked_by)


def check_submission(conn, submission_id, text, file_type="txt") -> int | None:
    """The automatic reading after a student submits (system path).
    ``None`` when AI readings are off for the module."""
    access.ensure(conn)
    sub = access.one(conn, "SELECT s.id, s.student_id, s.assignment_id, s.file_name, "
                           "a.module_code, a.title FROM assignment_submissions s JOIN assignments "
                           "a ON a.id = s.assignment_id WHERE s.id = ?", (submission_id,))
    if not sub or not access.ai_checks_enabled(conn, sub["module_code"]):
        return None
    result_id = _store(conn, student_id=sub["student_id"], module_code=sub["module_code"],
                       assignment_id=sub["assignment_id"], submission_id=submission_id,
                       title=f"{sub['title']} — {sub['file_name'] or 'submission'}", text=text,
                       file_type=file_type, checked_by="automatic")
    access.audit(conn, "automatic", "ai_result", result_id, "read", {"submission": submission_id})
    return result_id


def run_check(conn, who: access.Person, *, text, module_code, student_id=None,
              assignment_id=None, submission_id=None, title="", file_type="txt") -> int:
    """A reading taken by staff. With ``submission_id`` the student, module
    and assignment come from the submission."""
    access.ensure(conn)
    if submission_id:
        sub = access.one(conn, "SELECT s.student_id, s.assignment_id, a.module_code, a.title "
                               "FROM assignment_submissions s JOIN assignments a ON "
                               "a.id = s.assignment_id WHERE s.id = ?", (submission_id,))
        if not sub:
            raise ValueError(f"No submission {submission_id}")
        student_id, assignment_id = sub["student_id"], sub["assignment_id"]
        module_code, title = sub["module_code"], title or sub["title"]
    access.require(who.is_staff and access.can_review(conn, who, module_code),
                   "Only the module's staff can take a reading on this module's work")
    if not student_id:
        raise ValueError("Choose the student")
    if not conn.execute("SELECT 1 FROM students WHERE student_id = ?",
                        (str(student_id),)).fetchone():
        raise ValueError(f"No student {student_id}")
    if not conn.execute("SELECT 1 FROM modules WHERE module_code = ?",
                        (module_code,)).fetchone():
        raise ValueError(f"No module {module_code}")
    if not str(text or "").strip():
        raise ValueError("There is no text to read")
    result_id = _store(conn, student_id=student_id, module_code=module_code,
                       assignment_id=assignment_id, submission_id=submission_id,
                       title=title or "Text checked by staff", text=str(text),
                       file_type=file_type, checked_by=who.username)
    access.audit(conn, who.username, "ai_result", result_id, "read",
                 {"student": student_id, "module": module_code})
    return result_id


# ── who sees what ───────────────────────────────────────────────────────


_SELECT = ("SELECT r.id, r.ai_score, r.level, r.method, r.created_at, s.student_id, "
           "s.course_code, s.assignment_id, s.assignment_submission_id, s.checked_by, "
           "s.word_count, {title} AS title, v.decision, v.note, v.reviewed_by, v.reviewed_at, "
           "v.case_id FROM ai_detector_results r JOIN ai_detector_submissions s ON "
           "s.id = r.submission_id LEFT JOIN integrity_ai_reviews v ON v.ai_result_id = r.id")


def released(conn, row) -> bool:
    """May the student see this reading yet?"""
    if row["decision"]:
        return True
    if access.setting(conn, "release_after_review") != "1":
        return True
    return float(row["ai_score"] or 0) < access.number(conn, "ai_review_threshold")


def _scoped(conn, who, sql, params, limit):
    if who.is_student:
        sql += " AND s.student_id = ?"
        params.append(who.student_id or "")
    else:
        access.require(who.is_staff, "AI-writing readings are for staff and the student")
        modules = access.taught_modules(conn, who)
        if modules is not None:
            sql += f" AND s.course_code IN ({','.join('?' * len(modules)) or 'NULL'})"
            params += modules
    rows = access.dicts(conn.execute(sql + " ORDER BY r.id DESC LIMIT ?", params + [int(limit)]))
    if who.is_student:
        return [r for r in rows if released(conn, r)]
    for r in rows:
        r["student_id"] = access.student_label(conn, who, r["student_id"],
                                               _assignment_id(r["assignment_id"]))
    return rows


def results(conn, who: access.Person, *, module_code=None, limit=300) -> list[dict]:
    access.ensure(conn)
    if not _has_detector(conn):
        return []
    sql, params = _SELECT.format(title=_title(conn)) + " WHERE 1 = 1", []
    if module_code:
        sql += " AND s.course_code = ?"
        params.append(module_code)
    return _scoped(conn, who, sql, params, limit)


def flags(conn, who: access.Person, *, include_reviewed=False, limit=300) -> list[dict]:
    """Readings at or above ``ai_review_threshold`` on modules ``who`` reviews."""
    access.require(who.is_staff, "AI-writing flags are for staff")
    access.ensure(conn)
    if not _has_detector(conn):
        return []
    sql = _SELECT.format(title=_title(conn)) + " WHERE r.ai_score >= ?"
    params: list = [access.number(conn, "ai_review_threshold")]
    if not include_reviewed:
        sql += " AND v.ai_result_id IS NULL"
    return _scoped(conn, who, sql, params, limit)


def latest_for_submission(conn, submission_id) -> dict | None:
    """The newest reading on a submission, with its detail; None if there is none."""
    access.ensure(conn)
    if not _has_detector(conn):
        return None
    row = conn.execute("SELECT r.id FROM ai_detector_results r JOIN ai_detector_submissions s "
                       "ON s.id = r.submission_id WHERE s.assignment_submission_id = ? "
                       "ORDER BY r.id DESC LIMIT 1", (submission_id,)).fetchone()
    return _row(conn, row[0]) if row else None


def _row(conn, ai_result_id) -> dict:
    access.ensure(conn)
    if not _has_detector(conn):
        raise ValueError("There are no AI-writing readings")
    row = access.one(conn, _SELECT.format(title=_title(conn)).replace(
        "SELECT r.id,", "SELECT r.detailed_results, s.submission_text, s.purged, r.id,") +
        " WHERE r.id = ?", (ai_result_id,))
    if not row:
        raise ValueError(f"No AI-writing reading {ai_result_id}")
    return row


def result_detail(conn, who: access.Person, ai_result_id) -> dict:
    """One reading with its indicators and the passages behind them. The
    student sees their own once released."""
    row = _row(conn, ai_result_id)
    if who.is_student:
        access.require(row["student_id"] == who.student_id, "You cannot see this reading")
        access.require(released(conn, row), "This reading has not been released yet")
    else:
        access.require(who.is_staff and access.can_review(conn, who, row["course_code"]),
                       "You cannot see this reading")
        row["student_id"] = access.student_label(conn, who, row["student_id"],
                                                 _assignment_id(row["assignment_id"]))
        access.audit(conn, who.username, "ai_result", ai_result_id, "viewed")
    try:
        reading = json.loads(row.pop("detailed_results") or "{}")
    except ValueError:
        reading = {}
    if "indicators" not in reading:      # a score from the retired detector
        reading = {"method": "retired detector", "indicators": [], "passages": [],
                   "level": "no indicators recorded",
                   "note": "Taken by the retired AI detector, whose score was not reliable."}
    text = row.pop("submission_text") or ""
    reading["passages"] = [{**p, "text": text[p["start"]:p["end"]]}
                           for p in reading.get("passages", [])]
    row["comments"] = access.dicts(conn.execute(
        "SELECT * FROM ai_result_comments WHERE ai_result_id = ? ORDER BY comment_id",
        (ai_result_id,)))
    for key, value in reading.items():
        if row.get(key) is None:
            row[key] = value
    return {**row, "text": text, "notice": NOTICE}


def comment(conn, who: access.Person, ai_result_id, text) -> list[tuple]:
    """The student's comment on their own reading (or staff's reply).
    Returns e-mails for the module's staff when the student comments."""
    row = _row(conn, ai_result_id)
    if who.is_student:
        access.require(row["student_id"] == who.student_id and released(conn, row),
                       "You cannot comment on this reading")
    else:
        access.require(who.is_staff and access.can_review(conn, who, row["course_code"]),
                       "You cannot comment on this reading")
    text = str(text or "").strip()
    if len(text) < 10:
        raise ValueError("Write your comment (at least a few words)")
    conn.execute("INSERT INTO ai_result_comments (ai_result_id, author, comment, at) VALUES "
                 "(?, ?, ?, ?)", (ai_result_id, who.username, text, access.now()))
    access.audit(conn, who.username, "ai_result", ai_result_id, "commented")
    if not who.is_student:
        return []
    return [(address, f"{row['course_code']}: comment on an AI-writing reading",
             f"A student has commented on AI-writing reading {ai_result_id}. It is in the "
             "Academic Integrity window (AI writing).")
            for address in access.module_staff_emails(conn, row["course_code"])]


# ── review ──────────────────────────────────────────────────────────────


def review_flag(conn, who: access.Person, ai_result_id, decision, note, *,
                case_type="ai_misuse") -> dict:
    """Record a review of one reading. ``refer`` opens a case. Returns
    ``{"case_id", "emails"}``."""
    flag = _row(conn, ai_result_id)
    access.require(who.is_staff and access.can_review(conn, who, flag["course_code"]),
                   "Only the module's staff or a reviewer can review this reading")
    if decision not in DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(DECISIONS)}")
    if not str(note or "").strip():
        raise ValueError("Give a reason for the decision")
    if flag["decision"]:
        raise ValueError("This reading has already been reviewed")
    out = {"case_id": None, "emails": []}
    if decision == "refer":
        from education_system.systems.university.application.integrity import (
            review as integrity_review,
        )
        try:
            reading = json.loads(flag["detailed_results"] or "{}")
        except ValueError:
            reading = {}
        shown = "; ".join(f"{i['label']}: {i['shown']}" for i in reading.get("indicators", []))
        out = integrity_review.open_case(
            conn, who, student_id=flag["student_id"], case_type=case_type,
            description=note.strip(), assignment_id=_assignment_id(flag["assignment_id"]),
            submission_id=flag["assignment_submission_id"], module_code=flag["course_code"],
            source="ai_detection", source_ref=ai_result_id,
            evidence_items=[{"kind": "ai_result", "ref": ai_result_id,
                             "title": f"AI-writing reading {ai_result_id}",
                             "detail": f"{flag['level'] or 'reading'} ({shown or 'no detail'}), "
                                       f"{flag['created_at']}. {NOTICE}"}])
    conn.execute("INSERT INTO integrity_ai_reviews (ai_result_id, decision, note, reviewed_by, "
                 "reviewed_at, case_id) VALUES (?, ?, ?, ?, ?, ?)",
                 (ai_result_id, decision, note.strip(), who.username, access.now(),
                  out["case_id"]))
    access.audit(conn, who.username, "ai_result", ai_result_id, "reviewed",
                 {"decision": decision, "case": out["case_id"]})
    if decision != "refer":
        from education_system.systems.university.application.integrity import submission_results
        if not released(conn, flag):
            out["emails"] = submission_results.reading_review_finished(conn, flag)
    return out


def signal_for(conn, student_id, assignment_id, module_code=None) -> dict | None:
    """The latest reading for this student's work on the assignment (or the
    module, when no assignment was recorded)."""
    if not student_id or not _has_detector(conn):
        return None
    row = None
    if assignment_id:
        row = access.one(conn, "SELECT r.id, r.ai_score, r.level, r.created_at FROM "
                               "ai_detector_results r JOIN ai_detector_submissions s ON "
                               "s.id = r.submission_id WHERE s.student_id = ? AND "
                               "s.assignment_id = ? ORDER BY r.id DESC LIMIT 1",
                         (str(student_id), str(assignment_id)))
    if row is None and module_code:
        row = access.one(conn, "SELECT r.id, r.ai_score, r.level, r.created_at FROM "
                               "ai_detector_results r JOIN ai_detector_submissions s ON "
                               "s.id = r.submission_id WHERE s.student_id = ? AND "
                               "s.course_code = ? AND COALESCE(s.assignment_id, '') = '' "
                               "ORDER BY r.id DESC LIMIT 1", (str(student_id), module_code))
    return row


def statistics(conn, who: access.Person) -> dict:
    rows = results(conn, who, limit=100000)
    threshold = access.number(conn, "ai_review_threshold")
    return {"readings": len(rows),
            "flagged": sum(1 for r in rows if float(r["ai_score"] or 0) >= threshold),
            "waiting_review": sum(1 for r in rows if float(r["ai_score"] or 0) >= threshold
                                  and not r["decision"]),
            "referred": sum(1 for r in rows if r["decision"] == "refer"),
            "not_enough_text": sum(1 for r in rows if (r["level"] or "").startswith("not "))}


def purge(conn, cutoff) -> int:
    """Remove the text of readings older than ``cutoff`` (retention), except
    where the reading is evidence in a case that is not closed."""
    if not _has_detector(conn):
        return 0
    access.ensure(conn)
    cur = conn.execute(
        "UPDATE ai_detector_submissions AS s SET submission_text = '', purged = 1 WHERE "
        "COALESCE(purged, 0) = 0 AND submission_date < ? AND NOT EXISTS (SELECT 1 FROM "
        "ai_detector_results r JOIN integrity_ai_reviews v ON v.ai_result_id = r.id JOIN "
        "integrity_cases c ON c.id = v.case_id WHERE r.submission_id = s.id AND "
        "COALESCE(c.stage, 'referred') <> 'closed')", (cutoff,))
    if "text_content" in {r[1] for r in conn.execute("PRAGMA table_info(ai_detector_submissions)")}:
        conn.execute("UPDATE ai_detector_submissions SET text_content = NULL WHERE purged = 1")
    return cur.rowcount


def erase(conn, student_id) -> dict:
    """Remove ``student_id``'s readings, except any that are case evidence
    (system path; the caller has checked who may erase)."""
    if not _has_detector(conn):
        return {"removed": 0, "kept_as_evidence": []}
    access.ensure(conn)
    kept, removed = [], 0
    for sub_id, result_id, case_id in conn.execute(
            "SELECT s.id, r.id, v.case_id FROM ai_detector_submissions s LEFT JOIN "
            "ai_detector_results r ON r.submission_id = s.id LEFT JOIN integrity_ai_reviews v "
            "ON v.ai_result_id = r.id WHERE s.student_id = ?", (str(student_id),)).fetchall():
        if case_id:
            kept.append(result_id)
            continue
        if result_id:
            conn.execute("DELETE FROM ai_result_comments WHERE ai_result_id = ?", (result_id,))
            conn.execute("DELETE FROM integrity_ai_reviews WHERE ai_result_id = ?", (result_id,))
            for table in ("ai_detector_metadata", "advanced_detection_results",
                          "ai_analysis_history"):
                cols = {r[1] for r in conn.execute(f'PRAGMA table_info("{table}")')}
                if "submission_id" in cols:
                    conn.execute(f'DELETE FROM "{table}" WHERE submission_id = ?', (sub_id,))  # nosec B608
            conn.execute("DELETE FROM ai_detector_results WHERE id = ?", (result_id,))
        if not conn.execute("SELECT 1 FROM ai_detector_results WHERE submission_id = ?",
                            (sub_id,)).fetchone():
            conn.execute("DELETE FROM ai_detector_submissions WHERE id = ?", (sub_id,))
            removed += 1
    return {"removed": removed, "kept_as_evidence": kept}


def export(conn, student_id) -> list[dict]:
    """The student's readings for a subject access export."""
    if not _has_detector(conn):
        return []
    access.ensure(conn)
    rows = access.dicts(conn.execute(
        "SELECT r.id, r.ai_score, r.level, r.method, r.created_at, r.detailed_results, "
        "s.course_code, s.assignment_id, s.title, s.checked_by FROM ai_detector_results r JOIN "
        "ai_detector_submissions s ON s.id = r.submission_id WHERE s.student_id = ?",
        (str(student_id),)))
    for r in rows:
        r["comments"] = access.dicts(conn.execute(
            "SELECT author, comment, at FROM ai_result_comments WHERE ai_result_id = ?",
            (r["id"],)))
    return rows
