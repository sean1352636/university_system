"""Site & IT helpdesk for the Sixth Form System.

Any member of staff can report a broken radiator, a dead projector or a
password that will not reset; the site team and IT support work the
queue. Two tables:

* ``helpdesk_tickets`` — one row per job: Site or IT, a category, where
  it is (a free-text location, optionally the bookable room from
  :mod:`room_booking` and the asset from the asset register), priority,
  status, who it is assigned to, the SLA due time and the resolution.
* ``helpdesk_updates`` — the ticket's history: comments from the person
  who raised it and the team, plus an automatic line for every status
  change and (re)assignment. Internal notes are visible to the team only.

Status runs New → Assigned → In progress ⇄ On hold → Resolved → Closed;
a resolved or closed ticket can be reopened. The SLA clock is set from
the priority when the ticket is raised (or re-prioritised) and *stops*
while the ticket is On hold — the due time moves on by however long it
was held, so waiting for a part does not count against the team.

Access (``access.py``): any staff login raises tickets and sees, comments
on, confirms or reopens its own; ``OPERATIONS`` (site staff, IT support,
office) sees and manages every ticket. Tickets are never deleted — a
mistaken one is closed with a resolution saying so.

Resolving a ticket that names an asset can write a "Repair" entry into
the asset's maintenance log, so the asset register keeps its history.
"""

from __future__ import annotations

import datetime as _dt
import logging
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system import paths
from education_system.systems.sixth_form.domain.governance.user_management import (
    access,
)
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_STUDENTS_DB

SITE = "Site"
IT = "IT"
KINDS: tuple[str, ...] = (SITE, IT)

#: Categories per kind. Policy, not data: edit here to suit the site.
CATEGORIES: dict[str, tuple[str, ...]] = {
    SITE: ("Building fabric", "Heating / ventilation", "Plumbing / water",
           "Electrical / power", "Lighting", "Doors / locks / security",
           "Furniture", "Cleaning", "Grounds / external", "Pest control",
           "Health & safety hazard", "Other"),
    IT: ("Hardware / device", "Software", "Network / Wi-Fi",
         "Account / password", "Printing / copying", "AV / projector",
         "Email", "Telephony", "MIS / data", "Other"),
}

LOW, MEDIUM, HIGH, URGENT = "Low", "Medium", "High", "Urgent"
PRIORITIES: tuple[str, ...] = (LOW, MEDIUM, HIGH, URGENT)
DEFAULT_PRIORITY = MEDIUM

#: Hours from raising (clock time) to resolution, by priority.
SLA_HOURS: dict[str, int] = {URGENT: 4, HIGH: 24, MEDIUM: 72, LOW: 168}

NEW = "New"
ASSIGNED = "Assigned"
IN_PROGRESS = "In progress"
ON_HOLD = "On hold"
RESOLVED = "Resolved"
CLOSED = "Closed"
STATUSES: tuple[str, ...] = (NEW, ASSIGNED, IN_PROGRESS, ON_HOLD,
                             RESOLVED, CLOSED)
OPEN_STATUSES: tuple[str, ...] = (NEW, ASSIGNED, IN_PROGRESS, ON_HOLD)

