"""ILR learning delivery for an enrolment: funding, hours, outcomes.

An enrolment (one learner, one academic year) is what the ESFA funds, so
the Individualised Learner Record facts that belong to a *year of
learning* hang off it here, in two tables in the shared sixthform.db:

* ``enrolment_ilr`` — one row per enrolment (``enrolment_id`` FK,
  cascades): fee status, funding model (ILR ``FundModel``), mode of
  study, planned learning and employability/enrichment/pastoral hours
  (``PlanLearnHours`` / ``PlanEEPHours``) and the destination and
  progression outcome recorded when the learner finishes.
* ``aim_outcomes`` — the ILR ``Outcome`` of a learning aim (``aim_id``
  FK to ``learning_aims``, cascades): 1 achieved, 2 partial achievement,
  3 no achievement, 8 not yet known, with achievement date and grade.
  ``learning_aims`` itself is not changed.

**Everything not recorded is derived**, and every derived value says so
(``*_source``):

* fee status — from age on 31 August (16-18, a 19+ learner continuing a
  programme begun at 16-18, or 19-24 with an EHC plan → "16-19 funded")
  and the finance fee profile (an international residency → "Overseas");
  other 19+ learners have to be set by staff;
* funding model — from the fee status (:data:`FEE_STATUS_FUND_MODEL`);
* planned hours — the study programme's hours for the enrolment's aims
  (``study_programme.planned_hours``: the aim's own planned hours, else
  timetable / course / subject GLH; aims withdrawn before their
  qualifying period do not count) and its non-qualification hours;
* mode — **full time is 540 or more planned hours in the year**
  (:data:`FULL_TIME_HOURS`, the ESFA 16-19 full-time threshold), else
  part time, unless staff override it;
* completion status of an aim (``CompStatus``) — Active → 1 continuing,
  Completed → 2 completed, Withdrawn / Transferred → 3 withdrawn;
* outcome — when none is recorded: 8 for a completed aim, 3 for a
  withdrawn one.

16-19 funding band, from total planned hours (check the current ESFA
"Funding guidance for young people" each year): Band 5 580+, Band 4
450-579 (``study_programme`` splits it into 4a for 16-17s / high needs
and 4b for other 18+ learners, and an 18+ learner at 580+ is 4b too),
Band 3 360-449, Band 2 280-359, Band 1 under 280.

Early leavers: an enrolment withdrawn within :data:`QUALIFYING_DAYS`
(42) days of its start never reached the funding qualifying period and
is not funded; each aim is checked with learning_aims' own qualifying
rules too.

Writes need the enrolment writer capability (``admissions`` or
``students.manage``) and are audited in ``enrolment_history``.

These records are the data; the ILR *file* is built once, by the
census_ilr return builder, from them (:func:`export_csv` delegates). It
holds personal and SEND data: it needs ``funding``, ``admissions`` or
``students.manage`` and is logged as sensitive access.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.academics.qualifications import (
    learning_aims as _aims,
)
from education_system.systems.sixth_form.domain.academics.qualifications import (
    study_programme as _programme,
)
from education_system.systems.sixth_form.domain.admissions.enrolments import (
    enrolments as _en,
)

logger = logging.getLogger(__name__)

ValidationError = _en.ValidationError

# ── Codes ───────────────────────────────────────────────────────────

#: ILR ``FundModel`` values used by a sixth form.
FUND_MODELS: dict[int, str] = {
    25: "16-19 (excluding apprenticeships)",
    35: "Adult skills",
    99: "No ESFA funding",
}

FEE_16_19 = "16-19 funded"
FEE_19_FULL = "19+ fully funded"
FEE_19_CO = "19+ co-funded"
FEE_FULL_COST = "Full cost"
FEE_OVERSEAS = "Overseas"
FEE_STATUSES: tuple[str, ...] = (FEE_16_19, FEE_19_FULL, FEE_19_CO,
                                 FEE_FULL_COST, FEE_OVERSEAS)
#: Fee statuses where the learner (or an employer) pays something.
FEE_PAYING: tuple[str, ...] = (FEE_19_CO, FEE_FULL_COST, FEE_OVERSEAS)
#: The funding model each fee status is reported under.
FEE_STATUS_FUND_MODEL: dict[str, int] = {
    FEE_16_19: 25, FEE_19_FULL: 35, FEE_19_CO: 35,
    FEE_FULL_COST: 99, FEE_OVERSEAS: 99,
}
#: ILR ``LearningDeliveryFAM`` FFI (full or co-funding indicator), FM35 only.
FEE_STATUS_FFI: dict[str, int] = {FEE_19_FULL: 1, FEE_19_CO: 2}

FULL_TIME = "Full time"
PART_TIME = "Part time"
MODES: tuple[str, ...] = (FULL_TIME, PART_TIME)
#: ESFA 16-19: a study programme of 540+ planned hours a year is full time.
FULL_TIME_HOURS: int = 540

#: Enrolment-level qualifying period: the long-aim rule of
#: learning_aims.QUALIFYING_PERIOD_RULES (42 days for 24 weeks or more).
QUALIFYING_DAYS: int = _aims.QUALIFYING_PERIOD_RULES[0][1]

#: ILR ``Outcome``.
OUTCOMES: dict[int, str] = {
    1: "Achieved",
    2: "Partial achievement",
    3: "No achievement",
    8: "Learning activities complete but outcome not yet known",
}
#: Outcomes allowed for an aim in each ended status.
_OUTCOMES_FOR_STATUS: dict[str, tuple[int, ...]] = {
    "Completed": (1, 2, 3, 8),
    "Withdrawn": (2, 3),
    "Transferred": (2, 3),
}

#: ILR ``CompStatus`` from the learning aim's status.
COMP_STATUS: dict[str, int] = {"Active": 1, "Completed": 2,
                               "Withdrawn": 3, "Transferred": 3}
COMP_STATUS_LABELS: dict[int, str] = {
    1: "Continuing", 2: "Completed", 3: "Withdrawn"}

#: ILR destination and progression (``OutType`` → {``OutCode``: label}).
#: Check the current ILR specification each year.
DESTINATIONS: dict[str, dict[int, str]] = {
    "EDU": {1: "Traineeship", 2: "Apprenticeship", 3: "Supported internship",
            4: "Other FE (full time)", 5: "Other FE (part time)",
            6: "Higher education"},
    "EMP": {1: "Paid employment, 16+ hours a week",
            2: "Paid employment, under 16 hours a week",
            3: "Self-employed, 16+ hours a week",
            4: "Self-employed, under 16 hours a week"},
    "NPE": {1: "Not in paid employment, looking for work and available",
            2: "Not in paid employment, not looking for work or not available"},
    "GAP": {1: "Gap year before starting HE"},
    "VOL": {1: "Voluntary work"},
    "SDE": {1: "Social destination (high needs learners only)"},
    "OTH": {1: "Other outcome", 2: "Not known", 3: "Learner did not respond"},
}

#: ILR ``LLDDHealthProb``: 1 yes, 9 not provided (an open SEND register
#: entry is a yes; no entry is *not* a declaration of "no").
LLDD_YES, LLDD_NOT_PROVIDED = 1, 9

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enrolment_ilr (
    enrolment_id          INTEGER PRIMARY KEY,
    fee_status            TEXT,
    fund_model            INTEGER,
    mode_override         TEXT,
    plan_learn_hours      REAL,
    plan_eep_hours        REAL,
    destination_type      TEXT,
    destination_code      INTEGER,
    destination_start     TEXT,
    destination_collected TEXT,
    notes                 TEXT,
    updated_by            TEXT,
    updated_at            TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (enrolment_id) REFERENCES enrolments(enrolment_id)
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS aim_outcomes (
    aim_id            INTEGER PRIMARY KEY,
    outcome           INTEGER NOT NULL,
    achievement_date  TEXT,
    grade             TEXT,
    notes             TEXT,
    recorded_by       TEXT,
    recorded_at       TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (aim_id) REFERENCES learning_aims(aim_id) ON DELETE CASCADE
);
"""

