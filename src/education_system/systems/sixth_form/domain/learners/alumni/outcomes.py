"""Sixth-form alumni — Destination reports (#33-#41 HTML), outcomes extensions (#37-#40), HESA benchmarks and DfE export (#42-#43).

Split out of :mod:`education_system.systems.sixth_form.domain.learners.alumni.alumni`, which re-exports
every name; import from there.
"""

from __future__ import annotations

import csv as _csv
import datetime as _dt
import html as _html
import io as _io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from education_system.systems.sixth_form.infrastructure import database as db

from .models import (
    Alumnus,
    DESTINATION_TYPES,
    NEET_STATUSES,
    OXBRIDGE_UNIVERSITIES,
    PG_QUALIFICATIONS,
    RUSSELL_GROUP_UNIVERSITIES,
    _YEAR_RE,
    _log_action,
)
from .db import (
    IntegrationError,
    ValidationError,
    _connect,
    _opt,
    _row,
    _validate_date,
    init_db,
)


# ══ Reporting & analytics ════════════════════════════════════════
#
# These functions are read-only and produce structured data the CLI
# and GUI can render or export. Where DfE / cohort definitions are
# concerned the constants below are the school's best-effort lookup
# table — adjust them in this module to match the spec for a given
# return year.




RUSSELL_GROUP: tuple[str, ...] = (
    "University of Birmingham", "University of Bristol",
    "University of Cambridge", "Cardiff University",
    "Durham University", "University of Edinburgh",
    "University of Exeter", "University of Glasgow",
    "Imperial College London", "King's College London",
    "University of Leeds", "University of Liverpool",
    "London School of Economics", "University of Manchester",
    "Newcastle University", "University of Nottingham",
    "University of Oxford", "Queen Mary University of London",
    "Queen's University Belfast", "University of Sheffield",
    "University of Southampton", "University College London",
    "University of Warwick", "University of York",
)

OXBRIDGE: tuple[str, ...] = (
    "University of Oxford", "University of Cambridge",
)

# Pragmatic stand-in for the top third of UK HE providers by entry
# tariff. The HESA tariff bands change yearly; treat this list as a
# starting point and override in the constant for accurate stats.
TOP_THIRD_UNIVERSITIES: tuple[str, ...] = RUSSELL_GROUP + (
    "University of St Andrews", "University of Bath",
    "Lancaster University", "Loughborough University",
    "University of Sussex", "University of Reading",
    "University of Surrey",
)

# Map our destination_type to the DfE 16-18 destination category
# scheme (illustrative — confirm wording against the current
# specification before submission).
DFE_DESTINATION_CATEGORIES: dict[str, str] = {
    "University":     "Higher Education",
    "Apprenticeship": "Apprenticeship",
    "Further Study":  "Further Education",
    "Employment":     "Employment",
    "Self-Employed":  "Employment",
    "Gap Year":       "Other (incl gap year)",
    "Volunteering":   "Other (incl gap year)",
    "Unknown":        "Not known / unable to confirm",
    "Other":          "Other (incl gap year)",
}


def _contains_any(haystack: str | None,
                    needles: tuple[str, ...]) -> bool:
    if not haystack:
        return False
    s = haystack.lower()
    return any(n.lower() in s for n in needles)


# ── #33 KS5 destinations (DfE-style) ─────────────────────────────

def ks5_destinations_rows(*, leaving_year: str
                              ) -> list[dict[str, Any]]:
    """One row per alumnus for the given cohort. Columns map (best
    effort) to the DfE 16-18 destinations return. The shape is
    explicit (a list of dicts) so callers can write CSV / Excel /
    upload as they prefer."""
    init_db()
    if not _YEAR_RE.match(leaving_year):
        raise ValidationError(
            "Leaving year must be a 4-digit year (e.g. 2024)")
    rows = list_alumni(leaving_year=leaving_year)
    out: list[dict[str, Any]] = []
    for a in rows:
        category = DFE_DESTINATION_CATEGORIES.get(
            a.destination_type, "Not known / unable to confirm")
        out.append({
            "uln":                 a.original_student_id or "",
            "surname":             a.last_name,
            "forename":            a.first_name,
            "preferred_name":      a.preferred_name or "",
            "dob":                 a.dob or "",
            "gender":              a.gender or "",
            "leaving_year":        a.leaving_year or "",
            "leaving_date":        a.leaving_date or "",
            "destination_category": category,
            "destination_type":    a.destination_type,
            "destination_detail":  a.destination_detail or "",
            "country":             a.country or "",
            "region":              a.region or "",
            "consented_to_contact": "Y" if a.opt_in_contact else "N",
        })
    return out


