"""Funding data layer for Primary School System.

Two related concerns:
 - `FundingStream` records external funding sources (ESFA
   16-19 block, bursary allocations, high-needs uplift,
   pupil premium, advanced maths premium, etc.) with the
   allocated amount and academic year.
 - `LearnerAllocation` records per-learner allocations
   drawn from a stream (band 1/2/3/4/5, high needs element 2,
   advanced maths uplift, etc.) and tracks committed /
   drawn-down amounts.

The Summary aggregates allocation vs spend per stream so
finance can see remaining budget at a glance.
"""

from __future__ import annotations

import datetime as _dt
import logging
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

from education_system.systems.primary.infrastructure import paths as _paths

logger = logging.getLogger(__name__)

STREAM_TYPES: tuple[str, ...] = (
    "16-19 Programme Funding",
    "16-19 Bursary",
    "Discretionary Bursary",
    "Vulnerable Bursary",
    "High Needs Element 2",
    "High Needs Element 3",
    "Pupil Premium",
    "Advanced Maths Premium",
    "Disadvantage Block",
    "Adult Education Budget",
    "Apprenticeship Levy",
    "T-Level Capital",
    "Condition Improvement Fund",
    "Free Meals (16-19)",
    "Care Leaver Bursary",
    "Other Grant",
    "Other",
)
DEFAULT_STREAM_TYPE = "16-19 Programme Funding"

FUNDERS: tuple[str, ...] = (
    "ESFA",
    "DfE",
    "Local Authority",
    "Combined Authority",
    "Charity / Trust",
    "Internal",
    "Other",
)
DEFAULT_FUNDER = "ESFA"

STREAM_STATUSES: tuple[str, ...] = (
    "Planned",
    "Confirmed",
    "Active",
    "Underspent",
    "Closed",
    "Reconciled",
    "Withdrawn",
)
DEFAULT_STREAM_STATUS = "Planned"

FUNDING_BANDS: tuple[str, ...] = (
    "Band 1",
    "Band 2",
    "Band 3",
    "Band 4",
    "Band 4a",
    "Band 4b",
    "Band 5",
    "High Needs Element 2",
    "High Needs Element 3",
    "Advanced Maths Uplift",
    "Disadvantage Uplift",
    "Bursary - Vulnerable",
    "Bursary - Discretionary",
    "Free Meals",
    "Care Leaver",
    "Other",
)
DEFAULT_FUNDING_BAND = "Band 5"

ALLOCATION_STATUSES: tuple[str, ...] = (
    "Provisional",
    "Approved",
    "Active",
    "Suspended",
    "Drawn Down",
    "Closed",
    "Withdrawn",
)
DEFAULT_ALLOCATION_STATUS = "Provisional"


class ValidationError(Exception):
    pass


@dataclass
class FundingStream:
    stream_id: int
    name: str
    stream_type: str
    funder: str
    academic_year: str
    reference: str | None
    allocated_amount: float
    committed_amount: float
    drawn_down_amount: float
    starts_on: str | None
    ends_on: str | None
    status: str
    owner: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def remaining(self) -> float:
        return round(
            self.allocated_amount - self.committed_amount, 2)

    @property
    def headroom(self) -> float:
        return round(
            self.allocated_amount - self.drawn_down_amount, 2)

    @property
    def utilisation_pct(self) -> float:
        if self.allocated_amount <= 0:
            return 0.0
        return round(
            (self.drawn_down_amount / self.allocated_amount)
              * 100.0, 1)

    @property
    def is_overcommitted(self) -> bool:
        return self.committed_amount > self.allocated_amount


@dataclass
class LearnerAllocation:
    allocation_id: int
    stream_id: int | None
    learner_ref: str
    learner_name: str | None
    funding_band: str
    band_value: float
    committed_amount: float
    drawn_down_amount: float
    starts_on: str
    ends_on: str | None
    status: str
    purpose: str | None
    approved_by: str | None
    notes: str | None
    created_on: str
    updated_on: str

    @property
    def remaining(self) -> float:
        return round(
            self.committed_amount - self.drawn_down_amount, 2)


