"""Attendance Report: whole-school, year, form or pupil attendance for any
date range (default: this school year to date).

Read-only. Every figure comes from the session register
(``attendance_marks``, owned by :mod:`modules.attendance.domain.attendance`)
and uses its rules: the DfE codes and their categories, "not counted" codes
left out of possible sessions, attendance % = present + approved off-site
activity over possible sessions, persistent absence 10%+ (attendance below
90%) and severe absence 50%+.

What it gives (one pass over the marks):

* the headline figures and a DfE-style summary (possible sessions, overall,
  authorised and unauthorised absence rates, persistent and severe absentee
  counts and rates);
* every pupil's figures, the persistent and severe absence lists;
* a breakdown by code, by weekday and session, a week-by-week trend;
* a comparison of groups held on the pupil record (gender, SEN status, FSM,
  EAL) and of each year group and form;
* one pupil's figures with their code breakdown and weekly trend (drill
  down);
* CSV export of any of those tables.

Pupils who left part-way through the range are included for the days they
were on roll, as the DfE counts them.
"""

from __future__ import annotations

import datetime as _dt
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.attendance.domain import attendance as AT
from education_system.systems.secondary.modules.reporting.domain import report_common as RC
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.infrastructure.logging import activity_log
from education_system.systems.secondary.infrastructure.database import connection as database

ValidationError = RC.ValidationError
PermissionDenied = RC.PermissionDenied
NotFound = RC.NotFound

PERSISTENT = AT.PERSISTENT_ABSENCE
SEVERE = AT.SEVERE_ABSENCE
Summary = AT.Summary

#: Sections that can be exported, in the order the screen shows them.
SECTIONS: dict[str, str] = {
    "summary": "DfE-style summary",
    "pupils": "Pupils",
    "persistent": "Persistent absence",
    "severe": "Severe absence",
    "codes": "By code",
    "weekdays": "By weekday and session",
    "weeks": "Trend by week",
    "groups": "Groups",
    "years": "Year groups",
    "forms": "Forms",
}


@dataclass
class _Acc:
    """Counts for one bucket (a pupil, a group, a week...)."""
    c: Counter = field(default_factory=Counter)

    def add(self, code: str) -> None:
        cat = AT.category_of(code)
        self.c[cat or AT.UNAUTHORISED] += 1
        if code in ("L", "U"):
            self.c["late"] += 1

    def merge(self, other: Summary) -> None:
        for k in ("present", "aea", "authorised", "unauthorised", "not_counted", "late",
                  "unmarked"):
            self.c[k] += getattr(other, k)

    def summary(self, unmarked: int = 0) -> Summary:
        c = self.c
        possible = (c[AT.PRESENT] + c[AT.AEA] + c[AT.AUTHORISED] + c[AT.UNAUTHORISED])
        return Summary(possible=possible, present=c[AT.PRESENT], aea=c[AT.AEA],
                       authorised=c[AT.AUTHORISED], unauthorised=c[AT.UNAUTHORISED],
                       not_counted=c[AT.NOT_COUNTED], late=c["late"],
                       unmarked=unmarked + c["unmarked"])


@dataclass(frozen=True)
class GroupRow:
    group: str
    pupils: int
    summary: Summary
    persistent: int
    severe: int

    @property
    def persistent_pct(self) -> float | None:
        return RC.pct(self.persistent, self.pupils)

    @property
    def severe_pct(self) -> float | None:
        return RC.pct(self.severe, self.pupils)


