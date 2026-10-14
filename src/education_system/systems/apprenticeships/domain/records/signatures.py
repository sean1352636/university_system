"""Digital signatures: who agreed to what, as it stood when they agreed.

A signature here is a claim about content. When somebody signs, the
thing they signed is hashed and the hash is stored with the signature;
the signature is valid only while the thing still hashes to that value.
Edit a learning plan after the employer signed it and the employer's
signature lapses by itself — nobody has to remember to withdraw it, and
nobody can quietly change an agreement underneath a signature.

Each login signs as exactly one signatory (config.SIGNATORY_BY_ROLE):
an apprentice as Apprentice, an employer as Employer, provider staff
as Provider. Which signatories a thing needs is configuration
(config.SIGNATURE_REQUIREMENTS).

The older, per-review ``review_signatures`` are a separate mechanism and
are not affected by this module.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError

LEARNING_PLAN = "learning_plan"
DOCUMENT = "document"

ENTITY_LABELS: dict[str, str] = {
    LEARNING_PLAN: "Learning plan",
    DOCUMENT: "Document",
}

SIGNED = "Signed"
INVALIDATED = "Invalidated"
AWAITING = "Awaiting"

# What of the plan is being agreed to: what will be achieved, how, and
# by when. Status and progress are deliberately left out — recording
# progress is working the plan, not changing the agreement, and it would
# otherwise void every signature the first time a tutor moved a figure.
PLAN_OBJECTIVE_FIELDS: tuple[str, ...] = (
    "objective_id", "title", "description", "ksb_codes", "target_date",
)
PLAN_ACTIVITY_FIELDS: tuple[str, ...] = (
    "item_id", "title", "description", "objective_id", "delivery_mode",
    "planned_start", "planned_end", "planned_hours", "ksb_codes",
)


@dataclass
class Signature:
    """One signatory's signature on one thing."""

    signature_id: int
    entity_type: str
    entity_id: int
    signatory_role: str
    signed_by: str
    statement: str
    content_hash: str
    apprentice_id: int | None = None
    signer_role: str | None = None
    signed_at: str = ""

    def is_valid_for(self, current_hash: str) -> bool:
        return bool(current_hash) and self.content_hash == current_hash


@dataclass
class SignOff:
    """Where one signable thing stands: who has signed, who still must."""

    entity_type: str
    entity_id: int
    content_hash: str
    required: tuple[str, ...]
    # Oldest first. A signatory may appear more than once: re-signing
    # after an edit adds a signature rather than rewriting the old one.
    signatures: list[Signature] = field(default_factory=list)
    apprentice_id: int | None = None
    title: str = ""

    def for_role(self, signatory_role: str) -> list[Signature]:
        return [s for s in self.signatures if s.signatory_role == signatory_role]

    def valid_signature(self, signatory_role: str) -> Signature | None:
        """The signatory's most recent signature on the content as it is now."""
        valid = [s for s in self.for_role(signatory_role) if s.is_valid_for(self.content_hash)]
        return valid[-1] if valid else None

    def latest(self, signatory_role: str) -> Signature | None:
        mine = self.for_role(signatory_role)
        return mine[-1] if mine else None

    def state(self, signatory_role: str) -> str:
        """Signed, Invalidated (signed, then changed), or Awaiting."""
        if self.valid_signature(signatory_role) is not None:
            return SIGNED
        if self.for_role(signatory_role):
            return INVALIDATED
        return AWAITING

    @property
    def outstanding(self) -> list[str]:
        return [r for r in self.required if self.state(r) != SIGNED]

    @property
    def invalidated(self) -> list[str]:
        return [r for r in self.required if self.state(r) == INVALIDATED]

    @property
    def signed_count(self) -> int:
        return sum(1 for r in self.required if self.state(r) == SIGNED)

    @property
    def is_required(self) -> bool:
        return bool(self.required)

    @property
    def is_complete(self) -> bool:
        return self.is_required and not self.outstanding

    @property
    def summary(self) -> str:
        if not self.required:
            return "Not required"
        if self.is_complete:
            return "Fully signed"
        text = f"{self.signed_count} of {len(self.required)} signed"
        if self.invalidated:
            text += f" — {', '.join(self.invalidated)} to re-sign"
        return text

    @property
    def rag(self) -> str | None:
        if not self.required:
            return None
        if self.is_complete:
            return "Green"
        return "Red" if self.invalidated else "Amber"


