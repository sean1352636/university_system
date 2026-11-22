"""Batch imports and bulk runs from a file, row by row through the same
rules as a single change:

* **students** - new students through ``StudentLifecycleService.create``
  (validation, catalogue course by code or name, duplicate check on name +
  date of birth, within the file too, and on e-mail address when the batch
  duplicate rule says so); existing students (by ``student_id``)
  get only the fields the file supplies, with the job's reason recorded, and
  a different course becomes a transfer. Nothing is overwritten wholesale.
* **marks** - an assessment mark per row (score, percentage or ABS /
  ABS-MC) through ``exam_marking`` (referral caps, moderation, module result
  recalculation); refused for students not on the module or with a confirmed
  result.
* **staff** - a ``staff`` record and sign-in per row (staff role only, never
  admin); the person gets an activation email, no password is handled.
* **actions** - a list of student IDs for ``student_bulk_actions``.

``dry_run=True`` returns what each row would do and writes nothing. A real
run records a :class:`batch_jobs.Job` whose rows say how to undo them.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from contextlib import closing
from datetime import date

from education_system.systems.university.application.batch import files as batch_files
from education_system.systems.university.application.batch.jobs import Job

STAFF_ROLE_ALIASES = ("staff", "lecturer", "tutor", "instructor", "teacher", "faculty")
_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{2,31}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _connect(db_path):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path, row_factory=False)


def _service(db_path, auth_db_path):
    from education_system.systems.university.application.students.lifecycle import (
        StudentLifecycleService,
    )
    return StudentLifecycleService(db_path, auth_db_path=auth_db_path)


def _errors(exc):
    errors = getattr(exc, "errors", None)
    return "; ".join(f"{k}: {v}" for k, v in errors.items()) if errors else str(exc)


def _fold(*parts):
    text = unicodedata.normalize("NFKD", " ".join(str(p or "") for p in parts)).casefold()
    return "".join(c for c in text if not unicodedata.combining(c)).strip()


def _key(kind, row_no):
    return f"batch:{kind}:{row_no}:{secrets.token_urlsafe(8)}"


# ── students ────────────────────────────────────────────────────────────


def _course_code(conn, value):
    row = conn.execute("SELECT COALESCE(NULLIF(course_code, ''), code) FROM courses WHERE "
                       "? IN (course_code, code, course_name, name) AND "
                       "LOWER(COALESCE(status, 'active')) = 'active' LIMIT 1",
                       (value,)).fetchone()
    if not row:
        raise ValueError(f"course '{value}' is not in the active catalogue")
    return row[0]


def _command(conn, row):
    from education_system.systems.university.application.students.lifecycle import (
        StudentCommand,
        validate_student_command,
    )
    fields = {k: v for k, v in row.items() if k in StudentCommand.__dataclass_fields__}
    fields.pop("student_id", None)
    fields["course"] = _course_code(conn, row.get("course", ""))
    if fields.get("ucas_tariff"):
        try:
            fields["ucas_tariff"] = int(fields["ucas_tariff"])
        except ValueError:
            raise ValueError("ucas_tariff must be a whole number") from None
    for extra in ("pronouns", "emergency_contact"):
        fields.pop(extra, None)
    return validate_student_command(StudentCommand(**fields))


def _plan_create(conn, row, seen):
    from education_system.systems.university.application.students import (
        record_rules as student_record_rules,
    )
    command = _command(conn, row)
    who = _fold(command.first_name, command.last_name, command.dob)
    if who in seen:
        return {"action": "skip", "message": f"same person as row {seen[who]} of this file"}
    matches = student_record_rules.find_duplicates(conn, command.first_name, command.last_name,
                                                   command.dob)
    if matches:
        return {"action": "skip", "message": "possible duplicate of " +
                ", ".join(m["student_id"] for m in matches)}
    same_email = _email_owner(conn, command)
    if same_email:
        return {"action": "skip", "message": f"e-mail address already belongs to {same_email} "
                                             "(the batch duplicate rule includes e-mail)"}
    return {"action": "create", "command": command, "who": who}


def _email_owner(conn, command):
    """With the duplicate rule set to include e-mail (``batch_window``), the
    student who already has this row's address."""
    from education_system.systems.university.application.batch import window as batch_window
    addresses = [a for a in (command.email_address, command.personal_email) if a]
    if not addresses or not batch_window.duplicate_by_email(conn):
        return None
    marks = ",".join("?" * len(addresses))
    row = conn.execute(f"SELECT student_id FROM students WHERE (LOWER(email_address) IN ({marks}) "  # nosec B608
                       f"OR LOWER(personal_email) IN ({marks})) AND student_id NOT LIKE "
                       "'ERASED-%' LIMIT 1",
                       [a.lower() for a in addresses] * 2).fetchone()
    return row[0] if row else None


