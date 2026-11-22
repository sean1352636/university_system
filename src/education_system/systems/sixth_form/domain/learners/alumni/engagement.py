"""Sixth-form alumni — Engagement extensions (#1-#8): social handles, connections, chapters, engagement score, re-engagement, milestones, lost contact, directory.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    Alumnus,
    CHAPTER_ROLES,
    CONNECTION_KINDS,
    Consent,
    DIRECTORY_CONSENT_SCOPE,
    HARD_BOUNCE_THRESHOLD,
    SOCIAL_PLATFORMS,
    _log_action,
)
from .db import (
    ValidationError,
    _connect,
    _row,
    _validate_date,
    init_db,
)


# ── #1 Social handles ─────────────────────────────────────────────

@dataclass
class SocialHandle:
    handle_id: int
    alumni_id: int
    platform: str
    handle: str
    url: str | None
    verified: bool
    verified_at: str | None
    notes: str | None
    created_at: str


def _row_social(r: db.Row) -> SocialHandle:
    return SocialHandle(
        handle_id=r["handle_id"], alumni_id=r["alumni_id"],
        platform=r["platform"], handle=r["handle"],
        url=r["url"],
        verified=bool(r["verified"]),
        verified_at=r["verified_at"],
        notes=r["notes"], created_at=r["created_at"])


def add_social_handle(alumni_id: int, platform: str, handle: str, *,
                        url: str | None = None,
                        verified: bool = False,
                        notes: str | None = None,
                        actor: str | None = None) -> SocialHandle:
    init_db()
    platform = (platform or "").strip()
    handle = (handle or "").strip()
    if not platform:
        raise ValidationError("Platform is required")
    if platform not in SOCIAL_PLATFORMS:
        raise ValidationError(
            f"Platform must be one of: {', '.join(SOCIAL_PLATFORMS)}")
    if not handle:
        raise ValidationError("Handle is required")
    verified_at = (
        _dt.datetime.now().isoformat(timespec="seconds")
        if verified else None)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        try:
            cur = conn.execute(
                """INSERT INTO alumni_social_handles
                       (alumni_id, platform, handle, url, verified,
                        verified_at, notes)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (alumni_id, platform, handle,
                 (url or "").strip() or None,
                 1 if verified else 0, verified_at,
                 (notes or "").strip() or None))
        except db.IntegrityError as exc:
            raise ValidationError(
                "That platform/handle is already recorded for this "
                "alumnus") from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_social_handles WHERE handle_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("social.add", actor=actor, alumni_id=alumni_id,
                  platform=platform, handle=handle, verified=verified)
    return _row_social(r)


def list_social_handles(alumni_id: int) -> list[SocialHandle]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_social_handles "
            "WHERE alumni_id = ? "
            "ORDER BY platform COLLATE NOCASE, handle_id",
            (alumni_id,)).fetchall()
    return [_row_social(r) for r in rows]


