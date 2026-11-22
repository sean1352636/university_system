"""Reports on batch work, from what actually happened (``batch_jobs`` and
their rows) — the old Batch Operations report manager's four reports,
rebuilt on real history:

* :func:`success_rates` — rows processed, succeeded, skipped and failed per
  kind of run and per person.
* :func:`error_analysis` — failed and skipped rows grouped by the reason
  given (numbers and quoted values folded so the same problem groups).
* :func:`performance` — runs per week, rows per run and rows per minute,
  for trends.
* :func:`comprehensive` — all three plus the measured system figures
  (``infrastructure/monitoring/system_metrics``: resources, database,
  logins, log errors, health and findings — never invented).

Plus :func:`enrolment_statistics` (students by course, status, year, mode,
fee status and gender; module enrolment counts) and :func:`history` /
:func:`export_history` for the job list. Reports are for staff who may
run batch work; statistics are counts only, never individuals.

``write_report`` saves any report as JSON, or CSV for its main table.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime

KIND_SQL = ("CASE WHEN kind = 'actions' AND mode = 'enrolments' THEN 'enrolments' "
            "ELSE kind END")


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _require(viewer):
    if not (viewer.can_update or viewer.can_mark or viewer.can_manage_users):
        raise ValueError("Batch reports are for staff who run batch work")


def _since(days):
    return ("", []) if not days else (" AND j.started_at >= datetime('now', ?)",
                                      [f"-{int(days)} days"])


def _ensure(conn):
    from education_system.systems.university.infrastructure.database.schemas import (
        batch_jobs_schema,
    )
    batch_jobs_schema.apply_to_connection(conn)


def _rate(ok, bad):
    return round(ok / (ok + bad) * 100, 1) if ok + bad else None


def success_rates(conn, viewer, days=90) -> dict:
    _require(viewer)
    _ensure(conn)
    where, args = _since(days)
    kinds = _dicts(conn.execute(
        f"SELECT {KIND_SQL} AS kind, COUNT(*) AS runs, SUM(total) AS rows, "
        "SUM(succeeded) AS succeeded, SUM(skipped) AS skipped, SUM(failed) AS failed, "
        "SUM(status = 'undone') AS undone FROM batch_jobs j WHERE 1 = 1" + where +
        " GROUP BY 1 ORDER BY rows DESC", args))  # nosec B608 - fixed clauses
    people = _dicts(conn.execute(
        "SELECT actor, COUNT(*) AS runs, SUM(total) AS rows, SUM(succeeded) AS succeeded, "
        "SUM(failed) AS failed FROM batch_jobs j WHERE 1 = 1" + where +
        " GROUP BY actor ORDER BY rows DESC", args))  # nosec B608
    for r in kinds + people:
        r["success_rate"] = _rate(r["succeeded"] or 0, r["failed"] or 0)
    total_ok = sum(r["succeeded"] or 0 for r in kinds)
    total_bad = sum(r["failed"] or 0 for r in kinds)
    return {"title": "Batch success rates", "days": days, "by_kind": kinds, "by_person": people,
            "runs": sum(r["runs"] for r in kinds), "succeeded": total_ok, "failed": total_bad,
            "success_rate": _rate(total_ok, total_bad)}


_NOISE = (re.compile(r"'[^']*'"), re.compile(r'"[^"]*"'), re.compile(r"\b\d[\d./:-]*\b"))


def _reason_key(message) -> str:
    text = str(message or "no reason recorded")
    for rx in _NOISE:
        text = rx.sub("…", text)
    return " ".join(text.split())[:160]


def error_analysis(conn, viewer, days=90, limit=30) -> dict:
    _require(viewer)
    _ensure(conn)
    where, args = _since(days)
    rows = conn.execute(
        f"SELECT {KIND_SQL}, r.outcome, r.message, j.id FROM batch_job_rows r JOIN batch_jobs j "
        "ON j.id = r.job_id WHERE r.outcome IN ('failed', 'skipped')" + where,
        args).fetchall()  # nosec B608
    groups: dict[tuple, dict] = {}
    for kind, outcome, message, job_id in rows:
        key = (kind, outcome, _reason_key(message))
        g = groups.setdefault(key, {"kind": kind, "outcome": outcome, "reason": key[2],
                                    "count": 0, "jobs": set(), "example": message})
        g["count"] += 1
        g["jobs"].add(job_id)
    ordered = sorted(groups.values(), key=lambda g: -g["count"])[:limit]
    for g in ordered:
        g["jobs"] = len(g["jobs"])
    return {"title": "Batch error analysis", "days": days, "problems": len(rows),
            "groups": ordered}


def performance(conn, viewer, days=180) -> dict:
    _require(viewer)
    _ensure(conn)
    where, args = _since(days)
    jobs = _dicts(conn.execute(
        f"SELECT j.id, {KIND_SQL} AS kind, j.total, j.succeeded, j.failed, j.started_at, "
        "j.finished_at, (julianday(j.finished_at) - julianday(j.started_at)) * 86400.0 AS "
        "seconds FROM batch_jobs j WHERE j.finished_at IS NOT NULL" + where +
        " ORDER BY j.started_at", args))  # nosec B608
    weeks: dict[str, dict] = {}
    for j in jobs:
        week = datetime.fromisoformat(str(j["started_at"])[:19]).strftime("%G-W%V")
        w = weeks.setdefault(week, {"week": week, "runs": 0, "rows": 0, "seconds": 0.0,
                                    "succeeded": 0, "failed": 0})
        w["runs"] += 1
        w["rows"] += j["total"] or 0
        w["seconds"] += max(0.0, j["seconds"] or 0.0)
        w["succeeded"] += j["succeeded"] or 0
        w["failed"] += j["failed"] or 0
    trend = []
    for w in sorted(weeks.values(), key=lambda w: w["week"]):
        trend.append({**w, "seconds": round(w["seconds"], 1),
                      "rows_per_run": round(w["rows"] / w["runs"], 1),
                      "rows_per_minute": (round(w["rows"] / (w["seconds"] / 60), 1)
                                          if w["seconds"] > 0 else None),
                      "success_rate": _rate(w["succeeded"], w["failed"])})
    slowest = sorted(jobs, key=lambda j: -(j["seconds"] or 0))[:10]
    return {"title": "Batch performance", "days": days, "weeks": trend,
            "slowest": [{"job": j["id"], "kind": j["kind"], "rows": j["total"],
                         "seconds": round(j["seconds"] or 0, 1)} for j in slowest]}


def comprehensive(conn, viewer, days=90, db_path=None) -> dict:
    from education_system.systems.university.infrastructure.monitoring import system_metrics
    _require(viewer)
    sources = system_metrics.default_sources()
    measured = system_metrics.collect_all(db_path or sources["db_path"], sources["log_path"],
                                          days=days)
    return {"title": "Comprehensive batch and system report",
            "generated_at": datetime.now().isoformat(timespec="seconds"), "days": days,
            "success": success_rates(conn, viewer, days),
            "errors": error_analysis(conn, viewer, days),
            "performance": performance(conn, viewer, days), "system": measured}


def system_status(viewer, db_path=None) -> dict:
    """The measured system figures only (resources, database, logins, log,
    batch success, health and findings)."""
    from education_system.systems.university.infrastructure.monitoring import system_metrics
    _require(viewer)
    sources = system_metrics.default_sources()
    return system_metrics.collect_all(db_path or sources["db_path"], sources["log_path"])


# ── enrolment statistics ────────────────────────────────────────────────


def _count_by(conn, expr, table="students s", where="") -> list[dict]:
    return [{"value": v if v not in (None, "") else "(not recorded)", "students": n}
            for v, n in conn.execute(f"SELECT {expr}, COUNT(*) FROM {table} {where} "  # nosec B608
                                     "GROUP BY 1 ORDER BY 2 DESC").fetchall()]


def enrolment_statistics(conn, viewer) -> dict:
    """Counts only. Erased records are left out."""
    if not (viewer.can_view_all or viewer.can_export):
        raise ValueError("You do not have permission to see university-wide statistics")
    live = "WHERE COALESCE(s.status, '') NOT LIKE 'Erased%' AND s.student_id NOT LIKE 'ERASED-%'"
    from education_system.systems.university.application.students import search as student_search
    out = {"title": "Enrolment statistics",
           "generated_at": datetime.now().isoformat(timespec="seconds"),
           "students": conn.execute(f"SELECT COUNT(*) FROM students s {live}").fetchone()[0]}
    for key, expr in (("by_course", student_search.FIELDS["course"].expr),
                      ("by_status", student_search.FIELDS["status"].expr),
                      ("by_year_of_study", "s.year_of_study"),
                      ("by_mode_of_study", "s.mode_of_study"),
                      ("by_fee_status", "s.fee_status"), ("by_gender", "s.gender")):
        out[key] = _count_by(conn, expr, where=live)
    out["module_enrolments"] = [
        {"module_code": code, "module_name": name, "enrolled": n}
        for code, name, n in conn.execute(
            "SELECT sm.module_code, COALESCE(m.module_name, sm.module_name), COUNT(*) FROM "
            "student_modules sm LEFT JOIN modules m ON m.module_code = sm.module_code WHERE "
            "LOWER(COALESCE(sm.status, 'enrolled')) IN ('enrolled', 'active', 'registered') "
            "GROUP BY sm.module_code ORDER BY 3 DESC").fetchall()]
    return out


# ── job history ─────────────────────────────────────────────────────────


def history(conn, kind=None, days=None, actor=None) -> list[dict]:
    _ensure(conn)
    sql = f"SELECT j.*, {KIND_SQL} AS shown_kind FROM batch_jobs j WHERE 1 = 1"
    args: list = []
    if kind:
        sql += f" AND {KIND_SQL} = ?"
        args.append(kind)
    if actor:
        sql += " AND j.actor = ?"
        args.append(actor)
    where, extra = _since(days)
    return _dicts(conn.execute(sql + where + " ORDER BY j.id DESC", args + extra))


def export_history(conn, viewer, path, kind=None, days=None) -> int:
    _require(viewer)
    rows = history(conn, kind, days)
    columns = ["id", "shown_kind", "source", "mode", "actor", "reason", "status", "total",
               "succeeded", "skipped", "failed", "started_at", "finished_at", "undone_by",
               "undone_at", "undo_reason"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


# ── saving and showing reports ──────────────────────────────────────────

_MAIN_TABLE = {"Batch success rates": "by_kind", "Batch error analysis": "groups",
               "Batch performance": "weeks", "Enrolment statistics": "by_course"}


def write_report(report, path) -> str:
    """JSON (everything) or CSV (the report's main table)."""
    if str(path).lower().endswith(".csv"):
        rows = report.get(_MAIN_TABLE.get(report.get("title"), ""), [])
        if not rows:
            raise ValueError("This report has no table to save as CSV; save it as JSON")
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    else:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, default=str)
    return str(path)


