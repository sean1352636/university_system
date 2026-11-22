"""School Census: the DfE school census return builder (autumn / spring /
summer), its validation report, and a log of each run.

Read-only over the pupil records: the return is built from data already
held, never typed in again.

* **Census day.** Autumn is the first Thursday in October, spring the third
  Thursday in January, summer the third Thursday in May; any other date can
  be chosen. Pupils on roll on census day are in the return.
* **Pupil fields.** UPN, surname, forename, middle names, preferred name,
  date of birth, gender, ethnicity, first language, enrolment status (C -
  single registration), entry date, actual National Curriculum year, SEN
  provision (N / K / E) with primary and secondary type of need (SEN
  details), free school meals eligibility (the FSM flag on the pupil record),
  home postcode. Learner support and post-16 items don't apply to
  Years 7-11 and are left blank ("n/a").
* **Attendance** for the term before the census term (autumn census: last
  summer term; spring: autumn; summer: spring): sessions possible, and
  sessions missed for each reason code, from the session register.
* **Suspensions and permanent exclusions** for the term two terms before
  (autumn: spring; spring: last summer; summer: autumn), as the census
  collects them: category (SUSP / PERM), start date, reason category and
  sessions (school days x 2), from :mod:`modules.behaviour.domain.exclusions`.
* **Validation**: an error or a query per pupil - missing or malformed UPN
  (including a wrong check letter), missing ethnicity / first language
  (this system holds only the EAL flag, so first language is returned as
  ENB / OTB "believed"), missing postcode, SEN support / EHC plan with no
  type of need, an EHC plan with no reference, a year group out of line with
  the date of birth, no attendance marks, unmarked sessions, an exclusion
  with no reason category.
* **Returns.** Each built return can be kept in ``census_runs`` (date,
  term, counts, error and query totals - no pupil data), with the old return
  tracking kept: return types (the three school censuses, workforce,
  alternative provision, pupil premium, other), statuses (Planned, Draft,
  Under Review, Validated, Submitted, Accepted, Rejected, Resubmitted,
  Archived), the collection window and deadline, overdue and open-window
  views, submitted / accepted dates and file reference.
* **Files**: CSV (pupils, attendance, exclusions, validation) and a simple
  CTF-style XML file.

Only the data manager (:data:`DATA_MANAGERS`) may build or export a return.
"""

from __future__ import annotations

import datetime as _dt
import json
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.behaviour.domain import exclusions as EX
from education_system.systems.secondary.modules.pupils.domain import sen_details as SEN
from education_system.systems.secondary.modules.reporting.domain import report_common as RC
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import current_year
from education_system.systems.secondary.core.academic_calendar.school_year import today as _today
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = RC.ValidationError
PermissionDenied = RC.PermissionDenied
NotFound = RC.NotFound

TERMS: tuple[str, ...] = ("Autumn", "Spring", "Summer")
#: Reason codes the census counts absence by (authorised then unauthorised).
ABSENCE_CODES: tuple[str, ...] = tuple(
    c for c, (_l, cat) in AT.CODES.items() if cat in (AT.AUTHORISED, AT.UNAUTHORISED))
