"""Sixth-form alumni — Mentorships, mentor matching, capacity, feedback and safeguarding checks (#16-#19).

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
    MENTORSHIP_STATUSES,
    SAFEGUARDING_STATUSES,
    SESSION_FORMATS,
    _log_action,
)
from .db import (
    ValidationError,
    _connect,
    _require,
    _row,
    _validate_date,
    init_db,
)


# ── Mentorships ──────────────────────────────────────────────────

@dataclass
class Mentorship:
    mentorship_id: int
    mentor_alumni_id: int
    mentee_student_id: str
    topic: str | None
    started_on: str
    ended_on: str | None
    status: str
    notes: str | None
    created_at: str


@dataclass
class MentorSession:
    session_id: int
    mentorship_id: int
    session_date: str
    duration_minutes: int | None
    format: str | None
    summary: str | None
    mentor_feedback: str | None
    mentee_feedback: str | None
    created_at: str


def _row_mentorship(r: db.Row) -> Mentorship:
    return Mentorship(
        mentorship_id=r["mentorship_id"],
        mentor_alumni_id=r["mentor_alumni_id"],
        mentee_student_id=r["mentee_student_id"],
        topic=r["topic"], started_on=r["started_on"],
        ended_on=r["ended_on"], status=r["status"],
        notes=r["notes"], created_at=r["created_at"],
    )


def _row_session(r: db.Row) -> MentorSession:
    return MentorSession(
        session_id=r["session_id"],
        mentorship_id=r["mentorship_id"],
        session_date=r["session_date"],
        duration_minutes=r["duration_minutes"],
        format=r["format"], summary=r["summary"],
        mentor_feedback=r["mentor_feedback"],
        mentee_feedback=r["mentee_feedback"],
        created_at=r["created_at"],
    )


def start_mentorship(mentor_alumni_id: int,
                      mentee_student_id: str,
                      *,
                      topic: str | None = None,
                      started_on: str | None = None,
                      notes: str | None = None) -> Mentorship:
    init_db()
    started = _validate_date(started_on or _dt.date.today().isoformat(),
                                "Start date", required=True)
    mentee = _require(mentee_student_id, "Mentee student id").strip()
    with _connect() as conn:
        _require_alumnus(conn, mentor_alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_mentorships
                   (mentor_alumni_id, mentee_student_id, topic,
                    started_on, status, notes)
               VALUES (?, ?, ?, ?, 'Active', ?)""",
            (mentor_alumni_id, mentee,
             (topic or "").strip() or None, started,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_mentorships WHERE mentorship_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_mentorship(r)


def list_mentorships_by_mentor(alumni_id: int
                                  ) -> list[Mentorship]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_mentorships "
            "WHERE mentor_alumni_id = ? "
            "ORDER BY status='Active' DESC, started_on DESC",
            (alumni_id,)).fetchall()
    return [_row_mentorship(r) for r in rows]


def list_mentorships_by_mentee(student_id: str
                                  ) -> list[Mentorship]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_mentorships "
            "WHERE mentee_student_id = ? "
            "ORDER BY started_on DESC",
            (student_id.strip(),)).fetchall()
    return [_row_mentorship(r) for r in rows]


def end_mentorship(mentorship_id: int, *,
                    ended_on: str | None = None,
                    status: str = "Completed",
                    notes: str | None = None) -> Mentorship:
    if status not in MENTORSHIP_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(MENTORSHIP_STATUSES)}")
    end = _validate_date(ended_on or _dt.date.today().isoformat(),
                           "End date", required=True)
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_mentorships SET ended_on = ?, status = ?, "
            "notes = COALESCE(?, notes) "
            "WHERE mentorship_id = ?",
            (end, status, notes, mentorship_id))
        conn.commit()
        if cur.rowcount == 0:
            raise ValidationError(
                f"No mentorship #{mentorship_id}")
        r = conn.execute(
            "SELECT * FROM alumni_mentorships WHERE mentorship_id = ?",
            (mentorship_id,)).fetchone()
    return _row_mentorship(r)


def delete_mentorship(mentorship_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_mentorships WHERE mentorship_id = ?",
            (mentorship_id,))
        conn.commit()
        return cur.rowcount > 0