def _table(rows, columns) -> list[str]:
    if not rows:
        return ["  (none)"]
    widths = [max(len(c), *(len(str(r.get(k, "") if r.get(k) is not None else "–"))
                            for r in rows)) for k, c in columns]
    lines = ["  " + "  ".join(c.ljust(w) for (_k, c), w in zip(columns, widths))]
    for r in rows:
        lines.append("  " + "  ".join(
            str(r.get(k) if r.get(k) is not None else "–").ljust(w)[:60]
            for (k, _c), w in zip(columns, widths)))
    return lines


def as_text(report) -> str:
    """A plain-text rendering for screens, the CLI and e-mail."""
    title = report.get("title", "Report")
    lines = [title, "=" * len(title)]
    if "days" in report and report["days"]:
        lines.append(f"Last {report['days']} days")
    if title == "Batch success rates":
        lines += [f"{report['runs']} run(s); {report['succeeded']} rows succeeded, "
                  f"{report['failed']} failed; success rate "
                  f"{report['success_rate'] if report['success_rate'] is not None else '–'}%",
                  "", "By kind:"]
        lines += _table(report["by_kind"], [("kind", "Kind"), ("runs", "Runs"), ("rows", "Rows"),
                                            ("succeeded", "OK"), ("skipped", "Skipped"),
                                            ("failed", "Failed"), ("undone", "Undone"),
                                            ("success_rate", "Rate %")])
        lines += ["", "By person:"]
        lines += _table(report["by_person"], [("actor", "Who"), ("runs", "Runs"),
                                              ("rows", "Rows"), ("failed", "Failed"),
                                              ("success_rate", "Rate %")])
    elif title == "Batch error analysis":
        lines.append(f"{report['problems']} failed or skipped row(s)")
        lines += _table(report["groups"], [("count", "Rows"), ("jobs", "Jobs"), ("kind", "Kind"),
                                           ("outcome", "Outcome"), ("reason", "Reason")])
    elif title == "Batch performance":
        lines += _table(report["weeks"], [("week", "Week"), ("runs", "Runs"), ("rows", "Rows"),
                                          ("rows_per_run", "Rows/run"),
                                          ("rows_per_minute", "Rows/min"),
                                          ("success_rate", "Rate %")])
        lines += ["", "Slowest runs:"]
        lines += _table(report["slowest"], [("job", "Job"), ("kind", "Kind"), ("rows", "Rows"),
                                            ("seconds", "Seconds")])
    elif title == "Enrolment statistics":
        lines.append(f"{report['students']} student record(s)")
        for key, label in (("by_course", "Course"), ("by_status", "Status"),
                           ("by_year_of_study", "Year of study"),
                           ("by_mode_of_study", "Mode of study"),
                           ("by_fee_status", "Fee status"), ("by_gender", "Gender")):
            lines += ["", f"By {label.lower()}:"]
            lines += _table(report[key], [("value", label), ("students", "Students")])
        lines += ["", "Module enrolments:"]
        lines += _table(report["module_enrolments"], [("module_code", "Module"),
                                                      ("module_name", "Name"),
                                                      ("enrolled", "Enrolled")])
    elif "system" in report or "health" in report:
        system = report.get("system", report)
        if "success" in report:
            for part in ("success", "errors", "performance"):
                lines += ["", as_text(report[part])]
        lines += ["", "System", "------"]
        lines += _system_lines(system)
    return "\n".join(lines)