@dataclass
class PendingSignature:
    """Something waiting for one signatory — a row on "Awaiting Signature"."""

    signoff: SignOff
    signatory_role: str
    title: str
    apprentice_name: str | None = None
    category: str | None = None

    @property
    def entity_type(self) -> str:
        return self.signoff.entity_type

    @property
    def entity_id(self) -> int:
        return self.signoff.entity_id

    @property
    def status(self) -> str:
        return self.signoff.state(self.signatory_role)

    @property
    def what(self) -> str:
        return ENTITY_LABELS.get(self.entity_type, self.entity_type)

    @property
    def key(self) -> str:
        """A stable identity for a list row: entity type and id together."""
        return f"{self.entity_type}:{self.entity_id}"


# ═════════════════════════════════════════════════════════════════════
# Rules
# ═════════════════════════════════════════════════════════════════════

def required_signatories(entity_type: str, category: str | None = None) -> tuple[str, ...]:
    """Who must sign this kind of thing. Empty means nobody.

    A document's requirement depends on its category, so it is looked
    up as ``document:<category>`` first and the bare type second.
    """
    if category:
        specific = config.SIGNATURE_REQUIREMENTS.get(f"{entity_type}:{category}")
        if specific is not None:
            return tuple(specific)
    return tuple(config.SIGNATURE_REQUIREMENTS.get(entity_type, ()))


def signatory_for(role: str | None) -> str | None:
    """The signatory a login of *role* signs as, or None if it never signs."""
    return config.SIGNATORY_BY_ROLE.get(role or "")


def validate_statement(value: str | None) -> str:
    text = (value or "").strip() or config.SIGNATURE_DEFAULT_STATEMENT
    if len(text) > config.SIGNATURE_STATEMENT_MAX_LENGTH:
        raise ValidationError(
            f"A signature statement must be {config.SIGNATURE_STATEMENT_MAX_LENGTH} "
            "characters or fewer"
        )
    return text


def require_can_sign(signoff: SignOff, signatory_role: str | None) -> str:
    """Refuse a signature this signatory has no business adding."""
    if signatory_role is None:
        raise ValidationError("Your role does not sign records")
    if not signoff.required:
        raise ValidationError("This does not need signing")
    if signatory_role not in signoff.required:
        raise ValidationError(f"This does not need a {signatory_role} signature")
    if signoff.state(signatory_role) == SIGNED:
        raise ValidationError(
            f"This already carries a valid {signatory_role} signature for its current content"
        )
    return signatory_role


# ═════════════════════════════════════════════════════════════════════
# Hashing
# ═════════════════════════════════════════════════════════════════════

def content_hash(content: Any) -> str:
    """A stable SHA-256 of a JSON-able structure.

    Keys are sorted and whitespace fixed, so the same content always
    hashes the same however it was assembled.
    """
    canonical = json.dumps(
        content, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def plan_content(objectives: Iterable[Any], activities: Iterable[Any]) -> dict[str, Any]:
    """The part of a learning plan that a signature agrees to."""
    return {
        "objectives": sorted(
            (_pick(o, PLAN_OBJECTIVE_FIELDS) for o in objectives),
            key=lambda row: row.get("objective_id") or 0,
        ),
        "activities": sorted(
            (_pick(a, PLAN_ACTIVITY_FIELDS) for a in activities),
            key=lambda row: row.get("item_id") or 0,
        ),
    }


def plan_hash(objectives: Iterable[Any], activities: Iterable[Any]) -> str:
    return content_hash(plan_content(objectives, activities))


def document_hash(sha256: str) -> str:
    """A document's signed content is its file: the file's own digest."""
    return sha256


def signoff(
    entity_type: str,
    entity_id: int,
    current_hash: str,
    required: Sequence[str],
    signatures: Iterable[Signature],
    *,
    apprentice_id: int | None = None,
    title: str = "",
) -> SignOff:
    return SignOff(
        entity_type=entity_type,
        entity_id=entity_id,
        content_hash=current_hash,
        required=tuple(required),
        signatures=sorted(signatures, key=lambda s: (s.signed_at, s.signature_id)),
        apprentice_id=apprentice_id,
        title=title,
    )


def _pick(record: Any, names: Sequence[str]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for name in names:
        value = getattr(record, name, None)
        if isinstance(value, str):
            value = value.strip() or None
        elif isinstance(value, float) and value.is_integer():
            # 7 and 7.0 are the same number of hours.
            value = int(value)
        row[name] = value
    return row
