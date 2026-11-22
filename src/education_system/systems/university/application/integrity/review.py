"""What happens after a similarity check, and the university's one
academic misconduct case record.

* **Review** — a result at or above the module's threshold waits for
  module staff or a reviewer: ``no_concern`` (properly cited, common
  phrasing), ``false_positive`` (the match is wrong, e.g. the student's own
  earlier draft) or ``refer``. Every decision is recorded with a note.
* **Cases** (``integrity_cases``) are opened by a referral, by hand, from an
  AI-detection flag (``integrity_ai``), an exam incident (``exam_office``) or
  a disciplinary record (the disciplinary portal); ``source`` says which.
  A case moves through ``referred → investigating → meeting → decided →
  closed``, each step logged in ``integrity_case_events``. The student has
  until ``response_due`` to give their account (``integrity_evidence``).
* **Outcome** (an integrity officer) comes from :data:`OUTCOMES`. The
  student's earlier upheld cases set the offence number and the
  recommended outcomes (:data:`TARIFF`); going outside them needs a reason.
  A case resting only on an AI-detection score cannot end in a penalty.
* **Penalty** — a mark penalty is recorded on the submission
  (``assignment_submissions.misconduct_penalty``) and the mark changed
  through the module result calculation, so the module result, the
  released gradebook entry and any later re-mark (``assessment_qa``
  ``record_mark`` keeps applying it) all agree. A result an exam board has
  locked cannot be changed: the board must be reopened first.
* **Appeal** — the student can appeal within ``appeal_days`` of the
  decision; an officer who did not make the decision upholds (penalty
  withdrawn, mark restored, case dismissed) or rejects.
* **Holds** — :func:`blocking_cases` lists the cases still undecided (or
  decided with an appeal waiting, or sent to the panel); graduation and
  exam boards will not go ahead while one is open.

Module staff and reviewers see a candidate number in place of the student
while an assignment is marked anonymously (``integrity_access.student_label``).

E-mails are returned as ``(address, subject, body)`` for the caller to
send after commit.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import evidence
from education_system.systems.university.infrastructure.database.schemas.academic_integrity_schema import (  # noqa: E501
    CASE_TYPES,
)

REVIEW_DECISIONS = ("no_concern", "false_positive", "refer")
STAGES = ("referred", "investigating", "meeting", "decided", "closed")
SOURCES = ("similarity", "manual", "ai_detection", "exam_incident", "disciplinary", "legacy")
OUTCOMES = {
    "no_case": ("No case to answer", None),
    "advice": ("Advice on good academic practice", None),
    "warning": ("Formal warning, recorded", None),
    "mark_capped": ("Mark capped at the pass mark", "cap"),
    "mark_zero": ("Mark of zero for this assessment", "zero"),
    "resubmit": ("Resubmission required, mark capped at the pass mark", "resubmit"),
    "panel": ("Referred to the university academic misconduct panel", None),
}
#: Recommended outcomes by offence number (third and later share the last).
TARIFF = {
    1: ("advice", "warning", "mark_capped", "resubmit"),
    2: ("warning", "mark_capped", "mark_zero", "resubmit"),
    3: ("mark_zero", "panel"),
}
UPHELD = ("advice", "warning", "mark_capped", "mark_zero", "resubmit", "panel")
PASS_MARK = 40.0
_STATUS = {"referred": "open", "investigating": "investigating", "meeting": "investigating",
           "decided": "resolved", "closed": "resolved"}


def _student_email(conn, student_id) -> str | None:
    return evidence._student_email(conn, student_id)


def _mail(conn, student_id, subject, body) -> list[tuple]:
    address = _student_email(conn, student_id)
    return [(address, subject, body)] if address else []


def _officers(conn, subject, body) -> list[tuple]:
    return [(address, subject, body) for address in access.officer_emails(conn)]


# ── results ─────────────────────────────────────────────────────────────


def _result(conn, result_id) -> dict:
    access.ensure(conn)
    row = access.one(conn, "SELECT r.*, d.module_code, d.student_id, d.author_id, d.title, "
                           "d.kind, d.academic_year FROM plagiarism_results r JOIN "
                           "document_repository d ON d.id = r.document_id WHERE r.id = ?",
                     (result_id,))
    if not row:
        raise ValueError(f"No result {result_id}")
    return row


def results(conn, who: access.Person, *, review_status=None, module_code=None,
            assignment_id=None, limit=300) -> list[dict]:
    """Results ``who`` may see: students their own released ones, staff
    those on modules they review."""
    access.ensure(conn)
    sql = ("SELECT r.id, r.document_id, d.title, d.student_id, d.module_code, r.assignment_id, "
           "r.similarity_score, r.paraphrase_score, r.obfuscated_chars, r.status, "
           "r.review_status, r.case_id, r.check_date, r.released_to_student "
           "FROM plagiarism_results r JOIN document_repository d ON d.id = r.document_id "
           "WHERE 1 = 1")
    params: list = []
    if who.is_student:
        sql += " AND r.released_to_student = 1 AND (d.student_id = ? OR d.author_id = ?)"
        params += [who.student_id or "", who.user_id or -1]
    else:
        modules = access.taught_modules(conn, who)
        if modules is not None:
            sql += f" AND d.module_code IN ({','.join('?' * len(modules)) or 'NULL'})"
            params += modules
    for column, value in (("r.review_status", review_status), ("d.module_code", module_code),
                          ("r.assignment_id", assignment_id)):
        if value:
            sql += f" AND {column} = ?"
            params.append(value)
    sql += " ORDER BY r.id DESC LIMIT ?"
    params.append(int(limit))
    rows = access.dicts(conn.execute(sql, params))
    if not who.is_student:
        for r in rows:
            r["student_id"] = access.student_label(conn, who, r["student_id"], r["assignment_id"])
    return rows


def _source_label(conn, doc_id) -> str:
    src = access.one(conn, "SELECT kind, title, module_code, academic_year, source_url FROM "
                           "document_repository WHERE id = ?", (doc_id,))
    if not src:
        return "a source that has since been removed"
    if src["kind"] == "reference":
        return f"reference: {src['title']}"
    if src["kind"] == "external":
        return f"published source: {src['title']}" + (f" ({src['source_url']})"
                                                      if src["source_url"] else "")
    return f"another student's submission ({src['module_code'] or 'no module'}, " \
           f"{src['academic_year'] or 'year unknown'})"


def result_detail(conn, who: access.Person, result_id) -> dict:
    """The report. Staff see each source and both sides of every passage;
    the student sees their own text and which kind of source matched."""
    res = _result(conn, result_id)
    own = access.owns(who, res)
    if own and who.is_student:
        access.require(res["released_to_student"], "This report has not been released yet")
    else:
        access.require(access.can_review(conn, who, res["module_code"]) and who.is_staff,
                       "You cannot see this report")
    text = conn.execute("SELECT content FROM document_repository WHERE id = ?",
                        (res["document_id"],)).fetchone()[0]
    matches = []
    for m in access.dicts(conn.execute("SELECT * FROM plagiarism_matches WHERE result_id = ? "
                                       "ORDER BY COALESCE(counted, 1) DESC, score DESC",
                                       (result_id,))):
        passages = json.loads(m["passages"] or "[]")
        item = {"match_id": m["match_id"], "score": m["score"],
                "matched_words": m["matched_words"],
                "match_kind": m.get("match_kind") or "exact",
                "counted": bool(1 if m.get("counted") is None else m["counted"]),
                "source": _source_label(conn, m["matched_document_id"]),
                "passages": [{**p, "text": text[p["start"]:p["end"]]} for p in passages]}
        if who.is_staff:
            src = conn.execute("SELECT content, student_id, assignment_id FROM "
                               "document_repository WHERE id = ?",
                               (m["matched_document_id"],)).fetchone()
            item["source_document_id"] = m["matched_document_id"]
            item["source_student_id"] = (access.student_label(conn, who, src[1], src[2])
                                         if src else None)
            for p in item["passages"]:
                p["source_text"] = (src[0][p["source_start"]:p["source_end"]]
                                    if src and p.get("source_start") is not None else "")
        matches.append(item)
    detail = {**res, "text": text, "matches": matches}
    if who.is_staff:
        detail["student_id"] = access.student_label(conn, who, res["student_id"],
                                                    res["assignment_id"])
        from education_system.systems.university.application.integrity import ai as integrity_ai
        detail["ai_signal"] = integrity_ai.signal_for(conn, res["student_id"],
                                                      res["assignment_id"], res["module_code"])
        access.audit(conn, who.username, "result", result_id, "viewed")
    return detail


# ── review ──────────────────────────────────────────────────────────────


def review(conn, who: access.Person, result_id, decision, note, *,
           case_type="plagiarism") -> dict:
    """Record a review. ``refer`` opens a case. Returns ``{"case_id",
    "emails"}``."""
    res = _result(conn, result_id)
    access.require(who.is_staff and access.can_review(conn, who, res["module_code"]),
                   "Only the module's staff or a reviewer can review this result")
    if decision not in REVIEW_DECISIONS:
        raise ValueError(f"decision must be one of {', '.join(REVIEW_DECISIONS)}")
    if not str(note or "").strip():
        raise ValueError("Give a reason for the decision")
    if res["case_id"]:
        raise ValueError("This result is already part of a case")
    status = {"refer": "referred"}.get(decision, decision)
    conn.execute("UPDATE plagiarism_results SET review_status = ?, reviewed_by = ?, "
                 "reviewed_at = ?, review_note = ?, released_to_student = 1 WHERE id = ?",
                 (status, who.username, access.now(), note.strip(), result_id))
    access.audit(conn, who.username, "result", result_id, "reviewed",
                 {"decision": decision, "note": note.strip()})
    if decision != "refer":
        emails = []
        if not res["released_to_student"]:
            from education_system.systems.university.application.integrity import (
                submission_results,
            )
            emails = submission_results.similarity_review_finished(conn, result_id)
        return {"case_id": None, "emails": emails}
    return open_case(conn, who, student_id=res["student_id"], case_type=case_type,
                     description=note.strip(), result_id=result_id,
                     submission_id=res["submission_id"], assignment_id=res["assignment_id"],
                     module_code=res["module_code"], source="similarity", source_ref=result_id)


# ── cases ───────────────────────────────────────────────────────────────


def _event(conn, case_id, stage, note, actor) -> None:
    conn.execute("INSERT INTO integrity_case_events (case_id, stage, note, actor, at) "
                 "VALUES (?, ?, ?, ?, ?)", (case_id, stage, note, actor, access.now()))


def _module_of_assignment(conn, assignment_id):
    if not assignment_id:
        return None
    row = conn.execute("SELECT module_code FROM assignments WHERE id = ?",
                       (assignment_id,)).fetchone()
    return row[0] if row else None


def open_case(conn, who: access.Person | None, *, student_id, case_type, description,
              result_id=None, submission_id=None, assignment_id=None, module_code=None,
              source="manual", source_ref=None, severity=None, actor=None,
              evidence_items=()) -> dict:
    """Open a case. ``who`` is ``None`` only for a system path (an exam
    incident, a disciplinary escalation), which names itself in ``actor``.
    ``evidence_items`` are ``{"kind", "title", "detail", "ref"}`` dicts added
    as evidence. Returns ``{"case_id", "emails"}``."""
    access.ensure(conn)
    if who is not None:
        access.require(who.is_staff, "Only staff can open an integrity case")
    by = who.username if who is not None else str(actor or "system")
    if not student_id:
        raise ValueError("A case needs a student")
    if case_type not in CASE_TYPES:
        raise ValueError(f"case_type must be one of {', '.join(CASE_TYPES)}")
    if source not in SOURCES:
        raise ValueError(f"source must be one of {', '.join(SOURCES)}")
    if not str(description or "").strip():
        raise ValueError("Describe the concern")
    if submission_id and not assignment_id:
        row = conn.execute("SELECT assignment_id FROM assignment_submissions WHERE id = ?",
                           (submission_id,)).fetchone()
        assignment_id = row[0] if row else None
    module_code = module_code or _module_of_assignment(conn, assignment_id)
    due = evidence.response_due(conn)
    cur = conn.execute(
        "INSERT INTO integrity_cases (student_id, assignment_id, case_type, description, status, "
        "created_by, created_at, updated_at, result_id, submission_id, stage, source, source_ref, "
        "module_code, severity, response_due) "
        "VALUES (?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, 'referred', ?, ?, ?, ?, ?)",
        (str(student_id), assignment_id, case_type, str(description).strip(), by, access.now(),
         access.now(), result_id, submission_id, source,
         None if source_ref is None else str(source_ref), module_code, severity, due))
    case_id = cur.lastrowid
    if result_id:
        conn.execute("UPDATE plagiarism_results SET case_id = ? WHERE id = ?", (case_id, result_id))
        res = access.one(conn, "SELECT similarity_score, paraphrase_score, obfuscated_chars "
                               "FROM plagiarism_results WHERE id = ?", (result_id,))
        if res:
            evidence.add_system_evidence(
                conn, case_id, "similarity_result", f"Similarity report {result_id}",
                f"{float(res['similarity_score'] or 0):.0%} matching text, "
                f"{float(res['paraphrase_score'] or 0):.0%} reworded, "
                f"{res['obfuscated_chars'] or 0} disguised character(s)", result_id, by)
    for item in evidence_items:
        evidence.add_system_evidence(conn, case_id, item["kind"], item["title"],
                                     item.get("detail", ""), item.get("ref"), by)
    _event(conn, case_id, "referred", str(description).strip(), by)
    access.audit(conn, by, "case", case_id, "opened", {"type": case_type, "source": source})
    body = ("A concern about academic integrity has been raised about your work "
            f"(case {case_id}). Nothing has been decided. You can see the concern and the "
            "evidence in the University app (Academic Integrity, My cases), and you can send "
            f"your own account of what happened until {due}. An integrity officer will contact "
            "you, and no decision is made before you have had the chance to respond. Support "
            "is available from the Students' Union advice service.")
    emails = _mail(conn, student_id, f"Academic integrity case {case_id}", body)
    emails += _officers(conn, f"New academic integrity case {case_id}",
                        f"Case {case_id} ({case_type}) was opened by {by} from {source}.")
    return {"case_id": case_id, "emails": emails}


def _may_handle(conn, who, row) -> bool:
    return access.is_officer(conn, who) or (who.is_staff and row["created_by"] == who.username)


def case(conn, who: access.Person, case_id) -> dict:
    access.ensure(conn)
    row = access.one(conn, "SELECT * FROM integrity_cases WHERE id = ?", (case_id,))
    if not row:
        raise ValueError(f"No case {case_id}")
    officer = access.is_officer(conn, who)
    access.require(officer or row["student_id"] == who.student_id
                   or (who.is_staff and row["created_by"] == who.username),
                   "You cannot see this case")
    row["events"] = access.dicts(conn.execute(
        "SELECT * FROM integrity_case_events WHERE case_id = ? ORDER BY event_id", (case_id,)))
    row["appeals"] = access.dicts(conn.execute(
        "SELECT * FROM integrity_appeals WHERE case_id = ? ORDER BY appeal_id", (case_id,)))
    row["statements"] = evidence.statements(conn, who, case_id)
    row["evidence"] = evidence.evidence(conn, who, case_id)
    if officer:
        row["history"] = [c for c in history(conn, who, row["student_id"]) if c["id"] != row["id"]]
        row["recommended"] = recommended(conn, row)
    elif who.is_staff:
        row["student_id"] = access.student_label(conn, who, row["student_id"],
                                                 row["assignment_id"])
    return row


def cases(conn, who: access.Person, *, stage=None) -> list[dict]:
    access.ensure(conn)
    sql = "SELECT * FROM integrity_cases WHERE 1 = 1"
    params: list = []
    officer = access.is_officer(conn, who)
    if who.is_student:
        sql += " AND student_id = ?"
        params.append(who.student_id or "")
    elif not officer:
        sql += " AND created_by = ?"
        params.append(who.username)
    if stage:
        sql += " AND stage = ?"
        params.append(stage)
    rows = access.dicts(conn.execute(sql + " ORDER BY id DESC", params))
    if who.is_staff and not officer:
        for r in rows:
            r["student_id"] = access.student_label(conn, who, r["student_id"], r["assignment_id"])
    return rows


def advance(conn, who: access.Person, case_id, stage, note) -> list[tuple]:
    """Move a case to ``investigating`` or ``meeting``."""
    access.require(access.is_officer(conn, who), "Only an integrity officer can progress a case")
    row = case(conn, who, case_id)
    if stage not in ("investigating", "meeting"):
        raise ValueError("Use decide() for an outcome")
    if STAGES.index(stage) <= STAGES.index(row["stage"] or "referred"):
        raise ValueError(f"The case is already at {row['stage']}")
    conn.execute("UPDATE integrity_cases SET stage = ?, status = ?, updated_at = ? WHERE id = ?",
                 (stage, _STATUS[stage], access.now(), case_id))
    _event(conn, case_id, stage, note, who.username)
    access.audit(conn, who.username, "case", case_id, stage)
    if stage == "meeting":
        return _mail(conn, row["student_id"], f"Academic integrity case {case_id}: meeting",
                     f"You are invited to a meeting about case {case_id}. {note} You may bring "
                     "a friend or Students' Union adviser.")
    return []


# ── previous cases and the tariff ───────────────────────────────────────


def history(conn, who: access.Person, student_id) -> list[dict]:
    """Every case about ``student_id``, oldest first (integrity officers)."""
    access.require(access.is_officer(conn, who), "Only an integrity officer can see this")
    access.ensure(conn)
    rows = access.dicts(conn.execute(
        "SELECT id, case_type, stage, status, outcome, penalty, module_code, source, "
        "created_at, decided_at, offence_number FROM integrity_cases WHERE student_id = ? "
        "ORDER BY created_at, id", (str(student_id),)))
    for r in rows:
        r["upheld"] = r["outcome"] in UPHELD and r["status"] != "dismissed"
    return rows


def offence_number(conn, row) -> int:
    """1 + the student's earlier upheld cases (decided before this one)."""
    earlier = conn.execute(
        "SELECT COUNT(*) FROM integrity_cases WHERE student_id = ? AND id <> ? AND "
        f"outcome IN ({','.join('?' * len(UPHELD))}) AND status <> 'dismissed' AND "
        "stage IN ('decided', 'closed')",
        (row["student_id"], row["id"], *UPHELD)).fetchone()[0]
    return int(earlier) + 1