def _plan_update(conn, row, current):
    from education_system.systems.university.application.students.lifecycle import (
        StudentLifecycleService,
        validate_update,
    )
    sid = current["student_id"]
    changes = {k: v for k, v in row.items() if k in StudentLifecycleService.UPDATABLE
               and str(v) != str(current.get(k) or "")}
    if changes:
        validate_update(changes)
    transfer = None
    if row.get("course"):
        code = _course_code(conn, row["course"])
        if code != current.get("course") and row["course"] != current.get("course"):
            transfer = code
    if not changes and not transfer:
        return {"action": "unchanged", "ref": sid}
    return {"action": "update", "ref": sid, "changes": changes, "transfer": transfer,
            "old": {k: current.get(k) for k in changes}, "old_course": current.get("course")}


def _current(conn, sid):
    cur = conn.execute("SELECT * FROM students WHERE student_id = ? AND student_id NOT LIKE "
                       "'ERASED-%'", (sid,))
    row = cur.fetchone()
    return dict(zip([d[0] for d in cur.description], row)) if row else None


def plan_student_row(conn, row, mode, seen):
    """What one canonical row would do: create / update / unchanged / skip,
    or raise ValueError with the reason it cannot be imported."""
    sid = (row.get("student_id") or "").strip()
    current = _current(conn, sid) if sid else None
    if current and mode in ("update", "both"):
        return _plan_update(conn, row, current)
    if current:
        return {"action": "skip", "ref": sid, "message": "already exists (mode is create only)"}
    if mode == "update":
        raise ValueError(f"no student with ID '{sid}'" if sid else "student_id is required")
    if sid:
        raise ValueError(f"no student with ID '{sid}' (IDs are assigned on creation)")
    return _plan_create(conn, row, seen)


def _do_student(plan, service, viewer, reason, row_no, provision, auth):
    if plan["action"] == "create":
        created = service.create(plan["command"], actor_id=viewer.username,
                                 idempotency_key=_key("create", row_no))
        if provision:
            service.provision(created.student_id, auth=auth)
        return created.student_id, "created", {"created": created.student_id}
    sid = plan["ref"]
    if plan["changes"]:
        service.update(sid, plan["changes"], actor_id=viewer.username, reason=reason,
                       idempotency_key=_key("update", row_no))
    if plan["transfer"]:
        service.transfer_course(sid, plan["transfer"], actor_id=viewer.username, reason=reason,
                                idempotency_key=_key("transfer", row_no))
    return sid, "updated", {"student_id": sid, "old": plan["old"],
                            "old_course": plan["old_course"] if plan["transfer"] else None}


def _check_student_run(viewer, mode, reason):
    if mode not in ("create", "update", "both"):
        raise ValueError("Mode must be create, update or both")
    if not viewer.can_update:
        raise ValueError("You do not have permission to import students")
    if mode != "create" and not (reason or "").strip():
        raise ValueError("Give a reason; it is recorded on every changed student")


def import_students(rows, viewer, *, mode="create", reason="", source=None, dry_run=False,
                    provision=True, auth=None, db_path=None, auth_db_path=None,
                    only_rows=None) -> dict:
    """``rows`` are canonical dicts (see :func:`batch_files.apply_mapping`).
    ``only_rows`` limits the run to those file row numbers (resuming a run
    that stopped part-way). Returns ``{"job_id", "rows": [{row_no, action,
    ref, message}], "counts"}``."""
    _check_student_run(viewer, mode, reason)
    service = None if dry_run else _service(db_path, auth_db_path)
    job = None if dry_run else Job("students", viewer.username, source=source, mode=mode,
                                   reason=reason, db_path=db_path)
    results, seen = [], {}
    try:
        for row_no, row in enumerate(rows, 2):           # row 1 is the header
            if only_rows is not None and row_no not in only_rows:
                continue
            results.append(_student_row(row_no, row, mode, seen, dry_run, service, viewer,
                                        reason, provision, auth, job, db_path))
    finally:
        if job:
            job.__exit__(None, None, None)
    return _summary(job, results)


