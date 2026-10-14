"""Real system metrics for the Batch Operations reports.

The performance and comprehensive reports used to be built entirely from
``random.uniform()`` and ``random.choice()`` — health scores, CPU
figures, error counts and security metrics were all invented fresh on
every run. They looked authoritative and meant nothing.

This module collects the same shapes from things that actually exist:

===========================  ==================================================
Metric                       Source
===========================  ==================================================
CPU / memory / disk          ``psutil`` against this process's host
Database size and timing     the SQLite file, plus a real timed query
Authentication activity      ``login_attempts`` (has ``success``, ``attempt_time``)
User activity                ``activity_log`` / ``audit_log``
Errors and warnings          the application log file, parsed by level
Batch operation success      ``import_history.json`` — actual past runs
===========================  ==================================================

**The rule: never invent a number.** Every collector returns
``available: False`` and a ``note`` explaining why when it cannot
measure something — a missing table, no ``psutil``, an empty log. The
report renders those as "not measured" rather than filling the gap. A
blank in a report is honest; a plausible fabricated number is not, and
that is exactly the failure this module exists to correct.

Metrics that genuinely cannot be derived from this system at all
(network latency, packet loss, cache hit ratios for a database with no
cache layer) are simply not collected. They are absent from the reports
rather than estimated.
"""

import datetime
import json
import logging
import os
import re
import sqlite3
import time
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the environment
    psutil = None
    PSUTIL_AVAILABLE = False


def _unavailable(note, **extra):
    out = {'available': False, 'note': note}
    out.update(extra)
    return out


def _connect_ro(db_path):
    """Read-only connection. Reports must never mutate the database."""
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _table_exists(conn, name):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (name,)).fetchone()
    return row is not None


# ── Host resources ──────────────────────────────────────────────────

def resource_metrics():
    """CPU, memory and disk for the host this process runs on."""
    if not PSUTIL_AVAILABLE:
        return _unavailable("psutil is not installed")
    try:
        # interval=None returns the value since the last call, which is
        # meaningless on a first call; a short blocking sample is the
        # only way to get a real instantaneous figure.
        cpu = psutil.cpu_percent(interval=0.25)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(Path.home()))
        process = psutil.Process(os.getpid())
        return {
            'available': True,
            'source': 'psutil',
            'cpu_percent': round(cpu, 1),
            'cpu_count': psutil.cpu_count() or 0,
            'load_average': [round(v, 2) for v in os.getloadavg()]
                            if hasattr(os, 'getloadavg') else None,
            'memory_percent': round(memory.percent, 1),
            'memory_used_mb': round(memory.used / (1024 ** 2)),
            'memory_total_mb': round(memory.total / (1024 ** 2)),
            'disk_percent': round(disk.percent, 1),
            'disk_free_gb': round(disk.free / (1024 ** 3), 1),
            'process_memory_mb': round(
                process.memory_info().rss / (1024 ** 2), 1),
            'process_uptime_hours': round(
                (time.time() - process.create_time()) / 3600, 1),
        }
    except Exception as exc:
        logger.warning("Resource metrics unavailable: %s", exc)
        return _unavailable(f"psutil failed: {exc}")


# ── Database ────────────────────────────────────────────────────────

def database_metrics(db_path):
    """Size, shape and a genuinely timed query against the database."""
    path = Path(db_path)
    if not path.exists():
        return _unavailable(f"database not found at {path}")
    try:
        size_mb = path.stat().st_size / (1024 ** 2)
        conn = _connect_ro(path)
        try:
            page_count = conn.execute("PRAGMA page_count").fetchone()[0]
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
            tables = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()[0]
            indexes = conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='index'"
            ).fetchone()[0]

            # Time a real query rather than quoting a made-up figure.
            # Three samples, take the median, so one scheduling hiccup
            # does not become the headline number.
            samples = []
            for _ in range(3):
                start = time.perf_counter()
                conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "ORDER BY name LIMIT 200").fetchall()
                samples.append((time.perf_counter() - start) * 1000)
            samples.sort()
            return {
                'available': True,
                'source': str(path),
                'size_mb': round(size_mb, 1),
                'page_count': page_count,
                'page_size': page_size,
                'journal_mode': journal,
                'tables': tables,
                'indexes': indexes,
                'catalogue_query_ms': round(samples[1], 2),
            }
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Database metrics unavailable: %s", exc)
        return _unavailable(f"could not read the database: {exc}")


