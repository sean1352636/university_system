"""Pull current data into a SEF section as a dated evidence block.

A SEF section's evidence used to be typed from memory. :func:`pull_evidence`
inserts what the records say *today* — the 16-18 measures, attendance,
behaviour counts, condition of funding, destinations, safeguarding
training compliance — into the section's ``evidence`` field as a block
marked with the date it was pulled:

    ── Data evidence pulled 2026-10-22 14:05 (2025/26) ──
    ...
    ── end of data evidence ──

The text the author wrote is kept. Pulling again replaces the previous
block (so the evidence never doubles up) and leaves everything outside
the markers alone. Only open sections (Draft / In Review) can be
changed — an approved or published SEF is not rewritten underneath its
approver.

Which data goes into which area follows the Ofsted judgement areas; the
"Overall Effectiveness" and "Sixth Form Provision" sections get it all.
Every measure carries its "approximates DfE methodology" caveat.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from typing import Callable

from education_system.systems.sixth_form.domain.assessment.sef_builder import (
    sef_builder as core,
)

logger = logging.getLogger(__name__)

BLOCK_START = "── Data evidence pulled"
BLOCK_END = "── end of data evidence ──"
_BLOCK_RE = re.compile(re.escape(BLOCK_START) + r".*?" + re.escape(BLOCK_END),
                       re.S)


# ── Evidence pieces ────────────────────────────────────────────────

def _measure_lines(report, keys: tuple[str, ...]) -> list[str]:
    lines: list[str] = []
    for key in keys:
        m = report.get(key)
        if m is None:
            continue
        basis = f" ({m.basis})" if m.basis else ""
        lines.append(f"- {m.label}: {m.display}{basis}")
        for n in m.notes:
            lines.append(f"    {n}")
    return lines


def _behaviour_lines(days: int = 365) -> list[str]:
    from education_system.systems.sixth_form.domain.pastoral.behaviour import (
        behaviour,
    )
    today = _dt.date.today()
    since = (today - _dt.timedelta(days=days)).isoformat()
    rows = behaviour.list_entries(date_from=since, date_to=today.isoformat())
    pos = sum(1 for r in rows if r.entry_type == "Positive")
    neg = sum(1 for r in rows if r.entry_type == "Negative")
    students = len({r.student_id for r in rows if r.entry_type == "Negative"})
    follow = sum(1 for r in rows if r.follow_up_required)
    return [f"- Behaviour (last {days} days): {pos} positive, {neg} negative "
            f"entries; {students} learner(s) with a negative entry; "
            f"{follow} needing follow-up"]


def _safeguarding_training_lines() -> list[str]:
    """In-date safeguarding training among active staff (HR records)."""
    from education_system.systems.sixth_form.domain.staff.staff_hr import staff_hr
    recs = [r for r in staff_hr.list_records() if r.is_active]
    if not recs:
        return ["- Safeguarding training: no staff HR records held"]
    trained = [r for r in recs if r.safeguarding_training_on
               and not r.safeguarding_expired]
    expired = sum(1 for r in recs if r.safeguarding_expired)
    never = sum(1 for r in recs if not r.safeguarding_training_on)
    pct = 100.0 * len(trained) / len(recs)
    return [f"- Safeguarding training in date: {len(trained)} of {len(recs)} "
            f"active staff ({pct:.0f}%); {expired} expired, {never} with no "
            "training recorded"]


def _prevent_training_lines() -> list[str]:
    from education_system.systems.sixth_form.domain.safeguarding.prevent_duty import (
        prevent_duty,
    )
    s = prevent_duty.summary()
    return [f"- Prevent training: {s.staff_with_training} staff with a record, "
            f"{s.training_expired} expired, {s.training_expiring_soon} "
            "expiring within 60 days"]


def _destination_lines(report) -> list[str]:
    return _measure_lines(report, ("destinations",))


def _safe(fn: Callable[[], list[str]], label: str) -> list[str]:
    try:
        return fn()
    except Exception as e:
        logger.debug("SEF evidence %s failed", label, exc_info=True)
        return [f"- {label}: not available ({e})"]


_AREA_MEASURES: dict[str, tuple[str, ...]] = {
    "Quality of Education": ("achievement", "l3va", "em_progress",
                             "retention", "cof"),
    "Behaviour & Attitudes": ("attendance", "retention"),
    "Personal Development": ("destinations",),
    "Leadership & Management": ("retention", "achievement", "cof",
                                "attendance"),
    "Sixth Form Provision": ("retention", "achievement", "l3va",
                             "em_progress", "destinations", "attendance",
                             "cof"),
    "Overall Effectiveness": ("retention", "achievement", "l3va",
                              "em_progress", "destinations", "attendance",
                              "cof"),
    "Safeguarding": ("attendance",),
}


def build_evidence(area: str, *, academic_year: str | None = None,
                   report=None) -> str:
    """The dated evidence block for one SEF area (text, markers included)."""
    from education_system.systems.sixth_form.domain.governance.compliance.measures import (
        measures,
    )
    if area not in core.AREAS:
        raise core.ValidationError(f"Area must be one of: {', '.join(core.AREAS)}")
    if report is None:
        report = measures.compute_all(academic_year)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"{BLOCK_START} {stamp} ({report.academic_year}) ──"]
    lines += _measure_lines(report, _AREA_MEASURES.get(area, ()))
    if area in ("Behaviour & Attitudes", "Personal Development",
                "Overall Effectiveness", "Sixth Form Provision"):
        lines += _safe(_behaviour_lines, "Behaviour")
    if area in ("Safeguarding", "Leadership & Management",
                "Overall Effectiveness"):
        lines += _safe(_safeguarding_training_lines, "Safeguarding training")
        lines += _safe(_prevent_training_lines, "Prevent training")
    lines.append(f"  ({measures.DISCLAIMER})")
    lines.append(BLOCK_END)
    return "\n".join(lines)


def merge_evidence(existing: str | None, block: str) -> str:
    """Replace the previous data block in *existing*, or append *block*."""
    text = existing or ""
    if _BLOCK_RE.search(text):
        return _BLOCK_RE.sub(lambda _m: block, text, count=1).strip()
    return (text.rstrip() + "\n\n" + block).strip() if text.strip() else block


def pull_evidence(section_id: int, *, academic_year: str | None = None,
                  report=None) -> core.SEFSection:
    """Insert current data into a section's evidence, keeping manual text."""
    s = core.get_section(section_id)
    if s is None:
        raise core.ValidationError(f"No SEF section with id {section_id}")
    if not s.is_open:
        raise core.ValidationError(
            f"Section is {s.status} - only Draft / In Review sections can "
            "have evidence pulled in")
    block = build_evidence(s.area, academic_year=academic_year, report=report)
    data = core._to_dict(s)
    data["evidence"] = merge_evidence(s.evidence, block)
    return core.update_section(section_id, data)


def pull_evidence_for_cycle(cycle: str, *, academic_year: str | None = None
                            ) -> tuple[int, list[str]]:
    """Pull evidence into every open section of a cycle (measures computed once)."""
    from education_system.systems.sixth_form.domain.governance.compliance.measures import (
        measures,
    )
    report = measures.compute_all(academic_year)
    done = 0
    skipped: list[str] = []
    for s in core.list_sections(cycle=cycle):
        if not s.is_open:
            skipped.append(f"{s.area} ({s.status})")
            continue
        pull_evidence(s.section_id, report=report)
        done += 1
    return done, skipped


__all__ = ["BLOCK_START", "BLOCK_END", "build_evidence", "merge_evidence",
           "pull_evidence", "pull_evidence_for_cycle"]
