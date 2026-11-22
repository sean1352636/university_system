"""The skills matrix: every KSB and how far the apprentice has got with it.

Exposes: menu.

Read-only. An apprentice goes straight to their own matrix. Tutors,
administrators and employers get the cohort view — apprentices against
% competent per KSB type — and can open any one apprentice's matrix.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.progress.skills_matrix import (
    SkillsMatrix,
    average_percent,
    level_bar,
)
from education_system.systems.apprenticeships.interfaces.cli import prompts
from education_system.systems.apprenticeships.interfaces.cli.commands import apprentices
from education_system.systems.apprenticeships.application.learning import skills_matrix_service
from education_system.systems.apprenticeships.application.security.access import Actor

logger = logging.getLogger(__name__)

_KSB_COLUMNS = (
    ("KSB", 5), ("Level", 11), ("", config.SKILLS_MATRIX_BAR_WIDTH), ("Evid.", -5),
    ("Statement", 44),
)
_COHORT_COLUMNS = (
    ("Apprentice", 22), ("Programme", 22), ("Employer", 18), ("K %", -6), ("S %", -6),
    ("B %", -6), ("All %", -6),
)

# Roles with a cohort to compare. Mirrors the service, which refuses the rest.
_COHORT_ROLES = (config.ADMIN, config.STAFF, config.EMPLOYER)


def menu(actor: Actor) -> None:
    if actor.role == config.APPRENTICE:
        prompts.run_action(partial(_mine, actor))
        return
    entries: list[tuple[str, Callable[[], None]]] = []
    if actor.role in _COHORT_ROLES:
        entries.append(("Cohort view", partial(_cohort, actor)))
    entries.append(("One apprentice's matrix", partial(_one, actor)))
    prompts.run_menu("Skills Matrix", entries)


def _mine(actor: Actor) -> None:
    matrix = skills_matrix_service.my_matrix(actor)
    if matrix is None:
        prompts.fail("Your login is not linked to an apprentice record yet.")
        prompts.note("Ask your provider to link it, then sign in again.")
    else:
        show(matrix)
    prompts.pause()


def _one(actor: Actor) -> None:
    summary = apprentices.pick(actor, heading="Whose skills matrix?", active_only=True)
    show(skills_matrix_service.apprentice_matrix(actor, summary.apprentice.apprentice_id))
    prompts.pause()


def _cohort(actor: Actor) -> None:
    rows = skills_matrix_service.cohort_matrix(actor)
    prompts.title("Skills matrix — cohort")
    prompts.table(
        _COHORT_COLUMNS,
        rows,
        lambda r: (r.apprentice_name, r.programme_title, r.employer_name,
                   r.percent("Knowledge"), r.percent("Skill"), r.percent("Behaviour"),
                   r.percent_overall),
        noun="apprentice",
        empty="no active apprentices on a programme in your view",
    )
    if rows:
        prompts.details([
            ("Mean % competent — Knowledge", average_percent(rows, "Knowledge")),
            ("Skills", average_percent(rows, "Skill")),
            ("Behaviours", average_percent(rows, "Behaviour")),
            ("Overall", average_percent(rows)),
        ])
    prompts.pause()


def show(matrix: SkillsMatrix) -> None:
    """One apprentice's matrix, grouped Knowledge / Skill / Behaviour."""
    prompts.title(f"Skills matrix — {matrix.apprentice_name}")
    prompts.details([
        ("Programme", matrix.programme_title),
        ("Competent", f"{matrix.competent} of {matrix.total}  "
                      f"{prompts.bar(matrix.percent_competent)}"),
    ])
    grouped = matrix.by_type()
    for summary in matrix.summaries():
        items = grouped.get(summary.ksb_type, [])
        if not items:
            continue
        pct = summary.percent_competent
        prompts.note(
            f"\n{summary.ksb_type}: {summary.competent} of {summary.total} competent"
            + (f" ({pct:.0f}%)" if pct is not None else "")
        )
        prompts.table(
            _KSB_COLUMNS,
            items,
            lambda c: (c.ksb.code, c.coverage, level_bar(c.coverage), c.evidence_count,
                       c.ksb.description),
            noun="KSB",
        )