def recommended(conn, row) -> dict:
    number = offence_number(conn, row)
    return {"offence_number": number, "outcomes": list(TARIFF[min(number, max(TARIFF))])}


# ── marks ───────────────────────────────────────────────────────────────


def _submission(conn, submission_id) -> dict | None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(assignments)")}
    resit = "a.reassessment_of" if "reassessment_of" in cols else "NULL"
    return access.one(conn, f"SELECT s.id, s.grade, s.student_id, s.status, "  # nosec B608
                            f"s.grade_released_at, a.module_code, a.title, {resit} AS resit_of "
                            "FROM assignment_submissions s JOIN assignments a ON "
                            "a.id = s.assignment_id WHERE s.id = ?", (submission_id,))


def _result_module(conn, sub) -> str:
    if sub.get("resit_of"):
        row = conn.execute("SELECT module_code FROM assignments WHERE id = ?",
                           (sub["resit_of"],)).fetchone()
        if row and row[0]:
            return row[0]
    return sub["module_code"]


def _require_unlocked(conn, sub) -> None:
    from education_system.systems.university.application.assessment import module_results
    module = _result_module(conn, sub)
    if module_results.is_locked(conn, sub["student_id"], module):
        raise ValueError(f"The exam board has confirmed and locked {module} for this student. "
                         "The board must be reopened before the mark can be changed.")


