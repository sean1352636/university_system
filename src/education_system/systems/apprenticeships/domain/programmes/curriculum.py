"""A standard's curriculum: the modules it is delivered through.

The KSBs say what an apprentice must be able to do by the end; the
curriculum says how the provider gets them there — modules grouped into
stages such as "Year 1", each naming the KSBs it builds and the planned
off-the-job hours. Applying the curriculum to an apprentice turns each
module into an objective on their learning plan, so the plan starts from
the programme rather than from a blank page.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.programmes.models import validate_ksb_code

MAX_STAGE_LENGTH = 40
MAX_TITLE_LENGTH = 200
MAX_PLANNED_HOURS = 2000.0


@dataclass
class ProgrammeModule:
    """One module of a standard's curriculum."""

    module_id: int
    programme_id: int
    title: str
    stage: str = "Year 1"
    position: int = 1
    description: str | None = None
    ksb_codes: str | None = None
    planned_hours: float = 0.0
    created_at: str = ""
    updated_at: str = ""

    @property
    def ksb_list(self) -> list[str]:
        return [c for c in re.split(r"[,\s]+", self.ksb_codes or "") if c]


@dataclass
class CurriculumResult:
    """What applying a curriculum to one apprentice did."""

    apprentice_id: int
    programme_id: int
    # Module titles, by what happened to each.
    created: list[str] = field(default_factory=list)
    linked: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    activities: int = 0

    @property
    def summary(self) -> str:
        parts = [f"{len(self.created)} objective(s) added"]
        if self.linked:
            parts.append(f"{len(self.linked)} matched to objectives already on the plan")
        if self.skipped:
            parts.append(f"{len(self.skipped)} already applied")
        if self.activities:
            parts.append(f"{self.activities} activit{'y' if self.activities == 1 else 'ies'} "
                         "planned")
        return ", ".join(parts)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def validate_title(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError("A module needs a title")
    if len(text) > MAX_TITLE_LENGTH:
        raise ValidationError(f"A module title must be {MAX_TITLE_LENGTH} characters or fewer")
    return text


def validate_stage(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError("A module needs a stage, such as 'Year 1'")
    if len(text) > MAX_STAGE_LENGTH:
        raise ValidationError(f"A stage must be {MAX_STAGE_LENGTH} characters or fewer")
    return text


def validate_position(value: object) -> int:
    text = str(value if value is not None else "").strip()
    if not text:
        return 1
    try:
        position = int(text)
    except ValueError as exc:
        raise ValidationError("Position must be a whole number") from exc
    if position < 1:
        raise ValidationError("Position must be 1 or more")
    return position


def validate_planned_hours(value: object) -> float:
    text = str(value if value is not None else "").strip()
    if not text:
        return 0.0
    try:
        hours = round(float(text), 2)
    except ValueError as exc:
        raise ValidationError("Planned hours must be a number") from exc
    if not 0 <= hours <= MAX_PLANNED_HOURS:
        raise ValidationError(f"Planned hours must be from 0 to {MAX_PLANNED_HOURS:.0f}")
    return hours


def normalise_ksb_codes(value: object, known: set[str] | None = None) -> str | None:
    """Comma-separated KSB codes, each checked, optionally against the standard."""
    raw = [c for c in re.split(r"[,\s]+", str(value or "")) if c]
    codes: list[str] = []
    for item in raw:
        code, _ = validate_ksb_code(item)
        if known and code not in known:
            raise ValidationError(f"{code} is not a KSB on this standard")
        if code not in codes:
            codes.append(code)
    return ", ".join(codes) or None


def stage_order(modules: list[ProgrammeModule]) -> list[str]:
    """Stages in delivery order: by the earliest position of any module in them."""
    first: dict[str, tuple[int, int]] = {}
    for module in modules:
        key = (module.position, module.module_id)
        if module.stage not in first or key < first[module.stage]:
            first[module.stage] = key
    return sorted(first, key=lambda stage: first[stage])


def ordered(modules: list[ProgrammeModule]) -> list[ProgrammeModule]:
    """Modules grouped by stage in delivery order, then by position."""
    rank = {stage: index for index, stage in enumerate(stage_order(modules))}
    return sorted(modules, key=lambda m: (rank[m.stage], m.position, m.module_id))


def stage_windows(
    stages: list[str], start: str | None, end: str | None
) -> dict[str, tuple[str, str]]:
    """Split the programme's dates evenly across its stages.

    Stage labels are free text, so their dates cannot be read off them;
    an even split is the plan's starting point, and a tutor moves any
    target that turns out wrong. Empty when either date is unknown.
    """
    try:
        first = date.fromisoformat(start) if start else None
        last = date.fromisoformat(end) if end else None
    except ValueError:
        return {}
    if first is None or last is None or last <= first or not stages:
        return {}
    span = (last - first).days
    windows: dict[str, tuple[str, str]] = {}
    for index, stage in enumerate(stages):
        window_start = first + timedelta(days=span * index // len(stages))
        window_end = first + timedelta(days=span * (index + 1) // len(stages))
        windows[stage] = (window_start.isoformat(), window_end.isoformat())
    return windows


def title_key(title: str | None) -> str:
    """How a module and an objective are matched: case and spacing ignored."""
    return " ".join((title or "").split()).casefold()
