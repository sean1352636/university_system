"""The sixth form job scheduler: registry, persisted state, locking, runs.

Nothing in the sixth form used to run on its own — scheduled
announcements never went live, scheduled notifications never sent,
nightly scans only ran when someone pressed a button. This module is the
one place that makes things happen on a timetable.

* **Registry** — each job is a :class:`JobSpec`: a name, a function, a
  schedule (every N minutes, or daily at ``HH:MM``) and whether it is on
  by default. Jobs register themselves from :mod:`.jobs`.
* **State** — ``sf_scheduler_jobs`` holds what staff changed (enabled,
  schedule overrides) and when each job is next due;
  ``sf_scheduler_runs`` is the history: one row per run with status,
  summary, error and duration.
* **Locking** — ``sf_scheduler_locks`` holds one leased row per running
  job, taken inside ``BEGIN IMMEDIATE``, so two app instances (or the
  GUI and a cron run) never run the same job at once. A crashed run's
  lease expires and its history row is marked *Abandoned*.
* **Catch-up** — after a run, the next due time is computed from *now*,
  never from the missed slot, so a daily job missed for a week runs once
  on the next start rather than seven times.
* **Principal** — jobs run as an explicit system principal
  (:func:`system_principal`), bound in a context variable for the
  running thread only. The signed-in user's principal is never widened,
  and access checks inside the jobs still apply.

Jobs return a :class:`JobResult` (or a plain summary string). A job that
finishes with ``errors`` is recorded as *Partial*; a job that raises is
*Failed* with its traceback. Jobs never touch Tk.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import logging
import os
import socket
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from education_system import paths
from education_system.systems.sixth_form.infrastructure import database as _sql

logger = logging.getLogger(__name__)

# ── Vocabularies ────────────────────────────────────────────────────

RUNNING = "Running"
SUCCESS = "Success"
PARTIAL = "Partial"
FAILED = "Failed"
SKIPPED = "Skipped"
ABANDONED = "Abandoned"
STATUSES: tuple[str, ...] = (RUNNING, SUCCESS, PARTIAL, FAILED, SKIPPED,
                             ABANDONED)

TRIGGER_SCHEDULE = "schedule"
TRIGGER_CATCH_UP = "catch-up"
TRIGGER_MANUAL = "manual"
TRIGGER_HEADLESS = "headless"

SYSTEM_USERNAME = "system:scheduler"

#: A daily job whose slot passed longer ago than this is a catch-up run.
CATCH_UP_GRACE = _dt.timedelta(minutes=15)
#: A failed daily job is retried this soon (if before its next slot).
FAILED_RETRY = _dt.timedelta(hours=1)
#: History older than this is pruned by the housekeeping job.
HISTORY_KEEP_DAYS = 90
MAX_TEXT = 8000

_FMT = "%Y-%m-%d %H:%M:%S"

#: Identifies this process as a lock owner.
OWNER = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"


class ValidationError(ValueError):
    """Bad input to the scheduler (unknown job, bad schedule)."""


# ── Registry ────────────────────────────────────────────────────────

@dataclass
class JobResult:
    """What a job did. ``errors`` makes the run *Partial*."""

    summary: str = ""
    errors: list[str] = field(default_factory=list)

    def add(self, part: str) -> None:
        self.summary = f"{self.summary}; {part}" if self.summary else part


@dataclass(frozen=True)
class JobSpec:
    name: str
    title: str
    func: Callable[[], Any]
    description: str = ""
    category: str = "General"
    interval_minutes: int | None = None
    daily_at: str | None = None
    enabled: bool = True
    #: How long the lock is held before another instance may assume the
    #: run died.
    lease_minutes: int = 60


_REGISTRY: dict[str, JobSpec] = {}


def _check_daily(value: str | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        t = _dt.datetime.strptime(str(value).strip(), "%H:%M")
    except ValueError:
        raise ValidationError(f"Daily time must be HH:MM, not {value!r}") from None
    return t.strftime("%H:%M")


def _check_interval(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValidationError("Interval must be a whole number of minutes") from None
    if not 1 <= n <= 7 * 24 * 60:
        raise ValidationError("Interval must be between 1 minute and 7 days")
    return n


def register(spec: JobSpec) -> JobSpec:
    """Add (or replace) a job in the registry."""
    if not spec.name or not spec.name.replace(".", "").replace("_", "").isalnum():
        raise ValidationError(f"Bad job name {spec.name!r}")
    if (spec.interval_minutes is None) == (spec.daily_at is None):
        raise ValidationError(
            f"Job {spec.name}: give exactly one of interval_minutes / daily_at")
    _check_interval(spec.interval_minutes)
    _check_daily(spec.daily_at)
    _REGISTRY[spec.name] = spec
    return spec


def registry() -> dict[str, JobSpec]:
    """All registered jobs (the built-in ones are loaded on first use)."""
    _ensure_builtin()
    return dict(_REGISTRY)


def get_spec(name: str) -> JobSpec:
    _ensure_builtin()
    spec = _REGISTRY.get(name)
    if spec is None:
        raise ValidationError(f"No scheduled job called {name!r}")
    return spec


_BUILTIN_LOADED = False


def _ensure_builtin() -> None:
    global _BUILTIN_LOADED
    if _BUILTIN_LOADED:
        return
    _BUILTIN_LOADED = True
    from education_system.systems.sixth_form.infrastructure.scheduler import (
        jobs,
    )
    jobs.register_builtin_jobs()


# ── DB plumbing ─────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sf_scheduler_jobs (
    job_name          TEXT PRIMARY KEY,
    enabled           INTEGER,
    interval_minutes  INTEGER,
    daily_at          TEXT,
    next_due_at       TEXT,
    last_run_id       INTEGER,
    last_started_at   TEXT,
    last_finished_at  TEXT,
    last_status       TEXT,
    last_error        TEXT,
    last_duration_ms  INTEGER,
    updated_at        TEXT DEFAULT (datetime('now')),
    updated_by        TEXT
);

CREATE TABLE IF NOT EXISTS sf_scheduler_runs (
    run_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    job_name      TEXT NOT NULL,
    trigger       TEXT NOT NULL,
    triggered_by  TEXT,
    status        TEXT NOT NULL,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    duration_ms   INTEGER,
    summary       TEXT,
    error         TEXT,
    owner         TEXT
);
CREATE INDEX IF NOT EXISTS idx_sf_sched_runs_job
    ON sf_scheduler_runs(job_name, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_sf_sched_runs_status
    ON sf_scheduler_runs(status);

CREATE TABLE IF NOT EXISTS sf_scheduler_locks (
    job_name     TEXT PRIMARY KEY,
    owner        TEXT NOT NULL,
    run_id       INTEGER,
    acquired_at  TEXT NOT NULL,
    expires_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sf_scheduler_settings (
    key         TEXT PRIMARY KEY,
    value       TEXT,
    updated_at  TEXT DEFAULT (datetime('now'))
);
"""