def _student_row(row_no, row, mode, seen, dry_run, service, viewer, reason, provision, auth,
                 job, db_path):
    try:
        with closing(_connect(db_path)) as conn:
            plan = plan_student_row(conn, row, mode, seen)
        if plan["action"] == "create":
            seen[plan["who"]] = row_no
        if dry_run or plan["action"] in ("skip", "unchanged"):
            out = {"row_no": row_no, "action": plan["action"], "ref": plan.get("ref"),
                   "message": plan.get("message") or _describe(plan)}
            if job:
                job.row(row_no, plan.get("ref"), "skipped" if plan["action"] == "skip"
                        else "unchanged", out["message"])
            return out
        ref, outcome, undo = _do_student(plan, service, viewer, reason, row_no, provision, auth)
        if job:
            job.row(row_no, ref, outcome, _describe(plan), undo)
        return {"row_no": row_no, "action": outcome, "ref": ref, "message": _describe(plan)}
    except Exception as exc:
        if job:
            job.row(row_no, row.get("student_id"), "failed", _errors(exc))
        return {"row_no": row_no, "action": "failed", "ref": row.get("student_id"),
                "message": _errors(exc)}


def _describe(plan):
    if plan["action"] == "create":
        c = plan["command"]
        return f"new student {c.first_name} {c.last_name} on {c.course}"
    if plan["action"] == "update":
        parts = [f"{k} -> {v}" for k, v in plan["changes"].items()]
        if plan["transfer"]:
            parts.append(f"transfer to {plan['transfer']}")
        return "; ".join(parts)
    return plan.get("message") or plan["action"]


def _summary(job, results):
    counts: dict[str, int] = {}
    for r in results:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    return {"job_id": job.id if job else None, "rows": results, "counts": counts}


def undo_student_row(data, ref, viewer, reason, *, db_path=None, auth_db_path=None):
    service = _service(db_path, auth_db_path)
    if data.get("created"):
        service.deactivate(data["created"], actor_id=viewer.username,
                           reason=f"Import undone: {reason}", idempotency_key=_key("undo", ref))
        return
    sid = data["student_id"]
    if data.get("old_course"):
        service.transfer_course(sid, data["old_course"], actor_id=viewer.username,
                                reason=f"Import undone: {reason}",
                                idempotency_key=_key("undo-transfer", ref))
    if data.get("old"):
        service.update(sid, {k: v for k, v in data["old"].items()}, actor_id=viewer.username,
                       reason=f"Import undone: {reason}", idempotency_key=_key("undo", ref))


# ── marks ───────────────────────────────────────────────────────────────


def _assessment(conn, row):
    if row.get("assessment_id"):
        found = conn.execute("SELECT assessment_id, module_code, max_points, assessment_name "
                             "FROM assessments WHERE assessment_id = ?",
                             (row["assessment_id"],)).fetchone()
    else:
        found = conn.execute("SELECT assessment_id, module_code, max_points, assessment_name "
                             "FROM assessments WHERE module_code = ? AND "
                             "LOWER(assessment_name) = LOWER(?) AND LOWER(COALESCE(status, "
                             "'active')) NOT IN ('draft', 'archived')",
                             (row.get("module_code", ""), row.get("assessment", ""))).fetchone()
    if not found:
        raise ValueError("assessment not found (give assessment_id, or module_code and "
                         "assessment name)")
    return {"id": found[0], "module": found[1], "max": float(found[2] or 100), "name": found[3]}


def _mark_value(row, a):
    from education_system.systems.university.application.exams.marking import ABSENCE_CODES
    raw = (row.get("score") or row.get("percentage") or "").strip()
    if raw.upper() in ABSENCE_CODES:
        return None, raw.upper()
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"'{raw}' is not a mark") from None
    score = value if row.get("score") else value * a["max"] / 100
    if not 0 <= score <= a["max"]:
        raise ValueError(f"mark must be between 0 and {a['max']:g}")
    return round(score, 2), None