ERROR, QUERY = "Error", "Query"
_POSTCODE_RE = re.compile(r"^[A-Z]{1,2}[0-9][A-Z0-9]? ?[0-9][A-Z]{2}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS census_runs (
    return_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    return_type      TEXT NOT NULL DEFAULT 'School Census - Autumn',
    census_term      TEXT CHECK (census_term IS NULL OR census_term IN
                     ('Autumn', 'Spring', 'Summer')),
    academic_year    TEXT NOT NULL,
    census_date      TEXT,
    attendance_from  TEXT,
    attendance_to    TEXT,
    exclusions_from  TEXT,
    exclusions_to    TEXT,
    pupils           INTEGER NOT NULL DEFAULT 0,
    by_year          TEXT,
    sen_k            INTEGER NOT NULL DEFAULT 0,
    sen_e            INTEGER NOT NULL DEFAULT 0,
    fsm              INTEGER NOT NULL DEFAULT 0,
    exclusions       INTEGER NOT NULL DEFAULT 0,
    errors           INTEGER NOT NULL DEFAULT 0,
    queries          INTEGER NOT NULL DEFAULT 0,
    error_kinds      TEXT,
    status           TEXT NOT NULL DEFAULT 'Draft' CHECK (status IN
                     ('Planned', 'Draft', 'Under Review', 'Validated', 'Submitted',
                      'Accepted', 'Rejected', 'Resubmitted', 'Archived')),
    window_opens     TEXT,
    window_closes    TEXT,
    deadline         TEXT,
    submitted_on     TEXT,
    submitted_by     TEXT,
    accepted_on      TEXT,
    file_ref         TEXT,
    exported_as      TEXT,
    notes            TEXT,
    created_by       TEXT NOT NULL,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_by       TEXT,
    updated_at       TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_census_runs_year ON census_runs (academic_year, census_term);
"""
database.register_schema("census_runs", _SCHEMA)


# ── Dates ────────────────────────────────────────────────────────────

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> _dt.date:
    d = _dt.date(year, month, 1)
    d += _dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + _dt.timedelta(weeks=n - 1)


def _easter(year: int) -> _dt.date:
    """Easter Sunday (anonymous Gregorian algorithm)."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    day = (h + l_ - 7 * m + 114) % 31 + 1
    return _dt.date(year, month, day)


def _start_year(academic_year: str) -> int:
    m = re.fullmatch(r"(\d{4})/(\d{2})", (academic_year or "").strip())
    if not m:
        raise ValidationError(["School year must look like 2026/27"])
    return int(m.group(1))


def census_date(term: str, academic_year: str | None = None) -> _dt.date:
    """The DfE census day for *term* in *academic_year* (default this year)."""
    term = _term(term)
    y = _start_year(academic_year or current_year())
    if term == "Autumn":
        return _nth_weekday(y, 10, 3, 1)
    return _nth_weekday(y + 1, 1 if term == "Spring" else 5, 3, 3)


def term_dates(term: str, start_year: int) -> tuple[_dt.date, _dt.date]:
    """The census collection window of a term in the school year starting in
    *start_year*: autumn 1 Aug - 31 Dec, spring 1 Jan - Easter Sunday, summer
    Easter Monday - 31 Jul. Only school days inside count."""
    nxt = start_year + 1
    if term == "Autumn":
        return _dt.date(start_year, 8, 1), _dt.date(start_year, 12, 31)
    if term == "Spring":
        return _dt.date(nxt, 1, 1), _easter(nxt)
    return _easter(nxt) + _dt.timedelta(days=1), _dt.date(nxt, 7, 31)


def _back(term: str, start_year: int, n: int) -> tuple[str, int]:
    i = TERMS.index(term) - n
    while i < 0:
        i += 3
        start_year -= 1
    return TERMS[i], start_year


def periods(term: str, academic_year: str | None = None) -> dict[str, Any]:
    """The attendance (previous term) and exclusions (two terms back) windows."""
    term = _term(term)
    y = _start_year(academic_year or current_year())
    at, ay = _back(term, y, 1)
    xt, xy = _back(term, y, 2)
    a0, a1 = term_dates(at, ay)
    x0, x1 = term_dates(xt, xy)
    return {"attendance_term": f"{at} {ay}/{(ay + 1) % 100:02d}",
            "attendance_from": a0.isoformat(), "attendance_to": a1.isoformat(),
            "exclusions_term": f"{xt} {xy}/{(xy + 1) % 100:02d}",
            "exclusions_from": x0.isoformat(), "exclusions_to": x1.isoformat()}


def _term(term: str) -> str:
    t = (term or "").strip().capitalize()
    if t not in TERMS:
        raise ValidationError([f"Census must be one of {', '.join(TERMS)}"])
    return t


def next_census(today: _dt.date | None = None) -> tuple[str, str]:
    """(term, school year) of the next census day on or after *today*."""
    d = today or _today()
    for start in (d.year - 1, d.year):
        year = f"{start}/{(start + 1) % 100:02d}"
        for t in TERMS:
            if census_date(t, year) >= d:
                return t, year
    return "Autumn", f"{d.year}/{(d.year + 1) % 100:02d}"


# ── The return ───────────────────────────────────────────────────────

@dataclass(frozen=True)
class Problem:
    pupil_id: int | None
    admission_no: str
    pupil: str
    severity: str
    field: str
    message: str


@dataclass
class CensusReturn:
    term: str
    academic_year: str
    census_date: str
    periods: dict[str, Any]
    pupils: list[dict[str, Any]] = field(default_factory=list)
    attendance: list[dict[str, Any]] = field(default_factory=list)
    exclusions: list[dict[str, Any]] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)
    return_id: int | None = None

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.severity == ERROR]

    @property
    def queries(self) -> list[Problem]:
        return [p for p in self.problems if p.severity == QUERY]

    def counts(self) -> dict[str, Any]:
        rows = self.pupils
        return {"pupils": len(rows),
                "by_year": dict(sorted(Counter(r["ncyear"] for r in rows).items())),
                "by_gender": dict(Counter(r["gender"] for r in rows)),
                "sen_k": sum(1 for r in rows if r["sen_provision"] == "K"),
                "sen_e": sum(1 for r in rows if r["sen_provision"] == "E"),
                "fsm": sum(1 for r in rows if r["fsm"] == "Y"),
                "eal": sum(1 for r in rows if r["first_language"] == "OTB"),
                "exclusions": len(self.exclusions),
                "suspensions": sum(1 for x in self.exclusions if x["category"] == "SUSP"),
                "permanent": sum(1 for x in self.exclusions if x["category"] == "PERM"),
                "sessions_possible": sum(a["possible"] for a in self.attendance),
                "sessions_missed": sum(a["authorised"] + a["unauthorised"]
                                       for a in self.attendance),
                "errors": len(self.errors), "queries": len(self.queries),
                "error_kinds": dict(Counter(p.field for p in self.errors))}

    def summary_lines(self) -> list[str]:
        c = self.counts()
        pr = self.periods
        return [
            f"{self.term} census {self.academic_year} - census day {self.census_date}",
            f"Attendance: {pr['attendance_term']} ({pr['attendance_from']} to "
            f"{pr['attendance_to']})",
            f"Exclusions: {pr['exclusions_term']} ({pr['exclusions_from']} to "
            f"{pr['exclusions_to']})", "",
            f"Pupils on roll: {c['pupils']}  "
            + "  ".join(f"Y{y}: {n}" for y, n in c["by_year"].items()),
            f"SEN support (K): {c['sen_k']}   EHC plan (E): {c['sen_e']}   "
            f"FSM eligible: {c['fsm']}   EAL: {c['eal']}",
            f"Sessions possible: {c['sessions_possible']}   missed: {c['sessions_missed']}",
            f"Suspensions: {c['suspensions']}   permanent exclusions: {c['permanent']}", "",
            f"Errors: {c['errors']}   queries: {c['queries']}",
            *(f"  {k}: {n}" for k, n in sorted(c["error_kinds"].items(),
                                               key=lambda kv: -kv[1]))]


