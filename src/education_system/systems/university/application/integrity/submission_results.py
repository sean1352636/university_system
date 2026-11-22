"""E-mailing a student the results of the checks on their submission.

The checks themselves run in ``integrity/submission_hook``. Staff review comes
first where the university asks for it: with ``release_after_review`` on, a result
at or above the review level is not released, so the first e-mail says only that a
member of staff is looking at it. The figures follow when the review ends with no
further action. A referral opens a case, which tells the student itself.

The same rules decide what the student can see on screen, so the e-mail never
shows more than the portal does. Sources are never named. Group work goes to every
member. Functions return ``(address, subject, body)`` tuples to send after commit.
"""

from __future__ import annotations

import json
import logging

from education_system.systems.university.application.integrity import access, evidence
from education_system.systems.university.infrastructure.email.template_utils import (
    render_template,
)

logger = logging.getLogger(__name__)

RESULTS_TEMPLATE = "academics/assignment_check_results"
FINISHED_TEMPLATE = "academics/assignment_check_review_finished"
UNDER_REVIEW = ("A member of staff is reviewing this result first. You will be told the outcome "
                "when they have finished.")
NOT_RUN = "This check is not used on this module."


def similarity_text(conn, row) -> str:
    """A released similarity result, in words. Never names a source."""
    words = row["words_checked"] or 0
    excluded = row["words_excluded"] or 0
    sources = conn.execute("SELECT COUNT(*) FROM plagiarism_matches WHERE result_id = ? "
                           "AND counted = 1", (row["id"],)).fetchone()[0]
    if sources:
        text = (f"{float(row['similarity_score'] or 0):.0%} of the {words} words checked also "
                f"appear in {sources} other source(s).")
    else:
        text = f"No matching text was found in the {words} words checked."
    if excluded:
        text += f" {excluded} quoted or reference-list words were left out."
    if row["paraphrase_score"]:
        text += (f" A further {float(row['paraphrase_score']):.0%} of the words are in sentences "
                 "that reword a source.")
    return text


def reading_text(row) -> str:
    """A released AI-writing reading, in words."""
    from education_system.systems.university.application.integrity import ai as integrity_ai
    try:
        reading = json.loads(row.get("detailed_results") or "{}")
    except ValueError:
        reading = {}
    if reading.get("strength") is None:
        return reading.get("note") or "No reading was taken for this kind of work."
    lines = [f"Reading: {row['level'] or 'taken'} ({float(row['ai_score'] or 0):.0%})."]
    lines += [f"- {i['label']}: {i['shown']}" for i in reading.get("indicators", [])
              if i.get("label")]
    lines.append(integrity_ai.NOTICE)
    return "\n".join(lines)


def _submission(conn, submission_id) -> dict | None:
    return access.one(conn, "SELECT s.*, a.title, a.module_code FROM assignment_submissions s "
                            "JOIN assignments a ON a.id = s.assignment_id WHERE s.id = ?",
                      (submission_id,))


def _members(conn, sub) -> list[str]:
    """Who the submission belongs to: the student, or everyone in the group."""
    if not sub.get("group_id"):
        return [sub["student_id"]]
    rows = conn.execute("SELECT DISTINCT student_id FROM assignment_submissions "
                        "WHERE assignment_id = ? AND group_id = ?",
                        (sub["assignment_id"], sub["group_id"])).fetchall()
    return [r[0] for r in rows] or [sub["student_id"]]


def _first_name(conn, student_id) -> str:
    if "first_name" not in {r[1] for r in conn.execute("PRAGMA table_info(students)")}:
        return "student"
    row = conn.execute("SELECT first_name FROM students WHERE student_id = ?",
                       (student_id,)).fetchone()
    return (row[0] if row else "") or "student"


def _emails(conn, sub, template, values) -> list[tuple]:
    out = []
    for student_id in _members(conn, sub):
        address = evidence._student_email(conn, student_id)
        if not address:
            logger.info("No e-mail address for student %s; check results not sent", student_id)
            continue
        subject, body = render_template(template, {
            "first_name": _first_name(conn, student_id), "assignment_title": sub["title"] or "",
            "module_code": sub["module_code"] or "", **values})
        if subject is None:
            raise ValueError(f"E-mail template {template} could not be rendered")
        out.append((address, subject, body))
    return out


def _latest_similarity(conn, submission_id) -> dict | None:
    return access.one(conn, "SELECT * FROM plagiarism_results WHERE submission_id = ? "
                            "ORDER BY id DESC LIMIT 1", (submission_id,))


def results_emails(conn, submission_id) -> list[tuple]:
    """The e-mail after an automatic check. Empty if neither check was run."""
    from education_system.systems.university.application.integrity import ai as integrity_ai
    access.ensure(conn)
    sub = _submission(conn, submission_id)
    if not sub:
        return []
    similarity = _latest_similarity(conn, submission_id)
    reading = integrity_ai.latest_for_submission(conn, submission_id)
    if not similarity and not reading:
        return []
    if not similarity:
        similarity_result = NOT_RUN
    elif similarity["released_to_student"]:
        similarity_result = similarity_text(conn, similarity)
    else:
        similarity_result = UNDER_REVIEW
    if not reading:
        ai_result = NOT_RUN
    elif integrity_ai.released(conn, reading):
        ai_result = reading_text(reading)
    else:
        ai_result = UNDER_REVIEW
    return _emails(conn, sub, RESULTS_TEMPLATE,
                   {"similarity_result": similarity_result, "ai_result": ai_result})


def similarity_review_finished(conn, result_id) -> list[tuple]:
    """After staff close a held similarity result with no further action."""
    row = access.one(conn, "SELECT * FROM plagiarism_results WHERE id = ?", (result_id,))
    sub = _submission(conn, row["submission_id"]) if row and row["submission_id"] else None
    if not sub:
        return []
    return _emails(conn, sub, FINISHED_TEMPLATE, {"check_name": "similarity check",
                                                  "result": similarity_text(conn, row)})


def reading_review_finished(conn, row) -> list[tuple]:
    """After staff close a held AI-writing reading with no further action."""
    sub = (_submission(conn, row["assignment_submission_id"])
           if row.get("assignment_submission_id") else None)
    if not sub:
        return []
    return _emails(conn, sub, FINISHED_TEMPLATE, {"check_name": "AI-writing reading",
                                                  "result": reading_text(row)})
