"""Reusable CLI helpers for the Learner 360 / Student Journey + promote action.

Any system's CLI can wire these in with a one-liner so staff can (a) see
which systems hold a learner and their whole history, and (b) promote a
pupil to the next phase — the same cross-system linkage the GUI panel
shows, made operable from the terminal.

Promotion asks for the parent's (or learner's) consent to share sensitive
information when the boundary needs it. Nursery -> primary *requires*
medical alerts, which may only cross with consent, so a promotion without
it is refused up front rather than failing inside the transfer — or,
worse, sending a child to Reception with their allergies missing.
"""

from __future__ import annotations

import importlib
import inspect
import logging
import re
from collections.abc import Callable
from typing import Any

from education_system.platform.cross_system import (
    learner_360,
    progression,
    student_view,
)

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
        "education_system.systems.sixth_form.domain.learners.students.transfers:mark_transferred",
        "plain"),
}

_JOURNEY_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-"
                         r"[0-9a-f]{12}$", re.IGNORECASE)

MEDICAL_CONSENT_QUESTION = (
    "Has the parent/carer (or the learner, if 16+) consented to share "
    "medical alerts with the next setting?")
SUPPORT_CONSENT_QUESTION = (
    "Has the parent/carer (or the learner, if 16+) consented to share "
    "SEND / support information with the next setting?")
REFERENCE_QUESTION = "Safeguarding handover reference (optional)"


def _viewer(auth) -> tuple[str | None, str | None]:
    """(role, system) of the signed-in user, or (None, None) if unknown."""
    try:
        cu = getattr(auth, "current_user", None) or {}
        role = cu.get("role") or next(iter(cu.get("roles") or []), None)
        return role, cu.get("system") or cu.get("system_key")
    except Exception:
        return None, None


def _render(overview: dict) -> str:
    view = overview.get("learner_360")
    if view:
        return learner_360.format_learner_360_text(view)
    return student_view.format_overview_text(overview)


def show_journey(system: str, student_id: str, *, auth=None) -> str:
    """Return a printable Learner 360 for a local student id.

    With a signed-in ``auth`` the view is filtered for that user's role;
    without one it is the trusted staff overview, as before.
    """
    role, viewer_system = _viewer(auth)
    if role:
        return learner_360.format_learner_360_text(
            learner_360.build_learner_360_for_student(
                system, student_id, viewer_role=role,
                viewer_system=viewer_system))
    return _render(student_view.build_overview_for_student(system, student_id))


def show_journey_by_id(journey_id: str, *, auth=None) -> str:
    """Return a printable Learner 360 for a canonical journey id."""
    role, viewer_system = _viewer(auth)
    return learner_360.format_learner_360_text(learner_360.build_learner_360(
        journey_id, viewer_role=role, viewer_system=viewer_system))


def print_journey(system: str, student_id: str) -> None:
    print(show_journey(system, student_id))


def next_phase_label(system: str) -> str | None:
    return progression.next_phase(system)


# ---------------------------------------------------------------------------
# Promotion
# ---------------------------------------------------------------------------

def _resolve(system: str) -> Callable[..., Any]:
    """The system's promote function (imported lazily: it is system code)."""
    spec = _PROMOTERS.get(system)
    if not spec:
        raise ValueError(f"No promotion path from {system!r}")
    module_path, _, func = spec[0].partition(":")
    return getattr(importlib.import_module(module_path), func)


def _consent_builder(system: str) -> Callable[..., Any] | None:
    """The system's own granular-consent builder (nursery's ``consent_for``)."""
    spec = _PROMOTERS.get(system)
    if not spec:
        return None
    try:
        module = importlib.import_module(spec[0].partition(":")[0])
    except Exception:
        return None
    return getattr(module, "consent_for", None)


def _accepted(fn: Callable[..., Any]) -> set[str] | None:
    """Parameter names ``fn`` takes, or None if it takes ``**kwargs``."""
    try:
        params = inspect.signature(fn).parameters
    except (TypeError, ValueError):
        return None
    if any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return None
    return set(params)


def promote(system: str, student_id: str, **kwargs):
    """Promote a learner to the next phase by invoking that system's
    transfer flow. ``kwargs`` carries phase-specific extras (``subject_1/2/3``
    for school → college, ``consent`` and ``safeguarding_reference`` where
    the boundary hands over sensitive information). Returns the result.

    Raises ValueError if the system has no promoter, or if it would be
    handed an argument it does not take — a consent silently dropped is a
    handover that quietly withholds what the parent agreed to share.
    """
    fn = _resolve(system)
    accepted = _accepted(fn)
    if accepted is not None:
        unexpected = sorted(k for k in kwargs if k not in accepted)
        if unexpected:
            raise ValueError(
                f"The {system} promotion does not accept "
                f"{', '.join(unexpected)}")
    result = fn(student_id, **kwargs)
    logger.info("Promoted %s/%s to next phase", system, student_id)
    return result