def _db_path() -> str:
    return str(paths.SIXTH_FORM_STUDENTS_DB)


def _connect(*, autocommit: bool = False) -> _sql.Connection:
    paths.ensure_sixth_form_directories()
    conn = _sql.connect(_db_path(), timeout=30,
                        isolation_level=None if autocommit else "")
    conn.row_factory = _sql.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextlib.contextmanager
def _conn(*, autocommit: bool = False) -> Iterator[_sql.Connection]:
    conn = _connect(autocommit=autocommit)
    try:
        yield conn
        if not autocommit:
            conn.commit()
    finally:
        conn.close()


_READY_FOR: str | None = None


def init_db() -> None:
    """Create the scheduler tables (idempotent, lazy)."""
    global _READY_FOR
    key = _db_path()
    if _READY_FOR == key:
        return
    with _conn() as conn:
        conn.executescript(_SCHEMA)
    _READY_FOR = key


def _now() -> _dt.datetime:
    return _dt.datetime.now().replace(microsecond=0)


def _fmt(t: _dt.datetime | None) -> str | None:
    return t.strftime(_FMT) if t else None


def _parse(s: str | None) -> _dt.datetime | None:
    if not s:
        return None
    try:
        return _dt.datetime.fromisoformat(str(s).replace("T", " "))
    except ValueError:
        return None


def _clip(s: str | None) -> str | None:
    if s is None:
        return None
    return s if len(s) <= MAX_TEXT else s[:MAX_TEXT - 20] + "\n… (truncated)"


# ── Settings (small key/value store for jobs) ───────────────────────

