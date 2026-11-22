"""Bursary payment store: schedules, payment runs, attendance holds,
the 16-19 vulnerable bursary, evidence checks and discretionary policy
rules.

Split out of :mod:`bursaries` (which re-exports every public name here,
so ``bursaries.payment_run`` etc. keep working). The schema for these
tables is created by ``bursaries._extend_schema`` / ``ensure_store``;
everything here takes an optional ``db_path`` — production callers leave
it out, the attendance rule layer passes its own ``DB_PATH``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Any

from education_system.systems.sixth_form.domains.finance.domain.bursaries.bursaries import (
    APPROVED_STATUSES,
    Application,
    BURSARY_TYPES,
    CURRENCY_SYMBOL,
    DECISION_HOLD,
    DECISION_PAY,
    DEFAULT_DISBURSEMENT_METHOD,
    DEFAULT_FREQUENCY,
    DISBURSEMENT_METHODS,
    DISCRETIONARY_TYPE,
    ELIGIBILITY_BASES,
    EVIDENCE_TYPES,
    INSTALMENT_CANCELLED,
    INSTALMENT_FORFEITED,
    INSTALMENT_HELD,
    INSTALMENT_PAID,
    INSTALMENT_PENDING,
    INSTALMENT_RELEASED,
    INSTALMENT_STATES,
    PAYMENT_FREQUENCIES,
    TERMS,
    VULNERABLE_CATEGORIES,
    VULNERABLE_MAX_AWARD,
    VULNERABLE_TYPE,
    ValidationError,
    _VULNERABLE_BASIS,
    _connect,
    _require,
    _row_app,
    _table_exists,
    _validate_amount,
    _validate_date,
    create_application,
    ensure_store,
    get_application,
    init_db,
    logger,
    update_application,
)
from education_system.systems.sixth_form.infrastructure import database as db


# ── Dataclasses ────────────────────────────────────────────────────

@dataclass
class Instalment:
    """One scheduled bursary payment and what happened to it."""

    instalment_id: int
    application_id: int
    student_id: str
    period_from: str
    period_to: str
    due_date: str
    amount: float
    state: str
    attendance_pct: float | None
    threshold_pct: float | None
    decision: str | None
    decided_by: str | None
    decided_at: str | None
    released_by: str | None
    released_at: str | None
    disbursement_id: int | None
    note: str | None
    created_at: str | None

    @property
    def is_open(self) -> bool:
        return self.state in (INSTALMENT_PENDING, INSTALMENT_HELD)


@dataclass
class DueItem:
    """A payment run's recommendation for one instalment. Nothing done yet."""

    instalment: Instalment
    student_name: str
    bursary_type: str
    decision: str
    reason: str
    attendance_pct: float | None
    threshold_pct: float | None
    exempt: bool = False

    @property
    def would_hold(self) -> bool:
        return self.decision == DECISION_HOLD


@dataclass
class PaymentRun:
    as_of: str
    items: list[DueItem]

    @property
    def to_pay(self) -> list[DueItem]:
        return [i for i in self.items if i.decision == DECISION_PAY]

    @property
    def to_hold(self) -> list[DueItem]:
        return [i for i in self.items if i.decision == DECISION_HOLD]

    @property
    def total_payable(self) -> float:
        return round(sum(i.instalment.amount for i in self.to_pay), 2)

    @property
    def total_held(self) -> float:
        return round(sum(i.instalment.amount for i in self.to_hold), 2)

    @property
    def summary(self) -> str:
        return (f"{len(self.to_pay)} to pay "
                f"({CURRENCY_SYMBOL}{self.total_payable:.2f}), "
                f"{len(self.to_hold)} to hold "
                f"({CURRENCY_SYMBOL}{self.total_held:.2f})")


@dataclass
class PolicyRule:
    rule_id: int
    name: str
    academic_year: str | None
    bursary_type: str
    eligibility_basis: str | None
    max_household_income: float | None
    min_household_size: int | None
    award_amount: float
    payment_frequency: str
    attendance_conditional: bool
    requires_evidence: bool
    priority: int
    active: bool
    notes: str | None


@dataclass
class PolicyDecision:
    application_id: int
    eligible: bool
    amount: float | None
    rule: PolicyRule | None
    reasons: list[str]


def _row_inst(r: db.Row) -> Instalment:
    return Instalment(
        instalment_id=r["instalment_id"], application_id=r["application_id"],
        student_id=r["student_id"], period_from=r["period_from"],
        period_to=r["period_to"], due_date=r["due_date"],
        amount=r["amount"], state=r["state"],
        attendance_pct=r["attendance_pct"], threshold_pct=r["threshold_pct"],
        decision=r["decision"], decided_by=r["decided_by"],
        decided_at=r["decided_at"], released_by=r["released_by"],
        released_at=r["released_at"], disbursement_id=r["disbursement_id"],
        note=r["note"], created_at=r["created_at"])


def _row_rule(r: db.Row) -> PolicyRule:
    return PolicyRule(
        rule_id=r["rule_id"], name=r["name"],
        academic_year=r["academic_year"], bursary_type=r["bursary_type"],
        eligibility_basis=r["eligibility_basis"],
        max_household_income=r["max_household_income"],
        min_household_size=r["min_household_size"],
        award_amount=r["award_amount"],
        payment_frequency=r["payment_frequency"],
        attendance_conditional=bool(r["attendance_conditional"]),
        requires_evidence=bool(r["requires_evidence"]),
        priority=r["priority"], active=bool(r["active"]), notes=r["notes"])


# ── Schedule periods ───────────────────────────────────────────────

def _year_end_for(start: str) -> str:
    from education_system.systems.sixth_form.domains.finance.domain import (
        finance_calendar as fc,
    )
    return fc.teaching_end(fc.academic_year_for(start))


def schedule_periods(frequency: str, start: str,
                     end: str) -> list[tuple[str, str]]:
    """The (from, to) periods a schedule pays over, in order.

    Weekly / fortnightly periods step from the start date; monthly ones
    follow calendar months; termly ones follow :data:`TERMS`. Every
    period is clipped to [start, end].
    """
    import datetime as _dt
    if frequency not in PAYMENT_FREQUENCIES:
        raise ValidationError(
            f"Frequency must be one of: {', '.join(PAYMENT_FREQUENCIES)}")
    s = _dt.date.fromisoformat(start)
    e = _dt.date.fromisoformat(end)
    if e < s:
        raise ValidationError("A schedule cannot end before it starts")
    out: list[tuple[str, str]] = []
    if frequency == "One-off":
        return [(start, start)]
    if frequency in ("Weekly", "Fortnightly"):
        step = 7 if frequency == "Weekly" else 14
        d = s
        while d <= e:
            last = min(e, d + _dt.timedelta(days=step - 1))
            out.append((d.isoformat(), last.isoformat()))
            d = last + _dt.timedelta(days=1)
        return out
    if frequency == "Monthly":
        import calendar as _cal
        d = s
        while d <= e:
            month_end = _dt.date(d.year, d.month,
                                 _cal.monthrange(d.year, d.month)[1])
            last = min(e, month_end)
            out.append((d.isoformat(), last.isoformat()))
            d = last + _dt.timedelta(days=1)
        return out
    # Termly.
    for year in range(s.year - 1, e.year + 1):
        for _name, (sm, sd), (em, ed) in TERMS:
            # Autumn belongs to the calendar year it starts in; spring
            # and summer to the following one.
            y = year if sm >= 9 else year + 1
            t_from = _dt.date(y, sm, sd)
            t_to = _dt.date(y, em, ed)
            lo, hi = max(t_from, s), min(t_to, e)
            if lo <= hi:
                out.append((lo.isoformat(), hi.isoformat()))
    out.sort()
    return out


