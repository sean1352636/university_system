"""Offline register capture and sync for Sixth Form Attendance.

Sibling to :mod:`attendance`. Half the rooms in a college have no usable
signal, and the sports hall has none at all. A teacher who cannot take
the register on their phone takes it on paper, and paper reaches the
office on Thursday, if at all.

So a device works from a **bundle** — the roster, the marks that already
exist, and a digest of what the server held at the moment it was packed
(:func:`pack_bundle`). Marks taken offline are **queued** against that
digest (:func:`queue_batch`) and applied when the device gets back in
range (:func:`sync`).

The interesting part is what happens when the world moved on while the
device was away. If the office authorised an absence at 10:05 and the
teacher's phone — which last synced at 09:00 — pushes "absent" at 11:30,
applying it blindly silently undoes the authorisation. That is a
conflict, and this module detects it per learner rather than per
register: one contested learner should not block the other twenty-nine.

Three resolutions, chosen by policy:

* ``server-wins`` — apply everything except the contested learners.
  The right default: the office had newer information.
* ``device-wins`` — apply everything. For when the teacher in the room
  is the one who actually knows.
* ``hold`` — apply nothing, park the batch for a human. For when it
  matters enough that a rule should not decide it.

Idempotency comes from a ``client_uuid`` the device generates. A batch
pushed twice — flaky connection, retried upload — is stored once and
applied once.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from typing import Any

from education_system.systems.sixth_form.domain.academics.attendance import (
    attendance as core,
    attendance_register as reg,
    attendance_weeks as weeks,
    attendance_window as window,
)
from education_system.systems.sixth_form.domain.academics.timetable import (
    timetable as tt,
)
from education_system import paths

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_ATTENDANCE_DB

ValidationError = core.ValidationError


# ── Vocabularies ────────────────────────────────────────────────────

PENDING: str = "Pending"
APPLIED: str = "Applied"
CONFLICT: str = "Conflict"
REJECTED: str = "Rejected"
DISCARDED: str = "Discarded"
STATES: tuple[str, ...] = (PENDING, APPLIED, CONFLICT, REJECTED, DISCARDED)

# What to do when the server has moved on under the device's feet.
SERVER_WINS: str = "server-wins"
DEVICE_WINS: str = "device-wins"
HOLD: str = "hold"
POLICIES: tuple[str, ...] = (SERVER_WINS, DEVICE_WINS, HOLD)
DEFAULT_POLICY: str = SERVER_WINS

# The data source stamped on anything that arrives this way.
SYNC_SOURCE: str = "sync"

# A queued batch older than this was almost certainly captured against a
# world that no longer exists; sync still applies it, but says so.
STALE_BATCH_DAYS: int = 14

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_offline_queue (
    queue_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    client_uuid TEXT NOT NULL UNIQUE,
    device_name TEXT,
    actor       TEXT,
    slot_id     INTEGER NOT NULL,
    date        TEXT NOT NULL,
    payload     TEXT NOT NULL,
    base_digest TEXT,
    captured_at TEXT NOT NULL,
    queued_at   TEXT DEFAULT (datetime('now')),
    state       TEXT NOT NULL DEFAULT 'Pending',
    applied_at  TEXT,
    written     INTEGER NOT NULL DEFAULT 0,
    skipped     INTEGER NOT NULL DEFAULT 0,
    conflicts   TEXT,
    detail      TEXT,
    resolution  TEXT
);

CREATE INDEX IF NOT EXISTS idx_att_offline_state
    ON attendance_offline_queue(state);
CREATE INDEX IF NOT EXISTS idx_att_offline_key
    ON attendance_offline_queue(slot_id, date);
CREATE INDEX IF NOT EXISTS idx_att_offline_device
    ON attendance_offline_queue(device_name);
"""


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class Bundle:
    """What a device takes away with it.

    ``digest`` is the fingerprint of the register as packed. The device
    hands it back on push, and a mismatch is what tells us the server
    changed while it was gone.
    """

    slot_id: int
    date: str
    digest: str
    locked: bool
    group_id: int | None
    room: str | None
    period: int | None
    students: list[dict[str, Any]] = field(default_factory=list)
    packed_at: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "slot_id": self.slot_id, "date": self.date,
            "digest": self.digest, "locked": self.locked,
            "group_id": self.group_id, "room": self.room,
            "period": self.period, "students": self.students,
            "packed_at": self.packed_at,
        }, separators=(",", ":"))