def get_setting(key: str, default: str | None = None) -> str | None:
    init_db()
    with _conn() as conn:
        r = conn.execute("SELECT value FROM sf_scheduler_settings WHERE key = ?",
                         (key,)).fetchone()
    return r["value"] if r and r["value"] is not None else default


def set_setting(key: str, value: str | None) -> None:
    init_db()
    with _conn() as conn:
        conn.execute(
            """INSERT INTO sf_scheduler_settings (key, value, updated_at)
               VALUES (?, ?, datetime('now'))
               ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                   updated_at = datetime('now')""", (key, value))


def setting_once(key: str, value: str) -> str:
    """The stored value for *key*, storing *value* first if unset."""
    init_db()
    with _conn() as conn:
        conn.execute("INSERT OR IGNORE INTO sf_scheduler_settings (key, value) "
                     "VALUES (?, ?)", (key, value))
        r = conn.execute("SELECT value FROM sf_scheduler_settings WHERE key = ?",
                         (key,)).fetchone()
    return r["value"]


# ── System principal ────────────────────────────────────────────────

def system_principal_object():
    """The principal scheduled jobs run as.

    Not an administrator: it holds the capabilities the jobs need
    (operations, comms, assessment, exams, pastoral, safeguarding
    alerting, reports, …) and never ADMIN, HR, MEDICAL, FINANCE or
    FUNDING.
    """
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    caps = access.ALL_CAPABILITIES - {
        access.ADMIN, access.HR, access.MEDICAL, access.FINANCE,
        access.FUNDING, access.ACCOUNT}
    return access.Principal(username=SYSTEM_USERNAME, user_id=None,
                            role="system", capabilities=frozenset(caps))


@contextlib.contextmanager
def system_principal() -> Iterator[Any]:
    """Run the block as the scheduler's system principal.

    Uses :func:`access.bind_request`, a context variable: it applies to
    the current thread only and is unbound afterwards, so a signed-in
    user's own principal is never replaced or widened.
    """
    from education_system.systems.sixth_form.domain.governance.user_management import (
        access,
    )
    p = system_principal_object()
    token = access.bind_request(p)
    try:
        yield p
    finally:
        access.unbind_request(token)


# ── Job state ───────────────────────────────────────────────────────

@dataclass
class JobState:
    name: str
    title: str
    description: str
    category: str
    enabled: bool
    interval_minutes: int | None
    daily_at: str | None
    default_enabled: bool
    default_interval: int | None
    default_daily_at: str | None
    next_due_at: str | None
    last_run_id: int | None
    last_started_at: str | None
    last_finished_at: str | None
    last_status: str | None
    last_error: str | None
    last_duration_ms: int | None
    running: bool = False

    @property
    def schedule_label(self) -> str:
        if self.daily_at:
            return f"Daily at {self.daily_at}"
        n = self.interval_minutes or 0
        if n % 1440 == 0:
            return f"Every {n // 1440} day(s)"
        if n % 60 == 0:
            return f"Every {n // 60} hour(s)"
        return f"Every {n} min"


@dataclass
class Run:
    run_id: int
    job_name: str
    trigger: str
    triggered_by: str | None
    status: str
    started_at: str
    finished_at: str | None
    duration_ms: int | None
    summary: str | None
    error: str | None
    owner: str | None


def _run(r: _sql.Row) -> Run:
    return Run(**{k: r[k] for k in r.keys()})


def _schedule_of(spec: JobSpec, row: _sql.Row | None) -> tuple[int | None, str | None]:
    """Effective (interval, daily_at): a stored override wins."""
    if row is not None and (row["interval_minutes"] or row["daily_at"]):
        return row["interval_minutes"], row["daily_at"]
    return spec.interval_minutes, spec.daily_at


def next_due_after(interval: int | None, daily_at: str | None,
                   after: _dt.datetime) -> _dt.datetime:
    """The first slot strictly after *after*."""
    if daily_at:
        h, m = (int(x) for x in daily_at.split(":"))
        cand = after.replace(hour=h, minute=m, second=0, microsecond=0)
        if cand <= after:
            cand += _dt.timedelta(days=1)
        return cand
    return after + _dt.timedelta(minutes=int(interval or 60))


def _first_due(interval: int | None, daily_at: str | None,
               now: _dt.datetime) -> _dt.datetime:
    """When a job that has never run is first due: interval jobs straight
    away, daily jobs at their next slot (a fresh install does not fire
    every nightly job at once)."""
    if daily_at:
        return next_due_after(None, daily_at, now)
    return now


