"""Validation rules for a census / ILR return.

``validate_return`` used to set the status to "Validated" without
looking at anything. :func:`run` checks the return's learners and aims
and stores the findings in ``return_findings``; ``census_ilr.validate_return``
then records the error / warning counts and only marks the return
Validated when there are no errors.

Rules (each finding names the rule, the learner and what to do):

Learner
  * ULN missing; ULN fails the LRS check digit; ULN used twice.
  * Date of birth missing; age on 31 August under 16 (error) or 19+
    without an EHCP (warning — not 16-19 fundable without one).
  * Postcode missing; ethnicity not held (warning).
  * Planned hours missing / zero; the funding band does not match the
    planned hours (e.g. a hand override that left the band behind).
  * No aims in the year.
  * Condition of funding not met (warning).
  * From the enrolment's ILR record: no started enrolment for the year
    (warning — funding and hours are then derived, not recorded); fee
    status / funding model not set (error); no planned learning hours
    (``PlanLearnHours``, error); early leaver — withdrawn inside the
    42-day qualifying period (info). The funding band and the 19+ age
    warning apply to 16-19 funding (FundModel 25) only.
Aim
  * Aim reference (QAN / LARS) missing.
  * Planned end before start; actual end before start; actual end in
    the future.
  * Withdrawn / transferred / completed without an actual end date;
    continuing with one.
  * Completion code does not match the status.
  * Planned hours missing on the aim (warning).
  * Withdrawn before the funding qualifying period (info — the aim will
    not be funded).
  * Completed without an outcome (warning).
  * Withdrawn (CompStatus 3) without an ILR WithdrawReason code (error).
  * Generated aim whose learning aim no longer exists (kept only for its
    overrides — warning).
Attendance (from ATTEND's attendance_census validation, for the same
period): carried over as-is for a school census; as warnings for an
ILR, which does not carry attendance.

These are the college's own checks. They approximate, and do not
replace, the ESFA Funding Information System (FIS) / DfE COLLECT
validation rules, which must still be run on the exported file.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass

from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
    census_ilr as core,
    return_builder as builder,
)

logger = logging.getLogger(__name__)

ERROR = "Error"
WARNING = "Warning"
INFO = "Info"
SEVERITIES: tuple[str, ...] = (ERROR, WARNING, INFO)

# Status -> completion codes that agree with it (census_ilr legend).
_STATUS_CODES: dict[str, tuple[int, ...]] = {
    "Continuing": (1,),
    "Temporarily Withdrawn": (6,),
    "Withdrawn": (3,),
    "Transferred": (7, 3),
    "Completed": (2, 10),
    "Achieved": (2,),
    "Partially Achieved": (2, 10),
    "Not Achieved": (10, 2),
}
_ENDED = ("Withdrawn", "Transferred", "Completed", "Achieved",
          "Partially Achieved", "Not Achieved")


@dataclass
class Finding:
    severity: str
    rule: str
    message: str
    learner_ref: str | None = None
    aim_id: int | None = None
    fix: str | None = None
    finding_id: int | None = None

    @property
    def label(self) -> str:
        who = f" [{self.learner_ref}]" if self.learner_ref else ""
        aim = f" aim #{self.aim_id}" if self.aim_id else ""
        fix = f" -> {self.fix}" if self.fix else ""
        return f"{self.severity}: {self.rule}{who}{aim}: {self.message}{fix}"


def _band_for(hours: float | None, age: int | None, ehcp: bool) -> str | None:
    if hours is None:
        return None
    try:
        from education_system.systems.sixth_form.domain.academics.qualifications import (
            study_programme,
        )
        return study_programme.funding_band(hours, age, high_needs=ehcp)
    except Exception:
        return None


#: The ILR field each rule is about (for the ILR export's problem list).
RULE_FIELDS: dict[str, str] = {
    "ULN missing": "ULN", "ULN check digit": "ULN", "Duplicate ULN": "ULN",
    "Date of birth missing": "DateOfBirth", "Age on 31 August": "DateOfBirth",
    "Postcode missing": "Postcode", "Ethnicity not held": "Ethnicity",
    "Planned hours missing": "PlanLearnHours",
    "Planned learning hours missing": "PlanLearnHours",
    "Funding band": "FundingBand", "No aims": "LearnAimRef",
    "Condition of funding": "ConditionOfFunding",
    "No enrolment": "Enrolment", "Fee status missing": "FeeStatus",
    "Early leaver": "LearnActEndDate", "Orphaned aim": "LearnAimRef",
    "Aim reference missing": "LearnAimRef", "Aim dates": "LearnStartDate",
    "Actual end date missing": "LearnActEndDate",
    "Status / end date": "LearnActEndDate",
    "Planned end passed": "LearnPlanEndDate",
    "Completion status missing": "CompStatus",
    "Completion status": "CompStatus", "Aim planned hours": "PlanLearnHours",
    "Qualifying period": "LearnActEndDate", "Outcome not known": "Outcome",
    "Withdraw reason missing": "WithdrawReason",
}


def check(return_id: int) -> list[Finding]:
    """All findings for a return, worst first. Writes nothing."""
    ret = core.get_return(return_id)
    if ret is None:
        raise core.ValidationError(f"No return with id {return_id}")
    route = builder.get_route()
    learners = builder.list_learners(return_id)
    aims = core.aims_for_return(return_id)
    out: list[Finding] = []
    if not learners and not aims:
        out.append(Finding(ERROR, "Empty return",
                           "The return has no learners or aims",
                           fix="Generate the return from the records"))
    out.extend(check_rows(learners, aims))
    out.extend(_attendance_findings(ret, route))
    return _sorted(out)


def _sorted(findings: list[Finding]) -> list[Finding]:
    order = {ERROR: 0, WARNING: 1, INFO: 2}
    return sorted(findings, key=lambda f: (order.get(f.severity, 3), f.rule,
                                           f.learner_ref or ""))


def check_rows(learners: list, aims: list[core.LearnerAim]) -> list[Finding]:
    """The learner and aim rules over rows held anywhere: a stored return
    (:func:`check`) or the in-memory year the ILR file is built from
    (``return_export.export_ilr_csv``). Writes nothing."""
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        identifiers,
    )
    today = _dt.date.today().isoformat()
    out: list[Finding] = []
    add = out.append

    aims_by_ref: dict[str, list[core.LearnerAim]] = {}
    for a in aims:
        aims_by_ref.setdefault(a.learner_ref, []).append(a)

    seen_uln: dict[str, str] = {}
    for ln in learners:
        ref = ln.learner_ref
        if not ln.uln:
            add(Finding(ERROR, "ULN missing", f"{ln.name} has no ULN", ref,
                        fix="Find the ULN through the LRS and record it"))
        elif not identifiers.is_valid_uln(ln.uln):
            add(Finding(ERROR, "ULN check digit",
                        f"ULN {ln.uln} fails the LRS check digit", ref,
                        fix="Re-check the number with the LRS"))
        else:
            if ln.uln in seen_uln:
                add(Finding(ERROR, "Duplicate ULN",
                            f"ULN {ln.uln} also used by {seen_uln[ln.uln]}",
                            ref, fix="One of the two learners has the wrong ULN"))
            seen_uln[ln.uln] = ref
        if not ln.date_of_birth:
            add(Finding(ERROR, "Date of birth missing",
                        f"{ln.name} has no date of birth", ref))
        elif ln.age_31_aug is not None:
            fm = getattr(ln, "fund_model", None)
            if ln.age_31_aug < 16:
                add(Finding(ERROR, "Age on 31 August",
                            f"Aged {ln.age_31_aug} on 31 August - below 16",
                            ref, fix="Check the date of birth"))
            elif ln.age_31_aug >= 19 and not ln.ehcp and fm in (None, 25):
                add(Finding(WARNING, "Age on 31 August",
                            f"Aged {ln.age_31_aug} on 31 August without an "
                            "EHCP - not 16-19 fundable", ref,
                            fix="Confirm the funding route (EHCP / adult)"))
        if not ln.postcode:
            add(Finding(WARNING, "Postcode missing",
                        f"No postcode held for {ln.name}", ref,
                        fix="Record the home postcode (prior-to-enrolment "
                            "postcode on the ILR)"))
        if not ln.ethnicity:
            add(Finding(WARNING, "Ethnicity not held",
                        "Ethnicity is not held - it will be returned as "
                        "'not provided'", ref))
        if not ln.planned_hours:
            add(Finding(ERROR, "Planned hours missing",
                        f"{ln.name} has no planned hours for the year", ref,
                        fix="Set planned hours on the aims / non-qualification "
                            "hours in Study Programme"))
        elif getattr(ln, "fund_model", None) in (None, 25):
            expect = _band_for(ln.planned_hours, ln.age_31_aug, bool(ln.ehcp))
            if ln.funding_band and expect and expect != ln.funding_band:
                add(Finding(ERROR, "Funding band",
                            f"Band {ln.funding_band} does not match "
                            f"{ln.planned_hours:g} planned hours ({expect})",
                            ref, fix="Correct the hours or clear the band "
                                     "override"))
            elif not ln.funding_band:
                add(Finding(ERROR, "Funding band",
                            "No funding band recorded", ref))
        if ln.planned_hours and not ln.planned_qual_hours:
            add(Finding(ERROR, "Planned learning hours missing",
                        f"{ln.name} has no planned learning (qualification) "
                        "hours - PlanLearnHours", ref,
                        fix="Set planned hours on the aims, or record them on "
                            "the enrolment's ILR details"))
        out.extend(_enrolment_findings(ln))
        if not aims_by_ref.get(ref):
            add(Finding(ERROR, "No aims",
                        f"{ln.name} has no learning aims in the year", ref,
                        fix="Add the learner's learning aims"))
        if ln.cof_compliant == 0:
            detail = "; ".join(x for x in (ln.cof_english, ln.cof_maths)
                               if x and x.startswith("Non-compliant"))
            add(Finding(WARNING, "Condition of funding",
                        detail or "English / maths condition of funding not met",
                        ref))

    learner_refs = {ln.learner_ref for ln in learners}
    for a in aims:
        ref = a.learner_ref
        if learners and ref not in learner_refs and a.is_generated:
            add(Finding(WARNING, "Orphaned aim",
                        "Generated aim whose learner is no longer in the "
                        "return (kept for its overrides)", ref, a.aim_id,
                        fix="Delete it, or clear its overrides and regenerate"))
        if not (a.aim_reference or "").strip():
            add(Finding(ERROR, "Aim reference missing",
                        f"{a.aim_title or 'Aim'} has no QAN / LARS reference",
                        ref, a.aim_id,
                        fix="Record the aim code on the learning aim"))
        if a.planned_end_date and a.planned_end_date < a.start_date:
            add(Finding(ERROR, "Aim dates", "Planned end is before the start",
                        ref, a.aim_id))
        if a.actual_end_date:
            if a.actual_end_date < a.start_date:
                add(Finding(ERROR, "Aim dates",
                            "Actual end is before the start", ref, a.aim_id))
            if a.actual_end_date > today:
                add(Finding(ERROR, "Aim dates",
                            f"Actual end {a.actual_end_date} is in the future",
                            ref, a.aim_id))
        if a.status in _ENDED and not a.actual_end_date:
            add(Finding(ERROR, "Actual end date missing",
                        f"{a.status} without an actual end date", ref,
                        a.aim_id, fix="Record the withdrawal / end date"))
        if a.status == "Continuing" and a.actual_end_date:
            add(Finding(ERROR, "Status / end date",
                        "Continuing but has an actual end date", ref, a.aim_id))
        if (a.status == "Continuing" and a.planned_end_date
                and a.planned_end_date < today):
            add(Finding(WARNING, "Planned end passed",
                        f"Still continuing after planned end "
                        f"{a.planned_end_date}", ref, a.aim_id,
                        fix="Complete, withdraw or extend the aim"))
        allowed = _STATUS_CODES.get(a.status)
        if a.completion_code is None:
            add(Finding(ERROR, "Completion status missing",
                        "No completion code", ref, a.aim_id))
        elif allowed and a.completion_code not in allowed:
            add(Finding(ERROR, "Completion status",
                        f"Code {a.completion_code} does not match status "
                        f"{a.status}", ref, a.aim_id))
        if not a.planned_hours:
            add(Finding(WARNING, "Aim planned hours",
                        "No planned hours on the aim", ref, a.aim_id))
        if a.qualifying_met is False and a.status in ("Withdrawn",
                                                       "Transferred"):
            add(Finding(INFO, "Qualifying period",
                        "Withdrawn before the funding qualifying period - "
                        "not funded", ref, a.aim_id))
        if a.status in ("Completed",) and a.outcome_code in (None, "", "8"):
            add(Finding(WARNING, "Outcome not known",
                        "Completed with no outcome yet", ref, a.aim_id,
                        fix="Record the result when it is released, or the "
                            "aim outcome on the Enrolment screen"))
        if (a.is_generated and a.completion_code == 3
                and not a.withdraw_reason_code):
            add(Finding(ERROR, "Withdraw reason missing",
                        f"{a.aim_title or 'Aim'} withdrawn with no ILR "
                        "WithdrawReason code", ref, a.aim_id,
                        fix="Record the withdrawal reason on the enrolment"))
    return _sorted(out)


def _enrolment_findings(ln) -> list[Finding]:
    """Rules on the enrolment ILR fields (FundModel, FeeStatus, early leaver)."""
    ref = ln.learner_ref
    if getattr(ln, "enrolment_id", None) is None:
        return [Finding(WARNING, "No enrolment",
                        f"{ln.name} has no started enrolment for the year - "
                        "funding model, fee status and hours are not recorded",
                        ref, fix="Enrol the learner for the year (Enrolments)")]
    out: list[Finding] = []
    if not ln.fee_status or ln.fund_model is None:
        out.append(Finding(ERROR, "Fee status missing",
                           f"{ln.name}: fee status / funding model (FundModel) "
                           "not set - a 19+ learner's has to be recorded", ref,
                           fix="Record it on the enrolment's ILR details"))
    if ln.early_leaver:
        out.append(Finding(INFO, "Early leaver",
                           "Withdrawn before the 42-day qualifying period - "
                           "not funded", ref))
    return out


def _attendance_findings(ret: core.CensusReturn, route: str) -> list[Finding]:
    """ATTEND's attendance-return findings for the same period."""
    try:
        year = builder.normalise_year(ret.academic_year)
        start, end = builder.year_bounds(year)
        today = _dt.date.today().isoformat()
        to = max(start, min(ret.reference_date or today, today, end))
        att = builder.attendance_extract(builder.route_attendance_kind(route),
                                         start, to)
    except Exception as e:
        logger.debug("attendance validation unavailable", exc_info=True)
        return [Finding(WARNING, "Attendance",
                        f"Attendance extract could not be built: {e}")]
    out: list[Finding] = []
    for f in att.findings:
        sev = f.severity
        if route != builder.ROUTE_SCHOOL_CENSUS and sev == ERROR:
            sev = WARNING
        out.append(Finding(sev, f"Attendance: {f.check}", f.detail,
                           f.student_id, fix=f.fix))
    return out


