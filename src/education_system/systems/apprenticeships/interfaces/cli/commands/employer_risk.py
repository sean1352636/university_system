"""Employer risk: every employer rated Low, Medium or High, with the reasons.

Exposes: menu.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.application.employers import employer_risk_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)


def menu(actor: Actor) -> None:
    entries: list[tuple[str, Callable[[], None]]] = [
        ("Risk table, highest first", partial(_table, actor)),
        ("Why is an employer rated as it is?", partial(_why, actor)),
    ]
    prompts.run_menu("Employer Risk", entries)


def _table(actor: Actor) -> None:
    results = employer_risk_service.assess_employers(actor)
    prompts.title("Employer risk")
    prompts.table(
        (("Employer", 26), ("Risk", 7), ("Pts", -4), ("Active", -7), ("Attend", -7),
         ("OTJ ok", -7), ("Rev over", -9), ("Cmt over", -9), ("Satisf", -7)),
        results,
        lambda r: (
            r.employer_name, r.level, r.points, r.metrics.active_apprentices,
            _pct(r.metrics.attendance_percent), _pct(r.metrics.otj_compliance_percent),
            r.metrics.reviews_overdue, r.metrics.commitments_overdue,
            "" if r.metrics.satisfaction is None else f"{r.metrics.satisfaction:.1f}",
        ),
        noun="employer",
        empty="there are no employers to rate yet",
    )
    prompts.pause()


def _why(actor: Actor) -> None:
    results = employer_risk_service.assess_employers(actor)
    result = prompts.choose(
        "Employer", results, render=lambda r: f"{r.employer_name} — {r.level} ({r.points})"
    )
    prompts.title(f"{result.employer_name}: {result.level} risk")
    prompts.details([
        ("Points", result.points),
        ("Apprentices", f"{result.metrics.active_apprentices} active of "
                        f"{result.metrics.apprentices}"),
        ("Attendance", _pct(result.metrics.attendance_percent)),
        ("Off-the-job on track", _pct(result.metrics.otj_compliance_percent)),
        ("Reviews completed", result.metrics.reviews_completed),
        ("Reviews overdue", result.metrics.reviews_overdue),
        ("Commitments outstanding", result.metrics.commitments_outstanding),
        ("Commitments overdue", result.metrics.commitments_overdue),
        ("Satisfaction", "" if result.metrics.satisfaction is None
         else f"{result.metrics.satisfaction:.1f} / 5 ({result.metrics.feedback_count})"),
    ])
    prompts.note("\nReasons:")
    for reason in result.reasons:
        prompts.note(f"  • {reason}")
    prompts.pause()


def _pct(value: float | None) -> str:
    return "" if value is None else f"{value:.0f}%"