def _split_amounts(total: float, n: int,
                   instalment: float | None) -> list[float]:
    if n <= 0:
        return []
    if instalment:
        out: list[float] = []
        left = round(total, 2)
        for _ in range(n):
            amt = round(min(instalment, max(0.0, left)), 2)
            out.append(amt)
            left = round(left - amt, 2)
        return out
    each = round(total / n, 2)
    out = [each] * n
    out[-1] = round(total - each * (n - 1), 2)
    return out


def _app_at(conn: db.Connection, application_id: int) -> Application | None:
    r = conn.execute(
        "SELECT * FROM bursary_applications WHERE application_id = ?",
        (application_id,)).fetchone()
    return _row_app(r) if r else None


def _inst_at(conn: db.Connection, instalment_id: int) -> Instalment | None:
    r = conn.execute(
        "SELECT * FROM bursary_schedule WHERE instalment_id = ?",
        (instalment_id,)).fetchone()
    return _row_inst(r) if r else None


def _roll_status_conn(conn: db.Connection, application_id: int) -> None:
    """:func:`_auto_roll_status` on an open connection."""
    app = _app_at(conn, application_id)
    if app is None or not app.is_approved or app.amount_awarded is None:
        return
    paid = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM bursary_disbursements "
        "WHERE application_id = ? AND status = 'Paid'",
        (application_id,)).fetchone()[0])
    if paid <= 0:
        new = "Approved"
    elif paid >= app.amount_awarded - 0.001:
        new = "Paid in Full"
    else:
        new = "Partially Paid"
    if new != app.status:
        conn.execute(
            "UPDATE bursary_applications SET status=?, "
            "updated_at=datetime('now') WHERE application_id=?",
            (new, application_id))


def set_payment_schedule(
    application_id: int,
    *,
    frequency: str = DEFAULT_FREQUENCY,
    start: str | None = None,
    end: str | None = None,
    instalment_amount: float | None = None,
    attendance_conditional: bool = True,
    generate: bool = True,
) -> list[Instalment]:
    """Set how an approved award is paid, and (by default) build its
    instalments. Returns the instalments created."""
    init_db()
    app = get_application(application_id)
    if app is None:
        raise ValidationError(f"No application #{application_id}")
    if frequency not in PAYMENT_FREQUENCIES:
        raise ValidationError(
            f"Frequency must be one of: {', '.join(PAYMENT_FREQUENCIES)}")
    from education_system.systems.sixth_form.domains.finance.domain import (
        finance_calendar as fc,
    )
    if not start:
        if app.academic_year:
            try:
                start = max(fc.year_bounds(app.academic_year)[0],
                            app.application_date)
            except ValueError:
                start = app.application_date
        else:
            start = app.application_date
    start = _validate_date(start, "Schedule start", required=True)
    end = _validate_date(end, "Schedule end") or _year_end_for(start)
    if end < start:
        raise ValidationError("Schedule end cannot be before its start")
    inst = _validate_amount(instalment_amount, "Instalment amount")
    if app.vulnerable_category or app.bursary_type == VULNERABLE_TYPE:
        # A statutory entitlement is never conditional on attendance.
        attendance_conditional = False
    with _connect() as conn:
        conn.execute(
            """UPDATE bursary_applications SET payment_frequency=?,
                   schedule_start=?, schedule_end=?, instalment_amount=?,
                   attendance_conditional=?, active=1,
                   updated_at=datetime('now')
               WHERE application_id=?""",
            (frequency, start, end, inst, 1 if attendance_conditional else 0,
             application_id))
        conn.commit()
    return generate_schedule(application_id) if generate else []


def generate_schedule(application_id: int, *, regenerate: bool = False,
                      db_path: Any = None) -> list[Instalment]:
    """Create the Pending instalments for an approved award.

    Idempotent: periods that already have an instalment are left alone.
    ``regenerate`` first drops instalments nobody has decided on yet
    (state Pending, no decision), e.g. after the award changed.
    """
    ensure_store(db_path)
    with _connect(db_path) as conn:
        app = _app_at(conn, application_id)
        if app is None:
            raise ValidationError(f"No application #{application_id}")
        if not app.is_approved or app.amount_awarded is None:
            raise ValidationError(
                "Only an approved award with an amount can be scheduled")
        if not app.payment_frequency:
            raise ValidationError(
                "Set a payment frequency for this award first")
        start = app.schedule_start or app.application_date
        end = app.schedule_end or _year_end_for(start)
        if regenerate:
            conn.execute(
                "DELETE FROM bursary_schedule WHERE application_id = ? "
                "AND state = 'Pending' AND decision IS NULL",
                (application_id,))
        existing = {(r["period_from"], r["period_to"]) for r in conn.execute(
            "SELECT period_from, period_to FROM bursary_schedule "
            "WHERE application_id = ?", (application_id,))}
        committed = float(conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM bursary_schedule "
            "WHERE application_id = ? AND state <> 'Cancelled'",
            (application_id,)).fetchone()[0])
        periods = [p for p in schedule_periods(app.payment_frequency,
                                               start, end)
                   if p not in existing]
        left = round(app.amount_awarded - committed, 2)
        if not periods or left <= 0:
            return []
        amounts = _split_amounts(left, len(periods), app.instalment_amount)
        new_ids: list[int] = []
        for (p_from, p_to), amount in zip(periods, amounts):
            if amount <= 0:
                continue
            cur = conn.execute(
                """INSERT INTO bursary_schedule
                       (application_id, student_id, period_from, period_to,
                        due_date, amount, state)
                   VALUES (?, ?, ?, ?, ?, ?, 'Pending')""",
                (application_id, app.student_id, p_from, p_to, p_to, amount))
            new_ids.append(int(cur.lastrowid))
        conn.commit()
        out = [i for i in (_inst_at(conn, n) for n in new_ids) if i]
    logger.info("Scheduled %d instalment(s) for bursary #%d",
                len(out), application_id)
    return out


def get_instalment(instalment_id: int, *, db_path: Any = None
                   ) -> Instalment | None:
    ensure_store(db_path)
    with _connect(db_path) as conn:
        return _inst_at(conn, instalment_id)


