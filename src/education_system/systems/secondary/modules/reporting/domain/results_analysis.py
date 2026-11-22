"""Results Analysis: grades by assessment point, mock series or exam series.

Read-only. The grades come from where they are kept:

* an **assessment point** (data drop) - the working-at grades in
  :mod:`modules.assessment.domain.assessment_points`;
* a **mock series** - each pupil's subject grade from
  :mod:`modules.examinations.domain.mock_exams` (papers totalled, boundaries
  applied);
* an **exam series** - the final graded results in
  :mod:`modules.examinations.domain.exam_results` (embargoed series are only
  shown to the exams officer, as there).

For the chosen source and filters (year group, subject, form):

* per subject: entries, grade distribution, average grade, % 4+ / 5+ / 7+,
  progress against target grades (above / on track / below / well below,
  using the target-grade rules) and the **subject residual** - how pupils
  did in this subject compared with their own average in their other
  subjects (positive = better here);
* headline figures: pupils, results, average grade, % 4+ / 5+ / 7+, English
  and maths at 4+ and 5+;
* group comparisons (gender, SEN status, FSM, EAL, year group);
* each pupil's average grade and how many results are below target;
* Attainment 8 / Progress 8 headlines from
  :mod:`modules.assessment.domain.headline_measures`;
* any two sources compared pupil by pupil (e.g. mock vs actual);
* CSV export of every table.

GCSE grades are counted as numbers (a combined-science "6-5" is 5.5, U is
0). KS3 steps and BTEC grades appear in the distributions and against
targets but not in the numeric measures.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from education_system.systems.secondary.modules.assessment.domain import assessment_points as AP
from education_system.systems.secondary.modules.examinations.domain import exam_entries as EE
from education_system.systems.secondary.modules.examinations.domain import exam_results as ER
from education_system.systems.secondary.modules.assessment.domain import headline_measures as HM
from education_system.systems.secondary.modules.examinations.domain import mock_exams as MX
from education_system.systems.secondary.modules.assessment.domain import target_grades as TGR
from education_system.systems.secondary.modules.reporting.domain import report_common as RC
from education_system.systems.secondary.modules.pupils.domain import pupils as P
from education_system.systems.secondary.core.permissions.access import Principal
from education_system.systems.secondary.core.academic_calendar.school_year import current_year
from education_system.systems.secondary.infrastructure.logging import activity_log

ValidationError = RC.ValidationError
PermissionDenied = RC.PermissionDenied
NotFound = RC.NotFound

KINDS: dict[str, str] = {"point": "Assessment point", "mock": "Mock series",
                         "exam": "Exam series"}
TARGET_STATUSES = ("Above", "On track", "Below", "Well below", "No target", "No data",
                   "Different scale")
SECTIONS: dict[str, str] = {
    "subjects": "Subjects", "distribution": "Grade distribution", "targets": "Against target",
    "groups": "Groups", "pupils": "Pupils", "headline": "Headline", "a8p8": "Attainment 8 / P8",
}
_ORDER = {g: i for i, g in enumerate(("9", "8", "7", "6", "5", "4", "3", "2", "1", "U",
                                      "D*", "D", "M", "P", "Mastering", "Secure",
                                      "Developing", "Emerging"))}


@dataclass(frozen=True)
class Source:
    kind: str
    source_id: int
    label: str
    detail: str = ""

    @property
    def key(self) -> str:
        return f"{self.kind}:{self.source_id}"


@dataclass(frozen=True)
class Result:
    pupil: P.Pupil
    subject_id: int
    subject_code: str
    subject_name: str
    grade: str

    @property
    def value(self) -> float | None:
        return ER.grade_value(self.grade)


def grade_value(grade: str | None) -> float | None:
    return ER.grade_value(grade)


def _grade_sort(g: str) -> tuple[int, str]:
    return (_ORDER.get(g, 50 if "-" in g else 99), g if "-" not in g else
            f"{9 - (ER.grade_value(g) or 0):04.1f}")


# ── Sources ──────────────────────────────────────────────────────────

def sources(actor: Principal) -> list[Source]:
    """Every assessment point, mock series and (visible) exam series."""
    RC.require_staff(actor, "results_analysis.view")
    out = [Source("point", pt.point_id, f"{pt.name} ({pt.academic_year})",
                  f"Years {pt.years_label}, {pt.status}") for pt in AP.list_points()]
    out += [Source("mock", s.series_id, f"{s.name} (mocks)",
                   f"Year {s.year_group}, {MX.STATUS_LABELS.get(s.status, s.status)}")
            for s in MX.list_series()]
    for s in EE.list_series():
        if ER.can_see(actor, s.series_id):
            out.append(Source("exam", s.series_id, f"{s.name} (exams)",
                              f"{s.season} {s.exam_year}"))
    return out


def parse_source(ref: Any) -> Source:
    """``"point:3"`` / ``("mock", 2)`` / a Source -> Source."""
    if isinstance(ref, Source):
        return ref
    if isinstance(ref, tuple):
        kind, sid = ref
    else:
        kind, _, sid = str(ref or "").partition(":")
    if kind not in KINDS or not str(sid).strip().isdigit():
        raise ValidationError(["Choose an assessment point, mock series or exam series"])
    return Source(kind, int(sid), f"{KINDS[kind]} #{sid}")


def results(actor: Principal, source: Any, *, year_group: Any = None, subject_id: Any = None,
            form: str | None = None) -> list[Result]:
    """The grades from *source*, one per pupil per subject, filtered."""
    RC.require_staff(actor, "results_analysis.view")
    src = parse_source(source)
    yg, sid = RC.int_or_none(year_group), RC.int_or_none(subject_id)
    pupils = {p.pupil_id: p for p in P.list_pupils(roll_status=None)}
    out: list[Result] = []
    if src.kind == "point":
        AP.get_point(src.source_id)
        for g in AP.grades(src.source_id, year_group=yg, subject_id=sid):
            if g.working_at and g.pupil_id in pupils:
                out.append(Result(pupils[g.pupil_id], g.subject_id, g.subject_code,
                                  g.subject_code, g.working_at))
    elif src.kind == "mock":
        MX.get_series(src.source_id)
        for r in MX.subject_results(src.source_id, subject_id=sid):
            if r["grade"]:
                p = pupils.get(r["pupil"].pupil_id, r["pupil"])
                out.append(Result(p, r["subject_id"], r["subject_code"], r["subject_name"],
                                  r["grade"]))
    else:
        EE.get_series(src.source_id)
        if not ER.can_see(actor, src.source_id):
            raise PermissionDenied("These results are still under embargo.")
        for r in ER.list_results(series_id=src.source_id, subject_id=sid, actor=actor):
            if r.graded and r.pupil_id in pupils:
                out.append(Result(pupils[r.pupil_id], r.subject_id, r.subject_code,
                                  r.subject_name, r.final_grade or ""))
    return [r for r in out if (yg is None or r.pupil.year_group == yg)
            and (not form or (r.pupil.form_group or "").lower() == form.strip().lower())]


# ── Analysis ─────────────────────────────────────────────────────────

def _measures(rs: list[Result]) -> dict[str, Any]:
    vals = [v for v in (r.value for r in rs) if v is not None]
    n = len(vals)
    return {"results": len(rs), "numeric": n, "average": RC.mean(vals),
            "pct_4": RC.pct(sum(1 for v in vals if v >= 4), n),
            "pct_5": RC.pct(sum(1 for v in vals if v >= 5), n),
            "pct_7": RC.pct(sum(1 for v in vals if v >= 7), n)}


def _target_status(r: Result, targets: dict[tuple[int, int], str]) -> tuple[str | None, str]:
    t = targets.get((r.pupil.pupil_id, r.subject_id))
    if not t:
        return None, "No target"
    return t, TGR.progress_status(t, r.grade)


def _residuals(rs: list[Result]) -> dict[int, list[float]]:
    """subject -> each pupil's (grade here - their mean in their other subjects)."""
    by_pupil: dict[int, list[Result]] = {}
    for r in rs:
        if r.value is not None:
            by_pupil.setdefault(r.pupil.pupil_id, []).append(r)
    out: dict[int, list[float]] = {}
    for xs in by_pupil.values():
        if len(xs) < 2:
            continue
        total = sum(x.value or 0 for x in xs)
        for x in xs:
            others = (total - (x.value or 0)) / (len(xs) - 1)
            out.setdefault(x.subject_id, []).append((x.value or 0) - others)
    return out


