"""Generate a census / ILR return from the records the college already holds.

The return used to be a hand-typed register: somebody re-keyed every
learner and every aim from the student record into ``learner_aims``.
:func:`generate_return` builds it instead:

* **learners** (``return_learners``) — one row per learner in the
  funding year: ULN, name, date of birth, sex, postcode (student record,
  else the last CTF import), ethnicity (only if the student record holds
  it), LLDD flag (open entry on the SEND register — read only), EHCP,
  average GCSE point score and best English / maths grades, age on
  31 August, planned hours and 16-19 funding band, condition-of-funding
  position, and census-period attendance;
* **aims** (``learner_aims`` rows with ``source = 'generated'``) — one per
  learning aim live in the year: aim (QAN / LARS) reference, start,
  planned end and actual end dates, planned hours, completion status,
  outcome and grade (from released exam results), and whether the aim
  reached its funding qualifying period.

**Manual edits are kept as overrides.** Editing a generated aim (through
``census_ilr.update_aim``) or learner (:func:`update_learner`) records
the field in ``overrides``; regeneration refreshes every other field and
leaves overridden ones alone. Aims typed in by hand (``source =
'manual'``) are never touched.

A sixth form *in a school* files the **school census** (post-16 learning
aims module); a sixth-form *college* files the **ILR**. The choice is a
setting (:func:`set_route`), used by validation and export.

**Learning delivery comes from the enrolment.** When the learner has a
started enrolment for the year (Enrolled / Withdrawn / Completed, not
archived), the per-enrolment ILR record (``enrolments.ilr.get_ilr``) is
the source of the aims in the year, fee status, funding model
(``FundModel``) and FFI, mode, planned learning and EEP hours
(``PlanLearnHours`` / ``PlanEEPHours``), funding band, age, completion
status (``CompStatus``), ILR withdrawal reason code, early leaver and
qualifying period, destination, and any aim outcome recorded on the
Enrolment screens (``aim_outcomes``: outcome, grade, achievement date).
An outcome not recorded there is still derived from released exam
results. A learner with no enrolment for the year falls back to the
learning aims and study programme directly (and validation says so).

There is **one ILR file**: :func:`return_export.export_ilr_csv` builds it
from these same rows (:func:`_build_year`, in memory) for both the Census
ILR screens and the Enrolment screens (``ilr.export_csv`` delegates).

Sources (public functions only):
QUAL ``learning_aims``, ``prior_attainment``, ``study_programme``,
``identifiers``; ATTEND ``attendance_census``; SEND register
``list_entries``; exam results ``list_results``; LRS
``last_known_postcode``; enrolments ``list_enrolments``; enrolment ILR
``get_ilr``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field, fields
from typing import Any

from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
    census_ilr as core,
)

logger = logging.getLogger(__name__)

ValidationError = core.ValidationError

# ── Settings ───────────────────────────────────────────────────────

ROUTE_ILR = "ILR"
ROUTE_SCHOOL_CENSUS = "School Census"
ROUTES: tuple[str, ...] = (ROUTE_ILR, ROUTE_SCHOOL_CENSUS)
DEFAULT_ROUTE = ROUTE_ILR

SETTING_KEYS: tuple[str, ...] = ("route", "ukprn", "provider_name",
                                 "laestab", "urn")


def get_settings() -> dict[str, str | None]:
    core.init_db()
    with core._connect() as conn:
        rows = {r["key"]: r["value"] for r in conn.execute(
            "SELECT key, value FROM census_ilr_settings")}
    out = {k: rows.get(k) for k in SETTING_KEYS}
    out["route"] = out["route"] or DEFAULT_ROUTE
    return out


def set_setting(key: str, value: str | None) -> None:
    if key not in SETTING_KEYS:
        raise ValidationError(f"Unknown setting {key!r}")
    v = (value or "").strip() or None
    if key == "route" and v not in ROUTES:
        raise ValidationError(f"Route must be one of: {', '.join(ROUTES)}")
    if key == "ukprn" and v and not re.fullmatch(r"1\d{7}", v):
        raise ValidationError("UKPRN is 8 digits starting with 1")
    if key == "laestab" and v and not re.fullmatch(r"\d{7}", v):
        raise ValidationError("LAESTAB is 7 digits (LA code + establishment)")
    core.init_db()
    with core._connect() as conn:
        conn.execute(
            "INSERT INTO census_ilr_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, v))


def get_route() -> str:
    return get_settings()["route"] or DEFAULT_ROUTE


def set_route(route: str) -> None:
    set_setting("route", route)


# ── Access ─────────────────────────────────────────────────────────

def _guard(action: str) -> Any:
    """A generated return holds personal and SEND data: FUNDING only."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    if not p.can(access.FUNDING):
        access.log_sensitive_access(p, "census_ilr", action, allowed=False)
        p.require(access.FUNDING, action)
    access.log_sensitive_access(p, "census_ilr", action)
    return p


