"""16-19 funding summary: who is funded, in which band, and who is at risk.

Built entirely from QUAL's qualification functions, so the rules live in
one place:

* **42-day qualifying period** — ``learning_aims.qualifying_check_for``
  (42 days for an aim of 24 weeks or more, 14 for 2-24 weeks, 1 day
  otherwise). A learner counts for funding in the year once at least one
  of their in-year aims has met its qualifying period.
* **Planned hours and band** — ``study_programme.planned_hours`` (aims
  withdrawn before qualifying are already left out of the hours) and
  its ``funding_band``. EHCP learners (SEND register, read only) are
  passed as high needs.
* **Condition of funding** — ``prior_attainment.funding_condition``.

"At risk of not qualifying" = an active aim whose qualifying date has
not yet been reached on the as-of date: if the learner leaves before
then the aim earns nothing. "Withdrawn before qualifying" = already lost.

These follow the ESFA 16-19 funding guidance as encoded in QUAL's
modules; check the thresholds against the current year's guidance.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field

from education_system.systems.sixth_form.domains.finance.domain.census_ilr import (
    return_builder as builder,
)

logger = logging.getLogger(__name__)


@dataclass
class AimRisk:
    aim_id: int
    label: str
    start_date: str
    qualifying_date: str
    days_in_learning: int
    qualifying_days: int
    status: str


@dataclass
class FundingLearner:
    student_id: str
    student_name: str
    age_31_aug: int | None
    planned_hours: float
    band: str
    funded: bool
    high_needs: bool
    aims_in_year: int
    aims_qualified: int
    at_risk: list[AimRisk] = field(default_factory=list)
    withdrawn_before_qualifying: list[AimRisk] = field(default_factory=list)
    cof_compliant: bool | None = None
    cof_status: str = ""


@dataclass
class FundingSummary:
    academic_year: str
    as_of: str
    learners: list[FundingLearner] = field(default_factory=list)
    band_counts: dict[str, int] = field(default_factory=dict)

    @property
    def funded(self) -> list[FundingLearner]:
        return [ln for ln in self.learners if ln.funded]

    @property
    def not_funded(self) -> list[FundingLearner]:
        return [ln for ln in self.learners if not ln.funded]

    @property
    def at_risk(self) -> list[FundingLearner]:
        return [ln for ln in self.learners if ln.at_risk]

    @property
    def lost_aims(self) -> list[FundingLearner]:
        return [ln for ln in self.learners if ln.withdrawn_before_qualifying]

    @property
    def cof_non_compliant(self) -> list[FundingLearner]:
        return [ln for ln in self.learners if ln.cof_compliant is False]

    @property
    def total_planned_hours(self) -> float:
        return round(sum(ln.planned_hours for ln in self.funded), 1)

    def text(self) -> str:
        lines = [f"16-19 funding summary - {self.academic_year} "
                 f"(as of {self.as_of})", "=" * 64,
                 f"Learners with aims in year : {len(self.learners)}",
                 f"Funded (qualified)         : {len(self.funded)}",
                 f"Not yet / not funded       : {len(self.not_funded)}",
                 f"Funded planned hours       : {self.total_planned_hours:,.1f}",
                 f"At risk of not qualifying  : {len(self.at_risk)}",
                 f"Aims lost before qualifying: "
                 f"{sum(len(x.withdrawn_before_qualifying) for x in self.learners)}",
                 f"CoF non-compliant          : {len(self.cof_non_compliant)}",
                 "", "Funding bands (funded learners):"]
        for band, n in self.band_counts.items():
            lines.append(f"  {band:<10}: {n}")
        if self.at_risk:
            lines += ["", "At risk of not qualifying:"]
            for ln in self.at_risk:
                for a in ln.at_risk:
                    lines.append(f"  {ln.student_id} {ln.student_name}: "
                                 f"{a.label} qualifies on {a.qualifying_date} "
                                 f"({a.days_in_learning}/{a.qualifying_days} days)")
        if self.cof_non_compliant:
            lines += ["", "Condition of funding not met:"]
            for ln in self.cof_non_compliant:
                lines.append(f"  {ln.student_id} {ln.student_name}: {ln.cof_status}")
        lines += ["", "Rules: ESFA 16-19 funding guidance as encoded in the "
                      "learning-aims / study-programme modules - check the "
                      "current year's thresholds."]
        return "\n".join(lines)


def funding_summary(academic_year: str | None = None, *,
                    as_of: str | None = None) -> FundingSummary:
    from education_system.systems.sixth_form.domain.academics.qualifications import (
        learning_aims,
        prior_attainment,
        study_programme,
    )
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    builder._guard("funding summary")
    year = builder.normalise_year(academic_year or builder.current_year())
    as_of = as_of or _dt.date.today().isoformat()
    ehcp = {sid for sid, (_on, has, _st) in builder._send_flags().items() if has}
    out = FundingSummary(academic_year=year, as_of=as_of,
                         band_counts={b[0]: 0 for b in study_programme.FUNDING_BANDS})
    for s in students.list_students():
        try:
            aims = [a for a in learning_aims.list_aims(s.student_id)
                    if builder.aim_in_year(a, year)]
            if not aims:
                continue
            hn = s.student_id in ehcp
            ph = study_programme.planned_hours(s.student_id, year, high_needs=hn)
            ln = FundingLearner(
                student_id=s.student_id, student_name=s.full_name,
                age_31_aug=ph.age_on_31_august, planned_hours=ph.total_hours,
                band=ph.band, funded=False, high_needs=hn,
                aims_in_year=len(aims), aims_qualified=0)
            for a in aims:
                chk = learning_aims.qualifying_check_for(a, as_of=as_of)
                risk = AimRisk(aim_id=a.aim_id, label=a.label,
                               start_date=a.start_date,
                               qualifying_date=chk.qualifying_date,
                               days_in_learning=chk.days_in_learning,
                               qualifying_days=chk.qualifying_days,
                               status=a.status)
                if chk.met:
                    ln.aims_qualified += 1
                elif chk.withdrawn_before_qualifying:
                    ln.withdrawn_before_qualifying.append(risk)
                elif a.status == "Active":
                    ln.at_risk.append(risk)
            ln.funded = ln.aims_qualified > 0
            try:
                cof = prior_attainment.funding_condition(s.student_id)
                ln.cof_compliant = cof.compliant
                ln.cof_status = "; ".join(
                    f"{x.area}: {x.status}" for x in cof.areas if not x.compliant)
            except Exception:
                logger.debug("CoF failed for %s", s.student_id, exc_info=True)
            out.learners.append(ln)
            if ln.funded:
                out.band_counts[ln.band] = out.band_counts.get(ln.band, 0) + 1
        except Exception:
            logger.exception("Funding summary failed for %s", s.student_id)
    return out


__all__ = ["AimRisk", "FundingLearner", "FundingSummary", "funding_summary"]
