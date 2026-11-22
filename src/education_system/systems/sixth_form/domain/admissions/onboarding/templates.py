"""Onboarding templates — stored in the onboarding database, editable and
versioned.

A template is a named list of tasks. Each task has a rule key (kept when
the task is renamed, so its evidence rule still applies), a category,
whether it is required, a due-day offset from the learner's start date,
an owner role (the queue it lands in) and a sensitive flag.

* Every save writes a **new version** (the old ones are kept, with who
  saved them, when and what changed); a checklist records which template
  version(s) it was made from (``onboarding_checklist_templates``).
* ``kind`` is ``base`` (a checklist is opened from one) or ``addon``
  (added on top of a base for a learner it applies to — SEND / EHCP,
  looked-after / care leaver).
* When the template table is empty it is filled with the built-in
  defaults: the product's existing templates (``onboarding.TEMPLATES``)
  plus the learner-type templates below. Nothing else is seeded.

Writes need ``admissions`` or ``students.manage`` (as the rest of
onboarding).
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.admissions.onboarding import (
    onboarding as ob,
)

ValidationError = ob.ValidationError

KINDS: tuple[str, ...] = ("base", "addon")

#: Learner types a template can be for (``choose_template`` picks by them).
YEAR12 = "Year 12 new starter"
YEAR13_TRANSFER = "Year 13 transfer-in"
MID_YEAR = "Mid-year joiner"
INTERNATIONAL = "International"
SEND = "SEND / EHCP"
CARE = "Looked-after / care leaver"
YEAR13_RETURN = "Year 13 return"
LEARNER_TYPES: tuple[str, ...] = (YEAR12, YEAR13_TRANSFER, MID_YEAR,
                                  INTERNATIONAL, SEND, CARE, YEAR13_RETURN)

#: Who a task belongs to (the role queues of :mod:`workflow`).
OWNER_ROLES: tuple[str, ...] = ("Admissions", "IT", "Pastoral", "Tutor",
                                "Finance", "Exams", "Library", "SEND",
                                "Safeguarding")

#: Defaults for a task that names no owner / offset (built-ins only).
CATEGORY_OWNER: dict[str, str] = {
    "Enrolment Paperwork": "Admissions", "Account & IT": "IT",
    "Equipment": "Admissions", "Health & Safety": "Pastoral",
    "Wellbeing & Pastoral": "Tutor", "Academic": "Tutor",
    "Library & Resources": "Library", "Finance": "Finance",
    "Other": "Admissions",
}
CATEGORY_OFFSET: dict[str, int] = {
    "Enrolment Paperwork": 7, "Account & IT": 3, "Equipment": 5,
    "Health & Safety": 5, "Wellbeing & Pastoral": 10, "Academic": 14,
    "Library & Resources": 10, "Finance": 21, "Other": 14,
}
#: Built-in per-task overrides: key -> (owner role, offset days).
_KEY_DEFAULTS: dict[str, tuple[str, int]] = {
    "Photocopy of ID / passport": ("Admissions", 0),
    "Passport / visa scanned": ("Admissions", 0),
    "UKVI right-to-study check": ("Admissions", 0),
    "Safeguarding briefing": ("Safeguarding", 5),
    "Safeguarding catch-up": ("Safeguarding", 5),
    "Course textbooks issued": ("Library", 10),
}

MIN_OFFSET, MAX_OFFSET = -90, 365

#: The UKVI check every international template must keep, required.
UKVI_KEY = "UKVI right-to-study check"
BURSARY_KEY = "Bursary applied for"
YEAR13_RETURN_TEMPLATE = "Year 13 return"
SEND_TEMPLATE = "SEND / EHCP"
CARE_TEMPLATE = "Looked-after / care leaver"
YEAR13_TRANSFER_TEMPLATE = "Year 13 transfer-in"
INTERNATIONAL_TEMPLATE = "International student"
MID_YEAR_TEMPLATE = "Mid-year transfer"
EHCP_REVIEW_KEY = "EHCP: review post-16 provision with the local authority"
PEP_KEY = "Looked-after: virtual school / PEP contact"

# (task, category, required[, owner, offset]) — the learner-type built-ins.
_T = tuple
_BUILT_IN_EXTRA: dict[str, tuple[str, str, str, list[_T]]] = {
    YEAR13_TRANSFER_TEMPLATE: (YEAR13_TRANSFER, "base",
        "Joining in Year 13 from another provider to finish a course", [
        ("Transfer paperwork received", "Enrolment Paperwork", True),
        ("Photocopy of ID / passport", "Enrolment Paperwork", True),
        ("Previous provider's records and Year 12 reports received",
         "Academic", True),
        ("Subjects reconciled with course (same specifications)",
         "Academic", True),
        ("Coursework / NEA progress confirmed with previous provider",
         "Academic", True, "Exams", 14),
        ("Exam entries transferred (board, centre, components)",
         "Academic", True, "Exams", 21),
        ("Medical / GP consent form", "Health & Safety", True),
        ("Photo consent", "Enrolment Paperwork", True),
        ("Account & email account created", "Account & IT", True),
        ("ID card issued", "Equipment", True),
        ("Safeguarding catch-up", "Health & Safety", True),
        ("Form tutor introduction", "Wellbeing & Pastoral", True),
        ("UCAS / next steps meeting booked", "Academic", True, "Tutor", 21),
        ("Library account activated", "Library & Resources", True),
        ("Bursary reviewed", "Finance", False),
    ]),
    SEND_TEMPLATE: (SEND, "addon",
        "Added for a learner on the SEND register or with an EHCP", [
        ("SEND: support plan agreed with the SENCo", "Wellbeing & Pastoral",
         True, "SEND", 14),
        (EHCP_REVIEW_KEY, "Wellbeing & Pastoral", True, "SEND", 28),
        ("Access arrangements assessed (exams)", "Academic", True,
         "Exams", 28),
        ("Teaching staff briefed on support strategies", "Academic", False,
         "SEND", 14),
    ]),
    CARE_TEMPLATE: (CARE, "addon",
        "Added for a looked-after child or care leaver (sensitive tasks)", [
        (PEP_KEY, "Wellbeing & Pastoral", True, "Pastoral", 10),
        ("Care leaver: support plan and bursary", "Finance", True,
         "Finance", 14),
        ("Looked-after: designated teacher introduction",
         "Wellbeing & Pastoral", True, "Pastoral", 5),
    ]),
    YEAR13_RETURN_TEMPLATE: (YEAR13_RETURN, "base",
        "Short re-onboarding for a learner returning for Year 13", [
        ("Contact and emergency details re-checked", "Enrolment Paperwork",
         True, "Admissions", 7),
        ("Medical information re-checked", "Health & Safety", True,
         "Pastoral", 10),
        ("Year 13 timetable confirmed", "Academic", True, "Tutor", 7),
        ("Learner agreement signed for Year 13", "Enrolment Paperwork",
         True, "Admissions", 7),
        ("Bursary applied for", "Finance", False, "Finance", 21),
        ("UCAS / next steps meeting booked", "Academic", False, "Tutor", 21),
    ]),
}
#: Learner type + kind for the product's existing templates.
_EXISTING_TYPES: dict[str, tuple[str | None, str, str]] = {
    "Standard new starter": (YEAR12, "base", "Year 12 new starter"),
    "Mid-year transfer": (MID_YEAR, "base",
                          "Joining after the start of the year"),
    "International student": (INTERNATIONAL, "base",
                              "Learner who needs a visa to study"),
    "Empty (no items)": (None, "base", "No tasks — add them by hand"),
}
#: Tasks the international built-in gains (visa / UKVI / BRP / CAS).
_INTERNATIONAL_EXTRA: list[_T] = [
    ("CAS (Confirmation of Acceptance for Studies) issued",
     "Enrolment Paperwork", True, "Admissions", 0),
    ("BRP / eVisa status checked", "Enrolment Paperwork", True,
     "Admissions", 0),
    ("Visa conditions explained to the learner", "Wellbeing & Pastoral",
     True, "Admissions", 7),
    ("UKVI attendance monitoring set up", "Academic", True, "Admissions", 7),
]


@dataclass
class TemplateItem:
    key: str
    task: str
    category: str
    required: bool = True
    due_offset_days: int = 14
    owner_role: str | None = None
    sensitive: bool = False
    position: int = 0


@dataclass
class Template:
    template_id: int
    name: str
    learner_type: str | None
    kind: str
    description: str | None
    active: bool
    version: int
    updated_at: str | None
    updated_by: str | None
    items: list[TemplateItem] = field(default_factory=list)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS onboarding_templates (
    template_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL UNIQUE,
    learner_type    TEXT,
    kind            TEXT NOT NULL DEFAULT 'base',
    description     TEXT,
    active          INTEGER NOT NULL DEFAULT 1,
    current_version INTEGER NOT NULL DEFAULT 1,
    built_in        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now')),
    updated_by      TEXT
);
CREATE TABLE IF NOT EXISTS onboarding_template_versions (
    version_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    template_id  INTEGER NOT NULL,
    version      INTEGER NOT NULL,
    learner_type TEXT,
    kind         TEXT NOT NULL,
    description  TEXT,
    saved_at     TEXT DEFAULT (datetime('now')),
    saved_by     TEXT,
    note         TEXT,
    changes      TEXT,
    UNIQUE (template_id, version),
    FOREIGN KEY (template_id) REFERENCES onboarding_templates(template_id)
);
CREATE TABLE IF NOT EXISTS onboarding_template_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id      INTEGER NOT NULL,
    position        INTEGER NOT NULL DEFAULT 0,
    item_key        TEXT NOT NULL,
    task_name       TEXT NOT NULL,
    category        TEXT NOT NULL,
    required        INTEGER NOT NULL DEFAULT 1,
    due_offset_days INTEGER NOT NULL DEFAULT 14,
    owner_role      TEXT,
    sensitive       INTEGER NOT NULL DEFAULT 0,
    UNIQUE (version_id, item_key),
    FOREIGN KEY (version_id) REFERENCES onboarding_template_versions(version_id)
);
CREATE TABLE IF NOT EXISTS onboarding_checklist_templates (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    checklist_id  INTEGER NOT NULL,
    template_name TEXT NOT NULL,
    version       INTEGER NOT NULL,
    applied_at    TEXT DEFAULT (datetime('now')),
    applied_by    TEXT,
    FOREIGN KEY (checklist_id) REFERENCES onboarding_checklists(checklist_id)
);
CREATE INDEX IF NOT EXISTS idx_ob_tpl_ver ON onboarding_template_versions(template_id);
CREATE INDEX IF NOT EXISTS idx_ob_tpl_items ON onboarding_template_items(version_id);
CREATE INDEX IF NOT EXISTS idx_ob_chk_tpl ON onboarding_checklist_templates(checklist_id);
"""