def record_counts(db_path, tables=None):
    """Row counts for the tables that actually matter to a report."""
    wanted = tables or ('students', 'user_accounts', 'module_enrolments',
                        'modules', 'activity_log', 'audit_log')
    path = Path(db_path)
    if not path.exists():
        return _unavailable(f"database not found at {path}")
    counts, missing = {}, []
    try:
        conn = _connect_ro(path)
        try:
            for table in wanted:
                if not _table_exists(conn, table):
                    missing.append(table)
                    continue
                # Table names come from the fixed tuple above, never
                # from user input, so the interpolation is safe here.
                counts[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()
    except Exception as exc:
        return _unavailable(f"could not count records: {exc}")
    return {'available': True, 'counts': counts, 'missing_tables': missing}


# ── Authentication ──────────────────────────────────────────────────

def auth_metrics(db_path, hours=24):
    """Login success and failure from ``login_attempts``.

    Replaces what used to be ``random.randint`` for "successful logins",
    "failed attempts" and "account lockouts".
    """
    path = Path(db_path)
    if not path.exists():
        return _unavailable(f"database not found at {path}")
    try:
        conn = _connect_ro(path)
        try:
            if not _table_exists(conn, 'login_attempts'):
                return _unavailable("no login_attempts table")
            cutoff = (datetime.datetime.now()
                      - datetime.timedelta(hours=hours)
                      ).strftime('%Y-%m-%d %H:%M:%S')
            row = conn.execute(
                """SELECT
                       COUNT(*)                                   AS total,
                       SUM(CASE WHEN success IN (1,'1','true','True')
                                THEN 1 ELSE 0 END)                AS ok,
                       COUNT(DISTINCT username)                   AS users,
                       COUNT(DISTINCT ip_address)                 AS ips
                     FROM login_attempts
                    WHERE attempt_time >= ?""", (cutoff,)).fetchone()
            total, ok, users, ips = (row[0] or 0, row[1] or 0,
                                     row[2] or 0, row[3] or 0)
            all_time = conn.execute(
                "SELECT COUNT(*) FROM login_attempts").fetchone()[0]

            # Repeated failures against one account are the signal worth
            # surfacing; a raw failure count is not.
            repeat = conn.execute(
                """SELECT username, COUNT(*) AS failures
                     FROM login_attempts
                    WHERE attempt_time >= ?
                      AND success NOT IN (1,'1','true','True')
                    GROUP BY username HAVING failures >= 3
                    ORDER BY failures DESC LIMIT 10""", (cutoff,)).fetchall()
            return {
                'available': True,
                'source': 'login_attempts',
                'window_hours': hours,
                'total_attempts': total,
                'successful': ok,
                'failed': total - ok,
                'success_rate': round(ok / total * 100, 1) if total else None,
                'distinct_users': users,
                'distinct_ips': ips,
                'all_time_attempts': all_time,
                'repeat_failures': [
                    {'username': r[0], 'failures': r[1]} for r in repeat],
            }
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Auth metrics unavailable: %s", exc)
        return _unavailable(f"could not read login_attempts: {exc}")


# ── Activity ────────────────────────────────────────────────────────

def activity_metrics(db_path, days=30):
    """Recent user activity from ``activity_log``, falling back to audit."""
    path = Path(db_path)
    if not path.exists():
        return _unavailable(f"database not found at {path}")
    try:
        conn = _connect_ro(path)
        try:
            table = ('activity_log' if _table_exists(conn, 'activity_log')
                     else 'audit_log' if _table_exists(conn, 'audit_log')
                     else None)
            if table is None:
                return _unavailable("no activity_log or audit_log table")
            column = 'timestamp' if table == 'activity_log' else 'timestamp'
            cutoff = (datetime.datetime.now()
                      - datetime.timedelta(days=days)
                      ).strftime('%Y-%m-%d %H:%M:%S')
            total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            try:
                recent = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column} >= ?",
                    (cutoff,)).fetchone()[0]
                by_action = conn.execute(
                    f"""SELECT action, COUNT(*) AS n FROM {table}
                         WHERE {column} >= ? GROUP BY action
                         ORDER BY n DESC LIMIT 8""", (cutoff,)).fetchall()
            except sqlite3.OperationalError:
                # Older schemas name the column differently; the total is
                # still worth reporting.
                recent, by_action = None, []
            return {
                'available': True,
                'source': table,
                'window_days': days,
                'total_events': total,
                'recent_events': recent,
                'by_action': [{'action': r[0] or '(none)', 'count': r[1]}
                              for r in by_action],
            }
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Activity metrics unavailable: %s", exc)
        return _unavailable(f"could not read the activity log: {exc}")


