"""Module registration: which modules a student takes, by the rules of their
course and year. One rule set behind the Module Registration portal, its
CLI menu and the registration API.

* **Structure** - a student's modules come from their course and year:
  ``module_programme_designations`` (core / compulsory -> compulsory,
  optional -> optional) when the course has any, else the course
  curriculum (every module compulsory).
* **Compulsory** modules are enrolled automatically and cannot be dropped by
  the student. **Optional** modules are chosen within the course's limits
  (``programme_credit_rules``: number of options, credit target and
  maximum) and, unless the rules say otherwise, approved by the student's
  personal tutor, the course team or an admin.
* **Every enrolment** goes through ``module_enrolment`` (prerequisites,
  co-requisites, exclusions, the registration window, capacity, sections),
  joins the waitlist when the module is full, keeps ``module_enrolments``
  in step with ``student_modules`` (the record everything reads) and logs a
  status change. After committing, callers run :func:`side_effects` (fees,
  timetable, library holds, ATAS).
* **Who may register**: Active or Registration Pending students only.
* **Catalogue** - any student can browse every active module
  (``module_catalogue``); enrolling outside the course structure stays with
  staff, who override with a reason.
* **Messages** - after committing, :func:`side_effects` sends the enrolment
  confirmation and ``module_registration_messages.after_drop`` the drop /
  withdrawal acknowledgement.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date, datetime

from education_system.systems.university.application.modules import enrolment as module_enrolment
from education_system.systems.university.infrastructure.database.schemas import (
    module_registration_schema as schema,
)

REGISTRABLE = ("Active", "Registration Pending")
DEFAULT_RULES = {"target_credits": 120, "max_credits": 140, "min_optional": 0,
                 "max_optional": None, "needs_approval": 1}
DECLARATIONS = (
    "My personal and contact details are correct.",
    "I have read and will follow the student regulations.",
    "I will pay, or have arranged to pay, my tuition fees.",
)


def ensure(conn):
    from education_system.systems.university.services.bus import registration_calendar
    registration_calendar.ensure_schema(conn)       # commits: call before any write
    schema.apply_to_connection(conn)


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def academic_year(today=None) -> str:
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}/{start + 1}"


# ── the student and their course structure ──────────────────────────────


def student(conn, student_id) -> dict:
    rows = _dicts(conn.execute(
        "SELECT s.student_id, TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, "
        "'')) AS name, s.status, s.enrollment_date, s.course AS course_raw, "
        "(SELECT COALESCE(NULLIF(c.course_code, ''), c.code) FROM courses c WHERE s.course IN "
        "(c.course_code, c.code, c.course_name, c.name) LIMIT 1) AS course FROM students s "
        "WHERE s.student_id = ? AND s.student_id NOT LIKE 'ERASED-%'", (str(student_id),)))
    if not rows:
        raise ValueError(f"No student {student_id}")
    out = rows[0]
    out["year_of_study"] = year_of_study(conn, out)
    return out


def _int(value):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return number if 0 < number <= 7 else None


def year_of_study(conn, s) -> int:
    """Recorded year of study, else years since enrolment (Sept start; a
    student enrolled from June onwards is counted from that September)."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(students)")}
    for column in ("year_of_study", "course_year", "year"):
        if column in cols:
            row = conn.execute(f"SELECT {column} FROM students WHERE student_id = ?",  # nosec B608
                               (s["student_id"],)).fetchone()
            if row and _int(row[0]):
                return _int(row[0])
    try:
        started = date.fromisoformat(str(s.get("enrollment_date") or "")[:10])
    except ValueError:
        return 1
    start_year = started.year if started.month >= 6 else started.year - 1
    current = int(academic_year()[:4])
    return max(1, min(current - start_year + 1, 7))


def rules(conn, course, year) -> dict:
    ensure(conn)
    row = _dicts(conn.execute("SELECT * FROM programme_credit_rules WHERE course_code = ? AND "
                              "year_of_study = ?", (course, year)))
    return {**DEFAULT_RULES, **(row[0] if row else {}), "course_code": course,
            "year_of_study": year}


def _module_rows(conn, codes):
    if not codes:
        return {}
    marks = ", ".join("?" for _ in codes)
    return {r["module_code"]: r for r in _dicts(conn.execute(
        f"SELECT module_code, module_name, NULLIF(credits, 0) AS credits FROM modules WHERE "
        f"module_code IN ({marks})", list(codes)))}