def census_gender(gender: str | None) -> str:
    """The census gender code: F or M, or "" for Non-binary / Other / Prefer
    not to say (sent blank and flagged, never as the label)."""
    return {"Female": "F", "Male": "M"}.get(gender or "", "")


def _sen_map() -> dict[int, SEN.SenDetails]:
    out = {}
    for p, d in SEN.register():
        if d is not None:
            out[p.pupil_id] = d
    return out


def _attendance(pupils: list[P.Pupil], start: str, end: str) -> dict[int, dict[str, Any]]:
    s, e = _dt.date.fromisoformat(start), min(_dt.date.fromisoformat(end), _today())
    out: dict[int, dict[str, Any]] = {p.pupil_id: {"codes": Counter(), "n": 0}
                                      for p in pupils}
    days = [d.isoformat() for d in AT.school_days(s, e)] if e >= s else []
    if e >= s:
        with database.connect() as conn:
            for r in conn.execute("SELECT pupil_id, code FROM attendance_marks WHERE date "
                                  "BETWEEN ? AND ?", (s.isoformat(), e.isoformat())):
                if r["pupil_id"] in out:
                    out[r["pupil_id"]]["codes"][r["code"]] += 1
                    out[r["pupil_id"]]["n"] += 1
    by = {p.pupil_id: p for p in pupils}
    for pid, d in out.items():
        c = d["codes"]
        cats = Counter()
        for code, n in c.items():
            cats[AT.category_of(code) or AT.UNAUTHORISED] += n
        d["possible"] = cats[AT.PRESENT] + cats[AT.AEA] + cats[AT.AUTHORISED] + \
            cats[AT.UNAUTHORISED]
        d["authorised"], d["unauthorised"] = cats[AT.AUTHORISED], cats[AT.UNAUTHORISED]
        d["expected"] = 2 * sum(1 for x in days if RC.on_roll_on(by[pid], x))
        d["unmarked"] = max(0, d["expected"] - d["n"])
    return out


