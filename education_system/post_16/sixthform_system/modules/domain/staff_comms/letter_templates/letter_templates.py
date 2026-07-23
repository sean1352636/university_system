"""Letter Templates data layer for Sixth Form System.

Reusable letter / email templates with `{{placeholder}}` merge
fields. A simple `render(template, context)` helper substitutes
placeholders against a context dict and reports any missing
required fields.
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator
from education_system.post_16.sixthform_system.core import paths as _paths

logger = logging.getLogger(__name__)

CATEGORIES: tuple[str, ...] = (
    "Welcome / Induction",
    "Attendance",
    "Behaviour",
    "Achievement",
    "Awards",
    "Parents' Evening",
    "Trip / Visit",
    "Bursary / Finance",
    "Disciplinary",
    "Reference",
    "Offer Letter",
    "Rejection Letter",
    "Reminder",
    "Safeguarding",
    "Examinations",
    "UCAS",
    "End of Year",
    "Other",
)
DEFAULT_CATEGORY = "Other"

RECIPIENT_TYPES: tuple[str, ...] = (
    "Student",
    "Parent / Carer",
    "Both",
    "Staff",
    "External Agency",
    "University",
    "Employer",
    "Other",
)
DEFAULT_RECIPIENT_TYPE = "Parent / Carer"

STATUSES: tuple[str, ...] = (
    "Draft",
    "Active",
    "Archived",
    "Retired",
)
DEFAULT_STATUS = "Draft"

FORMATS: tuple[str, ...] = (
    "Letter",
    "Email",
    "SMS",
    "Both Letter & Email",
)
DEFAULT_FORMAT = "Letter"


class ValidationError(Exception):
    pass


_PLACEHOLDER_RE = re.compile(r"\{\{\s*([a-zA-Z_][\w]*)\s*\}\}")


def extract_placeholders(text: str | None) -> list[str]:
    """Return distinct placeholders in order of first occurrence."""
    if not text:
        return []
    seen: list[str] = []
    for m in _PLACEHOLDER_RE.finditer(text):
        name = m.group(1)
        if name not in seen:
            seen.append(name)
    return seen


@dataclass
class Template:
    template_id: int
    name: str
    description: str | None
    category: str
    recipient_type: str
    format: str
    subject_line: str | None
    body: str
    letterhead: str | None
    footer: str | None
    signature: str | None
    sender_role: str | None
    merge_fields: str | None
    attachments_ref: str | None
    status: str
    created_by: str | None
    last_used_on: str | None
    use_count: int
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def is_active(self) -> bool:
        return self.status == "Active"

    @property
    def merge_field_list(self) -> list[str]:
        if not self.merge_fields:
            return []
        return [f.strip() for f in self.merge_fields.split(",")
                  if f.strip()]

    @property
    def detected_placeholders(self) -> list[str]:
        """Placeholders actually present in the template body
        and subject line."""
        result = list(extract_placeholders(self.subject_line))
        for p in extract_placeholders(self.body):
            if p not in result:
                result.append(p)
        return result


@dataclass
class RenderedTemplate:
    subject: str | None
    body: str
    missing_fields: list[str]


@dataclass
class TemplatesSummary:
    total: int = 0
    active: int = 0
    drafts: int = 0
    archived: int = 0
    retired: int = 0
    total_uses: int = 0
    most_used_name: str | None = None
    most_used_count: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_recipient_type: dict[str, int] = field(default_factory=dict)
    by_format: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.LETTER_TEMPLATES_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS letter_templates (
                template_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                description TEXT,
                category TEXT NOT NULL,
                recipient_type TEXT NOT NULL,
                format TEXT NOT NULL,
                subject_line TEXT,
                body TEXT NOT NULL,
                letterhead TEXT,
                footer TEXT,
                signature TEXT,
                sender_role TEXT,
                merge_fields TEXT,
                attachments_ref TEXT,
                status TEXT NOT NULL,
                created_by TEXT,
                last_used_on TEXT,
                use_count INTEGER NOT NULL DEFAULT 0,
                notes TEXT,
                created_on TEXT NOT NULL,
                updated_on TEXT NOT NULL
            )
        """)


def _check_date(label: str, value: str | None) -> None:
    if value in (None, ""):
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(f"{label} must be YYYY-MM-DD")