def _ilr_export_guard() -> Any:
    """The ILR file holds personal and SEND data. Exporting it is open to
    funding, admissions or students.manage (the Enrolment screens' users
    as well as Finance) and is always logged as sensitive access."""
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    caps = (access.FUNDING, access.ADMISSIONS, access.STUDENTS_MANAGE)
    if not any(p.can(c) for c in caps):
        access.log_sensitive_access(p, "ilr", "export ILR", allowed=False)
        p.require(caps[0], "export the ILR")
    access.log_sensitive_access(p, "ilr", "export ILR")
    return p


# ── Year helpers ───────────────────────────────────────────────────

def normalise_year(value: str | None) -> str:
    """'2025/26' from '2025/26', '2025-26', '2025-2026' or '2025'."""
    m = re.match(r"^\s*(\d{4})", value or "")
    if not m:
        raise ValidationError(
            f"Cannot read an academic year from {value!r} (use '2025/26')")
    y = int(m.group(1))
    return f"{y}/{str(y + 1)[-2:]}"


def year_bounds(academic_year: str) -> tuple[str, str]:
    """1 August to 31 July — the funding year."""
    y = int(normalise_year(academic_year)[:4])
    return _dt.date(y, 8, 1).isoformat(), _dt.date(y + 1, 7, 31).isoformat()


def current_year() -> str:
    t = _dt.date.today()
    y = t.year if t.month >= 8 else t.year - 1
    return f"{y}/{str(y + 1)[-2:]}"


def aim_in_year(aim: Any, academic_year: str) -> bool:
    """Same rule as study_programme: the aim overlaps the funding year."""
    start, end = year_bounds(academic_year)
    finish = aim.withdrawal_date or aim.actual_end_date or aim.planned_end_date
    return aim.start_date <= end and (finish is None or finish >= start)


# ── Lazy imports of other agents' modules ──────────────────────────

def _students():
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    return students


def _aims():
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims,
    )
    return learning_aims


def _prior():
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        prior_attainment,
    )
    return prior_attainment


def _programme():
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        study_programme,
    )
    return study_programme


def _enrolments():
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments,
    )
    return enrolments


def _ilr():
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        ilr,
    )
    return ilr


#: Enrolment ILR ``FundModel`` -> the return's funding model name.
FUND_MODEL_NAMES: dict[int, str] = {
    25: core.DEFAULT_FUNDING_MODEL,
    35: "Adult Skills",
    99: "Other",
}


def year_enrolments(academic_year: str) -> dict[str, Any]:
    """student_id -> the learner's started enrolment for the year
    (Enrolled / Withdrawn / Completed; Pending and archived are left out,
    as the ILR leaves them out)."""
    out: dict[str, Any] = {}
    try:
        rows = _enrolments().list_enrolments(
            academic_year=normalise_year(academic_year))
    except Exception:
        logger.warning("Enrolments unavailable for the return", exc_info=True)
        return out
    for e in rows:
        if e.status != "Pending":
            out.setdefault(e.student_id, e)
    return out


def _ilr_reason_code(reason: str | None) -> str | None:
    """*reason* when it is an ILR WithdrawReason code, else None."""
    codes = {c for c, _label in _enrolments().WITHDRAWAL_REASONS}
    return reason if reason in codes else None


# ── Per-learner source data ────────────────────────────────────────

_SEX = {"male": "M", "m": "M", "female": "F", "f": "F"}


def _student_columns() -> set[str]:
    """Columns on the students table (postcode / ethnicity / upn may or
    may not exist depending on which modules have extended it)."""
    s = _students()
    s.init_db()
    conn = db.connect(str(s.DB_PATH))
    try:
        return {r[1] for r in conn.execute("PRAGMA table_info(students)")}
    finally:
        conn.close()


def _student_extras(student_id: str, cols: set[str]) -> dict[str, Any]:
    """postcode / ethnicity / upn straight from the students row, if held."""
    wanted = [c for c in ("postcode", "ethnicity", "upn") if c in cols]
    if not wanted:
        return {}
    s = _students()
    conn = db.connect(str(s.DB_PATH))
    conn.row_factory = db.Row
    try:
        r = conn.execute(
            f"SELECT {', '.join(wanted)} FROM students WHERE student_id = ?",
            (student_id,)).fetchone()
    finally:
        conn.close()
    return dict(r) if r else {}