def structure(conn, course, year) -> dict:
    """``{"compulsory": [...], "optional": [...], "source"}`` - each module a
    dict with code, name and credits (None when not recorded).

    Compulsory = modules designated core / compulsory for the course and
    year, plus the year's curriculum modules not designated optional (so a
    course with only its options designated keeps its curriculum).
    """
    designated = conn.execute(
        "SELECT module_code, category FROM module_programme_designations WHERE course_code = ? "
        "AND (year_of_study IS NULL OR year_of_study = ?)", (course, year)).fetchall() \
        if _has(conn, "module_programme_designations") else []
    curriculum = [r[0] for r in conn.execute(
        "SELECT module_code FROM course_curriculum WHERE course_code = ? AND year = ? ORDER BY id",
        (course, year))] if _has(conn, "course_curriculum") else []
    optional = [c for c, k in designated if k == "optional"]
    compulsory = list(dict.fromkeys(
        [c for c, k in designated if k in ("core", "compulsory")] +
        [c for c in curriculum if c not in optional]))
    groups = {"compulsory": compulsory, "optional": optional}
    info = _module_rows(conn, compulsory + optional)
    out = {"source": "designations + curriculum" if designated else "curriculum"}
    for kind, codes in groups.items():
        out[kind] = [{"code": c, "name": (info.get(c) or {}).get("module_name") or c,
                      "credits": (info.get(c) or {}).get("credits")} for c in codes]
    return out


def _has(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (table,)).fetchone()


def _states(conn, student_id) -> dict:
    states = {r[0]: r[1] for r in conn.execute(
        "SELECT module_code, status FROM student_modules WHERE student_id = ?", (student_id,))}
    for (code,) in conn.execute("SELECT module_code FROM module_waitlist WHERE student_id = ? "
                                "AND status = 'waiting'", (student_id,)).fetchall():
        states.setdefault(code, "Waitlisted")
    for (code,) in conn.execute(
            "SELECT i.module_code FROM module_choice_items i JOIN module_choice_submissions s ON "
            "s.id = i.submission_id WHERE s.student_id = ? AND s.status = 'submitted'",
            (student_id,)).fetchall():
        states.setdefault(code, "Awaiting approval")
    return states


def enrolled_credits(conn, student_id) -> tuple[int, int]:
    """``(credits of current enrolments, enrolments with no credits)``."""
    rows = conn.execute("SELECT NULLIF(m.credits, 0) FROM student_modules sm JOIN modules m ON "
                        "m.module_code = sm.module_code WHERE sm.student_id = ? AND "
                        "sm.status = 'Enrolled'", (student_id,)).fetchall()
    return sum(r[0] or 0 for r in rows), sum(1 for r in rows if r[0] is None)


def block_reason(s) -> str | None:
    if s["status"] not in REGISTRABLE:
        return f"{s['name']} is {s['status']}, so cannot change module registration"
    if not s["course"]:
        return f"{s['name']}'s course '{s['course_raw']}' is not in the catalogue"
    return None


def overview(conn, student_id) -> dict:
    """Everything the portal shows for one student."""
    from education_system.systems.university.services.bus import registration_calendar as cal
    ensure(conn)
    s = student(conn, student_id)
    reason = block_reason(s)
    course_rules = rules(conn, s["course"], s["year_of_study"]) if s["course"] else DEFAULT_RULES
    plan = structure(conn, s["course"], s["year_of_study"]) if s["course"] else \
        {"compulsory": [], "optional": [], "source": None}
    states = _states(conn, s["student_id"])
    for kind in ("compulsory", "optional"):
        for m in plan[kind]:
            m["state"] = states.get(m["code"], "")
    credits, unknown = enrolled_credits(conn, s["student_id"])
    return {"student": s, "blocked": reason, "rules": course_rules, "structure": plan,
            "credits": credits, "unknown_credits": unknown,
            "window": cal.registration_state(conn=conn), "drop": cal.classify_drop(conn=conn),
            "pending": pending_submission(conn, s["student_id"]),
            "other_enrolments": [c for c, st in states.items() if st == "Enrolled" and c not in
                                 {m["code"] for k in ("compulsory", "optional")
                                  for m in plan[k]}]}


# ── enrolling and dropping ──────────────────────────────────────────────


def _log(conn, student_id, code, to_status, from_status, actor, note=None):
    conn.execute("INSERT INTO enrolment_status_changes (student_id, module_code, from_status, "
                 "to_status, changed_by, source, note) VALUES (?, ?, ?, ?, ?, "
                 "'module_registration', ?)", (str(student_id), code, from_status, to_status,
                                               actor, note))