def _validate_payload(p: dict[str, Any], *,
                          existing_id: int | None = None
                          ) -> dict[str, Any]:
    out = dict(p)
    out["name"] = (out.get("name") or "").strip()
    if not out["name"]:
        raise ValidationError("Name is required")

    cat = (out.get("category") or DEFAULT_CATEGORY).strip()
    if cat not in CATEGORIES:
        raise ValidationError(
            f"Category must be one of: {', '.join(CATEGORIES)}")
    out["category"] = cat

    rt = (out.get("recipient_type")
            or DEFAULT_RECIPIENT_TYPE).strip()
    if rt not in RECIPIENT_TYPES:
        raise ValidationError(
            f"Recipient type must be one of: "
            f"{', '.join(RECIPIENT_TYPES)}")
    out["recipient_type"] = rt

    fmt = (out.get("format") or DEFAULT_FORMAT).strip()
    if fmt not in FORMATS:
        raise ValidationError(
            f"Format must be one of: {', '.join(FORMATS)}")
    out["format"] = fmt

    status = (out.get("status") or DEFAULT_STATUS).strip()
    if status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    out["status"] = status

    out["body"] = out.get("body") or ""
    if not isinstance(out["body"], str) or not out["body"].strip():
        raise ValidationError("Body is required")

    _check_date("Last used on", out.get("last_used_on"))

    # Normalise merge_fields (accept list or comma-string)
    mf = out.get("merge_fields")
    if mf is None:
        detected = extract_placeholders(out.get("subject_line"))
        for p_ in extract_placeholders(out["body"]):
            if p_ not in detected:
                detected.append(p_)
        out["merge_fields"] = (", ".join(detected)
                                    if detected else None)
    elif isinstance(mf, (list, tuple)):
        parts = [str(f).strip() for f in mf if str(f).strip()]
        out["merge_fields"] = (", ".join(parts) if parts
                                    else None)
    elif isinstance(mf, str):
        parts = [f.strip() for f in mf.split(",") if f.strip()]
        out["merge_fields"] = (", ".join(parts) if parts
                                    else None)

    uc = out.get("use_count")
    if uc in (None, ""):
        out["use_count"] = 0
    else:
        try:
            out["use_count"] = int(uc)
        except (TypeError, ValueError):
            raise ValidationError(
                "Use count must be an integer")
        if out["use_count"] < 0:
            raise ValidationError("Use count must be >= 0")

    for k in ("description", "subject_line", "letterhead",
               "footer", "signature", "sender_role",
               "attachments_ref", "created_by", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    out["last_used_on"] = (
        (out.get("last_used_on") or "").strip() or None
        if isinstance(out.get("last_used_on"), str)
        else out.get("last_used_on"))

    # Uniqueness on name
    with _connect() as conn:
        row = conn.execute(
            "SELECT template_id FROM letter_templates "
            "WHERE name=?", (out["name"],)).fetchone()
    if row and row["template_id"] != existing_id:
        raise ValidationError(
            f"A template named {out['name']!r} already exists")
    return out


def _row(r: sqlite3.Row) -> Template:
    return Template(
        template_id=r["template_id"],
        name=r["name"],
        description=r["description"],
        category=r["category"],
        recipient_type=r["recipient_type"],
        format=r["format"],
        subject_line=r["subject_line"],
        body=r["body"],
        letterhead=r["letterhead"],
        footer=r["footer"],
        signature=r["signature"],
        sender_role=r["sender_role"],
        merge_fields=r["merge_fields"],
        attachments_ref=r["attachments_ref"],
        status=r["status"],
        created_by=r["created_by"],
        last_used_on=r["last_used_on"],
        use_count=r["use_count"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def create_template(payload: dict[str, Any]) -> Template:
    init_db()
    p = _validate_payload(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO letter_templates (
              name, description, category, recipient_type,
              format, subject_line, body,
              letterhead, footer, signature, sender_role,
              merge_fields, attachments_ref, status,
              created_by, last_used_on, use_count, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?)
        """, (
            p["name"], p["description"], p["category"],
            p["recipient_type"], p["format"],
            p["subject_line"], p["body"],
            p["letterhead"], p["footer"], p["signature"],
            p["sender_role"], p["merge_fields"],
            p["attachments_ref"], p["status"],
            p["created_by"], p["last_used_on"],
            p["use_count"], p["notes"], now, now,
        ))
        new_id = cur.lastrowid
    return get_template(new_id)


def update_template(template_id: int,
                        payload: dict[str, Any]) -> Template:
    init_db()
    if get_template(template_id) is None:
        raise ValidationError(
            f"No template with id {template_id}")
    p = _validate_payload(payload, existing_id=template_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE letter_templates SET
              name=?, description=?, category=?,
              recipient_type=?, format=?,
              subject_line=?, body=?,
              letterhead=?, footer=?, signature=?, sender_role=?,
              merge_fields=?, attachments_ref=?, status=?,
              created_by=?, last_used_on=?, use_count=?,
              notes=?, updated_on=?
            WHERE template_id=?
        """, (
            p["name"], p["description"], p["category"],
            p["recipient_type"], p["format"],
            p["subject_line"], p["body"],
            p["letterhead"], p["footer"], p["signature"],
            p["sender_role"], p["merge_fields"],
            p["attachments_ref"], p["status"],
            p["created_by"], p["last_used_on"],
            p["use_count"], p["notes"], now, template_id,
        ))
    return get_template(template_id)


def delete_template(template_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM letter_templates "
            "WHERE template_id=?", (template_id,))
        return cur.rowcount > 0


def get_template(template_id: int) -> Template | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM letter_templates "
            "WHERE template_id=?",
            (template_id,)).fetchone()
        return _row(r) if r else None


def get_template_by_name(name: str) -> Template | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM letter_templates WHERE name=?",
            (name.strip(),)).fetchone()
        return _row(r) if r else None


def list_templates(*,
                       category: str | None = None,
                       recipient_type: str | None = None,
                       format: str | None = None,
                       status: str | None = None,
                       active_only: bool = False,
                       name_like: str | None = None,
                       created_by_like: str | None = None,
                       ) -> list[Template]:
    init_db()
    sql = "SELECT * FROM letter_templates WHERE 1=1"
    params: list[Any] = []
    if category:
        sql += " AND category=?"
        params.append(category)
    if recipient_type:
        sql += " AND recipient_type=?"
        params.append(recipient_type)
    if format:
        sql += " AND format=?"
        params.append(format)
    if status:
        sql += " AND status=?"
        params.append(status)
    if active_only:
        sql += " AND status='Active'"
    if name_like:
        sql += " AND name LIKE ?"
        params.append(f"%{name_like}%")
    if created_by_like:
        sql += " AND created_by LIKE ?"
        params.append(f"%{created_by_like}%")
    sql += " ORDER BY category, name"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row(r) for r in rows]


