"""Subject access request (SAR) compiler and deadline tracking.

:mod:`gdpr` keeps the register of requests. This module does the work a
SAR actually needs:

* :func:`compile_sar` gathers everything the sixth form holds about a
  learner. It scans the sixth form database (``sqlite_master``) for every
  table with a ``student_id`` column (plus a few other learner-key
  columns), follows foreign keys one level down to the rows that hang
  off those (a bursary's disbursements, a booking's payments), and writes
  a JSON + CSV bundle into a dated folder under the sixth form data
  directory, with a manifest.

  **Safeguarding records are never put in the bundle.** Tables that hold
  them are listed, with record counts and ids only, in ``DSL_REVIEW.txt``
  for the designated safeguarding lead to decide on — disclosure of
  safeguarding information has its own exemptions and must be a person's
  decision. Tables and columns likely to hold **third-party data**
  (parents, referees, staff authors, free-text notes) are included but
  flagged in ``REDACTION_REVIEW.txt`` so they are checked and redacted
  by hand before anything is released.

* Deadline tracking: one calendar month from receipt
  (:func:`sar_deadline`), extendable once by up to two further months
  for complex or numerous requests (:func:`extend_deadline`), with
  :func:`deadlines` listing every open request by days remaining.

Every compilation is recorded against the request and in the sensitive
access log.
"""

from __future__ import annotations

import csv
import datetime as _dt
import json
import logging
import re
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domains.finance.domain import (
    finance_calendar as fc,
)
from education_system.systems.sixth_form.domain.governance.gdpr import gdpr

logger = logging.getLogger(__name__)

ValidationError = gdpr.ValidationError

#: Columns that identify the learner directly.
STUDENT_KEY_COLUMNS: tuple[str, ...] = (
    "student_id", "learner_ref", "original_student_id", "subject_ref",
)

#: A table whose name contains any of these holds safeguarding records.
#: Never exported; listed for the DSL. Keep in step with retention.py.
SAFEGUARDING_PATTERNS: tuple[str, ...] = (
    "safeguard", "child_protection", "prevent", "cp_plan", "cp_record",
    "lado", "dsl_",
)

#: Tables likely to carry other people's data -> why.
THIRD_PARTY_TABLE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("parent", "parent / guardian details"),
    ("reference", "written by a referee"),
    ("message", "correspondence with other people"),
    ("contact", "third-party contact details"),
    ("disciplinary", "witnesses and staff accounts"),
    ("behaviour", "other learners / staff may be named"),
    ("wellbeing", "special category; staff observations"),
    ("med_", "special category health data; clinician notes"),
    ("accessibility", "special category; assessor reports"),
    ("intervention", "staff notes"),
    ("early_warning", "staff judgements"),
    ("observation", "staff notes"),
    ("system_logs", "may name staff users"),
)

#: Columns likely to carry other people's data or free text.
THIRD_PARTY_COLUMN_PATTERNS: tuple[str, ...] = (
    "emergency_contact", "parent", "guardian", "witness", "referee",
    "reported_by", "recorded_by", "author", "staff", "note", "comment",
    "description", "detail",
)

# Internal tables that are never personal data in their own right.
_SKIP_TABLE_PREFIXES: tuple[str, ...] = ("sqlite_", "search_index_fts")

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

SAR_TYPE: str = "Subject Access (SAR)"
EXTENSION_MONTHS: int = 2

_REQUEST_COLUMNS: tuple[tuple[str, str], ...] = (
    ("extended_due_date", "TEXT"),
    ("extension_reason", "TEXT"),
    ("extended_on", "TEXT"),
    ("extended_by", "TEXT"),
    ("bundle_path", "TEXT"),
    ("compiled_at", "TEXT"),
    ("compiled_by", "TEXT"),
)


def _ident(name: str) -> str:
    """Quote a table / column name read from sqlite_master."""
    if not _IDENT_RE.match(name or ""):
        raise ValidationError(f"Unsafe identifier {name!r}")
    return f'"{name}"'


