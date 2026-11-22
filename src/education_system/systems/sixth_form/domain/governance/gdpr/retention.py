"""Data retention schedule for the Sixth Form System.

Two parts, deliberately separated:

1. **The schedule and the dry run** (always available). Each data
   category (``gdpr_retention_schedule``) names the tables it covers, how
   long the data is kept, what starts the clock (the learner's leaving
   date, or a date column on each record) and what happens at the end
   (anonymise or delete). :func:`dry_run` reports, per category, which
   learners and how many records are past retention. It changes nothing.

2. **Acting on it** (:func:`apply_category`) — shipped **disabled**. It
   only runs when *all* of these hold:

   * the college-wide switch is on (``set_purge_enabled``; off by
     default, admin only);
   * the category itself has been opted in (``enabled``; every category
     starts disabled);
   * the caller is an admin;
   * a second confirmation is given — the category name typed back;
   * a full backup of the database has just been written to
     ``paths.system_backup_dir("sixth_form", "gdpr_retention")``.

   Every run is logged (``gdpr_retention_log``) with the backup path.

**Safeguarding records are never touched.** They have their own
retention rules (normally until the learner's 25th birthday or longer,
decided by the DSL). Any table matching :data:`sar.SAFEGUARDING_PATTERNS`
is refused when a category is saved *and* again when one is applied.

The learner's leaving date is derived from the records that hold it:
the alumni record's ``leaving_date``, the latest ILR learning-aim
``actual_end_date``, or — for a learner whose status is no longer
Active — the date their status changed (``students.transferred_at``).
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system import paths
from education_system.systems.sixth_form.domains.finance.domain import (
    finance_calendar as fc,
)
from education_system.systems.sixth_form.domain.governance.gdpr import gdpr, sar

logger = logging.getLogger(__name__)

ValidationError = gdpr.ValidationError

TRIGGER_LEAVING: str = "leaving_date"
TRIGGER_RECORD: str = "record_date"
TRIGGERS: tuple[str, ...] = (TRIGGER_LEAVING, TRIGGER_RECORD)

ACTION_ANONYMISE: str = "anonymise"
ACTION_DELETE: str = "delete"
ACTIONS: tuple[str, ...] = (ACTION_ANONYMISE, ACTION_DELETE)

ANONYMISED: str = "[anonymised]"

# Column-name fragments treated as personal / free text when anonymising.
PII_COLUMN_PATTERNS: tuple[str, ...] = (
    "name", "email", "phone", "address", "postcode", "note", "comment",
    "description", "reason", "detail", "contact", "date_of_birth", "dob",
    "household", "medical", "dietary", "evidence", "nhs", "uln",
    "reference", "relation", "statement", "text", "summary",
)
# ...but never these (keys, money, dates, states).
_KEEP_COLUMNS: tuple[str, ...] = (
    "student_id", "status", "state", "amount", "created_at", "updated_at",
)

# Suggested starting schedule. These are starting points for the DPO
# to confirm against the college's records-management policy (e.g. the
# IRMS toolkit for schools) — not legal advice. Only tables that exist
# in this database and hold a student_id are loaded. All start disabled.
SUGGESTED_SCHEDULE: tuple[dict[str, Any], ...] = (
    {"category": "Bursary and free meals",
     "description": "16-19 Bursary Fund and free meals records. Funding "
                    "audit: 6 years after the learner leaves.",
     "tables": ["bursary_applications", "bursary_schedule",
                "free_meal_entitlements", "free_meal_usage"],
     "retention_months": 72, "trigger": TRIGGER_LEAVING,
     "action": ACTION_ANONYMISE},
    {"category": "Fees and invoices",
     "description": "Fee items, invoices, remissions and fee profiles. "
                    "Financial records: 6 years after leaving.",
     "tables": ["fee_items", "fee_invoices", "fee_remissions",
                "fee_student_profiles", "receipts"],
     "retention_months": 72, "trigger": TRIGGER_LEAVING,
     "action": ACTION_ANONYMISE},
    {"category": "Trips",
     "description": "Trip bookings (consent, medical and dietary notes). "
                    "6 years after leaving, then anonymised.",
     "tables": ["trip_bookings"],
     "retention_months": 72, "trigger": TRIGGER_LEAVING,
     "action": ACTION_ANONYMISE},
    {"category": "Attendance",
     "description": "Session attendance marks: 3 years from the date of "
                    "each mark.",
     "tables": ["attendance_records", "attendance_daily_sessions"],
     "retention_months": 36, "trigger": TRIGGER_RECORD,
     "date_column": "date", "action": ACTION_DELETE},
    {"category": "Behaviour",
     "description": "Behaviour log: 6 years after leaving.",
     "tables": ["behaviour_entries"],
     "retention_months": 72, "trigger": TRIGGER_LEAVING,
     "action": ACTION_ANONYMISE},
    {"category": "Library",
     "description": "Loans, fines and reservations: 1 year after leaving.",
     "tables": ["library_loans", "library_fines", "library_reservations"],
     "retention_months": 12, "trigger": TRIGGER_LEAVING,
     "action": ACTION_DELETE},
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS gdpr_retention_schedule (
    category          TEXT PRIMARY KEY,
    description       TEXT,
    tables            TEXT NOT NULL,
    retention_months  INTEGER NOT NULL,
    trigger           TEXT NOT NULL DEFAULT 'leaving_date',
    date_column       TEXT,
    action            TEXT NOT NULL DEFAULT 'anonymise',
    enabled           INTEGER NOT NULL DEFAULT 0,
    notes             TEXT,
    updated_by        TEXT,
    updated_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gdpr_retention_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    updated_by TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS gdpr_retention_log (
    log_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    category       TEXT NOT NULL,
    action         TEXT NOT NULL,
    learners       INTEGER NOT NULL DEFAULT 0,
    rows_affected  INTEGER NOT NULL DEFAULT 0,
    detail         TEXT,
    backup_path    TEXT,
    run_by         TEXT NOT NULL,
    run_at         TEXT DEFAULT (datetime('now'))
);
"""


