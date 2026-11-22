"""Announcements for staff, pupils and families.

Kept from the old Announcements (and the old Notices board, which it
replaces):

* Title, body, summary, category, priority (1 Low to 5 Urgent), audiences,
  pinned, banner, needs acknowledgement, publish and expiry dates, author,
  view count, linked item, attachments note, notes and status (Draft,
  Scheduled, Published, Expired, Archived, Withdrawn).
* Publish, schedule, withdraw, archive, toggle pin, toggle banner, change
  status, delete, auto-expire; the Live now / Scheduled / Pinned / Banners /
  Expired / All lists, filters and search; the feed one audience sees; the
  summary.

New:

* **Audiences** for this school: all staff, all pupils, parents, a year group
  or a form (a year or form reaches its pupils and their families).
* **Who.** Any member of staff writes drafts. :data:`ANNOUNCEMENT_EDITORS`
  publish anything; a head of year publishes to their own year (and its
  forms). Authors change their own drafts. Every change is in
  ``announcement_audit`` and the activity log (ids only).
* **Read receipts.** Who has seen it and who has acknowledged it, and which
  staff haven't read a staff announcement yet. :func:`active_for` is what My
  Day and the portals show.
* **E-mail** a published announcement to its audience through the school
  outbox (staff logins; contacts with parental responsibility).
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import (
    ANNOUNCEMENT_EDITORS,
    STAFF_ROLES,
    Principal,
)
from education_system.systems.secondary.core.utilities.exports import safe_cell as _safe
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = P.ValidationError
PermissionDenied = P.PermissionDenied
NotFound = P.NotFound

CATEGORIES: tuple[str, ...] = (
    "General", "Whole School", "Safeguarding", "Examinations", "Sport", "Trips & Visits",
    "Achievements", "Wellbeing", "Parents", "Staff", "Pastoral", "Careers", "Clubs",
    "Timetable Change", "Cover", "Library", "Emergency", "Closure / Weather", "IT / Systems",
    "Other")
DEFAULT_CATEGORY = "General"
PRIORITIES: tuple[int, ...] = (1, 2, 3, 4, 5)
PRIORITY_LABELS = {1: "Low", 2: "Normal", 3: "Important", 4: "High", 5: "Urgent"}
DEFAULT_PRIORITY = 2
STATUSES: tuple[str, ...] = ("Draft", "Scheduled", "Published", "Expired", "Archived",
                             "Withdrawn")
DEFAULT_STATUS = "Draft"
#: Fixed audiences; "year:9" and "form:9A" are added per year / form.
BASE_AUDIENCES: dict[str, str] = {"staff": "All staff", "pupils": "All pupils",
                                  "parents": "Parents"}
TEMPLATE = "announcement"
MAX_TITLE, MAX_BODY = 150, 8000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS announcements (
    announcement_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title                    TEXT NOT NULL,
    body                     TEXT NOT NULL,
    summary                  TEXT,
    category                 TEXT NOT NULL DEFAULT 'General',
    priority                 INTEGER NOT NULL DEFAULT 2 CHECK (priority BETWEEN 1 AND 5),
    audiences                TEXT NOT NULL,
    pinned                   INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1)),
    banner                   INTEGER NOT NULL DEFAULT 0 CHECK (banner IN (0, 1)),
    requires_acknowledgement INTEGER NOT NULL DEFAULT 0 CHECK (requires_acknowledgement IN (0, 1)),
    publish_on               TEXT,
    expires_on               TEXT,
    published_on             TEXT,
    published_by             TEXT,
    status                   TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN
                             ('Draft', 'Scheduled', 'Published', 'Expired', 'Archived',
                              'Withdrawn')),
    author                   TEXT,
    author_name              TEXT,
    view_count               INTEGER NOT NULL DEFAULT 0,
    linked_to                TEXT,
    attachments_ref          TEXT,
    notes                    TEXT,
    emailed_at               TEXT,
    email_message_id         INTEGER,
    created_at               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by               TEXT,
    updated_at               TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_announcements_status ON announcements (status, publish_on);
CREATE TABLE IF NOT EXISTS announcement_reads (
    announcement_id INTEGER NOT NULL REFERENCES announcements (announcement_id)
                    ON DELETE CASCADE,
    username        TEXT NOT NULL COLLATE NOCASE,
    role            TEXT,
    read_at         TEXT NOT NULL DEFAULT (datetime('now')),
    acknowledged_at TEXT,
    PRIMARY KEY (announcement_id, username)
);
CREATE TABLE IF NOT EXISTS announcement_audit (
    audit_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    announcement_id INTEGER,
    action          TEXT NOT NULL,
    detail          TEXT,
    actor           TEXT NOT NULL,
    at              TEXT NOT NULL DEFAULT (datetime('now'))
);
"""
database.register_schema("announcements", _SCHEMA)