#: DB paths whose schema is ready (keyed by path so a redirected DB is
#: set up again).
_READY_PATHS: set[str] = set()


def _built_in_item(t: _T, pos: int) -> TemplateItem:
    task, cat, req = t[0], t[1], t[2]
    owner, offset = _KEY_DEFAULTS.get(
        task, (CATEGORY_OWNER.get(cat, "Admissions"),
               CATEGORY_OFFSET.get(cat, 14)))
    if len(t) > 3:
        owner, offset = t[3], t[4]
    return TemplateItem(key=task, task=task, category=cat, required=req,
                        due_offset_days=offset, owner_role=owner,
                        sensitive=ob._is_sensitive_key(task), position=pos)


def built_in_defaults() -> list[tuple[str, str | None, str, str, list[TemplateItem]]]:
    """(name, learner type, kind, description, items) for every built-in."""
    out = []
    for name, rows in ob.TEMPLATES.items():
        ltype, kind, desc = _EXISTING_TYPES.get(name, (None, "base", None))
        rows = list(rows) + (_INTERNATIONAL_EXTRA
                             if name == INTERNATIONAL_TEMPLATE else [])
        out.append((name, ltype, kind, desc,
                    [_built_in_item(t, i) for i, t in enumerate(rows)]))
    for name, (ltype, kind, desc, rows) in _BUILT_IN_EXTRA.items():
        out.append((name, ltype, kind, desc,
                    [_built_in_item(t, i) for i, t in enumerate(rows)]))
    return out