def plan_mark_row(conn, row):
    from education_system.systems.university.application.assessment import module_results
    sid = (row.get("student_id") or "").strip()
    a = _assessment(conn, row)
    if not conn.execute("SELECT 1 FROM student_modules WHERE student_id = ? AND module_code = ? "
                        "AND LOWER(COALESCE(status, '')) = 'enrolled'",
                        (sid, a["module"])).fetchone():
        raise ValueError(f"{sid} is not enrolled on {a['module']}")
    if module_results.is_locked(conn, sid, a["module"]):
        raise ValueError(f"{sid}'s {a['module']} result is confirmed by a board")
    score, code = _mark_value(row, a)
    old = conn.execute("SELECT grade_id, score, result_code FROM grades WHERE assessment_id = ? "
                       "AND student_id = ? ORDER BY grade_id DESC LIMIT 1",
                       (a["id"], sid)).fetchone()
    if old and old[1] == score and (old[2] or None) == code:
        return {"action": "unchanged", "ref": sid, "a": a}
    return {"action": "update" if old else "create", "ref": sid, "a": a, "score": score,
            "code": code, "old": old, "comments": row.get("comments")}


def _write_mark(conn, plan, viewer, reason):
    from education_system.systems.university.application.exams import marking as exam_marking
    a, sid, old = plan["a"], plan["ref"], plan["old"]
    if plan["code"]:
        grade_id = exam_marking.record_absence(conn, a["id"], sid, plan["code"], viewer.username,
                                               reason=reason or None)
    elif old:
        exam_marking.log_change(conn, source="grades", record_id=old[0], student_id=sid,
                                module_code=a["module"], old_value=old[2] or old[1],
                                new_value=plan["score"], reason=reason or "batch import",
                                changed_by=viewer.username)
        conn.execute("UPDATE grades SET score = ?, result_code = NULL, comments = COALESCE(?, "
                     "comments) WHERE grade_id = ?", (plan["score"], plan["comments"], old[0]))
        grade_id = old[0]
    else:
        grade_id = conn.execute(
            "INSERT INTO grades (student_id, assessment_id, score, submission_date, comments, "
            "graded_by) VALUES (?, ?, ?, ?, ?, ?)",
            (sid, a["id"], plan["score"], date.today().isoformat(), plan["comments"],
             viewer.username)).lastrowid
    if not plan["code"]:
        exam_marking.after_mark(conn, grade_id, viewer.username)
    return grade_id


def import_marks(rows, viewer, *, reason="", source=None, dry_run=False, db_path=None,
                 only_rows=None) -> dict:
    if not viewer.can_mark:
        raise ValueError("You do not have permission to enter marks")
    job = None if dry_run else Job("marks", viewer.username, source=source, reason=reason,
                                   db_path=db_path)
    results = []
    try:
        with closing(_connect(db_path)) as conn:
            for row_no, row in enumerate(rows, 2):
                if only_rows is not None and row_no not in only_rows:
                    continue
                results.append(_mark_row(conn, row_no, row, viewer, reason, dry_run, job))
    finally:
        if job:
            job.__exit__(None, None, None)
    return _summary(job, results)


def _mark_row(conn, row_no, row, viewer, reason, dry_run, job):
    try:
        plan = plan_mark_row(conn, row)
        a = plan["a"]
        what = (f"{a['module']} {a['name']}: " +
                (plan.get("code") or f"{plan.get('score')}/{a['max']:g}"
                 if plan["action"] != "unchanged" else "same mark"))
        if dry_run or plan["action"] == "unchanged":
            if job:
                job.row(row_no, plan["ref"], "unchanged", what)
            return {"row_no": row_no, "action": plan["action"], "ref": plan["ref"],
                    "message": what}
        conn.execute("SAVEPOINT mark_row")
        grade_id = _write_mark(conn, plan, viewer, reason)
        conn.execute("RELEASE mark_row")
        conn.commit()
        old = plan["old"]
        undo = {"grade_id": grade_id, "created": old is None,
                "old_score": old[1] if old else None, "old_code": old[2] if old else None}
        outcome = "updated" if old else "created"
        if job:
            job.row(row_no, plan["ref"], outcome, what, undo)
        return {"row_no": row_no, "action": outcome, "ref": plan["ref"], "message": what}
    except Exception as exc:
        if conn.in_transaction:
            conn.rollback()
        if job:
            job.row(row_no, row.get("student_id"), "failed", _errors(exc))
        return {"row_no": row_no, "action": "failed", "ref": row.get("student_id"),
                "message": _errors(exc)}


