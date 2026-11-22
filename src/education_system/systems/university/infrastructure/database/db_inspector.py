"""Inspect and maintain the university SQLite database for the admin screens.

Everything here reports what SQLite itself says - PRAGMAs, ``dbstat``,
``sqlite_master`` and the files on disk - instead of invented figures.

* :func:`inspect_database` is read-only (``mode=ro``).
* :func:`run_maintenance` writes, and is only called when an operator clicks a
  button. It refuses ``VACUUM`` while another process has the database open,
  because VACUUM rewrites the whole file and needs every other connection to
  be idle; connections inside this process cannot be enumerated, so a busy
  one surfaces as SQLite's own "database is locked" error instead.
"""

from __future__ import annotations

import os
import sqlite3
import time
from datetime import datetime
from pathlib import Path


def default_db_path() -> str:
    from education_system.paths import UNIVERSITY_DEFAULT_DB_PATH
    return str(UNIVERSITY_DEFAULT_DB_PATH)


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def fmt_bytes(n: int) -> str:
    value = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{int(value)} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} B"


def _open_ro(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def other_processes_with_db_open(path: str) -> list[dict]:
    """Other processes holding *path* (or its -wal) open, via ``/proc``.

    Linux only; returns ``[]`` where ``/proc`` is unavailable. The current
    process is excluded.
    """
    targets = {os.path.realpath(path), os.path.realpath(path + "-wal")}
    found: list[dict] = []
    proc = Path("/proc")
    if not proc.is_dir():
        return found
    me = os.getpid()
    for entry in proc.iterdir():
        if not entry.name.isdigit() or int(entry.name) == me:
            continue
        try:
            for fd in (entry / "fd").iterdir():
                try:
                    if os.path.realpath(fd) in targets:
                        try:
                            cmd = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                                "utf-8", "replace").strip()
                        except OSError:
                            cmd = ""
                        found.append({"pid": int(entry.name), "command": cmd[:120]})
                        break
                except OSError:
                    continue
        except (OSError, PermissionError):
            continue
    return found