def log_mentor_session(mentorship_id: int,
                         payload: dict[str, Any]) -> MentorSession:
    init_db()
    day = _validate_date(payload.get("session_date")
                            or _dt.date.today().isoformat(),
                          "Session date", required=True)
    fmt = (payload.get("format") or "").strip()
    if fmt and fmt not in SESSION_FORMATS:
        raise ValidationError(
            f"Format must be one of: {', '.join(SESSION_FORMATS)}")
    dur = payload.get("duration_minutes")
    if dur in (None, ""):
        dur = None
    else:
        try:
            dur = max(0, int(dur))
        except (TypeError, ValueError):
            raise ValidationError("Duration must be minutes (number)") \
                from None
    with _connect() as conn:
        r0 = conn.execute(
            "SELECT 1 FROM alumni_mentorships WHERE mentorship_id = ?",
            (mentorship_id,)).fetchone()
        if r0 is None:
            raise ValidationError(
                f"No mentorship #{mentorship_id}")
        cur = conn.execute(
            """INSERT INTO alumni_mentor_sessions
                   (mentorship_id, session_date, duration_minutes,
                    format, summary, mentor_feedback, mentee_feedback)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (mentorship_id, day, dur, fmt or None,
             (payload.get("summary") or "").strip() or None,
             (payload.get("mentor_feedback") or "").strip() or None,
             (payload.get("mentee_feedback") or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_mentor_sessions WHERE session_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_session(r)


def list_mentor_sessions(mentorship_id: int) -> list[MentorSession]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_mentor_sessions "
            "WHERE mentorship_id = ? "
            "ORDER BY session_date DESC, session_id DESC",
            (mentorship_id,)).fetchall()
    return [_row_session(r) for r in rows]


def delete_mentor_session(session_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_mentor_sessions WHERE session_id = ?",
            (session_id,))
        conn.commit()
        return cur.rowcount > 0


# ── #16 Mentor matching ──────────────────────────────────────────

@dataclass
class MentorMatch:
    alumnus: Alumnus
    score: float
    reasons: list[str]


_MATCH_WEIGHTS = {
    "subject_overlap":   10.0,  # per shared subject
    "sector_match":       8.0,
    "university_match":  12.0,
    "country_match":      3.0,
    "region_match":       3.0,
    "is_speaker":         2.0,
    "active_mentor":      4.0,  # already mentoring → proven engagement
    "has_consent":        2.0,
    "opt_in_contact":     3.0,
    "skill_match":        2.0,  # per matching skill
}


def _student_context(student_id: str) -> dict[str, Any]:
    """Best-effort lookup of a student's subjects, target university,
    aspirations, and skills. Resilient to schema drift in the
    students/careers/aspirations modules — anything we can't fetch
    falls back to an empty list/value."""
    out: dict[str, Any] = {
        "subjects": [], "target_university": None,
        "aspiration_sector": None, "skills": [],
        "country": None, "region": None,
    }
    try:
        from education_system.systems.sixth_form.domain.learners.students \
            import students as students_mod
        s = students_mod.get_student(student_id)
        if s:
            out["subjects"] = list(getattr(s, "subjects", []) or [])
    except Exception:
        pass
    asp = _career_aspiration_for(student_id)
    if asp:
        out["aspiration_sector"] = asp
    return out


def match_mentors_for_student(student_id: str, *,
                                  limit: int = 10,
                                  require_consent: bool = True
                                  ) -> list[MentorMatch]:
    """Rank Active alumni as mentor candidates for ``student_id``.

    Scoring is additive — see ``_MATCH_WEIGHTS``. Already-active
    mentorships score higher (proven engagement); alumni without
    ``Mentoring`` consent are dropped when ``require_consent`` is
    true."""
    init_db()
    ctx = _student_context(student_id)
    student_subjects = {s.lower() for s in ctx["subjects"]}
    aspiration = (ctx.get("aspiration_sector") or "").lower()

    with _connect() as conn:
        alumni_rows = conn.execute(
            "SELECT * FROM alumni "
            "WHERE status = 'Active' AND deleted_at IS NULL"
            ).fetchall()
        speakers = {r["alumni_id"] for r in conn.execute(
            "SELECT alumni_id FROM alumni_speakers").fetchall()}
        active_mentors = {r["mentor_alumni_id"] for r in conn.execute(
            "SELECT DISTINCT mentor_alumni_id FROM alumni_mentorships "
            "WHERE status = 'Active'").fetchall()}

    matches: list[MentorMatch] = []
    for r in alumni_rows:
        a = _row(r)
        reasons: list[str] = []
        score = 0.0
        # Subject overlap with mentor's education rows.
        mentor_subjects = {
            (e.subject or "").lower()
            for e in list_education(a.alumni_id)
            if e.subject}
        overlap = student_subjects & mentor_subjects
        if overlap:
            score += len(overlap) * _MATCH_WEIGHTS["subject_overlap"]
            reasons.append(
                f"shared subjects: {', '.join(sorted(overlap))}")
        # Sector / aspiration match.
        if aspiration:
            sector_val = (a.current_sector or "").lower()
            if sector_val and sector_val == aspiration:
                score += _MATCH_WEIGHTS["sector_match"]
                reasons.append(f"sector match ({a.current_sector})")
        # University match — any of the mentor's institutions matches
        # any of the student's destination-university values from
        # alumni_education? We use the educations attached to the
        # alumnus as the alumnus's universities.
        unis = {(e.institution or "").lower()
                  for e in list_education(a.alumni_id)
                  if e.institution}
        if unis and ctx.get("target_university") \
                and ctx["target_university"].lower() in unis:
            score += _MATCH_WEIGHTS["university_match"]
            reasons.append(
                f"university match ({ctx['target_university']})")
        # Country / region (rough proxy — students module may not
        # carry these, so this is best-effort).
        if a.country and ctx.get("country") \
                and a.country.lower() == ctx["country"].lower():
            score += _MATCH_WEIGHTS["country_match"]
            reasons.append(f"country ({a.country})")
        if a.region and ctx.get("region") \
                and a.region.lower() == ctx["region"].lower():
            score += _MATCH_WEIGHTS["region_match"]
            reasons.append(f"region ({a.region})")
        if a.alumni_id in speakers:
            score += _MATCH_WEIGHTS["is_speaker"]
            reasons.append("registered speaker")
        if a.alumni_id in active_mentors:
            score += _MATCH_WEIGHTS["active_mentor"]
            reasons.append("currently mentoring")
        if has_active_consent(a.alumni_id, "Mentoring"):
            score += _MATCH_WEIGHTS["has_consent"]
            reasons.append("mentoring consent")
        elif require_consent:
            continue
        if a.opt_in_contact:
            score += _MATCH_WEIGHTS["opt_in_contact"]
        # Skill match: any student skill that this mentor lists.
        if ctx.get("skills"):
            mentor_skill_names = {
                s.skill_name.lower()
                for s in list_skills_for(a.alumni_id)}
            shared = mentor_skill_names & {
                x.lower() for x in ctx["skills"]}
            if shared:
                score += len(shared) * _MATCH_WEIGHTS["skill_match"]
                reasons.append(
                    f"shared skills: {', '.join(sorted(shared))}")
        if score <= 0:
            continue
        matches.append(MentorMatch(
            alumnus=a, score=round(score, 2), reasons=reasons))
    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]


# ── #17 Mentor capacity & availability ───────────────────────────

@dataclass
class MentorProfile:
    alumni_id: int
    max_mentees: int
    available_from: str | None
    available_until: str | None
    paused: bool
    bio: str | None
    updated_at: str


def _row_mentor_profile(r: db.Row) -> MentorProfile:
    return MentorProfile(
        alumni_id=r["alumni_id"],
        max_mentees=int(r["max_mentees"]),
        available_from=r["available_from"],
        available_until=r["available_until"],
        paused=bool(r["paused"]),
        bio=r["bio"],
        updated_at=r["updated_at"])


def upsert_mentor_profile(alumni_id: int, *,
                              max_mentees: int = 3,
                              available_from: str | None = None,
                              available_until: str | None = None,
                              paused: bool = False,
                              bio: str | None = None,
                              actor: str | None = None
                              ) -> MentorProfile:
    init_db()
    if max_mentees < 0:
        raise ValidationError("max_mentees must be ≥ 0")
    avail_from = _validate_date(available_from, "Available from",
                                    required=False)
    avail_until = _validate_date(available_until, "Available until",
                                     required=False)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_mentor_profiles
                   (alumni_id, max_mentees, available_from,
                    available_until, paused, bio, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id) DO UPDATE SET
                   max_mentees     = excluded.max_mentees,
                   available_from  = excluded.available_from,
                   available_until = excluded.available_until,
                   paused          = excluded.paused,
                   bio             = excluded.bio,
                   updated_at      = excluded.updated_at""",
            (alumni_id, max_mentees, avail_from, avail_until,
             1 if paused else 0, (bio or "").strip() or None, now))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_mentor_profiles "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    _log_action("mentor.profile", actor=actor, alumni_id=alumni_id,
                  max_mentees=max_mentees, paused=paused)
    return _row_mentor_profile(r)


