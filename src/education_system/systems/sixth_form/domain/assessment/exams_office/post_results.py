"""Post-results services: clerical checks, reviews of marking, scripts.

A request is made for one result (a component result or a
qualification result). The candidate's written consent is required
before a review is submitted, because a review can lower a grade as
well as raise it. Each service has a board deadline counted from
results day (constants in :mod:`boards`) and a fee from the fee list
the exams officer keeps per board and series.

When the board's outcome changes the grade, the result is updated in
place and the change is kept in the result history; the fee is then
normally refunded by the board, which is recorded too.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
    POST_RESULTS_SERVICES,
    post_results_deadline_days,
)
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

SERVICES = POST_RESULTS_SERVICES

# Services that can change a mark, so need the candidate's consent.
_CONSENT_SERVICES = {"Clerical check", "Review of marking", "Priority review of marking",
                     "Review of moderation"}

STATUSES: tuple[str, ...] = (
    "Requested", "Consent received", "Submitted", "Outcome received", "Withdrawn")

OUTCOMES: tuple[str, ...] = (
    "Pending", "Grade changed", "Mark changed, grade unchanged",
    "No change", "Script received", "Rejected (late / ineligible)")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_post_results_fees (
    fee_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_board  TEXT NOT NULL,
    season      TEXT NOT NULL,
    year        INTEGER NOT NULL,
    service     TEXT NOT NULL,
    fee         REAL NOT NULL,
    UNIQUE(exam_board, season, year, service)
);

CREATE TABLE IF NOT EXISTS exams_post_results (
    request_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    result_id       INTEGER,
    qual_result_id  INTEGER,
    exam_board      TEXT NOT NULL,
    code            TEXT NOT NULL,
    season          TEXT NOT NULL,
    year            INTEGER NOT NULL,
    service         TEXT NOT NULL,
    deadline        TEXT,
    consent_obtained INTEGER NOT NULL DEFAULT 0,
    consent_date    TEXT,
    consent_ref     TEXT,
    status          TEXT NOT NULL DEFAULT 'Requested',
    requested_date  TEXT NOT NULL,
    submitted_date  TEXT,
    board_reference TEXT,
    fee             REAL,
    fee_paid_by     TEXT,
    original_grade  TEXT,
    original_marks  INTEGER,
    outcome         TEXT NOT NULL DEFAULT 'Pending',
    outcome_date    TEXT,
    new_grade       TEXT,
    new_marks       INTEGER,
    fee_refunded    INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    recorded_by     TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (result_id) REFERENCES exam_results(result_id) ON DELETE SET NULL,
    FOREIGN KEY (qual_result_id)
        REFERENCES exams_qualification_results(qual_result_id) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS idx_exams_pr_series ON exams_post_results(year, season);
"""


def _results_day_init() -> None:
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    results_day.init_db()


def init_db() -> None:
    store.ensure("post_results", _SCHEMA, after=(_results_day_init,))


_FIELDS = ("request_id", "student_id", "result_id", "qual_result_id", "exam_board",
           "code", "season", "year", "service", "deadline", "consent_obtained",
           "consent_date", "consent_ref", "status", "requested_date", "submitted_date",
           "board_reference", "fee", "fee_paid_by", "original_grade", "original_marks",
           "outcome", "outcome_date", "new_grade", "new_marks", "fee_refunded", "notes",
           "recorded_by", "created_at", "updated_at")


@dataclass
class Request:
    request_id: int
    student_id: str
    result_id: int | None
    qual_result_id: int | None
    exam_board: str
    code: str
    season: str
    year: int
    service: str
    deadline: str | None
    consent_obtained: bool
    consent_date: str | None
    consent_ref: str | None
    status: str
    requested_date: str
    submitted_date: str | None
    board_reference: str | None
    fee: float | None
    fee_paid_by: str | None
    original_grade: str | None
    original_marks: int | None
    outcome: str
    outcome_date: str | None
    new_grade: str | None
    new_marks: int | None
    fee_refunded: bool
    notes: str | None
    recorded_by: str | None
    created_at: str | None
    updated_at: str | None
    full_name: str | None = None

    @property
    def needs_consent(self) -> bool:
        return self.service in _CONSENT_SERVICES

    @property
    def overdue(self) -> bool:
        return bool(self.deadline and not self.submitted_date
                    and self.status not in ("Withdrawn",)
                    and store.today() > self.deadline)


