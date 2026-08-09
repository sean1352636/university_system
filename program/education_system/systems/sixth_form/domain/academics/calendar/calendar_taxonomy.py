"""Departments, tags and type colours for the Sixth Form Calendar.

Sibling to :mod:`calendar`. Three small vocabularies that keep the
events table honest without bloating it:

* **Departments** — the core table's ``department`` column is free
  text, and free text drifts: "Maths", "Mathematics" and "maths " are
  three departments to a filter. This module holds the college's
  actual list, and renaming here renames every event in one go.
* **Tags** — cheaper than growing ``EVENT_TYPES`` every time somebody
  wants to mark ten events as "ofsted-week". A tag is created by
  using it and dies by nobody using it; there is no form to fill in.
* **Type colours** — one colour per event type, editable, with
  defaults chosen so a month grid reads at a glance. Views ask
  :func:`colour_for` and never hard-code a hex again.
"""

from __future__ import annotations

import logging
import re
import sqlite3

from education_system import paths
from education_system.systems.sixth_form.domain.academics.calendar import (
    calendar as core,
)

logger = logging.getLogger(__name__)

DB_PATH = paths.SIXTH_FORM_CALENDAR_DB

ValidationError = core.ValidationError

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Muted, distinguishable defaults — dark enough for white text on a
# month-grid chip, light enough not to shout. Types that behave alike
# share a family: exams amber, whole-college events blue, closures
# grey.
DEFAULT_COLOURS: dict[str, str] = {
    "Lesson Block":      "#4a6fa5",
    "Assembly":          "#5b8db8",
    "Tutor Time":        "#6d9dc5",
    "Meeting":           "#7f8c8d",
    "Trip":              "#2e8b57",
    "Exam":              "#c0762c",
    "Mock Exam":         "#d29d4b",
    "Deadline":          "#b03a3a",
    "Parents' Evening":  "#7d5ba6",
    "Open Day":          "#3e7cb1",
    "Sports Fixture":    "#3a9188",
    "Social":            "#c26f9d",
    "INSET":             "#8a8a8a",
    "Holiday":           "#a0a0a0",
    "Training":          "#946b4c",
    "Assembly Practice": "#9aa96e",
    "Other":             "#6b7280",
}
FALLBACK_COLOUR: str = "#6b7280"


_SCHEMA = """
CREATE TABLE IF NOT EXISTS calendar_departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL COLLATE NOCASE UNIQUE,
    active        INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calendar_tags (
    tag_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL COLLATE NOCASE UNIQUE,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS calendar_event_tags (
    event_id   INTEGER NOT NULL,
    tag_id     INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(event_id, tag_id)
);

CREATE INDEX IF NOT EXISTS idx_cal_evtag_event
    ON calendar_event_tags(event_id);
CREATE INDEX IF NOT EXISTS idx_cal_evtag_tag
    ON calendar_event_tags(tag_id);

CREATE TABLE IF NOT EXISTS calendar_type_colours (
    event_type TEXT PRIMARY KEY,
    colour     TEXT NOT NULL
);
"""


# ── DB plumbing ─────────────────────────────────────────────────────

def _connect() -> sqlite3.Connection:
    paths.ensure_sixth_form_directories()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY: bool = False


def init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    core.init_db()
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        conn.commit()
    logger.debug("Calendar taxonomy schema ready at %s", DB_PATH)
    _DB_READY = True


# ── Departments ─────────────────────────────────────────────────────

def list_departments(*, active_only: bool = True) -> list[str]:
    init_db()
    where = "WHERE active = 1" if active_only else ""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT name FROM calendar_departments {where} "
            "ORDER BY name COLLATE NOCASE").fetchall()
    return [r["name"] for r in rows]


