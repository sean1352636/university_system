"""Validation of a built HESA Data Futures return before anything is written
for upload.

Errors stop the upload file being produced (the draft XML and the report are
still kept so the registry can work through them); warnings are listed for
review. These are this system's own pre-submission checks on the data it
holds - HESA's quality rules run again on upload to the Data Futures portal.
"""

from __future__ import annotations

ERROR, WARNING = "error", "warning"


def _issue(level, student, entity, field, message) -> dict:
    return {"level": level, "student_id": student, "entity": entity, "field": field,
            "message": message}


def _student_rules(s, period) -> list[dict]:
    sid, out = s["OWNSTU"], []
    if not s.get("SID"):
        out.append(_issue(ERROR, sid, "Student", "SID",
                          "No HESA student identifier (SID) recorded"))
    if not s.get("SURNAME"):
        out.append(_issue(ERROR, sid, "Student", "SURNAME", "Surname is missing"))
    birth = s.get("BIRTHDTE")
    if not birth:
        out.append(_issue(ERROR, sid, "Student", "BIRTHDTE", "Date of birth is missing"))
    elif not ("1900-01-01" < birth < period[0]):
        out.append(_issue(ERROR, sid, "Student", "BIRTHDTE",
                          f"Date of birth {birth} is not plausible"))
    elif int(period[0][:4]) - int(birth[:4]) < 15:
        out.append(_issue(WARNING, sid, "Student", "BIRTHDTE",
                          f"Student would be under 15 at the start of the period ({birth})"))
    if not s.get("SEXID"):
        out.append(_issue(ERROR, sid, "Student", "SEXID",
                          f"Sex {s.get('_sex_raw')!r} has no SEXID code"))
    if not s.get("NATIONALITY"):
        out.append(_issue(WARNING, sid, "Student", "NATIONALITY",
                          f"Nationality {s.get('_nation_raw')!r} has no NATION code"
                          if s.get("_nation_raw") else "Nationality not recorded"))
    return out


def _session_rules(sid, scs) -> list[dict]:
    out = []
    if not scs.get("COURSEID"):
        out.append(_issue(ERROR, sid, "StudentCourseSession", "COURSEID",
                          "Course session has no programme code"))
    if not scs.get("SCSMODE"):
        out.append(_issue(ERROR, sid, "StudentCourseSession", "SCSMODE",
                          f"Mode of study {scs.get('_mode_raw')!r} has no MODE code"))
    if scs.get("SCSENDDATE") and scs["SCSENDDATE"] < scs["SCSSTARTDATE"]:
        out.append(_issue(ERROR, sid, "StudentCourseSession", "SCSENDDATE",
                          "Course session ends before it starts"))
    if scs.get("_source") == "student record":
        out.append(_issue(WARNING, sid, "StudentCourseSession", "SCSESSIONID",
                          "No registration record; session derived from the student record"))
    if not scs["ModuleInstance"]:
        out.append(_issue(WARNING, sid, "ModuleInstance", "MODID",
                          "No module instances in this course session"))
    for mod in scs["ModuleInstance"]:
        if not mod.get("MODOUT") and scs.get("SCSENDDATE"):
            out.append(_issue(WARNING, sid, "ModuleInstance", "MODOUT",
                              f"Module {mod['MODID']} has no confirmed outcome"))
    return out


def _engagement_rules(sid, eng) -> list[dict]:
    out = []
    if not eng["StudentCourseSession"]:
        out.append(_issue(ERROR, sid, "Engagement", "StudentCourseSession",
                          "Engagement has no course session"))
    if eng.get("ENGENDDATE") and eng["ENGENDDATE"] < eng["ENGSTARTDATE"]:
        out.append(_issue(ERROR, sid, "Engagement", "ENGENDDATE",
                          "Engagement ends before it starts"))
    leaver = eng.get("Leaver")
    if leaver and not leaver.get("RSNENGEND"):
        out.append(_issue(ERROR, sid, "Leaver", "RSNENGEND",
                          f"Reason for leaving {leaver.get('_reason_raw')!r} has no RSNENGEND "
                          "code (add a Student field mapping for it)"))
    for qual in eng["QualificationAwarded"]:
        if qual.get("_class_raw") and not qual.get("QUALRESULT"):
            out.append(_issue(WARNING, sid, "QualificationAwarded", "QUALRESULT",
                              f"Classification {qual['_class_raw']!r} has no CLASS code"))
    entry = eng.get("EntryQualificationAwarded")
    if entry and not entry.get("QUALTYPEID"):
        out.append(_issue(WARNING, sid, "EntryQualificationAwarded", "QUALTYPEID",
                          f"Entry qualification {entry['_raw']!r} has no QUALTYPEID mapping; "
                          "it is left out"))
    for scs in eng["StudentCourseSession"]:
        out.extend(_session_rules(sid, scs))
    return out


def validate(students: list[dict], period: tuple[str, str]) -> dict:
    """``{"errors": n, "warnings": n, "issues": [...]}`` for a built return."""
    issues: list[dict] = []
    seen_sid: dict[str, str] = {}
    for s in students:
        issues.extend(_student_rules(s, period))
        if s.get("SID"):
            if s["SID"] in seen_sid:
                issues.append(_issue(ERROR, s["OWNSTU"], "Student", "SID",
                                     f"SID also used by {seen_sid[s['SID']]}"))
            seen_sid.setdefault(s["SID"], s["OWNSTU"])
        for eng in s["Engagement"]:
            issues.extend(_engagement_rules(s["OWNSTU"], eng))
    if not students:
        issues.append(_issue(WARNING, None, "Submission", "Student",
                             "Nobody is registered in this reference period"))
    errors = sum(1 for i in issues if i["level"] == ERROR)
    return {"errors": errors, "warnings": len(issues) - errors, "issues": issues}


__all__ = ["ERROR", "WARNING", "validate"]
