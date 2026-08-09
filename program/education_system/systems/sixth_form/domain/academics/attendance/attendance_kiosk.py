"""Kiosk and QR self check-in for Sixth Form Attendance.

Sibling to :mod:`attendance`. A register taken by a teacher reading
names off a screen costs five minutes of every lesson. A terminal by the
door that a learner taps a card against costs none, and it timestamps
the arrival properly instead of guessing at it.

Three things live here:

* **Devices** — the terminals themselves. Each has a name, usually a
  room, and a key it presents so a register cannot be written by
  anything that merely knows the URL. A device in ``entrance`` mode
  records arrival *on site* rather than at a lesson, which is what
  :mod:`attendance_rollcall` reads when the alarm goes off.
* **Tokens** — what the learner presents: a card number, a printed QR
  badge, a code in the portal. Tokens are revocable and expire, because
  cards get lost and a lost card that still marks its owner present is
  worse than no card at all.
* **Check-ins** — the event itself. Resolving a tap into a mark means
  answering "which lesson is this person supposed to be in right now",
  which is the timetable, the clock, the A/B week and the room all at
  once.

**Nothing here raises at the doorway.** A queue of learners tapping in
before period 1 is the worst possible place for an exception, so
:func:`check_in` always returns a :class:`CheckIn` carrying an outcome —
marked, already checked in, no lesson, wrong room, unknown card — and
every one of them is logged. What went wrong at the door is answerable
later, and the queue keeps moving.
"""

from __future__ import annotations

import datetime as _dt
import logging
import secrets
import sqlite3
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_codes as codes,
    attendance_register as reg,
    attendance_weeks as weeks,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

# What a terminal is for. A `room` device marks the lesson happening in
# front of it; an `entrance` device records that somebody is in the
# building at all; a `roaming` device (a tablet a tutor carries) marks
# whatever lesson the learner is timetabled into, wherever it is.
ROOM: str = "room"
ENTRANCE: str = "entrance"
ROAMING: str = "roaming"
DEVICE_MODES: tuple[str, ...] = (ROOM, ENTRANCE, ROAMING)

# How a tap is recorded, so a scanned badge and a typed card number stay
# distinguishable in the data source column.
KIND_CARD: str = "card"
KIND_QR: str = "qr"
TOKEN_KINDS: tuple[str, ...] = (KIND_CARD, KIND_QR)

# The outcomes a tap can have. Only `MARKED` and `ON_SITE` write
# anything; the rest exist so the door queue never stalls on an error.
MARKED: str = "Marked"
DUPLICATE: str = "Already checked in"
ON_SITE: str = "On site"
NO_LESSON: str = "No lesson"
WRONG_ROOM: str = "Wrong room"
UNKNOWN_TOKEN: str = "Unknown token"
REVOKED: str = "Token revoked"
EXPIRED: str = "Token expired"
LOCKED: str = "Register submitted"
REFUSED: str = "Refused"
DEVICE_INACTIVE: str = "Device inactive"

OUTCOMES: tuple[str, ...] = (
    MARKED, DUPLICATE, ON_SITE, NO_LESSON, WRONG_ROOM, UNKNOWN_TOKEN,
    REVOKED, EXPIRED, LOCKED, REFUSED, DEVICE_INACTIVE,
)

# How early a learner may tap in for a lesson, and how long after the
# start the terminal keeps accepting. Ten minutes before covers the
# corridor; the lesson end covers a very late arrival, which is still
# worth recording as an arrival rather than as an absence.
EARLY_MINUTES: int = 10

# Minutes past the start before the mark stops being "late but in the
# registration window" (`L`) and becomes `U` — late after the register
# closed, which counts as unauthorised absence.
REGISTER_CLOSES_AFTER: int = 30

# A device that has not been heard from in this long is probably
# unplugged, and its room's registers are probably empty.
STALE_DEVICE_HOURS: int = 24

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_kiosk_devices (
    device_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    room         TEXT,
    mode         TEXT NOT NULL DEFAULT 'room',
    enforce_room INTEGER NOT NULL DEFAULT 1,
    api_key      TEXT NOT NULL,
    active       INTEGER NOT NULL DEFAULT 1,
    location     TEXT,
    last_seen_at TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(name)
);

