"""Sixth-form alumni — Bulk CSV import, consent-aware export and saved searches.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import csv as _csv
import io as _io
import json as _json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    Alumnus,
    EXPORT_FIELDS,
    _log_action,
    logger,
)
from .db import (
    ValidationError,
    _connect,
    _require,
    _validate_payload,
    init_db,
)


# ══ Operational quality ══════════════════════════════════════════



# ── Bulk CSV import ──────────────────────────────────────────────

# Header tokens our importer recognises (lower-case) → canonical
# alumnus field name. Used to suggest a default column mapping
# from the CSV's headers.
_IMPORT_FIELD_ALIASES: dict[str, str] = {
    "first_name": "first_name", "first name": "first_name",
    "forename": "first_name", "given name": "first_name",
    "last_name": "last_name", "last name": "last_name",
    "surname": "last_name", "family name": "last_name",
    "preferred_name": "preferred_name",
    "preferred name": "preferred_name",
    "pronouns": "pronouns",
    "gender": "gender",
    "dob": "dob", "date of birth": "dob",
    "leaving_year": "leaving_year", "leaving year": "leaving_year",
    "year of leaving": "leaving_year",
    "leaving_date": "leaving_date",
    "leaving date": "leaving_date",
    "leaving_reason": "leaving_reason",
    "leaving reason": "leaving_reason",
    "destination_type": "destination_type",
    "destination": "destination_type",
    "destination_detail": "destination_detail",
    "destination detail": "destination_detail",
    "current_role": "current_role", "current role": "current_role",
    "role": "current_role",
    "current_employer": "current_employer",
    "employer": "current_employer",
    "current_sector": "current_sector", "sector": "current_sector",
    "current_location": "current_location",
    "location": "current_location",
    "country": "country", "region": "region",
    "email": "email", "email address": "email",
    "phone": "phone", "telephone": "phone", "mobile": "phone",
    "address": "address",
    "linkedin": "linkedin", "linkedin url": "linkedin",
    "other_social": "other_social",
    "notes": "notes",
    "original_student_id": "original_student_id",
    "student id": "original_student_id",
    "uln": "original_student_id",
    "opt_in_contact": "opt_in_contact",
    "opt in": "opt_in_contact",
    "status": "status",
}


@dataclass
class ImportPreview:
    total_rows: int
    will_create: int
    will_skip: int            # blank / missing required
    will_update: int           # match on original_student_id
    errors: list[tuple[int, str]]   # (row_no, message)


def _import_resolve_value(value: Any, field: str) -> Any:
    """Coerce a CSV string into the right Python shape for one of
    our fields. Most are str-or-None; bools (opt_in_contact) get
    parsed from yes/no/1/0/true/false."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    if field == "opt_in_contact":
        return s.lower() in ("yes", "y", "true", "1", "on")
    return s


def parse_import_csv(source: str | Path) -> list[dict[str, str]]:
    """Read a CSV file from disk and return raw rows (str values)
    with whitespace stripped. The header row is used as keys."""
    rows: list[dict[str, str]] = []
    with open(source, encoding="utf-8-sig", newline="") as f:
        reader = _csv.DictReader(f)
        for r in reader:
            rows.append({(k or "").strip():
                          (v or "").strip()
                          for k, v in r.items()})
    return rows


def suggest_import_mapping(headers: list[str]) -> dict[str, str]:
    """Return a {csv_column: alumni_field} suggestion based on
    header aliasing. Unknown columns are omitted (caller picks)."""
    out: dict[str, str] = {}
    for h in headers:
        key = (h or "").strip().lower()
        if key in _IMPORT_FIELD_ALIASES:
            out[h] = _IMPORT_FIELD_ALIASES[key]
    return out


def _shape_import_payload(row: dict[str, str],
                            mapping: dict[str, str]
                            ) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for col, field in mapping.items():
        if not field:
            continue
        payload[field] = _import_resolve_value(row.get(col, ""), field)
    return payload


