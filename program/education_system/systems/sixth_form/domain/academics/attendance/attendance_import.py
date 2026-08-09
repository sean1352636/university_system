"""Bulk attendance import for the Sixth Form System.

Sibling to :mod:`attendance`. A learner who arrives in September did not
begin existing in September: they have two years of attendance behind
them at a school that is about to send a CSV. Retyping it is not an
option, and neither is throwing it away — the first pastoral
conversation of the year is much better informed by it.

Importing history is a different act from taking a register, and this
module treats it as one:

* **Nothing is written until it has been read.** :func:`plan` parses,
  resolves and validates the whole file, and reports what *would*
  happen — how many rows land, which learners are unknown, which dates
  fall outside the timetable, which marks would overwrite something
  that is already there. A file is applied only after somebody has seen
  that.
* **Every batch can be undone.** Each written row keeps the state it
  replaced, so :func:`rollback` puts the register back exactly as it
  was, including the rows the import created (which are deleted).
  Bulk-writing thousands of marks with no way back is how a bad column
  mapping becomes a permanent problem.
* **It is honest about being retrospective.** Import writes carry the
  ``import`` data source and pass the retro-marking window explicitly
  rather than pretending a 2024 mark was taken this morning.

The register lock is *not* bypassed. A submitted register is a signed
document, and a file arriving from elsewhere does not get to overwrite
one silently — those rows are skipped and reported.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

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

# What happened to one row of the file.
WRITTEN: str = "Written"
SKIPPED: str = "Skipped"
ERROR: str = "Error"
ROW_OUTCOMES: tuple[str, ...] = (WRITTEN, SKIPPED, ERROR)

APPLIED: str = "Applied"
ROLLED_BACK: str = "Rolled back"
BATCH_STATES: tuple[str, ...] = (APPLIED, ROLLED_BACK)

IMPORT_SOURCE: str = "import"

# Column aliases, so a file exported from somebody else's MIS does not
# need editing before it can be read. Keys are our names; values are
# what a header might plausibly say.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "student_id":   ("student_id", "student", "studentid", "id", "upn",
                     "candidate", "candidate_no", "learner", "learner_id"),
    "date":         ("date", "attendance_date", "day_date", "session_date"),
    "slot_id":      ("slot_id", "slot", "slotid"),
    "group_id":     ("group_id", "group", "class", "class_id", "teaching_group"),
    "period":       ("period", "lesson", "period_no"),
    "code":         ("code", "mark", "attendance_code", "mark_code"),
    "status":       ("status", "attendance", "present"),
    "minutes_late": ("minutes_late", "minutes", "mins_late", "late_minutes",
                     "late"),
    "notes":        ("notes", "note", "comment", "comments", "reason_text"),
}

# A file bigger than this is a migration, not an import, and should go
# through the migration tooling where it can be run out of hours.
MAX_ROWS: int = 20000

_SCHEMA = """
CREATE TABLE IF NOT EXISTS attendance_import_batches (
    batch_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    label          TEXT NOT NULL,
    source         TEXT,
    imported_by    TEXT,
    state          TEXT NOT NULL DEFAULT 'Applied',
    rows_read      INTEGER NOT NULL DEFAULT 0,
    rows_written   INTEGER NOT NULL DEFAULT 0,
    rows_skipped   INTEGER NOT NULL DEFAULT 0,
    rows_errored   INTEGER NOT NULL DEFAULT 0,
    date_from      TEXT,
    date_to        TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    rolled_back_at TEXT,
    rolled_back_by TEXT
);

