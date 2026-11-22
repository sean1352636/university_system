"""Sixth-form alumni — Career extensions (#9-#15): skills, SOC classification, salary bands, promotions, employers, jobs board, internships.

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    APPLICATION_STATUSES,
    Alumnus,
    INTERNSHIP_STATUSES,
    JOB_STATUSES,
    JOB_TYPES,
    PROFICIENCY_LEVELS,
    SALARY_BANDS,
    _log_action,
)
from .db import (
    ValidationError,
    _connect,
    _row,
    _validate_date,
    init_db,
)


# ── #9 Skills ─────────────────────────────────────────────────────

@dataclass
class Skill:
    skill_id: int
    name: str
    category: str | None


@dataclass
class AlumnusSkill:
    alumni_id: int
    skill_id: int
    skill_name: str
    proficiency: str
    years: float | None
    notes: str | None


def _row_skill(r: db.Row) -> Skill:
    return Skill(skill_id=r["skill_id"], name=r["name"],
                   category=r["category"])


def list_all_skills() -> list[Skill]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_skills ORDER BY name COLLATE NOCASE"
            ).fetchall()
    return [_row_skill(r) for r in rows]


def get_or_create_skill(name: str, *,
                          category: str | None = None) -> Skill:
    init_db()
    name = (name or "").strip()
    if not name:
        raise ValidationError("Skill name is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT * FROM alumni_skills WHERE name = ? COLLATE NOCASE",
            (name,)).fetchone()
        if r:
            return _row_skill(r)
        cur = conn.execute(
            "INSERT INTO alumni_skills (name, category) VALUES (?, ?)",
            (name, (category or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_skills WHERE skill_id = ?",
            (cur.lastrowid,)).fetchone()
    return _row_skill(r)


def add_skill_to_alumnus(alumni_id: int, name: str, *,
                            proficiency: str = "Intermediate",
                            years: float | None = None,
                            notes: str | None = None,
                            actor: str | None = None) -> AlumnusSkill:
    init_db()
    if proficiency not in PROFICIENCY_LEVELS:
        raise ValidationError(
            f"Proficiency must be one of: "
            f"{', '.join(PROFICIENCY_LEVELS)}")
    skill = get_or_create_skill(name)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_skill_links
                   (alumni_id, skill_id, proficiency, years, notes)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id, skill_id) DO UPDATE SET
                   proficiency = excluded.proficiency,
                   years       = excluded.years,
                   notes       = excluded.notes""",
            (alumni_id, skill.skill_id, proficiency, years,
             (notes or "").strip() or None))
        conn.commit()
    _log_action("skill.add", actor=actor, alumni_id=alumni_id,
                  skill=name, proficiency=proficiency)
    return AlumnusSkill(
        alumni_id=alumni_id, skill_id=skill.skill_id,
        skill_name=skill.name, proficiency=proficiency,
        years=years, notes=(notes or "").strip() or None)


def remove_skill_from_alumnus(alumni_id: int, skill_id: int, *,
                                actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_skill_links "
            "WHERE alumni_id = ? AND skill_id = ?",
            (alumni_id, skill_id))
        conn.commit()
    if cur.rowcount:
        _log_action("skill.remove", actor=actor,
                      alumni_id=alumni_id, skill_id=skill_id)
    return cur.rowcount > 0


def list_skills_for(alumni_id: int) -> list[AlumnusSkill]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT l.alumni_id, l.skill_id, s.name, l.proficiency,
                      l.years, l.notes
                 FROM alumni_skill_links l
                 JOIN alumni_skills s ON s.skill_id = l.skill_id
                WHERE l.alumni_id = ?
                ORDER BY s.name COLLATE NOCASE""",
            (alumni_id,)).fetchall()
    return [AlumnusSkill(
        alumni_id=r["alumni_id"], skill_id=r["skill_id"],
        skill_name=r["name"], proficiency=r["proficiency"],
        years=r["years"], notes=r["notes"]) for r in rows]


def find_alumni_by_skill(name: str, *,
                            min_proficiency: str | None = None
                            ) -> list[Alumnus]:
    init_db()
    levels = list(PROFICIENCY_LEVELS)
    accept: set[str] = set(levels)
    if min_proficiency:
        if min_proficiency not in levels:
            raise ValidationError(
                f"Proficiency must be one of: {', '.join(levels)}")
        idx = levels.index(min_proficiency)
        accept = set(levels[idx:])
    placeholders = ",".join("?" * len(accept))
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT a.* FROM alumni a
                  JOIN alumni_skill_links l ON l.alumni_id = a.alumni_id
                  JOIN alumni_skills s ON s.skill_id = l.skill_id
                 WHERE s.name = ? COLLATE NOCASE
                   AND l.proficiency IN ({placeholders})
                   AND a.deleted_at IS NULL
                 ORDER BY a.last_name, a.first_name""",
            (name, *accept)).fetchall()
    return [_row(r) for r in rows]