def is_safeguarding_table(name: str) -> bool:
    low = name.lower()
    return any(p in low for p in SAFEGUARDING_PATTERNS)


def _third_party_reason(name: str) -> str | None:
    low = name.lower()
    for pat, why in THIRD_PARTY_TABLE_PATTERNS:
        if pat in low:
            return why
    return None


# ── Plumbing ───────────────────────────────────────────────────────

def _db_path() -> str:
    return str(gdpr.DB_PATH)


def _connect(readonly: bool = False) -> db.Connection:
    paths.ensure_sixth_form_directories()
    if readonly:
        conn = db.connect(f"file:{_db_path()}?mode=ro", uri=True)
    else:
        conn = db.connect(_db_path())
        conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = db.Row
    return conn


_READY: set[str] = set()


def init_db() -> None:
    key = _db_path()
    if key in _READY:
        return
    gdpr.init_db()
    with _connect() as conn:
        have = {r[1] for r in conn.execute("PRAGMA table_info(gdpr_requests)")}
        for name, ddl in _REQUEST_COLUMNS:
            if name not in have:
                conn.execute(
                    f"ALTER TABLE gdpr_requests ADD COLUMN {name} {ddl}")
        conn.commit()
    _READY.add(key)


def _principal():
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    return access, access.current()


# ── Deadlines ─────────────────────────────────────────────────────

def sar_deadline(received: str) -> str:
    """One calendar month from receipt (31 Jan -> 28/29 Feb)."""
    return fc.add_months(received, 1)


@dataclass
class Deadline:
    request_id: int
    subject_name: str
    subject_ref: str | None
    request_type: str
    received_date: str
    due_date: str
    extended_due_date: str | None
    status: str
    compiled_at: str | None
    bundle_path: str | None

    @property
    def effective_due(self) -> str:
        return self.extended_due_date or self.due_date

    @property
    def days_remaining(self) -> int:
        return (_dt.date.fromisoformat(self.effective_due)
                - _dt.date.today()).days

    @property
    def overdue(self) -> bool:
        return self.days_remaining < 0

    @property
    def rag(self) -> str:
        d = self.days_remaining
        return "Overdue" if d < 0 else ("Due soon" if d <= 7 else "On track")


def _deadline(r: db.Row) -> Deadline:
    return Deadline(
        request_id=r["request_id"], subject_name=r["subject_name"],
        subject_ref=r["subject_ref"], request_type=r["request_type"],
        received_date=r["received_date"], due_date=r["due_date"],
        extended_due_date=r["extended_due_date"], status=r["status"],
        compiled_at=r["compiled_at"], bundle_path=r["bundle_path"])


def get_deadline(request_id: int) -> Deadline | None:
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT * FROM gdpr_requests WHERE request_id = ?",
                         (request_id,)).fetchone()
    return _deadline(r) if r else None


def deadlines(*, open_only: bool = True,
              sar_only: bool = False) -> list[Deadline]:
    """Requests by days remaining (most urgent first)."""
    init_db()
    clauses: list[str] = []
    args: list[Any] = []
    if open_only:
        clauses.append(
            f"status IN ({','.join('?' * len(gdpr.OPEN_REQUEST_STATUSES))})")
        args.extend(gdpr.OPEN_REQUEST_STATUSES)
    if sar_only:
        clauses.append("request_type = ?")
        args.append(SAR_TYPE)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            # db-audit: ignore[DBW001] - where is built from fixed clauses
            f"SELECT * FROM gdpr_requests {where}", args).fetchall()
    out = [_deadline(r) for r in rows]
    out.sort(key=lambda d: d.effective_due)
    return out


