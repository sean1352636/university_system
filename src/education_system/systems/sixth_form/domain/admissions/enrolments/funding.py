"""Condition of funding and fees for an enrolment.

**Condition of funding** (16-19 funded learners only). Whether a learner
must study English and/or maths, and what qualification counts, is
decided by ``prior_attainment.funding_condition`` (grade 4+ held or an
exemption → nothing needed; prior grade 3 → a GCSE; grade 2 or below,
or no GCSE → a GCSE or Functional Skills). This module scopes that to
the **enrolment's year**: the requirement is met only by a GCSE (or,
where allowed, Functional Skills) aim that is active or completed *in
that year* — last year's resit does not cover this year.
:func:`apply_condition_of_funding` adds the missing aims through
``learning_aims.add_aim``.

**Fees** (19+ co-funded, full cost and overseas learners — the fee
status lives on the ILR record, see :mod:`ilr`). There is one fee
schedule, finance's (``domains/finance/domain/fees/fee_rules``): the fee
is worked out by ``fee_rules.calculate_fee`` from the learner's age on
31 August, their finance residency/fee profile and the enrolment's fee
status, less finance remissions. 16-19 funded and 19+ fully funded
learners owe nothing. :func:`raise_fee` raises finance's numbered tuition
invoice (``fee_rules.generate_invoice``, which creates the Tuition fee
item) — one live invoice per learner per year, and an enrolment is one
per learner per year, so the invoice is the enrolment's charge and
nothing can be raised twice.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.qualifications import (
    learning_aims as _aims,
)
from education_system.systems.sixth_form.domain.academics.qualifications import (
    prior_attainment as _prior,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as _en,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    ilr as _ilr,
)

logger = logging.getLogger(__name__)

ValidationError = _en.ValidationError

AREAS: tuple[str, ...] = tuple(_prior.AREAS)
#: Subject used for a resit aim created by apply_condition_of_funding.
DEFAULT_SUBJECTS: dict[str, str] = {"English": "English Language",
                                    "Maths": "Mathematics"}
GCSE = "GCSE"
FUNCTIONAL_SKILLS = "Functional Skills"


def init_db() -> None:
    """Fees keep no tables of their own; the ILR record must exist."""
    _ilr.init_db()


def _enrolment(enrolment_id: int) -> _en.Enrolment:
    e = _en.get_enrolment(int(enrolment_id))
    if e is None:
        raise ValidationError(f"No enrolment #{enrolment_id}")
    return e


def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    return students


# ── Condition of funding ────────────────────────────────────────────

_PREFIX = re.compile(r"^(gcse|functional skills|fs)\s+", re.I)


def _area_of(aim: Any) -> str | None:
    if aim.qualification_type not in (GCSE, FUNCTIONAL_SKILLS):
        return None
    return _prior.area_for_subject(_PREFIX.sub("", aim.subject.strip()))


@dataclass
class CofArea:
    area: str
    best_grade: str | None
    requirement: str            # "None", "GCSE", "GCSE or Functional Skills"
    met: bool
    status: str
    aim_id: int | None = None
    aim_label: str | None = None
    exempt: bool = False


@dataclass
class CofPosition:
    enrolment_id: int
    student_id: str
    academic_year: str
    applies: bool               # False for learners not 16-19 funded
    reason: str
    english: CofArea | None = None
    maths: CofArea | None = None

    @property
    def areas(self) -> list[CofArea]:
        return [a for a in (self.english, self.maths) if a is not None]

    @property
    def compliant(self) -> bool:
        return not self.applies or all(a.met for a in self.areas)


@dataclass
class CofGap:
    area: str
    best_grade: str | None
    requirement: str
    suggested_type: str         # what apply_condition_of_funding adds by default
    allowed_types: tuple[str, ...]
    status: str


def _year_area(area: Any, aims: list[Any]) -> CofArea:
    """Scope one prior_attainment AreaStatus to the enrolment year's aims."""
    if area.requirement == "None":
        return CofArea(area=area.area, best_grade=area.best_grade,
                       requirement="None", met=True, status=area.status,
                       exempt=area.exemption is not None)
    allowed = (GCSE,) if area.requirement == GCSE else (GCSE, FUNCTIONAL_SKILLS)
    matching = [a for a in aims if _area_of(a) == area.area
                and a.status in ("Active", "Completed")]
    chosen = next((a for a in matching if a.qualification_type == GCSE), None)
    if chosen is None:
        chosen = next((a for a in matching
                       if a.qualification_type in allowed), None)
    held = f"grade {area.best_grade}" if area.best_grade else "no GCSE recorded"
    if chosen is None:
        if any(a.qualification_type == FUNCTIONAL_SKILLS for a in matching):
            status = (f"Not met — {held}: must be on a GCSE, Functional "
                      "Skills does not meet the condition")
        else:
            status = (f"Not met — {held}: needs a {area.requirement} "
                      f"{area.area} aim this year")
        return CofArea(area=area.area, best_grade=area.best_grade,
                       requirement=area.requirement, met=False, status=status)
    return CofArea(area=area.area, best_grade=area.best_grade,
                   requirement=area.requirement, met=True,
                   status=f"Met — {held}, on {chosen.label}",
                   aim_id=chosen.aim_id, aim_label=chosen.label)