@dataclass
class Conflict:
    """One learner whose mark changed on both sides."""

    student_id: str
    server_status: str | None
    server_code: str | None
    server_recorded_at: str | None
    device_status: str | None
    device_code: str | None

    @property
    def label(self) -> str:
        return (f"{self.student_id}: server {self.server_code or '—'}"
                f"/{self.server_status or '—'} vs device "
                f"{self.device_code or '—'}/{self.device_status or '—'}")


@dataclass
class QueuedBatch:
    """One offline register waiting to be applied."""

    queue_id: int
    client_uuid: str
    device_name: str | None
    actor: str | None
    slot_id: int
    date: str
    payload: dict[str, dict[str, Any]]
    base_digest: str | None
    captured_at: str
    queued_at: str | None
    state: str
    applied_at: str | None
    written: int
    skipped: int
    conflicts: list[Conflict]
    detail: str | None
    resolution: str | None

    @property
    def size(self) -> int:
        return len(self.payload)

    @property
    def is_open(self) -> bool:
        return self.state in (PENDING, CONFLICT)

    @property
    def label(self) -> str:
        return (f"#{self.queue_id} slot #{self.slot_id} {self.date} "
                f"({self.size} mark(s), {self.state})")


@dataclass
class SyncResult:
    """What happened to one batch."""

    queue_id: int
    state: str
    written: int = 0
    skipped: int = 0
    conflicts: list[Conflict] = field(default_factory=list)
    detail: str | None = None

    @property
    def ok(self) -> bool:
        return self.state == APPLIED


@dataclass
class SyncReport:
    """What happened to all of them."""

    processed: int = 0
    applied: int = 0
    held: int = 0
    rejected: int = 0
    written: int = 0
    skipped: int = 0
    results: list[SyncResult] = field(default_factory=list)

    @property
    def conflicts(self) -> list[Conflict]:
        return [c for r in self.results for c in r.conflicts]

    @property
    def summary(self) -> str:
        return (f"{self.processed} batch(es): {self.applied} applied "
                f"({self.written} mark(s)), {self.held} held, "
                f"{self.rejected} rejected")


@dataclass
class DeviceBacklog:
    """How far behind one device is."""

    device_name: str | None
    pending: int
    conflicts: int
    oldest_capture: str | None


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
    logger.debug("Offline-queue schema ready at %s", DB_PATH)
    _DB_READY = True


def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _conflict_row(data: dict[str, Any]) -> Conflict:
    return Conflict(
        student_id=data.get("student_id", ""),
        server_status=data.get("server_status"),
        server_code=data.get("server_code"),
        server_recorded_at=data.get("server_recorded_at"),
        device_status=data.get("device_status"),
        device_code=data.get("device_code"),
    )


def _row(r: sqlite3.Row) -> QueuedBatch:
    return QueuedBatch(
        queue_id=r["queue_id"],
        client_uuid=r["client_uuid"],
        device_name=r["device_name"],
        actor=r["actor"],
        slot_id=r["slot_id"],
        date=r["date"],
        payload=json.loads(r["payload"]),
        base_digest=r["base_digest"],
        captured_at=r["captured_at"],
        queued_at=r["queued_at"],
        state=r["state"],
        applied_at=r["applied_at"],
        written=r["written"],
        skipped=r["skipped"],
        conflicts=[_conflict_row(c) for c in json.loads(r["conflicts"] or "[]")],
        detail=r["detail"],
        resolution=r["resolution"],
    )


# ── Validation ──────────────────────────────────────────────────────

def validate_policy(value: Any) -> str:
    s = (value or "").strip().lower() if isinstance(value, str) else ""
    if not s:
        return DEFAULT_POLICY
    if s not in POLICIES:
        raise ValidationError(
            f"Policy must be one of: {', '.join(POLICIES)}")
    return s