@dataclass
class Category:
    category: str
    description: str | None
    tables: list[str]
    retention_months: int
    trigger: str
    date_column: str | None
    action: str
    enabled: bool
    notes: str | None
    updated_by: str | None
    updated_at: str | None


@dataclass
class TableFinding:
    table: str
    rows: int
    note: str | None = None


@dataclass
class CategoryFinding:
    category: Category
    cutoff: str
    learners: list[str] = field(default_factory=list)
    tables: list[TableFinding] = field(default_factory=list)
    no_leaving_date: list[str] = field(default_factory=list)

    @property
    def rows(self) -> int:
        return sum(t.rows for t in self.tables)


# ── Plumbing ───────────────────────────────────────────────────────

def _db_path() -> str:
    return str(gdpr.DB_PATH)


def _connect() -> db.Connection:
    paths.ensure_sixth_form_directories()
    conn = db.connect(_db_path())
    conn.row_factory = db.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


_READY: set[str] = set()


def init_db() -> None:
    key = _db_path()
    if key in _READY:
        return
    gdpr.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    _READY.add(key)


def _row(r: db.Row) -> Category:
    return Category(
        category=r["category"], description=r["description"],
        tables=[t for t in json.loads(r["tables"] or "[]")],
        retention_months=int(r["retention_months"]), trigger=r["trigger"],
        date_column=r["date_column"], action=r["action"],
        enabled=bool(r["enabled"]), notes=r["notes"],
        updated_by=r["updated_by"], updated_at=r["updated_at"])


def _table_columns(conn: db.Connection, table: str) -> list[str]:
    return [r[1] for r in conn.execute(
        f"PRAGMA table_info({sar._ident(table)})")]


def _existing_tables(conn: db.Connection) -> set[str]:
    return {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}


# ── Schedule ──────────────────────────────────────────────────────