def cof_position(enrolment_id: int) -> CofPosition:
    """English and maths condition-of-funding position for one enrolment."""
    e = _enrolment(enrolment_id)
    rec = _ilr.get_ilr(e.enrolment_id)
    base = dict(enrolment_id=e.enrolment_id, student_id=e.student_id,
                academic_year=e.academic_year)
    if rec.fund_model != 25:
        why = (f"not 16-19 funded ({rec.fee_status})" if rec.fee_status
               else "fee status not set")
        return CofPosition(**base, applies=False,
                           reason=f"Condition of funding does not apply: {why}")
    cond = _prior.funding_condition(e.student_id)
    aims = _ilr.year_aims(e)
    return CofPosition(**base, applies=True, reason="16-19 funded",
                       english=_year_area(cond.english, aims),
                       maths=_year_area(cond.maths, aims))


def condition_of_funding_gaps(enrolment_id: int) -> list[CofGap]:
    """The English / maths aims the enrolment is missing (empty when met
    or when the condition does not apply)."""
    pos = cof_position(enrolment_id)
    gaps: list[CofGap] = []
    for a in pos.areas:
        if a.met:
            continue
        allowed = (GCSE,) if a.requirement == GCSE else (GCSE, FUNCTIONAL_SKILLS)
        gaps.append(CofGap(
            area=a.area, best_grade=a.best_grade, requirement=a.requirement,
            suggested_type=GCSE if a.requirement == GCSE else FUNCTIONAL_SKILLS,
            allowed_types=allowed, status=a.status))
    return gaps


@dataclass
class CofApplyResult:
    enrolment_id: int
    created: list[Any] = field(default_factory=list)   # LearningAim
    problems: list[str] = field(default_factory=list)


def apply_condition_of_funding(
        enrolment_id: int, *,
        qualification_types: dict[str, str] | None = None,
        subjects: dict[str, str] | None = None,
        aim_codes: dict[str, str] | None = None,
        planned_hours: dict[str, float] | None = None,
        awarding_bodies: dict[str, str] | None = None,
        start_date: str | None = None,
        areas: tuple[str, ...] | list[str] | None = None) -> CofApplyResult:
    """Add the missing English / maths aims to the learner's programme.

    Per-area choices are keyed "English" / "Maths". The type defaults to
    the gap's suggestion and must be allowed for the learner's grade
    (a grade 3 must take the GCSE). Start date = the enrolment's start
    (else the year's first day), planned end = the year's last day. Each
    area is added separately; an area that fails is reported in
    ``problems`` and does not stop the other.
    """
    _en._require_writer("add condition-of-funding aims")
    e = _enrolment(enrolment_id)
    if not e.is_live:
        raise ValidationError("Condition-of-funding aims can only be added to "
                              "a live (Enrolled or Pending) enrolment")
    first, last = _en.academic_year_dates(e.academic_year)
    start = start_date or e.start_date or first
    if not (first <= start <= last):
        raise ValidationError(f"Start date must fall inside {e.academic_year}")
    out = CofApplyResult(enrolment_id=e.enrolment_id)
    wanted = set(areas) if areas else None
    for gap in condition_of_funding_gaps(e.enrolment_id):
        if wanted is not None and gap.area not in wanted:
            continue
        qtype = (qualification_types or {}).get(gap.area) or gap.suggested_type
        if qtype not in gap.allowed_types:
            out.problems.append(
                f"{gap.area}: {qtype} does not meet the condition for "
                f"{gap.best_grade and 'grade ' + gap.best_grade or 'this learner'}"
                f" — use {' or '.join(gap.allowed_types)}")
            continue
        payload = {
            "qualification_type": qtype,
            "subject": (subjects or {}).get(gap.area) or DEFAULT_SUBJECTS[gap.area],
            "start_date": start, "planned_end_date": last,
            "academic_year": e.academic_year,
            "aim_code": (aim_codes or {}).get(gap.area),
            "planned_hours": (planned_hours or {}).get(gap.area),
            "awarding_body": (awarding_bodies or {}).get(gap.area),
            "notes": "Condition of funding",
        }
        try:
            aim = _aims.add_aim(e.student_id, payload, recorded_by=_en._actor(),
                                reason="Condition of funding")
        except (_aims.ValidationError, ValueError) as exc:
            out.problems.append(f"{gap.area}: {exc}")
            continue
        out.created.append(aim)
    if out.created:
        with _en._connect() as conn:
            _en._log(conn, e, "Condition of funding",
                     "Added " + ", ".join(a.label for a in out.created))
            conn.commit()
    return out