@dataclass(frozen=True)
class Analysis:
    source: Source
    results: list[Result]
    targets: dict[tuple[int, int], str]

    def headline(self) -> dict[str, Any]:
        rs = self.results
        pupils = sorted({r.pupil.pupil_id for r in rs})

        def best(pid: int, word: str) -> float:
            vals = [r.value for r in rs if r.pupil.pupil_id == pid and r.value is not None
                    and (word in r.subject_name.lower() or word in r.subject_code.lower())]
            return max(vals) if vals else 0
        em4 = sum(1 for p in pupils if best(p, "eng") >= 4 and best(p, "mat") >= 4)
        em5 = sum(1 for p in pupils if best(p, "eng") >= 5 and best(p, "mat") >= 5)
        st = Counter(_target_status(r, self.targets)[1] for r in rs)
        return {"pupils": len(pupils), "subjects": len({r.subject_id for r in rs}),
                **_measures(rs),
                "eng_maths_4": em4, "eng_maths_4_pct": RC.pct(em4, len(pupils)),
                "eng_maths_5": em5, "eng_maths_5_pct": RC.pct(em5, len(pupils)),
                **{f"target_{s}": st.get(s, 0) for s in TARGET_STATUSES}}

    def subjects(self) -> list[dict[str, Any]]:
        by: dict[int, list[Result]] = {}
        for r in self.results:
            by.setdefault(r.subject_id, []).append(r)
        res = _residuals(self.results)
        out = []
        for sid, rs in by.items():
            st = Counter(_target_status(r, self.targets)[1] for r in rs)
            out.append({"subject_id": sid, "code": rs[0].subject_code,
                        "subject": rs[0].subject_name, "pupils": len({r.pupil.pupil_id
                                                                      for r in rs}),
                        **_measures(rs),
                        "distribution": dict(sorted(Counter(r.grade for r in rs).items(),
                                                    key=lambda kv: _grade_sort(kv[0]))),
                        "above": st["Above"], "on_track": st["On track"],
                        "below": st["Below"], "well_below": st["Well below"],
                        "no_target": st["No target"],
                        "residual": RC.mean(res.get(sid, [])),
                        "residual_pupils": len(res.get(sid, []))})
        return sorted(out, key=lambda d: d["subject"].lower())

    def grades_seen(self) -> list[str]:
        return sorted({r.grade for r in self.results}, key=_grade_sort)

    def target_rows(self, status: str | None = None) -> list[dict[str, Any]]:
        out = []
        for r in self.results:
            t, st = _target_status(r, self.targets)
            if status and st != status:
                continue
            tv, gv = grade_value(t), r.value
            out.append({"pupil": r.pupil, "subject": r.subject_code, "grade": r.grade,
                        "target": t, "status": st,
                        "gap": round(gv - tv, 1) if tv is not None and gv is not None
                        else None})
        order = {s: i for i, s in enumerate(("Well below", "Below", "On track", "Above"))}
        return sorted(out, key=lambda d: (order.get(d["status"], 9), d["gap"] or 0,
                                          RC.name(d["pupil"]), d["subject"]))

    def groups(self) -> list[dict[str, Any]]:
        out = []
        for label, test in RC.GROUPS:
            rs = [r for r in self.results if test(r.pupil)]
            if not rs and label != "All pupils":
                continue
            st = Counter(_target_status(r, self.targets)[1] for r in rs)
            with_t = sum(st[s] for s in ("Above", "On track", "Below", "Well below"))
            out.append({"group": label, "pupils": len({r.pupil.pupil_id for r in rs}),
                        **_measures(rs),
                        "on_or_above_pct": RC.pct(st["Above"] + st["On track"], with_t)})
        return out

    def pupils(self) -> list[dict[str, Any]]:
        by: dict[int, list[Result]] = {}
        for r in self.results:
            by.setdefault(r.pupil.pupil_id, []).append(r)
        out = []
        for rs in by.values():
            st = Counter(_target_status(r, self.targets)[1] for r in rs)
            vals = [v for v in (r.value for r in rs) if v is not None]
            out.append({"pupil": rs[0].pupil, "subjects": len(rs), "average": RC.mean(vals),
                        "grades": ", ".join(f"{r.subject_code} {r.grade}" for r in
                                            sorted(rs, key=lambda r: r.subject_code)),
                        "above": st["Above"], "on_track": st["On track"],
                        "below": st["Below"] + st["Well below"],
                        "pct_4": RC.pct(sum(1 for v in vals if v >= 4), len(vals))})
        return sorted(out, key=lambda d: (-d["below"], d["average"] if d["average"] is not None
                                          else 99, RC.name(d["pupil"])))