def preview_import(rows: list[dict[str, str]],
                     mapping: dict[str, str]) -> ImportPreview:
    """Dry-run an import. Validates every row through the same
    pipeline as :func:`create_alumnus` (so the user sees the same
    errors) but writes nothing."""
    init_db()
    will_create = will_update = will_skip = 0
    errors: list[tuple[int, str]] = []
    for i, row in enumerate(rows, 1):
        payload = _shape_import_payload(row, mapping)
        if not payload.get("first_name") or not payload.get("last_name"):
            will_skip += 1
            errors.append((i, "missing first_name / last_name"))
            continue
        try:
            _validate_payload(payload)
        except ValidationError as e:
            errors.append((i, str(e)))
            will_skip += 1
            continue
        oid = payload.get("original_student_id")
        existing = (get_alumnus_by_original_id(oid)
                      if oid else None)
        if existing:
            will_update += 1
        else:
            will_create += 1
    return ImportPreview(
        total_rows=len(rows), will_create=will_create,
        will_skip=will_skip, will_update=will_update, errors=errors)


@dataclass
class ImportResult:
    created: int
    updated: int
    skipped: int
    errors: list[tuple[int, str]]


def apply_import(rows: list[dict[str, str]],
                   mapping: dict[str, str], *,
                   actor: str | None = None) -> ImportResult:
    """Commit the rows from a previously-previewed import."""
    init_db()
    created = updated = skipped = 0
    errors: list[tuple[int, str]] = []
    for i, row in enumerate(rows, 1):
        payload = _shape_import_payload(row, mapping)
        if not payload.get("first_name") or not payload.get("last_name"):
            skipped += 1
            continue
        try:
            oid = payload.get("original_student_id")
            existing = (get_alumnus_by_original_id(oid)
                          if oid else None)
            if existing:
                update_alumnus(existing.alumni_id, payload,
                                 actor=actor)
                updated += 1
            else:
                create_alumnus(payload)
                created += 1
        except ValidationError as e:
            errors.append((i, str(e)))
            skipped += 1
    _log_action("alumnus.bulk_import", actor=actor,
                  created=created, updated=updated,
                  skipped=skipped, errors=len(errors),
                  level=logging.WARNING if errors else logging.INFO)
    return ImportResult(created=created, updated=updated,
                          skipped=skipped, errors=errors)


# ── Bulk export with column picker + consent-aware redaction ─────

# Field → sensitivity class lookup derived from EXPORT_FIELDS.
_EXPORT_SENS: dict[str, str] = {f: s for f, s in EXPORT_FIELDS}

REDACTION_PLACEHOLDER: str = "[redacted]"


def _redact(value: Any, field: str, alumnus: Alumnus,
              has_photo_consent: bool) -> Any:
    """Apply consent-aware redaction rules. Contact / sensitive
    fields are redacted when ``opt_in_contact`` is false or status
    is Opt-out. Public-tier fields (bio, photo_path) require active
    ``Photo Use`` consent."""
    if value in (None, ""):
        return ""
    sens = _EXPORT_SENS.get(field, "internal")
    if alumnus.status == "Opt-out":
        if sens in ("contact", "sensitive", "internal",
                     "professional", "name", "public"):
            return REDACTION_PLACEHOLDER
    if sens in ("contact", "sensitive") and not alumnus.opt_in_contact:
        return REDACTION_PLACEHOLDER
    if sens == "public" and not has_photo_consent:
        return REDACTION_PLACEHOLDER
    if sens == "internal":
        # Notes etc. — never exported.
        return REDACTION_PLACEHOLDER
    return value


def export_alumni_csv(*, out_path: str | Path | None = None,
                         columns: list[str] | None = None,
                         filters: dict[str, Any] | None = None,
                         respect_consent: bool = True
                         ) -> str:
    """Render alumni to CSV. ``columns`` defaults to every field in
    :data:`EXPORT_FIELDS` (in that order); pass a subset to limit
    output. When ``respect_consent`` is true (the default) PII
    fields are replaced with a placeholder for alumni who haven't
    opted in / have opted out (see :func:`_redact`).

    If ``out_path`` is provided the CSV is written there and the
    path is returned; otherwise the CSV string is returned."""
    init_db()
    if columns is None:
        columns = [f for f, _ in EXPORT_FIELDS]
    else:
        unknown = [c for c in columns if c not in _EXPORT_SENS]
        if unknown:
            raise ValidationError(
                f"Unknown column(s): {', '.join(unknown)}")
    rows = list_alumni(**(filters or {}))
    consent_cache: dict[int, bool] = {}
    buf = _io.StringIO()
    w = _csv.writer(buf, quoting=_csv.QUOTE_MINIMAL)
    w.writerow(columns)
    for a in rows:
        if respect_consent:
            if a.alumni_id not in consent_cache:
                consent_cache[a.alumni_id] = has_active_consent(
                    a.alumni_id, "Photo Use")
            photo_ok = consent_cache[a.alumni_id]
        else:
            photo_ok = True
        out_row: list[Any] = []
        for c in columns:
            raw = getattr(a, c, "")
            if isinstance(raw, bool):
                raw = "yes" if raw else "no"
            if respect_consent:
                out_row.append(_redact(raw, c, a, photo_ok))
            else:
                out_row.append(raw if raw is not None else "")
        w.writerow(out_row)
    _log_action("alumnus.bulk_export", rows=len(rows),
                  columns=len(columns),
                  respect_consent=respect_consent,
                  out_path=str(out_path) if out_path else "(stdout)")
    if out_path:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            f.write(buf.getvalue())
        return str(out_path)
    return buf.getvalue()


