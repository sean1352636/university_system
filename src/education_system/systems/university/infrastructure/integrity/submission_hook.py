"""The automatic similarity check (and AI-writing reading) after a student
submits, and the e-mail telling the student the results.

Every place that saves an assignment submission calls
:func:`after_submission` once its transaction has committed. The check
runs in a background thread on its own connection, so the student is
never kept waiting and a failed check never loses a submission. A failure
is recorded (``plagiarism_checks.record_failure``) so it shows in staff's
"Failed checks" list; :func:`retry_failures` (run daily) tries again, up to
:data:`MAX_ATTEMPTS` times, and staff can check the text by hand.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from education_system.systems.university.application.integrity import (
    plagiarism_checks,
    submission_results,
)
from education_system.systems.university.infrastructure.integrity import text_extract

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
RETRY_AFTER = timedelta(hours=1)


def _connect(db_path=None):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path, row_factory=False)


def check_now(submission_id, *, text=None, path=None, db_path=None) -> int | None:
    """Run the check in this thread. Returns the result id."""
    conn = _connect(db_path)
    try:
        if text is None:
            if path is None:
                row = conn.execute("SELECT file_path, content FROM assignment_submissions "
                                   "WHERE id = ?", (submission_id,)).fetchone()
                if not row:
                    return None
                path, text = row[0], row[1]
            if text is None or not str(text).strip():
                text = text_extract.extract(path)
        kind = text_extract.file_type(path) if path else "txt"
        result = plagiarism_checks.check_submission(conn, submission_id, text, kind)
        conn.commit()
        _ai_reading(conn, submission_id, text, kind)
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ai_reading(conn, submission_id, text, kind) -> None:
    """The AI-writing reading on the same text. Its failure never fails the
    similarity check, and a resubmission is read again."""
    from education_system.systems.university.application.integrity import ai as integrity_ai
    try:
        result_id = integrity_ai.check_submission(conn, submission_id, text, kind)
        emails = []
        if result_id:
            from education_system.systems.university.shared.ai.ai_detector.detector import (
                reading,
            )
            emails = reading.alert_emails(conn, result_id)
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("AI-writing reading for submission %s failed", submission_id)
        return
    if emails:
        from education_system.systems.university.infrastructure.ui.record_screens import (
            send_emails,
        )
        send_emails(emails)


def _record_failure(submission_id, error, db_path) -> None:
    try:
        conn = _connect(db_path)
        try:
            plagiarism_checks.record_failure(conn, submission_id, error)
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.exception("Could not record the failed check of submission %s", submission_id)


def _email_results(submission_id, db_path) -> None:
    """Tell the student how the checks went. Failing here doesn't fail the check."""
    try:
        conn = _connect(db_path)
        try:
            emails = submission_results.results_emails(conn, submission_id)
            conn.commit()
        finally:
            conn.close()
        if emails:
            from education_system.systems.university.infrastructure.ui.record_screens import (
                send_emails,
            )
            send_emails(emails)
    except Exception:
        logger.exception("Could not e-mail the check results for submission %s", submission_id)


def _checks_on(submission_id, db_path) -> bool:
    """False when the lecturer turned the checks off on this assignment."""
    conn = _connect(db_path)
    try:
        if "automatic_checks" not in {r[1] for r in conn.execute("PRAGMA table_info(assignments)")}:
            return True
        row = conn.execute("SELECT a.automatic_checks FROM assignment_submissions s JOIN assignments a "
                           "ON a.id = s.assignment_id WHERE s.id = ?", (submission_id,)).fetchone()
        return not row or row[0] != 0
    finally:
        conn.close()


def _safe(submission_id, text, path, db_path) -> bool:
    try:
        if not _checks_on(submission_id, db_path):
            return True
        check_now(submission_id, text=text, path=path, db_path=db_path)
    except Exception as exc:
        logger.exception("Similarity check for submission %s failed", submission_id)
        _record_failure(submission_id, exc, db_path)
        return False
    _email_results(submission_id, db_path)
    return True


def retry_failures(db_path=None, now=None) -> dict:
    """Try failed automatic checks again (from the stored file or text)."""
    now = now or datetime.now()
    cutoff = (now - RETRY_AFTER).strftime("%Y-%m-%d %H:%M:%S")
    conn = _connect(db_path)
    try:
        plagiarism_checks.access.ensure(conn)
        due = [r[0] for r in conn.execute(
            "SELECT submission_id FROM integrity_check_failures WHERE resolved_at IS NULL "
            "AND attempts < ? AND last_attempt_at <= ?", (MAX_ATTEMPTS, cutoff))]
    finally:
        conn.close()
    done = [sid for sid in due if _safe(sid, None, None, db_path)]
    if done:
        # Ran without error but made no result: the submission is gone or
        # checks were turned off for its module since.
        conn = _connect(db_path)
        try:
            for sid in done:
                plagiarism_checks.resolve_failure(conn, sid, "no check needed")
            conn.commit()
        finally:
            conn.close()
    return {"retried": len(due), "checked": len(done)}


def after_submission(submission_id, *, text=None, path=None, db_path=None,
                     background=True) -> None:
    """Call after the submission is committed."""
    if not background:
        _safe(submission_id, text, path, db_path)
        return
    threading.Thread(target=_safe, args=(submission_id, text, path, db_path), daemon=True,
                     name=f"similarity-check-{submission_id}").start()
