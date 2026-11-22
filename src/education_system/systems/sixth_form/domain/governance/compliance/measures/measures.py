"""DfE 16-18 accountability measures, computed from the college's records.

The headline measures a sixth form is judged on, worked out from the
learning aims, exam results, prior attainment, destinations and
attendance already held:

* **Retention** — students retained to the end of their main study
  programme (core aim).
* **Achievement rate** — aims achieved / (aims started − transfers).
* **English and maths progress** — average grade progress for students
  who did not hold a grade 4 at 16.
* **Destinations** — positive / sustained destinations of leavers.
* **Level 3 value added** — actual minus expected grade, expected from
  average GCSE via the benchmark table (value_added.derivation).
* **Attendance** — census-basis attendance for the year to date.
* **Condition of funding compliance** — learners meeting the English /
  maths condition of funding.

**These APPROXIMATE the DfE methodology.** The real measures use DfE
cohort rules (a student's "main study programme", the end-of-16-to-18
cohort, discounting, qualification size weightings, national subject
regressions for L3VA, sustained-destination matching to HMRC / HESA
data) that cannot be reproduced from one college's records. Each
formula below is written out in the code and in the ``formula`` text
shown with the figure. Check every one against the current DfE 16-18
accountability technical guidance before quoting a figure externally.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DISCLAIMER = ("Approximation of the DfE 16-18 methodology from college "
              "records - check against the current DfE technical guidance.")


@dataclass
class MeasureResult:
    key: str
    label: str
    value: float | None
    unit: str                         # "%", "grades", "pts"
    numerator: float | None
    denominator: float | None
    formula: str
    notes: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def display(self) -> str:
        if self.value is None:
            return "—"
        if self.unit == "%":
            return f"{self.value:.1f}%"
        if self.unit in ("grades", "pts"):
            return f"{self.value:+.2f}"
        return f"{self.value:g}"

    @property
    def basis(self) -> str:
        if self.numerator is None or self.denominator is None:
            return ""
        return f"{self.numerator:g} / {self.denominator:g}"


@dataclass
class MeasuresReport:
    academic_year: str
    generated_at: str
    measures: list[MeasureResult] = field(default_factory=list)

    def get(self, key: str) -> MeasureResult | None:
        return next((m for m in self.measures if m.key == key), None)

    def text(self) -> str:
        lines = [f"16-18 measures - {self.academic_year} "
                 f"(generated {self.generated_at})", DISCLAIMER, "=" * 72]
        for m in self.measures:
            basis = f"  ({m.basis})" if m.basis else ""
            lines.append(f"{m.label:<34} {m.display:>10}{basis}")
            lines.append(f"    formula: {m.formula}")
            for n in m.notes:
                lines.append(f"    note: {n}")
        return "\n".join(lines)


# ── Year helpers ───────────────────────────────────────────────────

def current_year() -> str:
    t = _dt.date.today()
    y = t.year if t.month >= 8 else t.year - 1
    return f"{y}/{str(y + 1)[-2:]}"


def _year(value: str | None) -> tuple[str, int, str, str]:
    """('2025/26', 2025, '2025-08-01', '2026-07-31')."""
    m = re.match(r"^\s*(\d{4})", value or current_year())
    if not m:
        raise ValueError("Academic year must look like '2025/26'")
    y = int(m.group(1))
    return (f"{y}/{str(y + 1)[-2:]}", y, f"{y}-08-01", f"{y + 1}-07-31")


def _pct(n: float, d: float) -> float | None:
    return round(100.0 * n / d, 1) if d else None


# ── Shared per-learner context (built once per report) ─────────────

@dataclass
class _Learner:
    student: Any
    aims: list[Any]
    results: dict[str, Any]
    prior: Any


class Context:
    """Learners, their aims, results and prior attainment — read once."""

    def __init__(self) -> None:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            learning_aims,
            prior_attainment,
        )
        from education_system.systems.sixth_form.domain.assessment.value_added import (
            derivation,
        )
        from education_system.systems.sixth_form.domain.learners.students import (
            students,
        )
        self.learners: list[_Learner] = []
        for s in students.list_students():
            try:
                self.learners.append(_Learner(
                    student=s, aims=learning_aims.list_aims(s.student_id),
                    results=derivation.actual_results_for(s.student_id),
                    prior=prior_attainment.prior_attainment(s.student_id)))
            except Exception:
                logger.debug("measures: skipped %s", s.student_id,
                             exc_info=True)


def _ends_in(aim: Any, start: str, end: str) -> bool:
    """The aim's end (actual, else planned) falls in the year."""
    finish = aim.withdrawal_date or aim.actual_end_date or aim.planned_end_date
    return bool(finish) and start <= finish <= end