CREATE TABLE IF NOT EXISTS attendance_kiosk_tokens (
    token      TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    kind       TEXT NOT NULL DEFAULT 'card',
    label      TEXT,
    expires_on TEXT,
    revoked    INTEGER NOT NULL DEFAULT 0,
    revoked_at TEXT,
    issued_by  TEXT,
    issued_at  TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_kiosk_tok_student
    ON attendance_kiosk_tokens(student_id);

CREATE TABLE IF NOT EXISTS attendance_kiosk_events (
    event_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    INTEGER,
    device_name  TEXT,
    token        TEXT,
    student_id   TEXT,
    date         TEXT NOT NULL,
    time         TEXT NOT NULL,
    slot_id      INTEGER,
    outcome      TEXT NOT NULL,
    status       TEXT,
    minutes_late INTEGER,
    detail       TEXT,
    recorded_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_att_kiosk_ev_date
    ON attendance_kiosk_events(date);
CREATE INDEX IF NOT EXISTS idx_att_kiosk_ev_outcome
    ON attendance_kiosk_events(outcome);
CREATE INDEX IF NOT EXISTS idx_att_kiosk_ev_student
    ON attendance_kiosk_events(student_id, date);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Device:
    """One terminal."""

    device_id: int
    name: str
    room: str | None
    mode: str
    enforce_room: bool
    active: bool
    location: str | None
    last_seen_at: str | None
    created_at: str | None
    api_key: str | None = None      # withheld from list reads

    @property
    def is_entrance(self) -> bool:
        return self.mode == ENTRANCE

    @property
    def label(self) -> str:
        where = self.room or self.location or "unplaced"
        return f"{self.name} ({self.mode}, {where})"


@dataclass
class Token:
    """A card or badge belonging to one learner."""

    token: str
    student_id: str
    kind: str
    label: str | None
    expires_on: str | None
    revoked: bool
    revoked_at: str | None
    issued_by: str | None
    issued_at: str | None

    def is_valid(self, *, on: str | None = None) -> bool:
        if self.revoked:
            return False
        if self.expires_on:
            today = on or _dt.date.today().isoformat()
            return self.expires_on >= today
        return True


@dataclass
class CheckIn:
    """The result of one tap. Never an exception."""

    outcome: str
    date: str
    time: str
    student_id: str | None = None
    student_name: str | None = None
    slot_id: int | None = None
    status: str | None = None
    code: str | None = None
    minutes_late: int | None = None
    detail: str | None = None
    event_id: int | None = None

    @property
    def ok(self) -> bool:
        """Whether the tap resulted in something being recorded."""
        return self.outcome in (MARKED, ON_SITE, DUPLICATE)

    @property
    def message(self) -> str:
        """What the terminal should show, in one line."""
        who = self.student_name or self.student_id or "Card"
        if self.outcome == MARKED:
            if self.minutes_late:
                return f"{who} — {self.minutes_late} min late. Go straight in."
            return f"{who} — thank you, you're marked present."
        if self.outcome == DUPLICATE:
            return f"{who} — already checked in for this lesson."
        if self.outcome == ON_SITE:
            return f"{who} — welcome in, {self.time}."
        if self.outcome == NO_LESSON:
            return f"{who} — no lesson timetabled right now."
        if self.outcome == WRONG_ROOM:
            return f"{who} — you're due in another room. {self.detail or ''}".strip()
        if self.outcome in (UNKNOWN_TOKEN, REVOKED, EXPIRED):
            return "Card not recognised — please see reception."
        if self.outcome == LOCKED:
            return f"{who} — that register is already signed off. See staff."
        return self.detail or "Check-in could not be completed."


@dataclass
class DeviceHealth:
    """Whether a terminal is still talking to us."""

    device: Device
    hours_since_seen: float | None
    taps_today: int

    @property
    def stale(self) -> bool:
        return (self.hours_since_seen is None
                or self.hours_since_seen > STALE_DEVICE_HOURS)


@dataclass
class KioskEvent:
    event_id: int
    device_name: str | None
    token: str | None
    student_id: str | None
    date: str
    time: str
    slot_id: int | None
    outcome: str
    status: str | None
    minutes_late: int | None
    detail: str | None
    recorded_at: str | None


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    reg.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Kiosk schema ready at %s", DB_PATH)
    _DB_READY = True


def _now_time() -> str:
    return _dt.datetime.now().strftime("%H:%M")


def _today() -> str:
    return _dt.date.today().isoformat()


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


# ── Devices ─────────────────────────────────────────────────────────

def validate_mode(value: Any) -> str:
    s = (value or "").strip().lower() if isinstance(value, str) else ""
    if not s:
        return ROOM
    if s not in DEVICE_MODES:
        raise ValidationError(
            f"Device mode must be one of: {', '.join(DEVICE_MODES)}")
    return s


def _device_row(r: sqlite3.Row, *, with_key: bool = False) -> Device:
    keys = r.keys()
    return Device(
        device_id=r["device_id"],
        name=r["name"],
        room=r["room"],
        mode=r["mode"],
        enforce_room=bool(r["enforce_room"]),
        active=bool(r["active"]),
        location=r["location"],
        last_seen_at=r["last_seen_at"],
        created_at=r["created_at"] if "created_at" in keys else None,
        api_key=(r["api_key"] if with_key and "api_key" in keys else None),
    )


def register_device(
    name: str,
    *,
    room: str | None = None,
    mode: str = ROOM,
    location: str | None = None,
    enforce_room: bool = True,
    actor: str | None = None,
) -> Device:
    """Enrol a terminal and mint its key.

    The key is returned **once**, on the object this call hands back —
    every later read withholds it. Losing it means
    :func:`rotate_key`, which is the correct amount of friction for a
    credential that can write registers.
    """
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Device name is required")
    if len(name) > 80:
        raise ValidationError("Device name must be 80 characters or fewer")
    mode = validate_mode(mode)
    room = (room or "").strip() or None
    if mode == ROOM and not room:
        raise ValidationError("A room-mode device needs a room")
    key = secrets.token_hex(16)

    with _connect() as conn:
        existing = conn.execute(
            "SELECT device_id FROM attendance_kiosk_devices WHERE name = ?",
            (name,)).fetchone()
        if existing:
            raise ValidationError(f"A device called {name!r} already exists")
        cur = conn.execute(
            """INSERT INTO attendance_kiosk_devices
                   (name, room, mode, enforce_room, api_key, location)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, room, mode, 1 if enforce_room else 0, key,
             (location or "").strip() or None))
        conn.commit()
        device_id = int(cur.lastrowid or 0)
    logger.info("Kiosk device registered: %s (%s, room=%s) by %s",
                name, mode, room or "-", actor or "?")
    out = get_device(device_id, with_key=True)
    assert out is not None
    return out


def get_device(device_id: int, *, with_key: bool = False) -> Device | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_kiosk_devices WHERE device_id = ?",
            (device_id,)).fetchone()
    return _device_row(r, with_key=with_key) if r else None


def device_by_name(name: str, *, with_key: bool = False) -> Device | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_kiosk_devices WHERE name = ?",
            ((name or "").strip(),)).fetchone()
    return _device_row(r, with_key=with_key) if r else None


def list_devices(*, active_only: bool = False,
                 mode: str | None = None) -> list[Device]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if active_only:
        clauses.append("active = 1")
    if mode:
        clauses.append("mode = ?")
        args.append(validate_mode(mode))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_kiosk_devices {where} ORDER BY name",
            args).fetchall()
    return [_device_row(r) for r in rows]


def authenticate(name: str, api_key: str) -> Device:
    """Resolve a terminal from its name and key.

    Compared with :func:`secrets.compare_digest`, because a timing
    difference is still a difference.
    """
    init_db()
    device = device_by_name(name, with_key=True)
    presented = (api_key or "").strip()
    if device is None or not device.api_key or not presented:
        raise ValidationError("Unknown device or key")
    if not secrets.compare_digest(device.api_key, presented):
        logger.warning("Kiosk auth failed for device %r", name)
        raise ValidationError("Unknown device or key")
    if not device.active:
        raise ValidationError(f"Device {device.name} is deactivated")
    touch_device(device.device_id)
    device.api_key = None
    return device


def rotate_key(device_id: int, *, actor: str | None = None) -> Device:
    """Issue a new key, invalidating the old one immediately."""
    init_db()
    if get_device(device_id) is None:
        raise ValidationError(f"No device with id {device_id}")
    key = secrets.token_hex(16)
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_kiosk_devices SET api_key = ? "
            "WHERE device_id = ?", (key, device_id))
        conn.commit()
    logger.info("Rotated key for kiosk device #%d (%s)", device_id, actor or "?")
    out = get_device(device_id, with_key=True)
    assert out is not None
    return out


def set_device_active(device_id: int, active: bool) -> Device:
    init_db()
    if get_device(device_id) is None:
        raise ValidationError(f"No device with id {device_id}")
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_kiosk_devices SET active = ? WHERE device_id = ?",
            (1 if active else 0, device_id))
        conn.commit()
    out = get_device(device_id)
    assert out is not None
    return out


def touch_device(device_id: int) -> None:
    """Record that a device just spoke to us."""
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_kiosk_devices SET last_seen_at = datetime('now') "
            "WHERE device_id = ?", (device_id,))
        conn.commit()


def delete_device(device_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM attendance_kiosk_devices WHERE device_id = ?",
            (device_id,))
        conn.commit()
    return bool(cur.rowcount)


def device_health() -> list[DeviceHealth]:
    """Which terminals have gone quiet.

    The answer to "why is period 3's register empty" is often "the kiosk
    outside R12 has been unplugged since Tuesday", and that is not
    something anyone notices without a list.
    """
    init_db()
    today = _today()
    with _connect() as conn:
        taps = {
            r["device_id"]: r["n"]
            for r in conn.execute(
                "SELECT device_id, COUNT(*) AS n FROM attendance_kiosk_events "
                "WHERE date = ? GROUP BY device_id", (today,)).fetchall()
        }
    now = _dt.datetime.now()
    out: list[DeviceHealth] = []
    for device in list_devices():
        hours: float | None = None
        if device.last_seen_at:
            try:
                seen = _dt.datetime.fromisoformat(device.last_seen_at)
                hours = round((now - seen).total_seconds() / 3600.0, 1)
            except ValueError:              # pragma: no cover - defensive
                hours = None
        out.append(DeviceHealth(device=device, hours_since_seen=hours,
                                taps_today=taps.get(device.device_id, 0)))
    out.sort(key=lambda h: (not h.stale, h.device.name))
    return out


# ── Tokens ──────────────────────────────────────────────────────────

def validate_kind(value: Any) -> str:
    s = (value or "").strip().lower() if isinstance(value, str) else ""
    if not s:
        return KIND_CARD
    if s not in TOKEN_KINDS:
        raise ValidationError(
            f"Token kind must be one of: {', '.join(TOKEN_KINDS)}")
    return s


def _token_row(r: sqlite3.Row) -> Token:
    return Token(
        token=r["token"],
        student_id=r["student_id"],
        kind=r["kind"],
        label=r["label"],
        expires_on=r["expires_on"],
        revoked=bool(r["revoked"]),
        revoked_at=r["revoked_at"],
        issued_by=r["issued_by"],
        issued_at=r["issued_at"],
    )


def issue_token(
    student_id: str,
    *,
    kind: str = KIND_CARD,
    label: str | None = None,
    expires_on: str | None = None,
    token: str | None = None,
    actor: str | None = None,
    revoke_existing: bool = True,
) -> Token:
    """Issue a card or QR badge to a learner.

    Any live token they already hold is revoked by default: a replacement
    card exists precisely because the old one should stop working.
    ``token`` accepts an existing card number so a college with printed
    ID cards can enrol what it already has.
    """
    init_db()
    student_id = (student_id or "").strip()
    if not student_id:
        raise ValidationError("Student ID is required")
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    if _students.get_student(student_id) is None:
        raise ValidationError(f"No student with id {student_id}")
    kind = validate_kind(kind)
    value = (token or "").strip() or secrets.token_urlsafe(12)
    if len(value) > 128:
        raise ValidationError("Token must be 128 characters or fewer")
    if expires_on:
        expires_on = core._validate_date(expires_on)

    if revoke_existing:
        for existing in list_tokens(student_id=student_id, active_only=True):
            revoke_token(existing.token, actor=actor,
                         reason="Replaced by a new token")

    with _connect() as conn:
        clash = conn.execute(
            "SELECT student_id FROM attendance_kiosk_tokens WHERE token = ?",
            (value,)).fetchone()
        if clash:
            raise ValidationError("That token is already in use")
        conn.execute(
            """INSERT INTO attendance_kiosk_tokens
                   (token, student_id, kind, label, expires_on, issued_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (value, student_id, kind, (label or "").strip() or None,
             expires_on, (actor or "").strip() or None))
        conn.commit()
    logger.info("Issued %s token to %s", kind, student_id)
    out = get_token(value)
    assert out is not None
    return out


def get_token(token: str) -> Token | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_kiosk_tokens WHERE token = ?",
            ((token or "").strip(),)).fetchone()
    return _token_row(r) if r else None


def list_tokens(*, student_id: str | None = None,
                active_only: bool = False) -> list[Token]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if active_only:
        clauses.append("revoked = 0")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_kiosk_tokens {where} "
            "ORDER BY issued_at DESC", args).fetchall()
    return [_token_row(r) for r in rows]


def revoke_token(token: str, *, actor: str | None = None,
                 reason: str | None = None) -> bool:
    """Stop a card working. A lost card that still marks its owner
    present is worse than no card at all."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE attendance_kiosk_tokens "
            "SET revoked = 1, revoked_at = datetime('now') "
            "WHERE token = ? AND revoked = 0", ((token or "").strip(),))
        conn.commit()
    if cur.rowcount:
        logger.info("Revoked token for %s (%s)", token[:6] + "…",
                    reason or actor or "no reason given")
    return bool(cur.rowcount)


def resolve_token(token: str, *, on: str | None = None) -> tuple[str | None, str]:
    """Turn a presented token into ``(student_id, outcome)``."""
    entry = get_token(token)
    if entry is None:
        return None, UNKNOWN_TOKEN
    if entry.revoked:
        return entry.student_id, REVOKED
    if not entry.is_valid(on=on):
        return entry.student_id, EXPIRED
    return entry.student_id, MARKED


# ── Working out which lesson this is ────────────────────────────────

def current_slot_for(
    student_id: str,
    *,
    date: str | None = None,
    at_time: str | None = None,
    room: str | None = None,
) -> int | None:
    """The lesson a learner is due in at a given moment.

    Their timetable, narrowed to the weekday, then to the A/B week, then
    to the slots whose window contains the time — with a grace period at
    the front so tapping in on the way is not punished. When two slots
    overlap (they should not, but timetables are made by people), the
    one that started most recently wins.
    """
    date = core._validate_date(date or _today())
    at_time = reg._validate_time(at_time or _now_time(), "Time")
    day = _dt.date.fromisoformat(date).weekday() + 1

    slots = [s for s in tt.list_slots(student_id=student_id) if s.day == day]
    slots = weeks.filter_slots(slots, date)
    if room:
        target = room.strip().lower()
        in_room = [s for s in slots if (s.room or "").strip().lower() == target]
        slots = in_room or slots

    now = _minutes(at_time)
    candidates: list[tuple[int, int]] = []
    for slot in slots:
        start, end = reg.slot_window(slot.slot_id)
        if _minutes(start) - EARLY_MINUTES <= now <= _minutes(end):
            candidates.append((_minutes(start), slot.slot_id))
    if not candidates:
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def _room_for_slot(slot_id: int) -> str | None:
    slot = tt.get_slot(slot_id)
    return slot.room if slot else None


def _student_name(student_id: str) -> str | None:
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student(student_id)
    return student.full_name if student else None


def code_for_arrival(minutes_late: int) -> str:
    """Which mark an arrival earns.

    On time is `/`; late within the registration window is `L`, which
    still counts as present; late after it closes is `U`, which is a
    present learner and an unauthorised absence at the same time. That
    is not a contradiction — it is the sector's way of saying "here, but
    not in time to count".
    """
    if minutes_late <= 0:
        return "/"
    return "L" if minutes_late <= REGISTER_CLOSES_AFTER else "U"


# ── The tap ─────────────────────────────────────────────────────────

def _log_event(
    *,
    device: Device | None,
    token: str | None,
    student_id: str | None,
    date: str,
    at_time: str,
    slot_id: int | None,
    outcome: str,
    status: str | None = None,
    minutes_late: int | None = None,
    detail: str | None = None,
) -> int:
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_kiosk_events
                   (device_id, device_name, token, student_id, date, time,
                    slot_id, outcome, status, minutes_late, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (device.device_id if device else None,
             device.name if device else None,
             token, student_id, date, at_time, slot_id, outcome, status,
             minutes_late, detail))
        conn.commit()
        return int(cur.lastrowid or 0)


def _stamp_arrival(slot_id: int, student_id: str, date: str,
                   at_time: str) -> None:
    """Write the arrival clock time onto an existing mark.

    ``save_register`` owns the mark, its code and its audit trail but
    does not carry the clock columns; rather than duplicate the whole
    upsert here, the row is stamped straight afterwards.
    """
    with _connect() as conn:
        conn.execute(
            "UPDATE attendance_records SET arrival_time = ? "
            "WHERE slot_id = ? AND student_id = ? AND date = ?",
            (at_time, slot_id, student_id, date))
        conn.commit()


def check_in(
    token: str,
    *,
    device: Device | str | None = None,
    date: str | None = None,
    at_time: str | None = None,
    source: str | None = None,
) -> CheckIn:
    """Handle one tap. Always returns; never raises.

    ``device`` may be a :class:`Device`, a device name, or nothing at
    all (a check-in from the portal, with no terminal involved).
    """
    init_db()
    date = core._validate_date(date or _today())
    try:
        at_time = reg._validate_time(at_time or _now_time(), "Time")
    except ValidationError:
        at_time = _now_time()

    if isinstance(device, str):
        device = device_by_name(device)
    if device is not None:
        if not device.active:
            event = _log_event(device=device, token=token, student_id=None,
                               date=date, at_time=at_time, slot_id=None,
                               outcome=DEVICE_INACTIVE)
            return CheckIn(outcome=DEVICE_INACTIVE, date=date, time=at_time,
                           event_id=event,
                           detail=f"Device {device.name} is deactivated")
        touch_device(device.device_id)

    student_id, verdict = resolve_token(token, on=date)
    if verdict != MARKED:
        event = _log_event(device=device, token=token, student_id=student_id,
                           date=date, at_time=at_time, slot_id=None,
                           outcome=verdict)
        return CheckIn(outcome=verdict, date=date, time=at_time,
                       student_id=student_id, event_id=event)
    assert student_id is not None

    return check_in_student(student_id, device=device, date=date,
                            at_time=at_time, token=token, source=source)


def check_in_student(
    student_id: str,
    *,
    device: Device | str | None = None,
    date: str | None = None,
    at_time: str | None = None,
    token: str | None = None,
    source: str | None = None,
) -> CheckIn:
    """The tap, once the learner is known.

    Split out so reception can check somebody in who has forgotten their
    card, without inventing a token for them.
    """
    init_db()
    date = core._validate_date(date or _today())
    at_time = reg._validate_time(at_time or _now_time(), "Time")
    if isinstance(device, str):
        device = device_by_name(device)
    name = _student_name(student_id)

    def event(outcome: str, **kwargs: Any) -> CheckIn:
        event_id = _log_event(device=device, token=token,
                              student_id=student_id, date=date,
                              at_time=at_time,
                              slot_id=kwargs.get("slot_id"),
                              outcome=outcome,
                              status=kwargs.get("status"),
                              minutes_late=kwargs.get("minutes_late"),
                              detail=kwargs.get("detail"))
        return CheckIn(outcome=outcome, date=date, time=at_time,
                       student_id=student_id, student_name=name,
                       event_id=event_id, **kwargs)

    # An entrance terminal is not marking a lesson — it is recording
    # that somebody is in the building, which is what a roll call needs.
    if device is not None and device.is_entrance:
        return event(ON_SITE, detail=device.location or device.name)

    room = device.room if (device and device.mode == ROOM) else None
    slot_id = current_slot_for(student_id, date=date, at_time=at_time,
                               room=room)
    if slot_id is None:
        return event(NO_LESSON,
                     detail=f"No timetabled lesson at {at_time}")

    if room and device is not None and device.enforce_room:
        actual = (_room_for_slot(slot_id) or "").strip().lower()
        if actual and actual != room.strip().lower():
            return event(WRONG_ROOM, slot_id=slot_id,
                         detail=f"Due in {_room_for_slot(slot_id)}")

    existing = core.get_record_for(slot_id, student_id, date)
    if existing is not None and not existing.voided and existing.arrival_time:
        return event(DUPLICATE, slot_id=slot_id, status=existing.status,
                     minutes_late=existing.minutes_late,
                     detail=f"Checked in at {existing.arrival_time}")

    start, _end = reg.slot_window(slot_id)
    late = max(0, _minutes(at_time) - _minutes(start))
    code = code_for_arrival(late)
    status = codes.status_for_code(code)

    try:
        core.save_register(
            slot_id, date,
            {student_id: {"code": code,
                          "status": status,
                          "minutes_late": late or None,
                          "data_source": source or KIND_QR}},
        )
    except ValidationError as e:
        outcome = LOCKED if "submitted" in str(e).lower() else REFUSED
        return event(outcome, slot_id=slot_id, detail=str(e))

    _stamp_arrival(slot_id, student_id, date, at_time)
    logger.info("Kiosk check-in: %s slot #%d at %s (%s)",
                student_id, slot_id, at_time, code)
    result = event(MARKED, slot_id=slot_id, status=status,
                   minutes_late=late or None)
    result.code = code
    return result


# ── Events ──────────────────────────────────────────────────────────

def _event_row(r: sqlite3.Row) -> KioskEvent:
    return KioskEvent(
        event_id=r["event_id"],
        device_name=r["device_name"],
        token=r["token"],
        student_id=r["student_id"],
        date=r["date"],
        time=r["time"],
        slot_id=r["slot_id"],
        outcome=r["outcome"],
        status=r["status"],
        minutes_late=r["minutes_late"],
        detail=r["detail"],
        recorded_at=r["recorded_at"],
    )


def list_events(
    *,
    date: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    student_id: str | None = None,
    outcome: str | None = None,
    device_id: int | None = None,
    limit: int = 200,
) -> list[KioskEvent]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if date:
        clauses.append("date = ?")
        args.append(core._validate_date(date))
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    if student_id:
        clauses.append("student_id = ?")
        args.append(student_id.strip())
    if outcome:
        if outcome not in OUTCOMES:
            raise ValidationError(
                f"Outcome must be one of: {', '.join(OUTCOMES)}")
        clauses.append("outcome = ?")
        args.append(outcome)
    if device_id is not None:
        clauses.append("device_id = ?")
        args.append(device_id)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_kiosk_events {where} "
            "ORDER BY event_id DESC LIMIT ?", args).fetchall()
    return [_event_row(r) for r in rows]


def outcome_breakdown(*, date: str | None = None,
                      date_from: str | None = None,
                      date_to: str | None = None) -> dict[str, int]:
    """Taps by outcome — the health check for the whole scheme."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if date:
        clauses.append("date = ?")
        args.append(core._validate_date(date))
    if date_from:
        clauses.append("date >= ?")
        args.append(core._validate_date(date_from))
    if date_to:
        clauses.append("date <= ?")
        args.append(core._validate_date(date_to))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT outcome, COUNT(*) AS n FROM attendance_kiosk_events "
            f"{where} GROUP BY outcome ORDER BY n DESC", args).fetchall()
    return {r["outcome"]: r["n"] for r in rows}


def unrecognised_cards(*, date_from: str | None = None,
                       date_to: str | None = None,
                       limit: int = 50) -> list[KioskEvent]:
    """Taps that matched no live token.

    A card appearing here repeatedly is either a learner whose
    replacement never got issued or somebody trying it on; both are
    worth knowing.
    """
    return [e for e in list_events(date_from=date_from, date_to=date_to,
                                   limit=limit * 4)
            if e.outcome in (UNKNOWN_TOKEN, REVOKED, EXPIRED)][:limit]


def student_taps(student_id: str, *, date: str | None = None) -> list[KioskEvent]:
    """One learner's taps, for when they insist the machine ate their card."""
    return list_events(student_id=student_id, date=date or _today())