def add_department(name: str) -> str:
    init_db()
    clean = (name or "").strip()
    if not clean:
        raise ValidationError("Department name is required")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO calendar_departments (name, active) "
            "VALUES (?, 1) ON CONFLICT(name) DO UPDATE SET active = 1",
            (clean,))
        conn.commit()
    return clean


def rename_department(old: str, new: str) -> int:
    """Rename the vocabulary entry and every event carrying it.

    Returns how many events moved. This is the whole reason the list
    exists — free text can only be fixed row by row.
    """
    init_db()
    old_clean = (old or "").strip()
    new_clean = (new or "").strip()
    if not old_clean or not new_clean:
        raise ValidationError("Both department names are required")
    add_department(new_clean)
    with _connect() as conn:
        conn.execute(
            "UPDATE calendar_departments SET active = 0 "
            "WHERE name = ? AND name != ?", (old_clean, new_clean))
        cur = conn.execute(
            "UPDATE calendar_events SET department = ?, "
            "updated_at = datetime('now') WHERE department = ?",
            (new_clean, old_clean))
        conn.commit()
    moved = cur.rowcount
    logger.info("Department %r → %r (%d event(s))", old_clean,
                new_clean, moved)
    return moved


def retire_department(name: str) -> bool:
    """Drop a department from the pick list. Events keep the value —
    history does not get rewritten because a department merged."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE calendar_departments SET active = 0 WHERE name = ?",
            ((name or "").strip(),))
        conn.commit()
    return bool(cur.rowcount)


# ── Tags ────────────────────────────────────────────────────────────

def _normalise_tag(name: str) -> str:
    clean = (name or "").strip().lower().replace(" ", "-")
    if not clean:
        raise ValidationError("Tag name is required")
    if len(clean) > 40:
        raise ValidationError("Tag names are capped at 40 characters")
    return clean


def tag_event(event_id: int, name: str) -> str:
    """Attach a tag, creating it on first use."""
    init_db()
    if core.get_event(event_id) is None:
        raise ValidationError(f"No event #{event_id}")
    clean = _normalise_tag(name)
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO calendar_tags (name) VALUES (?)",
            (clean,))
        tag_id = conn.execute(
            "SELECT tag_id FROM calendar_tags WHERE name = ?",
            (clean,)).fetchone()["tag_id"]
        conn.execute(
            "INSERT OR IGNORE INTO calendar_event_tags "
            "(event_id, tag_id) VALUES (?, ?)", (event_id, tag_id))
        conn.commit()
    return clean


def untag_event(event_id: int, name: str) -> bool:
    init_db()
    clean = _normalise_tag(name)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM calendar_event_tags WHERE event_id = ? AND "
            "tag_id = (SELECT tag_id FROM calendar_tags WHERE name = ?)",
            (event_id, clean))
        # A tag nobody uses any more disappears from the pick list.
        conn.execute(
            "DELETE FROM calendar_tags WHERE tag_id NOT IN "
            "(SELECT DISTINCT tag_id FROM calendar_event_tags)")
        conn.commit()
    return bool(cur.rowcount)


def tags_for(event_id: int) -> list[str]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT t.name FROM calendar_tags t "
            "JOIN calendar_event_tags et ON et.tag_id = t.tag_id "
            "WHERE et.event_id = ? ORDER BY t.name",
            (event_id,)).fetchall()
    return [r["name"] for r in rows]


def list_tags() -> list[tuple[str, int]]:
    """Every tag in use, with how many events carry it."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT t.name, COUNT(et.event_id) AS n "
            "FROM calendar_tags t "
            "LEFT JOIN calendar_event_tags et ON et.tag_id = t.tag_id "
            "GROUP BY t.tag_id ORDER BY n DESC, t.name").fetchall()
    return [(r["name"], r["n"]) for r in rows]