def _postcode(student_id: str, extras: dict[str, Any]) -> str | None:
    pc = (extras.get("postcode") or "").strip().upper()
    if pc:
        return pc
    try:
        from education_system.systems.sixth_form.infrastructure.integrations import lrs
        return lrs.last_known_postcode(student_id)
    except Exception:
        logger.debug("No CTF postcode for %s", student_id, exc_info=True)
        return None


def _send_flags() -> dict[str, tuple[bool, bool, str]]:
    """student_id -> (on register, has EHCP, register status). Read only."""
    out: dict[str, tuple[bool, bool, str]] = {}
    try:
        from education_system.systems.sixth_form.domain.pastoral.send import send
        for e in send.list_entries(open_only=True):
            prev = out.get(e.student_id)
            ehcp = e.has_ehcp or (prev[1] if prev else False)
            out[e.student_id] = (True, ehcp,
                                 "EHCP" if ehcp else e.register_status)
    except Exception:
        logger.warning("SEND register unavailable for the return",
                       exc_info=True)
    return out


# Building an attendance extract walks the calendar day by day, which is
# slow over a whole year; generate, validate and the measures all want
# the same extract within seconds of each other, so it is cached briefly.
_ATT_CACHE: dict[tuple[str, str, str], tuple[float, Any]] = {}
ATTENDANCE_CACHE_SECONDS = 300


def attendance_extract(kind: str, date_from: str, date_to: str, *,
                       fresh: bool = False) -> Any:
    """ATTEND's attendance return (``attendance_census.census_extract`` /
    ``ilr_extract``) for the period, cached for a few minutes.

    ``kind`` is ``"census"`` or ``"ilr"``. Raises what ATTEND raises.
    """
    import time
    from education_system.systems.sixth_form.domain.academics.attendance import (
        attendance_census,
    )
    key = (kind, date_from, date_to)
    hit = _ATT_CACHE.get(key)
    if hit and not fresh and time.monotonic() - hit[0] < ATTENDANCE_CACHE_SECONDS:
        return hit[1]
    fn = (attendance_census.census_extract if kind == attendance_census.CENSUS
          else attendance_census.ilr_extract)
    ret = fn(date_from=date_from, date_to=date_to)
    _ATT_CACHE[key] = (time.monotonic(), ret)
    return ret


def route_attendance_kind(route: str) -> str:
    return "census" if route == ROUTE_SCHOOL_CENSUS else "ilr"


def _attendance_rows(date_from: str, date_to: str,
                     route: str) -> tuple[dict[str, Any], Any]:
    """ATTEND's census / ILR attendance extract, keyed by student."""
    try:
        ret = attendance_extract(route_attendance_kind(route), date_from,
                                 date_to, fresh=True)
        return {r.student_id: r for r in ret.rows}, ret
    except Exception:
        logger.warning("Attendance extract unavailable", exc_info=True)
        return {}, None


def _aim_type_for(aim: Any) -> str:
    if aim.is_core_aim:
        return "Core Aim"
    area = _prior().area_for_subject(_strip_prefix(aim.subject))
    if area == "English" and aim.qualification_type in (
            "GCSE", "Functional Skills"):
        return "English"
    if area == "Maths" and aim.qualification_type in (
            "GCSE", "Functional Skills"):
        return "Maths"
    return "Programme Aim"


def _strip_prefix(subject: str) -> str:
    return re.sub(r"^(gcse|functional skills|fs)\s+", "", subject.strip(),
                  flags=re.I)


def _outcome(aim: Any, result: Any) -> tuple[str, int, str | None, str | None]:
    """(census_ilr status, completion code, outcome code, grade).

    Completion codes follow census_ilr.COMPLETION_CODES; outcome codes
    the ILR's (1 achieved, 3 no achievement, 8 not yet known).
    """
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    grade = result.grade if result else None
    if aim.status == "Withdrawn":
        return "Withdrawn", 3, "3", grade
    if aim.status == "Transferred":
        return "Transferred", 7, "3", grade
    if aim.status == "Completed" or (aim.status == "Active" and grade):
        if grade is None:
            return "Completed", 2, "8", None
        if grade_scales.is_pass(grade, aim.qualification_type):
            return "Achieved", 2, "1", grade
        return "Not Achieved", 10, "3", grade
    return "Continuing", 1, None, None


#: A recorded outcome on a completed aim -> (census_ilr status, completion code).
_RECORDED_COMPLETED: dict[int, tuple[str, int]] = {
    1: ("Achieved", 2), 2: ("Partially Achieved", 2),
    3: ("Not Achieved", 10), 8: ("Completed", 2),
}