def priority_label(p: int | None) -> str:
    return PRIORITY_LABELS.get(int(p), "Unknown") if p is not None else "-"


def audience_label(token: str) -> str:
    if token in BASE_AUDIENCES:
        return BASE_AUDIENCES[token]
    if token.startswith("year:"):
        return f"Year {token[5:]}"
    if token.startswith("form:"):
        return f"Form {token[5:]}"
    return token


@dataclass(frozen=True)
class Announcement:
    announcement_id: int
    title: str
    body: str
    summary: str | None
    category: str
    priority: int
    audiences: str
    pinned: bool
    banner: bool
    requires_acknowledgement: bool
    publish_on: str | None
    expires_on: str | None
    published_on: str | None
    published_by: str | None
    status: str
    author: str | None
    author_name: str | None
    view_count: int
    linked_to: str | None
    attachments_ref: str | None
    notes: str | None
    emailed_at: str | None
    email_message_id: int | None
    created_at: str
    updated_by: str | None
    updated_at: str

    @property
    def audience_list(self) -> list[str]:
        return [a for a in self.audiences.split(",") if a]

    @property
    def audience_text(self) -> str:
        return ", ".join(audience_label(a) for a in self.audience_list)

    @property
    def priority_label(self) -> str:
        return priority_label(self.priority)

    @property
    def is_published(self) -> bool:
        return self.status in ("Published", "Scheduled")

    @property
    def is_live(self) -> bool:
        """Currently visible to its audience."""
        if not self.is_published:
            return False
        today = _today().isoformat()
        if self.publish_on and self.publish_on > today:
            return False
        return not (self.expires_on and self.expires_on < today)

    @property
    def is_expired(self) -> bool:
        return self.status == "Expired" or (
            self.is_published and bool(self.expires_on) and
            self.expires_on < _today().isoformat())

    @property
    def is_scheduled(self) -> bool:
        return self.is_published and bool(self.publish_on) and \
            self.publish_on > _today().isoformat()

    @property
    def shown_status(self) -> str:
        if self.is_expired and self.status != "Expired":
            return "Expired"
        if self.status == "Scheduled" and self.is_live:
            return "Published"
        return self.status


_BOOLS = ("pinned", "banner", "requires_acknowledgement")


def _row(r) -> Announcement:
    v = {k: r[k] for k in Announcement.__dataclass_fields__}
    for k in _BOOLS:
        v[k] = bool(v[k])
    return Announcement(**v)


# ── Who may do what ──────────────────────────────────────────────────

def is_editor(actor: Principal) -> bool:
    return actor.role in ANNOUNCEMENT_EDITORS


def _deny(actor: Principal, action: str, target: Any, message: str) -> None:
    activity_log.record(f"announcements.{action}", target=target, outcome="denied",
                        principal=actor)
    raise PermissionDenied(message)


def _require_staff(actor: Principal, action: str, target: Any = None) -> None:
    if actor.role not in STAFF_ROLES:
        _deny(actor, action, target, "Only staff can write announcements.")


def _require_editor(actor: Principal, action: str, target: Any = None) -> None:
    if not is_editor(actor):
        _deny(actor, action, target, "Only the announcements editors can do that.")


def _form_years() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        from education_system.systems.secondary.modules.curriculum.domain import form_groups as FG
        out = {f.name.upper(): f.year_group for f in FG.list_forms()}
    except Exception:  # noqa: BLE001 - fall back to pupils' forms
        out = {}
    for p in P.list_pupils():
        if p.form_group:
            out.setdefault(p.form_group.upper(), p.year_group)
    return out


def _token_year(token: str, forms: dict[str, int] | None = None) -> int | None:
    if token.startswith("year:"):
        return int(token[5:])
    if token.startswith("form:"):
        return (forms if forms is not None else _form_years()).get(token[5:].upper())
    return None


def can_publish(actor: Principal, audiences: list[str] | str) -> bool:
    """The editors publish anything; a head of year publishes to their own
    year group and its forms."""
    if is_editor(actor):
        return True
    if actor.role not in STAFF_ROLES:
        return False
    tokens = audiences.split(",") if isinstance(audiences, str) else list(audiences)
    tokens = [t for t in tokens if t]
    if not tokens:
        return False
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    forms = _form_years()
    for t in tokens:
        y = _token_year(t, forms)
        if y is None or not BH.is_head_of_year(actor, y):
            return False
    return True