def analyse(actor: Principal, source: Any, *, year_group: Any = None, subject_id: Any = None,
            form: str | None = None) -> Analysis:
    rs = results(actor, source, year_group=year_group, subject_id=subject_id, form=form)
    targets = {(t.pupil_id, t.subject_id): t.target_grade for t in TGR.list_targets()}
    src = parse_source(source)
    match = next((s for s in sources(actor) if s.key == src.key), src)
    activity_log.record("results_analysis.run", principal=actor, source=match.key,
                        results=len(rs))
    return Analysis(match, rs, targets)


def pupil_text(a: Analysis, pupil_id: int) -> str:
    """One pupil's grades in the source with targets (drill down)."""
    rows = [d for d in a.target_rows() if d["pupil"].pupil_id == int(pupil_id)]
    if not rows:
        p = P.get_pupil(int(pupil_id))
        if p is None:
            raise NotFound(f"No pupil with id {pupil_id}")
        return f"{p.display_name}: no grades in {a.source.label}."
    p = rows[0]["pupil"]
    lines = [f"{p.display_name} ({p.admission_no}) - Year {p.year_group} {p.form_group or ''}",
             a.source.label, "", f"{'Subject':<10} {'Grade':<10} {'Target':<10} Status"]
    lines += [f"{d['subject']:<10} {d['grade']:<10} {d['target'] or '-':<10} {d['status']}"
              for d in sorted(rows, key=lambda d: d["subject"])]
    return "\n".join(lines)