def _delivery_outcome(aim: Any, delivery: Any, result: Any
                      ) -> tuple[str, int, str | None, str | None]:
    """:func:`_outcome`, except that an outcome recorded on the Enrolment
    screens (``aim_outcomes``) wins over the exam-result derivation."""
    if delivery is None or delivery.outcome_source != "recorded":
        return _outcome(aim, result)
    grade = delivery.grade or (result.grade if result else None)
    code = str(delivery.outcome)
    if aim.status == "Withdrawn":
        return "Withdrawn", 3, code, grade
    if aim.status == "Transferred":
        return "Transferred", 7, code, grade
    status, cc = _RECORDED_COMPLETED.get(delivery.outcome, ("Completed", 2))
    return status, cc, code, grade


# ── Generation ─────────────────────────────────────────────────────

@dataclass
class GenerateResult:
    return_id: int
    academic_year: str
    route: str
    learners: int = 0
    learners_kept_overrides: int = 0
    aims_created: int = 0
    aims_updated: int = 0
    aims_removed: int = 0
    aims_orphaned: int = 0          # source aim gone, kept for its overrides
    attendance_summary: str | None = None
    messages: list[str] = field(default_factory=list)

    @property
    def summary(self) -> str:
        bits = [f"{self.learners} learner(s)",
                f"{self.aims_created} aim(s) added",
                f"{self.aims_updated} refreshed",
                f"{self.aims_removed} removed"]
        if self.aims_orphaned:
            bits.append(f"{self.aims_orphaned} kept for overrides")
        return (f"{self.route} {self.academic_year}: " + ", ".join(bits))


# Learner fields a user may override; editing one records it.
OVERRIDABLE_LEARNER_FIELDS: tuple[str, ...] = (
    "uln", "family_name", "given_names", "date_of_birth", "sex",
    "postcode", "ethnicity", "lldd", "ehcp", "prior_attainment",
    "gcse_english", "gcse_maths", "planned_hours", "planned_qual_hours",
    "planned_eep_hours", "funding_band", "learner_status",
)

#: Learner fields taken from the enrolment's ILR record. They are edited
#: on the Enrolment screens (ILR details), not overridden here.
ILR_LEARNER_FIELDS: tuple[str, ...] = (
    "enrolment_id", "fee_status", "fund_model", "ffi", "study_mode",
    "early_leaver", "destination_type", "destination_code",
    "destination_start", "destination_collected",
)

_LEARNER_GENERATED: tuple[str, ...] = OVERRIDABLE_LEARNER_FIELDS + (
    "learner_ref", "send_status", "age_31_aug", "cof_english",
    "cof_maths", "cof_compliant", "attendance_pct", "hours_attended",
) + ILR_LEARNER_FIELDS

_AIM_GENERATED: tuple[str, ...] = (
    "learner_ref", "learner_name", "ukprn", "uln", "aim_type",
    "aim_reference", "aim_title", "funding_model", "start_date",
    "planned_end_date", "actual_end_date", "completion_code",
    "outcome_code", "status", "planned_hours", "student_id",
    "qualification_type", "outcome_grade", "withdrawal_reason",
    "qualifying_met", "withdraw_reason_code", "outcome_source",
    "achievement_date",
)