def _refresh_marks(conn, sub, new_grade) -> None:
    """Recalculate the module result and, where the mark was released, the
    gradebook entry — inside the caller's transaction."""
    from education_system.systems.university.application.assessment import module_results
    module_results.recompute(conn, str(sub["student_id"]), _result_module(conn, sub))
    if new_grade is None or not sub.get("grade_released_at"):
        return
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'student_grades'").fetchone():
        conn.execute("UPDATE student_grades SET grade = ?, grade_value = ?, percentage = ?, "
                     "updated_at = ? WHERE student_id = ? AND module_code = ? AND "
                     "assessment_name = ?",
                     (f"{new_grade}/100", str(new_grade), new_grade, access.now(),
                      str(sub["student_id"]), sub["module_code"], sub["title"]))


def _apply_penalty(conn, row, kind) -> float | None:
    """Record ``kind`` on the submission and change the mark. Returns the
    mark before."""
    if not kind or not row["submission_id"]:
        return None
    sub = _submission(conn, row["submission_id"])
    if not sub:
        return None
    _require_unlocked(conn, sub)
    grade = sub["grade"]
    if kind == "zero":
        new = 0.0
    elif grade is None:
        new = None          # not marked yet: record_mark applies the penalty when it is
    else:
        new = min(float(grade), PASS_MARK)
    conn.execute("UPDATE assignment_submissions SET misconduct_penalty = ?, "
                 "misconduct_case_id = ?, grade = COALESCE(?, grade), status = CASE WHEN ? = "
                 "'resubmit' THEN 'resubmission_required' ELSE status END WHERE id = ?",
                 (kind, row["id"], new, kind, row["submission_id"]))
    _refresh_marks(conn, sub, new)
    return grade


