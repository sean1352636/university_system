"""Letters home: a template library, mail merge, sending, print copies and
reply slips.

Kept from the old Letter Templates:

* Templates with name (unique), description, category, recipient type,
  format, subject line, body, letterhead, footer, signature, sender role,
  merge fields, attachments note, status (Draft, Active, Archived, Retired),
  author, use count, last used and notes.
* Activate, archive, retire, change status, duplicate, preview, render,
  record use, delete; the Active / Drafts / Archived / All lists with their
  filters; the summary.

New:

* **Merge fields** ``{pupil_name}``, ``{first_name}``, ``{last_name}``,
  ``{year}``, ``{form}``, ``{parent_name}``, ``{date}``, ``{school_name}``,
  ``{admission_no}``, ``{reply_by}`` and the template's own custom fields
  (listed in *merge fields*, filled in when sending). Old ``{{field}}``
  placeholders still work. An unknown field is refused before saving.
* **Mail merge** to chosen pupils, a form or a year group: one letter per
  pupil, e-mailed through the school outbox to contacts with parental
  responsibility (a parent of two gets one e-mail with both letters).
  :func:`preview` shows one pupil's letter first.
* **Families without e-mail**: :func:`print_copies` gives a print / text copy
  (with the tear-off reply slip) for the pupils nobody could be e-mailed for.
* **History** of letters sent per pupil and per mail merge.
* **Reply slips**: a yes/no question with a reply-by date; replies are
  recorded per pupil (by staff, or by the family through the portal with
  :func:`reply_for_family`), with a chase list of non-replies and a reminder
  e-mail.
* **Who.** :data:`LETTER_EDITORS` keep the template library and send to a
  form, a year group or several; any member of staff sends an active template
  to pupils they choose and drafts templates of their own. Every change is in
  ``letter_audit`` and the activity log (ids only).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import LETTER_EDITORS, STAFF_ROLES, Principal
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

logger = logging.getLogger(__name__)

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

CATEGORIES: tuple[str, ...] = (
    "Welcome / Induction", "Attendance", "Behaviour", "Achievement", "Awards",
    "Parents' Evening", "Trip / Visit", "Consent", "Bursary / Finance", "Disciplinary",
    "Reference", "Reminder", "Safeguarding", "Examinations", "Options", "Health",
    "End of Year", "Other")
DEFAULT_CATEGORY = "Other"
RECIPIENT_TYPES: tuple[str, ...] = (
    "Parent / Carer", "Student", "Both", "Staff", "External Agency", "Employer", "Other")
DEFAULT_RECIPIENT = "Parent / Carer"
STATUSES: tuple[str, ...] = ("Draft", "Active", "Archived", "Retired")
DEFAULT_STATUS = "Draft"
FORMATS: tuple[str, ...] = ("Letter", "Email", "SMS", "Both Letter & Email")
DEFAULT_FORMAT = "Both Letter & Email"
REPLIES: tuple[str, ...] = ("Yes", "No")
#: Merge fields every letter can use (field -> what fills it).
STANDARD_FIELDS: dict[str, str] = {
    "pupil_name": "The pupil's preferred first name and surname",
    "first_name": "The pupil's preferred or first name",
    "last_name": "The pupil's surname",
    "year": "The pupil's year group",
    "form": "The pupil's form",
    "parent_name": "The contact's name (or Parent/Carer)",
    "date": "Today's date",
    "school_name": "The school's name",
    "admission_no": "The pupil's admission number",
    "reply_by": "The reply-by date of a reply slip",
}
TEMPLATE = "letter"
TEMPLATE_REMINDER = "letter_reply_reminder"
SCHOOL_NAME_DEFAULT = "Secondary School"
MAX_BODY = 15000

_FIELD_RE = re.compile(r"\{\{?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}?\}")
_CUSTOM_RE = re.compile(r"^[a-z_][a-z0-9_]{0,39}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS letter_templates (
    template_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description     TEXT,
    category        TEXT NOT NULL DEFAULT 'Other',
    recipient_type  TEXT NOT NULL DEFAULT 'Parent / Carer',
    format          TEXT NOT NULL DEFAULT 'Both Letter & Email',
    subject_line    TEXT NOT NULL,
    body            TEXT NOT NULL,
    letterhead      TEXT,
    footer          TEXT,
    signature       TEXT,
    sender_role     TEXT,
    merge_fields    TEXT,
    attachments_ref TEXT,
    reply_slip      INTEGER NOT NULL DEFAULT 0 CHECK (reply_slip IN (0, 1)),
    reply_question  TEXT,
    status          TEXT NOT NULL DEFAULT 'Draft'
                    CHECK (status IN ('Draft', 'Active', 'Archived', 'Retired')),
    created_by      TEXT,
    last_used_on    TEXT,
    use_count       INTEGER NOT NULL DEFAULT 0,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by      TEXT,
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS letter_sends (
    send_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id    INTEGER REFERENCES letter_templates (template_id) ON DELETE SET NULL,
    template_name  TEXT NOT NULL,
    subject        TEXT NOT NULL,
    audience_kind  TEXT NOT NULL CHECK (audience_kind IN ('pupils', 'form', 'year')),
    audience_label TEXT NOT NULL,
    custom_values  TEXT,
    reply_question TEXT,
    reply_by       TEXT,
    message_id     INTEGER,
    letters        INTEGER NOT NULL DEFAULT 0,
    emails         INTEGER NOT NULL DEFAULT 0,
    sent_by        TEXT NOT NULL,
    sent_at        TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS letter_recipients (
    recipient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    send_id      INTEGER NOT NULL REFERENCES letter_sends (send_id) ON DELETE CASCADE,
    pupil_id     INTEGER NOT NULL REFERENCES pupils (pupil_id) ON DELETE CASCADE,
    parent_name  TEXT,
    subject      TEXT NOT NULL,
    body         TEXT NOT NULL,
    emails       INTEGER NOT NULL DEFAULT 0,
    printed_at   TEXT,
    reply        TEXT CHECK (reply IS NULL OR reply IN ('Yes', 'No')),
    reply_note   TEXT,
    reply_at     TEXT,
    reply_by_user TEXT,
    chase_count  INTEGER NOT NULL DEFAULT 0,
    chased_at    TEXT,
    UNIQUE (send_id, pupil_id)
);
CREATE INDEX IF NOT EXISTS ix_letter_recipients_pupil ON letter_recipients (pupil_id);
CREATE TABLE IF NOT EXISTS letter_audit (
    audit_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id  INTEGER,
    send_id      INTEGER,
    pupil_id     INTEGER,
    action       TEXT NOT NULL,
    detail       TEXT,
    actor        TEXT NOT NULL,
    at           TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("letters", _SCHEMA)


@dataclass(frozen=True)
class Template:
    template_id: int
    name: str
    description: str | None
    category: str
    recipient_type: str
    format: str
    subject_line: str
    body: str
    letterhead: str | None
    footer: str | None
    signature: str | None
    sender_role: str | None
    merge_fields: str | None
    attachments_ref: str | None
    reply_slip: bool
    reply_question: str | None
    status: str
    created_by: str | None
    last_used_on: str | None
    use_count: int
    notes: str | None
    created_at: str
    updated_by: str | None
    updated_at: str

    @property
    def custom_fields(self) -> list[str]:
        return [f.strip() for f in (self.merge_fields or "").split(",") if f.strip()]

    merge_field_list = custom_fields

    @property
    def detected_placeholders(self) -> list[str]:
        return extract_placeholders(f"{self.subject_line}\n{self.letterhead or ''}\n{self.body}"
                                    f"\n{self.signature or ''}\n{self.footer or ''}")


@dataclass(frozen=True)
class Send:
    send_id: int
    template_id: int | None
    template_name: str
    subject: str
    audience_kind: str
    audience_label: str
    custom_values: str | None
    reply_question: str | None
    reply_by: str | None
    message_id: int | None
    letters: int
    emails: int
    sent_by: str
    sent_at: str

    @property
    def has_reply_slip(self) -> bool:
        return bool(self.reply_question)


@dataclass(frozen=True)
class Recipient:
    recipient_id: int
    send_id: int
    pupil_id: int
    parent_name: str | None
    subject: str
    body: str
    emails: int
    printed_at: str | None
    reply: str | None
    reply_note: str | None
    reply_at: str | None
    reply_by_user: str | None
    chase_count: int
    chased_at: str | None
    pupil_name: str = ""
    admission_no: str = ""
    pupil_year: int = 0
    form_group: str | None = None
    sent_at: str = ""
    template_name: str = ""
    reply_question: str | None = None
    reply_by: str | None = None


@dataclass
class Rendered:
    """The old RenderedTemplate."""
    subject: str
    body: str
    missing: list[str] = field(default_factory=list)


def _template_row(r) -> Template:
    v = {k: r[k] for k in Template.__dataclass_fields__}
    v["reply_slip"] = bool(v["reply_slip"])
    return Template(**v)


def _send_row(r) -> Send:
    return Send(**{k: r[k] for k in Send.__dataclass_fields__})


_REC_SELECT = ("SELECT r.*, p.legal_last_name, p.legal_first_name, p.preferred_name, "
               "p.admission_no, p.year_group AS pupil_year, p.form_group, s.sent_at, "
               "s.template_name, s.reply_question, s.reply_by FROM letter_recipients r "
               "JOIN pupils p USING (pupil_id) JOIN letter_sends s USING (send_id)")
_REC_BASE = ("recipient_id", "send_id", "pupil_id", "parent_name", "subject", "body", "emails",
             "printed_at", "reply", "reply_note", "reply_at", "reply_by_user", "chase_count",
             "chased_at")


def _rec_row(r) -> Recipient:
    return Recipient(**{k: r[k] for k in _REC_BASE},
                     pupil_name=f"{r['legal_last_name']}, "
                                f"{r['preferred_name'] or r['legal_first_name']}",
                     admission_no=r["admission_no"], pupil_year=r["pupil_year"],
                     form_group=r["form_group"], sent_at=r["sent_at"],
                     template_name=r["template_name"], reply_question=r["reply_question"],
                     reply_by=r["reply_by"])


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in LETTER_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"letters.{action}", target=target, outcome="denied", principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can send letters.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the letters editors (school office) can do that.")


def can_edit_template(actor: Principal, t: Template) -> bool:
    """Editors change any template; staff change their own drafts."""
    return is_editor(actor) or (actor.role in STAFF_ROLES and t.status == "Draft" and
                                bool(actor.username) and
                                (t.created_by or "").lower() == actor.username.lower())


def _audit(conn, action: str, actor: Principal, *, template_id: int | None = None,
           send_id: int | None = None, pupil_id: int | None = None, **detail: Any) -> None:
    conn.execute("INSERT INTO letter_audit (template_id, send_id, pupil_id, action, detail, "
                 "actor) VALUES (?, ?, ?, ?, ?, ?)",
                 (template_id, send_id, pupil_id, action,
                  json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(*, template_id: int | None = None, send_id: int | None = None,
            pupil_id: int | None = None, limit: int = 300) -> list[dict[str, Any]]:
    sql, where, params = "SELECT * FROM letter_audit", [], []
    for col, val in (("template_id", template_id), ("send_id", send_id),
                     ("pupil_id", pupil_id)):
        if val is not None:
            where.append(f"{col} = ?")
            params.append(int(val))
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        return [{"at": r["at"], "template_id": r["template_id"], "send_id": r["send_id"],
                 "pupil_id": r["pupil_id"], "action": r["action"], "actor": r["actor"],
                 "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Merge fields ─────────────────────────────────────────────────────

def extract_placeholders(text: str | None) -> list[str]:
    """Distinct merge fields in order of first use."""
    seen: list[str] = []
    for m in _FIELD_RE.finditer(text or ""):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def school_name() -> str:
    """The name in School Settings (falls back to the old template default)."""
    try:
        from education_system.systems.secondary.modules.administration.domain import settings as ST
        name = ST.get_setting("school_name")
        if name and name != ST.get_spec("school_name").default:
            return str(name)
    except Exception:  # noqa: BLE001 - a name to print, not a gate
        logger.exception("School name setting could not be read")
    try:
        from education_system.systems.secondary.modules.communication.domain import email_templates
        return email_templates.load_template("exclusion_notice").defaults.get(
            "school_name") or SCHOOL_NAME_DEFAULT
    except Exception:  # noqa: BLE001 - a name to print, not a gate
        return SCHOOL_NAME_DEFAULT


def _fill(text: str, values: dict[str, str]) -> tuple[str, list[str]]:
    missing: list[str] = []

    def one(m: re.Match) -> str:
        k = m.group(1)
        if k in values:
            return values[k]
        if k not in missing:
            missing.append(k)
        return m.group(0)
    return _FIELD_RE.sub(one, text or ""), missing


def pupil_values(p: P.Pupil, *, parent_name: str | None = None,
                 reply_by: str | None = None, day: _dt.date | None = None) -> dict[str, str]:
    d = day or _today()
    return {"pupil_name": p.display_name, "first_name": p.preferred_name or p.legal_first_name,
            "last_name": p.legal_last_name, "year": str(p.year_group),
            "form": p.form_group or "", "parent_name": parent_name or "Parent/Carer",
            "date": f"{d.day} {d:%B %Y}", "school_name": school_name(),
            "admission_no": p.admission_no, "reply_by": reply_by or ""}


def _compose(t: Template) -> str:
    parts = [x for x in (t.letterhead, t.body, t.signature, t.footer) if x and x.strip()]
    return "\n\n".join(x.strip() for x in parts)


def render(template: Template | int, context: dict[str, Any], *, track_use: bool = False,
           actor: Principal | None = None) -> Rendered:
    """The old Render: fill the template's fields from *context*; fields with
    no value are left in place and listed in ``missing``."""
    t = template if isinstance(template, Template) else get_template(int(template))
    values = {k: "" if v is None else str(v) for k, v in context.items()}
    subject, m1 = _fill(t.subject_line, values)
    body, m2 = _fill(_compose(t), values)
    if track_use and actor is not None:
        record_use(t.template_id, actor=actor)
    return Rendered(" ".join(subject.split()), body, list(dict.fromkeys(m1 + m2)))


def preview(template: Template | int, pupil: Any = None, custom: dict[str, Any] | None = None,
            *, reply_by: str | None = None) -> Rendered:
    """The template as one pupil's family would get it (no pupil: the raw
    template, fields shown)."""
    t = template if isinstance(template, Template) else get_template(int(template))
    if pupil in (None, ""):
        return Rendered(t.subject_line, _compose(t), [])
    p = _pupil(pupil)
    if p is None:
        raise ValidationError([f"No pupil {pupil}"])
    names = _parent_names(p.pupil_id)
    ctx = {**pupil_values(p, parent_name=names, reply_by=reply_by),
           **{k: v for k, v in (custom or {}).items() if v not in (None, "")}}
    r = render(t, ctx)
    if t.reply_slip:
        r.body += "\n\n" + _slip_text(t.reply_question or "", reply_by, p)
    return r


# ── Cleaning ─────────────────────────────────────────────────────────

def _choice(value: Any, options: tuple[str, ...], label: str, problems: list[str],
            default: str | None) -> str | None:
    v = str(value or "").strip()
    if not v:
        return default
    hit = next((o for o in options if o.lower() == v.lower()), None)
    if hit is None:
        problems.append(f"{label} must be one of {', '.join(options)}")
        return default
    return hit


def _text(value: Any, limit: int) -> str | None:
    return (str(value or "").replace("\r\n", "\n").strip()[:limit]) or None


def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _pupil(ref: Any) -> P.Pupil | None:
    if ref in (None, ""):
        return None
    if isinstance(ref, P.Pupil):
        return ref
    if isinstance(ref, int) or str(ref).strip().isdigit():
        return P.get_pupil(int(ref))
    return P.find_by_reference(str(ref).strip())


TEMPLATE_FIELDS = ("name", "description", "category", "recipient_type", "format",
                   "subject_line", "body", "letterhead", "footer", "signature", "sender_role",
                   "merge_fields", "attachments_ref", "reply_slip", "reply_question", "status",
                   "notes")


def _clean_template(data: dict[str, Any], current: Template | None
                    ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in TEMPLATE_FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in TEMPLATE_FIELDS})
    out: dict[str, Any] = {}
    out["name"] = " ".join(str(merged.get("name") or "").split())[:120]
    if not out["name"]:
        problems.append("Name is required")
    out["description"] = _text(merged.get("description"), 500)
    out["category"] = _choice(merged.get("category"), CATEGORIES, "Category", problems,
                              DEFAULT_CATEGORY)
    out["recipient_type"] = _choice(merged.get("recipient_type"), RECIPIENT_TYPES,
                                    "Recipient", problems, DEFAULT_RECIPIENT)
    out["format"] = _choice(merged.get("format"), FORMATS, "Format", problems, DEFAULT_FORMAT)
    out["subject_line"] = " ".join(str(merged.get("subject_line") or "").split())[:200]
    if not out["subject_line"]:
        problems.append("Subject line is required")
    out["body"] = _text(merged.get("body"), MAX_BODY + 1) or ""
    if not out["body"]:
        problems.append("Body is required")
    elif len(out["body"]) > MAX_BODY:
        problems.append(f"Body must be {MAX_BODY} characters or fewer")
    for k, limit in (("letterhead", 1000), ("footer", 1000), ("signature", 500),
                     ("sender_role", 100), ("attachments_ref", 300), ("notes", 2000)):
        out[k] = _text(merged.get(k), limit)
    custom = [f.strip().strip("{}").strip() for f in
              re.split(r"[,;\s]+", str(merged.get("merge_fields") or "")) if f.strip()]
    bad = [f for f in custom if not _CUSTOM_RE.match(f)]
    if bad:
        problems.append("Custom fields are lower-case words with underscores: "
                        + ", ".join(bad))
    clash = [f for f in custom if f in STANDARD_FIELDS]
    if clash:
        problems.append("These are standard fields, not custom ones: " + ", ".join(clash))
    custom = [f for f in dict.fromkeys(custom) if f not in clash and f not in bad]
    used = extract_placeholders("\n".join(str(out.get(k) or "") for k in (
        "subject_line", "body", "letterhead", "footer", "signature")))
    unknown = [f for f in used if f not in STANDARD_FIELDS and f not in custom]
    if unknown:
        problems.append("Unknown merge field(s): " + ", ".join("{" + f + "}" for f in unknown)
                        + " - add them to the custom fields or use "
                        + ", ".join("{" + f + "}" for f in STANDARD_FIELDS))
    out["merge_fields"] = ", ".join(custom) or None
    rs = merged.get("reply_slip")
    out["reply_slip"] = rs if isinstance(rs, bool) else str(rs or "").strip().lower() in (
        "1", "true", "yes", "y", "on")
    out["reply_question"] = _text(merged.get("reply_question"), 300)
    if out["reply_slip"] and not out["reply_question"]:
        problems.append("A reply slip needs its yes/no question")
    out["status"] = _choice(merged.get("status"), STATUSES, "Status", problems, DEFAULT_STATUS)
    return out, problems


# ── Templates ────────────────────────────────────────────────────────

def get_template(template_id: int) -> Template:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM letter_templates WHERE template_id = ?",
                         (int(template_id),)).fetchone()
    if r is None:
        raise NotFound(f"No letter template #{template_id}")
    return _template_row(r)


def find_template(name: str) -> Template | None:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM letter_templates WHERE name = ?",
                         (" ".join(str(name or "").split()),)).fetchone()
    return _template_row(r) if r else None


TEMPLATE_SCOPES = ("active", "drafts", "archived", "all")


def list_templates(*, scope: str = "all", category: str | None = None,
                   recipient_type: str | None = None, format: str | None = None,
                   status: str | None = None, search: str | None = None) -> list[Template]:
    """The library (the old Active / Drafts / Archived / All tabs + filters)."""
    where, params = [], []
    if scope == "active":
        where.append("status = 'Active'")
    elif scope == "drafts":
        where.append("status = 'Draft'")
    elif scope == "archived":
        where.append("status IN ('Archived', 'Retired')")
    for col, val in (("category", category), ("recipient_type", recipient_type),
                     ("format", format), ("status", status)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    for term in (search or "").split():
        where.append("(name LIKE ? OR description LIKE ? OR subject_line LIKE ? OR body LIKE ?)")
        params += [f"%{term}%"] * 4
    sql = "SELECT * FROM letter_templates" + (" WHERE " + " AND ".join(where) if where else "") \
        + " ORDER BY category, name COLLATE NOCASE"
    with database.connect() as conn:
        return [_template_row(r) for r in conn.execute(sql, params)]


def create_template(data: dict[str, Any], *, actor: Principal) -> Template:
    """The old New template. Staff make drafts; only editors make one active."""
    _require_staff(actor, "template_create")
    c, problems = _clean_template(data, None)
    if c["status"] != "Draft" and not is_editor(actor):
        problems.append("Save it as a draft - the school office activates templates")
    if find_template(c["name"]):
        problems.append(f"A template called '{c['name']}' already exists")
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        tid = conn.execute(
            f"INSERT INTO letter_templates ({', '.join(TEMPLATE_FIELDS)}, created_by, "
            f"updated_by) VALUES ({', '.join('?' * len(TEMPLATE_FIELDS))}, ?, ?)",
            (*(int(c[k]) if k == "reply_slip" else c[k] for k in TEMPLATE_FIELDS),
             actor.username, actor.username)).lastrowid
        _audit(conn, "template_create", actor, template_id=tid)
    activity_log.record("letters.template_create", target=f"template:{tid}", principal=actor)
    return get_template(tid)


def update_template(template_id: int, changes: dict[str, Any], *, actor: Principal
                    ) -> Template:
    cur = get_template(template_id)
    if not can_edit_template(actor, cur):
        _deny(actor, "template_update", f"template:{cur.template_id}",
              "You can change your own draft templates; the school office changes the "
              "library.")
    c, problems = _clean_template(changes, cur)
    if c["status"] != cur.status and not is_editor(actor):
        problems.append("Only the school office changes a template's status")
    other = find_template(c["name"])
    if other and other.template_id != cur.template_id:
        problems.append(f"A template called '{c['name']}' already exists")
    if problems:
        raise ValidationError(problems)
    changed = [k for k in TEMPLATE_FIELDS if c[k] != getattr(cur, k)]
    if not changed:
        return cur
    with database.connect() as conn:
        conn.execute("UPDATE letter_templates SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE template_id = ?",
                     (*(int(c[k]) if k == "reply_slip" else c[k] for k in changed),
                      actor.username, cur.template_id))
        _audit(conn, "template_update", actor, template_id=cur.template_id, fields=changed)
    activity_log.record("letters.template_update", target=f"template:{cur.template_id}",
                        principal=actor, fields=",".join(changed))
    return get_template(cur.template_id)


def set_status(template_id: int, status: str, *, actor: Principal) -> Template:
    """The old Change status."""
    _require_editor(actor, "template_status", f"template:{template_id}")
    return update_template(template_id, {"status": status}, actor=actor)


def activate(template_id: int, *, actor: Principal) -> Template:
    return set_status(template_id, "Active", actor=actor)


def archive(template_id: int, *, actor: Principal) -> Template:
    return set_status(template_id, "Archived", actor=actor)


def retire(template_id: int, *, actor: Principal) -> Template:
    return set_status(template_id, "Retired", actor=actor)


def duplicate(template_id: int, *, actor: Principal, name: str | None = None) -> Template:
    """A draft copy (a new name)."""
    t = get_template(template_id)
    base = name or f"{t.name} (copy)"
    new, n = base, 2
    while find_template(new):
        new, n = f"{base} {n}", n + 1
    return create_template({**{k: getattr(t, k) for k in TEMPLATE_FIELDS}, "name": new,
                            "status": "Draft"}, actor=actor)


def record_use(template_id: int, *, actor: Principal, count: int = 1) -> Template:
    """The old Record use (sending records it too)."""
    _require_staff(actor, "record_use")
    t = get_template(template_id)
    with database.connect() as conn:
        conn.execute("UPDATE letter_templates SET use_count = use_count + ?, last_used_on = ? "
                     "WHERE template_id = ?", (int(count), _today().isoformat(), t.template_id))
    return get_template(t.template_id)


def delete_template(template_id: int, *, actor: Principal) -> bool:
    """The old Delete. Letters already sent keep their copy."""
    t = get_template(template_id)
    own_draft = can_edit_template(actor, t) and t.status == "Draft"
    if not (is_editor(actor) or own_draft):
        _deny(actor, "template_delete", f"template:{t.template_id}",
              "Only the school office deletes templates from the library.")
    with database.connect() as conn:
        conn.execute("DELETE FROM letter_templates WHERE template_id = ?", (t.template_id,))
        _audit(conn, "template_delete", actor, template_id=t.template_id)
    activity_log.record("letters.template_delete", target=f"template:{t.template_id}",
                        principal=actor)
    return True


# ── Sending ──────────────────────────────────────────────────────────

def _contacts(pupil_ids: list[int]) -> dict[int, list[Any]]:
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    return {pid: [c for c in cs if c.email and c.parental_responsibility]
            for pid, cs in C.emailable_for_pupils(pupil_ids).items()}


def _parent_names(pupil_id: int) -> str:
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    names = [c.full_name for c in C.list_for_pupil(pupil_id) if c.parental_responsibility]
    return " and ".join(names[:2]) or "Parent/Carer"


def _slip_text(question: str, reply_by: str | None, p: P.Pupil) -> str:
    return "\n".join([
        "- " * 30, "REPLY SLIP" + (f" - please reply by {reply_by}" if reply_by else ""),
        f"Pupil: {p.display_name} ({p.form_group or f'Year {p.year_group}'})",
        f"{question}", "[ ] Yes      [ ] No", "",
        "Signed (parent/carer): ______________________   Date: __________"])


def _email_slip(question: str, reply_by: str | None) -> str:
    return (f"Reply needed: {question}\nPlease reply Yes or No"
            + (f" by {reply_by}" if reply_by else "")
            + " - through the parent portal, by replying to this e-mail, or on the paper slip.")


def parse_pupil_refs(text: str) -> list[str]:
    """Admission numbers / ids typed with commas, semicolons, spaces or lines."""
    return [x for x in re.split(r"[,;\s]+", text or "") if x]


def audience_pupils(*, pupil_ids: list[Any] | None = None, form: str | None = None,
                    year: int | str | None = None) -> tuple[str, str, list[P.Pupil]]:
    """(kind, label, pupils) for a mail merge."""
    if pupil_ids:
        found = [_pupil(x) for x in dict.fromkeys(pupil_ids)]
        missing = [str(x) for x, p in zip(dict.fromkeys(pupil_ids), found) if p is None]
        if missing:
            raise ValidationError(["No pupil " + ", ".join(missing)])
        pupils = [p for p in found if p is not None and p.roll_status == "on_roll"]
        return "pupils", f"{len(pupils)} chosen pupil(s)", pupils
    if form:
        return "form", f"Form {form.strip().upper()}", P.list_pupils(form_group=form.strip())
    if year not in (None, ""):
        y = int(str(year).strip())
        if y not in P.YEAR_GROUPS:
            raise ValidationError(["Year group must be 7 to 11"])
        return "year", f"Year {y}", P.list_pupils(year_group=y)
    raise ValidationError(["Choose the pupils, a form or a year group"])


def check_send(template_id: int, *, actor: Principal, custom: dict[str, Any] | None = None,
               reply_by: str | None = None, **audience: Any) -> dict[str, Any]:
    """What a send would do, without saving: {'pupils', 'with_email',
    'no_email', 'emails'}; raises on the problems."""
    t, kind, label, pupils, values, rb = _prepare(template_id, actor, custom, reply_by,
                                                  audience)
    contacts = _contacts([p.pupil_id for p in pupils])
    no_email = [p for p in pupils if not contacts.get(p.pupil_id)]
    addresses = {c.email.lower() for cs in contacts.values() for c in cs}
    return {"template": t, "label": label, "pupils": pupils, "no_email": no_email,
            "with_email": len(pupils) - len(no_email), "emails": len(addresses)}


def _prepare(template_id: int, actor: Principal, custom: dict[str, Any] | None,
             reply_by: str | None, audience: dict[str, Any]):
    _require_staff(actor, "send")
    t = get_template(template_id)
    kind, label, pupils = audience_pupils(**audience)
    if kind != "pupils" and not is_editor(actor):
        _deny(actor, "send", f"template:{t.template_id}",
              "You can send letters to pupils you choose; the school office sends to a "
              "form or year group.")
    problems: list[str] = []
    if t.status != "Active":
        problems.append(f"The template is {t.status.lower()} - only active templates are sent")
    if not pupils:
        problems.append("Nobody on roll to send to")
    values = {k: str(v).strip() for k, v in (custom or {}).items()
              if k in t.custom_fields and str(v or "").strip()}
    missing = [f for f in t.custom_fields if f not in values and f in t.detected_placeholders]
    if missing:
        problems.append("Fill in: " + ", ".join(missing))
    rb = _date(reply_by, "Reply by", problems)
    if rb and rb < _today().isoformat():
        problems.append("The reply-by date has passed")
    if "reply_by" in t.detected_placeholders and t.reply_slip and not rb:
        problems.append("Give the reply-by date")
    if problems:
        raise ValidationError(problems)
    return t, kind, label, pupils, values, rb


def send(template_id: int, *, actor: Principal, custom: dict[str, Any] | None = None,
         reply_by: str | None = None, pupil_ids: list[Any] | None = None,
         form: str | None = None, year: int | str | None = None) -> dict[str, Any]:
    """Mail-merge an active template to the pupils' contacts with parental
    responsibility. Returns {'send_id', 'message_id', 'letters', 'emails',
    'no_email'} (pupils who need a printed copy)."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    t, kind, label, pupils, values, rb = _prepare(
        template_id, actor, custom, reply_by,
        {"pupil_ids": pupil_ids, "form": form, "year": year})
    contacts = _contacts([p.pupil_id for p in pupils])
    wrapper = email_templates.load_template(TEMPLATE)
    question = t.reply_question if t.reply_slip else None
    rows: list[tuple[P.Pupil, str, str, str, int]] = []
    by_addr: dict[str, dict[str, Any]] = {}
    no_email: list[P.Pupil] = []
    for p in pupils:
        names = _parent_names(p.pupil_id)
        r = render(t, {**pupil_values(p, parent_name=names, reply_by=rb), **values})
        found = contacts.get(p.pupil_id, [])
        body = r.body + ("\n\n" + _slip_text(question, rb, p) if question else "")
        rows.append((p, names, r.subject, body, len(found)))
        if not found:
            no_email.append(p)
        for c in found:
            mine = render(t, {**pupil_values(p, parent_name=c.full_name, reply_by=rb),
                              **values})
            x = by_addr.setdefault(c.email.lower(), {"name": c.full_name, "subject": mine.subject,
                                                     "bodies": []})
            x["bodies"].append(mine.body)
    letters = []
    for addr, x in by_addr.items():
        subject, body = wrapper.render({
            "subject": x["subject"],
            "body": ("\n\n" + "-" * 40 + "\n\n").join(x["bodies"]),
            "reply_slip": _email_slip(question, rb) if question else ""})
        letters.append((addr, x["name"], subject, body))
    mid = E.save_prepared("letter", f"Letter: {label}"[:200], t.subject_line,
                          "(mail merge, one letter per pupil)", letters, actor=actor) \
        if letters else None
    with database.connect() as conn:
        sid = conn.execute(
            "INSERT INTO letter_sends (template_id, template_name, subject, audience_kind, "
            "audience_label, custom_values, reply_question, reply_by, message_id, letters, "
            "emails, sent_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (t.template_id, t.name, t.subject_line, kind, label,
             json.dumps(values) if values else None, question, rb, mid, len(rows),
             len(letters), actor.username)).lastrowid
        conn.executemany(
            "INSERT INTO letter_recipients (send_id, pupil_id, parent_name, subject, body, "
            "emails) VALUES (?, ?, ?, ?, ?, ?)",
            [(sid, p.pupil_id, names, subj, body, n) for p, names, subj, body, n in rows])
        conn.execute("UPDATE letter_templates SET use_count = use_count + ?, last_used_on = ? "
                     "WHERE template_id = ?", (len(rows), _today().isoformat(), t.template_id))
        _audit(conn, "send", actor, template_id=t.template_id, send_id=sid, kind=kind,
               letters=len(rows), emails=len(letters))
    activity_log.record("letters.send", target=f"send:{sid}", principal=actor,
                        template=t.template_id, letters=len(rows), emails=len(letters))
    return {"send_id": sid, "message_id": mid, "letters": len(rows), "emails": len(letters),
            "no_email": no_email}