def can_edit(actor: Principal, a: Announcement) -> bool:
    if is_editor(actor):
        return True
    if actor.role not in STAFF_ROLES:
        return False
    own = bool(actor.username) and (a.author or "").lower() == actor.username.lower()
    if own and a.status in ("Draft", "Withdrawn"):
        return True
    return can_publish(actor, a.audience_list)


def _audit(conn, action: str, actor: Principal, announcement_id: int | None, **detail: Any
           ) -> None:
    conn.execute("INSERT INTO announcement_audit (announcement_id, action, detail, actor) "
                 "VALUES (?, ?, ?, ?)",
                 (announcement_id, action, json.dumps(detail, default=str) if detail else None,
                  actor.username or "unknown"))


def history(announcement_id: int | None = None, *, limit: int = 300) -> list[dict[str, Any]]:
    sql, params = "SELECT * FROM announcement_audit", []
    if announcement_id is not None:
        sql += " WHERE announcement_id = ?"
        params.append(int(announcement_id))
    with database.connect() as conn:
        return [{"at": r["at"], "announcement_id": r["announcement_id"], "action": r["action"],
                 "actor": r["actor"], "detail": json.loads(r["detail"] or "{}")}
                for r in conn.execute(sql + " ORDER BY audit_id DESC LIMIT ?",
                                      (*params, int(limit)))]


# ── Cleaning ─────────────────────────────────────────────────────────

def _date(value: Any, label: str, problems: list[str]) -> str | None:
    if value in (None, "") or (isinstance(value, str) and not value.strip()):
        return None
    try:
        return _dt.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        problems.append(f"{label} must be a date (YYYY-MM-DD)")
        return None


def _flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in ("1", "true", "yes", "y", "on")


def _text(value: Any, limit: int) -> str | None:
    return (str(value or "").strip()[:limit]) or None


def audience_choices() -> list[tuple[str, str]]:
    """Every audience to pick from: (token, label)."""
    out = list(BASE_AUDIENCES.items())
    out += [(f"year:{y}", f"Year {y}") for y in P.YEAR_GROUPS]
    out += [(f"form:{f}", f"Form {f}") for f in sorted(_form_years())]
    return out


def parse_audiences(value: Any, problems: list[str]) -> list[str]:
    """Tokens from a list or text ("staff, parents, year 9, form 9A")."""
    raw = value if isinstance(value, (list, tuple, set)) else \
        re.split(r"[,;\n]+", str(value or ""))
    out: list[str] = []
    labels = {v.lower(): k for k, v in BASE_AUDIENCES.items()}
    for item in raw:
        v = " ".join(str(item).split()).strip()
        if not v:
            continue
        low = v.lower()
        tok = None
        if low in BASE_AUDIENCES:
            tok = low
        elif low in labels:
            tok = labels[low]
        elif low in ("students", "all students", "all pupils"):
            tok = "pupils"
        elif low in ("all staff",):
            tok = "staff"
        elif low in ("all parents",):
            tok = "parents"
        else:
            m = re.match(r"^(?:year[:\s]*)(\d+)$", low)
            f = re.match(r"^form[:\s]*(\S+)$", low)
            if m and int(m.group(1)) in P.YEAR_GROUPS:
                tok = f"year:{int(m.group(1))}"
            elif f:
                tok = f"form:{f.group(1).upper()}"
        if tok is None:
            problems.append(f"Unknown audience '{v}' (all staff, all pupils, parents, "
                            "year 7-11, form <name>)")
        elif tok not in out:
            out.append(tok)
    return out


FIELDS = ("title", "body", "summary", "category", "priority", "audiences", "pinned", "banner",
          "requires_acknowledgement", "publish_on", "expires_on", "linked_to",
          "attachments_ref", "notes")


