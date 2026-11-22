"""Sixth Form coursework assignments — similarity / plagiarism checks, automatic
late detection and the summary.

Owns ``_SIMILARITY_PROVIDER``; the ``assignments`` facade forwards reads and
writes of it here.

Split out of ``assignments.py``, which re-exports every name defined here."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
import datetime as _dt
from education_system.systems.sixth_form.domain.academics.assignments.models import (
    ASSIGNMENT_STATUSES,
    ASSIGNMENT_TYPES,
    Attachment,
    DEFAULT_SIMILARITY_THRESHOLD,
    DONE_SUBMISSION_STATUSES,
    PENDING_SUBMISSION_STATUSES,
    SimilarityResult,
    Submission,
    Summary,
    ValidationError,
    logger,
)
from education_system.systems.sixth_form.domain.academics.assignments.store import (
    _connect,
    _row_submission,
    _validate_date,
    _validate_number,
    get_assignment,
    get_submission,
    init_db,
    list_assignments,
)
from education_system.systems.sixth_form.domain.academics.assignments.submissions import (
    list_attachments,
)

# ── Similarity / plagiarism ───────────────────────────────────────

# Set by whatever integration the college actually buys. Called with
# (submission, attachments) and expected to return a SimilarityResult
# or None. Nothing ships wired up — the schema, threshold and flagged
# report below work whether or not a provider is registered.
_SIMILARITY_PROVIDER: Callable[
    [Submission, list[Attachment]], SimilarityResult | None] | None = None


def register_similarity_provider(
        fn: Callable[[Submission, list[Attachment]],
                      SimilarityResult | None]) -> None:
    """Install the plagiarism checker used by :func:`run_similarity_check`."""
    global _SIMILARITY_PROVIDER
    _SIMILARITY_PROVIDER = fn
    logger.info("Similarity provider registered: %s",
                getattr(fn, "__name__", fn))


def clear_similarity_provider() -> None:
    global _SIMILARITY_PROVIDER
    _SIMILARITY_PROVIDER = None


def record_similarity(submission_id: int, *,
                       score: float,
                       provider: str | None = None,
                       report_ref: str | None = None,
                       checked_on: str | None = None,
                       version_id: int | None = None) -> Submission:
    """Store a similarity score against a submission (and attempt).

    Above the assignment's threshold the result is logged as a flag for
    a human to review — this module never accuses anyone by itself.
    """
    init_db()
    sub = get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    value = _validate_number(score, "Similarity score",
                              min_val=0, max_val=100)
    if value is None:
        raise ValidationError("Similarity score is required")
    when = _validate_date(checked_on, "Checked on") \
        or _dt.date.today().isoformat()

    with _connect() as conn:
        conn.execute(
            """UPDATE coursework_submissions SET
                   similarity_score = ?, similarity_provider = ?,
                   similarity_report = ?, similarity_checked_on = ?,
                   updated_at = datetime('now')
               WHERE submission_id = ?""",
            (value, (provider or "").strip() or None,
             (report_ref or "").strip() or None, when, submission_id))
        if version_id is not None:
            conn.execute(
                "UPDATE coursework_submission_versions SET "
                "similarity_score = ? WHERE version_id = ? "
                "AND submission_id = ?",
                (value, version_id, submission_id))
        conn.commit()

    out = get_submission(submission_id)
    assert out is not None
    assignment = get_assignment(sub.assignment_id)
    threshold = (assignment.effective_similarity_threshold
                  if assignment else DEFAULT_SIMILARITY_THRESHOLD)
    if value >= threshold:
        logger.warning(
            "Similarity %.1f%% on submission #%d (student %s, "
            "assignment #%d) is at or above the %.1f%% threshold — "
            "flagged for review%s",
            value, submission_id, sub.student_id, sub.assignment_id,
            threshold,
            f" (report {report_ref})" if report_ref else "")
    return out


def run_similarity_check(submission_id: int) -> SimilarityResult | None:
    """Ask the registered provider to score a submission.

    Returns ``None`` when no provider is installed, so callers can
    offer the action without needing to know whether the college has
    an integration.
    """
    init_db()
    if _SIMILARITY_PROVIDER is None:
        logger.info("No similarity provider registered — skipping check "
                    "on submission #%d", submission_id)
        return None
    sub = get_submission(submission_id)
    if sub is None:
        raise ValidationError(f"No submission #{submission_id}")
    files = list_attachments(submission_id=submission_id, kind="Work")
    result = _SIMILARITY_PROVIDER(sub, files)
    if result is None:
        return None
    record_similarity(submission_id, score=result.score,
                       provider=result.provider,
                       report_ref=result.report_ref,
                       checked_on=result.checked_on)
    return result


def list_flagged_submissions(*, assignment_id: int | None = None
                              ) -> list[Submission]:
    """Submissions whose similarity score meets the review threshold."""
    init_db()
    clauses = ["s.similarity_score IS NOT NULL"]
    args: list[Any] = []
    if assignment_id is not None:
        clauses.append("s.assignment_id = ?")
        args.append(int(assignment_id))
    sql = ("SELECT s.* FROM coursework_submissions s "
           "JOIN coursework_assignments a "
           "  ON a.assignment_id = s.assignment_id "
           f"WHERE {' AND '.join(clauses)} "
           "  AND s.similarity_score >= "
           "      COALESCE(a.similarity_threshold, ?) "
           "ORDER BY s.similarity_score DESC")
    with _connect() as conn:
        return [_row_submission(r) for r in conn.execute(
            sql, (*args, DEFAULT_SIMILARITY_THRESHOLD)).fetchall()]


# ── Automatic late detection ──────────────────────────────────────

def list_overdue_submissions(*, today: str | None = None,
                              assignment_id: int | None = None
                              ) -> list[Submission]:
    """Open submissions past their (possibly extended) deadline."""
    init_db()
    day = _validate_date(today, "today") or _dt.date.today().isoformat()
    ph = ",".join("?" * len(PENDING_SUBMISSION_STATUSES))
    clauses = [f"s.status IN ({ph})", "a.status IN ('Draft', 'Set')"]
    args: list[Any] = list(PENDING_SUBMISSION_STATUSES)
    if assignment_id is not None:
        clauses.append("s.assignment_id = ?")
        args.append(int(assignment_id))
    sql = ("SELECT s.* FROM coursework_submissions s "
           "JOIN coursework_assignments a "
           "  ON a.assignment_id = s.assignment_id "
           f"WHERE {' AND '.join(clauses)} "
           "  AND COALESCE(s.extended_due_date, a.due_date) IS NOT NULL "
           "  AND COALESCE(s.extended_due_date, a.due_date) < ? "
           "ORDER BY COALESCE(s.extended_due_date, a.due_date) ASC")
    with _connect() as conn:
        return [_row_submission(r)
                for r in conn.execute(sql, (*args, day)).fetchall()]


def sweep_late_submissions(*, today: str | None = None,
                            assignment_id: int | None = None,
                            dry_run: bool = False) -> dict[str, int]:
    """Mark work that is past its deadline and never arrived.

    Only touches ``Not Started`` / ``In Progress`` rows on assignments
    that are still open, and reads the deadline through
    :func:`effective_due_date` so an extension protects that student.
    Idempotent: a second run over the same day changes nothing.

    Returns counts: ``overdue`` seen, ``marked_missing`` changed.
    """
    init_db()
    day = _validate_date(today, "today") or _dt.date.today().isoformat()
    overdue = list_overdue_submissions(today=day,
                                        assignment_id=assignment_id)
    if dry_run or not overdue:
        return {"overdue": len(overdue), "marked_missing": 0}

    ids = [s.submission_id for s in overdue]
    with _connect() as conn:
        conn.executemany(
            "UPDATE coursework_submissions SET status = 'Missing', "
            "auto_status_on = ?, updated_at = datetime('now') "
            "WHERE submission_id = ?",
            [(day, sid) for sid in ids])
        conn.commit()
    logger.info("Late sweep on %s: marked %d submission(s) Missing",
                day, len(ids))
    return {"overdue": len(overdue), "marked_missing": len(ids)}


# ── Summary ───────────────────────────────────────────────────────

def summary(*, upcoming_window_days: int = 14) -> Summary:
    init_db()
    today = _dt.date.today().isoformat()
    horizon = (_dt.date.today()
                + _dt.timedelta(days=upcoming_window_days)).isoformat()
    rows = list_assignments()
    by_status = {s: 0 for s in ASSIGNMENT_STATUSES}
    by_type = {t: 0 for t in ASSIGNMENT_TYPES}
    by_subject: dict[str, int] = {}
    open_count = 0
    overdue = 0
    upcoming = 0
    for a in rows:
        by_status[a.status] = by_status.get(a.status, 0) + 1
        by_type[a.assignment_type] = by_type.get(
            a.assignment_type, 0) + 1
        by_subject[a.subject_name] = by_subject.get(
            a.subject_name, 0) + 1
        if a.is_open:
            open_count += 1
            if a.is_overdue:
                overdue += 1
            elif a.due_date and today <= a.due_date <= horizon:
                upcoming += 1

    with _connect() as conn:
        tot = conn.execute(
            "SELECT COUNT(*) FROM coursework_submissions"
        ).fetchone()[0]
        done = conn.execute(
            f"SELECT COUNT(*) FROM coursework_submissions "
            f"WHERE status IN "
            f"({','.join('?' * len(DONE_SUBMISSION_STATUSES))})",
            DONE_SUBMISSION_STATUSES).fetchone()[0]
        marked = conn.execute(
            "SELECT COUNT(*) FROM coursework_submissions "
            "WHERE marks IS NOT NULL").fetchone()[0]
        extensions = conn.execute(
            "SELECT COUNT(*) FROM coursework_submissions "
            "WHERE extended_due_date IS NOT NULL").fetchone()[0]
        att = conn.execute(
            "SELECT COUNT(*) n, COALESCE(SUM(byte_size), 0) b "
            "FROM coursework_attachments").fetchone()

    return Summary(
        total_assignments=len(rows),
        by_status=by_status,
        by_type=by_type,
        by_subject=dict(sorted(by_subject.items(),
                                key=lambda kv: kv[1],
                                reverse=True)),
        open_count=open_count,
        overdue=overdue,
        upcoming_due=upcoming,
        total_submissions=tot,
        submitted_total=done,
        marked_total=marked,
        overdue_submissions=len(list_overdue_submissions(today=today)),
        active_extensions=extensions,
        flagged_similarity=len(list_flagged_submissions()),
        attachment_count=att["n"] or 0,
        attachment_bytes=att["b"] or 0,
    )