def _validate(d: dict[str, Any], conn: db.Connection) -> dict[str, Any]:
    name = (d.get("category") or "").strip()
    if not name:
        raise ValidationError("Category name is required")
    tables = d.get("tables") or []
    if isinstance(tables, str):
        tables = [t.strip() for t in tables.split(",") if t.strip()]
    if not tables:
        raise ValidationError("A category must cover at least one table")
    existing = _existing_tables(conn)
    for t in tables:
        sar._ident(t)
        if sar.is_safeguarding_table(t):
            raise ValidationError(
                f"{t} holds safeguarding records, which have their own "
                "retention and are never handled here")
        if t not in existing:
            raise ValidationError(f"No table called {t}")
    trigger = (d.get("trigger") or TRIGGER_LEAVING).strip()
    if trigger not in TRIGGERS:
        raise ValidationError(f"Trigger must be one of: {', '.join(TRIGGERS)}")
    date_col = (d.get("date_column") or "").strip() or None
    for t in tables:
        cols = _table_columns(conn, t)
        if trigger == TRIGGER_LEAVING and "student_id" not in cols:
            raise ValidationError(
                f"{t} has no student_id, so a leaving-date trigger cannot "
                "apply to it")
        if trigger == TRIGGER_RECORD:
            if not date_col:
                raise ValidationError(
                    "A record-date trigger needs the date column to use")
            sar._ident(date_col)
            if date_col not in cols:
                raise ValidationError(f"{t} has no column {date_col}")
    action = (d.get("action") or ACTION_ANONYMISE).strip()
    if action not in ACTIONS:
        raise ValidationError(f"Action must be one of: {', '.join(ACTIONS)}")
    try:
        months = int(d.get("retention_months"))
    except (TypeError, ValueError):
        raise ValidationError("Retention period must be whole months") from None
    if months < 1 or months > 1200:
        raise ValidationError("Retention period must be 1..1200 months")
    return {"category": name,
            "description": (d.get("description") or "").strip() or None,
            "tables": json.dumps(tables), "retention_months": months,
            "trigger": trigger, "date_column": date_col, "action": action,
            "notes": (d.get("notes") or "").strip() or None}


def save_category(d: dict[str, Any], *, by: str) -> Category:
    """Create or change a category. Saving never enables it."""
    init_db()
    with _connect() as conn:
        p = _validate(d, conn)
        conn.execute(
            """INSERT INTO gdpr_retention_schedule (category, description,
                   tables, retention_months, trigger, date_column, action,
                   enabled, notes, updated_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
               ON CONFLICT(category) DO UPDATE SET
                   description=excluded.description, tables=excluded.tables,
                   retention_months=excluded.retention_months,
                   trigger=excluded.trigger,
                   date_column=excluded.date_column, action=excluded.action,
                   notes=excluded.notes, updated_by=excluded.updated_by,
                   updated_at=datetime('now')""",
            (p["category"], p["description"], p["tables"],
             p["retention_months"], p["trigger"], p["date_column"],
             p["action"], p["notes"], (by or "").strip() or None))
        conn.commit()
    out = get_category(p["category"])
    assert out is not None
    return out


def get_category(name: str) -> Category | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM gdpr_retention_schedule WHERE category = ?",
            (name,)).fetchone()
    return _row(r) if r else None


def list_categories() -> list[Category]:
    init_db()
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM gdpr_retention_schedule "
                            "ORDER BY category").fetchall()
    return [_row(r) for r in rows]


def delete_category(name: str) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM gdpr_retention_schedule WHERE category = ?", (name,))
        conn.commit()
    return bool(cur.rowcount)


def load_suggested_schedule(*, by: str) -> list[Category]:
    """Add the suggested categories that are not defined yet, keeping only
    tables that exist here (and hold student_id for leaving triggers).
    Everything loads disabled."""
    init_db()
    out: list[Category] = []
    with _connect() as conn:
        existing = _existing_tables(conn)
        have = {r[0] for r in conn.execute(
            "SELECT category FROM gdpr_retention_schedule")}
        plans: list[dict[str, Any]] = []
        for spec in SUGGESTED_SCHEDULE:
            if spec["category"] in have:
                continue
            tables = []
            for t in spec["tables"]:
                if t not in existing:
                    continue
                cols = _table_columns(conn, t)
                if spec["trigger"] == TRIGGER_LEAVING and \
                        "student_id" not in cols:
                    continue
                if spec["trigger"] == TRIGGER_RECORD and \
                        spec.get("date_column") not in cols:
                    continue
                tables.append(t)
            if tables:
                plans.append({**spec, "tables": tables})
    for spec in plans:
        out.append(save_category(spec, by=by))
    return out