def _clean(data: dict[str, Any], current: Announcement | None
           ) -> tuple[dict[str, Any], list[str]]:
    problems: list[str] = []
    merged = {k: getattr(current, k) for k in FIELDS} if current else {}
    merged.update({k: v for k, v in data.items() if k in FIELDS})
    out: dict[str, Any] = {}
    out["title"] = " ".join(str(merged.get("title") or "").split())
    if not out["title"]:
        problems.append("Title is required")
    elif len(out["title"]) > MAX_TITLE:
        problems.append(f"Title must be {MAX_TITLE} characters or fewer")
    out["body"] = str(merged.get("body") or "").replace("\r\n", "\n").strip()
    if not out["body"]:
        problems.append("The announcement is empty")
    elif len(out["body"]) > MAX_BODY:
        problems.append(f"The announcement must be {MAX_BODY} characters or fewer")
    out["summary"] = _text(merged.get("summary"), 300)
    cat = str(merged.get("category") or "").strip()
    out["category"] = next((c for c in CATEGORIES if c.lower() == cat.lower()),
                           DEFAULT_CATEGORY if not cat else None)
    if out["category"] is None:
        problems.append(f"Category must be one of {', '.join(CATEGORIES)}")
        out["category"] = DEFAULT_CATEGORY
    raw = merged.get("priority")
    try:
        out["priority"] = int(str(raw).strip()[:1]) if raw not in (None, "") else \
            DEFAULT_PRIORITY
    except ValueError:
        out["priority"] = next((k for k, v in PRIORITY_LABELS.items()
                                if v.lower() == str(raw).strip().lower()), 0)
    if out["priority"] not in PRIORITIES:
        problems.append("Priority must be 1 (Low) to 5 (Urgent)")
        out["priority"] = DEFAULT_PRIORITY
    tokens = parse_audiences(merged.get("audiences"), problems)
    if not tokens and not any(p.startswith("Unknown audience") for p in problems):
        problems.append("Choose who it is for")
    out["audiences"] = ",".join(tokens)
    for k in _BOOLS:
        out[k] = _flag(merged.get(k))
    out["publish_on"] = _date(merged.get("publish_on"), "Publish on", problems)
    out["expires_on"] = _date(merged.get("expires_on"), "Expires on", problems)
    if out["publish_on"] and out["expires_on"] and out["expires_on"] < out["publish_on"]:
        problems.append("It can't expire before it is published")
    out["linked_to"] = _text(merged.get("linked_to"), 200)
    out["attachments_ref"] = _text(merged.get("attachments_ref"), 300)
    out["notes"] = _text(merged.get("notes"), 2000)
    return out, problems


def _staff_name(actor: Principal) -> str:
    from education_system.systems.secondary.modules.behaviour.domain import behaviour as BH
    return BH._staff_name(actor)


# ── Reading ──────────────────────────────────────────────────────────

def get(announcement_id: int) -> Announcement:
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM announcements WHERE announcement_id = ?",
                         (int(announcement_id),)).fetchone()
    if r is None:
        raise NotFound(f"No announcement #{announcement_id}")
    return _row(r)


def get_announcement(announcement_id: int) -> Announcement | None:
    try:
        return get(announcement_id)
    except NotFound:
        return None


SCOPES = ("live", "scheduled", "pinned", "banners", "expired", "drafts", "all")


def _sorted(rows: list[Announcement]) -> list[Announcement]:
    """Pinned first, then most urgent, then newest."""
    rows = sorted(rows, key=lambda a: (a.published_on or a.created_at or "",
                                       a.announcement_id), reverse=True)
    return sorted(rows, key=lambda a: (not a.pinned, -a.priority))


def list_announcements(*, scope: str = "all", category: str | None = None,
                       status: str | None = None, audience: str | None = None,
                       priority_min: int | None = None, search: str | None = None,
                       author: str | None = None) -> list[Announcement]:
    """The old lists: live now, scheduled, pinned, banners, expired (not yet
    archived), drafts and all, with the old filters and a search."""
    with database.connect() as conn:
        rows = [_row(r) for r in conn.execute("SELECT * FROM announcements")]
    out = []
    for a in rows:
        if scope == "live" and not a.is_live:
            continue
        if scope == "scheduled" and not (a.is_scheduled or a.status == "Scheduled" and
                                         not a.is_live and not a.is_expired):
            continue
        if scope == "pinned" and not (a.pinned and a.status not in ("Archived", "Withdrawn")):
            continue
        if scope == "banners" and not (a.banner and a.is_live):
            continue
        if scope == "expired" and not (a.is_expired and a.status != "Archived"):
            continue
        if scope == "drafts" and a.status != "Draft":
            continue
        if category and a.category != category:
            continue
        if status and a.shown_status != status and a.status != status:
            continue
        if audience and audience not in a.audience_list:
            continue
        if priority_min and a.priority < int(priority_min):
            continue
        if author and (a.author or "").lower() != author.lower():
            continue
        if search:
            hay = f"{a.title}\n{a.body}\n{a.summary or ''}".lower()
            if not all(w in hay for w in search.lower().split()):
                continue
        out.append(a)
    return _sorted(out)


def feed_for_audience(token: str) -> list[Announcement]:
    """What one audience sees now (the old notices feed)."""
    return [a for a in list_announcements(scope="live") if token in a.audience_list]


def _tokens_for_pupils(pupils: list[P.Pupil]) -> set[str]:
    out: set[str] = set()
    for p in pupils:
        out.add(f"year:{p.year_group}")
        if p.form_group:
            out.add(f"form:{p.form_group.upper()}")
    return out