# ── #10 SOC/NAICS classification ─────────────────────────────────

# A tiny built-in dictionary of UK SOC 2020-style codes. The
# `soc_classify` lookup combines this with anything stored in
# `alumni_job_title_soc`. Patterns match case-insensitively as
# substrings of the job title.
_BUILTIN_SOC_PATTERNS: tuple[tuple[str, str, str, str | None], ...] = (
    # (pattern, soc_code, soc_label, naics_code)
    ("software engineer", "2136", "Programmers and software development", "5415"),
    ("software developer", "2136", "Programmers and software development", "5415"),
    ("data scientist",   "2425", "Actuaries, economists and statisticians", "5417"),
    ("data analyst",     "2425", "Actuaries, economists and statisticians", "5417"),
    ("teacher",          "2314", "Secondary education teaching", "6111"),
    ("nurse",            "2231", "Nurses", "6221"),
    ("doctor",           "2211", "Medical practitioners", "6211"),
    ("solicitor",        "2412", "Solicitors", "5411"),
    ("barrister",        "2411", "Barristers and judges", "5411"),
    ("accountant",       "2421", "Chartered and certified accountants", "5412"),
    ("civil engineer",   "2121", "Civil engineers", "5413"),
    ("mechanical engineer", "2122", "Mechanical engineers", "5413"),
    ("electrical engineer", "2123", "Electrical engineers", "5413"),
    ("marketing manager", "1132", "Marketing and sales directors", "5418"),
    ("product manager",   "1136", "Information technology managers", "5415"),
    ("designer",         "3421", "Graphic designers", "5414"),
    ("consultant",       "2423", "Management consultants and business analysts", "5416"),
    ("researcher",       "2150", "Research and development managers", "5417"),
    ("journalist",       "2471", "Journalists, newspaper and periodical editors", "5111"),
)


