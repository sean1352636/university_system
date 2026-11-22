"""What a programme (a ``courses`` row) *is*, and the rules that hang off it:
specification and entry requirements, progression and exit awards, fees,
intake targets, programme external examiners, survey results, and its link to
Programme Governance (versions, accreditation, teach-out).

* A course is identified by its code (``courses.code`` / ``course_code``).
  Student records file people under either the code or the course *name*
  (``students.course`` holds both 'CS' and 'Computer Science'), so look-ups
  accept both — see :func:`names_for`.
* Exit awards use each student's earned credits by module level
  (``degree_audit.progress.module_progress``; a module's level is
  ``modules.level``, else year of study + 3).
* Fees live in finance's ``program_fees`` (one row per course, year and fee
  type); "home" maps to the undergraduate / graduate tuition fee type and
  "international" to the international one.
* Governance keys on ``governed_programmes.programme_code``; an existing
  course is registered there directly (status active) rather than through a
  new-programme proposal.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

import re
from datetime import date

from education_system.systems.university.infrastructure.database.schemas import (
    programme_catalogue_schema as schema,
)

SPEC_FIELDS = ("award_title", "ucas_code", "hecos_code", "mode_of_study", "awarding_body",
               "campus", "typical_offer", "required_subjects", "english_requirement",
               "pass_mark", "progression_credits", "max_compensated_credits",
               "compensation_min_mark")
_NUMBERS = {"pass_mark": (0, 100), "progression_credits": (0, 480),
            "max_compensated_credits": (0, 120), "compensation_min_mark": (0, 100)}
#: UK sector norms, offered as a starting point (never written unasked).
STANDARD_EXIT_AWARDS = {
    "undergraduate": (("Certificate of Higher Education", 120, 90, 4, 0),
                      ("Diploma of Higher Education", 240, 90, 5, 0),
                      ("Ordinary Degree", 300, 60, 6, 0),
                      ("Honours Degree", 360, 90, 6, 1)),
    "postgraduate": (("Postgraduate Certificate", 60, 40, 7, 0),
                     ("Postgraduate Diploma", 120, 90, 7, 0),
                     ("Masters Degree", 180, 150, 7, 1)),
}
STANDARD_PROGRESSION = {"pass_mark": 40, "progression_credits": 120,
                        "max_compensated_credits": 20, "compensation_min_mark": 30}
EXAMINER_MAX_YEARS = 4
FEE_STATUSES = ("home", "international")
_ACTIVE = "LOWER(COALESCE(s.status, 'active')) NOT IN ('withdrawn', 'graduated', 'completed', " \
          "'inactive', 'suspended', 'transferred', 'merged')"


def ensure(conn):
    schema.apply_to_connection(conn)


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _course(conn, code):
    rows = _dicts(conn.execute(
        "SELECT COALESCE(NULLIF(course_code, ''), code) AS code, "
        "COALESCE(NULLIF(course_name, ''), name) AS name, level, credits, duration, status "
        "FROM courses WHERE COALESCE(NULLIF(course_code, ''), code) = ?", (code,)))
    if not rows:
        raise ValueError(f"No course {code}")
    return rows[0]


def names_for(conn, code) -> list[str]:
    """The values a student record may use for this course: code and name."""
    course = _course(conn, code)
    return [v for v in (course["code"], course["name"]) if v]


def is_postgraduate(course) -> bool:
    return "post" in str(course.get("level") or "").lower() or \
        str(course.get("level") or "").lower() in ("pg", "masters", "graduate")


# ── specification ───────────────────────────────────────────────────────


def get_spec(conn, code) -> dict:
    ensure(conn)
    _course(conn, code)
    rows = _dicts(conn.execute(f"SELECT {', '.join(SPEC_FIELDS)}, updated_by, updated_at "
                               "FROM course_specifications WHERE course_code = ?", (code,)))
    return rows[0] if rows else dict.fromkeys(SPEC_FIELDS + ("updated_by", "updated_at"))


def _clean_number(key, value):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{key.replace('_', ' ')} must be a number") from None
    low, high = _NUMBERS[key]
    if not low <= number <= high:
        raise ValueError(f"{key.replace('_', ' ')} must be between {low} and {high}")
    return int(number) if key.endswith("credits") else number


def clean_spec(values: dict) -> dict:
    out = {}
    for key, value in values.items():
        if key not in SPEC_FIELDS:
            raise ValueError(f"{key} is not part of the programme specification")
        value = value.strip() if isinstance(value, str) else value
        out[key] = _clean_number(key, value) if key in _NUMBERS else (value or None)
    if out.get("ucas_code") and not re.fullmatch(r"[A-Z0-9]{4}", out["ucas_code"].upper()):
        raise ValueError("A UCAS course code is 4 letters/digits, e.g. G400")
    if out.get("hecos_code") and not re.fullmatch(r"\d{6}", out["hecos_code"]):
        raise ValueError("A HECoS code is 6 digits, e.g. 100366")
    if out.get("mode_of_study") and out["mode_of_study"] not in schema.MODES:
        raise ValueError(f"Mode of study must be one of: {', '.join(schema.MODES)}")
    if out.get("ucas_code"):
        out["ucas_code"] = out["ucas_code"].upper()
    return out


def save_spec(conn, code, values: dict, actor) -> dict:
    """Save the specification; returns ``{field: (old, new)}`` for what changed."""
    current = get_spec(conn, code)
    clean = clean_spec(values)
    changed = {k: (current.get(k), v) for k, v in clean.items()
               if str(current.get(k) or "") != str(v or "")}
    if not changed:
        return {}
    conn.execute("INSERT OR IGNORE INTO course_specifications (course_code) VALUES (?)", (code,))
    sets = ", ".join(f"{k} = ?" for k in changed)
    # db-audit: ignore[DBW001] - keys are checked against SPEC_FIELDS
    conn.execute(f"UPDATE course_specifications SET {sets}, updated_by = ?, "
                 "updated_at = datetime('now') WHERE course_code = ?",
                 (*[v for _o, v in changed.values()], actor, code))
    _log(conn, code, changed, actor)
    return changed


def _log(conn, code, changed, actor):
    """Field changes into ``course_history`` when it has the usual columns."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(course_history)")}
    if not {"course_code", "field_name", "old_value", "new_value"} <= cols:
        return
    who = "changed_by" if "changed_by" in cols else None
    for field, (old, new) in changed.items():
        columns = ["course_code", "field_name", "old_value", "new_value"] + ([who] if who else [])
        values = [code, f"spec.{field}", None if old is None else str(old),
                  None if new is None else str(new)] + ([actor] if who else [])
        # db-audit: ignore[DBW001] - column names are literals checked by PRAGMA
        conn.execute(f"INSERT INTO course_history ({', '.join(columns)}) "
                     f"VALUES ({', '.join('?' for _ in columns)})", values)