_READY_PATHS: set[str] = set()


def init_db() -> None:
    key = str(_en.DB_PATH)
    if key in _READY_PATHS:
        return
    _en.init_db()
    _aims.init_db()
    with _en._connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY_PATHS.add(key)


# ── Records ─────────────────────────────────────────────────────────

@dataclass
class AimOutcome:
    aim_id: int
    outcome: int
    achievement_date: str | None
    grade: str | None
    notes: str | None
    recorded_by: str | None
    recorded_at: str | None

    @property
    def label(self) -> str:
        return OUTCOMES.get(self.outcome, str(self.outcome))


@dataclass
class AimDelivery:
    """One ILR LearningDelivery: a learning aim in the enrolment's year."""
    aim_id: int
    label: str
    qualification_type: str
    subject: str
    aim_code: str | None
    start_date: str
    planned_end_date: str | None
    actual_end_date: str | None
    status: str
    comp_status: int
    withdraw_reason: str | None
    outcome: int | None
    outcome_source: str          # "recorded", "derived" or "none"
    grade: str | None
    achievement_date: str | None
    planned_hours: float | None
    counted: bool                # counts towards funded hours
    qualifying_met: bool
    withdrawn_before_qualifying: bool


@dataclass
class ILRRecord:
    enrolment_id: int
    student_id: str
    academic_year: str
    status: str
    start_date: str
    age_on_31_august: int | None
    fee_status: str | None
    fee_status_source: str       # "recorded", "derived" or "none"
    fund_model: int | None
    ffi: int | None
    mode: str | None
    mode_source: str             # "recorded" or "derived"
    plan_learn_hours: float | None
    plan_learn_hours_source: str
    plan_eep_hours: float | None
    plan_eep_hours_source: str
    high_needs: bool
    destination_type: str | None
    destination_code: int | None
    destination_start: str | None
    destination_collected: str | None
    notes: str | None
    updated_by: str | None
    updated_at: str | None
    days_in_learning: int
    qualifying_met: bool
    early_leaver: bool
    aims: list[AimDelivery] = field(default_factory=list)

    @property
    def total_hours(self) -> float:
        return round((self.plan_learn_hours or 0) + (self.plan_eep_hours or 0), 1)

    @property
    def funding_band(self) -> str | None:
        if self.fund_model != 25:
            return None
        return funding_band(self.total_hours, self.age_on_31_august,
                            high_needs=self.high_needs)

    @property
    def funded(self) -> bool:
        """ESFA funded and past (or not yet failed) the qualifying period."""
        return self.fund_model in (25, 35) and not self.early_leaver

    @property
    def fee_paying(self) -> bool:
        return self.fee_status in FEE_PAYING

    @property
    def destination_label(self) -> str | None:
        if not self.destination_type:
            return None
        label = DESTINATIONS.get(self.destination_type, {}).get(
            self.destination_code or 0)
        return f"{self.destination_type} {self.destination_code} — {label}" \
            if label else self.destination_type