COMMENT = "Comment"
INTERNAL = "Internal note"
STATUS_CHANGE = "Status"
ASSIGNMENT = "Assignment"
UPDATE_KINDS: tuple[str, ...] = (COMMENT, INTERNAL, STATUS_CHANGE,
                                 ASSIGNMENT)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS helpdesk_tickets (
    ticket_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    kind               TEXT NOT NULL,
    category           TEXT NOT NULL,
    title              TEXT NOT NULL,
    description        TEXT,
    location           TEXT,
    resource_id        INTEGER,
    asset_id           INTEGER,
    asset_tag          TEXT,
    priority           TEXT NOT NULL DEFAULT 'Medium',
    status             TEXT NOT NULL DEFAULT 'New',
    raised_by          TEXT NOT NULL,
    raised_by_staff_id TEXT,
    raised_by_name     TEXT,
    contact            TEXT,
    assignee_staff_id  TEXT,
    assignee_name      TEXT,
    raised_at          TEXT NOT NULL,
    sla_due_at         TEXT NOT NULL,
    hold_started_at    TEXT,
    hold_reason        TEXT,
    held_seconds       INTEGER NOT NULL DEFAULT 0,
    first_response_at  TEXT,
    resolved_at        TEXT,
    resolved_by        TEXT,
    resolution         TEXT,
    closed_at          TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    updated_at         TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (resource_id) REFERENCES rb_resources(resource_id)
        ON DELETE SET NULL,
    FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
        ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS helpdesk_updates (
    update_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id   INTEGER NOT NULL,
    at          TEXT NOT NULL,
    author      TEXT,
    kind        TEXT NOT NULL DEFAULT 'Comment',
    body        TEXT NOT NULL,
    FOREIGN KEY (ticket_id) REFERENCES helpdesk_tickets(ticket_id)
);

CREATE INDEX IF NOT EXISTS idx_hd_status   ON helpdesk_tickets(status);
CREATE INDEX IF NOT EXISTS idx_hd_raiser   ON helpdesk_tickets(raised_by);
CREATE INDEX IF NOT EXISTS idx_hd_assignee
    ON helpdesk_tickets(assignee_staff_id);
CREATE INDEX IF NOT EXISTS idx_hd_sla      ON helpdesk_tickets(sla_due_at);
CREATE INDEX IF NOT EXISTS idx_hd_updates  ON helpdesk_updates(ticket_id);
"""


class ValidationError(ValueError):
    pass


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Ticket:
    ticket_id: int
    kind: str
    category: str
    title: str
    description: str | None
    location: str | None
    resource_id: int | None
    asset_id: int | None
    asset_tag: str | None
    priority: str
    status: str
    raised_by: str
    raised_by_staff_id: str | None
    raised_by_name: str | None
    contact: str | None
    assignee_staff_id: str | None
    assignee_name: str | None
    raised_at: str
    sla_due_at: str
    hold_started_at: str | None
    hold_reason: str | None
    held_seconds: int
    first_response_at: str | None
    resolved_at: str | None
    resolved_by: str | None
    resolution: str | None
    closed_at: str | None
    created_at: str
    updated_at: str

    @property
    def reference(self) -> str:
        return f"HD{self.ticket_id:05d}"

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES

    def is_overdue(self, now: str | None = None) -> bool:
        """Open, not on hold, and past its SLA due time."""
        if not self.is_open or self.status == ON_HOLD:
            return False
        return self.sla_due_at < (now or _now())

    @property
    def resolution_hours(self) -> float | None:
        if not self.resolved_at:
            return None
        try:
            a = _dt.datetime.fromisoformat(self.raised_at)
            b = _dt.datetime.fromisoformat(self.resolved_at)
        except ValueError:
            return None
        return round((b - a).total_seconds() / 3600, 1)

    @property
    def met_sla(self) -> bool | None:
        if not self.resolved_at:
            return None
        return self.resolved_at <= self.sla_due_at


@dataclass
class Update:
    update_id: int
    ticket_id: int
    at: str
    author: str | None
    kind: str
    body: str


@dataclass
class HelpdeskSummary:
    open_tickets: int = 0
    overdue: int = 0
    on_hold: int = 0
    unassigned: int = 0
    resolved_in_period: int = 0
    sla_met_in_period: int = 0
    avg_resolution_hours: float | None = None
    by_status: dict[str, int] = field(default_factory=dict)
    open_by_category: dict[str, int] = field(default_factory=dict)
    open_by_assignee: dict[str, int] = field(default_factory=dict)
    open_by_priority: dict[str, int] = field(default_factory=dict)


# ── DB plumbing ─────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[_sql.Connection]:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(str(DB_PATH))
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    # FK targets first: bookable rooms and the asset register.
    from education_system.systems.sixth_form.domain.academics.room_booking import (
        room_booking as _rooms,
    )
    from education_system.systems.sixth_form.domains.operations.domain.assets import (
        assets as _assets,
    )
    _rooms.init_db()
    _assets.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
    logger.debug("Helpdesk schema ready at %s", DB_PATH)
    _DB_READY = True


def _ticket(r: _sql.Row) -> Ticket:
    return Ticket(**{k: r[k] for k in Ticket.__dataclass_fields__})


def _update(r: _sql.Row) -> Update:
    return Update(**{k: r[k] for k in Update.__dataclass_fields__})


# ── Helpers ─────────────────────────────────────────────────────────

def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _text(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _require(v: Any, label: str) -> str:
    s = _text(v)
    if not s:
        raise ValidationError(f"{label} is required")
    return s


def _choice(v: Any, options: tuple[str, ...], label: str,
            default: str | None = None) -> str:
    s = _text(v) or default
    for o in options:
        if s and s.lower() == o.lower():
            return o
    raise ValidationError(f"{label} must be one of: {', '.join(options)}")


def sla_due(raised_at: str, priority: str) -> str:
    start = _dt.datetime.fromisoformat(raised_at)
    hours = SLA_HOURS[_choice(priority, PRIORITIES, "Priority")]
    return (start + _dt.timedelta(hours=hours)).isoformat(timespec="seconds")


def _me() -> access.Principal:
    p = access.current()
    if not (p.is_staff or p.can(access.OPERATIONS)):
        raise access.AccessDenied(
            "Only staff can use the site & IT helpdesk.")
    return p


def can_manage(p: access.Principal | None = None) -> bool:
    return (p or access.current()).can(access.OPERATIONS)


def _is_mine(t: Ticket, p: access.Principal) -> bool:
    if p.username and t.raised_by.lower() == p.username.lower():
        return True
    return bool(p.staff_id) and p.staff_id in (t.raised_by_staff_id,
                                               t.assignee_staff_id)


def _can_see(t: Ticket, p: access.Principal) -> bool:
    return can_manage(p) or _is_mine(t, p)


def _staff_label(staff_id: str) -> tuple[str, str]:
    from education_system.systems.sixth_form.domain.staff import (
        staff as _staff,
    )
    s = _staff.get_staff(staff_id)
    if s is None:
        raise ValidationError(f"No staff member with id {staff_id}")
    return s.staff_id, s.full_name


def _resource(resource_id: Any) -> tuple[int | None, str | None]:
    if resource_id in (None, ""):
        return None, None
    from education_system.systems.sixth_form.domain.academics.room_booking import (
        room_booking as _rooms,
    )
    try:
        rid = int(resource_id)
    except (TypeError, ValueError):
        raise ValidationError("Room must be a room id") from None
    r = _rooms.get_resource(rid)
    if r is None:
        raise ValidationError(f"No room / resource #{rid}")
    where = r.name + (f" ({r.location})" if r.location else "")
    return rid, where


def _asset(asset_id: Any) -> tuple[int | None, str | None]:
    if asset_id in (None, ""):
        return None, None
    from education_system.systems.sixth_form.domains.operations.domain.assets import (
        assets as _assets,
    )
    a = None
    try:
        a = _assets.get_asset(int(asset_id))
    except (TypeError, ValueError):
        a = _assets.get_by_tag(str(asset_id).strip())
    if a is None:
        raise ValidationError(f"No asset '{asset_id}' in the asset register")
    return a.asset_id, a.asset_tag


def room_options() -> list[tuple[int, str]]:
    """Bookable rooms (id, label) for pick lists."""
    from education_system.systems.sixth_form.domain.academics.room_booking import (
        room_booking as _rooms,
    )
    return [(r.resource_id, r.name + (f" ({r.location})" if r.location
                                      else ""))
            for r in _rooms.list_resources(active_only=True)]


def asset_options() -> list[tuple[int, str]]:
    """Assets still in service (id, label) for pick lists."""
    from education_system.systems.sixth_form.domains.operations.domain.assets import (
        assets as _assets,
    )
    return [(a.asset_id, f"{a.asset_tag} — {a.name}"
             + (f" ({a.room or a.location})" if (a.room or a.location)
                else ""))
            for a in _assets.list_assets()
            if a.status not in _assets.DISPOSED_STATUSES]


def _log(conn: _sql.Connection, ticket_id: int, kind: str, body: str,
         author: str | None) -> None:
    conn.execute(
        "INSERT INTO helpdesk_updates (ticket_id, at, author, kind, body) "
        "VALUES (?, ?, ?, ?, ?)",
        (ticket_id, _now(), author, kind, body))


def _who(p: access.Principal) -> str:
    return p.staff_name or p.username or "unknown"


# ── Raising and reading ─────────────────────────────────────────────

def raise_ticket(payload: dict[str, Any]) -> Ticket:
    """Report a fault. Any staff login; the raiser is the signed-in user."""
    init_db()
    p = _me()
    kind = _choice(payload.get("kind"), KINDS, "Type", SITE)
    category = _choice(payload.get("category"), CATEGORIES[kind],
                       f"{kind} category", "Other")
    title = _require(payload.get("title"), "Summary")
    if len(title) > 200:
        raise ValidationError("Summary must be 200 characters or fewer")
    rid, room_label = _resource(payload.get("resource_id"))
    aid, tag = _asset(payload.get("asset_id"))
    location = _text(payload.get("location")) or room_label
    if not location and kind == SITE:
        raise ValidationError("Say where the problem is (location or room)")
    priority = _choice(payload.get("priority"), PRIORITIES, "Priority",
                       DEFAULT_PRIORITY)
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO helpdesk_tickets (kind, category, title, "
            "description, location, resource_id, asset_id, asset_tag, "
            "priority, status, raised_by, raised_by_staff_id, "
            "raised_by_name, contact, raised_at, sla_due_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (kind, category, title, _text(payload.get("description")),
             location, rid, aid, tag, priority, NEW,
             p.username or "unknown", p.staff_id, p.staff_name,
             _text(payload.get("contact")), now, sla_due(now, priority)))
        new_id = cur.lastrowid
        _log(conn, new_id, STATUS_CHANGE, f"Raised ({priority})", _who(p))
    logger.info("Helpdesk ticket #%d raised by %s (%s / %s)", new_id,
                p.username, kind, category)
    return get_ticket(new_id)


def get_ticket(ticket_id: int) -> Ticket:
    """One ticket, if the signed-in user may see it."""
    init_db()
    p = _me()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM helpdesk_tickets WHERE ticket_id=?",
                         (int(ticket_id),)).fetchone()
    if r is None:
        raise ValidationError(f"No helpdesk ticket #{ticket_id}")
    t = _ticket(r)
    if not _can_see(t, p):
        raise access.AccessDenied("You can only see tickets you raised "
                                  "or that are assigned to you.")
    return t


def list_tickets(*, mine: bool = False, kind: str | None = None,
                 category: str | None = None, status: str | None = None,
                 priority: str | None = None,
                 assignee_staff_id: str | None = None,
                 open_only: bool = False, overdue_only: bool = False,
                 unassigned_only: bool = False,
                 search: str | None = None) -> list[Ticket]:
    """Tickets the signed-in user may see. Without ``OPERATIONS`` (or
    with ``mine=True``) that is the tickets they raised or hold."""
    init_db()
    p = _me()
    clauses: list[str] = []
    args: list[Any] = []
    if mine or not can_manage(p):
        own = ["LOWER(raised_by) = LOWER(?)"]
        args.append(p.username or "")
        if p.staff_id:
            own += ["raised_by_staff_id = ?", "assignee_staff_id = ?"]
            args += [p.staff_id, p.staff_id]
        clauses.append("(" + " OR ".join(own) + ")")
    if kind:
        clauses.append("kind = ?")
        args.append(_choice(kind, KINDS, "Type"))
    if category:
        clauses.append("category = ?")
        args.append(category.strip())
    if status:
        clauses.append("status = ?")
        args.append(_choice(status, STATUSES, "Status"))
    if priority:
        clauses.append("priority = ?")
        args.append(_choice(priority, PRIORITIES, "Priority"))
    if assignee_staff_id:
        clauses.append("assignee_staff_id = ?")
        args.append(assignee_staff_id.strip())
    if open_only or overdue_only or unassigned_only:
        clauses.append("status IN (%s)" % ",".join("?" * len(OPEN_STATUSES)))
        args += list(OPEN_STATUSES)
    if unassigned_only:
        clauses.append("assignee_staff_id IS NULL")
    if search:
        clauses.append("(title LIKE ? OR description LIKE ? "
                       "OR location LIKE ? OR asset_tag LIKE ?)")
        args += [f"%{search.strip()}%"] * 4
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    order = (" ORDER BY CASE WHEN status IN ('Resolved','Closed') THEN 1 "
             "ELSE 0 END, sla_due_at, ticket_id")
    with _connect() as conn:
        rows = [_ticket(r) for r in conn.execute(
            f"SELECT * FROM helpdesk_tickets{where}{order}",  # DBW001: clauses are literals; values are bound
            args).fetchall()]
    if overdue_only:
        now = _now()
        rows = [t for t in rows if t.is_overdue(now)]
    return rows


def list_updates(ticket_id: int) -> list[Update]:
    """A ticket's history. Internal notes are shown to the team only."""
    t = get_ticket(ticket_id)
    with _connect() as conn:
        rows = [_update(r) for r in conn.execute(
            "SELECT * FROM helpdesk_updates WHERE ticket_id=? "
            "ORDER BY at, update_id", (t.ticket_id,)).fetchall()]
    if not can_manage():
        rows = [u for u in rows if u.kind != INTERNAL]
    return rows


# ── Working a ticket ────────────────────────────────────────────────

def _require_manage(action: str) -> access.Principal:
    p = _me()
    p.require(access.OPERATIONS, action)
    return p


def add_comment(ticket_id: int, body: str, *,
                internal: bool = False) -> Update:
    """Comment on a ticket you can see; internal notes are team-only."""
    t = get_ticket(ticket_id)
    p = _me()
    text = _require(body, "Comment")
    if internal:
        p.require(access.OPERATIONS, "internal helpdesk notes")
    with _connect() as conn:
        _log(conn, t.ticket_id, INTERNAL if internal else COMMENT, text,
             _who(p))
        if can_manage(p) and not _is_mine(t, p) and not t.first_response_at:
            conn.execute("UPDATE helpdesk_tickets SET first_response_at=?, "
                         "updated_at=datetime('now') WHERE ticket_id=?",
                         (_now(), t.ticket_id))
        uid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        r = conn.execute("SELECT * FROM helpdesk_updates WHERE update_id=?",
                         (uid,)).fetchone()
    return _update(r)


def assign(ticket_id: int, staff_id: str | None) -> Ticket:
    """Give the ticket to a member of staff (None = unassign)."""
    p = _require_manage("assign helpdesk tickets")
    t = get_ticket(ticket_id)
    if not t.is_open:
        raise ValidationError(f"{t.reference} is {t.status} — reopen it "
                              "first")
    sid, name = _staff_label(staff_id) if _text(staff_id) else (None, None)
    status = t.status
    if sid and t.status == NEW:
        status = ASSIGNED
    elif not sid and t.status == ASSIGNED:
        status = NEW
    now = _now()
    with _connect() as conn:
        conn.execute(
            "UPDATE helpdesk_tickets SET assignee_staff_id=?, "
            "assignee_name=?, status=?, "
            "first_response_at=COALESCE(first_response_at, ?), "
            "updated_at=datetime('now') WHERE ticket_id=?",
            (sid, name, status, now if sid else None, t.ticket_id))
        _log(conn, t.ticket_id, ASSIGNMENT,
             f"Assigned to {name}" if sid else "Unassigned", _who(p))
    return get_ticket(t.ticket_id)


def set_priority(ticket_id: int, priority: str) -> Ticket:
    """Re-prioritise; the SLA is recalculated from when it was raised."""
    p = _require_manage("re-prioritise helpdesk tickets")
    t = get_ticket(ticket_id)
    pr = _choice(priority, PRIORITIES, "Priority")
    if pr == t.priority:
        return t
    held = _held_seconds_so_far(t)
    due = _dt.datetime.fromisoformat(sla_due(t.raised_at, pr))
    due += _dt.timedelta(seconds=t.held_seconds + held)
    with _connect() as conn:
        conn.execute(
            "UPDATE helpdesk_tickets SET priority=?, sla_due_at=?, "
            "updated_at=datetime('now') WHERE ticket_id=?",
            (pr, due.isoformat(timespec="seconds"), t.ticket_id))
        _log(conn, t.ticket_id, STATUS_CHANGE,
             f"Priority {t.priority} → {pr}", _who(p))
    return get_ticket(t.ticket_id)


def _held_seconds_so_far(t: Ticket) -> int:
    if t.status != ON_HOLD or not t.hold_started_at:
        return 0
    start = _dt.datetime.fromisoformat(t.hold_started_at)
    return max(0, int((_dt.datetime.now() - start).total_seconds()))


def set_status(ticket_id: int, status: str, *,
               note: str | None = None) -> Ticket:
    """Move a ticket through New / Assigned / In progress / On hold.

    Resolving and closing go through :func:`resolve` and :func:`close`
    because they need a resolution. Putting a ticket on hold needs a
    reason; taking it off hold extends the SLA by the time held.
    """
    p = _require_manage("update helpdesk tickets")
    t = get_ticket(ticket_id)
    new = _choice(status, STATUSES, "Status")
    if new in (RESOLVED, CLOSED):
        raise ValidationError("Use Resolve / Close — they need a "
                              "resolution")
    if not t.is_open:
        raise ValidationError(f"{t.reference} is {t.status} — reopen it "
                              "first")
    if new == t.status:
        return t
    if new == ASSIGNED and not t.assignee_staff_id:
        raise ValidationError("Assign the ticket to someone first")
    reason = _text(note)
    if new == ON_HOLD and not reason:
        raise ValidationError("Give a reason for putting it on hold "
                              "(e.g. waiting for a part)")
    sets = ["status=?", "updated_at=datetime('now')",
            "first_response_at=COALESCE(first_response_at, ?)"]
    args: list[Any] = [new, _now()]
    line = f"{t.status} → {new}"
    if new == ON_HOLD:
        sets += ["hold_started_at=?", "hold_reason=?"]
        args += [_now(), reason]
        line = f"On hold: {reason}"
    elif t.status == ON_HOLD:
        held = _held_seconds_so_far(t)
        due = (_dt.datetime.fromisoformat(t.sla_due_at)
               + _dt.timedelta(seconds=held))
        sets += ["hold_started_at=NULL", "hold_reason=NULL",
                 "sla_due_at=?", "held_seconds=held_seconds+?"]
        args += [due.isoformat(timespec="seconds"), held]
        line = (f"Off hold after {held // 60} min → {new}; SLA now "
                f"{due.isoformat(timespec='minutes')}")
    if reason and new != ON_HOLD:
        line += f" — {reason}"
    with _connect() as conn:
        conn.execute(
            f"UPDATE helpdesk_tickets SET {', '.join(sets)} "  # DBW001: column list is literal
            "WHERE ticket_id=?", (*args, t.ticket_id))
        _log(conn, t.ticket_id, STATUS_CHANGE, line, _who(p))
    return get_ticket(t.ticket_id)


def resolve(ticket_id: int, resolution: str, *,
            log_asset_repair: bool = False,
            repair_cost: float | None = None) -> Ticket:
    """Record the fix. With ``log_asset_repair`` and a linked asset, a
    Repair entry goes into the asset's maintenance log."""
    p = _require_manage("resolve helpdesk tickets")
    t = get_ticket(ticket_id)
    if not t.is_open:
        raise ValidationError(f"{t.reference} is already {t.status}")
    text = _require(resolution, "Resolution")
    now = _now()
    sla_extra = _held_seconds_so_far(t)
    due = t.sla_due_at
    if sla_extra:
        due = (_dt.datetime.fromisoformat(t.sla_due_at)
               + _dt.timedelta(seconds=sla_extra)).isoformat(
                   timespec="seconds")
    if log_asset_repair:
        if not t.asset_id:
            raise ValidationError("This ticket has no asset to log the "
                                  "repair against")
        from education_system.systems.sixth_form.domains.operations.domain.assets import (
            assets as _assets,
        )
        _assets.add_maintenance(t.asset_id, {
            "service_date": now[:10], "service_type": "Repair",
            "performed_by": t.assignee_name or _who(p),
            "staff_id": t.assignee_staff_id or p.staff_id,
            "cost": repair_cost, "outcome": "Completed",
            "notes": f"Helpdesk {t.reference}: {text}"[:1000]})
    with _connect() as conn:
        conn.execute(
            "UPDATE helpdesk_tickets SET status=?, resolution=?, "
            "resolved_at=?, resolved_by=?, sla_due_at=?, "
            "held_seconds=held_seconds+?, "
            "hold_started_at=NULL, hold_reason=NULL, "
            "first_response_at=COALESCE(first_response_at, ?), "
            "updated_at=datetime('now') WHERE ticket_id=?",
            (RESOLVED, text, now, _who(p), due, sla_extra, now, t.ticket_id))
        _log(conn, t.ticket_id, STATUS_CHANGE, f"Resolved: {text}", _who(p))
    logger.info("Helpdesk %s resolved by %s", t.reference, p.username)
    return get_ticket(t.ticket_id)


def close(ticket_id: int, *, resolution: str | None = None) -> Ticket:
    """Close a ticket. The raiser may close their own resolved ticket
    (confirming the fix); the team may close any, but an unresolved one
    needs a resolution (duplicate, raised in error, …)."""
    t = get_ticket(ticket_id)
    p = _me()
    if t.status == CLOSED:
        raise ValidationError(f"{t.reference} is already closed")
    manage = can_manage(p)
    if not manage and not (_is_mine(t, p) and t.status == RESOLVED):
        raise access.AccessDenied("You can close your own ticket once it "
                                  "has been resolved.")
    text = _text(resolution)
    if t.status != RESOLVED and not text:
        raise ValidationError("Say why it is being closed unresolved")
    now = _now()
    with _connect() as conn:
        conn.execute(
            "UPDATE helpdesk_tickets SET status=?, closed_at=?, "
            "resolution=COALESCE(resolution, ?), "
            "resolved_at=COALESCE(resolved_at, ?), "
            "resolved_by=COALESCE(resolved_by, ?), "
            "hold_started_at=NULL, hold_reason=NULL, "
            "updated_at=datetime('now') WHERE ticket_id=?",
            (CLOSED, now, text, now, _who(p), t.ticket_id))
        _log(conn, t.ticket_id, STATUS_CHANGE,
             "Closed" + (f": {text}" if text else " (fix confirmed)"),
             _who(p))
    return get_ticket(t.ticket_id)


def reopen(ticket_id: int, reason: str) -> Ticket:
    """Back into the queue — the fix did not hold. Raiser or team."""
    t = get_ticket(ticket_id)
    p = _me()
    if t.is_open:
        raise ValidationError(f"{t.reference} is still open")
    if not (can_manage(p) or _is_mine(t, p)):
        raise access.AccessDenied("Only the person who raised it or the "
                                  "site / IT team can reopen a ticket.")
    why = _require(reason, "Reason for reopening")
    status = IN_PROGRESS if t.assignee_staff_id else NEW
    now = _now()
    with _connect() as conn:
        conn.execute(
            "UPDATE helpdesk_tickets SET status=?, resolved_at=NULL, "
            "resolved_by=NULL, closed_at=NULL, resolution=NULL, "
            "held_seconds=0, "
            "sla_due_at=?, updated_at=datetime('now') WHERE ticket_id=?",
            (status, sla_due(now, t.priority), t.ticket_id))
        _log(conn, t.ticket_id, STATUS_CHANGE,
             f"Reopened: {why} (previous resolution: "
             f"{t.resolution or '—'})", _who(p))
    return get_ticket(t.ticket_id)


def update_details(ticket_id: int, payload: dict[str, Any]) -> Ticket:
    """Correct category / summary / location / room / asset. The raiser
    may edit their own ticket while it is New; the team at any time."""
    t = get_ticket(ticket_id)
    p = _me()
    if not (can_manage(p) or (_is_mine(t, p) and t.status == NEW)):
        raise access.AccessDenied("Only the site / IT team can edit a "
                                  "ticket once it is being worked on.")
    kind = _choice(payload.get("kind", t.kind), KINDS, "Type")
    category = _choice(payload.get("category", t.category),
                       CATEGORIES[kind], f"{kind} category", "Other")
    title = _require(payload.get("title", t.title), "Summary")
    rid, room_label = (_resource(payload["resource_id"])
                       if "resource_id" in payload
                       else (t.resource_id, None))
    aid, tag = (_asset(payload["asset_id"]) if "asset_id" in payload
                else (t.asset_id, t.asset_tag))
    location = (_text(payload.get("location", t.location)) or room_label
                or t.location)
    with _connect() as conn:
        conn.execute(
            "UPDATE helpdesk_tickets SET kind=?, category=?, title=?, "
            "description=?, location=?, resource_id=?, asset_id=?, "
            "asset_tag=?, contact=?, updated_at=datetime('now') "
            "WHERE ticket_id=?",
            (kind, category, title,
             _text(payload.get("description", t.description)), location,
             rid, aid, tag, _text(payload.get("contact", t.contact)),
             t.ticket_id))
        _log(conn, t.ticket_id, STATUS_CHANGE, "Details edited", _who(p))
    if "priority" in payload and payload["priority"] != t.priority:
        return set_priority(t.ticket_id, payload["priority"])
    return get_ticket(t.ticket_id)


# ── Reports ─────────────────────────────────────────────────────────

def overdue(*, kind: str | None = None) -> list[Ticket]:
    """Open tickets past their SLA (on-hold tickets excluded)."""
    _require_manage("helpdesk reports")
    return list_tickets(kind=kind, overdue_only=True)


def open_by_category(*, kind: str | None = None
                     ) -> list[tuple[str, str, int, int]]:
    """``(kind, category, open, overdue)`` rows, busiest first."""
    _require_manage("helpdesk reports")
    now = _now()
    counts: dict[tuple[str, str], list[int]] = {}
    for t in list_tickets(kind=kind, open_only=True):
        c = counts.setdefault((t.kind, t.category), [0, 0])
        c[0] += 1
        c[1] += 1 if t.is_overdue(now) else 0
    return sorted(((k, cat, n, o) for (k, cat), (n, o) in counts.items()),
                  key=lambda r: (-r[2], r[0], r[1]))


def sla_performance(*, date_from: str | None = None,
                    date_to: str | None = None
                    ) -> list[tuple[str, int, int, float | None]]:
    """``(priority, resolved, met SLA, average hours)`` for tickets
    resolved between the dates (inclusive, YYYY-MM-DD)."""
    _require_manage("helpdesk reports")
    for d, label in ((date_from, "From"), (date_to, "To")):
        if d:
            try:
                _dt.date.fromisoformat(d)
            except ValueError:
                raise ValidationError(f"{label} must be YYYY-MM-DD") from None
    out = []
    rows = [t for t in list_tickets() if t.resolved_at
            and (not date_from or t.resolved_at[:10] >= date_from)
            and (not date_to or t.resolved_at[:10] <= date_to)]
    for pr in PRIORITIES:
        mine = [t for t in rows if t.priority == pr]
        hours = [t.resolution_hours for t in mine
                 if t.resolution_hours is not None]
        out.append((pr, len(mine), sum(1 for t in mine if t.met_sla),
                    round(sum(hours) / len(hours), 1) if hours else None))
    return out


def summary(*, period_days: int = 30) -> HelpdeskSummary:
    """Queue picture for the team; for other staff, their own tickets."""
    init_db()
    out = HelpdeskSummary(by_status={s: 0 for s in STATUSES})
    now = _now()
    since = (_dt.date.today() - _dt.timedelta(days=period_days)).isoformat()
    hours: list[float] = []
    for t in list_tickets():
        out.by_status[t.status] += 1
        if t.resolved_at and t.resolved_at[:10] >= since:
            out.resolved_in_period += 1
            out.sla_met_in_period += 1 if t.met_sla else 0
            if t.resolution_hours is not None:
                hours.append(t.resolution_hours)
        if not t.is_open:
            continue
        out.open_tickets += 1
        out.overdue += 1 if t.is_overdue(now) else 0
        out.on_hold += 1 if t.status == ON_HOLD else 0
        out.unassigned += 0 if t.assignee_staff_id else 1
        key = f"{t.kind}: {t.category}"
        out.open_by_category[key] = out.open_by_category.get(key, 0) + 1
        who = t.assignee_name or "(unassigned)"
        out.open_by_assignee[who] = out.open_by_assignee.get(who, 0) + 1
        out.open_by_priority[t.priority] = (
            out.open_by_priority.get(t.priority, 0) + 1)
    if hours:
        out.avg_resolution_hours = round(sum(hours) / len(hours), 1)
    return out