def use_standard_progression(conn, code, actor) -> dict:
    return save_spec(conn, code, dict(STANDARD_PROGRESSION), actor)


def has_progression_rule(conn, code) -> bool:
    """Whether :func:`progression` has the two figures it cannot work without."""
    spec = get_spec(conn, code)
    return spec["progression_credits"] is not None and spec["pass_mark"] is not None


def fill_progression_rule(conn, code, actor) -> dict:
    """Standard values for whichever parts of the rule are blank; set ones stay."""
    spec = get_spec(conn, code)
    return save_spec(conn, code, {k: v for k, v in STANDARD_PROGRESSION.items()
                                  if spec[k] is None}, actor)


# ── exit awards ─────────────────────────────────────────────────────────


def exit_awards(conn, code) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT id, award_name, total_credits, credits_at_level, at_level, "
                               "is_final FROM course_exit_awards WHERE course_code = ? "
                               "ORDER BY total_credits", (code,)))


def add_exit_award(conn, code, award_name, total_credits, credits_at_level=0, at_level=None,
                   is_final=False) -> int:
    ensure(conn)
    _course(conn, code)
    if not (award_name or "").strip():
        raise ValueError("Name the award")
    try:
        total, at = int(total_credits), int(credits_at_level or 0)
        level = int(at_level) if str(at_level or "").strip() else None
    except (TypeError, ValueError):
        raise ValueError("Credits and level must be whole numbers") from None
    if total <= 0 or at < 0 or at > total:
        raise ValueError("Credits at level cannot exceed the total, and the total must be positive")
    if at and level is None:
        raise ValueError("Say which level the credits-at-level rule applies to")
    try:
        cur = conn.execute("INSERT INTO course_exit_awards (course_code, award_name, total_credits, "
                           "credits_at_level, at_level, is_final) VALUES (?, ?, ?, ?, ?, ?)",
                           (code, award_name.strip(), total, at, level, 1 if is_final else 0))
    except Exception as exc:
        if "UNIQUE" in str(exc):
            raise ValueError(f"{code} already has an award called {award_name}") from None
        raise
    return int(cur.lastrowid)