def funding_band(hours: float, age: int | None = None, *,
                 high_needs: bool = False) -> str:
    """16-19 funding band for planned hours (study_programme's rule)."""
    return _programme.funding_band(hours, age, high_needs=high_needs)


def mode_for_hours(hours: float | None) -> str:
    """Full time at :data:`FULL_TIME_HOURS` planned hours or more."""
    return FULL_TIME if (hours or 0) >= FULL_TIME_HOURS else PART_TIME


# ── Helpers ─────────────────────────────────────────────────────────

def _enrolment(enrolment_id: int) -> _en.Enrolment:
    e = _en.get_enrolment(int(enrolment_id))
    if e is None:
        raise ValidationError(f"No enrolment #{enrolment_id}")
    return e


def _start(e: _en.Enrolment) -> str:
    return e.start_date or _en.academic_year_dates(e.academic_year)[0]


def year_aims(e: _en.Enrolment) -> list[Any]:
    """Every learning aim (any status) live at some point in the
    enrolment's year and belonging to it (enrolments.aims_for_enrolment)."""
    first, last = _en.academic_year_dates(e.academic_year)
    out = []
    for a in _en.aims_for_enrolment(e, active_only=False):
        finish = a.withdrawal_date or a.actual_end_date or a.planned_end_date
        if a.start_date <= last and (finish is None or finish >= first):
            out.append(a)
    return out