def _area(subject: str) -> str | None:
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        prior_attainment,
    )
    stripped = re.sub(r"^(gcse|functional skills|fs)\s+", "", subject.strip(),
                      flags=re.I)
    return prior_attainment.area_for_subject(stripped)


def core_aim(aims: list[Any]) -> Any | None:
    """The learner's main study programme aim.

    The aim flagged ``is_core_aim``; failing that, the substantive aim
    (not an English / maths resit) with the latest planned end date —
    an approximation of the DfE "main study programme".
    """
    live = [a for a in aims if a.status != "Transferred"] or aims
    flagged = [a for a in live if a.is_core_aim]
    if flagged:
        return flagged[0]
    substantive = [a for a in live if not (
        a.qualification_type in ("GCSE", "Functional Skills")
        and _area(a.subject))] or live
    if not substantive:
        return None
    return max(substantive, key=lambda a: (a.planned_end_date or a.start_date,
                                           a.planned_hours or 0))


def _qualified(aim: Any) -> bool:
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims,
    )
    return not learning_aims.qualifying_check_for(aim).withdrawn_before_qualifying


# ── Retention ──────────────────────────────────────────────────────

def retention(academic_year: str | None = None, *,
              ctx: Context | None = None) -> MeasureResult:
    """Students retained to the end of their main study programme.

    Formula (approximation):
      cohort   = learners whose core aim ends (actual, else planned end)
                 in the year, EXCLUDING core aims withdrawn before the
                 funding qualifying period and core aims transferred
      retained = cohort members whose core aim is Completed, or still
                 Active (in learning — provisional until the year ends)
      retention % = retained / cohort × 100
    """
    year, _y, start, end = _year(academic_year)
    ctx = ctx or Context()
    rows: list[dict[str, Any]] = []
    cohort = retained = 0
    for ln in ctx.learners:
        core = core_aim(ln.aims)
        if core is None or not _ends_in(core, start, end):
            continue
        if core.status == "Transferred" or not _qualified(core):
            continue
        cohort += 1
        kept = core.status in ("Completed", "Active")
        retained += kept
        rows.append({"student_id": ln.student.student_id,
                     "name": ln.student.full_name, "core_aim": core.label,
                     "status": core.status, "retained": kept})
    notes = []
    if any(r["status"] == "Active" for r in rows):
        notes.append("Active core aims count as retained until the year ends "
                     "(provisional).")
    return MeasureResult(
        key="retention", label="Retention", value=_pct(retained, cohort),
        unit="%", numerator=retained, denominator=cohort,
        formula=("core aims Completed or still Active / core aims ending in "
                 "the year (excl. withdrawn before qualifying, transfers)"),
        notes=notes, rows=rows)


# ── Achievement rate ───────────────────────────────────────────────