def init_db() -> None:
    ob.init_db()
    key = str(ob.DB_PATH)
    if key in _READY_PATHS:
        return
    with ob._connect() as conn:
        conn.executescript(_SCHEMA)
        if conn.execute("SELECT COUNT(*) FROM onboarding_templates"
                        ).fetchone()[0] == 0:
            for name, ltype, kind, desc, items in built_in_defaults():
                _write_version(conn, None, name=name, learner_type=ltype,
                               kind=kind, description=desc, items=items,
                               note="Built-in default", changes="created",
                               built_in=True, who="system")
        conn.commit()
    _READY_PATHS.add(key)


# ── Reading ───────────────────────────────────────────────────────

def _items_for_version(conn: Any, version_id: int
                       ) -> list[TemplateItem]:
    return [TemplateItem(
        key=r["item_key"], task=r["task_name"], category=r["category"],
        required=bool(r["required"]), due_offset_days=r["due_offset_days"],
        owner_role=r["owner_role"], sensitive=bool(r["sensitive"]),
        position=r["position"]) for r in conn.execute(
            "SELECT * FROM onboarding_template_items WHERE version_id = ? "
            "ORDER BY position, id", (version_id,))]


def _load(conn: Any, r: Any,
          version: int | None = None) -> Template:
    v = conn.execute(
        "SELECT * FROM onboarding_template_versions WHERE template_id = ? "
        "AND version = ?", (r["template_id"], version or r["current_version"])
    ).fetchone()
    if v is None:
        raise ValidationError(f"Template {r['name']!r} has no version "
                              f"{version}")
    return Template(
        template_id=r["template_id"], name=r["name"],
        learner_type=v["learner_type"], kind=v["kind"],
        description=v["description"], active=bool(r["active"]),
        version=v["version"], updated_at=v["saved_at"],
        updated_by=v["saved_by"],
        items=_items_for_version(conn, v["version_id"]))


