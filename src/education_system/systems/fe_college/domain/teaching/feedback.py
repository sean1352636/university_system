"""Feedback on marked work, and the internal verification that samples it.

FE quality assurance requires a proportion of every assessor's marking to be
internally verified. The sampling rule lives here so the IV screen and the
reports agree on what "enough sampling" means.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from education_system.systems.fe_college.domain.students.models import (
    optional_ref,
    ValidationError,
    parse_date,
)

FEEDBACK_TYPES = ("Formative", "Summative", "Verbal", "Action plan")

IV_OUTCOMES = ("Agreed", "Agreed with comments", "Not agreed — remark required")

# Minimum share of an assessor's marked work that must be internally verified,
# and the floor below which the percentage rule is meaningless.
IV_SAMPLE_PCT = 20.0
IV_MINIMUM_SAMPLE = 2


@dataclass
class Feedback:
    """Written feedback attached to a marked submission."""

    feedback_id: int | None
    submission_id: int
    author_id: str                   # staff_id
    body: str
    feedback_type: str = "Summative"
    strengths: str = ""
    improvements: str = ""
    given_at: date | None = None
    seen_by_student: bool = False

    def validate(self) -> None:
        if not self.author_id.strip():
            raise ValidationError("Feedback must record its author")
        if not self.body.strip():
            raise ValidationError("Feedback cannot be empty")
        if self.feedback_type not in FEEDBACK_TYPES:
            raise ValidationError(f"Unknown feedback type '{self.feedback_type}'")

    def to_row(self) -> dict:
        return {
            "submission_id": int(self.submission_id),
            "author_id": optional_ref(self.author_id),
            "body": self.body.strip(),
            "feedback_type": self.feedback_type,
            "strengths": self.strengths.strip(),
            "improvements": self.improvements.strip(),
            "given_at": self.given_at.isoformat() if self.given_at else None,
            "seen_by_student": 1 if self.seen_by_student else 0,
        }

    @classmethod
    def from_row(cls, row) -> "Feedback":
        d = dict(row)
        return cls(
            feedback_id=d.get("feedback_id"),
            submission_id=int(d.get("submission_id") or 0),
            author_id=d.get("author_id") or "",
            body=d.get("body") or "",
            feedback_type=d.get("feedback_type") or "Summative",
            strengths=d.get("strengths") or "",
            improvements=d.get("improvements") or "",
            given_at=parse_date(d.get("given_at")),
            seen_by_student=bool(d.get("seen_by_student")),
        )


@dataclass
class InternalVerification:
    """One IV check of an assessor's marking decision."""

    iv_id: int | None
    submission_id: int
    verifier_id: str
    outcome: str = "Agreed"
    comments: str = ""
    verified_at: date | None = None

    @property
    def requires_remark(self) -> bool:
        return self.outcome == "Not agreed — remark required"

    def validate(self) -> None:
        if not self.verifier_id.strip():
            raise ValidationError("Internal verification must record its verifier")
        if self.outcome not in IV_OUTCOMES:
            raise ValidationError(f"Unknown IV outcome '{self.outcome}'")
        if self.requires_remark and not self.comments.strip():
            raise ValidationError("A 'not agreed' verification must explain why")

    def to_row(self) -> dict:
        return {
            "submission_id": int(self.submission_id),
            "verifier_id": optional_ref(self.verifier_id),
            "outcome": self.outcome,
            "comments": self.comments.strip(),
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
        }

    @classmethod
    def from_row(cls, row) -> "InternalVerification":
        d = dict(row)
        return cls(
            iv_id=d.get("iv_id"),
            submission_id=int(d.get("submission_id") or 0),
            verifier_id=d.get("verifier_id") or "",
            outcome=d.get("outcome") or "Agreed",
            comments=d.get("comments") or "",
            verified_at=parse_date(d.get("verified_at")),
        )


def required_sample_size(marked_count: int) -> int:
    """How many of ``marked_count`` marked pieces must be internally verified.

    20% rounded up, with a floor of 2 — sampling one piece of work out of three
    tells a quality manager nothing.
    """
    if marked_count <= 0:
        return 0
    if marked_count <= IV_MINIMUM_SAMPLE:
        return marked_count
    return max(IV_MINIMUM_SAMPLE, math.ceil(marked_count * IV_SAMPLE_PCT / 100))


def sampling_shortfall(marked_count: int, verified_count: int) -> int:
    """How many more pieces need verifying to meet the sampling rule."""
    return max(0, required_sample_size(marked_count) - verified_count)


__all__ = [
    "FEEDBACK_TYPES",
    "IV_MINIMUM_SAMPLE",
    "IV_OUTCOMES",
    "IV_SAMPLE_PCT",
    "Feedback",
    "InternalVerification",
    "required_sample_size",
    "sampling_shortfall",
]