def inspect_database(path: str | None = None, *, integrity: str | None = "quick",
                     table_limit: int = 15) -> dict:
    """Facts about the database. *integrity*: ``"quick"``, ``"full"`` or None."""
    path = path or default_db_path()
    info: dict = {
        "path": path,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "exists": os.path.exists(path),
        "file_size": _size(path),
        "wal_size": _size(path + "-wal"),
        "shm_size": _size(path + "-shm"),
        "errors": [],
    }
    if not info["exists"]:
        info["errors"].append("database file not found")
        return info
    try:
        info["modified"] = datetime.fromtimestamp(os.path.getmtime(path)).strftime(
            "%Y-%m-%d %H:%M:%S")
    except OSError:
        info["modified"] = ""

    start = time.perf_counter()
    try:
        conn = _open_ro(path)
    except sqlite3.Error as exc:
        info["errors"].append(f"cannot open: {exc}")
        return info
    try:
        conn.execute("SELECT 1").fetchone()
        info["open_ms"] = round((time.perf_counter() - start) * 1000, 1)
        info["sqlite_version"] = sqlite3.sqlite_version
        for pragma in ("page_size", "page_count", "freelist_count", "journal_mode",
                       "auto_vacuum", "user_version", "foreign_keys", "synchronous"):
            try:
                # db-audit: ignore[DBW001] - pragma names are literals above
                info[pragma] = conn.execute(f"PRAGMA {pragma}").fetchone()[0]
            except sqlite3.Error:
                info[pragma] = None
        info["auto_vacuum"] = {0: "none", 1: "full", 2: "incremental"}.get(
            info.get("auto_vacuum"), info.get("auto_vacuum"))
        counts = {r["type"]: r["n"] for r in conn.execute(
            "SELECT type, COUNT(*) AS n FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' GROUP BY type")}
        info["tables"] = counts.get("table", 0)
        info["views"] = counts.get("view", 0)
        info["indexes"] = counts.get("index", 0)
        info["triggers"] = counts.get("trigger", 0)

        sizes: dict[str, int] = {}
        try:
            for r in conn.execute("SELECT name, SUM(pgsize) AS bytes FROM dbstat GROUP BY name"):
                sizes[r["name"]] = r["bytes"] or 0
        except sqlite3.Error:
            pass  # dbstat not compiled in

        rows: list[dict] = []
        total_rows = 0
        empty = 0
        for (name,) in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall():
            try:
                # db-audit: ignore[DBW001] - name comes from sqlite_master
                n = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
            except sqlite3.Error:
                continue
            total_rows += n
            empty += 1 if n == 0 else 0
            rows.append({"name": name, "rows": n, "bytes": sizes.get(name, 0)})
        info["total_rows"] = total_rows
        info["empty_tables"] = empty
        rows.sort(key=lambda r: (r["bytes"], r["rows"]), reverse=True)
        info["largest_tables"] = rows[:table_limit]

        index_rows = conn.execute(
            "SELECT name, tbl_name, sql IS NULL AS auto FROM sqlite_master "
            "WHERE type='index' ORDER BY tbl_name, name").fetchall()
        info["index_list"] = [{"name": r["name"], "table": r["tbl_name"],
                               "auto": bool(r["auto"]), "bytes": sizes.get(r["name"], 0)}
                              for r in index_rows]
        info["index_bytes"] = sum(i["bytes"] for i in info["index_list"])
        # Count automatic (UNIQUE / PRIMARY KEY) indexes too, so the total
        # matches the index list.
        info["indexes"] = len(info["index_list"])
        info["auto_indexes"] = sum(1 for i in info["index_list"] if i["auto"])

        if integrity:
            pragma = "integrity_check" if integrity == "full" else "quick_check"
            t0 = time.perf_counter()
            # db-audit: ignore[DBW001] - one of two literals
            result = [r[0] for r in conn.execute(f"PRAGMA {pragma}").fetchmany(50)]
            info["integrity"] = {"check": pragma, "ok": result == ["ok"], "messages": result,
                                 "ms": round((time.perf_counter() - t0) * 1000, 1)}
        try:
            fk = conn.execute("PRAGMA foreign_key_check").fetchmany(1000)
            info["fk_violations"] = len(fk)
        except sqlite3.Error:
            info["fk_violations"] = None
    except sqlite3.Error as exc:
        info["errors"].append(str(exc))
    finally:
        conn.close()

    info["other_processes"] = other_processes_with_db_open(path)
    if info.get("page_count"):
        info["free_pct"] = round(100.0 * (info.get("freelist_count") or 0) / info["page_count"], 1)
    return info