def _registration_id(conn, student_id, course, year):
    row = conn.execute("SELECT registration_id FROM programme_registrations WHERE student_id = ? "
                       "ORDER BY academic_year = ? DESC, registration_id DESC LIMIT 1",
                       (student_id, year)).fetchone()
    if row:
        return row[0]
    today = date.today().isoformat()
    return conn.execute(
        "INSERT INTO programme_registrations (student_id, programme_code, academic_year, "
        "occurrence_code, status, effective_from, registered_at, registered_by) VALUES "
        "(?, ?, ?, 'MAIN', 'registered', ?, ?, 'module_registration')",
        (student_id, course, year, today, datetime.now().isoformat())).lastrowid


def mirror(conn, student_id, code, status, course=None):
    """Keep ``module_enrolments`` in step with ``student_modules``. Once the
    mirror triggers are installed (migration ``1a3c5e7f9b2d``) the database
    does this on every ``student_modules`` write and this does nothing."""
    if not _has(conn, "module_enrolments"):
        return
    from education_system.systems.university.infrastructure.database.schemas import (
        enrolment_mirror_schema,
    )
    if enrolment_mirror_schema.installed(conn.execute):
        return
    canonical = "enrolled" if status == "Enrolled" else str(status).lower()
    if conn.execute("UPDATE module_enrolments SET status = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE student_id = ? AND module_code = ?",
                    (canonical, student_id, code)).rowcount or canonical != "enrolled":
        return
    year = academic_year()
    conn.execute("INSERT OR IGNORE INTO module_enrolments (registration_id, student_id, "
                 "module_code, academic_year, status, effective_from) VALUES (?, ?, ?, ?, "
                 "'enrolled', ?)", (_registration_id(conn, student_id, course, year), student_id,
                                    code, year, date.today().isoformat()))


def _allowed(plan, code):
    for kind in ("compulsory", "optional"):
        if any(m["code"] == code for m in plan[kind]):
            return kind
    return None


def _check_credits(conn, s, code, course_rules):
    credits, _unknown = enrolled_credits(conn, s["student_id"])
    extra = (_module_rows(conn, [code]).get(code) or {}).get("credits") or 0
    if credits + extra > course_rules["max_credits"]:
        return (f"{code} would take {s['name']} to {credits + extra} credits, over the "
                f"{course_rules['max_credits']} maximum")
    return None


def _gate(conn, s, code, plan, course_rules, staff, override):
    """Refusals that a member of staff may override with a reason."""
    problems = []
    if not _allowed(plan, code):
        problems.append(f"{code} is not part of {s['course']} year {s['year_of_study']}")
    over = _check_credits(conn, s, code, course_rules)
    if over:
        problems.append(over)
    if problems and not (staff and (override or "").strip()):
        raise ValueError("; ".join(problems) + (" (staff can override with a reason)"
                                                if staff else ""))
    return problems


def enrol(conn, student_id, code, actor, *, staff=False, section_id=None, override=None) -> dict:
    """Enrol (or waitlist) one module. Returns ``{"result", "notes"}``."""
    ensure(conn)
    s = student(conn, student_id)
    reason = block_reason(s)
    if reason:
        raise ValueError(reason)
    plan = structure(conn, s["course"], s["year_of_study"])
    course_rules = rules(conn, s["course"], s["year_of_study"])
    notes = _gate(conn, s, code, plan, course_rules, staff, override)
    verdict = module_enrolment.eligibility(conn, code, s["student_id"], section_id)
    if not verdict.ok:
        result = _not_eligible(conn, s, code, verdict, staff, override, section_id, actor)
        if result:
            return result
        notes.append(verdict.reason())
    previous = conn.execute("SELECT status FROM student_modules WHERE student_id = ? AND "
                            "module_code = ?", (s["student_id"], code)).fetchone()
    result = module_enrolment.enrol(conn, code, s["student_id"], section_id)
    mirror(conn, s["student_id"], code, "Enrolled", s["course"])
    _log(conn, s["student_id"], code, "Enrolled", previous[0] if previous else None, actor,
         ("override: " + override + " - " + "; ".join(notes)) if notes else None)
    return {"result": result, "notes": notes}