def achievement_rate(academic_year: str | None = None, *,
                     ctx: Context | None = None) -> MeasureResult:
    """Aims achieved / (aims started − transfers).

    Formula (approximation of the DfE / QAR achievement rate):
      leavers  = aims ending (actual, else planned end) in the year,
                 EXCLUDING aims withdrawn before the funding qualifying
                 period (never counted as starts) and transfers
      achieved = leavers with a released passing grade on their own
                 qualification scale (grade_scales.is_pass)
      achievement % = achieved / leavers × 100
    Withdrawals and fails count against; aims completed with no result
    yet are counted as not achieved and reported separately.
    """
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    year, _y, start, end = _year(academic_year)
    ctx = ctx or Context()
    rows: list[dict[str, Any]] = []
    leavers = achieved = unknown = transfers = 0
    for ln in ctx.learners:
        for a in ln.aims:
            if not _ends_in(a, start, end):
                continue
            if a.status == "Transferred":
                transfers += 1
                continue
            if not _qualified(a):
                continue
            leavers += 1
            res = ln.results.get(a.subject)
            ok = bool(res and grade_scales.is_pass(res.grade,
                                                   a.qualification_type))
            if a.status == "Withdrawn":
                ok = False
            elif res is None:
                unknown += 1
            achieved += ok
            rows.append({"student_id": ln.student.student_id,
                         "name": ln.student.full_name, "aim": a.label,
                         "status": a.status,
                         "grade": res.grade if res else None,
                         "achieved": ok})
    notes = [f"{transfers} transfer(s) removed from the starts."]
    if unknown:
        notes.append(f"{unknown} aim(s) have no released result yet and "
                     "count as not achieved.")
    return MeasureResult(
        key="achievement", label="Achievement rate",
        value=_pct(achieved, leavers), unit="%", numerator=achieved,
        denominator=leavers,
        formula=("aims with a passing grade / aims ending in the year minus "
                 "transfers (excl. withdrawn before qualifying)"),
        notes=notes, rows=rows)


# ── English and maths progress ─────────────────────────────────────

def _gcse_points(grade: str | None) -> float | None:
    if grade is None:
        return None
    g = grade.strip().upper()
    if g.isdigit():
        return float(g)
    return 0.0 if g in ("U", "X") else None


def _result_in_year(res: Any, y: int) -> bool:
    if res is None:
        return False
    autumn = (res.season or "").lower() in ("november", "autumn", "winter")
    return res.year == y + 1 or (res.year == y and autumn)


def english_maths_progress(academic_year: str | None = None, *,
                           ctx: Context | None = None) -> MeasureResult:
    """Average GCSE grade progress for students without a grade 4 at 16.

    Formula (approximation of the DfE English and maths progress measure):
      in scope = (learner, area) pairs where the learner's best prior
                 GCSE in that area is below 4 (or none) AND they had an
                 English / maths aim (GCSE or Functional Skills) live in
                 the year
      progress = best GCSE points achieved in the year's series
                 (Nov of year 1 / summer of year 2) − prior best points
                 (no prior GCSE = 0; no new GCSE result = 0 progress)
      measure  = mean progress over the pairs (English and maths pooled)
    Functional Skills passes are not converted to GCSE points here; they
    are counted and reported in the notes.
    """
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    year, y, start, end = _year(academic_year)
    ctx = ctx or Context()
    rows: list[dict[str, Any]] = []
    total = 0.0
    n = grade4 = fs_pass = 0
    for ln in ctx.learners:
        for area, prior_pts, prior_grade in (
                ("English", ln.prior.best_english, ln.prior.best_english_grade),
                ("Maths", ln.prior.best_maths, ln.prior.best_maths_grade)):
            if prior_pts is not None and prior_pts >= 4:
                continue
            area_aims = [a for a in ln.aims if _area(a.subject) == area
                         and a.qualification_type in ("GCSE", "Functional Skills")
                         and a.start_date <= end
                         and (not (a.withdrawal_date or a.actual_end_date
                                   or a.planned_end_date)
                              or (a.withdrawal_date or a.actual_end_date
                                  or a.planned_end_date) >= start)]
            if not area_aims:
                continue
            best_new: float | None = None
            new_grade = None
            for a in area_aims:
                res = ln.results.get(a.subject)
                if not _result_in_year(res, y):
                    continue
                if a.qualification_type == "Functional Skills":
                    if grade_scales.is_pass(res.grade, "Functional Skills"):
                        fs_pass += 1
                    continue
                pts = _gcse_points(res.grade)
                if pts is not None and (best_new is None or pts > best_new):
                    best_new, new_grade = pts, res.grade
            prior = prior_pts or 0.0
            progress = (best_new - prior) if best_new is not None else 0.0
            total += progress
            n += 1
            if best_new is not None and best_new >= 4:
                grade4 += 1
            rows.append({"student_id": ln.student.student_id,
                         "name": ln.student.full_name, "area": area,
                         "prior": prior_grade or "none",
                         "new": new_grade or "-",
                         "progress": round(progress, 1)})
    value = round(total / n, 2) if n else None
    return MeasureResult(
        key="em_progress", label="English & maths progress", value=value,
        unit="grades", numerator=round(total, 1), denominator=n,
        formula=("mean(best new GCSE points − prior best points) over "
                 "learners without grade 4 at 16 on an English / maths aim"),
        notes=[f"{grade4} of {n} reached grade 4+ in the year.",
               f"{fs_pass} Functional Skills pass(es) not converted to points."],
        rows=rows)