def list_instalments(
    *,
    application_id: int | None = None,
    student_id: str | None = None,
    state: str | None = None,
    period_from: str | None = None,
    due_by: str | None = None,
    decided_only: bool = False,
    limit: int = 2000,
    db_path: Any = None,
) -> list[Instalment]:
    ensure_store(db_path)
    clauses: list[str] = []
    args: list[Any] = []
    if application_id is not None:
        clauses.append("application_id = ?")
        args.append(application_id)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if state:
        if state not in INSTALMENT_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(INSTALMENT_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    if period_from:
        clauses.append("period_from = ?")
        args.append(_validate_date(period_from, "Period from"))
    if due_by:
        clauses.append("due_date <= ?")
        args.append(_validate_date(due_by, "Due by"))
    if decided_only:
        clauses.append("decision IS NOT NULL")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM bursary_schedule {where} "
            "ORDER BY period_from DESC, student_id, instalment_id LIMIT ?",
            args).fetchall()
    return [_row_inst(r) for r in rows]


def _pay_instalment(conn: db.Connection, inst: Instalment, *,
                    by: str, method: str | None = None,
                    paid_on: str | None = None) -> int | None:
    """Write the disbursement for an instalment. Returns its id (None for
    a zero-value instalment). Open-ended awards (no schedule end) grow
    their awarded total to fit; capped awards refuse to overpay."""
    if inst.amount <= 0:
        return None
    app = _app_at(conn, inst.application_id)
    if app is None:
        raise ValidationError(f"No application #{inst.application_id}")
    paid = float(conn.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM bursary_disbursements "
        "WHERE application_id = ? AND status = 'Paid'",
        (inst.application_id,)).fetchone()[0])
    awarded = app.amount_awarded or 0.0
    if round(paid + inst.amount, 2) > awarded + 0.001:
        if app.schedule_end:
            raise ValidationError(
                f"Paying {CURRENCY_SYMBOL}{inst.amount:.2f} would take award "
                f"#{app.application_id} past its {CURRENCY_SYMBOL}"
                f"{awarded:.2f} total — increase the award first")
        conn.execute(
            "UPDATE bursary_applications SET amount_awarded = ?, "
            "updated_at = datetime('now') WHERE application_id = ?",
            (round(paid + inst.amount, 2), app.application_id))
        logger.info("Open-ended bursary #%d grown to %.2f",
                    app.application_id, paid + inst.amount)
    method = method or DEFAULT_DISBURSEMENT_METHOD
    if method not in DISBURSEMENT_METHODS:
        raise ValidationError(
            f"Method must be one of: {', '.join(DISBURSEMENT_METHODS)}")
    cur = conn.execute(
        """INSERT INTO bursary_disbursements
               (application_id, amount, paid_on, method, status, reference,
                recorded_by, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'Paid', ?, ?, ?, datetime('now'),
                   datetime('now'))""",
        (inst.application_id, inst.amount,
         paid_on or _date.today().isoformat(), method,
         f"Instalment #{inst.instalment_id}",
         (by or "").strip() or None,
         f"Bursary instalment {inst.period_from} to {inst.period_to}"))
    return int(cur.lastrowid)


def _reverse_disbursement(conn: db.Connection,
                          disbursement_id: int | None, why: str) -> None:
    if not disbursement_id:
        return
    conn.execute(
        "UPDATE bursary_disbursements SET status='Reversed', "
        "notes = COALESCE(notes || ' | ', '') || ?, "
        "updated_at=datetime('now') WHERE disbursement_id = ?",
        (why, disbursement_id))


def _decide(conn: db.Connection, inst: Instalment, *, decision: str,
            decided_by: str, attendance_pct: float | None,
            threshold_pct: float | None, note: str | None,
            method: str | None) -> None:
    if decision not in (DECISION_PAY, DECISION_HOLD):
        raise ValidationError("Decision must be Pay or Hold")
    if inst.state in (INSTALMENT_FORFEITED, INSTALMENT_CANCELLED):
        raise ValidationError(
            f"Instalment #{inst.instalment_id} is {inst.state.lower()}")
    already_paid = inst.state in (INSTALMENT_PAID, INSTALMENT_RELEASED)
    disb_id = inst.disbursement_id
    if decision == DECISION_PAY:
        state = INSTALMENT_PAID if inst.state != INSTALMENT_RELEASED \
            else INSTALMENT_RELEASED
        if not already_paid:
            disb_id = _pay_instalment(conn, inst, by=decided_by,
                                      method=method)
    else:
        state = INSTALMENT_HELD
        if already_paid:
            _reverse_disbursement(conn, disb_id,
                                  f"Held on review by {decided_by}")
            disb_id = None
    conn.execute(
        """UPDATE bursary_schedule SET decision=?, state=?,
               attendance_pct=?, threshold_pct=COALESCE(?, threshold_pct),
               decided_by=?, decided_at=datetime('now'),
               disbursement_id=?, note=COALESCE(?, note),
               updated_at=datetime('now')
           WHERE instalment_id=?""",
        (decision, state, attendance_pct, threshold_pct, decided_by,
         disb_id, (note or "").strip() or None, inst.instalment_id))
    _roll_status_conn(conn, inst.application_id)


def decide_instalment(
    instalment_id: int,
    *,
    decision: str,
    decided_by: str,
    attendance_pct: float | None = None,
    threshold_pct: float | None = None,
    note: str | None = None,
    method: str | None = None,
    db_path: Any = None,
) -> Instalment:
    """Pay or hold one instalment. Paying writes the disbursement."""
    if not (decided_by or "").strip():
        raise ValidationError("A bursary decision must name who made it")
    ensure_store(db_path)
    with _connect(db_path) as conn:
        inst = _inst_at(conn, instalment_id)
        if inst is None:
            raise ValidationError(f"No instalment #{instalment_id}")
        _decide(conn, inst, decision=decision, decided_by=decided_by.strip(),
                attendance_pct=attendance_pct, threshold_pct=threshold_pct,
                note=note, method=method)
        conn.commit()
        out = _inst_at(conn, instalment_id)
    assert out is not None
    return out