def _send_flags(student_id: str | None = None) -> dict[str, tuple[bool, bool]]:
    """student_id -> (open SEND register entry, EHC plan). Read only."""
    out: dict[str, tuple[bool, bool]] = {}
    try:
        from education_system.systems.sixth_form.domain.pastoral.send import send
        for entry in send.list_entries(open_only=True, student_id=student_id):
            prev = out.get(entry.student_id, (False, False))
            out[entry.student_id] = (True, prev[1] or bool(
                getattr(entry, "has_ehcp", False)))
    except Exception:  # noqa: BLE001 — the register is optional here
        logger.debug("SEND register not read", exc_info=True)
    return out


def _fee_profile(student_id: str) -> Any:
    try:
        from education_system.systems.sixth_form.domains.finance.domain.fees import (
            fee_rules,
        )
        return fee_rules.get_profile(student_id)
    except Exception:  # noqa: BLE001 — finance profile is optional here
        logger.debug("fee profile not read for %s", student_id, exc_info=True)
        return None


def derive_fee_status(student_id: str, academic_year: str, *,
                      ehcp: bool | None = None) -> str | None:
    """The fee status the records imply, or None when staff must decide
    (a 19+ learner with nothing recorded about continuing or residency)."""
    st = _students().get_student(student_id)
    profile = _fee_profile(student_id)
    if profile is not None and str(profile.residency_category).startswith(
            "International"):
        return FEE_OVERSEAS
    age = _programme.age_on_31_august(st.date_of_birth if st else None,
                                      academic_year)
    if age is None:
        return None
    if age < 19:
        return FEE_16_19
    if ehcp is None:
        ehcp = _send_flags(student_id).get(student_id, (False, False))[1]
    if profile is not None and (profile.continuing_learner
                                or (profile.has_ehcp and age < 25)):
        return FEE_16_19
    if ehcp and age < 25:
        return FEE_16_19
    return None


def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    return students


def _date(value: Any, label: str) -> str | None:
    if value in (None, ""):
        return None
    s = str(value).strip()
    try:
        _dt.date.fromisoformat(s)
    except ValueError:
        raise ValidationError(f"{label} must be a real date (YYYY-MM-DD)") from None
    return s


def _hours(value: Any, label: str) -> float | None:
    if value in (None, ""):
        return None
    try:
        h = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number of hours") from None
    if h < 0 or h > 2000:
        raise ValidationError(f"{label} must be between 0 and 2000")
    return round(h, 1)


def _outcomes(aim_ids: list[int]) -> dict[int, AimOutcome]:
    if not aim_ids:
        return {}
    init_db()
    marks = ",".join("?" * len(aim_ids))
    with _en._connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM aim_outcomes WHERE aim_id IN ({marks})",  # noqa: S608 — placeholders only
            aim_ids).fetchall()
    return {r["aim_id"]: AimOutcome(**dict(r)) for r in rows}


def _stored(enrolment_id: int) -> dict[str, Any]:
    init_db()
    with _en._connect() as conn:
        r = conn.execute("SELECT * FROM enrolment_ilr WHERE enrolment_id = ?",
                         (enrolment_id,)).fetchone()
    return dict(r) if r else {}


# ── Read ────────────────────────────────────────────────────────────

def qualifying_status(e: _en.Enrolment, *, as_of: str | None = None
                      ) -> tuple[int, bool, bool]:
    """(days in learning, qualifying period met, early leaver).

    A withdrawn enrolment counts up to its withdrawal date; a live one up
    to ``as_of`` (default today); a completed one is always met.
    """
    start = _dt.date.fromisoformat(_start(e))
    if e.status == "Completed":
        end = e.completed_at[:10] if e.completed_at else (
            _en.academic_year_dates(e.academic_year)[1])
    elif e.status == "Withdrawn":
        end = e.withdrawal_date or start.isoformat()
    else:
        end = as_of or _dt.date.today().isoformat()
    try:
        days = max(0, (_dt.date.fromisoformat(end[:10]) - start).days + 1)
    except ValueError:
        days = 0
    met = e.status == "Completed" or days >= QUALIFYING_DAYS
    return days, met, (e.status == "Withdrawn" and not met)


