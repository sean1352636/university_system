"""The HESA Data Futures entities this system can source, for one reference
period.

Who is returned: every student with a programme registration (or an annual
registration) overlapping the period, plus anyone whose lifecycle history or
ratified award falls inside it. For each:

* **Student** - SID (``hesa_student_identifiers``), OWNSTU (our student id),
  names, birth date, SEXID, NATIONALITY.
* **Engagement** - one per student here (NUMHUS 1): start = first
  registration, end = withdrawal / completion / award inside the period.
* **StudentCourseSession** - one per programme registration overlapping the
  period (SCSESSIONID = registration id, COURSEID = programme code, SCSMODE),
  with its **SessionYear** (the overlap with the period), **ModuleInstance**
  rows (``student_modules`` started inside the session, outcome from the
  confirmed ``module_grades``) and **FundingAndMonitoring** (FUNDCOMP).
* **Leaver** - when the engagement ended inside the period (RSNENGEND from
  the lifecycle reason through the coding frame / field mappings).
* **QualificationAwarded** - ratified, not superseded awards in the period.
* **EntryQualificationAwarded** - only when the recorded entry qualification
  maps to a QUALTYPEID code; otherwise validation says so.

Values are coded through :class:`hesa_codes.Coder`; an uncoded value is kept
as ``None`` with the raw value beside it so validation can name it.
"""

from __future__ import annotations

from datetime import date

from education_system.systems.university.application.statutory import access as sa
from education_system.systems.university.application.statutory import hesa_codes

_ENDING = ("withdraw", "complete", "close")


def _d(value) -> str | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def _overlaps(start, end, period) -> bool:
    start = _d(start) or period[0]
    end = _d(end) or period[1]
    return start <= period[1] and end >= period[0]


def _in_period(value, period) -> bool:
    value = _d(value)
    return bool(value) and period[0] <= value <= period[1]


def _registrations(conn, period) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if sa.has_table(conn, "programme_registrations"):
        for row in sa.dicts(conn.execute(
                "SELECT registration_id, student_id, programme_code, academic_year, mode_of_study, "
                "status, effective_from, effective_to FROM programme_registrations "
                "ORDER BY effective_from")):
            if _overlaps(row["effective_from"], row["effective_to"], period):
                out.setdefault(row["student_id"], []).append({**row, "source": "programme"})
    if sa.has_table(conn, "student_registrations"):
        for row in sa.dicts(conn.execute(
                "SELECT registration_id, student_id, programme_code, academic_year, mode_of_study, "
                "status, registered_at AS effective_from FROM student_registrations "
                "WHERE status = 'completed'")):
            if row["student_id"] in out or not _in_period(row["effective_from"], period):
                continue
            out.setdefault(row["student_id"], []).append(
                {**row, "effective_to": None, "source": "annual"})
    return out


def _history(conn, period) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if not sa.has_table(conn, "student_lifecycle_history"):
        return out
    for row in sa.dicts(conn.execute(
            "SELECT history_id, student_id, action, from_status, to_status, effective_date, "
            "reason, old_programme, new_programme, new_mode FROM student_lifecycle_history "
            "ORDER BY effective_date, history_id")):
        if _in_period(row["effective_date"], period):
            out.setdefault(row["student_id"], []).append(row)
    return out


def _awards(conn, period) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    if not sa.has_table(conn, "ratified_student_awards"):
        return out
    for row in sa.dicts(conn.execute(
            "SELECT award_id, student_id, programme_code, award_name, classification, "
            "academic_year, ratified_at FROM ratified_student_awards "
            "WHERE status = 'ratified' AND superseded_by_award_id IS NULL")):
        if _in_period(row["ratified_at"], period):
            out.setdefault(row["student_id"], []).append(row)
    return out


def _sids(conn) -> dict[str, str]:
    return dict(conn.execute("SELECT student_id, sid FROM hesa_student_identifiers").fetchall())


def _nationalities(conn) -> dict[str, str]:
    if not sa.has_table(conn, "visa_records"):
        return {}
    return {r[0]: r[1] for r in conn.execute(
        "SELECT student_id, nationality FROM visa_records WHERE nationality IS NOT NULL")}


