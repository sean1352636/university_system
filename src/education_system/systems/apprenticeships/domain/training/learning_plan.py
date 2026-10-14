"""The individual learning plan (ILP).

The plan is the agreement about what an apprentice will achieve and how.
Objectives are the "what": each names the knowledge, skills and
behaviours it builds, a target date, and how far along it is. The
activities under an objective — the training plan items — are the
"how". Comments are the conversation around the plan: the apprentice,
their employer and provider staff can all add to it, and a progress
update by staff is recorded as a comment too, so every objective carries
its own history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.training.sessions import TrainingPlanItem

# Objectives still being worked on. Deferred is paused, so it is neither
# open (it cannot fall overdue) nor finished.
OPEN_OBJECTIVE_STATUSES: frozenset[str] = frozenset({"Not started", "In progress"})


@dataclass
class LearningObjective:
    """One thing the apprentice will achieve, and by when."""

    objective_id: int
    apprentice_id: int
    title: str
    description: str | None = None
    ksb_codes: str | None = None
    target_date: str | None = None
    status: str = "Not started"
    progress: int = 0
    achieved_at: str | None = None
    created_by: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_OBJECTIVE_STATUSES

    def is_overdue(self, today: date) -> bool:
        target = _parse(self.target_date)
        return self.is_open and target is not None and today > target

    def rag(self, today: date) -> str | None:
        """Green when achieved or comfortably on time, Amber when the target
        is close, Red when it has passed. None for a deferred or withdrawn
        objective, which is not being judged."""
        if self.status == "Achieved":
            return "Green"
        if not self.is_open:
            return None
        if self.is_overdue(today):
            return "Red"
        target = _parse(self.target_date)
        if target is not None and target <= today + timedelta(days=config.OBJECTIVE_DUE_SOON_DAYS):
            return "Amber"
        return "Green"


@dataclass
class PlanComment:
    """One contribution to the conversation about a plan."""

    comment_id: int
    apprentice_id: int
    author: str
    author_role: str
    body: str
    objective_id: int | None = None
    # Set when the comment records a progress update.
    progress: int | None = None
    created_at: str = ""

    @property
    def author_label(self) -> str:
        return f"{self.author} ({config.ROLE_LABELS.get(self.author_role, self.author_role)})"


@dataclass
class LearningPlan:
    """An apprentice's whole plan: objectives, activities and comments."""

    apprentice_id: int
    objectives: list[LearningObjective] = field(default_factory=list)
    activities: list[TrainingPlanItem] = field(default_factory=list)
    # Newest first.
    comments: list[PlanComment] = field(default_factory=list)

    @property
    def counted_objectives(self) -> list[LearningObjective]:
        """Every objective except withdrawn ones, which no longer count."""
        return [o for o in self.objectives if o.status != "Withdrawn"]

    @property
    def overall_progress(self) -> float:
        counted = self.counted_objectives
        if not counted:
            return 0.0
        return round(sum(o.progress for o in counted) / len(counted), 1)

    @property
    def achieved(self) -> int:
        return sum(1 for o in self.objectives if o.status == "Achieved")

    @property
    def unlinked_activities(self) -> list[TrainingPlanItem]:
        return [a for a in self.activities if a.objective_id is None]

    def activities_for(self, objective_id: int) -> list[TrainingPlanItem]:
        return [a for a in self.activities if a.objective_id == objective_id]

    def comments_for(self, objective_id: int) -> list[PlanComment]:
        return [c for c in self.comments if c.objective_id == objective_id]

    def overdue(self, today: date) -> list[LearningObjective]:
        return [o for o in self.objectives if o.is_overdue(today)]

    def next_target(self, today: date) -> LearningObjective | None:
        """The open objective due soonest — overdue ones first."""
        dated = [o for o in self.objectives if o.is_open and _parse(o.target_date)]
        return min(dated, key=lambda o: o.target_date or "", default=None)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def validate_objective_status(value: str | None) -> str:
    cleaned = (value or "Not started").strip()
    match = next((s for s in config.OBJECTIVE_STATUSES if s.casefold() == cleaned.casefold()), None)
    if match is None:
        allowed = ", ".join(config.OBJECTIVE_STATUSES)
        raise ValidationError(f"Objective status must be one of: {allowed}")
    return match


def validate_progress(value: object) -> int:
    """Progress as a whole percentage from 0 to 100."""
    text = str(value if value is not None else "").strip().rstrip("%")
    if not text:
        return 0
    try:
        progress = round(float(text))
    except ValueError as exc:
        raise ValidationError("Progress must be a number from 0 to 100") from exc
    if not 0 <= progress <= 100:
        raise ValidationError("Progress must be from 0 to 100")
    return progress


def settle(status: str, progress: int) -> tuple[str, int]:
    """Make an objective's status and progress agree.

    Achieved means 100%, and an open objective reaching 100% is achieved.
    Any progress means it has started.
    """
    if status == "Achieved" or (progress >= 100 and status in OPEN_OBJECTIVE_STATUSES):
        return "Achieved", 100
    if status == "Not started" and progress > 0:
        return "In progress", progress
    return status, progress


def status_after_progress(
    current: str, progress: int, requested: str | None = None
) -> tuple[str, int]:
    """The status an objective should have once its progress changes.

    An explicit status wins. Otherwise an achieved objective whose
    progress is lowered has been reopened, rather than the lowered figure
    being quietly overruled back to 100%.
    """
    if requested:
        return settle(requested, progress)
    if current == "Achieved" and progress < 100:
        return settle("In progress", progress)
    return settle(current, progress)


def validate_comment(body: str | None) -> str:
    text = (body or "").strip()
    if not text:
        raise ValidationError("A comment cannot be empty")
    if len(text) > config.PLAN_COMMENT_MAX_LENGTH:
        raise ValidationError(
            f"A comment must be {config.PLAN_COMMENT_MAX_LENGTH} characters or fewer"
        )
    return text


def validate_plan_item_status(value: str | None, *, current: str | None = None) -> str:
    """A plan item status from the list — or the one the item already has.

    Plans written before the list existed stored free text, so editing
    such an item without touching its status must not reject it.
    """
    cleaned = (value or "").strip() or current or "Planned"
    if cleaned == current:
        return cleaned
    match = next(
        (s for s in config.PLAN_ITEM_STATUSES if s.casefold() == cleaned.casefold()), None
    )
    if match is None:
        allowed = ", ".join(config.PLAN_ITEM_STATUSES)
        raise ValidationError(f"Activity status must be one of: {allowed}")
    return match


def _parse(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso)
    except ValueError:
        return None