# ── Workflow ──────────────────────────────────────────────

def _to_dict(t: Template) -> dict[str, Any]:
    return {
        "name": t.name,
        "description": t.description,
        "category": t.category,
        "recipient_type": t.recipient_type,
        "format": t.format,
        "subject_line": t.subject_line,
        "body": t.body,
        "letterhead": t.letterhead,
        "footer": t.footer,
        "signature": t.signature,
        "sender_role": t.sender_role,
        "merge_fields": t.merge_fields,
        "attachments_ref": t.attachments_ref,
        "status": t.status,
        "created_by": t.created_by,
        "last_used_on": t.last_used_on,
        "use_count": t.use_count,
        "notes": t.notes,
    }


def activate(template_id: int) -> Template:
    t = get_template(template_id)
    if t is None:
        raise ValidationError(
            f"No template with id {template_id}")
    return update_template(template_id,
                                {**_to_dict(t),
                                  "status": "Active"})


def archive(template_id: int) -> Template:
    t = get_template(template_id)
    if t is None:
        raise ValidationError(
            f"No template with id {template_id}")
    return update_template(template_id,
                                {**_to_dict(t),
                                  "status": "Archived"})


def retire(template_id: int) -> Template:
    t = get_template(template_id)
    if t is None:
        raise ValidationError(
            f"No template with id {template_id}")
    return update_template(template_id,
                                {**_to_dict(t),
                                  "status": "Retired"})


def set_status(template_id: int, new_status: str) -> Template:
    if new_status not in STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(STATUSES)}")
    t = get_template(template_id)
    if t is None:
        raise ValidationError(
            f"No template with id {template_id}")
    return update_template(template_id,
                                {**_to_dict(t),
                                  "status": new_status})