def upsert_soc_pattern(pattern: str, soc_code: str,
                          soc_label: str, *,
                          naics_code: str | None = None) -> None:
    init_db()
    pattern = (pattern or "").strip().lower()
    if not pattern:
        raise ValidationError("Pattern is required")
    if not (soc_code or "").strip():
        raise ValidationError("SOC code is required")
    if not (soc_label or "").strip():
        raise ValidationError("SOC label is required")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_job_title_soc
                   (pattern, soc_code, soc_label, naics_code)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(pattern) DO UPDATE SET
                   soc_code   = excluded.soc_code,
                   soc_label  = excluded.soc_label,
                   naics_code = excluded.naics_code""",
            (pattern, soc_code.strip(), soc_label.strip(),
             (naics_code or "").strip() or None))
        conn.commit()


def soc_classify(title: str | None
                    ) -> tuple[str, str, str | None] | None:
    """Return (soc_code, soc_label, naics_code) for the first matching
    pattern found in ``title``. Custom DB patterns override built-ins."""
    init_db()
    if not title:
        return None
    needle = title.lower()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT pattern, soc_code, soc_label, naics_code "
            "FROM alumni_job_title_soc").fetchall()
        for r in rows:
            if r["pattern"].lower() in needle:
                return (r["soc_code"], r["soc_label"], r["naics_code"])
    for pattern, code, label, naics in _BUILTIN_SOC_PATTERNS:
        if pattern in needle:
            return (code, label, naics)
    return None


def soc_breakdown(*, leaving_year: str | None = None
                     ) -> list[tuple[str, str, int]]:
    """Return (soc_code, soc_label, count) for current-job rows.
    Unclassified titles are returned under code ``'-'``."""
    init_db()
    sql = ("SELECT c.role FROM alumni_career c "
            "JOIN alumni a ON a.alumni_id = c.alumni_id "
            "WHERE c.is_current = 1 AND a.deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    counts: dict[tuple[str, str], int] = {}
    with _connect() as conn:
        for r in conn.execute(sql, params).fetchall():
            cls = soc_classify(r["role"])
            key = (cls[0], cls[1]) if cls else ("-", "Unclassified")
            counts[key] = counts.get(key, 0) + 1
    return sorted(
        [(code, label, n) for (code, label), n in counts.items()],
        key=lambda t: (-t[2], t[1]))


# ── #11 Salary-band analytics ────────────────────────────────────

@dataclass
class SalaryBandRow:
    band: str
    count: int
    pct: float


def salary_band_breakdown(*, leaving_year: str | None = None,
                              sector: str | None = None
                              ) -> list[SalaryBandRow]:
    """Distribution of salary bands across current career rows.

    The salary_band column is already optional/free-text-ish; rows
    with no band recorded are grouped under ``'Unknown'`` to make
    completeness visible to the user."""
    init_db()
    sql = ("SELECT COALESCE(NULLIF(TRIM(c.salary_band), ''), 'Unknown') "
            "       AS band, COUNT(*) AS n "
            "  FROM alumni_career c "
            "  JOIN alumni a ON a.alumni_id = c.alumni_id "
            " WHERE c.is_current = 1 AND a.deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    if sector:
        sql += " AND (c.sector = ? OR a.current_sector = ?)"
        params.extend([sector, sector])
    sql += " GROUP BY band"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    total = sum(int(r["n"]) for r in rows) or 1
    out = [SalaryBandRow(band=r["band"], count=int(r["n"]),
                              pct=100 * int(r["n"]) / total)
            for r in rows]
    # Sort by SALARY_BANDS canonical order; unknowns last.
    order = {b: i for i, b in enumerate(SALARY_BANDS)}
    out.sort(key=lambda r: order.get(r.band, 99))
    return out


def median_salary_band(*, leaving_year: str | None = None,
                          sector: str | None = None) -> str | None:
    """Pick the band where the running cumulative percentage first
    reaches 50% (with bands in SALARY_BANDS order). Returns ``None`` if
    no banded rows exist."""
    rows = [r for r in salary_band_breakdown(leaving_year=leaving_year,
                                                  sector=sector)
              if r.band != "Unknown"]
    total = sum(r.count for r in rows)
    if total == 0:
        return None
    cum = 0
    for r in rows:
        cum += r.count
        if cum / total >= 0.5:
            return r.band
    return rows[-1].band


# ── #12 Promotion timeline ───────────────────────────────────────

@dataclass
class PromotionStep:
    career_id: int
    start_date: str | None
    end_date: str | None
    role: str
    employer: str
    is_current: bool


def promotion_timeline(alumni_id: int) -> list[PromotionStep]:
    """Career rows sorted chronologically. The list is also a
    promotion sequence if the alumnus's roles escalate; consumers can
    inspect ``role`` adjacency to flag promotions vs lateral moves."""
    init_db()
    rows = list_career(alumni_id)
    rows.sort(key=lambda c: (c.start_date or "0000-00-00", c.career_id))
    return [PromotionStep(
        career_id=c.career_id, start_date=c.start_date,
        end_date=c.end_date, role=c.role, employer=c.employer,
        is_current=c.is_current) for c in rows]


# ── #13 Employer directory ───────────────────────────────────────

@dataclass
class Employer:
    employer_id: int
    canonical_name: str
    sector: str | None
    website: str | None
    country: str | None
    notes: str | None
    created_at: str


def _row_employer(r: db.Row) -> Employer:
    return Employer(
        employer_id=r["employer_id"],
        canonical_name=r["canonical_name"],
        sector=r["sector"], website=r["website"],
        country=r["country"], notes=r["notes"],
        created_at=r["created_at"])


def upsert_employer(canonical_name: str, *,
                       sector: str | None = None,
                       website: str | None = None,
                       country: str | None = None,
                       notes: str | None = None,
                       actor: str | None = None) -> Employer:
    init_db()
    canonical_name = (canonical_name or "").strip()
    if not canonical_name:
        raise ValidationError("Employer name is required")
    with _connect() as conn:
        existing = conn.execute(
            "SELECT * FROM alumni_employers "
            "WHERE canonical_name = ? COLLATE NOCASE",
            (canonical_name,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE alumni_employers
                      SET sector  = COALESCE(?, sector),
                          website = COALESCE(?, website),
                          country = COALESCE(?, country),
                          notes   = COALESCE(?, notes)
                    WHERE employer_id = ?""",
                ((sector or "").strip() or None,
                 (website or "").strip() or None,
                 (country or "").strip() or None,
                 (notes or "").strip() or None,
                 existing["employer_id"]))
            eid = existing["employer_id"]
        else:
            cur = conn.execute(
                """INSERT INTO alumni_employers
                       (canonical_name, sector, website, country, notes)
                   VALUES (?, ?, ?, ?, ?)""",
                (canonical_name,
                 (sector or "").strip() or None,
                 (website or "").strip() or None,
                 (country or "").strip() or None,
                 (notes or "").strip() or None))
            eid = cur.lastrowid
        conn.execute(
            "INSERT OR IGNORE INTO alumni_employer_aliases "
            "(alias, employer_id) VALUES (?, ?)",
            (canonical_name, eid))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_employers WHERE employer_id = ?",
            (eid,)).fetchone()
    _log_action("employer.upsert", actor=actor,
                  employer_id=eid, name=canonical_name)
    return _row_employer(r)