# ── Switches ──────────────────────────────────────────────────────

def purge_enabled() -> bool:
    """The college-wide switch. Off unless an admin has turned it on."""
    init_db()
    with _connect() as conn:
        r = conn.execute("SELECT value FROM gdpr_retention_settings "
                         "WHERE key = 'purge_enabled'").fetchone()
    return bool(r and r["value"] == "1")


def _require_admin(action: str):
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = access.current()
    if not p.is_admin:
        raise access.AccessDenied(
            f"{p.username or 'This account'} is not an administrator; "
            f"only an admin may {action}.")
    return access, p


def set_purge_enabled(on: bool) -> bool:
    access, p = _require_admin("change the retention purge switch")
    init_db()
    with _connect() as conn:
        conn.execute(
            """INSERT INTO gdpr_retention_settings (key, value, updated_by)
               VALUES ('purge_enabled', ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                   updated_by=excluded.updated_by,
                   updated_at=datetime('now')""",
            ("1" if on else "0", p.username))
        conn.commit()
    access.log_sensitive_access(p, "gdpr", "retention_switch_"
                                + ("on" if on else "off"))
    logger.warning("GDPR retention purge switch turned %s by %s",
                   "ON" if on else "off", p.username)
    return on


def set_category_enabled(name: str, on: bool) -> Category:
    access, p = _require_admin("opt a retention category in or out")
    cat = get_category(name)
    if cat is None:
        raise ValidationError(f"No retention category {name!r}")
    with _connect() as conn:
        conn.execute(
            "UPDATE gdpr_retention_schedule SET enabled=?, updated_by=?, "
            "updated_at=datetime('now') WHERE category=?",
            (1 if on else 0, p.username, name))
        conn.commit()
    access.log_sensitive_access(p, "gdpr", "retention_category_"
                                + ("enabled" if on else "disabled"),
                                record_ref=name)
    out = get_category(name)
    assert out is not None
    return out


# ── Leaving dates ─────────────────────────────────────────────────

def leaving_dates(conn: db.Connection) -> dict[str, str | None]:
    """Every learner -> leaving date (None = no date found).

    Active learners map to None and are never past retention.
    """
    tables = _existing_tables(conn)
    out: dict[str, str | None] = {}
    status: dict[str, str] = {}
    for r in conn.execute(
            "SELECT student_id, status, transferred_at FROM students"
            if "transferred_at" in _table_columns(conn, "students")
            else "SELECT student_id, status, NULL AS transferred_at "
                 "FROM students"):
        status[r["student_id"]] = r["status"] or "Active"
        out[r["student_id"]] = (None if (r["status"] or "Active") == "Active"
                                else (r["transferred_at"] or "")[:10] or None)

    def later(sid: str, d: str | None) -> None:
        if not d or sid not in out or status.get(sid) == "Active":
            return
        d = d[:10]
        if out[sid] is None or d > (out[sid] or ""):
            out[sid] = d

    if "alumni" in tables and {"original_student_id", "leaving_date"} <= set(
            _table_columns(conn, "alumni")):
        for r in conn.execute("SELECT original_student_id, leaving_date "
                              "FROM alumni WHERE leaving_date IS NOT NULL"):
            later(r[0], r[1])
    if "learner_aims" in tables:
        for r in conn.execute(
                "SELECT learner_ref, MAX(actual_end_date) FROM learner_aims "
                "WHERE actual_end_date IS NOT NULL GROUP BY learner_ref"):
            later(r[0], r[1])
    return out


# ── Dry run ───────────────────────────────────────────────────────