# ── Sent letters ─────────────────────────────────────────────────────

def get_send(send_id: int) -> Send:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM letter_sends WHERE send_id = ?",
                         (int(send_id),)).fetchone()
    if r is None:
        raise NotFound(f"No mail merge #{send_id}")
    return _send_row(r)


def list_sends(*, template_id: int | None = None, sent_by: str | None = None,
               replies_only: bool = False, limit: int = 500) -> list[Send]:
    where, params = [], []
    if template_id:
        where.append("template_id = ?")
        params.append(int(template_id))
    if sent_by:
        where.append("lower(sent_by) = lower(?)")
        params.append(sent_by)
    if replies_only:
        where.append("reply_question IS NOT NULL")
    sql = "SELECT * FROM letter_sends" + (" WHERE " + " AND ".join(where) if where else "") \
        + " ORDER BY send_id DESC LIMIT ?"
    with database.connect() as conn:
        return [_send_row(r) for r in conn.execute(sql, (*params, int(limit)))]


def recipients(send_id: int, *, no_email_only: bool = False,
               no_reply_only: bool = False) -> list[Recipient]:
    sql = _REC_SELECT + " WHERE r.send_id = ?"
    if no_email_only:
        sql += " AND r.emails = 0"
    if no_reply_only:
        sql += " AND r.reply IS NULL"
    with database.connect() as conn:
        return [_rec_row(r) for r in conn.execute(
            sql + " ORDER BY p.form_group, p.legal_last_name COLLATE NOCASE", (int(send_id),))]