def get_mentor_profile(alumni_id: int) -> MentorProfile | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_mentor_profiles WHERE alumni_id = ?",
            (alumni_id,)).fetchone()
    return _row_mentor_profile(r) if r else None


def active_mentee_count(alumni_id: int) -> int:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT COUNT(*) FROM alumni_mentorships "
            "WHERE mentor_alumni_id = ? AND status = 'Active'",
            (alumni_id,)).fetchone()
    return int(r[0])


def mentor_has_capacity(alumni_id: int,
                          today: _dt.date | None = None) -> bool:
    """True when the mentor profile is not paused, within their
    availability window, and below ``max_mentees``."""
    init_db()
    p = get_mentor_profile(alumni_id)
    if p is None or p.paused:
        return False
    today = today or _dt.date.today()
    if p.available_from:
        try:
            if today < _dt.date.fromisoformat(p.available_from):
                return False
        except ValueError:
            pass
    if p.available_until:
        try:
            if today > _dt.date.fromisoformat(p.available_until):
                return False
        except ValueError:
            pass
    return active_mentee_count(alumni_id) < p.max_mentees


def list_available_mentors() -> list[MentorProfile]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_mentor_profiles "
            "WHERE paused = 0 ORDER BY alumni_id").fetchall()
    return [p for p in (_row_mentor_profile(r) for r in rows)
              if mentor_has_capacity(p.alumni_id)]