def get_ilr(enrolment_id: int, *, as_of: str | None = None,
            _send: dict[str, tuple[bool, bool]] | None = None) -> ILRRecord:
    """The enrolment's ILR learning delivery, recorded values over derived."""
    init_db()
    e = _enrolment(enrolment_id)
    row = _stored(e.enrolment_id)
    send = _send if _send is not None else _send_flags(e.student_id)
    on_reg, ehcp = send.get(e.student_id, (False, False))
    aims = year_aims(e)
    try:
        ph = _programme.planned_hours(e.student_id, e.academic_year,
                                      high_needs=ehcp)
    except Exception:  # noqa: BLE001 — hours are best effort, shown as missing
        logger.debug("planned hours unavailable for %s", e.student_id,
                     exc_info=True)
        ph = None
    by_aim = {h.aim.aim_id: h for h in (ph.aims if ph else [])}
    outcomes = _outcomes([a.aim_id for a in aims])
    withdraw_reason = e.withdrawal_reason if e.status == "Withdrawn" else None

    deliveries: list[AimDelivery] = []
    qual_hours = 0.0
    for a in aims:
        h = by_aim.get(a.aim_id)
        planned = h.planned_hours if h else a.planned_hours
        counted = h.counted if h else True
        if counted and planned:
            qual_hours += planned
        chk = _aims.qualifying_check_for(a, as_of=as_of)
        rec = outcomes.get(a.aim_id)
        if rec is not None:
            outcome, src = rec.outcome, "recorded"
        elif a.status == "Completed":
            outcome, src = 8, "derived"
        elif a.status in ("Withdrawn", "Transferred"):
            outcome, src = 3, "derived"
        else:
            outcome, src = None, "none"
        comp = COMP_STATUS.get(a.status, 1)
        deliveries.append(AimDelivery(
            aim_id=a.aim_id, label=a.label,
            qualification_type=a.qualification_type, subject=a.subject,
            aim_code=a.aim_code, start_date=a.start_date,
            planned_end_date=a.planned_end_date,
            actual_end_date=((a.withdrawal_date or a.actual_end_date)
                             if a.status != "Active" else None),
            status=a.status, comp_status=comp,
            withdraw_reason=((withdraw_reason or (
                a.withdrawal_reason if a.withdrawal_reason in _REASON_CODES
                else None)) if comp == 3 else None),
            outcome=outcome, outcome_source=src,
            grade=rec.grade if rec else None,
            achievement_date=rec.achievement_date if rec else None,
            planned_hours=planned, counted=counted,
            qualifying_met=chk.met,
            withdrawn_before_qualifying=chk.withdrawn_before_qualifying))

    if row.get("plan_learn_hours") is not None:
        learn, learn_src = float(row["plan_learn_hours"]), "recorded"
    else:
        learn = round(qual_hours, 1) if aims else None
        learn_src = "derived" if learn else "none"
    if row.get("plan_eep_hours") is not None:
        eep, eep_src = float(row["plan_eep_hours"]), "recorded"
    else:
        eep = ph.non_qualification_hours if ph else None
        eep_src = "derived" if ph is not None else "none"

    fee = row.get("fee_status")
    fee_src = "recorded" if fee else "none"
    if not fee:
        fee = derive_fee_status(e.student_id, e.academic_year, ehcp=ehcp)
        fee_src = "derived" if fee else "none"
    fund_model = row.get("fund_model") or (FEE_STATUS_FUND_MODEL.get(fee)
                                           if fee else None)
    total = (learn or 0) + (eep or 0)
    mode = row.get("mode_override") or mode_for_hours(total)
    days, met, early = qualifying_status(e, as_of=as_of)
    st = _students().get_student(e.student_id)
    return ILRRecord(
        enrolment_id=e.enrolment_id, student_id=e.student_id,
        academic_year=e.academic_year, status=e.status, start_date=_start(e),
        age_on_31_august=_programme.age_on_31_august(
            st.date_of_birth if st else None, e.academic_year),
        fee_status=fee, fee_status_source=fee_src, fund_model=fund_model,
        ffi=FEE_STATUS_FFI.get(fee or "") if fund_model == 35 else None,
        mode=mode, mode_source="recorded" if row.get("mode_override") else "derived",
        plan_learn_hours=learn, plan_learn_hours_source=learn_src,
        plan_eep_hours=eep, plan_eep_hours_source=eep_src,
        high_needs=ehcp,
        destination_type=row.get("destination_type"),
        destination_code=row.get("destination_code"),
        destination_start=row.get("destination_start"),
        destination_collected=row.get("destination_collected"),
        notes=row.get("notes"), updated_by=row.get("updated_by"),
        updated_at=row.get("updated_at"),
        days_in_learning=days, qualifying_met=met, early_leaver=early,
        aims=deliveries)