def _assess(conn: db.Connection, cat: Category,
            leavers: dict[str, str | None], today: str) -> CategoryFinding:
    cutoff = fc.add_months(today, -cat.retention_months)
    finding = CategoryFinding(category=cat, cutoff=cutoff)
    existing = _existing_tables(conn)
    if cat.trigger == TRIGGER_LEAVING:
        expired = sorted(s for s, d in leavers.items() if d and d < cutoff)
        finding.learners = expired
        finding.no_leaving_date = sorted(
            s for s, d in leavers.items() if d is None
            and conn.execute("SELECT status FROM students WHERE student_id=?",
                             (s,)).fetchone()[0] not in (None, "Active"))
    for t in cat.tables:
        if t not in existing:
            finding.tables.append(TableFinding(t, 0, "table missing"))
            continue
        if sar.is_safeguarding_table(t):
            finding.tables.append(TableFinding(t, 0, "SAFEGUARDING - refused"))
            continue
        if cat.trigger == TRIGGER_LEAVING:
            if not finding.learners:
                finding.tables.append(TableFinding(t, 0))
                continue
            n = 0
            for i in range(0, len(finding.learners), 500):
                chunk = finding.learners[i:i + 500]
                n += conn.execute(
                    # db-audit: ignore[DBW001] - identifier validated by sar._ident
                    f"SELECT COUNT(*) FROM {sar._ident(t)} WHERE student_id "
                    f"IN ({','.join('?' * len(chunk))})", chunk).fetchone()[0]
            finding.tables.append(TableFinding(t, n))
        else:
            col = cat.date_column or ""
            if col not in _table_columns(conn, t):
                finding.tables.append(TableFinding(t, 0, f"no column {col}"))
                continue
            n = conn.execute(
                # db-audit: ignore[DBW001] - identifiers validated by sar._ident
                f"SELECT COUNT(*) FROM {sar._ident(t)} WHERE "
                f"{sar._ident(col)} < ?", (cutoff,)).fetchone()[0]
            finding.tables.append(TableFinding(t, n))
    return finding


def dry_run(categories: list[str] | None = None, *,
            on: str | None = None) -> list[CategoryFinding]:
    """What each category would act on today. Reads only."""
    init_db()
    today = on or _dt.date.today().isoformat()
    cats = [c for c in list_categories()
            if categories is None or c.category in categories]
    with _connect() as conn:
        leavers = leaving_dates(conn)
        return [_assess(conn, c, leavers, today) for c in cats]


def dry_run_text(findings: list[CategoryFinding]) -> str:
    """The dry run as a plain report."""
    lines = ["RETENTION DRY RUN - nothing has been changed",
             f"Run {_dt.datetime.now().isoformat(timespec='minutes')}",
             f"Purge switch: {'ON' if purge_enabled() else 'off'}", ""]
    for f in findings:
        c = f.category
        lines.append(f"{c.category}  [{'ENABLED' if c.enabled else 'disabled'}]"
                     f"  {c.action} after {c.retention_months} months from "
                     f"{c.trigger.replace('_', ' ')}  (cutoff {f.cutoff})")
        if c.trigger == TRIGGER_LEAVING:
            lines.append(f"    learners past retention: {len(f.learners)}"
                         + (f" ({', '.join(f.learners[:10])}"
                            + (" ..." if len(f.learners) > 10 else "") + ")"
                            if f.learners else ""))
            if f.no_leaving_date:
                lines.append(f"    leavers with no leaving date (not "
                             f"assessed): {len(f.no_leaving_date)}")
        for t in f.tables:
            lines.append(f"    {t.table:<32} {t.rows:>7} row(s)"
                         + (f"  ({t.note})" if t.note else ""))
        lines.append("")
    lines.append("Safeguarding records are excluded from every category.")
    return "\n".join(lines)


# ── Acting (disabled by default) ──────────────────────────────────

def backup_database(label: str) -> Path:
    """Copy the whole sixth form database to the GDPR retention backup
    folder using SQLite's online backup. Returns the backup path."""
    folder = paths.system_backup_dir("sixth_form", "gdpr_retention")
    folder.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(ch if ch.isalnum() else "_" for ch in label)[:40]
    target = folder / f"{Path(_db_path()).stem}_{stamp}_{safe}.db"
    src = db.connect(_db_path())
    try:
        dst = db.connect(str(target))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return target


def _scrub_columns(conn: db.Connection, table: str) -> list[tuple[str, bool]]:
    """(column, not_null) pairs to clear when anonymising *table*."""
    out = []
    for r in conn.execute(f"PRAGMA table_info({sar._ident(table)})"):
        name, ctype, notnull, pk = r[1], (r[2] or "").upper(), r[3], r[5]
        low = name.lower()
        if pk or low in _KEEP_COLUMNS or low.endswith("_id"):
            continue
        if "TEXT" not in ctype and ctype not in ("", "VARCHAR"):
            continue
        if any(p in low for p in PII_COLUMN_PATTERNS):
            out.append((name, bool(notnull)))
    return out