# ── Application log ─────────────────────────────────────────────────

_LOG_LINE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})[,.]?\d*\s*-\s*'
    r'(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL)\s*-\s*'
    r'(?P<logger>[\w.]+)\s*-\s*(?P<message>.*)$')

#: Buckets for grouping errors. Ordered — first match wins.
_ERROR_CATEGORIES = (
    ('Database', ('sqlite', 'database', 'no such table', 'no such column',
                  'integrity', 'locked')),
    ('Network', ('connection', 'timeout', 'socket', 'http', 'urlopen',
                 'unreachable')),
    ('Authentication', ('auth', 'login', 'password', 'permission',
                        'forbidden', 'token', 'credential')),
    ('Validation', ('validation', 'invalid', 'missing required',
                    'must be', 'malformed')),
    ('Import/Export', ('import', 'export', 'csv', 'encoding', 'decode')),
)


def _categorise(message):
    lowered = message.lower()
    for name, needles in _ERROR_CATEGORIES:
        if any(needle in lowered for needle in needles):
            return name
    return 'Other'


def log_metrics(log_path, max_lines=40000):
    """Counts by level and error categories, parsed from the log file.

    Replaces the invented "total errors analysed" and per-category
    percentages. Only the tail is read: these logs grow without bound
    and a report must not stall on a 200MB file.
    """
    path = Path(log_path) if log_path else None
    if not path or not path.exists():
        return _unavailable(f"log file not found at {path}")
    try:
        with open(path, 'r', errors='replace') as handle:
            lines = handle.readlines()
        truncated = len(lines) > max_lines
        lines = lines[-max_lines:]

        levels = {}
        categories = {}
        recent_errors = []
        first_ts = last_ts = None
        for line in lines:
            match = _LOG_LINE.match(line.strip())
            if not match:
                continue
            level = match.group('level')
            levels[level] = levels.get(level, 0) + 1
            timestamp = match.group('ts')
            first_ts = first_ts or timestamp
            last_ts = timestamp
            if level in ('ERROR', 'CRITICAL'):
                message = match.group('message')
                category = _categorise(message)
                categories[category] = categories.get(category, 0) + 1
                recent_errors.append({
                    'timestamp': timestamp,
                    'logger': match.group('logger'),
                    'category': category,
                    'message': message[:200],
                })

        parsed = sum(levels.values())
        errors = levels.get('ERROR', 0) + levels.get('CRITICAL', 0)
        return {
            'available': True,
            'source': str(path),
            'lines_scanned': len(lines),
            'truncated': truncated,
            'parsed_records': parsed,
            'levels': levels,
            'errors': errors,
            'warnings': levels.get('WARNING', 0),
            'error_rate_percent': (round(errors / parsed * 100, 2)
                                   if parsed else None),
            'categories': [
                {'category': name, 'count': count,
                 'percentage': round(count / errors * 100, 1) if errors else 0}
                for name, count in sorted(categories.items(),
                                          key=lambda kv: -kv[1])],
            'recent_errors': recent_errors[-15:],
            'first_timestamp': first_ts,
            'last_timestamp': last_ts,
        }
    except Exception as exc:
        logger.warning("Log metrics unavailable: %s", exc)
        return _unavailable(f"could not read the log: {exc}")


# ── Batch operation history ─────────────────────────────────────────