_REASON_CODES = {code for code, _label in _en.WITHDRAWAL_REASONS}


# ── Write ───────────────────────────────────────────────────────────

#: Keys :func:`set_ilr` accepts. A key given as None / "" clears the
#: recorded value so the derived one applies again.
ILR_FIELDS: tuple[str, ...] = (
    "fee_status", "fund_model", "mode", "plan_learn_hours", "plan_eep_hours",
    "destination_type", "destination_code", "destination_start",
    "destination_collected", "notes",
)


def _validate(data: dict[str, Any], current: dict[str, Any],
              e: _en.Enrolment) -> dict[str, Any]:
    unknown = set(data) - set(ILR_FIELDS)
    if unknown:
        raise ValidationError(f"Unknown ILR field(s): {', '.join(sorted(unknown))}")
    out: dict[str, Any] = {}
    if "fee_status" in data:
        fee = (data["fee_status"] or "").strip() or None
        if fee is not None and fee not in FEE_STATUSES:
            raise ValidationError(
                f"Fee status must be one of: {', '.join(FEE_STATUSES)}")
        out["fee_status"] = fee
    if "fund_model" in data:
        fm = data["fund_model"]
        if fm in (None, ""):
            out["fund_model"] = None
        else:
            try:
                fm = int(fm)
            except (TypeError, ValueError):
                raise ValidationError("Funding model must be 25, 35 or 99") from None
            if fm not in FUND_MODELS:
                raise ValidationError("Funding model must be 25 (16-19), "
                                      "35 (adult skills) or 99 (no ESFA funding)")
            out["fund_model"] = fm
    fee = out.get("fee_status", current.get("fee_status"))
    if "fee_status" in out and "fund_model" not in out:
        out["fund_model"] = FEE_STATUS_FUND_MODEL.get(fee) if fee else None
    fm = out.get("fund_model", current.get("fund_model"))
    if fee and fm is not None and FEE_STATUS_FUND_MODEL[fee] != fm:
        raise ValidationError(
            f"Fee status '{fee}' is reported under funding model "
            f"{FEE_STATUS_FUND_MODEL[fee]}, not {fm}")
    if "mode" in data:
        mode = (data["mode"] or "").strip() or None
        if mode is not None and mode not in MODES:
            raise ValidationError(f"Mode must be one of: {', '.join(MODES)}")
        out["mode_override"] = mode
    for key, label in (("plan_learn_hours", "Planned learning hours"),
                       ("plan_eep_hours", "Planned EEP hours")):
        if key in data:
            out[key] = _hours(data[key], label)
    if "destination_type" in data or "destination_code" in data:
        dtype = data.get("destination_type", current.get("destination_type"))
        dtype = (dtype or "").strip().upper() or None
        code = data.get("destination_code", current.get("destination_code"))
        if dtype is None:
            out["destination_type"] = out["destination_code"] = None
        else:
            if dtype not in DESTINATIONS:
                raise ValidationError("Destination type must be one of: "
                                      + ", ".join(DESTINATIONS))
            try:
                code = int(code)
            except (TypeError, ValueError):
                raise ValidationError("Destination code is required") from None
            if code not in DESTINATIONS[dtype]:
                raise ValidationError(
                    f"{dtype} code must be one of: "
                    + ", ".join(str(c) for c in DESTINATIONS[dtype]))
            out["destination_type"], out["destination_code"] = dtype, code
    for key, label in (("destination_start", "Destination start date"),
                       ("destination_collected", "Destination collected on")):
        if key in data:
            out[key] = _date(data[key], label)
    collected = out.get("destination_collected",
                        current.get("destination_collected"))
    if collected and collected > _dt.date.today().isoformat():
        raise ValidationError("Destination collected on cannot be in the future")
    if collected and collected < _start(e):
        raise ValidationError("Destination collected on is before the enrolment started")
    if "notes" in data:
        out["notes"] = (data["notes"] or "").strip() or None
    return out