def get_recipient(recipient_id: int) -> Recipient:
    with database.connect() as conn:
        r = conn.execute(_REC_SELECT + " WHERE r.recipient_id = ?",
                         (int(recipient_id),)).fetchone()
    if r is None:
        raise NotFound(f"No letter #{recipient_id}")
    return _rec_row(r)


def for_pupil(pupil_id: int) -> list[Recipient]:
    """Every letter sent home about a pupil, newest first."""
    with database.connect() as conn:
        return [_rec_row(r) for r in conn.execute(
            _REC_SELECT + " WHERE r.pupil_id = ? ORDER BY s.sent_at DESC, r.recipient_id DESC",
            (int(pupil_id),))]


def print_copies(send_id: int, *, actor: Principal, only_no_email: bool = True,
                 mark_printed: bool = True) -> str:
    """The letters as text to print (form feed between letters), with the
    tear-off reply slip - for families without e-mail by default."""
    _require_staff(actor, "print")
    rows = recipients(send_id, no_email_only=only_no_email)
    text = "\f".join(f"{r.subject}\n\n{r.body}\n" for r in rows)
    if rows and mark_printed:
        now = _dt.datetime.now().isoformat(timespec="seconds")
        with database.connect() as conn:
            conn.executemany("UPDATE letter_recipients SET printed_at = ? WHERE "
                             "recipient_id = ?", [(now, r.recipient_id) for r in rows])
            _audit(conn, "print", actor, send_id=int(send_id), letters=len(rows))
        activity_log.record("letters.print", target=f"send:{send_id}", principal=actor,
                            letters=len(rows))
    return text


