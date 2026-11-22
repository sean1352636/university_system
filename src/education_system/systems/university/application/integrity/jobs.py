"""The daily academic integrity jobs (run by
``infrastructure/integrity/retention_worker`` with the retention purge).

* Similarity results and AI-writing readings waiting for review longer
  than ``review_reminder_days`` — the module's staff are reminded, again
  every ``review_reminder_days`` while they wait.
* Cases sitting at ``referred`` / ``investigating`` / ``meeting`` with
  nothing logged for ``stage_reminder_days`` — the integrity officers are
  reminded, again every ``stage_reminder_days``.
* The student is reminded once, two days before their statement deadline,
  if they have not responded, and once, three days before the appeal
  deadline, if they have not appealed.
* With ``auto_close`` on, a decided case whose appeal period has passed
  with no appeal waiting is closed (a case sent to the panel is not: the
  panel's decision closes it).

Reminders sent are kept in ``integrity_reminders`` so nothing is sent
twice. Functions take an open connection and do not commit; e-mails are
returned for the caller to send after commit.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from education_system.systems.university.application.integrity import access
from education_system.systems.university.application.integrity import evidence
from education_system.systems.university.application.integrity import review

STATEMENT_WARNING_DAYS = 2
APPEAL_WARNING_DAYS = 3


def _fmt(day) -> str:
    return day.strftime("%Y-%m-%d %H:%M:%S")


def _due(conn, kind, ref, now, every_days=None) -> bool:
    """Should reminder ``(kind, ref)`` go now? Once ever, or once every
    ``every_days``."""
    row = conn.execute("SELECT sent_at FROM integrity_reminders WHERE kind = ? AND ref = ?",
                       (kind, str(ref))).fetchone()
    if row is None:
        return True
    if every_days is None:
        return False
    return row[0] <= _fmt(now - timedelta(days=every_days))


def _sent(conn, kind, ref, now) -> None:
    conn.execute("INSERT INTO integrity_reminders (kind, ref, sent_at) VALUES (?, ?, ?) "
                 "ON CONFLICT(kind, ref) DO UPDATE SET sent_at = excluded.sent_at",
                 (kind, str(ref), _fmt(now)))


def _review_reminders(conn, now) -> list[tuple]:
    days = int(access.number(conn, "review_reminder_days"))
    cutoff = _fmt(now - timedelta(days=days))
    waiting: dict[str, list] = {}
    for result_id, module, checked in conn.execute(
            "SELECT r.id, d.module_code, r.check_date FROM plagiarism_results r JOIN "
            "document_repository d ON d.id = r.document_id WHERE r.review_status = 'pending' "
            "AND r.check_date <= ? AND d.module_code IS NOT NULL", (cutoff,)).fetchall():
        if _due(conn, "review", result_id, now, days):
            waiting.setdefault(module, []).append(("review", result_id, "similarity report",
                                                   checked))
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'ai_detector_results'").fetchone():
        for result_id, module, read_at in conn.execute(
                "SELECT r.id, s.course_code, r.created_at FROM ai_detector_results r JOIN "
                "ai_detector_submissions s ON s.id = r.submission_id LEFT JOIN "
                "integrity_ai_reviews v ON v.ai_result_id = r.id WHERE v.ai_result_id IS NULL "
                "AND r.ai_score >= ? AND r.created_at <= ? AND s.course_code IS NOT NULL",
                (access.number(conn, "ai_review_threshold"), cutoff)).fetchall():
            if _due(conn, "ai_review", result_id, now, days):
                waiting.setdefault(module, []).append(("ai_review", result_id,
                                                       "AI-writing reading", read_at))
    emails = []
    for module, items in waiting.items():
        addresses = access.module_staff_emails(conn, module) or access.officer_emails(conn)
        lines = "\n".join(f"  {what} {rid}, taken {(at or '')[:10]}"
                          for _kind, rid, what, at in items)
        for address in addresses:
            emails.append((address, f"{module}: integrity results waiting for review",
                           f"These results on {module} have waited more than {days} days for "
                           f"review:\n{lines}\n\nStudents do not see a held result until it "
                           "is reviewed."))
        for kind, rid, _what, _at in items:
            _sent(conn, kind, rid, now)
    return emails


def _stage_reminders(conn, now) -> list[tuple]:
    days = int(access.number(conn, "stage_reminder_days"))
    cutoff = _fmt(now - timedelta(days=days))
    stalled = []
    for case_id, stage, last in conn.execute(
            "SELECT c.id, c.stage, MAX(e.at) FROM integrity_cases c LEFT JOIN "
            "integrity_case_events e ON e.case_id = c.id WHERE c.stage IN "
            "('referred', 'investigating', 'meeting') GROUP BY c.id").fetchall():
        if (last or "") <= cutoff and _due(conn, "stage", case_id, now, days):
            stalled.append((case_id, stage, last))
    if not stalled:
        return []
    lines = "\n".join(f"  case {cid}: {stage} since {(last or '')[:10] or 'unknown'}"
                      for cid, stage, last in stalled)
    for cid, _stage, _last in stalled:
        _sent(conn, "stage", cid, now)
    return [(address, "Academic integrity cases with no progress",
             f"Nothing has been recorded on these cases for {days} days or more:\n{lines}")
            for address in access.officer_emails(conn)]


def _student_reminders(conn, now) -> list[tuple]:
    emails = []
    today = now.strftime("%Y-%m-%d")
    soon = (now + timedelta(days=STATEMENT_WARNING_DAYS)).strftime("%Y-%m-%d")
    for case_id, student, due in conn.execute(
            "SELECT id, student_id, response_due FROM integrity_cases WHERE stage IN "
            "('referred', 'investigating', 'meeting') AND response_due BETWEEN ? AND ?",
            (today, soon)).fetchall():
        if evidence.has_statement(conn, case_id) or not _due(conn, "statement", case_id, now):
            continue
        emails += review._mail(conn, student, f"Academic integrity case {case_id}: your account",
                               f"You have until {due} to send your account of what happened "
                               f"for case {case_id} (University app, Academic Integrity, My "
                               "cases). If you do not, the case may be decided without it.")
        _sent(conn, "statement", case_id, now)
    soon = (now + timedelta(days=APPEAL_WARNING_DAYS)).strftime("%Y-%m-%d")
    for case_id, student, deadline in conn.execute(
            "SELECT c.id, c.student_id, c.appeal_deadline FROM integrity_cases c WHERE "
            "c.stage = 'decided' AND c.outcome <> 'no_case' AND c.appeal_deadline BETWEEN ? "
            "AND ? AND NOT EXISTS (SELECT 1 FROM integrity_appeals a WHERE a.case_id = c.id)",
            (today, soon)).fetchall():
        if not _due(conn, "appeal", case_id, now):
            continue
        emails += review._mail(conn, student, f"Academic integrity case {case_id}: appeal deadline",
                               f"If you want to appeal the decision on case {case_id}, you have "
                               f"until {deadline}.")
        _sent(conn, "appeal", case_id, now)
    return emails


def _auto_close(conn, now) -> int:
    if access.setting(conn, "auto_close") != "1":
        return 0
    today = now.strftime("%Y-%m-%d")
    closed = 0
    for (case_id,) in conn.execute(
            "SELECT c.id FROM integrity_cases c WHERE c.stage = 'decided' AND "
            "COALESCE(c.outcome, '') <> 'panel' AND c.appeal_deadline < ? AND NOT EXISTS "
            "(SELECT 1 FROM integrity_appeals a WHERE a.case_id = c.id AND a.status = 'lodged')",
            (today,)).fetchall():
        review.close(conn, None, case_id, "Closed automatically: the appeal period ended.",
                     actor="automatic")
        closed += 1
    return closed


def run_daily(conn, now=None) -> dict:
    """Run every daily job. Returns counts and ``emails``."""
    access.ensure(conn)
    now = now or datetime.now()
    emails = _review_reminders(conn, now)
    emails += _stage_reminders(conn, now)
    emails += _student_reminders(conn, now)
    closed = _auto_close(conn, now)
    if emails or closed:
        access.audit(conn, "automatic", "jobs", None, "daily run",
                     {"emails": len(emails), "closed": closed})
    return {"emails": emails, "reminders": len(emails), "closed": closed}