def update_social_handle(handle_id: int,
                           payload: dict[str, Any], *,
                           actor: str | None = None) -> SocialHandle:
    init_db()
    fields: dict[str, Any] = {}
    if "url" in payload:
        fields["url"] = (payload["url"] or "").strip() or None
    if "handle" in payload:
        h = (payload["handle"] or "").strip()
        if not h:
            raise ValidationError("Handle is required")
        fields["handle"] = h
    if "notes" in payload:
        fields["notes"] = (payload["notes"] or "").strip() or None
    if "verified" in payload:
        fields["verified"] = 1 if payload["verified"] else 0
        fields["verified_at"] = (
            _dt.datetime.now().isoformat(timespec="seconds")
            if payload["verified"] else None)
    if not fields:
        with _connect() as conn:
            r = conn.execute(
                "SELECT * FROM alumni_social_handles WHERE handle_id=?",
                (handle_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No social handle #{handle_id}")
        return _row_social(r)
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = list(fields.values()) + [handle_id]
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE alumni_social_handles SET {sets} "
            f"WHERE handle_id = ?", vals)
        if cur.rowcount == 0:
            raise ValidationError(f"No social handle #{handle_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_social_handles WHERE handle_id = ?",
            (handle_id,)).fetchone()
    _log_action("social.update", actor=actor,
                  handle_id=handle_id, **{k: v for k, v in fields.items()
                                          if k != "verified_at"})
    return _row_social(r)


def verify_social_handle(handle_id: int, *,
                          actor: str | None = None) -> SocialHandle:
    return update_social_handle(handle_id, {"verified": True},
                                  actor=actor)


def delete_social_handle(handle_id: int, *,
                           actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_social_handles WHERE handle_id = ?",
            (handle_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("social.delete", actor=actor, handle_id=handle_id)
    return cur.rowcount > 0


# ── #2 Connections graph ──────────────────────────────────────────

@dataclass
class Connection:
    connection_id: int
    a_id: int
    b_id: int
    kind: str
    since: str | None
    notes: str | None
    created_at: str


def _row_connection(r: db.Row) -> Connection:
    return Connection(
        connection_id=r["connection_id"],
        a_id=r["a_id"], b_id=r["b_id"],
        kind=r["kind"], since=r["since"],
        notes=r["notes"], created_at=r["created_at"])


def _normalise_pair(a: int, b: int) -> tuple[int, int]:
    if a == b:
        raise ValidationError(
            "An alumnus cannot be connected to themselves")
    return (a, b) if a < b else (b, a)


def connect_alumni(alumni_a: int, alumni_b: int, *,
                    kind: str = "Friend",
                    since: str | None = None,
                    notes: str | None = None,
                    actor: str | None = None) -> Connection:
    init_db()
    if kind not in CONNECTION_KINDS:
        raise ValidationError(
            f"Kind must be one of: {', '.join(CONNECTION_KINDS)}")
    lo, hi = _normalise_pair(alumni_a, alumni_b)
    since_iso = _validate_date(since, "Since", required=False)
    with _connect() as conn:
        _require_alumnus(conn, lo)
        _require_alumnus(conn, hi)
        existing = conn.execute(
            "SELECT * FROM alumni_connections "
            "WHERE a_id = ? AND b_id = ?", (lo, hi)).fetchone()
        if existing:
            return _row_connection(existing)
        cur = conn.execute(
            """INSERT INTO alumni_connections
                   (a_id, b_id, kind, since, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (lo, hi, kind, since_iso,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_connections WHERE connection_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("connection.create", actor=actor,
                  a_id=lo, b_id=hi, kind=kind)
    return _row_connection(r)


def disconnect_alumni(alumni_a: int, alumni_b: int, *,
                       actor: str | None = None) -> bool:
    init_db()
    lo, hi = _normalise_pair(alumni_a, alumni_b)
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_connections "
            "WHERE a_id = ? AND b_id = ?", (lo, hi))
        conn.commit()
    if cur.rowcount:
        _log_action("connection.delete", actor=actor,
                      a_id=lo, b_id=hi)
    return cur.rowcount > 0


def list_connections(alumni_id: int) -> list[tuple[Connection, Alumnus]]:
    """Return all connections involving ``alumni_id``, each paired with
    the other party's Alumnus row."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT c.*,
                      CASE WHEN c.a_id = ? THEN c.b_id
                           ELSE c.a_id END AS other_id
                 FROM alumni_connections c
                WHERE c.a_id = ? OR c.b_id = ?
                ORDER BY c.created_at DESC""",
            (alumni_id, alumni_id, alumni_id)).fetchall()
        out: list[tuple[Connection, Alumnus]] = []
        for r in rows:
            other = conn.execute(
                "SELECT * FROM alumni WHERE alumni_id = ?",
                (r["other_id"],)).fetchone()
            if other is None:
                continue
            out.append((_row_connection(r), _row(other)))
    return out


def _neighbours(conn: db.Connection, alumni_id: int) -> set[int]:
    rows = conn.execute(
        "SELECT a_id, b_id FROM alumni_connections "
        "WHERE a_id = ? OR b_id = ?",
        (alumni_id, alumni_id)).fetchall()
    out: set[int] = set()
    for r in rows:
        out.add(r["b_id"] if r["a_id"] == alumni_id else r["a_id"])
    return out


def mutuals_of(alumni_a: int, alumni_b: int) -> list[Alumnus]:
    init_db()
    with _connect() as conn:
        common = _neighbours(conn, alumni_a) & _neighbours(conn, alumni_b)
        if not common:
            return []
        placeholders = ",".join("?" * len(common))
        rows = conn.execute(
            f"SELECT * FROM alumni WHERE alumni_id IN ({placeholders}) "
            "ORDER BY last_name, first_name", tuple(common)).fetchall()
    return [_row(r) for r in rows]


def degrees_between(alumni_a: int, alumni_b: int, *,
                      max_depth: int = 6) -> int | None:
    """BFS over the undirected connection graph. Returns the number of
    hops separating the two alumni, or ``None`` if no path is found
    within ``max_depth``."""
    init_db()
    if alumni_a == alumni_b:
        return 0
    visited: set[int] = {alumni_a}
    frontier: set[int] = {alumni_a}
    with _connect() as conn:
        for depth in range(1, max_depth + 1):
            nxt: set[int] = set()
            for node in frontier:
                for n in _neighbours(conn, node):
                    if n in visited:
                        continue
                    if n == alumni_b:
                        return depth
                    nxt.add(n)
            if not nxt:
                return None
            visited |= nxt
            frontier = nxt
    return None


# ── #3 Chapters ───────────────────────────────────────────────────

CHAPTER_KINDS: tuple[str, ...] = (
    "Regional", "Industry", "Cohort", "Affinity", "Other",
)


@dataclass
class Chapter:
    chapter_id: int
    name: str
    kind: str
    region: str | None
    description: str | None
    status: str
    created_at: str


@dataclass
class ChapterMembership:
    chapter_id: int
    alumni_id: int
    role: str
    joined_on: str | None
    left_on: str | None


def _row_chapter(r: db.Row) -> Chapter:
    return Chapter(
        chapter_id=r["chapter_id"], name=r["name"],
        kind=r["kind"], region=r["region"],
        description=r["description"], status=r["status"],
        created_at=r["created_at"])


def _row_chapter_member(r: db.Row) -> ChapterMembership:
    return ChapterMembership(
        chapter_id=r["chapter_id"], alumni_id=r["alumni_id"],
        role=r["role"], joined_on=r["joined_on"],
        left_on=r["left_on"])


def create_chapter(name: str, *, kind: str = "Regional",
                     region: str | None = None,
                     description: str | None = None,
                     actor: str | None = None) -> Chapter:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Chapter name is required")
    if kind not in CHAPTER_KINDS:
        raise ValidationError(
            f"Kind must be one of: {', '.join(CHAPTER_KINDS)}")
    with _connect() as conn:
        try:
            cur = conn.execute(
                """INSERT INTO alumni_chapters
                       (name, kind, region, description)
                   VALUES (?, ?, ?, ?)""",
                (name, kind,
                 (region or "").strip() or None,
                 (description or "").strip() or None))
        except db.IntegrityError as exc:
            raise ValidationError(
                f"A chapter named {name!r} already exists") from exc
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_chapters WHERE chapter_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("chapter.create", actor=actor, name=name, kind=kind)
    return _row_chapter(r)


def list_chapters(*, status: str | None = None,
                    kind: str | None = None) -> list[Chapter]:
    init_db()
    sql = "SELECT * FROM alumni_chapters WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if kind:
        sql += " AND kind = ?"
        params.append(kind)
    sql += " ORDER BY name COLLATE NOCASE"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_chapter(r) for r in rows]


def get_chapter(chapter_id: int) -> Chapter | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_chapters WHERE chapter_id = ?",
            (chapter_id,)).fetchone()
    return _row_chapter(r) if r else None


def update_chapter(chapter_id: int, payload: dict[str, Any], *,
                     actor: str | None = None) -> Chapter:
    init_db()
    fields: dict[str, Any] = {}
    for key in ("name", "region", "description"):
        if key in payload:
            val = (payload[key] or "").strip()
            if key == "name" and not val:
                raise ValidationError("Chapter name is required")
            fields[key] = val or None
    if "kind" in payload:
        if payload["kind"] not in CHAPTER_KINDS:
            raise ValidationError(
                f"Kind must be one of: {', '.join(CHAPTER_KINDS)}")
        fields["kind"] = payload["kind"]
    if "status" in payload:
        fields["status"] = payload["status"]
    if not fields:
        existing = get_chapter(chapter_id)
        if not existing:
            raise ValidationError(f"No chapter #{chapter_id}")
        return existing
    sets = ", ".join(f"{k} = ?" for k in fields)
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE alumni_chapters SET {sets} WHERE chapter_id = ?",
            list(fields.values()) + [chapter_id])
        if cur.rowcount == 0:
            raise ValidationError(f"No chapter #{chapter_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_chapters WHERE chapter_id = ?",
            (chapter_id,)).fetchone()
    _log_action("chapter.update", actor=actor,
                  chapter_id=chapter_id, **fields)
    return _row_chapter(r)


def delete_chapter(chapter_id: int, *,
                     actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_chapters WHERE chapter_id = ?",
            (chapter_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("chapter.delete", actor=actor,
                      chapter_id=chapter_id)
    return cur.rowcount > 0


def add_chapter_member(chapter_id: int, alumni_id: int, *,
                         role: str = "Member",
                         joined_on: str | None = None,
                         actor: str | None = None
                         ) -> ChapterMembership:
    init_db()
    if role not in CHAPTER_ROLES:
        raise ValidationError(
            f"Role must be one of: {', '.join(CHAPTER_ROLES)}")
    joined_iso = _validate_date(joined_on, "Joined on", required=False)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        existing = conn.execute(
            "SELECT * FROM alumni_chapter_members "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (chapter_id, alumni_id)).fetchone()
        if existing:
            conn.execute(
                "UPDATE alumni_chapter_members "
                "SET role = ?, joined_on = COALESCE(?, joined_on), "
                "    left_on = NULL "
                "WHERE chapter_id = ? AND alumni_id = ?",
                (role, joined_iso, chapter_id, alumni_id))
        else:
            conn.execute(
                """INSERT INTO alumni_chapter_members
                       (chapter_id, alumni_id, role, joined_on)
                   VALUES (?, ?, ?, ?)""",
                (chapter_id, alumni_id, role, joined_iso))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_chapter_members "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (chapter_id, alumni_id)).fetchone()
    _log_action("chapter.add_member", actor=actor,
                  chapter_id=chapter_id, alumni_id=alumni_id, role=role)
    return _row_chapter_member(r)


def set_chapter_role(chapter_id: int, alumni_id: int, role: str, *,
                       actor: str | None = None) -> ChapterMembership:
    init_db()
    if role not in CHAPTER_ROLES:
        raise ValidationError(
            f"Role must be one of: {', '.join(CHAPTER_ROLES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_chapter_members SET role = ? "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (role, chapter_id, alumni_id))
        if cur.rowcount == 0:
            raise ValidationError("Member not in chapter")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_chapter_members "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (chapter_id, alumni_id)).fetchone()
    _log_action("chapter.set_role", actor=actor,
                  chapter_id=chapter_id, alumni_id=alumni_id, role=role)
    return _row_chapter_member(r)


def remove_chapter_member(chapter_id: int, alumni_id: int, *,
                            when: str | None = None,
                            actor: str | None = None) -> bool:
    """Soft-removes by stamping ``left_on``. Pass ``when=None`` for
    today. Use :func:`purge_chapter_member` to hard-delete."""
    init_db()
    left_iso = (
        _validate_date(when, "Left on", required=False)
        or _dt.date.today().isoformat())
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_chapter_members SET left_on = ? "
            "WHERE chapter_id = ? AND alumni_id = ? AND left_on IS NULL",
            (left_iso, chapter_id, alumni_id))
        conn.commit()
    if cur.rowcount:
        _log_action("chapter.remove_member", actor=actor,
                      chapter_id=chapter_id, alumni_id=alumni_id)
    return cur.rowcount > 0


def purge_chapter_member(chapter_id: int, alumni_id: int, *,
                           actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_chapter_members "
            "WHERE chapter_id = ? AND alumni_id = ?",
            (chapter_id, alumni_id))
        conn.commit()
    if cur.rowcount:
        _log_action("chapter.purge_member", actor=actor,
                      chapter_id=chapter_id, alumni_id=alumni_id)
    return cur.rowcount > 0


def list_chapter_members(chapter_id: int, *,
                           include_left: bool = False
                           ) -> list[tuple[ChapterMembership, Alumnus]]:
    init_db()
    sql = ("SELECT m.*, a.* FROM alumni_chapter_members m "
            "JOIN alumni a ON a.alumni_id = m.alumni_id "
            "WHERE m.chapter_id = ?")
    if not include_left:
        sql += " AND m.left_on IS NULL"
    sql += " ORDER BY a.last_name, a.first_name"
    with _connect() as conn:
        rows = conn.execute(sql, (chapter_id,)).fetchall()
    out: list[tuple[ChapterMembership, Alumnus]] = []
    for r in rows:
        out.append((_row_chapter_member(r), _row(r)))
    return out


def list_chapters_for(alumni_id: int, *,
                        include_left: bool = False
                        ) -> list[tuple[ChapterMembership, Chapter]]:
    init_db()
    sql = ("SELECT m.*, c.* FROM alumni_chapter_members m "
            "JOIN alumni_chapters c ON c.chapter_id = m.chapter_id "
            "WHERE m.alumni_id = ?")
    if not include_left:
        sql += " AND m.left_on IS NULL"
    sql += " ORDER BY c.name COLLATE NOCASE"
    with _connect() as conn:
        rows = conn.execute(sql, (alumni_id,)).fetchall()
    out: list[tuple[ChapterMembership, Chapter]] = []
    for r in rows:
        out.append((_row_chapter_member(r), _row_chapter(r)))
    return out


# ── #4 Engagement score ──────────────────────────────────────────

@dataclass
class EngagementScore:
    alumni_id: int
    score: float
    comms_opens: int
    events_attended: int
    donations_count: int
    donation_total_pence: int
    volunteer_hours: float
    months_since_contact: int | None
    decay: float


# Weights tuned for typical usage. Adjust here, not at call sites.
_ENG_WEIGHTS = {
    "comms_open":       1.0,
    "event_attended":   8.0,
    "rsvp_yes":         3.0,
    "donation_each":    6.0,
    "donation_per_£10": 0.5,
    "volunteer_per_hr": 2.0,
    "mentor_active":    10.0,
    "speaker_profile":  5.0,
    "wxp_offer":        4.0,
}


def _months_between(iso_date: str | None,
                      now: _dt.date | None = None) -> int | None:
    if not iso_date:
        return None
    try:
        d = _dt.date.fromisoformat(iso_date[:10])
    except ValueError:
        return None
    now = now or _dt.date.today()
    return (now.year - d.year) * 12 + (now.month - d.month)


def compute_engagement_score(alumni_id: int) -> EngagementScore:
    """Composite engagement score for one alumnus.

    Aggregates communications opens, event attendance and RSVPs,
    donation count and total, volunteer hours, active mentorship,
    speaker profile, and work-experience offers. Multiplies the raw
    sum by a recency-decay factor based on ``last_contacted``."""
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT last_contacted FROM alumni WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No alumnus #{alumni_id}")
        last_contacted = r["last_contacted"]
        events_attended = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_event_rsvps "
            "WHERE alumni_id = ? AND attended = 1",
            (alumni_id,)).fetchone()[0])
        rsvp_yes = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_event_rsvps "
            "WHERE alumni_id = ? AND status = 'Yes' AND attended = 0",
            (alumni_id,)).fetchone()[0])
        don = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(amount_pence),0) AS t "
            "FROM alumni_donations WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
        donations_count = int(don["n"])
        donation_total = int(don["t"])
        vol_hours = float(conn.execute(
            "SELECT COALESCE(SUM(hours),0) FROM alumni_volunteer_hours "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()[0])
        active_mentor = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_mentorships "
            "WHERE mentor_alumni_id = ? AND status = 'Active'",
            (alumni_id,)).fetchone()[0])
        speaker = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_speakers WHERE alumni_id = ?",
            (alumni_id,)).fetchone()[0])
        wxp = int(conn.execute(
            "SELECT COUNT(*) FROM alumni_work_exp_offers "
            "WHERE alumni_id = ? AND status = 'Open'",
            (alumni_id,)).fetchone()[0])
    # Comms-open count comes from the shared messages module if it
    # has the corresponding bookkeeping; otherwise treat as 0.
    comms_opens = _count_comms_opens(alumni_id)
    raw = (
        comms_opens     * _ENG_WEIGHTS["comms_open"]
        + events_attended * _ENG_WEIGHTS["event_attended"]
        + rsvp_yes        * _ENG_WEIGHTS["rsvp_yes"]
        + donations_count * _ENG_WEIGHTS["donation_each"]
        + (donation_total / 1000.0) * _ENG_WEIGHTS["donation_per_£10"]
        + vol_hours       * _ENG_WEIGHTS["volunteer_per_hr"]
        + active_mentor   * _ENG_WEIGHTS["mentor_active"]
        + speaker         * _ENG_WEIGHTS["speaker_profile"]
        + wxp             * _ENG_WEIGHTS["wxp_offer"])
    months = _months_between(last_contacted)
    if months is None:
        decay = 0.5  # never contacted — heavy decay
    elif months <= 3:
        decay = 1.0
    elif months <= 12:
        decay = 0.85
    elif months <= 24:
        decay = 0.6
    elif months <= 48:
        decay = 0.35
    else:
        decay = 0.15
    return EngagementScore(
        alumni_id=alumni_id,
        score=round(raw * decay, 2),
        comms_opens=comms_opens,
        events_attended=events_attended,
        donations_count=donations_count,
        donation_total_pence=donation_total,
        volunteer_hours=vol_hours,
        months_since_contact=months,
        decay=decay)


def _count_comms_opens(alumni_id: int) -> int:
    """Pulled out so it stays defensive: the shared ``messages`` table
    may not have an ``opened_at`` column on older deployments."""
    try:
        msgs = _messages_module()
    except Exception:
        return 0
    db_path = getattr(msgs, "DB_PATH", None)
    if not db_path:
        return 0
    try:
        with db.connect(str(db_path)) as conn:
            conn.row_factory = db.Row
            cols = {row[1] for row in conn.execute(
                "PRAGMA table_info(messages)").fetchall()}
            if "opened_at" not in cols or "alumni_id" not in cols:
                return 0
            r = conn.execute(
                "SELECT COUNT(*) FROM messages "
                "WHERE alumni_id = ? AND opened_at IS NOT NULL",
                (alumni_id,)).fetchone()
            return int(r[0]) if r else 0
    except db.Error:
        return 0


def engagement_leaderboard(*, limit: int = 50,
                              leaving_year: str | None = None
                              ) -> list[EngagementScore]:
    init_db()
    sql = "SELECT alumni_id FROM alumni WHERE status = 'Active'"
    params: list[Any] = []
    if leaving_year:
        sql += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        ids = [r["alumni_id"] for r in conn.execute(sql, params).fetchall()]
    scored = [compute_engagement_score(a) for a in ids]
    scored.sort(key=lambda s: s.score, reverse=True)
    return scored[:limit]


# ── #5 Re-engagement worklist ─────────────────────────────────────

@dataclass
class ReEngagementCandidate:
    alumnus: Alumnus
    score: float
    months_since_contact: int | None
    reason: str


def re_engagement_worklist(*, score_threshold: float = 5.0,
                              months_quiet: int = 18,
                              leaving_year: str | None = None,
                              limit: int = 100
                              ) -> list[ReEngagementCandidate]:
    """Active alumni whose engagement score has fallen below
    ``score_threshold`` *or* who have had no contact for at least
    ``months_quiet`` months — ranked by who is most worth reaching
    again (highest historical engagement first, then longest gap)."""
    init_db()
    sql = ("SELECT * FROM alumni WHERE status = 'Active' "
            "AND deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    out: list[ReEngagementCandidate] = []
    for r in rows:
        a = _row(r)
        es = compute_engagement_score(a.alumni_id)
        quiet = (es.months_since_contact is None
                   or es.months_since_contact >= months_quiet)
        below = es.score < score_threshold
        if not (quiet or below):
            continue
        reasons = []
        if below:
            reasons.append(f"score {es.score} < {score_threshold}")
        if quiet:
            gap = (f"{es.months_since_contact}mo"
                    if es.months_since_contact is not None
                    else "never contacted")
            reasons.append(f"quiet ({gap})")
        out.append(ReEngagementCandidate(
            alumnus=a, score=es.score,
            months_since_contact=es.months_since_contact,
            reason="; ".join(reasons)))
    # Highest historical engagement first; tie-break on longest gap.
    out.sort(key=lambda c: (-c.score,
                              -(c.months_since_contact or 999)))
    return out[:limit]


# ── #6 Milestones / reminders ─────────────────────────────────────

MILESTONE_KINDS: tuple[str, ...] = (
    "Birthday", "Graduation Anniversary", "Work Anniversary",
)


@dataclass
class Milestone:
    alumni_id: int
    full_name: str
    kind: str
    when: str            # next-occurrence ISO date
    years: int | None    # 5, 10, 25 etc. for anniversaries
    detail: str | None   # employer/role for work anniversaries


def _next_anniversary(original: str | None,
                        now: _dt.date) -> tuple[_dt.date, int] | None:
    if not original:
        return None
    try:
        d = _dt.date.fromisoformat(original[:10])
    except ValueError:
        return None
    candidate = d.replace(year=now.year) if d.month != 2 or d.day != 29 \
        else _dt.date(now.year, 2, 28)
    if candidate < now:
        try:
            candidate = d.replace(year=now.year + 1)
        except ValueError:
            candidate = _dt.date(now.year + 1, 2, 28)
    years = candidate.year - d.year
    return candidate, years


def upcoming_milestones(*, days: int = 30,
                          kinds: tuple[str, ...] | None = None,
                          today: _dt.date | None = None
                          ) -> list[Milestone]:
    """Birthdays, graduation anniversaries and work anniversaries
    landing in the next ``days`` days.

    Graduation anniversaries fire only on round years (1, 5, 10, 15,
    20, 25, …). Work anniversaries fire on every year ≥ 1."""
    init_db()
    today = today or _dt.date.today()
    horizon = today + _dt.timedelta(days=days)
    wanted = set(kinds or MILESTONE_KINDS)
    out: list[Milestone] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT alumni_id, first_name, last_name, preferred_name, "
            "       dob, leaving_date "
            "FROM alumni WHERE status = 'Active' AND deleted_at IS NULL"
        ).fetchall()
        for r in rows:
            full = f"{r['preferred_name'] or r['first_name']} " \
                     f"{r['last_name']}"
            if "Birthday" in wanted:
                nxt = _next_anniversary(r["dob"], today)
                if nxt and today <= nxt[0] <= horizon:
                    out.append(Milestone(
                        alumni_id=r["alumni_id"], full_name=full,
                        kind="Birthday",
                        when=nxt[0].isoformat(), years=nxt[1],
                        detail=None))
            if "Graduation Anniversary" in wanted:
                nxt = _next_anniversary(r["leaving_date"], today)
                if nxt and today <= nxt[0] <= horizon \
                        and nxt[1] >= 1 \
                        and (nxt[1] == 1 or nxt[1] % 5 == 0):
                    out.append(Milestone(
                        alumni_id=r["alumni_id"], full_name=full,
                        kind="Graduation Anniversary",
                        when=nxt[0].isoformat(), years=nxt[1],
                        detail=None))
        if "Work Anniversary" in wanted:
            crows = conn.execute(
                "SELECT c.alumni_id, c.role, c.employer, c.start_date, "
                "       a.first_name, a.last_name, a.preferred_name "
                "FROM alumni_career c "
                "JOIN alumni a ON a.alumni_id = c.alumni_id "
                "WHERE c.is_current = 1 AND a.status = 'Active' "
                "  AND a.deleted_at IS NULL AND c.start_date IS NOT NULL"
            ).fetchall()
            for r in crows:
                nxt = _next_anniversary(r["start_date"], today)
                if not nxt or not (today <= nxt[0] <= horizon):
                    continue
                if nxt[1] < 1:
                    continue
                full = f"{r['preferred_name'] or r['first_name']} " \
                         f"{r['last_name']}"
                out.append(Milestone(
                    alumni_id=r["alumni_id"], full_name=full,
                    kind="Work Anniversary",
                    when=nxt[0].isoformat(), years=nxt[1],
                    detail=f"{r['role']} @ {r['employer']}"))
    out.sort(key=lambda m: (m.when, m.full_name))
    return out


# ── #7 Lost-contact / find-a-friend queue ─────────────────────────

@dataclass
class LostContactCandidate:
    alumnus: Alumnus
    bounce_count: int
    has_email: bool
    has_phone: bool
    has_address: bool
    last_contacted: str | None


def lost_contact_queue(*,
                          bounce_threshold: int = HARD_BOUNCE_THRESHOLD,
                          require_no_phone: bool = True,
                          limit: int = 200
                          ) -> list[LostContactCandidate]:
    """Alumni who look unreachable:

    * email has hard-bounced at or beyond ``bounce_threshold`` *or*
      they have no email at all; AND
    * (default) they also have no phone number on file.

    Excludes opted-out, deceased, and already soft-deleted records."""
    init_db()
    out: list[LostContactCandidate] = []
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni "
            "WHERE deleted_at IS NULL "
            "  AND status NOT IN ('Deceased', 'Opt-out')"
        ).fetchall()
        for r in rows:
            a = _row(r)
            primary = conn.execute(
                "SELECT 1 FROM alumni_emails WHERE alumni_id = ? LIMIT 1",
                (a.alumni_id,)).fetchone()
            has_email = bool(a.email) or primary is not None
            phone_row = conn.execute(
                "SELECT 1 FROM alumni_phones WHERE alumni_id = ? LIMIT 1",
                (a.alumni_id,)).fetchone()
            has_phone = bool(a.phone) or phone_row is not None
            email_dead = (a.bounce_count >= bounce_threshold
                            or not has_email)
            if not email_dead:
                continue
            if require_no_phone and has_phone:
                continue
            out.append(LostContactCandidate(
                alumnus=a, bounce_count=a.bounce_count,
                has_email=has_email, has_phone=has_phone,
                has_address=bool(a.address),
                last_contacted=a.last_contacted))
    out.sort(key=lambda c: (c.last_contacted or "0000-00-00"))
    return out[:limit]


# ── #8 Public directory ──────────────────────────────────────────

@dataclass
class DirectoryEntry:
    alumni_id: int
    display_name: str
    leaving_year: str | None
    current_role: str | None
    current_employer: str | None
    current_sector: str | None
    country: str | None
    region: str | None
    linkedin: str | None
    bio: str | None


def opt_in_directory(alumni_id: int, *,
                       source: str | None = None,
                       notes: str | None = None,
                       actor: str | None = None) -> Consent:
    """Grants the 'Directory' consent scope. Idempotent — if an active
    consent already exists for the scope, the existing one is
    returned without recording a duplicate."""
    init_db()
    existing = [c for c in list_consents(alumni_id, active_only=True)
                  if c.scope == DIRECTORY_CONSENT_SCOPE]
    if existing:
        return existing[0]
    out = grant_consent(alumni_id, DIRECTORY_CONSENT_SCOPE,
                          source=source, notes=notes)
    _log_action("directory.opt_in", actor=actor, alumni_id=alumni_id)
    return out


def opt_out_directory(alumni_id: int, *,
                        actor: str | None = None,
                        notes: str | None = None) -> int:
    """Withdraws every active 'Directory' consent for ``alumni_id``.
    Returns the number of consent rows withdrawn (usually 0 or 1)."""
    init_db()
    active = [c for c in list_consents(alumni_id, active_only=True)
                if c.scope == DIRECTORY_CONSENT_SCOPE]
    for c in active:
        withdraw_consent(c.consent_id, notes=notes)
    if active:
        _log_action("directory.opt_out", actor=actor,
                      alumni_id=alumni_id, count=len(active))
    return len(active)


def is_in_directory(alumni_id: int) -> bool:
    return has_active_consent(alumni_id, DIRECTORY_CONSENT_SCOPE)


def list_public_directory(*,
                             leaving_year: str | None = None,
                             sector: str | None = None,
                             country: str | None = None,
                             region: str | None = None,
                             q: str | None = None,
                             limit: int = 500
                             ) -> list[DirectoryEntry]:
    """All Active alumni who hold an in-force 'Directory' consent,
    optionally filtered. Returns the redacted public projection — no
    DOB, email, phone, address, or original_student_id."""
    init_db()
    sql = ("""SELECT a.* FROM alumni a
               WHERE a.status = 'Active'
                 AND a.deleted_at IS NULL
                 AND EXISTS (
                   SELECT 1 FROM alumni_consent c
                    WHERE c.alumni_id = a.alumni_id
                      AND c.scope = ?
                      AND c.withdrawn_at IS NULL)""")
    params: list[Any] = [DIRECTORY_CONSENT_SCOPE]
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    if sector:
        sql += " AND a.current_sector = ?"
        params.append(sector)
    if country:
        sql += " AND a.country = ?"
        params.append(country)
    if region:
        sql += " AND a.region = ?"
        params.append(region)
    if q:
        like = f"%{q.strip()}%"
        sql += (" AND (a.first_name LIKE ? OR a.last_name LIKE ? "
                 "  OR a.preferred_name LIKE ? "
                 "  OR a.current_employer LIKE ? "
                 "  OR a.current_role LIKE ?)")
        params.extend([like, like, like, like, like])
    sql += (" ORDER BY a.leaving_year DESC NULLS LAST, "
             "          a.last_name ASC, a.first_name ASC LIMIT ?")
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    out: list[DirectoryEntry] = []
    for r in rows:
        a = _row(r)
        out.append(DirectoryEntry(
            alumni_id=a.alumni_id,
            display_name=a.display_name,
            leaving_year=a.leaving_year,
            current_role=a.current_role,
            current_employer=a.current_employer,
            current_sector=a.current_sector,
            country=a.country,
            region=a.region,
            linkedin=a.linkedin,
            bio=a.bio))
    return out


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .profile import (  # noqa: E402,F401
    _require_alumnus,
)
from .comms import (  # noqa: E402,F401
    _messages_module,
)
from .compliance import (  # noqa: E402,F401
    grant_consent,
    has_active_consent,
    list_consents,
    withdraw_consent,
)