def _system_lines(m) -> list[str]:
    out = []
    health = m.get("health", {})
    out.append(f"Health: {health.get('overall_score', '–')} ({health.get('rating', 'not measured')}"
               f", {health.get('factors_measured', 0)} factor(s) measured)")
    for name, part in (("Resources", "resources"), ("Database", "database"),
                       ("Logins", "auth"), ("Log", "logs"), ("Batch runs", "operations")):
        item = m.get(part, {})
        if not item.get("available"):
            out.append(f"{name}: not measured ({item.get('note', 'unavailable')})")
            continue
        if part == "resources":
            out.append(f"{name}: CPU {item.get('cpu_percent')}%, memory "
                       f"{item.get('memory_percent')}%, disk {item.get('disk_percent')}%")
        elif part == "database":
            out.append(f"{name}: {item.get('size_mb')} MB, {item.get('tables')} tables, "
                       f"journal {item.get('journal_mode')}, query {item.get('catalogue_query_ms')} ms")
        elif part == "auth":
            out.append(f"{name}: success rate {item.get('success_rate')}% over "
                       f"{item.get('window_hours')} h")
        elif part == "logs":
            out.append(f"{name}: {item.get('errors')} error(s), {item.get('warnings')} warning(s) "
                       f"in {item.get('lines_scanned')} lines")
        else:
            out.append(f"{name}: {item.get('runs')} run(s), success rate "
                       f"{item.get('success_rate')}%")
    for f in m.get("findings", []):
        out.append(f"[{f['severity']}] {f['headline']} — {f['detail']}")
    return out