def _ensure_rows(conn: _sql.Connection, now: _dt.datetime) -> None:
    """One state row per registered job, with a first due time."""
    have = {r["job_name"]: r for r in conn.execute(
        "SELECT * FROM sf_scheduler_jobs").fetchall()}
    for name, spec in _REGISTRY.items():
        row = have.get(name)
        interval, daily = _schedule_of(spec, row)
        if row is None:
            conn.execute(
                "INSERT OR IGNORE INTO sf_scheduler_jobs (job_name, next_due_at) "
                "VALUES (?, ?)", (name, _fmt(_first_due(interval, daily, now))))
        elif not row["next_due_at"]:
            conn.execute("UPDATE sf_scheduler_jobs SET next_due_at = ? "
                         "WHERE job_name = ?",
                         (_fmt(_first_due(interval, daily, now)), name))


def list_jobs() -> list[JobState]:
    """Every registered job with its effective settings and last run."""
    _ensure_builtin()
    init_db()
    now = _now()
    with _conn() as conn:
        _ensure_rows(conn, now)
        rows = {r["job_name"]: r for r in conn.execute(
            "SELECT * FROM sf_scheduler_jobs").fetchall()}
        locked = {r["job_name"] for r in conn.execute(
            "SELECT job_name FROM sf_scheduler_locks WHERE expires_at > ?",
            (_fmt(now),)).fetchall()}
    out = []
    for name, spec in sorted(_REGISTRY.items(),
                             key=lambda kv: (kv[1].category, kv[1].title)):
        row = rows.get(name)
        interval, daily = _schedule_of(spec, row)
        enabled = spec.enabled if row is None or row["enabled"] is None \
            else bool(row["enabled"])
        out.append(JobState(
            name=name, title=spec.title, description=spec.description,
            category=spec.category, enabled=enabled,
            interval_minutes=None if daily else interval, daily_at=daily,
            default_enabled=spec.enabled,
            default_interval=spec.interval_minutes,
            default_daily_at=spec.daily_at,
            next_due_at=row["next_due_at"] if row else None,
            last_run_id=row["last_run_id"] if row else None,
            last_started_at=row["last_started_at"] if row else None,
            last_finished_at=row["last_finished_at"] if row else None,
            last_status=row["last_status"] if row else None,
            last_error=row["last_error"] if row else None,
            last_duration_ms=row["last_duration_ms"] if row else None,
            running=name in locked))
    return out


def get_job(name: str) -> JobState:
    get_spec(name)
    return next(j for j in list_jobs() if j.name == name)


def set_enabled(name: str, enabled: bool, *, by: str | None = None) -> JobState:
    get_spec(name)
    init_db()
    with _conn() as conn:
        _ensure_rows(conn, _now())
        conn.execute("UPDATE sf_scheduler_jobs SET enabled = ?, "
                     "updated_at = datetime('now'), updated_by = ? "
                     "WHERE job_name = ?", (1 if enabled else 0, by, name))
    logger.info("Scheduled job %s %s by %s", name,
                "enabled" if enabled else "disabled", by or "?")
    return get_job(name)


def set_schedule(name: str, *, interval_minutes: Any = None,
                 daily_at: str | None = None, by: str | None = None) -> JobState:
    """Override a job's schedule (both blank = back to the default)."""
    spec = get_spec(name)
    interval = _check_interval(interval_minutes)
    daily = _check_daily(daily_at)
    if interval is not None and daily is not None:
        raise ValidationError("Give an interval or a daily time, not both")
    eff_interval, eff_daily = (interval, daily) if (interval or daily) else \
        (spec.interval_minutes, spec.daily_at)
    init_db()
    now = _now()
    with _conn() as conn:
        _ensure_rows(conn, now)
        conn.execute(
            "UPDATE sf_scheduler_jobs SET interval_minutes = ?, daily_at = ?, "
            "next_due_at = ?, updated_at = datetime('now'), updated_by = ? "
            "WHERE job_name = ?",
            (interval, daily, _fmt(next_due_after(eff_interval, eff_daily, now)),
             by, name))
    return get_job(name)


# ── History ─────────────────────────────────────────────────────────