def audiences_for(principal: Principal) -> set[str]:
    """The audience tokens a login belongs to."""
    out: set[str] = set()
    if principal.role in STAFF_ROLES:
        out.add("staff")
    from education_system.systems.secondary.modules.portals.domain import portal_accounts as PA
    if principal.is_student:
        out.add("pupils")
        out |= _tokens_for_pupils(PA.pupils_for(principal, "pupil"))
    elif principal.is_parent or (principal.role in STAFF_ROLES and PA.has_children(principal)):
        kids = PA.pupils_for(principal, "parent")
        if kids or principal.is_parent:
            out.add("parents")
        out |= _tokens_for_pupils(kids)
    return out


def active_for(principal: Principal) -> list[Announcement]:
    """Live announcements for this login (My Day, the portals), pinned and
    urgent first."""
    mine = audiences_for(principal)
    return [a for a in list_announcements(scope="live") if mine & set(a.audience_list)]


def banners_for(principal: Principal) -> list[Announcement]:
    return [a for a in active_for(principal) if a.banner]


def _read_rows(announcement_id: int) -> list[dict[str, Any]]:
    with database.connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM announcement_reads WHERE announcement_id = ? ORDER BY read_at",
            (int(announcement_id),))]


def unread_for(principal: Principal) -> list[Announcement]:
    rows = active_for(principal)
    if not rows or not principal.username:
        return rows
    with database.connect() as conn:
        seen = {r[0] for r in conn.execute(
            "SELECT announcement_id FROM announcement_reads WHERE username = ?",
            (principal.username,))}
    return [a for a in rows if a.announcement_id not in seen]


def needs_acknowledgement(principal: Principal) -> list[Announcement]:
    rows = [a for a in active_for(principal) if a.requires_acknowledgement]
    if not rows or not principal.username:
        return rows
    with database.connect() as conn:
        done = {r[0] for r in conn.execute(
            "SELECT announcement_id FROM announcement_reads WHERE username = ? AND "
            "acknowledged_at IS NOT NULL", (principal.username,))}
    return [a for a in rows if a.announcement_id not in done]


# ── Read receipts ────────────────────────────────────────────────────

def mark_read(announcement_id: int, principal: Principal) -> bool:
    """Record that this login has seen it (first view counts). True when new."""
    a = get(announcement_id)
    if not principal.username:
        return False
    if not (is_editor(principal) or (a.is_live and audiences_for(principal) &
                                     set(a.audience_list))):
        return False
    with database.connect() as conn:
        cur = conn.execute("INSERT OR IGNORE INTO announcement_reads (announcement_id, "
                           "username, role) VALUES (?, ?, ?)",
                           (a.announcement_id, principal.username, principal.role))
        new = cur.rowcount > 0
        if new:
            conn.execute("UPDATE announcements SET view_count = view_count + 1 WHERE "
                         "announcement_id = ?", (a.announcement_id,))
    return new


def acknowledge(announcement_id: int, principal: Principal) -> None:
    a = get(announcement_id)
    if not (a.is_live and audiences_for(principal) & set(a.audience_list)):
        raise ValidationError(["That announcement isn't showing for you"])
    mark_read(a.announcement_id, principal)
    with database.connect() as conn:
        conn.execute("UPDATE announcement_reads SET acknowledged_at = COALESCE("
                     "acknowledged_at, datetime('now')) WHERE announcement_id = ? AND "
                     "username = ?", (a.announcement_id, principal.username))
    activity_log.record("announcements.acknowledge", target=f"announcement:{a.announcement_id}",
                        principal=principal)


def receipts(announcement_id: int, *, actor: Principal) -> dict[str, Any]:
    """Who has seen it: {'read': [{username, role, read_at, acknowledged_at}],
    'staff_not_read': [display names], 'acknowledged': n}."""
    a = get(announcement_id)
    _require_staff(actor, "receipts")
    rows = _read_rows(a.announcement_id)
    names: dict[str, str] = {}
    not_read: list[str] = []
    try:
        from education_system.systems.secondary.infrastructure.authentication import accounts
        staff = accounts.staff_logins()
        names = {s["username"].lower(): s["display_name"] for s in staff}
        if "staff" in a.audience_list:
            have = {r["username"].lower() for r in rows}
            not_read = [s["display_name"] for s in staff if s["username"].lower() not in have]
    except Exception:  # noqa: BLE001 - the names are a convenience
        pass
    for r in rows:
        r["name"] = names.get(r["username"].lower(), r["username"])
    return {"read": rows, "staff_not_read": not_read,
            "acknowledged": sum(1 for r in rows if r["acknowledged_at"])}


# ── Writing ──────────────────────────────────────────────────────────