def operation_metrics(history_path=None, history=None):
    """Success rates from real past batch runs.

    ``history`` (the live in-memory list) wins over ``history_path``, so
    a report generated straight after an import includes that import.
    """
    entries = history
    if entries is None:
        path = Path(history_path) if history_path else None
        if not path or not path.exists():
            return _unavailable("no import history recorded yet")
        try:
            entries = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            return _unavailable(f"could not read the import history: {exc}")
    if not entries:
        return _unavailable("no import history recorded yet")

    total_records = successful = failed = 0
    by_operation = {}
    for entry in entries:
        try:
            records = int(entry.get('total_records', 0) or 0)
            ok = int(entry.get('successful_imports', 0) or 0)
            bad = int(entry.get('failed_imports', 0) or 0)
        except (TypeError, ValueError):
            continue
        total_records += records
        successful += ok
        failed += bad
        name = entry.get('operation_type') or 'unknown'
        bucket = by_operation.setdefault(
            name, {'runs': 0, 'records': 0, 'successful': 0, 'failed': 0})
        bucket['runs'] += 1
        bucket['records'] += records
        bucket['successful'] += ok
        bucket['failed'] += bad

    for bucket in by_operation.values():
        processed = bucket['successful'] + bucket['failed']
        bucket['success_rate'] = (round(bucket['successful'] / processed * 100, 1)
                                  if processed else None)

    processed = successful + failed
    return {
        'available': True,
        'source': 'import history',
        'runs': len(entries),
        'total_records': total_records,
        'successful': successful,
        'failed': failed,
        'success_rate': (round(successful / processed * 100, 1)
                         if processed else None),
        'by_operation': [
            {'operation': name, **stats}
            for name, stats in sorted(by_operation.items(),
                                      key=lambda kv: -kv[1]['records'])],
        'last_run': entries[-1].get('timestamp') if entries else None,
    }


# ── Derived health ──────────────────────────────────────────────────

def health_assessment(resources, database, auth, logs, operations):
    """A health score computed from whatever was actually measured.

    Only measured factors contribute; the score is the mean of the ones
    available, and ``factors_measured`` says how many that was. A score
    built from one factor is not the same claim as one built from five,
    so the report shows both.
    """
    factors = {}

    if resources.get('available'):
        # Headroom, not usage: 20% CPU is a healthy 80.
        factors['CPU headroom'] = max(0.0, 100.0 - resources['cpu_percent'])
        factors['Memory headroom'] = max(0.0, 100.0 - resources['memory_percent'])
        factors['Disk headroom'] = max(0.0, 100.0 - resources['disk_percent'])

    if database.get('available'):
        query_ms = database.get('catalogue_query_ms') or 0
        # 0ms -> 100, 50ms+ -> 0. The catalogue query is small; anything
        # slower than that indicates real contention.
        factors['Query speed'] = max(0.0, 100.0 - (query_ms * 2))

    if logs.get('available') and logs.get('parsed_records'):
        rate = logs.get('error_rate_percent') or 0
        factors['Log cleanliness'] = max(0.0, 100.0 - (rate * 10))

    if auth.get('available') and auth.get('success_rate') is not None:
        factors['Login success'] = auth['success_rate']

    if operations.get('available') and operations.get('success_rate') is not None:
        factors['Batch success'] = operations['success_rate']

    if not factors:
        return _unavailable(
            "nothing could be measured, so no health score was calculated",
            factors={}, factors_measured=0)

    score = sum(factors.values()) / len(factors)
    if score >= 90:
        rating = 'Excellent'
    elif score >= 75:
        rating = 'Good'
    elif score >= 60:
        rating = 'Fair'
    else:
        rating = 'Needs attention'
    return {
        'available': True,
        'overall_score': round(score, 1),
        'rating': rating,
        'factors': {name: round(value, 1) for name, value in factors.items()},
        'factors_measured': len(factors),
    }