def _not_eligible(conn, s, code, verdict, staff, override, section_id, actor):
    """Waitlist a full module; otherwise refuse unless staff override."""
    if verdict.needs_section and section_id is None:
        raise SectionRequired(code, verdict.sections)
    if verdict.only_capacity:
        if not conn.execute("SELECT 1 FROM module_waitlist WHERE module_code = ? AND "
                            "student_id = ? AND status = 'waiting'",
                            (code, s["student_id"])).fetchone():
            module_enrolment.join_waitlist(conn, code, s["student_id"], section_id)
            _log(conn, s["student_id"], code, "Waitlisted", None, actor)
        return {"result": "waitlisted", "notes": [verdict.reason()]}
    if not (staff and (override or "").strip()):
        raise ValueError(verdict.reason())
    return None


class SectionRequired(ValueError):
    """The module runs in sections; the caller asks which one, then retries."""

    def __init__(self, code, sections):
        super().__init__(f"{code} runs in sections; choose one")
        self.sections = sections


def drop(conn, student_id, code, actor, *, staff=False, reason=None) -> str:
    """Drop or withdraw from a module, by the registration calendar's
    deadlines. Compulsory modules need a member of staff and a reason."""
    from education_system.systems.university.services.bus import registration_calendar as cal
    ensure(conn)
    s = student(conn, student_id)
    verdict = cal.classify_drop(conn=conn)
    if not verdict["allowed"]:
        raise ValueError(verdict.get("reason") or "The withdrawal deadline has passed")
    plan = structure(conn, s["course"], s["year_of_study"]) if s["course"] else {}
    if plan and _allowed(plan, code) == "compulsory" and not (staff and (reason or "").strip()):
        raise ValueError(f"{code} is compulsory for {s['course']}; only staff can remove it, "
                         "with a reason")
    row = conn.execute("SELECT status FROM student_modules WHERE student_id = ? AND "
                       "module_code = ?", (s["student_id"], code)).fetchone()
    if not row or row[0] != "Enrolled":
        raise ValueError(f"{s['name']} is not enrolled on {code}")
    conn.execute("UPDATE student_modules SET status = ? WHERE student_id = ? AND module_code = ?",
                 (verdict["status"], s["student_id"], code))
    mirror(conn, s["student_id"], code, verdict["status"])
    _log(conn, s["student_id"], code, verdict["status"], "Enrolled", actor, reason)
    module_enrolment.promote_next(conn, code, actor)
    return verdict["status"]


def enrol_compulsory(conn, student_id, actor) -> dict:
    """Enrol every compulsory module not yet taken. Returns per-module results."""
    ensure(conn)
    s = student(conn, student_id)
    reason = block_reason(s)
    if reason:
        raise ValueError(reason)
    states = _states(conn, s["student_id"])
    out = {}
    for m in structure(conn, s["course"], s["year_of_study"])["compulsory"]:
        if states.get(m["code"]) == "Enrolled":
            continue
        conn.execute("SAVEPOINT compulsory")
        try:
            out[m["code"]] = enrol(conn, s["student_id"], m["code"], actor)["result"]
            conn.execute("RELEASE compulsory")
        except Exception as exc:
            conn.execute("ROLLBACK TO compulsory")
            conn.execute("RELEASE compulsory")
            out[m["code"]] = f"not enrolled: {exc}"
    return out


# ── optional choices and approval ───────────────────────────────────────


def pending_submission(conn, student_id):
    rows = _dicts(conn.execute("SELECT * FROM module_choice_submissions WHERE student_id = ? AND "
                               "status = 'submitted' ORDER BY id DESC LIMIT 1", (student_id,)))
    if not rows:
        return None
    rows[0]["modules"] = [r[0] for r in conn.execute(
        "SELECT module_code FROM module_choice_items WHERE submission_id = ?", (rows[0]["id"],))]
    return rows[0]


def _validate_choices(conn, s, codes, plan, course_rules):
    optional = {m["code"]: m for m in plan["optional"]}
    unknown = [c for c in codes if c not in optional]
    if unknown:
        raise ValueError(f"Not optional modules for {s['course']} year {s['year_of_study']}: "
                         + ", ".join(unknown))
    if len(codes) < course_rules["min_optional"]:
        raise ValueError(f"Choose at least {course_rules['min_optional']} optional module(s)")
    if course_rules["max_optional"] is not None and len(codes) > course_rules["max_optional"]:
        raise ValueError(f"Choose at most {course_rules['max_optional']} optional module(s)")
    credits = [m["credits"] for m in plan["compulsory"]] + [optional[c]["credits"] for c in codes]
    if None not in credits and sum(credits) > course_rules["max_credits"]:
        raise ValueError(f"These choices total {sum(credits)} credits, over the "
                         f"{course_rules['max_credits']} maximum")
    return credits