def create(data: dict[str, Any], *, actor: Principal) -> Announcement:
    """A new draft (any member of staff)."""
    _require_staff(actor, "create")
    c, problems = _clean(data, None)
    if problems:
        raise ValidationError(problems)
    with database.connect() as conn:
        aid = conn.execute(
            f"INSERT INTO announcements ({', '.join(FIELDS)}, status, author, author_name, "
            f"updated_by) VALUES ({', '.join('?' * len(FIELDS))}, 'Draft', ?, ?, ?)",
            (*(int(c[k]) if k in _BOOLS else c[k] for k in FIELDS), actor.username,
             _staff_name(actor), actor.username)).lastrowid
        _audit(conn, "create", actor, aid, audiences=c["audiences"])
    activity_log.record("announcements.create", target=f"announcement:{aid}", principal=actor)
    return get(aid)


new_announcement = create


def update(announcement_id: int, changes: dict[str, Any], *, actor: Principal) -> Announcement:
    """The old Edit. A published announcement's audience can only become one
    you may publish to."""
    cur = get(announcement_id)
    if not can_edit(actor, cur):
        _deny(actor, "update", f"announcement:{cur.announcement_id}",
              "You can change your own drafts; editors and heads of year change published "
              "ones.")
    c, problems = _clean(changes, cur)
    if cur.is_published and not problems and not can_publish(actor, c["audiences"]):
        problems.append("You can't publish to that audience")
    if problems:
        raise ValidationError(problems)
    changed = [k for k in FIELDS if c[k] != getattr(cur, k)]
    if not changed:
        return cur
    with database.connect() as conn:
        conn.execute("UPDATE announcements SET " + ", ".join(f"{k} = ?" for k in changed)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE announcement_id = ?",
                     (*(int(c[k]) if k in _BOOLS else c[k] for k in changed), actor.username,
                      cur.announcement_id))
        _audit(conn, "update", actor, cur.announcement_id, fields=changed)
    activity_log.record("announcements.update", target=f"announcement:{cur.announcement_id}",
                        principal=actor, fields=",".join(changed))
    return get(cur.announcement_id)


def _set(a: Announcement, actor: Principal, action: str, **vals: Any) -> Announcement:
    with database.connect() as conn:
        conn.execute("UPDATE announcements SET " + ", ".join(f"{k} = ?" for k in vals)
                     + ", updated_by = ?, updated_at = datetime('now') WHERE announcement_id = ?",
                     (*vals.values(), actor.username, a.announcement_id))
        _audit(conn, action, actor, a.announcement_id,
               **{k: v for k, v in vals.items() if k in ("status", "pinned", "banner",
                                                         "publish_on")})
    activity_log.record(f"announcements.{action}", target=f"announcement:{a.announcement_id}",
                        principal=actor)
    return get(a.announcement_id)


def publish(announcement_id: int, *, actor: Principal, publish_on: str | None = None
            ) -> Announcement:
    """Publish now, or schedule it when its publish date is ahead."""
    a = get(announcement_id)
    if not can_publish(actor, a.audience_list):
        _deny(actor, "publish", f"announcement:{a.announcement_id}",
              "Only the announcements editors publish school-wide; a head of year publishes "
              "to their own year.")
    problems: list[str] = []
    when = _date(publish_on, "Publish on", problems) if publish_on else a.publish_on
    if a.status in ("Archived",):
        problems.append("Restore it (change status to Draft) before publishing")
    if a.expires_on and a.expires_on < _today().isoformat():
        problems.append("Its expiry date has passed - change the expiry date first")
    if when and a.expires_on and a.expires_on < when:
        problems.append("It can't expire before it is published")
    if problems:
        raise ValidationError(problems)
    today = _today().isoformat()
    status = "Scheduled" if when and when > today else "Published"
    return _set(a, actor, "publish", status=status, publish_on=when,
                published_on=a.published_on or (when if when and when > today else today),
                published_by=actor.username)


def schedule(announcement_id: int, publish_on: str, *, actor: Principal) -> Announcement:
    """The old Schedule: publish on a later date."""
    problems: list[str] = []
    when = _date(publish_on, "Publish on", problems)
    if not when:
        problems.append("Give the date to publish on")
    elif when <= _today().isoformat():
        problems.append("Schedule for a date after today (or publish now)")
    if problems:
        raise ValidationError(problems)
    return publish(announcement_id, actor=actor, publish_on=when)


def withdraw(announcement_id: int, *, actor: Principal) -> Announcement:
    a = get(announcement_id)
    if not can_publish(actor, a.audience_list):
        _require_editor(actor, "withdraw", f"announcement:{a.announcement_id}")
    return _set(a, actor, "withdraw", status="Withdrawn")


