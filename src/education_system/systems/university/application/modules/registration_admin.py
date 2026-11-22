"""Setting up module registration: credit rules per course and year,
registration periods (add / drop / withdraw deadlines), module credits, and
keeping ``module_enrolments`` in step with ``student_modules``.

``student_modules`` is the enrolment record everything reads and writes
(grades, attendance, timetables, the lifecycle API); ``module_enrolments`` is
the per-registration copy, kept in step by database triggers since migration
``1a3c5e7f9b2d`` (``enrolment_mirror_schema``). :func:`mismatches` lists any
disagreement left (e.g. a student with no course, so no registration to copy
under) and :func:`fix_mismatches` reconciles.

Functions take an open connection and do not commit; the caller does.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.university.application.modules import registration as reg


def _dicts(cur):
    names = [d[0] for d in cur.description]
    return [dict(zip(names, tuple(r))) for r in cur.fetchall()]


def _admin(admin):
    if not admin:
        raise ValueError("Only an admin can change registration settings")


# ── credit rules ────────────────────────────────────────────────────────


def all_rules(conn) -> list[dict]:
    reg.ensure(conn)
    return _dicts(conn.execute("SELECT * FROM programme_credit_rules ORDER BY course_code, "
                               "year_of_study"))


def set_rules(conn, course, year, *, target_credits=120, max_credits=140, min_optional=0,
              max_optional=None, needs_approval=True, actor=None, admin=False):
    _admin(admin)
    reg.ensure(conn)
    values = [int(v) for v in (year, target_credits, max_credits, min_optional)]
    if not 0 < values[0] <= 7:
        raise ValueError("Year of study must be 1 to 7")
    if values[2] < values[1]:
        raise ValueError("The maximum must be at least the target")
    top = None if max_optional in (None, "") else int(max_optional)
    if top is not None and top < values[3]:
        raise ValueError("The most options allowed must be at least the minimum")
    conn.execute(
        "INSERT INTO programme_credit_rules (course_code, year_of_study, target_credits, "
        "max_credits, min_optional, max_optional, needs_approval, updated_by) VALUES "
        "(?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (course_code, year_of_study) DO UPDATE SET "
        "target_credits = excluded.target_credits, max_credits = excluded.max_credits, "
        "min_optional = excluded.min_optional, max_optional = excluded.max_optional, "
        "needs_approval = excluded.needs_approval, updated_by = excluded.updated_by, "
        "updated_at = datetime('now')",
        (course, *values, top, int(bool(needs_approval)), actor))


# ── registration periods ────────────────────────────────────────────────


def periods(conn) -> list[dict]:
    reg.ensure(conn)
    return _dicts(conn.execute("SELECT * FROM registration_periods ORDER BY registration_opens "
                               "DESC"))


def _date(value, label, required=False):
    if not value:
        if required:
            raise ValueError(f"{label} is required")
        return None
    try:
        return date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        raise ValueError(f"{label} must be YYYY-MM-DD") from None


def add_period(conn, *, academic_year, opens, closes, add_deadline=None, drop_deadline=None,
               withdraw_deadline=None, late_add_allowed=False, name="", admin=False) -> int:
    """Registration opens..closes; adds until the add deadline (later only if
    late adds are allowed); clean drops until the drop deadline, recorded
    withdrawals until the withdrawal deadline."""
    _admin(admin)
    reg.ensure(conn)
    dates = {"opens": _date(opens, "Opens", True), "closes": _date(closes, "Closes", True),
             "add": _date(add_deadline, "Add deadline"),
             "drop": _date(drop_deadline, "Drop deadline"),
             "withdraw": _date(withdraw_deadline, "Withdrawal deadline")}
    if dates["closes"] < dates["opens"]:
        raise ValueError("Registration must close after it opens")
    for key in ("add", "drop"):
        if dates[key] and not dates["opens"] <= dates[key] <= dates["closes"]:
            raise ValueError(f"The {key} deadline must fall inside the registration period")
    if dates["withdraw"] and dates["drop"] and dates["withdraw"] < dates["drop"]:
        raise ValueError("The withdrawal deadline cannot be before the drop deadline")
    return int(conn.execute(
        "INSERT INTO registration_periods (academic_year, name, registration_opens, "
        "registration_closes, add_deadline, drop_deadline, withdraw_deadline, late_add_allowed) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (academic_year or reg.academic_year(), name or f"Registration {academic_year}",
         dates["opens"], dates["closes"], dates["add"], dates["drop"], dates["withdraw"],
         int(bool(late_add_allowed)))).lastrowid)


def set_period_active(conn, period_id, active, admin=False):
    _admin(admin)
    reg.ensure(conn)
    if not conn.execute("UPDATE registration_periods SET is_active = ?, updated_at = "
                        "datetime('now') WHERE period_id = ?",
                        (int(bool(active)), period_id)).rowcount:
        raise ValueError("No such registration period")


# ── module credits ──────────────────────────────────────────────────────


def modules_without_credits(conn) -> list[dict]:
    return _dicts(conn.execute(
        "SELECT module_code, module_name, course, level FROM modules WHERE COALESCE(is_active, 1) "
        "= 1 AND COALESCE(credits, 0) = 0 AND TRIM(COALESCE(module_code, '')) <> '' "
        "ORDER BY module_code"))


def set_credits(conn, codes, credits, actor, admin=False) -> int:
    """Set the credit value of modules (recorded in the module history)."""
    _admin(admin)
    credits = int(credits)
    if not 0 < credits <= 120:
        raise ValueError("Credits must be between 1 and 120")
    history = reg._has(conn, "module_change_history")
    changed = 0
    for code in codes:
        old = conn.execute("SELECT credits FROM modules WHERE module_code = ?", (code,)).fetchone()
        if old is None:
            continue
        conn.execute("UPDATE modules SET credits = ? WHERE module_code = ?", (credits, code))
        if history:
            conn.execute("INSERT INTO module_change_history (module_code, field, old_value, "
                         "new_value, changed_by) VALUES (?, 'credits', ?, ?, ?)",
                         (code, None if old[0] is None else str(old[0]), str(credits), actor))
        changed += 1
    return changed


# ── keeping module_enrolments in step ───────────────────────────────────


def mismatches(conn) -> list[dict]:
    """Enrolments the two tables disagree about, and what fixing does."""
    if not reg._has(conn, "module_enrolments"):
        return []
    missing = _dicts(conn.execute(
        "SELECT sm.student_id, sm.module_code, sm.status AS record, NULL AS copy FROM "
        "student_modules sm WHERE sm.status = 'Enrolled' AND NOT EXISTS (SELECT 1 FROM "
        "module_enrolments me WHERE me.student_id = sm.student_id AND me.module_code = "
        "sm.module_code AND LOWER(me.status) = 'enrolled')"))
    extra = _dicts(conn.execute(
        "SELECT me.student_id, me.module_code, sm.status AS record, me.status AS copy FROM "
        "module_enrolments me LEFT JOIN student_modules sm ON sm.student_id = me.student_id AND "
        "sm.module_code = me.module_code WHERE LOWER(me.status) = 'enrolled' AND "
        "COALESCE(sm.status, '') <> 'Enrolled'"))
    for row in missing:
        row["fix"] = "add to module_enrolments"
    for row in extra:
        row["fix"] = ("mark not enrolled in module_enrolments (" +
                      (row["record"] or "no student_modules row") + ")")
    return missing + extra


def fix_mismatches(conn, actor, admin=False) -> int:
    _admin(admin)
    from education_system.systems.university.infrastructure.database.schemas import (
        enrolment_mirror_schema,
    )
    if enrolment_mirror_schema.installed(conn.execute):
        done = enrolment_mirror_schema.reconcile(conn.execute)
        return done["copies_made"] + done["statuses_fixed"] + done["orphan_enrolments_removed"]
    fixed = 0
    for row in mismatches(conn):
        status = row["record"] if row["record"] else "withdrawn"
        course = conn.execute("SELECT course FROM students WHERE student_id = ?",
                              (row["student_id"],)).fetchone()
        reg.mirror(conn, row["student_id"], row["module_code"], status,
                   course[0] if course else None)
        fixed += 1
    return fixed