def events_with_tag(name: str, *,
                    include_deleted: bool = False) -> list[core.Event]:
    init_db()
    clean = _normalise_tag(name)
    archived = "" if include_deleted else "AND e.deleted_at IS NULL "
    with _connect() as conn:
        rows = conn.execute(
            "SELECT e.* FROM calendar_events e "
            "JOIN calendar_event_tags et ON et.event_id = e.event_id "
            "JOIN calendar_tags t ON t.tag_id = et.tag_id "
            f"WHERE t.name = ? {archived}"
            "ORDER BY e.start_date, e.event_id", (clean,)).fetchall()
    return [core._row(r) for r in rows]


def rename_tag(old: str, new: str) -> int:
    """Rename a tag everywhere; merges into ``new`` if it exists."""
    init_db()
    old_clean = _normalise_tag(old)
    new_clean = _normalise_tag(new)
    if old_clean == new_clean:
        return 0
    with _connect() as conn:
        old_row = conn.execute(
            "SELECT tag_id FROM calendar_tags WHERE name = ?",
            (old_clean,)).fetchone()
        if old_row is None:
            raise ValidationError(f"No tag {old_clean!r}")
        new_row = conn.execute(
            "SELECT tag_id FROM calendar_tags WHERE name = ?",
            (new_clean,)).fetchone()
        if new_row is None:
            cur = conn.execute(
                "UPDATE calendar_tags SET name = ? WHERE tag_id = ?",
                (new_clean, old_row["tag_id"]))
            conn.commit()
            n = conn.execute(
                "SELECT COUNT(*) FROM calendar_event_tags "
                "WHERE tag_id = ?", (old_row["tag_id"],)).fetchone()[0]
            return int(n)
        # Merge: repoint, dropping links that would collide.
        cur = conn.execute(
            "UPDATE OR IGNORE calendar_event_tags SET tag_id = ? "
            "WHERE tag_id = ?", (new_row["tag_id"], old_row["tag_id"]))
        moved = cur.rowcount
        conn.execute("DELETE FROM calendar_event_tags WHERE tag_id = ?",
                     (old_row["tag_id"],))
        conn.execute("DELETE FROM calendar_tags WHERE tag_id = ?",
                     (old_row["tag_id"],))
        conn.commit()
    logger.info("Tag %r merged into %r (%d link(s))", old_clean,
                new_clean, moved)
    return moved


# ── Type colours ────────────────────────────────────────────────────

def colour_for(event_type: str) -> str:
    """The colour a view should paint this type. Never raises — an
    unknown type gets the fallback grey rather than crashing a grid."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT colour FROM calendar_type_colours "
            "WHERE event_type = ?", (event_type,)).fetchone()
    if r:
        return r["colour"]
    return DEFAULT_COLOURS.get(event_type, FALLBACK_COLOUR)


def palette() -> dict[str, str]:
    """The full type → colour mapping, overrides applied."""
    init_db()
    out = dict(DEFAULT_COLOURS)
    with _connect() as conn:
        for r in conn.execute(
                "SELECT event_type, colour FROM calendar_type_colours"):
            out[r["event_type"]] = r["colour"]
    return out


def set_colour(event_type: str, colour: str) -> str:
    init_db()
    if event_type not in core.EVENT_TYPES:
        raise ValidationError(
            f"Event type must be one of: {', '.join(core.EVENT_TYPES)}")
    clean = (colour or "").strip()
    if not _HEX_RE.match(clean):
        raise ValidationError("Colour must be #RRGGBB")
    clean = clean.lower()
    with _connect() as conn:
        conn.execute(
            "INSERT INTO calendar_type_colours (event_type, colour) "
            "VALUES (?, ?) ON CONFLICT(event_type) "
            "DO UPDATE SET colour = excluded.colour",
            (event_type, clean))
        conn.commit()
    return clean


def reset_colour(event_type: str) -> str:
    """Back to the shipped default."""
    init_db()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM calendar_type_colours WHERE event_type = ?",
            (event_type,))
        conn.commit()
    return DEFAULT_COLOURS.get(event_type, FALLBACK_COLOUR)