def validate_state(value: Any) -> str:
    s = (value or "").strip() if isinstance(value, str) else ""
    for state in STATES:
        if s.lower() == state.lower():
            return state
    raise ValidationError(f"State must be one of: {', '.join(STATES)}")


def _validate_payload(payload: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict) or not payload:
        raise ValidationError("An offline batch needs at least one mark")
    out: dict[str, dict[str, Any]] = {}
    for sid, values in payload.items():
        key = str(sid).strip()
        if not key:
            raise ValidationError("A mark is missing its student ID")
        if not isinstance(values, dict):
            raise ValidationError(f"{key}: mark must be an object")
        if not (values.get("status") or values.get("code")):
            raise ValidationError(f"{key}: mark needs a status or a code")
        out[key] = dict(values)
    return out


# ── Packing a bundle for the device ─────────────────────────────────

def pack_bundle(slot_id: int, date: str) -> Bundle:
    """Everything a device needs to take this register without a network.

    The digest travels with it. Handing it back on push is what makes
    conflict detection possible at all — without it, a device can only
    say what it wants, never what it was looking at when it decided.
    """
    reg.init_db()
    date = reg._validate_date(date)
    entries = core.register_view(slot_id, date)
    slot = tt.get_slot(slot_id)

    students = [{
        "student_id": e.student_id,
        "full_name": e.full_name,
        "status": e.record.status if e.record else None,
        "code": e.record.code if e.record else None,
        "minutes_late": e.record.minutes_late if e.record else None,
        "notes": e.record.notes if e.record else None,
    } for e in entries]

    return Bundle(
        slot_id=slot_id,
        date=date,
        digest=reg.register_digest(slot_id, date),
        locked=reg.is_locked(slot_id, date),
        group_id=slot.group_id if slot else None,
        room=slot.room if slot else None,
        period=slot.period if slot else None,
        students=students,
        packed_at=_now(),
    )


def pack_day(*, date: str | None = None,
             group_id: int | None = None) -> list[Bundle]:
    """Bundles for every register a device might need today.

    Handed to a teacher heading for the sports hall with a tablet and no
    expectation of signal.
    """
    day_str = reg._validate_date(date or _dt.date.today().isoformat())
    day = _dt.date.fromisoformat(day_str).weekday() + 1
    slots = [s for s in tt.list_slots(group_id=group_id) if s.day == day]
    slots = weeks.filter_slots(slots, day_str)
    return [pack_bundle(slot.slot_id, day_str)
            for slot in sorted(slots, key=lambda s: s.period)]


# ── Queueing ────────────────────────────────────────────────────────

def queue_batch(
    slot_id: int,
    date: str,
    payload: dict[str, dict[str, Any]],
    *,
    client_uuid: str,
    device_name: str | None = None,
    actor: str | None = None,
    base_digest: str | None = None,
    captured_at: str | None = None,
) -> QueuedBatch:
    """Accept a register captured offline.

    Nothing is written to the register here — that is :func:`sync`'s
    job, and keeping the two apart is what lets a device push at a bad
    moment (mid-lesson, mid-migration) without consequence.

    Pushing the same ``client_uuid`` twice returns the batch already
    stored. A device that retries an upload it is not sure landed must
    not be punished with a double application.
    """
    init_db()
    date = reg._validate_date(date)
    key = (client_uuid or "").strip()
    if not key:
        raise ValidationError("A client_uuid is required for an offline batch")
    if len(key) > 100:
        raise ValidationError("client_uuid must be 100 characters or fewer")
    marks = _validate_payload(payload)
    if tt.get_slot(slot_id) is None:
        raise ValidationError(f"No slot with id {slot_id}")

    existing = batch_by_uuid(key)
    if existing is not None:
        logger.info("Offline batch %s already queued as #%d — ignoring repeat",
                    key, existing.queue_id)
        return existing

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_offline_queue
                   (client_uuid, device_name, actor, slot_id, date, payload,
                    base_digest, captured_at, state)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (key, (device_name or "").strip() or None,
             (actor or "").strip() or None, slot_id, date,
             json.dumps(marks, separators=(",", ":")),
             (base_digest or "").strip() or None,
             (captured_at or "").strip() or _now(), PENDING))
        conn.commit()
        queue_id = int(cur.lastrowid or 0)
    logger.info("Queued offline batch #%d: slot #%d %s, %d mark(s) from %s",
                queue_id, slot_id, date, len(marks), device_name or "?")
    out = get_batch(queue_id)
    assert out is not None
    return out


