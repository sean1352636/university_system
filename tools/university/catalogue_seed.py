#!/usr/bin/env python3
"""List the university course/module catalogue, and put it back if it was removed.

The catalogue itself lives in :mod:`catalogue_data` as plain Python literals, so
it survives a database rebuild.  This script is the operational half:

Listing::

    python tools/university/catalogue_seed.py --list
    python tools/university/catalogue_seed.py --list modules --course CS

Checking a database against the catalogue (read-only, the default)::

    python tools/university/catalogue_seed.py --check
    python tools/university/catalogue_seed.py --check --db /path/to/other.db

Putting missing rows back::

    python tools/university/catalogue_seed.py --apply

``--apply`` is additive and idempotent.  It recreates the ``courses`` /
``modules`` tables if they were dropped, inserts rows whose key is absent, and
never updates or deletes a row that is already there — so live edits made since
the catalogue was generated are preserved.  A timestamped copy of the database
is written under ``var/backups/maintenance/catalogue-seed/`` first unless
``--no-backup`` is given.

Regenerating the catalogue after a deliberate change to the real tables::

    python tools/university/catalogue_seed.py --regenerate
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import textwrap
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catalogue_data as cat  # noqa: E402


def _default_db_path() -> Path:
    """Resolve the university DB from the project's central path config."""
    try:
        from education_system import paths
        return Path(paths.UNIVERSITY_DEFAULT_DB_PATH)
    except Exception:
        repo = Path(__file__).resolve().parents[2]
        return repo / "var/data/university/db_files/student_records.db"


def _backup_dir(stamp: str) -> Path:
    """One-off pre-apply backups go to the single maintenance tree."""
    try:
        from education_system import paths
        return paths.maintenance_backup_dir("catalogue-seed", stamp)
    except Exception:
        repo = Path(__file__).resolve().parents[2]
        return repo / "var/backups/maintenance/catalogue-seed" / stamp


def _prune_backups(dest: Path | None = None) -> None:
    """Apply the maintenance retention rule, if the package is importable.

    This tool runs standalone against a bare checkout, so a missing package is
    not an error — it just means no pruning happens on that run.
    """
    try:
        from education_system import paths
    except Exception:
        return
    paths.prune_maintenance_backups("catalogue-seed", exclude=dest)


# ---------------------------------------------------------------------------
# Table plumbing
# ---------------------------------------------------------------------------

class Spec:
    """Everything the seeder needs to know about one catalogue table."""

    def __init__(self, table, key, fields, rows, create_sql, label):
        self.table = table
        self.key = key
        self.fields = fields
        self.rows = rows
        self.create_sql = create_sql
        self.label = label


COURSE_SPEC = Spec(
    "courses", cat.COURSE_KEY, cat.COURSE_FIELDS, cat.COURSES,
    cat.COURSES_TABLE_SQL, "course",
)
MODULE_SPEC = Spec(
    "modules", cat.MODULE_KEY, cat.MODULE_FIELDS, cat.MODULES,
    cat.MODULES_TABLE_SQL, "module",
)
SPECS = {"courses": COURSE_SPEC, "modules": MODULE_SPEC}


def _table_exists(conn, table) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _table_info(conn, table):
    """Return ``{column: (notnull, has_default)}`` for *table*."""
    return {
        r[1]: (bool(r[3]), r[4] is not None or bool(r[5]))
        for r in conn.execute(f"PRAGMA table_info({table})")
    }


def _writable_fields(conn, spec):
    """Catalogue fields that actually exist as columns on the live table."""
    cols = _table_info(conn, spec.table)
    return [f for f in spec.fields if f in cols], cols


def _unsatisfiable(cols, fields):
    """NOT NULL columns with no default that the catalogue cannot supply."""
    return [
        c for c, (notnull, has_default) in cols.items()
        if notnull and not has_default and c not in fields
    ]


def _existing_keys(conn, spec):
    return {
        r[0] for r in conn.execute(
            f"SELECT {spec.key} FROM {spec.table} "
            f"WHERE COALESCE({spec.key}, '') != ''"
        )
    }