def export_text(send_id: int, path: str | Path, *, actor: Principal,
                only_no_email: bool = True) -> int:
    text = print_copies(send_id, actor=actor, only_no_email=only_no_email)
    Path(path).write_text(text, encoding="utf-8")
    return len(recipients(send_id, no_email_only=only_no_email))


# ── Reply slips ──────────────────────────────────────────────────────

def _reply(value: Any) -> str:
    v = str(value or "").strip().lower()
    if v in ("y", "yes", "1", "true"):
        return "Yes"
    if v in ("n", "no", "0", "false"):
        return "No"
    raise ValidationError(["Reply must be Yes or No"])


def record_reply(recipient_id: int, reply: Any, *, actor: Principal,
                 note: str | None = None) -> Recipient:
    """Staff record a returned slip (or a phone / e-mail reply)."""
    _require_staff(actor, "reply")
    return _save_reply(get_recipient(recipient_id), _reply(reply), note, actor)


def _save_reply(r: Recipient, reply: str, note: str | None, actor: Principal) -> Recipient:
    if not r.reply_question:
        raise ValidationError(["That letter has no reply slip"])
    with database.connect() as conn:
        conn.execute("UPDATE letter_recipients SET reply = ?, reply_note = ?, reply_at = "
                     "datetime('now'), reply_by_user = ? WHERE recipient_id = ?",
                     (reply, _text(note, 500), actor.username, r.recipient_id))
        _audit(conn, "reply", actor, send_id=r.send_id, pupil_id=r.pupil_id, reply=reply)
    activity_log.record("letters.reply", target=r.admission_no, principal=actor,
                        send=r.send_id)
    return get_recipient(r.recipient_id)