@dataclass
class CofRow:
    enrolment_id: int
    student_id: str
    student_name: str
    year_group: int
    tutor_group: str | None
    status: str
    position: CofPosition

    @property
    def gaps(self) -> list[str]:
        return [a.area for a in self.position.areas if not a.met]

    def csv_row(self) -> dict[str, Any]:
        """Flat row for enrolment_reports.to_csv."""
        p = self.position
        return {
            "enrolment_id": self.enrolment_id, "student_id": self.student_id,
            "student_name": self.student_name, "year_group": self.year_group,
            "tutor_group": self.tutor_group, "status": self.status,
            "applies": "Yes" if p.applies else "No", "reason": p.reason,
            "english": p.english.status if p.english else "",
            "maths": p.maths.status if p.maths else "",
            "compliant": "Yes" if p.compliant else "No",
            "gaps": ", ".join(self.gaps),
        }


def cof_report(academic_year: str, *, only_gaps: bool = False,
               live_only: bool = True) -> list[CofRow]:
    """Condition-of-funding position for every enrolment in the year
    (archived left out; ``live_only`` leaves out withdrawn/completed)."""
    names = {s.student_id: s.full_name for s in _students().list_students()}
    rows: list[CofRow] = []
    for e in _en.list_enrolments(academic_year=academic_year):
        if live_only and not e.is_live:
            continue
        pos = cof_position(e.enrolment_id)
        if only_gaps and pos.compliant:
            continue
        rows.append(CofRow(enrolment_id=e.enrolment_id, student_id=e.student_id,
                           student_name=names.get(e.student_id, "(unknown)"),
                           year_group=e.year_group, tutor_group=e.tutor_group,
                           status=e.status, position=pos))
    return rows


# ── Fees (finance's fee schedule) ───────────────────────────────────

def _fee_rules():
    from education_system.systems.sixth_form.domains.finance.domain.fees import (
        fee_rules,
    )
    return fee_rules


def require_fee_rules_access(action: str = "manage fee rules") -> Any:
    """Fee rules are kept by finance or funding staff (screens that open
    finance's Fee Rules from the enrolment side check this first)."""
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return _guard.require_any((access.FINANCE, access.FUNDING), action)


@dataclass
class FeeDue:
    enrolment_id: int
    student_id: str
    academic_year: str
    fee_status: str | None
    fee_paying: bool
    rule: Any | None                    # fee_rules.FeeRule that priced it
    age_on_31_aug: int | None
    age_band: str | None
    residency_category: str | None
    gross_fee: float
    remission_amount: float
    net_fee: float
    already_raised: float
    to_raise: float
    explanation: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


def list_charges(enrolment_id: int, *, include_cancelled: bool = True
                 ) -> list[Any]:
    """Finance's tuition invoices (``fee_rules.Invoice``) for the
    enrolment's learner and year — the enrolment's charges."""
    e = _enrolment(enrolment_id)
    invs = _fee_rules().list_invoices(student_id=e.student_id,
                                      academic_year=e.academic_year)
    if not include_cancelled:
        invs = [i for i in invs if i.status == "Issued"]
    return sorted(invs, key=lambda i: i.invoice_id)