def undo_mark_row(data, ref, viewer, reason, *, db_path=None, auth_db_path=None):
    from education_system.systems.university.application.exams import marking as exam_marking
    from education_system.systems.university.application.assessment import module_results
    with closing(_connect(db_path)) as conn:
        row = conn.execute("SELECT g.student_id, a.module_code FROM grades g JOIN assessments a "
                           "ON a.assessment_id = g.assessment_id WHERE g.grade_id = ?",
                           (data["grade_id"],)).fetchone()
        if not row:
            raise ValueError("the mark no longer exists")
        if module_results.is_locked(conn, row[0], row[1]):
            raise ValueError("the module result has since been confirmed by a board")
        exam_marking.log_change(conn, source="grades", record_id=data["grade_id"],
                                student_id=row[0], module_code=row[1], old_value="imported",
                                new_value=data.get("old_score") or data.get("old_code"),
                                reason=f"Import undone: {reason}", changed_by=viewer.username)
        if data["created"]:
            conn.execute("DELETE FROM grades WHERE grade_id = ?", (data["grade_id"],))
        else:
            conn.execute("UPDATE grades SET score = ?, result_code = ? WHERE grade_id = ?",
                         (data.get("old_score"), data.get("old_code"), data["grade_id"]))
        module_results.recompute_safely(conn, row[0], row[1])
        conn.commit()


# ── staff accounts ──────────────────────────────────────────────────────


def plan_staff_row(conn, row):
    username = (row.get("username") or "").strip().lower()
    if not _USERNAME.match(username):
        raise ValueError("username must be 3-32 lower-case letters, digits, '.', '_' or '-'")
    role = (row.get("role") or "staff").strip().lower()
    if role not in STAFF_ROLE_ALIASES:
        raise ValueError(f"role '{role}' cannot be created in bulk (staff roles only; admins "
                         "are created one at a time)")
    email = (row.get("email") or "").strip()
    if not _EMAIL.match(email):
        raise ValueError("a valid email is required (the activation link is sent there)")
    for table, column in (("staff", "username"), ("users", "username"), ("staff", "email")):
        value = email if column == "email" else username
        if conn.execute(f"SELECT 1 FROM {table} WHERE LOWER({column}) = LOWER(?)",  # nosec B608
                        (value,)).fetchone():
            return {"action": "skip", "ref": username,
                    "message": f"{value} already has an account"}
    name = f"{row.get('first_name', '').strip()} {row.get('last_name', '').strip()}".strip()
    if not name:
        raise ValueError("first and last name are required")
    return {"action": "create", "ref": username, "name": name, "email": email,
            "teaches": str(row.get("teaches", "")).strip().lower() in ("yes", "y", "true", "1"),
            "department": (row.get("department") or "").strip()}


def _create_staff(plan, db_path, auth):
    from education_system.systems.university.services import staff_provisioning
    from education_system.systems.university.services.student_provisioning import (
        send_student_activation,
    )
    with closing(_connect(db_path)) as conn:
        staff_id = conn.execute(
            "INSERT INTO staff (username, password_hash, name, email, role, hire_date, status) "
            "VALUES (?, '!', ?, ?, 'staff', ?, 'active')",
            (plan["ref"], plan["name"], plan["email"], date.today().isoformat())).lastrowid
        if plan["department"] and conn.execute("SELECT 1 FROM sqlite_master WHERE name = "
                                               "'staff_profiles'").fetchone():
            conn.execute("INSERT INTO staff_profiles (user_id, department) VALUES (?, ?)",
                         (plan["ref"], plan["department"]))
        conn.commit()
    member = {"id": staff_id, "username": plan["ref"], "name": plan["name"],
              "email": plan["email"], "role": "staff"}
    login = staff_provisioning.provision_staff_login(member, auth=auth)
    if plan["teaches"]:
        staff_provisioning.provision_instructor_profile(member, db_path)
    sent = login.get("shared_ok") and send_student_activation(plan["email"])
    return ("account created" + ("; activation email sent" if sent else
                                 "; activation email NOT sent - resend from user management"))