def ks5_destinations_csv(*, leaving_year: str,
                           out_path: str | None = None) -> str:
    """Render the KS5 destinations rows as CSV. If ``out_path`` is
    given the file is written and the path returned; otherwise the
    CSV is returned as a string."""
    rows = ks5_destinations_rows(leaving_year=leaving_year)
    headers = list(rows[0].keys()) if rows else [
        "uln", "surname", "forename", "dob", "gender",
        "leaving_year", "destination_category",
        "destination_type", "destination_detail",
        "country", "region", "consented_to_contact",
    ]
    buf = _io.StringIO()
    w = _csv.DictWriter(buf, fieldnames=headers,
                          extrasaction="ignore",
                          quoting=_csv.QUOTE_MINIMAL)
    w.writeheader()
    for r in rows:
        w.writerow(r)
    _log_action("report.ks5_destinations_csv",
                  leaving_year=leaving_year, rows=len(rows),
                  out_path=str(out_path) if out_path else "(stdout)")
    if out_path:
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            f.write(buf.getvalue())
        return out_path
    return buf.getvalue()


# ── #34 Sustained destinations (1 / 3 / 5 years post-leaving) ────

@dataclass
class SustainedRow:
    alumni_id: int
    full_name: str
    leaving_year: str
    year_plus_1: str
    year_plus_3: str
    year_plus_5: str


def _activity_at(alumni_id: int, when: str) -> str:
    """Classify what the alumnus was doing at a particular date.
    Returns one of: 'In HE/FE', 'Employed', 'Mixed', 'Not known'."""
    init_db()
    with _connect() as conn:
        edu = conn.execute(
            "SELECT start_date, end_date, status "
            "FROM alumni_education WHERE alumni_id = ?",
            (alumni_id,)).fetchall()
        car = conn.execute(
            "SELECT start_date, end_date, is_current "
            "FROM alumni_career WHERE alumni_id = ?",
            (alumni_id,)).fetchall()
    in_study = False
    in_work  = False
    for r in edu:
        s = r["start_date"] or ""
        e = r["end_date"]   or ""
        st = r["status"] or ""
        if s and s > when:
            continue
        if e and e < when and st != "In Progress":
            continue
        in_study = True
        break
    for r in car:
        s = r["start_date"] or ""
        e = r["end_date"]   or ""
        if s and s > when:
            continue
        if r["is_current"]:
            in_work = True
            break
        if e and e < when:
            continue
        in_work = True
        break
    if in_study and in_work:
        return "Mixed"
    if in_study:
        return "In HE/FE"
    if in_work:
        return "Employed"
    return "Not known"


def sustained_destinations(*, leaving_year: str
                              ) -> list[SustainedRow]:
    init_db()
    if not _YEAR_RE.match(leaving_year):
        raise ValidationError(
            "Leaving year must be a 4-digit year (e.g. 2024)")
    base_year = int(leaving_year)
    rows = list_alumni(leaving_year=leaving_year)
    out: list[SustainedRow] = []
    for a in rows:
        out.append(SustainedRow(
            alumni_id=a.alumni_id, full_name=a.full_name,
            leaving_year=leaving_year,
            year_plus_1=_activity_at(a.alumni_id,
                                          f"{base_year + 1}-10-15"),
            year_plus_3=_activity_at(a.alumni_id,
                                          f"{base_year + 3}-10-15"),
            year_plus_5=_activity_at(a.alumni_id,
                                          f"{base_year + 5}-10-15"),
        ))
    return out


# ── #35 Cohort comparison (year-over-year destination mix) ───────

@dataclass
class CohortComparison:
    years: list[str]                       # sorted desc
    destinations: list[str]                # column order
    counts: dict[str, dict[str, int]]      # counts[year][dest]
    totals: dict[str, int]                 # totals[year]


def cohort_comparison() -> CohortComparison:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT leaving_year, destination_type, COUNT(*) AS n "
            "FROM alumni WHERE leaving_year IS NOT NULL "
            "GROUP BY leaving_year, destination_type"
        ).fetchall()
    counts: dict[str, dict[str, int]] = {}
    totals: dict[str, int] = {}
    years: set[str] = set()
    for r in rows:
        y = r["leaving_year"]
        d = r["destination_type"] or "Unknown"
        n = int(r["n"])
        counts.setdefault(y, {})[d] = n
        totals[y] = totals.get(y, 0) + n
        years.add(y)
    return CohortComparison(
        years=sorted(years, reverse=True),
        destinations=list(DESTINATION_TYPES),
        counts=counts, totals=totals)


# ── #36 University success rates ─────────────────────────────────

@dataclass
class UniversitySuccessRow:
    leaving_year: str
    uni_total: int
    russell: int
    oxbridge: int
    top_third: int