def clear_reply(recipient_id: int, *, actor: Principal) -> Recipient:
    _require_staff(actor, "reply")
    r = get_recipient(recipient_id)
    with database.connect() as conn:
        conn.execute("UPDATE letter_recipients SET reply = NULL, reply_note = NULL, reply_at = "
                     "NULL, reply_by_user = NULL WHERE recipient_id = ?", (r.recipient_id,))
        _audit(conn, "reply_clear", actor, send_id=r.send_id, pupil_id=r.pupil_id)
    return get_recipient(r.recipient_id)


def for_family(principal: Principal, pupil_id: int) -> list[Recipient]:
    """What the portal shows: letters about the family's child, with any
    reply slip still to answer."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    PA.require_pupil(principal, int(pupil_id), "parent")
    return for_pupil(int(pupil_id))


def reply_for_family(principal: Principal, recipient_id: int, reply: Any,
                     note: str | None = None) -> Recipient:
    """A parent answers a reply slip through the portal (before the reply-by
    date has passed)."""
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    r = get_recipient(recipient_id)
    PA.require_pupil(principal, r.pupil_id, "parent")
    if r.reply_by and r.reply_by < _today().isoformat():
        raise ValidationError(["The reply date has passed - please contact the school"])
    return _save_reply(r, _reply(reply), note, principal)


def chase_list(send_id: int | None = None) -> list[Recipient]:
    """Letters with a reply slip and no reply yet (one mail merge, or all)."""
    if send_id is not None:
        return recipients(send_id, no_reply_only=True) if get_send(send_id).reply_question \
            else []
    with database.connect() as conn:
        return [_rec_row(r) for r in conn.execute(
            _REC_SELECT + " WHERE s.reply_question IS NOT NULL AND r.reply IS NULL "
            "ORDER BY COALESCE(s.reply_by, '9999'), s.send_id, p.legal_last_name")]


def reply_summary(send_id: int) -> dict[str, Any]:
    rows = recipients(send_id)
    c = Counter(r.reply or "No reply" for r in rows)
    return {"letters": len(rows), "yes": c.get("Yes", 0), "no": c.get("No", 0),
            "no_reply": c.get("No reply", 0),
            "rate": round(100 * (len(rows) - c.get("No reply", 0)) / len(rows)) if rows else 0}


def chase(send_id: int, *, actor: Principal) -> dict[str, Any]:
    """E-mail a reminder to the families who haven't replied. Returns
    {'message_id', 'emails', 'no_email'}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    s = get_send(send_id)
    if not (is_editor(actor) or (actor.username or "").lower() == s.sent_by.lower()):
        _deny(actor, "chase", f"send:{s.send_id}",
              "The sender or the school office chases replies.")
    rows = chase_list(s.send_id)
    if not rows:
        raise ValidationError(["Everyone has replied" if s.reply_question else
                               "That letter has no reply slip"])
    contacts = _contacts([r.pupil_id for r in rows])
    template = email_templates.load_template(TEMPLATE_REMINDER)
    seen: set[str] = set()
    letters, no_email, chased = [], [], []
    for r in rows:
        found = contacts.get(r.pupil_id, [])
        if not found:
            no_email.append(r)
            continue
        chased.append(r.recipient_id)
        p = P.get_pupil(r.pupil_id)
        for c in found:
            addr = c.email.lower()
            if addr in seen:
                continue
            seen.add(addr)
            subject, body = template.render({
                "recipient_name": c.full_name, "subject": r.subject,
                "pupil_name": p.display_name if p else r.pupil_name,
                "question": s.reply_question, "body": r.body,
                "reply_by": f"by {s.reply_by}" if s.reply_by else "as soon as possible",
                "school_name": school_name()})
            letters.append((addr, c.full_name, subject, body))
    mid = E.save_prepared("letter_reminder", f"Reply reminder: {s.template_name}"[:200],
                          f"Reminder: {s.subject}", "(one reminder per contact)", letters,
                          actor=actor) if letters else None
    with database.connect() as conn:
        conn.executemany("UPDATE letter_recipients SET chase_count = chase_count + 1, "
                         "chased_at = datetime('now') WHERE recipient_id = ?",
                         [(i,) for i in chased])
        _audit(conn, "chase", actor, send_id=s.send_id, emails=len(letters))
    activity_log.record("letters.chase", target=f"send:{s.send_id}", principal=actor,
                        emails=len(letters))
    return {"message_id": mid, "emails": len(letters), "no_email": no_email}