def import_staff(rows, viewer, *, reason="", source=None, dry_run=False, auth=None,
                 db_path=None, only_rows=None) -> dict:
    if not viewer.can_manage_users:
        raise ValueError("You do not have permission to create accounts")
    job = None if dry_run else Job("staff", viewer.username, source=source, reason=reason,
                                   db_path=db_path)
    results = []
    try:
        for row_no, row in enumerate(rows, 2):
            if only_rows is not None and row_no not in only_rows:
                continue
            results.append(_staff_row(row_no, row, dry_run, job, auth, db_path))
    finally:
        if job:
            job.__exit__(None, None, None)
    return _summary(job, results)


def _staff_row(row_no, row, dry_run, job, auth, db_path):
    try:
        with closing(_connect(db_path)) as conn:
            plan = plan_staff_row(conn, row)
        if dry_run or plan["action"] == "skip":
            message = plan.get("message") or f"new staff account {plan['ref']} ({plan['name']})"
            if job:
                job.row(row_no, plan["ref"], "skipped", message)
            return {"row_no": row_no, "action": plan["action"], "ref": plan["ref"],
                    "message": message}
        message = _create_staff(plan, db_path, auth)
        if job:
            job.row(row_no, plan["ref"], "created", message, {"username": plan["ref"]})
        return {"row_no": row_no, "action": "created", "ref": plan["ref"], "message": message}
    except Exception as exc:
        if job:
            job.row(row_no, row.get("username"), "failed", _errors(exc))
        return {"row_no": row_no, "action": "failed", "ref": row.get("username"),
                "message": _errors(exc)}


def undo_staff_row(data, ref, viewer, reason, *, db_path=None, auth_db_path=None):
    from education_system.systems.university.services.student_provisioning import (
        set_student_login_active,
    )
    with closing(_connect(db_path)) as conn:
        conn.execute("UPDATE staff SET status = 'inactive' WHERE username = ?",
                     (data["username"],))
        conn.commit()
    set_student_login_active(data["username"], False, auth_db_path)


# ── bulk actions on a list of students ──────────────────────────────────


def run_actions(rows, viewer, action, *, value=None, reason="", subject="", source=None,
                db_path=None, auth_db_path=None) -> dict:
    """``student_bulk_actions`` on the file's student IDs, recorded as a job."""
    from education_system.systems.university.application.students import (
        bulk_actions as student_bulk_actions,
    )
    ids = [r["student_id"] for r in rows if r.get("student_id")]
    result = student_bulk_actions.run(action, ids, viewer, value=value, reason=reason,
                                      subject=subject, db_path=db_path,
                                      auth_db_path=auth_db_path)
    failed = dict(result["failed"])
    label = student_bulk_actions.ACTIONS[action]
    with Job("actions", viewer.username, source=source, mode=action, reason=reason,
             db_path=db_path) as job:
        for row_no, sid in enumerate(dict.fromkeys(ids), 2):
            job.row(row_no, sid, "failed" if sid in failed else "updated",
                    failed.get(sid) or label)
    return {"job_id": job.id, "done": result["done"], "failed": result["failed"]}


def read_and_map(path, kind, mapping=None, mode=None, sheet=None) -> tuple[list[dict], dict]:
    """Read a file (``sheet`` of a workbook) and map it (``mapping`` or
    automatic); refuses a file missing a required column."""
    headers, rows = batch_files.read_table(path, sheet)
    mapping = mapping or batch_files.auto_mapping(kind, headers)
    missing = batch_files.missing_required(kind, mapping, mode)
    if missing:
        raise ValueError(f"Missing column(s): {', '.join(missing)}. Map them or use the "
                         "template.")
    return batch_files.apply_mapping(rows, mapping), mapping


# ── watched folders ─────────────────────────────────────────────────────

WATCH_SUFFIXES = (".csv", ".xlsx", ".json")


def _owner_viewer(conn, username):
    """A watched folder imports with its owner's rights (by role)."""
    from education_system.systems.university.application.students.search import (
        ADMIN_ROLES,
        Viewer,
    )
    row = conn.execute("SELECT role FROM users WHERE username = ?", (username,)).fetchone()
    role = str(row[0] if row else "").lower()
    admin = role in ADMIN_ROLES
    staff = admin or role in STAFF_ROLE_ALIASES
    return Viewer(username=username, role=role, can_view_all=staff, can_update=staff,
                  can_mark=staff, can_withdraw=admin, can_manage_users=admin)