CREATE TABLE IF NOT EXISTS attendance_import_rows (
    import_row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id      INTEGER NOT NULL,
    line_no       INTEGER,
    student_id    TEXT,
    date          TEXT,
    slot_id       INTEGER,
    code          TEXT,
    status        TEXT,
    outcome       TEXT NOT NULL,
    detail        TEXT,
    prior         TEXT,
    FOREIGN KEY (batch_id) REFERENCES attendance_import_batches(batch_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_att_import_rows_batch
    ON attendance_import_rows(batch_id);
CREATE INDEX IF NOT EXISTS idx_att_import_rows_outcome
    ON attendance_import_rows(outcome);
"""

# The columns a rollback has to put back. Mirrors the undo snapshot in
# :mod:`attendance_register` for the same reason: anything missing here
# would be silently reset to its default when a batch is undone.
_RESTORE_COLUMNS: tuple[str, ...] = (
    "status", "minutes_late", "notes", "arrival_time", "departure_time",
    "code", "reason_id", "session", "authorised_by", "authorised_at",
    "authorisation_note", "is_offsite", "offsite_location", "data_source",
    "voided", "voided_by", "voided_at", "void_reason",
)

_RESTORE_DEFAULTS: dict[str, Any] = {
    "is_offsite": 0, "voided": 0, "data_source": "manual",
}


# ── Shapes ──────────────────────────────────────────────────────────

@dataclass
class ImportRow:
    """One line of the file, resolved as far as it can be."""

    line_no: int
    student_id: str | None = None
    date: str | None = None
    slot_id: int | None = None
    code: str | None = None
    status: str | None = None
    minutes_late: int | None = None
    notes: str | None = None
    outcome: str = WRITTEN
    detail: str | None = None
    existing: bool = False          # a mark is already there

    @property
    def ok(self) -> bool:
        return self.outcome != ERROR

    @property
    def key(self) -> tuple[int, str, str]:
        return (self.slot_id or 0, self.student_id or "", self.date or "")

    @property
    def label(self) -> str:
        return (f"line {self.line_no}: {self.student_id or '?'} "
                f"{self.date or '?'} slot #{self.slot_id or '?'} "
                f"{self.code or self.status or '?'}")


@dataclass
class ImportPlan:
    """What applying this file would do. Nothing has been written."""

    rows: list[ImportRow] = field(default_factory=list)
    errors: list[ImportRow] = field(default_factory=list)
    unknown_students: set[str] = field(default_factory=set)
    unknown_slots: set[int] = field(default_factory=set)
    locked_registers: set[tuple[int, str]] = field(default_factory=set)
    duplicates: int = 0
    date_from: str | None = None
    date_to: str | None = None

    @property
    def writable(self) -> list[ImportRow]:
        return [r for r in self.rows if r.outcome == WRITTEN]

    @property
    def overwrites(self) -> int:
        return sum(1 for r in self.writable if r.existing)

    @property
    def total(self) -> int:
        return len(self.rows) + len(self.errors)

    @property
    def summary(self) -> str:
        return (f"{self.total} row(s) read: {len(self.writable)} to write "
                f"({self.overwrites} overwriting an existing mark), "
                f"{len(self.rows) - len(self.writable)} skipped, "
                f"{len(self.errors)} in error")


@dataclass
class ImportBatch:
    """A file that was applied."""

    batch_id: int
    label: str
    source: str | None
    imported_by: str | None
    state: str
    rows_read: int
    rows_written: int
    rows_skipped: int
    rows_errored: int
    date_from: str | None
    date_to: str | None
    created_at: str | None
    rolled_back_at: str | None
    rolled_back_by: str | None

    @property
    def is_live(self) -> bool:
        return self.state == APPLIED


@dataclass
class RollbackResult:
    batch_id: int
    restored: int
    deleted: int


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
    logger.debug("Attendance import schema ready at %s", DB_PATH)
    _DB_READY = True


# ── Parsing ─────────────────────────────────────────────────────────

def _normalise_header(name: str) -> str:
    return (name or "").strip().lower().replace(" ", "_").replace("-", "_")


def map_columns(headers: Sequence[str]) -> dict[str, str]:
    """Work out which column in the file is which of ours.

    Returns ``our_name -> their_header``. Unrecognised columns are
    ignored rather than fatal: exports carry all sorts of passengers.
    """
    seen = {_normalise_header(h): h for h in headers if h}
    mapping: dict[str, str] = {}
    for ours, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            if alias in seen:
                mapping[ours] = seen[alias]
                break
    return mapping


def _as_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_date(value: Any) -> str | None:
    """Accept ISO, and the two orderings a spreadsheet is likely to emit."""
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d", "%d.%m.%Y"):
        try:
            return _dt.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _resolve_slot(row: dict[str, Any], mapping: dict[str, str],
                  date: str) -> tuple[int | None, str | None]:
    """Find the timetable slot a row refers to.

    A file that names the slot outright is easy. One that names a group
    and a period — which is what most exports carry — is resolved
    against the timetable for that date's weekday, honouring the A/B
    week so a fortnightly lesson lands on the right slot.
    """
    if "slot_id" in mapping:
        slot_id = _as_int(row.get(mapping["slot_id"]))
        if slot_id is not None:
            return slot_id, None
    group_id = (_as_int(row.get(mapping["group_id"]))
                if "group_id" in mapping else None)
    period = (_as_int(row.get(mapping["period"]))
              if "period" in mapping else None)
    if group_id is None or period is None:
        return None, "No slot_id, and no group + period to resolve one from"
    day = _dt.date.fromisoformat(date).weekday() + 1
    candidates = [s for s in tt.list_slots(group_id=group_id)
                  if s.day == day and s.period == period]
    candidates = weeks.filter_slots(candidates, date)
    if not candidates:
        return None, (f"No slot for group #{group_id} period {period} on "
                      f"{date}")
    return candidates[0].slot_id, None


def parse_rows(records: Iterable[dict[str, Any]],
               *, headers: Sequence[str] | None = None) -> list[ImportRow]:
    """Turn raw file records into resolved :class:`ImportRow` objects.

    Separate from :func:`parse_csv` so a caller with data from anywhere
    else — a spreadsheet library, an API pull — gets the same
    resolution and the same error reporting.
    """
    records = list(records)
    if len(records) > MAX_ROWS:
        raise ValidationError(
            f"File has {len(records)} rows; the limit is {MAX_ROWS}. "
            "Split it, or use the migration tooling.")
    if headers is None:
        headers = list(records[0].keys()) if records else []
    mapping = map_columns(headers)
    if "student_id" not in mapping:
        raise ValidationError(
            "No student column found. Expected one of: "
            + ", ".join(COLUMN_ALIASES["student_id"]))
    if "date" not in mapping:
        raise ValidationError(
            "No date column found. Expected one of: "
            + ", ".join(COLUMN_ALIASES["date"]))
    if "code" not in mapping and "status" not in mapping:
        raise ValidationError(
            "No mark column found — expected a 'code' or a 'status' column")

    out: list[ImportRow] = []
    for offset, record in enumerate(records, start=2):   # line 1 is the header
        row = ImportRow(line_no=offset)
        row.student_id = str(record.get(mapping["student_id"]) or "").strip()
        if not row.student_id:
            row.outcome, row.detail = ERROR, "Missing student ID"
            out.append(row)
            continue
        row.date = _parse_date(record.get(mapping["date"]))
        if not row.date:
            row.outcome = ERROR
            row.detail = (f"Unreadable date "
                          f"{record.get(mapping['date'])!r}")
            out.append(row)
            continue

        slot_id, problem = _resolve_slot(record, mapping, row.date)
        if slot_id is None:
            row.outcome, row.detail = ERROR, problem
            out.append(row)
            continue
        row.slot_id = slot_id

        raw_code = (str(record.get(mapping["code"]) or "").strip()
                    if "code" in mapping else "")
        raw_status = (str(record.get(mapping["status"]) or "").strip()
                      if "status" in mapping else "")
        if raw_code:
            try:
                row.code = codes.validate_code(raw_code)
            except ValidationError as e:
                row.outcome, row.detail = ERROR, str(e)
                out.append(row)
                continue
        if raw_status:
            row.status = raw_status.title()
        if not row.code and not row.status:
            row.outcome, row.detail = ERROR, "Row has no mark"
            out.append(row)
            continue

        if "minutes_late" in mapping:
            row.minutes_late = _as_int(record.get(mapping["minutes_late"]))
        if "notes" in mapping:
            row.notes = str(record.get(mapping["notes"]) or "").strip() or None
        out.append(row)
    return out


def parse_csv(text: str) -> list[ImportRow]:
    """Parse CSV text into rows."""
    reader = csv.DictReader(io.StringIO(text))
    return parse_rows(list(reader), headers=reader.fieldnames or [])


def parse_file(path: str | Path) -> list[ImportRow]:
    """Parse a CSV file from disk, tolerating a UTF-8 byte-order mark."""
    target = Path(path)
    if not target.exists():
        raise ValidationError(f"No such file: {target}")
    return parse_csv(target.read_text(encoding="utf-8-sig"))


# ── Planning ────────────────────────────────────────────────────────

def plan(rows: Sequence[ImportRow]) -> ImportPlan:
    """Work out what applying these rows would do. Writes nothing.

    Every reason a row will not land is decided here rather than
    halfway through the write, so the report somebody approves is the
    report they get.
    """
    init_db()
    result = ImportPlan()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    known_students = {s.student_id for s in _students.list_students()}
    known_slots = {s.slot_id for s in tt.list_slots()}
    rosters: dict[int, set[str]] = {}
    seen: set[tuple[int, str, str]] = set()

    from education_system.systems.sixth_form.domain.academics.class_groups import (
        class_groups as _cg,
    )

    for row in rows:
        if row.outcome == ERROR:
            result.errors.append(row)
            continue

        assert row.student_id and row.date and row.slot_id is not None
        if row.student_id not in known_students:
            result.unknown_students.add(row.student_id)
            row.outcome = SKIPPED
            row.detail = f"No student {row.student_id} in this college"
            result.rows.append(row)
            continue
        if row.slot_id not in known_slots:
            result.unknown_slots.add(row.slot_id)
            row.outcome = SKIPPED
            row.detail = f"No slot #{row.slot_id}"
            result.rows.append(row)
            continue

        if row.slot_id not in rosters:
            slot = tt.get_slot(row.slot_id)
            rosters[row.slot_id] = (set(_cg.list_members(slot.group_id))
                                    if slot else set())
        if row.student_id not in rosters[row.slot_id]:
            row.outcome = SKIPPED
            row.detail = (f"{row.student_id} is not on the roster for slot "
                          f"#{row.slot_id}")
            result.rows.append(row)
            continue

        if row.key in seen:
            result.duplicates += 1
            row.outcome = SKIPPED
            row.detail = "Duplicate of an earlier row in the same file"
            result.rows.append(row)
            continue
        seen.add(row.key)

        if reg.is_locked(row.slot_id, row.date):
            result.locked_registers.add((row.slot_id, row.date))
            row.outcome = SKIPPED
            row.detail = "That register has been submitted"
            result.rows.append(row)
            continue

        existing = core.get_record_for(row.slot_id, row.student_id, row.date)
        row.existing = existing is not None and not existing.voided
        result.rows.append(row)

        if result.date_from is None or row.date < result.date_from:
            result.date_from = row.date
        if result.date_to is None or row.date > result.date_to:
            result.date_to = row.date
    return result


def plan_csv(text: str) -> ImportPlan:
    """Parse and plan in one call — the usual entry point for a preview."""
    return plan(parse_csv(text))


# ── Applying ────────────────────────────────────────────────────────

def _capture_prior(slot_id: int, student_id: str,
                   date: str) -> dict[str, Any] | None:
    """The row as it stands, so a rollback can put it back."""
    with _connect() as conn:
        r = conn.execute(
            f"SELECT {', '.join(_RESTORE_COLUMNS)} FROM attendance_records "
            "WHERE slot_id = ? AND student_id = ? AND date = ?",
            (slot_id, student_id, date)).fetchone()
    return dict(r) if r else None


def apply_plan(
    result: ImportPlan,
    *,
    label: str,
    source: str | None = None,
    actor: str | None = None,
    skip_overwrites: bool = False,
) -> ImportBatch:
    """Write a planned import, recording enough to undo it.

    ``skip_overwrites`` leaves alone any learner who already has a mark
    for that lesson — the safe choice when back-filling history into a
    college that has already started taking its own registers.
    """
    init_db()
    label = (label or "").strip()
    if not label:
        raise ValidationError("An import needs a label")
    rows = result.writable
    if skip_overwrites:
        for row in rows:
            if row.existing:
                row.outcome = SKIPPED
                row.detail = "Existing mark kept (overwrites skipped)"
        rows = [r for r in rows if r.outcome == WRITTEN]
    if not rows:
        raise ValidationError("Nothing in this plan would be written")

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO attendance_import_batches
                   (label, source, imported_by, state, rows_read, date_from,
                    date_to)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (label, (source or "").strip() or None,
             (actor or "").strip() or None, APPLIED, result.total,
             result.date_from, result.date_to))
        conn.commit()
        batch_id = int(cur.lastrowid or 0)

    # Group by register: one save per (slot, date) rather than per row,
    # so a term's import is hundreds of transactions and not thousands.
    grouped: dict[tuple[int, str], dict[str, dict[str, Any]]] = {}
    priors: dict[tuple[int, str, str], dict[str, Any] | None] = {}
    for row in rows:
        assert row.slot_id is not None and row.student_id and row.date
        key = (row.slot_id, row.date)
        payload: dict[str, Any] = {"data_source": IMPORT_SOURCE}
        if row.code:
            payload["code"] = row.code
        if row.status:
            payload["status"] = row.status
        if row.minutes_late is not None:
            payload["minutes_late"] = row.minutes_late
        if row.notes:
            payload["notes"] = row.notes
        grouped.setdefault(key, {})[row.student_id] = payload
        priors[(row.slot_id, row.student_id, row.date)] = _capture_prior(
            row.slot_id, row.student_id, row.date)

    written = 0
    for (slot_id, date), payload in sorted(grouped.items()):
        try:
            written += core.save_register(
                slot_id, date, payload, actor=actor,
                reason=f"Bulk import: {label}",
                # Historical by definition — that is the whole point of
                # an import, and the window logs the override.
                allow_retro=True)
        except ValidationError as e:
            for row in rows:
                if row.slot_id == slot_id and row.date == date:
                    row.outcome, row.detail = ERROR, str(e)
            logger.warning("Import batch #%d: slot #%d %s failed — %s",
                           batch_id, slot_id, date, e)

    skipped = [r for r in result.rows if r.outcome == SKIPPED]
    errored = [r for r in (*result.errors, *result.rows)
               if r.outcome == ERROR]
    _record_rows(batch_id, rows, priors)
    _record_rows(batch_id, skipped, {})
    _record_rows(batch_id, errored, {})

    with _connect() as conn:
        conn.execute(
            """UPDATE attendance_import_batches
                  SET rows_written = ?, rows_skipped = ?, rows_errored = ?
                WHERE batch_id = ?""",
            (written, len(skipped), len(errored), batch_id))
        conn.commit()
    logger.info("Import batch #%d (%s): %d written, %d skipped, %d errored",
                batch_id, label, written, len(skipped), len(errored))
    out = get_batch(batch_id)
    assert out is not None
    return out


def _record_rows(batch_id: int, rows: Sequence[ImportRow],
                 priors: dict[tuple[int, str, str], dict[str, Any] | None]
                 ) -> None:
    if not rows:
        return
    with _connect() as conn:
        conn.executemany(
            """INSERT INTO attendance_import_rows
                   (batch_id, line_no, student_id, date, slot_id, code,
                    status, outcome, detail, prior)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(batch_id, r.line_no, r.student_id, r.date, r.slot_id, r.code,
              r.status, r.outcome, r.detail,
              json.dumps(priors.get(
                  (r.slot_id or 0, r.student_id or "", r.date or "")))
              if r.outcome == WRITTEN else None)
             for r in rows])
        conn.commit()