def get_template(name: str, *, version: int | None = None) -> Template | None:
    """The template (its current version, or ``version``)."""
    init_db()
    with ob._connect() as conn:
        r = conn.execute("SELECT * FROM onboarding_templates WHERE name = ?",
                         ((name or "").strip(),)).fetchone()
        return _load(conn, r, version) if r else None


def list_templates(*, kind: str | None = None, learner_type: str | None = None,
                   include_inactive: bool = False) -> list[Template]:
    init_db()
    clauses, args = [], []
    if not include_inactive:
        clauses.append("active = 1")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with ob._connect() as conn:
        rows = conn.execute(f"SELECT * FROM onboarding_templates {where} "  # noqa: S608 — fixed clause
                            "ORDER BY template_id", args).fetchall()
        out = [_load(conn, r) for r in rows]
    return [t for t in out if (kind is None or t.kind == kind)
            and (learner_type is None or t.learner_type == learner_type)]


def template_names(*, kind: str | None = "base") -> list[str]:
    """Active template names (for pickers; base templates by default)."""
    return [t.name for t in list_templates(kind=kind)]


def exists(name: str) -> bool:
    t = get_template(name)
    return t is not None and t.active


def for_learner_type(learner_type: str) -> Template | None:
    """The active template for a learner type (first one made)."""
    found = list_templates(learner_type=learner_type)
    return found[0] if found else None


def versions(name: str) -> list[dict[str, Any]]:
    """Every saved version, newest first (who, when, note, what changed)."""
    init_db()
    with ob._connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT v.version, v.saved_at, v.saved_by, v.note, v.changes, "
            "v.learner_type, v.kind, (SELECT COUNT(*) FROM "
            "onboarding_template_items i WHERE i.version_id = v.version_id) "
            "AS tasks FROM onboarding_template_versions v JOIN "
            "onboarding_templates t ON t.template_id = v.template_id "
            "WHERE t.name = ? ORDER BY v.version DESC", (name,))]