def build_findings(resources, database, auth, logs, operations):
    """Concrete, sourced observations — the replacement for canned advice.

    Each is ``(severity, headline, detail)`` and only appears when the
    measurement that triggers it was actually taken. An empty list means
    nothing was wrong, not that nothing was checked.
    """
    findings = []

    if resources.get('available'):
        if resources['disk_percent'] >= 90:
            findings.append(('bad', "Disk almost full",
                             f"{resources['disk_percent']}% used, "
                             f"{resources['disk_free_gb']} GB free."))
        elif resources['disk_percent'] >= 75:
            findings.append(('warn', "Disk filling up",
                             f"{resources['disk_percent']}% used, "
                             f"{resources['disk_free_gb']} GB free."))
        if resources['memory_percent'] >= 90:
            findings.append(('bad', "Memory pressure",
                             f"{resources['memory_percent']}% of "
                             f"{resources['memory_total_mb']} MB in use."))

    if logs.get('available'):
        rate = logs.get('error_rate_percent')
        if rate is not None and rate >= 5:
            findings.append(('bad', f"Elevated error rate ({rate}%)",
                             f"{logs['errors']} error records in the last "
                             f"{logs['lines_scanned']:,} log lines."))
        elif logs.get('errors'):
            top = logs['categories'][0] if logs['categories'] else None
            findings.append((
                'warn', f"{logs['errors']} error(s) in the log",
                f"Most common category: {top['category']} "
                f"({top['count']})." if top else ""))

    if auth.get('available'):
        for entry in auth.get('repeat_failures', [])[:3]:
            findings.append((
                'warn',
                f"Repeated login failures for '{entry['username']}'",
                f"{entry['failures']} failed attempts in the last "
                f"{auth['window_hours']} hours."))

    if operations.get('available') and operations.get('success_rate') is not None:
        if operations['success_rate'] < 90:
            findings.append((
                'bad', f"Batch success rate is {operations['success_rate']}%",
                f"{operations['failed']:,} of "
                f"{operations['successful'] + operations['failed']:,} "
                f"records failed across {operations['runs']} run(s)."))

    if database.get('available') and database.get('journal_mode', '').lower() != 'wal':
        findings.append((
            'warn',
            f"Database journal mode is {database['journal_mode']}",
            "WAL allows readers and a writer to work concurrently."))

    return findings


def collect_all(db_path, log_path=None, history_path=None, history=None):
    """Everything at once, plus the derived health and findings."""
    resources = resource_metrics()
    database = database_metrics(db_path)
    records = record_counts(db_path)
    auth = auth_metrics(db_path)
    activity = activity_metrics(db_path)
    logs = log_metrics(log_path)
    operations = operation_metrics(history_path=history_path, history=history)
    return {
        'generated_at': datetime.datetime.now().isoformat(timespec='seconds'),
        'resources': resources,
        'database': database,
        'records': records,
        'auth': auth,
        'activity': activity,
        'logs': logs,
        'operations': operations,
        'health': health_assessment(resources, database, auth, logs, operations),
        'findings': [
            {'severity': s, 'headline': h, 'detail': d}
            for s, h, d in build_findings(resources, database, auth, logs,
                                          operations)],
    }


# ── Source resolution ───────────────────────────────────────────────

def resolve_log_path():
    """Find the application log actually being written.

    ``constants`` asks ``get_log_file`` for ``modules_system.log``, which
    does not exist in this deployment — the live file is ``app.log``. So
    try the candidates and take the largest one that is really there,
    rather than reporting "no log" because of a stale filename.
    """
    candidates = []
    try:
        from education_system.systems.university.infrastructure.logging.log_config import (
            get_log_file,
        )
        for name in ('app.log', 'modules_system.log', 'university.log'):
            try:
                candidates.append(Path(get_log_file(name)))
            except Exception:
                continue
    except Exception:
        logger.debug("log_config unavailable", exc_info=True)
    try:
        from education_system.paths import UNIVERSITY_LOGS_DIR
        candidates.extend(Path(UNIVERSITY_LOGS_DIR).glob('*.log'))
    except Exception:
        logger.debug("UNIVERSITY_LOGS_DIR unavailable", exc_info=True)

    existing = [p for p in candidates if p.exists() and p.stat().st_size > 0]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_size)


def gui_sources(gui):
    """The measurement sources reachable from a Batch Operations GUI."""
    from education_system.systems.university.shell.gui.batch_operations.constants import (
        DEFAULT_DB_PATH, IMPORT_HISTORY_PATH,
    )
    backend = getattr(gui, 'backend', None)
    return {
        'db_path': DEFAULT_DB_PATH,
        'log_path': resolve_log_path(),
        'history_path': IMPORT_HISTORY_PATH,
        'history': getattr(backend, 'import_history', None),
    }