def import_csv(
    text: str,
    *,
    label: str,
    source: str | None = None,
    actor: str | None = None,
    skip_overwrites: bool = False,
) -> ImportBatch:
    """Parse, plan and apply in one call.

    For a caller that has already decided — a scripted migration, or a
    UI that showed the preview from :func:`plan_csv` a moment ago.
    """
    return apply_plan(plan_csv(text), label=label, source=source,
                      actor=actor, skip_overwrites=skip_overwrites)


# ── Rollback ────────────────────────────────────────────────────────

def rollback(batch_id: int, *, actor: str | None = None) -> RollbackResult:
    """Undo a batch, putting every touched row back as it was.

    Rows the import created are deleted; rows it overwrote are restored
    from the state captured at the time. Marks changed by somebody
    *after* the import are still reverted — a rollback undoes the batch,
    not the calendar — which is why it asks for an actor and logs.
    """
    init_db()
    batch = get_batch(batch_id)
    if batch is None:
        raise ValidationError(f"No import batch with id {batch_id}")
    if batch.state == ROLLED_BACK:
        raise ValidationError(f"Batch #{batch_id} has already been rolled back")

    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_import_rows "
            "WHERE batch_id = ? AND outcome = ?",
            (batch_id, WRITTEN)).fetchall()

        restored = deleted = 0
        restorable = list(_RESTORE_COLUMNS)
        columns = ", ".join(restorable)
        placeholders = ", ".join("?" * len(restorable))
        updates = ", ".join(f"{c} = excluded.{c}" for c in restorable)
        insert_sql = (
            f"INSERT INTO attendance_records (slot_id, student_id, date, "
            f"{columns}) VALUES (?, ?, ?, {placeholders}) "
            f"ON CONFLICT(slot_id, student_id, date) DO UPDATE SET "
            f"{updates}, recorded_at = datetime('now')")

        for r in rows:
            prior = json.loads(r["prior"] or "null")
            if prior is None:
                conn.execute(
                    "DELETE FROM attendance_records "
                    "WHERE slot_id = ? AND student_id = ? AND date = ?",
                    (r["slot_id"], r["student_id"], r["date"]))
                deleted += 1
                continue
            conn.execute(insert_sql, (
                r["slot_id"], r["student_id"], r["date"],
                *(prior.get(c) if prior.get(c) is not None
                  else _RESTORE_DEFAULTS.get(c) for c in restorable)))
            restored += 1

        conn.execute(
            """UPDATE attendance_import_batches
                  SET state = ?, rolled_back_at = datetime('now'),
                      rolled_back_by = ?
                WHERE batch_id = ?""",
            (ROLLED_BACK, (actor or "").strip() or None, batch_id))
        conn.commit()

    logger.info("Rolled back import batch #%d: %d restored, %d removed (%s)",
                batch_id, restored, deleted, actor or "?")
    return RollbackResult(batch_id=batch_id, restored=restored,
                          deleted=deleted)