def list_runs(*, job_name: str | None = None, status: str | None = None,
              problems_only: bool = False, limit: int = 200) -> list[Run]:
    init_db()
    clauses, args = [], []
    if job_name:
        clauses.append("job_name = ?")
        args.append(job_name)
    if status:
        clauses.append("status = ?")
        args.append(status)
    if problems_only:
        clauses.append("status IN (?, ?, ?)")
        args.extend([FAILED, PARTIAL, ABANDONED])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with _conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM sf_scheduler_runs {where} "
            "ORDER BY run_id DESC LIMIT ?", (*args, int(limit))).fetchall()
    return [_run(r) for r in rows]


def get_run(run_id: int) -> Run | None:
    init_db()
    with _conn() as conn:
        r = conn.execute("SELECT * FROM sf_scheduler_runs WHERE run_id = ?",
                         (int(run_id),)).fetchone()
    return _run(r) if r else None


def prune_history(*, keep_days: int = HISTORY_KEEP_DAYS) -> int:
    """Delete finished runs older than *keep_days* (never a job's last)."""
    init_db()
    cutoff = _fmt(_now() - _dt.timedelta(days=int(keep_days)))
    with _conn() as conn:
        cur = conn.execute(
            "DELETE FROM sf_scheduler_runs WHERE started_at < ? "
            "AND status != ? AND run_id NOT IN "
            "(SELECT last_run_id FROM sf_scheduler_jobs "
            " WHERE last_run_id IS NOT NULL)", (cutoff, RUNNING))
        return cur.rowcount


# ── Locking ─────────────────────────────────────────────────────────

def _acquire(name: str, lease_minutes: int, now: _dt.datetime) -> bool:
    expires = _fmt(now + _dt.timedelta(minutes=max(1, int(lease_minutes))))
    conn = _connect(autocommit=True)
    try:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute("DELETE FROM sf_scheduler_locks WHERE job_name = ? "
                         "AND expires_at <= ?", (name, _fmt(now)))
            cur = conn.execute(
                "INSERT OR IGNORE INTO sf_scheduler_locks "
                "(job_name, owner, acquired_at, expires_at) VALUES (?, ?, ?, ?)",
                (name, OWNER, _fmt(now), expires))
            got = cur.rowcount == 1
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        return got
    finally:
        conn.close()


def _release(name: str) -> None:
    with _conn() as conn:
        conn.execute("DELETE FROM sf_scheduler_locks WHERE job_name = ? "
                     "AND owner = ?", (name, OWNER))


def recover_abandoned() -> int:
    """Mark *Running* runs whose lock has gone (expired or released
    without finishing — the process died) as *Abandoned*."""
    init_db()
    now = _fmt(_now())
    with _conn() as conn:
        conn.execute("DELETE FROM sf_scheduler_locks WHERE expires_at <= ?", (now,))
        cur = conn.execute(
            "UPDATE sf_scheduler_runs SET status = ?, finished_at = ?, "
            "error = COALESCE(error, 'The run stopped without finishing "
            "(the app closed or crashed); its lock has expired.') "
            "WHERE status = ? AND job_name NOT IN "
            "(SELECT job_name FROM sf_scheduler_locks)",
            (ABANDONED, now, RUNNING))
        n = cur.rowcount
        if n:
            conn.execute(
                "UPDATE sf_scheduler_jobs SET last_status = ? WHERE last_run_id "
                "IN (SELECT run_id FROM sf_scheduler_runs WHERE status = ?) "
                "AND last_status = ?", (ABANDONED, ABANDONED, RUNNING))
    if n:
        logger.warning("Marked %d abandoned scheduled run(s)", n)
    return n


# ── Running ─────────────────────────────────────────────────────────

def _coerce(out: Any) -> JobResult:
    if isinstance(out, JobResult):
        return out
    if out is None:
        return JobResult(summary="Done")
    return JobResult(summary=str(out))


