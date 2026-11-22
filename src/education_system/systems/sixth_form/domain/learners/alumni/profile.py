"""Sixth-form alumni — Education history, career history, emails/phones, tags and achievements.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    ACHIEVEMENT_CATEGORIES,
    Achievement,
    AlumniEmail,
    AlumniPhone,
    Alumnus,
    Career,
    DEFAULT_EDUCATION_STATUS,
    EDUCATION_STATUSES,
    EMAIL_LABELS,
    Education,
    PHONE_LABELS,
    SALARY_BANDS,
    SECTORS,
    Tag,
)
from .db import (
    ValidationError,
    _connect,
    _require,
    _row,
    _validate_date,
    _validate_email,
    _validate_phone,
    init_db,
)


# ── Education history ─────────────────────────────────────────────

def _require_alumnus(conn: db.Connection, alumni_id: int) -> None:
    r = conn.execute(
        "SELECT 1 FROM alumni WHERE alumni_id = ?", (alumni_id,)
    ).fetchone()
    if r is None:
        raise ValidationError(f"No alumnus #{alumni_id}")


def _row_education(r: db.Row) -> Education:
    return Education(
        education_id=r["education_id"], alumni_id=r["alumni_id"],
        qualification=r["qualification"], subject=r["subject"],
        institution=r["institution"],
        start_date=r["start_date"], end_date=r["end_date"],
        grade=r["grade"], status=r["status"], notes=r["notes"],
        created_at=r["created_at"],
    )


def add_education(alumni_id: int, payload: dict[str, Any]) -> Education:
    init_db()
    qual   = _require(payload.get("qualification"), "Qualification").strip()
    inst   = _require(payload.get("institution"),   "Institution").strip()
    status = (payload.get("status") or DEFAULT_EDUCATION_STATUS).strip()
    if status not in EDUCATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(EDUCATION_STATUSES)}")
    start = _validate_date(payload.get("start_date"), "Start date")
    end   = _validate_date(payload.get("end_date"),   "End date")
    subject = (payload.get("subject") or "").strip() or None
    grade   = (payload.get("grade")   or "").strip() or None
    notes   = (payload.get("notes")   or "").strip() or None
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_education
                   (alumni_id, qualification, subject, institution,
                    start_date, end_date, grade, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, qual, subject, inst, start, end,
             grade, status, notes),
        )
        conn.commit()
        new_id = cur.lastrowid
        r = conn.execute(
            "SELECT * FROM alumni_education WHERE education_id = ?",
            (new_id,)).fetchone()
    return _row_education(r)


def list_education(alumni_id: int) -> list[Education]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_education WHERE alumni_id = ? "
            "ORDER BY COALESCE(end_date, start_date, '') DESC, "
            "education_id DESC",
            (alumni_id,)).fetchall()
    return [_row_education(r) for r in rows]


def update_education(education_id: int,
                      payload: dict[str, Any]) -> Education:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_education WHERE education_id = ?",
            (education_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No education row #{education_id}")
    merged = {
        "qualification": payload.get("qualification", r["qualification"]),
        "subject":       payload.get("subject",       r["subject"]),
        "institution":   payload.get("institution",   r["institution"]),
        "start_date":    payload.get("start_date",    r["start_date"]),
        "end_date":      payload.get("end_date",      r["end_date"]),
        "grade":         payload.get("grade",         r["grade"]),
        "status":        payload.get("status",        r["status"]),
        "notes":         payload.get("notes",         r["notes"]),
    }
    qual   = _require(merged["qualification"], "Qualification").strip()
    inst   = _require(merged["institution"],   "Institution").strip()
    status = (merged["status"] or DEFAULT_EDUCATION_STATUS).strip()
    if status not in EDUCATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(EDUCATION_STATUSES)}")
    start = _validate_date(merged["start_date"], "Start date")
    end   = _validate_date(merged["end_date"],   "End date")
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni_education SET
                   qualification = ?, subject = ?, institution = ?,
                   start_date = ?, end_date = ?, grade = ?,
                   status = ?, notes = ?
               WHERE education_id = ?""",
            (qual, (merged["subject"] or "").strip() or None,
             inst, start, end,
             (merged["grade"] or "").strip() or None, status,
             (merged["notes"] or "").strip() or None, education_id),
        )
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_education WHERE education_id = ?",
            (education_id,)).fetchone()
    return _row_education(r2)