@dataclass(frozen=True)
class Report:
    start: str
    end: str
    scope: str
    school_days: int
    overall: Summary
    pupils: list[tuple[P.Pupil, Summary]]
    by_code: list[dict[str, Any]]
    by_weekday: list[dict[str, Any]]
    by_week: list[dict[str, Any]]
    groups: list[GroupRow]
    years: list[GroupRow]
    forms: list[GroupRow]

    @property
    def persistent(self) -> list[tuple[P.Pupil, Summary]]:
        return [t for t in self.pupils if t[1].band in ("persistent", "severe")]

    @property
    def severe(self) -> list[tuple[P.Pupil, Summary]]:
        return [t for t in self.pupils if t[1].band == "severe"]

    def dfe_summary(self) -> list[tuple[str, Any]]:
        """The DfE absence measures, as (label, value) rows."""
        o, n = self.overall, len([t for t in self.pupils if t[1].possible])
        return [
            ("Period", f"{self.start} to {self.end}"),
            ("Covering", self.scope),
            ("School days", self.school_days),
            ("Pupils (with possible sessions)", n),
            ("Possible sessions", o.possible),
            ("Sessions attended (incl. approved activity)", o.attended),
            ("Attendance %", o.attendance_pct),
            ("Overall absence (sessions)", o.absent),
            ("Overall absence rate %", o.absence_pct),
            ("Authorised absence (sessions)", o.authorised),
            ("Authorised absence rate %", RC.pct(o.authorised, o.possible)),
            ("Unauthorised absence (sessions)", o.unauthorised),
            ("Unauthorised absence rate %", RC.pct(o.unauthorised, o.possible)),
            ("Late sessions (L and U)", o.late),
            ("Sessions not counted (D, X, Y, Z, #...)", o.not_counted),
            ("Sessions not yet marked", o.unmarked),
            (f"Persistent absentees ({PERSISTENT:g}%+ missed)", len(self.persistent)),
            ("Persistent absence rate %", RC.pct(len(self.persistent), n)),
            (f"Severe absentees ({SEVERE:g}%+ missed)", len(self.severe)),
            ("Severe absence rate %", RC.pct(len(self.severe), n)),
        ]


# ── Building ─────────────────────────────────────────────────────────

def _marks(start: str, end: str, pupil_ids: set[int]) -> dict[int, list[tuple[str, str, str]]]:
    """pupil -> [(date, session, code)] in the range (read-only)."""
    out: dict[int, list[tuple[str, str, str]]] = {}
    with database.connect() as conn:
        for r in conn.execute("SELECT pupil_id, date, session, code FROM attendance_marks "
                              "WHERE date BETWEEN ? AND ? ORDER BY date, session",
                              (start, end)):
            if r["pupil_id"] in pupil_ids:
                out.setdefault(r["pupil_id"], []).append((r["date"], r["session"], r["code"]))
    return out


def _group(label: str, rows: list[tuple[P.Pupil, Summary]]) -> GroupRow:
    acc = _Acc()
    for _p, s in rows:
        acc.merge(s)
    with_possible = [s for _p, s in rows if s.possible]
    return GroupRow(group=label, pupils=len(with_possible), summary=acc.summary(),
                    persistent=sum(1 for s in with_possible if s.band in ("persistent",
                                                                           "severe")),
                    severe=sum(1 for s in with_possible if s.band == "severe"))


def _scope(year_group: Any, form: str | None, pupil: P.Pupil | None) -> str:
    if pupil is not None:
        return f"{pupil.display_name} ({pupil.admission_no})"
    if form:
        return f"Form {form}" + (f", Year {year_group}" if year_group else "")
    if year_group:
        return f"Year {year_group}"
    return "Whole school"