def submit_choices(conn, student_id, codes, actor) -> dict:
    """Record a student's optional choices: enrolled straight away when the
    course does not need approval, otherwise sent for approval."""
    from education_system.systems.university.services.bus import registration_calendar as cal
    ensure(conn)
    s = student(conn, student_id)
    reason = block_reason(s)
    if reason:
        raise ValueError(reason)
    window = cal.registration_state(conn=conn)
    if not window["open"]:
        raise ValueError(window.get("reason") or "Registration is closed")
    codes = list(dict.fromkeys(c.strip() for c in codes if c.strip()))
    plan = structure(conn, s["course"], s["year_of_study"])
    course_rules = rules(conn, s["course"], s["year_of_study"])
    _validate_choices(conn, s, codes, plan, course_rules)
    conn.execute("UPDATE module_choice_submissions SET status = 'withdrawn' WHERE student_id = ? "
                 "AND status = 'submitted'", (s["student_id"],))
    sub_id = conn.execute("INSERT INTO module_choice_submissions (student_id, academic_year, "
                          "year_of_study, submitted_by) VALUES (?, ?, ?, ?)",
                          (s["student_id"], academic_year(), s["year_of_study"], actor)).lastrowid
    conn.executemany("INSERT INTO module_choice_items (submission_id, module_code) VALUES (?, ?)",
                     [(sub_id, c) for c in codes])
    if not course_rules["needs_approval"]:
        return {"submission_id": sub_id, **_apply(conn, sub_id, s, codes, actor, "automatic")}
    return {"submission_id": sub_id, "status": "submitted", "results": {}}


def personal_tutor(conn, student_id):
    if not (_has(conn, "tutor_groups") and _has(conn, "tutor_group_members")):
        return None
    row = conn.execute("SELECT g.lead_tutor_id FROM tutor_group_members m JOIN tutor_groups g ON "
                       "g.group_id = m.group_id WHERE m.student_id = ? AND COALESCE(m.is_active, "
                       "1) = 1 AND COALESCE(g.is_active, 1) = 1 ORDER BY m.membership_id DESC "
                       "LIMIT 1", (student_id,)).fetchone()
    if not row or row[0] is None:
        return None
    user = conn.execute("SELECT username FROM users WHERE id = ? OR username = ?",
                        (row[0], str(row[0]))).fetchone()
    return user[0] if user else str(row[0])


def can_approve(conn, student_id, viewer, admin=False) -> bool:
    if admin:
        return True
    from education_system.systems.university.application.programmes import course_team
    s = student(conn, student_id)
    if viewer and viewer == personal_tutor(conn, s["student_id"]):
        return True
    return bool(s["course"] and course_team.access(conn, s["course"], viewer))


def submissions(conn, viewer, admin=False, status="submitted") -> list[dict]:
    ensure(conn)
    rows = _dicts(conn.execute(
        "SELECT s.*, TRIM(COALESCE(st.first_name, '') || ' ' || COALESCE(st.last_name, '')) AS "
        "name, st.course FROM module_choice_submissions s JOIN students st ON st.student_id = "
        "s.student_id WHERE s.status = ? ORDER BY s.submitted_at", (status,)))
    out = []
    for r in rows:
        if can_approve(conn, r["student_id"], viewer, admin):
            r["modules"] = [x[0] for x in conn.execute(
                "SELECT module_code FROM module_choice_items WHERE submission_id = ?", (r["id"],))]
            out.append(r)
    return out


def _apply(conn, sub_id, s, codes, actor, how):
    results = {}
    for code in codes:
        conn.execute("SAVEPOINT choice")
        try:
            results[code] = enrol(conn, s["student_id"], code, actor)["result"]
            conn.execute("RELEASE choice")
        except Exception as exc:
            conn.execute("ROLLBACK TO choice")
            conn.execute("RELEASE choice")
            results[code] = f"not enrolled: {exc}"
        conn.execute("UPDATE module_choice_items SET result = ? WHERE submission_id = ? AND "
                     "module_code = ?", (results[code], sub_id, code))
    conn.execute("UPDATE module_choice_submissions SET status = 'approved', decided_by = ?, "
                 "decided_at = datetime('now'), note = COALESCE(note, ?) WHERE id = ?",
                 (actor, how, sub_id))
    return {"status": "approved", "results": results}