def _move(path, folder, sub, note=None):
    from datetime import datetime
    from pathlib import Path
    target = Path(folder) / sub
    target.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    moved = target / f"{stamp}_{Path(path).name}"
    Path(path).rename(moved)
    if note:
        moved.with_suffix(moved.suffix + ".error.txt").write_text(note, encoding="utf-8")
    return moved


def _run_watch(watch, db_path, auth_db_path):
    from pathlib import Path
    with closing(_connect(db_path)) as conn:
        viewer = _owner_viewer(conn, watch["owner"])
        mapping = batch_files.mapping(conn, watch["mapping_id"]) if watch["mapping_id"] else None
    done, problems = 0, 0
    for path in sorted(p for p in Path(watch["folder"]).iterdir()
                       if p.is_file() and p.suffix.lower() in WATCH_SUFFIXES):
        try:
            rows, _ = read_and_map(path, watch["kind"], mapping, watch["mode"])
            if watch["kind"] == "marks":
                result = import_marks(rows, viewer, reason=watch["reason"], source=str(path),
                                      db_path=db_path)
            else:
                result = import_students(rows, viewer, mode=watch["mode"],
                                         reason=watch["reason"], source=str(path),
                                         db_path=db_path, auth_db_path=auth_db_path)
            _move(path, watch["folder"], "processed")
            done += 1
            problems += result["counts"].get("failed", 0)
        except Exception as exc:
            _move(path, watch["folder"], "failed", _errors(exc))
            problems += 1
    return f"{done} file(s) imported, {problems} problem(s)"


def run_watch_folders(*, db_path=None, auth_db_path=None) -> dict:
    """Import every new file in every active watched folder (the Batch
    Operations window and CLI call this on open and on Run now; folders
    with a daily time are also run by ``batch_schedule.run_due_watches``)."""
    from education_system.systems.university.infrastructure.database.schemas import (
        batch_jobs_schema,
    )
    with closing(_connect(db_path)) as conn:
        batch_jobs_schema.apply_to_connection(conn)
        cur = conn.execute("SELECT * FROM batch_watch_folders WHERE active = 1")
        watches = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]
    ran = []
    for watch in watches:
        try:
            result = _run_watch(watch, db_path, auth_db_path)
        except Exception as exc:
            result = f"failed: {exc}"
        ran.append((watch["id"], result))
        with closing(_connect(db_path)) as conn:
            conn.execute("UPDATE batch_watch_folders SET last_run_at = datetime('now'), "
                         "last_result = ? WHERE id = ?", (result, watch["id"]))
            conn.commit()
    return {"watches": ran}


# ── resuming a run that stopped part-way ────────────────────────────────

STALE_MINUTES = 10


def interrupted(conn) -> list[dict]:
    """Jobs still marked running after :data:`STALE_MINUTES` (the program
    stopped mid-file) whose file is still there to resume from."""
    from pathlib import Path
    from education_system.systems.university.application.batch import jobs as batch_jobs
    batch_jobs.schema.apply_to_connection(conn)
    cur = conn.execute("SELECT * FROM batch_jobs WHERE status = 'running' AND started_at <= "
                       f"datetime('now', '-{STALE_MINUTES} minutes') ORDER BY id DESC")
    names = [d[0] for d in cur.description]
    jobs = [dict(zip(names, r)) for r in cur.fetchall()]
    out = []
    for j in jobs:
        j["rows_done"] = conn.execute("SELECT COUNT(*) FROM batch_job_rows WHERE job_id = ?",
                                      (j["id"],)).fetchone()[0]
        j["file_present"] = bool(j["source"]) and Path(j["source"]).is_file()
        j["resumable"] = j["file_present"] and (
            j["kind"] in ("students", "marks", "staff") or j["mode"] == "enrolments")
        out.append(j)
    return out