def build(actor: Principal, start: Any = None, end: Any = None, *,
          year_group: Any = None, form: str | None = None, pupil_id: Any = None) -> Report:
    """The whole report for the range and filters."""
    RC.require_staff(actor, "attendance_report.run")
    s, e = RC.date_range(start, end)
    si, ei = s.isoformat(), e.isoformat()
    pupils = RC.cohort(si, ei, year_group=year_group, form=form, pupil_id=pupil_id)
    if pupil_id not in (None, "") and not pupils:
        if P.get_pupil(RC.int_or_none(pupil_id) or 0) is None:
            raise NotFound(f"No pupil with id {pupil_id}")
    days = AT.school_days(s, e)
    day_isos = [d.isoformat() for d in days]
    marks = _marks(si, ei, {p.pupil_id for p in pupils})

    per_pupil: list[tuple[P.Pupil, Summary]] = []
    codes: Counter = Counter()
    code_pupils: dict[str, set[int]] = {}
    weekday: dict[tuple[int, str], _Acc] = {}
    weeks: dict[str, _Acc] = {}
    for p in pupils:
        acc = _Acc()
        rows = marks.get(p.pupil_id, [])
        for day, session, code in rows:
            acc.add(code)
            codes[code] += 1
            code_pupils.setdefault(code, set()).add(p.pupil_id)
            d = _dt.date.fromisoformat(day)
            weekday.setdefault((d.weekday(), session), _Acc()).add(code)
            weeks.setdefault(RC.week_start(d), _Acc()).add(code)
        expected = 2 * sum(1 for d in day_isos if RC.on_roll_on(p, d))
        per_pupil.append((p, acc.summary(unmarked=max(0, expected - len(rows)))))
    per_pupil.sort(key=lambda t: (t[1].attendance_pct is None, t[1].attendance_pct or 0,
                                  t[0].legal_last_name.lower()))
    overall = _Acc()
    for _p, sm in per_pupil:
        overall.merge(sm)

    total = sum(codes.values())
    by_code = [{"code": c, "label": AT.code_label(c),
                "category": AT.CATEGORY_LABELS.get(AT.category_of(c), "Unknown code"),
                "sessions": n, "pct": RC.pct(n, total),
                "pupils": len(code_pupils.get(c, ()))}
               for c, n in sorted(codes.items(), key=lambda kv: (-kv[1], kv[0]))]
    by_weekday = []
    for (wd, session), acc in sorted(weekday.items()):
        sm = acc.summary()
        by_weekday.append({"weekday": RC.WEEKDAYS[wd], "session": session,
                           "possible": sm.possible, "attended": sm.attended,
                           "authorised": sm.authorised, "unauthorised": sm.unauthorised,
                           "late": sm.late, "attendance_pct": sm.attendance_pct})
    by_week = []
    for wk, acc in sorted(weeks.items()):
        sm = acc.summary()
        by_week.append({"week": wk, "possible": sm.possible, "attended": sm.attended,
                        "authorised": sm.authorised, "unauthorised": sm.unauthorised,
                        "late": sm.late, "attendance_pct": sm.attendance_pct,
                        "absence_pct": sm.absence_pct})
    groups = [_group(label, [t for t in per_pupil if test(t[0])])
              for label, test in RC.GROUPS if not label.startswith("Year ")]
    groups = [g for g in groups if g.pupils or g.group == "All pupils"]
    years = [_group(f"Year {y}", [t for t in per_pupil if t[0].year_group == y])
             for y in sorted({p.year_group for p in pupils})]
    forms = [_group(f"{yg} {fm}", [t for t in per_pupil if (t[0].year_group, t[0].form_group
                                                            or "(no form)") == (yg, fm)])
             for yg, fm in sorted({(p.year_group, p.form_group or "(no form)")
                                   for p in pupils})]
    pupil = pupils[0] if pupil_id not in (None, "") and pupils else None
    report = Report(start=si, end=ei, scope=_scope(year_group, form, pupil),
                    school_days=len(days), overall=overall.summary(), pupils=per_pupil,
                    by_code=by_code, by_weekday=by_weekday, by_week=by_week, groups=groups,
                    years=years, forms=forms)
    activity_log.record("attendance_report.run", principal=actor, pupils=len(pupils),
                        year=year_group or "", form=form or "")
    return report


def pupil_detail(actor: Principal, pupil_id: int, start: Any = None, end: Any = None
                 ) -> dict[str, Any]:
    """One pupil (drill down): figures, codes, weeks and the absent sessions."""
    p = P.get_pupil(int(pupil_id))
    if p is None:
        raise NotFound(f"No pupil with id {pupil_id}")
    r = build(actor, start, end, pupil_id=p.pupil_id)
    s, e = r.start, r.end
    absences = [m for m in AT.pupil_history(p.pupil_id, s, e)
                if AT.category_of(m.code) in (AT.AUTHORISED, AT.UNAUTHORISED)]
    summary = r.pupils[0][1] if r.pupils else Summary()
    activity_log.record("attendance_report.pupil", target=p.admission_no, principal=actor)
    return {"pupil": p, "summary": summary, "codes": r.by_code, "weeks": r.by_week,
            "weekdays": r.by_weekday, "absences": absences, "start": s, "end": e}