def delete_education(education_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_education WHERE education_id = ?",
            (education_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Career history ────────────────────────────────────────────────

def _row_career(r: db.Row) -> Career:
    return Career(
        career_id=r["career_id"], alumni_id=r["alumni_id"],
        role=r["role"], employer=r["employer"], sector=r["sector"],
        country=r["country"], location=r["location"],
        start_date=r["start_date"], end_date=r["end_date"],
        is_current=bool(r["is_current"]),
        salary_band=r["salary_band"], notes=r["notes"],
        created_at=r["created_at"],
    )


def _validate_career_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    out["role"]     = _require(payload.get("role"),     "Role").strip()
    out["employer"] = _require(payload.get("employer"), "Employer").strip()
    sector = (payload.get("sector") or "").strip()
    if sector and sector not in SECTORS:
        raise ValidationError(
            f"Sector must be one of: {', '.join(SECTORS)}")
    out["sector"]      = sector or None
    out["country"]     = (payload.get("country")  or "").strip() or None
    out["location"]    = (payload.get("location") or "").strip() or None
    out["start_date"]  = _validate_date(payload.get("start_date"),
                                          "Start date")
    out["end_date"]    = _validate_date(payload.get("end_date"),
                                          "End date")
    out["is_current"]  = bool(payload.get("is_current"))
    band = (payload.get("salary_band") or "").strip()
    if band and band not in SALARY_BANDS:
        raise ValidationError(
            f"Salary band must be one of: {', '.join(SALARY_BANDS)}")
    out["salary_band"] = band or None
    out["notes"]       = (payload.get("notes") or "").strip() or None
    return out


def add_career(alumni_id: int, payload: dict[str, Any]) -> Career:
    init_db()
    p = _validate_career_payload(payload)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if p["is_current"]:
            conn.execute(
                "UPDATE alumni_career SET is_current = 0 "
                "WHERE alumni_id = ?", (alumni_id,))
        cur = conn.execute(
            """INSERT INTO alumni_career
                   (alumni_id, role, employer, sector, country, location,
                    start_date, end_date, is_current, salary_band, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, p["role"], p["employer"], p["sector"],
             p["country"], p["location"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["salary_band"], p["notes"]),
        )
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_career WHERE career_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_career(r)


def list_career(alumni_id: int) -> list[Career]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_career WHERE alumni_id = ? "
            "ORDER BY is_current DESC, "
            "COALESCE(end_date, start_date, '') DESC, career_id DESC",
            (alumni_id,)).fetchall()
    return [_row_career(r) for r in rows]


def update_career(career_id: int, payload: dict[str, Any]) -> Career:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_career WHERE career_id = ?",
            (career_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No career row #{career_id}")
    merged = {
        "role":        payload.get("role",        r["role"]),
        "employer":    payload.get("employer",    r["employer"]),
        "sector":      payload.get("sector",      r["sector"]),
        "country":     payload.get("country",     r["country"]),
        "location":    payload.get("location",    r["location"]),
        "start_date":  payload.get("start_date",  r["start_date"]),
        "end_date":    payload.get("end_date",    r["end_date"]),
        "is_current":  payload.get("is_current",  bool(r["is_current"])),
        "salary_band": payload.get("salary_band", r["salary_band"]),
        "notes":       payload.get("notes",       r["notes"]),
    }
    p = _validate_career_payload(merged)
    with _connect() as conn:
        if p["is_current"]:
            conn.execute(
                "UPDATE alumni_career SET is_current = 0 "
                "WHERE alumni_id = ? AND career_id != ?",
                (r["alumni_id"], career_id))
        conn.execute(
            """UPDATE alumni_career SET
                   role = ?, employer = ?, sector = ?, country = ?,
                   location = ?, start_date = ?, end_date = ?,
                   is_current = ?, salary_band = ?, notes = ?
               WHERE career_id = ?""",
            (p["role"], p["employer"], p["sector"], p["country"],
             p["location"], p["start_date"], p["end_date"],
             1 if p["is_current"] else 0, p["salary_band"],
             p["notes"], career_id),
        )
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_career WHERE career_id = ?",
            (career_id,)).fetchone()
    return _row_career(r2)


def delete_career(career_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_career WHERE career_id = ?",
            (career_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Emails / phones ───────────────────────────────────────────────

def _row_email(r: db.Row) -> AlumniEmail:
    return AlumniEmail(
        email_id=r["email_id"], alumni_id=r["alumni_id"],
        email=r["email"], label=r["label"],
        is_primary=bool(r["is_primary"]),
    )


def _row_phone(r: db.Row) -> AlumniPhone:
    return AlumniPhone(
        phone_id=r["phone_id"], alumni_id=r["alumni_id"],
        phone=r["phone"], label=r["label"],
        is_primary=bool(r["is_primary"]),
    )


def add_email(alumni_id: int, email: str, *,
              label: str = "Personal",
              is_primary: bool = False) -> AlumniEmail:
    init_db()
    addr = _validate_email(email)
    if not addr:
        raise ValidationError("Email is required")
    if label not in EMAIL_LABELS:
        raise ValidationError(
            f"Label must be one of: {', '.join(EMAIL_LABELS)}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if is_primary:
            conn.execute(
                "UPDATE alumni_emails SET is_primary = 0 "
                "WHERE alumni_id = ?", (alumni_id,))
        cur = conn.execute(
            "INSERT INTO alumni_emails "
            "(alumni_id, email, label, is_primary) VALUES (?, ?, ?, ?)",
            (alumni_id, addr, label, 1 if is_primary else 0))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_emails WHERE email_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_email(r)


def list_emails(alumni_id: int) -> list[AlumniEmail]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_emails WHERE alumni_id = ? "
            "ORDER BY is_primary DESC, email_id ASC",
            (alumni_id,)).fetchall()
    return [_row_email(r) for r in rows]


def set_primary_email(email_id: int) -> AlumniEmail:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_emails WHERE email_id = ?",
            (email_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No email row #{email_id}")
        conn.execute(
            "UPDATE alumni_emails SET is_primary = 0 "
            "WHERE alumni_id = ?", (r["alumni_id"],))
        conn.execute(
            "UPDATE alumni_emails SET is_primary = 1 WHERE email_id = ?",
            (email_id,))
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_emails WHERE email_id = ?",
            (email_id,)).fetchone()
    return _row_email(r2)


def delete_email(email_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_emails WHERE email_id = ?", (email_id,))
        conn.commit()
        return cur.rowcount > 0


def add_phone(alumni_id: int, phone: str, *,
              label: str = "Mobile",
              is_primary: bool = False) -> AlumniPhone:
    init_db()
    num = _validate_phone(phone)
    if not num:
        raise ValidationError("Phone is required")
    if label not in PHONE_LABELS:
        raise ValidationError(
            f"Label must be one of: {', '.join(PHONE_LABELS)}")
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        if is_primary:
            conn.execute(
                "UPDATE alumni_phones SET is_primary = 0 "
                "WHERE alumni_id = ?", (alumni_id,))
        cur = conn.execute(
            "INSERT INTO alumni_phones "
            "(alumni_id, phone, label, is_primary) VALUES (?, ?, ?, ?)",
            (alumni_id, num, label, 1 if is_primary else 0))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_phones WHERE phone_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_phone(r)


def list_phones(alumni_id: int) -> list[AlumniPhone]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_phones WHERE alumni_id = ? "
            "ORDER BY is_primary DESC, phone_id ASC",
            (alumni_id,)).fetchall()
    return [_row_phone(r) for r in rows]


def set_primary_phone(phone_id: int) -> AlumniPhone:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_phones WHERE phone_id = ?",
            (phone_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No phone row #{phone_id}")
        conn.execute(
            "UPDATE alumni_phones SET is_primary = 0 "
            "WHERE alumni_id = ?", (r["alumni_id"],))
        conn.execute(
            "UPDATE alumni_phones SET is_primary = 1 WHERE phone_id = ?",
            (phone_id,))
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_phones WHERE phone_id = ?",
            (phone_id,)).fetchone()
    return _row_phone(r2)


def delete_phone(phone_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_phones WHERE phone_id = ?", (phone_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Tags ──────────────────────────────────────────────────────────

def _row_tag(r: db.Row) -> Tag:
    return Tag(tag_id=r["tag_id"], name=r["name"])


def list_all_tags() -> list[Tag]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_tags ORDER BY name COLLATE NOCASE"
        ).fetchall()
    return [_row_tag(r) for r in rows]


def get_or_create_tag(name: str) -> Tag:
    init_db()
    nm = _require(name, "Tag name").strip()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_tags WHERE name = ? COLLATE NOCASE",
            (nm,)).fetchone()
        if r:
            return _row_tag(r)
        cur = conn.execute(
            "INSERT INTO alumni_tags (name) VALUES (?)", (nm,))
        conn.commit()
        return Tag(tag_id=cur.lastrowid, name=nm)


def list_tags_for(alumni_id: int) -> list[Tag]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT t.* FROM alumni_tags t "
            "JOIN alumni_tag_links l ON l.tag_id = t.tag_id "
            "WHERE l.alumni_id = ? "
            "ORDER BY t.name COLLATE NOCASE",
            (alumni_id,)).fetchall()
    return [_row_tag(r) for r in rows]


def list_alumni_for_tag(tag_id: int) -> list[Alumnus]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT a.* FROM alumni a "
            "JOIN alumni_tag_links l ON l.alumni_id = a.alumni_id "
            "WHERE l.tag_id = ? "
            "ORDER BY a.last_name ASC, a.first_name ASC",
            (tag_id,)).fetchall()
    return [_row(r) for r in rows]


def add_tag(alumni_id: int, name: str) -> Tag:
    init_db()
    tag = get_or_create_tag(name)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            "INSERT OR IGNORE INTO alumni_tag_links "
            "(alumni_id, tag_id) VALUES (?, ?)",
            (alumni_id, tag.tag_id))
        conn.commit()
    return tag


def remove_tag(alumni_id: int, tag_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_tag_links "
            "WHERE alumni_id = ? AND tag_id = ?",
            (alumni_id, tag_id))
        conn.commit()
        return cur.rowcount > 0


def delete_tag(tag_id: int) -> bool:
    """Delete a tag globally (and all its links)."""
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_tags WHERE tag_id = ?", (tag_id,))
        conn.commit()
        return cur.rowcount > 0


# ── Achievements ──────────────────────────────────────────────────

def _row_achievement(r: db.Row) -> Achievement:
    return Achievement(
        achievement_id=r["achievement_id"], alumni_id=r["alumni_id"],
        date=r["date"], title=r["title"], category=r["category"],
        description=r["description"], url=r["url"],
        created_at=r["created_at"],
    )


def add_achievement(alumni_id: int,
                     payload: dict[str, Any]) -> Achievement:
    init_db()
    title    = _require(payload.get("title"), "Title").strip()
    date     = _validate_date(payload.get("date"), "Date")
    category = (payload.get("category") or "").strip()
    if category and category not in ACHIEVEMENT_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: "
            f"{', '.join(ACHIEVEMENT_CATEGORIES)}")
    desc = (payload.get("description") or "").strip() or None
    url  = (payload.get("url") or "").strip() or None
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_achievements
                   (alumni_id, date, title, category, description, url)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (alumni_id, date, title, category or None, desc, url))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_achievements "
            "WHERE achievement_id = ?", (cur.lastrowid,)).fetchone()
    return _row_achievement(r)


def list_achievements(alumni_id: int) -> list[Achievement]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_achievements WHERE alumni_id = ? "
            "ORDER BY COALESCE(date, '') DESC, achievement_id DESC",
            (alumni_id,)).fetchall()
    return [_row_achievement(r) for r in rows]


def update_achievement(achievement_id: int,
                        payload: dict[str, Any]) -> Achievement:
    init_db()
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_achievements "
            "WHERE achievement_id = ?", (achievement_id,)).fetchone()
        if r is None:
            raise ValidationError(
                f"No achievement #{achievement_id}")
    merged = {
        "date":        payload.get("date",        r["date"]),
        "title":       payload.get("title",       r["title"]),
        "category":    payload.get("category",    r["category"]),
        "description": payload.get("description", r["description"]),
        "url":         payload.get("url",         r["url"]),
    }
    title    = _require(merged["title"], "Title").strip()
    date     = _validate_date(merged["date"], "Date")
    category = (merged["category"] or "").strip()
    if category and category not in ACHIEVEMENT_CATEGORIES:
        raise ValidationError(
            f"Category must be one of: "
            f"{', '.join(ACHIEVEMENT_CATEGORIES)}")
    with _connect() as conn:
        conn.execute(
            """UPDATE alumni_achievements SET
                   date = ?, title = ?, category = ?,
                   description = ?, url = ?
               WHERE achievement_id = ?""",
            (date, title, category or None,
             (merged["description"] or "").strip() or None,
             (merged["url"] or "").strip() or None,
             achievement_id))
        conn.commit()
        r2 = conn.execute(
            "SELECT * FROM alumni_achievements "
            "WHERE achievement_id = ?", (achievement_id,)).fetchone()
    return _row_achievement(r2)


def delete_achievement(achievement_id: int) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_achievements WHERE achievement_id = ?",
            (achievement_id,))
        conn.commit()
        return cur.rowcount > 0