def set_ilr(enrolment_id: int, data: dict[str, Any]) -> ILRRecord:
    """Record (or clear, with None) ILR fields for an enrolment.

    Raises ValidationError with a message for the screen; AccessDenied
    without the enrolment writer capability.
    """
    _en._require_writer("record ILR details")
    init_db()
    e = _enrolment(enrolment_id)
    if e.is_archived:
        raise ValidationError("This enrolment is archived — restore it first")
    current = _stored(e.enrolment_id)
    p = _validate(dict(data or {}), current, e)
    changes = [f"{k}: {current.get(k)!r} → {v!r}" for k, v in p.items()
               if current.get(k) != v]
    if not changes:
        return get_ilr(e.enrolment_id)
    with _en._connect() as conn:
        if not current:
            conn.execute("INSERT INTO enrolment_ilr (enrolment_id) VALUES (?)",
                         (e.enrolment_id,))
        sets = ", ".join(f"{k} = ?" for k in p)
        conn.execute(
            f"UPDATE enrolment_ilr SET {sets}, updated_by = ?, "  # noqa: S608 — keys validated
            "updated_at = datetime('now') WHERE enrolment_id = ?",
            (*p.values(), _en._actor(), e.enrolment_id))
        _en._log(conn, e, "ILR updated", "; ".join(changes))
        conn.commit()
    return get_ilr(e.enrolment_id)


def _enrolment_for_aim(aim: Any) -> _en.Enrolment | None:
    for e in _en.list_for_student(aim.student_id):  # newest year first
        if any(a.aim_id == aim.aim_id for a in year_aims(e)):
            return e
    return None


def get_aim_outcome(aim_id: int) -> AimOutcome | None:
    return _outcomes([int(aim_id)]).get(int(aim_id))


def set_aim_outcome(aim_id: int, outcome: int, *,
                    achievement_date: str | None = None,
                    grade: str | None = None,
                    notes: str | None = None) -> AimOutcome:
    """Record an aim's ILR outcome. The aim must have ended: a completed
    aim may take 1/2/3/8, a withdrawn or transferred one 2/3. A grade is
    checked against the aim's qualification type."""
    _en._require_writer("record an aim outcome")
    init_db()
    aim = _aims.get_aim(int(aim_id))
    if aim is None:
        raise ValidationError(f"No learning aim #{aim_id}")
    try:
        outcome = int(outcome)
    except (TypeError, ValueError):
        raise ValidationError("Outcome must be 1, 2, 3 or 8") from None
    if outcome not in OUTCOMES:
        raise ValidationError("Outcome must be 1 (achieved), 2 (partial), "
                              "3 (no achievement) or 8 (not yet known)")
    allowed = _OUTCOMES_FOR_STATUS.get(aim.status)
    if allowed is None:
        raise ValidationError(f"{aim.label} is still continuing — complete or "
                              "withdraw the aim before recording an outcome")
    if outcome not in allowed:
        raise ValidationError(
            f"A {aim.status.lower()} aim can take outcome "
            + " or ".join(str(o) for o in allowed))
    ach = _date(achievement_date, "Achievement date")
    if ach is not None:
        if outcome not in (1, 2):
            raise ValidationError("An achievement date only goes with outcome 1 or 2")
        if ach < aim.start_date:
            raise ValidationError("Achievement date is before the aim started")
        if ach > _dt.date.today().isoformat():
            raise ValidationError("Achievement date cannot be in the future")
    g = (grade or "").strip() or None
    if g is not None:
        try:
            from education_system.systems.sixth_form.domain.academics.qualifications import (
                grade_scales,
            )
            g = grade_scales.validate_grade(g, aim.qualification_type)
        except ValueError as exc:
            raise ValidationError(str(exc)) from None
    who = _en._actor()
    note = (notes or "").strip() or None
    e = _enrolment_for_aim(aim)
    with _en._connect() as conn:
        conn.execute(
            """INSERT INTO aim_outcomes (aim_id, outcome, achievement_date,
                   grade, notes, recorded_by, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
               ON CONFLICT(aim_id) DO UPDATE SET outcome = excluded.outcome,
                   achievement_date = excluded.achievement_date,
                   grade = excluded.grade, notes = excluded.notes,
                   recorded_by = excluded.recorded_by,
                   recorded_at = excluded.recorded_at""",
            (aim.aim_id, outcome, ach, g, note, who))
        if e is not None:
            _en._log(conn, e, "Aim outcome",
                     f"{aim.label} (#{aim.aim_id}): {outcome} {OUTCOMES[outcome]}"
                     + (f", grade {g}" if g else ""))
        conn.commit()
    out = get_aim_outcome(aim.aim_id)
    assert out is not None
    return out


