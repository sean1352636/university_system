"""Certificate issue log.

Boards send certificates to the centre some months after results. Each
delivery is a batch (board + series + date received); each certificate
in it is issued to the student, who signs for it (or a nominated person
collects, or it is posted).

JCQ: unclaimed certificates must be kept for at least
:data:`RETENTION_MONTHS` months from receipt; after that the centre may
destroy them (or return them to the board), keeping a record. The
retention list shows what has reached, or is about to reach, that date.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass
from typing import Any

from education_system.systems.sixth_form.domain.assessment.exams_office import store
from education_system.systems.sixth_form.domain.assessment.exams_office.store import (
    ValidationError,
)

logger = logging.getLogger(__name__)

RETENTION_MONTHS: int = 12
RETENTION_NOTICE_DAYS: int = 30   # warn this long before retention ends

ISSUE_METHODS: tuple[str, ...] = (
    "Collected in person", "Collected by nominee (written authority)",
    "Posted (recorded delivery)", "Returned to board", "Destroyed after retention")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS exams_certificate_batches (
    batch_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    exam_board     TEXT NOT NULL,
    season         TEXT NOT NULL,
    year           INTEGER NOT NULL,
    received_date  TEXT NOT NULL,
    count_received INTEGER,
    notes          TEXT,
    recorded_by    TEXT,
    UNIQUE(exam_board, season, year, received_date)
);

CREATE TABLE IF NOT EXISTS exams_certificates (
    certificate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id       INTEGER NOT NULL,
    student_id     TEXT NOT NULL,
    certificate_ref TEXT,
    issued_date    TEXT,
    method         TEXT,
    collected_by   TEXT,
    signature_ref  TEXT,
    issued_by      TEXT,
    notes          TEXT,
    UNIQUE(batch_id, student_id),
    FOREIGN KEY (batch_id) REFERENCES exams_certificate_batches(batch_id)
        ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
);
"""


def init_db() -> None:
    store.ensure("certificates", _SCHEMA)


@dataclass
class Batch:
    batch_id: int
    exam_board: str
    season: str
    year: int
    received_date: str
    count_received: int | None
    notes: str | None
    recorded_by: str | None

    @property
    def retain_until(self) -> str:
        return store.add_months(self.received_date, RETENTION_MONTHS)


@dataclass
class Certificate:
    certificate_id: int
    batch_id: int
    student_id: str
    certificate_ref: str | None
    issued_date: str | None
    method: str | None
    collected_by: str | None
    signature_ref: str | None
    issued_by: str | None
    notes: str | None
    full_name: str | None = None
    exam_board: str | None = None
    series: str | None = None
    received_date: str | None = None

    @property
    def issued(self) -> bool:
        return bool(self.issued_date)

    @property
    def retain_until(self) -> str | None:
        return store.add_months(self.received_date, RETENTION_MONTHS) if self.received_date else None


def _batch(r) -> Batch:
    return Batch(**{k: r[k] for k in ("batch_id", "exam_board", "season", "year",
                                      "received_date", "count_received", "notes",
                                      "recorded_by")})


def record_batch(data: dict[str, Any], *, add_candidates: bool = True) -> Batch:
    """Log a delivery of certificates and (optionally) list the candidates
    expected in it — everyone who sat a paper with that board that series."""
    init_db()
    board = store.board(data.get("exam_board"))
    season, year = store.season_year(data.get("season"), data.get("year"))
    received = store.date(data.get("received_date"), "Received date") or store.today()
    try:
        with store.connect() as conn:
            cur = conn.execute(
                "INSERT INTO exams_certificate_batches (exam_board, season, year, "
                "received_date, count_received, notes, recorded_by) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (board, season, year, received,
                 store.integer(data.get("count_received"), "Number received", lo=0),
                 store.text(data.get("notes"), "Notes", limit=500), store.actor()))
            conn.commit()
            batch_id = int(cur.lastrowid)
    except store.IntegrityError as e:
        raise ValidationError("That delivery is already logged") from e
    if add_candidates:
        add_series_candidates(batch_id)
    out = get_batch(batch_id)
    assert out is not None
    return out


def add_series_candidates(batch_id: int) -> int:
    """Add a certificate line for every candidate who sat with the board."""
    from education_system.systems.sixth_form.domain.assessment.exam_entries import (
        exam_entries as _entries,
    )
    batch = get_batch(batch_id)
    if batch is None:
        raise ValidationError(f"No batch #{batch_id}")
    sids = sorted({e.student_id for e in _entries.list_entries(
        exam_board=batch.exam_board, season=batch.season, year=batch.year)
        if e.status != "Withdrawn"})
    added = 0
    with store.connect() as conn:
        for sid in sids:
            cur = conn.execute("INSERT OR IGNORE INTO exams_certificates (batch_id, student_id) "
                               "VALUES (?, ?)", (batch_id, sid))
            added += cur.rowcount
        conn.commit()
    return added


