"""GCSE results-day confirmation of conditional offers.

On results day admissions staff record (or import) each applicant's
actual GCSE results, then every open conditional offer is evaluated
against its structured conditions (see :mod:`entry_requirements`):

    Met        — confirm the place (the offer becomes unconditional)
    Near miss  — one grade short somewhere: confirm anyway, offer an
                 alternative programme, or decline
    Not met    — offer an alternative or decline
    Pending    — no actual results yet, or a free-text condition still
                 needs a staff decision

``admissions_results_day`` holds one row per applicant per results day
cycle (academic year of entry): the evaluated outcome and the decision
taken, with who decided and when. Decisions also update the applicant
(offer type, status, decision reason) and land on its timeline.
"""

from __future__ import annotations

import datetime as _dt
import logging
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.admissions import (
    admissions as _adm,
    entry_requirements as _er,
)

logger = logging.getLogger(__name__)

ValidationError = _adm.ValidationError

DECISIONS: tuple[str, ...] = (
    "Pending", "Confirmed", "Confirmed (near miss)", "Alternative offered",
    "Declined",
)
#: Applicant statuses whose offer is still live on results day.
LIVE_OFFER_STATUSES: tuple[str, ...] = ("Offer Made", "Offer Accepted")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS admissions_results_day (
    applicant_id      TEXT NOT NULL,
    cycle             TEXT NOT NULL,
    outcome           TEXT NOT NULL DEFAULT 'Pending',
    outcome_detail    TEXT,
    evaluated_at      TEXT,
    decision          TEXT NOT NULL DEFAULT 'Pending',
    alternative       TEXT,
    decided_by        TEXT,
    decided_at        TEXT,
    notes             TEXT,
    PRIMARY KEY (applicant_id, cycle),
    FOREIGN KEY (applicant_id) REFERENCES admissions_applicants(applicant_id)
        ON DELETE CASCADE
);
"""


@dataclass
class ResultsDayRow:
    applicant_id: str
    cycle: str
    outcome: str
    outcome_detail: str | None
    evaluated_at: str | None
    decision: str
    alternative: str | None
    decided_by: str | None
    decided_at: str | None
    notes: str | None
    applicant_name: str = ""
    status: str = ""
    conditions: str = ""


@dataclass
class Dashboard:
    cycle: str
    total: int
    by_outcome: dict[str, int]
    by_decision: dict[str, int]
    awaiting_results: int
    awaiting_decision: int
    rows: list[ResultsDayRow] = field(default_factory=list)


# ── DB plumbing ────────────────────────────────────────────────────

def _connect() -> db.Connection:
    return _adm._connect()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    _er.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    _DB_READY = True


def current_cycle(today: _dt.date | None = None) -> str:
    """The entry year whose results day this is (e.g. '2026/27').

    A configured admissions cycle (:mod:`cycles`) whose results day falls
    this summer wins. Otherwise: GCSE results come out in August for
    entry the following September, so the cycle is the academic year
    beginning this calendar year.
    """
    from education_system.systems.sixth_form.domain.admissions import cycles
    configured = cycles.results_day_cycle(today)
    if configured:
        return configured
    return _adm.default_academic_year(today)


def _row(r: db.Row) -> ResultsDayRow:
    return ResultsDayRow(
        applicant_id=r["applicant_id"], cycle=r["cycle"],
        outcome=r["outcome"], outcome_detail=r["outcome_detail"],
        evaluated_at=r["evaluated_at"], decision=r["decision"],
        alternative=r["alternative"], decided_by=r["decided_by"],
        decided_at=r["decided_at"], notes=r["notes"])


def get_row(applicant_id: str, cycle: str | None = None
            ) -> ResultsDayRow | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM admissions_results_day WHERE applicant_id = ? "
            "AND cycle = ?", (applicant_id, cycle or current_cycle())
        ).fetchone()
    return _row(r) if r else None


# ── Evaluation ─────────────────────────────────────────────────────

def conditional_applicants(*, intake_year: str | None = None
                           ) -> list[_adm.Applicant]:
    """Applicants holding a live conditional offer (archived or merged
    records and converted applicants are never included), optionally for
    one intake year."""
    return [a for a in _adm.list_applicants(include_archived=False,
                                            intake_year=intake_year)
            if a.status in LIVE_OFFER_STATUSES
            and not a.is_archived and not a.converted_student_id
            and (a.offer_type or "Conditional") == "Conditional"]


def _live_offer(applicant_id: str, action: str) -> _adm.Applicant:
    """The applicant, if their offer can still be changed on results day;
    otherwise a clear reason why not."""
    a = _adm.get_applicant(applicant_id)
    if a is None:
        raise ValidationError(f"No applicant {applicant_id!r}")
    name = a.full_name
    if a.is_archived:
        raise ValidationError(
            f"{name}'s application is archived; restore it before you "
            f"{action}.")
    if a.converted_student_id or a.status == "Enrolled":
        raise ValidationError(
            f"{name} is already enrolled (student "
            f"{a.converted_student_id or '?'}), so you cannot {action} "
            "here. Change their programme in the Student Directory.")
    if a.status in ("Offer Declined", "Rejected", "Withdrawn"):
        raise ValidationError(
            f"{name}'s application is closed ({a.status}), so you cannot "
            f"{action}. Reopen the application with a reason first.")
    if a.status not in LIVE_OFFER_STATUSES:
        raise ValidationError(
            f"{name} does not hold a live offer (status: {a.status}), so "
            f"you cannot {action}.")
    return a


def evaluate_applicant(applicant_id: str, *, cycle: str | None = None
                       ) -> ResultsDayRow:
    """Evaluate one applicant's conditions against actual results."""
    init_db()
    cyc = cycle or current_cycle()
    if not _er.list_conditions(applicant_id):
        # Older offers only have the free-text box: build the rows from
        # the entry requirements so there is something to evaluate.
        _er.generate_conditions(applicant_id, replace=False)
    ev = _er.evaluate(applicant_id, result_type="Actual")
    detail = "; ".join(f"{c.description}: {c.effective_outcome}"
                       for c in ev.conditions)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO admissions_results_day
                   (applicant_id, cycle, outcome, outcome_detail,
                    evaluated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(applicant_id, cycle) DO UPDATE SET
                   outcome = excluded.outcome,
                   outcome_detail = excluded.outcome_detail,
                   evaluated_at = excluded.evaluated_at""",
            (applicant_id, cyc, ev.overall, detail or None, now))
        _adm._log_event(conn, applicant_id,
                        f"Results day: conditions {ev.overall} "
                        f"({ev.results_used} result(s))", kind="offer")
        conn.commit()
    out = get_row(applicant_id, cyc)
    assert out is not None
    return out


def evaluate_all(*, cycle: str | None = None) -> dict[str, int]:
    """Evaluate every live conditional offer. Returns outcome counts."""
    counts: dict[str, int] = {}
    for a in conditional_applicants():
        try:
            row = evaluate_applicant(a.applicant_id, cycle=cycle)
            counts[row.outcome] = counts.get(row.outcome, 0) + 1
        except Exception:  # noqa: BLE001 — one bad record must not stop the run
            logger.exception("Results day: evaluation failed for %s",
                             a.applicant_id)
            counts["Error"] = counts.get("Error", 0) + 1
    logger.info("Results day evaluation: %s", counts)
    return counts


# ── Decisions ──────────────────────────────────────────────────────

def _record_decision(applicant_id: str, decision: str, *, cycle: str | None,
                     by: str | None, notes: str | None,
                     alternative: str | None = None) -> ResultsDayRow:
    init_db()
    cyc = cycle or current_cycle()
    if get_row(applicant_id, cyc) is None:
        evaluate_applicant(applicant_id, cycle=cyc)
    with _connect() as conn:
        conn.execute(
            """UPDATE admissions_results_day SET decision = ?,
                   alternative = ?, decided_by = ?,
                   decided_at = datetime('now'), notes = ?
               WHERE applicant_id = ? AND cycle = ?""",
            (decision, alternative, by, (notes or "").strip() or None,
             applicant_id, cyc))
        _adm._log_event(conn, applicant_id,
                        f"Results day decision: {decision}"
                        + (f" — {alternative}" if alternative else "")
                        + (f" (by {by})" if by else ""), kind="offer")
        conn.commit()
    out = get_row(applicant_id, cyc)
    assert out is not None
    return out


def confirm(applicant_id: str, *, by: str | None = None,
            notes: str | None = None, allow_near_miss: bool = False,
            cycle: str | None = None) -> ResultsDayRow:
    """Confirm the place: the conditional offer becomes unconditional.

    A near miss needs ``allow_near_miss``; a "Not met" or "Pending"
    outcome is refused (offer an alternative, decline, or record the
    missing results first).
    """
    a = _live_offer(applicant_id, "confirm their place")
    row = evaluate_applicant(applicant_id, cycle=cycle)
    if row.outcome == "Near miss" and not allow_near_miss:
        raise ValidationError(
            "Conditions were narrowly missed — confirm as a near miss, "
            "offer an alternative or decline")
    if row.outcome not in ("Met", "Near miss"):
        raise ValidationError(
            f"Conditions are '{row.outcome}' — cannot confirm the place")
    _adm.update_applicant(applicant_id, {
        "offer_type": "Unconditional",
        "decision_by": by or a.decision_by,
        "decision_date": _dt.date.today().isoformat(),
    })
    decision = ("Confirmed (near miss)" if row.outcome == "Near miss"
                else "Confirmed")
    return _record_decision(applicant_id, decision, cycle=cycle, by=by,
                            notes=notes)


def decline(applicant_id: str, *, by: str | None = None,
            notes: str | None = None, cycle: str | None = None
            ) -> ResultsDayRow:
    """Withdraw the offer because the conditions were not met."""
    _live_offer(applicant_id, "decline their offer")
    if get_row(applicant_id, cycle) is None:
        evaluate_applicant(applicant_id, cycle=cycle)
    _adm.record_decision(applicant_id, "Rejected",
                         reason="Offer conditions not met", decided_by=by,
                         notes=notes or "Offer conditions not met on GCSE "
                                        "results day")
    return _record_decision(applicant_id, "Declined", cycle=cycle, by=by,
                            notes=notes)


def offer_alternative(applicant_id: str, *, choices: list[Any],
                      by: str | None = None, notes: str | None = None,
                      cycle: str | None = None) -> ResultsDayRow:
    """Offer a different programme instead of the original one.

    ``choices`` replaces the applicant's programme choices (same shape
    as :func:`admissions.set_programme_choices`). The new offer is
    unconditional — it is made on the results already in hand — and
    the applicant has to accept it, so the status returns to Offer Made.
    """
    _live_offer(applicant_id, "offer an alternative programme")
    if not choices:
        raise ValidationError("Choose at least one alternative programme")
    if get_row(applicant_id, cycle) is None:
        evaluate_applicant(applicant_id, cycle=cycle)
    new = _adm.set_programme_choices(applicant_id, choices)
    label = ", ".join(c.label for c in new)
    _adm.make_offer(applicant_id, offer_type="Unconditional",
                    conditions=None, decided_by=by)
    return _record_decision(applicant_id, "Alternative offered",
                            cycle=cycle, by=by, notes=notes,
                            alternative=label)


def reset_decision(applicant_id: str, *, cycle: str | None = None) -> None:
    """Undo the results-day decision record (not the applicant change)."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "UPDATE admissions_results_day SET decision = 'Pending', "
            "alternative = NULL, decided_by = NULL, decided_at = NULL "
            "WHERE applicant_id = ? AND cycle = ?",
            (applicant_id, cycle or current_cycle()))
        _adm._log_event(conn, applicant_id, "Results day decision reset",
                        kind="offer")
        conn.commit()