def format_report(info: dict, *, title: str = "DATABASE STATUS REPORT",
                  index_limit: int = 40) -> str:
    """Plain-text report of :func:`inspect_database` output."""
    lines = [title, "=" * len(title), f"Generated: {info.get('generated', '')}", "",
             "FILE:",
             f"- Path: {info.get('path')}",
             f"- Database file: {fmt_bytes(info.get('file_size', 0))}"
             + (f" (modified {info['modified']})" if info.get("modified") else ""),
             f"- WAL file: {fmt_bytes(info.get('wal_size', 0))}",
             f"- Shared-memory file: {fmt_bytes(info.get('shm_size', 0))}"]
    if info.get("errors"):
        lines += ["", "ERRORS:"] + [f"- {e}" for e in info["errors"]]
    if "page_count" in info:
        lines += ["", "ENGINE:",
                  f"- SQLite {info.get('sqlite_version')}, journal mode {info.get('journal_mode')}, "
                  f"synchronous {info.get('synchronous')}, auto-vacuum {info.get('auto_vacuum')}",
                  f"- Page size {info.get('page_size')} B, {info.get('page_count')} pages, "
                  f"{info.get('freelist_count')} free ({info.get('free_pct', 0)}%)",
                  f"- Schema version (user_version): {info.get('user_version')}",
                  f"- Opened read-only in {info.get('open_ms')} ms",
                  "", "SCHEMA:",
                  f"- {info.get('tables')} tables ({info.get('empty_tables')} empty), "
                  f"{info.get('views')} views, {info.get('indexes')} indexes "
                  f"({info.get('auto_indexes', 0)} automatic), "
                  f"{info.get('triggers')} triggers",
                  f"- {info.get('total_rows'):,} rows in total",
                  f"- Index storage: {fmt_bytes(info.get('index_bytes', 0))}"]
    integ = info.get("integrity")
    if integ:
        status = "ok" if integ["ok"] else "PROBLEMS FOUND"
        lines += ["", f"INTEGRITY ({integ['check']}, {integ['ms']} ms): {status}"]
        if not integ["ok"]:
            lines += [f"- {m}" for m in integ["messages"]]
    if info.get("fk_violations") is not None:
        lines.append(f"Foreign key violations: {info['fk_violations']}")
    procs = info.get("other_processes")
    if procs is not None:
        lines += ["", "OTHER PROCESSES WITH THE DATABASE OPEN:"]
        lines += ([f"- pid {p['pid']}: {p['command']}" for p in procs] or ["- none detected"])
    if info.get("largest_tables"):
        lines += ["", "LARGEST TABLES:"]
        for t in info["largest_tables"]:
            lines.append(f"- {t['name']}: {t['rows']:,} rows, {fmt_bytes(t['bytes'])}")
    if info.get("index_list"):
        biggest = sorted(info["index_list"], key=lambda i: i["bytes"], reverse=True)[:index_limit]
        lines += ["", f"INDEXES (largest {len(biggest)} of {len(info['index_list'])}):"]
        for i in biggest:
            kind = " (automatic)" if i["auto"] else ""
            lines.append(f"- {i['name']} on {i['table']}{kind}: {fmt_bytes(i['bytes'])}")
    return "\n".join(lines) + "\n"


def run_maintenance(operations, path: str | None = None) -> dict:
    """Run the chosen operations, in a fixed safe order. Writes to *path*.

    *operations* is a subset of ``{"checkpoint", "analyze", "reindex",
    "vacuum"}``. Returns ``{"before", "after", "steps": [(op, ok, message)]}``.
    """
    path = path or default_db_path()
    ops = set(operations)
    before = inspect_database(path, integrity=None, table_limit=0)
    steps: list[tuple[str, bool, str]] = []

    if "vacuum" in ops:
        others = other_processes_with_db_open(path)
        if others:
            ops.discard("vacuum")
            names = ", ".join(f"pid {p['pid']}" for p in others)
            steps.append(("VACUUM", False,
                          f"refused: the database is open in another process ({names}). "
                          "Close the other application windows or the API server and try again."))

    conn = sqlite3.connect(path, timeout=5)
    try:
        for op, sql in (("checkpoint", "PRAGMA wal_checkpoint(TRUNCATE)"),
                        ("analyze", "ANALYZE"),
                        ("reindex", "REINDEX"),
                        ("vacuum", "VACUUM")):
            if op not in ops:
                continue
            t0 = time.perf_counter()
            try:
                result = conn.execute(sql).fetchall()
                conn.commit()
                ms = round((time.perf_counter() - t0) * 1000)
                detail = ""
                if op == "checkpoint" and result:
                    busy, log_frames, done = result[0]
                    detail = (f" (busy={busy}, {done}/{log_frames} WAL frames written back)"
                              if log_frames >= 0 else "")
                    if busy:
                        steps.append(("WAL checkpoint", False,
                                      f"another connection was busy; partial checkpoint{detail}"))
                        continue
                label = {"checkpoint": "WAL checkpoint"}.get(op, op.upper())
                steps.append((label, True, f"done in {ms} ms{detail}"))
            except sqlite3.Error as exc:
                steps.append((op.upper(), False, str(exc)))
    finally:
        conn.close()

    after = inspect_database(path, integrity=None, table_limit=0)
    return {"before": before, "after": after, "steps": steps}