def build(term: str, academic_year: str | None = None, *, actor: Principal,
          on: Any = None) -> CensusReturn:
    """Build (but don't save) the return for *term*; *on* overrides census day."""
    RC.require_data_manager(actor, "census.build", "census returns")
    term = _term(term)
    year = academic_year or current_year()
    problems: list[str] = []
    day = RC.as_date(on, "Census date", problems) if on not in (None, "") else None
    if problems:
        raise ValidationError(problems)
    day = day or census_date(term, year)
    dayi = day.isoformat()
    pr = periods(term, year)
    ret = CensusReturn(term=term, academic_year=year, census_date=dayi, periods=pr)
    pupils = [p for p in P.list_pupils(roll_status=None) if RC.on_roll_on(p, dayi)]
    sen = _sen_map()
    att = _attendance(pupils, pr["attendance_from"], pr["attendance_to"])

    def flag(p: P.Pupil | None, sev: str, fld: str, msg: str) -> None:
        ret.problems.append(Problem(p.pupil_id if p else None, p.admission_no if p else "",
                                    RC.name(p) if p else "", sev, fld, msg))

    for p in pupils:
        d = sen.get(p.pupil_id)
        ret.pupils.append({
            "pupil_id": p.pupil_id, "admission_no": p.admission_no, "upn": p.upn or "",
            "surname": p.legal_last_name, "forename": p.legal_first_name,
            "middle_names": p.middle_names or "", "preferred_forename": p.preferred_name or "",
            "dob": p.date_of_birth, "gender": census_gender(p.gender),
            "ethnicity": "", "first_language": "OTB" if p.eal else "ENB",
            "enrol_status": "C", "entry_date": p.admission_date, "ncyear": p.year_group,
            "form": p.form_group or "", "sen_provision": p.sen_status,
            "sen_need_1": (d.primary_need if d else "") or "",
            "sen_need_2": (d.secondary_need if d else "") or "",
            "fsm": "Y" if p.fsm_eligible else "N", "postcode": p.postcode or "",
            "learner_support": "n/a", "post16": "n/a"})
        # Validation.
        if not p.upn:
            flag(p, ERROR, "UPN", "UPN missing")
        else:
            why = P.upn_problem(p.upn)
            if why:
                flag(p, ERROR, "UPN", f"UPN {p.upn} invalid: {why}")
        flag(p, ERROR, "Ethnicity", "Ethnicity missing (not recorded on the pupil record)")
        if not census_gender(p.gender):
            flag(p, ERROR, "Gender", f"The census takes F or M only; the record says "
                                     f"'{p.gender}'. Check the legal sex to return.")
        if p.eal:
            flag(p, QUERY, "First language", "EAL pupil: first language not recorded - "
                                             "returned as OTB (believed other than English)")
        if not p.postcode:
            flag(p, ERROR, "Postcode", "Home postcode missing")
        elif not _POSTCODE_RE.match(p.postcode.upper()):
            flag(p, QUERY, "Postcode", f"Postcode '{p.postcode}' doesn't look valid")
        if p.sen_status in ("K", "E") and not (d and d.primary_need):
            flag(p, ERROR, "SEN need", "SEN provision K/E but no primary type of need")
        if p.sen_status == "E" and not (d and d.ehcp_reference):
            flag(p, QUERY, "EHC plan", "EHC plan but no plan reference recorded")
        try:
            expected = P.expected_year_group(p.date_of_birth, day)
        except ValueError:
            flag(p, ERROR, "Date of birth", "Date of birth is not a valid date")
        else:
            if expected != p.year_group:
                flag(p, QUERY, "NC year", f"In Year {p.year_group} but date of birth "
                                          f"suggests Year {expected}")
        a = att[p.pupil_id]
        if a["expected"] and not a["n"]:
            flag(p, QUERY, "Attendance", "No attendance marks for the attendance term")
        elif a["unmarked"]:
            flag(p, QUERY, "Attendance", f"{a['unmarked']} session(s) unmarked in the "
                                         "attendance term")
        if a["expected"] or a["n"]:
            ret.attendance.append({
                "pupil_id": p.pupil_id, "upn": p.upn or "", "admission_no": p.admission_no,
                "pupil": RC.name(p), "possible": a["possible"], "authorised": a["authorised"],
                "unauthorised": a["unauthorised"], "unmarked": a["unmarked"],
                "codes": {c: a["codes"].get(c, 0) for c in ABSENCE_CODES}})

    on_roll = {p.pupil_id for p in pupils}
    for c in EX.list_cases(formal_only=True, date_from=pr["exclusions_from"],
                           date_to=pr["exclusions_to"]):
        if not c.counts or not (pr["exclusions_from"] <= c.start_date <= pr["exclusions_to"]):
            continue
        p = P.get_pupil(c.pupil_id)
        ret.exclusions.append({
            "case_id": c.case_id, "pupil_id": c.pupil_id, "upn": p.upn if p and p.upn else "",
            "admission_no": c.admission_no, "pupil": c.pupil_name,
            "on_roll": c.pupil_id in on_roll,
            "category": "PERM" if c.case_type == EX.PERMANENT else "SUSP",
            "start_date": c.start_date, "reason": c.reason_category or "",
            "sessions": (c.days or 0) * 2 if c.case_type == EX.SUSPENSION else "",
            "days": c.days or ""})
        if not c.reason_category:
            flag(p, ERROR, "Exclusion reason", f"Case #{c.case_id} ({c.start_date}) has no "
                                               "reason category")
        if p is not None and not p.upn:
            flag(p, ERROR, "UPN", f"Excluded pupil (case #{c.case_id}) has no UPN")
    activity_log.record("census.build", principal=actor, term=term, year=year,
                        pupils=len(ret.pupils), errors=len(ret.errors))
    return ret