def university_success_rates() -> list[UniversitySuccessRow]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT leaving_year, destination_detail "
            "FROM alumni "
            "WHERE destination_type = 'University' "
            "AND leaving_year IS NOT NULL"
        ).fetchall()
    by_year: dict[str, dict[str, int]] = {}
    for r in rows:
        y = r["leaving_year"]
        d = r["destination_detail"] or ""
        s = by_year.setdefault(y, {"uni_total": 0, "russell": 0,
                                       "oxbridge": 0, "top_third": 0})
        s["uni_total"] += 1
        if _contains_any(d, RUSSELL_GROUP):
            s["russell"] += 1
        if _contains_any(d, OXBRIDGE):
            s["oxbridge"] += 1
        if _contains_any(d, TOP_THIRD_UNIVERSITIES):
            s["top_third"] += 1
    return [UniversitySuccessRow(
        leaving_year=y, uni_total=v["uni_total"],
        russell=v["russell"], oxbridge=v["oxbridge"],
        top_third=v["top_third"])
        for y, v in sorted(by_year.items(), reverse=True)]


# ── #37 Apprenticeship outcomes ──────────────────────────────────

_LEVEL_RE = re.compile(r"\blevel\s*(\d)\b", re.IGNORECASE)


@dataclass
class ApprenticeshipRow:
    leaving_year: str
    level: str            # "Level 2".."Level 7" or "Unknown"
    provider: str
    count: int


def apprenticeship_outcomes() -> list[ApprenticeshipRow]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT leaving_year, destination_detail "
            "FROM alumni WHERE destination_type = 'Apprenticeship' "
            "AND leaving_year IS NOT NULL"
        ).fetchall()
    bucket: dict[tuple[str, str, str], int] = {}
    for r in rows:
        y = r["leaving_year"]
        detail = (r["destination_detail"] or "").strip()
        m = _LEVEL_RE.search(detail)
        level = f"Level {m.group(1)}" if m else "Unknown"
        # Provider heuristic: the substring after " at " or " — "
        # or " - ", else the whole detail.
        provider = detail
        for sep in (" at ", " @ ", " — ", " - "):
            if sep in detail:
                provider = detail.split(sep, 1)[1].strip()
                break
        key = (y, level, provider or "Unknown")
        bucket[key] = bucket.get(key, 0) + 1
    return sorted(
        (ApprenticeshipRow(leaving_year=k[0], level=k[1],
                            provider=k[2], count=v)
         for k, v in bucket.items()),
        key=lambda r: (r.leaving_year, r.level, -r.count))


# ── #38 Disadvantage-gap (tagged vs cohort baseline) ─────────────

@dataclass
class GapRow:
    destination_type: str
    cohort_count: int
    cohort_pct: float
    tagged_count: int
    tagged_pct: float
    gap_pct: float       # tagged_pct - cohort_pct


def disadvantage_gap(*,
                      tag_name: str = "Bursary recipient",
                      leaving_year: str | None = None
                      ) -> list[GapRow]:
    init_db()
    args_y: list[Any] = []
    year_clause = ""
    if leaving_year:
        if not _YEAR_RE.match(leaving_year):
            raise ValidationError("Leaving year must be 4 digits")
        year_clause = "AND a.leaving_year = ?"
        args_y.append(leaving_year)
    with _connect() as conn:
        cohort = conn.execute(
            f"SELECT destination_type, COUNT(*) AS n FROM alumni a "
            f"WHERE 1 = 1 {year_clause} "
            "GROUP BY destination_type", args_y).fetchall()
        tagged = conn.execute(
            f"""SELECT a.destination_type, COUNT(*) AS n
                  FROM alumni a
                  JOIN alumni_tag_links l ON l.alumni_id = a.alumni_id
                  JOIN alumni_tags      t ON t.tag_id = l.tag_id
                 WHERE t.name = ? COLLATE NOCASE {year_clause}
              GROUP BY a.destination_type""",
            (tag_name, *args_y)).fetchall()
    c_total = sum(r["n"] for r in cohort) or 1
    t_total = sum(r["n"] for r in tagged) or 1
    c_map = {r["destination_type"]: int(r["n"]) for r in cohort}
    t_map = {r["destination_type"]: int(r["n"]) for r in tagged}
    out: list[GapRow] = []
    for d in DESTINATION_TYPES:
        c = c_map.get(d, 0)
        t = t_map.get(d, 0)
        c_pct = 100 * c / c_total
        t_pct = 100 * t / t_total
        out.append(GapRow(
            destination_type=d, cohort_count=c, cohort_pct=c_pct,
            tagged_count=t, tagged_pct=t_pct,
            gap_pct=t_pct - c_pct))
    return out


# ── #39 Geographic distribution ──────────────────────────────────

@dataclass
class GeoCell:
    country: str
    region: str
    count: int