def build_learner(student: Any, academic_year: str, *, as_of: str,
                  cols: set[str], send_flags: dict, attendance: dict,
                  ukprn: str | None, enrolment: Any = None
                  ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(learner row, aim rows) for one student — pure read, no writes here.

    *enrolment* is the learner's started enrolment for the year (see
    :func:`year_enrolments`); when given, its ILR record supplies the
    learning delivery. Returns ``({}, [])`` when the learner has nothing
    in the year, is not on roll and has no enrolment for it.
    """
    from education_system.systems.sixth_form.domain.assessment.value_added import (
        derivation,
    )
    sid = student.student_id
    all_aims = _aims().list_aims(sid)
    aims = [a for a in all_aims if aim_in_year(a, academic_year)]
    if not aims and student.status != "Active" and enrolment is None:
        return {}, []
    on_reg, ehcp, send_status = send_flags.get(sid, (False, False, None))
    rec = None
    if enrolment is not None:
        try:
            rec = _ilr().get_ilr(enrolment.enrolment_id, as_of=as_of,
                                 _send={sid: (on_reg, ehcp)})
        except Exception:
            logger.warning("ILR record unavailable for enrolment #%s",
                           enrolment.enrolment_id, exc_info=True)
    extras = _student_extras(sid, cols)
    pa = _prior().prior_attainment(sid)
    ph = None
    if rec is None:
        try:
            ph = _programme().planned_hours(sid, academic_year, high_needs=ehcp)
        except Exception:
            logger.debug("planned hours failed for %s", sid, exc_info=True)
    try:
        cof = _prior().funding_condition(sid)
    except Exception:
        logger.debug("CoF failed for %s", sid, exc_info=True)
        cof = None
    att = attendance.get(sid)
    uln = (getattr(student, "uln", None) or "").strip() or None
    learner = {
        "student_id": sid,
        "learner_ref": sid[:12],
        "uln": uln,
        "family_name": student.last_name,
        "given_names": " ".join(x for x in (student.first_name,
                                            student.middle_name) if x),
        "date_of_birth": student.date_of_birth,
        "sex": _SEX.get((student.gender or "").strip().lower()),
        "postcode": _postcode(sid, extras),
        "ethnicity": (str(extras.get("ethnicity")).strip()
                      if extras.get("ethnicity") else None),
        "lldd": 1 if on_reg else 0,
        "ehcp": 1 if ehcp else 0,
        "send_status": send_status,
        "prior_attainment": pa.average_point_score,
        "gcse_english": pa.best_english_grade,
        "gcse_maths": pa.best_maths_grade,
        "cof_english": cof.english.status if cof else None,
        "cof_maths": cof.maths.status if cof else None,
        "cof_compliant": (1 if cof.compliant else 0) if cof else None,
        "attendance_pct": att.attendance_pct if att else None,
        "hours_attended": (att.hours_attended if att and att.hours_attended
                           else None),
        "learner_status": student.status,
    }
    if rec is not None:
        learner.update(_ilr_learner_fields(rec))
    else:
        learner.update({
            "age_31_aug": (ph.age_on_31_august if ph else
                           _programme().age_on_31_august(
                               student.date_of_birth, academic_year)),
            "planned_hours": ph.total_hours if ph else None,
            "planned_qual_hours": ph.qualification_hours if ph else None,
            "planned_eep_hours": ph.non_qualification_hours if ph else None,
            "funding_band": ph.band if ph else None,
        })
    results = derivation.actual_results_for(sid)
    aim_rows: list[dict[str, Any]] = []
    if rec is not None:
        by_id = {a.aim_id: a for a in all_aims}
        pairs = [(by_id[d.aim_id], d) for d in rec.aims if d.aim_id in by_id]
        fund_model = FUND_MODEL_NAMES.get(rec.fund_model or 0,
                                          core.DEFAULT_FUNDING_MODEL)
    else:
        pairs = [(a, None) for a in aims]
        fund_model = core.DEFAULT_FUNDING_MODEL
        hours_by_aim = {h.aim.aim_id: h for h in (ph.aims if ph else [])}
    for a, d in pairs:
        res = results.get(a.subject)
        status, cc, outcome, grade = _delivery_outcome(a, d, res)
        if d is not None:
            planned_f = d.planned_hours
            met = d.qualifying_met
            reason_code = d.withdraw_reason
            ended = d.actual_end_date
        else:
            h = hours_by_aim.get(a.aim_id)
            planned_f = (h.planned_hours if h and h.planned_hours
                         else a.planned_hours)
            met = _aims().qualifying_check_for(a, as_of=as_of).met
            reason_code = (_ilr_reason_code(a.withdrawal_reason)
                           if a.status in ("Withdrawn", "Transferred")
                           else None)
            ended = ((a.withdrawal_date or a.actual_end_date)
                     if a.status != "Active" else None)
        aim_rows.append({
            "source_aim_id": a.aim_id,
            "student_id": sid,
            "learner_ref": learner["learner_ref"],
            "learner_name": student.full_name,
            "ukprn": ukprn,
            "uln": uln,
            "aim_type": _aim_type_for(a),
            "aim_reference": (a.aim_code or "").strip(),
            "aim_title": a.label,
            "funding_model": fund_model,
            "start_date": a.start_date,
            "planned_end_date": a.planned_end_date,
            "actual_end_date": ended,
            "completion_code": cc,
            "outcome_code": outcome,
            "status": status,
            "planned_hours": int(round(planned_f)) if planned_f else None,
            "qualification_type": a.qualification_type,
            "outcome_grade": grade,
            "withdrawal_reason": a.withdrawal_reason,
            "qualifying_met": 1 if met else 0,
            "withdraw_reason_code": reason_code,
            "outcome_source": ("recorded" if d is not None
                               and d.outcome_source == "recorded"
                               else ("derived" if outcome else None)),
            "achievement_date": d.achievement_date if d is not None else None,
        })
    return learner, aim_rows


def _ilr_learner_fields(rec: Any) -> dict[str, Any]:
    """Learner columns from an enrolment's ILR record (recorded over derived)."""
    total = (rec.total_hours
             if rec.plan_learn_hours is not None or rec.plan_eep_hours is not None
             else None)
    band = rec.funding_band
    if band is None and rec.fund_model is None and total is not None:
        # Fee status not settled yet: show the 16-19 band the hours imply,
        # validation reports the missing fee status.
        band = _ilr().funding_band(total, rec.age_on_31_august,
                                   high_needs=rec.high_needs)
    return {
        "age_31_aug": rec.age_on_31_august,
        "planned_hours": total,
        "planned_qual_hours": rec.plan_learn_hours,
        "planned_eep_hours": rec.plan_eep_hours,
        "funding_band": band,
        "enrolment_id": rec.enrolment_id,
        "fee_status": rec.fee_status,
        "fund_model": rec.fund_model,
        "ffi": rec.ffi,
        "study_mode": rec.mode,
        "early_leaver": 1 if rec.early_leaver else 0,
        "destination_type": rec.destination_type,
        "destination_code": rec.destination_code,
        "destination_start": rec.destination_start,
        "destination_collected": rec.destination_collected,
    }