def duplicate(template_id: int, *,
                  new_name: str) -> Template:
    """Create a copy under a new name (Draft status, use_count
    reset)."""
    t = get_template(template_id)
    if t is None:
        raise ValidationError(
            f"No template with id {template_id}")
    if not new_name:
        raise ValidationError("New name is required")
    data = _to_dict(t)
    data["name"] = new_name
    data["status"] = "Draft"
    data["use_count"] = 0
    data["last_used_on"] = None
    return create_template(data)


# ── Render ────────────────────────────────────────────────

def render(template: Template | int,
              context: dict[str, Any], *,
              track_use: bool = True
              ) -> RenderedTemplate:
    """Substitute `{{placeholder}}` tokens in `subject_line` and
    `body` against `context`. Returns the rendered result with
    a list of any placeholders that were missing from `context`."""
    if isinstance(template, int):
        t = get_template(template)
        if t is None:
            raise ValidationError(
                f"No template with id {template}")
    else:
        t = template
    placeholders = t.detected_placeholders
    ctx = {str(k): ("" if v is None else str(v))
              for k, v in (context or {}).items()}
    missing = [p for p in placeholders if p not in ctx]

    def _sub(text: str | None) -> str | None:
        if text is None:
            return None
        def repl(m: re.Match[str]) -> str:
            return ctx.get(m.group(1), m.group(0))
        return _PLACEHOLDER_RE.sub(repl, text)

    rendered = RenderedTemplate(
        subject=_sub(t.subject_line),
        body=_sub(t.body) or "",
        missing_fields=missing,
    )
    if track_use and not missing:
        record_use(t.template_id)
    return rendered


def preview(template: Template | int) -> RenderedTemplate:
    """Render with an empty context — no use tracking. Useful
    for showing the raw template with placeholders intact."""
    if isinstance(template, int):
        t = get_template(template)
        if t is None:
            raise ValidationError(
                f"No template with id {template}")
    else:
        t = template
    return RenderedTemplate(
        subject=t.subject_line,
        body=t.body,
        missing_fields=t.detected_placeholders,
    )


def record_use(template_id: int, *,
                   used_on: str | None = None) -> Template:
    t = get_template(template_id)
    if t is None:
        raise ValidationError(
            f"No template with id {template_id}")
    data = _to_dict(t)
    data["use_count"] = t.use_count + 1
    data["last_used_on"] = (used_on
                                  or _dt.date.today().isoformat())
    return update_template(template_id, data)


# ── Summary ──────────────────────────────────────────────

def summary() -> TemplatesSummary:
    rows = list_templates()
    out = TemplatesSummary(total=len(rows))
    if not rows:
        return out
    most_used = None
    most_used_count = 0
    for t in rows:
        if t.status == "Active":
            out.active += 1
        elif t.status == "Draft":
            out.drafts += 1
        elif t.status == "Archived":
            out.archived += 1
        elif t.status == "Retired":
            out.retired += 1
        out.total_uses += t.use_count
        if t.use_count > most_used_count:
            most_used_count = t.use_count
            most_used = t.name
        out.by_category[t.category] = (
            out.by_category.get(t.category, 0) + 1)
        out.by_recipient_type[t.recipient_type] = (
            out.by_recipient_type.get(t.recipient_type, 0) + 1)
        out.by_format[t.format] = (
            out.by_format.get(t.format, 0) + 1)
        out.by_status[t.status] = (
            out.by_status.get(t.status, 0) + 1)
    out.most_used_name = most_used
    out.most_used_count = most_used_count
    return out


__all__ = [
    "CATEGORIES", "DEFAULT_CATEGORY",
    "RECIPIENT_TYPES", "DEFAULT_RECIPIENT_TYPE",
    "STATUSES", "DEFAULT_STATUS",
    "FORMATS", "DEFAULT_FORMAT",
    "ValidationError",
    "Template", "RenderedTemplate", "TemplatesSummary",
    "init_db", "extract_placeholders",
    "create_template", "update_template", "delete_template",
    "get_template", "get_template_by_name", "list_templates",
    "activate", "archive", "retire", "set_status",
    "duplicate",
    "render", "preview", "record_use",
    "summary",
]