def pupil_text(d: dict[str, Any]) -> str:
    p, s = d["pupil"], d["summary"]
    lines = [f"{p.display_name} ({p.admission_no}) - Year {p.year_group} {p.form_group or ''}",
             f"{d['start']} to {d['end']}", "",
             f"Attendance {RC.show(s.attendance_pct)}%   absence {RC.show(s.absence_pct)}%"
             + (f"   ({s.band} absence)" if s.band else ""),
             f"Possible {s.possible}, attended {s.attended}, authorised {s.authorised}, "
             f"unauthorised {s.unauthorised}, late {s.late}, unmarked {s.unmarked}", "",
             "By code:"]
    lines += [f"  {c['code']:<3} {c['label']:<50} {c['sessions']}" for c in d["codes"]] \
        or ["  (no marks)"]
    lines += ["", "By week:"]
    lines += [f"  {w['week']}  {RC.show(w['attendance_pct']):>6}%  "
              f"auth {w['authorised']}  unauth {w['unauthorised']}" for w in d["weeks"]]
    lines += ["", "Absent sessions:"]
    lines += [f"  {m.date} {m.session}  {m.code:<3} {m.label}" for m in d["absences"]] \
        or ["  (none)"]
    return "\n".join(lines)


# ── Export ───────────────────────────────────────────────────────────

_PUPIL_HEAD = ["Admission no", "Pupil", "Year", "Form", "Gender", "SEN", "Possible",
               "Attended", "Authorised", "Unauthorised", "Late", "Not counted", "Unmarked",
               "Attendance %", "Absence %", "Band"]
_GROUP_HEAD = ["Group", "Pupils", "Possible", "Attended", "Authorised", "Unauthorised",
               "Attendance %", "Authorised %", "Unauthorised %", "Persistent",
               "Persistent %", "Severe", "Severe %"]


def _pupil_row(p: P.Pupil, s: Summary) -> list[Any]:
    return [p.admission_no, RC.name(p), p.year_group, p.form_group, p.gender, p.sen_status,
            s.possible, s.attended, s.authorised, s.unauthorised, s.late, s.not_counted,
            s.unmarked, s.attendance_pct, s.absence_pct, s.band]


def group_row(g: GroupRow) -> list[Any]:
    s = g.summary
    return [g.group, g.pupils, s.possible, s.attended, s.authorised, s.unauthorised,
            s.attendance_pct, RC.pct(s.authorised, s.possible),
            RC.pct(s.unauthorised, s.possible), g.persistent, g.persistent_pct, g.severe,
            g.severe_pct]


def table(report: Report, section: str) -> tuple[list[str], list[list[Any]]]:
    """(headings, rows) for one section (screen, CLI and CSV share it)."""
    if section == "summary":
        return ["Measure", "Value"], [list(r) for r in report.dfe_summary()]
    if section in ("pupils", "persistent", "severe"):
        rows = getattr(report, section)
        return _PUPIL_HEAD, [_pupil_row(p, s) for p, s in rows]
    if section == "codes":
        return (["Code", "Meaning", "Category", "Sessions", "% of marks", "Pupils"],
                [[c["code"], c["label"], c["category"], c["sessions"], c["pct"], c["pupils"]]
                 for c in report.by_code])
    if section == "weekdays":
        return (["Weekday", "Session", "Possible", "Attended", "Authorised", "Unauthorised",
                 "Late", "Attendance %"],
                [[w["weekday"], w["session"], w["possible"], w["attended"], w["authorised"],
                  w["unauthorised"], w["late"], w["attendance_pct"]] for w in report.by_weekday])
    if section == "weeks":
        return (["Week of", "Possible", "Attended", "Authorised", "Unauthorised", "Late",
                 "Attendance %", "Absence %"],
                [[w["week"], w["possible"], w["attended"], w["authorised"], w["unauthorised"],
                  w["late"], w["attendance_pct"], w["absence_pct"]] for w in report.by_week])
    if section in ("groups", "years", "forms"):
        return _GROUP_HEAD, [group_row(g) for g in getattr(report, section)]
    raise ValidationError([f"Section must be one of {', '.join(SECTIONS)}"])


def export_csv(path: str | Path, report: Report, section: str = "pupils", *,
               actor: Principal) -> int:
    RC.require_staff(actor, "attendance_report.export")
    head, rows = table(report, section)
    return RC.write_csv(path, head, rows, actor=actor, action="attendance_report.export",
                        section=section)