def _missing(conn, spec):
    """Return the catalogue rows whose key is absent from the database."""
    if not _table_exists(conn, spec.table):
        return list(spec.rows)
    have = _existing_keys(conn, spec)
    return [r for r in spec.rows if r[spec.key] not in have]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(what, course_filter):
    if what in ("all", "courses"):
        rows = cat.COURSES
        if course_filter:
            rows = [c for c in rows if c[cat.COURSE_KEY] == course_filter]
        print(f"COURSES ({len(rows)})")
        print(f"  {'CODE':<6} {'NAME':<34} {'LEVEL':<14} {'CREDITS':>7}  DEPARTMENT")
        for c in rows:
            print(f"  {c['code']:<6} {c['name'][:34]:<34} "
                  f"{c.get('level', '') or '':<14} {c.get('credits', '') or '':>7}  "
                  f"{c.get('department', '') or ''}")
        print()

    if what in ("all", "modules"):
        rows = cat.MODULES
        if course_filter:
            rows = cat.modules_for_course(course_filter)
        print(f"MODULES ({len(rows)})")
        current = object()
        for m in rows:
            group = m.get("course") or "(no course)"
            if group != current:
                current = group
                print(f"\n  [{group}]")
            year = f"Y{m['year']}" if m.get("year") else "  "
            print(f"    {m['module_code']:<12} {year:<3} "
                  f"{m['module_name'][:44]:<44} "
                  f"{m.get('module_type', '') or '':<12} "
                  f"{m.get('credits', 0) or 0:>3} cr")
        print()

    orphans = [m for m in cat.MODULES
               if m.get("course") and m["course"] not in cat.courses_by_code()]
    if orphans:
        print(f"WARNING: {len(orphans)} modules reference a course not in the "
              f"catalogue: {sorted({m['course'] for m in orphans})}")