# ── Comparing two sources (mock vs actual, point vs point) ──────────

def compare(actor: Principal, first: Any, second: Any, *, year_group: Any = None,
            subject_id: Any = None) -> dict[str, Any]:
    """Pupil-by-pupil, subject-by-subject: *second* minus *first* (numeric
    grades). For mock vs actual pass the mock first."""
    a = {(r.pupil.pupil_id, r.subject_id): r for r in results(
        actor, first, year_group=year_group, subject_id=subject_id)}
    b = {(r.pupil.pupil_id, r.subject_id): r for r in results(
        actor, second, year_group=year_group, subject_id=subject_id)}
    pairs = []
    for k in sorted(set(a) & set(b)):
        x, y = a[k], b[k]
        if x.value is None or y.value is None:
            continue
        pairs.append({"pupil": y.pupil, "subject_id": y.subject_id, "subject": y.subject_code,
                      "first": x.grade, "second": y.grade, "diff": round(y.value - x.value, 1)})
    subjects: dict[int, list[dict[str, Any]]] = {}
    for d in pairs:
        subjects.setdefault(d["subject_id"], []).append(d)
    by_subject = []
    for _sid, ds in sorted(subjects.items(), key=lambda kv: kv[1][0]["subject"]):
        by_subject.append({"subject": ds[0]["subject"], "pairs": len(ds),
                           "first_avg": RC.mean(grade_value(d["first"]) or 0 for d in ds),
                           "second_avg": RC.mean(grade_value(d["second"]) or 0 for d in ds),
                           "avg_diff": RC.mean(d["diff"] for d in ds),
                           "up": sum(1 for d in ds if d["diff"] > 0),
                           "same": sum(1 for d in ds if d["diff"] == 0),
                           "down": sum(1 for d in ds if d["diff"] < 0)})
    return {"pairs": pairs, "subjects": by_subject,
            "only_first": len(set(a) - set(b)), "only_second": len(set(b) - set(a)),
            "avg_diff": RC.mean(d["diff"] for d in pairs)}


# ── Attainment 8 / Progress 8 ────────────────────────────────────────

def a8p8(actor: Principal, *, year_group: int = 11, academic_year: str | None = None,
         record_source: str = "Actual") -> dict[str, Any]:
    """The headline-measures figures for a year group (from its own module)."""
    RC.require_staff(actor, "results_analysis.view")
    year = academic_year or current_year()
    if record_source not in HM.SOURCES:
        raise ValidationError([f"Source must be one of {', '.join(HM.SOURCES)}"])
    h = HM.headline(year_group=int(year_group), academic_year=year,
                    record_source=record_source)
    return {"headline": h,
            "a8": HM.cohort_summary(year_group=year_group, academic_year=year,
                                    record_source=record_source),
            "p8": HM.p8_summary(year_group=year_group, academic_year=year)}


# ── Tables and export ────────────────────────────────────────────────

_HEADLINE_LABELS = (
    ("pupils", "Pupils"), ("subjects", "Subjects"), ("results", "Results"),
    ("numeric", "Numeric (GCSE) grades"), ("average", "Average grade"),
    ("pct_4", "% grade 4+"), ("pct_5", "% grade 5+"), ("pct_7", "% grade 7+"),
    ("eng_maths_4", "English & maths 4+ (pupils)"), ("eng_maths_4_pct", "English & maths 4+ %"),
    ("eng_maths_5", "English & maths 5+ (pupils)"), ("eng_maths_5_pct", "English & maths 5+ %"),
    *((f"target_{s}", f"Against target: {s}") for s in TARGET_STATUSES))