def remove_exit_award(conn, award_id) -> bool:
    ensure(conn)
    return conn.execute("DELETE FROM course_exit_awards WHERE id = ?", (award_id,)).rowcount > 0


def use_standard_exit_awards(conn, code) -> int:
    """Add the sector-standard awards the course does not already have."""
    course = _course(conn, code)
    have = {a["award_name"] for a in exit_awards(conn, code)}
    added = 0
    key = "postgraduate" if is_postgraduate(course) else "undergraduate"
    for name, total, at, level, final in STANDARD_EXIT_AWARDS[key]:
        if name not in have:
            add_exit_award(conn, code, name, total, at, level, final)
            added += 1
    return added


def _module_levels(conn) -> dict:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(modules)")}
    level = "level" if "level" in cols else "NULL"
    out = {}
    # db-audit: ignore[DBW001] - column chosen from PRAGMA
    for code, lvl, year in conn.execute(f"SELECT module_code, {level}, year FROM modules"):
        try:
            out[code] = int(lvl) if lvl else int(str(year).strip()) + 3
        except (TypeError, ValueError):
            out[code] = None
    return out


def credits_by_level(conn, student_id) -> dict:
    """``{level: earned credits}`` plus ``'total'``."""
    from education_system.systems.university.domains.progression.domain.degree_audit.progress import (  # noqa: E501
        module_progress,
    )
    levels = _module_levels(conn)
    out = {"total": 0.0}
    for row in module_progress(conn, student_id):
        if row["earned"]:
            lvl = levels.get(row["module_code"])
            out[lvl] = out.get(lvl, 0.0) + row["credits"]
            out["total"] += row["credits"]
    return out


def eligible_exit_award(conn, student_id, code) -> dict | None:
    """The highest exit award the student's earned credits already meet."""
    credit = credits_by_level(conn, student_id)
    best = None
    for award in exit_awards(conn, code):
        at_or_above = sum(v for k, v in credit.items()
                          if k != "total" and k is not None and award["at_level"]
                          and k >= award["at_level"])
        if credit["total"] >= award["total_credits"] and at_or_above >= award["credits_at_level"]:
            best = award
    return best


# ── progression ─────────────────────────────────────────────────────────


def _stage_results(conn, student_id, code, year):
    """Final marks and credits for the modules of one stage."""
    from education_system.systems.university.domains.progression.domain.degree_audit.progress import (  # noqa: E501
        module_progress,
    )
    stage = {r[0] for r in conn.execute("SELECT module_code FROM course_curriculum WHERE "
                                        "course_code = ? AND year = ?", (code, year))}
    marks = {r[0]: r[1] for r in conn.execute(
        "SELECT module_code, final_score FROM module_grades WHERE student_id = ? "
        "AND final_score IS NOT NULL ORDER BY id", (str(student_id),))}
    return [dict(r, mark=marks.get(r["module_code"])) for r in module_progress(conn, student_id)
            if r["module_code"] in stage]


def progression(conn, student_id, code, year) -> dict:
    """Apply the course's progression rule to one stage's results.

    ``progress`` when the passed credits meet the rule, ``progress with
    compensation`` when a shortfall is within the compensation limit and every
    failed mark is at least the compensation minimum, else ``resit required``
    (or ``incomplete`` while marks are outstanding).
    """
    rule = get_spec(conn, code)
    if rule["progression_credits"] is None or rule["pass_mark"] is None:
        raise ValueError(f"{code} has no progression rule — set one in the specification")
    rows = _stage_results(conn, student_id, code, year)
    if not rows:
        return {"passed_credits": 0, "required": rule["progression_credits"], "failed": [],
                "outstanding": [], "outcome": "no results for this year"}
    passed = sum(r["credits"] for r in rows if r["mark"] is not None and r["mark"] >= rule["pass_mark"])
    failed = [r for r in rows if r["mark"] is not None and r["mark"] < rule["pass_mark"]]
    outstanding = [r["module_code"] for r in rows if r["mark"] is None]
    short = rule["progression_credits"] - passed
    out = {"passed_credits": passed, "required": rule["progression_credits"],
           "failed": [r["module_code"] for r in failed], "outstanding": outstanding}
    if short <= 0:
        return dict(out, outcome="progress")
    if outstanding:
        return dict(out, outcome="incomplete")
    floor = rule["compensation_min_mark"] or 0
    if short <= (rule["max_compensated_credits"] or 0) and all(r["mark"] >= floor for r in failed):
        return dict(out, outcome="progress with compensation")
    return dict(out, outcome="resit required")