def _withdraw_penalty(conn, row) -> None:
    sub = _submission(conn, row["submission_id"])
    if not sub:
        return
    _require_unlocked(conn, sub)
    conn.execute("UPDATE assignment_submissions SET grade = ?, misconduct_penalty = NULL, "
                 "misconduct_case_id = NULL, status = CASE WHEN status = "
                 "'resubmission_required' THEN 'submitted' ELSE status END WHERE id = ?",
                 (row["grade_before"], row["submission_id"]))
    _refresh_marks(conn, sub, row["grade_before"])


# ── decisions ───────────────────────────────────────────────────────────


def decide(conn, who: access.Person, case_id, outcome, note, *,
           departure_reason=None) -> list[tuple]:
    access.require(access.is_officer(conn, who), "Only an integrity officer can decide a case")
    row = case(conn, who, case_id)
    if outcome not in OUTCOMES:
        raise ValueError(f"outcome must be one of {', '.join(OUTCOMES)}")
    if row["stage"] in ("decided", "closed"):
        raise ValueError("This case has already been decided")
    if not str(note or "").strip():
        raise ValueError("Give the reasons for the decision")
    label, penalty = OUTCOMES[outcome]
    if outcome != "no_case":
        if (row["response_due"] and access.now()[:10] <= row["response_due"]
                and not evidence.has_statement(conn, case_id)):
            raise ValueError(f"The student has until {row['response_due']} to give their "
                             "account. Wait for it, or change the deadline with a reason "
                             "(for example when they say they will not respond).")
        kinds = evidence.kinds_in_case(conn, case_id)
        if penalty and (row["case_type"] == "ai_misuse" or row["source"] == "ai_detection") \
                and not (kinds - {"ai_result"}) and not evidence.has_statement(conn, case_id):
            raise ValueError("An AI-detection score on its own is not enough evidence for a "
                             "penalty. Add what else the decision rests on (a meeting record, "
                             "drafts, version history) first.")
    tariff = recommended(conn, row)
    departure = None
    if outcome not in ("no_case", "panel") and outcome not in tariff["outcomes"]:
        departure = str(departure_reason or "").strip()
        if len(departure) < 10:
            raise ValueError(f"For offence {tariff['offence_number']} the recommended outcomes "
                             f"are {', '.join(tariff['outcomes'])}. Give the reason for "
                             "departing from them.")
    before = _apply_penalty(conn, row, penalty)
    days = int(access.number(conn, "appeal_days"))
    deadline = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    conn.execute("UPDATE integrity_cases SET stage = 'decided', status = ?, outcome = ?, "
                 "penalty = ?, decided_by = ?, decided_at = ?, resolved_at = ?, grade_before = ?, "
                 "appeal_deadline = ?, offence_number = ?, tariff = ?, tariff_departure = ?, "
                 "updated_at = ? WHERE id = ?",
                 ("dismissed" if outcome == "no_case" else "resolved", outcome, label,
                  who.username, access.now(), access.now(), before, deadline,
                  tariff["offence_number"] if outcome in UPHELD else None,
                  json.dumps(tariff["outcomes"]), departure, access.now(), case_id))
    _event(conn, case_id, "decided", f"{label}. {note.strip()}"
           + (f" (Outside the recommended outcomes: {departure})" if departure else ""),
           who.username)
    access.audit(conn, who.username, "case", case_id, "decided",
                 {"outcome": outcome, "grade_before": before,
                  "offence_number": tariff["offence_number"], "departure": departure})
    _sync_source(conn, row, "decided", label)
    return _mail(conn, row["student_id"], f"Academic integrity case {case_id}: decision",
                 f"The decision on case {case_id} is: {label}.\n\nReasons: {note.strip()}\n\n"
                 f"You can appeal in the University app until {deadline}.")