# ── Returns (the old Census / ILR returns list, now fed by the builder) ──

#: The old return types and statuses, kept.
RETURN_TYPES: tuple[str, ...] = (
    "School Census - Autumn", "School Census - Spring", "School Census - Summer",
    "Workforce Census", "Alternative Provision Census", "Pupil Premium Return", "Other")
RETURN_STATUSES: tuple[str, ...] = (
    "Planned", "Draft", "Under Review", "Validated", "Submitted", "Accepted", "Rejected",
    "Resubmitted", "Archived")
DONE_STATUSES = frozenset({"Submitted", "Accepted", "Resubmitted", "Archived"})
#: Fields the return editor shows (the old ones).
RETURN_FIELDS: tuple[str, ...] = (
    "return_type", "academic_year", "census_date", "status", "window_opens", "window_closes",
    "deadline", "submitted_on", "submitted_by", "accepted_on", "pupils", "errors",
    "queries", "file_ref", "notes")
_DATE_FIELDS = ("census_date", "window_opens", "window_closes", "deadline", "submitted_on",
                "accepted_on")
#: Workflow moves: action -> (allowed from, to).
ACTIONS: dict[str, tuple[frozenset[str] | None, str]] = {
    "validate": (frozenset({"Planned", "Draft", "Under Review", "Rejected"}), "Validated"),
    "submit": (frozenset({"Draft", "Under Review", "Validated"}), "Submitted"),
    "accept": (frozenset({"Submitted", "Resubmitted"}), "Accepted"),
    "reject": (frozenset({"Submitted", "Resubmitted"}), "Rejected"),
    "resubmit": (frozenset({"Rejected"}), "Resubmitted"),
    "archive": (None, "Archived"),
}


def type_for_term(term: str) -> str:
    return f"School Census - {_term(term)}"


def _run_row(r) -> dict[str, Any]:
    d = dict(r)
    d["by_year"] = json.loads(d["by_year"] or "{}")
    d["error_kinds"] = json.loads(d["error_kinds"] or "{}")
    today = _today().isoformat()
    d["is_overdue"] = bool(d["deadline"]) and d["deadline"] < today and \
        d["status"] not in DONE_STATUSES
    d["is_open_window"] = bool(d["window_opens"] and d["window_closes"]) and \
        d["window_opens"] <= today <= d["window_closes"]
    return d


def save_run(ret: CensusReturn, *, actor: Principal, notes: str | None = None) -> int:
    """Keep a built return's counts (no pupil data) as a Draft return."""
    RC.require_data_manager(actor, "census.save", "census returns")
    c = ret.counts()
    with database.connect() as conn:
        rid = conn.execute(
            "INSERT INTO census_runs (return_type, census_term, academic_year, census_date, "
            "attendance_from, attendance_to, exclusions_from, exclusions_to, pupils, by_year, "
            "sen_k, sen_e, fsm, exclusions, errors, queries, error_kinds, notes, created_by, "
            "updated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (type_for_term(ret.term), ret.term, ret.academic_year, ret.census_date,
             ret.periods["attendance_from"], ret.periods["attendance_to"],
             ret.periods["exclusions_from"], ret.periods["exclusions_to"], c["pupils"],
             json.dumps(c["by_year"]), c["sen_k"], c["sen_e"], c["fsm"], c["exclusions"],
             c["errors"], c["queries"], json.dumps(c["error_kinds"]),
             (notes or "").strip()[:500] or None, actor.username or "unknown",
             actor.username or "unknown")).lastrowid
    ret.return_id = int(rid)
    activity_log.record("census.save", target=rid, principal=actor)
    return int(rid)


def _mark_exported(ret: CensusReturn, kind: str) -> None:
    if ret.return_id:
        with database.connect() as conn:
            conn.execute("UPDATE census_runs SET exported_as = trim(COALESCE(exported_as || "
                         "', ', '') || ?), updated_at = datetime('now') WHERE return_id = ?",
                         (kind, ret.return_id))