def record_period_decision(
    application_id: int,
    *,
    period_from: str,
    period_to: str,
    amount: float,
    decision: str,
    decided_by: str,
    attendance_pct: float | None = None,
    threshold_pct: float | None = None,
    note: str | None = None,
    db_path: Any = None,
) -> Instalment:
    """Decide the instalment for an arbitrary period, creating it first
    if the award has none for exactly that period. Used by the attendance
    layer's fortnightly runs; deciding twice updates, never duplicates."""
    if not (decided_by or "").strip():
        raise ValidationError("A bursary decision must name who made it")
    ensure_store(db_path)
    with _connect(db_path) as conn:
        app = _app_at(conn, application_id)
        if app is None:
            raise ValidationError(f"No award #{application_id}")
        r = conn.execute(
            "SELECT instalment_id FROM bursary_schedule WHERE "
            "application_id = ? AND period_from = ? AND period_to = ?",
            (application_id, period_from, period_to)).fetchone()
        if r is None:
            cur = conn.execute(
                """INSERT INTO bursary_schedule
                       (application_id, student_id, period_from, period_to,
                        due_date, amount, state)
                   VALUES (?, ?, ?, ?, ?, ?, 'Pending')""",
                (application_id, app.student_id, period_from, period_to,
                 period_to, round(float(amount), 2)))
            iid = int(cur.lastrowid)
        else:
            iid = int(r["instalment_id"])
        inst = _inst_at(conn, iid)
        assert inst is not None
        _decide(conn, inst, decision=decision, decided_by=decided_by.strip(),
                attendance_pct=attendance_pct, threshold_pct=threshold_pct,
                note=note, method=None)
        conn.commit()
        out = _inst_at(conn, iid)
    assert out is not None
    return out


def release_instalment(instalment_id: int, *, released_by: str,
                       note: str | None = None,
                       db_path: Any = None) -> Instalment:
    """Pay a held instalment (attendance recovered, or somebody decided)."""
    ensure_store(db_path)
    with _connect(db_path) as conn:
        inst = _inst_at(conn, instalment_id)
        if inst is None:
            raise ValidationError(f"No payment with id {instalment_id}")
        if inst.state != INSTALMENT_HELD:
            raise ValidationError(
                f"Payment #{instalment_id} is {inst.state.lower()}, "
                "not held")
        if not (released_by or "").strip():
            raise ValidationError("A release must name who authorised it")
        disb_id = _pay_instalment(conn, inst, by=released_by)
        conn.execute(
            """UPDATE bursary_schedule SET state=?, released_by=?,
                   released_at=datetime('now'), disbursement_id=?,
                   note=COALESCE(?, note), updated_at=datetime('now')
               WHERE instalment_id=?""",
            (INSTALMENT_RELEASED, released_by.strip(), disb_id,
             (note or "").strip() or None, instalment_id))
        _roll_status_conn(conn, inst.application_id)
        conn.commit()
        out = _inst_at(conn, instalment_id)
    assert out is not None
    logger.info("Bursary instalment #%d released by %s", instalment_id,
                released_by)
    return out


def forfeit_instalment(instalment_id: int, *, reason: str, by: str,
                       db_path: Any = None) -> Instalment:
    """Write a held instalment off. Needs a reason and a named person."""
    ensure_store(db_path)
    with _connect(db_path) as conn:
        inst = _inst_at(conn, instalment_id)
        if inst is None:
            raise ValidationError(f"No payment with id {instalment_id}")
        if inst.state != INSTALMENT_HELD:
            raise ValidationError("Only a held payment can be forfeited")
        if not (reason or "").strip() or not (by or "").strip():
            raise ValidationError(
                "Forfeiting a bursary payment needs a reason and a named "
                "person")
        conn.execute(
            "UPDATE bursary_schedule SET state=?, note=?, released_by=?, "
            "updated_at=datetime('now') WHERE instalment_id=?",
            (INSTALMENT_FORFEITED, reason.strip(), by.strip(), instalment_id))
        conn.commit()
        out = _inst_at(conn, instalment_id)
    assert out is not None
    return out


def cancel_instalment(instalment_id: int, *, reason: str, by: str) -> Instalment:
    """Cancel a Pending instalment (award ended, learner left)."""
    init_db()
    if not (reason or "").strip() or not (by or "").strip():
        raise ValidationError("Cancelling needs a reason and a named person")
    with _connect() as conn:
        inst = _inst_at(conn, instalment_id)
        if inst is None:
            raise ValidationError(f"No instalment #{instalment_id}")
        if inst.state != INSTALMENT_PENDING:
            raise ValidationError("Only a pending instalment can be cancelled")
        conn.execute(
            "UPDATE bursary_schedule SET state='Cancelled', note=?, "
            "decided_by=?, updated_at=datetime('now') WHERE instalment_id=?",
            (reason.strip(), by.strip(), instalment_id))
        conn.commit()
        out = _inst_at(conn, instalment_id)
    assert out is not None
    return out


# ── Payment runs ───────────────────────────────────────────────────

def payment_run(as_of: str | None = None, *,
                threshold_pct: float | None = None,
                application_id: int | None = None) -> PaymentRun:
    """Every Pending instalment due on or before *as_of*, each with a
    Pay / Hold recommendation from the attendance rules. Writes nothing.
    """
    init_db()
    as_of = _validate_date(as_of or _date.today().isoformat(), "As of",
                           required=True)
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_bursary as rules,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    names = {s.student_id: s.full_name for s in _students.list_students()}
    items: list[DueItem] = []
    pending = list_instalments(state=INSTALMENT_PENDING, due_by=as_of,
                               application_id=application_id, limit=100000)
    apps: dict[int, Application | None] = {}
    for inst in sorted(pending, key=lambda i: (i.due_date, i.student_id)):
        if inst.application_id not in apps:
            apps[inst.application_id] = get_application(inst.application_id)
        app = apps[inst.application_id]
        if app is None or not app.is_approved or not app.active:
            continue
        linked = (app.attendance_conditional
                  and rules.attendance_linked_type(app.bursary_type))
        decision, reason, pct, threshold, exempt = rules.evaluate_attendance(
            inst.student_id, attendance_linked=linked,
            period_from=inst.period_from, period_to=inst.period_to,
            threshold_pct=threshold_pct, label=app.bursary_type)
        items.append(DueItem(
            instalment=inst, student_name=names.get(inst.student_id, "?"),
            bursary_type=app.bursary_type,
            decision=DECISION_HOLD if decision == rules.HOLD else DECISION_PAY,
            reason=reason, attendance_pct=pct, threshold_pct=threshold,
            exempt=exempt))
    items.sort(key=lambda i: (i.decision != DECISION_HOLD,
                              i.instalment.due_date))
    run = PaymentRun(as_of=as_of, items=items)
    logger.info("Bursary payment run to %s: %s", as_of, run.summary)
    return run


def commit_run(run: PaymentRun, *, decided_by: str, pay_only: bool = False,
               method: str | None = None,
               overrides: dict[int, str] | None = None) -> dict[str, int]:
    """Commit a payment run. ``pay_only`` pays and leaves holds for
    individual review; ``overrides`` maps instalment id -> Pay/Hold."""
    if not (decided_by or "").strip():
        raise ValidationError("A payment run must name who committed it")
    overrides = overrides or {}
    counts = {DECISION_PAY: 0, DECISION_HOLD: 0, "skipped": 0}
    for item in run.items:
        decision = overrides.get(item.instalment.instalment_id, item.decision)
        if pay_only and decision == DECISION_HOLD:
            counts["skipped"] += 1
            continue
        decide_instalment(
            item.instalment.instalment_id, decision=decision,
            decided_by=decided_by, attendance_pct=item.attendance_pct,
            threshold_pct=item.threshold_pct,
            note=(item.reason if decision == item.decision
                  else f"Override of '{item.reason}' by {decided_by}"),
            method=method)
        counts[decision] += 1
    logger.info("Bursary run committed by %s: %s", decided_by, counts)
    return counts