def extend_deadline(request_id: int, *, reason: str, by: str,
                    months: int = EXTENSION_MONTHS) -> Deadline:
    """Extend a request's deadline once, by up to two calendar months.

    UK GDPR allows this where the request is complex or the person has
    made several; the requester must be told within the first month,
    which is why the extension must be made before the original due date.
    """
    init_db()
    if not (reason or "").strip() or not (by or "").strip():
        raise ValidationError("An extension needs a reason and a name")
    if not 1 <= int(months) <= EXTENSION_MONTHS:
        raise ValidationError(
            f"An extension is 1 to {EXTENSION_MONTHS} months")
    d = get_deadline(request_id)
    if d is None:
        raise ValidationError(f"No request #{request_id}")
    if d.extended_due_date:
        raise ValidationError("This request has already been extended")
    if d.status not in gdpr.OPEN_REQUEST_STATUSES:
        raise ValidationError(f"Request #{request_id} is {d.status}")
    today = _dt.date.today().isoformat()
    if today > d.due_date:
        raise ValidationError(
            "Too late to extend: the requester must be told within the "
            "original one-month deadline")
    new_due = fc.add_months(d.due_date, int(months))
    with _connect() as conn:
        conn.execute(
            """UPDATE gdpr_requests SET extended_due_date=?,
                   extension_reason=?, extended_on=?, extended_by=?,
                   updated_at=datetime('now') WHERE request_id=?""",
            (new_due, reason.strip(), today, by.strip(), request_id))
        conn.commit()
    logger.info("GDPR request #%d extended to %s by %s", request_id,
                new_due, by)
    out = get_deadline(request_id)
    assert out is not None
    return out


# ── Compilation ───────────────────────────────────────────────────

@dataclass
class TableExtract:
    table: str
    key_column: str
    rows: list[dict[str, Any]]
    via: str | None = None              # parent table for FK-followed rows
    review_reason: str | None = None
    flagged_columns: list[str] = field(default_factory=list)


@dataclass
class SarBundle:
    student_id: str
    request_id: int | None
    folder: Path
    included: list[TableExtract]
    safeguarding: dict[str, list[Any]]   # table -> record ids (not exported)
    generated_at: str

    @property
    def total_rows(self) -> int:
        return sum(len(t.rows) for t in self.included)

    @property
    def review_tables(self) -> list[TableExtract]:
        return [t for t in self.included
                if t.review_reason or t.flagged_columns]


def _tables(conn: db.Connection) -> list[str]:
    return [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if not r[0].startswith(_SKIP_TABLE_PREFIXES)
        and _IDENT_RE.match(r[0])]


def _cols(conn: db.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(f"PRAGMA table_info({_ident(table)})")]