def get_run(actor: Principal, return_id: int) -> dict[str, Any]:
    RC.require_data_manager(actor, "census.runs", "census returns")
    with database.connect() as conn:
        r = conn.execute("SELECT * FROM census_runs WHERE return_id = ?",
                         (int(return_id),)).fetchone()
    if r is None:
        raise NotFound(f"No census return #{return_id}")
    return _run_row(r)


def list_runs(actor: Principal, *, academic_year: str | None = None,
              return_type: str | None = None, status: str | None = None,
              overdue_only: bool = False, open_only: bool = False) -> list[dict[str, Any]]:
    """The old returns list (with its Type / Year / Status filters and the
    Overdue and Open windows views)."""
    RC.require_data_manager(actor, "census.runs", "census returns")
    sql, where, params = "SELECT * FROM census_runs", [], []
    for col, val in (("academic_year", academic_year), ("return_type", return_type),
                     ("status", status)):
        if val:
            where.append(f"{col} = ?")
            params.append(val)
    if where:
        sql += " WHERE " + " AND ".join(where)
    with database.connect() as conn:
        rows = [_run_row(r) for r in conn.execute(sql + " ORDER BY return_id DESC", params)]
    if overdue_only:
        rows = [r for r in rows if r["is_overdue"]]
    if open_only:
        rows = [r for r in rows if r["is_open_window"]]
    return rows


def _clean_return(data: dict[str, Any], current: dict[str, Any] | None) -> dict[str, Any]:
    problems: list[str] = []
    merged = {k: (current or {}).get(k) for k in RETURN_FIELDS}
    merged.update({k: v for k, v in data.items() if k in RETURN_FIELDS})
    out: dict[str, Any] = {}
    rt = str(merged.get("return_type") or RETURN_TYPES[0]).strip()
    if rt not in RETURN_TYPES:
        problems.append(f"Type must be one of {', '.join(RETURN_TYPES)}")
    out["return_type"] = rt
    year = str(merged.get("academic_year") or "").strip()
    if not year:
        problems.append("Academic year is required")
    elif not re.fullmatch(r"\d{4}/\d{2}", year):
        problems.append("Academic year must look like 2026/27")
    out["academic_year"] = year
    st = str(merged.get("status") or "Draft").strip()
    if st not in RETURN_STATUSES:
        problems.append(f"Status must be one of {', '.join(RETURN_STATUSES)}")
    out["status"] = st
    for k in _DATE_FIELDS:
        d = RC.as_date(merged.get(k), k.replace("_", " ").capitalize(), problems)
        out[k] = d.isoformat() if d else None
    if out["window_opens"] and out["window_closes"] and \
            out["window_closes"] < out["window_opens"]:
        problems.append("Window closes cannot be before window opens")
    for k, label in (("pupils", "Learner count"), ("errors", "Error count"),
                     ("queries", "Warning count")):
        v = merged.get(k)
        if v in (None, ""):
            out[k] = 0
            continue
        try:
            out[k] = int(str(v).strip())
            if out[k] < 0:
                raise ValueError
        except ValueError:
            problems.append(f"{label} must be a whole number of 0 or more")
    for k, n in (("submitted_by", 80), ("file_ref", 200), ("notes", 2000)):
        out[k] = (str(merged.get(k) or "").strip()[:n]) or None
    if problems:
        raise ValidationError(problems)
    if rt.startswith("School Census - "):
        out["census_term"] = rt.rsplit(" ", 1)[1]
    else:
        out["census_term"] = None
    return out


def create_return(data: dict[str, Any], *, actor: Principal) -> dict[str, Any]:
    """A return recorded by hand (the old New return), e.g. a workforce census."""
    RC.require_data_manager(actor, "census.create", "census returns")
    c = _clean_return(data, None)
    cols = [*RETURN_FIELDS, "census_term"]
    with database.connect() as conn:
        rid = conn.execute(
            f"INSERT INTO census_runs ({', '.join(cols)}, created_by, updated_by) VALUES "
            f"({', '.join('?' * len(cols))}, ?, ?)",
            (*(c[k] for k in cols), actor.username or "unknown",
             actor.username or "unknown")).lastrowid
    activity_log.record("census.create", target=rid, principal=actor)
    return get_run(actor, rid)


def update_return(return_id: int, changes: dict[str, Any], *, actor: Principal
                  ) -> dict[str, Any]:
    cur = get_run(actor, return_id)
    c = _clean_return(changes, cur)
    cols = [*RETURN_FIELDS, "census_term"]
    with database.connect() as conn:
        conn.execute(f"UPDATE census_runs SET {', '.join(f'{k} = ?' for k in cols)}, "
                     "updated_by = ?, updated_at = datetime('now') WHERE return_id = ?",
                     (*(c[k] for k in cols), actor.username or "unknown", int(return_id)))
    activity_log.record("census.update", target=return_id, principal=actor,
                        fields=",".join(sorted(k for k in changes if k in RETURN_FIELDS)))
    return get_run(actor, return_id)