def _req(r, names: dict[str, str] | None = None) -> Request:
    q = Request(**{k: r[k] for k in _FIELDS})
    q.consent_obtained = bool(q.consent_obtained)
    q.fee_refunded = bool(q.fee_refunded)
    q.full_name = (names or {}).get(q.student_id)
    return q


# ── Fees and deadlines ──────────────────────────────────────────────

def set_fee(exam_board: str, season: str, year: int, service: str, fee: Any) -> None:
    init_db()
    board = store.board(exam_board)
    season, year = store.season_year(season, year)
    service = store.choice(service, "Service", SERVICES)
    amount = store.money(fee, "Fee")
    if amount is None:
        raise ValidationError("Fee is required")
    with store.connect() as conn:
        conn.execute(
            """INSERT INTO exams_post_results_fees (exam_board, season, year, service, fee)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(exam_board, season, year, service) DO UPDATE SET
                   fee = excluded.fee""", (board, season, year, service, amount))
        conn.commit()


def list_fees(*, year: int | None = None) -> list[dict]:
    init_db()
    sql = "SELECT * FROM exams_post_results_fees"
    args: list[Any] = []
    if year is not None:
        sql += " WHERE year = ?"
        args.append(int(year))
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(
            sql + " ORDER BY year DESC, season, exam_board, service", args)]


def fee_for(exam_board: str, season: str, year: int, service: str) -> float | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute(
            "SELECT fee FROM exams_post_results_fees WHERE exam_board = ? AND season = ? "
            "AND year = ? AND service = ?",
            (store.board(exam_board), season, int(year), service)).fetchone()
    return r["fee"] if r else None


def deadline_for(exam_board: str, season: str, year: int, service: str) -> str | None:
    """Board deadline: results day (from the release schedule) + the JCQ gap."""
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    rel = results_day.release_for(season, year, exam_board)
    if rel is None:
        return None
    days = post_results_deadline_days(exam_board, season, service)
    return (_dt.date.fromisoformat(rel.results_date) + _dt.timedelta(days=days)).isoformat()


def deadlines_table(season: str, year: int) -> list[tuple[str, str, int, str | None]]:
    """(board, service, days after results, date) for every board/service."""
    from education_system.systems.sixth_form.domain.assessment.exams_office.boards import (
        EXAM_BOARDS,
    )
    out = []
    for board in EXAM_BOARDS[:5]:
        for service in SERVICES:
            out.append((board, service, post_results_deadline_days(board, season, service),
                        deadline_for(board, season, year, service)))
    return out


# ── Requests ────────────────────────────────────────────────────────

def _target(data: dict[str, Any]) -> tuple[str, int | None, int | None, str, str, str, int,
                                           str | None, int | None]:
    """Resolve the result a request is about.

    Returns (student, result_id, qual_result_id, board, code, season, year,
    current grade, current marks).
    """
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _results,
    )
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    rid = store.integer(data.get("result_id"), "Result")
    qid = store.integer(data.get("qual_result_id"), "Qualification result")
    if rid is not None:
        res = _results.get_result(rid)
        if res is None:
            raise ValidationError(f"No result #{rid}")
        e = _entries.get_entry(res.entry_id)
        assert e is not None
        return (e.student_id, rid, None, e.exam_board, e.paper_code, e.season, e.year,
                res.grade, res.marks)
    if qid is not None:
        q = results_day.get_qualification_result_by_id(qid)
        if q is None:
            raise ValidationError(f"No qualification result #{qid}")
        return (q.student_id, None, qid, q.exam_board, q.entry_code, q.season, q.year,
                q.grade, q.marks)
    raise ValidationError("Pick the result the request is about")