def _pk_columns(conn: db.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({_ident(table)})").fetchall()
    pks = sorted((r[5], r[1]) for r in rows if r[5])
    return [name for _n, name in pks] or ["rowid"]


def scan(student_id: str) -> tuple[list[TableExtract], dict[str, list[Any]]]:
    """Find every row about *student_id*. Read-only.

    Returns (extracts, safeguarding) — safeguarding maps each
    safeguarding table to the ids of the learner's records in it.
    """
    sid = (student_id or "").strip()
    if not sid:
        raise ValidationError("Student ID is required")
    extracts: list[TableExtract] = []
    safeguarding: dict[str, list[Any]] = {}
    with _connect(readonly=True) as conn:
        tables = _tables(conn)
        found: dict[str, list[db.Row]] = {}
        for t in tables:
            cols = _cols(conn, t)
            key = next((c for c in STUDENT_KEY_COLUMNS if c in cols), None)
            if key is None:
                continue
            if key == "subject_ref" and not t.startswith("gdpr_"):
                continue
            try:
                rows = conn.execute(
                    # db-audit: ignore[DBW001] - identifiers validated by _ident
                    f"SELECT rowid AS _rowid_, * FROM {_ident(t)} "
                    f"WHERE {_ident(key)} = ?", (sid,)).fetchall()
            except db.OperationalError as exc:
                logger.warning("SAR scan skipped %s: %s", t, exc)
                continue
            if not rows:
                continue
            if is_safeguarding_table(t):
                pk = _pk_columns(conn, t)[0]
                safeguarding[t] = [r[pk] if pk in r.keys() else r["_rowid_"]
                                   for r in rows]
                continue
            found[t] = rows
            extracts.append(_extract(t, key, rows, cols))
        # One level of FK children (a bursary's disbursements, a
        # booking's payments) that carry no student_id of their own.
        for child in tables:
            if child in found:
                continue
            for fk in conn.execute(
                    f"PRAGMA foreign_key_list({_ident(child)})").fetchall():
                parent, from_col, to_col = fk[2], fk[3], fk[4]
                if parent not in found or not to_col \
                        or not _IDENT_RE.match(from_col or ""):
                    continue
                keys = [r[to_col] for r in found[parent] if to_col in r.keys()]
                if not keys:
                    continue
                ph = ",".join("?" * len(keys))
                try:
                    rows = conn.execute(
                        # db-audit: ignore[DBW001] - identifiers validated by _ident
                        f"SELECT rowid AS _rowid_, * FROM {_ident(child)} "
                        f"WHERE {_ident(from_col)} IN ({ph})", keys).fetchall()
                except db.OperationalError as exc:
                    logger.warning("SAR scan skipped %s: %s", child, exc)
                    continue
                if not rows:
                    continue
                if is_safeguarding_table(child) or is_safeguarding_table(
                        parent):
                    safeguarding.setdefault(child, []).extend(
                        r["_rowid_"] for r in rows)
                    continue
                extracts.append(_extract(child, from_col, rows,
                                         _cols(conn, child), via=parent))
                break
    return extracts, safeguarding


def _extract(table: str, key: str, rows: list[db.Row],
             cols: list[str], via: str | None = None) -> TableExtract:
    data = [{k: r[k] for k in r.keys() if k != "_rowid_"} for r in rows]
    flagged = [c for c in cols
               if any(p in c.lower() for p in THIRD_PARTY_COLUMN_PATTERNS)
               and any(d.get(c) not in (None, "") for d in data)]
    return TableExtract(table=table, key_column=key, rows=data, via=via,
                        review_reason=_third_party_reason(table),
                        flagged_columns=flagged)


def _bundle_folder(student_id: str) -> Path:
    base = paths.SIXTH_FORM_DATA_DIR / "gdpr" / "sar"
    stem = f"{_dt.date.today().isoformat()}_{re.sub(r'[^A-Za-z0-9_-]', '_', student_id)}"
    folder = base / stem
    n = 2
    while folder.exists():
        folder = base / f"{stem}_{n}"
        n += 1
    folder.mkdir(parents=True)
    return folder


def compile_sar(student_id: str, *, request_id: int | None = None,
                compiled_by: str | None = None) -> SarBundle:
    """Compile a learner's SAR bundle. See the module docstring."""
    access, p = _principal()
    p.require(access.GOVERNANCE, "subject access requests")
    init_db()
    from education_system.systems.sixth_form.domain.learners.students import (
        students as _students,
    )
    student = _students.get_student((student_id or "").strip())
    if student is None:
        raise ValidationError(f"No student with id {student_id}")
    if request_id is not None:
        req = gdpr.get_request(int(request_id))
        if req is None:
            raise ValidationError(f"No request #{request_id}")
        if req.request_type != SAR_TYPE:
            raise ValidationError(
                f"Request #{request_id} is a {req.request_type}, not a SAR")
    who = (compiled_by or p.username or "").strip() or "unknown"
    extracts, safeguarding = scan(student.student_id)
    folder = _bundle_folder(student.student_id)
    generated = _dt.datetime.now().isoformat(timespec="seconds")

    data_dir = folder / "data"
    data_dir.mkdir()
    for ex in extracts:
        stem = ex.table if ex.via is None else f"{ex.table}__via_{ex.via}"
        (data_dir / f"{stem}.json").write_text(
            json.dumps(ex.rows, indent=2, default=str), encoding="utf-8")
        with (data_dir / f"{stem}.csv").open("w", newline="",
                                             encoding="utf-8") as fh:
            cols = list(ex.rows[0].keys()) if ex.rows else []
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for row in ex.rows:
                w.writerow({k: ("" if v is None else v)
                            for k, v in row.items()})

    manifest = {
        "student_id": student.student_id,
        "student_name": student.full_name,
        "request_id": request_id,
        "generated_at": generated,
        "generated_by": who,
        "database": Path(_db_path()).name,
        "tables": [{"table": e.table, "key": e.key_column, "via": e.via,
                    "rows": len(e.rows), "review_reason": e.review_reason,
                    "flagged_columns": e.flagged_columns}
                   for e in extracts],
        "safeguarding_excluded": {t: len(ids)
                                  for t, ids in safeguarding.items()},
        "status": "DRAFT - not for release until redaction review and DSL "
                  "review are complete",
    }
    (folder / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8")

    review = [
        "REDACTION REVIEW - check before release",
        "=" * 40,
        f"Learner: {student.student_id} {student.full_name}",
        f"Generated: {generated} by {who}", "",
        "These tables/columns may contain other people's personal data or",
        "free text naming others. Review each and redact third-party data",
        "(unless they consent or it is reasonable to disclose).", "",
    ]
    for ex in extracts:
        if ex.review_reason or ex.flagged_columns:
            review.append(f"* {ex.table}"
                          + (f" (via {ex.via})" if ex.via else "")
                          + f" - {len(ex.rows)} row(s)")
            if ex.review_reason:
                review.append(f"    why: {ex.review_reason}")
            if ex.flagged_columns:
                review.append("    columns: " + ", ".join(ex.flagged_columns))
    (folder / "REDACTION_REVIEW.txt").write_text("\n".join(review) + "\n",
                                                 encoding="utf-8")

    dsl = [
        "FOR THE DESIGNATED SAFEGUARDING LEAD",
        "=" * 36,
        f"Learner: {student.student_id} {student.full_name}",
        f"Generated: {generated} by {who}", "",
        "Safeguarding records are NOT included in this bundle. The DSL must",
        "decide what (if anything) can be disclosed, applying the relevant",
        "exemptions (e.g. serious harm, third-party information).", "",
    ]
    if safeguarding:
        for t, ids in sorted(safeguarding.items()):
            dsl.append(f"* {t}: {len(ids)} record(s) - ids "
                       + ", ".join(str(i) for i in ids[:50])
                       + (" ..." if len(ids) > 50 else ""))
    else:
        dsl.append("No safeguarding records were found for this learner.")
    (folder / "DSL_REVIEW.txt").write_text("\n".join(dsl) + "\n",
                                           encoding="utf-8")

    if request_id is not None:
        with _connect() as conn:
            conn.execute(
                """UPDATE gdpr_requests SET bundle_path=?, compiled_at=?,
                       compiled_by=?, status=CASE WHEN status IN
                       ('Received', 'Identity Verified') THEN 'In Review'
                       ELSE status END, updated_at=datetime('now')
                   WHERE request_id=?""",
                (str(folder), generated, who, int(request_id)))
            conn.commit()
    access.log_sensitive_access(p, "gdpr", "sar_compile",
                                student_id=student.student_id,
                                record_ref=str(folder))
    logger.info("SAR bundle for %s: %d table(s), %d row(s), %d safeguarding "
                "table(s) listed for the DSL -> %s", student.student_id,
                len(extracts), sum(len(e.rows) for e in extracts),
                len(safeguarding), folder)
    return SarBundle(student_id=student.student_id, request_id=request_id,
                     folder=folder, included=extracts,
                     safeguarding=safeguarding, generated_at=generated)