def held_instalments() -> list[Instalment]:
    return list_instalments(state=INSTALMENT_HELD, limit=100000)


def release_on_recovery(*, date_from: str, date_to: str, released_by: str,
                        threshold_pct: float | None = None) -> list[Instalment]:
    """Release every held instalment whose learner's attendance over the
    given window now meets the threshold."""
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_bursary as rules,
    )
    out = rules.release_on_recovery(date_from=date_from, date_to=date_to,
                                    released_by=released_by,
                                    threshold_pct=threshold_pct)
    return [i for i in (get_instalment(p.payment_id) for p in out) if i]


@dataclass
class ScheduleSummary:
    pending: int
    pending_value: float
    due_now: int
    due_now_value: float
    held: int
    held_value: float
    paid_value: float
    released_value: float
    forfeited_value: float


def schedule_summary(as_of: str | None = None) -> ScheduleSummary:
    init_db()
    as_of = as_of or _date.today().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT state, due_date, amount FROM bursary_schedule").fetchall()
    def tot(pred) -> tuple[int, float]:
        sel = [r for r in rows if pred(r)]
        return len(sel), round(sum(r["amount"] for r in sel), 2)
    p_n, p_v = tot(lambda r: r["state"] == INSTALMENT_PENDING)
    d_n, d_v = tot(lambda r: r["state"] == INSTALMENT_PENDING
                   and r["due_date"] <= as_of)
    h_n, h_v = tot(lambda r: r["state"] == INSTALMENT_HELD)
    return ScheduleSummary(
        pending=p_n, pending_value=p_v, due_now=d_n, due_now_value=d_v,
        held=h_n, held_value=h_v,
        paid_value=tot(lambda r: r["state"] == INSTALMENT_PAID)[1],
        released_value=tot(lambda r: r["state"] == INSTALMENT_RELEASED)[1],
        forfeited_value=tot(lambda r: r["state"] == INSTALMENT_FORFEITED)[1])


# ── Awards made by the attendance layer ────────────────────────────