def _modules(conn, student_id, start, end) -> list[dict]:
    if not sa.has_table(conn, "student_modules"):
        return []
    grades = {}
    if sa.has_table(conn, "module_grades"):
        for code, outcome, status in conn.execute(
                "SELECT module_code, outcome, status FROM module_grades WHERE student_id = ? "
                "ORDER BY COALESCE(attempt, 1)", (student_id,)):
            grades[code] = (str(outcome or "").lower(), str(status or "").lower())
    out = []
    for row in sa.dicts(conn.execute(
            "SELECT module_code, enrollment_date, completion_date, status FROM student_modules "
            "WHERE student_id = ? ORDER BY module_code", (student_id,))):
        started = _d(row["enrollment_date"])
        if started and not (start <= started <= (end or "9999-12-31")):
            continue
        out.append({"MODINSTID": f"{student_id}-{row['module_code']}",
                    "MODID": row["module_code"], "MODINSTSTARTDATE": started,
                    "MODINSTENDDATE": _d(row["completion_date"]),
                    "MODOUT": _module_outcome(row, grades.get(row["module_code"]))})
    return out


def _module_outcome(row, grade) -> str | None:
    if str(row.get("status") or "").lower() == "withdrawn":
        return "2"
    if not grade or grade[1] not in ("confirmed", "final", "ratified", "published"):
        return None
    if grade[0] in ("pass", "passed", "compensated", "condoned"):
        return "1"
    if grade[0] in ("fail", "failed"):
        return "3"
    return None


def _ending(history, awards) -> dict | None:
    """The event that ended the engagement inside the period, if any."""
    ends = [h for h in history if h["action"] in _ENDING]
    if ends and not any(str(h["action"]).startswith("reverse:") and
                        h["effective_date"] >= ends[-1]["effective_date"] for h in history):
        last = ends[-1]
        return {"date": _d(last["effective_date"]), "action": last["action"],
                "reason": last.get("reason")}
    if awards:
        return {"date": _d(awards[-1]["ratified_at"]), "action": "complete",
                "reason": "complete"}
    return None


def _fundcomp(session, ending, period) -> str:
    status = str(session.get("status") or "").lower()
    if ending and ending["action"] == "withdraw":
        return "3"
    if ending or status in ("graduated", "completed"):
        return "1"
    end = _d(session.get("effective_to"))
    if end and end <= period[1] and status not in ("registered", "active"):
        return "3"
    return "2"


def _session(conn, coder, student_id, reg, ending, period) -> dict:
    start = _d(reg.get("effective_from")) or period[0]
    end = _d(reg.get("effective_to")) or (ending or {}).get("date")
    mode_raw = reg.get("mode_of_study")
    return {
        "SCSESSIONID": f"{reg['source'][0].upper()}{reg['registration_id']}",
        "COURSEID": reg.get("programme_code"),
        "SCSSTARTDATE": start, "SCSENDDATE": end,
        "SCSMODE": coder.code("MODE", mode_raw), "_mode_raw": mode_raw,
        "_source": reg["source"],
        "SessionYear": {"SYSTARTDATE": max(start, period[0]),
                        "SYENDDATE": min(end, period[1]) if end else None},
        "ModuleInstance": _modules(conn, student_id, start, end),
        "FundingAndMonitoring": {"FUNDCOMP": _fundcomp(reg, ending, period)},
    }