def get_batch(queue_id: int) -> QueuedBatch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_offline_queue WHERE queue_id = ?",
            (queue_id,)).fetchone()
    return _row(r) if r else None


def batch_by_uuid(client_uuid: str) -> QueuedBatch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_offline_queue WHERE client_uuid = ?",
            ((client_uuid or "").strip(),)).fetchone()
    return _row(r) if r else None


def list_batches(
    *,
    state: str | None = None,
    device_name: str | None = None,
    slot_id: int | None = None,
    date: str | None = None,
    open_only: bool = False,
    limit: int = 200,
) -> list[QueuedBatch]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if state:
        clauses.append("state = ?")
        args.append(validate_state(state))
    elif open_only:
        clauses.append("state IN (?, ?)")
        args.extend([PENDING, CONFLICT])
    if device_name:
        clauses.append("device_name = ?")
        args.append(device_name.strip())
    if slot_id is not None:
        clauses.append("slot_id = ?")
        args.append(slot_id)
    if date:
        clauses.append("date = ?")
        args.append(reg._validate_date(date))
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_offline_queue {where} "
            "ORDER BY captured_at, queue_id LIMIT ?", args).fetchall()
    return [_row(r) for r in rows]


def pending_count() -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) AS n FROM attendance_offline_queue "
            "WHERE state = ?", (PENDING,)).fetchone()
    return int(r["n"])


def conflicts() -> list[QueuedBatch]:
    """Batches parked for a human to decide."""
    return list_batches(state=CONFLICT)


# ── Conflict detection ──────────────────────────────────────────────

def detect_conflicts(batch: QueuedBatch) -> list[Conflict]:
    """Which learners in this batch changed on the server since capture.

    The digest says *whether* the register moved; this says *who*. A
    server row counts as contested when it was recorded after the device
    captured its marks — a mark somebody made while the device was away.

    Device clocks drift, so a batch that arrives with no ``base_digest``
    is trusted rather than second-guessed: with nothing to compare
    against, inventing conflicts would block honest registers.
    """
    if not batch.base_digest:
        return []
    current = reg.register_digest(batch.slot_id, batch.date)
    if current == batch.base_digest:
        return []

    out: list[Conflict] = []
    for sid, values in batch.payload.items():
        server = core.get_record_for(batch.slot_id, sid, batch.date)
        if server is None:
            continue
        recorded = server.recorded_at or ""
        if recorded and recorded <= batch.captured_at:
            # The server row predates the capture: the device already had
            # it, so overwriting is not a conflict, it is an edit.
            continue
        out.append(Conflict(
            student_id=sid,
            server_status=server.status,
            server_code=server.code,
            server_recorded_at=server.recorded_at,
            device_status=values.get("status"),
            device_code=values.get("code"),
        ))
    return out


