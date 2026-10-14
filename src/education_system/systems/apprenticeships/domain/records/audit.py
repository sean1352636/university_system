"""Audit diffs: what an edit changed, field by field.

The audit log has always said *that* a record was edited, by whom and
when. The next question an auditor asks is what it said before — and a
detail line of "status, tutor_id" cannot answer it. So an edit now
carries a list of ``{field, before, after}`` alongside the free-text
detail, and this module is the one place that list is worked out,
stored and read back.

Pure: no database, no interface. The services diff the record they
loaded against the one they saved; the repository stores the JSON; the
screens render ``field: before → after``.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.apprenticeships import config
from education_system.systems.apprenticeships.domain.compliance.eligibility import AuditEntry

ARROW = "→"

# Bookkeeping columns that move on every write and say nothing about it.
# Skipped only when the caller has not named the fields to compare.
IGNORED_FIELDS: frozenset[str] = frozenset({"created_at", "updated_at"})


@dataclass(frozen=True)
class FieldChange:
    """One field's move from one value to another."""

    field: str
    before: Any = None
    after: Any = None

    @property
    def label(self) -> str:
        return f"{self.field}: {_show(self.before)} {ARROW} {_show(self.after)}"

    def as_dict(self) -> dict[str, Any]:
        return {"field": self.field, "before": self.before, "after": self.after}


@dataclass
class AuditRecord(AuditEntry):
    """An audit entry together with the field changes it recorded.

    A subclass rather than a new field on ``AuditEntry`` so that every
    existing reader of the audit trail keeps working untouched: it is
    still an ``AuditEntry``, with ``changes`` on top.
    """

    changes: list[FieldChange] = field(default_factory=list)

    @property
    def changes_text(self) -> str:
        return describe(self.changes)


# ═════════════════════════════════════════════════════════════════════
# Working out the changes
# ═════════════════════════════════════════════════════════════════════

def diff(
    before: Any, after: Any, *, fields: Iterable[str] | None = None
) -> list[dict[str, Any]]:
    """The fields whose value differs between two versions of a record.

    *before* and *after* may each be a dataclass instance, a mapping, or
    None (the record did not exist yet, or no longer does). *fields*
    names what to compare; left out, it is the fields of *after* (or of
    *before* when there is no after), less the timestamp bookkeeping.

    Returns plain JSON-ready dicts in field order, ready to hand to
    ``compliance_repository.record(changes=...)``. A blank string and
    None count as the same value — a form sends "" where the database
    holds NULL, and that is not a change anybody made.
    """
    old = _as_mapping(before)
    new = _as_mapping(after)
    keys = list(dict.fromkeys(fields)) if fields is not None else _default_keys(before, after)
    out: list[dict[str, Any]] = []
    for key in keys:
        was, now = _normalise(old.get(key)), _normalise(new.get(key))
        if was == now:
            continue
        out.append({"field": key, "before": was, "after": now})
    return out


def change(field_name: str, before: Any, after: Any) -> list[dict[str, Any]]:
    """A single change, or nothing if the value did not actually move.

    For writes that are not a record-against-record edit — a role grant,
    a login linked to a record — where there is one value to report.
    """
    return diff({field_name: before}, {field_name: after}, fields=[field_name])


# ═════════════════════════════════════════════════════════════════════
# Storing and reading back
# ═════════════════════════════════════════════════════════════════════

def encode(changes: Sequence[Any] | None) -> str | None:
    """Serialise a change list for the ``audit_log.changes`` column.

    Accepts :class:`FieldChange` objects, ``{field, before, after}``
    mappings or ``(field, before, after)`` tuples, so callers can use
    whichever is to hand. Empty means NULL: an event, not an edit.
    """
    if not changes:
        return None
    rows = [_coerce(item).as_dict() for item in changes]
    rows = [r for r in rows if r["field"]]
    if not rows:
        return None
    return json.dumps(rows, ensure_ascii=False, default=str)


def decode(text: str | None) -> list[FieldChange]:
    """Read the stored JSON back. Never raises.

    A value that will not parse is still shown rather than dropped: an
    audit screen that silently hides a row it cannot read is worse than
    one that shows it raw.
    """
    if not text:
        return []
    try:
        rows = json.loads(text)
    except (TypeError, ValueError):
        return [FieldChange(field="(unreadable)", after=_truncate(str(text)))]
    if not isinstance(rows, list):
        return [FieldChange(field="(unreadable)", after=_truncate(str(text)))]
    out: list[FieldChange] = []
    for row in rows:
        try:
            out.append(_coerce(row))
        except (TypeError, ValueError):
            out.append(FieldChange(field="(unreadable)", after=_truncate(str(row))))
    return out


def describe(changes: Sequence[FieldChange], *, sep: str = "; ") -> str:
    """``status: Applicant → On Programme; tutor_id: — → 4``."""
    return sep.join(c.label for c in changes)


# ═════════════════════════════════════════════════════════════════════
# Helpers
# ═════════════════════════════════════════════════════════════════════

def _as_mapping(value: Any) -> Mapping[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return value
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: getattr(value, f.name) for f in dataclasses.fields(value)}
    return {}


def _default_keys(before: Any, after: Any) -> list[str]:
    source = after if after is not None else before
    if isinstance(source, Mapping):
        keys = list(source)
    elif dataclasses.is_dataclass(source) and not isinstance(source, type):
        keys = [f.name for f in dataclasses.fields(source)]
    else:
        keys = []
    return [k for k in keys if k not in IGNORED_FIELDS]


def _normalise(value: Any) -> Any:
    """A JSON-friendly, comparable form of one value."""
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return _truncate(text) if text else None
    if isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, (list, tuple, set, frozenset)):
        items = [_normalise(v) for v in value]
        return sorted(items, key=str) if isinstance(value, (set, frozenset)) else items
    return _truncate(str(value))


def _truncate(text: str) -> str:
    limit = config.AUDIT_CHANGE_VALUE_MAX_LENGTH
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _coerce(item: Any) -> FieldChange:
    if isinstance(item, FieldChange):
        return item
    if isinstance(item, Mapping):
        return FieldChange(
            field=str(item.get("field") or ""),
            before=_normalise(item.get("before")),
            after=_normalise(item.get("after")),
        )
    if isinstance(item, (tuple, list)) and len(item) == 3:
        name, before, after = item
        return FieldChange(field=str(name), before=_normalise(before), after=_normalise(after))
    raise TypeError(f"Not a field change: {item!r}")


def _show(value: Any) -> str:
    if value is None or value == "":
        return config.EMPTY_CELL
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)