# ── Saved searches ───────────────────────────────────────────────

@dataclass
class SavedSearch:
    search_id: int
    name: str
    description: str | None
    filters: dict[str, Any]
    owner_staff_id: str | None
    created_at: str


def _row_search(r: db.Row) -> SavedSearch:
    try:
        filters = _json.loads(r["filters_json"]) or {}
    except Exception:
        logger.warning("Corrupt filters_json for saved search #%s; "
                         "treating as empty",
                         r["search_id"], exc_info=True)
        filters = {}
    return SavedSearch(
        search_id=r["search_id"], name=r["name"],
        description=r["description"], filters=filters,
        owner_staff_id=r["owner_staff_id"],
        created_at=r["created_at"],
    )


# Filters that may appear in a saved-search payload (whitelist —
# anything else is rejected so saved searches stay portable).
_ALLOWED_SEARCH_KEYS: frozenset[str] = frozenset({
    "leaving_year", "destination_type", "status",
    "contactable_only", "search", "employer", "university",
    "sector", "country", "tag", "has_email", "include_deleted",
})


def save_search(name: str, filters: dict[str, Any], *,
                 description: str | None = None,
                 owner_staff_id: str | None = None,
                 replace: bool = False) -> SavedSearch:
    init_db()
    name = _require(name, "Search name").strip()
    bad = [k for k in filters if k not in _ALLOWED_SEARCH_KEYS]
    if bad:
        raise ValidationError(
            f"Unknown filter(s): {', '.join(bad)}")
    payload = _json.dumps(filters, sort_keys=True, default=str)
    with _connect() as conn:
        try:
            conn.execute(
                """INSERT INTO alumni_saved_searches
                       (name, description, filters_json,
                        owner_staff_id)
                   VALUES (?, ?, ?, ?)""",
                (name,
                 (description or "").strip() or None,
                 payload,
                 ((owner_staff_id or "").strip().upper() or None)))
        except db.IntegrityError:
            if not replace:
                raise ValidationError(
                    f"A saved search called '{name}' already "
                    "exists (use replace=True to overwrite)") \
                    from None
            conn.execute(
                """UPDATE alumni_saved_searches SET
                       description = ?, filters_json = ?,
                       owner_staff_id = ?
                   WHERE name = ?""",
                ((description or "").strip() or None,
                 payload,
                 ((owner_staff_id or "").strip().upper() or None),
                 name))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_saved_searches WHERE name = ?",
            (name,)).fetchone()
    _log_action("saved_search.save", actor=owner_staff_id,
                  name=name, filters=str(filters))
    return _row_search(r)


def list_saved_searches() -> list[SavedSearch]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_saved_searches "
            "ORDER BY name COLLATE NOCASE").fetchall()
    return [_row_search(r) for r in rows]


def get_saved_search(name: str) -> SavedSearch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_saved_searches "
            "WHERE name = ? COLLATE NOCASE",
            (name,)).fetchone()
    return _row_search(r) if r else None


def run_saved_search(name: str) -> list[Alumnus]:
    s = get_saved_search(name)
    if s is None:
        raise ValidationError(f"No saved search '{name}'")
    return list_alumni(**s.filters)


def delete_saved_search(name: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_saved_searches "
            "WHERE name = ? COLLATE NOCASE", (name,))
        conn.commit()
        deleted = cur.rowcount > 0
    if deleted:
        _log_action("saved_search.delete", name=name)
    return deleted


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .records import (  # noqa: E402,F401
    create_alumnus,
    get_alumnus_by_original_id,
    list_alumni,
    update_alumnus,
)
from .compliance import (  # noqa: E402,F401
    has_active_consent,
)