def _student(conn, coder, row, ctx, period) -> dict:
    sid = row["student_id"]
    regs, history, awards = ctx["regs"].get(sid, []), ctx["hist"].get(sid, []), \
        ctx["awards"].get(sid, [])
    ending = _ending(history, awards)
    nationality = row.get("nationality") or ctx["nations"].get(sid)
    first = min([_d(r.get("effective_from")) or period[0] for r in regs]
                or [_d(row.get("enrollment_date")) or period[0]])
    engagement = {
        "NUMHUS": "1", "OWNENGID": f"{sid}-1", "ENGSTARTDATE": first,
        "ENGENDDATE": (ending or {}).get("date"),
        "StudentCourseSession": [_session(conn, coder, sid, r, ending, period) for r in regs],
        "Leaver": None, "QualificationAwarded": [], "EntryQualificationAwarded": None,
    }
    if ending:
        engagement["Leaver"] = {"ENGENDDATE": ending["date"],
                                "RSNENGEND": coder.code("RSNENGEND", ending["reason"])
                                or coder.code("RSNENGEND", ending["action"]),
                                "_reason_raw": ending["reason"] or ending["action"]}
    for award in awards:
        engagement["QualificationAwarded"].append({
            "QUALAWARDID": str(award["award_id"]), "QUALID": award["programme_code"],
            "QUALRESULT": coder.code("CLASS", award.get("classification")),
            "_class_raw": award.get("classification"), "_award_name": award["award_name"]})
    entry = row.get("entry_qualifications")
    if entry:
        engagement["EntryQualificationAwarded"] = {
            "ENTRYQUALAWARDID": f"{sid}-E1", "QUALTYPEID": coder.code("QUALTYPEID", entry),
            "_raw": entry}
    return {
        "SID": ctx["sids"].get(sid), "OWNSTU": sid,
        "FNAMES": " ".join(p for p in (row.get("first_name"), row.get("middle_name")) if p),
        "SURNAME": row.get("last_name"), "BIRTHDTE": _d(row.get("dob")),
        "SEXID": coder.code("SEXID", row.get("gender")), "_sex_raw": row.get("gender"),
        "NATIONALITY": coder.code("NATION", nationality), "_nation_raw": nationality,
        "Engagement": [engagement],
    }


def _fallback_registration(row, period) -> list[dict]:
    """A student in scope with no registration row: one course session from
    the student record (flagged as derived by validation)."""
    if not row.get("course"):
        return []
    return [{"registration_id": row["student_id"], "programme_code": row["course"],
             "mode_of_study": row.get("mode_of_study"), "status": row.get("status"),
             "effective_from": _d(row.get("enrollment_date")) or period[0],
             "effective_to": None, "source": "student record"}]


def collect(conn, period: tuple[str, str]) -> list[dict]:
    """Every Student entity (with nested entities) for *period* (ISO dates)."""
    coder = hesa_codes.Coder(conn)
    ctx = {"regs": _registrations(conn, period), "hist": _history(conn, period),
           "awards": _awards(conn, period), "sids": _sids(conn),
           "nations": _nationalities(conn)}
    in_scope = set(ctx["regs"]) | set(ctx["hist"]) | set(ctx["awards"])
    wanted = {"student_id", "first_name", "middle_name", "last_name", "dob", "gender",
              "nationality", "course", "mode_of_study", "status", "enrollment_date",
              "entry_qualifications"}
    cols = ", ".join(sorted(wanted & sa.columns(conn, "students")))
    students = []
    # db-audit: ignore[DBW001] - cols is an allow-list intersection of real column names
    for row in sa.dicts(conn.execute(f"SELECT {cols} FROM students ORDER BY student_id")):
        if row["student_id"] not in in_scope:
            continue
        if row["student_id"] not in ctx["regs"]:
            ctx["regs"][row["student_id"]] = _fallback_registration(row, period)
        students.append(_student(conn, coder, row, ctx, period))
    return students


def counts(students: list[dict]) -> dict[str, int]:
    out = {"Student": len(students), "Engagement": 0, "StudentCourseSession": 0,
           "ModuleInstance": 0, "Leaver": 0, "QualificationAwarded": 0,
           "EntryQualificationAwarded": 0}
    for student in students:
        for eng in student["Engagement"]:
            out["Engagement"] += 1
            out["StudentCourseSession"] += len(eng["StudentCourseSession"])
            out["ModuleInstance"] += sum(len(s["ModuleInstance"])
                                         for s in eng["StudentCourseSession"])
            out["Leaver"] += 1 if eng["Leaver"] else 0
            out["QualificationAwarded"] += len(eng["QualificationAwarded"])
            out["EntryQualificationAwarded"] += 1 if eng["EntryQualificationAwarded"] else 0
    return out


__all__ = ["collect", "counts"]