def apply_category(name: str, *, confirm: str, actor: str | None = None,
                   on: str | None = None) -> dict[str, Any]:
    """Anonymise or delete what one category's dry run found.

    Refuses unless the purge switch is on, the category is enabled, the
    caller is an admin and *confirm* repeats the category name exactly.
    Backs the database up first.
    """
    access, p = _require_admin("run a retention purge")
    init_db()
    if not purge_enabled():
        raise ValidationError(
            "Retention purges are switched off for this college. An admin "
            "must turn the purge switch on first.")
    cat = get_category(name)
    if cat is None:
        raise ValidationError(f"No retention category {name!r}")
    if not cat.enabled:
        raise ValidationError(
            f"Category {name!r} has not been opted in (it is disabled)")
    if confirm != cat.category:
        raise ValidationError(
            "Type the category name exactly to confirm the purge")
    for t in cat.tables:
        if sar.is_safeguarding_table(t):
            raise ValidationError(
                f"{t} holds safeguarding records — refusing to touch it")
    who = (actor or p.username or "").strip() or "unknown"
    finding = dry_run([cat.category], on=on)[0]
    if finding.rows == 0:
        return {"category": cat.category, "rows": 0, "learners": 0,
                "backup": None}
    backup = backup_database(cat.category)
    affected = 0
    detail: dict[str, int] = {}
    with _connect() as conn:
        try:
            conn.execute("BEGIN")
            for t in cat.tables:
                q = sar._ident(t)
                if cat.trigger == TRIGGER_LEAVING:
                    if not finding.learners:
                        continue
                    where_sql, keys = None, finding.learners
                else:
                    where_sql = f"{sar._ident(cat.date_column or '')} < ?"
                    keys = [finding.cutoff]
                chunks = ([keys[i:i + 500] for i in range(0, len(keys), 500)]
                          if where_sql is None else [keys])
                n = 0
                for chunk in chunks:
                    cond = (where_sql if where_sql is not None else
                            f"student_id IN ({','.join('?' * len(chunk))})")
                    if cat.action == ACTION_DELETE:
                        # db-audit: ignore[DBW001] - identifiers validated by sar._ident
                        cur = conn.execute(f"DELETE FROM {q} WHERE {cond}",
                                           chunk)
                    else:
                        cols = _scrub_columns(conn, t)
                        if not cols:
                            continue
                        sets = ", ".join(
                            f"{sar._ident(c)} = " + ("?" if nn else "NULL")
                            for c, nn in cols)
                        args = [ANONYMISED for _c, nn in cols if nn]
                        # db-audit: ignore[DBW001] - identifiers validated by sar._ident
                        cur = conn.execute(f"UPDATE {q} SET {sets} WHERE {cond}",
                                           args + list(chunk))
                    n += cur.rowcount
                detail[t] = n
                affected += n
            bad = conn.execute("PRAGMA foreign_key_check").fetchall()
            if bad:
                raise ValidationError(
                    f"Foreign-key check failed ({len(bad)} row(s)); "
                    "nothing was changed")
            conn.execute(
                """INSERT INTO gdpr_retention_log (category, action, learners,
                       rows_affected, detail, backup_path, run_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cat.category, cat.action, len(finding.learners), affected,
                 json.dumps(detail), str(backup), who))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    access.log_sensitive_access(p, "gdpr", f"retention_{cat.action}",
                                record_ref=f"{cat.category}: {affected} rows")
    logger.warning("Retention %s on %r by %s: %d row(s); backup %s",
                   cat.action, cat.category, who, affected, backup)
    return {"category": cat.category, "rows": affected,
            "learners": len(finding.learners), "detail": detail,
            "backup": str(backup)}


def run_log(limit: int = 200) -> list[dict[str, Any]]:
    init_db()
    with _connect() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM gdpr_retention_log ORDER BY log_id DESC LIMIT ?",
            (int(limit),))]