def archive(announcement_id: int, *, actor: Principal) -> Announcement:
    a = get(announcement_id)
    if not can_publish(actor, a.audience_list):
        _require_editor(actor, "archive", f"announcement:{a.announcement_id}")
    return _set(a, actor, "archive", status="Archived", pinned=0, banner=0)


def toggle_pin(announcement_id: int, *, actor: Principal) -> Announcement:
    a = get(announcement_id)
    if not can_edit(actor, a):
        _require_editor(actor, "pin", f"announcement:{a.announcement_id}")
    return _set(a, actor, "pin", pinned=0 if a.pinned else 1)


def toggle_banner(announcement_id: int, *, actor: Principal) -> Announcement:
    a = get(announcement_id)
    if not can_edit(actor, a):
        _require_editor(actor, "banner", f"announcement:{a.announcement_id}")
    return _set(a, actor, "banner", banner=0 if a.banner else 1)


def set_status(announcement_id: int, status: str, *, actor: Principal) -> Announcement:
    """The old Change status (Published and Scheduled go through publish)."""
    a = get(announcement_id)
    st = next((s for s in STATUSES if s.lower() == str(status or "").strip().lower()), None)
    if st is None:
        raise ValidationError([f"Status must be one of {', '.join(STATUSES)}"])
    if st in ("Published", "Scheduled"):
        return publish(a.announcement_id, actor=actor)
    if st == "Draft" and not can_edit(actor, a):
        _require_editor(actor, "status", f"announcement:{a.announcement_id}")
    elif st != "Draft" and not can_publish(actor, a.audience_list):
        _require_editor(actor, "status", f"announcement:{a.announcement_id}")
    return _set(a, actor, "status", status=st)


def delete(announcement_id: int, *, actor: Principal) -> bool:
    """Authors delete their own drafts; editors delete any."""
    a = get(announcement_id)
    own = bool(actor.username) and (a.author or "").lower() == actor.username.lower()
    if not (is_editor(actor) or (own and a.status == "Draft")):
        _deny(actor, "delete", f"announcement:{a.announcement_id}",
              "You can delete your own drafts; editors delete published announcements.")
    with database.connect() as conn:
        conn.execute("DELETE FROM announcements WHERE announcement_id = ?", (a.announcement_id,))
        _audit(conn, "delete", actor, a.announcement_id, title_len=len(a.title))
    activity_log.record("announcements.delete", target=f"announcement:{a.announcement_id}",
                        principal=actor)
    return True


def auto_expire(*, actor: Principal) -> int:
    """The old Auto-expire: published announcements past their expiry date
    become Expired. Returns how many."""
    _require_editor(actor, "auto_expire")
    today = _today().isoformat()
    with database.connect() as conn:
        n = conn.execute("UPDATE announcements SET status = 'Expired', updated_by = ?, "
                         "updated_at = datetime('now') WHERE status IN ('Published', "
                         "'Scheduled') AND expires_on IS NOT NULL AND expires_on < ?",
                         (actor.username, today)).rowcount
        _audit(conn, "auto_expire", actor, None, count=n)
    activity_log.record("announcements.auto_expire", principal=actor, count=n)
    return int(n)


def duplicate(announcement_id: int, *, actor: Principal) -> Announcement:
    """A new draft copied from another."""
    a = get(announcement_id)
    return create({**{k: getattr(a, k) for k in FIELDS}, "title": f"Copy of {a.title}"[:MAX_TITLE],
                   "publish_on": None, "expires_on": None}, actor=actor)


# ── E-mail ───────────────────────────────────────────────────────────

def _audience_pupils(tokens: list[str]) -> list[P.Pupil]:
    if "parents" in tokens:
        return P.list_pupils()
    out: dict[int, P.Pupil] = {}
    for t in tokens:
        if t.startswith("year:"):
            out.update({p.pupil_id: p for p in P.list_pupils(year_group=int(t[5:]))})
        elif t.startswith("form:"):
            out.update({p.pupil_id: p for p in P.list_pupils(form_group=t[5:])})
    return list(out.values())


