"""Minimum expected grades (MEG) from prior attainment.

A MEG is the floor grade a learner should reach in a subject given their
average GCSE point score. It comes from the same benchmark table as the
value-added expected grade (:mod:`value_added.derivation` — the band's
``meg_grade``, or its expected grade when no separate MEG is set), so
the two can never disagree about what a learner "should" get.

:func:`apply_megs` writes the MEG into Target Setting's ``mte_grade``
(Minimum Target Expected) through ``target_setting``'s public
``create_target`` / ``update_target`` — creating a target where none
exists, and only replacing a different hand-set MTE when asked to
(``overwrite=True``). Target Setting's own validation applies; anything
it rejects is reported back rather than forced.

The seeded benchmark table is a PLACEHOLDER (see derivation) and every
MEG computed from it is flagged as such.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass, field

from education_system.systems.sixth_form.domain.assessment.value_added import (
    derivation,
)

logger = logging.getLogger(__name__)


@dataclass
class MEGRow:
    student_id: str
    student_name: str
    subject: str
    qualification_type: str
    aps: float | None
    meg_grade: str | None
    placeholder: bool
    target_id: int | None
    current_mte: str | None
    note: str = ""

    @property
    def action(self) -> str:
        """What apply_megs would do with this row."""
        if self.meg_grade is None:
            return "none"
        if self.target_id is None:
            return "create"
        if self.current_mte == self.meg_grade:
            return "same"
        return "differs"


@dataclass
class ApplyResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    kept: int = 0                       # different MTE kept (no overwrite)
    skipped: list[tuple[str, str, str]] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (f"{self.created} target(s) created, {self.updated} updated, "
                f"{self.unchanged} already matched, {self.kept} kept "
                f"(hand-set MTE differs), {len(self.skipped)} skipped")


def _ts():
    from education_system.systems.sixth_form.domain.assessment.target_setting import (
        target_setting,
    )
    return target_setting


def megs_for_student(student_id: str, *, student_name: str | None = None
                     ) -> list[MEGRow]:
    """MEG per live aim for one learner, beside their current MTE."""
    ts = _ts()
    out: list[MEGRow] = []
    for d in derivation.derive_student(student_id, student_name=student_name):
        target = None
        try:
            target = ts.get_target_for(student_id, d.subject)
        except Exception:
            logger.debug("target lookup failed", exc_info=True)
        out.append(MEGRow(
            student_id=student_id, student_name=d.student_name,
            subject=d.subject, qualification_type=d.qualification_type,
            aps=d.aps, meg_grade=d.meg_grade, placeholder=d.placeholder,
            target_id=target.target_id if target else None,
            current_mte=target.mte_grade if target else None,
            note=d.note))
    return out


def meg_report(*, active_only: bool = True,
               subject: str | None = None) -> list[MEGRow]:
    """MEGs for every (active) learner."""
    from education_system.systems.sixth_form.domain.learners.students import (
        students,
    )
    rows: list[MEGRow] = []
    for s in students.list_students():
        if active_only and s.status != "Active":
            continue
        try:
            for r in megs_for_student(s.student_id, student_name=s.full_name):
                if subject and r.subject != subject:
                    continue
                rows.append(r)
        except Exception:
            logger.debug("MEG failed for %s", s.student_id, exc_info=True)
    return rows


def apply_megs(rows: list[MEGRow], *, overwrite: bool = False,
               set_by: str | None = None) -> ApplyResult:
    """Write MEGs into Target Setting's MTE field."""
    ts = _ts()
    out = ApplyResult()
    today = _dt.date.today().isoformat()
    for r in rows:
        if r.meg_grade is None:
            out.skipped.append((r.student_id, r.subject,
                                r.note or "no benchmark band"))
            continue
        rationale = (f"MEG from average GCSE {r.aps:.2f} via the "
                     + ("PLACEHOLDER " if r.placeholder else "")
                     + "benchmark table")
        try:
            target = ts.get_target_for(r.student_id, r.subject)
            if target is None:
                ts.create_target({
                    "student_id": r.student_id, "subject_name": r.subject,
                    "mte_grade": r.meg_grade, "set_on": today,
                    "set_by": set_by, "rationale": rationale})
                out.created += 1
            elif target.mte_grade == r.meg_grade:
                out.unchanged += 1
            elif not overwrite:
                out.kept += 1
            else:
                ts.update_target(target.target_id, {
                    "mte_grade": r.meg_grade, "set_by": set_by,
                    "rationale": rationale})
                out.updated += 1
        except (ts.ValidationError, ValueError) as e:
            out.skipped.append((r.student_id, r.subject, str(e)))
    return out


__all__ = ["MEGRow", "ApplyResult", "megs_for_student", "meg_report",
           "apply_megs"]