# ── fees ────────────────────────────────────────────────────────────────


def _fee_type(conn, course, fee_status):
    wanted = ("international" if fee_status == "international"
              else "graduate" if is_postgraduate(course) else "undergraduate")
    for fid, name in conn.execute("SELECT fee_type_id, fee_name FROM fee_types "
                                  "WHERE COALESCE(is_active, 1) = 1 ORDER BY fee_type_id"):
        lowered = str(name).lower()
        if "tuition" in lowered and wanted in lowered and \
                (wanted != "graduate" or "under" not in lowered):
            return fid
    raise ValueError(f"No active {wanted} tuition fee type in Finance — add one there first")


def fees(conn, code) -> list[dict]:
    rows = _dicts(conn.execute(
        "SELECT p.program_fee_id AS id, p.academic_year, p.amount, p.currency, t.fee_name "
        "FROM program_fees p LEFT JOIN fee_types t ON t.fee_type_id = p.fee_type_id "
        "WHERE p.course = ? ORDER BY p.academic_year DESC, t.fee_name", (code,)))
    for r in rows:
        r["fee_status"] = "international" if "international" in str(r["fee_name"]).lower() \
            else "home"
    return rows


def set_fee(conn, code, academic_year, fee_status, amount) -> None:
    course = _course(conn, code)
    if fee_status not in FEE_STATUSES:
        raise ValueError("Fee status is home or international")
    if not re.fullmatch(r"\d{4}[/-]\d{2,4}", str(academic_year or "").strip()):
        raise ValueError("Academic year looks like 2026/27")
    try:
        amount = round(float(amount), 2)
    except (TypeError, ValueError):
        raise ValueError("The fee must be a number") from None
    if amount < 0:
        raise ValueError("The fee cannot be negative")
    fee_type = _fee_type(conn, course, fee_status)
    updated = conn.execute("UPDATE program_fees SET amount = ?, updated_at = datetime('now') "
                           "WHERE course = ? AND academic_year = ? AND fee_type_id = ?",
                           (amount, code, academic_year.strip(), fee_type)).rowcount
    if not updated:
        conn.execute("INSERT INTO program_fees (fee_type_id, course, amount, currency, "
                     "academic_year, created_at, updated_at) VALUES (?, ?, ?, 'GBP', ?, "
                     "datetime('now'), datetime('now'))",
                     (fee_type, code, amount, academic_year.strip()))


# ── intake ──────────────────────────────────────────────────────────────


def set_intake_target(conn, code, academic_year, target, mode="full-time", actor=None):
    ensure(conn)
    _course(conn, code)
    if mode not in schema.MODES:
        raise ValueError(f"Mode of study must be one of: {', '.join(schema.MODES)}")
    try:
        target = int(target)
    except (TypeError, ValueError):
        raise ValueError("The target must be a whole number") from None
    if target < 0:
        raise ValueError("The target cannot be negative")
    conn.execute("INSERT INTO course_intake_targets (course_code, academic_year, mode_of_study, "
                 "target, updated_by) VALUES (?, ?, ?, ?, ?) ON CONFLICT(course_code, "
                 "academic_year, mode_of_study) DO UPDATE SET target = excluded.target, "
                 "updated_by = excluded.updated_by, updated_at = datetime('now')",
                 (code, str(academic_year).strip(), mode, target, actor))


def _year_matches(stored, academic_year):
    """'2026' / '2026/27' / '2026-2027' all mean the year starting 2026."""
    return str(stored or "")[:4] == str(academic_year or "")[:4]