def cmd_check(db_path):
    """Report what the catalogue holds that the database does not. Read-only."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        print(f"database: {db_path}\n")
        total_missing = 0
        for spec in (COURSE_SPEC, MODULE_SPEC):
            if not _table_exists(conn, spec.table):
                print(f"  {spec.table}: TABLE MISSING — all {len(spec.rows)} "
                      f"{spec.label}s would be restored")
                total_missing += len(spec.rows)
                continue

            live = conn.execute(f"SELECT COUNT(*) FROM {spec.table}").fetchone()[0]
            missing = _missing(conn, spec)
            total_missing += len(missing)
            fields, cols = _writable_fields(conn, spec)
            dropped = [f for f in spec.fields if f not in cols]

            print(f"  {spec.table}: {live} row(s) live, "
                  f"{len(spec.rows)} in catalogue, {len(missing)} missing")
            if dropped:
                print(f"      columns absent from the live table (will be "
                      f"skipped on insert): {dropped}")
            blockers = _unsatisfiable(cols, fields)
            if blockers:
                print(f"      BLOCKED — NOT NULL columns the catalogue cannot "
                      f"fill: {blockers}")
            for r in missing[:15]:
                print(f"      + {r[spec.key]}  {r.get('name') or r.get('module_name')}")
            if len(missing) > 15:
                print(f"      ... and {len(missing) - 15} more")

            extra = _existing_keys(conn, spec) - {r[spec.key] for r in spec.rows}
            if extra:
                shown = sorted(extra)[:10]
                print(f"      note: {len(extra)} row(s) in the database are not "
                      f"in the catalogue (left alone): {shown}"
                      f"{' ...' if len(extra) > 10 else ''}")
        print()
        if total_missing:
            print(f"{total_missing} row(s) would be inserted. "
                  f"Re-run with --apply to write them.")
        else:
            print("Database matches the catalogue — nothing to insert.")
        return total_missing
    finally:
        conn.close()


def cmd_apply(db_path, do_backup=True):
    db_path = Path(db_path)
    if not db_path.exists():
        print(f"error: no such database: {db_path}", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        plan = []
        for spec in (COURSE_SPEC, MODULE_SPEC):
            missing = _missing(conn, spec)
            if missing:
                plan.append((spec, missing))
        if not plan:
            print("Nothing to do — database already matches the catalogue.")
            return 0

        if do_backup:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = _backup_dir(stamp)
            dest.mkdir(parents=True, exist_ok=True)
            _prune_backups(dest)
            conn.execute("PRAGMA wal_checkpoint(FULL)")
            shutil.copy2(db_path, dest / db_path.name)
            print(f"backup: {dest / db_path.name}")

        inserted = {}
        with conn:
            for spec, missing in plan:
                if not _table_exists(conn, spec.table):
                    print(f"recreating dropped table: {spec.table}")
                    conn.execute(spec.create_sql)

                fields, cols = _writable_fields(conn, spec)
                blockers = _unsatisfiable(cols, fields)
                if blockers:
                    raise SystemExit(
                        f"error: {spec.table} has NOT NULL column(s) the "
                        f"catalogue cannot fill: {blockers} — aborting, no rows "
                        f"written."
                    )

                cols_sql = ", ".join(f'"{f}"' for f in fields)
                placeholders = ", ".join("?" for f in fields)
                sql = (f"INSERT INTO {spec.table} ({cols_sql}) "
                       f"VALUES ({placeholders})")
                conn.executemany(
                    sql, [tuple(r.get(f) for f in fields) for r in missing]
                )
                inserted[spec.table] = len(missing)

        for table, n in inserted.items():
            live = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            print(f"  {table}: inserted {n} row(s) — {live} now live")
        print("\nDone.")
        return 0
    finally:
        conn.close()


def cmd_regenerate(db_path):
    """Rewrite catalogue_data.py from the live tables."""
    out = Path(__file__).resolve().parent / "catalogue_data.py"
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        for spec in (COURSE_SPEC, MODULE_SPEC):
            if not _table_exists(conn, spec.table):
                print(f"error: {spec.table} is missing from {db_path} — "
                      f"refusing to regenerate from an incomplete database.",
                      file=sys.stderr)
                return 1

        courses = [dict(r) for r in conn.execute(
            "SELECT * FROM courses ORDER BY code")]
        modules = [dict(r) for r in conn.execute(
            "SELECT * FROM modules WHERE COALESCE(module_code, '') != '' "
            "ORDER BY COALESCE(course, 'zzz'), COALESCE(year, ''), module_code")]
        courses_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='courses'"
        ).fetchone()[0]
        modules_sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='modules'"
        ).fetchone()[0]

        # Columns the catalogue deliberately drops, so the docstring can name
        # them rather than leaving the omission unexplained.
        omitted = []
        for table, rows in (("courses", courses), ("modules", modules)):
            live_cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
            kept = COURSE_SPEC.fields if table == "courses" else MODULE_SPEC.fields
            omitted += [c for c in live_cols if c not in kept
                        and all(r.get(c) is None for r in rows)]
    finally:
        conn.close()

    def block(rows, fields):
        return "\n".join(
            "    {" + ", ".join(
                f"{f!r}: {r[f]!r}" for f in fields if r.get(f) is not None
            ) + "},"
            for r in rows
        )

    header = f'"""{_regen_docstring(len(courses), len(modules), omitted)}"""\n'
    body = f'''
COURSE_KEY = "code"
MODULE_KEY = "module_code"

COURSE_FIELDS = {cat.COURSE_FIELDS!r}

MODULE_FIELDS = {cat.MODULE_FIELDS!r}

#: ``CREATE TABLE`` statements, used to rebuild a table that was dropped.
COURSES_TABLE_SQL = """{courses_sql}"""

MODULES_TABLE_SQL = """{modules_sql}"""


COURSES = [
{block(courses, cat.COURSE_FIELDS)}
]

MODULES = [
{block(modules, cat.MODULE_FIELDS)}
]
{_HELPERS}'''
    out.write_text(header + body)
    print(f"wrote {out} — {len(courses)} courses, {len(modules)} modules")
    return 0


def _regen_docstring(n_courses, n_modules, omitted=()):
    dropped = textwrap.fill(
        ", ".join(f"``{c}``" for c in sorted(set(omitted))) or "none",
        width=74, initial_indent="  ", subsequent_indent="  ",
    ).lstrip()
    return f'''Static catalogue of university courses and modules.

Generated from ``student_records.db`` — this is the authoritative in-repo copy
of the ``courses`` and ``modules`` tables, so the catalogue survives a database
rebuild.  See ``catalogue_seed.py`` to list it or to put the rows back into a
database they were removed from.

Regenerate after a deliberate catalogue change::

    python tools/university/catalogue_seed.py --regenerate

Counts at generation time: {n_courses} courses, {n_modules} modules.

Notes
-----
* ``courses`` is keyed on ``code``; ``modules`` is keyed on ``module_code``.
* ``current_enrollment`` is a snapshot of live state, not catalogue data — the
  seeder only writes it when creating a row that is missing entirely.
* Rows with an empty ``module_code`` are excluded; they carry no catalogue
  information.
* Columns that were NULL for every row are omitted:
  {dropped}.
'''


_HELPERS = '''

def courses_by_code():
    """Return ``{course code: course dict}``."""
    return {c[COURSE_KEY]: c for c in COURSES}


def modules_by_code():
    """Return ``{module code: module dict}``."""
    return {m[MODULE_KEY]: m for m in MODULES}


def modules_for_course(code):
    """Return the modules belonging to *code*, in year then module-code order."""
    return [m for m in MODULES if m.get("course") == code]


def unassigned_modules():
    """Return modules that are not attached to any course."""
    return [m for m in MODULES if not m.get("course")]
'''


def main(argv=None):
    p = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--db", default=None,
                   help="database to act on (default: the university DB)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--list", nargs="?", const="all",
                   choices=["all", "courses", "modules"],
                   help="print the catalogue and exit")
    g.add_argument("--check", action="store_true",
                   help="report what is missing from the database (default)")
    g.add_argument("--apply", action="store_true",
                   help="insert the missing rows into the database")
    g.add_argument("--regenerate", action="store_true",
                   help="rewrite catalogue_data.py from the live tables")
    p.add_argument("--course", default=None,
                   help="restrict --list to one course code, e.g. CS")
    p.add_argument("--no-backup", action="store_true",
                   help="skip the pre-apply database backup")
    args = p.parse_args(argv)

    db = args.db or _default_db_path()

    if args.list:
        cmd_list(args.list, args.course)
        return 0
    if args.regenerate:
        return cmd_regenerate(db)
    if args.apply:
        return cmd_apply(db, do_backup=not args.no_backup)
    cmd_check(db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