def _sync_source(conn, row, stage, label) -> None:
    """Keep a disciplinary record that was escalated into this case in step."""
    if row.get("source") != "disciplinary" or not row.get("source_ref"):
        return
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'disciplinary_records'"
                        ).fetchone():
        return
    status = "Resolved" if stage in ("decided", "closed") else "Escalated"
    conn.execute("UPDATE disciplinary_records SET status = ? WHERE record_id = ?",
                 (status, row["source_ref"]))


def close(conn, who: access.Person | None, case_id, note="", *, actor=None) -> None:
    """Close a decided case. ``who`` is ``None`` only for the automatic
    close once the appeal period has passed."""
    if who is not None:
        access.require(access.is_officer(conn, who), "Only an integrity officer can close a case")
        row = case(conn, who, case_id)
    else:
        row = access.one(conn, "SELECT * FROM integrity_cases WHERE id = ?", (case_id,))
        if not row:
            raise ValueError(f"No case {case_id}")
        row["appeals"] = access.dicts(conn.execute(
            "SELECT * FROM integrity_appeals WHERE case_id = ?", (case_id,)))
    if row["stage"] != "decided":
        raise ValueError("Only a decided case can be closed")
    if any(a["status"] == "lodged" for a in row["appeals"]):
        raise ValueError("An appeal is waiting for a decision")
    by = who.username if who is not None else str(actor or "automatic")
    conn.execute("UPDATE integrity_cases SET stage = 'closed', closed_at = ?, updated_at = ? "
                 "WHERE id = ?", (access.now(), access.now(), case_id))
    _event(conn, case_id, "closed", note, by)
    access.audit(conn, by, "case", case_id, "closed")
    _sync_source(conn, row, "closed", row.get("penalty"))