def email_recipients(announcement_id: int) -> dict[str, Any]:
    """Who an e-mail would reach: {'to': [(address, name)], 'pupils_without':
    n, 'pupils_only': bool}."""
    from education_system.systems.secondary.modules.pupils.domain import contacts as C
    a = get(announcement_id)
    tokens = a.audience_list
    seen: dict[str, str] = {}
    if "staff" in tokens:
        try:
            from education_system.systems.secondary.infrastructure.authentication import accounts
            for s in accounts.staff_logins():
                if s.get("email") and C.valid_email(s["email"].lower()):
                    seen.setdefault(s["email"].lower(), s["display_name"])
        except Exception:  # noqa: BLE001 - no staff list: families still get it
            pass
    pupils = _audience_pupils(tokens)
    contacts = C.emailable_for_pupils([p.pupil_id for p in pupils])
    without = 0
    for p in pupils:
        found = [c for c in contacts.get(p.pupil_id, []) if c.parental_responsibility]
        if not found:
            without += 1
        for c in found:
            seen.setdefault(c.email.lower(), c.full_name)
    return {"to": sorted(seen.items()), "pupils_without": without,
            "pupils_only": tokens == ["pupils"]}


def email_audience(announcement_id: int, *, actor: Principal) -> dict[str, Any]:
    """E-mail a live announcement to its audience (staff logins and contacts
    with parental responsibility; pupils see it in their portal). Returns
    {'message_id', 'emails', 'pupils_without'}."""
    from education_system.systems.secondary.modules.communication.domain import email_outbox as E
    from education_system.systems.secondary.modules.communication.domain import email_templates
    a = get(announcement_id)
    if not can_publish(actor, a.audience_list):
        _deny(actor, "email", f"announcement:{a.announcement_id}",
              "Only someone who can publish to this audience can e-mail it.")
    if not a.is_live:
        raise ValidationError(["Publish it first (it must be showing now)"])
    who = email_recipients(a.announcement_id)
    if not who["to"]:
        raise ValidationError(["Nobody to e-mail - pupils see announcements in their portal"
                               if who["pupils_only"] else "Nobody in the audience has an "
                               "e-mail address"])
    template = email_templates.load_template(TEMPLATE)
    letters = []
    for addr, name in who["to"]:
        subject, body = template.render({"recipient_name": name or "Parent/Carer",
                                         "title": a.title, "body": a.body,
                                         "author_name": a.author_name or a.author or ""})
        letters.append((addr, name, subject, body))
    mid = E.save_prepared("announcement", f"Announcement: {a.audience_text}"[:200], a.title,
                          "(one e-mail per recipient)", letters, actor=actor)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with database.connect() as conn:
        conn.execute("UPDATE announcements SET emailed_at = ?, email_message_id = ? WHERE "
                     "announcement_id = ?", (now, mid, a.announcement_id))
        _audit(conn, "email", actor, a.announcement_id, emails=len(letters))
    activity_log.record("announcements.email", target=f"announcement:{a.announcement_id}",
                        principal=actor, emails=len(letters))
    return {"message_id": mid, "emails": len(letters), "pupils_without": who["pupils_without"]}


# ── Summary & export ─────────────────────────────────────────────────

@dataclass
class AnnouncementsSummary:
    total: int = 0
    drafts: int = 0
    scheduled: int = 0
    published: int = 0
    live_now: int = 0
    expired_unarchived: int = 0
    pinned: int = 0
    banners: int = 0
    urgent_count: int = 0
    total_views: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_priority: dict[int, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_audience: dict[str, int] = field(default_factory=dict)


def summary() -> AnnouncementsSummary:
    rows = list_announcements()
    out = AnnouncementsSummary(total=len(rows))
    aud: Counter = Counter()
    for a in rows:
        out.drafts += a.status == "Draft"
        out.scheduled += a.is_scheduled
        out.published += a.status == "Published"
        out.live_now += a.is_live
        out.expired_unarchived += a.is_expired and a.status != "Archived"
        out.pinned += a.pinned
        out.banners += a.banner
        out.urgent_count += a.priority == 5 and a.is_live
        out.total_views += a.view_count
        aud.update(audience_label(t) for t in a.audience_list)
    out.by_category = dict(Counter(a.category for a in rows))
    out.by_priority = dict(Counter(a.priority for a in rows))
    out.by_status = dict(Counter(a.shown_status for a in rows))
    out.by_audience = dict(aud)
    return out


def export_csv(path: str | Path, *, actor: Principal, **filters: Any) -> int:
    _require_staff(actor, "export")
    rows = list_announcements(**filters)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "title", "category", "priority", "audiences", "status", "pinned",
                    "banner", "publish_on", "expires_on", "author", "views", "emailed"])
        for a in rows:
            w.writerow([a.announcement_id, _safe(a.title), a.category, a.priority,
                        _safe(a.audience_text), a.shown_status, int(a.pinned), int(a.banner),
                        a.publish_on or "", a.expires_on or "", _safe(a.author_name or a.author),
                        a.view_count, (a.emailed_at or "")[:10]])
    activity_log.record("announcements.export", principal=actor, rows=len(rows))
    return len(rows)
