"""Module enrolments from a file: one row per student and module, enrol
(the default) or withdraw, through ``module_enrolment`` — the same rules
as enrolling one student by hand.

* An enrolment is checked against the module's rules (prerequisites,
  capacity, clashes — ``module_enrolment.eligibility``); a row that fails
  them is refused unless the run is an ``override`` with a reason.
* A withdrawal is refused where the exam board has confirmed and locked
  the student's result on that module.
* ``dry_run=True`` says what each row would do and writes nothing.

A real run is a ``batch_jobs`` job (kind ``actions``, mode
``enrolments``) whose rows can be undone: enrolments it made are withdrawn
and withdrawals it made are re-enrolled.
"""

from __future__ import annotations

from contextlib import closing

from education_system.systems.university.application.batch.jobs import Job

ACTIONS = ("enrol", "withdraw")


def _connect(db_path):
    from education_system.systems.university.infrastructure.database.db import get_connection
    return get_connection(db_path, row_factory=False)


def _module(conn, code):
    if not str(code or "").strip():
        raise ValueError("No module_code")
    row = conn.execute("SELECT module_code FROM modules WHERE UPPER(module_code) = UPPER(?)",
                       (code,)).fetchone()
    if not row:
        raise ValueError(f"No module {code}")
    return row[0]


def _locked(conn, student_id, code) -> bool:
    from education_system.systems.university.application.assessment import module_results
    return module_results.is_locked(conn, student_id, code)


def _plan(conn, row, override):
    from education_system.systems.university.application.modules import (
        enrolment as module_enrolment,
    )
    sid = str(row.get("student_id") or "").strip()
    if not sid:
        raise ValueError("No student_id")
    if not conn.execute("SELECT 1 FROM students WHERE student_id = ?", (sid,)).fetchone():
        raise ValueError(f"No student with ID {sid}")
    code = _module(conn, str(row.get("module_code") or "").strip())
    action = str(row.get("action") or "enrol").strip().lower()
    action = {"enroll": "enrol", "add": "enrol", "drop": "withdraw", "remove": "withdraw",
              "unenrol": "withdraw"}.get(action, action)
    if action not in ACTIONS:
        raise ValueError(f"action must be enrol or withdraw, not {row.get('action')!r}")
    status = conn.execute("SELECT status FROM student_modules WHERE student_id = ? AND "
                          "module_code = ?", (sid, code)).fetchone()
    enrolled = bool(status and status[0] == module_enrolment.ENROLLED)
    if action == "enrol":
        if enrolled:
            return {"action": "unchanged", "sid": sid, "code": code,
                    "message": f"already enrolled on {code}"}
        verdict = module_enrolment.eligibility(conn, code, sid)
        allowed = bool(getattr(verdict, "ok", True))
        why = "; ".join(str(getattr(b, "message", None) or getattr(b, "kind", b))
                        for b in getattr(verdict, "blocks", []))
        if not allowed and not override:
            return {"action": "skip", "sid": sid, "code": code,
                    "message": f"not eligible for {code}: {why or 'module rules'}"}
        return {"action": "enrol", "sid": sid, "code": code,
                "message": f"enrol on {code}" + (" (override)" if not allowed else "")}
    if not enrolled:
        return {"action": "unchanged", "sid": sid, "code": code,
                "message": f"not enrolled on {code}"}
    if _locked(conn, sid, code):
        return {"action": "skip", "sid": sid, "code": code,
                "message": f"the board has confirmed the result on {code}"}
    return {"action": "withdraw", "sid": sid, "code": code, "message": f"withdraw from {code}"}


def _check_run(viewer, reason, override):
    if not viewer.can_update:
        raise ValueError("You do not have permission to change module enrolments")
    if not (reason or "").strip():
        raise ValueError("Give the reason recorded on the job")
    if override and viewer.role not in ("admin", "administrator", "superadmin"):
        raise ValueError("Only an administrator can override the module rules in bulk")


def _apply(conn, plan):
    """Make the change; returns ``(outcome, undo data)``."""
    from education_system.systems.university.application.modules import (
        enrolment as module_enrolment,
    )
    if plan["action"] == "enrol":
        module_enrolment.enrol(conn, plan["code"], plan["sid"])
        return "created", {"student_id": plan["sid"], "module_code": plan["code"],
                           "reverse": "withdraw"}
    module_enrolment.withdraw(conn, plan["code"], plan["sid"])
    return "updated", {"student_id": plan["sid"], "module_code": plan["code"],
                       "reverse": "enrol"}


def _one_row(row_no, row, override, dry_run, job, db_path) -> dict:
    ref = f"{row.get('student_id', '')}:{row.get('module_code', '')}"
    try:
        with closing(_connect(db_path)) as conn:
            plan = _plan(conn, row, override)
            if dry_run or plan["action"] in ("skip", "unchanged"):
                if job:
                    job.row(row_no, ref, "skipped" if plan["action"] == "skip" else "unchanged",
                            plan["message"])
                return {"row_no": row_no, "action": plan["action"], "ref": ref,
                        "message": plan["message"]}
            outcome, undo = _apply(conn, plan)
            conn.commit()
        if job:
            job.row(row_no, ref, outcome, plan["message"], undo)
        return {"row_no": row_no, "action": outcome, "ref": ref, "message": plan["message"]}
    except Exception as exc:
        if job:
            job.row(row_no, ref, "failed", str(exc))
        return {"row_no": row_no, "action": "failed", "ref": ref, "message": str(exc)}


def import_enrolments(rows, viewer, *, reason="", source=None, dry_run=False, override=False,
                      db_path=None, only_rows=None) -> dict:
    """Returns ``{"job_id", "rows": [{row_no, action, ref, message}], "counts"}``."""
    _check_run(viewer, reason, override)
    job = None if dry_run else Job("actions", viewer.username, source=source,
                                   mode="enrolments", reason=reason.strip(), db_path=db_path)
    results = []
    try:
        for row_no, row in enumerate(rows, 2):
            if only_rows is None or row_no in only_rows:
                results.append(_one_row(row_no, row, override, dry_run, job, db_path))
    finally:
        if job:
            job.__exit__(None, None, None)
    counts: dict[str, int] = {}
    for r in results:
        counts[r["action"]] = counts.get(r["action"], 0) + 1
    return {"job_id": job.id if job else None, "rows": results, "counts": counts}


def undo_enrolment_row(data, ref, viewer, reason, *, db_path=None, auth_db_path=None):
    from education_system.systems.university.application.modules import (
        enrolment as module_enrolment,
    )
    with closing(_connect(db_path)) as conn:
        if data["reverse"] == "withdraw":
            if _locked(conn, data["student_id"], data["module_code"]):
                raise ValueError("the board has since confirmed the result")
            module_enrolment.withdraw(conn, data["module_code"], data["student_id"])
        else:
            module_enrolment.enrol(conn, data["module_code"], data["student_id"])
        conn.commit()