def add_certificate(batch_id: int, student_id: str,
                    certificate_ref: str | None = None) -> Certificate:
    init_db()
    if get_batch(batch_id) is None:
        raise ValidationError(f"No batch #{batch_id}")
    sid = store.student(student_id)
    with store.connect() as conn:
        conn.execute(
            "INSERT INTO exams_certificates (batch_id, student_id, certificate_ref) "
            "VALUES (?, ?, ?) ON CONFLICT(batch_id, student_id) DO UPDATE SET "
            "certificate_ref = COALESCE(excluded.certificate_ref, certificate_ref)",
            (batch_id, sid, store.text(certificate_ref, "Certificate ref", limit=60)))
        conn.commit()
    return next(c for c in list_certificates(batch_id=batch_id) if c.student_id == sid)


def get_batch(batch_id: int) -> Batch | None:
    init_db()
    with store.connect() as conn:
        r = conn.execute("SELECT * FROM exams_certificate_batches WHERE batch_id = ?",
                         (int(batch_id),)).fetchone()
    return _batch(r) if r else None


def list_batches(*, year: int | None = None) -> list[Batch]:
    init_db()
    sql = "SELECT * FROM exams_certificate_batches"
    args: list[Any] = []
    if year is not None:
        sql += " WHERE year = ?"
        args.append(int(year))
    with store.connect() as conn:
        return [_batch(r) for r in conn.execute(sql + " ORDER BY received_date DESC", args)]


def delete_batch(batch_id: int) -> bool:
    init_db()
    if any(c.issued for c in list_certificates(batch_id=batch_id)):
        raise ValidationError("Certificates in this batch have been issued — it is a "
                              "retained record")
    with store.connect() as conn:
        cur = conn.execute("DELETE FROM exams_certificate_batches WHERE batch_id = ?",
                           (int(batch_id),))
        conn.commit()
    return bool(cur.rowcount)


def list_certificates(*, batch_id: int | None = None, student_id: str | None = None,
                      unclaimed_only: bool = False) -> list[Certificate]:
    init_db()
    clauses, args = [], []
    if batch_id is not None:
        clauses.append("c.batch_id = ?")
        args.append(int(batch_id))
    if student_id:
        clauses.append("c.student_id = ?")
        args.append(student_id)
    if unclaimed_only:
        clauses.append("c.issued_date IS NULL")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    names = store.student_names()
    with store.connect() as conn:
        rows = conn.execute(
            f"""SELECT c.*, b.exam_board, b.season, b.year, b.received_date
                  FROM exams_certificates c
                  JOIN exams_certificate_batches b ON b.batch_id = c.batch_id
                {where} ORDER BY b.received_date DESC, c.student_id""", args).fetchall()
    out = []
    for r in rows:
        c = Certificate(**{k: r[k] for k in (
            "certificate_id", "batch_id", "student_id", "certificate_ref", "issued_date",
            "method", "collected_by", "signature_ref", "issued_by", "notes")})
        c.full_name = names.get(c.student_id)
        c.exam_board = r["exam_board"]
        c.series = f"{r['season']} {r['year']}"
        c.received_date = r["received_date"]
        out.append(c)
    return out


def issue(certificate_id: int, *, method: str, collected_by: str | None = None,
          signature_ref: str | None = None, issued_date: str | None = None,
          notes: str | None = None) -> Certificate:
    """Record that a certificate left the office, and who signed for it."""
    init_db()
    method = store.choice(method, "Method", ISSUE_METHODS)
    who = store.text(collected_by, "Collected by", limit=120)
    if method.startswith("Collected") and not who:
        raise ValidationError("Record who collected the certificate")
    if method.startswith("Collected") and not (signature_ref or "").strip():
        raise ValidationError("The collector must sign — record the signature "
                              "(e.g. 'signed issue sheet p.3')")
    with store.connect() as conn:
        r = conn.execute("SELECT c.issued_date, b.received_date FROM exams_certificates c "
                         "JOIN exams_certificate_batches b ON b.batch_id = c.batch_id "
                         "WHERE certificate_id = ?", (int(certificate_id),)).fetchone()
        if r is None:
            raise ValidationError(f"No certificate #{certificate_id}")
        if r["issued_date"]:
            raise ValidationError(f"Already issued on {r['issued_date']}")
        when = store.date(issued_date, "Issued date") or store.today()
        if method == "Destroyed after retention":
            until = store.add_months(r["received_date"], RETENTION_MONTHS)
            if when < until:
                raise ValidationError(f"Unclaimed certificates must be kept until {until}")
        conn.execute(
            """UPDATE exams_certificates SET issued_date = ?, method = ?, collected_by = ?,
                   signature_ref = ?, issued_by = ?, notes = COALESCE(?, notes)
               WHERE certificate_id = ?""",
            (when, method, who, store.text(signature_ref, "Signature", limit=120),
             store.actor(), store.text(notes, "Notes", limit=500), int(certificate_id)))
        conn.commit()
    return next(c for c in list_certificates() if c.certificate_id == int(certificate_id))


def retention_notices(*, within_days: int = RETENTION_NOTICE_DAYS) -> list[tuple[Certificate, int]]:
    """Unclaimed certificates near or past the end of retention.

    Returns ``(certificate, days until retention ends)`` — negative means
    the certificate may now be destroyed or returned.
    """
    today = _dt.date.fromisoformat(store.today())
    out = []
    for c in list_certificates(unclaimed_only=True):
        if not c.retain_until:
            continue
        left = (_dt.date.fromisoformat(c.retain_until) - today).days
        if left <= within_days:
            out.append((c, left))
    out.sort(key=lambda t: t[1])
    return out
