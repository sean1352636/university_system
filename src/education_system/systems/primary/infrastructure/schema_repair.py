"""Repair tables the sixth-form copies of primary modules created.

Several primary modules were ported from the sixth form with their schema
unchanged, so their tables declared ``REFERENCES students(student_id)`` (and
Messages ``REFERENCES alumni(alumni_id)``). The primary database has neither
table - pupils live in ``pupils(pupil_id)`` - and foreign keys are on, so
every insert into those tables failed with "no such table".

:func:`repair_links` rewrites any such table in place: same columns, same
rows, the pupil link pointed at ``pupils(pupil_id)`` and links to tables that
never exist in primary dropped. Indexes and triggers are recreated. It runs
once per database per process and is a no-op once a database is clean.
"""

from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

_STUDENT_REF = re.compile(r"REFERENCES\s+students\s*\(\s*student_id\s*\)", re.I)
_ON_ACTION = r"(?:\s+ON\s+(?:DELETE|UPDATE)\s+(?:SET\s+NULL|SET\s+DEFAULT|CASCADE|RESTRICT|NO\s+ACTION))*"
#: Whole ``FOREIGN KEY (...) REFERENCES alumni(...)`` clauses, with the comma
#: that joins them to the column list.
_ALUMNI_FK = re.compile(
    r",\s*FOREIGN\s+KEY\s*\(\s*\w+\s*\)\s*REFERENCES\s+alumni\s*\(\s*\w+\s*\)" + _ON_ACTION,
    re.I)

_done: set[str] = set()


def _fixed_sql(sql: str) -> str:
    return _ALUMNI_FK.sub("", _STUDENT_REF.sub("REFERENCES pupils(pupil_id)", sql))


def repair_links(db_path: str | Path) -> list[str]:
    """Rebuild every table in ``db_path`` that links to ``students`` or
    ``alumni``. Returns the names of the tables rebuilt."""
    key = str(Path(db_path).resolve())
    if key in _done:
        return []
    rebuilt: list[str] = []
    conn = sqlite3.connect(str(db_path))
    try:
        tables = conn.execute(
            "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
        ).fetchall()
        broken = [(n, s) for n, s in tables if _fixed_sql(s) != s]
        if broken:
            conn.execute("PRAGMA foreign_keys=OFF")
            with conn:
                for name, sql in broken:
                    extras = [r[0] for r in conn.execute(
                        "SELECT sql FROM sqlite_master WHERE tbl_name = ? "
                        "AND type IN ('index', 'trigger') AND sql IS NOT NULL", (name,))]
                    tmp = f"{name}__repaired"
                    new_sql = re.sub(
                        r"^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[\"`\[]?" + re.escape(name)
                        + r"[\"`\]]?", f'CREATE TABLE "{tmp}"', _fixed_sql(sql), count=1,
                        flags=re.I)
                    conn.execute(new_sql)
                    cols = ", ".join(f'"{r[1]}"' for r in conn.execute(
                        f'PRAGMA table_info("{name}")'))
                    conn.execute(f'INSERT INTO "{tmp}" ({cols}) SELECT {cols} FROM "{name}"')
                    conn.execute(f'DROP TABLE "{name}"')
                    conn.execute(f'ALTER TABLE "{tmp}" RENAME TO "{name}"')
                    for extra in extras:
                        conn.execute(extra)
                    rebuilt.append(name)
            conn.execute("PRAGMA foreign_keys=ON")
            logger.info("Repaired sixth-form table links in %s: %s", db_path, ", ".join(rebuilt))
    finally:
        conn.close()
    _done.add(key)
    return rebuilt


__all__ = ["repair_links"]