def _close_job(job_id, db_path, note):
    with closing(_connect(db_path)) as conn:
        counts = dict(conn.execute("SELECT outcome, COUNT(*) FROM batch_job_rows WHERE "
                                   "job_id = ? GROUP BY outcome", (job_id,)).fetchall())
        conn.execute(
            "UPDATE batch_jobs SET status = 'done', finished_at = datetime('now'), total = ?, "
            "succeeded = ?, skipped = ?, failed = ?, reason = COALESCE(reason, '') || ? "
            "WHERE id = ?",
            (sum(counts.values()), counts.get("created", 0) + counts.get("updated", 0),
             counts.get("skipped", 0) + counts.get("unchanged", 0), counts.get("failed", 0),
             note, job_id))
        conn.commit()


def resume(job_id, viewer, *, auth=None, db_path=None, auth_db_path=None) -> dict:
    """Carry on an interrupted job: the rows its file has that the job never
    reached run as a new job (columns matched automatically), and the old
    job is closed with what it did. Rows already done are not repeated."""
    with closing(_connect(db_path)) as conn:
        match = [j for j in interrupted(conn) if j["id"] == int(job_id)]
        if not match:
            raise ValueError("That job is not an interrupted run")
        old = match[0]
        if not old["resumable"]:
            raise ValueError("Its file is no longer there; import the rest from a new file")
        done = {r[0] for r in conn.execute("SELECT row_no FROM batch_job_rows WHERE job_id = ?",
                                           (old["id"],))}
    if old["actor"] != viewer.username and viewer.role not in ("admin", "administrator",
                                                                "superadmin"):
        raise ValueError("Only the person who started the job (or an admin) can resume it")
    kind = "enrolments" if old["mode"] == "enrolments" else old["kind"]
    rows, _mapping = read_and_map(old["source"], kind, None, old["mode"])
    todo = {n for n in range(2, len(rows) + 2) if n not in done}
    reason = f"{old['reason'] or ''} (resumed job {old['id']})".strip()
    if kind == "students":
        result = import_students(rows, viewer, mode=old["mode"] or "create", reason=reason,
                                 source=old["source"], auth=auth, db_path=db_path,
                                 auth_db_path=auth_db_path, only_rows=todo)
    elif kind == "marks":
        result = import_marks(rows, viewer, reason=reason, source=old["source"],
                              db_path=db_path, only_rows=todo)
    elif kind == "staff":
        result = import_staff(rows, viewer, reason=reason, source=old["source"], auth=auth,
                              db_path=db_path, only_rows=todo)
    else:
        from education_system.systems.university.application.batch import (
            enrolments as batch_enrolments,
        )
        result = batch_enrolments.import_enrolments(rows, viewer, reason=reason,
                                                    source=old["source"], db_path=db_path,
                                                    only_rows=todo)
    _close_job(old["id"], db_path, f" [stopped part-way; rest resumed as job {result['job_id']}]")
    return {**result, "resumed_from": old["id"], "rows_remaining": len(todo)}


def import_files(paths, kind, viewer, *, mode="create", reason="", provision=True, auth=None,
                 sheet=None, db_path=None, auth_db_path=None) -> list[dict]:
    """Import several files of one kind, each as its own job. A file that
    cannot be read is reported and the others carry on."""
    from pathlib import Path
    out = []
    for path in paths:
        name = Path(path).name
        try:
            rows, _mapping = read_and_map(path, kind, None, mode, sheet)
            if kind == "students":
                result = import_students(rows, viewer, mode=mode, reason=reason, source=str(path),
                                         provision=provision, auth=auth, db_path=db_path,
                                         auth_db_path=auth_db_path)
            elif kind == "marks":
                result = import_marks(rows, viewer, reason=reason, source=str(path),
                                      db_path=db_path)
            elif kind == "staff":
                result = import_staff(rows, viewer, reason=reason, source=str(path), auth=auth,
                                      db_path=db_path)
            elif kind == "enrolments":
                from education_system.systems.university.application.batch import (
                    enrolments as batch_enrolments,
                )
                result = batch_enrolments.import_enrolments(rows, viewer, reason=reason,
                                                            source=str(path), db_path=db_path)
            else:
                raise ValueError(f"Cannot import {kind} from several files")
            out.append({"file": name, "job_id": result["job_id"], "counts": result["counts"],
                        "error": None})
        except Exception as exc:
            out.append({"file": name, "job_id": None, "counts": {}, "error": _errors(exc)})
    return out