def _build_rows(academic_year: str, *, as_of: str, attendance: dict,
                ukprn: str | None, messages: list[str]
                ) -> list[tuple[dict, list[dict]]]:
    """(learner, aims) rows for every learner in the year. Pure read: the
    one place both :func:`generate_return` and the ILR file get them."""
    cols = _student_columns()
    send_flags = _send_flags()
    enrolled = year_enrolments(academic_year)
    built: list[tuple[dict, list[dict]]] = []
    for s in _students().list_students():
        try:
            learner, aims = build_learner(
                s, academic_year, as_of=as_of, cols=cols,
                send_flags=send_flags, attendance=attendance, ukprn=ukprn,
                enrolment=enrolled.get(s.student_id))
        except Exception as e:      # one bad record must not sink the return
            logger.exception("Could not build learner %s", s.student_id)
            messages.append(f"{s.student_id}: could not build ({e})")
            continue
        if learner:
            built.append((learner, aims))
    return built


def generate_return(return_id: int, *, as_of: str | None = None
                    ) -> GenerateResult:
    """(Re)build the return's learners and aims from the records.

    Idempotent. Overridden fields and manual aims survive; generated
    aims whose learning aim no longer exists are removed unless they
    carry overrides (then kept and flagged by validation).
    """
    _guard("generate return")
    ret = core.get_return(return_id)
    if ret is None:
        raise ValidationError(f"No return with id {return_id}")
    year = normalise_year(ret.academic_year)
    route = get_route()
    settings = get_settings()
    y_start, y_end = year_bounds(year)
    today = _dt.date.today().isoformat()
    as_of = as_of or ret.reference_date or min(today, y_end)
    att_to = max(y_start, min(as_of, today))
    attendance, att_return = _attendance_rows(y_start, att_to, route)

    out = GenerateResult(return_id=return_id, academic_year=year, route=route)
    if att_return is not None:
        out.attendance_summary = att_return.summary
    built = _build_rows(year, as_of=as_of, attendance=attendance,
                        ukprn=settings.get("ukprn"), messages=out.messages)

    now = _dt.datetime.now().isoformat(timespec="seconds")
    with core._connect() as conn:
        _write_learners(conn, return_id, [b[0] for b in built], now, out)
        _write_aims(conn, return_id, [a for b in built for a in b[1]], now, out)
        learners = conn.execute(
            "SELECT COUNT(*) FROM return_learners WHERE return_id=?",
            (return_id,)).fetchone()[0]
        conn.execute(
            "UPDATE census_returns SET learner_count=?, updated_on=?, "
            "status=CASE WHEN status='Planned' THEN 'Draft' ELSE status END "
            "WHERE return_id=?", (learners, now, return_id))
    out.learners = len(built)
    logger.info("Generated return #%s: %s", return_id, out.summary)
    return out


def _build_year(academic_year: str, *, as_of: str | None = None
                ) -> tuple[list[ReturnLearner], list[core.LearnerAim], list[str]]:
    """The year's learners and aims exactly as :func:`generate_return`
    would store them (without overrides or attendance, which the ILR does
    not carry), held in memory — nothing is written. Callers gate access
    (:func:`return_export.export_ilr_csv`)."""
    year = normalise_year(academic_year)
    _y_start, y_end = year_bounds(year)
    as_of = as_of or min(_dt.date.today().isoformat(), y_end)
    messages: list[str] = []
    built = _build_rows(year, as_of=as_of, attendance={},
                        ukprn=get_settings().get("ukprn"), messages=messages)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    built.sort(key=lambda b: (b[0].get("family_name") or "",
                              b[0].get("given_names") or "",
                              b[0]["student_id"]))
    learners = [_memory_learner(lr, now) for lr, _a in built]
    aims = [_memory_aim(a, now) for _lr, rows in built for a in rows]
    return learners, aims, messages