def run(return_id: int) -> list[Finding]:
    """Check the return and store the findings (replacing the last run)."""
    findings = check(return_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with core._connect() as conn:
        conn.execute("DELETE FROM return_findings WHERE return_id=?",
                     (return_id,))
        conn.executemany(
            "INSERT INTO return_findings (return_id, severity, rule, "
            "learner_ref, aim_id, message, fix, created_on) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(return_id, f.severity, f.rule, f.learner_ref, f.aim_id,
              f.message, f.fix, now) for f in findings])
    return findings


def list_findings(return_id: int) -> list[Finding]:
    """Findings stored by the last validation run."""
    core.init_db()
    with core._connect() as conn:
        rows = conn.execute(
            "SELECT * FROM return_findings WHERE return_id=? "
            "ORDER BY CASE severity WHEN 'Error' THEN 0 WHEN 'Warning' "
            "THEN 1 ELSE 2 END, rule, learner_ref", (return_id,)).fetchall()
    return [Finding(severity=r["severity"], rule=r["rule"],
                    message=r["message"], learner_ref=r["learner_ref"],
                    aim_id=r["aim_id"], fix=r["fix"],
                    finding_id=r["finding_id"]) for r in rows]


def report(findings: list[Finding]) -> str:
    errors = sum(1 for f in findings if f.severity == ERROR)
    warnings = sum(1 for f in findings if f.severity == WARNING)
    lines = [f.label for f in findings] or ["No issues found."]
    lines.append("-" * 72)
    lines.append(f"{errors} error(s), {warnings} warning(s)"
                 + ("  - fix the errors before exporting" if errors else ""))
    return "\n".join(lines)


__all__ = ["ERROR", "WARNING", "INFO", "SEVERITIES", "RULE_FIELDS", "Finding",
           "check", "check_rows", "run", "list_findings", "report"]