# ── Saving ────────────────────────────────────────────────────────

def _clean_items(items: list[Any]) -> list[TemplateItem]:
    out: list[TemplateItem] = []
    keys: set[str] = set()
    for pos, raw in enumerate(items or []):
        d = raw.__dict__ if isinstance(raw, TemplateItem) else dict(raw)
        task = (d.get("task") or d.get("task_name") or "").strip()
        if not task:
            raise ValidationError(f"Task {pos + 1}: a task name is required")
        if len(task) > 200:
            raise ValidationError(f"Task {pos + 1}: name too long (200 max)")
        key = (d.get("key") or d.get("item_key") or task).strip()
        if key in keys:
            raise ValidationError(f"Task {task!r} appears twice")
        keys.add(key)
        cat = (d.get("category") or "").strip()
        if cat not in ob.CATEGORIES:
            raise ValidationError(f"{task!r}: category must be one of: "
                                  f"{', '.join(ob.CATEGORIES)}")
        try:
            offset = int(d.get("due_offset_days",
                               CATEGORY_OFFSET.get(cat, 14)))
        except (TypeError, ValueError):
            raise ValidationError(f"{task!r}: the due offset must be a "
                                  "whole number of days") from None
        if not MIN_OFFSET <= offset <= MAX_OFFSET:
            raise ValidationError(f"{task!r}: the due offset must be "
                                  f"{MIN_OFFSET}..{MAX_OFFSET} days")
        owner = (d.get("owner_role") or "").strip() or None
        if owner is not None:
            match = next((o for o in OWNER_ROLES
                          if o.lower() == owner.lower()), None)
            if match is None:
                raise ValidationError(f"{task!r}: owner must be one of: "
                                      f"{', '.join(OWNER_ROLES)}")
            owner = match
        out.append(TemplateItem(
            key=key, task=task, category=cat,
            required=bool(d.get("required", True)), due_offset_days=offset,
            owner_role=owner,
            sensitive=bool(d.get("sensitive")) or ob._is_sensitive_key(key),
            position=pos))
    return out


def _diff(old: list[TemplateItem], new: list[TemplateItem]) -> str:
    o = {i.key: i for i in old}
    n = {i.key: i for i in new}
    parts = [f"+{k}" for k in n if k not in o]
    parts += [f"-{k}" for k in o if k not in n]
    for k in n.keys() & o.keys():
        a, b = o[k], n[k]
        what = [f for f in ("task", "category", "required", "due_offset_days",
                            "owner_role", "sensitive")
                if getattr(a, f) != getattr(b, f)]
        if what:
            parts.append(f"~{k} ({', '.join(what)})")
    return "; ".join(parts) or "no task changes"


def _write_version(conn: Any, template_id: int | None, *,
                   name: str, learner_type: str | None, kind: str,
                   description: str | None, items: list[TemplateItem],
                   note: str | None, changes: str, who: str | None,
                   built_in: bool = False) -> int:
    if template_id is None:
        template_id = conn.execute(
            "INSERT INTO onboarding_templates (name, learner_type, kind, "
            "description, current_version, built_in, updated_by) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)",
            (name, learner_type, kind, description, 1 if built_in else 0,
             who)).lastrowid
        version = 1
    else:
        version = conn.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM "
            "onboarding_template_versions WHERE template_id = ?",
            (template_id,)).fetchone()[0]
        conn.execute(
            "UPDATE onboarding_templates SET learner_type = ?, kind = ?, "
            "description = ?, current_version = ?, updated_at = "
            "datetime('now'), updated_by = ? WHERE template_id = ?",
            (learner_type, kind, description, version, who, template_id))
    vid = conn.execute(
        "INSERT INTO onboarding_template_versions (template_id, version, "
        "learner_type, kind, description, saved_by, note, changes) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (template_id, version, learner_type, kind, description, who, note,
         changes)).lastrowid
    conn.executemany(
        "INSERT INTO onboarding_template_items (version_id, position, "
        "item_key, task_name, category, required, due_offset_days, "
        "owner_role, sensitive) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [(vid, i.position, i.key, i.task, i.category, 1 if i.required else 0,
          i.due_offset_days, i.owner_role, 1 if i.sensitive else 0)
         for i in items])
    return version