def geographic_distribution() -> list[GeoCell]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT COALESCE(country, '—') AS c, "
            "COALESCE(region, '—') AS r, COUNT(*) AS n "
            "FROM alumni "
            "WHERE status NOT IN ('Deceased') "
            "AND (country IS NOT NULL OR current_location IS NOT NULL) "
            "GROUP BY c, r ORDER BY n DESC"
        ).fetchall()
    return [GeoCell(country=r["c"], region=r["r"], count=int(r["n"]))
              for r in rows]


# ── #40 Sector breakdown ─────────────────────────────────────────

@dataclass
class SectorRow:
    sector: str
    count: int
    pct: float


def sector_breakdown() -> list[SectorRow]:
    """Distribution of alumni by ``current_sector``. Falls back to
    the sector of the latest ``alumni_career.is_current`` row when
    the top-level field is empty."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT COALESCE(NULLIF(a.current_sector, ''),
                                 (SELECT sector FROM alumni_career
                                  WHERE alumni_id = a.alumni_id
                                  AND is_current = 1
                                  ORDER BY career_id DESC LIMIT 1))
                       AS s,
                       COUNT(*) AS n
                FROM alumni a
               WHERE a.status NOT IN ('Deceased')
               GROUP BY s
               ORDER BY n DESC"""
        ).fetchall()
    total = sum(int(r["n"]) for r in rows) or 1
    return [SectorRow(sector=(r["s"] or "Unknown"),
                       count=int(r["n"]),
                       pct=100 * int(r["n"]) / total)
              for r in rows]


# ── #41 "Where are they now" HTML generator ──────────────────────