def create_scheduled_award(
    student_id: str,
    *,
    amount: float,
    bursary_type: str = DISCRETIONARY_TYPE,
    frequency: str = "Fortnightly",
    start: str | None = None,
    end: str | None = None,
    attendance_conditional: bool = True,
    notes: str | None = None,
    db_path: Any = None,
) -> Application:
    """Record an approved, scheduled award directly (no application
    stage). *amount* is the per-instalment amount; the awarded total is
    that times the number of periods to *end* (or the end of the
    teaching year). The caller has already checked the learner exists.
    """
    ensure_store(db_path)
    if bursary_type not in BURSARY_TYPES:
        raise ValidationError(
            f"Bursary type must be one of: {', '.join(BURSARY_TYPES)}")
    if frequency not in PAYMENT_FREQUENCIES:
        frequency = "Fortnightly"
    value = round(float(amount), 2)
    today = _date.today().isoformat()
    span_from = start or today
    span_to = end or _year_end_for(span_from)
    try:
        n = max(1, len(schedule_periods(frequency, span_from, span_to)))
    except ValidationError:
        n = 1
    total = round(value * n, 2)
    with _connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO bursary_applications
                   (student_id, bursary_type, academic_year,
                    application_date, amount_requested, amount_awarded,
                    status, evidence_received, notes, assessed_on,
                    payment_frequency, instalment_amount, schedule_start,
                    schedule_end, attendance_conditional, active,
                    run_driven, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'Approved', 0, ?, ?, ?, ?, ?, ?, ?,
                       1, 1, datetime('now'), datetime('now'))""",
            (student_id, bursary_type, _academic_year_of(span_from),
             start or today, total, total, (notes or "").strip() or None,
             today, frequency, value, start, end,
             1 if attendance_conditional else 0))
        conn.commit()
        new_id = int(cur.lastrowid)
        out = _app_at(conn, new_id)
    assert out is not None
    logger.info("Scheduled bursary award #%d for %s (%s, %s%.2f %s)",
                new_id, student_id, bursary_type, CURRENCY_SYMBOL, value,
                frequency)
    return out


def _academic_year_of(d: str) -> str:
    from education_system.systems.sixth_form.domains.finance.domain import (
        finance_calendar as fc,
    )
    return fc.academic_year_for(d)


def get_award_at(application_id: int, *, db_path: Any = None
                 ) -> Application | None:
    ensure_store(db_path)
    with _connect(db_path) as conn:
        return _app_at(conn, application_id)


def list_scheduled_awards(*, student_id: str | None = None,
                          active_only: bool = True,
                          bursary_types: tuple[str, ...] | None = None,
                          run_driven: bool | None = None,
                          limit: int = 500,
                          db_path: Any = None) -> list[Application]:
    """Approved awards that are paid on a schedule. ``run_driven``
    narrows to the attendance layer's period-by-period awards (True) or
    to schedule-driven ones (False)."""
    ensure_store(db_path)
    clauses = ["payment_frequency IS NOT NULL"]
    args: list[Any] = []
    ph = ",".join("?" * len(APPROVED_STATUSES))
    clauses.append(f"status IN ({ph})")
    args.extend(APPROVED_STATUSES)
    if active_only:
        clauses.append("active = 1")
    if run_driven is not None:
        clauses.append("run_driven = ?")
        args.append(1 if run_driven else 0)
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if bursary_types:
        clauses.append(f"bursary_type IN ({','.join('?' * len(bursary_types))})")
        args.extend(bursary_types)
    args.append(max(1, int(limit)))
    with _connect(db_path) as conn:
        rows = conn.execute(
            f"SELECT * FROM bursary_applications WHERE {' AND '.join(clauses)} "
            "ORDER BY student_id, application_id LIMIT ?", args).fetchall()
    return [_row_app(r) for r in rows]


def end_scheduled_award(application_id: int, *, on: str,
                        db_path: Any = None) -> Application:
    """Stop an award: inactive, schedule ends *on*, later Pending
    instalments cancelled."""
    ensure_store(db_path)
    with _connect(db_path) as conn:
        if _app_at(conn, application_id) is None:
            raise ValidationError(f"No award with id {application_id}")
        conn.execute(
            "UPDATE bursary_applications SET active = 0, schedule_end = ?, "
            "updated_at = datetime('now') WHERE application_id = ?",
            (on, application_id))
        conn.execute(
            "UPDATE bursary_schedule SET state = 'Cancelled', "
            "note = COALESCE(note || ' | ', '') || 'Award ended', "
            "updated_at = datetime('now') WHERE application_id = ? "
            "AND state = 'Pending' AND period_from > ?",
            (application_id, on))
        conn.commit()
        out = _app_at(conn, application_id)
    assert out is not None
    return out


# ── Evidence + vulnerable bursary ─────────────────────────────────

def verify_evidence(application_id: int, *, verified_by: str,
                    evidence_type: str, note: str | None = None,
                    on: str | None = None) -> Application:
    """Record that the evidence for an application has been seen and
    checked, and by whom. Needed before a vulnerable or policy award."""
    init_db()
    app = get_application(application_id)
    if app is None:
        raise ValidationError(f"No application #{application_id}")
    who = (verified_by or "").strip()
    if not who:
        raise ValidationError("Evidence must be verified by a named person")
    if evidence_type not in EVIDENCE_TYPES:
        raise ValidationError(
            f"Evidence type must be one of: {', '.join(EVIDENCE_TYPES)}")
    when = _validate_date(on or _date.today().isoformat(), "Verified on",
                          required=True)
    with _connect() as conn:
        conn.execute(
            """UPDATE bursary_applications SET evidence_received=1,
                   evidence_type=?, evidence_verified_by=?,
                   evidence_verified_on=?,
                   evidence_note=COALESCE(?, evidence_note),
                   status=CASE WHEN status='Awaiting Evidence'
                               THEN 'Under Review' ELSE status END,
                   updated_at=datetime('now')
               WHERE application_id=?""",
            (evidence_type, who, when, (note or "").strip() or None,
             application_id))
        conn.commit()
    out = get_application(application_id)
    assert out is not None
    logger.info("Evidence for bursary #%d verified by %s (%s)",
                application_id, who, evidence_type)
    return out


def create_vulnerable_application(student_id: str, *, category: str,
                                  academic_year: str | None = None,
                                  amount_requested: float | None = None,
                                  reason: str | None = None) -> Application:
    """Open a vulnerable-bursary application (status Awaiting Evidence)."""
    if category not in VULNERABLE_CATEGORIES:
        raise ValidationError(
            "Category must be one of: " + "; ".join(VULNERABLE_CATEGORIES))
    from education_system.systems.sixth_form.domains.finance.domain import (
        finance_calendar as fc,
    )
    app = create_application({
        "student_id": student_id, "bursary_type": VULNERABLE_TYPE,
        "academic_year": fc.normalise_year(academic_year),
        "amount_requested": (amount_requested if amount_requested is not None
                             else VULNERABLE_MAX_AWARD),
        "status": "Awaiting Evidence",
        "eligibility_basis": _VULNERABLE_BASIS[category],
        "reason": reason,
    })
    with _connect() as conn:
        conn.execute(
            "UPDATE bursary_applications SET vulnerable_category=? "
            "WHERE application_id=?", (category, app.application_id))
        conn.commit()
    out = get_application(app.application_id)
    assert out is not None
    return out


def award_vulnerable(application_id: int, *, category: str | None = None,
                     amount: float | None = None,
                     assessed_by: str | None = None,
                     frequency: str = DEFAULT_FREQUENCY,
                     start: str | None = None, end: str | None = None,
                     decision_note: str | None = None) -> Application:
    """Approve a vulnerable bursary and schedule it.

    Requires a defined vulnerable category and verified evidence; the
    award may not exceed :data:`VULNERABLE_MAX_AWARD` (pass a lower
    amount for a pro-rata award). Never attendance-conditional.
    """
    init_db()
    app = get_application(application_id)
    if app is None:
        raise ValidationError(f"No application #{application_id}")
    if app.bursary_type != VULNERABLE_TYPE:
        raise ValidationError(
            f"Application #{application_id} is a {app.bursary_type}, "
            f"not a {VULNERABLE_TYPE}")
    category = category or app.vulnerable_category
    if category not in VULNERABLE_CATEGORIES:
        raise ValidationError(
            "A vulnerable bursary needs one of the defined categories: "
            + "; ".join(VULNERABLE_CATEGORIES))
    if not app.evidence_verified:
        raise ValidationError(
            "Verify the evidence (and record who checked it) before "
            "awarding a vulnerable bursary")
    value = _validate_amount(
        VULNERABLE_MAX_AWARD if amount in (None, "") else amount,
        "Amount", required=True, allow_zero=False)
    assert value is not None
    if value > VULNERABLE_MAX_AWARD + 0.001:
        raise ValidationError(
            f"A vulnerable bursary is at most {CURRENCY_SYMBOL}"
            f"{VULNERABLE_MAX_AWARD:,.2f} a year")
    note = decision_note or f"Vulnerable bursary: {category}"
    update_application(application_id, {
        "status": "Approved", "amount_awarded": value,
        "amount_requested": max(value, app.amount_requested or 0.0),
        "eligibility_basis": _VULNERABLE_BASIS[category],
        "assessed_by": assessed_by, "assessed_on": _date.today().isoformat(),
        "decision_note": note,
    })
    with _connect() as conn:
        conn.execute(
            "UPDATE bursary_applications SET vulnerable_category=? "
            "WHERE application_id=?", (category, application_id))
        conn.commit()
    set_payment_schedule(application_id, frequency=frequency, start=start,
                         end=end, attendance_conditional=False)
    out = get_application(application_id)
    assert out is not None
    return out


# ── Discretionary policy rules ─────────────────────────────────────

def _validate_rule(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["name"] = str(_require(d.get("name"), "Rule name")).strip()
    year = (d.get("academic_year") or "").strip() if isinstance(
        d.get("academic_year"), str) else d.get("academic_year")
    if year:
        from education_system.systems.sixth_form.domains.finance.domain import (
            finance_calendar as fc,
        )
        try:
            year = fc.normalise_year(year)
        except ValueError as e:
            raise ValidationError(str(e)) from None
    out["academic_year"] = year or None
    btype = (d.get("bursary_type") or DISCRETIONARY_TYPE).strip()
    if btype not in BURSARY_TYPES or btype == VULNERABLE_TYPE:
        raise ValidationError(
            "Policy rules are for non-vulnerable bursary types")
    out["bursary_type"] = btype
    basis = (d.get("eligibility_basis") or "").strip() or None
    if basis and basis not in ELIGIBILITY_BASES:
        raise ValidationError(
            f"Eligibility basis must be one of: {', '.join(ELIGIBILITY_BASES)}")
    out["eligibility_basis"] = basis
    out["max_household_income"] = _validate_amount(
        d.get("max_household_income"), "Maximum household income")
    size = d.get("min_household_size")
    if size in (None, ""):
        out["min_household_size"] = None
    else:
        try:
            out["min_household_size"] = int(size)
        except (TypeError, ValueError):
            raise ValidationError(
                "Minimum household size must be a whole number") from None
    out["award_amount"] = _validate_amount(
        d.get("award_amount"), "Award amount", required=True,
        allow_zero=False)
    freq = (d.get("payment_frequency") or DEFAULT_FREQUENCY).strip()
    if freq not in PAYMENT_FREQUENCIES:
        raise ValidationError(
            f"Frequency must be one of: {', '.join(PAYMENT_FREQUENCIES)}")
    out["payment_frequency"] = freq
    out["attendance_conditional"] = 1 if d.get(
        "attendance_conditional", True) else 0
    out["requires_evidence"] = 1 if d.get("requires_evidence", True) else 0
    try:
        out["priority"] = int(d.get("priority") or 100)
    except (TypeError, ValueError):
        raise ValidationError("Priority must be a whole number") from None
    out["active"] = 1 if d.get("active", True) else 0
    out["notes"] = (d.get("notes") or "").strip() or None
    return out


_RULE_COLS = ("name", "academic_year", "bursary_type", "eligibility_basis",
              "max_household_income", "min_household_size", "award_amount",
              "payment_frequency", "attendance_conditional",
              "requires_evidence", "priority", "active", "notes")


def create_rule(d: dict[str, Any]) -> PolicyRule:
    init_db()
    p = _validate_rule(d)
    with _connect() as conn:
        cur = conn.execute(
            f"INSERT INTO bursary_policy_rules ({', '.join(_RULE_COLS)}) "
            f"VALUES ({', '.join('?' * len(_RULE_COLS))})",
            [p[c] for c in _RULE_COLS])
        conn.commit()
        new_id = int(cur.lastrowid)
    out = get_rule(new_id)
    assert out is not None
    return out


def get_rule(rule_id: int) -> PolicyRule | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM bursary_policy_rules WHERE rule_id=?",
                         (rule_id,)).fetchone()
    return _row_rule(r) if r else None


def list_rules(*, active_only: bool = False,
               academic_year: str | None = None) -> list[PolicyRule]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if active_only:
        clauses.append("active = 1")
    if academic_year:
        clauses.append("(academic_year IS NULL OR academic_year = ?)")
        args.append(academic_year)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM bursary_policy_rules {where} "
            "ORDER BY priority, award_amount DESC, rule_id", args).fetchall()
    return [_row_rule(r) for r in rows]


def update_rule(rule_id: int, d: dict[str, Any]) -> PolicyRule:
    existing = get_rule(rule_id)
    if existing is None:
        raise ValidationError(f"No policy rule #{rule_id}")
    merged = {**vars(existing), **d}
    p = _validate_rule(merged)
    with _connect() as conn:
        conn.execute(
            f"UPDATE bursary_policy_rules SET "
            f"{', '.join(c + '=?' for c in _RULE_COLS)}, "
            "updated_at=datetime('now') WHERE rule_id=?",
            [p[c] for c in _RULE_COLS] + [rule_id])
        conn.commit()
    out = get_rule(rule_id)
    assert out is not None
    return out


def delete_rule(rule_id: int) -> bool:
    """Delete a rule nobody has been awarded under; otherwise deactivate."""
    init_db()
    with _connect() as conn:
        used = conn.execute(
            "SELECT 1 FROM bursary_applications WHERE policy_rule_id=? LIMIT 1",
            (rule_id,)).fetchone()
        if used:
            cur = conn.execute(
                "UPDATE bursary_policy_rules SET active=0, "
                "updated_at=datetime('now') WHERE rule_id=?", (rule_id,))
        else:
            cur = conn.execute(
                "DELETE FROM bursary_policy_rules WHERE rule_id=?", (rule_id,))
        conn.commit()
    return bool(cur.rowcount)


def evaluate_discretionary(application_id: int) -> PolicyDecision:
    """Which policy rule (if any) an application meets, and the award it
    gives. Rules are tried in priority order; the first match wins."""
    app = get_application(application_id)
    if app is None:
        raise ValidationError(f"No application #{application_id}")
    reasons: list[str] = []
    if app.bursary_type == VULNERABLE_TYPE:
        return PolicyDecision(application_id, False, None, None,
                              ["Vulnerable bursaries use award_vulnerable, "
                               "not the discretionary policy"])
    rules = [r for r in list_rules(active_only=True,
                                   academic_year=app.academic_year)
             if r.bursary_type == app.bursary_type]
    if not rules:
        return PolicyDecision(application_id, False, None, None,
                              [f"No active policy rule for {app.bursary_type}"
                               + (f" in {app.academic_year}"
                                  if app.academic_year else "")])
    for rule in rules:
        why: list[str] = []
        if rule.eligibility_basis and rule.eligibility_basis != \
                app.eligibility_basis:
            why.append(f"basis is not {rule.eligibility_basis}")
        if rule.max_household_income is not None:
            if app.household_income is None:
                why.append("household income not recorded")
            elif app.household_income > rule.max_household_income:
                why.append(
                    f"income {CURRENCY_SYMBOL}{app.household_income:,.0f} > "
                    f"{CURRENCY_SYMBOL}{rule.max_household_income:,.0f}")
        if rule.min_household_size is not None and (
                app.household_size or 0) < rule.min_household_size:
            why.append(f"household smaller than {rule.min_household_size}")
        if why:
            reasons.append(f"Rule '{rule.name}': " + "; ".join(why))
            continue
        if rule.requires_evidence and not app.evidence_verified:
            return PolicyDecision(
                application_id, False, None, rule,
                reasons + [f"Meets rule '{rule.name}' but the evidence has "
                           "not been verified"])
        amount = rule.award_amount
        if app.amount_requested and app.amount_requested < amount:
            amount = app.amount_requested
            reasons.append("Capped at the amount requested")
        return PolicyDecision(application_id, True, round(amount, 2), rule,
                              reasons + [f"Meets rule '{rule.name}'"])
    return PolicyDecision(application_id, False, None, None, reasons)


def apply_discretionary_policy(application_id: int, *,
                               assessed_by: str | None = None,
                               start: str | None = None,
                               end: str | None = None) -> Application:
    """Approve an application at the amount its matching policy rule
    gives, and schedule it the way the rule says."""
    decision = evaluate_discretionary(application_id)
    if not decision.eligible or decision.rule is None:
        raise ValidationError("Not eligible under the policy: "
                              + "; ".join(decision.reasons))
    rule = decision.rule
    update_application(application_id, {
        "status": "Approved", "amount_awarded": decision.amount,
        "assessed_by": assessed_by,
        "assessed_on": _date.today().isoformat(),
        "decision_note": f"Policy rule #{rule.rule_id} '{rule.name}'",
    })
    with _connect() as conn:
        conn.execute(
            "UPDATE bursary_applications SET policy_rule_id=? "
            "WHERE application_id=?", (rule.rule_id, application_id))
        conn.commit()
    set_payment_schedule(application_id, frequency=rule.payment_frequency,
                         start=start, end=end,
                         attendance_conditional=rule.attendance_conditional)
    out = get_application(application_id)
    assert out is not None
    return out


# ── Legacy attendance-bursary migration ────────────────────────────

_LEGACY_TYPE_MAP: dict[str, str] = {
    "Vulnerable group": VULNERABLE_TYPE,
    "Discretionary": DISCRETIONARY_TYPE,
    "Travel": "Transport",
    "Free meals": "Free Meals (FSM)",
    "Equipment": "Books & Equipment",
}


def _migrate_attendance_bursary(conn: db.Connection) -> dict[str, int]:
    """Fold attendance_bursary_awards/payments into this store.

    Idempotent — each legacy award / payment is copied once, keyed on
    ``legacy_award_id`` / ``legacy_payment_id``. The legacy tables are
    left exactly as they were.
    """
    counts = {"awards": 0, "payments": 0}
    if not _table_exists(conn, "attendance_bursary_awards"):
        return counts
    import datetime as _dt
    today = _dt.date.today().isoformat()
    mapped = {r[0]: r[1] for r in conn.execute(
        "SELECT legacy_award_id, application_id FROM bursary_applications "
        "WHERE legacy_award_id IS NOT NULL")}
    has_payments = _table_exists(conn, "attendance_bursary_payments")
    for a in conn.execute(
            "SELECT * FROM attendance_bursary_awards").fetchall():
        if a["award_id"] in mapped:
            continue
        freq = a["period"] if a["period"] in PAYMENT_FREQUENCIES \
            else "Fortnightly"
        span_from = a["start_date"] or (a["created_at"] or today)[:10]
        span_to = a["end_date"] or _year_end_for(span_from)
        try:
            n = max(1, len(schedule_periods(freq, span_from, span_to)))
        except (ValidationError, ValueError):
            n = 1
        moved = 0.0
        if has_payments:
            moved = float(conn.execute(
                "SELECT COALESCE(SUM(amount), 0) FROM "
                "attendance_bursary_payments WHERE award_id = ?",
                (a["award_id"],)).fetchone()[0])
        total = round(max((a["amount"] or 0.0) * n, moved), 2)
        cur = conn.execute(
            """INSERT INTO bursary_applications
                   (student_id, bursary_type, academic_year,
                    application_date, amount_requested, amount_awarded,
                    status, evidence_received, notes, assessed_on,
                    payment_frequency, instalment_amount, schedule_start,
                    schedule_end, attendance_conditional, active,
                    legacy_award_id, run_driven, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, 'Approved', 0, ?, ?, ?, ?, ?, ?,
                       ?, ?, ?, 1, COALESCE(?, datetime('now')),
                       datetime('now'))""",
            (a["student_id"],
             _LEGACY_TYPE_MAP.get(a["award_type"], DISCRETIONARY_TYPE),
             _academic_year_of(span_from), span_from, total, total,
             ((a["notes"] or "") + " " if a["notes"] else "")
             + f"(migrated from attendance bursary award #{a['award_id']})",
             span_from, freq, a["amount"], a["start_date"], a["end_date"],
             int(a["conditional"]), int(a["active"]), a["award_id"],
             a["created_at"]))
        mapped[a["award_id"]] = int(cur.lastrowid)
        counts["awards"] += 1
    if has_payments:
        done = {r[0] for r in conn.execute(
            "SELECT legacy_payment_id FROM bursary_schedule "
            "WHERE legacy_payment_id IS NOT NULL")}
        touched: set[int] = set()
        for p in conn.execute(
                "SELECT * FROM attendance_bursary_payments").fetchall():
            if p["payment_id"] in done or p["award_id"] not in mapped:
                continue
            app_id = mapped[p["award_id"]]
            # A period this award already has an instalment for keeps it.
            if conn.execute(
                    "SELECT 1 FROM bursary_schedule WHERE application_id=? "
                    "AND period_from=? AND period_to=?",
                    (app_id, p["period_from"], p["period_to"])).fetchone():
                continue
            disb_id = None
            if p["state"] in ("Paid", "Released") and (p["amount"] or 0) > 0:
                paid_on = ((p["released_at"] or p["decided_at"]
                            or p["period_to"]) or today)[:10]
                cur = conn.execute(
                    """INSERT INTO bursary_disbursements
                           (application_id, amount, paid_on, method, status,
                            reference, recorded_by, notes)
                       VALUES (?, ?, ?, ?, 'Paid', ?, ?, ?)""",
                    (app_id, p["amount"], paid_on,
                     DEFAULT_DISBURSEMENT_METHOD,
                     f"Migrated attendance payment #{p['payment_id']}",
                     p["released_by"] or p["decided_by"],
                     f"Bursary payment {p['period_from']} to "
                     f"{p['period_to']}"))
                disb_id = int(cur.lastrowid)
            state = p["state"] if p["state"] in INSTALMENT_STATES \
                else INSTALMENT_PENDING
            conn.execute(
                """INSERT INTO bursary_schedule
                       (application_id, student_id, period_from, period_to,
                        due_date, amount, state, attendance_pct,
                        threshold_pct, decision, decided_by, decided_at,
                        released_by, released_at, disbursement_id,
                        legacy_payment_id, note, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                           COALESCE(?, datetime('now')))""",
                (app_id, p["student_id"], p["period_from"], p["period_to"],
                 p["period_to"], p["amount"], state, p["attendance_pct"],
                 p["threshold_pct"],
                 "Hold" if p["decision"] == "Hold" else
                 ("Pay" if p["decision"] else None),
                 p["decided_by"], p["decided_at"], p["released_by"],
                 p["released_at"], disb_id, p["payment_id"], p["note"],
                 p["created_at"]))
            touched.add(app_id)
            counts["payments"] += 1
        for app_id in touched:
            _roll_status_conn(conn, app_id)
    if counts["awards"] or counts["payments"]:
        logger.info("Migrated %d attendance bursary award(s) and %d "
                    "payment(s) into the bursary store",
                    counts["awards"], counts["payments"])
    return counts


def migrate_attendance_bursary(db_path: Any = None) -> dict[str, int]:
    """Run the legacy migration explicitly (it also runs on first use)."""
    ensure_store(db_path)
    with _connect(db_path) as conn:
        out = _migrate_attendance_bursary(conn)
        conn.commit()
    return out


def erase_attendance_details(student_id: str, *, db_path: Any = None) -> int:
    """Strip one learner's attendance figures from their instalments.

    Called by the attendance right-to-erasure. The instalments and the
    money paid or held stay (bursary spend is audited by the ESFA and
    kept for its retention period); the attendance percentage and the
    attendance-based note that justified each decision are removed.
    """
    ensure_store(db_path)
    with _connect(db_path) as conn:
        cur = conn.execute(
            "UPDATE bursary_schedule SET attendance_pct = NULL, "
            "note = CASE WHEN decision IS NOT NULL "
            "THEN 'Attendance detail erased' ELSE note END, "
            "updated_at = datetime('now') WHERE student_id = ?",
            (student_id,))
        conn.commit()
    return int(cur.rowcount or 0)