def fee_due(enrolment_id: int) -> FeeDue:
    """The tuition fee this enrolment owes, from finance's fee rules.

    The ILR fee status decides whether a fee arises (16-19 funded and 19+
    fully funded → £0). For a fee-paying status, finance's
    ``calculate_fee`` takes the learner's age on 31 August, their finance
    residency/fee profile and the fee status to pick a rule, then takes
    off finance remissions. Problems (no fee status, no profile, no
    matching rule, an invoice that no longer matches) are listed, not
    raised.
    """
    e = _enrolment(enrolment_id)
    rec = _ilr.get_ilr(e.enrolment_id)
    out = FeeDue(enrolment_id=e.enrolment_id, student_id=e.student_id,
                 academic_year=e.academic_year, fee_status=rec.fee_status,
                 fee_paying=rec.fee_paying, rule=None, age_on_31_aug=None,
                 age_band=None, residency_category=None, gross_fee=0.0,
                 remission_amount=0.0, net_fee=0.0, already_raised=0.0,
                 to_raise=0.0)
    fr = _fee_rules()
    live = list_charges(e.enrolment_id, include_cancelled=False)
    out.already_raised = round(sum(i.net_fee for i in live), 2)
    if not rec.fee_status:
        out.problems.append("Fee status not set — record it on the ILR details")
        return out
    out.explanation.append(f"Fee status: {rec.fee_status} ({rec.fee_status_source})")
    if not rec.fee_paying:
        out.explanation.append("No tuition fee for this fee status")
        if live:
            out.problems.append(
                f"Tuition invoice {live[0].invoice_number} is live but "
                f"{rec.fee_status} learners pay no fee — cancel it")
        return out
    try:
        calc = fr.calculate_fee(e.student_id, e.academic_year,
                                fee_status=rec.fee_status)
    except fr.ValidationError as exc:
        out.problems.append(str(exc))
        return out
    out.rule, out.age_on_31_aug = calc.rule, calc.age_on_31_aug
    out.age_band, out.residency_category = calc.age_band, calc.residency_category
    out.gross_fee, out.remission_amount = calc.gross_fee, calc.remission_amount
    out.net_fee = calc.net_fee
    out.explanation.extend(line for line in calc.explanation
                           if line != f"Fee status: {rec.fee_status}")
    if calc.gross_fee <= 0 and calc.rule.fee_status is None:
        out.problems.append(
            f"Finance rule #{calc.rule.rule_id} charges nothing for "
            f"{calc.age_band} / {calc.residency_category}, but "
            f"{rec.fee_status} learners pay a fee — add a fee rule for fee "
            f"status {rec.fee_status} under Finance > Fee Rules")
    if live:
        inv = live[0]
        out.explanation.append(f"Invoice {inv.invoice_number}: £{inv.net_fee:,.2f}")
        if abs(inv.net_fee - out.net_fee) >= 0.005:
            out.problems.append(
                f"Invoice {inv.invoice_number} (£{inv.net_fee:,.2f}) no longer "
                f"matches the fee (£{out.net_fee:,.2f}) — cancel it and raise "
                "it again")
    else:
        out.to_raise = out.net_fee
    return out


def _require_raise(action: str) -> Any:
    from education_system.systems.sixth_form.domain.admissions import _guard
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return _guard.require_any(
        (access.FINANCE, access.ADMISSIONS, access.STUDENTS_MANAGE), action)


def raise_fee(enrolment_id: int, *, due_date: str | None = None) -> Any:
    """Raise the enrolment's tuition fee as finance's numbered invoice
    (``fee_rules.generate_invoice`` — it creates the Tuition fee item, so
    payments, statements and receipts work as for any fee). Returns the
    ``fee_rules.Invoice``. Blank *due_date* = finance's default.

    Refused (ValidationError, message for the screen) when nothing is
    due, a problem stops the calculation or an invoice is already live
    for the learner and year.
    """
    _require_raise("raise a tuition fee")
    due = fee_due(enrolment_id)
    if due.problems:
        raise ValidationError("; ".join(due.problems))
    if due.to_raise <= 0:
        raise ValidationError("No tuition fee left to raise for this enrolment")
    e = _enrolment(enrolment_id)
    if e.is_archived:
        raise ValidationError("This enrolment is archived — restore it first")
    fr = _fee_rules()
    try:
        inv = fr.generate_invoice(e.student_id, e.academic_year,
                                  issued_by=_en._actor() or "enrolments",
                                  due_date=due_date, fee_status=due.fee_status)
    except fr.ValidationError as exc:
        raise ValidationError(str(exc)) from None
    with _en._connect() as conn:
        _en._log(conn, e, "Tuition fee raised",
                 f"{inv.invoice_number}: £{inv.net_fee:,.2f} ({due.fee_status})")
        conn.commit()
    return inv


def cancel_fee_charge(invoice_id: int, *, reason: str) -> Any:
    """Cancel one of the enrolment's tuition invoices (its finance item
    becomes Cancelled). Refused once a payment has been taken — refund it
    in finance. Returns the cancelled ``fee_rules.Invoice``."""
    _require_raise("cancel a tuition fee")
    if not (reason or "").strip():
        raise ValidationError("Give a reason for cancelling the charge")
    fr = _fee_rules()
    try:
        inv = fr.cancel_invoice(int(invoice_id), reason=reason.strip(),
                                by=_en._actor() or "enrolments")
    except fr.ValidationError as exc:
        raise ValidationError(str(exc)) from None
    e = next(iter(_en.list_enrolments(
        student_id=inv.student_id, academic_year=inv.academic_year,
        include_archived=True)), None)
    if e is not None:
        with _en._connect() as conn:
            _en._log(conn, e, "Tuition fee cancelled",
                     f"{inv.invoice_number}: {reason.strip()}")
            conn.commit()
    return inv