def blocking_cases(conn, student_id, module_code=None) -> list[dict]:
    """Cases that must be settled before ``student_id``'s results are
    confirmed or award conferred: not yet decided, decided with an appeal
    waiting, or sent to the panel and not closed. With ``module_code``,
    only cases on that module or on no particular module. No person check:
    for graduation and exam boards."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'integrity_cases'").fetchone():
        return []
    access.ensure(conn)
    sql = ("SELECT c.id, c.case_type, c.stage, c.module_code, c.outcome FROM integrity_cases c "
           "WHERE c.student_id = ? AND (c.stage IN ('referred', 'investigating', 'meeting') OR "
           "(c.stage = 'decided' AND (c.outcome = 'panel' OR EXISTS (SELECT 1 FROM "
           "integrity_appeals a WHERE a.case_id = c.id AND a.status = 'lodged'))))")
    params: list = [str(student_id)]
    if module_code:
        sql += " AND (c.module_code IS NULL OR c.module_code = ?)"
        params.append(module_code)
    return access.dicts(conn.execute(sql + " ORDER BY c.id", params))


# ── appeals ─────────────────────────────────────────────────────────────


def lodge_appeal(conn, who: access.Person, case_id, grounds) -> list[tuple]:
    row = case(conn, who, case_id)
    access.require(who.is_student and row["student_id"] == who.student_id,
                   "Only the student can appeal their case")
    if row["stage"] != "decided":
        raise ValueError("Only a decided case can be appealed")
    if row["appeal_deadline"] and access.now()[:10] > row["appeal_deadline"]:
        raise ValueError(f"The appeal deadline ({row['appeal_deadline']}) has passed")
    if any(a["status"] == "lodged" for a in row["appeals"]):
        raise ValueError("You already have an appeal waiting")
    if len(str(grounds or "").strip()) < 20:
        raise ValueError("Explain your grounds for appeal")
    conn.execute("INSERT INTO integrity_appeals (case_id, grounds, lodged_by, lodged_at) "
                 "VALUES (?, ?, ?, ?)", (case_id, grounds.strip(), who.username, access.now()))
    _event(conn, case_id, "decided", "Appeal lodged", who.username)
    access.audit(conn, who.username, "case", case_id, "appeal lodged")
    return (_mail(conn, row["student_id"], f"Appeal received: case {case_id}",
                  "Your appeal has been received and will be considered by an officer who was "
                  "not involved in the original decision.")
            + _officers(conn, f"Appeal lodged: case {case_id}",
                        f"The student has appealed the decision on case {case_id}. It must be "
                        f"decided by someone other than {row['decided_by']}."))


def decide_appeal(conn, who: access.Person, appeal_id, upheld, note) -> list[tuple]:
    access.require(access.is_officer(conn, who), "Only an integrity officer can decide appeals")
    appeal = access.one(conn, "SELECT * FROM integrity_appeals WHERE appeal_id = ?", (appeal_id,))
    if not appeal or appeal["status"] != "lodged":
        raise ValueError("No appeal waiting with that number")
    row = case(conn, who, appeal["case_id"])
    if row["decided_by"] == who.username:
        raise PermissionError("An appeal must be decided by someone other than the original "
                              "decision-maker")
    if not str(note or "").strip():
        raise ValueError("Give the reasons for the appeal decision")
    if upheld and row["submission_id"] and OUTCOMES.get(row["outcome"], (0, None))[1]:
        _withdraw_penalty(conn, row)
    conn.execute("UPDATE integrity_appeals SET status = ?, decided_by = ?, decided_at = ?, "
                 "decision_note = ? WHERE appeal_id = ?",
                 ("upheld" if upheld else "rejected", who.username, access.now(), note.strip(),
                  appeal_id))
    if upheld:
        conn.execute("UPDATE integrity_cases SET status = 'dismissed', outcome = 'no_case', "
                     "penalty = 'Withdrawn on appeal', offence_number = NULL, updated_at = ? "
                     "WHERE id = ?", (access.now(), row["id"]))
    _event(conn, row["id"], "decided", f"Appeal {'upheld' if upheld else 'rejected'}: {note}",
           who.username)
    access.audit(conn, who.username, "appeal", appeal_id, "upheld" if upheld else "rejected")
    return _mail(conn, row["student_id"], f"Appeal decision: case {row['id']}",
                 f"Your appeal has been {'upheld' if upheld else 'rejected'}.\n\n{note.strip()}")


# ── statistics ──────────────────────────────────────────────────────────


def statistics(conn, who: access.Person) -> dict:
    access.require(who.is_staff, "Statistics are for staff")
    rows = results(conn, who, limit=100000)
    waiting = sum(1 for r in rows if r["review_status"] == "pending")
    from education_system.systems.university.application.integrity import plagiarism_checks
    return {
        "checks": len(rows),
        "waiting_review": waiting,
        "referred": sum(1 for r in rows if r["review_status"] == "referred"),
        "by_status": {s: sum(1 for r in rows if r["status"] == s)
                      for s in ("HIGH", "MODERATE", "LOW", "NO_MATCH")},
        "reworded": sum(1 for r in rows if (r["paraphrase_score"] or 0)
                        >= access.number(conn, "paraphrase_threshold")),
        "disguised": sum(1 for r in rows if (r["obfuscated_chars"] or 0)
                         >= access.number(conn, "obfuscation_chars")),
        "failed_checks": len(plagiarism_checks.failures(conn, who)),
        "open_cases": sum(1 for c in cases(conn, who) if c["stage"] not in ("decided", "closed")),
    }