def clear_aim_outcome(aim_id: int) -> bool:
    """Remove a recorded outcome (the derived one applies again)."""
    _en._require_writer("clear an aim outcome")
    init_db()
    aim = _aims.get_aim(int(aim_id))
    if aim is None:
        return False
    e = _enrolment_for_aim(aim)
    with _en._connect() as conn:
        cur = conn.execute("DELETE FROM aim_outcomes WHERE aim_id = ?",
                           (aim.aim_id,))
        if cur.rowcount:
            if e is not None:
                _en._log(conn, e, "Aim outcome cleared",
                         f"{aim.label} (#{aim.aim_id})")
        conn.commit()
        return cur.rowcount > 0


# ── Early leavers ───────────────────────────────────────────────────

@dataclass
class EarlyLeaver:
    enrolment_id: int
    student_id: str
    student_name: str
    year_group: int
    tutor_group: str | None
    start_date: str
    withdrawal_date: str | None
    withdrawal_reason: str | None
    days_in_learning: int
    aims_before_qualifying: list[str] = field(default_factory=list)


def early_leavers(academic_year: str) -> list[EarlyLeaver]:
    """Enrolments withdrawn before the 42-day qualifying period: not funded."""
    out: list[EarlyLeaver] = []
    names = {}
    for e in _en.list_enrolments(academic_year=academic_year, status="Withdrawn"):
        days, _met, early = qualifying_status(e)
        if not early:
            continue
        if not names:
            names = {s.student_id: s.full_name
                     for s in _students().list_students()}
        aims = [a.label for a in year_aims(e)
                if _aims.qualifying_check_for(a).withdrawn_before_qualifying]
        out.append(EarlyLeaver(
            enrolment_id=e.enrolment_id, student_id=e.student_id,
            student_name=names.get(e.student_id, "(unknown)"),
            year_group=e.year_group, tutor_group=e.tutor_group,
            start_date=_start(e), withdrawal_date=e.withdrawal_date,
            withdrawal_reason=e.withdrawal_reason, days_in_learning=days,
            aims_before_qualifying=aims))
    out.sort(key=lambda r: (r.withdrawal_date or "", r.student_id))
    return out


# ── Export ──────────────────────────────────────────────────────────
#
# There is one ILR file and it is built in one place: the census_ilr
# return builder (Finance & Bursaries → Census ILR). It takes its learning
# delivery from the records above (get_ilr, year_aims, aim outcomes), so
# what is recorded on the Enrolment screens appears in it. export_csv is
# kept, with the same signature and result, so the Enrolment screens'
# "ILR Export" produces exactly the Census ILR screens' file.

_EXPORT_NAMES = {"ExportProblem": "ExportProblem",
                 "ExportResult": "ExportResult",
                 "EXPORT_COLUMNS": "ILR_CSV_COLUMNS"}


def _export_module():
    from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
        return_export,
    )
    return return_export


def __getattr__(name: str) -> Any:
    """``ExportResult`` / ``ExportProblem`` / ``EXPORT_COLUMNS`` are the
    census_ilr export's own (one definition, imported on first use)."""
    if name in _EXPORT_NAMES:
        return getattr(_export_module(), _EXPORT_NAMES[name])
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def export_csv(academic_year: str, *, path: str | Path | None = None,
               as_of: str | None = None) -> Any:
    """The ILR Learner + LearningDelivery file for the year, with its
    problems (``ExportResult``); written to ``path`` when given.

    Delegates to ``census_ilr.return_export.export_ilr_csv`` — the single
    ILR export — which needs ``funding``, ``admissions`` or
    ``students.manage`` and logs the export as sensitive access.
    """
    return _export_module().export_ilr_csv(academic_year, path=path, as_of=as_of)