def move(return_id: int, action: str, *, actor: Principal, file_ref: str | None = None
         ) -> dict[str, Any]:
    """The old workflow buttons: validate, submit, accept, reject, resubmit,
    archive."""
    if action not in ACTIONS:
        raise ValidationError([f"Action must be one of {', '.join(ACTIONS)}"])
    cur = get_run(actor, return_id)
    allowed, to = ACTIONS[action]
    if allowed is not None and cur["status"] not in allowed:
        raise ValidationError([f"A {cur['status']} return can't be {to.lower()} "
                               f"(it must be {', '.join(sorted(allowed))})"])
    today = _today().isoformat()
    changes: dict[str, Any] = {"status": to}
    if action in ("submit", "resubmit"):
        changes |= {"submitted_on": today, "submitted_by": actor.username}
        if file_ref:
            changes["file_ref"] = file_ref
    if action == "accept":
        changes["accepted_on"] = today
    return update_return(return_id, changes, actor=actor)


def set_status(return_id: int, status: str, *, actor: Principal) -> dict[str, Any]:
    """The old Status button: any status."""
    return update_return(return_id, {"status": status}, actor=actor)


def record_counts(return_id: int, *, actor: Principal, errors: Any, queries: Any
                  ) -> dict[str, Any]:
    """The old "Record validation counts"."""
    return update_return(return_id, {"errors": errors, "queries": queries}, actor=actor)


def delete_return(return_id: int, *, actor: Principal) -> bool:
    cur = get_run(actor, return_id)
    if cur["status"] in DONE_STATUSES - {"Archived"}:
        raise ValidationError(["A submitted or accepted return is kept - archive it instead"])
    with database.connect() as conn:
        conn.execute("DELETE FROM census_runs WHERE return_id = ?", (int(return_id),))
    activity_log.record("census.delete", target=return_id, principal=actor)
    return True


def runs_summary(actor: Principal) -> dict[str, Any]:
    """The old Summary tab (returns side)."""
    rows = list_runs(actor)
    st = Counter(r["status"] for r in rows)
    return {"total": len(rows), "planned": st["Planned"],
            "in_progress": st["Draft"] + st["Under Review"] + st["Validated"],
            "submitted": st["Submitted"] + st["Resubmitted"], "accepted": st["Accepted"],
            "rejected": st["Rejected"], "overdue": sum(1 for r in rows if r["is_overdue"]),
            "open_windows": sum(1 for r in rows if r["is_open_window"]),
            "by_type": dict(Counter(r["return_type"] for r in rows)),
            "by_status": dict(st)}


# ── Files ────────────────────────────────────────────────────────────

PUPIL_COLUMNS = (("upn", "UPN"), ("surname", "Surname"), ("forename", "Forename"),
                 ("middle_names", "Middle names"), ("preferred_forename", "Preferred forename"),
                 ("dob", "Date of birth"), ("gender", "Gender"), ("ethnicity", "Ethnicity"),
                 ("first_language", "First language"), ("enrol_status", "Enrol status"),
                 ("entry_date", "Entry date"), ("ncyear", "NC year actual"),
                 ("sen_provision", "SEN provision"), ("sen_need_1", "SEN need 1"),
                 ("sen_need_2", "SEN need 2"), ("fsm", "FSM eligible"),
                 ("postcode", "Postcode"), ("learner_support", "Learner support"),
                 ("post16", "Post-16"))
PARTS: dict[str, str] = {"pupils": "Pupils", "attendance": "Attendance",
                         "exclusions": "Exclusions", "problems": "Validation report"}