def save_template(name: str, *, items: list[Any],
                  learner_type: str | None = None, kind: str = "base",
                  description: str | None = None,
                  note: str | None = None) -> Template:
    """Create a template or save a new version of it. ``items`` are
    :class:`TemplateItem` or dicts (task, key, category, required,
    due_offset_days, owner_role, sensitive). Checklists already made keep
    the version they were made from."""
    ob._require_writer("editing onboarding templates")
    init_db()
    name = (name or "").strip()
    if not name or len(name) > 80:
        raise ValidationError("A template name (80 characters max) is "
                              "required")
    if kind not in KINDS:
        raise ValidationError(f"Kind must be one of: {', '.join(KINDS)}")
    learner_type = (learner_type or "").strip() or None
    if learner_type is not None and learner_type not in LEARNER_TYPES:
        raise ValidationError("Learner type must be one of: "
                              + ", ".join(LEARNER_TYPES))
    clean = _clean_items(items)
    if kind == "addon" and not clean:
        raise ValidationError("An add-on template needs at least one task")
    if learner_type == INTERNATIONAL and not any(
            i.key == UKVI_KEY and i.required for i in clean):
        raise ValidationError(
            f"An international template must keep '{UKVI_KEY}' as a "
            "required task")
    who = ob._actor()
    with ob._connect() as conn:
        r = conn.execute("SELECT * FROM onboarding_templates WHERE name = ?",
                         (name,)).fetchone()
        if r is None:
            changes = f"created with {len(clean)} task(s)"
            _write_version(conn, None, name=name, learner_type=learner_type,
                           kind=kind, description=description, items=clean,
                           note=note, changes=changes, who=who)
        else:
            old = _load(conn, r)
            changes = _diff(old.items, clean)
            if old.kind != kind:
                changes += f"; kind {old.kind} → {kind}"
            if old.learner_type != learner_type:
                changes += (f"; learner type {old.learner_type or '—'} → "
                            f"{learner_type or '—'}")
            _write_version(conn, r["template_id"], name=name,
                           learner_type=learner_type, kind=kind,
                           description=description, items=clean, note=note,
                           changes=changes, who=who)
        conn.commit()
    out = get_template(name)
    assert out is not None
    return out


def set_active(name: str, active: bool, *, reason: str) -> Template:
    """Retire (or bring back) a template. Templates are never deleted:
    checklists keep pointing at the version they were made from."""
    ob._require_writer("editing onboarding templates")
    init_db()
    reason = ob._min_text(reason, "The reason")
    t = get_template(name)
    if t is None:
        raise ValidationError(f"No template {name!r}")
    if not active and name == ob.DEFAULT_TEMPLATE:
        raise ValidationError(f"{name!r} is the default template and can't "
                              "be retired")
    with ob._connect() as conn:
        conn.execute("UPDATE onboarding_templates SET active = ?, "
                     "updated_at = datetime('now'), updated_by = ? "
                     "WHERE template_id = ?",
                     (1 if active else 0, ob._actor(), t.template_id))
        conn.execute(
            "UPDATE onboarding_template_versions SET note = COALESCE(note "
            "|| ' / ', '') || ? WHERE template_id = ? AND version = ?",
            (f"{'Restored' if active else 'Retired'} by {ob._actor()} on "
             f"{_dt.date.today().isoformat()}: {reason}", t.template_id,
             t.version))
        conn.commit()
    out = get_template(name)
    assert out is not None
    return out


# ── Use by checklists ─────────────────────────────────────────────

def _start_date(started_on: str | None, enrolment_id: Any) -> _dt.date:
    if enrolment_id not in (None, ""):
        try:
            from education_system.systems.sixth_form.domain.admissions.enrolments import (
                enrolments as _enr,
            )
            e = _enr.get_enrolment(int(enrolment_id))
            if e is not None and e.start_date:
                return _dt.date.fromisoformat(e.start_date)
        except (ValueError, TypeError):
            pass
    return (_dt.date.fromisoformat(started_on) if started_on
            else _dt.date.today())