# ── Destinations ───────────────────────────────────────────────────

def destinations_summary() -> MeasureResult:
    """Positive destinations of leavers (destinations module summary).

    Formula (approximation):
      positive % = leavers whose LEAVING destination is HE / FE /
                   apprenticeship / employment / training
                   / leavers with a LEAVING record × 100
    DfE's measure is a *sustained* destination (two terms in the year
    after leaving, matched to national data); the +6 month checkpoint
    is the nearest proxy and is shown in the notes. Records are not
    filtered by leaving year.
    """
    from education_system.systems.sixth_form.domain.progression.destinations import (
        destinations,
    )
    s = destinations.summary()
    plus6 = sum(1 for r in destinations.list_records(checkpoint="PLUS_6"))
    rows = [{"destination": k, "records": v}
            for k, v in s.by_destination_type.items() if v]
    return MeasureResult(
        key="destinations", label="Positive destinations",
        value=_pct(s.positive_at_leaving, s.students_with_leaving), unit="%",
        numerator=s.positive_at_leaving, denominator=s.students_with_leaving,
        formula=("leavers with a positive LEAVING destination / leavers with "
                 "a LEAVING record"),
        notes=[f"{s.students_missing_leaving} leaver(s) have no destination "
               "recorded.",
               f"+6 months: {s.positive_at_plus_6} positive of {plus6} "
               "recorded (sustained-destination proxy)."],
        rows=rows)


# ── Level 3 value added ────────────────────────────────────────────

def level3_value_added(academic_year: str | None = None) -> MeasureResult:
    """Mean of (actual − expected grade points) for results in the year.

    Formula (approximation of DfE L3VA):
      expected = grade from average GCSE via the benchmark table
                 (value_added.derivation; subject bands first)
      VA       = actual points − expected points on the qualification's
                 own ordinal scale (one point per grade)
      measure  = mean VA over aims with a released result in the summer
                 series ending the year
    DfE L3VA uses national subject regressions and size weightings; the
    seeded benchmark table is a linear PLACEHOLDER until replaced.
    """
    from education_system.systems.sixth_form.domain.assessment.value_added import (
        derivation,
    )
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        grade_scales,
    )
    year, y, _s, _e = _year(academic_year)
    level3 = tuple(t for t in grade_scales.QUALIFICATION_TYPES
                   if t not in ("GCSE", "Functional Skills"))
    cohort = derivation.derive_cohort(results_year=y + 1,
                                      qualification_types=level3)
    scored = [r for r in cohort.rows if r.va is not None]
    notes = []
    if cohort.placeholder_in_use:
        notes.append("Uses the PLACEHOLDER benchmark table - not ALPS/DfE "
                     "data. Replace it before relying on this figure.")
    rows = [{"subject": s.subject, "learners": s.learners,
             "with_results": s.with_results, "mean_va": s.mean_va}
            for s in cohort.by_subject]
    return MeasureResult(
        key="l3va", label="Level 3 value added", value=cohort.mean_va,
        unit="grades", numerator=(round(sum(r.va for r in scored), 1)
                                  if scored else None),
        denominator=len(scored),
        formula="mean(actual points − expected points) over results in the year",
        notes=notes, rows=rows)