def promote_kind(system: str) -> str | None:
    """What extra input the promote prompt needs: 'plain' | 'subjects'."""
    spec = _PROMOTERS.get(system)
    return spec[1] if spec else None


def promote_accepts_consent(system: str) -> bool:
    """Whether this system's promotion takes a handover consent."""
    try:
        accepted = _accepted(_resolve(system))
    except Exception:
        return False
    return accepted is None or "consent" in accepted


def consent_requirements(system: str) -> tuple[str, ...]:
    """Handover fields the next boundary *requires* that need consent.

    Restricted fields (the safeguarding reference) are not in this list:
    they cross on statutory duty, not on consent.
    """
    nxt = progression.next_phase(system)
    if not nxt:
        return ()
    try:
        from education_system.platform.cross_system import handover
        spec = handover.get_spec(system, nxt)
        if spec is None:
            return ()
        return tuple(
            key for key in spec.required_keys()
            if spec.get(key) is not None
            and spec.get(key).sensitivity is handover.Sensitivity.SENSITIVE)
    except Exception:
        logger.debug("Handover spec lookup failed for %s", system,
                     exc_info=True)
        return ()


def build_consent(system: str, *, medical: bool, support: bool):
    """The promoter's ``consent`` value from the two answers.

    Uses the system's own granular builder where it has one (nursery's
    ``consent_for``). Without one, consent is all-or-nothing, so it is only
    given when both answers are yes; otherwise sensitive fields are
    withheld, which is the safe failure.
    """
    builder = _consent_builder(system)
    if builder is not None:
        granted = builder(medical=medical, support=support)
        return granted or None
    return True if (medical and support) else None


def missing_consent(system: str, consent) -> tuple[str, ...]:
    """Required consent-dependent fields that ``consent`` does not cover."""
    required = consent_requirements(system)
    if consent is True:
        return ()
    granted = set(consent or ())
    return tuple(key for key in required if key not in granted)


def _yes(answer: Any) -> bool:
    return str(answer or "").strip().lower() in ("y", "yes")


def prompt_consent(system: str, *, input_fn=input) -> tuple[Any, str | None]:
    """Ask the consent questions; return (consent, safeguarding_reference)."""
    medical = _yes(input_fn(f"{MEDICAL_CONSENT_QUESTION} [y/N]: "))
    support = _yes(input_fn(f"{SUPPORT_CONSENT_QUESTION} [y/N]: "))
    reference = (input_fn(f"{REFERENCE_QUESTION}: ") or "").strip() or None
    return build_consent(system, medical=medical, support=support), reference


def prompt_and_show(system: str, *, auth=None, input_fn=input,
                    output_fn=print) -> None:
    """Interactive: ask for a local id (or a journey id) and print the view."""
    key = (input_fn("Student/Pupil ID (or journey ID): ") or "").strip()
    if not key:
        output_fn("Cancelled.")
        return
    if _JOURNEY_ID.match(key):
        output_fn(show_journey_by_id(key, auth=auth))
    else:
        output_fn(show_journey(system, key, auth=auth))


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
    extra: dict[str, Any] = {}
    if promote_kind(system) == "subjects":
        for i in (1, 2, 3):
            extra[f"subject_{i}"] = (
                input_fn(f"A-Level subject {i}: ") or "").strip()
    if promote_accepts_consent(system):
        consent, reference = prompt_consent(system, input_fn=input_fn)
        missing = missing_consent(system, consent)
        if missing:
            output_fn(
                f"Cannot promote to {nxt}: the handover requires "
                f"{', '.join(missing)}, which may only be shared with the "
                "parent's consent. Record the consent and try again.")
            return
        extra["consent"] = consent
        if reference:
            extra["safeguarding_reference"] = reference
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
        prompt_and_show(system, auth=auth, input_fn=input_fn,
                        output_fn=output_fn)
        return True
    if label == PROMOTE_LABEL:
        prompt_and_promote(system, input_fn=input_fn, output_fn=output_fn)
        return True
    return False


__all__ = [
    "show_journey",
    "show_journey_by_id",
    "print_journey",
    "promote",
    "promote_kind",
    "promote_accepts_consent",
    "consent_requirements",
    "build_consent",
    "missing_consent",
    "prompt_consent",
    "next_phase_label",
    "prompt_and_show",
    "prompt_and_promote",
    "dispatch",
    "JOURNEY_LABEL",
    "PROMOTE_LABEL",
    "CLI_MENU_ITEMS",
]