def item_rows(t: Template, start: _dt.date) -> list[dict[str, Any]]:
    """Keyword sets for ``onboarding._insert_item`` (no ``order``)."""
    return [{"task": i.task, "category": i.category, "required": i.required,
             "key": i.key, "sensitive": i.sensitive,
             "owner_role": i.owner_role,
             "due_date": (start + _dt.timedelta(days=i.due_offset_days)
                          ).isoformat()} for i in t.items]


def items_for(name: str, *, started_on: str | None = None,
              enrolment_id: Any = None
              ) -> tuple[int | None, list[dict[str, Any]]]:
    """(version, task rows) for opening a checklist from ``name``; each
    task's due date is the learner's start date (the enrolment's, else
    ``started_on``, else today) plus its offset."""
    t = get_template(name)
    if t is None or not t.active:
        raise ValidationError(f"Unknown template {name!r}. Valid: "
                              f"{', '.join(template_names(kind=None))}")
    return t.version, item_rows(t, _start_date(started_on, enrolment_id))


def record_use(conn: Any, checklist_id: int, name: str,
               version: int) -> None:
    """Remember which template version a checklist was made from."""
    conn.execute("INSERT INTO onboarding_checklist_templates (checklist_id, "
                 "template_name, version, applied_by) VALUES (?, ?, ?, ?)",
                 (checklist_id, name, version, ob._actor()))


def templates_used(checklist_id: int) -> list[dict[str, Any]]:
    """Template versions a checklist was made from (base first)."""
    init_db()
    with ob._connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT template_name, version, applied_at, applied_by FROM "
            "onboarding_checklist_templates WHERE checklist_id = ? "
            "ORDER BY id", (checklist_id,))]


def apply_template(checklist_id: int, name: str) -> list[str]:
    """Add a template's tasks (an add-on) to an open checklist; tasks it
    already has (by rule key) are kept, a required one makes the existing
    task required. Returns the tasks added. Idempotent."""
    ob._require_writer("adding onboarding tasks")
    init_db()
    chk = ob.get_checklist(checklist_id)
    if chk is None:
        raise ValidationError(f"No checklist #{checklist_id}")
    if not chk.is_open:
        raise ValidationError(f"Checklist #{checklist_id} is {chk.status}"
                              + (" (archived)" if chk.is_archived else ""))
    t = get_template(name)
    if t is None or not t.active:
        raise ValidationError(f"Unknown template {name!r}")
    rows = item_rows(t, _start_date(chk.started_on, chk.enrolment_id))
    added: list[str] = []
    with ob._connect() as conn:
        have = {r["item_key"] or r["task_name"]: r for r in conn.execute(
            "SELECT item_id, item_key, task_name, required FROM "
            "onboarding_items WHERE checklist_id = ?", (checklist_id,))}
        order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) FROM onboarding_items "
            "WHERE checklist_id = ?", (checklist_id,)).fetchone()[0] or 0
        for row in rows:
            got = have.get(row["key"])
            if got is not None:
                if row["required"] and not got["required"]:
                    conn.execute("UPDATE onboarding_items SET required = 1 "
                                 "WHERE item_id = ?", (got["item_id"],))
                continue
            order += 1
            ob._insert_item(conn, checklist_id, order=order,
                            source=f"template:{name}", **row)
            added.append(row["task"])
        already = conn.execute(
            "SELECT 1 FROM onboarding_checklist_templates WHERE "
            "checklist_id = ? AND template_name = ? AND version = ?",
            (checklist_id, name, t.version)).fetchone()
        if not already:
            record_use(conn, checklist_id, name, t.version)
            ob._log(conn, checklist_id=checklist_id,
                    student_id=chk.student_id, action="Template applied",
                    detail=f"{name} v{t.version}: "
                           + (", ".join(added) or "no new tasks"))
        conn.commit()
    if added:
        ob._maybe_auto_complete(checklist_id)
    return added