# ── Reads ───────────────────────────────────────────────────────────

def _batch_row(r: sqlite3.Row) -> ImportBatch:
    return ImportBatch(
        batch_id=r["batch_id"],
        label=r["label"],
        source=r["source"],
        imported_by=r["imported_by"],
        state=r["state"],
        rows_read=r["rows_read"],
        rows_written=r["rows_written"],
        rows_skipped=r["rows_skipped"],
        rows_errored=r["rows_errored"],
        date_from=r["date_from"],
        date_to=r["date_to"],
        created_at=r["created_at"],
        rolled_back_at=r["rolled_back_at"],
        rolled_back_by=r["rolled_back_by"],
    )


def get_batch(batch_id: int) -> ImportBatch | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM attendance_import_batches WHERE batch_id = ?",
            (batch_id,)).fetchone()
    return _batch_row(r) if r else None


def list_batches(*, state: str | None = None,
                 limit: int = 50) -> list[ImportBatch]:
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if state:
        if state not in BATCH_STATES:
            raise ValidationError(
                f"State must be one of: {', '.join(BATCH_STATES)}")
        clauses.append("state = ?")
        args.append(state)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_import_batches {where} "
            "ORDER BY batch_id DESC LIMIT ?", args).fetchall()
    return [_batch_row(r) for r in rows]


def batch_rows(batch_id: int, *, outcome: str | None = None,
               limit: int = 500) -> list[ImportRow]:
    """The per-line record of what the import did."""
    init_db()
    clauses = ["batch_id = ?"]
    args: list[Any] = [batch_id]
    if outcome:
        if outcome not in ROW_OUTCOMES:
            raise ValidationError(
                f"Outcome must be one of: {', '.join(ROW_OUTCOMES)}")
        clauses.append("outcome = ?")
        args.append(outcome)
    args.append(max(1, int(limit)))
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM attendance_import_rows "
            f"WHERE {' AND '.join(clauses)} ORDER BY line_no LIMIT ?",
            args).fetchall()
    return [ImportRow(
        line_no=r["line_no"] or 0, student_id=r["student_id"], date=r["date"],
        slot_id=r["slot_id"], code=r["code"], status=r["status"],
        outcome=r["outcome"], detail=r["detail"]) for r in rows]


def template_csv() -> str:
    """A header row and one example, for somebody preparing a file."""
    today = _dt.date.today().isoformat()
    return ("student_id,date,slot_id,code,minutes_late,notes\n"
            f"S12345,{today},1,/,,Imported from previous school\n")