def intake_report(conn, code) -> list[dict]:
    """Per academic year: target vs applications, offers, acceptances and
    students who actually started."""
    ensure(conn)
    names = [n.lower() for n in names_for(conn, code)]
    targets = {}
    for year, mode, target in conn.execute("SELECT academic_year, mode_of_study, target FROM "
                                           "course_intake_targets WHERE course_code = ?", (code,)):
        targets[year] = targets.get(year, 0) + target
    apps = []
    try:
        apps = [r for r in conn.execute("SELECT academic_year, LOWER(COALESCE(status, '')), "
                                        "LOWER(program_applied) FROM admission_applications")
                if r[2] in names]
    except Exception:
        apps = []
    # One row per starting year, whichever spelling ('2026', '2026/27') each
    # source used; shown with the target's label when there is one.
    labels = {str(y)[:4]: y for y in targets}
    years = sorted({str(y)[:4] for y in targets} | {str(r[0])[:4] for r in apps}, reverse=True)
    out = []
    for year in years:
        mine = [r[1] for r in apps if _year_matches(r[0], year)]
        offers = sum(1 for s in mine if "offer" in s or s in ("accepted", "firm", "enrolled"))
        accepted = sum(1 for s in mine if s in ("accepted", "firm", "enrolled", "offer_accepted"))
        started = conn.execute(f"SELECT COUNT(*) FROM students s WHERE LOWER(s.course) IN "
                               f"({', '.join('?' for _ in names)}) AND substr(COALESCE("
                               "s.enrollment_date, s.registration_datetime, ''), 1, 4) = ?",
                               (*names, str(year)[:4])).fetchone()[0]
        target = next((t for y, t in targets.items() if _year_matches(y, year)), None)
        out.append({"academic_year": labels.get(year, year), "target": target, "applications": len(mine),
                    "offers": offers, "accepted": accepted, "started": started,
                    "against_target": None if not target else round(started / target * 100)})
    return out


# ── programme external examiners ────────────────────────────────────────


def examiners(conn, code) -> list[dict]:
    ensure(conn)
    today = date.today().isoformat()
    rows = _dicts(conn.execute(
        "SELECT ce.*, e.name, e.institution FROM course_external_examiners ce "
        "JOIN external_examiners e ON e.examiner_id = ce.examiner_id "
        "WHERE ce.course_code = ? ORDER BY ce.appointed_to DESC", (code,)))
    for r in rows:
        r["current"] = r["appointed_from"] <= today <= r["appointed_to"]
        r["report_overdue"] = bool(r["report_due"] and not r["report_received_at"]
                                   and r["report_due"] < today)
        r["response_outstanding"] = bool(r["report_received_at"] and not r["responded_at"])
    return rows


def appoint_examiner(conn, code, examiner_id, appointed_from, appointed_to, report_due=None):
    ensure(conn)
    _course(conn, code)
    if not conn.execute("SELECT 1 FROM external_examiners WHERE examiner_id = ? AND "
                        "LOWER(COALESCE(status, 'active')) = 'active'", (examiner_id,)).fetchone():
        raise ValueError("Choose an active external examiner")
    start, end = str(appointed_from or "")[:10], str(appointed_to or "")[:10]
    try:
        years = (date.fromisoformat(end) - date.fromisoformat(start)).days / 365.25
    except ValueError:
        raise ValueError("Dates are YYYY-MM-DD") from None
    if years <= 0:
        raise ValueError("The appointment must end after it starts")
    if years > EXAMINER_MAX_YEARS + 0.1:
        raise ValueError(f"A term of office is at most {EXAMINER_MAX_YEARS} years")
    clash = conn.execute("SELECT 1 FROM course_external_examiners WHERE course_code = ? AND "
                         "examiner_id = ? AND appointed_from <= ? AND appointed_to >= ?",
                         (code, examiner_id, end, start)).fetchone()
    if clash:
        raise ValueError("That examiner is already appointed to this course for those dates")
    cur = conn.execute("INSERT INTO course_external_examiners (course_code, examiner_id, "
                       "appointed_from, appointed_to, report_due) VALUES (?, ?, ?, ?, ?)",
                       (code, examiner_id, start, end, (report_due or "")[:10] or None))
    return int(cur.lastrowid)


def record_report(conn, appointment_id, summary, received=None):
    if not (summary or "").strip():
        raise ValueError("Summarise the report")
    done = conn.execute("UPDATE course_external_examiners SET report_received_at = ?, "
                        "report_summary = ? WHERE id = ?",
                        ((received or date.today().isoformat())[:10], summary.strip(),
                         appointment_id)).rowcount
    if not done:
        raise ValueError("No such appointment")