# ── Summary & export ─────────────────────────────────────────────────

@dataclass
class LettersSummary:
    total: int = 0
    active: int = 0
    drafts: int = 0
    archived: int = 0
    retired: int = 0
    total_uses: int = 0
    most_used: list[tuple[str, int]] = field(default_factory=list)
    with_reply_slip: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_recipient: dict[str, int] = field(default_factory=dict)
    by_format: dict[str, int] = field(default_factory=dict)
    sends: int = 0
    letters_sent: int = 0
    awaiting_replies: int = 0


def summary() -> LettersSummary:
    rows = list_templates()
    c = Counter(t.status for t in rows)
    sends = list_sends(limit=100000)
    return LettersSummary(
        total=len(rows), active=c.get("Active", 0), drafts=c.get("Draft", 0),
        archived=c.get("Archived", 0), retired=c.get("Retired", 0),
        total_uses=sum(t.use_count for t in rows),
        most_used=[(t.name, t.use_count) for t in sorted(rows, key=lambda t: -t.use_count)
                   if t.use_count][:5],
        with_reply_slip=sum(1 for t in rows if t.reply_slip),
        by_category=dict(Counter(t.category for t in rows)),
        by_recipient=dict(Counter(t.recipient_type for t in rows)),
        by_format=dict(Counter(t.format for t in rows)), sends=len(sends),
        letters_sent=sum(s.letters for s in sends), awaiting_replies=len(chase_list()))


def export_csv(send_id: int, path: str | Path, *, actor: Principal) -> int:
    """One mail merge's letters and replies as CSV."""
    _require_staff(actor, "export")
    rows = recipients(send_id)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["letter_id", "admission_no", "pupil", "year", "form", "parent", "emails",
                    "printed", "reply", "reply_note", "reply_at", "chased"])
        for r in rows:
            w.writerow([r.recipient_id, _safe(r.admission_no), _safe(r.pupil_name),
                        r.pupil_year, _safe(r.form_group), _safe(r.parent_name), r.emails,
                        (r.printed_at or "")[:10], r.reply or "", _safe(r.reply_note),
                        (r.reply_at or "")[:10], r.chase_count])
    activity_log.record("letters.export", principal=actor, send=int(send_id), rows=len(rows))
    return len(rows)
