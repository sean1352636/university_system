"""Surveys: asking apprentices and employers, and reading the answers in aggregate.

A survey is a set of fixed questions (chosen by its kind, from
``config.SURVEY_QUESTIONS``) answered on the satisfaction scale, plus a
free-text comment. The questions are fixed per kind rather than written
per survey so that this year's results can be compared with last
year's: a reworded question is a different question.

Results are anonymous, and that is a property of the aggregation here,
not a courtesy of the screen: :func:`summarise` never receives who
answered, and withholds everything below
``config.SURVEY_ANONYMITY_THRESHOLD`` responses, because an average of
one answer is that person's answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

SCALE: tuple[str, ...] = config.SATISFACTION_SCALE

# Which role answers a survey sent to each audience.
AUDIENCE_ROLES: dict[str, str] = {
    "Apprentice": config.APPRENTICE,
    "Employer": config.EMPLOYER,
}

SURVEY_TRANSITIONS: dict[str, frozenset[str]] = {
    "Draft": frozenset({"Open"}),
    "Open": frozenset({"Closed"}),
    "Closed": frozenset(),
}


@dataclass
class Survey:
    """One survey, sent to one audience."""

    survey_id: int
    title: str
    audience: str
    kind: str
    status: str = "Draft"
    opens_on: str | None = None
    closes_on: str | None = None
    created_by: str | None = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def questions(self) -> tuple[str, ...]:
        return config.SURVEY_QUESTIONS.get(self.kind, ())

    def is_accepting(self, today: date) -> bool:
        """Open, and today falls inside its dates."""
        if self.status != "Open":
            return False
        opens, closes = _parse(self.opens_on), _parse(self.closes_on)
        if opens is not None and today < opens:
            return False
        return not (closes is not None and today > closes)


@dataclass
class QuestionResult:
    """How one question was answered, across every response."""

    question: str
    average: float | None
    answered: int
    # How many chose each point on the scale, lowest first.
    distribution: tuple[int, ...] = ()

    @property
    def average_label(self) -> str:
        """The average as the nearest point on the scale."""
        if self.average is None:
            return config.EMPTY_CELL
        return SCALE[min(len(SCALE), max(1, round(self.average))) - 1]


@dataclass
class SurveyResults:
    """A survey's anonymised results."""

    survey: Survey
    response_count: int
    eligible_count: int
    responded_count: int
    questions: list[QuestionResult] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    # True when too few have answered to show anything without
    # identifying them.
    withheld: bool = False

    @property
    def response_rate(self) -> float | None:
        """Percentage of the eligible audience that has answered."""
        if not self.eligible_count:
            return None
        return round(min(100.0, 100.0 * self.responded_count / self.eligible_count), 1)


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def score_for(value: object) -> int:
    """A scale answer as a score from 1 to 5.

    Accepts the score itself or the scale label, so a form can post
    whichever it shows.
    """
    if isinstance(value, bool):
        raise ValidationError("An answer must be a point on the scale")
    if isinstance(value, int):
        score = value
    else:
        text = str(value if value is not None else "").strip()
        label = next((i for i, s in enumerate(SCALE, 1) if s.casefold() == text.casefold()), None)
        if label is not None:
            return label
        if not text.isdigit():
            raise ValidationError(f"Answers must be one of: {', '.join(SCALE)}")
        score = int(text)
    if not 1 <= score <= len(SCALE):
        raise ValidationError(f"A score must be from 1 to {len(SCALE)}")
    return score


def label_for(score: int) -> str:
    return SCALE[score - 1]


def validate_kind(value: str | None) -> str:
    return _match(value, config.SURVEY_KINDS, "Survey kind")


def validate_audience(kind: str, value: str | None) -> str:
    """An audience this kind of survey may be sent to."""
    audience = _match(value, config.SURVEY_AUDIENCES, "Audience")
    allowed = config.SURVEY_KIND_AUDIENCES.get(kind, config.SURVEY_AUDIENCES)
    if audience not in allowed:
        raise ValidationError(f"The {kind} survey is for: {', '.join(allowed)}")
    return audience


def require_transition(current: str, new: str) -> None:
    if new in SURVEY_TRANSITIONS.get(current, frozenset()):
        return
    raise ValidationError(f"A {current.lower()} survey cannot be set to {new}")


def validate_dates(opens_on: str | None, closes_on: str | None) -> tuple[str | None, str | None]:
    opens = _validate_date(opens_on, "Opening date")
    closes = _validate_date(closes_on, "Closing date")
    if opens and closes and closes < opens:
        raise ValidationError("A survey cannot close before it opens")
    return opens, closes


def validate_answers(kind: str, answers: dict[str, object] | None) -> dict[str, int]:
    """Every question for *kind* answered, and nothing else.

    A partial response would skew the per-question averages towards
    whoever bothered to finish, so all questions are required.
    """
    questions = config.SURVEY_QUESTIONS.get(kind, ())
    given = dict(answers or {})
    unknown = [q for q in given if q not in questions]
    if unknown:
        raise ValidationError(f"Not a question on this survey: {unknown[0]}")
    missing = [q for q in questions if given.get(q) in (None, "")]
    if missing:
        raise ValidationError(f"Please answer every question — missing: {missing[0]}")
    return {q: score_for(given[q]) for q in questions}


def validate_comment(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > config.SURVEY_COMMENT_MAX_LENGTH:
        raise ValidationError(
            f"A comment must be {config.SURVEY_COMMENT_MAX_LENGTH} characters or fewer"
        )
    return text


def eligible_statuses(kind: str) -> frozenset[str]:
    """Apprentice statuses that may answer a survey of *kind*."""
    if kind == "End of programme":
        return config.SURVEY_END_OF_PROGRAMME_STATUSES
    return config.ACTIVE_STATUSES


def summarise(
    survey: Survey,
    answer_sets: list[dict[str, int]],
    comments: list[str | None],
    *,
    eligible_count: int,
    responded_count: int,
) -> SurveyResults:
    """Aggregate a survey's answers.

    Takes the answers and comments with no respondent attached — there
    is nothing here that could leak a name. Comments are sorted rather
    than kept in the order they arrived, so they cannot be lined up
    against who was known to answer when.
    """
    count = len(answer_sets)
    results = SurveyResults(
        survey=survey,
        response_count=count,
        eligible_count=eligible_count,
        responded_count=responded_count,
    )
    if count < config.SURVEY_ANONYMITY_THRESHOLD:
        results.withheld = True
        return results

    for question in survey.questions:
        scores = [a[question] for a in answer_sets if isinstance(a.get(question), int)]
        results.questions.append(QuestionResult(
            question=question,
            average=round(sum(scores) / len(scores), 2) if scores else None,
            answered=len(scores),
            distribution=tuple(scores.count(point) for point in range(1, len(SCALE) + 1)),
        ))
    results.comments = sorted(c.strip() for c in comments if c and c.strip())
    return results


def _validate_date(value: str | None, label: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError as exc:
        raise ValidationError(f"{label} must be a date in YYYY-MM-DD format") from exc


def _match(value: str | None, allowed: tuple[str, ...], label: str) -> str:
    cleaned = (value or "").strip()
    match = next((s for s in allowed if s.casefold() == cleaned.casefold()), None)
    if match is None:
        raise ValidationError(f"{label} must be one of: {', '.join(allowed)}")
    return match


def _parse(iso: str | None) -> date | None:
    if not iso:
        return None
    try:
        return date.fromisoformat(iso[:10])
    except ValueError:
        return None