def record_response(conn, appointment_id, response, actor):
    row = conn.execute("SELECT report_received_at FROM course_external_examiners WHERE id = ?",
                       (appointment_id,)).fetchone()
    if not row:
        raise ValueError("No such appointment")
    if not row[0]:
        raise ValueError("Record the examiner's report before the response to it")
    if not (response or "").strip():
        raise ValueError("Write the response")
    conn.execute("UPDATE course_external_examiners SET response = ?, responded_at = "
                 "date('now'), responded_by = ? WHERE id = ?",
                 (response.strip(), actor, appointment_id))


# ── survey results ──────────────────────────────────────────────────────


def set_survey_result(conn, code, academic_year, theme, agree_pct, respondents=None,
                      survey="NSS"):
    ensure(conn)
    _course(conn, code)
    try:
        pct = float(agree_pct)
        count = int(respondents) if str(respondents or "").strip() else None
    except (TypeError, ValueError):
        raise ValueError("Agreement is a percentage and respondents a whole number") from None
    if not 0 <= pct <= 100 or not (theme or "").strip():
        raise ValueError("Give a theme and a percentage between 0 and 100")
    conn.execute("INSERT INTO course_survey_results VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT"
                 "(course_code, survey, academic_year, theme) DO UPDATE SET "
                 "agree_pct = excluded.agree_pct, respondents = excluded.respondents",
                 (code, survey, str(academic_year).strip(), theme.strip(), pct, count))


def survey_results(conn, code) -> list[dict]:
    ensure(conn)
    return _dicts(conn.execute("SELECT survey, academic_year, theme, agree_pct, respondents "
                               "FROM course_survey_results WHERE course_code = ? "
                               "ORDER BY academic_year DESC, theme", (code,)))


# ── governance ──────────────────────────────────────────────────────────


def governed_id(conn, code):
    try:
        row = conn.execute("SELECT programme_id FROM governed_programmes WHERE programme_code = ?",
                           (code,)).fetchone()
    except Exception:
        return None
    return row[0] if row else None


def register_for_governance(conn, code, actor) -> int:
    """Put an existing course on the governance register (status active)."""
    existing = governed_id(conn, code)
    if existing:
        return existing
    course = _course(conn, code)
    spec = get_spec(conn, code)
    award = spec.get("award_title") or ("Postgraduate" if is_postgraduate(course)
                                        else "Undergraduate")
    department = conn.execute("SELECT department FROM courses WHERE COALESCE(NULLIF("
                              "course_code, ''), code) = ?", (code,)).fetchone()
    cur = conn.execute("INSERT INTO governed_programmes (programme_code, programme_name, "
                       "owning_school, award_type, status, created_by) VALUES "
                       "(?, ?, ?, ?, 'active', ?)",
                       (code, course["name"], department[0] if department else None, award, actor))
    conn.execute("INSERT INTO programme_governance_history (programme_id, action, actor_id, "
                 "reason) VALUES (?, 'registered_existing_course', ?, ?)",
                 (cur.lastrowid, actor, "Registered from Course Management"))
    return int(cur.lastrowid)


def active_students(conn, code) -> int:
    names = names_for(conn, code)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(students)")}
    flag = " AND COALESCE(s.is_active, 1) = 1" if "is_active" in cols else ""
    status = f" AND {_ACTIVE}" if "status" in cols else ""
    # db-audit: ignore[DBW001] - placeholders and literal clauses only
    return conn.execute(f"SELECT COUNT(*) FROM students s WHERE s.course IN "
                        f"({', '.join('?' for _ in names)}){flag}{status}", names).fetchone()[0]


def closure_blocker(conn, code, new_status) -> str | None:
    """Why the course cannot be taken out of the catalogue yet, or None.

    A course with students still on it must have a teach-out plan (what they
    are promised until they finish) before it stops running.
    """
    if str(new_status).lower() in ("active", "draft", "planned"):
        return None
    try:
        students = active_students(conn, code)
    except ValueError:  # not a catalogue course code: nothing to protect
        return None
    if not students:
        return None
    pid = governed_id(conn, code)
    plan = pid and conn.execute("SELECT 1 FROM programme_teach_out_plans WHERE programme_id = ?",
                                (pid,)).fetchone()
    if plan:
        return None
    return (f"{students} student(s) are still on {code}. Record a teach-out plan "
            "(Course Management → Programme Record → Governance) before it stops running.")
