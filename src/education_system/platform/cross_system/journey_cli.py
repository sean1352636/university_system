"""Reusable CLI helpers for the Student Journey + promote action.

Any system's CLI can wire these in with a one-liner so staff can (a) see
which systems hold a learner and their whole history, and (b) promote a
pupil to the next phase — the same cross-system linkage the GUI panel
shows, made operable from the terminal.
"""

from __future__ import annotations

import logging

from education_system.platform.cross_system import progression, student_view

logger = logging.getLogger(__name__)

# system -> ("module:function", kind). kind tells the prompt what extra
# input the transfer needs.
_PROMOTERS = {
    "nursery": (
        "education_system.systems.nursery.domain.learners.children.primary_transfer:move_to_primary_school",
        "plain"),
    "primary": (
        "education_system.systems.primary.domain.learners.pupils.secondary_transfer:move_to_secondary_school",
        "plain"),
    "secondary": (
        "education_system.systems.secondary.domain.admissions.sixthform_transfer:move_to_sixth_form",
        "subjects"),
    "sixth_form": (
        "education_system.systems.sixth_form.domain.learners.students.students:mark_transferred",
        "plain"),
}


def show_journey(system: str, student_id: str) -> str:
    """Return a printable cross-system overview for a local student id."""
    overview = student_view.build_overview_for_student(system, student_id)
    return student_view.format_overview_text(overview)


def print_journey(system: str, student_id: str) -> None:
    print(show_journey(system, student_id))


def next_phase_label(system: str) -> str | None:
    return progression.next_phase(system)


def promote(system: str, student_id: str, **kwargs):
    """Promote a learner to the next phase by invoking that system's
    transfer flow. ``kwargs`` carries phase-specific extras (e.g.
    ``subject_1/2/3`` for school → college). Returns the transfer result.

    Raises ValueError if the system has no next phase / promoter.
    """
    import importlib

    spec = _PROMOTERS.get(system)
    if not spec:
        raise ValueError(f"No promotion path from {system!r}")
    ref, _kind = spec
    module_path, _, func = ref.partition(":")
    fn = getattr(importlib.import_module(module_path), func)
    result = fn(student_id, **kwargs)
    logger.info("Promoted %s/%s to next phase", system, student_id)
    return result


def promote_kind(system: str) -> str | None:
    """What extra input the promote prompt needs: 'plain' | 'subjects'."""
    spec = _PROMOTERS.get(system)
    return spec[1] if spec else None


def prompt_and_show(system: str, *, input_fn=input, output_fn=print) -> None:
    """Interactive: ask for a student id and print their journey."""
    sid = (input_fn("Student/Pupil ID: ") or "").strip()
    if not sid:
        output_fn("Cancelled.")
        return
    output_fn(show_journey(system, sid))


def prompt_and_promote(system: str, *, input_fn=input, output_fn=print) -> None:
    """Interactive promote-to-next-phase, prompting for any extras."""
    nxt = progression.next_phase(system)
    if not nxt or promote_kind(system) is None:
        output_fn(f"No next phase to promote to from {system}.")
        return
    sid = (input_fn("Student/Pupil ID to promote: ") or "").strip()
    if not sid:
        output_fn("Cancelled.")
        return
    extra = {}
    if promote_kind(system) == "subjects":
        for i in (1, 2, 3):
            extra[f"subject_{i}"] = (
                input_fn(f"A-Level subject {i}: ") or "").strip()
    try:
        result = promote(system, sid, **extra)
    except Exception as exc:  # noqa: BLE001
        output_fn(f"Promotion failed: {exc}")
        return
    output_fn(f"Promoted {sid} to {nxt}. ({result})")


# Menu labels each system's CLI can offer in a "Cross-System" category.
JOURNEY_LABEL = "Student Journey"
PROMOTE_LABEL = "Promote to Next System"
CLI_MENU_ITEMS = [JOURNEY_LABEL, PROMOTE_LABEL]


def dispatch(label: str, system: str, *, auth=None,
             input_fn=input, output_fn=print) -> bool:
    """Route a CLI menu ``label`` for ``system``. Returns True if handled.

    Drop ``journey_cli.dispatch(label, "<system>")`` into a CLI's dispatch
    chain and add :data:`CLI_MENU_ITEMS` to a "Cross-System" menu category.
    """
    if label == JOURNEY_LABEL:
        prompt_and_show(system, input_fn=input_fn, output_fn=output_fn)
        return True
    if label == PROMOTE_LABEL:
        prompt_and_promote(system, input_fn=input_fn, output_fn=output_fn)
        return True
    return False


__all__ = [
    "show_journey",
    "print_journey",
    "promote",
    "promote_kind",
    "next_phase_label",
    "prompt_and_show",
    "prompt_and_promote",
    "dispatch",
    "JOURNEY_LABEL",
    "PROMOTE_LABEL",
    "CLI_MENU_ITEMS",
]