def run_job(name: str, *, trigger: str = TRIGGER_MANUAL,
            triggered_by: str | None = None) -> Run | None:
    """Run one job now, under its lock and as the system principal.

    Returns the finished :class:`Run`, or ``None`` when another instance
    holds the job's lock (a manual run records that as *Skipped*).
    """
    spec = get_spec(name)
    init_db()
    start = _now()
    with _conn() as conn:
        _ensure_rows(conn, start)
    if not _acquire(name, spec.lease_minutes, start):
        logger.info("Scheduled job %s is already running elsewhere", name)
        if trigger == TRIGGER_MANUAL:
            with _conn() as conn:
                conn.execute(
                    "INSERT INTO sf_scheduler_runs (job_name, trigger, triggered_by, "
                    "status, started_at, finished_at, duration_ms, summary, owner) "
                    "VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)",
                    (name, trigger, triggered_by, SKIPPED, _fmt(start), _fmt(start),
                     "Not run: the job is already running (another window, "
                     "app instance or cron run holds its lock)", OWNER))
        return None
    try:
        with _conn() as conn:
            cur = conn.execute(
                "INSERT INTO sf_scheduler_runs (job_name, trigger, triggered_by, "
                "status, started_at, owner) VALUES (?, ?, ?, ?, ?, ?)",
                (name, trigger, triggered_by, RUNNING, _fmt(start), OWNER))
            run_id = cur.lastrowid
            conn.execute("UPDATE sf_scheduler_locks SET run_id = ? WHERE job_name = ? "
                         "AND owner = ?", (run_id, name, OWNER))
            conn.execute(
                "UPDATE sf_scheduler_jobs SET last_run_id = ?, last_started_at = ?, "
                "last_status = ? WHERE job_name = ?",
                (run_id, _fmt(start), RUNNING, name))
        t0 = time.monotonic()
        summary: str | None
        error: str | None
        try:
            with system_principal():
                result = _coerce(spec.func())
            status = PARTIAL if result.errors else SUCCESS
            summary = result.summary or "Done"
            error = "\n".join(result.errors) if result.errors else None
        except Exception as e:  # noqa: BLE001 - every failure is the recorded outcome
            logger.exception("Scheduled job %s failed", name)
            status = FAILED
            summary = f"{type(e).__name__}: {e}"
            error = "".join(traceback.format_exception(e))
        duration = int((time.monotonic() - t0) * 1000)
        end = _now()
        with _conn() as conn:
            row = conn.execute("SELECT * FROM sf_scheduler_jobs WHERE job_name = ?",
                               (name,)).fetchone()
            interval, daily = _schedule_of(spec, row)
            nxt = next_due_after(interval, daily, end)
            if status == FAILED and daily:
                nxt = min(nxt, end + FAILED_RETRY)
            conn.execute(
                "UPDATE sf_scheduler_runs SET status = ?, finished_at = ?, "
                "duration_ms = ?, summary = ?, error = ? WHERE run_id = ?",
                (status, _fmt(end), duration, _clip(summary), _clip(error), run_id))
            conn.execute(
                "UPDATE sf_scheduler_jobs SET last_finished_at = ?, last_status = ?, "
                "last_error = ?, last_duration_ms = ?, next_due_at = ? "
                "WHERE job_name = ?",
                (_fmt(end), status, _clip(error), duration, _fmt(nxt), name))
        logger.info("Scheduled job %s: %s in %d ms — %s", name, status, duration,
                    summary)
        return get_run(run_id)
    finally:
        _release(name)


@dataclass
class DueRun:
    name: str
    trigger: str
    run: Run | None


def due_jobs(now: _dt.datetime | None = None) -> list[tuple[str, str]]:
    """``(job name, trigger)`` for every enabled job that is due now."""
    now = now or _now()
    out = []
    for j in list_jobs():
        if not j.enabled or j.running:
            continue
        due = _parse(j.next_due_at)
        if due is None or due > now:
            continue
        late = now - due
        trigger = TRIGGER_CATCH_UP if (j.daily_at and late > CATCH_UP_GRACE) \
            or (j.interval_minutes and late > _dt.timedelta(
                minutes=2 * j.interval_minutes)) else TRIGGER_SCHEDULE
        out.append((j.name, trigger))
    out.sort(key=lambda t: t[0])
    return out


def run_due_jobs(*, triggered_by: str | None = None,
                 headless: bool = False,
                 should_stop: Callable[[], bool] | None = None) -> list[DueRun]:
    """Run every due job once, one after another."""
    recover_abandoned()
    out = []
    for name, trigger in due_jobs():
        if should_stop is not None and should_stop():
            break
        if headless and trigger == TRIGGER_SCHEDULE:
            trigger = TRIGGER_HEADLESS
        out.append(DueRun(name, trigger,
                          run_job(name, trigger=trigger, triggered_by=triggered_by)))
    return out