def decide(conn, submission_id, approve: bool, viewer, *, admin=False, note="") -> dict:
    """Approve (enrol each choice) or reject a student's optional choices."""
    ensure(conn)
    row = _dicts(conn.execute("SELECT * FROM module_choice_submissions WHERE id = ?",
                              (submission_id,)))
    if not row or row[0]["status"] != "submitted":
        raise ValueError("That submission is not waiting for a decision")
    if not can_approve(conn, row[0]["student_id"], viewer, admin):
        raise ValueError("Only the student's personal tutor, course team or an admin can decide")
    s = student(conn, row[0]["student_id"])
    codes = [r[0] for r in conn.execute("SELECT module_code FROM module_choice_items WHERE "
                                        "submission_id = ?", (submission_id,))]
    if approve:
        result = _apply(conn, submission_id, s, codes, viewer, note or "approved")
    else:
        if not (note or "").strip():
            raise ValueError("Say why the choices are not approved")
        conn.execute("UPDATE module_choice_submissions SET status = 'rejected', decided_by = ?, "
                     "decided_at = datetime('now'), note = ? WHERE id = ?",
                     (viewer, note.strip(), submission_id))
        result = {"status": "rejected", "results": {}}
    _tell_student(conn, s, approve, result, note)
    return result


def _tell_student(conn, s, approved, result, note):
    from education_system.systems.university.infrastructure.email.messages_inbox import (
        deliver_inbox_message_on,
    )
    if approved:
        lines = [f"{c}: {r}" for c, r in result["results"].items()]
        body = "Your optional module choices were approved.\n\n" + "\n".join(lines)
    else:
        body = f"Your optional module choices were not approved: {note}. Please choose again."
    deliver_inbox_message_on(conn, s["student_id"], "Your module choices", body)


# ── annual registration ─────────────────────────────────────────────────


def annual_register(student_id, actor, *, declarations, mode_of_study=None, returning=False,
                    db_path=None) -> dict:
    """Annual (re-)registration through the registration lifecycle, then the
    year's compulsory modules. Every declaration must be accepted."""
    from contextlib import closing

    from education_system.systems.university.domains.learners.domain import student_lifecycle
    from education_system.systems.university.infrastructure.database.db import get_connection
    missing = [d for d in DECLARATIONS if not (declarations or {}).get(d)]
    if missing:
        raise ValueError("Accept every declaration: " + "; ".join(missing))
    year = academic_year()
    try:
        registration_id = student_lifecycle.register(
            str(student_id), year, actor_id=actor, mode_of_study=mode_of_study,
            declarations={d: True for d in DECLARATIONS}, returning=returning)
    except Exception as exc:
        raise ValueError(str(exc)) from None
    with closing(get_connection(db_path, row_factory=False)) as conn:
        modules = enrol_compulsory(conn, student_id, actor)
        conn.commit()
    return {"registration_id": registration_id, "academic_year": year, "modules": modules}


def side_effects(student_id, module_code) -> list[str]:
    """After an enrolment is committed: fees, timetable, library holds, an
    ATAS check for students with a visa record and the enrolment
    confirmation to the student. Best effort; returns the steps that failed."""
    failed = []
    steps = (("fee", "education_system.systems.university.domains.finance.domain.services."
                     "enrolment_fees", "assess_module_enrolment_fee"),
             ("timetable", "education_system.systems.university.domains.curriculum."
                           "domain.course_management.timetable_sync",
              "sync_for_student_enrolment"),
             ("library holds", "education_system.systems.university.plugins.campus_commerce."
                               "domain.textbooks.services.library_holds",
              "place_holds_for_enrolment"))
    import importlib
    for label, module, name in steps:
        try:
            getattr(importlib.import_module(module), name)(student_id, module_code)
        except Exception:
            failed.append(label)
    try:
        _atas(student_id, module_code)
    except Exception:
        failed.append("ATAS")
    from education_system.systems.university.application.modules import (
        registration_messages as module_registration_messages,
    )
    if not module_registration_messages.notify_enrolled(student_id, module_code):
        failed.append("confirmation e-mail")
    return failed


def _atas(student_id, module_code):
    from education_system.systems.university.domains.governance.domain.compliance.international_compliance.services import (  # noqa: E501
        visa_service as vs,
    )
    if not vs.is_atas_required_for_module(module_code):
        return
    if vs.get_visa_record(student_id) is None:
        return
    vs.record_atas_clearance(student_id=student_id, module_code=module_code,
                             certificate_number=None, issued_on=None, expires_on=None,
                             status="pending",
                             notes=f"Flagged at module registration for {module_code}")