def alumni_with_public_consent() -> list[Alumnus]:
    """Alumni who are Active and have granted (and not withdrawn)
    the 'Photo Use' consent scope. Use this to decide who to
    publish on a public-facing site."""
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.* FROM alumni a
               WHERE a.status = 'Active'
                 AND EXISTS (
                   SELECT 1 FROM alumni_consent c
                    WHERE c.alumni_id = a.alumni_id
                      AND c.scope = 'Photo Use'
                      AND c.withdrawn_at IS NULL)
               ORDER BY a.leaving_year DESC NULLS LAST,
                          a.last_name ASC""").fetchall()
    return [_row(r) for r in rows]


def _wan_profile_html(a: Alumnus) -> str:
    edu  = list_education(a.alumni_id)
    car  = list_career(a.alumni_id)
    ach  = list_achievements(a.alumni_id)

    def esc(x: str | None) -> str:
        return _html.escape(x or "")

    parts: list[str] = []
    parts.append("<!doctype html>\n<html lang='en'>\n<head>")
    parts.append("<meta charset='utf-8'>")
    parts.append(f"<title>{esc(a.display_name)}</title>")
    parts.append("<style>body{font-family:system-ui,sans-serif;"
                  "max-width:780px;margin:2em auto;padding:0 1em;"
                  "color:#222} h1{margin-bottom:.2em} .meta{color:#666;"
                  "margin-bottom:1.2em} h2{margin-top:1.4em;"
                  "border-bottom:1px solid #ccc;padding-bottom:2px} "
                  "ul{padding-left:1.2em}</style>")
    parts.append("</head>\n<body>")
    parts.append(f"<h1>{esc(a.display_name)}</h1>")
    bits = []
    if a.leaving_year:
        bits.append(f"Class of {esc(a.leaving_year)}")
    if a.current_role and a.current_employer:
        bits.append(f"{esc(a.current_role)} at "
                      f"{esc(a.current_employer)}")
    elif a.current_employer:
        bits.append(esc(a.current_employer))
    if a.current_sector:
        bits.append(esc(a.current_sector))
    if a.country or a.region:
        loc = ", ".join(filter(None, [a.region, a.country]))
        bits.append(esc(loc))
    if bits:
        parts.append(f"<div class='meta'>{' &middot; '.join(bits)}</div>")
    if a.photo_path:
        parts.append(f"<img src='{esc(a.photo_path)}' "
                      "alt='' style='max-width:240px;float:right;"
                      "margin:0 0 1em 1em;border-radius:6px'>")
    if a.bio:
        parts.append(f"<p>{esc(a.bio)}</p>")
    if edu:
        parts.append("<h2>Education</h2><ul>")
        for e in edu:
            line = f"<b>{esc(e.qualification)}</b>"
            if e.subject:
                line += f" {esc(e.subject)}"
            line += f" — {esc(e.institution)}"
            if e.grade:
                line += f" ({esc(e.grade)})"
            parts.append(f"<li>{line}</li>")
        parts.append("</ul>")
    if car:
        parts.append("<h2>Career</h2><ul>")
        for c in car:
            line = (f"<b>{esc(c.role)}</b> at {esc(c.employer)}")
            if c.is_current:
                line += " <small>(current)</small>"
            parts.append(f"<li>{line}</li>")
        parts.append("</ul>")
    if ach:
        parts.append("<h2>Achievements</h2><ul>")
        for x in ach:
            parts.append(f"<li>{esc(x.title)}</li>")
        parts.append("</ul>")
    parts.append("</body></html>\n")
    return "\n".join(parts)


def generate_where_are_they_now(out_dir: str | Path) -> int:
    """Write per-alumnus HTML profile pages plus an index page to
    ``out_dir``. Only alumni who are Active and have granted
    (and not withdrawn) the 'Photo Use' consent scope are
    included. Returns the number of profile pages written."""
    from pathlib import Path as _P
    base = _P(out_dir)
    base.mkdir(parents=True, exist_ok=True)
    rows = alumni_with_public_consent()
    index_items: list[str] = []
    for a in rows:
        fname = f"alumnus_{a.alumni_id}.html"
        (base / fname).write_text(_wan_profile_html(a),
                                       encoding="utf-8")
        meta = (a.current_role and a.current_employer
                  and f" — {_html.escape(a.current_role)} at "
                       f"{_html.escape(a.current_employer)}"
                  or "")
        index_items.append(
            f"<li><a href='{fname}'>"
            f"{_html.escape(a.display_name)}</a> "
            f"<small>({_html.escape(a.leaving_year or '—')})</small>"
            f"{meta}</li>")
    index_html = (
        "<!doctype html>\n<html><head><meta charset='utf-8'>"
        "<title>Where are they now?</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:780px;"
        "margin:2em auto;padding:0 1em} li{margin:.4em 0}</style>"
        "</head><body>"
        f"<h1>Where are they now? ({len(rows)} alumni)</h1>"
        "<ul>" + "\n".join(index_items) + "</ul>"
        "</body></html>"
    )
    (base / "index.html").write_text(index_html, encoding="utf-8")
    _log_action("report.where_are_they_now",
                  out_dir=str(out_dir), profiles=len(rows))
    return len(rows)


# ── #37 NEET tracking ────────────────────────────────────────────

@dataclass
class NEETCheck:
    check_id: int
    alumni_id: int
    months_after: int
    checked_on: str
    status: str
    notes: str | None


def _row_neet(r: db.Row) -> NEETCheck:
    return NEETCheck(
        check_id=r["check_id"], alumni_id=r["alumni_id"],
        months_after=int(r["months_after"]),
        checked_on=r["checked_on"], status=r["status"],
        notes=r["notes"])


def record_neet_check(alumni_id: int, *,
                          months_after: int, status: str,
                          checked_on: str | None = None,
                          notes: str | None = None,
                          actor: str | None = None) -> NEETCheck:
    init_db()
    if months_after not in (3, 6, 12, 24):
        raise ValidationError(
            "months_after must be one of 3, 6, 12, 24")
    if status not in NEET_STATUSES:
        raise ValidationError(
            f"Status must be one of: {', '.join(NEET_STATUSES)}")
    when = _validate_date(checked_on, "Checked on", required=False) \
        or _dt.date.today().isoformat()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            """INSERT INTO alumni_neet_checks
                   (alumni_id, months_after, checked_on, status, notes)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(alumni_id, months_after) DO UPDATE SET
                   checked_on = excluded.checked_on,
                   status     = excluded.status,
                   notes      = excluded.notes""",
            (alumni_id, months_after, when, status,
             (notes or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_neet_checks "
            "WHERE alumni_id = ? AND months_after = ?",
            (alumni_id, months_after)).fetchone()
    _log_action("neet.record", actor=actor,
                  alumni_id=alumni_id, months_after=months_after,
                  status=status)
    return _row_neet(r)


def list_neet_checks(alumni_id: int) -> list[NEETCheck]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM alumni_neet_checks WHERE alumni_id = ? "
            "ORDER BY months_after", (alumni_id,)).fetchall()
    return [_row_neet(r) for r in rows]


@dataclass
class NEETRateRow:
    months_after: int
    cohort: int
    neet: int
    not_neet: int
    unknown: int
    neet_rate_pct: float


def neet_breakdown(*, leaving_year: str | None = None
                        ) -> list[NEETRateRow]:
    """Aggregate NEET status by months-after-leaving. Alumni without
    a recorded check at a given milestone are counted as 'Unknown'."""
    init_db()
    rows: list[NEETRateRow] = []
    sql_alumni = ("SELECT alumni_id FROM alumni "
                    "WHERE deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql_alumni += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        ids = [r["alumni_id"] for r in conn.execute(
            sql_alumni, params).fetchall()]
        cohort = len(ids)
    if cohort == 0:
        return rows
    for m in (3, 6, 12):
        with _connect() as conn:
            placeholders = ",".join("?" * len(ids))
            checks = conn.execute(
                f"SELECT status FROM alumni_neet_checks "
                f"WHERE months_after = ? AND alumni_id IN "
                f"({placeholders})",
                (m, *ids)).fetchall()
        neet = sum(1 for c in checks if c["status"] == "NEET")
        not_neet = sum(1 for c in checks
                          if c["status"] not in ("NEET", "Unknown"))
        unknown = cohort - neet - not_neet
        denom = neet + not_neet or 1
        rows.append(NEETRateRow(
            months_after=m, cohort=cohort, neet=neet,
            not_neet=not_neet, unknown=unknown,
            neet_rate_pct=round(100 * neet / denom, 1)))
    return rows


# ── #38 Russell Group / Oxbridge breakout ────────────────────────

def _is_uni_match(name: str | None, group: tuple[str, ...]) -> bool:
    if not name:
        return False
    n = name.lower()
    return any(u.lower() in n for u in group)


@dataclass
class UniGroupRow:
    leaving_year: str | None
    cohort: int
    russell_group: int
    russell_rate_pct: float
    oxbridge: int
    oxbridge_rate_pct: float


def russell_group_breakdown(*, leaving_year: str | None = None
                                  ) -> UniGroupRow:
    init_db()
    sql_a = "SELECT alumni_id, leaving_year FROM alumni " \
              "WHERE deleted_at IS NULL"
    params: list[Any] = []
    if leaving_year:
        sql_a += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        alumni = conn.execute(sql_a, params).fetchall()
        cohort = len(alumni)
        rg = ox = 0
        for a in alumni:
            unis = conn.execute(
                "SELECT institution FROM alumni_education "
                "WHERE alumni_id = ?", (a["alumni_id"],)).fetchall()
            names = [u["institution"] for u in unis]
            if any(_is_uni_match(n, RUSSELL_GROUP_UNIVERSITIES)
                      for n in names):
                rg += 1
            if any(_is_uni_match(n, OXBRIDGE_UNIVERSITIES)
                      for n in names):
                ox += 1
    return UniGroupRow(
        leaving_year=leaving_year, cohort=cohort,
        russell_group=rg,
        russell_rate_pct=round(100 * rg / max(cohort, 1), 1),
        oxbridge=ox,
        oxbridge_rate_pct=round(100 * ox / max(cohort, 1), 1))


# ── #39 Postgraduate progression ─────────────────────────────────

@dataclass
class PostgraduateRow:
    alumni_id: int
    full_name: str
    leaving_year: str | None
    pg_qualifications: list[str]
    pg_institutions: list[str]


def postgraduate_progression(*, leaving_year: str | None = None
                                   ) -> list[PostgraduateRow]:
    """Alumni with at least one alumni_education row whose
    qualification matches a known PG label (MSc/PhD/etc.)."""
    init_db()
    sql = ("""SELECT a.alumni_id, a.first_name, a.last_name,
                      a.leaving_year
                 FROM alumni a WHERE deleted_at IS NULL""")
    params: list[Any] = []
    if leaving_year:
        sql += " AND a.leaving_year = ?"
        params.append(leaving_year)
    out: list[PostgraduateRow] = []
    with _connect() as conn:
        alumni = conn.execute(sql, params).fetchall()
        for a in alumni:
            edus = conn.execute(
                "SELECT qualification, institution "
                "FROM alumni_education WHERE alumni_id = ?",
                (a["alumni_id"],)).fetchall()
            pg = [(e["qualification"], e["institution"]) for e in edus
                    if any(p.lower() in (e["qualification"] or "").lower()
                              for p in PG_QUALIFICATIONS)]
            if not pg:
                continue
            out.append(PostgraduateRow(
                alumni_id=a["alumni_id"],
                full_name=f"{a['first_name']} {a['last_name']}",
                leaving_year=a["leaving_year"],
                pg_qualifications=[q for q, _ in pg],
                pg_institutions=[i for _, i in pg]))
    return out


@dataclass
class PostgraduateRate:
    leaving_year: str | None
    cohort: int
    pg_count: int
    pg_rate_pct: float


def postgraduate_rate(*, leaving_year: str | None = None
                           ) -> PostgraduateRate:
    init_db()
    sql = ("SELECT COUNT(*) FROM alumni WHERE deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        cohort = int(conn.execute(sql, params).fetchone()[0])
    pg = len(postgraduate_progression(leaving_year=leaving_year))
    return PostgraduateRate(
        leaving_year=leaving_year, cohort=cohort, pg_count=pg,
        pg_rate_pct=round(100 * pg / max(cohort, 1), 1))


# ── #40 First-generation HE outcomes ─────────────────────────────

def set_first_gen_he(alumni_id: int, value: bool, *,
                          actor: str | None = None) -> None:
    init_db()
    with _connect() as conn:
        _require_alumnus(conn, alumni_id)
        conn.execute(
            "UPDATE alumni SET first_gen_he = ? WHERE alumni_id = ?",
            (1 if value else 0, alumni_id))
        conn.commit()
    _log_action("first_gen_he.set", actor=actor,
                  alumni_id=alumni_id, value=value)


def first_gen_he_for_student(student_id: str) -> bool | None:
    """``True`` when the learner's alumni record is marked first
    generation in HE; ``None`` otherwise.

    Never ``False``: the column defaults to 0, so an unmarked row means
    "not recorded" as often as "not first generation", and a reader such
    as the university handover must not present the one as the other.
    """
    init_db()
    with _connect() as conn:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(alumni)")}
        if "first_gen_he" not in cols:
            return None
        row = conn.execute(
            "SELECT MAX(first_gen_he) FROM alumni "
            "WHERE original_student_id = ?",
            ((student_id or "").strip(),)).fetchone()
    return True if row and row[0] else None


@dataclass
class FirstGenOutcomeRow:
    bucket: str  # 'first_gen' or 'continuing_gen'
    cohort: int
    in_he: int
    he_rate_pct: float
    russell_group: int
    russell_rate_pct: float


def first_gen_outcomes(*, leaving_year: str | None = None
                            ) -> list[FirstGenOutcomeRow]:
    """HE-entry and Russell-Group rates, split by ``first_gen_he``
    flag. ``in_he`` is the count of alumni with ``destination_type``
    set to 'University' or 'Further Study'."""
    init_db()
    sql_a = ("SELECT alumni_id, first_gen_he, destination_type "
              "FROM alumni WHERE deleted_at IS NULL")
    params: list[Any] = []
    if leaving_year:
        sql_a += " AND leaving_year = ?"
        params.append(leaving_year)
    with _connect() as conn:
        rows = conn.execute(sql_a, params).fetchall()
    buckets: dict[str, dict[str, int]] = {
        "first_gen":      {"cohort": 0, "in_he": 0, "rg": 0},
        "continuing_gen": {"cohort": 0, "in_he": 0, "rg": 0},
    }
    he_set = {"University", "Further Study"}
    with _connect() as conn:
        for r in rows:
            key = ("first_gen"
                     if _opt(r, "first_gen_he") else "continuing_gen")
            buckets[key]["cohort"] += 1
            if r["destination_type"] in he_set:
                buckets[key]["in_he"] += 1
            unis = conn.execute(
                "SELECT institution FROM alumni_education "
                "WHERE alumni_id = ?", (r["alumni_id"],)).fetchall()
            if any(_is_uni_match(u["institution"],
                                    RUSSELL_GROUP_UNIVERSITIES)
                      for u in unis):
                buckets[key]["rg"] += 1
    return [FirstGenOutcomeRow(
        bucket=k, cohort=v["cohort"], in_he=v["in_he"],
        he_rate_pct=round(100 * v["in_he"] / max(v["cohort"], 1), 1),
        russell_group=v["rg"],
        russell_rate_pct=round(100 * v["rg"] / max(v["cohort"], 1), 1))
            for k, v in buckets.items()]


# ── #42 HESA benchmark comparison ────────────────────────────────

@dataclass
class HESABenchmark:
    benchmark_id: int
    leaving_year: str
    metric: str
    rate_pct: float
    source: str | None


def _row_benchmark(r: db.Row) -> HESABenchmark:
    return HESABenchmark(
        benchmark_id=r["benchmark_id"],
        leaving_year=r["leaving_year"], metric=r["metric"],
        rate_pct=float(r["rate_pct"]), source=r["source"])


def upsert_hesa_benchmark(leaving_year: str, metric: str,
                              rate_pct: float, *,
                              source: str | None = None,
                              actor: str | None = None
                              ) -> HESABenchmark:
    init_db()
    leaving_year = (leaving_year or "").strip()
    metric = (metric or "").strip()
    if not leaving_year or not metric:
        raise ValidationError(
            "leaving_year and metric are required")
    if not 0 <= rate_pct <= 100:
        raise ValidationError("rate_pct must be between 0 and 100")
    with _connect() as conn:
        conn.execute(
            """INSERT INTO alumni_hesa_benchmarks
                   (leaving_year, metric, rate_pct, source)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(leaving_year, metric) DO UPDATE SET
                   rate_pct = excluded.rate_pct,
                   source   = excluded.source""",
            (leaving_year, metric, rate_pct,
             (source or "").strip() or None))
        conn.commit()
        r = conn.execute(
            "SELECT * FROM alumni_hesa_benchmarks "
            "WHERE leaving_year = ? AND metric = ?",
            (leaving_year, metric)).fetchone()
    _log_action("hesa.upsert", actor=actor,
                  leaving_year=leaving_year, metric=metric,
                  rate_pct=rate_pct)
    return _row_benchmark(r)


def list_hesa_benchmarks(*, leaving_year: str | None = None
                              ) -> list[HESABenchmark]:
    init_db()
    sql = "SELECT * FROM alumni_hesa_benchmarks"
    params: list[Any] = []
    if leaving_year:
        sql += " WHERE leaving_year = ?"; params.append(leaving_year)
    sql += " ORDER BY leaving_year DESC, metric"
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_benchmark(r) for r in rows]


@dataclass
class HESADeltaRow:
    metric: str
    leaving_year: str
    school_rate_pct: float
    hesa_rate_pct: float
    delta_pct: float


def _local_rate(metric: str, leaving_year: str | None) -> float | None:
    """Map a metric name to the corresponding internal rate. New
    metric names can be plugged in here without disturbing callers."""
    if metric == "he_entry":
        rows = first_gen_outcomes(leaving_year=leaving_year)
        cohort = sum(r.cohort for r in rows)
        in_he = sum(r.in_he for r in rows)
        return round(100 * in_he / max(cohort, 1), 1) if cohort else None
    if metric == "russell_group":
        r = russell_group_breakdown(leaving_year=leaving_year)
        return r.russell_rate_pct if r.cohort else None
    if metric == "oxbridge":
        r = russell_group_breakdown(leaving_year=leaving_year)
        return r.oxbridge_rate_pct if r.cohort else None
    if metric == "postgraduate":
        r = postgraduate_rate(leaving_year=leaving_year)
        return r.pg_rate_pct if r.cohort else None
    return None


def compare_with_hesa(leaving_year: str) -> list[HESADeltaRow]:
    init_db()
    benchmarks = list_hesa_benchmarks(leaving_year=leaving_year)
    out: list[HESADeltaRow] = []
    for b in benchmarks:
        local = _local_rate(b.metric, leaving_year)
        if local is None:
            continue
        out.append(HESADeltaRow(
            metric=b.metric, leaving_year=leaving_year,
            school_rate_pct=local, hesa_rate_pct=b.rate_pct,
            delta_pct=round(local - b.rate_pct, 1)))
    return out


# ── #43 DfE 16-18 destinations export ────────────────────────────

_DFE_BUCKETS = {
    "University":      "Sustained higher education",
    "Further Study":   "Sustained further education",
    "Apprenticeship":  "Apprenticeship",
    "Employment":      "Employment",
    "Self-Employed":   "Employment",
    "Volunteering":    "Other positive activity",
    "Gap Year":        "Other positive activity",
    "Other":           "Other",
    "Unknown":         "Activity not captured",
}


def export_dfe_destinations_csv(out_path: str,  # type: ignore[name-defined]
                                    *, leaving_year: str,
                                    actor: str | None = None) -> int:
    """Emit a DfE 16-18 destinations measure CSV for one cohort.

    Output columns track the published DfE structure: leaver, DfE
    bucket, sustained flag, university (if applicable). Returns the
    number of rows written."""
    init_db()
    from pathlib import Path as _Path
    import csv as _csv
    with _connect() as conn:
        rows = conn.execute(
            """SELECT a.*,
                       (SELECT institution FROM alumni_education e
                          WHERE e.alumni_id = a.alumni_id
                          ORDER BY e.start_date LIMIT 1) AS first_uni
                  FROM alumni a
                 WHERE a.leaving_year = ?
                   AND a.deleted_at IS NULL""",
            (leaving_year,)).fetchall()
    p = _Path(out_path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IntegrationError(
            f"Cannot create output directory {p.parent}: {exc}") from exc
    try:
        with p.open("w", newline="", encoding="utf-8") as fh:
            w = _csv.writer(fh)
            w.writerow(["Pupil reference", "First name", "Last name",
                           "Leaving year", "DfE category",
                           "Destination detail", "Institution",
                           "Sustained at 6 months"])
            for r in rows:
                bucket = _DFE_BUCKETS.get(
                    r["destination_type"], "Other")
                try:
                    sustained = _activity_at(r["alumni_id"], "6m") \
                        if "_activity_at" in globals() else "Unknown"
                except Exception:  # noqa: BLE001
                    # _activity_at is a best-effort helper from a
                    # sibling cluster; never let it fail the export.
                    sustained = "Unknown"
                w.writerow([
                    r["original_student_id"] or "",
                    r["first_name"], r["last_name"], leaving_year,
                    bucket, r["destination_detail"] or "",
                    r["first_uni"] or "", sustained])
    except OSError as exc:
        raise IntegrationError(
            f"Could not write {p}: {exc}") from exc
    _log_action("dfe.export", actor=actor,
                  leaving_year=leaving_year, rows=len(rows),
                  path=str(p))
    return len(rows)


# Sibling-module names, bound after this module's own definitions so the
# feature modules can call each other without an import cycle at load time.
# They are only used inside function bodies (and string annotations).
from .records import (  # noqa: E402,F401
    list_alumni,
)
from .profile import (  # noqa: E402,F401
    _require_alumnus,
    list_achievements,
    list_career,
    list_education,
)