def _set_state(
    queue_id: int,
    state: str,
    *,
    written: int = 0,
    skipped: int = 0,
    conflict_list: list[Conflict] | None = None,
    detail: str | None = None,
    resolution: str | None = None,
) -> None:
    payload = json.dumps(
        [{"student_id": c.student_id,
          "server_status": c.server_status,
          "server_code": c.server_code,
          "server_recorded_at": c.server_recorded_at,
          "device_status": c.device_status,
          "device_code": c.device_code}
         for c in (conflict_list or [])], separators=(",", ":"))
    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_offline_queue
                  SET state = ?, written = ?, skipped = ?, conflicts = ?,
                      detail = ?, resolution = ?,
                      applied_at = CASE WHEN ? IN ('Applied', 'Rejected',
                                                   'Discarded')
                                        THEN datetime('now') ELSE applied_at END
                WHERE queue_id = ?""",
            (state, written, skipped, payload, detail, resolution, state,
             queue_id))
        conn.commit()


# ── Applying ────────────────────────────────────────────────────────

def apply_batch(
    queue_id: int,
    *,
    policy: str = DEFAULT_POLICY,
    actor: str | None = None,
    allow_retro: bool = False,
) -> SyncResult:
    """Push one queued batch into the register.

    Returns what happened rather than raising: a batch that cannot be
    applied is a state to look at, not a crash in the middle of a sync
    run that still has forty batches to get through.
    """
    init_db()
    batch = get_batch(queue_id)
    if batch is None:
        raise ValidationError(f"No queued batch with id {queue_id}")
    if batch.state in (APPLIED, DISCARDED):
        return SyncResult(queue_id=queue_id, state=batch.state,
                          written=batch.written,
                          detail="Already resolved")
    policy = validate_policy(policy)

    if reg.is_locked(batch.slot_id, batch.date):
        detail = ("Register was submitted before this batch arrived — "
                  "reopen it to apply these marks")
        _set_state(queue_id, REJECTED, detail=detail, resolution=policy)
        return SyncResult(queue_id=queue_id, state=REJECTED, detail=detail)

    decision = window.evaluate(batch.date)
    if not decision.allowed and not allow_retro:
        _set_state(queue_id, REJECTED, detail=decision.message,
                   resolution=policy)
        return SyncResult(queue_id=queue_id, state=REJECTED,
                          detail=decision.message)

    found = detect_conflicts(batch)
    payload = dict(batch.payload)
    skipped = 0

    if found:
        if policy == HOLD:
            detail = f"{len(found)} learner(s) changed since capture"
            _set_state(queue_id, CONFLICT, conflict_list=found, detail=detail,
                       resolution=policy)
            return SyncResult(queue_id=queue_id, state=CONFLICT,
                              conflicts=found, detail=detail)
        if policy == SERVER_WINS:
            for conflict in found:
                payload.pop(conflict.student_id, None)
            skipped = len(found)

    if not payload:
        detail = "Every mark in the batch was superseded on the server"
        _set_state(queue_id, APPLIED, written=0, skipped=skipped,
                   conflict_list=found, detail=detail, resolution=policy)
        return SyncResult(queue_id=queue_id, state=APPLIED, written=0,
                          skipped=skipped, conflicts=found, detail=detail)

    stamped = {
        sid: {**values,
              "data_source": values.get("data_source") or SYNC_SOURCE}
        for sid, values in payload.items()
    }
    try:
        written = core.save_register(
            batch.slot_id, batch.date, stamped,
            actor=batch.actor or actor,
            reason=f"Offline sync from {batch.device_name or 'a device'} "
                   f"(captured {batch.captured_at})",
            allow_retro=allow_retro)
    except ValidationError as e:
        _set_state(queue_id, REJECTED, detail=str(e), resolution=policy)
        return SyncResult(queue_id=queue_id, state=REJECTED, detail=str(e))

    _set_state(queue_id, APPLIED, written=written, skipped=skipped,
               conflict_list=found, resolution=policy,
               detail=(f"{skipped} learner(s) kept the server's mark"
                       if skipped else None))
    logger.info("Applied offline batch #%d: %d written, %d skipped (%s)",
                queue_id, written, skipped, policy)
    return SyncResult(queue_id=queue_id, state=APPLIED, written=written,
                      skipped=skipped, conflicts=found)


def sync(
    *,
    policy: str = DEFAULT_POLICY,
    device_name: str | None = None,
    limit: int = 200,
    actor: str | None = None,
    allow_retro: bool = False,
) -> SyncReport:
    """Apply every pending batch, oldest capture first.

    Order matters: two devices that both marked period 3 should land in
    the order the marks were taken, not the order the buses got back
    into signal.
    """
    init_db()
    batches = list_batches(state=PENDING, device_name=device_name, limit=limit)
    report = SyncReport()
    for batch in batches:
        result = apply_batch(batch.queue_id, policy=policy, actor=actor,
                             allow_retro=allow_retro)
        report.processed += 1
        report.results.append(result)
        report.written += result.written
        report.skipped += result.skipped
        if result.state == APPLIED:
            report.applied += 1
        elif result.state == CONFLICT:
            report.held += 1
        elif result.state == REJECTED:
            report.rejected += 1
    logger.info("Offline sync: %s", report.summary)
    return report


def resolve(queue_id: int, *, policy: str,
            actor: str | None = None) -> SyncResult:
    """Decide a held batch by hand.

    ``policy`` here is the human's call, so ``hold`` is not one of the
    options — a held batch that is held again has not been resolved.
    """
    policy = validate_policy(policy)
    if policy == HOLD:
        raise ValidationError(
            "Resolving a conflict means choosing the server's marks or the "
            "device's, not holding it again")
    batch = get_batch(queue_id)
    if batch is None:
        raise ValidationError(f"No queued batch with id {queue_id}")
    if batch.state != CONFLICT:
        raise ValidationError(
            f"Batch #{queue_id} is {batch.state}, not awaiting a decision")
    # Put it back in the queue so `apply_batch` treats it as fresh work.
    _set_state(queue_id, PENDING, conflict_list=batch.conflicts)
    return apply_batch(queue_id, policy=policy, actor=actor)


def discard(queue_id: int, *, reason: str,
            actor: str | None = None) -> QueuedBatch:
    """Throw a batch away — a duplicate, or a register taken in error."""
    init_db()
    batch = get_batch(queue_id)
    if batch is None:
        raise ValidationError(f"No queued batch with id {queue_id}")
    if batch.state == APPLIED:
        raise ValidationError(
            f"Batch #{queue_id} has already been applied — amend the "
            "register instead")
    note = (reason or "").strip()
    if not note:
        raise ValidationError("A reason is required to discard a batch")
    _set_state(queue_id, DISCARDED, detail=note,
               resolution=(actor or "").strip() or None)
    logger.info("Discarded offline batch #%d: %s", queue_id, note)
    out = get_batch(queue_id)
    assert out is not None
    return out


# ── Housekeeping and reporting ──────────────────────────────────────

def device_backlog() -> list[DeviceBacklog]:
    """Which devices are sitting on unsynced work."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT device_name,
                      SUM(state = ?) AS pending,
                      SUM(state = ?) AS conflicts,
                      MIN(captured_at) AS oldest
                 FROM attendance_offline_queue
                WHERE state IN (?, ?)
             GROUP BY device_name
             ORDER BY pending DESC""",
            (PENDING, CONFLICT, PENDING, CONFLICT)).fetchall()
    return [DeviceBacklog(device_name=r["device_name"],
                          pending=r["pending"] or 0,
                          conflicts=r["conflicts"] or 0,
                          oldest_capture=r["oldest"])
            for r in rows]


def stale_batches(*, older_than_days: int = STALE_BATCH_DAYS
                  ) -> list[QueuedBatch]:
    """Pending batches captured long enough ago to be worth a look."""
    cutoff = (_dt.date.today()
              - _dt.timedelta(days=max(0, int(older_than_days)))).isoformat()
    return [b for b in list_batches(open_only=True)
            if (b.captured_at or "")[:10] < cutoff]


def purge_resolved(*, before_date: str, dry_run: bool = False) -> int:
    """Drop applied and discarded batches older than a date.

    The queue is a delivery mechanism, not a record — the marks it
    delivered live in the register, and their history lives in the
    amendment trail.
    """
    init_db()
    cutoff = reg._validate_date(before_date, "Cutoff date")
    sql_where = ("WHERE state IN (?, ?, ?) AND substr(captured_at, 1, 10) < ?")
    args = [APPLIED, DISCARDED, REJECTED, cutoff]
    with _connect() as conn:
        if dry_run:
            r = conn.execute(
                f"SELECT COUNT(*) AS n FROM attendance_offline_queue "
                f"{sql_where}", args).fetchone()
            return int(r["n"])
        cur = conn.execute(
            f"DELETE FROM attendance_offline_queue {sql_where}", args)
        conn.commit()
    logger.info("Purged %d resolved offline batch(es) before %s",
                cur.rowcount, cutoff)
    return int(cur.rowcount)