@dataclass
class FundingSummary:
    total_streams: int = 0
    planned: int = 0
    active: int = 0
    closed: int = 0
    overcommitted: int = 0
    total_allocated: float = 0.0
    total_committed: float = 0.0
    total_drawn_down: float = 0.0
    total_remaining: float = 0.0
    total_allocations: int = 0
    distinct_learners: int = 0
    avg_utilisation_pct: float = 0.0
    by_stream_type: dict[str, int] = field(default_factory=dict)
    by_funder: dict[str, int] = field(default_factory=dict)
    by_stream_status: dict[str, int] = field(default_factory=dict)
    by_band: dict[str, int] = field(default_factory=dict)
    by_allocation_status: dict[str, int] = field(default_factory=dict)


# ── DB ─────────────────────────────────────────────────────────────

@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    _paths.ensure_directories()
    conn = sqlite3.connect(_paths.FUNDING_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS funding_streams (
              stream_id           INTEGER PRIMARY KEY AUTOINCREMENT,
              name                TEXT NOT NULL,
              stream_type         TEXT NOT NULL,
              funder              TEXT NOT NULL,
              academic_year       TEXT NOT NULL,
              reference           TEXT,
              allocated_amount    REAL NOT NULL DEFAULT 0,
              committed_amount    REAL NOT NULL DEFAULT 0,
              drawn_down_amount   REAL NOT NULL DEFAULT 0,
              starts_on           TEXT,
              ends_on             TEXT,
              status              TEXT NOT NULL,
              owner               TEXT,
              notes               TEXT,
              created_on          TEXT NOT NULL,
              updated_on          TEXT NOT NULL,
              UNIQUE (name, academic_year)
            );

            CREATE TABLE IF NOT EXISTS funding_allocations (
              allocation_id       INTEGER PRIMARY KEY AUTOINCREMENT,
              stream_id           INTEGER REFERENCES funding_streams(stream_id) ON DELETE SET NULL,
              learner_ref         TEXT NOT NULL,
              learner_name        TEXT,
              funding_band        TEXT NOT NULL,
              band_value          REAL NOT NULL DEFAULT 0,
              committed_amount    REAL NOT NULL DEFAULT 0,
              drawn_down_amount   REAL NOT NULL DEFAULT 0,
              starts_on           TEXT NOT NULL,
              ends_on             TEXT,
              status              TEXT NOT NULL,
              purpose             TEXT,
              approved_by         TEXT,
              notes               TEXT,
              created_on          TEXT NOT NULL,
              updated_on          TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_alloc_learner
              ON funding_allocations(learner_ref);
            CREATE INDEX IF NOT EXISTS ix_alloc_stream
              ON funding_allocations(stream_id);
            CREATE INDEX IF NOT EXISTS ix_alloc_status
              ON funding_allocations(status);
        """)


def _check_date(label: str, value: str | None) -> None:
    if not value:
        return
    try:
        _dt.date.fromisoformat(value)
    except ValueError:
        raise ValidationError(
            f"{label} must be YYYY-MM-DD")


def _opt_float(out: dict, key: str, label: str, *,
                  default: float = 0.0,
                  allow_negative: bool = False) -> None:
    v = out.get(key)
    if v in (None, ""):
        out[key] = default
        return
    try:
        out[key] = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} must be a number")
    if not allow_negative and out[key] < 0:
        raise ValidationError(f"{label} must be >= 0")


def _validate_stream(p: dict[str, Any], *,
                            existing_id: int | None = None
                            ) -> dict[str, Any]:
    out = dict(p)
    out["name"] = (out.get("name") or "").strip()
    if not out["name"]:
        raise ValidationError("Name is required")

    st = (out.get("stream_type")
            or DEFAULT_STREAM_TYPE).strip()
    if st not in STREAM_TYPES:
        raise ValidationError(
            f"Stream type must be one of: "
            f"{', '.join(STREAM_TYPES)}")
    out["stream_type"] = st

    funder = (out.get("funder") or DEFAULT_FUNDER).strip()
    if funder not in FUNDERS:
        raise ValidationError(
            f"Funder must be one of: {', '.join(FUNDERS)}")
    out["funder"] = funder

    out["academic_year"] = (out.get("academic_year")
                                    or "").strip()
    if not out["academic_year"]:
        raise ValidationError("Academic year is required")

    status = (out.get("status") or DEFAULT_STREAM_STATUS).strip()
    if status not in STREAM_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(STREAM_STATUSES)}")
    out["status"] = status

    _check_date("Starts on", out.get("starts_on"))
    _check_date("Ends on", out.get("ends_on"))
    if (out.get("starts_on") and out.get("ends_on")
            and out["ends_on"] < out["starts_on"]):
        raise ValidationError(
            "Ends on cannot be before starts on")

    _opt_float(out, "allocated_amount", "Allocated amount")
    _opt_float(out, "committed_amount", "Committed amount")
    _opt_float(out, "drawn_down_amount", "Drawn-down amount")

    for k in ("reference", "owner", "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("starts_on", "ends_on"):
        v = out.get(k)
        out[k] = ((v or "").strip() or None
                    if isinstance(v, str) else v)

    # Uniqueness on (name, academic_year)
    with _connect() as conn:
        row = conn.execute(
            "SELECT stream_id FROM funding_streams "
            "WHERE name=? AND academic_year=?",
            (out["name"], out["academic_year"])).fetchone()
    if row and row["stream_id"] != existing_id:
        raise ValidationError(
            f"A stream named {out['name']!r} for "
            f"{out['academic_year']} already exists")
    return out


def _validate_allocation(p: dict[str, Any]) -> dict[str, Any]:
    out = dict(p)
    out["learner_ref"] = (out.get("learner_ref") or "").strip()
    if not out["learner_ref"]:
        raise ValidationError("Learner ref is required")

    band = (out.get("funding_band")
              or DEFAULT_FUNDING_BAND).strip()
    if band not in FUNDING_BANDS:
        raise ValidationError(
            f"Funding band must be one of: "
            f"{', '.join(FUNDING_BANDS)}")
    out["funding_band"] = band

    status = (out.get("status")
                  or DEFAULT_ALLOCATION_STATUS).strip()
    if status not in ALLOCATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ALLOCATION_STATUSES)}")
    out["status"] = status

    out["starts_on"] = (out.get("starts_on") or "").strip()
    if not out["starts_on"]:
        raise ValidationError("Starts on is required")
    _check_date("Starts on", out["starts_on"])
    _check_date("Ends on", out.get("ends_on"))
    if (out.get("ends_on")
            and out["ends_on"] < out["starts_on"]):
        raise ValidationError(
            "Ends on cannot be before starts on")

    sid = out.get("stream_id")
    if sid in (None, "", 0):
        out["stream_id"] = None
    else:
        try:
            out["stream_id"] = int(sid)
        except (TypeError, ValueError):
            raise ValidationError(
                "Stream id must be an integer")

    _opt_float(out, "band_value", "Band value")
    _opt_float(out, "committed_amount", "Committed amount")
    _opt_float(out, "drawn_down_amount", "Drawn-down amount")

    if out["drawn_down_amount"] > out["committed_amount"]:
        raise ValidationError(
            "Drawn-down amount cannot exceed committed amount")

    for k in ("learner_name", "purpose", "approved_by",
               "notes"):
        v = out.get(k)
        out[k] = (v.strip() if isinstance(v, str) else v) or None
    for k in ("ends_on",):
        v = out.get(k)
        out[k] = ((v or "").strip() or None
                    if isinstance(v, str) else v)
    return out


def _row_stream(r: sqlite3.Row) -> FundingStream:
    return FundingStream(
        stream_id=r["stream_id"],
        name=r["name"],
        stream_type=r["stream_type"],
        funder=r["funder"],
        academic_year=r["academic_year"],
        reference=r["reference"],
        allocated_amount=r["allocated_amount"],
        committed_amount=r["committed_amount"],
        drawn_down_amount=r["drawn_down_amount"],
        starts_on=r["starts_on"],
        ends_on=r["ends_on"],
        status=r["status"],
        owner=r["owner"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


def _row_allocation(r: sqlite3.Row) -> LearnerAllocation:
    return LearnerAllocation(
        allocation_id=r["allocation_id"],
        stream_id=r["stream_id"],
        learner_ref=r["learner_ref"],
        learner_name=r["learner_name"],
        funding_band=r["funding_band"],
        band_value=r["band_value"],
        committed_amount=r["committed_amount"],
        drawn_down_amount=r["drawn_down_amount"],
        starts_on=r["starts_on"],
        ends_on=r["ends_on"],
        status=r["status"],
        purpose=r["purpose"],
        approved_by=r["approved_by"],
        notes=r["notes"],
        created_on=r["created_on"],
        updated_on=r["updated_on"],
    )


# ── CRUD: streams ────────────────────────────────────────

def create_stream(payload: dict[str, Any]) -> FundingStream:
    init_db()
    p = _validate_stream(payload)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO funding_streams (
              name, stream_type, funder, academic_year,
              reference, allocated_amount, committed_amount,
              drawn_down_amount, starts_on, ends_on,
              status, owner, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?)
        """, (
            p["name"], p["stream_type"], p["funder"],
            p["academic_year"], p["reference"],
            p["allocated_amount"], p["committed_amount"],
            p["drawn_down_amount"], p["starts_on"],
            p["ends_on"], p["status"], p["owner"],
            p["notes"], now, now,
        ))
        sid = cur.lastrowid
    return get_stream(sid)  # type: ignore[return-value]


def update_stream(stream_id: int,
                       payload: dict[str, Any]) -> FundingStream:
    init_db()
    if get_stream(stream_id) is None:
        raise ValidationError(
            f"No stream with id {stream_id}")
    p = _validate_stream(payload, existing_id=stream_id)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE funding_streams SET
              name=?, stream_type=?, funder=?,
              academic_year=?, reference=?,
              allocated_amount=?, committed_amount=?,
              drawn_down_amount=?, starts_on=?, ends_on=?,
              status=?, owner=?, notes=?, updated_on=?
            WHERE stream_id=?
        """, (
            p["name"], p["stream_type"], p["funder"],
            p["academic_year"], p["reference"],
            p["allocated_amount"], p["committed_amount"],
            p["drawn_down_amount"], p["starts_on"],
            p["ends_on"], p["status"], p["owner"],
            p["notes"], now, stream_id,
        ))
    return get_stream(stream_id)  # type: ignore[return-value]


def delete_stream(stream_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM funding_streams WHERE stream_id=?",
            (stream_id,))
        return cur.rowcount > 0


def get_stream(stream_id: int) -> FundingStream | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM funding_streams WHERE stream_id=?",
            (stream_id,)).fetchone()
    return _row_stream(r) if r else None


def list_streams(*,
                       stream_type: str | None = None,
                       funder: str | None = None,
                       academic_year: str | None = None,
                       status: str | None = None,
                       active_only: bool = False,
                       overcommitted_only: bool = False,
                       name_like: str | None = None,
                       ) -> list[FundingStream]:
    init_db()
    sql = "SELECT * FROM funding_streams WHERE 1=1"
    params: list[Any] = []
    if stream_type:
        sql += " AND stream_type=?"
        params.append(stream_type)
    if funder:
        sql += " AND funder=?"
        params.append(funder)
    if academic_year:
        sql += " AND academic_year=?"
        params.append(academic_year)
    if status:
        sql += " AND status=?"
        params.append(status)
    if active_only:
        sql += (" AND status IN "
                  "('Confirmed','Active','Underspent')")
    if overcommitted_only:
        sql += " AND committed_amount > allocated_amount"
    if name_like:
        sql += " AND name LIKE ?"
        params.append(f"%{name_like}%")
    sql += (" ORDER BY academic_year DESC,"
              " stream_type, name")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_stream(r) for r in rows]


# ── CRUD: allocations ────────────────────────────────────

def create_allocation(payload: dict[str, Any]
                              ) -> LearnerAllocation:
    init_db()
    p = _validate_allocation(payload)
    if p["stream_id"] is not None:
        if get_stream(p["stream_id"]) is None:
            raise ValidationError(
                f"No stream with id {p['stream_id']}")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute("""
            INSERT INTO funding_allocations (
              stream_id, learner_ref, learner_name,
              funding_band, band_value, committed_amount,
              drawn_down_amount, starts_on, ends_on,
              status, purpose, approved_by, notes,
              created_on, updated_on
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?)
        """, (
            p["stream_id"], p["learner_ref"],
            p["learner_name"], p["funding_band"],
            p["band_value"], p["committed_amount"],
            p["drawn_down_amount"], p["starts_on"],
            p["ends_on"], p["status"], p["purpose"],
            p["approved_by"], p["notes"], now, now,
        ))
        aid = cur.lastrowid
    if p["stream_id"] is not None:
        _recompute_stream_totals(p["stream_id"])
    return get_allocation(aid)  # type: ignore[return-value]


def update_allocation(allocation_id: int,
                              payload: dict[str, Any]
                              ) -> LearnerAllocation:
    init_db()
    existing = get_allocation(allocation_id)
    if existing is None:
        raise ValidationError(
            f"No allocation with id {allocation_id}")
    p = _validate_allocation(payload)
    if p["stream_id"] is not None:
        if get_stream(p["stream_id"]) is None:
            raise ValidationError(
                f"No stream with id {p['stream_id']}")
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute("""
            UPDATE funding_allocations SET
              stream_id=?, learner_ref=?, learner_name=?,
              funding_band=?, band_value=?,
              committed_amount=?, drawn_down_amount=?,
              starts_on=?, ends_on=?, status=?, purpose=?,
              approved_by=?, notes=?, updated_on=?
            WHERE allocation_id=?
        """, (
            p["stream_id"], p["learner_ref"],
            p["learner_name"], p["funding_band"],
            p["band_value"], p["committed_amount"],
            p["drawn_down_amount"], p["starts_on"],
            p["ends_on"], p["status"], p["purpose"],
            p["approved_by"], p["notes"], now,
            allocation_id,
        ))
    for sid in {existing.stream_id, p["stream_id"]}:
        if sid is not None:
            _recompute_stream_totals(sid)
    return get_allocation(allocation_id)  # type: ignore[return-value]


def delete_allocation(allocation_id: int) -> bool:
    init_db()
    existing = get_allocation(allocation_id)
    if existing is None:
        return False
    with _connect() as conn:
        conn.execute(
            "DELETE FROM funding_allocations "
            "WHERE allocation_id=?",
            (allocation_id,))
    if existing.stream_id is not None:
        _recompute_stream_totals(existing.stream_id)
    return True


def get_allocation(allocation_id: int
                            ) -> LearnerAllocation | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM funding_allocations "
            "WHERE allocation_id=?",
            (allocation_id,)).fetchone()
    return _row_allocation(r) if r else None


def list_allocations(*,
                              stream_id: int | None = None,
                              learner_ref: str | None = None,
                              funding_band: str | None = None,
                              status: str | None = None,
                              active_only: bool = False,
                              ) -> list[LearnerAllocation]:
    init_db()
    sql = "SELECT * FROM funding_allocations WHERE 1=1"
    params: list[Any] = []
    if stream_id is not None:
        sql += " AND stream_id=?"
        params.append(stream_id)
    if learner_ref:
        sql += " AND learner_ref=?"
        params.append(learner_ref)
    if funding_band:
        sql += " AND funding_band=?"
        params.append(funding_band)
    if status:
        sql += " AND status=?"
        params.append(status)
    if active_only:
        sql += " AND status IN ('Approved','Active')"
    sql += (" ORDER BY learner_ref, starts_on,"
              " allocation_id DESC")
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_allocation(r) for r in rows]


def allocations_for_learner(learner_ref: str
                                       ) -> list[LearnerAllocation]:
    return list_allocations(learner_ref=learner_ref)


def allocations_for_stream(stream_id: int
                                       ) -> list[LearnerAllocation]:
    return list_allocations(stream_id=stream_id)


def _recompute_stream_totals(stream_id: int) -> None:
    """Sum allocations under a stream into committed /
    drawn_down on the stream header."""
    with _connect() as conn:
        r = conn.execute(
            "SELECT COALESCE(SUM(committed_amount), 0) AS c,"
            " COALESCE(SUM(drawn_down_amount), 0) AS d "
            "FROM funding_allocations WHERE stream_id=?",
            (stream_id,)).fetchone()
        now = _dt.datetime.now().isoformat(timespec="seconds")
        conn.execute(
            "UPDATE funding_streams SET "
            "committed_amount=?, drawn_down_amount=?, "
            "updated_on=? WHERE stream_id=?",
            (round(r["c"], 2), round(r["d"], 2),
              now, stream_id))


# ── Workflow ──────────────────────────────────────────────

def _stream_dict(s: FundingStream) -> dict[str, Any]:
    return {
        "name": s.name,
        "stream_type": s.stream_type,
        "funder": s.funder,
        "academic_year": s.academic_year,
        "reference": s.reference,
        "allocated_amount": s.allocated_amount,
        "committed_amount": s.committed_amount,
        "drawn_down_amount": s.drawn_down_amount,
        "starts_on": s.starts_on,
        "ends_on": s.ends_on,
        "status": s.status,
        "owner": s.owner,
        "notes": s.notes,
    }


def confirm_stream(stream_id: int) -> FundingStream:
    s = get_stream(stream_id)
    if s is None:
        raise ValidationError(
            f"No stream with id {stream_id}")
    return update_stream(stream_id,
                                {**_stream_dict(s),
                                  "status": "Confirmed"})


def activate_stream(stream_id: int) -> FundingStream:
    s = get_stream(stream_id)
    if s is None:
        raise ValidationError(
            f"No stream with id {stream_id}")
    return update_stream(stream_id,
                                {**_stream_dict(s),
                                  "status": "Active"})


def close_stream(stream_id: int) -> FundingStream:
    s = get_stream(stream_id)
    if s is None:
        raise ValidationError(
            f"No stream with id {stream_id}")
    return update_stream(stream_id,
                                {**_stream_dict(s),
                                  "status": "Closed"})


def reconcile_stream(stream_id: int) -> FundingStream:
    s = get_stream(stream_id)
    if s is None:
        raise ValidationError(
            f"No stream with id {stream_id}")
    return update_stream(stream_id,
                                {**_stream_dict(s),
                                  "status": "Reconciled"})


def set_stream_status(stream_id: int,
                                  new_status: str) -> FundingStream:
    if new_status not in STREAM_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(STREAM_STATUSES)}")
    s = get_stream(stream_id)
    if s is None:
        raise ValidationError(
            f"No stream with id {stream_id}")
    return update_stream(stream_id,
                                {**_stream_dict(s),
                                  "status": new_status})


def _alloc_dict(a: LearnerAllocation) -> dict[str, Any]:
    return {
        "stream_id": a.stream_id,
        "learner_ref": a.learner_ref,
        "learner_name": a.learner_name,
        "funding_band": a.funding_band,
        "band_value": a.band_value,
        "committed_amount": a.committed_amount,
        "drawn_down_amount": a.drawn_down_amount,
        "starts_on": a.starts_on,
        "ends_on": a.ends_on,
        "status": a.status,
        "purpose": a.purpose,
        "approved_by": a.approved_by,
        "notes": a.notes,
    }


def approve_allocation(allocation_id: int, *,
                                  approved_by: str | None = None
                                  ) -> LearnerAllocation:
    a = get_allocation(allocation_id)
    if a is None:
        raise ValidationError(
            f"No allocation with id {allocation_id}")
    data = _alloc_dict(a)
    data["status"] = "Approved"
    if approved_by:
        data["approved_by"] = approved_by
    return update_allocation(allocation_id, data)


def activate_allocation(allocation_id: int
                                  ) -> LearnerAllocation:
    a = get_allocation(allocation_id)
    if a is None:
        raise ValidationError(
            f"No allocation with id {allocation_id}")
    return update_allocation(allocation_id,
                                       {**_alloc_dict(a),
                                         "status": "Active"})


def suspend_allocation(allocation_id: int
                                 ) -> LearnerAllocation:
    a = get_allocation(allocation_id)
    if a is None:
        raise ValidationError(
            f"No allocation with id {allocation_id}")
    return update_allocation(allocation_id,
                                       {**_alloc_dict(a),
                                         "status": "Suspended"})


def close_allocation(allocation_id: int
                               ) -> LearnerAllocation:
    a = get_allocation(allocation_id)
    if a is None:
        raise ValidationError(
            f"No allocation with id {allocation_id}")
    return update_allocation(allocation_id,
                                       {**_alloc_dict(a),
                                         "status": "Closed"})


def withdraw_allocation(allocation_id: int
                                   ) -> LearnerAllocation:
    a = get_allocation(allocation_id)
    if a is None:
        raise ValidationError(
            f"No allocation with id {allocation_id}")
    return update_allocation(allocation_id,
                                       {**_alloc_dict(a),
                                         "status": "Withdrawn"})


def record_drawdown(allocation_id: int, *,
                              amount: float) -> LearnerAllocation:
    a = get_allocation(allocation_id)
    if a is None:
        raise ValidationError(
            f"No allocation with id {allocation_id}")
    if amount <= 0:
        raise ValidationError(
            "Drawdown amount must be > 0")
    new_drawn = round(a.drawn_down_amount + amount, 2)
    if new_drawn > a.committed_amount:
        raise ValidationError(
            "Drawdown would exceed committed amount")
    data = _alloc_dict(a)
    data["drawn_down_amount"] = new_drawn
    if new_drawn == a.committed_amount:
        data["status"] = "Drawn Down"
    return update_allocation(allocation_id, data)


def set_allocation_status(allocation_id: int,
                                       new_status: str
                                       ) -> LearnerAllocation:
    if new_status not in ALLOCATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(ALLOCATION_STATUSES)}")
    a = get_allocation(allocation_id)
    if a is None:
        raise ValidationError(
            f"No allocation with id {allocation_id}")
    return update_allocation(allocation_id,
                                       {**_alloc_dict(a),
                                         "status": new_status})


# ── Summary ─────────────────────────────────────────────

def summary() -> FundingSummary:
    streams = list_streams()
    allocations = list_allocations()
    out = FundingSummary(
        total_streams=len(streams),
        total_allocations=len(allocations))
    util_sum = 0.0
    util_n = 0
    for s in streams:
        if s.status == "Planned":
            out.planned += 1
        elif s.status in ("Confirmed", "Active",
                                 "Underspent"):
            out.active += 1
        elif s.status in ("Closed", "Reconciled",
                                 "Withdrawn"):
            out.closed += 1
        if s.is_overcommitted:
            out.overcommitted += 1
        out.total_allocated += s.allocated_amount
        out.total_committed += s.committed_amount
        out.total_drawn_down += s.drawn_down_amount
        if s.allocated_amount > 0:
            util_sum += s.utilisation_pct
            util_n += 1
        out.by_stream_type[s.stream_type] = (
            out.by_stream_type.get(s.stream_type, 0) + 1)
        out.by_funder[s.funder] = (
            out.by_funder.get(s.funder, 0) + 1)
        out.by_stream_status[s.status] = (
            out.by_stream_status.get(s.status, 0) + 1)
    out.total_remaining = round(
        out.total_allocated - out.total_committed, 2)
    out.total_allocated = round(out.total_allocated, 2)
    out.total_committed = round(out.total_committed, 2)
    out.total_drawn_down = round(out.total_drawn_down, 2)
    if util_n:
        out.avg_utilisation_pct = round(util_sum / util_n, 1)
    learners: set[str] = set()
    for a in allocations:
        learners.add(a.learner_ref)
        out.by_band[a.funding_band] = (
            out.by_band.get(a.funding_band, 0) + 1)
        out.by_allocation_status[a.status] = (
            out.by_allocation_status.get(a.status, 0) + 1)
    out.distinct_learners = len(learners)
    return out


__all__ = [
    "STREAM_TYPES", "DEFAULT_STREAM_TYPE",
    "FUNDERS", "DEFAULT_FUNDER",
    "STREAM_STATUSES", "DEFAULT_STREAM_STATUS",
    "FUNDING_BANDS", "DEFAULT_FUNDING_BAND",
    "ALLOCATION_STATUSES", "DEFAULT_ALLOCATION_STATUS",
    "ValidationError",
    "FundingStream", "LearnerAllocation", "FundingSummary",
    "init_db",
    "create_stream", "update_stream", "delete_stream",
    "get_stream", "list_streams",
    "create_allocation", "update_allocation",
    "delete_allocation", "get_allocation",
    "list_allocations", "allocations_for_learner",
    "allocations_for_stream",
    "confirm_stream", "activate_stream", "close_stream",
    "reconcile_stream", "set_stream_status",
    "approve_allocation", "activate_allocation",
    "suspend_allocation", "close_allocation",
    "withdraw_allocation", "record_drawdown",
    "set_allocation_status",
    "summary",
]