# ── Dashboard ──────────────────────────────────────────────────────

def dashboard(*, cycle: str | None = None) -> Dashboard:
    """Counts and rows for the results-day screen.

    Rows cover every applicant evaluated this cycle plus every live
    conditional offer not yet evaluated (shown as awaiting results).
    """
    init_db()
    cyc = cycle or current_cycle()
    with _connect() as conn:
        stored = {r["applicant_id"]: _row(r) for r in conn.execute(
            "SELECT * FROM admissions_results_day WHERE cycle = ?",
            (cyc,)).fetchall()}
    rows: list[ResultsDayRow] = list(stored.values())
    for a in conditional_applicants():
        if a.applicant_id not in stored:
            rows.append(ResultsDayRow(
                applicant_id=a.applicant_id, cycle=cyc, outcome="Pending",
                outcome_detail="Not yet evaluated", evaluated_at=None,
                decision="Pending", alternative=None, decided_by=None,
                decided_at=None, notes=None))
    by_outcome = {o: 0 for o in ("Met", "Near miss", "Not met", "Pending")}
    by_decision = {d: 0 for d in DECISIONS}
    awaiting_results = awaiting_decision = 0
    out_rows: list[ResultsDayRow] = []
    for r in rows:
        a = _adm.get_applicant(r.applicant_id)
        if a is None:
            continue
        r.applicant_name, r.status = a.full_name, a.status
        r.conditions = a.offer_conditions or ""
        by_outcome[r.outcome] = by_outcome.get(r.outcome, 0) + 1
        by_decision[r.decision] = by_decision.get(r.decision, 0) + 1
        if not _er.list_gcses(r.applicant_id, result_type="Actual"):
            awaiting_results += 1
        elif r.decision == "Pending":
            awaiting_decision += 1
        out_rows.append(r)
    order = {"Near miss": 0, "Not met": 1, "Pending": 2, "Met": 3}
    out_rows.sort(key=lambda r: (r.decision != "Pending",
                                 order.get(r.outcome, 9), r.applicant_name))
    return Dashboard(cycle=cyc, total=len(out_rows), by_outcome=by_outcome,
                     by_decision=by_decision,
                     awaiting_results=awaiting_results,
                     awaiting_decision=awaiting_decision, rows=out_rows)