def table(a: Analysis | None, section: str, *, a8: dict[str, Any] | None = None
          ) -> tuple[list[str], list[list[Any]]]:
    if section == "a8p8":
        if a8 is None:
            raise ValidationError(["Run the Attainment 8 / Progress 8 figures first"])
        return (["Group", "Pupils", "With A8", "Average A8", "With P8", "Average P8",
                 "Eng & maths 4+ %", "Eng & maths 5+ %", "EBacc entry %"],
                [[g["group"], g["pupils"], g["with_a8"], g["average_a8"], g["with_p8"],
                  g["average_p8"], g["eng_maths_4"], g["eng_maths_5"], g["ebacc_entry"]]
                 for g in a8["headline"]["groups"]])
    if a is None:
        raise ValidationError(["Choose what to analyse first"])
    if section == "headline":
        h = a.headline()
        return ["Measure", "Value"], [["Source", a.source.label],
                                      *([lab, h[k]] for k, lab in _HEADLINE_LABELS)]
    if section == "subjects":
        return (["Code", "Subject", "Pupils", "Results", "Average", "% 4+", "% 5+", "% 7+",
                 "Above", "On track", "Below", "Well below", "No target", "Residual"],
                [[s["code"], s["subject"], s["pupils"], s["results"], s["average"], s["pct_4"],
                  s["pct_5"], s["pct_7"], s["above"], s["on_track"], s["below"],
                  s["well_below"], s["no_target"], s["residual"]] for s in a.subjects()])
    if section == "distribution":
        grades = a.grades_seen()
        return (["Subject", *grades, "Total"],
                [[s["code"], *(s["distribution"].get(g, 0) for g in grades), s["results"]]
                 for s in a.subjects()])
    if section == "targets":
        return (["Admission no", "Pupil", "Year", "Form", "Subject", "Grade", "Target",
                 "Gap", "Status"],
                [[d["pupil"].admission_no, RC.name(d["pupil"]), d["pupil"].year_group,
                  d["pupil"].form_group, d["subject"], d["grade"], d["target"], d["gap"],
                  d["status"]] for d in a.target_rows()])
    if section == "groups":
        return (["Group", "Pupils", "Results", "Average", "% 4+", "% 5+", "% 7+",
                 "On / above target %"],
                [[g["group"], g["pupils"], g["results"], g["average"], g["pct_4"], g["pct_5"],
                  g["pct_7"], g["on_or_above_pct"]] for g in a.groups()])
    if section == "pupils":
        return (["Admission no", "Pupil", "Year", "Form", "Subjects", "Average", "% 4+",
                 "Above", "On track", "Below", "Grades"],
                [[d["pupil"].admission_no, RC.name(d["pupil"]), d["pupil"].year_group,
                  d["pupil"].form_group, d["subjects"], d["average"], d["pct_4"], d["above"],
                  d["on_track"], d["below"], d["grades"]] for d in a.pupils()])
    raise ValidationError([f"Section must be one of {', '.join(SECTIONS)}"])


def compare_table(c: dict[str, Any], detail: bool = False) -> tuple[list[str], list[list[Any]]]:
    if detail:
        return (["Admission no", "Pupil", "Subject", "First", "Second", "Difference"],
                [[d["pupil"].admission_no, RC.name(d["pupil"]), d["subject"], d["first"],
                  d["second"], d["diff"]] for d in c["pairs"]])
    return (["Subject", "Pupils", "First avg", "Second avg", "Avg difference", "Up", "Same",
             "Down"],
            [[s["subject"], s["pairs"], s["first_avg"], s["second_avg"], s["avg_diff"],
              s["up"], s["same"], s["down"]] for s in c["subjects"]])


def export_csv(path: str | Path, a: Analysis | None, section: str = "subjects", *,
               actor: Principal, a8: dict[str, Any] | None = None) -> int:
    RC.require_staff(actor, "results_analysis.export")
    head, rows = table(a, section, a8=a8)
    return RC.write_csv(path, head, rows, actor=actor, action="results_analysis.export",
                        section=section)


def export_compare_csv(path: str | Path, c: dict[str, Any], *, actor: Principal,
                       detail: bool = True) -> int:
    RC.require_staff(actor, "results_analysis.export")
    head, rows = compare_table(c, detail)
    return RC.write_csv(path, head, rows, actor=actor, action="results_analysis.export",
                        section="compare")