# ── #18 Mentor feedback / rating ─────────────────────────────────

def rate_mentor_session(session_id: int, *,
                          mentee_rating: int | None = None,
                          mentor_rating: int | None = None,
                          mentor_feedback: str | None = None,
                          mentee_feedback: str | None = None,
                          actor: str | None = None) -> None:
    """Record numeric ratings (1-5) and/or freeform feedback against a
    mentor session row. Either rating may be omitted."""
    init_db()
    for label, val in (("mentee_rating", mentee_rating),
                          ("mentor_rating", mentor_rating)):
        if val is not None and not (1 <= int(val) <= 5):
            raise ValidationError(f"{label} must be between 1 and 5")
    sets: list[str] = []
    vals: list[Any] = []
    if mentee_rating is not None:
        sets.append("mentee_rating = ?"); vals.append(int(mentee_rating))
    if mentor_rating is not None:
        sets.append("mentor_rating = ?"); vals.append(int(mentor_rating))
    if mentor_feedback is not None:
        sets.append("mentor_feedback = ?")
        vals.append((mentor_feedback or "").strip() or None)
    if mentee_feedback is not None:
        sets.append("mentee_feedback = ?")
        vals.append((mentee_feedback or "").strip() or None)
    if not sets:
        return
    vals.append(session_id)
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE alumni_mentor_sessions SET {', '.join(sets)} "
            f"WHERE session_id = ?", vals)
        if cur.rowcount == 0:
            raise ValidationError(f"No mentor session #{session_id}")
        conn.commit()
    _log_action("mentor.rate", actor=actor, session_id=session_id,
                  mentee_rating=mentee_rating,
                  mentor_rating=mentor_rating)


@dataclass
class MentorScorecard:
    alumni_id: int
    sessions: int
    avg_mentee_rating: float | None
    avg_mentor_rating: float | None


def mentor_scorecard(alumni_id: int) -> MentorScorecard:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            """SELECT COUNT(*) AS n,
                      AVG(mentee_rating) AS mr,
                      AVG(mentor_rating) AS gr
                 FROM alumni_mentor_sessions s
                 JOIN alumni_mentorships m
                   ON m.mentorship_id = s.mentorship_id
                WHERE m.mentor_alumni_id = ?""",
            (alumni_id,)).fetchone()
    return MentorScorecard(
        alumni_id=alumni_id, sessions=int(r["n"]),
        avg_mentee_rating=(round(float(r["mr"]), 2)
                              if r["mr"] is not None else None),
        avg_mentor_rating=(round(float(r["gr"]), 2)
                              if r["gr"] is not None else None))


# ── #19 Mentor safeguarding checks ───────────────────────────────

@dataclass
class MentorSafeguarding:
    alumni_id: int
    dbs_reference: str | None
    dbs_issued_on: str | None
    dbs_expires_on: str | None
    training_done_on: str | None
    training_expires_on: str | None
    status: str
    notes: str | None
    updated_at: str