def _memory_learner(row: dict[str, Any], now: str) -> ReturnLearner:
    base = {f.name: row.get(f.name) for f in fields(ReturnLearner)}
    base.update(learner_id=0, return_id=0, overrides=(), notes=None,
                generated_on=now, updated_on=now)
    return ReturnLearner(**base)


def _memory_aim(row: dict[str, Any], now: str) -> core.LearnerAim:
    base = {f.name: row.get(f.name) for f in fields(core.LearnerAim)}
    base.update(aim_id=row["source_aim_id"], return_id=None,
                source="generated", overrides=(), created_on=now,
                updated_on=now,
                qualifying_met=(None if row.get("qualifying_met") is None
                                else bool(row["qualifying_met"])))
    return core.LearnerAim(**base)


def _write_learners(conn: db.Connection, return_id: int,
                    learners: list[dict], now: str,
                    out: GenerateResult) -> None:
    existing = {r["student_id"]: r for r in conn.execute(
        "SELECT * FROM return_learners WHERE return_id=?", (return_id,))}
    seen: set[str] = set()
    for row in learners:
        sid = row["student_id"]
        seen.add(sid)
        old = existing.get(sid)
        if old is None:
            cols = ["return_id", "student_id", *_LEARNER_GENERATED,
                    "generated_on", "updated_on"]
            vals = [return_id, sid, *[row.get(c) for c in _LEARNER_GENERATED],
                    now, now]
            conn.execute(
                f"INSERT INTO return_learners ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' * len(cols))})", vals)
            continue
        keep = set(core._split_overrides(old["overrides"]))
        if keep:
            out.learners_kept_overrides += 1
        fields = [c for c in _LEARNER_GENERATED if c not in keep]
        conn.execute(
            f"UPDATE return_learners SET "
            f"{', '.join(f'{c}=?' for c in fields)}, generated_on=?, "
            f"updated_on=? WHERE learner_id=?",
            [*[row.get(c) for c in fields], now, now, old["learner_id"]])
    for sid, old in existing.items():
        if sid not in seen and not old["overrides"]:
            conn.execute("DELETE FROM return_learners WHERE learner_id=?",
                         (old["learner_id"],))


def _write_aims(conn: db.Connection, return_id: int,
                aims: list[dict], now: str, out: GenerateResult) -> None:
    existing = {r["source_aim_id"]: r for r in conn.execute(
        "SELECT * FROM learner_aims WHERE return_id=? AND source='generated'",
        (return_id,))}
    seen: set[int] = set()
    for row in aims:
        src = row["source_aim_id"]
        seen.add(src)
        old = existing.get(src)
        if old is None:
            cols = [*_AIM_GENERATED, "return_id", "source", "source_aim_id",
                    "created_on", "updated_on"]
            vals = [*[row.get(c) for c in _AIM_GENERATED], return_id,
                    "generated", src, now, now]
            conn.execute(
                f"INSERT INTO learner_aims ({', '.join(cols)}) "
                f"VALUES ({', '.join('?' * len(cols))})", vals)
            out.aims_created += 1
            continue
        keep = set(core._split_overrides(old["overrides"]))
        fields = [c for c in _AIM_GENERATED if c not in keep]
        conn.execute(
            f"UPDATE learner_aims SET {', '.join(f'{c}=?' for c in fields)}, "
            f"updated_on=? WHERE aim_id=?",
            [*[row.get(c) for c in fields], now, old["aim_id"]])
        out.aims_updated += 1
    for src, old in existing.items():
        if src in seen:
            continue
        if old["overrides"]:
            out.aims_orphaned += 1
            continue
        conn.execute("DELETE FROM learner_aims WHERE aim_id=?",
                     (old["aim_id"],))
        out.aims_removed += 1


# ── Return learners: read / override ───────────────────────────────

