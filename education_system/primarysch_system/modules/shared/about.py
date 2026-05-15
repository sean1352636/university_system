"""About / system info for the Primary School System.

Read-only helper that gathers metadata for the About dialog and CLI:
version, build info, runtime/platform, paths of the local SQLite DBs,
and quick counts of the largest tables. Nothing here mutates state.
"""

from __future__ import annotations

import logging
import platform
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from education_system.primarysch_system import SYSTEM_NAME
from education_system.primarysch_system import SYSTEM_SLUG
from education_system.primarysch_system.core import paths

logger = logging.getLogger(__name__)

VERSION: str = "1.0.0"
RELEASE_NAME: str = "Primary School Edition"
RELEASE_DATE: str = "2026-05-11"
SYSTEM_KEY: str = "college"   # matches the launcher / role system key

AUTHORS: tuple[str, ...] = (
    "Sean Catchpole (lead developer)",
    "Built on the Education System shared platform.",
)
LICENSE: str = "Proprietary — internal use within the institution"
SUPPORT: str = "support@primary.sch.uk"

# Tables to count in the local DB for the "quick stats" section.
_STATS_TABLES: tuple[tuple[str, str], ...] = (
    ("students",          "Students"),
    ("staff",             "Staff"),
    ("enrolments",        "Enrolments"),
    ("courses",           "Courses"),
    ("class_groups",      "Class groups"),
    ("timetable_slots",   "Timetable slots"),
    ("attendance_records", "Attendance records"),
    ("homework_assignments", "Homework"),
    ("ucas_applications", "UCAS applications"),
    ("safeguarding_concerns", "Safeguarding concerns"),
    ("wellbeing_checkins", "Wellbeing check-ins"),
    ("parent_contacts",   "Parent contacts"),
    ("parents_evenings",  "Parents' evenings"),
    ("notices",           "Notices"),
    ("messages",          "Messages"),
    ("fee_items",         "Fee items"),
    ("bursary_applications", "Bursary applications"),
    ("trips",             "Trips"),
    ("receipts",          "Receipts"),
    ("progress_reviews",  "Progress reviews"),
)


# ── Result types ──────────────────────────────────────────────────

@dataclass
class TableStat:
    table: str
    label: str
    rows: int | None  # None if the table doesn't exist yet


@dataclass
class AboutInfo:
    system_name: str
    system_slug: str
    system_key: str
    version: str
    release_name: str
    release_date: str

    python_version: str
    platform: str
    machine: str
    cwd: str
    db_path: str
    db_exists: bool
    db_size_bytes: int

    authors: tuple[str, ...]
    license: str
    support: str

    current_user: str | None
    current_role: str | None
    table_stats: list[TableStat] = field(default_factory=list)
    generated_at: str = ""

    @property
    def db_size_kb(self) -> float | None:
        if not self.db_exists:
            return None
        return round(self.db_size_bytes / 1024.0, 1)


# ── Builders ──────────────────────────────────────────────────────

def _db_stats() -> list[TableStat]:
    p = paths.PUPILS_DB
    if not Path(p).exists():
        return [TableStat(table=t, label=l, rows=None)
                for t, l in _STATS_TABLES]
    rows: list[TableStat] = []
    try:
        conn = sqlite3.connect(str(p))
        conn.row_factory = sqlite3.Row
        try:
            existing = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            for tbl, label in _STATS_TABLES:
                if tbl not in existing:
                    rows.append(TableStat(table=tbl, label=label,
                                            rows=None))
                    continue
                try:
                    n = conn.execute(
                        f"SELECT COUNT(*) AS n FROM {tbl}"
                    ).fetchone()["n"]
                    rows.append(TableStat(table=tbl, label=label,
                                            rows=int(n)))
                except Exception:
                    rows.append(TableStat(table=tbl, label=label,
                                            rows=None))
        finally:
            conn.close()
    except Exception:
        logger.exception("Could not gather DB stats")
        rows = [TableStat(table=t, label=l, rows=None)
                for t, l in _STATS_TABLES]
    return rows


def build(*, auth: Any = None) -> AboutInfo:
    p = paths.PUPILS_DB
    db_exists = Path(p).exists()
    size = Path(p).stat().st_size if db_exists else 0

    cu_name: str | None = None
    role: str | None = None
    if auth is not None:
        cu = getattr(auth, "current_user", None) or {}
        cu_name = cu.get("username")
        try:
            role = auth.get_role_for_system(SYSTEM_KEY)
        except Exception:
            role = None

    return AboutInfo(
        system_name=SYSTEM_NAME,
        system_slug=SYSTEM_SLUG,
        system_key=SYSTEM_KEY,
        version=VERSION,
        release_name=RELEASE_NAME,
        release_date=RELEASE_DATE,
        python_version=(
            f"{sys.version_info.major}.{sys.version_info.minor}."
            f"{sys.version_info.micro}  "
            f"({platform.python_implementation()})"),
        platform=platform.platform(),
        machine=platform.machine() or "?",
        cwd=str(Path.cwd()),
        db_path=str(p),
        db_exists=db_exists,
        db_size_bytes=size,
        authors=AUTHORS,
        license=LICENSE,
        support=SUPPORT,
        current_user=cu_name,
        current_role=role,
        table_stats=_db_stats(),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )


# ── Convenience renderers ────────────────────────────────────────

def text_report(info: AboutInfo) -> str:
    """A plain-text version of the About info."""
    L: list[str] = []
    L.append("═" * 60)
    L.append(f"  {info.system_name}  v{info.version}")
    L.append(f"  {info.release_name}  ({info.release_date})")
    L.append("═" * 60)
    L.append("")
    L.append("Build")
    L.append("-----")
    L.append(f"  System name   : {info.system_name}")
    L.append(f"  System slug   : {info.system_slug}")
    L.append(f"  System key    : {info.system_key}")
    L.append(f"  Version       : {info.version}")
    L.append(f"  Release       : {info.release_name}")
    L.append(f"  Release date  : {info.release_date}")
    L.append("")
    L.append("Runtime")
    L.append("-------")
    L.append(f"  Python        : {info.python_version}")
    L.append(f"  Platform      : {info.platform}")
    L.append(f"  Machine       : {info.machine}")
    L.append(f"  Working dir   : {info.cwd}")
    L.append("")
    L.append("Local database")
    L.append("--------------")
    L.append(f"  Path          : {info.db_path}")
    if info.db_exists:
        L.append(f"  Size          : {info.db_size_kb} KB")
    else:
        L.append(f"  Size          : (not yet created)")
    L.append("")
    L.append("Session")
    L.append("-------")
    L.append(f"  Signed in as  : {info.current_user or '(none)'}")
    L.append(f"  Role          : {info.current_role or '—'}")
    L.append("")
    L.append("Quick stats")
    L.append("-----------")
    for s in info.table_stats:
        v = "—" if s.rows is None else str(s.rows)
        L.append(f"  {s.label:<22} : {v}")
    L.append("")
    L.append("Credits")
    L.append("-------")
    for a in info.authors:
        L.append(f"  • {a}")
    L.append("")
    L.append("Support / contact")
    L.append("-----------------")
    L.append(f"  License       : {info.license}")
    L.append(f"  Support       : {info.support}")
    L.append("")
    L.append(f"Generated: {info.generated_at}")
    return "\n".join(L)