# ── Attendance ─────────────────────────────────────────────────────

def attendance(academic_year: str | None = None) -> MeasureResult:
    """Census-basis attendance for the year to date (ATTEND's extract).

    Formula: sessions attended (present + approved activity) / sessions
    possible × 100, as built and validated by attendance_census.
    """
    from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
        return_builder,
    )
    year, _y, start, end = _year(academic_year)
    today = _dt.date.today().isoformat()
    to = max(start, min(today, end))
    # attendance_census.census_extract, through the short-lived cache
    ret = return_builder.attendance_extract("census", start, to)
    notes = []
    if ret.errors:
        notes.append(f"Attendance return has {len(ret.errors)} validation "
                     "error(s) - the figure may be incomplete.")
    return MeasureResult(
        key="attendance", label="Attendance (year to date)",
        value=ret.attendance_pct, unit="%", numerator=ret.sessions_attended,
        denominator=ret.sessions_possible,
        formula="sessions attended / sessions possible (census basis)",
        notes=notes)


# ── Condition of funding ───────────────────────────────────────────

def cof_compliance() -> MeasureResult:
    """Learners on roll meeting the English and maths condition of funding.

    Formula: active learners compliant in both English and maths
    (prior_attainment.funding_condition) / active learners × 100.
    """
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        prior_attainment,
    )
    rows = prior_attainment.compliance_report()
    ok = sum(1 for r in rows if r.condition.compliant)
    return MeasureResult(
        key="cof", label="Condition of funding compliance",
        value=_pct(ok, len(rows)), unit="%", numerator=ok,
        denominator=len(rows),
        formula="active learners compliant in English and maths / active learners",
        rows=[{"student_id": r.student_id, "name": r.student_name,
               "english": r.condition.english.status,
               "maths": r.condition.maths.status}
              for r in rows if not r.condition.compliant])


# ── All together ───────────────────────────────────────────────────

def _failed(key: str, label: str, err: Exception) -> MeasureResult:
    return MeasureResult(key=key, label=label, value=None, unit="%",
                         numerator=None, denominator=None,
                         formula="(could not be computed)",
                         notes=[f"Error: {err}"])


def compute_all(academic_year: str | None = None) -> MeasuresReport:
    """Every measure for the year. A failing measure shows as '—'."""
    year = _year(academic_year)[0]
    out = MeasuresReport(academic_year=year,
                         generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
    try:
        ctx = Context()
    except Exception as e:
        logger.exception("measures context failed")
        ctx = None
        out.measures.append(_failed("context", "Learner data", e))
    plan = (
        ("retention", "Retention", lambda: retention(year, ctx=ctx)),
        ("achievement", "Achievement rate",
         lambda: achievement_rate(year, ctx=ctx)),
        ("em_progress", "English & maths progress",
         lambda: english_maths_progress(year, ctx=ctx)),
        ("l3va", "Level 3 value added", lambda: level3_value_added(year)),
        ("destinations", "Positive destinations", destinations_summary),
        ("attendance", "Attendance (year to date)", lambda: attendance(year)),
        ("cof", "Condition of funding compliance", cof_compliance),
    )
    for key, label, fn in plan:
        if ctx is None and key in ("retention", "achievement", "em_progress"):
            continue
        try:
            out.measures.append(fn())
        except Exception as e:
            logger.exception("measure %s failed", key)
            out.measures.append(_failed(key, label, e))
    return out


__all__ = ["DISCLAIMER", "MeasureResult", "MeasuresReport", "Context",
           "current_year", "core_aim", "retention", "achievement_rate",
           "english_maths_progress", "destinations_summary",
           "level3_value_added", "attendance", "cof_compliance",
           "compute_all"]