def create_request(data: dict[str, Any]) -> Request:
    init_db()
    sid, rid, qid, board, code, season, year, grade, marks = _target(data)
    service = store.choice(data.get("service"), "Service", SERVICES)
    requested = store.date(data.get("requested_date"), "Requested date") or store.today()
    deadline = deadline_for(board, season, year, service)
    fee = store.money(data.get("fee"), "Fee")
    if fee is None:
        fee = fee_for(board, season, year, service)
    consent = store.flag(data.get("consent_obtained"))
    consent_date = store.date(data.get("consent_date"), "Consent date")
    if consent and not consent_date:
        consent_date = store.today()
    with store.connect() as conn:
        cur = conn.execute(
            """INSERT INTO exams_post_results
                   (student_id, result_id, qual_result_id, exam_board, code, season,
                    year, service, deadline, consent_obtained, consent_date,
                    consent_ref, status, requested_date, fee, fee_paid_by,
                    original_grade, original_marks, notes, recorded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sid, rid, qid, board, code, season, year, service, deadline, consent,
             consent_date, store.text(data.get("consent_ref"), "Consent reference", limit=60),
             "Consent received" if consent else "Requested", requested, fee,
             store.text(data.get("fee_paid_by"), "Fee paid by", limit=60),
             grade, marks, store.text(data.get("notes"), "Notes", limit=1000),
             store.actor()))
        conn.commit()
        new_id = int(cur.lastrowid)
    out = get_request(new_id)
    assert out is not None
    logger.info("Post-results request #%d: %s for %s %s", new_id, service, sid, code)
    return out


def record_consent(request_id: int, *, consent_date: str | None = None,
                   consent_ref: str | None = None) -> Request:
    init_db()
    req = _require(request_id)
    with store.connect() as conn:
        conn.execute(
            """UPDATE exams_post_results SET consent_obtained = 1, consent_date = ?,
                   consent_ref = COALESCE(?, consent_ref),
                   status = CASE WHEN status = 'Requested' THEN 'Consent received'
                                 ELSE status END,
                   updated_at = datetime('now')
               WHERE request_id = ?""",
            (store.date(consent_date, "Consent date") or store.today(),
             store.text(consent_ref, "Consent reference", limit=60), req.request_id))
        conn.commit()
    return _require(request_id)


def submit_request(request_id: int, *, board_reference: str | None = None,
                   submitted_date: str | None = None) -> Request:
    """Mark a request as sent to the board. Refuses without consent."""
    init_db()
    req = _require(request_id)
    if req.status in ("Submitted", "Outcome received", "Withdrawn"):
        raise ValidationError(f"Request #{request_id} is already {req.status.lower()}")
    if req.needs_consent and not req.consent_obtained:
        raise ValidationError(
            "The candidate's written consent is required before a review is "
            "submitted — a grade can go down as well as up")
    when = store.date(submitted_date, "Submitted date") or store.today()
    with store.connect() as conn:
        conn.execute(
            """UPDATE exams_post_results SET status = 'Submitted', submitted_date = ?,
                   board_reference = COALESCE(?, board_reference),
                   updated_at = datetime('now')
               WHERE request_id = ?""",
            (when, store.text(board_reference, "Board reference", limit=60),
             req.request_id))
        conn.commit()
    out = _require(request_id)
    if out.deadline and when > out.deadline:
        logger.warning("Post-results request #%d submitted after the %s deadline",
                       request_id, out.deadline)
    return out


def record_outcome(request_id: int, *, outcome: str, new_grade: str | None = None,
                   new_marks: Any = None, outcome_date: str | None = None,
                   fee_refunded: bool | None = None, notes: str | None = None) -> Request:
    """Record the board's answer; a changed grade updates the result."""
    init_db()
    from education_system.systems.sixth_form.domain.assessment.exam_results import (
        exam_results as _results,
    )
    from education_system.systems.sixth_form.domain.assessment.exams_office import (
        results_day,
    )
    req = _require(request_id)
    if req.status == "Withdrawn":
        raise ValidationError("This request was withdrawn")
    outcome = store.choice(outcome, "Outcome", OUTCOMES)
    marks = store.integer(new_marks, "New marks", lo=0, hi=10000)
    grade = store.text(new_grade, "New grade", limit=20)
    if outcome == "Grade changed":
        if not grade:
            raise ValidationError("Give the new grade")
        if grade == req.original_grade:
            raise ValidationError("The new grade is the same as the original")
    elif outcome == "Mark changed, grade unchanged" and marks is None:
        raise ValidationError("Give the new mark")
    reason = f"{req.service} (request #{req.request_id}): {outcome}"
    if outcome in ("Grade changed", "Mark changed, grade unchanged"):
        if req.result_id:
            payload: dict[str, Any] = {}
            if outcome == "Grade changed":
                payload["grade"] = grade
            if marks is not None:
                payload["marks"] = marks
            _results.update_result(req.result_id, payload, reason=reason)
        elif req.qual_result_id:
            q = results_day.get_qualification_result_by_id(req.qual_result_id)
            if q is None:
                raise ValidationError("The qualification result no longer exists")
            results_day.save_qualification_result({
                "student_id": q.student_id, "exam_board": q.exam_board,
                "entry_code": q.entry_code, "season": q.season, "year": q.year,
                "qualification_type": q.qualification_type,
                "grade": grade if outcome == "Grade changed" else q.grade,
                "marks": marks if marks is not None else q.marks, "ums": q.ums,
            }, source="post-results", released=True, reason=reason)
    refunded = (outcome == "Grade changed") if fee_refunded is None else bool(fee_refunded)
    with store.connect() as conn:
        conn.execute(
            """UPDATE exams_post_results SET outcome = ?, outcome_date = ?,
                   new_grade = ?, new_marks = ?, fee_refunded = ?,
                   status = 'Outcome received',
                   notes = COALESCE(?, notes), updated_at = datetime('now')
               WHERE request_id = ?""",
            (outcome, store.date(outcome_date, "Outcome date") or store.today(),
             grade if outcome == "Grade changed" else None, marks, 1 if refunded else 0,
             store.text(notes, "Notes", limit=1000), req.request_id))
        conn.commit()
    logger.info("Post-results request #%d outcome: %s", request_id, outcome)
    return _require(request_id)


def withdraw_request(request_id: int, *, reason: str | None = None) -> Request:
    init_db()
    req = _require(request_id)
    if req.status == "Outcome received":
        raise ValidationError("The board has already answered this request")
    with store.connect() as conn:
        conn.execute(
            "UPDATE exams_post_results SET status = 'Withdrawn', "
            "notes = COALESCE(?, notes), updated_at = datetime('now') WHERE request_id = ?",
            (store.text(reason, "Reason", limit=500), req.request_id))
        conn.commit()
    return _require(request_id)


def get_request(request_id: int) -> Request | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT * FROM exams_post_results WHERE request_id = ?",
                         (int(request_id),)).fetchone()
    return _req(r, store.student_names()) if r else None


def _require(request_id: int) -> Request:
    req = get_request(request_id)
    if req is None:
        raise ValidationError(f"No post-results request #{request_id}")
    return req


def list_requests(*, season: str | None = None, year: int | None = None,
                  student_id: str | None = None, status: str | None = None,
                  service: str | None = None) -> list[Request]:
    init_db()
    clauses, args = [], []
    for col, val in (("season", season), ("student_id", student_id),
                     ("status", status), ("service", service)):
        if val:
            clauses.append(f"{col} = ?")
            args.append(val)
    if year is not None:
        clauses.append("year = ?")
        args.append(int(year))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    names = store.student_names()
    with store.connect() as conn:
        rows = conn.execute(f"SELECT * FROM exams_post_results {where} "
                            "ORDER BY requested_date DESC, request_id DESC", args).fetchall()
    return [_req(r, names) for r in rows]
