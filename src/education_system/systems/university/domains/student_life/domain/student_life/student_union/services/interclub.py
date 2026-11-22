"""Inter-club competitions: competitions, club entries and results.

Backs the Inter-Club Competitions screens, which used to show hardcoded
competitions, clubs and team members. It reuses the existing tables:

* ``club_competitions`` — the competitions themselves.
* ``competition_participants`` — one row per entered team member, keyed
  to the club (``student_clubs``) and the member's student id; a club
  with no members on record enters with a single club-level row
  (``student_id`` NULL). Score and rank are per club, as the existing
  Update Scores screen already writes them. A ``team_name`` column is
  added for the entry's team name.

Clubs come from ``student_clubs`` and members from ``club_members``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

FINISHED = ("completed", "cancelled")

_ensured: set[str] = set()


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dicts(cur) -> list[dict[str, Any]]:
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def ensure_schema(conn) -> None:
    try:
        key = str(conn.execute("PRAGMA database_list").fetchone()[2])
    except Exception:  # pragma: no cover - defensive
        key = str(id(conn))
    if key in _ensured:
        return
    have = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
        "('club_competitions','competition_participants')")}
    if "club_competitions" not in have or "competition_participants" not in have:
        from education_system.systems.university.domains.student_life.domain.student_life.student_union.administration.student_union_core import (
            init_student_union_db,
        )
        init_student_union_db()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(competition_participants)")]
    if "team_name" not in cols:
        conn.execute("ALTER TABLE competition_participants ADD COLUMN team_name TEXT")
    cols = [r[1] for r in conn.execute("PRAGMA table_info(club_competitions)")]
    for col in ("rules", "created_date"):
        if col not in cols:
            # db-audit: ignore[DBW001] - fixed names
            conn.execute(f"ALTER TABLE club_competitions ADD COLUMN {col} TEXT")
    conn.commit()
    _ensured.add(key)


def list_competitions(conn, *, include_finished: bool = False) -> list[dict[str, Any]]:
    ensure_schema(conn)
    sql = ("SELECT c.*, (SELECT COUNT(DISTINCT p.club_id) FROM competition_participants p "
           " WHERE p.competition_id = c.competition_id) AS clubs_entered "
           "FROM club_competitions c")
    if not include_finished:
        sql += " WHERE LOWER(COALESCE(c.status, 'upcoming')) NOT IN ('completed', 'cancelled')"
    sql += " ORDER BY COALESCE(NULLIF(c.start_date, ''), '9999'), c.competition_name"
    return _dicts(conn.execute(sql))


def get_competition(conn, competition_id: int) -> dict[str, Any] | None:
    ensure_schema(conn)
    rows = _dicts(conn.execute("SELECT * FROM club_competitions WHERE competition_id = ?",
                               (competition_id,)))
    return rows[0] if rows else None


def entries(conn, competition_id: int) -> list[dict[str, Any]]:
    """One row per entered club: team name, members, score, rank."""
    ensure_schema(conn)
    rows = _dicts(conn.execute(
        "SELECT p.club_id, sc.club_name, MAX(p.team_name) AS team_name, "
        "MIN(p.registration_date) AS registered, AVG(p.score) AS score, "
        "MIN(p.rank_position) AS rank_position, "
        "GROUP_CONCAT(CASE WHEN p.student_id IS NOT NULL THEN "
        "  COALESCE(s.first_name || ' ' || s.last_name, p.student_id) END, ', ') AS members "
        "FROM competition_participants p "
        "LEFT JOIN student_clubs sc ON sc.club_id = p.club_id "
        "LEFT JOIN students s ON s.student_id = p.student_id "
        "WHERE p.competition_id = ? GROUP BY p.club_id, sc.club_name "
        "ORDER BY COALESCE(MIN(p.rank_position), 999999), AVG(p.score) DESC, sc.club_name",
        (competition_id,)))
    return rows


def clubs_for(conn, owner_id: str | None, *, staff: bool) -> list[dict[str, Any]]:
    """Active clubs the user may enter: all for staff, their own clubs otherwise."""
    ensure_schema(conn)
    if staff:
        return _dicts(conn.execute(
            "SELECT club_id, club_name FROM student_clubs "
            "WHERE LOWER(COALESCE(status, 'active')) = 'active' ORDER BY club_name"))
    if not owner_id:
        return []
    return _dicts(conn.execute(
        "SELECT DISTINCT sc.club_id, sc.club_name FROM student_clubs sc "
        "JOIN club_members cm ON cm.club_id = sc.club_id "
        "WHERE cm.student_id = ? AND LOWER(COALESCE(sc.status, 'active')) = 'active' "
        "ORDER BY sc.club_name", (owner_id,)))


def club_members(conn, club_id: int) -> list[dict[str, Any]]:
    ensure_schema(conn)
    return _dicts(conn.execute(
        "SELECT cm.student_id, COALESCE(s.first_name || ' ' || s.last_name, cm.student_id) AS name, "
        "cm.role FROM club_members cm LEFT JOIN students s ON s.student_id = cm.student_id "
        "WHERE cm.club_id = ? AND cm.student_id IS NOT NULL ORDER BY name", (club_id,)))


def register_entry(conn, competition_id: int, club_id: int, member_ids: list[str],
                   team_name: str = "") -> int:
    """Enter a club; returns the number of rows written. Raises ValueError."""
    ensure_schema(conn)
    comp = get_competition(conn, competition_id)
    if not comp:
        raise ValueError("That competition no longer exists.")
    status = str(comp.get("status") or "upcoming").lower()
    if status in FINISHED:
        raise ValueError(f"This competition is {status}; entries are closed.")
    deadline = (comp.get("registration_deadline") or "").strip()
    if deadline and deadline[:10] < datetime.now().strftime("%Y-%m-%d"):
        raise ValueError(f"The registration deadline ({deadline}) has passed.")
    if conn.execute("SELECT 1 FROM competition_participants WHERE competition_id = ? "
                    "AND club_id = ?", (competition_id, club_id)).fetchone():
        raise ValueError("That club is already entered in this competition.")
    limit = comp.get("max_participants_per_club")
    try:
        limit = int(limit) if limit not in (None, "") else None
    except (TypeError, ValueError):
        limit = None
    if limit and len(member_ids) > limit:
        raise ValueError(f"At most {limit} members per club may be entered.")
    known = {m["student_id"] for m in club_members(conn, club_id)}
    stray = [m for m in member_ids if m not in known]
    if stray:
        raise ValueError("Only members of the club can be entered.")
    if known and not member_ids:
        raise ValueError("Choose at least one team member.")
    team = (team_name or "").strip() or None
    now = _now()
    ids = member_ids or [None]
    for sid in ids:
        conn.execute(
            "INSERT INTO competition_participants (competition_id, club_id, student_id, "
            "registration_date, team_name) VALUES (?, ?, ?, ?, ?)",
            (competition_id, club_id, sid, now, team))
    conn.commit()
    return len(ids)


def standings(conn) -> list[dict[str, Any]]:
    """Overall club standings across all ranked results (podium-weighted)."""
    ensure_schema(conn)
    return _dicts(conn.execute(
        "SELECT sc.club_name, COUNT(DISTINCT r.competition_id) AS entered, "
        "SUM(CASE WHEN r.rank_position = 1 THEN 1 ELSE 0 END) AS gold, "
        "SUM(CASE WHEN r.rank_position = 2 THEN 1 ELSE 0 END) AS silver, "
        "SUM(CASE WHEN r.rank_position = 3 THEN 1 ELSE 0 END) AS bronze "
        "FROM (SELECT competition_id, club_id, MIN(rank_position) AS rank_position "
        "      FROM competition_participants GROUP BY competition_id, club_id) r "
        "JOIN student_clubs sc ON sc.club_id = r.club_id "
        "GROUP BY sc.club_id, sc.club_name "
        "ORDER BY gold DESC, silver DESC, bronze DESC, entered DESC, sc.club_name"))


__all__ = ["club_members", "clubs_for", "ensure_schema", "entries", "get_competition",
           "list_competitions", "register_entry", "standings"]