def _row_safeguarding(r: db.Row) -> MentorSafeguarding:
    return MentorSafeguarding(
        alumni_id=r["alumni_id"],
        dbs_reference=r["dbs_reference"],
        dbs_issued_on=r["dbs_issued_on"],
        dbs_expires_on=r["dbs_expires_on"],
        training_done_on=r["training_done_on"],
        training_expires_on=r["training_expires_on"],
        status=r["status"], notes=r["notes"],
        updated_at=r["updated_at"])


def _derive_safeguarding_status(
        dbs_expires_on: str | None,
        training_expires_on: str | None,
        today: _dt.date | None = None) -> str:
    today = today or _dt.date.today()
    expiries: list[_dt.date] = []
    for s in (dbs_expires_on, training_expires_on):
        if not s:
            continue
        try:
            expiries.append(_dt.date.fromisoformat(s))
        except ValueError:
            continue
    if not expiries:
        return "Pending"
    if any(d < today for d in expiries):
        return "Expired"
    if any((d - today).days <= 60 for d in expiries):
        return "Expiring Soon"
    return "Cleared"


def upsert_mentor_safeguarding(alumni_id: int, *,
                                   dbs_reference: str | None = None,
                                   dbs_issued_on: str | None = None,
                                   dbs_expires_on: str | None = None,
                                   training_done_on: str | None = None,
                                   training_expires_on: str | None = None,
                                   status: str | None = None,
                                   notes: str | None = None,
                                   actor: str | None = None
                                   ) -> MentorSafeguarding:
    init_db()
    iso_dbs_iss = _validate_date(dbs_issued_on, "DBS issued",
                                     required=False)
    iso_dbs_exp = _validate_date(dbs_expires_on, "DBS expires",
                                     required=False)
    iso_tr_done = _validate_date(training_done_on, "Training done",
                                     required=False)
    iso_tr_exp = _validate_date(training_expires_on,
                                    "Training expires",
                                    required=False)
    if status and status not in SAFEGUARDING_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(SAFEGUARDING_STATUSES)}")
    derived = status or _derive_safeguarding_status(
        iso_dbs_exp, iso_tr_exp)
    now = _dt.datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_mentor_safeguarding
                   (alumni_id, dbs_reference, dbs_issued_on,
                    dbs_expires_on, training_done_on,
                    training_expires_on, status, notes, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id) DO UPDATE SET
                   dbs_reference       = excluded.dbs_reference,
                   dbs_issued_on       = excluded.dbs_issued_on,
                   dbs_expires_on      = excluded.dbs_expires_on,
                   training_done_on    = excluded.training_done_on,
                   training_expires_on = excluded.training_expires_on,
                   status              = excluded.status,
                   notes               = excluded.notes,
                   updated_at          = excluded.updated_at""",
            (alumni_id,
             (dbs_reference or "").strip() or None,
             iso_dbs_iss, iso_dbs_exp,
             iso_tr_done, iso_tr_exp, derived,
             (notes or "").strip() or None, now))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_mentor_safeguarding "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    _log_action("mentor.safeguarding", actor=actor,
                  alumni_id=alumni_id, status=derived)
    return _row_safeguarding(r)


def get_mentor_safeguarding(alumni_id: int
                                ) -> MentorSafeguarding | None:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_mentor_safeguarding "
            "WHERE alumni_id = ?", (alumni_id,)).fetchone()
    return _row_safeguarding(r) if r else None


def list_safeguarding_alerts(*, days: int = 60
                                  ) -> list[MentorSafeguarding]:
    """Anyone whose DBS or training expires within ``days`` days, or
    is already expired."""
    init_db()
    today = _dt.date.today()
    horizon = today + _dt.timedelta(days=days)
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM alumni_mentor_safeguarding
                WHERE (dbs_expires_on IS NOT NULL
                          AND dbs_expires_on <= ?)
                   OR (training_expires_on IS NOT NULL
                          AND training_expires_on <= ?)""",
            (horizon.isoformat(), horizon.isoformat())).fetchall()
    out = [_row_safeguarding(r) for r in rows]
    for s in out:
        # Recompute live status so list reflects 'today', not stored.
        s.status = _derive_safeguarding_status(
            s.dbs_expires_on, s.training_expires_on, today=today)
    out.sort(key=lambda s: (s.dbs_expires_on or s.training_expires_on
                              or "9999-99-99"))
    return out


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .profile import (  # noqa: E402,F401
    _require_alumnus,
    list_education,
)
from .compliance import (  # noqa: E402,F401
    has_active_consent,
)
from .linking import (  # noqa: E402,F401
    _career_aspiration_for,
)
from .careers import (  # noqa: E402,F401
    list_skills_for,
)