def table(ret: CensusReturn, part: str) -> tuple[list[str], list[list[Any]]]:
    if part == "pupils":
        return ["Admission no", *(h for _k, h in PUPIL_COLUMNS)], \
            [[r["admission_no"], *(r[k] for k, _h in PUPIL_COLUMNS)] for r in ret.pupils]
    if part == "attendance":
        return (["UPN", "Admission no", "Pupil", "Sessions possible", "Authorised",
                 "Unauthorised", "Unmarked", *ABSENCE_CODES],
                [[a["upn"], a["admission_no"], a["pupil"], a["possible"], a["authorised"],
                  a["unauthorised"], a["unmarked"], *(a["codes"][c] for c in ABSENCE_CODES)]
                 for a in ret.attendance])
    if part == "exclusions":
        return (["UPN", "Admission no", "Pupil", "Category", "Start date", "Reason",
                 "Sessions", "School days", "On roll on census day"],
                [[x["upn"], x["admission_no"], x["pupil"], x["category"], x["start_date"],
                  x["reason"], x["sessions"], x["days"], "Y" if x["on_roll"] else "N"]
                 for x in ret.exclusions])
    if part == "problems":
        return (["Severity", "Admission no", "Pupil", "Field", "Problem"],
                [[p.severity, p.admission_no, p.pupil, p.field, p.message]
                 for p in sorted(ret.problems, key=lambda p: (p.severity != ERROR,
                                                              p.pupil, p.field))])
    raise ValidationError([f"Part must be one of {', '.join(PARTS)}"])


def export_csv(ret: CensusReturn, path: str | Path, part: str = "pupils", *,
               actor: Principal) -> int:
    RC.require_data_manager(actor, "census.export", "census returns")
    head, rows = table(ret, part)
    n = RC.write_csv(path, head, rows, actor=actor, action="census.export", part=part)
    _mark_exported(ret, f"csv:{part}")
    return n


def school_identity() -> tuple[str, str]:
    """(school name, LAESTAB without the slash) from School Settings."""
    try:
        from education_system.systems.secondary.modules.administration.domain import settings as ST
        return (str(ST.get_setting("school_name") or ""),
                str(ST.get_setting("dfe_number") or "").replace("/", ""))
    except Exception:  # noqa: BLE001 - settings unreadable: typed in instead
        return "", ""


def export_xml(ret: CensusReturn, path: str | Path, *, actor: Principal,
               school_name: str = "", laestab: str = "") -> int:
    """A simple CTF-style XML file of the whole return. The school name and
    LAESTAB come from School Settings unless given."""
    RC.require_data_manager(actor, "census.export", "census returns")
    if not (school_name and laestab):
        name, number = school_identity()
        school_name, laestab = school_name or name, laestab or number
    root = ET.Element("SchoolCensus")
    h = ET.SubElement(root, "Header")
    for tag, val in (("CensusTerm", ret.term), ("AcademicYear", ret.academic_year),
                     ("CensusDate", ret.census_date), ("SchoolName", school_name),
                     ("LAEstab", laestab), ("Phase", "Secondary"),
                     ("AttendanceFrom", ret.periods["attendance_from"]),
                     ("AttendanceTo", ret.periods["attendance_to"]),
                     ("ExclusionsFrom", ret.periods["exclusions_from"]),
                     ("ExclusionsTo", ret.periods["exclusions_to"]),
                     ("Generated", _dt.datetime.now().isoformat(timespec="seconds"))):
        ET.SubElement(h, tag).text = str(val)
    att = {a["pupil_id"]: a for a in ret.attendance}
    pupils = ET.SubElement(root, "Pupils")
    for r in ret.pupils:
        pe = ET.SubElement(pupils, "Pupil")
        for k, _h in PUPIL_COLUMNS:
            tag = "".join(w.capitalize() for w in k.split("_"))
            ET.SubElement(pe, tag).text = str(r[k])
        a = att.get(r["pupil_id"])
        if a:
            ae = ET.SubElement(pe, "TermlyAttendance")
            ET.SubElement(ae, "SessionsPossible").text = str(a["possible"])
            for c in ABSENCE_CODES:
                if a["codes"][c]:
                    ET.SubElement(ae, "SessionsMissed", Reason=c).text = str(a["codes"][c])
        for x in (x for x in ret.exclusions if x["pupil_id"] == r["pupil_id"]):
            xe = ET.SubElement(pe, "Exclusion")
            for tag, val in (("Category", x["category"]), ("StartDate", x["start_date"]),
                             ("Reason", x["reason"]), ("Sessions", x["sessions"])):
                ET.SubElement(xe, tag).text = str(val)
    leavers = [x for x in ret.exclusions if not x["on_roll"]]
    if leavers:
        le = ET.SubElement(root, "ExcludedPupilsNotOnRoll")
        for x in leavers:
            xe = ET.SubElement(le, "Exclusion")
            for tag, val in (("UPN", x["upn"]), ("Category", x["category"]),
                             ("StartDate", x["start_date"]), ("Reason", x["reason"]),
                             ("Sessions", x["sessions"])):
                ET.SubElement(xe, tag).text = str(val)
    ET.indent(root)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    activity_log.record("census.export", principal=actor, part="xml", rows=len(ret.pupils))
    _mark_exported(ret, "xml")
    return len(ret.pupils)