@dataclass
class ReturnLearner:
    learner_id: int
    return_id: int
    student_id: str
    learner_ref: str
    uln: str | None
    family_name: str | None
    given_names: str | None
    date_of_birth: str | None
    sex: str | None
    postcode: str | None
    ethnicity: str | None
    lldd: int | None
    ehcp: int | None
    send_status: str | None
    prior_attainment: float | None
    gcse_english: str | None
    gcse_maths: str | None
    age_31_aug: int | None
    planned_hours: float | None
    planned_qual_hours: float | None
    planned_eep_hours: float | None
    funding_band: str | None
    cof_english: str | None
    cof_maths: str | None
    cof_compliant: int | None
    attendance_pct: float | None
    hours_attended: float | None
    learner_status: str | None
    overrides: tuple[str, ...]
    notes: str | None
    generated_on: str | None
    updated_on: str | None
    # From the enrolment's ILR record (None when there is no enrolment).
    enrolment_id: int | None = None
    fee_status: str | None = None
    fund_model: int | None = None
    ffi: int | None = None
    study_mode: str | None = None
    early_leaver: int | None = None
    destination_type: str | None = None
    destination_code: int | None = None
    destination_start: str | None = None
    destination_collected: str | None = None

    @property
    def name(self) -> str:
        return " ".join(x for x in (self.given_names, self.family_name) if x)


def _row_learner(r: db.Row) -> ReturnLearner:
    d = dict(r)
    d["overrides"] = core._split_overrides(d.get("overrides"))
    return ReturnLearner(**d)


def list_learners(return_id: int) -> list[ReturnLearner]:
    core.init_db()
    with core._connect() as conn:
        return [_row_learner(r) for r in conn.execute(
            "SELECT * FROM return_learners WHERE return_id=? "
            "ORDER BY family_name, given_names, student_id", (return_id,))]


def get_learner(learner_id: int) -> ReturnLearner | None:
    core.init_db()
    with core._connect() as conn:
        r = conn.execute("SELECT * FROM return_learners WHERE learner_id=?",
                         (learner_id,)).fetchone()
    return _row_learner(r) if r else None


_NUMERIC_LEARNER = {"lldd": int, "ehcp": int, "prior_attainment": float,
                    "planned_hours": float, "planned_qual_hours": float,
                    "planned_eep_hours": float}


def update_learner(learner_id: int, payload: dict[str, Any]) -> ReturnLearner:
    """Hand-correct a generated learner; edited fields become overrides."""
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        identifiers,
    )
    _guard("edit return learner")
    old = get_learner(learner_id)
    if old is None:
        raise ValidationError(f"No return learner #{learner_id}")
    changes: dict[str, Any] = {}
    for k, v in payload.items():
        if k == "notes":
            changes["notes"] = (v or "").strip() or None
            continue
        if k not in OVERRIDABLE_LEARNER_FIELDS:
            continue
        if isinstance(v, str):
            v = v.strip() or None
        if v is not None and k in _NUMERIC_LEARNER:
            try:
                v = _NUMERIC_LEARNER[k](v)
            except (TypeError, ValueError):
                raise ValidationError(f"{k} must be a number") from None
        if k == "uln" and v:
            try:
                v = identifiers.validate_uln(v)
            except ValueError as e:
                raise ValidationError(str(e)) from None
        if k == "date_of_birth" and v:
            core._check_date("Date of birth", v)
        if k == "sex" and v and v not in ("M", "F"):
            raise ValidationError("Sex must be M or F")
        if v != getattr(old, k):
            changes[k] = v
    if not changes:
        return old
    over = set(old.overrides) | (set(changes) - {"notes"})
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with core._connect() as conn:
        conn.execute(
            f"UPDATE return_learners SET "
            f"{', '.join(f'{c}=?' for c in changes)}, overrides=?, "
            f"updated_on=? WHERE learner_id=?",
            [*changes.values(), ",".join(sorted(over)) or None, now,
             learner_id])
    return get_learner(learner_id)  # type: ignore[return-value]


def clear_learner_overrides(learner_id: int) -> ReturnLearner:
    _guard("clear return learner overrides")
    if get_learner(learner_id) is None:
        raise ValidationError(f"No return learner #{learner_id}")
    with core._connect() as conn:
        conn.execute(
            "UPDATE return_learners SET overrides=NULL WHERE learner_id=?",
            (learner_id,))
    return get_learner(learner_id)  # type: ignore[return-value]


__all__ = [
    "ROUTES", "ROUTE_ILR", "ROUTE_SCHOOL_CENSUS", "DEFAULT_ROUTE",
    "SETTING_KEYS", "get_settings", "set_setting", "get_route", "set_route",
    "normalise_year", "year_bounds", "current_year", "aim_in_year",
    "attendance_extract", "route_attendance_kind",
    "GenerateResult", "generate_return", "build_learner", "year_enrolments",
    "FUND_MODEL_NAMES", "ILR_LEARNER_FIELDS",
    "OVERRIDABLE_LEARNER_FIELDS", "ReturnLearner", "list_learners",
    "get_learner", "update_learner", "clear_learner_overrides",
]