def add_employer_alias(alias: str, employer_id: int, *,
                          actor: str | None = None) -> None:
    init_db()
    alias = (alias or "").strip()
    if not alias:
        raise ValidationError("Alias is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT 1 FROM alumni_employers WHERE employer_id = ?",
            (employer_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No employer #{employer_id}")
        conn.execute(
            "INSERT OR REPLACE INTO alumni_employer_aliases "
            "(alias, employer_id) VALUES (?, ?)",
            (alias, employer_id))
        conn.commit()
    _log_action("employer.alias", actor=actor,
                  employer_id=employer_id, alias=alias)


def resolve_employer(name: str) -> Employer | None:
    """Resolve a free-text employer name via aliases. Returns ``None``
    if no canonical mapping exists yet."""
    init_db()
    if not name:
        return None
    with _connect() as conn:
        r = conn.execute(
            """SELECT e.* FROM alumni_employer_aliases al
                 JOIN alumni_employers e
                   ON e.employer_id = al.employer_id
                WHERE al.alias = ? COLLATE NOCASE""",
            ((name or "").strip(),)).fetchone()
    return _row_employer(r) if r else None


def list_employers() -> list[Employer]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_employers "
            "ORDER BY canonical_name COLLATE NOCASE").fetchall()
    return [_row_employer(r) for r in rows]


def delete_employer(employer_id: int, *,
                       actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_employers WHERE employer_id = ?",
            (employer_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("employer.delete", actor=actor,
                      employer_id=employer_id)
    return cur.rowcount > 0


@dataclass
class TopEmployerRow:
    employer: str
    alumni_count: int


def top_employers(*, limit: int = 25,
                     leaving_year: str | None = None
                     ) -> list[TopEmployerRow]:
    """Count alumni per employer using the normalised name where one
    exists, else the free-text ``current_employer``. Useful for
    'top 25 employers of our alumni' boards."""
    init_db()
    sql = ("""SELECT COALESCE(e.canonical_name, a.current_employer)
                       AS name,
                     COUNT(*) AS n
                FROM alumni a
                LEFT JOIN alumni_employer_aliases al
                       ON al.alias = a.current_employer COLLATE NOCASE
                LEFT JOIN alumni_employers e
                       ON e.employer_id = al.employer_id
               WHERE a.current_employer IS NOT NULL
                 AND TRIM(a.current_employer) <> ''
                 AND a.deleted_at IS NULL
                 AND a.status = 'Active'""")
    params: list[Any] = []
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    sql += " GROUP BY name ORDER BY n DESC, name COLLATE NOCASE LIMIT ?"
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [TopEmployerRow(employer=r["name"], alumni_count=int(r["n"]))
            for r in rows]


# ── #14 Job postings board ────────────────────────────────────────

@dataclass
class JobPosting:
    job_id: int
    alumni_id: int
    title: str
    employer: str | None
    sector: str | None
    location: str | None
    job_type: str
    salary_band: str | None
    description: str | None
    apply_url: str | None
    deadline: str | None
    status: str
    posted_at: str


@dataclass
class JobApplication:
    application_id: int
    job_id: int
    applicant_kind: str
    applicant_id: str
    applied_on: str
    status: str
    notes: str | None


def _row_job(r: db.Row) -> JobPosting:
    return JobPosting(
        job_id=r["job_id"], alumni_id=r["alumni_id"],
        title=r["title"], employer=r["employer"],
        sector=r["sector"], location=r["location"],
        job_type=r["job_type"], salary_band=r["salary_band"],
        description=r["description"], apply_url=r["apply_url"],
        deadline=r["deadline"], status=r["status"],
        posted_at=r["posted_at"])


def _row_job_app(r: db.Row) -> JobApplication:
    return JobApplication(
        application_id=r["application_id"], job_id=r["job_id"],
        applicant_kind=r["applicant_kind"],
        applicant_id=r["applicant_id"],
        applied_on=r["applied_on"], status=r["status"],
        notes=r["notes"])


def post_job(alumni_id: int, payload: dict[str, Any], *,
                actor: str | None = None) -> JobPosting:
    init_db()
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    job_type = payload.get("job_type") or "Graduate"
    if job_type not in JOB_TYPES:
        raise ValidationError(
            f"Job type must be one of: {', '.join(JOB_TYPES)}")
    salary_band = (payload.get("salary_band") or "").strip() or None
    if salary_band and salary_band not in SALARY_BANDS:
        raise ValidationError(
            f"Salary band must be one of: {', '.join(SALARY_BANDS)}")
    deadline = _validate_date(
        payload.get("deadline"), "Deadline", required=False)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_jobs
                   (alumni_id, title, employer, sector, location,
                    job_type, salary_band, description, apply_url,
                    deadline, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, title,
             (payload.get("employer") or "").strip() or None,
             (payload.get("sector") or "").strip() or None,
             (payload.get("location") or "").strip() or None,
             job_type, salary_band,
             (payload.get("description") or "").strip() or None,
             (payload.get("apply_url") or "").strip() or None,
             deadline,
             payload.get("status") or "Open"))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_jobs WHERE job_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("job.post", actor=actor, alumni_id=alumni_id,
                  title=title, job_id=r["job_id"])
    return _row_job(r)


def list_jobs(*, status: str | None = "Open",
                 alumni_id: int | None = None,
                 sector: str | None = None) -> list[JobPosting]:
    init_db()
    sql = "SELECT * FROM alumni_jobs WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if alumni_id is not None:
        sql += " AND alumni_id = ?"
        params.append(alumni_id)
    if sector:
        sql += " AND sector = ?"
        params.append(sector)
    sql += " ORDER BY posted_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_job(r) for r in rows]


def set_job_status(job_id: int, status: str, *,
                      actor: str | None = None) -> JobPosting:
    init_db()
    if status not in JOB_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(JOB_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_jobs SET status = ? WHERE job_id = ?",
            (status, job_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No job #{job_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_jobs WHERE job_id = ?",
            (job_id,)).fetchone()
    _log_action("job.status", actor=actor,
                  job_id=job_id, status=status)
    return _row_job(r)


def delete_job(job_id: int, *,
                  actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_jobs WHERE job_id = ?", (job_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("job.delete", actor=actor, job_id=job_id)
    return cur.rowcount > 0


def apply_to_job(job_id: int, *,
                    applicant_kind: str = "Alumnus",
                    applicant_id: str,
                    notes: str | None = None,
                    actor: str | None = None) -> JobApplication:
    init_db()
    if applicant_kind not in ("Alumnus", "Student", "External"):
        raise ValidationError(
            "Applicant kind must be Alumnus / Student / External")
    if not (applicant_id or "").strip():
        raise ValidationError("Applicant id is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT status FROM alumni_jobs WHERE job_id = ?",
            (job_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No job #{job_id}")
        if r["status"] != "Open":
            raise ValidationError(
                f"Job #{job_id} is {r['status']}, not Open")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_job_applications
                       (job_id, applicant_kind, applicant_id, notes)
                   VALUES (?, ?, ?, ?)""",
                (job_id, applicant_kind, applicant_id.strip(),
                 (notes or "").strip() or None))
        except db.IntegrityError as exc:
            raise ValidationError(
                "Already applied to this job") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_job_applications "
            "WHERE application_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("job.apply", actor=actor, job_id=job_id,
                  applicant_kind=applicant_kind,
                  applicant_id=applicant_id)
    return _row_job_app(row)


def list_job_applications(job_id: int) -> list[JobApplication]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_job_applications "
            "WHERE job_id = ? ORDER BY applied_on DESC, "
            "application_id DESC", (job_id,)).fetchall()
    return [_row_job_app(r) for r in rows]


def set_job_application_status(application_id: int, status: str, *,
                                  actor: str | None = None
                                  ) -> JobApplication:
    init_db()
    if status not in APPLICATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(APPLICATION_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_job_applications SET status = ? "
            "WHERE application_id = ?", (status, application_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No application #{application_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_job_applications "
            "WHERE application_id = ?",
            (application_id,)).fetchone()
    _log_action("job.app.status", actor=actor,
                  application_id=application_id, status=status)
    return _row_job_app(r)


# ── #15 Internships board (for current sixth-formers) ─────────────

@dataclass
class Internship:
    internship_id: int
    alumni_id: int
    title: str
    employer: str | None
    sector: str | None
    location: str | None
    duration_weeks: int | None
    paid: bool
    hourly_pence: int | None
    start_window: str | None
    requirements: str | None
    apply_url: str | None
    deadline: str | None
    status: str
    posted_at: str


@dataclass
class InternshipApplication:
    application_id: int
    internship_id: int
    student_id: str
    applied_on: str
    status: str
    notes: str | None


def _row_internship(r: db.Row) -> Internship:
    return Internship(
        internship_id=r["internship_id"], alumni_id=r["alumni_id"],
        title=r["title"], employer=r["employer"], sector=r["sector"],
        location=r["location"],
        duration_weeks=r["duration_weeks"],
        paid=bool(r["paid"]), hourly_pence=r["hourly_pence"],
        start_window=r["start_window"],
        requirements=r["requirements"], apply_url=r["apply_url"],
        deadline=r["deadline"], status=r["status"],
        posted_at=r["posted_at"])


def _row_internship_app(r: db.Row) -> InternshipApplication:
    return InternshipApplication(
        application_id=r["application_id"],
        internship_id=r["internship_id"],
        student_id=r["student_id"],
        applied_on=r["applied_on"], status=r["status"],
        notes=r["notes"])


def post_internship(alumni_id: int, payload: dict[str, Any], *,
                       actor: str | None = None) -> Internship:
    init_db()
    title = (payload.get("title") or "").strip()
    if not title:
        raise ValidationError("Title is required")
    duration = payload.get("duration_weeks")
    if duration is not None and duration != "":
        try:
            duration = int(duration)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Duration (weeks) must be an integer") from exc
        if duration < 1:
            raise ValidationError("Duration must be ≥ 1 week")
    else:
        duration = None
    paid = bool(payload.get("paid"))
    hourly_pence = _pounds_to_pence(
        payload.get("hourly_pay"), "Hourly pay",
        required=False) if "hourly_pay" in payload \
        else payload.get("hourly_pence")
    if hourly_pence is not None:
        try:
            hourly_pence = int(hourly_pence)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                "Hourly pay must be a number") from exc
    deadline = _validate_date(
        payload.get("deadline"), "Deadline", required=False)
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        cur = conn.execute(
            """INSERT INTO alumni_internships
                   (alumni_id, title, employer, sector, location,
                    duration_weeks, paid, hourly_pence, start_window,
                    requirements, apply_url, deadline, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (alumni_id, title,
             (payload.get("employer") or "").strip() or None,
             (payload.get("sector") or "").strip() or None,
             (payload.get("location") or "").strip() or None,
             duration, 1 if paid else 0, hourly_pence,
             (payload.get("start_window") or "").strip() or None,
             (payload.get("requirements") or "").strip() or None,
             (payload.get("apply_url") or "").strip() or None,
             deadline,
             payload.get("status") or "Open"))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_internships WHERE internship_id = ?",
            (cur.lastrowid,)).fetchone()
    _log_action("internship.post", actor=actor,
                  alumni_id=alumni_id, title=title,
                  internship_id=r["internship_id"])
    return _row_internship(r)


def list_internships(*, status: str | None = "Open",
                        alumni_id: int | None = None,
                        sector: str | None = None,
                        paid_only: bool = False
                        ) -> list[Internship]:
    init_db()
    sql = "SELECT * FROM alumni_internships WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    if alumni_id is not None:
        sql += " AND alumni_id = ?"
        params.append(alumni_id)
    if sector:
        sql += " AND sector = ?"
        params.append(sector)
    if paid_only:
        sql += " AND paid = 1"
    sql += " ORDER BY posted_at DESC"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_internship(r) for r in rows]


def set_internship_status(internship_id: int, status: str, *,
                             actor: str | None = None) -> Internship:
    init_db()
    if status not in INTERNSHIP_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(INTERNSHIP_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_internships SET status = ? "
            "WHERE internship_id = ?", (status, internship_id))
        if cur.rowcount == 0:
            raise ValidationError(f"No internship #{internship_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_internships WHERE internship_id = ?",
            (internship_id,)).fetchone()
    _log_action("internship.status", actor=actor,
                  internship_id=internship_id, status=status)
    return _row_internship(r)


def delete_internship(internship_id: int, *,
                         actor: str | None = None) -> bool:
    init_db()
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM alumni_internships WHERE internship_id = ?",
            (internship_id,))
        conn.commit()
    if cur.rowcount:
        _log_action("internship.delete", actor=actor,
                      internship_id=internship_id)
    return cur.rowcount > 0


def apply_to_internship(internship_id: int, student_id: str, *,
                           notes: str | None = None,
                           actor: str | None = None
                           ) -> InternshipApplication:
    init_db()
    if not (student_id or "").strip():
        raise ValidationError("Student id is required")
    with _connect() as conn:
        r = conn.execute(
            "SELECT status FROM alumni_internships "
            "WHERE internship_id = ?", (internship_id,)).fetchone()
        if r is None:
            raise ValidationError(f"No internship #{internship_id}")
        if r["status"] != "Open":
            raise ValidationError(
                f"Internship #{internship_id} is {r['status']}, "
                "not Open")
        try:
            cur = conn.execute(
                """INSERT INTO alumni_internship_applications
                       (internship_id, student_id, notes)
                   VALUES (?, ?, ?)""",
                (internship_id, student_id.strip(),
                 (notes or "").strip() or None))
        except db.IntegrityError as exc:
            raise ValidationError(
                "Already applied to this internship") from exc
        conn.commit()
        row = conn.execute(
            "SELECT * FROM alumni_internship_applications "
            "WHERE application_id = ?", (cur.lastrowid,)).fetchone()
    _log_action("internship.apply", actor=actor,
                  internship_id=internship_id, student_id=student_id)
    return _row_internship_app(row)


def list_internship_applications(internship_id: int
                                     ) -> list[InternshipApplication]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_internship_applications "
            "WHERE internship_id = ? "
            "ORDER BY applied_on DESC, application_id DESC",
            (internship_id,)).fetchall()
    return [_row_internship_app(r) for r in rows]


def set_internship_application_status(application_id: int, status: str,
                                          *, actor: str | None = None
                                          ) -> InternshipApplication:
    init_db()
    if status not in APPLICATION_STATUSES:
        raise ValidationError(
            f"Status must be one of: "
            f"{', '.join(APPLICATION_STATUSES)}")
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE alumni_internship_applications SET status = ? "
            "WHERE application_id = ?", (status, application_id))
        if cur.rowcount == 0:
            raise ValidationError(
                f"No internship application #{application_id}")
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_internship_applications "
            "WHERE application_id = ?",
            (application_id,)).fetchone()
    _log_action("internship.app.status", actor=actor,
                  application_id=application_id, status=status)
    return _row_internship_app(r)


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .profile import (  # noqa: E402,F401
    _require_alumnus,
    list_career,
)
from .linking import (  # noqa: E402,F401
    _pounds_to_pence,
)
