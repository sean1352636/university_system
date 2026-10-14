"""Versions of an apprenticeship standard.

IfATE revises standards: version 1.1 of ST0119 may reword a KSB or change
an assessment method. Apprentices already training towards 1.0 finish on
1.0, so a new version is a new programme row that shares the reference,
and the old row becomes 'Superseded' — closed to new enrolments, still
delivered to the people on it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from education_system.systems.apprenticeships.domain.apprentices.models import ValidationError
from education_system.systems.apprenticeships.domain.programmes.models import Programme

_VERSION_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){0,2}$")


@dataclass
class ProgrammeVersion:
    """One version of a standard, and how many apprentices are on it."""

    programme: Programme
    apprentices: int = 0

    @property
    def is_current(self) -> bool:
        return self.programme.status == "Active"


def validate_version(value: object) -> str:
    """A dotted version number such as 1.0, 1.2 or 2."""
    text = str(value or "").strip().lstrip("vV")
    if not _VERSION_RE.match(text):
        raise ValidationError("A version is one to three numbers separated by dots, e.g. 1.1")
    return text


def version_key(version: str | None) -> tuple[int, ...]:
    """Numeric sort key, so 1.10 comes after 1.9."""
    try:
        return tuple(int(part) for part in (version or "0").split("."))
    except ValueError:
        return (0,)


def next_version(current: str | None) -> str:
    """The next minor version: 1.0 -> 1.1, 1.9 -> 1.10, 2 -> 2.1."""
    parts = list(version_key(current or "1.0"))
    if len(parts) == 1:
        parts.append(1)
    else:
        parts[-1] += 1
    return ".".join(str(p) for p in parts)


def require_newer(candidate: str, current: str) -> str:
    """Refuse a new version that does not come after the current one."""
    cleaned = validate_version(candidate)
    if version_key(cleaned) <= version_key(current):
        raise ValidationError(f"The new version must come after {current}")
    return cleaned
